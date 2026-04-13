# UNIT ECONOMICS EXHIBIT
## Bridge Loan Fee Mechanics, Phase Splits, and Minimum Thresholds
### VERSION 2.0 | Bridgepoint Intelligence Inc.

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

## 2. Two-Tier Pricing Floor (CODE-ENFORCED)

LIP uses a **code-enforced two-tier pricing structure** that eliminates economic ambiguity:

| Fee Rate | Funding Source | BPI Revenue Share | Economics |
|-----------|----------------|-------------------|-----------|
| **300–799 bps** | Bank balance sheet (Phase 1) OR SPV warehouse-eligible | 30% IP royalty | Platform minimum |
| **≥ 800 bps** | SPV warehouse-funded (Phase 2/3) | 55% lending revenue | Warehouse minimum |

**Platform Floor (300 bps):** Applies to ALL loans regardless of funding source. This is the regulatory minimum.

**Warehouse Floor (800 bps):** Required for SPV-funded loans in Phase 2/3. Loans priced below 800 bps are routed to bank balance sheet (BPI earns IP royalty only). Loans at or above 800 bps are SPV-eligible.

**Why 800 bps?**

At 800 bps annualized:
- Asset yield = 8% on $1M loan ($80K/year per $1M)
- SPV capital structure: ~7% senior debt cost + ~1% BPI equity margin (~8% total)
- **Every warehouse-funded loan generates positive equity returns**

This ensures:
1. SPV economics work from day one
2. Capital partners see assets that service debt
3. BPI's first-loss tranche earns ~1% positive margin

**Implementation:** See `lip/common/constants.py` (WAREHOUSE_ELIGIBILITY_FLOOR_BPS) and `is_spv_warehouse_eligible()` function for routing logic.

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

| Principal | Fee Rate | Fee Calculation | Total Fee | Funding Source |
|-----------|----------|----------------|-----------|----------------|
| $1,500,000 (minimum for Class A) | 400 bps | $1.5M × 0.04 × 3/365 | **$493.15** | Bank-funded |
| $2,000,000 | 300 bps | $2M × 0.03 × 3/365 | **$493.15** | Bank-funded |
| $5,000,000 | 300 bps | $5M × 0.03 × 3/365 | **$1,232.88** | Bank-funded |

### 4.2 Class B Loan (7-day maturity)

| Principal | Fee Rate | Fee Calculation | Total Fee | Funding Source |
|-----------|----------|----------------|-----------|----------------|
| $700,000 (minimum for Class B) | 400 bps | $700K × 0.04 × 7/365 | **$536.99** | Bank-funded (below warehouse floor) |
| $1,000,000 | 400 bps | $1M × 0.04 × 7/365 | **$767.12** | Bank-funded (below warehouse floor) |
| $1,000,000 | 800 bps (warehouse-eligible) | $1M × 0.08 × 7/365 | **$1,534.25** | SPV warehouse-funded |
| $2,000,000 | 800 bps (warehouse-eligible) | $2M × 0.08 × 7/365 | **$3,068.49** | SPV warehouse-funded |
| $2,890,000 | 706 bps (warehouse-eligible) | $2.89M × 0.0706 × 7/365 | **$3,911** | SPV warehouse-funded |

### 4.3 Class C Loan (21-day maturity)

| Principal | Fee Rate | Fee Calculation | Total Fee | Funding Source |
|-----------|----------|----------------|-----------|----------------|
| $500,000 (minimum for Class C) | 800 bps (warehouse-eligible) | $500K × 0.08 × 21/365 | **$2,301.37** | SPV warehouse-funded |
| $1,000,000 | 800 bps (warehouse-eligible) | $1M × 0.08 × 21/365 | **$4,602.74** | SPV warehouse-funded |
| $2,000,000 | 800 bps (warehouse-eligible) | $2M × 0.08 × 21/365 | **$9,205.48** | SPV warehouse-funded |

---

## 5. Deployment Phase Fee Splits

The total fee from Section 4 is split between BPI and bank according to the deployment phase:

### 5.1 Phase Split Table

| Phase | BPI Share | Bank Share | Bank Breakdown | Income Classification |
|-------|-----------|------------|----------------|----------------------|
| **Phase 1 (Licensor)** | 30% | 70% | 70% retained by bank (bank funds 100% of capital) | **IP Royalty** |
| **Phase 2 (Hybrid)** | 55% | 45% | 30% capital return + 15% distribution premium | **Lending Revenue** |
| **Phase 3 (Full MLO)** | 80% | 20% | 0% capital return + 20% distribution premium | **Lending Revenue** |

**Tax note:** Phase 1 income is classified as IP royalty (relevant for SR&ED, HST treatment). Phase 2 and Phase 3 income is lending revenue — different Canadian tax treatment applies.

### 5.2 Phase Split on a $1M / 7-day / 800 bps Loan (SPV-Funded, Warehouse-Eligible)

Total fee: $1,000,000 × 0.08 × 7/365 = **$1,534.25**

| Phase | BPI Earns | Bank Earns | BPI Revenue Classification |
|-------|-----------|------------|----------------------|
| Phase 2 | $843.84 | $690.41 | Lending Revenue (55% share) |
| Phase 3 | $1,227.40 | $306.85 | Lending Revenue (80% share) |

**At 800 bps warehouse floor:**
- Asset yield: 8% annualized ($80K/year per $1M)
- SPV capital cost: ~7% senior + ~1% BPI equity margin ≈ 8%
- **Every SPV-funded loan generates positive equity returns for BPI**

### 5.3 Phase Split on a $2.89M / 9-day / 706 bps Loan (Investor Briefing Example)

Total fee: **$5,033**

| Phase | BPI Earns | Bank Earns |
|-------|-----------|------------|
| Phase 2 | $2,768.15 | $2,264.85 |
| Phase 3 | $4,026.40 | $1,006.60 |

**Note:** 706 bps is the C2 model's risk-adjusted rate for this specific payment, NOT the 300 bps floor. Typical risk-adjusted rates range from 600–800+ bps depending on borrower characteristics.

---

## 6. Asset Yield vs. Debt Service — Honest Economics

### The Structural Reality

**At 300 bps platform minimum:**
- Asset yield: 4% annualized ($40K/year per $1M)
- Capital structure debt service: ~6.55% (senior ~7% + mezz ~12%)
- **Gap: -2.55% — assets don't service debt**

**At 800 bps warehouse minimum:**
- Asset yield: 8% annualized ($80K/year per $1M)
- Capital structure debt service: ~7% senior + ~1% BPI equity margin ≈ 8%
- **Gap: ~0% — assets service debt with margin**

### The Solution: Code-Enforced Two-Tier Pricing

The two-tier floor ensures that every SPV-funded loan generates sufficient yield to service the SPV capital structure:

```
Funding Logic:
├── Phase 1: Bank funds all loans → BPI earns 30% IP royalty
├── Phase 2/3: SPV funds loans
│   ├── If fee < 800 bps → Route to bank (BPI earns 30% IP royalty)
│   └── If fee ≥ 800 bps → SPV warehouse-funds (BPI earns 55% lending revenue)
```

**Economic impact:**
- Phase 1: No capital required; IP royalty income on all loans
- Phase 2: Low-fee loans generate royalty; high-fee (800+ bps) loans generate positive lending equity returns
- Phase 3: All loans SPV-funded at securitization pricing; strong equity returns

**This is not "capital-negative by design" — it's a code-enforced routing mechanism that optimizes portfolio composition automatically.** The C2 risk model naturally routes higher-risk borrowers (who pay higher fees) to SPV funding, while lower-risk borrowers remain bank-funded.

---

## 7. Platform Royalty Calculation

BPI earns a royalty on ALL loans it touches (regardless of funding source):

```
royalty = fee_amount × PLATFORM_ROYALTY_RATE (30%)
```

The 300 bps platform floor applies to all loans. The 800 bps warehouse floor
determines funding source (SPV vs. bank), not the royalty amount.

---

*All constants sourced from `lip/common/constants.py` (canonical, QUANT-controlled). Fee formula implemented in `lip/c2_pd_model/fee.py`. Phase splits implemented in `lip/common/deployment_phase.py`.*
