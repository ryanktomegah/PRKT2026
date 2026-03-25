# GROWTH ACCELERATION STRATEGY
## Beyond Bank-by-Bank Sales: SWIFT Partnership, Regulatory Tailwinds, Data Moat, and Capital Partner Distribution
### VERSION 1.0 | Bridgepoint Intelligence Inc. | 2026-03-25

---

> **PURPOSE:** The Revenue-Projection-Model.md baseline trajectory (2 new banks/year from Year 3) assumes organic bank-by-bank sales only. This document maps four acceleration strategies that can transform that trajectory — from linear growth into exponential adoption. Each strategy is independently valuable; together they are multiplicative.

---

## 1. The Baseline Problem: Bank-by-Bank Sales Is Linear

LIP's current go-to-market is individual bank sales: identify a target bank, navigate their IT committee, negotiate the MRFA, complete integration, go live. This process takes 12–24 months per bank from first conversation to first loan. At 1–2 new banks per year, reaching 15 banks takes a decade.

This is not a failure of the product — it is a structural feature of how large banks procure infrastructure. The question is whether BPI can change the procurement dynamic through channels that bypass or compress the standard cycle.

Four strategies can do this. None require changes to the platform. All are commercially executable within the first three years post-PFD.

---

## 2. Strategy 1: SWIFT Partnership

### 2.1 The Strategic Logic

SWIFT gpi already tracks payment failures via UETR. LIP is the "what happens next" layer. Together, they form a complete failure detection + resolution product:

- **SWIFT sees the problem** — gpi telemetry identifies the specific payment event and its status
- **LIP provides the solution** — C1 classifier ingests the same telemetry, triggers the bridge loan offer, collects repayment on UETR settlement

This is not a technical integration. LIP already consumes ISO 20022 pacs/camt messages natively. A SWIFT partnership is a **business relationship**, not an engineering project.

### 2.2 Three Partnership Tiers

| Tier | Structure | What Changes | Timeline |
|------|-----------|-------------|---------|
| **Tier 1: Endorsed Add-On** | LIP listed on SWIFT Partner Programme | Banks find LIP through their existing SWIFT relationship; reduces cold outreach to warm inbound | Year 3–4 post-PFD |
| **Tier 2: gpi Integration** | When gpi detects a failure event, LIP offer is triggered in the gpi flow | Changes sales from "convince bank to try LIP" to "LIP is part of the gpi product banks already use" | Year 4–6 post-PFD |
| **Tier 3: Infrastructure Embedding** | LIP capability built into SWIFT's own service layer | Maximum reach (4,500+ gpi institutions); minimum per-bank sales effort | Year 7–10 post-PFD |

Tier 1 is achievable through standard SWIFT Partner Programme registration. Tier 2 requires SWIFT commercial negotiation. Tier 3 is a long-horizon aspiration.

### 2.3 SWIFT's Incentive Alignment

SWIFT wants to be more than messaging infrastructure. Their strategic narrative since 2021 has been "payment intelligence" — not just moving money, but making payments smarter. LIP adds a capability SWIFT cannot build themselves without entering the credit business (which their member-owned governance structure prohibits). **LIP makes SWIFT more valuable to banks without SWIFT taking credit risk.** That is an unusual alignment of interests.

The Sibos conference (SWIFT's annual gathering, ~10,000 attendees) is the venue to initiate this conversation. A demo of LIP operating on live SWIFT telemetry — showing detection, pricing, and auto-repayment — is the most credible possible opening.

### 2.4 Revenue Impact: Three Scenarios

| Scenario | Bank Onboarding Rate | Year 10 Banks | Year 10 BPI Revenue (Base) |
|----------|---------------------|---------------|---------------------------|
| No SWIFT relationship | 2/year | 15 | ~$921M |
| Tier 1 endorsement | 3–4/year | 20–25 | ~$1.2B–$1.5B |
| Tier 2 gpi integration | 5–6/year | 30–35 | ~$1.8B–$2.1B |
| Tier 3 infrastructure | 8–10/year | 50+ | ~$3B+ |

*Revenue estimates use base case per-bank figures from Revenue-Projection-Model.md v1.1 §2.3.*

### 2.5 Risks and Prerequisites

- **SWIFT revenue share:** SWIFT will seek a royalty on LIP usage by their member banks. Budget 5–15% of LIP royalty income from SWIFT-referred banks as the relationship cost. This is worthwhile at any adoption acceleration above 20%.
- **Patent implications:** A SWIFT endorsement does not create licensing obligations but may trigger Tier 3 banks to scrutinise the patent portfolio more carefully. File P3 before initiating Tier 2 conversations.
- **Regulatory oversight:** SWIFT is regulated by the Belgian National Bank with G10 central bank oversight. Any Tier 2/3 integration will require SWIFT's regulatory counsel approval. REX must be involved from the first substantive conversation.
- **Timing:** Do not initiate SWIFT partnership conversations before 12 months of live pilot data exist. An empty track record weakens the pitch.

---

## 3. Strategy 2: Regulatory Tailwind Manufacturing

### 3.1 The Strategic Logic

Banks adopt infrastructure for two reasons: competitive differentiation (first-mover) or regulatory expectation (compliance). The first-mover dynamic is already captured in the commercial strategy. The regulatory pathway is an underexploited lever.

If regulators begin to expect payment resilience mechanisms, banks must adopt — not to gain advantage, but to avoid falling behind supervisory expectations. BPI does not need regulators to mandate LIP. BPI needs regulators to establish that payment resilience is a supervisory priority.

### 3.2 Target Regulators and Current Posture

| Regulator | Jurisdiction | Current Posture | BPI Opportunity |
|-----------|-------------|----------------|----------------|
| **OSFI** | Canada | Guideline B-13 (Technology and Cyber Risk, 2022) includes operational resilience for payment systems | Most accessible — BPI's home regulator; target first |
| **FCA** | UK | Consumer Duty (2023) requires banks to demonstrate payment outcome improvement | Position LIP as tool for meeting payment outcome obligations |
| **ECB/EBA** | Eurozone | DORA (2025) requires ICT operational resilience; ECB payment strategy targets instant payment reliability | LIP data feeds DORA operational resilience reporting |
| **FSB / G20** | Global | Cross-Border Payments Roadmap: 75% of B2B payments within 1 hour by 2027. Current rate: 5.9% (FSB 2024) | LIP directly addresses the gap between 5.9% and 75% target |
| **BIS/CPMI** | Global standards | CPMI consultation papers on cross-border payment efficiency published regularly | Respond to consultations with live deployment data |

### 3.3 The Consultation Paper Response Strategy

Regulators publish consultation papers before setting expectations. BPI should respond to every relevant consultation with:

1. Empirical data from live deployments (anonymised, aggregated)
2. Quantified evidence that LIP-style mechanisms improve payment resilience outcomes
3. Policy language suggesting "payment resilience mechanisms" as a supervisory expectation

Each response creates a precedent. When a regulator eventually sets expectations citing "mechanisms like payment bridging facilities," BPI has been in the regulatory record for years. The first bank to read that supervisory guidance will call BPI.

### 3.4 The Regulatory Cascade Effect

Once one major regulator (OSFI or FCA) establishes payment resilience as a supervisory priority, others follow within 2–4 years. The Basel III capital framework, DORA, and FATF recommendations all propagated through this cascade mechanism. BPI needs one regulator — not all of them.

*REX governance: all regulatory engagement strategy, consultation paper responses, and any representation to regulators requires REX sign-off. REX has final authority on compliance positioning.*

### 3.5 Timeline and Sequencing

| Period | Activity | Goal |
|--------|----------|------|
| Year 1–2 (pre-pilot) | Build regulatory relationships, attend OSFI and FCA industry events | Establish BPI as a known voice on payment resilience |
| Year 2–3 (post-pilot) | Begin consultation paper responses with pilot data | Enter the regulatory record |
| Year 3–5 | Speaking engagements, published anonymised data (Annual Failure Rate Report) | Establish BPI as data authority |
| Year 5–7 | OSFI or FCA supervisory guidance begins referencing payment resilience mechanisms | Banks start treating LIP as compliance infrastructure, not optional product |

---

## 4. Strategy 3: The Annual Failure Rate Report

### 4.1 The Concept

Beginning one year after the first pilot bank goes live, BPI publishes an annual report: *Cross-Border Payment Failure Benchmarks — [Year]*. Content: anonymised, aggregated failure rates by corridor class, rejection code distributions, P95 settlement timing benchmarks, and working capital gap estimates — derived from live BPI deployment data across all enrolled banks.

### 4.2 Why This Matters Competitively

No such report currently exists with live SWIFT telemetry data. The BIS CPMI Red Book and McKinsey Global Payments Report use survey data and aggregate SWIFT statistics — not labeled outcome data from actual bridging deployments. BPI will be the first organisation able to publish performance data at the corridor/rejection-class level because BPI is the only organisation with labeled bridge loan outcome data.

This creates an authority asymmetry: BPI becomes the citation source for cross-border payment failure statistics. Academic papers, regulator consultation documents, and bank board presentations will cite BPI data — not the other way around.

### 4.3 Strategic Purposes

1. **Sales tool:** "Your bank's EUR→INR failure rate is 4.7% vs an industry median of 3.2%" — a statement that requires no BPI representative in the room to create urgency
2. **Regulatory credibility:** Every consultation paper response BPI submits can cite proprietary data no other organisation has
3. **Data moat proof:** The existence of multi-bank aggregated data demonstrates scale without revealing proprietary details — a powerful signal to prospective banks
4. **Earned media:** Annual payment industry reports generate press coverage, conference invitations, and analyst attention at zero marginal cost

### 4.4 Data Governance

| What Can Be Published | What Cannot |
|----------------------|------------|
| Aggregate failure rates by rejection class (A/B/C/BLOCK) | Any bank-identifiable data |
| Corridor-level benchmarks (EUR→INR, USD→CNY, etc.) | Individual UETR or transaction data |
| P95 settlement timing by class | Bank-specific performance data |
| Industry-level working capital gap estimates | C2 model weights or proprietary risk parameters |

*CIPHER sign-off required on anonymisation methodology before any data is prepared for publication. REX sign-off required on regulatory compliance (GDPR Article 89, PIPEDA, banking secrecy obligations in relevant jurisdictions).*

### 4.5 Precedents

| Publication | Publisher | Authority Created |
|-------------|-----------|------------------|
| Global Payments Report | McKinsey | Market sizing benchmark; cited by every payments company |
| Red Book | BIS CPMI | Regulatory reference for payment system statistics |
| SWIFT Annual Review | SWIFT | Message volume and growth data |

BPI's report will be more operationally specific than any of these — because BPI has labeled outcome data, not just volume statistics.

---

## 5. Strategy 4: Capital Partner as Distribution Channel

*This strategy is documented in full in Capital-Partner-Strategy.md §11. Summary:*

Capital partners (BlackRock Credit, Apollo, CDPQ) have direct relationships with 50+ banks each. Their incentive to introduce BPI to banks is structural — more BPI volume means more AUM deployment for the capital partner. With a Tier 1 capital partner actively co-selling, bank onboarding rate increases to 3–4 banks/year (Year 3–5) and 8–10 banks by Year 8, versus 5 banks on organic sales alone.

---

## 6. Combined Impact: Three Scenarios

The four strategies are not additive — they are multiplicative. SWIFT endorsement creates awareness; regulatory tailwind creates urgency; the Annual Failure Rate Report provides data-driven pressure; the capital partner closes deals.

| Scenario | Active Strategies | Year 5 Banks | Year 10 Banks | Year 10 BPI Revenue (Base) |
|----------|------------------|-------------|---------------|---------------------------|
| **Baseline** | Organic sales only | 3–4 | 15 | ~$921M |
| **One channel** | + SWIFT Tier 1 OR capital partner | 5–6 | 20–22 | ~$1.2B–$1.4B |
| **Two channels** | + SWIFT Tier 1 AND capital partner | 7–9 | 28–32 | ~$1.7B–$2.0B |
| **Three channels** | + Regulatory tailwind activating | 10–12 | 40–50 | ~$2.5B–$3.1B |
| **Full stack** | All four strategies active | 12–15 | 50+ | ~$3.1B+ |

*Revenue estimates use base case per-bank Phase 3 economics from Revenue-Projection-Model.md v1.1 §2.3 ($61.4M/bank/year at Phase 3). Year 10 revenue assumes Phase 2/3 mix across the bank population.*

---

## 7. Prioritisation and Sequencing

Not all strategies activate simultaneously. Sequencing matters:

| Priority | Strategy | Why First | Prerequisites |
|----------|----------|-----------|--------------|
| **1** | Annual Failure Rate Report | Requires only pilot data; produces compounding value from Year 2 | 12 months of live deployment data |
| **2** | Capital Partner Distribution | Accelerates bank onboarding immediately; sets up Phase 2 | Capital facility committed (pre-Phase 2) |
| **3** | SWIFT Tier 1 Endorsement | Requires credible track record; low cost to initiate | 12+ months pilot data + P3 filed |
| **4** | Regulatory Engagement | Long lead time; 3–5 year payoff | Pilot data + regulatory relationship building starts Year 1 |
| **5** | SWIFT Tier 2 Integration | Requires SWIFT commercial negotiation | Tier 1 relationship + multiple banks live |

---

*Cross-references: [Revenue-Projection-Model.md](Revenue-Projection-Model.md) (base trajectory) | [Capital-Partner-Strategy.md §11](Capital-Partner-Strategy.md) (capital partner distribution) | [Competitive-Landscape-Analysis.md §5](Competitive-Landscape-Analysis.md) (data moat and Annual Failure Rate Report) | [Canada-Big-5-Revenue-Simulation.md](Canada-Big-5-Revenue-Simulation.md) (Canadian market beachhead) | [Market-Fundamentals-Fact-Sheet.md](Market-Fundamentals-Fact-Sheet.md) (FSB G20 5.9% statistic, SWIFT gpi data)*

*This document contains forward-looking estimates based on internal models. All projections are subject to market conditions, regulatory developments, and successful Phase 1 pilot performance.*
