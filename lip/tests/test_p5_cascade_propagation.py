"""
test_p5_cascade_propagation.py — TDD tests for BFS cascade propagation and CVaR.

Tests cover: linear chain, star graph, diamond topology, threshold pruning,
max hops, CVaR computation, amplification factor, edge cases.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.cascade_propagation import (
    CascadePropagationEngine,
)
from lip.p5_cascade_engine.constants import (
    CASCADE_INTERVENTION_THRESHOLD,
)
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
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
