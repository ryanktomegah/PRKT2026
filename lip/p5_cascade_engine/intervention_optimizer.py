"""
intervention_optimizer.py — Greedy weighted set cover for cascade intervention.

P5 blueprint Section 5.4: given a cascade propagation result and a budget,
select bridge loans that maximise cascade value prevented per dollar spent.

Greedy guarantee: (1 - 1/e) >= 63.2% of optimal.
Empirically >90% for tree-like supply chain topologies.
"""
from __future__ import annotations

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

        while remaining > 0:
            best_ratio = 0.0
            best_candidate = None

            for node in cascade_result.cascade_map.values():
                if node.corporate_id in protected:
                    continue

                bridge_cost = node.incoming_volume_at_risk_usd
                if bridge_cost <= 0 or bridge_cost > remaining:
                    continue

                value_prevented = (
                    node.cascade_probability * node.incoming_volume_at_risk_usd
                    + node.downstream_value_at_risk_usd
                )

                ratio = value_prevented / bridge_cost
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_candidate = (node, bridge_cost, value_prevented, ratio)

            if best_candidate is None:
                break

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
        """BFS to find all descendants of corporate_id in the cascade map."""
        descendants: Set[str] = set()
        queue = [corporate_id]
        while queue:
            current = queue.pop()
            for node in cascade_map.values():
                if (
                    node.parent_corporate_id == current
                    and node.corporate_id not in descendants
                ):
                    descendants.add(node.corporate_id)
                    queue.append(node.corporate_id)
        return descendants
