# C5: Streaming

## Role in Pipeline

C5 is the **ingest and normalisation layer**. It ingests raw payment events from multiple payment rails (SWIFT, FedNow, RTP, SEPA) via Kafka, normalises them into the canonical `NormalizedEvent` format, and routes them to the appropriate downstream Flink jobs.

## Algorithm 1 Position

```
pacs.002 / FedNow / RTP / SEPA
        │
        ▼
  [C5: Kafka worker]
        │  normalise to NormalizedEvent
        ▼
  C1 (via Flink PAYMENT_SCORING job)
```

C5 is **Step 0 / pre-Step 1** of Algorithm 1 — it produces the `NormalizedEvent` consumed by the pipeline.

## Key Classes

| Class / Module | File | Description |
|---------------|------|-------------|
| `EventNormalizer` | `event_normalizer.py` | Multi-rail message parser (SWIFT/FedNow/RTP/SEPA) |
| `KafkaConfig` | `kafka_config.py` | Producer/consumer configuration with EOS settings |
| `RedisConfig` | `redis_config.py` | Cluster config + key schema definitions |
| `FlinkJobRegistry` | `flink_jobs.py` | Job registry with configs and routing handlers |
| `KafkaTopic` | `kafka_config.py` | Enum of all 9 LIP topics |

## Kafka Topic Map

| Topic | Partitions | Retention | Description |
|-------|-----------|-----------|-------------|
| `lip.payment.events` | 24 | 7 days | Inbound raw payment events |
| `lip.failure.predictions` | 12 | 7 days | C1 classifier output |
| `lip.settlement.signals` | 24 | 7 days | Inbound settlement confirmations |
| `lip.dispute.results` | 6 | 7 days | C4 classifier output |
| `lip.velocity.alerts` | 6 | 7 days | C6 AML velocity breaches |
| `lip.loan.offers` | 6 | 7 days | C7 outbound loan offers |
| `lip.repayment.events` | 6 | 7 days | C3 repayment confirmations |
| `lip.decision.log` | 12 | **7 years** | Immutable audit trail (compliance) |
| `lip.dead.letter` | 6 | 7 days | Unprocessable events |

> **Note**: `lip.decision.log` has a **7-year retention** policy (`retention_ms = 7 * 365 * 24 * 3600 * 1000`) required by SR 11-7 model governance and EU AI Act Art.17.

## Exactly-Once Semantics

All Kafka producers use:
- `enable.idempotence = True`
- `acks = all`
- `max.in.flight.requests.per.connection = 1`

All consumers use:
- `enable.auto.commit = False` (manual commit)
- `isolation.level = read_committed`

## Redis Key Schema

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `lip:embedding:{currency_pair}` | 7 days | Corridor embeddings |
| `lip:uetr_map:{end_to_end_id}` | — | UETR deduplication |
| `lip:velocity:{entity_id}:{window}` | 24 h | AML velocity counters |
| `lip:salt:current` | 365 days | Current AML salt |
| `lip:salt:previous` | 30 days | Previous salt (overlap window) |
| `lip:kill_switch` | No TTL | Kill switch flag |

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `DECISION_LOG_RETENTION_YEARS` | **7** | `lip.decision.log` Kafka retention |
| `CORRIDOR_BUFFER_WINDOW_DAYS` | 90 | Redis corridor embedding lookback |

## Spec References

- Architecture Spec v1.2 §C5 — Streaming component specification
- Architecture Spec v1.2 §S11.3 — Redis key schema and salt storage
