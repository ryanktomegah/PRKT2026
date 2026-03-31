"""
regulatory_router.py — P10 Regulatory API HTTP endpoints.

Sprint 4c: 7 REST endpoints over Sprint 4b systemic risk engine.
Sprint 5 Task 6: Content negotiation for GET /reports/{id} (JSON/CSV/PDF)
  and new POST /reports/generate endpoint.
Factory pattern matching make_cascade_router / make_miplo_router.

Endpoints:
  GET  /corridors                     — Corridor failure rate snapshots
  GET  /corridors/{corridor_id}/trend — Time-series for one corridor
  GET  /concentration                 — HHI concentration metrics
  GET  /contagion/simulate            — BFS stress propagation
  POST /stress-test                   — Multi-shock stress scenario
  GET  /reports/{report_id}           — Retrieve report (JSON/CSV/PDF)
  POST /reports/generate              — Generate new versioned report
  GET  /metadata                      — API + data metadata
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import json as json_stdlib

    from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

    from lip.api.rate_limiter import TokenBucketRateLimiter
    from lip.api.regulatory_models import (
        ConcentrationResponse,
        ContagionNodeResponse,
        ContagionSimulationResponse,
        CorridorListResponse,
        CorridorSnapshotResponse,
        CorridorTrendResponse,
        GenerateReportRequest,
        MetadataResponse,
        StressTestRequest,
        StressTestResponse,
    )
    from lip.api.regulatory_service import RegulatoryService
    from lip.p10_regulatory_data.report_metadata import ReportIntegrityError

    def _make_rate_limit_dep(limiter: TokenBucketRateLimiter):
        """Create a FastAPI dependency for rate limiting.

        Uses client IP as the rate-limit key (placeholder for Sprint 6
        RegulatorSubscriptionToken-based keying).
        """

        async def _check_rate(request: Request, response: Response):
            key = request.client.host if request.client else "unknown"
            allowed, remaining = limiter.check_and_consume_with_remaining(key)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "3600"},
                )

        return _check_rate

    def make_regulatory_router(
        regulatory_service: RegulatoryService,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        auth_dependency: Any = None,
    ) -> APIRouter:
        """Factory that builds the P10 Regulatory API router.

        Follows make_cascade_router / make_miplo_router pattern.
        Service + rate_limiter captured by closure — no global state.
        """
        router = APIRouter(tags=["regulatory"])

        deps: list = []
        if auth_dependency is not None:
            deps.append(Depends(auth_dependency))
        if rate_limiter is not None:
            deps.append(Depends(_make_rate_limit_dep(rate_limiter)))

        @router.get(
            "/corridors",
            response_model=CorridorListResponse,
            dependencies=deps,
        )
        async def list_corridors(
            period_count: int = Query(default=24, ge=1, le=720),
            min_bank_count: int = Query(default=5, ge=1),
        ):
            """Corridor failure rate snapshots with k-anonymity filtering."""
            snapshots, suppressed = regulatory_service.get_corridor_snapshots(
                period_count=period_count,
                min_bank_count=min_bank_count,
            )
            return CorridorListResponse(
                corridors=[
                    CorridorSnapshotResponse(
                        corridor=s.corridor,
                        period_label=s.period_label,
                        failure_rate=s.failure_rate,
                        total_payments=s.total_payments,
                        failed_payments=s.failed_payments,
                        bank_count=s.bank_count,
                        trend_direction=s.trend_direction,
                        trend_magnitude=s.trend_magnitude,
                        contains_stale_data=s.contains_stale_data,
                    )
                    for s in snapshots
                ],
                total_corridors=len(snapshots),
                suppressed_count=suppressed,
                timestamp=time.time(),
            )

        @router.get(
            "/corridors/{corridor_id}/trend",
            response_model=CorridorTrendResponse,
            dependencies=deps,
        )
        async def get_corridor_trend(
            corridor_id: str,
            periods: int = Query(default=24, ge=1, le=720),
        ):
            """Time-series failure rate data for one corridor."""
            snapshots = regulatory_service.get_corridor_trend(corridor_id, periods)
            return CorridorTrendResponse(
                corridor_id=corridor_id,
                snapshots=[
                    CorridorSnapshotResponse(
                        corridor=s.corridor,
                        period_label=s.period_label,
                        failure_rate=s.failure_rate,
                        total_payments=s.total_payments,
                        failed_payments=s.failed_payments,
                        bank_count=s.bank_count,
                        trend_direction=s.trend_direction,
                        trend_magnitude=s.trend_magnitude,
                        contains_stale_data=s.contains_stale_data,
                    )
                    for s in snapshots
                ],
                total_periods=len(snapshots),
            )

        @router.get(
            "/concentration",
            response_model=ConcentrationResponse,
            dependencies=deps,
        )
        async def get_concentration(
            dimension: str = Query(
                default="corridor", pattern="^(corridor|jurisdiction)$"
            ),
        ):
            """HHI concentration metrics."""
            result = regulatory_service.get_concentration(dimension)
            return ConcentrationResponse(
                dimension=result.dimension,
                hhi=result.hhi,
                effective_count=result.effective_count,
                is_concentrated=result.is_concentrated,
                top_entities=[list(e) for e in result.top_entities],
            )

        @router.get(
            "/contagion/simulate",
            response_model=ContagionSimulationResponse,
            dependencies=deps,
        )
        async def simulate_contagion(
            shock_corridor: str = Query(..., min_length=3),
            shock_magnitude: float = Query(default=1.0, ge=0.0, le=1.0),
            max_hops: int = Query(default=5, ge=1, le=10),
        ):
            """BFS contagion stress propagation simulation."""
            result = regulatory_service.simulate_contagion(
                shock_corridor=shock_corridor,
                shock_magnitude=shock_magnitude,
                max_hops=max_hops,
            )
            return ContagionSimulationResponse(
                origin_corridor=result.origin_corridor,
                shock_magnitude=result.shock_magnitude,
                affected_corridors=[
                    ContagionNodeResponse(
                        corridor=n.corridor,
                        stress_level=n.stress_level,
                        hop_distance=n.hop_distance,
                        propagation_path=list(n.propagation_path),
                    )
                    for n in result.affected_corridors
                ],
                max_propagation_depth=result.max_propagation_depth,
                total_volume_at_risk_usd=result.total_volume_at_risk_usd,
                systemic_risk_score=result.systemic_risk_score,
            )

        @router.post(
            "/stress-test",
            response_model=StressTestResponse,
            dependencies=deps,
        )
        async def run_stress_test(request: StressTestRequest):
            """Multi-shock stress test scenario."""
            shocks = [(s.corridor, s.magnitude) for s in request.shocks]
            report_id, vr = regulatory_service.run_stress_test(
                scenario_name=request.scenario_name,
                shocks=shocks,
            )
            return StressTestResponse(
                scenario_name=request.scenario_name,
                report_id=report_id,
                overall_failure_rate=vr.report.overall_failure_rate,
                highest_risk_corridor=vr.report.highest_risk_corridor,
                concentration_hhi=vr.report.concentration_hhi,
                systemic_risk_score=vr.report.systemic_risk_score,
                total_corridors_analyzed=vr.report.total_corridors_analyzed,
                stale_corridor_count=vr.report.stale_corridor_count,
                timestamp=vr.report.timestamp,
            )

        @router.get(
            "/reports/{report_id}",
            dependencies=deps,
        )
        async def get_report(
            report_id: str,
            format: str = Query(default="json", pattern="^(json|csv|pdf)$"),
        ):
            """Retrieve a report in JSON, CSV, or PDF format."""
            try:
                content, content_type = regulatory_service.render_report(
                    report_id, fmt=format
                )
            except ValueError:
                raise HTTPException(status_code=404, detail="Report not found")
            except ReportIntegrityError:
                raise HTTPException(
                    status_code=500,
                    detail="Report integrity check failed",
                )
            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="PDF generation not available (fpdf2 not installed)",
                )

            if format == "json":
                return json_stdlib.loads(content)
            elif format == "csv":
                return Response(
                    content=content,
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f'attachment; filename="{report_id}.csv"'
                    },
                )
            else:  # pdf
                return Response(
                    content=content,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{report_id}.pdf"'
                    },
                )

        @router.post(
            "/reports/generate",
            dependencies=deps,
        )
        async def generate_report(request: GenerateReportRequest):
            """Generate a new versioned report from current engine state."""
            vr = regulatory_service.generate_report(
                period_start=request.period_start,
                period_end=request.period_end,
            )
            return {
                "report_id": vr.report_id,
                "version": vr.version,
                "generated_at": vr.generated_at,
                "content_hash": vr.content_hash,
                "methodology_version": vr.methodology_version,
            }

        @router.get(
            "/metadata",
            response_model=MetadataResponse,
            dependencies=deps,
        )
        async def get_metadata():
            """API and data metadata."""
            meta = regulatory_service.get_metadata()
            return MetadataResponse(**meta)

        return router

except ImportError:
    logger.debug("FastAPI not installed — regulatory router not available")

    def make_regulatory_router(*args, **kwargs):  # type: ignore[misc]
        """Stub when FastAPI is not installed."""
        raise ImportError("FastAPI is required for the regulatory router")
