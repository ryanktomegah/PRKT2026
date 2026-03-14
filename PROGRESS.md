# LIP Project — Progress Tracker

> Always update this file at the end of every session so the next session can resume without
> reading git history. Record: what was done, what is next, and any blockers.

---

- **GAP-04 COMPLETE**: Retry detection (idempotency).
  - New: `lip/common/uetr_tracker.py` — `UETRTracker` for thread-safe duplicate detection.
  - Updated `PipelineResult` (C7) to include `RETRY_BLOCKED` outcome.
  - Updated `LIPPipeline` to inject `uetr_tracker` and block duplicate UETRs.
  - Updated `lip/tests/test_e2e_latency.py` to use unique UETRs.
  - New: `lip/tests/test_gap04_retry_detection.py` — **4 integration tests, all passing**.

---

## Test Suite Status (as of GAP-04 complete)

| Metric | Value |
|--------|-------|
| Tests passing (local) | 1,082 (was 1,078 + 4 new) |
| Coverage | 92%+ |
| Ruff errors | 0 |
| Active branch | `feat/e2e-simulation-harness` |

---

## Module Completion

| Component | Status | Notes |
|-----------|--------|-------|
| C1 Failure Classifier | ✅ Complete | val_AUC=0.9998 on synthetic. |
| C2 PD Model | ✅ Complete | Tier 1/2/3 routing, 300 bps floor |
| C3 Repayment Engine | ✅ Complete | UETR TTL, 5 rails |
| C4 Dispute Classifier | ✅ Complete | FN rate 1%, prefilter FP rate 4%. |
| C5 Streaming | ✅ Complete | Kafka worker, Flink jobs |
| C6 AML Velocity | ✅ Complete | Sanctions, configurable velocity caps |
| C7 Execution Agent | ✅ Complete | offer delivery, borrower registry, **retry detection (GAP-04)** |
| C8 License Manager | ✅ Complete | caps in license token |

---

## Critical Gaps — Implementation Status

### TIER 1 — Pre-Launch Blockers

| Gap | Description | Status |
|-----|-------------|--------|
| GAP-01 | **No loan acceptance protocol** | ✅ **DONE** |
| GAP-02 | **AML velocity caps unscalable** | ✅ **DONE** |
| GAP-03 | **No enrolled borrower registry** | ✅ **DONE** |
| GAP-04 | **No retry detection** | ✅ **DONE** |
| GAP-05 | **No BPI royalty collection** | ⏳ Next |
| GAP-06 | **No SWIFT message spec for bridge disbursement** | ⏳ Pending |
| GAP-17 | **Disbursement amount not anchored** | ⏳ Pending |

### TIER 2 — First-Month Operational

| Gap | Description | Status |
|-----|-------------|--------|
| GAP-07 | No portfolio reporting API for MLO | ⏳ Pending |
| GAP-08 | Human override timeout outcome undefined | ⏳ Pending |
| GAP-09 | Calendar-day maturities misfire on non-business days | ⏳ Pending |
| GAP-10 | No governing law / jurisdiction field on LoanOffer | ⏳ Pending |
| GAP-11 | Thin-file Tier 3 for creditworthy established banks | ⏳ Pending |
| GAP-12 | FX risk undefined for cross-currency corridors | ⏳ Pending |

### TIER 3 — Full Commercial Readiness

| Gap | Description | Status |
|-----|-------------|--------|
| GAP-13 | No customer-facing notification framework | ⏳ Pending |
| GAP-14 | No regulatory reporting format (DORA, SR 11-7) | ⏳ Pending |
| GAP-15 | No BPI admin / multi-tenant monitoring | ⏳ Pending |
| GAP-16 | Partial settlement handling undefined | ⏳ Pending |

---

## Immediate Next Engineering Tasks (ordered)

1. ✅ **GAP-01** — Offer delivery and acceptance protocol (`0e7c69a`)
2. **GAP-02** — Licensee-configurable AML caps via license token
   - Add `aml_dollar_cap_usd` and `aml_count_cap` fields to `LicenseToken` / `LicenseeContext`
   - Update `VelocityChecker.check()` to accept per-call cap overrides
   - Update C7 `process_payment` to pass licensee caps from `LicenseeContext` to C6
   - Files: `lip/c8_license_manager/license_token.py`, `lip/c6_aml_velocity/velocity.py`,
     `lip/c7_execution_agent/agent.py`
3. **GAP-03** — `BorrowerRegistry` + C7 first-gate check + `BORROWER_NOT_ENROLLED` state
   - New `lip/common/borrower_registry.py`; C7 checks registry BEFORE all other logic
4. **GAP-05** — `BPIRoyaltySettlement` monthly batch mechanism
   - New `lip/common/royalty_settlement.py`; triggered from C3 repayment callback
5. **GAP-17** — `original_payment_amount_usd` in NormalizedEvent + validation in `_build_loan_offer`
6. **Stress Regime Detector** — `StressRegimeDetector` in C5 (corridor_failure_rate_1h > 3× baseline)
   - New `lip/c5_streaming/stress_regime_detector.py`
7. **GAP-04** — Redis-backed `RetryDetector` (30-min tuple window)
   - New `lip/c5_streaming/retry_detector.py`

---

## Canonical Constants (NEVER change without QUANT sign-off)

| Constant | Value |
|----------|-------|
| τ* (failure threshold) | 0.152 |
| Fee floor | 300 bps |
| Latency SLO | ≤ 94ms p99 |
| UETR TTL buffer | 45 days |
| Salt rotation | 365 days, 30-day overlap |
| Platform royalty | 15% of fee_repaid_usd |
| RETRY_DETECTION_WINDOW_MINUTES | 30 (proposed, not yet implemented) |
| STRESS_REGIME_FAILURE_RATE_MULTIPLIER | 3.0 (proposed, not yet implemented) |

---

## Fee Brackets (annualized) — For Reference

| Tier | Who | PD Range | Fee Range | Fee on $5M / 7 days | BPI Royalty (15%) |
|------|-----|----------|-----------|---------------------|-------------------|
| 1 | Investment-grade, listed | 0.5%–2% | 300–540 bps | ~$5,178 | ~$777 |
| 2 | Private co, balance sheet data | 2%–8% | 540–900 bps | ~$8,630 | ~$1,295 |
| 3 | Thin file | 8%–15% | 900–1,500 bps | ~$14,383 | ~$2,157 |

Fee is collected at repayment via C3 sweep — NEVER deducted from disbursement principal.
Receiver always receives 100% of original payment amount (GAP-17 validation enforces this).

## Three-Layer Enrollment Requirement (before first bridge loan fires)

1. Bank signs BPI License Agreement → C8 loads and validates token at boot
2. Bank obtains signed MRFA from each corporate client → authorizes automatic fee debit
3. Bank registers each client's BIC in Enrolled Borrower Registry → C7 permits offers (GAP-03)

LIP returns `BORROWER_NOT_ENROLLED` for every offer until Step 3 is complete for at
least one client. This is correct behavior. Banks must understand this before go-live.

## Key Open Decisions (requires QUANT or BPI team sign-off)

- **RETRY_DETECTION_WINDOW_MINUTES**: 30 minutes proposed. Could be 15 or 60 depending on
  observed retry latency in pilot SWIFT data.
- **STRESS_REGIME_FAILURE_RATE_MULTIPLIER**: 3.0 proposed. Needs calibration against historical
  corridor stress events.
- **GAP-05 settlement frequency**: Monthly batch recommended. Could be weekly or per-event.
- **GAP-08 timeout_action default**: DECLINE recommended (conservative). Licensee may configure OFFER.
- **GAP-12 FX risk policy**: Who denominates the bridge loan in cross-currency corridors?

---

## Documents

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Dev environment, team agents, canonical constants, key rules |
| `PROGRESS.md` | This file — session state and next actions |
| `CLIENT_PERSPECTIVE_ANALYSIS.md` | INTERNAL. 7-archetype business logic analysis, 16 gaps, scenarios |
| `README.md` | Project overview |

---

## C4 Notes
- `MockLLMBackend` has no negation awareness — FP rate 4% after prefilter step 2a
- `DISPUTE_FN_CURRENT` = 0.01 measured on negation suite (commit `3808a74`)
- Production LLM backend still needed (GPTQ quantized model or API-based)

## C1 Notes
- `val_AUC=0.9998` on 2K synthetic samples (commit `f38f0dc`) — root cause was 55/88 features
  being zero; stats enrichment fixed this
- Real-world AUC estimate: 0.82–0.88 (pending pilot with anonymised SWIFT data, QUANT sign-off)
- macOS performance note: CPU-only training ~10× slower than Linux GPU — use `eval_c1_auc_torch.py`
  for benchmarking

---

*Last updated: 2026-03-13 — Session: GAP-01 complete (offer delivery protocol, 62 tests, commit `0e7c69a`). Next: GAP-02 (AML caps).*
