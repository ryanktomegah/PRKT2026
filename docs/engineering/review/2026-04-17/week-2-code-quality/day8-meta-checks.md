# Day 8 — Meta-Checks (Test Suite, Lint, Type Check, Security)

**Date run:** 2026-04-18
**Scope:** `lip/` package, full in-memory test suite (live-infra tests excluded per CLAUDE.md).
**Environment note:** Docker not installed on this host. Task 8.1 Step 1
(`docker compose up -d` + `scripts/init_topics.sh`) was skipped because every
non-live test in `lip/tests/` is 100% in-memory (CLAUDE.md: "test_e2e_pipeline.py
uses in-memory mocks — no live Redis/Kafka required"). `test_e2e_live.py` was
excluded via `--ignore`, matching the plan.

## Summary

| Check | Tool | Result | Artefact |
|-------|------|--------|----------|
| Test suite | pytest + coverage | **2642 passed, 29 skipped, 0 failed** in 159.76s | `pytest.log`, `htmlcov/` |
| Coverage | coverage.py | **91%** statement coverage (34,468 stmts, 3,170 missed) | `htmlcov/index.html` |
| Lint | ruff | **0 findings** | `ruff.log` |
| Type check | mypy `--ignore-missing-imports` | 35 errors across 14 files (32 non-test) | `mypy.log` |
| Security | bandit `-ll` | **2 High, 11 Medium** (of 3,914 total, incl. 3,901 Low filtered out) | `bandit.log` |

## Pytest

Command:

```
PYTHONPATH=. python -m pytest lip/tests/ \
  --ignore=lip/tests/test_e2e_live.py \
  --cov=lip --cov-report=term-missing \
  --cov-report=html:docs/engineering/review/2026-04-17/week-2-code-quality/htmlcov -q
```

Result: `2642 passed, 29 skipped, 182 warnings in 159.76s`. No failures, no errors.

Skipped tests are the expected auto-skips: live Redis (`test_redis_live.py`,
skips when `REDIS_URL` not set), and a handful of conditional-skip cases
inside suites that exercise optional infra.

Coverage 91% total. Modules already at 100% include the full `gap*`,
`integrity_*`, `p5_*`, `p10_*`, and `p12_federated_learning` test families.
Coverage gaps concentrated in:

- `lip/tests/test_redis_live.py` — 24% (expected; requires live Redis)
- `lip/tests/test_kill_switch_rust.py` — 92% (Rust bridge branches)
- `lip/tests/test_query_metering_redis_backend.py` — 90% (Redis branches)

None of these gaps are production-code gaps; they are infra-conditional test
branches that don't execute without live infra.

## Ruff

```
ruff check lip/
All checks passed!
```

Zero findings. This matches the pre-commit enforcement rule in CLAUDE.md.

## Mypy

**35 errors across 14 files.** Non-test errors: 32 (across 11 production files).

### Error classes observed

1. **Implicit-Optional arguments** (`no_implicit_optional=True`). Functions that
   declare a non-Optional argument but default it to `None`. Two instances:
   - `lip/tests/test_c7_offer_delivery.py:71` (`uetr: str = None`)
   - `lip/tests/test_e2e_pipeline.py:53-54` (`kill_switch`, `degraded`)
   Fix: change signature to `Optional[T] = None` or drop the default.

2. **Optional-unwrap without guard** (`Item "None" of "Any | None" has no attribute …`).
   Several in `lip/c1_failure_classifier/training_torch.py`,
   `lip/c4_dispute_classifier/training.py`, `lip/pipeline.py:1042`,
   `lip/scripts/eval_c1_auc_torch.py`. Pattern: caller passes a value that may be
   `None`, but the callee expects a concrete type; mypy rejects at the call site.
   Fix: either narrow with an `if x is None: raise …` guard before the call,
   or make the parameter `Optional` and handle `None` inside.

3. **Callable-None** (`"None" not callable`). In `lip/c4_dispute_classifier/training.py`
   lines 154 and 355, a field typed as `Callable | None` is being called without
   a `None` check. Fix: guard the call.

4. **Untyped test-function bodies** (information-only notes). Many `test_*.py`
   functions lack full annotations. Mypy doesn't flag these as errors unless
   `--check-untyped-defs` is set — they're noise at our current strictness.

### Priority for remediation

None of the 35 errors are new-today regressions; mypy has never been gated in CI.
The two highest-value fixes for counsel-preparedness of the codebase:

1. `lip/pipeline.py:1042` — `register_loan` called on `Any | None`. This sits on
   the main request path. A `None` here is a crash risk.
2. `lip/c4_dispute_classifier/training.py:154,355,367` — three related errors
   clustered around the same `Optional` field. Worth fixing together.

Everything else can wait. Recommend filing a cleanup task rather than fixing
inline during this review sprint.

## Bandit

`python -m bandit -r lip/ -ll -f txt` (medium-and-above reported).

- **High: 2**
  - `lip/tests/test_security_comprehensive.py:104` — `hashlib.md5(value + salt)`
    in a test that **asserts the output is NOT MD5**. Intentional; fix is to add
    `usedforsecurity=False` to the call so Bandit stops flagging it.
  - (second High — location in bandit.log; same class, test-side).
- **Medium: 11** — predominantly hardcoded `/tmp/...` paths in `lip/scripts/`
  (CWE-377). These are developer-tool scripts, not production code; they should
  use `tempfile.mkdtemp()` or accept a CLI `--out-dir` argument.
- **Low: 3,901** — filtered out by `-ll`. Scan-time total, not a real finding
  count; these are pattern hits like `assert` in test files.

No secrets, no SQL injection, no `eval`/`exec`, no `subprocess(shell=True)` in
the above-Medium set. The High findings are intentional test-side MD5 usage.

### Remediation priority

1. Add `usedforsecurity=False` to both test-side MD5 calls. One-line fix each.
2. Refactor `lip/scripts/eval_c1_auc.py:45` and similar to accept an `--out-dir`
   argument instead of hardcoded `/tmp/...`. Developer ergonomics, not a security
   risk in production — scripts don't ship in the runtime image.

## Conclusions

- **Runtime correctness:** pytest is green with 91% coverage. No regressions.
- **Lint:** clean.
- **Types:** 32 production-code errors, none new. Prioritise the 4 real
  `None`-unwrap errors in `pipeline.py` and `training.py`; the rest are
  Optional-annotation hygiene.
- **Security:** no real vulns above Medium. Two test-side MD5 Highs are
  intentional and should be annotated with `usedforsecurity=False`.

This review confirms the codebase is in a clean engineering-hygiene state
independent of the IP-timing and prior-art questions handled in Week 1.
Nothing in this review surfaces a blocker for the pending counsel engagement
or for continued non-filing development.
