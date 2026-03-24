# UNIT ECONOMICS EXHIBIT
## Bridge Loan Fee Mechanics, Phase Splits, and Minimum Thresholds
### VERSION 1.0 | Bridgepoint Intelligence Inc.

---

## 1. The Fee Formula

Every bridge loan fee in LIP is computed using a single annualized formula:

```
fee = principal × (fee_bps / 10,000) × (days_funded / 365)
```

| Variable | Description | Source |
|----------|-------------|--------|
| `principal` | Bridge loan amount (USD) | Loan offer amount |
| `fee_bps` | Annualized fee rate in basis points | C2 PD model output, subject to tiered floors |
| `days_funded` | Maturity window by rejection class | Rejection taxonomy classification |

**Critical:** The fee rate is **annualized**, not flat per cycle. A 300 bps rate on a 7-day loan is NOT 3% of principal — it is `3% × (7/365) = 0.0575%` of principal.

---

## 2. Tiered Fee Floors (QUANT-Controlled)

The C2 model outputs a risk-adjusted fee rate, but it can never fall below the tiered floor:

| Principal Range | Fee Floor (bps, annualized) | Rationale |
|----------------|---------------------------|-----------|
| < $500,000 | 500 bps | Small principals generate insufficient absolute fee to cover expected-loss risk |
| $500,000 – $2,000,000 | 400 bps | Mid-tier principals: breakeven threshold for operational costs |
| ≥ $2,000,000 | 300 bps | Canonical floor (Architecture Spec v1.2, Appendix A) |

**Absolute minimum cash fee:** $150 per loan (safety net — prevents microloans from clearing the system).

---

## 3. Maturity Windows by Rejection Class

| Rejection Class | Maturity (days) | Typical Codes | Description |
|----------------|----------------|---------------|-------------|
| Class A | 3 days | AC01, AM04, RC01 | Routing/account errors — fast resolution |
| Class B | 7 days | AM05, MS03 | Systemic/processing delays |
| Class C | 21 days | AG02, MD01 | Liquidity/sanctions/investigation holds |
| BLOCK | 0 (no loan) | DNOR, CNOR, RR01-RR04, AG01, LEGL | Compliance holds — never bridged (EPG-19) |

---

## 4. Worked Examples — Fee at Each Tier and Maturity

### 4.1 Class A Loan (3-day maturity)

| Principal | Fee Rate | Fee Calculation | Total Fee |
|-----------|----------|----------------|-----------|
| $1,500,000 (minimum for Class A) | 400 bps | $1.5M × 0.04 × 3/365 | **$493.15** |
| $2,000,000 | 300 bps | $2M × 0.03 × 3/365 | **$493.15** |
| $5,000,000 | 300 bps | $5M × 0.03 × 3/365 | **$1,232.88** |

### 4.2 Class B Loan (7-day maturity)

| Principal | Fee Rate | Fee Calculation | Total Fee |
|-----------|----------|----------------|-----------|
| $700,000 (minimum for Class B) | 400 bps | $700K × 0.04 × 7/365 | **$536.99** |
| $1,000,000 | 400 bps | $1M × 0.04 × 7/365 | **$767.12** |
| $2,000,000 | 300 bps | $2M × 0.03 × 7/365 | **$1,150.68** |
| $2,890,000 (Investor Briefing example) | ~706 bps* | $2.89M × 0.0706 × 7/365 | **$3,911** |

*\*The $5,033 fee quoted in the Investor Briefing implies a 9-day duration at ~706 bps (the C2 model's risk-adjusted rate for the specific payment scenario), NOT the 300 bps floor. See Section 6 for reconciliation.*

### 4.3 Class C Loan (21-day maturity)

| Principal | Fee Rate | Fee Calculation | Total Fee |
|-----------|----------|----------------|-----------|
| $500,000 (minimum for Class C) | 400 bps | $500K × 0.04 × 21/365 | **$1,150.68** |
| $1,000,000 | 400 bps | $1M × 0.04 × 21/365 | **$2,301.37** |
| $2,000,000 | 300 bps | $2M × 0.03 × 21/365 | **$3,452.05** |

---

## 5. Deployment Phase Fee Splits

The total fee from Section 4 is split between BPI and the bank according to the deployment phase:

### 5.1 Phase Split Table

| Phase | BPI Share | Bank Share | Bank Breakdown | Income Classification |
|-------|-----------|------------|----------------|----------------------|
| **Phase 1 (Licensor)** | 30% | 70% | 70% retained by bank (bank funds 100% of capital) | **IP Royalty** |
| **Phase 2 (Hybrid)** | 55% | 45% | 30% capital return + 15% distribution premium | **Lending Revenue** |
| **Phase 3 (Full MLO)** | 80% | 20% | 0% capital return + 20% distribution premium | **Lending Revenue** |

**Tax note:** Phase 1 income is classified as IP royalty (relevant for SR&ED, HST treatment). Phase 2/3 income is lending revenue — different Canadian tax treatment applies.

### 5.2 Phase Split on a $1M / 7-day / 400 bps Loan

Total fee: $1,000,000 × 0.04 × 7/365 = **$767.12**

| Phase | BPI Earns | Bank Earns | Bank Capital Return | Bank Distribution Premium |
|-------|-----------|------------|--------------------|--------------------------|
| Phase 1 | $230.14 | $536.98 | N/A | N/A |
| Phase 2 | $421.92 | $345.20 | $230.14 | $115.06 |
| Phase 3 | $613.70 | $153.42 | $0.00 | $153.42 |

### 5.3 Phase Split on a $2.89M / 9-day / ~706 bps Loan (Investor Briefing example)

Total fee: **$5,033**

| Phase | BPI Earns | Bank Earns |
|-------|-----------|------------|
| Phase 1 | $1,509.90 | $3,523.10 |
| Phase 2 | $2,768.15 | $2,264.85 |
| Phase 3 | $4,026.40 | $1,006.60 |

---

## 6. Investor Briefing Fee Reconciliation

The Investor Briefing (v2.1) quotes a live system output:

> Advance amount: $2,890,000 | Total cost to receiver: $5,033 | Duration: 9 days

**Reconciliation:**
- Fee = $2,890,000 × (fee_bps / 10,000) × (9 / 365)
- $5,033 = $2,890,000 × fee_bps/10,000 × 0.02466
- fee_bps = $5,033 / ($2,890,000 × 0.02466) = **706 bps**

This is the **C2 model's risk-adjusted rate** for this specific payment, not the 300 bps floor. The model priced this payment higher than the floor because the underlying PD (probability of default) warranted a higher rate.

**Important for investor communications:** The 300 bps floor is the minimum. Most loans will be priced above the floor by the C2 model. The $5,033 example demonstrates risk-adjusted pricing, not floor pricing.

---

## 7. Class-Aware Loan Minimums

| Rejection Class | Minimum Principal | Rationale |
|----------------|------------------|-----------|
| Class A (3d) | $1,500,000 | P95 resolution = 7.05h — loan matures 10× before problem resolves; early repayment destroys yield; breakeven at 400bps/3d |
| Class B (7d) | $700,000 | Processing delays run close to full term; breakeven at 400bps/7d |
| Class C (21d) | $500,000 | Liquidity/sanctions holds almost always run to maturity; $500K clears fee floor |
| BLOCK | N/A | No loan offered — compliance holds are never bridged (EPG-19) |

---

## 8. LGD Methodology Flag (QUANT Review Required)

**Current approach:** Jurisdiction-based LGD (loss given default) estimates — using the enrolled bank's country to determine expected recovery rates.

**Potential issue:** Bridge loans are **payment-collateralized** — the underlying SWIFT payment IS the collateral. When the payment settles, the loan auto-repays. This means the actual LGD should be driven by the probability of the payment *permanently* failing (not settling at all), not by general bank credit recovery rates.

**Implication:** Current LGD assumptions may be overly conservative. This is good for safety (we never underprice risk), but may result in uncompetitive fee pricing at the margin. A payment-collateralized recovery model would likely produce lower LGDs and therefore lower fee rates.

**Status:** Flag only — no code change until QUANT signs off on revised LGD methodology.

---

*All constants sourced from `lip/common/constants.py` (canonical, QUANT-controlled). Fee formula implemented in `lip/c2_pd_model/fee.py`. Phase splits implemented in `lip/common/deployment_phase.py`.*
