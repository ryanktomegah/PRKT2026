"""Load tests for P10 Regulatory API — 100 concurrent queries (Sprint 8)."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.shadow_data import generate_shadow_events
from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lip.api.rate_limiter import TokenBucketRateLimiter
    from lip.api.regulatory_router import make_regulatory_router
    from lip.api.regulatory_service import RegulatoryService
    from lip.c8_license_manager.query_metering import RegulatoryQueryMetering
    from lip.c8_license_manager.regulator_subscription import (
        RegulatorSubscriptionToken,
        encode_regulator_token,
        sign_regulator_token,
    )

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")

_SALT = b"load_test_salt__32bytes_________"
_SIGNING_KEY = b"load_test_signing_key___________"


def _make_test_app(rate_limit_per_hour: int = 10000):
    """Build a fully-wired FastAPI test app with seeded data."""
    events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
    anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=42)
    engine = SystemicRiskEngine()
    runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anon, risk_engine=engine)
    runner.run(events)

    service = RegulatoryService(risk_engine=engine)
    limiter = TokenBucketRateLimiter(rate=rate_limit_per_hour, period_seconds=3600)
    metering = RegulatoryQueryMetering(metering_key=_SIGNING_KEY)

    router = make_regulatory_router(
        regulatory_service=service,
        rate_limiter=limiter,
        regulator_signing_key=_SIGNING_KEY,
        query_metering=metering,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/regulatory")
    return app, metering


def _make_token(
    regulator_id: str = "OSFI-001",
    tier: str = "REALTIME",
    corridors: list[str] | None = None,
) -> str:
    token = RegulatorSubscriptionToken(
        regulator_id=regulator_id,
        regulator_name=f"Test Regulator {regulator_id}",
        subscription_tier=tier,
        permitted_corridors=corridors,
        query_budget_monthly=10000,
        privacy_budget_allocation=100.0,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    signed = sign_regulator_token(token, _SIGNING_KEY)
    return encode_regulator_token(signed)


class TestConcurrentCorridorQueries:
    """100 concurrent GET /corridors requests."""

    def test_100_concurrent_corridor_queries(self):
        app, _ = _make_test_app()
        client = TestClient(app)
        token = _make_token()
        results: list[tuple[int, float]] = []
        errors: list[str] = []

        def _query():
            try:
                t0 = time.perf_counter()
                resp = client.get(
                    "/api/v1/regulatory/corridors",
                    headers={"Authorization": f"Bearer {token}"},
                )
                latency = (time.perf_counter() - t0) * 1000
                results.append((resp.status_code, latency))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_query) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors[:5]}"
        statuses = [r[0] for r in results]
        assert all(s == 200 for s in statuses)

    def test_response_time_corridor_under_load(self):
        app, _ = _make_test_app()
        client = TestClient(app)
        token = _make_token()
        latencies: list[float] = []

        def _query():
            t0 = time.perf_counter()
            client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token}"},
            )
            latencies.append((time.perf_counter() - t0) * 1000)

        threads = [threading.Thread(target=_query) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        assert p95 < 500, f"p95 latency {p95:.0f}ms exceeds 500ms target"


class TestMixedEndpointLoad:
    """100 concurrent requests across endpoint types."""

    def test_100_concurrent_mixed_endpoints(self):
        app, _ = _make_test_app()
        client = TestClient(app)
        token = _make_token()
        results: list[int] = []

        endpoints = [
            "/api/v1/regulatory/corridors",
            "/api/v1/regulatory/concentration",
            "/api/v1/regulatory/metadata",
        ]

        def _query(path: str):
            resp = client.get(path, headers={"Authorization": f"Bearer {token}"})
            results.append(resp.status_code)

        threads = []
        for i in range(100):
            path = endpoints[i % len(endpoints)]
            threads.append(threading.Thread(target=_query, args=(path,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(results) == 100
        assert all(s == 200 for s in results)


class TestRateLimiterUnderLoad:
    """Rate limiter correctness under concurrent access."""

    def test_rate_limiter_under_load(self):
        app, _ = _make_test_app(rate_limit_per_hour=50)
        client = TestClient(app)
        token = _make_token()
        results: list[int] = []

        def _query():
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token}"},
            )
            results.append(resp.status_code)

        threads = [threading.Thread(target=_query) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        ok_count = sum(1 for s in results if s == 200)
        rate_limited = sum(1 for s in results if s == 429)
        assert ok_count <= 51, f"Expected <=51 OK, got {ok_count}"
        assert rate_limited > 0, "Expected some 429 responses"


class TestBudgetUnderConcurrency:
    """Budget enforcement with concurrent requests."""

    def test_budget_enforcement_under_concurrency(self):
        app, metering = _make_test_app()
        client = TestClient(app)
        token = _make_token(regulator_id="BUDGET-TEST")
        results: list[int] = []

        def _query():
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token}"},
            )
            results.append(resp.status_code)

        threads = [threading.Thread(target=_query) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        summary = metering.get_billing_summary("BUDGET-TEST")
        assert summary["query_count"] <= 50

    def test_privacy_budget_isolation_under_load(self):
        """Different regulators' budgets don't cross-contaminate."""
        app, metering = _make_test_app()
        client = TestClient(app)
        token_a = _make_token(regulator_id="REG-A")
        token_b = _make_token(regulator_id="REG-B")
        results_a: list[int] = []
        results_b: list[int] = []

        def _query_a():
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            results_a.append(resp.status_code)

        def _query_b():
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            results_b.append(resp.status_code)

        threads = []
        for _ in range(25):
            threads.append(threading.Thread(target=_query_a))
            threads.append(threading.Thread(target=_query_b))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        summary_a = metering.get_billing_summary("REG-A")
        summary_b = metering.get_billing_summary("REG-B")
        # Each regulator's queries counted independently
        assert summary_a["query_count"] == len(results_a)
        assert summary_b["query_count"] == len(results_b)


class TestStressTestUnderLoad:
    """Stress test endpoint performance."""

    def test_response_time_stress_test_under_load(self):
        app, _ = _make_test_app()
        client = TestClient(app)
        token = _make_token()
        latencies: list[float] = []

        def _query():
            t0 = time.perf_counter()
            client.post(
                "/api/v1/regulatory/stress-test",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "scenario_name": "load_test",
                    "shocks": [{"corridor": "EUR-USD", "magnitude": 0.5}],
                },
            )
            latencies.append((time.perf_counter() - t0) * 1000)

        threads = [threading.Thread(target=_query) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        assert p95 < 30000, f"p95 stress test latency {p95:.0f}ms exceeds 30s target"


class TestConsistency:
    """Sequential vs concurrent result consistency."""

    def test_sequential_vs_concurrent_consistency(self):
        app, _ = _make_test_app()
        client = TestClient(app)
        token = _make_token()

        # Sequential
        seq_results = []
        for _ in range(5):
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token}"},
            )
            seq_results.append(resp.json()["total_corridors"])

        # Concurrent
        conc_results: list[int] = []

        def _query():
            resp = client.get(
                "/api/v1/regulatory/corridors",
                headers={"Authorization": f"Bearer {token}"},
            )
            conc_results.append(resp.json()["total_corridors"])

        threads = [threading.Thread(target=_query) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert all(s == seq_results[0] for s in seq_results)
        assert all(c == seq_results[0] for c in conc_results)
