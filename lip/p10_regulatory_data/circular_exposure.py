"""
Circular exposure detection for BIC payment graphs.

Sprint 6 P10/C6 extension: identifies circular dependency chains in a
:class:`~lip.c1_failure_classifier.graph_builder.CorridorGraph` using
modified depth-first search (DFS).  Detected cycles represent closed loops
of institutional dependency (A -> B -> C -> A) where each edge's Bayesian-
smoothed ``dependency_score`` exceeds a configurable threshold.

Flagged cycles are soft-flagged only (``flagged_for_review=True``) per
CIPHER rule -- no automated action is taken.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p10_regulatory_data.constants import (
    P10_CIRCULAR_EXPOSURE_MAX_LENGTH,
    P10_CIRCULAR_EXPOSURE_MIN_WEIGHT,
)

logger = logging.getLogger(__name__)

# Bayesian smoothing constant -- mirrored from graph_builder._SMOOTHING_K.
# Cycles where every edge has observation_count >= this value are HIGH confidence.
_CONFIDENCE_OBSERVATION_THRESHOLD: int = 5


@dataclass(frozen=True)
class CircularExposure:
    """An identified circular dependency chain in the BIC payment graph.

    Each instance represents a closed cycle of BIC nodes where every directed
    edge carries a ``dependency_score`` above the detection threshold.

    Attributes
    ----------
    cycle_nodes:
        BIC chain as a tuple.  ``(A, B, C)`` represents the cycle
        A -> B -> C -> A.  The tuple is canonically rotated so the
        lexicographically smallest BIC appears first.
    cycle_length:
        Number of nodes in the cycle (equal to ``len(cycle_nodes)``).
    aggregate_weight:
        Product of all edge ``dependency_score`` values around the cycle.
    min_edge_weight:
        Weakest (lowest ``dependency_score``) link in the cycle.
    max_edge_weight:
        Strongest (highest ``dependency_score``) link in the cycle.
    min_observation_count:
        Lowest ``observation_count`` across all cycle edges.  Values below
        ``_CONFIDENCE_OBSERVATION_THRESHOLD`` (5) indicate that at least one
        edge score is still pulled significantly toward the Bayesian prior.
    confidence:
        ``"HIGH"`` if every edge in the cycle has ``observation_count >= 5``
        (the Bayesian smoothing constant ``_SMOOTHING_K``), otherwise ``"LOW"``.
    flagged_for_review:
        Soft flag only (CIPHER rule).  Always ``True`` by default -- no
        automated enforcement action is taken on detected cycles.
    """

    cycle_nodes: tuple[str, ...]
    cycle_length: int
    aggregate_weight: float
    min_edge_weight: float
    max_edge_weight: float
    min_observation_count: int
    confidence: str
    flagged_for_review: bool = True


def _canonicalize_cycle(cycle: List[str]) -> Tuple[str, ...]:
    """Rotate *cycle* so the lexicographically smallest BIC is first.

    This ensures that cycles discovered from different starting nodes are
    deduplicated correctly (e.g. ``(A, B, C)`` and ``(B, C, A)`` both
    canonicalize to ``(A, B, C)``).
    """
    if not cycle:
        return ()
    min_idx = cycle.index(min(cycle))
    return tuple(cycle[min_idx:] + cycle[:min_idx])


def _latest_edge(edges: List[PaymentEdge]) -> PaymentEdge:
    """Return the edge with the highest timestamp from a non-empty list."""
    return max(edges, key=lambda e: e.timestamp)


def detect_circular_exposures(
    graph: CorridorGraph,
    min_cycle_weight: float = float(P10_CIRCULAR_EXPOSURE_MIN_WEIGHT),
    max_cycle_length: int = P10_CIRCULAR_EXPOSURE_MAX_LENGTH,
) -> list[CircularExposure]:
    """Detect circular dependency chains in a BIC payment graph.

    Runs a modified DFS from every node in *graph*, tracking the current
    recursion path.  When a back-edge is found (a neighbour already on the
    current path), the cycle is extracted, canonicalized, and -- if it passes
    weight and length filters -- added to the result set.

    Edge selection: for each ``(sender, receiver)`` pair that may have
    multiple :class:`PaymentEdge` instances, the **latest by timestamp** is
    selected and its ``dependency_score`` is used.

    Parameters
    ----------
    graph:
        A :class:`~lip.c1_failure_classifier.graph_builder.CorridorGraph`
        snapshot built by :class:`BICGraphBuilder.build_graph`.
    min_cycle_weight:
        Minimum ``dependency_score`` for an edge to be traversed.  Edges
        below this threshold are pruned during DFS.  Defaults to
        ``P10_CIRCULAR_EXPOSURE_MIN_WEIGHT`` (0.3).
    max_cycle_length:
        Maximum number of nodes in a reportable cycle.  Cycles longer than
        this are discarded.  Defaults to ``P10_CIRCULAR_EXPOSURE_MAX_LENGTH``
        (5).

    Returns
    -------
    list[CircularExposure]
        Deduplicated list of detected circular exposures, sorted by
        ``aggregate_weight`` descending (highest-risk cycles first).
    """
    # Pre-compute the latest edge for each (sender, receiver) pair and cache
    # only those that meet the minimum weight threshold.
    latest_edges: Dict[str, Dict[str, PaymentEdge]] = {}
    for sender, receivers in graph.adjacency.items():
        for receiver, edges in receivers.items():
            if not edges:
                continue
            edge = _latest_edge(edges)
            if edge.dependency_score >= min_cycle_weight:
                latest_edges.setdefault(sender, {})[receiver] = edge

    seen_cycles: Set[Tuple[str, ...]] = set()
    results: List[CircularExposure] = []

    def _dfs(
        node: str,
        path: List[str],
        path_set: Set[str],
    ) -> None:
        """Iterative-style recursive DFS collecting cycles via back-edges."""
        neighbours = latest_edges.get(node)
        if neighbours is None:
            return

        for neighbour, edge in neighbours.items():
            if neighbour in path_set:
                # Back-edge found -- extract the cycle.
                cycle_start_idx = path.index(neighbour)
                raw_cycle = path[cycle_start_idx:]

                if len(raw_cycle) > max_cycle_length:
                    continue

                canonical = _canonicalize_cycle(raw_cycle)
                if canonical in seen_cycles:
                    continue
                seen_cycles.add(canonical)

                # Gather edge metrics around the cycle.
                edge_scores: List[float] = []
                edge_obs_counts: List[int] = []
                for i in range(len(raw_cycle)):
                    src = raw_cycle[i]
                    dst = raw_cycle[(i + 1) % len(raw_cycle)]
                    cycle_edge = latest_edges[src][dst]
                    edge_scores.append(cycle_edge.dependency_score)
                    edge_obs_counts.append(cycle_edge.observation_count)

                aggregate_weight = math.prod(edge_scores)
                min_obs = min(edge_obs_counts)

                exposure = CircularExposure(
                    cycle_nodes=canonical,
                    cycle_length=len(canonical),
                    aggregate_weight=aggregate_weight,
                    min_edge_weight=min(edge_scores),
                    max_edge_weight=max(edge_scores),
                    min_observation_count=min_obs,
                    confidence=(
                        "HIGH"
                        if min_obs >= _CONFIDENCE_OBSERVATION_THRESHOLD
                        else "LOW"
                    ),
                )
                results.append(exposure)
            else:
                path.append(neighbour)
                path_set.add(neighbour)
                _dfs(neighbour, path, path_set)
                path.pop()
                path_set.discard(neighbour)

    # Launch DFS from every node in the graph.
    for start_node in graph.nodes:
        _dfs(start_node, [start_node], {start_node})

    # Sort by aggregate_weight descending (highest-risk first).
    results.sort(key=lambda ce: ce.aggregate_weight, reverse=True)

    logger.info(
        "detect_circular_exposures: found %d cycles (min_weight=%.2f, max_length=%d)",
        len(results),
        min_cycle_weight,
        max_cycle_length,
    )
    return results
