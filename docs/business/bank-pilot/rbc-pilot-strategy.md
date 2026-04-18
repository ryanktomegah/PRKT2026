# RBC Pilot Strategy — Internal Planning Document

> **CONFIDENTIAL — BPI internal use only. Do NOT share with RBC or any external party.**
> This document plans the approach for engaging RBC as BPI's first pilot bank customer.
> Execution gated on: (1) IP resolution, (2) patent filing, (3) clean separation from RBC employment.

---

## 1. RBC Organisational Map (Post Sept 2024 Reorg)

### Group Executive (reports to CEO Dave McKay)

| Name | Title | Relevance to LIP |
|------|-------|-------------------|
| **Derek Neldner** | CEO & Group Head, RBC Capital Markets | **HIGH** — Transaction Banking (institutional payments, clearing, custody) sits under Capital Markets |
| **Sean Amato-Gauci** | Group Head, Commercial Banking | **MEDIUM** — commercial clients experience payment failures that LIP would bridge |
| **Erica Nielsen** | Group Head, Personal Banking | **LOW** — retail-focused, not relevant to LIP |
| **Neil McLaughlin** | Group Head, Wealth Management | **LOW** — not payments-related |
| **Bruce Ross** | Head, AI Group (reports to CEO) | **HIGH** — newly formed Feb 2026, mandate to scale AI use cases, looking for wins |
| **Naim Kazmi** | Group Head, Technology & Operations | **MEDIUM** — infrastructure decisions, tech adoption |
| **Sid Paquette** | Head, RBCx (venture arm) | **HIGH** — purpose-built to engage with fintechs, invests in B2B payments |

### Transaction Banking (under Capital Markets)

This is the business unit that actually handles institutional cross-border payments — the operational domain where LIP creates value. Transaction Banking covers:
- Payments clearing and settlement (CAD, USD, cross-border)
- Cash management for corporate and institutional clients
- Correspondent banking relationships
- Trade finance

RBC is the **#1 clearer for CAD payments** and has won multiple awards for treasury and cash management innovation.

### RBC Borealis AI

- AI research institute with labs in **Toronto, Montreal, Waterloo, and Vancouver**
- 850+ AI developers and data engineers, 100+ PhDs
- Vancouver lab exists — relevant for local relationship building
- Ranked **#1 in Canada, #3 globally** for AI maturity (2025 Evident AI Index)
- Partnerships: MIT FinTechAI@CSAIL, Vector Institute, Cohere, Databricks
- Focus areas: AI explainability, bias mitigation, financial crime prevention, responsible AI

### RBCx (Venture Arm)

- Founded 2017, based in Toronto
- Invests in: **B2B payments, fintech, AI/ML, cybersecurity**
- Investment stages: seed through later-stage
- Key question from Sid Paquette: *"What's the problem, what's the size of the prize, and why are you best suited to solve it?"*
- Website: rbcx.com — has "Connect With An Advisor" intake process

---

## 2. Regulatory Landscape (Canada-Specific)

### OSFI (Office of the Superintendent of Financial Institutions)

RBC is a D-SIB (Domestic Systemically Important Bank) regulated by OSFI. Key guidelines relevant to LIP adoption:

| Guideline | Description | LIP Relevance |
|-----------|-------------|---------------|
| **E-23** (Model Risk Management) | Canada's equivalent of SR 11-7. Effective May 2027. Requires model inventory, validation, governance for all ML models. | LIP's C1/C2 models need E-23 compliant documentation. LIP pre-generates validation reports — this is a **selling point**. |
| **B-10** (Third-Party Risk Management) | Governs outsourcing and third-party technology adoption. | RBC's risk team will evaluate BPI as a third-party technology provider under B-10. |
| **B-13** (Technology and Cyber Risk) | Technology risk management for FRFIs. | LIP's zero-outbound architecture, HMAC auth, kill switch directly address B-13 concerns. |

**Strategic implication:** LIP's built-in regulatory compliance (E-23 model cards, DORA-compatible incident reporting, human oversight via kill switch) is a major differentiator. RBC's MRM (Model Risk Management) team will need to validate C1/C2 — having reports pre-built saves them months.

---

## 3. Entry Strategy — Three Doors

### Door 1: RBCx (Recommended Primary)

**Why this door:**
- Purpose-built to receive fintech pitches — they have a structured intake process
- Invests in B2B payments and fintech — LIP is squarely in scope
- Can make warm introductions to Transaction Banking internally
- Potential for RBCx investment + RBC as pilot customer (ideal outcome)
- Sid Paquette and team evaluate hundreds of startups — they know how to assess

**How to approach:**
1. Apply through rbcx.com "Connect With An Advisor"
2. Prepare a pitch deck tailored to Sid's three questions (see Section 5)
3. Request a meeting, not an investment — frame it as "strategic partnership for pilot deployment"
4. RBCx will route you to the right internal business unit if interested

**Risk:** RBCx may view LIP as too early-stage (no revenue, no customers yet). Counter: the technology is production-ready (1472 tests passing, containerised, Helm-deployable), and you're offering RBC first-mover advantage.

### Door 2: Transaction Banking (Direct)

**Why this door:**
- The actual P&L owner who would benefit from LIP
- They experience payment failures daily — they know the problem intimately
- Decision-makers here can champion a pilot internally

**How to approach:**
1. Identify VP-level contacts in Transaction Banking (LinkedIn research)
2. Cold outreach with a one-page value proposition (not a pitch deck — too much for a cold email)
3. Frame it as: "I've built a platform that turns your payment failure costs into revenue"
4. Request a 30-minute technical demo

**Risk:** Cold outreach to a bank's institutional business unit has low response rates. This door works better as a warm introduction via RBCx or Borealis.

### Door 3: AI Group (Bruce Ross)

**Why this door:**
- Newly formed (Feb 2026), actively looking for AI use cases to prove value
- Reports directly to CEO — can bypass business unit politics
- LIP is an AI-native platform (ML classification, PD models, anomaly detection)
- RBC wants $1B in AI-generated enterprise value by 2027 — LIP is a tangible use case

**How to approach:**
1. Borealis AI Vancouver lab is local — attend events, network
2. Frame LIP as an AI success story: "7-component ML pipeline for institutional payments"
3. Emphasise the E-23 compliance angle — AI Group cares about responsible AI
4. Bruce Ross's mandate is to find and scale AI opportunities — LIP is exactly that

**Risk:** AI Group may not have P&L authority to approve a pilot — they'd need to convince Transaction Banking. But they can champion internally.

---

## 4. Recommended Sequence

```
Phase 1 — Groundwork (while still employed / during gap period)
  ├── Resolve IP (lawyer consultation)
  ├── File provisional patent
  ├── Clean-room re-implementation (new repo)
  ├── Incorporate BPI (if not already done)
  └── Build pitch deck and one-pager

Phase 2 — Initial Contact (after clean separation)
  ├── RBCx application via website
  ├── LinkedIn research for Transaction Banking VPs
  ├── Attend Borealis AI Vancouver events
  └── Prepare live demo environment (GCP deployment)

Phase 3 — First Meeting
  ├── RBCx intro meeting (pitch deck, live demo)
  ├── Goal: get routed to Transaction Banking for technical evaluation
  └── Leave behind: API reference, integration guide

Phase 4 — Technical Evaluation
  ├── Demo walkthrough with Transaction Banking technical team
  ├── Integration guide review with their engineering
  ├── E-23 compliance review with their MRM team
  ├── Legal prerequisites discussion with their legal counsel
  └── Goal: LOI for pilot deployment

Phase 5 — Pilot Deployment
  ├── Deploy LIP to RBC's infrastructure (K8s)
  ├── Known entity registration for RBC's counterparties
  ├── Bridgeability Certification API integration
  ├── 90-day pilot with Class A payments only
  └── Goal: demonstrate revenue generation, expand to Phase 2
```

---

## 5. Pitch Deck Structure (For RBCx / Transaction Banking)

Answering Sid Paquette's three questions:

### Slide 1-2: The Problem

**"Cross-border payment failures cost banks revenue and customer relationships."**

- X% of cross-border payments experience at least one rejection/return
- When a payment fails, the beneficiary doesn't get paid on time
- Banks currently eat the cost — no revenue from the failure event
- Technical failures (wrong account number, format errors) resolve in 1-3 days but cause real harm in the meantime

### Slide 3-4: The Size of the Prize

**"Bridge lending on payment failures is a new revenue category."**

- Corridor economics example: $1M EUR→USD payment, Class A failure, 300 bps fee = $246 per loan
- At scale: 3,000 bridgeable failures/month × $200 avg fee = $600K/month = $7.2M/year (per bank)
- RBC Phase 1 share (85%): $6.1M/year
- BPI share (30% royalty): $2.2M/year
- Market size: top 20 global banks × $5-10M/year each = $100-200M TAM

### Slide 5-6: Why BPI

**"We've built the full stack — classification, credit, execution, compliance."**

- 7-component ML pipeline: failure classification → credit scoring → bridge loan execution
- Production-ready: 1,472 tests passing, containerised, Helm-deployable
- Regulatory compliance built-in: E-23/SR 11-7 model cards, incident reporting, human oversight
- Patent-pending two-step classification mechanism
- Zero balance sheet risk for BPI in Phase 1 (technology royalty model)

### Slide 7: The Ask

**"We're looking for a pilot bank partner. RBC is our first choice."**

- 90-day pilot on Class A payments (technical errors — lowest risk)
- BPI deploys LIP on RBC's infrastructure (zero data leaves RBC's network)
- RBC retains 85% of bridge loan fee revenue
- Regulatory documentation pre-built (E-23, DORA, EU AI Act)

### Slide 8: Architecture (For Technical Audience)

- Pipeline diagram: C1→C4∥C6→C2→C7→C3
- ISO 20022 native (pacs.002/pacs.008)
- Zero-outbound C7 container
- Kill switch for human oversight
- HMAC-SHA256 authenticated API

---

## 6. Framing Your RBC Background

You previously worked at RBC. This is an advantage but must be framed carefully.

**What to say:**
- "I have experience in Canadian banking operations, including at RBC"
- "I understand the payment failure problem from the operational side"
- "After leaving RBC, I founded BPI to build a solution"

**What NOT to say:**
- "I built this while working at RBC" (triggers IP questions)
- "I used RBC data/systems to develop this" (never true, never imply)
- Any reference to specific RBC customers, volumes, or internal systems
- Any confidential information learned during employment

**If asked directly "Did you build this while at RBC?":**
- "BPI was founded after I left RBC. The platform was developed independently, on my own time and equipment, with no connection to my role or RBC's resources."

---

## 7. Competitive Positioning

### Why RBC Should Move First

1. **First-mover advantage**: The first Big 5 bank to deploy LIP captures the most attractive corridors before competitors
2. **AI leadership narrative**: RBC is #1 in Canada for AI maturity — LIP is an AI-native payments platform that reinforces this positioning
3. **Revenue at zero R&D cost**: Phase 1 is a technology license — RBC pays nothing upfront, earns 85% of fee revenue
4. **E-23 ready**: OSFI E-23 takes effect May 2027 — LIP comes with pre-built model validation, giving RBC a head start on compliance

### Potential Objections and Responses

| Objection | Response |
|-----------|----------|
| "We can build this internally" | "You could, but it would take 18-24 months and a dedicated ML team. LIP is production-ready today. Phase 1 royalty model means you pay nothing until it generates revenue." |
| "What about regulatory risk?" | "LIP comes with E-23 model cards, DORA incident reporting, and a human oversight kill switch. Your MRM team can validate C1/C2 using our pre-built reports. We've also built the Bridgeability Certification API structure so your compliance system retains full control." |
| "We don't want a third-party on our payment infrastructure" | "LIP runs entirely within your infrastructure — zero outbound from the execution agent. Your network policies apply. BPI accesses only aggregate admin metrics via authenticated API." |
| "What if the ML models are wrong?" | "C1 operates at a calibrated threshold (F-beta optimised). False positives mean we don't offer a loan — no financial exposure. False negatives mean we miss a lending opportunity — lost revenue, not lost capital. The kill switch lets you halt everything instantly." |
| "Our legal team won't approve this in 90 days" | "We've pre-drafted the three warranty clauses and the MRFA structure. Your legal team reviews, they don't draft from scratch. The Bridgeability Certification API follows FATF R.13 correspondent KYC cert structure — your compliance team will recognise the pattern." |

---

## 8. Timeline

| Milestone | Target | Dependencies |
|-----------|--------|-------------|
| IP lawyer consultation | Week of departure | Find BC IP/employment lawyer |
| Resign from RBC | When next job secured | Job search |
| File provisional patent | During gap period | Lawyer sign-off |
| Clean-room re-implementation | Gap period (2-4 weeks) | Patent filed |
| Incorporate BPI (if needed) | Gap period | — |
| Deploy demo to GCP | Gap period | GCP setup |
| Pitch deck complete | Before first RBCx contact | — |
| RBCx initial contact | 1 week after separation complete | Pitch deck ready |
| First meeting | 2-4 weeks after contact | RBCx scheduling |
| Technical demo | 4-8 weeks after first meeting | Demo environment live |
| LOI negotiation | 8-16 weeks after technical demo | Legal review |
| Pilot deployment | Within 30 days of LOI | Integration work |

---

## 9. Key Contacts to Research (LinkedIn)

| Target | Why | How to Find |
|--------|-----|-------------|
| VP-level in Transaction Banking | Business unit owner for institutional payments | LinkedIn: "RBC Transaction Banking Vice President" |
| Sid Paquette (Head of RBCx) | Fintech intake, investment decisions | rbcx.com, LinkedIn |
| Bruce Ross (Head of AI Group) | AI use case champion, reports to CEO | LinkedIn, Borealis AI events |
| Borealis AI Vancouver team | Local AI research, potential technical champions | Borealis events in Vancouver, LinkedIn |
| RBC MRM (Model Risk Management) | Will evaluate C1/C2 models under E-23 | LinkedIn: "RBC Model Risk Management" |
| RBC Legal — Commercial Banking | Will review MRFA and warranty clauses | Via RBCx introduction (don't cold-contact legal) |
