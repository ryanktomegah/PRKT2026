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

## CBDC + Project Nexus normalisers (Phases A-E, 2026-04-25)

Multi-CBDC support is **end-to-end wired** — events flow from raw rail message through dispatcher → rail-specific normaliser → `NormalizedEvent` → pipeline → rail-aware C7 offer construction. Five CBDC-class rails are supported across three normalizer modules:

| Rail | Module | Class | Maturity buffer | Real-world status (April 2026) |
|---|---|---|---|---|
| `CBDC_ECNY` | `cbdc_normalizer.py` (`CBDCNormalizer.normalize_ecny`) | retail | 4h | PBoC e-CNY |
| `CBDC_EEUR` | `cbdc_normalizer.py` (`CBDCNormalizer.normalize_eeur`) | retail | 4h | ECB experimental e-EUR |
| `CBDC_SAND_DOLLAR` | `cbdc_normalizer.py` (`CBDCNormalizer.normalize_sand_dollar`) | retail | 4h | CBB Sand Dollar |
| `CBDC_MBRIDGE` | `cbdc_mbridge_normalizer.py` (`MBridgeNormalizer`) | wholesale multi-leg PvP | 4h | Post-BIS-exit (Oct 2024); 5 central banks operate; ~$55.5B settled, e-CNY = 95% of volume |
| `CBDC_NEXUS` | `nexus_normalizer.py` (`NexusNormalizer`) | wholesale instant | 4h | NGP Singapore-incorporated 2025; **PHASE-2-STUB** — onboarding mid-2027 per BSP |

### Failure-code mapping (`cbdc_normalizer.CBDC_FAILURE_CODE_MAP`)

CBDC-specific codes are translated to ISO 20022 equivalents at normalisation time so downstream components (C7 compliance gate, rejection taxonomy, C1 classifier) operate on a uniform code space without CBDC-specific branching:

| CBDC code | ISO 20022 | Class | Meaning |
|---|---|---|---|
| `CBDC-SC01` | `AC01` | A | Smart-contract execution failure |
| `CBDC-SC02` | `AC04` | A | Smart-contract timeout |
| `CBDC-SC03` | `ED05` | A | Contract validation failure |
| `CBDC-KYC01` | `RR01` | **BLOCK** | KYC identity verification failure |
| `CBDC-KYC02` | `RR02` | **BLOCK** | KYC address verification failure |
| `CBDC-LIQ01` | `AM04` | B | Liquidity pool insufficient |
| `CBDC-LIQ02` | `AM02` | B | Amount exceeds wallet limit |
| `CBDC-FIN01` | `TM01` | B | Finality timeout |
| `CBDC-FIN02` | `DT01` | B | Settlement date mismatch |
| `CBDC-INT01` | `FF01` | A | Interoperability bridge failure |
| `CBDC-INT02` | `NARR` | C | Cross-chain protocol error (no direct ISO equivalent) |
| `CBDC-CRY01` | `DS02` | A | Signature validation failure |
| `CBDC-CRY02` | `DS02` | A | Certificate chain error |
| `CBDC-NET01` | `MS03` | C | Network congestion delay |
| `CBDC-CF01` | `AM04` | B | Consensus not reached (mBridge) |
| `CBDC-CB01` | `FF01` | A | Cross-chain bridge failure (mBridge) |

EPG-20/21: KYC failures map to the *generic* `RR01`/`RR02` codes — **not** to AML/SAR-tagged values. The CBDC normalizer source is patent-language-scrubbed.

### mBridge multi-leg PvP

mBridge transactions can settle **up to 5 currency legs atomically** (CNY/HKD/THB/AED/SAR). On failure, `MBridgeNormalizer` selects the failed leg as the primary `NormalizedEvent`; sister legs and bridge metadata (`consensus_round`, `finality_seconds`, `atomic_settlement_id`) are preserved in `raw_source` for forensic / regulatory reporting.

Selection rule:
1. If `msg['failed_leg_index']` is present and in range, use that leg.
2. Else, find the first leg with `status == 'FAILED'`.
3. If no failed leg, raise `ValueError` (atomic PvP success has no bridge-lending implications).

### Schema status

- e-CNY / e-EUR / Sand Dollar: schemas modelled from public PBoC / ECB / CBB documentation; tests cover the modelled shape.
- mBridge: schema modelled from BIS Innovation Hub published material — the formal production message schema has not been released. Module docstring documents this; swap when published.
- Nexus: `PHASE-2-STUB`. ISO 20022 native — uses standard `ExternalStatusReason1Code` codes (no proprietary map needed). Schema modelled from BIS Nexus blueprint (July 2024); keep this path stubbed until NGP publishes the formal ISO 20022 profile and onboarding schemas.

### Dispatcher routing (`event_normalizer.EventNormalizer.normalize`)

```python
upper = rail.upper()
if upper == "CBDC_MBRIDGE":  → MBridgeNormalizer
if upper == "CBDC_NEXUS":    → NexusNormalizer
if upper.startswith("CBDC_"):→ CBDCNormalizer
else:                        → in-class SWIFT/FedNow/RTP/SEPA handlers
```

Unknown rails raise `ValueError` — never silently fall through.

### Cross-rail handoff detection (Phase C)

`UETRTracker.register_handoff(parent_uetr, child_uetr, child_rail)` links an upstream cross-border SWIFT UETR to a downstream domestic-rail UETR (FedNow/RTP/SEPA) with a 30-minute TTL. When the child fails, `pipeline.process()` emits a `DOMESTIC_LEG_FAILURE` outcome and adds `parent_uetr` to the loan_offer dict for cross-rail audit. Patent angle: P9 continuation candidate ("detecting settlement confirmation from disparate payment network rails for a single UETR-tracked payment"). See `Master-Action-Plan-2026.md:378`. Filing remains frozen per CLAUDE.md non-negotiable #6.

### Tests

- `test_cbdc_normalizer.py` — 38 tests (per-rail normalisation, code mapping, dispatcher, EPG-21 patent-language scrub)
- `test_cbdc_mbridge_normalizer.py` — 15 tests (multi-leg parsing, failed-leg selection, dispatcher, patent-language scrub with currency-code allowance)
- `test_nexus_stub.py` — 7 tests (smoke + dispatcher routing)
- `test_cross_rail_handoff.py` — 11 tests (TTL expiry, rail validation, pipeline routing for `DOMESTIC_LEG_FAILURE`)
- `test_cbdc_e2e.py` — 12 tests (pipeline E2E for e-CNY, e-EUR, Sand Dollar, mBridge, FedNow, regression on SWIFT)

### Spec + ADR

- Design: `docs/superpowers/specs/2026-04-25-cbdc-normalizer-end-to-end-design.md`
- Plan: `docs/superpowers/plans/2026-04-25-cbdc-normalizer-end-to-end.md`
- ADR: `docs/engineering/decisions/ADR-2026-04-25-rail-aware-maturity.md`
- Research: `docs/models/cbdc-protocol-research.md`

---

## Stress regime detector (`stress_regime_detector.py`)

Monitors corridor failure rates in real-time. If the short-term (current) failure rate exceeds the long-term (baseline) by a multiplier (default 3.0), the corridor is declared a `STRESS_REGIME`.

When in stress:
1. Triggers human review for all offers in the stressed corridor (EU AI Act Art.14 circuit breaker)
2. Alerts the licensee bank's risk desk via Kafka topic `lip.stress.regime`

Wired into the real runtime pipeline via `build_runtime_pipeline()` — enabled by default, disable with `LIP_STRESS_DETECTOR_DISABLED=1`. Configurable via `LIP_STRESS_BASELINE_SECONDS`, `LIP_STRESS_CURRENT_SECONDS`, `LIP_STRESS_MULTIPLIER`, `LIP_STRESS_MIN_TXNS` env vars.

### Rail-aware window tuning (Phase A follow-up, 2026-04-26)

The constructor defaults (24h baseline / 1h current / 20 min txns) are calibrated for SWIFT/SEPA where loans run 3–21 days. On sub-day rails the legacy windows would detect a spike only after the loan has nearly settled — exactly when the circuit breaker most needs to fire.

`RAIL_STRESS_WINDOWS` in `lip/common/constants.py` provides per-rail tuning:

| Rail | Baseline | Current | Min txns | Rationale |
|---|---|---|---|---|
| `SWIFT`, `SEPA` | 24h | 1h | 20 | Legacy default |
| `FEDNOW`, `RTP` | 1h | 5min | 10 | 24h tenor |
| `CBDC_ECNY`, `CBDC_EEUR`, `CBDC_SAND_DOLLAR` | 30min | 5min | 5 | 4h tenor |
| `CBDC_MBRIDGE` | 30min | 3min | 5 | 4h tenor + sharper PvP signal |
| `CBDC_NEXUS` | 5min | 30s | 3 | 60s finality |

Detector API gained an optional `rail` kwarg on `record_event()`, `is_stressed()`, `check_and_emit()`, `get_rates()`. When `rail` is provided, the detector keeps a separate history bucket per `(rail, corridor)` pair and uses the rail's tuned windows for evaluation. Unknown rails (or `rail=None` legacy callers) fall back to constructor defaults — deliberately *not* sub-day, so a future rail without tuning gets the safer SWIFT-shaped windows.

Pipeline wiring: `pipeline.py:_stress_detector.record_event(corridor, True, rail=event.rail)`. C7 wiring: `agent.py:stress_detector.is_stressed(corridor, rail=rail)` in both call sites (line 350 and line 658). Emitted `StressRegimeEvent` payloads now include `rail` when the caller supplied one, so downstream consumers can distinguish `CBDC_MBRIDGE::CNY_HKD` stress from `SWIFT::CNY_HKD` stress.

ADR: `docs/engineering/decisions/ADR-2026-04-26-rail-aware-stress-detection.md`

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
