# `lip/common/` — Shared Infrastructure

> **The shared layer underneath every component.** If a piece of code is used by more than one of C1–C8, it lives here. Touching anything in `common/` ripples through the whole platform — read the relevant component README and `CLAUDE.md` rules before making changes.

**Source:** `lip/common/`
**Module count:** 23 modules + `__init__.py`

---

## Purpose

`lip/common/` exists to enforce consistency across components that would otherwise drift. Schemas, state machines, constants, encryption, and the registries (borrower, known-entity) all live here so that no component can disagree with another about what a `LoanOffer` looks like or how a `PaymentState` may transition.

The module-level docstring describes itself as: *"shared utilities, schemas, constants, state machines, and cryptographic helpers."* That is accurate, but understates how much of the operative business logic also lives here — `business_calendar`, `borrower_registry`, `swift_disbursement`, `royalty_settlement`, `regulatory_reporter` are not utilities; they are subsystems in their own right that simply happen to be shared.

---

## Module groups

### 1. Schemas — the wire format

| File | Purpose |
|------|---------|
| `schemas.py` | All Pydantic models that cross component boundaries: `LoanOffer`, `LoanOfferDelivery`, `LoanOfferAcceptance`, `LoanOfferRejection`, `LoanOfferExpiry`, `OfferExpiryReason`, `ClassifyRequest/Response`, `PDRequest/Response`, `DisputeRequest/Response`, `VelocityRequest/Response`, `ExecutionConfirmation`, `SettlementSignal`, `RepaymentConfirmation`, `DecisionLogEntry`, `FeeAllocation`, `TenantContext`, `NAVEvent`, `RevenueRecord`. **Anything that crosses a component boundary is defined here.** |
| `constants.py` | Canonical numeric constants used at runtime: τ\*, fee floor, latency SLO, UETR TTL, salt rotation, AML caps. Mirror of `lip/configs/canonical_numbers.yaml` for code that cannot read YAML at startup. **Locked — see `CLAUDE.md` § Canonical Constants.** |

### 2. State machines

| File | Purpose |
|------|---------|
| `state_machines.py` | `PaymentState`, `PaymentStateMachine`, `LoanState`, `LoanStateMachine`, `InvalidTransitionError`. Every state transition in C3 (loan lifecycle) and the pipeline (payment lifecycle) goes through these classes — direct mutation is not allowed. |

### 3. Identity & registries

| File | Purpose |
|------|---------|
| `borrower_registry.py` | `BorrowerRegistry` — the enrolled-borrower lookup that C7 checks **first** in `process_payment`. If the originating bank BIC is not enrolled (no signed MRFA recorded), the offer is refused with `BORROWER_NOT_ENROLLED`. Closes GAP-03. |
| `known_entity_registry.py` | Lookup for known counterparty entities (used in C2 tier assignment, C6 sanctions cross-reference) |

### 4. Cryptography & licensing

| File | Purpose |
|------|---------|
| `encryption.py` | Symmetric encryption helpers; KMS abstractions used by C7's KMS gate |
| `redis_factory.py` | Centralised Redis client construction so TLS / cluster / standalone modes are configured in one place |

### 5. Time & jurisdiction

| File | Purpose |
|------|---------|
| `business_calendar.py` | `add_business_days`, `currency_to_jurisdiction` — closes GAP-09 (calendar-day maturities misfiring on non-business days). Maturity windows (CLASS_A=3d, CLASS_B=7d, CLASS_C=21d) are computed here. |
| `governing_law.py` | `bic_to_jurisdiction()` derives governing law from BIC chars 4–5 (the SWIFT country code), **not** from payment currency. Implements EPG-14 — see [`../decisions/EPG-14_borrower_identity.md`](../decisions/EPG-14_borrower_identity.md). |

### 6. Settlement & money movement

| File | Purpose |
|------|---------|
| `uetr_tracker.py` | `UETRTracker` — Redis-backed retry detection with rolling-window cleanup and tuple-based dedup `(sending_bic, receiving_bic, amount, currency)`. Closes GAP-04. 30-min default TTL. |
| `swift_disbursement.py` | SWIFT MT-format disbursement message construction (closes GAP-06). The bridge funds always go to the receiver in the original payment amount; fees are collected at repayment via C3 sweep, never deducted from disbursement principal (GAP-17). |
| `partial_settlement.py` | Partial settlement reconciliation (closes GAP-16) |
| `royalty_settlement.py` / `royalty_batch.py` | `BPIRoyaltySettlement` monthly batch (closes GAP-05). Triggered from C3 repayment callback — collects 15% platform royalty on `fee_repaid_usd`. |
| `fx_risk_policy.py` | FX risk policy hooks for cross-currency corridors (closes GAP-12 scaffold; policy choice still open — see [`../OPEN_BLOCKERS.md`](../OPEN_BLOCKERS.md)) |

### 7. Stability & quality

| File | Purpose |
|------|---------|
| `circuit_breaker.py` | Generic circuit breaker for downstream calls (used by C4 LLM backend, C7 bank-side delivery, C5 Kafka) |
| `drift_detector.py` | Feature/output drift monitoring for C1 / C2 (SR 11-7 ongoing monitoring requirement) |
| `conformal.py` | Conformal prediction helpers — calibration intervals for C1 / C2 / C9 |
| `deployment_phase.py` | Phase tagging — pilot vs. production vs. paused; controls which gates are active |

### 8. Notification & reporting

| File | Purpose |
|------|---------|
| `notification_service.py` | `NotificationService` + `NotificationEventType` — the customer-facing event bus (closes GAP-13) |
| `regulatory_reporter.py` | `RegulatoryReporter`, `DORAAuditEvent` (4h / 24h thresholds, `within_threshold` property), `SR117ModelValidationReport` (AUC ≥ 0.75 validation gate), `DORASeverity` enum. Closes GAP-14. |
| `regulatory_export.py` | Export adapters for `regulatory_reporter` outputs into the formats regulators actually consume |

---

## Public API

Per `lip/common/__init__.py`:

```python
from lip.common import constants, encryption, schemas, state_machines
__all__ = ["constants", "schemas", "state_machines", "encryption"]
```

The `__init__.py` re-exports only the four most foundational modules. Everything else is imported directly by callers, e.g. `from lip.common.borrower_registry import BorrowerRegistry`.

## Dependency direction

`lip/common/` is a **leaf** in the dependency graph. It must not import from any `c{N}_*` component or from the patent-family modules (`p5_cascade_engine`, `p10_regulatory_data`, `c9_settlement_predictor`). Doing so creates circular imports and is rejected at code review.

The reverse is allowed and expected: every component imports from `lip/common/`.

## Cross-references

- **Constants source of truth**: `lip/configs/canonical_numbers.yaml` ([`configs.md`](configs.md))
- **Audit trail entries**: `DecisionLogEntry` in `schemas.py` is the canonical structure used by every `PipelineResult`
- **Operative decisions that constrain this layer**: EPG-14 (governing law), EPG-16/17 (AML caps), EPG-23 (`class_b_eligible=False` pre-wired in `LoanOfferExpiry`)
- **Migration specs that touched this layer**: [`../specs/c3_state_machine_migration.md`](../specs/c3_state_machine_migration.md), [`../specs/c2_fee_formula_hardening.md`](../specs/c2_fee_formula_hardening.md)
