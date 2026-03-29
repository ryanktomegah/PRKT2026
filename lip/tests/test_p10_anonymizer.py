"""
test_p10_anonymizer.py — TDD tests for P10 Anonymizer Foundation.

QUANT domain: Laplace mechanism correctness, variance, budget arithmetic.
CIPHER domain: k-anonymity enforcement, entity hashing integration.
Integration: Full 3-layer pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


class TestTelemetrySchema:
    """Structural tests for TelemetryBatch and CorridorStatistic dataclasses."""

    def test_corridor_statistic_construction(self):
        from lip.p10_regulatory_data.telemetry_schema import CorridorStatistic
        cs = CorridorStatistic(
            corridor="EUR-USD",
            total_payments=1247,
            failed_payments=23,
            failure_rate=23 / 1247,
            failure_class_distribution={"CLASS_A": 14, "CLASS_B": 6, "CLASS_C": 3, "BLOCK": 0},
            mean_settlement_hours=4.2,
            p95_settlement_hours=18.7,
            amount_bucket_distribution={"0-10K": 412, "10K-100K": 589, "100K-1M": 201, "1M-10M": 38, "10M+": 7},
            stress_regime_active=False,
            stress_ratio=1.2,
        )
        assert cs.corridor == "EUR-USD"
        assert cs.total_payments == 1247
        assert cs.failed_payments == 23

    def test_telemetry_batch_construction(self):
        from lip.p10_regulatory_data.telemetry_schema import TelemetryBatch
        now = datetime.now(tz=timezone.utc)
        batch = TelemetryBatch(
            batch_id="TB-001",
            bank_hash="a3f8c2d91e",
            period_start=now,
            period_end=now,
            corridor_statistics=[],
            hmac_signature="abc123",
        )
        assert batch.batch_id == "TB-001"
        assert batch.bank_hash == "a3f8c2d91e"

    def test_anonymized_corridor_result_construction(self):
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult
        result = AnonymizedCorridorResult(
            corridor="EUR-USD",
            period_label="2029-08-01T14:00Z",
            total_payments=1250,
            failed_payments=25,
            failure_rate=0.02,
            bank_count=7,
            k_anonymity_satisfied=True,
            privacy_budget_remaining=4.5,
            noise_applied=True,
            stale=False,
        )
        assert result.k_anonymity_satisfied is True
        assert result.noise_applied is True


class TestPrivacyBudget:
    """QUANT domain — privacy budget arithmetic must be exact."""

    def test_initial_budget_is_full(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        status = tracker.get_status("EUR-USD")
        assert status.budget_remaining == float(Decimal("5.0"))
        assert status.is_exhausted is False

    def test_deduct_reduces_budget(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        status = tracker.get_status("EUR-USD")
        assert status.budget_remaining == pytest.approx(4.5)
        assert status.queries_executed == 1

    def test_budget_exhaustion_at_exact_boundary(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        for _ in range(10):
            tracker.deduct("EUR-USD", Decimal("0.5"))
        status = tracker.get_status("EUR-USD")
        assert status.budget_remaining == pytest.approx(0.0)
        assert status.is_exhausted is True

    def test_deduct_beyond_budget_raises(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        for _ in range(10):
            tracker.deduct("EUR-USD", Decimal("0.5"))
        with pytest.raises(ValueError, match="exhausted"):
            tracker.deduct("EUR-USD", Decimal("0.5"))

    def test_independent_corridor_budgets(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        tracker.deduct("GBP-EUR", Decimal("1.0"))
        eur = tracker.get_status("EUR-USD")
        gbp = tracker.get_status("GBP-EUR")
        assert eur.budget_remaining == pytest.approx(4.5)
        assert gbp.budget_remaining == pytest.approx(4.0)

    def test_reset_restores_full_budget(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("5.0"))
        tracker.deduct("EUR-USD", Decimal("3.0"))
        tracker.reset_all()
        status = tracker.get_status("EUR-USD")
        assert status.budget_remaining == pytest.approx(5.0)
        assert status.queries_executed == 0

    def test_has_budget_returns_false_when_exhausted(self):
        from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("1.0"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        assert tracker.has_budget("EUR-USD", Decimal("0.5")) is True
        tracker.deduct("EUR-USD", Decimal("0.5"))
        assert tracker.has_budget("EUR-USD", Decimal("0.5")) is False
