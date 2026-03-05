"""
test_c2_pd_model.py — Tests for C2 Unified PD Model
"""
import pytest
import numpy as np
from decimal import Decimal

from lip.c2_pd_model.tier_assignment import (
    assign_tier, TierFeatures, Tier, tier_one_hot, hash_borrower_id
)
from lip.c2_pd_model.lgd import estimate_lgd, lgd_for_corridor
from lip.c2_pd_model.fee import compute_fee_bps_from_el, compute_loan_fee, FEE_FLOOR_BPS
from lip.c2_pd_model.baseline import merton_pd, altman_z_score, altman_pd, financial_ratio_pd


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
