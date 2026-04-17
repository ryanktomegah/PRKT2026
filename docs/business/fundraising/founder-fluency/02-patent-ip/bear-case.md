# Patent / IP — Bear Case

**How to read this file:** Each entry names a real weakness, writes an honest structured answer, and flags the don't-say traps. Master Index ranks entries by `(likelihood of being asked) × (severity if fumbled)`. META-01 is the single most important entry in the entire Playbook. Spend 50% of drill time on META-01 and B-PAT-01.

## Master Index

| Rank | ID | Weakness | Resolution event |
|---|---|---|---|
| 1 | META-01 | RBC IP clause could claim ownership | Employment counsel resolution + documented timeline of invention |
| 2 | B-PAT-01 | JPMorgan US7089207B1 prior art overlap | Non-provisional filing grants novel claims |
| 3 | B-PAT-02 | Provisional not yet non-provisional | Non-provisional filed |
| 4 | B-PAT-03 | Provisional deadline approaching | Same as above |
| 5 | B-PAT-04 | Examiner may narrow on two-step classification | Granted claim language |
| 6 | B-PAT-05 | Alice §101 software-patent risk | Claims drafted with concrete technical effect |
| 7 | B-PAT-06 | Competitive patents in pipeline we can't see | FTO (freedom-to-operate) opinion from counsel |

---

## META-01 — RBC IP clause could claim ownership
**(Master entry — cross-referenced from all volumes; governs the founder-employment IP question; single most important entry in the entire Playbook)**

### Honest Truth

The founder is a current RBC employee. RBC's offer letter contains a broad IP assignment clause — the kind that purports to cover anything conceived or reduced to practice during the period of employment. Bridgepoint Intelligence Inc. (BPI) cannot have a clean chain of title — and therefore cannot issue SAFEs, close investment, or enforce patent claims — if there is unresolved ambiguity about whether RBC holds a colourable claim to the invention. This is the hardest fact in the company's legal profile. It is not going away by being ignored, minimised, or deferred. It must be sequenced correctly.

### Structured Answer

1. **Acknowledge plainly.** "I'm a current RBC employee. Their offer letter has an IP assignment clause. This has to be addressed before the non-provisional filing milestone. I know it. Counsel knows it. It's the first thing on the legal critical path."

2. **Documented timeline — conception predates employment.** The invention was conceived and the development record was established before the RBC start date of January 12, 2026. Repository commit history, the provisional priority date, and an independent development record document the timeline factually. Patent ownership in Canada and the United States attaches at the moment of conception — not at filing, not at employment start. A documented pre-employment timeline is the primary factual defence against an IP assignment clause that applies only to work conceived "during employment."

3. **Resolution path — Angle 6 sequencing.** The strategy is not "hope RBC doesn't notice." The strategy is named and sequenced: Angle 6. The founder resigns from RBC. The non-provisional application is then filed by the founder as an independent inventor — outside the employment relationship, with no RBC nexus. Employment counsel has been engaged specifically on this sequencing: the memo on file documents the conception-date evidence, the clause analysis, and the resignation-before-filing requirement. Nothing in the patent application is socialised internally at RBC before resignation. The application record creates no RBC nexus.

4. **Investor-protection mechanism — SAFE and cap table gated.** No investor takes ownership risk. The SAFE and cap table are gated on resolution of the employment IP question and clean chain of title. The sequencing is: (a) employment counsel memo on file, (b) founder resigns from RBC, (c) non-provisional filed with founder as sole independent inventor. Capital does not close against an ambiguous chain of title. That gate is not a courtesy — it is the mechanism that makes the investment clean.

### Don't-say-this

- ❌ "It's fine, the clause doesn't apply." — This shuts down diligence on the hardest question. Any investor who knows employment IP law will hear this and conclude the founder hasn't done the work.
- ❌ "RBC doesn't know about LIP." — This implies that obscurity is the defence strategy. It is not. Obscurity is temporary and legally irrelevant to an IP assignment clause.
- ❌ "I'll resign when we close a round." — This inverts the required sequence. Resignation precedes the non-provisional filing. Filing precedes the close. "I'll resign at close" means the patent is filed while still an employee — which is exactly the scenario that triggers the assignment clause.
- ❌ Any minimising language: "just a standard clause," "boilerplate," "all employment contracts say this." These phrases signal the founder has not read the clause carefully. A sophisticated investor has read employment IP clauses. They know the difference between a narrow clause and a broad one. The RBC clause is broad. Own that.

### Resolution Milestone

Three events, in strict sequence:

**(a)** Employment counsel memo on file — documents the conception-date evidence, the clause analysis, and the specific steps required for clean separation.

**(b)** Founder resigns from RBC — ends the employment relationship that the IP assignment clause governs.

**(c)** Non-provisional application filed with the founder as sole independent inventor — establishes enforceable claims under a clean chain of title, with no RBC employment nexus in the application record.

No investor capital closes until all three events are complete and documented.

### Investor Intuition Target

"They have the hardest conversation planned. They're not pretending it isn't there. The resolution path is concrete and sequenced — not 'we'll figure it out when we need to.' The gate on the SAFE is the mechanism that protects us."

### Drill Linkage

- **Q-PAT-21** (Crushing-Generalist — "Your employer RBC has an IP clause. What happens when they claim ownership?") — this is the direct question; drill this entry until the structured answer is recitable under pressure.
- **Q-PAT-12** (Probing-Fintech — "What prevents an incumbent from designing around it?") — the employment IP question surfaces here because a clean chain of title is a prerequisite for enforcement.
- **Q-TECH-17** (Adversarial-Generalist — "Non-technical founder, current RBC employee, no production traffic. Convince me this isn't a pipe dream.") — cross-referenced from Technical volume; RBC employment is one of the three simultaneous challenges in that question.
- **Q-TECH-21** (Crushing-Generalist — "Walk me through what happens if RBC claims ownership of the IP under your employment clause.") — cross-referenced from Technical volume; the answer tracks to this entry exactly.

All four confirmed in respective drill.md files.

### Cross-Volume References

- **Referenced in:** `01-technical-depth/bear-case.md` (cross-volume pointer block at top of Master Index section) and `03-market-timing/bear-case.md` (cross-volume pointer block — pilot-path implications: if RBC becomes the counterparty, a conflict-of-interest analysis is required).
- **Master entry location:** this file (`02-patent-ip/bear-case.md`).

---

## B-PAT-01 — JPMorgan US7089207B1 prior art overlap

### Honest Truth

JPMorgan Chase US7089207B1 is the closest prior-art reference in the payment-failure bridge-lending space. It was cited in the prior art search. Any investor who has done basic patent diligence will find it. The question is not whether it exists — it does — but whether it teaches all five elements of LIP's Independent Claim 1. It does not.

### Structured Answer

1. **Acknowledge the prior art.** "JPMorgan US7089207B1 is the closest prior-art reference in the space. We found it. It's in our prior-art analysis. The question is what it covers and what it leaves open."

2. **Three distinctions, each independently claimable.** First, coverage: US7089207B1 requires observable equity market prices as mandatory inputs — it explicitly covers listed companies only. The Tier 2/3 private-counterparty extension via Damodaran industry-beta and Altman Z' thin-file scoring covers the full counterparty data spectrum, including private companies with no observable equity price. JPMorgan's patent structurally cannot cover this population. Second, trigger: US7089207B1 is a standalone pricing tool. It does not receive ISO 20022 pacs.002 rejection messages. It does not generate loan offers in response to payment failure events. There is no payment-network telemetry connection in the prior art. Third, the conditional gate: US7089207B1 has no failure taxonomy, no hold-type classification, and no pipeline short-circuit. The two-step classification + conditional offer mechanism — the trigger, the taxonomy evaluation, and the conditional gate — is entirely absent from US7089207B1.

3. **Combination attack also fails.** US7089207B1 combined with Bottomline Technologies US11532040B2 — the §103 obviousness combination — still does not teach all five elements of Independent Claim 1. Bottomline covers aggregate portfolio forecasting; it does not cover individual UETR-keyed payment events or the classification gate mechanism.

4. **Resolution.** Non-provisional filing grants novel claims on the two-step classification + conditional offer mechanism and the Tier 2/3 private-counterparty extension. Those claims are novel over the prior art individually and in combination.

### Don't-say-this

- ❌ "JPMorgan's patent is old — technology has completely changed." Age is irrelevant to novelty analysis. The prior art is analysed for what it teaches, not when it was filed.
- ❌ "We use ML and they don't — that's the difference." ML architecture is not the claim. The mechanism is the claim. Don't anchor the novelty argument on implementation choices that can be exchanged.

### Resolution Milestone

Non-provisional application filed; examiner's novelty analysis confirms that US7089207B1 does not anticipate Independent Claim 1, and the §103 combination of US7089207B1 + US11532040B2 does not render it obvious.

### Investor Intuition Target

"They've done the prior-art work. They know exactly what JPMorgan covers and what it doesn't. The novelty argument is clean and specific."

### Drill Linkage

- **Q-PAT-09** (Probing-Generalist — "How is this different from JPMorgan's patent?") — confirmed in drill.md.
- **Q-PAT-18** (Adversarial-Fintech — "JPMorgan's patent predates yours and covers the category. You're a continuation, not a novel claim.") — confirmed in drill.md.

---

## B-PAT-02 — Provisional not yet non-provisional

### Honest Truth

The provisional application (LIP P1) establishes the priority date and protects the five patent families for a twelve-month window. It confers no enforceable claims. Until the non-provisional utility application (LIP P2) is filed and examined, LIP has no patent rights an infringer is required to respect. This is a pre-non-provisional state.

### Structured Answer

1. **Acknowledge the state.** "We are at provisional stage. The provisional establishes the priority date for all subsequent filings. Enforceable claims come with the non-provisional at PFD + 12 months."

2. **Reframe: provisional is not weakness, it is structure.** The provisional filing date (PFD) establishes priority against any reference published or filed after PFD. Every continuation and PCT filing in the five-patent-family architecture carries PFD forward at no incremental cost. The non-provisional converts the provisional protection into five independent claims and thirteen dependent claims — enforceable against the world.

3. **What the non-provisional resolves.** The non-provisional filing milestone at PFD + 12 months is the gate. At that date: LIP P2 is filed, prosecution begins, and the claims become public. Licensing conversations in Phase 1 run on the provisional priority date — the bank's diligence question is whether the claims are novel, not whether they are yet granted. The grant strengthens Phase 2 and Phase 3 renegotiation posture materially.

4. **Timeline is calendared.** Patent counsel is engaged. Three checkpoints: provisional files (PFD established), prosecution strategy complete at PFD + 8 months, non-provisional filed at PFD + 11 months with one-month buffer. The PFD + 18-month PCT deadline across five jurisdictions — United States, Canada, European Patent Office, Singapore, and UAE — is separately calendared.

### Don't-say-this

- ❌ "We're basically protected — the provisional covers us." A provisional confers no enforceable claims. Don't overstate its protection.
- ❌ "We'll file the non-provisional when the time is right." The deadline is absolute, not a timing choice.

### Resolution Milestone

Non-provisional utility application (LIP P2) filed by PFD + 12 months; five independent claims and D1–D13 dependent claims enter prosecution.

### Investor Intuition Target

"They understand the difference between provisional protection and enforceable claims. The timeline is calendared. This isn't wishful thinking."

### Drill Linkage

- **Q-PAT-04** (Warm-Fintech — "What's the filing timeline?") — confirmed in drill.md.
- **Q-PAT-23** (Crushing-Bank-strategic — "You filed a provisional. Non-provisional deadline is PFD + 12 months. Missing it means public disclosure wipes your rights. What's your plan?") — confirmed in drill.md.

---

## B-PAT-03 — Provisional deadline approaching

### Honest Truth

The twelve-month provisional window has a hard calendar end: PFD + 12 months. Missing that deadline is not recoverable. Public disclosure after that date wipes patent rights in every jurisdiction that requires novelty at filing. There is no grace period in the European Patent Office. There is a limited grace period in the United States (12 months from first public disclosure), but the PCT filing window at PFD + 18 months is also absolute across the five target jurisdictions. These are not soft targets. Missing either deadline is a total-loss event for the relevant claims.

### Structured Answer

1. **Acknowledge the risk for what it is.** "The PFD + 12-month deadline is the hardest legal deadline in the company's calendar. Missing it destroys the priority date and, in most jurisdictions, the claims. We treat it as a hard stop."

2. **Operational, not philosophical.** This is a calendared-risk problem with named milestones, not a strategic uncertainty. The counsel engagement timeline, the prosecution strategy review checkpoint, and the non-provisional filing date are all calendared. The non-provisional files at PFD + 11 months — one month before the hard deadline — to create buffer for any counsel review cycle.

3. **What the milestone sequence looks like.** PFD established at provisional filing. Prosecution strategy review complete at PFD + 8 months. Non-provisional LIP P2 filed at PFD + 11 months. PCT filing across five jurisdictions by PFD + 18 months. The total patent portfolio investment — utility, PCT, prior art search, and two initial continuations — comes in under two hundred thousand dollars ($200,000). This is a calendared capital allocation, not a vague future commitment.

4. **Named milestone owner.** Patent counsel is the named owner of both deadlines. These are not tracked on an internal to-do list. They are in counsel's docket with hard-stop billing triggers.

### Don't-say-this

- ❌ "We'll file well before the deadline — it's on our roadmap." Roadmaps imply flexibility. This deadline has none.
- ❌ "Our attorneys are tracking it." That delegates accountability without evidence of a sequenced plan. Name the milestone dates.

### Resolution Milestone

Non-provisional filed by PFD + 11 months (one-month buffer before the PFD + 12-month absolute deadline). PCT filing by PFD + 18 months across United States, Canada, European Patent Office, Singapore, and UAE.

### Investor Intuition Target

"The deadline is real and they're running ahead of it, not against it. Counsel owns it. The buffer is built in. This is operational discipline, not luck."

### Drill Linkage

- **Q-PAT-23** (Crushing-Bank-strategic — "You filed a provisional. Non-provisional deadline is PFD + 12 months. Missing it means public disclosure wipes your rights. What's your plan?") — confirmed in drill.md. This question is the direct test of this entry.

---

## B-PAT-04 — Examiner may narrow on two-step classification

### Honest Truth

During prosecution, the examiner can require the applicant to narrow claims to distinguish them from prior art. If Independent Claim 1 is narrowed — for example, to enumerate specific rejection codes rather than covering the classification gate mechanism broadly — the scope of protection shrinks. A narrow claim may still be enforceable, but it is easier to design around.

### Structured Answer

1. **Acknowledge the scenario.** "Examiner narrowing is a real scenario in prosecution. Independent Claim 1 could be narrowed. We've built the prosecution strategy around it."

2. **The five-patent-family architecture is the answer.** The five-patent-family structure is specifically designed for this scenario. Every narrowing amendment to Independent Claim 1 must be evaluated for its effect on the continuation family before acceptance — elements narrowed in the parent cannot be recaptured in a continuation without losing the priority date. That evaluation is a hard protocol, not a post-hoc consideration. Family 1, Independent Claim 5 — the auto-repayment loop — is the terminal fallback within the core family. Any competitor building an automated payment bridging product must collect repayment somehow. If they use payment-network confirmation data to do so automatically, they infringe Claim 5 regardless of how they have designed around Claims 1 through 4.

3. **What "acceptable narrowing" looks like.** Acceptable so long as: (a) the two-step mechanism — the classification gate and the conditional offer output — survives in some form, and (b) the Tier 2/3 private-counterparty extension under Dependent Claim D5 survives independently. Both of these elements are novel over the prior art individually. A narrowing that preserves both still produces a licensable patent.

4. **Pilot-licensing posture is durable.** Even a claim narrowed to a specific implementation preserves the pilot-licensing posture. A bank licensing the technology pays for the specific two-step classification + conditional offer mechanism as implemented, not for theoretical sweep. The narrowing affects enforcement breadth, not the licensing economics of Phase 1.

### Don't-say-this

- ❌ "We'll cross that bridge when we get there." The prosecution strategy must anticipate narrowing before filing, not respond to it reactively.
- ❌ "Our patent attorney is handling the prosecution strategy." Delegate accountability with specifics. Name the protocol, not the person.

### Resolution Milestone

Granted claim language — acceptable as long as the two-step classification + conditional offer mechanism and the Tier 2/3 private-counterparty extension survive in some independently claimable form.

### Investor Intuition Target

"Narrowing was anticipated in the filing strategy. The portfolio holds value even in the narrow scenario. They know what's acceptable and what isn't."

### Drill Linkage

- **Q-PAT-10** (Probing-Generalist — "What if the examiner narrows the claims?") — confirmed in drill.md.
- **Q-PAT-22** (Crushing-Fintech — "The examiner narrows to block-code-list infringement only. Your patent becomes worthless. What's the fallback?") — confirmed in drill.md.

---

## B-PAT-05 — Alice §101 software-patent risk

### Honest Truth

Alice v. CLS Bank International (2014) raised the bar for software patent eligibility under 35 U.S.C. §101. The USPTO rejection rate for fintech software patents under Alice runs approximately seventy percent (70%), per the framing in Q-PAT-24. A claim directed to an abstract financial result — "bridging failed payments" — without specific technical anchoring fails §101. This is a real risk, not a theoretical one. The claim structure must do the work of §101 defence from the first draft, not from the response to a rejection.

### Structured Answer

1. **Acknowledge the base rate.** "Alice §101 rejection rates for fintech software patents run around seventy percent (70%). That base rate is real. The question is which population LIP's claims fall into — the 70% or the 30%."

2. **Two Federal Circuit affirmative eligibility decisions anchor the §101 position.** First, *Enfish v. Microsoft* (2016): claims are eligible when they improve the functioning of computer or network infrastructure itself — not when they produce a financial result using a computer. LIP's pipeline latency — median under forty-five milliseconds (45ms), p99 under ninety-four milliseconds (94ms) — is a technical performance specification for the real-time payment-network monitoring pipeline. That is a technical infrastructure improvement, not an abstract financial result dressed in technical language. Second, *McRO v. Bandai Namco* (2016): claims are eligible when they impose specific technological rules on how a result is achieved. LIP's classification gate mechanism, UETR-keyed settlement correlation across all pipeline stages, and BIC-derived governing-law logic are specific technological constraints on how the conditional offer is generated — not functional end-state claims.

3. **Alice-clean anchoring is built in from draft one.** The §101 defence is not a response to a rejection. It is the structure of the claims from the first draft. The two-step classification + conditional offer mechanism covers a specific technical gate on a specific ISO 20022 message type. The claim is anchored to payment-network processing infrastructure. *Enfish* and *McRO* are the controlling Federal Circuit precedents that hold this category of claim eligible. Counsel confirms anchoring before the non-provisional files.

4. **What the 30% approval rate is made of.** The 70% rejection rate concentrates on claims directed to abstract financial results with only functional language. Claims anchored to Federal Circuit affirmative eligibility precedents — with specific technical constraints and measurable technical performance specifications — are in the 30% approval population. That is the structural distinction, not wishful thinking.

### Don't-say-this

- ❌ "Alice is a risk but most fintech patents survive it." The base rate says most do not. Don't contradict data with assertion.
- ❌ "Our lawyers say we're in good shape." That delegates the §101 analysis without demonstrating it. Name the anchoring cases and the specific claim structure.

### Resolution Milestone

Claims filed with concrete technical effect language — latency SLO specifications, UETR-keyed correlation, BIC-derived governing-law logic — anchored to *Enfish* and *McRO*. Counsel confirms §101 eligibility argument before non-provisional filing milestone.

### Investor Intuition Target

"They know the case law. The §101 defence is built into the claim structure, not argued in response to a rejection. That's what Alice-clean means."

### Drill Linkage

- **Q-PAT-15** (Probing-Adversarial — "Alice §101 — why does this survive?") — confirmed in drill.md.
- **Q-PAT-24** (Crushing-Adversarial — "Alice §101 rejection rate for fintech software patents is about 70%. Statistical base-rate says you lose. Argue.") — confirmed in drill.md.

---

## B-PAT-06 — Competitive patents in pipeline we can't see

### Honest Truth

Patent applications are not published for eighteen months after filing. A competitor could have filed a patent application in this space in the last eighteen months and BPI cannot see it. The prior-art search covers granted patents and published applications — it does not cover pending applications in the secrecy window. This is a structural limitation of the patent landscape at any given date, not a failure of diligence.

### Structured Answer

1. **Acknowledge the structural limitation.** "We cannot see applications filed in the last eighteen months. That is a structural limitation of patent diligence, not a failure to search. Anyone doing a freedom-to-operate analysis faces the same window."

2. **Freedom-to-operate opinion is the standard response.** An FTO (freedom-to-operate) opinion from patent counsel evaluates the landscape of granted patents and published applications that could affect LIP's commercial operations. That analysis is standard pre-pilot diligence for any technology company entering a licensing relationship with a bank. The FTO opinion identifies claims that could be asserted against BPI and quantifies the design-around cost or licensing exposure.

3. **Mitigation through claim structure.** The two-step classification + conditional offer mechanism and the Tier 2/3 private-counterparty extension via Damodaran industry-beta and Altman Z' are structurally novel combinations. A competitor who filed a patent in this space after LIP's provisional priority date cannot assert priority over LIP's claims. A competitor who filed before LIP's PFD and whose application is still in the secrecy window is the real risk — the FTO opinion and the BPI claim structure together reduce, but cannot eliminate, that risk.

4. **FTO is on file before pilot launch.** The FTO opinion is calendared to complete before the first pilot bank's legal review begins. A bank's IP counsel will ask for it. Having it on file before they ask is the right sequencing.

### Don't-say-this

- ❌ "We've done a thorough patent search and nothing came up." A search of published patents and applications cannot find unpublished applications. Don't overstate the completeness of the search.
- ❌ "The big players are too slow to file in this space." Assertion without evidence, and irrelevant — a well-resourced filer can file quickly.

### Resolution Milestone

FTO opinion from patent counsel completed and on file before pilot launch; known published prior art landscape documented; unpublished application risk acknowledged and quantified.

### Investor Intuition Target

"They know the secrecy window is real and they've structured the standard diligence correctly. The FTO opinion is calendared before it becomes an issue."

### Drill Linkage

- **Q-PAT-06** (Warm-Bank-strategic — "Does a licensee need the patent to be granted?") — confirmed in drill.md. This question surfaces the FTO and landscape question from the licensee side.
