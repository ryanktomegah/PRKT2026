# C6 Velocity & Sanctions Migration — Python → Rust (Atomics via PyO3)

**Priority:** 4  
**Status:** IMPLEMENTED  
**Authors:** CIPHER (security), QUANT (financial math), ARIA (ML)  
**Date:** 2026-04-02

---

## 1. Overview

C6 comprises rolling 24-hour AML velocity counters, sanctions screening
(OFAC/EU/UN), salt rotation, and cross-licensee envelope crypto.

This spec covers the migration of **velocity counters** and **sanctions
screening** to Rust via PyO3 for sub-4ms SLA on the critical path. Salt
rotation (`salt_rotation.py`) and cross-licensee crypto (`cross_licensee.py`)
remain in Python — both are already correct and not on the latency-critical
path.

---

## 2. Architecture

```
Pipeline (pipeline.py)
    │
    ├── AMLChecker.check() — C6 gate
    │       │
    │       ├── RustSanctionsScreener.screen()   ← Rust via PyO3
    │       │       │  Aho-Corasick + Jaccard
    │       │       └── fallback: SanctionsScreener (Python)
    │       │
    │       ├── RustVelocityChecker.check_and_record()   ← Rust via PyO3
    │       │       │  DashMap + Rust atomics
    │       │       └── fallback: VelocityChecker (Python)
    │       │
    │       └── AnomalyDetector.predict()         (stays Python)
    │
    ├── SaltRotationManager              (stays Python — OpenSSL SHA-256)
    └── CrossLicenseeAggregator          (stays Python — AES-256-GCM)
```

### 2.1 Rust Crate: `lip_c6_rust_velocity`

Location: `lip/c6_aml_velocity/rust_velocity/`

| Module | Purpose |
|---|---|
| `velocity.rs` | `PyRollingVelocity` — DashMap rolling window + atomics |
| `sanctions.rs` | `PySanctionsScreener` — Aho-Corasick + Jaccard |
| `lib.rs` | PyO3 module entry point (`lip_c6_rust_velocity`) |

### 2.2 Python Bridge Modules

| File | Purpose |
|---|---|
| `velocity_bridge.py` | `RustVelocityChecker` — unified interface over Rust/Python |
| `sanctions_bridge.py` | `RustSanctionsScreener` — unified interface over Rust/Python |

---

## 3. Velocity Counter Design

### 3.1 Data Structure

```rust
DashMap<String, EntityWindow>
// key: SHA-256(entity_id + salt)
// value: Vec<VelocityRecord { timestamp_us, amount_cents, bene_hash }>
```

`DashMap` uses 16 shards by default, each protected by an `RwLock`. Concurrent
access from multiple Python threads is safe without holding the GIL.

### 3.2 Three Velocity Rules (identical to Python)

1. **Dollar cap**: rolling 24h volume + candidate ≤ cap (0 = unlimited, EPG-16)
2. **Count cap**: rolling 24h count + 1 ≤ cap (0 = unlimited, EPG-16)
3. **Beneficiary concentration**: single-beneficiary share of projected window ≤ 80%
   (only enforced when ≥ 2 prior transactions and ≥ 2 distinct beneficiaries)

### 3.3 Atomic Check-and-Record

`check_and_record()` holds the `DashMap` entry write-guard for the full check +
write cycle, eliminating the TOCTOU race that exists in the separate
`check()` + `record()` pattern (EPG-25).

### 3.4 Privacy: Entity ID Hashing

```rust
SHA-256(entity_id.as_bytes() + salt)
```

Raw entity IDs are never stored — only their hex digests. Identical to the
Python `VelocityChecker._hash_entity()` algorithm.

---

## 4. Sanctions Screening Design

### 4.1 Algorithm (compliance-identical to Python)

**Tier 1 — Aho-Corasick substring pre-filter:**

An Aho-Corasick automaton is built from all loaded entries. Any query
containing a loaded entry as a substring is identified in O(n+m). This serves
as a fast confidence-boost path (not a replacement for the Jaccard scan).

**Tier 2 — Jaccard token-overlap scan:**

All entries are scanned with `jaccard(query_tokens, entry_tokens) = |A∩B|/|A∪B|`.
Hits with `confidence ≥ threshold` (default 0.8) are returned.

This is **identical** to `SanctionsScreener._fuzzy_match()` in Python —
ensuring zero compliance regression.

### 4.2 Thread Safety

`PySanctionsScreener` uses a `parking_lot::RwLock<SanctionsScreener>`:
- `screen()` and `is_clear()` acquire **read guards** — fully concurrent.
- `load()` and `flush()` acquire a **write guard** — exclusive, brief.

### 4.3 Known Compliance Gaps

See `docs/c6_sanctions_audit.md` for the full audit.

Summary:
- ❌ No transliteration (Cyrillic, Arabic → Latin) — **Tier 1 gap, blocking for bank pilot**
- ❌ No phonetic matching — Tier 2 gap
- ⚠️ OFAC AKA records not loaded by `sanctions_loader.py` — Tier 2 gap

---

## 5. Python Bridge Fallback Contract

Both bridge modules follow the **fail-operational** fallback pattern established
by C3 (`state_machine_bridge.py`) and C7 (`kill_switch_bridge.py`):

```python
try:
    import lip_c6_rust_velocity as _rust
    _RUST_AVAILABLE = True
except ImportError:
    _rust = None
    _RUST_AVAILABLE = False
    warnings.warn("...", UserWarning)
```

The fallback is **loud** (UserWarning on startup) but **not fail-closed** —
velocity and sanctions checks continue with the Python implementation.

Forced Python mode for testing: `LIP_C6_FORCE_PYTHON=1`

---

## 6. Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `c6_velocity_check_latency_seconds` | Histogram | `check()` call latency |
| `c6_velocity_backend` | Info | `"rust"` or `"python"` |
| `c6_sanctions_screen_latency_seconds` | Histogram | `screen()` call latency |
| `c6_sanctions_hits_total` | Counter | Total sanctions hits |
| `c6_sanctions_misses_total` | Counter | Total clean screens |
| `c6_sanctions_backend` | Info | `"rust"` or `"python"` |

Rust-side atomics are also exposed via `get_rust_metrics()` on both bridge
classes, returning dicts compatible with Prometheus Gauge pushes.

---

## 7. Build Instructions

```bash
# Build Rust wheel
cd lip/c6_aml_velocity/rust_velocity
maturin build --release
pip install target/wheels/*.whl

# Verify
python -c "import lip_c6_rust_velocity; print(lip_c6_rust_velocity.health_check())"
# → {'ok': True, 'version': '0.1.0', 'backend': 'lip_c6_rust_velocity'}

# Run Rust unit tests (21 tests)
cargo test

# Run Python integration tests (39 tests)
cd <repo_root>
PYTHONPATH=. python -m pytest lip/tests/test_c6_rust_velocity.py -v
```

---

## 8. Latency SLO

Target: ≤ 4ms p99 for the combined sanctions + velocity check on the critical path.

| Operation | Target | Backend |
|---|---|---|
| `screen()` per entity | ≤ 0.5ms p99 | Rust (Aho-Corasick + Jaccard) |
| `check_and_record()` per entity | ≤ 0.5ms p99 | Rust (DashMap shard lock) |
| Full C6 gate (sanctions + velocity + anomaly) | ≤ 4ms p99 | Mixed |

The overall LIP pipeline SLO (≤ 94ms p99) is not affected by this migration.

---

## 9. Definition of Done

- [x] Sanctions logic audit + Python test vector suite committed (`docs/c6_sanctions_audit.md`)
- [x] Rust crate implemented (`lip_c6_rust_velocity`) with 21 unit tests, all passing
- [x] Python bridge modules (`velocity_bridge.py`, `sanctions_bridge.py`) with fallback
- [x] Python integration tests (39 tests), Rust/Python parity verified
- [x] Prometheus metrics wired in both bridge modules
- [x] Fallback to pure Python when `LIP_C6_FORCE_PYTHON=1` or wheel missing
- [x] CI job `rust-build-c6` added — builds wheel, runs Rust + Python tests
- [x] `ruff check lip/` — zero errors
- [x] `.gitignore` updated to exclude `rust_velocity/target/` and `Cargo.lock`
- [ ] CIPHER sign-off — audit doc reviewed, compliance gaps documented
- [ ] QUANT sign-off — no fee math in scope; velocity caps EPG-16 verified unchanged
