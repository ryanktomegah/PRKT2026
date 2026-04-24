# `lip/c5_streaming/` — ISO 20022 Normalisation and Kafka Ingestion

> **The entry point for every payment event.** Raw `pacs.002` rejection messages (and their CBDC equivalents) arrive from the licensee bank's SWIFT gateway or payment rail — C5 normalises them into a single `NormalizedEvent` shape, enforces schema integrity, and publishes into the Kafka topic that drives the pipeline.

**Source:** `lip/c5_streaming/` (Python) + `lip/c5_streaming/go_consumer/` (Go)
**Module count:** 10 Python files + Go consumer, 2,588 LoC Python + ~1500 LoC Go
**Test files:** 5 (`test_c5_{consumer_commit_on_error,kafka_worker,streaming,stress_regime,telemetry_eligible}.py`) + `test_dgen_c6_bic_validity.py`
**Spec:** [`../specs/BPI_C5_Component_Spec_v1.0_Part1.md`](../specs/BPI_C5_Component_Spec_v1.0_Part1.md) + Part 2
**Migration:** [`../specs/c5_kafka_consumer_migration.md`](../specs/c5_kafka_consumer_migration.md)

---

## Purpose

C5 owns three responsibilities that happen before anything else in the platform sees the event:

1. **Envelope validation** — enforce ISO 20022 `pacs.002` schema compliance; reject malformed messages with `MalformedEventError`.
2. **Rail-agnostic normalisation** — produce a single `NormalizedEvent` shape from SWIFT, CBDC, or other rails.
3. **Kafka ingestion** — deliver validated events to the pipeline topic with at-least-once guarantees + dead-letter queue for poison messages.

C5 is the licensee-side boundary — it is the only component that talks to the bank's internal payment rails. Every other component consumes from Kafka topics C5 produces.

---

## Architecture — dual-path (Go + Python)

```
 Bank SWIFT gateway ──┐
 (pacs.002 XML)       │
                      ▼
            ┌──────────────────────────┐
            │ C5 Go Consumer           │
            │ lip/c5_streaming/        │
            │   go_consumer/           │
            │                          │
            │  High-throughput fast    │
            │  path. Consumes raw      │
            │  events, validates XML,  │
            │  normalises to proto,    │
            │  writes to Kafka.        │
            └──────────────────────────┘
                      │  Kafka
                      ▼
            ┌──────────────────────────┐
            │ C5 Python Worker         │
            │ kafka_worker.py          │
            │                          │
            │  Enrichment + dispatch   │
            │  to C1/C6/C2 subscribers.│
            │  Also used when Go       │
            │  consumer unavailable.   │
            └──────────────────────────┘
```

### Why dual implementation

The Go consumer (`go_consumer/consumer.go` + `normalizer.go`) is the production path — confluent-kafka-go bindings, ~15k TPS per replica. The Python worker exists because:

1. **Local dev convenience** — engineers can run `docker-compose up -d` and `python -m lip.c5_streaming.kafka_worker` without setting up Go toolchain.
2. **Integration testing** — `test_c5_kafka_worker.py` exercises the full pipeline end-to-end without the Go consumer in the loop.
3. **Migration path** — the Python worker is the legacy implementation; it is still validated against the Go consumer's outputs in parallel (`test_c5_streaming.py::test_go_py_parity`).

The Go consumer is the default in staging. Python worker is the default in unit tests.

---

## Normalisation (`event_normalizer.py`)

The core dataclass:

```python
@dataclass(frozen=True)
class NormalizedEvent:
    uetr: str                       # ISO 20022 Unique End-to-End Transaction Reference
    individual_payment_id: str      # C3 dedup key
    sending_bic: str                # 8 or 11 chars; validated via regex
    receiving_bic: str              # same
    amount: Decimal                 # Decimal, never float
    currency: str                   # ISO 4217 3-letter
    timestamp: datetime             # tz-aware UTC
    rail: str                       # "SWIFT" | "SEPA" | "CBDC_MBRIDGE" | "CBDC_HK" | ...
    rejection_code: str             # ISO 20022 ExternalPaymentTransactionStatusReason1Code
    narrative: Optional[str]        # Free text — consumed by C4
    raw_source: dict                # Audit trail of the original envelope
```

### Validation rules

- **UETR** — must match `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` (UUIDv4 format per ISO 20022)
- **BIC** — 8 or 11 alphanumeric chars; reject if fits the sentinel `XXXXXXXXXXX` pattern (used to detect test-message leaks into production)
- **amount** — must be `> 0`; precision at most 2 decimal places; rejected if parsed as float (`Decimal` only per CLAUDE.md rule)
- **timestamp** — must be `tz-aware UTC`; reject naive datetimes
- **currency** — must be in `SUPPORTED_CURRENCIES` frozenset in `lip/common/constants.py`

Malformed events raise `MalformedEventError` which the Kafka consumer commits to the dead-letter queue rather than retrying.

### Test-message detection

`_TEST_BIC = "XXXXXXXXXXX"` is the SWIFT test-message sentinel. Any event where sending_bic OR receiving_bic equals this value is `test_only = True` and routed to the test Kafka topic, never to the production pipeline topic. This is belt-and-braces against licensee-side config errors where test traffic leaks into prod.

---

## CBDC normaliser (`cbdc_normalizer.py`)

Multi-CBDC support — mBridge (BIS), Hong Kong e-HKD, digital ECB euro, Project Dunbar. Each CBDC rail has its own message format; `CBDCNormalizer` adapts them all into the same `NormalizedEvent` shape.

Research status — wired for proof-of-concept integration. Production use requires per-CBDC signed integration agreements which don't yet exist. The adapter tests (`test_c5_streaming.py::test_mbridge_normalisation`) validate the mapping shape only, not live CBDC traffic.

---

## Stress regime detector (`stress_regime_detector.py`)

Monitors corridor failure rates in real-time. If the short-term (1h) failure rate exceeds the long-term (24h) baseline by a multiplier (default 3.0), the corridor is declared a `STRESS_REGIME`.

When in stress:
1. Triggers human review for all offers in the stressed corridor
2. Alerts the licensee bank's risk desk via Kafka topic `lip.stress.regime`

Wired into the real runtime pipeline via `build_runtime_pipeline()` — enabled by default, disable with `LIP_STRESS_DETECTOR_DISABLED=1`. Configurable via `LIP_STRESS_BASELINE_SECONDS`, `LIP_STRESS_CURRENT_SECONDS`, `LIP_STRESS_MULTIPLIER`, `LIP_STRESS_MIN_TXNS` env vars.

---

## Cancellation detector (`cancellation_detector.py`)

A variant of the stress detector focused on `pacs.028` cancellation messages. A surge in cancellations often precedes settlement failures; detecting the surge earlier than C1's failure probability crossing τ\* gives the pipeline a lead-time signal.

Not yet wired into the main runtime pipeline — research prototype. Exposed via the Kafka worker for subscribers that want it.

---

## Flink jobs (`flink_jobs.py`)

Apache Flink stream-processing topology for the Phase 2 cross-tenant analytics. Computes:
- Per-corridor 1h/24h/7d failure-rate moving averages
- Per-BIC velocity signals (feeds C6's cross-licensee aggregation)
- Stress-regime cascade alerts

Deployed in the `streaming-flink` profile of `scripts/deploy_staging_self_hosted.sh`. Requires a Flink cluster — not part of the default local staging.

---

## Kafka topics

All topics defined in `lip/c5_streaming/kafka_config.py`:

| Topic | Purpose | Retention |
|-------|---------|-----------|
| `lip.events.raw` | Input to C5 — raw pacs.002 messages from licensee bank | 7 days |
| `lip.events.normalised` | Output from C5 — `NormalizedEvent` protobuf; input to C1 | 7 days |
| `lip.events.dlq` | Dead-letter queue for malformed events | 30 days |
| `lip.decisions.audit` | **7-year retention** — regulatory decision log | 7 years |
| `lip.c3.repayment` | Settlement + repayment events | 90 days |
| `lip.c7.offers` | Loan offer lifecycle | 90 days |
| `lip.stress.regime` | Stress regime alerts | 30 days |
| `lip.c6.aml_flag` | AML velocity / sanctions flags | 90 days |
| `lip.regulatory.nav` | Hourly NAV snapshots for the regulatory data product | 7 years |
| `lip.test.normalised` | Test-traffic normalised events | 1 day |

Run `bash scripts/init_topics.sh` against a fresh Redpanda/Kafka cluster to create them all.

---

## Consumers and producers

| Who | Role | Topic |
|-----|------|-------|
| Bank SWIFT gateway | producer | `lip.events.raw` |
| C5 Go consumer | consumer + producer | raw → normalised |
| C1 / C4 / C6 / C7 (via runtime pipeline) | consumer | `lip.events.normalised` |
| C3 Settlement monitor | consumer | (in-process) |
| C7 Execution agent | producer | `lip.c7.offers`, `lip.decisions.audit` |
| C9 analytics job | consumer | `lip.regulatory.nav` |
| P10 Regulatory data | consumer | `lip.decisions.audit`, `lip.regulatory.nav` |

---

## Redis config (`redis_config.py`)

Canonical Redis key prefixes + TTLs:

| Prefix | Purpose | TTL |
|--------|---------|-----|
| `lip:c6:velocity:` | Per-entity velocity rolling windows | 24h |
| `lip:c6:structuring:` | StructuringDetector per-entity tenant sets | 7d |
| `lip:c3:active_loans:` | C3 active loan registry | maturity + 45d buffer |
| `lip:c1:corridor_embedding:` | CorridorEmbeddingPipeline cache | 30d |
| `lip:uetr:dedup:` | UETRTracker dedup set | `UETR_TTL_BUFFER_DAYS = 45d` |
| `lip:c7:kill_switch:` | Kill switch persisted state | no TTL (manual reset) |

---

## Load testing (`load_test/`)

`load_test/locustfile.py` — Locust-based load generator with realistic BIC distributions (uses real-looking BIC templates like `DEUTDEDBFRA`, `CHASUS33XXX`). Used by `benchmark_pipeline.py` for the 94ms SLO validation.

Run against local staging:
```bash
locust -f lip/c5_streaming/load_test/locustfile.py \
    --host http://lip-api.lip-staging.svc.cluster.local:8080 \
    --users 100 --spawn-rate 10
```

---

## What C5 does NOT do

- **Does not score the payment** — C1 does that. C5 produces normalised events; scoring happens downstream.
- **Does not classify dispute** — C4 does that, on the narrative field.
- **Does not validate sanctions** — C6 does that.
- **Does not talk to the loan offer router** — that is C7. C5 is upstream of everything.

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § step 1 ("C5 normalises the raw event")
- **Spec** — [`../specs/BPI_C5_Component_Spec_v1.0_Part1.md`](../specs/BPI_C5_Component_Spec_v1.0_Part1.md), [`Part 2`](../specs/BPI_C5_Component_Spec_v1.0_Part2.md)
- **Migration** — [`../specs/c5_kafka_consumer_migration.md`](../specs/c5_kafka_consumer_migration.md)
- **CBDC research** — [`../../models/cbdc-protocol-research.md`](../../models/cbdc-protocol-research.md)
- **Canonical schemas** — `lip/common/schemas.py`
