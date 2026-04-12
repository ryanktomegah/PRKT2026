# Resolution Status — 2026-04-08 Review

**Last updated**: 2026-04-11
**Status**: All 12 Critical findings RESOLVED. All Highs listed below RESOLVED. Review CLOSED.

This file supersedes the "open" framing in [INDEX.md](INDEX.md). The 2026-04-08
review identified 12 Critical and 27+ High findings. Between 2026-04-08 and
2026-04-10 a hardening sprint (B1–B13) landed fixes for every Critical and
every High flagged below. The individual batch files (`03-c8-license.md`,
`06-c5-streaming.md`, etc.) still describe the findings as they were *at the
time of review* — that history is preserved for audit. **This file is the
source of truth for current status.**

If a finding is not in this file, assume it is still open (Medium/Low/Nit
backlog — see individual batch files).

---

## How to verify a fix yourself

```bash
# For any finding, read the fix commit:
git show <commit-hash>

# Or list every B-prefixed fix:
git log --oneline --all | grep -E "B(1[0-3]|[3-9])-0[0-9]"
```

All fixes have landed on `main`. HEAD at time of closure: `81d7750`.

---

## Critical findings — ALL RESOLVED

| Review ID | Finding (one-line) | Fix Commit | Verification File |
|-----------|--------------------|------------|-------------------|
| **B3-01** | TOCTOU race in C8 DP budget enforcement | `eb93fc8` | `lip/c8_license_manager/query_metering.py:121-189` — atomic check-and-increment under single lock hold |
| **B3-02** | Hand-maintained HMAC canonical payload (privilege-escalation primitive) | `1a183fc` | `lip/c8_license_manager/license_token.py` — payload now derived from dataclass fields; schema-version tag added |
| **B6-01** | 5+ way dual-maintained BLOCK code list across Py/Rust/Go | `dd6f780` | `lip/common/block_codes.json` — single source; Python import, Rust `include_str!`, Go `go:embed` all load from it |
| **B6-02** | Exactly-once claim violated — Go consumer committed offset on error paths | `6b4c55f` | `lip/c5_streaming/go_consumer/consumer.go` — offsets committed only after successful handler return |
| **B8-01** | Differential privacy composition undercounted by 3× (1ε charged, 3 values released) | `f4bb1d5` | `lip/p10_regulatory_data/anonymizer.py:175-177` — `epsilon_per_batch = self._epsilon * 3` |
| **B8-02** | DP budget-exhausted fallback published raw un-noised data | `8d4b0c7` | `lip/p10_regulatory_data/anonymizer.py:198-206` — raises `PrivacyBudgetExhaustedError` instead of returning raw |
| **B9-01** | `INTERVENTION_FEE_RATE_BPS = 200` violated 300 bps canonical floor | `6e03d06` | `lip/p5_cascade_engine/constants.py` — restored to 300 bps; QUANT-signed |
| **B10-01** | `pickle.load()` on C1 lgbm/calibrator with no integrity check (RCE) | `7610c82` | `lip/common/secure_pickle.py` — HMAC-verified loader; C1 routed through it |
| **B10-02** | Same pickle RCE for C2 5-model PD ensemble | `7610c82` | `lip/common/secure_pickle.py` — C2 routed through it |
| **B11-01** | CLASS_B mislabelled as "compliance/AML hold" in DGEN | `a3a59d5` | `lip/dgen/iso20022_payments.py` + `statistical_validator_production.py` — label now "systemic/processing delay" |
| **B11-02** | EPG-19 codes tagged as bridgeable in DGEN — trains C1 to bridge compliance holds | `dd6f780` (B6-01 consolidation) | `lip/dgen/c1_generator.py` — now consumes shared BLOCK list; `is_bridgeable=False` enforced |
| **B13-01** | Zero regression tests for pickle-load RCE | `7610c82` | `lip/tests/test_secure_pickle.py` — guards `pickle.load` absence outside `secure_pickle.py` |
| **B13-02** | No cross-language BLOCK-code drift regression | `dd6f780` | `lip/tests/test_block_codes_consistency.py` — asserts set-equality across Py/Rust/Go |

---

## High findings — RESOLVED (selected list from INDEX)

| Review ID | Finding | Fix Commit | Notes |
|-----------|---------|------------|-------|
| **B3-03** | Default-permissive AML caps (0=unlimited) on programmatic construction | `abce143`, `254d0bc` | Opt-in `allow_insecure_default=True` required |
| **B3-04** | In-memory C8 metering store (redeploy resets, multi-replica N×) | `2c08f8c` | Requires explicit `single_replica=True` opt-in; see `query_metering.py:56-62` |
| **B3-05** | No schema version in HMAC canonical payload | `1a183fc` | Schema-version tag added |
| **B3-07** | Decimal→float round-trip on license take-rate | `0c35f0a` | Decimal-native path |
| **B3-08** | Empty-default HMAC metering key trivially forgeable | `e281ec5` | Constructor now raises on empty key |
| **B6-03** | Proprietary → ISO 20022 mapping dual-maintained (Go/Py) | `bfee1b2`, `f0f7ff2` | Consolidated into shared JSON |
| **B6-04** | gRPC insecure credentials — payment data plaintext in cluster | `70b0e4b`, `007afc2`, `b4117f2` | Default TLS |
| **B6-05** | Go consumer Kafka default PLAINTEXT vs Py SSL | `70b0e4b`, `007afc2`, `18c99ea` | Default SSL |
| **B6-06** | Go/Py `max.in.flight` divergence undocumented | `7c79d91`, `63d73a4` | Documented + aligned |
| **B7-01** | Decimal→float precision loss at Rust AML cap boundary | `0c35f0a` | Integer-cents path |
| **B7-02** | Rust velocity has no Redis backing (multi-replica N× AML budget) | `2c08f8c` | Requires `single_replica=True` opt-in |
| **B7-03** | Sanctions screening had no transliteration/phonetic matching | `d1c6d18`, `d4cb315` | Unicode transliteration + phonetic matching added |
| **B8-03** | 6th independent BLOCK code list in `telemetry_collector.py` | `dd6f780` | Absorbed into shared JSON |
| **B8-04** | Decimal→float round-trip in parametric VaR | `0c35f0a` | Decimal-native path |
| **B8-05** | Tautological privacy audit attacks (always pass by construction) | `e203712`, `73a1dc8` | Replaced with real statistical tests |
| **B9-02** | O(n²) bottom-up CVaR pass in cascade | `e2be4f9` | O(n log n) |
| **B9-03** | O(N²) greedy intervention optimizer | `e2be4f9` | Heap-based O(N log N) |
| **B10-03** | C2 OOT split collapse + Tier-3 stress train/test contamination | `10624a7`, `492868d` | Tier-3 restricted to test set; dict path fixed |
| **B10-04** | C1 OOT split silently random on missing `timestamp_unix` | `3f9e2d2`, `63c6314` | Warns; `strict_oot` flag added |
| **B10-05** | MockLLMBackend default for C4 (substring match prod footgun) | `abce143`, `254d0bc` | Opt-in required |
| **B10-06** | Prompt injection via user-controlled `narrative`/`counterparty` | `5db337c`, `e3d3f43` | Sanitised |
| **B10-07** | Zero-byte default salt — trivially reversible borrower-ID hashes | `abce143`, `254d0bc` | Opt-in required |
| **B10-08** | `assert` for 300 bps fee floor (stripped under `python -O`) | `6ce34a6` | Explicit `if ... raise` |
| **B12-01** | No upper version bounds on any package | `e173820`, `26251d7` | Bounds added |
| **B12-02** | Triton base image pinned to 2024-01 with CVEs since | `34c0bbb`, `4f48f76` | Updated to 25.04-py3 |

## Remaining Medium/Low/Nit

Individual batch files (`03-c8-license.md` through `13-tests.md`) list many
Medium, Low, and Nit findings beyond those tabled above. Most of those were
also addressed in the batches named by the grep-able commits:

- `63b34fc` — B11-03..14 (DGEN: seeded RNG, AML env-only, BIC pool, FEE_FLOOR)
- `48191eb` — B3-06..13 + B10-11 (C8 immutable dataclass, C9 pickle security, misc)
- `91e3dcc` — B7-04..13 (C6 AML encapsulation, integer cents, predict-before-fit)
- `6e4b1ae` — B6-07..14 + B10-16 (C4/C5 Kafka offset mgmt, fail-closed parse, gRPC upgrade)
- `033fedf` — B5-02..17 (C3 state machine, corridor buffer thread safety, Rust FFI type safety)
- `d6b5730` — B4-01..16 (C7 AML fail-closed, UETR required, thread safety, atomic state)
- `db3c908` — B8-06..17 (P10/risk: Decimal positions, Laplace bias, random seed)
- `f971874` — B12-03..07 (Infra: secrets CI guard, Redis port docs, Redis persistence)

Assume any Medium/Low finding whose sprint ID appears in one of the above
commits has been addressed. A small backlog of triage items (nits, docs,
cosmetics) is still open and lives in the individual batch files.

---

## What is NOT closed by the B1–B13 sprint

The deferred batches from the original review are still partially outstanding:

- **Batch 11 (DGEN)** — was re-run and fixes landed (`63b34fc`, `23cab89`, `a3a59d5`, `dd6f780`). Closed.
- **Batch 13 (Tests)** — regression tests for pickle (B13-01) and BLOCK code consistency (B13-02) landed. Full test-batch review never re-run at the scope originally planned — a broader test-audit pass (coverage gaps beyond B13-01/02) is still on the backlog.

---

## Maintenance note

This file must be updated whenever a new finding is raised in a subsequent
review and later resolved. The pattern is:

1. Raise finding in new review batch file with a Bn-nn ID.
2. Fix ships; commit message carries the ID (`fix(c8): ... (Bn-nn)`).
3. Add a row to this file: `Bn-nn | description | commit | verification file`.

Consolidation wins over per-batch-file edits because the next reviewer only
reads one page to know what's open.
