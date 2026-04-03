"""
regulatory_models.py — Pydantic request/response models for P10 Regulatory API.

Separated from the router to keep endpoint wiring focused.
Sprint 4c: 7 endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field

    # ── Request Models ──────────────────────────────────────────────

    class CorridorListParams(BaseModel):
        """Query params for GET /corridors."""

        period_count: int = Field(default=24, ge=1, le=720)
        min_bank_count: int = Field(default=5, ge=1)

    class CorridorTrendParams(BaseModel):
        """Query params for GET /corridors/{corridor_id}/trend."""

        periods: int = Field(default=24, ge=1, le=720)

    class ConcentrationParams(BaseModel):
        """Query params for GET /concentration."""

        dimension: str = Field(
            default="corridor", pattern="^(corridor|jurisdiction)$"
        )

    class ContagionSimulationParams(BaseModel):
        """Query params for GET /contagion/simulate."""

        shock_corridor: str = Field(..., min_length=3)
        shock_magnitude: float = Field(default=1.0, ge=0.0, le=1.0)
        max_hops: int = Field(default=5, ge=1, le=10)

    class StressTestShock(BaseModel):
        """One shock in a stress test scenario."""

        corridor: str = Field(..., min_length=3)
        magnitude: float = Field(..., ge=0.0, le=1.0)

    class StressTestRequest(BaseModel):
        """Request body for POST /stress-test."""

        scenario_name: str = Field(..., min_length=1, max_length=200)
        shocks: List[StressTestShock] = Field(..., min_length=1, max_length=20)

    class GenerateReportRequest(BaseModel):
        """Request body for POST /reports/generate."""

        period_start: str = ""
        period_end: str = ""

    # ── Response Models ─────────────────────────────────────────────

    class CorridorSnapshotResponse(BaseModel):
        """One corridor in the corridor list or trend."""

        corridor: str
        period_label: str
        failure_rate: float
        total_payments: int
        failed_payments: int
        bank_count: int
        trend_direction: str
        trend_magnitude: float
        contains_stale_data: bool

    class CorridorListResponse(BaseModel):
        """Response for GET /corridors."""

        corridors: List[CorridorSnapshotResponse]
        total_corridors: int
        suppressed_count: int
        timestamp: float

    class CorridorTrendResponse(BaseModel):
        """Response for GET /corridors/{corridor_id}/trend."""

        corridor_id: str
        snapshots: List[CorridorSnapshotResponse]
        total_periods: int

    class ConcentrationResponse(BaseModel):
        """Response for GET /concentration."""

        dimension: str
        hhi: float
        effective_count: float
        is_concentrated: bool
        top_entities: List[List[Any]]

    class ContagionNodeResponse(BaseModel):
        """One affected corridor in contagion results."""

        corridor: str
        stress_level: float
        hop_distance: int
        propagation_path: List[str]

    class ContagionSimulationResponse(BaseModel):
        """Response for GET /contagion/simulate."""

        origin_corridor: str
        shock_magnitude: float
        affected_corridors: List[ContagionNodeResponse]
        max_propagation_depth: int
        total_volume_at_risk_usd: float
        systemic_risk_score: float

    class StressTestResponse(BaseModel):
        """Response for POST /stress-test."""

        scenario_name: str
        report_id: str
        overall_failure_rate: float
        highest_risk_corridor: str
        concentration_hhi: float
        systemic_risk_score: float
        total_corridors_analyzed: int
        stale_corridor_count: int
        timestamp: float

    class ReportResponse(BaseModel):
        """Response for GET /reports/{report_id}."""

        report_id: str
        timestamp: float
        corridor_snapshots: List[CorridorSnapshotResponse]
        overall_failure_rate: float
        highest_risk_corridor: str
        concentration_hhi: float
        systemic_risk_score: float
        stale_corridor_count: int
        total_corridors_analyzed: int

    class MetadataResponse(BaseModel):
        """Response for GET /metadata."""

        api_version: str
        data_freshness: Dict[str, Any]
        methodology: Dict[str, Any]
        rate_limit: Dict[str, Any]

    class UsageAnalyticsResponse(BaseModel):
        """Response for GET /usage/{regulator_id}."""

        query_count: int
        epsilon_consumed: float
        total_billing_usd: str
        mean_latency_ms: float
        p95_latency_ms: int
        endpoints_breakdown: Dict[str, int]
        corridors_queried: List[str]
        first_query_at: Any  # str | None
        last_query_at: Any  # str | None

except ImportError:
    logger.debug("Pydantic not installed — regulatory models not available")
