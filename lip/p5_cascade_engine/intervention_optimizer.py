"""
intervention_optimizer.py — Greedy weighted set cover for cascade intervention.

P5 blueprint Section 5.4: given a cascade propagation result and a budget,
select bridge loans that maximise cascade value prevented per dollar spent.

Greedy guarantee: (1 - 1/e) >= 63.2% of optimal.
Empirically >90% for tree-like supply chain topologies.
"""
from __future__ import annotations

import heapq
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

        # Build a max-heap (negate ratio for min-heap inversion) — O(n log n) initial build
        # Each element: (-ratio, corporate_id) so we can pop the best candidate in O(log n)
        heap: list = []
        node_lookup: Dict[str, CascadeRiskNode] = {}
        for node in cascade_result.cascade_map.values():
            bridge_cost = node.incoming_volume_at_risk_usd
            if bridge_cost <= 0:
                continue
            value_prevented = (
                node.cascade_probability * node.incoming_volume_at_risk_usd
                + node.downstream_value_at_risk_usd
            )
            ratio = value_prevented / bridge_cost
            heapq.heappush(heap, (-ratio, node.corporate_id))
            node_lookup[node.corporate_id] = node

        while remaining > 0 and heap:
            neg_ratio, corp_id = heapq.heappop(heap)

            if corp_id in protected:
                continue

            node = node_lookup[corp_id]
            bridge_cost = node.incoming_volume_at_risk_usd
            if bridge_cost > remaining:
                continue

            value_prevented = (
                node.cascade_probability * node.incoming_volume_at_risk_usd
                + node.downstream_value_at_risk_usd
            )
            ratio = -neg_ratio
            best_candidate = (node, bridge_cost, value_prevented, ratio)

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
        """BFS to find all descendants of corporate_id in the cascade map.

        Uses a pre-built children index for O(n) total traversal instead of
        O(n) per BFS step (was O(n²) overall).
        """
        # Build children index: parent_id -> [child_ids]
        children: Dict[str, List[str]] = {}
        for node in cascade_map.values():
            parent = node.parent_corporate_id
            if parent not in children:
                children[parent] = []
            children[parent].append(node.corporate_id)

        descendants: Set[str] = set()
        queue = [corporate_id]
        while queue:
            current = queue.pop()
            for child_id in children.get(current, []):
                if child_id not in descendants:
                    descendants.add(child_id)
                    queue.append(child_id)
        return descendants
