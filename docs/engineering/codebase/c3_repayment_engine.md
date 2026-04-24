# `lip/c3_repayment_engine/` + `lip/c3/` — Settlement Monitoring and Auto-Repayment

> **The component that watches the UETR after funding.** When C7 funds a bridge loan, it tells C3 "monitor this UETR and deregister the loan when settlement arrives." Everything past the loan-offer-accepted state is C3 territory.

**Source:** `lip/c3_repayment_engine/` (Python orchestration) + `lip/c3/rust_state_machine/` (PyO3 FSM)
**Module count:** 8 Python + 4 Rust, 2,144 LoC Python + ~500 Rust
**Test files:** 4 (`test_c3_{api,c4_c5_coverage,repayment,state_machine_bridge}.py`) + `test_settlement_bridge.py`
**Spec:** [`../specs/BPI_C3_Component_Spec_v1.0_Part1.md`](../specs/BPI_C3_Component_Spec_v1.0_Part1.md) + Part 2

---

## Purpose

C3 owns three responsibilities:

1. **Settlement monitoring** — poll the UETR (Unique End-to-End Transaction Reference) on each funded loan until the originating bank's payment settles or hits the maturity deadline.
2. **Auto-repayment** — when settlement is observed, deregister the loan, mark it `REPAID`, emit a repayment event.
3. **Rejection taxonomy** — the authoritative mapping of every ISO 20022 rejection code to CLASS_A / CLASS_B / CLASS_C / BLOCK, which determines the bridgeable maturity window.

C3 is the **only** component that spans the Python/Rust boundary twice — the state machine is a Rust PyO3 extension (`lip/c3/rust_state_machine/`), and the orchestration is Python (`repayment_loop.py`).

---

## Architecture

```
C7 ExecutionAgent (loan accepted)
        │  register(uetr, loan)
        ▼
┌──────────────────────────────────────┐
│  SettlementMonitor (Python)          │
│  lip/c3_repayment_engine/            │
│    repayment_loop.py                 │
│                                      │
│  In-memory + Redis-backed registry   │
│  of ActiveLoan records by UETR       │
└──────────────────────────────────────┘
        │  poll (1 Hz default) OR Kafka event
        ▼
┌──────────────────────────────────────┐
│  SettlementBridge                    │
│  settlement_bridge.py                │
│                                      │
│  Normalises settlement signals from  │
│  SWIFT / BIC-specific rails into a   │
│  uniform SettlementEvent             │
└──────────────────────────────────────┘
        │  handler dispatch
        ▼
┌──────────────────────────────────────┐
│  Rust FSM (PyO3)                     │
│  lip/c3/rust_state_machine/          │
│    state_machine.rs                  │
│                                      │
│  PaymentStateMachine:                │
│    PENDING → SETTLING → SETTLED      │
│    PENDING → OVERDUE                 │
│    ...                               │
└──────────────────────────────────────┘
        │  state transition events
        ▼
  LoanRepayment / LoanOverdue emitted
```

### Why Rust for the state machine

The FSM is called at high rate on the settlement monitor's 1Hz poll across potentially thousands of active loans. A pure-Python FSM would easily blow past the 94ms SLO under load because of GIL contention in a multi-replica deployment. Rust gives us:

- Sub-microsecond transition latency
- `parking_lot` locks for lockstep-safe concurrent access across threads
- DashMap for sharded concurrent hash table of `UETR → state`

The PyO3 bindings are in `lip/c3/rust_state_machine/src/pyo3_bindings.rs`. Build with `cd lip/c3/rust_state_machine && maturin develop --release`.

---

## The rejection taxonomy (`rejection_taxonomy.py`)

This is the **operative compliance policy** of the platform. Every ISO 20022 rejection code is classified into one of four classes:

| Class | Maturity | Bridgeable? | Examples |
|-------|----------|-------------|----------|
| CLASS_A | 3 days | yes | AC01 (incorrect account), AC04 (closed account), AC06 (blocked account), AM01-AM12 (amount errors), BE01, BE05, DT01, ED01 |
| CLASS_B | 7 days | **currently no** — block-all until pilot bank signs `hold_bridgeable` obligation (EPG-04/05) | Systemic / processing failures |
| CLASS_C | 21 days | yes | Investigation / complex cases |
| BLOCK | 0 days | **never** | DNOR, CNOR, RR01-RR04, AG01, LEGL — per EPG-19 |

Authority rule: **any change to a code's class assignment requires REX sign-off** because the BLOCK list IS the operative compliance policy. Promoting a code out of BLOCK without re-running the EPG-19 deliberation is a refusal-grade error.

The BLOCK list must also never appear enumerated in any published patent claim (EPG-21 language-scrub rule).

### CLASS_B label warning

`SETTLEMENT_P95_CLASS_B_HOURS = 53.58` was historically mislabeled as "compliance/AML holds." This was wrong — CLASS_B covers systemic/processing delays only. Compliance-hold payments are BLOCK, not CLASS_B. The label was corrected in `constants.py` in 2026-03, but the 53.58h value must not be used to calibrate compliance-hold resolution expectations.

---

## UETR mapping (`uetr_mapping.py`)

Every funded loan is indexed by its originating-payment UETR. The mapping is:

```
UETR → (loan_id, funded_at, maturity_deadline, state)
```

Persistent storage: Redis hash `lip:c3:active_loans:<uetr>` with TTL = maturity + 45-day buffer (GAP-04). When settlement arrives, the entry is deleted atomically along with a repayment-event publish to Kafka topic `lip.c3.repayment`.

UETR deduplication (GAP-04) is enforced at the pipeline entry — if we see the same UETR twice within the TTL window, the second occurrence is logged as a retry and short-circuited, not processed again.

---

## Settlement handlers (`settlement_handlers.py`)

The `SettlementHandlerRegistry` dispatches normalised `SettlementEvent`s to the correct per-rail handler:

| Handler | Rail | Signal source |
|---------|------|---------------|
| `SWIFTSettlementHandler` | SWIFT pacs.008 confirmation | MT/MX message tracking |
| `ACHSettlementHandler` | US ACH | NACHA return/settlement file |
| `SEPASettlementHandler` | EU SEPA | SEPA settlement confirmation |
| `CHIPSSettlementHandler` | CHIPS | CHIPS participant message |
| `BlocksettlementHandler` | block-class catch-all (never bridged) | N/A |

5 default handlers are installed via `SettlementHandlerRegistry.install_defaults()`. Adding a new rail = one handler class + one `.register()` call.

---

## Corridor buffer (`corridor_buffer.py`)

SR 11-7 governance artifact — the four-tier bootstrap protocol for new BIC-pair corridors (Architecture Spec §11.4). When a corridor has fewer than 100 observations, the capital buffer is expanded:

| Bucket | Obs count | Buffer multiplier |
|--------|-----------|-------------------|
| Bootstrap | 0-25 | 3.0x |
| Early | 26-50 | 2.5x |
| Developing | 51-100 | 2.0x |
| Established | 101+ | 1.0x (canonical) |

This is a **statistical calculation, not a model** — so it's governed under this component spec, not under an SR 11-7 model governance document. See [`../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md).

---

## NAV emitter (`nav_emitter.py`)

Hourly thread that publishes `NAVEvent`s (net asset value snapshots) to the regulatory reporting pipeline. Used by P10 for the regulator-facing data product. Runs with `interval=3600s` by default — configurable via `LIP_NAV_EMIT_INTERVAL_SECONDS`.

Logged at boot: `"NAVEventEmitter thread started (interval=3600s)"`. If this line is missing from lip-api pod logs, the regulatory data product is missing hourly ticks.

---

## Consumers

| Consumer | How it uses C3 |
|----------|---------------|
| `lip/pipeline.py` | Calls `c3_monitor.register(uetr, loan)` after C7 accepts the offer |
| `lip/api/runtime_pipeline.py` | Constructs `SettlementMonitor` + `SettlementHandlerRegistry.install_defaults()` |
| `lip/c7_execution_agent/offer_delivery.py` | Reads `repayment_loop.finalize_accepted_offer` as the state-transition callback |
| `lip/p10_regulatory_data/` | Consumes NAV events for the regulator data product |

---

## What C3 does NOT do

- **Does not classify the payment** — that is C1 (failure prediction) + C4 (dispute). C3 operates on already-classified, already-bridged UETRs only.
- **Does not authorize loans** — that is C7. C3 sees loans only after they are funded.
- **Does not talk to banks** — the settlement signal comes from C5 Kafka streams or BIC-side APIs, not from C3's own HTTP calls.

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § step 4 (C3 activates after ELO acceptance)
- **Spec** — [`../specs/BPI_C3_Component_Spec_v1.0_Part1.md`](../specs/BPI_C3_Component_Spec_v1.0_Part1.md), [`Part 2`](../specs/BPI_C3_Component_Spec_v1.0_Part2.md)
- **Rust state machine migration** — [`../specs/c3_state_machine_migration.md`](../specs/c3_state_machine_migration.md)
- **EPG-19 compliance-hold bridging** — [`../../legal/decisions/EPG-19_compliance_hold_bridging.md`](../../legal/decisions/EPG-19_compliance_hold_bridging.md)
- **Constants** — `lip/common/constants.py` (`UETR_TTL_BUFFER_DAYS`, `SETTLEMENT_P95_CLASS_A_HOURS`, etc.)
