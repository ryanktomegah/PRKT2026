"""
test_integration_flows.py — 5 integration test flows (Phase 5 roadmap)

Flow 1: Normal payment failure → bridge offer → funded → repaid
Flow 2: Dispute-blocked payment (DISP code → immediate block)
Flow 3: AML velocity block → no bridge offered
Flow 4: Kill switch active → all new offers halted
Flow 5: High PD thin-file → fee floor applies → offer logged
"""
import time
from datetime import datetime, timezone
from decimal import Decimal

from lip.c2_pd_model.fee import FEE_FLOOR_BPS, compute_fee_bps_from_el, compute_loan_fee
from lip.c2_pd_model.tier_assignment import Tier, TierFeatures, assign_tier
from lip.c3_repayment_engine.corridor_buffer import _WINDOW_SECONDS, CorridorBuffer
from lip.c3_repayment_engine.rejection_taxonomy import (
    RejectionClass,
    classify_rejection_code,
    maturity_days,
)
from lip.c4_dispute_classifier.prefilter import apply_prefilter
from lip.c4_dispute_classifier.taxonomy import DisputeClass
from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.velocity import DOLLAR_CAP_USD, VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogEntryData, DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.state_machines import (
    LoanState,
    LoanStateMachine,
    PaymentState,
    PaymentStateMachine,
)

_SALT = b"integration_test_salt_32bytes___"
_HMAC_KEY = b"integration_test_hmac_32bytes___"


def _make_agent(config=None):
    ks = KillSwitch()
    logger = DecisionLogger(hmac_key=_HMAC_KEY)
    override = HumanOverrideInterface()
    degraded = DegradedModeManager()
    return ExecutionAgent(ks, logger, override, degraded, config or ExecutionConfig())


class TestFlow1NormalPaymentFailureToBridgeLoan:
    """Flow 1: payment fails → bridge offered → funded → repaid."""

    def test_payment_state_machine_full_flow(self):
        sm = PaymentStateMachine()
        assert sm.current_state == PaymentState.MONITORING

        sm.transition(PaymentState.FAILURE_DETECTED)
        assert sm.current_state == PaymentState.FAILURE_DETECTED

        sm.transition(PaymentState.BRIDGE_OFFERED)
        assert sm.current_state == PaymentState.BRIDGE_OFFERED

        sm.transition(PaymentState.FUNDED)
        assert sm.current_state == PaymentState.FUNDED

        sm.transition(PaymentState.REPAID)
        assert sm.current_state == PaymentState.REPAID
        assert sm.is_terminal is True

    def test_loan_state_machine_full_flow(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.REPAYMENT_PENDING)
        sm.transition(LoanState.REPAID)
        assert sm.is_terminal is True

    def test_fee_applied_correctly_for_normal_pd(self):
        fee_bps = compute_fee_bps_from_el(
            pd=Decimal("0.02"), lgd=Decimal("0.30"), ead=Decimal("100000")
        )
        # 0.02 * 0.30 * 10000 = 60 bps → floor → 300
        assert fee_bps == FEE_FLOOR_BPS
        fee = compute_loan_fee(Decimal("100000"), fee_bps, 7)
        assert fee == Decimal("57.53")

    def test_rejection_code_determines_maturity(self):
        cls = classify_rejection_code("AC04")
        assert cls == RejectionClass.CLASS_A
        assert maturity_days(cls) == 3

    def test_end_to_end_execution_offer(self):
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        agent = _make_agent(cfg)
        ctx = {
            "uetr": "flow1-uetr-001",
            "individual_payment_id": "flow1-pid-001",
            "failure_probability": 0.75,
            "pd_score": 0.05,
            "fee_bps": 300,
            "loan_amount": "1000000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": True,
            "maturity_days": 7,
        }
        result = agent.process_payment(ctx)
        assert result["status"] in ("OFFER", "DECLINE")
        assert result["decision_entry_id"] is not None


class TestFlow2DisputeBlockedPayment:
    """Flow 2: DISP rejection code → immediate dispute block, no bridge offered."""

    def test_disp_code_is_block_class(self):
        cls = classify_rejection_code("DISP")
        assert cls == RejectionClass.BLOCK

    def test_prefilter_blocks_immediately(self):
        result = apply_prefilter("DISP")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED

    def test_payment_state_goes_to_dispute_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.DISPUTE_BLOCKED)
        assert sm.current_state == PaymentState.DISPUTE_BLOCKED
        assert sm.is_terminal is True

    def test_execution_agent_blocks_dispute(self):
        agent = _make_agent()
        ctx = {
            "uetr": "flow2-uetr-001",
            "individual_payment_id": "flow2-pid-001",
            "failure_probability": 0.8,
            "pd_score": 0.05,
            "fee_bps": 300,
            "loan_amount": "100000",
            "dispute_class": "DISPUTE_CONFIRMED",
            "aml_passed": True,
        }
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert result["halt_reason"] == "dispute_blocked"

    def test_maturity_days_for_block_is_zero(self):
        assert maturity_days(RejectionClass.BLOCK) == 0


class TestFlow3AMLVelocityBlock:
    """Flow 3: AML velocity check blocks payment, no bridge offered."""

    def test_velocity_check_blocks_at_cap(self):
        checker = VelocityChecker(salt=_SALT)
        checker.record("entity_flow3", DOLLAR_CAP_USD - Decimal("100"), "bene1")
        result = checker.check("entity_flow3", Decimal("200"), "bene2")
        assert result.passed is False
        assert "CAP" in result.reason

    def test_payment_state_goes_to_aml_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.AML_BLOCKED)
        assert sm.current_state == PaymentState.AML_BLOCKED
        assert sm.is_terminal is True

    def test_execution_agent_blocks_aml(self):
        agent = _make_agent()
        ctx = {
            "uetr": "flow3-uetr-001",
            "individual_payment_id": "flow3-pid-001",
            "failure_probability": 0.8,
            "pd_score": 0.05,
            "fee_bps": 300,
            "loan_amount": "100000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": False,
        }
        result = agent.process_payment(ctx)
        assert result["status"] == "BLOCK"
        assert result["halt_reason"] == "aml_blocked"


class TestFlow4KillSwitchHalt:
    """Flow 4: Kill switch activated → all new offers halted."""

    def test_kill_switch_halts_all_offers(self):
        agent = _make_agent()
        agent.kill_switch.activate("emergency stop")

        for i in range(3):
            ctx = {
                "uetr": f"flow4-uetr-{i:03d}",
                "individual_payment_id": f"flow4-pid-{i:03d}",
                "failure_probability": 0.8,
                "pd_score": 0.05,
                "fee_bps": 300,
                "loan_amount": "100000",
                "dispute_class": "NOT_DISPUTE",
                "aml_passed": True,
            }
            result = agent.process_payment(ctx)
            assert result["status"] == "HALT", f"Payment {i} not halted"

    def test_kill_switch_deactivated_allows_offers(self):
        cfg = ExecutionConfig(require_human_review_above_pd=0.99)
        agent = _make_agent(cfg)
        agent.kill_switch.activate()
        agent.kill_switch.deactivate()

        ctx = {
            "uetr": "flow4-resume-001",
            "individual_payment_id": "flow4-resume-pid-001",
            "failure_probability": 0.8,
            "pd_score": 0.05,
            "fee_bps": 300,
            "loan_amount": "100000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": True,
        }
        result = agent.process_payment(ctx)
        assert result["status"] != "HALT"


class TestFlow5ThinFileFeeFloor:
    """Flow 5: High-uncertainty thin-file borrower → fee floor always applies."""

    def test_thin_file_gets_tier3(self):
        feats = TierFeatures(
            has_financial_statements=False,
            has_transaction_history=False,
            has_credit_bureau=False,
            months_history=0,
            transaction_count=0,
        )
        assert assign_tier(feats) == Tier.TIER_3

    def test_thin_file_fee_floor_applies(self):
        """For any thin-file PD, fee_bps should be at the 300 bps floor or above."""
        thin_pds = ["0.05", "0.10", "0.15", "0.20", "0.25"]
        for pd_str in thin_pds:
            fee_bps = compute_fee_bps_from_el(
                pd=Decimal(pd_str),
                lgd=Decimal("0.40"),
                ead=Decimal("100000"),
            )
            assert fee_bps >= FEE_FLOOR_BPS, f"PD={pd_str}: fee_bps={fee_bps} below floor"

    def test_thin_file_fee_calculation(self):
        fee = compute_loan_fee(Decimal("50000"), FEE_FLOOR_BPS, 7)
        # $50K * 300/10000 * 7/365 = $50K * 0.03 * 0.01918... = ~$28.77
        assert Decimal("28.00") < fee < Decimal("30.00")

    def test_decision_log_entry_has_required_fields(self):
        """Decision log entries must always include kms_unavailable_gap and degraded_mode."""
        entry = DecisionLogEntryData(
            entry_id="",
            uetr="flow5-uetr-001",
            individual_payment_id="flow5-pid-001",
            decision_type="OFFER",
            decision_timestamp=datetime.now(tz=timezone.utc).isoformat(),
            failure_probability=0.15,
            pd_score=0.15,
            fee_bps=300,
            loan_amount="50000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
            kms_unavailable_gap=None,
            degraded_mode=False,
            gpu_fallback=False,
        )
        logger = DecisionLogger(hmac_key=_HMAC_KEY)
        eid = logger.log(entry)
        stored = logger.get(eid)
        assert stored.kms_unavailable_gap is None
        assert stored.degraded_mode is False
        assert stored.entry_signature != ""
        assert logger.verify(eid) is True


# ===========================================================================
# Gap 2 integration: combined AML gate (sanctions → velocity → anomaly)
# ===========================================================================

def _make_aml_checker() -> AMLChecker:
    from lip.c6_aml_velocity.velocity import VelocityChecker
    return AMLChecker(velocity_checker=VelocityChecker(salt=_SALT))


class TestCombinedAMLGate:
    """Gap 2: AMLChecker must enforce sanctions before velocity before anomaly."""

    def test_clean_entity_passes_all_gates(self):
        checker = _make_aml_checker()
        result = checker.check("entity_clean", Decimal("1000"), "bene_clean")
        assert result.passed is True

    def test_sanctions_hit_blocks_before_velocity(self):
        """If sanctions fires, velocity must not be recorded."""
        checker = _make_aml_checker()
        result = checker.check(
            "entity_ok", Decimal("500"),
            "bene_ok",
            beneficiary_name="TEST BLOCKED PARTY",
        )
        assert result.passed is False
        # Velocity check for entity_ok should return volume 0 (sanctions blocked before record())
        vol_result = checker._velocity.check("entity_ok", Decimal("0"), "x")
        assert vol_result.dollar_volume_24h == Decimal("0")

    def test_velocity_block_does_not_increment_on_failure(self):
        """A velocity-blocked transaction must not be recorded in the velocity store."""
        checker = _make_aml_checker()
        from lip.c6_aml_velocity.velocity import DOLLAR_CAP_USD
        # Saturate velocity
        checker._velocity.record("entity_sat", DOLLAR_CAP_USD - Decimal("1"), "b1")
        result = checker.check("entity_sat", Decimal("2"), "b2")
        assert result.passed is False
        # Volume should still be DOLLAR_CAP_USD - 1, not incremented further
        vol_result = checker._velocity.check("entity_sat", Decimal("0"), "x")
        assert vol_result.dollar_volume_24h == DOLLAR_CAP_USD - Decimal("1")

    def test_passing_transaction_is_recorded(self):
        """A passing transaction must be recorded in the velocity store."""
        checker = _make_aml_checker()
        amount = Decimal("5000")
        result = checker.check("entity_record", amount, "bene_rec")
        assert result.passed is True
        # After a passing check, velocity volume should equal the amount
        vol_result = checker._velocity.check("entity_record", Decimal("0"), "x")
        assert vol_result.dollar_volume_24h == amount


# ===========================================================================
# Gap 3 integration: corridor buffer 90-day rolling window
# ===========================================================================

class TestCorridorBuffer90DayIntegration:
    """Gap 3: observations stamped >90 days ago must not count toward the tier."""

    def test_expired_observations_not_counted(self):
        buf = CorridorBuffer()
        old_ts = time.time() - _WINDOW_SECONDS - 86_400
        # Inject 200 "old" observations — they should all be pruned
        buf._observations["USD_EUR"] = [(old_ts, float(i)) for i in range(200)]
        assert buf.get_buffer_tier("USD_EUR") == 0

    def test_mixed_window_only_fresh_contribute(self):
        buf = CorridorBuffer()
        old_ts = time.time() - _WINDOW_SECONDS - 86_400
        fresh_ts = time.time()
        # 50 old + 40 fresh → should be Tier 2 (30–100)
        buf._observations["EUR_USD"] = (
            [(old_ts, 1.0)] * 50 + [(fresh_ts, 2.0)] * 40
        )
        tier = buf.get_buffer_tier("EUR_USD")
        assert tier == 2
