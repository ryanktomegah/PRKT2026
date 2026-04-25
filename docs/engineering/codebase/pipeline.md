# `lip/pipeline.py` — End-to-End Orchestrator

> **The single entry point for reading the LIP code.** If you want to understand how a payment becomes a bridge loan, start here. Every other module is called from this file (directly or one hop away).

**Source:** `lip/pipeline.py`
**Implements:** Algorithm 1 (Architecture Specification v1.2 § 3)
**Canonical spec:** [`docs/engineering/specs/BPI_Architecture_Specification_v1.2.md`](../specs/BPI_Architecture_Specification_v1.2.md)

---

## Purpose

`pipeline.py` implements **Algorithm 1**, the end-to-end loop that turns a single ISO 20022 `pacs.002` payment-failure event into either (a) a delivered bridge-loan offer awaiting ELO acceptance, or (b) a refused outcome with a full audit trail. Funding-side effects happen only after the ELO accepts the delivered offer.

It is the **only** place in the codebase where C1, C2, C3, C4, C5, C6, and C7 are composed together. Every other module either (a) implements one of those components, (b) provides shared infrastructure that they all use, or (c) supports them with data, configuration, or governance.

## Algorithm 1 (as implemented)

For each payment event:

1. **C5 normalises the raw event** (done by the caller; `pipeline.py` accepts a `NormalizedEvent`)
2. **C1** extracts features and predicts `failure_probability`
3. If `failure_probability >= τ*` (τ\* = 0.110, see canonical constants):
   - **C4** checks for dispute (hard block)
   - **C6** checks AML velocity, sanctions, and anomaly (hard block; anomaly → human review per EPG-18)
   - **C2** computes PD + `fee_bps` (annualised, 300 bps floor)
   - **Decision Engine** aggregates signals and generates a `LoanOffer`
   - **C7** receives the offer, applies kill-switch / KMS / borrower-registry / stress-regime checks
   - If C7 offers: `PipelineResult.outcome = OFFERED` while the offer awaits ELO acceptance
   - If the ELO accepts: `OfferDeliveryService` calls `LIPPipeline.finalize_accepted_offer()`, C6 records velocity, C3 registers the active loan, and portfolio risk exposure is added
4. Returns a `PipelineResult` with full audit trail (`outcome`, `compliance_hold`, `decision_log_entries`, latency telemetry)

The `τ*` constant (`FAILURE_PROBABILITY_THRESHOLD = 0.110`) is documented inline in `pipeline.py` with the calibration provenance: F2-optimal threshold from C1 retraining on a 10M corpus, ECE = 0.0687 post-isotonic calibration, validated 2026-03-21. **It is locked** — see [`../../legal/decisions/README.md`](../../legal/decisions/README.md) and `CLAUDE.md` § Canonical Constants.

## Where it sits

```
caller (C5 normaliser, test harness, or API router)
   │
   ▼
NormalizedEvent
   │
   ▼
┌──────────────────────────────────────────────┐
│  pipeline.py — LIPPipeline.process_event()   │
│                                              │
│  C1 → [τ* gate] → C4 ∥ C6 ∥ C2 → C7 → C3     │
│                                              │
│  with audit trail, latency tracking,         │
│  payment_context propagation, UETR tracking  │
└──────────────────────────────────────────────┘
   │
   ▼
PipelineResult  (outcome, compliance_hold, decision_log, latency)
```

## Key responsibilities

- **Threshold gating** at τ\* — short-circuit before invoking expensive downstream components if `failure_probability < τ*`
- **Parallel C4 / C6 / C2** invocation where the architecture allows
- **`payment_context` propagation** — a dict carrying `sending_bic`, `receiving_bic`, `amount`, `currency`, `licensee_id`, `original_payment_amount_usd`, etc., consumed by every downstream component
- **UETR tracking** for retry detection (GAP-04) — checks `UETRTracker` before any decision and records the returned pipeline outcome
- **Outcome routing** — the function that maps every internal state into one of the canonical `PipelineResult.outcome` values (`OFFERED`, `DECLINED`, `COMPLIANCE_HOLD`, `PENDING_HUMAN_REVIEW`, `BORROWER_NOT_ENROLLED`, etc.)
- **Audit trail assembly** — appends `DecisionLogEntry` records at every gate so the `PipelineResult` is fully reconstructible after the fact
- **Latency tracking** via `lip.instrumentation.LatencyTracker` against the 94 ms p99 SLO

## Cross-references

- **Per-step detail**: see each component's README in `lip/c{N}_*/README.md` and the canonical spec in [`docs/engineering/specs/BPI_C{N}_Component_Spec_v1.0*.md`](../specs/)
- **State machines**: `lip/common/state_machines.py` — `PaymentState`, `LoanState`, `PaymentStateMachine`, `LoanStateMachine`
- **Schemas**: `lip/common/schemas.py` — `LoanOffer`, `LoanOfferDelivery`, `LoanOfferAcceptance`, `LoanOfferExpiry`, `DecisionLogEntry`, `TenantContext`, `LoanState`, `OfferExpiryReason`, `RevenueRecord`
- **Result type**: `lip/pipeline_result.py` — `PipelineResult`
- **Rejection taxonomy**: `lip/c3_repayment_engine/rejection_taxonomy.py` — the BLOCK / CLASS_A / CLASS_B / CLASS_C classification of every ISO 20022 rejection code
- **Operative compliance policy**: [`../../legal/decisions/EPG-19_compliance_hold_bridging.md`](../../legal/decisions/EPG-19_compliance_hold_bridging.md) — defense-in-depth at Layer 1 (rejection_taxonomy) and Layer 2 (C7 `_COMPLIANCE_HOLD_CODES`)

## Reading order for a new developer

1. The top-of-file docstring (Algorithm 1 + three-entity role mapping: MLO / MIPLO / ELO)
2. The constants block (τ\*, dispute block classes, latency thresholds)
3. `LIPPipeline.__init__` — what the orchestrator wires up
4. `process_event()` — the main loop, top to bottom
5. The outcome-mapping helpers at the bottom of the file
6. Then jump into whichever component you need from `lip/c{N}_*/`

Do **not** modify `pipeline.py` without (a) reading the relevant component spec in [`docs/engineering/specs/`](../specs/), and (b) running the full E2E test suite (`lip/tests/test_e2e_pipeline.py` — 8 in-memory scenarios, no infrastructure required).
