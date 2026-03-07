"""
state_machines.py — LIP Payment and Loan State Machines
Architecture Spec v1.2 Sections S6 and S7

Payment lifecycle:  MONITORING → … → terminal
Loan lifecycle:     OFFER_PENDING → … → terminal

Maturity window T = f(rejection_code_class):
    Class A → 3 days   (MATURITY_CLASS_A_DAYS)
    Class B → 7 days   (MATURITY_CLASS_B_DAYS)
    Class C → 21 days  (MATURITY_CLASS_C_DAYS)
"""
from __future__ import annotations

import enum
from typing import Final

from lip.common.constants import (
    MATURITY_CLASS_A_DAYS,
    MATURITY_CLASS_B_DAYS,
    MATURITY_CLASS_C_DAYS,
)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class InvalidTransitionError(Exception):
    """Raised when a forbidden state-machine transition is attempted.

    Attributes
    ----------
    current_state:
        The state from which the transition was attempted.
    requested_state:
        The target state that was requested.
    """

    def __init__(self, current_state: str, requested_state: str) -> None:
        self.current_state = current_state
        self.requested_state = requested_state
        super().__init__(
            f"Invalid transition: {current_state!r} → {requested_state!r} is not permitted."
        )


# ---------------------------------------------------------------------------
# Maturity window helper  (T = f(rejection_code_class))
# ---------------------------------------------------------------------------

#: Explicit mapping of rejection-code class → maturity window in days.
MATURITY_DAYS: Final[dict[str, int]] = {
    "A": MATURITY_CLASS_A_DAYS,   # 3 days
    "B": MATURITY_CLASS_B_DAYS,   # 7 days
    "C": MATURITY_CLASS_C_DAYS,   # 21 days
}


def maturity_days(rejection_code_class: str) -> int:
    """Return the maturity window in days for the given rejection-code class.

    Parameters
    ----------
    rejection_code_class:
        One of ``'A'``, ``'B'``, or ``'C'``.

    Returns
    -------
    int
        Maturity window in calendar days.

    Raises
    ------
    ValueError
        If *rejection_code_class* is not a recognised class.
    """
    try:
        return MATURITY_DAYS[rejection_code_class]
    except KeyError:
        valid = ", ".join(sorted(MATURITY_DAYS))
        raise ValueError(
            f"Unknown rejection_code_class {rejection_code_class!r}. "
            f"Must be one of: {valid}."
        ) from None


# ---------------------------------------------------------------------------
# Payment state machine  (Architecture Spec S6)
# ---------------------------------------------------------------------------

class PaymentState(str, enum.Enum):
    """All valid states for a cross-border payment in the LIP system (S6)."""

    MONITORING         = "MONITORING"
    FAILURE_DETECTED   = "FAILURE_DETECTED"
    BRIDGE_OFFERED     = "BRIDGE_OFFERED"
    FUNDED             = "FUNDED"
    REPAYMENT_PENDING  = "REPAYMENT_PENDING"
    # ── Terminal states ──────────────────────────────────────────────────────
    REPAID             = "REPAID"
    BUFFER_REPAID      = "BUFFER_REPAID"
    DEFAULTED          = "DEFAULTED"
    OFFER_DECLINED     = "OFFER_DECLINED"
    OFFER_EXPIRED      = "OFFER_EXPIRED"
    DISPUTE_BLOCKED    = "DISPUTE_BLOCKED"
    AML_BLOCKED        = "AML_BLOCKED"


#: Allowed outgoing transitions for each payment state.
#: Terminal states map to an empty frozenset — no transitions permitted.
_PAYMENT_TRANSITIONS: Final[dict[PaymentState, frozenset[PaymentState]]] = {
    PaymentState.MONITORING: frozenset({
        PaymentState.FAILURE_DETECTED,
        PaymentState.DISPUTE_BLOCKED,
        PaymentState.AML_BLOCKED,
    }),
    PaymentState.FAILURE_DETECTED: frozenset({
        PaymentState.BRIDGE_OFFERED,
        PaymentState.DISPUTE_BLOCKED,
        PaymentState.AML_BLOCKED,
    }),
    PaymentState.BRIDGE_OFFERED: frozenset({
        PaymentState.FUNDED,
        PaymentState.OFFER_DECLINED,
        PaymentState.OFFER_EXPIRED,
    }),
    PaymentState.FUNDED: frozenset({
        PaymentState.REPAID,
        PaymentState.BUFFER_REPAID,
        PaymentState.DEFAULTED,
        PaymentState.REPAYMENT_PENDING,
    }),
    PaymentState.REPAYMENT_PENDING: frozenset({
        PaymentState.REPAID,
        PaymentState.BUFFER_REPAID,
        PaymentState.DEFAULTED,
    }),
    # Terminal states — no outgoing transitions
    PaymentState.REPAID:          frozenset(),
    PaymentState.BUFFER_REPAID:   frozenset(),
    PaymentState.DEFAULTED:       frozenset(),
    PaymentState.OFFER_DECLINED:  frozenset(),
    PaymentState.OFFER_EXPIRED:   frozenset(),
    PaymentState.DISPUTE_BLOCKED: frozenset(),
    PaymentState.AML_BLOCKED:     frozenset(),
}

#: Set of terminal payment states for fast membership testing.
_PAYMENT_TERMINAL_STATES: Final[frozenset[PaymentState]] = frozenset(
    state for state, targets in _PAYMENT_TRANSITIONS.items() if not targets
)


class PaymentStateMachine:
    """Enforces the LIP payment lifecycle state machine (Architecture Spec S6).

    Parameters
    ----------
    initial_state:
        Starting state; defaults to ``MONITORING``.

    Raises
    ------
    InvalidTransitionError
        On any call to :meth:`transition` that requests a forbidden move.
    """

    def __init__(
        self,
        initial_state: PaymentState = PaymentState.MONITORING,
    ) -> None:
        self._state: PaymentState = initial_state

    # ── Public interface ─────────────────────────────────────────────────────

    @property
    def current_state(self) -> PaymentState:
        """The current payment state."""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """True when the machine has reached a terminal state."""
        return self._state in _PAYMENT_TERMINAL_STATES

    def transition(self, new_state: PaymentState) -> None:
        """Advance the machine to *new_state*.

        Parameters
        ----------
        new_state:
            The target state to transition into.

        Raises
        ------
        InvalidTransitionError
            If the transition from the current state to *new_state* is not
            permitted by the Architecture Spec S6 transition table.
        """
        allowed = _PAYMENT_TRANSITIONS[self._state]
        if new_state not in allowed:
            raise InvalidTransitionError(self._state.value, new_state.value)
        self._state = new_state

    def allowed_transitions(self) -> frozenset[PaymentState]:
        """Return the set of states reachable from the current state."""
        return _PAYMENT_TRANSITIONS[self._state]

    def __repr__(self) -> str:
        return (
            f"PaymentStateMachine(current_state={self._state.value!r}, "
            f"is_terminal={self.is_terminal})"
        )


# ---------------------------------------------------------------------------
# Loan state machine  (Architecture Spec S7)
# ---------------------------------------------------------------------------

class LoanState(str, enum.Enum):
    """All valid states for a bridge loan in the LIP system (S7)."""

    OFFER_PENDING      = "OFFER_PENDING"
    ACTIVE             = "ACTIVE"
    REPAYMENT_PENDING  = "REPAYMENT_PENDING"
    UNDER_REVIEW       = "UNDER_REVIEW"
    # ── Terminal states ──────────────────────────────────────────────────────
    REPAID             = "REPAID"
    BUFFER_REPAID      = "BUFFER_REPAID"
    DEFAULTED          = "DEFAULTED"
    OFFER_EXPIRED      = "OFFER_EXPIRED"
    OFFER_DECLINED     = "OFFER_DECLINED"


#: Allowed outgoing transitions for each loan state.
_LOAN_TRANSITIONS: Final[dict[LoanState, frozenset[LoanState]]] = {
    LoanState.OFFER_PENDING: frozenset({
        LoanState.ACTIVE,
        LoanState.OFFER_EXPIRED,
        LoanState.OFFER_DECLINED,
    }),
    LoanState.ACTIVE: frozenset({
        LoanState.REPAYMENT_PENDING,
        LoanState.DEFAULTED,
        LoanState.UNDER_REVIEW,
    }),
    LoanState.REPAYMENT_PENDING: frozenset({
        LoanState.REPAID,
        LoanState.BUFFER_REPAID,
        LoanState.DEFAULTED,
    }),
    LoanState.UNDER_REVIEW: frozenset({
        LoanState.ACTIVE,
        LoanState.DEFAULTED,
    }),
    # Terminal states — no outgoing transitions
    LoanState.REPAID:        frozenset(),
    LoanState.BUFFER_REPAID: frozenset(),
    LoanState.DEFAULTED:     frozenset(),
    LoanState.OFFER_EXPIRED: frozenset(),
    LoanState.OFFER_DECLINED: frozenset(),
}

#: Set of terminal loan states for fast membership testing.
_LOAN_TERMINAL_STATES: Final[frozenset[LoanState]] = frozenset(
    state for state, targets in _LOAN_TRANSITIONS.items() if not targets
)


class LoanStateMachine:
    """Enforces the LIP bridge-loan lifecycle state machine (Architecture Spec S7).

    Parameters
    ----------
    initial_state:
        Starting state; defaults to ``OFFER_PENDING``.

    Raises
    ------
    InvalidTransitionError
        On any call to :meth:`transition` that requests a forbidden move.
    """

    def __init__(
        self,
        initial_state: LoanState = LoanState.OFFER_PENDING,
    ) -> None:
        self._state: LoanState = initial_state

    # ── Public interface ─────────────────────────────────────────────────────

    @property
    def current_state(self) -> LoanState:
        """The current loan state."""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """True when the machine has reached a terminal state."""
        return self._state in _LOAN_TERMINAL_STATES

    def transition(self, new_state: LoanState) -> None:
        """Advance the machine to *new_state*.

        Parameters
        ----------
        new_state:
            The target state to transition into.

        Raises
        ------
        InvalidTransitionError
            If the transition from the current state to *new_state* is not
            permitted by the Architecture Spec S7 transition table.
        """
        allowed = _LOAN_TRANSITIONS[self._state]
        if new_state not in allowed:
            raise InvalidTransitionError(self._state.value, new_state.value)
        self._state = new_state

    def allowed_transitions(self) -> frozenset[LoanState]:
        """Return the set of states reachable from the current state."""
        return _LOAN_TRANSITIONS[self._state]

    def __repr__(self) -> str:
        return (
            f"LoanStateMachine(current_state={self._state.value!r}, "
            f"is_terminal={self.is_terminal})"
        )
