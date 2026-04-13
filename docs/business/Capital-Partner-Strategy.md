# CAPITAL PARTNER STRATEGY
## Warehouse Facility, SPV Architecture, and Path to Securitization
### VERSION 2.0 | Bridgepoint Intelligence Inc. | 2026-04-13

---

> **PURPOSE:** This document lays out BPI's strategy for securing a capital partner to fund Phase 2 (Hybrid) and Phase 3 (Full MLO) bridge lending operations. It is written for internal planning and for sharing with prospective capital partners. Every number is derived from validated models in [Revenue-Projection-Model.md](Revenue-Projection-Model.md) and [Unit-Economics-Exhibit.md](Unit-Economics-Exhibit.md). Where numbers are unflattering, they are presented anyway. Sophisticated capital partners can smell a deck that hides --> hard math -- BPI does not hide it.

> **Income Classification Note:** Phase 1 revenue is IP royalty income (BPI licenses its platform; bank funds and originates all loans). Phase 2 and Phase 3 revenue is lending revenue (BPI deploys capital and earns a share of loan fees). These carry materially different tax and regulatory treatment. This distinction is maintained throughout this document. *(See: [docs/business/feedback_income_classification.md](docs/business/feedback_income_classification.md))*

---

## 1. Why BPI Needs a Capital Partner (and When)

### Phase 1 Requires Zero BPI Capital

In Phase 1 (Licensor), BPI licenses C1-C8 platform to a bank. The bank funds 100% of every bridge loan. BPI earns a **30% royalty on pure IP licensing** -- no warehouse facility, no lending license, no balance-sheet risk.

This is proof period. Phase 1 exists to:
- Demonstrate that the platform works in production (real SWIFT traffic, real UETR settlement)
- Build 12-18 months of auditable loan performance data
- Generate $3.0M+/year revenue from a single conservative Tier 1 bank *(Revenue-Projection-Model.md §2.2)*
- Prove to capital partners that bridge loans self-liquidate as designed

### Phase 2 Changes Everything

In Phase 2 (Hybrid), BPI co-funds 70% of each bridge loan alongside to bank's 30%. BPI's fee share jumps from 30% to 55%. Per bank, revenue multiplies **1.8×** compared to Phase 1. *(Revenue-Projection-Model.md §2.2–2.3)*

But BPI now needs capital to deploy. The transition from Phase 1 to Phase 2 is critical inflection point: BPI must secure a capital facility before it can capture the revenue uplift.

### Timing

Phase 2 begins Year 3-4, after Phase 1 pilot proves to model. The capital partner conversation starts in Year 2 -- warm introductions, performance data sharing, preliminary term negotiation -- so that the facility is committed before BPI is ready to flip to switch.

---

## 2. The Warehouse Facility -- What It Is

A warehouse facility is a revolving credit line secured by loans BPI originates. It is a standard funding mechanism for specialty lenders, mortgage originators, and fintech platforms. Here is how it works for BPI:

### Step 1: Create a Subsidiary SPV

**BPI Capital I Ltd** -- a legally separate special purpose vehicle, 100% owned by BPI Inc. (the parent). The parent holds IP, patents, and platform. The SPV holds the loan book. This separation is non-negotiable.

### Step 2: Capital Partner Commits a Facility Limit

The capital partner commits a facility size (e.g., $10M to start). This is a **commitment**, not deployed cash. BPI pays 25-50 bps/year as a commitment fee on undrawn balance. The capital partner earns commitment fee for making capacity available, regardless of utilization.

### Step 3: Define the Credit Box -- Two-Tier Pricing Structure

BPI's credit box uses a **code-enforced two-tier pricing structure** that ensures SPV economics work from day one:

| Fee Rate | SPV Warehouse-Eligible | Funding Source | BPI Revenue Share |
|-----------|----------------------|------------------|-------------------|
| **300-799 bps** | No (routed to bank) | Bank balance sheet (Phase 1) OR bank-funded below warehouse floor | 30% IP royalty |
| **≥ 800 bps** | Yes (routed to SPV) | SPV warehouse (Phase 2/3) | 55% lending revenue |

**Implementation:**
- Platform floor (300 bps): Applies to ALL loans
- Warehouse floor (800 bps): Required for SPV funding
  - Ensures asset yield (~8%) covers debt service (~7% senior + ~1% BPI equity)
  - Loans priced below 800 bps are automatically routed to bank balance sheet
  - BPI earns 30% IP royalty on those loans
  - Loans at or above 800 bps are SPV warehouse-eligible

**Additional eligibility criteria:**

| Criterion | Source | Rationale |
|-----------|--------|-----------|
| Class A, B, or C only | Rejection taxonomy (C1) | BLOCK class is never bridged -- EPG-19 *(Unit-Economics-Exhibit.md §3)* |
| τ* ≤ 15.2% threshold enforced | C2 PD model | High-risk loans blocked before origination |
| Fee rate ≥ 800 bps | QUANT-controlled floor *(Unit-Economics-Exhibit.md §2)* | Required for SPV warehouse funding. Ensures asset yield (~8%) covers debt service (~7% senior + ~1% BPI equity) |
| UETR binding required | C3 settlement layer | Self-liquidation mechanism must be in place |
| Minimum principal per tier | Unit-Economics-Exhibit.md §4 | Sub-minimum loans uneconomic |
| `hold_bridgeable = true` certification | EPG-04/05 bank warranty | Compliance hold protection |

**Routing Logic:** See `lip/common/constants.py` (WAREHOUSE_ELIGIBILITY_FLOOR_BPS) and `is_spv_warehouse_eligible()` function. The credit box is not a negotiation -- it is the system's own operating envelope. This makes diligence straightforward: capital partner is not underwriting BPI's judgment, they are underwriting the algorithm's constraints.

### Step 4: Draw Against Borrowing Base

When BPI originates an eligible loan, it draws against the facility. The advance rate is typically 80-90% of eligible loan face value. BPI's equity contribution (10-20%) is first-loss tranche -- BPI takes the first dollar of loss on every loan.

### Step 5: Automatic Repayment via SWIFT UETR Settlement

When the underlying cross-border payment settles (confirmed by SWIFT UETR), the bridge loan self-liquidates. The capital partner's principal plus interest returns automatically. No human collection. No dunning. No workout desk. Average cycle time: ~7 days. *(Unit-Economics-Exhibit.md §3: Class B average maturity = 7 days)*

---

## 3. SPV Architecture

```
BPI Inc. (Parent -- holds IP, patents, platform, all licensing agreements)
    │
    ├── Platform License → Banks (C1-C8 system, Phase 1 royalty income)
    │
    └── 100% equity owner of:
            │
            BPI Capital I Ltd (SPV -- warehouse vehicle)
                │
                ├── Senior Lender (Credit Fund / Bank Co-Investor)
                │     └── 85-90% of facility, SOFR + spread, first out in waterfall
                ├── Mezzanine (Family Office)
                │     └── 5-10% of facility, higher spread, second out
                └── BPI First-Loss Equity Tranche
                      └── 5-15% of facility, last out -- eats first losses,
                          earns highest residual return
```

### What This Structure Achieves

**1. Protects BPI's crown jewels.** The IP portfolio, patents, platform code, and bank licensing agreements sit in the parent entity. If the SPV's loan book suffers unexpected losses, the parent is structurally remote. A capital partner's claim stops at the SPV boundary. BPI's IP is never collateral for lending operations.

**2. Creates a tiered capital structure with aligned incentives.**

| Tranche | % of Facility | Target Return | Priority |
|---------|--------------|---------------|----------|
| Senior | 85-90% | SOFR + 200-350 bps (6-8% all-in) | First out |
| Mezzanine | 5-10% | 10-14% | Second out |
| BPI Equity | 5-15% | 30%+ residual (variable) | Last out |

BPI's first-loss position is key: it means BPI's incentives are perfectly aligned with the capital partner's. BPI loses money before anyone else does.

**3. Gives BPI operational control.** BPI retains full origination authority within the agreed credit box. The capital partner does not approve individual loans -- credit box and algorithm do. This is critical for maintaining the platform's sub-second decision speed.

**4. Enables future securitization.** After 12-18 months of clean SPV performance data, BPI can refinance warehouse facility into a rated securitization, dropping cost of capital from ~12% to ~5-6%. The warehouse is a bridge to permanent capital -- not an end state.

---

## 4. Capital Efficiency -- The Honest Math

### The Two-Tier Advantage

With the 800 bps warehouse eligibility floor, SPV-funded loans are profitable from day one:

**Asset pool yield at 800 bps:**
- $1M bridge loan over 7 days = $1,534 fee
- Annualized: $1,534 × (365/7) = **$80,000/year** per $1M
- Asset yield = **8.0%**

**SPV capital structure debt service:**
- Senior (85% at ~7%): $595K annual cost per $8.5M deployed
- BPI equity (55% at 8% yield): ~$374K annual income per $8.5M
- Total SPV cost to cover: **~969K** vs. ~$672K revenue
- **Every SPV-funded loan generates positive equity returns**

**Result:** At 800 bps warehouse floor, the SPV economics work. The capital partner sees assets that service debt. BPI's first-loss tranche earns a positive ~1% margin.

**Phase 2 low-fee loans (<800 bps):**
- Routed to bank balance sheet
- BPI earns 30% IP royalty
- No capital cost for BPI (bank funds 100%)
- These loans provide data for Phase 3 securitization

This creates a natural portfolio optimization: higher-risk borrowers pay higher fees and get SPV funding; lower-risk borrowers pay lower fees and remain bank-funded. Both paths generate data.

---

## 5. Three Deal Terms You Must Never Give Away

### 1. Cross-Default Trigger

**What they will ask for:** Full cross-default -- any default by BPI or any affiliate on any obligation triggers acceleration of the warehouse facility.

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

The patent portfolio is BPI's existential asset. It must never be pledged to a warehouse lender. If BPI's lending book goes to zero, IP remains intact and BPI can rebuild from Phase 1. If IP is pledged and seized, BPI is dead.

### 3. Repurchase Triggers

**What they will ask for:** Broad repurchase obligations -- BPI must buy back any loan that defaults, breaches representations, or fails to settle within maturity window.

**What BPI must negotiate:**
- Repurchase limited to **fraud or misrepresentation** by BPI in originating the loan
- Maturity extension (not repurchase) for loans that settle late but within UETR TTL (45-day buffer per canonical constants)
- UETR settlement is the natural repayment mechanism -- loan is designed to self-liquidate. Repurchase should be an exception (originator misconduct), not a rule (settlement timing variance)

---

## 6. Performance Covenants

### Default Rate Covenant

The τ* = 15.2% threshold is the first line of defense -- it blocks high-risk loans before origination at the platform level. The covenant should reference the system's own risk threshold: loans that clear τ* and still default represent tail risk, not underwriting failure.

Negotiate a default rate covenant at a level that reflects the system's expected performance plus a reasonable buffer. If Phase 1 data shows a 0.5% annualized default rate, propose a covenant at 2.0% -- four times observed performance.

### Concentration Limits

| Period | Maximum Single-Bank Concentration | Rationale |
|--------|----------------------------------|-----------|
| Month 0-12 | 100% (single bank allowed) | Phase 2 starts with one bank; forcing diversification before it exists is meaningless |
| Month 12-18 | 60% | Second bank onboarded; step-down begins |
| Month 24-30 | 40% | Third bank; approaching diversified book |

Negotiate a Year 1 single-bank allowance upfront. Capital partners will push for 50% concentration limits from day one -- this is structurally impossible for a startup scaling one bank at a time. The step-down schedule shows a credible path to diversification without constraining early operations.

### Leverage for Refinancing

Clean covenant performance in Year 1 is ammunition for Year 2 refinancing conversations. Every month of zero defaults, on-time UETR settlement, and within-covenant performance is a data point that reduces BPI's cost of capital at renewal.

---

## 7. The Sequencing Chess Game

Four moves, in order:

### Move 1: Close Architecture Gaps

Ensure that C1-C8 pipeline is production-ready and all architecture sign-off items are resolved. Per BPI Architecture Sign-Off Record, the core pipeline (1,410+ tests passing) is implemented. Remaining items are contractual (MRFA B2B clause, EPG-04/05 bank warranty language) -- these are legal work, not engineering work.

**Status:** Substantially complete. Remaining gaps are legal/contractual, not technical.

### Move 2: Warm Introductions to Capital Partners

Target list (Canadian market, BPI's home jurisdiction):

| Type | Examples | Rationale |
|------|----------|-----------|
| BDC / Government-backed | BDC Capital | Mandate to support Canadian fintech; patient capital |
| Private debt funds | Fiera Private Debt, RP Investment Advisors | Specialty lending appetite; structured credit expertise |
| Family offices | Toronto-based family offices with fintech or payments thesis | Flexible on structure; can move faster than institutional funds |
| Credit funds | Canadian and US credit opportunity funds | Higher return targets align with mezz tranche |

Start conversations 12+ months before capital is needed. Share Phase 1 performance data quarterly. Build relationship before you ask.

### Move 3: Anchor Investor Mechanism

Ask the first capital partner for **$5M as an anchor commitment**. Structure the facility with capacity for a co-investor (second $5M tranche). The anchor gets:
- First look at deal flow and performance data
- Slightly better economics (lower spread or commitment fee) in exchange for anchoring
- Pro-rata rights on facility expansion

The anchor commitment de-risks co-investor conversation: "We have $5M committed from [credible name], looking for $5M co-invest."

### Move 4: Conditional LOI Exchange

This is a critical choreography:

1. Capital partner commitment is **conditional on** BPI having a signed bank LOI (proving there are loans to fund)
2. Bank LOI is **conditional on** BPI having committed capital (proving BPI can co-fund Phase 2)
3. Both close simultaneously -- neither party takes unconditional risk

This is standard in specialty lending. The capital partner's counsel and the bank's counsel are accustomed to conditional closings. BPI's job is to get both parties to the table at the same time, not to close either one first.

---

## 8. The Psychology of Pre-Committed Capital

### Version A: BPI Without Capital (Evaluation Mode)

> "We have a patent-protected platform for bridge lending on failed cross-border payments. We'd like to discuss a Phase 2 deployment where your bank co-funds bridge loans alongside us."

The bank hears: startup, unproven, needs capital, will they even be around next year? The bank enters **evaluation mode** -- months of diligence, committee reviews, pilot scope negotiations, legal back-and-forth.

### Version B: BPI With Committed Capital (Infrastructure Mode)

> "We have a patent-protected platform already processing [X] bridge loans per month in Phase 1. We have a $10M warehouse facility committed by [credible capital partner name]. We're ready to deploy Phase 2 on [specific corridor] with 70/30 co-funding. Here is 12 months of performance data."

The bank hears: capitalized infrastructure, proven performance, ready to deploy. The bank shifts from evaluation mode to **FOMO mode** -- how fast can we get live? What corridors are available? Are our competitors already talking to BPI?

The difference is not the platform. The difference is that pre-committed capital transforms BPI from a vendor to be evaluated into infrastructure to be accessed.

**This is why capital partner conversation must start before Phase 2 bank conversation.** Even if the capital partner's commitment is conditional on a bank LOI (Move 4 above), the *existence* of a capital partner in conversation changes the bank's psychological frame from day one.

---

## 9. The Securitization Path

### The Warehouse Is a Bridge, Not a Destination

After 12-18 months of clean SPV performance data, BPI can refinance the warehouse facility into a rated securitization:

| Parameter | Warehouse (Year 1-2) | Securitization (Year 3+) |
|-----------|----------------------|--------------------------|
| Cost of capital (senior) | SOFR + 200-350 bps (~6-8%) | SOFR + 50-150 bps (~5-6%) |
| Blended cost | ~12% | ~5-6% |
| Facility size | $5-20M | $50-200M+ |
| Investor base | 1-3 private lenders | Rated note buyers (insurance, pensions, asset managers) |
| Ongoing relationship | Bilateral, relationship-dependent | Market access, repeatable |

### What Changes at Securitization

Recall the two-tier pricing structure from Section 4:

- Loans at or above 800 bps are SPV-funded and eligible for securitization
- Asset yield at 800 bps is ~8%, which covers SPV capital costs (~8% total)
- After securitization, SPV loans generate positive equity returns

| Item | Warehouse | Securitization |
|------|-----------|----------------|
| BPI effective yield | 8% | 8% |
| Cost of capital | ~8% | ~5-6% |
| Net spread | **0%** | 8% - 8% = 0% (vs -3.3% previously) |
| BPI equity ROE | **+1%** | Improving with scale |

### The Capital Partner's Exit

The warehouse-to-securitization transition is also the capital partner's natural exit:
- Their warehouse facility is "taken out" by securitization proceeds
- They earn their preferred rate for 12-18 months with minimal duration risk (7-day average loan life)
- They can reinvest in a new BPI Capital II vehicle or exit cleanly
- Clean exit mechanics make the initial warehouse commitment more attractive

### What BPI Needs for Securitization

1. **12-18 months of auditable loan-level performance data** -- default rates, recovery rates, settlement timing, loss severity
2. **Rating agency engagement** -- Moody's, DBRS, or Kroll for Canadian-issued paper
3. **Servicing track record** -- proof that BPI can manage collections (which, given UETR auto-settlement, is mostly proof that technology works)
4. **Legal opinion on true sale** -- loans transferred from BPI to SPV are a "true sale" for bankruptcy remoteness

---

## 10. Capital Partner Pitch -- The Five Numbers

When BPI sits across the table from a capital partner, five numbers tell the story:

### 1. $31.7 Trillion

Annual cross-border payment volume (FXC Intelligence, 2024). This is the ocean BPI operates in. *(Revenue-Projection-Model.md §1.1)*

### 2. 7 Days

A bridge loan duration. Self-liquidating against SWIFT UETR settlement confirmation. The capital partner's money comes back in a week -- not a month, not a quarter, not a year. 52 capital turns per year. *(Unit-Economics-Exhibit.md §3)*

### 3. 800 Basis Points (Warehouse Floor) -- 300 Basis Points (Platform Floor)

**Platform floor (300 bps):** Applies to ALL loans. BPI earns IP royalty on bank-funded loans regardless of fee rate.

**Warehouse floor (800 bps):** Required for SPV funding. Loans priced below 800 bps are routed to bank balance sheet. Loans at or above 800 bps are SPV warehouse-eligible and generate positive BPI equity returns.

### 4. $3M+

BPI's annual revenue from Phase 1 (licensor) pilot. Proven before BPI asks for capital. The capital partner is not funding a hypothesis -- they are scaling a proven revenue stream. *(Revenue-Projection-Model.md §2.2)*

### 5. 12-18 Months

Time from warehouse close to securitization-ready. Clean performance data enables a rated deal, cost of capital collapses from ~12% to ~5-6%. This is the timeline for a capital partner's deployment -- not a 5-year lockup, not a venture-style 10-year fund.

---

*Cross-references: [Revenue-Projection-Model.md](Revenue-Projection-Model.md) | [Unit-Economics-Exhibit.md](Unit-Economics-Exhibit.md)*

*This document contains forward-looking estimates based on internal models. All projections are subject to market conditions, regulatory approvals, and successful Phase 1 pilot performance.*
