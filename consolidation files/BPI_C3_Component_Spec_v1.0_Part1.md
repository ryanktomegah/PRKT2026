# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 3 — DUAL-SIGNAL REPAYMENT ENGINE
## Build Specification v1.0 — Part 1 of 2
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** NOVA — Payments Infrastructure Engineering
**Support:** LEX (claim language: "individual" + "UETR", T = f(rejection_code_class)),
             FORGE (Flink/Kafka/Redis integration),
             REX (DORA Art.30 audit trail, EU AI Act Art.17),
             CIPHER (idempotency adversarial testing)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS — PART 1

1.  Purpose & Scope
2.  Why C3 Is the Infrastructure Backbone
3.  Architecture Overview
4.  Function 1: Failure Detection & Rejection Code Classification
    4.1 pacs.002 Parser
    4.2 Rejection Code Taxonomy — Full Table (A / B / C / UNKNOWN)
    4.3 T = f(rejection_code_class) — Maturity Assignment
    4.4 Maturity Timer Registration
5.  Function 2: Settlement Signal Processing
    5.1 Signal Channel 1 — SWIFT camt.054
    5.2 Signal Channel 2 — FedNow pacs.002 (ACSC)
    5.3 Signal Channel 3 — RTP ISO 20022
    5.4 Signal Channel 4 — SEPA Instant pacs.008
    5.5 Signal Channel 5 — Statistical Buffer Fallback
6.  RTP UETR Mapping Sub-Service
    6.1 Design & Redis Schema
    6.2 Missing Mapping Fallback
    6.3 Sequencing Race Condition (NOVA flag — addressed)
7.  Corridor Buffer Design
    7.1 P95 Formula & Rolling Window
    7.2 4-Tier Bootstrap Protocol
    7.3 Buffer vs. Maturity Window Relationship (guard required)
8.  Idempotency Design
    8.1 Redis Deduplication Layer
    8.2 Flink Exactly-Once Semantics
    8.3 Duplicate Signal Handling
9.  State Machine Implementation
    9.1 Payment Lifecycle — C3 Transitions
    9.2 Loan Lifecycle — C3 Transitions
    9.3 Timer Management (Processing-Time)
    9.4 Terminal State Guarantees

> Part 2 covers: Sections 10–18 (Repayment Instruction Flow, Flink Topology,
> Error Handling, IP Alignment, Integration Requirements, Monitoring,
> Known Limitations, Validation Requirements, Audit Gate 2.1 Checklist)

---

## 1. PURPOSE & SCOPE

C3 is the payment lifecycle intelligence engine. It owns two tightly coupled functions:

**Function 1 — Failure Detection & Classification:**
Parse every SWIFT pacs.002 RJCT event, classify the rejection code into taxonomy Class A,
B, or C, and compute the maturity window T = f(rejection_code_class). This classification
feeds directly into the LoanOffer maturity_days field (Architecture Spec S4.6) and into
C2's PDRequest rejection_code_class field (S4.3). Without C3's classification, no offer
can be correctly priced.

**Function 2 — Repayment Engine:**
Once a loan is funded (ELO execution confirmed by C7), monitor all five settlement signal
channels per individual UETR-keyed loan. Trigger repayment on the first valid settlement
signal received from any channel. Trigger DEFAULTED state on maturity expiry with no prior
settlement signal.

C3 is the only component in the system that operates on multi-day state. C1, C2, C4, and
C6 all complete their work in milliseconds and discard per-event state immediately. C3
maintains live monitoring state per funded individual UETR for up to 21 calendar days.
This makes C3 the most stateful component in the system and the most complex to operate
correctly under failure conditions.

**C3 scope:**
- Parse and classify all SWIFT pacs.002 RJCT events in real-time
- Full rejection code taxonomy (Class A / B / C / UNKNOWN), with quarterly review process
- T = f(rejection_code_class) maturity assignment as explicit first-class feature
- Settlement signal handlers for all 5 channels
- RTP UETR mapping sub-service (EndToEndId → UETR resolution)
- Corridor-specific statistical buffer (P95, rolling 90-day window, 4-tier bootstrap)
- Idempotent repayment triggering — exactly-once semantics enforced
- Maturity expiry and default declaration
- Repayment instructions to C7 via Kafka
- Full state audit log on `lip.state.transitions`

**C3 does NOT:**
- Score payment failure probability (C1)
- Estimate credit risk or compute fees (C2)
- Screen for commercial disputes (C4)
- Perform AML velocity checks (C6)
- Execute loan funding or repayment transactions (C7 — ELO only)
- Make the decision to offer a bridge loan (Decision Engine)

---

## 2. WHY C3 IS THE INFRASTRUCTURE BACKBONE

Every other component in the system operates on the critical path (<100ms). C3 is
explicitly NOT on the critical path for offer generation — it operates asynchronously.
But it is on the critical path for *everything that happens after a loan is funded*.

The failure mode that destroys capital is not a bad ML model. A bad ML model makes offers
it shouldn't. C3's failure mode is worse: a funded loan that is never repaid because the
settlement signal was missed, mismatched, or silently dropped. That is a direct capital loss.

Three design decisions in C3's architecture follow from this:

**Decision 1 — No assumed universal camt.054.**
camt.054 availability varies by SWIFT member configuration and corridor. Building C3 around
camt.054 as the sole settlement confirmation would mean that for any corridor where camt.054
is not configured, funded loans would default even if the underlying payment settled. The
5-channel design ensures that at least one settlement confirmation path exists for every
commercially active corridor.

**Decision 2 — Deterministic state machine with no undefined transitions.**
Every input to C3 — including malformed inputs, duplicate signals, and signals for UETRs
already in terminal state — has an explicitly defined handler. "Undefined behavior" in a
financial state machine is not an engineering failure; it is a capital risk.

**Decision 3 — Idempotency as a first-class constraint, not an afterthought.**
When a payment settles, multiple rails can simultaneously send confirmation signals.
camt.054 and SEPA Instant pacs.008 can both fire for the same underlying payment within
seconds of each other. The idempotency design must ensure that exactly one repayment
instruction is generated per funded individual UETR, regardless of how many channels
confirm settlement.

---

## 3. ARCHITECTURE OVERVIEW

C3 runs as two coordinated Flink streaming jobs sharing a Redis state store:

```
Job A: Failure Classifier (Function 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kafka: lip.payments.raw (pacs.002 events)
    |
    v
[pacs.002 Parser]
    | Extract: UETR, rejection_code, BIC_pair,
    |          amount_usd, timestamp_utc
    v
[Rejection Code Classifier]
    | T = f(rejection_code_class)
    | Class A → maturity_days = 3
    | Class B → maturity_days = 7
    | Class C → maturity_days = 21
    | UNKNOWN → maturity_days = 21 (+ quarterly review flag)
    v
Publish: lip.payments.classified (UETR + class + maturity_days)
    → consumed by Decision Engine → feeds LoanOffer
    → consumed by C2 → feeds PDRequest.rejection_code_class
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Job B: Repayment Engine (Function 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kafka: lip.loans.funded       → activate monitoring per UETR
Kafka: lip.settlement.camt054 → Channel 1
Kafka: lip.settlement.fednow  → Channel 2
Kafka: lip.settlement.rtp     → Channel 3
Kafka: lip.settlement.sepa    → Channel 4
Kafka: lip.payments.outbound  → RTP UETR mapping sub-service
    |
    v
[Multi-Source Union Stream]  ← Flink union() of all 5 channels
    |
    | Keyed by UETR (all channels)
    v
[Settlement Signal Router]
    | Per UETR check: is loan in ACTIVE state?
    | If YES: validate signal → idempotency check → repay
    | If NO (terminal): silently drop + log
    v
[Buffer Timer / Maturity Timer]
    | Processing-time timers (wall-clock, not event-time)
    | Buffer timer: P95 corridor threshold → BUFFER_REPAID
    | Maturity timer: maturity_days wall-clock → DEFAULTED
    v
Output:
    lip.repayment.instructions  (→ C7 executes repayment)
    lip.decisions.log           (→ audit record)
    lip.state.transitions       (→ state machine audit)
    lip.alerts                  (→ operational alerting)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sub-Service: RTP UETR Mapper
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kafka: lip.payments.outbound  → outbound pacs.008 events
    |
    v
Extract: EndToEndId, UETR, corridor, amount_usd, maturity_days
    |
    v
Redis HASH: "rtp:e2e:{EndToEndId}"
    TTL: maturity_days + 45 days (max 66 days)
    Partition guarantee: UETR (ordered before failure event possible)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 4. FUNCTION 1: FAILURE DETECTION & REJECTION CODE CLASSIFICATION

### 4.1 pacs.002 Parser

Input: raw ISO 20022 pacs.002 message from Kafka topic `lip.payments.raw`

Trigger condition: `TxInfAndSts/TxSts = "RJCT"`
Non-trigger: `TxSts = "PDNG"`, `"ACSP"`, `"ACSC"`

Fields extracted:

```
ParsedFailureEvent {
  individual_payment_id   : string  // TxInfAndSts/OrgnlUETR — explicit individual identifier
  uetr                    : string  // TxInfAndSts/OrgnlUETR — canonical name
  rejection_code          : string  // TxInfAndSts/StsRsnInf/Rsn/Cd
  rejection_additional    : string  // TxInfAndSts/StsRsnInf/AddtlInf (may be empty)
  bic_sender              : string  // GrpHdr/InstgAgt/FinInstnId/BICFI
  bic_receiver            : string  // GrpHdr/InstdAgt/FinInstnId/BICFI
  amount_usd              : double  // TxInfAndSts/OrgnlTxRef/Amt/InstdAmt (USD normalized)
  currency_original       : string  // original currency before normalization
  message_id              : string  // GrpHdr/MsgId (deduplication key)
  creation_timestamp_utc  : int64   // GrpHdr/CreDtTm (milliseconds)
  remittance_info         : string  // TxInfAndSts/OrgnlTxRef/RmtInf (→ forwarded to C4)
}
```

**Parser validation rules:**
- If `rejection_code` absent or empty: set `rejection_code = "UNKNOWN"`, proceed as Class C
- If `individual_payment_id` (OrgnlUETR) absent: discard to `lip.dlq.parse_error` + alert — UETR is mandatory
- If `amount_usd` cannot be normalized: use 0.0, set `amount_normalization_failed = true` + alert
- Duplicate `message_id` within 24h window: silently drop + log (SWIFT may redeliver)

### 4.2 Rejection Code Taxonomy — Full Table

This table is the authoritative mapping of SWIFT ISO 20022 external status reason codes to
LIP maturity classes. It directly implements the T = f(rejection_code_class) patent claim
element. It is a first-class system feature, not a configuration table.

**Classification rationale:**
- **Class A (3 days):** Permanent structural failures with known fast-resolution paths. The payment will not settle via the original instruction.
- **Class B (7 days):** Operational, liquidity, or system-level failures where the payment may resume via retry or alternative routing. Moderate uncertainty.
- **Class C (21 days):** Customer-initiated returns, fraud investigations, regulatory holds, or legal decisions. Resolution timeline inherently uncertain.
- **UNKNOWN:** Any code not in this table. Defaults to Class C. Flagged for quarterly review.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASS A — maturity_days = 3
Permanent structural / routing / identity failures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Code   Description                           Rationale
AC01   IncorrectAccountNumber                Account structure error — permanent
AC04   ClosedAccountNumber                   Account closed — permanent
AC06   BlockedAccount                        Debtor-side block — effectively permanent
AC13   InvalidDebtorAccountType              Account type mismatch — structural
AG01   TransactionForbidden                  Routing prohibition — not overridable
AG02   InvalidBankOperationCode              Operational code error — format
BE04   MissingCreditorAddress                Structural — required field absent
BE05   UnrecognisedInitiatingParty           Identity failure — not resolvable via retry
BE06   UnknownEndCustomer                    Identity failure
BE07   MissingDebtorAddress                  Structural
BE08   InvalidBankDetails                    Routing failure
CNOR   CreditorBankNotRegistered             BIC not in SWIFT directory — permanent
DNOR   DebtorBankNotRegistered               BIC not in SWIFT directory — permanent
FF01   InvalidFileFormat                     Message format error — permanent for this msg
FF05   InvalidLocalInstrumentCode            Instrument code invalid — format
RC01   BankIdentifierIncorrect               BIC incorrect — routing failure
PY01   UnknownBICInDirectory                 BIC not found — routing failure
RR01   MissingDebtorAcctOrId                 Required field absent — structural
RR02   MissingDebtorNameOrAddress            Required field absent — structural
RR03   MissingCreditorNameOrAddress          Required field absent — structural

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASS B — maturity_days = 7
Operational / liquidity / system-level failures with moderate uncertainty
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Code   Description                           Rationale
AM04   InsufficientFunds                     Liquidity failure — may resolve with retry
AM07   BlockedAmount                         Temporary operational hold
ED05   SettlementFailed                      Settlement system failure — retry path exists
SVNR   ServicerNotAvailable                  Temporary system unavailability
TM01   InvalidCutOffTime                     Cut-off missed — retry next window
DT01   InvalidDate                           Date processing error — operational
CH03   ExecutionDateTooFarInFuture           Scheduling constraint — operational
MD01   NoMandate                             Mandate system failure — operational resolution
MD02   MissingMandatoryInfoInMandate         Mandate data incomplete — correctable
SL01   SpecificServiceByDebtorAgent          Service limitation — corridor-specific
SL11   CreditorAcctCurrencyNotAllowed        Currency constraint for corridor
SL12   CreditorCountryNotAllowed             Country restriction — corridor constraint
SL13   CurrenciesNotCoveredBySystem          Currency pair not supported

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASS C — maturity_days = 21
Customer-initiated / regulatory / fraud / legal / high uncertainty
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Code   Description                           Rationale
CUST   RequestedByCustomer                   Customer dispute — open-ended
FOCR   FollowingCancellationRequest          Cancellation in progress
FR01   Fraud                                 Fraud investigation — also triggers C4
LEGL   LegalDecision                         Legal hold — cannot predict timeline
MD06   ReturnedReasonByEndCustomer           Customer dispute — inherently uncertain
MD07   EndCustomerDeceased                   Estate/legal processing — long timeline
MS02   NotSpecifiedReasonCustomerGenerated   Unknown customer reason
MS03   NotSpecifiedReasonAgentGenerated      Unknown agent reason
NARR   Narrative                             Unstructured reason — cannot classify
NOAS   NoAnswerFromCustomer                  Customer investigation ongoing
RR04   RegulatoryReason                      Compliance review — unpredictable timeline
SL14   OtherBilateral                        Bilateral agreement — complex resolution
ERIN   ERInformationReason                   Investigation pending
NOOR   NoOriginalTransactionReceived         Reconciliation issue — investigation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UNKNOWN — Default Class C (maturity_days = 21)
All codes not in the above table
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- taxonomy_status = "UNCLASSIFIED"; maturity_days = 21 (conservative default)
- Flagged for quarterly review — ARIA pulls UNKNOWN events, analyzes settlement
  outcomes, proposes reclassification (Architecture Spec S11.6)
- FR01 note: Class C for maturity purposes AND independently triggers C4.
  These are orthogonal signals — C3 sets the maturity window; C4 determines
  whether to hard block the offer entirely.
```

**Taxonomy total: 47 classified codes + UNKNOWN catch-all.**

### 4.3 T = f(rejection_code_class) — Maturity Assignment

The maturity window is a deterministic function of the rejection code class. This is not a
heuristic or a default. It is an explicit first-class feature — the primary distinction from
JPMorgan US7089207B1, which uses static term assignment independent of rejection taxonomy.

```
MATURITY ASSIGNMENT FUNCTION

Input:  rejection_code_class ∈ {A, B, C, UNKNOWN}
Output: maturity_days ∈ {3, 7, 21}

T = f(rejection_code_class):
  Class A   → maturity_days = 3
  Class B   → maturity_days = 7
  Class C   → maturity_days = 21
  UNKNOWN   → maturity_days = 21 (conservative default)

Properties:
  Deterministic  : same input always produces same output
  Exhaustive     : every possible rejection code has a defined output
  Immutable      : maturity_days set at classification time; never changes
                   for the lifetime of that individual UETR-keyed loan
  Logged         : rejection_code_class AND maturity_days both written to
                   DecisionLogEntry (Architecture Spec S4.8)
```

maturity_days flows into:
- `lip.payments.classified` → Decision Engine → LoanOffer
- `PDRequest.maturity_days` → C2
- `LoanOffer.maturity_days` → C7
- `DecisionLogEntry.maturity_days` → 7-year audit log

### 4.4 Maturity Timer Registration

On receiving an ExecutionConfirmation from C7 (via `lip.loans.funded`), C3 stores loan
state and registers two processing-time timers in Flink keyed state:

```
On LOAN_FUNDED event for individual UETR:

  Store in Flink keyed state (keyed by UETR):
    funded_timestamp_utc  : int64   // wall-clock at funding
    maturity_days         : int32   // from rejection_code_class
    loan_amount_usd       : double  // from ExecutionConfirmation
    corridor              : string  // BIC_sender + BIC_receiver + currency
    fee_bps               : float   // annualized (from original LoanOffer)
    loan_reference        : string  // bank's internal loan ID
    rejection_class       : string  // A / B / C / UNKNOWN
    model_version_c1/c2/c4: string  // for audit trail continuity

  Register Timer 1 — Buffer Timer:
    fire_at = funded_timestamp_utc + buffer_trigger_hours * 3,600,000
    type    = PROCESSING_TIME (wall-clock)
    guard   : fire_at MUST be < (funded_utc + (maturity_days - 1) * 86,400,000)
              If P95 >= maturity_days * 24h:
                cap buffer to (maturity_days * 24h - 24h)
              This ensures buffer ALWAYS fires before maturity expiry.

  Register Timer 2 — Maturity Timer:
    fire_at = funded_timestamp_utc + maturity_days * 86,400,000
    type    = PROCESSING_TIME (wall-clock)
    guard   : only acts if loan is still in ACTIVE state
              (cancelled immediately on any terminal state transition)
```

---

## 5. FUNCTION 2: SETTLEMENT SIGNAL PROCESSING

### 5.1 Signal Channel 1 — SWIFT camt.054

**Source topic:** `lip.settlement.camt054`
**Trigger:** `Ntfctn/Ntry/Sts = "BOOK"`
**UETR field:** `Ntfctn/Ntry/NtryDtls/TxDtls/Refs/UETR`

```
Parser extracts:
  uetr                 : string  // Ntfctn/Ntry/NtryDtls/TxDtls/Refs/UETR
  booking_date         : string  // Ntfctn/Ntry/BookgDt
  settled_amount       : double  // Ntfctn/Ntry/Amt
  settlement_currency  : string  // Ntfctn/Ntry/Amt[@Ccy]
  account_iban         : string  // Ntfctn/Acct/Id/IBAN
  entry_status         : string  // Ntfctn/Ntry/Sts — must be "BOOK"
  message_id           : string  // GrpHdr/MsgId
  raw_message_hash     : string  // SHA-256(raw_xml_bytes)
```

**UETR field absence handling (NOVA flag — addressed):**
camt.054 UETR population is not universal across all SWIFT member configurations.
If UETR field is absent:
1. Attempt secondary match via `Ntfctn/Ntry/NtryDtls/TxDtls/Refs/InstrId` → Redis lookup
2. If InstrId match succeeds → proceed, log `camt054_uetr_absent = true`
3. If both fail → route to `lip.settlement.human_review` + alert; never drop silently

### 5.2 Signal Channel 2 — FedNow pacs.002 (ACSC)

**Source topic:** `lip.settlement.fednow`
**Trigger:** `TxInfAndSts/TxSts = "ACSC"`
**UETR field:** `TxInfAndSts/OrgnlUETR` — native, no mapping table required

```
Parser extracts:
  uetr                  : string  // TxInfAndSts/OrgnlUETR (native — direct match)
  individual_payment_id : string  // TxInfAndSts/OrgnlUETR — explicit individual identifier
  settlement_timestamp  : int64   // GrpHdr/CreDtTm (milliseconds)
  transaction_status    : string  // must be "ACSC"
  settled_amount        : double  // TxInfAndSts/OrgnlTxRef/Amt/InstdAmt
  message_id            : string  // GrpHdr/MsgId
  raw_message_hash      : string  // SHA-256(raw_bytes)
```

FedNow carries UETR natively. This is the simplest and most reliable of the 5 channels.

**Disambiguation:** FedNow produces both failure pacs.002 (RJCT) and settlement pacs.002
(ACSC). These arrive on separate Kafka topics to prevent ambiguity:
- `lip.payments.raw` → failure pacs.002 (all rails, filtered for RJCT by Job A)
- `lip.settlement.fednow` → FedNow ACSC events only, pre-filtered at ingestion

### 5.3 Signal Channel 3 — RTP ISO 20022

**Source topic:** `lip.settlement.rtp`
**Trigger:** `TxSts = "ACSC"`
**UETR availability:** NOT native in RTP — requires EndToEndId → UETR resolution (Section 6)

```
Parser extracts:
  end_to_end_id         : string  // CdtTrfTxInf/PmtId/EndToEndId
  transaction_status    : string  // must be "ACSC"
  settlement_date       : string  // RTPSpecific/SttlmDt
  settled_amount        : double  // CdtTrfTxInf/Amt/InstdAmt
  message_id            : string  // GrpHdr/MsgId
  raw_message_hash      : string  // SHA-256(raw_bytes)

UETR resolution:
  redis_lookup: HGET "rtp:e2e:{end_to_end_id}" uetr
  If found    → proceed; individual_payment_id = resolved UETR
  If not found → Section 6.2 missing mapping fallback
```

### 5.4 Signal Channel 4 — SEPA Instant pacs.008

**Source topic:** `lip.settlement.sepa`
**Trigger:** `CdtTrfTxInf/AccptncDtTm` present AND `LclInstrm/Cd = "INST"`
**UETR field:** `CdtTrfTxInf/PmtId/UETR` — native

```
Parser extracts:
  uetr                  : string  // CdtTrfTxInf/PmtId/UETR (direct match)
  individual_payment_id : string  // CdtTrfTxInf/PmtId/UETR — explicit individual identifier
  acceptance_timestamp  : int64   // CdtTrfTxInf/AccptncDtTm (settlement proxy)
  settled_amount        : double  // CdtTrfTxInf/Amt/InstdAmt
  settlement_currency   : string  // CdtTrfTxInf/Amt/InstdAmt[@Ccy]
  local_instrument_code : string  // CdtTrfTxInf/PmtTpInf/LclInstrm/Cd
  message_id            : string  // GrpHdr/MsgId
  raw_message_hash      : string  // SHA-256(raw_bytes)
```

**SEPA Instant finality note:**
AccptncDtTm as settlement confirmation is valid only for SCT Inst (SEPA Instant) — not
standard SCT. Under EPC SCT Inst rules, acceptance is final and irrevocable. Parser
validates `LclInstrm/Cd = "INST"` before triggering repayment. If `LclInstrm/Cd ≠ "INST"`:
route to human review; do NOT auto-trigger.

### 5.5 Signal Channel 5 — Statistical Buffer Fallback

**Trigger:** Processing-time Flink timer (registered at loan funding — Section 4.4).
No external Kafka message. Triggered by wall-clock timer firing on an ACTIVE loan.

```
On BufferTimer fire for individual UETR:

  Check Flink keyed state: loan_state == ACTIVE?
  If NO (terminal already): cancel, log duplicate suppression
  If YES:
    1. Generate SettlementSignal:
         signal_source        = "STATISTICAL_BUFFER"
         is_buffer_trigger    = true
         buffer_p95_hours     = corridor P95 effective value used at funding
         settlement_timestamp = current_processing_time_utc
         settled_amount       = loan_amount_usd (assumed full settlement)
    2. Publish to lip.repayment.instructions
    3. Write DecisionLogEntry: event_type = "BUFFER_REPAID"
    4. Set loan_state = BUFFER_REPAID (terminal)
    5. Publish soft alert to lip.alerts:
         alert_type        = "BUFFER_REPAYMENT_TRIGGERED"
         uetr              = individual_uetr
         corridor          = bic_pair + currency
         buffer_p95_hours  = value used
```

Buffer repayment is not a failure mode. It is the designed behavior for corridors where
explicit settlement confirmation is unavailable. Soft alerts enable monitoring of buffer
trigger rates per corridor — unexpected rate increases may indicate deteriorating settlement
infrastructure warranting taxonomy reclassification.

---

## 6. RTP UETR MAPPING SUB-SERVICE

### 6.1 Design & Redis Schema

RTP (The Clearing House) does not carry UETR natively. C3 maintains an
EndToEndId → UETR mapping table in Redis, populated from outbound payment events published
by the bank's ELO system.

**Redis schema (per Architecture Spec S2.4):**
```
Key:    "rtp:e2e:{EndToEndId}"
Type:   Redis HASH
Fields:
  uetr           : string  // Unique End-to-End Transaction Reference
  corridor       : string  // BIC_sender + "_" + BIC_receiver + "_" + currency
  amount_usd     : string  // USD-normalized amount
  created_at     : string  // Unix milliseconds of outbound event
  rail           : string  // "RTP"
TTL:    (maturity_days + 45) * 86400 seconds
         Class A → 48 days
         Class B → 52 days
         Class C → 66 days (maximum)
```

**Partition key guarantee:** `lip.payments.outbound` is partitioned by UETR. Outbound
events are published before payment initiation, which must precede any failure or
settlement event on the same UETR. This sequence guarantee ensures the mapping is
written to Redis before any settlement signal for that UETR can arrive.

### 6.2 Missing Mapping Fallback

```
When RTP settlement signal arrives with no UETR match in Redis:

Step 1 — Immediate retry:
  3 attempts, 500ms backoff (1.5s total window)
  Handles rare Kafka processing lag race conditions

Step 2 — If retries exhausted with no match:
  Attempt fuzzy match: find loans in ACTIVE state where
    amount_usd matches within ±0.01 USD AND
    settlement_date within maturity_days of funded_timestamp
  If exactly ONE match: route to lip.settlement.human_review
    with suggested UETR (do NOT auto-trigger)
  If ZERO or MULTIPLE matches: route to human_review, no suggestion

Step 3 — All cases:
  Publish alert to lip.alerts:
    alert_type     = "RTP_UNMAPPED_SETTLEMENT"
    end_to_end_id  = EndToEndId from message
    settled_amount = amount from message
    disposition    = "HUMAN_REVIEW_QUEUED"
    raw_msg_hash   = SHA-256 of original message

Invariant: An RTP settlement signal is NEVER silently dropped.
A silently dropped signal on an active loan = missed repayment = capital loss.
```

### 6.3 Sequencing Race Condition (NOVA flag — addressed)

**Scenario:** Bank payment system has a processing lag; the outbound pacs.008 Kafka event
is delayed, and an RTP settlement signal arrives before the UETR mapping is written to Redis.

**Probability:** Very low. The sequence outbound → correspondent processing → RTP settlement
notification → C3 reception takes O(seconds) of network round-trip. The UETR mapper writes
to Redis in O(milliseconds). A race condition requires the Kafka pacs.008 event to be delayed
by more than the full payment round-trip time — architecturally improbable under normal
conditions.

**Mitigation:** The 3-retry window in Section 6.2 (1.5 seconds) covers all realistic
scenarios. Residual risk: if the bank never publishes outbound pacs.008 events (integration
contract violation), all RTP signals fail permanently. This is an integration enforcement
issue documented in Section 14, Requirement 1.

---

## 7. CORRIDOR BUFFER DESIGN

### 7.1 P95 Formula & Rolling Window

The statistical buffer is a per-corridor estimate of the 95th percentile settlement latency.
When no explicit settlement signal has arrived within this window, C3 assumes settlement has
occurred statistically and triggers buffer repayment.

**Corridor key:** `{BIC8_sender}_{BIC8_receiver}_{currency_pair}`
e.g., `BARCGB22_CITIUS33_USD_GBP`

```
For corridor C with N observations in rolling 90-day window:

  settlement_latencies = [h₁, h₂, ..., hₙ]  // hours: pacs.002 → settlement signal

  P95(C) = 95th percentile of settlement_latencies
         = sorted_latencies[ ceil(0.95 * N) - 1 ]   // 0-indexed

Rolling window:
  Include : settlement events where event_timestamp > (NOW - 90 days)
  Exclude : DEFAULTED events (no settlement — not a valid latency sample)
  Update  : on each new settlement event → add, evict events > 90 days
  Storage : Redis Sorted Set "corridor:latency:{corridor_id}"
              Score  = settlement_timestamp_utc (for time-based eviction)
              Member = settlement_latency_hours (float, 2dp)

Latency measurement:
  latency_hours =
    (settlement_signal_timestamp_utc - pacs002_creation_timestamp_utc)
    / 3,600,000
```

### 7.2 4-Tier Bootstrap Protocol

```
Tier 0 — N < 50 observations:
  P95_effective = 72 hours (conservative flat default)
  data_source   = "DEFAULT_TIER0"
  Note: for known major corridors (EUR/USD, GBP/USD, USD/JPY),
        consider seeding from public BIS/SWIFT GPI statistics
        rather than flat 72h — flagged as pre-Gate 2.1 enhancement

Tier 1 — 50 ≤ N < 100 observations:
  P95_effective = P95_observed * 1.30  // 30% safety margin
  Rationale: early estimates have high variance

Tier 2 — 100 ≤ N < 200 observations:
  P95_effective = P95_observed * 1.15  // 15% safety margin
  Rationale: estimate stabilizing

Tier 3 — N ≥ 200 observations:
  P95_effective = P95_observed * 1.05  // 5% measurement noise margin
  Rationale: statistically reliable; quarterly recalibration applies

Tier is computed at loan FUNDING TIME and does not change during the loan's life.
```

Redis corridor metadata:
```
Key: "corridor:meta:{corridor_id}"   Type: HASH
Fields:
  observation_count     : int    // N in rolling window
  tier                  : int    // 0–3
  p95_hours_raw         : float  // before safety margin
  p95_hours_effective   : float  // after safety margin (used for timer)
  window_start_utc      : int64  // oldest event in rolling window
  last_updated_utc      : int64
  data_source           : string // "OBSERVED" | "DEFAULT_TIER0"
```

### 7.3 Buffer vs. Maturity Window Relationship

This guard is mandatory. Without it, a corridor P95 > maturity_days would set a buffer timer
that fires after the maturity timer. Since DEFAULTED is a terminal state, the buffer could
never fire — the loan would be incorrectly declared in default on corridors with wide P95.

```
INVARIANT: buffer_trigger_hours < maturity_days * 24

Enforcement at timer registration:

  raw_buffer_hours         = P95_corridor_effective_hours
  max_allowed_buffer_hours = (maturity_days * 24) - 24  // 24h before maturity

  buffer_trigger_hours = min(raw_buffer_hours, max_allowed_buffer_hours)

  If capped (raw > max):
    Log warning "corridor_buffer_capped":
      corridor          = corridor_id
      raw_p95_hours     = raw_buffer_hours
      capped_to_hours   = max_allowed_buffer_hours
      maturity_days     = maturity_days
    Note: consistent capping on a corridor is a signal that settlement is
    highly uncertain there — Class C (21 days) is the maximum available
    backstop. Buffer will fire at day 20; maturity at day 21.
```

---

## 8. IDEMPOTENCY DESIGN

### 8.1 Redis Deduplication Layer

```
Deduplication key : "repaid:{uetr}"
Type              : Redis string
Value             : signal_source that first triggered repayment
TTL               : maturity_days * 86400 + 7 * 86400  // maturity + 7-day buffer

Check logic (atomic):
  SETNX "repaid:{uetr}" "{signal_source}"

  Returns 1 (key absent, now set)
    → First signal for this UETR
    → Proceed with repayment trigger

  Returns 0 (key already exists)
    → Duplicate signal
    → Silently drop
    → Log: duplicate_signal_suppressed = true,
           original_source = GET "repaid:{uetr}"
    → Do NOT generate RepaymentInstruction
    → Do NOT modify loan state
```

### 8.2 Flink Exactly-Once Semantics

- Kafka consumer: `isolation.level = read_committed`
- Checkpoint interval: 10 seconds, RocksDB state backend
- Kafka sink: transactional two-phase commit (Flink Kafka Sink v2)
- On Flink restart: state restored from checkpoint; Kafka offsets restored from checkpoint
  (not broker offset); messages since last checkpoint reprocessed; Redis dedup catches any
  duplicate repayment triggers from reprocessing

Net effect: exactly-once repayment trigger per individual UETR guaranteed under
any single-node Flink failure scenario.

### 8.3 Duplicate Signal Handling

```
Scenario 1 — Two channels fire within milliseconds of each other:
  e.g., camt.054 at T+2h, FedNow pacs.002 at T+2.05h
  Handler: camt.054 SETNX=1 → proceeds. FedNow SETNX=0 → dropped.
  Outcome: Exactly one RepaymentInstruction to C7.

Scenario 2 — Kafka at-least-once redelivery of same message:
  Handler: message_id deduplication in Flink (24h window).
           Dropped at message level before UETR-level dedup.
  Outcome: Idempotent at two independent layers.

Scenario 3 — Buffer fires after explicit settlement (race condition):
  e.g., FedNow fires at T+6h, buffer timer fires at T+6.5h
  Handler: FedNow sets loan_state = REPAID (terminal).
           Buffer timer fires → checks loan_state ≠ ACTIVE → cancelled.
  Outcome: Timer cancellation on repayment is mandatory; enforced always.

Scenario 4 — Settlement signal arrives on DEFAULTED loan:
  e.g., Long-delayed camt.054 after maturity expiry
  Handler: DEFAULTED is terminal → signal dropped; log late_settlement = true
           Alert: routed to human review for capital recovery investigation
  Outcome: State immutable. Alert for potential recovery action.
```

---

## 9. STATE MACHINE IMPLEMENTATION

### 9.1 Payment Lifecycle — C3 Transitions

```
C3-owned transitions (Architecture Spec S6):

  FUNDED → REPAID          Channels 1–4 validated signal received
  FUNDED → BUFFER_REPAID   Channel 5 buffer timer fires
  FUNDED → DEFAULTED       Maturity timer fires, no prior repayment

Transitions C3 does NOT own:
  MONITORING      → FAILURE_DETECTED   Flink stream processor + Job A
  FAILURE_DETECTED → DISPUTE_BLOCKED   C4
  FAILURE_DETECTED → AML_BLOCKED       C6
  FAILURE_DETECTED → BRIDGE_OFFERED    Decision Engine
  BRIDGE_OFFERED  → FUNDED             C7 ELO execution
  BRIDGE_OFFERED  → OFFER_DECLINED     C7 ELO decline or 60s timeout
```

### 9.2 Loan Lifecycle — C3 Transitions

```
C3-owned transitions (Architecture Spec S7):

  ACTIVE            → REPAYMENT_PENDING  Any settlement signal received + validated
  REPAYMENT_PENDING → REPAID             Channels 1–4 instruction sent, C7 confirms
  REPAYMENT_PENDING → BUFFER_REPAID      Channel 5 buffer instruction sent
  ACTIVE            → DEFAULTED          Maturity timer fires, no prior signal
```

### 9.3 Timer Management

```
[LOAN_FUNDED received]
    |
    ├── Register Buffer Timer
    |     timer_id  = "buf:{uetr}"
    |     fire_at   = funded_utc + buffer_trigger_hours * 3,600,000
    |     type      = PROCESSING_TIME
    |
    ├── Register Maturity Timer
    |     timer_id  = "mat:{uetr}"
    |     fire_at   = funded_utc + maturity_days * 86,400,000
    |     type      = PROCESSING_TIME
    |
    └── Set Flink keyed state: loan_state = ACTIVE

[Settlement signal received — loan_state == ACTIVE]
    |
    ├── Validate → idempotency check (SETNX)
    ├── If first signal:
    |     deleteTimer("buf:{uetr}")       // cancel buffer timer
    |     deleteTimer("mat:{uetr}")       // cancel maturity timer
    |     Set loan_state = REPAYMENT_PENDING
    |     Publish RepaymentInstruction → C7
    |     On C7 confirmation → loan_state = REPAID (terminal)
    |     Clear Flink keyed state
    └── If duplicate → drop + log

[Buffer Timer fires — loan_state == ACTIVE]
    |
    ├── deleteTimer("mat:{uetr}")
    ├── Set loan_state = BUFFER_REPAID (terminal)
    ├── Publish RepaymentInstruction (signal_source = STATISTICAL_BUFFER)
    ├── Publish soft alert to lip.alerts
    └── Clear Flink keyed state

[Maturity Timer fires — loan_state == ACTIVE]
    |
    ├── Set loan_state = DEFAULTED (terminal)
    ├── Publish DefaultDeclaration to lip.repayment.instructions
    ├── Publish HARD alert to lip.alerts (alert_type = LOAN_DEFAULTED)
    ├── Write DecisionLogEntry: event_type = "DEFAULTED"
    └── Clear Flink keyed state
```

### 9.4 Terminal State Guarantees

```
Terminal states: REPAID | BUFFER_REPAID | DEFAULTED

Invariants:
  1. Once terminal state written → no signal or timer can overwrite it
  2. Terminal states persisted to:
       Flink keyed state          (primary runtime)
       Redis "repaid:{uetr}"      (idempotency gate)
       lip.decisions.log          (append-only, 7-year retention)
       lip.state.transitions      (full state machine audit)
  3. Backward transitions forbidden:
       Any terminal → any state: raise error + alert (not silent drop)
  4. DEFAULTED ≠ unrecoverable capital loss:
       Late settlement on DEFAULTED loan → alert only, no state change
       Routes to human review for manual capital recovery investigation
```

---

*End of Part 1. Continues in BPI_C3_Component_Spec_v1.0_Part2.md*
*Sections 10–18: Repayment Instruction Flow, Flink Job Topology, Error Handling,*
*IP Alignment, Integration Requirements, Monitoring, Known Limitations,*
*Validation Requirements, Audit Gate 2.1 Checklist*

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026 | Lead: NOVA | Version: 1.0*
