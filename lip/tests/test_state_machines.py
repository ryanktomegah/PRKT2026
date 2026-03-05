"""
test_state_machines.py — State machine tests for LIP (Architecture Spec S6, S7)

Covers:
- All valid payment transitions
- All forbidden payment transitions raise InvalidTransitionError
- Terminal payment state immutability
- All valid loan transitions
- All forbidden loan transitions raise InvalidTransitionError
- Terminal loan state immutability
- maturity_days() T = f(rejection_code_class)
"""
import pytest

from lip.common.state_machines import (
    PaymentState,
    PaymentStateMachine,
    LoanState,
    LoanStateMachine,
    InvalidTransitionError,
    maturity_days,
)


# ── maturity_days ────────────────────────────────────────────────────────────

class TestMaturityDays:
    def test_class_a_is_3_days(self):
        assert maturity_days("A") == 3

    def test_class_b_is_7_days(self):
        assert maturity_days("B") == 7

    def test_class_c_is_21_days(self):
        assert maturity_days("C") == 21

    def test_unknown_class_raises(self):
        with pytest.raises(ValueError, match="Unknown rejection_code_class"):
            maturity_days("D")

    def test_lowercase_raises(self):
        with pytest.raises(ValueError):
            maturity_days("a")


# ── PaymentStateMachine — valid transitions ──────────────────────────────────

class TestPaymentStateMachineValidTransitions:
    def test_initial_state_is_monitoring(self):
        sm = PaymentStateMachine()
        assert sm.current_state == PaymentState.MONITORING

    def test_monitoring_to_failure_detected(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        assert sm.current_state == PaymentState.FAILURE_DETECTED

    def test_monitoring_to_dispute_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.DISPUTE_BLOCKED)
        assert sm.current_state == PaymentState.DISPUTE_BLOCKED

    def test_monitoring_to_aml_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.AML_BLOCKED)
        assert sm.current_state == PaymentState.AML_BLOCKED

    def test_failure_detected_to_bridge_offered(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        assert sm.current_state == PaymentState.BRIDGE_OFFERED

    def test_failure_detected_to_dispute_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.DISPUTE_BLOCKED)
        assert sm.current_state == PaymentState.DISPUTE_BLOCKED

    def test_failure_detected_to_aml_blocked(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.AML_BLOCKED)
        assert sm.current_state == PaymentState.AML_BLOCKED

    def test_bridge_offered_to_funded(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        sm.transition(PaymentState.FUNDED)
        assert sm.current_state == PaymentState.FUNDED

    def test_bridge_offered_to_offer_declined(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        sm.transition(PaymentState.OFFER_DECLINED)
        assert sm.current_state == PaymentState.OFFER_DECLINED

    def test_bridge_offered_to_offer_expired(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        sm.transition(PaymentState.OFFER_EXPIRED)
        assert sm.current_state == PaymentState.OFFER_EXPIRED

    def test_funded_to_repaid(self):
        sm = PaymentStateMachine()
        for s in [PaymentState.FAILURE_DETECTED, PaymentState.BRIDGE_OFFERED, PaymentState.FUNDED]:
            sm.transition(s)
        sm.transition(PaymentState.REPAID)
        assert sm.current_state == PaymentState.REPAID

    def test_funded_to_buffer_repaid(self):
        sm = PaymentStateMachine()
        for s in [PaymentState.FAILURE_DETECTED, PaymentState.BRIDGE_OFFERED, PaymentState.FUNDED]:
            sm.transition(s)
        sm.transition(PaymentState.BUFFER_REPAID)
        assert sm.current_state == PaymentState.BUFFER_REPAID

    def test_funded_to_defaulted(self):
        sm = PaymentStateMachine()
        for s in [PaymentState.FAILURE_DETECTED, PaymentState.BRIDGE_OFFERED, PaymentState.FUNDED]:
            sm.transition(s)
        sm.transition(PaymentState.DEFAULTED)
        assert sm.current_state == PaymentState.DEFAULTED

    def test_funded_to_repayment_pending_to_repaid(self):
        sm = PaymentStateMachine()
        for s in [PaymentState.FAILURE_DETECTED, PaymentState.BRIDGE_OFFERED,
                  PaymentState.FUNDED, PaymentState.REPAYMENT_PENDING]:
            sm.transition(s)
        sm.transition(PaymentState.REPAID)
        assert sm.current_state == PaymentState.REPAID


# ── PaymentStateMachine — forbidden transitions ──────────────────────────────

class TestPaymentStateMachineForbiddenTransitions:
    def test_monitoring_cannot_go_to_funded(self):
        sm = PaymentStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.FUNDED)

    def test_monitoring_cannot_go_to_bridge_offered(self):
        sm = PaymentStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.BRIDGE_OFFERED)

    def test_failure_detected_cannot_go_to_repaid(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.REPAID)

    def test_bridge_offered_cannot_go_to_failure_detected(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.FAILURE_DETECTED)

    def test_error_contains_state_names(self):
        sm = PaymentStateMachine()
        try:
            sm.transition(PaymentState.FUNDED)
        except InvalidTransitionError as e:
            assert "MONITORING" in str(e)
            assert "FUNDED" in str(e)


# ── PaymentStateMachine — terminal state immutability ────────────────────────

class TestPaymentTerminalStateImmutability:
    @pytest.mark.parametrize("terminal", [
        PaymentState.REPAID,
        PaymentState.BUFFER_REPAID,
        PaymentState.DEFAULTED,
        PaymentState.OFFER_DECLINED,
        PaymentState.OFFER_EXPIRED,
        PaymentState.DISPUTE_BLOCKED,
        PaymentState.AML_BLOCKED,
    ])
    def test_terminal_state_is_terminal(self, terminal):
        sm = PaymentStateMachine(initial_state=terminal)
        assert sm.is_terminal is True

    @pytest.mark.parametrize("terminal", [
        PaymentState.REPAID,
        PaymentState.BUFFER_REPAID,
        PaymentState.DEFAULTED,
        PaymentState.OFFER_DECLINED,
        PaymentState.OFFER_EXPIRED,
        PaymentState.DISPUTE_BLOCKED,
        PaymentState.AML_BLOCKED,
    ])
    def test_terminal_state_cannot_transition(self, terminal):
        sm = PaymentStateMachine(initial_state=terminal)
        for target in PaymentState:
            with pytest.raises(InvalidTransitionError):
                sm.transition(target)

    def test_non_terminal_not_flagged(self):
        sm = PaymentStateMachine()
        assert sm.is_terminal is False


# ── LoanStateMachine — valid transitions ────────────────────────────────────

class TestLoanStateMachineValidTransitions:
    def test_initial_state_is_offer_pending(self):
        sm = LoanStateMachine()
        assert sm.current_state == LoanState.OFFER_PENDING

    def test_offer_pending_to_active(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        assert sm.current_state == LoanState.ACTIVE

    def test_offer_pending_to_offer_expired(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.OFFER_EXPIRED)
        assert sm.current_state == LoanState.OFFER_EXPIRED

    def test_offer_pending_to_offer_declined(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.OFFER_DECLINED)
        assert sm.current_state == LoanState.OFFER_DECLINED

    def test_active_to_repayment_pending(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.REPAYMENT_PENDING)
        assert sm.current_state == LoanState.REPAYMENT_PENDING

    def test_active_to_under_review(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.UNDER_REVIEW)
        assert sm.current_state == LoanState.UNDER_REVIEW

    def test_active_to_defaulted(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.DEFAULTED)
        assert sm.current_state == LoanState.DEFAULTED

    def test_under_review_back_to_active(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.UNDER_REVIEW)
        sm.transition(LoanState.ACTIVE)
        assert sm.current_state == LoanState.ACTIVE

    def test_repayment_pending_to_repaid(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.REPAYMENT_PENDING)
        sm.transition(LoanState.REPAID)
        assert sm.current_state == LoanState.REPAID

    def test_repayment_pending_to_buffer_repaid(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.REPAYMENT_PENDING)
        sm.transition(LoanState.BUFFER_REPAID)
        assert sm.current_state == LoanState.BUFFER_REPAID


# ── LoanStateMachine — forbidden transitions ─────────────────────────────────

class TestLoanStateMachineForbiddenTransitions:
    def test_offer_pending_cannot_go_to_repaid(self):
        sm = LoanStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.REPAID)

    def test_active_cannot_skip_to_repaid_directly(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.REPAID)

    def test_repayment_pending_cannot_go_to_under_review(self):
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        sm.transition(LoanState.REPAYMENT_PENDING)
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.UNDER_REVIEW)


# ── LoanStateMachine — terminal state immutability ───────────────────────────

class TestLoanTerminalStateImmutability:
    @pytest.mark.parametrize("terminal", [
        LoanState.REPAID,
        LoanState.BUFFER_REPAID,
        LoanState.DEFAULTED,
        LoanState.OFFER_EXPIRED,
        LoanState.OFFER_DECLINED,
    ])
    def test_terminal_is_flagged(self, terminal):
        sm = LoanStateMachine(initial_state=terminal)
        assert sm.is_terminal is True

    @pytest.mark.parametrize("terminal", [
        LoanState.REPAID,
        LoanState.BUFFER_REPAID,
        LoanState.DEFAULTED,
        LoanState.OFFER_EXPIRED,
        LoanState.OFFER_DECLINED,
    ])
    def test_terminal_cannot_transition(self, terminal):
        sm = LoanStateMachine(initial_state=terminal)
        for target in LoanState:
            with pytest.raises(InvalidTransitionError):
                sm.transition(target)
