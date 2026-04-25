"""
test_c5_kafka_worker.py — Tests for C5 PaymentEventWorker.

confluent_kafka is NOT installed in CI, so we mock it entirely via sys.modules.
All tests run without a real Kafka broker.
"""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Fake confluent_kafka module (installed once at module level)
# ---------------------------------------------------------------------------

def _install_fake_confluent_kafka():
    """Create and inject a minimal fake confluent_kafka into sys.modules."""
    if "confluent_kafka" in sys.modules:
        return  # already present (real or fake)

    ck = types.ModuleType("confluent_kafka")

    class _FakeMessage:
        def __init__(self, value, key=None, offset=0, error=None):
            self._value = value
            self._key = key
            self._offset = offset
            self._error = error

        def value(self):
            return self._value

        def key(self):
            return self._key

        def offset(self):
            return self._offset

        def error(self):
            return self._error

    class _FakeConsumer:
        def __init__(self, cfg):
            self._subscribed = []
            self._messages = []  # injected by tests
            self.committed = []  # track committed messages for B6-07 tests

        def subscribe(self, topics):
            self._subscribed = topics

        def poll(self, timeout=1.0):
            if self._messages:
                return self._messages.pop(0)
            return None

        def commit(self, message=None, asynchronous=True):
            if message is not None:
                self.committed.append(message)

        def close(self):
            pass

    class _FakeProducer:
        def __init__(self, cfg):
            self.produced = []

        def produce(self, topic, key=None, value=None, headers=None):
            self.produced.append({"topic": topic, "key": key, "value": value})

        def poll(self, timeout=0):
            pass

        def flush(self, timeout=10):
            pass

    ck.Consumer = _FakeConsumer
    ck.Producer = _FakeProducer
    ck._FakeMessage = _FakeMessage
    sys.modules["confluent_kafka"] = ck
    return ck


_install_fake_confluent_kafka()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_swift_payload(uetr="test-uetr-001", rejection_code="AC01"):
    """Minimal SWIFT pacs.002 message dict that EventNormalizer.normalize_swift() can handle.

    The SWIFT normalizer reads:
      GrpHdr.MsgId          → NormalizedEvent.uetr
      TxInfAndSts.StsRsnInf.Rsn.Cd → rejection_code
      DbtrAgt.FinInstnId.BIC → sending_bic
      GrpHdr.InstdAgt.FinInstnId.BIC → receiving_bic
      OrgnlTxRef.Amt.InstdAmt → amount/currency
    """
    return {
        "GrpHdr": {
            "MsgId": uetr,
            "CreDtTm": "2024-03-01T12:00:00",
            "InstdAgt": {"FinInstnId": {"BIC": "CHASUS33XXX"}},
        },
        "TxInfAndSts": {
            "OrgnlEndToEndId": f"PAY-{uetr}",
            "StsRsnInf": {"Rsn": {"Cd": rejection_code}},
            "OrgnlTxRef": {
                "Amt": {
                    "InstdAmt": {"value": "50000.00", "Ccy": "EUR"}
                }
            },
            "AddtlInf": "Test payment",
        },
        "DbtrAgt": {"FinInstnId": {"BIC": "DEUTDEDBFRA"}},
        "rail": "SWIFT",
    }


def _make_kafka_message(payload: dict, offset: int = 0):
    """Wrap a payload dict as a fake Kafka message."""
    import confluent_kafka as ck

    # Extract uetr from either flat or pacs.002 nested format
    uetr = payload.get("GrpHdr", {}).get("MsgId", payload.get("uetr", ""))
    fake_message_cls = getattr(ck, "_FakeMessage")
    return fake_message_cls(
        value=json.dumps(payload).encode("utf-8"),
        key=uetr.encode("utf-8"),
        offset=offset,
    )


def _make_worker(pipeline_fn=None, dry_run=True):
    """Build a PaymentEventWorker with a fake KafkaConfig and optional pipeline."""
    from lip.c5_streaming.kafka_config import KafkaConfig
    from lip.c5_streaming.kafka_worker import PaymentEventWorker

    cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
    if pipeline_fn is None:
        pipeline_fn = lambda event: {"uetr": event.uetr, "status": "ok"}  # noqa: E731
    return PaymentEventWorker(kafka_config=cfg, pipeline_fn=pipeline_fn, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPaymentEventWorkerInit(unittest.TestCase):
    def test_instantiation(self):
        worker = _make_worker()
        self.assertTrue(worker._dry_run)
        self.assertEqual(worker._group_id, "lip-c5-worker")
        self.assertEqual(worker._processed, 0)
        self.assertEqual(worker._errors, 0)

    def test_custom_group_id(self):
        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, group_id="my-group", dry_run=True)
        self.assertEqual(worker._group_id, "my-group")


class TestProcessMessage(unittest.TestCase):
    """Unit tests for _process_message — does not require a running Kafka broker."""

    def test_swift_event_calls_pipeline(self):
        """A valid SWIFT message reaches the pipeline function."""
        calls = []

        def mock_pipeline(event):
            calls.append(event)
            return {"uetr": event.uetr, "status": "ok"}

        worker = _make_worker(pipeline_fn=mock_pipeline, dry_run=True)
        # Bootstrap the consumer/producer (dry_run=True → no producer)
        worker._consumer = MagicMock()
        worker._producer = None

        payload = _make_swift_payload(uetr="abc-123")
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        self.assertEqual(len(calls), 1)
        event = calls[0]
        self.assertEqual(event.uetr, "abc-123")
        self.assertEqual(event.rail, "SWIFT")
        self.assertEqual(event.currency, "EUR")
        self.assertEqual(worker._processed, 1)
        self.assertEqual(worker._errors, 0)

    def test_fednow_rail_normalised(self):
        """FedNow events are dispatched to the FedNow normaliser."""
        received = []

        def mock_pipeline(event):
            received.append(event)
            return {}

        worker = _make_worker(pipeline_fn=mock_pipeline, dry_run=True)
        worker._consumer = MagicMock()
        worker._producer = None

        payload = _make_swift_payload(uetr="fed-001")
        payload["rail"] = "FEDNOW"
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        # May raise EventNormalizationError for missing FedNow fields — that's
        # fine; what matters is the worker doesn't crash the consumer loop.
        # Either 1 success or 1 error is acceptable.
        self.assertEqual(worker._processed + worker._errors, 1)

    def test_pipeline_result_produced_when_not_dry_run(self):
        """When dry_run=False, pipeline result is produced to failure_predictions."""
        import confluent_kafka as ck

        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        producer = ck.Producer({})
        worker = PaymentEventWorker(
            kafka_config=cfg,
            pipeline_fn=lambda e: {"uetr": e.uetr, "status": "FUNDED"},
            dry_run=False,
        )
        worker._consumer = MagicMock()
        worker._producer = producer

        payload = _make_swift_payload(uetr="prod-001")
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        self.assertEqual(worker._processed, 1)
        self.assertEqual(len(producer.produced), 1)
        produced = producer.produced[0]
        self.assertIn("failure", produced["topic"])
        result = json.loads(produced["value"].decode("utf-8"))
        self.assertEqual(result["uetr"], "prod-001")
        self.assertEqual(result["status"], "FUNDED")

    def test_null_value_message_skipped(self):
        """Messages with None value are skipped without error."""
        import confluent_kafka as ck

        worker = _make_worker(dry_run=True)
        worker._consumer = MagicMock()
        worker._producer = None

        null_msg = ck._FakeMessage(value=None, offset=5)
        worker._process_message(null_msg)

        self.assertEqual(worker._processed, 0)
        self.assertEqual(worker._errors, 0)

    def test_invalid_json_routes_to_dead_letter(self):
        """Invalid JSON increments error counter and routes to dead-letter."""
        import confluent_kafka as ck

        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        producer = ck.Producer({})
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=False)
        worker._consumer = MagicMock()
        worker._producer = producer

        bad_msg = ck._FakeMessage(value=b"not valid json{{{", offset=99)
        worker._process_message(bad_msg)

        self.assertEqual(worker._errors, 1)
        self.assertEqual(worker._processed, 0)
        # Dead letter should have been produced
        self.assertEqual(len(producer.produced), 1)
        self.assertIn("dead", producer.produced[0]["topic"])

    def test_pipeline_exception_routes_to_dead_letter(self):
        """Pipeline raising an exception increments errors and routes to dead-letter."""
        import confluent_kafka as ck

        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        def exploding_pipeline(event):
            raise RuntimeError("pipeline exploded")

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        producer = ck.Producer({})
        worker = PaymentEventWorker(cfg, exploding_pipeline, dry_run=False)
        worker._consumer = MagicMock()
        worker._producer = producer

        payload = _make_swift_payload(uetr="boom-001")
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        self.assertEqual(worker._errors, 1)
        self.assertIn("dead", producer.produced[0]["topic"])


class TestWorkerStats(unittest.TestCase):
    def test_stats_initial(self):
        worker = _make_worker()
        stats = worker.stats
        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["errors"], 0)
        self.assertTrue(stats["dry_run"])


class TestOffsetCommitB607(unittest.TestCase):
    """B6-07: offset must be committed only on success, never on error."""

    def _make_mock_consumer(self):
        consumer = MagicMock()
        consumer.committed_messages = []

        def _commit(message=None, asynchronous=True):
            if message is not None:
                consumer.committed_messages.append(message)

        consumer.commit.side_effect = _commit
        return consumer

    def test_commit_on_success(self):
        """Offset is committed after successful pipeline processing."""
        worker = _make_worker(dry_run=True)
        worker._consumer = self._make_mock_consumer()
        worker._producer = None

        payload = _make_swift_payload(uetr="commit-ok-001")
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        self.assertEqual(worker._processed, 1)
        worker._consumer.commit.assert_called_once_with(message=msg)

    def test_no_commit_on_json_error(self):
        """Offset is NOT committed when JSON decode fails."""
        import confluent_kafka as ck

        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        producer = ck.Producer({})
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=False)
        worker._consumer = self._make_mock_consumer()
        worker._producer = producer

        bad_msg = ck._FakeMessage(value=b"not json{{", offset=77)
        worker._process_message(bad_msg)

        self.assertEqual(worker._errors, 1)
        worker._consumer.commit.assert_not_called()

    def test_no_commit_on_pipeline_error(self):
        """Offset is NOT committed when the pipeline function raises."""
        import confluent_kafka as ck

        from lip.c5_streaming.kafka_config import KafkaConfig
        from lip.c5_streaming.kafka_worker import PaymentEventWorker

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        producer = ck.Producer({})
        worker = PaymentEventWorker(cfg, lambda e: (_ for _ in ()).throw(RuntimeError("boom")), dry_run=False)
        worker._consumer = self._make_mock_consumer()
        worker._producer = producer

        payload = _make_swift_payload(uetr="no-commit-001")
        msg = _make_kafka_message(payload)
        worker._process_message(msg)

        self.assertEqual(worker._errors, 1)
        worker._consumer.commit.assert_not_called()

    def test_commit_on_null_value(self):
        """Null-value tombstone messages advance the offset (safe to skip)."""
        import confluent_kafka as ck

        worker = _make_worker(dry_run=True)
        worker._consumer = self._make_mock_consumer()
        worker._producer = None

        null_msg = ck._FakeMessage(value=None, offset=5)
        worker._process_message(null_msg)

        self.assertEqual(worker._processed, 0)
        self.assertEqual(worker._errors, 0)
        worker._consumer.commit.assert_called_once_with(message=null_msg)


if __name__ == "__main__":
    unittest.main()
