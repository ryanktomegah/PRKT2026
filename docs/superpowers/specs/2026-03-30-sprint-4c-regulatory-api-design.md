# Sprint 4c — P10 Regulatory API Design Spec

**Status:** Approved (CTO decision)
**Sprint:** 4c of 23-session build program (Session 12)
**Prerequisites:** Sprint 4b (P10 Systemic Risk Engine)
**Product:** P10 Regulatory Data Product
**Blueprint Reference:** Sections 8.1, 8.2, 8.3

---

## Problem Statement

Sprint 4b built three computation modules — `SystemicRiskEngine`, `CorridorConcentrationAnalyzer`, `ContagionSimulator` — that transform anonymized corridor data into systemic risk intelligence. But computation sitting in memory is useless to regulators. Sprint 4c builds the HTTP layer that exposes these computations as a versioned REST API, following the same pattern as the Cascade API (P5): computation engine first, HTTP wrapper second.

---

## Design Principle: HTTP Wrapper, Not New Logic

Sprint 4c is a thin HTTP layer over Sprint 4b's computation. All business logic lives in the existing engine classes. The new code is: Pydantic models (request/response validation), a service layer (orchestration + caching), a router factory (endpoint wiring), and a rate limiter. No new financial math, no new risk computations.

**Auth scope:** Reuses existing HMAC auth (`make_hmac_dependency`). The `RegulatorSubscriptionToken` and per-regulator corridor access control are Sprint 6 (C8 Extension). Sprint 4c wires the auth slot so Sprint 6 can drop in the new token type without changing the router.

**Report format scope:** Endpoint 6 (report retrieval) returns JSON only. PDF/CSV generation is Sprint 5 (Report Generator).

---

## Architecture

Three-layer pattern matching Cascade API (`cascade_service.py` + `cascade_router.py`):

```
SystemicRiskEngine / ConcentrationAnalyzer / ContagionSimulator  (Sprint 4b — computation)
        |
RegulatoryService  (new — orchestration, caching, query tracking)
        |
RegulatoryRouter   (new — HTTP endpoints, Pydantic models, rate limiting)
```

All new files live in `lip/api/` alongside existing routers. The router is mounted in `app.py` at `/api/v1/regulatory`, conditionally on a `SystemicRiskEngine` being provided to `create_app()`.

---

## Component Design

### 1. Rate Limiter (`rate_limiter.py`)

A reusable in-memory token-bucket rate limiter. Built as a standalone module so other routers can adopt it later.

```python
class TokenBucketRateLimiter:
    """In-memory token-bucket rate limiter.

    Thread-safe. One bucket per key (API key / regulator ID).
    Tokens refill at a constant rate. When bucket is empty, requests
    are rejected with 429.
    """

    def __init__(self, rate: int = 100, period_seconds: int = 3600):
        self._rate = rate
        self._period = period_seconds
        self._buckets: Dict[str, Tuple[int, float]] = {}  # key → (tokens, last_refill)
        self._lock = threading.Lock()

    def check_and_consume(self, key: str) -> bool:
        """Consume one token. Returns True if allowed, False if rate-limited."""

    def remaining(self, key: str) -> int:
        """Tokens remaining for key (for response headers)."""
```

Default: 100 requests per hour per key. Redis-backed version deferred to infrastructure sprint.

### 2. Regulatory Service (`regulatory_service.py`)

Orchestration layer between HTTP and computation. Manages report lifecycle and wires the three Sprint 4b engines together.

```python
@dataclass
class CachedReport:
    """In-memory cached risk report with TTL."""
    report_id: str
    report: SystemicRiskReport
    created_at: float
    corridor_volumes: Dict[str, float]  # for contagion simulation context

class RegulatoryService:
    """Regulatory API business logic orchestration.

    Wraps SystemicRiskEngine, ConcentrationAnalyzer, ContagionSimulator.
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
        Returns (snapshots, suppressed_count)."""

    def get_corridor_trend(
        self,
        corridor_id: str,
        periods: int = 24,
    ) -> List[CorridorRiskSnapshot]:
        """Get time-series for one corridor."""

    def get_concentration(
        self,
        dimension: str = "corridor",
    ) -> ConcentrationResult:
        """Compute HHI concentration for corridor or jurisdiction dimension."""

    def simulate_contagion(
        self,
        shock_corridor: str,
        shock_magnitude: float = 1.0,
        max_hops: int = 5,
    ) -> ContagionResult:
        """Run contagion simulation from a shock corridor."""

    def run_stress_test(
        self,
        scenario_name: str,
        shocks: List[Tuple[str, float]],
    ) -> SystemicRiskReport:
        """Run multi-shock stress test.
        Ingests shocks as synthetic results, computes risk report."""

    def get_report(self, report_id: str) -> Optional[CachedReport]:
        """Retrieve cached report by ID. Returns None if expired/missing."""

    def get_metadata(self) -> Dict[str, Any]:
        """Return API and data metadata."""
```

**Report caching:** `compute_risk_report()` results are stored with a UUID and TTL. Eviction is lazy (checked on access) + capped at `max_cached_reports` (oldest evicted first).

**Stress test implementation:** For each shock `(corridor, magnitude)`, the service builds a synthetic `AnonymizedCorridorResult` with elevated failure rate, ingests it, and then computes a risk report. After the report is generated, the synthetic data is removed so it doesn't pollute the engine's history. This is a snapshot computation, not a persistent state change.

### 3. Pydantic Models (`regulatory_models.py`)

Request and response models at the HTTP boundary. Separated into their own file to keep the router focused on wiring.

```python
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
    dimension: str = Field(default="corridor", pattern="^(corridor|jurisdiction)$")

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
    """One corridor in the corridor list."""
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
    top_entities: List[List]  # [[entity, share], ...]

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
    data_freshness: dict  # corridors_monitored, total_queries, ...
    methodology: dict  # k_anonymity_threshold, epsilon, ...
    rate_limit: dict  # requests_per_hour, ...
```

### 4. Regulatory Router (`regulatory_router.py`)

Factory function matching the established pattern.

```python
def make_regulatory_router(
    regulatory_service: RegulatoryService,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
    auth_dependency=None,
) -> APIRouter:
    """Factory that builds the P10 Regulatory API router.

    Follows make_cascade_router / make_miplo_router pattern.
    Service + rate_limiter captured by closure — no global state.
    """
    router = APIRouter(tags=["regulatory"])

    # Auth + rate limiting as dependencies
    deps = []
    if auth_dependency is not None:
        deps.append(Depends(auth_dependency))
    if rate_limiter is not None:
        deps.append(Depends(_make_rate_limit_dep(rate_limiter)))
```

**7 Endpoints:**

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/corridors` | `list_corridors` | Corridor failure rate snapshots |
| GET | `/corridors/{corridor_id}/trend` | `get_corridor_trend` | Time-series for one corridor |
| GET | `/concentration` | `get_concentration` | HHI concentration metrics |
| GET | `/contagion/simulate` | `simulate_contagion` | BFS stress propagation |
| POST | `/stress-test` | `run_stress_test` | Multi-shock stress scenario |
| GET | `/reports/{report_id}` | `get_report` | Retrieve cached report (JSON) |
| GET | `/metadata` | `get_metadata` | API + data metadata |

**Rate limiting dependency:** Extracts API key from auth header (or uses client IP as fallback). Returns `429 Too Many Requests` with `Retry-After` header when bucket is empty. Adds `X-RateLimit-Remaining` header to all responses.

**Error handling:** Standard FastAPI/HTTP conventions:
- `404` — corridor not found, report not found
- `422` — Pydantic validation failure (automatic)
- `429` — rate limit exceeded
- `500` — unexpected engine error (logged, generic message returned)

### 5. App Integration (`app.py` modification)

Add conditional mounting in `create_app()`, matching the Cascade pattern:

```python
def create_app(pipeline=None, processor_context=None, cascade_graph=None,
               systemic_risk_engine=None) -> FastAPI:
    ...
    # Regulatory API (P10 — conditional on systemic risk engine)
    if systemic_risk_engine is not None:
        from lip.api.rate_limiter import TokenBucketRateLimiter
        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService

        reg_service = RegulatoryService(risk_engine=systemic_risk_engine)
        reg_limiter = TokenBucketRateLimiter(rate=100, period_seconds=3600)
        application.include_router(
            make_regulatory_router(reg_service, rate_limiter=reg_limiter, auth_dependency=auth_dep),
            prefix="/api/v1/regulatory",
        )
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/api/rate_limiter.py` | `TokenBucketRateLimiter` — reusable, in-memory |
| Create | `lip/api/regulatory_models.py` | Pydantic request/response models |
| Create | `lip/api/regulatory_service.py` | `RegulatoryService` orchestration + caching |
| Create | `lip/api/regulatory_router.py` | `make_regulatory_router()` — 7 endpoints |
| Modify | `lip/api/app.py` | Mount regulatory router (conditional) |
| Create | `lip/tests/test_regulatory_api.py` | Full test suite |

---

## Testing Strategy

All tests use `httpx.AsyncClient` + FastAPI `TestClient` (matching existing patterns). No live infrastructure.

### Rate Limiter (5 tests)
- Fresh bucket starts at capacity
- Consume tokens until empty → next request rejected
- Multi-key isolation (different keys don't share buckets)
- Token refill after time passes
- `remaining()` returns correct count

### Service Layer (8 tests)
- `get_corridor_snapshots` returns snapshots + suppression count
- `get_corridor_trend` delegates to engine correctly
- `get_concentration` for corridor and jurisdiction dimensions
- `simulate_contagion` returns valid ContagionResult
- `run_stress_test` doesn't pollute engine history
- `get_report` returns cached report
- `get_report` returns None for expired report
- `get_metadata` returns expected structure

### Router Endpoints (14 tests)
- GET `/corridors` — 200 with corridor list
- GET `/corridors` — empty engine returns empty list
- GET `/corridors/{id}/trend` — 200 with time-series
- GET `/corridors/{id}/trend` — unknown corridor returns empty
- GET `/concentration` — 200 with HHI result
- GET `/concentration?dimension=jurisdiction` — jurisdiction mode
- GET `/contagion/simulate?shock_corridor=X` — 200 with simulation
- GET `/contagion/simulate` — 422 missing required param
- POST `/stress-test` — 200 with report
- POST `/stress-test` — 422 empty shocks list
- GET `/reports/{id}` — 200 for cached report
- GET `/reports/{id}` — 404 for missing report
- GET `/metadata` — 200 with metadata
- Any endpoint — 429 when rate limited

### Integration (3 tests)
- Full pipeline: ingest → API call → verify response
- Rate limiter wired to router (101st request returns 429)
- App mounting: regulatory router present when engine provided, absent when not

**Total: ~30 tests**

---

## Out of Scope

- `RegulatorSubscriptionToken` (Sprint 6 — C8 Extension)
- Per-regulator corridor access control (Sprint 6)
- Query metering / billing (Sprint 6)
- PDF/CSV report formats (Sprint 5 — Report Generator)
- Redis-backed rate limiting (infrastructure sprint)
- WebSocket / streaming (not in blueprint)
- OpenAPI spec customization (auto-generated by FastAPI is sufficient for v1)

---

## QUANT / CIPHER Review Notes

**QUANT:** No new financial math — all computation delegates to Sprint 4b engines. Stress test is additive (synthetic ingestion → report → cleanup), not a new formula. HHI and contagion results pass through unchanged.

**CIPHER:** No new data exposure beyond what Sprint 4b already computes. Corridor names are public knowledge. Bank identifiers never appear in API responses (only hash-derived metrics). Rate limiting prevents enumeration attacks. HMAC auth prevents unauthorized access. RegulatorSubscriptionToken (Sprint 6) will add corridor-level access control.

---

## Sprint 6 Integration Points

Sprint 4c deliberately leaves these extension points for Sprint 6:

1. **Auth dependency slot** — `auth_dependency` parameter on `make_regulatory_router()`. Sprint 6 replaces `make_hmac_dependency` with `make_regulator_token_dependency`.
2. **Corridor filter** — `RegulatoryService` methods accept an optional `permitted_corridors` parameter (defaulting to all). Sprint 6 wires this from the token's `permitted_corridors` field.
3. **Query counter** — `RegulatoryService._query_count` tracks total queries. Sprint 6 breaks this down by regulator and wires to `RevenueMetering`.
