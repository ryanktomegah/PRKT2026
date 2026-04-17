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

**The patent landscape today.** Software patents in financial infrastructure face two hurdles: prior art and Alice (the 2014 Supreme Court decision that raised the bar for software patents). Most fintech IP is fragile on one or both. LIP's patent strategy addresses both from the start.

**What JPMorgan covers — and what it misses.** JPMorgan Chase holds US7089207B1, granted in 2006. That patent covers deriving a probability of default from observable equity market data — share price and equity volatility — without assuming a credit spread. It is a genuine prior-art contribution. But it is limited to listed public companies. Private companies, which represent the majority of mid-market cross-border counterparties, cannot be evaluated under US7089207B1 because they have no observable equity price.

**The LIP insight that fills the gap.** Correspondent banking operates overwhelmingly with private counterparties — Tier 2 companies with balance-sheet data, Tier 3 companies with thin financial files. LIP's tiered probability-of-default framework selects the right model by data availability: Merton/KMV for listed counterparties, Damodaran industry-beta proxies for Tier 2 private companies, Altman Z' thin-file scoring for Tier 3. Neither Damodaran nor Altman are novel inputs individually — but integrating them into a real-time payment-failure-triggered lending pipeline, conditioned on ISO 20022 rejection-code classification, is novel as a combination. No prior art teaches or suggests it.

**The two-step claim structure.** Independent Claim 1 in the provisional covers: receive the pacs.002 rejection code; evaluate it against the three-class taxonomy (permanent failure, systemic delay, hold-type classification); route to the bridge lending pipeline if the classification clears; short-circuit the pipeline before any offer generation if the classification falls into the hold-type class. The conditional gating — not the bridge mechanics — is the claim. Dependent Claim 5 in Patent Family 1 adds the B1/B2 sub-classification gate: a second discrimination layer that distinguishes procedural holds (bridgeable upon certification) from investigatory holds (permanently blocked).

**Filing status and near-term milestone.** The provisional application is drafted and under counsel review. The non-provisional filing milestone — PFD + 12 months — is the hard deadline that converts provisional protection into enforceable claims. Five patent families are structured across the provisional, with a fifteen-patent portfolio planned through continuations.

*The Market volume covers the addressable volume the Tier 2/3 extension unlocks.*

---

## Tier C — 5-minute

**1. Why this patent matters — moat economics.**

A software patent on a financial infrastructure method does three things: it blocks exact replication, it forces design-arounds that are commercially less efficient, and it creates a licensing revenue stream independent of the platform's deployment scale. For LIP, the patent is also a diligence gate. Any Tier 1 bank considering a pilot must assess whether BPI owns the method or whether a competitor can replicate it the following quarter. A granted patent answers that question cleanly. An unpatented method does not.

The planned patent total investment to secure the portfolio — utility filing, PCT across five jurisdictions, prior art search, and two continuations — comes in under two hundred thousand dollars ($200,000). For a method that addresses a gap in thirty-one point six trillion dollars ($31.6T) in annual B2B payment volume, that is an asymmetric investment.

**2. Prior art survey.**

Two patents define the prior art landscape. JPMorgan Chase US7089207B1 (2006) derives probability of default from observable equity data for listed companies — the closest antecedent to LIP's pricing methodology. Bottomline Technologies US11532040B2 (2022) covers ML-based aggregate cash flow forecasting that triggers automated liquidity — the closest antecedent to LIP's automated offer generation. Neither covers the two-step classification + conditional offer mechanism operating on ISO 20022 rejection codes. Neither covers the Tier 2/3 private-counterparty extension. No single reference, and no combination of these references, teaches all five elements of LIP's Independent Claim 1.

**3. The specific novelty — two-step classification on ISO 20022 pacs.002.**

The novel claim is not "bridge a failed payment." It is: receive a pacs.002 rejection code; classify it against a three-class taxonomy that distinguishes permanent failures, systemic delays, and hold-type classifications; generate an offer only when the classification clears the bridgeability gate; and short-circuit the entire pipeline — before any machine learning inference, any pricing computation, and any offer generation — when the classification is hold-type. Both the classification step and the conditional gating step are independently claimable. Patent Family 1, Independent Claim 1 is the core. Family 1, Claim 5 adds the B1/B2 sub-classification gate. Family 3 covers the C4 dispute classifier and human override interface. Family 5 covers the corridor stress regime detector and CBDC normalization layer.

**4. The Tier 2/3 extension via Damodaran and Altman.**

US7089207B1 requires current equity share price and equity price volatility as mandatory inputs. Remove those inputs and the method fails. LIP's tiered framework selects the estimation method by available data: structural Merton/KMV for listed companies, sector-median asset volatility from Damodaran industry-beta data for Tier 2 private companies, modified Altman Z' financial ratio scoring for Tier 3 thin-file counterparties. This tiered selection logic — which enables probability-of-default estimation across the full counterparty data spectrum — is a novel combination that US7089207B1 neither teaches nor suggests. It is covered in LIP Dependent Claim D5, depending on Independent Claim 1.

**5. Language discipline and why.**

The claims use a language discipline throughout: no enumeration of the specific rejection codes that trigger a hard-block outcome appears in any independent claim. The enumeration appears only in a dependent claim and in the specification, using open "comprising at least" language. This is not stylistic — it is strategic. An enumerated public list of blocked codes is a roadmap for circumvention: a bad actor reads the claim, uses a code not on the list, and the gate does not fire. The claim instead describes the existence of the gate, its criterion (classification result equals hold-type), and the conditional routing — not the specific contents of the blocked-code set. The same discipline applies to all claim language throughout the five families.

**6. Filing status.**

The provisional is drafted. The non-provisional filing milestone — the hard deadline at PFD + 12 months — is the gate that converts the provisional priority date into enforceable claims. The PCT filing deadline falls at PFD + 18 months, covering United States, Canada, European Patent Office, Singapore, and UAE. The most time-sensitive continuation is LIP P4 (pre-emptive liquidity portfolio management), which must file before a competitor publishes in that space — target at approximately Year 3.

**7. What could go wrong.**

Two risks are material. First, Alice (the 2014 Supreme Court decision that raised the bar for software patents): an examiner could reject the claims as directed to an abstract financial idea without sufficient technical implementation. LIP's §101 analysis is anchored on *Enfish, LLC v. Microsoft Corp.* (Fed. Cir. 2016) and *McRO, Inc. v. Bandai Namco Games Am. Inc.* (Fed. Cir. 2016) — both affirmative eligibility decisions grounded in technical infrastructure improvements: payment-network processing latency, protocol interoperability across heterogeneous rails, and UETR-keyed settlement correlation. Second, examiner narrowing: an examiner may require the independent claims to be narrowed to closer embodiments, reducing continuation scope. The prosecution strategy anticipates this — every narrowing amendment to Independent Claim 1 must be evaluated against its effect on the continuation family before acceptance.

There is a third risk that the bear-case volume covers in full: the META-01 RBC employment IP assignment clause. That risk is flagged here by reference.

*The bear-case volume covers the RBC clause, Alice §101 risk depth, and the continuation narrowing scenario in detail.*

---

## Tier D — Deep-dive

### 1. Problem the patent solves

In patent-office language: a need exists for a computer-implemented method that classifies real-time ISO 20022 payment failure events against a structured failure taxonomy, conditionally gates a bridge lending pipeline based on that classification, extends probability-of-default estimation to counterparties lacking observable equity market data, and auto-collects repayment upon settlement confirmation of the original payment.

In plain terms: when a cross-border payment fails, the rejection message contains a structured code that predicts — but no system interprets — the failure type and the credit risk. No prior system built a real-time classification gate on those codes. No prior system gated an automated lending offer on the output of that gate. No prior system extended credit pricing to private counterparties in that pipeline. Those three gaps define the problem the patent solves.

---

### 2. Prior art analysis

**JPMorgan Chase US7089207B1 — in detail.**

Granted 2006. The patent derives a company's probability of default using observable market factors: current equity share price, equity price volatility, and total debt levels. These inputs feed a structural credit risk model. Credit spread is an output, not an assumed input — making the system a price discovery tool for credit risk rather than a look-up table.

Three distinctions separate LIP's claims from US7089207B1. First, coverage: US7089207B1 explicitly requires observable equity market prices. Private companies cannot be evaluated. LIP's Dependent Claim D5 covers a tiered framework that extends PD estimation to private companies via balance-sheet data, sector-median asset volatility proxies from Damodaran industry-beta data, and Altman Z' financial ratio scoring. Second, trigger: US7089207B1 is a standalone pricing tool with no connection to payment network infrastructure. It does not monitor payment transactions, does not receive pacs.002 messages, and does not generate automated lending offers in response to payment events. LIP's Independent Claim 1 is triggered by a real-time ISO 20022 rejection event — a present-state observation, not a forecast. Third, the conditional gating: US7089207B1 has no classification gate and no conditional offer mechanism. There is no taxonomy of failure types. There is no short-circuit path for hold-type classifications. The two-step mechanism is entirely absent from the prior art.

**Bottomline Technologies US11532040B2 — in brief.**

Granted 2022. The patent covers ML-based aggregate cash flow forecasting that predicts a future period when an entity's cash position will fall below a threshold, then automatically initiates borrowing to cover the predicted shortfall. The trigger is a forward-looking statistical forecast. LIP's trigger is a present-state observed pacs.002 rejection event on a specific identified payment carrying a unique UETR. The distinction is architectural: a weather forecast versus a smoke alarm. US11532040B2 does not monitor live payment network telemetry, does not receive ISO 20022 rejection codes, and does not apply any failure taxonomy.

**The §103 combination attack — pre-emption.**

An examiner may argue that combining US7089207B1 with US11532040B2 makes LIP's claims obvious. The pre-emption rests on three grounds. First, the triggering mechanisms are incompatible: Bottomline's forecast trigger and JPMorgan's static pricing tool do not combine into a real-time payment-event-triggered system without the inventive step of conceiving that ISO 20022 rejection telemetry could serve as the trigger — and that step is LIP's. Second, extending JPMorgan's method to private companies requires the tiered Damodaran/Altman framework, which neither reference teaches. Third, the auto-repayment loop — Independent Claim 5, which monitors UETR settlement and auto-collects repayment on confirmation — has no antecedent in either reference.

---

### 3. The novel claim structure

**Family 1 — ISO 20022 Failure Taxonomy and Dual-Layer Bridge Lending Pipeline.**

Independent Claim 1 is the core method claim. The key steps: receive the ISO 20022 pacs.002 rejection code; evaluate it against a three-class taxonomy — permanent failure class, systemic delay class, and hold-type classification class; route to the bridge lending pipeline for permanent failure and systemic delay classifications; short-circuit the pipeline before any inference engine, pricing engine, or disbursement service fires when the classification is hold-type, regardless of pipeline position.

Dependent Claim 2 adds the machine-readable hold-type classification output — logically distinct from both a loan-declined status and a payment-processing-error status — and the immutable decision log. Dependent Claim 3 adds the defense-in-depth architecture: primary gating upstream of all pipeline components, plus a secondary gate that independently verifies the rejection code against the hold-type code set downstream. Dependent Claim 5 adds the B1/B2 sub-classification gate.

**Family 2 — Multi-Rail Settlement Monitoring and Maturity Calculation.**

Covers the system that normalizes rejection codes from SWIFT, FedNow, RTP, SEPA, and CBDC rails into a unified ISO 20022 schema, derives governing law from BIC characters four and five, applies jurisdiction-specific holiday calendars for maturity calculation, and executes settlement via idempotency-token-based partial settlement logic.

**Family 3 — C4 Dispute Classifier and Human Override Interface.**

Covers the two-stage natural language prefilter that routes loan requests without invoking the LLM when the narrative is empty or contains hold-type indicator keywords, and the human override interface with configurable timeout, dual-approval mode, and pipeline re-entry context store.

**Family 4 — Federated Learning Across Bank Consortium.**

Covers differentially private gradient aggregation across a consortium of bank computing nodes — ε=1.0, δ=1e-5 per round, Rényi accounting via Poisson composition — with layer partitioning that keeps institution-specific counterparty topology local and shares only final aggregation layers globally.

**Family 5 — CBDC Normalization and Corridor Stress Regime Detector.**

Independent Claim 2 covers the real-time stress regime detector: baseline failure rate over a rolling twenty-four-hour window; current failure rate over a rolling one-hour window; stress declared when the ratio exceeds three point zero times (3.0×) the baseline, with a twenty-transaction minimum in each window; stress event emitted to the distributed streaming platform; pending loan decisions routed to mandatory human review, functioning as a regulatory circuit breaker.

---

### 4. Claim language strategy

The claim language discipline in force throughout all five families rests on two requirements.

First, no enumeration of hold-type rejection codes in any independent claim. The specific ISO 20022 rejection codes that trigger a hard-block outcome are never listed in an independent claim. They appear only in Family 1, Dependent Claim 4, using open "comprising at least" language, covering only the hold-type class. The hard-block code list is in the specification description, not in the claims. This is strategic, not stylistic: an enumerated public list of codes is a circumvention roadmap. The claim instead covers the classification gate mechanism, the criterion — hold-type classification output — and the conditional routing. A competitor who uses a rejection code not on the published list still infringes the independent claim because the independent claim covers the gate, not the code list.

Second, no regulatory language anywhere in the claims or specification. The claims describe what the system computes — failure taxonomy, classification gate, bridgeability flag, procedural hold, investigatory hold — not what the real-world regulatory event is. This matters for §101: a claim that explicitly recites regulatory concepts is more vulnerable to an Alice challenge as a claim directed to an abstract regulatory compliance idea rather than a technical infrastructure method. A claim that recites only the technical mechanism — the classification gate, the conditional routing, the short-circuit architecture — is anchored to technical infrastructure improvement throughout.

These two requirements also compound: a claim that enumerates regulatory block codes is simultaneously a circumvention roadmap and a §101 vulnerability. Avoiding both with a single drafting discipline is the correct approach.

---

### 5. Enforcement posture

**What infringement looks like.**

A competitor infringes Independent Claim 1 if their system receives an ISO 20022 payment failure event, classifies it against any three-category taxonomy that includes a category resulting in pipeline short-circuit before offer generation, and conditions offer generation on that classification output. The specific rejection codes used, the specific ML architecture chosen, the specific programming language, and the deployment environment do not matter for independent claim infringement. Independent Claim 5 — the auto-repayment loop — is infringed by any system that establishes a monitoring relationship between a disbursed liquidity advance and a specific cross-border payment identified by a unique network-assigned reference, and automatically initiates repayment collection upon settlement confirmation of that payment.

**What defensibility looks like.**

Defensibility rests on three layers. The granted patent: once the non-provisional issues, the method is exclusive in all designated jurisdictions for twenty years from the filing date. The continuation family: each continuation filed within statutory periods inherits the priority date while covering new embodiments; a competitor who designs around one family still faces the others. The trade secret layer: the specific feature engineering pipeline, the Damodaran industry-beta calibration tables, the Altman Z' thin-file scoring weights, and the corridor-level correspondent bank performance database are maintained as trade secrets under the Defend Trade Secrets Act. A competitor practicing the patented method still must independently derive these parameters at significant cost.

---

### 6. Risks

**Alice / §101 — software patent eligibility.**

Alice Corp. v. CLS Bank Int'l (2014) established that claims directed to abstract ideas must contain an inventive concept that transforms the abstract idea into a patent-eligible application. A financial-method claim that merely recites "lend money when a payment fails" fails Alice. LIP's §101 analysis is anchored on two affirmative Federal Circuit precedents.

*Enfish, LLC v. Microsoft Corp.* (Fed. Cir. 2016) held claims patent-eligible when they improve the functioning of computer or network infrastructure itself — not merely use computers as tools for an abstract purpose. LIP's latency claim (median inference under fifty milliseconds (50 ms), p99 under ninety-four milliseconds (94 ms)) is a technical performance specification for the real-time payment network monitoring pipeline. Achieving that latency requires specific distributed stream processing architectures. That is a technical infrastructure improvement, not an abstract financial result.

*McRO, Inc. v. Bandai Namco Games Am. Inc.* (Fed. Cir. 2016) held claims patent-eligible when they impose specific, meaningful technological rules and constraints on how a result is achieved — not merely claim the result in functional terms. LIP's classification gate mechanism, the UETR-keyed correlation across all pipeline stages, and the BIC-derived governing-law logic are specific technological rules for achieving a result, not abstract functional claims.

One case must be distinguished from the §101 strategy. *Recentive Analytics, LLC v. Fox Corp.* (Fed. Cir. 2025) found claims patent-ineligible on the ground that applying established ML techniques to a new data environment does not constitute a patent-eligible inventive concept without a demonstrable improvement to the technical operation of the system itself. That adverse holding is not cited in LIP's §101 analysis — citing a case where the claims failed would create an exploitable prosecution vulnerability. LIP's §101 position rests exclusively on *Enfish* and *McRO*.

**Examiner narrowing.**

An examiner may require the independent claims to be narrowed to closer embodiments during prosecution. Every narrowing amendment must be evaluated for its effect on continuation claim scope before acceptance — elements narrowed in the parent cannot be recaptured in continuations without losing the priority date. The prosecution strategy designates Claim 5 (the auto-repayment loop) as the terminal fallback: any competitor building an automated payment bridging product must collect repayment somehow, and if they use payment network confirmation data to do so automatically, they infringe Claim 5 regardless of how they have engineered around Claims 1 through 4.

**RBC IP clause — META-01.**

There is a material risk specific to this founding situation. The RBC offer letter contains a broad IP assignment clause covering "anything you conceive, create or produce … during your employment." All ideation and development occurred during the RBC employment period. Counsel review is required before the patent is filed. The bear-case volume covers META-01 in full — including the probability distribution of outcomes, the defence arguments, and the sequencing strategy. This flag is noted here for completeness; the narrative does not go deeper on it.

---

### 7. Filing roadmap

**Step 1 — Provisional (P1).** Drafted. Under counsel review. Filing date to be confirmed at attorney engagement. The provisional filing date (PFD) establishes the priority date for all subsequent filings. No enforceable claims attach to the provisional — it creates the priority date only.

**Step 2 — Non-provisional utility application (P2).** Hard deadline: PFD + 12 months. This filing converts the provisional into five independent claims and thirteen dependent claims (D1–D13). All five independent claims must be preserved as filed. Any examiner-required narrowing must be evaluated against its continuation impact before acceptance.

**Step 3 — PCT filing.** Hard deadline: PFD + 18 months. Covers five jurisdictions: United States Patent and Trademark Office, Canadian Intellectual Property Office, European Patent Office, Intellectual Property Office of Singapore, and UAE. National phase entries follow at approximately thirty months from PFD.

**Step 4 — Continuation family (P3–P15).** Each continuation filed within statutory periods under 35 U.S.C. § 120 inherits the PFD priority date. The most time-sensitive continuation is LIP P4 — pre-emptive liquidity portfolio management — which must file before a competitor publishes in that space. Target: approximately Year 3 from PFD.

**Total investment.** Patent portfolio total investment to secure the core portfolio — utility application, PCT across five jurisdictions, prior art search, and two initial continuations — comes in under two hundred thousand dollars ($200,000).

**Coverage duration.** The last continuation is planned at approximately Year 12 from PFD. Each utility patent carries twenty years of exclusivity from its filing date. The terminal continuation therefore extends portfolio protection approximately thirty-two years from the foundational filing.

*The bear-case volume covers the META-01 RBC clause risk, the Alice §101 depth scenario, and the examiner-narrowing bear case in full.*
