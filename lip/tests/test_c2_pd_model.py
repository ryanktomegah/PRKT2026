"""
test_c2_pd_model.py — Tests for C2 Unified PD Model
"""
from decimal import Decimal

from lip.c2_pd_model.baseline import altman_pd, altman_z_score, financial_ratio_pd, merton_pd
from lip.c2_pd_model.fee import FEE_FLOOR_BPS, compute_fee_bps_from_el, compute_loan_fee
from lip.c2_pd_model.lgd import estimate_lgd, lgd_for_corridor
from lip.c2_pd_model.tier_assignment import (
    Tier,
    TierFeatures,
    assign_tier,
    hash_borrower_id,
    tier_one_hot,
)


class TestTierAssignment:
    """Deterministic tier routing (C2 Spec Section 4)."""

    def test_tier1_full_data(self):
        feats = TierFeatures(
            has_financial_statements=True,
            has_transaction_history=True,
            has_credit_bureau=True,
            months_history=24,
            transaction_count=100,
        )
        assert assign_tier(feats) == Tier.TIER_1

    def test_tier2_transaction_history(self):
        feats = TierFeatures(
            has_financial_statements=False,
            has_transaction_history=True,
            has_credit_bureau=False,
            months_history=6,
            transaction_count=12,
        )
        assert assign_tier(feats) == Tier.TIER_2

    def test_tier3_thin_file(self):
        feats = TierFeatures(
            has_financial_statements=False,
            has_transaction_history=False,
            has_credit_bureau=False,
            months_history=0,
            transaction_count=0,
        )
        assert assign_tier(feats) == Tier.TIER_3

    def test_deterministic(self):
        """Same input always produces same tier."""
        feats = TierFeatures(True, True, True, 24, 100)
        results = {assign_tier(feats) for _ in range(5)}
        assert len(results) == 1

    def test_tier_one_hot_tier1(self):
        assert tier_one_hot(Tier.TIER_1) == [1, 0, 0]

    def test_tier_one_hot_tier2(self):
        assert tier_one_hot(Tier.TIER_2) == [0, 1, 0]

    def test_tier_one_hot_tier3(self):
        assert tier_one_hot(Tier.TIER_3) == [0, 0, 1]

    def test_hash_borrower_id_no_raw_id(self):
        """SHA-256 hash is hex string, not the original value."""
        salt = b"testsalt"
        result = hash_borrower_id("TAX123456", salt)
        assert "TAX123456" not in result
        assert len(result) == 64  # SHA-256 hex digest

    def test_hash_borrower_id_deterministic(self):
        salt = b"salt"
        r1 = hash_borrower_id("ABC", salt)
        r2 = hash_borrower_id("ABC", salt)
        assert r1 == r2

    def test_hash_borrower_id_different_salts_differ(self):
        r1 = hash_borrower_id("ABC", b"salt1")
        r2 = hash_borrower_id("ABC", b"salt2")
        assert r1 != r2


class TestLGD:
    def test_us_jurisdiction(self):
        lgd = estimate_lgd("US")
        assert lgd == Decimal("0.35")

    def test_eu_jurisdiction(self):
        lgd = estimate_lgd("EU")
        assert lgd == Decimal("0.30")

    def test_default_jurisdiction(self):
        lgd = estimate_lgd("UNKNOWN_COUNTRY")
        assert lgd == Decimal("0.45")

    def test_cash_collateral_reduces_lgd(self):
        base = estimate_lgd("US")
        with_collateral = estimate_lgd("US", collateral_type="CASH")
        assert with_collateral < base

    def test_lgd_floor_at_10_pct(self):
        """LGD cannot go below 0.10."""
        lgd = estimate_lgd("US", collateral_type="REAL_ESTATE",
                           collateral_value_pct=Decimal("0.50"))
        assert lgd >= Decimal("0.10")

    def test_corridor_lgd_is_max(self):
        us_lgd = estimate_lgd("US")
        mea_lgd = estimate_lgd("MEA")
        corridor = lgd_for_corridor("US", "MEA")
        assert corridor == max(us_lgd, mea_lgd)


class TestBaseline:
    def test_merton_pd_in_range(self):
        pd = merton_pd(
            asset_value=1_000_000,
            debt=800_000,
            asset_vol=0.25,
            risk_free=0.05,
        )
        assert 0.0 <= pd <= 1.0

    def test_altman_z_safe_zone(self):
        z = altman_z_score(
            working_capital=500_000,
            total_assets=1_000_000,
            retained_earnings=300_000,
            ebit=200_000,
            market_cap=600_000,
            total_liabilities=400_000,
            revenue=2_000_000,
        )
        assert z > 2.99
        assert altman_pd(z) == 0.05

    def test_altman_pd_distress_zone(self):
        pd = altman_pd(1.0)
        assert pd == 0.75

    def test_altman_pd_grey_zone(self):
        pd = altman_pd(2.5)
        assert 0.05 < pd < 0.75

    def test_ratio_pd_in_range(self):
        pd = financial_ratio_pd(
            current_ratio=1.5,
            debt_to_equity=1.0,
            interest_coverage=3.0,
        )
        assert 0.0 <= pd <= 1.0


class TestFeeFloor:
    """300 bps annualized floor — C2 Spec Section 9 / Basel III capital floor."""

    def test_floor_binds_when_el_below_300bps(self):
        """PD × LGD × 10000 = 10 bps < 300 bps floor — floor must apply."""
        fee = compute_fee_bps_from_el(
            pd=Decimal("0.001"),
            lgd=Decimal("0.10"),
            ead=Decimal("1000000"),
        )
        assert fee == Decimal("300.0"), f"Expected 300.0 bps floor, got {fee}"

    def test_floor_binds_at_zero_pd(self):
        """PD=0 is an extreme but valid case — floor must still apply."""
        fee = compute_fee_bps_from_el(
            pd=Decimal("0"),
            lgd=Decimal("0.45"),
            ead=Decimal("500000"),
        )
        assert fee == Decimal("300.0")

    def test_floor_binds_at_zero_lgd(self):
        """LGD=0 produces EL=0 bps — floor must still apply."""
        fee = compute_fee_bps_from_el(
            pd=Decimal("0.50"),
            lgd=Decimal("0"),
            ead=Decimal("1000000"),
        )
        assert fee == Decimal("300.0")

    def test_floor_not_binding_above_300bps(self):
        """PD=0.05, LGD=0.40 → EL=200 bps ... wait, 0.05*0.40*10000=200 < 300, floor binds."""
        # Use PD=0.10, LGD=0.40 → 400 bps > floor
        fee = compute_fee_bps_from_el(
            pd=Decimal("0.10"),
            lgd=Decimal("0.40"),
            ead=Decimal("1000000"),
        )
        assert fee == Decimal("400.0"), f"Expected 400.0 bps (no floor), got {fee}"
        assert not (fee == FEE_FLOOR_BPS), "Floor should not be binding at 400 bps"

    def test_verify_floor_applies_at_300(self):
        """verify_floor_applies() returns True at exactly 300 bps."""
        from lip.c2_pd_model.fee import verify_floor_applies
        assert verify_floor_applies(Decimal("300")) is True
        assert verify_floor_applies(Decimal("300.0")) is True

    def test_verify_floor_not_at_301(self):
        from lip.c2_pd_model.fee import verify_floor_applies
        assert verify_floor_applies(Decimal("301")) is False

    def test_compute_loan_fee_1m_300bps_7days(self):
        """Canonical example from spec docstring: $1M × 300 bps × 7/365 = $575.34."""
        fee = compute_loan_fee(
            loan_amount=Decimal("1000000"),
            fee_bps=Decimal("300"),
            days_funded=7,
        )
        assert fee == Decimal("575.34"), f"Expected $575.34, got ${fee}"

    def test_compute_loan_fee_scales_with_days(self):
        """21-day loan should be exactly 3× the 7-day loan at same rate."""
        fee_7d = compute_loan_fee(Decimal("1000000"), Decimal("300"), 7)
        fee_21d = compute_loan_fee(Decimal("1000000"), Decimal("300"), 21)
        ratio = fee_21d / fee_7d
        # Allow 1 cent rounding tolerance
        assert abs(ratio - Decimal("3")) < Decimal("0.01"), f"Ratio {ratio} != 3"

    def test_fee_floor_from_el_boundary_exactly_300bps(self):
        """PD × LGD = exactly 300 bps — floor is binding at boundary."""
        # PD=0.03, LGD=1.0 → 300 bps exactly
        fee = compute_fee_bps_from_el(
            pd=Decimal("0.03"),
            lgd=Decimal("1.00"),
            ead=Decimal("100000"),
        )
        assert fee == Decimal("300.0")
