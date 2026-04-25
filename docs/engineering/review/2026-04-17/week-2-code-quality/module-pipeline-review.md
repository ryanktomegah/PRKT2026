# Module Review — `lip/pipeline.py`

**Date:** 2026-04-19
**Reviewer:** Claude (Day 10 Task 10.1)
**Scope:** `/Users/tomegah/PRKT2026/lip/pipeline.py` (1,109 lines before fix; 1,112 after inline fix)
**Audience:** Outside counsel (LIP pre-lawyer review sprint)
**Associated commits:** see "Commits" section at the bottom.

---

## Summary

`pipeline.py` is the central orchestrator of the LIP decision flow. A
`NormalizedEvent` (pacs.002 / pacs.004 payload) enters `LIPPipeline.process`
and — gate by gate — is either short-circuited (retry, dispute, AML fail,
anomaly, compliance hold, kill switch) or allowed to proceed to a
`LoanOffer`/`FUNDED` outcome. The file implements the Algorithm 1 skeleton
from Architecture Spec v1.2 §3, with fail-closed semantics on every
classification component (C4, C6, C7). The code is clear, heavily commented
with EPG references, and defense-in-depth against compliance-hold bridging.
One real correctness bug was found and fixed inline (EPG-27 audit-trail
contamination in `_log_block`). Two function-local imports on the hot path
were lifted to module scope. The remaining findings are either design-level
(extract-method refactors, which we decline so as not to add call-frame
overhead to the 94ms SLO path) or follow-ups that require QUANT / NOVA
sign-off before committing.

---

## 1. Architecture map

### Entry points

| Callable | Line | Role |
|----------|------|------|
| `LIPPipeline.__init__` | 131 | DI wiring for C1, C2, C3, C4, C6, C7, optional C9, drift/conformal/risk/integrity |
| `LIPPipeline.process` | 197 | Single-event Algorithm 1 loop |

Only `process` is a hot-path entry; `__init__` runs once and includes a
one-shot integrity-gate check at line 183.

### Stage sequence (all flows go through `process`)

```
 pacs.002 in (NormalizedEvent)
   └── retry detection            (UETRTracker.is_retry, line 244)
   └── stress-detector record     (line 258)
   └── early BLOCK short-circuit  (is_dispute_block, line 265)
   └── entity/tenant resolution   (lines 290-303)
   └── state machine init         (line 306)
   └── C1 inference               (line 322, measured)
        ├── drift update          (line 329, optional)
        └── below-threshold exit  (line 344)
   └── C4 + C6 in parallel        (ThreadPoolExecutor, line 367)
        ├── AML None → fail-closed (EPG-27, line 383)
        ├── dispute hard block    (line 420)
        ├── AML hard block        (line 445)
        └── EPG-18 anomaly → PENDING_HUMAN_REVIEW (line 473)
   └── C2 PD + fee                (line 493, measured)
        └── conformal widening    (line 509, optional)
   └── maturity/rejection derive  (lines 522-523)
   └── C7 ExecutionAgent          (line 561, measured)
        ├── COMPLIANCE_HOLD       (line 594)
        ├── HALT                  (line 630)
        ├── PENDING_HUMAN_REVIEW  (line 653)
        └── DECLINE / BLOCK class (line 679)
   └── FUNDED path                (line 713)
        ├── state transition      (lines 714-718)
        ├── C6 record (post-fund) (line 721, measured)
        ├── C3 register_loan      (line 737, optional)
        └── risk engine add       (line 740, optional)
   └── PipelineResult out
```

### Cross-module dependencies

| Import | Usage |
|--------|-------|
| `lip.c3_repayment_engine.rejection_taxonomy` | `classify_rejection_code`, `is_dispute_block`, `maturity_days` — Layer 1 BLOCK gate |
| `lip.c3_repayment_engine.repayment_loop.ActiveLoan` | Funded-loan record for C3 + risk engine |
| `lip.c4_dispute_classifier.taxonomy.DisputeClass` | Enum for hard-block check |
| `lip.c5_streaming.event_normalizer.NormalizedEvent` | Input type |
| `lip.common.business_calendar` | GAP-09 business-day maturity |
| `lip.common.notification_service` | EPG-11 compliance-team notify |
| `lip.common.redis_factory.create_redis_client` | DI fallback |
| `lip.common.schemas.TenantContext` | P3 licensing |
| `lip.common.state_machines` | PaymentState / LoanState FSMs |
| `lip.common.uetr_tracker.UETRTracker` | GAP-04 retry detection |
| `lip.instrumentation.LatencyTracker` | Per-call + global p50/p99 |
| `lip.pipeline_result.PipelineResult` | Output dataclass |
| `lip.common.conformal.uncertainty_fee_adjustment` | Local import (line 519 after fix), only when conformal is calibrated |

### Error-handling pattern

Uniform: every external component call is wrapped in either `try/except`
(broad, defensive) or returns a sentinel (`None`) that the pipeline then
treats as fail-closed. Broad `except Exception` is appropriate here —
the pipeline must not propagate an engine-level crash to the Kafka
consumer, because that would stop the stream. Concrete examples:

- `_run_c4` (line 808) → defaults to `NOT_DISPUTE` on exception (line 817)
- `_run_c6` (line 881) → returns `None` on exception; pipeline blocks (EPG-27)
- `_c7.process_payment` (line 560) → SYSTEM_ERROR outcome (line 563)
- `_log_block`, `_register_with_c3` → swallow and log; non-fatal for result

---

## 2. 94ms SLO-critical path

The SLO is measured on `process`. The "hot" path is the happy path: C1 →
(C4‖C6) → C2 → C7 → FUNDED. BELOW_THRESHOLD is the *most common* exit by
volume but C1 dominates its latency, so both are listed.

All measurements below are the LatencyTracker budgets from
`lip/common/constants.py` (C1 ≤ 15ms p99, C2 ≤ 20ms, C6 ≤ 15ms, C7 ≤ 30ms
per `LATENCY_SLO_*` constants) combined with Python call-overhead estimates
of 1–2 µs per frame. Exact wall-clock percentiles live in
`test_e2e_latency.py` output; see `LATENCY_P99_MS=94`.

| # | Line | Call | Sync/Async | Budget (ms) | Notes |
|---|------|------|------------|-------------|-------|
| 1 | 244 | `UETRTracker.is_retry` | sync | <1 | in-memory SortedSet, cheap |
| 2 | 259 | `stress_detector.record_event` | sync | <0.5 | dict update |
| 3 | 265 | `is_dispute_block` | sync | <0.05 | set membership |
| 4 | 322 | `c1_engine.predict` | sync | ≤15 p99 | LightGBM + GraphSAGE + SHAP |
| 5 | 340 | `drift_monitor.update` | sync | <0.5 | ADWIN arithmetic |
| 6 | 367 | `ThreadPoolExecutor(2).submit × 2` | parallel | ≤max(c4, c6) ≈15 p99 | pool is spun up *per call* — thread-create overhead ~1–3 ms, see H1 |
| 7 | 810 | `c4.classify` | sync (thread A) | ≤12 p99 | prefilter + optional LLM; LLM is *not* on the hot path (guarded) |
| 8 | 876 | `c6.check` | sync (thread B) | ≤15 p99 | Redis HINCRBY + UETR hash; bounded by Redis RTT |
| 9 | 862 | `inspect.signature(self._c6.check)` | sync | ~0.02 | uncached per call — see M1 |
| 10 | 495 | `c2_engine.predict` | sync | ≤20 p99 | cascade pricer |
| 11 | 511 | `conformal.predict_interval` | sync | <1 | isotonic lookup, only if calibrated |
| 12 | 522 | `_derive_maturity_days` | sync | <0.05 | taxonomy dict lookup |
| 13 | 523 | `_derive_rejection_class` | sync | <0.05 | same |
| 14 | 562 | `c7_agent.process_payment` | sync | ≤30 p99 | builds LoanOffer, KMS/kill-switch checks |
| 15 | 721 | `c6.record` (post-fund) | sync | ≤5 | Redis pipeline |
| 16 | 737 | `_register_with_c3` | sync | ≤3 | local hash set insert |
| 17 | 740 | `risk_engine.add_position` | sync | ≤2 | optional |
| 18 | — | `_record_global` | sync | <0.5 | shared LatencyTracker writes |

**Budgeted sum (p99):** retry (<1) + stress (<0.5) + C1 (15) + drift (<0.5)
+ max(C4, C6) (15) + C2 (20) + C7 (30) + C6.record (5) + C3 (3) + risk (2)
≈ **92 ms.**

That is *already* at the 94 ms ceiling with almost no headroom. The per-call
`ThreadPoolExecutor` construction at line 367 is the single largest piece of
avoidable overhead on this path (H1 below).

### Hot-path flags

- **H1 — Per-call ThreadPoolExecutor (line 367):** creates + tears down a
  2-worker pool on every above-threshold event. On macOS this is typically
  1–3 ms of thread-creation overhead; on Linux with a saturated kernel
  scheduler it can spike to 5–10 ms at the p99 tail. Fix is mechanically
  simple (store the executor on `self` in `__init__`, tear down in an
  explicit `close()` or context) but it *changes the object lifecycle*, so
  it is filed as a follow-up rather than done inline — QUANT + FORGE should
  sign off on the resource model.
- **H2 — Per-call `inspect.signature(self._c6.check)` (line 862 pre-fix /
  line 861 post-fix):** signature introspection is not free (~20 µs).
  Because `self._c6` is fixed at construction, this result can be computed
  once in `__init__`. Filed as follow-up M1.
- **No async I/O on the hot path.** Good: the pipeline is fully
  synchronous. C5 handles async at the stream boundary. The
  `ThreadPoolExecutor` at line 367 is the only concurrency construct, and
  it is used correctly (CPU-bound C4 + I/O-bound C6 in parallel).

---

## 3. Split candidates

The file is 1,112 lines but the single `process` method is ~590 lines. We
evaluated splits against the guardrail "does extraction add call-frame
overhead to the SLO-critical path?" Every extraction of a hot-path section
adds one Python function-call frame, which is ~1 µs — negligible on its
own, but a budget we can't afford to spend if the *result* is cosmetic.

| Section | Lines | Net recommendation |
|---------|-------|---------------------|
| C1 step (320-358) | 39 | **Keep inline.** Three inlined branches (drift update, below-threshold exit, transition). Extraction buys nothing and costs a frame. |
| C4+C6 parallel block (363-416) | 54 | **Keep inline.** Both executor lifecycle and post-processing need to share locals; extracting it to `_run_c4_c6_parallel` would force a tuple unpack plus an extra frame. |
| Dispute / AML / anomaly / compliance handlers (419-710) | 292 | **Extract — but only via a shared `_build_result` helper.** Every branch constructs an almost-identical `PipelineResult`. A single factory method keyed by outcome would drop ~200 LOC and materially reduce maintenance drift. SLO impact: +1 frame, ~1 µs — acceptable. Filed as M2 because it is a real refactor, not a surgical fix. |
| FUNDED finalisation (712-787) | 76 | **Keep inline.** Already clean; C3 and risk_engine calls are guarded. |
| `_register_with_c3` (994-1052) | 59 | **Keep as-is.** Already extracted. |
| `_event_to_payment_dict` (1054-1090) | 37 | **Keep as-is.** Already extracted; called twice (C1 + C2 reuse payment_dict). |

**Split decision:** do not split in this sprint. The one legitimate win —
a shared result builder — is a refactor and is filed for the next cycle.

---

## 4. Grading

| Axis | Grade | Rationale (with line refs) |
|------|-------|----------------------------|
| **Correctness** | **B+** | One real bug found in `_log_block` audit-trail (pre-fix line 922) — `aml_check_unavailable` collapsed to `aml_passed=True`, corrupting the audit log. Fixed inline. All other control flow (retry, dispute, AML, compliance, HALT, anomaly) is correct and fail-closed. Defense-in-depth against EPG-19 compliance-hold bridging is present (taxonomy Layer 1 at line 265 + C7 Layer 2 referenced but not re-implemented here). |
| **Tests** | **A-** | `test_e2e_pipeline.py` (37 scenarios) covers all outcomes and passes after fix. `test_e2e_latency.py`, `test_e2e_state_machines.py`, `test_e2e_decision_log.py`, `test_e2e_corridor.py`, `test_e2e_settlement.py`, `test_e2e_config.py` all exercise `LIPPipeline.process`. Gap: no explicit unit test for the `_log_block` audit-trail `aml_passed` field across all three `block_reason` values — added to follow-ups as L1. |
| **Security** | **A** | Fail-closed on C6 unreachable (line 383), fail-closed on C6 exception (line 885), SYSTEM_ERROR on C7 exception (line 563), no AML typology leakage (CIPHER rule), no secrets in file. EPG-14 governing-law derivation is delegated to C7 (not here). GAP-17 original payment amount is propagated (line 537). Retry detection uses `UETRTracker` composite context key (lines 238-243). |
| **Performance** | **B** | Budgeted sum is ~92 ms vs. 94 ms SLO — this file sits at the latency cliff. H1 (per-call executor construction) and H2 (per-call `inspect.signature`) are avoidable overhead. H2 fixed inline by lifting `import inspect` to module scope; the `inspect.signature` call itself remains per-call (filed as M1). Function-local imports at line 742 (`timedelta`) and 516 (`uncertainty_fee_adjustment`) also moved / left as appropriate. |
| **Maintainability** | **B** | `process` is 590 lines, 15 exit points, 9 distinct outcome branches. Each branch constructs a nearly-identical `PipelineResult` kwargs dict (~25 LOC × 8 branches ≈ 200 LOC of repetition). EPG comments are dense and valuable for auditors but increase visual noise. The function is too long to grade higher, and extraction is the right fix — filed as M2 rather than done inline (it would exceed the 10-line fix budget). |

**Aggregate:** B+. Production-ready, auditable, and safe. The refactor
debt is real but not urgent.

---

## 5. Findings

| ID | Severity | Line(s) | Description | Action | Status |
|----|----------|---------|-------------|--------|--------|
| C1 | **Critical** | 922 (pre-fix) | `_log_block` computes `aml_passed = block_reason != "aml_blocked"` which returns `True` when `block_reason == "aml_check_unavailable"`. EPG-27 means that path is a *fail-closed block because C6 was unreachable* — AML status is unverified, not passed. The audit-log entry written to C7 would therefore mis-record the block as "AML passed but something else went wrong", contaminating the regulatory audit trail under AMLD6 Art.10. | Narrow the expression to treat `aml_check_unavailable` as `aml_passed=False`. | **fixed-inline** (commit a) |
| H1 | High | 367 | `ThreadPoolExecutor(max_workers=2)` constructed per call. Thread-pool create/teardown on every above-threshold event burns ~1–3 ms of the 94 ms budget. | Hoist the executor to `self._c4c6_pool`, init in `__init__`, close in a `close()` method wired to the pipeline lifecycle. | **filed-as-followup** (resource lifecycle change, needs QUANT + FORGE sign-off) |
| H2 | High | 861 pre-fix | `import inspect` inside `_run_c6` runs on every C6 call. | Lifted to module-scope `import inspect` at line 28. | **fixed-inline** (commit a) |
| M1 | Medium | 862 | `inspect.signature(self._c6.check)` is recomputed on every call. Cache once in `__init__`. | Compute `self._c6_accepts_tenant_id = bool` at construction. | **filed-as-followup** |
| M2 | Medium | 419-710 | ~200 LOC of repeated `PipelineResult` construction across 8 outcome branches. | Extract `_build_result(outcome: str, ...)` factory. | **filed-as-followup** (>10 line refactor; out of inline-fix budget) |
| M3 | Medium | 742 pre-fix | `from datetime import timedelta` inside `if self._risk_engine` branch. | Lifted to module-scope import. | **fixed-inline** (commit a) |
| M4 | Medium | 282 | On early-BLOCK short-circuit, `loan_state` is reported as `LoanState.OFFER_PENDING.value` even though no offer was ever pending. Semantically misleading; downstream audit analytics may double-count "offers." | Either introduce a `LoanState.NOT_STARTED` or explicitly leave `loan_state=None`. | **filed-as-followup** (schema change, needs NOVA sign-off) |
| L1 | Low | — | No unit test specifically asserts that `_log_block(..., "aml_check_unavailable")` writes `aml_passed=False` to the C7 audit-log context. | Add a targeted test in `test_e2e_pipeline.py`. | **filed-as-followup** |
| L2 | Low | 169 | `create_redis_client()` is called in `__init__` — even in unit tests that pass a mock for every component. For a non-live test, this may unnecessarily attempt a Redis connection attempt (the factory has a fallback but still resolves `REDIS_URL`). | Already guarded; minor. | **noted only** |
| L3 | Low | 293-302 | EPG-28 composite entity key falls back to BIC-only when `debtor_account` is absent. Consistency across a rail upgrade (e.g. a BIC that later starts carrying `DbtrAcct`) will split that entity's velocity window. | Document the behaviour at pilot-bank handoff. | **filed-as-followup** |
| L4 | Low | 725 / 855 | Same `aml_dollar_cap_usd` / `aml_count_cap` `hasattr` block is repeated in `process` (721-727) and `_run_c6` (852-857). | Extract `_resolve_aml_caps()` helper. | **filed-as-followup** |
| L5 | Low | 946 | `_derive_maturity_days` returns 0 for unknown rejection codes after logging critical. Caller must understand "0 = no offer" semantics; currently enforced only by C7's downstream checks. | Add an explicit outcome path to raise or short-circuit to DECLINED. | **filed-as-followup** |

---

## 6. Follow-ups not fixed in this sprint (one-line reason each)

1. **H1 — executor lifecycle:** changes resource model of the pipeline (needs QUANT + FORGE sign-off on connection-pool + thread-pool ownership).
2. **M1 — cache `inspect.signature` result:** trivial but crosses the ML-engine DI boundary; batch with H1.
3. **M2 — extract `_build_result` factory:** >10 LOC and behaviour-preserving refactor; wait for the post-pilot stabilisation window.
4. **M4 — `LoanState.NOT_STARTED`:** new FSM state requires NOVA sign-off on state-machine invariants and a pass over downstream audit consumers.
5. **L1 — `_log_block` targeted test:** trivial test authoring; batch with the next test-coverage pass.
6. **L3 — EPG-28 composite key migration doc:** document-only; fold into pilot-bank MRFA annex.
7. **L4 — `_resolve_aml_caps` helper:** small, but couples to C7's attribute contract; batch with M2.
8. **L5 — unknown-rejection-code explicit outcome path:** requires taxonomy-change review (REX + NOVA).

---

## 7. Commits

- `fix(pipeline): correct audit-log aml_passed on C6 unavailable; hoist imports` — addresses C1, H2, M3.
- `docs(review): pipeline.py deep review and grading` — this file.

## 8. Verification

- `ruff check lip/` — clean.
- `PYTHONPATH=. python -m pytest lip/tests/test_e2e_pipeline.py -x -q` — 37 passed (pre- and post-fix).
- Full suite (`--ignore=lip/tests/test_e2e_live.py`) — see pytest output in commit.
- `test_e2e_live.py` skipped (Docker daemon socket not accessible in this session despite colima reported up; 3 live tests not run. Not a regression signal.).
