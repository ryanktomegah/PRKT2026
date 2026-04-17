# Market & Timing — Drill

Question bank organised by investor persona × difficulty. Cover the Gold-standard block when self-drilling.

**Canonical anchors** (every answer must touch at least one):
1. **ISO 20022 migration window** — The regulatory migration that produced structured, machine-readable pacs.002 rejection codes; the window that makes real-time failure classification tractable now.
2. **correspondent banking stack** — The Tier 1 and Tier 2/3 interbank settlement layer where LIP operates; not consumer payments, not SMB rails.
3. **Tier 2/3 private counterparties** — The underserved segment JPMorgan US7089207B1 cannot reach; the wedge LIP enters with Damodaran industry-beta and Altman Z' thin-file pricing. (Braided with Patent volume Anchor 2.)
4. **bank-as-borrower, not balance-sheet lender** — The B2B interbank structure: originating bank is the MRFA borrower; LIP licenses the platform; BPI earns a fee share, not net interest margin.
5. **thirty-one point six trillion dollar market** — The canonical TAM anchor; every sizing claim derives from this figure.

**Question IDs:** `Q-MKT-NN` — append-only. Never renumber.

**Every number must trace to `appendix-numbers.md`. No TAM figure is approximated.**

---

## Warm Tier — Q-MKT-01 through Q-MKT-08

### Q-MKT-01 · Generalist VC · Warm
**Question:** "How big is this market?"

**Gold-standard answer** (30-second spoken):
Cross-border B2B payments carry thirty-one point six trillion dollars ($31.6T) annually — FXC Intelligence 2024. Three to five percent fail on first attempt. At the four percent midpoint, one point two seven trillion dollars ($1.27T) in value is disrupted per year. Addressable bridge volume, after excluding investigatory holds and sub-minimum payments, is approximately six hundred thirty billion dollars ($630B). BPI earns a thirty percent fee share on licensee fee revenue in Phase 1 — no balance-sheet capital required to enter.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "The market is in the trillions" (imprecise)
- ❌ "We're going after payment failures generally"

**Bear-case pointer:** None

---

### Q-MKT-02 · Generalist VC · Warm
**Question:** "Why now — what changed?"

**Gold-standard answer** (30-second spoken):
Two force functions. First, the ISO 20022 migration window: SWIFT's coexistence period ended November 2025, producing structured pacs.002 rejection codes across eleven thousand plus member institutions — the data environment that makes real-time failure classification tractable. Second, AMLD6 Article 10 criminal liability for legal persons is forcing Tier 2/3 banks to build investigatory hold discrimination infrastructure. LIP provides both in a single license. Neither existed two years ago.

**Anchors this answer must touch:**
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "The timing feels right"
- ❌ "Banks are looking at AI solutions generally"

**Bear-case pointer:** None

---

### Q-MKT-03 · Generalist VC · Warm
**Question:** "Who are the incumbents?"

**Gold-standard answer** (30-second spoken):
Three categories. JPMorgan handles bridge lending internally for listed counterparties — US7089207B1 covers their method. BNY Mellon has deep custody and clearing infrastructure but no published failure-classification product. Wise and Ripple operate SMB and pre-funded corridor rails at different scales — no overlap with the correspondent banking stack. The gap — real-time pacs.002 classification conditioning a priced bridge offer, extended to Tier 2/3 private counterparties — is unoccupied.

**Anchors this answer must touch:**
- correspondent banking stack
- Tier 2/3 private counterparties

**Don't-say-this traps:**
- ❌ "There are no incumbents" (false)
- ❌ "We're competing with JPMorgan" (misframes the relationship)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-04 · Fintech Specialist · Warm
**Question:** "What's the unit economics per bridge?"

**Gold-standard answer** (30-second spoken):
The live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points, nine-day maturity — total fee five thousand and thirty-three dollars ($5,033), annualised yield seven point zero six percent (7.06%). Phase 1 fee shares: BPI thirty percent (30%), bank seventy percent (70%). Fee tiers step by principal: five hundred basis points below five hundred thousand dollars, four hundred basis points mid-range, three hundred basis points at two million dollars and above. The three-hundred basis point floor is the canonical floor — QUANT-locked.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Fees are around three to five percent" (imprecise — cite bps)
- ❌ "Our take rate is thirty percent" (ambiguous — specify fee share, not revenue share)

**Bear-case pointer:** None

---

### Q-MKT-05 · Fintech Specialist · Warm
**Question:** "What's your SAM and SOM?"

**Gold-standard answer** (30-second spoken):
TAM thirty-one point six trillion dollars ($31.6T), disrupted volume one point two seven trillion dollars ($1.27T) at four percent failure midpoint. SAM is addressable bridge volume after excluding the eight BLOCK-class investigatory hold codes and sub-minimum principals — approximately six hundred thirty billion dollars ($630B). Per-bank SOM: a Tier 1 bank processes three to five trillion dollars ($3T–$5T) in annual correspondent volume; at four percent failure and fifty percent bridgeable, sixty to one hundred billion dollars of bridge principal per bank per year. BPI captures thirty percent of licensee fee revenue in Phase 1.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "SAM is a percentage of TAM" (define the exclusions explicitly)
- ❌ "Hard to size SOM before pilot data" (give the per-bank frame)

**Bear-case pointer:** B-MKT-06

---

### Q-MKT-06 · Bank-strategic · Warm
**Question:** "How does a bank actually buy LIP?"

**Gold-standard answer** (30-second spoken):
Software licence on the LIP platform. The bank is the MRFA borrower — originating bank on the failed payment — and funds one hundred percent of bridge capital in Phase 1. BPI earns a thirty percent fee share; the bank keeps seventy percent. No BPI balance sheet. RBCx is the entry channel for Canada. Bank onboarding cycle eighteen to twenty-four months for a pilot contract. The MRFA is B2B interbank — the bank signs the master facility, not the end customer.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "It's a SaaS product" (loses the MRFA structure)
- ❌ "We lend against bank receivables" (wrong — bank is borrower)

**Bear-case pointer:** B-MKT-02

---

### Q-MKT-07 · Bank-strategic · Warm
**Question:** "Who inside the bank makes the buy decision?"

**Gold-standard answer** (30-second spoken):
Three stakeholders. Transaction Banking owns the pacs.002 pain — they see failed payments today and manage the treasury gap. They are the buyer. The AML / compliance officer signs off on the hold-type discriminator and the `hold_bridgeable` certification API. Their block is structural. Treasury / capital markets owns the MRFA terms and the BIC-derived governing law. At RBC the path is RBCx (Sid Paquette) as sponsor, Transaction Banking (Derek Neldner) as buyer, AI Group (Bruce Ross) as parallel vector.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "The CIO decides" (loses the AML officer gate)
- ❌ "It's an innovation lab sale" (RBCx sponsors, Transaction Banking buys)

**Bear-case pointer:** None

---

### Q-MKT-08 · Adversarial · Warm
**Question:** "Who's using this in production today?"

**Gold-standard answer** (30-second spoken):
Zero banks in production today. Zero letters of intent signed as of today. The working demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points in real time — that is the only live proof point. The RBC pilot is the gate. Sequence: resign from RBC, file the provisional patent, approach through RBCx, Transaction Banking, and the RBC AI Group as an external vendor. Onboarding cycle eighteen to twenty-four months. Seed runway is sized against that timeline.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "We have early-stage conversations with several banks" (vague; say zero LOIs)
- ❌ "We're in production internally" (misleading — demo is not production)

**Bear-case pointer:** B-MKT-01

---

## Probing Tier — Q-MKT-09 through Q-MKT-16

### Q-MKT-09 · Generalist VC · Probing
**Question:** "Defend the thirty-one trillion TAM number."

**Gold-standard answer** (30-second spoken):
FXC Intelligence 2024 — B2B value, not total cross-border value, not message-count. Seven percent is SWIFT message count growth; five point nine percent (5.9%) is value CAGR. Disrupted volume derives from the four percent midpoint failure rate on first attempt. Supporting figures: one hundred eighteen point five billion dollar ($118.5B) global cost of failed payments, Accuity and LexisNexis 2021; LexisNexis fourteen percent first-attempt failure rate under a broader definition. TAM is not flat-growth — the thirty-one point six trillion dollar market is the anchor; addressable volume is six hundred thirty billion dollars after exclusions.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "TAM is a rough estimate" (cite the source)
- ❌ "It could be higher or lower" (pick the canonical anchor)

**Bear-case pointer:** None

---

### Q-MKT-10 · Generalist VC · Probing
**Question:** "Why can't JPMorgan just extend their patent to cover this?"

**Gold-standard answer** (30-second spoken):
Three reasons. First, US7089207B1 requires observable equity market data — private counterparties have none. Extending would require a new structural model; LIP's Tier 2/3 private-counterparty extension via Damodaran industry-beta and Altman Z' is the covering claim. Second, their patent is not conditioned on ISO 20022 pacs.002 events — the two-step classification + conditional offer mechanism is our novel claim, not theirs. Third, JPM serves Tier 1 listed counterparties internally; the correspondent banking stack for Tier 2/3 is the underserved wedge.

**Anchors this answer must touch:**
- Tier 2/3 private counterparties
- correspondent banking stack
- ISO 20022 migration window

**Don't-say-this traps:**
- ❌ "JPMorgan could try but it's hard"
- ❌ "They'd need a new patent" (true but not the point — explain the structural gap)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-11 · Fintech Specialist · Probing
**Question:** "Walk me through corridor-level fee math."

**Gold-standard answer** (30-second spoken):
Corridor example — US-to-EU, Class A (systemic delay, three-day maturity). Principal one million dollars, fee four hundred basis points, maturity three days. Fee total four thousand dollars ($4,000). Phase 1 split: BPI earns thirty percent ($1,200), bank earns seventy percent ($2,800). Annualised yield approximately forty-eight percent ($4K on $1M over three days). Fifty-two capital cycles per year drive revenue. Floor three hundred basis points is QUANT-locked; every loan executed is capital-positive for BPI.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Yields look high but they're short-duration" (be explicit about the math)
- ❌ "We haven't finalised corridor fees" (the floor and tiers are canonical)

**Bear-case pointer:** None

---

### Q-MKT-12 · Fintech Specialist · Probing
**Question:** "What happens if an incumbent launches a copycat in ninety days?"

**Gold-standard answer** (30-second spoken):
Three defences. First, the two-step classification + conditional offer mechanism is the patent claim — a copycat that receives pacs.002, classifies with a hold-type class causing pipeline short-circuit, and conditions an offer on that output infringes Independent Claim 1. Second, the Tier 2/3 private-counterparty extension requires Damodaran and Altman Z' calibration — trade secret. Third, the correspondent banking stack is a trust-and-integration market — licensing incumbency matters more than launch speed. Ninety days is insufficient to displace a signed licence.

**Anchors this answer must touch:**
- correspondent banking stack
- Tier 2/3 private counterparties

**Don't-say-this traps:**
- ❌ "We have a patent so nobody can copy us"
- ❌ "Banks will pick the first mover" (weak argument)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-13 · Bank-strategic · Probing
**Question:** "Bank procurement cycles are eighteen to twenty-four months. How do you survive that?"

**Gold-standard answer** (30-second spoken):
Two structural answers. First, RBCx — RBC's venture arm, Sid Paquette — is an innovation-accelerator channel built to shortcut exactly this cycle. Parallel vectors through Transaction Banking (Derek Neldner) and the RBC AI Group (Bruce Ross) compress to twelve months. Second, seed capital is sized for the full eighteen to twenty-four month onboarding — two hundred thousand dollars per month over eighteen months. The MRFA is B2B interbank — the bank legal review converges on a known correspondent-banking structure, not a novel one.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "We'll find a faster path"
- ❌ "Bank cycles vary widely" (imprecise)

**Bear-case pointer:** B-MKT-02

---

### Q-MKT-14 · Bank-strategic · Probing
**Question:** "Why would an AML officer approve this?"

**Gold-standard answer** (30-second spoken):
The AML officer approves because LIP reduces their regulatory exposure, not raises it. The eight BLOCK-class investigatory hold codes — DNOR, CNOR, RR01 through RR04, AG01, LEGL — are permanently excluded from bridging in code (EPG-19). AMLD6 Article 10 criminal liability for legal persons applies if a bank bridges a compliance-held payment; LIP's hold-type discriminator is the infrastructure that keeps the bank compliant. The `hold_bridgeable` certification flag (EPG-04/05) lets the bank's internal compliance system gate bridging without disclosing why a hold was raised.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "The AML officer signs off because it's automated" (misses the regulatory logic)
- ❌ "Banks can customise the AML rules" (FATF-prohibited to query hold reasons)

**Bear-case pointer:** None

---

### Q-MKT-15 · Adversarial · Probing
**Question:** "ISO 20022 deadlines have slipped before. What if November 2025 slips again?"

**Gold-standard answer** (30-second spoken):
The deadline already held — SWIFT's coexistence period ended November 2025. The structured pacs.002 data environment is live across eleven thousand plus institutions. Even if a regulator extends a national phase-in, the direction of travel does not reverse — banks that migrated are not unwinding. The second force function, AMLD6 investigatory hold infrastructure demand, is independent of ISO 20022 timing. The ISO 20022 migration window is a door that has opened; slippage risk is past, not forward.

**Anchors this answer must touch:**
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "We're betting on ISO 20022 holding" (reframe as past-tense fact)
- ❌ "Even if it slips we can wait" (weak — give the second force function)

**Bear-case pointer:** B-MKT-03

---

### Q-MKT-16 · Adversarial · Probing
**Question:** "Your TAM is headline. Give me SAM minus the stuff you can't actually touch."

**Gold-standard answer** (30-second spoken):
Thirty-one point six trillion dollar ($31.6T) TAM. Four percent midpoint failure rate produces one point two seven trillion dollars ($1.27T) disrupted. Exclude the eight BLOCK-class investigatory hold codes — approximately half of disrupted volume by category count, though dollar-weighted exclusions are smaller. Exclude sub-minimum principals below seven hundred thousand dollars ($700K) for Class B and one million five hundred thousand dollars ($1,500,000) for Class A. Result: approximately six hundred thirty billion dollars ($630B) addressable bridge volume. BPI captures thirty percent of licensee fee revenue in Phase 1.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "SAM is most of TAM" (force the exclusions)
- ❌ "The number is conservative" (cite it)

**Bear-case pointer:** B-MKT-06

---

## Adversarial Tier — Q-MKT-17 through Q-MKT-20

### Q-MKT-17 · Generalist VC · Adversarial
**Question:** "Every fintech deck has a trillion-dollar TAM. Why should I believe yours?"

**Gold-standard answer** (30-second spoken):
Because the anchor is sourced and the exclusions are explicit. Thirty-one point six trillion dollar ($31.6T) from FXC Intelligence 2024 — B2B value only, not cross-border total, not message count. Disrupted volume at four percent midpoint is cross-checked against the one hundred eighteen point five billion dollar ($118.5B) Accuity/LexisNexis 2021 global cost of failed payments and the LexisNexis fourteen percent figure under a broader definition. Addressable volume after hold and principal exclusions is six hundred thirty billion dollars ($630B). Every number traces to the appendix.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Our TAM is conservative relative to peers" (weak)
- ❌ "The numbers are from multiple sources" (cite them specifically)

**Bear-case pointer:** B-MKT-06

---

### Q-MKT-18 · Fintech Specialist · Adversarial
**Question:** "JPMorgan and BNY have incumbency. You're late."

**Gold-standard answer** (30-second spoken):
Incumbency applies to Tier 1 listed counterparties — JPMorgan US7089207B1 structurally cannot price Tier 2/3 private counterparties, because private companies produce no observable equity market data. That is the gap. LIP's Tier 2/3 private-counterparty extension via Damodaran industry-beta and Altman Z' thin-file models covers it. The ISO 20022 migration window produced the pacs.002 data environment after US7089207B1 filed — so their claim cannot touch the two-step classification + conditional offer mechanism. We are not late; we are building the layer that their structural model cannot.

**Anchors this answer must touch:**
- Tier 2/3 private counterparties
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "They're slow to move" (weak)
- ❌ "We're smaller and nimbler" (weak)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-19 · Bank-strategic · Adversarial
**Question:** "Banks build this kind of thing internally. Why would they buy?"

**Gold-standard answer** (30-second spoken):
Three reasons. First, the two-step classification + conditional offer mechanism is patent-protected — an internal build infringes Independent Claim 1 or requires designing around a specific technical gate. Less efficient than licensing. Second, the Tier 2/3 private-counterparty extension requires Damodaran and Altman Z' calibration on a corridor-level correspondent bank dataset — trade-secret calibration, eighteen to twenty-four months of data work at best. Third, AMLD6 Article 14 audit trail, OSFI E-23 model validation reports, DORA operational resilience documentation — LIP ships these as licensed artefacts, not as build-it-yourself compliance projects.

**Anchors this answer must touch:**
- Tier 2/3 private counterparties
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Banks don't build this kind of thing" (false — they can and do)
- ❌ "It's too complex for in-house teams" (weak)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-20 · Adversarial · Adversarial
**Question:** "Zero LOIs. Zero production traffic. You have nothing."

**Gold-standard answer** (30-second spoken):
Correct on the facts. Zero LOIs signed. Zero production banks. The working demo — two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge priced at seven hundred six basis points in real time — is the only live proof point. The RBC pilot is the gate; the sequencing is named: resign from RBC, file the provisional patent, approach as an external vendor through RBCx, Transaction Banking, and the AI Group. Seed runway is sized against eighteen to twenty-four month bank onboarding. First LOI is the resolution milestone — the market claim becomes evidentiary at that point.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "We're pre-revenue like any seed-stage company" (weak)
- ❌ "Early conversations are promising" (vague)

**Bear-case pointer:** META-02, B-MKT-01

---

## Crushing Tier — Q-MKT-21 through Q-MKT-24

### Q-MKT-21 · Generalist VC · Crushing
**Question:** "If RBC's IP clause attaches to LIP, your whole market entry is through a hostile counterparty. What's the plan?"

**Gold-standard answer** (60-second spoken):
Correct — META-01 is the most consequential risk in the stack. The sequencing is deliberate. Conception and development predate the RBC start date of January 12, 2026 — repository commit history and independent development documentation establish this factually. Employment counsel is engaged. The plan is resignation before the non-provisional filing milestone, so the non-provisional is filed as an external vendor, not as an RBC employee. The patent is not socialised inside RBC before resignation — nothing in the application record creates an RBC nexus. If RBC asserts a claim, the factual timeline is defensible. Even in the worst-case scenario where the clause attaches, the pilot path shifts to a non-RBC Tier 2 Canadian or European bank — RBC is the primary vector, not the only vector. The SAFE and cap table are gated on clean chain of title. META-01 in the Patent bear-case covers the full probability distribution.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "RBC would never assert the clause" (complacent)
- ❌ "We'll pivot to another bank" (vague — name the secondary path)
- ❌ "The clause is standard boilerplate" (dismissive)

**Bear-case pointer:** META-01, B-MKT-01

---

### Q-MKT-22 · Fintech Specialist · Crushing
**Question:** "AMLD7 text changes investigatory hold definitions. Your Class B pool shrinks by half. Argue."

**Gold-standard answer** (30-second spoken):
AMLD7 text is not finalised. If investigatory hold definitions widen and Class B shrinks, addressable bridge volume falls — from six hundred thirty billion dollars ($630B) toward four hundred billion dollars or lower, depending on the reclassification scope. That reduces TAM but does not create compliance exposure — the BLOCK-class gate is designed to expand, not shrink. Fee floor at three hundred basis points and the Tier 2/3 private-counterparty extension still hold on the remaining volume. Phase 1 licensing economics do not require the top of the band; a single Tier 1 bank at six million dollar ($6M) Year 3 conservative revenue does not depend on Class B width. The bear-case volume carries the scenario math.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "AMLD7 is years away" (hand-wave)
- ❌ "We'll adapt if it happens" (too vague)

**Bear-case pointer:** B-MKT-04

---

### Q-MKT-23 · Bank-strategic · Crushing
**Question:** "Revenue lag is two to three years from pilot to material ARR. Show me the ramp."

**Gold-standard answer** (30-second spoken):
Conservative Year 3, one Tier 1 bank in Phase 1: six million dollars ($6.0M). Base Year 3: twenty-three million dollars ($23.0M). The ramp is license-driven — each additional bank onboarded is independent fee-share revenue, not proportional capital deployment. Base Year 10, fifteen banks: approximately nine hundred twenty-one million dollars ($921M). Upside Year 10: approximately three point two billion dollars ($3.2B). Cumulative base Years 3 through 10: approximately two point two billion dollars ($2.2B). Seed runway at two hundred thousand dollars per month for eighteen months is sized to first LOI, not first revenue dollar.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Revenue will inflect in Year 3" (cite the figures)
- ❌ "Our model shows strong growth" (vague)

**Bear-case pointer:** B-MKT-07

---

### Q-MKT-24 · Adversarial · Crushing
**Question:** "Thirty-one trillion TAM is nonsense. Half your disrupted volume is permanently blocked. Convince me this is a real market."

**Gold-standard answer** (30-second spoken):
Agreed that TAM alone is not the market. Addressable bridge volume after blocking the eight investigatory hold codes and sub-minimum principals is six hundred thirty billion dollars ($630B) — the real number. At three hundred to five hundred basis point fee tiers, that is a multi-billion-dollar annual fee pool. BPI captures thirty percent in Phase 1. Per-bank SOM is sixty to one hundred billion dollars of bridge principal at a Tier 1 bank; one pilot bank at six million dollars ($6M) conservative Year 3 revenue validates the unit economics. The market is not thirty-one trillion; the market is a six-hundred-thirty-billion-dollar addressable flow with a validated fee floor and a specified capture mechanism.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "TAM is the starting point" (concede and reframe instead)
- ❌ "The thirty-one trillion is defensible" (the argument is SAM, not TAM)

**Bear-case pointer:** B-MKT-06, META-02
