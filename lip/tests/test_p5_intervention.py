"""
test_p5_intervention.py — TDD tests for greedy intervention optimizer.

Tests cover: single intervention, greedy ordering, budget constraint,
descendant protection, empty cascade, efficiency ratio.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
)
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.intervention_optimizer import (
    InterventionOptimizer,
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
