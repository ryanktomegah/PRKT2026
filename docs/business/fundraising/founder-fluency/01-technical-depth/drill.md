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

### Q-TECH-25 · Generalist VC · Warm
**Question:** "How does a bank actually license LIP? Walk me through the onboarding."

**Gold-standard answer** (30-second spoken):
The bank signs the MRFA — Master Receivables Financing Agreement — which names the originating bank BIC as borrower and includes the hold_bridgeable certification warranty. A C8 license token is issued, HMAC-SHA256 signed, carrying per-licensee AML caps at boot time. The pipeline boots inside the bank's environment; the two-step classification + conditional offer mechanism runs against their pacs.002 feed. No new credit policy is negotiated in Phase 1 — the bank funds one hundred percent (100%) of capital; BPI earns a thirty percent (30%) royalty on fees the bank collects.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "Onboarding is pretty straightforward once the paperwork is done"
- ❌ "We do a standard software licensing deal"

**Bear-case pointer:** None

---

### Q-TECH-26 · Generalist VC · Warm
**Question:** "How much of this can I actually see running today? Documentation, dashboards, logs?"

**Gold-standard answer** (30-second spoken):
The codebase is self-documenting: a README with one thousand two hundred eighty-four (1,284) passing tests and ninety-two percent (92%) coverage, data cards for C1 and C2, and the EPG decision register under `docs/legal/decisions/`. Observability is structured: every pacs.002 produces a decision log entry with UETR, classification output, fee, and latency — retained seven (7) years for regulatory audit. The synthetic-first build means every number cited — the ninety-four millisecond SLO, the three-hundred basis point floor — is traceable to a test, not a slide.

**Anchors this answer must touch:**
- synthetic-first build
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "We have extensive documentation"
- ❌ "Happy to walk you through the demo anytime"

**Bear-case pointer:** None

---

### Q-TECH-27 · Fintech Specialist · Warm
**Question:** "What integration surface does a bank actually touch? APIs, SDKs, message queues?"

**Gold-standard answer** (30-second spoken):
One inbound, one outbound. Inbound: a Kafka topic carrying the bank's pacs.002 stream — C5 normalises the ISO 20022 message at entry. Outbound: a Go gRPC endpoint that delivers the priced offer to treasury. That is the integration surface. No REST API, no polling loop, no bank-side SDK to embed. The synthetic-first build means the Kafka consumer and gRPC router have been stress-tested against two million (2M) records before the bank plugs in.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We have a flexible API that integrates with anything"
- ❌ "We meet the bank wherever they are on their stack"

**Bear-case pointer:** None

---

### Q-TECH-28 · Fintech Specialist · Warm
**Question:** "What is your service-level commitment at the contract level — not the engineering SLO?"

**Gold-standard answer** (30-second spoken):
Contractual SLA mirrors the engineering target: ninety-four millisecond (94ms) p99 end-to-end, measured from pacs.002 arrival on the Kafka topic to gRPC offer delivery. Availability target is four nines (99.99%) on the inference service, aligned to DORA operational resilience expectations. If the SLA is breached, the offer is not issued — no offer without classification gate clearance, per the two-step classification + conditional offer mechanism. The QUANT-locked SLO is what the contract references; there is no softer internal number.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We'd work with the bank to set an SLA that works for them"
- ❌ "94ms is the SLO; the SLA would be negotiated in the pilot"

**Bear-case pointer:** None

---

### Q-TECH-29 · Bank-strategic · Warm
**Question:** "What does model observability look like once LIP is live in my bank?"

**Gold-standard answer** (30-second spoken):
Every C1 inference writes a decision log: UETR, rejection code, classification score, threshold clearance at zero point one one zero (0.110), and downstream C2 fee output. Drift monitors track the C1 score distribution against the synthetic baseline AUC of zero point seven three nine (0.739) — calibration shift surfaces within a single trading day. Conformal prediction intervals on C2 carry a ninety percent (90%) coverage guarantee; coverage breach is an alarm, not a surprise. The Ford Principle governs response: QUANT signs off before any threshold or floor moves.

**Anchors this answer must touch:**
- synthetic-first build
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "We have standard ML monitoring in place"
- ❌ "The bank's data science team can plug in their own tools"

**Bear-case pointer:** None

---

### Q-TECH-30 · Bank-strategic · Warm
**Question:** "Who owns the audit trail — you or my bank?"

**Gold-standard answer** (30-second spoken):
The bank owns the audit trail. Decision logs write to the bank's storage inside their security perimeter — seven (7) year retention for SR 11-7 and OSFI E-23 model-risk reviews. BPI receives only aggregate telemetry under the P10 privacy layer: k-anonymity threshold of five (5), differential privacy epsilon of zero point five (0.5). Nothing leaves the bank that identifies a counterparty or a payment. That is the synthetic-first build posture extended into production: bank-boundary-respecting by construction.

**Anchors this answer must touch:**
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We store a copy on our side for our own monitoring"
- ❌ "The audit trail is shared between us and the bank"

**Bear-case pointer:** None

---

### Q-TECH-31 · Adversarial · Warm
**Question:** "What's the simplest failure mode — what breaks first?"

**Gold-standard answer** (30-second spoken):
The first-to-break is C1 calibration under live rejection-code distributions. Synthetic baseline AUC is zero point seven three nine (0.739); target after production training is zero point eight five zero (0.850). Live data will shift the score distribution — the zero point one one zero (0.110) threshold may need recalibration inside the pilot. That is the expected pilot output, not a surprise. The two-step classification + conditional offer mechanism degrades gracefully: if C1 does not clear, no offer issues. The bank loses revenue, not money.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We haven't really thought about failure modes"
- ❌ "The system is robust — it doesn't really fail"

**Bear-case pointer:** B-TECH-01

---

### Q-TECH-32 · Adversarial · Warm
**Question:** "You said 1,284 tests. What do they actually cover?"

**Gold-standard answer** (30-second spoken):
End-to-end pipeline across eight (8) scenarios with mock C1 and C2 outputs — no live Redis or Kafka required. Unit tests on every QUANT-locked constant: the three-hundred basis point (300 bps) floor, the ninety-four millisecond (94ms) SLO, the zero point one one zero (0.110) threshold, the eight (8) BLOCK rejection codes. Negation corpus of five hundred (500) cases on C4 dispute classification. Ninety-two percent (92%) coverage. The synthetic-first build gates the rest — the test suite is the contract between code and claim.

**Anchors this answer must touch:**
- synthetic-first build
- three-hundred basis point fee floor
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "The usual — unit tests and integration tests"
- ❌ "92% coverage speaks for itself"

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

### Q-TECH-33 · Generalist VC · Probing
**Question:** "What's the feature engineering story? Why those features, not others?"

**Gold-standard answer** (30-second spoken):
Three signal families. pacs.002 tabular — rejection code, amount, corridor, counterparty tier — fed to TabTransformer, output dim eighty-eight (88). Corridor graph structure — co-failure patterns across eleven thousand-plus (11,000+) SWIFT member institutions — fed to GraphSAGE, output dim three hundred eighty-four (384). Temporal velocity — per-entity frequency over a ninety (90)-day corridor window. LightGBM combines all three on a four hundred seventy-two (472)-dim embedding. Features were selected because the ISO 20022 migration window made the tabular signal structured for the first time.

**Anchors this answer must touch:**
- ISO 20022 migration window
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We used the features that made sense for the problem"
- ❌ "We did the usual feature selection experiments"

**Bear-case pointer:** None

---

### Q-TECH-34 · Generalist VC · Probing
**Question:** "How do you govern the agents? What stops one of them from breaking something critical?"

**Gold-standard answer** (30-second spoken):
The Ford Principle. QUANT has final authority on all financial math — nothing merges that changes the three-hundred basis point (300 bps) fee floor or the ninety-four millisecond (94ms) SLO without QUANT sign-off. CIPHER has final authority on AML patterns — typology rules are never committed to version control. REX has final authority on compliance — no model ships without a data card. These are vetoes, not suggestions. The canonical constants are QUANT-locked in `lip/common/constants.py`: the code itself refuses drift.

**Anchors this answer must touch:**
- three-hundred basis point fee floor
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "We have good internal review processes"
- ❌ "Our team is senior and aligned"

**Bear-case pointer:** None

---

### Q-TECH-35 · Fintech Specialist · Probing
**Question:** "What happens when C1 and C2 disagree — high classification confidence but low PD pricing signal, or the reverse?"

**Gold-standard answer** (30-second spoken):
They cannot disagree by design. The two-step classification + conditional offer mechanism is sequential: C1 must clear its zero point one one zero (0.110) threshold before C2 runs. If C1 does not clear, C2 never prices. If C1 clears but the payment is sub-minimum — below one million five hundred thousand dollars ($1,500,000) for Class A — C2 still produces a price, but at the five hundred basis point (500 bps) small-tier rate, never below the three-hundred basis point (300 bps) canonical floor. Conformal intervals on C2 cap upward adjustment at two-times (2.0x). The disagreement case is structurally prevented.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "We average the two outputs"
- ❌ "If they disagree we escalate to human review"

**Bear-case pointer:** None

---

### Q-TECH-36 · Fintech Specialist · Probing
**Question:** "Walk me through model monitoring in production — what alarms fire, when, and who catches them?"

**Gold-standard answer** (30-second spoken):
Three layers. C1 score drift against synthetic baseline AUC zero point seven three nine (0.739) — alarm on a single-day distribution shift beyond a pre-set KS threshold. C2 conformal coverage breach — ninety percent (90%) coverage is the guarantee; a breach triggers QUANT review. Latency p99 regression — the ninety-four millisecond (94ms) SLO is a QUANT-locked constant; a breach pages FORGE on infrastructure and ARIA on inference. The Ford Principle governs response authority; no silent fixes merge.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "We use standard MLOps tooling — Grafana, Prometheus, and so on"
- ❌ "The alarms are tuned during the pilot"

**Bear-case pointer:** B-TECH-01

---

### Q-TECH-37 · Bank-strategic · Probing
**Question:** "Explain the EPG-04/05 decision. Why ask for a certification flag and not a hold reason?"

**Gold-standard answer** (30-second spoken):
FATF Recommendation 21 forbids tipping-off — a bank cannot tell a third party why it raised a compliance hold. So we designed around it. EPG-04/05 asks the bank for a single hold_bridgeable boolean flag, certified by the bank's automated compliance system. The bank decides internally; LIP sees only the certification. That mirrors FATF Recommendation 13 correspondent KYC cert structure. The two-step classification + conditional offer mechanism hard-blocks on false. The license agreement carries three warranties: certification, system integrity, indemnification.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We ask the bank to tell us what's wrong with the payment"
- ❌ "We handle the compliance question in a smart way"

**Bear-case pointer:** None

---

### Q-TECH-38 · Bank-strategic · Probing
**Question:** "What happens if an operator on my team manually overrides a decision? Can they?"

**Gold-standard answer** (30-second spoken):
Yes — human oversight is required by EU AI Act Article 14 and designed in, not bolted on. C7 checks three flags before any offer issues: the kill switch, KMS availability, and the human-override flag. C6 anomalies route to PENDING_HUMAN_REVIEW. A treasury officer can decline any offer; they cannot silently approve a blocked one — the two-step classification + conditional offer mechanism never clears for BLOCK class. Every override writes to the seven (7)-year decision log with operator identity. Authority is preserved; auditability is absolute.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "Operators can override anything — we don't block them"
- ❌ "Human override is a fallback feature"

**Bear-case pointer:** None

---

### Q-TECH-39 · Adversarial · Probing
**Question:** "AUC of 0.739 on synthetic. That's not great. What makes you think live data helps?"

**Gold-standard answer** (30-second spoken):
Zero point seven three nine (0.739) is the baseline, not the ceiling. The zero point eight five zero (0.850) target is after production training on live rejection distributions. The synthetic corpus was deliberately conservative — calibrated to BIS/SWIFT GPI settlement P95 data, not tuned to flatter the model. Live corpora carry richer temporal signals and true counterparty histories that synthetic cannot reproduce. ARIA refuses to call the number "good" without that caveat. The synthetic-first build gives us a trained pipeline that improves under live traffic, not a shiny number that degrades.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "0.739 is actually decent for this type of problem"
- ❌ "The model will definitely hit 0.850 in production"

**Bear-case pointer:** B-TECH-01

---

### Q-TECH-40 · Adversarial · Probing
**Question:** "Your Phase 1 royalty is 30%. Where does that number actually come from?"

**Gold-standard answer** (30-second spoken):
Thirty percent (30%) is QUANT-locked, derived from the IP-licensing share convention for pure-software royalty on bank-funded capital — an EPG-decision-anchored constant in `lip/common/constants.py`. At the three-hundred basis point (300 bps) fee floor on a large ticket, the bank nets two hundred ten (210) bps and BPI nets ninety (90) bps — both sides capital-positive after debt service. Phase 2 moves to fifty-five percent (55%) BPI share when BPI starts funding capital; Phase 3 to eighty percent (80%) at full MLO. The progression is engineered; the starting share is not.

**Anchors this answer must touch:**
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "30% felt like a reasonable starting share"
- ❌ "We benchmarked against other fintech deals"

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

### Q-TECH-41 · Generalist VC · Adversarial
**Question:** "Where's the scaling cliff? Not when you grow 10x — when you grow 100x?"

**Gold-standard answer** (30-second spoken):
The cliff is the GraphSAGE graph store, not the inference path. At one hundred times (100x) current load, the corridor graph crosses the threshold where five (5)-neighbour inference traversal stops fitting in a single node's memory — a partitioning rewrite, not a rewrite of the two-step classification + conditional offer mechanism. The ninety-four millisecond SLO is stateless at inference; horizontally scalable. The Kafka partitioning and HPA scale-out at queue depth one hundred (100) handle raw throughput. The graph layer is the known next engineering milestone; it is scoped, not surprising.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "We haven't hit a scaling cliff yet"
- ❌ "Kubernetes handles the scaling question"

**Bear-case pointer:** B-TECH-02

---

### Q-TECH-42 · Fintech Specialist · Adversarial
**Question:** "Polyglot stack — Python, Rust, Go. That's a hiring nightmare. How do you survive the first engineering hire?"

**Gold-standard answer** (30-second spoken):
Polyglot was a latency decision, not a preference. Python owns the ML inference path; Rust via PyO3 owns the C3 repayment FSM and C6 velocity counters where GC pauses would break the ninety-four millisecond SLO; Go owns C5 Kafka and C7 gRPC where concurrency primitives eliminate serialisation. The first hire targets the Python layer where the hiring pool is deepest; Rust and Go ownership grows over time. One thousand two hundred eighty-four (1,284) tests and ninety-two percent (92%) coverage mean any senior engineer reads the codebase and trusts it within a week. The search is longer; the onboarding is not.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "The Rust hiring market is fine"
- ❌ "We can always refactor to pure Python"

**Bear-case pointer:** B-TECH-03

---

### Q-TECH-43 · Bank-strategic · Adversarial
**Question:** "If Groq deprecates Qwen3 tomorrow, C4 stops working. What's the exposure?"

**Gold-standard answer** (30-second spoken):
C4 is not on the critical path. The two-step classification + conditional offer mechanism runs on C1 and C2. C4 advises on dispute characteristics; its failure routes to human review, not a pipeline halt. The ninety-four millisecond SLO is not gated on C4 — it runs in parallel with C6 AML screening. A Qwen3 deprecation is a swap event: a second LLM backend is the planned resolution, validated against the five hundred (500)-case negation corpus before it goes live. The exposure is a temporary routing of dispute calls to human review, not a system outage.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "We can swap LLMs easily"
- ❌ "Groq is a reliable provider — we're not worried"

**Bear-case pointer:** B-TECH-04

---

### Q-TECH-44 · Bank-strategic · Adversarial
**Question:** "If Kafka has an outage mid-session, what does my treasury officer see?"

**Gold-standard answer** (30-second spoken):
They see the existing manual process. Kafka is the durability layer — messages queue on recovery; nothing is lost. During outage, no pacs.002 enters the pipeline, so no offer issues — the two-step classification + conditional offer mechanism simply does not clear. The bank continues the manual overnight bridge workflow they used before LIP. Recovery is Kafka-native: queued messages replay on the dequeue clock; the ninety-four millisecond SLO measures from dequeue, so back-pressure surfaces as latency, never as lost decisions. The failure mode is silent revert to status quo, not a broken pipeline.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- ninety-four millisecond SLO

**Don't-say-this traps:**
- ❌ "Kafka doesn't really go down"
- ❌ "We'd handle that case in the pilot"

**Bear-case pointer:** B-TECH-02

---

### Q-TECH-45 · Adversarial · Adversarial
**Question:** "Your dependency graph — PyTorch, LightGBM, PyO3, Groq, Kafka, Kubernetes. Any one breaks and you're down. Walk me through the fragility."

**Gold-standard answer** (30-second spoken):
Each dependency maps to a component, and each component has a graceful-degradation path. PyTorch+LightGBM surfaced a macOS thread deadlock during development — caught, fixed with a session-scoped pytest fixture, gated in CI. PyO3 is the Rust-Python bridge for C3 and C6 velocity — no network dependency. Groq is a C4 advisory path, not critical. Kafka is the durability layer. The two-step classification + conditional offer mechanism is the only non-substitutable piece — and that is the patent. The synthetic-first build caught every one of these before a bank ever plugged in.

**Anchors this answer must touch:**
- synthetic-first build
- two-step classification + conditional offer mechanism

**Don't-say-this traps:**
- ❌ "None of those are real risks — they're all mature tools"
- ❌ "We've hardened every dependency"

**Bear-case pointer:** B-TECH-05

---

### Q-TECH-46 · Adversarial · Adversarial
**Question:** "What's the SLO regression scenario that scares you most?"

**Gold-standard answer** (30-second spoken):
The one I cannot simulate on synthetic data: a live rejection-code distribution that shifts C1 inference time into the long tail. The ninety-four millisecond SLO is p99; median is under fifty milliseconds (50ms). If live data produces a long-tail rejection type that hits GraphSAGE's ten (10)-neighbour path at training instead of the five (5)-neighbour inference path, p99 drifts. The mitigation is measured in the pilot: retrain on live distribution, recalibrate the zero point one one zero (0.110) threshold. It is the expected pilot output, not an architecture rewrite.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- synthetic-first build

**Don't-say-this traps:**
- ❌ "Nothing really scares me about the SLO"
- ❌ "We'd handle any SLO issue with more pods"

**Bear-case pointer:** B-TECH-02

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

---

### Q-TECH-47 · Generalist VC · Crushing
**Question:** "Non-technical founder, RBC IP clause unresolved, zero production traffic. Why is this a company and not a preprint?"

**Gold-standard answer** (30-second spoken):
Because the synthetic-first build is a company decision, not a stalled prototype. The RBC IP clause resolves through resignation before the provisional files — sequenced, not hoped. The non-technical founder question resolves through governance: the Ford Principle, QUANT-locked constants, and a team that pushes back before wrong code ships. The production-traffic question resolves in the pilot — the ninety-four millisecond SLO and the three-hundred basis point (300 bps) floor are pre-pilot guarantees; the live numbers are the pilot's job. Three material risks, three scoped resolution events. That is a company.

**Anchors this answer must touch:**
- synthetic-first build
- ninety-four millisecond SLO
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "Every early-stage company has risks"
- ❌ "Those are the normal hurdles at this stage"

**Bear-case pointer:** META-01, META-02, META-03

---

### Q-TECH-48 · Fintech Specialist · Crushing
**Question:** "You can't prove 94ms on real traffic, your founder can't write the code, and you're still at RBC. Which of those is the one that kills you?"

**Gold-standard answer** (30-second spoken):
None of them, because each has a scoped resolution event — and none depends on the others. Ninety-four milliseconds (94ms) resolves with the first live UETR in the RBC pilot; the two-step classification + conditional offer mechanism is architecturally scale-ready. The founder-fluency question resolves continuously — I can defend the GraphSAGE output dim of three hundred eighty-four (384), the zero point one one zero (0.110) threshold, the three-hundred basis point (300 bps) floor derivation. The RBC IP resolves with resignation before filing. The kill scenario is all three compounding; they are sequenced precisely to prevent that.

**Anchors this answer must touch:**
- ninety-four millisecond SLO
- two-step classification + conditional offer mechanism
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "The 94ms is the one I worry about most"
- ❌ "Pick whichever one you think is worst"

**Bear-case pointer:** META-01, META-02, META-03

---

### Q-TECH-49 · Bank-strategic · Crushing
**Question:** "You want my bank to be your first pilot. I have a non-technical founder, unverified performance claims, and an IP risk with my Canadian competitor. Why shouldn't I wait?"

**Gold-standard answer** (30-second spoken):
Because waiting is not free. The ISO 20022 migration window narrows as incumbents complete migration — the two-step classification + conditional offer mechanism is patentable now, not in eighteen (18) months. Phase 1 is a software licence: your bank funds one hundred percent (100%) of capital, BPI earns a thirty percent (30%) royalty, no new credit policy to negotiate. The synthetic-first build means the pilot is a three-month technical validation, not an engineering sprint. The founder-fluency and IP questions resolve on defined timelines; the market window does not. The cost of waiting is the three-hundred basis point (300 bps) floor multiplied by the bridge volume you cede to the first mover.

**Anchors this answer must touch:**
- ISO 20022 migration window
- synthetic-first build
- three-hundred basis point fee floor

**Don't-say-this traps:**
- ❌ "You won't regret going first"
- ❌ "The other risks are manageable — just look at the product"

**Bear-case pointer:** META-01, META-02, META-03

---

### Q-TECH-50 · Adversarial · Crushing
**Question:** "Walk me through the scenario where everything breaks: RBC claims your IP, your engineer quits, your synthetic data doesn't generalise. What's left?"

**Gold-standard answer** (30-second spoken):
What is left is the provisional patent filed before resignation — the two-step classification + conditional offer mechanism with a priority date the RBC claim cannot predate. What is left is a documented codebase — one thousand two hundred eighty-four (1,284) tests, ninety-two percent (92%) coverage, QUANT-locked constants — that any senior engineer reads and trusts within a week. What is left is the synthetic-first build's honest framing: the baseline AUC of zero point seven three nine (0.739) is the floor, not the claim; live-data shift is the expected pilot output. Three simultaneous failures still leave the IP, the code, and the calibration discipline. That is the company.

**Anchors this answer must touch:**
- two-step classification + conditional offer mechanism
- synthetic-first build

**Don't-say-this traps:**
- ❌ "That scenario is really unlikely"
- ❌ "We'd find a way through — we always do"

**Bear-case pointer:** META-01, META-02, META-03
