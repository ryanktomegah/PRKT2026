# `lip/p5_cascade_engine/` — P5 Supply-Chain Cascade Engine

> **Patent family P5.** A cascade-detection layer that models payment-failure propagation through corporate supply chains, prices the cascade-adjusted PD into C2, triggers C3 settlement events on cascade-confirmed liquidity restoration, and exposes a coordinated intervention API through C7. **Until now, this entire patent family had no reader-facing documentation in the repo.**

**Source:** `lip/p5_cascade_engine/`
**Module count:** 9 modules + `__init__.py`
**Patent reference:** `consolidation files/P5-v0-Implementation-Blueprint.md`, `Patent-Family-Architecture-v2.1.md`
**Sprint history:** Sprint 3a (entity resolution) → 3b (propagation) → 3c (C2/C3/C5 bridges) → 3d (C7 intervention API)

---

## Purpose

When a single payment fails, the LIP base pipeline (Algorithm 1) prices a bridge for that one payment in isolation. But payment failures in cross-border B2B do not happen in isolation — they cluster along supply chains. A delivery failure between Tier-1 supplier and OEM cascades into delivery failures at Tier-2 and Tier-3, which cascade into payment failures across an entire corridor of corporate counterparties within hours.

P5's contribution is to make the cascade visible to LIP **before** the second-order failures arrive at the pipeline. Once the cascade is modelled, three things become possible:

1. **C2 prices the cascade-adjusted PD**, not just the bilateral PD — a payment that is part of a cascade is materially more likely to fail again
2. **C3 triggers a settlement event** when the cascade resolves (liquidity restoration is observable across the cascade graph, not just on the single UETR)
3. **C7 exposes a coordinated intervention API** so a pilot bank's MIPLO can take a single decision over a cluster of related payments instead of fighting the same fire one payment at a time

---

## Modules

| File | Lines | Purpose |
|------|-------|---------|
| `entity_resolver.py` | 150 | `CorporateEntityResolver` — maps payment counterparty identifiers (BIC, IBAN, debtor name strings) to canonical corporate entities. The graph is only as good as this resolution; sloppy resolution produces phantom cascades. |
| `corporate_graph.py` | 144 | `CorporateNode`, `CorporateEdge`, `CascadeGraph` — the in-memory graph data structure. Edges are weighted by historical failure correlation between counterparties. |
| `corporate_features.py` | 78 | `get_corporate_node_features` — extracts the per-node feature vector consumed by `cascade_propagation` (industry, country, tier, historical PD, settlement-time distribution) |
| `cascade_propagation.py` | 180 | `CascadePropagationEngine`, `CascadeResult`, `CascadeRiskNode` — the BFS-based propagation engine that walks the corporate graph from a seed failure event and computes the cascade-adjusted risk at each downstream node |
| `cascade_alerts.py` | 107 | `CascadeAlert`, `build_cascade_alert` — the alert object that fires when a cascade crosses a severity threshold; consumed by C7 and the `cascade_router` HTTP endpoint |
| `intervention_optimizer.py` | 159 | `InterventionOptimizer`, `InterventionAction`, `InterventionPlan` — the optimisation layer that, given a cascade and a budget, picks which subset of payments to bridge to break the cascade with minimum capital. The optimisation objective is "cut the cascade with the least exposure", not "fund every failing payment". |
| `cascade_settlement_trigger.py` | 88 | `CascadeSettlementTrigger` — the bridge into C3 (Sprint 3c). When a cascade resolves, this fires settlement-monitoring events for every loan that was part of the intervention plan. |
| `stress_cascade_bridge.py` | 82 | `StressCascadeBridge` — the bridge into C5 (Sprint 3c). C5's stress-regime detector escalates into the cascade engine when a corridor crosses the stress threshold. |
| `constants.py` | 50 | P5-local constants (cascade depth limits, severity thresholds, intervention budget defaults) — separate from `lip/configs/canonical_numbers.yaml` because they are P5-specific and not part of the platform-wide canonical lock |

---

## How it integrates with the base pipeline

P5 is a **parallel layer** that runs alongside the base pipeline, not inside it. The base `lip/pipeline.py` does not import from `p5_cascade_engine` directly. Instead:

```
   base pipeline (lip/pipeline.py)
        │
        │ payment events → (also forwarded to)
        ▼
   ┌─────────────────────────────────────┐
   │ p5_cascade_engine                   │
   │  ↓                                  │
   │  CorporateEntityResolver            │
   │  ↓                                  │
   │  CascadeGraph (in-memory)           │
   │  ↓                                  │
   │  CascadePropagationEngine           │
   │  ↓                                  │
   │  CascadeAlert (severity gate)       │
   │  ↓                                  │
   │  InterventionOptimizer              │
   └─────┬───────────────────────────────┘
         │
         │  bridges:
         ├──→ C2 (cascade-adjusted PD input)
         ├──→ C3 (cascade_settlement_trigger)
         ├──→ C5 (stress_cascade_bridge)
         └──→ C7 (coordinated intervention via cascade_router HTTP)
```

This separation matters: the base pipeline meets its 94 ms p99 SLO without ever calling into P5. P5 runs on its own latency budget, against an event stream that is forwarded from the pipeline. If P5 is unavailable (e.g. graph state is being rebuilt), the base pipeline degrades to the bilateral PD model — cascades are simply not detected during that window, but no payment is delayed.

---

## Public API

Per `lip/p5_cascade_engine/__init__.py`:

```python
from .cascade_alerts import CascadeAlert, build_cascade_alert
from .cascade_propagation import CascadePropagationEngine, CascadeResult, CascadeRiskNode
from .cascade_settlement_trigger import CascadeSettlementTrigger
from .corporate_features import get_corporate_node_features
from .corporate_graph import CascadeGraph, CorporateEdge, CorporateNode
from .entity_resolver import CorporateEntityResolver
from .intervention_optimizer import InterventionAction, InterventionOptimizer, InterventionPlan
from .stress_cascade_bridge import StressCascadeBridge
```

The intent is that integrators consume P5 through the HTTP `cascade_router` rather than by importing the engine directly. Direct import is supported for tests and for the bridge modules in C2/C3/C5/C7.

## Patent context

P5 is a separate patent in the BPI patent family — not a dependent claim of the base provisional. The patentable contributions are:

1. **Cascade-adjusted PD** as an input to a real-time payment-failure bridging decision (the bridge between the cascade graph and C2)
2. **Cascade-resolution settlement triggers** (the bridge between the cascade graph and C3)
3. **Optimised coordinated intervention** — picking the minimum-exposure cut to break a cascade, rather than funding payments individually as they arrive

When discussing P5 with patent counsel, the same EPG-21 language scrub rules apply: no AML / SAR / OFAC / SDN / PEP terms; do not enumerate the BLOCK list; describe the cascade gate by its structure, not its contents.

## Cross-references

- **HTTP surface**: `lip/api/cascade_router.py` and `cascade_service.py` (see [`api.md`](api.md))
- **Patent blueprint**: `consolidation files/P5-v0-Implementation-Blueprint.md`
- **Patent family map**: `consolidation files/Patent-Family-Architecture-v2.1.md`
- **Forward technology disclosure**: `consolidation files/Future-Technology-Disclosure-v2.1.md`
- **Related forward-looking patents**: P9 (CBDC, see [`../cbdc-protocol-research.md`](../cbdc-protocol-research.md)), P10 (regulatory data, see [`p10_regulatory_data.md`](p10_regulatory_data.md)), P12 (federated learning, see [`../federated-learning-architecture.md`](../federated-learning-architecture.md))
