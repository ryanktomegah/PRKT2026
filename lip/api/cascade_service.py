"""
cascade_service.py — Cascade intervention service layer.

Manages CascadeGraph, alert lifecycle (create → active → executed/expired),
and intervention execution tracking. In-memory storage for v0.

Sprint 3d: C7 Coordinated Intervention API (P5 Supply Chain Cascade).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lip.p5_cascade_engine.cascade_alerts import CascadeAlert, build_cascade_alert
from lip.p5_cascade_engine.corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


@dataclass
class InterventionStatus:
    """Tracks execution state of a cascade intervention."""

    alert_id: str
    status: str  # "PENDING", "EXECUTED", "EXPIRED"
    executed_actions: List[int] = field(default_factory=list)
    total_bridge_amount_usd: float = 0.0
    total_value_prevented_usd: float = 0.0
    executed_at: Optional[float] = None


@dataclass
class CorporateNeighborhood:
    """Dependency neighborhood for a single corporate."""

    corporate_id: str
    sector: str
    jurisdiction: str
    cascade_centrality: float
    upstream: List[dict] = field(default_factory=list)
    downstream: List[dict] = field(default_factory=list)


@dataclass
class GraphSummary:
    """High-level graph metadata."""

    node_count: int
    edge_count: int
    avg_dependency_score: float
    max_centrality_node: str
    build_timestamp: float


class CascadeService:
    """Cascade alert lifecycle management and graph queries.

    Holds a CascadeGraph reference and an in-memory alert store with
    lazy TTL eviction. Delegates cascade analysis to build_cascade_alert()
    and intervention optimization to InterventionOptimizer (via the alert).
    """

    def __init__(self, cascade_graph: CascadeGraph, default_budget_usd: float):
        self._graph = cascade_graph
        self._budget = default_budget_usd
        self._alerts: Dict[str, CascadeAlert] = {}
        self._intervention_status: Dict[str, InterventionStatus] = {}

    def analyze(
        self,
        corporate_id: str,
        budget_usd: Optional[float] = None,
        trigger_type: str = "PAYMENT_FAILURE",
    ) -> Optional[CascadeAlert]:
        """Trigger cascade analysis for a corporate.

        Delegates to build_cascade_alert(). If CVaR >= threshold, stores
        the alert for later retrieval and returns it.
        """
        budget = budget_usd if budget_usd is not None else self._budget
        alert = build_cascade_alert(
            graph=self._graph,
            origin_corporate_id=corporate_id,
            budget_usd=budget,
            trigger_type=trigger_type,
        )
        if alert is not None:
            self._alerts[alert.alert_id] = alert
            logger.info(
                "analyze: alert=%s severity=%s cvar=%.0f corporate=%s",
                alert.alert_id,
                alert.severity,
                alert.cascade_result.total_value_at_risk_usd,
                corporate_id,
            )
        return alert

    def list_alerts(
        self,
        severity: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CascadeAlert]:
        """List alerts with optional severity filter and active-only flag."""
        now = time.time()
        results = []
        for alert in self._alerts.values():
            if active_only and alert.expires_at < now:
                continue
            if severity is not None and alert.severity != severity:
                continue
            results.append(alert)
        return sorted(results, key=lambda a: a.timestamp, reverse=True)

    def get_alert(self, alert_id: str) -> Optional[CascadeAlert]:
        """Get a specific alert by ID. Returns expired alerts too."""
        return self._alerts.get(alert_id)

    def execute_intervention(
        self, alert_id: str, action_priorities: List[int]
    ) -> Optional[InterventionStatus]:
        """Execute selected interventions from an alert's plan.

        Returns None if alert not found. Returns EXPIRED status if
        the alert's exclusivity window has passed.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None

        now = time.time()
        if alert.expires_at < now:
            status = InterventionStatus(alert_id=alert_id, status="EXPIRED")
            self._intervention_status[alert_id] = status
            return status

        # Find matching interventions
        executed = []
        total_bridge = 0.0
        total_value = 0.0
        if alert.intervention_plan is not None:
            for action in alert.intervention_plan.interventions:
                if action.priority in action_priorities:
                    executed.append(action.priority)
                    total_bridge += action.bridge_amount_usd
                    total_value += action.cascade_value_prevented_usd

        status = InterventionStatus(
            alert_id=alert_id,
            status="EXECUTED",
            executed_actions=executed,
            total_bridge_amount_usd=total_bridge,
            total_value_prevented_usd=total_value,
            executed_at=now,
        )
        self._intervention_status[alert_id] = status
        logger.info(
            "execute_intervention: alert=%s actions=%d bridge=%.0f value_prevented=%.0f",
            alert_id,
            len(executed),
            total_bridge,
            total_value,
        )
        return status

    def get_intervention_status(self, alert_id: str) -> Optional[InterventionStatus]:
        """Get execution status for an alert."""
        return self._intervention_status.get(alert_id)

    def get_corporate_neighbors(
        self, corporate_id: str
    ) -> Optional[CorporateNeighborhood]:
        """Get upstream and downstream dependency neighborhood."""
        node = self._graph.nodes.get(corporate_id)
        if node is None:
            return None

        downstream = []
        for target_id, edge in self._graph.adjacency.get(corporate_id, {}).items():
            downstream.append({
                "corporate_id": target_id,
                "dependency_score": edge.dependency_score,
                "volume_30d": edge.total_volume_30d,
            })

        upstream = []
        for source_id, edge in self._graph.reverse_adjacency.get(
            corporate_id, {}
        ).items():
            upstream.append({
                "corporate_id": source_id,
                "dependency_score": edge.dependency_score,
                "volume_30d": edge.total_volume_30d,
            })

        return CorporateNeighborhood(
            corporate_id=corporate_id,
            sector=node.sector,
            jurisdiction=node.jurisdiction,
            cascade_centrality=node.cascade_centrality,
            upstream=upstream,
            downstream=downstream,
        )

    def get_graph_summary(self) -> GraphSummary:
        """Return high-level graph metadata."""
        return GraphSummary(
            node_count=self._graph.node_count,
            edge_count=self._graph.edge_count,
            avg_dependency_score=self._graph.avg_dependency_score,
            max_centrality_node=self._graph.max_cascade_centrality_node,
            build_timestamp=self._graph.build_timestamp,
        )
