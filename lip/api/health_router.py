"""
health_router.py — K8s liveness and readiness probes.
GAP-18: K8s manifests reference /health/live and /health/ready but no
        Python implementation existed.

Endpoints (prefix: /health):
  GET /health/live   — 200 always (liveness probe)
  GET /health/ready  — 200 when Redis reachable + kill switch disengaged +
                        Kafka deliverable; 503 otherwise
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ReadinessChecker(Protocol):
    """Protocol for components that contribute to readiness status."""

    def check_redis(self) -> bool: ...
    def check_kafka(self) -> bool: ...
    def check_kill_switch(self) -> bool: ...


class DefaultReadinessChecker:
    """Concrete readiness checker wired to live dependencies.

    Parameters
    ----------
    redis_client:
        Redis client instance (or None for in-memory mode).
    kill_switch:
        KillSwitch instance from C7.
    kafka_producer:
        Confluent Kafka producer (or None when Kafka unavailable).
    """

    def __init__(
        self,
        redis_client: Any = None,
        kill_switch: Any = None,
        kafka_producer: Any = None,
    ) -> None:
        self._redis = redis_client
        self._kill_switch = kill_switch
        self._kafka_producer = kafka_producer

    def check_redis(self) -> bool:
        if self._redis is None:
            return True  # in-memory mode — always ready
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def check_kafka(self) -> bool:
        if self._kafka_producer is None:
            return True  # no Kafka configured — not a blocker
        try:
            # confluent_kafka Producer.list_topics() returns metadata
            self._kafka_producer.list_topics(timeout=2.0)
            return True
        except Exception:
            return False

    def check_kill_switch(self) -> bool:
        if self._kill_switch is None:
            return True
        return not self._kill_switch.is_active()


try:
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    def make_health_router(readiness_checker: ReadinessChecker) -> APIRouter:
        """Create a FastAPI APIRouter for K8s health probes.

        Usage::

            app = FastAPI()
            app.include_router(make_health_router(checker), prefix="/health")

        Args:
            readiness_checker: Implementation of :class:`ReadinessChecker`.

        Returns:
            :class:`~fastapi.APIRouter` with liveness and readiness endpoints.
        """
        router = APIRouter(tags=["health"])

        @router.get("/live")
        def liveness() -> dict:
            """Liveness probe — always 200."""
            return {"status": "alive"}

        @router.get("/ready")
        def readiness() -> JSONResponse:
            """Readiness probe — 200 when all checks pass, 503 otherwise."""
            checks = {
                "redis": readiness_checker.check_redis(),
                "kafka": readiness_checker.check_kafka(),
                "kill_switch": readiness_checker.check_kill_switch(),
            }
            all_ready = all(checks.values())
            status_code = 200 if all_ready else 503
            return JSONResponse(
                content={"status": "ready" if all_ready else "not_ready", "checks": checks},
                status_code=status_code,
            )

        return router

except ImportError:
    pass  # FastAPI not required for core pipeline operation
