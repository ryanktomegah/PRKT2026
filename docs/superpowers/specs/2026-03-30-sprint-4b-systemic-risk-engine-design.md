# Sprint 4b — P10 Systemic Risk Engine Design Spec

**Status:** Approved (CTO decision)
**Sprint:** 4b of 23-session build program (Session 11)
**Prerequisites:** Sprint 4a (P10 Anonymizer Foundation)
**Product:** P10 Regulatory Data Product
**Blueprint Reference:** Sections 4.3, 4.4, 7.5

---

## Problem Statement

Sprint 4a built the anonymization engine — the privacy-preserving pipeline that transforms raw bank telemetry into k-anonymous, differentially private corridor statistics. But anonymized data sitting in memory is useless to regulators. Sprint 4b builds the computation layer that transforms anonymized corridor results into actionable systemic risk intelligence: cross-bank failure rate trends, concentration hotspots, and contagion propagation simulations.

---

## Design Principle: Computation Only, No API

Sprint 4b is pure computation — no HTTP endpoints, no FastAPI routers. The Regulatory API (Sprint 4c) will expose these computations. This separation follows the same pattern as P5: cascade engine (computation) was built before cascade API (HTTP layer).

All classes live in the existing `lip/p10_regulatory_data/` package. No new top-level module — keeps P10 cohesive and avoids cross-package import complexity.

---

## Component Design

### 1. Corridor Failure Rate Aggregation (`systemic_risk.py`)

Aggregates `AnonymizedCorridorResult` objects across time periods into trend data.

```python
@dataclass(frozen=True)
class CorridorRiskSnapshot:
    """Point-in-time risk summary for one corridor."""
    corridor: str
    period_label: str
    failure_rate: float
    total_payments: int
    failed_payments: int
    bank_count: int
    trend_direction: str  # "RISING", "FALLING", "STABLE"
    trend_magnitude: float  # rate of change vs prior period
    contains_stale_data: bool

@dataclass(frozen=True)
class SystemicRiskReport:
    """Full systemic risk assessment across all corridors."""
    timestamp: float
    corridor_snapshots: List[CorridorRiskSnapshot]
    overall_failure_rate: float
    highest_risk_corridor: str
    concentration_hhi: float
    systemic_risk_score: float  # 0.0-1.0
    stale_corridor_count: int
    total_corridors_analyzed: int

class SystemicRiskEngine:
    """Cross-institutional payment failure analytics.

    Thread-safe via threading.Lock (matches PortfolioRiskEngine pattern).
    """

    def __init__(self, anonymizer: RegulatoryAnonymizer):
        self._anonymizer = anonymizer
        self._lock = threading.Lock()
        self._history: Dict[str, List[CorridorRiskSnapshot]] = defaultdict(list)
        self._concentration = CorridorConcentrationAnalyzer()
        self._contagion = ContagionSimulator()

    def ingest_results(self, results: List[AnonymizedCorridorResult]) -> None:
        """Ingest anonymized results into the time-series history."""

    def compute_risk_report(self) -> SystemicRiskReport:
        """Compute full systemic risk report from accumulated history."""

    def get_corridor_trend(self, corridor: str, periods: int = 24) -> List[CorridorRiskSnapshot]:
        """Return last N periods of risk snapshots for a corridor."""

    def compute_trend_direction(self, snapshots: List[CorridorRiskSnapshot]) -> Tuple[str, float]:
        """Compute RISING/FALLING/STABLE + magnitude from recent snapshots."""
```

**Trend detection:** Compare last 3 periods' average failure rate against prior 3 periods. Rising if delta > 10% relative increase, falling if delta < -10%, stable otherwise. Simple and auditable — regulators prefer explainable over sophisticated.

### 2. Concentration Metrics (`concentration.py`)

Measures how concentrated payment volume is across corridors, correspondents, and jurisdictions using the Herfindahl-Hirschman Index (HHI).

```python
@dataclass(frozen=True)
class ConcentrationResult:
    """HHI concentration measurement for one dimension."""
    dimension: str  # "corridor", "correspondent", "jurisdiction"
    hhi: float  # 0.0 (perfectly dispersed) to 1.0 (single entity)
    effective_count: float  # 1/HHI — equivalent number of equal participants
    is_concentrated: bool  # HHI > 0.25
    top_entities: List[Tuple[str, float]]  # (entity_id, share) top 5

class CorridorConcentrationAnalyzer:
    """Compute HHI concentration metrics from anonymized corridor data.

    HHI formula: sum(share_i^2) where share_i = volume_i / total_volume.
    HHI > 0.25 = "highly concentrated" (< 4 effective participants).

    Thread-safety: stateless — safe for concurrent use.
    """

    def compute_corridor_concentration(
        self, snapshots: List[CorridorRiskSnapshot]
    ) -> ConcentrationResult:
        """HHI across corridors by payment volume."""

    def compute_jurisdiction_concentration(
        self, snapshots: List[CorridorRiskSnapshot]
    ) -> ConcentrationResult:
        """HHI across jurisdictions (extracted from corridor pairs)."""
```

**Jurisdiction extraction:** From corridor "EUR-USD", extract both "EUR" and "USD" zones. A corridor contributes half its volume to each jurisdiction. Simple heuristic that works for regulatory reporting.

### 3. Contagion Simulation (`contagion.py`)

BFS propagation on a corridor dependency graph built from anonymized payment flows.

```python
@dataclass(frozen=True)
class ContagionNode:
    """One node in the contagion propagation result."""
    corridor: str
    stress_level: float  # 0.0-1.0 propagated stress
    hop_distance: int
    propagation_path: List[str]  # corridor chain from origin

@dataclass(frozen=True)
class ContagionResult:
    """Complete result of a contagion simulation."""
    origin_corridor: str
    shock_magnitude: float
    affected_corridors: List[ContagionNode]
    max_propagation_depth: int
    total_volume_at_risk_usd: float
    systemic_risk_score: float  # 0.0-1.0

class ContagionSimulator:
    """BFS stress propagation across corridor dependency graph.

    Dependency graph: corridors are nodes, edges connect corridors
    that share correspondent banks (from anonymized data). Edge weight =
    Jaccard similarity of bank hash sets. This keeps contagion
    privacy-preserving — no raw bank identifiers used.

    Algorithm:
      1. Seed origin corridor at shock_magnitude
      2. BFS: for each neighbor, propagated_stress = parent_stress * edge_weight * decay
      3. Prune if propagated_stress < threshold (default 0.05)
      4. Stop at max_hops (default 5)
      5. Aggregate: count affected, sum volume at risk, compute systemic score
    """

    def __init__(
        self,
        propagation_decay: float = 0.7,
        max_hops: int = 5,
        stress_threshold: float = 0.05,
    ):
        self._decay = propagation_decay
        self._max_hops = max_hops
        self._threshold = stress_threshold

    def build_dependency_graph(
        self, corridor_bank_sets: Dict[str, Set[str]]
    ) -> Dict[str, Dict[str, float]]:
        """Build adjacency from corridor → bank_hash sets.
        Edge weight = Jaccard similarity of bank sets."""

    def simulate(
        self,
        graph: Dict[str, Dict[str, float]],
        origin_corridor: str,
        shock_magnitude: float,
        corridor_volumes: Optional[Dict[str, float]] = None,
    ) -> ContagionResult:
        """Run BFS contagion from origin corridor."""
```

**Why Jaccard similarity:** Two corridors sharing 4 out of 5 banks have Jaccard = 0.8 — a shock to one likely propagates to the other because the same banks are processing both. This is derived purely from anonymized data (bank hashes, not real BICs). Privacy-preserving by construction.

---

## Constants (QUANT sign-off required)

```python
# ── P10 Systemic Risk Engine — Contagion & Concentration ────────────────
P10_CONTAGION_PROPAGATION_DECAY = Decimal("0.7")    # per-hop stress multiplier
P10_CONTAGION_MAX_HOPS = 5                           # BFS depth limit
P10_CONTAGION_STRESS_THRESHOLD = Decimal("0.05")     # minimum stress to propagate
P10_HHI_CONCENTRATION_THRESHOLD = Decimal("0.25")    # "highly concentrated" marker
P10_TREND_RISING_THRESHOLD = Decimal("0.10")         # 10% relative increase = RISING
P10_TREND_WINDOW_PERIODS = 3                          # periods for trend comparison
P10_MAX_HISTORY_PERIODS = 720                         # 30 days × 24 hours
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `lip/common/constants.py` | Add P10 systemic risk constants |
| Modify | `lip/p10_regulatory_data/constants.py` | Re-export new constants |
| Create | `lip/p10_regulatory_data/systemic_risk.py` | SystemicRiskEngine, CorridorRiskSnapshot, SystemicRiskReport |
| Create | `lip/p10_regulatory_data/concentration.py` | CorridorConcentrationAnalyzer, ConcentrationResult |
| Create | `lip/p10_regulatory_data/contagion.py` | ContagionSimulator, ContagionNode, ContagionResult |
| Modify | `lip/p10_regulatory_data/__init__.py` | Export new classes |
| Create | `lip/tests/test_p10_systemic_risk.py` | TDD test suite |

---

## Testing Strategy

### Corridor Failure Rate (7 tests)
- Ingest single period → snapshot matches input
- Ingest multiple periods → trend computed correctly
- Rising trend detection (>10% increase)
- Falling trend detection (>10% decrease)
- Stable trend detection (within ±10%)
- Stale data flagging (contains_stale_data=True)
- Empty history → empty report

### Concentration Metrics (6 tests)
- Single corridor → HHI = 1.0 (maximum concentration)
- Equal volume across 4 corridors → HHI = 0.25 (threshold boundary)
- Dispersed corridors → HHI < 0.25, is_concentrated=False
- Concentrated corridors → HHI > 0.25, is_concentrated=True
- Jurisdiction extraction from corridor pairs
- Top entities ranking correct

### Contagion Simulation (8 tests)
- Build dependency graph from bank sets (Jaccard similarity)
- Single-hop propagation (stress * weight * decay)
- Multi-hop propagation respects max_hops limit
- Threshold pruning removes weak propagation
- Disconnected corridors not affected
- Circular graph doesn't infinite loop (visited set)
- Zero shock magnitude → no propagation
- Full scenario: 5-corridor graph with known topology

### Integration (5 tests)
- Full pipeline: anonymize → ingest → risk report
- Thread safety: concurrent ingest + compute
- Systemic risk score computation
- Risk report includes concentration + contagion
- Reset clears history

### Regression
- All existing tests pass unchanged (~1785 tests)
- `ruff check lip/` zero errors

---

## QUANT / CIPHER Review Notes

**QUANT:** HHI formula is standard (sum of squared shares). Contagion decay and threshold constants are conservative defaults — regulators can override per-scenario. Trend detection uses simple relative comparison (not regression) for auditability. All concentration ratios use Decimal internally.

**CIPHER:** Contagion graph is built from bank hash sets (not raw BICs) — privacy-preserving by construction. No bank identifiers flow through the systemic risk engine. Corridor names are not considered sensitive (public knowledge). The dependency graph structure itself could reveal bank participation patterns — but Jaccard similarity on k-anonymous sets (k≥5) provides adequate protection.

---

## Out of Scope

- HTTP endpoints (Sprint 4c — Regulatory API)
- PDF/CSV report generation (Sprint 4c)
- Real-time streaming ingestion (infrastructure sprint)
- Historical data persistence (all in-memory for v1)
- C8 regulator access tokens (Sprint 4c)
