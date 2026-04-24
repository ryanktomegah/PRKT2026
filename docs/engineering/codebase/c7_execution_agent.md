# `lip/c7_execution_agent/` — Loan Execution Agent (ELO)

> **The component that turns a priced offer into a funded loan.** Every decision the pipeline makes upstream (C1 says "will fail," C4 says "no dispute," C6 says "no AML block," C2 says "fee = X bps") converges here. C7 is the last gate — kill switch, KMS, borrower registry, and stress-regime checks — and the last place a loan offer can be refused before it reaches the ELO for acceptance.

**Source:** `lip/c7_execution_agent/` (Python) + `lip/c7_execution_agent/go_offer_router/` (Go gRPC) + `lip/c7_execution_agent/rust_kill_switch/` (Rust PyO3)
**Module count:** 13 Python + Go router + Rust kill-switch, 3,332 LoC Python + ~2000 LoC Go + ~600 LoC Rust
**Test files:** 3 (`test_c7_{execution,go_router,offer_delivery}.py`) + `test_redis_atomic.py`
**Spec:** [`../specs/BPI_C7_Component_Spec_v1.0_Part1.md`](../specs/BPI_C7_Component_Spec_v1.0_Part1.md) + Part 2 + [`Bank Deployment Guide`](../specs/BPI_C7_Bank_Deployment_Guide_v1.0.md)

---

## Purpose

C7 is the **Execution Lending Organisation (ELO)** boundary — the bank-side agent that:

1. Receives the loan offer assembled by the pipeline
2. Runs final safety gates (kill switch, KMS reachable, borrower enrolled, known-entity tier override, compliance-hold defense layer 2)
3. Persists a signed decision log entry (7-year retention, HMAC integrity)
4. Delivers the offer to the bank's internal acceptance system
5. Finalises the loan on acceptance — triggers C3 settlement monitoring, publishes to Kafka

C7 is the **zero-outbound** component in the canonical bank deployment. Its container has no default outbound network access; only specific egress rules for Redis, KMS, and the internal gRPC acceptance endpoint.

---

## Architecture

```
      Pipeline-assembled LoanOffer
                │
                ▼
   ┌────────────────────────────────────┐
   │  ExecutionAgent.process_payment()  │
   │  agent.py                          │
   │                                    │
   │  Layer 2 compliance hold check:    │
   │  _COMPLIANCE_HOLD_CODES frozenset  │
   │  — EPG-19 defense-in-depth         │
   │                                    │
   │  KillSwitch check (Rust FSM)       │
   │  KMS reachability probe            │
   │  BorrowerRegistry enrolment check  │
   │  KnownEntityRegistry tier override │
   │  StressRegimeDetector signal       │
   └────────────────────────────────────┘
                │  offer approved
                ▼
   ┌────────────────────────────────────┐
   │  DecisionLogger                    │
   │  decision_log.py                   │
   │                                    │
   │  HMAC-SHA256 signed record         │
   │  7-year retention in Kafka topic   │
   │  lip.decisions.audit               │
   │  (EU AI Act Art.61 + SR 11-7)      │
   └────────────────────────────────────┘
                │
                ▼
   ┌────────────────────────────────────┐
   │  OfferDeliveryService              │
   │  offer_delivery.py                 │
   │                                    │
   │  HTTPS POST to bank acceptance     │
   │  endpoint (LIP_OFFER_DELIVERY_     │
   │  ENDPOINT) OR in-process callback  │
   └────────────────────────────────────┘
                │  bank accepts
                ▼
   ┌────────────────────────────────────┐
   │  Go gRPC Offer Router              │
   │  go_offer_router/                  │
   │                                    │
   │  Low-latency streaming offer       │
   │  delivery to multiple ELOs.        │
   │  Also hosts the gRPC kill-switch   │
   │  client.                           │
   └────────────────────────────────────┘
                │
                ▼
           C3 Settlement Monitoring begins
```

### Why mixed Python/Rust/Go

Each sub-component has a different latency / safety requirement:

| Sub-component | Language | Why |
|---------------|----------|-----|
| Orchestration (`agent.py`) | Python | Integration surface with the rest of the pipeline; needs to import from every other C* |
| Kill switch (`rust_kill_switch/`) | Rust PyO3 | Must survive process crashes + be readable by any attached watchdog; uses memory-mapped shared state |
| Offer router (`go_offer_router/`) | Go | Low-latency gRPC streaming to multiple ELOs; Go's goroutine scheduler outperforms Python asyncio at 10k+ concurrent streams |
| Redis atomic ops (`redis_atomic.py`) | Python + Lua | Compare-and-set + lease semantics on the kill switch state, atomic under Redis WATCH/MULTI |

---

## Kill switch (`kill_switch.py` + `rust_kill_switch/`)

The **refusal-grade safety boundary**. Any of the following engage the kill switch:

- C8 license validation failure at boot
- KMS endpoint unreachable
- Decision log HMAC failure (cannot sign)
- Borrower registry empty or unreadable
- Explicit operator call via admin API

### Engagement semantics

```python
KillSwitch.engage(reason: str) -> None
```

- Writes to the Rust shared-memory region so external watchdog processes can read
- Writes to Redis `lip:c7:kill_switch:engaged` with the reason
- Emits a Prometheus metric `lip_kill_switch_engaged{reason=...}`
- Logs at CRITICAL + emits DORA Art.19 incident if configured

Disengagement is **manual only** — requires an admin API call with a valid C8 LicenseeContext and an operator override token. There is no automatic recovery.

### Rust shared memory

`rust_kill_switch/src/shm.rs` uses `memmap2` to expose a 4KB region at `/dev/shm/lip_kill_switch`. Layout:

```
Offset 0-7:   magic number (0xDEADBEEF + version)
Offset 8-15:  engaged-at timestamp (ms since epoch)
Offset 16-23: reason length
Offset 24-N:  reason UTF-8 bytes
```

Watchdog processes (an external sidecar or an Argo Rollout gate) can mmap the same region and refuse to promote a release when the switch is engaged — without needing to reach the kill switch API.

---

## Decision log (`decision_log.py`)

Every loan decision produces a signed `DecisionLogEntry`:

```python
@dataclass(frozen=True)
class DecisionLogEntry:
    decision_id: str             # ULID
    uetr: str
    licensee_id: str
    tenant_id: Optional[str]
    outcome: str                 # FUNDED / DECLINED / COMPLIANCE_HOLD / PENDING_HUMAN_REVIEW / ...
    c1_failure_probability: float
    c4_dispute_class: str
    c6_aml_passed: bool
    c2_pd_score: float
    c2_fee_bps: int
    kill_switch_state: str       # at decision time
    signed_at: datetime          # tz-aware UTC
    hmac_signature: str          # hex SHA-256 over canonical_bytes
```

### Retention

- **Kafka topic** `lip.decisions.audit` with 7-year retention (ISO 20022 regulatory requirement)
- **Persistent volume** `/data/decision-log/` inside the C7 container (700 permissions, lipuser-owned) for local file-based retention as a secondary copy

The HMAC key comes from `LIP_DECISION_LOG_HMAC_KEY` env var (falls back to `LIP_API_HMAC_KEY` if unset). Without either, `build_runtime_pipeline()` raises at startup — the pipeline refuses to start without integrity-signed decision logs.

### Regulator-facing export

P10's `RegulatoryService` reads from `lip.decisions.audit`, filters by scope, and exports DORA Art.19 / SR 11-7 / EU AI Act Art.61 reports. The HMAC signature lets the regulator verify export integrity without trusting P10's extraction pipeline.

---

## Offer delivery (`offer_delivery.py`)

Two delivery modes:

| Mode | Transport | When used |
|------|-----------|-----------|
| In-process callback | Python function call | Unit tests; staging when `LIP_OFFER_DELIVERY_ENDPOINT` is empty |
| HTTPS POST | `LIP_OFFER_DELIVERY_ENDPOINT` → bank's acceptance endpoint | Production + pilot bank |

The in-process mode is used for `test_c7_offer_delivery.py` and for staging where the offer is accepted by a stub endpoint. In production, the endpoint is the bank's internal gRPC / HTTPS service that routes to their loan operations system.

### Race condition guarding (`offer_delivery_race_fix.py`)

Accept and expire can race: if the bank's acceptance arrives at the same moment as the offer expiry timer fires, both paths could try to finalise the loan. `OfferDeliveryService` uses a Redis atomic compare-and-set (`SET key value NX`) on the offer ID to ensure exactly one wins. The losing path returns `OfferExpiryReason.RACE_LOST` and logs at WARNING.

### Override sweeper (`override_sweeper.py`)

For manual operator overrides — if a human approves a `PENDING_HUMAN_REVIEW` outcome, the override sweeper polls for the override state, finalises the loan if approved, and cleans up the override record. Runs as a background thread with configurable interval (`LIP_OVERRIDE_SWEEPER_INTERVAL_SECONDS`, default 30s).

---

## Compliance-hold defense layer 2 (EPG-19)

Defense-in-depth for the 8 compliance-hold codes (DNOR, CNOR, RR01-RR04, AG01, LEGL):

- **Layer 1** (C3 rejection taxonomy) — these codes are BLOCK class, short-circuit the pipeline at `process_event` entry
- **Layer 2** (C7 `_COMPLIANCE_HOLD_CODES` frozenset in `agent.py`) — same codes, re-checked immediately before offer generation

If Layer 1 is ever accidentally disabled (a bug or misconfig), Layer 2 still catches every compliance-hold payment. Both layers must independently hard-block. The test suite enforces this symmetry (`test_c7_execution.py::test_compliance_hold_double_defense`).

---

## Known-entity tier override (`agent.py` + `KnownEntityRegistry`)

Some bank-to-bank corridors have long-standing relationships — e.g., if Deutsche Bank has a 10-year account with BNP Paribas, the C2 Tier 3 default (for a thin-file BIC) is wrong. The `KnownEntityRegistry` allows the licensee to pre-declare tier overrides for specific BICs.

Flow:
1. `agent.py` checks `KnownEntityRegistry.lookup(bic)` after C2 returns
2. If an override exists, `fee_bps` is recomputed with the override tier
3. The decision log records both the original C2 tier and the override used — for regulator audit

Overrides cannot push a BIC UP in tier (Tier 3 → Tier 1 = "trust this thin-file bank as if it were fully documented"). They can only push DOWN (Tier 1 → Tier 2/3 = "be conservative on this well-documented but misbehaving bank").

---

## Borrower registry (`BorrowerRegistry`)

Three-layer enrollment requirement (see PROGRESS.md § Three-Layer Enrollment):

1. **License Agreement** between BPI and the licensee bank
2. **MRFA** (Master Receivables Financing Agreement) between licensee and originating bank
3. **Borrower Registry** — per-BIC enrollment record inside the licensee's LIP deployment

C7 checks layer 3 on every offer. `borrower_registry.is_enrolled(bic)` returns False → outcome = `BORROWER_NOT_ENROLLED`, no loan offer generated. This is a hard gate.

---

## Execution config (`ExecutionConfig`)

Groups the optional external references:

```python
@dataclass
class ExecutionConfig:
    borrower_registry: BorrowerRegistry
    kms_endpoint: Optional[str] = None
    ramq_check_enabled: bool = True  # Rest-of-pipeline assembly must complete in < SLO
    stress_regime_detector: Optional[Any] = None
    known_entity_registry: Optional[KnownEntityRegistry] = None
```

---

## Degraded mode (`degraded_mode.py`)

When external dependencies are partially available, C7 can enter a degraded state instead of engaging the kill switch:

| Degraded signal | What happens |
|-----------------|--------------|
| KMS 5xx intermittent | Fail closed — no new offers until KMS recovers |
| Redis high latency | Use in-memory fallback for kill switch state; log WARNING |
| Decision log Kafka producer backpressure | Buffer locally; circuit break after 1000-entry buffer |

Degraded state is reversible — `DegradedModeManager.can_recover()` evaluates health and exits degraded mode automatically. Kill-switch engagement is not reversible without operator action.

---

## Human override (`human_override.py`)

EU AI Act Art.14 (Human Oversight) implementation. For outcomes that route to `PENDING_HUMAN_REVIEW` (C6 anomaly flag per EPG-18), C7 exposes a pending-review API surface:

```
GET /admin/overrides/pending           → list pending decisions
POST /admin/overrides/<decision_id>    → approve|reject|escalate
```

Approvals must include the operator's C8 LicenseeContext + a free-text rationale. The rationale is recorded in the decision log alongside the approve/reject signal. Regulators receive both.

---

## Consumers

| Consumer | How it uses C7 |
|----------|---------------|
| `lip/pipeline.py::LIPPipeline.process_event` | Calls `c7_agent.process_payment` with the assembled context |
| `lip/api/runtime_pipeline.py::build_runtime_pipeline` | Constructs ExecutionAgent + injects KillSwitch, DecisionLogger, BorrowerRegistry, HumanOverrideInterface, DegradedModeManager |
| `lip/pipeline.py::LIPPipeline.finalize_accepted_offer` | Called by OfferDeliveryService on bank acceptance; registers the active loan with C3 |
| Admin routers | `/admin/kill-switch/`, `/admin/overrides/` |

---

## What C7 does NOT do

- **Does not assess the payment** — C1+C4+C6+C2 do that upstream.
- **Does not monitor settlement** — C3 does.
- **Does not issue licenses** — C8 does.
- **Does not generate regulator reports** — P10 does, reading from C7's decision log.

---

## Deployment model

C7 hosts the `lip-api` image in the default staging topology — `Dockerfile.c7` is used for the FastAPI surface too, because the lip-api process mounts C7's ExecutionAgent inline. In a true on-prem bank deployment, C7 runs as a separate bank-side zero-outbound container; lip-api remains BPI-hosted or licensee-hosted separately. See [`../specs/BPI_C7_Bank_Deployment_Guide_v1.0.md`](../specs/BPI_C7_Bank_Deployment_Guide_v1.0.md).

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § step 3e
- **Spec** — [`../specs/BPI_C7_Component_Spec_v1.0_Part1.md`](../specs/BPI_C7_Component_Spec_v1.0_Part1.md), [`Part 2`](../specs/BPI_C7_Component_Spec_v1.0_Part2.md)
- **Bank Deployment Guide** — [`../specs/BPI_C7_Bank_Deployment_Guide_v1.0.md`](../specs/BPI_C7_Bank_Deployment_Guide_v1.0.md)
- **EPG-19** — [`../../legal/decisions/EPG-19_compliance_hold_bridging.md`](../../legal/decisions/EPG-19_compliance_hold_bridging.md)
- **EPG-18** — [`../../legal/decisions/EPG-16-18_aml_caps_human_review.md`](../../legal/decisions/EPG-16-18_aml_caps_human_review.md)
- **C8** — [`c8_license_manager.md`](c8_license_manager.md)
