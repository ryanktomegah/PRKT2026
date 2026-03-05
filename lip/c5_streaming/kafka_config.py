"""
kafka_config.py — Kafka topic definitions and partition strategies
C5 Spec: Exactly-once semantics, payment event processing
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class KafkaTopic(str, Enum):
    PAYMENT_EVENTS = "lip.payment.events"
    FAILURE_PREDICTIONS = "lip.failure.predictions"
    SETTLEMENT_SIGNALS = "lip.settlement.signals"
    DISPUTE_RESULTS = "lip.dispute.results"
    VELOCITY_ALERTS = "lip.velocity.alerts"
    LOAN_OFFERS = "lip.loan.offers"
    REPAYMENT_EVENTS = "lip.repayment.events"
    DECISION_LOG = "lip.decision.log"
    DEAD_LETTER = "lip.dead.letter"


@dataclass
class TopicConfig:
    topic: KafkaTopic
    partitions: int
    replication_factor: int = 3
    retention_ms: int = 7 * 24 * 3600 * 1000  # 7 days default
    exactly_once: bool = True
    partition_key: str = "uetr"  # partition by UETR for ordering


TOPIC_DEFINITIONS: Dict[KafkaTopic, TopicConfig] = {
    KafkaTopic.PAYMENT_EVENTS: TopicConfig(
        topic=KafkaTopic.PAYMENT_EVENTS,
        partitions=24,
        exactly_once=True,
    ),
    KafkaTopic.FAILURE_PREDICTIONS: TopicConfig(
        topic=KafkaTopic.FAILURE_PREDICTIONS,
        partitions=12,
    ),
    KafkaTopic.SETTLEMENT_SIGNALS: TopicConfig(
        topic=KafkaTopic.SETTLEMENT_SIGNALS,
        partitions=24,
    ),
    KafkaTopic.DISPUTE_RESULTS: TopicConfig(
        topic=KafkaTopic.DISPUTE_RESULTS,
        partitions=6,
    ),
    KafkaTopic.VELOCITY_ALERTS: TopicConfig(
        topic=KafkaTopic.VELOCITY_ALERTS,
        partitions=6,
    ),
    KafkaTopic.LOAN_OFFERS: TopicConfig(
        topic=KafkaTopic.LOAN_OFFERS,
        partitions=6,
    ),
    KafkaTopic.REPAYMENT_EVENTS: TopicConfig(
        topic=KafkaTopic.REPAYMENT_EVENTS,
        partitions=6,
    ),
    KafkaTopic.DECISION_LOG: TopicConfig(
        topic=KafkaTopic.DECISION_LOG,
        partitions=12,
        retention_ms=7 * 365 * 24 * 3600 * 1000,  # 7 years for compliance
    ),
    KafkaTopic.DEAD_LETTER: TopicConfig(
        topic=KafkaTopic.DEAD_LETTER,
        partitions=6,
    ),
}


@dataclass
class KafkaConfig:
    bootstrap_servers: List[str] = field(default_factory=lambda: ["kafka:9092"])
    security_protocol: str = "SSL"
    ssl_ca_location: str = "/etc/ssl/kafka/ca.crt"
    ssl_cert_location: str = "/etc/ssl/kafka/client.crt"
    ssl_key_location: str = "/etc/ssl/kafka/client.key"
    enable_idempotence: bool = True  # exactly-once
    acks: str = "all"
    max_in_flight_requests_per_connection: int = 1  # exactly-once requires this
    transactional_id: Optional[str] = None

    def to_producer_config(self) -> dict:
        cfg = {
            "bootstrap.servers": ",".join(self.bootstrap_servers),
            "security.protocol": self.security_protocol,
            "ssl.ca.location": self.ssl_ca_location,
            "ssl.certificate.location": self.ssl_cert_location,
            "ssl.key.location": self.ssl_key_location,
            "enable.idempotence": self.enable_idempotence,
            "acks": self.acks,
            "max.in.flight.requests.per.connection": self.max_in_flight_requests_per_connection,
        }
        if self.transactional_id:
            cfg["transactional.id"] = self.transactional_id
        return cfg

    def to_consumer_config(self, group_id: str) -> dict:
        return {
            "bootstrap.servers": ",".join(self.bootstrap_servers),
            "security.protocol": self.security_protocol,
            "ssl.ca.location": self.ssl_ca_location,
            "ssl.certificate.location": self.ssl_cert_location,
            "ssl.key.location": self.ssl_key_location,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # manual commit for exactly-once
            "isolation.level": "read_committed",
        }
