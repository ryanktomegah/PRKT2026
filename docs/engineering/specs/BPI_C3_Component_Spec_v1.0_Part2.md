# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 3 — DUAL-SIGNAL REPAYMENT ENGINE
## Build Specification v1.0 — Part 2 of 2
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** NOVA — Payments Infrastructure Engineering
**Support:** LEX (claim language), FORGE (streaming integration),
             REX (DORA / EU AI Act), CIPHER (idempotency adversarial testing)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

> This is Part 2 of 2. Part 1 (BPI_C3_Component_Spec_v1.0_Part1.md) covers
> Sections 1–9: Purpose, Architecture, Failure Detection, Signal Channels,
> RTP Mapping, Corridor Buffer, Idempotency, and State Machine.

---

## TABLE OF CONTENTS — PART 2

10. Repayment Instruction Flow
    10.1 Normalized Settlement Event Schema
    10.2 RepaymentInstruction to C7
    10.3 Decision Log Entry
11. Flink Job Topology
    11.1 Kafka Topics: Consumed and Produced
    11.2 Keyed State Design
    11.3 Processing Time vs. Event Time — Explicit Decision
12. Error Handling & Fallbacks
    12.1 Malformed Messages
    12.2 Redis Unavailability
    12.3 Kafka Consumer Lag
    12.4 camt.054 UETR Field Absent
13. IP & Claim Alignment (LEX)
14. Integration Requirements (Bank-Side)
15. Monitoring & Alerting
16. Known Limitations & Open Design Questions (NOVA Self-Critique)
17. Validation Requirements
    17.1 Settlement Signal Parser Tests
    17.2 State Machine Completeness Test
    17.3 Corridor Buffer Accuracy
    17.4 Idempotency Stress Test
    17.5 T = f(rejection_code_class) Completeness
    17.6 camt.054 Absence Test
18. Audit Gate 2.1 Checklist

---

## 10. REPAYMENT INSTRUCTION FLOW

### 10.1 Normalized Settlement Event Schema

All five signal channels produce parser-specific outputs. Before any downstream processing,
each is normalized to a common `NormalizedSettlementEvent`. This normalization step makes
the idempotency layer and state machine fully channel-agnostic.

```
NormalizedSettlementEvent {
  uetr                  : string   // individual UETR — primary key
  individual_payment_id : string   // same as UETR — explicit individual identifier
  signal_source         : string   // "SWIFT_CAMT054" | "FEDNOW_PACS002" |
                                   //  "RTP_ISO20022" | "SEPA_INSTANT" |
                                   //  "STATISTICAL_BUFFER"
  settlement_timestamp  : int64    // milliseconds UTC
                                   // (processing time if buffer trigger)
  settled_amount        : double   // in original currency units
  settlement_currency   : string   // ISO 4217 ("USD" if buffer trigger)
  raw_message_hash      : string   // SHA-256 of original message bytes
                                   // (empty string for buffer — no source message)
  is_buffer_trigger     : bool     // true only for Channel 5
  buffer_p95_hours      : float    // P95 effective value used (0.0 if not buffer)
  corridor              : string   // from Flink keyed state
  normalization_flags   : string[] // "UETR_FROM_INSTR_ID" | "SEPA_INST_CONFIRMED" |
                                   //  "RTP_MAPPING_RESOLVED" | etc.
}
```

### 10.2 RepaymentInstruction to C7

C3 publishes repayment instructions to Kafka topic `lip.repayment.instructions`.
C7 consumes this topic and executes the actual repayment via the bank's core banking system.

```
RepaymentInstruction {
  uetr                  : string   // individual UETR
  individual_payment_id : string   // explicit individual identifier — same as UETR
  loan_reference        : string   // from original ExecutionConfirmation (bank's ID)
  repayment_amount_usd  : double   // principal + fee (total amount owed)
  principal_usd         : double   // loan principal only
  fee_usd               : double   // computed at repayment time:
                                   //   fee = principal
                                   //         * (fee_bps / 10000)
                                   //         * (days_funded / 365)
                                   //   uses ACTUAL days_funded, not maturity_days
  days_funded           : int32    // (settlement_timestamp - funded_utc) / 86,400,000
  settlement_source     : string   // from NormalizedSettlementEvent.signal_source
  settlement_timestamp  : int64    // from NormalizedSettlementEvent
  is_buffer_repayment   : bool
  instruction_id        : string   // UUID v4 — idempotency key for C7
  instruction_timestamp : int64    // when C3 generated this instruction
}
```

**Fee calculation note:**
Early repayment uses actual `days_funded`, not `maturity_days`. This is an explicit
design feature — it incentivizes counterparties to re-route failed payments quickly and
rewards early settlement with lower fees. Floor: fee must be ≥ minimum computed at
300 bps annualized = 0.0575% per 7-day cycle. If actual `days_funded < 1`:
set `days_funded = 1` (same-day minimum floor).

### 10.3 Decision Log Entry

Every C3-triggered state change generates a `DecisionLogEntry` (Architecture Spec S4.8):

```
C3 DecisionLogEntry fields (REPAID | BUFFER_REPAID | DEFAULTED):

  log_entry_id          : string  // UUID v4
  uetr                  : string  // individual UETR
  event_type            : string  // "REPAID" | "BUFFER_REPAID" | "DEFAULTED"
  timestamp_utc         : int64
  amount_usd            : double  // loan principal at event time
  rejection_code        : string  // from original pacs.002 classification
  rejection_code_class  : string  // A | B | C | UNKNOWN
  maturity_days         : int32   // from T = f(rejection_code_class)
  days_funded           : int32   // actual days loan was active
  settlement_source     : string  // signal source, or "NONE" if defaulted
  fee_usd               : double  // actual fee charged (0.0 if defaulted)
  taxonomy_status       : string  // "CLASSIFIED" | "UNCLASSIFIED"
  model_version_c1      : string  // from original offer — full audit trail
  model_version_c2      : string
  model_version_c4      : string
  entry_signature       : string  // HMAC-SHA256 of entry content
```

---

## 11. FLINK JOB TOPOLOGY

### 11.1 Kafka Topics: Consumed and Produced

```
CONSUMED BY C3:
  lip.payments.raw            pacs.002 events (Job A: failure classifier)
  lip.loans.funded            ExecutionConfirmation from C7 (activate monitoring)
  lip.payments.outbound       outbound pacs.008 from bank ELO (RTP mapper)
  lip.settlement.camt054      SWIFT camt.054 booking confirmations
  lip.settlement.fednow       FedNow pacs.002 ACSC events
  lip.settlement.rtp          RTP ISO 20022 settlement events
  lip.settlement.sepa         SEPA Instant pacs.008 acceptance events

PRODUCED BY C3:
  lip.payments.classified     UETR + rejection_class + maturity_days
                              → consumed by Decision Engine and C2
  lip.repayment.instructions  RepaymentInstruction → C7
  lip.decisions.log           DecisionLogEntry (REPAID/BUFFER_REPAID/DEFAULTED)
  lip.state.transitions       Full state machine audit trail
  lip.alerts                  Operational alerts (buffer triggers, defaults, unmapped)
  lip.settlement.human_review Signals requiring manual UETR matching
  lip.dlq.parse_error         Unparseable messages (dead letter queue)
```

### 11.2 Keyed State Design

All Flink state is keyed by UETR. State backend: RocksDB (persistent, checkpoint-recoverable).

```
Per-UETR runtime state:

  LoanMonitorState {
    uetr                  : string
    loan_state            : enum    // ACTIVE | REPAID | BUFFER_REPAID | DEFAULTED
    funded_utc            : int64
    maturity_days         : int32
    rejection_class       : string
    loan_amount_usd       : double
    loan_reference        : string  // bank's internal ID
    corridor              : string
    buffer_hours_used     : float   // P95 effective at funding time
    buffer_timer_id       : string  // Flink timer registration reference
    maturity_timer_id     : string
    fee_bps               : float   // annualized (from LoanOffer)
    model_version_c1      : string  // audit trail continuity
    model_version_c2      : string
    model_version_c4      : string
  }

Per-message deduplication state (24h TTL, Flink map state):
  MessageDeduplication {
    message_id            : string  // GrpHdr/MsgId
    processed_at          : int64
  }

State retention policy:
  Active loans       : retained until terminal state + 7 days
  Terminal state     : cleared from Flink state after 7 days
  Audit records      : Kafka lip.decisions.log (7-year retention — Arch Spec S11.7)
```

### 11.3 Processing Time vs. Event Time — Explicit Decision

C3's buffer and maturity timers use **processing time** (wall-clock), not event time.
This is an explicit design decision.

**Rationale:**
Event-time timers require watermarks. In a multi-rail settlement system, watermarks on
settlement topics are unreliable because signals may arrive with hours or days of delay
relative to the original payment event. A watermark-based timer would stall indefinitely
on sparse corridors — precisely the corridors where the buffer is most needed.

Processing-time timers advance at wall-clock rate regardless of message arrival. For
financial loan maturity (3/7/21 calendar days), wall-clock time is the contractually
correct reference. A 7-day loan matures 7 calendar days after funding — not 7
"event-stream days."

**Known implication:** If the Flink job is paused and restarted after an extended outage,
processing-time timers that fired during the outage will execute immediately on restart.
The terminal state guard (Section 9.4) prevents double-firing. Operationally, this may
produce a burst of DEFAULTED declarations on restart — these are correct declarations,
not errors. Alert suppression on restart should batch these into a single grouped alert
rather than individual per-loan alerts.

---

## 12. ERROR HANDLING & FALLBACKS

### 12.1 Malformed Messages

```
UETR absent:
  → Discard to lip.dlq.parse_error
  → Alert: "MISSING_UETR_IN_SETTLEMENT_SIGNAL"
  → Never attempt downstream processing without UETR

Rejection code absent (pacs.002 only):
  → Set rejection_code = "UNKNOWN"; class = C; maturity_days = 21
  → taxonomy_status = "UNCLASSIFIED"
  → Proceed — UNKNOWN is a valid class, not a parse error

Amount unparseable:
  → Set amount = 0.0; amount_parse_failed = true; log warning
  → Proceed — amount mismatch checking is advisory; does not block repayment

Timestamp absent:
  → Use Kafka message timestamp as fallback
  → timestamp_source = "KAFKA_FALLBACK"; log warning

Entire message invalid (not parseable as ISO 20022):
  → Discard to lip.dlq.parse_error; no further processing
  → Alert if dead letter rate > 0.1% of volume in any 1-hour window
```

### 12.2 Redis Unavailability

```
C3 Redis dependencies:
  (a) Corridor buffer P95 lookup at loan funding
  (b) RTP UETR mapping writes and reads
  (c) Idempotency deduplication keys

(a) Buffer P95 lookup fails (Redis read unavailable):
  → Use Tier 0 default (72 hours) as conservative fallback
  → Log: "REDIS_UNAVAILABLE_BUFFER_FALLBACK"
  → Do NOT halt loan monitoring activation — conservative buffer is safe

(b) RTP mapping write fails (Redis write unavailable):
  → Buffer the pacs.008 event in Flink keyed state (durable)
  → On Redis recovery: replay buffered events
  → Alert: "RTP_MAPPING_WRITE_DELAYED"

(c) Idempotency dedup key read fails:
  → FAIL-SAFE: do NOT trigger repayment without confirmed dedup check
  → Buffer the settlement signal in Flink state
  → On Redis recovery: re-process buffered signals
  → Alert: "REPAYMENT_DEDUP_CHECK_DEFERRED"
  → Rationale: a missed dedup check risks double repayment instruction.
    Deferral is safe; a double instruction to C7 is not.

Redis unavailability is NEVER fail-open for repayment triggering.
```

### 12.3 Kafka Consumer Lag

```
Consumer lag > 60 seconds:
  → Alert: "SETTLEMENT_CONSUMER_LAG_HIGH"
  → Include: topic, partition, lag_seconds, uetr_count_in_backlog

Consumer lag > 300 seconds:
  → Alert: "SETTLEMENT_CONSUMER_LAG_CRITICAL"
  → Check: is Flink parallelism at maximum? Trigger autoscale review
  → Human review: are any active loans at risk of timer expiry
    before the backlog clears?

Timer behavior under consumer lag:
  Processing-time timers advance at wall-clock regardless of lag.
  If a loan's buffer or maturity timer fires while its settlement
  signal is in the consumer backlog, the timer wins. When the
  backlog clears and the signal is processed, it is silently dropped
  (loan already in terminal state). This is correct — the contractual
  maturity window is wall-clock, not queue-adjusted.
```

### 12.4 camt.054 UETR Field Absent

Summary of handling path (full detail in Section 5.1):

```
1. Primary: UETR from Ntfctn/Ntry/NtryDtls/TxDtls/Refs/UETR
2. Secondary: InstrId match via Redis mapping table
3. If secondary succeeds: proceed; log "CAMT054_UETR_ABSENT_INSTR_MATCH"
4. If both fail: route to lip.settlement.human_review + alert
5. Invariant: a camt.054 with Ntry/Sts = "BOOK" is NEVER silently dropped
```

---

## 13. IP & CLAIM ALIGNMENT (LEX)

LEX has reviewed this specification against all immutable standards.

### "individual" + "UETR" — line-by-line check

```
Section 4.1 ParsedFailureEvent:
  individual_payment_id : "explicit individual identifier" ✅
  uetr                  : canonical UETR field ✅

Section 5.2 FedNow parser:
  individual_payment_id : "TxInfAndSts/OrgnlUETR — explicit individual identifier" ✅
  uetr                  : ✅

Section 5.3 RTP parser:
  UETR resolution produces individual_payment_id explicitly ✅

Section 5.4 SEPA Instant parser:
  individual_payment_id : "CdtTrfTxInf/PmtId/UETR — explicit individual identifier" ✅

Section 10.1 NormalizedSettlementEvent:
  uetr                  : "individual UETR — primary key" ✅
  individual_payment_id : "explicit individual identifier" ✅

Section 10.2 RepaymentInstruction:
  uetr                  : "individual UETR" ✅
  individual_payment_id : "explicit individual identifier — same as UETR" ✅

Section 10.3 DecisionLogEntry:
  uetr                  : "individual UETR" ✅
  rejection_code_class  : A | B | C logged per decision ✅
  maturity_days         : from T = f(rejection_code_class) ✅
```

### T = f(rejection\_code\_class) — explicit at every use

```
Section 4.2 : Taxonomy table with explicit Class → maturity_days ✅
Section 4.3 : Function formalized, named, and properties documented ✅
Section 4.4 : maturity timer uses maturity_days from classification ✅
Section 10.3: rejection_code_class + maturity_days in every DecisionLogEntry ✅
Section 17.5: 47+1 code coverage test required at Audit Gate ✅
```

### camt.054 fallback — first-class, not implied

```
Section 5.1  : camt.054 is Channel 1; UETR-absent fallback explicit ✅
Section 5.5  : Statistical buffer explicitly designed for camt.054-absent corridors ✅
Section 12.4 : Handling path for absent UETR documented ✅
Section 17.6 : camt.054 absence test is a mandatory Audit Gate 2.1 item ✅
```

### Recentive v. Fox

Zero mentions in this document. ✅

### §101 anchor — quantifiable technical improvements

```
vs. JPMorgan US7089207B1:
  JPMorgan assigns static maturity terms independent of rejection code.
  C3 implements T = f(rejection_code_class) — dynamic maturity as a learned
  function of rejection taxonomy. Non-generic rule (McRO) producing a
  specific technical outcome: correctly sized bridge loan duration per
  individual UETR-keyed payment event.

vs. manual treasury processes:
  Multi-rail settlement detection triggering automated repayment replaces
  24-48 hour manual reconciliation cycles. UETR-keyed per-transaction
  state monitoring is a specific computer improvement (Enfish) — not
  generic data aggregation.
```

---

## 14. INTEGRATION REQUIREMENTS (BANK-SIDE)

These are hard requirements on the bank's infrastructure. C3 cannot function correctly
without them. They must be documented in the C7 bank deployment guide and verified
during pilot onboarding.

```
Requirement 1 — Outbound pacs.008 publication (MANDATORY for RTP corridors):
  The bank's payment initiation system MUST publish ISO 20022 pacs.008 events
  to Kafka topic lip.payments.outbound for every outbound payment that may settle
  via RTP. Published at or before payment initiation time.
  Required fields: EndToEndId, UETR, corridor, amount_usd, maturity_days.
  Failure consequence: all RTP settlement signals for that bank become
  permanently unresolvable. C3 will route all RTP signals to human review.
  Verification: dedicated integration test during C7 pilot onboarding.

Requirement 2 — SWIFT camt.054 subscription (STRONGLY RECOMMENDED):
  For SWIFT corridors where camt.054 is available, the bank SHOULD subscribe
  to camt.054 notifications and route them to lip.settlement.camt054.
  Not mandatory — C3 functions via Channel 5 without it — but camt.054
  provides the most precise settlement confirmation available.

Requirement 3 — FedNow event routing (MANDATORY for USD domestic corridors):
  FedNow pacs.002 ACSC events MUST be routed to lip.settlement.fednow.
  Required for all loans with USD domestic settlement legs.

Requirement 4 — SEPA Instant event routing (MANDATORY for EU corridors):
  SEPA Instant acceptance events MUST be routed to lip.settlement.sepa.
  C3 SEPA parser will validate LclInstrm/Cd = "INST" before treating as
  settlement (see Section 5.4).

Requirement 5 — Kafka topic access:
  Bank ELO writes to  : lip.payments.outbound, lip.loans.funded
  Bank ELO reads from : lip.repayment.instructions, lip.settlement.human_review
  All topics within bank infrastructure. Zero outbound data to Bridgepoint.

Requirement 6 — Clock synchronization:
  Bank infrastructure clock synchronized to NTP within ±1 second.
  Processing-time maturity/buffer timers are wall-clock — significant drift
  would cause timers to fire at contractually incorrect times.
```

---

## 15. MONITORING & ALERTING

```
REPAYMENT HEALTH:
  repayment_rate_by_channel
    % of repayments triggered per signal source (1–5)
    Expected: camt.054 dominant for SWIFT corridors

  buffer_repayment_rate_by_corridor
    % of repayments via Channel 5 (buffer) per corridor
    Alert threshold: >30% on any corridor
    Indicates: camt.054 unavailable or settlement pattern deteriorating

  default_rate_by_rejection_class
    Defaults per Class A / B / C
    Alert threshold: Class A default rate > 0.5%
    (Class A represents known permanent failures — very low expected default)

  late_settlement_on_defaulted_loans
    Count per week of settlement signals on DEFAULTED UETRs
    Each instance = capital recovery candidate → route to operations team

SETTLEMENT LAG:
  p50_settlement_hours_by_corridor   median latency per corridor
  p95_settlement_hours_by_corridor   used for buffer calibration
  buffer_timer_accuracy              (buffer_fire_time − actual_settlement_time)
                                     positive = buffer fired before confirmation;
                                     negative = should not occur; investigate if seen

STATE MACHINE HEALTH:
  undefined_transition_count         MUST be zero; any non-zero = critical defect
  terminal_state_overwrite_attempt   MUST be zero; any non-zero = critical defect
  duplicate_signal_suppression_rate  expected non-zero; sudden spike = investigate

TAXONOMY:
  unknown_rejection_code_count       per week, by raw code → feeds quarterly review
  unclassified_loan_count            loans with taxonomy_status = "UNCLASSIFIED"

INFRASTRUCTURE:
  rtp_unmapped_signal_count          per day; >0 = check Requirement 1 compliance
  parse_error_rate                   events in lip.dlq.parse_error; alert if >0.1%/hr
  redis_fallback_count               buffer using Tier 0 default due to Redis miss
  consumer_lag_by_topic              all settlement topics; alert at 60s; critical at 300s
  flink_checkpoint_gap               alert if checkpoint interval > 60s
```

---

## 16. KNOWN LIMITATIONS & OPEN DESIGN QUESTIONS (NOVA SELF-CRITIQUE)

These are honest design challenges surfaced before build, not discovered during audit.
None are blockers for Phase 2 build start. All must be resolved before Audit Gate 2.1.

### 16.1 camt.054 UETR Population Coverage

**Issue:** The UETR field in camt.054 was introduced with ISO 20022 adoption. Older SWIFT
member configurations — particularly in some APAC and LATAM corridors — may not populate it.
The secondary InstrId match (Section 5.1) is a mitigation, not a guarantee, as InstrId
availability also varies by schema version.

**True ceiling:** On legacy-configured corridors, camt.054 may arrive with neither UETR nor
InstrId. Channel 1 is effectively unavailable; Channel 5 (buffer) becomes the primary
repayment trigger. This is designed behavior. The limitation is that settlement is confirmed
statistically rather than definitively on these corridors.

**Mitigation:** Before activating bridge lending on any corridor, run a 30-day camt.054
availability audit: what % of camt.054 messages carry populated UETR? If <70%, configure
that corridor to treat Channel 5 as the primary expected channel and monitor buffer trigger
rates accordingly.

### 16.2 SEPA Instant Schema Validation

**Issue:** Some multi-bank SEPA configurations route pacs.008 messages with inconsistent
`LclInstrm/Cd` population. The parser's `LclInstrm/Cd = "INST"` guard (Section 5.4) may
route valid SEPA Instant confirmations to human review if the field is absent or incorrectly
coded by the originating system.

**Residual risk:** Low. SEPA Instant is additive to camt.054 and the buffer for EU corridors.
Channel 4 routing to human review is conservative but not a capital risk — it delays
automated repayment recognition, not the repayment itself.

**Mitigation:** During EU corridor pilot onboarding, characterize the pacs.008 message
patterns from each corridor before relying on Channel 4 for automated triggering.

### 16.3 RTP Integration Contract Enforcement

**Issue:** Requirement 1 (Section 14) depends on the bank's payment initiation system.
Bridgepoint cannot enforce this — it is a bank-side integration deliverable. If the bank
fails to publish outbound pacs.008 events, all RTP settlement signals become permanently
unresolvable for that bank.

**Mitigation:** Alert `RTP_UNMAPPED_SETTLEMENT` fires on every unmapped signal. Consistent
firing for a bank is an unambiguous indicator of the missing integration. Human review
fallback (Section 6.2) ensures no capital is lost — repayment is delayed, not missed.

**C7 spec dependency flagged:** The C7 bank deployment guide must include an explicit
integration test for outbound pacs.008 publication before any corridor goes live on RTP.

### 16.4 Flink Processing-Time Timer Burst on Restart

**Issue:** If Flink is down for longer than a loan's maturity window (e.g., 3+ days for
Class A), loans whose timers fired during the outage execute in rapid succession on restart.
Multiple DEFAULTED declarations may cascade simultaneously.

**Assessment:** This is correct behavior under the wall-clock contract. The operational
concern is alert flooding. Mitigation: batch DEFAULTED events within a 60-second restart
window into a single grouped alert rather than per-loan alerts. The state machine terminal
state guarantee prevents double-firing regardless.

**Likelihood:** Requires a Flink availability failure of multi-day duration. Covered by
Flink HA configuration (FORGE Phase 4 deliverable). Not a C3 design defect.

### 16.5 Tier 0 Buffer Seeding With Public Data

**Issue:** The flat 72-hour Tier 0 default is conservative but unsophisticated. For
well-characterized corridors at pilot launch (EUR/USD, GBP/USD, USD/JPY), public
BIS/SWIFT GPI cross-border payment SLA data could provide materially better initial
P95 estimates.

**Status:** Non-blocking for Phase 2 build. Flagged as a pre-Audit Gate 2.1 enhancement.
NOVA to build a corridor seed table from public SWIFT GPI SLA statistics before gate.

---

## 17. VALIDATION REQUIREMENTS

### 17.1 Settlement Signal Parser Tests

```
Channel 1 — camt.054 (minimum 50 real ISO 20022 samples):
  [ ] Ntry/Sts = "BOOK" triggers correctly
  [ ] Ntry/Sts = "PDNG" does NOT trigger
  [ ] UETR-populated sample: direct match succeeds
  [ ] UETR-absent sample: InstrId secondary match fires
  [ ] UETR-absent + InstrId-absent: routes to human_review, not dropped
  [ ] Amount and booking_date extracted correctly
  [ ] SHA-256 hash computed on raw bytes, not parsed fields

Channel 2 — FedNow pacs.002 (minimum 30 samples):
  [ ] TxSts = "ACSC" triggers; "RJCT" does NOT trigger
  [ ] OrgnlUETR extracted directly — no Redis lookup required
  [ ] Disambiguation confirmed: failure pacs.002 on lip.payments.raw,
      settlement pacs.002 on lip.settlement.fednow — no cross-contamination

Channel 3 — RTP (minimum 30 samples):
  [ ] EndToEndId present: Redis mapping lookup fires and resolves UETR
  [ ] Mapping absent: 3-retry logic fires with 500ms backoff
  [ ] After 3 retries, no match: fuzzy match attempted
  [ ] All paths route to lip.settlement.human_review (never silently dropped)
  [ ] Alert "RTP_UNMAPPED_SETTLEMENT" fires on every unresolved signal

Channel 4 — SEPA Instant (minimum 30 samples):
  [ ] LclInstrm/Cd = "INST": triggers repayment
  [ ] LclInstrm/Cd = "SCT": routes to human_review; does NOT trigger
  [ ] LclInstrm/Cd absent: routes to human_review; does NOT trigger
  [ ] AccptncDtTm extraction correct

Channel 5 — Statistical Buffer:
  [ ] Buffer timer fires at correct wall-clock offset from funded_utc
  [ ] Guard invariant tested: buffer_trigger_hours < maturity_days * 24
      (tested for all 3 maturity classes: 3, 7, 21 days)
  [ ] Capping logic fires when P95 > maturity_days * 24h; warning logged
  [ ] Buffer generates STATISTICAL_BUFFER signal_source in RepaymentInstruction
  [ ] Soft alert fires to lip.alerts on buffer trigger
```

### 17.2 State Machine Completeness Test

```
Valid transitions — all must pass:
  [ ] MONITORING → FAILURE_DETECTED   pacs.002 RJCT received
  [ ] FUNDED → REPAID                 each of Channels 1–4 independently
  [ ] FUNDED → BUFFER_REPAID          Channel 5 timer fires
  [ ] FUNDED → DEFAULTED              maturity timer fires, no prior signal

Forbidden / terminal transitions — must block and alert:
  [ ] REPAID → any state              silently dropped + logged (not error)
  [ ] DEFAULTED → any state           terminal; signal dropped + logged
  [ ] BUFFER_REPAID → any state       terminal; signal dropped + logged
  [ ] Backward transition attempt     raises error + alert (not silent)

Undefined input under all states:
  [ ] Malformed message → dead letter; no state change
  [ ] Duplicate settlement signal → dropped; no double RepaymentInstruction
  [ ] Late settlement on DEFAULTED loan → alert only; state unchanged
  [ ] Redis unavailable during dedup → deferred; not skipped (fail-safe)

Requirement: ZERO undefined transition states under any input combination.
```

### 17.3 Corridor Buffer Accuracy

```
Using historical or synthetic settlement data:

  Generate 500 simulated loan lifecycles across 5 corridor archetypes:
    - High-frequency major corridor (e.g., EUR/USD, abundant data)
    - Low-frequency emerging corridor (sparse data, Tier 1 or 2)
    - New corridor (zero history, Tier 0)
    - APAC legacy corridor (camt.054 absent, buffer primary)
    - EU SEPA corridor (mix of Channels 1, 4, 5)

  For each simulation:
    Record: (a) time buffer fires, (b) time actual settlement arrived
    Classify: buffer fired BEFORE actual settlement = acceptable
              buffer fired AFTER actual settlement = false buffer repayment risk

  Acceptance criterion:
    Buffer fires AFTER actual settlement in ≥ 90% of simulated cases
    (i.e., statistical buffer does not trigger before genuine settlement
    confirmation in more than 10% of cases)

  If criterion not met:
    Increase safety margins in affected tiers; re-test before Gate 2.1
```

### 17.4 Idempotency Stress Test

In all 5 tests below, exactly ONE `RepaymentInstruction` must appear in
`lip.repayment.instructions`. Any test producing 0 or >1 instructions fails.

```
Test A — Kafka at-least-once redelivery:
  Same camt.054 message delivered twice (simulated broker redelivery)
  Expected: message_id dedup catches duplicate at Flink level

Test B — Two channels fire within 100ms:
  camt.054 + FedNow ACSC both fire for same UETR within 100ms
  Expected: SETNX on first channel = 1 (proceeds); second = 0 (dropped)

Test C — Three channels fire within 1 second:
  camt.054 + FedNow + buffer timer all fire within 1 second
  Expected: first channel SETNX=1; second and third SETNX=0

Test D — Flink restart mid-processing:
  First settlement signal consumed; Flink job killed before checkpoint
  Restart: state restored from checkpoint; signal reprocessed from Kafka
  Expected: Redis dedup catches reprocessed signal; one instruction total

Test E — Redis write succeeds, Kafka produce fails:
  RepaymentInstruction produced to Kafka fails on first attempt; C3 retries
  Expected: Flink two-phase commit ensures exactly-once Kafka delivery;
            no duplicate instruction on retry
```

### 17.5 T = f(rejection\_code\_class) Completeness

```
For every code in the taxonomy table (Section 4.2, all 47 codes):
  [ ] Feed synthetic pacs.002 with that rejection_code to Job A
  [ ] Verify: correct class assigned (A / B / C)
  [ ] Verify: correct maturity_days assigned (3 / 7 / 21)
  [ ] Verify: rejection_code_class AND maturity_days both in DecisionLogEntry

Unknown code test (1 additional test case):
  [ ] Feed pacs.002 with rejection_code = "ZZ99" (not in taxonomy)
  [ ] Verify: class = UNKNOWN; maturity_days = 21
  [ ] Verify: taxonomy_status = "UNCLASSIFIED" in DecisionLogEntry
  [ ] Verify: "ZZ99" appears in unknown_rejection_code monitoring metric

Total required: 48 test cases. All must pass.
```

### 17.6 camt.054 Absence Test

This is the architectural proof that C3 does not depend on camt.054. Required before Gate.

```
Setup:
  Configure test corridor with camt.054 delivery disabled.
  Fund a loan on that corridor (ExecutionConfirmation sent to C3).
  Do NOT deliver any Channels 1–4 signals during loan lifetime.

Expected outcomes:
  [ ] Buffer timer fires at correct tier-appropriate P95 offset
  [ ] loan_state transitions: ACTIVE → BUFFER_REPAID (terminal)
  [ ] RepaymentInstruction generated:
        signal_source = "STATISTICAL_BUFFER"
        is_buffer_repayment = true
        buffer_p95_hours = tier P95 value used
  [ ] Soft alert fires: alert_type = "BUFFER_REPAYMENT_TRIGGERED"
  [ ] DecisionLogEntry: event_type = "BUFFER_REPAID", settlement_source = "STATISTICAL_BUFFER"
  [ ] DEFAULTED state is NOT declared (buffer fires before maturity expiry)
  [ ] Maturity timer cancelled after buffer fires

If any item fails: C3 has a dependency on camt.054. Do not proceed to Gate 2.1.
```

---

## 18. AUDIT GATE 2.1 CHECKLIST

Gate passes when ALL items are checked.
**NOVA signs.** LEX verifies claim language. FORGE verifies streaming integration.
REX verifies compliance hooks. CIPHER verifies idempotency adversarial tests.

### Settlement Signal Parsers
- [ ] Channel 1 (camt.054): 50+ real samples parsed; UETR-absent path tested; human_review routing confirmed
- [ ] Channel 2 (FedNow): 30+ samples; disambiguation from failure pacs.002 confirmed; no cross-contamination
- [ ] Channel 3 (RTP): 30+ samples; UETR mapping lookup tested; missing mapping → 3-retry → human_review confirmed
- [ ] Channel 4 (SEPA Instant): 30+ samples; INST/non-INST routing verified; non-INST never auto-triggers
- [ ] Channel 5 (Buffer): fires at correct offset; guard caps buffer before maturity in all 3 classes; soft alert fires

### Rejection Code Taxonomy
- [ ] All 47 taxonomy codes tested: correct class + maturity_days assignment confirmed
- [ ] UNKNOWN code path tested: Class C default; UNCLASSIFIED flag set; monitoring metric fires
- [ ] T = f(rejection_code_class) logged in every DecisionLogEntry (rejection_code_class AND maturity_days)
- [ ] Quarterly taxonomy review process documented (per Architecture Spec S11.6)

### State Machine
- [ ] All valid transitions tested and pass
- [ ] All forbidden/terminal transitions tested — error + alert confirmed (not silent)
- [ ] Zero undefined transition states under any input combination
- [ ] Terminal state overwrite attempt: blocked and alerted in all test scenarios

### Idempotency
- [ ] All 5 stress test scenarios pass (Section 17.4)
- [ ] Exactly one RepaymentInstruction per UETR in all test scenarios — no exceptions
- [ ] Flink exactly-once semantics verified under restart (Test D)
- [ ] Redis fail-safe deferred (not skipped) under Redis unavailability confirmed

### Corridor Buffer
- [ ] Backtesting completed on 5 corridor archetypes (Section 17.3)
- [ ] Buffer fires after actual settlement in ≥ 90% of simulated cases
- [ ] Guard invariant (buffer < maturity) verified across all 3 maturity classes
- [ ] 4-tier P95 computation verified with synthetic observation sets at tier boundaries
- [ ] Tier 0 corridor seed table built from public BIS/SWIFT GPI data (Section 16.5 enhancement)

### camt.054 Absence Test
- [ ] Corridor-without-camt.054 test passes end-to-end (Section 17.6 — all 7 items)
- [ ] BUFFER_REPAID state set; RepaymentInstruction correct; DEFAULTED NOT declared

### IP & Claim Language (LEX sign-off required)
- [ ] "individual_payment_id" + "uetr" present in all 5 parser output schemas
- [ ] "individual" + "UETR" explicit in RepaymentInstruction and DecisionLogEntry
- [ ] T = f(rejection_code_class) formalized (Section 4.3) and logged in every state transition
- [ ] Zero mentions of Recentive v. Fox anywhere in this document

### Integration Requirements
- [ ] Requirement 1 (outbound pacs.008) documented in C7 bank deployment guide
- [ ] RTP unmapped signal alert tested: fires on every unresolved UETR
- [ ] Human review routing confirmed for all unresolvable signals (zero silent drops)
- [ ] Integration test for outbound pacs.008 publication defined for C7 pilot onboarding

### DORA / EU AI Act (REX sign-off required)
- [ ] All state transitions logged to lip.state.transitions (7-year retention)
- [ ] DecisionLogEntry present for every REPAID, BUFFER_REPAID, and DEFAULTED event
- [ ] Any funded loan's full lifecycle reconstructable from logs alone (replay test: 3 loans)
- [ ] fee_usd calculated on actual days_funded (not maturity_days) — arithmetic verified

### Flink / Streaming Infrastructure (FORGE sign-off required)
- [ ] RocksDB state backend configured and tested under load
- [ ] Checkpoint interval: 10 seconds; checkpoint recovery tested (state restores correctly)
- [ ] Processing-time timer burst behavior on restart confirmed; grouped alert suppression working
- [ ] Kafka topic partition configuration: UETR as partition key on all relevant topics
- [ ] Dead letter topic (lip.dlq.parse_error) routing confirmed; alert threshold (0.1%) tested
- [ ] lip.payments.classified consumer lag: Decision Engine and C2 both consuming correctly

---

## OUTSTANDING ITEMS (NON-BLOCKING, FLAGGED)

**Item 1 — Provisional Spec v5.2 (LEX):**
Recentive v. Fox citation must be removed from Provisional-Specification-v5.1.md before it
becomes v5.2. Immutable standard violation in the current document. Non-blocking for C3 build;
blocking for any IP work on that document.

**Item 2 — Roadmap Status Update:**
BPI_Internal_Build_Validation_Roadmap_v1.0.md Phase 0 row still reads "IN PROGRESS."
Should be updated to "COMPLETE" — Architecture Spec v1.2 is fully signed off. Non-blocking.

**Item 3 — Corridor Seed Table (Section 16.5):**
Tier 0 buffer seeding from public BIS/SWIFT GPI data. Pre-Gate 2.1 enhancement.
NOVA to complete before gate submission.

**Item 4 — C7 Spec Pre-loads:**
Two C3 flags must be addressed in the C7 spec:
  - Section 6.3: outbound pacs.008 publication integration test requirement
  - Section 14, Req 1: bank deployment guide must specify and verify this contract
These are documented here; NOVA will lead C7 drafting next.

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026 | Lead: NOVA | Version: 1.0*
*Part 2 of 2 — see BPI_C3_Component_Spec_v1.0_Part1.md for Sections 1–9*
