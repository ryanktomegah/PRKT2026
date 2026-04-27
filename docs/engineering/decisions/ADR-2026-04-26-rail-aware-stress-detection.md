# ADR 2026-04-26 — Rail-Aware Stress Regime Detection

**Status:** Accepted (Claude as architect, founder authority granted 2026-04-25)
**Context:** Tech debt #3 from post-Nexus sequence; companion to ADR-2026-04-25-rail-aware-maturity
**Spec/PR:** PR #73 (`feat(c5/stress): rail-aware window tuning for sub-day detection`)

## Decision

The stress regime detector accepts an optional `rail` kwarg on its public surface (`record_event`, `is_stressed`, `check_and_emit`, `get_rates`). When `rail` is provided:

1. Events are recorded in a `(rail, corridor)`-keyed history bucket — events from different rails do not contaminate each other.
2. Window tuning is read from `RAIL_STRESS_WINDOWS` in `lip/common/constants.py` for that call's evaluation.
3. Unknown rails (and `rail=None` legacy callers) fall back to the detector's constructor defaults — preserving the SWIFT-shaped window semantics that existed before this change.

Per-rail window calibration:

| Rail | Baseline | Current | Min txns |
|---|---|---|---|
| SWIFT / SEPA | 86400 (24h) | 3600 (1h) | 20 |
| FedNow / RTP | 3600 (1h) | 300 (5m) | 10 |
| CBDC retail | 1800 (30m) | 300 (5m) | 5 |
| CBDC_MBRIDGE | 1800 (30m) | 180 (3m) | 5 |
| CBDC_NEXUS | 300 (5m) | 30 (30s) | 3 |

## Why this was needed

The legacy single-window detector was tuned for SWIFT/SEPA where loan tenor is 3–21 days. On sub-day rails the math breaks:

- **CBDC at 4h tenor:** 1h current window = 25% of the loan duration. By the time the spike crosses the 3× threshold and the circuit breaker fires, the loan has nearly settled — circuit breaker fires too late to do anything useful.
- **mBridge with 1–3s atomic PvP finality:** 1h is meaningless. By the time we have an hour of data, the entire pipeline of mBridge transactions has cleared.
- **Project Nexus at 60s finality:** 1h is 60× the loan duration. The detector would be permanently silent.

The EU AI Act Art.14 human-oversight requirement is the legal hook. If the circuit breaker can't fire in time on sub-day rails, the autonomous funding decision proceeds — exactly the failure mode Art.14 exists to prevent.

## Why per-rail buckets, not per-rail detectors

Initial design considered instantiating one detector per rail. Rejected because:

1. **Shared corridor name across rails.** `"USD_USD"` exists on SWIFT (cross-currency same-currency), FedNow, and RTP simultaneously. With one detector per rail, the corridor key was clean. With a single detector, we needed to disambiguate, leading to bucket keys like `(rail, corridor)`.
2. **Per-rail detectors complicate the runtime wiring.** `pipeline.py` would need to look up the right instance per event; `c7/agent.py` would need a registry. The per-bucket-key approach keeps a single detector instance that callers can use without knowing about rail tuning.
3. **Backward compatibility is harder with per-rail instances.** Existing callers don't pass rail; they'd get a "default" instance that doesn't see rail-specific events. With buckets, `rail=None` keeps using the legacy `("", corridor)` bucket — zero-line-change for legacy callers.

## Why fall back to SWIFT for unknown rails (not sub-day)

If a future rail is added to `RAIL_MATURITY_HOURS` but not yet to `RAIL_STRESS_WINDOWS`, the detector returns the constructor defaults (SWIFT-shaped 24h/1h/20). Picking sub-day for unknown rails would be aggressive — a new rail with unknown behavior gets the safer, less-prone-to-false-positives SWIFT tuning until someone explicitly tunes it.

This is the fail-closed shape: an unknown rail's stress signal will fire less often, not more often. False negatives are visible (the pilot bank reports a missed spike); false positives generate noise that masks real signals.

## Window calibration rationale

Each rail's current window is roughly 5–15% of the typical loan duration. The baseline window is 5–10× the current window — long enough to establish a stable failure-rate average, short enough that conditions a day ago don't pollute today's signal.

`min_txns` is reduced for low-volume rails. Q1 2026 traffic estimates:
- SWIFT majors: thousands per minute → 20 min txns trivially satisfied
- mBridge corridors: tens per minute → need lower min_txns or the gate never opens
- Nexus: untested in production (mid-2027 onboarding) → modelled tightest

When real pilot data arrives, all numbers should be re-tuned. `RAIL_STRESS_WINDOWS` is a Python dict — recalibration is a one-line change, no code refactor needed.

## Consequences

- **C7 human-review gate (`agent.py`)** receives `rail` from `payment_context` and passes it to `is_stressed`. Sub-day rails with stress trigger human review within minutes of the spike, not hours.
- **Pipeline (`pipeline.py`)** records events with `rail=event.rail`. Per-rail buckets mean a SWIFT spike doesn't contaminate the mBridge bucket and vice versa.
- **Existing tests preserved.** Two internal-key references in `test_c5_stress_regime.py` and `test_gap_stress_detector.py` updated to use the new tuple key shape; everything else unchanged.
- **No new audit-log fields.** `StressRegimeEvent` schema unchanged — `corridor` field carries the corridor name, not the rail. Downstream Kafka consumers that disambiguate by rail must do so via the `triggered_at` plus a separate event-rail mapping.

## Open question — deferred

`StressRegimeEvent.corridor` is rail-agnostic. If two rails see stress on the same corridor name simultaneously, downstream Kafka consumers can't tell them apart. **Not addressed in this ADR**; flagged for the next iteration when real multi-rail traffic exists. Options when it matters: (a) add `rail` field to `StressRegimeEvent`, (b) include rail in the corridor key (`"CBDC_MBRIDGE::CNY_HKD"`), (c) emit on a rail-keyed Kafka topic. Choice depends on whether the stressed-corridor consumer wants per-rail or per-corridor signals.

## Patent posture

This change supports P5 Family 5 Independent Claim 2 (corridor stress regime detector with EU AI Act Art.14 circuit breaker). The claim language is rail-agnostic — "transaction failure events across a specific cross-border payment corridor" — so the claim still reads on the rail-aware implementation. No new claim language drafted; filing remains frozen per CLAUDE.md non-negotiable #6.

## Authors

Claude Opus 4.7 (acting architect, founder authority granted 2026-04-25).
