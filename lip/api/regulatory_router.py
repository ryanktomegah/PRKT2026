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
import threading
import time
from decimal import Decimal
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
        UsageAnalyticsResponse,
    )
    from lip.api.regulatory_service import RegulatoryService
    from lip.c8_license_manager.query_metering import (
        PrivacyBudgetExceededError,
        QueryBudgetExceededError,
        RegulatoryQueryMetering,
    )
    from lip.c8_license_manager.regulator_subscription import (
        REGULATOR_SUBSCRIPTION_TIERS,
        decode_regulator_token,
        verify_regulator_token,
    )
    from lip.p10_regulatory_data.report_metadata import ReportIntegrityError

    def _make_rate_limit_dep(limiter: TokenBucketRateLimiter):
        """Create a FastAPI dependency for rate limiting.

        Uses the first IP from X-Forwarded-For (proxy-aware) or X-Real-IP
        as the rate-limit key, falling back to the direct peer IP.
        In multi-replica deployments this limiter is per-pod (in-memory);
        see B2-11 comments in rate_limiter.py for Redis upgrade path.
        """

        async def _check_rate(request: Request, response: Response):
            # Proxy-aware: use X-Forwarded-For first IP, then X-Real-IP,
            # then fall back to peer IP.  Prevents N-replica rate collapse
            # where a single proxy IP would be keyed N times.
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                key = forwarded_for.split(",")[0].strip()
            else:
                real_ip = request.headers.get("x-real-ip", "")
                if real_ip:
                    key = real_ip.strip()
                else:
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

    _TIER_RANK: dict[str, int] = {
        tier: idx for idx, tier in enumerate(REGULATOR_SUBSCRIPTION_TIERS, start=1)
    }

    def _required_tier_for_endpoint(path: str) -> str:
        if path.endswith("/stress-test") or path.endswith("/contagion/simulate"):
            return "STRESS_TEST"
        if path.endswith("/reports/generate") or "/corridors/" in path:
            return "QUERY"
        return "STANDARD"

    def _tier_permits(subscription_tier: str, required_tier: str) -> bool:
        return _TIER_RANK.get(subscription_tier, 0) >= _TIER_RANK.get(required_tier, 0)

    def _epsilon_cost_for_endpoint(path: str) -> float:
        if path.endswith("/stress-test"):
            return 0.25
        if path.endswith("/contagion/simulate"):
            return 0.20
        if path.endswith("/reports/generate"):
            return 0.15
        return 0.05

    def _billing_amount_for_endpoint(path: str) -> Decimal:
        if path.endswith("/stress-test"):
            return Decimal("50000")
        if path.endswith("/contagion/simulate"):
            return Decimal("25000")
        if path.endswith("/reports/generate"):
            return Decimal("15000")
        return Decimal("5000")

    def _corridor_is_permitted(corridor: str, permitted_corridors: list[str]) -> bool:
        for allowed in permitted_corridors:
            if allowed.endswith("*"):
                if corridor.startswith(allowed[:-1]):
                    return True
            elif corridor == allowed:
                return True
        return False

    async def _extract_corridors_from_request(request: Request) -> list[str]:
        corridors: list[str] = []
        seen: set[str] = set()

        def _append(value: Optional[str]) -> None:
            if not value:
                return
            v = value.strip()
            if v and v not in seen:
                seen.add(v)
                corridors.append(v)

        _append(request.path_params.get("corridor_id"))
        _append(request.query_params.get("corridor_id"))
        _append(request.query_params.get("shock_corridor"))
        _append(request.query_params.get("corridor"))

        csv_corridors = request.query_params.get("corridors")
        if csv_corridors:
            for value in csv_corridors.split(","):
                _append(value)

        if request.method.upper() == "POST" and request.url.path.endswith("/stress-test"):
            # Read body once and cache it so downstream handlers can re-read
            # via request.body() without re-consuming the stream.
            body = await request.body()  # FastAPI caches; safe to call multiple times
            if body:
                try:
                    payload = json_stdlib.loads(body)
                    shocks = payload.get("shocks", [])
                    for shock in shocks:
                        if isinstance(shock, dict):
                            _append(shock.get("corridor"))
                except (ValueError, json_stdlib.JSONDecodeError) as e:
                    # Body validation is handled by FastAPI endpoint parsing.
                    logger.debug("Could not parse corridors from request body: %s", e)

        return corridors

    # Per-regulator lock map for atomic budget check+consume (B2-03).
    # Prevents TOCTOU race where two concurrent requests both pass the budget
    # pre-check before either has recorded consumption.
    _regulator_locks: dict[str, threading.Lock] = {}
    _regulator_locks_meta = threading.Lock()

    def _get_regulator_lock(regulator_id: str) -> threading.Lock:
        with _regulator_locks_meta:
            if regulator_id not in _regulator_locks:
                _regulator_locks[regulator_id] = threading.Lock()
            return _regulator_locks[regulator_id]

    def _make_regulator_subscription_dep(
        signing_key: bytes,
        query_metering: Optional[RegulatoryQueryMetering],
    ):
        """Create dependency for regulator bearer-token auth + metering."""

        async def _check_regulator(request: Request):
            auth_header = request.headers.get("authorization", "")
            # B2-17: Return 401 immediately if Authorization header is missing
            # or not a Bearer token.  Do not fall through unauthenticated.
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing regulator bearer token",
                )

            encoded = auth_header[len("Bearer "):].strip()
            try:
                token = decode_regulator_token(encoded)
            except ValueError as exc:
                raise HTTPException(status_code=401, detail="Invalid regulator token") from exc

            if not verify_regulator_token(token, signing_key):
                raise HTTPException(status_code=401, detail="Invalid regulator token")

            required_tier = _required_tier_for_endpoint(request.url.path)
            if not _tier_permits(token.subscription_tier, required_tier):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Subscription tier {token.subscription_tier} cannot access "
                        f"this endpoint (requires {required_tier})"
                    ),
                )

            corridors = await _extract_corridors_from_request(request)
            if token.permitted_corridors is not None:
                for corridor in corridors:
                    if not _corridor_is_permitted(corridor, token.permitted_corridors):
                        raise HTTPException(
                            status_code=403,
                            detail=f"Corridor {corridor} not permitted for this token",
                        )

            epsilon_cost = _epsilon_cost_for_endpoint(request.url.path)
            billing_amount = _billing_amount_for_endpoint(request.url.path)

            # B2-03: Acquire per-regulator lock before check+consume to prevent
            # TOCTOU race where concurrent requests both pass the budget gate.
            reg_lock = _get_regulator_lock(token.regulator_id)
            with reg_lock:
                if query_metering is not None:
                    try:
                        query_metering.assert_within_budget(
                            token=token, epsilon_cost=epsilon_cost
                        )
                    except QueryBudgetExceededError as exc:
                        raise HTTPException(
                            status_code=429,
                            detail="Query budget exceeded",
                        ) from exc
                    except PrivacyBudgetExceededError as exc:
                        raise HTTPException(
                            status_code=429,
                            detail="Privacy budget exceeded",
                        ) from exc

            started = time.monotonic()
            try:
                yield
            finally:
                if query_metering is not None:
                    latency_ms = max(int((time.monotonic() - started) * 1000), 0)
                    try:
                        query_metering.record_query(
                            token=token,
                            endpoint=request.url.path,
                            corridors_queried=corridors,
                            epsilon_consumed=epsilon_cost,
                            response_latency_ms=latency_ms,
                            billing_amount_usd=billing_amount,
                        )
                    except (QueryBudgetExceededError, PrivacyBudgetExceededError):
                        # Another concurrent request can consume the remaining budget
                        # between pre-check and finalize write.
                        logger.warning(
                            "Budget exceeded during metering finalize for regulator_id=%s",
                            token.regulator_id,
                        )

        return _check_regulator

    def make_regulatory_router(
        regulatory_service: RegulatoryService,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        auth_dependency: Any = None,
        regulator_signing_key: Optional[bytes] = None,
        query_metering: Optional[RegulatoryQueryMetering] = None,
    ) -> APIRouter:
        """Factory that builds the P10 Regulatory API router.

        Follows make_cascade_router / make_miplo_router pattern.
        Service + rate_limiter captured by closure — no global state.
        """
        router = APIRouter(tags=["regulatory"])

        deps: list = []
        metering: Optional[RegulatoryQueryMetering] = query_metering
        if auth_dependency is not None:
            deps.append(Depends(auth_dependency))
        if rate_limiter is not None:
            deps.append(Depends(_make_rate_limit_dep(rate_limiter)))
        if regulator_signing_key is not None:
            metering = query_metering or RegulatoryQueryMetering(
                metering_key=regulator_signing_key,
                single_replica=True,
            )
            deps.append(
                Depends(
                    _make_regulator_subscription_dep(
                        signing_key=regulator_signing_key,
                        query_metering=metering,
                    )
                )
            )

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
            except ValueError as exc:
                # B2-16: use raise-from to preserve exception chain
                raise HTTPException(status_code=404, detail="Report not found") from exc
            except ReportIntegrityError as exc:
                # B2-16: use raise-from; B2-15: generic message hides internal detail
                logger.error("Report integrity check failed for %s: %s", report_id, exc)
                raise HTTPException(
                    status_code=500,
                    detail="Report integrity check failed",
                ) from exc
            except ImportError as exc:
                # B2-16: use raise-from
                raise HTTPException(
                    status_code=501,
                    detail="PDF generation not available (fpdf2 not installed)",
                ) from exc
            except Exception as exc:
                # B2-15: catch-all to prevent domain/stack-trace leak to client
                logger.error("Unexpected error rendering report %s: %s", report_id, exc)
                raise HTTPException(
                    status_code=500,
                    detail="An internal error occurred while retrieving the report",
                ) from exc

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

        @router.get(
            "/usage/{regulator_id}",
            response_model=UsageAnalyticsResponse,
            dependencies=deps,
        )
        async def get_usage_analytics(
            regulator_id: str,
            request: Request,
        ):
            """Usage analytics and billing summary for a regulator."""
            # Extract and verify caller identity for authorization
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                encoded = auth_header[len("Bearer "):].strip()
                try:
                    caller = decode_regulator_token(encoded)
                except ValueError:
                    raise HTTPException(status_code=401, detail="Invalid token")

                # Authorization: own data or REALTIME tier (admin)
                if (
                    caller.regulator_id != regulator_id
                    and caller.subscription_tier != "REALTIME"
                ):
                    raise HTTPException(
                        status_code=403,
                        detail="Cannot view another regulator's usage",
                    )

            if metering is not None:
                summary = metering.get_billing_summary(regulator_id)
                return UsageAnalyticsResponse(**summary)

            return UsageAnalyticsResponse(
                query_count=0,
                epsilon_consumed=0.0,
                total_billing_usd="0",
                mean_latency_ms=0.0,
                p95_latency_ms=0,
                endpoints_breakdown={},
                corridors_queried=[],
                first_query_at=None,
                last_query_at=None,
            )

        return router

except ImportError:
    logger.debug("FastAPI not installed — regulatory router not available")

    def make_regulatory_router(*args, **kwargs):  # type: ignore[misc]
        """Stub when FastAPI is not installed."""
        raise ImportError("FastAPI is required for the regulatory router")
