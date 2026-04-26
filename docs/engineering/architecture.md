# LIP Architecture Reference

## Algorithm 1: End-to-End Pipeline Processing Loop

**Source of truth**: `lip/pipeline.py` (`LIPPipeline.process`)
**Spec reference**: Architecture Spec v1.2 §3

For each payment event received from C5:

```
Step 1 — C1 (Failure Classifier)
  Input:  NormalizedEvent → payment_dict
  Output: failure_probability, above_threshold, shap_top20
  Gate:   if failure_probability ≤ τ* (0.110) → return BELOW_THRESHOLD (fast path)

Step 2 — C4 ∥ C6 (parallel, ThreadPoolExecutor max_workers=2)
  C4: DisputeClassifier.classify(rejection_code, narrative, amount, currency, counterparty)
      → dispute_class, hard_block
  C6: VelocityChecker.check(entity_id, amount, beneficiary_id)
      → VelocityResult(passed, reason, entity_id_hash, ...)

  Gate: if dispute_hard_block → return DISPUTE_BLOCKED
  Gate: if aml_hard_block     → return AML_BLOCKED

Step 3 — C2 (PD Model)
  Input:  payment_dict, borrower_dict
  Output: pd_score, fee_bps (ANNUALISED, rail-aware floor), tier, shap_values_c2

  Rail-aware maturity (Phase A, 2026-04-25):
    payment_context["rail"] is set by pipeline._derive_maturity_hours(event.rail).
    For known rails in RAIL_MATURITY_HOURS (SWIFT/SEPA/FEDNOW/RTP/CBDC_*),
    maturity_hours is read directly. Sub-day rails (< 48h) trigger the
    1200 bps FEE_FLOOR_BPS_SUBDAY floor; day-scale rails use the universal
    300 bps FEE_FLOOR_BPS floor. Both floors are additive — neither lowers
    the universal floor.

  maturity_days = _derive_maturity_days(rejection_code) [legacy fallback]
    Class A → 3 days, Class B → 7 days, Class C → 21 days

Step 3.5 — Cross-rail handoff detection (Phase C, 2026-04-25)
  Pre-step that runs after C5 normalisation, before C1: when a FedNow/RTP/SEPA
  event has a rejection_code AND UETRTracker.find_parent(event.uetr) returns
  a registered upstream SWIFT UETR, the result outcome is later labelled
  DOMESTIC_LEG_FAILURE (instead of OFFERED) and parent_uetr is added to
  loan_offer for cross-rail audit. The bridge offer is still issued —
  the underlying payment failure is real and bridgeable.

Step 4 — C7 (Execution Agent)
  Input:  payment_context dict (includes rail + maturity_hours per Phase A)
  Checks: kill_switch / KMS unavailability → HALT
          human override / risk controls   → DECLINE / PENDING_HUMAN_REVIEW
  Output: {status, loan_offer, decision_entry_id, delivery_id}

  _build_loan_offer reads payment_context["rail"]:
    - For known rails: maturity_date = funded_at + RAIL_MATURITY_HOURS[rail]
    - Loan offer dict carries rail + maturity_hours fields for downstream consumers
    - Defence-in-depth third gate: applicable_fee_floor_bps(maturity_hours)

  if HALT   → return HALT
  if DECLINE → return DECLINED
  if OFFER  → return OFFERED (or DOMESTIC_LEG_FAILURE if handoff parent found)

Step 5 — Offer Acceptance (if ELO accepts)
  PaymentStateMachine: BRIDGE_OFFERED → FUNDED
  LoanStateMachine:    OFFER_PENDING → ACTIVE
  Register ActiveLoan with SettlementMonitor only after acceptance.
  ActiveLoan.rail field drives _claim_repayment hour-precision TTL for
  sub-day rails; legacy day-scale rails preserve the existing TTL path.
```

## Three-Entity Model

| Entity | Acronym | Role |
|--------|---------|------|
| Money Lending Organisation | **MLO** | Capital provider; holds loan on balance sheet |
| Money In/Payment Lending Organisation | **MIPLO** | BPI technology platform operator |
| Execution Lending Organisation | **ELO** | Bank-side agent (implemented by C7) |

**Business model**: MIPLO (BPI) earns a **30% technology licensor royalty** on `fee_repaid_usd`. MLO/MIPLO/ELO split the remaining 70%.

## State Machines

### Payment State Machine (`common/state_machines.py §S6`)

```
MONITORING
  ├─→ FAILURE_DETECTED
  │     ├─→ BRIDGE_OFFERED
  │     │     ├─→ FUNDED
  │     │     │     ├─→ REPAID ✓
  │     │     │     ├─→ BUFFER_REPAID ✓
  │     │     │     ├─→ DEFAULTED ✓
  │     │     │     └─→ REPAYMENT_PENDING
  │     │     │             ├─→ REPAID ✓
  │     │     │             ├─→ BUFFER_REPAID ✓
  │     │     │             └─→ DEFAULTED ✓
  │     │     ├─→ OFFER_DECLINED ✓
  │     │     └─→ OFFER_EXPIRED ✓
  │     ├─→ DISPUTE_BLOCKED ✓
  │     └─→ AML_BLOCKED ✓
  ├─→ DISPUTE_BLOCKED ✓
  └─→ AML_BLOCKED ✓
```
`✓` = terminal state (no outgoing transitions)

### Loan State Machine (`common/state_machines.py §S7`)

```
OFFER_PENDING
  ├─→ ACTIVE
  │     ├─→ REPAYMENT_PENDING
  │     │     ├─→ REPAID ✓
  │     │     ├─→ BUFFER_REPAID ✓
  │     │     └─→ DEFAULTED ✓
  │     ├─→ DEFAULTED ✓
  │     └─→ UNDER_REVIEW
  │             ├─→ ACTIVE
  │             └─→ DEFAULTED ✓
  ├─→ OFFER_EXPIRED ✓
  └─→ OFFER_DECLINED ✓
```

## Canonical Constants Table

> **All constants below require QUANT sign-off before modification.**

| Constant | Value | File | Significance |
|----------|-------|------|-------------|
| `τ*` (failure threshold) | **0.110** | `pipeline.py` | F2-optimal decision gate (calibrated) |
| Fee floor | **300 bps** annualised | `constants.py` | Minimum bridge loan fee |
| Latency SLO (p99) | **≤ 94 ms** | `constants.py` | End-to-end pipeline SLO |
| UETR TTL buffer | **45 days** | `constants.py` | Beyond maturity deduplication |
| Platform royalty | **30%** of fee | `constants.py` | BPI technology licensor share |
| Salt rotation | **365 days** | `constants.py` | AML entity hash rotation |
| Salt overlap | **30 days** | `constants.py` | Dual-salt transition window |
| Decision log retention | **7 years** | `constants.py` | SR 11-7 / EU AI Act retention |

## Redis Key Schema

All keys namespaced under `lip:` prefix.

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `lip:embedding:{currency_pair}` | 7 days | Corridor embeddings for C1 |
| `lip:uetr_map:{end_to_end_id}` | — | UETR deduplication index |
| `lip:velocity:{entity_id}:{window}` | 24 h | C6 velocity counters (hashed entity) |
| `lip:beneficiary:{entity_id}:{beneficiary_id}:{window}` | 24 h | C6 beneficiary counters |
| `lip:loan:{loan_id}` | 90 days | Active loan state |
| `lip:salt:current` | 365 days | Current C6 AML salt |
| `lip:salt:previous` | 30 days | Previous salt (overlap window) |
| `lip:kill_switch` | No TTL | `'ACTIVE'` string when engaged |

## Kafka Topic Map

| Topic | Partitions | Retention | Key |
|-------|-----------|-----------|-----|
| `lip.payment.events` | 24 | 7 days | `uetr` |
| `lip.failure.predictions` | 12 | 7 days | `uetr` |
| `lip.settlement.signals` | 24 | 7 days | `uetr` |
| `lip.dispute.results` | 6 | 7 days | `uetr` |
| `lip.velocity.alerts` | 6 | 7 days | `uetr` |
| `lip.loan.offers` | 6 | 7 days | `uetr` |
| `lip.repayment.events` | 6 | 7 days | `uetr` |
| `lip.decision.log` | 12 | **7 years** | `uetr` |
| `lip.dead.letter` | 6 | 7 days | `uetr` |
| `lip.stress.regime` | 6 | 7 days | `corridor` |

## Patent Claims Mapping

| Patent Claim | LIP Component | Description |
|-------------|--------------|-------------|
| Claims 1(a–h) | Full pipeline | Detection → bridge offer → auto-repayment |
| Claims 2(i–vi) | C1–C8 | System architecture components |
| Claims 3(k–n) | C2, C3 | Bridge loan instrument structure |
| Claims 5(t–x) | C3 | Settlement-confirmation auto-repayment loop |
| Dependent Claims D1–D11 | C1, C2, C3, C5 | ISO 20022, F-beta threshold, tiered PD, UETR tracking |

**Patent moat**: JPMorgan US7089207B1 covers Tier 1 (listed counterparties) only. LIP's Tier 2+3 (private counterparties using Damodaran and Altman Z' models) is the core patent contribution and constitutes the primary competitive moat.
