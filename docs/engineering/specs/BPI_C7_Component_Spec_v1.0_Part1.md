# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 7 — EMBEDDED EXECUTION AGENT
## Build Specification v1.0 — Part 1 of 2
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** NOVA — Payments Infrastructure Engineering
**Support:** FORGE (Kubernetes / container hardening), REX (DORA / EU AI Act),
             CIPHER (network isolation / adversarial testing), LEX (claim language),
             QUANT (fee arithmetic verification)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

> Part 1 of 2 covers Sections 1–9: Purpose, The ELO Boundary,
> Architecture, Container Design, API Contracts, Offer Processing,
> Loan Funding Execution, Kill Switch, and Degraded Mode.
> Part 2 (BPI_C7_Component_Spec_v1.0_Part2.md) covers Sections 10–18:
> Human Override, Decision Log, Repayment Execution, Outbound pacs.008,
> Network Isolation, KMS Integration, Integration Requirements,
> Monitoring, Known Limitations, Validation, and Audit Gate 2.2.

---

## TABLE OF CONTENTS — PART 1

1. Purpose & Scope
2. The ELO Boundary — Why C7 Is Different From Every Other Component
   2.1 The Three-Entity Architecture
   2.2 What C7 Does That Nothing Else Can
   2.3 Capital, Risk, and Execution Sit Here Alone
3. Architecture Overview
   3.1 C7 Internal Component Map
   3.2 Kafka Topic Map (Consumed and Produced)
   3.3 C4 Deployment Within C7
   3.4 Critical Path Position
4. Container Design & Deployment
   4.1 Technology Stack
   4.2 Container Image Specification
   4.3 Kubernetes Deployment Topology
   4.4 Resource Sizing
   4.5 Key Injection Pattern
5. API Contracts — Inbound From Decision Engine
   5.1 LoanOffer Schema (received)
   5.2 ExecutionConfirmation Schema (produced)
   5.3 Offer Expiry Enforcement
6. Loan Offer Processing
   6.1 Processing Sequence
   6.2 Hard Block Enforcement — C4 and C6
   6.3 Bank-Configurable Risk Threshold
   6.4 Offer Acceptance Decision Logic
   6.5 Offer State Machine
7. Loan Funding Execution
   7.1 Core Banking API Interface
   7.2 Bank-Agnostic Adapter Pattern
   7.3 Funding Confirmation Sequence
   7.4 Idempotency on Funding
   7.5 Funding Failure Handling
8. Kill Switch Design
   8.1 Trigger Types
   8.2 Kill Switch Execution Sequence
   8.3 State Preservation Guarantee
   8.4 Recovery Sequence
   8.5 Kill Switch vs. KMS Unavailability — Explicit Distinction
9. Degraded Mode Design
   9.1 Degradation Taxonomy
   9.2 Per-Component Failure Scenarios
   9.3 Degraded Mode Logging
   9.4 Auto-Recovery Behavior

---

## 1. PURPOSE & SCOPE

C7 is the Embedded Execution Agent — the only component in the Liquidity Intelligence
Platform that moves money. Every other component generates intelligence, monitors signals,
or routes messages. C7 is the terminal execution point. It receives loan offers from the
MIPLO Decision Engine, applies the bank's own risk governance (including human override),
executes loan funding via the bank's core banking system, and maintains an immutable
decision log of every automated action.

C7 is written in Go and deployed as a containerized Kubernetes workload within the bank's
own infrastructure. It has zero outbound network connections to Bridgepoint systems. All
data it produces stays within the bank's infrastructure perimeter. The bank controls every
encryption key that protects C7's data. Bridgepoint has no decryption access to anything
C7 writes.

This specification defines C7 to the level of precision required before a line of
production code is written. Every API contract, state transition, failure mode, and
security invariant is specified explicitly. Ambiguity in a component that moves money is
a capital risk, not a design inconvenience.

**NOVA Self-Critique Before Delivery:**
C7 is the most operationally consequential spec in the system. The primary risks are:
(a) orphaned funded loans under failure scenarios, (b) double-funding a loan due to
retry logic, (c) fail-open behavior under AML or KMS outage, and (d) human override
interface that can be bypassed. Every section below addresses at least one of these.
No section was written without asking: "what breaks here, and what happens when it does?"

---

## 2. THE ELO BOUNDARY — WHY C7 IS DIFFERENT FROM EVERY OTHER COMPONENT

### 2.1 The Three-Entity Architecture

The LIP is architected as a three-entity system:

```
MLO (Machine Learning Operator) — Bridgepoint
  Components: C1, C2
  Role: generates intelligence (failure probability, PD estimate, SHAP values)
  Capability: ZERO execution capability — cannot move money

MIPLO (Monitoring, Intelligence & Processing Operator) — Bridgepoint
  Components: C3, C4, C5, C6
  Role: monitors payment networks, applies risk controls, generates loan offers
  Capability: ZERO execution capability — generates offers, cannot fund them

ELO (Execution Lending Operator) — Bank
  Components: C7
  Role: executes loans, enforces blocks, logs every decision
  Capability: SOLE execution capability — the only entity that moves money
```

This separation is architecturally intentional. The design ensures that no automated
action can occur without the bank (as ELO) accepting it. MIPLO cannot bypass ELO.
MLO cannot bypass ELO. C7 is the chokepoint through which every lending decision flows,
and the bank holds complete veto power at all times.

### 2.2 What C7 Does That Nothing Else Can

```
RECEIVES from MIPLO:  LoanOffer (probabilistic intelligence)
ENFORCES:             Hard blocks from C4 (dispute) and C6 (AML/sanctions)
APPLIES:              Bank's own risk governance (configurable PD threshold)
ROUTES:               requires_human_review offers to human review queue
EXECUTES:             Loan funding via bank's core banking system
LOGS:                 Every decision to bank-controlled immutable decision log
PUBLISHES:            ExecutionConfirmation → C3 activates settlement monitoring
PUBLISHES:            Outbound pacs.008 → C3 RTP UETR mapping table
EXECUTES:             Loan repayment via bank's core banking system
ENFORCES:             Kill switch and KMS unavailability halt conditions
```

Nothing in this list is delegatable. C4's on-device inference runs inside C7's
container. C6's block signals arrive as inputs to C7's processing logic. The bank's
own risk thresholds live inside C7's configuration. All of it executes within the
bank's infrastructure. None of it reaches Bridgepoint.

### 2.3 Capital, Risk, and Execution Sit Here Alone

When C7 executes a loan funding, the bank's capital moves. The bank bears the credit
risk. If C7 funds a loan and the borrower defaults, the bank absorbs the loss (offset
by the fee on performing loans). If C7 funds a loan twice due to a retry bug, the bank
has double-exposed itself. If C7 processes an offer after C6 has flagged a sanctions
match, the bank has violated its AML obligations.

These are not engineering footnotes. They are the design constraints that every
implementation decision in this specification must satisfy.

---

## 3. ARCHITECTURE OVERVIEW

### 3.1 C7 Internal Component Map

```
C7 EMBEDDED EXECUTION AGENT (bank-side container)
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ┌──────────────────┐     ┌────────────────────────┐   │
│  │  Offer Processor  │     │  C4 Dispute Classifier │   │
│  │  (Go service)     │────▶│  (on-device, llama.cpp)│   │
│  └──────────────────┘     └────────────────────────┘   │
│          │                                              │
│          ▼                                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Execution Decision Logic                         │  │
│  │  • Hard block enforcement (C4 + C6 signals)       │  │
│  │  • Bank risk threshold check                      │  │
│  │  • Offer expiry check (60s window)                │  │
│  │  • Human review routing                           │  │
│  └──────────────────────────────────────────────────┘  │
│          │                                              │
│          ▼                                              │
│  ┌──────────────────┐     ┌────────────────────────┐   │
│  │  Human Review    │     │  Core Banking Adapter   │   │
│  │  Interface       │     │  (bank-internal API)    │   │
│  └──────────────────┘     └────────────────────────┘   │
│          │                          │                   │
│          ▼                          ▼                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Immutable Decision Log Writer                    │  │
│  │  • HMAC-SHA256 signed per entry                   │  │
│  │  • Bank-controlled KMS                            │  │
│  │  • Append-only → lip.decisions.log                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Repayment Executor                               │  │
│  │  Consumes: lip.repayment.instructions (from C3)   │  │
│  │  Executes: bank core banking repayment API        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Kill Switch Controller                           │  │
│  │  • Manual trigger (operator command)              │  │
│  │  • Watchdog threshold (automated trigger)         │  │
│  │  • State serialization                            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ZERO OUTBOUND CONNECTIONS TO BRIDGEPOINT               │
│  ALL DATA STAYS WITHIN BANK INFRASTRUCTURE              │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Kafka Topic Map

```
CONSUMED BY C7:
  lip.offers.pending          LoanOffer from MIPLO Decision Engine
  lip.repayment.instructions  RepaymentInstruction from C3
  lip.aml.blocks              Hard block signals from C6 (read-only cache refresh)

PRODUCED BY C7:
  lip.loans.funded            ExecutionConfirmation → C3 activates settlement monitor
  lip.payments.outbound       Outbound pacs.008 (for C3 RTP UETR mapping)
  lip.decisions.log           DecisionLogEntry (every decision — HMAC signed)
  lip.state.transitions       Loan lifecycle audit trail
  lip.alerts                  Kill switch, degraded mode, human review timeouts
  lip.repayment.confirmations Repayment execution confirmation to MIPLO
  lip.human.review.queue      Offers routed to human reviewer
```

### 3.3 C4 Deployment Within C7

C4 (the Llama-3 8B dispute classifier) is deployed as an on-device process within
the C7 container. It does not run as a separate service. There is no network call
from C7 to C4 — C4 is a library-level dependency called by C7's Offer Processor.

This design is non-negotiable. SWIFT RmtInf content is borrower payment data. It
cannot leave the bank container. Deploying C4 as a separate networked service would
require transmitting RmtInf to that service, creating a data boundary violation.

C4's quantized model weights (4-bit GPTQ or GGUF) are deployed as a file mount
within the C7 container via bank-controlled volume or init container. The weights
are Bridgepoint-produced but bank-controlled once deployed — the bank controls
model version updates and can reject any update.

C4 uses two paths:
- Fast-path binary classifier (~3ms): always in the synchronous offer processing path
- LLM path (~30-60ms): triggered async when fast-path confidence is uncertain (0.3-0.7)
  LLM timeout behavior per Architecture Spec S11.5:
    ≤$50K:   PROCEED on timeout (fast-path result stands)
    $50K-$500K: HOLD for human ELO review (30-min max); if no response: BLOCK
    >$500K:  HARD BLOCK on timeout

### 3.4 Critical Path Position

C7 is NOT on the end-to-end latency critical path for offer generation. By the time
a LoanOffer arrives at C7, ML inference is already complete. C7's job is to enforce
governance and execute — not to generate intelligence. The latency budget from
Architecture Spec S10.1 (p50 ~26ms from SWIFT receipt to offer generation) is
fully consumed before C7 receives the offer.

C7's execution latency (offer receipt → funding confirmed → ExecutionConfirmation
published) is a separate measurement and is NOT part of the sub-100ms p50 SLA.
The SLA covers offer generation. Loan funding latency is core-banking-dependent
and varies by bank's infrastructure.

---

## 4. CONTAINER DESIGN & DEPLOYMENT

### 4.1 Technology Stack

```
Language:       Go 1.22+
  Rationale:    Memory safety without GC pauses that degrade p99;
                goroutines for concurrent offer + repayment processing;
                first-class Kubernetes client libraries.

Container:      Docker (distroless base image)
  Rationale:    Zero shell, no package manager, minimal attack surface.
                No tools an attacker can use if container is compromised.

Orchestration:  Kubernetes (bank-managed cluster)
  Deployment:   Deployment resource (not StatefulSet — state lives in Redis)
  Scaling:      Non-auto-scaled. Fixed replica count.
                Rationale: C7 is stateless-within-pod. All durable state
                is in Redis (bank-side) and Kafka. Autoscaling adds race
                conditions in the human review queue — not worth it.

C4 runtime:     llama.cpp (CGO binding from Go or subprocess with IPC)
  Model format: GGUF quantized (4-bit, Q4_K_M or Q5_K_M)
  Memory:       <6GB for 8B parameter model at 4-bit

Kafka client:   confluent-kafka-go (Confluent Go client)
Redis client:   go-redis/v9 (bank Redis cluster)
gRPC:           google.golang.org/grpc (MIPLO interface)
```

### 4.2 Container Image Specification

```
FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app/c7-agent /usr/local/bin/c7-agent
COPY --from=builder /app/c4-fast-classifier /usr/local/bin/c4-fast

# C4 model weights: mounted at runtime via bank volume mount
# NEVER baked into the image
# VOLUME ["/models/c4"]

# No shell. No package manager. No curl. No wget.
# If this container is compromised, the attacker has a Go binary and nothing else.

USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/c7-agent"]
```

**Image signing requirement:**
All C7 container images MUST be signed with Cosign and verified by the bank's
admission controller (e.g., Kyverno or OPA Gatekeeper) before deployment.
An unsigned C7 image MUST be rejected at the admission stage — not just flagged.

**Dependency pinning:**
All Go module dependencies pinned by exact version hash in go.sum.
No indirect dependency upgrades without explicit review.
Container image digest pinned in Kubernetes deployment manifest.
Supply chain attack surface is minimal by design (distroless + pinned).

### 4.3 Kubernetes Deployment Topology

```
Namespace:          lip-execution (isolated from MIPLO components)
Replicas:           2 (active-active, Kafka consumer group handles distribution)
Pod anti-affinity:  Required — two replicas MUST run on separate physical nodes
  Rationale:        Single node failure kills at most one replica.
                    Human review queue continuity during node failure.

Resources per pod:
  CPU request:    2 cores   CPU limit:    4 cores
  Memory request: 8Gi       Memory limit: 12Gi
  (C4 GGUF model: ~5-6Gi; Go process: ~500Mi; headroom for burst)

Liveness probe:   /healthz — checks Kafka consumer lag and Redis connectivity
Readiness probe:  /readyz — checks KMS reachability and C4 model loaded
Startup probe:    60s startup timeout (C4 model load can take 30-45s)

Network policy:
  Ingress:  Kafka broker (bank-internal) only
            gRPC from MIPLO Decision Engine (bank VPC)
            Bank operator UI (for human review)
  Egress:   Kafka broker (bank-internal) only
            Redis cluster (bank-internal)
            Bank core banking API (bank-internal)
            Bank KMS (bank-internal)
            ZERO egress to external internet
            ZERO egress to Bridgepoint infrastructure

Pod security:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  seccompProfile: RuntimeDefault
  capabilities: drop ALL
```

### 4.4 Resource Sizing

C4 model memory is the dominant sizing constraint. At 4-bit quantization, an 8B
parameter model requires approximately 5-6 GB of resident memory. The LLM path
is async — it does not block the synchronous offer processing goroutine — but the
model must be resident in memory at all times to avoid cold-load latency on each
inference request.

GPU acceleration for C4 is optional within C7. C4's 4-bit quantized model achieves
acceptable latency on CPU (~30-60ms for the LLM path). The LLM path is not on the
critical path (it runs async and only triggers for uncertain cases). GPU is not
required for C7 — only for C1 in the MIPLO inference tier.

If the bank's Kubernetes nodes lack sufficient memory (12Gi), the C7 memory limit
must be raised, or C4 must be quantized more aggressively (Q3_K_M at ~4Gi). This
trade-off lowers C4 accuracy marginally. ARIA to benchmark before final deployment.

### 4.5 Key Injection Pattern

No secrets are baked into the C7 container image. No secrets are stored in
Kubernetes Secrets resources (which are base64-encoded, not encrypted, by default).

```
Key Injection: Kubernetes External Secrets Operator (ESO)
Bank vault backend: HashiCorp Vault or AWS Secrets Manager (bank-deployed)

Secrets managed via ESO:
  - Bank KMS endpoint + credentials (for decision log encryption)
  - HMAC signing key reference (for decision log entry signatures)
  - Kafka SASL credentials (for broker authentication)
  - Redis authentication token
  - Bank core banking API credentials (OAuth2 client credentials)
  - C4 model mount credentials (if model is in bank object storage)

Init container pattern for model loading:
  An init container pulls the C4 GGUF model from bank-controlled object storage
  (e.g., bank S3-equivalent) and writes it to a shared volume. The C7 main
  container mounts this volume read-only. The init container has credentials;
  the main container does not — it only reads the already-loaded file.

Key rotation:
  ESO re-syncs secrets on rotation without pod restart (where possible).
  HMAC signing key rotation requires a brief C7 restart window.
  All rotations are bank-scheduled and bank-controlled.
  Bridgepoint has zero visibility into bank key material.
```

---

## 5. API CONTRACTS — INBOUND FROM DECISION ENGINE

### 5.1 LoanOffer Schema (received)

C7 receives LoanOffer messages on Kafka topic `lip.offers.pending`.
Partition key: UETR. The full schema is defined in Architecture Spec S4.6.
Repeated here for C7 build completeness.

```
LoanOffer {
  uetr                   : string   // Unique End-to-End Transaction Reference
  individual_payment_id  : string   // Explicit individual identifier (same as UETR)
  loan_amount_usd        : double   // Computed by C2 (EAD)
  maturity_days          : int32    // 3, 7, or 21 — from T = f(rejection_code_class)
  fee_bps                : float    // ANNUALIZED rate — see fee arithmetic (Section 7.3)
  pd_estimate            : float    // 0.0 - 1.0 from C2
  rejection_code         : string   // Original SWIFT rejection code
  rejection_code_class   : string   // "A", "B", or "C"
  pd_shap                : ShapValue[]  // C2 SHAP values for this individual UETR
  classifier_shap        : ShapValue[]  // C1 SHAP values for this individual UETR
  offer_expiry_utc       : int64    // Offer valid for 60 seconds from generation
  corridor               : string   // "EUR_USD_CITI" format
  requires_human_review  : bool     // True if PD >= bank-configured review threshold
  remittance_info        : string   // Raw RmtInf text — passed to C4 on-device
  c6_aml_result          : VelocityResponse  // Pre-computed AML result from C6
                                             // C7 enforces — does not re-query C6
}
```

**Note on c6_aml_result:** C6 runs in the MIPLO critical path before the offer is
generated. The AML result is packaged into the offer by the Decision Engine and
carried through to C7. C7 enforces the block result — it does not re-query C6.
This keeps C7 stateless with respect to AML and avoids a duplicate C6 call.
Re-query behavior: if c6_aml_result is absent or malformed, C7 treats it as
a hard block (fail-safe). No offer is accepted without a valid AML result present.

### 5.2 ExecutionConfirmation Schema (produced)

C7 produces ExecutionConfirmation on Kafka topic `lip.loans.funded`.
This is consumed by C3 to activate settlement monitoring.

```
ExecutionConfirmation {
  uetr                   : string   // individual UETR
  individual_payment_id  : string   // explicit individual identifier
  accepted               : bool
  decline_reason         : string   // populated if accepted = false
                                    //  "OFFER_EXPIRED" | "HARD_BLOCK_C4" |
                                    //  "HARD_BLOCK_C6" | "PD_THRESHOLD_EXCEEDED" |
                                    //  "HUMAN_DECLINED" | "FUNDING_FAILED" |
                                    //  "KMS_UNAVAILABLE" | "C4_UNAVAILABLE"
  loan_reference         : string   // bank's internal loan ID (if accepted)
  funded_timestamp_utc   : int64    // when funding was confirmed by core banking
  funded_amount_usd      : double   // actual funded amount (may differ from offer
                                    //   if bank rounds to integer units)
  maturity_days          : int32    // from original offer
  fee_bps                : float    // annualized rate from original offer
  elo_operator_id        : string   // populated if human_reviewed = true
  human_reviewed         : bool
  model_version_c1       : string   // from original offer — audit trail
  model_version_c2       : string
  model_version_c4       : string
  rejection_code_class   : string   // carried through for C3 state machine
  corridor               : string   // carried through for C3 buffer lookup
}
```

### 5.3 Offer Expiry Enforcement

Every LoanOffer carries an `offer_expiry_utc` timestamp set 60 seconds after
the offer was generated in the Decision Engine. C7 checks this before any
processing step.

```
Expiry check:
  if current_time_utc > offer_expiry_utc:
    → decline_reason = "OFFER_EXPIRED"
    → publish DecisionLogEntry (event_type = "OFFER_EXPIRED")
    → publish ExecutionConfirmation (accepted = false)
    → no further processing
    → no alert (expected behavior; log only)

Why 60 seconds:
  The underlying payment failure is real-time. If C7 delays more than 60 seconds
  in processing an offer (e.g., human review queue backed up, core banking slow),
  market conditions and AML velocity calculations may have changed. The 60-second
  window forces the Decision Engine to regenerate a fresh offer if processing
  is delayed beyond the expiry.

Clock skew tolerance:
  C7's clock must be synchronized to NTP within ±1 second (Architecture Spec S14,
  Requirement 6). Expiry check uses a 2-second grace buffer (accept if
  current_time_utc <= offer_expiry_utc + 2000ms) to absorb minor skew.
  Clock skew alert: if C7's wall clock deviates >5 seconds from NTP, alert
  "C7_CLOCK_SKEW_CRITICAL" and halt new offer processing.
```

---

## 6. LOAN OFFER PROCESSING

### 6.1 Processing Sequence

This sequence is exhaustive. Every check must be completed in this order.
No step may be skipped. No check may be parallelized with a subsequent check.
Sequence integrity is a compliance requirement (EU AI Act Art.14).

```
Step 1: Offer expiry check
  if expired: decline "OFFER_EXPIRED" → end

Step 2: AML/sanctions block check (from c6_aml_result in offer)
  if c6_aml_result absent or malformed: decline "HARD_BLOCK_C6" → end
  if c6_aml_result.hard_block = true: decline "HARD_BLOCK_C6" → end
  if c6_aml_result.sanctions_match = true: decline "HARD_BLOCK_C6" → end

Step 3: C4 dispute check (on-device, synchronous fast-path)
  Feed remittance_info to C4 fast-path binary classifier
  if dispute_detected = true (confidence > 0.7): decline "HARD_BLOCK_C4" → end
  if confidence uncertain (0.3-0.7): route to C4 LLM path (async, see Section 6.2)
  if C4 process unavailable: decline "C4_UNAVAILABLE" → end (fail-safe)

Step 4: KMS availability check
  Attempt bank KMS connectivity (lightweight ping, <5ms)
  if KMS unavailable: decline "KMS_UNAVAILABLE" → end (per Architecture Spec S2.5)

Step 5: Bank risk threshold check
  if pd_estimate >= bank_pd_threshold_hard_block: decline "PD_THRESHOLD_EXCEEDED"
  if pd_estimate >= bank_pd_threshold_review (AND human review not yet done):
    set requires_human_review = true → route to human review (Section 6.3)

Step 6: requires_human_review check
  if requires_human_review = true AND offer.requires_human_review = true:
    route to human review queue (Section 10)

Step 7: Execute loan funding
  Call bank core banking API (Section 7)

Step 8: Publish ExecutionConfirmation (accepted = true)
  → lip.loans.funded (consumed by C3)

Step 9: Publish outbound pacs.008
  → lip.payments.outbound (consumed by C3 RTP UETR mapper)

Step 10: Write DecisionLogEntry (event_type = "LOAN_FUNDED")
  → lip.decisions.log (HMAC-SHA256 signed)
```

### 6.2 Hard Block Enforcement — C4 and C6

Hard blocks are absolute. No bank risk threshold, no human override, no retry
can reverse a hard block once triggered. This is a system invariant.

```
C6 Hard Block:
  Sources: velocity_dollar | velocity_count | beneficiary_concentration |
           sanctions_match | anomaly
  Trigger: c6_aml_result.hard_block = true OR sanctions_match = true
  Consequence: offer declined; DecisionLogEntry logged with block_reason;
               UETR added to short-term block list in C7 local Redis cache
               (TTL 24h — prevents re-offer on same UETR within 24h)
  Human override: NOT PERMITTED for sanctions_match = true
                  PERMITTED (with explicit justification) for velocity/anomaly
                  blocks where bank compliance team reviews the entity

C4 Hard Block:
  Sources: fast-path dispute_detected > 0.7 OR LLM-path dispute_detected = true
  Trigger: dispute_detected = true in either path
  Consequence: offer declined; DecisionLogEntry logged; payment state →
               DISPUTE_BLOCKED (terminal for automated lending)
  Human override: PERMITTED — bank compliance officer can unblock with explicit
                  rationale logged. See Section 10 for protocol.

C4 Unavailability (on-device process failure):
  If C4's fast-path binary classifier process is unresponsive:
  → Treat as HARD BLOCK for amounts > $50K (fail-safe)
  → For amounts ≤ $50K: proceed, log c4_unavailable = true in DecisionLogEntry
  Rationale: the risk asymmetry between funding a disputed payment vs. delaying
  a small-amount legitimate payment justifies the $50K threshold split.
  This threshold is CONFIGURABLE by bank operators. Default: $50K.
```

### 6.3 Bank-Configurable Risk Threshold

C7 exposes two bank-configurable PD thresholds. These are bank-side governance
controls — Bridgepoint does not set or influence them.

```
bank_pd_threshold_review:
  Default: 0.15 (15% PD triggers human review)
  Range:   0.05 - 0.50 (bank-configurable)
  Effect:  Offers with pd_estimate >= this threshold go to human review queue
           before funding. Reviewer can approve or decline.

bank_pd_threshold_hard_block:
  Default: 0.40 (40% PD = hard block, no human review available)
  Range:   0.20 - 1.00 (bank-configurable; must be > threshold_review)
  Effect:  Offers with pd_estimate >= this threshold are declined without
           routing to human review. Rationale: at very high PD, the cost
           of human review time does not justify the capital risk.

Configuration source: Kubernetes ConfigMap (bank-managed)
  Not a secret — these thresholds are governance policy, not credentials.
  Config changes require pod restart (no hot-reload for risk thresholds).
  Every config change logged: who changed, when, what from/to.

Threshold floor enforcement:
  bank_pd_threshold_hard_block MUST be > bank_pd_threshold_review.
  If misconfigured (hard_block <= review), C7 refuses to start.
  Startup validation prevents misconfiguration from going undetected.
```

### 6.4 Offer Acceptance Decision Logic

After all blocks and threshold checks, the offer acceptance decision logic is:

```
ACCEPT if ALL of the following are true:
  ✓ Offer not expired
  ✓ c6_aml_result present and hard_block = false and sanctions_match = false
  ✓ C4 dispute_detected = false (or C4 unavailable AND amount ≤ threshold)
  ✓ KMS available
  ✓ pd_estimate < bank_pd_threshold_hard_block
  ✓ Either: pd_estimate < bank_pd_threshold_review
    OR:     human reviewer has explicitly approved this offer
  ✓ Kill switch not active

DECLINE if ANY of the following:
  × Offer expired
  × c6_aml_result absent, malformed, or hard_block = true
  × c6_aml_result.sanctions_match = true
  × C4 dispute_detected = true
  × C4 unavailable AND amount > $50K threshold
  × KMS unavailable
  × pd_estimate >= bank_pd_threshold_hard_block
  × Human reviewer declined (or review timed out for amounts >$500K)
  × Kill switch active
```

### 6.5 Offer State Machine

```
STATES:
  RECEIVED          Offer consumed from lip.offers.pending
  EXPIRY_CHECK      Expiry timestamp verified
  AML_CHECK         c6_aml_result enforced
  DISPUTE_CHECK     C4 on-device check
  KMS_CHECK         KMS availability verified
  THRESHOLD_CHECK   PD vs. bank thresholds evaluated
  UNDER_REVIEW      Human reviewer notified, awaiting decision
  EXECUTING         Core banking funding call in flight
  FUNDED            Funding confirmed, ExecutionConfirmation published
  DECLINED          Offer rejected (any decline_reason)

VALID TRANSITIONS:
  RECEIVED        → EXPIRY_CHECK
  EXPIRY_CHECK    → AML_CHECK        (not expired)
  EXPIRY_CHECK    → DECLINED         (expired)
  AML_CHECK       → DISPUTE_CHECK    (no block)
  AML_CHECK       → DECLINED         (hard block or sanctions)
  DISPUTE_CHECK   → KMS_CHECK        (no dispute, fast-path)
  DISPUTE_CHECK   → DECLINED         (dispute detected or C4 unavailable >$50K)
  DISPUTE_CHECK   → UNDER_REVIEW     (LLM path uncertain, amount $50K-$500K)
  KMS_CHECK       → THRESHOLD_CHECK  (KMS available)
  KMS_CHECK       → DECLINED         (KMS unavailable)
  THRESHOLD_CHECK → UNDER_REVIEW     (pd >= review threshold)
  THRESHOLD_CHECK → DECLINED         (pd >= hard_block threshold)
  THRESHOLD_CHECK → EXECUTING        (all checks pass, no review required)
  UNDER_REVIEW    → EXECUTING        (human approved)
  UNDER_REVIEW    → DECLINED         (human declined or timeout/amount >$500K)
  EXECUTING       → FUNDED           (core banking confirms)
  EXECUTING       → DECLINED         (core banking failure — funding_failed)

TERMINAL STATES: FUNDED, DECLINED
No re-processing of a terminal-state offer. Duplicate Kafka delivery of a
terminal-state offer: silently dropped + logged (idempotency guarantee).
```

---

## 7. LOAN FUNDING EXECUTION

### 7.1 Core Banking API Interface

C7 calls the bank's core banking system to execute loan funding. The bank's
core banking API is bank-specific — there is no universal standard. C7 uses
an adapter pattern to remain bank-agnostic at the C7 code level.

The bank-agnostic interface C7 expects from the adapter:

```
FundingRequest {
  loan_reference          : string   // C7-generated UUID v4 — idempotency key
  uetr                    : string   // individual UETR
  individual_payment_id   : string   // explicit individual identifier
  amount_usd              : double   // from LoanOffer.loan_amount_usd
  maturity_days           : int32    // from LoanOffer.maturity_days
  beneficiary_account_ref : string   // from original payment — bank-internal ref
  rejection_code          : string   // for bank's internal risk classification
  rejection_code_class    : string   // "A", "B", or "C"
  fee_bps                 : float    // annualized (from LoanOffer)
  funding_timestamp_utc   : int64    // C7 wall-clock at call time
  authorized_by           : string   // "AUTOMATED" or operator_id if human reviewed
}

FundingResponse {
  loan_reference          : string   // echoed back for confirmation
  success                 : bool
  bank_loan_id            : string   // bank's internal loan identifier
  funded_amount_usd       : double   // actual amount funded (post-rounding)
  funded_timestamp_utc    : int64    // bank's internal funding timestamp
  failure_reason          : string   // if success = false:
                                     //   "INSUFFICIENT_CAPITAL" |
                                     //   "ACCOUNT_NOT_FOUND" |
                                     //   "DAILY_LIMIT_EXCEEDED" |
                                     //   "SYSTEM_UNAVAILABLE" |
                                     //   "DUPLICATE_REQUEST"
}
```

### 7.2 Bank-Agnostic Adapter Pattern

```
Interface: CoreBankingAdapter (Go interface)
  FundLoan(ctx context.Context, req FundingRequest) (FundingResponse, error)
  RepayLoan(ctx context.Context, req RepaymentRequest) (RepaymentResponse, error)
  GetLoanStatus(ctx context.Context, loanReference string) (LoanStatus, error)

Implementations (one per bank deployment):
  BankACoreAdapter       — implements CoreBankingAdapter for Bank A
  BankBCoreAdapter       — implements CoreBankingAdapter for Bank B
  BankCCoreAdapter       — implements CoreBankingAdapter for Bank C
  [etc. — one per pilot bank]
```

> **Note:** BankA / BankB / BankC are illustrative placeholders. No specific
> institution is contemplated by these names — any ISO-20022-speaking
> correspondent bank can be integrated via a CoreBankingAdapter subclass.

```
Adapter selection: Kubernetes ConfigMap "bank_id" variable
  C7 loads the correct adapter at startup based on bank_id.
  No code changes required for new bank deployment — only a new adapter
  implementation and a ConfigMap update.

Adapter testing requirement:
  Each adapter must be tested against the bank's UAT core banking environment
  before production deployment. Integration test: fund and immediately repay
  a $1 test loan. Confirm loan_reference idempotency (duplicate request
  returns DUPLICATE_REQUEST, not a second funding).
```

### 7.3 Funding Confirmation Sequence

```
1. C7 generates loan_reference = UUID v4 (idempotency key)
2. C7 writes pending entry to local Redis:
     Key:   "c7:funding:pending:{loan_reference}"
     Value: {uetr, amount_usd, timestamp_utc, status: "IN_FLIGHT"}
     TTL:   30 seconds
3. C7 calls CoreBankingAdapter.FundLoan with loan_reference
4a. Success:
     Update Redis entry: status = "CONFIRMED", bank_loan_id = ...
     Publish ExecutionConfirmation (accepted = true) to lip.loans.funded
     Publish outbound pacs.008 to lip.payments.outbound (Section 13)
     Write DecisionLogEntry (event_type = "LOAN_FUNDED")
     Publish lip.state.transitions (OFFER_PENDING → ACTIVE)
     Clear Redis pending entry (TTL cleanup)
4b. Failure (success = false):
     Update Redis entry: status = "FAILED", failure_reason = ...
     Publish ExecutionConfirmation (accepted = false, decline_reason = "FUNDING_FAILED")
     Write DecisionLogEntry (event_type = "FUNDING_FAILED")
     Alert: "FUNDING_EXECUTION_FAILED" with uetr, loan_reference, failure_reason
```

**Fee arithmetic (verified by QUANT):**

The fee charged at repayment time uses the ANNUALIZED fee_bps from the LoanOffer.
The per-cycle fee formula is:

```
fee_usd = funded_amount_usd
          * (fee_bps / 10_000)
          * (actual_days_funded / 365)

Example at fee floor (300 bps annualized, 7-day cycle):
  fee_usd = 100,000 * (300 / 10,000) * (7 / 365)
          = 100,000 * 0.03 * 0.01918
          = $57.53
  → 0.0575% of principal for a 7-day cycle

CRITICAL: fee_bps is NOT a flat per-cycle rate.
Applying 300 bps as a flat rate would yield 3% per cycle = $3,000 on $100K.
This is 52× the intended fee. The per-cycle formula above is the correct one.
This note is mandatory in every C7 code review touching fee calculation.
```

### 7.4 Idempotency on Funding

Loan funding idempotency is enforced at two layers:

**Layer 1 — C7 local Redis deduplication:**
Before calling CoreBankingAdapter.FundLoan, C7 checks Redis for an existing
entry with the same loan_reference. If a "CONFIRMED" entry exists: return
the prior FundingResponse, skip the core banking call, and log
"IDEMPOTENT_FUNDING_DUPLICATE_SUPPRESSED".

**Layer 2 — Core banking adapter idempotency:**
CoreBankingAdapter.FundLoan must implement idempotency keyed on loan_reference.
If the bank's core banking system returns "DUPLICATE_REQUEST", C7 calls
CoreBankingAdapter.GetLoanStatus(loan_reference) to retrieve the original
FundingResponse and proceeds as if the original call succeeded.

**What this prevents:**
- Kafka at-least-once redelivery causing two funding calls for one offer
- Flink restart replaying an already-funded offer
- Network timeout where the funding call succeeded but the response was lost

**What this does NOT prevent:**
Two different offers for the same UETR being funded sequentially. This is
prevented at the MIPLO Decision Engine level — C7 does not re-check. The
architecture invariant is that the Decision Engine generates at most one
offer per UETR. If this invariant is violated, C7 will fund both. This is
a Decision Engine defect, not a C7 defect — but C7 should alert on
detection of duplicate UETR in funded loans (two loan_references pointing
to the same UETR) as a defense-in-depth signal.

### 7.5 Funding Failure Handling

```
Transient failure (SYSTEM_UNAVAILABLE):
  Retry: 3 attempts with exponential backoff (1s, 2s, 4s)
  After 3 retries: treat as permanent failure
  loan_reference: same across all retries (idempotency maintained)

Permanent failure:
  Publish ExecutionConfirmation (accepted = false, decline_reason = "FUNDING_FAILED")
  Write DecisionLogEntry (event_type = "FUNDING_FAILED")
  Alert: "FUNDING_EXECUTION_FAILED" with uetr + failure_reason
  The UETR remains in BRIDGE_OFFERED state in MIPLO state machine.
  The MIPLO offer will expire (60s window). No automatic re-offer.
  Human intervention: bank operator can trigger a fresh offer cycle if warranted.

INSUFFICIENT_CAPITAL:
  Treat as permanent failure (no retry — capital constraint is not transient)
  Alert: "INSUFFICIENT_CAPITAL_FUNDING_HALT"
  If this alert fires > 3 times in 1 hour: escalate to "CAPITAL_EXHAUSTION_WARNING"
  Kill switch consideration: bank operator should evaluate kill switch if capital
  exhaustion is systemic rather than isolated.

DAILY_LIMIT_EXCEEDED:
  Treat as permanent failure for this UETR
  Alert: "DAILY_FUNDING_LIMIT_REACHED"
  No new loan offers should be accepted until next rolling window reset
  Kill switch: C7 holds all new offers until limit resets (configurable behavior)
```

---

## 8. KILL SWITCH DESIGN

### 8.1 Trigger Types

C7 supports two kill switch trigger types (Architecture Spec S2.5):

```
Type 1 — Manual Operator Trigger:
  Bank operator sends authenticated command to C7 admin API
  (POST /admin/kill-switch/activate with operator credentials + reason)
  Takes effect: immediately on all C7 replicas (via Kubernetes ConfigMap update
  that C7 watches; no restart required)
  Requires: dual authorization (two operator IDs) for safety

Type 2 — Automated Watchdog Trigger:
  C7 internal watchdog monitors configurable thresholds.
  Default thresholds that trigger automated kill switch:
    • Funding failure rate > 50% in any 15-minute window
    • INSUFFICIENT_CAPITAL alert fires > 5 times in 1 hour
    • KMS connectivity fails > 3 consecutive health checks (60-second interval)
    • C4 on-device process unavailable > 5 continuous minutes
    • Decision log write failure rate > 10% in any 5-minute window
  Thresholds are configurable via Kubernetes ConfigMap.
  Automated trigger: logs "KILL_SWITCH_AUTO_TRIGGERED" with reason and threshold
  Bank operator notified immediately on automated trigger.
```

### 8.2 Kill Switch Execution Sequence

```
Step 1: Set kill_switch_active = true in C7 in-memory state
  (Atomic operation — goroutine-safe. All offer processing goroutines check this flag.)

Step 2: Stop consuming from lip.offers.pending
  (Kafka consumer paused — messages remain in topic, not lost)

Step 3: Snapshot all active loan states to persistent Redis
  "c7:kill_switch:snapshot:{timestamp}"
  Contains: all UETRs currently in FUNDED state with their metadata
  TTL: 30 days (well beyond longest maturity of 21 days)

Step 4: Continue consuming lip.repayment.instructions (read-only settlement)
  Funded loans MUST continue to receive settlement signals and execute repayments.
  Kill switch halts NEW lending. It does not abandon in-flight loans.
  Repayment execution continues normally.

Step 5: Continue writing to lip.decisions.log for any repayment events
  Audit trail must be maintained during kill switch period.

Step 6: Publish alert "KILL_SWITCH_ACTIVATED" with:
  trigger_type: "MANUAL" or "AUTOMATED"
  reason: from operator command or watchdog threshold
  active_funded_loans: count of UETRs currently in FUNDED state
  snapshot_key: Redis snapshot key

Step 7: Notify bank operator via configured alert channel
  (Kafka lip.alerts; bank operator notification webhook if configured)
```

### 8.3 State Preservation Guarantee

This is an inviolable invariant: **no funded loan is orphaned under any kill switch scenario.**

```
"Orphaned" means: a UETR in FUNDED state with no settlement monitoring active.
If C7 is shut down hard (e.g., OOM kill, node failure), Redis persistence ensures
that funded loan state survives. On C7 restart, the following recovery sequence fires.

Redis persistence requirement:
  Redis must be configured with persistence (RDB snapshots + AOF).
  In-memory-only Redis mode is NOT acceptable for C7's loan state.
  If Redis itself fails during kill switch: C7 cannot guarantee no orphans.
  Redis HA (5-node cluster) and Redis persistence are prerequisites for C7.
  This is a FORGE Phase 4 deliverable dependency.

Kafka-backed safety net:
  lip.loans.funded contains every ExecutionConfirmation ever published.
  C3's settlement monitor is the primary keeper of funded loan state.
  If C7's Redis is corrupted or lost, C3's Flink state (RocksDB) still holds
  the UETR → ACTIVE state for every funded loan. Settlement monitoring
  continues in C3 regardless of C7's state. C3 does not depend on C7 for
  settlement detection — C3 is the authoritative keeper of funded loan lifecycle.

Implication: C7's role after funding is primarily repayment execution.
C3 is the durable watchdog. C7 executes what C3 tells it to repay.
```

### 8.4 Recovery Sequence

```
On C7 pod restart (after kill switch or failure):

Step 1: C7 startup validation
  Check KMS connectivity (required before proceeding)
  Check Kafka broker connectivity
  Check Redis connectivity
  Load C4 model (via volume mount or init container)
  If any required check fails: pod enters CrashLoopBackOff (Kubernetes handles restart)

Step 2: Restore kill_switch_active state
  Read Kubernetes ConfigMap for kill_switch_active flag
  If still true: resume in kill switch mode (no new offers)
  If cleared by operator: proceed to normal operation

Step 3: Re-process any in-flight items
  Check Redis for "c7:funding:pending:{*}" entries (TTL 30s)
  Any IN_FLIGHT entries older than 30s: treat as timed-out
  Check core banking status for each: GetLoanStatus(loan_reference)
  Reconcile: funded → publish ExecutionConfirmation if not already published
             failed  → publish ExecutionConfirmation(declined) + alert

Step 4: Resume consumption
  lip.repayment.instructions: always (settlement execution)
  lip.offers.pending: only if kill_switch_active = false

Step 5: Log "C7_RECOVERY_COMPLETE" with reconciliation summary
```

### 8.5 Kill Switch vs. KMS Unavailability — Explicit Distinction

These are different failure modes with different responses (Architecture Spec S2.5):

```
Kill Switch:
  Decision: bank operator or watchdog
  New offers: halted
  Repayment execution: continues
  Funded loans: monitored and repaid normally
  Recovery: operator-initiated (manual) or auto-recovery (watchdog)

KMS Unavailability:
  Decision: automatic (cannot write to encrypted log = fail-safe halt)
  New offers: halted (cannot maintain audit trail)
  Repayment execution: continues (settlement signals still processed;
    repayment log entries written with kms_unavailable_gap = true on recovery)
  Funded loans: settlement signals buffered in Kafka, replayed on KMS recovery
  Recovery: automatic on KMS restoration (no manual intervention required)

Key invariant for both: settlement monitoring and repayment execution on
already-funded loans continues in all cases. C3 holds durable funded loan state.
```

---

## 9. DEGRADED MODE DESIGN

### 9.1 Degradation Taxonomy

C7 defines four degradation levels:

```
Level 0 — NORMAL OPERATION
  All components healthy. Full offer processing pipeline active.

Level 1 — ADVISORY DEGRADED (no offer processing impact)
  C1 GPU inference → CPU fallback (p99 rises but within SLA)
  Decision latency increases; offer generation continues
  Logged: degraded_mode = true in all DecisionLogEntries

Level 2 — PARTIAL DEGRADED (processing continues with constraints)
  C4 unavailable → offers ≤ $50K proceed; >$50K blocked
  Kafka consumer lag > 60s → alert fired; processing continues
  Redis read latency > 50ms → alert fired; processing continues

Level 3 — FULL DEGRADED (new offer processing halted)
  KMS unavailable → halt new offers (fail-safe; funded loans still repaid)
  C6 AML result absent → halt new offers (fail-safe)
  Kill switch active → halt new offers
  Core banking API unavailable → halt new offers; queue not retained

Level 4 — SHUTDOWN (pod not accepting work)
  Startup validation failed (KMS, Kafka, Redis unreachable at boot)
  Pod enters CrashLoopBackOff
```

### 9.2 Per-Component Failure Scenarios

```
Scenario A — C1/C2 Model Server Unavailable (MIPLO-side)
  Effect on C7: C7 receives no new offers (Decision Engine does not generate
    offers if C1/C2 are down — this is MIPLO's fail behavior, not C7's)
  C7 behavior: idle (no offers arriving); repayment execution continues
  Alert: none from C7 (MIPLO emits the model unavailability alert)
  C7 degradation level: Level 0 from C7's perspective

Scenario B — C4 On-Device Process Failure
  Effect on C7: C7 cannot perform dispute check
  C7 behavior:
    Offers ≤ $50K: proceed; log c4_unavailable = true; alert fired
    Offers > $50K: decline "C4_UNAVAILABLE"; alert fired
  Alert: "C4_ON_DEVICE_UNAVAILABLE" — immediate; includes offer count blocked
  C7 degradation level: Level 2
  Recovery: Kubernetes liveness probe restarts C4 process (not full pod restart)
    C4 runs as a sidecar process monitored by C7's internal health check
    Process supervisor (Go-based): if C4 returns non-zero 3× in 60s, restart it
    Model reload on restart: ~30-45s (init container pre-loads model to volume)

Scenario C — C6 AML Result Absent in Offer
  Effect on C7: cannot confirm AML clearance
  C7 behavior: decline "HARD_BLOCK_C6"; alert fired
  Alert: "C6_AML_RESULT_ABSENT_IN_OFFER" — immediate
  C7 degradation level: Level 3 (fail-safe halt for affected offers)
  Recovery: Decision Engine must be checked — why is c6_aml_result absent?
    If systemic (C6 down), MIPLO emits alerts. C7 alert is an additional signal.

Scenario D — KMS Unavailable
  Effect on C7: cannot write to encrypted decision log
  C7 behavior: halt new offer processing; repayment execution continues
    Repayment log entries buffered; written with kms_unavailable_gap = true on recovery
  Alert: "KMS_UNAVAILABLE" — immediate with KMS endpoint and last_success_timestamp
  C7 degradation level: Level 3
  Recovery: automatic on KMS response; no manual intervention required
    C7 polls KMS at 10-second intervals during unavailability
    On recovery: flush buffered log entries (in order) then resume offers

Scenario E — Bank Core Banking API Unavailable
  Effect on C7: cannot execute loan funding
  C7 behavior: offers fail at EXECUTING state; 3-retry then decline "FUNDING_FAILED"
    New offers continue to be processed through Steps 1-6 (blocks, thresholds, etc.)
    All offers fail at Step 7 (funding) until core banking recovers
  Alert: "CORE_BANKING_UNAVAILABLE" after 3 consecutive funding failures
  C7 degradation level: Level 2 (processing continues; funding fails)
  Recovery: automatic — next offer attempt after core banking recovers will succeed

Scenario F — Kafka Consumer Lag
  lip.offers.pending consumer lag > 60s:
    Alert: "OFFER_CONSUMER_LAG_HIGH"
    Behavior: processing continues; backlogged offers may expire (60s window)
    Implication: high lag = high offer expiry rate = lower effective throughput
    Mitigation: investigate C7 processing time per offer; check CPU/memory

  lip.repayment.instructions consumer lag > 60s:
    Alert: "REPAYMENT_CONSUMER_LAG_HIGH" — higher severity
    Behavior: settlement executions are delayed; loans may default unnecessarily
    Escalation: if lag > 300s, escalate to "REPAYMENT_CONSUMER_LAG_CRITICAL"
    Mitigation: C7 pod count can be increased (consumer group adds capacity)

Scenario G — C7 Pod Node Failure
  One of two replicas lost (node failure)
  Behavior: remaining replica picks up full Kafka consumer load
    No offers are lost (messages remain in lip.offers.pending)
    Human review queue: in-progress reviews are preserved in Redis
    Funded loan state: preserved in Redis (HA) and C3 Flink (RocksDB)
  Alert: Kubernetes node failure alert (separate monitoring)
  C7 alert: none (Kubernetes handles pod rescheduling)
  Recovery: Kubernetes reschedules pod on available node; ~30-45s to ready
    (dominated by C4 model load time from volume mount)
```

### 9.3 Degraded Mode Logging

Every DecisionLogEntry written during degraded mode carries:
```
degraded_mode         : bool    // true if ANY Level 1+ degradation active
degraded_components   : string[]  // "C4_UNAVAILABLE" | "C1_CPU_FALLBACK" |
                                   //  "KMS_GAP_RECOVERY" | etc.
kms_unavailable_gap   : bool    // true if entry written during KMS recovery
                                 //   (entry may have been temporarily buffered)
```

This is an EU AI Act Art.13 requirement: every automated decision must disclose
the conditions under which it was made, including whether any system component
was operating in a degraded state.

### 9.4 Auto-Recovery Behavior

C7 does not require manual intervention to recover from any degraded mode except:
- Kill switch: requires explicit operator deactivation (or watchdog threshold clear)
- Core banking failure: recovers automatically when core banking API responds
- KMS unavailability: recovers automatically when KMS responds
- C4 process failure: process supervisor restarts C4 automatically

All auto-recoveries are logged:
```
"C7_AUTO_RECOVERY": {
  component: string,
  degradation_started_utc: int64,
  degradation_resolved_utc: int64,
  duration_seconds: int32,
  offers_blocked_during_gap: int32,
  repayments_deferred_during_gap: int32  // 0 except for KMS gap
}
```

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026 | Lead: NOVA | Version: 1.0*
*Part 1 of 2 — continue to BPI_C7_Component_Spec_v1.0_Part2.md for Sections 10–18*
