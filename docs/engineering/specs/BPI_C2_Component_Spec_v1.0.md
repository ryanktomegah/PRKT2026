# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 2 — UNIFIED PD ESTIMATION MODEL
## Build Specification v1.0
### Phase 1 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** ARIA — ML & AI Engineering
**Support:** REX (EU AI Act Art.13 compliance), QUANT (fee arithmetic),
             LEX (three-tier patent claim preservation)
**Status:** ACTIVE BUILD [UPDATE 2026-04-24: staging RC retrained on 50k corpus, 50 Optuna trials, 5 LightGBM models, signed artifact passed stress gate; see docs/operations/releases/staging-rc-2026-04-24.md]
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS

1.  Purpose & Scope
2.  Why Replace the Three-Model Stack
3.  Architecture Overview
4.  Three-Tier Framework Preservation (LEX requirement)
5.  Feature Specification
6.  Feature Masking & Thin-File Path
7.  LightGBM Model Specification
8.  LGD Estimation
9.  Fee Derivation from PD Output
10. Training Data Specification
11. Training Pipeline
12. Benchmark Definition (Three-Model Baseline)
13. Validation Requirements (Audit Gate 1.2)
14. SHAP Explainability Specification
15. Model Versioning & Registry
16. Known Limitations & Honest Ceiling
17. Audit Gate 1.2 Checklist

---

## 1. PURPOSE & SCOPE

C2 estimates the probability of default (PD) on a short-duration
bridge loan for a specific borrowing entity at the time a loan offer
is generated. The PD drives the risk-adjusted fee computation and
the expected loss calculation that determines whether to offer at all.

C2 replaces the existing three-model routing stack (Merton structural
model / Altman proxy model / reduced-form ratio model) with a single
unified LightGBM ensemble that handles the full borrower spectrum —
listed public companies through data-sparse SMEs — in one model.

**Target:** 10-15% accuracy improvement over three-model baseline.
ARIA is required to define "accuracy" precisely (Section 12),
measure honestly, and report the actual delta — target or not.

C2 scope:
  - PD estimation per individual UETR-keyed loan offer
  - LGD estimation (initial: jurisdiction + tier defaults)
  - Expected loss computation: EL = PD × LGD × EAD
  - Fee derivation: fee_bps from EL as proportion of advance
  - SHAP values per decision (EU AI Act Art.13)
  - Three-tier framework preserved as internalized feature (LEX)

C2 does NOT:
  - Make the lending decision (Decision Engine does)
  - Score payment failure probability (C1)
  - Screen for disputes (C4) or AML (C6)

---

## 2. WHY REPLACE THE THREE-MODEL STACK

### 2.1 The Three-Model Stack Problem

The current architecture routes each borrower to one of three models:
  - Tier 1: Merton structural model — listed public companies only
    Requires: current equity price, equity volatility, total debt
  - Tier 2: Proxy structural model — private companies with balance sheets
    Uses sector-median asset volatility as equity proxy
  - Tier 3: Reduced-form ratio model — thin-file entities
    Uses financial ratio scoring when balance sheet is unavailable

Four structural problems with this routing approach:

**Problem 1 — Routing error compounds model error.**
If an entity is misclassified into the wrong tier (e.g., a small
listed company with unreliable equity prices routed to Tier 1),
the model error is added to the routing error. Two sources of error
become one visible failure mode.

**Problem 2 — PD outputs are not calibrated across tiers.**
Tier 1 outputs a Merton distance-to-default converted to PD.
Tier 3 outputs a scoring model converted to PD.
These two numbers are not on the same probability scale. A Tier 1
PD of 0.05 and a Tier 3 PD of 0.05 do not mean the same thing.
Fee pricing based on inconsistent PD scales is incorrect pricing.

**Problem 3 — SHAP values are not comparable across tiers.**
EU AI Act Art.13 requires explainability per decision. If the model
changes based on routing, a regulator auditing two decisions from
different tiers sees different feature sets and different SHAP
structures. This creates an inconsistent audit trail.

**Problem 4 — Thin-file performance is unmeasured.**
There is no single held-out test set that covers all three tiers
simultaneously. Each tier's model is evaluated separately. The
system-level PD accuracy — across the full borrower population
as it would be encountered in deployment — has never been measured.
The 10-15% improvement target is relative to this unmeasured baseline.

### 2.2 The Unified Model Solution

One LightGBM model with learned feature masking handles all tiers.
- Missing features → explicit missingness indicators (not imputed silently)
- The model learns from the PATTERN of what's missing
  (a private company with no equity price is a different risk profile
  from a public company with an unavailable equity price — the model
  distinguishes these via the availability indicators)
- Single calibrated PD output across all entity types
- Consistent SHAP structure for all decisions

The three-tier framework is preserved as an INTERNALIZED FEATURE
(see Section 4) — the tier assignment remains a first-class input
to the model, satisfying LEX's patent claim requirement.

---

## 3. ARCHITECTURE OVERVIEW

```
Input: PDRequest (per loan offer, per individual UETR)
  entity_tax_id_hash, entity_type, jurisdiction,
  annual_revenue_usd (0 if unavailable),
  existing_exposure_usd, requested_amount_usd,
  rejection_code_class, maturity_days, is_thin_file

         |
         v
+------------------------------+
|  TIER ASSIGNMENT LAYER       |
|  (deterministic, not learned)|
|                              |
|  Tier 1: listed public co.   |
|    (equity data available)   |
|  Tier 2: private, balance    |
|    sheet available           |
|  Tier 3: thin-file / sparse  |
+------------------------------+
         |
         v  tier + all features + availability indicators
+------------------------------+
|  FEATURE ENGINEERING LAYER  |
|  - Compute derived features  |
|  - Apply missingness masks   |
|  - Log-transform amounts     |
|  - Encode categoricals       |
+------------------------------+
         |
         v  feature_vector [~120 features]
+------------------------------+
|  LIGHTGBM ENSEMBLE          |
|  - 5 trees, soft voting      |
|  - Calibrated output         |
+------------------------------+
         |
         v
+------------------------------+
|  CALIBRATION LAYER          |
|  (Platt scaling, fit on val) |
+------------------------------+
         |
   pd_estimate [0-1]      lgd_estimate [0-1]
         |                       |
         +-----------+-----------+
                     |
         expected_loss_usd = pd * lgd * ead
                     |
         fee_bps = f(expected_loss, maturity_days)
                     |
         SHAP values [top 20]
```

---

## 4. THREE-TIER FRAMEWORK PRESERVATION (LEX)

**LEX requirement:** Dependent Claim D5 in the Provisional Spec v5.1
covers the tiered PD framework as a patent element. The unified model
must not abandon or obscure the three-tier structure — it must
internalize it as an explicit first-class feature.

### 4.1 Tier Assignment (Deterministic)

Tier assignment is a deterministic pre-processing step, not a model
prediction. It is based solely on data availability:

```
Tier 1 — Structural (Listed Public Company):
  Condition: equity_price_available = true
             AND equity_volatility_available = true
  Data source: stock exchange API (populated at enrollment)
  Merton distance-to-default computed as FEATURE (not used for routing)

Tier 2 — Proxy Structural (Private Company, Balance Sheet Available):
  Condition: Tier 1 not met
             AND balance_sheet_available = true
             AND annual_revenue_usd > 0
  Sector-median asset volatility used as proxy
  Altman components computed as FEATURES where available

Tier 3 — Reduced-Form (Thin-File / Data-Sparse):
  Condition: Tier 1 not met AND Tier 2 not met
  is_thin_file = true
  Financial ratio scoring features only (no balance sheet)
```

### 4.2 Tier as Model Feature

```
tier_encoding: float[3]  // One-hot: [1,0,0], [0,1,0], [0,0,1]
```

This is a mandatory feature in the LightGBM model. The model
learns tier-specific risk patterns while maintaining one unified
PD output. This satisfies LEX's requirement that the tiered
framework is explicit and not implied.

**Patent claim language preserved:**
"a tiered probability-of-default estimation framework that selects
the appropriate methodology based on the data available for each
specific counterparty" — the tier assignment step is the methodology
selection. The LightGBM model IS the methodology, unified across tiers.

---

## 5. FEATURE SPECIFICATION

### 5.1 Universal Features (All Tiers)

These features are available for every borrower regardless of tier.
No missingness expected for these.

```
// Entity classification
entity_type_emb           : float[4]    // PUBLIC, PRIVATE, SME, FINANCIAL
jurisdiction_emb          : float[16]   // ISO 3166-1 alpha-2
industry_sector_emb       : float[16]   // NAICS 2-digit sector code
entity_age_years          : float       // Years since incorporation
tier_encoding             : float[3]    // One-hot tier [1/2/3]

// Exposure
requested_amount_usd_log  : float       // log1p(requested_amount_usd)
existing_exposure_usd_log : float       // log1p(existing_exposure_usd)
exposure_concentration    : float       // requested / (existing + requested)

// Loan characteristics
rejection_code_class_enc  : float[3]    // One-hot A/B/C
maturity_days_enc         : float[3]    // One-hot 3/7/21
maturity_amount_interaction: float      // maturity_days * amount_log

// Jurisdiction risk
country_gdp_growth        : float       // Most recent annual GDP growth
country_default_rate      : float       // Sovereign credit rating proxy
country_banking_score     : float       // World Bank financial stability

// Network history (from C6 velocity data, anonymized)
entity_prior_bridge_count : int         // Number of prior bridges (0 if new)
entity_prior_default_rate : float       // Entity-specific default rate if known
                                        // 0.0 if no history
entity_history_available  : float       // 0/1 availability indicator

TOTAL: ~55 universal features
```

### 5.2 Tier 1 Features (Listed Public Company)

```
// Merton distance-to-default components
equity_price_usd          : float       // Current equity price
equity_volatility_30d     : float       // 30-day historical volatility
equity_volatility_180d    : float       // 180-day historical volatility
market_cap_usd_log        : float       // log1p(market_cap)
total_debt_usd_log        : float       // log1p(total_debt)
debt_to_equity            : float       // Leverage ratio
merton_dd                 : float       // Computed Merton distance-to-default
                                        // = (log(V/D) + (μ - σ²/2)T) / (σ√T)
                                        // Using sector-median μ if unavailable

// Altman Z-score components (listed version)
working_capital_ratio     : float       // Working capital / total assets
retained_earnings_ratio   : float       // Retained earnings / total assets
ebit_ratio                : float       // EBIT / total assets
market_equity_ratio       : float       // Market cap / total liabilities
sales_ratio               : float       // Sales / total assets
altman_z_listed           : float       // Computed Z-score

// Tier 1 availability indicators
merton_dd_available       : float       // 0/1
altman_z_listed_available : float       // 0/1

TIER 1 FEATURES: ~15 features
```

### 5.3 Tier 2 Features (Private, Balance Sheet Available)

```
// Proxy Merton (no observable equity price)
sector_median_asset_vol   : float       // From industry database
book_equity_usd_log       : float       // Book value of equity
total_assets_usd_log       : float
debt_ratio                : float       // Total debt / total assets
current_ratio             : float       // Current assets / current liabilities
quick_ratio               : float       // (Current assets - inventory) / CL
interest_coverage         : float       // EBIT / interest expense

// Altman Z-score (private version — book value of equity, not market)
altman_z_private          : float       // Altman Z' for private companies

// Revenue-based
annual_revenue_usd_log    : float       // log1p(annual_revenue_usd)
revenue_growth_yoy        : float       // Year-over-year growth if available
ebitda_margin             : float       // If available from accounting API
net_profit_margin         : float       // If available

// Tier 2 availability indicators
balance_sheet_available   : float       // 0/1
revenue_available         : float       // 0/1
ebitda_available          : float       // 0/1

TIER 2 FEATURES: ~17 features
```

### 5.4 Tier 3 Features (Thin-File / Data-Sparse)

```
// What's available for thin-file entities
annual_revenue_usd_log    : float       // If available (0 if not)
revenue_available         : float       // 0/1 indicator
estimated_revenue_band    : float[5]    // <500K, 500K-2M, 2M-10M, 10M-50M, >50M
                                        // Estimated from transaction volume
transaction_volume_90d    : float       // Via C6 cross-licensee data (hashed)
industry_sector_default_rate: float     // Sector-level default rate (external)
jurisdiction_sme_default_rate: float    // SME default rate by jurisdiction

// Thin-file availability indicators (all expected to be 0 for Tier 3)
balance_sheet_available   : float       // 0
equity_data_available     : float       // 0

TIER 3 FEATURES: ~9 features
```

### 5.5 Total Feature Count

Universal: ~55
Tier 1 additions: ~15
Tier 2 additions: ~17
Tier 3 additions: ~9
Availability indicators: ~12 binary flags

Total feature vector: ~108-120 features (depending on tier)
Tier 2 and 3 entities have Tier 1 features set to 0 with
availability indicators set to 0. Single vector, consistent schema.

---

## 6. FEATURE MASKING & THIN-FILE PATH

### 6.1 The Masking Strategy

For every optional feature group, two fields exist in the vector:
  - feature_value: float (set to 0 if unavailable)
  - feature_available: float (0 or 1)

This is the correct approach — do NOT use mean imputation or
median imputation for missing financial data. Missing financial
data is not "average" — a company with no balance sheet available
is a materially different risk profile from one with an average
balance sheet. Imputing the mean erases that distinction.

The LightGBM model learns that `merton_dd_available = 0` alongside
`merton_dd = 0` is a signal about the entity type, not a missing
data problem to be solved.

### 6.2 Thin-File Performance Requirement

The thin-file path (Tier 3) must be evaluated SEPARATELY from
Tier 1 and Tier 2 in Audit Gate 1.2. Performance may be lower —
that is acceptable — but it must be:
  1. Measured honestly
  2. Above a minimum acceptable threshold
  3. Documented in the model card with explicit limitations

Minimum acceptable AUC for thin-file subsample: 0.72
(Below XGBoost baseline but above random. If below 0.72:
thin-file entities get a conservative fixed PD rate rather than
model-predicted PD — documented as a system design decision.)

### 6.3 Stress Test at Data Extremes

Required: test model behavior when ALL optional features unavailable
(pure Tier 3, no revenue, no sector data, no history).

In this extreme case:
  - Model has only: entity_type, jurisdiction, maturity, amount,
    rejection_code_class, and all availability indicators = 0
  - Expected output: a conservative PD reflecting maximum uncertainty
  - Acceptable output range: PD ∈ [0.05, 0.25]
  - Unacceptable: PD < 0.02 (model is expressing false confidence)
  - Unacceptable: PD > 0.50 (model is blocking all thin-file borrowers)

If stress test fails: add a PD floor/ceiling constraint for pure
thin-file entities. Not a hack — a documented risk management control.

---

## 7. LIGHTGBM MODEL SPECIFICATION

### 7.1 Why LightGBM

Considered alternatives:

| Model          | Pros                           | Cons                          | Selected |
|----------------|--------------------------------|-------------------------------|----------|
| XGBoost        | Mature, well-calibrated        | Slower than LightGBM          | No       |
| CatBoost       | Best for categoricals          | Harder to tune, slower        | No       |
| LightGBM       | Fast, scales to 120 features,  | Requires careful leaf tuning  | YES      |
|                | native categorical support,    |                               |          |
|                | strong on tabular + mixed data |                               |          |
| Neural net     | Could learn interactions       | Overfits on small datasets,   | No       |
|                |                                | poor calibration default      |          |

LightGBM is the right choice for this feature profile (mixed
categorical/continuous, many availability indicators, ~120 features).

### 7.2 Ensemble Architecture

5 LightGBM models trained with different:
  - Random seeds
  - Subsample rates (0.7 - 0.9)
  - Feature fractions (0.7 - 0.9)
  - Num leaves (63 - 127)

Final PD output: mean of 5 model outputs (soft voting)
  - Reduces variance without changing expected prediction
  - More stable than single model for tail risks

Note: 5 models adds ~5ms to inference. Acceptable within the
p50 <5ms target for C2 (see Architecture Spec S10). If latency
budget is tight, reduce to 3 models.

### 7.3 Hyperparameter Ranges (Tuning via CV)

```
num_leaves          : [63, 127, 255]      // Primary complexity control
min_data_in_leaf    : [20, 50, 100]       // Prevents overfitting
learning_rate       : [0.01, 0.05, 0.1]
n_estimators        : [300, 500, 1000]    // With early stopping (patience=50)
subsample           : [0.7, 0.8, 0.9]
colsample_bytree    : [0.7, 0.8, 0.9]
reg_alpha           : [0, 0.1, 1.0]      // L1 regularization
reg_lambda          : [0.1, 1.0, 10.0]   // L2 regularization

Optimization: 5-fold cross-validation on training set
Metric: AUC + binary logloss (AUC for ranking, logloss for calibration)
Search: Optuna Bayesian optimization, 50 trials
```

### 7.4 Objective & Loss

```
objective: binary (cross-entropy)
class_weight: balanced
  (default rate expected ~2-8%; class weighting prevents
  the model from predicting 0 for all entities)
metric: [auc, binary_logloss]
```

### 7.5 Categorical Feature Handling

LightGBM native categorical encoding for:
  - entity_type (4 categories)
  - jurisdiction (195 possible — use LightGBM's max_cat_to_onehot)
  - industry_sector (20 NAICS 2-digit sectors)
  - rejection_code_class (3 categories)
  - maturity_days (3 values)

Native encoding is more efficient than one-hot for high-cardinality
features like jurisdiction. LightGBM builds optimal splits
across category subsets.

---

## 8. LGD ESTIMATION

### 8.1 Why LGD Matters

Expected Loss = PD × LGD × EAD

A miscalibrated LGD directly flows into wrong fee pricing.
If LGD = 0 everywhere, expected_loss_usd = 0 and fee_bps = 0
(floor applies, but the model is economically meaningless).

### 8.2 Initial LGD Framework (Pre-Pilot)

Without empirical default data, LGD is estimated from the
payment recovery pathway, not trained from observed defaults.

Three recovery pathways with different LGD profiles:

```
Pathway A — Original payment eventually settles (bridge was false positive):
  LGD ≈ 0%  (loan repaid from settlement proceeds)
  Probability: (1 - C1 failure_probability) at time of offer

Pathway B — Permanent failure, sender enforcement succeeds:
  LGD ≈ 15-30%  (accrued fees + enforcement costs, principal recovered)
  Probability: varies by jurisdiction
  Anchor: SWIFT STP permanent failure rate ≈ 3.5% midpoint

Pathway C — Permanent failure, sender unenforceable, borrower collections:
  LGD ≈ 40-65%  (significant recovery costs, possible haircut)
  Probability: subset of Pathway B where assignment fails

Blended LGD for initial deployment:
  LGD = w_A * 0.00 + w_B * 0.22 + w_C * 0.52
  Weights set by: jurisdiction enforcement quality + corridor class

Jurisdiction enforcement quality tiers:
  Tier I   (UK, US, SG, DE, FR, CA): w_B = 0.70, w_C = 0.30
  Tier II  (BR, IN, MX, ZA, TH):     w_B = 0.50, w_C = 0.50
  Tier III (high-uncertainty jurisdictions): w_B = 0.30, w_C = 0.70
```

### 8.3 LGD as Model Feature in C2

The blended LGD is a deterministic calculation, not a trained model.
It is computed from:
  - jurisdiction_enforcement_tier (lookup table)
  - rejection_code_class (Class C correlates with higher LGD)
  - entity_type (financial entities have different recovery profiles)

LGD is returned in PDResponse alongside pd_estimate.
LGD is included in SHAP computation — it is a named component of
expected_loss_usd, not a hidden parameter.

### 8.4 Post-Pilot LGD Update

After pilot data accumulates actual recovery outcomes:
  - LGD updated from observed recovery rates per pathway per jurisdiction
  - This is a Phase 5 ARIA + QUANT deliverable
  - Until then: jurisdiction-tiered defaults are used
  - Model card must document: "LGD is pre-pilot estimate, not
    empirically calibrated. Post-pilot update is planned."

---

## 9. FEE DERIVATION FROM PD OUTPUT

### 9.1 Fee Formula

As per Architecture Spec S4.3 and S7 (QUANT locked):

  fee_per_cycle = loan_amount × (fee_bps / 10000) × (days_funded / 365)

Where fee_bps is derived as:

  fee_bps = max(
    fee_floor_bps,           // 300 bps minimum — absolute floor
    (pd_estimate × lgd_estimate × 10000) / (days_funded / 365)
                             // EL-based pricing, annualized
    + risk_premium_bps       // Corridor/jurisdiction premium (10-50 bps)
    + operational_cost_bps   // Platform operating cost (15-25 bps)
  )

This formula ensures:
  1. Floor: 300 bps always applies — no loan priced below floor
  2. EL coverage: fee covers expected loss at minimum
  3. Risk premium: corridor-specific spread above EL
  4. Operational: platform cost recovery

### 9.2 Fee Arithmetic Verification (QUANT check)

At 300 bps floor, 7-day maturity, $100K loan:
  fee_per_cycle = 100,000 × (300/10000) × (7/365)
               = 100,000 × 0.03 × 0.01918
               = $57.53
               = 0.0575% of principal ✅

At PD = 0.03, LGD = 0.30, 7-day, $100K loan:
  EL = 100,000 × 0.03 × 0.30 = $900
  EL as annualized bps = (900/100,000) × (365/7) × 10000
                       = 0.009 × 52.14 × 10000 = 4693 bps
  This exceeds the floor significantly — fee_bps = 4693 + risk + ops
  This represents a high-risk borrower — correct behavior

At PD = 0.001, LGD = 0.15, 7-day, $100K loan:
  EL = 100,000 × 0.001 × 0.15 = $15
  EL as annualized bps = (15/100,000) × (365/7) × 10000 = 78 bps
  This is below floor — fee_bps = 300 bps (floor applies)
  This represents a very low-risk borrower — floor protects revenue ✅

### 9.3 Fee Bps Annotation

As per Architecture Spec S4.3, fee_bps in PDResponse is explicitly
annotated as ANNUALIZED rate. The per-cycle formula is applied
by the fee calculation layer, not by PDResponse itself.
See Architecture Spec S4.3 for the full annotation.

---

## 10. TRAINING DATA SPECIFICATION

### 10.1 Training Target Definition

**Target variable:** bridge_loan_default
  - 1 = loan not repaid within maturity_days + 30-day buffer
  - 0 = loan repaid within maturity_days + 30-day buffer

Note: this is DEFAULT ON THE BRIDGE LOAN specifically — not general
corporate default. A company that defaults on a bridge loan may be
perfectly healthy in general (they may have simply not received the
original payment that was the collateral for the bridge).

This is a subtle but important distinction:
  - General corporate PD (Merton, Altman): probability of company default
  - Bridge loan PD: probability of non-repayment on THIS specific loan
  - Bridge loan PD is lower than corporate PD for most entities
    because the collateral is a specific receivable

The model is trained to predict BRIDGE LOAN DEFAULT, not corporate
default. This must be explicit in the model card.

### 10.2 Required Dataset Schema

```
TrainingRecord {
  entity_tax_id_hash       : string    // SHA-256 — for deduplication
  entity_type              : string
  jurisdiction             : string
  industry_sector          : string
  entity_age_years         : float
  tier                     : int       // 1, 2, or 3

  // Tier 1 fields (null/0 if unavailable)
  equity_price_usd         : float
  equity_volatility_30d    : float
  market_cap_usd           : float
  total_debt_usd           : float
  // ... all Tier 1 features

  // Tier 2 fields (null/0 if unavailable)
  annual_revenue_usd       : float
  total_assets_usd         : float
  // ... all Tier 2 features

  // Availability indicators
  equity_data_available    : bool
  balance_sheet_available  : bool
  // ... all availability flags

  // Loan characteristics
  requested_amount_usd     : float
  maturity_days            : int
  rejection_code_class     : string

  // Label
  bridge_loan_default      : int       // 0 or 1

  // Metadata (not features)
  loan_date_utc            : int64     // For time-based split
  uetr                     : string    // For deduplication
}
```

### 10.3 Class Imbalance Expectation

Bridge loan default rates expected to be low (2-8% in normal conditions).
Extreme class imbalance (e.g., 98:2) requires:
  - class_weight = 'balanced' in LightGBM
  - AUC as primary metric (not accuracy — accuracy is misleading at 98:2)
  - Precision/recall at multiple thresholds reported
  - If default rate < 1% in training data: flag as insufficient data

### 10.4 Minimum Dataset Size

Target: 50,000+ loan outcomes with known default status
Minimum viable: 10,000 outcomes

At <10,000 outcomes: AUC estimates are unreliable due to
small number of actual defaults. If 2% default rate, 10,000
outcomes = only 200 actual defaults. Report confidence intervals.

Tier stratification minimum:
  - Tier 1: ≥ 2,000 examples
  - Tier 2: ≥ 5,000 examples
  - Tier 3: ≥ 3,000 examples

If any tier is below minimum: that tier uses default LGD
and conservative fixed PD until sufficient data accumulates.

### 10.5 Train / Validation / Test Split

Same protocol as C1: TIME-BASED split.
  - Train:       Oldest 70% by loan_date
  - Validation:  Next 15%
  - Test (OOT):  Most recent 15%

---

## 11. TRAINING PIPELINE

```
Stage 1: Data Validation
  - Schema check, label distribution logging
  - Deduplication by UETR
  - Tier distribution check: report count per tier
  - Default rate by tier: must be reported before training

Stage 2: Feature Engineering
  - Compute Merton DD for Tier 1 entities
  - Compute Altman Z-scores (listed + private versions)
  - Compute all ratio features
  - Set availability indicators
  - Log-transform all amount features
  - Fit normalization on training set only, persist artifact

Stage 3: Hyperparameter Optimization
  - Optuna Bayesian search, 50 trials, 5-fold CV
  - Optimize: val AUC + val logloss (weighted combination)
  - Save best hyperparameters

Stage 4: Ensemble Training
  - Train 5 LightGBM models with best hyperparameters + varied seeds
  - Save all 5 model files

Stage 5: Calibration
  - Fit Platt scaling layer on validation set outputs
  - Plot calibration curve before and after Platt scaling
  - Report ECE before and after calibration
  - If ECE < 0.03 without calibration: skip Platt, log the decision

Stage 6: Thin-File Evaluation
  - Extract Tier 3 subset from OOT test set
  - Evaluate AUC on Tier 3 subset only
  - Report separately: Tier 1 AUC, Tier 2 AUC, Tier 3 AUC

Stage 7: Stress Test
  - Create 100 synthetic extreme examples (all features unavailable)
  - Run inference, verify PD ∈ [0.05, 0.25] for all
  - If any PD outside range: apply PD floor/ceiling constraint

Stage 8: SHAP Computation
  - Use TreeExplainer (LightGBM is tree-based — TreeExplainer is exact)
  - Compute on 1,000-example sample from OOT test set
  - Verify top 20 features are interpretable, no leakage

Stage 9: Baseline Benchmark
  - Run three-model baseline on same OOT test set (Section 12)
  - Compute improvement metrics
  - Report improvement honestly (target vs. actual)

Stage 10: MLflow Logging
  - All parameters, metrics, artifacts logged
  - Model registered as C2_v1.0.0
  - Tagged "staging" pending Audit Gate 1.2
```

---

## 12. BENCHMARK DEFINITION (THREE-MODEL BASELINE)

### 12.1 The Baseline

The three-model stack is the baseline. Before it can be "beaten,"
it must be formally defined and implemented.

Baseline implementation:

```
Baseline model routing:
  IF equity_data_available: use Merton model
  ELIF balance_sheet_available: use Altman proxy model
  ELSE: use financial ratio scoring model

Merton model (Tier 1):
  DD = (log(V/D) + (r - σ²/2)T) / (σ√T)
  PD = N(-DD)  [standard normal CDF]
  Parameters: V = market cap + debt, D = total debt
              r = risk-free rate (10Y treasury), σ = equity_volatility_180d
              T = maturity_days / 365

Altman Proxy model (Tier 2):
  Z' = 0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
  X1 = working_capital / total_assets
  X2 = retained_earnings / total_assets
  X3 = EBIT / total_assets
  X4 = book_equity / total_liabilities
  X5 = sales / total_assets
  Convert Z' to PD via Platt scaling fit on training data

Ratio scoring model (Tier 3):
  score = w1*current_ratio + w2*debt_ratio + w3*revenue_growth + ...
  Convert score to PD via logistic regression fit on training data
```

### 12.2 "Accuracy" Definition

The roadmap target is "10-15% accuracy improvement." ARIA defines
this precisely as:

**Primary metric: Reduction in Mean Absolute Error (MAE) of PD vs.
actual default rate.**

MAE = mean(|predicted_pd - actual_default|) across all OOT test records.

Why MAE: pricing correctness depends on absolute PD accuracy, not
just ranking (AUC measures ranking). A model with perfect AUC but
systematically biased PDs produces wrong fees.

**Secondary metric: AUC improvement on OOT test set.**
Reported alongside MAE for completeness.

**Tertiary metric: Calibration ECE improvement.**

If the unified model achieves:
  - MAE reduction ≥ 10%: target met
  - MAE reduction 5-9%: below target, document and proceed
  - MAE reduction < 5%: escalate — may not justify replacing baseline
  - MAE INCREASE: do not deploy unified model; retain baseline

### 12.3 Tier-Stratified Benchmark

Report improvement separately by tier:
  - Tier 1 (listed): unified vs. Merton
  - Tier 2 (private): unified vs. Altman proxy
  - Tier 3 (thin-file): unified vs. ratio scoring

If unified model underperforms baseline on Tier 1 specifically
(Merton is well-established for listed companies): use Merton
for Tier 1 and unified model for Tier 2 and Tier 3.
Pragmatic hybrid is acceptable — document the decision.

---

## 13. VALIDATION REQUIREMENTS (AUDIT GATE 1.2)

### 13.1 Improvement Over Baseline (Quantified)

Compute MAE_baseline and MAE_unified on same OOT test set.
Report:
  - MAE_baseline (three-model stack)
  - MAE_unified (LightGBM ensemble)
  - Improvement = (MAE_baseline - MAE_unified) / MAE_baseline × 100%
  - Target: ≥ 10% improvement
  - Report: honest measured value

### 13.2 SHAP Logs — EU AI Act Art.13 Compliance

SHAP format must match Architecture Spec S4.3 PDResponse schema:
  shap_values: List[ShapValue{feature_name, contribution}]
  Top 20 features by |contribution|

Additional Art.13 requirements:
  - Every SHAP feature name must be human-readable (no internal codes)
  - SHAP values must sum to: log_odds(pd_estimate) [TreeExplainer property]
  - SHAP direction must be interpretable: positive = increases PD,
    negative = decreases PD
  - SHAP values for availability indicators must be included:
    (e.g., "balance_sheet_not_available" as a named SHAP feature)

### 13.3 Calibration Validation

Calibration curve on OOT test set.
ECE (Expected Calibration Error) target: < 0.04
If ECE > 0.04: apply Platt scaling, re-report ECE.
Calibration is mandatory — PD feeds fee_bps directly.

### 13.4 Thin-File Performance

AUC on Tier 3 OOT subsample: target ≥ 0.72
If below 0.72: conservative fixed PD deployed for Tier 3.
Document threshold and rationale in model card.

Thin-file performance tested at multiple data availability levels:
  - Level A: revenue available, no balance sheet
  - Level B: no revenue, no balance sheet (sector defaults only)
  - Level C: nothing available (stress test — Section 6.3)

### 13.5 Stress Test at Data Extremes

100 synthetic extreme examples (Section 6.3):
  All PD ∈ [0.05, 0.25]: pass
  Any PD outside range: add PD floor/ceiling, re-test, document

---

## 14. SHAP EXPLAINABILITY SPECIFICATION

### 14.1 SHAP Method

LightGBM is a tree ensemble → use TreeExplainer (exact, fast).
TreeExplainer is preferable to GradientExplainer for tree models.
Compute time per inference: < 2ms (TreeExplainer is highly optimized)

### 14.2 Expected Top Features (Pre-Training Hypothesis)

ARIA's expectation before training:
  1. requested_amount_usd_log (higher amounts → higher absolute risk)
  2. entity_type (financial vs. SME)
  3. pd_feature: jurisdiction_sme_default_rate or country_default_rate
  4. tier_encoding (Tier 3 carries more uncertainty → higher PD)
  5. balance_sheet_available = 0 (missingness signal)
  6. rejection_code_class (Class C failures → longer exposure → higher PD)
  7. maturity_days (21-day loans have more time for things to go wrong)
  8. entity_prior_default_rate (if history available)
  9. debt_ratio (if available)
 10. industry_sector (some sectors have higher bridge default rates)

If the actual top features deviate significantly from this list,
ARIA must explain why — either the model learned something non-obvious
(valuable insight) or there is a data leakage issue (defect).

### 14.3 Availability Indicator SHAP

The SHAP contribution of `balance_sheet_available = 0` must be
explicitly reported as a named feature: "balance_sheet_unavailable."
This is a first-class explainability output, not a model artifact
to be hidden. It demonstrates to a regulator that the model
accounts for data quality transparently.

---

## 15. MODEL VERSIONING & REGISTRY

Version format: C2_v{MAJOR}.{MINOR}.{PATCH}
First production model: C2_v1.0.0

Model artifact contents:
```
C2_v1.0.0/
  lgbm_model_1.pkl ... lgbm_model_5.pkl  // Ensemble members
  calibration_layer.pkl                  // Platt scaling params
  feature_engineering.pkl               // Normalization, encoders
  lgd_lookup_table.json                 // Jurisdiction × tier LGD
  shap_background.pkl                   // 500 background examples
  feature_importance.json               // Top 20 features
  model_card.md                         // Performance + limitations
  benchmark_results.json                // Unified vs. baseline MAE/AUC
```

Hot-swap: same canary protocol as C1 (5% traffic, 1 hour, auto-rollback).

---

## 16. KNOWN LIMITATIONS & HONEST CEILING

1. **LGD is not empirically calibrated pre-pilot.** The jurisdiction-
   tiered LGD estimates are informed defaults, not fitted parameters.
   Fee pricing accuracy is limited by LGD accuracy until pilot data
   provides observed recovery rates. Post-pilot LGD update is
   critical for commercial-quality pricing.

2. **Bridge loan PD ≠ corporate PD.** The model is trained on bridge
   loan defaults, not corporate defaults. If training data is sourced
   from general corporate default databases (a common proxy), the
   model is mis-specified. Training data must be bridge loan outcomes
   specifically, or the target variable must be adjusted.

3. **Small-sample Tier 1 risk.** Listed companies that use bridge
   loan products for cross-border payment failures are likely
   non-investment-grade (investment grade companies have credit
   facilities). The Tier 1 sample may be dominated by borderline
   cases where Merton DD is near zero — reducing the structural
   model's discriminatory power.

4. **Jurisdiction coverage.** The jurisdiction_emb embedding must
   cover all enrolled borrower jurisdictions. Rare jurisdictions
   (e.g., small island states) will have near-random embeddings.
   Jurisdiction-level features (GDP growth, banking score) partially
   mitigate this.

5. **AUC ceiling estimate:** ARIA's honest pre-training AUC estimate:
   0.80-0.87 on OOT test set. Bridge loan default prediction is
   inherently noisy at short maturities — a 3-day loan has little
   time for predictive signals to manifest.

---

## 17. AUDIT GATE 1.2 CHECKLIST

Gate passes when ALL items checked. ARIA signs. QUANT verifies fee
arithmetic. REX verifies Art.13 compliance.

**Baseline Benchmark:**
  [ ] Three-model baseline formally implemented and tested on OOT set
  [ ] MAE_baseline documented
  [ ] MAE_unified documented
  [ ] Improvement % calculated: target ≥ 10%, honest actual reported
  [ ] AUC improvement documented (secondary metric)
  [ ] Tier-stratified benchmark complete (Tier 1/2/3 separately)

**Model Performance:**
  [ ] AUC on OOT test set documented (target, honest actual)
  [ ] Precision/recall at multiple PD thresholds documented
  [ ] Calibration curve produced, ECE < 0.04 (or Platt applied)
  [ ] Train/val/test AUC gap ≤ 3%

**Thin-File:**
  [ ] Tier 3 AUC on OOT subsample documented
  [ ] Tier 3 AUC ≥ 0.72 OR conservative fixed PD deployed and documented
  [ ] Performance at Level A / B / C data availability documented

**Stress Test:**
  [ ] 100 extreme examples run
  [ ] All PD ∈ [0.05, 0.25] OR floor/ceiling constraint applied
  [ ] Constraint documented in model card if applied

**SHAP / Explainability:**
  [ ] Top 20 SHAP features documented, all human-readable
  [ ] Each top feature explained in plain language
  [ ] Availability indicators present as named SHAP features
  [ ] SHAP format matches Architecture Spec S4.3 schema
  [ ] TreeExplainer latency < 2ms verified

**Fee Arithmetic:**
  [ ] fee_bps derivation formula implemented correctly
  [ ] 300 bps floor enforced at all times
  [ ] Spot-check: 300 bps, 7-day, $100K = $57.53 fee ✅
  [ ] Spot-check: floor applies when EL-based price < 300 bps ✅

**LGD:**
  [ ] LGD lookup table populated for all deployed jurisdictions
  [ ] LGD documented as pre-pilot estimate in model card
  [ ] Post-pilot LGD update scheduled as Phase 5 deliverable

**SR 11-7:**
  [ ] Model card complete: purpose, methodology, training data,
      known limitations, failure modes, performance benchmarks
  [ ] Bridge loan PD vs. corporate PD distinction documented
  [ ] Training data provenance documented

**Gate Outcome:**
  [ ] ARIA signs: improvement over baseline documented (honest delta)
  [ ] QUANT signs: fee arithmetic correct, 300 bps floor enforced
  [ ] REX signs: SHAP logs EU AI Act Art.13 compliant

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
*Status: ACTIVE BUILD — Phase 1, Component 2*
