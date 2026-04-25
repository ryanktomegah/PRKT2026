# LIP Patent Claims — Consolidated Draft
## For Patent Counsel Review — Pre-Non-Provisional Filing
**Status**: Draft — all claims reviewed against source code and architecture docs  
**Repo ref**: PRKT2026 @ main  
**Last updated**: 2026-04-09  
**Prepared by**: Bridgepoint Intelligence (patent counsel briefing session)

> **Language scrub rule (EPG-21)**: All regulatory language has been replaced per the  
> substitution table in `patent_counsel_briefing.md`.

---

## Patent Family 1 — ISO 20022 Failure Taxonomy & Dual-Layer Bridge Lending Pipeline

### Independent Claim 1

A computer-implemented method for gating a real-time autonomous bridge lending pipeline based on an ISO 20022 payment failure classification taxonomy, the method comprising:

- receiving, by a processor, an ISO 20022 payment failure message comprising an ISO 20022 rejection reason code;
- evaluating the ISO 20022 rejection reason code against a three-class taxonomy consisting of a permanent failure class, a systemic delay class, and a hold-type classification class;
- routing the transaction to a machine learning inference engine, a probability of default solver, a fee computation engine, and a funds disbursement service to evaluate bridge loan eligibility in response to determining the ISO 20022 rejection reason code belongs to the permanent failure class or the systemic delay class; and
- short-circuiting the pipeline prior to invoking any of the machine learning inference engine, the probability of default solver, the fee computation engine, or the funds disbursement service in response to determining the ISO 20022 rejection reason code belongs to the hold-type classification class, regardless of pipeline gate position.

### Dependent Claim 2

The computer-implemented method of claim 1, wherein evaluating the ISO 20022 rejection reason code comprises verifying whether the rejection reason code belongs to the hold-type classification class prior to evaluating the permanent failure class and the systemic delay class, and wherein short-circuiting the pipeline comprises:

- outputting a logically distinct hold-type classification outcome that is machine-readable and distinguishable from both a loan declined status and a payment processing error status; and
- persisting the hold-type classification outcome to an immutable decision log entry for regulatory audit examination, wherein the decision log entry includes a halt reason field that identifies the outcome as a hold-type classification for purposes of regulatory examination under applicable financial integrity reporting requirements.

### Dependent Claim 3

The computer-implemented method of claim 2, further comprising enforcing a defense-in-depth architecture by:

- applying the short-circuiting as a primary gating layer upstream of all pipeline inference components; and
- independently verifying, by a downstream autonomous execution agent, the ISO 20022 rejection reason code against a predefined frozenset of hold-type classification codes as a secondary gating layer to prevent bridge loan offer generation and funds disbursement on any payment event bearing a hold-type classification;

wherein the ISO 20022 rejection reason code evaluated at both the primary and secondary gating layers is first normalized from a proprietary payment rail rejection code — from at least one of a FedNow rail, an RTP rail, a SEPA rail, or a CBDC rail — into a canonical ISO 20022 rejection reason code by a streaming normalization component, and the normalized code is used uniformly by both layers.

### Dependent Claim 4 — Hold-Type Classification Gate

The computer-implemented method of claim 2, wherein the hold-type classification class comprises at least a code in the non-bridgeable set defined in an internal taxonomy external to this claim, wherein each code in the hold-type classification class independently triggers a hold-type classification outcome regardless of any other pipeline conditions.

### Dependent Claim 5 — B1/B2 Sub-Classification Gate

The computer-implemented method of claim 1, further comprising applying a second classification gate to a payment event classified within a procedural-hold sub-class of the hold-type classification class, the second classification gate:

- receiving a bridgeability certification signal from the originating financial institution; and
- classifying the payment event as either a procedural-hold (bridgeable upon certification) or an investigatory-hold (permanently blocked);

wherein the second classification gate routes procedural-hold events back into the bridge lending pipeline upon receipt of a positive bridgeability certification, and routes investigatory-hold events to a hard-block outcome independent of any bridgeability certification.

---

## Patent Family 2 — Multi-Rail Settlement Monitoring & Maturity Calculation

### Independent Claim 1 (System)

A multi-rail settlement monitoring and maturity calculation system for bridge loans, the system comprising at least one processor and a memory storing instructions that, when executed, cause the system to:

- receive payment event streams from a plurality of distinct settlement rails comprising a SWIFT rail, a FedNow rail, an RTP rail, a SEPA rail, and a CBDC rail;
- normalize the received payment event streams into a single normalized event schema, wherein each normalized event populates a unified original payment amount field based on an interbank settlement amount extracted from the respective settlement rail;
- validate a disbursement amount of a bridge loan against the unified original payment amount field within a preconfigured tolerance of $0.01;
- (a) derive a governing law jurisdiction for the bridge loan from characters four and five of a sending Bank Identifier Code, wherein the governing law jurisdiction determines the legal framework applicable to the loan agreement; and (b) derive a business calendar jurisdiction for maturity calculation from the governing law jurisdiction or, when unavailable, from a currency-based fallback;
- calculate a business-day adjusted maturity date by applying an iterative business-day advancement algorithm that advances the maturity date forward past each non-business day, as defined by a jurisdiction-specific holiday table selected from TARGET2, FEDWIRE, and CHAPS tables, until a valid settlement day is reached; and
- determine a partial settlement policy comprising one of a require-full policy or an accept-partial policy, and process settlement events based on the determined policy by selectively consuming or preserving an idempotency token in a distributed cache.

### Independent Claim 2 (Method)

A computer-implemented method for multi-rail settlement monitoring and maturity calculation for bridge loans, the method comprising:

- receiving payment event streams from a plurality of distinct settlement rails;
- normalizing the payment event streams into a single normalized event schema, including populating a unified original payment amount field based on interbank settlement amounts;
- validating a loan disbursement amount against the unified original payment amount field within a preconfigured tolerance;
- deriving a settlement jurisdiction from characters four and five of a sending Bank Identifier Code, wherein the sending Bank Identifier Code identifies the originating financial institution of the rejected payment;
- calculating a business-day adjusted maturity date utilizing a jurisdiction-specific holiday calendar; and
- executing a settlement transaction according to a configurable partial settlement policy, comprising selectively consuming or preserving an idempotency token in a distributed cache based on whether a received settlement amount satisfies the full loan amount or triggers a partial settlement protocol.

### Dependent Claim 3 — CBDC Interoperability

The system of claim 1, wherein the CBDC rail operates with a four-hour settlement buffer, and wherein normalizing the payment event streams further comprises translating CBDC rail-specific failure codes into corresponding ISO 20022 rejection reason codes, including at a minimum: CBDC-SC01 to AC01, CBDC-KYC01 to RR01, CBDC-LIQ01 to AM04, and CBDC-FIN01 to TM01, such that CBDC failure events are processed uniformly by downstream pipeline components without CBDC-specific branching logic.

### Dependent Claim 4 — Partial Settlement Redis Idempotency

The method of claim 2, wherein the distributed cache comprises a Redis data store, and wherein executing the settlement transaction further comprises:

- preserving the idempotency token within the Redis data store without consumption when the require-full policy is active and the received settlement amount is less than the full loan amount;
- computing a settlement fee based strictly on the actual received settlement amount rather than the total loan amount when the accept-partial policy is active; and
- generating a settlement record comprising a partial settlement boolean indicator, a calculated shortfall amount, and a calculated shortfall percentage, wherein the shortfall amount and shortfall percentage are computed using fixed-point decimal arithmetic to ensure exactness for regulatory reporting without floating-point rounding error.

### Dependent Claim 5 — Jurisdiction Derivation & Fallback

The system of claim 1, wherein determining the settlement jurisdiction comprises extracting the geographic country code from characters four and five of the BIC, and wherein the instructions further cause the system to:

- apply a currency-based fallback jurisdiction derivation when the BIC is unavailable or unrecognized; and
- apply a default jurisdiction corresponding to a FEDWIRE calendar when both BIC-based derivation and currency-based fallback fail to identify a recognized jurisdiction.

### Dependent Claim 6 — SWIFT pacs.008 Disbursement Message

The method of claim 2, wherein disbursing funds for the bridge loan comprises constructing a SWIFT pacs.008 credit transfer message comprising:

- an end-to-end identifier formatted as 'LIP-BRIDGE-{original_uetr}', wherein original_uetr is the Universal End-to-End Transaction Reference of the rejected payment;
- a remittance information field referencing both the original UETR and a bridge loan identifier; and
- a settlement amount equal to 100% of the original payment amount, wherein no fee amount is deducted from the disbursed principal;

such that the outbound bridge credit transfer is traceable to the original rejected payment through a shared UETR reference.

### Dependent Claim 7 — UETR Deduplication Tracker

The system of claim 1, further configured to register each processed UETR in a distributed in-memory data store with:

- a deduplication key comprising a tuple of sending bank identifier code, receiving bank identifier code, payment amount, and payment currency;
- a deduplication window of thirty minutes, wherein a second bridge loan request matching the same tuple within thirty minutes of the first is rejected as a duplicate; and
- a time-to-live of forty-five days, after which the UETR registration expires;

wherein the deduplication mechanism prevents duplicate bridge loan issuance across distributed pipeline instances without requiring a distributed lock.

---

## Patent Family 3 — C4 Dispute Classifier & Human Override Interface

### Independent Claim 1

A method for real-time natural language dispute classification and autonomous disbursement control within a bridge lending pipeline, the method comprising:

- receiving, by one or more processors, an electronic loan request comprising a natural language narrative and associated payment stream data;
- evaluating the electronic loan request through a first machine learning classification gate to determine a probability of failure, wherein subsequent dispute classification is executed only when the probability of failure exceeds a predetermined threshold;
- applying a two-stage prefilter to the natural language narrative prior to invocation of a large language model (LLM), wherein applying the two-stage prefilter comprises:
  - (a) routing the electronic loan request to an UNKNOWN classification without invoking the LLM when the natural language narrative is empty or null; and
  - (b) routing the electronic loan request to a hold-type indicator classification without invoking the LLM when the narrative contains one or more predetermined hold-type indicator keywords;
- transmitting the natural language narrative to the LLM to classify the narrative into either a DISPUTE_CONFIRMED or NOT_DISPUTE classification when the narrative bypasses the two-stage prefilter; and
- routing the electronic loan request to a human override interface to block an autonomous funded disbursement decision when the classification is DISPUTE_CONFIRMED, when the classification is hold-type indicator, or when an independent hold-type anomaly flag is detected;

wherein the human override interface:
  - applies a configurable timeout action upon expiration of a configurable timeout period, wherein the configurable timeout action is one of a decline action or an approve action, set at system instantiation time by a licensee without modifying the classification pipeline;
  - requires a non-empty operator identifier and, for rejection decisions, a non-empty justification field, both enforced prior to recording the override response in an audit log; and
  - supports an escalation decision that preserves the pending state and re-assigns the override request to a higher authority without consuming the request.

### Dependent Claim 2 — /no_think Latency Reduction

The method of claim 1, wherein transmitting the natural language narrative to the LLM comprises:

- embedding a structured output control directive as a terminal token within the prompt text of the API request, distinct from API-level parameters, to suppress intermediate chain-of-thought reasoning token generation;
- setting an empty stop-sequence array as a separate API-level parameter; and
- applying a regular expression text-stripping operation to the LLM output to extract a finalized classification;

wherein the embedded directive and the empty stop-sequence array operate in combination to prevent generation halting and minimize production latency, without mutual dependency.

### Dependent Claim 3 — Adversarial Training Data Generator

The method of claim 1, further comprising generating adversarial training data by:

- injecting synthetic ISO 20022 camt.056 payment cancellation requests into simulated payment event streams, wherein each injected cancellation request is associated with a prior pacs.002 rejection message sharing a common UETR;
- extracting cancellation intent metadata and a cancellation reason code from each injected camt.056 message; and
- labeling payment events containing the injected camt.056 pattern as a critical adversarial outcome in a training dataset;

whereby the LLM classifier is trained to recognize fraudulent bridge loan cancellation patterns as a subclass of the hold-type indicator classification.

### Dependent Claim 4 — Pipeline Re-Entry Context Store

The method of claim 1, further comprising:

- upon routing the electronic loan request to the human override interface, storing the complete original payment event in a context store keyed by a unique override request identifier;
- upon receiving an operator approval decision, retrieving the stored payment event from the context store using the override request identifier; and
- re-submitting the retrieved payment event to the bridge lending pipeline from its initial entry point, wherein the re-submitted event bypasses human review routing upon detecting the presence of a human approval flag;

enabling deterministic pipeline re-entry without re-parsing or re-normalizing the original payment data.

### Dependent Claim 5 — Dual-Approval Mode

The method of claim 1, wherein the human override interface is configurable to require approval from two independent operators before an override decision is recorded, wherein a single-operator approval is insufficient to release a bridge loan offer when dual-approval mode is active, and wherein dual-approval mode is set at system instantiation time.

---

## Patent Family 4 — Federated Learning Across Bank Consortium (P12)

### Independent Claim 1

A method of calibrating a payment failure prediction model across a consortium of financial institutions without sharing raw transaction records, the method comprising:

- receiving, at a neutral aggregation server operated by a platform operator, differentially private gradient updates from a plurality of bank computing nodes, wherein each bank computing node computes gradients from local transaction data without transmitting the local transaction data outside the originating institution;
- wherein each gradient update is computed by clipping per-sample gradients to an L2 norm of 1.0 and adding Gaussian noise parameterized by a noise multiplier of 1.1, such that the per-round privacy loss is bounded by ε=1.0 and δ=1e-5;
- tracking cumulative privacy loss across all training rounds using a Rényi Differential Privacy accountant via Poisson-sampled composition, wherein the cumulative ε across all rounds is bounded to a regulator-accepted threshold without requiring the per-round ε to equal the cumulative ε; and
- aggregating the received gradient updates at the neutral aggregation server to produce updated global model weights, wherein the neutral aggregation server is logically and administratively external to all bank computing nodes.

### Dependent Claim 2 — Layer Partitioning

The method of claim 1, wherein the payment failure prediction model comprises a graph neural network and a tabular transformer ensemble, and wherein only weights of the final aggregation layers of the graph neural network and the transformer encoder and classifier head of the tabular transformer are shared across the consortium, and wherein all layers encoding institution-specific counterparty topology and borrower identifiers remain local to each bank computing node and are never transmitted.

### Dependent Claim 3 — FedProx Non-IID Regularization

The method of claim 1, further comprising applying a proximal regularization term to local gradient computation at each bank computing node, wherein the proximal term penalizes local weight updates that deviate from global model weights by more than a configurable proximal coefficient μ within the range of 0.001 to 0.1, wherein μ is determined by a qualified financial risk officer prior to each pilot bank onboarding to balance model convergence speed against non-identical data distribution drift across bank jurisdictions.

### Dependent Claim 4 — Phase 3 Secure Aggregation Upgrade

The federated learning system of claim 1, wherein the neutral aggregation server is further configurable to aggregate received gradients utilizing a cryptographic secure aggregation protocol that prevents the aggregation server from inspecting individual gradient updates, wherein the cryptographic protocol is activated upon the consortium reaching a minimum participant threshold of three bank computing nodes, and wherein prior to activation, gradient aggregation is performed using FedProx proximal regularization without cryptographic masking under a semi-honest adversary model established by a multi-party contractual non-collusion agreement.

### Dependent Claim 5 — Asynchronous Quorum Aggregation

The federated learning system of claim 1, wherein the aggregation server executes a training round upon receiving gradient updates from a minimum quorum of participating bank computing nodes less than the total enrolled count, wherein gradient updates from non-responding nodes are excluded from aggregation for the current round without invalidating the round, and wherein each excluded node is re-synchronized with the updated global model at the start of the subsequent round; whereby the protocol tolerates asynchronous participation and dropped connections without requiring unanimous bank participation in each round.

### Dependent Claim 6 — Communication Budget

The method of claim 1, wherein transmission of gradient updates over the financial communication network is constrained such that the weight delta payload per training round does not exceed a per-round size limit, and wherein the total gradient transmission volume across all training rounds remains within the normal operation capacity of a SWIFT SWIFTNet or equivalent secure financial messaging channel without requiring a dedicated high-bandwidth data channel separate from existing transaction messaging infrastructure.

---

## Patent Family 5 — CBDC Normalization & Stress Regime Detection

### Independent Claim 1 — CBDC Normalization & Bridge Lending

A computer-implemented method for unified processing of cross-border bridge lending across heterogeneous settlement rails, the method comprising:

- receiving, at a computing system, a continuous stream of transaction failure events from a plurality of settlement networks comprising at least one legacy payment network and at least one CBDC network;
- normalizing, by a streaming event normalization layer operating prior to any machine learning inference component, a set of CBDC-specific failure codes into a standardized ISO 20022 failure taxonomy, comprising translating CBDC smart contract account errors into AC01, CBDC KYC failures into RR01, and CBDC liquidity pool insufficiencies into AM04;
- routing the normalized failure events into a unified bridge lending pipeline configured to process events across all settlement networks via a source rail enumeration field embedded in each normalized event; and
- executing, by an autonomous execution agent, real-time collateralized lending decisions wherein the collateral authorization amount is derived exclusively from the interbank settlement amount field of the normalized failure event without querying an external credit facility, counterparty master agreement, or pre-established bilateral credit line.

### Independent Claim 2 — Corridor Stress Regime Detector

A computer-implemented method for real-time financial corridor stress regime detection and autonomous decision gating, the method comprising:

- monitoring transaction failure events across a specific cross-border payment corridor;
- calculating a baseline failure rate over a rolling 24-hour baseline window, wherein the baseline window excludes transaction events falling within a rolling 1-hour stress window, such that the baseline and current failure rates are calculated over non-overlapping time intervals;
- calculating a current failure rate over the rolling 1-hour stress window;
- determining whether the ratio of current failure rate to baseline failure rate exceeds a stress regime multiplier of 3.0, wherein the ratio is only evaluated when a minimum transaction count of 20 has been processed in both the 1-hour stress window and the 24-hour baseline window independently;
- wherein when the baseline failure rate is zero, declaring a stress regime upon detecting any single transaction failure within the current window, independent of the stress regime multiplier;
- generating a serialized stress regime event dataclass comprising a corridor identifier, a current failure rate, a baseline failure rate, a ratio field that encodes a null value when the baseline failure rate is zero, and a triggered-at timestamp;
- emitting the serialized stress regime event to a designated topic on a distributed event streaming platform; and
- intercepting, in response to the emitted event, an autonomous funding decision by an execution agent to route pending loan executions to a mandatory human review queue operating as a regulatory circuit breaker under EU AI Act Article 14, applicable irrespective of whether the stressed corridor originates from a CBDC rail or a legacy payment rail.

### Dependent Claim 3 — Differential Maturity by Rail

The method of claim 1, further comprising executing differential loan maturity logic based on the source rail enumeration field of the normalized event, wherein:

- a 4-hour settlement buffer is enforced for a bridge loan where the source rail enumeration field identifies a CBDC rail; and
- a 45-day Universal Confirmations UETR time-to-live threshold is applied for a bridge loan where the source rail enumeration field identifies a legacy payment rail;

wherein the differential maturity logic is applied deterministically based on the source rail value without requiring human configuration per transaction.

### Dependent Claim 4 — Statistical Significance Gate

The method of claim 2, wherein the minimum transaction count of 20 applies independently to both the 1-hour stress window and the 24-hour baseline window, such that a stress regime declaration is suppressed unless both windows independently satisfy the minimum count threshold, preventing false-positive stress signals on thin-traffic or newly established corridors.

### Dependent Claim 5 — New Corridor Zero-Baseline Conservative Gate

The method of claim 2, wherein when the baseline failure rate for a corridor is zero, indicating a newly established corridor with no historical failure baseline, the stress regime is declared upon detecting any single transaction failure within the current window, independent of the stress regime multiplier, such that newly established corridors are treated with maximum conservatism pending accumulation of a statistically valid baseline.

---

## Cross-Patent Notes for Counsel

### EPG-20/21 Language Compliance

All claims use the substitution table from `patent_counsel_briefing.md`. Hold-type classification, hold-type indicator, and categorised originator terminology is used throughout.

### What Is Deliberately Not Claimed

Per EPG-21: the specific enumeration of ISO 20022 rejection codes that trigger a hard-block outcome does not appear in any independent claim. The specific enumeration of ISO 20022 rejection codes that trigger a hold-type outcome is held in the internal taxonomy referenced by the claim, and is not disclosed in any independent or dependent claim.

### Filing Priority Recommendation

| Family | Priority | Basis |
|--------|----------|-------|
| Family 1 — Taxonomy + Dual-Layer Gate | **Highest** | Core novel architecture; most defensive |
| Family 5 — Stress Regime Detector | **High** | Fully implemented; operationally distinct from all prior art |
| Family 3 — C4 Dispute + Human Override | **High** | Pipeline re-entry is genuinely novel; EU AI Act Art. 14 hook |
| Family 2 — Multi-Rail Settlement | **Medium** | Strong but narrower; best filed as continuation of Family 1 |
| Family 4 — Federated Learning (P12) | **Medium** | Phase 2 not yet implemented; file provisional now, non-provisional post-pilot |

---

*This document is a patent counsel working draft. All claims require formal review by qualified patent counsel before filing. Regulatory advice is not provided herein.*
