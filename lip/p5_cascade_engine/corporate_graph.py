"""
corporate_graph.py — Corporate-level graph data structures for P5 cascade engine.

CorporateNode: represents a corporate entity transacting via one or more BICs.
CorporateEdge: directed supply chain payment edge between two corporates.
CascadeGraph: snapshot of the corporate-level directed graph.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List

logger = logging.getLogger(__name__)


@dataclass
class CorporateNode:
    """A corporate entity in the supply chain graph."""

    corporate_id: str
    name_hash: str = ""
    bics: FrozenSet[str] = field(default_factory=frozenset)
    sector: str = "UNKNOWN"
    jurisdiction: str = "XX"
    total_incoming_volume_30d: float = 0.0
    total_outgoing_volume_30d: float = 0.0
    dependency_scores: Dict[str, float] = field(default_factory=dict)
    cascade_centrality: float = 0.0


@dataclass
class CorporateEdge:
    """Directed supply chain payment edge between two corporates."""

    source_corporate_id: str
    target_corporate_id: str
    total_volume_30d: float = 0.0
    payment_count_30d: int = 0
    dependency_score: float = 0.0
    failure_rate_30d: float = 0.0
    avg_settlement_hours: float = 0.0
    last_payment_timestamp: float = 0.0


@dataclass
class CascadeGraph:
    """Snapshot of the corporate-level directed graph."""

    nodes: Dict[str, CorporateNode] = field(default_factory=dict)
    edges: List[CorporateEdge] = field(default_factory=list)
    adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    build_timestamp: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    avg_dependency_score: float = 0.0
    max_cascade_centrality_node: str = ""
    corridor_to_corporates: Dict[str, List[str]] = field(default_factory=dict)
    """Maps currency-pair corridor (e.g. 'EUR_USD') to corporate IDs with volume on it."""

    def get_downstream_dependents(
        self, corporate_id: str, threshold: float = 0.2
    ) -> List[str]:
        """Return corporate IDs downstream with dependency_score >= threshold."""
        targets = self.adjacency.get(corporate_id, {})
        return [
            cid for cid, edge in targets.items()
            if edge.dependency_score >= threshold
        ]

    def get_corporates_on_corridor(self, corridor: str) -> List[str]:
        """Return corporate IDs with payment volume on the given corridor."""
        return list(self.corridor_to_corporates.get(corridor, []))

    def compute_centrality(self) -> None:
        """Compute betweenness centrality for all nodes (Brandes algorithm)."""
        if not self.nodes:
            return

        centrality = _brandes_betweenness(self.adjacency, set(self.nodes.keys()))

        max_centrality = 0.0
        max_node = ""
        for corp_id, score in centrality.items():
            self.nodes[corp_id].cascade_centrality = score
            if score > max_centrality:
                max_centrality = score
                max_node = corp_id

        self.max_cascade_centrality_node = max_node
        logger.info(
            "compute_centrality: %d nodes, max_centrality=%.4f at %s",
            len(self.nodes), max_centrality, max_node,
        )


def _brandes_betweenness(
    adjacency: Dict[str, Dict[str, CorporateEdge]],
    all_nodes: set,
) -> Dict[str, float]:
    """Compute betweenness centrality using Brandes (2001) algorithm.

    Unweighted variant. Returns {corporate_id: centrality_score} normalized to [0, 1].
    """
    cb: Dict[str, float] = {v: 0.0 for v in all_nodes}

    for s in all_nodes:
        stack: list = []
        predecessors: Dict[str, list] = {v: [] for v in all_nodes}
        sigma: Dict[str, int] = {v: 0 for v in all_nodes}
        sigma[s] = 1
        dist: Dict[str, int] = {v: -1 for v in all_nodes}
        dist[s] = 0
        queue: deque = deque([s])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adjacency.get(v, {}):
                if w not in all_nodes:
                    continue
                if dist[w] < 0:
                    queue.append(w)
                    dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)

        delta: Dict[str, float] = {v: 0.0 for v in all_nodes}
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]

    n = len(all_nodes)
    if n > 2:
        normalization = (n - 1) * (n - 2)
        for v in cb:
            cb[v] /= normalization

    return cb
