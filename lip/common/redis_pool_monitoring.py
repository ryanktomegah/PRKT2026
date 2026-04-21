"""
redis_pool_monitoring.py — Redis connection pool exhaustion monitoring (ESG-08: System: Redis memory exhaustion).

Monitors Redis connection pool metrics and provides alerts when pool is
approaching exhaustion levels. Prevents UETR eviction during memory pressure.
"""
import logging
import time

logger = logging.getLogger(__name__)

# ESG-08: Monitoring thresholds
_POOL_UTILIZATION_WARNING = 0.8    # 80% pool utilization triggers warning
_POOL_UTILIZATION_CRITICAL = 0.95   # 95% pool utilization triggers critical alert
_CONN_WAIT_WARNING_MS = 100         # Connection wait time > 100ms triggers warning
_CONN_WAIT_CRITICAL_MS = 500       # Connection wait time > 500ms triggers critical


class RedisPoolMonitor:
    """Monitors Redis connection pool for exhaustion prevention (ESG-08)."""

    def __init__(self, redis_client=None):
        """
        Args:
            redis_client: Optional redis.Redis instance for monitoring.
        """
        self._redis = redis_client
        self._last_metrics = {}
        self._monitoring = False

    def start_monitoring(self):
        """Start background pool monitoring."""
        self._monitoring = True
        logger.info("Redis pool monitoring started")

    def stop_monitoring(self):
        """Stop background pool monitoring."""
        self._monitoring = False
        logger.info("Redis pool monitoring stopped")

    def get_pool_utilization(self) -> float:
        """Get current Redis connection pool utilization.

        Returns:
            float between 0.0 and 1.0 indicating pool utilization.
        """
        if self._redis is None:
            return 0.0

        try:
            # connection pool size (approximate number of connections)
            pool = getattr(self._redis, 'connection_pool', None)
            if pool and hasattr(pool, 'created_connections'):
                created = len(pool.created_connections)
                # connections available (in pool, not checked out)
                if hasattr(pool, '_in_use_connections'):
                    in_use = len(pool._in_use_connections)
                available = max(0, created - in_use)
                if created > 0:
                    return min(1.0, created / available) if available > 0 else 0.0

        except Exception as exc:
            logger.warning("Failed to get pool utilization: %s", exc)
            return 0.0

    def check_connection_waits(self) -> dict:
        """Check if Redis connection waits are excessive.

        Returns:
            Dict with wait metrics and status indicators.
        """
        if self._redis is None:
            return {"status": "no_redis", "wait_ms_avg": 0}

        try:
            pool = getattr(self._redis, 'connection_pool', None)
            if pool is None:
                return {"status": "no_pool", "wait_ms_avg": 0}

            # Get connection wait times
            wait_ms = getattr(pool, 'connection_pool', {}).get('wait_average_ms', 0)
            wait_max = getattr(pool, 'connection_pool', {}).get('wait_max_ms', 0)

            status = "ok"
            if wait_ms > _CONN_WAIT_CRITICAL_MS:
                status = "critical"
            elif wait_ms > _CONN_WAIT_WARNING_MS:
                status = "warning"
            elif wait_ms > 100:  # normal threshold
                status = "warning"
            else:
                status = "ok"

            return {
                "status": status,
                "wait_ms_avg": wait_ms,
                "wait_ms_max": wait_max,
                "utilization": self.get_pool_utilization(),
            }

        except Exception as exc:
            logger.warning("Failed to check connection waits: %s", exc)
            return {"status": "error", "error": str(exc)}

    def log_metrics(self) -> None:
        """Log current pool metrics for monitoring."""
        if self._redis is None:
            return

        metrics = self.check_connection_waits()
        if metrics.get("status") != "error":
            self._last_metrics = {
                "pool_utilization": metrics["utilization"],
                "connection_waits_ms_avg": metrics["wait_ms_avg"],
                "timestamp": time.time(),
            }

            logger.info(
                "Redis pool metrics: utilization=%.1f%% wait_ms=%.0fms status=%s",
                metrics["pool_utilization"] * 100,
                metrics["wait_ms_avg"],
                metrics["status"],
            )

            # ESG-08: Check for pool exhaustion risk
            util = metrics["pool_utilization"]
            if util >= _POOL_UTILIZATION_CRITICAL:
                logger.critical(
                    "Redis pool exhaustion risk: utilization=%.1f%% CRITICAL",
                    util,
                )
            elif util >= _POOL_UTILIZATION_WARNING:
                logger.warning(
                    "Redis pool exhaustion warning: utilization=%.1f%% WARNING",
                    util,
                )
