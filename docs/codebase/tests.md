# `lip/tests/` — Test Organisation

> **121 test files, ~1284 tests passing, 92% coverage.** This file is the map. It tells you which tests cover what, which require infrastructure, which are flaky, and which you must never `--ignore`.

**Source:** `lip/tests/`
**Test count:** 121 test files (+ `conftest.py`, `__init__.py`, `load/`)
**Reported:** 1284 tests passing, 92% coverage, 0 ruff errors (per README badges)

---

## Layout

### By component (matches `lip/c{N}_*/`)

| Component | Test files |
|-----------|-----------|
| C1 | `test_c1_calibration.py`, `test_c1_classifier.py`, `test_c1_graphsage_neighbors.py`, `test_c1_inference_types.py`, `test_c1_lgbm_ensemble.py`, `test_c1_torch.py`, `test_c1_training.py` |
| C2 | `test_c2_cascade_pricing.py`, `test_c2_comprehensive.py`, `test_c2_fee_formula.py`, `test_c2_model.py`, `test_c2_pd_model.py` |
| C3 | `test_c3_c4_c5_coverage.py`, `test_c3_repayment.py`, `test_c3_state_machine_bridge.py` |
| C4 | `test_c4_backends.py`, `test_c4_contraction_expansion.py`, `test_c4_dispute.py`, `test_c4_llm_integration.py` |
| C5 | `test_c5_kafka_worker.py`, `test_c5_streaming.py`, `test_c5_stress_regime.py`, `test_c5_telemetry_eligible.py`, `test_cancellation_detector.py` |
| C6 | `test_c6_aml.py`, `test_c6_rust_velocity.py`, `test_c6_tenant_velocity.py` |
| C7 | `test_c7_execution.py`, `test_c7_go_router.py`, `test_c7_offer_delivery.py` |
| C8 | `test_c8_license.py`, `test_c8_processor.py` |

### By GAP (one test file per GAP closure)

`test_gap02_aml_caps.py`, `test_gap02_licensee_aml_caps.py`, `test_gap03_borrower_registry.py`, `test_gap04_retry_detection.py`, `test_gap04_uetr_ttl.py`, `test_gap05_royalty_collection.py`, `test_gap06_swift_disbursement.py`, `test_gap07_portfolio_api.py`, `test_gap08_override_timeout.py`, `test_gap09_business_calendar.py`, `test_gap10_governing_law.py`, `test_gap11_entity_tier_override.py`, `test_gap12_fx_risk_policy.py`, `test_gap13_notifications.py`, `test_gap14_regulatory_reporting.py`, `test_gap15_admin_monitoring.py`, `test_gap16_partial_settlement.py`, `test_gap17_amount_validation.py`. (See `PROGRESS.md` § Critical Gaps for the GAP-XX descriptions.)

### End-to-end (the most important tests for a new contributor to know)

| File | What it covers | Infrastructure required |
|------|----------------|--------------------------|
| `test_e2e_pipeline.py` | **8 in-memory scenarios** — full pipeline with mock C1/C2, no Kafka/Redis. **DO NOT use `--ignore` on this file** (CLAUDE.md rule). It is the canonical pipeline regression suite. | None — fully in-memory |
| `test_e2e_live.py` | Live integration against Redpanda (Kafka) at `localhost:9092` | Requires `start_local_infra.sh` to be running. Marked `@pytest.mark.live`; auto-skips when infra is down. |
| `test_e2e_corridor.py` | Per-corridor end-to-end against the canonical corridor parameters | None |
| `test_e2e_decision_log.py` | Audit-trail completeness across the pipeline | None |
| `test_e2e_latency.py` | 94 ms p99 SLO regression | None — but see flaky-test note below |
| `test_e2e_settlement.py` | C3 settlement / repayment loop | None |
| `test_e2e_state_machines.py` | `PaymentState` and `LoanState` transitions across the full pipeline | None |
| `test_e2e_config.py` | Canonical config loading and runtime constants alignment | None |

### Cascade and forward-looking patents

| File | Covers |
|------|--------|
| `test_cascade_api.py` | P5 cascade engine via the HTTP `cascade_router` (see [`p5_cascade_engine.md`](p5_cascade_engine.md), [`api.md`](api.md)) |
| `test_c2_cascade_pricing.py` | P5 cascade-adjusted PD pricing in C2 (Sprint 3c bridge) |

### Cross-cutting

| File | Covers |
|------|--------|
| `test_api_auth.py` | HMAC authentication on the FastAPI surface (`lip/api/auth.py`) |
| `test_circuit_breaker.py` | `lip/common/circuit_breaker.py` |
| `test_conformal.py` | `lip/common/conformal.py` (calibration intervals) |
| `test_drift_detector.py` | `lip/common/drift_detector.py` (SR 11-7 ongoing monitoring) |
| `test_deployment_phase.py` | `lip/common/deployment_phase.py` (pilot vs. production gating) |
| `test_dgen_adversarial.py` | `lip/dgen/` adversarial corpus validation |
| `test_failure_modes.py` | Negative-path coverage across the pipeline |
| `test_fee_arithmetic.py` | The QUANT-locked fee formula. Touching this without QUANT sign-off is a refusal-grade error. |
| `test_coverage_gaps.py` | Meta-test that flags any module with coverage below the project floor |

---

## Markers and selectors

```bash
# Default — fast iteration; excludes long-running tests and live infra
PYTHONPATH=. python -m pytest lip/tests/ -m "not slow" --ignore=lip/tests/test_e2e_live.py

# Full suite (excludes only the live-infra suite by default) — ~12 minutes, ~1010+ tests
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_live.py

# Live integration only (requires Redpanda at localhost:9092)
./scripts/start_local_infra.sh
PYTHONPATH=. python -m pytest lip/tests/test_e2e_live.py -m live -v

# Single GAP
PYTHONPATH=. python -m pytest lip/tests/test_gap04_retry_detection.py -v
```

## Test discipline (from `CLAUDE.md` and `PROGRESS.md`)

- **Full suite is ~12 minutes** (722s, 1010+ tests). Use `-m "not slow"` for iteration.
- **`test_e2e_pipeline.py` is 100% in-memory** (8 scenarios, mock C1/C2, no Kafka/Redis). Safe to run without infrastructure. **DO NOT `--ignore` it.**
- **`test_e2e_live.py` requires live Redpanda**. Marked `@pytest.mark.live`; auto-skips when infra is down. Exclude from default suite with `--ignore=lip/tests/test_e2e_live.py`.
- **`test_slo_p99_94ms` (in `test_c1_classifier.py`) is a flaky timing test** — fails under CPU load, passes in isolation. **Not a regression signal.** Re-run in isolation before treating it as a real failure.
- **Long pytest runs are auto-backgrounded** by the Bash tool. Wait with `TaskOutput(block=True, timeout=600000)` and `TaskStop` competing runs before starting a new one.

## PyTorch / ML test gotchas

From `CLAUDE.md`:

- **`torch>=2.6.0`** — `torch==2.2.0` is unavailable on the CPU wheel index
- **LightGBM (OpenMP) + PyTorch BLAS deadlock on macOS** in the same pytest process. Any test file using both must include a session-scoped autouse fixture: `torch.set_num_threads(1); torch.set_num_interop_threads(1)`

## Pre-commit gates

Before any commit:

1. `ruff check lip/` — must be **zero errors**
2. `python -m pytest lip/tests/` — must pass (excluding `test_e2e_live.py` if infra is not running)

`CLAUDE.md` Key Rules: both gates are non-negotiable. FORGE will refuse `--no-verify` and `--force` push to main, ever.

## `conftest.py` and `load/`

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures shared across the test suite — Redis test client, Kafka mock, license-token factory, normalised-event factory |
| `load/` | Load and benchmark tests — see [`scripts.md`](scripts.md) for the related runners |

## Cross-references

- **CI workflow**: `.github/workflows/` (run via `gh run list --repo ryanktomegah/PRKT2026`)
- **Pre-commit rules**: `CLAUDE.md` § Key Rules
- **Coverage badge source**: 92% (per README)
