"""
test_subday_fee_floor.py — Sub-day fee floor framework (Phase A).

Covers:
  - applicable_fee_floor_bps() returns 1200 bps for sub-day, 300 for day-scale.
  - compute_fee_bps_from_el() applies sub-day floor when maturity_hours < 48.
  - compute_loan_fee() enforces FEE_FLOOR_ABSOLUTE_USD.
  - is_subday_rail() boundary at SUBDAY_THRESHOLD_HOURS.
  - Existing 300 bps floor unchanged for legacy day-scale callers.
"""
from decimal import Decimal

from lip.c2_pd_model.fee import (
    applicable_fee_floor_bps,
    apply_absolute_fee_floor,
    compute_fee_bps_from_el,
    compute_loan_fee,
    is_subday_rail,
)
from lip.common.constants import (
    FEE_FLOOR_ABSOLUTE_USD,
    FEE_FLOOR_BPS,
    FEE_FLOOR_BPS_SUBDAY,
    SUBDAY_THRESHOLD_HOURS,
)


class TestApplicableFloor:

    def test_subday_4h_returns_1200(self):
        assert applicable_fee_floor_bps(4.0) == FEE_FLOOR_BPS_SUBDAY

    def test_subday_24h_returns_1200(self):
        assert applicable_fee_floor_bps(24.0) == FEE_FLOOR_BPS_SUBDAY

    def test_boundary_47h_is_subday(self):
        assert applicable_fee_floor_bps(47.999) == FEE_FLOOR_BPS_SUBDAY

    def test_boundary_48h_is_dayscale(self):
        assert applicable_fee_floor_bps(SUBDAY_THRESHOLD_HOURS) == FEE_FLOOR_BPS

    def test_dayscale_7d_returns_300(self):
        assert applicable_fee_floor_bps(7 * 24) == FEE_FLOOR_BPS

    def test_dayscale_45d_returns_300(self):
        assert applicable_fee_floor_bps(45 * 24) == FEE_FLOOR_BPS


class TestIsSubdayRail:

    def test_4h_is_subday(self):
        assert is_subday_rail(4.0) is True

    def test_24h_is_subday(self):
        assert is_subday_rail(24.0) is True

    def test_48h_is_not_subday(self):
        assert is_subday_rail(48.0) is False

    def test_72h_is_not_subday(self):
        assert is_subday_rail(72.0) is False


class TestFeeBpsWithMaturity:

    def test_subday_low_pd_floors_at_1200(self):
        # PD=0.001, LGD=0.45 -> raw EL = 4.5 bps. Sub-day floor must lift to 1200.
        result = compute_fee_bps_from_el(
            Decimal("0.001"), Decimal("0.45"), Decimal("1000000"),
            maturity_hours=4.0,
        )
        assert result == FEE_FLOOR_BPS_SUBDAY

    def test_dayscale_low_pd_floors_at_300(self):
        # Same PD/LGD, day-scale maturity — uses 300 bps floor (existing behaviour).
        result = compute_fee_bps_from_el(
            Decimal("0.001"), Decimal("0.45"), Decimal("1000000"),
            maturity_hours=7 * 24,
        )
        assert result == FEE_FLOOR_BPS

    def test_subday_high_pd_unchanged(self):
        # PD=0.30, LGD=0.45 -> 1350 bps. Above 1200 sub-day floor — no floor binding.
        result = compute_fee_bps_from_el(
            Decimal("0.30"), Decimal("0.45"), Decimal("1000000"),
            maturity_hours=4.0,
        )
        assert result == Decimal("1350.0")

    def test_default_maturity_is_dayscale(self):
        # Backward-compat: callers that don't pass maturity_hours get 300 floor.
        result = compute_fee_bps_from_el(
            Decimal("0.001"), Decimal("0.45"), Decimal("1000000"),
        )
        assert result == FEE_FLOOR_BPS


class TestAbsoluteFloor:
    """apply_absolute_fee_floor is the C7-side enforcement of $25 operational floor.

    compute_loan_fee preserves raw-math semantics (per-cycle formula); the
    absolute floor is applied separately at offer-construction time so test
    fixtures using zero/negative inputs don't get spuriously floored.
    """

    def test_tiny_loan_fee_floored_to_25(self):
        # $1000 * 1200 bps * (4h / 8760h) = ~$0.055 — below $25 absolute.
        raw = compute_loan_fee(
            Decimal("1000"),
            Decimal("1200"),
            Decimal("4") / Decimal("24"),  # 4h in days = 0.1667
        )
        assert raw < FEE_FLOOR_ABSOLUTE_USD
        assert apply_absolute_fee_floor(raw) == FEE_FLOOR_ABSOLUTE_USD

    def test_normal_loan_fee_above_floor(self):
        # $5M * 1200 bps * (4h / 8760h) = ~$273.97 — above $25.
        raw = compute_loan_fee(
            Decimal("5000000"),
            Decimal("1200"),
            Decimal("4") / Decimal("24"),
        )
        assert raw >= Decimal("273.00")
        assert raw <= Decimal("275.00")
        # Floor doesn't change a fee already above it.
        assert apply_absolute_fee_floor(raw) == raw

    def test_legacy_dayscale_unchanged(self):
        # $1M * 300 bps * 7 days = $575.34 — well above $25.
        fee = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        assert fee == Decimal("575.34")
        assert apply_absolute_fee_floor(fee) == fee

    def test_zero_fee_passes_through_unchanged(self):
        # Test fixtures and edge cases (zero principal etc.) must not be
        # spuriously floored — they're not real loans.
        assert apply_absolute_fee_floor(Decimal("0")) == Decimal("0")

    def test_negative_fee_passes_through_unchanged(self):
        assert apply_absolute_fee_floor(Decimal("-10")) == Decimal("-10")
