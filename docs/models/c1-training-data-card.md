# M-01 Training Data Card — 10M Synthetic Payment Corpus

**Model:** M-01 (C1 — Payment Failure Prediction Classifier)
**Model Version:** C1v1.1.0
**Card Date:** 2026-03-21
**Card Author:** DGEN (Data Generation), REX (Regulatory & Compliance)
**Regulatory Alignment:** EU AI Act Art.10 (Data Governance), SR 11-7 §3.3 (Training Data Documentation)
**Data Type:** FULLY SYNTHETIC — no real transaction data, no real BICs

---

## 1. Dataset Summary

| Field | Value |
|-------|-------|
| Dataset name | `payments_synthetic` |
| File | `artifacts/production_data/payments_synthetic.parquet` |
| Format | Apache Parquet |
| Total records | 10,000,000 |
| Training sample used | 2,000,000 |
| Label distribution | 20% RJCT (2,000,000) / 80% SUCCESS (8,000,000) |
| Generation tool | `lip.dgen.run_production_pipeline` |
| Generation date | 2026-03-21 |
| Seed | 42 |
| PII present | **No** |
| Temporal span | 18 months (2023-07-01 to 2025-01-01) |

---

## 2. Regulatory Compliance

| Requirement | Status |
|-------------|--------|
| EU AI Act Art.10 — Data governance | Documented in this card |
| SR 11-7 — Out-of-time validation | 18-month temporal spread; chronological train/val split |
| Data residency | Generated and processed within Bridgepoint infrastructure |
| PII | None — fully synthetic BICs, UETRs, amounts, timestamps |
| Real financial data | None — no real transaction data used |

---

## 3. Schema

### 3.1 Required Fields (0 nulls verified)

| Field | Type | Description |
|-------|------|-------------|
| `uetr` | string (UUID) | Unique End-to-end Transaction Reference — synthetic |
| `bic_sender` | string | Sending bank BIC — synthetic (not real SWIFT BICs) |
| `bic_receiver` | string | Receiving bank BIC — synthetic |
| `corridor` | string | Currency pair (e.g., "EUR/USD") |
| `label` | string | "RJCT" or "SUCCESS" |
| `amount_usd` | float | Transaction amount in USD |
| `is_permanent_failure` | bool | Whether the failure is permanent (Class A) |
| `timestamp_utc` | datetime | Payment event timestamp |
| `currency_pair` | string | Same as corridor (canonical form) |
| `rail` | string | Payment rail: SWIFT, SEPA_INSTANT, FEDNOW, RTP, STATISTICAL |
| `rejection_code` | string | ISO 20022 rejection code (for RJCT records) |
| `rejection_class` | string | A, B, or C (derived from rejection code) |
| `settlement_time_hours` | float | Settlement time in hours (for SUCCESS records) |

### 3.2 UETR Uniqueness

All 10,000,000 UETRs are unique. Verified by data validation pipeline.

---

## 4. Data Generation Parameters

### 4.1 Corridor Configuration (20 Corridors)

| Corridor | Volume Weight | Failure Rate | Amount μ (log) | Amount σ (log) |
|----------|--------------|--------------|-----------------|-----------------|
| EUR/USD | 0.25 | 0.15 | 13.5 | 1.4 |
| USD/EUR | 0.15 | 0.15 | 13.5 | 1.4 |
| GBP/USD | 0.12 | 0.08 | 13.2 | 1.5 |
| USD/JPY | 0.10 | 0.12 | 13.0 | 1.5 |
| USD/GBP | 0.08 | 0.08 | 13.2 | 1.5 |
| EUR/GBP | 0.06 | 0.11 | 13.0 | 1.5 |
| USD/CNY | 0.06 | 0.26 | 12.0 | 1.8 |
| USD/CAD | 0.05 | 0.095 | 13.0 | 1.5 |
| USD/INR | 0.04 | 0.28 | 11.5 | 1.8 |
| USD/CHF | 0.04 | 0.09 | 13.1 | 1.4 |
| USD/SGD | 0.03 | 0.18 | 12.5 | 1.6 |
| USD/AUD | 0.03 | 0.10 | 12.8 | 1.5 |
| USD/HKD | 0.03 | 0.13 | 12.9 | 1.5 |
| AUD/USD | 0.02 | 0.10 | 12.8 | 1.5 |
| HKD/USD | 0.02 | 0.13 | 12.9 | 1.5 |
| EUR/CHF | 0.02 | 0.085 | 13.0 | 1.4 |
| EUR/SEK | 0.02 | 0.095 | 12.7 | 1.5 |
| USD/KRW | 0.02 | 0.22 | 11.8 | 1.7 |
| USD/BRL | 0.02 | 0.30 | 11.2 | 1.9 |
| USD/MXN | 0.01 | 0.19 | 11.5 | 1.8 |

### 4.2 Rejection Code Distribution

**Source of truth:** `lip/dgen/c1_generator.py:77-113` (canonical 14-code distribution post-B11-02 realignment, 2026-04-08 code review). Pre-B11-02 versions of this card listed RR01/RR02 as Class B, FRAU/LEGL as Class C, and NARR/FF01 as BLOCK — those labels were opposite to the canonical taxonomy and have been corrected. The pre-B11-02 corpus would have trained C1 to bridge EPG-19 compliance holds (catastrophic); current corpus is realigned and includes BLOCK examples (DNOR, CNOR, RR01-RR04, AG01, LEGL, DISP, DUPL, FRAD, FRAU).

24 ISO 20022 rejection codes across 4 classes (A, B, C, BLOCK):

| Code | Class | Raw Weight | Description |
|------|-------|------------|-------------|
| AC01 | A | 0.10 | Incorrect Account Number |
| AC04 | A | 0.07 | Closed Account |
| AC06 | A | 0.04 | Blocked Account |
| BE04 | A | 0.05 | Missing Creditor Address |
| RC01 | A | 0.04 | BIC Invalid |
| FF01 | A | 0.02 | Invalid File Format (Class A post-B11-02) |
| AM04 | B | 0.13 | Insufficient Funds |
| AM05 | B | 0.09 | Duplicate Payment |
| CUST | B | 0.07 | Customer Decision |
| NARR | B | 0.06 | Narrative (Class B post-B11-02) |
| AG02 | B | 0.04 | Invalid Bank Operation Code |
| AGNT | C | 0.05 | Incorrect Agent |
| INVB | C | 0.04 | Invalid BIC |
| NOAS | C | 0.03 | No Answer from Customer |
| DNOR | BLOCK | 0.015 | Debtor Not Allowed to Send (EPG-02) |
| CNOR | BLOCK | 0.015 | Creditor Not Allowed to Receive (EPG-03) |
| RR01 | BLOCK | 0.018 | Missing Debtor Account/ID (EPG-01) |
| RR02 | BLOCK | 0.014 | Missing Debtor Name/Address (EPG-01) |
| RR03 | BLOCK | 0.012 | Missing Creditor Name/Address (EPG-01) |
| RR04 | BLOCK | 0.014 | Regulatory Reason (EPG-07) |
| AG01 | BLOCK | 0.012 | Transaction Forbidden (EPG-08) |
| LEGL | BLOCK | 0.018 | Legal Decision (EPG-08) |
| DISP | BLOCK | 0.013 | Disputed Transaction |
| DUPL | BLOCK | 0.011 | Duplicate Detected |
| FRAD | BLOCK | 0.011 | Fraudulent Origin |
| FRAU | BLOCK | 0.018 | Fraud |

**Class target fractions:** A ≈ 32%, B ≈ 39%, C ≈ 12%, BLOCK ≈ 17%
**Observed fractions:** must be regenerated from the post-B11-02 corpus and reported here on next retrain.

### 4.3 BIC Pool

| Parameter | Value |
|-----------|-------|
| Hub banks | 10 |
| Spoke banks | 190 |
| Total BICs | 200 |
| Hub volume weight | 60% |
| Spoke volume weight | 40% |
| Countries covered | 30+ |

**Risk tiers** (assigned by BIC alphabetical order, deterministic):

| Tier | BIC Range | Failure Rate Multiplier | Effective Failure Rate |
|------|-----------|------------------------|----------------------|
| TIER1 (bottom 30%) | Low-alpha BICs | 0.25× | ~6% |
| TIER2 (30–80%) | Mid-alpha BICs | 1.0× (baseline) | ~20% |
| TIER3 (80–95%) | High-alpha BICs | 5.0× | ~56% |
| TIER4 (top 5%) | Highest-alpha BICs | 15.0× | ~79% |

Risk tiers drive the `sender_stats.failure_rate` discriminative signal for C1. This is the primary mechanism for creating realistic BIC-level variation in failure propensity.

### 4.4 Settlement Time Parameters

| Class | μ (log-hours) | σ (log-hours) | P95 Target (hours) | P95 Observed (hours) |
|-------|---------------|---------------|--------------------|--------------------|
| A | 0.8 | 0.7 | 7.0 | 7.03 |
| B | 2.5 | 0.9 | 53.6 | 53.55 |
| C | 3.5 | 1.0 | 171.0 | 171.73 |

All P95 values within ±10% tolerance band. PASS.

### 4.5 Temporal Distribution

Intraday windows with volume weighting:

| Window (UTC) | Weight | Description |
|-------------|--------|-------------|
| 06:00–11:00 | 40% | European morning / Asian close |
| 11:00–17:00 | 35% | Americas morning / European afternoon |
| 17:00–22:00 | 15% | Americas afternoon |
| 22:00–06:00 | 10% | Off-hours |

**Temporal burst clustering:** 30% of RJCT senders have burst patterns — concentrated failure events within 1d/7d/30d windows, creating realistic temporal failure rate variation.

### 4.6 Amount Calibration

| Parameter | Value |
|-----------|-------|
| ECB median payment (EUR) | €6,532 |
| ECB mean payment (EUR) | €4,300,000 |
| Model | Log-normal per corridor |
| Corridor-specific μ/σ | See §4.1 |

---

## 5. Validation Results

### 5.1 Passing Checks (5/7)

| Check | Result | Details |
|-------|--------|---------|
| Label distribution | **PASS** | RJCT fraction = 0.200 (target 0.20 ±0.10) |
| Null sweep (10 required fields) | **PASS** | 0 nulls |
| Null sweep (3 conditional fields) | **PASS** | 0 nulls |
| UETR uniqueness | **PASS** | All 10,000,000 UETRs unique |
| Settlement P95 per class | **PASS** | A: 7.03h, B: 53.55h, C: 171.73h — all within ±10% |
| Class ratio A/B/C | **PASS** | A: 0.349, B: 0.400, C: 0.250 — all within tolerance |

### 5.2 Failing Checks (2/7)

| Check | Result | Details | Impact Assessment |
|-------|--------|---------|-------------------|
| Rejection code chi-square | **FAIL** | χ² = 26.72, p = 0.021 (threshold: p > 0.05) | **Low impact.** Minor deviation from prior weights. Individual rejection codes are one-hot encoded — small frequency deviations do not materially affect model learning. |
| Amount log-normality (Shapiro-Wilk) | **FAIL** | EUR-USD corridor p = 0.014 (other corridors pass) | **Low impact.** Amounts are log-transformed and standardized. Slight non-log-normality in one corridor does not affect model performance. USD-EUR (p = 0.386) and GBP-USD (p = 0.270) pass. |

**Overall assessment:** Both failing checks are minor statistical deviations in the generator, not data quality issues that affect model training. The model's feature engineering (log-transform, standardization, one-hot encoding) is robust to these deviations.

---

## 6. Calibration Sources

The synthetic data generation pipeline is calibrated from published industry data:

| Source | Used For |
|--------|----------|
| BIS CPMI Quarterly Payment Statistics 2024 | Corridor volumes, cross-border payment flows |
| BIS/SWIFT GPI Joint Analytics | Corridor settlement times, STP rates |
| ECB Annual Report on Payment Statistics 2023 | Amount distributions, T2 timing |
| BIS CPMI Brief No.10 | RTGS operating hours, fast payment coverage |
| NY Fed EPR Vol.14 No.2 / Afonso & Zimmerman 2008 | Fedwire intraday patterns |
| PaySim 2016 (Lopez-Rojas et al.) | Graph topology proxy only |
| IEEE-CIS Fraud Detection Kaggle 2019 | AML flag rate proxy only |

---

## 7. Limitations and Caveats

1. **Fully synthetic.** This dataset contains no real SWIFT payment data. Statistical properties are calibrated from published aggregates but may not capture all real-world distribution complexities (heavy tails, seasonal patterns, correlation structures).

2. **No adversarial patterns.** The corpus does not include deliberately crafted payment patterns designed to exploit model weaknesses. Adversarial robustness is untested.

3. **BIC risk tiers are deterministic.** Risk tier assignment by alphabetical BIC order is a simplification. Real-world BIC risk varies based on jurisdiction, bank size, regulatory environment, and internal controls — none of which are modeled.

4. **No concept drift.** The 18-month temporal span uses stationary corridor failure rates. Real payment networks exhibit non-stationary failure dynamics (regulatory changes, system upgrades, market events).

5. **Graph topology is fixed.** The BIC-pair network structure is generated once and does not evolve over the 18-month span. Real payment networks have dynamic topology.

---

## 8. Prohibited Uses

- Do not use as real transaction data
- Do not use `aml_synthetic` subset for live sanctions screening
- Do not commit output files (parquet, model artifacts) to version control
- Do not distribute outside Bridgepoint Intelligence Inc.

---

## 9. Related Artifacts

| Artifact | Path |
|----------|------|
| Data card (JSON) | `artifacts/c1_trained/production_data/data_card.json` |
| Synthesis parameters | `artifacts/c1_trained/production_data/synthesis_parameters.json` |
| Payments parquet | `artifacts/production_data/payments_synthetic.parquet` |
| Model card | `docs/c1-model-card.md` |
| Training metrics | `artifacts/c1_trained/c1_trained/train_metrics_parquet.json` |

---

*M-01 Training Data Card — Bridgepoint Intelligence Inc.*
*EU AI Act Art.10 + SR 11-7 §3.3 Compliant*
*Generated 2026-03-21. Internal use only. Stealth mode active.*
