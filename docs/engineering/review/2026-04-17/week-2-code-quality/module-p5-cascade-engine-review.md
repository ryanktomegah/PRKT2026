# P5 Cascade Engine — Code Quality & Correctness Review

**Sprint**: Pre-Lawyer Review (Day 12, Task 12.2)
**Date**: 2026-04-19
**Scope**: `lip/p5_cascade_engine/` (9 files) + cascade consumer in `lip/c2_pd_model/fee.py::compute_cascade_adjusted_pd`
**Reviewers**: QUANT (cascade-to-fee math) + ARIA (propagation model)
**Branch**: `codex/pre-lawyer-review`
**Aggregate grade**: **A−**

---

## 1. Executive summary

P5 models supply-chain payment contagion: starting from a failed payment at one corporate, BFS propagates failure probability to supplier/customer neighbours on a corporate ownership graph, outputs a `cascade_value_prevented` figure, and passes it to `fee.py::compute_cascade_adjusted_pd` to apply a bounded PD discount. The module is **materially one of the strongest in the repo** on three axes:

- **Defence-in-depth on the cascade→fee boundary**. Even if the upstream propagation result is wrong, adversarial, or unbounded, the fee-side has three independent ceilings: (1) `CASCADE_DISCOUNT_CAP = 0.30` hard cap on PD reduction (fee.py:313), (2) `compute_fee_bps_from_el` re-applies the 300 bps platform floor, (3) the cascade path re-validates the 800 bps warehouse floor (fee.py:327). Worst-case adversarial `cascade_value_prevented` can only reduce fee to `0.7 × base_fee`, still subject to the warehouse floor.
- **Canonical constant binding**. `INTERVENTION_FEE_RATE_BPS = FEE_FLOOR_BPS` at `constants.py:41` with a module-level comment: *"The intervention optimiser must never estimate costs below the fee floor — doing so would make bridge loans appear cheaper than they can ever actually be priced, overstating cost-efficiency and biasing the greedy selection. QUANT sign-off is required to decouple this from FEE_FLOOR_BPS."* This is exactly the kind of binding that prevents drift.
- **BFS termination is provably correct**. `visited` set (propagation.py:93, 110, 119–120) prevents re-visits → each node processed at most once → termination in O(V+E). `max_hops = 5` hard caps depth; `threshold = 0.70` prunes low-probability branches.

Two HIGH findings are architectural and don't block this sprint:

- **P5-H1**: `CascadeGraph` has no cryptographic signature / version hash / builder attestation. An attacker with write access to the in-memory graph could inflate cascade values. Same class as C8-H2 (RevenueMetering tenant_id). **Document** — cross-module architectural work.
- **P5-H2**: The BFS uses `visited` to prevent re-visit, but this means if a higher-probability path to a node exists via a longer route, it's missed (first-reached wins, not maximum-probability). Conservative — **underestimates** cascade, which is fail-safe for fee pricing — but subtly incorrect vs. the stated P5 blueprint §5.2 algorithm. **Document** for ARIA; not a correctness risk for the fee side.

No inline fixes applied this sprint; all findings are document-only per plan policy (Critical inline; High ≤30 lines / 1 file inline else defer; Medium / Low / Info document only).

---

## 2. Scoring

| Axis | Grade | Rationale |
|------|-------|-----------|
| Cascade→fee math correctness | **A** | `compute_cascade_adjusted_pd` (fee.py:251–342) guards `base_pd ∈ [0,1]`, guards `intervention_cost > 0 and cascade_value_prevented > 0` (no divide-by-zero, no negative discount), caps discount at 30%, re-validates 800 bps warehouse floor. Three-layer defence-in-depth. |
| Propagation algorithm | **A−** | BFS with `visited`-guard terminates in O(V+E); `max_hops=5` + `threshold=0.70` prune; probabilities multiply by `dependency_score ∈ [0,1]` so monotone non-increasing along any path. Minor: `visited` first-wins vs. max-probability path (P5-H2). |
| Canonical constant discipline | **A** | `INTERVENTION_FEE_RATE_BPS` bound to `FEE_FLOOR_BPS` at source with QUANT sign-off comment; `CASCADE_DISCOUNT_CAP`, `CASCADE_MAX_HOPS`, `CASCADE_ALERT_THRESHOLD_USD` all named with rationale. |
| Input validation | **B+** | Graph-level: `CorporateEdge.dependency_score` has no `[0,1]` enforcement (P5-M1) — if upstream builder produces >1.0, BFS amplifies before threshold cuts. Fee-side re-validation (fee.py:311 `> 0` guards) rescues correctness. |
| Graph integrity | **C+** | `CascadeGraph.build_timestamp` is a float, not a signed attestation. No `graph_hash`, no `signer_id`, no re-signing on mutation (P5-H1). Same architectural gap class as C8-H2. |
| Entity resolution | **B** | `entity_resolver.py` uses exact BIC-string matching against `bic_to_corporate` mapping. No LEI fallback, no fuzzy match, silent drop on unmapped BIC. Dependency on bank data quality is entirely external (P5-M2). |
| Graph freshness | **B** | No refresh logic observed — graph built at startup, read-only thereafter (P5-M3). Stale topology risk is real but the fail-mode is conservative (missed cascade → no discount → higher fee, not lower). |
| Code hygiene | **A−** | Comprehensive type hints, named constants, Decimal in fee boundary, docstrings cite P5 blueprint §5.2/5.3/5.4. Brandes (2001) betweenness centrality implementation cited and faithful (corporate_graph.py:99–146). No hand-written crypto in-module. |

---

## 3. Strengths worth preserving

### S1. Canonical fee-floor binding in P5 constants (`p5_cascade_engine/constants.py:41–50`)

```python
INTERVENTION_FEE_RATE_BPS = FEE_FLOOR_BPS
"""Default bridge loan fee (bps annualised) for cost estimation.

Bound to the canonical ``FEE_FLOOR_BPS`` (300 bps). The intervention
optimiser must never estimate costs below the fee floor — doing so would
make bridge loans appear cheaper than they can ever actually be priced,
overstating cost-efficiency and biasing the greedy selection.

QUANT sign-off is required to decouple this from ``FEE_FLOOR_BPS``.
"""
```

This is the gold standard. The P5 module does not redefine `300` anywhere; it imports the canonical value and documents why decoupling is a QUANT-gated decision. Any other module touching fee-adjacent constants should follow this pattern.

### S2. Three-layer fee defence-in-depth

At `fee.py::compute_cascade_adjusted_pd`:

1. **Input validation** (line 304): `base_pd` must be in `[0, 1]` — raises `ValueError` otherwise.
2. **Discount cap** (line 313): `cascade_discount = min(raw_discount, CASCADE_DISCOUNT_CAP)` — hard 30% ceiling regardless of `cascade_value_prevented` magnitude. Cascade-adjusted PD is guaranteed ≥ `0.7 × base_pd`.
3. **Warehouse floor re-validation** (line 327): `if cascade_adjusted_fee_bps < WAREHOUSE_ELIGIBILITY_FLOOR_BPS: raise ValueError(...)` — SPV-funded loans must meet 800 bps regardless of cascade discount.

Result: no combination of adversarial or buggy `cascade_value_prevented`, `base_pd`, or `intervention_cost` can produce an SPV-funded loan priced below 800 bps.

### S3. Divide-by-zero guarded at the cascade→fee boundary (`fee.py:311`)

```python
if intervention_cost > 0 and cascade_value_prevented > 0:
    raw_discount = cascade_value_prevented / (Decimal("10") * intervention_cost)
    cascade_discount = min(raw_discount, CASCADE_DISCOUNT_CAP)
else:
    cascade_discount = Decimal("0")
```

Both operands checked `> 0` before division. A zero cost → no discount applies, falls through to base PD. A zero value-prevented → same. A negative value-prevented (bug in producer) → no discount. This is correct fail-safe behaviour.

### S4. BFS termination is proved by the code structure

`cascade_propagation.py::propagate`:

- `visited` set (line 93, 110, 119) — each node enters `cascade_map` at most once.
- `hop >= max_hops: continue` (line 116) — hard depth cap at `CASCADE_MAX_HOPS = 5`.
- `p_child >= threshold` pruning (line 101, 123) — at `threshold = 0.70` with dependency_scores typically in `[0.3, 0.9]`, the branching factor collapses within 2–3 hops.

Result: BFS is O(V+E) with a small constant in practice. No runaway recursion is possible even with adversarial graph input.

### S5. Brandes (2001) betweenness centrality faithfully implemented

`corporate_graph.py::_brandes_betweenness` (lines 99–146) implements the canonical Brandes algorithm for unweighted betweenness — the `stack`/`predecessors`/`sigma`/`dist` dependency-accumulation pass is textbook (Brandes, J. Math. Sociol. 2001). Normalisation at line 141–144 divides by `(n-1)(n-2)` for directed graphs — correct.

---

## 4. Findings

### P5-H1 — HIGH — `CascadeGraph` has no cryptographic integrity [DOCUMENT]

**Evidence**: `corporate_graph.py:47–61`:
```python
@dataclass
class CascadeGraph:
    nodes: Dict[str, CorporateNode] = field(default_factory=dict)
    edges: List[CorporateEdge] = field(default_factory=list)
    adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    build_timestamp: float = 0.0
    node_count: int = 0
    ...
```

No `graph_hash`, no `signer_id`, no HMAC field. `build_timestamp` is a plain `float`, not a signed attestation of when and by whom the graph was built. There's no `verify()` method or equivalent integrity check before the graph is consumed by `CascadePropagationEngine.propagate()`.

**Attack surface**:
1. Anyone with write-access to the Python process memory (legitimate or via code-injection) can add phantom edges with `dependency_score = 0.99` between two unrelated corporates to fabricate a large cascade and extract a 30% discount at price time.
2. No audit trail proves the graph in-memory is the graph that entity resolution produced — a tampered mapping or edge table would be silently honoured.

**Why the rating is HIGH not CRITICAL**: The fee-side defence-in-depth (S2 above) caps the financial impact — worst-case exploit reduces fee by 30%, still re-validated against the 800 bps warehouse floor. And the exploit requires either process-memory write or `bic_to_corporate` mapping tampering — not a remote attack. But for a pre-lawyer filing, the graph-integrity gap is the kind of thing a bank's risk committee **will** ask about.

**Fix path** (not applied this sprint):
1. Add `graph_hash: str` field computed as `hmac_sha256(key, canonical_bytes(nodes||edges))`.
2. Add `signer_id: str` and `signed_at: datetime`.
3. `propagate()` verifies `graph_hash` before consuming the graph; on mismatch → `RuntimeError` (fail-closed, same as C8 `KillSwitch` pattern).
4. Integration: entity resolver signs the graph on build; C3/C7 consumers verify before use.

**Owner**: CIPHER + ARIA coordination. **Scheduled**: Week-3 architectural pass.

---

### P5-H2 — HIGH — BFS `visited` set is first-reached, not max-probability [DOCUMENT]

**Evidence**: `cascade_propagation.py:119–120`:
```python
for target_id, edge in graph.adjacency.get(u, {}).items():
    if target_id in visited:
        continue
```

Once a node is in `visited`, it's never re-processed — even if a later BFS iteration would reach it via a path with higher cumulative probability.

**Why this matters**: the P5 blueprint §5.2 algorithm implies the cascade probability at each node is the **maximum** over all paths from the origin. With first-reached BFS:

- Path 1 (2 hops): origin → A (dep 0.8) → B (dep 0.5) → `P(B) = 0.40`
- Path 2 (3 hops): origin → C (dep 0.9) → D (dep 0.9) → B (dep 0.9) → `P(B) = 0.729`

Because BFS explores shallow-first, Path 1 settles `B` at probability 0.40, and when Path 2 would reach `B` at 0.729, it's skipped. **`B`'s cascade probability is understated by 0.329**.

**Direction of the error**: always **conservative** — actual cascade is ≥ reported cascade. Fee-side effect: cascade discount is ≤ what it would otherwise be → fees are higher, not lower. **Fail-safe for pricing**, but the reported `cascade_value_prevented` fed to downstream alerts is under-estimated.

**Why the rating is HIGH not CRITICAL**: the conservative direction means no under-pricing risk. But the algorithm does not match the spec, and the blueprint's empirical claim (">95% of cascade value within 3 hops") was presumably calibrated against the max-probability variant, not the first-reached variant.

**Fix path** (not applied — algorithm change requires ARIA retraining + recalibration of `max_hops`):
1. Replace `visited`-set gating with a `best_probability[node]` dict; re-process a node if a higher-probability path is found (Dijkstra-style relaxation, not BFS).
2. Recalibrate `CASCADE_MAX_HOPS` and `CASCADE_INTERVENTION_THRESHOLD` against the max-probability algorithm.
3. Re-run the ">95% within 3 hops" empirical validation.
4. Data card note on the change.

**Owner**: ARIA + QUANT. **Scheduled**: Week-3 algorithmic review bundle.

---

### P5-M1 — MEDIUM — `CorporateEdge.dependency_score` not bounded to `[0, 1]` [DOCUMENT]

**Evidence**: `corporate_graph.py:33–44`:
```python
@dataclass
class CorporateEdge:
    source_corporate_id: str
    target_corporate_id: str
    total_volume_30d: float = 0.0
    payment_count_30d: int = 0
    dependency_score: float = 0.0
    ...
```

No `__post_init__`, no `@validator`, no clamp. An upstream builder bug or tampered mapping producing `dependency_score = 1.5` would propagate probabilities upward along each hop (`p_u * 1.5`) until the threshold (0.70) eventually cuts — but the threshold cut happens **after** the amplification has already polluted downstream nodes.

**Why MEDIUM, not HIGH**: the fee-side three-layer defence (S2) still bounds the financial impact. And `dependency_score` is computed by the entity resolver from observed payment volumes — the canonical formula (resolver.py:71–77) produces a ratio that is structurally `∈ [0, 1]`. So the bad-data path requires either a resolver bug or tampering.

**Fix path** (not applied per policy — Medium = document):
```python
def __post_init__(self):
    if not 0.0 <= self.dependency_score <= 1.0:
        raise ValueError(
            f"dependency_score={self.dependency_score} out of [0,1] — "
            f"source={self.source_corporate_id} target={self.target_corporate_id}"
        )
```
~5 lines, one file. Could be bundled with the P5-H2 algorithmic pass.

**Owner**: ARIA. **Scheduled**: Week-3.

---

### P5-M2 — MEDIUM — Entity resolver uses exact BIC string matching [DOCUMENT]

**Evidence**: `entity_resolver.py` `resolve()`:
- Line ~42: `source_corp = self._mapping.get(edge.sending_bic)` — exact string key lookup.
- Line ~45: `if source_corp is None: continue` — silent drop on unmapped BIC.

No LEI fallback, no Levenshtein / phonetic match, no cross-check against tax_id or corporate name. No logging of drop rate (how many edges are silently lost because their BICs are unmapped?).

**Operational risk**:
- Data-quality cliff: a typo or case-mismatch in `bic_to_corporate` (`"COBADEFF"` vs `"cobadeff"`) drops the edge.
- New onboarding: a newly-enrolled BIC isn't in the mapping until next refresh → cascade miss.
- No metric for mapping coverage.

**Why MEDIUM**: the dependency on bank data quality is entirely external; LIP can't fix upstream. The right home for the guarantee is the License Agreement warranty, not the code. Relevant to EPG-04/05 scope (pilot-bank certification structure).

**Fix path** (contractual, not code):
1. License Agreement obligation: pilot bank provides `bic_to_corporate` mapping with stated coverage SLA (e.g., ≥99%).
2. Optional: add a `mapping_coverage_pct` metric logged at resolver load; alert below threshold.

**Owner**: REX (contract language) + ARIA (metric). **Scheduled**: pre-pilot-LOI.

---

### P5-M3 — MEDIUM — `CascadeGraph` has no refresh logic [DOCUMENT]

**Evidence**: The graph is built once during app initialization (via `CorporateEntityResolver.resolve()` called once) and stored on `CascadePropagationEngine` as an injected dependency. No refresh method, no TTL, no rebuild trigger.

**Staleness risk**: a new supply-chain relationship forms between two corporates → payments flow between them → they don't appear as connected in the graph until the process restarts or the graph is manually rebuilt. Cascade alerts under-count value at risk.

**Why MEDIUM**: the fail-mode is conservative (missed cascade → no discount applied → higher fee, not lower). But cascade **alerts** to the bank (the valuable product, per the intervention optimizer) become stale.

**Fix path** (not applied — out of sprint scope):
1. Scheduled refresh (daily via APScheduler, per `CORPORATE_CENTRALITY_BATCH_INTERVAL_HOURS = 4`).
2. Or event-driven refresh on significant change (new BIC enrolled, large new payment flow observed).
3. Contractual: License Agreement refresh-cadence obligation.

**Owner**: FORGE (scheduler) + REX (contractual cadence). **Scheduled**: pilot infrastructure work.

---

### P5-L1 — LOW — Intervention optimizer approximation guarantee unvalidated on production graphs [DOCUMENT]

**Evidence**: `intervention_optimizer.py:7–8`:
```python
Greedy guarantee: (1 - 1/e) >= 63.2% of optimal.
Empirically >90% for tree-like supply chain topologies.
```

The `(1 - 1/e)` bound is the standard Nemhauser-Wolsey-Fisher 1978 result for monotone submodular maximisation with a cardinality constraint — this is correctly applied to budget-constrained maximum coverage. The ">90% for tree-like topologies" claim is **unvalidated empirically** in the code — no test, no benchmark, no citation to a data run.

**Impact**: if production corporate graphs are non-tree-like (dense multi-path structures, which is typical for large banking corridors), the actual approximation ratio can degrade toward the 63.2% bound. Intervention plans are suboptimal but still valid.

**Fix path** (Week-3 data card work):
1. Benchmark on the synthetic corporate graph in `dgen` module; record actual ratio vs. ILP optimum for 100–1000 node graphs.
2. Add the benchmark result to `docs/models/p5-model-card.md`.
3. Replace the ">90%" claim with a measured range.

**Owner**: ARIA + DGEN. **Scheduled**: Week-3.

---

### P5-L2 — LOW — Academic citations in blueprint, not in code [DOCUMENT]

**Evidence**: `cascade_propagation.py:1–8` cites "P5 blueprint Section 5.2/5.3" but not the underlying papers. The P5 blueprint (per agent survey) references Josselin & Brechmann 2024 (JFS), Acemoglu et al. 2012 (Econometrica), Barrot & Sauvagnat 2016 (QJE), Baqaee & Farhi 2019 (QJE). None appear in module docstrings.

**Impact**: a bank risk committee or patent counsel reviewing the model sees blueprint-internal citations only. For SR 11-7 §4.1 conceptual soundness documentation, explicit citations at the algorithm site (not just in a blueprint doc) strengthen the model-validation file.

**Fix path** (doc-only, Week-3):
Add citation block to each algorithmic module (`cascade_propagation.py`, `intervention_optimizer.py`) referencing the specific papers that justify the algorithm choice.

**Owner**: REX (model validation file) + ARIA. **Scheduled**: Week-3 model card.

---

### P5-I1 — INFO — `stress_cascade_bridge.py` and `corporate_features.py` not reviewed in depth

**Observation**: This review focused on the cascade→fee boundary (the QUANT-critical path). `stress_cascade_bridge.py` (stress-scenario bridging) and `corporate_features.py` (8-dim corporate node feature vector) were not line-by-line reviewed. They are on the ARIA path, not the fee path.

**Recommendation**: include in Day 13 ARIA review bundle (C1/C2/C4/dgen).

---

### P5-I2 — INFO — `INTERVENTION_BUDGET_SHARE = 0.25` has no external-bound check

**Observation**: `constants.py:26` — *"Maximum fraction of bank bridge lending capacity for cascade interventions"*. The value itself is reasonable (25% of available bridge budget reserved for cascade interventions, leaving 75% for primary pipeline). No corresponding check in `InterventionOptimizer.optimize()` that `budget_usd` arg is actually ≤ `0.25 × total_bridge_capacity` — the constant is documentation only, not enforced.

**Recommendation**: either enforce in optimizer (compare against a capacity source-of-truth) or remove the constant and move the 25% policy to the C8 license token. Week-3 cleanup.

---

## 5. What was applied inline this sprint

**None.** All findings are document-only per plan policy:
- P5-H1, P5-H2: architectural / algorithmic, cross-module scope
- P5-M1, M2, M3: Medium (document per policy)
- P5-L1, L2, I1, I2: Low / Info (document)

## 6. Deferred work summary

| Finding | Severity | Owner | Target |
|---------|----------|-------|--------|
| P5-H1 (graph crypto integrity) | HIGH | CIPHER + ARIA | Week-3 architectural pass |
| P5-H2 (BFS max-probability relaxation) | HIGH | ARIA + QUANT | Week-3 algorithmic bundle |
| P5-M1 (`dependency_score` bounds) | MED | ARIA | Week-3 |
| P5-M2 (entity resolver data quality) | MED | REX | pre-pilot-LOI contract |
| P5-M3 (graph refresh) | MED | FORGE + REX | pilot infrastructure |
| P5-L1 (optimizer empirical validation) | LOW | ARIA + DGEN | Week-3 model card |
| P5-L2 (academic citations in code) | LOW | REX + ARIA | Week-3 model card |
| P5-I1/I2 | INFO | Week-3 cleanup |  |

---

## 7. Files reviewed

| File | LOC (approx) | Review depth |
|------|-------------|--------------|
| `lip/p5_cascade_engine/cascade_propagation.py` | 187 | Full — BFS algorithm, termination, visited-set semantics |
| `lip/p5_cascade_engine/corporate_graph.py` | 147 | Full — dataclass integrity, Brandes impl |
| `lip/p5_cascade_engine/intervention_optimizer.py` | 178 | Full — greedy set-cover, heap usage, approximation claim |
| `lip/p5_cascade_engine/entity_resolver.py` | 166 | Scanned — BIC-mapping path, silent-drop failure mode |
| `lip/p5_cascade_engine/cascade_settlement_trigger.py` | 88 | Scanned — real-time trigger path |
| `lip/p5_cascade_engine/constants.py` | 61 | Full — canonical constant binding verified |
| `lip/p5_cascade_engine/cascade_alerts.py` | — | Not reviewed (ARIA path) |
| `lip/p5_cascade_engine/corporate_features.py` | — | Not reviewed (ARIA path, P5-I1) |
| `lip/p5_cascade_engine/stress_cascade_bridge.py` | — | Not reviewed (ARIA path, P5-I1) |
| `lip/c2_pd_model/fee.py::compute_cascade_adjusted_pd` | 92 | Full — consumer-side defence-in-depth |

---

## 8. Lens sign-off

- **QUANT**: cascade→fee boundary **A**. Three-layer defence prevents adversarial under-pricing. `INTERVENTION_FEE_RATE_BPS = FEE_FLOOR_BPS` binding is the correct pattern.
- **ARIA**: propagation algorithm **A−**. Visited-set semantics (P5-H2) is a quiet departure from the blueprint, but conservative direction. Recommend bundling the relaxation fix with the P5 retraining pass.
- **CIPHER** (coordination): graph integrity (P5-H1) tracks with C8-H2 architectural pattern — both are unsigned in-memory structs consumed across module boundaries. Schedule together.
- **REX**: data card work queued — cascade model validation file and benchmark results (P5-L1, P5-L2).

**Next**: Day 13 — ML Models review bundle (C1 failure classifier, C2 PD ensemble, C4 dispute classifier, dgen synthetic data).
