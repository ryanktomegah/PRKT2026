# C8 License Manager — Code Quality & Security Review

**Sprint**: Pre-Lawyer Review (Day 11, Task 11.2)
**Date**: 2026-04-19
**Scope**: `lip/c8_license_manager/` (1,426 LOC across 6 files)
**Reviewer**: CIPHER (security lens)
**Branch**: `codex/pre-lawyer-review`
**Aggregate grade**: **A−**

---

## 1. Executive summary

C8 is the BPI licensing enforcement layer — offline HMAC verification of signed
tokens at container boot, with a hard-wired kill switch on any failure. The module
is materially stronger than most of the rest of the repo on audit defensibility and
fail-closed discipline. Two notable strengths carry the grade:

- The `LicenseToken.canonical_payload()` introspection pattern (B3-02) makes
  "added a field, forgot to sign it" impossible.
- The `_AML_CAP_UNSET = -1` sentinel (EPG-16/17) + `from_dict` `KeyError` +
  boot-validator rejection chain enforces that BPI provisioning tokens state AML
  caps deliberately — a missing cap does **not** silently become "unlimited."

Two HIGH findings keep this from being a flat A:

- **C8-H1**: `RegulatorSubscriptionToken.canonical_payload()` is hand-written
  rather than derived via `dataclasses.fields()`. This is the exact bug class that
  B3-02 fixed on `LicenseToken`. It is the same 20-line fix. **Applying inline.**
- **C8-H2**: `revenue_metering.RevenueMetering` accepts any `tenant_id` without
  authz on the caller. The module is currently only invoked from internal plumbing
  (`app.py` settlement bridge), so exposure is contained — but the enforcement
  point for tenant = authenticated-tenant is unspecified. **Document** (architectural).

---

## 2. Scoring

| Axis | Grade | Rationale |
|------|-------|-----------|
| Crypto hygiene | **A−** | HMAC-SHA256 + `hmac.compare_digest` throughout; keys env-sourced; empty-key rejected. Single blemish: C8-H1 hand-written regulator payload. |
| Fail-closed | **A** | Boot validator → `KillSwitch.activate()` on **every** failure path; component-not-licensed raises `RuntimeError`; empty metering key rejected at construction; mode mutex (`single_replica` xor `redis_client`) enforced. |
| TOCTOU | **A** | Redis path uses Lua `_ATOMIC_RECORD_LUA` for single-round-trip check+increment+append+TTL; in-memory path serialises via `threading.Lock`. B3-01 annotation explicitly names the invariant. |
| Audit / evidence | **A−** | `QueryMeterEntry.hmac_signature` signed per-query; revenue waterfall invariant documented (`processor_take + bpi_net == gross_fee`). `schema_version` is present but unenforced (C8-M2). |
| Constants hygiene | **A** | `PROCESSOR_TAKE_RATE_{MIN,MAX}_PCT` from `common.constants`; `_AML_CAP_UNSET` sentinel is well-named and scoped. `_VALID_PHASES` / `_VALID_LICENSEE_TYPES` duplicated (with documented rationale) from `deployment_phase.py`. |
| Privacy / PII | **B+** | `LicenseToken.verify_token` truncates `licensee_id` in one log. `RegulatorSubscriptionToken.verify_regulator_token` does **not** truncate `regulator_id` (C8-M1); severity is limited because regulator IDs are typically public (FINCEN, FCA, OSFI). |
| Concurrency | **A** | `threading.Lock` used correctly; Lua atomicity documented. No observed races. |

---

## 3. Strengths worth preserving

### S1. `canonical_payload()` via `dataclasses.fields()` introspection (license_token.py:103–121)

```python
_CANONICAL_EXCLUDE: ClassVar[frozenset] = frozenset({"hmac_signature"})

def canonical_payload(self) -> bytes:
    payload = {}
    for f in dataclasses.fields(self):
        if f.name in self._CANONICAL_EXCLUDE:
            continue
        value = getattr(self, f.name)
        if isinstance(value, list):
            value = sorted(value)
        payload[f.name] = value
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

Eliminates the "added a field, forgot to sign it" class bug. Adding `schema_version`, `deployment_phase`, `sub_licensee_bics` et al. automatically includes them in the HMAC. `_CANONICAL_EXCLUDE` as a `ClassVar[frozenset]` makes the exclusion explicit and immutable. The accompanying test (`test_license_token_canonical.py:test_all_fields_in_canonical_payload`) iterates `dataclasses.fields` and asserts every non-excluded field appears in the serialised payload — a compile-time-ish guarantee.

### S2. `_AML_CAP_UNSET` sentinel (license_token.py:44–45, boot_validator.py:87–97)

Three-layer defence for EPG-16/17:
1. `LicenseToken.aml_dollar_cap_usd` defaults to `-1`, not `0` ("0 = unlimited" is valid; `-1 = never set" is rejected).
2. `LicenseToken.from_dict` raises `KeyError` if `aml_dollar_cap_usd` is missing — no silent default.
3. `LicenseBootValidator` explicitly checks `token.aml_dollar_cap_usd == _AML_CAP_UNSET` and engages the kill switch with reason `aml_cap_not_configured`.

A missing cap on a BPI provisioning token refuses to start the binary, not "starts with $1M default" — the exact failure mode the C6 M2 finding called out in the C6 review.

### S3. Redis Lua atomic record (query_metering.py:187–217)

Budget check, counter increment, entry append, and TTL refresh all execute in one server round-trip. No TOCTOU window — two concurrent callers cannot both pass a "count + 1 ≤ max_queries" check and then both increment.

### S4. Mode mutex and empty-key guards (query_metering.py:327–345)

```python
if redis_client is not None and single_replica:
    raise ValueError("Pass exactly one of single_replica=True or redis_client...")
if redis_client is None and not single_replica:
    raise ValueError("RegulatoryQueryMetering uses in-memory state...")
if not metering_key:
    raise ValueError("metering_key must be non-empty bytes...")
```

Fails at construction, not at first use. Forces the caller to acknowledge the
single-replica constraint (ticket B3-04) rather than silently running in a broken
configuration.

### S5. Processor take-rate bounds and BIC validation (boot_validator.py:109–129)

- BIC regex: `^[A-Z0-9]{8}([A-Z0-9]{3})?$` — hard-gate before the context is built.
- Take-rate range check: `PROCESSOR_TAKE_RATE_MIN_PCT ≤ take_rate ≤ PROCESSOR_TAKE_RATE_MAX_PCT` — prevents a rogue processor token from claiming 99% platform take.

Both failures engage the kill switch with a specific reason (`processor_invalid_bic`, `processor_take_rate_out_of_bounds`), enabling the SRE to diagnose from audit logs alone.

---

## 4. Findings

| ID | Severity | Axis | Summary | Disposition |
|----|----------|------|---------|-------------|
| C8-H1 | HIGH | Crypto hygiene | `RegulatorSubscriptionToken.canonical_payload()` is hand-written | **FIX INLINE** |
| C8-H2 | HIGH | Authz | `RevenueMetering` does not enforce `tenant_id` authorization | **DOCUMENT** (architectural) |
| C8-M1 | MED | Privacy | `regulator_id` fully logged on HMAC mismatch | **FIX INLINE** |
| C8-M2 | MED | Schema | `schema_version` present but not enforced | **DOCUMENT** |
| C8-M3 | MED | Input validation | `sub_licensee_bics` not deduplicated | **DOCUMENT** |
| C8-L1 | LOW | DX | `from_dict` `KeyError` does not name the missing key | **DOCUMENT** |
| C8-L2 | LOW | Schema | `deployment_phase`/`licensee_type` silently default when missing | **DOCUMENT** |
| C8-I1 | INFO | Docs | Key rotation comment (license_token.py:15) is aspirational | **DOCUMENT** |
| C8-I2 | INFO | Structure | `_VALID_PHASES` duplicates `deployment_phase.py` enum | **DOCUMENT** (accepted trade-off) |
| C8-I3 | INFO | Style | `LicenseToken` is not frozen dataclass | **DOCUMENT** |

### C8-H1 — HIGH — Hand-written regulator canonical payload

**File**: `lip/c8_license_manager/regulator_subscription.py:54–69`

```python
def canonical_payload(self) -> bytes:
    payload = {
        "regulator_id": self.regulator_id,
        "regulator_name": self.regulator_name,
        "subscription_tier": self.subscription_tier,
        ...
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

Adding a new field to `RegulatorSubscriptionToken` (e.g., `rate_limit_tier`, `mfa_required`) and forgetting to update this dict would silently omit the field from the HMAC. A token-bearer could then alter the new field without invalidating the signature — exactly the bug class that B3-02 fixed on `LicenseToken`.

**Fix**: Migrate to the `dataclasses.fields()` pattern, preserving the existing wire format (datetime → UTC ISO string, tuple → sorted list, `None` preserved). Byte-identical payload output means existing signed tokens continue to verify.

**Scope**: one file, ~20 lines. **Inline.**

### C8-H2 — HIGH — RevenueMetering has no per-tenant authz

**File**: `lip/c8_license_manager/revenue_metering.py:68–93`

`record_transaction(tenant_id, ...)` and `compute_quarterly_summary(tenant_id, ...)` accept any string. If a future processor UI or sub-licensee API ever exposes these methods, the handler **must** enforce `tenant_id == authenticated_tenant_id` at the API layer. The module itself has no way to know which caller is authorized for which tenant.

**Today's exposure**: The only caller is `lip/api/app.py` at the settlement-bridge level, invoked from internal C3 repayment callbacks with a tenant_id injected from `ProcessorLicenseeContext`. No API router hands a caller-supplied `tenant_id` into this module. So the gap is *architectural*, not currently exploitable.

**Disposition**: Document the enforcement contract in the module docstring so a future API author sees the invariant. Actual router-layer enforcement belongs in the P3/MIPLO review, not in C8. **Not fixing inline.**

### C8-M1 — MEDIUM — Regulator ID full-logged on mismatch

**File**: `lip/c8_license_manager/regulator_subscription.py:156, 160`

```python
logger.error("Regulator token HMAC mismatch for regulator_id=%s", token.regulator_id)
logger.error("Regulator token inactive for regulator_id=%s", token.regulator_id)
```

`LicenseToken.verify_token` (license_token.py:265–268) truncates: `licensee_id[:8] + "…"`. The regulator path is inconsistent. Severity is limited because regulator identifiers are typically public (FINCEN, FCA, OSFI, BIS), but the pattern should match across the two token types to avoid drift.

**Fix**: Truncate to first 8 chars + ellipsis, matching the LicenseToken pattern.

**Scope**: two log lines. **Inline.**

### C8-M2 — MEDIUM — schema_version present but not enforced

**File**: `lip/c8_license_manager/license_token.py:78`, `from_dict`:145

```python
schema_version: int = 1  # B3-02/B3-05: bump on every field add
...
schema_version=int(data.get("schema_version", 1)),
```

`from_dict` accepts any int. No code gates compatibility on `schema_version`. If BPI ever issues a v2 token with breaking field semantics (e.g., `aml_dollar_cap_usd` changes units from cents to dollars), a v1-aware binary will deserialize it and misinterpret the value.

**Current state**: there is only v1. This is a schema-evolution landmine, not an active bug.

**Recommendation**: Add `if schema_version > MAX_SUPPORTED_VERSION: raise ValueError` in `from_dict`, and bump `MAX_SUPPORTED_VERSION` explicitly when adding v2 support. Not inline — schema-evolution policy is a design decision for REX + CIPHER jointly.

### C8-M3 — MEDIUM — `sub_licensee_bics` not deduplicated

**File**: `lip/c8_license_manager/boot_validator.py:109–117`

A processor token with `sub_licensee_bics = ["DEUTDEFFXXX", "DEUTDEFFXXX"]` passes validation. Downstream usage in `app.py` and the MIPLO gateway treats the list as a membership test (iteration / `bic in context.sub_licensee_bics`), so duplicates are harmless today. But any future counter-based use (billing per-BIC, concurrency cap per-BIC) would double-count.

**Recommendation**: `len(set(token.sub_licensee_bics)) != len(token.sub_licensee_bics)` check, kill-switch reason `processor_duplicate_bic`. Trivial fix; defer to the next C8 change that has reason to touch this file.

### C8-L1 — LOW — `from_dict` errors lack key name

**File**: `lip/c8_license_manager/license_token.py:146–151`

`data["licensee_id"]` / `data["aml_dollar_cap_usd"]` raise `KeyError` without naming which key was missing. `boot_validator.py:201` catches it as `license_parse_error` and engages the kill switch — the system fails closed, but the SRE has no hint on which field is missing. Wrap the key reads in a loop or explicit per-field check that names the offender.

### C8-L2 — LOW — `deployment_phase` / `licensee_type` silently default

**File**: `lip/c8_license_manager/license_token.py:134, 139`

```python
phase = data.get("deployment_phase", "LICENSOR")
licensee_type = data.get("licensee_type", "BANK")
```

A malformed processor token missing `licensee_type` becomes a bank token — its `sub_licensee_bics` field will populate (processor semantics) but the runtime code path gates on `licensee_type == "PROCESSOR"` and routes as a bank. Downstream processor-specific logic (revenue metering, sub-licensee BIC gate) is simply skipped.

Not exploitable today. But the silent type-coercion is a schema ambiguity worth a future `required=True` change on these fields.

### C8-I1 — INFO — Aspirational key-rotation comment

`license_token.py:15`: *"Key rotation: aligned with SALT_ROTATION_DAYS (365-day cycle)."* No code references this constant; rotation is an operational practice, not code-enforced. Either enforce (refuse tokens signed with a key > 365 days old — requires `key_id` in the signed payload), or reword to clarify it's SRE guidance.

### C8-I2 — INFO — Duplicated `_VALID_PHASES`

`license_token.py:49`: `frozenset({"LICENSOR", "HYBRID", "FULL_MLO"})` duplicates the `DeploymentPhase` enum in `deployment_phase.py`. Rationale is documented: circular-import avoidance. Accepted trade-off; the `test_c8_license.py` suite asserts the two sets match.

### C8-I3 — INFO — `LicenseToken` not frozen

`LicenseToken` is a regular dataclass; `RegulatorSubscriptionToken` is `@dataclass(frozen=True)`. Mutation after signing would invalidate the HMAC (fail-safe), so this is not a security gap — but freezing `LicenseToken` would make the intent clearer.

---

## 5. Trigger-based escalations

- **Trigger #3 (ToS / third-party licensing)** — **N/A.** C8 *is* the licensing logic; it does not consume external licensed services.
- **Trigger #4 (secrets / typology patterns)** — **N/A.** All HMAC keys are env-sourced (`LIP_LICENSE_KEY_HEX`, `LIP_API_HMAC_KEY`, `LIP_REGULATOR_SUBSCRIPTION_KEY_HEX`). No typology patterns committed. `gitleaks` scan (Day 9.3) showed no C8 findings.

---

## 6. Fix policy disposition

| Finding | Policy band | Action |
|---------|-------------|--------|
| C8-H1 | HIGH, < 30 lines, 1 file | Fix inline |
| C8-H2 | HIGH, architectural (router-layer) | Document; future API review |
| C8-M1 | MEDIUM, 2 lines, 1 file | Fix inline |
| C8-M2 | MEDIUM, schema-evolution design decision | Document |
| C8-M3 | MEDIUM, trivial but no active bug | Document |
| C8-L1/L2 | LOW | Document |
| C8-I1/2/3 | INFO | Document |

**Inline fixes applied this commit**: C8-H1, C8-M1.

---

## 7. Post-review verification

- `ruff check lip/` — clean
- `pytest lip/tests/test_c8_license.py lip/tests/test_c8_processor.py lip/tests/test_license_token_canonical.py lip/tests/test_p10_regulator_subscription.py lip/tests/test_p10_security_pentest.py lip/tests/test_query_metering_redis_backend.py` — all pass
- Full non-slow suite — all pass

---

## 8. Next actions (tracked outside this review)

1. **C8-H2 follow-up**: When the P3 processor UI ships, confirm the API router
   layer enforces `tenant_id == authenticated_tenant_id` before calling
   `RevenueMetering.compute_quarterly_summary`. Capture in P3 review sprint.
2. **C8-M2 follow-up**: Joint REX + CIPHER decision on `schema_version` enforcement
   policy before any v2 token rollout.
3. **C8-M3 follow-up**: Add `sub_licensee_bics` dedup check in the next C8 change
   that has reason to touch `boot_validator.py`.
