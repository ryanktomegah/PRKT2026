"""
fee.py — Fee derivation for bridge loans
C2 Spec Section 9:
  fee_bps ANNUALIZED, 300 bps floor
  Per-cycle formula: fee = loan_amount * (fee_bps / 10000) * (days_funded / 365)
  Floor: 300 bps annualized = 0.0575% per 7-day cycle
  DO NOT apply fee_bps as a flat per-cycle rate.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 300 bps annualized floor  (C2 Spec Section 9)
FEE_FLOOR_BPS: Decimal = Decimal("300")

# 300 bps annualized over a 7-day cycle as a decimal multiplier:
#   300 / 10000 * 7 / 365 = 0.000575342...
#   Expressed as a percentage: ≈ 0.0575% per 7-day cycle.
#   The value stored here is the DECIMAL (not percentage) representation.
FEE_FLOOR_PER_7DAY_CYCLE: Decimal = Decimal("0.000575")

_DAYS_IN_YEAR: Decimal = Decimal("365")
_BPS_DIVISOR: Decimal = Decimal("10000")


def compute_fee_bps_from_el(
    pd: Decimal,
    lgd: Decimal,
    ead: Decimal,
    risk_free_rate: Decimal = Decimal("0.05"),
) -> Decimal:
    """Derive the ANNUALIZED fee in basis points from expected-loss components.

    ANNUALIZED rate in basis points.  Per-cycle fee =
    ``loan_amount * (fee_bps/10000) * (days_funded/365)``.
    Floor: 300 bps annualized.  As a decimal multiplier over a 7-day cycle:
    300/10000 * 7/365 = 0.000575 (i.e. ≈ 0.0575% of the loan amount).
    DO NOT apply as flat per-cycle rate.

    Formula
    -------
    The annualized EL in bps is:

        fee_bps = PD × LGD × 10 000

    This represents the expected annual credit cost per unit of EAD expressed
    in basis points.  The 300 bps floor ensures minimum revenue coverage for
    thin-file / high-uncertainty borrowers.

    Parameters
    ----------
    pd:
        Probability of Default in ``[0, 1]``.
    lgd:
        Loss Given Default in ``[0, 1]``.
    ead:
        Exposure at Default (loan notional, in any consistent currency unit).
        Used for validation only; the bps formula is already normalised per unit
        of EAD, so the numeric value of *ead* does not change the result.
    risk_free_rate:
        Annualized risk-free rate (default 5 %).  Reserved for future cost-of-
        funds adjustment; not applied in the current formula version.

    Returns
    -------
    Decimal
        Annualized fee in basis points, rounded to 1 decimal place.
        Minimum value is ``FEE_FLOOR_BPS`` (300.0 bps).
    """
    pd = Decimal(str(pd))
    lgd = Decimal(str(lgd))

    # Annualized expected-loss bps:  PD * LGD * 10_000
    fee_bps = pd * lgd * _BPS_DIVISOR

    # Apply absolute floor
    fee_bps = max(fee_bps, FEE_FLOOR_BPS)

    return fee_bps.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def compute_loan_fee(
    loan_amount: Decimal,
    fee_bps: Decimal,
    days_funded: int,
) -> Decimal:
    """Compute the ACTUAL cash fee for a bridge-loan cycle.

    Uses the time-proportionate per-cycle formula:

        fee = loan_amount × (fee_bps / 10 000) × (days_funded / 365)

    This is the correct interpretation of an annualized rate — the fee scales
    with the fraction of the year the loan is outstanding.  Do NOT apply
    ``fee_bps`` as a flat per-cycle rate (e.g. charging 300 bps for every
    7-day cycle regardless of tenor).

    Parameters
    ----------
    loan_amount:
        Notional value of the bridge loan in the base currency (e.g. USD).
    fee_bps:
        Annualized fee rate in basis points (minimum 300 bps per spec).
    days_funded:
        Number of calendar days the loan is outstanding.

    Returns
    -------
    Decimal
        Actual fee rounded to 2 decimal places (cents).

    Examples
    --------
    >>> compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
    Decimal('575.34')
    """
    loan_amount = Decimal(str(loan_amount))
    fee_bps = Decimal(str(fee_bps))
    days = Decimal(str(days_funded))

    fee = loan_amount * (fee_bps / _BPS_DIVISOR) * (days / _DAYS_IN_YEAR)
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def verify_floor_applies(fee_bps: Decimal) -> bool:
    """Return ``True`` when *fee_bps* equals the regulatory floor of 300 bps.

    This indicates the floor was binding — the model-derived EL was below 300 bps
    and the fee was raised to the minimum.  Useful for audit logging and stress
    test verification.

    Parameters
    ----------
    fee_bps:
        Annualized fee in basis points (output of :func:`compute_fee_bps_from_el`).

    Returns
    -------
    bool
        ``True`` iff ``fee_bps == FEE_FLOOR_BPS`` (exactly 300.0 bps).
    """
    return Decimal(str(fee_bps)) == FEE_FLOOR_BPS
