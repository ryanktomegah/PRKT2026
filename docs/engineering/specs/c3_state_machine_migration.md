# C3 Repayment Engine — State Machine Migration: Python → Rust via PyO3

**Status:** Implemented  
**Author:** LIP Engineering  
**Date:** 2026-04-02  
**Priority:** 2 (approved migration sequence — after C7 Kill Switch)

---

## 1. Context and Motivation

The C3 repayment engine's payment lifecycle state machine was previously implemented
in pure Python (`lip/common/state_machines.py`). While functionally correct, Python's
dynamic dispatch leaves illegal state transitions representable at runtime — a silent
failure mode that is unacceptable for financial state transitions.

This migration ports the state machine core, rejection taxonomy, and ISO 20022 message
field extraction to Rust, exposed to the Python orchestration layer via PyO3. Key goals:

- **Illegal transitions unrepresentable**: Rust enum with exhaustive `match` + `Result` return.
- **Fail-closed**: Any error in Rust core surfaces as an explicit Python exception — never
  silently downgrades.
- **Audit robustness**: Rust's deterministic semantics eliminate a class of timing-dependent
  bugs that are difficult to reproduce and audit.
- **Operational correctness**: Watchdog timer detects payments stuck in non-terminal states
  beyond their TTL (complements the representational correctness of the Rust enum).

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Python Orchestration Layer (agent.py, repayment_loop.py, …)   │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐    │
│   │  lip/c3/state_machine_bridge.py  (StateMachineBridge)  │    │
│   │  • Graceful fallback: Rust → pure Python               │    │
│   │  • PaymentWatchdog: stuck-state detection + alerting   │    │
│   └───────────────────────┬────────────────────────────────┘    │
│                            │ PyO3 FFI                           │
│   ┌────────────────────────▼────────────────────────────────┐   │
│   │  lip_c3_rust_state_machine  (compiled .so)              │   │
│   │  ┌──────────────────┐  ┌────────────┐  ┌────────────┐   │   │
│   │  │ state_machine.rs │  │ taxonomy.rs│  │ iso20022.rs│   │   │
│   │  │ PaymentState     │  │ Rejection  │  │ Camt054    │   │   │
│   │  │ transition()     │  │ Class      │  │ Pacs008    │   │   │
│   │  │ TransitionError  │  │ classify() │  │ extractors │   │   │
│   │  └──────────────────┘  └────────────┘  └────────────┘   │   │
│   └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Rust Crate: `lip/c3/rust_state_machine/`

| File | Responsibility |
|------|---------------|
| `Cargo.toml` | Crate manifest: pyo3, thiserror, serde, quick-xml |
| `src/lib.rs` | PyO3 module entrypoint; re-exports all PyO3 classes |
| `src/state_machine.rs` | `PaymentState` enum, `transition()`, `TransitionError` |
| `src/taxonomy.rs` | `RejectionClass` enum, `REJECTION_CODE_TAXONOMY`, `classify()` |
| `src/iso20022.rs` | `Camt054Fields`, `Pacs008Fields` structs + field extraction |
| `src/pyo3_bindings.rs` | `PyPaymentStateMachine`, `py_classify_*`, `py_extract_*` |

### 2.2 Python Bridge: `lip/c3/state_machine_bridge.py`

- **`StateMachineBridge`**: Unified API. Tries the compiled Rust module; falls back to
  `lip.common.state_machines` + `lip.c3_repayment_engine.rejection_taxonomy`.
- **`PaymentWatchdog`**: Background thread. Monitors `{uetr: (state, timestamp)}` store.
  Flags stuck payments. Emits Prometheus gauge. Fires PagerDuty alert.

---

## 3. State Machine Design

### 3.1 PaymentState Enum

```
MONITORING → FAILURE_DETECTED → BRIDGE_OFFERED → FUNDED → REPAYMENT_PENDING → REPAID
                                                         ↘ BUFFER_REPAID
                                                         ↘ DEFAULTED
                                 ↘ OFFER_DECLINED
                                 ↘ OFFER_EXPIRED
           → DISPUTE_BLOCKED (terminal)
           → AML_BLOCKED (terminal)
                                          ↘ CANCELLATION_ALERT → REPAID / DEFAULTED / FUNDED
```

### 3.2 Transition Table

| From | Allowed Targets |
|------|----------------|
| `MONITORING` | `FAILURE_DETECTED`, `DISPUTE_BLOCKED`, `AML_BLOCKED` |
| `FAILURE_DETECTED` | `BRIDGE_OFFERED`, `DISPUTE_BLOCKED`, `AML_BLOCKED` |
| `BRIDGE_OFFERED` | `FUNDED`, `OFFER_DECLINED`, `OFFER_EXPIRED` |
| `FUNDED` | `REPAID`, `BUFFER_REPAID`, `DEFAULTED`, `REPAYMENT_PENDING`, `CANCELLATION_ALERT` |
| `REPAYMENT_PENDING` | `REPAID`, `BUFFER_REPAID`, `DEFAULTED` |
| `CANCELLATION_ALERT` | `REPAID`, `DEFAULTED`, `FUNDED` |
| Terminal states | ∅ (no transitions) |

**Terminal states**: `REPAID`, `BUFFER_REPAID`, `DEFAULTED`, `OFFER_DECLINED`,
`OFFER_EXPIRED`, `DISPUTE_BLOCKED`, `AML_BLOCKED`

### 3.3 Fail-Closed Contract

```rust
pub fn transition(&self, target: PaymentState) -> Result<PaymentState, TransitionError>
```

- Returns `Ok(new_state)` on success.
- Returns `Err(TransitionError { from, to })` on illegal transition.
- **Never panics** — all match arms are exhaustive.
- PyO3 layer converts `TransitionError` → `ValueError` in Python.

---

## 4. Rejection Taxonomy Classification

The Rust `taxonomy.rs` mirrors `lip/c3_repayment_engine/rejection_taxonomy.py` exactly.

```rust
pub enum RejectionClass { ClassA, ClassB, ClassC, Block }

pub fn classify(code: &str) -> Result<RejectionClass, UnknownCodeError>
pub fn maturity_days(cls: RejectionClass) -> u32
pub fn is_block(code: &str) -> bool
```

All 80+ SWIFT codes from the Python taxonomy are ported. Unknown codes raise `ValueError`
in Python (via `UnknownCodeError` → PyO3 conversion).

---

## 5. ISO 20022 Parsing

### 5.1 Message Types

| Message | Standard | Handler |
|---------|----------|---------|
| `camt.054` | SWIFT BankToCustomerDebitCreditNotification | `extract_camt054_fields()` |
| `pacs.008` | ISO 20022 FI-to-FI Customer Credit Transfer | `extract_pacs008_fields()` |

### 5.2 Extracted Fields

**camt.054:**
- `uetr` — Unique End-to-End Transaction Reference
- `individual_payment_id` — EndToEndId
- `amount` — transaction amount (string, decimal-safe)
- `currency` — ISO 4217 currency code
- `settlement_time` — ISO 8601 datetime string
- `rejection_code` — ISO 20022 rejection reason code (optional)

**pacs.008:**
- `uetr` — UETR
- `end_to_end_id` — EndToEndId
- `amount` — IntrBkSttlmAmt
- `currency` — currency code
- `settlement_date` — IntrBkSttlmDt
- `debtor_bic` — DbtrAgt BIC
- `creditor_bic` — CdtrAgt BIC

### 5.3 Known Limitations

| Limitation | Affected Rails | Impact |
|------------|---------------|--------|
| Dict-based extraction only; no XML string parsing | All | Raw XML strings must be pre-parsed to dict by Python layer |
| SEPA namespace variations (`urn:iso:std:iso:20022:...` vs `xmlns:...`) | SEPA | Field paths may differ; Python layer SEPA handler remains authoritative |
| FedNow pacs.002 vs pacs.008 message type differences | FedNow | `extract_pacs008_fields` expects pacs.008 structure; FedNow status confirmations are pacs.002 |
| RTP partial settlement not modeled | RTP | Partial settlement amounts not broken out; full amount assumed |
| serde-xml-rs XML parsing is not used for production paths | All | XML→dict conversion remains in Python for all rail handlers |

### 5.4 Error Handling

All field extraction errors in Rust return `PyValueError` with a structured message:
```
ValueError: camt.054 field extraction failed: missing required field 'uetr'
```
Python callers must handle `ValueError` on all parse calls.

---

## 6. PyO3 Interface Contract

### 6.1 Classes

#### `PyPaymentStateMachine`

```python
class PyPaymentStateMachine:
    def __init__(self, initial_state: str = "MONITORING") -> None: ...
    @property
    def current_state(self) -> str: ...
    @property
    def is_terminal(self) -> bool: ...
    def transition(self, new_state: str) -> None:
        """Raises ValueError on illegal transition."""
    def allowed_transitions(self) -> list[str]: ...
```

### 6.2 Functions

```python
def classify_rejection_code(code: str) -> str:
    """Return rejection class name: 'CLASS_A', 'CLASS_B', 'CLASS_C', or 'BLOCK'.
    Raises ValueError for unknown codes."""

def maturity_days_for_class(rejection_class: str) -> int:
    """Return maturity window in days for a rejection class string."""

def is_block_code(code: str) -> bool:
    """Return True if code maps to BLOCK class."""

def extract_camt054_fields(raw_message: dict) -> dict:
    """Extract normalised fields from a camt.054 dict.
    Raises ValueError on parse failure."""

def extract_pacs008_fields(raw_message: dict) -> dict:
    """Extract normalised fields from a pacs.008 dict.
    Raises ValueError on parse failure."""
```

### 6.3 Exceptions

| Rust Error | Python Exception | Trigger |
|------------|-----------------|---------|
| `TransitionError` | `ValueError` | Illegal state transition |
| `UnknownCodeError` | `ValueError` | Unknown rejection code |
| `ExtractionError` | `ValueError` | Missing/malformed ISO 20022 field |
| `InvalidStateError` | `ValueError` | Unknown state string passed to constructor |

---

## 7. Watchdog Timer

### 7.1 Design

```python
class PaymentWatchdog:
    """Background thread that flags payments stuck in non-terminal states.

    Checks every `poll_interval_s` seconds. For each tracked payment:
    - If state is terminal: skip.
    - If age > ttl_seconds[state_class]: flag as stuck.
      Emit Prometheus metric + fire PagerDuty alert.
    """
```

### 7.2 TTL Configuration

| State | Default TTL |
|-------|------------|
| `MONITORING` | 2 × Class A maturity = 6 days |
| `FAILURE_DETECTED` | 2 × Class A maturity = 6 days |
| `BRIDGE_OFFERED` | 24 hours (offer window) |
| `FUNDED` | 2 × Class C maturity = 42 days |
| `REPAYMENT_PENDING` | 2 × Class B maturity = 14 days |
| `CANCELLATION_ALERT` | 2 × Class B maturity = 14 days |

TTLs are configurable at runtime via `PaymentWatchdog(ttl_overrides={...})`.

### 7.3 Alerting

**Prometheus metric** (emitted if `prometheus_client` is installed):
```
lip_c3_stuck_payments_total{state="FUNDED", corridor="USD_EUR"} 1
```

**PagerDuty alert** (fired via Events API v2 if `pagerduty_routing_key` is set):
```json
{
  "routing_key": "<key>",
  "event_action": "trigger",
  "payload": {
    "summary": "LIP C3: payment UETR <x> stuck in FUNDED for >42d",
    "severity": "critical",
    "source": "lip-c3-watchdog"
  }
}
```

---

## 8. Build Instructions

### 8.1 Development Build

```bash
# From repo root
cd lip/c3/rust_state_machine
maturin develop           # installs into current virtualenv
```

### 8.2 Release Build

```bash
maturin build --release   # produces .whl in target/wheels/
pip install target/wheels/lip_c3_rust_state_machine-*.whl
```

### 8.3 CI/CD Integration

The Python bridge (`state_machine_bridge.py`) gracefully falls back to pure Python
when the compiled Rust module is unavailable. CI pipelines that don't include a Rust
build step will still pass all Python tests via the fallback path.

To enable Rust builds in CI, add:
```yaml
- name: Install maturin
  run: pip install maturin
- name: Build Rust extension
  run: cd lip/c3/rust_state_machine && maturin develop
```

---

## 9. Definition of Done Checklist

- [x] Spec committed: `docs/specs/c3_state_machine_migration.md`
- [x] Rust crate: `lip/c3/rust_state_machine/` (compiles with `maturin develop`)
- [x] PyO3 bindings: all functions listed in §6 exposed
- [x] Python bridge: `lip/c3/state_machine_bridge.py` with fallback + watchdog
- [x] Rust unit tests: state machine, taxonomy, ISO 20022 extractors
- [x] Python test suite: `lip/tests/test_c3_state_machine_bridge.py`
- [x] Ruff lint: zero errors
- [x] All existing tests pass (no regressions)
- [ ] CIPHER sign-off: audit log correctness (pending pilot bank deployment)
- [ ] QUANT sign-off: latency SLO — Rust core < 1ms per transition (benchmark pending)

---

## 10. References

- Architecture Spec v1.2, Sections S6, S7, S8, S11.4
- PyO3 User Guide: https://pyo3.rs/
- ISO 20022 camt.054.001.xx
- ISO 20022 pacs.008.001.xx
- EPG-09/10/14/16/17/18/19 — EPIGNOSIS Architecture Review (2026-03-18)
