# `lip/c6_aml_velocity/` — AML / Velocity / Sanctions Gate

> **The compliance gate.** Every event that passes C1 (τ\* gate) and C4 (dispute check) lands at C6 for sanctions screening, velocity limit checks, and anomaly flagging. CIPHER is the final authority on everything in this component — it is the platform's front line against FATF, OFAC, and AMLD6 violations.

**Source:** `lip/c6_aml_velocity/` (Python) + `lip/c6_aml_velocity/rust_velocity/` (Rust PyO3)
**Module count:** 14 Python files + 3 Rust, 3,553 LoC Python + ~800 Rust
**Test files:** 4 (`test_c6_{aml,api,rust_velocity,tenant_velocity}.py`) + `test_c6_velocity_sanctions_migration.md` + `test_structuring_detector_redis.py`
**Spec:** [`../specs/BPI_C6_Component_Spec_v1.0.md`](../specs/BPI_C6_Component_Spec_v1.0.md)
**Migration:** [`../specs/c6_velocity_sanctions_migration.md`](../specs/c6_velocity_sanctions_migration.md)

---

## Purpose

C6 performs three **hard-block** checks in parallel with C2:

1. **Sanctions screening** — Jaccard similarity match of counterparty name against OFAC + EU + UN + UK consolidated lists
2. **Velocity limits** — per-entity 24h rolling windows of dollar volume + transaction count, enforced against C8 license-token caps (EPG-16 / EPG-17)
3. **Anomaly detection** — Isolation Forest signal on the normalized feature vector; EU AI Act Art.14 routes anomalies to `PENDING_HUMAN_REVIEW` (EPG-18)

Plus one **soft-flag** check:

4. **Structuring detection** — FATF R.21 cross-tenant structuring; CIPHER review flag on the AMLResult, does not block transactions (the hard block is volume-based via velocity)

Every check can hard-block. `AMLResult.passed = True` requires all three hard checks to pass.

---

## Architecture

```
           NormalizedEvent (+entity_id, beneficiary_id)
                       │
                       ▼
    ┌──────────────────────────────────────────┐
    │  AMLChecker.check() — aml_checker.py     │
    │                                          │
    │  ┌─────────────────────────────────────┐ │
    │  │ 1. SanctionsScreener                │ │
    │  │    sanctions.py                     │ │
    │  │    - Resolves BIC → legal name      │ │
    │  │      via bic_name_resolver          │ │
    │  │    - Jaccard against sanctions.json │ │
    │  │    - Rust fast path when available  │ │
    │  └─────────────────────────────────────┘ │
    │                                          │
    │  ┌─────────────────────────────────────┐ │
    │  │ 2. VelocityChecker                  │ │
    │  │    velocity.py (Python)             │ │
    │  │    rust_velocity/*.rs (fast path)   │ │
    │  │    - Redis ZSET rolling windows     │ │
    │  │    - ZCARD + ZRANGEBYSCORE atomic   │ │
    │  │    - License-token caps enforced    │ │
    │  └─────────────────────────────────────┘ │
    │                                          │
    │  ┌─────────────────────────────────────┐ │
    │  │ 3. AnomalyDetector (optional)       │ │
    │  │    anomaly.py                       │ │
    │  │    - Isolation Forest               │ │
    │  │    - EPG-18: route to human review  │ │
    │  └─────────────────────────────────────┘ │
    │                                          │
    │  ┌─────────────────────────────────────┐ │
    │  │ 4. StructuringDetector              │ │
    │  │    tenant_velocity.py               │ │
    │  │    - Per-entity tenant registry     │ │
    │  │    - FATF R.21 cross-tenant flag    │ │
    │  └─────────────────────────────────────┘ │
    │                                          │
    └──────────────────────────────────────────┘
                       │
                       ▼
           AMLResult — passed, reason, velocity_result, sanctions_hits,
                       structuring_flag, requires_human_review
```

### Why Rust (`rust_velocity/`)

Pure-Python velocity counters add measurable p99 latency in multi-replica deployments because of GIL contention on the Redis client pool. The Rust extension (`lip_c6_rust_velocity`) compiled via maturin:

- Sub-ms p99 on single-BIC velocity lookups
- Bulk BIC checks parallelised via rayon
- Aho-Corasick automaton for multi-pattern sanctions name matching (~10x faster than Python regex)
- SHA-256 + HMAC primitives from the sha2 crate (no Python overhead)

The Rust extension is **required** in production — `Dockerfile.c6` and `Dockerfile.c7` both run a maturin build stage that compiles the wheel and installs it into the runtime image. If the extension is missing, Python falls back silently with CRITICAL log lines ("Rust extension not found — LATENCY WILL BE DEGRADED") — treat that as a P1 incident.

Build: `cd lip/c6_aml_velocity/rust_velocity && maturin build --release && pip install target/wheels/*.whl`

---

## Sanctions screening (`sanctions.py` + `sanctions_loader.py`)

### Data source

`lip/c6_aml_velocity/data/sanctions.json` — committed, ~48KB, curated aggregation of OFAC + UN + EU + UK consolidated lists. Updated via `.github/workflows/update-sanctions.yml` on a weekly cron.

Production: `LIP_SANCTIONS_PATH` env var points at this file inside the container (`/app/lip/c6_aml_velocity/data/sanctions.json`). Without the env var, SanctionsScreener falls back to a tiny `MOCK_SANCTIONS_ENTRIES` suitable for unit tests only — in production this would silently disable screening, so deploy_staging_self_hosted.sh sets the env var explicitly.

### Name resolution (`bic_name_resolver.py`)

Sanctions screening needs human-readable institution names, not 8-char BICs. `bic_name_resolver.py` ships a curated 40-BIC → legal-name map covering:

- North America (10): JPMorgan, BofA, Citibank, Wells Fargo, BNY Mellon, RBC, TD, BMO, Scotiabank, CIBC
- Europe (18): Deutsche, Commerzbank, BNP Paribas, SocGen, Crédit Agricole, Barclays, HSBC, Lloyds, NatWest, UBS, Credit Suisse, ING, ABN AMRO, Rabobank, UniCredit, Intesa Sanpaolo, BBVA, Santander
- Asia-Pacific (12): MUFG, SMBC, Mizuho, HSBC HK, Standard Chartered HK, DBS, OCBC, UOB, CBA, ANZ

Unknown BICs return `None`; the sanctions screener falls back to using the raw BIC string (Jaccard against names then produces 0.0 and no hit — safe but unhelpful). **Extend the map, don't add a catch-all "unknown bank" entry.**

Production replacement: licensed SWIFT BIC directory integration or an enrolled-borrower registry with legal-name fields. Tracked under the capital-partner strategy docs.

### Jaccard threshold

`sanctions.py::SANCTIONS_JACCARD_THRESHOLD = 0.82` — locked. Changing without a CIPHER+REX review is a refusal-grade error because it directly modifies the sanctions false-positive/false-negative rate. A 0.01 drop in the threshold can flip hundreds of legitimate counterparties into hit-list matches.

Empty names at inference time raise `ValueError` ("whitespace_only" or "non_alphabetic_only") — this is a belt-and-braces guard against a badly-wired resolver returning `""` instead of `None`. See `test_c6_aml.py::test_empty_name_*`.

### Bypass logger

`_bypass_logger = logging.getLogger("lip.c6_sanctions_bypass")` — dedicated logger for cases where screening was bypassed (empty name with entity_id set). This logger's emissions are a regulatory audit trail — they record every time a decision was made WITHOUT a sanctions check being run. Grep staging logs for the child logger name; if it fires at non-zero rate, investigate immediately.

---

## Velocity checking (`velocity.py`)

### Rolling window algorithm

Redis sorted set per entity, keyed on `lip:c6:velocity:<salt_ns>:<entity_hash>`. Each entry:

```
score = unix_timestamp
member = "<uuid>|<dollar_amount>|<beneficiary_hash>"
```

On `check()`:
1. `ZADD` the new transaction
2. `ZREMRANGEBYSCORE` the entries older than 24h
3. `ZCARD` for count
4. `ZRANGEBYSCORE` for the full window → sum dollar amounts, compute beneficiary concentration (top-3 concentration ratio)
5. Compare against `(aml_dollar_cap_usd, aml_count_cap)` from the C8 LicenseeContext

Both the ADD and REMOVE are atomic via Redis pipeline. TTL = 48h (twice the window) so stale keys expire without unbounded growth.

### Single-replica fallback

When Redis is unavailable, the Python path uses `collections.deque`. The Rust path uses `DashMap`. Both are process-local — velocity counters DO NOT survive pod restarts or span multi-replica deployments. The `VelocityBridge` constructor logs CRITICAL at boot if Redis is unavailable in a multi-replica deployment (which is the default in staging).

### Salt rotation (`salt_rotation.py`)

`SALT_ROTATION_DAYS = 365` with a `SALT_ROTATION_OVERLAP_DAYS = 30` grace window. During the overlap, both old-salt and new-salt hashes are checked, so in-flight UETRs don't lose their velocity history across rotation.

---

## Anomaly detection (`anomaly.py`)

Isolation Forest over the C1 feature vector + C2 tier + velocity features. Trained offline on the synthetic corpus. Per-licensee scoring threshold configurable via the C8 license token.

On anomaly:
- `AMLResult.requires_human_review = True`
- `PipelineResult.outcome = PENDING_HUMAN_REVIEW` (not DECLINED)
- Pipeline halts; the offer is queued for a human operator to approve or reject

This is the EU AI Act Art.14 "human oversight" requirement. The alternative (auto-declining anomalies) is wrong because it makes the anomaly detector effectively a binary gate, which means ARIA cannot calibrate it on a false-positive / false-negative trade-off independently of the hard-block path.

---

## Structuring detection (`tenant_velocity.py::StructuringDetector`)

**FATF R.21 cross-tenant structuring** — the same entity splitting transactions across multiple tenants to evade per-tenant velocity limits.

Two operational modes:

| Mode | Backing | State durability |
|------|---------|------------------|
| `single_replica=True` | `defaultdict(lambda: defaultdict(Decimal))` — in-process | resets on pod restart; does not span replicas |
| `redis_client=<Redis>` | Redis hash per entity (`HINCRBYFLOAT` + `HGETALL`) | shared across replicas; 7-day TTL |

Production (Redis-backed): combined volume across tenants accumulates for 7 days; when an entity appears in 2+ tenants AND combined volume exceeds the dollar cap, `AMLResult.structuring_flag = True`. This is a **soft flag** — it surfaces in the AMLResult for CIPHER review, it does not block the transaction.

The hard block for structuring is still volume-based via velocity. Structuring detection is the pattern-detection surface that lets CIPHER file SARs retrospectively.

### Single-replica warning

When built in `single_replica=True` mode, tenant_velocity.py logs WARNING at boot:

```
StructuringDetector running with single_replica=True — cross-tenant structuring detection will not work across replicas
```

In staging with Redis deployed, this warning should NEVER fire. If it does, the Redis connection is broken or the REDIS_URL env var is wrong.

---

## Cross-licensee aggregation (`cross_licensee.py`)

Phase 3 feature — aggregate velocity signals across licensees (BPI's cloud multi-tenant deployment only) for typology detection that no single licensee can do alone. Research implementation; not wired into the default runtime pipeline.

---

## License-token enforcement (EPG-16 / EPG-17)

AML caps come from the C8 LicenseeContext — not from hardcoded platform defaults:

```python
result = aml_checker.check(
    entity_id=bic,
    amount=amount,
    beneficiary_id=beneficiary_hash,
    dollar_cap_override=license_context.aml_dollar_cap_usd,   # 0 = unlimited
    count_cap_override=license_context.aml_count_cap,         # 0 = unlimited
)
```

EPG-17 rule: both caps are **explicit fields** in every license token, even when zero ("unlimited"). This prevents silent defaults. See `lip/c8_license_manager/license_token.py::LicenseToken.from_dict` which raises if the fields are absent.

---

## Operator signals

| Signal | Meaning |
|--------|---------|
| `"Redis connected: redis://lip-redis:6379/0"` | Boot log — Redis-backed mode active |
| `"VelocityChecker: Redis client set via set_redis_client()"` | Velocity counter using Redis |
| `"AMLChecker: Redis client wired into VelocityChecker"` | AMLChecker wiring complete |
| `"AMLChecker: loaded sanctions from /app/lip/c6_aml_velocity/data/sanctions.json"` | Sanctions data loaded |
| `"StructuringDetector running in Redis-backed multi-replica mode"` | Multi-replica-safe mode |
| `"StructuringDetector running with single_replica=True — …"` | WARNING — Redis unavailable |
| `"SanctionsScreener: no lists_path provided — falling back to MOCK sanctions data"` | WARNING — `LIP_SANCTIONS_PATH` unset |
| `"lip_c6_rust_velocity Rust extension not found. …"` | CRITICAL — degraded latency |

---

## Consumers

| Consumer | How it uses C6 |
|----------|---------------|
| `lip/pipeline.py::LIPPipeline.process_event` | Calls `c6_checker.check()` in parallel with C4 and C2 after τ\* gate |
| `lip/c6_aml_velocity/api.py` | Standalone HTTP surface — used in `local-core` staging profile |
| `lip/api/runtime_pipeline.py::_build_c6_checker` | Constructs AMLChecker with BIC resolver + Redis wiring |

---

## What C6 does NOT do

- **Does not see the narrative text** — C4 reads the narrative. C6 operates on the normalized fields only.
- **Does not decide fee** — C2 does.
- **Does not finalize the loan offer** — C7 does.
- **Does not report to the regulator directly** — that is P10 / DORA Art.19 reporting. C6 produces `AMLResult`; P10 consumes + anonymises.

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § step 3b
- **Spec** — [`../specs/BPI_C6_Component_Spec_v1.0.md`](../specs/BPI_C6_Component_Spec_v1.0.md)
- **Migration** — [`../specs/c6_velocity_sanctions_migration.md`](../specs/c6_velocity_sanctions_migration.md)
- **EPG-16 / EPG-17** — [`../../legal/decisions/EPG-16-18_aml_caps_human_review.md`](../../legal/decisions/EPG-16-18_aml_caps_human_review.md)
- **Sanctions audit** — [`../../legal/c6_sanctions_audit.md`](../../legal/c6_sanctions_audit.md)
- **C8 license enforcement** — [`c8_license_manager.md`](c8_license_manager.md)
