# BRIDGEPOINT INTELLIGENCE INC.
## SR 11-7 Model Governance Pack v1.0
**Phase 3 Compliance Deliverable — Internal Use Only**  
**Leads:** REX (Regulatory & Compliance), ARIA (ML & AI Engineering)  
**Date:** March 5, 2026  
**Status:** ACTIVE — Stealth Mode. Nothing External.

> **Current-state addendum (2026-04-28):** this pack preserves the March 2026 SR 11-7 governance baseline. For deployable artifact truth, current C1/C2 staging RC metrics, and production-final caveats, read [`../../CURRENT_STATE.md`](../../CURRENT_STATE.md) and [`../../operations/releases/staging-rc-2026-04-24.md`](../../operations/releases/staging-rc-2026-04-24.md).

---

## REX SELF-CRITIQUE BEFORE DELIVERY

SR 11-7 was written for banks with large model inventories and dedicated model risk management (MRM) functions. Bridgepoint is a software licensor, not a bank. The risk here is either over-applying SR 11-7 in ways that create obligations Bridgepoint doesn't have, or under-applying it in ways that leave gaps when a bank licensee's MRM team conducts a vendor model review. The correct posture is: document to the standard a Tier-2 bank's MRM team would expect to see when reviewing an AI system embedded in their lending workflow — because that is the actual examination that will happen. Three areas where SR 11-7 creates genuine obligations for Bridgepoint as a model vendor: (1) model documentation must be sufficient for an independent validator to assess the model without the developer present; (2) model limitations must be stated honestly, not minimized; (3) the ongoing monitoring framework must be specific, not aspirational. This document meets all three standards or it doesn't ship.

ARIA self-critique: Pre-training performance targets (AUC ≥ 0.85, FN rate <2%) are cited throughout. They are targets. Until the models are built and tested, the honest ceiling is an estimate. This document documents the targets, the methodology for measuring against them, and the honest uncertainty bounds. It does not certify results that don't exist yet.

---

## 1. Purpose and Scope

This document constitutes the Model Risk Governance Pack for the Liquidity Intelligence Platform (LIP) operated by Bridgepoint Intelligence Inc. It is prepared in conformance with the principles of SR 11-7 (Supervisory Guidance on Model Risk Management, Federal Reserve / OCC, April 2011) and is intended to satisfy the model documentation, validation pathway, and ongoing monitoring requirements that bank licensees will require from Bridgepoint as a third-party model vendor.

**Scope:** Three models currently in scope.

| Model ID | Name | Component | Risk Tier |
|---|---|---|---|
| M-01 | Payment Failure Prediction Classifier | C1 | **High** — directly gates loan offer generation |
| M-02 | Unified Probability of Default Estimator | C2 | **High** — directly determines loan amount and fee pricing |
| M-03 | Dispute Classifier | C4 | **High** — hard block; missed disputes result in funded loans against contested invoices |

All three models are High risk under SR 11-7 classification criteria: they are used in automated decisions that directly affect lending outcomes, their outputs cannot be easily overridden without the human review path, and errors have direct financial consequences for the bank licensee.

**Out of scope for this version:** The C6 AML Velocity Module is a rules-based and statistical anomaly detection system, not a predictive model in the SR 11-7 sense. It is governed separately under CIPHER's security and AML documentation. The corridor bootstrap buffer algorithm (C3) is a statistical calculation, not a model, and is governed under the C3 component spec.

---

## 2. Model Inventory and Classification

### 2.1 M-01 — Payment Failure Prediction Classifier

| Field | Value |
|---|---|
| Model ID | M-01 |
| Component | C1 |
| Version at documentation | C1v1.0.0 (pre-production; version assigned at first training run) [UPDATED 2026-03-21: C1v1.1.0 — TRAINED. See docs/c1-model-card.md] |
| Model family | Graph Neural Network (GraphSAGE) + TabTransformer, binary classification head |
| Primary output | `failure_probability` — float [0.0, 1.0] per individual UETR-keyed payment event |
| Operating threshold | F2-optimal threshold determined at training time; documented in model artifact `modelcard.md` |
| Decision use | Threshold exceeded → loan offer generated. Threshold not exceeded → no action |
| Materiality | High. Directly gates whether a bridge loan offer is generated for any given UETR |
| Model owner | ARIA |
| Business owner | Bridgepoint Intelligence Inc. (MLO) |
| Bank-side user | Bank ELO — receives output embedded in `LoanOffer.classifier_shap` |

### 2.2 M-02 — Unified Probability of Default Estimator

| Field | Value |
|---|---|
| Model ID | M-02 |
| Component | C2 |
| Version at documentation | C2v1.0.0 (pre-production) |
| Model family | Unified LightGBM ensemble (5 models), Platt-scaled calibration layer |
| Primary outputs | `pd_estimate` — float [0.0, 1.0]; `lgd_estimate` — float; `fee_bps` — annualized basis points (floor: 300 bps) |
| Operating use | PD drives fee pricing and human review routing (bank-configurable threshold). LGD feeds expected loss calculation |
| Materiality | High. Determines loan pricing and whether offer routes to human review |
| Model owner | ARIA |
| Business owner | Bridgepoint Intelligence Inc. (MLO) |
| Bank-side user | Bank ELO — uses `fee_bps` for fee collection; `pd_estimate` compared to bank-configured thresholds |

### 2.3 M-03 — Dispute Classifier

| Field | Value |
|---|---|
| Model ID | M-03 |
| Component | C4 |
| Version at documentation | C4v1.0.0 (pre-production) |
| Model family | Fast-path: binary logistic classifier (3ms). LLM path: Llama-3 8B, 4-bit GGUF quantized, LoRA fine-tuned |
| Primary output | `dispute_detected` — bool; `dispute_confidence` — float [0.0, 1.0]; `dispute_category` — enum |
| Operating use | `dispute_detected = true` at confidence ≥ 0.7 → hard block, no loan offered. Confidence 0.3–0.7 → async LLM path |
| Materiality | High. False negative (missed dispute) results in a funded bridge loan against a genuinely contested invoice — near-zero recovery probability |
| Deployment constraint | On-device within C7 bank container. Zero network calls. SWIFT `RmtInf` text never leaves bank perimeter |
| Model owner | ARIA |
| Business owner | Bridgepoint Intelligence Inc. (MIPLO) |
| Bank-side user | C7 Embedded Execution Agent — enforces block; bank operator can override with logged justification |

---

## 3. Model Documentation — M-01

### 3.1 Purpose

M-01 predicts, in real time, whether a specific individual cross-border B2B payment — identified by its UETR — will fail to settle within its rejection-class-appropriate maturity window (3, 7, or 21 days). The output is a continuous probability score. When this score exceeds the operating threshold, the MIPLO Decision Engine generates a bridge loan offer for the receiving bank's ELO to accept or decline.

This is not a portfolio-level forecasting model. It operates on individual payment events, one UETR at a time, within a latency budget of p50 ≤ 30ms on GPU (T4 class minimum). This individual-event architecture is the structural distinction from prior art systems that operate on aggregate cash flow forecasts.

### 3.2 Methodology

**Graph construction:** A BIC-pair payment network graph is constructed weekly from historical payment flow data. Nodes are BIC codes (sending and receiving banks). Edges represent corridor relationships, weighted by volume and historical failure rates over a rolling 90-day window. GraphSAGE performs neighborhood aggregation: each BIC node's embedding encodes its own characteristics plus a weighted summary of its neighbors' characteristics, capturing network-level contagion effects (a bank with many failing neighbors is itself more likely to be involved in failures).

**Tabular feature encoding:** A TabTransformer encodes 14 tabular features including rejection code class (A/B/C), amount tier (log-normalized), time-of-day (cyclic sin/cos encoding), day-of-week, corridor-specific historical rejection rate over 90 days, sender-receiver BIC relationship age, and jurisdiction pair. TabTransformer applies multi-head self-attention to learn interactions between tabular features that a standard gradient boosting model would require manual feature engineering to capture.

**Combined classifier head:** GraphSAGE corridor embedding (output of neighborhood aggregation for the relevant BIC pair) is concatenated with the TabTransformer output. A 3-layer MLP with dropout produces the final binary classification probability.

**Threshold setting:** Operating threshold is set using F2-weighted optimization, reflecting asymmetric cost of errors: false negatives (missed failure, no bridge offered — missed revenue) are penalized twice as heavily as false positives (bridge offered when payment would have settled — capital deployed at minor opportunity cost, but bridge loan generates revenue if accepted).

[ACTUAL 2026-03-21: Isotonic calibration (PAVA) added post-training. LightGBM 50/50 ensemble with PyTorch neural. ECE reduced from 0.1867 to 0.0687.]

### 3.3 Training Data

| Field | Value |
|---|---|---|
| Data type | Historical ISO 20022 pacs.002 payment status events with settlement outcome labels |
| Label definition | Positive (failure): no settlement signal received within maturity window (3/7/21 days per rejection class). Negative (not failure): settlement confirmed via any of 5 signal channels |
| Expected label noise | 1–3% (settlement signals received but not captured due to Kafka gaps or parsing errors are mislabeled as failures) |
| Minimum training size | To be determined at Phase 1 build; minimum 50,000 labeled events required for reliable GNN graph construction [ACTUAL 2026-03-21: 2M sample from 10M corpus. Full provenance: docs/c1-training-data-card.md] |
| Train/validation/test split | 70/15/15 chronological split. Out-of-time (OOT) test set = most recent 15% of data by date. Random split is prohibited — it leaks temporal patterns |
| Data provenance | Documented in model artifact `modelcard.md` at training time: source, date range, volume, label distribution |
| Data residency | Training data processed within Bridgepoint infrastructure (Zone A). No raw borrower identity data. UETR and BIC codes only |

### 3.4 Inputs

All inputs are sourced from the `ClassifyRequest` gRPC schema (Architecture Spec §4.2). Key inputs:

- `uetr` — individual payment identifier (verbatim in every request; required)
- `individual_payment_id` — explicit individual transaction reference (verbatim; required)
- `rejection_code` — raw SWIFT ISO 20022 rejection code (e.g., AC04, AM04, AG01)
- `rejection_code_class` — Class A/B/C derived from taxonomy (Architecture Spec §8)
- `bic_sender`, `bic_receiver` — corridor identification
- `amount_usd` — normalized transaction amount
- `corridor_embedding` — pre-computed float array from Redis (BIC-pair graph representation); Phase 1 ARIA deliverable
- `hour_of_day`, `day_of_week` — temporal features (cyclic encoded)
- `is_thin_file` — indicates limited entity history available

### 3.5 Outputs

- `failure_probability` — float [0.0, 1.0]; primary model output [ACTUAL τ* = 0.110 (calibrated probability scale, isotonic regression)]
- `threshold_exceeded` — bool; convenience flag for Decision Engine
- `shap_values` — list of top-20 feature contributions (GradientExplainer, PyTorch); logged in `DecisionLogEntry` per EU AI Act Art.13
- `model_version` — semantic version string (e.g., C1v1.0.0); logged for audit trail
- `inference_latency_ms` — wall-clock inference time; monitored for degradation

### 3.6 Known Limitations

These limitations are structural, not implementation defects. They are disclosed in full.

1. **Graph topology assumption.** GraphSAGE assumes the BIC-pair network is stable between weekly rebuilds. Sudden routing changes (bank mergers, sanctions-driven re-routing) degrade performance until the next weekly graph rebuild. Monitoring: graph structure drift alert fires if edge count changes >15% between weekly builds.

2. **Label noise ceiling.** With 1–3% label noise in training data, an AUC ceiling exists at approximately 0.88–0.90. AUC above 0.90 on the test set is likely overfitting, not genuine performance. ARIA documents the honest AUC ceiling before training begins.

3. **Rare rejection code coverage.** SWIFT rejection codes appearing fewer than 100 times in training data will have poorly calibrated individual embeddings. The `rejection_code_class` (A/B/C) feature provides a backstop. Rare codes are flagged as `taxonomy_status: UNCLASSIFIED` for quarterly review.

4. **Cold-start corridors.** New BIC-pair corridors with no history use currency-pair mean embeddings. Performance on new corridors is expected to be lower than established corridors. The four-tier bootstrap protocol (Architecture Spec §11.4) manages capital risk during this period.

5. **Pre-training AUC estimate.** ARIA's honest pre-training estimate: **AUC 0.82–0.88**. The target of 0.85 is achievable but not guaranteed. A hard ceiling near 0.88–0.90 likely exists for this problem domain given irreducible noise in payment network events. [RESULT 2026-03-21: Val AUC = 0.8871 achieved, within honest ceiling. F2 = 0.6245, ECE = 0.0687.]

### 3.7 Failure Modes

| Failure Mode | Probability | Impact | Mitigation |
|---|---|---|---|
| False negative (failure missed) | Dependent on threshold | Missed revenue; no capital loss | F2-weighted threshold optimization increases recall |
| False positive (false failure predicted) | Dependent on threshold | Capital deployed at opportunity cost; usually revenue-generating if borrower accepts | Acceptable per F2 weighting; monitored via calibration curve |
| Model decay (AUC decline over time) | Medium — payment networks evolve | Increasing false negatives over time | Rolling-window backtest; quarterly retraining trigger if AUC declines >3% |
| Graph topology shift | Low-Medium | Performance degradation until next weekly rebuild | Graph structure drift monitoring; emergency rebuild capability |
| GPU unavailability | Low | Inference falls to CPU: p50 ~86ms, p99 ~163ms — within SLA but zero headroom | CPU fallback path implemented; `degraded_mode: true` logged; automatic recovery |
| Training data contamination | Low | Biased model; overfit to specific time period | Chronological split enforced; OOT test set mandatory |

---

## 4. Model Documentation — M-02

### 4.1 Purpose

M-02 estimates, in real time, the probability that the borrower (payment receiver) will fail to repay the bridge loan by maturity. It also estimates Loss Given Default (LGD) and derives the annualized fee in basis points (`fee_bps`), subject to a hard floor of 300 bps (0.0575% per 7-day cycle). This replaces the prior three-tier stack (Merton structural model / Altman Z-Score proxy / Statistical industry proxy) with a unified LightGBM ensemble that handles the full borrower spectrum — listed corporates to thin-file SMEs — through a single model with learned feature imputation for missing data.

### 4.2 Methodology

**Unified LightGBM ensemble:** Five LightGBM models trained on bootstrap samples of the training dataset (bagging). Final PD estimate is the mean of five model outputs after Platt scaling calibration. Bagging reduces variance and provides uncertainty estimation: the spread across five models is a proxy for prediction confidence.

**Thin-file path:** When `is_thin_file = true` (no balance sheet data available), the model activates feature imputation: jurisdiction-level SME default rates, sector-level default rates, and rejection code class serve as the primary features. The model is designed to produce a conservative but calibrated estimate in the absence of financial data — not to fail or return a null value.

**Calibration:** Platt scaling applied post-training. Expected Calibration Error (ECE) target ≤ 0.04. Calibration is mandatory because `fee_bps` is derived from the PD output — an uncalibrated PD that is systematically over-confident underprices risk.

**Fee derivation:** `fee_bps = max(300, base_rate + EL_spread)` where `EL_spread = PD × LGD × EAD_factor`. The 300 bps floor ensures minimum revenue coverage regardless of model output. Fee is **annualized** — per-cycle fee formula is:

\[ \text{fee}_{USD} = \text{funded\_amount} \times \frac{\text{fee\_bps}}{10{,}000} \times \frac{\text{days\_funded}}{365} \]

At 300 bps, 7-day cycle, $100,000 principal: fee = $57.53 (0.0575%). Applying 300 bps as a flat per-cycle rate would yield $3,000 — 52× the intended fee. This error is documented in every code review touching fee calculation.

### 4.3 Training Data

| Field | Value |
|---|---|
| Target variable | Binary: bridge loan default (1) or repayment by maturity (0) |
| Critical requirement | Training data must be **bridge loan defaults**, not general corporate defaults. Bridge loan default dynamics (3–21 day maturity, trade finance context) differ materially from corporate credit defaults |
| Thin-file subsample | Tier 3 (SME/proxy) entities must comprise ≥20% of training set to ensure adequate representation |
| Minimum training size | To be determined at Phase 1; minimum 20,000 labeled bridge loan outcomes recommended |
| Data provenance | Documented in `modelcard.md` at training time |

### 4.4 Inputs

All inputs sourced from `PDRequest` gRPC schema (Architecture Spec §4.3):

- `entity_tax_id_hash` — SHA-256(tax_id, salt); never raw identity
- `entity_type` — PUBLIC / PRIVATE / SME
- `jurisdiction` — ISO 3166-1 alpha-2
- `annual_revenue_usd` — 0.0 if unavailable; triggers thin-file path
- `existing_exposure_usd` — current outstanding bridge loans to this entity
- `requested_amount_usd` — EAD proxy
- `rejection_code_class` — A / B / C (drives maturity which affects EL)
- `maturity_days` — 3, 7, or 21; derived from rejection code class
- `is_thin_file` — bool; triggers imputation path

### 4.5 Outputs

- `pd_estimate` — float [0.0, 1.0]; primary output; calibrated probability
- `lgd_estimate` — float; jurisdiction-tiered lookup (pre-pilot defaults; to be updated with observed recovery data post-pilot)
- `expected_loss_usd` — `pd_estimate × lgd_estimate × EAD`
- `fee_bps` — annualized, minimum 300 bps
- `shap_values` — top-20 features (TreeExplainer, ≤2ms latency; EU AI Act Art.13)
- `thin_file_flag` — bool; logged for regulatory transparency
- `model_version` — e.g., C2v1.0.0

### 4.6 Known Limitations

1. **LGD is pre-pilot estimated, not empirically calibrated.** Jurisdiction-tiered LGD defaults are informed estimates. Post-pilot observed recovery rates will replace these. All outputs prior to LGD calibration carry this caveat in `modelcard.md`.

2. **Bridge loan PD ≠ corporate PD.** If training data is sourced from general corporate default databases (a common proxy), the model is misspecified. Training data must be bridge loan outcomes or the target variable must be explicitly adjusted with rationale documented.

3. **Thin-file AUC ceiling.** For Tier 3 SME borrowers with no financial data, ARIA's honest AUC estimate is 0.70–0.78. If AUC on the Tier 3 OOT subsample falls below 0.72, a conservative fixed PD is deployed for that tier rather than the model output. This is a known limitation, not a failure.

4. **Short-maturity noise.** For 3-day (Class A) loans, there is limited time for predictive signals to manifest. AUC on Class A loans is expected to be lower than Class B/C. Documented in model card.

5. **Jurisdiction coverage gaps.** Rare jurisdictions (small island states, frontier markets) will have near-random jurisdiction embeddings. Jurisdiction-level macro features (GDP growth, banking system score) partially mitigate this but do not eliminate it.

### 4.7 Failure Modes

| Failure Mode | Probability | Impact | Mitigation |
|---|---|---|---|
| PD underestimation (systematic) | Medium pre-calibration | Fee underpricing; bank capital losses | Platt calibration; ECE target ≤ 0.04 |
| LGD mis-estimation | High pre-pilot | Fee underpricing | LGD flagged as pre-pilot estimate; post-pilot recalibration scheduled |
| Feature availability failure (no data) | Low | Model defaults to conservative thin-file path | Thin-file path tested at 3 data availability levels (A/B/C) |
| Model decay | Medium | Systematic underpricing as credit conditions evolve | Quarterly recalibration; challenger model monitoring |
| Fee floor breach | Near-zero | Loan underpriced below minimum | Hard floor enforced at output layer; QUANT-verified in every code review |

---

## 5. Model Documentation — M-03

### 5.1 Purpose

M-03 classifies whether the free-text remittance information field (`RmtInf`) in a SWIFT payment message indicates a **commercial dispute** (contested invoice, rejected goods, quality issue, etc.) that would render the underlying receivable uncollectable. A bridge loan funded against a genuinely disputed invoice has near-zero recovery probability — it is the highest-severity false-negative scenario in the entire LIP. M-03 is deployed as a hard block: if dispute is detected with confidence ≥ 0.70, no loan offer is generated, regardless of any other model output.

M-03 runs **on-device within the C7 bank container**. The `RmtInf` field contains borrower payment data and must never leave the bank's infrastructure perimeter. There is no network call from C7 to any Bridgepoint system for M-03 inference.

### 5.2 Methodology

**Two-path architecture:**

- **Fast path** (always active, synchronous, 3ms): A lightweight binary logistic classifier trained on engineered features extracted from `RmtInf` text (keyword n-grams, negation flags, reference pattern detection). Produces a confidence score. If confidence ≥ 0.70: hard block. If confidence ≤ 0.30: clear (proceed). If confidence 0.30–0.70: uncertain, route to LLM path.

- **LLM path** (async, triggered on uncertain fast-path, 30–60ms): Llama-3 8B parameter model, fine-tuned via LoRA/QLoRA on ≥50,000 labeled SWIFT `RmtInf` messages. Quantized to 4-bit GGUF (Q4_K_M or Q5_K_M) for bank container deployment. The LLM path handles nuanced cases: negation ("not a disputed invoice"), partial disputes, multilingual text, and structured reference formats that the fast-path classifier may misread. LLM timeout policy: 500ms hard limit with amount-tiered fallback (proceed <$50K; human review $50K–$500K; block >$500K).

**Training corpus:** Minimum 50,000 labeled SWIFT `RmtInf` messages. Label categories:
- DISPUTE: genuine commercial dispute language
- NOT_DISPUTE: non-dispute (negation, unrelated text)
- NEGATION_DISPUTE: text containing dispute keywords in negated context ("not a disputed invoice") — a dedicated category to prevent false positives on negation patterns

**Quarterly retraining:** M-03 is retrained quarterly using blocked-case review data from the bank's credit team. Every hard block generates a human review queue entry. Reviewer verdicts (dispute confirmed / dispute false-positive) become labeled training data.

### 5.3 Inputs

All inputs from `DisputeRequest` gRPC schema (Architecture Spec §4.4):

- `uetr` — individual payment identifier
- `remittance_info` — raw SWIFT `RmtInf` free text
- `structured_ref` — structured reference if available
- `creditor_ref` — creditor reference if available

**Critical constraint:** No entity identifiers are passed to M-03. The dispute decision is made purely on remittance text content, not on borrower identity.

### 5.4 Outputs

- `dispute_detected` — bool; primary output
- `dispute_confidence` — float [0.0, 1.0]
- `dispute_category` — enum: INVOICE_DISPUTE / QUALITY / DELIVERY / FRAUD / UNKNOWN
- `fast_path_used` — bool; logged for path-level monitoring
- `llm_path_used` — bool; logged for LLM utilization monitoring
- `inference_latency_ms` — logged per inference

### 5.5 Known Limitations

1. **Language coverage.** Initial training corpus may be English-dominant. Performance on non-English `RmtInf` text (EUR, APAC corridors) will be lower until multilingual training data is incorporated. Flag: if ≥10% of processed messages contain non-English text, ARIA reviews language coverage of training corpus.

2. **Structured vs. unstructured `RmtInf`.** Many payments use structured reference formats (ISO 20022 structured remittance) with no free text. M-03's fast-path classifier is optimized for free text. On structured-only `RmtInf` with no text content, M-03 should return NOT_DISPUTE with low confidence — routing to LLM path for safety. ARIA confirms this behavior in validation.

3. **Pre-training false-negative estimate.** Current keyword matcher FN rate: ~8%. Target: <2%. ARIA's honest pre-training estimate on fine-tuned Llama-3 8B: **1.5%–3.0% FN rate on held-out test set** — achievable but not guaranteed. Honest result reported at Audit Gate 1.3 regardless of target.

4. **Memory footprint constraint.** 4-bit GGUF at 8B parameters requires ~5–6GB resident memory within the C7 container. If bank container memory is constrained, Q3_K_M quantization (~4GB) may be required, with marginal accuracy reduction. ARIA benchmarks both before final deployment decision.

5. **LLM timeout rate.** If LLM timeout rate exceeds 1% of LLM-path inferences in any rolling 1-hour window, this indicates undersized hardware. Alert fires; FORGE escalates. The 50K/500K timeout thresholds are defaults pending pilot calibration.

### 5.6 Failure Modes

| Failure Mode | Probability | Impact | Mitigation |
|---|---|---|---|
| False negative (dispute missed) | Target <2%; current ~8% | Funded bridge loan against disputed invoice; near-zero recovery | Fine-tuned LLM; dedicated negation training; quarterly retraining |
| False positive (not dispute, blocked) | Low on fine-tuned model | Revenue missed; borrower experience degraded | Negation test suite; human override available |
| LLM timeout (high value) | Low at correct hardware sizing | Amount-tiered: block >$500K, review $50K–$500K | FORGE hardware sizing; auto-scale on timeout rate >1% |
| On-device process failure | Very low | Amount-tiered: hard block >$50K, proceed <$50K | Fail-safe design; `C4_UNAVAILABLE` logged |
| Model staleness (FN rate drift) | Medium over time | Increasing missed disputes as new dispute language emerges | Quarterly retraining from human review labels |

---

## 6. Independent Validation Pathway

SR 11-7 requires that models be validated by parties independent of model development. For Bridgepoint as a vendor, this means:

**Internal cross-agent validation (pre-pilot):**
- M-01 (ARIA-built) is validated by NOVA and FORGE (infrastructure feasibility) and REX (regulatory compliance of outputs). ARIA does not self-certify.
- M-02 (ARIA-built) is validated by QUANT (fee arithmetic and capital treatment implications) and REX (EU AI Act Art.13 SHAP compliance). ARIA does not self-certify.
- M-03 (ARIA-built) is validated by CIPHER (adversarial robustness) and REX (compliance of hard-block logic). ARIA does not self-certify.

**Bank-side MRM validation (pre-pilot):**
Each bank licensee's Model Risk Management function will conduct an independent review of M-01, M-02, and M-03 prior to live deployment. Bridgepoint provides to bank MRM:
- Complete model documentation (this document)
- Model artifact package (weights + `modelcard.md` + `benchmark_results.json`)
- Training data provenance summary (source, date range, size — not raw data)
- SHAP value examples (anonymized)
- Validation test results from Audit Gates 1.1, 1.2, and 1.3

**Bridgepoint does not conduct the bank's independent validation.** The bank's MRM team conducts it independently. Bridgepoint cooperates with information provision only.

**Post-pilot independent validation:**
After the first 90 days of pilot data, ARIA produces a **live performance validation report** comparing model performance on live bank data against development dataset performance. This report is provided to the bank's MRM function. It is the first empirical validation against non-synthetic data.

---

## 7. Model Change Approval Workflow

No model weight change, threshold adjustment, or architecture modification may be deployed to production without completing the following approval sequence:

**Step 1 — Change proposal (ARIA)**
ARIA documents: nature of change (MAJOR / MINOR / PATCH per semantic versioning), reason for change, expected performance impact, rollback plan.

**Step 2 — Impact assessment (REX + QUANT)**
REX assesses: Does the change affect EU AI Act Art.13 SHAP log compliance? Does it affect the independent validation pathway? Does it require bank MRM notification?
QUANT assesses (M-02 only): Does the change affect `fee_bps` derivation or the 300 bps floor? If yes, QUANT sign-off required before deployment.

**Step 3 — Validation (cross-agent)**
The changed model runs through the full validation suite from the relevant Audit Gate checklist (1.1, 1.2, or 1.3) before production deployment. No exceptions.

**Step 4 — Bank notification**
- PATCH changes: bank notified via changelog at next scheduled update window
- MINOR changes: bank MRM notified 14 days before production deployment; 7-day objection window
- MAJOR changes: bank MRM notified 30 days before; full re-validation required; bank sign-off required

**Step 5 — Canary deployment**
5% traffic canary for minimum 1 hour. Auto-rollback if p99 latency exceeds target or error rate exceeds 0.5%. Full rollout only after canary passes. Previous model version retained for 90 days.

**Step 6 — Model change log entry**
Every change logged with: model version from/to, change type, reason, test results, approvers, deployment timestamp. This log is a 7-year retention record (SR 11-7 model documentation requirement).

---

## 8. Performance Monitoring Dashboard Specification

This section specifies the ongoing monitoring dashboard that must be operational before Phase 5 integration testing begins. It satisfies EU AI Act Art.17 quality management and SR 11-7 ongoing monitoring requirements.

### 8.1 M-01 Monitoring Metrics

| Metric | Alert Threshold | Cadence | Owner |
|---|---|---|---|
| AUC (proxy via label feedback) | <0.80 → WARNING; <0.75 → CRITICAL | Weekly | ARIA |
| Operating threshold score distribution | Shift >5% from baseline → WARNING | Daily | ARIA |
| Inference latency p99 (GPU) | >50ms → WARNING; >100ms → CRITICAL | Real-time | FORGE |
| Corridor embedding drift | Edge count change >15% week-over-week → WARNING | Weekly | ARIA |
| False negative rate (estimated from label feedback) | >5% → WARNING | Weekly | ARIA |
| Unknown rejection code volume | >5% of weekly events → WARNING (NOVA taxonomy review) | Weekly | NOVA |
| Degraded mode CPU activations | Any → INFO; >1 hour → WARNING | Real-time | FORGE |

### 8.2 M-02 Monitoring Metrics

| Metric | Alert Threshold | Cadence | Owner |
|---|---|---|---|
| PD distribution drift | KS statistic >0.10 vs. training distribution → WARNING | Weekly | ARIA |
| Fee floor activations (% of offers at floor) | >80% of offers at floor → WARNING (model may be over-estimating PD) | Daily | QUANT |
| LGD estimate vs. observed recovery (post-pilot) | MAE >5 percentage points → CRITICAL recalibration required | Post-pilot monthly | ARIA + QUANT |
| Thin-file ratio | >60% of requests thin-file → WARNING (corpus drift) | Weekly | ARIA |
| Calibration ECE | >0.06 → WARNING; >0.10 → CRITICAL retrain | Monthly | ARIA |
| Inference latency p99 | >30ms → WARNING; >60ms → CRITICAL | Real-time | FORGE |

### 8.3 M-03 Monitoring Metrics

| Metric | Alert Threshold | Cadence | Owner |
|---|---|---|---|
| False negative rate (human review verdicts) | >3% confirmed disputes missed → WARNING; >5% → CRITICAL immediate retrain | Weekly | ARIA |
| Hard block rate (% of offers blocked by C4) | >15% → WARNING (may indicate over-classification) | Daily | ARIA |
| LLM timeout rate | >1% of LLM-path inferences → WARNING | Hourly | FORGE |
| Fast-path uncertainty rate (0.3–0.7 confidence) | >20% of inferences → WARNING (fast-path weakening) | Daily | ARIA |
| Non-English text volume | >10% of `RmtInf` text → WARNING (language coverage review) | Weekly | ARIA |
| Human override rate on C4 blocks | >10% of blocks overridden → WARNING (false positive rate high) | Weekly | ARIA |

### 8.4 Challenger Model Framework

For each model in production, a challenger model is maintained in parallel on a shadow dataset:

- **M-01 challenger:** Retrained GraphSAGE + TabTransformer with updated corridor graph and most recent 6-month data. Shadow inference runs on all live traffic; outputs logged but not acted upon. If challenger AUC exceeds production model by >3% on 30-day rolling window, champion/challenger swap initiated per Section 7 workflow.
- **M-02 challenger:** Retrained LightGBM ensemble with updated LGD estimates from post-pilot recovery data. Same swap trigger.
- **M-03 challenger:** Retrained fast-path classifier and LLM fine-tune on most recent quarterly review labels. Swap trigger: challenger FN rate <80% of production FN rate on monthly labeled test set.

**Challenger infrastructure:** Shadow inference does not add latency to production path. Challenger models run as separate replicas consuming from a mirrored Kafka topic. No capital risk.

---

## 9. Audit Gate 3.2 — SR 11-7 Checklist

Gate passes when ALL items are checked. REX signs. ARIA co-signs on technical accuracy.

**Model Inventory**
- [ ] All three models (M-01, M-02, M-03) documented with purpose, methodology, training data, outputs, limitations, failure modes
- [ ] All models classified as HIGH risk — justified in Section 2
- [ ] C6 AML module correctly classified as out-of-scope for SR 11-7 model governance — justified

**M-01 Documentation**
- [ ] Purpose, methodology, training data, inputs, outputs documented
- [ ] Known limitations Section 3.6 — all 5 limitations stated honestly
- [ ] Failure modes Section 3.7 — all 6 modes with mitigation
- [ ] Pre-training AUC honest ceiling documented (0.82–0.88)

**M-02 Documentation**
- [ ] Purpose, methodology, training data, inputs, outputs documented
- [ ] LGD pre-pilot status explicitly flagged as estimated
- [ ] Bridge loan PD vs. corporate PD distinction documented
- [ ] Fee arithmetic formula correct; 300 bps floor enforced; QUANT verified
- [ ] Known limitations Section 4.6 — all 5 limitations stated

**M-03 Documentation**
- [ ] Purpose, methodology, training data, inputs, outputs documented
- [ ] On-device deployment constraint documented; zero network calls confirmed
- [ ] Pre-training FN rate honest estimate documented (1.5%–3.0%)
- [ ] Negation handling addressed in methodology
- [ ] LLM timeout policy documented

**Independent Validation**
- [ ] Internal cross-agent validation assignments documented (Section 6)
- [ ] Bank MRM validation process documented — what Bridgepoint provides
- [ ] Post-pilot live performance validation report scheduled
- [ ] Bridgepoint's role clearly separated from bank's independent validation

**Model Change Workflow**
- [ ] 6-step approval workflow documented
- [ ] MAJOR/MINOR/PATCH classification criteria defined
- [ ] Bank notification windows defined (7 / 14 / 30 days by change tier)
- [ ] Canary deployment protocol documented
- [ ] Model change log as 7-year retention record confirmed

**Performance Monitoring Dashboard**
- [ ] M-01, M-02, M-03 monitoring metrics specified with alert thresholds
- [ ] Dashboard operational before Phase 5 — FORGE implementation required
- [ ] Challenger model framework documented for all three models
- [ ] Shadow inference infrastructure specified (no production latency impact)

**SR 11-7 Compliance Statement**
- [ ] Model documentation sufficient for independent validator to assess models without developer present
- [ ] All limitations stated honestly — none minimized
- [ ] Ongoing monitoring framework specific and measurable, not aspirational
- [ ] Training data provenance documented for each model (to be completed at training time)

---

*BPI SR 11-7 Model Governance Pack v1.0 — Complete.*  
*Internal use only. Stealth mode active. March 5, 2026.*  
*Leads: REX, ARIA. Next document: EU AI Act Compliance Document (Art.9/13/14/17/61).*
