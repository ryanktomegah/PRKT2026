"""
test_p5_fee_floor.py — Regression tests for B9-01.

The P5 cascade intervention fee rate must never drop below the canonical
300 bps fee floor defined in ``lip.common.constants``. The original bug
was ``INTERVENTION_FEE_RATE_BPS = 200`` in ``p5_cascade_engine/constants.py``
which would have made bridge loans appear 33% cheaper than the minimum
price they can ever actually be offered at, biasing the intervention
optimiser's cost-efficiency ratio.

These tests will fail if anyone:
  - Reverts the constant to a literal below 300
  - Decouples ``INTERVENTION_FEE_RATE_BPS`` from ``FEE_FLOOR_BPS`` without
    simultaneously updating this test (forcing QUANT review)
"""
from __future__ import annotations

from decimal import Decimal

from lip.common.constants import FEE_FLOOR_BPS
from lip.p5_cascade_engine.constants import INTERVENTION_FEE_RATE_BPS


def test_intervention_fee_rate_meets_canonical_floor() -> None:
    """B9-01: P5 intervention fee rate must be >= FEE_FLOOR_BPS."""
    assert FEE_FLOOR_BPS == Decimal("300"), (
        "Canonical FEE_FLOOR_BPS changed — this is a QUANT-gated constant. "
        "If this assertion fires, lip/common/constants.py was edited without "
        "QUANT sign-off OR the entire fee floor is being re-evaluated."
    )
    assert Decimal(str(INTERVENTION_FEE_RATE_BPS)) >= FEE_FLOOR_BPS, (
        f"INTERVENTION_FEE_RATE_BPS={INTERVENTION_FEE_RATE_BPS} violates the "
        f"canonical FEE_FLOOR_BPS={FEE_FLOOR_BPS} (CLAUDE.md canonical constant). "
        "See B9-01 in docs/review/2026-04-08/09-p5-cascade.md."
    )


def test_intervention_fee_rate_bound_to_fee_floor() -> None:
    """B9-01: rate is bound to FEE_FLOOR_BPS, not an independent literal.

    If a future change replaces the binding with a literal (even a correct
    300), this test fails — forcing the author to justify the decoupling
    and get QUANT sign-off.
    """
    assert INTERVENTION_FEE_RATE_BPS is FEE_FLOOR_BPS, (
        "INTERVENTION_FEE_RATE_BPS must be bound to FEE_FLOOR_BPS "
        "(single source of truth). Decoupling requires QUANT sign-off."
    )
