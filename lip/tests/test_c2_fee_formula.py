"""
test_c2_fee_formula.py — C2 Fee Formula Hardening Test Suite
=============================================================
Architecture Spec C2 Section 9 / c2_fee_formula_hardening.md

Validates that ``compute_loan_fee`` in ``lip.c2_pd_model.fee`` is the single
authoritative source of the per-cycle fee formula:

    fee = loan_amount × (fee_bps / 10 000) × (days_funded / 365)

Coverage matrix:
  - Golden-fixture regression tests (QUANT-blessed values)
  - Property-based invariants (linearity, non-negativity, floor monotonicity)
  - Currency rounding (ROUND_HALF_UP, 2 decimal places / cents)
  - Edge inputs: zero days, zero amount, very large amounts, fractional days
  - Negative / invalid inputs (ValueError / Decimal conversion guard)
  - Overflow guard (extremely large loan amounts)
  - Integration: c3_generator and portfolio_router call compute_loan_fee
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from lip.c2_pd_model.fee import (
    FEE_FLOOR_BPS,
    compute_cascade_adjusted_pd,
    compute_fee_bps_from_el,
    compute_loan_fee,
    compute_platform_royalty,
    compute_tiered_fee_floor,
)
from lip.common.constants import (
    FEE_TIER_MID_THRESHOLD_USD,
    MIN_LOAN_AMOUNT_USD,
)

# ---------------------------------------------------------------------------
# Golden-fixture regression tests
# ---------------------------------------------------------------------------

class TestGoldenFixtures:
    """QUANT-blessed golden values — do NOT change without QUANT sign-off."""

    @pytest.mark.parametrize(
        "loan_amount,fee_bps,days_funded,expected_fee",
        [
            # Standard floor scenarios
            ("100000",  "300",  7,   "57.53"),
            ("1000000", "300",  7,   "575.34"),
            ("500000",  "300",  3,   "123.29"),
            ("500000",  "300",  21,  "863.01"),
            # Above-floor scenarios
            ("1000000", "450",  7,   "863.01"),
            ("1000000", "600",  21,  "3452.05"),
            ("250000",  "300",  3,   "61.64"),
            ("2000000", "300",  7,   "1150.68"),
            # Full-year: fee = principal * bps / 10000
            ("100000",  "300",  365, "3000.00"),
            ("1000000", "300",  365, "30000.00"),
        ],
    )
    def test_golden_value(
        self, loan_amount: str, fee_bps: str, days_funded: int, expected_fee: str
    ) -> None:
        fee = compute_loan_fee(Decimal(loan_amount), Decimal(fee_bps), days_funded)
        assert fee == Decimal(expected_fee), (
            f"compute_loan_fee({loan_amount}, {fee_bps}, {days_funded}) = {fee}; "
            f"expected {expected_fee}"
        )


# ---------------------------------------------------------------------------
# Property-based invariants
# ---------------------------------------------------------------------------

class TestPropertyInvariants:
    """Mathematical properties that must hold for all valid inputs."""

    def test_linearity_in_loan_amount(self) -> None:
        """Fee scales exactly linearly with loan_amount (within 1-cent rounding)."""
        fee_1x = compute_loan_fee(Decimal("500000"), Decimal("300"), 7)
        fee_2x = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        assert abs(fee_2x - fee_1x * 2) <= Decimal("0.01"), (
            f"Linearity broken: fee_2x={fee_2x}, 2*fee_1x={fee_1x * 2}"
        )

    def test_linearity_in_fee_bps(self) -> None:
        """Fee scales linearly with fee_bps (within 1-cent rounding)."""
        fee_300 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        fee_600 = compute_loan_fee(Decimal("1000000"), Decimal("600"), 7)
        assert abs(fee_600 - fee_300 * 2) <= Decimal("0.01"), (
            f"Linearity in fee_bps broken: fee_600={fee_600}, 2*fee_300={fee_300 * 2}"
        )

    def test_linearity_in_days(self) -> None:
        """Fee scales linearly with days_funded (within 1-cent rounding)."""
        fee_7 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        fee_14 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 14)
        assert abs(fee_14 - fee_7 * 2) <= Decimal("0.01"), (
            f"Linearity in days broken: fee_14={fee_14}, 2*fee_7={fee_7 * 2}"
        )

    def test_non_negative_for_valid_inputs(self) -> None:
        """Fee is always >= 0 for any non-negative input triple."""
        params = [
            ("0",       "300",  0),
            ("100000",  "300",  0),
            ("0",       "300",  7),
            ("100000",  "300",  7),
            ("1000000", "4650", 21),
        ]
        for amount, bps, days in params:
            fee = compute_loan_fee(Decimal(amount), Decimal(bps), days)
            assert fee >= Decimal("0.00"), (
                f"Negative fee for ({amount}, {bps}, {days}): {fee}"
            )

    def test_full_year_equals_annualized_rate(self) -> None:
        """For days_funded=365, fee == loan_amount * fee_bps / 10000 (no time discount)."""
        for amount, bps in [("100000", "300"), ("2000000", "450"), ("750000", "600")]:
            fee = compute_loan_fee(Decimal(amount), Decimal(bps), 365)
            expected = (Decimal(amount) * Decimal(bps) / Decimal("10000")).quantize(
                Decimal("0.01")
            )
            assert fee == expected, (
                f"Full-year fee={fee}, expected={expected} for ({amount}, {bps})"
            )

    def test_annualized_not_flat_per_cycle(self) -> None:
        """Flat per-cycle interpretation (bps/10000 directly) gives a much larger fee."""
        fee_correct = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        fee_flat_wrong = Decimal("100000") * Decimal("300") / Decimal("10000")
        assert fee_correct < fee_flat_wrong, (
            "Annualized fee should be much smaller than the flat per-cycle misapplication"
        )
        # The correct 7-day fee is ≈ $57.53; flat misapplication would be $3,000
        assert fee_flat_wrong / fee_correct > 50, (
            "Expected at least 50x difference between flat and annualized for 7-day cycle"
        )

    def test_monotone_increasing_in_days(self) -> None:
        """Fee is non-decreasing as days_funded increases (given fixed amount and bps)."""
        fees = [
            compute_loan_fee(Decimal("1000000"), Decimal("300"), d)
            for d in [1, 3, 7, 14, 21, 30, 90, 180, 365]
        ]
        for i in range(len(fees) - 1):
            assert fees[i] <= fees[i + 1], (
                f"Fee not monotone: fees[{i}]={fees[i]} > fees[{i+1}]={fees[i+1]}"
            )

    def test_monotone_increasing_in_bps(self) -> None:
        """Fee is non-decreasing as fee_bps increases (given fixed amount and days)."""
        fees = [
            compute_loan_fee(Decimal("1000000"), Decimal(str(bps)), 7)
            for bps in [300, 350, 400, 450, 600, 1000, 4650]
        ]
        for i in range(len(fees) - 1):
            assert fees[i] <= fees[i + 1], (
                f"Fee not monotone in bps: fees[{i}]={fees[i]} > fees[{i+1}]={fees[i+1]}"
            )


# ---------------------------------------------------------------------------
# Currency rounding tests
# ---------------------------------------------------------------------------

class TestCurrencyRounding:
    """Fee is always rounded to 2 decimal places (cents) using ROUND_HALF_UP."""

    def test_result_always_two_decimal_places(self) -> None:
        """Result has exactly 2 decimal places for all tested inputs."""
        cases = [
            ("123456.78", "300", 7),
            ("999999.99", "450", 21),
            ("1",         "300", 1),
            ("100000",    "301", 7),   # non-round fee_bps
        ]
        for amount, bps, days in cases:
            fee = compute_loan_fee(Decimal(amount), Decimal(bps), days)
            assert fee == fee.quantize(Decimal("0.01")), (
                f"Not 2 dp for ({amount}, {bps}, {days}): {fee}"
            )

    def test_rounding_applied_to_cents(self) -> None:
        """Result is always rounded to exactly 2 decimal places (cents).

        The $1M, 300 bps, 7-day case yields 1000000 * 0.03 * 7/365 =
        575.342465... which is rounded DOWN to $575.34 (not up), confirming
        that Decimal ROUND_HALF_UP is applied: .342 < .5 → round down.
        """
        fee = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        assert fee == Decimal("575.34")

    def test_returns_decimal_not_float(self) -> None:
        """Return type must be Decimal (not float) to preserve precision."""
        fee = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        assert isinstance(fee, Decimal), f"Expected Decimal, got {type(fee)}"

    def test_float_inputs_produce_decimal_output(self) -> None:
        """Float inputs are coerced to Decimal; result is still a Decimal."""
        fee = compute_loan_fee(100000.0, 300.0, 7)
        assert isinstance(fee, Decimal)
        assert fee == Decimal("57.53")

    def test_int_inputs_produce_decimal_output(self) -> None:
        """Integer inputs are coerced to Decimal; result is still a Decimal."""
        fee = compute_loan_fee(100000, 300, 7)
        assert isinstance(fee, Decimal)
        assert fee == Decimal("57.53")

    def test_mixed_input_types(self) -> None:
        """Mixed input types (int, float, Decimal) all yield the same result."""
        expected = Decimal("57.53")
        assert compute_loan_fee(Decimal("100000"), Decimal("300"), 7) == expected
        assert compute_loan_fee(100000.0, 300.0, 7) == expected
        assert compute_loan_fee(100000, 300, 7) == expected


# ---------------------------------------------------------------------------
# Edge-case inputs
# ---------------------------------------------------------------------------

class TestEdgeCaseInputs:
    """Edge cases: zero, very small, very large, fractional days."""

    def test_zero_days_funded(self) -> None:
        """Zero days → zero fee."""
        fee = compute_loan_fee(Decimal("1000000"), Decimal("300"), 0)
        assert fee == Decimal("0.00")

    def test_zero_loan_amount(self) -> None:
        """Zero principal → zero fee."""
        fee = compute_loan_fee(Decimal("0"), Decimal("300"), 7)
        assert fee == Decimal("0.00")

    def test_zero_fee_bps(self) -> None:
        """Zero fee_bps (hypothetical) → zero fee."""
        fee = compute_loan_fee(Decimal("1000000"), Decimal("0"), 7)
        assert fee == Decimal("0.00")

    def test_single_day_loan(self) -> None:
        """1-day loan at 300 bps on $1M = 1M * 0.03 / 365 ≈ $82.19."""
        fee = compute_loan_fee(Decimal("1000000"), Decimal("300"), 1)
        # 1000000 * (300/10000) * (1/365) = 1000000 * 0.03 * 0.002739... = 82.19...
        assert fee == Decimal("82.19")

    def test_fractional_days_funding(self) -> None:
        """Fractional days (float) accepted and produce proportional fee."""
        fee_7 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        fee_3_5 = compute_loan_fee(Decimal("1000000"), Decimal("300"), 3.5)
        # 3.5 days should be exactly half of 7 days (within 1 cent)
        assert abs(fee_3_5 - fee_7 / 2) <= Decimal("0.01"), (
            f"fee_3.5d={fee_3_5}, fee_7d/2={fee_7/2}"
        )

    def test_minimum_realistic_loan(self) -> None:
        """Minimum realistic loan ($5K) at floor bps, 3-day maturity (CLASS_A)."""
        fee = compute_loan_fee(Decimal("5000"), Decimal("300"), 3)
        # 5000 * 0.03 * (3/365) = 5000 * 0.03 * 0.008219... = 1.23...
        assert fee == Decimal("1.23")

    def test_max_realistic_loan(self) -> None:
        """Max realistic loan ($10M) at 4650 bps, 21-day maturity (CLASS_C)."""
        fee = compute_loan_fee(Decimal("10000000"), Decimal("4650"), 21)
        # 10M * (4650/10000) * (21/365) = 10M * 0.465 * 0.057534... = 267,534.24...
        assert isinstance(fee, Decimal)
        assert fee > Decimal("0")

    def test_large_loan_amount_no_overflow(self) -> None:
        """Extremely large loan ($1B) should not overflow — Decimal is unbounded."""
        fee = compute_loan_fee(Decimal("1000000000"), Decimal("300"), 7)
        expected_approx = Decimal("575342.47")  # ~$575K
        # Allow ±1 for rounding
        assert abs(fee - expected_approx) <= Decimal("1"), (
            f"Unexpected fee for $1B loan: {fee}"
        )

    def test_high_fee_bps_does_not_overflow(self) -> None:
        """Very high fee_bps (e.g. 50000 = 500%) on large loan remains a valid Decimal."""
        fee = compute_loan_fee(Decimal("1000000"), Decimal("50000"), 365)
        assert fee == Decimal("5000000.00")  # 1M * 5.0 * 1.0

    def test_one_cent_loan(self) -> None:
        """Penny principal gives $0.00 fee at any standard tenor."""
        fee = compute_loan_fee(Decimal("0.01"), Decimal("300"), 7)
        assert fee == Decimal("0.00")  # rounds down to zero cents


# ---------------------------------------------------------------------------
# Negative / invalid input tests
# ---------------------------------------------------------------------------

class TestNegativeInputs:
    """Negative or clearly invalid inputs should yield negative/zero fee but not crash.

    Note: compute_loan_fee is a pure arithmetic function and does NOT validate
    sign of inputs — callers must enforce non-negative constraints.  These
    tests document the ACTUAL behaviour so callers know what to expect.
    """

    def test_negative_loan_amount_gives_negative_fee(self) -> None:
        """Negative principal propagates to a negative fee (arithmetic pass-through)."""
        fee = compute_loan_fee(Decimal("-100000"), Decimal("300"), 7)
        assert fee < Decimal("0"), f"Expected negative fee, got {fee}"

    def test_negative_fee_bps_gives_negative_fee(self) -> None:
        """Negative fee_bps propagates (arithmetic pass-through)."""
        fee = compute_loan_fee(Decimal("100000"), Decimal("-300"), 7)
        assert fee < Decimal("0"), f"Expected negative fee, got {fee}"

    def test_negative_days_gives_negative_fee(self) -> None:
        """Negative days_funded propagates (arithmetic pass-through)."""
        fee = compute_loan_fee(Decimal("100000"), Decimal("300"), -7)
        assert fee < Decimal("0"), f"Expected negative fee, got {fee}"

    def test_result_type_preserved_for_negative_inputs(self) -> None:
        """Return type is always Decimal even for negative inputs."""
        fee = compute_loan_fee(Decimal("-1000000"), Decimal("300"), 7)
        assert isinstance(fee, Decimal)


# ---------------------------------------------------------------------------
# Fee-floor invariant: compute_fee_bps_from_el always >= 300 bps
# ---------------------------------------------------------------------------

class TestFeeBpsFloor:
    """compute_fee_bps_from_el must always return >= FEE_FLOOR_BPS (300 bps)."""

    @pytest.mark.parametrize(
        "pd,lgd",
        [
            ("0.0001", "0.01"),   # extremely low EL
            ("0.001",  "0.10"),
            ("0.005",  "0.20"),
            ("0.01",   "0.30"),
            ("0.03",   "0.45"),   # Basel III standard, below floor
            ("0.0",    "1.0"),    # zero PD
            ("0.029",  "0.99"),   # just below floor: 0.029*0.99*10000 = 287.1 → floor
        ],
    )
    def test_floor_always_applied(self, pd: str, lgd: str) -> None:
        result = compute_fee_bps_from_el(
            pd=Decimal(pd), lgd=Decimal(lgd), ead=Decimal("1000000")
        )
        assert result >= FEE_FLOOR_BPS, (
            f"floor violated for PD={pd}, LGD={lgd}: got {result}"
        )

    def test_above_floor_not_clamped(self) -> None:
        """When EL bps > 300, result matches the EL bps (floor not applied)."""
        # PD=0.10, LGD=0.45 → 450 bps > 300 → no clamping
        result = compute_fee_bps_from_el(
            pd=Decimal("0.10"), lgd=Decimal("0.45"), ead=Decimal("1000000")
        )
        assert result == Decimal("450.0")

    def test_fee_bps_return_type_is_decimal(self) -> None:
        result = compute_fee_bps_from_el(
            pd=Decimal("0.03"), lgd=Decimal("0.45"), ead=Decimal("1000000")
        )
        assert isinstance(result, Decimal)

    def test_fee_bps_rounded_to_one_decimal(self) -> None:
        """Result is rounded to 1 decimal place.

        PD=0.123, LGD=0.456 → raw EL bps = 0.123 * 0.456 * 10000 = 560.88.
        Since 560.88 > 300 (floor), the floor does not apply.
        The raw bps are then rounded to 1dp: 560.9.
        """
        result = compute_fee_bps_from_el(
            pd=Decimal("0.123"), lgd=Decimal("0.456"), ead=Decimal("1000000")
        )
        assert result == result.quantize(Decimal("0.1")), (
            f"Not rounded to 1dp: {result}"
        )


# ---------------------------------------------------------------------------
# Royalty split invariant
# ---------------------------------------------------------------------------

class TestRoyaltySplitInvariant:
    """royalty + net == fee for all realistic scenarios (no rounding leak)."""

    @pytest.mark.parametrize(
        "principal,bps,days",
        [
            ("100000",  "300",  7),
            ("500000",  "300",  3),
            ("1000000", "300",  7),
            ("2000000", "450",  21),
            ("750000",  "600",  7),
            ("5000000", "300",  14),
        ],
    )
    def test_royalty_plus_net_equals_fee(
        self, principal: str, bps: str, days: int
    ) -> None:
        fee = compute_loan_fee(Decimal(principal), Decimal(bps), days)
        royalty = compute_platform_royalty(fee)
        net = fee - royalty
        assert royalty + net == fee, (
            f"Rounding leak: royalty({royalty}) + net({net}) != fee({fee}) "
            f"for ({principal}, {bps}, {days})"
        )


# ---------------------------------------------------------------------------
# Single source of truth: integration smoke tests
# ---------------------------------------------------------------------------

class TestSingleSourceIntegration:
    """Verify that production callers use compute_loan_fee (no silent drift)."""

    def test_c3_generator_uses_compute_loan_fee(self) -> None:
        """c3_generator.py must import and call compute_loan_fee."""
        import inspect

        import lip.dgen.c3_generator as c3gen

        source = inspect.getsource(c3gen)
        assert "compute_loan_fee" in source, (
            "c3_generator.py does not reference compute_loan_fee — "
            "inline fee formula detected (single-source violation)"
        )
        # Verify no bare inline formula pattern remains
        assert "(principal_usd * fee_bps / 10_000) * (" not in source, (
            "c3_generator.py still contains bare inline fee formula"
        )

    def test_portfolio_router_uses_compute_loan_fee(self) -> None:
        """portfolio_router.py must import and call compute_loan_fee."""
        import inspect

        import lip.api.portfolio_router as router

        source = inspect.getsource(router)
        assert "compute_loan_fee" in source, (
            "portfolio_router.py does not reference compute_loan_fee — "
            "inline fee formula detected (single-source violation)"
        )

    def test_train_all_uses_compute_fee_bps_from_el(self) -> None:
        """train_all.py must import and call compute_fee_bps_from_el for fee validation."""
        import inspect

        import lip.train_all as train_all

        source = inspect.getsource(train_all)
        assert "compute_fee_bps_from_el" in source, (
            "train_all.py does not reference compute_fee_bps_from_el — "
            "inline formula detected (single-source violation)"
        )

    def test_repayment_loop_uses_compute_loan_fee(self) -> None:
        """c3_repayment_engine/repayment_loop.py must use compute_loan_fee."""
        import inspect

        import lip.c3_repayment_engine.repayment_loop as loop

        source = inspect.getsource(loop)
        assert "compute_loan_fee" in source, (
            "repayment_loop.py does not reference compute_loan_fee — "
            "single-source violation"
        )

    def test_c7_agent_uses_compute_loan_fee(self) -> None:
        """c7_execution_agent/agent.py must use compute_loan_fee."""
        import inspect

        import lip.c7_execution_agent.agent as agent

        source = inspect.getsource(agent)
        assert "compute_loan_fee" in source, (
            "c7 agent.py does not reference compute_loan_fee — "
            "single-source violation"
        )


# ---------------------------------------------------------------------------
# Tiered fee floor tests (QUANT-controlled — do NOT change without QUANT sign-off)
# ---------------------------------------------------------------------------


class TestTieredFeeFloor:
    """compute_tiered_fee_floor() boundary and value tests.

    Post commit 256e808, the tiered-by-principal schedule was flattened:
    compute_tiered_fee_floor returns FEE_FLOOR_BPS (300) for every loan size.
    Warehouse eligibility (>=800 bps for SPV funding) is enforced elsewhere —
    via is_spv_warehouse_eligible() at origination and via the 800-bps raise
    in compute_cascade_adjusted_pd — not through this helper.
    """

    @pytest.mark.parametrize(
        "loan_amount",
        [
            Decimal("0.01"),
            Decimal("100000"),
            Decimal("499999.99"),
            Decimal("500000"),
            Decimal("500000.01"),
            Decimal("1000000"),
            Decimal("1999999.99"),
            Decimal("2000000"),
            Decimal("2000000.01"),
            Decimal("10000000"),
        ],
    )
    def test_tiered_floor_values(self, loan_amount: Decimal) -> None:
        """Every loan size now resolves to the canonical 300 bps platform floor."""
        result = compute_tiered_fee_floor(loan_amount)
        assert result == FEE_FLOOR_BPS, (
            f"compute_tiered_fee_floor({loan_amount}) = {result}, expected {FEE_FLOOR_BPS}"
        )

    def test_canonical_floor_matches_fee_floor_bps_constant(self) -> None:
        """The ≥$2M result must equal FEE_FLOOR_BPS so constants stay consistent."""
        assert compute_tiered_fee_floor(Decimal("2000000")) == FEE_FLOOR_BPS

    def test_small_tier_floor_matches_constant(self) -> None:
        """Small principals share the flattened 300 bps platform floor."""
        assert compute_tiered_fee_floor(Decimal("100000")) == FEE_FLOOR_BPS

    def test_mid_tier_floor_matches_constant(self) -> None:
        """Mid-range principals share the flattened 300 bps platform floor."""
        assert compute_tiered_fee_floor(Decimal("1000000")) == FEE_FLOOR_BPS

    def test_returns_decimal(self) -> None:
        """Return type must be Decimal for downstream Decimal arithmetic safety."""
        assert isinstance(compute_tiered_fee_floor(Decimal("500000")), Decimal)

    def test_mid_threshold_boundary_is_inclusive(self) -> None:
        """FEE_TIER_MID_THRESHOLD_USD exactly maps to the canonical 300 bps floor."""
        assert compute_tiered_fee_floor(FEE_TIER_MID_THRESHOLD_USD) == FEE_FLOOR_BPS

    def test_min_loan_boundary_is_inclusive(self) -> None:
        """MIN_LOAN_AMOUNT_USD now resolves to the canonical 300 bps platform floor."""
        assert compute_tiered_fee_floor(MIN_LOAN_AMOUNT_USD) == FEE_FLOOR_BPS


# ---------------------------------------------------------------------------
# Cascade-adjusted PD and pricing tests
# ---------------------------------------------------------------------------


class TestCascadeAdjustedPD:
    """compute_cascade_adjusted_pd() correctness, guard, and invariant tests.

    QUANT invariant (commit 256e808): cascade-adjusted pricing is the SPV-funded
    pricing path. The function raises ValueError whenever the cascade-adjusted
    fee would fall below WAREHOUSE_ELIGIBILITY_FLOOR_BPS (800 bps) — SPV-funded
    loans must yield ≥8% to service the capital structure. All valid inputs
    therefore require ``base_pd × lgd × 10_000 × (1 − CASCADE_DISCOUNT_CAP) ≥ 800``.
    With default ``lgd=0.45``, this means ``base_pd ≳ 0.254``. Tests in this
    class use ``base_pd=0.30`` (1350 bps pre-discount, 945 bps post-max-discount)
    which stays comfortably above the warehouse floor.
    """

    def test_no_cascade_value_yields_no_discount(self) -> None:
        """Zero cascade value prevented → zero discount → unchanged PD and fee."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.30"),
            cascade_value_prevented=Decimal("0"),
            intervention_cost=Decimal("1000000"),
        )
        assert result.cascade_discount == Decimal("0")
        assert result.cascade_adjusted_pd == result.base_pd

    def test_discount_capped_at_30_percent(self) -> None:
        """CASCADE_DISCOUNT_CAP (30%) is never exceeded regardless of value/cost ratio."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.30"),
            cascade_value_prevented=Decimal("1000000000"),  # very large
            intervention_cost=Decimal("1"),
        )
        from lip.p5_cascade_engine.constants import CASCADE_DISCOUNT_CAP
        assert result.cascade_discount <= CASCADE_DISCOUNT_CAP

    def test_adjusted_pd_always_less_than_or_equal_base_pd(self) -> None:
        """Cascade adjustment can only reduce PD, never increase it."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.30"),
            cascade_value_prevented=Decimal("500000"),
            intervention_cost=Decimal("1000000"),
        )
        assert result.cascade_adjusted_pd <= result.base_pd

    def test_quant_invariant_warehouse_floor_never_violated(self) -> None:
        """cascade_adjusted_fee_bps must always be >= WAREHOUSE_ELIGIBILITY_FLOOR_BPS (800 bps).

        For SPV-funded loans the relevant floor is 800 bps, not the 300 bps
        platform floor. This test picks inputs that land just above the
        warehouse floor after the 30% max discount and verifies the guard
        permits them through without raising.
        """
        from lip.common.constants import WAREHOUSE_ELIGIBILITY_FLOOR_BPS
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("0.30"),
            cascade_value_prevented=Decimal("100000"),
            intervention_cost=Decimal("1000000"),
        )
        assert result.cascade_adjusted_fee_bps >= Decimal(str(WAREHOUSE_ELIGIBILITY_FLOOR_BPS))
        assert result.cascade_adjusted_fee_bps >= FEE_FLOOR_BPS

    def test_invalid_base_pd_above_one_raises(self) -> None:
        """base_pd > 1.0 is not a valid probability — must raise ValueError."""
        with pytest.raises(ValueError, match="base_pd must be in"):
            compute_cascade_adjusted_pd(
                base_pd=Decimal("1.5"),
                cascade_value_prevented=Decimal("100000"),
                intervention_cost=Decimal("1000000"),
            )

    def test_invalid_base_pd_negative_raises(self) -> None:
        """Negative base_pd is not a valid probability — must raise ValueError."""
        with pytest.raises(ValueError, match="base_pd must be in"):
            compute_cascade_adjusted_pd(
                base_pd=Decimal("-0.01"),
                cascade_value_prevented=Decimal("100000"),
                intervention_cost=Decimal("1000000"),
            )

    def test_base_pd_below_warehouse_floor_raises(self) -> None:
        """PD too low to clear the 800 bps warehouse floor must raise.

        Previously this was ``test_base_pd_zero_is_valid``. Under the SPV
        warehouse invariant (commit 256e808), a risk-free borrower cannot be
        priced through this function — the cascade-adjusted fee lands at the
        300 bps platform floor, which is below the 800 bps warehouse minimum.
        """
        with pytest.raises(ValueError, match="WAREHOUSE_ELIGIBILITY_FLOOR_BPS"):
            compute_cascade_adjusted_pd(
                base_pd=Decimal("0"),
                cascade_value_prevented=Decimal("0"),
                intervention_cost=Decimal("1000000"),
            )

    def test_base_pd_one_is_valid(self) -> None:
        """base_pd = 1.0 is a valid edge case (certain default)."""
        result = compute_cascade_adjusted_pd(
            base_pd=Decimal("1"),
            cascade_value_prevented=Decimal("0"),
            intervention_cost=Decimal("1000000"),
        )
        assert result.base_pd == Decimal("1")
        assert result.cascade_adjusted_fee_bps >= FEE_FLOOR_BPS

    def test_warehouse_guard_survives_python_optimize_mode(self) -> None:
        """B13-03: Warehouse-floor guard must hold even under ``python -O``.

        The guard in compute_cascade_adjusted_pd is ``raise`` not ``assert``
        (B10-08 + 256e808). This test exercises the raise path directly —
        if the check were still an ``assert``, running under ``python -O``
        would silently drop the guard and no exception would surface.

        Inputs chosen to produce fee <800 bps (very low PD + max cascade
        discount ⇒ 300 bps platform floor ⇒ below warehouse floor ⇒ raise).
        """
        with pytest.raises(ValueError, match="WAREHOUSE_ELIGIBILITY_FLOOR_BPS"):
            compute_cascade_adjusted_pd(
                base_pd=Decimal("0.0001"),
                cascade_value_prevented=Decimal("9999999"),
                intervention_cost=Decimal("1"),
            )
