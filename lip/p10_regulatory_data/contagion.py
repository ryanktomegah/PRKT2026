"""
contagion.py — BFS contagion simulation across corridor dependency graph.

Dependency graph: corridors are nodes, edges connect corridors that share
correspondent banks (from anonymized data). Edge weight = Jaccard similarity
of bank hash sets. Privacy-preserving by construction — no raw BICs used.

Algorithm:
  1. Seed origin corridor at shock_magnitude
  2. BFS: for each neighbor, propagated_stress = parent_stress * edge_weight * decay
  3. Prune if propagated_stress < threshold
  4. Stop at max_hops
  5. Aggregate: count affected, sum volume at risk, compute systemic score

QUANT authority: propagation decay, threshold calibration, risk scoring.
CIPHER authority: privacy preservation (bank hash sets only).
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from .constants import (
    P10_CONTAGION_MAX_HOPS,
    P10_CONTAGION_PROPAGATION_DECAY,
    P10_CONTAGION_STRESS_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContagionNode:
    """One node in the contagion propagation result."""

    corridor: str
    stress_level: float  # 0.0-1.0 propagated stress
    hop_distance: int
    propagation_path: Tuple[str, ...]  # corridor chain from origin


@dataclass(frozen=True)
class ContagionResult:
    """Complete result of a contagion simulation."""

    origin_corridor: str
    shock_magnitude: float
    affected_corridors: List[ContagionNode]
    max_propagation_depth: int
    total_volume_at_risk_usd: float
    systemic_risk_score: float  # 0.0-1.0


class ContagionSimulator:
    """BFS stress propagation across corridor dependency graph.

    Thread-safety: stateless — safe for concurrent use.
    """

    def __init__(
        self,
        propagation_decay: float = float(P10_CONTAGION_PROPAGATION_DECAY),
        max_hops: int = P10_CONTAGION_MAX_HOPS,
        stress_threshold: float = float(P10_CONTAGION_STRESS_THRESHOLD),
    ):
        self._decay = propagation_decay
        self._max_hops = max_hops
        self._threshold = stress_threshold

    def build_dependency_graph(
        self,
        corridor_bank_sets: Dict[str, Set[str]],
    ) -> Dict[str, Dict[str, float]]:
        """Build adjacency from corridor -> bank_hash sets.

        Edge weight = Jaccard similarity of bank sets.
        Only creates edges where Jaccard > 0.
        """
        corridors = list(corridor_bank_sets.keys())
        graph: Dict[str, Dict[str, float]] = {c: {} for c in corridors}

        for c1, c2 in combinations(corridors, 2):
            s1, s2 = corridor_bank_sets[c1], corridor_bank_sets[c2]
            union_size = len(s1 | s2)
            if union_size == 0:
                continue
            jaccard = len(s1 & s2) / union_size
            if jaccard > 0:
                graph[c1][c2] = jaccard
                graph[c2][c1] = jaccard

        return graph

    def simulate(
        self,
        graph: Dict[str, Dict[str, float]],
        origin_corridor: str,
        shock_magnitude: float,
        corridor_volumes: Optional[Dict[str, float]] = None,
    ) -> ContagionResult:
        """Run BFS contagion from origin corridor.

        Args:
            graph: Adjacency dict from build_dependency_graph.
            origin_corridor: The corridor experiencing the shock.
            shock_magnitude: Initial stress level (0.0-1.0).
            corridor_volumes: Optional volume per corridor (for risk scoring).

        Returns:
            ContagionResult with affected corridors and systemic risk score.
        """
        if shock_magnitude <= 0.0 or origin_corridor not in graph:
            return ContagionResult(
                origin_corridor=origin_corridor,
                shock_magnitude=shock_magnitude,
                affected_corridors=[],
                max_propagation_depth=0,
                total_volume_at_risk_usd=0.0,
                systemic_risk_score=0.0,
            )

        visited: Set[str] = {origin_corridor}
        affected: List[ContagionNode] = []
        max_depth = 0

        # BFS queue: (corridor, stress_level, hop_count, path)
        queue: deque[Tuple[str, float, int, Tuple[str, ...]]] = deque()

        # Seed neighbors of origin
        for neighbor, weight in graph.get(origin_corridor, {}).items():
            propagated = shock_magnitude * weight * self._decay
            if propagated >= self._threshold:
                queue.append((neighbor, propagated, 1, (origin_corridor, neighbor)))

        while queue:
            corridor, stress, hops, path = queue.popleft()

            if corridor in visited:
                continue
            if hops > self._max_hops:
                continue

            visited.add(corridor)
            affected.append(
                ContagionNode(
                    corridor=corridor,
                    stress_level=stress,
                    hop_distance=hops,
                    propagation_path=path,
                )
            )
            max_depth = max(max_depth, hops)

            # Propagate to neighbors
            for neighbor, weight in graph.get(corridor, {}).items():
                if neighbor not in visited:
                    propagated = stress * weight * self._decay
                    if propagated >= self._threshold:
                        queue.append(
                            (
                                neighbor,
                                propagated,
                                hops + 1,
                                path + (neighbor,),
                            )
                        )

        # Compute systemic risk score
        total_volume_at_risk = 0.0
        systemic_score = 0.0

        if corridor_volumes:
            total_volume = sum(corridor_volumes.values())
            if total_volume > 0:
                for node in affected:
                    vol = corridor_volumes.get(node.corridor, 0.0)
                    total_volume_at_risk += vol * node.stress_level
                    systemic_score += (vol / total_volume) * node.stress_level
                systemic_score = min(1.0, systemic_score)

        return ContagionResult(
            origin_corridor=origin_corridor,
            shock_magnitude=shock_magnitude,
            affected_corridors=affected,
            max_propagation_depth=max_depth,
            total_volume_at_risk_usd=total_volume_at_risk,
            systemic_risk_score=systemic_score,
        )
