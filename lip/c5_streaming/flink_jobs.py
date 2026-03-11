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
    """Enumeration of Flink streaming jobs deployed in the LIP pipeline.

    Attributes:
        PAYMENT_SCORING: Routes inbound payment events from
            ``lip.payment.events`` to the C1 failure classifier.
            Parallelism 8 (highest throughput requirement).
        SETTLEMENT_MONITORING: Routes settlement signals from
            ``lip.settlement.signals`` to the C3 repayment engine.
            Parallelism 4.
        VELOCITY_AGGREGATION: Aggregates transaction volumes and counts
            per entity for C6 AML velocity checks.  Parallelism 4.
        EMBEDDING_REBUILD: Periodically rebuilds corridor embeddings in
            Redis.  Lower parallelism (2) and 5-minute checkpoint interval
            due to infrequent invocation.
    """

    PAYMENT_SCORING = "PAYMENT_SCORING"
    SETTLEMENT_MONITORING = "SETTLEMENT_MONITORING"
    VELOCITY_AGGREGATION = "VELOCITY_AGGREGATION"
    EMBEDDING_REBUILD = "EMBEDDING_REBUILD"


@dataclass
class FlinkJobConfig:
    """Flink job execution parameters.

    Attributes:
        job_type: :class:`FlinkJobType` this config applies to.
        parallelism: Number of parallel task slots (default 4).
        checkpoint_interval_ms: Milliseconds between Flink checkpoints
            for state recovery (default 60 000 = 1 minute).
        state_backend: Flink state backend name (default ``'rocksdb'``
            for large-state jobs).
        watermark_strategy: Flink watermark strategy name; ``'bounded_out_of_orderness'``
            handles late payment events up to ``max_lateness_seconds``.
        max_lateness_seconds: Maximum tolerated event lateness in seconds
            before the watermark advances past the event and it is dropped
            (default 30).
    """

    job_type: FlinkJobType
    parallelism: int = 4
    checkpoint_interval_ms: int = 60_000
    state_backend: str = "rocksdb"
    watermark_strategy: str = "bounded_out_of_orderness"
    max_lateness_seconds: int = 30


class FlinkJobRegistry:
    """Registry mapping :class:`FlinkJobType` values to configs and handlers.

    Provides a centralised lookup for all Flink jobs in the LIP pipeline.
    Jobs must be registered (via :meth:`register`) before they can be
    dispatched.  Use :meth:`create_default_registry` to obtain a
    pre-configured instance with all production job registrations.
    """

    def __init__(self) -> None:
        self._configs: Dict[FlinkJobType, FlinkJobConfig] = {}
        self._handlers: Dict[FlinkJobType, Callable] = {}

    def register(
        self,
        job_type: FlinkJobType,
        config: FlinkJobConfig,
        handler: Callable,
    ) -> None:
        """Register a job type with its config and event-processing handler.

        Args:
            job_type: The :class:`FlinkJobType` to register.
            config: :class:`FlinkJobConfig` with parallelism and checkpoint
                settings for this job.
            handler: Callable ``(event: dict) -> dict`` that processes a
                single Kafka event and returns a routing/status dict.
        """
        self._configs[job_type] = config
        self._handlers[job_type] = handler
        logger.info("Registered Flink job: %s", job_type)

    def get_config(self, job_type: FlinkJobType) -> FlinkJobConfig:
        """Retrieve the :class:`FlinkJobConfig` for a registered job type.

        Args:
            job_type: The :class:`FlinkJobType` to look up.

        Returns:
            The associated :class:`FlinkJobConfig`.

        Raises:
            KeyError: If ``job_type`` has not been registered.
        """
        if job_type not in self._configs:
            raise KeyError(f"Flink job not registered: {job_type}")
        return self._configs[job_type]

    def get_handler(self, job_type: FlinkJobType) -> Callable:
        """Retrieve the event-processing handler for a registered job type.

        Args:
            job_type: The :class:`FlinkJobType` to look up.

        Returns:
            The registered ``(event: dict) -> dict`` callable.

        Raises:
            KeyError: If ``job_type`` has not been registered.
        """
        if job_type not in self._handlers:
            raise KeyError(f"Flink job handler not registered: {job_type}")
        return self._handlers[job_type]

    @classmethod
    def create_default_registry(cls) -> "FlinkJobRegistry":
        """Build and return a registry pre-loaded with all production jobs.

        Returns:
            :class:`FlinkJobRegistry` instance with all four
            :class:`FlinkJobType` entries registered.
        """
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
