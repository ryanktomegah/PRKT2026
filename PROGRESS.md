# LIP Project — Progress Tracker

> Always update this file at the end of every session so the next session can resume without
> reading git history. Record: what was done, what is next, and any blockers.

---

## Current Status: 2026-03-13

### Last Session Work
- **CI Fix**: Fixed `RuntimeError: cannot set number of interop threads after parallel work
  has started` — both `test_c1_torch.py` and `test_c1_graphsage_neighbors.py` now wrap
  `torch.set_num_interop_threads(1)` in `try/except RuntimeError`. Committed `cee2a44`,
  pushed to main. CI run `23024495328` triggered — monitor for green.

- **Client Perspective Analysis**: Completed `CLIENT_PERSPECTIVE_ANALYSIS.md` (842 lines).
  Examines LIP's architecture from the perspective of every external stakeholder type.
  Identified **5 Tier-1 pre-launch blockers** and **16 total gaps**.

---

## Test Suite Status (as of `cee2a44`)

| Metric | Value |
|--------|-------|
| Tests passing (local) | 1,010 |
| Coverage | 92%+ |
| Ruff errors | 0 |
| Last CI result | Failure (`f8df467`) — fixed in `cee2a44`, CI in progress |

---

## Module Completion

| Component | Status | Notes |
|-----------|--------|-------|
| C1 Failure Classifier | ✅ Complete | val_AUC=0.9998 on synthetic. Real-world target 0.85 needs pilot SWIFT data (QUANT sign-off) |
| C2 PD Model | ✅ Complete | Tier 1/2/3 routing, 300 bps floor, LGD corridors |
| C3 Repayment Engine | ✅ Complete | UETR TTL, 5 rails, buffer P95 tiers, idempotent SETNX |
| C4 Dispute Classifier | ✅ Complete | FN rate 1%, prefilter FP rate 4%. LLM backend = mock (needs production backend) |
| C5 Streaming | ✅ Complete | Kafka worker, Flink jobs, event normalizer |
| C6 AML Velocity | ✅ Complete | Sanctions, velocity caps, salt rotation |
| C7 Execution Agent | ✅ Complete | Kill switch, human override, degraded mode, decision log |
| C8 License Manager | ✅ Complete | HMAC token, boot validation |

---

## Critical Gaps Identified (from CLIENT_PERSPECTIVE_ANALYSIS.md)

### TIER 1 — Pre-Launch Blockers (fix before any pilot bank discussion)

| Gap | Description | Next Engineering Action |
|-----|-------------|------------------------|
| GAP-01 | **No loan acceptance protocol** — LoanOffer generated with no delivery/acceptance mechanism | Design `LoanOfferDelivery` webhook + `LoanOfferAcceptance` callback schema |
| GAP-02 | **AML velocity caps unscalable** — $1M/entity/24h blocks institutional SWIFT flow | Add `aml_dollar_cap_usd`, `aml_count_cap` to license token; read from LicenseeContext in C6 |
| GAP-03 | **No enrolled borrower registry** — loans made to BICs with no signed framework agreement | Build `BorrowerRegistry`, wire as C7 first-gate check, add `BORROWER_NOT_ENROLLED` terminal state |
| GAP-04 | **No retry detection** — manual payment retries cause double-funding | Build Redis-backed `RetryDetector` with 30-min tuple window in C5 |
| GAP-05 | **No BPI royalty collection** — royalty calculated but never transferred to BPI | Monthly batch `BPIRoyaltySettlement` schema + trigger |
| GAP-06 | **No SWIFT message spec for bridge disbursement** — beneficiary cannot reconcile incoming funds | Define pacs.008 template with original UETR in remittance info |
| GAP-17 | **Disbursement amount not anchored to original payment** — `agent.py:125` reads `payment_context.get("loan_amount", "0")` with no validation against original payment amount. Default is `"0"`. Silent failure risk. | Add `original_payment_amount_usd` to NormalizedEvent; validate in `_build_loan_offer` that `loan_amount == original_payment_amount_usd ± $0.01` |

### TIER 2 — First-Month Operational (fix before first live payment)

| Gap | Description |
|-----|-------------|
| GAP-07 | No portfolio reporting API for MLO |
| GAP-08 | Human override timeout outcome undefined |
| GAP-09 | Calendar-day maturities misfire on non-business days |
| GAP-10 | No governing law / jurisdiction field on LoanOffer |
| GAP-11 | Thin-file Tier 3 for creditworthy established banks |
| GAP-12 | FX risk undefined for cross-currency corridors |

### TIER 3 — Full Commercial Readiness

| Gap | Description |
|-----|-------------|
| GAP-13 | No customer-facing notification framework |
| GAP-14 | No regulatory reporting format (DORA, SR 11-7) |
| GAP-15 | No BPI admin / multi-tenant monitoring |
| GAP-16 | Partial settlement handling undefined |

---

## Immediate Next Engineering Tasks (ordered)

1. **GAP-01**: `LoanOfferDelivery` webhook + acceptance API — this unblocks all pipeline validation
2. **GAP-02**: Licensee-configurable AML caps via license token
3. **GAP-03**: `BorrowerRegistry` + C7 first-gate check + `BORROWER_NOT_ENROLLED` state
4. **GAP-05**: `BPIRoyaltySettlement` monthly batch mechanism
5. **GAP-17**: `original_payment_amount_usd` in NormalizedEvent + validation in `_build_loan_offer`
6. **Stress Regime Detector**: `StressRegimeDetector` in C5 (corridor_failure_rate_1h > 3× baseline triggers conservative mode)
7. **GAP-04**: Redis-backed `RetryDetector` (30-min tuple window)

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
3. Bank registers each client's BIC in Enrolled Borrower Registry → C7 permits offers

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

*Last updated: 2026-03-13 — Session: CI fix + Client Perspective Analysis complete*
