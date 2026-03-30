# Sprint 4c — P10 Regulatory API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 7-endpoint REST API that exposes Sprint 4b's systemic risk computations (corridor failure rates, HHI concentration, BFS contagion) to regulators.

**Architecture:** Three-layer pattern matching the Cascade API: `RegulatoryService` (orchestration + caching) wraps Sprint 4b's computation engines, `RegulatoryRouter` (factory function) wires 7 endpoints with Pydantic models, and `TokenBucketRateLimiter` (in-memory) enforces request limits. Mounted at `/api/v1/regulatory` in `app.py`, conditional on a `SystemicRiskEngine` being provided.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, httpx (testing), pytest, threading, ruff

---

## Context

Session 12 of 23. Sprint 4b built three computation modules: `SystemicRiskEngine` (trend detection + risk reports), `CorridorConcentrationAnalyzer` (HHI), `ContagionSimulator` (BFS propagation). Sprint 4c wraps them in HTTP. Sprint 5 adds PDF/CSV reports. Sprint 6 adds `RegulatorSubscriptionToken` + billing.

**Existing code consumed:**
- `lip/p10_regulatory_data/systemic_risk.py` — `SystemicRiskEngine`, `CorridorRiskSnapshot`, `SystemicRiskReport`
- `lip/p10_regulatory_data/concentration.py` — `CorridorConcentrationAnalyzer`, `ConcentrationResult`
- `lip/p10_regulatory_data/contagion.py` — `ContagionSimulator`, `ContagionNode`, `ContagionResult`
- `lip/p10_regulatory_data/telemetry_schema.py` — `AnonymizedCorridorResult`
- `lip/api/cascade_router.py` — pattern reference (router factory, Pydantic models, `try/except ImportError` guard)
- `lip/api/cascade_service.py` — pattern reference (service layer with in-memory store)
- `lip/api/auth.py` — `make_hmac_dependency` (reused, not modified)
- `lip/api/app.py:46-227` — `create_app()` factory (will add `systemic_risk_engine` param)

**Key interface notes:**
- `CorridorConcentrationAnalyzer.compute_corridor_concentration()` takes `Dict[str, float]` (corridor→volume), not snapshots. The service layer must extract volumes from the engine's history.
- `ContagionSimulator.simulate()` requires a `graph` (adjacency dict). The service must build this from corridor bank sets. For Sprint 4c, the service uses a synthetic/placeholder graph derived from corridor names (real bank hash sets require live data ingestion). The contagion endpoint is functional for demonstration but produces meaningful results only after real telemetry ingestion.
- `ContagionNode.propagation_path` is `Tuple[str, ...]` in the dataclass but serializes to `List[str]` in the Pydantic response model — Pydantic handles this automatically.

**Spec:** `docs/superpowers/specs/2026-03-30-sprint-4c-regulatory-api-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/api/rate_limiter.py` | `TokenBucketRateLimiter` — in-memory, per-key, thread-safe |
| Create | `lip/api/regulatory_models.py` | Pydantic request/response models (6 request, 9 response) |
| Create | `lip/api/regulatory_service.py` | `RegulatoryService` + `CachedReport` — orchestration, caching |
| Create | `lip/api/regulatory_router.py` | `make_regulatory_router()` — 7 endpoints, factory pattern |
| Modify | `lip/api/app.py:46` | Add `systemic_risk_engine` param, mount regulatory router |
| Create | `lip/tests/test_regulatory_api.py` | Full TDD test suite (~30 tests) |

---

## Task 1: Implement TokenBucketRateLimiter (TDD)

**Files:** `lip/tests/test_regulatory_api.py` (create), `lip/api/rate_limiter.py` (create)

- [ ] **Step 1: Write `TestRateLimiter` tests** (5 tests)

```python
"""
test_regulatory_api.py — TDD tests for P10 Regulatory API.

Sprint 4c: HTTP REST endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations

import time

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
        # key-A exhausted, key-B still full
        assert limiter.check_and_consume("key-A") is False
        assert limiter.check_and_consume("key-B") is True

    def test_tokens_refill_after_period(self):
        """Tokens refill proportionally as time passes."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, period_seconds=10)
        # Consume all tokens
        for _ in range(10):
            limiter.check_and_consume("key-1")
        assert limiter.check_and_consume("key-1") is False
        # Simulate 5 seconds passing (should refill 5 tokens)
        # Access internal state to adjust timestamp
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
```

- [ ] **Step 2: Run tests (expect ImportError)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRateLimiter -v`

- [ ] **Step 3: Implement `lip/api/rate_limiter.py`**

```python
"""
rate_limiter.py — In-memory token-bucket rate limiter.

Reusable across routers. One bucket per key (API key / regulator ID).
Thread-safe via threading.Lock.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


class TokenBucketRateLimiter:
    """In-memory token-bucket rate limiter.

    Each key gets ``rate`` tokens per ``period_seconds``. Tokens refill
    continuously (proportional to elapsed time). When a key's bucket
    is empty, ``check_and_consume`` returns False.

    Thread-safe.
    """

    def __init__(self, rate: int = 100, period_seconds: int = 3600):
        self._rate = rate
        self._period = period_seconds
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check_and_consume(self, key: str) -> bool:
        """Consume one token for ``key``.

        Returns True if the request is allowed, False if rate-limited.
        """
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(self._rate), now))

            # Refill tokens proportional to elapsed time
            elapsed = now - last_refill
            refill = elapsed * (self._rate / self._period)
            tokens = min(float(self._rate), tokens + refill)
            last_refill = now

            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, last_refill)
                return True
            else:
                self._buckets[key] = (tokens, last_refill)
                return False

    def remaining(self, key: str) -> int:
        """Return number of tokens remaining for ``key``."""
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(self._rate), now))

            elapsed = now - last_refill
            refill = elapsed * (self._rate / self._period)
            tokens = min(float(self._rate), tokens + refill)

            return int(tokens)
```

- [ ] **Step 4: Run tests (expect PASS)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRateLimiter -v`

- [ ] **Step 5: Ruff check + commit**

Run: `PYTHONPATH=. ruff check lip/api/rate_limiter.py lip/tests/test_regulatory_api.py`

---

## Task 2: Implement Pydantic Models

**Files:** `lip/api/regulatory_models.py` (create)

No TDD for models — they are pure data declarations validated by the router tests in Task 4.

- [ ] **Step 1: Create `lip/api/regulatory_models.py`**

```python
"""
regulatory_models.py — Pydantic request/response models for P10 Regulatory API.

Separated from the router to keep endpoint wiring focused.
Sprint 4c: 7 endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field

    # ── Request Models ──────────────────────────────────────────────

    class CorridorListParams(BaseModel):
        """Query params for GET /corridors."""

        period_count: int = Field(default=24, ge=1, le=720)
        min_bank_count: int = Field(default=5, ge=1)

    class CorridorTrendParams(BaseModel):
        """Query params for GET /corridors/{corridor_id}/trend."""

        periods: int = Field(default=24, ge=1, le=720)

    class ConcentrationParams(BaseModel):
        """Query params for GET /concentration."""

        dimension: str = Field(
            default="corridor", pattern="^(corridor|jurisdiction)$"
        )

    class ContagionSimulationParams(BaseModel):
        """Query params for GET /contagion/simulate."""

        shock_corridor: str = Field(..., min_length=3)
        shock_magnitude: float = Field(default=1.0, ge=0.0, le=1.0)
        max_hops: int = Field(default=5, ge=1, le=10)

    class StressTestShock(BaseModel):
        """One shock in a stress test scenario."""

        corridor: str = Field(..., min_length=3)
        magnitude: float = Field(..., ge=0.0, le=1.0)

    class StressTestRequest(BaseModel):
        """Request body for POST /stress-test."""

        scenario_name: str = Field(..., min_length=1, max_length=200)
        shocks: List[StressTestShock] = Field(..., min_length=1, max_length=20)

    # ── Response Models ─────────────────────────────────────────────

    class CorridorSnapshotResponse(BaseModel):
        """One corridor in the corridor list or trend."""

        corridor: str
        period_label: str
        failure_rate: float
        total_payments: int
        failed_payments: int
        bank_count: int
        trend_direction: str
        trend_magnitude: float
        contains_stale_data: bool

    class CorridorListResponse(BaseModel):
        """Response for GET /corridors."""

        corridors: List[CorridorSnapshotResponse]
        total_corridors: int
        suppressed_count: int
        timestamp: float

    class CorridorTrendResponse(BaseModel):
        """Response for GET /corridors/{corridor_id}/trend."""

        corridor_id: str
        snapshots: List[CorridorSnapshotResponse]
        total_periods: int

    class ConcentrationResponse(BaseModel):
        """Response for GET /concentration."""

        dimension: str
        hhi: float
        effective_count: float
        is_concentrated: bool
        top_entities: List[List[Any]]

    class ContagionNodeResponse(BaseModel):
        """One affected corridor in contagion results."""

        corridor: str
        stress_level: float
        hop_distance: int
        propagation_path: List[str]

    class ContagionSimulationResponse(BaseModel):
        """Response for GET /contagion/simulate."""

        origin_corridor: str
        shock_magnitude: float
        affected_corridors: List[ContagionNodeResponse]
        max_propagation_depth: int
        total_volume_at_risk_usd: float
        systemic_risk_score: float

    class StressTestResponse(BaseModel):
        """Response for POST /stress-test."""

        scenario_name: str
        report_id: str
        overall_failure_rate: float
        highest_risk_corridor: str
        concentration_hhi: float
        systemic_risk_score: float
        total_corridors_analyzed: int
        stale_corridor_count: int
        timestamp: float

    class ReportResponse(BaseModel):
        """Response for GET /reports/{report_id}."""

        report_id: str
        timestamp: float
        corridor_snapshots: List[CorridorSnapshotResponse]
        overall_failure_rate: float
        highest_risk_corridor: str
        concentration_hhi: float
        systemic_risk_score: float
        stale_corridor_count: int
        total_corridors_analyzed: int

    class MetadataResponse(BaseModel):
        """Response for GET /metadata."""

        api_version: str
        data_freshness: Dict[str, Any]
        methodology: Dict[str, Any]
        rate_limit: Dict[str, Any]

except ImportError:
    logger.debug("Pydantic not installed — regulatory models not available")
```

- [ ] **Step 2: Ruff check**

Run: `PYTHONPATH=. ruff check lip/api/regulatory_models.py`

- [ ] **Step 3: Commit**

---

## Task 3: Implement RegulatoryService (TDD)

**Files:** `lip/tests/test_regulatory_api.py` (add class), `lip/api/regulatory_service.py` (create)

- [ ] **Step 1: Write `TestRegulatoryService` tests** (8 tests)

Add to `lip/tests/test_regulatory_api.py`:

```python
class TestRegulatoryService:
    """Service layer orchestration tests."""

    def _make_engine_with_data(self):
        """Create a SystemicRiskEngine with ingested test data."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult
        engine = SystemicRiskEngine()
        results = [
            AnonymizedCorridorResult(
                corridor="EUR-USD", period_label="2029-08-01T14:00Z",
                total_payments=500, failed_payments=25, failure_rate=0.05,
                bank_count=8, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
            ),
            AnonymizedCorridorResult(
                corridor="GBP-EUR", period_label="2029-08-01T14:00Z",
                total_payments=300, failed_payments=24, failure_rate=0.08,
                bank_count=6, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
            ),
            AnonymizedCorridorResult(
                corridor="USD-JPY", period_label="2029-08-01T14:00Z",
                total_payments=200, failed_payments=6, failure_rate=0.03,
                bank_count=3, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
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
        assert len(trend) == 1  # only 1 period ingested
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
        result = service.simulate_contagion(shock_corridor="EUR-USD", shock_magnitude=0.8)
        assert result.origin_corridor == "EUR-USD"
        assert 0.0 <= result.systemic_risk_score <= 1.0

    def test_run_stress_test_returns_report_and_does_not_pollute(self):
        """Stress test produces a report and does not pollute engine history."""
        from lip.api.regulatory_service import RegulatoryService
        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        # Get baseline corridor count
        baseline = engine.compute_risk_report()
        baseline_count = baseline.total_corridors_analyzed
        # Run stress test
        report_id, report = service.run_stress_test(
            scenario_name="test-scenario",
            shocks=[("EUR-USD", 0.9), ("GBP-EUR", 0.7)],
        )
        assert report.total_corridors_analyzed >= 1
        assert report_id is not None
        # Engine history should not contain synthetic data
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
```

- [ ] **Step 2: Run tests (expect ImportError)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRegulatoryService -v`

- [ ] **Step 3: Implement `lip/api/regulatory_service.py`**

```python
"""
regulatory_service.py — Regulatory API service layer.

Orchestrates SystemicRiskEngine, CorridorConcentrationAnalyzer, and
ContagionSimulator into API-ready responses. Manages in-memory report
cache with TTL eviction.

Sprint 4c: no new financial math — all computation delegates to Sprint 4b.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lip.p10_regulatory_data.concentration import (
    ConcentrationResult,
    CorridorConcentrationAnalyzer,
)
from lip.p10_regulatory_data.contagion import ContagionResult, ContagionSimulator
from lip.p10_regulatory_data.constants import (
    P10_DIFFERENTIAL_PRIVACY_EPSILON,
    P10_K_ANONYMITY_THRESHOLD,
)
from lip.p10_regulatory_data.systemic_risk import (
    CorridorRiskSnapshot,
    SystemicRiskEngine,
    SystemicRiskReport,
)
from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

logger = logging.getLogger(__name__)


@dataclass
class CachedReport:
    """In-memory cached risk report with TTL."""

    report_id: str
    report: SystemicRiskReport
    created_at: float
    scenario_name: str = ""


class RegulatoryService:
    """Regulatory API business logic orchestration.

    Wraps SystemicRiskEngine, CorridorConcentrationAnalyzer, ContagionSimulator.
    Manages in-memory report cache with TTL eviction.
    Thread-safe (delegates to thread-safe engines).
    """

    def __init__(
        self,
        risk_engine: SystemicRiskEngine,
        report_ttl_seconds: float = 3600.0,
        max_cached_reports: int = 100,
    ):
        self._engine = risk_engine
        self._concentration = CorridorConcentrationAnalyzer()
        self._contagion = ContagionSimulator()
        self._report_ttl = report_ttl_seconds
        self._max_reports = max_cached_reports
        self._reports: Dict[str, CachedReport] = {}
        self._lock = threading.Lock()
        self._query_count: int = 0

    def get_corridor_snapshots(
        self,
        period_count: int = 24,
        min_bank_count: int = 5,
    ) -> Tuple[List[CorridorRiskSnapshot], int]:
        """Get latest corridor snapshots, filtering by k-anonymity.

        Returns (published_snapshots, suppressed_count).
        Corridors with bank_count < min_bank_count are suppressed.
        """
        self._query_count += 1
        report = self._engine.compute_risk_report()
        published = []
        suppressed = 0
        for snapshot in report.corridor_snapshots:
            if snapshot.bank_count >= min_bank_count:
                published.append(snapshot)
            else:
                suppressed += 1
        return published, suppressed

    def get_corridor_trend(
        self,
        corridor_id: str,
        periods: int = 24,
    ) -> List[CorridorRiskSnapshot]:
        """Get time-series for one corridor."""
        self._query_count += 1
        return self._engine.get_corridor_trend(corridor_id, periods)

    def get_concentration(
        self,
        dimension: str = "corridor",
    ) -> ConcentrationResult:
        """Compute HHI concentration for corridor or jurisdiction dimension.

        Extracts corridor volumes from the engine's current report.
        """
        self._query_count += 1
        report = self._engine.compute_risk_report()
        volumes = {
            s.corridor: float(s.total_payments)
            for s in report.corridor_snapshots
        }
        if not volumes:
            volumes = {"__empty__": 1.0}

        if dimension == "jurisdiction":
            return self._concentration.compute_jurisdiction_concentration(volumes)
        return self._concentration.compute_corridor_concentration(volumes)

    def simulate_contagion(
        self,
        shock_corridor: str,
        shock_magnitude: float = 1.0,
        max_hops: int = 5,
    ) -> ContagionResult:
        """Run contagion simulation from a shock corridor.

        Builds a corridor dependency graph from the current report's
        corridor names using synthetic bank sets (real bank hash sets
        require live telemetry ingestion via RegulatoryAnonymizer).
        """
        self._query_count += 1
        report = self._engine.compute_risk_report()
        corridors = [s.corridor for s in report.corridor_snapshots]

        # Build synthetic bank sets for graph construction.
        # Each corridor gets a set of synthetic bank hashes.
        # Corridors sharing a currency zone share some banks.
        bank_sets: Dict[str, set] = {}
        bank_counter = 0
        currency_banks: Dict[str, set] = {}
        for corridor in corridors:
            parts = corridor.split("-")
            corridor_banks = set()
            for part in parts:
                if part not in currency_banks:
                    currency_banks[part] = {
                        f"SB{bank_counter + i}" for i in range(3)
                    }
                    bank_counter += 3
                corridor_banks |= currency_banks[part]
            bank_sets[corridor] = corridor_banks

        if shock_corridor not in bank_sets:
            bank_sets[shock_corridor] = {f"SB{bank_counter}"}

        sim = ContagionSimulator(
            max_hops=max_hops,
        )
        graph = sim.build_dependency_graph(bank_sets)
        volumes = {
            s.corridor: float(s.total_payments)
            for s in report.corridor_snapshots
        }
        return sim.simulate(graph, shock_corridor, shock_magnitude, volumes)

    def run_stress_test(
        self,
        scenario_name: str,
        shocks: List[Tuple[str, float]],
    ) -> Tuple[str, SystemicRiskReport]:
        """Run multi-shock stress test.

        Creates a temporary engine clone, ingests synthetic elevated-failure
        results for each shock corridor, computes a report, caches it,
        and returns (report_id, report). Does NOT pollute the main engine.
        """
        self._query_count += 1

        # Create a fresh engine for the stress test.
        # Must hold the source engine's lock while copying history
        # to avoid concurrent-modification bugs.
        stress_engine = SystemicRiskEngine()
        with self._engine._lock:
            for corridor, history in self._engine._history.items():
                stress_engine._history[corridor] = list(history)

        # Ingest synthetic shocks
        synthetic_results = []
        for corridor, magnitude in shocks:
            synthetic_results.append(
                AnonymizedCorridorResult(
                    corridor=corridor,
                    period_label="STRESS-TEST",
                    total_payments=1000,
                    failed_payments=int(1000 * magnitude),
                    failure_rate=magnitude,
                    bank_count=10,
                    k_anonymity_satisfied=True,
                    privacy_budget_remaining=5.0,
                    noise_applied=False,
                    stale=False,
                )
            )
        stress_engine.ingest_results(synthetic_results)

        # Compute report on stress engine
        report = stress_engine.compute_risk_report()
        report_id = f"RPT-{uuid.uuid4().hex[:12].upper()}"

        # Cache the report
        with self._lock:
            self._reports[report_id] = CachedReport(
                report_id=report_id,
                report=report,
                created_at=time.time(),
                scenario_name=scenario_name,
            )
            # Evict oldest if over capacity
            if len(self._reports) > self._max_reports:
                oldest_key = min(
                    self._reports, key=lambda k: self._reports[k].created_at
                )
                del self._reports[oldest_key]

        return report_id, report

    def get_report(self, report_id: str) -> Optional[CachedReport]:
        """Retrieve cached report by ID. Returns None if expired/missing."""
        with self._lock:
            cached = self._reports.get(report_id)
            if cached is None:
                return None
            if time.time() - cached.created_at > self._report_ttl:
                del self._reports[report_id]
                return None
            return cached

    def get_metadata(self) -> Dict[str, Any]:
        """Return API and data metadata."""
        report = self._engine.compute_risk_report()
        return {
            "api_version": "1.0.0",
            "data_freshness": {
                "corridors_monitored": report.total_corridors_analyzed,
                "stale_corridors": report.stale_corridor_count,
                "total_queries": self._query_count,
            },
            "methodology": {
                "k_anonymity_threshold": P10_K_ANONYMITY_THRESHOLD,
                "differential_privacy_epsilon": float(
                    P10_DIFFERENTIAL_PRIVACY_EPSILON
                ),
                "methodology_version": "P10-v1.0",
            },
            "rate_limit": {
                "requests_per_hour": 100,
            },
        }
```

- [ ] **Step 4: Run tests (expect PASS)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRegulatoryService -v`

- [ ] **Step 5: Ruff check + commit**

---

## Task 4: Implement Regulatory Router (TDD)

**Files:** `lip/tests/test_regulatory_api.py` (add classes), `lip/api/regulatory_router.py` (create)

- [ ] **Step 1: Write `TestRegulatoryRouter` tests** (14 tests)

Add to `lip/tests/test_regulatory_api.py`:

```python
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
        engine.ingest_results([
            AnonymizedCorridorResult(
                corridor="EUR-USD", period_label="2029-08-01T14:00Z",
                total_payments=500, failed_payments=25, failure_rate=0.05,
                bank_count=8, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
            ),
            AnonymizedCorridorResult(
                corridor="GBP-EUR", period_label="2029-08-01T14:00Z",
                total_payments=300, failed_payments=24, failure_rate=0.08,
                bank_count=6, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
            ),
        ])
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
        app.include_router(make_regulatory_router(service), prefix="/api/v1/regulatory")
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
        resp = client.get("/api/v1/regulatory/concentration?dimension=jurisdiction")
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
        # First create a report via stress test
        create_resp = client.post(
            "/api/v1/regulatory/stress-test",
            json={
                "scenario_name": "test",
                "shocks": [{"corridor": "EUR-USD", "magnitude": 0.5}],
            },
        )
        report_id = create_resp.json()["report_id"]
        # Retrieve it
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
        # Consume all tokens
        c.get("/api/v1/regulatory/metadata")
        c.get("/api/v1/regulatory/metadata")
        # 3rd request should be rate limited
        resp = c.get("/api/v1/regulatory/metadata")
        assert resp.status_code == 429
```

- [ ] **Step 2: Run tests (expect ImportError)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRegulatoryRouter -v`

- [ ] **Step 3: Implement `lip/api/regulatory_router.py`**

```python
"""
regulatory_router.py — P10 Regulatory API HTTP endpoints.

Sprint 4c: 7 REST endpoints over Sprint 4b systemic risk engine.
Factory pattern matching make_cascade_router / make_miplo_router.

Endpoints:
  GET  /corridors                     — Corridor failure rate snapshots
  GET  /corridors/{corridor_id}/trend — Time-series for one corridor
  GET  /concentration                 — HHI concentration metrics
  GET  /contagion/simulate            — BFS stress propagation
  POST /stress-test                   — Multi-shock stress scenario
  GET  /reports/{report_id}           — Retrieve cached report (JSON)
  GET  /metadata                      — API + data metadata
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

    from lip.api.rate_limiter import TokenBucketRateLimiter
    from lip.api.regulatory_models import (
        ConcentrationResponse,
        ContagionNodeResponse,
        ContagionSimulationResponse,
        CorridorListResponse,
        CorridorSnapshotResponse,
        CorridorTrendResponse,
        MetadataResponse,
        ReportResponse,
        StressTestRequest,
        StressTestResponse,
    )
    from lip.api.regulatory_service import RegulatoryService

    def _make_rate_limit_dep(limiter: TokenBucketRateLimiter):
        """Create a FastAPI dependency for rate limiting.

        Uses client IP as the rate-limit key (placeholder for Sprint 6
        RegulatorSubscriptionToken-based keying).
        """

        async def _check_rate(request: Request, response: Response):
            key = request.client.host if request.client else "unknown"
            remaining = limiter.remaining(key)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            if not limiter.check_and_consume(key):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "3600"},
                )

        return _check_rate

    def make_regulatory_router(
        regulatory_service: RegulatoryService,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        auth_dependency: Any = None,
    ) -> APIRouter:
        """Factory that builds the P10 Regulatory API router.

        Follows make_cascade_router / make_miplo_router pattern.
        Service + rate_limiter captured by closure — no global state.
        """
        router = APIRouter(tags=["regulatory"])

        deps: list = []
        if auth_dependency is not None:
            deps.append(Depends(auth_dependency))
        if rate_limiter is not None:
            deps.append(Depends(_make_rate_limit_dep(rate_limiter)))

        @router.get(
            "/corridors",
            response_model=CorridorListResponse,
            dependencies=deps,
        )
        async def list_corridors(
            period_count: int = Query(default=24, ge=1, le=720),
            min_bank_count: int = Query(default=5, ge=1),
        ):
            """Corridor failure rate snapshots with k-anonymity filtering."""
            snapshots, suppressed = regulatory_service.get_corridor_snapshots(
                period_count=period_count,
                min_bank_count=min_bank_count,
            )
            return CorridorListResponse(
                corridors=[
                    CorridorSnapshotResponse(
                        corridor=s.corridor,
                        period_label=s.period_label,
                        failure_rate=s.failure_rate,
                        total_payments=s.total_payments,
                        failed_payments=s.failed_payments,
                        bank_count=s.bank_count,
                        trend_direction=s.trend_direction,
                        trend_magnitude=s.trend_magnitude,
                        contains_stale_data=s.contains_stale_data,
                    )
                    for s in snapshots
                ],
                total_corridors=len(snapshots),
                suppressed_count=suppressed,
                timestamp=time.time(),
            )

        @router.get(
            "/corridors/{corridor_id}/trend",
            response_model=CorridorTrendResponse,
            dependencies=deps,
        )
        async def get_corridor_trend(
            corridor_id: str,
            periods: int = Query(default=24, ge=1, le=720),
        ):
            """Time-series failure rate data for one corridor."""
            snapshots = regulatory_service.get_corridor_trend(corridor_id, periods)
            return CorridorTrendResponse(
                corridor_id=corridor_id,
                snapshots=[
                    CorridorSnapshotResponse(
                        corridor=s.corridor,
                        period_label=s.period_label,
                        failure_rate=s.failure_rate,
                        total_payments=s.total_payments,
                        failed_payments=s.failed_payments,
                        bank_count=s.bank_count,
                        trend_direction=s.trend_direction,
                        trend_magnitude=s.trend_magnitude,
                        contains_stale_data=s.contains_stale_data,
                    )
                    for s in snapshots
                ],
                total_periods=len(snapshots),
            )

        @router.get(
            "/concentration",
            response_model=ConcentrationResponse,
            dependencies=deps,
        )
        async def get_concentration(
            dimension: str = Query(
                default="corridor", pattern="^(corridor|jurisdiction)$"
            ),
        ):
            """HHI concentration metrics."""
            result = regulatory_service.get_concentration(dimension)
            return ConcentrationResponse(
                dimension=result.dimension,
                hhi=result.hhi,
                effective_count=result.effective_count,
                is_concentrated=result.is_concentrated,
                top_entities=[list(e) for e in result.top_entities],
            )

        @router.get(
            "/contagion/simulate",
            response_model=ContagionSimulationResponse,
            dependencies=deps,
        )
        async def simulate_contagion(
            shock_corridor: str = Query(..., min_length=3),
            shock_magnitude: float = Query(default=1.0, ge=0.0, le=1.0),
            max_hops: int = Query(default=5, ge=1, le=10),
        ):
            """BFS contagion stress propagation simulation."""
            result = regulatory_service.simulate_contagion(
                shock_corridor=shock_corridor,
                shock_magnitude=shock_magnitude,
                max_hops=max_hops,
            )
            return ContagionSimulationResponse(
                origin_corridor=result.origin_corridor,
                shock_magnitude=result.shock_magnitude,
                affected_corridors=[
                    ContagionNodeResponse(
                        corridor=n.corridor,
                        stress_level=n.stress_level,
                        hop_distance=n.hop_distance,
                        propagation_path=list(n.propagation_path),
                    )
                    for n in result.affected_corridors
                ],
                max_propagation_depth=result.max_propagation_depth,
                total_volume_at_risk_usd=result.total_volume_at_risk_usd,
                systemic_risk_score=result.systemic_risk_score,
            )

        @router.post(
            "/stress-test",
            response_model=StressTestResponse,
            dependencies=deps,
        )
        async def run_stress_test(request: StressTestRequest):
            """Multi-shock stress test scenario."""
            shocks = [(s.corridor, s.magnitude) for s in request.shocks]
            report_id, report = regulatory_service.run_stress_test(
                scenario_name=request.scenario_name,
                shocks=shocks,
            )
            return StressTestResponse(
                scenario_name=request.scenario_name,
                report_id=report_id,
                overall_failure_rate=report.overall_failure_rate,
                highest_risk_corridor=report.highest_risk_corridor,
                concentration_hhi=report.concentration_hhi,
                systemic_risk_score=report.systemic_risk_score,
                total_corridors_analyzed=report.total_corridors_analyzed,
                stale_corridor_count=report.stale_corridor_count,
                timestamp=report.timestamp,
            )

        @router.get(
            "/reports/{report_id}",
            response_model=ReportResponse,
            dependencies=deps,
        )
        async def get_report(report_id: str):
            """Retrieve a cached risk report by ID (JSON only)."""
            cached = regulatory_service.get_report(report_id)
            if cached is None:
                raise HTTPException(status_code=404, detail="Report not found")
            report = cached.report
            return ReportResponse(
                report_id=cached.report_id,
                timestamp=report.timestamp,
                corridor_snapshots=[
                    CorridorSnapshotResponse(
                        corridor=s.corridor,
                        period_label=s.period_label,
                        failure_rate=s.failure_rate,
                        total_payments=s.total_payments,
                        failed_payments=s.failed_payments,
                        bank_count=s.bank_count,
                        trend_direction=s.trend_direction,
                        trend_magnitude=s.trend_magnitude,
                        contains_stale_data=s.contains_stale_data,
                    )
                    for s in report.corridor_snapshots
                ],
                overall_failure_rate=report.overall_failure_rate,
                highest_risk_corridor=report.highest_risk_corridor,
                concentration_hhi=report.concentration_hhi,
                systemic_risk_score=report.systemic_risk_score,
                stale_corridor_count=report.stale_corridor_count,
                total_corridors_analyzed=report.total_corridors_analyzed,
            )

        @router.get(
            "/metadata",
            response_model=MetadataResponse,
            dependencies=deps,
        )
        async def get_metadata():
            """API and data metadata."""
            meta = regulatory_service.get_metadata()
            return MetadataResponse(**meta)

        return router

except ImportError:
    logger.debug("FastAPI not installed — regulatory router not available")

    def make_regulatory_router(*args, **kwargs):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the regulatory router")
```

- [ ] **Step 4: Run tests (expect PASS)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py::TestRegulatoryRouter -v`

- [ ] **Step 5: Ruff check + commit**

---

## Task 5: Integration Tests + App Mounting + Full Regression

**Files:** `lip/tests/test_regulatory_api.py` (add class), `lip/api/app.py` (modify)

- [ ] **Step 1: Write `TestIntegration` tests** (3 tests)

Add to `lip/tests/test_regulatory_api.py`:

```python
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
        engine.ingest_results([
            AnonymizedCorridorResult(
                corridor="EUR-USD", period_label="2029-08-01T14:00Z",
                total_payments=1000, failed_payments=100, failure_rate=0.10,
                bank_count=10, k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5, noise_applied=True, stale=False,
            ),
        ])
        service = RegulatoryService(risk_engine=engine)
        app = FastAPI()
        app.include_router(make_regulatory_router(service), prefix="/api/v1/regulatory")
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
        from lip.api.app import create_app
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

        engine = SystemicRiskEngine()
        app = create_app(systemic_risk_engine=engine)
        routes = [r.path for r in app.routes]
        assert any("/api/v1/regulatory" in r for r in routes)
```

- [ ] **Step 2: Modify `lip/api/app.py`**

Add `systemic_risk_engine=None` parameter to `create_app()` and mount the regulatory router conditionally (matching the Cascade pattern at lines 217-225).

In the function signature on line 46:
```python
def create_app(pipeline=None, processor_context=None, cascade_graph=None,
               systemic_risk_engine=None) -> FastAPI:
```

Also update the fallback `create_app` in the `except ImportError` block (line 236):
```python
    def create_app(pipeline=None, processor_context=None, cascade_graph=None,
                   systemic_risk_engine=None):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the HTTP application")
```

After the Cascade router block (after line 225), add:
```python
        # Regulatory API (P10 — available when systemic risk engine provided)
        if systemic_risk_engine is not None:
            from lip.api.rate_limiter import TokenBucketRateLimiter
            from lip.api.regulatory_router import make_regulatory_router
            from lip.api.regulatory_service import RegulatoryService

            reg_service = RegulatoryService(risk_engine=systemic_risk_engine)
            reg_limiter = TokenBucketRateLimiter(rate=100, period_seconds=3600)
            application.include_router(
                make_regulatory_router(
                    reg_service, rate_limiter=reg_limiter, auth_dependency=auth_dep,
                ),
                prefix="/api/v1/regulatory",
            )
```

- [ ] **Step 3: Run all regulatory API tests**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_regulatory_api.py -v`

Expected: All ~30 tests pass.

- [ ] **Step 4: Run P10 tests (4a + 4b still pass)**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_anonymizer.py lip/tests/test_p10_systemic_risk.py -v`

Expected: 54 pass.

- [ ] **Step 5: Ruff check full lip/**

Run: `PYTHONPATH=. ruff check lip/`

Expected: All checks passed!

- [ ] **Step 6: Full regression**

Run: `PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -k "not (test_returns_dict or test_returns_fitted or test_calibration_attaches or test_run_end_to_end)"`

Expected: ~1840+ passed, 0 failures.

- [ ] **Step 7: Verify imports**

Run: `PYTHONPATH=. python -c "from lip.api.regulatory_router import make_regulatory_router; from lip.api.regulatory_service import RegulatoryService; from lip.api.rate_limiter import TokenBucketRateLimiter; print('OK')"`

- [ ] **Step 8: Commit + push**

---

## Verification Checklist

1. [ ] `python -m pytest lip/tests/test_regulatory_api.py -v` — all ~30 tests pass
2. [ ] `python -m pytest lip/tests/test_p10_anonymizer.py lip/tests/test_p10_systemic_risk.py -v` — 54 Sprint 4a+4b tests still pass
3. [ ] Full regression — ~1840+ tests pass, 0 failures
4. [ ] `ruff check lip/` — zero errors
5. [ ] `python -c "from lip.api.regulatory_router import make_regulatory_router; print('OK')"` — imports clean
6. [ ] QUANT: No new financial math — all computation delegates to Sprint 4b engines
7. [ ] CIPHER: No raw bank IDs in API responses, rate limiting prevents enumeration, HMAC auth enforced
