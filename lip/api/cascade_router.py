"""
cascade_router.py — C7 Coordinated Intervention API HTTP endpoints.
Sprint 3d: P5 Supply Chain Cascade Detection & Prevention.

Endpoints:
  POST /cascade/analyze              — Trigger cascade analysis for a corporate
  GET  /cascade/alerts               — List active alerts (optional severity filter)
  GET  /cascade/alerts/{alert_id}    — Get specific alert with intervention plan
  POST /cascade/alerts/{alert_id}/execute — Execute selected interventions
  GET  /cascade/graph/{corporate_id} — Query corporate dependency neighborhood
  GET  /cascade/graph                — Graph summary metadata
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    # ── Request / Response Models ────────────────────────────────────────────

    class CascadeAnalyzeRequest(BaseModel):
        """Request to trigger cascade analysis."""

        corporate_id: str = Field(..., description="Corporate ID to analyze")
        budget_usd: Optional[float] = Field(
            default=None, description="Override intervention budget (USD)"
        )
        trigger_type: str = Field(
            default="PAYMENT_FAILURE",
            description="PAYMENT_FAILURE or CORRIDOR_STRESS",
        )

    class CascadeAnalyzeResponse(BaseModel):
        """Result of cascade analysis."""

        alert_id: Optional[str] = None
        severity: Optional[str] = None
        total_value_at_risk_usd: float = 0.0
        cascade_amplification_factor: float = 0.0
        nodes_at_risk: int = 0
        intervention_count: int = 0
        total_intervention_cost_usd: float = 0.0
        total_value_prevented_usd: float = 0.0
        expires_at: Optional[float] = None

    class CascadeAlertSummary(BaseModel):
        """Summary of one alert in the list."""

        alert_id: str
        severity: str
        origin_corporate_id: str
        origin_sector: str
        total_value_at_risk_usd: float
        intervention_count: int
        timestamp: float
        expires_at: float
        is_expired: bool

    class CascadeAlertListResponse(BaseModel):
        """List of cascade alerts."""

        alerts: List[CascadeAlertSummary]
        total: int

    class InterventionDetail(BaseModel):
        """One intervention action in an alert."""

        priority: int
        source_corporate_id: str
        target_corporate_id: str
        bridge_amount_usd: float
        cascade_value_prevented_usd: float
        cost_efficiency_ratio: float

    class CascadeAlertDetailResponse(BaseModel):
        """Full detail for a single alert."""

        alert_id: str
        severity: str
        origin_corporate_id: str
        origin_sector: str
        origin_jurisdiction: str
        total_value_at_risk_usd: float
        cascade_amplification_factor: float
        nodes_at_risk: int
        max_hops_reached: int
        trigger_type: str
        interventions: List[InterventionDetail]
        total_intervention_cost_usd: float
        total_value_prevented_usd: float
        budget_utilization_pct: float
        timestamp: float
        expires_at: float
        execution_status: Optional[str] = None

    class ExecuteInterventionRequest(BaseModel):
        """Request to execute selected interventions."""

        action_priorities: List[int] = Field(
            ..., description="Priority indices of interventions to execute"
        )

    class ExecuteInterventionResponse(BaseModel):
        """Result of intervention execution."""

        alert_id: str
        status: str
        executed_actions: List[int]
        total_bridge_amount_usd: float
        total_value_prevented_usd: float

    class NeighborEdge(BaseModel):
        """One edge in a corporate neighborhood."""

        corporate_id: str
        dependency_score: float
        volume_30d: float

    class CorporateNeighborhoodResponse(BaseModel):
        """Dependency neighborhood for a corporate."""

        corporate_id: str
        sector: str
        jurisdiction: str
        cascade_centrality: float
        upstream: List[NeighborEdge]
        downstream: List[NeighborEdge]

    class GraphSummaryResponse(BaseModel):
        """High-level graph metadata."""

        node_count: int
        edge_count: int
        avg_dependency_score: float
        max_centrality_node: str
        build_timestamp: float

    # ── Router Factory ───────────────────────────────────────────────────────

    def make_cascade_router(cascade_service: Any, auth_dependency=None) -> APIRouter:
        """Factory that builds the C7 Cascade Intervention API router.

        Follows the same pattern as make_miplo_router, make_admin_router, etc.
        The cascade_service is captured by closure — no global state.
        """
        router = APIRouter(tags=["cascade"])

        if auth_dependency is not None:
            deps = [Depends(auth_dependency)]
        else:
            deps = []

        @router.post("/analyze", response_model=CascadeAnalyzeResponse, dependencies=deps)
        async def analyze(request: CascadeAnalyzeRequest):
            """Trigger cascade analysis for a corporate entity.

            Runs BFS propagation from the specified corporate, computes CVaR,
            and generates an intervention plan if CVaR >= $1M threshold.
            """
            alert = cascade_service.analyze(
                corporate_id=request.corporate_id,
                budget_usd=request.budget_usd,
                trigger_type=request.trigger_type,
            )
            if alert is None:
                return CascadeAnalyzeResponse()

            plan = alert.intervention_plan
            return CascadeAnalyzeResponse(
                alert_id=alert.alert_id,
                severity=alert.severity,
                total_value_at_risk_usd=alert.cascade_result.total_value_at_risk_usd,
                cascade_amplification_factor=alert.cascade_result.cascade_amplification_factor,
                nodes_at_risk=alert.cascade_result.nodes_above_threshold,
                intervention_count=len(plan.interventions) if plan else 0,
                total_intervention_cost_usd=plan.total_cost_usd if plan else 0.0,
                total_value_prevented_usd=plan.total_value_prevented_usd if plan else 0.0,
                expires_at=alert.expires_at,
            )

        @router.get("/alerts", response_model=CascadeAlertListResponse, dependencies=deps)
        async def list_alerts(
            severity: Optional[str] = None,
            active_only: bool = True,
        ):
            """List cascade alerts with optional severity filter."""
            now = time.time()
            alerts = cascade_service.list_alerts(
                severity=severity, active_only=active_only
            )
            summaries = [
                CascadeAlertSummary(
                    alert_id=a.alert_id,
                    severity=a.severity,
                    origin_corporate_id=a.origin_corporate_id,
                    origin_sector=a.origin_sector,
                    total_value_at_risk_usd=a.cascade_result.total_value_at_risk_usd,
                    intervention_count=(
                        len(a.intervention_plan.interventions) if a.intervention_plan else 0
                    ),
                    timestamp=a.timestamp,
                    expires_at=a.expires_at,
                    is_expired=a.expires_at < now,
                )
                for a in alerts
            ]
            return CascadeAlertListResponse(alerts=summaries, total=len(summaries))

        @router.get(
            "/alerts/{alert_id}",
            response_model=CascadeAlertDetailResponse,
            dependencies=deps,
        )
        async def get_alert_detail(alert_id: str):
            """Get full detail for a specific cascade alert."""
            alert = cascade_service.get_alert(alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

            plan = alert.intervention_plan
            interventions = []
            if plan:
                for action in plan.interventions:
                    interventions.append(
                        InterventionDetail(
                            priority=action.priority,
                            source_corporate_id=action.source_corporate_id,
                            target_corporate_id=action.target_corporate_id,
                            bridge_amount_usd=action.bridge_amount_usd,
                            cascade_value_prevented_usd=action.cascade_value_prevented_usd,
                            cost_efficiency_ratio=action.cost_efficiency_ratio,
                        )
                    )

            exec_status = cascade_service.get_intervention_status(alert_id)

            return CascadeAlertDetailResponse(
                alert_id=alert.alert_id,
                severity=alert.severity,
                origin_corporate_id=alert.origin_corporate_id,
                origin_sector=alert.origin_sector,
                origin_jurisdiction=alert.origin_jurisdiction,
                total_value_at_risk_usd=alert.cascade_result.total_value_at_risk_usd,
                cascade_amplification_factor=alert.cascade_result.cascade_amplification_factor,
                nodes_at_risk=alert.cascade_result.nodes_above_threshold,
                max_hops_reached=alert.cascade_result.max_hops_reached,
                trigger_type=alert.cascade_result.trigger_type,
                interventions=interventions,
                total_intervention_cost_usd=plan.total_cost_usd if plan else 0.0,
                total_value_prevented_usd=plan.total_value_prevented_usd if plan else 0.0,
                budget_utilization_pct=plan.budget_utilization_pct if plan else 0.0,
                timestamp=alert.timestamp,
                expires_at=alert.expires_at,
                execution_status=exec_status.status if exec_status else None,
            )

        @router.post(
            "/alerts/{alert_id}/execute",
            response_model=ExecuteInterventionResponse,
            dependencies=deps,
        )
        async def execute_intervention(alert_id: str, request: ExecuteInterventionRequest):
            """Execute selected interventions from an alert's plan.

            The action_priorities list specifies which interventions (by priority
            index) to execute. Returns 404 if alert not found, 410 if expired.
            """
            status = cascade_service.execute_intervention(
                alert_id=alert_id, action_priorities=request.action_priorities
            )
            if status is None:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
            if status.status == "EXPIRED":
                raise HTTPException(
                    status_code=410,
                    detail=f"Alert {alert_id} exclusivity window has expired",
                )

            return ExecuteInterventionResponse(
                alert_id=status.alert_id,
                status=status.status,
                executed_actions=status.executed_actions,
                total_bridge_amount_usd=status.total_bridge_amount_usd,
                total_value_prevented_usd=status.total_value_prevented_usd,
            )

        @router.get(
            "/graph/{corporate_id}",
            response_model=CorporateNeighborhoodResponse,
            dependencies=deps,
        )
        async def get_corporate_neighborhood(corporate_id: str):
            """Query a corporate's upstream and downstream dependencies."""
            neighborhood = cascade_service.get_corporate_neighbors(corporate_id)
            if neighborhood is None:
                raise HTTPException(
                    status_code=404, detail=f"Corporate {corporate_id} not found"
                )

            return CorporateNeighborhoodResponse(
                corporate_id=neighborhood.corporate_id,
                sector=neighborhood.sector,
                jurisdiction=neighborhood.jurisdiction,
                cascade_centrality=neighborhood.cascade_centrality,
                upstream=[
                    NeighborEdge(**e) for e in neighborhood.upstream
                ],
                downstream=[
                    NeighborEdge(**e) for e in neighborhood.downstream
                ],
            )

        @router.get("/graph", response_model=GraphSummaryResponse, dependencies=deps)
        async def get_graph_summary():
            """Return high-level graph metadata."""
            summary = cascade_service.get_graph_summary()
            return GraphSummaryResponse(
                node_count=summary.node_count,
                edge_count=summary.edge_count,
                avg_dependency_score=summary.avg_dependency_score,
                max_centrality_node=summary.max_centrality_node,
                build_timestamp=summary.build_timestamp,
            )

        return router

except ImportError:
    logger.debug("FastAPI not installed — cascade router not available")

    def make_cascade_router(*args, **kwargs):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the cascade router")
