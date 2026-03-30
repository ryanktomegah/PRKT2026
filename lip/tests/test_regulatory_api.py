"""
test_regulatory_api.py — TDD tests for P10 Regulatory API.

Sprint 4c: HTTP REST endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations


class TestRateLimiter:
    """Token-bucket rate limiter tests."""

    def test_fresh_bucket_allows_request(self):
        """New key starts at full capacity — first request allowed."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, period_seconds=3600)
        assert limiter.check_and_consume("key-1") is True

    def test_exhaust_bucket_rejects(self):
        """After consuming all tokens, next request rejected."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=3, period_seconds=3600)
        for _ in range(3):
            assert limiter.check_and_consume("key-1") is True
        assert limiter.check_and_consume("key-1") is False

    def test_different_keys_independent(self):
        """Different keys have separate buckets."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=2, period_seconds=3600)
        limiter.check_and_consume("key-A")
        limiter.check_and_consume("key-A")
        assert limiter.check_and_consume("key-A") is False
        assert limiter.check_and_consume("key-B") is True

    def test_tokens_refill_after_period(self):
        """Tokens refill proportionally as time passes."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, period_seconds=10)
        for _ in range(10):
            limiter.check_and_consume("key-1")
        assert limiter.check_and_consume("key-1") is False
        with limiter._lock:
            tokens, last_refill = limiter._buckets["key-1"]
            limiter._buckets["key-1"] = (tokens, last_refill - 5.0)
        assert limiter.check_and_consume("key-1") is True

    def test_remaining_returns_correct_count(self):
        """remaining() reflects tokens left."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=5, period_seconds=3600)
        assert limiter.remaining("key-1") == 5
        limiter.check_and_consume("key-1")
        assert limiter.remaining("key-1") == 4


class TestRegulatoryService:
    """Service layer orchestration tests."""

    def _make_engine_with_data(self):
        """Create a SystemicRiskEngine with ingested test data."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        results = [
            AnonymizedCorridorResult(
                corridor="EUR-USD",
                period_label="2029-08-01T14:00Z",
                total_payments=500,
                failed_payments=25,
                failure_rate=0.05,
                bank_count=8,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
            AnonymizedCorridorResult(
                corridor="GBP-EUR",
                period_label="2029-08-01T14:00Z",
                total_payments=300,
                failed_payments=24,
                failure_rate=0.08,
                bank_count=6,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
            AnonymizedCorridorResult(
                corridor="USD-JPY",
                period_label="2029-08-01T14:00Z",
                total_payments=200,
                failed_payments=6,
                failure_rate=0.03,
                bank_count=3,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
        ]
        engine.ingest_results(results)
        return engine

    def test_get_corridor_snapshots_returns_snapshots_and_suppression(self):
        """Returns filtered snapshots + suppressed count."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        snapshots, suppressed = service.get_corridor_snapshots(min_bank_count=5)
        # EUR-USD (8 banks) and GBP-EUR (6 banks) pass; USD-JPY (3 banks) suppressed
        assert len(snapshots) == 2
        assert suppressed == 1

    def test_get_corridor_trend_delegates_to_engine(self):
        """Trend returns time-series from engine."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        trend = service.get_corridor_trend("EUR-USD", periods=10)
        assert len(trend) == 1
        assert trend[0].corridor == "EUR-USD"

    def test_get_concentration_corridor(self):
        """Corridor dimension returns HHI result."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        result = service.get_concentration(dimension="corridor")
        assert result.dimension == "corridor"
        assert result.hhi > 0.0

    def test_get_concentration_jurisdiction(self):
        """Jurisdiction dimension extracts from corridor names."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        result = service.get_concentration(dimension="jurisdiction")
        assert result.dimension == "jurisdiction"

    def test_simulate_contagion_returns_result(self):
        """Contagion simulation returns valid ContagionResult."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        result = service.simulate_contagion(
            shock_corridor="EUR-USD", shock_magnitude=0.8
        )
        assert result.origin_corridor == "EUR-USD"
        assert 0.0 <= result.systemic_risk_score <= 1.0

    def test_run_stress_test_returns_report_and_does_not_pollute(self):
        """Stress test produces a report and does not pollute engine history."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        baseline = engine.compute_risk_report()
        baseline_count = baseline.total_corridors_analyzed
        report_id, report = service.run_stress_test(
            scenario_name="test-scenario",
            shocks=[("EUR-USD", 0.9), ("GBP-EUR", 0.7)],
        )
        assert report.total_corridors_analyzed >= 1
        assert report_id is not None
        after = engine.compute_risk_report()
        assert after.total_corridors_analyzed == baseline_count

    def test_get_report_cached(self):
        """Cached report retrievable by ID."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        report_id, _ = service.run_stress_test("test", [("EUR-USD", 0.5)])
        cached = service.get_report(report_id)
        assert cached is not None
        assert cached.report_id == report_id

    def test_get_report_missing_returns_none(self):
        """Non-existent report returns None."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        assert service.get_report("nonexistent-id") is None

    def test_get_metadata_structure(self):
        """Metadata returns expected keys."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        meta = service.get_metadata()
        assert "api_version" in meta
        assert "methodology" in meta
        assert "data_freshness" in meta
        assert "rate_limit" in meta
