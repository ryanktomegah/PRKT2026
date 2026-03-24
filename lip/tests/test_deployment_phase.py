"""
test_deployment_phase.py — Unit tests for deployment phase fee model.

Coverage:
  - DeploymentPhase enum values
  - PhaseFeeConfig invariants (bpi + bank == 1; bank decomposition == bank_share)
  - get_phase_config lookup
  - compute_fee_waterfall: dollar allocation per phase
  - Phase 1 backward-compatibility with compute_platform_royalty
  - income_type classification per phase
  - FeeWaterfall: bpi + bank == total_fee
  - Capital provider cost: reported but does not reduce fee shares
"""
from decimal import Decimal

import pytest

from lip.c2_pd_model.fee import compute_platform_royalty
from lip.common.deployment_phase import (
    DeploymentPhase,
    FeeWaterfall,
    compute_fee_waterfall,
    get_phase_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# PhaseFeeConfig invariants
# ---------------------------------------------------------------------------

class TestPhaseFeeConfigInvariants:
    """Verify share sums and decomposition invariants for all three phases."""

    @pytest.mark.parametrize("phase", list(DeploymentPhase))
    def test_bpi_plus_bank_equals_one(self, phase: DeploymentPhase) -> None:
        cfg = get_phase_config(phase)
        assert cfg.bpi_fee_share + cfg.bank_fee_share == Decimal("1"), (
            f"{phase}: bpi_fee_share + bank_fee_share != 1"
        )

    @pytest.mark.parametrize("phase", list(DeploymentPhase))
    def test_bank_decomposition_equals_bank_share(self, phase: DeploymentPhase) -> None:
        cfg = get_phase_config(phase)
        decomposed = cfg.bank_capital_return_share + cfg.bank_distribution_premium_share
        assert decomposed == cfg.bank_fee_share, (
            f"{phase}: bank_capital_return_share + bank_distribution_premium_share "
            f"({decomposed}) != bank_fee_share ({cfg.bank_fee_share})"
        )

    def test_phase1_income_type_is_royalty(self) -> None:
        cfg = get_phase_config(DeploymentPhase.LICENSOR)
        assert cfg.income_type == "ROYALTY"

    @pytest.mark.parametrize("phase", [DeploymentPhase.HYBRID, DeploymentPhase.FULL_MLO])
    def test_phase2_3_income_type_is_lending_revenue(self, phase: DeploymentPhase) -> None:
        cfg = get_phase_config(phase)
        assert cfg.income_type == "LENDING_REVENUE"

    def test_phase2_bank_capital_return_is_thirty_pct(self) -> None:
        cfg = get_phase_config(DeploymentPhase.HYBRID)
        assert cfg.bank_capital_return_share == _dec("0.30")

    def test_phase3_bank_capital_return_is_zero(self) -> None:
        cfg = get_phase_config(DeploymentPhase.FULL_MLO)
        assert cfg.bank_capital_return_share == _dec("0")

    def test_phase3_bank_distribution_premium_is_twenty_pct(self) -> None:
        cfg = get_phase_config(DeploymentPhase.FULL_MLO)
        assert cfg.bank_distribution_premium_share == _dec("0.20")


# ---------------------------------------------------------------------------
# compute_fee_waterfall — dollar allocation
# ---------------------------------------------------------------------------

class TestComputeFeeWaterfall:
    """Spot-check waterfall outputs and invariants for all phases."""

    def test_phase1_bpi_share_matches_compute_platform_royalty(self) -> None:
        """Phase 1 output must be bit-identical to compute_platform_royalty(fee)."""
        fee = _dec("575.34")
        wf = compute_fee_waterfall(fee, DeploymentPhase.LICENSOR)
        legacy = compute_platform_royalty(fee)
        assert wf.bpi_share_usd == legacy, (
            f"Phase 1 bpi_share_usd ({wf.bpi_share_usd}) != compute_platform_royalty ({legacy})"
        )

    def test_phase1_income_type(self) -> None:
        wf = compute_fee_waterfall(_dec("767.00"), DeploymentPhase.LICENSOR)
        assert wf.income_type == "ROYALTY"

    def test_phase2_bpi_share_55pct(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.HYBRID)
        # 767 * 0.55 = 421.85
        assert wf.bpi_share_usd == _dec("421.85"), f"Got {wf.bpi_share_usd}"

    def test_phase2_bank_share_45pct(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.HYBRID)
        # 767 - 421.85 = 345.15
        assert wf.bank_share_usd == _dec("345.15"), f"Got {wf.bank_share_usd}"

    def test_phase2_bank_decomposition(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.HYBRID)
        # capital_return = 767 * 0.30 = 230.10; distribution_premium = 345.15 - 230.10 = 115.05
        assert wf.bank_capital_return_usd == _dec("230.10"), f"Got {wf.bank_capital_return_usd}"
        assert wf.bank_distribution_premium_usd == _dec("115.05"), f"Got {wf.bank_distribution_premium_usd}"

    def test_phase2_income_type(self) -> None:
        wf = compute_fee_waterfall(_dec("767.00"), DeploymentPhase.HYBRID)
        assert wf.income_type == "LENDING_REVENUE"

    def test_phase3_bpi_share_80pct(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.FULL_MLO)
        # 767 * 0.80 = 613.60
        assert wf.bpi_share_usd == _dec("613.60"), f"Got {wf.bpi_share_usd}"

    def test_phase3_bank_share_20pct(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.FULL_MLO)
        # 767 - 613.60 = 153.40
        assert wf.bank_share_usd == _dec("153.40"), f"Got {wf.bank_share_usd}"

    def test_phase3_bank_capital_return_zero(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.FULL_MLO)
        assert wf.bank_capital_return_usd == _dec("0.00"), f"Got {wf.bank_capital_return_usd}"

    def test_phase3_bank_distribution_premium(self) -> None:
        fee = _dec("767.00")
        wf = compute_fee_waterfall(fee, DeploymentPhase.FULL_MLO)
        # bank_share = 153.40; capital_return = 0; so distribution_premium = 153.40
        assert wf.bank_distribution_premium_usd == _dec("153.40"), f"Got {wf.bank_distribution_premium_usd}"

    def test_phase3_income_type(self) -> None:
        wf = compute_fee_waterfall(_dec("767.00"), DeploymentPhase.FULL_MLO)
        assert wf.income_type == "LENDING_REVENUE"

    @pytest.mark.parametrize("phase", list(DeploymentPhase))
    def test_bpi_plus_bank_equals_total_fee(self, phase: DeploymentPhase) -> None:
        fee = _dec("1234.56")
        wf = compute_fee_waterfall(fee, phase)
        assert wf.bpi_share_usd + wf.bank_share_usd == fee, (
            f"{phase}: bpi_share + bank_share ({wf.bpi_share_usd + wf.bank_share_usd}) != fee ({fee})"
        )

    @pytest.mark.parametrize("phase", list(DeploymentPhase))
    def test_bank_decomposition_equals_bank_share(self, phase: DeploymentPhase) -> None:
        fee = _dec("999.99")
        wf = compute_fee_waterfall(fee, phase)
        decomposed = wf.bank_capital_return_usd + wf.bank_distribution_premium_usd
        assert decomposed == wf.bank_share_usd, (
            f"{phase}: capital_return + distribution_premium ({decomposed}) != bank_share ({wf.bank_share_usd})"
        )

    def test_capital_cost_does_not_reduce_fee_shares(self) -> None:
        """Capital provider cost is a reporting line only — bpi + bank must still == fee."""
        fee = _dec("500.00")
        capital = _dec("1000000")
        wf = compute_fee_waterfall(fee, DeploymentPhase.HYBRID, capital_deployed=capital)
        # Verify capital_cost > 0 (it was computed)
        assert wf.capital_provider_cost_usd > 0
        # Verify fee shares still sum to fee
        assert wf.bpi_share_usd + wf.bank_share_usd == fee

    def test_capital_cost_not_computed_for_phase1(self) -> None:
        """Phase 1 capital cost is $0 (bank bears all capital risk as licensor)."""
        wf = compute_fee_waterfall(_dec("500.00"), DeploymentPhase.LICENSOR, capital_deployed=_dec("1000000"))
        assert wf.capital_provider_cost_usd == _dec("0")

    def test_capital_cost_not_computed_when_omitted(self) -> None:
        wf = compute_fee_waterfall(_dec("500.00"), DeploymentPhase.HYBRID)
        assert wf.capital_provider_cost_usd == _dec("0")

    def test_deployment_phase_field_in_waterfall(self) -> None:
        wf = compute_fee_waterfall(_dec("300.00"), DeploymentPhase.HYBRID)
        assert wf.deployment_phase == "HYBRID"

    def test_returns_fee_waterfall_instance(self) -> None:
        wf = compute_fee_waterfall(_dec("100.00"), DeploymentPhase.LICENSOR)
        assert isinstance(wf, FeeWaterfall)
