# Sprint 3d — C7 Coordinated Intervention API Design Spec

**Status:** Approved (CTO self-review)
**Sprint:** 3d of 23-session build program (Session 9)
**Prerequisites:** Sprint 3c (C2/C3/C5 cascade integration)
**Product:** P5 Supply Chain Cascade Detection & Prevention
**Blueprint Reference:** Sections 7.6, 8.2-8.3

---

## Problem Statement

Sprints 3a-3c built the full cascade engine: corporate graph, BFS propagation, intervention optimizer, cascade alerts, and three integration bridges (C2, C3, C5). But there is no way for a bank risk desk to interact with any of this. Sprint 3d exposes the cascade engine through C7 API endpoints — the bank's interface for triggering cascade analysis, reviewing intervention plans, executing bridge loans, and querying the dependency graph.

---

## Design Principle: Router Factory + Service Layer

Follow the established LIP API pattern exactly:

1. **Service layer** (`cascade_service.py`) — owns all business logic, holds CascadeGraph reference, manages alert lifecycle
2. **Router factory** (`cascade_router.py`) — `make_cascade_router(service, auth_dep)` returns an `APIRouter` with all endpoints. Service captured by closure.
3. **Wire in `app.py`** — `create_app()` constructs cascade service + router when CascadeGraph is available

This matches how MIPLO, admin, portfolio, and health routers are structured.

---

## Component Design

### 1. Cascade Service (`lip/api/cascade_service.py`)

Owns CascadeGraph, manages in-memory alert store with TTL eviction, tracks intervention execution status.

```python
class CascadeService:
    def __init__(self, cascade_graph: CascadeGraph, default_budget_usd: float):
        self._graph = cascade_graph
        self._budget = default_budget_usd
        self._alerts: Dict[str, CascadeAlert] = {}
        self._intervention_status: Dict[str, InterventionStatus] = {}

    def analyze(self, corporate_id: str, budget_usd: float | None, trigger_type: str) -> Optional[CascadeAlert]
    def list_alerts(self, severity: str | None, active_only: bool) -> List[CascadeAlert]
    def get_alert(self, alert_id: str) -> Optional[CascadeAlert]
    def execute_intervention(self, alert_id: str, action_priorities: List[int]) -> InterventionExecution
    def get_intervention_status(self, alert_id: str) -> Optional[InterventionStatus]
    def get_corporate_neighbors(self, corporate_id: str) -> Optional[CorporateNeighborhood]
    def get_graph_summary(self) -> GraphSummary
```

**Alert lifecycle:** `analyze()` → stores alert in `_alerts` → bank calls `execute_intervention()` within 4h exclusivity → status tracked in `_intervention_status`. Expired alerts are evicted on read (lazy TTL).

**InterventionStatus** tracks execution state:
```python
@dataclass
class InterventionStatus:
    alert_id: str
    status: str  # "PENDING", "EXECUTING", "EXECUTED", "EXPIRED"
    executed_actions: List[int]  # priority indices of executed interventions
    total_bridge_amount_usd: float
    total_value_prevented_usd: float
    executed_at: Optional[float]
```

**CorporateNeighborhood** — response for graph query:
```python
@dataclass
class CorporateNeighborhood:
    corporate_id: str
    sector: str
    jurisdiction: str
    cascade_centrality: float
    upstream: List[dict]   # [{corporate_id, dependency_score, volume_30d}]
    downstream: List[dict] # [{corporate_id, dependency_score, volume_30d}]
```

**GraphSummary** — high-level graph metadata:
```python
@dataclass
class GraphSummary:
    node_count: int
    edge_count: int
    avg_dependency_score: float
    max_centrality_node: str
    build_timestamp: float
```

### 2. Cascade Router (`lip/api/cascade_router.py`)

Five endpoints following the established `make_<router>()` pattern:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/cascade/analyze` | Trigger cascade analysis for a corporate |
| GET | `/cascade/alerts` | List active/all alerts with optional severity filter |
| GET | `/cascade/alerts/{alert_id}` | Get specific alert with full intervention plan |
| POST | `/cascade/alerts/{alert_id}/execute` | Execute selected interventions from the plan |
| GET | `/cascade/graph/{corporate_id}` | Query corporate's dependency neighborhood |

**Request/Response Models (Pydantic):**

```python
class CascadeAnalyzeRequest(BaseModel):
    corporate_id: str
    budget_usd: Optional[float] = None
    trigger_type: str = "PAYMENT_FAILURE"

class CascadeAnalyzeResponse(BaseModel):
    alert_id: Optional[str]
    severity: Optional[str]
    total_value_at_risk_usd: float
    cascade_amplification_factor: float
    nodes_at_risk: int
    intervention_count: int
    total_intervention_cost_usd: float
    total_value_prevented_usd: float
    expires_at: Optional[float]

class CascadeAlertListResponse(BaseModel):
    alerts: List[CascadeAlertSummary]
    total: int

class CascadeAlertSummary(BaseModel):
    alert_id: str
    severity: str
    origin_corporate_id: str
    origin_sector: str
    total_value_at_risk_usd: float
    intervention_count: int
    timestamp: float
    expires_at: float
    is_expired: bool

class CascadeAlertDetailResponse(BaseModel):
    alert_id: str
    severity: str
    origin_corporate_id: str
    origin_sector: str
    origin_jurisdiction: str
    total_value_at_risk_usd: float
    cascade_amplification_factor: float
    nodes_at_risk: int
    max_hops_reached: int
    trigger_type: str
    interventions: List[InterventionDetail]
    total_intervention_cost_usd: float
    total_value_prevented_usd: float
    budget_utilization_pct: float
    timestamp: float
    expires_at: float
    execution_status: Optional[str]

class InterventionDetail(BaseModel):
    priority: int
    source_corporate_id: str
    target_corporate_id: str
    bridge_amount_usd: float
    cascade_value_prevented_usd: float
    cost_efficiency_ratio: float

class ExecuteInterventionRequest(BaseModel):
    action_priorities: List[int]  # which interventions to execute (by priority)

class ExecuteInterventionResponse(BaseModel):
    alert_id: str
    status: str
    executed_actions: List[int]
    total_bridge_amount_usd: float
    total_value_prevented_usd: float

class CorporateNeighborhoodResponse(BaseModel):
    corporate_id: str
    sector: str
    jurisdiction: str
    cascade_centrality: float
    upstream: List[NeighborEdge]
    downstream: List[NeighborEdge]

class NeighborEdge(BaseModel):
    corporate_id: str
    dependency_score: float
    volume_30d: float
```

### 3. App Wiring (`lip/api/app.py`)

The cascade router is available in both bank-mode and processor-mode deployments — cascade risk affects all banks, not just processors. It is wired unconditionally when a CascadeGraph is provided.

`create_app()` gains an optional `cascade_graph` parameter:

```python
def create_app(pipeline=None, processor_context=None, cascade_graph=None) -> FastAPI:
    ...
    # Cascade intervention API (P5 — bank + processor deployments)
    if cascade_graph is not None:
        from lip.api.cascade_router import make_cascade_router
        from lip.api.cascade_service import CascadeService

        cascade_svc = CascadeService(cascade_graph, default_budget_usd=10_000_000.0)
        application.include_router(
            make_cascade_router(cascade_svc, auth_dependency=auth_dep),
            prefix="/cascade",
        )
```

**Why optional:** Not all deployments need cascade analysis (e.g., minimal test deployments). Same pattern as MIPLO — conditional wiring.

**Why $10M default budget:** Matches CASCADE_ALERT_SEVERITY_HIGH_USD threshold. Configurable per-request via the analyze endpoint.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/api/cascade_service.py` | Cascade alert lifecycle, graph queries, intervention tracking |
| Create | `lip/api/cascade_router.py` | 5 HTTP endpoints + Pydantic request/response models |
| Modify | `lip/api/app.py` | Wire cascade router (conditional on cascade_graph) |
| Create | `lip/tests/test_cascade_api.py` | Full TDD test suite for cascade API |

---

## Testing Strategy

- **Analyze endpoint:** Valid corporate → alert returned, unknown corporate → empty response, custom budget, custom trigger_type
- **List alerts:** Empty list, multiple alerts, severity filter, active-only filter (expired excluded)
- **Get alert detail:** Valid alert_id → full detail, unknown alert_id → 404, expired alert → still retrievable
- **Execute intervention:** Valid execution → status EXECUTED, expired alert → 410 Gone, invalid priorities → 400, alert not found → 404
- **Graph query:** Known corporate → neighborhood, unknown corporate → 404
- **Alert expiry:** Lazy TTL eviction on list (active_only=true filters expired)
- **Regression:** All existing API, C7, P5, C2, C3, C5 tests pass unchanged

---

## QUANT / CIPHER Review Notes

**QUANT:** No new financial math — the API layer delegates to existing P5 propagation + optimizer (already QUANT-approved). Budget parameter flows through to InterventionOptimizer unchanged. No fee calculations in the API layer.

**CIPHER:** Cascade endpoints are auth-gated via the same HMAC dependency as admin/portfolio routers. Corporate IDs are opaque hashes (no PII). Intervention execution is logged to decision log. The alert store is in-memory (no persistence of sensitive cascade topology data). Graph queries expose dependency_score and volume — these are aggregate metrics, not transaction-level data.

---

## Out of Scope

- Kafka topic emission for cascade alerts (deferred to infrastructure sprint)
- Real-time WebSocket streaming of cascade updates (v1)
- Cascade dashboard frontend (bank builds this)
- Decision log integration for intervention execution (requires C7 agent extension — Sprint 4+)
- Rate limiting on analyze endpoint (defer to API gateway infra)
