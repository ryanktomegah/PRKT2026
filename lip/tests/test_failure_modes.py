"""
test_failure_modes.py — Chaos / failure-mode tests.

Tests system behaviour under component failure scenarios:
  1. GPU failure → CPU fallback, system continues
  2. KMS failure → new offers halted, degraded flag set
  3. Network failure → degraded mode, fallback decision
  4. Kill switch concurrent activation → state consistent
  5. C4 timeout fallback → DISPUTE_POSSIBLE (conservative)
  6. C3 corridor buffer cold start → Tier 0 conservative defaults
  7. C6 velocity cap edge → exact threshold enforcement
  8. Settlement monitor idempotency → double-deregister safe
  9. Decision log tamper detection → integrity preserved
 10. Kill switch + degraded cascade → both flags independent
 11. State machine terminal state immutability
"""

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer, CorridorBufferDefaults
from lip.c3_repayment_engine.repayment_loop import ActiveLoan, SettlementMonitor
from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable
from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c4_dispute_classifier.taxonomy import DisputeClass, is_blocking, timeout_fallback
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.decision_log import DecisionLogEntryData, DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager, DegradedReason
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.state_machines import (
    InvalidTransitionError,
    LoanState,
    LoanStateMachine,
    PaymentState,
    PaymentStateMachine,
)

# EPG-16: module-level caps are now 0 (unlimited). Tests must use explicit values.
_TEST_DOLLAR_CAP_USD = Decimal("1000000")
_SALT = b"chaos_test_salt_32bytes_________"
_HMAC_KEY = b"chaos_test_hmac_32bytes_________"


def _make_monitor() -> SettlementMonitor:
    registry = SettlementHandlerRegistry()
    uetr_map = UETRMappingTable()
    corridor_buf = CorridorBuffer()
    return SettlementMonitor(registry, uetr_map, corridor_buf)


def _make_active_loan(uetr: str = "chaos-uetr-001") -> ActiveLoan:
    return ActiveLoan(
        loan_id=f"loan-{uetr}",
        uetr=uetr,
        individual_payment_id="pid-chaos-001",
        principal=Decimal("100000"),
        fee_bps=300,
        maturity_date=datetime.now(timezone.utc) + timedelta(days=7),
        rejection_class="CLASS_B",
        corridor="USD_EUR",
        funded_at=datetime.now(timezone.utc),
    )


def _make_log_entry(
    entry_id: str = "",
    uetr: str = "uetr-chaos-001",
    individual_payment_id: str = "pid-chaos-001",
    decision_type: str = "OFFER",
    decision_timestamp: str = "",
    failure_probability: float = 0.75,
    pd_score: float = 0.04,
    fee_bps: int = 300,
    loan_amount: str = "50000",
    dispute_class: str = "NOT_DISPUTE",
    aml_passed: bool = True,
) -> DecisionLogEntryData:
    return DecisionLogEntryData(
        entry_id=entry_id,
        uetr=uetr,
        individual_payment_id=individual_payment_id,
        decision_type=decision_type,
        decision_timestamp=decision_timestamp or datetime.now(tz=timezone.utc).isoformat(),
        failure_probability=failure_probability,
        pd_score=pd_score,
        fee_bps=fee_bps,
        loan_amount=loan_amount,
        dispute_class=dispute_class,
        aml_passed=aml_passed,
    )


# ---------------------------------------------------------------------------
# 1. GPU failure — CPU fallback
# ---------------------------------------------------------------------------

class TestGPUFailureFallback:
    def test_enter_gpu_failure_enables_cpu_fallback(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        assert dm.is_degraded()
        assert dm.should_use_cpu()

    def test_gpu_degraded_does_not_halt_new_offers(self):
        """GPU fallback to CPU does NOT halt new offers — only KMS does."""
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        assert dm.should_halt_new_offers() is False

    def test_exit_degraded_restores_normal(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        dm.exit_degraded_mode()
        assert dm.is_degraded() is False
        assert dm.should_use_cpu() is False


# ---------------------------------------------------------------------------
# 2. KMS failure — new offers halted
# ---------------------------------------------------------------------------

class TestKMSFailure:
    def test_kms_failure_halts_new_offers(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        assert dm.should_halt_new_offers() is True

    def test_kms_failure_does_not_enable_cpu_fallback(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        assert dm.should_use_cpu() is False

    def test_kms_gap_seconds_non_negative(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        gap = dm.get_kms_gap_seconds()
        assert gap is not None
        assert gap >= 0.0

    def test_kms_recovery_clears_halt(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        dm.exit_degraded_mode()
        assert dm.should_halt_new_offers() is False
        assert dm.get_kms_gap_seconds() is None


# ---------------------------------------------------------------------------
# 3. Network failure → degraded mode
# ---------------------------------------------------------------------------

class TestNetworkFailure:
    def test_network_failure_enters_degraded(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.NETWORK_FAILURE)
        assert dm.is_degraded()

    def test_network_failure_does_not_halt_offers(self):
        """Network failure is recoverable — does not block offers like KMS."""
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.NETWORK_FAILURE)
        assert dm.should_halt_new_offers() is False

    def test_state_dict_reflects_degraded(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.NETWORK_FAILURE)
        state = dm.get_state_dict()
        assert state["degraded_mode"] is True


# ---------------------------------------------------------------------------
# 4. Kill switch concurrent activation
# ---------------------------------------------------------------------------

class TestKillSwitchConcurrency:
    def test_multiple_activations_remain_active(self):
        """Kill switch stays active regardless of how many times activated."""
        ks = KillSwitch()
        for i in range(10):
            ks.activate(f"reason_{i}")
        assert ks.is_active() is True

    def test_concurrent_activate_deactivate_no_crash(self):
        """Thread-safety: no exceptions from concurrent activate/deactivate."""
        ks = KillSwitch()
        errors = []

        def toggle():
            try:
                ks.activate("thread test")
                ks.deactivate()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=toggle) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

    def test_deactivate_without_prior_activate_is_safe(self):
        ks = KillSwitch()
        ks.deactivate()  # Must not raise
        assert ks.is_active() is False


# ---------------------------------------------------------------------------
# 5. C4 timeout fallback → DISPUTE_POSSIBLE
# ---------------------------------------------------------------------------

class TestC4TimeoutFallback:
    def test_timeout_fallback_returns_dispute_possible(self):
        """On timeout, taxonomy.timeout_fallback() returns DISPUTE_POSSIBLE (spec §9.3)."""
        assert timeout_fallback() == DisputeClass.DISPUTE_POSSIBLE

    def test_dispute_possible_is_blocking(self):
        assert is_blocking(DisputeClass.DISPUTE_POSSIBLE) is True

    def test_dispute_confirmed_is_blocking(self):
        assert is_blocking(DisputeClass.DISPUTE_CONFIRMED) is True

    def test_not_dispute_is_not_blocking(self):
        assert is_blocking(DisputeClass.NOT_DISPUTE) is False

    def test_negotiation_is_not_blocking(self):
        assert is_blocking(DisputeClass.NEGOTIATION) is False

    def test_mock_backend_simulate_timeout_returns_possible(self):
        """MockLLMBackend with simulate_timeout=True → DISPUTE_POSSIBLE."""
        backend = MockLLMBackend(simulate_timeout=True)
        classifier = DisputeClassifier(llm_backend=backend)
        result = classifier.classify(rejection_code=None, narrative="normal payment")
        assert result["dispute_class"] == DisputeClass.DISPUTE_POSSIBLE


# ---------------------------------------------------------------------------
# 6. C3 corridor buffer cold start (Tier 0)
# ---------------------------------------------------------------------------

class TestCorridorBufferColdStart:
    def test_cold_start_returns_tier0(self):
        """With no observations, Tier 0 defaults apply."""
        buf = CorridorBuffer()
        tier = buf.get_buffer_tier("USD_EUR")
        assert tier == 0

    def test_cold_start_p95_matches_corridor_default(self):
        buf = CorridorBuffer()
        p95 = buf.estimate_p95("USD_EUR")
        assert p95 == CorridorBufferDefaults().get("USD_EUR")

    def test_cold_start_unknown_corridor_uses_default_fallback(self):
        buf = CorridorBuffer()
        p95 = buf.estimate_p95("XYZ_ABC")
        assert p95 == CorridorBufferDefaults().get("DEFAULT")

    def test_single_observation_is_tier1(self):
        buf = CorridorBuffer()
        buf.add_observation("USD_EUR", 2.5)
        assert buf.get_buffer_tier("USD_EUR") == 1

    def test_30_observations_is_tier2(self):
        buf = CorridorBuffer()
        for _ in range(30):
            buf.add_observation("USD_EUR", 2.5)
        assert buf.get_buffer_tier("USD_EUR") == 2

    def test_101_observations_is_tier3(self):
        buf = CorridorBuffer()
        for i in range(101):
            buf.add_observation("USD_EUR", float(i % 5 + 1))
        assert buf.get_buffer_tier("USD_EUR") == 3


# ---------------------------------------------------------------------------
# 7. C6 velocity cap — exact threshold enforcement
# ---------------------------------------------------------------------------

class TestVelocityCapEdge:
    def test_small_amount_passes(self):
        checker = VelocityChecker(salt=_SALT)
        result = checker.check("entity_small", Decimal("1000.00"), "beneficiary_A")
        assert result.passed is True

    def test_single_transaction_over_cap_fails(self):
        """A single transaction exceeding the cap must fail."""
        checker = VelocityChecker(salt=_SALT)
        over_cap = _TEST_DOLLAR_CAP_USD + Decimal("0.01")
        result = checker.check("entity_over", over_cap, "beneficiary_B",
                               dollar_cap_override=_TEST_DOLLAR_CAP_USD)
        assert result.passed is False

    def test_single_transaction_at_cap_passes(self):
        """Exactly at the cap is not exceeded."""
        checker = VelocityChecker(salt=_SALT)
        at_cap = _TEST_DOLLAR_CAP_USD
        result = checker.check("entity_at_cap", at_cap, "beneficiary_C",
                               dollar_cap_override=_TEST_DOLLAR_CAP_USD)
        assert result.passed is True


# ---------------------------------------------------------------------------
# 8. Settlement monitor idempotency
# ---------------------------------------------------------------------------

class TestSettlementMonitorIdempotency:
    def test_register_and_deregister_returns_loan(self):
        monitor = _make_monitor()
        loan = _make_active_loan("idempotency-uetr-001")
        monitor.register_loan(loan)
        retrieved = monitor.deregister_loan("idempotency-uetr-001")
        assert retrieved is not None
        assert retrieved.uetr == "idempotency-uetr-001"

    def test_double_deregister_returns_none_on_second(self):
        """Deregistering a loan twice must not crash."""
        monitor = _make_monitor()
        loan = _make_active_loan("idempotency-uetr-002")
        monitor.register_loan(loan)
        monitor.deregister_loan("idempotency-uetr-002")
        second = monitor.deregister_loan("idempotency-uetr-002")
        assert second is None

    def test_deregister_unknown_uetr_returns_none(self):
        monitor = _make_monitor()
        result = monitor.deregister_loan("nonexistent-uetr-xyz")
        assert result is None

    def test_match_loan_after_registration(self):
        monitor = _make_monitor()
        loan = _make_active_loan("match-uetr-001")
        monitor.register_loan(loan)
        matched = monitor.match_loan("match-uetr-001")
        assert matched is not None
        assert matched.uetr == "match-uetr-001"

    def test_match_loan_after_deregistration_returns_none(self):
        monitor = _make_monitor()
        loan = _make_active_loan("match-uetr-002")
        monitor.register_loan(loan)
        monitor.deregister_loan("match-uetr-002")
        assert monitor.match_loan("match-uetr-002") is None


# ---------------------------------------------------------------------------
# 9. Decision log tamper detection
# ---------------------------------------------------------------------------

class TestDecisionLogIntegrity:
    def test_valid_entry_verifies(self):
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_log_entry()
        eid = dl.log(entry)
        assert dl.verify(eid) is True

    def test_tampered_pd_score_fails_verification(self):
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_log_entry(uetr="uetr-tamper-001", individual_payment_id="pid-t-001")
        eid = dl.log(entry)
        stored = dl.get(eid)
        stored.pd_score = 0.99  # Tamper
        assert dl.verify(eid) is False

    def test_tampered_fee_bps_fails_verification(self):
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_log_entry(uetr="uetr-tamper-002", individual_payment_id="pid-t-002")
        eid = dl.log(entry)
        stored = dl.get(eid)
        stored.fee_bps = 0  # Attempt to zero out the fee
        assert dl.verify(eid) is False

    def test_get_by_uetr_after_log(self):
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        entry = _make_log_entry(uetr="uetr-lookup-001", individual_payment_id="pid-l-001")
        dl.log(entry)
        results = dl.get_by_uetr("uetr-lookup-001")
        assert len(results) == 1

    def test_get_by_uetr_returns_empty_for_unknown(self):
        dl = DecisionLogger(hmac_key=_HMAC_KEY)
        assert dl.get_by_uetr("uetr-unknown-xyz") == []


# ---------------------------------------------------------------------------
# 10. Kill switch + degraded cascade — independence
# ---------------------------------------------------------------------------

class TestKillSwitchAndDegradedIndependence:
    def test_both_flags_can_be_set_simultaneously(self):
        ks = KillSwitch()
        dm = DegradedModeManager()
        ks.activate("regulatory hold")
        dm.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        assert ks.is_active() is True
        assert dm.is_degraded() is True
        assert dm.should_use_cpu() is True

    def test_clearing_kill_switch_does_not_clear_degraded(self):
        ks = KillSwitch()
        dm = DegradedModeManager()
        ks.activate()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        ks.deactivate()
        assert ks.is_active() is False
        assert dm.is_degraded() is True

    def test_clearing_degraded_does_not_clear_kill_switch(self):
        ks = KillSwitch()
        dm = DegradedModeManager()
        ks.activate()
        dm.enter_degraded_mode(DegradedReason.GPU_FAILURE, gpu_fallback=True)
        dm.exit_degraded_mode()
        assert ks.is_active() is True
        assert dm.is_degraded() is False


# ---------------------------------------------------------------------------
# 11. State machine terminal state immutability
# ---------------------------------------------------------------------------

class TestStateMachineTerminalImmutability:
    def test_dispute_blocked_is_terminal(self):
        psm = PaymentStateMachine()
        psm.transition(PaymentState.FAILURE_DETECTED)
        psm.transition(PaymentState.DISPUTE_BLOCKED)
        with pytest.raises(InvalidTransitionError):
            psm.transition(PaymentState.BRIDGE_OFFERED)

    def test_aml_blocked_is_terminal(self):
        psm = PaymentStateMachine()
        psm.transition(PaymentState.FAILURE_DETECTED)
        psm.transition(PaymentState.AML_BLOCKED)
        with pytest.raises(InvalidTransitionError):
            psm.transition(PaymentState.BRIDGE_OFFERED)

    def test_loan_defaulted_is_terminal(self):
        # OFFER_PENDING → ACTIVE → DEFAULTED
        lsm = LoanStateMachine()
        lsm.transition(LoanState.ACTIVE)
        lsm.transition(LoanState.DEFAULTED)
        with pytest.raises(InvalidTransitionError):
            lsm.transition(LoanState.REPAID)

    def test_loan_repaid_is_terminal(self):
        # OFFER_PENDING → ACTIVE → REPAYMENT_PENDING → REPAID
        lsm = LoanStateMachine()
        lsm.transition(LoanState.ACTIVE)
        lsm.transition(LoanState.REPAYMENT_PENDING)
        lsm.transition(LoanState.REPAID)
        with pytest.raises(InvalidTransitionError):
            lsm.transition(LoanState.DEFAULTED)

    def test_payment_repaid_is_terminal(self):
        psm = PaymentStateMachine()
        psm.transition(PaymentState.FAILURE_DETECTED)
        psm.transition(PaymentState.BRIDGE_OFFERED)
        psm.transition(PaymentState.FUNDED)
        psm.transition(PaymentState.REPAID)
        with pytest.raises(InvalidTransitionError):
            psm.transition(PaymentState.FUNDED)
