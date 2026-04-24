"""
api.py — Internal HTTP wrapper for the C3 repayment engine worker.

Exposes liveness/readiness endpoints while the repayment monitoring loop runs
in a background thread inside the same container.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c8_license_manager.runtime import enforce_component_license
from lip.common.redis_factory import create_redis_client

from .repayment_loop import RepaymentLoop, SettlementMonitor
from .settlement_handlers import SettlementHandlerRegistry

logger = logging.getLogger(__name__)


class C3Service:
    def __init__(
        self,
        repayment_loop: Optional[RepaymentLoop] = None,
        redis_client=None,
    ) -> None:
        self.redis_client = redis_client if redis_client is not None else create_redis_client()
        self.kill_switch = KillSwitch(redis_client=self.redis_client)
        self.license_context = enforce_component_license(
            "C3",
            kill_switch=self.kill_switch,
        )
        self.repayment_loop = repayment_loop or self._build_loop()

    def _build_loop(self) -> RepaymentLoop:
        monitor = SettlementMonitor(
            handler_registry=SettlementHandlerRegistry.create_default(),
            uetr_mapping={},
            corridor_buffer={},
        )
        return RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda record: logger.info(
                "C3 repayment callback: loan_id=%s trigger=%s",
                record.get("loan_id"),
                record.get("trigger"),
            ),
            redis_client=self.redis_client,
        )

    def start(self) -> None:
        self.repayment_loop.run_monitoring_loop(interval_seconds=30)

    def stop(self) -> None:
        self.repayment_loop.stop()

    def redis_ready(self) -> bool:
        if self.redis_client is None:
            return True
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    def is_ready(self) -> bool:
        return self.repayment_loop.is_monitoring() and self.redis_ready()


def create_app(service: Optional[C3Service] = None) -> FastAPI:
    c3_service = service or C3Service()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        c3_service.start()
        yield
        c3_service.stop()

    app = FastAPI(title="LIP C3 Repayment Engine", version="1.0.0", lifespan=lifespan)

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, str]:
        return {"status": "ready" if c3_service.is_ready() else "not_ready"}

    app.state.c3_service = c3_service
    return app


app = create_app()
