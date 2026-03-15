"""
test_c5_streaming.py — Unit tests for C5 streaming infrastructure
Tests: EventNormalizer (4 rails), KafkaConfig, FlinkJobRegistry, RedisConfig
"""
import unittest
from datetime import datetime
from decimal import Decimal

from lip.c5_streaming.event_normalizer import EventNormalizer, NormalizedEvent, normalize_event
from lip.c5_streaming.flink_jobs import FlinkJobConfig, FlinkJobRegistry, FlinkJobType
from lip.c5_streaming.kafka_config import TOPIC_DEFINITIONS, KafkaConfig, KafkaTopic
from lip.c5_streaming.redis_config import RedisConfig

# ---------------------------------------------------------------------------
# EventNormalizer — SWIFT rail
# ---------------------------------------------------------------------------

class TestNormalizeSwift(unittest.TestCase):

    def _make_msg(self, **overrides) -> dict:
        base = {
            "GrpHdr": {
                "MsgId": "UETR-SWIFT-001",
                "CreDtTm": "2025-06-15T10:30:00",
                "InstdAgt": {"FinInstnId": {"BIC": "DEUTDEFFXXX"}},
            },
            "DbtrAgt": {"FinInstnId": {"BIC": "BOFAUS3NXXX"}},
            "TxInfAndSts": {
                "OrgnlEndToEndId": "E2E-001",
                "StsRsnInf": {"Rsn": {"Cd": "AC01"}},
                "OrgnlTxRef": {
                    "Amt": {"InstdAmt": {"value": "10000.50", "Ccy": "USD"}},
                },
                "AddtlInf": "Insufficient funds",
            },
        }
        base.update(overrides)
        return base

    def setUp(self):
        self.n = EventNormalizer()

    def test_rail_is_swift(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.rail, "SWIFT")

    def test_uetr_extracted_from_msg_id(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.uetr, "UETR-SWIFT-001")

    def test_amount_parsed_as_decimal(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertIsInstance(event.amount, Decimal)
        self.assertEqual(event.amount, Decimal("10000.50"))

    def test_currency_extracted(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.currency, "USD")

    def test_sending_bic_from_dbtr_agt(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.sending_bic, "BOFAUS3NXXX")

    def test_receiving_bic_from_grp_hdr(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.receiving_bic, "DEUTDEFFXXX")

    def test_rejection_code_extracted(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.rejection_code, "AC01")

    def test_narrative_extracted(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertEqual(event.narrative, "Insufficient funds")

    def test_timestamp_parsed(self):
        event = self.n.normalize_swift(self._make_msg())
        self.assertIsInstance(event.timestamp, datetime)

    def test_no_rejection_code_returns_none(self):
        msg = self._make_msg()
        msg["TxInfAndSts"]["StsRsnInf"] = {}
        event = self.n.normalize_swift(msg)
        self.assertIsNone(event.rejection_code)

    def test_fallback_bic_from_tx_dbtr_agt(self):
        """If top-level DbtrAgt missing, fall back to TxInfAndSts.DbtrAgt."""
        msg = self._make_msg()
        del msg["DbtrAgt"]
        msg["TxInfAndSts"]["DbtrAgt"] = {"FinInstnId": {"BIC": "FALLBACKBIC"}}
        event = self.n.normalize_swift(msg)
        self.assertEqual(event.sending_bic, "FALLBACKBIC")

    def test_invalid_amount_defaults_to_zero(self):
        msg = self._make_msg()
        msg["TxInfAndSts"]["OrgnlTxRef"]["Amt"]["InstdAmt"] = {"value": "not_a_number", "Ccy": "USD"}
        event = self.n.normalize_swift(msg)
        self.assertEqual(event.amount, Decimal("0"))

    def test_raw_source_preserved(self):
        msg = self._make_msg()
        event = self.n.normalize_swift(msg)
        self.assertIs(event.raw_source, msg)


# ---------------------------------------------------------------------------
# EventNormalizer — FedNow rail
# ---------------------------------------------------------------------------

class TestNormalizeFedNow(unittest.TestCase):

    def _make_msg(self) -> dict:
        return {
            "messageId": "FEDNOW-MSG-001",
            "endToEndId": "E2E-FN-001",
            "amount": {"value": "5000.00", "currency": "USD"},
            "debitParty": {"routingNumber": "021000021"},
            "creditParty": {"routingNumber": "111000038"},
            "timestamp": "2025-06-15T14:00:00",
            "rejectReason": "INSF",
            "remittanceInfo": "Invoice payment",
        }

    def setUp(self):
        self.n = EventNormalizer()

    def test_rail_is_fednow(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.rail, "FEDNOW")

    def test_uetr_from_message_id(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.uetr, "FEDNOW-MSG-001")

    def test_amount_parsed(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.amount, Decimal("5000.00"))

    def test_currency_usd(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.currency, "USD")

    def test_routing_numbers_as_bic(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.sending_bic, "021000021")
        self.assertEqual(event.receiving_bic, "111000038")

    def test_rejection_code(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.rejection_code, "INSF")

    def test_no_rejection_code_is_none(self):
        msg = self._make_msg()
        del msg["rejectReason"]
        event = self.n.normalize_fednow(msg)
        self.assertIsNone(event.rejection_code)

    def test_narrative(self):
        event = self.n.normalize_fednow(self._make_msg())
        self.assertEqual(event.narrative, "Invoice payment")


# ---------------------------------------------------------------------------
# EventNormalizer — RTP rail
# ---------------------------------------------------------------------------

class TestNormalizeRTP(unittest.TestCase):

    def _make_msg(self) -> dict:
        return {
            "paymentMessage": {
                "messageId": "RTP-MSG-001",
                "endToEndId": "E2E-RTP-001",
            },
            "amount": {"value": "2500.00", "currency": "USD"},
            "sendingBank": "RTPSENDBIC",
            "receivingBank": "RTPRECVBIC",
            "timestamp": "2025-06-15T11:00:00",
        }

    def setUp(self):
        self.n = EventNormalizer()

    def test_rail_is_rtp(self):
        event = self.n.normalize_rtp(self._make_msg())
        self.assertEqual(event.rail, "RTP")

    def test_amount_parsed(self):
        event = self.n.normalize_rtp(self._make_msg())
        self.assertEqual(event.amount, Decimal("2500.00"))

    def test_sending_receiving_bank(self):
        event = self.n.normalize_rtp(self._make_msg())
        self.assertEqual(event.sending_bic, "RTPSENDBIC")
        self.assertEqual(event.receiving_bic, "RTPRECVBIC")

    def test_no_rejection_returns_none(self):
        event = self.n.normalize_rtp(self._make_msg())
        self.assertIsNone(event.rejection_code)

    def test_scalar_amount(self):
        msg = self._make_msg()
        msg["amount"] = "1234.56"
        event = self.n.normalize_rtp(msg)
        self.assertEqual(event.amount, Decimal("1234.56"))


# ---------------------------------------------------------------------------
# EventNormalizer — SEPA rail
# ---------------------------------------------------------------------------

class TestNormalizeSEPA(unittest.TestCase):

    def _make_msg(self) -> dict:
        return {
            "FIToFIPmtStsRpt": {
                "GrpHdr": {
                    "MsgId": "SEPA-UETR-001",
                    "CreDtTm": "2025-06-15T09:00:00",
                    "InstdAgt": {"FinInstnId": {"BIC": "BNPAFRPPXXX"}},
                },
                "DbtrAgt": {"FinInstnId": {"BIC": "DEUTDEFFXXX"}},
                "TxInfAndSts": {
                    "OrgnlEndToEndId": "E2E-SEPA-001",
                    "StsRsnInf": {"Rsn": {"Cd": "FF01"}},
                    "OrgnlTxRef": {
                        "Amt": {"InstdAmt": {"value": "8000.00", "Ccy": "EUR"}},
                    },
                },
            },
        }

    def setUp(self):
        self.n = EventNormalizer()

    def test_rail_is_sepa(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.rail, "SEPA")

    def test_currency_eur(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.currency, "EUR")

    def test_amount_parsed(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.amount, Decimal("8000.00"))

    def test_rejection_code(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.rejection_code, "FF01")

    def test_sending_bic(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.sending_bic, "DEUTDEFFXXX")

    def test_receiving_bic_from_instd_agt(self):
        event = self.n.normalize_sepa(self._make_msg())
        self.assertEqual(event.receiving_bic, "BNPAFRPPXXX")


# ---------------------------------------------------------------------------
# EventNormalizer — dispatch
# ---------------------------------------------------------------------------

class TestNormalizeDispatch(unittest.TestCase):

    def setUp(self):
        self.n = EventNormalizer()

    def test_dispatch_swift(self):
        msg = {
            "GrpHdr": {"MsgId": "X", "CreDtTm": None},
            "TxInfAndSts": {"OrgnlTxRef": {"Amt": {"InstdAmt": {"value": "100", "Ccy": "USD"}}}},
        }
        event = self.n.normalize("SWIFT", msg)
        self.assertEqual(event.rail, "SWIFT")

    def test_dispatch_case_insensitive(self):
        msg = {"messageId": "Y", "amount": {"value": "50", "currency": "USD"}}
        event = self.n.normalize("fednow", msg)
        self.assertEqual(event.rail, "FEDNOW")

    def test_unknown_rail_raises(self):
        with self.assertRaises(ValueError):
            self.n.normalize("PIGEONPOST", {})

    def test_convenience_function(self):
        msg = {
            "GrpHdr": {"MsgId": "Z", "CreDtTm": None},
            "TxInfAndSts": {"OrgnlTxRef": {"Amt": {"InstdAmt": {"value": "200", "Ccy": "USD"}}}},
        }
        event = normalize_event("SWIFT", msg)
        self.assertIsInstance(event, NormalizedEvent)


# ---------------------------------------------------------------------------
# KafkaConfig
# ---------------------------------------------------------------------------

class TestKafkaConfig(unittest.TestCase):

    def test_all_ten_topics_defined(self):
        self.assertEqual(len(TOPIC_DEFINITIONS), 10)

    def test_payment_events_partitions(self):
        cfg = TOPIC_DEFINITIONS[KafkaTopic.PAYMENT_EVENTS]
        self.assertEqual(cfg.partitions, 24)

    def test_decision_log_7yr_retention(self):
        cfg = TOPIC_DEFINITIONS[KafkaTopic.DECISION_LOG]
        expected_ms = 7 * 365 * 24 * 3600 * 1000
        self.assertEqual(cfg.retention_ms, expected_ms)

    def test_payment_events_exactly_once(self):
        cfg = TOPIC_DEFINITIONS[KafkaTopic.PAYMENT_EVENTS]
        self.assertTrue(cfg.exactly_once)

    def test_producer_config_has_required_keys(self):
        kafka = KafkaConfig()
        cfg = kafka.to_producer_config()
        self.assertIn("bootstrap.servers", cfg)
        self.assertIn("enable.idempotence", cfg)
        self.assertIn("acks", cfg)
        self.assertEqual(cfg["acks"], "all")

    def test_producer_config_idempotence_enabled(self):
        kafka = KafkaConfig()
        cfg = kafka.to_producer_config()
        self.assertTrue(cfg["enable.idempotence"])

    def test_consumer_config_isolation_level(self):
        kafka = KafkaConfig()
        cfg = kafka.to_consumer_config(group_id="test-group")
        self.assertEqual(cfg["isolation.level"], "read_committed")
        self.assertFalse(cfg["enable.auto.commit"])

    def test_consumer_config_group_id(self):
        kafka = KafkaConfig()
        cfg = kafka.to_consumer_config(group_id="lip-scorer")
        self.assertEqual(cfg["group.id"], "lip-scorer")

    def test_transactional_id_optional(self):
        kafka = KafkaConfig(transactional_id="lip-tx-001")
        cfg = kafka.to_producer_config()
        self.assertEqual(cfg.get("transactional.id"), "lip-tx-001")

    def test_max_in_flight_one_for_exactly_once(self):
        kafka = KafkaConfig()
        cfg = kafka.to_producer_config()
        self.assertEqual(cfg["max.in.flight.requests.per.connection"], 1)

    def test_partition_key_is_uetr(self):
        cfg = TOPIC_DEFINITIONS[KafkaTopic.PAYMENT_EVENTS]
        self.assertEqual(cfg.partition_key, "uetr")

    def test_replication_factor_three(self):
        for topic_cfg in TOPIC_DEFINITIONS.values():
            self.assertEqual(topic_cfg.replication_factor, 3,
                             f"{topic_cfg.topic} must have RF=3")


# ---------------------------------------------------------------------------
# FlinkJobRegistry
# ---------------------------------------------------------------------------

class TestFlinkJobRegistry(unittest.TestCase):

    def test_default_registry_has_all_jobs(self):
        registry = FlinkJobRegistry.create_default_registry()
        for job_type in FlinkJobType:
            cfg = registry.get_config(job_type)
            self.assertIsNotNone(cfg)

    def test_payment_scoring_parallelism_8(self):
        registry = FlinkJobRegistry.create_default_registry()
        cfg = registry.get_config(FlinkJobType.PAYMENT_SCORING)
        self.assertEqual(cfg.parallelism, 8)

    def test_unknown_job_raises_key_error(self):
        registry = FlinkJobRegistry()
        with self.assertRaises(KeyError):
            registry.get_config(FlinkJobType.PAYMENT_SCORING)

    def test_register_and_retrieve_handler(self):
        registry = FlinkJobRegistry()
        handler = lambda event: event  # noqa: E731
        registry.register(
            FlinkJobType.PAYMENT_SCORING,
            FlinkJobConfig(job_type=FlinkJobType.PAYMENT_SCORING),
            handler,
        )
        retrieved = registry.get_handler(FlinkJobType.PAYMENT_SCORING)
        self.assertIs(retrieved, handler)

    def test_checkpoint_interval_default(self):
        cfg = FlinkJobConfig(job_type=FlinkJobType.PAYMENT_SCORING)
        self.assertEqual(cfg.checkpoint_interval_ms, 60_000)

    def test_state_backend_rocksdb(self):
        cfg = FlinkJobConfig(job_type=FlinkJobType.PAYMENT_SCORING)
        self.assertEqual(cfg.state_backend, "rocksdb")

    def test_all_four_job_types_defined(self):
        self.assertEqual(len(FlinkJobType), 4)


# ---------------------------------------------------------------------------
# RedisConfig
# ---------------------------------------------------------------------------

class TestRedisConfig(unittest.TestCase):

    def test_default_host_redis(self):
        cfg = RedisConfig()
        self.assertEqual(cfg.host, "redis")

    def test_default_port_6379(self):
        cfg = RedisConfig()
        self.assertEqual(cfg.port, 6379)

    def test_connection_kwargs_host_and_port(self):
        cfg = RedisConfig(host="redis-prod", port=6380)
        kwargs = cfg.to_connection_kwargs()
        self.assertEqual(kwargs["host"], "redis-prod")
        self.assertEqual(kwargs["port"], 6380)

    def test_ssl_enabled_by_default(self):
        cfg = RedisConfig()
        kwargs = cfg.to_connection_kwargs()
        self.assertTrue(kwargs["ssl"])

    def test_ssl_disabled_flag(self):
        cfg = RedisConfig(ssl=False)
        kwargs = cfg.to_connection_kwargs()
        self.assertFalse(kwargs["ssl"])

    def test_password_omitted_when_none(self):
        cfg = RedisConfig(password=None)
        kwargs = cfg.to_connection_kwargs()
        self.assertNotIn("password", kwargs)

    def test_password_included_when_set(self):
        cfg = RedisConfig(password="s3cr3t")
        kwargs = cfg.to_connection_kwargs()
        self.assertEqual(kwargs["password"], "s3cr3t")

    def test_retry_on_timeout_default_true(self):
        cfg = RedisConfig()
        self.assertTrue(cfg.retry_on_timeout)


if __name__ == "__main__":
    unittest.main()
