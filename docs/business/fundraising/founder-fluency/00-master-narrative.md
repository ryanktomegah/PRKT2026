# Master Braided Narrative

**How to read this file:** Four tiers (30-second / 2-minute / 5-minute / deep-dive) of the full LIP pitch, woven across all three volumes — Technical, Patent, Market. No tier speaks for more than thirty seconds about one topic without crossing into an adjacent topic. When an investor asks "what do you do," read the tier that matches the time available.

**Braid anchors** (every tier must carry all three):
1. **Technical** — *two-step classification + 94 milliseconds* — the latency-bounded classification gate that decides whether a payment can be bridged before ML inference fires.
2. **Patent** — *two-step classification + conditional offer mechanism, extended to Tier 2/3 private counterparties* — the novel claim LIP owns, covering the gap JPMorgan US7089207B1 structurally cannot reach.
3. **Market** — *ISO 20022 migration window + bank-as-borrower, not balance-sheet lender* — the regulatory door that opened the data environment, and the licensed B2B structure that captures the resulting flow.

**Braid rule.** No tier is allowed to speak for more than thirty seconds about one topic without crossing into an adjacent topic. Each beat below is tagged with the topic it foregrounds; the braid check counts topic presence across tiers.

---

## Tier A — 30-second braided pitch

Cross-border B2B payments carry thirty-one point six trillion dollars ($31.6T) per year — three to five percent fail, and the ISO 20022 migration window just produced the structured pacs.002 rejection codes that make real-time failure classification tractable. [Market]
LIP is the two-step classification + conditional offer mechanism that decides in under ninety-four milliseconds whether a failed payment can be bridged, and conditionally prices a bridge loan — patent-pending, with a novel extension to Tier 2/3 private counterparties that JPMorgan's prior art cannot reach. [Technical + Patent]
BPI licenses the platform; the originating bank is the MRFA borrower — bank-as-borrower, not balance-sheet lender — and BPI earns a thirty percent fee share at a three-hundred basis point floor, no BPI capital required in Phase 1. [Market]

---

## Tier B — 2-minute braided pitch

**Beat 1 — [Market + Technical].** Cross-border B2B payments move thirty-one point six trillion dollars ($31.6T) annually. Three to five percent fail — one point two seven trillion dollars ($1.27T) in disrupted value each year through the correspondent banking stack. The ISO 20022 migration window closed in November 2025, producing structured pacs.002 rejection codes across eleven thousand plus institutions. That is the data environment that makes real-time classification tractable.

**Beat 2 — [Technical + Patent].** LIP is the two-step classification + conditional offer mechanism. Step one: classify the pacs.002 rejection code against a three-class taxonomy — permanent failure, systemic delay, investigatory hold. Step two: offer a priced bridge loan only when the classification clears the bridgeability gate. The entire pipeline — C1 through C7 — runs under ninety-four milliseconds at p99. That gate is the core novel patent claim.

**Beat 3 — [Patent + Market].** JPMorgan US7089207B1 covers bridge lending for listed counterparties — it requires observable equity market data. Private counterparties have none. LIP's Tier 2/3 private-counterparty extension via Damodaran industry-beta and Altman Z' thin-file models covers exactly the gap their structural model cannot reach. That is the novel claim; that is the market wedge.

**Beat 4 — [Market + Technical].** The live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points in real time, nine-day maturity, total fee five thousand and thirty-three dollars ($5,033). Bank-as-borrower, not balance-sheet lender: the originating bank is the MRFA borrower, BPI earns a thirty percent fee share at a three-hundred basis point floor, and no BPI capital is required in Phase 1.

**Beat 5 — [Market].** Zero LOIs signed as of today. The RBC pilot is the gate — sequenced after resignation and provisional filing, approached through RBCx, Transaction Banking, and the RBC AI Group as an external vendor. Seed runway at two hundred thousand dollars ($200K) per month for eighteen months is sized against the eighteen- to twenty-four-month bank procurement cycle.

---

## Tier C — 5-minute braided pitch

**Beat 1 — [Market].** Cross-border B2B payments carry thirty-one point six trillion dollars ($31.6T) annually — FXC Intelligence 2024, B2B value only. At the four percent midpoint failure rate, one point two seven trillion dollars ($1.27T) in value is disrupted each year. Addressable bridge volume, after excluding the eight BLOCK-class investigatory hold codes and sub-minimum principals, is approximately six hundred thirty billion dollars ($630B). The FSB 2024 G20 report shows only five point nine percent (5.9%) of B2B services settle within one hour versus a seventy-five percent target. That is the market.

**Beat 2 — [Technical + Patent].** LIP is the classification layer built on top of the new ISO 20022 data environment. The two-step classification + conditional offer mechanism is both the technical architecture and the core patent claim. Step one classifies the pacs.002 rejection code into permanent failure, systemic delay, or investigatory hold. Step two gates a priced bridge loan offer on that classification. The investigatory hold class short-circuits the pipeline before any ML inference or offer generation — that is the structural compliance gate.

**Beat 3 — [Technical].** The latency spec is ninety-four milliseconds at p99, under fifty milliseconds at median. C1 is a three-headed failure classifier — GraphSAGE on corridor graph structure, TabTransformer on pacs.002 tabular features, LightGBM on the combined embedding — with an F2-optimal threshold of 0.110. C2 is the tiered PD model: Merton/KMV for Tier 1 listed counterparties, Damodaran industry-beta for Tier 2, Altman Z' thin-file for Tier 3. C6 runs the sanctions screen and Rust velocity engine. C7 executes the loan with a kill switch and gRPC offer router. Every canonical constant is QUANT-locked.

**Beat 4 — [Patent + Market].** JPMorgan's US7089207B1 is the closest prior art — bridge lending for listed counterparties, observable equity data required. Private counterparties produce no equity price series, so their structural model structurally cannot reach Tier 2/3. LIP's Tier 2/3 private-counterparty extension via Damodaran and Altman Z' covers that gap. That is the market wedge and the novel claim simultaneously — the patent is the licensing economics moat; the market is the flow their prior art cannot price.

**Beat 5 — [Patent + Technical].** The patent is a five-patent-family architecture. Family 1 is the core — the two-step classification + conditional offer mechanism on ISO 20022 rejection events. Family 2 covers multi-rail settlement; Family 3 the dispute classifier; Family 4 federated learning; Family 5 CBDC normalization. Alice-clean anchoring is built in from draft one — *Enfish v. Microsoft* for technical infrastructure improvement, *McRO v. Bandai Namco* for specific technological rules. The non-provisional filing milestone at PFD + 12 months converts provisional protection into enforceable claims across US, Canada, EPO, Singapore, and UAE.

**Beat 6 — [Market].** LIP licenses the platform; the bank is the MRFA borrower — bank-as-borrower, not balance-sheet lender. In Phase 1 the bank funds one hundred percent of bridge capital; BPI earns a thirty percent fee share at a three-hundred basis point floor. No BPI warehouse facility required to enter. The live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points, nine-day maturity — total fee five thousand and thirty-three dollars ($5,033), annualised yield seven point zero six percent (7.06%). Phase 2 and Phase 3 transition to hybrid and full BPI capital; that sequencing is in the capital strategy.

**Beat 7 — [Market + Technical].** Zero LOIs signed as of today. The RBC pilot is the gate. The sequence is specified: resign from RBC, file the provisional patent, approach as an external vendor through RBCx (Sid Paquette), Transaction Banking (Derek Neldner), and the RBC AI Group (Bruce Ross). Bank onboarding cycle is eighteen to twenty-four months. Seed runway at two hundred thousand dollars ($200K) per month for eighteen months is sized to first LOI, not first revenue dollar. Conservative Year 3 (one bank, Phase 1): six million dollars ($6.0M). Base Year 10 (fifteen banks): approximately nine hundred twenty-one million dollars ($921M).

---

## Tier D — Deep-dive braided pitch (~2,000 words)

### 1. The market and the window — [Market]

Cross-border B2B payments carry thirty-one point six trillion dollars ($31.6T) annually. That figure is FXC Intelligence 2024, B2B value only — not total cross-border flow, not SWIFT message count. The CAGR is five point nine percent (5.9%); seven percent is message-count growth, not value growth. At the four percent midpoint failure rate, one point two seven trillion dollars ($1.27T) of that volume is disrupted each year — supported by the one hundred eighteen point five billion dollar ($118.5B) Accuity / LexisNexis 2021 global cost-of-failed-payments figure and the LexisNexis fourteen percent first-attempt failure rate under a broader definition.

Addressable bridge volume is the number that matters. After excluding the eight BLOCK-class investigatory hold codes (DNOR, CNOR, RR01 through RR04, AG01, LEGL) and sub-minimum principals below seven hundred thousand dollars ($700K) for Class B and one million five hundred thousand dollars ($1,500,000) for Class A, the remaining addressable bridge volume is approximately six hundred thirty billion dollars ($630B) annually. That is the market LIP serves.

The ISO 20022 migration window is why the timing is now. SWIFT's coexistence period ran through November 2025; structured pacs.002 rejection codes are now standardised across eleven thousand plus member institutions. That migration created the data environment that makes real-time failure classification tractable. A real-time classification layer on top of structured pacs.002 rejections did not exist because structured pacs.002 rejections did not exist. The door is open.

### 2. The classification layer — [Technical + Patent]

LIP is the two-step classification + conditional offer mechanism. That phrase is the technical architecture and the core patent claim simultaneously.

Step one: receive the pacs.002 rejection code. Classify against a three-class taxonomy — permanent failure, systemic delay, investigatory hold. Step two: route to the lending pipeline if the classification is permanent failure or systemic delay; short-circuit before any ML inference, pricing, or offer generation if the classification is investigatory hold. The pipeline short-circuit before inference is the structural compliance gate — EPG-19 — and the structural novelty in the patent claim.

The latency spec is ninety-four milliseconds at p99, under fifty milliseconds at median, end to end. Every bank sees the failure in the same instant LIP sees it; the decision must land inside the window before a treasury officer opens the case manually. That ninety-four-millisecond SLO is a technical infrastructure improvement — which is what *Enfish v. Microsoft* 2016 held eligible under §101. The classification gate itself — specific technological rules imposed on a specific data artifact — is what *McRO v. Bandai Namco* 2016 held eligible. Alice-clean anchoring is in the claim structure from draft one.

### 3. The failure classifier and the PD model — [Technical]

C1 is the three-headed failure classifier. GraphSAGE on corridor graph structure (output dimension 384) carries the structural-risk signal — which BIC pairs historically fail together and which are clean. TabTransformer on pacs.002 tabular features (output dimension 88) carries the event-specific signal — code, amount, time of day, corridor. LightGBM on the combined embedding delivers the final probability. F2-optimal threshold of 0.110 — the asymmetric BCE alpha of 0.7 reflects the design choice that false negatives cost the bank a stalled trade, so the model errs toward false positives.

C2 is the tiered PD model. Tier 1 listed counterparties get Merton / KMV structural PD from observable equity data. Tier 2 private counterparties get Damodaran industry-beta calibration — unobservable equity replaced by industry-level regressions. Tier 3 thin-file counterparties get Altman Z' with thin-file weights. That tiered structure is the Tier 2/3 private-counterparty extension — Dependent Claim D5 in the patent, and the market wedge into the segment JPMorgan's US7089207B1 structurally cannot reach.

### 4. The patent family — [Patent]

Five independent claims, thirteen dependent claims. Independent Claim 1 is the two-step classification + conditional offer mechanism — the classification gate on ISO 20022 pacs.002 events. Independent Claim 5 is the auto-repayment loop — UETR settlement monitoring with automatic repayment initiation via the correspondent banking rails. Dependent Claim D4 covers the B1 / B2 sub-classification (procedural vs. investigatory holds). Dependent Claim D5 covers the Tier 2/3 private-counterparty extension. Dependent Claim D13 covers adversarial camt.056 recall detection.

The five-patent-family architecture compounds the moat. Family 1 is the core. Family 2 covers multi-rail settlement. Family 3 covers the C4 dispute classifier. Family 4 covers federated learning across licensees. Family 5 covers CBDC normalization. Each family extends through continuations at no incremental filing cost.

The non-provisional filing milestone is at PFD + 12 months — the hard deadline that converts provisional protection into enforceable claims. PCT at PFD + 18 months locks five jurisdictions: US, Canada, EPO, Singapore, UAE. Prior art analysis names two references: JPMorgan US7089207B1 (2006) and Bottomline US11532040B2 (2022). Neither covers the two-step classification + conditional offer mechanism; neither covers the Tier 2/3 extension. No single reference or combination teaches all five elements of Independent Claim 1.

### 5. The licensing economics — [Market + Patent]

LIP licenses the platform. The bank is the MRFA borrower — bank-as-borrower, not balance-sheet lender. Phase 1: the originating bank funds one hundred percent of bridge capital; BPI earns a thirty percent fee share; the bank earns seventy percent. Fee tiers: five hundred basis points below five hundred thousand dollars ($500K) principal, four hundred basis points in the five hundred thousand to two million dollar range, three hundred basis points at or above two million dollars ($2M) — the QUANT-locked floor. Every loan executed is capital-positive for BPI because no BPI capital is at risk in Phase 1.

The live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points, nine-day maturity, total fee five thousand and thirty-three dollars ($5,033), annualised yield seven point zero six percent (7.06%). That is the only live proof point today.

Phase 2 transitions to hybrid capital: BPI and an SPV contribute seventy percent, the bank contributes thirty percent; BPI earns a fifty-five percent fee share. Phase 3 is full MLO structure: BPI funds one hundred percent via the SPV, earns an eighty percent fee share; the bank earns a twenty percent distribution premium. Income classification changes materially — Phase 1 is royalty income; Phase 2 and Phase 3 are lending revenue — a tax and legal distinction that has been reviewed.

### 6. The regulatory backdrop — [Market]

Four drivers. ISO 20022 through November 2025 is the data-environment driver — structured pacs.002 across eleven thousand plus institutions. AMLD6 Article 10 is the compliance-infrastructure driver — criminal liability for legal persons on investigatory hold failures forces Tier 2/3 banks to build hold-type discrimination, which LIP provides. DORA (EU) is the operational resilience driver — relevant to Phase 2 and Phase 3 European bank onboarding. OSFI E-23 (Canada, effective May 2027) is the Canadian SR 11-7 equivalent — LIP pre-generates the model validation reports. EU AI Act Article 14 human oversight requirements are directly implemented by C6 anomaly routing to PENDING_HUMAN_REVIEW.

Regulatory headwinds. AMLD7 is not finalised; widened investigatory hold definitions would shrink the addressable Class B pool — from six hundred thirty billion dollars toward four hundred billion or lower. The BLOCK-class gate is designed to expand, not break; compliance value rises as scope narrows. Phase 2 and Phase 3 lending license obligations are known gating requirements, not surprises.

### 7. The entry path and the runway — [Market]

Zero LOIs signed as of today. The RBC pilot is the gate. Three parallel vectors: RBCx (Sid Paquette) as innovation-accelerator sponsor, Transaction Banking (Derek Neldner) as the operational buyer, RBC AI Group (Bruce Ross, formed February 2026) as the AI-mandate channel. The sequence is fixed — resign from RBC, file the provisional patent, approach as an external vendor. Chain-of-title has to be clean before outreach starts.

Bank onboarding cycle is eighteen to twenty-four months. Seed runway at two hundred thousand dollars ($200K) per month for eighteen months is sized to first LOI, not first revenue dollar. Series A economics are gated on signed pilots, not revenue.

Revenue trajectory. Conservative Year 3 (one Tier 1 bank, Phase 1): six million dollars ($6.0M). Base Year 3: twenty-three million dollars ($23.0M). Conservative Year 10: approximately two hundred forty-one million dollars ($241M). Base Year 10 (fifteen banks): approximately nine hundred twenty-one million dollars ($921M). Upside Year 10: approximately three point two billion dollars ($3.2B). Cumulative base Years 3 through 10: approximately two point two billion dollars ($2.2B).

### 8. The META risks — [Patent + Market + Technical]

Three meta risks deserve explicit acknowledgement.

**META-01 — RBC IP clause.** The RBC offer letter contains a broad IP assignment clause covering anything conceived during employment. This is the most consequential single risk in the stack. Conception and development predate the January 12, 2026 RBC start date — the repository commit history establishes this factually. Sequencing: resignation before non-provisional filing, so the filing lands as an external vendor. Employment counsel is engaged. The SAFE and cap table are gated on clean chain of title. Patent bear-case carries the full probability distribution.

**META-02 — No production traffic.** Pre-production. The full pipeline runs on two million synthetic pacs.002 records calibrated to BIS / SWIFT GPI settlement distributions. One thousand two hundred eighty-four tests passing, ninety-two percent coverage. First live UETR in the first pilot bank is the resolution event; until then, every metric carries the synthetic caveat.

**META-03 — Non-technical founder.** Strategic background, not engineering. The governance model is the Ford Principle — the team translates direction into correct technical decisions and has explicit authority to push back. QUANT has final authority on financial math; CIPHER on security and AML; REX on compliance. Fluency is demonstrated continuously, not proven by a single event.

### 9. The single-sentence close — [Technical + Patent + Market]

LIP is the two-step classification + conditional offer mechanism that decides under ninety-four milliseconds whether a failed cross-border payment can be bridged, and prices a bridge loan when it can — a patent-pending novel claim extending to the Tier 2/3 private-counterparty segment JPMorgan's prior art cannot reach, delivered as a licensed platform where the originating bank is the MRFA borrower so BPI earns a three-hundred-basis-point-floor fee share with no balance-sheet capital required in Phase 1, entering the market through the ISO 20022 migration window that structured pacs.002 rejections just opened.
