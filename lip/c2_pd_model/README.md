# C2: PD Model (Probability of Default)

## Role in Pipeline

C2 prices the credit risk of a proposed bridge loan. Given the upstream C1 failure-probability score and the borrower profile, C2 selects a structural PD model (tiered by data availability), computes a probability-of-default score, and outputs an **annualised fee in basis points** with a hard floor of 300 bps.

## Algorithm 1 Position

```
C5 → C1 → C4 ∥ C6 → [C2] → C7 → C3
```

C2 is **Step 3** of Algorithm 1 — runs only after C4 and C6 have both passed (no hard block).

## Key Classes

| Class / Function | File | Description |
|-----------------|------|-------------|
| `PDInferenceEngine` | `inference.py` | Production inference wrapper — routes tier, hashes borrower IDs, enforces fee floor |
| `PDModel` | `model.py` | Trained ensemble used for production PD inference |
| `MertonKMVSolver` | `merton_kmv.py` | Structural Merton/KMV asset-value solver (Crosbie & Bohn 2003) — Tier-1 feature input |
| `merton_pd` | `baseline.py` | Analytic Merton PD — baseline/feature |
| `altman_z_score`, `altman_pd` | `baseline.py` | Analytic Altman Z-score and PD mapping — baseline/feature; **see §Methodology caveat below** |
| `assign_tier`, `hash_borrower_id` | `tier_assignment.py` | Data-availability tier routing + salted borrower-ID hashing |
| `UnifiedFeatureEngineer` | `features.py` | 75-dim feature construction across tiers |
| `compute_fee_bps_from_el`, `compute_cascade_adjusted_pd` | `fee.py` | Fee derivation from PD×LGD, with platform floor (300 bps) and warehouse floor (800 bps) |
| `lgd_for_corridor` | `lgd.py` | Per-jurisdiction LGD table (fully-Decimal) |

> **Methodology caveat (under ARIA+QUANT review, 2026-04-19)**: `altman_z_score`
> currently implements the original Altman (1968) Z for **public** manufacturing
> firms — it requires `market_cap` in X₄ (see `baseline.py:95`). For the stated
> Tier-3 thin-file **private**-borrower use case, the Z′ (1983) variant with
> book equity substituted for market cap and recalibrated coefficients
> (0.717·X₁ + 0.847·X₂ + 3.107·X₃ + 0.420·X₄ + 0.998·X₅) is the correct model.
> Tracked in `docs/engineering/review/2026-04-17/week-2-code-quality/module-c2-review.md` (C2-H2).

## Inputs / Outputs

**Input** — `(payment_dict, borrower_dict)`:

| Key | Source | Description |
|-----|--------|-------------|
| `failure_probability` | C1 output | Upstream failure probability |
| `rejection_code_class` | C3 taxonomy | `'A'`, `'B'`, or `'C'` — determines maturity |
| `loan_amount` | event | Bridge principal in USD |
| `corridor` | event | ISO 4217 currency pair |
| Borrower fields | borrower_dict | Market cap, leverage, industry beta (Tier 1/2) |

**Output** dict:

| Key | Type | Description |
|-----|------|-------------|
| `pd_score` | float | Probability of default [0, 1] |
| `fee_bps` | int | **Annualised** fee in basis points (≥ 300) |
| `tier` | int | Model tier used (1, 2, or 3) |
| `days_funded` | int | Maturity days (A=3, B=7, C=21) |
| `expected_fee_usd` | Decimal | Pre-computed fee |

## ⚠️ Fee Formula Warning

`fee_bps` is an **ANNUALISED** rate. The correct per-cycle calculation is:

```
per_cycle_fee = loan_amount × (fee_bps / 10_000) × (days_funded / 365)
```

**DO NOT** apply `fee_bps` as a flat per-cycle rate. 300 bps annualised ≈ 0.0575% per 7-day cycle.

## Sub-day fee floor framework (Phase A, 2026-04-25)

Sub-day rails (CBDC at 4h, FedNow/RTP at 24h) need a *tighter* fee floor than the universal 300 bps because at sub-day tenor, 300 bps annualised doesn't cover bank cost of funds.

**Math at $5M / 4h:** 300 bps × 4/8760 = $68 vs 5% COF capital cost = $114 — loss-making at universal floor.

**`compute_fee_bps_from_el(maturity_hours=...)`** selects the binding floor via `applicable_fee_floor_bps()`:

```
applicable_fee_floor_bps(maturity_hours)
  → FEE_FLOOR_BPS_SUBDAY (1200) if maturity_hours < 48h
  → FEE_FLOOR_BPS (300)          otherwise
```

The two floors are **additive** — sub-day is a *tighter* floor, not a replacement. The universal 300 bps floor is preserved unchanged per CLAUDE.md non-negotiable #2.

**`apply_absolute_fee_floor(fee_usd)`** is a *separate* helper (not embedded in `compute_loan_fee`) that enforces a $25 operational absolute floor at C7 offer-construction time. Keeping it separate preserves `compute_loan_fee`'s raw-math contract (Architecture Spec C2 §9) so edge-case tests (zero principal, negative inputs) still work.

**Side effect:** existing FedNow / RTP loans (24h maturity) are now subject to the 1200 bps floor. This is a *correction* of pricing that previously under-recovered cost of funds; no production FedNow/RTP loans existed when the change was made.

## ⚠️ Fee Formula Warning

`fee_bps` is an **ANNUALISED** rate. The correct per-cycle calculation is:

```
per_cycle_fee = loan_amount × (fee_bps / 10_000) × (days_funded / 365)
```

**DO NOT** apply `fee_bps` as a flat per-cycle rate. 300 bps annualised ≈ 0.0575% per 7-day cycle.

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `FEE_FLOOR_BPS` | **300** | Universal annualised floor — applies to ALL loans (CLAUDE.md non-negotiable #2) |
| `FEE_FLOOR_BPS_SUBDAY` | **1200** | Tighter floor for sub-day rails (maturity < 48h). Calibrated to cost of capital. |
| `FEE_FLOOR_ABSOLUTE_USD` | **25** | Operational absolute floor applied via `apply_absolute_fee_floor()` at C7 |
| `SUBDAY_THRESHOLD_HOURS` | **48.0** | Boundary: maturity_hours < this → SUBDAY floor |
| `FEE_FLOOR_PER_7DAY_CYCLE` | `0.000575` | 0.0575% per 7-day cycle (= 300 bps / 365 × 7) |
| `WAREHOUSE_ELIGIBILITY_FLOOR_BPS` | **800** | Warehouse-eligibility floor for SPV-funded loans (Phase 2/3) |
| `MATURITY_CLASS_A_DAYS` | 3 | Class A rejection codes (e.g., technical errors) |
| `MATURITY_CLASS_B_DAYS` | 7 | Class B rejection codes (default) |
| `MATURITY_CLASS_C_DAYS` | 21 | Class C rejection codes (complex disputes) |
| `RAIL_MATURITY_HOURS["CBDC_*"]` | **4.0** | All CBDC-class rails — 4h buffer over programmatic finality |

## Key fee-math API

| Function | Purpose |
|---|---|
| `compute_fee_bps_from_el(pd, lgd, ead, maturity_hours=...)` | Annualised fee bps from EL, with rail-aware floor selection |
| `compute_loan_fee(amount, fee_bps, days_funded)` | Raw per-cycle formula — preserved exactly for spec compliance |
| `apply_absolute_fee_floor(fee_usd)` | C7-side enforcement of $25 operational floor |
| `is_subday_rail(maturity_hours)` | Boolean: True iff maturity_hours < SUBDAY_THRESHOLD_HOURS |
| `applicable_fee_floor_bps(maturity_hours)` | Returns the binding floor in bps |
| `compute_tiered_fee_floor(loan_amount)` | Tier-based floor (defence-in-depth in C7) |

## Spec References

- Architecture Spec v1.2 Appendix A — fee formula and 300 bps floor
- Architecture Spec v1.2 §4.3 — `PDRequest` / `PDResponse` API schemas
- ADR-2026-04-25-rail-aware-maturity.md — sub-day fee floor design + cost-of-capital math
- SR 11-7 §4.4 — Tiered model validation requirements
