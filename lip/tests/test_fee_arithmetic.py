"""
test_fee_arithmetic.py — QUANT verification of fee arithmetic
Architecture Spec C2 Section 9 / Appendix A

Critical invariants:
  - 300 bps annualized floor
  - fee = loan_amount * (fee_bps / 10000) * (days_funded / 365)
  - floor applied before per-cycle fee computation
  - fee_bps is ANNUALIZED, not flat per-cycle
"""
import pytest
from decimal import Decimal

from lip.c2_pd_model.fee import (
    compute_fee_bps_from_el,
    compute_loan_fee,
    verify_floor_applies,
    FEE_FLOOR_BPS,
    FEE_FLOOR_PER_7DAY_CYCLE,
)


class TestFeeFloor:
    """300 bps annualized floor enforcement."""

    def test_floor_is_300_bps(self):
        assert FEE_FLOOR_BPS == Decimal("300")

    def test_floor_per_7day_cycle_value(self):
        # 300/10000 * 7/365 ≈ 0.000575
        assert FEE_FLOOR_PER_7DAY_CYCLE == Decimal("0.000575")

    def test_low_pd_triggers_floor(self):
        """Low PD (0.001) * LGD 0.30 = 0.30 bps → floor applies → 300 bps."""
        fee_bps = compute_fee_bps_from_el(
            pd=Decimal("0.001"), lgd=Decimal("0.30"), ead=Decimal("100000")
        )
        assert fee_bps == FEE_FLOOR_BPS
        assert verify_floor_applies(fee_bps)

    def test_floor_applies_returns_true_at_floor(self):
        assert verify_floor_applies(Decimal("300")) is True

    def test_floor_applies_returns_false_above_floor(self):
        assert verify_floor_applies(Decimal("400")) is False


class TestFeeArithmeticQuant:
    """QUANT spot-check: 300 bps, 7-day, $100K → fee = $57.53."""

    def test_quant_spot_check_100k_7days_300bps(self):
        """
        QUANT verification:
          loan_amount = $100,000
          fee_bps     = 300 (annualized floor)
          days_funded = 7

          fee = 100_000 * (300 / 10_000) * (7 / 365)
              = 100_000 * 0.03 * 0.019178...
              = 100_000 * 0.000575342...
              ≈ $57.53
        """
        fee = compute_loan_fee(
            loan_amount=Decimal("100000"),
            fee_bps=Decimal("300"),
            days_funded=7,
        )
        # Must be $57.53 (rounded to nearest cent)
        assert fee == Decimal("57.53"), f"Expected $57.53, got ${fee}"

    def test_quant_1m_7days_300bps(self):
        """$1M, 7 days, 300 bps → $575.34."""
        fee = compute_loan_fee(
            loan_amount=Decimal("1000000"),
            fee_bps=Decimal("300"),
            days_funded=7,
        )
        assert fee == Decimal("575.34"), f"Expected $575.34, got ${fee}"

    def test_high_pd_exceeds_floor(self):
        """
        QUANT verification: PD=0.03, LGD=0.30 → fee_bps = 0.03 * 0.30 * 10000 = 90 bps
        But 90 < 300, so floor applies → 300 bps.
        """
        fee_bps = compute_fee_bps_from_el(
            pd=Decimal("0.03"), lgd=Decimal("0.30"), ead=Decimal("100000")
        )
        # 0.03 * 0.30 * 10000 = 90 bps → floor → 300
        assert fee_bps == Decimal("300")

    def test_very_high_pd_exceeds_floor(self):
        """
        QUANT verification: PD=0.50, LGD=0.93 → 0.50 * 0.93 * 10000 = 4650 bps ≥ 300.
        Uses approximately: PD=0.03, LGD=0.93 → 0.03*0.93*10000 = 279 bps → floor → 300.
        PD=0.50, LGD=0.93 → 4650 bps (well above floor).
        """
        fee_bps = compute_fee_bps_from_el(
            pd=Decimal("0.50"), lgd=Decimal("0.93"), ead=Decimal("100000")
        )
        assert fee_bps > Decimal("300")
        assert not verify_floor_applies(fee_bps)

    def test_approximate_4693_bps(self):
        """
        QUANT: PD=0.03, LGD=0.30 floor case already tested.
        Check a higher-PD case: PD=0.469, LGD=1.0 → ~4690 bps.
        """
        fee_bps = compute_fee_bps_from_el(
            pd=Decimal("0.469"), lgd=Decimal("1.0"), ead=Decimal("100000")
        )
        assert Decimal("4680") <= fee_bps <= Decimal("4700")


class TestFeeIsAnnualized:
    """fee_bps must be treated as an ANNUALIZED rate, not flat per-cycle."""

    def test_proportional_to_days(self):
        """Fee for 14 days is approximately 2x fee for 7 days (within 1 cent of rounding)."""
        fee_7 = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        fee_14 = compute_loan_fee(Decimal("100000"), Decimal("300"), 14)
        # Allow 1-cent rounding difference from Decimal ROUND_HALF_UP
        diff = abs(fee_14 - fee_7 * 2)
        assert diff <= Decimal("0.01"), f"fee_14={fee_14}, 2*fee_7={fee_7*2}"

    def test_proportional_to_amount(self):
        """Fee scales linearly with loan amount (within 1 cent of rounding)."""
        fee_100k = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        fee_200k = compute_loan_fee(Decimal("200000"), Decimal("300"), 7)
        diff = abs(fee_200k - fee_100k * 2)
        assert diff <= Decimal("0.01"), f"fee_200k={fee_200k}, 2*fee_100k={fee_100k*2}"

    def test_annualized_not_flat(self):
        """
        A flat per-cycle interpretation (fee = loan * fee_bps/10000) would give
        $3,000 for $100K at 300 bps. The correct annualized formula gives $57.53
        for a 7-day loan. Verify the annualized interpretation.
        """
        fee_correct = compute_loan_fee(Decimal("100000"), Decimal("300"), 7)
        fee_flat_incorrect = Decimal("100000") * Decimal("300") / Decimal("10000")
        assert fee_correct != fee_flat_incorrect
        assert fee_correct < fee_flat_incorrect  # $57.53 < $3,000

    def test_365_day_fee_equals_bps_percentage(self):
        """For a full year (365 days), fee = loan_amount * fee_bps/10000."""
        fee_365 = compute_loan_fee(Decimal("100000"), Decimal("300"), 365)
        expected = Decimal("100000") * Decimal("300") / Decimal("10000")
        assert fee_365 == expected.quantize(Decimal("0.01"))


class TestFeeEdgeCases:
    def test_zero_days_funded(self):
        fee = compute_loan_fee(Decimal("100000"), Decimal("300"), 0)
        assert fee == Decimal("0.00")

    def test_el_below_floor_always_returns_floor(self):
        """Any PD * LGD < 0.03 should yield the 300 bps floor."""
        for pd in ["0.001", "0.005", "0.01", "0.025"]:
            fee_bps = compute_fee_bps_from_el(
                pd=Decimal(pd), lgd=Decimal("0.10"), ead=Decimal("100000")
            )
            assert fee_bps == FEE_FLOOR_BPS, f"PD={pd}: expected floor, got {fee_bps}"
