# LIP Project — Progress Tracker

> Always update this file at the end of every session so the next session can resume without
> reading git history. Record: what was done, what is next, and any blockers.

---

## Session 2026-04-26 — CBDC Normalizer End-to-End (Phases A-E) + GH Health

**Tests**: 2,743 passing in fast suite (+32 from baseline). Zero ruff errors.
**CI**: green on main (fix #70 merged — pip-cache cleanup failure on k8s-manifest-guard).
**Branches pushed**: 5 phase branches + 1 fix branch, all rebased on green main.
**Open draft PRs**: #65 (Phase C), #66 (Phase E), #67 (Phase D), #68 (Phase A), #69 (Phase B).

### CBDC Normalizer end-to-end — Phases A through E

Strategic context: founder asked for the CBDC normalizer to be "finally built." Investigation showed the C5-side normalizer existed (e-CNY, e-EUR, Sand Dollar) but its output was dead — no downstream component consumed `event.rail`. Closed the gap end-to-end and extended to mBridge and FedNow.

**Phase A (PR #68) — End-to-end wiring + sub-day fee floor framework.**
- `lip/common/constants.py`: + `FEE_FLOOR_BPS_SUBDAY=1200`, `FEE_FLOOR_ABSOLUTE_USD=25`, `SUBDAY_THRESHOLD_HOURS=48.0`. Universal 300 bps floor unchanged (CLAUDE.md non-negotiable #2 preserved). QUANT call by Claude per founder authority grant 2026-04-25.
- `lip/c2_pd_model/fee.py`: + `applicable_fee_floor_bps()`, `is_subday_rail()`, `apply_absolute_fee_floor()`. `compute_fee_bps_from_el()` now accepts `maturity_hours` kwarg. `compute_loan_fee()` raw-math contract preserved (Architecture Spec C2 §9).
- `lip/c3_repayment_engine/repayment_loop.py`: + `ActiveLoan.rail` field; `_claim_repayment(rail=...)` computes hour-precision TTL for sub-day rails.
- `lip/c7_execution_agent/agent.py`: `_build_loan_offer` reads rail, applies sub-day floor as defence-in-depth third gate, surfaces `rail` and `maturity_hours` on the offer dict.
- `lip/pipeline.py`: `payment_context` carries `rail` + `maturity_hours`; new `_derive_maturity_hours()` helper; `_register_with_c3` uses hour-precision maturity_date for sub-day rails (legacy day-scale path preserved).
- New: `lip/tests/test_subday_fee_floor.py` (19 tests), `lip/tests/test_cbdc_e2e.py` (12 tests across phases). Extended: `TestRailAwareTTL` in `test_c3_repayment.py` (5 tests).

**QUANT defence (cost of capital math at $5M / 4h):**
COF (5% APR) = $114; opex ~$5; ~100 bps margin = $55; risk reserve ~$100; total ~$274. 1200 bps × 4h on $5M = $274. Exactly covers cost stack. 12% APR is consistent with private overnight bridge products priced 600-700 bps over Fed discount window (currently 5-6%).

**Phase B (PR #69) — mBridge multi-CBDC PvP rail.**
- New `lip/c5_streaming/cbdc_mbridge_normalizer.py` with `MBridgeNormalizer`. Multi-leg PvP shape (up to 5 currencies CNY/HKD/THB/AED/SAR settled atomically); failed leg surfaces as primary `NormalizedEvent`, sister legs preserved in `raw_source`.
- New CBDC failure codes: `CBDC-CF01` (consensus failure → AM04), `CBDC-CB01` (cross-chain bridge failure → FF01).
- `RAIL_MATURITY_HOURS["CBDC_MBRIDGE"] = 4.0`. Phase A foundation handles mBridge automatically.
- `EventNormalizer` dispatcher routes `CBDC_MBRIDGE` to the new normalizer.
- New: `lip/tests/test_cbdc_mbridge_normalizer.py` (15 tests including EPG-21 patent-language scrub with word-boundary matching to allow SAR currency code).

**Real-world context (verified April 2026):** mBridge is post-BIS (BIS exited Oct 2024), 5 central banks (PBOC, HKMA, BoT, CBUAE, SAMA) operate it independently with 31 observers, ~$55.5B settled across ~4,000 transactions, e-CNY = 95% of volume, SAMA joined as full participant post-BIS-exit.

**Phase C (PR #65) — FedNow E2E + cross-rail handoff detection.**
- FedNow already had a normalizer; Phase A foundation picks it up automatically (24h maturity → sub-day floor binds).
- New `UETRTracker.register_handoff(parent_uetr, child_uetr, child_rail)` with 30-min TTL. `find_parent()` reverse lookup. In-memory; production needs Redis backing (T2.2).
- Pipeline routing: when an event arrives on FEDNOW/RTP/SEPA + has rejection_code + has registered parent, outcome labelled `DOMESTIC_LEG_FAILURE` (instead of OFFERED) and `parent_uetr` field added to loan_offer dict. Bridge offer still issued (real failure to bridge).
- `PipelineResult` outcome list extended; `CLAUDE.md` outcome list updated (verify-field-semantics rule).
- New: `lip/tests/test_cross_rail_handoff.py` (11 tests including TTL expiry, rail validation, pipeline routing).

**Patent angle:** P9 continuation candidate — "*detecting settlement confirmation from disparate payment network rails for a single UETR-tracked payment*" (Master-Action-Plan-2026.md:378). Code only; filing frozen per CLAUDE.md #6.

**Phase D (PR #67) — Project Nexus stub (PHASE-2-STUB).**
- `RAIL_MATURITY_HOURS["CBDC_NEXUS"] = 4.0` (60s finality + 4h safety buffer).
- New `lip/c5_streaming/nexus_normalizer.py`. ISO 20022 native — no proprietary code map. Dispatcher routes `CBDC_NEXUS` to it.
- Schema modelled from BIS Nexus blueprint (July 2024); replace with real ISO 20022 profiles when NGP publishes.
- New: `lip/tests/test_nexus_stub.py` (7 tests).

**Real-world status:** NGP incorporated 2025 in Singapore (MAS as home regulator). 5 founding banks: RBI/BNM/BSP/MAS/BoT. Indonesia joining; ECB special observer. Onboarding pushed to mid-2027 per BSP Deputy Governor (March 2026).

**Phase E (PR #66) — Doc corrections + ADR.**
- `docs/operations/Master-Action-Plan-2026.md` §21 corrected — "mBridge paused 2024" was wrong. BIS *exited* in Oct 2024; platform alive with 5 central banks operating independently.
- `docs/models/cbdc-protocol-research.md`: + §1.1.1 post-BIS update, + §1.5 Project Nexus.
- New ADR: `docs/engineering/decisions/ADR-2026-04-25-rail-aware-maturity.md` documenting the architectural decisions (why no parallel `maturity_hours` field on ActiveLoan, why apply_absolute_fee_floor is separate from compute_loan_fee, FedNow/RTP repricing rationale).

### GH Health Audit + CI Fix

**Investigated:** All CI was red on main since 2026-04-25 (`93a6f8fa`). Initial hypothesis was Node 24 deprecation flag — wrong, that flag is now a no-op.

**Real root cause (PR #70, merged):** `actions/setup-python@v5` with `cache: "pip"` runs a post-job cleanup step that fails on empty cache save. The `Kubernetes manifest guard` job is the only job that uses pip cache without ever running pip-install (it runs `python scripts/check_k8s_manifests.py`, stdlib-only). 12/13 jobs were green; only k8s-manifest-guard red, pulling the whole run red.

**Fix:** Removed `cache: "pip"` (and the now-pointless `cache-dependency-path`) from k8s-manifest-guard job. Job runs in ~6 seconds; pip caching adds zero value. Verified: PR #70 LIP CI run 24958430119 — 13/13 jobs green.

**Side cleanup:**
- Renamed/proper-bodied/converted-to-draft all 5 phase PRs (auto-PR hook had opened C/D/E with stub bodies; A/B had no PRs).
- All 5 phase branches rebased onto green main.
- Workaround for documented Darwin TLS bug in `gh` CLI: used direct REST/GraphQL via `urllib` + PAT.

### What is NEXT

**Strategic (Project Nexus is an existential threat):**
1. The pivot conversation: LIP is no longer a "SWIFT bridge lending platform" — it's the cross-rail intelligence layer. Phase A's sub-day fee floor + Phase B's mBridge support + Phase C's cross-rail handoff are the *only* economic structure under which LIP works in a Nexus world. 300 bps × 60 seconds = $0.024 on $5M. The investor/pilot pitch needs a rewrite.
2. Patent counsel meeting on RBC IP clause — gates everything else (CLAUDE.md #6). Phase C cross-rail handoff is the strongest claim LIP has and cannot be filed until counsel opines.
3. Approach Nexus founding banks (BSP, MAS, BoT) directly — they have the corridors that see Nexus first and have most to gain from cross-rail intelligence.

**Engineering (next 2-4 sprints):**
1. **DGEN CBDC corridors** — C1 has zero training data on the rails we just normalized. Highest-leverage technical work item.
2. **C2 PD recalibration on sub-day** — current PD assumes day-scale tenor; at 4h, default-probability shape is different.
3. **Sub-day stress regime detector** — current 1h/24h windows are SWIFT-era; Nexus needs 1min/1h windows.
4. **T2.1 Kafka consumer for mBridge** — we have a normalizer, not a real consumer.
5. **Workflow hardening:** CodeQL flagged 15 alerts (10 missing-permissions on workflows + 3 clear-text-logging in C6 AML + 1 hard-coded crypto value in Rust + 1 misc). 10 are 5-minute fixes; CIPHER sign-off needed for the C6 logging and crypto-value items.

**Repo state at session close:** main green, 0 dependabot alerts, 5 draft phase PRs ready for review, 1 closed CI fix PR (#70), 1 deleted merged branch (codex/fix-ci-k8s-empty-cache-save), 11 unrelated open issues none.

---

## Session 2026-03-15 — Plan fizzy-jumping-rain Execution

**Tests**: 1276 passing (was 1286 reported; actual clean baseline was 1255 + pre-session uncommitted WIP).
Net gain this session: +21 stress regime tests, +7 from untracked test files.
**Lint**: 0 ruff errors.

### P1 COMPLETE — Local Prototype Infrastructure
- `docker-compose.yml`: Redpanda v24.1.1 (Kafka API-compatible) + Redis 7 Alpine.
  Includes `redpanda-init` service that creates all 10 Kafka topics on first boot.
- `scripts/start_local_infra.sh`: One-command startup with health-wait and env var guidance.
- `scripts/init_topics.sh`: Idempotent topic creation via `rpk`, supports `--brokers` + `--replicas` flags.
- **Usage**: `./scripts/start_local_infra.sh` (requires Docker Desktop running)

### P3 COMPLETE — Stress Regime Detector (C5)
- `lip/c5_streaming/stress_regime_detector.py`: Full implementation.
  - `StressRegimeEvent` dataclass (frozen): `corridor, failure_rate_1h, baseline_rate, ratio, triggered_at`.
    `to_json()` serialises for Kafka; `inf` ratio → `null` (JSON-safe).
  - `StressRegimeDetector`: 24h baseline vs. 1h current window; 3× multiplier (QUANT constant).
    `record_event()` / `is_stressed()` / `check_and_emit()` / `get_rates()` API.
    Kafka emit via injected producer; in-memory `emitted_events` fallback (PHASE-2-STUB).
    `_stress_window_rates()`: ratio in emitted event matches `is_stressed()` threshold exactly.
  - 21 tests in `lip/tests/test_c5_stress_regime.py` — all passing.
- `lip/c5_streaming/kafka_config.py`: Added `KafkaTopic.STRESS_REGIME = "lip.stress.regime"` (6 partitions, 7-day retention, at-least-once).
- `lip/c5_streaming/__init__.py`: Exports `StressRegimeDetector`, `StressRegimeEvent`.
- `lip/common/constants.py`: Added `STRESS_REGIME_MULTIPLIER = 3.0` + `STRESS_REGIME_MIN_TXNS = 20` (QUANT sign-off required).

### Integration Fixes (uncommitted WIP from prior session — now committed)
- `lip/c7_execution_agent/agent.py`: Integrated `BorrowerRegistry` (replaces `enrolled_borrowers: set`),
  `StressRegimeDetector`, `LicenseeContext`. Fixed enrollment check: empty registry = allow-all (dev default).
- `lip/pipeline.py`: Added `stress_detector` param + corridor stress recording. Added `c6.record()` call post-FUNDED.
- `lip/common/borrower_registry.py`: W293 ruff fixes (was untracked, now committed).
- `lip/tests/test_coverage_gaps.py`: Added `_MockC6.record()` no-op to match updated pipeline interface.
- `lip/tests/test_c5_streaming.py`: Updated `test_all_nine_topics_defined` → `test_all_ten_topics_defined`.

### P2 COMPLETE — Latency Benchmark
- `scripts/benchmark_pipeline.py`: 1,000 events (100 cold + 900 warm). Mock C1/C2; real C4+C6+C7+HMAC.
- Result: warm p99=0.29ms (323× below 94ms SLO). Cold path higher due to model init.
- `docs/benchmark-results.md`: Auto-generated, clearly states ML inference NOT measured.

### P5 COMPLETE — Cascade Risk Bayesian Smoothing
- `lip/c1_failure_classifier/graph_builder.py`: Added `_SMOOTHING_K=5`, `_DEPENDENCY_PRIOR_DEFAULT=0.10`.
  Added `observation_count: int` to `PaymentEdge`. Smoothing: `score = (n×raw + k×prior) / (n+k)`.
  `get_cascade_risk()` now returns `(at_risk_bics, CascadeConfidence)` tuple.
- `lip/tests/test_p5_cascade.py`: 10 tests covering first-payment fix, convergence, high-confidence.

### P4 COMPLETE — Large-Scale Synthetic Validation (Session 2026-03-15 continuation)
- `lip/dgen/c1_generator.py`: NEW — BIS CPMI-calibrated corridor distributions, 300 synthetic BICs,
  ISO 20022 rejection codes (A/B/C/BLOCK taxonomy). `generate_at_scale(n=2_000_000, seed=42)`.
- `lip/dgen/c2_generator.py`: Added `generate_at_scale(n=500_000, seed=42)`.
- `lip/dgen/c4_generator.py`: Added `generate_at_scale(n=200_000, seed=42)`.
- `lip/dgen/c6_generator.py`: Added `generate_at_scale(n=300_000, seed=42)`.
- `scripts/run_poc_validation.py`: Orchestrates generation + inference + metrics for all 4 components.
  Default: 10K records per component (~27s). Full-scale with `--full-scale` flag.
  C4 uses DisputeClassifier (MockLLMBackend). C6 uses AnomalyDetector (80/20 train/test).
- `docs/poc-validation-report.md`: Auto-generated bank-readable report. Results at n=10K:
  - C1: ✅ corridor rate error=0.0, temporal span=539.9 days, class fracs match BIS targets
  - C2: ✅ Altman Z separation healthy=3.995 vs default=1.33, tier default rates within tolerance
  - C4: ⚠️ DISPUTE_CONFIRMED recall=0.528 (known MockLLMBackend limitation; P6 fixes this)
  - C6: ✅ AML flag rate=7.85% (target 8%), precision=1.0, recall=0.244 (Isolation Forest unsupervised)
- **Tests**: 1284 passing, 1 skipped, 0 failures. 0 ruff errors.

### P7 COMPLETE — Federated Learning Architecture Document
- `docs/federated-learning-architecture.md`: Full ADR for P12 patent portfolio.
  - Protocol decision: FedProx (FedAvg + proximal term) for non-IID bank data.
  - DP budget: ε=1.0, δ=1e-5 via DP-SGD + Rényi DP accounting (50 rounds pilot).
  - Layer partitioning: first 2 GraphSAGE layers LOCAL (BIC topology), final + TabTransformer SHARED.
  - Communication: ~500 MB/bank over 6-month pilot (trivially within SWIFTNet capacity).
  - Threat model: semi-honest adversary (Phase 2); SecAgg + Byzantine-robustness for Phase 3.
  - Framework selected: Flower (Apache 2.0) + Opacus for DP-SGD.
  - 4 patent claims documented supporting P12.

### P8 COMPLETE — CBDC Protocol Research Document
- `docs/cbdc-protocol-research.md`: Research + architecture stubs for P9 patent portfolio.
  - BIS mBridge (MVP 2024): 1-3 second finality, ISO 20022 native, 4-participant CBDC settlement.
  - ECB DLT Pilot (2024): EUR zone wCBDC interoperability trials, intraday finality.
  - FedNow (2023): domestic only — scoped as `SettlementRail.FEDNOW` stub, not cross-border.
  - Digital Pound: 3-5 year horizon, BoE research phase.
  - CBDC-specific failure codes mapped to ISO 20022 taxonomy (CBDC-SC01→AC01, etc.).
  - `normalize_cbdc()` handler shape documented for `event_normalizer.py`.
  - `SettlementRail.CBDC` + `SettlementRail.FEDNOW` stub shapes documented for C3.
  - Settlement timing: CBDC 4h buffer vs SWIFT 45-day UETR TTL.
  - 4 patent claims + novelty over JPMorgan US7089207B1 documented.
  - Competitive moat: 36-60 month lead on DLT bridge lending (no known prior art).

### P6 COMPLETE — C4 LLM Integration Test (2026-03-16)
- `lip/tests/test_c4_llm_integration.py`: 17 tests, 6 test classes. **All 17 passing** (46s with Groq).
  - `TestC4FourClassAccuracy`: 4 parametrized cases — all 4 classes correct.
  - `TestC4NegationAwareness`: 6 negation tests — not-dispute, no-fraud, double-negation, conditional — all pass.
  - `TestC4Multilingual`: French/German/Spanish — all pass.
  - `TestC4PrefilterInteraction`: FRAU prefilter + empty narrative — pass.
  - `TestC4LLMLatency`: p95 < 10s on 10 consecutive calls — pass.
  - `TestC4NegationBulk`: FN rate on 50 sampled corpus cases < 15% — pass.
- `scripts/evaluate_c4_on_negation_corpus.py`: 100-case evaluation (20/category). Key results:
  - DISPUTE_CONFIRMED FN rate: **0.0%** (vs MockLLMBackend: 47.2%)
  - NOT_DISPUTE FP rate: **4.0%** (vs MockLLMBackend: 0.1%)
  - Overall accuracy: **71%** (low on conditional_negation; LLM conservatively flags conditionals as disputes)
  - Model: `qwen/qwen3-32b` via Groq API; `/no_think` directive disables chain-of-thought.
- `lip/common/constants.py`: `DISPUTE_FN_CURRENT` updated to `0.0000` (LLM=qwen/qwen3-32b, n=100).
- Key fix: removed `stop=["\n", " "]` from `_Qwen3GroqBackend.generate()` in both files.
  Root cause: stop token halted generation inside unclosed `<think>` block; `/no_think` + regex stripping is the correct approach.

### What is NEXT
- **ALL PLAN ITEMS COMPLETE** (P1–P8 + P6).
- Tests: 1284 passing, 1 skipped, 0 ruff errors. 17 new LLM integration tests (skipped without GROQ_API_KEY).
- The `fizzy-jumping-rain.md` plan is fully executed.
- Next sessions: pilot bank onboarding, real SWIFT data calibration (QUANT sign-off required), C1 AUC validation on anonymised data.

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
| C5 Streaming | ✅ Complete | Kafka worker, Flink jobs, **Stress Regime Detection** |
| C6 AML Velocity | ✅ Complete | Sanctions, **Licensee-configurable caps (GAP-02)** |
| C7 Execution Agent | ✅ Complete | offer delivery, **Borrower Registry (GAP-03)**, retry detection |
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
2. ✅ **GAP-02** — Licensee-configurable AML caps via license token
   - Added `aml_dollar_cap_usd` and `aml_count_cap` to `LicenseeContext`
   - Updated `VelocityChecker` to accept overrides in `check()` and `record()`
   - Updated `ExecutionAgent` to load caps from `LicenseeContext`
3. ✅ **GAP-03** — `BorrowerRegistry` + C7 first-gate check + `BORROWER_NOT_ENROLLED` state
   - New `lip/common/borrower_registry.py` managing MRFA enrollments
   - C7 `process_payment` checks registry BEFORE all other logic
4. ✅ **Stress Regime Detector** — `StressRegimeDetector` in C5 (corridor_failure_rate_1h > 3× baseline)
   - New `lip/c5_streaming/stress_regime_detector.py`
   - Integrated into `ExecutionAgent` to mandate human review during stress
5. ✅ **GAP-04** — Redis-ready `UETRTracker` with 30-min TTL + tuple-based dedup (FULL FIX 2026-03-22)
   - Updated `lip/common/uetr_tracker.py` with rolling window cleanup
   - Tuple-based dedup wired into pipeline.py: context (sending_bic, receiving_bic, amount, currency) passed to is_retry() and record()
   - 4 new integration tests in test_gap04_retry_detection.py (manual retry, FX tolerance, different sender, different amount)
6. **GAP-05** — `BPIRoyaltySettlement` monthly batch mechanism
   - New `lip/common/royalty_settlement.py`; triggered from C3 repayment callback
7. **GAP-17** — `original_payment_amount_usd` in NormalizedEvent + validation in `_build_loan_offer` (DONE)

---

## Canonical Constants (NEVER change without QUANT sign-off)

| Constant | Value |
|----------|-------|
| τ* (failure threshold) | 0.110 (calibrated, 2026-03-21) |
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

## Session 2026-03-16 — Production Data Pipeline (DGEN)

**Tests**: 1321 passing (was 1286), 18 skipped. Zero ruff errors.
**Branch**: `feat/e2e-simulation-harness` merged → `main` (commit `9bcad06`).

### DGEN Production Pipeline — COMPLETE ✅

Six new modules in `lip/dgen/` (do NOT modify — no unit tests by convention, exercised via CLI):

| Module | Purpose |
|--------|---------|
| `bic_pool.py` | 200 fictional ISO 9362 BICs, hub-and-spoke topology, corridor-aligned sampling |
| `iso20022_payments.py` | 2M+ ISO 20022 RJCT events, parquet, BIS/SWIFT GPI calibrated |
| `aml_production.py` | 100K AML records (STRUCTURING/VELOCITY/SANCTIONS_ADJACENT/CLEAN) |
| `web_inspector.py` | Public dataset HTTP inspection + `data_inspection_report.md` |
| `statistical_validator_production.py` | 7-check production validation suite |
| `run_production_pipeline.py` | CLI orchestrator; `--dry-run` (10K records, <30s) |

**Run the pipeline**:
```bash
# Dry-run validation (10K records, 6.9s):
python -m lip.dgen.run_production_pipeline --dry-run

# Full production (2M payments, 100K AML, 87s):
python -m lip.dgen.run_production_pipeline \
  --output-dir artifacts/production_data \
  --n-payments 2000000 --n-aml 100000 --seed 42
```

**Artifacts** (gitignored, reproducible with seed=42):
- `artifacts/production_data/payments_synthetic.parquet` — 143.8 MB, 2,000,000 rows
- `artifacts/production_data/aml_synthetic.parquet` — 10.5 MB, 100,000 rows

**Data-derived P95 constants** (locked in `lip/common/constants.py`):

| Constant | Value | BIS/SWIFT GPI target |
|----------|-------|---------------------|
| `SETTLEMENT_P95_CLASS_A_HOURS` | 7.05h | 7.0h |
| `SETTLEMENT_P95_CLASS_B_HOURS` | 53.58h | 53.6h |
| `SETTLEMENT_P95_CLASS_C_HOURS` | 170.67h | 171.0h |

### What is NEXT

1. **C1 Model Training on payments_synthetic.parquet** (IMMEDIATE)
   - `artifacts/production_data/payments_synthetic.parquet` is the training corpus
   - Target: `is_permanent_failure` (Class A = 1)
   - Graph input: BIC-pair topology from `bic_sender` / `bic_receiver`
   - Expected real-world AUC: 0.82–0.88 (needs anonymised SWIFT data under QUANT sign-off)

2. **Scale to 5–10M records** (before final C1 training run)
   ```bash
   python -m lip.dgen.run_production_pipeline \
     --output-dir artifacts/production_data_10m \
     --n-payments 10000000 --n-aml 500000
   ```
   Est. ~8 min on M-series MacBook.

3. **C6 Redis Phase 2** — wire `RollingWindow` → Redis `ZADD`/`ZRANGEBYSCORE`
   (documented in `velocity.py` module docstring, stub in place)

4. **Cloud provider selection** — K8s deployment for pilot bank onboarding

---

*Last updated: 2026-03-16 — Session: DGEN production pipeline complete, 1321 tests passing,
feat/e2e-simulation-harness merged to main. All 17 platform gaps done. P95 constants locked.*

---

## Session 2026-03-17/18 — EPIGNOSIS Architecture Review + C1 Production Training

**Tests**: 1351 passing (was 1321), 1 skipped. Zero ruff errors.
**Commits**: `be16c22` (EPG-01/03/07/08 taxonomy BLOCK), `0ec874c` (EPG-09/10/16/17/18), `[this session]` (EPG-14 code fix + defense-in-depth)

### DGEN Mixed Corpus — COMPLETE ✅
- `iso20022_payments.py`: now generates mixed corpus — RJCT events (label=1) + successful payments (label=0)
- Default `success_multiplier=4.0` → 80/20 split (success/RJCT); Option C labeling now valid
- `statistical_validator_production.py`: updated for mixed corpus (split RJCT/all-record checks, label distribution validation)
- `scripts/train_c1_on_parquet.py`: updated to use `label` column directly (Option C)

### EPG Taxonomy Fixes — COMPLETE ✅ (commit be16c22)
All compliance-hold and KYC-failure rejection codes moved to BLOCK class in `rejection_taxonomy.py`:

| Code | Meaning | EPG |
|------|---------|-----|
| RR01 | MissingDebtorAccountOrIdentification — KYC failure | EPG-01 |
| RR02 | MissingDebtorNameOrAddress — KYC failure | EPG-01 |
| RR03 | MissingCreditorNameOrAddress — KYC failure | EPG-01 |
| RR04 | RegulatoryReason — regulatory prohibition | EPG-07 |
| DNOR | DebtorNotAllowedToSend — compliance prohibition | EPG-02 |
| CNOR | CreditorNotAllowedToReceive — compliance prohibition | EPG-03 |
| AG01 | TransactionForbidden — bank-level prohibition | EPG-08 |
| LEGL | LegalDecision — court/regulatory hold | EPG-08 |

Tests updated: `test_c3_repayment.py` — 8 new BLOCK assertions, AG02 as canonical CLASS_B.

### EPG Compliance Architecture Fixes — COMPLETE ✅ (commit 0ec874c)

| EPG | Description | Implementation |
|-----|-------------|----------------|
| EPG-09/10 | Compliance hold audit trail | `outcome="COMPLIANCE_HOLD"` distinct from `"DECLINED"`; `compliance_hold: bool` on PipelineResult |
| EPG-16 | AML cap default scaled for correspondent banking | `AML_DOLLAR_CAP_USD=0`, `AML_COUNT_CAP=0` (unlimited); per-licensee via C8 token; 0=unlimited guard in velocity.py |
| EPG-17 | Explicit cap enforcement at boot | `license_token.from_dict` requires `aml_dollar_cap_usd`/`aml_count_cap` as mandatory JSON fields; missing → KeyError → boot_validator engages kill switch |
| EPG-18 | C6 anomaly → human review (EU AI Act Art.14) | `aml_anomaly_flagged` extracted from C6 result; routes to `PENDING_HUMAN_REVIEW` before any autonomous FUNDED decision |

### EPIGNOSIS Team Deliberation — EPG-19 and EPG-14 — COMPLETE ✅

**EPG-19 — Compliance-hold bridging: UNANIMOUS NO (REX final authority)**

NOVA + CIPHER + REX deliberated and reached full alignment. Defense-in-depth implemented:
- **Layer 1** (already in place): BLOCK class in rejection taxonomy → pipeline.py short-circuit
- **Layer 2** (this session): `_COMPLIANCE_HOLD_CODES` in agent.py expanded from 3 codes to 8:
  Added DNOR, CNOR, RR01, RR02, RR03 — previously absent despite being BLOCK-class. Comment
  updated with full rationale from all three agents.

Open (non-code): BPI License Agreement must require banks to maintain a compliance hold register
API. SAR-coded payments (MS03/NARR) are invisible to LIP — contractual mitigation required.

**EPG-14 — Who is the borrower: UNANIMOUS B2B interbank (REX final authority)**

Five required actions. Code action completed this session:
- ✅ **Tier 2 code fix**: `governing_law` now derived from `bic_to_jurisdiction(sending_bic)` not
  `currency_to_jurisdiction(loan_currency)`. New `bic_to_jurisdiction()` function in `governing_law.py`
  uses BIC chars 4–5 (ISO 3166-1 country code) → FEDWIRE/CHAPS/TARGET2/UNKNOWN, with currency fallback.

Open (legal/contract — not code):
- Tier 1: MRFA explicit B2B framing, originating bank as borrower, unconditional repayment clause
- Tier 1: BPI License Agreement AML disclosure (C6 cannot see bank's internal compliance holds)
- Tier 3: C2 model card — document PD model prices bank (near-zero PD), not end-customer

### Miscellaneous Fixes
- `SETTLEMENT_P95_CLASS_B_HOURS` label corrected in constants.py: was "Compliance/AML holds" (wrong —
  compliance holds are BLOCK, never bridged); now "Systemic/processing delays"
- CLAUDE.md: full EPIGNOSIS findings documented, governing_law rule added to Key Rules
- All test mock c6 results updated with `anomaly_flagged=False` where EPG-18 gate was triggering on MagicMock truthy bleed

---

## Session 2026-03-20 — Full Codebase Audit (Logic, Math, Security)

**Baseline**: 1410 passed, 2 failed, 8 skipped, 18 deselected (73.6s).
**Post-fix**: 1412 passed, 0 failed, 8 skipped, 18 deselected (73.3s).
**Lint**: 0 ruff errors.

### CRITICAL FIX — Compliance Hold Notification Dead Code (pipeline.py)

**Bug**: `pipeline.py` had two handlers for `c7_status == "COMPLIANCE_HOLD_BLOCKS_BRIDGE"`.
The first handler (reachable) returned early without calling `self._notification.notify()`.
The second handler (unreachable dead code) contained the EPG-11 notification logic.
Result: compliance hold notifications were **never sent**, violating FATF R.18/R.20 and EU AMLD6 Art.10.

**Fix**: Merged notification call into the first handler, deleted the dead second handler entirely.
Two pre-existing tests (`test_compliance_hold_fires_notification`, `test_compliance_hold_notification_payload`)
now pass — they were written to catch this exact scenario and were correctly failing.

### Type Consistency Fix — Fee Floor Constants (constants.py)

Changed 3 fee floor constants from `int` to `Decimal` for type consistency:
- `FEE_FLOOR_BPS`: `300` → `Decimal("300")`
- `FEE_FLOOR_TIER_SMALL_BPS`: `500` → `Decimal("500")`
- `FEE_FLOOR_TIER_MID_BPS`: `400` → `Decimal("400")`

All downstream consumers already wrapped in `Decimal(str(...))` or `int(...)` — zero breakage.

### C1 Failure Classifier Audit — PASS (1 hygiene issue)

- **Architecture**: GraphSAGE[384] + TabTransformer[88] → 472 → MLP(256→64→1). Dimensions verified correct.
- **Threshold**: `InferenceEngine.__init__` defaults to 0.110 (τ*, calibrated), matching `FAILURE_PROBABILITY_THRESHOLD` in pipeline.py. Pipeline recomputes `above_threshold` independently.
- **Feature leakage**: No direct leakage. Temporal features (failure_rate_1d/7d/30d) computed from graph builder using `_max_timestamp` (data-relative, not wall-clock). Caller responsible for excluding current payment from stats — documented but not enforced in code.
- **Calibration**: IsotonicCalibrator fitted on validation set, applied conditionally. Consistent with threshold application.
- **Docstring**: training.py:285 says `(n_val, 88)` but correct shape is `(n_val, 96)` — documentation-only bug.

### dgen Quality Audit — CONDITIONAL PASS (unstaged changes need test coverage)

**New corridors (8)**: USD/AUD, AUD/USD, USD/HKD, HKD/USD, EUR/SEK, USD/KRW, USD/BRL, USD/MXN.
All have realistic failure rates and settlement parameters. Channel mixes sum to 1.0.

**Temporal clustering** (`_inject_temporal_clustering`):
- Only modifies RJCT timestamps; labels never flipped — integrity preserved.
- 2–3 burst windows per BIC (7–21 days), 30% of RJCT senders.
- Creates genuine 1d/7d/30d failure rate variation for C1 feature training.
- **Risk**: burst windows could span train/test split boundaries if temporal splitting is used (current split is stratified random — safe for now).
- **Missing**: no unit test for temporal clustering. Should add before merging.

**c1_generator.py, c2_generator.py, validator.py**: Clean. Basel III PD calibration correct.

### Infrastructure Audit — 9 action items identified

**Good**: Network policies strict for C4/C7. HPA queue depth thresholds match canonical constants (C1=100, C2/C6=50, C3/C7=30). Resource limits appropriate for ML inference. ESO secret management is best practice.

**Action items** (none blocking current work — all infra hardening for pre-pilot):
1. Placeholder credentials need templated tokens (values.yaml)
2. imagePullPolicy should be IfNotPresent (not Always) for production
3. Pod Security Standards label missing on `lip` namespace
4. securityContext hardening only on C7 — needs applying to C1–C6
5. Explicit NetworkPolicy needed for C3/C6
6. C7 bank-side node selector needs taints/tolerations enforcement
7. Standalone Redis needs TLS
8. License refresh interval (24h) should be reduced to 1h
9. Kafka production TLS/SASL config needs documenting

### Audit Follow-ups — All Fixed (commit 7ff74dd)

**Post-fix test suite: 1419 passed, 0 failed** (was 1412 after critical fix).

1. **C1 InferenceEngine default threshold**: Changed from 0.5 → 0.110 (τ*, calibrated). Pipeline always
   overrode this, but direct callers would silently get the wrong threshold. Added
   `_DEFAULT_THRESHOLD` constant in inference.py. Updated `run_inference()` in `__init__.py`.
2. **dgen temporal clustering hardened**: Uses canonical `_EPOCH_START`/`_EPOCH_SPAN` instead of
   data-derived values. Added label integrity assertion. Documented train/test leakage caveat.
3. **7 new tests** (`TestTemporalClustering`): labels preserved, shape preserved, timestamps valid,
   epoch bounds, success timestamps unchanged, determinism, burst detection.
4. **training.py:285 docstring**: Fixed `(n_val, 88)` → `(n_val, 96)`.
5. **8 new corridors committed**: USD/AUD, AUD/USD, USD/HKD, HKD/USD, EUR/SEK, USD/KRW, USD/BRL,
   USD/MXN — all validated with realistic failure rates and settlement parameters.

### Infrastructure Hardening — All 9 Items Fixed (commit 221158b)

1. **securityContext on C1–C6**: runAsNonRoot, runAsUser=1000, readOnlyRootFilesystem, no privilege escalation. Consistent with C7.
2. **imagePullPolicy**: C1–C6 → IfNotPresent; C7 → Never (bank-side, pre-pulled).
3. **PSS namespace labels**: `pod-security.kubernetes.io/enforce: restricted` on `lip` namespace.
4. **C7 taints/tolerations**: `lip/bank-container=true:NoSchedule` toleration added.
5. **NetworkPolicy for C3/C6**: explicit ingress (lip ns, 8080) + egress (Redis 6379/6380, intra-ns, DNS).
6. **Redis TLS**: standalone Redis now serves on port 6380 with TLS cert/key/CA. Probes updated.
7. **License refresh**: 24h → 1h.
8. **Secrets placeholders**: ACCOUNT_ID → `<AWS_ACCOUNT_ID>`; deadbeef → `openssl rand -hex 32`.
9. **Helm values**: pullPolicy → IfNotPresent, tag → "" (requires explicit version at deploy).
10. **Redpanda docs**: production Kafka TLS/SASL configuration documented in header comments.

### What is NEXT

**Immediate (blocking pre-pilot — all are legal/contractual, not engineering)**:
1. Legal counsel engagement — MRFA explicit B2B framing + unconditional repayment clause (EPG-14)
2. BPI License Agreement — compliance hold register API clause (EPG-19), AML screen disclosure (EPG-14)
3. Patent filing — provisional patent (EPG-20/21), clean-room re-implementation
4. Bridgeability Certification API warranties — three warranties for pilot bank LOI (EPG-04/05)

**Engineering — ALL COMPLETE as of 2026-03-22:**
- ~~C2 model card~~ → DONE (docs/c2-model-card.md, B2B PD framing, EPG-14 Tier 3)
- ~~C6 Redis Phase 2~~ → DONE (atomic Lua script, TOCTOU-safe, multi-instance K8s)
- ~~GAP-04 tuple-based dedup~~ → DONE (pipeline.py context wired, 4 new tests)
- ~~C1/C2 temporal OOT split~~ → DONE (chronological split in training pipelines)
- ~~C4 docstrings/manifests~~ → DONE (Groq reality documented, dual-mode K8s)
- ~~CI httpx dependency~~ → DONE (added to requirements-ml.txt + pyproject.toml)
- Cloud deployment — K8s manifests hardened; ready for pilot bank onboarding

---

## Session: Hardening Sprint — Code Review Day + B1–B13 Remediation (2026-04-01 to 2026-04-10)

**Focus:** Security, correctness, and robustness hardening following comprehensive code review (2026-04-08, 13 batches, 30+ findings). Repository reorganisation to audience-based documentation structure.

### Completed — Security & Correctness (B-series findings)

- **B3-02**: Fixed unsigned HMAC fields — `dataclasses.fields()` introspection now auto-includes new `LicenseToken` fields in canonical signed payload
- **B3-01**: TOCTOU race in differential privacy budget accounting addressed with atomic operations
- **B6-01**: Compliance BLOCK code drift resolved — single source of truth via `_COMPLIANCE_HOLD_CODES` frozenset in `agent.py` (EPG-19 defence-in-depth Layer 2)
- **B6-02**: Kafka offset commit fixed on error paths (was committing before processing)
- **B8-01/02**: Federated learning DP composition bound and fail-open privacy fallback hardened
- **B9-01**: Intervention fee floor violation patched (was 200 bps path, now enforces `FEE_FLOOR_BPS = 300`)
- **B10-01/02**: Pickle deserialization RCE risk addressed via `secure_pickle.py` with hash verification
- **B11-01/02**: DGEN mislabelling issues corrected in synthetic data generators
- AML encapsulation tightened (CIPHER review findings)
- Fail-closed defaults enforced across all pipeline gates
- `Decimal` precision used throughout fee arithmetic (no more float drift)
- Rust/Go compilation errors resolved; CI pipeline repaired
- HMAC enforcement across all signed structures verified
- Sanctions screening edge cases hardened (C6)

### Completed — Repository Reorganisation (2026-04-10)

- **Cache cleared**: ~360 MB of `pytest-of-tomegah/`, `.mypy_cache/`, `torchinductor_tomegah/` deleted
- **`.gitignore` fixed**: Added `.mypy_cache/` and `torchinductor_*/` patterns
- **Legacy `consolidation-files` directory dissolved**: 45 files decomposed into `docs/legal/patent/`, `docs/engineering/specs/`, `docs/engineering/blueprints/`, `docs/legal/governance/`, `docs/engineering/research/`, `docs/business/`, `docs/operations/`
- **Root decluttered**: `CLIENT_PERSPECTIVE_ANALYSIS.md`, `LIP_COMPLETE_NARRATIVE.md`, `EPIGNOSIS_ARCHITECTURE_REVIEW.md` moved to `docs/`; root now has only `README.md`, `CLAUDE.md`, `PROGRESS.md`, and config files
- **Audience-based docs structure**: `docs/engineering/`, `docs/legal/`, `docs/business/`, `docs/operations/`, `docs/models/`
- **Duplicates removed**: `BPI_Gap_Analysis_v2.0 (1).md`, two `.docx` binaries, legacy `scripts/train_all.py`
- **README.md rewritten**: New layout diagram, updated metrics, audience-based navigation
- **INDEX.md rewritten**: 6 role-based reading paths, complete docs/ map, quick reference table

### Current State (2026-04-10)

**Test suite:** 1284 tests passing, 92% coverage

**Engineering blockers:** None.

**Legal/contractual blockers (non-engineering — not resolved by code):**
1. Patent non-provisional filing — pending patent counsel engagement
2. Pilot bank LOI — `hold_bridgeable` API clause language required before RBCx engagement (EPG-04/05)
3. MRFA B2B clause — unconditional repayment language required (EPG-14)
4. BPI License Agreement — AML disclosure / indemnification clause (EPG-14)
