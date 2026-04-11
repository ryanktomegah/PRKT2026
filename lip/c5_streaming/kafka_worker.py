"""
kafka_worker.py — Python Kafka consumer/producer worker for C5 streaming.

Reads from the payment_events topic, normalises events via EventNormalizer,
calls the injected pipeline function, and writes results to the
failure_predictions topic.

This is the Python-native alternative to PyFlink job submission.
In production deployments at 50K TPS, Flink TaskManagers run this logic at
scale (managed via c5-deployment.yaml). For single-region / lower-volume
deployments, this standalone worker provides the same pipeline integration
without Flink cluster overhead.

Usage:
  PYTHONPATH=. python -m lip.c5_streaming.kafka_worker \\
      --group-id lip-c5-worker-1 \\
      [--dry-run]

Environment (via KafkaConfig):
  KAFKA_BOOTSTRAP_SERVERS  — comma-separated broker list (default: kafka:9092)
  KAFKA_SSL_CA_LOCATION    — path to CA cert file (optional)
  KAFKA_SSL_CERT_LOCATION  — path to client cert file (optional)
  KAFKA_SSL_KEY_LOCATION   — path to client key file (optional)
"""
import argparse
import json
import logging
import os
import signal
import time
from typing import Any, Callable, Optional

from lip.c5_streaming.event_normalizer import EventNormalizer, NormalizedEvent
from lip.c5_streaming.kafka_config import KafkaConfig, KafkaTopic

logger = logging.getLogger(__name__)

# DLQ retry configuration (GAP-20)
_DLQ_MAX_RETRIES = 3
_DLQ_BACKOFF_BASE_MS = 100  # exponential: 100ms, 200ms, 400ms


# ---------------------------------------------------------------------------
# PaymentEventWorker
# ---------------------------------------------------------------------------

class PaymentEventWorker:
    """
    Kafka consumer/producer for the payment_events → failure_predictions lane.

    Args:
        kafka_config:  KafkaConfig with broker / SSL settings.
        pipeline_fn:   Callable[[NormalizedEvent], dict] — typically
                       ``LIPPipeline.process(event)``. Must be thread-safe
                       if multiple workers run in the same process.
        group_id:      Kafka consumer group ID. Multiple workers with the
                       same group_id share the partition load.
        dry_run:       When True, events are consumed and pipeline_fn is called
                       but no messages are produced to Kafka. Useful for
                       integration testing without a write-capable broker.
    """

    def __init__(
        self,
        kafka_config: KafkaConfig,
        pipeline_fn: Callable[[NormalizedEvent], dict],
        group_id: str = "lip-c5-worker",
        dry_run: bool = False,
        metrics_collector: Any = None,
    ) -> None:
        self._config = kafka_config
        self._pipeline_fn = pipeline_fn
        self._group_id = group_id
        self._dry_run = dry_run
        self._running = False
        self._normalizer = EventNormalizer()
        self._consumer: Any = None
        self._producer: Any = None
        self._processed = 0
        self._errors = 0
        self._produce_errors = 0
        self._metrics = metrics_collector

    # ── Kafka client builders ────────────────────────────────────────────────

    def _build_consumer(self) -> Any:
        from confluent_kafka import Consumer  # type: ignore[import]

        cfg = self._config.to_consumer_config(self._group_id)
        logger.info(
            "Creating Kafka consumer: group=%s brokers=%s",
            self._group_id,
            self._config.bootstrap_servers,
        )
        return Consumer(cfg)

    def _build_producer(self) -> Any:
        from confluent_kafka import Producer  # type: ignore[import]

        cfg = self._config.to_producer_config()
        logger.info(
            "Creating Kafka producer: brokers=%s",
            self._config.bootstrap_servers,
        )
        return Producer(cfg)

    # ── Signal handling ──────────────────────────────────────────────────────

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Signal %s received — initiating graceful shutdown", signum)
        self._running = False

    # ── Main consumer loop ───────────────────────────────────────────────────

    def run(self, topic_override: Optional[str] = None) -> None:
        """
        Start the consumer loop. Blocks until SIGTERM or SIGINT.

        Args:
            topic_override: Subscribe to this topic name instead of the
                            canonical ``lip.payment.events``.
        """
        self._consumer = self._build_consumer()
        self._producer = self._build_producer() if not self._dry_run else None

        topic = topic_override or KafkaTopic.PAYMENT_EVENTS.value
        self._consumer.subscribe([topic])
        self._running = True

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info(
            "C5 PaymentEventWorker started — topic=%s group=%s dry_run=%s",
            topic,
            self._group_id,
            self._dry_run,
        )

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Kafka consumer error: %s", msg.error())
                    continue
                self._process_message(msg)
        finally:
            logger.info(
                "C5 worker shutting down — processed=%d errors=%d",
                self._processed,
                self._errors,
            )
            self._consumer.close()
            if self._producer:
                self._producer.flush(timeout=10)

    # ── Message processing ───────────────────────────────────────────────────

    def _process_message(self, msg: Any) -> None:
        """
        Decode → normalise → pipeline → produce.

        Errors are caught and counted but do not stop the consumer loop.
        The problematic message is NOT committed so it will be reprocessed
        on restart (exactly-once semantics relies on idempotent producer +
        transactional offsets; see kafka_config.py).
        """
        try:
            raw_bytes = msg.value()
            if raw_bytes is None:
                logger.warning("Received null-value message — skipping offset=%s", msg.offset())
                return

            raw: dict = json.loads(raw_bytes.decode("utf-8"))
            rail: str = raw.get("rail", "SWIFT").upper()

            event: NormalizedEvent = self._normalizer.normalize(rail, raw)
            result: dict = self._pipeline_fn(event)

            if not self._dry_run and self._producer is not None:
                out_topic = KafkaTopic.FAILURE_PREDICTIONS.value
                key_bytes = event.uetr.encode("utf-8")
                value_bytes = json.dumps(result, default=str).encode("utf-8")
                self._produce_with_retry(out_topic, key_bytes, value_bytes)

            self._processed += 1

        except json.JSONDecodeError as exc:
            logger.error(
                "JSON decode error at offset=%s: %s — routing to dead letter",
                msg.offset(),
                exc,
            )
            self._route_dead_letter(msg)
            self._errors += 1
        except (SystemExit, KeyboardInterrupt):
            # B6-10: never swallow process termination signals in a catch-all.
            raise
        except Exception:  # Intentional catch-all: any unhandled error must be
            # routed to DLQ rather than crashing the consumer loop. Narrowing
            # this catch further risks killing the consumer on unexpected errors
            # in production (e.g. third-party library exceptions). The noqa is
            # replaced by this comment explaining the deliberate design choice.
            logger.exception(
                "Unexpected error processing offset=%s — routing to dead letter",
                msg.offset(),
            )
            self._route_dead_letter(msg)
            self._errors += 1

    def _produce_with_retry(
        self,
        topic: str,
        key: bytes,
        value: bytes,
    ) -> None:
        """Produce a message with exponential backoff retry (GAP-20).

        On failure after all retries, routes to dead-letter topic and
        increments the kafka producer error metric.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(_DLQ_MAX_RETRIES):
            try:
                self._producer.produce(
                    topic,
                    key=key,
                    value=value,
                )
                self._producer.poll(0)
                return
            except Exception as exc:
                last_exc = exc
                backoff_ms = _DLQ_BACKOFF_BASE_MS * (2 ** attempt)
                logger.warning(
                    "Kafka produce failed (attempt %d/%d, backoff %dms): %s",
                    attempt + 1, _DLQ_MAX_RETRIES, backoff_ms, exc,
                )
                time.sleep(backoff_ms / 1000.0)

        # All retries exhausted — route to DLQ
        self._produce_errors += 1
        if self._metrics is not None:
            try:
                from lip.infrastructure.monitoring.metrics import METRIC_KAFKA_PRODUCER_ERRORS
                self._metrics.increment(METRIC_KAFKA_PRODUCER_ERRORS)
            except Exception:
                pass
        logger.error(
            "Kafka produce failed after %d retries — routing to DLQ: %s",
            _DLQ_MAX_RETRIES, last_exc,
        )
        try:
            self._producer.produce(
                KafkaTopic.DEAD_LETTER.value,
                key=key,
                value=value,
                headers={"source-topic": topic, "error": str(last_exc)[:200]},
            )
            self._producer.poll(0)
        except Exception:
            logger.exception("Failed to route to dead-letter topic after produce failure")

    def _route_dead_letter(self, msg: Any) -> None:
        """Forward a failed message to the dead-letter topic for operator review."""
        if self._dry_run or self._producer is None:
            return
        try:
            self._producer.produce(
                KafkaTopic.DEAD_LETTER.value,
                key=msg.key(),
                value=msg.value(),
                headers={"source-topic": KafkaTopic.PAYMENT_EVENTS.value},
            )
            self._producer.poll(0)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to route message to dead-letter topic")

    # ── Stats ────────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """Return current processing statistics."""
        return {
            "processed": self._processed,
            "errors": self._errors,
            "produce_errors": self._produce_errors,
            "group_id": self._group_id,
            "dry_run": self._dry_run,
        }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="LIP C5 Kafka payment event consumer/producer worker."
    )
    parser.add_argument(
        "--group-id",
        default="lip-c5-worker",
        help="Kafka consumer group ID (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Consume and process but do not produce output messages",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Override the default payment_events topic name",
    )
    args = parser.parse_args()

    # Build KafkaConfig from environment
    kafka_config = KafkaConfig(
        bootstrap_servers=os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
        ).split(","),
        ssl_ca_location=os.environ.get("KAFKA_SSL_CA_LOCATION"),
        ssl_cert_location=os.environ.get("KAFKA_SSL_CERT_LOCATION"),
        ssl_key_location=os.environ.get("KAFKA_SSL_KEY_LOCATION"),
    )

    # Build a minimal pipeline function for standalone operation.
    # In production, inject the real LIPPipeline instance.
    def _noop_pipeline(event: NormalizedEvent) -> dict:
        logger.warning(
            "No pipeline injected — returning stub result for uetr=%s", event.uetr
        )
        return {"uetr": event.uetr, "status": "no_pipeline"}

    worker = PaymentEventWorker(
        kafka_config=kafka_config,
        pipeline_fn=_noop_pipeline,
        group_id=args.group_id,
        dry_run=args.dry_run,
    )
    worker.run(topic_override=args.topic)


if __name__ == "__main__":
    _cli()
