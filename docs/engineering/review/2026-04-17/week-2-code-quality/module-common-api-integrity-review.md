# Day 10 Task 10.2 — `common/`, `api/`, `integrity/` Module Review

**Date run:** 2026-04-19
**Reviewer:** Claude (Opus 4.7), subagent-driven-development skill, controller-executed after Agent-tool quota exhaustion.
**Scope:** `lip/common/` (16 files, ~4,100 LoC), `lip/api/` (12 files, ~3,200 LoC), `lip/integrity/` (8 files, ~1,700 LoC).
**Companion docs:** `day8-meta-checks.md`, `day9-task-9.1-summary.md`, `day9-task-9.2-summary.md`, `groq-qwen3-tos-review.md`, `module-pipeline-review.md`.

## Executive Summary

All three module trees are **counsel-viewable**. No Critical security exposure, no EPG-19 weakness, no AMLD6 audit-trail falsification, no auth bypass found. The crypto primitives in `common/encryption.py` and the secure-pickle wrapper in `common/secure_pickle.py` are textbook: fail-closed, constant-time compare, HMAC-verified-before-deserialise, OWASP-2023 PBKDF2 iteration count. HTTP auth at the application layer (`api/auth.py` + `api/app.py`) is fail-closed when no HMAC key is configured (`make_deny_all_dependency`).

Two **High** findings (defense-in-depth gaps, not live exposures):

- **API router factories fail open when `auth_dependency` is not passed** (5 routers, 6 sites). `app.py` always passes it, but the factory signature invites a future caller — or a test — to construct an unauthenticated router. Tighten by making `auth_dependency` required (raise if `None`).
- **Pydantic models lack `extra="forbid"` / `strict=True` across `common/schemas.py` (22 models) and `api/regulatory_models.py`.** Unknown / typo'd client fields are silently dropped rather than 422'd. High-impact on fee-adjacent and regulatory endpoints — clients can drift from the contract without ever seeing an error.

One **Medium** finding: `FEE_FLOOR_BPS = 300` is hardcoded three times in `common/schemas.py` (`ge=Decimal("300")`) instead of imported from `common/constants.py`. If QUANT ever changes the canonical floor, the schema-level validator will silently keep enforcing the old value. QUANT-sign-off duplication.

Aggregate grade: **A–** across all three trees. Grading table at the end.

## 1. `lip/common/` (16 files)

### 1.1 `constants.py` — QUANT canonical single-source-of-truth

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| C-1 | Info | `constants.py:18-33,40,85-87,108,111` | QUANT constants present: `FEE_FLOOR_BPS=Decimal("300")`, `LATENCY_P99_TARGET_MS=94`, `C1_FAILURE_PROBABILITY_THRESHOLD=0.110`, `MATURITY_CLASS_{A,B,C}_DAYS = 3/7/21`, `MATURITY_BLOCK_DAYS=0`, `UETR_TTL_BUFFER_DAYS=45`, `SALT_ROTATION_DAYS=365` / overlap `30`. All match CLAUDE.md. | None. Clean. |
| C-2 | Low | `constants.py` (all values) | No `typing.Final` annotation. Plan called for `Final` marking. Mutability is prevented by import-only pattern in practice (nobody reassigns module-level ints in `lip/`), but annotation would make the intent explicit to `mypy --strict`. | Add `from typing import Final` and annotate each QUANT constant. 30-minute refactor, zero runtime impact. Deferred. |
| C-3 | Low | `constants.py:36-44,164-175` | Comments cite dataset scope and sign-off dates (good — matches CLAUDE.md `DISPUTE_FN_CURRENT` template) but only sometimes include a commit hash. Example: `DISPUTE_FN_CURRENT` cites commit 3808a74; `SETTLEMENT_P95_CLASS_*_HOURS` cite BIS/SWIFT GPI but not the commit that landed them. | Backfill commit hashes when next touching each constant. Not blocking. |
| C-4 | Low | `schemas.py:8`, `conformal.py:1` (grep hits on `300`/`0.110`/`94`) | Plan called for detecting duplicate literals of QUANT values. `conformal.py` hit on unrelated coincidence (line number, not a duplicated QUANT value). `schemas.py:8` is import-count; actual duplicates live at `185/388/718` (see §1.2). | No action on conformal.py. See §1.2 for schemas.py. |

**Axes:** Correctness **A**, Tests **A-** (tested via usage in other tests), Security **A**, Performance **A** (constants — no perf dimension), Maintainability **A-**. **Overall: A.**

### 1.2 `schemas.py` (947 LoC)

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| S-1 | **Medium** | `schemas.py:185, 388, 718` — `ge=Decimal("300")` in three `fee_bps` fields | Hardcoded QUANT floor; does not import `FEE_FLOOR_BPS` from `constants.py`. If QUANT changes the canonical value, schema validators silently stay at 300. QUANT sign-off duplication. | Import `FEE_FLOOR_BPS` and use `ge=FEE_FLOOR_BPS`. Not fixed inline — Pydantic default/constraint changes can break existing snapshot tests; needs a focused PR. |
| S-2 | **High** | `schemas.py` (all 22 models) | Every model uses `model_config = ConfigDict(frozen=True)`. Good for immutability but NO `extra="forbid"`, NO `strict=True`. Pydantic v2 default is `extra="ignore"` — unknown fields are silently dropped. For fee-adjacent models (`FeeComputation`, `PipelineResult`, loan offers), a typo'd client field can bypass validation. | Adopt a `StrictBase(BaseModel)` with `ConfigDict(frozen=True, extra="forbid", strict=True)` and migrate the 22 models. Likely breaks some tests that pass auxiliary fields; Medium-sized PR. Not fixed inline. |
| S-3 | Low | `schemas.py` 947 LoC | Single file holds 22 Pydantic models across C1/C2/C3/C5/C6/C7 domains. Cyclomatic complexity is low (models are declarative) but navigability suffers. | Split by domain (e.g., `schemas/fee.py`, `schemas/loan.py`, `schemas/rejection.py`). Nice-to-have, not blocking. |

**Axes:** Correctness **A-**, Tests **A**, Security **B+** (strict-mode gap), Performance **A**, Maintainability **B+**. **Overall: B+.**

### 1.3 `encryption.py` (272 LoC) — CIPHER-grade crypto

Textbook implementation. No hardcoded keys. AES-256-GCM with NIST-recommended 12-byte random nonce, 16-byte GCM tag via `cryptography.hazmat`. HMAC-SHA256 for both identifier hashing and log signatures, constant-time verify via `hmac.compare_digest`. PBKDF2-HMAC-SHA256 at 600,000 iterations (OWASP 2023). Power-on self-test on import. All `ValueError` guards on empty keys/salts, wrong-length AES keys, wrong-length nonces.

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| E-1 | Info | `encryption.py:133` (`os.urandom(12)` random GCM nonce per encrypt) | 96-bit random nonce means NIST birthday-bound collision probability hits 2⁻³² after ~2³² encryptions under the same key. For LIP bank-pilot scale this is non-issue; CIPHER should document the rotation policy. | Key-rotation policy in CIPHER runbook: re-key every 2³² encryptions or annually, whichever first. Not a code change. |

**Axes:** Correctness **A+**, Tests **A**, Security **A+**, Performance **A**, Maintainability **A**. **Overall: A+.**

### 1.4 `secure_pickle.py` (211 LoC) — pickle RCE mitigation (B10-01/02)

HMAC-verified sidecar (`.sig`) is read and validated **before** `pickle.loads` runs. Fail-closed: missing sidecar, missing key, wrong-length key, HMAC mismatch all raise `SecurePickleError` with no fallthrough. `test_pickle_ban.py` enforces that this wrapper is the only legal pickle loader in the codebase.

**Findings:** none.

**Axes:** Correctness **A+**, Tests **A** (ban-test + unit coverage), Security **A+**, Performance **A**, Maintainability **A**. **Overall: A+.**

### 1.5 `governing_law.py` (91 LoC) — EPG-14 BIC-based jurisdiction

`bic_to_jurisdiction()` correctly uses BIC chars 4-5 (`bic[4:6].upper()`) per EPG-14. US → FEDWIRE, GB → CHAPS, eurozone TARGET2 members → TARGET2, else → UNKNOWN. Module docstring explicitly calls out that currency-based derivation is wrong. `law_for_jurisdiction()` is the jurisdiction→law mapping authority.

**Findings:** none. Matches CLAUDE.md canonical EPG-14 rule verbatim.

**Axes:** Correctness **A+**, Tests **A**, Security **A**, Performance **A**, Maintainability **A**. **Overall: A+.**

### 1.6 `regulatory_reporter.py` (409 LoC) — AMLD6 Art.10 audit trail

High-volume module. Spot-checked for the pattern that tripped pipeline.py (audit field value disagreeing with audit field label, e.g., `aml_passed=True` when the AML check was unavailable). No similar bug spotted; the module cleanly delegates field values to its callers. DORA and SR 11-7 export paths exist (see `regulatory_export.py`, 84 LoC).

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| R-1 | Info | `regulatory_reporter.py` (callers) | The integrity of `aml_passed`-style fields is only as good as the callers' correctness. The pipeline.py Critical fix (`aml_check_unavailable` → `aml_passed=False`) landed; no audit of every other caller was performed in this task. | Schedule a sweep across all `record_*` call sites for similar label/value drift. Out of Day 10.2 scope. |

**Axes:** Correctness **A**, Tests **A-**, Security **A**, Performance **A**, Maintainability **B+**. **Overall: A-.**

### 1.7 Remaining `common/*` modules (10 files)

Spot-checked:

- `state_machines.py` (339 LoC), `uetr_tracker.py` (210), `notification_service.py` (328), `royalty_batch.py` (167), `royalty_settlement.py` (159), `known_entity_registry.py` (156), `redis_factory.py` (85), `fx_risk_policy.py` (94), `regulatory_export.py` (84), `partial_settlement.py` (58), `swift_disbursement.py` (59).

No critical findings. `redis_factory.py` correctly falls back to in-memory on `REDIS_URL` absence (observable in app.py). `fx_risk_policy.py` enforces `SAME_CURRENCY_ONLY` default (GAP-12). `state_machines.py` exposes the state machine invariants referenced by `c3/`.

**Aggregate `common/` grade:** Correctness **A**, Tests **A-**, Security **A**, Performance **A**, Maintainability **A-**. **Overall: A.**

## 2. `lip/api/` (12 files)

### 2.1 `auth.py` + `app.py` — HMAC-SHA256 authentication

- `app.py:109-138` — fail-closed pattern. When `LIP_API_HMAC_KEY` is absent, `make_deny_all_dependency()` is installed so every protected route returns 401 (B2-01). Key parsing tries base64 then hex, raises `RuntimeError` at startup if both fail (B2-05/06). No silent fallback to raw UTF-8.
- `auth.py:83-141` — asymmetric replay window: 300s past tolerance, `_MAX_FUTURE_SECONDS = 300` future tolerance (B2-10). Signed scope covers method, host, path, sorted query string, SHA-256 body hash (B2-04). Constant-time HMAC compare via `verify_hmac_sha256` → `hmac.compare_digest`.
- `app.py:182-202` — every non-health router (`/admin`, `/portfolio`, `/known-entities`, `/miplo`, `/cascade`, `/api/v1/regulatory`) is mounted with `auth_dependency=auth_dep`. `/metrics` explicitly protected (B2-08). Only `/health` is unauthenticated — correct for K8s liveness/readiness probes.

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| A-1 | **High** | `admin_router.py:155`, `portfolio_router.py:334,375`, `cascade_router.py:154`, `miplo_router.py:71`, `regulatory_router.py:294` — 6 sites across 5 files | Every router factory has the pattern `deps = [Depends(auth_dependency)] if auth_dependency else []` (or the `is not None` variant). When a caller omits `auth_dependency`, the router mounts completely unauthenticated. `app.py` always passes it in production, but the signature is fail-open. A future refactor or test that forgets the argument ships an unauthenticated API. | Make `auth_dependency` a required keyword argument; raise `ValueError("auth_dependency is required")` if `None`. 6-line change across 5 files. Deferred — needs a QA pass to catch any test that relied on the omission. |
| A-2 | Medium | `auth.py:33` | `_MAX_FUTURE_SECONDS = 300` but the module comment at line 29-32 says: "This is set to 300s to match the existing test suite expectation. Tighten to 30s once the test is updated to reflect the tighter window." Backwards-compat debt — the wider window accepts tokens clock-skewed up to 5 minutes ahead, wider than a bank clock-sync SLA needs. | Update `test_future_timestamp_within_window` to use a +25s stamp, tighten `_MAX_FUTURE_SECONDS` to 30. Deferred. |
| A-3 | Medium | `auth.py:213-223` | `make_hmac_dependency` signs host="" — scope does not include HTTP Host header. Comment acknowledges backwards-compat and says "Tighten to include host once all clients are updated." A malicious intermediate could theoretically redirect a signed request to a different vhost (low likelihood behind TLS + reverse proxy, but defence-in-depth). | Coordinate with all signing clients (LIP internal test harness) to add Host, then flip the default. Deferred. |

### 2.2 Router files (admin, cascade, miplo, portfolio, regulatory, health)

- `regulatory_router.py` (589 LoC) — the highest-risk surface. Rate limiter wired via `TokenBucketRateLimiter(rate=100, period_seconds=3600)` in `app.py:284`. Good.
- `rate_limiter.py` (138 LoC) — token bucket. Spot-checked; only attached to `/api/v1/regulatory`. Other routers (portfolio, admin, cascade, miplo) have **no rate limit** at the router layer. Relying entirely on upstream (nginx/reverse proxy) for throttling.
- `admin_router.py:290-313` — `/admin/model-card` endpoint returns **501 Not Implemented** with an explicit refusal to forge regulatory documentation ("Returning placeholder data would constitute forged SR 11-7 documentation"). REX-approved pattern.
- `admin_router.py:219-287` — `/stress-test` endpoint has hard caps: `_STRESS_TEST_MAX_ITERATIONS=100`, `_STRESS_TEST_MAX_SECONDS=10`, with a daemon-thread watchdog. DoS-resistant.
- Pydantic models (`regulatory_models.py`) use `Field(..., min_length=3, ge=0.0, le=1.0, pattern="^(corridor|jurisdiction)$")` — per-field constraints are tight, but no `extra="forbid"` on the model class (same finding as S-2).

**Findings:**

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| A-4 | Medium | `app.py:284` (only `/api/v1/regulatory` has rate limit) | `admin`, `portfolio`, `cascade`, `miplo`, `known-entities` endpoints have no application-layer rate limit. Reliance on upstream nginx/reverse proxy is fine for pilot deployment but leaves a gap if a bank mounts the app behind an L4-only LB. | Extend `TokenBucketRateLimiter` to all non-health routers; tune per-route rates. |
| A-5 | Info | `regulatory_router.py:294` (5-line fix-open pattern) | Same as A-1. | See A-1. |
| A-6 | Low | `admin_router.py:270` `except Exception as exc: error_holder.append(exc)` inside daemon thread | Bare-ish exception capture within the thread; at `284-285` the exception is re-raised outside. Acceptable pattern but `Exception` swallows `KeyboardInterrupt`/`SystemExit` — defensible for a daemon thread. | Narrow to `(RuntimeError, ValueError, ImportError)` if QA confirms. |

**Aggregate `api/` grade:** Correctness **A-**, Tests **A-**, Security **B+** (A-1 + A-4 tip it from A), Performance **A**, Maintainability **A-**. **Overall: B+.**

## 3. `lip/integrity/` (8 files)

### 3.1 Module-by-module invariants

| Module | Lines | Invariant enforced | Test file |
|--------|------:|--------------------|-----------|
| `pipeline_gate.py` | 150 | Pipeline must not start if any integrity check fails (GPL contamination, unattributed OSS, stale model evidence > 720h). | `test_integrity_gate.py` |
| `claims_registry.py` | 212 | Every documented claim has a matching evidence record. | `test_integrity_claims.py` |
| `evidence.py` | 200 | HMAC-signed evidence records; tamper detection via `sign_evidence` / `utcnow`. | `test_integrity_evidence.py` |
| `oss_tracker.py` | 244 | OSS package attribution; GPL/AGPL/SSPL contamination detection. | `test_integrity_oss.py` |
| `compliance_enforcer.py` | 202 | **Delve defence**: compliance reports must be generated from live data (SHA-256 data hash, n-gram Jaccard boilerplate detection > 90%, timestamp-after-observation-period check). | `test_integrity_compliance_enforcer.py` |
| `breach_protocol.py` | 326 | Defines breach types + response lifecycle; can't be bypassed once triggered. | `test_integrity_breach.py` |
| `vendor_attestation.py` | 236 | Vendor attestation records (who signed what, when). | `test_integrity_attestation.py` |
| `vendor_validator.py` | 287 | Validates vendor attestations using `compliance_enforcer` primitives. | `test_integrity_vendor.py` |

Every module has a matching test file under `lip/tests/`. Coverage is structural (happy + failure paths) — full Day 8 coverage was 91% across 2,642 tests.

### 3.2 Findings

| # | Severity | Location | Finding | Remediation |
|---|----------|----------|---------|-------------|
| I-1 | Low | `pipeline_gate.py:114` — `for ev in self._claims._evidence.values()` | Access to the private `_evidence` attribute of `ClaimsRegistry` breaks encapsulation. Change to a public iterator (`evidence_records()`) on the registry. | ~10-line refactor, zero behaviour change. Deferred. |
| I-2 | Info | `pipeline_gate.py:55-58` | Both registries are `Optional[...]` and default `None`; when `None`, the corresponding check silently no-ops. Documented in the docstring as "graceful no-op for backward compatibility with existing tests that do not yet wire the gate." Structural risk: a real deployment could start without wiring either registry and silently pass the gate. | Add a stricter `require_claims: bool = True` / `require_oss: bool = True` in production construction path. Deferred — not a live exposure since `app.py` does not currently construct `IntegrityGate` at all (it's used by pipeline.py, already covered in 10.1). |
| I-3 | Info | `compliance_enforcer.py:32` `DEFAULT_BOILERPLATE_THRESHOLD = 0.90` | Constant duplicated as `common/constants.py` "matches the constant added to" comment — but the constant does not actually appear in `constants.py` (grep-confirmed). Docstring describes intent that is not backed by the code. | Either add the shared constant to `constants.py` and import it here, or drop the misleading comment. |

**Aggregate `integrity/` grade:** Correctness **A**, Tests **A** (every module has a test file), Security **A**, Performance **A**, Maintainability **B+** (I-1, I-3). **Overall: A-.**

## 4. Fixes Applied Inline

**None.** No finding rose to the Critical bar (no EPG-19 violation, no AMLD6 audit-trail falsification, no auth bypass). The two High findings (A-1 router fail-open, S-2 Pydantic strictness) touch 5 files and 22 models respectively — Fix Policy says High ≤ 30 lines / 1 file → fix inline, else defer. Both deferred.

## 5. Follow-Ups Not Fixed (by severity)

**High:**
1. **API router fail-open default** — make `auth_dependency` required across 5 router factories (A-1). Defence-in-depth, no live exposure since `app.py` wires it correctly.
2. **Pydantic strict mode** — adopt a `StrictBase(BaseModel)` with `extra="forbid"` across `common/schemas.py` (22 models) and `api/regulatory_models.py` (S-2). Requires coordinated test update.

**Medium:**
3. **Import `FEE_FLOOR_BPS` in `schemas.py`** — replace three `ge=Decimal("300")` with `ge=FEE_FLOOR_BPS` (S-1). 3-line change, needs snapshot-test verification.
4. **Rate limit beyond `/regulatory`** — extend `TokenBucketRateLimiter` to `admin`, `portfolio`, `cascade`, `miplo`, `known-entities` routers (A-4).
5. **Tighten `_MAX_FUTURE_SECONDS` to 30s** — update test harness and flip (A-2).
6. **Include Host in HMAC signed scope** — coordinate with signing clients and flip default (A-3).

**Low:**
7. **Add `typing.Final` to QUANT constants** in `constants.py` (C-2).
8. **Backfill commit hashes** on `SETTLEMENT_P95_*` and other QUANT constants (C-3).
9. **Replace `_claims._evidence` access** with a public iterator on `ClaimsRegistry` (I-1).
10. **Reconcile `DEFAULT_BOILERPLATE_THRESHOLD`** — either add to `constants.py` or drop the misleading comment (I-3).
11. **Split `schemas.py`** into per-domain files (S-3).

**Info:**
12. **Sweep `RegulatoryReporter` callers** for label/value drift in audit fields, similar to the pipeline.py `aml_check_unavailable` bug (R-1).
13. **CIPHER key-rotation policy** — document 2³²-encryption / annual rotation for AES-GCM random-nonce schedule (E-1).

## 6. Aggregate Grade Table

| Module | Correctness | Tests | Security | Performance | Maintainability | Overall |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|
| `common/constants.py` | A | A- | A | A | A- | **A** |
| `common/schemas.py` | A- | A | B+ | A | B+ | **B+** |
| `common/encryption.py` | A+ | A | A+ | A | A | **A+** |
| `common/secure_pickle.py` | A+ | A | A+ | A | A | **A+** |
| `common/governing_law.py` | A+ | A | A | A | A | **A+** |
| `common/regulatory_reporter.py` | A | A- | A | A | B+ | **A-** |
| `common/` remaining (10 files) | A | A- | A | A | A- | **A** |
| **`common/` aggregate** | **A** | **A-** | **A** | **A** | **A-** | **A** |
| `api/auth.py` + `api/app.py` | A- | A | A- | A | A | **A** |
| `api/admin_router.py` | A- | A | B+ | A | A- | **A-** |
| `api/portfolio_router.py` | A- | A | B+ | A | A- | **A-** |
| `api/regulatory_router.py` | A- | A | B+ | A | A- | **A-** |
| `api/cascade_router.py` + `miplo_router.py` | A- | A- | B+ | A | A- | **B+** |
| `api/rate_limiter.py` | A | A | A | A | A | **A** |
| **`api/` aggregate** | **A-** | **A-** | **B+** | **A** | **A-** | **B+** |
| `integrity/pipeline_gate.py` | A | A | A | A | B+ | **A-** |
| `integrity/evidence.py` + `claims_registry.py` | A | A | A | A | A | **A** |
| `integrity/oss_tracker.py` | A | A | A | A | A | **A** |
| `integrity/compliance_enforcer.py` | A | A | A | A | B+ | **A-** |
| `integrity/breach_protocol.py` | A | A | A | A | A- | **A** |
| `integrity/vendor_attestation.py` + `vendor_validator.py` | A | A | A | A | A | **A** |
| **`integrity/` aggregate** | **A** | **A** | **A** | **A** | **B+** | **A-** |
| **Task 10.2 overall** | **A** | **A-** | **A-** | **A** | **A-** | **A-** |

## 7. Cross-References

- Pipeline review (Day 10.1): `module-pipeline-review.md` — graded B+ overall. Fixed one Critical AMLD6 audit-trail bug and one High import-hoist before landing.
- Meta-checks (Day 8): `day8-meta-checks.md` — coverage 91% on 2,642 tests, ruff/mypy/bandit clean after inline fixes.
- Dependency audits (Day 9): 0 Python CVEs, 0 Rust advisories, 0 Go advisories, 0 gitleaks findings, Groq ToS cleared, Qwen3 Apache 2.0 cleared.
