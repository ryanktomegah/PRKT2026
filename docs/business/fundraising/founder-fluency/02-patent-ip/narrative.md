# Patent & IP — Narrative

**Canonical anchors (use verbatim across all tiers and every drill answer):**
1. **two-step classification + conditional offer mechanism** — The core novel claim: system classifies the ISO 20022 rejection code against a failure taxonomy first; only classifications that pass the bridgeability gate proceed to offer generation.
2. **Tier 2/3 private-counterparty extension** — The specific gap JPMorgan US7089207B1 cannot close: listed-company structural model does not work for private companies. LIP's tiered PD framework extends coverage via Damodaran industry-beta (Tier 2) and Altman Z' thin-file model (Tier 3).
3. **non-provisional filing milestone** — Hard deadline at PFD + 12 months; the moment the filing lands, all five independent claims become enforceable against the world.
4. **five-patent-family architecture** — Provisional covers five families; each continuation extends the priority date forward at no incremental filing cost.
5. **Alice-clean anchoring** — Both §101 decisions supporting our eligibility (*Enfish v. Microsoft*, *McRO v. Bandai Namco*) ground the claims in specific technical infrastructure improvements, not abstract financial results.

---

## Tier A — 30-second

The patent claims a two-step classification + conditional offer mechanism: receive an ISO 20022 pacs.002 rejection, classify the rejection code against a three-class failure taxonomy, and generate a bridge loan offer only if the classification clears the bridgeability gate.
JPMorgan holds the closest prior art — US7089207B1 — but that patent applies only to listed public companies; it cannot price credit for private counterparties without observable equity market data.
LIP closes that gap with a tiered probability-of-default framework that extends to private companies via Damodaran industry-beta and Altman Z' thin-file models, covering the Tier 2/3 counterparties that account for the majority of correspondent banking volume.

*The Technical volume covers the underlying mechanism; the Market volume quantifies what the Tier 2/3 extension unlocks.*

---

## Tier B — 2-minute

**Prior art.** JPMorgan Chase US7089207B1 (2006) derives probability of default from observable equity market data — listed companies only. Private companies, the majority of mid-market cross-border counterparties, cannot be evaluated: no observable equity price.

**The LIP gap-fill.** LIP's tiered probability-of-default framework selects by data availability: Merton/KMV for listed counterparties, Damodaran industry-beta for Tier 2 private companies, Altman Z' thin-file scoring for Tier 3. Integrating both into a real-time payment-failure-triggered lending pipeline conditioned on ISO 20022 rejection-code classification is novel as a combination — the Tier 2/3 private-counterparty extension. No prior art teaches or suggests it.

**The two-step claim structure.** Independent Claim 1 is the two-step classification + conditional offer mechanism: receive the pacs.002 rejection code; evaluate against the three-class taxonomy; route to the lending pipeline if the classification clears; short-circuit before any offer generation if the classification is hold-type. The conditional gating — not the bridge mechanics — is the claim. Dependent Claim 5 adds the B1/B2 sub-classification gate: procedural holds versus investigatory holds.

**Filing status.** The provisional is drafted and under counsel review. The non-provisional filing milestone — PFD + 12 months — converts provisional protection into enforceable claims. The five-patent-family architecture covers five families with a fifteen-patent portfolio planned through continuations. Alice-clean anchoring is built into the claim structure on *Enfish* and *McRO*.

*The Market volume covers the addressable volume the Tier 2/3 extension unlocks.*

---

## Tier C — 5-minute

**1. Why this patent matters — moat economics.**

A software patent on a financial infrastructure method blocks exact replication, forces commercially less efficient design-arounds, and creates a licensing revenue stream. For LIP, the patent is also a diligence gate: any Tier 1 bank considering a pilot must assess whether a competitor can replicate the method next quarter. A granted patent answers that question cleanly.

Total investment to secure the portfolio — utility filing, PCT across five jurisdictions, prior art search, and two continuations — comes in under two hundred thousand dollars ($200,000). For a method addressing a gap in thirty-one point six trillion dollars ($31.6T) in annual B2B payment volume, that is an asymmetric investment.

**2. Prior art survey.**

Two patents define the prior art landscape. JPMorgan Chase US7089207B1 (2006) derives probability of default from observable equity data for listed companies — the closest antecedent to LIP's pricing methodology. Bottomline Technologies US11532040B2 (2022) covers ML-based aggregate cash flow forecasting that triggers automated liquidity — the closest antecedent to LIP's automated offer generation. Neither covers the two-step classification + conditional offer mechanism operating on ISO 20022 rejection codes. Neither covers the Tier 2/3 private-counterparty extension. No single reference, and no combination, teaches all five elements of Independent Claim 1.

**3. The specific novelty — two-step classification on ISO 20022 pacs.002.**

The novel claim: receive a pacs.002 rejection code; classify it against a three-class taxonomy — permanent failures, systemic delays, hold-type; generate an offer only when the classification clears the bridgeability gate; short-circuit the entire pipeline before any ML inference, pricing computation, or offer generation when the classification is hold-type. Patent Family 1, Independent Claim 1 is the core. Claim 5 adds the B1/B2 sub-classification gate. Family 3 covers the dispute classifier. Family 5 covers the corridor stress regime detector and CBDC normalization layer.

**4. The Tier 2/3 extension via Damodaran and Altman.**

US7089207B1 requires observable equity market prices — remove those inputs and the method fails. LIP's tiered framework selects by available data: Merton/KMV for listed companies, Damodaran industry-beta for Tier 2 private companies, Altman Z' thin-file scoring for Tier 3. This tiered selection logic is a novel combination US7089207B1 neither teaches nor suggests. Covered in Dependent Claim D5.

**5. Language discipline and why.**

No enumeration of specific hold-type rejection codes appears in any independent claim — only in a dependent claim and specification, using open "comprising at least" language. An enumerated list is a circumvention roadmap. The claim covers the gate mechanism and the conditional routing, not the code list. The same discipline applies across all five patent families.

**6. Filing status.**

The provisional is drafted. The non-provisional filing milestone — PFD + 12 months — converts provisional priority into enforceable claims. PCT filing at PFD + 18 months covers United States, Canada, European Patent Office, Singapore, and UAE. Most time-sensitive continuation is LIP P4, targeting approximately Year 3.

**7. What could go wrong.**

Two risks are material. Alice §101: an examiner could reject claims as abstract financial ideas. LIP's §101 analysis is anchored on *Enfish v. Microsoft* and *McRO v. Bandai Namco* — affirmative eligibility decisions grounded in technical infrastructure improvements. Examiner narrowing: every narrowing amendment to Independent Claim 1 must be evaluated against continuation impact before acceptance. A third risk — META-01 RBC employment IP clause — is flagged here by reference.

*The bear-case volume covers the RBC clause, Alice §101 risk depth, and the continuation narrowing scenario in detail.*

---

## Tier D — Deep-dive

### 1. Problem the patent solves

A need exists for a computer-implemented method that classifies real-time ISO 20022 payment failure events against a structured failure taxonomy, conditionally gates a bridge lending pipeline based on that classification, extends probability-of-default estimation to counterparties lacking observable equity market data, and auto-collects repayment upon settlement confirmation.

When a cross-border payment fails, the rejection message contains a structured code that predicts — but no prior system interprets — the failure type and the credit risk. No prior system built a real-time classification gate on those codes. No prior system gated an automated lending offer on the classification output. No prior system extended credit pricing to private counterparties in that pipeline. Those three gaps define the problem the patent solves.

---

### 2. Prior art analysis

**JPMorgan Chase US7089207B1 — in detail.**

Granted 2006. Derives probability of default from observable market factors: equity share price, equity volatility, total debt. Credit spread is an output — a price discovery tool, not a look-up table.

Three distinctions separate LIP from US7089207B1. First, coverage: US7089207B1 requires observable equity market prices; private companies cannot be evaluated. LIP's Dependent Claim D5 extends PD estimation to private companies via Damodaran industry-beta and Altman Z' scoring. Second, trigger: US7089207B1 is a standalone pricing tool with no connection to payment network infrastructure — no pacs.002 monitoring, no real-time offer generation. LIP's Independent Claim 1 is triggered by a present-state ISO 20022 rejection event. Third, conditional gating: US7089207B1 has no failure taxonomy, no hold-type classification, no pipeline short-circuit. The two-step classification + conditional offer mechanism is entirely absent from the prior art.

**Bottomline Technologies US11532040B2 — in brief.**

Granted 2022. Covers ML-based aggregate cash flow forecasting that predicts a future liquidity shortfall and initiates automated borrowing. Trigger is a forward-looking forecast. LIP's trigger is a present-state pacs.002 rejection on a specific UETR-keyed payment — a smoke alarm versus a weather forecast. US11532040B2 does not receive ISO 20022 rejection codes and applies no failure taxonomy.

**The §103 combination attack — pre-emption.**

An examiner may argue combining US7089207B1 with US11532040B2 renders LIP's claims obvious. Pre-emption rests on three grounds. Bottomline's forecast trigger and JPMorgan's static pricing tool do not combine into a real-time payment-event-triggered system without the inventive step of conceiving ISO 20022 rejection telemetry as the trigger — that step is LIP's. Extending JPMorgan's method to private companies requires the Damodaran/Altman framework, which neither reference teaches. The auto-repayment loop — Claim 5, UETR-keyed settlement monitoring with auto-collection — has no antecedent in either reference.

---

### 3. The novel claim structure

**Family 1 — ISO 20022 Failure Taxonomy and Dual-Layer Bridge Lending Pipeline.**

Independent Claim 1: receive the pacs.002 rejection code; evaluate against the three-class taxonomy — permanent failure, systemic delay, hold-type; route to the lending pipeline for permanent failure and systemic delay; short-circuit before any inference engine, pricing engine, or disbursement service fires when the classification is hold-type. Dependent Claim 2 adds the machine-readable hold-type output and immutable decision log. Dependent Claim 3 adds defense-in-depth: primary gate upstream of all pipeline components plus a secondary downstream gate. Dependent Claim 5 adds the B1/B2 sub-classification gate.

**Family 2 — Multi-Rail Settlement Monitoring and Maturity Calculation.**

Normalizes rejection codes from SWIFT, FedNow, RTP, SEPA, and CBDC rails into a unified ISO 20022 schema; derives governing law from BIC characters four and five; applies jurisdiction-specific holiday calendars; executes settlement via idempotency-token-based partial settlement logic.

**Family 3 — C4 Dispute Classifier and Human Override Interface.**

Two-stage NLP prefilter that routes loan requests without invoking the LLM when the narrative is empty or contains hold-type indicator keywords; human override interface with configurable timeout, dual-approval mode, and pipeline re-entry context store.

**Family 4 — Federated Learning Across Bank Consortium.**

Differentially private gradient aggregation across a bank consortium — ε=1.0, δ=1e-5 per round, Rényi accounting — with layer partitioning that keeps institution-specific counterparty topology local and shares only final aggregation layers globally.

**Family 5 — CBDC Normalization and Corridor Stress Regime Detector.**

Real-time stress detector: baseline failure rate over a rolling twenty-four-hour window; current rate over a one-hour window; stress declared when the ratio exceeds three point zero times (3.0×) the baseline with a twenty-transaction minimum; stress event emitted to the streaming platform; pending loan decisions routed to mandatory human review.

---

### 4. Claim language strategy

Two requirements govern all five families.

No enumeration of hold-type rejection codes in any independent claim. Specific codes appear only in Family 1, Dependent Claim 4, using open "comprising at least" language. The hard-block code list is in the specification, not the claims. An enumerated list is a circumvention roadmap — a competitor uses a code not on the list and the gate does not fire. The independent claim covers the gate mechanism and conditional routing; a competitor who builds any taxonomy with a hold-type class resulting in pipeline short-circuit infringes regardless of which specific codes they use.

No regulatory language anywhere in the claims or specification. Claims describe what the system computes — failure taxonomy, classification gate, bridgeability flag, procedural hold, investigatory hold — not what the real-world event is. A claim that recites regulatory concepts is more vulnerable to an Alice challenge. A claim reciting only the technical mechanism is anchored to infrastructure improvement throughout. These two requirements compound: enumerating regulatory block codes is simultaneously a circumvention roadmap and a §101 vulnerability.

---

### 5. Enforcement posture

A competitor infringes Independent Claim 1 if their system receives an ISO 20022 payment failure event, classifies it against any three-category taxonomy with a hold-type class causing pipeline short-circuit, and conditions offer generation on that output. Specific codes, ML architecture, language, and deployment environment are irrelevant. Independent Claim 5 is infringed by any system that links a disbursed liquidity advance to a specific UETR and automatically initiates repayment on settlement confirmation.

Defensibility rests on three layers: the granted patent (twenty-year exclusivity per jurisdiction); the continuation family (each continuation inherits PFD while covering new embodiments); and the trade secret layer — Damodaran calibration tables, Altman Z' scoring weights, and the corridor-level correspondent bank database maintained under the Defend Trade Secrets Act. A competitor practicing the patented method must independently derive these parameters at significant cost.

---

### 6. Risks

**Alice / §101 — software patent eligibility.**

*Alice Corp. v. CLS Bank Int'l* (2014): claims directed to abstract ideas must contain an inventive concept transforming the idea into a patent-eligible application. LIP's §101 analysis is anchored on two affirmative Federal Circuit precedents.

*Enfish v. Microsoft* (Fed. Cir. 2016): claims eligible when they improve computer or network infrastructure itself. LIP's latency specification — median inference under fifty milliseconds (50 ms), p99 under ninety-four milliseconds (94 ms) — is a technical performance specification requiring specific distributed stream processing architectures. That is a technical infrastructure improvement.

*McRO v. Bandai Namco* (Fed. Cir. 2016): claims eligible when they impose specific technological rules on how a result is achieved. LIP's classification gate mechanism, UETR-keyed correlation, and BIC-derived governing-law logic are specific technological constraints, not functional end-state claims.

*Recentive Analytics v. Fox Corp.* (Fed. Cir. 2025) found claims ineligible where applying established ML techniques to a new data environment showed no demonstrable technical improvement. That adverse holding is not cited in LIP's §101 position — citing a case where claims failed creates an exploitable prosecution vulnerability. LIP's §101 position rests exclusively on *Enfish* and *McRO*.

**Examiner narrowing.**

Every narrowing amendment to Independent Claim 1 must be evaluated for its effect on continuation scope before acceptance — narrowed elements cannot be recaptured in continuations without losing the priority date. Claim 5 (auto-repayment loop) is the terminal fallback: any competitor using payment-network confirmation data to auto-collect repayment infringes Claim 5 regardless of how they have designed around Claims 1 through 4.

**RBC IP clause — META-01.**

The RBC offer letter contains a broad IP assignment clause covering "anything you conceive, create or produce … during your employment." Counsel review is required before filing. The bear-case volume covers META-01 in full — probability distribution of outcomes, defence arguments, and sequencing strategy. This flag is noted here per META-01; the narrative does not go deeper.

---

### 7. Filing roadmap

**Step 1 — Provisional (P1).** Drafted. Under counsel review. PFD establishes the priority date for all subsequent filings. No enforceable claims attach — it creates the priority date only.

**Step 2 — Non-provisional utility (P2).** Hard deadline: PFD + 12 months. The non-provisional filing milestone converts the provisional into five independent claims and thirteen dependent claims (D1–D13). All five independent claims preserved as filed; any examiner narrowing evaluated against continuation impact before acceptance.

**Step 3 — PCT filing.** Hard deadline: PFD + 18 months. Five jurisdictions: United States Patent and Trademark Office, Canadian Intellectual Property Office, European Patent Office, Intellectual Property Office of Singapore, and UAE. National phase entries at approximately thirty months from PFD.

**Step 4 — Continuation family (P3–P15).** Each continuation under 35 U.S.C. § 120 inherits the PFD priority date. Most time-sensitive: LIP P4 (pre-emptive liquidity portfolio management), target approximately Year 3 from PFD.

**Total investment.** Under two hundred thousand dollars ($200,000) for utility application, PCT across five jurisdictions, prior art search, and two initial continuations.

**Coverage duration.** Last continuation planned at approximately Year 12 from PFD; terminal continuation extends portfolio protection approximately thirty-two years from the foundational filing.

*The bear-case volume covers the META-01 RBC clause risk, the Alice §101 depth scenario, and the examiner-narrowing bear case in full.*
