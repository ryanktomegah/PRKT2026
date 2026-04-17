# Appendix — Canonical Numbers

Single source of truth for every figure the founder may cite in an investor conversation. **Any number spoken in a pitch must come from this file.** If a number needs to change, change it here first and propagate outward (update narratives, drill answers, bear-case text that reference it; log in CHANGELOG).

## Product & Technical

| Figure | Value | Source | Notes |
|---|---|---|---|
| Latency SLO (p99) | 94ms | `lip/common/constants.py` — QUANT-locked | End-to-end pacs.002 → loan offer; canonical SLO |
| Latency p50 (median) | 45ms | `lip/common/constants.py` — QUANT-locked | Median inference; cite as "median under 50ms" |
| Fee floor | 300 bps | `lip/common/constants.py` — QUANT-locked | Platform minimum; all loans regardless of funding source |
| Maturity — CLASS_A | 3 days | `lip/common/constants.py` | Routing/account errors |
| Maturity — CLASS_B | 7 days | `lip/common/constants.py` | Systemic/processing delays only (NOT compliance holds — EPG-19) |
| Maturity — CLASS_C | 21 days | `lip/common/constants.py` | Liquidity/sanctions/investigation holds |
| Maturity — BLOCK | 0 days (no loan) | `lip/common/constants.py` | Compliance holds — never bridged (EPG-19) |
| C1 decision threshold (τ★) | 0.110 | `lip/common/constants.py` — QUANT-locked | F2-optimal; QUANT + ARIA sign-off to change |
| UETR TTL buffer | 45 days | `lip/common/constants.py` — QUANT-locked | Buffer beyond maturity for UETR deduplication |
| Salt rotation cycle | 365 days | `lip/common/constants.py` | Full cross-licensee salt rotation (CIPHER authority) |
| Salt rotation overlap | 30 days | `lip/common/constants.py` | Old salt accepted during transition window |
| Tests passing | 1,284 | `README.md` badge line 3 | Update on every material test-count change |
| Coverage | 92% | `README.md` badge line 4 | |
| ML baseline AUC | 0.739 | `lip/common/constants.py` | C1 pre-training baseline |
| ML target AUC | 0.850 | `lip/common/constants.py` | C1 target after production training |
| C1 corpus (training run) | 10M payments | `lip/common/constants.py` comment | F2-optimal threshold calibration run |
| Dispute FN rate (current, n=100) | 0.0% | `lip/common/constants.py` — DISPUTE_FN_CURRENT | LLM=qwen/qwen3-32b; ARIA must restate data-quality caveat |
| Dispute FN target | 2.0% | `lip/common/constants.py` | |
| Corridor embedding dim | 128 | `lip/common/constants.py` | |
| GraphSAGE output dim | 384 | `lip/common/constants.py` | |
| TabTransformer output dim | 88 | `lip/common/constants.py` | Combined input dim = 472 |
| GraphSAGE neighbors (train) | 10 | `lip/common/constants.py` | |
| GraphSAGE neighbors (infer) | 5 | `lip/common/constants.py` | |
| Asymmetric BCE alpha | 0.7 | `lip/common/constants.py` | False negatives more costly |
| F-beta (threshold calibration) | 2 | `lip/common/constants.py` | F2-optimal threshold |
| Decision log retention | 7 years | `lip/common/constants.py` | Regulatory audit requirement |
| HPA scale-out queue depth | 100 | `lip/common/constants.py` | Kubernetes HPA trigger |
| HPA scale-in queue depth | 20 | `lip/common/constants.py` | |
| Settlement P95 — Class A | 7.05h | `lip/common/constants.py` | BIS/SWIFT GPI calibration; 2M synthetic records |
| Settlement P95 — Class B | 53.58h | `lip/common/constants.py` | Systemic delays only — NOT compliance holds |
| Settlement P95 — Class C | 170.67h | `lip/common/constants.py` | |
| Min loan — Class A | $1,500,000 | `lip/common/constants.py` — QUANT-locked | Breakeven at 400bps/3d |
| Min loan — Class B | $700,000 | `lip/common/constants.py` — QUANT-locked | |
| Min loan — Class C | $500,000 | `lip/common/constants.py` — QUANT-locked | Legacy default |
| Min cash fee per cycle | $150 | `lip/common/constants.py` | Arithmetic guard (last resort) |
| Fee tier: small (<$500K) | 500 bps | `lip/common/constants.py` — QUANT-locked | Sub-minimum principal |
| Fee tier: mid ($500K–$2M) | 400 bps | `lip/common/constants.py` — QUANT-locked | |
| Fee tier: large (≥$2M) | 300 bps | `lip/common/constants.py` — QUANT-locked | Canonical FEE_FLOOR_BPS |
| Fee tier mid threshold | $2,000,000 | `lip/common/constants.py` | Boundary mid → canonical 300 bps |
| Conformal coverage level | 90% | `lip/common/constants.py` | Split conformal prediction; 1-in-10 may fall outside |
| Conformal uncertainty max multiplier | 2.0× | `lip/common/constants.py` — QUANT-locked | Caps upward fee adjustment from interval width |
| Conformal uncertainty scale factor | 0.5 | `lip/common/constants.py` — QUANT sign-off: 2026-03-26 | |
| Partial settlement minimum | 10% | `lip/common/constants.py` — QUANT sign-off: 2026-03-21 | Below this = noise |
| Amount validation tolerance | $0.01 | `lip/common/constants.py` — QUANT sign-off: 2026-03-21 | FX rounding tolerance |
| Stress regime multiplier | 3.0× | `lip/common/constants.py` — QUANT-locked | 1h failure rate vs 24h baseline; BIS CPMI threshold |
| Stress regime min transactions | 20 | `lip/common/constants.py` | Valid stress signal floor |
| Settlement safety margin | 1.5× | `lip/common/constants.py` — QUANT-locked | Dynamic maturity safety margin |
| Settlement min maturity | 12h | `lip/common/constants.py` | Minimum dynamic maturity |
| C3 watchdog fallback TTL | 14 days | `lip/common/constants.py` | 2× Class B maturity; QUANT + NOVA sign-off |
| CBDC maturity — SWIFT/SEPA | 1,080h (45 days) | `lip/common/constants.py` | Equals UETR_TTL_BUFFER_DAYS × 24 |
| CBDC maturity — FedNow/RTP | 24h | `lip/common/constants.py` | Same-day domestic |
| CBDC maturity — e-CNY/e-EUR/Sand Dollar | 4h | `lip/common/constants.py` | NOVA sign-off to change |
| Corridor buffer window | 90 days | `lip/common/constants.py` | Rolling window for corridor risk / embedding lookback |
| FX G10 currencies | 10 | `lip/common/constants.py` | USD EUR GBP JPY CAD CHF AUD NZD SEK NOK |
| Cancellation suspicion window | 300 seconds | `lip/common/constants.py` — CIPHER sign-off | camt.056 recall post-funding |
| Cancellation sender recall threshold | 3 per 24h | `lip/common/constants.py` — CIPHER sign-off | Behavioral alert |
| Beneficiary concentration alert | >80% | `lip/common/constants.py` | Single beneficiary velocity trigger |
| P10 k-anonymity threshold | 5 | `lip/common/constants.py` — QUANT + CIPHER | Min distinct banks per corridor/time-bucket |
| P10 differential privacy epsilon | 0.5 | `lip/common/constants.py` — QUANT + CIPHER | Per-query privacy loss (Laplace mechanism) |
| P10 privacy budget per cycle | 5.0 epsilon | `lip/common/constants.py` — QUANT + CIPHER | 30-day reset |
| P10 timestamp bucket | 1 hour | `lip/common/constants.py` | Rounding granularity |
| P10 telemetry min amount | $1,000 | `lip/common/constants.py` — QUANT sign-off | Sub-$1K excluded from telemetry |
| P10 contagion decay | 0.7 per hop | `lip/common/constants.py` — QUANT | |
| P10 contagion max hops | 5 | `lip/common/constants.py` — QUANT | BFS depth limit |
| P10 HHI concentration threshold | 0.25 | `lip/common/constants.py` — QUANT | "Highly concentrated" marker |
| Portfolio max HHI | 2,500 | `lip/common/constants.py` — QUANT | DOJ/FTC highly concentrated threshold |
| Portfolio max single-name exposure | 25% | `lip/common/constants.py` — QUANT | |
| Portfolio VaR confidence | 99% | `lip/common/constants.py` — QUANT | |
| Portfolio VaR horizon | 10 days | `lip/common/constants.py` — QUANT | |
| Revenue shortfall alert | <50% of annualized min | `lip/common/constants.py` | Trailing 90-day trigger |
| Revenue metering sync | 300 seconds | `lip/common/constants.py` | 5-minute sync to BPI telemetry |
| Container heartbeat | 60 seconds | `lip/common/constants.py` | P3 processor heartbeat |
| DGEN epoch start | 2023-07-01 UTC | `lip/common/constants.py` | SR 11-7 out-of-time validation window |
| DGEN epoch span | ~18 months | `lip/common/constants.py` | 18 × 30 × 86,400 seconds |
| Components | 8 (C1–C8) + 3 (C9, P5, P10) | `README.md` Architecture table | |
| Failure rate conservative | 3.0% | `lip/common/constants.py` | |
| Failure rate midpoint | 3.5% | `lip/common/constants.py` | Used in model calibration |
| Failure rate upside | 4.0% | `lip/common/constants.py` | |

## Economics

| Figure | Value | Source | Notes |
|---|---|---|---|
| Phase 1 BPI fee share | 30% | `lip/common/constants.py` — QUANT-locked | IP royalty; bank funds 100% of capital |
| Phase 2 BPI fee share | 55% | `lip/common/constants.py` — QUANT-locked | Lending revenue; 30% bank / 70% BPI capital |
| Phase 3 BPI fee share | 80% | `lip/common/constants.py` — QUANT-locked | Lending revenue; BPI funds 100% |
| Phase 2 bank capital return | 30% | `lip/common/constants.py` | Proportional to bank's 30% capital contribution |
| Phase 2 bank distribution premium | 15% | `lip/common/constants.py` | Origination, compliance, correspondent services |
| Phase 3 bank capital return | 0% | `lip/common/constants.py` | Bank contributes 0% capital |
| Phase 3 bank distribution premium | 20% | `lip/common/constants.py` | Origination / compliance value |
| Warehouse eligibility floor | 800 bps | `lip/common/constants.py` — QUANT-locked | SPV funding threshold; ensures 8% asset yield covers ~7% senior cost |
| Credit tier 1 | 300–539 bps | `lip/common/constants.py` | Investment-grade, listed |
| Credit tier 2 min | 540 bps | `lip/common/constants.py` | Private company, balance-sheet data |
| Credit tier 3 min | 900 bps | `lip/common/constants.py` | Thin file |
| Fee per 7-day cycle at floor | 0.0575% | `lip/common/constants.py` | 300 bps × 7/365 |
| SPV capital structure — senior tranche | 85% at ~7% | `docs/business/Revenue-Projection-Model.md` §8.3 | QUANT-controlled ratio |
| BPI first-loss tranche | 15% | `docs/business/Revenue-Projection-Model.md` §8.3 | Per loan: $105K on a $700K SPV position |
| Phase 2 capital — bank share | 30% | `lip/common/constants.py` | |
| Phase 2 capital — BPI/SPV share | 70% | `lip/common/constants.py` | |
| SPV senior debt cost (Phase 2) | ~7% | `docs/business/Unit-Economics-Exhibit.md` §6 | All-in; Phase 3 securitization drops to ~5% |
| Mezzanine cost (Phase 2) | ~12% | `docs/business/Investor-Briefing-v2.1.md` §4.2 | Honest Economics Disclosure |
| Blended cost of capital (Phase 2) | ~6.55% | `docs/business/Unit-Economics-Exhibit.md` §6 | Senior ~7% + mezz ~12% blend |
| Phase 2 breakeven average fee rate | ~1,000 bps | `docs/business/Revenue-Projection-Model.md` §8.4 | Below this BPI equity ROE is negative |
| Phase 3 breakeven average fee rate | ~700 bps | `docs/business/Revenue-Projection-Model.md` §8.5 | At 706 bps demonstrated, ROE ~9.1% |
| Asset yield at 800 bps | 8.0% | `docs/business/Unit-Economics-Exhibit.md` §2 | $80K/year per $1M deployed |
| Asset yield at 300 bps | 4.0% | `docs/business/Unit-Economics-Exhibit.md` §6 | Below debt service — capital negative |
| Capital cycles per year (7-day avg) | ~52× | `docs/business/Revenue-Projection-Model.md` §8.1 | 365/7; self-liquidating |
| Phase 2 warehouse facility — conservative entry | $15M–$35M | `docs/business/Revenue-Projection-Model.md` §8.2 | 1 bank, 2–5% of corridors |
| Processor take rate min | 15% | `lip/common/constants.py` — QUANT | P3 platform licensing |
| Processor take rate max | 30% | `lip/common/constants.py` — QUANT | |
| Processor take rate walkaway | >35% | `lip/common/constants.py` — QUANT | Economics unviable above this |
| Processor annual minimum floor | $500,000 | `lip/common/constants.py` — QUANT | P3 blueprint §3.2 |
| Processor annual minimum ceiling | $2,000,000 | `lip/common/constants.py` — QUANT | |
| Processor performance premium min | 10% | `lip/common/constants.py` — QUANT | |
| Processor performance premium max | 25% | `lip/common/constants.py` — QUANT | |
| Processor performance baseline | 80% of projected annual volume | `lip/common/constants.py` — QUANT | |
| Live demo loan: advance amount | $2,890,000 | `docs/business/Investor-Briefing-v2.1.md` §2 | Single live output example |
| Live demo loan: duration | 9 days | `docs/business/Investor-Briefing-v2.1.md` §2 | |
| Live demo loan: total fee | $5,033 | `docs/business/Investor-Briefing-v2.1.md` §2 | 0.17% of advance |
| Live demo loan: fee rate | 706 bps | `docs/business/Unit-Economics-Exhibit.md` §5.3 | C2 model output for this payment |
| Live demo loan: annualized yield | 7.06% | `docs/business/Investor-Briefing-v2.1.md` §4.2 | |
| Live demo loan: failure probability | 25.4% | `docs/business/Investor-Briefing-v2.1.md` §2 | C1 output for this payment |
| Conservative Year 3 BPI revenue (1 bank, Phase 1) | $6.0M | `docs/business/Revenue-Projection-Model.md` §3.2 | Single Tier 1 bank, conservative scenario |
| Base Year 3 BPI revenue (1 bank, Phase 1) | $23.0M | `docs/business/Revenue-Projection-Model.md` §3.3 | |
| Conservative Year 10 BPI revenue (15 banks) | ~$241M | `docs/business/Revenue-Projection-Model.md` §3.2 | |
| Base Year 10 BPI revenue (15 banks) | ~$921M | `docs/business/Revenue-Projection-Model.md` §3.3 | Founder Financial Model cites $863M (rounding) |
| Upside Year 10 BPI revenue | ~$3.2B | `docs/business/Revenue-Projection-Model.md` §3.4 | |
| Cumulative revenue Years 3–10 (conservative) | ~$581M | `docs/business/Revenue-Projection-Model.md` §4 | |
| Cumulative revenue Years 3–10 (base) | ~$2.2B | `docs/business/Revenue-Projection-Model.md` §4 | |
| Cumulative revenue Years 3–10 (upside) | ~$7.1B | `docs/business/Revenue-Projection-Model.md` §4 | |
| Long-horizon cumulative royalties (prior doc) | $18B–$35B | `docs/business/Investor-Briefing-v2.1.md` §4.1 | Years 4–32; superseded for planning by bottom-up model above |
| Phase 1→2 revenue multiplier per bank | 2.7× | `docs/business/Revenue-Projection-Model.md` §6 | |
| Phase 2→3 revenue multiplier per bank | 1.9× | `docs/business/Revenue-Projection-Model.md` §6 | |
| Per-bank Tier 1 annual volume — conservative | $3 trillion | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Per-bank Tier 1 annual volume — base | $5 trillion | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Per-bank Tier 1 annual volume — upside | $8 trillion | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average bridge principal — conservative | $800,000 | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average bridge principal — base | $1,000,000 | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average bridge principal — upside | $1,500,000 | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average fee rate — conservative | 350 bps | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average fee rate — base | 400 bps | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average fee rate — upside | 450 bps | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average maturity — conservative | 5 days | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average maturity — base | 7 days | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Average maturity — upside | 10 days | `docs/business/Revenue-Projection-Model.md` §1.2 | |
| Founder ownership at IPO (illustrative) | ~27% | `docs/business/Founder-Financial-Model.md` §2 | 10:1 Class A voting; loses majority at ~9.1% economic |
| ESOP reserved at inception | 15% | `docs/business/Founder-Financial-Model.md` §2 | |
| Class A voting ratio | 10:1 | `docs/business/Founder-Financial-Model.md` §2 | Founder loses voting majority at ~9.1% economic ownership |
| Pre-seed raise | $1.5M | `docs/business/Founder-Financial-Model.md` §5 | |
| Seed raise | $4M | `docs/business/Founder-Financial-Model.md` §5 | |
| Series A raise | $12M | `docs/business/Founder-Financial-Model.md` §5 | |
| Series B raise | $35M | `docs/business/Founder-Financial-Model.md` §5 | |
| Growth/pre-IPO raise | $60–80M | `docs/business/Founder-Financial-Model.md` §5 | |
| Founder after-tax exit (conservative scenario) | $158M–$264M | `docs/business/Founder-Financial-Model.md` §4 | At $226M BPI annual revenue |
| Founder after-tax exit (base scenario) | $606M–$1.0B | `docs/business/Founder-Financial-Model.md` §4 | At $863M BPI annual revenue |
| Canadian capital gains effective rate | ~13.4% | `docs/business/Founder-Financial-Model.md` §4 | 50% inclusion × 26.76% Ontario top rate |
| Patent total investment to secure portfolio | under $200,000 | `docs/business/Investor-Briefing-v2.1.md` §7.1 | Utility + PCT + prior art + 2 continuations |
| P2 (utility) filing cost | $20K–$35K | `docs/business/Investor-Briefing-v2.1.md` §7.1 | |
| PCT filing (5 jurisdictions, incl. national phase) | $50K–$80K | `docs/business/Investor-Briefing-v2.1.md` §7.1 | PFD + 30 months for national entries |
| Prior art search cost | $8K–$15K | `docs/business/Investor-Briefing-v2.1.md` §7.1 | |
| P3 continuation cost | $12K–$18K | `docs/business/Investor-Briefing-v2.1.md` §7.1 | |
| P4 continuation cost | $12K–$18K | `docs/business/Investor-Briefing-v2.1.md` §7.1 | |
| Taulia/SAP acquisition price | ~$1.1B | `docs/business/Competitive-Landscape-Analysis.md` §2.8 | 2022 |
| Bottomline Technologies take-private | ~$3.6B | `docs/business/Competitive-Landscape-Analysis.md` §2.4 | Thoma Bravo, 2022 |
| Bank onboarding cycle | 18–24 months | `docs/business/Founder-Financial-Model.md` §7.1 | Tier 1 bank, first conversation to production |
| Seed burn rate | $200K/month | `docs/business/Founder-Financial-Model.md` §5 | Fully loaded; covers 18 months on $4M |

## Market

| Figure | Value | Source | Notes |
|---|---|---|---|
| Global cross-border B2B payment volume (2024) | $31.6 trillion/year | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | FXC Intelligence 2024; codebase uses $31.7T (rounding) |
| Total cross-border payments TAM (2024) | $194.6 trillion | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | Includes interbank, wholesale, consumer |
| B2B CAGR (value, 2024–2032) | 5.9% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | FXC Intelligence; NOT 7% (7% = SWIFT message count) |
| Projected B2B volume (2050, at 5.9% CAGR) | ~$140 trillion | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | Internal extrapolation |
| Projected B2B volume (2050, at 7% CAGR) | ~$183 trillion | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | Higher estimate using message growth rate |
| Daily average B2B (2024) | ~$86.6 billion/day | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | $31.6T / 365 |
| Daily in-transit volume (used in pitch) | $88 billion | `docs/business/Investor-Briefing-v2.1.md` One-Sentence Summary | Rounded from $86.6B; from $31.7T/365 |
| Daily stuck / delayed / rejected (3–5% failure) | $2.6B–$4.4B | `docs/business/Investor-Briefing-v2.1.md` | At 3–5% of $31.7T daily |
| Annual disrupted volume (at 4%) | ~$1.27 trillion | `docs/business/Investor-Briefing-v2.1.md` §3; `Market-Fundamentals-Fact-Sheet.md` §2 | $31.7T × 4% |
| Addressable bridge volume | ~$630–635 billion | `docs/business/Market-Fundamentals-Fact-Sheet.md` §2 | 50% of disrupted volume; excl. compliance holds + sub-minimum |
| BPI canonical failure rate (midpoint) | 4.0% | `docs/business/Revenue-Projection-Model.md` §1.1 | Conservative projection midpoint |
| LexisNexis first-attempt failure rate | 14% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §2 | Broader definition; context only — not used in revenue models |
| LexisNexis cross-border STP rate | 26% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §2 | 74% require manual intervention |
| Global cost of failed payments | $118.5 billion/year | `docs/business/Market-Fundamentals-Fact-Sheet.md` §2 | Accuity/LexisNexis 2021 |
| Average fee per rejected/repaired payment | $12.10 | `docs/business/Market-Fundamentals-Fact-Sheet.md` §2 | LexisNexis 2023 |
| SWIFT FIN messages/day (2024 avg) | 53.3 million | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | SWIFT Annual Review 2024 |
| SWIFT FIN messages total (2024) | 13.4 billion | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | |
| SWIFT record daily peak | 55 million | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | June 1 and Nov 30, 2023 |
| SWIFT gpi adoption | 4,500+ institutions | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | ~80% of cross-border SWIFT traffic |
| SWIFT gpi: reach destination within 1h | 90% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | |
| SWIFT gpi: credited within 30 min | ~60% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | |
| SWIFT gpi: credited within 24h | 92% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | |
| FSB: B2B services settling within 1 hour | 5.9% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | FSB 2024 G20 KPI; vs 75% target |
| SWIFT member institutions | 11,000+ in 200+ countries | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | |
| SWIFT FIN message CAGR (2023–2024) | ~12% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | Message count (NOT value) |
| ISO 20022 migration status | Coexistence period through Nov 2025 | `docs/business/Market-Fundamentals-Fact-Sheet.md` §3 | SWIFT Standards Release 2024 |
| Correspondent banking avg transaction size | $500K–$5M+ | `docs/business/Market-Fundamentals-Fact-Sheet.md` §4 | BIS CPMI, McKinsey 2024 |
| Corporate trade finance avg transaction | $1M–$50M | `docs/business/Market-Fundamentals-Fact-Sheet.md` §4 | ICC Trade Register 2024 |
| Patent portfolio: total planned patents | 15 | `docs/business/Investor-Briefing-v2.1.md` §6; Patent-Family-Architecture-v2.1.md | 5 core + 10 continuations |
| Patent portfolio: independent claims | 5 | `docs/business/Investor-Briefing-v2.1.md` §6 | |
| Patent portfolio: dependent claims | 13 | `docs/business/Investor-Briefing-v2.1.md` §6 | D1–D13; D13 = adversarial camt.056 |
| Patent portfolio: coverage duration | ~32 years from foundational filing | `docs/business/Investor-Briefing-v2.1.md` §6 | Last continuation ~Year 12 + 20 |
| PCT jurisdictions | 5 | `docs/business/Investor-Briefing-v2.1.md` §7.1 | US, Canada, EU, Singapore, UAE |
| PFD + 12 months | Hard deadline — utility application | `docs/business/Investor-Briefing-v2.1.md` §5.1 | |
| PFD + 18 months | Hard deadline — PCT filing | `docs/business/Investor-Briefing-v2.1.md` §5.1 | |
| PFD + 36 months | P4 continuation deadline | `docs/business/Investor-Briefing-v2.1.md` §5.1 | Most time-sensitive continuation |

## Traction

| Figure | Value | Source | Notes |
|---|---|---|---|
| Bank LOIs signed | 0 | Current state as of 2026-04-17 | Update when RBC or any bank signs |
| Production pilots live | 0 | Current state as of 2026-04-17 | Update when first bank goes live |
| Active licensees | 0 | Current state as of 2026-04-17 | |
| Working demo | Live; produces real outputs | `docs/business/Investor-Briefing-v2.1.md` §7.2 | Demo priced $2.89M loan at $5,033 in real time |
| Patent status | Provisional not yet filed | Current state as of 2026-04-17 | All deadlines as offsets from PFD |

## Compliance

| Figure | Value | Source | Notes |
|---|---|---|---|
| AML dollar cap default | 0 (unlimited) | `lip/common/constants.py` EPG-16 | Per-licensee set via C8 token; 0 = unlimited guard in velocity.py |
| AML count cap default | 0 (unlimited) | `lip/common/constants.py` EPG-16 | |
| AMLD6 article | Art. 10 | `CLAUDE.md` EPG-19 | Criminal liability for legal persons |
| FATF recommendations relevant | R.13, R.21 | `CLAUDE.md` EPG-04/05 | Correspondent KYC cert; tipping-off prohibition |
| BLOCK rejection codes | DNOR, CNOR, RR01–RR04, AG01, LEGL | `CLAUDE.md` EPG-19 | 8 codes; never bridged; two-layer defense |
| EU AI Act article | Art. 14 | `CLAUDE.md` EPG-18 | Human oversight → C6 anomaly routing to PENDING_HUMAN_REVIEW |
| SR 11-7 equivalent (Canada) | OSFI E-23 | `docs/business/bank-pilot/rbc-pilot-strategy.md` | Effective May 2027 |
| License agreement warranties required | 3 | `CLAUDE.md` EPG-04/05 | Certification; system integrity; indemnification |

---

## Discrepancies flagged during Phase 1

| Item | Value in Source A | Source A | Value in Source B | Source B | Notes |
|---|---|---|---|---|---|
| BPI Phase 1 fee share | 15% | Historical docs referenced in `Capital-Partner-Strategy.md` (pre-constants refactor) | 30% | `lip/common/constants.py` — PLATFORM_ROYALTY_RATE | **30% is canonical.** QUANT authority. The 15% figure appears in older narrative docs written before the constants refactor; discard. |
| Base Year 10 BPI revenue | $863M | `docs/business/Founder-Financial-Model.md` §4 | ~$921M | `docs/business/Revenue-Projection-Model.md` §3.3 | $863M is rounded/conservative presentation in Founder Financial Model; $921M is the bottom-up model output. Use $921M for Revenue-Projection-Model citations; $863M when citing Founder Financial Model directly. |
| B2B payment volume | $31.7T | Codebase constants / `docs/business/Investor-Briefing-v2.1.md` | $31.6T | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | Fact Sheet governs for investor communications ($31.6T); codebase rounding ($31.7T) is in constants for backward compatibility. Both cite FXC Intelligence 2024. |
| B2B CAGR cited | 7% | `docs/business/Investor-Briefing-v2.1.md` table | 5.9% | `docs/business/Market-Fundamentals-Fact-Sheet.md` §1 | **5.9% is correct** for B2B value growth (FXC Intelligence). 7% = SWIFT message count growth, overestimates value growth. Use 5.9% in any new investor material. |
| Settlement P95 Class B label | "Compliance/AML holds" | Prior version of `lip/common/constants.py` (EPG-19 pre-fix) | "Systemic/processing delays" | `lip/common/constants.py` current | **Current label is correct.** Compliance holds are BLOCK class, never bridged. The 53.58h P95 value is NOT calibrated for compliance-hold resolution time. |

---

## Update protocol

When a figure changes:
1. Update the Value column here.
2. Grep the Playbook for the old value: `grep -r "OLD_VALUE" docs/business/fundraising/founder-fluency/`.
3. Update every narrative/drill/bear-case reference.
4. Log in `CHANGELOG.md` with category `[numbers]`.
