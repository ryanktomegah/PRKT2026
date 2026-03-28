# Sprint 3a — Corporate-Level Graph Nodes Design Spec

**Status:** Approved (CTO self-review)
**Sprint:** 3a of 23-session build program (Session 6)
**Prerequisites:** Sprint 2a-2d (P3 multi-tenant foundation), existing BICGraphBuilder (C1)
**Product:** P5 Supply Chain Cascade Detection & Prevention

---

## Problem Statement

BPI's `BICGraphBuilder` maps payment flows between BIC codes (financial institutions). P5 requires mapping between corporate entities (the actual supply chain participants behind those institutions). A single corporate may transact through multiple BICs (e.g., BMW uses COBADEFF for EUR payments and BNPAFRPP for USD payments), and a single BIC services thousands of corporates. Without corporate-level entity resolution, cascade risk analysis operates at the wrong granularity — it sees bank-to-bank payment corridors, not supplier-to-customer dependency chains.

Sprint 3a builds the **corporate entity resolution layer** — the bridge between BIC-level payment graphs (C1) and corporate-level cascade analysis (Sprint 3b). This layer:

1. Elevates BIC-level `PaymentEdge` objects to corporate-level `CorporateEdge` objects
2. Computes corporate node features (8-dimensional vector for downstream ML consumption)
3. Computes cascade centrality (betweenness) to identify high-impact nodes
4. Establishes the `CascadeGraph` data structure consumed by Sprint 3b's BFS propagation engine

---

## Design Decision: Option C (Hybrid Module Layout)

**Three options considered:**

| Option | Layout | Trade-off |
|--------|--------|-----------|
| A | Everything in `lip/c1_failure_classifier/` | Mixes ML inference + domain logic; C1 already 6,697 LOC |
| B | Everything in `lip/p5_cascade_engine/` | Clean boundary but corporate features divorced from C1 pipeline |
| **C** | **Data structures + resolver + features in `lip/p5_cascade_engine/`; C1 unchanged** | **Follows blueprint module layout; clean ownership; Sprint 3b extends naturally** |

**Rationale:** C1 is the ML failure classifier — its responsibility is inference, not corporate entity resolution. The corporate graph is a P5 domain concept that happens to produce features consumed by C1. By placing it in `lip/p5_cascade_engine/`, Sprint 3b (cascade propagation) and Sprint 3d (intervention API) naturally extend the same module without cross-cutting C1.

---

## Component Design

### 1. P5 Constants (`lip/p5_cascade_engine/constants.py`)

Cascade-specific thresholds and parameters. All require QUANT sign-off to change.

```python
# Cascade propagation thresholds (QUANT sign-off required)
CASCADE_INTERVENTION_THRESHOLD = 0.70       # Minimum cascade probability for intervention plan
CASCADE_ALERT_THRESHOLD_USD = Decimal("1000000")  # $1M — min CVaR to trigger bank alert
CASCADE_ALERT_DEPENDENCY_THRESHOLD = 0.50   # Min dependency_score for C3 cascade trigger
CASCADE_MAX_HOPS = 5                        # Max BFS depth (>95% of value within 3 hops)
CASCADE_DISCOUNT_CAP = Decimal("0.30")      # Max PD reduction from cascade discount
INTERVENTION_BUDGET_SHARE = Decimal("0.25") # Max fraction of bridge capacity for cascade

# Entity resolution
CORPORATE_EDGE_MIN_PAYMENTS_30D = 2         # Min payment count to form corporate edge
CORPORATE_CENTRALITY_BATCH_INTERVAL_HOURS = 4  # Betweenness recomputation interval
```

### 2. Corporate Graph Data Structures (`lip/p5_cascade_engine/corporate_graph.py`)

**CorporateNode** — dataclass representing a corporate entity in the supply chain graph.

```python
@dataclass
class CorporateNode:
    corporate_id: str           # Opaque hash of corporate entity ID (bank-provided)
    name_hash: str              # SHA-256 of normalised name (deduplication)
    bics: frozenset[str]        # BIC codes through which this corporate transacts
    sector: str                 # GICS Level 2 industry sector
    jurisdiction: str           # ISO 3166-1 alpha-2 from primary BIC chars 4-5
    total_incoming_volume_30d: float   # Rolling 30d incoming USD volume
    total_outgoing_volume_30d: float   # Rolling 30d outgoing USD volume
    dependency_scores: Dict[str, float]  # {upstream_corp_id: smoothed_score}
    cascade_centrality: float = 0.0     # Betweenness centrality (batch-computed)
```

**Why `frozenset` for `bics`:** Immutable after construction. A corporate's BIC set doesn't change mid-analysis. Hashable for use as dict keys if needed.

**CorporateEdge** — directed supply chain payment edge between two corporates.

```python
@dataclass
class CorporateEdge:
    source_corporate_id: str     # Paying corporate (upstream)
    target_corporate_id: str     # Receiving corporate (downstream)
    total_volume_30d: float      # Rolling 30d payment volume (USD)
    payment_count_30d: int       # Distinct payments in 30d
    dependency_score: float      # Volume-weighted mean of BIC-level scores
    failure_rate_30d: float      # Fraction of failed payments
    avg_settlement_hours: float  # Mean settlement time (0.0 if C9 not available)
    last_payment_timestamp: float  # Most recent payment epoch
```

**CascadeGraph** — immutable snapshot of the corporate-level directed graph.

```python
@dataclass
class CascadeGraph:
    nodes: Dict[str, CorporateNode]
    edges: List[CorporateEdge]
    adjacency: Dict[str, Dict[str, CorporateEdge]]  # {source: {target: edge}}
    reverse_adjacency: Dict[str, Dict[str, CorporateEdge]]  # {target: {source: edge}}
    build_timestamp: float
    node_count: int
    edge_count: int
    avg_dependency_score: float
    max_cascade_centrality_node: str  # Corporate ID with highest betweenness
```

**Why `reverse_adjacency`:** Sprint 3b's cascade propagation needs both forward (who does this corp pay?) and backward (who pays this corp?) lookups. Building it during graph construction avoids O(E) traversal at query time.

**Methods on CascadeGraph:**

```python
def compute_centrality(self) -> None:
    """Compute betweenness centrality for all nodes (Brandes algorithm).

    Updates each CorporateNode.cascade_centrality in place.
    O(V * E) — run as batch job, not real-time.
    """

def get_node_features(self, corporate_id: str) -> np.ndarray:
    """Return 8-dimensional corporate node feature vector."""

def get_corporates_on_corridor(self, corridor: str) -> List[str]:
    """Return corporate IDs with payment volume on the given currency corridor."""

def get_downstream_dependents(self, corporate_id: str, threshold: float = 0.2) -> List[str]:
    """Return corporate IDs downstream of the given corporate with dependency >= threshold."""
```

### 3. Corporate Entity Resolver (`lip/p5_cascade_engine/entity_resolver.py`)

**Responsibility:** Elevate a BIC-level `CorridorGraph` to a corporate-level `CascadeGraph`.

```python
class CorporateEntityResolver:
    def __init__(
        self,
        bic_to_corporate: Dict[str, str],
        corporate_metadata: Optional[Dict[str, Dict]] = None,
    ) -> None:
        """
        Args:
            bic_to_corporate: Bank-provided mapping {bic: corporate_id}.
                BICs not in this mapping are excluded from the corporate graph
                (they represent non-enrolled banks or unmapped entities).
            corporate_metadata: Optional {corporate_id: {"name_hash": ..., "sector": ..., "jurisdiction": ...}}.
                When not provided, jurisdiction is derived from BIC chars 4-5
                and sector defaults to "UNKNOWN".
        """
```

**`resolve()` algorithm:**

1. Iterate all `PaymentEdge` objects from the `CorridorGraph`
2. For each edge, resolve `sending_bic` and `receiving_bic` to corporate IDs
3. **Skip** if either BIC is not in the mapping (unmapped entity)
4. **Skip** if `bic_to_corporate[sending_bic] == bic_to_corporate[receiving_bic]` (intra-corporate transfer — same corporate using different BICs)
5. **Skip** if `edge.amount_usd <= 0` (zero-volume edge — prevents division-by-zero in dependency aggregation)
6. Aggregate edges by `(source_corp, target_corp)` pair:
   - Sum `amount_usd` → `total_volume_30d`
   - Count distinct UETRs → `payment_count_30d`
   - Volume-weighted mean of `dependency_score`
   - Weighted failure rate from `edge.features.get("failed", False)` — boolean flag set by C5; edges without this key are treated as non-failed
   - Max timestamp → `last_payment_timestamp`
6. Filter: discard corporate edges with `payment_count_30d < CORPORATE_EDGE_MIN_PAYMENTS_30D`
7. Build `CorporateNode` for each unique corporate:
   - `bics` = all BICs mapping to this corporate
   - `total_incoming_volume_30d` = sum of incoming edge volumes
   - `total_outgoing_volume_30d` = sum of outgoing edge volumes
   - `dependency_scores` = {upstream_corp: edge.dependency_score for each incoming edge}
   - `jurisdiction` from metadata or primary BIC chars 4-5
   - `sector` from metadata or "UNKNOWN"
8. Construct `CascadeGraph` with adjacency + reverse_adjacency

**Dependency score aggregation formula:**

When corporate pair (A, B) has N BIC-level corridors with volumes `w_i` and dependency scores `d_i`:

```
dependency_score(A→B) = sum(w_i * d_i) / sum(w_i)
```

This preserves the Bayesian smoothing applied by BICGraphBuilder at the BIC level.

### 4. Corporate Node Features (`lip/p5_cascade_engine/corporate_features.py`)

8-dimensional feature vector per corporate node (extending C1's 8-dim BIC features):

| Idx | Feature | Description | Computation |
|-----|---------|-------------|-------------|
| 0 | `total_incoming_volume_30d` | log1p of total incoming USD | `log1p(node.total_incoming_volume_30d)` |
| 1 | `total_outgoing_volume_30d` | log1p of total outgoing USD | `log1p(node.total_outgoing_volume_30d)` |
| 2 | `supplier_count` | Distinct upstream corporates | `len(reverse_adjacency[corp_id])` |
| 3 | `customer_count` | Distinct downstream corporates | `len(adjacency[corp_id])` |
| 4 | `max_dependency_score` | Highest dependency on any sender | `max(node.dependency_scores.values(), default=0.0)` |
| 5 | `hhi_supplier_concentration` | HHI of incoming payment volumes | Herfindahl-Hirschman index (computed directly — NOT from PortfolioRiskEngine, which measures loan counterparty concentration, a different metric) |
| 6 | `failure_rate_30d` | Volume-weighted avg failure rate | From incoming edges |
| 7 | `cascade_centrality` | Betweenness centrality | From `compute_centrality()` |

**HHI computation:**
```
shares = [volume_from_supplier_i / total_incoming_volume for each supplier]
hhi = sum(s^2 for s in shares)
```
HHI = 1.0 means single-supplier dependency (maximum concentration risk). HHI near 0 means highly diversified.

**Edge case guards:**
- If `node.dependency_scores` is empty (no upstream corporates): `max_dependency_score = 0.0`
- If `total_incoming_volume_30d == 0`: `hhi = 0.0`, `failure_rate_30d = 0.0`
- If node has no edges at all: return `np.zeros(8)` (isolated node)

### 5. Cascade Centrality — Brandes Algorithm

Betweenness centrality identifies nodes whose failure would disrupt the most supply chain paths. A node with high betweenness sits on many shortest paths — its failure cascades through more of the network.

**Implementation:** Brandes (2001) algorithm, O(V * E) for unweighted graphs. We use the unweighted variant because we care about path *structure*, not path *cost*.

```python
def _brandes_betweenness(adjacency: Dict[str, Dict[str, CorporateEdge]]) -> Dict[str, float]:
    """Compute betweenness centrality using Brandes algorithm.

    For each source node s:
      1. BFS from s to compute shortest path counts and predecessors
      2. Back-propagate dependency values from leaves to source
      3. Accumulate centrality for intermediate nodes

    Returns {corporate_id: centrality_score} normalized to [0, 1].
    """
```

**No NetworkX dependency.** The blueprint mentions NetworkX as shorthand; CTO override — adding NetworkX (320K+ LOC, 50+ transitive dependencies) for a single 60-line algorithm is not justified. The Brandes (2001) algorithm is well-documented and the implementation will be thoroughly tested against known graph topologies (star, chain, diamond, cycle).

**Immutability note:** `CascadeGraph` is described as an "immutable snapshot" but `compute_centrality()` mutates `CorporateNode.cascade_centrality` in place. This is intentional — centrality is a batch computation that runs after graph construction. The graph is immutable in the sense that nodes and edges are not added/removed after `resolve()`, but node attributes are updated by batch computations. This follows the same pattern as BICGraphBuilder's `_max_timestamp` updates.

---

## Data Flow

```
Bank Payment Data Feed
    │
    v
C5 ISO 20022 Processor → NormalizedEvent
    │
    v
BICGraphBuilder.add_payment(PaymentEdge)
    │
    v
BICGraphBuilder.build_graph() → CorridorGraph
    │                              (BIC-level: nodes=BICs, edges=payment corridors)
    │
    v
CorporateEntityResolver.resolve(bic_graph) → CascadeGraph
    │  ├── Bank-provided bic_to_corporate mapping
    │  ├── Intra-corporate transfers filtered out
    │  ├── BIC edges aggregated to corporate edges (volume-weighted)
    │  └── CorporateNode built with 30d rolling volumes + dependency scores
    │
    v
CascadeGraph.compute_centrality()
    │  └── Brandes betweenness centrality (batch, every 4h)
    │
    v
CascadeGraph.get_node_features(corporate_id) → np.ndarray(8,)
    │  └── [volume_in, volume_out, supplier_count, customer_count,
    │       max_dep, hhi, failure_rate, centrality]
    │
    v
[Sprint 3b: CascadePropagationEngine.propagate(origin, graph)]
[Sprint 3c: C2.compute_cascade_adjusted_pd(base_pd, cascade_prob)]
[Sprint 3d: C7 Coordinated Intervention API]
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/p5_cascade_engine/__init__.py` | Module exports |
| Create | `lip/p5_cascade_engine/constants.py` | P5 cascade thresholds and parameters |
| Create | `lip/p5_cascade_engine/corporate_graph.py` | CorporateNode, CorporateEdge, CascadeGraph |
| Create | `lip/p5_cascade_engine/entity_resolver.py` | CorporateEntityResolver (BIC → corporate) |
| Create | `lip/p5_cascade_engine/corporate_features.py` | 8-dim corporate node feature vector |
| Create | `lip/tests/test_p5_corporate_graph.py` | TDD: data structures, entity resolution, features, centrality |

---

## Testing Strategy

- **TDD throughout**: Tests written first, then implementation
- **Entity resolution**: Multi-BIC corporates, intra-corporate transfer filtering, unmapped BIC exclusion, minimum payment count filtering
- **Dependency score aggregation**: Volume-weighted mean matches manual calculation
- **Feature computation**: Shape (8,), each feature correct for known inputs
- **Centrality**: Known graph topologies (star, chain, diamond) with expected centrality values
- **Edge cases**: Empty graph, single node, all intra-corporate, no mapped BICs
- **Regression**: All existing C1 tests pass unchanged

---

## QUANT / CIPHER Review Notes

**QUANT:** Dependency score aggregation uses volume-weighted mean to preserve BICGraphBuilder's Bayesian smoothing. The formula `sum(w_i * d_i) / sum(w_i)` is exact (no rounding). Cascade centrality is structural (graph topology), not financial math — no Decimal arithmetic needed. HHI is a standard concentration metric (0 = diversified, 1 = concentrated).

**CIPHER:** `corporate_id` is an opaque hash provided by the bank. BPI never sees the corporate's real name or identifier — only the hash. `name_hash` is SHA-256 of normalised name for deduplication only. No PII is stored in the graph. Cascade alerts to the bank reference `corporate_id`, not specific UETRs (GDPR compliance per blueprint §3.3).

---

## Out of Scope

- Cascade propagation algorithm (Sprint 3b)
- Intervention optimiser (Sprint 3b)
- Cascade-adjusted PD in C2 (Sprint 3c)
- Coordinated intervention API in C7 (Sprint 3d)
- C3 cascade alert trigger (Sprint 3c/3d)
- Real-time centrality updates (batch every 4h is sufficient per blueprint)
- Bank onboarding API for BIC→corporate mapping (infrastructure — provided as Dict)
