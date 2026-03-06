# BRIDGEPOINT INTELLIGENCE INC.
## ARCHITECTURE OPEN QUESTIONS — RESOLUTION RECORD v1.0
### Phase 0 — Internal Use Only

**Date:** March 4, 2026
**Status:** RESOLVED — Pending Confirmation
**Source:** Architecture Specification v1.0, Section 11
**Authors:** ARIA, NOVA, CIPHER, REX, FORGE, QUANT, LEX

---

## PURPOSE

This document resolves all 8 open design questions raised in
Architecture Specification v1.0 Section 11. Once confirmed, these
resolutions are locked into Architecture Specification v1.1 and
become binding engineering standards for all phases.

---

## Q1: GPU vs CPU INFERENCE DECISION
**Owner:** FORGE + ARIA | **Priority:** CRITICAL

### Question
Confirm hardware spec for C1 (GNN + TabTransformer) inference
and define autoscaling trigger metric.

### Analysis (ARIA)

CPU-only is not viable for production SLA with margin:
- C1 on CPU: p50 ~80ms, p99 ~150ms
- Total critical path on CPU: p50 ~86ms, p99 ~163ms
- This is technically within targets but leaves zero headroom
- Any traffic spike, model complexity increase, or cold start
  will breach p50 <100ms — unacceptable for a production SLA

GPU provides the required margin:
- C1 on GPU (T4 class): p50 ~20ms, p99 ~40ms
- Total critical path on GPU: p50 ~26ms, p99 ~51ms
- 4x headroom on p50, nearly 4x on p99

### Throughput Analysis (FORGE)

At 10K TPS with micro-batching (batch size 32, max wait 5ms):
- Each batch: 32 payments * ~20ms GPU inference = 1,600 TPS per GPU
- For 10K TPS sustained: ceil(10,000 / 1,600) = 7 GPUs minimum
- With 25% headroom: 9 GPUs for steady-state 10K TPS
- For 50K TPS peak: ~40 GPUs (autoscaled)

### Resolution

**Hardware standard:** NVIDIA T4 (minimum) or A10G (preferred)
per inference node. GPU inference is a hard infrastructure
requirement for C1. CPU deployment is explicitly a degraded mode
only — never the primary path.

**Autoscaling trigger:** Kubernetes HPA on inference queue depth.
- Scale-out trigger: queue depth > 100 pending requests per node
- Scale-in trigger: queue depth < 20 per node for 5 minutes
- Min nodes: 2 (HA baseline)
- Max nodes: 50 (50K TPS peak coverage)
- Do NOT use CPU/memory as primary autoscaling metric for ML nodes

**Model serving:** NVIDIA Triton Inference Server
- Dynamic batching: max batch size 32, max wait 5ms
- Multiple model instances per GPU (where memory permits)
- Health check: inference latency p99, not just HTTP 200

**Degraded mode behavior (FORGE):**
If all GPU nodes fail, system falls back to CPU serving.
CPU degraded mode MUST:
1. Alert immediately (PagerDuty equivalent)
2. Log every decision as "DEGRADED_MODE_CPU" in decision log
3. Continue serving — do not halt (a slow bridge is better than none)
4. Auto-recover when GPU nodes available (no manual intervention)

**Self-critique (ARIA):** T4 throughput estimate assumes GNN graph
size of ~500 nodes (BIC-pair network). If production graph grows
to 5,000+ nodes, T4 inference time may double. Graph size must be
monitored and A10G upgrade path pre-planned.

---

## Q2: RTP UETR MAPPING TABLE
**Owner:** NOVA | **Priority:** HIGH

### Question
RTP does not natively carry UETR. Define Redis schema for
EndToEndID to UETR resolution.

### Analysis (NOVA)

RTP uses EndToEndId (ISO 20022 field) as its primary transaction
reference. SWIFT assigns UETR at payment initiation. When a
cross-border payment terminates on US domestic RTP rails, the
settlement confirmation carries EndToEndId, not UETR.

The mapping must be populated BEFORE the payment could possibly
fail — meaning at payment initiation, not failure detection.
The hook point is the outbound pacs.008 (credit transfer initiation)
that contains both UETR and EndToEndId.

If the mapping is not populated before a failure is detected,
RTP settlement signals cannot be matched to funded loans.
This is a race condition that must be architecturally eliminated.

### Resolution

**Redis Schema:**

```
Key:   "rtp:e2e:{EndToEndId}"
Type:  Redis HASH
TTL:   maturity_days + 45 days (max = 21 + 45 = 66 days)

Fields:
  uetr          : string   # SWIFT UETR
  corridor      : string   # e.g. "EUR_USD_FEDNOW"
  amount_usd    : float    # Original instructed amount
  created_at    : int64    # Unix ms — population timestamp
  rail          : string   # "RTP" or "FEDNOW" (shared table)
```

**Population trigger:**
Outbound pacs.008 event on Kafka topic `lip.payments.outbound`
populates the mapping table atomically before payment enters
MONITORING state.

**Sequencing guarantee:**
Flink consumer must process `lip.payments.outbound` BEFORE
`lip.payments.raw` for the same UETR. Enforce via:
- Kafka partition key = UETR (same partition, ordered)
- Flink processing order: outbound > raw per UETR

**FedNow note:** FedNow uses the same ISO 20022 pacs.002 as SWIFT
and does carry UETR in TxInfAndSts/OrgnlUETR — no mapping table
needed for FedNow. Only RTP requires this table.

**Monitoring:** Alert if RTP settlement signal arrives with no
matching UETR in mapping table. This indicates a gap in outbound
payment capture — must be investigated immediately.

---

## Q3: SALT ROTATION PROTOCOL FOR SHA-256 HASHING
**Owner:** CIPHER | **Priority:** HIGH

### Question
Define salt rotation frequency and key migration path for
SHA-256(tax_id + salt) borrower identifiers.

### Analysis (CIPHER)

Salt rotation breaks cross-licensee velocity continuity.
If Entity X had hash H1 under salt S1, and salt rotates to S2,
Entity X gets hash H2. Velocity counters for H1 are orphaned.
A structuring attacker could exploit the rotation window by
timing attacks to coincide with salt rotation.

Two competing requirements:
1. Security: rotate salts to limit exposure if salt is compromised
2. Continuity: velocity monitoring must survive rotation

### Resolution

**Rotation frequency:** Annually (every 12 months)
More frequent rotation creates too large a migration burden and
attack window. Annual rotation is standard for long-lived
cryptographic material at this sensitivity level.

**Emergency rotation:** If salt compromise is suspected, 24-hour
hard rotation with the protocol below executed at speed.

**Dual-Salt Migration Protocol:**
```
Phase 1 — Preparation (Days 1-7 before rotation):
  - Generate new salt S_new in HSM
  - Begin computing dual hashes: H_old + H_new for all active entities
  - Write both to Redis: SET "vel:{H_old}" and SET "vel:{H_new}"
    with H_new pointing to same counter (copy, not new counter)

Phase 2 — Rotation Window (Days 8-37, 30-day overlap):
  - New payments: primary hash = SHA-256(tax_id + S_new)
  - Velocity lookup: check BOTH H_old and H_new
  - Sum both counters for velocity total
  - All licensees notified (via Bridgepoint aggregation service)

Phase 3 — Retirement (Day 38):
  - Stop generating H_old hashes
  - H_old velocity counters: TTL set to 24h (flush after last 24h window)
  - S_old destroyed in HSM
  - S_new becomes S_current
```

**Salt storage:** HSM-backed (AWS CloudHSM or equivalent)
- One salt per environment (dev/staging/prod)
- Never in application config files, environment variables, or logs
- Access: application service account only, via HSM API

**Per-licensee salt:** Each bank licensee gets a unique salt for
their local borrower hashes. The cross-licensee aggregation
service holds a SEPARATE aggregation salt for the shared velocity
table. Compromise of one licensee's salt does not expose others.

**Self-critique (CIPHER):** The 30-day overlap window is a known
vulnerability — a sophisticated attacker who knows rotation is
happening could exploit the dual-hash period. Mitigation: rotation
dates are never published or predictable. HSM rotation is silent.

---

## Q4: CORRIDOR BUFFER BOOTSTRAP STRATEGY
**Owner:** NOVA + ARIA | **Priority:** HIGH

### Question
Define the P95 settlement latency calculation for new corridors
with no 90-day history. What is the fallback?

### Analysis (NOVA + ARIA)

Three bootstrap failure modes to prevent:
1. Too aggressive (buffer too short): loan repaid before settlement
   → default declared incorrectly → damages borrower relationship
2. Too conservative (buffer too long): capital tied up unnecessarily
   → fee revenue deferred → reduces capital efficiency
3. No buffer at all: loan held in FUNDED state indefinitely if
   settlement never comes → system stuck

### Resolution — Four-Tier Bootstrap Model

**Tier 0: Days 0-7 (New Corridor, No Data)**
Use rejection_code_class × currency_pair conservative defaults:

| Class | Currency Pair     | Bootstrap Buffer |
|-------|-------------------|-----------------|
| A     | Major (USD/EUR/GBP/JPY) | 48 hours   |
| A     | Emerging markets  | 72 hours        |
| B     | Major             | 10 days         |
| B     | Emerging markets  | 14 days         |
| C     | Major             | 25 days         |
| C     | Emerging markets  | 30 days         |

These are intentionally conservative — protecting capital is
the priority when data is absent.

**Tier 1: Days 8-30 (Early Data)**
Blend global P95 for currency-pair + rejection class with
corridor-specific observed settlements.
Formula:
  buffer = 0.7 * global_P95(currency_pair, class)
           + 0.3 * corridor_P95(observed_so_far)

Weight shifts toward corridor-specific as sample size grows.

**Tier 2: Days 31-89 (Growing Sample)**
Continue Bayesian blend, shifting weight:
  buffer = 0.3 * global_P95(currency_pair, class)
           + 0.7 * corridor_P95(observed_so_far)

Flag to ARIA: if corridor P95 is >50% different from global P95,
generate alert for manual review — may indicate anomalous corridor
behavior that bootstrap cannot handle safely.

**Tier 3: Days 90+ (Full History)**
Pure corridor-specific P95, rolling 90-day window.
This is the steady-state operation defined in Architecture Spec v1.0.

**Early graduation:** If corridor accumulates 200+ observations
before Day 90, graduate to Tier 3 early. Sample size > 200
is sufficient for statistical reliability at P95.

**Storage:** Bootstrap tier status stored per corridor in Redis:
```
Key:   "corridor:buffer:{bic_sender}_{bic_receiver}_{class}"
Type:  Redis HASH
Fields:
  tier            : int    # 0, 1, 2, or 3
  sample_count    : int    # Observations collected
  created_at      : int64
  current_p95_hrs : float  # Current buffer hours
  last_updated    : int64
```

---

## Q5: LLM ASYNC PATH TIMEOUT BEHAVIOR
**Owner:** ARIA | **Priority:** MEDIUM

### Question
If quantized Llama-3 8B exceeds 200ms on the async path,
what is the fallback decision? Hold? Proceed? Block?

### Analysis (ARIA)

Recall the two-path dispute classifier architecture:
- Fast path: binary pre-classifier (~3ms) — always runs in critical path
- LLM path: Llama-3 8B quantized (~30-50ms) — runs async for
  uncertain cases (fast-path confidence 0.3-0.7)

Three cases on LLM timeout:

**Case 1: Fast-path was HIGH confidence NO_DISPUTE (>0.7)**
LLM was running speculatively to refine, not to decide.
Decision: PROCEED. Fast-path result stands.
LLM timeout logged for model monitoring. No customer impact.

**Case 2: Fast-path was HIGH confidence DISPUTE (>0.7)**
Already blocked by fast-path. LLM timeout irrelevant.
Decision: HARD BLOCK already in effect.

**Case 3: Fast-path was UNCERTAIN (0.3-0.7) — LLM timed out**
This is the only genuinely hard case.

### Resolution for Case 3

**Two-stage timeout handling:**

Stage 1 (200ms timeout): LLM result not received.
  → Extend hold to 500ms total. LLM gets one more window.
  → Log: "DISPUTE_LLM_STAGE1_TIMEOUT" + UETR + amount

Stage 2 (500ms hard limit): LLM still not received.
  → Apply amount-based risk policy:

```
If loan_amount_usd <= $50,000:
  Decision = PROCEED (small amount, fast-path lean used)
  Reason: exposure limited; false negative cost < false positive cost

If loan_amount_usd > $50,000 AND <= $500,000:
  Decision = HOLD_FOR_HUMAN_REVIEW
  Flag to ELO: "DISPUTE_UNRESOLVED_MEDIUM_RISK"
  Hold duration: up to 30 minutes for human ELO review
  If no human response in 30 min: BLOCK

If loan_amount_usd > $500,000:
  Decision = BLOCK (conservative)
  Reason: high-value disputed payment risk > bridge revenue
  Log: "DISPUTE_TIMEOUT_HIGHVALUE_BLOCK"
```

**Threshold $50K/$500K:** These are initial defaults.
Bank licensees can configure thresholds via ELO admin interface
based on their own risk appetite. Bridgepoint recommends these
defaults based on expected false-negative cost vs. revenue.

**LLM performance monitoring:** If timeout rate exceeds 1% of
LLM-path inferences in any rolling 1-hour window, FORGE
auto-scales inference nodes and ARIA is alerted. LLM timeout
at >1% means hardware is undersized for traffic.

**Self-critique (ARIA):** The $50K threshold is not empirically
derived — it is a reasonable starting default. After pilot, actual
dispute amounts should be analyzed and threshold calibrated to
minimize expected loss. This is an ARIA Phase 5 deliverable.

---

## Q6: UNKNOWN REJECTION CODES — CLASS B DEFAULT
**Owner:** NOVA + LEX | **Priority:** MEDIUM

### Question
Confirm Class B (7-day) default for unknown rejection codes
is correct, and define quarterly taxonomy review process.

### Analysis (NOVA + LEX)

Class B (7 days) as default for unknown codes is correct.
Reasoning:
- Class A (3 days) is too aggressive for unknowns — if the code
  represents a structural failure, 3 days is too short and we
  declare a false default
- Class C (21 days) is too conservative for unknowns — if the code
  is a temporary issue, capital is tied up 3x longer than needed
- Class B (7 days) is the right conservative middle ground: enough
  time for most compliance holds, not so long it destroys capital
  efficiency on temporary issues

LEX note: The taxonomy mapping (T = f(rejection_code_class)) is
the core distinguishing feature over JPMorgan US7089207B1.
Any unknown code that is later reclassified to Class A or C
is an improvement to this function — document all reclassifications
as evidence of the system's learned specificity.

### Resolution

**Default confirmed:** Unknown rejection codes → Class B (7 days)
**Log:** All unknown codes logged with field "taxonomy_status: UNCLASSIFIED"
for quarterly review.

**Quarterly Taxonomy Review Process:**

```
Step 1 — Data Pull (ARIA, first week of each quarter):
  Query decision log for all entries where taxonomy_status = UNCLASSIFIED
  Group by rejection_code, count occurrences, calculate actual
  settlement time (FUNDED timestamp to REPAID timestamp)

Step 2 — Classification Analysis (NOVA):
  For each unclassified code with >10 occurrences:
    - Calculate observed P95 settlement time
    - If P95 <= 4 days: propose Class A
    - If P95 4-10 days: confirm Class B (no change)
    - If P95 > 10 days: propose Class C
    - If no settlement in 90%+ cases: propose HARD_BLOCK

Step 3 — LEX Review:
  Any reclassification must be reviewed by LEX before deployment.
  Reclassifications strengthen T = f(rejection_code_class) specificity.
  Document each reclassification as: "learned mapping from observed
  settlement telemetry" — this is the non-obvious, specific technical
  contribution that distinguishes from static prior art.

Step 4 — Deployment:
  Updated taxonomy deployed as new model version (C3 config update)
  Previous version retained for 90 days (rollback capability)
  All reclassifications documented in model change log (SR 11-7)
```

**SWIFT code monitoring:** NOVA monitors SWIFT release notes
for new ISO 20022 reason codes. New codes added to UNCLASSIFIED
pool immediately on publication, prior to any real-world occurrence.

---

## Q7: DECISION LOG RETENTION PERIOD
**Owner:** REX | **Priority:** MEDIUM

### Question
Confirm 7-year minimum aligns with all applicable jurisdictions.

### Analysis (REX)

Retention requirements by jurisdiction and framework:

| Framework          | Jurisdiction | Requirement        | Record Type              |
|--------------------|--------------|--------------------|--------------------------|
| BSA / AML records  | US           | 5 years            | Transaction records      |
| SOX                | US           | 7 years            | Financial records        |
| SR 11-7            | US           | Duration of use    | Model documentation      |
|                    |              | + 3 years          |                          |
| FINTRAC            | Canada       | 5 years            | Transaction records      |
| DORA Art.30        | EU           | Contract duration  | ICT service records      |
|                    |              | + 3 years minimum  |                          |
| GDPR               | EU           | Data minimization  | Personal data (tension)  |
| MiFID II           | EU           | 5 years            | Financial instrument rec |
| MAS TRM            | Singapore    | 5 years            | Technology risk records  |
| CBUAE              | UAE          | 5 years            | Banking records          |

### Resolution

**Confirmed: 7-year minimum retention for all decision log entries.**

7 years satisfies every applicable jurisdiction at the most
conservative interpretation. SOX and SR 11-7 (duration + 3 years)
drive this to 7+ years; 7 is the correct floor.

**GDPR tension — resolved:**
The decision log contains NO personal data directly.
It contains only:
- SHA-256 entity hashes (not reversible to personal data)
- UETR (transaction reference, not personal data under GDPR)
- SHAP values (mathematical coefficients, not personal data)
- Loan amounts, codes, timestamps (transactional metadata)

If a bank asserts GDPR right-to-erasure on a borrower, Bridgepoint
cannot erase decision log entries because:
1. Log entries contain no personal data as defined under GDPR
2. Regulatory retention obligations (AML, SOX) override erasure
   where personal data is present (GDPR Art.17(3)(b))

REX recommends legal counsel confirm the SHA-256 hash
non-personal-data classification in target jurisdictions.
This is a medium-risk interpretation, not a guaranteed one.

**Tiered retention by record type:**

| Record Type                    | Retention | Rationale              |
|--------------------------------|-----------|------------------------|
| Decision log entries (full)    | 7 years   | SOX / SR 11-7          |
| AML velocity records           | 7 years   | BSA 5yr + safety margin|
| Model version snapshots        | 7 years   | SR 11-7 model governance|
| Raw SWIFT messages (Kafka)     | 30 days   | Operational only       |
| Corridor buffer calibration    | 7 years   | Model audit trail      |
| Human override records         | 7 years   | Regulatory accountability|

**Storage:** Decision log entries are append-only, cryptographically
signed (HMAC-SHA256). Signed entries satisfy non-repudiation
requirements for regulatory submissions.

---

## Q8: KAFKA ENCRYPTION KEY OWNERSHIP
**Owner:** REX + FORGE | **Priority:** MEDIUM

### Question
Define Bridgepoint vs bank-managed KMS per deployment model.

### Analysis (REX + FORGE)

Two deployment contexts exist within the architecture:

**Context A: Bank-deployed components**
C5 (Kafka, Redis), C7 (Execution Agent) run inside the bank's
own infrastructure. DORA Art.30 requires banks to maintain
control over ICT operational risk. Bank's regulators expect
the bank to own encryption keys for data within their perimeter.

**Context B: Bridgepoint-operated components**
Cross-licensee velocity aggregation service (part of C6)
runs on Bridgepoint infrastructure. Banks send only SHA-256
hashes — no raw data. Bridgepoint controls this service.

### Resolution

**Model A — Bank-Deployed Components (C5, C7):**
Bank manages KMS entirely.

```
Encryption key ownership:
  Kafka at-rest encryption:     Bank KMS (e.g., AWS KMS, Azure Key Vault)
  Redis at-rest encryption:     Bank KMS
  Decision log encryption:      Bank KMS
  HMAC signing keys:            Bank HSM
  TLS certificates (internal):  Bank PKI

Bridgepoint access:
  ZERO decryption capability for bank-side data
  Read access to decision logs via bank-controlled export API only
  (bank generates signed export; Bridgepoint receives, cannot
   access raw store directly)

DORA compliance:
  Bank fully controls ICT operational resilience for their data
  Satisfies DORA Art.30(2) sub-contractor and data security requirements
  Bank can audit Bridgepoint-deployed code without key handover
```

**Model B — Bridgepoint-Operated Components (C6 cross-licensee):**
Envelope encryption with bank master key.

```
Architecture:
  Data Encryption Keys (DEKs):  Generated by Bridgepoint per licensee
  Key Encryption Keys (KEKs):   Bank-held master keys
  Mechanism: DEK wrapped with bank KEK (envelope encryption)

Operation:
  Bridgepoint operates the velocity aggregation service normally
  using DEKs. DEKs are encrypted with each bank's KEK.
  If Bridgepoint is compromised, attacker gets only wrapped DEKs —
  useless without bank KEKs.

  If a bank withdraws from the platform, their KEK is revoked,
  their DEK becomes permanently inaccessible. Data is
  cryptographically deleted without physical deletion.

Cross-licensee velocity:
  Only SHA-256 hashes are processed. No raw PII transits
  Bridgepoint infrastructure. KEK protection on top of
  hash-only architecture creates defense in depth.
```

**Key Rotation:**

| Key Type                    | Rotation Frequency  | Owner      |
|-----------------------------|---------------------|------------|
| Bank KMS keys (C5, C7)      | Bank's policy       | Bank       |
| Cross-licensee DEKs         | Annually            | Bridgepoint|
| Cross-licensee KEKs         | Bank's policy       | Bank       |
| HMAC signing keys           | Annually            | Bank       |
| TLS certificates            | 90 days             | Both       |
| SHA-256 borrower ID salts   | Annually (see Q3)   | CIPHER     |

**FORGE implementation note:**
Kafka encryption key injection via init container pattern —
bank KMS credentials are injected at pod startup, never stored
in container images or Kubernetes secrets in plaintext.
Use Kubernetes External Secrets Operator with bank's vault
backend for secrets management.

---

## RESOLUTION SUMMARY

| # | Question                           | Resolution               | Status    |
|---|------------------------------------|--------------------------|-----------|
| 1 | GPU vs CPU inference               | GPU required; T4 min;    | RESOLVED  |
|   |                                    | HPA on queue depth       |           |
| 2 | RTP UETR mapping table             | Redis HASH; populated at | RESOLVED  |
|   |                                    | pacs.008 outbound event  |           |
| 3 | Salt rotation protocol             | Annual; 30-day dual-salt | RESOLVED  |
|   |                                    | migration window; HSM    |           |
| 4 | Corridor buffer bootstrap          | 4-tier model; Days 0-7   | RESOLVED  |
|   |                                    | conservative defaults    |           |
| 5 | LLM async timeout behavior         | 500ms hard limit; amount | RESOLVED  |
|   |                                    | tiered policy for Case 3 |           |
| 6 | Unknown rejection code default     | Class B confirmed; qrtly | RESOLVED  |
|   |                                    | taxonomy review process  |           |
| 7 | Decision log retention             | 7 years all records;     | RESOLVED  |
|   |                                    | GDPR tension documented  |           |
| 8 | Kafka encryption key ownership     | Model A (bank KMS) for   | RESOLVED  |
|   |                                    | C5/C7; envelope encrypt  |           |
|   |                                    | for C6 cross-licensee    |           |

**All 8 questions resolved. Architecture Specification v1.1 can now
be produced as the FINAL Phase 0 architectural reference.**

---

## ITEMS REQUIRING EXTERNAL LEGAL CONFIRMATION
(Internal flag — do not act on until stealth mode lifted)

- REX: GDPR classification of SHA-256 hashes as non-personal data
  should be confirmed by qualified EU data protection counsel
  before any EU bank deployment
- REX: SR 11-7 "duration of use + 3 years" retention interpretation
  should be confirmed against Federal Reserve guidance
- QUANT: $50K/$500K dispute timeout thresholds in Q5 are defaults —
  calibrate against actual dispute loss data from pilot phase

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
*Next action: Produce Architecture Specification v1.1 (FINAL)*
