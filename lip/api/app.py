"""
app.py — FastAPI application entrypoint for LIP.
GAP-22: K8s expects HTTP on port 8080. Assembles all routers into a
        running FastAPI application with graceful shutdown.

Usage:
    uvicorn lip.api.app:app --host 0.0.0.0 --port 8080

    Or: ``create_app()`` factory for testing / programmatic use.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from lip.api.admin_router import BPIAdminService, make_admin_router
    from lip.api.auth import make_hmac_dependency
    from lip.api.health_router import DefaultReadinessChecker, make_health_router
    from lip.api.portfolio_router import (
        KnownEntityManager,
        PortfolioReporter,
        make_known_entities_router,
        make_portfolio_router,
    )
    from lip.api.runtime_pipeline import build_runtime_pipeline, real_pipeline_enabled
    from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
    from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
    from lip.c7_execution_agent.kill_switch import KillSwitch
    from lip.c8_license_manager.runtime import enforce_component_license
    from lip.common.borrower_registry import BorrowerRegistry
    from lip.common.known_entity_registry import KnownEntityRegistry
    from lip.common.local_env import load_repo_env_file
    from lip.common.notification_service import NotificationService
    from lip.common.redis_factory import create_redis_client
    from lip.common.regulatory_reporter import RegulatoryReporter
    from lip.common.royalty_settlement import BPIRoyaltySettlement
    from lip.infrastructure.monitoring.metrics import PrometheusMetricsCollector

    # Shared state for shutdown coordination
    _shutdown_hooks: list = []

    # Local dev/test convenience: load gitignored .env.local when present,
    # but never override real environment variables injected by the runtime.
    load_repo_env_file()

    def _decode_runtime_key(raw: str, env_name: str) -> bytes:
        stripped = raw.strip()
        if len(stripped) % 2 == 0 and all(
            ch in "0123456789abcdefABCDEF" for ch in stripped
        ):
            try:
                return bytes.fromhex(stripped)
            except ValueError:
                pass
        try:
            import base64 as _base64

            return _base64.b64decode(stripped, validate=True)
        except Exception as exc:
            raise RuntimeError(
                f"{env_name} is neither valid hex nor valid base64. "
                "Refusing to start with an unparseable key."
            ) from exc

    def create_app(pipeline=None, processor_context=None, cascade_graph=None,
                   systemic_risk_engine=None) -> FastAPI:
        """Factory that assembles the full LIP HTTP application.

        Wires dependencies from environment variables:
        - ``REDIS_URL`` — Redis connection (optional; in-memory fallback)
        - ``LIP_API_HMAC_KEY`` — HMAC signing key for authenticated endpoints
        - ``LIP_KILL_SWITCH_ACTIVE`` — initial kill switch state

        Returns:
            Configured :class:`FastAPI` application.
        """
        redis_client = create_redis_client()

        # Core components
        kill_switch = KillSwitch()
        license_context = enforce_component_license("C7", kill_switch=kill_switch)
        # B2-13: Store in app state so the registry is reachable and not silently GC'd.
        borrower_registry = BorrowerRegistry(redis_client=redis_client)
        known_entity_registry = KnownEntityRegistry(redis_client=redis_client)
        notification_service = NotificationService(redis_client=redis_client)
        regulatory_reporter = RegulatoryReporter(redis_client=redis_client)
        royalty_settlement = BPIRoyaltySettlement(redis_client=redis_client)

        # Settlement / repayment
        handler_registry = SettlementHandlerRegistry.create_default()
        settlement_monitor = SettlementMonitor(
            handler_registry=handler_registry,
            uetr_mapping={},        # populated at runtime when C3 connects
            corridor_buffer={},     # populated at runtime when C3 connects
        )
        from lip.c3_repayment_engine.settlement_bridge import SettlementCallbackBridge

        # Bank mode default: bridge routes to royalty settlement only
        settlement_bridge = SettlementCallbackBridge(
            royalty_settlement=royalty_settlement,
        )
        repayment_loop = RepaymentLoop(
            monitor=settlement_monitor,
            repayment_callback=settlement_bridge,
        )

        # Risk engine (portfolio VaR + concentration)
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        risk_engine = PortfolioRiskEngine()

        # Metrics collector for /metrics Prometheus scraping endpoint
        metrics_collector = PrometheusMetricsCollector()

        # Service layers
        admin_service = BPIAdminService(repayment_loop=repayment_loop)
        portfolio_reporter = PortfolioReporter(
            repayment_loop=repayment_loop,
            royalty_settlement=royalty_settlement,
            risk_engine=risk_engine,
        )
        known_entity_manager = KnownEntityManager(registry=known_entity_registry)

        # Readiness checker
        readiness_checker = DefaultReadinessChecker(
            redis_client=redis_client,
            kill_switch=kill_switch,
        )

        # Auth dependency — fail-closed: if no key is configured, all protected
        # endpoints return 401 rather than allowing unauthenticated access (B2-01).
        hmac_key_hex = os.environ.get("LIP_API_HMAC_KEY", "").strip()
        if hmac_key_hex:
            hmac_key = _decode_runtime_key(hmac_key_hex, "LIP_API_HMAC_KEY")
            logger.debug("LIP_API_HMAC_KEY decoded (%d bytes)", len(hmac_key))
            auth_dep = make_hmac_dependency(hmac_key)
        else:
            # No key configured: install a deny-all dependency so protected
            # routes return 401 instead of being silently open.
            from lip.api.auth import make_deny_all_dependency
            auth_dep = make_deny_all_dependency()
            logger.warning(
                "LIP_API_HMAC_KEY is not set — all authenticated endpoints will "
                "return 401. Set this variable to enable API access."
            )

        # B2-01 / review-A-1: Each downstream router factory accepts
        # auth_dependency=None for test ergonomics (unauthenticated TestClient
        # calls). Production wire-up must never pass None — a missing auth
        # dependency here would silently open every protected route. Fail hard
        # at composition time if that invariant is ever violated.
        assert auth_dep is not None, (
            "auth_dep must be set before mounting routers — refusing to build "
            "a production app with no authentication dependency."
        )

        regulator_signing_key = None
        regulator_key_hex = os.environ.get("LIP_REGULATOR_SUBSCRIPTION_KEY_HEX", "").strip()
        if regulator_key_hex:
            try:
                regulator_signing_key = bytes.fromhex(regulator_key_hex)
            except ValueError as exc:
                # B2-06: Do not fall back to raw UTF-8 bytes — raise at startup so
                # the misconfiguration is surfaced immediately.
                raise RuntimeError(
                    "LIP_REGULATOR_SUBSCRIPTION_KEY_HEX is not valid hex. "
                    "Refusing to start with an unparseable regulator signing key."
                ) from exc

        # Lifespan for startup/shutdown
        @asynccontextmanager
        async def lifespan(application: FastAPI):
            logger.info("LIP API starting up")
            yield
            logger.info("LIP API shutting down — draining resources")
            notification_service.shutdown()
            if redis_client is not None:
                try:
                    redis_client.close()
                except Exception:
                    pass
            for hook in _shutdown_hooks:
                try:
                    hook()
                except Exception as exc:
                    logger.warning("Shutdown hook error: %s", exc)

        application = FastAPI(
            title="LIP — Lending Intelligence Platform",
            version="1.0.0",
            lifespan=lifespan,
        )
        # B2-13: Store shared components in app state so they are reachable
        # from middleware, background tasks, or future endpoints.
        application.state.borrower_registry = borrower_registry
        application.state.known_entity_registry = known_entity_registry
        application.state.license_context = license_context

        runtime_pipeline = pipeline
        runtime_processor_context = processor_context
        if runtime_pipeline is None and real_pipeline_enabled():
            runtime_pipeline, derived_processor_context = build_runtime_pipeline(
                kill_switch=kill_switch,
                settlement_monitor=settlement_monitor,
                borrower_registry=borrower_registry,
                known_entity_registry=known_entity_registry,
                redis_client=redis_client,
                license_context=license_context,
            )
            if runtime_processor_context is None:
                runtime_processor_context = derived_processor_context
            logger.info(
                "Real runtime pipeline enabled (processor_mode=%s)",
                runtime_processor_context is not None,
            )

        application.state.runtime_pipeline = runtime_pipeline
        application.state.processor_context = runtime_processor_context

        # Mount routers
        application.include_router(
            make_health_router(readiness_checker),
            prefix="/health",
        )
        application.include_router(
            make_admin_router(
                admin_service,
                regulatory_reporter=regulatory_reporter,
                auth_dependency=auth_dep,
                risk_engine=risk_engine,
            ),
            prefix="/admin",
        )
        application.include_router(
            make_portfolio_router(portfolio_reporter, auth_dependency=auth_dep),
            prefix="/portfolio",
        )
        application.include_router(
            make_known_entities_router(known_entity_manager, auth_dependency=auth_dep),
            prefix="/known-entities",
        )

        # Prometheus /metrics scraping endpoint — protected by HMAC auth (B2-08).
        # Prometheus scrapers must be configured with a valid Authorization header.
        from fastapi import Depends
        from fastapi.responses import PlainTextResponse

        @application.get(
            "/metrics",
            response_class=PlainTextResponse,
            dependencies=[Depends(auth_dep)],
        )
        def prometheus_metrics():
            """Prometheus-compatible metrics scraping endpoint."""
            return metrics_collector.generate_latest()

        # MIPLO gateway (P3 processor deployments — conditional)
        if runtime_pipeline is not None and runtime_processor_context is not None:
            from decimal import Decimal as _Decimal

            from lip.api.miplo_router import make_miplo_router
            from lip.api.miplo_service import MIPLOService
            from lip.c3_repayment_engine.nav_emitter import NAVEventEmitter
            from lip.c8_license_manager.revenue_metering import RevenueMetering

            # Revenue metering for processor fee splits
            revenue_metering = RevenueMetering()

            # NAV emitter — wired to repayment_loop.get_active_loans after construction
            nav_emitter = NAVEventEmitter(
                get_active_loans=repayment_loop.get_active_loans,
                nav_callback=lambda nav: logger.info("NAV event: tenant=%s loans=%d", nav.tenant_id, nav.active_loans),
                metrics_collector=metrics_collector,
            )

            # Upgrade settlement bridge to processor mode (public method, not private mutation)
            settlement_bridge.upgrade_to_processor_mode(
                revenue_metering=revenue_metering,
                nav_emitter=nav_emitter,
                platform_take_rate_pct=_Decimal(str(runtime_processor_context.platform_take_rate_pct)),
            )

            # Tenant-scoped portfolio reporter for MIPLO
            miplo_portfolio_reporter = PortfolioReporter(
                repayment_loop=repayment_loop,
                royalty_settlement=royalty_settlement,
                licensee_id=runtime_processor_context.licensee_id,
                risk_engine=risk_engine,
            )

            miplo_svc = MIPLOService(
                runtime_pipeline, runtime_processor_context, metrics_collector,
                portfolio_reporter=miplo_portfolio_reporter,
            )
            application.include_router(
                make_miplo_router(miplo_svc, auth_dependency=auth_dep),
                prefix="/miplo",
            )

            # Start NAV emission background thread + register shutdown hook
            nav_emitter.start()
            _shutdown_hooks.append(nav_emitter.stop)

        # Cascade intervention API (P5 — available in bank + processor mode)
        if cascade_graph is not None:
            from lip.api.cascade_router import make_cascade_router
            from lip.api.cascade_service import CascadeService

            cascade_svc = CascadeService(cascade_graph, default_budget_usd=10_000_000.0)
            application.include_router(
                make_cascade_router(cascade_svc, auth_dependency=auth_dep),
                prefix="/cascade",
            )

        # Regulatory API (P10 — available when systemic risk engine provided)
        if systemic_risk_engine is not None:
            from lip.api.rate_limiter import TokenBucketRateLimiter
            from lip.api.regulatory_router import make_regulatory_router
            from lip.api.regulatory_service import RegulatoryService
            from lip.c8_license_manager.query_metering import RegulatoryQueryMetering

            reg_service = RegulatoryService(risk_engine=systemic_risk_engine)
            reg_limiter = TokenBucketRateLimiter(rate=100, period_seconds=3600)
            query_metering = None
            if regulator_signing_key is not None:
                query_metering = RegulatoryQueryMetering(
                    metering_key=regulator_signing_key,
                    single_replica=True,
                )
            application.include_router(
                make_regulatory_router(
                    reg_service,
                    rate_limiter=reg_limiter,
                    auth_dependency=auth_dep,
                    regulator_signing_key=regulator_signing_key,
                    query_metering=query_metering,
                ),
                prefix="/api/v1/regulatory",
            )

        return application

    # Module-level app instance for `uvicorn lip.api.app:app`
    app = create_app()

except ImportError:
    logger.debug("FastAPI not installed — HTTP application not available")
    app = None  # type: ignore[assignment]

    def create_app(pipeline=None, processor_context=None, cascade_graph=None,  # type: ignore[misc]
                   systemic_risk_engine=None):
        raise ImportError("FastAPI is required for the HTTP application")
