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
from typing import Dict

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

        # Phase 2: Bottom-up CVaR computation — O(n) with pre-built children index
        # Build children index once instead of scanning all nodes per parent (was O(n²))
        children_index: Dict[str, list] = {}
        for child in cascade_map.values():
            parent = child.parent_corporate_id
            if parent not in children_index:
                children_index[parent] = []
            children_index[parent].append(child)

        # Sort by hop distance descending (deepest first) — O(n log n) sort, O(n) pass
        sorted_nodes = sorted(
            cascade_map.values(), key=lambda n: n.hop_distance, reverse=True
        )
        for node in sorted_nodes:
            children_cvar = sum(
                child.cascade_probability * child.incoming_volume_at_risk_usd
                + child.downstream_value_at_risk_usd
                for child in children_index.get(node.corporate_id, [])
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
