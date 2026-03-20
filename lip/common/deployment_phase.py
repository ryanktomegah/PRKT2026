"""
deployment_phase.py — BPI deployment phase model and fee waterfall logic.

Three deployment phases with different capital structures and income classifications:
  Phase 1 (LICENSOR): Bank funds 100%.  BPI earns 15% IP royalty.
  Phase 2 (HYBRID):   30% bank / 70% BPI capital.  BPI earns 40% co-lending return.
  Phase 3 (FULL_MLO): BPI funds 100%.  BPI earns 75% gross lending revenue.

Bank fee decomposition (Phase 2/3) prevents negotiation traps at transition:
  Phase 2 bank share:  30% capital return  +  30% distribution premium  =  60%
  Phase 3 bank share:   0% capital return  +  25% distribution premium  =  25%

Invariants (enforced by get_phase_config):
  bpi_fee_share + bank_fee_share == 1
  bank_capital_return_share + bank_distribution_premium_share == bank_fee_share
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Optional

from lip.common.constants import (
    PHASE_1_BPI_FEE_SHARE,
    PHASE_1_INCOME_TYPE,
    PHASE_2_BANK_CAPITAL_RETURN,
    PHASE_2_BANK_DISTRIBUTION_PREMIUM,
    PHASE_2_BPI_FEE_SHARE,
    PHASE_2_INCOME_TYPE,
    PHASE_3_BANK_CAPITAL_RETURN,
    PHASE_3_BANK_DISTRIBUTION_PREMIUM,
    PHASE_3_BPI_FEE_SHARE,
    PHASE_3_INCOME_TYPE,
)

# Capital provider preferred return rate (reporting line item — not deducted from fee shares)
_CAPITAL_PROVIDER_PREFERRED_RATE = Decimal("0.12")  # 12% annualized


class DeploymentPhase(str, Enum):
    """BPI deployment phase — determines capital structure and income classification."""

    LICENSOR = "LICENSOR"    # Phase 1: bank funds 100%, BPI earns IP royalty
    HYBRID = "HYBRID"        # Phase 2: 30% bank / 70% BPI, co-lending return
    FULL_MLO = "FULL_MLO"    # Phase 3: BPI funds 100%, gross lending revenue


@dataclass(frozen=True)
class PhaseFeeConfig:
    """Fee split configuration for a deployment phase.

    Invariants (verified at module load — see _PHASE_CONFIGS):
      bpi_fee_share + bank_fee_share == 1
      bank_capital_return_share + bank_distribution_premium_share == bank_fee_share
    """

    bpi_fee_share: Decimal                    # BPI's fraction of the fee
    bank_fee_share: Decimal                   # Bank's fraction of the fee
    income_type: str                          # "ROYALTY" or "LENDING_REVENUE"
    bank_capital_return_share: Decimal        # Bank's capital-proportional share
    bank_distribution_premium_share: Decimal  # Bank's origination/compliance share


@dataclass
class FeeWaterfall:
    """Entity-level dollar allocation of a collected fee for one deployment phase.

    All USD amounts are rounded to cents (2 decimal places).
    capital_provider_cost_usd is a reporting line item only — it does NOT
    reduce bpi_share_usd or bank_share_usd.
    """

    deployment_phase: str
    income_type: str
    total_fee_usd: Decimal
    bpi_share_usd: Decimal
    bank_share_usd: Decimal
    bank_capital_return_usd: Decimal
    bank_distribution_premium_usd: Decimal
    capital_provider_cost_usd: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Phase config registry
# ---------------------------------------------------------------------------

_LICENSOR_BANK_SHARE = Decimal("1") - PHASE_1_BPI_FEE_SHARE  # 0.85

_PHASE_CONFIGS: dict[DeploymentPhase, PhaseFeeConfig] = {
    DeploymentPhase.LICENSOR: PhaseFeeConfig(
        bpi_fee_share=PHASE_1_BPI_FEE_SHARE,
        bank_fee_share=_LICENSOR_BANK_SHARE,
        income_type=PHASE_1_INCOME_TYPE,
        # Phase 1: bank keeps full 85% as their own fee; no capital-return split applies.
        # bank_capital_return == 0; bank_distribution_premium == bank_fee_share.
        bank_capital_return_share=Decimal("0"),
        bank_distribution_premium_share=_LICENSOR_BANK_SHARE,
    ),
    DeploymentPhase.HYBRID: PhaseFeeConfig(
        bpi_fee_share=PHASE_2_BPI_FEE_SHARE,
        bank_fee_share=Decimal("1") - PHASE_2_BPI_FEE_SHARE,  # 0.60
        income_type=PHASE_2_INCOME_TYPE,
        bank_capital_return_share=PHASE_2_BANK_CAPITAL_RETURN,
        bank_distribution_premium_share=PHASE_2_BANK_DISTRIBUTION_PREMIUM,
    ),
    DeploymentPhase.FULL_MLO: PhaseFeeConfig(
        bpi_fee_share=PHASE_3_BPI_FEE_SHARE,
        bank_fee_share=Decimal("1") - PHASE_3_BPI_FEE_SHARE,  # 0.25
        income_type=PHASE_3_INCOME_TYPE,
        bank_capital_return_share=PHASE_3_BANK_CAPITAL_RETURN,
        bank_distribution_premium_share=PHASE_3_BANK_DISTRIBUTION_PREMIUM,
    ),
}


def get_phase_config(phase: DeploymentPhase) -> PhaseFeeConfig:
    """Return the PhaseFeeConfig for *phase*.

    Raises KeyError for unknown phases (should not happen with a valid enum value).
    """
    return _PHASE_CONFIGS[phase]


# ---------------------------------------------------------------------------
# Fee waterfall computation
# ---------------------------------------------------------------------------

def compute_fee_waterfall(
    fee: Decimal,
    phase: DeploymentPhase,
    capital_deployed: Optional[Decimal] = None,
) -> FeeWaterfall:
    """Compute the entity-level fee allocation for a deployment phase.

    Parameters
    ----------
    fee:
        Total collected fee in USD (output of ``compute_loan_fee``).
    phase:
        Deployment phase governing the split.
    capital_deployed:
        Total capital deployed for this loan (BPI + bank combined), in USD.
        Used only to compute the capital_provider_cost reporting line item
        (12% annualized preferred return on deployed capital).  Optional;
        defaults to None (cost line = $0 when omitted).

    Returns
    -------
    FeeWaterfall
        Dollar amounts for each entity, rounded to cents.
        Invariants:
          bpi_share_usd + bank_share_usd == total_fee_usd
          bank_capital_return_usd + bank_distribution_premium_usd == bank_share_usd
    """
    fee = Decimal(str(fee))
    cfg = get_phase_config(phase)

    bpi_share = (fee * cfg.bpi_fee_share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    bank_share = (fee * cfg.bank_fee_share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Adjust bank_share so bpi + bank == fee exactly (absorb rounding residual in bank share)
    bank_share = fee - bpi_share

    bank_capital_return = (
        fee * cfg.bank_capital_return_share
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Distribution premium = bank_share - capital_return (absorbs any penny rounding)
    bank_distribution_premium = bank_share - bank_capital_return

    # Capital provider cost: 12% annualized on deployed capital (reporting only)
    capital_cost = Decimal("0")
    if capital_deployed is not None and phase != DeploymentPhase.LICENSOR:
        capital_cost = (
            Decimal(str(capital_deployed)) * _CAPITAL_PROVIDER_PREFERRED_RATE
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return FeeWaterfall(
        deployment_phase=phase.value,
        income_type=cfg.income_type,
        total_fee_usd=fee,
        bpi_share_usd=bpi_share,
        bank_share_usd=bank_share,
        bank_capital_return_usd=bank_capital_return,
        bank_distribution_premium_usd=bank_distribution_premium,
        capital_provider_cost_usd=capital_cost,
    )
