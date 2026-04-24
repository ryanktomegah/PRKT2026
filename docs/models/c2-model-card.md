# M-02 Model Card — C2 PD Model (Probability of Default)

> **Model ID:** M-02 C2v1.0.0
> **Classification:** SR 11-7 Tier 2 Model | EU AI Act Art.13 Technical Documentation
> **Status:** Pre-deployment (pending pilot bank engagement and Bank MRM review)
> **Last updated:** 2026-04-24

---

## 1. Model Overview

| Field | Value |
|-------|-------|
| **Model name** | C2 — Probability of Default (PD) Model |
| **Purpose** | Estimate annualised probability of default on bridge loans extended to correspondent banks |
| **Model type** | LightGBM gradient-boosted ensemble with Optuna hyperparameter tuning |
| **Input** | BIC-level financial features, transaction history, jurisdiction risk, corridor metadata |
| **Output** | `pd_score` (calibrated PD), `fee_bps` (annualised fee in basis points, 300 bps floor) |
| **Downstream consumers** | C7 Execution Agent (loan offer generation), C3 Repayment Engine (settlement monitoring) |

### Current Staging RC

The current staging RC replaces the old toy artifact with a signed, production-parameter candidate:

| Field | Value |
|-------|-------|
| Corpus | `artifacts/staging_rc_c2/c2_corpus_n50000_seed42.json` |
| Records | 50,000 |
| Optuna trials | 50 |
| Ensemble size | 5 |
| Backend | LightGBM 4.6.0 |
| Held-out AUC | 0.931482085175773 |
| Brier | 0.03374044185210159 |
| KS | 0.7380619645214892 |
| Stress gate | Passed |

The RC artifact is signed and loaded strictly from `artifacts/c2_trained/c2_model.pkl`.

---

## 2. B2B PD Framing (EPG-14)

### 2.1 The Borrower Is the Bank

C2 prices credit risk at **correspondent bank (BIC) level** — the legal counterparty in the Master Receivables Financing Agreement (MRFA). The borrower is the originating bank (e.g., Deutsche Bank), **not** the end customer (e.g., Siemens).

Bridge loans under LIP are B2B interbank credit facilities. The MRFA obligates the originating bank to repay unconditionally at maturity, regardless of whether the underlying payment settles. This means:

- **PD = probability that the originating bank defaults on the bridge loan principal**
- For Tier 1 banks (well-documented, high capital adequacy), PD is near-zero
- The 300 bps fee floor is **revenue coverage for thin-file/high-uncertainty borrowers**, not risk pricing for Tier 1

### 2.2 What C2 Does NOT Price

| Risk Category | Priced by C2? | Why |
|---------------|---------------|-----|
| **Bank credit risk (PD on bridge principal)** | Yes | Core model purpose |
| **End-customer credit risk** | No | LIP has no contractual relationship with, or data access to, the bank's underlying originators (EPG-14) |
| **Regulatory outcome risk** | No | Probability that enforcement action, sanctions designation, or legal hold makes the loan uncollectable is not modelled. This risk is gated by the Bridgeability Certification API (EPG-04/05) and the BLOCK class, not by fee calibration (EPG-06) |
| **FX risk** | No | Pilot policy: `SAME_CURRENCY_ONLY`. Cross-currency corridors deferred to Phase 2 |
| **Operational risk** | No | Infrastructure failures, settlement system outages not priced |

**Bank MRM teams must be aware**: `fee_bps` is a **credit-risk floor**, not a total-risk price. The regulatory tail risk is managed contractually (Bridgeability Certification API warranties) and operationally (BLOCK class, kill switch), not through fee calibration.

### 2.3 BIC-Level PD Is Correct by Design

C2 prices risk at the BIC level because:

1. The MRFA legal counterparty is the enrolled bank BIC
2. Repayment obligation runs to the bank, not the end customer
3. LIP has no data access to end-customer financials (the bank's borrower portfolio is opaque to LIP)
4. AML velocity tracking (C6) operates at the composite `(BIC, debtor_account)` key independently (EPG-28) — this is a velocity gate, not a credit gate

---

## 3. Three-Tier Data Architecture

| Tier | Data Richness | PD Range | Feature Source |
|------|--------------|----------|---------------|
| **Tier 1** | Full financial data | ~3% | Altman Z-score, Merton distance-to-default, financial ratios, transaction history |
| **Tier 2** | Transaction history only | ~6% | Average payment size, frequency, trend, corridor risk |
| **Tier 3** | Thin-file | ~12% | Jurisdiction risk, entity age, BIC registration metadata |

### 3.1 Structural Models (Tier 1 Only)

- **Merton KMV**: Distance-to-default computed from asset value, debt level, and asset volatility. Produces a continuous PD estimate for banks with public financial data.
- **Altman Z-score**: Discriminant function on working capital, retained earnings, EBIT, equity/debt, revenue/assets. Maps to PD via logistic regression.

These are **bank-level structural credit models** — they estimate the probability that a correspondent bank becomes unable to repay a bridge loan. They are NOT consumer credit bureau models and do not evaluate end-customer (debtor account) creditworthiness.

### 3.2 Fee Floor Interaction

The 300 bps annualised fee floor (`FEE_FLOOR_BPS` in `constants.py`) is binding for virtually all Tier 1 banks because:

- Tier 1 PD ≈ 3% → EL = PD × LGD × 10,000
- With LGD = 15% (US jurisdiction): EL = 0.03 × 0.15 × 10,000 = 45 bps
- 45 bps < 300 bps floor → floor binds

The floor is therefore a **minimum revenue threshold**, not a risk-proportionate price, for high-quality counterparties. This is intentional: the fee must cover operational costs, platform royalty, and capital buffer even when credit risk is negligible.

---

## 4. Training Data

| Field | Value |
|-------|-------|
| **Corpus** | Synthetic (lip.dgen.c2_generator) |
| **Size** | Configurable; default 10,000 records |
| **Temporal span** | 18 months (2023-07-01 to 2025-01-01) |
| **Train/val/test split** | Chronological OOT — sorted by timestamp |
| **Label** | Binary default indicator (1 = default, 0 = no default) |
| **Tier distribution** | Balanced across Tier 1/2/3 |
| **Seed** | 42 (reproducible) |

### 4.1 Known Limitations

- Synthetic data only — no historical bank default data used
- Merton/Altman challenger baselines are heuristic scaffolds, not calibrated to actual bank default histories
- PD estimates will require recalibration when pilot bank provides real counterparty data
- No backtesting on live SWIFT pacs.002 rejection corpus

---

## 5. Fee Schedule (QUANT-Controlled)

### 5.1 Tiered Fee Floors

| Principal | Floor (bps, annualised) |
|-----------|------------------------|
| < $500K | 500 bps |
| $500K – $2M | 400 bps |
| >= $2M | 300 bps (canonical floor) |

### 5.2 Class-Aware Loan Minimums

| Rejection Class | Maturity | Minimum Loan | Cash Fee at Floor |
|-----------------|----------|-------------|-------------------|
| Class A (routing/account errors) | 3 days | $1,500,000 | $493.15 |
| Class B (systemic/processing) | 7 days | $700,000 | $536.99 |
| Class C (liquidity/sanctions) | 21 days | $500,000 | $1,150.68 |
| BLOCK | 0 days | N/A | N/A (never bridged) |

### 5.3 Per-Cycle Fee Formula

```
fee = loan_amount * (fee_bps / 10,000) * (days_funded / 365)
```

This is a **time-proportionate annualised rate**. Do NOT apply fee_bps as a flat per-cycle charge.

### 5.4 Three-Phase Deployment Fee Shares

| Phase | BPI Share | Bank Share | Income Type |
|-------|-----------|------------|-------------|
| Phase 1 (Licensor) | 30% (royalty) | 70% | ROYALTY |
| Phase 2 (Hybrid) | 55% | 30% capital return + 15% distribution premium | LENDING_REVENUE |
| Phase 3 (Full MLO) | 80% | 0% capital return + 20% distribution premium | LENDING_REVENUE |

---

## 6. Scope Limitations and Caveats

### 6.1 EPG-06: Credit-Risk Floor, Not Total-Risk Price

C2 `fee_bps` represents the credit-risk component of loan pricing only. It does not include:
- Regulatory outcome risk (gated by EPG-04/05 Bridgeability Certification API)
- Compliance-hold risk (gated by BLOCK class — never bridged)
- Operational risk (gated by kill switch and health monitoring)

A bank's MRM team reviewing C2 should assess whether additional risk overlays are needed in their internal pricing framework.

### 6.2 EPG-14: No End-Customer PD

The model has no visibility into the originating bank's end-customer portfolio. A bank with high-quality borrowers and a bank with distressed borrowers will receive the same C2 PD score if their BIC-level financials are identical. This is a structural limitation of the B2B MRFA design, not a model deficiency.

### 6.3 Temporal Leakage Mitigation

Training uses chronological OOT split (most recent records form validation/test sets). This prevents temporal information leakage. However:
- Current corpus is synthetic — real temporal patterns (seasonality, macro cycles) are not captured
- When pilot data arrives, the OOT split will naturally partition pre/post-deployment observations
- Stratified random split remains available as a fallback for unit tests (when no timestamps are provided)

---

## 7. Deployment Artifact Loading

### 7.1 Signed Pickle Contract

The deployed C2 service loads a **signed pickle** pair at boot:

| File | Role |
|------|------|
| `artifacts/c2_trained/c2_model.pkl` | Serialised `PDModel` (LightGBM ensemble + calibration metadata) |
| `artifacts/c2_trained/c2_model.pkl.sig` | HMAC-SHA256 signature over the pickle bytes |
| `artifacts/c2_trained/c2_training_report.json` | Non-secret training metadata (metrics, seed, sample count) |

Signature verification uses `LIP_MODEL_HMAC_KEY` (≥32 bytes). If the signature does not verify, `_load_or_bootstrap_model()` in `lip/c2_pd_model/api.py` falls back to an in-process bootstrap model and logs `C2 service ready (bootstrap)`. A successful artifact load logs `C2 service ready (artifact)`.

This is a **deployment-time integrity control** (SR 11-7 Principle 4 — model change management): a tampered or unsigned pickle cannot silently replace the governed artifact. The key is injected via `kubectl apply -f` of `lip-model-artifact-secret`, never materialised on disk in the pod.

### 7.2 Generation

```bash
# Requires LIP_MODEL_HMAC_KEY (or --hmac-key-file)
PYTHONPATH=. python scripts/generate_c2_artifact.py \
    --hmac-key-file .secrets/c2_model_hmac_key \
    --output-dir artifacts/c2_trained \
    --corpus artifacts/staging_rc_c2/c2_corpus_n50000_seed42.json \
    --n-trials 50 --n-models 5 --min-auc 0.70
```

The script writes the signed `.pkl` + `.sig` + training report. Outputs are **gitignored** under `artifacts/` — the script is the reproducible source, artifacts are rebuilt per deployment. The RC path now fails closed if the Tier-3 stress gate fails, so a signed artifact is only produced after passing both AUC and stress checks.

### 7.3 Runtime Env Vars

| Variable | Required | Purpose |
|----------|----------|---------|
| `LIP_C2_MODEL_PATH` | Optional | Absolute path to the signed pickle inside the container. Unset → bootstrap path. |
| `LIP_MODEL_HMAC_KEY` | Required when `LIP_C2_MODEL_PATH` is set | Signature verification key. Must match the key used during generation. |

Staging defaults (see [`../operations/deployment.md`](../operations/deployment.md) § Self-Hosted Staging Deployment):

```
LIP_C2_MODEL_PATH=/app/artifacts/c2_trained/c2_model.pkl
LIP_MODEL_HMAC_KEY=<from k8s secret lip-model-artifact-secret>
```

### 7.4 Model-Source Observability

`C2Service.model_source` is the canonical label (`"artifact"`, `"bootstrap"`, or `"injected"`). It is accessible programmatically (`app.state.c2_service.model_source`) and is asserted in `test_c2_api_loads_signed_artifact`. It is intentionally **not** exposed on `/health` — the model-source label is governance metadata, not a live-traffic signal.

For operational verification:

| Signal | Command | Expected |
|--------|---------|----------|
| Service log line | `kubectl -n lip-staging logs deploy/lip-c2-pd \| grep "C2 service ready"` | `C2 service ready (artifact)` on success, `(bootstrap)` on signature-verification failure or missing `LIP_C2_MODEL_PATH` |
| Artifact presence in pod | `kubectl -n lip-staging exec deploy/lip-c2-pd -- ls -l /app/artifacts/c2_trained/` | `c2_model.pkl`, `c2_model.pkl.sig`, `c2_training_report.json` |

Log output is configured by `lip/common/logging_setup.py::configure_app_logging()`, called at import time from `lip/c2_pd_model/api.py`. Default level is `INFO`; override via `LIP_LOG_LEVEL` env var.

---

## 8. Approval Record

| Role | Name | Date | Status |
|------|------|------|--------|
| Model Developer | ARIA | 2026-03-21 | Trained and validated |
| Financial Math | QUANT | 2026-03-21 | Fee schedule signed off (see C1 model card §12.1) |
| Regulatory Review | REX | 2026-03-21 | Model card issued |
| Security Review | CIPHER | N/A | No AML/security scope in C2 |
| Bank MRM | Pending | — | Pre-pilot; awaiting bank engagement |

---

*M-02 Model Card C2v1.0.0 — Bridgepoint Intelligence Inc.*
*EU AI Act Art.13 + SR 11-7 Compliant*
*Generated 2026-03-21. Internal use only. Stealth mode active.*
