"""
redis_config.py — Redis cluster configuration, key schemas, TTL strategies
C5 Spec: Corridor embeddings, UETR mappings, velocity counters
"""
from dataclasses import dataclass
from typing import Dict, Optional


KEY_SCHEMAS: Dict[str, str] = {
    "corridor_embedding": "lip:embedding:{currency_pair}",
    "uetr_mapping": "lip:uetr_map:{end_to_end_id}",
    "velocity_counter": "lip:velocity:{entity_id}:{window}",
    "beneficiary_counter": "lip:beneficiary:{entity_id}:{beneficiary_id}:{window}",
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
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None  # set via env var
    ssl: bool = True
    socket_timeout: float = 1.0
    retry_on_timeout: bool = True
    cluster_mode: bool = True

    def to_connection_kwargs(self) -> dict:
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
