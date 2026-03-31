"""
test_regulatory_api.py — TDD tests for P10 Regulatory API.

Sprint 4c: HTTP REST endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations

import pytest


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
        report_id, vr = service.run_stress_test(
            scenario_name="test-scenario",
            shocks=[("EUR-USD", 0.9), ("GBP-EUR", 0.7)],
        )
        assert vr.report.total_corridors_analyzed >= 1
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


class TestRegulatoryRouter:
    """HTTP endpoint tests using FastAPI TestClient."""

    @pytest.fixture()
    def client(self):
        """Create a TestClient with regulatory router mounted."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results(
            [
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
            ]
        )
        service = RegulatoryService(risk_engine=engine)
        router = make_regulatory_router(service)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/regulatory")
        return TestClient(app)

    def test_get_corridors_200(self, client):
        """GET /corridors returns corridor list."""
        resp = client.get("/api/v1/regulatory/corridors")
        assert resp.status_code == 200
        data = resp.json()
        assert "corridors" in data
        assert data["total_corridors"] >= 1

    def test_get_corridors_empty_engine(self):
        """Empty engine returns empty corridor list."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

        engine = SystemicRiskEngine()
        service = RegulatoryService(risk_engine=engine)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(service), prefix="/api/v1/regulatory"
        )
        c = TestClient(app)
        resp = c.get("/api/v1/regulatory/corridors")
        assert resp.status_code == 200
        assert resp.json()["total_corridors"] == 0

    def test_get_corridor_trend_200(self, client):
        """GET /corridors/{id}/trend returns time-series."""
        resp = client.get("/api/v1/regulatory/corridors/EUR-USD/trend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["corridor_id"] == "EUR-USD"
        assert len(data["snapshots"]) >= 1

    def test_get_corridor_trend_unknown_returns_empty(self, client):
        """Unknown corridor returns empty trend (not 404)."""
        resp = client.get("/api/v1/regulatory/corridors/UNKNOWN-PAIR/trend")
        assert resp.status_code == 200
        assert resp.json()["total_periods"] == 0

    def test_get_concentration_200(self, client):
        """GET /concentration returns HHI result."""
        resp = client.get("/api/v1/regulatory/concentration")
        assert resp.status_code == 200
        data = resp.json()
        assert "hhi" in data
        assert data["dimension"] == "corridor"

    def test_get_concentration_jurisdiction(self, client):
        """GET /concentration?dimension=jurisdiction works."""
        resp = client.get(
            "/api/v1/regulatory/concentration?dimension=jurisdiction"
        )
        assert resp.status_code == 200
        assert resp.json()["dimension"] == "jurisdiction"

    def test_simulate_contagion_200(self, client):
        """GET /contagion/simulate returns simulation."""
        resp = client.get(
            "/api/v1/regulatory/contagion/simulate?shock_corridor=EUR-USD"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["origin_corridor"] == "EUR-USD"
        assert 0.0 <= data["systemic_risk_score"] <= 1.0

    def test_simulate_contagion_missing_param_422(self, client):
        """Missing required shock_corridor returns 422."""
        resp = client.get("/api/v1/regulatory/contagion/simulate")
        assert resp.status_code == 422

    def test_stress_test_200(self, client):
        """POST /stress-test returns report."""
        resp = client.post(
            "/api/v1/regulatory/stress-test",
            json={
                "scenario_name": "EU corridor shock",
                "shocks": [
                    {"corridor": "EUR-USD", "magnitude": 0.9},
                    {"corridor": "GBP-EUR", "magnitude": 0.7},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_name"] == "EU corridor shock"
        assert data["report_id"].startswith("RPT-")

    def test_stress_test_empty_shocks_422(self, client):
        """Empty shocks list returns 422."""
        resp = client.post(
            "/api/v1/regulatory/stress-test",
            json={"scenario_name": "empty", "shocks": []},
        )
        assert resp.status_code == 422

    def test_get_report_200(self, client):
        """GET /reports/{id} returns cached report."""
        create_resp = client.post(
            "/api/v1/regulatory/stress-test",
            json={
                "scenario_name": "test",
                "shocks": [{"corridor": "EUR-USD", "magnitude": 0.5}],
            },
        )
        report_id = create_resp.json()["report_id"]
        resp = client.get(f"/api/v1/regulatory/reports/{report_id}")
        assert resp.status_code == 200
        assert resp.json()["report_id"] == report_id

    def test_get_report_404(self, client):
        """Missing report returns 404."""
        resp = client.get("/api/v1/regulatory/reports/RPT-NONEXISTENT")
        assert resp.status_code == 404

    def test_get_metadata_200(self, client):
        """GET /metadata returns metadata."""
        resp = client.get("/api/v1/regulatory/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_version"] == "1.0.0"
        assert "methodology" in data

    def test_rate_limited_returns_429(self):
        """Rate-limited request returns 429."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.rate_limiter import TokenBucketRateLimiter
        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

        engine = SystemicRiskEngine()
        service = RegulatoryService(risk_engine=engine)
        limiter = TokenBucketRateLimiter(rate=2, period_seconds=3600)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(service, rate_limiter=limiter),
            prefix="/api/v1/regulatory",
        )
        c = TestClient(app)
        c.get("/api/v1/regulatory/metadata")
        c.get("/api/v1/regulatory/metadata")
        resp = c.get("/api/v1/regulatory/metadata")
        assert resp.status_code == 429


class TestIntegration:
    """Full pipeline integration tests."""

    def test_full_pipeline_ingest_to_api(self):
        """Ingest telemetry -> query API -> verify response matches."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results(
            [
                AnonymizedCorridorResult(
                    corridor="EUR-USD",
                    period_label="2029-08-01T14:00Z",
                    total_payments=1000,
                    failed_payments=100,
                    failure_rate=0.10,
                    bank_count=10,
                    k_anonymity_satisfied=True,
                    privacy_budget_remaining=4.5,
                    noise_applied=True,
                    stale=False,
                ),
            ]
        )
        service = RegulatoryService(risk_engine=engine)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(service), prefix="/api/v1/regulatory"
        )
        c = TestClient(app)
        resp = c.get("/api/v1/regulatory/corridors")
        data = resp.json()
        assert data["corridors"][0]["failure_rate"] == pytest.approx(0.10)

    def test_rate_limiter_wired_exhaustion_returns_429(self):
        """Exhausting rate limit via real HTTP calls returns 429."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.rate_limiter import TokenBucketRateLimiter
        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

        engine = SystemicRiskEngine()
        service = RegulatoryService(risk_engine=engine)
        limiter = TokenBucketRateLimiter(rate=5, period_seconds=3600)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(service, rate_limiter=limiter),
            prefix="/api/v1/regulatory",
        )
        c = TestClient(app)
        for _ in range(5):
            resp = c.get("/api/v1/regulatory/metadata")
            assert resp.status_code == 200
        resp = c.get("/api/v1/regulatory/metadata")
        assert resp.status_code == 429

    def test_app_mounts_regulatory_when_engine_provided(self):
        """create_app with systemic_risk_engine mounts /api/v1/regulatory."""
        import sys
        from unittest.mock import MagicMock, patch

        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

        fake_metrics = MagicMock()
        fake_metrics.generate_latest.return_value = ""

        # If lip.api.app hasn't been imported yet, the module-level
        # create_app() runs during import and hits duplicate Prometheus
        # metrics from other test files. Patch at the source to survive.
        if "lip.api.app" not in sys.modules:
            with patch(
                "lip.infrastructure.monitoring.metrics.PrometheusMetricsCollector",
                return_value=fake_metrics,
            ):
                import lip.api.app  # noqa: F401 — force safe import

        with patch("lip.api.app.PrometheusMetricsCollector", return_value=fake_metrics):
            from lip.api.app import create_app

            engine = SystemicRiskEngine()
            app = create_app(systemic_risk_engine=engine)

        routes = [r.path for r in app.routes]
        assert any("/api/v1/regulatory" in r for r in routes)
