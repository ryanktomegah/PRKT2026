# Day 11 Task 11.1 — C6 AML / Velocity Security Deep-Dive

**Date:** 2026-04-19
**Reviewer:** CTO lens (CIPHER-focused)
**Scope:** `lip/c6_aml_velocity/` — 10 Python files (3,146 LOC) +
`rust_velocity/` PyO3 crate (1,141 LOC Rust).
**Goal:** Identify security, correctness, and audit-defensibility gaps
in the AML/velocity gate prior to external lawyer review.

## Axes and grades

| Axis | Grade | Summary |
|------|-------|---------|
| Cryptographic hygiene | **C+** | Raw `SHA-256(value ‖ salt)` used in 8 sites (Python + Rust) instead of HMAC. Repo already migrated `lip.common.encryption.hash_identifier` to HMAC under B1-08 — C6 module was left behind. |
| Fail-closed posture | **A-** | Sanctions screening error → BLOCK (aml_checker.py:249-257). Resolver misconfig → ConfigurationError. Anomaly-unfitted → RuntimeError. Structuring detector requires explicit `single_replica` or `redis_client`. |
| TOCTOU safety | **A** | EPG-25 atomic check-and-record via Lua EVAL (Redis) + `_check_record_lock` (in-memory) + DashMap entry write-guard (Rust). Three independent correct implementations. |
| Audit defensibility | **B-** | sanctions.json has no freshness metadata. Impossible to prove from the artefact alone "what date was this screened against?". Stale docstrings about default $1M / count=100 contradict EPG-16. |
| Constant hygiene | **B** | `BENEFICIARY_CONCENTRATION_THRESHOLD`, `ROTATION_INTERVAL_DAYS`, `OVERLAP_DAYS` locally redefined — duplicates canonical `lip.common.constants` values. Single-source-of-truth violated. |
| Privacy engineering | **A** | Raw entity_id never stored. Transliteration + phonetic matching in sanctions.py. Salt rotation with 30d overlap. Per-tenant salt isolation. |
| Concurrency / distribution | **A-** | Redis sorted-set + Lua for distributed path. `StructuringDetector` properly refuses silent in-memory operation without explicit opt-in. `VelocityBridge` same pattern. |

**Aggregate:** **B+** — sound architectural primitives let down by the raw-SHA-256 inconsistency and the missing sanctions-freshness metadata. Both are fixable; neither requires re-architecting.

## Findings

### 🔴 HIGH — C6-H1: Raw `SHA-256(value ‖ salt)` across 8 sites instead of HMAC-SHA256

**Locations:**

| File | Line | Function |
|------|------|----------|
| `salt_rotation.py` | 148 | `SaltRotationManager.hash_with_current` |
| `salt_rotation.py` | 167 | `SaltRotationManager.hash_with_previous` |
| `velocity.py` | 442 | `VelocityChecker._hash_entity` |
| `velocity.py` | 457 | `VelocityChecker._hash_beneficiary` |
| `cross_licensee.py` | 24 | `cross_licensee_hash` |
| `tenant_velocity.py` | 261 | `TenantVelocityChecker.bpi_entity_hash` |
| `tenant_velocity.py` | 265 | `TenantVelocityChecker._bpi_beneficiary_hash` |
| `rust_velocity/src/velocity.rs` | 127–132 | `RollingVelocity::hash_id` |

**Problem.** `hashlib.sha256(value.encode() + salt).hexdigest()` is not a
keyed-PRF. It is vulnerable to length-extension: an attacker who learns
`H(value ‖ salt)` and the length of `value ‖ salt` can compute
`H(value ‖ salt ‖ suffix)` for arbitrary `suffix` without ever seeing
the salt. The correct primitive for "hash this identifier so the
salt acts as a secret key" is HMAC-SHA256.

**The repo already knows this.** `lip/common/encryption.py:hash_identifier`
uses HMAC-SHA256, and its docstring says verbatim: *"raw SHA-256
concatenation is vulnerable to length-extension attacks and offers no
keyed binding."* The invariant test at
`lip/tests/test_security_comprehensive.py:91` asserts this:

```python
# B1-08: hash_identifier now uses HMAC-SHA256 (keyed), not raw SHA-256
expected_hmac_sha256 = _hmac.new(salt, value.encode("utf-8"), hashlib.sha256).hexdigest()
assert result == expected_hmac_sha256
# Verify it does NOT match raw SHA-256 (which was the old, insecure implementation)
raw_sha256 = hashlib.sha256(value.encode("utf-8") + salt).hexdigest()
assert result != raw_sha256
```

The C6 velocity/cross-licensee/tenant hash functions were evidently
not migrated in the B1-08 rollout. `test_security_comprehensive.py:354`
even pins the current raw-SHA-256 behaviour of `cross_licensee_hash`
as a *"SECURITY INVARIANT"* — it isn't; it's the legacy pattern.

**Realistic threat assessment.** The length-extension attack is difficult
to weaponise for this codebase — the attacker would need (a) a digest
leak (Redis memory disclosure, log leak), (b) the exact byte sequence
used to produce it, and (c) a code path that accepts a pre-extended
digest. The VelocityChecker never accepts digests as input; it always
recomputes from raw `entity_id + salt`. So the observable practical
harm is low.

The **consistency** concern is higher: a CIPHER-level auditor will
flag the raw-concat pattern on sight, and the repo's own
B1-08 migration establishes the desired direction.

**Fix scope.** Migrating requires coordinated changes to:

1. Four Python files (salt_rotation, velocity, cross_licensee, tenant_velocity)
2. Rust `rust_velocity/src/velocity.rs:127-132`
3. Two invariant tests in `test_security_comprehensive.py` (lines 91-105 is fine; line 349-355 needs `expected` updated)
4. **Data migration:** existing Redis keys `lip:velocity:events:{hash}`,
   `lip:cl_velocity:{hash}:{metric}`, `lip:salt:{current|previous}`
   are computed from the old digest. During the 24-hour rolling window,
   both the old and new hash key spaces must be accepted for reads so
   the AML gate does not lose velocity state during the switchover.
5. The 30-day salt-rotation overlap window gives a natural deprecation
   window; the safest migration is to treat the construction change
   like a salt rotation.

**Fix decision (per Fix Policy):** **DEFER** — multi-file, cross-language
change spanning Python + Rust + live Redis keys with a data-migration
requirement. Not a 30-line one-file fix; cannot go inline during this
review without risk.

**Remediation plan (owner: CIPHER; target: Week 5, post-lawyer review):**

1. Create `lip.c6_aml_velocity.hashing` module exposing `entity_hash(value, salt)` → HMAC-SHA256
2. Add dual-read mode to `VelocityChecker.check`: look up both old and new hash keys during a 60-day migration window, record under new hash only
3. Migrate `cross_licensee.py`, `tenant_velocity.py`, `salt_rotation.py` to the new function
4. Port the same construction to `rust_velocity/src/velocity.rs`
5. Update tests — remove the "SECURITY INVARIANT: must equal raw SHA-256" assertion in `test_security_comprehensive.py:349-355`; add one that asserts the HMAC construction
6. Remove the dual-read path after the 60-day window closes

**Risk of deferral:** Low. The practical length-extension attack vector is narrow, and the window stays open until Week 5 anyway because we cannot ship a live Redis key rewrite without a planned deploy.

### 🟠 HIGH — C6-H2: sanctions.json has no freshness metadata

**Location:** `sanctions_loader.py:198-216` (`build_sanctions_json`).

**Problem.** The JSON snapshot has the shape:

```json
{
  "OFAC": [...],
  "UN":   [...],
  "EU":   [...]
}
```

No `generated_at`, no per-source `last_modified`, no snapshot version.
Once written, the file cannot prove when it was built or against which
upstream revision. A regulator / bank audit team asking "What date was
this loan screened against the then-current OFAC list?" has no way to
answer from the artefact.

Under AMLD6 Art.10 (which the EPG-19 rationale already cites), a
regulated entity must be able to evidence that its screening was
performed against the sanctions list as it existed at the time. This
is a non-negotiable audit-trail requirement for any bank pilot.

**Fix inline — scope small.** Add a `_metadata` key to the output of
`build_sanctions_json` and validate it in `validate_snapshot`.

```json
{
  "_metadata": {
    "generated_at": "2026-04-19T14:32:05+00:00",
    "builder_version": "sanctions_loader/1.0",
    "source_urls": {"OFAC": "...", "UN": "...", "EU": "..."}
  },
  "OFAC": [...], ...
}
```

`sanctions.py` already ignores unknown keys because it does
`data.get(list_name.value, [])` per list. Zero compatibility risk.

**Fix decision:** **FIX INLINE.**

### 🟡 MEDIUM — C6-M1: Duplicated canonical constants

**Locations:**

| File | Line | Local | Canonical |
|------|------|-------|-----------|
| `salt_rotation.py` | 20 | `ROTATION_INTERVAL_DAYS = 365` | `common.constants.SALT_ROTATION_DAYS` |
| `salt_rotation.py` | 21 | `OVERLAP_DAYS = 30` | `common.constants.SALT_ROTATION_OVERLAP_DAYS` |
| `velocity.py` | 45 | `BENEFICIARY_CONCENTRATION_THRESHOLD = Decimal("0.80")` | `common.constants.BENEFICIARY_CONCENTRATION` |

**Problem.** If QUANT / CIPHER change any of these canonical constants,
the C6 module silently ignores the change. The salt rotation case is
particularly consequential — extending rotation from 365d to 400d in
`common.constants` would leave this module rotating on the old cadence.

**Fix decision:** **FIX INLINE.** Same Day-10 pattern: import from
`lip.common.constants`, delete the local re-definition.

### 🟡 MEDIUM — C6-M2: Stale docstrings contradict EPG-16

**Locations:**

- `velocity.py:2-4` — module docstring: *"Dollar cap $1M, count cap 100 per entity per 24hr rolling window."*
- `aml_checker.py:212-214` — `check()` docstring parameter block: *"dollar_cap_override: Optional USD cap to use instead of the default $1M limit. count_cap_override: Optional count cap to use instead of the default 100 limit."*

**Problem.** EPG-16 (2026-03-18) removed the retail-scale defaults:
AML caps are now default-0 (unlimited), set per-licensee via C8 token.
The docstrings still advertise a non-existent $1M / 100 default that
the code rejected long ago. A future developer reading the docstring
may write `dollar_cap_override=None` expecting the $1M floor; the
actual behaviour is that caps become unlimited.

**Fix decision:** **FIX INLINE.** Docstring-only change.

### 🟡 MEDIUM — C6-M3: sanctions_loader silent-fail per-source

**Location:** `sanctions_loader.py:97, 146, 171` — each fetcher's
`except Exception: logger.exception(...)` path returns an empty list.
The `_cli()` entrypoint only bails when **all three** lists return
empty (line 297). A partial failure (e.g., EU endpoint down) silently
produces a snapshot with zero EU entries, guaranteeing that every
EU-only-designated party passes screening on the next deploy.

**Fix decision:** **DOCUMENT.** Fix is operational — the sanctions-load
step should run in CI with a minimum-entry-count assertion per source
(*e.g.*, OFAC must yield ≥ 1,000 entries; UN ≥ 500; EU ≥ 1,000). CI
guard is out-of-scope for this review (falls under FORGE), but record
it as a pilot-blocker in the follow-up register.

### 🟡 MEDIUM — C6-M4: Rust sanctions bridge lacks phonetic matching

**Location:** `sanctions_bridge.py:16-19` — docstring says *"Both
implementations share the same known compliance gap (no transliteration
/ phonetic matching)"*. But `sanctions.py:65-118` **has** transliteration
and soundex matching (added under B7-03). The Python screener does
both; the Rust screener does neither.

**Problem.** Production toggles to the Rust path (when the extension
compiles) silently lose transliteration + phonetic matching compared
to the Python path — a silent compliance regression.

**Fix decision:** **DOCUMENT.** Bringing parity in Rust requires porting
NFKD normalization + Soundex + transliteration to Rust, which is a
meaningful Rust-side engineering task. Not a one-file fix; record for
CIPHER follow-up.

### 🟢 LOW — C6-L1: Anomaly detector skip is DEBUG-level

**Location:** `aml_checker.py:348-349` —
`logger.debug("Anomaly detection skipped: %s", exc)`. An exception in
the anomaly detector makes the gate silently skip a soft-signal
detector. At DEBUG level this is invisible in production log
pipelines (typical log level = INFO or WARNING). Monitoring team
would never know anomaly is disabled.

**Fix decision:** **DOCUMENT.** Trivial one-liner but not security-
critical (soft flag; doesn't affect block outcome). Defer to cleanup
round.

### 🟢 LOW — C6-L2: Non-atomic in-memory dict access on `RollingWindow._records`

**Location:** `velocity.py:194-195, 394`. The `defaultdict(deque)`
insertion and the `_cleanup_expired` eviction are not individually
locked. Multiple-thread use of `RollingWindow.add()` from the in-memory
path relies on the higher-level `_check_record_lock` in `VelocityChecker`.
A direct caller of `RollingWindow.add()` without the outer lock has a
TOCTOU race on `_cleanup_expired` vs `append`.

**Fix decision:** **DOCUMENT.** In-memory path is already explicitly
flagged in `velocity_bridge.py:137-143` as requiring `single_replica=True`
opt-in. No external caller reaches `RollingWindow.add()` directly today
(aml_checker always goes through VelocityChecker). Re-check after any
refactor that exposes `RollingWindow` publicly.

### ℹ️ INFO — C6-I1: Structuring-detector and velocity-bridge opt-in pattern is exemplary

**Locations:** `tenant_velocity.py:90-101, 95-101` and `velocity_bridge.py:137-143`.
Both classes **refuse to construct** in an in-memory mode unless the
caller passes `single_replica=True` to explicitly acknowledge the
no-durability / no-multi-replica constraint. This is the correct
pattern for security-critical components whose failure mode is
"silently degrades under scale-out". Propagate this pattern elsewhere.

### ℹ️ INFO — C6-I2: Fail-closed sanctions error handling is correct

**Location:** `aml_checker.py:246-257`. Exception in `_sanctions.screen()`
is caught and the result is `passed=False, reason="SANCTIONS_SCREENING_ERROR"`.
No silent-pass. Matches CIPHER policy for a pre-offer hard gate.

### ℹ️ INFO — C6-I3: Rust safety posture is clean

`rust_velocity/src/` contains 2 `expect(...)` calls (`sanctions.rs:103, 136`)
both on Aho-Corasick `build()` which is documented-infallible on
empty input. No `unwrap()`, no `panic!`, no `unsafe` blocks. Prior
Day 9.2 cargo-audit was also clean.

## Summary of fixes applied in this commit

- [x] C6-H2 (HIGH) fixed inline: sanctions.json builder now emits a `_metadata` block with `generated_at` / `builder_version` / `source_urls`; `validate_snapshot` accepts it.
- [x] C6-M1 (MEDIUM) fixed inline: `salt_rotation.py` and `velocity.py` now import canonical constants from `lip.common.constants`.
- [x] C6-M2 (MEDIUM) fixed inline: stale docstrings in `velocity.py` module header and `aml_checker.py:check()` parameter block updated to EPG-16 truth ("0 = unlimited").

## Summary of fixes deferred

- [ ] C6-H1 (HIGH): migrate raw SHA-256 → HMAC-SHA256 across 8 sites (4 Python files + Rust crate). Requires coordinated data migration on live Redis keys; must be scheduled with CIPHER during Week 5 post-lawyer review. Risk of deferral is low — practical length-extension attack vector is narrow.
- [ ] C6-M3 (MEDIUM): CI guard enforcing minimum entry counts in `sanctions_loader._cli`. Operational / CI scope — falls under FORGE.
- [ ] C6-M4 (MEDIUM): port transliteration + soundex to `rust_velocity/src/sanctions.rs`. Rust-side engineering task; schedule with CIPHER + ARIA.
- [ ] C6-L1 (LOW): raise log level of anomaly-skip path from DEBUG to WARNING. Trivial cleanup; defer to next touch of aml_checker.py.
- [ ] C6-L2 (LOW): document in `RollingWindow.add()` docstring that the in-memory path is not thread-safe in isolation. Defer to next touch.

## Trigger assessment

**No Trigger-#3 escalation.** Findings are engineering-quality and
security-hygiene concerns. None indicate a compliance blocker for
pre-lawyer review. C6-H1 is elevated for CIPHER visibility but the
practical attack surface under the current deployment (Redis-internal,
no public digest exposure) is narrow enough that deferral to a planned
Week-5 migration is the correct call.

**No Trigger-#4 escalation.** No secrets, no AML typology leakage, no
corpus files, no sanctioned-entity-name disclosures in code paths.
