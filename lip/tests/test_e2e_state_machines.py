"""
test_e2e_state_machines.py — State machine exhaustive E2E tests.

Verifies in E2E context:
  - Terminal states (REPAID, DEFAULTED) are truly immutable.
  - Forbidden transitions raise InvalidTransitionError.
  - DISPUTE_BLOCKED / AML_BLOCKED → BRIDGE_OFFERED is forbidden.
  - State machine audit trail (via payment_state_history) is complete.
  - Full lifecycle transitions are correctly sequenced.
"""

from __future__ import annotations

import pytest

from lip.common.state_machines import (
    PaymentStateMachine,
    PaymentState,
    LoanStateMachine,
    LoanState,
    InvalidTransitionError,
)
from lip.pipeline import LIPPipeline, FAILURE_PROBABILITY_THRESHOLD
from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch

from .conftest import make_event, MockC1Engine, MockC2Engine, _HMAC_KEY, _SALT


def _build_pipeline(failure_probability=0.80):
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    agent = ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=MockC1Engine(failure_probability),
        c2_engine=MockC2Engine(),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
    )


# ===========================================================================
# Payment state machine — terminal state immutability
# ===========================================================================

class TestPaymentTerminalStateImmutability:

    @pytest.mark.parametrize("terminal_state", [
        PaymentState.REPAID,
        PaymentState.BUFFER_REPAID,
        PaymentState.DEFAULTED,
        PaymentState.OFFER_DECLINED,
        PaymentState.OFFER_EXPIRED,
        PaymentState.DISPUTE_BLOCKED,
        PaymentState.AML_BLOCKED,
    ])
    def test_terminal_state_raises_on_transition(self, terminal_state):
        """Any transition from a terminal payment state must raise InvalidTransitionError."""
        sm = PaymentStateMachine(initial_state=terminal_state)
        assert sm.is_terminal is True
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.MONITORING)

    def test_repaid_is_immutable_from_pipeline(self):
        """After REPAID, no further transitions are possible."""
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        sm.transition(PaymentState.BRIDGE_OFFERED)
        sm.transition(PaymentState.FUNDED)
        sm.transition(PaymentState.REPAID)
        assert sm.is_terminal is True
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.DEFAULTED)


# ===========================================================================
# Loan state machine — terminal state immutability
# ===========================================================================

class TestLoanTerminalStateImmutability:

    @pytest.mark.parametrize("terminal_state", [
        LoanState.REPAID,
        LoanState.BUFFER_REPAID,
        LoanState.DEFAULTED,
        LoanState.OFFER_EXPIRED,
        LoanState.OFFER_DECLINED,
    ])
    def test_terminal_loan_state_raises_on_transition(self, terminal_state):
        """Any transition from a terminal loan state must raise InvalidTransitionError."""
        sm = LoanStateMachine(initial_state=terminal_state)
        assert sm.is_terminal is True
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.OFFER_PENDING)


# ===========================================================================
# Forbidden transitions
# ===========================================================================

class TestForbiddenTransitions:

    def test_dispute_blocked_to_bridge_offered_is_forbidden(self):
        sm = PaymentStateMachine(initial_state=PaymentState.DISPUTE_BLOCKED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.BRIDGE_OFFERED)

    def test_aml_blocked_to_bridge_offered_is_forbidden(self):
        sm = PaymentStateMachine(initial_state=PaymentState.AML_BLOCKED)
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.BRIDGE_OFFERED)

    def test_monitoring_to_funded_is_forbidden(self):
        sm = PaymentStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(PaymentState.FUNDED)

    def test_offer_pending_to_repaid_is_forbidden(self):
        sm = LoanStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.REPAID)

    def test_active_to_repaid_is_forbidden(self):
        """ACTIVE → REPAID is not permitted; must go through REPAYMENT_PENDING."""
        sm = LoanStateMachine()
        sm.transition(LoanState.ACTIVE)
        with pytest.raises(InvalidTransitionError):
            sm.transition(LoanState.REPAID)


# ===========================================================================
# Full pipeline state transition sequences
# ===========================================================================

class TestPipelineStateTransitions:

    def test_happy_path_full_sequence(self):
        pipeline = _build_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        history = result.payment_state_history
        # History must contain all expected states in order
        assert history[0] == PaymentState.MONITORING.value
        assert PaymentState.FAILURE_DETECTED.value in history
        assert PaymentState.BRIDGE_OFFERED.value in history
        assert history[-1] == PaymentState.FUNDED.value

    def test_dispute_path_sequence(self):
        pipeline = _build_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="This invoice is disputed")
        result = pipeline.process(event)
        history = result.payment_state_history
        assert history[0] == PaymentState.MONITORING.value
        assert history[-1] == PaymentState.DISPUTE_BLOCKED.value

    def test_below_threshold_no_transition(self):
        pipeline = _build_pipeline(failure_probability=0.05)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        history = result.payment_state_history
        # Should stay at MONITORING
        assert history[-1] == PaymentState.MONITORING.value

    def test_loan_sm_offer_pending_to_active(self):
        pipeline = _build_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        assert result.loan_state == LoanState.ACTIVE.value

    def test_loan_sm_stays_offer_pending_on_block(self):
        pipeline = _build_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="DISP", narrative="disputed")
        result = pipeline.process(event)
        assert result.loan_state == LoanState.OFFER_PENDING.value


# ===========================================================================
# Allowed transitions inventory
# ===========================================================================

class TestAllowedTransitions:

    def test_monitoring_allowed_transitions(self):
        sm = PaymentStateMachine()
        allowed = sm.allowed_transitions()
        assert PaymentState.FAILURE_DETECTED in allowed
        assert PaymentState.DISPUTE_BLOCKED in allowed
        assert PaymentState.AML_BLOCKED in allowed

    def test_failure_detected_allowed_transitions(self):
        sm = PaymentStateMachine()
        sm.transition(PaymentState.FAILURE_DETECTED)
        allowed = sm.allowed_transitions()
        assert PaymentState.BRIDGE_OFFERED in allowed
        assert PaymentState.DISPUTE_BLOCKED in allowed
        assert PaymentState.AML_BLOCKED in allowed

    def test_terminal_states_have_no_allowed_transitions(self):
        for terminal in [
            PaymentState.REPAID, PaymentState.DEFAULTED,
            PaymentState.DISPUTE_BLOCKED, PaymentState.AML_BLOCKED,
        ]:
            sm = PaymentStateMachine(initial_state=terminal)
            assert len(sm.allowed_transitions()) == 0
