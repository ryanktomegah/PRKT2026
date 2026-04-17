# Technical Depth — Drill

Question bank organised by investor persona × difficulty. Cover the Gold-standard block when self-drilling.

**Canonical anchors** (every answer must touch at least one):
1. **two-step classification + conditional offer mechanism** — The core patent claim: C1 classifies the failure type first; C2 prices risk only if that classification clears; no offer issues without the gate passing.
2. **ninety-four millisecond SLO** — End-to-end latency from pacs.002 arrival to loan offer output, QUANT-locked at p99.
3. **three-hundred basis point fee floor** — Minimum annualised bridge loan fee, QUANT-locked; every loan that executes is capital-positive.
4. **ISO 20022 migration window** — SWIFT's structured rejection codes made real-time failure classification tractable for the first time.
5. **synthetic-first build** — The full pipeline was validated against two million synthetic records before any live bank traffic, so the system arrives at a pilot ready — not asking the bank to be a beta tester.

**Question IDs:** `Q-TECH-NN` — append-only. Never renumber.

---

## Warm Tier — Q-TECH-01 through Q-TECH-08

### Q-TECH-01 · Generalist VC · Warm
**Question:** "Give me the one-minute overview of what you've built."

**Gold-standard answer** (30-second spoken):
LIP detects a failed cross-border SWIFT payment, classifies why it failed in real time, and conditionally offers the originating bank a bridge loan — within the ninety-four millisecond SLO at p99. The core invention: C1 classifies the rejection code, C2 prices risk only if that classification clears — the two-step classification + conditional offer mechanism. Live demo: a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge priced at 706 bps on a synthetic pacs.002.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "It's basically an AI-powered bridge loan platform"
- ❌ "We detect payment failures and offer credit"

**Bear-case pointer:** None

---

### Q-TECH-02 · Generalist VC · Warm
**Question:** "Why did you build this? What's the insight that made you go build it?"

**Gold-standard answer** (30-second spoken):
The ISO 20022 migration window is the insight. Every failed cross-border payment now carries a structured rejection code — enough signal to classify failure type and price a bridge in machine time. Before ISO 20022, a lender couldn't distinguish a routing error from a sanctions hold fast enough to act. That window made the two-step classification + conditional offer mechanism viable and patentable. One hundred eighteen point five billion dollars ($118.5B) per year is the market it unlocks.

**Anchors this answer must touch:**
- ISO 20022 migration window
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "I noticed banks had a pain point with failed payments"
- ❌ "I wanted to solve liquidity for banks"

**Bear-case pointer:** None

---

### Q-TECH-03 · Fintech Specialist · Warm
**Question:** "What's the wedge — why pacs.002 specifically?"

**Gold-standard answer** (30-second spoken):
pacs.002 is the ISO 20022 rejection message — it arrives before treasury opens an inbox and now carries a structured rejection code. That code, combined with corridor-level graph signals, lets C1 classify failure type in real time. No prior system built a classification layer on pacs.002. That's the wedge: one standardised message, ubiquitous across eleven thousand-plus (11,000+) SWIFT member institutions, is the trigger event the two-step classification + conditional offer mechanism runs on.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ISO 20022 migration window

**Don't-say-this traps:**
- ❌ "pacs.002 is the rejection message that tells you a payment failed"
- ❌ "We intercept SWIFT messages and do analysis on them"

**Bear-case pointer:** None

---

### Q-TECH-04 · Fintech Specialist · Warm
**Question:** "How is this different from SWIFT GPI's own tooling?"

**Gold-standard answer** (30-second spoken):
SWIFT GPI tracks payments end-to-end and confirms ninety percent (90%) of payments reach their destination within one hour. It does not classify why a payment failed, does not price credit, and does not issue a bridge loan offer. LIP reads the pacs.002 GPI produces and turns that rejection into a conditional credit decision. The synthetic-first build ran two million records calibrated against BIS/SWIFT GPI settlement P95 data — we built on SWIFT's dataset, not against it.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "SWIFT GPI is just tracking — we do the intelligent part"
- ❌ "GPI doesn't have AI"

**Bear-case pointer:** None

---

### Q-TECH-05 · Bank-strategic · Warm
**Question:** "Walk me through what actually sits inside a bank when LIP runs."

**Gold-standard answer** (30-second spoken):
A pacs.002 arrives from the receiving correspondent. C1 reads the rejection code and counterparty graph — ninety-four milliseconds (94ms) later, C7 delivers a priced offer to the bank's treasury system via Go gRPC. The treasury officer sees an accept/decline prompt; no case was opened manually. In Phase 1 the bank funds the bridge; LIP's IP runs inside their environment. Nothing exits the bank's security perimeter that wasn't already in their SWIFT feed.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We integrate with the bank's systems"
- ❌ "LIP sits as a middleware layer"

**Bear-case pointer:** None

---

### Q-TECH-06 · Bank-strategic · Warm
**Question:** "Is this on-prem, cloud, or hybrid?"

**Gold-standard answer** (30-second spoken):
Deployment model is bank-determined. The Phase 1 architecture is designed for on-premises or dedicated-cloud deployment inside the bank's security boundary — nothing in the pacs.002 stream or the classification decision leaves the bank's environment. Kafka and Kubernetes run in the bank's cluster. The synthetic-first build means we arrive with a trained pipeline that doesn't require the bank's live data to initialise — reducing their data-governance risk at pilot entry.

**Anchors this answer must touch:**
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We're cloud-native so we can deploy anywhere"
- ❌ "The bank just points us at their SWIFT feed"

**Bear-case pointer:** None

---

### Q-TECH-07 · Adversarial · Warm
**Question:** "In one sentence, what have you actually built?"

**Gold-standard answer** (30-second spoken):
A production-grade pipeline that reads a pacs.002 rejection, classifies the failure type, and issues a priced bridge loan offer to the originating bank — in under ninety-four milliseconds (94ms) at p99 — validated against two million (2M) synthetic records calibrated to BIS/SWIFT GPI settlement data. That is the two-step classification + conditional offer mechanism, and it is the core of our provisional patent.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We've built a platform that basically..."
- ❌ "Think of it as the Stripe for failed payments"

**Bear-case pointer:** None

---

### Q-TECH-08 · Adversarial · Warm
**Question:** "Is this real or is it a deck?"

**Gold-standard answer** (30-second spoken):
It's real. One thousand two hundred eighty-four (1,284) tests passing, ninety-two percent (92%) coverage. The live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points (706 bps), nine-day maturity, five-thousand and thirty-three-dollar ($5,033) total fee — on a synthetic pacs.002 running through the full pipeline. The synthetic-first build was deliberate: we validated against two million (2M) records before asking any bank to be a beta tester. The deck describes what the code does.

**Anchors this answer must touch:**
- synthetic-first build
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "We have a working prototype"
- ❌ "We're basically ready, just need a pilot"

**Bear-case pointer:** None

---

## Probing Tier — Q-TECH-09 through Q-TECH-16

### Q-TECH-09 · Generalist VC · Probing
**Question:** "Why 94ms specifically? Where does that number come from?"

**Gold-standard answer** (30-second spoken):
The ninety-four millisecond SLO is the p99 end-to-end latency from pacs.002 arrival to loan offer output — QUANT-locked in `lip/common/constants.py`. The constraint is treasury-operational: a bank's straight-through-processing window for same-session decision-making closes in seconds, not minutes. At p99 we clear that window with headroom. Median latency is under fifty milliseconds (50ms). The SLO wasn't chosen arbitrarily — it was set to guarantee the offer arrives before a treasury officer opens the case.

**Anchors this answer must touch:**
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "94ms is just our target — we expect to hit it in production"
- ❌ "We benchmarked it and that's what we got"

**Bear-case pointer:** None

---

### Q-TECH-10 · Generalist VC · Probing
**Question:** "Why a fee floor — why not let the market price the bridge?"

**Gold-standard answer** (30-second spoken):
The three-hundred basis point (300 bps) fee floor is the point at which the loan is capital-positive at p99 of our cost-of-capital stack. Below three hundred bps (300 bps), annualised yield on a seven-day Class A bridge falls below debt service — the loan destroys value even if it repays. Market pricing that clears below the floor is economically incoherent, not disciplined. The floor is QUANT-locked: nothing changes it without sign-off on the underlying cost-of-capital math.

**Anchors this answer must touch:**
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "300 bps is our starting point — banks can negotiate"
- ❌ "It's a floor so we always make money"

**Bear-case pointer:** None

---

### Q-TECH-11 · Fintech Specialist · Probing
**Question:** "Walk me through C1's architecture — GraphSAGE, TabTransformer, LightGBM. Why all three?"

**Gold-standard answer** (30-second spoken):
Three signal types, three models. GraphSAGE captures corridor graph structure — counterparty co-failure patterns — output dim 384. TabTransformer handles pacs.002 tabular features — output dim 88. LightGBM runs gradient boosting on the combined embedding. Each captures what the others miss. C1 threshold: zero point one one zero (0.110), F2-optimal. False negatives cost more than false positives, so asymmetric BCE alpha is set at zero point seven (0.7).

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We use a mix of models to get better accuracy"
- ❌ "GraphSAGE handles the graph part, the others handle the rest"

**Bear-case pointer:** None

---

### Q-TECH-12 · Fintech Specialist · Probing
**Question:** "What's your latency breakdown per component? Where does the time go?"

**Gold-standard answer** (30-second spoken):
The ninety-four millisecond SLO (94ms) spans: pacs.002 ingestion, C1 inference, C4 dispute and C6 AML/velocity in parallel, C2 PD pricing, C7 offer delivery via Go gRPC. C1 dominates — GraphSAGE uses five (5) neighbors at inference vs. ten (10) at training, cutting graph traversal. C7 uses Go gRPC to eliminate serialisation overhead. p50 median is under fifty milliseconds (50ms); 94ms is the worst-in-hundred case.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "Most of the time is in the ML inference"
- ❌ "We haven't done a full breakdown yet but 94ms is the total"

**Bear-case pointer:** None

---

### Q-TECH-13 · Bank-strategic · Probing
**Question:** "My AML team would block this on day one. Convince me they won't."

**Gold-standard answer** (30-second spoken):
LIP is designed so AML blocks LIP, not the other way around. Eight rejection codes — DNOR, CNOR, RR01–RR04, AG01, LEGL — are permanently blocked: no classification runs, no offer issues. The two-step classification + conditional offer mechanism never clears for compliance-held payments. C6 AML and velocity screening runs on every non-blocked payment; any anomaly routes to PENDING_HUMAN_REVIEW per EU AI Act Article 14. AML authority is preserved by design.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We're fully compliant with AML regulations"
- ❌ "AML teams will see that LIP actually helps them"

**Bear-case pointer:** None

---

### Q-TECH-14 · Bank-strategic · Probing
**Question:** "What happens when Kafka backs up under bank-throughput load?"

**Gold-standard answer** (30-second spoken):
HPA scale-out triggers at queue depth of one hundred (100); scale-in at twenty (20). Messages queue in Kafka with no loss — Kafka is the durability layer. The ninety-four millisecond SLO (94ms) clock starts on dequeue, so back-pressure shows as queue wait time, not inference failures. The synthetic-first build ran throughput stress scenarios before any bank traffic. The failure mode is latency, not data loss.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "Kafka handles it — that's what it's designed for"
- ❌ "We'd need to tune the infrastructure with the bank's ops team"

**Bear-case pointer:** None

---

### Q-TECH-15 · Adversarial · Probing
**Question:** "You have no production traffic. What do you actually know about your model's behaviour?"

**Gold-standard answer** (30-second spoken):
Two million (2M) synthetic records calibrated to BIS/SWIFT GPI settlement P95 data: C1 baseline AUC zero point seven three nine (0.739), target zero point eight five zero (0.850) after production training. The synthetic-first build is the decision that lets us arrive with a trained pipeline, not a prototype. The AUC will shift on live rejection code distributions. That shift is the expected pilot output, not a surprise.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "Our synthetic data is representative of real-world conditions"
- ❌ "We've validated the model thoroughly"

**Bear-case pointer:** None

---

### Q-TECH-16 · Adversarial · Probing
**Question:** "Why should I believe 94ms holds at scale — say, 53 million messages a day?"

**Gold-standard answer** (30-second spoken):
SWIFT peaks at fifty-five million (55M) messages per day. The ninety-four millisecond SLO (94ms) is per-message p99 — the pipeline is stateless at inference and horizontally scalable. Each pacs.002 is an independent event. Kafka partitioning spreads load; HPA scale-out at queue depth of one hundred (100) adds pods. Under extreme load, the SLO degrades to queue wait time, not inference errors. Two million (2M) synthetic records stress-tested the inference path — the scaling architecture is proven.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We're confident it will scale — it's Kubernetes"
- ❌ "94ms is our current benchmark; we'd tune it at scale"

**Bear-case pointer:** None

---

## Adversarial Tier — Q-TECH-17 through Q-TECH-20

### Q-TECH-17 · Generalist VC · Adversarial
**Question:** "Non-technical founder, current RBC employee, no production traffic. Convince me this isn't a pipe dream."

**Gold-standard answer** (30-second spoken):
The code runs: one thousand two hundred eighty-four (1,284) tests, ninety-two percent (92%) coverage, live demo on record. Non-technical founder misidentifies the risk — technical execution is a hiring problem. The hard problem is knowing which ML architecture to validate and which patent claim to file first. I got those right. RBC employment means I understand compliance at the level of AMLD6 Article 10 and FATF Recommendation 13 — not despite being an insider, because of it.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "I have a great technical team behind me"
- ❌ "My background gives me unique insight into the problem"

**Bear-case pointer:** META-03

---

### Q-TECH-18 · Fintech Specialist · Adversarial
**Question:** "Your fee floor is 300 bps. That's roughly 3x Wise's FX margin. Why would any bank pay that?"

**Gold-standard answer** (30-second spoken):
Wise moves consumer and SMB payments of $200–$50K. LIP bridges correspondent banking failures where average principal is $800K–$1.5M. At the three-hundred basis point (300 bps) floor on a seven-day bridge, the fee is zero point zero five seven five percent (0.0575%) per cycle — basis-point noise on a multi-million-dollar trade. The bank compares that fee to the alternative: a stalled trade and a manual overnight bridge at a worse rate.

**Anchors this answer must touch:**
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "Banks are used to paying higher fees than consumers"
- ❌ "300 bps is just the floor — actual fees will be higher"

**Bear-case pointer:** None

---

### Q-TECH-19 · Bank-strategic · Adversarial
**Question:** "I've seen a hundred fintechs pitch liquidity to banks. Every one died in procurement. What's different?"

**Gold-standard answer** (30-second spoken):
Phase 1 is a software licence, not a lending arrangement. The bank funds one hundred percent (100%) of capital; BPI earns a thirty percent (30%) royalty on fees the bank already collects. No balance sheet exposure, no new credit policy, no BPI lending licence to negotiate. The bank's procurement question: does this IP generate fee income above the licence cost? The synthetic-first build means the pilot is a validation exercise — not a proof-of-concept the bank pays to build.

**Anchors this answer must touch:**
- synthetic-first build
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "We've designed LIP specifically to navigate bank procurement"
- ❌ "Our go-to-market is different because we work with banks, not against them"

**Bear-case pointer:** None

---

### Q-TECH-20 · Adversarial · Adversarial
**Question:** "JPMorgan has the patent. You're a synthetic-data startup. What stops them from shipping this in 90 days?"

**Gold-standard answer** (30-second spoken):
US7089207B1 covers static bridge loans for listed counterparties at fixed rates. It does not cover the two-step classification + conditional offer mechanism, ISO 20022 rejection-code-based maturity, or private counterparties via Damodaran industry-beta and Altman Z'. That gap is our novel claim. JPMorgan shipping this in ninety days requires re-engineering their credit pricing stack and stepping outside their own patent's scope. Their edge is distribution, not IP — and that's why we file first.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ISO 20022 migration window

**Don't-say-this traps:**
- ❌ "JPMorgan's patent is old — technology has moved on"
- ❌ "Our moat is the team and the data, not just the patent"

**Bear-case pointer:** None

---

## Crushing Tier — Q-TECH-21 through Q-TECH-24

### Q-TECH-21 · Generalist VC · Crushing
**Question:** "Walk me through what happens if RBC claims ownership of the IP under your employment clause."

**Gold-standard answer** (30-second spoken):
The most material risk in the company — and the answer: we resolve it before filing. RBC's offer letter has a broad IP assignment clause. The strategy is resignation before the provisional files — as an external vendor, BPI owns the IP clean. Counsel reviews and confirms the timeline. If RBC asserts a claim, the question is whether conception occurred during employment — a factual dispute, not automatic assignment. The patent is never socialised internally at RBC. Mitigation is sequenced.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "I don't think RBC would actually pursue that"
- ❌ "Our lawyer said we're probably fine"

**Bear-case pointer:** META-01

---

### Q-TECH-22 · Fintech Specialist · Crushing
**Question:** "Prove 94ms. Real traffic, real bank, real numbers — or admit you don't know."

**Gold-standard answer** (30-second spoken):
We do not have real bank traffic. The ninety-four millisecond SLO (94ms) is validated on synthetic pacs.002 — QUANT-locked, confirmed against two million (2M) records. What we know: inference is stateless, degrades gracefully under load. What we don't know: how live rejection distributions shift C1 inference time. That is the expected pilot output — not something we claim before having it. 94ms is the pre-pilot guarantee; the live number comes from the pilot.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "94ms is our SLO so we're confident we'll hit it"
- ❌ "We've stress-tested it extensively on synthetic data so it should hold"

**Bear-case pointer:** META-02

---

### Q-TECH-23 · Bank-strategic · Crushing
**Question:** "You will not get a pilot at a Tier 1 bank. Change my mind."

**Gold-standard answer** (30-second spoken):
Primary entry point: RBCx — RBC's venture arm led by Sid Paquette with a B2B payments mandate. Phase 1 is a software licence; the bank funds one hundred percent (100%) of capital. The bank's test: does the pipeline produce accurate offers on their pacs.002 feed? Three-month technical validation, not an eighteen-month procurement cycle. Synthetic-first build means we arrive with a trained pipeline. Bank onboarding is 18–24 months; we start that clock now.

**Anchors this answer must touch:**
- synthetic-first build
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "We have warm introductions at several Tier 1 banks"
- ❌ "The product sells itself once they see the demo"

**Bear-case pointer:** B-MKT-02, B-MKT-06

---

### Q-TECH-24 · Adversarial · Crushing
**Question:** "You're not technical. If your senior engineer leaves tomorrow, what happens?"

**Gold-standard answer** (30-second spoken):
One thousand two hundred eighty-four (1,284) tests, ninety-two percent (92%) coverage. Any senior engineer reads the codebase and trusts it within a week. Synthetic-first build produced a documented, reproducible pipeline — no tribal knowledge. QUANT-locked constants mean no engineer accidentally breaks the three-hundred basis point (300 bps) floor or ninety-four millisecond (94ms) SLO without a sign-off trail. The risk is two-to-four weeks of velocity loss. That is a hiring problem.

**Anchors this answer must touch:**
- synthetic-first build
- ninety-four millisecond SLO
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "I'm learning the technical side every day"
- ❌ "My CTO and I are very aligned so the risk is manageable"

**Bear-case pointer:** META-03
