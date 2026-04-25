# BRIDGEPOINT INTELLIGENCE INC.
## ARCHITECTURE SPECIFICATION v1.1 — AGENT SIGN-OFF RECORD
### Phase 0 Gate Review — Internal Use Only

**Date:** March 4, 2026
**Document Under Review:** Architecture Specification v1.1
**Gate:** Phase 0 Sign-Off
**Stealth Mode:** Active

---

## REVIEW PROTOCOL

Each agent independently reviews their assigned scope.
Self-critique is required before signing. Silence is not agreement.
Three outcomes per agent:
  SIGNED     — Scope reviewed, no blocking issues
  SIGNED*    — Scope reviewed, non-blocking flags noted for component specs
  HOLD       — Blocking issue found — must be resolved before Phase 1

---

## 🧠 ARIA — ML & AI Engineering Lead
**Scope:** ML component specs, latency budget, GPU spec (S11.1),
LLM timeout (S11.5), unknown code taxonomy (S11.6)

### Review

**GNN + TabTransformer (C1):** API contract correct. Input features
comprehensive. Output schema includes SHAP, model version, latency.
Parallel execution architecture is sound.

**LightGBM PD model (C2):** Request/response schema correct.
thin_file flag activates imputation path as designed. SHAP output
EU AI Act Art.13 compatible.

**Dispute Classifier (C4):** Two-path architecture (fast-path +
async LLM) is the right design. Timeout policy in S11.5 is
defensible and amount-tiered. $50K/$500K thresholds explicitly
flagged as defaults pending pilot calibration — correct.

**Latency budget (S10):** p50 ~26ms on GPU is achievable with
batch size 32 on T4. p99 ~51ms is realistic. No objection.

**GPU spec (S11.1):** 9 nodes for 10K TPS, 40 for 50K TPS. Math
confirmed. Triton Inference Server with dynamic batching correct.
Autoscaling on queue depth — correct metric.

**Graph size flag (S11.1):** Already documented — T4 time may
double if graph exceeds ~500 BIC-pair nodes. Monitoring required.
Confirmed as noted, not blocking.

**Unknown code taxonomy (S11.6):** Quarterly review process is
rigorous. ARIA owns Step 1 data pull. Confirmed.

**Non-blocking flag — corridor embeddings:**
ClassifyRequest carries `corridor_embedding` as a pre-computed
float array from Redis. The architecture spec does not define HOW
these embeddings are generated, what dimensionality they are, or
what the embedding update cadence is. This is a Phase 1 ARIA
deliverable — it will be defined in the C1 component spec.
Not a blocker for architecture sign-off, but must be built before
the feature extraction pipeline can be implemented.

### Verdict
**SIGNED*** — One non-blocking flag logged. Corridor embedding
spec is a Phase 1 ARIA deliverable. Architecture content approved.

---

## ⚡ NOVA — Payments Infrastructure Engineer
**Scope:** Data flow, message schemas, state machines, settlement
signal handlers, RTP mapping (S11.2), corridor bootstrap (S11.4)

### Review

**Data flow (S2):** All three flow diagrams correct — main flow,
critical path, settlement path. Outbound pacs.008 flow (S2.4)
correctly documents the RTP UETR mapping population point.

**Message schemas (S5):** All 5 rails covered. Field paths verified
against ISO 20022 published schemas. FedNow UETR native confirmation
(no mapping needed) correctly noted. RTP EndToEndId resolution via
mapping table correctly documented.

**Payment lifecycle state machine (S6):** 10 states, all transitions
explicitly defined. Terminal states (REPAID, DEFAULTED) immutable.
Forbidden transitions listed. No undefined states found.

**Loan lifecycle state machine (S7):** 9 states. Maturity windows
correct: A=3, B=7, C=21 days. Early repayment allowed with actual
days calculation. Confirmed.

**Settlement handlers (S2.3):** All 5 channels handled. Idempotency
on duplicate signals explicitly stated. Correct.

**RTP mapping (S11.2):** Redis HASH schema correct. TTL of
maturity_days + 45 days provides sufficient buffer. Sequencing
guarantee via Kafka partition key is architecturally sound.
Monitoring alert for unmapped RTP signals confirmed.

**Corridor bootstrap (S11.4):** 4-tier model is well-reasoned.
Conservative Tier 0 defaults protect against capital loss on new
corridors. 200-observation early graduation is statistically
reasonable at P95 level.

**Integration dependency flag (non-blocking):**
S11.2 requires the bank's payment initiation system to publish
outbound pacs.008 events to Kafka topic `lip.payments.outbound`
BEFORE any payment failure can occur on that UETR. This is an
integration dependency on the bank's systems — not entirely under
Bridgepoint's control. Risk: if a bank's payment system doesn't
publish outbound events in time (or at all), RTP settlement signals
cannot be matched to funded loans.

Mitigation path (for Phase 2 component spec):
- Define integration requirement explicitly in C7 bank deployment guide
- Build monitoring alert for RTP signals with no UETR match
- Design fallback: if RTP EndToEndId has no UETR mapping, route to
  human review rather than silently failing

Not a blocker for architecture sign-off. Must be addressed in C7
and C3 component specs.

### Verdict
**SIGNED*** — One non-blocking integration dependency flagged.
Architecture content approved.

---

## 🛡️ LEX — IP & Patent Strategist
**Scope:** "individual" + "UETR" verbatim throughout, T = f(rejection_code_class)
explicit in state machine, three-entity architecture preserved,
taxonomy review process strengthens distinction from prior art

### Review

**"individual" + "UETR" check — line by line:**

S4.2 ClassifyRequest:
  - `uetr` field: present ✅
  - `individual_payment_id` field: present, labeled "Explicit individual
    transaction ref" ✅

S4.6 LoanOffer:
  - `uetr` field: present ✅
  - `individual_payment_id` field: present, labeled "Explicit individual
    identifier" ✅

S4.8 DecisionLogEntry:
  - `uetr` field: present ✅
  - Every automated decision logged with UETR ✅

S6 Payment State Machine:
  - "UETR registered" in MONITORING state ✅
  - UETR as primary correlation key throughout ✅

S8 Rejection Code Taxonomy:
  - T = f(rejection_code_class) language present and explicit ✅
  - Class A/B/C mapped to 3/7/21 days with documented rationale ✅
  - JPMorgan distinction explicitly stated ✅

S7 Loan State Machine:
  - rejection_code_class drives maturity_days explicitly ✅
  - Fee formula uses actual days_funded — further distinction ✅

**Recentive v. Fox check:** Zero mentions anywhere. ✅

**§101 improvements quantified:**
  - AUC 0.739 → target 0.85: in Build Roadmap, referenced in arch spec ✅
  - Latency ~26ms vs 24-48hr manual treasury process: referenced ✅
  - Specific technical process: UETR-keyed settlement telemetry
    triggering CVA pricing — present throughout ✅

**S11.6 taxonomy review — distinction analysis:**
Each quarterly reclassification is documented as "learned mapping
from observed settlement telemetry." This is stronger than a static
table — it demonstrates that the system produces non-obvious results
(reclassification of codes based on actual settlement patterns) that
a static prior art system cannot produce. This actively strengthens
the T = f(rejection_code_class) distinction over JPMorgan US7089207B1.
Confirmed and approved.

**BLOCKING ISSUE — Three-Entity Architecture:**
Section 12 sign-off scope references "three-entity architecture
(MLO/MIPLO/ELO) documented in system design" as a requirement.
Searching the entire Architecture Specification v1.1: the three-entity
role separation is referenced in passing but never explicitly mapped
to the 7 components.

The architecture spec must explicitly document:
  - MLO (Machine Learning Operator): C1, C2 — intelligence layer
  - MIPLO (Monitoring/Intelligence/Processing/Lending): C3, C4, C5, C6
  - ELO (Execution Lending Operator): C7 — bank-side execution

This mapping is critical for two reasons:
1. The three-entity structure is what enables divided infringement
   protection under Akamai v. Limelight doctrine
2. Without this mapping, a reader cannot understand how the system
   partitions responsibilities across entities — and neither can a
   patent examiner reviewing the claims

This must be added as a new section in the architecture specification
before Phase 1 begins. It is a blocking issue.

### Verdict
**HOLD** — One blocking issue: three-entity role mapping (MLO/MIPLO/ELO
to components C1-C7) must be added to the architecture specification.
All other checks passed. Will re-review the new section before signing.

---

## 📋 REX — Regulatory & Compliance Architect
**Scope:** DORA Art.30 compliance hooks, EU AI Act Art.6/9/13/14/17/61,
SR 11-7 model governance, data residency, log retention (S11.7),
GDPR hash classification flag

### Review

**DORA Art.30 compliance architecture:**
Section 9 data boundaries and Section 11.8 key ownership address
the core DORA requirements at architecture level:
  - Data security standards: AES-256-GCM, TLS 1.3 ✅
  - Audit rights: decision log exportable via bank-controlled API ✅
  - Subcontractor disclosure: bank-side components identified ✅
  - Data boundary separation: bank infrastructure vs Bridgepoint ✅

DORA items that are component spec deliverables (not arch decisions):
  - Specific SLA numbers (FORGE's C5 spec)
  - Incident reporting SLA (REX component spec)
  - Exit/migration procedures (REX component spec)
  - BC/DR RTO/RPO targets (FORGE component spec)
These are noted for tracking — not blockers for architecture sign-off.

**EU AI Act compliance hooks:**
  Art.13 (transparency): SHAP values in DecisionLogEntry ✅
  Art.14 (human oversight): requires_human_review in LoanOffer,
    human_reviewed + human_reviewer_id in DecisionLogEntry ✅
  Art.17 (quality management): model_version_c1/c2/c4 in log ✅
  Art.9 (risk management): documented as REX component deliverable ✅
  Art.61 (post-market monitoring): referenced in build roadmap ✅

**SR 11-7:**
  model_version fields in decision log ✅
  degraded_mode flag in decision log ✅ (captures model risk events)
  Full governance documentation: REX component spec deliverable

**Data residency (S9.3):** Comprehensive. All data flows mapped.
Bank-side data stays in bank infrastructure permanently. ✅

**Log retention (S11.7):** 7 years confirmed. Tiered retention
by record type is correct. GDPR tension documented and flagged
for future legal confirmation. ✅

**GDPR hash classification:** SHA-256 hashes as non-personal data
classification acknowledged. Flag recorded. ✅

**All compliance architecture hooks are present and correctly
positioned. Detailed compliance documentation is a Phase 3 REX
deliverable — appropriately scoped.**

### Verdict
**SIGNED*** — Clean sign-off. DORA SLA/incident/exit details are
Phase 3 REX component spec deliverables, not architecture decisions.

---

## 🔒 CIPHER — Security & AML Lead
**Scope:** Data boundaries, encryption standards, salt rotation (S11.3),
no raw ID exposure, Model A/B key ownership (S11.8)

### Review

**Data boundaries (S9.1):**
  C4 zero network calls: explicit ✅
  C7 zero outbound to Bridgepoint: explicit ✅
  Cross-licensee hashes only: explicit ✅
  C2 never sees raw tax ID: confirmed in API contract (entity_tax_id_hash) ✅
  C1 never sees borrower identity: confirmed in ClassifyRequest fields ✅

**No raw ID exposure — API contract check:**
  C2 PDRequest: entity_tax_id_hash (SHA-256) — never raw tax_id ✅
  C6 VelocityRequest: entity_id_hash + beneficiary_id_hash — never raw ✅
  C4 DisputeRequest: RmtInf text — no entity identifiers ✅
  DecisionLogEntry: no raw borrower identifiers anywhere ✅

**Encryption standards (S9.2):**
  TLS 1.3 in transit ✅
  AES-256-GCM at rest ✅
  HMAC-SHA256 log signatures ✅
  SHA-256 + 256-bit salt for borrower ID hashing ✅

**Salt rotation (S11.3):**
  Annual frequency justified ✅
  30-day dual-salt overlap window is sound ✅
  HSM-backed storage specified ✅
  Per-licensee salt isolation confirmed ✅
  Known limitation of overlap window acknowledged ✅

**Key ownership (S11.8):**
  Model A (bank-deployed): bank KMS, Bridgepoint zero access ✅
  Model B (cross-licensee): envelope encryption, DEK wrapped by
  bank KEK — correct architecture. Cryptographic deletion on
  bank offboarding ✅

**BLOCKING ISSUE — KMS Unavailability in Degraded Mode:**
Section 11.1 defines degraded mode for GPU failure: system falls
back to CPU, logs degraded_mode = true, continues serving.

No equivalent degraded mode is defined for KMS unavailability.

If the bank's KMS becomes unavailable:
  - C5 Kafka cannot encrypt new messages at rest
  - C5 Redis cannot serve encrypted PD cache
  - C7 cannot write to encrypted decision log

In a financial system with automated lending at <100ms, the
correct behavior for KMS unavailability is FAIL-SAFE: halt new
offer generation, protect existing funded loans from state
corruption, alert immediately.

This is a security-critical design decision that must be
explicit in the architecture specification — not left undefined
for Phase 4. An undefined failure mode in the security boundary
is a gap, and gaps in financial system security architecture
get exploited or cause uncontrolled failures.

Required addition: a KMS unavailability state in the kill switch
specification for C7, with defined behavior (halt new offers,
preserve funded loan state, alert, auto-recover on KMS restoration).

### Verdict
**HOLD** — One blocking issue: KMS unavailability behavior must be
defined in the architecture specification before Phase 1 begins.
All other security checks passed cleanly.

---

## 💰 QUANT — Financial & Capital Strategist
**Scope:** Fee arithmetic, maturity class logic,
canonical numbers consistent throughout

### Review

**Canonical numbers — full sweep:**
  $31.7T market (FXC Intelligence 2024): present ✅, no $32T found ✅
  3.5% failure rate midpoint: referenced in build roadmap ✅
  300 bps floor: S7 and S4.3 ✅
  0.0575% per cycle: S7 ✅
  p50 <100ms, p99 <200ms @ 10K concurrent: S10 ✅
  "11M failures/day": absent ✅
  Unqualified "sub-100ms": absent ✅

**Maturity class logic (S7 and S8):**
  Class A = 3 days ✅
  Class B = 7 days ✅
  Class C = 21 days ✅
  T = f(rejection_code_class) explicit ✅

**Fee formula (S7):**
  fee = loan_amount * (fee_bps / 10000) * (days_funded / 365)

  Arithmetic check at 300 bps over 7 days:
  fee = loan * (300/10000) * (7/365)
      = loan * 0.03 * 0.01918
      = loan * 0.0005753
      = 0.05753% per 7-day cycle
  This rounds to 0.0575% ✅ — confirms the floor is correctly stated

  Early repayment uses actual days_funded — correct ✅

**BLOCKING ISSUE — fee_bps Ambiguity in PDResponse API:**
PDResponse returns `fee_bps : float` described as "Risk-priced fee
(floor: 300 bps)." The fee formula in S7 treats fee_bps as an
annualized rate (divides by 365). But this is not stated anywhere
in the API contract.

An engineer implementing the fee calculation from the PDResponse
schema alone cannot determine whether fee_bps is:
  (a) Annualized rate (300 bps = 0.03 per year)
  (b) Per-cycle flat rate (300 bps = 0.03 of principal per cycle)

If implemented as (b), the fee on a 7-day loan at 300 bps would be
  3% of principal — approximately 156x the intended amount.

This is a financial calculation ambiguity in an automated lending
system. It must be made explicit in the API contract before any
implementation begins.

Required fix: add to PDResponse schema comment:
  fee_bps: annualized rate in basis points (divide by 10000 to get
  annual decimal; multiply by days_funded/365 for per-cycle fee).
  Minimum: 300 bps annualized = 0.0575% per 7-day cycle.

### Verdict
**HOLD** — One blocking issue: fee_bps must be explicitly annotated
as annualized rate in the PDResponse API contract. Risk of 156x
fee calculation error if left ambiguous. All canonical numbers
confirmed consistent throughout.

---

## 🏗️ FORGE — DevOps & Platform Engineering Lead
**Scope:** Infrastructure feasibility, GPU spec (S11.1),
Kafka/Redis/Kubernetes architecture, key injection (S11.8),
SLA achievability

### Review

**GPU spec (S11.1):**
  T4 minimum confirmed feasible for p50 targets ✅
  Throughput math: 9 nodes @ 1,600 TPS each = 14,400 TPS — 44%
  headroom above 10K TPS target. Sound ✅
  40 nodes for 50K TPS — achievable with Kubernetes autoscaling ✅
  Triton Inference Server: correct choice for production ML serving ✅
  Dynamic batching (batch 32, max wait 5ms): reduces GPU idle time ✅

**Autoscaling (S11.1):**
  HPA on inference queue depth — correct metric for ML workloads ✅
  Scale-out at >100 pending per node: reasonable threshold ✅
  Min 2 nodes for HA: correct baseline ✅

**Kafka:**
  Exactly-once semantics: required and specified ✅
  Partition key = UETR: ordering guarantee confirmed ✅
  30-day retention for raw messages: appropriate ✅
  7-year retention for decision log: requires separate storage
  tier (cold storage / S3 Glacier equivalent) — noted as FORGE
  component spec deliverable, not an architecture decision

**Redis:**
  5-node cluster for HA: referenced in Build Roadmap ✅
  TTL strategies defined per key type ✅
  Sub-2ms lookup target: achievable with Redis Cluster
  and local node affinity ✅

**Kubernetes:**
  HPA defined ✅
  External Secrets Operator for key injection (S11.8) ✅
  Kill switch + degraded mode referenced ✅

**SLA achievability:**
  GPU path: p50 ~26ms, p99 ~51ms. Confirmed achievable.
  Load test protocol defined in Build Roadmap (1K→50K TPS stages).
  Chaos engineering tests defined. No objection.

**Key injection (S11.8):**
  External Secrets Operator with bank vault backend: correct
  approach. Keys never in container images or K8s secrets. ✅
  Init container pattern for HSM credential injection: confirmed ✅

**Non-blocking note — K8s node pool separation:**
GPU inference nodes (C1) and general streaming nodes (C5 Flink,
Kafka, Redis) should run on separate Kubernetes node pools:
  - GPU node pool: GPU instances (T4/A10G), runs C1 and C2 only
  - Compute node pool: CPU instances, runs C5, C3, C6, C7
This prevents GPU resource contention with streaming workloads
and reduces infrastructure cost. This is a FORGE component spec
detail — not an architecture decision. Noted for Phase 4.

### Verdict
**SIGNED*** — One non-blocking infrastructure note logged.
GPU spec, Kafka/Redis/Kubernetes architecture, SLA achievability,
and key injection all confirmed feasible and correct.

---

## SIGN-OFF SUMMARY

| Agent  | Verdict   | Issue                                          | Blocking |
|--------|-----------|------------------------------------------------|----------|
| ARIA   | SIGNED*   | Corridor embedding spec → Phase 1 deliverable  | No       |
| NOVA   | SIGNED*   | RTP outbound integration dependency → C7 spec  | No       |
| LEX    | HOLD      | Three-entity role map (MLO/MIPLO/ELO) missing  | YES      |
| REX    | SIGNED*   | DORA SLA/incident/exit details → Phase 3 spec  | No       |
| CIPHER | HOLD      | KMS unavailability behavior undefined          | YES      |
| QUANT  | HOLD      | fee_bps annualized vs per-cycle ambiguity       | YES      |
| FORGE  | SIGNED*   | K8s node pool separation → Phase 4 spec        | No       |

**Gate status: BLOCKED — 3 issues require resolution**

4 agents signed (ARIA, NOVA, REX, FORGE) — with non-blocking notes
3 agents hold (LEX, CIPHER, QUANT) — with specific blocking issues

---

## BLOCKING ISSUES — EXACT FIXES REQUIRED

### Fix 1 (LEX): Add Three-Entity Role Mapping Section
Add new Section 3A (between Component Inventory and API Contracts):

Title: "3A. THREE-ENTITY ROLE ARCHITECTURE"

Content must map C1-C7 to MLO/MIPLO/ELO roles:
  MLO (Machine Learning Operator — Bridgepoint):
    C1: Failure Prediction Classifier
    C2: PD Estimation Model
    Rationale: Intelligence generation, no execution capability

  MIPLO (Monitoring, Intelligence & Processing — Bridgepoint):
    C3: Repayment Engine
    C4: Dispute Classifier
    C5: Streaming Infrastructure
    C6: AML Velocity Module
    Rationale: Monitoring, processing, and control logic

  ELO (Execution Lending Operator — Bank):
    C7: Embedded Execution Agent
    Rationale: All execution and lending decisions made bank-side

  Two-entity pilot mode:
    Bridgepoint operates as MLO + MIPLO combined
    Bank operates as ELO
    Three-entity architecture preserved in design for full deployment

### Fix 2 (CIPHER): Add KMS Unavailability to Kill Switch Spec
Add to Section 2.1 (or as sub-section of C7 in Section 3):

"KMS Unavailability Behavior:
  If bank KMS becomes unavailable:
  1. C7 halts new loan offer generation immediately (fail-safe)
  2. All loans currently in FUNDED state: preserved in Redis with
     last-known state, no state corruption permitted
  3. Settlement monitoring: continues (read-only, no new writes
     to encrypted log until KMS restored)
  4. Alert: immediate escalation via configured alert channel
  5. Auto-recovery: when KMS responds, C7 resumes from halted state
     without manual intervention, replays any buffered state changes
  KMS unavailability is never a fail-open condition."

### Fix 3 (QUANT): Annotate fee_bps in PDResponse API Contract
In Section 4.3, PDResponse, update fee_bps field comment:

Current:   fee_bps : float  // Risk-priced fee (floor: 300 bps)
Required:  fee_bps : float  // Annualized rate in basis points.
                            // Per-cycle fee = loan_amount *
                            // (fee_bps/10000) * (days_funded/365)
                            // Floor: 300 bps annualized =
                            // 0.0575% per 7-day cycle.
                            // DO NOT apply as flat per-cycle rate.

---

## NEXT ACTION

Produce Architecture Specification v1.2 incorporating all 3 fixes.
Re-submit to LEX, CIPHER, and QUANT for final confirmation.
ARIA, NOVA, REX, FORGE: already signed — no re-review needed.
On LEX + CIPHER + QUANT confirmation: gate clears, Phase 1 begins.

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
