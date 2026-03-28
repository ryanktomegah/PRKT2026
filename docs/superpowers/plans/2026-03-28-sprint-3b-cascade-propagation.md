# Sprint 3b — Cascade Propagation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the BFS cascade propagation engine, CVaR computation, greedy intervention optimizer, and cascade alert generation on top of Sprint 3a's CascadeGraph.

**Architecture:** CascadePropagationEngine performs BFS with probability multiplication from a failed origin node, pruning at a configurable threshold. A second pass computes bottom-up CVaR (cascade value at risk). InterventionOptimizer uses greedy weighted set cover to rank bridge loan recommendations by cascade value prevented per dollar. CascadeAlert wraps the result for bank risk desk consumption.

**Tech Stack:** Python 3.14, dataclasses, collections.deque, Decimal arithmetic for financial thresholds, pytest, ruff

---

## Context

Session 7 of the 23-session build program. Sprint 3a (Session 6) built CascadeGraph, CorporateEntityResolver, and 8-dim corporate features. Sprint 3b adds the algorithmic intelligence that makes the graph actionable — failure propagation, risk quantification, and intervention planning.

**What this enables:** After this session, the codebase can answer: "If Corporate X fails, which downstream corporates are at risk, how much value is at risk, and which bridge loans prevent the most cascade damage?" Sprint 3c extends C2 with cascade-adjusted PD. Sprint 3d wires cascade alerts to the C7 bank API.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `lip/p5_cascade_engine/constants.py` | Add intervention/alert severity constants |
| Create | `lip/p5_cascade_engine/cascade_propagation.py` | CascadeRiskNode, CascadeResult, CascadePropagationEngine |
| Create | `lip/p5_cascade_engine/intervention_optimizer.py` | InterventionAction, InterventionPlan, InterventionOptimizer |
| Create | `lip/p5_cascade_engine/cascade_alerts.py` | CascadeAlert, build_cascade_alert factory |
| Modify | `lip/p5_cascade_engine/__init__.py` | Export new classes |
| Create | `lip/tests/test_p5_cascade_propagation.py` | BFS propagation + CVaR TDD tests |
| Create | `lip/tests/test_p5_intervention.py` | Intervention optimizer TDD tests |
| Create | `lip/tests/test_p5_cascade_alerts.py` | Alert generation TDD tests |

---

## Task 1: Add Sprint 3b Constants

**Files:**
- Modify: `lip/p5_cascade_engine/constants.py`

- [ ] **Step 1: Add intervention and alert severity constants**

Append after the existing constants:

```python
# ── Intervention optimizer ──────────────────────────────────────────────────
INTERVENTION_FEE_RATE_BPS = 200
"""Default bridge loan fee (bps annualised) for cost estimation."""

# ── Cascade alert severity thresholds ───────────────────────────────────────
CASCADE_ALERT_EXCLUSIVITY_HOURS = 4
"""Bank exclusivity window (hours) to act on intervention recommendation."""

CASCADE_ALERT_SEVERITY_HIGH_USD = Decimal("10000000")
"""CVaR >= $10M triggers HIGH severity alert."""

CASCADE_ALERT_SEVERITY_MEDIUM_USD = Decimal("1000000")
"""CVaR >= $1M triggers MEDIUM severity alert (same as alert threshold)."""
```

- [ ] **Step 2: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/constants.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add lip/p5_cascade_engine/constants.py
git commit -m "feat(p5): add intervention optimizer and alert severity constants"
```

---

## Task 2: Write Cascade Propagation TDD Tests

**Files:**
- Create: `lip/tests/test_p5_cascade_propagation.py`

- [ ] **Step 1: Write the complete test file**

```python
"""
test_p5_cascade_propagation.py — TDD tests for BFS cascade propagation and CVaR.

Tests cover: linear chain, star graph, diamond topology, threshold pruning,
max hops, CVaR computation, amplification factor, edge cases.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
    CascadeRiskNode,
)
from lip.p5_cascade_engine.constants import (
    CASCADE_INTERVENTION_THRESHOLD,
    CASCADE_MAX_HOPS,
)


def _make_node(cid: str) -> CorporateNode:
    return CorporateNode(corporate_id=cid)


def _make_edge(
    src: str, tgt: str, volume: float = 1000000.0, dep: float = 0.8
) -> CorporateEdge:
    return CorporateEdge(
        source_corporate_id=src,
        target_corporate_id=tgt,
        total_volume_30d=volume,
        payment_count_30d=10,
        dependency_score=dep,
    )


def _build_graph(
    node_ids: list[str], edges: list[CorporateEdge]
) -> CascadeGraph:
    nodes = {cid: _make_node(cid) for cid in node_ids}
    adjacency: dict = {cid: {} for cid in node_ids}
    reverse_adjacency: dict = {cid: {} for cid in node_ids}
    for e in edges:
        adjacency.setdefault(e.source_corporate_id, {})[e.target_corporate_id] = e
        reverse_adjacency.setdefault(e.target_corporate_id, {})[e.source_corporate_id] = e
    return CascadeGraph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
        node_count=len(nodes),
        edge_count=len(edges),
    )


class TestCascadePropagationBFS:
    """BFS propagation with probability multiplication."""

    def test_linear_chain_two_hops(self):
        """A -> B -> C, dep=0.8 each. P(B)=0.8, P(C)=0.64."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.8),
            _make_edge("B", "C", 20_000_000, 0.8),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert "B" in result.cascade_map
        assert result.cascade_map["B"].cascade_probability == pytest.approx(0.8)
        assert result.cascade_map["B"].hop_distance == 1

        assert "C" in result.cascade_map
        assert result.cascade_map["C"].cascade_probability == pytest.approx(0.64)
        assert result.cascade_map["C"].hop_distance == 2

    def test_star_graph(self):
        """A -> B, A -> C, A -> D. All at hop 1."""
        edges = [
            _make_edge("A", "B", 10_000_000, 0.9),
            _make_edge("A", "C", 20_000_000, 0.7),
            _make_edge("A", "D", 5_000_000, 0.85),
        ]
        graph = _build_graph(["A", "B", "C", "D"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert len(result.cascade_map) == 3
        assert result.cascade_map["B"].cascade_probability == pytest.approx(0.9)
        assert result.cascade_map["C"].cascade_probability == pytest.approx(0.7)
        assert result.cascade_map["D"].cascade_probability == pytest.approx(0.85)

    def test_diamond_graph(self):
        """A -> B -> D, A -> C -> D. D visited via first path only (BFS)."""
        edges = [
            _make_edge("A", "B", 30_000_000, 0.9),
            _make_edge("A", "C", 20_000_000, 0.8),
            _make_edge("B", "D", 15_000_000, 0.85),
            _make_edge("C", "D", 10_000_000, 0.75),
        ]
        graph = _build_graph(["A", "B", "C", "D"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert "D" in result.cascade_map
        # D reached via B first (higher dep): P(D) = P(B) * d(B,D) = 0.9 * 0.85 = 0.765
        assert result.cascade_map["D"].cascade_probability == pytest.approx(0.765)
        assert result.cascade_map["D"].hop_distance == 2

    def test_threshold_pruning(self):
        """Nodes below threshold are NOT in cascade_map."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.5),  # P(B) = 0.5 < 0.7
        ]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.7)

        assert len(result.cascade_map) == 0
        assert result.nodes_above_threshold == 0

    def test_threshold_stops_propagation(self):
        """A -> B (dep=0.9) -> C (dep=0.7). P(C)=0.63 < 0.7 threshold."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.9),
            _make_edge("B", "C", 20_000_000, 0.7),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=CASCADE_INTERVENTION_THRESHOLD)

        assert "B" in result.cascade_map  # P(B) = 0.9 >= 0.7
        assert "C" not in result.cascade_map  # P(C) = 0.63 < 0.7

    def test_max_hops_limit(self):
        """Long chain: A->B->C->D->E->F->G. max_hops=3 stops at D."""
        edges = [
            _make_edge("A", "B", 10_000_000, 0.95),
            _make_edge("B", "C", 10_000_000, 0.95),
            _make_edge("C", "D", 10_000_000, 0.95),
            _make_edge("D", "E", 10_000_000, 0.95),
            _make_edge("E", "F", 10_000_000, 0.95),
            _make_edge("F", "G", 10_000_000, 0.95),
        ]
        graph = _build_graph(["A", "B", "C", "D", "E", "F", "G"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5, max_hops=3)

        assert "B" in result.cascade_map
        assert "C" in result.cascade_map
        assert "D" in result.cascade_map
        assert "E" not in result.cascade_map
        assert result.max_hops_reached == 3

    def test_origin_not_in_cascade_map(self):
        """Origin node itself is NOT in cascade_map (it's the failure source)."""
        edges = [_make_edge("A", "B", 10_000_000, 0.8)]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert "A" not in result.cascade_map
        assert result.origin_corporate_id == "A"

    def test_unknown_origin_returns_empty(self):
        """Unknown origin returns empty result (no crash)."""
        graph = _build_graph(["A"], [])
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "UNKNOWN", threshold=0.5)

        assert len(result.cascade_map) == 0
        assert result.total_value_at_risk_usd == 0.0

    def test_empty_graph(self):
        """Empty graph returns empty result."""
        graph = CascadeGraph()
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert len(result.cascade_map) == 0

    def test_no_outgoing_edges(self):
        """Origin with no outgoing edges returns empty cascade."""
        graph = _build_graph(["A"], [])
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert len(result.cascade_map) == 0

    def test_parent_tracking(self):
        """Each cascade node tracks its parent for intervention tracing."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.9),
            _make_edge("B", "C", 20_000_000, 0.85),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.cascade_map["B"].parent_corporate_id == "A"
        assert result.cascade_map["C"].parent_corporate_id == "B"


class TestCascadeCVaR:
    """Cascade Value at Risk computation."""

    def test_cvar_simple_chain(self):
        """A -> B ($50M, dep=0.8) -> C ($20M, dep=0.8).
        CVaR(B) = 0.8 * 50M = 40M
        CVaR(C) = 0.64 * 20M = 12.8M
        Total = 52.8M
        """
        edges = [
            _make_edge("A", "B", 50_000_000, 0.8),
            _make_edge("B", "C", 20_000_000, 0.8),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.total_value_at_risk_usd == pytest.approx(52_800_000.0)

    def test_cvar_star_graph(self):
        """A -> B ($10M, d=0.9), A -> C ($20M, d=0.7), A -> D ($5M, d=0.85).
        CVaR = 0.9*10M + 0.7*20M + 0.85*5M = 9M + 14M + 4.25M = 27.25M
        """
        edges = [
            _make_edge("A", "B", 10_000_000, 0.9),
            _make_edge("A", "C", 20_000_000, 0.7),
            _make_edge("A", "D", 5_000_000, 0.85),
        ]
        graph = _build_graph(["A", "B", "C", "D"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.total_value_at_risk_usd == pytest.approx(27_250_000.0)

    def test_amplification_factor(self):
        """Amplification = total_var / origin_outgoing_volume."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.8),
            _make_edge("B", "C", 20_000_000, 0.8),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        # Origin outgoing = 50M, total CVaR = 52.8M
        assert result.origin_outgoing_volume_usd == pytest.approx(50_000_000.0)
        assert result.cascade_amplification_factor == pytest.approx(52_800_000 / 50_000_000)

    def test_downstream_cvar_aggregation(self):
        """B's downstream_value_at_risk includes C's cascade risk."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.8),
            _make_edge("B", "C", 20_000_000, 0.8),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        # B's downstream CVaR = P(C) * vol(B,C) = 0.64 * 20M = 12.8M
        assert result.cascade_map["B"].downstream_value_at_risk_usd == pytest.approx(
            12_800_000.0
        )
        # C has no children
        assert result.cascade_map["C"].downstream_value_at_risk_usd == pytest.approx(0.0)

    def test_blueprint_bmw_bosch_example(self):
        """Validate against blueprint Section 5.3 worked example.
        BMW -> Bosch ($50M, d=0.62). P(Bosch)=0.62.
        Bosch -> T2_C ($20M, d=0.45). P(T2_C)=0.279.
        Bosch -> T2_D ($15M, d=0.38). P(T2_D)=0.236.
        With threshold=0.2:
        CVaR(Bosch) = 0.62 * 50M = 31M
        CVaR(T2_C)  = 0.279 * 20M = 5.58M
        CVaR(T2_D)  = 0.236 * 15M = 3.54M
        Total = 40.12M
        """
        edges = [
            _make_edge("BMW", "BOSCH", 50_000_000, 0.62),
            _make_edge("BOSCH", "T2_C", 20_000_000, 0.45),
            _make_edge("BOSCH", "T2_D", 15_000_000, 0.38),
        ]
        graph = _build_graph(["BMW", "BOSCH", "T2_C", "T2_D"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "BMW", threshold=0.2)

        assert result.cascade_map["BOSCH"].cascade_probability == pytest.approx(0.62)
        assert result.cascade_map["T2_C"].cascade_probability == pytest.approx(0.279)
        assert result.cascade_map["T2_D"].cascade_probability == pytest.approx(0.236, abs=0.001)
        assert result.total_value_at_risk_usd == pytest.approx(40_120_000.0, rel=0.01)

    def test_zero_var_when_no_cascade(self):
        """No cascade nodes = zero CVaR."""
        edges = [_make_edge("A", "B", 10_000_000, 0.3)]  # Below threshold
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.total_value_at_risk_usd == 0.0
        assert result.cascade_amplification_factor == 0.0


class TestCascadeResultMetadata:
    """Result metadata: nodes_evaluated, nodes_above_threshold, trigger_type."""

    def test_nodes_evaluated_count(self):
        edges = [
            _make_edge("A", "B", 10_000_000, 0.9),
            _make_edge("A", "C", 10_000_000, 0.3),  # Below threshold
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.nodes_above_threshold == 1  # Only B

    def test_trigger_type_default(self):
        graph = _build_graph(["A"], [])
        engine = CascadePropagationEngine()
        result = engine.propagate(graph, "A", threshold=0.5)

        assert result.trigger_type == "PAYMENT_FAILURE"

    def test_trigger_type_custom(self):
        graph = _build_graph(["A"], [])
        engine = CascadePropagationEngine()
        result = engine.propagate(
            graph, "A", threshold=0.5, trigger_type="CORRIDOR_STRESS"
        )

        assert result.trigger_type == "CORRIDOR_STRESS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_cascade_propagation.py -v 2>&1 | head -20`
Expected: ImportError for CascadePropagationEngine

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_p5_cascade_propagation.py
git commit -m "test(p5): add TDD test suite for BFS cascade propagation and CVaR"
```

---

## Task 3: Implement Cascade Propagation Engine

**Files:**
- Create: `lip/p5_cascade_engine/cascade_propagation.py`

- [ ] **Step 1: Write the cascade propagation implementation**

```python
"""
cascade_propagation.py — BFS cascade propagation with probability multiplication.

P5 blueprint Section 5.2: BFS from failed origin node, multiply dependency scores
at each hop, prune below threshold. Section 5.3: compute CVaR bottom-up.

Complexity: O(V + E) BFS, O(k) in practice where k = nodes above threshold.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .constants import CASCADE_INTERVENTION_THRESHOLD, CASCADE_MAX_HOPS
from .corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


@dataclass
class CascadeRiskNode:
    """One node in the cascade propagation result."""

    corporate_id: str
    cascade_probability: float
    incoming_volume_at_risk_usd: float
    downstream_value_at_risk_usd: float = 0.0
    hop_distance: int = 0
    parent_corporate_id: str = ""


@dataclass
class CascadeResult:
    """Complete result of cascade propagation from a single origin."""

    origin_corporate_id: str
    trigger_type: str = "PAYMENT_FAILURE"
    cascade_map: Dict[str, CascadeRiskNode] = field(default_factory=dict)
    total_value_at_risk_usd: float = 0.0
    origin_outgoing_volume_usd: float = 0.0
    cascade_amplification_factor: float = 0.0
    nodes_evaluated: int = 0
    nodes_above_threshold: int = 0
    max_hops_reached: int = 0
    timestamp: float = 0.0


class CascadePropagationEngine:
    """BFS cascade propagation with probability multiplication and threshold pruning.

    Algorithm (P5 blueprint Section 5.2):
      1. BFS from origin node
      2. At each edge: P_child = P_parent * dependency_score
      3. Prune if P_child < threshold
      4. Stop at max_hops
      5. Bottom-up pass to compute downstream CVaR
    """

    def propagate(
        self,
        graph: CascadeGraph,
        origin_node: str,
        threshold: float = CASCADE_INTERVENTION_THRESHOLD,
        max_hops: int = CASCADE_MAX_HOPS,
        trigger_type: str = "PAYMENT_FAILURE",
    ) -> CascadeResult:
        """Run BFS cascade propagation from origin_node.

        Args:
            graph: Corporate-level CascadeGraph.
            origin_node: Corporate ID of the failed/stressed entity.
            threshold: Minimum cascade probability to include a node.
            max_hops: Maximum BFS depth.
            trigger_type: "PAYMENT_FAILURE" or "CORRIDOR_STRESS".

        Returns:
            CascadeResult with cascade_map, CVaR, and amplification factor.
        """
        result = CascadeResult(
            origin_corporate_id=origin_node,
            trigger_type=trigger_type,
            timestamp=time.time(),
        )

        if origin_node not in graph.adjacency:
            return result

        # Phase 1: BFS with probability multiplication
        cascade_map: Dict[str, CascadeRiskNode] = {}
        visited = {origin_node}
        # Queue entries: (node_id, probability, hop_distance)
        queue: deque = deque()

        # Seed: all children of origin with P = 1.0 * dep_score
        for target_id, edge in graph.adjacency.get(origin_node, {}).items():
            p_child = edge.dependency_score
            result.nodes_evaluated += 1
            if p_child >= threshold and target_id not in visited:
                risk_node = CascadeRiskNode(
                    corporate_id=target_id,
                    cascade_probability=p_child,
                    incoming_volume_at_risk_usd=edge.total_volume_30d,
                    hop_distance=1,
                    parent_corporate_id=origin_node,
                )
                cascade_map[target_id] = risk_node
                visited.add(target_id)
                queue.append((target_id, p_child, 1))

        # BFS loop
        while queue:
            u, p_u, hop = queue.popleft()
            if hop >= max_hops:
                continue
            for target_id, edge in graph.adjacency.get(u, {}).items():
                if target_id in visited:
                    continue
                result.nodes_evaluated += 1
                p_child = p_u * edge.dependency_score
                if p_child >= threshold:
                    risk_node = CascadeRiskNode(
                        corporate_id=target_id,
                        cascade_probability=p_child,
                        incoming_volume_at_risk_usd=edge.total_volume_30d,
                        hop_distance=hop + 1,
                        parent_corporate_id=u,
                    )
                    cascade_map[target_id] = risk_node
                    visited.add(target_id)
                    queue.append((target_id, p_child, hop + 1))

        # Phase 2: Bottom-up CVaR computation
        # Sort by hop distance descending (deepest first)
        sorted_nodes = sorted(
            cascade_map.values(), key=lambda n: n.hop_distance, reverse=True
        )
        for node in sorted_nodes:
            # Accumulate children's CVaR into parent's downstream value
            children_cvar = sum(
                child.cascade_probability * child.incoming_volume_at_risk_usd
                + child.downstream_value_at_risk_usd
                for child in cascade_map.values()
                if child.parent_corporate_id == node.corporate_id
            )
            node.downstream_value_at_risk_usd = children_cvar

        # Phase 3: Compute totals
        total_var = sum(
            n.cascade_probability * n.incoming_volume_at_risk_usd
            for n in cascade_map.values()
        )
        origin_outgoing = sum(
            edge.total_volume_30d
            for edge in graph.adjacency.get(origin_node, {}).values()
        )
        max_hop = max((n.hop_distance for n in cascade_map.values()), default=0)

        result.cascade_map = cascade_map
        result.total_value_at_risk_usd = total_var
        result.origin_outgoing_volume_usd = origin_outgoing
        result.cascade_amplification_factor = (
            total_var / origin_outgoing if origin_outgoing > 0 else 0.0
        )
        result.nodes_above_threshold = len(cascade_map)
        result.max_hops_reached = max_hop

        logger.info(
            "propagate: origin=%s, nodes_above_threshold=%d, total_cvar=%.0f, "
            "amplification=%.2fx, max_hops=%d",
            origin_node,
            len(cascade_map),
            total_var,
            result.cascade_amplification_factor,
            max_hop,
        )

        return result
```

- [ ] **Step 2: Run the TDD tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_cascade_propagation.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add lip/p5_cascade_engine/cascade_propagation.py
git commit -m "feat(p5): implement BFS cascade propagation with CVaR computation"
```

---

## Task 4: Write Intervention Optimizer TDD Tests

**Files:**
- Create: `lip/tests/test_p5_intervention.py`

- [ ] **Step 1: Write the complete test file**

```python
"""
test_p5_intervention.py — TDD tests for greedy intervention optimizer.

Tests cover: single intervention, greedy ordering, budget constraint,
descendant protection, empty cascade, efficiency ratio.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
    CascadeRiskNode,
)
from lip.p5_cascade_engine.intervention_optimizer import (
    InterventionAction,
    InterventionOptimizer,
    InterventionPlan,
)


def _make_node(cid: str) -> CorporateNode:
    return CorporateNode(corporate_id=cid)


def _make_edge(
    src: str, tgt: str, volume: float = 1000000.0, dep: float = 0.8
) -> CorporateEdge:
    return CorporateEdge(
        source_corporate_id=src,
        target_corporate_id=tgt,
        total_volume_30d=volume,
        payment_count_30d=10,
        dependency_score=dep,
    )


def _build_graph(
    node_ids: list[str], edges: list[CorporateEdge]
) -> CascadeGraph:
    nodes = {cid: _make_node(cid) for cid in node_ids}
    adjacency: dict = {cid: {} for cid in node_ids}
    reverse_adjacency: dict = {cid: {} for cid in node_ids}
    for e in edges:
        adjacency.setdefault(e.source_corporate_id, {})[e.target_corporate_id] = e
        reverse_adjacency.setdefault(e.target_corporate_id, {})[e.source_corporate_id] = e
    return CascadeGraph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
        node_count=len(nodes),
        edge_count=len(edges),
    )


class TestInterventionOptimizer:
    """Greedy weighted set cover for intervention planning."""

    def test_single_intervention(self):
        """One cascade node -> one intervention."""
        edges = [_make_edge("A", "B", 10_000_000, 0.8)]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=50_000_000)

        assert len(plan.interventions) == 1
        assert plan.interventions[0].target_corporate_id == "B"
        assert plan.interventions[0].bridge_amount_usd == 10_000_000
        assert plan.interventions[0].priority == 1

    def test_greedy_selects_highest_efficiency(self):
        """Two targets: B ($50M, dep=0.8) and C ($5M, dep=0.9).
        B: value=0.8*50M=40M, cost=50M, ratio=0.8
        C: value=0.9*5M=4.5M, cost=5M, ratio=0.9
        Greedy picks C first (higher ratio).
        """
        edges = [
            _make_edge("A", "B", 50_000_000, 0.8),
            _make_edge("A", "C", 5_000_000, 0.9),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=100_000_000)

        assert plan.interventions[0].target_corporate_id == "C"  # Higher ratio
        assert plan.interventions[0].priority == 1
        assert plan.interventions[1].target_corporate_id == "B"
        assert plan.interventions[1].priority == 2

    def test_budget_exhaustion(self):
        """Budget only covers one of two interventions."""
        edges = [
            _make_edge("A", "B", 30_000_000, 0.8),
            _make_edge("A", "C", 30_000_000, 0.9),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=35_000_000)

        assert len(plan.interventions) == 1
        assert plan.remaining_budget_usd == pytest.approx(5_000_000)

    def test_descendant_protection(self):
        """Bridging B protects C (downstream of B). C not in plan."""
        edges = [
            _make_edge("A", "B", 50_000_000, 0.9),
            _make_edge("B", "C", 20_000_000, 0.85),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=100_000_000)

        # B's value includes downstream C, so B is the better intervention point
        assert len(plan.interventions) == 1
        assert plan.interventions[0].target_corporate_id == "B"

    def test_empty_cascade_returns_empty_plan(self):
        """No cascade nodes = empty intervention plan."""
        cascade = CascadeResult(origin_corporate_id="A")
        graph = _build_graph(["A"], [])
        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=100_000_000)

        assert len(plan.interventions) == 0
        assert plan.total_cost_usd == 0.0
        assert plan.total_value_prevented_usd == 0.0

    def test_zero_budget_returns_empty_plan(self):
        edges = [_make_edge("A", "B", 10_000_000, 0.9)]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=0)

        assert len(plan.interventions) == 0

    def test_cost_efficiency_ratio(self):
        """Verify cost_efficiency_ratio = value_prevented / bridge_amount."""
        edges = [_make_edge("A", "B", 10_000_000, 0.8)]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=50_000_000)

        action = plan.interventions[0]
        assert action.cost_efficiency_ratio == pytest.approx(
            action.cascade_value_prevented_usd / action.bridge_amount_usd
        )

    def test_budget_utilization_pct(self):
        edges = [_make_edge("A", "B", 10_000_000, 0.9)]
        graph = _build_graph(["A", "B"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=100_000_000)

        # Used 10M of 100M = 10%
        assert plan.budget_utilization_pct == pytest.approx(10.0)

    def test_total_value_prevented(self):
        """total_value_prevented = sum of all intervention values."""
        edges = [
            _make_edge("A", "B", 10_000_000, 0.9),
            _make_edge("A", "C", 20_000_000, 0.8),
        ]
        graph = _build_graph(["A", "B", "C"], edges)
        engine = CascadePropagationEngine()
        cascade = engine.propagate(graph, "A", threshold=0.5)

        optimizer = InterventionOptimizer()
        plan = optimizer.optimize(cascade, graph, budget_usd=100_000_000)

        assert plan.total_value_prevented_usd == pytest.approx(
            sum(a.cascade_value_prevented_usd for a in plan.interventions)
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_intervention.py -v 2>&1 | head -20`
Expected: ImportError for InterventionOptimizer

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_p5_intervention.py
git commit -m "test(p5): add TDD test suite for greedy intervention optimizer"
```

---

## Task 5: Implement Intervention Optimizer

**Files:**
- Create: `lip/p5_cascade_engine/intervention_optimizer.py`

- [ ] **Step 1: Write the intervention optimizer implementation**

```python
"""
intervention_optimizer.py — Greedy weighted set cover for cascade intervention.

P5 blueprint Section 5.4: given a cascade propagation result and a budget,
select bridge loans that maximise cascade value prevented per dollar spent.

Greedy guarantee: (1 - 1/e) >= 63.2% of optimal.
Empirically >90% for tree-like supply chain topologies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .cascade_propagation import CascadeResult, CascadeRiskNode
from .corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


@dataclass
class InterventionAction:
    """A single bridge loan recommendation."""

    source_corporate_id: str
    target_corporate_id: str
    bridge_amount_usd: float
    cascade_value_prevented_usd: float
    cost_efficiency_ratio: float
    priority: int


@dataclass
class InterventionPlan:
    """Ranked set of bridge loan recommendations."""

    interventions: List[InterventionAction] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_value_prevented_usd: float = 0.0
    remaining_budget_usd: float = 0.0
    budget_utilization_pct: float = 0.0


class InterventionOptimizer:
    """Greedy weighted set cover for cascade intervention planning.

    Each iteration selects the intervention with the highest
    cascade_value_prevented / bridge_cost ratio, then marks
    the target and all its descendants as protected.
    """

    def optimize(
        self,
        cascade_result: CascadeResult,
        graph: CascadeGraph,
        budget_usd: float,
    ) -> InterventionPlan:
        """Compute optimal intervention plan within budget.

        Args:
            cascade_result: Output of CascadePropagationEngine.propagate().
            graph: The CascadeGraph (needed for edge lookup).
            budget_usd: Total bridge lending budget.

        Returns:
            InterventionPlan with ranked interventions.
        """
        plan = InterventionPlan(remaining_budget_usd=budget_usd)

        if not cascade_result.cascade_map or budget_usd <= 0:
            return plan

        protected: Set[str] = set()
        remaining = budget_usd
        priority = 1

        while remaining > 0:
            best_ratio = 0.0
            best_candidate = None

            for node in cascade_result.cascade_map.values():
                if node.corporate_id in protected:
                    continue

                bridge_cost = node.incoming_volume_at_risk_usd
                if bridge_cost <= 0 or bridge_cost > remaining:
                    continue

                value_prevented = (
                    node.cascade_probability * node.incoming_volume_at_risk_usd
                    + node.downstream_value_at_risk_usd
                )

                ratio = value_prevented / bridge_cost
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_candidate = (node, bridge_cost, value_prevented, ratio)

            if best_candidate is None:
                break

            node, cost, value, ratio = best_candidate
            action = InterventionAction(
                source_corporate_id=node.parent_corporate_id,
                target_corporate_id=node.corporate_id,
                bridge_amount_usd=cost,
                cascade_value_prevented_usd=value,
                cost_efficiency_ratio=ratio,
                priority=priority,
            )
            plan.interventions.append(action)
            remaining -= cost
            priority += 1

            # Protect target and all descendants
            protected.add(node.corporate_id)
            descendants = self._get_descendants(
                node.corporate_id, cascade_result.cascade_map
            )
            protected |= descendants

        plan.total_cost_usd = budget_usd - remaining
        plan.total_value_prevented_usd = sum(
            a.cascade_value_prevented_usd for a in plan.interventions
        )
        plan.remaining_budget_usd = remaining
        plan.budget_utilization_pct = (
            (plan.total_cost_usd / budget_usd * 100) if budget_usd > 0 else 0.0
        )

        logger.info(
            "optimize: %d interventions, total_cost=%.0f, value_prevented=%.0f, "
            "budget_util=%.1f%%",
            len(plan.interventions),
            plan.total_cost_usd,
            plan.total_value_prevented_usd,
            plan.budget_utilization_pct,
        )

        return plan

    @staticmethod
    def _get_descendants(
        corporate_id: str, cascade_map: Dict[str, CascadeRiskNode]
    ) -> Set[str]:
        """BFS to find all descendants of corporate_id in the cascade map."""
        descendants: Set[str] = set()
        queue = [corporate_id]
        while queue:
            current = queue.pop()
            for node in cascade_map.values():
                if (
                    node.parent_corporate_id == current
                    and node.corporate_id not in descendants
                ):
                    descendants.add(node.corporate_id)
                    queue.append(node.corporate_id)
        return descendants
```

- [ ] **Step 2: Run the TDD tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_intervention.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add lip/p5_cascade_engine/intervention_optimizer.py
git commit -m "feat(p5): implement greedy intervention optimizer (weighted set cover)"
```

---

## Task 6: Write Cascade Alert TDD Tests and Implementation

**Files:**
- Create: `lip/tests/test_p5_cascade_alerts.py`
- Create: `lip/p5_cascade_engine/cascade_alerts.py`

- [ ] **Step 1: Write the alert test file**

```python
"""
test_p5_cascade_alerts.py — TDD tests for cascade alert generation.

Tests cover: severity classification, alert_id format, below-threshold
returns None, exclusivity window, end-to-end alert generation.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from lip.p5_cascade_engine.cascade_alerts import CascadeAlert, build_cascade_alert
from lip.p5_cascade_engine.cascade_propagation import CascadeResult, CascadeRiskNode
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.constants import (
    CASCADE_ALERT_EXCLUSIVITY_HOURS,
    CASCADE_ALERT_SEVERITY_HIGH_USD,
    CASCADE_ALERT_SEVERITY_MEDIUM_USD,
    CASCADE_ALERT_THRESHOLD_USD,
)


def _make_node(cid: str, sector: str = "UNKNOWN", jur: str = "XX") -> CorporateNode:
    return CorporateNode(corporate_id=cid, sector=sector, jurisdiction=jur)


def _make_edge(
    src: str, tgt: str, volume: float = 1000000.0, dep: float = 0.8
) -> CorporateEdge:
    return CorporateEdge(
        source_corporate_id=src,
        target_corporate_id=tgt,
        total_volume_30d=volume,
        payment_count_30d=10,
        dependency_score=dep,
    )


def _build_graph(
    nodes: dict[str, CorporateNode], edges: list[CorporateEdge]
) -> CascadeGraph:
    adjacency: dict = {cid: {} for cid in nodes}
    reverse_adjacency: dict = {cid: {} for cid in nodes}
    for e in edges:
        adjacency.setdefault(e.source_corporate_id, {})[e.target_corporate_id] = e
        reverse_adjacency.setdefault(e.target_corporate_id, {})[e.source_corporate_id] = e
    return CascadeGraph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
        node_count=len(nodes),
        edge_count=len(edges),
    )


class TestCascadeAlertSeverity:
    """Severity classification based on CVaR."""

    def test_high_severity(self):
        """CVaR >= $10M -> HIGH."""
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B", "Auto Parts", "DE"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.8)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.severity == "HIGH"

    def test_medium_severity(self):
        """CVaR >= $1M but < $10M -> MEDIUM."""
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 5_000_000, 0.8)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.severity == "MEDIUM"

    def test_below_threshold_returns_none(self):
        """CVaR < $1M -> no alert."""
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 500_000, 0.8)]  # 0.8 * 500K = 400K < 1M
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is None


class TestCascadeAlertStructure:
    """Alert structure and metadata."""

    def test_alert_id_format(self):
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.alert_id.startswith("CASC-")
        assert alert.alert_type == "CASCADE_PROPAGATION"

    def test_exclusivity_window(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.expires_at == pytest.approx(
            alert.timestamp + CASCADE_ALERT_EXCLUSIVITY_HOURS * 3600, abs=1
        )

    def test_alert_carries_origin_metadata(self):
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.origin_corporate_id == "A"
        assert alert.origin_sector == "Automobiles"
        assert alert.origin_jurisdiction == "DE"

    def test_alert_has_intervention_plan(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.intervention_plan is not None
        assert len(alert.intervention_plan.interventions) >= 1

    def test_alert_has_cascade_result(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.cascade_result.origin_corporate_id == "A"
        assert alert.cascade_result.total_value_at_risk_usd > 0

    def test_unknown_origin_returns_none(self):
        graph = CascadeGraph()
        alert = build_cascade_alert(graph, "UNKNOWN", budget_usd=100_000_000)
        assert alert is None
```

- [ ] **Step 2: Write the cascade alerts implementation**

```python
"""
cascade_alerts.py — Cascade alert generation for bank risk desks.

Combines propagation + intervention into a structured alert with
severity classification and exclusivity window. Sprint 3d wires
this to C7 Cascade API endpoints.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .cascade_propagation import CascadePropagationEngine, CascadeResult
from .constants import (
    CASCADE_ALERT_EXCLUSIVITY_HOURS,
    CASCADE_ALERT_SEVERITY_HIGH_USD,
    CASCADE_ALERT_SEVERITY_MEDIUM_USD,
    CASCADE_ALERT_THRESHOLD_USD,
)
from .corporate_graph import CascadeGraph
from .intervention_optimizer import InterventionOptimizer, InterventionPlan

logger = logging.getLogger(__name__)


@dataclass
class CascadeAlert:
    """Structured cascade alert for bank risk desk consumption."""

    alert_id: str
    alert_type: str
    severity: str
    origin_corporate_id: str
    origin_sector: str
    origin_jurisdiction: str
    cascade_result: CascadeResult
    intervention_plan: Optional[InterventionPlan]
    timestamp: float
    expires_at: float


def build_cascade_alert(
    graph: CascadeGraph,
    origin_corporate_id: str,
    budget_usd: float,
    threshold: float = 0.50,
    trigger_type: str = "PAYMENT_FAILURE",
) -> Optional[CascadeAlert]:
    """Build a cascade alert if CVaR exceeds the alert threshold.

    Args:
        graph: Corporate-level CascadeGraph.
        origin_corporate_id: Corporate ID of the failed entity.
        budget_usd: Total bridge lending budget for intervention.
        threshold: Cascade probability threshold for propagation.
        trigger_type: "PAYMENT_FAILURE" or "CORRIDOR_STRESS".

    Returns:
        CascadeAlert if total CVaR >= CASCADE_ALERT_THRESHOLD_USD, else None.
    """
    engine = CascadePropagationEngine()
    cascade_result = engine.propagate(
        graph, origin_corporate_id, threshold=threshold, trigger_type=trigger_type
    )

    total_var = Decimal(str(cascade_result.total_value_at_risk_usd))
    if total_var < CASCADE_ALERT_THRESHOLD_USD:
        return None

    # Intervention plan
    optimizer = InterventionOptimizer()
    plan = optimizer.optimize(cascade_result, graph, budget_usd=budget_usd)

    # Severity classification
    if total_var >= CASCADE_ALERT_SEVERITY_HIGH_USD:
        severity = "HIGH"
    elif total_var >= CASCADE_ALERT_SEVERITY_MEDIUM_USD:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # Alert metadata
    now = time.time()
    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    alert_id = f"CASC-{date_str}-{int(now * 1000) % 100000:05d}"

    # Origin metadata
    origin_node = graph.nodes.get(origin_corporate_id)
    origin_sector = origin_node.sector if origin_node else "UNKNOWN"
    origin_jurisdiction = origin_node.jurisdiction if origin_node else "XX"

    return CascadeAlert(
        alert_id=alert_id,
        alert_type="CASCADE_PROPAGATION",
        severity=severity,
        origin_corporate_id=origin_corporate_id,
        origin_sector=origin_sector,
        origin_jurisdiction=origin_jurisdiction,
        cascade_result=cascade_result,
        intervention_plan=plan,
        timestamp=now,
        expires_at=now + CASCADE_ALERT_EXCLUSIVITY_HOURS * 3600,
    )
```

- [ ] **Step 3: Run the TDD tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_cascade_alerts.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit both files**

```bash
git add lip/p5_cascade_engine/cascade_alerts.py lip/tests/test_p5_cascade_alerts.py
git commit -m "feat(p5): implement cascade alert generation with severity classification"
```

---

## Task 7: Update Module Exports + Regression + Push

**Files:**
- Modify: `lip/p5_cascade_engine/__init__.py`

- [ ] **Step 1: Update exports**

```python
"""
p5_cascade_engine — P5 Supply Chain Cascade Detection & Prevention.

Sprint 3a: Corporate entity resolution layer.
Sprint 3b: Cascade propagation engine (BFS + intervention optimiser).
Sprint 3c-3d: C2/C7 integration.
"""
from .cascade_alerts import CascadeAlert, build_cascade_alert
from .cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
    CascadeRiskNode,
)
from .corporate_features import get_corporate_node_features
from .corporate_graph import CascadeGraph, CorporateEdge, CorporateNode
from .entity_resolver import CorporateEntityResolver
from .intervention_optimizer import (
    InterventionAction,
    InterventionOptimizer,
    InterventionPlan,
)

__all__ = [
    "CascadeAlert",
    "CascadeGraph",
    "CascadePropagationEngine",
    "CascadeResult",
    "CascadeRiskNode",
    "CorporateEdge",
    "CorporateEntityResolver",
    "CorporateNode",
    "InterventionAction",
    "InterventionOptimizer",
    "InterventionPlan",
    "build_cascade_alert",
    "get_corporate_node_features",
]
```

- [ ] **Step 2: Run ruff on all Sprint 3b files**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/`
Expected: zero errors

- [ ] **Step 3: Run all Sprint 3b tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_cascade_propagation.py lip/tests/test_p5_intervention.py lip/tests/test_p5_cascade_alerts.py -v`
Expected: ALL PASS

- [ ] **Step 4: Run Sprint 3a regression**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py lip/tests/test_p5_centrality.py -v`
Expected: ALL PASS (Sprint 3a unchanged)

- [ ] **Step 5: Run full test suite regression**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -q 2>&1 | tail -20`
Expected: all tests pass, zero failures

- [ ] **Step 6: Commit exports**

```bash
git add lip/p5_cascade_engine/__init__.py
git commit -m "feat(p5): export Sprint 3b cascade propagation, optimizer, and alert classes"
```

- [ ] **Step 7: Push to GitHub**

```bash
git push origin main
```

---

## Verification Checklist

Before declaring Sprint 3b complete:

1. [ ] `ruff check lip/p5_cascade_engine/` — zero errors
2. [ ] All propagation tests pass (linear chain, star, diamond, threshold pruning, max hops, CVaR)
3. [ ] All intervention tests pass (greedy ordering, budget, descendant protection)
4. [ ] All alert tests pass (severity, exclusivity, below-threshold None)
5. [ ] Blueprint BMW/Bosch example matches expected values (Section 5.3)
6. [ ] Sprint 3a regression: all 28 tests unchanged
7. [ ] Full test suite regression: zero failures
8. [ ] Pushed to GitHub

---

## Next Session: Sprint 3c — C2 Cascade-Adjusted PD + C3 Alert Trigger

Sprint 3c extends:
- C2 PD Pricing Engine with `compute_cascade_adjusted_pd()` (cascade discount, QUANT sign-off gate)
- C3 Settlement Monitor with cascade alert trigger on upstream failure
- C5 StressRegimeEvent → cascade re-evaluation trigger
