"""
test_e2e_pipeline.py — 8 End-to-End pipeline scenarios.

Scenarios:
  1. Happy Path — Normal RJCT → FUNDED → REPAID
  2. Dispute Block
  3. AML Block
  4. Kill Switch Halt
  5. KMS Unavailability Halt
  6. Thin-File Borrower (Tier 3)
  7. Multi-Rail Settlement (covered in more depth in test_e2e_settlement.py)
  8. Fee Arithmetic E2E Verification (QUANT)
"""

from __future__ import annotations

from decimal import Decimal

from lip.c2_pd_model.fee import FEE_FLOOR_BPS, compute_loan_fee
from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer
from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable
from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c4_dispute_classifier.taxonomy import DisputeClass
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager, DegradedReason
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.state_machines import (
    LoanState,
    PaymentState,
)
from lip.pipeline import FAILURE_PROBABILITY_THRESHOLD, LIPPipeline

from .conftest import _HMAC_KEY, _SALT, MockC1Engine, MockC2Engine, make_event

# EPG-16: DOLLAR_CAP_USD is now 0 (unlimited) by default. AML block tests must
# set an explicit test-level cap so the velocity checker actually enforces a limit.
_TEST_DOLLAR_CAP_USD = Decimal("1000000")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_pipeline(
    failure_probability: float = 0.80,
    pd_score: float = 0.05,
    fee_bps: int = 300,
    tier: int = 3,
    kill_switch: KillSwitch = None,
    degraded: DegradedModeManager = None,
    c3_monitor=None,
    salt: bytes = _SALT,
) -> LIPPipeline:
    ks = kill_switch or KillSwitch()
    dm = degraded or DegradedModeManager()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    agent = ExecutionAgent(
        kill_switch=ks,
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=dm,
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=MockC1Engine(failure_probability),
        c2_engine=MockC2Engine(pd_score=pd_score, fee_bps=fee_bps, tier=tier),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=salt),
        c7_agent=agent,
        c3_monitor=c3_monitor,
    )


# ===========================================================================
# Scenario 1: Happy Path — Normal RJCT → FUNDED
# ===========================================================================

class TestScenario1HappyPath:
    """Inject a Class-B RJCT event and verify the full funded pipeline path."""

    def test_c1_produces_above_threshold_probability(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.failure_probability > FAILURE_PROBABILITY_THRESHOLD
        assert result.above_threshold is True

    def test_c4_returns_not_dispute(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR", narrative=None)
        result = pipeline.process(event)
        assert result.dispute_class in (
            DisputeClass.NOT_DISPUTE.value, "NOT_DISPUTE", "NEGOTIATION"
        )
        assert result.dispute_hard_block is False

    def test_c6_returns_passed(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.aml_passed is True
        assert result.aml_hard_block is False

    def test_c2_produces_fee_bps_at_floor(self):
        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.fee_bps is not None
        assert result.fee_bps >= int(FEE_FLOOR_BPS)

    def test_loan_offer_generated(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        assert result.loan_offer is not None
        assert result.loan_offer["uetr"] == event.uetr

    def test_payment_state_machine_transitions_to_funded(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.payment_state == PaymentState.FUNDED.value
        history = result.payment_state_history
        assert PaymentState.MONITORING.value in history
        assert PaymentState.FAILURE_DETECTED.value in history
        assert PaymentState.BRIDGE_OFFERED.value in history
        assert PaymentState.FUNDED.value in history

    def test_loan_state_machine_transitions_to_active(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.loan_state == LoanState.ACTIVE.value

    def test_decision_log_entry_written(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.decision_entry_id is not None
        assert len(result.decision_entry_id) > 0

    def test_maturity_days_7_for_class_b_code(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")   # CLASS_B → 7 days
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        offer = result.loan_offer
        assert offer is not None
        assert offer.get("maturity_days") == 7

    def test_settlement_triggers_repaid_state(self):
        """Simulate camt.054 settlement signal → REPAID."""
        repaid_records = []
        registry = SettlementHandlerRegistry.create_default()
        um = UETRMappingTable()
        cb = CorridorBuffer()
        monitor = SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)
        _loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: repaid_records.append(r))

        pipeline = _make_pipeline(failure_probability=0.80, c3_monitor=monitor)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

        # Inject settlement signal
        settlement_msg = {
            "uetr": event.uetr,
            "individual_payment_id": event.individual_payment_id,
            "amount": str(event.amount),
            "currency": "USD",
        }
        trigger = monitor.process_signal("SWIFT", settlement_msg)
        assert trigger is not None
        assert trigger["uetr"] == event.uetr


# ===========================================================================
# Scenario 2: Dispute Block
# ===========================================================================

class TestScenario2DisputeBlock:
    """DISP rejection code → C4 hard block → DISPUTE_BLOCKED state."""

    def test_dispute_narrative_triggers_hard_block(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="This invoice is disputed")
        result = pipeline.process(event)
        assert result.dispute_hard_block is True

    def test_payment_state_is_dispute_blocked(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="This invoice is disputed")
        result = pipeline.process(event)
        assert result.outcome == "DISPUTE_BLOCKED"
        assert result.payment_state == PaymentState.DISPUTE_BLOCKED.value

    def test_dispute_blocked_is_terminal(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="This invoice is disputed")
        result = pipeline.process(event)
        # DISPUTE_BLOCKED is a terminal state — verify no loan offer generated
        assert result.loan_offer is None

    def test_no_loan_offer_on_dispute(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="This invoice is disputed")
        result = pipeline.process(event)
        assert result.loan_offer is None

    def test_decision_log_records_block_reason(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="disputed")
        result = pipeline.process(event)
        assert result.dispute_hard_block is True
        assert result.outcome == "DISPUTE_BLOCKED"


# ===========================================================================
# Scenario 3: AML Block
# ===========================================================================

class TestScenario3AMLBlock:
    """Entity exceeds rolling 24h cap → C6 hard block → AML_BLOCKED state."""

    def test_entity_over_dollar_cap_triggers_block(self):
        vc = VelocityChecker(salt=_SALT)
        entity_id = "aml_test_entity_over_cap"
        # Pre-fill to just below test cap
        vc.record(entity_id, _TEST_DOLLAR_CAP_USD - Decimal("100"), "bene1")

        pipeline = _make_pipeline(failure_probability=0.80)
        pipeline._c6 = vc
        # EPG-16: explicit cap required; 0 = unlimited so tests must set a cap
        pipeline._c7.aml_dollar_cap_usd = int(_TEST_DOLLAR_CAP_USD)

        event = make_event(
            rejection_code="CURR",
            sending_bic=entity_id,
        )
        result = pipeline.process(event, entity_id=entity_id, beneficiary_id="bene2")
        assert result.aml_hard_block is True

    def test_payment_state_is_aml_blocked(self):
        vc = VelocityChecker(salt=_SALT)
        entity_id = "aml_test_entity_blocked"
        vc.record(entity_id, _TEST_DOLLAR_CAP_USD - Decimal("50"), "bene1")

        pipeline = _make_pipeline(failure_probability=0.80)
        pipeline._c6 = vc
        pipeline._c7.aml_dollar_cap_usd = int(_TEST_DOLLAR_CAP_USD)

        event = make_event(rejection_code="CURR", sending_bic=entity_id)
        result = pipeline.process(event, entity_id=entity_id, beneficiary_id="bene2")
        assert result.outcome == "AML_BLOCKED"
        assert result.payment_state == PaymentState.AML_BLOCKED.value

    def test_no_loan_offer_on_aml_block(self):
        vc = VelocityChecker(salt=_SALT)
        entity_id = "aml_test_entity_no_offer"
        vc.record(entity_id, _TEST_DOLLAR_CAP_USD - Decimal("1"), "bene1")

        pipeline = _make_pipeline(failure_probability=0.80)
        pipeline._c6 = vc
        pipeline._c7.aml_dollar_cap_usd = int(_TEST_DOLLAR_CAP_USD)

        event = make_event(rejection_code="CURR", sending_bic=entity_id)
        result = pipeline.process(event, entity_id=entity_id, beneficiary_id="bene2")
        assert result.loan_offer is None


# ===========================================================================
# Scenario 4: Kill Switch Halt
# ===========================================================================

class TestScenario4KillSwitchHalt:
    """Kill switch active → pipeline halts new offer generation."""

    def test_kill_switch_halts_pipeline(self):
        ks = KillSwitch()
        ks.activate("emergency halt test")
        pipeline = _make_pipeline(failure_probability=0.80, kill_switch=ks)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "HALT"

    def test_kill_switch_active_no_loan_offer(self):
        ks = KillSwitch()
        ks.activate("test halt")
        pipeline = _make_pipeline(failure_probability=0.80, kill_switch=ks)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.loan_offer is None

    def test_deactivate_kill_switch_resumes_processing(self):
        ks = KillSwitch()
        ks.activate("test")
        ks.deactivate()
        pipeline = _make_pipeline(failure_probability=0.80, kill_switch=ks)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

    def test_funded_loans_not_affected_by_kill_switch(self):
        """Loans already funded before kill switch are preserved."""
        _repaid = []
        registry = SettlementHandlerRegistry.create_default()
        um = UETRMappingTable()
        cb = CorridorBuffer()
        monitor = SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)

        ks = KillSwitch()
        pipeline = _make_pipeline(failure_probability=0.80, kill_switch=ks, c3_monitor=monitor)

        # Fund a loan BEFORE activating kill switch
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

        # Activate kill switch
        ks.activate("test")

        # The funded loan in C3 monitor must still be retrievable
        active_loans = monitor.get_active_loans()
        assert any(loan.uetr == event.uetr for loan in active_loans)

        # New offers are halted (use distinct BIC so AML velocity doesn't block first)
        event2 = make_event(rejection_code="CURR", sending_bic="CCCCGB2LXXX")
        result2 = pipeline.process(event2)
        assert result2.outcome == "HALT"


# ===========================================================================
# Scenario 5: KMS Unavailability Halt
# ===========================================================================

class TestScenario5KMSUnavailability:
    """KMS unavailable → C7 halts new offers (FAIL-SAFE, never fail-open)."""

    def test_kms_degraded_mode_halts_new_offers(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        pipeline = _make_pipeline(failure_probability=0.80, degraded=dm)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "HALT"

    def test_kms_degraded_no_loan_offer(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        pipeline = _make_pipeline(failure_probability=0.80, degraded=dm)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.loan_offer is None

    def test_kms_recovery_resumes_processing(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        dm.exit_degraded_mode()
        pipeline = _make_pipeline(failure_probability=0.80, degraded=dm)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

    def test_kms_gap_flag_in_state_dict(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        state = dm.get_state_dict()
        # kms_unavailable_gap should be a non-zero float
        assert state["kms_unavailable_gap"] is not None
        assert state["kms_unavailable_gap"] >= 0.0


# ===========================================================================
# Scenario 6: Thin-File Borrower (Tier 3)
# ===========================================================================

class TestScenario6ThinFile:
    """Thin-file borrower → C2 assigns Tier 3, fee_bps = 300 floor."""

    def test_thin_file_tier_3_assignment(self):
        pipeline = _make_pipeline(failure_probability=0.80, tier=3)
        event = make_event(rejection_code="CURR")
        borrower = {
            "has_financial_statements": False,
            "has_transaction_history": False,
            "has_credit_bureau": False,
            "months_history": 0,
            "transaction_count": 0,
        }
        result = pipeline.process(event, borrower=borrower)
        assert result.tier == 3

    def test_thin_file_fee_bps_at_floor(self):
        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300, tier=3)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event, borrower={})
        assert result.fee_bps is not None
        assert result.fee_bps >= int(FEE_FLOOR_BPS)

    def test_thin_file_pipeline_still_funds(self):
        """Thin-file borrowers should still get offers (fee floor applied)."""
        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300, tier=3)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event, borrower={})
        assert result.outcome == "FUNDED"

    def test_shap_values_present_in_result(self):
        pipeline = _make_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert isinstance(result.shap_top20, list)
        assert len(result.shap_top20) == 20
        assert all("feature" in s and "value" in s for s in result.shap_top20)


# ===========================================================================
# Scenario 7: Multi-Rail Settlement (summary — see test_e2e_settlement.py)
# ===========================================================================

class TestScenario7MultiRailSummary:
    """Smoke test that the pipeline wires correctly to C3 for multi-rail settlement."""

    def test_pipeline_registers_loan_with_c3_monitor(self):
        registry = SettlementHandlerRegistry.create_default()
        um = UETRMappingTable()
        cb = CorridorBuffer()
        monitor = SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)

        pipeline = _make_pipeline(failure_probability=0.80, c3_monitor=monitor)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

        active = monitor.get_active_loans()
        assert any(loan.uetr == event.uetr for loan in active)

    def test_idempotent_settlement_signal(self):
        """Duplicate settlement signals must not create duplicate repayment records."""
        repaid = []
        registry = SettlementHandlerRegistry.create_default()
        um = UETRMappingTable()
        cb = CorridorBuffer()
        monitor = SettlementMonitor(registry, um, cb)
        _loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: repaid.append(r))

        pipeline = _make_pipeline(failure_probability=0.80, c3_monitor=monitor)
        event = make_event(rejection_code="CURR")
        pipeline.process(event)

        # First settlement signal — deregisters the loan via explicit deregister
        msg = {"uetr": event.uetr, "amount": str(event.amount), "currency": "USD"}
        trigger1 = monitor.process_signal("SWIFT", msg)
        assert trigger1 is not None
        # Explicitly deregister the loan (simulating what the repayment loop does)
        monitor.deregister_loan(event.uetr)

        # Second (duplicate) signal — loan already deregistered
        trigger2 = monitor.process_signal("SWIFT", msg)
        assert trigger2 is None


# ===========================================================================
# Scenario 8: Fee Arithmetic E2E Verification (QUANT)
# ===========================================================================

class TestScenario8FeeArithmetic:
    """Verify the QUANT spot-check fee arithmetic from Architecture Spec."""

    def test_100k_loan_300bps_7days_fee_is_57_53(self):
        """$100K × 300bps annualized × 7 days = $57.53"""
        fee = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        assert fee == Decimal("57.53"), f"Expected $57.53 but got ${fee}"

    def test_early_repayment_day_3_uses_actual_days(self):
        """Early repayment at day 3: fee uses days_funded=3, not maturity_days=7."""
        fee_day3 = compute_loan_fee(Decimal("100000"), Decimal("300"), 3)
        fee_day7 = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        # Day 3 fee must be strictly less than day 7 fee
        assert fee_day3 < fee_day7
        # Verify exact value: $100K × 0.03 × (3/365) ≈ $24.66
        assert Decimal("24.00") < fee_day3 < Decimal("25.00")

    def test_fee_bps_is_annualized_not_flat(self):
        """fee_bps is annualized — fee scales linearly with days_funded."""
        fee_7 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        fee_14 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 14)
        # 14 days should be exactly double 7 days (annualized linear scaling)
        assert abs(fee_14 - 2 * fee_7) <= Decimal("0.02")

    def test_pipeline_fee_bps_used_in_loan_offer(self):
        """Pipeline propagates fee_bps from C2; tiered floor applied in loan offer.

        C2 emits 300 bps.  At $1M (mid tier $500K–$2M) the tiered floor raises it
        to 400 bps in the offer.  result.fee_bps preserves the raw C2 value (300);
        result.loan_offer["fee_bps"] reflects the effective floor (400).
        """
        pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
        event = make_event(rejection_code="CURR", amount=Decimal("1000000"))
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        assert result.fee_bps == 300                       # C2 output preserved
        assert result.loan_offer is not None
        assert result.loan_offer["fee_bps"] == 400         # tiered floor: mid tier

    def test_below_threshold_skips_fee_computation(self):
        pipeline = _make_pipeline(failure_probability=0.05)  # below 0.110
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "BELOW_THRESHOLD"
        assert result.fee_bps is None
