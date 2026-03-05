"""
C5 Streaming — Kafka/Redis/Flink infrastructure configuration
Three-entity: MLO, MIPLO, ELO
"""
from .kafka_config import KafkaConfig, TOPIC_DEFINITIONS
from .redis_config import RedisConfig, KEY_SCHEMAS
from .event_normalizer import EventNormalizer, normalize_event

__all__ = [
    "KafkaConfig",
    "TOPIC_DEFINITIONS",
    "RedisConfig",
    "KEY_SCHEMAS",
    "EventNormalizer",
    "normalize_event",
]
