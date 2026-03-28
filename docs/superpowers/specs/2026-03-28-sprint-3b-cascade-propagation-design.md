# Sprint 3b — Cascade Propagation Engine Design Spec

**Status:** Approved (CTO self-review)
**Sprint:** 3b of 23-session build program (Session 7)
**Prerequisites:** Sprint 3a (corporate graph nodes — CascadeGraph, CorporateEntityResolver)
**Product:** P5 Supply Chain Cascade Detection & Prevention
**Blueprint Reference:** Sections 5.1-5.4, 7.6, 8.2-8.3

---

## Problem Statement

Sprint 3a built the corporate-level graph (CascadeGraph) — nodes are corporates, edges are supply chain payment relationships with Bayesian-smoothed dependency scores. But a graph alone does not answer the critical question: **when Corporate A fails to pay, which downstream corporates are at risk, how much value is at risk, and where should bridge loans be deployed to prevent the most cascade damage?**

Sprint 3b builds three capabilities on top of CascadeGraph:

1. **BFS Cascade Propagation** — computes multi-hop failure probabilities (P_cascade) using probability multiplication with threshold pruning
2. **Cascade Value at Risk (CVaR)** — quantifies the dollar impact at each node and total cascade amplification factor
3. **Intervention Optimizer** — greedy weighted set cover that identifies the minimum-cost bridge loans maximising cascade value prevented per dollar spent
4. **Cascade Alert Generation** — structured alert dataclass for bank risk desk consumption (Sprint 3d wires this to C7 API)

---

## Design Decision: Propagation + Optimizer in One Sprint

The blueprint separates these into Sprint 3 (propagation) and Sprint 4 (optimizer). CTO override — they share data structures (`CascadeResult` feeds `InterventionOptimizer`), the optimizer is ~80 lines, and splitting them creates a sprint with no testable end-to-end workflow. Combining them produces a self-contained engine: failure in → risk quantified → intervention plan out.

---

## Component Design

### 1. Additional Constants (`lip/p5_cascade_engine/constants.py`)

```python
# Intervention optimizer
INTERVENTION_FEE_RATE_BPS = 200  # Default bridge loan fee (bps annualised)
CASCADE_ALERT_EXCLUSIVITY_HOURS = 4  # Bank exclusivity window for intervention
CASCADE_ALERT_SEVERITY_HIGH_USD = Decimal("10000000")  # >= $10M = HIGH severity
CASCADE_ALERT_SEVERITY_MEDIUM_USD = Decimal("1000000")  # >= $1M = MEDIUM severity
```

### 2. Cascade Propagation Data Structures (`lip/p5_cascade_engine/cascade_propagation.py`)

**CascadeRiskNode** — one node in the cascade propagation result.

```python
@dataclass
class CascadeRiskNode:
    corporate_id: str
    cascade_probability: float       # P(cascade reaches this node)
    incoming_volume_at_risk_usd: float  # Volume on edge from parent
    downstream_value_at_risk_usd: float  # CVaR of this node's downstream subtree
    hop_distance: int                # Hops from origin
    parent_corporate_id: str         # For intervention tracing
```

**CascadeResult** — complete result of cascade propagation from a single origin.

```python
@dataclass
class CascadeResult:
    origin_corporate_id: str
    trigger_type: str                  # "PAYMENT_FAILURE" or "CORRIDOR_STRESS"
    cascade_map: Dict[str, CascadeRiskNode]  # {corporate_id: risk_node}
    total_value_at_risk_usd: float     # Sum of all cascade CVaR
    origin_outgoing_volume_usd: float  # Direct outgoing volume from origin
    cascade_amplification_factor: float  # total_var / origin_volume
    nodes_evaluated: int
    nodes_above_threshold: int
    max_hops_reached: int
    timestamp: float
```

### 3. CascadePropagationEngine (`lip/p5_cascade_engine/cascade_propagation.py`)

**`propagate()` algorithm (Section 5.2 of blueprint):**

```
ALGORITHM: BFS with Probability Multiplication and Threshold Pruning
INPUT:
    graph: CascadeGraph
    origin_node: str (failed/stressed corporate)
    threshold: float (default CASCADE_INTERVENTION_THRESHOLD = 0.70)
    max_hops: int (default CASCADE_MAX_HOPS = 5)
OUTPUT:
    CascadeResult

INITIALISE:
    queue = FIFO with (origin_node, probability=1.0, hop=0, parent=None)
    visited = {origin_node}
    cascade_map = {}

BFS LOOP:
    u, p_u, hop, parent = dequeue
    IF hop >= max_hops: skip children

    FOR EACH (u, v) in adjacency WHERE v not in visited:
        p_v = p_u * dependency_score(u, v)
        IF p_v >= threshold:
            cascade_map[v] = CascadeRiskNode(
                corporate_id=v,
                cascade_probability=p_v,
                incoming_volume_at_risk_usd=edge(u, v).total_volume_30d,
                downstream_value_at_risk_usd=0.0,  # computed in second pass
                hop_distance=hop + 1,
                parent_corporate_id=u,
            )
            visited.add(v)
            enqueue(v, p_v, hop + 1, u)

SECOND PASS — CVaR computation (bottom-up):
    Sort cascade_map nodes by hop_distance DESC.
    For each node v (deepest first):
        children_cvar = sum(
            child.cascade_probability * child.incoming_volume_at_risk_usd
            + child.downstream_value_at_risk_usd
            for child in cascade_map.values()
            if child.parent_corporate_id == v
        )
        v.downstream_value_at_risk_usd = children_cvar

TOTAL CVaR:
    total_var = sum(
        node.cascade_probability * node.incoming_volume_at_risk_usd
        for node in cascade_map.values()
    )
```

**Mathematical properties:**
1. **Monotonic decay:** d(u,v) in [0,1] so P_cascade decreases at every hop
2. **Exponential pruning:** Average dependency ~0.4 means threshold 0.70 prunes after 1 hop for diversified supply chains
3. **Complexity:** O(V + E) BFS, O(k) in practice where k = nodes above threshold

**Why a second pass for downstream CVaR:** The BFS computes cascade probability and direct volume at risk for each node. But the intervention optimizer needs to know: "if I bridge this edge, how much total downstream cascade do I prevent?" This requires bottom-up aggregation — the deepest nodes have zero downstream value, and each parent's downstream value is the sum of its children's cascade risk.

### 4. Intervention Optimizer (`lip/p5_cascade_engine/intervention_optimizer.py`)

**InterventionAction** — a single bridge loan recommendation.

```python
@dataclass
class InterventionAction:
    source_corporate_id: str       # Paying corporate (bridge prevents this failure)
    target_corporate_id: str       # Receiving corporate (bridge protects this node)
    bridge_amount_usd: float       # = edge volume (bridge covers the payment)
    cascade_value_prevented_usd: float  # = CVaR(target) + downstream CVaR
    cost_efficiency_ratio: float   # value_prevented / bridge_amount
    priority: int                  # 1 = highest priority
```

**InterventionPlan** — ranked set of bridge loan recommendations.

```python
@dataclass
class InterventionPlan:
    interventions: List[InterventionAction]
    total_cost_usd: float
    total_value_prevented_usd: float
    remaining_budget_usd: float
    budget_utilization_pct: float
```

**Greedy weighted set cover algorithm (Section 5.4 of blueprint):**

```
ALGORITHM: InterventionOptimise
INPUT:
    cascade_result: CascadeResult
    graph: CascadeGraph
    budget_usd: float
    fee_rate_bps: int (default 200)
OUTPUT:
    InterventionPlan

INITIALISE:
    remaining_budget = budget_usd
    plan = []
    protected = set()
    priority = 1

GREEDY LOOP:
    WHILE remaining_budget > 0:
        best_ratio = 0.0
        best_candidate = None

        FOR EACH node in cascade_result.cascade_map:
            IF node.corporate_id in protected: continue
            edge = graph.adjacency[node.parent_corporate_id][node.corporate_id]
            bridge_cost = edge.total_volume_30d
            IF bridge_cost > remaining_budget: continue
            IF bridge_cost <= 0: continue

            # Value prevented = this node's CVaR + all downstream CVaR
            value_prevented = (
                node.cascade_probability * node.incoming_volume_at_risk_usd
                + node.downstream_value_at_risk_usd
            )

            ratio = value_prevented / bridge_cost
            IF ratio > best_ratio:
                best_ratio = ratio
                best_candidate = (node, edge, bridge_cost, value_prevented)

        IF best_candidate is None: BREAK

        node, edge, cost, value = best_candidate
        plan.append(InterventionAction(...))
        remaining_budget -= cost
        protected.add(node.corporate_id)
        protected |= descendants(node)  # All downstream nodes are protected
        priority += 1

RETURN InterventionPlan(plan, ...)
```

**Greedy guarantee:** (1 - 1/e) >= 63.2% of optimal. Empirically >90% for tree-like supply chains.

**`_get_descendants()` helper:** BFS from a node to find all downstream corporate IDs in the cascade map. Used to mark entire subtrees as protected when a bridge intervention covers the root.

### 5. Cascade Alerts (`lip/p5_cascade_engine/cascade_alerts.py`)

**CascadeAlert** — structured alert for bank risk desk consumption.

```python
@dataclass
class CascadeAlert:
    alert_id: str                    # "CASC-{date}-{seq}"
    alert_type: str                  # "CASCADE_PROPAGATION"
    severity: str                    # "HIGH" (>=$10M), "MEDIUM" (>=$1M), "LOW"
    origin_corporate_id: str
    origin_sector: str
    origin_jurisdiction: str
    cascade_result: CascadeResult
    intervention_plan: Optional[InterventionPlan]
    timestamp: float
    expires_at: float                # timestamp + 4h exclusivity
```

**`build_cascade_alert()` factory function:**

1. Run propagation from origin
2. Check total CVaR against CASCADE_ALERT_THRESHOLD_USD — if below, return None
3. If above, run intervention optimizer
4. Compute severity from CVaR thresholds
5. Generate alert_id with timestamp-based sequence
6. Set expires_at = timestamp + CASCADE_ALERT_EXCLUSIVITY_HOURS

**Severity mapping (QUANT sign-off required):**
- `total_value_at_risk_usd >= $10M` → HIGH
- `total_value_at_risk_usd >= $1M` → MEDIUM
- Below $1M → no alert (filtered by CASCADE_ALERT_THRESHOLD_USD)

---

## Data Flow

```
CascadeGraph (from Sprint 3a)
    |
    v
CascadePropagationEngine.propagate(graph, origin_node)
    |  BFS with probability multiplication
    |  Threshold pruning at CASCADE_INTERVENTION_THRESHOLD
    |  Bottom-up CVaR computation
    |
    v
CascadeResult
    |  cascade_map: {corp_id: CascadeRiskNode}
    |  total_value_at_risk_usd
    |  cascade_amplification_factor
    |
    v
InterventionOptimizer.optimize(cascade_result, graph, budget)
    |  Greedy weighted set cover
    |  Bridge cost = edge volume
    |  Value = CVaR + downstream CVaR
    |
    v
InterventionPlan
    |  Ranked list of InterventionAction
    |  Total cost, value prevented, budget utilization
    |
    v
build_cascade_alert(graph, origin, budget)
    |  Propagate + optimize + severity + alert_id
    |
    v
CascadeAlert
    |  Ready for Sprint 3d (C7 Cascade API)
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `lip/p5_cascade_engine/constants.py` | Add intervention/alert constants |
| Create | `lip/p5_cascade_engine/cascade_propagation.py` | CascadeRiskNode, CascadeResult, CascadePropagationEngine |
| Create | `lip/p5_cascade_engine/intervention_optimizer.py` | InterventionAction, InterventionPlan, InterventionOptimizer |
| Create | `lip/p5_cascade_engine/cascade_alerts.py` | CascadeAlert, build_cascade_alert factory |
| Modify | `lip/p5_cascade_engine/__init__.py` | Export new classes |
| Create | `lip/tests/test_p5_cascade_propagation.py` | BFS propagation + CVaR tests |
| Create | `lip/tests/test_p5_intervention.py` | Intervention optimizer tests |
| Create | `lip/tests/test_p5_cascade_alerts.py` | Alert generation tests |

---

## Testing Strategy

- **TDD throughout**: Tests written first, then implementation
- **Propagation**: Linear chain (A->B->C->D), star graph (A->B,C,D), diamond (A->B->D, A->C->D), worked BMW/Bosch example from blueprint Section 5.3
- **Threshold pruning**: Verify nodes below threshold are excluded from cascade_map
- **Max hops**: Verify BFS stops at CASCADE_MAX_HOPS
- **CVaR**: Manual calculation against known topology, amplification factor = total_var / origin_volume
- **Intervention optimizer**: Single intervention, multiple interventions, budget exhaustion, empty cascade
- **Greedy ordering**: Verify highest efficiency ratio selected first
- **Descendant protection**: Verify bridging a node protects all downstream nodes
- **Alerts**: Severity classification, alert_id format, below-threshold returns None, exclusivity window
- **Edge cases**: Empty graph, unknown origin, single node, no edges above threshold
- **Regression**: All Sprint 3a tests pass unchanged

---

## QUANT / CIPHER Review Notes

**QUANT:** Cascade probability multiplication is mathematically sound — dependency_score in [0,1] guarantees monotonic decay. CVaR formula: P_cascade(v) * volume(parent, v) matches blueprint Section 5.3. Intervention optimizer uses greedy set cover with (1-1/e) approximation guarantee. All financial thresholds (CASCADE_ALERT_THRESHOLD_USD, severity levels) are Decimal constants requiring QUANT sign-off.

**CIPHER:** Cascade alerts reference `corporate_id` (opaque hash), not UETRs or corporate names — GDPR compliant per blueprint Section 3.3. Alert payloads include sector and jurisdiction for risk desk context but no PII. The 4-hour exclusivity window is a business term, not a security boundary.

---

## Out of Scope

- C7 Cascade API endpoints (Sprint 3d)
- Cascade-adjusted PD in C2 (Sprint 3c)
- C3 cascade alert trigger on upstream failure (Sprint 3c)
- C5 StressRegimeEvent → cascade re-evaluation (Sprint 3c)
- Kafka topic emission for cascade alerts (Sprint 3d)
- Real-time streaming cascade updates (v1, not v0)
- Non-linear cascade amplification / GNN model (patent claim, v1)
