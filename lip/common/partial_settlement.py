"""
partial_settlement.py — Policy for handling partial settlement amounts.
GAP-16: Bridge-loan repayment is triggered when the original payment
        settles on the external rail.  In rare cases (partial CHAPS
        recalls, RTP partial-return codes) the settlement_amount may be
        less than the full principal.

Two policies are supported:

  REQUIRE_FULL   — Reject the partial settlement; keep the loan active.
                   RepaymentLoop returns PARTIAL_PENDING without
                   deregistering the loan.  The loan remains live until
                   the full amount arrives or maturity triggers buffer
                   repayment.  The idempotency claim is NOT consumed.

  ACCEPT_PARTIAL — Accept whatever was settled; compute the fee on the
                   actual settled amount.  Deregister the loan as normal.
                   Useful for high-confidence corridors where residual
                   shortfall recovery is handled out-of-band.

REQUIRE_FULL is the conservative default (matches PROGRESS.md open decision).
ACCEPT_PARTIAL requires explicit opt-in and BPI/QUANT sign-off.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lip.common.constants import PARTIAL_SETTLEMENT_MIN_PCT


class PartialSettlementPolicy(str, Enum):
    """Policy governing RepaymentLoop behaviour on partial settlements."""

    REQUIRE_FULL = "REQUIRE_FULL"
    """Keep loan active and return PARTIAL_PENDING status on partial amounts."""

    ACCEPT_PARTIAL = "ACCEPT_PARTIAL"
    """Accept partial settlement; compute fee on settled amount and close loan."""


@dataclass(frozen=True)
class PartialSettlementConfig:
    """Configuration bundle for partial settlement handling in RepaymentLoop.

    Attributes
    ----------
    policy:
        :class:`PartialSettlementPolicy` governing the repayment behaviour.
    minimum_partial_pct:
        Minimum fraction of principal that must be present for ACCEPT_PARTIAL
        to proceed.  Below this threshold the settlement is treated as a
        near-zero noise event and PARTIAL_PENDING is returned regardless of
        policy.  Default: 0.10 (10%).
    """

    policy: PartialSettlementPolicy = PartialSettlementPolicy.REQUIRE_FULL
    minimum_partial_pct: float = float(PARTIAL_SETTLEMENT_MIN_PCT)
