# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 7 — EMBEDDED EXECUTION AGENT
## Build Specification v1.0 — Part 2 of 2
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** NOVA — Payments Infrastructure Engineering
**Support:** FORGE (Kubernetes / container hardening), REX (DORA / EU AI Act),
             CIPHER (network isolation / adversarial testing), LEX (claim language),
             QUANT (fee arithmetic verification)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

> Part 2 of 2. Covers Sections 10–20: Human Override, Immutable Decision Log,
> Repayment Execution, Outbound pacs.008, Network Isolation, KMS Integration,
> Integration Requirements, Monitoring, Known Limitations, Validation Requirements,
> and Audit Gate 2.2 Checklist.
> See BPI_C7_Component_Spec_v1.0_Part1.md for Sections 1–9.

---

## TABLE OF CONTENTS — PART 2

10. Human Override Interface
    10.1 When Human Review Is Triggered
    10.2 Human Review Queue
    10.3 Reviewer Decision Protocol
    10.4 Override Constraints (Immutable)
11. Immutable Decision Log
    11.1 Why It Exists
    11.2 DecisionLogEntry Schema
    11.3 Entry Signing Protocol
    11.4 Replay Guarantee (DORA Art.30)
12. Repayment Execution
    12.1 Repayment Consumer
    12.2 Repayment Idempotency
    12.3 Repayment Failure Handling
13. Outbound pacs.008 Publication
    13.1 Why C7 Owns This
    13.2 Outbound pacs.008 Schema
    13.3 Sequencing Guarantee
14. Network Isolation
    14.1 Zero-Trust Boundary Enforcement
    14.2 C4 On-Device Isolation
    14.3 Data Residency
15. KMS Integration
    15.1 KMS Role in C7
    15.2 KMS Operations
    15.3 KMS vs. Kill Switch — Explicit Distinction
16. Integration Requirements (Bank-Side)
17. Monitoring & Alerting
    17.1 Execution Health
    17.2 Safety & Compliance
    17.3 Repayment Health
    17.4 Alert Routing
18. Known Limitations & Open Design Questions (NOVA Self-Critique)
    18.1 Human Review UI Is Bank-Built
    18.2 Core Banking Adapter Is Untestable Without Bank UAT Access
    18.3 C4 Model Version Lag
    18.4 Offer Expiry Window May Be Too Tight for Human Review
    18.5 Repayment Confirmation Loop Is One-Way
19. Validation Requirements
    19.1 Offer Processing Path Tests
    19.2 Idempotency Tests
    19.3 Decision Log Integrity Tests
    19.4 Kill Switch Tests
    19.5 Fee Arithmetic Verification (QUANT)
    19.6 Network Isolation Verification (CIPHER)
20. Audit Gate 2.2 Checklist

---

## 10. HUMAN OVERRIDE INTERFACE

### 10.1 When Human Review Is Triggered

```
Four trigger conditions route an offer to human review:

  1. pd_estimate >= bank_pd_threshold_review
     (default: 15% PD — bank-configurable)

  2. offer.requires_human_review = true
     (set by Decision Engine for corridor-level policy overrides)

  3. C4 LLM path returns uncertain result (confidence 0.3–0.7)
     AND amount $50K–$500K

  4. C6 velocity block flagged (NOT sanctions — sanctions = no override)
     AND bank compliance officer initiates manual review
```

### 10.2 Human Review Queue

```
On trigger: C7 publishes to lip.human.review.queue

HumanReviewRequest {
  review_id             : string   // UUID v4
  uetr                  : string   // individual UETR
  individual_payment_id : string   // explicit individual identifier
  offer_expiry_utc      : int64    // original 60s window — may already be close
  review_deadline_utc   : int64    // = offer_expiry_utc (no extension granted)
  loan_amount_usd       : double
  pd_estimate           : float
  rejection_code_class  : string
  corridor              : string
  trigger_reason        : string   // "PD_THRESHOLD" | "C4_UNCERTAIN" |
                                   //  "C6_VELOCITY" | "POLICY_OVERRIDE"
  pd_shap_summary       : string   // top 3 SHAP drivers, human-readable
  c4_confidence         : float    // dispute classifier confidence score
  c6_summary            : string   // velocity signals summary
  remittance_info       : string   // raw RmtInf — reviewer sees full text
}
```

**Review deadline is the original offer_expiry_utc. No extensions.**
If the reviewer does not respond before expiry:
- Amount ≤ $500K: offer expires → OFFER_EXPIRED (standard path)
- Amount > $500K: HARD BLOCK (Architecture Spec S3.4 LLM timeout rule)

### 10.3 Reviewer Decision Protocol

```
Reviewer submits via bank operator UI:

HumanReviewDecision {
  review_id      : string   // matches HumanReviewRequest.review_id
  uetr           : string   // redundant check — must match
  decision       : string   // "APPROVE" | "DECLINE"
  operator_id    : string   // authenticated bank operator (audited)
  justification  : string   // mandatory free-text (min 20 chars)
                            // logged verbatim in DecisionLogEntry
  timestamp_utc  : int64
}

On APPROVE:
  → C7 resumes at Step 7 (funding execution)
  → ExecutionConfirmation.human_reviewed = true
  → ExecutionConfirmation.elo_operator_id = operator_id
  → DecisionLogEntry records: operator_id, justification, review_duration_ms

On DECLINE:
  → ExecutionConfirmation (accepted = false, decline_reason = "HUMAN_DECLINED")
  → DecisionLogEntry records: same fields as above
  → No retry, no re-offer on this UETR for 24h

On timeout (no decision before expiry):
  → Treated as DECLINE
    (amounts <= $500K: OFFER_EXPIRED; >$500K: HARD_BLOCK)
  → Alert: "HUMAN_REVIEW_TIMEOUT" with review_id + uetr + amount
```

### 10.4 Override Constraints (Immutable)

```
CANNOT be overridden by any human, any operator level:
  x sanctions_match = true (C6)      — absolute block, no exceptions
  x kill_switch_active = true        — halts all execution
  x KMS unavailable                  — no key = no log = no execution

CAN be overridden with dual authorization:
  + C6 velocity blocks (non-sanctions)
  + C4 dispute uncertain (not hard block)
  + PD above review threshold (below hard block threshold)

Cannot be hot-overridden (requires config change + restart):
  - bank_pd_threshold_hard_block
  - bank_pd_threshold_review
  - Kill switch watchdog thresholds
```

---

## 11. IMMUTABLE DECISION LOG

### 11.1 Why It Exists

C7 is the only component that moves money. Every automated decision — fund, decline,
block, expire, override — must be reconstructable from the log alone, with proof that
the log has not been tampered with. This is not an audit nicety. It is a DORA Art.30
requirement and an EU AI Act Art.17 requirement. It is also the primary evidence base
if a funded loan defaults and the bank needs to demonstrate that its governance
controls operated correctly.

### 11.2 DecisionLogEntry Schema

```
DecisionLogEntry {
  log_entry_id           : string   // UUID v4
  uetr                   : string   // individual UETR
  individual_payment_id  : string   // explicit individual identifier
  event_type             : string   // "LOAN_FUNDED" | "OFFER_DECLINED" |
                                    //  "OFFER_EXPIRED" | "HARD_BLOCK_C4" |
                                    //  "HARD_BLOCK_C6" | "FUNDING_FAILED" |
                                    //  "HUMAN_APPROVED" | "HUMAN_DECLINED" |
                                    //  "HUMAN_REVIEW_TIMEOUT" |
                                    //  "KILL_SWITCH_ACTIVATED" |
                                    //  "KILL_SWITCH_DEACTIVATED" |
                                    //  "REPAYMENT_EXECUTED" |
                                    //  "REPAYMENT_FAILED" |
                                    //  "IDEMPOTENT_DUPLICATE_SUPPRESSED"
  timestamp_utc          : int64    // C7 wall-clock (NTP-synced)
  loan_amount_usd        : double
  funded_amount_usd      : double   // actual (post bank rounding); 0.0 if declined
  fee_bps                : float    // annualized
  pd_estimate            : float
  rejection_code         : string
  rejection_code_class   : string   // A | B | C | UNKNOWN
  maturity_days          : int32
  corridor               : string
  decline_reason         : string   // populated if not LOAN_FUNDED
  c4_result              : string   // "CLEAR" | "DISPUTE" | "UNCERTAIN" | "UNAVAILABLE"
  c4_confidence          : float
  c6_hard_block          : bool
  c6_sanctions_match     : bool
  human_reviewed         : bool
  operator_id            : string   // if human_reviewed = true
  operator_justification : string   // if human_reviewed = true
  kill_switch_active     : bool     // state at time of decision
  kms_available          : bool     // state at time of decision
  model_version_c1       : string
  model_version_c2       : string
  model_version_c4       : string
  bank_id                : string   // which bank deployment
  entry_signature        : string   // HMAC-SHA256 — see 11.3
}
```

### 11.3 Entry Signing Protocol

```
Signing key: bank-controlled HMAC-SHA256 key (via KMS — Section 15)
             Bridgepoint has zero access to this key.

Signature computation:
  canonical_string = "{log_entry_id}|{uetr}|{event_type}|{timestamp_utc}|
                      {loan_amount_usd}|{funded_amount_usd}|{pd_estimate}|
                      {decline_reason}|{operator_id}|{bank_id}"
  entry_signature = HMAC-SHA256(canonical_string, bank_hmac_key)

Verification:
  Any party with the bank's HMAC key can verify any entry has not been
  tampered with since it was written. If canonical_string recomputed from
  the stored entry does not match the stored entry_signature: the entry
  has been modified. Alert: "DECISION_LOG_INTEGRITY_VIOLATION".

Log destination: lip.decisions.log (Kafka, append-only)
  Retention   : 7 years (Architecture Spec S11.7)
  Topic config: cleanup.policy = delete (not compact)
                retention.ms   = 7 * 365 * 24 * 3600 * 1000
                min.insync.replicas = 2
                replication.factor  = 3

Write failure handling:
  If lip.decisions.log write fails: C7 DOES NOT execute the loan.
  No log = no execution. This is the strongest possible enforcement.
  Retry: 3 attempts, 100ms backoff.
  After 3 failures: watchdog threshold check -> possible kill switch trigger.
  Alert: "DECISION_LOG_WRITE_FAILURE" fires on first failure.
```

### 11.4 Replay Guarantee (DORA Art.30)

For any funded individual UETR loan, a compliance officer must be able to
reconstruct the full decision chain from the log alone:

```
Reconstruction query (by UETR):
  SELECT * FROM lip.decisions.log WHERE uetr = '{uetr}'
  ORDER BY timestamp_utc ASC

Expected entries (happy path):
  1. event_type = "LOAN_FUNDED"
     — with all scores, model versions, operator if reviewed
  2. event_type = "REPAYMENT_EXECUTED"
     — with settlement_source, days_funded, fee_usd

Expected entries (human review path):
  1. event_type = "HUMAN_APPROVED"   — with operator_id + justification
  2. event_type = "LOAN_FUNDED"
  3. event_type = "REPAYMENT_EXECUTED"

Validation test: pick 5 funded loans from UAT; reconstruct full lifecycle
from log entries only; verify every field is present and signature validates.
This test is a mandatory Audit Gate 2.2 item.
```

---

## 12. REPAYMENT EXECUTION

### 12.1 Repayment Consumer

C7 consumes `lip.repayment.instructions` (produced by C3). This runs as a
separate goroutine from the offer processor — the two run concurrently and
independently.

```
RepaymentRequest (to CoreBankingAdapter):

  loan_reference         : string   // original bank loan ID from ExecutionConfirmation
  uetr                   : string   // individual UETR
  individual_payment_id  : string   // explicit individual identifier
  repayment_amount_usd   : double   // principal + fee (from C3 RepaymentInstruction)
  principal_usd          : double
  fee_usd                : double
  days_funded            : int32    // actual, not maturity_days
  settlement_source      : string   // signal source from C3
  is_buffer_repayment    : bool
  repayment_reference    : string   // UUID v4 — C7-generated idempotency key
  instruction_id         : string   // from C3 RepaymentInstruction (their key)
  repayment_timestamp    : int64    // C7 wall-clock

RepaymentResponse (from CoreBankingAdapter):
  success                : bool
  bank_repayment_id      : string
  repaid_timestamp_utc   : int64
  failure_reason         : string   // if success = false
```

### 12.2 Repayment Idempotency

Two layers, same pattern as funding:

**Layer 1 — C7 Redis:**
```
SETNX "c7:repayment:pending:{repayment_reference}" "{instruction_id}"
  Returns 1: proceed
  Returns 0: duplicate — fetch prior response from Redis, return it
```

**Layer 2 — Core banking adapter:**
`repayment_reference` is the idempotency key. If bank returns `DUPLICATE_REQUEST`:
call `GetLoanStatus(loan_reference)` to confirm repayment already executed.

### 12.3 Repayment Failure Handling

```
Transient failure (SYSTEM_UNAVAILABLE):
  Retry: 3 attempts, exponential backoff (2s, 4s, 8s)
  Same repayment_reference across all retries
  After 3 failures: alert "REPAYMENT_EXECUTION_FAILED"

Permanent failure (loan_reference not found in bank system):
  This is a critical defect — a funded loan has no record in core banking.
  Alert: "REPAYMENT_ORPHANED_LOAN" — highest severity
  Human intervention mandatory: bank ops team reconciles manually
  No automated retry after orphan alert fires

Fee floor enforcement at repayment:
  fee_usd MUST be >= (principal_usd * 0.0003 * (7 / 365))
  i.e., >= floor at 300 bps annualized for a 7-day cycle
  If C3 sends a fee below floor (C3 also enforces — defense-in-depth):
    C7 overrides to floor value; logs "FEE_FLOOR_ENFORCED"

Post-repayment:
  Publish: lip.repayment.confirmations -> MIPLO (closes loan lifecycle)
  Write:   DecisionLogEntry (event_type = "REPAYMENT_EXECUTED")
           Include: settlement_source, days_funded, fee_usd, repaid_timestamp
  Publish: lip.state.transitions (ACTIVE -> REPAID terminal)
```

---

## 13. OUTBOUND PACS.008 PUBLICATION

This section directly addresses the C3 integration flag (C3 Spec Section 14,
Requirement 1).

### 13.1 Why C7 Owns This

C3's RTP UETR mapper requires a mapping of `EndToEndId -> UETR` for every outbound
payment. That mapping must be written to Redis before any RTP settlement signal can
arrive. The bank's ELO (C7) initiates the payment — it is the only component that
knows both the UETR and the EndToEndId at the moment of funding confirmation.

C7 publishes an outbound pacs.008 event immediately after receiving a successful
FundingResponse from the core banking adapter.

### 13.2 Outbound pacs.008 Schema

```
OutboundPaymentEvent {
  uetr                  : string   // individual UETR
  individual_payment_id : string   // explicit individual identifier
  end_to_end_id         : string   // from original payment — bank sourced
  bic_sender            : string   // BIC8 of sending bank
  bic_receiver          : string   // BIC8 of receiving bank
  currency_pair         : string   // e.g., "USD_GBP"
  amount_usd            : double
  maturity_days         : int32    // for C3 Redis TTL calculation
  rejection_code_class  : string   // for context in C3
  funded_timestamp_utc  : int64
  rail                  : string   // "RTP" | "SWIFT" | "FEDNOW" | "SEPA_INSTANT"
  bank_id               : string
}
```

Published to: `lip.payments.outbound` (consumed by C3 RTP UETR mapper)

### 13.3 Sequencing Guarantee

```
Guaranteed sequence per individual UETR:
  T+0ms : FundingResponse.success = true received from core banking
  T+1ms : Redis pending entry updated to CONFIRMED
  T+2ms : lip.payments.outbound published   <- C3 RTP mapper writes Redis
  T+3ms : lip.loans.funded published        <- C3 activates settlement monitoring

This order is enforced in code. lip.payments.outbound MUST be published
before lip.loans.funded. C3 activating monitoring before the UETR mapping
is written creates the race condition described in C3 Spec Section 6.3.

Code review requirement: any change to this publication sequence requires
two-reviewer sign-off with explicit race condition analysis documented.
```

---

## 14. NETWORK ISOLATION

### 14.1 Zero-Trust Boundary Enforcement

```
C7 has ZERO outbound network connections to:
  x Bridgepoint infrastructure (any IP, any port)
  x External internet
  x Cloud metadata endpoints (IMDSv2 blocked by network policy)
  x Any service outside bank VPC

C7 permitted outbound connections (bank-internal only):
  + Kafka brokers         (TLS 1.3, SASL/SCRAM-SHA-512)
  + Redis cluster         (TLS 1.3, AUTH token)
  + Bank core banking API (mTLS)
  + Bank KMS              (TLS 1.3)
  + Bank NTP server       (UDP 123, bank-internal)
  + Bank operator UI      (for human review — bank-internal only)

Enforcement mechanisms:
  Kubernetes NetworkPolicy:
    spec.podSelector : matches lip-execution namespace
    spec.egress      : whitelist only — everything else denied by default
    spec.ingress     : Kafka + gRPC from MIPLO only

CIPHER adversarial test: attempt outbound connection to
  8.8.8.8:53, any external IP, any Bridgepoint endpoint.
  ALL must be blocked at network policy level.
  If any connection succeeds: critical security defect.
```

### 14.2 C4 On-Device Isolation

C4 model weights and inference happen entirely within the C7 container.
No model update is pulled automatically. Updates follow this protocol:

```
Model update protocol:
  1. Bridgepoint produces new GGUF weights (out-of-band, off-platform delivery)
  2. Bank security team reviews and approves model file (hash-verified)
  3. Bank uploads to bank-controlled object storage (not Bridgepoint storage)
  4. Bank schedules rolling C7 pod restart (init container pulls new weights)
  5. C7 logs on startup: model_version_c4 = "{version_from_model_manifest}"

The bank can reject any model update. Bridgepoint cannot push model updates
without bank consent and bank-controlled deployment.
This is the architectural proof of ELO independence.
```

### 14.3 Data Residency

```
Data produced by C7 and where it lives:

  lip.decisions.log          : bank Kafka -> bank archival (7-year retention)
  lip.loans.funded           : bank Kafka (consumed by C3 in bank infra)
  lip.payments.outbound      : bank Kafka (consumed by C3 in bank infra)
  lip.repayment.confirmations: bank Kafka
  lip.state.transitions      : bank Kafka
  Redis keyed state          : bank Redis cluster

Nothing leaves bank infrastructure. Bridgepoint receives:
  -> Aggregated, anonymized royalty reporting only (separate telemetry path,
     bank-controlled, no individual UETR data, no PII)
  -> That path is out of scope for this spec — handled in licensing agreement.
```

---

## 15. KMS INTEGRATION

### 15.1 KMS Role in C7

KMS serves two functions in C7:

1. **HMAC signing key** for decision log entries (tamper-evidence)
2. **Availability gate** — if KMS is unreachable, C7 declines all new offers
   (Architecture Spec S2.5)

### 15.2 KMS Operations

```
At startup:
  C7 performs KMS connectivity check.
  If KMS unreachable at startup: C7 refuses to start.
  Reason: starting in a state where log entries cannot be signed is
  operationally worse than not starting at all.

Per offer (Step 4 in Section 6.1):
  Lightweight KMS ping (< 5ms round-trip on bank-internal network)
  If KMS unreachable: decline "KMS_UNAVAILABLE"
  Log entry written with kms_available = false
  Note: signing an entry with kms_available = false is still valid —
  the entry records the failure; KMS availability is a pre-condition
  for execution, not for logging.

Per log entry:
  HMAC-SHA256 computed using bank KMS-managed key.
  C7 does NOT store the raw key in memory beyond the signing operation.
  Key retrieved via KMS API per signing call (or short TTL cache: 30s).

KMS unavailability mid-operation:
  -> Halt execution of any NEW offers immediately
  -> Complete in-flight funding calls already in EXECUTING state
  -> Log those completions with kms_available = false (entry unsigned)
  -> Alert: "KMS_UNAVAILABLE_HALT"
  -> Auto-resume when KMS connectivity restored
  -> Watchdog: if KMS unavailable > 3 consecutive 60s health checks
              -> trigger automated kill switch (Section 8.1 Type 2)
```

### 15.3 KMS vs. Kill Switch — Explicit Distinction

```
KMS unavailability:
  -> C7 halts NEW offer processing
  -> In-flight funding completes (cannot abandon a funded loan mid-execution)
  -> Auto-resumes when KMS returns
  -> No manual intervention required unless watchdog triggers kill switch

Kill switch:
  -> C7 halts ALL processing including repayment instructions
  -> Does NOT auto-resume — requires explicit operator deactivation
  -> Deactivation requires dual authorization (two operator IDs)

These are separate control planes. KMS unavailability is an infrastructure
failure mode with automatic recovery. Kill switch is a governance control
with deliberate human activation and deliberate human deactivation.
Conflating them produces a kill switch that auto-deactivates —
which defeats its purpose entirely.
```

---

## 16. INTEGRATION REQUIREMENTS (BANK-SIDE)

These mirror the requirements flagged in C3 Spec Section 14, now stated from
C7's perspective as the producing component.

```
Requirement 1 — Outbound pacs.008 (C7 OWNS THIS):
  C7 publishes OutboundPaymentEvent to lip.payments.outbound after every
  successful FundLoan call. This is C7's responsibility — confirmed. RESOLVED.

Requirement 2 — Core banking adapter UAT test (HARD GATE):
  Before any corridor goes live, bank adapter must pass all 4 tests:
  (a) FundLoan with new loan_reference           -> success
  (b) FundLoan with same loan_reference (repeat) -> DUPLICATE_REQUEST
  (c) RepayLoan for loan funded in (a)           -> success
  (d) GetLoanStatus for loan from (a)            -> correct status
  All 4 must pass in bank UAT environment before production activation.
  No production traffic flows through an untested adapter.

Requirement 3 — Kafka topic creation:
  Bank Kafka admin must create all 8 topics in Section 3.2 before deployment.
  Topic configs per Section 11.3 (decisions.log) and Architecture Spec S2.3.

Requirement 4 — Redis cluster:
  Bank Redis cluster available and authenticated before C7 startup.
  C7 readiness probe checks Redis; pod will not receive traffic until ready.

Requirement 5 — Bank operator UI for human review:
  Bank deploys the human review interface reading from lip.human.review.queue
  and writing HumanReviewDecision responses.
  Bridgepoint provides the API contract (Section 10).
  Bank builds and hosts the UI within their own infrastructure.

Requirement 6 — C4 model deployment:
  Bank completes the init container + model volume mount setup before production.
  C7 readiness probe checks C4 model is loaded; pod will not receive traffic until ready.

Requirement 7 — NTP synchronization:
  Bank infrastructure clock synchronized to NTP within +/- 1 second.
  C7 alert fires if drift > 5 seconds (Section 5.3 clock skew guard).
```

---

## 17. MONITORING & ALERTING

### 17.1 Execution Health

```
offer_processing_rate              offers/minute consumed from lip.offers.pending
offer_acceptance_rate              % of offers resulting in LOAN_FUNDED
offer_decline_breakdown            % per decline_reason across all codes
funding_execution_latency_p50/p99  ms from offer receipt to ExecutionConfirmation
funding_failure_rate               % of EXECUTING states -> DECLINED/FUNDING_FAILED
human_review_rate                  % of offers requiring human review
human_review_approval_rate         % of human reviews resulting in approval
human_review_timeout_rate          % of reviews that time out (alert if > 5%)
```

### 17.2 Safety & Compliance

```
hard_block_c4_rate                 % of offers hard-blocked by C4
hard_block_c6_rate                 % of offers hard-blocked by C6
sanctions_block_count              absolute count per day (any non-zero = review)
kms_unavailability_duration        seconds per incident; alert if > 30s
kill_switch_activations            absolute count; any activation = immediate escalation
decision_log_write_failure_rate    % of entries that fail to write; alert if > 0%
decision_log_integrity_violations  absolute count; any non-zero = critical defect
c4_unavailability_duration         seconds per incident; alert if > 60s
clock_skew_events                  count per day; alert on first occurrence
```

### 17.3 Repayment Health

```
repayment_execution_rate           repayments executed per day
repayment_failure_rate             % failing at core banking; alert if > 1%
orphaned_loan_count                absolute count (must be zero forever)
repayment_latency_p50/p99          ms from C3 instruction to bank confirmation
fee_floor_enforcement_count        times C7 overrode C3 fee below floor (should be 0)
buffer_repayment_proportion        % of repayments from statistical buffer vs. explicit
```

### 17.4 Alert Routing

```
CRITICAL (page on-call immediately):
  DECISION_LOG_INTEGRITY_VIOLATION
  REPAYMENT_ORPHANED_LOAN
  KILL_SWITCH_AUTO_TRIGGERED
  CAPITAL_EXHAUSTION_WARNING
  C7_CLOCK_SKEW_CRITICAL
  DECISION_LOG_WRITE_FAILURE (after 3 retries)

HIGH (alert within 15 minutes):
  FUNDING_EXECUTION_FAILED
  KMS_UNAVAILABLE_HALT
  HUMAN_REVIEW_TIMEOUT_RATE > 5%
  C4_UNAVAILABLE > 60s

MEDIUM (alert within 1 hour):
  REPAYMENT_EXECUTION_FAILED
  RTP_UNMAPPED_SETTLEMENT (from C3, surfaced in C7 dashboard)
  DAILY_FUNDING_LIMIT_REACHED
  FEE_FLOOR_ENFORCED (any occurrence)

LOW (daily digest):
  OFFER_EXPIRED_RATE > 20%
  IDEMPOTENT_DUPLICATE_SUPPRESSED (rate spike)
  HUMAN_REVIEW_RATE > 30% (policy review warranted)
```

---

## 18. KNOWN LIMITATIONS & OPEN DESIGN QUESTIONS (NOVA SELF-CRITIQUE)

### 18.1 Human Review UI Is Bank-Built

C7 publishes to `lip.human.review.queue` and consumes `HumanReviewDecision` responses.
The UI that bank operators use is built and hosted by the bank. Bridgepoint provides
the API contract. We have no visibility into whether the bank's UI correctly enforces
dual-authorization or logs reviewer justifications.

**Mitigation:** C7 validates that `operator_id` and `justification` are both present
and non-empty before accepting any HumanReviewDecision. If either is absent: reject
the decision, log `HUMAN_REVIEW_MALFORMED_RESPONSE`, and treat as timeout. The bank's
UI may be opaque to us, but C7's API boundary enforcement makes its internal behavior
irrelevant to correctness.

### 18.2 Core Banking Adapter Is Untestable Without Bank UAT Access

C7 can be tested end-to-end with a mock CoreBankingAdapter. But the actual bank
adapter — `BankACoreAdapter`, `BankBCoreAdapter`, etc. — cannot be validated until
we have UAT environment access from the bank.

> **Note:** BankA / BankB / BankC are illustrative placeholders. No specific
> institution is contemplated by these names — any ISO-20022-speaking
> correspondent bank can be integrated via a CoreBankingAdapter subclass. The adapter layer carries integration
risk that does not resolve until pilot onboarding.

**Mitigation:** Requirement 2 (Section 16) mandates a 4-test UAT battery before
any corridor goes live. This is a hard gate, not a recommendation. No production
traffic flows through an untested adapter.

### 18.3 C4 Model Version Lag

Banks control C4 model deployment. A bank may run an outdated C4 version for months
if their internal change management is slow. C7 logs `model_version_c4` in every
DecisionLogEntry — version lag is auditable. But outdated C4 means lower dispute
detection accuracy: false negatives increase as the model drifts from current
remittance text patterns.

**Mitigation:** ARIA's quarterly C4 retraining cycle (C4 Spec Section 14) should
include a version deprecation notice to banks: "version X reaches EOL on date Y."
C7 should emit a daily alert if `model_version_c4` is more than 2 minor versions
behind current release. Flagged for inclusion in the C4 deployment guide.

### 18.4 Offer Expiry Window May Be Too Tight for Human Review

The 60-second offer expiry window was designed for automated processing (milliseconds).
Human review on a $400K loan in 60 seconds is operationally demanding — reviewers
need time to read SHAP explanations, RmtInf content, and make a judgment.

**Assessment:** 60 seconds is the correct window for the underlying payment failure
signal — market intelligence degrades beyond that. A reviewer who cannot act in
60 seconds produces an OFFER_EXPIRED — a conservative outcome (no loan issued),
not a capital risk outcome. The limitation is a false negative on legitimate lending
opportunities, not a safety risk.

**Potential resolution (not yet decided):** A "pre-approved corridor" concept where
banks pre-approve lending on specific high-volume corridors up to a dollar limit
without per-offer human review. Flagged as Phase 3 feature discussion.

### 18.5 Repayment Confirmation Loop Is One-Way

C7 publishes `lip.repayment.confirmations` to MIPLO after executing repayment.
MIPLO does not send a confirmation back to C7. If MIPLO fails to process the
repayment confirmation, C7 has no visibility — the loan appears repaid in C7's
log, but MIPLO's state is stale.

**Assessment:** Acceptable trade-off. C7's source of truth is the bank's core
banking system and the immutable decision log. MIPLO's state machine is a derived
representation. If MIPLO state becomes stale, a reconciliation process can rebuild
it from C7's `lip.decisions.log`. Risk: monitoring gap in MIPLO dashboards, not
a capital risk.

---

## 19. VALIDATION REQUIREMENTS

### 19.1 Offer Processing Path Tests

```
Happy path (automated approval):
  [ ] Feed LoanOffer: pd=0.05, no blocks, KMS up, C4 clear
  [ ] Verify: LOAN_FUNDED ExecutionConfirmation published
  [ ] Verify: OutboundPaymentEvent published BEFORE lip.loans.funded
  [ ] Verify: DecisionLogEntry event_type="LOAN_FUNDED", HMAC valid
  [ ] Verify: all 10 processing steps completed in documented order

Expiry path:
  [ ] Feed LoanOffer with offer_expiry_utc = (now - 1000ms)
  [ ] Verify: OFFER_EXPIRED decline; no funding call made; log entry written

C6 sanctions block:
  [ ] Feed LoanOffer with c6_aml_result.sanctions_match = true
  [ ] Verify: HARD_BLOCK_C6; no human review offered; log written
  [ ] Verify: UETR added to 24h block list in Redis

C6 absent (malformed offer):
  [ ] Feed LoanOffer with c6_aml_result field absent
  [ ] Verify: treated as hard block (fail-safe); declined; logged

C4 dispute detected (fast-path):
  [ ] Feed LoanOffer with clear dispute language in remittance_info
  [ ] Verify: C4 fast-path confidence > 0.7
  [ ] Verify: HARD_BLOCK_C4; log written

C4 unavailable:
  [ ] Kill C4 process within C7 container
  [ ] Feed offer with amount > $50K threshold
  [ ] Verify: C4_UNAVAILABLE decline (fail-safe for large amounts)
  [ ] Feed offer with amount < $50K threshold
  [ ] Verify: offer proceeds; c4_result = "UNAVAILABLE" logged

KMS unavailable:
  [ ] Simulate KMS connectivity failure
  [ ] Feed LoanOffer
  [ ] Verify: KMS_UNAVAILABLE decline; no funding call; KMS_UNAVAILABLE_HALT alert

PD above hard block threshold:
  [ ] Feed LoanOffer with pd_estimate = 0.45 (above default 0.40)
  [ ] Verify: PD_THRESHOLD_EXCEEDED decline; no human review

PD above review threshold (below hard block):
  [ ] Feed LoanOffer with pd_estimate = 0.20
  [ ] Verify: routes to lip.human.review.queue
  [ ] Simulate human APPROVE -> verify proceeds to funding
  [ ] Simulate human DECLINE -> verify HUMAN_DECLINED; no funding
  [ ] Simulate timeout (<=$500K) -> OFFER_EXPIRED
  [ ] Simulate timeout (>$500K) -> HARD_BLOCK
```

### 19.2 Idempotency Tests

```
[ ] Same LoanOffer Kafka message delivered twice (at-least-once redelivery)
    -> Exactly one ExecutionConfirmation; one funding call; one log entry

[ ] Funding call succeeds; response lost; C7 retries same loan_reference
    -> DUPLICATE_REQUEST from bank; C7 calls GetLoanStatus; returns original
    -> Exactly one ExecutionConfirmation; no double-funding

[ ] Two C7 replicas receive same offer (consumer group coordination failure)
    -> Kafka consumer group ensures one replica processes it
    -> If both somehow process: Redis SETNX catches duplicate; one execution
    -> Test: disable consumer group coordination; verify Redis layer catches it
```

### 19.3 Decision Log Integrity Tests

```
[ ] Fund a loan; retrieve DecisionLogEntry; recompute HMAC-SHA256
    -> Signature must match stored entry_signature

[ ] Modify any field in a stored entry (simulate tamper)
    -> Recomputed HMAC must NOT match entry_signature
    -> DECISION_LOG_INTEGRITY_VIOLATION alert fires

[ ] Write failure: make lip.decisions.log Kafka topic unwritable
    -> C7 must NOT execute the loan (no log = no execution)
    -> After 3 retries: DECISION_LOG_WRITE_FAILURE alert fires

[ ] Replay test: 5 funded loans reconstructed from log alone
    -> All fields present; signatures valid; lifecycle coherent
```

### 19.4 Kill Switch Tests

```
[ ] Manual activation (dual operator auth):
    -> All new offer processing halts immediately
    -> In-flight repayment instructions complete
    -> KILL_SWITCH_ACTIVATED log entry written; alert fires

[ ] Single operator activation attempt:
    -> Rejected; no kill switch activation; log entry written

[ ] Automated watchdog trigger (funding failure rate > 50% in 15 min):
    -> KILL_SWITCH_AUTO_TRIGGERED fires; processing halts; bank notified

[ ] Kill switch deactivation (dual operator auth):
    -> Processing resumes; KILL_SWITCH_DEACTIVATED log entry written

[ ] Kill switch deactivation attempt (single operator):
    -> Rejected — same dual-auth requirement as activation
```

### 19.5 Fee Arithmetic Verification (QUANT)

```
Test case: $100,000 loan, fee_bps = 300 (annualized), days_funded = 7

Correct calculation:
  fee_usd = 100,000 * (300 / 10,000) * (7 / 365)
          = 100,000 * 0.03 * 0.019178
          = $57.53

Verify C7 computes $57.53 +/- $0.01 (floating point tolerance)

CRITICAL wrong calculations — flag immediately as defects if seen:
  $3,000.00  applying 300 bps as flat (not annualized) — 52x too high
  $20.55     applying 0.0575% flat with no annualization

Test for all three maturity classes:
  3-day:   $100K * 0.03 * (3/365)  = $24.66
  7-day:   $100K * 0.03 * (7/365)  = $57.53
  21-day:  $100K * 0.03 * (21/365) = $172.60

All three must match +/- $0.01.
Fee floor: all three values are at or above the floor at 300 bps annualized.
```

### 19.6 Network Isolation Verification (CIPHER)

```
[ ] Attempt TCP connection to 8.8.8.8:53 from C7 pod  -> blocked
[ ] Attempt TCP connection to any external IP          -> blocked
[ ] Attempt connection to simulated Bridgepoint endpoint -> blocked
[ ] Verify only whitelisted bank-internal endpoints reachable
[ ] Verify C4 inference produces result without any network call
[ ] Attempt DNS exfiltration of uetr / remittance_info -> blocked
```

---

## 20. AUDIT GATE 2.2 CHECKLIST

Gate passes when ALL items are checked.
**NOVA signs.** LEX verifies claim language. FORGE verifies infrastructure.
REX verifies compliance. CIPHER verifies security. QUANT verifies fee arithmetic.

### Offer Processing
- [ ] All 10 processing steps in documented sequence — sequence integrity test passes
- [ ] Happy path end-to-end test passes (LOAN_FUNDED + log + pacs.008 sequencing)
- [ ] All decline paths tested; correct DecisionLogEntry per decline_reason confirmed
- [ ] Offer expiry 60s enforced; 2s NTP grace buffer tested
- [ ] Threshold misconfiguration guard (hard_block <= review) tested at startup

### Hard Block Enforcement
- [ ] C6 sanctions_match: hard block, no human override possible — tested
- [ ] C6 absent/malformed: treated as hard block (fail-safe) — tested
- [ ] C4 dispute detected fast-path: hard block — tested
- [ ] C4 unavailable + amount > $50K: hard block (fail-safe) — tested
- [ ] C4 unavailable + amount <= $50K: proceeds with c4_unavailable logged — tested
- [ ] KMS unavailable: no execution — tested

### Human Override
- [ ] PD threshold triggers human review queue correctly
- [ ] Human APPROVE -> funding proceeds; operator_id + justification in log
- [ ] Human DECLINE -> correct decline entry in log
- [ ] Review timeout <=\$500K -> OFFER_EXPIRED; >\$500K -> HARD_BLOCK — both tested
- [ ] Dual authorization for kill switch activation/deactivation — tested
- [ ] Single operator kill switch attempt -> rejected — tested
- [ ] Malformed HumanReviewDecision (missing operator_id or justification) -> rejected

### Decision Log
- [ ] All 14 event_types generate a DecisionLogEntry — confirmed
- [ ] HMAC-SHA256 signature valid on 50+ entries across all event types
- [ ] Tamper detection: modified entry -> integrity violation alert fires
- [ ] Write failure: no execution without confirmed log write — tested
- [ ] Replay test: 5 funded loan lifecycles reconstructed from log alone (DORA Art.30)
- [ ] 7-year retention config on lip.decisions.log verified

### Repayment Execution
- [ ] Repayment idempotency: duplicate instruction -> one execution — tested
- [ ] Repayment failure retries: 3 attempts, same repayment_reference — tested
- [ ] Orphaned loan alert fires when loan_reference not found in bank system — tested
- [ ] Fee floor enforcement at C7 level: overrides below-floor fee from C3 — tested
- [ ] Fee arithmetic: $57.53 for $100K / 300bps / 7-day verified +/- $0.01

### Outbound pacs.008
- [ ] OutboundPaymentEvent published before lip.loans.funded — sequence verified
- [ ] All required fields present including maturity_days (for C3 Redis TTL)
- [ ] C3 RTP mapper end-to-end: C7 publishes -> C3 resolves UETR — tested

### Kill Switch
- [ ] All 4 kill switch test scenarios pass (Section 19.4)
- [ ] Automated watchdog triggers at configured thresholds — tested
- [ ] State serialization on kill switch: no orphaned in-flight loans — tested
- [ ] KMS unavailability halt is DISTINCT from kill switch — behavior verified

### Network Isolation (CIPHER sign-off required)
- [ ] All 6 network isolation tests pass (Section 19.6)
- [ ] C4 inference produces no network calls — verified
- [ ] Zero egress to Bridgepoint infrastructure — verified
- [ ] Container image signed with Cosign; unsigned image rejected by admission controller

### KMS Integration (REX sign-off required)
- [ ] KMS availability check per offer — tested
- [ ] KMS unavailability -> halt, not fail-open — tested
- [ ] HMAC key rotation: no unsigned entries post-rotation — tested
- [ ] Bridgepoint has zero access to bank KMS key material — architecture verified

### IP & Claim Language (LEX sign-off required)
- [ ] "individual_payment_id" + "uetr" explicit in all 3 C7-produced schemas
- [ ] rejection_code_class + maturity_days in every LOAN_FUNDED DecisionLogEntry
- [ ] fee_bps annualized (not flat) — fee arithmetic test passes
- [ ] Zero mentions of Recentive v. Fox in this document

### Integration Requirements (FORGE sign-off required)
- [ ] Core banking adapter UAT 4-test battery passed (Requirement 2)
- [ ] All 8 Kafka topics created with correct configs (Requirement 3)
- [ ] C7 startup validation: refuses to start if KMS or Redis unreachable
- [ ] C7 readiness probe: not ready until C4 model loaded — tested
- [ ] Bank operator UI human review API contract validated end-to-end

### DORA / EU AI Act (REX sign-off required)
- [ ] Every automated lending decision has DecisionLogEntry — no gaps
- [ ] Human override logged with operator_id + justification — mandatory fields enforced
- [ ] Full lifecycle of 5 loans reconstructable from log (DORA Art.30 replay test)
- [ ] Model versions (C1, C2, C4) present in every LOAN_FUNDED entry
- [ ] EU AI Act Art.14 processing sequence integrity: all 10 steps in order

---

## OUTSTANDING ITEMS (NON-BLOCKING, FLAGGED)

**Item 1 — C7 Bank Deployment Guide (NOVA next deliverable):**
Section 16 Requirements 2 and 5 reference a deployment guide that does not yet exist.
This guide must be written before any bank pilot onboarding begins. It must include:
  - Core banking adapter integration test suite (Requirement 2, 4-test battery)
  - Bank operator UI API contract (Requirement 5, full HumanReviewDecision spec)
  - Kubernetes deployment manifest templates
  - Init container + C4 model volume mount instructions
  - Redis and Kafka topic setup runbook

**Item 2 — Pre-Approved Corridor Concept (Phase 3, not Phase 2):**
Section 18.4 flags the 60-second human review window as operationally challenging.
Pre-approved corridor lending (bank pre-approves specific corridors below a dollar
threshold without per-offer human review) would resolve this for high-volume corridors.
Flagged for Phase 3 design. No Phase 2 build impact.

**Item 3 — C4 Model Version Deprecation Process (ARIA + C4 Deployment Guide):**
Section 18.3 flags that banks may run outdated C4 models. A version deprecation
notice process needs to be defined in the C4 deployment guide. C7 daily alert for
model version lag > 2 minor versions should be added to the C7 monitoring spec above.

---

*C7 Build Specification v1.0 — Part 2 of 2 complete.*
*Sections 10–20 locked. Combined with Part 1: full C7 spec delivered.*
*Next deliverable: C7 Bank Deployment Guide.*
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: NOVA | Support: FORGE, REX, CIPHER, LEX, QUANT*
