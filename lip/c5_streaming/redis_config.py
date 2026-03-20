"""
redis_config.py — Redis cluster configuration, key schemas, TTL strategies
C5 Spec: Corridor embeddings, UETR mappings, velocity counters
"""
from dataclasses import dataclass
from typing import Dict, Optional

KEY_SCHEMAS: Dict[str, str] = {
    "corridor_embedding": "lip:embedding:{currency_pair}",
    "uetr_mapping": "lip:uetr_map:{end_to_end_id}",
    "velocity_counter": "lip:velocity:events:{entity_hash}",
    "beneficiary_counter": "lip:beneficiary:{entity_hash}:{beneficiary_hash}",
    "active_loan": "lip:loan:{loan_id}",
    "salt_current": "lip:salt:current",
    "salt_previous": "lip:salt:previous",
    "kill_switch": "lip:kill_switch",
}

TTL_STRATEGIES: Dict[str, int] = {
    "corridor_embedding": 7 * 24 * 3600,    # 7 days
    "velocity_counter": 24 * 3600,           # 24 hours rolling
    "beneficiary_counter": 24 * 3600,        # 24 hours rolling
    "active_loan": 90 * 24 * 3600,           # 90 days max maturity
    "salt_previous": 30 * 24 * 3600,         # 30-day dual-salt overlap
}


@dataclass
class RedisConfig:
    """Redis cluster connection configuration for LIP.

    All LIP Redis keys are namespaced under the ``lip:`` prefix (see
    :data:`KEY_SCHEMAS`).  SSL is enabled by default; disable only in
    isolated test environments.

    Attributes:
        host: Redis cluster hostname or IP address (default ``'redis'``
            for Kubernetes service discovery).
        port: Redis port (default 6379).
        db: Redis logical database index (default 0).
        password: Optional authentication password.  Should be injected
            via environment variable rather than hardcoded.
        ssl: Enables TLS for the Redis connection (default ``True``).
        socket_timeout: Socket read/write timeout in seconds (default 1.0).
            LIP's ≤ 94ms pipeline SLO requires this to be kept tight.
        retry_on_timeout: Automatically retry timed-out operations once
            (default ``True``).
        cluster_mode: When ``True``, use a cluster-aware client (e.g.,
            ``redis.cluster.RedisCluster``); set ``False`` for single-node
            dev/test deployments.
    """

    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None  # set via env var
    ssl: bool = True
    socket_timeout: float = 1.0
    retry_on_timeout: bool = True
    cluster_mode: bool = True

    def to_connection_kwargs(self) -> dict:
        """Build a keyword-argument dict for ``redis.Redis()`` / ``RedisCluster()``.

        Omits the ``password`` key when no password is configured to avoid
        sending an empty-string auth token to Redis.

        Returns:
            Dict with ``host``, ``port``, ``db``, ``ssl``,
            ``socket_timeout``, ``retry_on_timeout``, and optionally
            ``password`` keys.
        """
        kwargs: dict = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ssl": self.ssl,
            "socket_timeout": self.socket_timeout,
            "retry_on_timeout": self.retry_on_timeout,
        }
        if self.password:
            kwargs["password"] = self.password
        return kwargs
