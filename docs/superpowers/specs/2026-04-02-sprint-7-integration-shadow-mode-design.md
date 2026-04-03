# Sprint 7 Design Spec: Integration & Shadow Mode

**Date:** 2026-04-02
**Sprint:** 7 of 8 (P10 Regulatory Data Product)
**Blueprint ref:** P10-v0-Implementation-Blueprint, Section 8 — Consolidated Engineering Timeline
**Branch:** `codex/default-execution-protocol`
**Baseline:** 2230 passed, 4 failed (pre-existing C2), 32 skipped

---

## 1. Objective

Wire all P10 modules (Sprints 1-6) into a working end-to-end pipeline and validate it with synthetic multi-bank data in shadow mode. No external publishing; no infrastructure dependencies.

**Blueprint performance targets:**
- API corridor query response: < 500ms
- Stress test simulation: < 30s
- Full pipeline (events -> report): < 5s at shadow scale

---

## 2. Architecture Decision

**Chosen:** Approach A — In-process shadow runner with synthetic data.

**Rationale (team consensus):**
- **NOVA:** Kafka wiring is mechanical plumbing. Proving the data flow is correct is the hard part — do that first.
- **CIPHER:** Shadow mode must not touch any real bank data. In-process with synthetic data is the safest posture.
- **QUANT:** Performance targets are meaningful only with reproducible data. Seeded synthetic generation gives us that.
- **FORGE:** No Redpanda/Kafka dependency means tests run in CI without infra provisioning. Sprint 8 is explicitly "validation & audit prep" — infrastructure integration belongs there.

**Rejected:**
- Approach B (Kafka shadow topic) — adds infra dependency with no logic validation benefit.
- Approach C (full production mode) — premature; no bank feeds exist yet.

---

## 3. New Components

### 3.1 TelemetryCollector

**File:** `lip/p10_regulatory_data/telemetry_collector.py`
**Purpose:** Aggregates raw `NormalizedEvent` streams into `TelemetryBatch` objects (hourly buckets, per-bank).

```
NormalizedEvent (C5) --[filter: telemetry_eligible=True]--> TelemetryCollector --> TelemetryBatch[]
```

**Class:** `TelemetryCollector`

**Constructor:**
- `salt: bytes` — HMAC signing key for batch integrity
- `bucket_hours: int = P10_TIMESTAMP_BUCKET_HOURS` (default 1)

**State:**
- `_accumulators: dict[tuple[str, str, str], _CorridorAccumulator]` — keyed by `(bank_hash, corridor, period_label)`
- Each `_CorridorAccumulator` tracks: total_payments, failed_payments, failure_class_counts (dict), amount_bucket_counts (dict), settlement_hours (list for p95), stress flags

**Methods:**
- `ingest(event: NormalizedEvent) -> bool` — Returns False if filtered (telemetry_eligible=False). Otherwise: hashes `sending_bic` with SHA-256 + salt, derives corridor from currency pair, computes period label from timestamp, increments accumulator counters. Classifies rejection code via the same hardcoded BLOCK set used in event_normalizer (avoids circular import). Maps amount to P10_AMOUNT_BUCKETS.
- `flush(period_start: datetime, period_end: datetime) -> list[TelemetryBatch]` — Drains all accumulators matching the time window, builds `TelemetryBatch` per (bank_hash, period), HMAC-signs each batch, resets drained accumulators. Returns empty list if nothing to flush.
- `pending_count -> int` — Property: number of events accumulated but not yet flushed.

**Corridor derivation:** `"{sending_currency}-{receiving_currency}"` extracted from `event.currency` field. For single-currency events (domestic), corridor is `"{currency}-{currency}"`. The currency_pair is derived from the event's currency field and the corridor conventions already established in CorridorStatistic.

**Amount bucket classification:** Uses `P10_AMOUNT_BUCKET_THRESHOLDS` from constants. Amounts are compared as float (sufficient precision for bucket boundaries at 10K/100K/1M/10M).

**Failure class determination:** Uses the same hardcoded `_BLOCK_REJECTION_CODES` frozenset as event_normalizer.py (12 ISO 20022 codes). For non-BLOCK codes, maps to CLASS_A/B/C using a lightweight lookup (AC01/AC04/AC06 -> CLASS_A, CURR/AM04/AM05 -> CLASS_B, etc.). Unknown codes default to CLASS_B (safe — longest maturity window).

**Thread safety:** Not thread-safe. Callers must synchronize externally if used from multiple threads. In shadow mode, single-threaded by design.

### 3.2 ShadowPipelineRunner

**File:** `lip/p10_regulatory_data/shadow_runner.py`
**Purpose:** Orchestrates the full P10 pipeline on synthetic data. Proves all modules connect.

**Class:** `ShadowPipelineRunner`

**Constructor:**
- `salt: bytes` — passed to TelemetryCollector
- `anonymizer: RegulatoryAnonymizer` — pre-configured (k, epsilon, budget)
- `risk_engine: SystemicRiskEngine` — pre-constructed
- `service: RegulatoryService | None = None` — optional, for API-layer integration tests

**Method:** `run(events: list[NormalizedEvent], period_start: datetime | None = None, period_end: datetime | None = None) -> ShadowRunResult`

**Pipeline stages (timed individually):**
1. **Collect** — Feed all events into `TelemetryCollector.ingest()`. Track ingested/filtered counts.
2. **Flush** — `collector.flush(period_start, period_end)` -> `list[TelemetryBatch]`
3. **Anonymize** — `anonymizer.anonymize_batch(batches)` -> `list[AnonymizedCorridorResult]`
4. **Ingest** — `risk_engine.ingest_results(results)`
5. **Report** — `risk_engine.compute_risk_report()` -> `SystemicRiskReport`
6. **Verify** — `create_versioned_report(report)` + `verify_report_integrity()` — confirms hash integrity

Each stage's wall-clock time captured via `time.perf_counter()`.

**Dataclass:** `ShadowRunResult` (frozen)
- `report: SystemicRiskReport`
- `versioned_report: VersionedReport`
- `events_ingested: int`
- `events_filtered: int`
- `batches_produced: int`
- `corridors_analyzed: int`
- `corridors_suppressed: int`
- `privacy_budget_consumed: float`
- `timings: dict[str, float]` — keys: "collect_ms", "flush_ms", "anonymize_ms", "ingest_ms", "report_ms", "verify_ms", "total_ms"
- `integrity_verified: bool`

### 3.3 Synthetic Multi-Bank Data Generator

**File:** `lip/p10_regulatory_data/shadow_data.py`
**Purpose:** Generates realistic NormalizedEvent streams for shadow mode testing.

**Function:** `generate_shadow_events(n_banks: int = 5, n_events_per_bank: int = 2000, corridors: list[str] | None = None, failure_rate: float = 0.08, stressed_corridor: str | None = "EUR-USD", stressed_rate: float = 0.15, seed: int = 42) -> list[NormalizedEvent]`

**Default corridors (8):** EUR-USD, GBP-EUR, USD-JPY, EUR-GBP, USD-CAD, GBP-USD, EUR-JPY, CAD-USD

**Synthetic BICs:** Generated as `"BANK{i:02d}XXXX"` (e.g., BANK01XXXX through BANK05XXXX). These are obviously synthetic — no collision with real SWIFT BICs.

**Event distribution per bank:**
- Events uniformly distributed across corridors (±20% random variation)
- Base failure rate: 8% (configurable)
- Failure class distribution: 50% CLASS_A, 30% CLASS_B, 15% CLASS_C, 5% BLOCK
- One stressed corridor at elevated rate (default 15% on EUR-USD)
- Amount distribution: log-normal, median $50K, matching BIS CPMI calibration
- ~2% of events marked telemetry_eligible=False (test/sandbox)
- Timestamps: spread across a 1-hour window (single period)

**Rejection code assignment:** Failed events get a random code from the appropriate class (CLASS_A: AC01/AC04/AC06, CLASS_B: CURR/AM04/AM05, CLASS_C: AGNT/ARDT, BLOCK: from the 12-code set). Non-failed events get rejection_code=None.

**Deterministic:** Seeded RNG ensures reproducible results for CI stability.

---

## 4. Integration Test Plan

### 4.1 test_p10_shadow_pipeline.py (NEW — ~24 tests)

**TestTelemetryCollector** (8 tests):

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_eligible_event_produces_batch` | Single eligible event → flush returns 1 batch with 1 corridor stat |
| 2 | `test_ineligible_event_filtered` | `telemetry_eligible=False` → ingest returns False, flush returns empty |
| 3 | `test_amount_bucket_boundaries` | $9,999 → "0-10K", $10,000 → "10K-100K", $10M → "10M+" |
| 4 | `test_corridor_from_currency` | EUR event with EUR sending → "EUR-EUR" corridor |
| 5 | `test_multiple_banks_separate_batches` | 2 BICs → flush returns 2 batches |
| 6 | `test_flush_clears_accumulators` | flush → flush again → empty |
| 7 | `test_batch_hmac_present` | Every flushed batch has non-empty hmac_signature |
| 8 | `test_failure_class_distribution` | BLOCK code → failure_class_distribution["BLOCK"] incremented |

**TestShadowPipelineEndToEnd** (8 tests):

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_full_pipeline_produces_report` | 10K events → non-None SystemicRiskReport |
| 2 | `test_all_corridors_present` | 8 corridors in report (5 banks >= k=5, none suppressed) |
| 3 | `test_stressed_corridor_elevated` | EUR-USD failure_rate > other corridors |
| 4 | `test_privacy_budget_consumed` | privacy_budget_consumed > 0.0 |
| 5 | `test_timings_populated` | All 7 timing keys present, all > 0 |
| 6 | `test_filtered_events_counted` | events_filtered ≈ 2% of total (±1%) |
| 7 | `test_report_integrity_verified` | integrity_verified is True |
| 8 | `test_sequential_runs_accumulate_trends` | 3 runs → trend history length == 3 for each corridor |

**TestPerformanceTargets** (3 tests):

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_corridor_query_under_500ms` | RegulatoryService.get_corridor_snapshots() < 500ms after shadow population |
| 2 | `test_stress_test_under_30s` | RegulatoryService.run_stress_test() < 30s |
| 3 | `test_full_pipeline_under_5s` | ShadowPipelineRunner.run(10K events) total_ms < 5000 |

**TestCircularExposureIntegration** (1 test):

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_circular_exposure_from_shadow_graph` | Build BICGraphBuilder from shadow events → detect_circular_exposures returns results when cycle exists in synthetic topology |

**TestAPIWithShadowData** (4 tests — added to test_p10_regulator_subscription.py):

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_corridors_endpoint_after_shadow` | GET /corridors returns non-empty after shadow run populates engine |
| 2 | `test_trend_endpoint_after_shadow` | GET /corridors/{id}/trend returns data points |
| 3 | `test_generate_report_after_shadow` | POST /reports/generate → 200 with valid report_id |
| 4 | `test_metadata_freshness_after_shadow` | GET /metadata shows recent data_freshness timestamp |

**Total: 24 new tests.**

---

## 5. File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `lip/p10_regulatory_data/telemetry_collector.py` | **NEW** | TelemetryCollector class (~150 lines) |
| `lip/p10_regulatory_data/shadow_runner.py` | **NEW** | ShadowPipelineRunner + ShadowRunResult (~120 lines) |
| `lip/p10_regulatory_data/shadow_data.py` | **NEW** | generate_shadow_events() (~100 lines) |
| `lip/p10_regulatory_data/__init__.py` | **EDIT** | Export TelemetryCollector, ShadowPipelineRunner, ShadowRunResult |
| `lip/tests/test_p10_shadow_pipeline.py` | **NEW** | 20 integration tests |
| `lip/tests/test_p10_regulator_subscription.py` | **EDIT** | +4 API integration tests |

---

## 6. Data Flow Diagram

```
NormalizedEvent[] (from DGEN / C5)
       |
       | [telemetry_eligible filter]
       v
TelemetryCollector.ingest()
       |
       | [hourly flush]
       v
TelemetryBatch[] (per-bank, HMAC-signed)
       |
       v
RegulatoryAnonymizer.anonymize_batch()
       |
       | [hash -> k-anonymity -> Laplace noise]
       v
AnonymizedCorridorResult[]
       |
       v
SystemicRiskEngine.ingest_results()
       |
       v
SystemicRiskEngine.compute_risk_report()
       |
       v
SystemicRiskReport
       |
       v
create_versioned_report() + verify_report_integrity()
       |
       v
VersionedReport (cached in RegulatoryService)
       |
       v
API endpoints: /corridors, /trend, /reports, /stress-test, etc.
```

---

## 7. Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| k-anonymity suppresses all corridors (< 5 banks) | None | Shadow data generator uses n_banks=5 (exactly k), and default k=5 |
| Privacy budget exhaustion during multi-run tests | Low | Each test creates fresh anonymizer instance; budget_per_cycle=5.0 is ample for ~10 queries |
| Circular import from TelemetryCollector importing rejection taxonomy | Low | Use same hardcoded BLOCK frozenset pattern as event_normalizer.py (proven in Sprint 6) |
| Performance test flakiness in CI | Medium | Use generous margins (500ms target tested at 2000ms ceiling); mark with pytest.mark.slow if needed |
| TelemetryCollector corridor derivation doesn't match existing CorridorStatistic conventions | Low | Derive corridor from currency field using same "{SEND}-{RECV}" format already used in telemetry_schema tests |

---

## 8. What This Sprint Does NOT Do

- No Kafka/Redpanda consumer wiring (Sprint 8 / bank pilot)
- No real bank data ingestion
- No external API publishing
- No load testing at production scale (100 concurrent queries — Sprint 8)
- No security penetration testing (Sprint 8)
- No formal privacy audit documentation (Sprint 8)

---

## 9. Success Criteria

1. Full pipeline runs end-to-end: NormalizedEvent -> SystemicRiskReport
2. All 8 corridors present in report (no spurious k-anonymity suppression)
3. Stressed corridor correctly identified with elevated failure rate
4. Privacy budget accounting works across sequential runs
5. Report integrity hash verification passes
6. Performance targets met: corridor < 500ms, stress < 30s, pipeline < 5s
7. API endpoints serve data populated by shadow pipeline
8. 24 new tests pass; total Sprint 7 test count: ~24
9. Zero ruff errors
10. No new test regressions (2230+ pass baseline maintained)
