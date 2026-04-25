# `lip/c2_pd_model/` — Probability of Default + Fee Pricing

> **The component that turns a risk probability into a dollar fee.** Every canonical fee constant (`FEE_FLOOR_BPS = 300`), every tier, every LGD table, every Merton/KMV computation lives here. QUANT has final authority over anything that affects fee arithmetic.

**Source:** `lip/c2_pd_model/`
**Module count:** 13 Python files, 3,574 LoC
**Test files:** 6 (`test_c2_{api,cascade_pricing,comprehensive,fee_formula,model,pd_model}.py`)
**Spec:** [`../specs/BPI_C2_Component_Spec_v1.0.md`](../specs/BPI_C2_Component_Spec_v1.0.md)
**Model card:** [`../../models/c2-model-card.md`](../../models/c2-model-card.md)

---

## Purpose

C2 prices credit risk at the **correspondent bank (BIC) level**, per EPG-14. Given:

- A payment context — amount, corridor, sending/receiving BIC, timestamp, jurisdiction
- A borrower context — financial statements, transaction history, entity metadata

It returns:

```python
{
    "pd_score": 0.032,           # annualized probability of default, ∈ [0, 1]
    "fee_bps": 347,              # annualized fee in bps, >= 300 floor
    "tier": 1,                   # borrower tier (1/2/3)
    "shap_values": [...],        # per-feature contribution for transparency
    "borrower_id_hash": "...",   # SHA-256 salted hash — no raw tax IDs persisted
}
```

The **borrower is the bank**, not the bank's end customer (EPG-14). C2 does not see the end-customer credit risk.

---

## Canonical invariants (QUANT-locked)

All of these are in `lip/common/constants.py` and must not change without QUANT sign-off:

| Constant | Value | Where enforced |
|----------|-------|----------------|
| `FEE_FLOOR_BPS` | 300 | `fee.py::apply_fee_floor` |
| `FEE_FLOOR_PER_7DAY_CYCLE` | 0.000575 | Derived: `300/10000 × 7/365 = 0.000575` |
| Maturity CLASS_A | 3 days | `lip/c3_repayment_engine/rejection_taxonomy.py` |
| Maturity CLASS_B | 7 days | Same |
| Maturity CLASS_C | 21 days | Same |
| BLOCK maturity | 0 days (no bridge) | Same — defense-in-depth, see EPG-19 |

Fee formula (`fee.py::compute_fee`):

```
fee_usd = loan_amount × (fee_bps / 10_000) × (days_funded / 365)
```

Do NOT apply `fee_bps` as a flat per-cycle charge. The formula is annualized time-proportionate, and `days_funded` is the **actual** time between disbursement and repayment (not the maturity window). This is checked by `test_c2_fee_formula.py`.

---

## Three-tier data architecture

From `tier_assignment.py`:

| Tier | Data richness | Typical PD | Source of information |
|------|--------------|-----------|----------------------|
| **Tier 1** | Full financial statements | ~3% | Altman Z + Merton KMV on bank balance sheet |
| **Tier 2** | Transaction history only | ~6% | Average payment size, frequency, trend, corridor risk |
| **Tier 3** | Thin-file | ~12% | Jurisdiction risk, entity age, BIC registration metadata |

`TierFeatures` dataclass carries the fields needed by each tier. `assign_tier()` decides which tier a borrower falls into based on which fields are populated.

For Tier 1 banks (the pilot target), the **300 bps floor binds** because `EL = PD × LGD ≈ 0.03 × 0.15 × 10000 = 45 bps`, which is far below 300. The floor is therefore a minimum-revenue threshold, not a risk-proportionate price. See model card § 3.2.

---

## Structural models (Tier 1 only)

### Merton KMV (`merton_kmv.py`)

Distance-to-default from asset value, debt, and asset volatility. Produces a continuous PD estimate.

```
d2 = (ln(V/D) + (r - σ²/2)×T) / (σ×√T)
PD = N(-d2)
```

Where `V` is asset value, `D` is short-term debt, `r` is risk-free rate, `σ` is asset volatility, `T` is horizon (1 year).

### Altman Z-score

Discriminant function over 5 financial ratios:
- Working capital / total assets
- Retained earnings / total assets
- EBIT / total assets
- Market cap / total liabilities
- Revenue / total assets

`training.py` fits a logistic regression from Z-score to PD on the synthetic corpus.

These are **bank-level structural credit models** — they estimate the probability that a correspondent bank becomes unable to repay a bridge loan. They are NOT consumer credit-bureau models.

---

## LGD (`lgd.py`)

Loss Given Default table keyed by sending BIC's jurisdiction. Values in `lip/c2_pd_model/lgd.py`:

| Jurisdiction | LGD | Rationale |
|--------------|-----|-----------|
| US | 0.15 | Deep resolution regime, FDIC backstop |
| GB | 0.18 | Bank of England resolution regime |
| DE / FR / NL | 0.20 | ECB Single Resolution Mechanism |
| CH | 0.22 | No formal resolution regime; SNB discretion |
| JP | 0.25 | Historically high LGD on cross-border correspondent failures |
| (default for unknown jurisdiction) | 0.45 | Conservative; forces C2 to refuse or fee-inflate until manually classified |

LGD feeds `expected_loss_bps = pd × lgd × 10000` which is compared against the fee floor.

---

## Fee decomposition (QUANT rule)

Bank fee shares MUST decompose into **capital return + distribution premium**, never as a single monolithic percentage. This is a user-facing hard rule (see feedback memory):

| Phase | BPI share | Bank share (decomposed) | Income type |
|-------|-----------|------------------------|-------------|
| Phase 1 (Licensor) | 30% (royalty) | 70% capital return | ROYALTY |
| Phase 2 (Hybrid) | 55% | 30% capital return + 15% distribution premium | LENDING_REVENUE |
| Phase 3 (Full MLO) | 80% | 0% capital return + 20% distribution premium | LENDING_REVENUE |

The distinction matters because Phase 1 is "royalty" income (passive, tax-advantaged); Phase 2+ is "lending revenue" (active, different accounting treatment). Any code path that reports bank share without the decomposition creates a Phase 3 negotiation trap. See `fee.py::PhaseShareRecord` and `test_c2_fee_formula.py::test_phase_share_decomposition`.

---

## Signed artifact loading (`api.py`)

Staging/production loads the trained PD model from a signed pickle:

| Env var | Purpose |
|---------|---------|
| `LIP_C2_MODEL_PATH` | Absolute path to `c2_model.pkl` inside the container (default `/app/artifacts/c2_trained/c2_model.pkl`) |
| `LIP_MODEL_HMAC_KEY` | HMAC key used to sign the `.pkl.sig` sidecar at generation time |

`_load_or_bootstrap_model()` in `api.py`:
1. Reads `LIP_C2_MODEL_PATH`
2. Calls `PDModel.load(path)` → internally uses `lip.common.secure_pickle.load` for integrity verification
3. On any verification failure: logs warning, returns a bootstrap model, sets `model_source="bootstrap"`
4. On success: sets `model_source="artifact"` and logs `"C2 service ready (artifact)"`

Generate the artifact with `scripts/generate_c2_artifact.py`. The current RC path supports `--corpus`, `--n-trials 50`, `--n-models 5`, `--min-auc 0.70`, and fails closed when the Tier-3 stress gate fails. Verify model source via pod logs — see [`../../operations/deployment.md`](../../operations/deployment.md) § Operator Commands.

---

## Feature engineering (`features.py`)

`UnifiedFeatureEngineer` produces the feature vector regardless of tier. Fields that are missing for a lower-tier borrower are imputed using the tier's defaults (`tier_assignment.py::TIER_DEFAULTS`). The design choice: **one feature vector shape** across tiers, with tier-appropriate defaults, rather than three separate shapes with tier-specific models — this keeps the deployment surface simple at the cost of slight tier-boundary discontinuity.

`FeatureMasker` masks the tier indicator at inference time if the operator wants to evaluate "what would Tier X pricing look like?" for the same borrower.

---

## Training (`training.py` + `PDTrainingPipeline`)

```
Load synthetic corpus → generate_pd_training_data()
        │
        ▼
Tier stratification → train one PDModel per tier
        │
        ▼
LightGBM ensemble (n_models=5 by default, bagging)
Optuna hyperparameter tuning (n_trials=50 by default)
        │
        ▼
Cross-tier isotonic calibration
        │
        ▼
Save signed pickle (secure_pickle.dump)
        │
        ▼
Training report JSON — metrics, seed, sample count
```

Reproducible invocation:

```bash
LIP_MODEL_HMAC_KEY=$(cat .secrets/c2_model_hmac_key) \
PYTHONPATH=. python scripts/generate_c2_artifact.py \
    --hmac-key-file .secrets/c2_model_hmac_key \
    --output-dir artifacts/c2_trained \
    --corpus artifacts/staging_rc_c2/c2_corpus_n50000_seed42.json \
    --n-trials 50 --n-models 5 --min-auc 0.70
```

The defaults (n=1200, trials=2, models=2) remain fast-iteration values for staging smoke tests. The current RC uses the production-parameter path above and requires the Tier-3 stress gate to pass before it writes a signed artifact.

---

## Consumers

| Consumer | How it uses C2 |
|----------|---------------|
| `lip/pipeline.py::LIPPipeline.process_event` | Calls `c2_service.predict` after C4+C6 pass; uses `fee_bps` and `pd_score` to build `LoanOffer` |
| `lip/c7_execution_agent/` | Reads `fee_bps` from `LoanOffer`; uses it in the offer delivery payload |
| `lip/p5_cascade_engine/` | Uses `pd_score` for systemic cascade propagation (Phase 2) |
| `lip/risk/portfolio_risk.py` | Adds funded positions with `pd` + `lgd` for VaR calculation |

---

## What C2 does NOT price

| Risk | Why excluded | Where it IS priced / gated |
|------|-------------|---------------------------|
| **End-customer credit risk** | LIP has no data access to the bank's underlying originators (EPG-14) | Not priced — B2B structure means bank is on the hook regardless |
| **Regulatory outcome risk** | Not a continuous risk — binary gate | Bridgeability Certification API (EPG-04 / EPG-05) + BLOCK class |
| **FX risk** | Pilot policy: SAME_CURRENCY_ONLY | Cross-currency deferred to Phase 2 |
| **Operational risk** | Infrastructure failures, kill switch | C7 kill-switch engagement is the operational-risk response |
| **Systemic contagion** | Single-payment PD doesn't capture correlated-failure scenarios | P5 cascade engine (separate subsystem) |

Bank MRM teams reviewing C2 must understand that `fee_bps` is a **credit-risk floor**, not a total-risk price. The regulatory tail is managed contractually (warranties) and operationally (BLOCK class + kill switch), not through fee calibration.

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § Algorithm 1 step 3c
- **Spec** — [`../specs/BPI_C2_Component_Spec_v1.0.md`](../specs/BPI_C2_Component_Spec_v1.0.md)
- **Model card** — [`../../models/c2-model-card.md`](../../models/c2-model-card.md)
- **Fee-formula hardening** — [`../specs/c2_fee_formula_hardening.md`](../specs/c2_fee_formula_hardening.md)
- **EPG-14** — [`../../legal/decisions/EPG-14_borrower_identity.md`](../../legal/decisions/EPG-14_borrower_identity.md)
- **Constants** — `lip/common/constants.py` + [`configs.md`](configs.md)
