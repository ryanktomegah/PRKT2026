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
    from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
    from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
    from lip.c7_execution_agent.kill_switch import KillSwitch
    from lip.common.borrower_registry import BorrowerRegistry
    from lip.common.known_entity_registry import KnownEntityRegistry
    from lip.common.notification_service import NotificationService
    from lip.common.redis_factory import create_redis_client
    from lip.common.regulatory_reporter import RegulatoryReporter
    from lip.common.royalty_settlement import BPIRoyaltySettlement
    from lip.infrastructure.monitoring.metrics import PrometheusMetricsCollector

    # Shared state for shutdown coordination
    _shutdown_hooks: list = []

    def create_app(pipeline=None, processor_context=None) -> FastAPI:
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
        BorrowerRegistry(redis_client=redis_client)  # init loads from Redis; shared via C7 config
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

        # Auth dependency (optional — no key = no auth enforcement)
        hmac_key_hex = os.environ.get("LIP_API_HMAC_KEY", "")
        auth_dep = None
        if hmac_key_hex:
            hmac_key = hmac_key_hex.encode() if len(hmac_key_hex) < 64 else bytes.fromhex(hmac_key_hex)
            auth_dep = make_hmac_dependency(hmac_key)

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

        # Prometheus /metrics scraping endpoint — no auth required
        from fastapi.responses import PlainTextResponse

        @application.get("/metrics", response_class=PlainTextResponse)
        def prometheus_metrics():
            """Prometheus-compatible metrics scraping endpoint."""
            return metrics_collector.generate_latest()

        # MIPLO gateway (P3 processor deployments — conditional)
        if pipeline is not None and processor_context is not None:
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
                platform_take_rate_pct=_Decimal(str(processor_context.platform_take_rate_pct)),
            )

            # Tenant-scoped portfolio reporter for MIPLO
            miplo_portfolio_reporter = PortfolioReporter(
                repayment_loop=repayment_loop,
                royalty_settlement=royalty_settlement,
                licensee_id=processor_context.licensee_id,
                risk_engine=risk_engine,
            )

            miplo_svc = MIPLOService(
                pipeline, processor_context, metrics_collector,
                portfolio_reporter=miplo_portfolio_reporter,
            )
            application.include_router(
                make_miplo_router(miplo_svc, auth_dependency=auth_dep),
                prefix="/miplo",
            )

            # Start NAV emission background thread + register shutdown hook
            nav_emitter.start()
            _shutdown_hooks.append(nav_emitter.stop)

        return application

    # Module-level app instance for `uvicorn lip.api.app:app`
    app = create_app()

except ImportError:
    logger.debug("FastAPI not installed — HTTP application not available")
    app = None  # type: ignore[assignment]

    def create_app(pipeline=None, processor_context=None):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the HTTP application")
