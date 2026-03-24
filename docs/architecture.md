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
  Output: pd_score, fee_bps (ANNUALISED, floor 300 bps), tier, shap_values_c2

  maturity_days = _derive_maturity_days(rejection_code)
    Class A → 3 days, Class B → 7 days, Class C → 21 days

Step 4 — C7 (Execution Agent)
  Input:  payment_context dict
  Checks: kill_switch / KMS unavailability → HALT
          human override / risk controls   → DECLINE / PENDING_HUMAN_REVIEW
  Output: {status, loan_offer, decision_entry_id}

  if HALT   → return HALT
  if DECLINE → return DECLINED

Step 5 — C3 Registration (if FUNDED)
  PaymentStateMachine: FAILURE_DETECTED → BRIDGE_OFFERED → FUNDED
  LoanStateMachine:    OFFER_PENDING → ACTIVE
  Register ActiveLoan with SettlementMonitor
  → return FUNDED
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
