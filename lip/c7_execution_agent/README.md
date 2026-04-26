# C7: Execution Agent (ELO)

## Role in Pipeline

C7 is the **loan execution controller** and the primary **human oversight and safety layer** (ELO — Execution Lending Organisation). It receives the aggregated decision from C1/C4/C6/C2, applies kill switch and KMS availability checks, logs every decision to the immutable audit trail, and — if all safety gates pass — emits a bridge-loan offer for ELO treasury acceptance.

## Algorithm 1 Position

```
C2 → [C7: kill switch / KMS / human override / decision log] → OFFER → ELO acceptance → FUNDED → C3
```

C7 is **Step 4** of Algorithm 1. It is the last gate before a loan offer is delivered. Funding and C3 activation happen only after explicit ELO acceptance.

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
6. Deliver offer                          → outcome: OFFER / DECLINE / HALT
```

## Rail-aware offer construction (Phase A, 2026-04-25)

`_build_loan_offer(payment_context, pd, fee_bps)` enforces three layered fee floors as defence-in-depth:

```
Layer 1 — tiered floor      compute_tiered_fee_floor(loan_amount)   [<$500K → 500 bps, $500K-$2M → 400 bps, ≥$2M → 300 bps]
Layer 2 — sub-day floor     applicable_fee_floor_bps(maturity_hours) [<48h → 1200 bps; ≥48h → 300 bps]
Layer 3 — operational floor apply_absolute_fee_floor(fee_usd)        [≥ $25 absolute]
```

Maturity is read from `RAIL_MATURITY_HOURS[payment_context["rail"]]`:

```
rail_upper = (payment_context.get("rail") or "SWIFT").upper()
if rail_upper in RAIL_MATURITY_HOURS:
    maturity_hours = RAIL_MATURITY_HOURS[rail_upper]   # CBDC=4h, FedNow/RTP=24h, SWIFT/SEPA=1080h
else:
    maturity_hours = float(maturity_days * 24)         # legacy fallback
maturity_date = funded_at + timedelta(hours=maturity_hours)
```

The constructed offer dict carries:
- `rail` — the rail the offer was built for
- `maturity_hours` — exact hour-precision duration
- `maturity_days` — `ceil(hours/24)` for legacy schema validators (`LoanOffer.maturity_days >= 1`)

Rail-specific FX policy is unchanged: `FXRiskConfig.is_supported(payment_currency)` continues to gate. CNY/EUR/BSD CBDC bridges work when the licensee bank's `bank_base_currency` matches the CBDC.

## Cross-rail handoff (Phase C, 2026-04-25)

When a FedNow/RTP/SEPA event has a registered upstream SWIFT parent UETR (`UETRTracker.find_parent`), pipeline.py emits `DOMESTIC_LEG_FAILURE` instead of `OFFERED` and adds `parent_uetr` to the loan_offer dict for cross-rail audit. C7's offer construction is unchanged; the outcome label is set in `pipeline.py` after C7 returns. Patent angle: P9 continuation candidate; filing frozen per CLAUDE.md non-negotiable #6.

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
