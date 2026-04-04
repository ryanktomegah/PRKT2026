"""
test_p10_circular_exposure.py — Sprint 6 circular exposure detection tests.

Verifies DFS-based cycle detection on BIC dependency graphs with weight
thresholds, confidence reporting, and deduplication.
"""
from __future__ import annotations

import pytest

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p10_regulatory_data.circular_exposure import (
    detect_circular_exposures,
)


def _make_edge(
    sending_bic: str,
    receiving_bic: str,
    dependency_score: float = 0.5,
    observation_count: int = 10,
    timestamp: float = 1000.0,
) -> PaymentEdge:
    """Factory for test PaymentEdge instances."""
    return PaymentEdge(
        uetr=f"UETR-{sending_bic}-{receiving_bic}",
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount_usd=100_000.0,
        currency_pair="EUR_USD",
        timestamp=timestamp,
        dependency_score=dependency_score,
        observation_count=observation_count,
    )


def _make_graph(
    edge_specs: list[tuple[str, str, float, int]],
) -> CorridorGraph:
    """Build a CorridorGraph from (sender, receiver, dep_score, obs_count) tuples."""
    nodes_set: set[str] = set()
    edges: list[PaymentEdge] = []
    adjacency: dict[str, dict[str, list[PaymentEdge]]] = {}

    for sender, receiver, score, obs in edge_specs:
        nodes_set.add(sender)
        nodes_set.add(receiver)
        edge = _make_edge(sender, receiver, score, obs)
        edges.append(edge)
        adjacency.setdefault(sender, {}).setdefault(receiver, []).append(edge)

    return CorridorGraph(
        nodes=sorted(nodes_set),
        edges=edges,
        adjacency=adjacency,
    )


class TestCircularExposureDetection:
    """Verify detect_circular_exposures() on various graph topologies."""

    def test_no_cycles_in_acyclic_graph(self):
        """Linear chain A->B->C has no cycles."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        assert result == []

    def test_simple_triangle_detected(self):
        """A->B->C->A with all edges >= 0.3 returns one CircularExposure."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        assert len(result) == 1
        assert result[0].cycle_length == 3
        assert result[0].flagged_for_review is True

    def test_cycle_weight_below_threshold_excluded(self):
        """One edge below min_cycle_weight breaks the cycle detection."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.2, 10),  # below default 0.3 threshold
            ("C", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph, min_cycle_weight=0.3)
        assert result == []

    def test_cycle_exceeding_max_length_excluded(self):
        """6-node cycle with max_cycle_length=5 is not detected."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "D", 0.5, 10),
            ("D", "E", 0.5, 10),
            ("E", "F", 0.5, 10),
            ("F", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph, max_cycle_length=5)
        assert result == []

    def test_cycle_at_max_length_included(self):
        """5-node cycle with max_cycle_length=5 is detected."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "D", 0.5, 10),
            ("D", "E", 0.5, 10),
            ("E", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph, max_cycle_length=5)
        assert len(result) == 1
        assert result[0].cycle_length == 5

    def test_aggregate_weight_is_product(self):
        """Triangle with scores 0.4, 0.5, 0.6 → aggregate ≈ 0.12."""
        graph = _make_graph([
            ("A", "B", 0.4, 10),
            ("B", "C", 0.5, 10),
            ("C", "A", 0.6, 10),
        ])
        result = detect_circular_exposures(graph, min_cycle_weight=0.3)
        assert len(result) == 1
        assert result[0].aggregate_weight == pytest.approx(0.4 * 0.5 * 0.6, rel=1e-6)

    def test_min_max_edge_weights(self):
        """Verify min_edge_weight and max_edge_weight on a triangle."""
        graph = _make_graph([
            ("A", "B", 0.4, 10),
            ("B", "C", 0.3, 10),
            ("C", "A", 0.6, 10),
        ])
        result = detect_circular_exposures(graph, min_cycle_weight=0.3)
        assert len(result) == 1
        assert result[0].min_edge_weight == pytest.approx(0.3)
        assert result[0].max_edge_weight == pytest.approx(0.6)

    def test_confidence_high_when_well_observed(self):
        """All edges with observation_count >= 5 → confidence='HIGH'."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 8),
            ("C", "A", 0.5, 5),
        ])
        result = detect_circular_exposures(graph)
        assert len(result) == 1
        assert result[0].confidence == "HIGH"

    def test_confidence_low_when_sparse(self):
        """One edge with observation_count=2 → confidence='LOW'."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 2),
            ("C", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        assert len(result) == 1
        assert result[0].confidence == "LOW"

    def test_multiple_independent_cycles(self):
        """Two independent triangles are both detected."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "A", 0.5, 10),
            ("X", "Y", 0.5, 10),
            ("Y", "Z", 0.5, 10),
            ("Z", "X", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        assert len(result) == 2

    def test_overlapping_cycles_both_reported(self):
        """A->B->C->A and A->B->D->A share edge A->B, both reported."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "A", 0.5, 10),
            ("B", "D", 0.5, 10),
            ("D", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        assert len(result) == 2

    def test_duplicate_cycles_deduplicated(self):
        """Same cycle discovered from different starts is reported once."""
        graph = _make_graph([
            ("A", "B", 0.5, 10),
            ("B", "C", 0.5, 10),
            ("C", "A", 0.5, 10),
        ])
        result = detect_circular_exposures(graph)
        # Regardless of starting node (A, B, or C), the cycle is the same
        assert len(result) == 1

    def test_empty_graph_returns_empty(self):
        """Graph with no edges returns empty list."""
        graph = CorridorGraph(nodes=["A", "B"], edges=[], adjacency={})
        result = detect_circular_exposures(graph)
        assert result == []

    def test_single_node_no_self_loop(self):
        """Single node with no edges returns empty list."""
        graph = CorridorGraph(nodes=["A"], edges=[], adjacency={})
        result = detect_circular_exposures(graph)
        assert result == []
