# C2 Fee Formula Hardening
## Spec/Design Document

**Status:** Implemented  
**Priority:** 8 (final migration step)  
**Owner:** QUANT  
**Reviewers:** ARIA, REX  
**Date:** 2026-04-02  

---

## 1. Rationale: No Language Migration

The C2 fee formula is a single arithmetic expression operating on `Decimal` types.
There is no latency or concurrency benefit from moving it to Rust, Go, or any
other language. Python's `decimal.Decimal` with `ROUND_HALF_UP` is the correct
tool: it gives exact cent-level rounding with no floating-point drift, and it is
fully auditable in a single-file pure function.

**Decision (unanimous, QUANT final authority):** Architectural discipline only —
isolate the formula as a named pure function with full test coverage and a single
definition point. No language migration.

---

## 2. Formula Derivation

The per-cycle bridge-loan fee is a time-proportionate slice of an annualised
interest rate:

```
fee = loan_amount × (fee_bps / 10 000) × (days_funded / 365)
```

**Why annualised?**

`fee_bps` is an **annualised** rate in basis points (minimum 300 bps per
QUANT canonical floor). Applying it as a flat per-cycle rate would be incorrect:
a 300 bps flat charge on a $1M loan would be $30,000 per cycle regardless of
duration, versus the correct time-proportionate $575.34 for a 7-day cycle.

**Why 365 days?**

Actual/365 convention is standard for interbank bridge facilities and matches
the Basel III EAD/EL calculation convention.

**Canonical function:** `compute_loan_fee` in `lip/c2_pd_model/fee.py`

```python
def compute_loan_fee(
    loan_amount: Union[Decimal, float, int],
    fee_bps: Union[Decimal, float, int],
    days_funded: Union[int, float, Decimal],
) -> Decimal:
    fee = loan_amount × (fee_bps / 10 000) × (days_funded / 365)
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

All inputs are coerced to `Decimal` via `Decimal(str(...))` before arithmetic,
ensuring no floating-point precision loss even when callers pass `float` values
(e.g. fractional days from the synthetic data generator).

---

## 3. Fee Floor

The **annualised** fee rate is floored at **300 bps** by `compute_fee_bps_from_el`:

```
fee_bps = max(300, PD × LGD × 10 000)
```

The floor is applied **before** `compute_loan_fee` is called. Callers must not
bypass the floor by calling `compute_loan_fee` directly with a sub-300 `fee_bps`.

---

## 4. Single Source of Truth — Call Sites

All C2 fee calculations must route through `compute_loan_fee`. The following
call sites were audited and patched as part of this hardening step:

| File | Change |
|------|--------|
| `lip/c2_pd_model/fee.py` | **Canonical definition** — `compute_loan_fee` |
| `lip/c2_pd_model/inference.py` | Already used `compute_fee_bps_from_el` + `compute_loan_fee` ✓ |
| `lip/c7_execution_agent/agent.py` | Already imported `compute_loan_fee` ✓ |
| `lip/c3_repayment_engine/repayment_loop.py` | Already imported `compute_loan_fee` ✓ |
| `lip/api/portfolio_router.py` | **Patched** — replaced inline formula with `compute_loan_fee` |
| `lip/dgen/c3_generator.py` | **Patched** — replaced 5 inline formulas with `compute_loan_fee` |
| `lip/train_all.py` | **Patched** — replaced inline `fee_bps` validation with `compute_fee_bps_from_el` |
| `lip/scripts/simulate_pipeline.py` | Already used `compute_loan_fee` ✓ |

**Schemas (`lip/common/schemas.py`):** The formula appears in field `description`
strings only (documentation). No runtime computation occurs there; no patch needed.

---

## 5. Test/Failure Grid

| Scenario | Test class | Key assertion |
|----------|------------|---------------|
| Golden fixtures (QUANT-blessed values) | `TestGoldenFixtures` | `fee == Decimal(expected)` |
| Linearity in loan_amount | `TestPropertyInvariants` | `fee(2x) ≈ 2 × fee(x)` ±$0.01 |
| Linearity in fee_bps | `TestPropertyInvariants` | `fee(2bps) ≈ 2 × fee(bps)` ±$0.01 |
| Linearity in days_funded | `TestPropertyInvariants` | `fee(2d) ≈ 2 × fee(d)` ±$0.01 |
| Non-negativity | `TestPropertyInvariants` | `fee >= 0` for all valid inputs |
| Full-year = annualised rate | `TestPropertyInvariants` | `fee(365d) == principal × bps/10000` |
| Annualised ≠ flat per-cycle | `TestPropertyInvariants` | `fee_annualised < fee_flat` |
| Monotone in days and bps | `TestPropertyInvariants` | Increasing sequence stays non-decreasing |
| 2 decimal places (cents) | `TestCurrencyRounding` | `fee == fee.quantize("0.01")` |
| ROUND_HALF_UP confirmation | `TestCurrencyRounding` | $575.34 golden |
| Return type is Decimal | `TestCurrencyRounding` | `isinstance(fee, Decimal)` |
| Float inputs coerced correctly | `TestCurrencyRounding` | Same result as Decimal inputs |
| Int inputs coerced correctly | `TestCurrencyRounding` | Same result as Decimal inputs |
| Zero days_funded → zero fee | `TestEdgeCaseInputs` | `fee == 0.00` |
| Zero loan_amount → zero fee | `TestEdgeCaseInputs` | `fee == 0.00` |
| Zero fee_bps → zero fee | `TestEdgeCaseInputs` | `fee == 0.00` |
| Single-day loan | `TestEdgeCaseInputs` | `fee == 82.19` ($1M, 300 bps) |
| Fractional days (float) | `TestEdgeCaseInputs` | `fee(3.5d) ≈ fee(7d)/2` ±$0.01 |
| Minimum realistic loan ($5K) | `TestEdgeCaseInputs` | `fee == 1.23` (3d, 300 bps) |
| Very large loan ($1B) — no overflow | `TestEdgeCaseInputs` | No exception; ≈$575K |
| 500% fee_bps — no overflow | `TestEdgeCaseInputs` | `fee == 5000000.00` |
| Penny principal → zero fee | `TestEdgeCaseInputs` | `fee == 0.00` |
| Negative loan_amount | `TestNegativeInputs` | `fee < 0` (arithmetic pass-through) |
| Negative fee_bps | `TestNegativeInputs` | `fee < 0` |
| Negative days_funded | `TestNegativeInputs` | `fee < 0` |
| Floor always applied (low EL) | `TestFeeBpsFloor` | `fee_bps >= 300` |
| No clamping above floor | `TestFeeBpsFloor` | `fee_bps == 450.0` for PD=0.10, LGD=0.45 |
| Royalty + net == fee | `TestRoyaltySplitInvariant` | No rounding leak |
| c3_generator uses compute_loan_fee | `TestSingleSourceIntegration` | Source inspection |
| portfolio_router uses compute_loan_fee | `TestSingleSourceIntegration` | Source inspection |
| train_all uses compute_fee_bps_from_el | `TestSingleSourceIntegration` | Source inspection |
| repayment_loop uses compute_loan_fee | `TestSingleSourceIntegration` | Source inspection |
| c7 agent uses compute_loan_fee | `TestSingleSourceIntegration` | Source inspection |

---

## 6. Rollback Plan

If a defect is found in `compute_loan_fee` after deployment:

1. **Immediate:** Revert commit in `lip/c2_pd_model/fee.py` only (single-function
   change — one file reverts the formula).
2. **Scope:** All call sites (c3_generator, portfolio_router, train_all, repayment_loop,
   c7 agent) automatically revert because they import the function.
3. **No data migration required:** The formula change is idempotent for new loan
   originations. In-flight loans use the stored `fee_bps` and `days_funded` fields
   from the offer record — they do not recompute the fee from scratch.
4. **Audit trail:** QUANT must file a deviation report citing the affected date range
   and recalculate actual vs. expected fees for any loans originated during the
   defective window.

---

## 7. Definition of Done Checklist

- [x] Spec doc merged (`docs/specs/c2_fee_formula_hardening.md`)
- [x] `compute_loan_fee` is the single named pure function (already existed in `fee.py`)
- [x] `days_funded` type broadened to `Union[int, float, Decimal]` (handles generator)
- [x] `lip/api/portfolio_router.py` patched to call `compute_loan_fee`
- [x] `lip/dgen/c3_generator.py` (5 inline usages) patched to call `compute_loan_fee`
- [x] `lip/train_all.py` patched to call `compute_fee_bps_from_el`
- [x] `lip/tests/test_c2_fee_formula.py` created (golden fixtures, property-based,
      rounding, edge cases, negative inputs, overflow, single-source integration)
- [x] `ruff check lip/` passes (zero errors)
- [x] `python -m pytest lip/tests/` passes (no regressions)
