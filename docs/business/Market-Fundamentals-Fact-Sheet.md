# MARKET FUNDAMENTALS FACT SHEET
## Sourced Data for All Market Claims in BPI Documentation
### VERSION 1.0 | Bridgepoint Intelligence Inc. | 2026-03-20

---

> **PURPOSE:** This document is the single source of truth for every market claim made in BPI investor communications, patent filings, and internal planning documents. Every number has an inline citation. If a number appears in another BPI document without matching this fact sheet, this fact sheet governs.

---

## 1. Global Cross-Border B2B Payment Volume

| Metric | Value | Source |
|--------|-------|--------|
| Annual cross-border B2B payment volume (2024) | **$31.6 trillion** | FXC Intelligence, 2024 (published 2025); codebase uses $31.7T (rounding) |
| Total cross-border payments TAM (2024) | **$194.6 trillion** | FXC Intelligence, 2024 (includes interbank, wholesale, consumer) |
| Daily average B2B (annualized) | ~$86.6 billion/day | $31.6T / 365 |
| B2B cross-border CAGR (value, 2024-2032) | **5.9%** | FXC Intelligence: $31.6T → $50T by 2032 |
| SWIFT FIN traffic CAGR (messages, 2023-2024) | ~12% | SWIFT Annual Review 2024: 11.9B → 13.4B messages |
| Projected B2B volume (2050, at 5.9% CAGR) | ~$140 trillion | $31.6T × 1.059^26 — internal extrapolation |
| Projected B2B volume (2050, at 7% CAGR) | ~$183 trillion | Higher estimate using SWIFT message growth rate (overestimates value growth) |

**Important distinctions:**
- The $31.6T figure covers B2B cross-border payments specifically (FXC Intelligence definition: commercial trade payments), not total cross-border flows ($194.6T) or total SWIFT messaging
- SWIFT processes **53.3 million FIN messages per day** (2024 average; SWIFT Annual Review 2024) across ALL message types — ~45% payments, ~50% securities, ~5% other
- Do NOT cite "11 million times a day" for B2B payment failures — SWIFT daily volume is 53.3M messages (11M was incorrect even as total traffic), and B2B failures are a small fraction
- **CAGR clarification:** FXC Intelligence projects 5.9% CAGR for B2B value growth. The 7% figure used in prior docs reflects SWIFT message count growth (2019-2024), which grows faster than B2B payment value. **Use 5.9% for value projections.**

---

## 2. Payment Failure and Delay Rates

| Metric | Value | Source |
|--------|-------|--------|
| **LexisNexis: % not completed on first attempt** | **14%** | LexisNexis Risk Solutions, "True Impact of Failed Payments" (Feb 2023) |
| LexisNexis: cross-border STP rate | 26% | Same report — 74% require manual intervention, repair, or investigation |
| Global cost of failed payments | **$118.5 billion/year** | Accuity/LexisNexis (2021 data) — fees, labor, and lost business |
| Average fee per rejected/repaired payment | $12.10 | LexisNexis 2023 |
| BPI conservative failure rate | 3.0% | Lower bound for our projections (narrower definition: outright rejection or material delay) |
| BPI midpoint failure rate | 3.5% | STP-derived estimate used in Academic Paper v2.1 |
| BPI upside failure rate | 4.0%–5.0% | Upper bound — includes emerging market corridors |
| **Canonical midpoint used in projections** | **4.0%** | Midpoint of 3–5% range; used in Patent-Family-Architecture-v2.1 Section 3 |

**Critical note on failure rate definitions:**
- LexisNexis's 14% figure counts ANY payment not completed on first attempt — including minor repairs, data corrections, and temporary holds that resolve within hours. This is much broader than LIP's target.
- BPI's 3–5% range uses a narrower definition: payments that generate a rejection reason code (AC01, AM04, RC01, etc.) or are materially delayed (>24h for Class A corridors). This is the subset that creates a bridgeable working capital gap.
- The 74% non-STP rate (LexisNexis) is even broader — it includes any payment requiring ANY form of manual touch. Most of these are operational fixes, not bridge loan opportunities.
- **For investor communications:** cite the 14%/LexisNexis figure as context for the scale of the problem, but use 3–5% as the addressable failure rate for revenue projections. This is conservative and defensible.

**Annual disrupted volume:** $31.6T × 4% = **~$1.26 trillion/year**

**Addressable bridge volume** (excluding compliance holds, same-day self-resolution, sub-minimum principals): estimated **50% of disrupted volume = ~$630 billion/year**

---

## 3. SWIFT Network Data

| Metric | Value | Source |
|--------|-------|--------|
| Total SWIFT FIN messages per day (2024 avg) | **53.3 million** | SWIFT Annual Review 2024 |
| Total SWIFT FIN messages (2024 annual) | **13.4 billion** | SWIFT Annual Review 2024 |
| Total SWIFT FIN messages (2023 annual) | 11.9 billion | SWIFT Annual Review 2023 |
| Record daily peak (2023) | 55 million (June 1 and Nov 30) | SWIFT Annual Review 2023 |
| Message split: payments (MT1xx + MT2xx) | ~45% of FIN traffic | SWIFT / Belgian National Bank Oversight 2024 |
| Message split: securities (MT5xx) | ~50% of FIN traffic | SWIFT / Belgian National Bank Oversight 2024 |
| SWIFT member institutions | 11,000+ in 200+ countries | swift.com |
| SWIFT gpi adoption | 4,500+ institutions | SWIFT gpi Tracker, 2024 |
| SWIFT gpi: reach destination bank within 1 hour | 90% | SWIFT 2024 |
| SWIFT gpi: credited to beneficiary within 30 min | ~60% | SWIFT 2024 |
| SWIFT gpi: credited within 24 hours | 92% | SWIFT 2024 |
| FSB G20: B2B services settling within 1 hour | **5.9%** | FSB 2024 Progress Report on Cross-Border Payment Targets |
| ISO 20022 migration status | In progress — coexistence period through Nov 2025 | SWIFT Standards Release 2024 |

**Note on SWIFT gpi:** SWIFT gpi improves payment tracking and speed but does NOT eliminate failures. Even with gpi, payments still fail due to account errors, compliance holds, insufficient funds, and processing issues. The FSB's 2024 data shows only **5.9% of B2B payment services** settle within one hour — well below the G20's 75% target. gpi provides better visibility into failures, which actually makes LIP more effective (better telemetry for the C1 classifier).

---

## 4. Average Transaction Sizes

| Segment | Average Size | Source |
|---------|-------------|--------|
| Correspondent banking (B2B) | $500K–$5M+ | BIS CPMI, McKinsey Global Payments 2024 |
| Corporate trade finance | $1M–$50M | ICC Trade Register 2024 |
| Consumer remittances | $200–$500 | World Bank Remittance Prices Worldwide, 2024 |
| **LIP minimum loan thresholds** | $500K–$1.5M by class | `lip/common/constants.py` (QUANT-controlled) |

**LIP targets the correspondent banking segment**, not consumer remittances. Average eligible bridge loan principal is estimated at $700K–$2M depending on rejection class.

---

## 5. Settlement Timing Data

| Rejection Class | P95 Settlement (hours) | Source |
|----------------|----------------------|--------|
| Class A (routing/account errors) | 7.05h | BIS/SWIFT GPI Joint Analytics; calibrated from 2M synthetic records |
| Class B (systemic/processing delays) | 53.58h | BIS/SWIFT GPI Joint Analytics |
| Class C (liquidity/sanctions/investigation) | 170.67h | BIS/SWIFT GPI Joint Analytics |
| BLOCK (compliance holds) | N/A — never bridged | EPG-19 (REX, CIPHER, NOVA unanimous) |

**Note:** These P95 values are the canonical Tier 0 corridor buffer references (Architecture Spec S11.4). QUANT sign-off required to change.

---

## 6. Competitive Context

No existing product offers real-time, ML-priced bridge loans triggered by individual payment failure events with automated settlement-confirmation repayment. Adjacent solutions include:

| Competitor/Product | What They Do | Gap vs LIP |
|-------------------|-------------|------------|
| SWIFT gpi | Improves payment tracking and speed | No credit/lending product; tracking only |
| Ripple/XRP | Alternative cross-border rails | Different infrastructure; no failure-bridging |
| JPMorgan Kinexys | Blockchain interbank settlement | No individual-payment bridge lending |
| Bottomline Technologies | ML-driven aggregate cash flow forecasting | Portfolio-level, not individual-payment-level |
| Trade finance (general) | Letters of credit, factoring | Slow (days–weeks), expensive, requires human intervention |
| Bank overdrafts | Emergency credit lines | Expensive (10–18% APR), slow to activate |

See `Competitive-Landscape-Analysis.md` for the full competitive analysis.

---

## 7. Latency Performance Claims

| Metric | Value | Source |
|--------|-------|--------|
| p50 (median) inference latency | **45ms** | `LATENCY_P50_TARGET_MS = 45` in `lip/common/constants.py` |
| p99 inference latency / SLO | **94ms** | `LATENCY_P99_TARGET_MS = 94` in `lip/common/constants.py` |

**Correct phrasing for investor communications:** "median latency under 50 milliseconds, with p99 under 100 milliseconds"

**Incorrect phrasing (corrected in v2.2):** "94ms at p50" — this was wrong; 94ms is the p99 SLO, not p50.

---

## 8. Claims — Validation Status (Updated 2026-03-20)

| Claim | Status | Resolution |
|-------|--------|------------|
| "7% annual CAGR" for cross-border payments | **CORRECTED** | 7% applies to SWIFT message count growth, not B2B value growth. FXC Intelligence projects **5.9% CAGR** for B2B cross-border value (2024-2032). Use 5.9% for value projections. |
| "$180T by 2050" market projection | **REVISED** | At 5.9% CAGR: ~$140T by 2050. At 7% (message growth): ~$183T. Flag both as internal extrapolations. |
| "3–5% failure rate" | **VALIDATED (conservative)** | LexisNexis data shows **14%** fail on first attempt, but this includes minor repairs. BPI's 3–5% narrower definition (material failures creating bridgeable gaps) is conservative and defensible. |
| "50% addressable" of failed volume | **NEEDS VALIDATION** | Internal estimate. Validate by analyzing rejection code distribution in synthetic data and actual SWIFT GPI failure code breakdowns. |
| "$118.5B cost of failed payments" | **NEW — VALIDATED** | Accuity/LexisNexis 2021. Can be cited in investor materials as context. |
| "53.3M SWIFT messages/day" | **NEW — VALIDATED** | SWIFT Annual Review 2024. Replaces any "11M" claims. |
| "5.9% of B2B services settle within 1 hour" | **NEW — VALIDATED** | FSB 2024 G20 Progress Report. Powerful data point: shows the settlement gap problem persists despite SWIFT gpi. |

---

## 9. Source Bibliography

| Source | Date | Key Data Points |
|--------|------|----------------|
| FXC Intelligence, Global Payments Report | 2024 (published 2025) | $31.6T B2B cross-border; $194.6T total; 5.9% CAGR |
| SWIFT Annual Review | 2024 | 53.3M FIN messages/day; 13.4B annual; fastest growth in 15 years |
| SWIFT Annual Review | 2023 | 47.6M FIN messages/day; 11.9B annual; +4.5% YoY |
| Belgian National Bank, SWIFT Oversight | 2024 | 45% payments / 50% securities traffic split |
| LexisNexis Risk Solutions, "True Impact of Failed Payments" | Feb 2023 | 14% first-attempt failure; 26% STP rate; $12.10 avg cost per failure |
| Accuity/LexisNexis | 2021 | $118.5B global cost of failed payments |
| FSB, G20 Cross-Border Payments KPI Report | 2024 | 5.9% of B2B services settle within 1 hour (vs 75% target) |
| McKinsey, Global Payments Report | 2024 | $179T total cross-border flows; 4% revenue growth |

---

*This fact sheet should be updated whenever new market data is published by SWIFT, BIS, FXC Intelligence, or McKinsey. All BPI investor communications must cite this document as the source for market claims.*
