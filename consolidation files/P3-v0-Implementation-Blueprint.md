# Bridgepoint Intelligence — P3 v0 Implementation Blueprint
## Multi-Party Platform Licensing Architecture (MIPLO/ELO Embedded Deployment)
## C-Component Engineering Map & Revenue Model
Version 1.0 | Confidential | March 2026

---

## Table of Contents
1. Executive Summary
2. Part 1 — Legal Entity & Licensing Architecture
3. Part 2 — Product Architecture (Multi-Tenant MIPLO API)
4. Part 3 — Revenue Waterfall
5. Part 4 — C-Component Engineering Map
6. Part 5 — Consolidated Engineering Timeline
7. Part 6 — What Stays in the Long-Horizon P3 Patent
8. Part 7 — Risk Register

---

## Executive Summary

This document is the engineering and legal blueprint for launching a live, revenue-bearing version of P3 (Multi-Party Architecture, Embedded Implementation & Adversarial Cancellation) in 2027 — ahead of the formal patent filing window (Year 2–3 per Patent Family Architecture v2.1). It defines the exact multi-tenant licensing architecture, processor integration model, revenue waterfall, and maps every change required against Bridgepoint's existing C1–C8 technical components.

Core thesis: P3 v0 does not require a greenfield multi-tenant platform. Bridgepoint's existing codebase is **80% P3-ready** — C8 license tokens with `LicenseeContext`, cross-licensee AML velocity aggregation with salt-rotation privacy, phase-aware fee waterfall decomposition, and licensee-stamped decision audit logging are all implemented and tested. P3 v0 extends these into a processor-hosted embedded deployment model where payment platforms (Finastra, FIS Global, Temenos) run Bridgepoint's classification and pricing engine as a containerised service within their own infrastructure.

Engineering summary:

| Component | P3 v0 Impact | Effort |
|-----------|-------------|--------|
| C1 — ML Failure Classifier | No change | 0 |
| C2 — PD Pricing Engine | Minor: tenant-scoped model config, risk bucket routing | 1 week |
| C3 — Settlement Monitor | Extend: multi-tenant settlement tracking, per-tenant NAV | 2–3 weeks |
| C4 — Dispute Classifier | No change (minor output routing, 1–2 days) | ~2 days |
| C5 — ISO 20022 Processor | No change | 0 |
| C6 — AML / Security | Extend: cross-tenant velocity isolation, namespace partitioning | 2 weeks |
| C7 — Bank Integration Layer | Extend: processor-hosted container management, MIPLO API gateway | 6–8 weeks |
| C8 — Licensing & Metering | Extend: processor token type, revenue metering, annual minimum enforcement | 3–4 weeks |

Total engineering effort: ~14–18 engineer-weeks across 2 senior engineers.
Calendar time: ~4.5 months from greenlight.
Target: Live processor pilot Q3 2027 (after first direct-bank Phase 1 deployment proves the product).

---

## Part 1 — Legal Entity & Licensing Architecture

### 1.1 Why Embedded Licensing (Not Standalone SaaS)

Embedded licensing through payment processors is the optimal go-to-market structure for P3 v0 for five compounding reasons:

1. **Distribution leverage eliminates the onboarding bottleneck.** Finastra FusionFabric.cloud serves 8,000+ banks with 65+ live API integrations. FIS Modern Banking Platform serves 650+ institutions with 60+ components via their Code Connect API Marketplace. Temenos Exchange targets 200+ fintechs with their SCALE Developer Program and sandbox portals. A single integration with one processor gives Bridgepoint access to hundreds of banks without the 18–24 month per-bank integration cycle that caps the direct model at 15 banks by Year 10.

2. **Mid-tier bank economics become viable.** Under the direct model, mid-tier banks processing $100–200B in cross-border payments generate only ~$268K/yr for BPI (GTM-Strategy-v1.0 §3) — below the integration cost threshold. Via a processor, BPI's marginal cost per additional bank approaches zero because the processor handles the integration. Mid-tier becomes profitable at $50K+/yr per bank.

3. **Akamai doctrine compliance.** P3's patent claims cover the three-entity distributed arrangement (MLO/MIPLO/ELO) affirmatively as a specific embodiment. Under *Akamai Technologies, Inc. v. Limelight Networks, Inc.* (Fed. Cir. 2015), a competitor distributing the method steps across three entities could avoid direct infringement of P2's method claims. P3 closes this gap by claiming the API data flow between entities as patentable subject matter. The embedded licensing model IS the claimed structure — deploying it commercially strengthens the patent's enforceability.

4. **DORA ICT third-party compliance is built-in.** Under DORA Article 29 (effective January 2025), the processor's use of Bridgepoint's technology constitutes a "sub-outsourcing" arrangement. Bridgepoint must support audit rights, exit strategies, and operational resilience testing. Designing for this from day 1 creates a compliance barrier that competitors must also overcome — a moat, not a cost.

5. **Category validation from comparable exits.** Featurespace (embedded payment fraud detection) was acquired by Visa in December 2024 for an estimated $350M–$925M. Feedzai ($2B+ valuation, $123.8M revenue) processes $8T in payments annually and signed a $100M deal with a top-10 European bank, plus an ECB digital euro contract. NICE Actimize ($453.5M revenue, 35% operating margin) is currently for sale at $1.5–2B (Goldman Sachs/JP Morgan advising). The embedded payment intelligence category is validated at billion-dollar scale.

### 1.2 Entity Stack

```
BRIDGEPOINT INTELLIGENCE INC. (Canada — BC ULC)
Role: Technology licensor, model owner, data processor (GDPR Art. 28)
Revenue: Per-transaction bps + annual minimum + performance premium
         + technology licensing fee (intra-group, same as P7 SV)
         |
         | (1) Master Licensing Agreement (MLA)
         | (2) Technology Addendum (per-product schedule)
         | (3) Data Processing Agreement (GDPR Article 28)
         | (4) DORA ICT Sub-outsourcing Addendum (Art. 29 compliance)
         | (5) Order Form (per-processor commercial terms)
         | (6) SLA (uptime, latency, support response)
         v
PAYMENT PROCESSOR (e.g., Finastra, FIS Global, Temenos)
Role: Platform operator, first-line compliance, bank relationship owner
Structure: Runs Bridgepoint containerised service within own infrastructure
Revenue: Platform take rate (15–30% of BPI fee share)
         |
         | Bank License Agreement (processor's existing standard terms)
         | BPI Technology Schedule (embedded as processor feature)
         | Processor SLA passthrough
         v
BANK / ELO PARTNER
Role: Lender of record, originator of bridge loans
Mechanism: Uses processor's platform with BPI intelligence embedded
           Bank may not even know BPI exists (white-label option)
Retains: Regulatory relationship, borrower KYC, AML obligation
```

### 1.3 Six-Layer Contract Stack

The legal architecture requires six distinct documents, each addressing a different compliance dimension:

| Layer | Document | Purpose | Key Clauses |
|-------|----------|---------|-------------|
| 1 | Master Licensing Agreement | Commercial relationship, IP rights, exclusivity | Territory exclusivity (optional), non-compete during term, IP ownership (BPI retains all) |
| 2 | Technology Addendum | Per-product technical specifications | C-component list, API specifications, model update cadence, data retention |
| 3 | Data Processing Agreement | GDPR Article 28 compliance | Data minimisation, purpose limitation, sub-processor list, breach notification (72h) |
| 4 | DORA Sub-outsourcing Addendum | DORA Article 29 compliance | Audit rights for processor and its regulated bank clients, exit strategy, operational resilience testing, incident reporting chain |
| 5 | Order Form | Per-processor commercial terms | Transaction pricing, annual minimum, performance premium thresholds, payment terms |
| 6 | SLA | Performance guarantees | Uptime (99.95%), latency (p99 < 94ms, consistent with LIP SLO), support SLA (P1: 15min, P2: 1h, P3: 4h) |

### 1.4 White-Label vs Co-Branded Deployment

Two deployment modes exist for P3 v0:

| Feature | White-Label | Co-Branded |
|---------|------------|------------|
| Bank awareness of BPI | No — processor presents as own capability | Yes — "Powered by Bridgepoint Intelligence" |
| Pricing premium | Lower (processor captures value perception) | Higher (BPI brand adds trust) |
| Regulatory liability | Processor primary | Shared (BPI as named technology provider) |
| Data access | BPI receives anonymised telemetry only | BPI may access de-identified analytics |
| Recommended for Phase 1 | **Yes** (faster adoption, lower friction) | Phase 2 (after brand established) |

Recommendation for P3 v0: White-label in Phase 1. The bank uses the processor's existing platform and does not need to evaluate, contract with, or integrate BPI directly. This reduces the sales cycle from 18–24 months (direct bank) to the processor's standard feature activation timeline (typically 2–4 weeks for existing bank clients).

---

## Part 2 — Product Architecture (Multi-Tenant MIPLO API)

### 2.1 MIPLO API Gateway

The Multi-party Intelligent Payment Lending Orchestration (MIPLO) API is the external-facing interface through which processors invoke Bridgepoint's classification and pricing engine. It wraps the existing `LIPPipeline` in a multi-tenant API layer gated by C8 license tokens.

**Endpoints:**

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `POST` | `/api/v1/miplo/classify` | Payment failure classification (C1 + C5) | C8 processor token |
| `POST` | `/api/v1/miplo/price` | PD/fee calculation (C2) | C8 processor token |
| `POST` | `/api/v1/miplo/execute` | Loan offer routing (C7) | C8 processor token |
| `POST` | `/api/v1/miplo/dispute` | Dispute classification (C4) | C8 processor token |
| `GET` | `/api/v1/miplo/portfolio` | Per-tenant portfolio view | C8 processor token |
| `GET` | `/api/v1/miplo/health` | Container health + license validity | C8 processor token |
| `GET` | `/api/v1/miplo/metrics` | Prometheus metrics (per-tenant) | Internal only |

### 2.2 Classify Request Payload

```json
{
  "tenant_id": "FINASTRA_EU_001",
  "request_id": "req-20270714-0001",
  "payment": {
    "uetr": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "sending_bic": "DEUTDEFF",
    "receiving_bic": "BNPAFRPP",
    "amount": 1250000.00,
    "currency": "EUR",
    "value_date": "2027-07-14",
    "rejection_code": "AC04",
    "rejection_reason_info": "Closed Account Number",
    "message_type": "pacs.002",
    "original_message_id": "MSG-20270714-0001"
  },
  "bank_context": {
    "sub_licensee_bic": "COBADEFF",
    "deployment_phase": "LICENSOR",
    "hold_bridgeable": true,
    "certified_by": "COBADEFF_COMPLIANCE_SYS_V3",
    "certification_ts": "2027-07-14T08:01:00Z"
  }
}
```

### 2.3 Classify Response Payload

```json
{
  "request_id": "req-20270714-0001",
  "tenant_id": "FINASTRA_EU_001",
  "classification": {
    "failure_class": "CLASS_A",
    "failure_probability": 0.87,
    "rejection_code_category": "ACCOUNT_ERROR",
    "is_compliance_hold": false,
    "is_block_class": false
  },
  "pricing": {
    "pd_score": 0.023,
    "fee_bps": 312,
    "fee_amount_usd": 3900.00,
    "maturity_days": 3,
    "governing_law": "DE"
  },
  "offer": {
    "loan_id": "BPI-MIPLO-20270714-0001",
    "loan_amount_usd": 1250000.00,
    "offer_expiry": "2027-07-14T08:16:00Z",
    "acceptance_required": true
  },
  "decision_log_id": "DL-20270714-0001-FINASTRA_EU_001",
  "latency_ms": 42
}
```

### 2.4 Tenant Isolation Architecture

Data isolation between processor tenants is enforced at four layers:

| Layer | Mechanism | Existing Code |
|-------|-----------|--------------|
| **L1 — Authentication** | C8 license token with `tenant_id` and `sub_licensee_bics` list. Token validated at every request. | `LicenseBootValidator` in `lip/c8_license_manager/boot_validator.py` |
| **L2 — Data Partitioning** | Every database key, Kafka topic, and Redis namespace includes `tenant_id` prefix. | Pattern exists in `CrossLicenseeAggregator` hash keys |
| **L3 — AML Velocity** | Velocity counters partitioned by `tenant_id`. Cross-tenant aggregation only at BPI level via `CrossLicenseeAggregator`. | `lip/c6_aml_velocity/cross_licensee.py` — salt-rotation overlap, dual-write |
| **L4 — Decision Audit** | Every `DecisionLogEntryData` stamped with `licensee_id` (=`tenant_id`). Immutable, HMAC-signed. | `lip/c7_execution_agent/agent.py:588` |

CIPHER must review the tenant isolation architecture before any processor deployment. Cross-tenant data leakage is a critical security risk — a bank's payment data visible to another processor's bank clients would be a GDPR Article 33 breach.

### 2.5 Processor-Hosted Container Lifecycle

```
DEPLOYMENT:
  1. Processor requests deployment for new bank BIC
  2. BPI generates C8 processor token: tenant_id + sub_licensee_bics + permitted_components
  3. BPI signs token with HMAC-SHA256 (signing key never leaves BPI HSM)
  4. Processor pulls containerised image from BPI-controlled registry (encrypted at rest)
  5. Container boots → LicenseBootValidator runs → token validated → components initialised
  6. Container registers heartbeat with BPI telemetry endpoint (every 60s)

RUNTIME:
  7. Processor routes payment events to container's MIPLO API
  8. Container processes: C5 → C1 → C2 → C4 → C6 → C7 (same pipeline as direct deployment)
  9. Container emits: decision log (encrypted, to BPI), metrics (Prometheus, to processor + BPI)
  10. Revenue metering: per-transaction counter incremented, synced to BPI every 5 minutes

MODEL UPDATES:
  11. BPI pushes updated model artifacts to registry (C1 GraphSAGE+TabTransformer, C2 LightGBM)
  12. Container detects new model version via registry poll (every 15 minutes)
  13. Blue-green deployment: new model loaded alongside old, traffic shifted after validation
  14. Rollback: if new model's inference latency > 94ms or AUC drops > 5%, auto-revert

KILL SWITCH:
  15. If C8 token expires, container enters degraded mode → no new offers, existing positions monitored
  16. If BPI revokes token (HMAC validation fails), container shuts down all lending operations
  17. Settlement monitoring (C3) continues regardless — existing bridge loans must be serviced
```

---

## Part 3 — Revenue Waterfall

### 3.1 Inflow Sources (Per Processor, Per Settlement Period)

| Source | Mechanism | Timing |
|--------|-----------|--------|
| Per-transaction fee | bps on each bridge loan originated through MIPLO API | On loan origination |
| Annual minimum guarantee | Processor commits to minimum annual fee regardless of volume | Quarterly in advance |
| Performance premium | 10–25% of revenue above agreed baseline (incentivises processor to onboard more banks) | Quarterly in arrears |
| Model update fee (optional) | Premium for priority access to model updates (e.g., new corridors, C4 dispute classifier) | Annual |

### 3.2 Outflow Waterfall (Strict Priority Order)

Distributions from each processor's revenue are made in the following sequence:

**Priority 1 — Infrastructure Costs**
- Container hosting (processor infrastructure, BPI reimburses or offsets)
- BPI telemetry, monitoring, model registry infrastructure
- Estimated: 5–10% of gross revenue

**Priority 2 — Processor Platform Fee (Take Rate)**
- 15–30% of BPI's gross per-transaction revenue
- Processor retains for: bank relationship management, first-line compliance, platform infrastructure, support
- Negotiable per processor; lower for higher-volume commitments

**Priority 3 — BPI Net Revenue (Per-Transaction)**
- Remaining 70–85% of per-transaction fee after processor take rate
- Split according to deployment phase (BPI share: 30% Phase 1, 55% Phase 2, 80% Phase 3)

**Priority 4 — Annual Minimum True-Up**
- If cumulative Priority 3 revenue < annual minimum, processor pays the shortfall
- Ensures BPI floor revenue regardless of transaction volume
- Minimum set at $500K–$2M per processor per year

**Priority 5 — Performance Premium**
- 10–25% of net revenue above agreed baseline
- Calculated quarterly; paid quarterly in arrears
- Baseline set at 80% of projected annual volume

### 3.3 Coverage Tests & Circuit Breakers

| Test | Trigger Level | Automatic Action |
|------|--------------|------------------|
| Latency SLO breach | p99 > 94ms for 5 consecutive minutes | Alert BPI engineering. If sustained 30 minutes, auto-scale container replicas. |
| AUC drift | Model AUC drops below 0.80 (existing threshold) | Block new model deployments. Alert ARIA. Revert to last-known-good model. |
| Revenue shortfall | Trailing 90-day revenue < 50% of annualised minimum | Escalate to BPI commercial team. Trigger processor engagement review. |
| Token expiry approaching | < 30 days to C8 token expiry | Auto-alert both BPI and processor. Renewal process initiated. |
| Security incident | CIPHER flags potential data leakage or AML breach | Immediate container isolation. Halt all new originations. Incident response protocol. |

---

## Part 4 — C-Component Engineering Map

### 4.1 C1 — ML Failure Classifier
**Status: NO CHANGE**

C1 performs real-time classification of payment failure type at sub-50ms latency using the GraphSAGE+TabTransformer architecture. P3 v0 consumes C1's output identically to the direct bank deployment. The classifier does not need to know whether the request originated from a direct bank integration or a processor-hosted MIPLO API — it processes `ClassifyRequest` schemas identically regardless of source.

Engineering work required: None.

### 4.2 C2 — PD Pricing Engine
**Status: MINOR — Tenant-Scoped Model Config (~1 week)**

C2's LightGBM PD model and CVA/LGD pricing engine are unchanged. The only extension is tenant-scoped model configuration — allowing different processors to use different model versions or corridor-specific calibrations.

New configuration structure:
```json
{
  "tenant_id": "FINASTRA_EU_001",
  "model_config": {
    "c2_model_version": "v2.3.1",
    "corridors_enabled": ["EU-APAC", "EU-NA", "EU-MENA"],
    "fee_floor_bps": 300,
    "fee_ceiling_bps": 500,
    "risk_bucket_overrides": {}
  }
}
```

Implementation: Add `tenant_model_config: Optional[Dict]` parameter to `C2PDModel.predict()`. If present, overrides global config. Falls back to global config if absent. This is a non-breaking change.

Engineering work required: 1 week (configuration layer + tests).

### 4.3 C3 — Settlement Monitor
**Status: EXTEND — Multi-Tenant Settlement Tracking (~2–3 weeks)**

C3 currently monitors UETR settlement via SWIFT gpi and triggers auto-repayment. P3 v0 requires C3 to track which tenant originated each bridge loan, so that settlement events are routed to the correct processor and the correct bank within that processor's tenant.

**C3 Extension 1: Tenant-Tagged Settlement Tracking (~1–2 weeks)**

Every bridge loan monitored by C3 must carry `tenant_id` and `sub_licensee_bic` in its tracking record. When C3 detects pacs.002 settlement, the repayment instruction is routed to the correct processor's C7 container via the MIPLO API (not directly to the bank).

New tracking record field:
```json
{
  "uetr": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenant_id": "FINASTRA_EU_001",
  "sub_licensee_bic": "COBADEFF",
  "loan_id": "BPI-MIPLO-20270714-0001",
  "originated_at": "2027-07-14T08:02:00Z",
  "expected_settlement_hours": 7.05,
  "status": "MONITORING"
}
```

**C3 Extension 2: Per-Tenant NAV Event Feed (~1 week)**

C3 emits an aggregated pool-level event every 60 minutes per tenant — identical to the P7 NAV Event Feed, but scoped to the processor tenant rather than the Luxembourg SV compartment. This feeds the processor's dashboard and BPI's revenue metering.

```json
{
  "tenant_id": "FINASTRA_EU_001",
  "active_loans": 47,
  "total_exposure_usd": 28400000,
  "settled_last_60min": 12,
  "settled_amount_last_60min_usd": 7200000,
  "trailing_loss_rate_30d": 0.0041,
  "timestamp": "2027-07-14T10:00:00Z"
}
```

### 4.4 C4 — Dispute Classifier
**Status: NO CHANGE (~2 days output routing)**

C4's adversarial camt.056 classifier already detects and classifies cancellation intent. P3 v0 adds one output routing rule: include `tenant_id` in the dispute classification result so downstream C7 knows which processor/bank to notify. The ML model, feature pipeline, and threshold logic are unchanged.

Engineering work required: 1–2 days (routing configuration only).

### 4.5 C5 — ISO 20022 Processor
**Status: NO CHANGE**

C5 parses all relevant ISO 20022 message types (pacs.002, pacs.008, camt.056, camt.029, camt.055). P3 v0 introduces no new message types. The MIPLO API receives pre-parsed payment data from the processor — C5 is invoked inside the container to normalise it.

Engineering work required: None.

### 4.6 C6 — AML / Security Module
**Status: EXTEND — Cross-Tenant Velocity Isolation (~2 weeks)**

C6 currently handles velocity monitoring and cross-licensee anomaly detection via `CrossLicenseeAggregator` in `lip/c6_aml_velocity/cross_licensee.py`. P3 v0 adds a tenant isolation layer to prevent cross-tenant data leakage while maintaining the ability to detect cross-institutional patterns at the BPI level.

**C6 Extension: Tenant-Namespaced Velocity Counters**

Current architecture: velocity counters keyed by `SHA-256(tax_id + salt)`. Cross-licensee aggregation uses the same hash across all licensees.

P3 v0 architecture:
```
Intra-tenant velocity:  SHA-256(tax_id + salt + tenant_id)  → per-tenant counter
Cross-tenant velocity:  SHA-256(tax_id + salt)              → BPI-level counter (existing)
```

This ensures:
- Processor A cannot see Processor B's transaction patterns
- BPI can still detect cross-institutional velocity anomalies (e.g., same entity transacting through multiple processors)
- Salt rotation with 30-day overlap (existing `SaltRotationManager`) applies to both layers

New rule — **cross-processor structuring detection:**
```
IF same entity_hash appears in velocity counters of 2+ processor tenants
   within 24-hour window
   AND combined volume exceeds aml_dollar_cap_usd
THEN flag for CIPHER review (potential structuring across processors)
```

Implementation: Add `tenant_id` parameter to `CrossLicenseeAggregator.record()` and `.get_cross_licensee_volume()`. Dual-write to both tenant-scoped and BPI-scoped counters. CIPHER must review before merge.

### 4.7 C7 — Bank Integration Layer
**Status: EXTEND — Highest Engineering Effort (~6–8 weeks, 2 engineers)**

C7 currently handles secure API communication between Bridgepoint and the bank/ELO for loan disbursement. P3 v0 makes C7 the core of the MIPLO API gateway — the component that translates between the processor's request format and the internal `LIPPipeline`.

**C7 Extension 1: MIPLO API Gateway (~4–5 weeks)**

New FastAPI router mounted at `/api/v1/miplo/` that:
1. Validates C8 processor token on every request
2. Extracts `tenant_id` and `sub_licensee_bic` from token
3. Verifies `sub_licensee_bic` is in the token's authorised BIC list
4. Constructs `ClassifyRequest` schema from processor payload
5. Invokes `LIPPipeline.process()` with tenant-scoped configuration
6. Returns `ClassifyResponse` with offer details
7. Logs `DecisionLogEntryData` with `licensee_id = tenant_id`

Implementation: New file `lip/api/miplo_router.py`. Reuses existing `LIPPipeline` — does NOT duplicate C1/C2/C7 logic. Factory method `create_tenant_pipeline(tenant_config)` instantiates a scoped pipeline with tenant-specific C2 model config and C6 velocity namespace.

**C7 Extension 2: Processor Container Management (~2–3 weeks)**

Container lifecycle management for processor-hosted deployments:
- Encrypted model artifact pull from BPI registry (AES-256-GCM at rest, TLS 1.3 in transit)
- Heartbeat telemetry: container status, inference latency, model version, token validity
- Blue-green model deployment: new model loaded alongside old, traffic shifted after validation pass
- Auto-rollback: if p99 latency > 94ms or AUC < 0.80 for 5 consecutive minutes, revert to previous model

New endpoint: `POST /api/v1/miplo/admin/model-update` (BPI-only, internal auth)

### 4.8 C8 — Licensing & Metering Engine
**Status: EXTEND — Medium Engineering Effort (~3–4 weeks, 1 engineer)**

C8 currently handles per-licensee (bank) fee configuration and royalty metering. P3 v0 adds `PROCESSOR` as a new licensee type with distinct token fields and revenue metering logic.

**C8 Extension 1: Processor Token Type (~1–2 weeks)**

New fields in `LicenseToken`:
```python
licensee_type: str = "BANK"         # "BANK" | "PROCESSOR"
sub_licensee_bics: List[str] = []   # Authorised bank BICs (PROCESSOR only)
annual_minimum_usd: int = 0         # Annual minimum fee commitment
performance_premium_pct: float = 0  # % of above-baseline revenue
platform_take_rate_pct: float = 0   # Processor's take rate
```

New `ProcessorLicenseeContext` extending existing `LicenseeContext`:
```python
@dataclass
class ProcessorLicenseeContext(LicenseeContext):
    licensee_type: str = "PROCESSOR"
    sub_licensee_bics: List[str] = field(default_factory=list)
    annual_minimum_usd: int = 500000
    performance_premium_pct: float = 0.15
    platform_take_rate_pct: float = 0.20
```

**C8 Extension 2: Revenue Metering (~1 week)**

Per-processor revenue tracking:
```python
{
  "tenant_id": "FINASTRA_EU_001",
  "period": "2027-Q3",
  "transaction_count": 4721,
  "gross_fee_usd": 2360500.00,
  "processor_take_usd": 472100.00,
  "bpi_net_usd": 1888400.00,
  "annual_minimum_usd": 500000,
  "minimum_shortfall_usd": 0,
  "performance_baseline_usd": 1500000.00,
  "performance_premium_usd": 58260.00,
  "total_bpi_revenue_usd": 1946660.00
}
```

**C8 Extension 3: Annual Minimum Enforcement (~1 week)**

Auto-alert when trailing quarterly revenue < 25% of annual minimum (on track to miss).
Auto-invoice for shortfall at year-end if actual < minimum.
Dashboard: per-processor revenue vs minimum, updated hourly from C3 NAV Event Feed.

---

## Part 5 — Consolidated Engineering Timeline

### 5.1 Build Plan: Q1–Q3 2027

| Sprint | Weeks | Components | Deliverable | Owner |
|--------|-------|------------|-------------|-------|
| Sprint 1 | W1–W2 | C8 Extension 1 | Processor token type, ProcessorLicenseeContext, sub_licensee_bics validation | Backend Eng 1 |
| Sprint 2 | W3–W4 | C6 Extension | Cross-tenant velocity isolation, namespace partitioning, structuring detection | Backend Eng 2 |
| Sprint 3 | W5–W6 | C2 Minor + C4 Minor | Tenant-scoped model config, risk bucket routing, dispute output routing | Backend Eng 1 |
| Sprint 4 | W7–W10 | C7 Extension 1 | MIPLO API gateway: classify/price/execute/portfolio endpoints, tenant pipeline factory | Backend Eng 1 + 2 |
| Sprint 5 | W11–W12 | C7 Extension 2 | Container management: encrypted model pull, heartbeat, blue-green deployment | Backend Eng 2 |
| Sprint 6 | W13–W14 | C3 Extension | Multi-tenant settlement tracking, per-tenant NAV Event Feed | Backend Eng 1 |
| Sprint 7 | W15–W16 | C8 Extensions 2–3 | Revenue metering, annual minimum enforcement, performance premium calculation | Backend Eng 2 |
| Sprint 8 | W17–W18 | Integration test | End-to-end: processor token → MIPLO classify → price → execute → settle → meter | Both |

Total engineering effort: ~14–18 engineer-weeks, 2 senior engineers.
Calendar time: ~4.5 months from greenlight → Q3 2027 live pilot.

### 5.2 Parallel Legal & Commercial Track

| Milestone | Owner | Timeline |
|-----------|-------|----------|
| Draft Master Licensing Agreement template | BPI + patent counsel | W1–W4 |
| Initial outreach to Finastra FusionFabric.cloud partnership team | BPI commercial | W1–W2 |
| Negotiate processor evaluation agreement (sandbox access) | BPI commercial + legal | W3–W8 |
| Draft GDPR DPA (Article 28) | BPI legal + external DPO | W4–W6 |
| Draft DORA sub-outsourcing addendum (Article 29) | BPI legal + DORA counsel | W6–W10 |
| PCI DSS scope assessment (determine if BPI needs SAQ or full RoC) | BPI + PCI QSA | W4–W8 |
| Processor technical evaluation / sandbox integration | BPI engineering + processor | W8–W14 |
| First processor contract signed | BPI commercial + legal | W14–W16 |
| Pilot: 1–3 banks via processor, one corridor, €5–25M volume cap | All tracks | W17–W18+ |

### 5.3 Processor Targeting Priority

| Priority | Processor | Rationale | Estimated Banks Unlocked |
|----------|-----------|-----------|-------------------------|
| 1 | **Finastra** | FusionFabric.cloud most open ecosystem (65+ APIs); FusionGlobal PAYplus is ISO 20022-native; 8,000+ bank clients | 500+ initially |
| 2 | **FIS Global** | Code Connect API Marketplace; Fintech Accelerator selects 10 startups/year; 650+ institutions | 300+ |
| 3 | **Temenos** | SCALE Developer Program; Quality certification via The Disruption House; 800+ bank clients | 400+ |

---

## Part 6 — What Stays in the Long-Horizon P3 Patent

The following features are not built in P3 v0. They are disclosed in Future Technology Disclosure v2.1 Extension F and will be claimed in the P3 continuation filing (Year 2–3).

| Feature | Why Not in 2027 | Target Filing Window |
|---------|----------------|---------------------|
| Embedded ERP/TMS deployment (BPI runs inside corporate's ERP) | ERP integration requires per-vendor connectors not yet built (SAP, Oracle, D365) | Year 3–4 (after P4 ERP connector stubs mature) |
| Adversarial camt.056 independent claims (broader than D13) | C4 LLM backend (Qwen3-32b via Groq) needs production validation before standalone patent claims | Year 2–3 (file with P3 continuation) |
| Cross-processor federated learning (P12 overlap) | Insufficient multi-processor deployment data; privacy framework immature | Year 9 (P12 filing window) |
| Real-time competitive bidding across processors (multi-processor arbitrage) | Only 1 processor in Phase 1; competitive dynamics require 3+ processors | Year 5–6 |

Critical strategic note: P3 v0 launched in 2027 does NOT limit P3 patent claims. The continuation patent covers the full multi-party architecture including embedded ERP deployment and adversarial cancellation as standalone claims. P3 v0 is a commercial product using a subset of the patented architecture — it strengthens the patent by providing commercial evidence of utility while the broader claims are prosecuted.

---

## Part 7 — Risk Register (P3 v0 Specific)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Processor demands source code or model weights access | High | Critical | Container-only deployment: processor runs BPI binary, never sees source. Model artifacts encrypted with BPI-controlled keys (AES-256-GCM). C8 token + HMAC validation means container is inoperable without BPI's signing key. MLA explicitly prohibits reverse engineering. |
| Cross-tenant data leakage between processor banks | Low | Critical | Four-layer isolation (L1-L4 per §2.4). CIPHER mandatory review before deployment. Annual penetration testing by independent security firm. GDPR Article 33 breach notification process documented in DPA. |
| PCI DSS scope expansion (BPI processes cardholder data) | Medium | High | BPI processes payment metadata only (BICs, amounts, rejection codes) — NOT cardholder data. Design for PCI DSS scope exclusion via data minimisation. If scope cannot be excluded, pursue SAQ-D (self-assessment) initially, full RoC in Phase 2. PCI DSS 4.0 mandatory since March 2025. |
| Processor take rate negotiation exceeds 30% | Medium | Medium | Annual minimum guarantees BPI floor revenue regardless of take rate. Performance premium incentivises volume growth, which dilutes take rate impact. Walk-away threshold: 35% take rate makes economics unviable at mid-tier bank volumes. |
| DORA CTPP designation triggers regulatory oversight | Low | Medium | Initially non-critical: first 19 CTPPs designated November 2025 are all hyperscalers (AWS, Google, Microsoft, Oracle, SAP). BPI's market share is too small for CTPP designation in 2027. Design for CTPP compliance from day 1 as a moat — competitors will face same requirements later. |
| P3 patent filing delayed past first public deployment | Medium | Critical | P3 MUST be filed before first processor partnership is publicly announced (Akamai doctrine). Filing window: Year 2–3 from provisional. Commercial deployment can proceed under NDA / white-label before public announcement. Patent attorney must be engaged by W1 of engineering timeline. |
| Processor becomes dependent then demands exclusivity | Medium | High | MLA includes non-exclusivity clause. BPI retains right to license to competing processors. Territory-limited exclusivity available as premium negotiation lever (e.g., exclusive in APAC for 2 years at higher annual minimum). |
| Model drift in processor environment differs from direct deployment | Medium | Medium | Continuous drift monitoring via heartbeat telemetry. AUC and feature drift metrics reported to BPI every 60 seconds. Auto-alert if processor environment drift diverges from direct deployment by > 2 standard deviations. C1 model card (SR 11-7) updated per-tenant. |
| Processor bankruptcy or acquisition disrupts service | Low | High | DORA sub-outsourcing addendum includes exit strategy: 90-day transition period, data export rights, direct bank migration path. BPI can activate direct bank deployment for any bank within the processor's tenant within 30 days. |
| Competitor replicates embedded model (e.g., Feedzai launches equivalent) | Medium | Medium | P3 patent claims the three-entity API data flow as patentable subject matter. Any competitor implementing the same architecture infringes regardless of their ML model. First-mover advantage: 12–18 months of deployment data creates model accuracy gap that a new entrant cannot close without equivalent data. |

---

End of Document

---

Bridgepoint Intelligence Inc.
Internal Use Only — Strictly Confidential — Attorney-Client Privileged
Document ID: P3-v0-Implementation-Blueprint-v1.0.md
Date: March 27, 2026
Supersedes: N/A (first version)
Next review: Upon completion of Sprint 4 (MIPLO API Gateway) or material change in processor partnership negotiations
