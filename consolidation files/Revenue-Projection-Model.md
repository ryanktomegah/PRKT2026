# REVENUE PROJECTION MODEL
## Bottom-Up Bridge Loan Revenue by Deployment Phase
### VERSION 1.0 | Bridgepoint Intelligence Inc. | 2026-03-20

---

> **PURPOSE:** This document replaces the top-down royalty projections in Patent-Family-Architecture-v2.1.md Section 3 with a transparent bottom-up model. Every assumption is stated, every calculation is shown, and three scenarios (conservative, base, upside) are provided. All figures are internal planning estimates only.

---

## 1. Key Assumptions

### 1.1 Market Fundamentals

| Parameter | Value | Source |
|-----------|-------|--------|
| Global cross-border B2B payment volume (2024) | $31.7 trillion/year | FXC Intelligence, 2024 |
| Payment failure/delay rate (midpoint) | 4.0% | STP-derived estimate; BIS/SWIFT GPI range 3–5% |
| Annual disrupted volume | ~$1.27 trillion | $31.7T × 4% |
| Addressable bridge volume (excl. compliance holds, same-day resolution) | ~$635 billion | 50% of disrupted volume |
| Market CAGR | 7% | SWIFT annual traffic growth; BIS CPMI data |

### 1.2 Per-Bank Assumptions

| Parameter | Conservative | Base | Upside | Source |
|-----------|-------------|------|--------|--------|
| Annual cross-border volume per Tier 1 bank | $3 trillion | $5 trillion | $8 trillion | Top 20 global banks process $2T-$10T/year in cross-border payments |
| Failure rate on eligible corridors | 3.5% | 4.0% | 4.5% | BIS/SWIFT GPI data |
| % of failures eligible for bridging | 40% | 50% | 60% | Excludes compliance holds (BLOCK), same-day resolution, sub-minimum principal |
| Average bridge principal | $800,000 | $1,000,000 | $1,500,000 | Weighted by class mix (A/B/C) |
| Average maturity (days) | 5 | 7 | 10 | Weighted by class mix |
| Average fee rate (bps, annualized) | 350 | 400 | 450 | C2 model output; most loans above 300 bps floor |

### 1.3 Deployment Phase Assumptions

| Phase | BPI Fee Share | Capital Source | Earliest Start |
|-------|-------------|----------------|----------------|
| Phase 1 (Licensor) | 15% | Bank funds 100% | Year 1 (pilot) |
| Phase 2 (Hybrid) | 40% | 30% bank / 70% BPI | Year 3–4 (requires BPI capital facility) |
| Phase 3 (Full MLO) | 75% | BPI funds 100% | Year 5–7 (requires lending license + treasury) |

---

## 2. Per-Bank Revenue Calculation

### 2.1 Formula

```
Eligible failures/year = bank_volume × failure_rate × eligible_pct / avg_principal
Fee per loan = avg_principal × (fee_bps / 10,000) × (avg_maturity / 365)
Total fee/year = eligible_failures × fee_per_loan
BPI revenue = total_fee × bpi_fee_share
```

### 2.2 Single Tier 1 Bank — Conservative Scenario (Phase 1)

| Step | Calculation | Result |
|------|-------------|--------|
| Eligible bridge volume | $3T × 3.5% × 40% | $42 billion/year |
| Number of loans | $42B / $800K | 52,500 loans/year |
| Fee per loan | $800K × (350/10,000) × (5/365) | $383.56 |
| Total fee revenue | 52,500 × $383.56 | **$20.1M/year** |
| BPI revenue (Phase 1, 15%) | $20.1M × 0.15 | **$3.02M/year** |
| BPI revenue (Phase 2, 40%) | $20.1M × 0.40 | **$8.05M/year** |
| BPI revenue (Phase 3, 75%) | $20.1M × 0.75 | **$15.1M/year** |

### 2.3 Single Tier 1 Bank — Base Scenario (Phase 1)

| Step | Calculation | Result |
|------|-------------|--------|
| Eligible bridge volume | $5T × 4.0% × 50% | $100 billion/year |
| Number of loans | $100B / $1M | 100,000 loans/year |
| Fee per loan | $1M × (400/10,000) × (7/365) | $767.12 |
| Total fee revenue | 100,000 × $767.12 | **$76.7M/year** |
| BPI revenue (Phase 1, 15%) | $76.7M × 0.15 | **$11.5M/year** |
| BPI revenue (Phase 2, 40%) | $76.7M × 0.40 | **$30.7M/year** |
| BPI revenue (Phase 3, 75%) | $76.7M × 0.75 | **$57.5M/year** |

### 2.4 Single Tier 1 Bank — Upside Scenario (Phase 1)

| Step | Calculation | Result |
|------|-------------|--------|
| Eligible bridge volume | $8T × 4.5% × 60% | $216 billion/year |
| Number of loans | $216B / $1.5M | 144,000 loans/year |
| Fee per loan | $1.5M × (450/10,000) × (10/365) | $1,849.32 |
| Total fee revenue | 144,000 × $1,849.32 | **$266.3M/year** |
| BPI revenue (Phase 1, 15%) | $266.3M × 0.15 | **$39.9M/year** |
| BPI revenue (Phase 2, 40%) | $266.3M × 0.40 | **$106.5M/year** |
| BPI revenue (Phase 3, 75%) | $266.3M × 0.75 | **$199.7M/year** |

---

## 3. Multi-Year Revenue Projection

### 3.1 Bank Onboarding Trajectory

| Year from PFD | Banks Live | Phase | Rationale |
|---------------|-----------|-------|-----------|
| Year 1–2 | 0 | Pre-revenue | Patent filing, pilot negotiation |
| Year 3 | 1 | Phase 1 | First pilot bank (likely Canadian Tier 1) |
| Year 4 | 2 | Phase 1 | Second bank; pilot proven |
| Year 5 | 3–4 | Phase 1→2 transition | Phase 2 begins with BPI co-funding |
| Year 6 | 5–7 | Phase 2 | Regional bank tier activating |
| Year 7 | 8–10 | Phase 2 | International expansion |
| Year 8–10 | 10–15 | Phase 2→3 transition | Phase 3 for earliest banks |

### 3.2 Conservative Scenario — BPI Annual Revenue

| Year | Banks | Phase | Per-Bank BPI Rev | Total BPI Revenue |
|------|-------|-------|-----------------|-------------------|
| 3 | 1 | Phase 1 | $3.0M | **$3.0M** |
| 4 | 2 | Phase 1 | $3.0M | **$6.0M** |
| 5 | 3 | Phase 1/2 mix | $4.7M avg | **$14.1M** |
| 6 | 5 | Phase 2 | $8.1M | **$40.3M** |
| 7 | 7 | Phase 2 | $8.1M | **$56.4M** |
| 8 | 10 | Phase 2/3 mix | $10.5M avg | **$105M** |
| 10 | 15 | Phase 3 | $15.1M | **$226M** |

### 3.3 Base Scenario — BPI Annual Revenue

| Year | Banks | Phase | Per-Bank BPI Rev | Total BPI Revenue |
|------|-------|-------|-----------------|-------------------|
| 3 | 1 | Phase 1 | $11.5M | **$11.5M** |
| 4 | 2 | Phase 1 | $11.5M | **$23.0M** |
| 5 | 3 | Phase 1/2 mix | $17.8M avg | **$53.4M** |
| 6 | 5 | Phase 2 | $30.7M | **$153M** |
| 7 | 8 | Phase 2 | $30.7M | **$245M** |
| 8 | 10 | Phase 2/3 mix | $40.0M avg | **$400M** |
| 10 | 15 | Phase 3 | $57.5M | **$863M** |

### 3.4 Upside Scenario — BPI Annual Revenue

| Year | Banks | Phase | Per-Bank BPI Rev | Total BPI Revenue |
|------|-------|-------|-----------------|-------------------|
| 3 | 1 | Phase 1 | $39.9M | **$39.9M** |
| 4 | 3 | Phase 1 | $39.9M | **$120M** |
| 5 | 5 | Phase 2 | $106.5M | **$533M** |
| 6 | 7 | Phase 2 | $106.5M | **$746M** |
| 7 | 10 | Phase 2/3 mix | $140M avg | **$1.4B** |
| 8 | 15 | Phase 3 | $199.7M | **$3.0B** |

---

## 4. Cumulative Revenue (Years 3–10)

| Scenario | Cumulative BPI Revenue | Phase 3 Steady-State (Year 10) |
|----------|----------------------|-------------------------------|
| **Conservative** | ~$450M | ~$226M/year |
| **Base** | ~$1.75B | ~$863M/year |
| **Upside** | ~$5.8B | ~$3.0B/year |

---

## 5. Comparison to Prior Projections

The Patent-Family-Architecture-v2.1.md projected $18B–$35B in cumulative royalties over the portfolio lifecycle. This bottom-up model shows:

| Metric | Prior Projection | Bottom-Up (Base) | Ratio |
|--------|-----------------|-------------------|-------|
| Year 4–8 annual revenue | $20M–$80M | $23M–$400M | Overlapping range (lower end matches; upper end exceeds due to Phase 2/3 transition) |
| Cumulative Years 3–10 | ~$2B (implied from table) | ~$1.75B | Comparable |
| Cumulative Years 3–32 | $18B–$35B (claimed) | Depends on Year 10+ growth | See note below |

**Note on long-horizon projections:** The prior $18B–$35B cumulative figure extrapolated to Year 32 using assumptions about market growth to $200T+ and 20% penetration. This bottom-up model does not project beyond Year 10 because assumptions about bank onboarding rates, market growth, and regulatory evolution beyond that horizon are speculative. For internal planning, use the Year 10 steady-state figure and apply market CAGR growth conservatively.

---

## 6. Key Sensitivities

The model is most sensitive to:

1. **Number of banks onboarded** — each Tier 1 bank is worth $3M–$40M/year to BPI depending on scenario and phase
2. **Average principal** — every $100K increase in average principal adds ~$38–$77 per loan in fee
3. **Deployment phase** — Phase 1→2 transition multiplies BPI revenue 2.7× per bank; Phase 2→3 adds another 1.9×
4. **Fee rate** — C2 model's risk-adjusted rate matters more than the floor; most loans price above 300 bps

The model is least sensitive to: maturity duration (most loans are 5–10 days regardless of class) and failure rate (range is narrow: 3–5%).

---

## 7. What This Model Does NOT Include

- **Licensing revenue from non-bank fintechs** — payment processors, treasury platforms (separate revenue stream)
- **Per-entity SaaS fees** — P4 pre-emptive facility, P8 AI treasury agent (recurring, not per-transaction)
- **Data product revenue** — P10 systemic risk monitoring feeds to regulators
- **Portfolio sale value** — IP portfolio valuation is separate from operational revenue

These additional revenue streams could materially increase total BPI revenue but are excluded from this model to maintain conservatism and transparency.

---

*All fee parameters sourced from `lip/common/constants.py`. Phase splits from `lip/common/deployment_phase.py`. Fee formula from `lip/c2_pd_model/fee.py`.*
