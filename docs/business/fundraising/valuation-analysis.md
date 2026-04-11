# Bridgepoint Intelligence Inc. — Pre-Seed Valuation Analysis

**Date:** March 2026
**Purpose:** Establish defensible valuation cap for Friends & Family SAFE round
**Recommended SAFE Cap:** $2,000,000 (pre-money)

---

## Executive Summary

This analysis applies five independent valuation methodologies to Bridgepoint Intelligence Inc. (BPI) at its current pre-incorporation, pre-revenue stage. All five methods converge on a range of $500K–$3.0M, with a central tendency of $1.5M–$2.5M.

The recommended Friends & Family SAFE valuation cap of **$2.0M pre-money** represents a **67% discount** to the planned $6.0M Pre-Seed valuation. This discount rewards F&F investors for bearing the earliest risk: pre-incorporation status, unresolved IP assignment questions, zero revenue, and sole-founder dependency.

---

## Method 1: Cost-to-Recreate

**Estimated Range: $900,000–$1,500,000**

This method establishes a **floor valuation** — the minimum cost a rational actor would incur to replicate BPI's current assets from scratch.

### Asset Inventory

| Asset | Replacement Cost | Basis |
|-------|-----------------|-------|
| ML inference engine (C2 model, BIC-pair detection, CVA, PD estimation) | $300K–$500K | 1 senior ML engineer × 12 months ($150K salary + 30% overhead) + compute |
| SWIFT integration layer (pacs.002/pacs.008 parsing, UETR tracking, rejection code taxonomy) | $150K–$250K | 1 payments domain engineer × 8 months |
| Infrastructure (7 Docker images, CI/CD, 1,476 tests) | $100K–$150K | 1 DevOps engineer × 6 months |
| Patent research & specification (15-patent portfolio strategy, claims drafted) | $100K–$200K | Patent attorney time + inventor time |
| Domain expertise & financial model suite (unit economics, revenue model, capital partner strategy) | $100K–$150K | 6 months fintech consulting equivalent |
| Academic paper & regulatory research | $50K–$100K | 3 months specialist research |
| **TOTAL** | **$800K–$1,350K** | |
| + 15% coordination overhead (solo founder did all integration) | $120K–$200K | Integration premium |
| **ADJUSTED TOTAL** | **$920K–$1,550K** | |

### Key Assumptions

- Salary rates based on Canadian Tier 1 city (Toronto/Vancouver) market rates for senior engineers
- 30% overhead includes benefits, tools, and compute
- Patent research valued at commercial rates ($400–$600/hr for patent counsel)
- Coordination overhead reflects the integration complexity of having one person maintain coherence across ML, payments, infrastructure, legal, and financial strategy

### Limitation

Cost-to-recreate establishes a **floor only**. It captures replacement cost but not strategic value, market opportunity, or optionality. A rational acquirer or investor would pay above replacement cost if the assembled assets unlock a market opportunity worth multiples of the build cost.

---

## Method 2: Berkus Method

**Estimated Range: $1,150,000–$1,350,000**

The Berkus Method assigns value (up to $500K each) across five risk dimensions for pre-revenue startups.

| Factor | Assessment | Value Assigned | Rationale |
|--------|-----------|---------------|-----------|
| **Sound Idea** | Strong | $350K–$400K | $31.7T cross-border payment market (FXC Intelligence 2024). 3–5% failure rate creates $960B–$1.6T disrupted volume. Bridging liquidity gap is a recognized pain point with no dominant automated solution. Deduction: regulatory complexity and bank sales cycle length. |
| **Working Prototype** | Strong | $350K–$400K | 1,476 passing tests. 7 Docker images. Full ML inference pipeline (45ms p50 latency). End-to-end loan decision demonstrated on real SWIFT rejection data. CI green. Deduction: never processed a real payment; no production environment. |
| **Quality of Team** | Moderate | $100K–$150K | Solo founder with deep domain knowledge spanning ML, payments, patent strategy, and financial modeling. "Ford model" — AI-augmented development demonstrated by scope of output. Deduction: single point of failure; no co-founder; no advisory board yet. |
| **Strategic Relationships** | Limited | $100K–$150K | RBC employment provides payments domain insight but founder must resign before engaging. No signed LOI or pilot agreement. Deduction: no formal bank relationships yet; RBC approach requires post-resignation strategy. |
| **Product Rollout / Sales** | Limited | $100K–$150K | Clear go-to-market strategy (RBCx → Transaction Banking → broader Tier 1). Detailed playbook. Deduction: zero revenue, no signed customers, no pipeline beyond strategy documents. |
| **TOTAL** | | **$1,000K–$1,250K** | |
| + 15% premium for patent strategy (15-patent portfolio with $18B–$35B projected value) | | $150K–$188K | |
| **ADJUSTED TOTAL** | | **$1,150K–$1,438K** | |

### Limitation

The Berkus Method caps at $2.5M by design and is calibrated for US angel investing. Canadian pre-seed valuations may differ. The method also struggles to capture the optionality value of a patent portfolio covering a $31.7T market.

---

## Method 3: Risk-Adjusted Discounted Cash Flow

**Estimated Range: $500,000–$2,000,000**

### Assumptions

| Parameter | Conservative | Base | Source |
|-----------|-------------|------|--------|
| Year 3 BPI Revenue | $3.0M | $11.5M | Revenue-Projection-Model.md: 1 Tier 1 bank, Phase 1 |
| Revenue Multiple | 5× | 8× | Comparable fintech SaaS/lending platforms |
| Year 3 Enterprise Value | $15.0M | $92.0M | Revenue × Multiple |
| Probability of Reaching Year 3 Revenue | 15% | 20% | Pre-revenue, pre-incorporation, solo founder |
| Discount Rate | 65% p.a. | 50% p.a. | Early-stage venture (50–75% typical range) |
| Time to Valuation Event | 3 years | 3 years | Per financial model timeline |

### Calculation

**Conservative Case:**

$$PV = \frac{\$15.0M \times 15\%}{(1 + 0.65)^3} = \frac{\$2.25M}{4.49} = \$501K$$

**Base Case:**

$$PV = \frac{\$92.0M \times 20\%}{(1 + 0.50)^3} = \frac{\$18.4M}{3.375} = \$5,452K$$

**Blended (weighted 70/30 conservative/base):**

$$Blended = (0.70 \times \$501K) + (0.30 \times \$5,452K) = \$351K + \$1,636K = \$1,987K$$

**Risk-Adjusted Range: $500K–$2,000K** (conservative-to-blended)

### Key Risk Adjustments

- **15–20% probability** reflects: pre-revenue, pre-incorporation, solo founder, unresolved IP assignment, no bank relationships signed
- **65% discount rate** (conservative) reflects extreme early-stage risk; 50% (base) is already aggressive for pre-revenue
- Year 3 revenue of $3.0M (conservative) assumes only 1 Tier 1 bank at Phase 1 (15% fee share = $3.0M annual BPI revenue per Revenue-Projection-Model.md)

### Limitation

DCF at pre-revenue stage is highly sensitive to probability and discount rate assumptions. A 5% swing in probability or 10% swing in discount rate moves the output by 30–50%. This method is directional, not precise.

---

## Method 4: Comparable Transactions

**Estimated Range: $1,500,000–$3,000,000**

### Comparable Set

| Company / Transaction | Stage | Valuation | Key Similarities | Key Differences |
|----------------------|-------|-----------|-----------------|-----------------|
| Canadian fintech pre-seed (median, 2024–2025) | Pre-seed, pre-revenue | $2.0M–$4.0M | Canadian jurisdiction; fintech | Most have co-founders; some have revenue |
| AI/ML infrastructure startups (pre-seed, 2024–2025) | Pre-seed, working prototype | $3.0M–$6.0M | Working ML prototype; technical depth | US-based; larger founding teams |
| Solo-founder SaaS (Canadian, pre-seed) | Pre-seed, MVP | $1.0M–$2.5M | Solo founder; Canadian | Simpler tech stack; smaller TAM |
| Payment infrastructure (pre-seed, 2024) | Pre-seed, partnerships | $3.0M–$5.0M | Payments domain; B2B | Usually have LOIs or early customers |

### Adjustment Factors

| Factor | Adjustment | Rationale |
|--------|-----------|-----------|
| Working prototype (1,476 tests, CI green) | +20% | Above-average technical maturity for pre-seed |
| Solo founder | -25% | Key-person risk; most comparables have 2–3 founders |
| Pre-incorporation | -15% | No legal entity; unusual at fundraising stage |
| Unresolved IP assignment | -20% | Material legal risk unique to BPI's situation |
| Patent strategy (15-patent portfolio) | +15% | Unusual IP depth for pre-seed; $31.7T market coverage |
| No revenue or customers | -10% | Standard pre-seed discount |

**Adjusted comparable range:** $2.5M median × (1.20 × 0.75 × 0.85 × 0.80 × 1.15 × 0.90) = $2.5M × 0.63 = **$1,575K**

**Range: $1,500K–$3,000K** (reflecting spread across comparable set after adjustments)

### Limitation

Canadian pre-seed fintech data is sparse. Most published valuations are US-centric. The adjustment factors are subjective. The unresolved IP assignment risk is unusual and may not be well-captured by standard adjustments.

---

## Method 5: Scorecard Method

**Estimated Range: $2,200,000–$2,800,000**

### Regional Median

**Baseline:** $2,500,000 (Canadian tech pre-seed median, 2024–2025, per CVCA and angel network data)

### Scorecard Weights

| Factor | Weight | Rating | Weighted Factor |
|--------|--------|--------|----------------|
| **Strength of Entrepreneur / Team** | 30% | 0.70× | 0.210 |
| Solo founder. Deep domain expertise across ML, payments, IP, and financial strategy. "Ford model" (AI-augmented) is proven by output scope. Heavy discount for key-person risk and no co-founder. | | | |
| **Size of Opportunity** | 25% | 1.30× | 0.325 |
| $31.7T cross-border B2B market. 3–5% failure rate. Clear path from $3M (Year 3, 1 bank) to $226M (Year 10, 15 banks). Market growing at 7% CAGR. | | | |
| **Product / Technology** | 15% | 1.40× | 0.210 |
| 1,476 passing tests. 7 Docker images. 45ms p50 inference. Full ML pipeline. Patent portfolio strategy covering 15 patents. Above-average for pre-seed. | | | |
| **Competitive Environment** | 10% | 1.10× | 0.110 |
| No dominant automated solution for cross-border payment failure bridging. Banks use manual processes. Patent-first strategy creates defensibility. Partial discount: large incumbents could build. | | | |
| **Marketing / Sales / Partnerships** | 10% | 0.60× | 0.060 |
| Zero customers. Zero revenue. No LOIs. Strategy documented but unexecuted. Must resign from RBC before approaching any bank. | | | |
| **Need for Additional Investment** | 5% | 1.00× | 0.050 |
| Clear capital efficiency: $75K–$150K F&F → legal/patent foundation → $1.5M Pre-Seed → pilot. Not capital-intensive until Phase 2 warehouse. | | | |
| **Other (IP/Legal Risk)** | 5% | 0.50× | 0.025 |
| Unresolved RBC IP assignment clause. Git history begins during employment period. Material risk requiring legal resolution as first use of proceeds. | | | |
| **TOTAL** | **100%** | | **0.990** |

### Calculation

$$Valuation = \$2,500,000 \times 0.990 = \$2,475,000$$

**Range: $2,200K–$2,800K** (reflecting uncertainty in weight assignments)

### Limitation

Scorecard method is anchored to the regional median, which may not reflect BPI's unique risk profile (IP assignment risk, solo founder, pre-incorporation). The method's strength is in relative comparison; its weakness is that outlier characteristics are compressed toward the median.

---

## Convergence Analysis

| Method | Low | Mid | High |
|--------|-----|-----|------|
| 1. Cost-to-Recreate | $920K | $1,235K | $1,550K |
| 2. Berkus Method | $1,150K | $1,294K | $1,438K |
| 3. Risk-Adjusted DCF | $501K | $1,250K | $1,987K |
| 4. Comparable Transactions | $1,500K | $2,250K | $3,000K |
| 5. Scorecard Method | $2,200K | $2,500K | $2,800K |
| **Simple Average** | **$1,254K** | **$1,706K** | **$2,155K** |
| **Median** | **$1,150K** | **$1,294K** | **$1,987K** |

### Observations

1. **Floor established at ~$900K** by cost-to-recreate. No rational valuation should fall below this.
2. **Ceiling at ~$3.0M** set by comparable transactions, reflecting the most optimistic reading of market comparables.
3. **Central tendency of $1.5M–$2.0M** across all five methods.
4. Methods 1–3 (asset-based and fundamental) cluster at $900K–$2.0M. Methods 4–5 (market-based) cluster at $1.5M–$3.0M. The divergence reflects the gap between "what exists today" and "what the market would pay for optionality."

---

## Recommended F&F SAFE Valuation Cap: $2,000,000

### Rationale

| Factor | Detail |
|--------|--------|
| **Convergence point** | $2.0M sits at the upper end of fundamental methods and lower end of market methods — defensible from both directions |
| **Discount to Pre-Seed** | 67% discount to planned $6.0M Pre-Seed valuation. Rewards F&F for earliest risk |
| **F&F risk premium** | F&F investors bear: pre-incorporation risk, unresolved IP assignment, zero revenue, sole-founder dependency, no institutional lead |
| **Cap table hygiene** | At $75K–$150K raise and $2.0M cap, F&F investors collectively own 3.6%–7.0% on conversion — manageable dilution |
| **Upside for F&F** | Clear path to 3× return at Pre-Seed conversion (see worked example below) |

### Worked Example: F&F Investor Return at Pre-Seed Conversion

**Assumptions:**
- F&F investor invests $25,000 via SAFE with $2.0M cap and 20% discount
- Pre-Seed round closes at $6.0M pre-money valuation, raising $1.5M

**Conversion — Better of Cap or Discount:**
- Cap price: $2.0M ÷ (shares outstanding at Pre-Seed) → effective price per share
- Discount price: Pre-Seed price × (1 - 20%) = Pre-Seed price × 0.80
- At $6.0M Pre-Seed, the $2.0M cap gives a **3.0× effective discount** (the cap is binding, not the 20% discount)

**Result:**
- $25,000 invested at $2.0M effective valuation
- Pre-Seed values company at $6.0M
- F&F investor's $25,000 converts to shares worth **$75,000 at Pre-Seed price** (3.0× paper return)
- This is a **paper return only** — actual liquidity requires a future exit event

**At Series A ($50M–$60M pre-money):**
- Same $25,000 investment is now worth **$625K–$750K** (25×–30× paper return)
- Subject to dilution from subsequent rounds

### Why Not Lower? Why Not Higher?

| Alternative Cap | Problem |
|----------------|---------|
| $1.0M–$1.5M | Below cost-to-recreate floor. Signals founder undervalues own work. May create adverse selection (only investors who don't understand the tech would accept). |
| $2.5M–$3.0M | Reduces F&F discount to Pre-Seed to only 50–58%. Insufficient reward for pre-incorporation, pre-IP-resolution risk. May make Pre-Seed harder to price. |
| $3.0M+ | Approaches Pre-Seed range. Eliminates F&F risk premium entirely. Not appropriate for current stage. |

---

## Source Documents

This analysis draws on the following BPI internal documents for consistency:

1. **Founder-Financial-Model.md** — $6M Pre-Seed valuation, equity journey table, phase transition multipliers
2. **Revenue-Projection-Model.md** — $3.0M conservative Year 3 revenue (1 bank, Phase 1), $31.7T TAM
3. **Capital-Partner-Strategy.md** — SPV structure, warehouse economics, Phase 2/3 capital requirements
4. **Unit-Economics-Exhibit.md** — 300 bps canonical fee floor, tiered floors (500/400/300 bps), $150 minimum cash fee
5. **Operational-Playbook-v2.1.md** — Phase 0 costs ($5K–$9K), Phase 1 IP costs ($100K–$155K incl. PCT)
6. **Investor-Briefing-v2.1.md** — $31.7T market size, 45ms p50 latency, live system output demonstration
7. **lip/common/constants.py** — All QUANT-controlled fee constants, latency targets, phase fee shares

---

## Disclaimer

This valuation analysis is for internal planning purposes only. It does not constitute a formal business valuation, fairness opinion, or investment recommendation. Investors should conduct their own due diligence and consult independent legal and financial advisors. All projections are forward-looking estimates based on internal models and assumptions that may not materialize.
