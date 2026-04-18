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

---

## Warm Tier (expansion) — Q-MKT-25 through Q-MKT-32

### Q-MKT-25 · Generalist VC · Warm
**Question:** "Walk me through a bank sales cycle end to end."

**Gold-standard answer** (30-second spoken):
Eighteen to twenty-four months, Tier 1 bank. First conversation with RBCx (Sid Paquette) or Transaction Banking (Derek Neldner). Technical diligence runs three to six months against the two-step classification plus conditional offer mechanism. Legal review on the MRFA, BIC-derived governing law, and the three `hold_bridgeable` warranties — six to nine months. Pilot contract signed. Integration and first live UETR — another three to six months. Seed runway at two hundred thousand dollars per month over eighteen months is sized against this cycle, not a best case.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "It moves faster with the right champion" (overpromise)
- ❌ "We'll adapt the timeline" (the bank's timeline governs)

**Bear-case pointer:** B-MKT-02

---

### Q-MKT-26 · Generalist VC · Warm
**Question:** "How does the thirty-one trillion break down by region?"

**Gold-standard answer** (30-second spoken):
The thirty-one point six trillion dollar ($31.6T) anchor is global B2B cross-border volume — FXC Intelligence 2024. Entry geography for LIP is Canada through RBCx, then EU through DORA and AMLD6-aligned Tier 2 banks, then UK, Singapore, and UAE through the PCT jurisdictions filed at PFD plus eighteen months. US enters via Tier 2 correspondent banks after OSFI and EU pilots validate. Corridor-level volume analysis at first pilot converts the headline global TAM into live per-corridor evidence.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "North America is fifty percent" (unsupported regional split)
- ❌ "We'll start in the US" (wrong — Canada via RBCx is the entry path)

**Bear-case pointer:** None

---

### Q-MKT-27 · Fintech Specialist · Warm
**Question:** "Segment bridge deals by size. Where do the fees actually concentrate?"

**Gold-standard answer** (30-second spoken):
Three tiers. Below five hundred thousand dollars ($500K), fee is five hundred basis points — sub-minimum principal, limited volume. Five hundred thousand to two million dollars ($500K–$2M), four hundred basis points — the thick middle of correspondent banking flow. At or above two million dollars ($2M), three hundred basis points — the canonical QUANT-locked floor. The live demo sat in the top tier: two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points, annualised yield seven point zero six percent (7.06%). Average fee in the base case: four hundred basis points.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Fees are three to five hundred bps on average" (cite the tiers)
- ❌ "Small deals drive revenue" (fee pool concentrates in the mid-to-large tier)

**Bear-case pointer:** None

---

### Q-MKT-28 · Fintech Specialist · Warm
**Question:** "Give me one concrete corridor and its annual bridge principal."

**Gold-standard answer** (30-second spoken):
US-to-EU, Tier 1 bank, Class A systemic delays. Per-bank correspondent volume three to five trillion dollars ($3T–$5T) annually. Four percent midpoint failure produces one hundred twenty to two hundred billion dollars of disrupted volume. Fifty percent bridgeable after investigatory hold and sub-minimum exclusions: sixty to one hundred billion dollars of annual bridge principal per bank on that corridor class. Average principal one million dollars, average maturity seven days, fifty-two capital cycles per year. Phase 1 BPI share thirty percent of fee revenue.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Corridors are hard to size in advance" (give the per-bank frame)
- ❌ "We'll model corridors after pilot" (the math is already specified)

**Bear-case pointer:** None

---

### Q-MKT-29 · Bank-strategic · Warm
**Question:** "What's a realistic cadence from first meeting to first live UETR?"

**Gold-standard answer** (30-second spoken):
Month zero, RBCx first meeting. Month three, technical diligence kickoff with Transaction Banking and the AI Group in parallel. Month nine, MRFA and `hold_bridgeable` warranty negotiation with the bank's legal team. Month fifteen, pilot contract signed. Month eighteen to twenty-four, integration and first live UETR. Seed capital at two hundred thousand dollars per month over eighteen months is sized to reach signed pilot contract, not first revenue dollar. First LOI is the Series A trigger.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "First UETR within twelve months" (overpromise)
- ❌ "Cadence varies widely" (give the monthly steps)

**Bear-case pointer:** B-MKT-02

---

### Q-MKT-30 · Bank-strategic · Warm
**Question:** "What principal size should a bank expect on its first ten bridges?"

**Gold-standard answer** (30-second spoken):
Average correspondent banking transaction five hundred thousand to five million dollars ($500K–$5M) — BIS CPMI and McKinsey 2024. First ten pilot bridges land in the mid tier: five hundred thousand to two million dollars ($500K–$2M), four hundred basis points. Expected blended fee per bridge two thousand to ten thousand dollars. Live demo proof point: two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points, nine-day maturity, fee five thousand and thirty-three dollars ($5,033). Class A maturity three days, Class B seven days. Principal floors one million five hundred thousand dollars Class A, seven hundred thousand dollars Class B.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Small bridges at first" (imprecise — cite the floors)
- ❌ "It depends on the corridor" (give the expected blended figure)

**Bear-case pointer:** None

---

### Q-MKT-31 · Adversarial · Warm
**Question:** "You say thirty-one trillion — most of that is in regions you won't touch for years. What's really reachable?"

**Gold-standard answer** (30-second spoken):
Correct that geographic reach is sequenced. Thirty-one point six trillion dollar ($31.6T) TAM is global. Canada enters first through RBCx. EU enters second through DORA and AMLD6-aligned Tier 2 banks. UK, Singapore, and UAE follow via the PCT jurisdictions at PFD plus eighteen months. Addressable bridge volume — six hundred thirty billion dollars ($630B) after hold and sub-minimum exclusions — is the reachable denominator, not the thirty-one trillion. Year 3 conservative revenue of six million dollars ($6.0M) is built on one Tier 1 bank, not fifteen.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "We have global reach from day one" (false — sequenced by jurisdiction)
- ❌ "Geographic mix is fluid" (name the sequence)

**Bear-case pointer:** B-MKT-06

---

### Q-MKT-32 · Adversarial · Warm
**Question:** "Bank sales cycles kill startups. What's your plan to not run out of runway?"

**Gold-standard answer** (30-second spoken):
Seed capital at two hundred thousand dollars per month over eighteen months is sized against the eighteen to twenty-four month bank onboarding cycle — designed to reach first LOI, not first revenue dollar. Three RBC vectors run in parallel — RBCx, Transaction Banking, AI Group — so the effective cycle is the fastest of three independent processes. One non-RBC Tier 2 Canadian or European bank runs as a secondary path. Series A is gated on signed pilot, priced against deployed contracts, not projected flow.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "We'll raise bridge capital if needed" (weak)
- ❌ "The cycle will be faster for us" (unsupported)

**Bear-case pointer:** B-MKT-02

---

## Probing Tier (expansion) — Q-MKT-33 through Q-MKT-40

### Q-MKT-33 · Generalist VC · Probing
**Question:** "Pick a single corridor. Show me the full unit economics."

**Gold-standard answer** (30-second spoken):
US-to-EU, Class A, systemic delay. Principal one million dollars, fee four hundred basis points, three-day maturity. Fee total four thousand dollars ($4,000). Phase 1 split: BPI thirty percent ($1,200), bank seventy percent ($2,800). Annualised yield approximately forty-eight percent on three-day duration. Per-bank corridor principal sixty to one hundred billion dollars annually at a Tier 1 bank. Fifty-two capital cycles per year. Floor three hundred basis points QUANT-locked — every executed loan is capital-positive for BPI.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Unit economics vary by corridor" (give the numbers)
- ❌ "Annualised yield looks unsustainable" (be explicit on short duration)

**Bear-case pointer:** None

---

### Q-MKT-34 · Generalist VC · Probing
**Question:** "How does OSFI E-23 actually help you sell in Canada?"

**Gold-standard answer** (30-second spoken):
OSFI E-23 is Canada's SR 11-7 equivalent — effective May 2027. Every Canadian D-SIB must produce model validation reports: out-of-time validation, data cards, model cards. LIP ships these as licensed artefacts, pre-generated. For RBC, that converts a compliance burden into a compliance asset delivered with the licence. The bank's Model Risk Management function reviews a ready artefact instead of building one. EU AI Act Article 14 human oversight via PENDING_HUMAN_REVIEW (EPG-18) and DORA documentation apply the same pattern in Phase 2 European onboarding.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "OSFI E-23 is a compliance box-check" (it is a buy signal)
- ❌ "Banks figure this out internally" (the pre-generated artefact is the leverage)

**Bear-case pointer:** None

---

### Q-MKT-35 · Fintech Specialist · Probing
**Question:** "Walk corridor economics at the fee floor. Show capital-positive math."

**Gold-standard answer** (30-second spoken):
Floor case. Principal two million dollars ($2M), fee three hundred basis points — the canonical QUANT-locked floor. Seven-day maturity. Fee total approximately eleven thousand five hundred dollars ($11,500). Fee per seven-day cycle at the floor: zero point zero five seven five percent (0.0575%). Phase 1 split BPI thirty percent, bank seventy percent. Fifty-two capital cycles per year. Warehouse eligibility floor is eight hundred basis points, above the fee floor — so Phase 1 economics do not require SPV warehouse funding. Every loan at the floor is capital-positive for BPI because Phase 1 carries no balance sheet.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Floor loans are marginal" (false — capital-positive for BPI in Phase 1)
- ❌ "We rarely hit the floor" (do not dodge — the floor is the canonical case)

**Bear-case pointer:** None

---

### Q-MKT-36 · Fintech Specialist · Probing
**Question:** "Break EU unit economics under AMLD6 versus where AMLD7 might land."

**Gold-standard answer** (30-second spoken):
Under AMLD6 Article 10, eight BLOCK-class codes are permanently excluded — DNOR, CNOR, RR01 through RR04, AG01, LEGL. Addressable bridge volume six hundred thirty billion dollars ($630B). If AMLD7 widens investigatory hold definitions, the BLOCK list expands and Class B shrinks — addressable could drop toward four hundred billion dollars. Fee floor three hundred basis points and the Tier 2/3 private-counterparty extension still hold on remaining volume. Phase 1 licensing economics do not require the top of the band — one Tier 1 bank at six million dollars ($6.0M) Year 3 conservative revenue does not depend on Class B width.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "AMLD7 won't matter" (unsupported)
- ❌ "We'll wait for finalised text" (name the scenario math)

**Bear-case pointer:** B-MKT-04

---

### Q-MKT-37 · Bank-strategic · Probing
**Question:** "On a US-to-EU corridor, what does the bank actually keep per bridge?"

**Gold-standard answer** (30-second spoken):
One-million-dollar principal, four hundred basis points, three-day Class A maturity. Fee total four thousand dollars ($4,000). Bank keeps seventy percent in Phase 1 — two thousand eight hundred dollars ($2,800) per bridge. At sixty to one hundred billion dollars of annual corridor principal, fifty-two cycles per year, blended four hundred basis point fee, the bank's Phase 1 fee-share revenue runs in the hundreds of millions annually on this one corridor class alone. Bank keeps the relationship, funds the capital, earns the seventy percent share.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "The bank earns net interest margin" (wrong — it is a fee share, not NIM)
- ❌ "Per-corridor numbers require calibration" (give the specified math)

**Bear-case pointer:** None

---

### Q-MKT-38 · Bank-strategic · Probing
**Question:** "DORA applies to EU banks in 2025. What does LIP ship on day one?"

**Gold-standard answer** (30-second spoken):
Three DORA-aligned artefacts, pre-built. First, operational resilience documentation — incident classification, recovery time objectives, third-party risk registers. Second, audit trail architecture — decision log retention at seven years, UETR-keyed event chain. Third, model governance via EU AI Act Article 14 — C6 anomaly routing to PENDING_HUMAN_REVIEW (EPG-18). For EU Tier 2 banks onboarding in Phase 2, LIP is a licensed compliance artefact set, not a build-it-yourself project. DORA becomes a buy accelerator, not a friction point.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "DORA compliance is the bank's problem" (LIP reduces their exposure)
- ❌ "We'll document DORA later" (the artefacts ship with the licence)

**Bear-case pointer:** None

---

### Q-MKT-39 · Adversarial · Probing
**Question:** "Corridor-level unit economics look pretty on paper. What blows them up in practice?"

**Gold-standard answer** (30-second spoken):
Three observable failure modes, each named and bounded. First, AMLD7 reclassification moves Class B volume into the BLOCK pool — covered by B-MKT-04, addressable drops toward four hundred billion dollars. Second, an incumbent patent extension — US7089207B1 structurally cannot price Tier 2/3 private counterparties, which is the wedge. Third, corridor-specific FX volatility — seven-day average maturity and fifty-two capital cycles per year bound duration risk. Fee floor three hundred basis points QUANT-locked — each loan is capital-positive in Phase 1 regardless of corridor noise.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Unit economics are robust" (name the failure modes)
- ❌ "Corridor noise is manageable" (vague)

**Bear-case pointer:** B-MKT-04, B-MKT-05

---

### Q-MKT-40 · Adversarial · Probing
**Question:** "EU AI Act Article 14 forces human review. Doesn't that wreck your latency story?"

**Gold-standard answer** (30-second spoken):
No — human review is routed only on C6 anomaly flag (EPG-18), not the default path. Ninety-four millisecond p99 latency applies to the standard two-step classification plus conditional offer. Median inference is forty-five milliseconds. Anomalies gate to PENDING_HUMAN_REVIEW — the exception path, not the hot path. EU AI Act Article 14 requires human oversight on high-risk outputs; LIP implements that oversight exactly where the Act requires it. The architecture ships the compliance artefact and preserves the latency SLO.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Human review is rare" (cite the routing mechanism)
- ❌ "We're fully automated" (false — EPG-18 routes anomalies)

**Bear-case pointer:** None

---

## Adversarial Tier (expansion) — Q-MKT-41 through Q-MKT-46

### Q-MKT-41 · Generalist VC · Adversarial
**Question:** "An incumbent with a real engineering org replicates your classification layer in six months. Then what?"

**Gold-standard answer** (30-second spoken):
Three barriers a six-month replication does not clear. First, the two-step classification plus conditional offer mechanism is patent-protected — a replica that receives pacs.002, classifies into a hold-type class causing pipeline short-circuit, and conditions an offer on that output infringes Independent Claim 1. Second, the Tier 2/3 private-counterparty extension requires Damodaran industry-beta and Altman Z' thin-file calibration on a corridor-level correspondent bank dataset — trade-secret calibration, eighteen to twenty-four months of data work at best. Third, the correspondent banking stack is a trust-and-integration market — a signed licence with MRFA, BIC-derived governing law, and three `hold_bridgeable` warranties is the moat, not raw code.

**Anchors this answer must touch:**
- correspondent banking stack
- Tier 2/3 private counterparties
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Nobody will replicate us" (complacent)
- ❌ "We'll out-execute them" (weak)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-42 · Fintech Specialist · Adversarial
**Question:** "A national regulator delays ISO 20022 adoption in a key corridor by a year. What happens to your entry?"

**Gold-standard answer** (30-second spoken):
SWIFT's coexistence period ended November 2025. Eleven thousand plus member institutions have migrated — structured pacs.002 is the operational standard across the correspondent banking stack. A national delay affects pace of adoption in that jurisdiction, not the fact of the data environment globally. Canada through RBCx, EU through AMLD6-aligned Tier 2 banks, PCT jurisdictions through PFD plus eighteen months — entry path does not depend on any single national regulator. Second force function, AMLD6 Article 10 investigatory hold infrastructure demand, is independent of ISO 20022 timing. Two independent drivers hedge the "why now".

**Anchors this answer must touch:**
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Delays don't matter" (acknowledge and bound)
- ❌ "We'll pivot corridors" (vague)

**Bear-case pointer:** B-MKT-03

---

### Q-MKT-43 · Bank-strategic · Adversarial
**Question:** "AMLD7 re-scores your Class B pool. Why should a bank sign a licence today?"

**Gold-standard answer** (30-second spoken):
Because the bank's regulatory exposure falls, whether or not AMLD7 widens. AMLD6 Article 10 criminal liability for legal persons is already in force — banks bridging a compliance-held payment face criminal exposure today. LIP's hold-type discriminator and the eight BLOCK-class permanent exclusions remove that exposure. If AMLD7 widens the list, LIP's gate expands in code — added codes do not break the architecture. Phase 1 fee-share economics do not require the top of the band. One Tier 1 bank at six million dollar ($6M) Year 3 conservative revenue does not depend on Class B width. The bank licences infrastructure, not speculative volume.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "AMLD7 is years away" (hand-wave)
- ❌ "Banks sign for the volume upside" (wrong — the compliance floor is the buy signal)

**Bear-case pointer:** B-MKT-04

---

### Q-MKT-44 · Adversarial · Adversarial
**Question:** "JPMorgan publishes a paper next quarter showing their internal bridge system now covers private counterparties. You're done."

**Gold-standard answer** (30-second spoken):
Publishing a paper is not shipping a licensed product to Tier 2/3 banks in the correspondent banking stack. US7089207B1 requires observable equity market data — extending to private counterparties requires a structurally new model. Claiming the extension in a paper is not the same as calibrating Damodaran industry-beta and Altman Z' on a corridor-level correspondent bank dataset, which is trade secret and eighteen to twenty-four months of data work. And the two-step classification plus conditional offer mechanism remains patent-protected — their paper does not shortcut Independent Claim 1. JPMorgan serves its own listed counterparties internally; licensing the Tier 2/3 stack is the layer they do not occupy.

**Anchors this answer must touch:**
- Tier 2/3 private counterparties
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "They'd have to rebuild their patent" (narrow — state the structural gap)
- ❌ "Papers aren't products" (true but weak — say why)

**Bear-case pointer:** B-MKT-05

---

### Q-MKT-45 · Generalist VC · Adversarial
**Question:** "Your entire 'why now' collapses if ISO 20022 fragments. Argue."

**Gold-standard answer** (30-second spoken):
SWIFT's coexistence period ended November 2025 — eleven thousand plus member institutions operate on structured pacs.002 today. Fragmentation means national phase-in differences, not a reversal. Banks that migrated are not unwinding. LIP reads the ISO 20022 message where it exists; fragmented corridors simply drop out of the addressable set until their national regulator lands. Second force function — AMLD6 Article 10 criminal liability for legal persons — is independent of messaging standard. Two drivers hedge "why now", and the ISO 20022 migration window door has opened, not closed.

**Anchors this answer must touch:**
- ISO 20022 migration window
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Fragmentation is unlikely" (unsupported)
- ❌ "Even fragmented it works" (cite the second force function)

**Bear-case pointer:** B-MKT-03

---

### Q-MKT-46 · Fintech Specialist · Adversarial
**Question:** "AMLD7 halves your Class B pool. Unit economics collapse."

**Gold-standard answer** (30-second spoken):
Unit economics are floor-anchored, not volume-anchored. Fee floor three hundred basis points QUANT-locked, warehouse eligibility floor eight hundred basis points. Phase 1 is a fee-share licence, no BPI balance sheet. If Class B halves, addressable volume drops from six hundred thirty billion dollars ($630B) toward three hundred to four hundred billion — fee pool shrinks proportionally, per-loan economics unchanged. Year 3 conservative revenue of six million dollars ($6.0M) is one-Tier-1-bank math; the fifteen-bank Year 10 base case of nine hundred twenty-one million dollars ($921M) has bank-count slack to absorb a Class B contraction. Floor holds, capture mechanism holds.

**Anchors this answer must touch:**
- bank-as-borrower, not balance-sheet lender
- correspondent banking stack

**Don't-say-this traps:**
- ❌ "Unit economics always survive" (vague)
- ❌ "AMLD7 is speculative" (hand-wave)

**Bear-case pointer:** B-MKT-04

---

## Crushing Tier (expansion) — Q-MKT-47 through Q-MKT-50

### Q-MKT-47 · Generalist VC · Crushing
**Question:** "Patent Independent Claim 1 gets narrowed and the RBC pilot slips to month twenty-four. How does the company survive both?"

**Gold-standard answer** (60-second spoken):
Name both and bound both. Claim 1 narrowing is covered in the Patent bear-case — B-PAT entries walk the design-around economics and the trade-secret moat layered underneath: Damodaran industry-beta and Altman Z' calibration, corridor-level correspondent bank dataset, eighteen to twenty-four months of data work for a copyist. Independent claims two through five and the D1–D13 dependents remain. RBC pilot slippage to month twenty-four is inside the seed runway envelope — two hundred thousand dollars per month over eighteen months was sized against the full bank onboarding cycle, not a best case. Parallel vectors — RBCx, Transaction Banking, AI Group — plus one non-RBC Tier 2 Canadian or European bank running as secondary keep the effective timeline at the fastest of four independent processes. First LOI triggers Series A, priced against deployed contracts, not projected flow. Compound downside scenario narrows the wedge; it does not break the company.

**Anchors this answer must touch:**
- correspondent banking stack
- Tier 2/3 private counterparties
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Both are unlikely" (address both head-on)
- ❌ "We'll bridge to Series A" (name the trigger, not a hope)

**Bear-case pointer:** B-MKT-02, B-MKT-05, B-MKT-07

---

### Q-MKT-48 · Fintech Specialist · Crushing
**Question:** "AMLD7 expands the BLOCK list, Class B halves, and you still have zero LOIs at month eighteen. What's the survival case?"

**Gold-standard answer** (60-second spoken):
Survival case is floor-anchored and compliance-sold. If AMLD7 expands BLOCK and Class B halves, addressable bridge volume drops from six hundred thirty billion dollars ($630B) toward three hundred to four hundred billion. Fee floor three hundred basis points QUANT-locked, per-loan economics unchanged, compliance value to the bank increases because the hold-type discriminator covers more codes. Zero LOIs at month eighteen is the B-MKT-01 scenario — first LOI is the trigger, the seed runway was sized against the full eighteen to twenty-four month onboarding cycle, and Series A is gated on signed pilot, not revenue. Three RBC vectors plus a non-RBC Tier 2 secondary run in parallel. If all four delay past runway, the company raises a priced bridge against the patent asset and the working demo proof point — two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points — not a pivot. Compound scenario forces a smaller raise; it does not force a shutdown.

**Anchors this answer must touch:**
- correspondent banking stack
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "Unlikely both hit at once" (address the compound head-on)
- ❌ "We'll find a solution" (name the bridge mechanism)

**Bear-case pointer:** B-MKT-01, B-MKT-04, META-02

---

### Q-MKT-49 · Bank-strategic · Crushing
**Question:** "If META-01 attaches, RBC is hostile, and you've lost the primary pilot corridor for the Canadian market. What's left?"

**Gold-standard answer** (60-second spoken):
META-01 is the single most consequential risk in the stack — covered in full in the Patent bear-case. Sequencing is deliberate. Conception and development predate the RBC start date of January 12, 2026 — repository commit history establishes the factual timeline. Resignation is executed before non-provisional filing; nothing in the application record creates an RBC nexus; the patent is not socialised inside RBC before resignation. Employment counsel is engaged. If counsel nonetheless determines the clause attaches, the pilot path shifts — one non-RBC Tier 2 Canadian bank, then EU Tier 2 banks under DORA and AMLD6, then UK, Singapore, and UAE through the PCT jurisdictions at PFD plus eighteen months. The correspondent banking stack does not depend on any single bank. Seed runway is sized against the full cycle; the Tier 2/3 private-counterparty wedge via Damodaran and Altman Z' does not require RBC. Bank-as-borrower structure is reproducible with any Tier 1 or Tier 2 licensee. The SAFE and cap table are gated on clean chain of title — clean of META-01.

**Anchors this answer must touch:**
- correspondent banking stack
- Tier 2/3 private counterparties
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "RBC would never assert" (complacent)
- ❌ "We pivot to another bank" (vague — name the secondary path)
- ❌ "The clause is standard" (dismissive)

**Bear-case pointer:** META-01, B-MKT-01

---

### Q-MKT-50 · Adversarial · Crushing
**Question:** "Everything goes wrong at once — META-01 attaches, AMLD7 expands, patent narrows, zero LOIs. Why shouldn't I pass?"

**Gold-standard answer** (60-second spoken):
Pass is a defensible call on this compound scenario — I will name why it is not the only call. META-01 is sequenced: resignation before non-provisional filing, conception predates January 12, 2026 start date, employment counsel engaged, patent not socialised inside RBC. If it attaches, the pilot vector shifts to non-RBC Tier 2 Canadian and EU banks. AMLD7 expansion shrinks addressable from six hundred thirty billion dollars ($630B) toward three to four hundred billion — fee floor three hundred basis points QUANT-locked, per-loan economics unchanged, compliance value to the bank increases. Patent narrowing is covered in the Patent bear-case — four remaining independent claims plus D1–D13 dependents, plus trade-secret calibration of Damodaran industry-beta and Altman Z' on the corridor-level correspondent bank dataset. Zero LOIs at month eighteen is the sized-for scenario — seed runway at two hundred thousand dollars per month was designed to reach first LOI, not first revenue dollar. The working demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points in real time — the proof point is live. Each risk is named, bounded, and has a resolution milestone. If you believe all four hit, pass is correct. If you believe the sequencing discipline holds on two of four, the six million dollar ($6.0M) Year 3 conservative case is the downside math and nine hundred twenty-one million dollars ($921M) Year 10 base is the upside.

**Anchors this answer must touch:**
- thirty-one point six trillion dollar market
- correspondent banking stack
- Tier 2/3 private counterparties
- bank-as-borrower, not balance-sheet lender

**Don't-say-this traps:**
- ❌ "All four won't hit at once" (address the compound directly)
- ❌ "We'll find a way" (name the downside math)
- ❌ "The upside justifies the risk" (concede what pass buys, then argue)

**Bear-case pointer:** META-01, META-02, B-MKT-01, B-MKT-04, B-MKT-05
