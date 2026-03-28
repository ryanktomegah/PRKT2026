"""
corporate_features.py — 8-dimensional corporate node feature extraction.

Feature vector (CORPORATE_NODE_FEATURE_DIM = 8):
  [0] total_incoming_volume_30d  — log1p of incoming USD
  [1] total_outgoing_volume_30d  — log1p of outgoing USD
  [2] supplier_count             — distinct upstream corporates
  [3] customer_count             — distinct downstream corporates
  [4] max_dependency_score       — highest dependency on any sender
  [5] hhi_supplier_concentration — HHI of incoming payment volumes
  [6] failure_rate_30d           — volume-weighted avg failure rate
  [7] cascade_centrality         — betweenness centrality
"""
from __future__ import annotations

import math

import numpy as np

from lip.p5_cascade_engine.constants import CORPORATE_NODE_FEATURE_DIM
from lip.p5_cascade_engine.corporate_graph import CascadeGraph


def get_corporate_node_features(
    graph: CascadeGraph, corporate_id: str
) -> np.ndarray:
    """Return 8-dimensional feature vector for a corporate node."""
    node = graph.nodes.get(corporate_id)
    if node is None:
        return np.zeros(CORPORATE_NODE_FEATURE_DIM, dtype=np.float64)

    f_incoming = math.log1p(node.total_incoming_volume_30d)
    f_outgoing = math.log1p(node.total_outgoing_volume_30d)

    upstream = graph.reverse_adjacency.get(corporate_id, {})
    f_supplier_count = float(len(upstream))

    downstream = graph.adjacency.get(corporate_id, {})
    f_customer_count = float(len(downstream))

    f_max_dep = max(node.dependency_scores.values(), default=0.0)
    f_hhi = _compute_hhi(graph, corporate_id)
    f_failure_rate = _compute_failure_rate(graph, corporate_id)
    f_centrality = node.cascade_centrality

    return np.array(
        [f_incoming, f_outgoing, f_supplier_count, f_customer_count,
         f_max_dep, f_hhi, f_failure_rate, f_centrality],
        dtype=np.float64,
    )


def _compute_hhi(graph: CascadeGraph, corporate_id: str) -> float:
    """Herfindahl-Hirschman index of incoming payment volume concentration."""
    upstream = graph.reverse_adjacency.get(corporate_id, {})
    if not upstream:
        return 0.0

    total = sum(e.total_volume_30d for e in upstream.values())
    if total <= 0:
        return 0.0

    return sum((e.total_volume_30d / total) ** 2 for e in upstream.values())


def _compute_failure_rate(graph: CascadeGraph, corporate_id: str) -> float:
    """Volume-weighted average failure rate across incoming edges."""
    upstream = graph.reverse_adjacency.get(corporate_id, {})
    if not upstream:
        return 0.0

    total = sum(e.total_volume_30d for e in upstream.values())
    if total <= 0:
        return 0.0

    return sum(
        e.total_volume_30d * e.failure_rate_30d for e in upstream.values()
    ) / total
