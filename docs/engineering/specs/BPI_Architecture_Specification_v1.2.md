# BRIDGEPOINT INTELLIGENCE INC.
## ARCHITECTURE SPECIFICATION v1.2
### Phase 0 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.2 — Three blocking issues from v1.1 sign-off resolved
**Status:** PENDING FINAL SIGN-OFF (LEX, CIPHER, QUANT re-review only)
**Authors:** NOVA, ARIA
**Reviewers:** LEX, CIPHER, QUANT (re-review), ARIA/NOVA/REX/FORGE (already signed)
**Stealth Mode:** Active — Nothing External

> **Current-state addendum (2026-04-28):** this specification is the locked architecture baseline. For current staging RC artifacts, post-spec multi-rail additions, and production-final blockers, read [`../../CURRENT_STATE.md`](../../CURRENT_STATE.md).

---

## VERSION HISTORY

| Version | Date         | Changes                                              |
|---------|--------------|------------------------------------------------------|
| 1.0     | Mar 4, 2026  | Initial draft — 8 open design questions flagged      |
| 1.1     | Mar 4, 2026  | All 8 open questions resolved and locked             |
| 1.2     | Mar 4, 2026  | Three blocking sign-off issues resolved:             |
|         |              |  LEX: Added S3A three-entity role mapping            |
|         |              |  CIPHER: Added S2.5 KMS unavailability behavior      |
|         |              |  QUANT: Annotated fee_bps as annualized in S4.3      |

---

## TABLE OF CONTENTS

1. Overview & Scope
2. System Data Flow
   2.1 High-Level Flow
   2.2 Critical Path
   2.3 Settlement Path
   2.4 Outbound Payment Event (RTP UETR Mapping)
   2.5 Kill Switch & KMS Unavailability Behavior [NEW v1.2]
3. Component Inventory
3A. Three-Entity Role Architecture [NEW v1.2]
4. API Contracts
5. Message Schema Reference
6. Payment Lifecycle State Machine
7. Loan Lifecycle State Machine
8. Rejection Code Taxonomy
9. Data Boundaries & Encryption Standards
10. Latency Budget & Critical Path Analysis
11. Resolved Design Decisions
12. Phase 0 Sign-Off Gate

---

## 1. OVERVIEW & SCOPE

This document is the single source of truth for the complete internal
architecture of the Liquidity Intelligence Platform (LIP). Every
subsequent build deliverable must conform to the contracts defined here.

v1.2 adds three items missing from v1.1:
- Explicit three-entity role mapping (MLO/MIPLO/ELO) to components
- KMS unavailability fail-safe behavior in kill switch spec
- fee_bps annotation clarifying annualized rate in PDResponse

No open items remain after these additions.

---

## 2. SYSTEM DATA FLOW

### 2.1 High-Level Flow

```
[SWIFT Gateway]
      |
      | pacs.002 (payment status / rejection)
      v
[Kafka Ingestion Topic] --> [Flink Stream Processor]
                                      |
                          +-----------+-----------+
                          |                       |
                    [Feature Extractor]    [Corridor State Store]
                          |                (Redis - BIC-pair history)
                          |
              +-----------+-----------+-----------+
              |           |           |           |
        [C1: Failure  [C2: PD     [C4: Dispute [C6: AML
         Classifier]  Model]      Classifier]  Velocity]
              |           |           |           |
              +-----------+-----------+-----------+
                          |
                   [Decision Engine]
                   (aggregate signals,
                    apply blocks,
                    generate offer)
                          |
                   [C7: Execution Agent]
                   (bank-side container)
                          |
              +-----------+-----------+
              |                       |
        [Bank ELO           [Immutable Decision
         Interface]          Log (append-only)]
              |
        [Loan Funded]
              |
    +---------+---------+---------+---------+
    |         |         |         |         |
[camt.054] [FedNow] [RTP ISO] [SEPA Inst] [Buffer
                    20022]            Fallback]
    |
[Repayment Engine] --> [Loan State: REPAID]
    |
[Immutable Log Updated]
```

### 2.2 Critical Path (p50 Target: <100ms)

```
SWIFT pacs.002 received
    |  ~2ms   Kafka ingestion + deserialization
    v
Feature extraction (UETR, BIC-pair, rejection code, amount, timestamp)
    |  ~2ms   Redis lookup (corridor history, borrower embedding)
    v
Parallel inference block (all run concurrently):
    |  ~20-30ms  C1: GNN + TabTransformer (GPU required — see S11.1)
    |  ~3-5ms    C2: LightGBM PD model
    |  ~2ms      C6: AML velocity check (Redis hash lookup)
    |  ~2-3ms    Sanctions screening (in-memory list)
    |  ~3ms      C4: Fast-path binary classifier (dispute pre-check)
    v
    Wait for slowest parallel component (~20-30ms on GPU)
    |
C4 LLM path runs async — not on critical path (see S11.5)
    |  ~1ms   Decision engine: aggregate signals, apply block logic
    v
Offer generated (amount, maturity, fee, SHAP values packaged)
    |  ~1ms   Route to C7 execution agent
    v
TOTAL p50 (GPU):  ~26ms  [within 100ms target with margin]
TOTAL p99 (GPU):  ~51ms  [within 200ms target with margin]
TOTAL p50 (CPU):  ~86ms  [degraded mode ONLY — see S11.1]
TOTAL p99 (CPU): ~163ms  [degraded mode ONLY — see S11.1]
```

### 2.3 Settlement Path (Async — Not on Critical Path)

```
[Settlement Monitor] listens on all 5 signal channels:

Channel 1: SWIFT camt.054
    Parse BookgDt + Amt + UETR --> match to funded loan --> repay

Channel 2: FedNow pacs.002
    Parse TxSts = ACSC + OrgnlUETR --> match --> repay

Channel 3: RTP ISO 20022
    Parse settlement + resolve via EndToEndId mapping (see S2.4)
    Match UETR --> repay

Channel 4: SEPA Instant pacs.008
    Parse AccptncDtTm + UETR --> match --> repay

Channel 5: Statistical Buffer Fallback
    No signal within corridor P95 threshold (see S11.4)
    Trigger buffer repayment + generate soft alert

First valid signal on any channel triggers repayment.
Duplicate signals on subsequent channels: silently dropped (idempotent).
```

### 2.4 Outbound Payment Event (RTP UETR Mapping)

```
[Bank ELO initiates payment]
    |
    | pacs.008 (credit transfer initiation)
    v
[Kafka Topic: lip.payments.outbound]
    |
    v
[UETR Mapping Service]
    Writes: Redis HASH "rtp:e2e:{EndToEndId}"
    Fields: uetr, corridor, amount_usd, created_at, rail
    TTL:    maturity_days + 45 days (max 66 days)
    Partition key: UETR (ordered before any failure event)

Note: FedNow carries UETR natively — no mapping table needed.
RTP only: EndToEndId does not carry UETR without this mapping.
```

### 2.5 Kill Switch & KMS Unavailability Behavior [NEW v1.2]

Two distinct failure modes require explicit halt behavior.
Both are FAIL-SAFE — no ambiguity permitted in a financial system.

**Kill Switch (Manual or Automated Trigger):**
```
Trigger: operator command OR watchdog threshold breach
  1. C7 halts all new loan offer generation immediately
  2. All loans in FUNDED state: state preserved in Redis
     No state corruption permitted under any shutdown scenario
  3. Settlement monitoring: continues (read-only)
     Funded loans continue to repay normally via settlement signals
  4. All active state machines: serialized to persistent storage
     before pod termination
  5. Restart: C7 resumes from last persisted state
     No manual intervention required for recovery
```

**KMS Unavailability (Bank Key Management Service Unreachable):**
```
Trigger: bank KMS API returns error or timeout on key operation
  1. C7 halts new loan offer generation immediately (FAIL-SAFE)
     Rationale: cannot write to encrypted decision log = cannot
     maintain audit trail = cannot proceed with automated lending
  2. Loans currently in FUNDED state: preserved in Redis
     Settlement monitor continues in read-only mode
     Settlement signals buffered in Kafka for replay on recovery
  3. C5 Kafka and Redis: serve existing cached data only
     No new encrypted writes until KMS restored
  4. Alert: immediate escalation via configured alert channel
     Alert includes: timestamp, KMS endpoint, last successful op
  5. Auto-recovery: when KMS responds successfully
     C7 resumes offer generation without manual intervention
     Buffered settlement signals replayed in order
     All missed decisions logged with kms_unavailable_gap flag

KMS unavailability is NEVER a fail-open condition.
No automated lending proceeds without a functioning audit trail.
```

---

## 3. COMPONENT INVENTORY

| ID  | Name                          | Role                              | Lead   | Stack                  |
|-----|-------------------------------|-----------------------------------|--------|------------------------|
| C1  | Failure Prediction Classifier | Real-time payment failure scoring | ARIA   | Python, PyTorch, DGL   |
| C2  | PD Estimation Model           | Borrower probability of default   | ARIA   | Python, LightGBM       |
| C3  | Repayment Engine              | Settlement detection + repayment  | NOVA   | Java/Scala, Flink      |
| C4  | Dispute Classifier            | SWIFT remittance dispute detection| ARIA   | Python, llama.cpp      |
| C5  | Streaming Infrastructure      | Message routing + state mgmt      | FORGE  | Kafka, Flink, Redis    |
| C6  | AML Velocity Module           | Anti-money laundering controls    | CIPHER | Python, Redis, DGL     |
| C7  | Embedded Execution Agent      | Bank-side orchestration + logging | NOVA   | Go, Docker, K8s        |

---

## 3A. THREE-ENTITY ROLE ARCHITECTURE [NEW v1.2]

The LIP is designed as a three-entity system. Each entity owns a
distinct set of components and has clearly bounded responsibilities.
This separation is architecturally intentional — it is the structural
design decision that preserves divided infringement protection and
defines the licensing model.

---

### MLO — Machine Learning Operator (Bridgepoint)

**Components:** C1, C2

**Role:** Generates intelligence. Produces the ML-derived signals
(failure probability, PD estimate, SHAP values) that inform every
lending decision. Has no execution capability — cannot fund loans,
cannot move money, cannot access bank systems directly.

```
C1: Failure Prediction Classifier
    Generates: failure_probability per individual UETR-keyed payment
    Does NOT: execute any transaction

C2: PD Estimation Model
    Generates: pd_estimate, fee_bps, expected_loss_usd per borrower
    Does NOT: make credit decisions, access bank systems
```

**Boundary:** MLO outputs are signals — probabilities and SHAP values.
No action flows from MLO alone. Every action requires MIPLO + ELO.

---

### MIPLO — Monitoring, Intelligence & Processing Operator (Bridgepoint)

**Components:** C3, C4, C5, C6

**Role:** Monitors payment networks, processes signals from MLO,
applies risk controls, and generates loan offers. Orchestrates the
intelligence pipeline. Does not execute — cannot fund loans or
instruct bank systems to move money.

```
C3: Repayment Engine
    Monitors: all 5 settlement signal channels per UETR
    Triggers: repayment instructions to C7 (ELO executes)

C4: Dispute Classifier
    Monitors: SWIFT RmtInf fields for dispute signals
    Generates: hard block signals (ELO enforces)

C5: Streaming Infrastructure
    Routes: all messages between MLO and MIPLO components
    Maintains: payment and loan state machines

C6: AML Velocity Module
    Monitors: cross-entity velocity and anomaly signals
    Generates: hard block signals (ELO enforces)
```

**Boundary:** MIPLO generates offers and block signals. No transaction
is executed without ELO acceptance. MIPLO cannot bypass ELO.

---

### ELO — Execution Lending Operator (Bank)

**Components:** C7

**Role:** The only entity that executes. Receives offers from MIPLO,
applies bank's own risk governance (including human override), funds
loans using the bank's own capital, and writes to the immutable
decision log. All execution occurs within the bank's infrastructure.

```
C7: Embedded Execution Agent
    Receives: loan offers from MIPLO (Decision Engine)
    Executes: loan funding via bank's core banking system
    Enforces: all hard blocks from C4 and C6
    Logs: every decision to immutable audit log (bank-controlled)
    Overrides: bank operator can block any automated decision
```

**Boundary:** ELO has full veto power. No loan is funded without
ELO acceptance. All execution, all capital, all risk sits with
the bank as ELO.

---

### Two-Entity Pilot Mode

For initial deployment, Bridgepoint operates as combined MLO + MIPLO.
Bank operates as ELO. The three-entity architecture is preserved in
system design — the component boundaries and interfaces are identical.
Only the legal/operational structure is simplified for pilot.

```
Pilot:
  Bridgepoint = MLO + MIPLO (C1, C2, C3, C4, C5, C6)
  Bank        = ELO          (C7)

Full deployment:
  Bridgepoint MLO  = C1, C2
  Bridgepoint MIPLO = C3, C4, C5, C6
  Bank ELO         = C7
```

The interface between MIPLO and ELO (Section 4.6 Offer API) is
identical in both modes. No re-integration required to transition
from pilot to full three-entity deployment.

---

## 4. API CONTRACTS

All internal APIs use gRPC for performance-critical paths.
Decision log writes: async append via Kafka (fire-and-forget + retry).
All requests carry UETR as primary correlation key.
All responses carry request_id for idempotency.

---

### 4.1 Ingestion API (SWIFT Gateway --> C5 Kafka)

**Topic:** `lip.payments.raw`
**Schema:** Avro
**Partition key:** UETR (ordering guaranteed per transaction)
**Retention:** 30 days (operational only — see S11.7)
**Exactly-once semantics:** Required (Kafka transactions enabled)

---

### 4.2 Inference API (C5 --> C1)

**Protocol:** gRPC | **Service:** `FailureClassifier`

Request:
```
ClassifyRequest {
  uetr                  : string   // Unique End-to-End Transaction Reference
  rejection_code        : string   // SWIFT rejection code (e.g. AC04, AM04)
  bic_sender            : string   // Sending bank BIC
  bic_receiver          : string   // Receiving bank BIC
  amount_usd            : double   // Normalized amount in USD
  currency_pair         : string   // e.g. "EUR_USD"
  timestamp_utc         : int64    // Unix milliseconds
  hour_of_day           : int32    // 0-23
  day_of_week           : int32    // 0-6
  corridor_embedding    : float[]  // Pre-computed from Redis
                                   // Spec: Phase 1 ARIA deliverable
  individual_payment_id : string   // Explicit individual transaction ref
}
```

Response:
```
ClassifyResponse {
  uetr                  : string
  failure_probability   : float    // 0.0 - 1.0
  threshold_exceeded    : bool     // true if >= operating threshold
  shap_values           : ShapValue[]
  model_version         : string
  inference_latency_ms  : int64
}

ShapValue {
  feature_name          : string
  contribution          : float
}
```

---

### 4.3 PD Model API (C5 --> C2)

**Protocol:** gRPC | **Service:** `PDEstimator`

Request:
```
PDRequest {
  uetr                   : string
  entity_tax_id_hash     : string   // SHA-256(tax_id + salt) — never raw
  entity_type            : string   // "PUBLIC", "PRIVATE", "SME"
  jurisdiction           : string   // ISO 3166-1 alpha-2
  annual_revenue_usd     : double   // 0.0 if unavailable (thin-file path)
  existing_exposure_usd  : double
  requested_amount_usd   : double
  rejection_code_class   : string   // "A", "B", or "C"
  maturity_days          : int32    // 3, 7, or 21
  is_thin_file           : bool     // true activates imputation path
}
```

Response:
```
PDResponse {
  uetr                   : string
  pd_estimate            : float    // 0.0 - 1.0
  lgd_estimate           : float    // Loss given default
  expected_loss_usd      : double   // PD * LGD * EAD
  fee_bps                : float    // ANNUALIZED rate in basis points.
                                    // Per-cycle fee formula:
                                    //   fee = loan_amount
                                    //         * (fee_bps / 10000)
                                    //         * (days_funded / 365)
                                    // Floor: 300 bps annualized
                                    //   = 0.0575% per 7-day cycle.
                                    // DO NOT apply as flat per-cycle rate.
                                    // Applying as flat rate at 300 bps
                                    // yields 3% per cycle — 156x intended.
  shap_values            : ShapValue[]
  thin_file_flag         : bool
  model_version          : string
  inference_latency_ms   : int64
}
```

---

### 4.4 Dispute Classifier API (C5 --> C4)

**Protocol:** gRPC | **Service:** `DisputeClassifier`
**Deployment:** On-device within C7 bank container (zero data export)

Request:
```
DisputeRequest {
  uetr                   : string
  remittance_info        : string   // SWIFT RmtInf raw text
  structured_ref         : string   // Structured reference if available
  creditor_ref           : string   // Creditor reference if available
}
```

Response:
```
DisputeResponse {
  uetr                   : string
  dispute_detected       : bool     // true = hard block
  dispute_confidence     : float    // 0.0 - 1.0
  dispute_category       : string   // "INVOICE_DISPUTE", "QUALITY",
                                    //  "DELIVERY", "FRAUD", "UNKNOWN"
  fast_path_used         : bool
  llm_path_used          : bool
  inference_latency_ms   : int64
}
```

Two-path architecture (full timeout behavior in S11.5):
- Fast path (~3ms): binary pre-classifier, always in critical path
- LLM path (~30-50ms): async for uncertain cases (confidence 0.3-0.7)

---

### 4.5 AML Velocity API (C6)

**Protocol:** gRPC | **Service:** `AMLVelocityChecker`

Request:
```
VelocityRequest {
  uetr                   : string
  entity_id_hash         : string   // SHA-256(tax_id + salt) — never raw
  amount_usd             : double
  beneficiary_id_hash    : string   // SHA-256(beneficiary_id + salt)
  jurisdiction           : string
  timestamp_utc          : int64
}
```

Response:
```
VelocityResponse {
  uetr                   : string
  hard_block             : bool
  block_reason           : string   // "VELOCITY_DOLLAR", "VELOCITY_COUNT",
                                    //  "BENEFICIARY_CONCENTRATION",
                                    //  "SANCTIONS_MATCH", "ANOMALY"
  anomaly_score          : float
  sanctions_match        : bool
  sanctions_list         : string   // "OFAC", "EU", "UN" if matched
  rolling_24h_usd        : int64
  rolling_24h_count      : int32
}
```

---

### 4.6 Decision Engine --> C7 Offer API

**Protocol:** gRPC | **Service:** `ExecutionAgent`

Loan Offer (MIPLO --> ELO):
```
LoanOffer {
  uetr                   : string
  individual_payment_id  : string   // Explicit individual identifier
  loan_amount_usd        : double
  maturity_days          : int32    // 3, 7, or 21
  fee_bps                : float    // Annualized (same as PDResponse)
  pd_estimate            : float
  rejection_code         : string
  rejection_code_class   : string   // "A", "B", or "C"
  pd_shap                : ShapValue[]
  classifier_shap        : ShapValue[]
  offer_expiry_utc       : int64    // Valid for 60 seconds
  corridor               : string   // "EUR_USD_CITI" format
  requires_human_review  : bool
}
```

Execution Confirmation (ELO --> MIPLO):
```
ExecutionConfirmation {
  uetr                   : string
  accepted               : bool
  decline_reason         : string
  loan_reference         : string   // Bank's internal loan ID
  funded_timestamp_utc   : int64
  funded_amount_usd      : double
  elo_operator_id        : string   // Human reviewer if manual review
  human_reviewed         : bool
}
```

---

### 4.7 Settlement Signal API (C3 Repayment Engine)

**Protocol:** gRPC | **Service:** `RepaymentEngine`

Settlement Signal:
```
SettlementSignal {
  uetr                   : string
  signal_source          : string   // "SWIFT_CAMT054", "FEDNOW_PACS002",
                                    //  "RTP_ISO20022", "SEPA_INSTANT",
                                    //  "STATISTICAL_BUFFER"
  settlement_timestamp   : int64
  settled_amount         : double
  settlement_currency    : string
  raw_message_hash       : string   // SHA-256 of original message
  is_buffer_trigger      : bool
  buffer_p95_hours       : float    // P95 value used if buffer
}
```

Response:
```
RepaymentConfirmation {
  uetr                   : string
  repayment_triggered    : bool
  new_loan_state         : string   // "REPAID" or "BUFFER_REPAID"
  repayment_timestamp    : int64
  idempotent_duplicate   : bool
}
```

---

### 4.8 Immutable Decision Log (All Components --> Kafka)

**Topic:** `lip.decisions.log`
**Guarantee:** At-least-once + deduplication on log_entry_id
**Storage:** Append-only, HMAC-SHA256 signed per entry
**Retention:** 7 years (see S11.7)

Log Entry:
```
DecisionLogEntry {
  log_entry_id           : string   // UUID v4
  uetr                   : string
  event_type             : string   // "OFFER_GENERATED", "HARD_BLOCK",
                                    //  "LOAN_FUNDED", "REPAID",
                                    //  "DEFAULTED", "HUMAN_OVERRIDE"
  timestamp_utc          : int64
  amount_usd             : double
  rejection_code         : string
  rejection_code_class   : string
  failure_probability    : float
  pd_estimate            : float
  fee_bps                : float    // Annualized rate (see S4.3)
  maturity_days          : int32
  pd_shap                : ShapValue[]
  classifier_shap        : ShapValue[]
  block_reason           : string
  human_reviewed         : bool
  human_reviewer_id      : string
  settlement_source      : string
  model_version_c1       : string
  model_version_c2       : string
  model_version_c4       : string
  taxonomy_status        : string   // "CLASSIFIED" or "UNCLASSIFIED"
  degraded_mode          : bool     // true if CPU fallback active
  kms_unavailable_gap    : bool     // true if written during KMS recovery
  entry_signature        : string   // HMAC-SHA256 of entry content
}
```

---

## 5. MESSAGE SCHEMA REFERENCE

### 5.1 SWIFT pacs.002 — Payment Status Report

| Field Path                                    | Element            | LIP Use                      |
|-----------------------------------------------|--------------------|------------------------------|
| GrpHdr/MsgId                                  | MessageId          | Deduplication key            |
| OrgnlGrpInfAndSts/OrgnlMsgId                  | OriginalMessageId  | Link to original payment     |
| TxInfAndSts/OrgnlUETR                         | OriginalUETR       | Primary correlation key      |
| TxInfAndSts/TxSts                             | TransactionStatus  | RJCT = rejection trigger     |
| TxInfAndSts/StsRsnInf/Rsn/Cd                  | ReasonCode         | Maps to taxonomy (Section 8) |
| TxInfAndSts/StsRsnInf/AddtlInf                | AdditionalInfo     | Supplementary detail         |
| TxInfAndSts/OrgnlTxRef/Amt/InstdAmt           | InstructedAmount   | Loan sizing input            |
| TxInfAndSts/OrgnlTxRef/RmtInf                 | RemittanceInfo     | C4 dispute classifier input  |
| GrpHdr/CreDtTm                                | CreationDateTime   | Latency calculation          |

Trigger: TxSts = "RJCT"
Non-trigger: TxSts = "PDNG", "ACSP", "ACSC"

### 5.2 SWIFT camt.054 — Debit/Credit Notification

| Field Path                                    | Element            | LIP Use                      |
|-----------------------------------------------|--------------------|------------------------------|
| Ntfctn/Acct/Id/IBAN                           | AccountIBAN        | Beneficiary confirmed        |
| Ntfctn/Ntry/BookgDt                           | BookingDate        | Settlement date              |
| Ntfctn/Ntry/Amt                               | Amount             | Amount verification          |
| Ntfctn/Ntry/NtryDtls/TxDtls/Refs/UETR        | UETR               | Match to funded loan         |
| Ntfctn/Ntry/Sts                               | EntryStatus        | BOOK = confirmed             |

Trigger: Ntry/Sts = "BOOK" + UETR matches funded loan

### 5.3 FedNow pacs.002 — US Domestic Settlement

| Field Path                                    | Element            | LIP Use                      |
|-----------------------------------------------|--------------------|------------------------------|
| TxInfAndSts/OrgnlUETR                         | OriginalUETR       | Direct UETR match            |
| TxInfAndSts/TxSts                             | TransactionStatus  | ACSC = settled               |
| GrpHdr/CreDtTm                                | CreationDateTime   | Settlement timestamp         |

Trigger: TxSts = "ACSC" + UETR matches funded loan
Note: FedNow carries UETR natively — no mapping table required.

### 5.4 SEPA Instant pacs.008 — EU Instant Credit Transfer

| Field Path                                    | Element            | LIP Use                      |
|-----------------------------------------------|--------------------|------------------------------|
| CdtTrfTxInf/PmtId/UETR                       | UETR               | Direct match                 |
| CdtTrfTxInf/AccptncDtTm                       | AcceptanceDateTime | Settlement timestamp         |
| CdtTrfTxInf/Amt/InstdAmt                      | InstructedAmount   | Amount verification          |

Trigger: AccptncDtTm present + UETR matches funded loan

### 5.5 RTP (The Clearing House) — US Real-Time Payments

| Field Path                                    | Element            | LIP Use                      |
|-----------------------------------------------|--------------------|------------------------------|
| CdtTrfTxInf/PmtId/EndToEndId                 | EndToEndId         | Resolved to UETR via S2.4    |
| RTPSpecific/TxSts                             | TransactionStatus  | ACSC = settled               |
| RTPSpecific/SttlmDt                           | SettlementDate     | Settlement timestamp         |

Trigger: TxSts = "ACSC" + EndToEndId resolves to funded loan UETR
Note: RTP does NOT carry UETR. See Section 2.4 for mapping table.

---

## 6. PAYMENT LIFECYCLE STATE MACHINE

```
STATES:
  MONITORING         Payment initiated, UETR registered, watching
  FAILURE_DETECTED   pacs.002 RJCT received, ML inference triggered
  DISPUTE_BLOCKED    Dispute classifier fired, no loan offered
  AML_BLOCKED        AML velocity or sanctions block, no loan offered
  BRIDGE_OFFERED     Loan offer generated, awaiting ELO
  OFFER_DECLINED     ELO rejected or offer expired (60s)
  FUNDED             Loan funded, settlement monitor active
  REPAID             Settlement signal received, loan repaid
  BUFFER_REPAID      Statistical buffer triggered repayment
  DEFAULTED          Buffer expired, no settlement, default declared

VALID TRANSITIONS:
  MONITORING       --> FAILURE_DETECTED   pacs.002 RJCT received
  FAILURE_DETECTED --> DISPUTE_BLOCKED    C4 dispute_detected = true
  FAILURE_DETECTED --> AML_BLOCKED        C6 hard_block = true
  FAILURE_DETECTED --> BRIDGE_OFFERED     No blocks, offer generated
  BRIDGE_OFFERED   --> OFFER_DECLINED     ELO decline OR 60s timeout
  BRIDGE_OFFERED   --> FUNDED             ELO execution confirmed
  FUNDED           --> REPAID             Any of signals 1-4 received
  FUNDED           --> BUFFER_REPAID      Signal 5 (buffer) triggered
  FUNDED           --> DEFAULTED          Buffer window expired

FORBIDDEN TRANSITIONS (raise error + alert):
  REPAID           --> Any               Terminal — immutable
  DEFAULTED        --> Any               Terminal — immutable
  DISPUTE_BLOCKED  --> BRIDGE_OFFERED    Cannot unblock without human
  AML_BLOCKED      --> BRIDGE_OFFERED    Cannot unblock without human
  MONITORING       --> FUNDED            Must pass through OFFERED
```

State persistence: Redis | Audit: Kafka `lip.state.transitions`
Idempotency: Terminal state trigger = silently dropped + logged

---

## 7. LOAN LIFECYCLE STATE MACHINE

```
STATES:
  OFFER_PENDING      Offer generated, awaiting ELO (60s window)
  OFFER_EXPIRED      ELO did not respond within 60 seconds
  OFFER_DECLINED     ELO explicitly declined
  ACTIVE             Loan funded, repayment monitoring active
  REPAYMENT_PENDING  Settlement signal received, processing
  REPAID             Repayment confirmed, loan closed
  BUFFER_REPAID      Repaid via statistical buffer
  DEFAULTED          Maturity window expired, no settlement
  UNDER_REVIEW       Human reviewer escalation active

VALID TRANSITIONS:
  OFFER_PENDING    --> OFFER_EXPIRED       60 second timeout
  OFFER_PENDING    --> OFFER_DECLINED      ELO explicit decline
  OFFER_PENDING    --> UNDER_REVIEW        requires_human_review = true
  OFFER_PENDING    --> ACTIVE              ELO execution confirmed
  UNDER_REVIEW     --> ACTIVE              Human reviewer approves
  UNDER_REVIEW     --> OFFER_DECLINED      Human reviewer declines
  ACTIVE           --> REPAYMENT_PENDING   Settlement signal received
  REPAYMENT_PENDING --> REPAID             Signals 1-4 processed
  REPAYMENT_PENDING --> BUFFER_REPAID      Buffer repayment processed
  ACTIVE           --> DEFAULTED           Maturity window expired

MATURITY WINDOWS — T = f(rejection_code_class):
  Class A: 3 calendar days
  Class B: 7 calendar days
  Class C: 21 calendar days

FEE CALCULATION:
  fee = loan_amount * (fee_bps / 10000) * (days_funded / 365)
  Floor: 300 bps annualized = 0.0575% per 7-day cycle
  Early repayment: actual days_funded used, not maturity days
```

---

## 8. REJECTION CODE TAXONOMY

T = f(rejection_code_class): the explicit feature distinguishing
LIP from static prior art (JPMorgan US7089207B1).

### Class A — Temporary Liquidity (Maturity: 3 days)

| Code  | Description                       | Rationale                     |
|-------|-----------------------------------|-------------------------------|
| AM04  | Insufficient funds                | Temporary cash shortfall      |
| AM14  | Amount exceeds agreed maximum     | Limit breach, short resolve   |
| AM09  | Wrong amount                      | Correction typically fast     |
| FOCR  | Following cancellation request    | Operational, short resolution |
| MS03  | Not specified (miscellaneous)     | Default shortest window       |
| LEGL  | Legal decision (temp injunction)  | Short-term legal hold         |

### Class B — Compliance Verification Hold (Maturity: 7 days)

| Code  | Description                       | Rationale                     |
|-------|-----------------------------------|-------------------------------|
| AC01  | Incorrect account number          | KYC/account verification      |
| AC04  | Closed account                    | Account migration process     |
| AC06  | Blocked account                   | Compliance review <7 days     |
| AG01  | Transaction forbidden             | Regulatory clearance          |
| AG02  | Invalid transaction code          | Bank compliance query         |
| MD01  | No mandate                        | Mandate verification          |
| MD06  | Returned by customer              | Resolution window needed      |
| RR01  | Regulatory reporting missing      | Submission <7 days            |
| RR02  | Regulatory reporting incomplete   | Amendment submission          |
| RR03  | Regulatory reporting not current  | Update submission             |
| RR04  | Regulatory reporting reason       | Generic regulatory hold       |
| FF01  | Invalid file format               | Technical correction needed   |

### Class C — Structural Routing Failure (Maturity: 21 days)

| Code  | Description                       | Rationale                     |
|-------|-----------------------------------|-------------------------------|
| RC01  | Bank identifier incorrect         | BIC error, manual correction  |
| BE01  | Inconsistent with end customer    | Identity verification         |
| BE04  | Missing creditor address          | Address resolution            |
| BE05  | Unrecognised initiating party     | Onboarding verification       |
| BE06  | Unknown end customer              | KYC from scratch              |
| BE08  | Invalid date                      | Correction + resubmission     |
| CNOR  | Creditor bank not registered      | Correspondent setup needed    |
| DNOR  | Debtor bank not registered        | Correspondent setup needed    |
| NARR  | Narrative (structural)            | Complex resolution            |
| NOAS  | No answer from customer           | Extended resolution window    |

### Hard Block — No Bridge Offered

| Code  | Description                       | Action                        |
|-------|-----------------------------------|-------------------------------|
| FRAUD | Fraud suspicion                   | HARD BLOCK                    |
| AC07  | Closed debtor account             | HARD BLOCK                    |
| SL01  | Sanction list (specific)          | HARD BLOCK — route to CIPHER  |
| SL11  | Creditor on sanctions list        | HARD BLOCK — route to CIPHER  |
| SL12  | Debtor on sanctions list          | HARD BLOCK — route to CIPHER  |
| SL13  | Involved party on sanctions list  | HARD BLOCK — route to CIPHER  |

### Unknown Codes
Default: Class B (7 days). Logged: taxonomy_status = "UNCLASSIFIED"
Quarterly review process: Section 11.6.

---

## 9. DATA BOUNDARIES & ENCRYPTION STANDARDS

### 9.1 Data Boundary Map

```
EXTERNAL (SWIFT Network / Bank Systems)
|
|  [C5 Kafka Ingestion] — ISO 20022 messages enter here
|  In transit: TLS 1.3
|
INTERNAL (MLO + MIPLO Processing Layer — Bridgepoint)
|
|  C1 (MLO): UETR, BIC-pair, rejection_code, amount, embeddings
|             Never sees: borrower identity, tax ID, account numbers
|
|  C2 (MLO): entity_id_hash (SHA-256), entity_type, financials
|             Never sees: raw tax ID, personal data
|
|  C3 (MIPLO): UETR, settlement signals (parsed fields only)
|               Never sees: borrower identity, financial details
|
|  C4 (MIPLO): RmtInf text, structured_ref (bank container only)
|               Zero network calls — on-device inference only
|               Never exports RmtInf outside bank container
|
|  C5 (MIPLO): Routes messages; Kafka + Redis encrypted at rest
|               Raw messages: 30-day retention only
|
|  C6 (MIPLO): entity_id_hash, amount, beneficiary_hash, timestamp
|               Velocity counters: SHA-256 keyed, 24h TTL in Redis
|               Cross-licensee: only hashes shared, never raw IDs
|
BANK INFRASTRUCTURE (ELO)
|
|  C7 (ELO): Bank-side only
|             Zero outbound calls to Bridgepoint systems
|             Bank controls all data residency
|             Decision log: bank-owned, bank-encrypted
```

### 9.2 Encryption Standards

| Location                    | Standard       | Key Management                   |
|-----------------------------|----------------|----------------------------------|
| Data in transit             | TLS 1.3        | Certificate rotation: 90 days    |
| Kafka at rest (C5, C7)      | AES-256-GCM    | Bank-managed KMS (see S11.8)     |
| Redis at rest (C5, C7)      | AES-256-GCM    | Bank-managed KMS (see S11.8)     |
| Decision log                | AES-256-GCM    | Bank-managed KMS (see S11.8)     |
| HMAC log signatures         | HMAC-SHA256    | Bank HSM-backed signing key      |
| Borrower ID hashing         | SHA-256 + salt | 256-bit salt, annual rotation    |
| Cross-licensee hashes       | SHA-256 + salt | Per-licensee salt, never shared  |
| C6 cross-licensee DEKs      | AES-256        | Envelope-encrypted (see S11.8)   |

### 9.3 Data Residency

- Borrower personal data: never leaves bank infrastructure
- SWIFT message content: 30-day Kafka retention only
- Model weights (C1, C2): Bridgepoint-managed, deployed read-only
- Model weights (C4): bank container copy, bank controls
- Decision logs: bank-owned; Bridgepoint access via export API only
- Cross-licensee velocity: only SHA-256 hashes transit Bridgepoint

---

## 10. LATENCY BUDGET & CRITICAL PATH ANALYSIS

### 10.1 Component Latency Targets

| Component | Operation                     | p50    | p99    | Notes                     |
|-----------|-------------------------------|--------|--------|---------------------------|
| C5        | Kafka ingestion + deserialize | 2ms    | 5ms    |                           |
| C5        | Feature extraction            | 1ms    | 3ms    |                           |
| C5        | Redis corridor lookup         | 1ms    | 2ms    |                           |
| C1        | GNN + TabTransformer (GPU)    | 20ms   | 40ms   | GPU required — see S11.1  |
| C1        | GNN + TabTransformer (CPU)    | 80ms   | 150ms  | Degraded mode ONLY        |
| C2        | LightGBM PD inference         | 3ms    | 8ms    |                           |
| C4        | Fast-path binary classifier   | 3ms    | 8ms    | Critical path             |
| C4        | LLM path (quantized 4-bit)    | 30ms   | 60ms   | Async only — see S11.5    |
| C6        | AML velocity (Redis)          | 2ms    | 4ms    |                           |
| C6        | Sanctions screening           | 2ms    | 5ms    | In-memory list            |
| Decision  | Aggregate + offer generation  | 1ms    | 2ms    |                           |
| C7        | Route to execution agent      | 1ms    | 3ms    |                           |

### 10.2 Critical Path Summary

| Mode            | p50    | p99    | Status                         |
|-----------------|--------|--------|--------------------------------|
| GPU (production)| ~26ms  | ~51ms  | Within SLA with margin         |
| CPU (degraded)  | ~86ms  | ~163ms | Within SLA — no headroom       |

GPU production deployment is required. See S11.1.

---

## 11. RESOLVED DESIGN DECISIONS

All 8 design decisions locked. None reopen without explicit documented
rationale and full agent re-review.

### 11.1 GPU vs CPU Inference (FORGE + ARIA)

GPU required in production for C1.
Hardware: NVIDIA T4 (minimum) or A10G (preferred).
CPU = degraded mode only, never primary.

Throughput at 10K TPS (batch 32, wait 5ms):
  1,600 TPS per GPU node → 9 nodes for 10K TPS (with headroom)
  40 nodes for 50K TPS peak (autoscaled)

Autoscaling: Kubernetes HPA on inference queue depth
  Scale-out: >100 pending / node | Scale-in: <20 / node for 5 min
  Min: 2 nodes (HA) | Max: 50 nodes (50K TPS peak)

Model serving: NVIDIA Triton Inference Server
  Dynamic batching: max 32, wait 5ms
  Health check: inference p99 latency

Degraded mode (CPU): system continues, logs degraded_mode = true,
auto-recovers on GPU restoration without manual intervention.

Graph size monitoring: if BIC-pair graph exceeds ~500 nodes,
T4 inference time may double. Monitor quarterly; A10G upgrade path
pre-planned at >500 nodes.

### 11.2 RTP UETR Mapping Table (NOVA)

Redis HASH populated at outbound pacs.008 event.

Schema:
  Key:    "rtp:e2e:{EndToEndId}"
  Type:   Redis HASH
  TTL:    maturity_days + 45 days (max 66 days)
  Fields: uetr, corridor, amount_usd, created_at, rail

Population trigger: Kafka `lip.payments.outbound` (pacs.008)
  Must be populated BEFORE payment enters MONITORING state.
  Sequencing: Kafka partition key = UETR enforces ordering.

Alert: if RTP settlement arrives with no UETR mapping, escalate.
FedNow: UETR native — no mapping table needed.

### 11.3 Salt Rotation Protocol (CIPHER)

Annual rotation. 30-day dual-salt migration window.
Emergency rotation: 24-hour accelerated protocol.

Protocol:
  Phase 1 (Days 1-7): Generate S_new; compute dual hashes H_old + H_new
  Phase 2 (Days 8-37): Dual-hash lookups; sum both velocity counters
  Phase 3 (Day 38): Retire S_old; H_old TTL = 24h flush; S_new = current

Storage: HSM-backed (AWS CloudHSM or equivalent)
Per-licensee salts isolated. Cross-licensee uses separate salt.
Rotation dates never published or predictable.

### 11.4 Corridor Buffer Bootstrap (NOVA + ARIA)

Four-tier model:

Tier 0 (Days 0-7): Conservative class × currency defaults:
  Class A: 48hr major / 72hr emerging
  Class B: 10d major / 14d emerging
  Class C: 25d major / 30d emerging

Tier 1 (Days 8-30):   70% global P95 + 30% corridor-specific
Tier 2 (Days 31-89):  30% global P95 + 70% corridor-specific
Tier 3 (Days 90+):    Pure corridor-specific P95, rolling 90-day

Early graduation: 200+ observations → Tier 3 regardless of age.
Alert: corridor P95 deviates >50% from global P95 → ARIA review.

Redis schema per corridor:
  Key:    "corridor:buffer:{bic_sender}_{bic_receiver}_{class}"
  Fields: tier, sample_count, created_at, current_p95_hrs, last_updated

### 11.5 LLM Async Path Timeout (ARIA)

Case 1 (fast-path confident NO_DISPUTE >0.7): PROCEED. LLM timeout logged.
Case 2 (fast-path confident DISPUTE >0.7): Already blocked. Irrelevant.
Case 3 (fast-path uncertain 0.3-0.7, LLM timed out):

  200ms: extend hold to 500ms
  500ms hard limit:
    amount <= $50K:           PROCEED
    $50K < amount <= $500K:   HOLD for human ELO review (30 min max)
                               If no response: BLOCK
    amount > $500K:           HARD BLOCK

Thresholds are configurable defaults. Bank licensees adjust via ELO admin.
LLM timeout alert: if >1% of LLM-path inferences timeout in 1hr, FORGE
auto-scales inference nodes, ARIA alerted.
Threshold calibration: Phase 5 ARIA deliverable (post-integration data).

### 11.6 Unknown Rejection Codes — Class B Default (NOVA + LEX)

Class B (7 days) confirmed as default for unknown codes.
Logged: taxonomy_status = "UNCLASSIFIED"

Quarterly Review:
  Step 1 — ARIA: pull unclassified entries, calculate observed P95
  Step 2 — NOVA: classify by P95 (<=4d→A, 4-10d→B, >10d→C, no settle→BLOCK)
  Step 3 — LEX: review before deployment; document as "learned mapping
    from observed settlement telemetry" (strengthens T = f(rejection_code_class))
  Step 4 — Deploy: versioned config update, 90-day rollback retained

NOVA monitors SWIFT release notes; new codes added to UNCLASSIFIED
immediately on publication.

### 11.7 Decision Log Retention (REX)

7 years confirmed. Satisfies all applicable jurisdictions.

| Framework      | Jurisdiction | Requirement          |
|----------------|--------------|----------------------|
| BSA/AML        | US           | 5 years              |
| SOX            | US           | 7 years              |
| SR 11-7        | US           | Duration + 3 years   |
| FINTRAC        | Canada       | 5 years              |
| DORA Art.30    | EU           | Contract + 3yr min   |
| MiFID II       | EU           | 5 years              |
| MAS TRM        | Singapore    | 5 years              |

GDPR: decision log contains no personal data (SHA-256 hashes,
UETRs, SHAP values, transactional metadata only).
Flag: EU data protection counsel to confirm hash non-personal-data
classification before EU bank deployment.

Tiered retention:
  Decision log entries, AML records, model snapshots,
  corridor calibration, human override records: 7 years
  Raw SWIFT messages (Kafka): 30 days

### 11.8 Kafka Encryption Key Ownership (REX + FORGE)

Model A — Bank-deployed (C5 Kafka, C5 Redis, C7):
  Bank manages KMS entirely. Bridgepoint has zero decryption access.
  Decision log: bank-controlled signed export API only.

Model B — Bridgepoint-operated C6 cross-licensee service:
  Envelope encryption: Bridgepoint holds DEKs wrapped by bank KEKs.
  Bank offboarding: KEK revoked = DEK permanently inaccessible
  (cryptographic deletion, no physical deletion required).

Key Rotation:
  Bank KMS keys (C5, C7): bank policy | Cross-licensee DEKs: annual
  Cross-licensee KEKs: bank policy | HMAC signing keys: annual
  TLS certificates: 90 days | SHA-256 salts: annual (see S11.3)

FORGE: keys injected via Kubernetes External Secrets Operator
with bank vault backend. Never in container images or K8s secrets.

---

## 12. PHASE 0 SIGN-OFF GATE

### Current Status

| Agent  | v1.1 Status | v1.2 Re-review Needed | v1.2 Status |
|--------|-------------|-----------------------|-------------|
| ARIA   | SIGNED*     | No                    | CARRIED     |
| NOVA   | SIGNED*     | No                    | CARRIED     |
| REX    | SIGNED*     | No                    | CARRIED     |
| FORGE  | SIGNED*     | No                    | CARRIED     |
| LEX    | HOLD        | Yes — review S3A      | PENDING     |
| CIPHER | HOLD        | Yes — review S2.5     | PENDING     |
| QUANT  | HOLD        | Yes — review S4.3     | PENDING     |

### What LEX, CIPHER, and QUANT are reviewing in v1.2

LEX: Section 3A — Three-Entity Role Architecture
  Confirm: MLO/MIPLO/ELO mapped correctly to C1-C7
  Confirm: Two-entity pilot mode preserves three-entity design intent
  Confirm: "individual" + "UETR" still explicit throughout (unchanged)

CIPHER: Section 2.5 — Kill Switch & KMS Unavailability Behavior
  Confirm: KMS unavailability is fail-safe (no fail-open)
  Confirm: Funded loan states preserved under KMS failure
  Confirm: Auto-recovery without manual intervention
  Confirm: kms_unavailable_gap flag in decision log (S4.8)

QUANT: Section 4.3 — PDResponse fee_bps annotation
  Confirm: fee_bps explicitly annotated as annualized rate
  Confirm: Per-cycle formula documented in API contract
  Confirm: 156x flat-rate error possibility explicitly warned
  Confirm: Canonical numbers unchanged throughout

### Gate Clears When

All 7 sign-offs recorded (4 carried + 3 new confirmations).
Zero open design questions.
No immutable standard violations (LEX confirms — per review scope).

### Items for Future External Confirmation
(Internal flags — stealth mode active, no external action)

1. REX: GDPR SHA-256 hash non-personal-data classification
   requires EU data protection counsel confirmation
2. REX: SR 11-7 "duration of use + 3 years" interpretation
   confirm against Federal Reserve examination guidance
3. ARIA: LLM timeout thresholds ($50K/$500K) recalibrate
   against actual dispute data post-pilot (Phase 5 deliverable)

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
*Status: Content complete — LEX, CIPHER, QUANT re-review pending*
