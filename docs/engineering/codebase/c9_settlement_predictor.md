# `lip/c9_settlement_predictor/` — C9 Settlement-Time Forecaster

> **Survival-analysis model for settlement-time prediction.** Where C1 predicts whether a payment will fail and C2 prices the bridge, C9 predicts *when* a payment that has failed will eventually settle. The output (an ETA distribution, not a point estimate) feeds the C3 maturity-window calibration and the customer-facing notification copy generated via `lip/common/notification_service.py`.

**Source:** `lip/c9_settlement_predictor/`
**Module count:** 2 modules + `__init__.py`
**Self-description:** *"C9 — Settlement time prediction via survival analysis."*

---

## Purpose

The base pipeline (Algorithm 1) treats every CLASS_A failure as having a 3-day maturity, every CLASS_B as 7 days, every CLASS_C as 21 days. Those are floors — the actual settlement time for any individual failed payment is a distribution shaped by the corridor, the rejection code, the bank pair, and the time of day. C9 fits a survival-analysis model to historical settlement events and emits a per-payment ETA distribution at offer time.

Three downstream consumers care:

1. **C3 maturity calibration** — instead of a fixed-class maturity, C3 can use the C9 distribution to set the maturity window at the right percentile (typically the 95th) of expected settlement time, which reduces over-extension on fast settlements and under-funding on slow ones
2. **Customer-facing notifications** — the bank's MIPLO can tell its corporate client "your payment is expected to settle within 18–36 hours" with a calibrated probability, instead of a useless "within the maturity window"
3. **Portfolio risk** — `lip/risk/var_monte_carlo.py` (see [`risk.md`](risk.md)) draws settlement-time samples from C9 distributions when running portfolio VaR, which gives a much tighter risk number than assuming worst-case maturity

C9 is currently a forward-looking component — the base pipeline still uses the fixed-class maturities from `rejection_taxonomy.yaml` (see [`configs.md`](configs.md)). C9 outputs are available but consumed only by the portfolio risk layer at present. Wiring C9 into C3's maturity calibration is a follow-up task gated on QUANT sign-off of the survival model's calibration.

---

## Modules

| File | Purpose |
|------|---------|
| `model.py` | The survival model itself. Likely Cox proportional-hazards or accelerated-failure-time depending on which fits the synthetic distribution best — read the source for the current choice. Exposes `fit`, `predict_distribution`, `predict_quantile`, calibration metrics. |
| `synthetic_data.py` | Synthetic settlement-time corpus generator for C9 training. Produces correlated settlement events with realistic right-censoring (some payments are still unsettled at the corpus cutoff, which survival analysis handles natively). |

The `__init__.py` is intentionally a one-line docstring with no exports — the module is consumed only by direct import from internal callers (currently `lip/risk/`).

---

## Why survival analysis specifically

Settlement time is **right-censored** at the maturity window: for any payment that has not settled by maturity, we know the settlement time is at least the maturity, but not the exact value. Standard regression models cannot handle this without throwing away the censored observations, which is most of the dataset for slow corridors. Survival models (Cox, AFT, parametric Weibull / log-normal) handle censoring natively, which is why C9 uses them.

This is also a **patentable** modelling choice in combination with the LIP base pipeline — using a survival model to set bridge-loan maturity windows on cross-border failed payments is novel. The C9 contribution is referenced in the forward technology disclosure ([`docs/legal/patent/Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md)).

## Cross-references

- **Reading order**: this file → `model.py` → `synthetic_data.py`
- **Consumers**: `lip/risk/var_monte_carlo.py` (today); `lip/c3_repayment_engine/` (planned, gated on QUANT sign-off)
- **Maturity windows it would replace**: `lip/configs/rejection_taxonomy.yaml` `maturity_days` table (see [`configs.md`](configs.md))
- **Forward technology disclosure**: [`../../legal/patent/Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md)
- **Notification surface**: `lip/common/notification_service.py` (see [`common.md`](common.md))
