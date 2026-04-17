# Appendix — Canonical Names

Single source of truth for every person, firm, regulator, standard, or prior-art reference the founder may cite in an investor conversation. **Any name spoken in a pitch must come from this file.** Canonical spelling and pronunciation matter — misnaming a regulator or a competitor is a visible tell.

## People

| Name | Role | Relevance | Spelling / pronunciation note |
|---|---|---|---|
| Bruce Ross | Head, RBC AI Group (reports to CEO) | Potential pilot champion; newly formed AI group Feb 2026 with mandate to scale AI use cases | |
| Dave McKay | CEO, RBC | Group executive; AI Group and RBCx both report to CEO level | |
| Derek Neldner | CEO & Group Head, RBC Capital Markets | Transaction Banking sits under Capital Markets; HIGH relevance — institutional payments, clearing | |
| Sean Amato-Gauci | Group Head, RBC Commercial Banking | MEDIUM — commercial clients experience payment failures LIP bridges | |
| Sid Paquette | Head, RBCx (RBC venture arm) | HIGH — purpose-built to engage fintechs; invests in B2B payments | "RBCx" = lowercase x |
| Naim Kazmi | Group Head, RBC Technology & Operations | Infrastructure decisions, tech adoption | |
| Erica Nielsen | Group Head, RBC Personal Banking | LOW relevance — retail-focused, not payments | Founder's former division |

## Firms / banks

| Name | Relevance | Spelling note |
|---|---|---|
| RBC (Royal Bank of Canada) | Primary pilot target; founder's current employer (META-01 conflict) | Full form: "Royal Bank of Canada" |
| RBCx | RBC's venture/innovation arm; invests in B2B payments and fintech | Lowercase "x" — "RBCx" not "RBCX" |
| RBC Borealis AI | RBC's AI research institute; 850+ AI engineers, 100+ PhDs; ranked #1 Canada / #3 globally (2025 Evident AI Index) | "Borealis" |
| Bridgepoint Intelligence Inc. | BPI — the company; IP owner and platform operator | Abbreviation: BPI |
| JPMorgan Chase | Incumbent; closest prior-art patent holder (US7089207B1); Kinexys interbank settlement platform | "JPMorgan" one word, not "JP Morgan" |
| BNY Mellon | Correspondent-banking incumbent | "BNY Mellon" |
| SWIFT | Society for Worldwide Interbank Financial Telecommunication; 11,000+ members; LIP reads SWIFT ISO 20022 messages | All-caps: SWIFT |
| Finastra | Banking infrastructure provider (Misys + D+H merger); 8,000+ financial institutions; FusionFabric.cloud; potential P3 distribution partner | |
| Bottomline Technologies | ML-driven aggregate cash flow forecasting; closest §103 obviousness risk (US11532040B2); taken private by Thoma Bravo 2022 for ~$3.6B | |
| Wise (formerly TransferWise) | Consumer/SMB FX transfer; different segment ($200–$50K typical); no competitive overlap with LIP | "Wise" — not "TransferWise" in current references |
| Ripple / RippleNet | Alternative cross-border rails (XRP Ledger); ODL for FX settlement; ~$30B annualized volume vs $150T+ on SWIFT; different problem from LIP | |
| CLS Group | FX settlement risk via PvP; $6.6T daily FX market; complementary to LIP | "CLS" |
| Taulia / SAP | Supply chain finance (early payment on approved invoices); SAP acquired Taulia ~$1.1B 2022; P5 continuation overlap | |
| JPMorgan Kinexys (formerly Onyx) | Blockchain interbank settlement; rebranded Oct 2024; ~$2B/day; tokenized repo | "Kinexys" — not "Onyx" in current references |
| Thoma Bravo | PE; owns Bottomline Technologies | |
| Groq | Inference provider for C4 LLM backend (Qwen3-32B) | |
| FXC Intelligence | Source for $31.6T B2B cross-border volume, 5.9% CAGR | "FXC Intelligence" |

## Regulators and regimes

| Name | Jurisdiction | Relevance to LIP |
|---|---|---|
| AMLD6 | EU | Art. 10 criminal liability for legal persons; drives compliance-hold NEVER rule (EPG-19) |
| AMLD7 | EU (pending) | Bear-case regulatory risk |
| SR 11-7 | US (Federal Reserve) | Model governance — LIP's data cards and model cards structure |
| OSFI E-23 | Canada (OSFI) | Canada's SR 11-7 equivalent; effective May 2027; LIP pre-generates compliant validation reports — selling point |
| EU AI Act | EU | Art. 14 human oversight → EPG-18 C6 anomaly routing to PENDING_HUMAN_REVIEW |
| DORA | EU | Operational resilience; relevant to Phase 2/3 European bank onboarding |
| FATF | International | Recommendation 13 (correspondent KYC); Recommendation 21 (tipping-off prohibition) |
| OFAC / SDN | US | Sanctions regime; OFAC strict liability applies even in B2B structure if funds benefit sanctioned person (CIPHER warning EPG-14) |
| OSFI | Canada | Regulates Canadian banks as D-SIBs; Phase 2/3 lending license engagement required |
| FSB | International | G20 cross-border payment targets; FSB 2024: only 5.9% of B2B services settle within 1 hour vs 75% G20 target |
| BIS CPMI | International | Correspondent banking data; settlement timing calibration source |

## Standards and protocols

| Name | Relevance | Spelling note |
|---|---|---|
| ISO 20022 | Core messaging standard; LIP reads pacs.002 rejections; migration coexistence through Nov 2025 | "ISO 20022" with space — not "ISO20022" |
| pacs.002 | The specific ISO 20022 rejection message LIP intercepts as trigger event | Lowercase, period: "pacs.002" |
| SWIFT GPI (Global Payments Innovation) | End-to-end payment tracking via UETR; calibration source for LIP synthetic corpus; BIS/SWIFT GPI Joint Analytics confirms settlement P95 values | "GPI" all-caps; "SWIFT gpi" in SWIFT's own branding is lowercase g — match context |
| UETR | Unique End-to-end Transaction Reference; the cryptographic anchor for every bridge loan and auto-repayment | "UETR" all-caps |
| BIC | Bank Identifier Code; governing-law derivation (EPG-14) — LIP uses BIC chars 4–5, NOT payment currency | "BIC" all-caps |
| camt.056 | ISO 20022 payment recall message; D13 patent claim covers adversarial cancellation detection | Lowercase, period: "camt.056" |
| SOFR | Secured Overnight Financing Rate; SPV senior tranche pricing reference | |
| FedNow | US Federal Reserve instant payment rail; CBDC maturity 24h in constants | |
| RTP (Real-Time Payments) | The Clearing House instant payment network; CBDC maturity 24h in constants | |
| SEPA | Single Euro Payments Area; CBDC maturity 1,080h (same as SWIFT) in constants | "SEPA" all-caps |
| CIPS | Cross-Border Interbank Payment System (China); P9 cross-network interoperability continuation | |

## Prior art and patents

| Reference | Owner | Relevance |
|---|---|---|
| US7089207B1 | JPMorgan Chase | Closest prior art — static bridge loans with fixed duration/rate. LIP's novelty: dynamic ML-priced terms, rejection-code-based maturity assignment, extension to Tier 2/3 private counterparties via Damodaran industry-beta and Altman Z' thin-file models |
| US11532040B2 | Bottomline Technologies | ML-based aggregate cash flow prediction and automated liquidity management. Primary §103 obviousness risk for LIP Claims 1 and 3. Distinction: aggregate portfolio level (Bottomline) vs. individual UETR-keyed payment level (LIP) |
| LIP P1 | BPI | Provisional application — establishes priority date; no enforceable claims until P2 issued |
| LIP P2 | BPI | Full utility application (file by PFD + 12 months hard deadline); 5 independent claims + D1–D13 dependent claims; source of all royalty income |
| LIP P3 | BPI | Multi-party architecture + adversarial camt.056 cancellation; ~Year 2–3 continuation |
| LIP P4 | BPI | Pre-emptive liquidity portfolio management; most time-sensitive (~Year 3); must file before competitor publishes |
| LIP P5 | BPI | Supply chain cascade detection; ~Year 4 continuation |
| LIP P6 | BPI | CBDC settlement failure detection; ~Year 5–6 continuation |
| LIP P7 | BPI | Tokenised receivable liquidity pool; ~Year 6 continuation |
| LIP P8 | BPI | AI-powered autonomous treasury management agent; ~Year 7 continuation |
| LIP P9 | BPI | Cross-network interoperability bridging (SWIFT↔CBDC, CIPS↔FedNow); ~Year 7 continuation |
| LIP P10 | BPI | Systemic risk monitoring and regulatory reporting layer; ~Year 8 continuation |
| LIP P11–P15 | BPI | B2B2X embedded payments; federated ML; carbon-aware routing; AI-native network intelligence; quantum-resistant cryptographic monitoring; ~Years 9–12 |

## Internal frameworks (LIP's own named concepts)

| Name | What it is | Why it matters in a pitch |
|---|---|---|
| Two-step classification | The core novel patent claim: C1 classifies failure → C2 prices risk → conditional loan offer gated on classification output | Anchor phrase — repeat consistently; this is the invention |
| Conditional offer mechanism | The logic that gates loan offers on C1 classification output | Second anchor phrase |
| Class A / B / C / BLOCK | Failure taxonomy tiers by rejection code | CLASS_B warning: systemic/processing delays ONLY — not compliance holds (EPG-19). BLOCK = 8 codes, never bridged. |
| MRFA (Master Receivables Financing Agreement) | The legal instrument between BPI and borrowing bank | B2B interbank structure; originating bank is borrower, not end-customer (EPG-14) |
| EPG decisions (EPG-04 through EPG-21) | EPIGNOSIS architecture review register | Demonstrates governance maturity in diligence; key decisions: EPG-04/05 (hold_bridgeable API), EPG-14 (BIC governing law), EPG-16 (AML caps), EPG-17 (license token), EPG-18 (EU AI Act), EPG-19 (compliance-hold NEVER), EPG-20/21 (patent counsel) |
| EPG-04 / EPG-05 | hold_bridgeable certification strategy — FATF-compliant alternative to asking for hold reason | Unlocks Class B revenue; required in pilot LOI before legal review |
| EPG-14 | B2B interbank structure; governing law from BIC chars 4–5 | Borrower is originating bank BIC, not end-customer |
| EPG-16 | AML caps: default 0 (unlimited); set per-licensee via C8 token | Replaces inoperable retail $1M cap at correspondent banking scale |
| EPG-17 | License token must contain explicit aml_dollar_cap_usd and aml_count_cap JSON fields | |
| EPG-18 | C6 anomaly flag → PENDING_HUMAN_REVIEW (EU AI Act Art. 14) | |
| EPG-19 | Compliance-hold bridging NEVER — DNOR, CNOR, RR01–RR04, AG01, LEGL permanently blocked | Three independent grounds: CIPHER (structuring/layering), REX (AMLD6 Art.10), NOVA (repayment mechanics broken) |
| EPG-20 / EPG-21 | Patent counsel briefing; language scrub — no "AML", "SAR", "OFAC", "SDN", "PEP" in any claim | Claim the gate, not the contents of the blocked list |
| Ford Principle | Team working model — agents push back on wrong direction before executing | Founder credibility: "my team has veto authority on financial and compliance math" |
| Phase 1 / Phase 2 / Phase 3 | Deployment phases: Licensor (bank funds 100%, BPI earns 30% royalty) → Hybrid (55% BPI) → Full MLO (80% BPI) | Revenue and capital structure changes materially across phases; income classification changes (royalty vs lending revenue) |
| QUANT | Financial math agent; final authority on all fee arithmetic and QUANT-locked constants | "Nothing merges that changes fee logic without QUANT sign-off" |
| ARIA | ML/AI agent; authority over C1, C2, C4 | QUANT escalation for fee-adjacent ML |
| NOVA | Payments agent; authority over C3, C5, C7, ISO 20022 | |
| CIPHER | Security agent; final authority on AML, cryptography, C8 licensing | AML typology patterns never committed to version control |
| REX | Regulatory compliance agent; final authority on compliance, SR 11-7 / EU AI Act / DORA | |
| DGEN | Data generation agent; synthetic corpora, calibration quality | Never calls data "good" without reading generator source |
| FORGE | DevOps agent; K8s, Kafka, CI/CD; never force-pushes to main | |
| Damodaran industry-beta | Aswath Damodaran's industry beta dataset; used in C2 for Tier 2 private company PD | Distinguishes LIP from JPMorgan US7089207B1 (listed companies only) |
| Altman Z' (thin-file) | Modified Z-score model for companies with limited balance-sheet data; C2 Tier 3 pricing | Patent novelty for Tier 3 private counterparties |
| Synthetic corpus (payments_synthetic.parquet) | 2M synthetic records; seed=42; BIS/SWIFT GPI calibration source for settlement P95 constants | DGEN-generated; QUANT sign-off required to change calibration |

---

## Update protocol

When a name is added (e.g. a new person becomes relevant, a new regulator enters the picture):
1. Add a row here.
2. Log in CHANGELOG with `[names]` category.
