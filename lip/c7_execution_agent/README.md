# C7: Execution Agent (ELO)

## Role in Pipeline

C7 is the **loan execution controller** and the primary **human oversight and safety layer** (ELO — Execution Lending Organisation). It receives the aggregated decision from C1/C4/C6/C2, applies kill switch and KMS availability checks, logs every decision to the immutable audit trail, and — if all safety gates pass — funds the bridge loan.

## Algorithm 1 Position

```
C2 → [C7: kill switch / KMS / human override / decision log] → FUNDED → C3
```

C7 is **Step 4** of Algorithm 1. It is the last gate before a loan is funded.

## Key Classes

| Class | File | Description |
|-------|------|-------------|
| `ExecutionAgent` | `agent.py` | Main entry point — orchestrates all safety checks |
| `KillSwitch` | `kill_switch.py` | Operator-controlled halt mechanism |
| `HumanOverrideInterface` | `human_override.py` | EU AI Act Art.14 override workflow |
| `DegradedModeManager` | `degraded_mode.py` | GPU/KMS failure state tracking |
| `DecisionLogger` | `decision_log.py` | HMAC-signed immutable decision logging |

## Safety Gates (in order)

```
1. KillSwitch.should_halt_new_offers()     → halt if kill switch OR KMS unavailable
2. DegradedModeManager.should_halt_new_offers() → halt if KMS degraded
3. AML / dispute double-check              → hard block
4. HumanOverrideInterface                  → EU AI Act Art.14 review (if triggered)
5. DecisionLogger.log()                    → HMAC-signed audit entry (always)
6. Fund loan                               → outcome: FUNDED / DECLINED / HALT
```

## Regulatory Obligations

| Regulation | Requirement | Implementation |
|-----------|-------------|---------------|
| **EU AI Act Art.14** | Human oversight mechanism | `HumanOverrideInterface` — operators can override any AI decision |
| **EU AI Act Art.9** | Risk management system | `KillSwitch.activate()` — hard stop without code changes |
| **DORA Art.30** | ICT resilience incident logging | Kill switch activations and KMS gap seconds logged and alerted |
| **SR 11-7 (Fed/OCC)** | Model risk management | Human override capability is mandatory; kill switch satisfies this |

## Kill Switch Behaviour

| Trigger | New Offers | Funded Loans | Settlements |
|---------|-----------|--------------|-------------|
| Kill switch `ACTIVE` | **HALT** | Preserved | Buffered |
| KMS `UNAVAILABLE` | **HALT** | Preserved | Buffered |
| GPU failure | Continue (CPU fallback) | Preserved | Normal |

## Decision Log

Every C7 decision (including blocks from C4/C6) produces a `DecisionLogEntry`:
- **HMAC-SHA256 signed** over the canonical payload (tamper detection)
- **7-year retention** on `lip.decision.log` Kafka topic
- **Immutable** — `ConfigDict(frozen=True)` enforces no post-creation mutation
- Fields include: `degraded_mode`, `gpu_fallback`, `kms_unavailable_gap`

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `DECISION_LOG_RETENTION_YEARS` | **7** | Kafka topic retention — **do not shorten** |
| `LATENCY_P99_TARGET_MS` | 94 ms | C7 must complete within the pipeline SLO budget |

## Spec References

- Architecture Spec v1.2 §2.5 — Kill switch and KMS unavailability behaviour
- Architecture Spec v1.2 §4.6 — `LoanOffer` / `ExecutionConfirmation` schemas
- Architecture Spec v1.2 §4.8 — `DecisionLogEntry` schema
- EU AI Act Art.9 / Art.13 / Art.14 / Art.17 — Risk management, transparency, oversight, documentation
- DORA Art.30 — ICT operational resilience testing and incident logging
