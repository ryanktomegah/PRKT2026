"""
C5 Streaming — Kafka/Redis/Flink infrastructure configuration
Three-entity: MLO, MIPLO, ELO
"""
from .event_normalizer import EventNormalizer, normalize_event
from .kafka_config import TOPIC_DEFINITIONS, KafkaConfig
from .redis_config import KEY_SCHEMAS, RedisConfig

__all__ = [
    "KafkaConfig",
    "TOPIC_DEFINITIONS",
    "RedisConfig",
    "KEY_SCHEMAS",
    "EventNormalizer",
    "normalize_event",
]
