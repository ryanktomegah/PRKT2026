"""
fee.py — Fee derivation for bridge loans
C2 Spec Section 9:
  fee_bps ANNUALIZED, 300 bps floor (platform minimum - applies to ALL loans)
  Two-tier pricing: 800 bps warehouse-eligibility floor for SPV-funded loans (Phase 2/3)
  Per-cycle formula: fee = loan_amount * (fee_bps/10000) * (days_funded/365)
  Platform floor (300 bps): bank-funded loans in Phase 1, or low-fee loans in Phase 2/3
  Warehouse floor (800 bps): SPV-funded loans in Phase 2/3 must meet this minimum
  Floor: 300 bps annualized = 0.0575% per 7-day cycle.
  DO NOT apply fee_bps as a flat per-cycle rate.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Union

from lip.common.constants import (
    FEE_FLOOR_BPS,
    FEE_FLOOR_PER_7DAY_CYCLE,  # noqa: F401 — re-exported for test consumers
    FEE_FLOOR_TIER_SMALL_BPS,
    FEE_FLOOR_TIER_MID_BPS,
    FEE_TIER_MID_THRESHOLD_USD,
    MIN_LOAN_AMOUNT_USD,
    PLATFORM_ROYALTY_RATE,
    WAREHOUSE_ELIGIBILITY_FLOOR_BPS,
    is_spv_warehouse_eligible,
)
from lip.p5_cascade_engine.constants import CASCADE_DISCOUNT_CAP

_DAYS_IN_YEAR: Decimal = Decimal("365")
_BPS_DIVISOR: Decimal = Decimal("10000")


def compute_fee_bps_from_el(
    pd: Decimal,
    lgd: Decimal,
    ead: Decimal,
    risk_free_rate: Decimal = Decimal("0.05"),
) -> Decimal:
    """Derive ANNUALIZED fee in basis points from expected-loss components.

    ANNUALIZED rate in basis points.  Per-cycle fee =
    ``loan_amount * (fee_bps/10000) * (days_funded/365)```.
    Platform floor: 300 bps (FEE_FLOOR_BPS) — applies to ALL loans.
    Warehouse floor: 800 bps (WAREHOUSE_ELIGIBILITY_FLOOR_BPS) — required for
    SPV-funded loans to service capital structure.

    Formula
    -------
    The annualized EL in bps is:

        fee_bps = PD × LGD × 10,000

    This represents the expected annual credit cost per unit of EAD expressed
    in basis points.  The 300 bps platform floor ensures minimum revenue
    coverage for thin-file / high-uncertainty borrowers.  The 800 bps
    warehouse floor ensures SPV-funded loans can service debt.

    Parameters
    ----------
    pd:
        Probability of Default in ``[0, 1]``.
    lgd:
        Loss Given Default in ``[0, 1]``.
    ead:
        Exposure at Default (loan notional, in any consistent currency unit).
        Used for validation only; bps formula is already normalised per unit
        of *ead*, so numeric value of *ead* does not change result.
    risk_free_rate:
        Annualized risk-free rate (default 5 %).  Reserved for future cost-of-
        funds adjustment; not applied in the current formula version.

    Returns
    -------
    Decimal
        Annualized fee in basis points, rounded to 1 decimal place.
        Minimum value is ``FEE_FLOOR_BPS`` (300.0 bps platform minimum).
    """
    pd = Decimal(str(pd))
    lgd = Decimal(str(lgd))

    # Annualized expected-loss bps: PD * LGD * 10_000
    fee_bps = pd * lgd * _BPS_DIVISOR

    # Apply platform floor (300 bps minimum - applies to ALL loans)
    fee_bps = max(fee_bps, FEE_FLOOR_BPS)

    return fee_bps.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def compute_loan_fee(
    loan_amount: Union[Decimal, float, int],
    fee_bps: Union[Decimal, float, int],
    days_funded: Union[int, float, Decimal],
    spv_eligible: bool = False,
) -> Decimal:
    """Compute the ACTUAL cash fee for a bridge-loan cycle.

    Uses the time-proportionate per-cycle formula:

        fee = loan_amount × (fee_bps / 10,000) × (days_funded / 365)

    This is the correct interpretation of an annualized rate — fee scales
    with the fraction of the year that the loan is outstanding.

    Parameters
    ----------
    loan_amount:
        Notional value of the bridge loan in base currency (e.g., USD).
    fee_bps:
        Annualized fee rate in basis points (minimum 300 bps platform floor).
        For SPV-funded loans in Phase 2/3, must be >= 800 bps
        to be warehouse-eligible (WAREHOUSE_ELIGIBILITY_FLOOR_BPS).
    days_funded:
        Number of calendar days that the loan is outstanding.
    spv_eligible:
        Override flag for SPV warehouse eligibility. If True, loan is
        considered SPV-warehouse-eligible regardless of fee rate. If False,
        loan is bank-funded (BPI earns IP royalty only).

    Returns
    -------
    Decimal
        Actual fee rounded to 2 decimal places (cents).

    Notes
    -----
    Two-Tier Pricing Floor:
    - Platform minimum (300 bps): Applies to ALL loans
    - Warehouse floor (800 bps): Required for SPV-funded loans (Phase 2/3)
      - Ensures asset yield (~8% at 800 bps) covers debt service cost
      - Loans below 800 bps in Phase 2/3 are routed to bank balance sheet
      - BPI earns IP royalty (30% share) on bank-funded loans
      - SPV-funded loans at >= 800 bps generate positive BPI equity returns

    Examples
    --------
    >>> compute_loan_fee(Decimal("1000000"), Decimal("300"), 7, False)
    Decimal('575.34')
    >>> compute_loan_fee(Decimal("1000000"), Decimal("400"), 7, True)  # SPV-eligible
    Decimal('767.12')
    >>> compute_loan_fee(Decimal("1000000"), Decimal("600"), 7, False)  # SPV-eligible
    Decimal('1150.68')
    """
    loan_amount = Decimal(str(loan_amount))
    fee_bps = Decimal(str(fee_bps))
    days = Decimal(str(days_funded))

    fee = loan_amount * (fee_bps / _BPS_DIVISOR) * (days / _DAYS_IN_YEAR)
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_platform_royalty(
    fee_amount_usd: Decimal,
    royalty_rate: Decimal = PLATFORM_ROYALTY_RATE,
) -> Decimal:
    """Compute BPI's technology licensor royalty from a collected loan fee.

    The licensor royalty is BPI's IP license fee — extracted from fee
    of licensee (MLO / MIPLO / ELO) collects from its borrower. BPI
    does not deploy capital or operate facility; it licenses technology.

        royalty = fee_amount_usd × royalty_rate
        net_to_entities = fee_amount_usd − royalty

    Parameters
    ----------
    fee_amount_usd:
        Actual cash fee for bridge-loan cycle (output of
        :func:`compute_loan_fee`).
    royalty_rate:
        Fraction of *fee_amount_usd* that flows to BPI as a technology license fee.
        Defaults to 30% (``PLATFORM_ROYALTY_RATE`` from constants.py).  Pass an
        explicit value to override for testing or future rate adjustments.

    Returns
    -------
    Decimal
        Platform royalty in USD, rounded to 2 decimal places (cents).

    Notes
    -----
    Royalty applies to all loans regardless of funding source. The 300 bps platform
    minimum is a floor, not a warehouse eligibility threshold.
    """
    fee_amount_usd = Decimal(str(fee_amount_usd))
    royalty_rate = Decimal(str(royalty_rate))
    royalty = fee_amount_usd * royalty_rate
    return royalty.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_tiered_fee_floor(loan_amount: Decimal) -> Decimal:
    """Return the applicable annualized fee floor in bps for a given principal amount.

    This now returns the platform floor (300 bps) for consistency.
    The two-tier warehouse eligibility is handled separately via
    is_spv_warehouse_eligible() in the loan origination logic.

    Parameters
    ----------
    loan_amount:
        Bridge-loan principal in USD.

    Returns
    -------
    Decimal
        Annualized fee floor in basis points (platform minimum of 300 bps).
    """
    amount = Decimal(str(loan_amount))

    # Platform floor applies to all loans
    return FEE_FLOOR_BPS


def verify_floor_applies(fee_bps: Decimal) -> bool:
    """Return ``True`` when *fee_bps* equals the platform floor of 300 bps.

    This indicates the platform floor was binding — model-derived EL was below
    300 bps and fee was raised to the minimum. Useful for audit logging
    and stress test verification.

    Note: The 800 bps warehouse eligibility floor is separate from the
    platform floor. This function only checks the 300 bps platform minimum.

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


@dataclass
class CascadeAdjustedPricing:
    """Result of cascade-adjusted PD computation (P5 blueprint §7.2).

    QUANT invariant: warehouse-eligible loans must meet WAREHOUSE_ELIGIBILITY_FLOOR_BPS
    (800 bps minimum ensures debt service capability).
    """
    base_pd: Decimal
    cascade_adjusted_pd: Decimal
    cascade_discount: Decimal
    base_fee_bps: Decimal
    cascade_adjusted_fee_bps: Decimal
    cascade_value_prevented: Decimal
    intervention_cost: Decimal


def compute_cascade_adjusted_pd(
    base_pd: Decimal,
    cascade_value_prevented: Decimal,
    intervention_cost: Decimal,
    lgd: Decimal = Decimal("0.45"),
    ead: Decimal = Decimal("1000000"),
) -> CascadeAdjustedPricing:
    """Compute cascade-adjusted PD and fee for intervention pricing.

    The cascade-adjusted PD is LOWER than base PD because an intervention
    prevents a larger cascade — the bank's risk committee sees a better
    risk-adjusted return.

    Formula (P5 blueprint §7.2, QUANT sign-off required):
        cascade_discount = min(CASCADE_DISCOUNT_CAP, value_prevented / (10 * cost))
        cascade_adjusted_pd = base_pd * (1 - cascade_discount)

    The 10x divisor is conservative — prevents aggressive discounting on small
    interventions with large claimed cascade values. The 30% cap ensures that
    cascade discount never reduces PD by more than 30%.

    Parameters
    ----------
    base_pd : Decimal
        Base probability of default for bridge borrower.
    cascade_value_prevented : Decimal
        Total downstream CVaR prevented by this intervention.
    intervention_cost : Decimal
        Bridge loan amount (cost of intervention).
    lgd : Decimal
        Loss Given Default (default 0.45 for unsecured bridge).
    ead : Decimal
        Exposure at Default (for fee computation).

    Returns
    -------
    CascadeAdjustedPricing
        Full pricing result with base and adjusted PD/fee.

    QUANT Invariant
    --------------
    All cascade-adjusted fees must meet the warehouse eligibility floor
    (WAREHOUSE_ELIGIBILITY_FLOOR_BPS = 800 bps) for SPV-funded loans.
    This ensures asset yield (~8% at 800 bps) covers debt service cost
    (~7% senior + ~1% BPI equity margin).
    """
    base_pd = Decimal(str(base_pd))
    cascade_value_prevented = Decimal(str(cascade_value_prevented))
    intervention_cost = Decimal(str(intervention_cost))

    # Guard: base_pd must be a valid probability in [0, 1].
    # An out-of-range value (e.g. from a pipeline passing raw EL instead of PD)
    # would produce an anomalously high fee_bps that bypasses the 300 bps floor check.
    if not (Decimal("0") <= base_pd <= Decimal("1")):
        raise ValueError(
            f"base_pd must be in [0, 1]; got {base_pd}. "
            "Ensure you input is a probability, not a raw expected-loss value."
        )

    # Cascade discount (capped at 30%)
    if intervention_cost > 0 and cascade_value_prevented > 0:
        raw_discount = cascade_value_prevented / (Decimal("10") * intervention_cost)
        cascade_discount = min(raw_discount, CASCADE_DISCOUNT_CAP)
    else:
        cascade_discount = Decimal("0")

    # Adjusted PD
    cascade_adjusted_pd = base_pd * (Decimal("1") - cascade_discount)

    # Fee computation
    base_fee_bps = compute_fee_bps_from_el(base_pd, lgd, ead)
    cascade_adjusted_fee_bps = compute_fee_bps_from_el(cascade_adjusted_pd, lgd, ead)

    # QUANT invariant: warehouse-eligible loans must meet 800 bps floor
    # Platform floor (300 bps) is checked by compute_fee_bps_from_el,
    # but warehouse eligibility (800 bps) must be verified here for cascade-adjusted fees.
    if cascade_adjusted_fee_bps < Decimal(str(WAREHOUSE_ELIGIBILITY_FLOOR_BPS)):
        raise ValueError(
            f"CASCADE_ADJUSTED_FEE {cascade_adjusted_fee_bps} bps < "
            f"WAREHOUSE_ELIGIBILITY_FLOOR_BPS={WAREHOUSE_ELIGIBILITY_FLOOR_BPS}. "
            "SPV-funded loans must generate >= 8% yield to service capital structure."
        )

    return CascadeAdjustedPricing(
        base_pd=base_pd,
        cascade_adjusted_pd=cascade_adjusted_pd,
        cascade_discount=cascade_discount,
        base_fee_bps=base_fee_bps,
        cascade_adjusted_fee_bps=cascade_adjusted_fee_bps,
        cascade_value_prevented=cascade_value_prevented,
        intervention_cost=intervention_cost,
    )
