# CAPITAL PARTNER STRATEGY
## Warehouse Facility, SPV Architecture, and the Path to Securitization
### VERSION 1.0 | Bridgepoint Intelligence Inc. | 2026-03-20

---

> **PURPOSE:** This document lays out BPI's strategy for securing a capital partner to fund Phase 2 (Hybrid) and Phase 3 (Full MLO) bridge lending operations. It is written for internal planning and for sharing with prospective capital partners. Every number is derived from the validated models in [Revenue-Projection-Model.md](Revenue-Projection-Model.md) and [Unit-Economics-Exhibit.md](Unit-Economics-Exhibit.md). Where the numbers are unflattering, they are presented anyway. Sophisticated capital partners can smell a deck that hides the hard math — BPI does not hide it.

> **Income Classification Note:** Phase 1 revenue is IP royalty income (BPI licenses its platform; the bank funds and originates all loans). Phase 2 and Phase 3 revenue is lending revenue (BPI deploys capital and earns a share of loan fees). These carry materially different tax and regulatory treatment. This distinction is maintained throughout this document. *(See: feedback_income_classification.md)*

---

## 1. Why BPI Needs a Capital Partner (and When)

### Phase 1 Requires Zero BPI Capital

In Phase 1 (Licensor), BPI licenses the C1–C8 platform to a bank. The bank funds 100% of every bridge loan. BPI earns 30% of total fee revenue as an IP royalty. BPI's capital requirement: **$0**.

This is the proof period. Phase 1 exists to:
- Demonstrate that the platform works in production (real SWIFT traffic, real UETR settlement)
- Build 12–18 months of auditable loan performance data
- Generate $3.0M+/year revenue from a single conservative Tier 1 bank *(Revenue-Projection-Model.md §2.2)*
- Prove to capital partners that bridge loans self-liquidate as designed

### Phase 2 Changes Everything

In Phase 2 (Hybrid), BPI co-funds 70% of each bridge loan alongside the bank's 30%. BPI's fee share jumps from 30% to 55%. Per bank, revenue multiplies **1.8×** compared to Phase 1. *(Revenue-Projection-Model.md §2.2–2.3)*

But BPI now needs capital to deploy. The transition from Phase 1 to Phase 2 is the critical inflection point: BPI must secure a capital facility before it can capture the revenue uplift.

### Timing

Phase 2 begins Year 3–4, after the Phase 1 pilot proves the model. The capital partner conversation starts in Year 2 — warm introductions, performance data sharing, preliminary term negotiation — so that the facility is committed before BPI is ready to flip the switch.

---

## 2. The Warehouse Facility — What It Is

A warehouse facility is a revolving credit line secured by the loans BPI originates. It is the standard funding mechanism for specialty lenders, mortgage originators, and fintech platforms. Here is how it works for BPI:

### Step 1: Create a Subsidiary SPV

**BPI Capital I Ltd** — a legally separate special purpose vehicle, 100% owned by BPI Inc. (the parent). The parent holds the IP, patents, and platform. The SPV holds the loan book. This separation is non-negotiable.

### Step 2: Capital Partner Commits a Facility Limit

The capital partner commits a facility size (e.g., $10M to start). This is a **commitment**, not deployed cash. BPI pays 25–50 bps/year as a commitment fee on the undrawn balance. The capital partner earns the commitment fee for making the capacity available, regardless of utilization.

### Step 3: Define the Credit Box

The credit box defines which loans are eligible for warehouse funding. BPI's credit box maps directly to the platform's own risk controls:

| Eligibility Criterion | Source | Rationale |
|----------------------|--------|-----------|
| Class A, B, or C only | Rejection taxonomy (C1) | BLOCK class is never bridged — EPG-19 *(Unit-Economics-Exhibit.md §3)* |
| τ* ≤ 15.2% threshold enforced | C2 PD model | High-risk loans blocked before origination |
| Fee rate ≥ 300 bps annualized | QUANT-controlled floor *(Unit-Economics-Exhibit.md §2)* | Ensures minimum economics per loan |
| UETR binding required | C3 settlement layer | Self-liquidation mechanism must be in place |
| Minimum principal per tier | Unit-Economics-Exhibit.md §4 | Sub-minimum loans uneconomic |
| `hold_bridgeable = true` certification | EPG-04/05 bank warranty | Compliance hold protection |

The credit box is not a negotiation — it is the system's own operating envelope. This makes diligence straightforward: the capital partner is not underwriting BPI's judgment, they are underwriting the algorithm's constraints.

### Step 4: Draw Against the Borrowing Base

When BPI originates an eligible loan, it draws against the facility. The advance rate is typically 80–90% of eligible loan face value. BPI's equity contribution (10–20%) is the first-loss tranche — BPI takes the first dollar of loss on every loan.

### Step 5: Automatic Repayment via SWIFT UETR Settlement

When the underlying cross-border payment settles (confirmed by SWIFT UETR), the bridge loan self-liquidates. The capital partner's principal plus interest returns automatically. No human collection. No dunning. No workout desk. Average cycle time: ~7 days. *(Unit-Economics-Exhibit.md §3: Class B average maturity = 7 days)*

---

## 3. SPV Architecture

```
BPI Inc. (Parent — holds IP, patents, platform, all licensing agreements)
    │
    ├── Platform License → Banks (C1–C8 system, Phase 1 royalty income)
    │
    └── 100% equity owner of:
            │
        BPI Capital I Ltd (SPV — warehouse vehicle)
            │
            ├── Senior Lender (Credit Fund / Bank Co-Investor)
            │     └── 85–90% of facility, SOFR + spread, first out in waterfall
            │
            ├── Mezzanine (Family Office)
            │     └── 5–10% of facility, higher spread, second out
            │
            └── BPI First-Loss Equity Tranche
                  └── 5–15% of facility, last out — eats first losses,
                        earns highest residual return
```

### What This Structure Achieves

**1. Protects BPI's crown jewels.** The IP portfolio, patents, platform code, and bank licensing agreements sit in the parent entity. If the SPV's loan book suffers unexpected losses, the parent is structurally remote. A capital partner's claim stops at the SPV boundary. BPI's IP is never collateral for lending operations.

**2. Creates a tiered capital structure with aligned incentives.**

| Tranche | % of Facility | Target Return | Priority |
|---------|--------------|---------------|----------|
| Senior | 85–90% | SOFR + 200–350 bps (6–8% all-in) | First out |
| Mezzanine | 5–10% | 10–14% | Second out |
| BPI Equity | 5–15% | 30%+ residual (variable) | Last out |

BPI's first-loss position is the key: it means BPI's incentives are perfectly aligned with the capital partner's. BPI loses money before anyone else does. This is the single most important structural feature for a capital partner evaluating a new originator.

**3. Gives BPI operational control.** BPI retains full origination authority within the agreed credit box. The capital partner does not approve individual loans — the credit box and the algorithm do. This is critical for maintaining the platform's sub-second decision speed.

**4. Enables future securitization.** After 12–18 months of clean SPV performance data, BPI can refinance the warehouse into a rated securitization, dropping cost of capital from ~12% to ~5–6%. The warehouse is a bridge to permanent capital — not the end state. *(See Section 9.)*

---

## 4. Capital Efficiency — The Working Capital Revelation (And Its Limits)

This is where most fintech pitch decks lie by omission. BPI will not.

### The Good News: Capital Turns Fast

Because bridge loans self-liquidate in ~7 days average, capital turns approximately **52 times per year** (365 ÷ 7). BPI does not need the full annual origination volume deployed simultaneously — only the amount active at any given moment.

Concurrent capital deployed = annual volume × (average maturity ÷ 365)

### The Hard Truth: Phase 2 Unit Economics at Scale

Let us calculate honestly, using the validated numbers from Revenue-Projection-Model.md.

#### Scenario A: Mid-Tier Bank (First Phase 2 Candidate?)

| Parameter | Value | Source |
|-----------|-------|--------|
| Annual cross-border volume | $100B–$200B | Mid-tier bank range |
| Failure rate × eligible % | 3.5% × 40% = 1.4% | Conservative assumptions |
| Annual bridge volume | $100B × 1.4% = **$1.4B** | |
| Number of loans | $1.4B ÷ $800K avg = **1,750/year** | |
| Concurrent capital deployed | $1.4B × (7/365) = **$26.8M** | |
| BPI's 70% share | **$18.8M** | Phase 2 co-funding ratio |
| Total fee revenue | 1,750 × $383.56 = **$671K** | Fee per loan from Revenue-Projection-Model.md §2.2 |
| BPI's 40% share | **$268K** | Phase 2 fee split |
| Capital partner cost at 12% preferred | $18.8M × 12% = **$2.26M** | Blended warehouse cost |

**Result: BPI earns $268K against $2.26M in capital costs. This is deeply underwater.** A mid-tier bank does not generate enough fee volume to justify the capital deployment. This is why Phase 2 does not start with mid-tier banks.

#### Scenario B: Conservative Tier 1 Bank — Full Book

| Parameter | Value | Source |
|-----------|-------|--------|
| Annual eligible bridge volume | **$42B** | Revenue-Projection-Model.md §2.2: $3T × 3.5% × 40% |
| Concurrent capital deployed | $42B × (7/365) = **$806M** | |
| BPI's 70% share | **$564M** | |

$564M concurrent deployment for a startup. This is obviously impossible. BPI does not launch Phase 2 on the entire book at once.

#### Scenario C: Tier 1, Single High-Value Corridor (Realistic Phase 2 Entry)

Phase 2 starts with 1–2 corridors, not the full book. Assume 2% of eligible volume (one high-value corridor):

| Parameter | Value |
|-----------|-------|
| Corridor volume | $42B × 2% = **$840M/year** |
| Concurrent capital | $840M × (7/365) = **$16.1M** |
| BPI's 70% share | **$11.3M** |
| Loans in corridor | $840M ÷ $800K = **1,050/year** |
| Total fee | 1,050 × $383.56 = **$403K** |
| BPI's 40% | **$161K** |
| Capital cost (12% on $11.3M) | **$1.36M** |

**Result: Still underwater. BPI earns $161K against $1.36M capital cost.**

### The Breakeven Math — Why Phase 2 Economics Are Structurally Challenging

Let us trace the math to its root.

On a single $1M bridge loan, funded 70% by BPI ($700K deployed), at 400 bps annualized over 7 days:

| Item | Calculation | Result |
|------|-------------|--------|
| Total fee | $1M × (400/10,000) × (7/365) | $767.12 |
| BPI's 40% share | $767.12 × 0.40 | $306.85 |
| Annualized per $700K deployed | $306.85 × 52 turns | $15,956/year |
| Effective yield on BPI capital | $15,956 ÷ $700,000 | **2.28%** |
| Capital cost (blended warehouse) | | **~12%** |
| **Gap** | | **-9.72%** |

BPI's fee income on deployed capital yields 2.28% annually. The warehouse costs 12%. The gap is approximately 9.7 percentage points. To close this gap through fee rates alone, BPI would need average rates of ~2,100 bps — seven times the floor. That is not realistic.

### So Why Does Phase 2 Exist?

Phase 2 is a **strategic investment**, not a standalone profit center. Its value lies in three things:

1. **Revenue multiplier.** BPI's total revenue per bank jumps 2.7× even though capital returns are negative on a spread basis. The absolute dollars ($8.05M vs $3.0M conservative) fund operations, hiring, and platform expansion.

2. **Performance data for securitization.** The 12–18 months of Phase 2 warehouse data is the raw material for a rated securitization (Section 9). Clean data → rated deal → cost of capital drops from 12% to 5–6% → Phase 3 becomes highly profitable.

3. **Phase 3 unlock.** Phase 3 (75% fee share, 100% BPI-funded) only works with cheaper capital. The warehouse-to-securitization path is the only realistic route to that cheaper capital. Phase 2 is the toll road.

**The capital partner's returns are not dependent on BPI equity economics.** The capital partner earns their preferred rate (SOFR + spread, ~6–8% senior, ~10–14% mezz) on deployed capital, secured by self-liquidating loans with BPI first-loss equity beneath them. Their return profile is attractive independent of BPI's blended economics. The capital partner is lending against a pool of short-duration, self-liquidating, algorithmically underwritten assets — not buying BPI equity.

### SPV Leverage and BPI's True Equity at Risk

BPI does not fund the full 70% from its own balance sheet. The SPV has a tiered capital structure (Section 3): the senior lender provides 85% of the SPV's capital at ~7%, and BPI contributes only the **15% first-loss equity tranche**. On a $15M facility, BPI's equity at risk is ~$2.25M, not $15M.

This leverage amplifies both returns and losses on BPI's equity. For detailed breakeven analysis at various fee rates, see [Revenue-Projection-Model.md §8.4–8.6](Revenue-Projection-Model.md). Key finding: at the 300–400 bps fee floor, Phase 2 is capital-negative even with leverage. At the C2 model's typical risk-adjusted rates (600–800+ bps), Phase 3 with securitized capital (5% senior cost) reaches breakeven at ~560 bps average and becomes profitable above that.

---

## 5. Three Deal Terms You Must Never Give Away

### 1. Cross-Default Trigger

**What they will ask for:** Full cross-default — any default by BPI or any affiliate on any obligation triggers acceleration of the warehouse facility.

**What BPI must negotiate:** Selective cross-default limited to:
- Fraud, misrepresentation, or criminal conduct by BPI
- Insolvency or bankruptcy filing by BPI parent
- Material breach of the warehouse agreement itself

All other covenant violations get a **30-day cure period minimum**. A technical covenant breach (e.g., momentary concentration limit exceedance during corridor expansion) must not give the capital partner the right to accelerate the entire facility.

### 2. SPV Equity Pledge

**What they will ask for:** Pledge of BPI parent equity or IP as additional collateral.

**What BPI must accept:** Pledge of SPV equity only. The capital partner gets a lien on BPI's ownership interest in BPI Capital I Ltd. If BPI defaults, the capital partner can seize the SPV and its loan book.

**What BPI must never accept:** Any lien, pledge, or security interest in:
- BPI's patent portfolio
- The platform IP or source code
- BPI parent equity
- Bank licensing agreements

The patent portfolio is BPI's existential asset. It must never be pledged to a warehouse lender. If BPI's lending book goes to zero, the IP remains intact and BPI can rebuild from Phase 1. If the IP is pledged and seized, BPI is dead.

### 3. Repurchase Triggers

**What they will ask for:** Broad repurchase obligations — BPI must buy back any loan that defaults, breaches representations, or fails to settle within the maturity window.

**What BPI must negotiate:**
- Repurchase limited to **fraud or misrepresentation** by BPI in originating the loan
- Maturity extension (not repurchase) for loans that settle late but within UETR TTL (45-day buffer per canonical constants)
- UETR settlement is the natural repayment mechanism — the loan is designed to self-liquidate. Repurchase should be the exception (originator misconduct), not the rule (settlement timing variance)

---

## 6. Performance Covenants

### Default Rate Covenant

The τ* = 15.2% threshold is the first line of defense — it blocks high-risk loans before origination at the platform level. The covenant should reference the system's own risk threshold: loans that clear τ* and still default represent tail risk, not underwriting failure.

Negotiate the default rate covenant at a level that reflects the system's expected performance plus a reasonable buffer. If Phase 1 data shows a 0.5% annualized default rate, propose a covenant at 2.0% — four times observed performance.

### Concentration Limits

| Period | Maximum Single-Bank Concentration | Rationale |
|--------|----------------------------------|-----------|
| Month 0–12 | 100% (single bank allowed) | Phase 2 starts with one bank; forcing diversification before it exists is meaningless |
| Month 12–18 | 60% | Second bank onboarded; step-down begins |
| Month 24–30 | 40% | Third bank; approaching diversified book |

Negotiate the Year 1 single-bank allowance upfront. Capital partners will push for 50% concentration limits from day one — this is structurally impossible for a startup scaling one bank at a time. The step-down schedule shows a credible path to diversification without constraining early operations.

### Leverage for Refinancing

Clean covenant performance in Year 1 is the ammunition for Year 2 refinancing conversations. Every month of zero defaults, on-time UETR settlement, and within-covenant performance is a data point that reduces BPI's cost of capital at renewal.

---

## 7. The Sequencing Chess Game

Four moves, in order:

### Move 1: Close Architecture Gaps

Ensure the C1–C8 pipeline is production-ready and all architecture sign-off items are resolved. Per the BPI Architecture Sign-Off Record, the core pipeline (1,410+ tests passing) is implemented. Remaining items are contractual (MRFA B2B clause, EPG-04/05 bank warranty language) — these are legal work, not engineering work.

**Status: Substantially complete. Remaining gaps are legal/contractual, not technical.**

### Move 2: Warm Introductions to Capital Partners

Target list (Canadian market, BPI's home jurisdiction):

| Type | Examples | Rationale |
|------|----------|-----------|
| BDC / Government-backed | BDC Capital | Mandate to support Canadian fintech; patient capital |
| Private debt funds | Fiera Private Debt, RP Investment Advisors | Specialty lending appetite; structured credit expertise |
| Family offices | Toronto-based family offices with fintech or payments thesis | Flexible on structure; can move faster than institutional funds |
| Credit funds | Canadian and US credit opportunity funds | Higher return targets align with mezz tranche |

Start conversations 12+ months before capital is needed. Share Phase 1 performance data quarterly. Build the relationship before the ask.

### Move 3: Anchor Investor Mechanism

Ask the first capital partner for **$5M as an anchor commitment**. Structure the facility with capacity for a co-investor (second $5M tranche). The anchor gets:
- First look at deal flow and performance data
- Slightly better economics (lower spread or commitment fee) in exchange for anchoring
- Pro-rata rights on facility expansion

The anchor commitment de-risks the co-investor conversation: "We have $5M committed from [credible name], looking for $5M co-invest."

### Move 4: Conditional LOI Exchange

This is the critical choreography:

1. Capital partner commitment is **conditional on** BPI having a signed bank LOI (proving there are loans to fund)
2. Bank LOI is **conditional on** BPI having committed capital (proving BPI can co-fund Phase 2)
3. Both close simultaneously — neither party takes unconditional risk

This is standard in specialty lending. The capital partner's counsel and the bank's counsel are accustomed to conditional closings. BPI's job is to get both parties to the table at the same time, not to close either one first.

---

## 8. The Psychology of Pre-Committed Capital

### Version A: BPI Without Capital (Evaluation Mode)

> "We have a patent-protected platform for bridge lending on failed cross-border payments. We'd like to discuss a Phase 2 deployment where your bank co-funds bridge loans alongside us."

The bank hears: startup, unproven, needs capital, will they even be around next year? The bank enters **evaluation mode** — months of diligence, committee reviews, pilot scope negotiations, legal back-and-forth.

### Version B: BPI With Committed Capital (Infrastructure Mode)

> "We have a patent-protected platform already processing [X] bridge loans per month in Phase 1. We have a $10M warehouse facility committed by [credible capital partner name]. We're ready to deploy Phase 2 on [specific corridor] with 70/30 co-funding. Here is 12 months of performance data."

The bank hears: capitalized infrastructure, proven performance, ready to deploy. The bank shifts from evaluation mode to **FOMO mode** — how fast can we get live? What corridors are available? Are our competitors already talking to BPI?

The difference is not the platform. The difference is not the patent. The difference is that pre-committed capital transforms BPI from a vendor to be evaluated into infrastructure to be accessed.

**This is why the capital partner conversation must start before the Phase 2 bank conversation.** Even if the capital partner's commitment is conditional on the bank LOI (Move 4 above), the *existence* of a capital partner in the conversation changes the bank's psychological frame from day one.

---

## 9. The Securitization Path

### The Warehouse Is a Bridge, Not the Destination

After 12–18 months of clean SPV performance data, BPI can refinance the warehouse facility into a rated securitization:

| Parameter | Warehouse (Year 1–2) | Securitization (Year 3+) |
|-----------|----------------------|--------------------------|
| Cost of capital (senior) | SOFR + 200–350 bps (~6–8%) | SOFR + 50–150 bps (~5–6%) |
| Blended cost | ~12% | ~5–6% |
| Facility size | $5–20M | $50–200M+ |
| Investor base | 1–3 private lenders | Rated note buyers (insurance, pensions, asset managers) |
| Ongoing relationship | Bilateral, relationship-dependent | Market access, repeatable |

### What Changes at Securitization

Recall the Phase 2 unit economics gap from Section 4: BPI's effective yield on deployed capital is ~2.28%, against a ~12% warehouse cost. At securitization pricing (~5–6% blended):

| Item | Warehouse | Securitization |
|------|-----------|----------------|
| BPI effective yield | 2.28% | 2.28% |
| Cost of capital | ~12% | ~5–6% |
| Net spread | **-9.7%** | **-3.3% to -3.7%** |

The gap narrows but does not close for Phase 2 alone. **Phase 3 is the real margin event**: at 75% fee share, BPI's effective yield on deployed capital approximately doubles (from 2.28% to ~4.28%), and at securitization cost of capital, the spread approaches breakeven or turns positive — especially on higher-fee corridors where the C2 model prices well above the 300 bps floor.

### The Capital Partner's Exit

The warehouse-to-securitization transition is also the capital partner's natural exit:
- Their warehouse facility is "taken out" by the securitization proceeds
- They earn their preferred rate for 12–18 months with minimal duration risk (7-day average loan life)
- They can reinvest in a new BPI Capital II vehicle or exit cleanly
- Clean exit mechanics make the initial warehouse commitment more attractive

### What BPI Needs for Securitization

1. **12–18 months of auditable loan-level performance data** — default rates, recovery rates, settlement timing, loss severity
2. **Rating agency engagement** — Moody's, DBRS, or Kroll for Canadian-issued paper
3. **Servicing track record** — proof that BPI can manage collections (which, given UETR auto-settlement, is mostly proof that the technology works)
4. **Legal opinion on true sale** — loans transferred from BPI to SPV are a "true sale" for bankruptcy remoteness

---

## 10. Capital Partner Pitch — The Five Numbers

When BPI sits across the table from a capital partner, five numbers tell the story:

### 1. $31.7 Trillion

Annual cross-border payment volume (FXC Intelligence, 2024). This is the ocean BPI operates in. *(Revenue-Projection-Model.md §1.1)*

### 2. 7 Days

Average bridge loan duration. Self-liquidating against SWIFT UETR settlement confirmation. The capital partner's money comes back in a week — not a month, not a quarter, not a year. 52 capital turns per year. *(Unit-Economics-Exhibit.md §3)*

### 3. 300 Basis Points

Hardcoded fee floor, enforced at the code level by the QUANT-controlled pricing engine. Not a guideline, not a suggestion — a `min()` function in production code that cannot be overridden without a code change, a test suite update, and QUANT sign-off. Tiered floors go higher for smaller principals (400–500 bps). *(Unit-Economics-Exhibit.md §2)*

### 4. $3M+

BPI's annual revenue from the first Phase 1 pilot (conservative, single Tier 1 bank). Proven before BPI asks for capital. The capital partner is not funding a hypothesis — they are scaling a proven revenue stream. *(Revenue-Projection-Model.md §2.2)*

### 5. 12–18 Months

Time from warehouse close to securitization-ready. Clean performance data enables a rated deal, cost of capital collapses from ~12% to ~5–6%, and the capital partner gets a clean exit. This is the timeline for the capital partner's deployment — not a 5-year lockup, not a venture-style 10-year fund. Short-duration capital for short-duration assets.

---

## Appendix: Income Classification Summary

| Phase | Income Type | Tax Treatment | Capital Required |
|-------|-----------|---------------|------------------|
| Phase 1 (Licensor) | **IP royalty** | Royalty income; eligible for IP box / patent box regimes where applicable | $0 — bank funds 100% |
| Phase 2 (Hybrid) | **Lending revenue** | Interest/fee income from lending operations; different withholding, deductibility, and regulatory treatment | 70% of each loan via warehouse facility |
| Phase 3 (Full MLO) | **Lending revenue** | Same as Phase 2 but at scale | 100% of each loan via securitization vehicle |

This distinction has material consequences for corporate structure, tax planning, transfer pricing between BPI parent and SPV, and regulatory licensing requirements. Legal and tax counsel must be engaged before Phase 2 launch.

---

*Cross-references: [Revenue-Projection-Model.md](Revenue-Projection-Model.md) | [Unit-Economics-Exhibit.md](Unit-Economics-Exhibit.md)*

*This document contains forward-looking estimates based on internal models. All projections are subject to market conditions, regulatory approvals, and successful Phase 1 pilot performance.*
