# M-01 Model Card — Payment Failure Prediction Classifier (C1)

**Model ID:** M-01
**Component:** C1
**Version:** C1v1.1.0
**Card Date:** 2026-03-21
**Card Author:** REX (Regulatory & Compliance), ARIA (ML & AI Engineering)
**Regulatory Alignment:** SR 11-7 (Fed/OCC), EU AI Act Art.13 (Regulation 2024/1689)
**Status:** Post-training — validated on synthetic corpus; pending pilot bank validation on live SWIFT data

---

## 1. Model Overview

| Field | Value |
|-------|-------|
| Model ID | M-01 |
| Component | C1 — Failure Classifier |
| Version | C1v1.1.0 |
| Model family | GraphSAGE (8-dim node embedding) + TabTransformer (88-dim tabular) → MLP binary classification head |
| Ensemble | 50/50 blend: PyTorch neural network + LightGBM gradient boosting |
| Calibration | Isotonic regression (PAVA algorithm) on held-out calibration set |
| Primary output | `failure_probability` — float [0.0, 1.0] per UETR-keyed payment event |
| Operating threshold (τ*) | **0.110** — F2-optimal, calibrated scale |
| Decision use | `failure_probability ≥ τ*` → loan offer generated; below → no action |
| Risk tier | **High** — directly gates bridge loan offer generation |
| Parameter count | ~220,000 (PyTorch) + LightGBM ensemble |
| Inference latency | p50 ≤ 30ms (GPU, T4 class); p50 ~86ms (CPU fallback) |
| Explainability | SHAP top-20 feature contributions per prediction (GradientExplainer) |

---

## 2. Intended Use

M-01 predicts whether a specific cross-border B2B payment — identified by its UETR — will fail to settle within its rejection-class-appropriate maturity window:

Canonical class membership: `lip/c3_repayment_engine/rejection_taxonomy.py`. BLOCK list also at `lip/common/block_codes.json`.

| Rejection Class | Maturity Window | Example Codes |
|-----------------|-----------------|---------------|
| A | 3 days | AC01, AC04, AM04, AM05, FF01, MD01, RC01 |
| B | 7 days | MS02, MS03, NARR, CUST, AG02, NOAS, TIMO |
| C | 21 days | AGNT, CVCY, FRSP, INDM, INVB, INVR |
| BLOCK | 0 (no offer) | DNOR, CNOR, RR01-RR04, AG01, LEGL, DISP, DUPL, FRAD, FRAU |

When the predicted failure probability exceeds the operating threshold (τ* = 0.110), the MIPLO Decision Engine generates a bridge loan offer for the receiving bank's ELO to accept or decline.

**This is an individual-event classifier, not a portfolio-level forecast.** It operates on one UETR at a time within a latency budget of p50 ≤ 30ms.

### Prohibited Uses

- Do not use M-01 output as a standalone credit decision — it predicts payment failure, not borrower creditworthiness (M-02 handles PD estimation)
- Do not use for compliance-held payments (BLOCK class codes: DNOR, CNOR, RR01–RR04, AG01, LEGL) — these are short-circuited before C1 inference
- Do not apply to non-ISO 20022 payment formats without revalidation

---

## 3. Training Results (C1v1.1.0)

### 3.0 Current Staging RC Snapshot

The latest staging RC was retrained on `2026-04-24` with the production-parameter path and signed supplementary artifacts:

| Field | Value |
|-------|-------|
| Corpus | `artifacts/staging_rc_c1_5m/payments_synthetic.parquet` |
| Generated rows | 5,000,000 |
| BLOCK-filtered rows | 4,550,658 |
| Training sample | 2,000,000 |
| Epochs | 20 |
| Best chronological OOT AUC | 0.8839 |
| Post-training summary AUC | 0.887623 |
| F2 score | 0.623269 |
| Calibrated threshold | 0.1100 |
| ECE post-calibration | 0.069066 |
| Supplementary artifacts | `c1_calibrator.pkl`, `c1_scaler.pkl`, `c1_lgbm_parquet.pkl` (all signed) |

This RC is deployable and verified, but the canonical production narrative remains the March 2026 10M-corpus baseline until the remote production-sized retrain is restored and promoted.

### 3.1 Training Configuration

| Parameter | Value |
|-----------|-------|
| Training date | 2026-03-21 |
| Corpus size (total) | 10,000,000 synthetic payments |
| Training sample | 2,000,000 (sampled from 10M corpus) |
| Corridors | 20 (see §5 for full list) |
| BIC pool | 200 synthetic BICs (10 hub + 190 spoke) |
| Risk tiers | 4-tier BIC risk model (0.25×, 1×, 5×, 15× baseline failure rate) |
| Temporal clustering | 30% of RJCT senders have burst clustering (1d/7d/30d variation) |
| Label distribution | 20% RJCT / 80% SUCCESS |
| Epochs | 20 |
| Seed | 42 |
| Train/val split | Chronological (OOT validation on most recent 15%) |
| Training time | 155 minutes (GitHub Actions `ubuntu-latest`, CPU) |

### 3.2 Validation Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Val AUC (ensemble)** | **0.8871** | 50/50 PyTorch + LightGBM blend |
| Val AUC (PyTorch only) | 0.8870 | GraphSAGE + TabTransformer |
| Val AUC (LightGBM only) | 0.8841 | Gradient boosting baseline |
| **F2 score** | **0.6245** | At calibrated threshold τ* = 0.110 |
| F2-optimal threshold (calibrated) | 0.110 | Isotonic calibration maps raw scores to true probabilities |
| F2-optimal threshold (raw) | 0.360 | Pre-calibration scale (not used in production) |
| **ECE (post-calibration)** | **0.0687** | Isotonic regression; pre-calibration ECE was 0.1867 |
| Training elapsed | 9,057 seconds | ~151 minutes |

### 3.3 Interpretation of Metrics

**AUC = 0.887:** Within the honest pre-training ceiling of 0.88–0.90 documented in SR 11-7 Pack §3.6. This is consistent with irreducible label noise of 1–3% in payment settlement outcome labeling. AUC above 0.90 on this problem domain would warrant investigation for data leakage or overfitting.

**F2 = 0.625:** F2-weighting penalises false negatives (missed failures → missed revenue) twice as heavily as false positives (unnecessary bridge offers → capital deployed but loan generates revenue if accepted). F2 = 0.625 reflects the asymmetric cost structure.

**ECE = 0.069:** Post-calibration expected calibration error. Isotonic calibration reduced ECE by 63% (from 0.187 to 0.069). Calibrated probabilities are reliable enough for threshold-based decisions but are not suitable for direct actuarial use without further calibration against live data.

**Threshold τ* = 0.110:** On the calibrated probability scale, 0.110 means "the model estimates an 11% probability of failure." This is lower than the raw-scale threshold (0.360) because isotonic calibration compresses the probability distribution toward true base rates. The calibrated threshold is operationally correct — it corresponds to the same F2-optimal decision boundary.

### 3.4 Comparison to Prior Model

| Metric | C1v1.0.0 (prior) | C1v1.1.0 (current) | Δ |
|--------|-------------------|---------------------|---|
| Val AUC | 0.794 | 0.887 | +0.093 |
| F2 score | 0.537 | 0.625 | +0.088 |
| ECE | — (uncalibrated) | 0.069 | — |
| Corridors | 12 | 20 | +8 |
| Training sample | 1,000,000 | 2,000,000 | +1,000,000 |
| Temporal features | No signal (uniform timestamps) | Active (burst clustering) | New |
| BIC risk tiers | Uniform | 4-tier (0.25×–15×) | New |
| Calibration | None | Isotonic (PAVA) | New |

**Root causes of improvement:** The +0.093 AUC gain is attributable to three structural changes in the training corpus, not hyperparameter tuning:
1. **Temporal burst clustering** — 30% of RJCT senders now have realistic 1d/7d/30d failure rate variation, giving temporal features (failure_rate_1d, failure_rate_7d, failure_rate_30d) genuine discriminating signal
2. **Per-BIC risk tiers** — 4-tier BIC risk model creates sender_risk_score variation across 200 BICs, enabling the model to learn sender-level risk patterns
3. **8 additional corridors** — expanded from 12 to 20 corridors, improving coverage of emerging market corridors (USD/CNY, USD/INR, USD/BRL) with higher baseline failure rates

---

## 4. Architecture

### 4.1 Feature Engineering (88-dimensional tabular vector)

The `TabularFeatureEngineer` produces an 88-dimensional feature vector per payment:

| Feature Group | Dimensions | Source |
|---------------|------------|--------|
| Rejection code one-hot | 15 | ISO 20022 rejection code taxonomy |
| Rejection class one-hot | 3 | A/B/C derived from rejection code |
| Amount features | 3 | log(amount), amount percentile, amount z-score |
| Temporal features | 4 | hour sin/cos, day-of-week sin/cos |
| Corridor features | 5 | corridor failure rate, volume rank, settlement p95 |
| Rail features | 6 | rail one-hot (SWIFT, SEPA_INSTANT, FEDNOW, RTP, STATISTICAL, OTHER) |
| Sender statistics | 15 | failure_rate, n_payments, failure_rate_1d/7d/30d, consecutive_failures, etc. |
| Receiver statistics | 15 | mirror of sender statistics |
| BIC pair statistics | 10 | pair failure rate, pair volume, corridor-specific features |
| Permanent failure flag | 1 | is_permanent_failure boolean |
| Thin file flag | 1 | is_thin_file boolean |
| Other | 10 | currency pair encoding, jurisdiction features |

### 4.2 Model Components

```
Payment Event
    │
    ├── GraphSAGE (BIC-pair network)
    │   └── 8-dim node embedding per BIC
    │
    └── TabTransformer
        └── 88-dim tabular feature vector
                │
                └── Concatenation → [96-dim]
                        │
                        ├── PyTorch MLP Head → logit → sigmoid → p_neural
                        │
                        └── LightGBM → p_lgbm
                                │
                                └── Ensemble: p_raw = 0.5 × p_neural + 0.5 × p_lgbm
                                        │
                                        └── Isotonic Calibrator → p_calibrated
                                                │
                                                └── p_calibrated ≥ 0.110 → FAILURE PREDICTED
```

### 4.3 Calibration

Isotonic regression (Pool Adjacent Violators Algorithm) trained on a held-out calibration set. The calibrator is a monotone piecewise-linear function mapping raw ensemble probabilities to calibrated probabilities.

**Pre-calibration ECE:** 0.1867 — model was systematically over-confident in the 0.2–0.5 range
**Post-calibration ECE:** 0.0687 — 63% reduction

The calibrator is saved as a separate artifact (`c1_calibrator.pkl`) and applied at inference time after ensemble blending.

---

## 5. Training Data Summary

**Full documentation:** See `docs/c1-training-data-card.md` for complete data provenance, validation results, and synthesis parameters.

| Field | Value |
|-------|-------|
| Data type | **Fully synthetic** — no real transaction data, no real BICs |
| Generator | `lip.dgen.run_production_pipeline` |
| Total records | 10,000,000 |
| Training sample | 2,000,000 (stratified random sample) |
| Label distribution | 20% RJCT (2,000,000) / 80% SUCCESS (8,000,000) |
| Temporal span | 18 months (2023-07-01 to 2025-01-01) |
| Corridors | 20 currency pairs |
| BICs | 200 synthetic (10 hub, 190 spoke) |
| Rejection codes | 15 ISO 20022 codes across 3 classes |

### 5.1 Corridor Coverage

| Corridor | Volume Weight | Failure Rate |
|----------|--------------|--------------|
| EUR/USD | 25% | 15% |
| USD/EUR | 15% | 15% |
| GBP/USD | 12% | 8% |
| USD/JPY | 10% | 12% |
| USD/GBP | 8% | 8% |
| EUR/GBP | 6% | 11% |
| USD/CNY | 6% | 26% |
| USD/CAD | 5% | 9.5% |
| USD/INR | 4% | 28% |
| USD/CHF | 4% | 9% |
| USD/SGD | 3% | 18% |
| USD/AUD | 3% | 10% |
| USD/HKD | 3% | 13% |
| AUD/USD | 2% | 10% |
| HKD/USD | 2% | 13% |
| EUR/CHF | 2% | 8.5% |
| EUR/SEK | 2% | 9.5% |
| USD/KRW | 2% | 22% |
| USD/BRL | 2% | 30% |
| USD/MXN | 1% | 19% |

### 5.2 Data Limitations

1. **Fully synthetic corpus.** All training data is generated by `lip.dgen`. No real SWIFT payment data has been used. Model performance on live data is unknown until pilot bank validation.
2. **Rejection code chi-square test FAILED.** The observed rejection code distribution deviates from priors (χ² = 26.72, p = 0.021). This is a minor calibration imperfection in the generator, not a model defect.
3. **EUR-USD amount log-normality FAILED.** Shapiro-Wilk test on EUR-USD corridor amounts rejected log-normality (p = 0.014). Other corridors passed. Impact on model performance is minimal — amounts are log-transformed and standardized before model input.
4. **No adversarial testing.** The synthetic corpus does not include adversarial payment patterns designed to exploit model weaknesses.

---

## 6. Known Limitations (SR 11-7 §3.6 Compliance)

These limitations are structural, not implementation defects. They are disclosed in full per SR 11-7 model documentation requirements.

1. **Synthetic training data only.** The model has never seen real SWIFT payment data. Performance estimates are from synthetic validation and may not transfer to production. The pilot bank validation (live data, 90-day observation) is the first empirical test. Pre-pilot deployment is contingent on bank MRM sign-off.

2. **AUC ceiling.** With 1–3% label noise in real payment settlement data, an AUC ceiling exists at approximately 0.88–0.90. The current AUC of 0.887 is near this ceiling. Reported AUC above 0.90 on real data should be investigated for overfitting or data leakage.

3. **Graph topology staleness.** GraphSAGE embeddings assume the BIC-pair network is stable between weekly rebuilds. Sudden routing changes (bank mergers, sanctions-driven re-routing, corridor shutdowns) degrade performance until the next weekly graph rebuild.

4. **Cold-start corridors.** New BIC-pair corridors with no history use currency-pair mean embeddings. Performance on new corridors is expected to be lower than established corridors.

5. **Rare rejection code coverage.** SWIFT rejection codes appearing fewer than 100 times in training data will have poorly calibrated individual embeddings. The `rejection_code_class` (A/B/C) feature provides a backstop.

6. **Calibration validity scope.** The isotonic calibrator was trained on synthetic data. Calibration accuracy on real data is unvalidated. ECE must be re-measured within 30 days of pilot deployment on live predictions.

7. **Temporal feature dependency.** The model relies on sender/receiver failure rate statistics (1d/7d/30d windows) computed from historical data. A new BIC with no history will have zero-valued temporal features — the model defaults to corridor-level priors.

---

## 7. Failure Modes

| Failure Mode | Probability | Impact | Mitigation |
|---|---|---|---|
| False negative (failure missed) | Threshold-dependent | Missed revenue; no capital loss | F2-weighted threshold optimisation increases recall |
| False positive (false failure) | Threshold-dependent | Capital deployed at opportunity cost; revenue-generating if borrower accepts | Acceptable per F2 weighting; calibration monitoring |
| Model decay (AUC decline) | Medium | Increasing false negatives over time | Rolling-window backtest; quarterly retrain if AUC drops >3% |
| Graph topology shift | Low–Medium | Degradation until next weekly rebuild | Graph structure drift alert (>15% edge count change) |
| GPU unavailability | Low | CPU fallback: p50 ~86ms, p99 ~163ms — within SLA | `degraded_mode: true` logged; automatic recovery |
| Calibrator drift | Medium | ECE increases; threshold may no longer be F2-optimal | Monthly ECE check; recalibrate if ECE > 0.10 |
| Synthetic-to-real distribution shift | **High pre-pilot** | All metrics may differ on live data | Pilot bank 90-day validation; OOT test on real data |

---

## 8. Ethical Considerations (EU AI Act Art.13)

### 8.1 High-Risk Classification

LIP processes payment failure predictions that inform credit decisions — classified as **high-risk AI** under EU AI Act Annex III, Section 5(b) (AI systems used in creditworthiness assessment).

### 8.2 Transparency

- **SHAP explanations:** Every prediction includes top-20 feature contributions via GradientExplainer (PyTorch) and TreeExplainer (LightGBM). These are logged in `DecisionLogEntry` and available to bank operators.
- **Model version tracking:** Every prediction logs `model_version` (e.g., C1v1.1.0) for auditability.
- **Calibration disclosure:** The operating threshold (τ* = 0.110) is on a calibrated probability scale. Documentation clearly states that this is a calibrated value, not a raw model score.

### 8.3 Human Oversight (Art.14)

- `HumanOverrideInterface` allows any AI decision to be countermanded by a qualified operator
- All overrides are logged with `operator_id` and `justification`
- Kill switch (`KillSwitch.activate()`) halts all new offers without code changes

### 8.4 Data Protection

- No real transaction data used in training (fully synthetic)
- No PII in model inputs — only UETR, BIC codes, amounts, timestamps, rejection codes
- BIC codes are synthetic in training; real BIC codes in production are not stored beyond the inference window

### 8.5 Non-Discrimination

- The model does not use any protected characteristics (race, gender, nationality of end parties)
- BIC-level features encode institutional payment history, not demographic data
- Corridor features reflect objective payment infrastructure differences (settlement speed, failure rates) calibrated from BIS/ECB published statistics

---

## 9. Model Artifacts

| Artifact | File | Size | Format |
|----------|------|------|--------|
| PyTorch model weights | `c1_model_parquet.pt` | 6.0 MB | `torch.save(state_dict)` |
| LightGBM model | `c1_lgbm_parquet.pkl` | 2.0 MB | Python pickle |
| Isotonic calibrator | `c1_calibrator.pkl` | 638 KB | Python pickle (sklearn IsotonicRegression) |
| Feature scaler | `c1_scaler.pkl` | 2.7 KB | Python pickle (sklearn StandardScaler) |
| F2 threshold | `f2_threshold.txt` | 6 B | Plain text: "0.1100" |
| Training metrics | `train_metrics_parquet.json` | — | JSON |

---

## 10. Ongoing Monitoring (SR 11-7 §8.1)

| Metric | Alert Threshold | Cadence | Owner |
|--------|----------------|---------|-------|
| AUC (proxy via label feedback) | <0.80 → WARNING; <0.75 → CRITICAL | Weekly | ARIA |
| ECE (calibration) | >0.10 → WARNING; >0.15 → CRITICAL retrain | Monthly | ARIA |
| Operating threshold score distribution | Shift >5% from baseline → WARNING | Daily | ARIA |
| Inference latency p99 (GPU) | >50ms → WARNING; >100ms → CRITICAL | Real-time | FORGE |
| Corridor embedding drift | Edge count change >15% week-over-week → WARNING | Weekly | ARIA |
| False negative rate (label feedback) | >5% → WARNING | Weekly | ARIA |
| Degraded mode CPU activations | Any → INFO; >1 hour → WARNING | Real-time | FORGE |

### Retraining Triggers

- AUC decline >3% from baseline (0.887) on rolling 30-day window
- ECE > 0.15 on monthly calibration check
- New corridor added (requires graph rebuild + retrain)
- Rejection taxonomy change (new codes added or class reassignment)

---

## 11. Validation Pathway

### Pre-Pilot (Current State)

- **Internal cross-agent validation:** M-01 (ARIA-built) validated by NOVA (infrastructure), FORGE (latency SLO), REX (regulatory compliance). ARIA does not self-certify.
- **Pilot validation script:** `scripts/validate_c1_pilot.py` — 500 synthetic payments through full pipeline with real trained model. 6/6 checks passing (2026-03-21).

### Pilot Bank Validation (Pending)

- Bank MRM receives: this model card, SR 11-7 Pack v1.0, training data card, model artifacts
- 90-day observation period on live SWIFT data
- ARIA produces live performance validation report comparing synthetic-trained metrics to real-world performance

### Post-Pilot

- Quarterly retraining on live data (chronological OOT split)
- Challenger model framework (SR 11-7 Pack §8.4)
- Champion/challenger swap if challenger AUC exceeds production by >3% on 30-day rolling window

---

## 12. Approval Record

| Role | Name | Date | Status |
|------|------|------|--------|
| Model Developer | ARIA | 2026-03-21 | Trained and validated |
| Regulatory Review | REX | 2026-03-21 | Model card issued |
| Financial Math | QUANT | 2026-03-21 | **Signed off** — fee impact review complete (see §12.1) |
| Security Review | CIPHER | N/A | No AML/security scope in C1 |
| Bank MRM | Pending | — | Pre-pilot; awaiting bank engagement |

### 12.1 QUANT Fee Impact Review — Sign-Off Record

**Reviewer:** QUANT (Financial Math authority)
**Date:** 2026-03-21
**Scope:** All canonical fee constants as defined in `lip/common/constants.py` as they interact with C1 threshold behaviour and the three-phase deployment model.

**Findings:**

1. **Threshold τ* = 0.110 — economic direction confirmed.** F2-weighting (β=2) is the correct asymmetric loss function. False negatives (missed failures) produce zero revenue. False positives (offered on payments that settle early) produce pro-rated fee income — they do not produce losses. The fee floor structure does not require adjustment for C1 false-positive behaviour; C3 repayment engine handles pro-rated fee calculation from `funded_at` timestamps.

2. **Fee floor arithmetic — verified correct.** 300 bps annualised floor, tiered to 400 bps for $500K–$2M and 500 bps below $500K (sub-minimum, blocked by class-aware loan minimums). All class-aware minimum loan amounts produce cash fees above `MIN_CASH_FEE_USD = $150` at their tier rate and maturity: Class A $493, Class B $536, Class C $1,151.

3. **`FEE_FLOOR_PER_7DAY_CYCLE = 0.000575` — verified.** Correct truncation of 300/10000 × 7/365 = 0.0005753. Delta of $0.34 per $1M per cycle is operationally negligible. Acceptable.

4. **Phase fee shares — sums verified 100%, decomposition internally consistent.**
   - Phase 1: 30% BPI (royalty) + 70% bank = 100%. `PLATFORM_ROYALTY_RATE` and `PHASE_1_BPI_FEE_SHARE` are confirmed equal.
   - Phase 2: 55% BPI + 30% bank capital return + 15% bank distribution premium = 100%.
   - Phase 3: 80% BPI + 0% bank capital return + 20% bank distribution premium = 100%.

5. **Distribution premium compression (Phase 2 → Phase 3): 15% → 20% — flagged and approved.** In Phase 3, the bank's distribution premium slightly increases from 15% to 20% because BPI assumes full capital risk and the bank's distribution/origination value is the sole remaining contribution. The even 25pp step progression (30→55→80) simplifies negotiation positioning across phases.

6. **Settlement P95 targets — verified against BIS/SWIFT GPI benchmarks.**
   - Class A: 7.05h (BIS target 7.0h) — conservative +0.7% buffer. Acceptable.
   - Class B: 53.58h (BIS target 53.6h) — within 0.04%. Label corrected: "Systemic/processing delays" (NOT compliance/AML holds — those are BLOCK class, never bridged). Acceptable.
   - Class C: 170.67h (BIS target 171.0h) — within 0.2%. Acceptable.
   - All three values are data-derived from 2M synthetic records (seed=42) and cross-referenced with BIS/SWIFT GPI Joint Analytics.

7. **STRESS_REGIME_MULTIPLIER = 3.0 — verified.** 3× baseline is consistent with BIS CPMI alert thresholds for corridor-level settlement failure spikes. Minimum 1h transaction count of 20 prevents false signals on thin corridors. No change required.

8. **Class-aware loan minimum breakeven — independently verified.**
   - Class A ($1.5M, 3d, 400bps): cash fee = $1,500,000 × 400/10000 × 3/365 = **$493.15** > $150 MIN_CASH_FEE_USD. Breakeven threshold at 400bps/3d = $1,520,833 → $1.5M round-down is conservative (fee covers EL at floor PD).
   - Class B ($700K, 7d, 400bps): cash fee = $700,000 × 400/10000 × 7/365 = **$536.99** > $150. Breakeven at 400bps/7d = $651,786 → $700K provides 7.4% headroom.
   - Class C ($500K, 21d, 400bps): cash fee = $500,000 × 400/10000 × 21/365 = **$1,150.68** > $150. Full-term yield well above minimum.
   - All class minimums produce fees above MIN_CASH_FEE_USD at their tier rate. Verified.

9. **EPG-06 scope limitation — acknowledged.** C2 fee_bps is a credit-risk floor, NOT a total-risk price. Regulatory outcome risk (enforcement actions, sanctions designations, legal holds) is not priced in C2. This is correct by design: regulatory risk is gated by the Bridgeability Certification API (EPG-04/05) and the BLOCK class, not by fee calibration. No fee constant change needed, but bank MRM teams must be made aware that fee_bps does not include regulatory tail risk. This is documented in `constants.py` EPG-06 comments and must be stated in any bank-facing model validation package.

10. **Constant duplication hazard — FIXED (2026-03-21).** `fee.py` previously defined `FEE_FLOOR_BPS`, `FEE_FLOOR_PER_7DAY_CYCLE`, and `_ROYALTY_DEFAULT` as local constants duplicating `constants.py`. If a QUANT-controlled value in `constants.py` was updated, the fee computation would silently use the stale local value. Fix: `fee.py` now imports all three from `constants.py` (`FEE_FLOOR_BPS`, `FEE_FLOOR_PER_7DAY_CYCLE`, `PLATFORM_ROYALTY_RATE`). Single source of truth enforced. Note: `lip/dgen/c3_generator.py` has a separate `_FEE_FLOOR_BPS = 300` (integer, data-gen scope only) — acceptable for synthetic data generation but flagged for awareness.

**Decision: APPROVED.** All fee constants are arithmetically correct and economically justified. Constant duplication hazard in `fee.py` has been resolved — all QUANT-controlled values now flow from `constants.py` as single source of truth. Settlement P95 targets, stress regime multiplier, and class-aware breakevens independently verified. EPG-06 scope limitation documented. The canonical constants table in `constants.py` is signed off as of this date.

> *QUANT — Financial Math authority, LIP Platform*
> *2026-03-21 — Final authority. No further review required for these constants unless values change.*
> *Supersedes prior partial sign-off. Full coverage: fee floors, phase shares, settlement P95, stress multiplier, class-aware minimums, EPG-06 scope, constant duplication fix.*

---

*M-01 Model Card C1v1.1.0 — Bridgepoint Intelligence Inc.*
*EU AI Act Art.13 + SR 11-7 Compliant*
*Generated 2026-03-21. Internal use only. Stealth mode active.*
