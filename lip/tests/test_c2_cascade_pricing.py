"""
test_c2_cascade_pricing.py — TDD tests for C2 cascade-adjusted PD pricing.

QUANT domain: all fee arithmetic must be penny-exact Decimal.
Cascade discount capped at 30% (CASCADE_DISCOUNT_CAP).
Fee floor (300 bps) must NEVER be breached.
"""
from __future__ import annotations

from decimal import Decimal

from lip.c2_pd_model.fee import (
    CascadeAdjustedPricing,
    compute_cascade_adjusted_pd,
    compute_fee_bps_from_el,
)
from lip.common.constants import FEE_FLOOR_BPS
from lip.p5_cascade_engine.constants import CASCADE_DISCOUNT_CAP


class TestCascadeAdjustedPD:
    """QUANT-controlled cascade discount pricing."""

    def test_basic_discount(self):
        """Cascade discount reduces PD proportionally."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("50000000"),
            intervention_cost=Decimal("10000000"),
        )
        # discount = min(0.30, 50M / (10 * 10M)) = min(0.30, 0.5) = 0.30 (capped)
        assert result.cascade_discount == Decimal("0.30")
        assert result.cascade_adjusted_pd == Decimal("0.05") * (1 - Decimal("0.30"))

    def test_discount_capped_at_30pct(self):
        """Discount never exceeds CASCADE_DISCOUNT_CAP (30%)."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.10"),
            cascade_value_prevented=Decimal("100000000"),  # Very large
            intervention_cost=Decimal("1000000"),  # Small cost
        )
        # Uncapped: 100M / (10 * 1M) = 10.0 >> 0.30
        assert result.cascade_discount == CASCADE_DISCOUNT_CAP

    def test_small_cascade_small_discount(self):
        """Small cascade value = small discount (below cap)."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("1000000"),  # $1M
            intervention_cost=Decimal("10000000"),  # $10M
        )
        # discount = min(0.30, 1M / (10 * 10M)) = min(0.30, 0.01) = 0.01
        assert result.cascade_discount == Decimal("0.01")
        expected_pd = Decimal("0.05") * (1 - Decimal("0.01"))
        assert result.cascade_adjusted_pd == expected_pd

    def test_zero_cascade_no_discount(self):
        """Zero cascade value = zero discount."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("0"),
            intervention_cost=Decimal("10000000"),
        )
        assert result.cascade_discount == Decimal("0")
        assert result.cascade_adjusted_pd == Decimal("0.05")

    def test_fee_floor_preserved(self):
        """Adjusted fee never drops below 300 bps floor."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.02"),  # Low PD
            cascade_value_prevented=Decimal("50000000"),
            intervention_cost=Decimal("10000000"),
        )
        # Even with 30% discount, fee floor must hold
        assert result.cascade_adjusted_fee_bps >= FEE_FLOOR_BPS

    def test_base_fee_computed(self):
        """Base fee is computed from base_pd."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.10"),
            cascade_value_prevented=Decimal("0"),
            intervention_cost=Decimal("10000000"),
        )
        expected_base_fee = compute_fee_bps_from_el(
            Decimal("0.10"), Decimal("0.45"), Decimal("1000000")
        )
        assert result.base_fee_bps == expected_base_fee

    def test_return_type_is_dataclass(self):
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("10000000"),
            intervention_cost=Decimal("5000000"),
        )
        assert isinstance(result, CascadeAdjustedPricing)
        assert isinstance(result.cascade_adjusted_pd, Decimal)
        assert isinstance(result.cascade_adjusted_fee_bps, Decimal)

    def test_all_fields_populated(self):
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("10000000"),
            intervention_cost=Decimal("5000000"),
        )
        assert result.base_pd == Decimal("0.05")
        assert result.cascade_value_prevented == Decimal("10000000")
        assert result.intervention_cost == Decimal("5000000")

    def test_zero_intervention_cost_no_discount(self):
        """Division by zero guard: zero cost = zero discount."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.05"),
            cascade_value_prevented=Decimal("10000000"),
            intervention_cost=Decimal("0"),
        )
        assert result.cascade_discount == Decimal("0")
        assert result.cascade_adjusted_pd == Decimal("0.05")
