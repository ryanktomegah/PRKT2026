# C2 PD Model + Fee Math — Code Quality & Correctness Review

**Sprint**: Pre-Lawyer Review (Day 12, Task 12.1)
**Date**: 2026-04-19
**Scope**: `lip/c2_pd_model/` (baseline, merton_kmv, fee, lgd, tier_assignment, features, inference, model, training, synthetic_data, README.md) + `lip/common/constants.py` fee constants
**Reviewers**: QUANT (fee math, final authority), ARIA (ML scaffolding)
**Branch**: `codex/pre-lawyer-review`
**Aggregate grade**: **B**

---

## 1. Executive summary

C2 prices bridge-loan credit risk: route a borrower to an appropriate tier model, derive PD, multiply by corridor LGD and exposure to get expected-loss bps, then clamp to the canonical 300 bps annualised fee floor. The **fee arithmetic is clean**: `compute_fee_bps_from_el` (fee.py:33–87) is fully `Decimal`, the floor is applied at line 85, and the cascade-adjustment pathway (fee.py:251–342) re-validates the warehouse-eligibility floor (800 bps) for SPV-funded loans. The Merton/KMV solver (merton_kmv.py) cites Crosbie & Bohn 2003 and correctly derives `DD = d2`.

The grade is held down by **documentation drift** and **one methodology mismatch**:

- **C2-H1** (HIGH): `README.md:21` referenced two files that do not exist in the tree — `damodaran.py` and `altman_z_prime.py`. The table also named classes (`DamodaranModel`, `AltmanZPrimeModel`) that do not exist. Anyone reading the module description would form an incorrect mental model. **Fixed inline** — README now lists what actually exists (`PDModel`, `MertonKMVSolver`, `altman_z_score`, `merton_pd`, `altman_pd`).
- **C2-H2** (HIGH): the module's stated Tier-3 use case is **thin-file private** borrowers, but `altman_z_score` in `baseline.py:95–148` implements the original **1968 public-firm Z** — it requires `market_cap` in X₄ and coefficients (1.2/1.4/3.3/0.6/1.0) calibrated on public manufacturing firms. The correct Tier-3 variant is Altman **Z′ (1983)** with book equity substituted for market cap and recalibrated coefficients (0.717/0.847/3.107/0.420/0.998). This is a **methodology gap requiring ARIA + QUANT joint sign-off** before production use; document-only for this sprint.
- **C2-H3** (HIGH, follow-on from C6-H1): `tier_assignment.hash_borrower_id` uses raw `SHA-256(salt || tax_id)` — the same length-extension vulnerability class as `c6_aml_velocity`. **Deferred with the C6-H1 remediation** (both must migrate to HMAC-SHA256 in the same commit so the UETR/tax-ID hash spaces stay aligned).

Inline fixes applied this sprint: C2-H1 (README), C2-M1 (constants typing), C2-M3 (dead param).

---

## 2. Scoring

| Axis | Grade | Rationale |
|------|-------|-----------|
| Fee arithmetic correctness | **A−** | `compute_fee_bps_from_el` is fully Decimal; platform 300 bps floor clamped at fee.py:85; warehouse 800 bps re-verified in cascade path (fee.py:327). Minor: `compute_tiered_fee_floor` (fee.py:191) returns `FEE_FLOOR_BPS` regardless of loan amount — dead code with a misleading name (C2-L2). |
| Input validation | **A−** | Cascade path validates `base_pd ∈ [0,1]` (fee.py:304); EL-to-fee path rejects non-positive EAD and out-of-range PD. Gap: `lgd.lgd_for_corridor` accepts `collateral_value_pct` without bounds check (negative or >100% would silently distort LGD). |
| Typing discipline | **B+** | `FEE_FLOOR_BPS: Final[Decimal]` is canonical. Missed in Day 10: `WAREHOUSE_ELIGIBILITY_FLOOR_BPS = 800` was a bare `int` (C2-M1 — fixed this sprint). `PLATFORM_ROYALTY_RATE` is `Final[Decimal]`. |
| Model methodology | **B−** | Merton/KMV solver cites Crosbie & Bohn 2003 correctly; DD = d2 is market standard. Altman implementation is 1968 public-firm Z, not Z′ — misaligned with stated thin-file private-borrower Tier-3 use case (C2-H2). LGD table (`lgd.py:18–26`) has no source citation — Basel III RIRB? Moody's RMS? JCB default study? (C2-M2). |
| Documentation ↔ code alignment | **C+** | README.md listed two phantom files and three phantom classes (C2-H1 — fixed). `_INFERENCE_SALT` path is well-documented. Missing: data card reference, calibration-source audit trail for LGD table, Altman Z / Z′ decision record. |
| Crypto hygiene (borrower ID hashing) | **C** | Raw SHA-256(salt || tax_id) — length-extension exposure (C2-H3). Salt rotation / salt-source configuration is clean (`configure_inference_salt` rejects <16-byte salts). The hash primitive itself needs the same HMAC migration scheduled for C6-H1. |
| Dead code / hygiene | **B+** | `barrier_penalty` unused parameter on `MertonKMVSolver.__init__` (C2-M3 — fixed). `compute_tiered_fee_floor` returns constant (C2-L2). Merton solver's `-99.0` sentinel on invalid inputs is ergonomic debt but not a correctness issue (C2-L1). |

---

## 3. Strengths worth preserving

### S1. Fee floor enforcement at every external output path

Platform floor (300 bps) is applied in `compute_fee_bps_from_el` at fee.py:85:

```python
fee_bps = max(fee_bps, FEE_FLOOR_BPS)
```

Cascade path validates warehouse floor (800 bps) at fee.py:327:

```python
if cascade_adjusted_fee_bps < WAREHOUSE_ELIGIBILITY_FLOOR_BPS:
    raise ValueError(...)
```

Every external callsite goes through one of these two functions — there is no bypass. This is the QUANT-required floor, and the code matches the spec.

### S2. Merton/KMV solver is correctly attributed and mathematically sound

`merton_kmv.py:10–36` cites the Crosbie & Bohn 2003 Moody's KMV formulation. The iterative solver (lines 71–114) uses:

- Initial guess `V_A ≈ V_E + D`, `σ_A ≈ σ_E · (V_E / V_A)` — standard starting point
- Newton-Raphson step on `V_A` with `f'(V_A) = N(d₁)` — textbook
- Fixed-point update for `σ_A` — the KMV canonical form

`DD = d₂` (line 118) is the market-standard distance-to-default — consistent with how `pd = N(−DD)` is computed downstream.

### S3. Fully-Decimal LGD + fee pipeline

`lgd.py` uses `Decimal` throughout — no float drift enters the fee computation. `compute_fee_bps_from_el` takes and returns `Decimal`. This prevents the entire class of "floor violated by 1 bps due to float rounding" failures.

### S4. Cascade PD adjustment bounds `base_pd ∈ [0,1]` before use

`fee.py:304` explicitly validates `base_pd` is in-range before applying the cascade discount. Out-of-range inputs raise `ValueError` rather than silently producing nonsensical `(1 − discount) · pd` values outside `[0,1]`.

---

## 4. Findings

### C2-H1 — HIGH — README.md references non-existent files and classes [FIXED INLINE]

**Evidence**: `README.md:19–22` (pre-fix):

| Class | File |
|-------|------|
| `MertonKMVModel` | `merton_kmv.py` |
| `DamodaranModel` | `damodaran.py` |
| `AltmanZPrimeModel` | `altman_z_prime.py` |

Actual tree (`ls lip/c2_pd_model/`): `baseline.py features.py fee.py inference.py lgd.py merton_kmv.py model.py synthetic_data.py tier_assignment.py training.py`. No `damodaran.py`. No `altman_z_prime.py`. No class named `MertonKMVModel` — the class is `MertonKMVSolver`. No `DamodaranModel`. No `AltmanZPrimeModel`.

**Impact**: Anyone reading the module description would believe there is a routing layer selecting between three distinct tier models; there isn't. The production path is a single trained `PDModel` ensemble in `model.py`. Reviewers, patent counsel, or pilot bank due-diligence teams would form an incorrect mental model of what exists.

**Fix** (applied inline): README rewritten to list actual files/functions — `PDModel`, `MertonKMVSolver`, `altman_z_score`, `altman_pd`, `merton_pd`, `assign_tier`, `UnifiedFeatureEngineer`, `compute_fee_bps_from_el`, `compute_cascade_adjusted_pd`, `lgd_for_corridor`. Methodology caveat added pointing at C2-H2.

**Commit**: this sprint.

---

### C2-H2 — HIGH — Altman Z implementation is 1968 public-firm, but stated use case is thin-file private borrowers [DEFERRED — ARIA + QUANT joint sign-off]

**Evidence**: `baseline.py:95–148` implements the original Altman (1968) Z-score. The docstring is explicit: *"the original Altman (1968) Z-score for public manufacturing firms"*. Formula:

```
Z = 1.2·X₁ + 1.4·X₂ + 3.3·X₃ + 0.6·X₄ + 1.0·X₅
where X₄ = market_cap / total_liabilities
```

README (pre-fix) claimed this served Tier-3 *"Thin-file Z' score for minimal-data cases"*. Tier-3 is defined (in `tier_assignment.py`) as borrowers without audited financials or market-traded equity — for these, `market_cap` is unavailable.

**Correct variant**: Altman Z′ (1983) uses book equity in X₄ and recalibrated coefficients:
```
Z' = 0.717·X₁ + 0.847·X₂ + 3.107·X₃ + 0.420·X₄ + 0.998·X₅
where X₄ = book equity / total_liabilities
```
For emerging-market / non-manufacturing firms, Altman Z″ (1995) drops X₅ and uses different coefficients again.

**Impact**:
1. Calling the 1968 Z on a thin-file borrower silently produces a near-zero X₄ term (missing market_cap treated as zero), systematically biasing Z downward — predicting distress where none exists. Fee bps biased upward.
2. Patent counsel reviewing claim language around "tiered PD model selection by data availability" needs this to be true before filing — a claim that depends on a Z′-for-private-firms differentiation is not supported by the current code.
3. SR 11-7 model validation record for C2 cannot truthfully cite the 1968 Z as appropriate for the stated use case.

**Fix path** (not applied this sprint — requires ARIA + QUANT):
1. Rename `altman_z_score` → `altman_z_1968`.
2. Add `altman_z_prime_1983` using book equity in X₄ with coefficients (0.717, 0.847, 3.107, 0.420, 0.998).
3. Update `PDInferenceEngine` / `features.UnifiedFeatureEngineer` to select by tier — 1968 Z for Tier-1 (listed), Z′ for Tier-2/3 (private).
4. Retrain `PDModel` with the correct features; update data card.
5. Decision record in `docs/legal/decisions/EPG-2?-altman-z-variant.md`.

**Owner**: ARIA (model spec) + QUANT (fee calibration). **Blocker for**: SR 11-7 validation, patent filing, any production Tier-3 inference.

---

### C2-H3 — HIGH — `hash_borrower_id` uses raw SHA-256 (length-extension class) [DEFERRED — with C6-H1 migration]

**Evidence**: `tier_assignment.py:108–132` — `hash_borrower_id(tax_id, salt)` computes `sha256(salt + tax_id.encode()).hexdigest()`. Inference layer mirrors this in `inference.py` via `_INFERENCE_SALT`.

**Impact**: Same vulnerability class as C6-H1 (`salt_rotation.hash_with_current`). Raw `sha256(salt || data)` is susceptible to length-extension — an attacker who knows one `(tax_id, hash)` pair can compute `hash(tax_id || padding || suffix)` without knowing the salt. Practically: if an attacker can request hashes through any exposed API surface (audit query, regulator portal), they can generate valid-looking hashes for forged borrower IDs.

**Fix**: migrate to `hmac.new(salt, tax_id.encode(), sha256).hexdigest()` in the **same commit** as the C6-H1 migration so the hash spaces stay aligned (a UETR hashed under the old scheme and a tax_id hashed under the new scheme would never cross-reference correctly if split across commits).

**Owner**: CIPHER (bundle with C6-H1). **Scheduled**: Sprint Week-3 task per pre-lawyer-review plan.

---

### C2-M1 — MEDIUM — `WAREHOUSE_ELIGIBILITY_FLOOR_BPS` was not `Final[Decimal]` [FIXED INLINE]

**Evidence** (pre-fix, `lip/common/constants.py:26`):
```python
WAREHOUSE_ELIGIBILITY_FLOOR_BPS = 800    # minimum bps for SPV funding
```

All other fee constants are `Final[Decimal]` (line 19: `FEE_FLOOR_BPS`, line 20: `FEE_FLOOR_PER_7DAY_CYCLE`). This bare `int` required downstream coercion (`Decimal(str(WAREHOUSE_ELIGIBILITY_FLOOR_BPS))`) at `fee.py:327` and `constants.py:377`. Missed during Day 10 typing discipline pass.

**Fix** (applied inline):
```python
WAREHOUSE_ELIGIBILITY_FLOOR_BPS: Final[Decimal] = Decimal("800")
```
Redundant `Decimal(str(...))` wrapper at `fee.py:327` removed. Callers at `constants.py:377` and `test_c2_fee_formula.py:606` still compile — `Decimal(str(Decimal("800")))` is idempotent. `test_fee_floor_two_tier.py:20–24` passes because `Decimal("800") >= Decimal(...)` comparisons work identically.

---

### C2-M2 — MEDIUM — `LGD_BY_JURISDICTION` has no source citation [DOCUMENT]

**Evidence**: `lip/c2_pd_model/lgd.py:18–26` defines a per-jurisdiction LGD table:
```python
LGD_BY_JURISDICTION: Dict[str, Decimal] = {
    "US": Decimal("0.45"),
    "GB": Decimal("0.40"),
    "DE": Decimal("0.35"),
    ...
}
```
No inline citation, no docstring reference, no `docs/models/` attribution. Values "look right" (Basel III RIRB typical banded LGD is 45%; UK/DE trend lower historically) but SR 11-7 §4.2 requires documented calibration source.

**Fix path** (not applied — data card work, not code):
1. Identify the source used during calibration (Basel III RIRB floors? Moody's Ultimate Recovery Database? JCB default study?).
2. Add citation to `lip/c2_pd_model/lgd.py` docstring.
3. Record in `docs/models/c2-model-card.md` and `docs/models/c2-training-data-card.md`.

**Owner**: ARIA + REX. **Scheduled**: Week-3 data card review.

---

### C2-M3 — MEDIUM — `barrier_penalty` is a dead parameter on `MertonKMVSolver.__init__` [FIXED INLINE]

**Evidence** (pre-fix, `merton_kmv.py:39–47`):
```python
def __init__(
    self,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    barrier_penalty: float = 1e10
) -> None:
    self.max_iter = max_iter
    self.tolerance = tolerance
    self.barrier_penalty = barrier_penalty
```

`self.barrier_penalty` is assigned but never read. `grep -rn barrier_penalty lip/` confirms no reference outside the dead assignment.

**Impact**: Test authors or future contributors might pass a non-default `barrier_penalty=...` expecting behavioural change. The comment trail suggests this was intended for a downside-barrier variant that was never implemented.

**Fix** (applied inline): parameter and attribute removed.

---

### C2-L1 — LOW — Merton solver `-99.0` sentinel on invalid input [DOCUMENT]

**Evidence**: `merton_kmv.py:62–63`:
```python
if equity_value <= 0 or debt <= 0 or equity_vol <= 0:
    return 0.0, 0.0, -99.0
```
Returning a magic number for DD is ergonomic debt — a typed result (e.g., `Optional[Tuple[float, float, float]]` returning `None`, or a dedicated `InvalidInputResult` sentinel dataclass) would force callers to handle the error case at the type level. Not a correctness issue — downstream `pd = N(−DD)` on `DD = −99.0` yields `pd ≈ 1.0` which is the conservative answer — but a reader must know `-99.0` is the magic code.

**Recommendation**: leave as-is for this sprint; include in a typed-return-refactor pass before ARIA retraining. Tracking only.

---

### C2-L2 — LOW — `compute_tiered_fee_floor` is dead code [DOCUMENT]

**Evidence**: `fee.py:191–209`:
```python
def compute_tiered_fee_floor(loan_amount: Decimal) -> Decimal:
    """Compute the applicable fee floor based on loan amount tier."""
    return FEE_FLOOR_BPS
```
The name implies tiered behaviour (small loans → higher floor, large loans → lower floor), but the function returns the constant `FEE_FLOOR_BPS` regardless of input. `grep compute_tiered_fee_floor lip/` shows no production caller. Leftover scaffolding.

**Recommendation**: delete in a cleanup pass once call-site audit confirms no external consumer relies on the export. Tracking only; not urgent.

---

### C2-I1 — INFO — `FEE_FLOOR_PER_7DAY_CYCLE` derivation documented in comment but not in test

**Observation**: `constants.py:20` comments that 0.000575 = 300 bps ÷ 365 × 7. A derivation test (`assert FEE_FLOOR_PER_7DAY_CYCLE == FEE_FLOOR_BPS / Decimal(10000) / Decimal(365) * Decimal(7)`) would catch any constant drift. Add in Week-3 cleanup.

### C2-I2 — INFO — `pd = N(−DD)` computation lives in `baseline.merton_pd`, not `merton_kmv.py`

**Observation**: The Merton/KMV solver returns `(V_A, σ_A, DD)`; the `N(−DD)` step lives in `baseline.merton_pd:37`. This split is fine but unclear from the module structure — callers have to know to chain `MertonKMVSolver.solve(...)` → `merton_pd(...)`. Consider exposing a `MertonKMVSolver.solve_pd(...)` convenience method in Week-3 cleanup. Tracking only.

---

## 5. What was applied inline this sprint

| Finding | File | Change |
|--------|------|--------|
| C2-H1 | `lip/c2_pd_model/README.md` | Rewrote "Key Classes" table to list actual files/functions; added methodology caveat pointing to C2-H2 |
| C2-M1 | `lip/common/constants.py:26` | `WAREHOUSE_ELIGIBILITY_FLOOR_BPS: Final[Decimal] = Decimal("800")` |
| C2-M1 | `lip/c2_pd_model/fee.py:327` | Removed redundant `Decimal(str(...))` coercion |
| C2-M3 | `lip/c2_pd_model/merton_kmv.py:39–47` | Removed unused `barrier_penalty` parameter |

## 6. What is deferred

| Finding | Deferral reason | Owner | Target |
|---------|-----------------|-------|--------|
| C2-H2 | Methodology change — requires retraining + data card | ARIA + QUANT | Week-3 before SR 11-7 validation |
| C2-H3 | Bundle with C6-H1 HMAC migration | CIPHER | Week-3 |
| C2-M2 | Data card task, not code | ARIA + REX | Week-3 |
| C2-L1 | Typed-return refactor bundle | ARIA | Week-3 cleanup |
| C2-L2 | Dead-code cleanup bundle | QUANT | Week-3 cleanup |
| C2-I1, I2 | Nice-to-have | QUANT | Week-3 cleanup |

---

## 7. Files reviewed

| File | LOC (approx) | Review depth |
|------|-------------|--------------|
| `lip/c2_pd_model/fee.py` | 343 | Full — line-by-line for floor enforcement, cascade path, Decimal discipline |
| `lip/c2_pd_model/merton_kmv.py` | 125 | Full — solver math verified against Crosbie & Bohn 2003 |
| `lip/c2_pd_model/baseline.py` | 180 | Full — Altman variant identification, Merton PD derivation |
| `lip/c2_pd_model/lgd.py` | ~90 | Full — Decimal discipline, citation audit |
| `lip/c2_pd_model/tier_assignment.py` | ~135 | Full — hashing primitive, tier routing |
| `lip/c2_pd_model/inference.py` | ~220 | Scanned — salt configuration, privacy contract |
| `lip/c2_pd_model/README.md` | 71 | Full — against source tree |
| `lip/common/constants.py` (fee section) | 50 | Full — typing + citation |

---

## 8. Lens sign-off

- **QUANT**: fee arithmetic **A−** (floor enforcement correct; constants typing now canonical). Methodology gap (C2-H2) flagged to ARIA — not a QUANT call alone.
- **ARIA**: model scaffolding **B**. Blocker: Altman Z variant alignment before any Tier-3 production retraining.
- **CIPHER** (coordination): C2-H3 will ride on the C6-H1 HMAC migration bundle.
- **REX**: data card gaps (LGD citation, Altman variant decision record) must close before SR 11-7 validation.

**Next**: Day 12.2 — P5 Cascade Engine review.
