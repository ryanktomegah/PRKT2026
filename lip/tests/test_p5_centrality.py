"""
test_p5_centrality.py — Tests for Brandes betweenness centrality on CascadeGraph.

Tests use known graph topologies with analytically computable centrality values.
"""
from __future__ import annotations

from collections import defaultdict

import pytest

from lip.p5_cascade_engine.corporate_graph import CascadeGraph, CorporateEdge, CorporateNode


def _build_cascade_direct(edges_spec: list[tuple]) -> CascadeGraph:
    """Build a CascadeGraph directly from (source, target) corporate pairs."""
    corp_edges = []
    adj: dict = defaultdict(dict)
    rev: dict = defaultdict(dict)
    all_corps: set = set()

    for src, tgt in edges_spec:
        ce = CorporateEdge(
            source_corporate_id=src,
            target_corporate_id=tgt,
            total_volume_30d=100_000.0,
            payment_count_30d=5,
            dependency_score=0.5,
        )
        corp_edges.append(ce)
        adj[src][tgt] = ce
        rev[tgt][src] = ce
        all_corps.add(src)
        all_corps.add(tgt)

    nodes = {c: CorporateNode(corporate_id=c) for c in all_corps}

    return CascadeGraph(
        nodes=nodes,
        edges=corp_edges,
        adjacency=dict(adj),
        reverse_adjacency=dict(rev),
        node_count=len(nodes),
        edge_count=len(corp_edges),
    )


class TestBrandesCentrality:

    def test_star_graph_center_highest(self):
        """Star: A->B, A->C, A->D. In directed star, no shortest paths pass through any node."""
        graph = _build_cascade_direct([("A", "B"), ("A", "C"), ("A", "D")])
        graph.compute_centrality()
        for node in graph.nodes.values():
            assert node.cascade_centrality == pytest.approx(0.0, abs=1e-6)

    def test_chain_graph_middle_highest(self):
        """Chain: A->B->C->D. B and C sit on shortest paths."""
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()
        assert graph.nodes["A"].cascade_centrality == pytest.approx(0.0, abs=1e-6)
        assert graph.nodes["D"].cascade_centrality == pytest.approx(0.0, abs=1e-6)
        assert graph.nodes["B"].cascade_centrality > 0
        assert graph.nodes["C"].cascade_centrality > 0

    def test_chain_b_and_c_equal(self):
        """In A->B->C->D, B and C have equal centrality."""
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()
        assert graph.nodes["B"].cascade_centrality == pytest.approx(
            graph.nodes["C"].cascade_centrality, abs=1e-6
        )

    def test_diamond_junction_highest(self):
        """Diamond: A->B, A->C, B->D, C->D. B and C are parallel — equal centrality."""
        graph = _build_cascade_direct([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])
        graph.compute_centrality()
        assert graph.nodes["B"].cascade_centrality == pytest.approx(
            graph.nodes["C"].cascade_centrality, abs=1e-6
        )

    def test_single_node_zero_centrality(self):
        nodes = {"SOLO": CorporateNode(corporate_id="SOLO")}
        graph = CascadeGraph(nodes=nodes, node_count=1)
        graph.compute_centrality()
        assert graph.nodes["SOLO"].cascade_centrality == 0.0

    def test_empty_graph(self):
        graph = CascadeGraph()
        graph.compute_centrality()  # Should not raise

    def test_max_cascade_centrality_node_set(self):
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()
        assert graph.max_cascade_centrality_node in ("B", "C")

    def test_centrality_normalized_0_to_1(self):
        graph = _build_cascade_direct([
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"),
            ("A", "C"), ("B", "D"),
        ])
        graph.compute_centrality()
        for node in graph.nodes.values():
            assert 0.0 <= node.cascade_centrality <= 1.0
