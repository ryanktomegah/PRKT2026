"""
flink_jobs.py — Flink job definitions for payment event processing
C5 Spec: Stream processing pipeline
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class FlinkJobType(str, Enum):
    PAYMENT_SCORING = "PAYMENT_SCORING"
    SETTLEMENT_MONITORING = "SETTLEMENT_MONITORING"
    VELOCITY_AGGREGATION = "VELOCITY_AGGREGATION"
    EMBEDDING_REBUILD = "EMBEDDING_REBUILD"


@dataclass
class FlinkJobConfig:
    job_type: FlinkJobType
    parallelism: int = 4
    checkpoint_interval_ms: int = 60_000
    state_backend: str = "rocksdb"
    watermark_strategy: str = "bounded_out_of_orderness"
    max_lateness_seconds: int = 30


class FlinkJobRegistry:
    def __init__(self) -> None:
        self._configs: Dict[FlinkJobType, FlinkJobConfig] = {}
        self._handlers: Dict[FlinkJobType, Callable] = {}

    def register(
        self,
        job_type: FlinkJobType,
        config: FlinkJobConfig,
        handler: Callable,
    ) -> None:
        self._configs[job_type] = config
        self._handlers[job_type] = handler
        logger.info("Registered Flink job: %s", job_type)

    def get_config(self, job_type: FlinkJobType) -> FlinkJobConfig:
        if job_type not in self._configs:
            raise KeyError(f"Flink job not registered: {job_type}")
        return self._configs[job_type]

    def get_handler(self, job_type: FlinkJobType) -> Callable:
        if job_type not in self._handlers:
            raise KeyError(f"Flink job handler not registered: {job_type}")
        return self._handlers[job_type]

    @classmethod
    def create_default_registry(cls) -> "FlinkJobRegistry":
        registry = cls()
        registry.register(
            FlinkJobType.PAYMENT_SCORING,
            FlinkJobConfig(job_type=FlinkJobType.PAYMENT_SCORING, parallelism=8),
            payment_scoring_handler,
        )
        registry.register(
            FlinkJobType.SETTLEMENT_MONITORING,
            FlinkJobConfig(job_type=FlinkJobType.SETTLEMENT_MONITORING, parallelism=4),
            settlement_monitoring_handler,
        )
        registry.register(
            FlinkJobType.VELOCITY_AGGREGATION,
            FlinkJobConfig(job_type=FlinkJobType.VELOCITY_AGGREGATION, parallelism=4),
            velocity_aggregation_handler,
        )
        registry.register(
            FlinkJobType.EMBEDDING_REBUILD,
            FlinkJobConfig(
                job_type=FlinkJobType.EMBEDDING_REBUILD,
                parallelism=2,
                checkpoint_interval_ms=300_000,
            ),
            lambda event: {"status": "embedding_rebuild", "event": event},
        )
        return registry


def payment_scoring_handler(event: dict) -> dict:
    """Route payment event to C1 classifier for failure-probability scoring."""
    logger.debug("payment_scoring_handler: uetr=%s", event.get("uetr"))
    return {
        "uetr": event.get("uetr"),
        "route": "c1_classifier",
        "payload": event,
        "status": "routed",
    }


def settlement_monitoring_handler(event: dict) -> dict:
    """Route settlement signal to C3 repayment engine."""
    logger.debug("settlement_monitoring_handler: uetr=%s", event.get("uetr"))
    return {
        "uetr": event.get("uetr"),
        "route": "c3_repayment_engine",
        "payload": event,
        "status": "routed",
    }


def velocity_aggregation_handler(event: dict) -> dict:
    """Route transaction to C6 AML velocity aggregator."""
    logger.debug("velocity_aggregation_handler: entity=%s", event.get("entity_id"))
    return {
        "entity_id": event.get("entity_id"),
        "route": "c6_aml_velocity",
        "payload": event,
        "status": "routed",
    }
