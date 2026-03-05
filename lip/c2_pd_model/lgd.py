"""
lgd.py — Loss Given Default estimation
C2 Spec Section 8: Jurisdiction-tiered defaults

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# ---------------------------------------------------------------------------
# Jurisdiction default LGD table  (C2 Spec Section 8)
# ---------------------------------------------------------------------------

LGD_BY_JURISDICTION: dict = {
    "US": Decimal("0.35"),
    "EU": Decimal("0.30"),
    "UK": Decimal("0.32"),
    "APAC": Decimal("0.40"),
    "LATAM": Decimal("0.45"),
    "MEA": Decimal("0.50"),
    "DEFAULT": Decimal("0.45"),
}

# Absolute floor on final LGD regardless of collateral benefit
_LGD_FLOOR = Decimal("0.10")

# Collateral-type reduction tables (absolute percentage points off LGD)
_COLLATERAL_REDUCTIONS: dict = {
    "CASH": Decimal("0.15"),
    "SECURITIES": Decimal("0.10"),
    "REAL_ESTATE": Decimal("0.20"),
}


def estimate_lgd(
    jurisdiction: str,
    collateral_type: Optional[str] = None,
    collateral_value_pct: Optional[Decimal] = None,
) -> Decimal:
    """Estimate Loss Given Default for a single-jurisdiction exposure.

    Resolution order
    ----------------
    1. Look up the base LGD for *jurisdiction* from ``LGD_BY_JURISDICTION``.
       Falls back to the ``'DEFAULT'`` entry for unknown jurisdictions.
    2. Apply any *collateral_type* reduction (absolute bps off LGD).
    3. Apply *collateral_value_pct* reduction if provided.
    4. Clamp the result to a minimum of 0.10 (10 %).

    Parameters
    ----------
    jurisdiction:
        ISO/internal jurisdiction code (e.g. ``'US'``, ``'EU'``, ``'APAC'``).
        Case-sensitive; normalise upstream if needed.
    collateral_type:
        Optional collateral category.  Supported values and their LGD
        reductions: ``'CASH'`` → -0.15, ``'SECURITIES'`` → -0.10,
        ``'REAL_ESTATE'`` → -0.20.  Unknown types are ignored.
    collateral_value_pct:
        Optional additional reduction expressed as a fraction of EAD
        (e.g. ``Decimal('0.20')`` for 20 % collateral coverage).

    Returns
    -------
    Decimal
        LGD estimate in ``[0.10, 1.00]``, rounded to 4 decimal places.
    """
    base_lgd = LGD_BY_JURISDICTION.get(jurisdiction, LGD_BY_JURISDICTION["DEFAULT"])

    reduction = Decimal("0")

    # Collateral type reduction
    if collateral_type is not None:
        reduction += _COLLATERAL_REDUCTIONS.get(collateral_type.upper(), Decimal("0"))

    # Explicit collateral value percentage reduction
    if collateral_value_pct is not None:
        reduction += Decimal(str(collateral_value_pct))

    lgd = base_lgd - reduction
    lgd = max(lgd, _LGD_FLOOR)
    lgd = min(lgd, Decimal("1.00"))
    return lgd.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def lgd_for_corridor(
    sending_jurisdiction: str,
    receiving_jurisdiction: str,
) -> Decimal:
    """Compute the corridor LGD as the maximum of the two endpoint jurisdictions.

    Taking the maximum is a conservative approach: the corridor exposure inherits
    the higher-risk jurisdiction's LGD to account for settlement-leg risk from
    either side.

    Parameters
    ----------
    sending_jurisdiction:
        Jurisdiction of the sending entity (MLO/MIPLO side).
    receiving_jurisdiction:
        Jurisdiction of the receiving entity (ELO/counterparty side).

    Returns
    -------
    Decimal
        Maximum of ``estimate_lgd(sending_jurisdiction)`` and
        ``estimate_lgd(receiving_jurisdiction)``, rounded to 4 decimal places.
    """
    lgd_send = estimate_lgd(sending_jurisdiction)
    lgd_recv = estimate_lgd(receiving_jurisdiction)
    corridor_lgd = max(lgd_send, lgd_recv)
    return corridor_lgd.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
