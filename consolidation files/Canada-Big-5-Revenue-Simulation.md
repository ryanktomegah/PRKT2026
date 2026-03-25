# CANADA BIG 5 REVENUE SIMULATION
## Bottom-Up Revenue Model for RBC, TD, Scotiabank, BMO, CIBC
### VERSION 1.0 | Bridgepoint Intelligence Inc. | 2026-03-25

---

> **PURPOSE:** This document provides a bank-specific revenue simulation for BPI's Canada beachhead strategy. Each of the Big 5 Canadian banks is modelled individually using public financial disclosures to estimate cross-border payment volume, bridge loan opportunity, and BPI revenue contribution across a 10-year horizon. Three scenarios (conservative, base, upside) are provided. All fee calculations use the canonical 30/55/80 phase splits from Unit-Economics-Exhibit.md §5.1.

---

## 1. Strategic Rationale — Why Canada First

### 1.1 Home Jurisdiction Advantages

- **Regulatory relationship:** OSFI is BPI's home regulator. First regulatory conversations happen in the same time zone, under familiar rules (CBCA incorporation, OSFI Guideline B-13).
- **Tax advantages:** SR&ED eligibility for platform development costs; potential IP box treatment for Phase 1 royalty income under Canadian tax rules.
- **Proof-of-concept value:** "All Big 5 Canadian banks use LIP" is a global pitch that requires no explanation. Canada's concentrated banking market makes this achievable; a fragmented market (US, EU) does not.
- **Pilot proximity:** Legal disputes, MRFA renegotiation, and platform issues can be resolved with in-person meetings. Time zones and travel costs matter for a startup.

### 1.2 Market Concentration

Canada's Big 5 banks control approximately **85% of Canadian banking assets** (~$7.2T total system assets). A startup that needs to prove its product can reach 85% market penetration in its home market by selling to 5 customers. This is structurally unusual and strategically valuable.

### 1.3 International Exposure

Canadian Big 5 banks have significant cross-border operations — particularly RBC (Caribbean, US), TD (US retail and wholesale), and Scotiabank (Latin America, Caribbean). These are high-failure-rate corridors. LIP's value proposition is strongest where failure rates are highest.

### 1.4 Cross-Reference

See Operational-Playbook-v2.1.md Phase 4 for the first commercial bank conversation timeline post-PFD.

---

## 2. Per-Bank Cross-Border Volume Estimates

All figures are internal estimates derived from public financial disclosures (annual reports, investor day presentations) and industry benchmarks. They are planning estimates, not audited figures.

### 2.1 Methodology

Cross-border payment volume is not directly disclosed by Canadian banks. It is estimated from:
1. **International revenue segment size** — international banking divisions report revenue; cross-border payment volume is inferred from revenue-to-volume ratios for comparable global banks (BIS CPMI data: ~5–8 bps revenue per dollar of cross-border volume)
2. **Total assets as proxy** — banks with larger international asset bases process higher cross-border volumes
3. **Corridor analysis** — bank-specific geographic exposure (e.g., Scotiabank's LatAm operations) indicates which corridors are most active

### 2.2 Estimated Cross-Border Payment Volumes

| Bank | Total Assets (2025E) | International Revenue Mix | Est. Annual Cross-Border Volume | Primary Corridors |
|------|---------------------|--------------------------|--------------------------------|------------------|
| **RBC** | ~$2.0T | ~18% (Caribbean, US, UK) | $180B–$360B | CAD↔USD, CAD↔GBP, CAD↔EUR |
| **TD** | ~$1.9T | ~35% (US retail + wholesale) | $330B–$665B | CAD↔USD (dominant), CAD↔EUR |
| **Scotiabank** | ~$1.3T | ~30% (LatAm, Caribbean) | $195B–$390B | CAD↔USD, USD↔MXN, USD↔COP, USD↔PEN |
| **BMO** | ~$1.1T | ~25% (US operations) | $138B–$275B | CAD↔USD (dominant), CAD↔EUR |
| **CIBC** | ~$900B | ~12% (US commercial) | $54B–$108B | CAD↔USD primarily |

**Key insight:** TD and Scotiabank are the highest-value targets for LIP due to volume and corridor diversity. TD's US operations generate the highest raw volume; Scotiabank's LatAm corridors have above-average failure rates.

### 2.3 Failure Rate Assumptions by Bank

Failure rates vary by corridor. Banks with higher LatAm/Caribbean exposure have higher failure rates:

| Bank | Blended Failure Rate (Conservative) | Blended Failure Rate (Base) | Rationale |
|------|-------------------------------------|----------------------------|-----------|
| RBC | 3.0% | 3.5% | Majority US/UK corridors — lower failure rates |
| TD | 3.0% | 3.5% | Majority US corridor — lower failure rates |
| Scotiabank | 4.0% | 5.0% | LatAm/Caribbean corridors — elevated failure rates |
| BMO | 3.0% | 3.5% | Majority US corridor |
| CIBC | 3.0% | 3.5% | Majority US corridor |

---

## 3. Per-Bank Revenue Model

### 3.1 Formula (from Revenue-Projection-Model.md v1.1 §2.1)

```
Eligible failures/year = bank_volume × failure_rate × eligible_pct / avg_principal
Fee per loan = avg_principal × (fee_bps / 10,000) × (avg_maturity / 365)
Total fee/year = eligible_failures × fee_per_loan
BPI revenue = total_fee × bpi_fee_share
```

Phase splits: Phase 1 = 30%, Phase 2 = 55%, Phase 3 = 80% *(Unit-Economics-Exhibit.md §5.1)*

### 3.2 RBC — Worked Example (Conservative Scenario)

| Parameter | Value | Source/Rationale |
|-----------|-------|-----------------|
| Annual cross-border volume | $180B | Conservative end of range |
| Failure rate × eligible % | 3.0% × 40% = 1.2% | Conservative failure rate, 40% eligible |
| Annual bridge volume | $2.16B | $180B × 1.2% |
| Average principal | $800K | Conservative (Class B dominant) |
| Loans/year | 2,700 | $2.16B ÷ $800K |
| Average maturity | 7 days | Class B weighted average |
| Fee per loan | $614.90 | $800K × (350/10,000) × (7/365) |
| Total fee/year | $1.66M | 2,700 × $614.90 |
| BPI Phase 1 (30%) | **$498K** | |
| BPI Phase 2 (55%) | **$913K** | |
| BPI Phase 3 (80%) | **$1.33M** | |

### 3.3 Per-Bank Revenue Summary — Three Scenarios

All figures represent **annual BPI revenue per bank** at each phase.

**Conservative Scenario** (lower-bound volume, 3.0–4.0% failure rate, 40% eligible, $800K avg principal, 350 bps):

| Bank | Total Fee/Year | Phase 1 (30%) | Phase 2 (55%) | Phase 3 (80%) |
|------|---------------|--------------|--------------|--------------|
| RBC | $1.66M | $498K | $913K | $1.33M |
| TD | $3.07M | $921K | $1.69M | $2.46M |
| Scotiabank | $3.04M | $913K | $1.67M | $2.43M |
| BMO | $2.02M | $606K | $1.11M | $1.62M |
| CIBC | $791K | $237K | $435K | $633K |
| **Big 5 Total** | **$10.6M** | **$3.2M** | **$5.8M** | **$8.5M** |

**Base Scenario** (mid-range volume, 3.5–5.0% failure rate, 50% eligible, $1M avg principal, 400 bps):

| Bank | Total Fee/Year | Phase 1 (30%) | Phase 2 (55%) | Phase 3 (80%) |
|------|---------------|--------------|--------------|--------------|
| RBC | $14.4M | $4.3M | $7.9M | $11.5M |
| TD | $26.6M | $8.0M | $14.6M | $21.3M |
| Scotiabank | $33.8M | $10.1M | $18.6M | $27.0M |
| BMO | $17.5M | $5.3M | $9.6M | $14.0M |
| CIBC | $6.9M | $2.1M | $3.8M | $5.5M |
| **Big 5 Total** | **$99.2M** | **$29.8M** | **$54.6M** | **$79.4M** |

**Upside Scenario** (upper-bound volume, 4.5–6.0% failure rate, 60% eligible, $1.5M avg principal, 450 bps):

| Bank | Total Fee/Year | Phase 1 (30%) | Phase 2 (55%) | Phase 3 (80%) |
|------|---------------|--------------|--------------|--------------|
| RBC | $73.4M | $22.0M | $40.4M | $58.7M |
| TD | $135.5M | $40.7M | $74.5M | $108.4M |
| Scotiabank | $157.1M | $47.1M | $86.4M | $125.7M |
| BMO | $89.2M | $26.8M | $49.1M | $71.4M |
| CIBC | $35.2M | $10.6M | $19.4M | $28.2M |
| **Big 5 Total** | **$490.4M** | **$147.1M** | **$269.7M** | **$392.3M** |

---

## 4. Aggregate Big 5 Revenue by Year

### 4.1 Recommended Onboarding Sequence

| Order | Bank | Rationale |
|-------|------|-----------|
| **1st** | Scotiabank | Highest LatAm/Caribbean corridor failure rates — strongest immediate value proposition; innovation posture more aggressive than RBC/TD |
| **2nd** | TD | Largest US corridor volume; strong innovation track record (TD Lab); US operations create cross-border regulatory simplicity |
| **3rd** | RBC | Largest Canadian bank by assets; Caribbean exposure adds value; relationship with OSFI strongest |
| **4th** | BMO | US operations post-Bank of the West acquisition (2023); growing cross-border footprint |
| **5th** | CIBC | Smallest international footprint of the Big 5; onboard last for maximum pilot data to support pitch |

### 4.2 Year-by-Year Revenue (Base Scenario)

| Year | Banks Live | Phase | BPI Revenue from Big 5 |
|------|-----------|-------|------------------------|
| 3 | 1 (Scotiabank, P1) | Phase 1 | $10.1M |
| 4 | 2 (+ TD, P1) | Phase 1 | $10.1M + $8.0M = **$18.1M** |
| 5 | 3 (+ RBC, P1/2 transition for Scotiabank) | P1/P2 mix | **~$32M** |
| 6 | 4 (+ BMO, Scotiabank→P2) | P1/P2 mix | **~$55M** |
| 7 | 5 (all Big 5, P1/P2 mix) | P1/P2 mix | **~$75M** |
| 8 | 5 (P2 for all) | Phase 2 | **$54.6M** (P2 rate) |
| 10 | 5 (Phase 3 for earliest banks) | P2/P3 mix | **~$65–70M** |

**Big 5 cumulative revenue Years 3–10 (base scenario): ~$370–$420M**

### 4.3 The Phase 3 Transition — Canada Alone

At Phase 3 for all five Big 5 banks, base scenario: **$79.4M/year** from Canada alone.

This represents ~9% of the total Year 10 base scenario ($921M) from a single country with five customers. The "prove Canada, expand globally" thesis is quantitatively justified.

---

## 5. Canada as Percentage of Global Revenue

| Year | Big 5 Revenue (Base) | Total BPI Revenue (Base) | Canada Share |
|------|---------------------|--------------------------|-------------|
| 3 | $10.1M | $23.0M | 44% |
| 6 | ~$55M | $211M | 26% |
| 10 | ~$70M | $921M | 8% |

Canada is dominant in the early years (proving the model) and becomes a smaller percentage as global expansion accelerates. This is the intended trajectory: Canada as proof-of-concept, global expansion as value creation.

---

## 6. Risks Specific to the Canadian Market

### 6.1 OSFI Regulatory Risk
OSFI has not yet issued specific guidance on bridge lending by non-bank technology platforms. BPI's Phase 1 (IP royalty, bank funds loans) is low regulatory risk. Phase 2/3 requires legal counsel to confirm OSFI's classification of BPI's lending operations. *(REX authority: regulatory classification must be confirmed before Phase 2 launch.)*

### 6.2 Big 5 Concentration Risk
All five banks use the same regulator, similar compliance frameworks, and comparable IT procurement processes. A single adverse regulatory event (e.g., OSFI guidance against third-party bridge lending) affects all five simultaneously. Geographic diversification beyond Canada is the mitigation — which is why global expansion (Years 4–6) cannot wait for full Canadian saturation.

### 6.3 CAD Corridor Limitations
CAD is not a major international currency. Most of the Big 5's cross-border volume is actually USD-denominated (USD↔other currency) routed through their Canadian operations. BPI's platform operates on ISO 20022 message types regardless of currency — this is not a technical limitation, but it means failure rates on pure CAD↔other corridors may be lower than USD↔other corridors.

### 6.4 Bank IT Procurement Cycles
Big 5 IT change management committees review new vendor integrations annually (Q4 budget cycles, Q1 sign-off). Missing a budget cycle means a 12-month delay. BPI must initiate conversations with each bank in Q1 of the target year for Q4 budget inclusion — arriving in Q3 means waiting until the following year.

### 6.5 MRFA Renegotiation Risk
Each bank's legal team will re-examine the MRFA independently, even if BPI has a clean precedent from Scotiabank. The EPG-14 B2B structure (bank as borrower, not end customer), the EPG-19 compliance hold protections, and the EPG-04/05 `hold_bridgeable` warranty language will all be scrutinised. Budget 6–9 months of legal negotiation per bank. Template acceleration kicks in from bank #3 onward.

---

## 7. Comparison to Global Revenue Model

At Phase 3 for all Big 5 (base scenario), Canada contributes $79.4M/year. The global 15-bank model contributes $921M/year. The Big 5 represent **~9% of the global model** at Year 10 — yet they are 5 of 15 banks (33% of bank count). This reflects the Big 5's relatively lower cross-border volumes compared to global Tier 1 banks (Deutsche Bank, HSBC, JPMorgan each have 10–30× Canadian Big 5 cross-border volumes).

**Implication:** Canada proves the model but is not the primary value creation engine. Global Tier 1 bank onboarding (Years 4–8) is where the base and upside scenarios diverge dramatically from the conservative.

---

*Cross-references: [Revenue-Projection-Model.md](Revenue-Projection-Model.md) (base model and per-bank formula) | [Unit-Economics-Exhibit.md](Unit-Economics-Exhibit.md) (fee formula, phase splits) | [Market-Fundamentals-Fact-Sheet.md](Market-Fundamentals-Fact-Sheet.md) (failure rates, settlement timing) | [Growth-Acceleration-Strategy.md](Growth-Acceleration-Strategy.md) (SWIFT and regulatory strategies that accelerate Big 5 onboarding) | [Operational-Playbook-v2.1.md](Operational-Playbook-v2.1.md) (Phase 4 commercial timeline)*

*All bank volume estimates are internal planning estimates derived from public disclosures. Not for external distribution. All projections subject to market conditions, regulatory approvals, and successful Phase 1 pilot performance.*
