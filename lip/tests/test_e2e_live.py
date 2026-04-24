"""
test_e2e_live.py — Live integration tests for LIP C5 streaming via real Redpanda.

All tests in this module are tagged ``@pytest.mark.live`` and are auto-skipped when:
  - ``confluent_kafka`` is not installed  →  pip install confluent-kafka
  - Redpanda is unreachable at localhost:9092  →  ./scripts/start_local_infra.sh

The skip check runs at *collection time* (module body), so pytest reports a single
clean SKIP rather than per-test errors.

Three test classes:
  TestLiveInfraHealth   — verify all 10 required topics exist in Redpanda
  TestLiveKafkaRoundTrip — produce a pacs.002 event, consume it back, assert UETR intact
  TestLiveC5Worker      — drive PaymentEventWorker._process_message with a real Message

TODO (Phase 2 unblocks):
  - C6 Redis live test: VelocityChecker.redis_client is stored but never read;
    blocked until Phase 2 wires RollingWindow → Redis ZADD / ZRANGEBYSCORE.
  - C5 output round-trip: dry_run=True skips lip.failure.predictions produce;
    add full produce→consume validation when Phase 2 adds Redis consumer group offsets.
  - confluent_kafka optional dep: add [project.optional-dependencies.live] to
    pyproject.toml when formalising live test CI job (currently dynamic import).
"""
from __future__ import annotations

import json
import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# Module-level availability checks — run during pytest collection
# ---------------------------------------------------------------------------

try:
    from confluent_kafka import Consumer, Producer  # type: ignore[import]
    from confluent_kafka.admin import AdminClient  # type: ignore[import]
except ImportError:
    pytest.skip(
        "confluent_kafka not installed — pip install confluent-kafka",
        allow_module_level=True,
    )


def _broker_reachable() -> bool:
    """Return True if Redpanda is listening at localhost:9092."""
    try:
        p = Producer({"bootstrap.servers": "localhost:9092", "socket.timeout.ms": 2000})
        p.list_topics(timeout=3)
        return True
    except Exception:
        return False


if not _broker_reachable():
    pytest.skip(
        "Redpanda unreachable at localhost:9092 — run ./scripts/start_local_infra.sh",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Live imports — only reached when confluent_kafka is installed and broker is up
# ---------------------------------------------------------------------------

from lip.c5_streaming.event_normalizer import NormalizedEvent  # noqa: E402
from lip.c5_streaming.kafka_config import KafkaConfig, KafkaTopic  # noqa: E402
from lip.c5_streaming.kafka_worker import PaymentEventWorker  # noqa: E402

# Apply pytest.mark.live to every test in this module
pytestmark = pytest.mark.live

# ---------------------------------------------------------------------------
# PLAINTEXT KafkaConfig for local Redpanda (production uses SSL / mTLS)
#
# KafkaConfig defaults to security_protocol="SSL" with cert paths.
# Local Redpanda is PLAINTEXT only; the ssl_* fields are ignored by librdkafka
# when security.protocol=PLAINTEXT, so empty strings are safe.
# ---------------------------------------------------------------------------

_LIVE_CONFIG = KafkaConfig(
    bootstrap_servers=["localhost:9092"],
    security_protocol="PLAINTEXT",
    ssl_ca_location="",
    ssl_cert_location="",
    ssl_key_location="",
)

# All 10 canonical LIP Kafka topics
REQUIRED_TOPICS = {t.value for t in KafkaTopic}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _swift_payload(uetr: str) -> dict:
    """
    Minimal ISO 20022 pacs.002 payload keyed by uetr.

    Mirrors the structure from test_c5_kafka_worker._make_swift_payload so
    EventNormalizer.normalize_swift() can parse it without error.
    GrpHdr.MsgId is the field EventNormalizer maps to NormalizedEvent.uetr.
    """
    return {
        "GrpHdr": {
            "MsgId": uetr,
            "CreDtTm": "2024-03-01T12:00:00",
            "InstdAgt": {"FinInstnId": {"BIC": "CHASUS33XXX"}},
        },
        "TxInfAndSts": {
            "OrgnlEndToEndId": f"PAY-{uetr}",
            "StsRsnInf": {"Rsn": {"Cd": "AC01"}},
            "OrgnlTxRef": {
                "Amt": {"InstdAmt": {"value": "75000.00", "Ccy": "USD"}},
            },
            "AddtlInf": "Live integration test payment",
        },
        "DbtrAgt": {"FinInstnId": {"BIC": "DEUTDEDBFRA"}},
        "rail": "SWIFT",
    }


def _flush_produce(topic: str, uetr: str, payload: dict) -> None:
    """
    Produce one JSON message synchronously.

    flush(timeout=10) blocks until the broker acknowledges all in-flight
    messages.  An assertion on the return value (number of undelivered messages)
    gives a clear failure if the broker is unreachable mid-test.
    """
    p = Producer(_LIVE_CONFIG.to_producer_config())
    p.produce(topic, key=uetr.encode(), value=json.dumps(payload).encode())
    undelivered = p.flush(timeout=10)
    assert undelivered == 0, (
        f"Producer flush timed out — {undelivered} message(s) undelivered to {topic}"
    )


def _consumer_latest(group_id: str) -> Consumer:
    """
    Build a Consumer with auto.offset.reset=latest.

    Using 'latest' instead of 'earliest' means the consumer only sees messages
    produced *after* it subscribes — preventing interference from historical events
    left in the topic by previous test runs.
    """
    cfg = {
        **_LIVE_CONFIG.to_consumer_config(group_id),
        "auto.offset.reset": "latest",
    }
    return Consumer(cfg)


def _wait_assignment(consumer: Consumer, timeout_s: float = 8.0) -> None:
    """
    Poll until the broker completes partition assignment for this consumer.

    Kafka group join + rebalance takes 500–2000 ms depending on session.timeout.ms.
    We must wait before producing so the 'latest' seek point is registered.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        consumer.poll(0.5)
        if consumer.assignment():
            return
    raise TimeoutError(
        f"Consumer partition assignment not received within {timeout_s}s"
    )


def _poll_for_uetr(consumer: Consumer, expected_uetr: str, timeout_s: float = 10.0):
    """
    Poll until a message whose GrpHdr.MsgId matches expected_uetr is received.

    Returns the raw confluent_kafka.Message so callers can use it as a real
    Message object (e.g. to pass to PaymentEventWorker._process_message).
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        msg = consumer.poll(0.5)
        if msg is None or msg.error():
            continue
        value = msg.value()
        if value is None:
            continue
        decoded = json.loads(value.decode("utf-8"))
        if decoded.get("GrpHdr", {}).get("MsgId") == expected_uetr:
            return msg
    raise TimeoutError(
        f"UETR {expected_uetr!r} not received from broker within {timeout_s}s"
    )


# ---------------------------------------------------------------------------
# TestLiveInfraHealth
# ---------------------------------------------------------------------------


class TestLiveInfraHealth:
    """Verify Redpanda cluster has all 10 required LIP topics."""

    def test_all_required_topics_exist(self) -> None:
        """
        All topics defined in KafkaTopic must be present in Redpanda.

        Topics are created by init_topics.sh, which is called from
        start_local_infra.sh.  A missing topic indicates the infra script
        was not run or was interrupted.
        """
        admin = AdminClient({"bootstrap.servers": "localhost:9092"})
        metadata = admin.list_topics(timeout=10)
        present = set(metadata.topics.keys())

        missing = REQUIRED_TOPICS - present
        assert not missing, (
            f"Missing Redpanda topics: {missing!r}\n"
            "Run ./scripts/start_local_infra.sh to create them."
        )


# ---------------------------------------------------------------------------
# TestLiveKafkaRoundTrip
# ---------------------------------------------------------------------------


class TestLiveKafkaRoundTrip:
    """Produce a SWIFT event and verify it survives the broker round-trip."""

    def test_uetr_survives_round_trip(self) -> None:
        """
        Produce a pacs.002 JSON payload keyed by UUID uetr; consume it back.

        Asserts:
        - The broker accepted the message (flush() returned 0 undelivered)
        - The message was partitioned and delivered to a consumer
        - JSON decodes cleanly from raw bytes
        - GrpHdr.MsgId in the decoded payload matches our produced uetr exactly
        """
        uetr = str(uuid.uuid4())
        group_id = f"live-rt-{uuid.uuid4().hex[:8]}"
        topic = KafkaTopic.PAYMENT_EVENTS.value

        consumer = _consumer_latest(group_id)
        consumer.subscribe([topic])
        try:
            # Wait for assignment before producing so 'latest' offset is captured
            _wait_assignment(consumer)
            _flush_produce(topic, uetr, _swift_payload(uetr))
            msg = _poll_for_uetr(consumer, uetr)
        finally:
            consumer.close()

        decoded = json.loads(msg.value().decode("utf-8"))
        assert decoded["GrpHdr"]["MsgId"] == uetr
        assert "TxInfAndSts" in decoded


# ---------------------------------------------------------------------------
# TestLiveC5Worker
# ---------------------------------------------------------------------------


class TestLiveC5Worker:
    """PaymentEventWorker processes a real confluent_kafka.Message via _process_message."""

    def test_worker_calls_pipeline_with_normalised_event(self) -> None:
        """
        A real Kafka message is consumed and passed to PaymentEventWorker._process_message.

        The test:
        1. Produces a SWIFT pacs.002 event to lip.payment.events
        2. Consumes the real confluent_kafka.Message from Redpanda
        3. Passes that Message directly to worker._process_message (bypasses run() loop)
        4. Asserts the injected mock pipeline received a valid NormalizedEvent

        dry_run=True: no message is produced to lip.failure.predictions
        (full output round-trip is a TODO blocked on Phase 2).
        """
        uetr = str(uuid.uuid4())
        group_id = f"live-c5-{uuid.uuid4().hex[:8]}"
        topic = KafkaTopic.PAYMENT_EVENTS.value

        consumer = _consumer_latest(group_id)
        consumer.subscribe([topic])
        try:
            _wait_assignment(consumer)
            _flush_produce(topic, uetr, _swift_payload(uetr))
            real_msg = _poll_for_uetr(consumer, uetr)
        finally:
            consumer.close()

        assert real_msg is not None, f"Did not receive UETR {uetr} from broker"

        # --- Wire up tracking pipeline ---
        received: list[NormalizedEvent] = []

        def _mock_pipeline(event: NormalizedEvent) -> dict:
            received.append(event)
            return {"uetr": event.uetr, "status": "FUNDED"}

        worker = PaymentEventWorker(
            kafka_config=_LIVE_CONFIG,
            pipeline_fn=_mock_pipeline,
            dry_run=True,
        )
        # _process_message does not use self._consumer or self._producer when
        # dry_run=True, so we skip full broker client initialisation.
        worker._consumer = None
        worker._producer = None

        worker._process_message(real_msg)

        # --- Assertions ---
        assert len(received) == 1, (
            f"Expected pipeline called once, got {len(received)}"
        )
        event = received[0]
        assert isinstance(event, NormalizedEvent), (
            f"Pipeline received {type(event).__name__}, expected NormalizedEvent"
        )
        # EventNormalizer maps GrpHdr.MsgId → NormalizedEvent.uetr for SWIFT rail
        assert event.uetr == uetr, f"Event UETR mismatch: got {event.uetr!r}"
        assert event.rail == "SWIFT"
        assert worker.stats["processed"] == 1
        assert worker.stats["errors"] == 0
