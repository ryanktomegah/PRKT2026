# FUTURE TECHNOLOGY DISCLOSURE
## VERSION 2.1 — PROSECUTION-READY

*Confidential Technical Disclosure for Continuation Patent Filing Purposes*

**The Liquidity Intelligence Platform — Seven Extensions**

| **Field** | **Value** |
|-----------|-----------|
| Document Version | 2.1 — Prosecution-Ready |
| Supersedes | v2.0 — Prosecution-Ready |
| Priority Date | To be established at provisional patent filing — all extensions described herein are to be preserved for claim with that priority date |
| Continuation Patents | P3 through P10 (filing offsets from provisional filing date — see Section: Filing Trigger Table) |
| Extensions Disclosed | Pre-Emptive Bridging (A) \| Supply Chain Cascade (B) \| Autonomous Treasury (C) \| Tokenised Receivable Pools (D) \| CBDC Bridging (E) \| Multi-Party Distributed Architecture (F) \| Adversarial Cancellation Detection (G) |
| Confidentiality | Trade Secret — Attorney-Client Privileged — Do Not Distribute Under Any Circumstances |

---

> **CRITICAL LEGAL PURPOSE OF THIS DOCUMENT:** Under US patent law, a continuation application can only claim subject matter that was described in the original parent application. If a technology extension is NOT described in the original provisional filing, it cannot be claimed with the original priority date — it can only be filed as a new application with a later priority date, making it vulnerable to intervening prior art. This document provides the technical descriptions that preserve the right to claim all seven extensions with the priority date established at provisional filing. Every extension described here was conceived before provisional filing and is therefore entitled to that priority date.
>
> **WHAT CHANGED IN v2.1:** Three corrections from v2.0. First, all foundational-specification references were updated from the old v5.0 placeholder to the current prosecution-ready provisional package. Second, the Filing Trigger Table at the end of this document has been updated to replace absolute calendar years (2028, 2029, 2031, 2033, 2034) with offset language anchored to the Provisional Filing Date (PFD) — consistent with the offset convention adopted throughout the Patent Family Architecture v2.1. The absolute calendar years were planning estimates written before the provisional was filed; offset language is more accurate and legally precise. Third, header metadata updated: "Continuation Patents" field now references PFD offset language rather than absolute years. All technical content, extension descriptions, claim draft elements, and strategic guidance are unchanged from v2.0.
>
> **WHAT CHANGED IN v2.0 (retained for record):** Two new extensions added: Extension F describes the multi-party distributed architecture in which the three system components are operated by different legal entities — a payment network operator, an ML inference provider, and a bank executing and funding liquidity — specifically to close the divided infringement design-around vector. Extension G describes the adversarial camt.056 cancellation detection system that corresponds to Dependent Claim D13 in the current prosecution-ready provisional specification. Both extensions were conceived before provisional filing and are entitled to the original priority date. Sections A through E were carried forward from v1.0 with minor clarifications and internal cross-references updated.

---

## Extension A: Pre-Emptive Liquidity Portfolio Management System

> **WHAT THIS IS:** The foundational system detects payment failures after they begin. This extension describes a system that anticipates payment failures before the payment is even sent — analysing historical patterns, counterparty behaviour, network conditions, and forward calendars to predict which upcoming payment receipts are at risk, and proactively offering a standing liquidity facility calibrated to the predicted working capital gap distribution. This extension is already incorporated into Independent Claim 4 of the foundational provisional specification; this section preserves the additional technical detail needed for continuation claims P4 that go beyond what Claim 4 covers.

### A.1 Technical Architecture

The Pre-Emptive Liquidity System operates as a parallel module to the reactive bridging system, consuming the same monitoring data but operating on a different time horizon. Where the reactive system processes events that have already occurred — a pacs.002 rejection message has been received — the pre-emptive system processes forward-looking probability distributions over anticipated future payment events.

The system maintains a payment expectation model for each enrolled business entity. This model is a probabilistic graph of expected payment receipts, constructed from the entity's historical payment receipt patterns, current outstanding invoices sourced via ERP API integration, and contractual payment terms. Each expected payment node in the graph carries a probability distribution over possible receipt dates and a conditional failure probability derived from the counterparty's historical performance and current network risk indicators.

### A.2 Core Technical Components

#### A.2.1 Payment Expectation Graph Builder

The Payment Expectation Graph is a directed graph where each node represents an expected future payment receipt and each edge represents a dependency relationship between payments. The system constructs this graph by ingesting invoice data from the entity's ERP system via API, cross-referencing counterparty payment history from the system's proprietary BIC-pair performance database, and applying Bayesian updating to the expected receipt date distribution based on real-time network risk indicators.

Each payment node carries five attributes: the expected receipt amount; the expected receipt date distribution modelled as a probability distribution over a date range; the sending counterparty's BIC identifier; the current failure probability estimate for this specific counterparty-corridor-timing combination; and a working capital criticality score indicating how severe the impact would be if this payment is delayed.

#### A.2.2 Forward Failure Probability Computation

For each payment node in the expectation graph, the system computes a forward failure probability using a time-conditional hazard model. Unlike the reactive system's point-in-time failure prediction, the forward model computes the probability of failure across the entire expected receipt date distribution, integrating over seasonal risk factors, end-of-period liquidity pressures, and counterparty-specific historical delay patterns.

```
P(failure | expected receipt in window [t1, t2]) =
  integral over [t1, t2] of:
    P(payment initiated on day t) × P(failure | initiated on day t) dt
```

The `P(failure | initiated on day t)` term incorporates: time-of-day risk (cutoff violations), day-of-week risk (Friday afternoon payments), banking holiday risk in both jurisdictions, and the counterparty's conditional failure probability given that the payment was initiated on that specific day.

#### A.2.3 Portfolio Gap Distribution and Facility Calibration

Given the failure probability estimates for all expected payments within a forward window — typically 14 to 30 days — the system computes a working capital gap distribution representing the probability distribution over possible total shortfalls the entity might experience.

```
Gap_portfolio = Σ  Amount_i × Bernoulli(PD_i)   for all payments i
```

The standing facility limit is set at the 95th percentile of this gap distribution, meaning the facility covers the payment shortfall in 95% of possible scenarios. The facility pricing uses the portfolio-level expected loss — the sum of CVA values across all payments in the forward window — allocated to a daily facility cost.

### A.3 Draft Claim Elements for Continuation Filing (P4)

> **(a)** analysing a historical and forward-looking payment receipt data stream for a monitored entity to construct a probabilistic payment expectation graph representing anticipated future payment receipts, wherein each node in the graph carries an expected receipt date distribution and an individual failure probability;
>
> **(b)** computing a forward failure probability distribution for each anticipated payment using a time-conditional hazard model that integrates seasonal, temporal, counterparty, and network risk factors over the expected receipt date distribution;
>
> **(c)** aggregating individual payment failure probabilities across the entity's payment portfolio to compute a portfolio-level working capital gap distribution representing the probability distribution of total potential shortfalls across all anticipated receipts within a defined forward window;
>
> **(d)** calibrating a standing liquidity facility limit to a specified quantile of the portfolio gap distribution; and
>
> **(e)** automatically drawing on and releasing the standing facility in real time as individual anticipated payments enter failure or settlement states.

---

## Extension B: Supply Chain Cascade Detection and Prevention System

> **WHAT THIS IS:** When one payment fails, it often triggers a chain of downstream failures across a supply chain network. Company A does not pay Company B, so Company B cannot pay Company C, which cannot pay its material suppliers. A single $100,000 delay can cascade into a $50 million supply chain disruption within 72 hours. This extension describes a system that models payment network topology, detects cascade risk propagation, and coordinates multi-party bridging to prevent the cascade from materialising.

### B.1 The Cascade Risk Problem

Current payment failure systems, including the reactive bridging system in the foundational patent, treat each payment failure as an isolated event. But in a densely interconnected supply chain, payment failures propagate through supplier networks according to predictable topological rules. The propagation speed and severity depend on three factors: the financial leverage of each node in the network, the payment term structure, and the network topology — hub-and-spoke networks propagate failures faster than distributed mesh networks.

### B.2 Supply Chain Payment Network Graph Construction

#### B.2.1 Network Topology Discovery

The system constructs a supply chain payment network graph by analysing the payment patterns of all enrolled entities over time. When Entity A regularly makes payments to Entity B on a predictable schedule, the system infers a supplier-buyer relationship and creates a directed edge in the network graph.

The network graph is represented as G = (V, E, W) where V is the set of enrolled entities, E is the set of inferred payment relationships, and W is a weight matrix encoding payment amount, frequency, timing regularity, and the financial dependency score of the downstream node on the upstream payment. The financial dependency score is derived from the ratio of the upstream payment to the downstream entity's estimated total receivables — a high ratio indicates that the downstream entity is heavily dependent on this specific payment and is vulnerable to cascade failure if it does not arrive.

#### B.2.2 Cascade Propagation Model

When the reactive bridging system detects a payment failure at node A, the cascade detection module activates. It computes a cascade propagation probability for each downstream node:

```
P(cascade to node B | failure at node A) =
  P(B cannot absorb gap)
  × P(B has imminent downstream obligations)
  × (A→B payment amount / B's estimated total receivables)
```

#### B.2.3 Multi-Party Coordinated Bridging

When cascade propagation probability exceeds a threshold across multiple downstream nodes simultaneously, the system activates a coordinated multi-party bridging protocol. The system computes the minimum intervention — the smallest set of entities that, if bridged simultaneously, prevents the cascade from propagating beyond the directly affected nodes.

This is a combinatorial optimisation problem solved using a greedy approximation algorithm that iteratively selects the bridge intervention with the highest ratio of cascade risk reduction to bridge cost, until the total cascade risk falls below threshold T.

### B.3 Draft Claim Elements for Continuation Filing (P5)

> **(f)** constructing and maintaining a directed weighted payment network graph representing inferred supply chain payment relationships between monitored entities, wherein edge weights encode payment dependency ratios, payment regularity, and downstream financial vulnerability;
>
> **(g)** upon detection of a payment failure at any node in the network graph, computing cascade propagation probabilities for all downstream-connected nodes based on financial dependency scores, liquidity reserve estimates, and proximate payment obligations;
>
> **(h)** identifying the minimum-cost set of coordinated bridge interventions that reduces total cascade propagation probability below a specified threshold; and
>
> **(i)** transmitting coordinated bridge offers to multiple affected entities simultaneously, calibrated collectively to contain the cascade within the directly affected network neighbourhood.

### B.4 Pre-Emptive Cascade Risk Assessment

The reactive cascade framework above activates after an upstream payment failure has already been observed. A broader continuation position should also preserve the scenario in which the system detects elevated cascade risk before any individual payment has yet entered a failure state. This pre-emptive cascade mode combines the forward failure probability methodology of Extension A with the supply chain payment network graph of Extension B.

For each node in the network graph, the system computes a forward failure probability distribution over anticipated payment obligations in a future window. These node-level forward probabilities are then propagated through the weighted dependency graph to estimate the probability that distress at one or more upstream nodes will generate a multi-node liquidity shortfall across the network neighbourhood. Where the aggregate cascade probability exceeds a threshold, the system proactively calibrates coordinated bridge capacity for the affected neighbourhood before the first payment failure occurs.

This architecture is materially different from both reactive cascade containment and single-entity pre-emptive bridging. The innovation lies in jointly modelling forward failure risk and topological dependency so that the system can intervene at the network level before the cascade manifests.

#### B.4.1 Draft Claim Elements for Pre-Emptive Cascade Prevention

> **(i-1)** computing, for multiple nodes in a directed payment dependency graph, forward failure probability distributions over anticipated payment obligations within a defined future window;
>
> **(i-2)** propagating said forward failure probability distributions through the dependency graph to estimate a network-level cascade probability for one or more supply chain neighbourhoods prior to any observed payment failure event;
>
> **(i-3)** identifying a coordinated set of pre-emptive bridge facilities or contingent liquidity commitments that reduces the projected cascade probability below a specified threshold before the first upstream failure occurs; and
>
> **(i-4)** transmitting or establishing said coordinated pre-emptive bridge facilities for the identified neighbourhood prior to detection of any live payment rejection or delay event.

---

## Extension C: AI-Powered Autonomous Treasury Management Agent

> **WHAT THIS IS:** The foundational system acts when payments fail. This extension describes a system that continuously manages an entity's entire cross-border payment portfolio autonomously — predicting failures, optimising payment sequencing, pre-hedging FX exposure, managing bridge facility drawdowns, and generating real-time treasury analytics — without human intervention. It is, effectively, an AI treasury department for mid-market companies that cannot afford a human one.

### C.1 The Treasury Management Gap

Effective treasury management for a company with $50M to $500M in cross-border payment activity requires continuous monitoring of payment flows, FX exposure, counterparty credit risk, and working capital position — tasks that currently require a dedicated treasury team of three to eight people at major corporations. Mid-market companies cannot afford this, leaving them exposed to payment timing risk, FX losses, and working capital gaps that sophisticated treasury management would prevent.

### C.2 Core Agent Architecture

#### C.2.1 Multi-Horizon Payment Portfolio Model

The agent maintains a continuously updated model of the entity's complete payment portfolio across three time horizons:

| **Horizon** | **Window** | **Contents** |
|-------------|-----------|--------------|
| Immediate | 0–7 days | Confirmed payment instructions in progress, monitored by the reactive bridging system |
| Near | 7–30 days | Anticipated payments from the pre-emptive system's expectation graph |
| Medium | 30–90 days | Scheduled payments from contracted obligations, purchase orders, and recurring supplier relationships |

Each payment in all three horizons carries a probability distribution over settlement timing and a CVA-based expected loss estimate.

#### C.2.2 FX Exposure Management Integration

When the agent identifies a payment in the near or medium horizon carrying material FX risk, it computes the optimal hedging strategy. For payments with high failure probability, the agent reduces the hedge ratio proportionally, because hedging a payment that may not arrive exposes the entity to a speculative FX position rather than a defensive one.

```
Optimal Hedge Ratio = (1 − PD_payment) × Standard Hedge Ratio
```

This probability-adjusted hedging formula integrates payment failure risk into FX exposure management — a combination that no existing treasury system implements. The agent places FX hedging instructions via API to the entity's bank or FX platform, adjusting the hedge in real time as the payment failure probability evolves.

#### C.2.3 Autonomous Decision-Making Framework

The agent operates within a configurable decision authority framework with three tiers:

> **Below lower authority boundary:** Agent acts without human approval — drawing on credit facilities, placing FX hedges, triggering bridge loan activations.
>
> **Between lower and upper authority boundaries:** Agent prepares recommendations and submits to designated approver via API notification, activating automatically if no response within specified timeout.
>
> **Above upper authority boundary:** Agent requires explicit human approval before acting.

This authority framework is patentable in its own right as a novel architecture for human-AI collaborative decision-making in financial operations.

### C.3 Draft Claim Elements for Continuation Filing (P8)

> **(j)** maintaining a multi-horizon payment portfolio model covering immediate, near-term, and medium-term payment flows with probability distributions over settlement timing and CVA-based expected loss estimates for each horizon;
>
> **(k)** computing probability-adjusted FX hedge ratios for anticipated cross-currency payments that integrate payment failure probability into the hedging decision, reducing hedge exposure proportionally to the probability that the underlying payment will not materialise;
>
> **(l)** executing autonomous treasury decisions within a configurable decision authority framework that defines the boundaries of autonomous action, the escalation pathway for decisions above the autonomous threshold, and the timeout-triggered activation mechanism for pending recommendations; and
>
> **(m)** continuously updating the portfolio model, hedge positions, and credit facility drawdown levels in real time as payment status events are received from the payment network monitoring layer.

---

## Extension D: Tokenised Receivable Liquidity Pool Architecture

> **WHAT THIS IS:** Instead of a single bank funding each bridge loan, the underlying payment receivable is tokenised — converted into a digital asset representing the right to receive the delayed payment — and auctioned in real time to a competitive pool of institutional investors. Competitive bidding drives the cost of capital down for receivers and creates a new class of short-duration, high-quality asset for institutional investors.

### D.1 The Capital Markets Transformation

The foundational system positions liquidity bridging as a bilateral credit product between a technology platform and a receiver, funded from a bank's balance sheet. The tokenised receivable pool architecture eliminates this ceiling by replacing bilateral bank funding with competitive institutional investor bidding, achieving market-rate pricing for each bridge transaction.

A tokenised receivable is a digital representation of the contractual right to receive a specific payment when it eventually settles. Because the payment is being tracked in real time via SWIFT gpi UETR, the settlement status of the tokenised receivable is continuously observable and verifiable by all participants. This makes the receivable a uniquely attractive asset for institutional investors: it is short-duration (1 to 7 days), it has a clear redemption trigger (settlement of the tracked payment), and its probability of full recovery can be independently verified using the CVA pricing methodology documented in the foundational patent.

### D.2 Technical Architecture

#### D.2.1 Tokenisation Layer

When the failure prediction engine flags a payment and the CVA engine prices the associated risk, the system simultaneously generates a digital token representing the right to receive the delayed payment. The token is a cryptographically signed data structure containing: the tracked payment's UETR identifier enabling real-time status verification; the expected payment amount; the receiver's identity for legal assignment of the receivable; the CVA-derived recovery probability; and a settlement date estimate with confidence interval.

The token is not necessarily a blockchain-based asset. The tokenisation layer can operate on any cryptographically secure digital ledger, including a permissioned institutional ledger. The key technical element is the cryptographic binding of the token to the live UETR tracking data.

#### D.2.2 Real-Time Competitive Dutch Auction Mechanism

The auction operates as a Dutch auction: starting from the CVA-derived fair value price and descending in real time until a bid is received. The Dutch auction mechanism is chosen over ascending auctions because time is critical — the receiver needs funds in minutes, not hours. A Dutch auction converges to the market-clearing price more rapidly because the first bidder to accept terminates the auction immediately.

The auction opening price is set at the CVA-derived expected loss, which represents the fair compensation to a risk-neutral investor for purchasing the receivable. The first investor to submit a bid at or above the current auction price wins the auction. The receiver receives the advance — principal minus the winning discount — within 60 seconds of auction completion.

#### D.2.3 Settlement and Redemption

The settlement monitoring component continuously tracks the original payment UETR. When the payment settles, the system automatically redeems the token: the full payment amount is credited to the token holder, not the original receiver. If the original payment fails entirely, the token holder's recovery depends on the collateral arrangement established at token issuance — in the standard implementation, the original payment receivable is legally assigned to the token holder at issuance.

### D.3 Draft Claim Elements for Continuation Filing (P7)

> **(n)** responsive to a payment failure prediction signal, generating a digital receivable token cryptographically bound to a specific in-flight payment transaction identifier, representing the right to receive the payment proceeds upon settlement;
>
> **(o)** initiating a time-constrained competitive Dutch auction of the digital receivable token among a pool of pre-qualified institutional liquidity providers, wherein the auction price is initialised at the CVA-derived expected recovery value and converges to a market-clearing discount through competitive bidding;
>
> **(p)** transmitting the auction proceeds — principal minus clearing discount — to the payment receiver as a liquidity advance upon auction completion; and
>
> **(q)** automatically redeeming the digital receivable token and crediting the winning bidder upon confirmation of settlement of the original payment transaction, or activating the collateral recovery mechanism in the event of permanent payment failure.

---

## Extension E: CBDC Settlement Failure Detection and Bridging

> **WHAT THIS IS:** Central bank digital currencies introduce an entirely new category of payment infrastructure with fundamentally different failure modes from correspondent banking. Smart contract execution failures, interoperability protocol errors between CBDC networks, and cryptographic validation failures will be the ISO 20022 rejection codes of the CBDC era. This extension describes the application of the foundational system's architecture to CBDC payment rails.

### E.1 CBDC-Specific Failure Modes

CBDC payment failures differ from correspondent banking failures in three important respects.

> **Programme-generated failure signals:** A smart contract executing on a CBDC platform produces a machine-readable error code when a transaction fails, analogous to but structurally different from a pacs.002 rejection message.
>
> **Cross-chain interoperability failures:** Where a payment attempts to move from one CBDC network to another and fails at the interoperability bridge — these have no equivalent in the current correspondent banking system.
>
> **Programmatic settlement finality:** CBDC transactions achieve programmatic finality when the smart contract execution is confirmed, but can fail at the execution stage in ways that correspondent banking transactions cannot.

### E.2 CBDC Monitoring Architecture

#### E.2.1 CBDC Event Stream Parsing and Normalisation

The system connects to CBDC network event streams via API or webhook interfaces provided by each CBDC platform. Unlike ISO 20022 message parsing, CBDC event parsing must handle platform-specific event schemas that will vary across implementations from different central banks. The system implements a CBDC event normalisation layer that translates platform-specific failure events into a standardised internal representation compatible with the foundational system's feature engineering pipeline.

| **CBDC Failure Type** | **ISO 20022 Analog** | **Severity Classification** |
|-----------------------|---------------------|----------------------------|
| Smart contract execution failure | ED05 | High — unambiguous failure event |
| Insufficient CBDC wallet balance | AM04 | High — same as insufficient funds |
| Interoperability protocol error at cross-chain bridge | (New — no ISO 20022 equivalent) | Critical — may indicate systemic issue |
| Cryptographic signature validation failure | (New — no ISO 20022 equivalent) | High — unambiguous rejection |
| CBDC network congestion delay | (Network-specific) | Medium — time-sensitive, may self-resolve |

### E.3 Draft Claim Elements for Continuation Filing (P6)

> **STRATEGIC PRIORITY:** CBDC interoperability standards are expected to be established approximately 5–6 years after foundational filing based on current G20 CBDC development timelines. Continuation patent P6 should be filed within 12 months of the publication of the first major international CBDC interoperability standard, capturing the architectural pattern before it becomes obvious from the standard itself.
>
> **(r)** monitoring a continuous stream of settlement event data from one or more central bank digital currency networks, including smart contract execution events, interoperability protocol events, and wallet validation events;
>
> **(s)** extracting failure indicators from CBDC settlement events using a normalisation layer that translates platform-specific event schemas into a standardised failure classification taxonomy;
>
> **(t)** applying the machine learning failure prediction methodology of the foundational system to CBDC payment transactions, using CBDC-specific feature representations adapted to the technical characteristics of programmable money settlement; and
>
> **(u)** providing automated liquidity bridging to CBDC payment receivers experiencing settlement delays or failures, using any financial instrument appropriate for the CBDC regulatory and technical context.

---

## Extension F: Multi-Party Distributed Architecture *(NEW IN v2.0)*

> **WHAT THIS IS:** A competitor or design-around attempt could argue that no single entity 'performs' all steps of the foundational method claims because each system component — payment network monitoring, ML inference, and liquidity execution — is operated by a different legal entity under a commercial arrangement. This extension discloses the three-entity distributed architecture — monitoring operator, inference provider, and executing bank — and provides the technical and contractual framework that closes the divided infringement design-around vector. The continuation patent P3 claiming this architecture should be filed before Bridgepoint's first commercial deployment is publicly announced.

### F.1 The Divided Infringement Problem and Why It Must Be Closed

Under *Akamai Technologies, Inc. v. Limelight Networks, Inc.* (Fed. Cir. 2015 en banc), divided infringement of a method claim occurs when no single entity performs all the steps of the claimed method. For a system as commercially deployable as the foundational architecture — where a bank provides the monitoring infrastructure, a fintech platform provides the ML inference engine, and a separate lending entity provides the liquidity execution — a sophisticated competitor or accused infringer could structure their implementation across three entities and argue that no single entity performs Claim 1's complete method.

The standard legal response to divided infringement is to demonstrate that one entity 'directs or controls' the others or that the entities form a 'joint enterprise' under the *Akamai* standard. But a more robust response is to claim the distributed architecture affirmatively — to describe the multi-entity structure as a specific disclosed embodiment, so that the continuation patent P3 covers the distributed arrangement as claimed subject matter rather than leaving it as an unintended gap.

### F.2 The Three-Entity Framework: MLO, MIPLO, and ELO

The distributed architecture of the Liquidity Intelligence Platform involves three functional roles that may be performed by the same entity or by separate entities under contractual arrangement.

#### F.2.1 The Monitoring and Liquidity Origination Entity (MLO)

The MLO is the entity that deploys the payment network monitoring component — step (a) of Claim 1, element (i) of Claim 2 — and that originates the liquidity provision offer — step (f) of Claim 1. The MLO may be a payment network operator, a correspondent bank with existing infrastructure on ISO 20022 message networks, or a fintech platform with direct API access to payment gateways.

In commercial deployment, the MLO receives a per-transaction technology licensing fee from the MIPLO or ELO, rather than holding the lending position itself. The MLO's contractual obligations to the MIPLO include: providing real-time payment status data via a standardised API at defined latency standards; providing the output of the failure prediction model with calibrated probability scores; and transmitting the liquidity provision offer to the payment receiver on behalf of the ELO.

#### F.2.2 The ML Inference and Pricing Licensing Organisation (MIPLO)

The MIPLO is the entity that operates the ML inference engine — step (c) of Claim 1, element (ii) of Claim 2 — and the counterparty risk assessment and liquidity pricing components — steps (d) and (e) of Claim 1, elements (iii) and (iv) of Claim 2. The MIPLO is Bridgepoint Intelligence Inc. itself in the commercial licensing model.

The MIPLO receives a continuous stream of payment feature vectors from the MLO via API, runs inference to produce failure probability scores and PD-based pricing, and transmits the results back to the MLO and ELO. The MIPLO does not hold any lending position and does not interact with the payment receiver directly. Its revenue is a licensing fee charged to the ELO per transaction processed.

The MIPLO API specification exposes three endpoints: a `/score` endpoint accepting a payment feature vector and returning a failure probability score with calibration metadata; a `/price` endpoint accepting counterparty financial data and advance duration and returning a risk-adjusted cost rate; and a `/monitor` endpoint accepting a UETR and returning real-time settlement status.

#### F.2.3 The Executing and Lending Organisation (ELO)

The ELO is the entity that executes the liquidity provision — steps (g) and (h) of Claim 1, elements (v) and (vi) of Claim 2. The ELO is a licensed financial institution — a bank, a regulated fintech lender, or a trade finance provider — that holds the lending position, disbursing bridge loans from its own balance sheet and collecting repayment upon settlement confirmation.

The ELO receives failure probability scores and pricing from the MIPLO via API, receives the liquidity provision offer parameters from the MLO, and makes the final lending decision within its own credit authority framework. The ELO is the lender of record, holds the perfected security interest in the payment receivable, and bears the credit risk of the advance.

### F.3 API Architecture and Data Flow Specification

The three-entity architecture operates through a defined API data flow:

```
Step 1: ISO 20022 pacs.002 message arrives at MLO monitoring infrastructure

Step 2: MLO extracts feature vector and calls MIPLO /score endpoint
        Request:  { uetr, payment_features, counterparty_bic, corridor }
        Response: { failure_probability, calibration_score, model_version }

Step 3: If failure_probability > threshold, MLO calls MIPLO /price endpoint
        Request:  { counterparty_id, advance_amount, advance_duration_days }
        Response: { pd_estimate, lgd_estimate, cost_rate_bps, tier_used }

Step 4: MLO packages offer parameters and transmits to ELO via secure API
        Message:  { uetr, receiver_id, advance_amount, cost_rate_bps, collateral_terms }

Step 5: ELO makes lending decision within its credit authority framework

Step 6: If approved, ELO disburses advance and registers security interest

Step 7: MLO monitors UETR for settlement; notifies ELO on settlement event

Step 8: ELO triggers repayment collection on settlement confirmation
```

### F.4 Contractual Framework for Joint Enterprise Compliance

For the three-entity arrangement to constitute a 'joint enterprise' under the *Akamai* standard — ensuring that infringement is not divided — the commercial agreements between MLO, MIPLO, and ELO must establish five elements: a common purpose (the provision of automated liquidity bridging services to payment receivers), a community of proprietary interest in that purpose (revenue sharing based on transaction outcomes), an equal right to direct and control the conduct of each other with respect to the common purpose (joint operational governance committee with defined escalation rights), a voluntary agreement to enter the enterprise (signed technology licensing and services agreement), and a mutual right to terminate the arrangement (termination provisions with data return and IP assignment obligations).

The legal opinion obtained under Amendment C.3 of the operational playbook should confirm whether this contractual framework satisfies the *Akamai* joint enterprise standard in each operating jurisdiction.

### F.5 Draft Claim Elements for Continuation Filing (P3)

> **FILING URGENCY:** P3 should be filed before Bridgepoint's first commercial deployment is publicly announced, because once the commercial arrangement is publicly known, a competitor can observe the distributed structure and design an implementation that pre-dates P3's filing. Filing P3 during prosecution of P2 — before P2 issues — preserves the broadest continuation scope.
>
> **(v)** providing, by a first entity operating a payment network monitoring component, real-time payment status event data and failure probability scores derived from said data to a second entity operating an ML inference and pricing component, pursuant to a technology licensing agreement that establishes a common commercial purpose between the first and second entities;
>
> **(w)** receiving, by a third entity operating a liquidity execution component, the failure probability scores and risk-adjusted pricing computed by the second entity, and independently applying the third entity's credit authority framework to make a final lending decision on each flagged payment event;
>
> **(x)** executing, by the third entity, a liquidity disbursement to the affected payment receiver, establishing a perfected security interest in the delayed payment receivable as collateral for the advance, wherein the security interest is established in the name of the third entity as lender of record regardless of the distributed arrangement among the three entities;
>
> **(y)** monitoring, by the first entity, the settlement status of the original payment transaction and transmitting a settlement confirmation event to the third entity upon detection of settlement; and
>
> **(z)** collecting repayment, by the third entity, upon receipt of the settlement confirmation event from the first entity, wherein the complete sequence of steps (v) through (z) constitutes a joint enterprise among the three entities as defined by the contractual arrangement establishing their common purpose and mutual rights of control.

---

## Extension G: Adversarial Payment Cancellation Detection and Security Interest Preservation *(NEW IN v2.0)*

> **WHAT THIS IS:** After a bridge loan is disbursed against a delayed payment, the original payment sender may issue a camt.056 Payment Cancellation Request — the ISO 20022 message used to recall a payment in transit. If the receiving bank accepts this cancellation via a pacs.004 return message, the receivable that secures the bridge loan is extinguished, converting a secured advance into an unsecured one. This extension describes the dual-stream monitoring architecture and ML classifier that distinguish between legitimate error-correction cancellations and adversarial cancellations, and the security interest preservation workflow that activates before the receiving bank can accept the cancellation. This extension corresponds directly to Dependent Claim D13 in the current prosecution-ready provisional specification.

### G.1 The Adversarial Cancellation Attack Vector

The auto-repayment loop of Independent Claim 5 depends on the original payment eventually settling — when it does, repayment is collected from the settlement proceeds. The security interest in the delayed payment receivable is the collateral that protects the lender in the event of permanent failure. Both of these mechanisms are undermined if the original payment sender can cancel the payment after the bridge loan has been disbursed.

Under ISO 20022 standards, a payment sender can issue a camt.056 FI-to-FI Payment Cancellation Request at any point before final settlement. The receiving bank has discretion to accept or reject the cancellation. If accepted, the receiving bank returns the funds to the sender via a pacs.004 Payment Return message. At the moment of pacs.004 processing, the receivable that secures the bridge loan is extinguished — the payment that was expected to arrive and repay the advance will instead be returned to the sender.

The adversarial scenario unfolds as follows: (1) the payment enters a delay state; (2) the bridge loan is disbursed to the receiver; (3) the original sender, aware that the receiver now has bridge funding and will not immediately notice the non-arrival of the original payment, issues a camt.056 cancellation request on the grounds that the payment was made in error; (4) the receiving bank, lacking awareness of the bridge loan, accepts the cancellation and issues a pacs.004 return; (5) the bridge loan is now unsecured — the collateral has been returned to the sender. The sender retains both the original payment amount and has effectively transferred the credit risk of the advance to the lender.

This is not a hypothetical scenario. In correspondent banking operations, fraudulent payment recall requests are documented. The camt.056 mechanism, designed for legitimate error correction, is exploitable in any system that disburses advances against receivables without monitoring for concurrent cancellation activity.

### G.2 Dual-Stream Monitoring Architecture

The adversarial cancellation detection system operates a dual-stream monitoring architecture that runs in parallel with the existing settlement monitoring stream.

#### G.2.1 Primary Stream: Settlement Monitoring (Existing)

The primary stream, described in Independent Claim 5 and element (vi) of Claim 2, monitors SWIFT gpi UETR tracking data, ISO 20022 pacs.002 status messages, and equivalent settlement confirmation events. Its purpose is to detect when the original payment settles so that repayment can be collected.

#### G.2.2 Secondary Stream: Cancellation Message Monitoring (New in v2.0)

The secondary stream monitors three parallel message channels for cancellation activity on any active advance record, keyed to the UETR of the original payment.

| **Message Type** | **ISO 20022 Code** | **SWIFT MT Equivalent** | **Trigger Condition** |
|-----------------|-------------------|------------------------|----------------------|
| FI-to-FI Payment Cancellation Request | camt.056 | MT n92 | Any cancellation request received with matching UETR while advance is active |
| Customer Credit Transfer Cancellation Request | camt.055 | MT 192 | Any cancellation request from the payment originator's customer |
| Payment Return | pacs.004 | MT 202 RTN / MT 900 | Return initiated on a payment for which an advance is active — critical alert |
| Resolution of Investigation | camt.029 | MT 999 | Cancellation accepted or rejected — determines outcome of security interest preservation workflow |

The secondary stream uses the UETR as the primary key linking cancellation messages to active advance records. Every advance record in the system carries the UETR of the original payment as a persistent attribute from the moment of disbursement. The secondary stream processes all incoming camt.056, camt.055, pacs.004, and camt.029 messages and queries the active advance records table for UETR matches on each message received.

### G.3 ML Classifier: Intent Classification of Cancellation Requests

Not all camt.056 cancellation requests are adversarial. The majority are legitimate error-correction messages — duplicate payments, wrong-amount corrections, wrong-beneficiary corrections. The ML classifier distinguishes between two classes of cancellation intent.

#### G.3.1 Class Labels

> **Class 0 — Error-Correction Cancellation:** Legitimate cancellation issued to correct a genuine payment error. The payment should be cancelled; the bridge loan should be immediately flagged for accelerated recovery from the receiver.
>
> **Class 1 — Adversarial Cancellation:** Cancellation issued to extinguish a receivable after a bridge loan has been disbursed, with the intent of avoiding repayment by eliminating the collateral. The security interest preservation workflow must activate before the receiving bank processes the cancellation.

#### G.3.2 Feature Set for the Classifier

The classifier operates on three feature categories that, in combination, distinguish adversarial from error-correction cancellations with statistically significant precision.

| **Feature Category** | **Specific Features** | **Adversarial Signal Direction** |
|---------------------|----------------------|----------------------------------|
| Temporal features | Time elapsed between advance disbursement and cancellation request arrival; time elapsed between original payment initiation and cancellation request; whether cancellation arrived within vs. outside business hours in sender jurisdiction | Adversarial cancellations cluster in the 2–48 hour window after disbursement — late enough for the advance to have been received, early enough to prevent recovery |
| Reason code features | ISO 20022 reason code on camt.056 message (DUPL = duplicate, CUST = customer request, UPAY = undue payment, AM09 = wrong amount, AC03 = wrong beneficiary); historical rate of same reason code from this sender | CUST and UPAY reason codes with no prior use from this sender BIC, arriving after advance disbursement, are strongest adversarial indicators |
| Originator behaviour features | Sender's historical camt.056 submission rate on this corridor; sender's payment completion rate on prior transactions; whether sender has any other active advances in the system; sender's prior cancellation success rate with the receiving bank | First-time cancellation from a sender with high historical completion rates, coinciding with an active advance, is strongest combined adversarial signal |

#### G.3.3 Model Architecture

The adversarial cancellation classifier is a binary classification model trained on labelled historical camt.056 events. Given the low base rate of genuine adversarial cancellations, the training dataset requires oversampling of adversarial examples and the classification threshold is calibrated to minimise false negatives — erring on the side of triggering the security interest preservation workflow — because the cost of failing to detect an adversarial cancellation (unsecured advance exposure) exceeds the cost of a false positive (unnecessary legal workflow that is subsequently resolved). The same cost-asymmetric F-beta threshold optimisation described in Dependent Claim D3 is applied here.

### G.4 Security Interest Preservation Workflow

When the classifier generates a Class 1 prediction — adversarial cancellation — or when the system detects a pacs.004 return on a payment with an active advance regardless of classifier output, the security interest preservation workflow activates. The workflow operates on a defined sequence with strict timing requirements.

#### G.4.1 Immediate Notification (within 60 seconds of camt.056 detection)

The system generates an automated legal notice addressed to the receiving financial institution asserting: (1) the existence of a perfected security interest in the delayed payment proceeds, established by a written assignment agreement executed at the time of advance disbursement; (2) the legal identity of the secured party (the ELO); (3) the UETR of the original payment and the amount of the advance secured against it; and (4) a formal objection to the processing of the cancellation request pending legal review of the competing claims.

This notice is transmitted via SWIFT Exceptions and Investigations messaging (camt message series), via email to the receiving institution's compliance and legal operations teams, and via any API notification channel available through the pilot or production integration agreement.

#### G.4.2 camt.029 Interception Protocol

In the standard ISO 20022 cancellation workflow, the receiving bank responds to the camt.056 with a camt.029 Resolution of Investigation message indicating whether the cancellation is accepted (ACCP) or rejected (RJCT). The security interest preservation workflow seeks to influence this outcome by ensuring the receiving bank has actual knowledge of the competing security interest before it issues the camt.029.

If the receiving bank issues a camt.029 with ACCP status — indicating it has accepted the cancellation and will process the pacs.004 return — the workflow immediately escalates to the pacs.004 interception step.

#### G.4.3 pacs.004 Return Funds Interception

When a pacs.004 return is issued by the receiving bank in response to an accepted cancellation on a payment with an active advance, the system initiates a legal claim against the return funds on behalf of the ELO. The claim asserts that the returned funds represent the proceeds of a receivable in which the ELO holds a perfected prior security interest, and that the return of those funds to the original sender without satisfying the secured advance constitutes conversion of secured property.

This claim is transmitted via Exceptions and Investigations messaging to both the sending and receiving financial institutions, and is contemporaneously registered with the legal counsel identified in the ELO's advance agreement. Whether this claim is ultimately successful depends on the jurisdiction-specific enforceability analysis described in Amendment C.3 of the operational playbook — which is precisely why that analysis must be completed before any live advance is disbursed.

#### G.4.4 Adversarial Cancellation Event Record

Regardless of the outcome of the security interest preservation workflow, the system generates a complete adversarial cancellation event record containing: the UETR of the original payment; the advance disbursement details; all camt and pacs messages exchanged during the cancellation attempt; the classifier prediction with feature values and confidence score; the timeline of the security interest preservation workflow actions taken; and the final resolution — whether the cancellation was reversed, whether the advance was repaid from alternative sources, or whether a loss was realised.

This event record serves three purposes: regulatory audit trail for the ELO's compliance function; training data for the adversarial cancellation classifier to improve future predictions; and evidentiary record for any legal proceedings arising from the cancellation attempt.

### G.5 Draft Claim Elements for Continuation Filing (P3 Addition / Dependent Claim D13)

> **RELATIONSHIP TO D13:** The claim elements below are already captured in Dependent Claim D13 of the current prosecution-ready provisional specification. This section provides the extended technical disclosure needed for (1) a broader independent continuation claim in P3 that covers the security interest preservation workflow independently of Claim 5, and (2) the specific architecture details that a patent attorney will need to draft comprehensive continuation claims covering the dual-stream monitoring, classifier architecture, and pacs.004 interception protocol as separate protectable elements.
>
> **(aa)** monitoring, by a secondary message stream operating in parallel with and keyed to the same payment transaction identifiers as the primary settlement monitoring stream, a plurality of ISO 20022 cancellation and return message channels including camt.056 FI-to-FI Payment Cancellation Request, camt.055 Customer Credit Transfer Cancellation Request, pacs.004 Payment Return, and camt.029 Resolution of Investigation;
>
> **(bb)** upon detection of any message in the monitored cancellation channels that references a payment transaction identifier associated with an active disbursed liquidity advance, generating a binary classification of cancellation intent using a trained machine learning classifier that operates on temporal features, rejection reason code features, and originator behaviour features derived from the cancellation message and the originating entity's transaction history;
>
> **(cc)** responsive to a classifier output indicating adversarial cancellation intent, or responsive to detection of a pacs.004 return on a payment with an active advance regardless of classifier output, initiating a security interest preservation workflow comprising: transmitting a notice of competing security interest to the receiving financial institution via Exceptions and Investigations messaging, asserting the secured party's prior perfected security interest in the payment proceeds established at advance disbursement;
>
> **(dd)** upon detection of a camt.029 Resolution of Investigation message with acceptance status on a payment with an active advance, escalating the security interest assertion to a legal claim against the pacs.004 return funds, asserting that the funds represent proceeds of a receivable subject to a prior perfected security interest; and
>
> **(ee)** generating a complete adversarial cancellation event record comprising all cancellation and return messages exchanged, the classifier prediction with feature values and confidence score, all security interest preservation workflow actions taken and their timestamps, and the final resolution of the competing claims, for regulatory audit, model training, and legal evidentiary purposes.

---

## Why This Document Is as Important as the Patent Itself

Every technology described in this document was conceived before the provisional patent filing. The foundational system is not merely a reactive bridging tool — it is an intelligence platform whose architecture naturally extends to pre-emptive liquidity management, supply chain risk prevention, autonomous treasury management, capital markets transformation of trade receivables, CBDC infrastructure, distributed multi-party commercial deployment, and adversarial event detection.

The purpose of this document is to memorialise that fact in writing, with sufficient technical specificity that a patent attorney can draft continuation claims for P3 through P10 at the appropriate filing times, claiming the benefit of the original provisional priority date. Without this document, each extension would need to be filed as a new application with a new priority date, making each one vulnerable to the decade of prior art that will accumulate in the payments technology space between now and then.

As deployment data accumulates, as banking partnerships deepen, and as the technology evolves in ways that cannot be fully anticipated today, new extensions will emerge. Each one should be documented in an internal disclosure memo as it is conceived, and the patent attorney should be notified annually to assess which disclosures have ripened into continuation-worthy claims.

---

## Filing Trigger Table

*All filing offsets are stated relative to the Provisional Filing Date (PFD = Year 0). Absolute calendar years are not used — all deadlines are relative to the PFD, which is to be confirmed at attorney engagement.*

| **Extension** | **Target Continuation** | **Target Filing Offset** | **Filing Trigger** |
|---------------|------------------------|--------------------------|-------------------|
| F — Multi-Party Distributed | P3 | ~PFD + Year 2 | File before P2 issues AND before first commercial deployment is publicly announced |
| G — Adversarial Cancellation | P3 / D13 | D13 included in P2 at PFD + Year 1; broader P3 claim at ~PFD + Year 2 | D13 already in provisional; broader independent claim filed with P3 |
| A — Pre-Emptive Bridging | P4 | ~PFD + Year 3 | File when first pre-emptive product feature is commercially tested; most time-sensitive continuation |
| B — Supply Chain Cascade | P5 | ~PFD + Year 4 | File when cascade detection feature is integrated into pilot deployment |
| E — CBDC Bridging | P6 | Within 12 months of first major CBDC interoperability standard publication (~PFD + Year 5–6) | Monitor G20 CBDC working group publications |
| D — Tokenised Receivables | P7 | ~PFD + Year 6 | File when tokenisation market infrastructure is sufficiently developed to validate commercial utility |
| C — Autonomous Treasury | P8 | ~PFD + Year 7 | File when AI agent architecture is validated in production deployment |

> **THE FINAL WORD:** The best patent portfolio in the world cannot protect an idea that was not written down. Every time a new technical capability is conceived — even informally, even in a conversation — the next step is a dated, signed memo describing the technical concept in sufficient detail for a patent attorney to work from. This document is that memo for seven extensions. The habit of writing it is the discipline that separates inventors who build durable IP empires from those who watch others profit from their own ideas.

---

**— END OF FUTURE TECHNOLOGY DISCLOSURE v2.1 —**

**TRADE SECRET — ATTORNEY-CLIENT PRIVILEGED — DO NOT DISTRIBUTE**

---

*Version 2.1 corrections: (A) Foundational-specification references updated from the old v5.0 placeholder to the current prosecution-ready provisional package. (B) Filing Trigger Table updated to replace absolute calendar years (2028, 2029, 2031, 2033, 2034) with PFD-relative offset language, consistent with Patent Family Architecture v2.1 offset convention. (C) Extension E.3 strategic priority note updated from absolute year range to PFD-relative offset (~Year 5–6). (D) Continuation Patents metadata field updated to reference PFD offset language. (E) Extension B now expressly includes pre-emptive cascade prevention disclosure. All other technical content, extension descriptions, claim draft elements (a)–(ee), and strategic guidance unchanged.*
