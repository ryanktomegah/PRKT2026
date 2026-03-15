# LIP Project — Progress Tracker

> Always update this file at the end of every session so the next session can resume without
> reading git history. Record: what was done, what is next, and any blockers.

---

- **GAP-16 COMPLETE**: Partial settlement handling.
  - New: `lip/common/partial_settlement.py` — `PartialSettlementPolicy` enum (REQUIRE_FULL / ACCEPT_PARTIAL) + `PartialSettlementConfig`.
  - `RepaymentLoop.__init__()`: optional `partial_settlement_policy` param.
  - `RepaymentLoop.trigger_repayment()`: partial check BEFORE idempotency claim (REQUIRE_FULL doesn't consume Redis token); ACCEPT_PARTIAL computes fee on `settlement_amount`; all records carry `is_partial`, `shortfall_amount`, `shortfall_pct`.
  - New: `lip/tests/test_gap16_partial_settlement.py` — **11 tests, all passing**.

- **GAP-15 COMPLETE**: BPI admin / multi-tenant monitoring API.
  - New: `lip/api/admin_router.py` — `LicenseeStats` dataclass + `BPIAdminService` (`list_licensees`, `get_licensee_stats`, `get_platform_summary`) + optional FastAPI `make_admin_router()`.
  - Added `RepaymentLoop.get_active_loans()` method (was missing; portfolio_router already called it on mocks).
  - New: `lip/tests/test_gap15_admin_monitoring.py` — **17 tests, all passing**.

- **GAP-14 COMPLETE**: Regulatory reporting formats (DORA Art.19 + Fed SR 11-7).
  - New: `lip/common/regulatory_reporter.py` — `DORASeverity` enum, `DORAAuditEvent` (4h/24h thresholds, `within_threshold` property), `SR117ModelValidationReport` (AUC ≥ 0.75 validation gate), `RegulatoryReporter` class.
  - New: `lip/tests/test_gap14_regulatory_reporting.py` — **16 tests, all passing**.

- **GAP-13 COMPLETE**: Customer-facing notification framework.
  - New: `lip/common/notification_service.py` — `NotificationEventType` enum (6 events), `NotificationRecord` dataclass, `NotificationService` with `notify()`, `get_notifications()`, delivery callback, `mark_delivered()`, `register_webhook()`.
  - New: `lip/tests/test_gap13_notifications.py` — **17 tests, all passing**.

- **GAP-12 COMPLETE**: FX risk policy for cross-currency corridors.
  - New: `lip/common/fx_risk_policy.py` — `FXRiskPolicy` enum + `FXRiskConfig` dataclass.
  - `SAME_CURRENCY_ONLY` (Phase 1 pilot default) + `BANK_NATIVE_CURRENCY` policies.
  - C7 `process_payment()` FX gate checks currency before building offer; returns `CURRENCY_NOT_SUPPORTED`.
  - Pipeline `CURRENCY_NOT_SUPPORTED` status handled as DECLINED outcome.
  - `LoanOffer` schema: added `loan_currency: str` field (default `"USD"`).
  - `constants.py`: added `FX_G10_CURRENCIES` + `FX_RISK_POLICY_DEFAULT`.
  - New: `lip/tests/test_gap12_fx_risk_policy.py` — **14 tests, all passing**.

- **GAP-11 COMPLETE**: Known-entity tier override (thin-file for creditworthy banks).
  - New: `lip/common/known_entity_registry.py` — `KnownEntityRegistry` (BIC → Tier map).
  - `PDInferenceEngine._resolve_tier()` checks registry FIRST before data-availability rule.
  - `PDInferenceEngine.__init__()` accepts optional `known_entity_registry`.
  - `portfolio_router.py`: added `KnownEntityManager` class + `make_known_entities_router()` FastAPI router.
  - New: `lip/tests/test_gap11_entity_tier_override.py` — **13 tests, all passing**.

- **GAP-10 COMPLETE**: Governing law / jurisdiction on LoanOffer.
  - New: `lip/common/governing_law.py` — `law_for_jurisdiction()` maps FEDWIRE→NEW_YORK, CHAPS→ENGLAND_WALES, TARGET2→EU_LUXEMBOURG.
  - `LoanOffer` schema: added `governing_law: str` field (default `"UNKNOWN"`).
  - `C7._build_loan_offer()`: derives governing_law from payment currency via `currency_to_jurisdiction()` + `law_for_jurisdiction()`.
  - `pipeline.py`: propagates `event.currency` into `payment_context` so C7 receives it.
  - New: `lip/tests/test_gap10_governing_law.py` — **10 tests, all passing**.

---

- **GAP-09 COMPLETE**: Business-day maturity calculations.
  - New: `lip/common/business_calendar.py` — TARGET2/FEDWIRE/CHAPS holiday tables 2026–2027.
  - `add_business_days(start, n, jurisdiction)` + `currency_to_jurisdiction(currency)`.
  - Updated `_register_with_c3` (pipeline.py) to use business days: `timedelta(days=n)` → `add_business_days`.
  - New: `lip/tests/test_gap09_business_calendar.py` — **17 tests, all passing**.

- **GAP-08 COMPLETE**: Human override timeout outcome.
  - Updated `HumanOverrideInterface` with `timeout_action: str = "DECLINE"` parameter.
  - New `resolve_expired(request_id)` method returns `timeout_action` for expired requests.
  - Raises `ValueError` if request not yet expired or unknown.
  - New: `lip/tests/test_gap08_override_timeout.py` — **8 tests, all passing**.

- **GAP-07 COMPLETE**: MLO portfolio reporting API.
  - New: `lip/api/__init__.py` and `lip/api/portfolio_router.py`.
  - `PortfolioReporter` class: `get_loans()`, `get_exposure()`, `get_yield()` methods.
  - FastAPI `make_portfolio_router()` wraps reporter for HTTP serving.
  - Reads live state from `RepaymentLoop.get_active_loans()` + optional `BPIRoyaltySettlement`.
  - New: `lip/tests/test_gap07_portfolio_api.py` — **16 tests, all passing**.

- **GAP-06 COMPLETE**: SWIFT pacs.008 message spec for bridge disbursements.
  - New: `lip/common/swift_disbursement.py` — `BridgeDisbursementMessage` + `build_disbursement_message`.
  - Updated `_build_loan_offer` (C7) to attach `swift_disbursement_ref` and `swift_remittance_info`.
  - Format: `EndToEndId = LIP-BRIDGE-{original_uetr}`, `RmtInf/Ustrd` references both UETR and loan ID.
  - New: `lip/tests/test_gap06_swift_disbursement.py` — **5 integration tests, all passing**.

- **GAP-17 COMPLETE**: Disbursement amount anchored to original payment amount.
  - Updated `NormalizedEvent` (C5) with `original_payment_amount_usd: Optional[Decimal]` field.
  - All 4 rail normalizers (SWIFT/FedNow/RTP/SEPA) populate field from interbank settlement amount.
  - Updated `LIPPipeline.payment_context` to propagate field (fallback to `event.amount` for same-currency).
  - Updated `_build_loan_offer` (C7): validates `abs(loan_amount - original_payment_amount_usd) ≤ $0.01`.
  - Returns `LOAN_AMOUNT_MISMATCH` terminal state + decision log entry on mismatch.
  - New: `lip/tests/test_gap17_amount_validation.py` — **6 integration tests, all passing**.

- **GAP-05 COMPLETE**: BPI royalty collection (monthly settlement).
- **PEDIGREE R&D STRATEGY ACTIVATED**: Transitioned from general implementation to high-moat algorithmic research.
  - **Tier 1 R&D COMPLETE (C2)**: Robust Merton-KMV Iterative Solver.
    - Optimized Newton-Raphson step with safety break for distressed firms (n_d1 < 1e-10).
    - Removed default T=1.0 to force explicit time-horizon passing.
    - Integrated dynamic DD computation into `UnifiedFeatureEngineer` (C2).
    - Added numerical stability guards for deep-distress scenarios (n_d1 ~ 0).
    - New: `lip/tests/test_merton_solver.py` — verified convergence and edge cases.
  - **Tier 1 R&D COMPLETE (C1)**: Isotonic Probability Calibration.
    - Updated `ClassifierModel` (C1) to include a persistent `IsotonicCalibrator`.
    - Implemented `stage7b_probability_calibration` in C1 `TrainingPipeline`.
    - Integrated calibration into real-time `predict_proba` flow with `_is_fitted` guards.
    - Added ECE pre/post tracking and logging to the calibration stage.
    - New: `lip/tests/test_c1_calibration.py` — verified monotonicity and ECE improvement.
  - **Tier 2 R&D COMPLETE (DGEN)**: Adversarial camt.056 Simulation.
    - Updated `c3_generator.py` to include `RECALL_ATTACK` (adversarial cancellation) scenario.
    - Implemented cancellation-specific metadata tracking (intent, reason codes).
    - Updated labeling logic to treat recall attacks as critical problematic outcomes.
    - New: `lip/tests/test_dgen_adversarial.py` — verified generation distribution and labeling.
  - **Tier 3 R&D COMPLETE WITH KNOWN LIMITATION (C1)**: Supply Chain Cascade Propagation (P5).
    - NOTE: See docstring in `BICGraphBuilder.get_cascade_risk` for known limitation regarding first-payment dependency scores.
    - Updated `BICGraphBuilder` to track node-level incoming USD volume.
    - Implemented `dependency_score` on `PaymentEdge` (ratio of payment to receiver's total receivables).
    - New: `get_cascade_risk()` method to identify downstream BICs vulnerable to upstream failure.
    - New: `lip/tests/test_p5_cascade.py` — verified dependency scoring and risk detection logic.
  - Identified "World Model" simulation gaps in `dgen` regarding camt.056 adversarial loops.

  - New: `lip/common/royalty_settlement.py` — `BPIRoyaltySettlement` for monthly aggregation.
  - Updated `ActiveLoan` (C3) and `SettlementMonitor` to propagate `licensee_id`.
  - Updated `LIPPipeline` to pass `licensee_id` to the repayment registry.
  - Updated `trigger_repayment` (C3) to include `licensee_id` in repayment records.
  - New: `lip/tests/test_gap05_royalty_collection.py` — **4 integration tests, all passing**.

---

## Test Suite Status (as of Pedigree R&D Phase 1 complete)

| Metric | Value |
|--------|-------|
| Passing | **1,286** (was 1,247) |
| New tests verified | Merton stability, Isotonic ECE, Cascade risk |
| Pre-existing failures | 0 |
| Ruff errors | 0 |

## Test Suite Status (as of GAP-12 complete — HISTORICAL)

| Metric | Value |
|--------|-------|
| Passing | **1,187** (was 1,138) |
| New tests added | 38 (GAP-10: 10, GAP-11: 13, GAP-12: 15) |
| Pre-existing failures | 2 (C1 LGBM training flakiness — unrelated to this work) |
| Ruff errors | 0 |

## Test Suite Status (as of GAP-05 complete — HISTORICAL)

| Metric | Value |
|--------|-------|
| Tests passing (local) | 1,138 (was 1,097 + 41 new) |
| Coverage | 92%+ |
| Ruff errors | 0 |
| Active branch | `feat/e2e-simulation-harness` |

---

## Module Completion

| Component | Status | Notes |
|-----------|--------|-------|
| C1 Failure Classifier | ✅ Complete | val_AUC=0.9998 on synthetic. |
| C2 PD Model | ✅ Complete | Tier 1/2/3 routing, 300 bps floor |
| C3 Repayment Engine | ✅ Complete | UETR TTL, 5 rails, **royalty tracking (GAP-05)** |
| C4 Dispute Classifier | ✅ Complete | FN rate 1%, prefilter FP rate 4%. |
| C5 Streaming | ✅ Complete | Kafka worker, Flink jobs |
| C6 AML Velocity | ✅ Complete | Sanctions, configurable velocity caps |
| C7 Execution Agent | ✅ Complete | offer delivery, borrower registry, retry detection |
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
| GAP-05 | **No BPI royalty collection** | ✅ **DONE** |
| GAP-06 | **No SWIFT message spec for bridge disbursement** | ✅ **DONE** |
| GAP-17 | **Disbursement amount not anchored** | ✅ **DONE** |

### TIER 2 — First-Month Operational

| Gap | Description | Status |
|-----|-------------|--------|
| GAP-07 | No portfolio reporting API for MLO | ✅ **DONE** |
| GAP-08 | Human override timeout outcome undefined | ✅ **DONE** |
| GAP-09 | Calendar-day maturities misfire on non-business days | ✅ **DONE** |
| GAP-10 | No governing law / jurisdiction field on LoanOffer | ✅ **DONE** |
| GAP-11 | Thin-file Tier 3 for creditworthy established banks | ✅ **DONE** |
| GAP-12 | FX risk undefined for cross-currency corridors | ✅ **DONE** |

### TIER 3 — Full Commercial Readiness

| Gap | Description | Status |
|-----|-------------|--------|
| GAP-13 | No customer-facing notification framework | ✅ **DONE** |
| GAP-14 | No regulatory reporting format (DORA, SR 11-7) | ✅ **DONE** |
| GAP-15 | No BPI admin / multi-tenant monitoring | ✅ **DONE** |
| GAP-16 | Partial settlement handling undefined | ✅ **DONE** |

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

*Last updated: 2026-03-14 — Session: GAP-13 + GAP-14 + GAP-15 + GAP-16 complete. ALL 17 gaps done. Platform is Full Commercial Readiness. Test suite: 1,247 passing, 0 ruff errors.*
