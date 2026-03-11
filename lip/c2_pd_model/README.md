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
| `PDInferenceEngine` | `inference.py` | Routes to correct tier model; enforces fee floor |
| `MertonKMVModel` | `merton_kmv.py` | Tier 1: Structural model for listed counterparties |
| `DamodaranModel` | `damodaran.py` | Tier 2: Industry-beta model for private counterparties |
| `AltmanZPrimeModel` | `altman_z_prime.py` | Tier 3: Thin-file Z' score for minimal-data cases |

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

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `FEE_FLOOR_BPS` | **300** | Minimum annualised fee — **QUANT sign-off required** |
| `FEE_FLOOR_PER_7DAY_CYCLE` | `0.000575` | 0.0575% per 7-day cycle (= 300 bps / 365 × 7) |
| `MATURITY_CLASS_A_DAYS` | 3 | Class A rejection codes (e.g., technical errors) |
| `MATURITY_CLASS_B_DAYS` | 7 | Class B rejection codes (default) |
| `MATURITY_CLASS_C_DAYS` | 21 | Class C rejection codes (complex disputes) |

## Spec References

- Architecture Spec v1.2 Appendix A — fee formula and 300 bps floor
- Architecture Spec v1.2 §4.3 — `PDRequest` / `PDResponse` API schemas
- SR 11-7 §4.4 — Tiered model validation requirements
