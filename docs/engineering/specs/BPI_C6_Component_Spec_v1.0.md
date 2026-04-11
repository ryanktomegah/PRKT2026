# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 6 — AML VELOCITY MODULE
## Build Specification v1.0
### Phase 2 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** CIPHER — Security & AML Lead
**Support:** NOVA (Kafka/Redis integration), REX (FINTRAC/FinCEN/GDPR),
             QUANT (threshold arithmetic), ARIA (ML model honest ceiling),
             LEX (claim language), FORGE (latency validation)
**Status:** ACTIVE BUILD — Phase 2
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS

1.  Purpose & Scope
2.  Why C6 Is Architecturally Non-Negotiable
3.  Architecture Overview
4.  SHA-256 Borrower ID Hashing
    4.1 Design Rationale
    4.2 Hash Construction
    4.3 Three-Entity Hash Coverage
5.  Velocity Control Engine
    5.1 Velocity Dimensions
    5.2 Redis Velocity Schema
    5.3 Threshold Configuration
6.  Sanctions Screening
    6.1 Lists Maintained
    6.2 Screening Methodology
    6.3 Sanctions Match Handling
    6.4 List Refresh (Off Critical Path)
7.  Structuring Detection
    7.1 Regulatory Basis
    7.2 Detection Algorithm
    7.3 Structuring Detection Limitations (CIPHER flag)
8.  Isolation Forest Anomaly Detection
    8.1 Purpose in C6
    8.2 Feature Vector
    8.3 Model Training
    8.4 Model Versioning
9.  GraphSAGE Network Anomaly Detection
    9.1 Purpose
    9.2 Graph Construction
    9.3 GraphSAGE Inference
    9.4 Known Sanctioned Entity Proximity Check
10. VelocityResponse Schema
11. Critical Path Position & Latency Budget
12. Redis State Design
13. Kafka Integration
14. Adversarial Threat Model (CIPHER)
    14.1 Velocity Threshold Probing
    14.2 Hash Preimage Attack
    14.3 Entity Rotation to Evade Velocity Controls
    14.4 Bloom Filter False Positive Exploitation
15. Known Limitations
    15.1 Initial Model Quality
    15.2 Salt Rotation Window Gap
    15.3 Sanctions List Latency
    15.4 GraphSAGE Graph Sparsity at Launch
16. Validation Requirements
    16.1 Velocity Control Tests
    16.2 Sanctions Screening Tests
    16.3 Structuring Detection Tests
    16.4 Isolation Forest Tests
    16.5 GraphSAGE Tests
    16.6 Latency Tests (FORGE)
    16.7 Fail-Safe Tests
17. Audit Gate 2.3 Checklist

---

## 1. PURPOSE & SCOPE

C6 is the AML Velocity Module. It runs in the MIPLO critical path — after C1 and C2
produce their scores, before the Decision Engine generates a LoanOffer. Every payment
that reaches a bridge loan offer has been cleared by C6 first. Every payment that C6
hard-blocks never becomes an offer.

C6 owns five functions:

```
Function 1 — Velocity Controls
  Dollar velocity   : total USD lent to this borrower entity in rolling 24h / 7d / 30d
  Count velocity    : number of bridge loans to this borrower in rolling 24h / 7d / 30d
  Beneficiary conc. : % of total funded volume going to a single beneficiary entity

Function 2 — Sanctions Screening
  Real-time match against OFAC SDN, EU Consolidated, UN Security Council lists
  Per individual UETR — every offer, every time. No caching of a prior clearance.

Function 3 — Structuring Detection
  Identify sequences of payments designed to stay below reporting thresholds
  BSA 31 USC 5324 / FINTRAC PCMLTFA analog

Function 4 — Isolation Forest Anomaly Scoring
  Unsupervised outlier detection on transaction feature vectors
  Flags statistically anomalous transactions for additional scrutiny

Function 5 — GraphSAGE Network Anomaly Scoring
  Graph-based detection of suspicious entity relationship patterns
  Flags transactions where borrower or beneficiary sits within a known
  suspicious network topology
```

C6 does NOT:
- Make the lending decision (Decision Engine)
- Execute loans or repayments (C7)
- Score payment failure probability (C1)
- Estimate credit risk (C2)
- Classify commercial disputes (C4)
- Monitor settlement signals (C3)

**CIPHER Self-Critique Before Delivery:**
C6 is the component most likely to be probed adversarially. Every hard block rule C6
enforces is a potential bypass target. A sophisticated actor will study the velocity
thresholds, structure payments to stay below them, rotate entity identities, and use
legitimate-looking intermediaries to pass sanctions screening. This spec is written
with that adversary in mind. Every threshold, every hash design, every graph edge type
was chosen because an adversary will try to circumvent it. Where a bypass path exists
and is not fully closed, it is explicitly named — not buried.

---

## 2. WHY C6 IS ARCHITECTURALLY NON-NEGOTIABLE

Two failure modes in C6 have consequences that dwarf any other component failure:

**Failure Mode 1 — Sanctions miss:**
A bridge loan funded to a sanctioned entity is an OFAC violation. Penalties: up to
$1M per violation (civil), potential criminal exposure for individuals, and
correspondent banking relationship termination. A single miss can end the bank's
ability to operate in USD. C6 is the only automated control between an incoming
payment and a sanctions-matched borrower.

**Failure Mode 2 — Structuring facilitation:**
If C6's velocity controls are too coarse, a sophisticated actor can use the LIP to
bridge a series of sub-threshold payments that collectively constitute BSA structuring.
The bank becomes an unwitting instrument of money laundering. Regulatory consequence:
FinCEN enforcement action, potential deferred prosecution agreement.

Both failure modes share a design implication: **C6 must be fail-safe, not fail-open.**
If C6 is unavailable, ambiguous, or produces a malformed result — no offer is
generated. C7 enforces this: `c6_aml_result` absent or malformed = hard block.

This is the inversion of normal system design. Most components fail gracefully by
degrading capability. C6 fails by blocking everything. That is the correct behavior.

---

## 3. ARCHITECTURE OVERVIEW

```
C6 runs as a Flink streaming job within MIPLO infrastructure.

Input:  lip.payments.classified  (from C3 — UETR + rejection_class + amount + corridor)
        lip.aml.entity.updates   (sanctions list refresh events — off critical path)

Processing sequence (per UETR, in critical path):

  [1] SHA-256 Hash Resolution
       hashed_borrower_id    = SHA-256(BIC_sender   + "|" + currency + "|" + salt)
       hashed_beneficiary_id = SHA-256(BIC_receiver + "|" + currency + "|" + salt)
       No raw BIC or entity name stored in C6 state — ever.

  [2] Sanctions Screen
       Bloom filter pre-check -> if miss: CLEAR (~1ms, fast path)
       If bloom hit: full Tier 1 + Tier 2 scan (~5-10ms)

  [3] Velocity Checks
       Redis HINCRBY atomic increments on hashed entity keys
       Dollar velocity, count velocity, beneficiary concentration

  [4] Structuring Detection
       Pattern match on hashed_borrower_id recent transaction sequence

  [5] Isolation Forest Score
       Feature vector -> pre-loaded model -> anomaly_score (0.0-1.0)

  [6] GraphSAGE Score
       Hashed entity node -> pre-computed embedding lookup -> network_anomaly_score

  [7] VelocityResponse assembly
       Aggregate all signals -> hard_block determination -> publish

Output: lip.aml.results (consumed by MIPLO Decision Engine)

Decision Engine packages c6_aml_result into LoanOffer -> C7 enforces it.
C6 does not communicate directly with C7.
```

---

## 4. SHA-256 BORROWER ID HASHING

### 4.1 Design Rationale

C6 must track lending velocity and network anomalies per entity over days and weeks.
Storing raw BIC codes or entity names in a shared Redis cluster creates a PII/data
residency risk — SWIFT BICs are quasi-identifying for financial institutions, and
C6's Redis state could constitute a transaction surveillance database if leaked.

The SHA-256 hash design eliminates this risk: C6 never stores a raw BIC, entity
name, or account number. It stores only hashes. The hash is one-way — the Redis
state is useless to an attacker without the salt.

### 4.2 Hash Construction

```
hashed_borrower_id:
  input     = BIC8_sender + "|" + corridor_currency + "|" + salt
  algorithm = SHA-256
  output    = 64-char hex string (256-bit hash)
  stored as : "c6:entity:{hashed_borrower_id}"

hashed_beneficiary_id:
  input     = BIC8_receiver + "|" + corridor_currency + "|" + salt
  algorithm = SHA-256
  output    = 64-char hex string
  stored as : "c6:beneficiary:{hashed_beneficiary_id}"

Salt:
  Source    : bank KMS-managed secret (separate key slot from C7 HMAC key)
  Rotation  : quarterly (Architecture Spec S2.4 salt rotation schedule)
  On rotation: all existing C6 Redis keys invalidated (TTL or explicit flush)
               New hashes computed for subsequent transactions
               Velocity windows restart — accepted trade-off for salt rotation
               A 30d velocity window crossing a rotation boundary loses
               pre-rotation history. Documented limitation (Section 15.2).
  Bridgepoint has zero access to the salt value.
```

### 4.3 Three-Entity Hash Coverage

Architecture Spec S2.1 three-entity mapping (sender, receiver, intermediary)
requires hashing all three where present:

```
hashed_sender_id       = SHA-256(BIC8_sender      + "|" + currency + "|" + salt)
hashed_receiver_id     = SHA-256(BIC8_receiver     + "|" + currency + "|" + salt)
hashed_intermediary_id = SHA-256(BIC8_intermediary + "|" + currency + "|" + salt)
                         (empty string if no intermediary BIC in pacs.002)

All three hashes flow into velocity tracking and GraphSAGE node lookup.
```

---

## 5. VELOCITY CONTROL ENGINE

### 5.1 Velocity Dimensions

Three independent velocity controls, each independently capable of triggering
a hard block:

```
DIMENSION 1 — Dollar Velocity (per hashed borrower entity)

  v_dollar_24h  = total USD funded to hashed_borrower_id in rolling 24 hours
  v_dollar_7d   = total USD funded to hashed_borrower_id in rolling 7 days
  v_dollar_30d  = total USD funded to hashed_borrower_id in rolling 30 days

  Default thresholds (bank-configurable):
    hard_block_24h  : $5,000,000 USD
    hard_block_7d   : $15,000,000 USD
    hard_block_30d  : $40,000,000 USD
    review_24h      : $2,000,000 USD (soft flag — not a hard block)

DIMENSION 2 — Count Velocity (per hashed borrower entity)

  v_count_24h   = number of bridge loans to hashed_borrower_id in rolling 24h
  v_count_7d    = number of bridge loans in rolling 7d

  Default thresholds:
    hard_block_24h  : 50 loans
    hard_block_7d   : 200 loans
    review_24h      : 20 loans (soft flag)

DIMENSION 3 — Beneficiary Concentration (system-wide)

  concentration = (total_usd_to_hashed_beneficiary_30d /
                   total_usd_funded_system_30d) * 100

  Default thresholds:
    hard_block      : 15% (single beneficiary > 15% of all funded volume in 30d)
    review          :  8% (soft flag)

  Rationale: beneficiary concentration is a classic money laundering pattern.
  15% is conservative for a new platform — expected recalibration post-pilot
  based on actual portfolio distribution.
```

### 5.2 Redis Velocity Schema

All velocity state uses Redis Sorted Sets for O(log N) rolling window operations:

```
Dollar velocity (rolling window, per entity):
  Key:    "c6:vel:dollar:{hashed_borrower_id}:{window}"
          window = "24h" | "7d" | "30d"
  Type:   Redis Sorted Set
  Score:  funded_timestamp_utc (milliseconds) — for range eviction
  Member: "{loan_reference}:{amount_usd}"
  TTL:    window_duration + 1 hour (auto-cleanup buffer)

  Atomic operation (Lua script):
    ZADD   key {timestamp} "{ref}:{amount}"
    ZREMRANGEBYSCORE key 0 {now - window_ms}   // evict stale entries
    ZRANGE key 0 -1 WITHSCORES                 // fetch for sum
    Sum member amounts -> compare to threshold

Count velocity:
  Key:    "c6:vel:count:{hashed_borrower_id}:{window}"
  Type:   Redis Sorted Set (member = loan_reference, score = timestamp)
  TTL:    window_duration + 1 hour

Beneficiary concentration (system-wide rolling 30d):
  Key:    "c6:conc:beneficiary:{hashed_beneficiary_id}"
  Type:   Redis Sorted Set (same pattern)
  Key:    "c6:conc:system:total:30d"
  Type:   Redis Sorted Set (all funded events — denominator)
  TTL:    30d + 1 hour

All writes: Lua script for atomicity
  ZADD + ZREMRANGEBYSCORE + sum in single atomic operation
  Prevents race conditions between concurrent Flink task managers
```

### 5.3 Threshold Configuration

```
All thresholds: Kubernetes ConfigMap (bank-managed, C6 namespace)
Not secrets — velocity thresholds are governance policy, not cryptographic material

Change protocol:
  - Bank AML compliance officer sign-off (logged)
  - Pod restart required (no hot-reload for AML thresholds)
  - Change logged: event_type = "AML_THRESHOLD_CHANGED" in lip.decisions.log
                   fields: old_value, new_value, changed_by, timestamp_utc

Threshold floor enforcement (startup validation):
  hard_block_24h_dollar MUST be > review_24h_dollar
  hard_block_7d_dollar  MUST be > hard_block_24h_dollar
  hard_block_30d_dollar MUST be > hard_block_7d_dollar
  If misconfigured: C6 refuses to start.
  Threshold inversion cannot go silently undetected.
```

---

## 6. SANCTIONS SCREENING

### 6.1 Lists Maintained

```
List 1 — OFAC Specially Designated Nationals (SDN)
  Source  : US Treasury OFAC
  Format  : XML (sdn.xml) — downloaded and parsed offline
  Update  : Daily automated refresh (off critical path)
  Scope   : Individuals, entities, vessels, aircraft

List 2 — EU Consolidated Sanctions List
  Source  : European External Action Service
  Format  : XML
  Update  : Daily automated refresh

List 3 — UN Security Council Consolidated List
  Source  : UN 1267/1989/2253 Committee
  Format  : XML
  Update  : Daily automated refresh

Total list entries: ~15,000-25,000 entities (combined, deduplicated)
```

### 6.2 Screening Methodology

C6 screens BICs against list entries. The core challenge: OFAC SDN entries are
names, aliases, and addresses — not BIC codes. C6 cannot match a BIC directly to
an SDN name without a mapping layer. Resolution: two-tier screening.

```
Tier 1 — Direct BIC/LEI match:
  Bank-curated lookup table: BIC/LEI -> SDN/EU/UN status
  Built by bank compliance team from correspondent banking databases
  Updated quarterly (or on-demand for new designations)
  C6 checks this first.
  Match     : hard block, sanctions_match = true
  No match  : proceed to Tier 2

Tier 2 — Fuzzy name match:
  BIC -> legal entity name (via bank SWIFT BIC directory subscription)
  Legal entity name -> Jaro-Winkler similarity against SDN list
  Match threshold: similarity > 0.92
  (High threshold intentional — false positives are costly;
   Tier 1 catches known sanctioned banks;
   Tier 2 catches renamed/alias entities)
  Match     : hard block, sanctions_match = true
  No match  : CLEAR

Bloom filter pre-screen (performance optimization):
  All sanctioned BICs/names loaded into Bloom filter at C6 startup
  Bloom check   : ~1ms, zero false negatives (probabilistic FP only)
  Bloom miss    : CLEAR immediately — skip full scan
  Bloom hit     : run full Tier 1 + Tier 2 match (~5-10ms)
  Bloom rebuild : on each daily list update (full rebuild, not incremental)
  Target FP rate: < 0.01%
```

### 6.3 Sanctions Match Handling

```
On sanctions_match = true:
  hard_block      = true
  sanctions_match = true
  VelocityResponse published immediately — no further C6 processing

  UETR published to lip.aml.sar.queue (bank compliance system consumes)
    C6 surfaces the match. The bank files the SAR. C6 does not.

  DecisionLogEntry written by C7 on enforcement:
    event_type   = "HARD_BLOCK_C6"
    block_reason = "SANCTIONS_MATCH"
    matched_list : "OFAC_SDN" | "EU_CONSOLIDATED" | "UN_SECURITY_COUNCIL"
    match_tier   : "TIER1_DIRECT" | "TIER2_FUZZY"
    match_score  : float  // 1.0 for Tier 1; Jaro-Winkler score for Tier 2

  No human override permitted for sanctions_match = true.
  Immutable invariant. Not configurable. Not bypassable by any operator level.
```

### 6.4 List Refresh (Off Critical Path)

```
Daily refresh sequence:
  1. Scheduled job downloads updated XML files
  2. Parses and rebuilds: BIC/name lookup tables + Bloom filter
  3. Atomic swap: new structures replace old in C6 memory (zero downtime)
  4. Publishes to lip.aml.entity.updates (Flink refreshes in-memory state)
  5. Alert: "SANCTIONS_LIST_REFRESH_FAILED" if refresh fails
     Escalate to CRITICAL if refresh has not succeeded in > 48 hours
     (48h+ stale list is a compliance risk)

Manual override: bank compliance officer can force immediate refresh via
bank operator API — does not wait for scheduled cycle.

Emergency block list:
  "c6:emergency:blocks" Redis Set
  Bank compliance officer can add any hashed_entity_id immediately
  Checked at every transaction regardless of refresh schedule
  Bypasses the 24h list update lag for newly designated entities
```

---

## 7. STRUCTURING DETECTION

### 7.1 Regulatory Basis

Under the Bank Secrecy Act (31 USC 5324) and FINTRAC PCMLTFA, structuring is the
deliberate breakdown of transactions to avoid Currency Transaction Report filing
thresholds ($10,000 USD / $10,000 CAD). Cross-border bridge loans are not directly
subject to CTR filing — but if C6 detects that a borrower is using the LIP to bridge
a sequence of sub-threshold payments that aggregate to a structuring pattern, the
bank has a SAR obligation.

### 7.2 Detection Algorithm

```
Structuring signal: multiple loans to hashed_borrower_id where:

Condition A — Sub-threshold clustering:
  3 or more loans in 24h where each loan_amount_usd in [$8,000, $9,900]
  (within 1-20% below $10K threshold)

Condition B — Rapid repetition:
  5 or more loans to hashed_borrower_id in any 4-hour window
  with no single loan >= $10,000

Condition C — Sawtooth pattern:
  Loan amounts in rolling 7d show sawtooth pattern:
  alternating high/low where highs are consistently just below round numbers
  ($9,950, $49,800, $99,500, etc.)
  Detection: coefficient of variation on amount sequence +
             proximity-to-round-number score

Any Condition A OR B OR C:
  structuring_detected = true
  NOT a hard block by default
  soft_flag = true
  Publishes to lip.aml.sar.queue for bank review
  Bank decides: file SAR and/or block entity

Configurable escalation (bank-controlled):
  structuring_hard_block = true -> hard_block = true on structuring_detected
  Default: false
  Rationale: false positive rate for structuring detection is higher than
  sanctions screening. Default soft-flag allows human review without
  auto-blocking legitimate multi-payment corridors.
```

### 7.3 Structuring Detection Limitations (CIPHER flag)

```
Bypass path 1 — Salt rotation resets windows:
  Adversary who knows rotation schedule can structure across rotation boundary.
  Mitigation: unpredictable exact rotation date (+-7 days from scheduled).
  Does not eliminate bypass; reduces it.

Bypass path 2 — Entity rotation:
  Adversary uses different BIC senders per payment.
  C6 hashes per BIC — different senders = different hash keys.
  Mitigation: beneficiary concentration catches funneling into single receiver.
  True gap: C6 cannot detect distributed structuring from many unrelated senders
  to the same beneficiary unless concentration threshold fires.
  GraphSAGE co-occurrence edges are the secondary defense.

Bypass path 3 — Threshold learning:
  Adversary probes by observing which offers are declined.
  Mitigation: threshold values never surfaced in any API response.
  Residual risk: determined actor can binary-search thresholds over time.
  Partial mitigation: configure thresholds as ranges with random daily component
  (bank AML team decision — not default).
```

---

## 8. ISOLATION FOREST ANOMALY DETECTION

### 8.1 Purpose in C6

Isolation Forest is an unsupervised anomaly detection algorithm. It does not require
labeled fraud data — it identifies transactions that are statistical outliers in the
feature space. In C6, it serves as a catch-all for anomalies not captured by
rule-based velocity controls or sanctions screening.

It is NOT a hard block by itself at launch. It contributes `anomaly_score` to the
VelocityResponse. The bank's configurable threshold determines whether it triggers
a soft flag or hard block. Default at launch: soft flag only (Section 15.1).

### 8.2 Feature Vector

```
12 features per transaction (all normalized 0-1):

  f1  : amount_usd_normalized         log-scaled, normalized to 30d corridor mean
  f2  : corridor_novelty              1 - (corridor_tx_count_7d / max_corridor_count)
  f3  : velocity_ratio_24h            v_dollar_24h / hard_block_24h threshold
  f4  : velocity_ratio_7d             v_dollar_7d / hard_block_7d threshold
  f5  : count_velocity_ratio_24h      v_count_24h / count_hard_block_24h
  f6  : rejection_class_encoded       A=0.1, B=0.5, C=1.0, UNKNOWN=0.8
  f7  : hour_of_day_normalized        0-23 / 23
  f8  : day_of_week_normalized        0-6 / 6
  f9  : amount_round_number_score     proximity to $1K, $5K, $10K, $50K, $100K
  f10 : beneficiary_concentration_pct concentration_pct / hard_block_concentration
  f11 : pd_estimate                   from C2 (high PD + high amount = anomaly signal)
  f12 : inter_arrival_time_normalized time since last loan to borrower / 24h

Dense vector. No sparse encoding required.
```

### 8.3 Model Training

```
Algorithm    : IsolationForest
n_estimators : 200 trees
contamination: 0.01 (1% of training samples assumed anomalous)
               Recalibrated quarterly based on confirmed SAR outcomes

Training data:
  Initial  : synthetic transactions from historical corridor statistics
             (no real transaction data available at build time)
  Post-pilot: retrain on real data with SAR outcomes as labels
              SAR filed = confirmed anomaly -> informs contamination parameter
  Cadence  : quarterly (aligned with C2 and C4 retraining)

Scoring:
  Model pre-loaded at startup (serialized ONNX or joblib)
  Inference : ~2ms on CPU (12-feature dense vector)
  Output    : anomaly_score in [0.0, 1.0]
               > 0.7 : anomaly_detected = true (soft flag)
               > 0.9 : hard_block eligible if bank_config.anomaly_hard_block = true

ARIA flag: Synthetic training data produces high initial false positive rate.
contamination parameter must be tuned post-pilot on real data.
Default: soft-flag only at launch. Hard-block config is post-pilot only.
Committing to anomaly_score hard-block thresholds before real data is premature.
```

### 8.4 Model Versioning

```
model_version_c6 logged in every VelocityResponse and C7 DecisionLogEntry.
Model updates follow same bank-controlled deployment protocol as C4:
  - Bank reviews and approves model file (hash-verified)
  - Bank uploads to bank-controlled storage
  - Bank schedules pod restart
  - Bridgepoint cannot push updates without bank consent
```

---

## 9. GRAPHSAGE NETWORK ANOMALY DETECTION

### 9.1 Purpose

Velocity controls and sanctions screening are entity-level checks. GraphSAGE is a
network-level check: it asks whether the transaction involves entities that sit within
a suspicious graph topology — even if each individual entity passes all rule-based
checks.

Classic example: a borrower entity that individually passes all velocity and sanctions
checks, but is a second-degree neighbor of a known sanctioned entity in the payment
network graph. No rule-based system catches this. GraphSAGE does.

### 9.2 Graph Construction

```
Node types:
  BANK_ENTITY      : hashed BIC (sender, receiver, intermediary)
  CORRIDOR         : BIC_pair + currency (e.g., "BARCGB22_CITIUS33_USD")
  REJECTION_CLASS  : A | B | C | UNKNOWN (shared node)
  TIME_BUCKET      : hour-of-day (0-23) — temporal pattern node

Edge types:
  SENT_ON_CORRIDOR     : BANK_ENTITY -> CORRIDOR (sender)
  RECEIVED_ON_CORRIDOR : BANK_ENTITY -> CORRIDOR (receiver)
  FAILED_WITH_CLASS    : CORRIDOR -> REJECTION_CLASS
  ACTIVE_IN_BUCKET     : CORRIDOR -> TIME_BUCKET
  CO_OCCURRED_WITH     : BANK_ENTITY -> BANK_ENTITY
    (edge exists if sender + receiver appear together >= 3 times in 30d)

Scale per bank (estimated):
  Nodes : ~10,000-50,000
  Edges : ~100,000-500,000
  Memory: ~500MB-2GB depending on corridor volume

Updates: incremental on each funded transaction
  New edge added or edge weight incremented
  Graph persisted in Redis as adjacency list (Section 12)
  Full rebuild: weekly (off critical path)
```

### 9.3 GraphSAGE Inference

```
Algorithm : GraphSAGE (Hamilton et al., 2017) — inductive representation learning
            Node embeddings from 2-hop neighborhood aggregation

Critical path design: pre-computed embeddings (Option A)
  At inference time: look up pre-computed 64-dimensional embedding from Redis
  Latency: ~2ms (Redis GET vs. ~10-15ms live inference)
  Fallback: if embedding absent -> run live GraphSAGE (~10-15ms)
  Post-fallback: write embedding to Redis for future lookups
  Embedding TTL: 7d (recomputed on next transaction involving entity)

Anomaly scoring:
  network_anomaly_score = cosine_distance(embedding, normal_centroid)
  normal_centroid computed during training; stored as model artifact
  Range: [0.0, 1.0] where 1.0 = maximally distant from normal cluster

  > 0.65 : network_anomaly_detected = true (soft flag)
  > 0.85 : contributes to hard_block consideration if bank configured

ARIA flag: GraphSAGE embeddings on sparse initial graph have low
discriminative power. normal_centroid poorly calibrated before real data
accumulates. Useful signal expected only after ~6 months of production.
Advisory-only posture at launch (same as Isolation Forest).
```

### 9.4 Known Sanctioned Entity Proximity Check

```
If any node in 2-hop neighborhood of hashed_borrower_id or
hashed_beneficiary_id is a known sanctioned entity (from Tier 1 or
Tier 2 match history):

  sanctions_proximity = true
  NOT a hard block by default
  Soft flag -> bank compliance enhanced due diligence
  Bank can configure sanctions_proximity = true to trigger hard_block

Rationale: second-degree neighbor of a sanctioned entity does not constitute
a violation. It is a risk signal warranting EDD. Auto-blocking on proximity
would have prohibitive false positive rates in concentrated correspondent
banking corridors where many entities route through the same 1-2 major banks.
```

---

## 10. VELOCITYRESPONSE SCHEMA

Authoritative schema. C7 enforces every field. Decision Engine reads every field.

```
VelocityResponse {
  uetr                     : string   // individual UETR
  individual_payment_id    : string   // explicit individual identifier
  hashed_borrower_id       : string   // SHA-256 hash (not raw BIC)
  hashed_beneficiary_id    : string   // SHA-256 hash (not raw BIC)

  // AGGREGATE RESULT
  hard_block               : bool     // true if ANY hard block condition met
  soft_flag                : bool     // true if any review-level signal present

  // SANCTIONS
  sanctions_match          : bool
  matched_list             : string   // "OFAC_SDN" | "EU_CONSOLIDATED" |
                                      //  "UN_SECURITY_COUNCIL" | "NONE"
  match_tier               : string   // "TIER1_DIRECT" | "TIER2_FUZZY" | "NONE"
  match_confidence         : float    // 1.0 Tier 1; Jaro-Winkler score Tier 2
  sanctions_proximity      : bool     // 2-hop neighbor of sanctioned entity

  // VELOCITY
  velocity_dollar_24h      : double
  velocity_dollar_7d       : double
  velocity_dollar_30d      : double
  velocity_count_24h       : int32
  velocity_count_7d        : int32
  velocity_dollar_exceeded : bool
  velocity_count_exceeded  : bool
  velocity_window_hit      : string   // "24H" | "7D" | "30D" | "NONE"

  // BENEFICIARY CONCENTRATION
  beneficiary_conc_pct     : float
  beneficiary_conc_exceeded: bool

  // STRUCTURING
  structuring_detected     : bool
  structuring_condition    : string   // "A" | "B" | "C" | "NONE"

  // ANOMALY
  anomaly_score            : float    // Isolation Forest [0.0-1.0]; -1.0 if unavailable
  anomaly_detected         : bool
  network_anomaly_score    : float    // GraphSAGE [0.0-1.0]; -1.0 if unavailable
  network_anomaly_detected : bool

  // METADATA
  model_version_c6         : string   // IF + GraphSAGE versions
  sanctions_list_version   : string   // date of most recent list refresh
  processing_time_ms       : int32
  timestamp_utc            : int64
}
```

**Hard block trigger logic:**
```
hard_block = true if ANY of:
  sanctions_match = true
  velocity_dollar_exceeded = true
  velocity_count_exceeded = true
  beneficiary_conc_exceeded = true
  (anomaly_detected = true AND bank_config.anomaly_hard_block = true)
  (structuring_detected = true AND bank_config.structuring_hard_block = true)

soft_flag = true if ANY of:
  structuring_detected = true
  anomaly_detected = true
  network_anomaly_detected = true
  sanctions_proximity = true
  velocity_dollar_24h > review_24h threshold
  velocity_count_24h  > review_24h count threshold
  beneficiary_conc_pct > review_concentration threshold
```

**C7 fail-safe enforcement:**
```
If VelocityResponse is absent or malformed:
  C7 treats as hard_block = true, sanctions_match = false
  Decline reason: "C6_RESULT_ABSENT"
  No offer generated. No exceptions.
```

---

## 11. CRITICAL PATH POSITION & LATENCY BUDGET

C6 is on the MIPLO critical path. Architecture Spec S10.1 end-to-end p50 target
is ~26ms from SWIFT receipt to offer generation. C6's share:

```
Critical path breakdown (p50):
  C1 inference   : ~8ms    (GNN + TabTransformer on GPU)
  C2 inference   : ~6ms    (LightGBM on CPU)
  C6 AML checks  : ~8ms    (target)
  Decision Engine: ~4ms
  Total          : ~26ms

C6 internal latency budget:

  Step                              Fast path   Bloom-hit path
  SHA-256 hash computation          0.1ms        0.1ms
  Bloom filter check                1.0ms        1.0ms
  Sanctions full scan (on hit)      —            5-10ms
  Velocity Redis reads (pipelined)  2.0ms        2.0ms
  Structuring pattern check         1.0ms        1.0ms
  Isolation Forest scoring          2.0ms        2.0ms
  GraphSAGE (pre-computed Redis)    2.0ms        2.0ms
  VelocityResponse assembly         0.2ms        0.2ms
                                    -------      --------
  Total                             ~8ms         ~18ms

p50 target: 8ms  — achievable on fast path (bloom miss)
p99 target: 20ms — achievable with pre-computed GraphSAGE embeddings

NOVA flag: GraphSAGE live inference (~10-15ms) would push p99 above 20ms
on large graphs. Pre-computed embedding option (Section 9.3) is mandatory
for latency compliance. Validation required at Gate 2.3.
```

---

## 12. REDIS STATE DESIGN

```
Velocity state (rolling windows):
  "c6:vel:dollar:{hashed_borrower_id}:24h"     Sorted Set, TTL 25h
  "c6:vel:dollar:{hashed_borrower_id}:7d"      Sorted Set, TTL 8d
  "c6:vel:dollar:{hashed_borrower_id}:30d"     Sorted Set, TTL 31d
  "c6:vel:count:{hashed_borrower_id}:24h"      Sorted Set, TTL 25h
  "c6:vel:count:{hashed_borrower_id}:7d"       Sorted Set, TTL 8d
  "c6:conc:beneficiary:{hashed_beneficiary_id}" Sorted Set, TTL 31d
  "c6:conc:system:total:30d"                   Sorted Set, TTL 31d

Sanctions state:
  "c6:sanctions:bic:{hashed_bic}"              String: "OFAC_SDN"|"EU"|"UN"
  "c6:sanctions:bloom"                         String: serialized Bloom filter
  "c6:emergency:blocks"                        Set: hashed_entity_ids (no TTL)
  TTL for sanctions lookup: none (refreshed daily)

GraphSAGE pre-computed embeddings:
  "c6:graph:emb:{hashed_entity_id}"            String: 64-float binary/JSON
  TTL: 7d (recomputed on next transaction involving entity)

Structuring detection state:
  "c6:struct:{hashed_borrower_id}:recent"      Sorted Set
    Score  : funded_timestamp_utc
    Member : "{loan_reference}:{amount_usd}"
  TTL: 7d

SAR queue:
  "c6:sar:queue"                               Redis List (LPUSH/BRPOP)
  Items: {uetr, hashed_borrower_id, trigger_type, timestamp}
  No TTL (compliance system responsible for processing)
```

---

## 13. KAFKA INTEGRATION

```
CONSUMED BY C6:
  lip.payments.classified  UETR + rejection_class + amount + corridor (from C3)
  lip.aml.entity.updates   Sanctions list refresh events (off critical path)

PRODUCED BY C6:
  lip.aml.results          VelocityResponse -> Decision Engine
  lip.aml.sar.queue        SAR candidates -> bank compliance system
  lip.decisions.log        C6 block events (hard blocks)
  lip.alerts               Sanctions list staleness, velocity anomalies

Topic partitioning:
  lip.payments.classified : partitioned by UETR (C3 guarantees)
  lip.aml.results         : partitioned by UETR (matches input)
  Partition alignment ensures C6 output reaches Decision Engine in UETR order.

Consumer group: lip-aml-c6
  Single consumer group ensures no duplicate C6 processing per UETR
```

---

## 14. ADVERSARIAL THREAT MODEL (CIPHER)

This section exists because a sophisticated adversary studies the spec.
Every known bypass path at build time is documented here — not buried.

### 14.1 Velocity Threshold Probing

**Attack:** Actor sends small-amount loans across sessions to infer velocity
thresholds by observing which offers are blocked.

**C6 response:** Decline reason = `"HARD_BLOCK_C6"` — no threshold details surfaced.
Amount triggering the block is never published.

**Residual risk:** Determined actor with enough probing attempts can binary-search
to the threshold over time.

**Mitigation (bank AML team decision):** Configure thresholds as ranges with a random
daily component (e.g., 24h dollar threshold = $5M +/- random($0, $200K) per entity,
resampled daily). Not default — bank compliance team decision.

### 14.2 Hash Preimage Attack

**Attack:** Reverse-engineer SHA-256 hashes in Redis to identify tracked entities.

**C6 response:** SHA-256 with KMS-managed salt is computationally infeasible to
reverse (2^256 preimage resistance under current cryptographic assumptions).

**Residual risk:** Salt leak via KMS compromise makes all hashes reversible.
**Mitigation:** Salt is bank-controlled KMS. Bridgepoint has no access. Risk sits
entirely within the bank's KMS security posture.

### 14.3 Entity Rotation to Evade Velocity Controls

**Attack:** Different sender BIC per loan; per-entity velocity stays low.

**C6 response:** Beneficiary concentration catches funneling to single receiver
regardless of how many senders are used.

**True gap:** Fully distributed structuring (sender AND receiver rotate, no
co-occurrence pattern) evades C6. This is an industry-wide AML limitation.

### 14.4 Bloom Filter False Positive Exploitation

**Attack:** Flood C6 with transactions that trigger Bloom filter false positives,
causing expensive Tier 2 lookups and degrading p99 latency.

**C6 response:** Bloom FP rate < 0.01%. At 10K TPS: ~1 false positive/second.
Manageable. Rate limiting on per-entity offer frequency provides secondary defense.

---

## 15. KNOWN LIMITATIONS

### 15.1 Initial Model Quality

Both Isolation Forest and GraphSAGE are trained on synthetic data at launch.
Discriminative power is limited before real transaction data accumulates.
ARIA is explicit: both models are soft-flag-only at launch. Hard-block configuration
for ML-based signals should not be activated until post-pilot retraining on real data
with confirmed SAR outcomes.

### 15.2 Salt Rotation Window Gap

Quarterly salt rotation resets all rolling velocity windows. An adversary with
knowledge of rotation timing can structure payments across the rotation boundary.
Partial mitigation: rotation date randomization (+/-7 days from scheduled date).

### 15.3 Sanctions List Latency

Daily refresh means C6 operates on a list up to 24 hours old. A newly sanctioned
entity could receive a bridge loan in the interval between designation and next refresh.
This is an industry-standard limitation — real-time OFAC API is not publicly available.

**Mitigation:** Emergency block list (`c6:emergency:blocks`) allows bank compliance
to add any entity immediately, bypassing the daily refresh cycle.

### 15.4 GraphSAGE Graph Sparsity at Launch

Transaction graph will be sparse at pilot launch. GraphSAGE embeddings on a sparse
graph provide weak signal. Expected: useful GraphSAGE signal only after ~6 months
of production transaction data.

---

## 16. VALIDATION REQUIREMENTS

### 16.1 Velocity Control Tests

```
Dollar velocity hard block:
  [ ] Fund loans to hashed_borrower_id totaling (24h_threshold - $1)
  [ ] Fund one more pushing total to (24h_threshold + $1)
  [ ] Verify: hard_block = true, velocity_dollar_exceeded = true,
              velocity_window_hit = "24H"
  [ ] Repeat for 7d and 30d thresholds

Count velocity hard block:
  [ ] Same pattern for count thresholds at 24h and 7d boundaries

Beneficiary concentration:
  [ ] Fund system total to $10M; fund $1.5M+$1 to single beneficiary
  [ ] Verify: beneficiary_conc_exceeded = true, hard_block = true at 15% threshold

Rolling window eviction:
  [ ] Fund to 90% of 24h threshold at T=0
  [ ] Advance time by 25h (evict all T=0 transactions)
  [ ] Fund same amount at T+25h
  [ ] Verify: window correctly evicted; new 24h balance = new amount only
  [ ] No false block from stale window data

Threshold misconfiguration (startup guard):
  [ ] Configure hard_block_24h_dollar < review_24h_dollar
  [ ] Verify: C6 refuses to start; error logged
```

### 16.2 Sanctions Screening Tests

```
Tier 1 direct match:
  [ ] Add test BIC to bank Tier 1 lookup table
  [ ] Feed transaction with that BIC as sender
  [ ] Verify: sanctions_match = true, match_tier = "TIER1_DIRECT", hard_block = true

Tier 2 fuzzy match:
  [ ] Add "Acme Bank Ltd" to SDN list equivalent
  [ ] Feed transaction where BIC maps to "Acme Bank Limited"
  [ ] Verify: Jaro-Winkler > 0.92 triggers match, match_tier = "TIER2_FUZZY"
  [ ] Feed transaction where name is "Acme Corp"
  [ ] Verify: Jaro-Winkler < 0.92 -> no match

Bloom filter:
  [ ] Verify: bloom miss produces CLEAR without full scan
  [ ] Verify: bloom hit triggers full scan
  [ ] Verify: false positive rate < 0.01% over 10,000 test transactions

Emergency block list:
  [ ] Add hashed_entity_id to c6:emergency:blocks
  [ ] Feed transaction from that entity
  [ ] Verify: hard_block = true without waiting for daily refresh

Sanctions list staleness:
  [ ] Simulate refresh failure for 48h
  [ ] Verify: "SANCTIONS_LIST_REFRESH_FAILED" escalates to CRITICAL at 48h

Override attempt:
  [ ] Attempt human override of sanctions_match = true block via C7
  [ ] Verify: rejected — immutable block, no operator can override
```

### 16.3 Structuring Detection Tests

```
Condition A:
  [ ] Feed 3 loans at $9,500 / $9,700 / $9,850 to same borrower within 24h
  [ ] Verify: structuring_detected = true, structuring_condition = "A"
  [ ] Verify: published to lip.aml.sar.queue
  [ ] Verify: hard_block = false (default), soft_flag = true

  [ ] Feed 3 loans at $9,500 / $9,700 / $12,000 (one above $10K)
  [ ] Verify: structuring_detected = false (Condition A not met)

Condition B:
  [ ] Feed 5 loans < $10K each within 4-hour window to same borrower
  [ ] Verify: structuring_detected = true, structuring_condition = "B"

Default behavior:
  [ ] Verify: hard_block = false unless bank configures structuring_hard_block = true
```

### 16.4 Isolation Forest Tests

```
Normal transaction:
  [ ] Feed transaction with all features near corridor mean
  [ ] Verify: anomaly_score < 0.5, anomaly_detected = false

Outlier transaction:
  [ ] Feed: amount 10x corridor mean, off-hours, new corridor,
            high pd_estimate, round number amount ($99,500)
  [ ] Verify: anomaly_score > 0.7, anomaly_detected = true, soft_flag = true
  [ ] Verify: hard_block = false (default, pre-pilot)

Model unavailable:
  [ ] Remove IF model at startup
  [ ] Verify: C6 starts; anomaly_score = -1.0; sanctions + velocity still function

Model version logged:
  [ ] Verify: model_version_c6 present in every VelocityResponse
```

### 16.5 GraphSAGE Tests

```
Pre-computed embedding path:
  [ ] Verify: embedding served from Redis when available (~2ms)
  [ ] Verify: live inference runs when embedding absent (~10-15ms)
  [ ] Verify: embedding written to Redis after live inference

Sanctioned neighbor (2-hop):
  [ ] Build test graph: sanctioned A -> intermediary B -> borrower C
  [ ] Feed transaction from C
  [ ] Verify: sanctions_proximity = true, soft_flag = true, hard_block = false

Model unavailable:
  [ ] Remove GraphSAGE model at startup
  [ ] Verify: C6 starts; network_anomaly_score = -1.0; other functions intact
```

### 16.6 Latency Tests (FORGE)

```
[ ] p50 C6 processing time <= 8ms  at 1,000 concurrent transactions
[ ] p99 C6 processing time <= 20ms at 1,000 concurrent transactions
[ ] p99 < 50ms at 10,000 concurrent transactions (degraded but functional)
[ ] GraphSAGE pre-computed embedding: p99 < 5ms for Redis lookup path
[ ] Velocity Redis pipelined reads: p99 < 3ms for all 3 windows combined
[ ] Sanctions Bloom filter miss path: p99 < 2ms
[ ] Full path with bloom hit (Tier 1 + Tier 2): p99 < 15ms
```

### 16.7 Fail-Safe Tests

```
[ ] Redis unavailable:
    Verify: VelocityResponse.hard_block = true (fail-safe, not fail-open)
    Rationale: velocity state unreadable = cannot confirm entity is safe

[ ] Sanctions Bloom filter empty (startup failure):
    Verify: hard_block = true; C6 does not start in degraded open mode

[ ] Isolation Forest not loaded:
    Verify: C6 starts; anomaly_score = -1.0; sanctions + velocity function

[ ] GraphSAGE not loaded:
    Verify: C6 starts; network_anomaly_score = -1.0; other functions intact

[ ] VelocityResponse publish failure to lip.aml.results (Kafka unavailable):
    Retry 3x; if all fail: publish hard_block = true to ensure C7 blocks
    Verify: a missing AML result is NEVER treated as implicit clearance

[ ] C6_RESULT_ABSENT at C7 (simulate missing VelocityResponse):
    Verify: C7 treats as hard_block = true, decline_reason = "C6_RESULT_ABSENT"
```

---

## 17. AUDIT GATE 2.3 CHECKLIST

Gate passes when ALL items are checked.
**CIPHER signs.** NOVA verifies Kafka/Redis. REX verifies regulatory compliance.
QUANT verifies threshold arithmetic. ARIA verifies ML honest ceiling.
LEX verifies claim language.

### SHA-256 Hashing
- [ ] No raw BIC or entity name stored anywhere in C6 Redis state — verified
- [ ] Hash construction: same input + same salt = same output; different salt = different — tested
- [ ] Three-entity hashing (sender, receiver, intermediary) implemented
- [ ] Salt in bank KMS only; Bridgepoint has no access — architecture verified
- [ ] Salt rotation: window resets documented as known limitation; behavior tested

### Velocity Controls
- [ ] Dollar velocity boundary tests pass for 24h, 7d, 30d thresholds
- [ ] Count velocity boundary tests pass for 24h, 7d thresholds
- [ ] Beneficiary concentration test passes at 15% threshold
- [ ] Rolling window eviction test: stale transactions correctly excluded
- [ ] Threshold inversion guard tested: C6 refuses to start if misconfigured
- [ ] Threshold change logged: "AML_THRESHOLD_CHANGED" in decisions.log

### Sanctions Screening
- [ ] Tier 1 direct match test passes
- [ ] Tier 2 fuzzy match at Jaro-Winkler > 0.92 fires; < 0.92 does not
- [ ] Bloom filter FP rate < 0.01% over 10K test transactions — confirmed
- [ ] Emergency block list bypasses daily refresh — tested
- [ ] Sanctions list staleness CRITICAL alert fires at 48h — tested
- [ ] sanctions_match = true: hard block, no human override — immutable, verified
- [ ] Override attempt rejected — tested

### Structuring Detection
- [ ] Condition A test passes
- [ ] Condition B test passes
- [ ] Default: soft_flag = true, hard_block = false — verified
- [ ] SAR queue publishing confirmed for every structuring_detected = true event

### Isolation Forest (ARIA sign-off required)
- [ ] Synthetic training documented; initial quality limitation acknowledged
- [ ] anomaly_score = -1.0 when model unavailable; C6 continues — tested
- [ ] model_version_c6 in every VelocityResponse
- [ ] Soft-flag-only posture at launch; hard-block config post-pilot only — confirmed
- [ ] Quarterly retraining plan documented

### GraphSAGE (ARIA sign-off required)
- [ ] Pre-computed embedding Redis path: p99 < 5ms — tested
- [ ] Live inference fallback: p99 < 15ms — tested
- [ ] Sanctioned neighbor 2-hop detection test passes
- [ ] Advisory-only posture at launch; graph sparsity limitation documented
- [ ] network_anomaly_score = -1.0 when model unavailable; C6 continues — tested

### Latency (FORGE sign-off required)
- [ ] p50 <= 8ms at 1,000 concurrent — load test passes
- [ ] p99 <= 20ms at 1,000 concurrent — load test passes
- [ ] p99 < 50ms at 10,000 concurrent — load test passes
- [ ] Pre-computed embedding confirmed as mandatory for latency compliance

### Fail-Safe Behavior (CIPHER sign-off required)
- [ ] Redis unavailable -> hard_block = true (not fail-open) — tested
- [ ] Sanctions list empty -> hard_block = true — tested
- [ ] VelocityResponse publish failure -> retry 3x -> hard_block = true — tested
- [ ] C6_RESULT_ABSENT at C7 -> hard_block = true — tested (C7 test)
- [ ] All 4 adversarial threat model scenarios tested; behavior documented

### Regulatory Compliance (REX sign-off required)
- [ ] SAR queue publishing: every structuring_detected and sanctions_match event surfaces to bank
- [ ] Bank compliance SAR processor consuming lip.aml.sar.queue — integration verified
- [ ] No PII in any C6 Redis key or Kafka message — all entity refs are SHA-256 hashes
- [ ] GDPR Art.28: C6 processes no personal data (BICs are institutional identifiers) — confirmed
- [ ] FinCEN/FINTRAC structuring detection documented; bank SAR obligation correctly surfaced
- [ ] OFAC sanctions liability: two-tier screening documented in bank AML program materials

### IP & Claim Language (LEX sign-off required)
- [ ] "individual_payment_id" + "uetr" explicit in VelocityResponse — individual identifier present
- [ ] model_version_c6 in every VelocityResponse (audit trail continuity)
- [ ] Zero mentions of Recentive v. Fox in this document

---

*C6 Build Specification v1.0 complete. One file — no split required.*
*Audit Gate 2.3 checklist locked.*
*Next: C5 (FORGE leads — infrastructure consolidation).*
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: CIPHER | Support: NOVA, REX, QUANT, ARIA, LEX, FORGE*
