# `lip/c9_settlement_predictor/` — C9 Settlement-Time Forecaster

> **Survival-analysis model for settlement-time prediction.** Where C1 predicts whether a payment will fail and C2 prices the bridge, C9 predicts *when* a payment that has failed will eventually settle. The output (an ETA distribution, not a point estimate) feeds the C3 maturity-window calibration and the customer-facing notification copy generated via `lip/common/notification_service.py`.

**Source:** `lip/c9_settlement_predictor/`
**Module count:** 3 modules + `__init__.py`, 673 LoC
**Test file:** `lip/tests/test_settlement_predictor.py` (15 tests)
**Model card:** [`../../models/c9-model-card.md`](../../models/c9-model-card.md)
**Self-description:** *"C9 — Settlement time prediction via Cox Proportional Hazards."*

---

## Production status (critical)

C9 is **NOT wired into the production real-time pipeline by default.** `lip/api/runtime_pipeline.py::_build_settlement_predictor` returns `None` unless `LIP_C9_ENABLED=1`. When activated, the predictor is fitted on synthetic data at process boot — suitable for staging smoke tests but **not valid for live capital decisions**.

Production wiring requires:

1. Real bank settlement history corpus (≥10K observations per corridor)
2. REX sign-off on the calibration methodology
3. QUANT sign-off on the fallback maturity floor
4. Out-of-time validation run against the pilot bank's actual history

Until then C9's deployment mode is the `analytics` batch profile via `lip/c9_settlement_predictor/job.py`.

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
| `model.py` | Cox Proportional Hazards implementation via `lifelines` (MIT-licensed optional dep). Falls back to a deterministic corridor-average heuristic when `lifelines` is not installed. Exposes `fit`, `predict`, `predict_dynamic_maturity_days`, `save`, `load`. |
| `synthetic_data.py` | Synthetic settlement-time corpus generator. Weibull(k=0.8, λ=48h) duration distribution, censored at 168h, ~20% right-censoring. Seed=42 for reproducibility. |
| `job.py` | Entry point for the `analytics` staging profile — fits the model on synthetic data, runs one example prediction, prints a JSON status envelope. Used as the batch job image command: `python -m lip.c9_settlement_predictor.job`. |

The `__init__.py` is intentionally a one-line docstring with no exports — the module is consumed only by direct import from internal callers (currently `lip/risk/` and, when enabled, `lip/api/runtime_pipeline.py`).

## Feature set

Canonical 8-feature vector (`FEATURE_NAMES` in `model.py`):

1. `corridor` — one-hot over top-30 corridors; rest → `OTHER`
2. `rejection_class` — one-hot {A, B, C} (BLOCK never reaches C9 — blocked upstream)
3. `amount_usd` — log1p scaling
4. `hour_of_day_sin`, `hour_of_day_cos` — cyclic
5. `day_of_week_sin`, `day_of_week_cos` — cyclic
6. `sending_bic_tier` — ordinal {1, 2, 3}
7. `receiving_bic_tier` — ordinal {1, 2, 3}
8. `historical_corridor_p50_hours` — continuous; reduces cold-start bias

## Runtime wiring (when enabled)

`lip/api/runtime_pipeline.py::_build_settlement_predictor` — activates only when `LIP_C9_ENABLED=1`:

```python
predictor = SettlementTimePredictor()
X, durations, events = generate_settlement_data(
    n_samples=int(os.environ.get("LIP_C9_FIT_SAMPLES", "512")),
    seed=int(os.environ.get("LIP_C9_FIT_SEED", "42")),
)
predictor.fit(X, durations, events)
```

Pipeline wiring: `LIPPipeline` accepts `settlement_predictor=`. When provided, `lip/pipeline.py` calls `c7_agent.set_settlement_predictor(predictor)` so C7 can use `predict_dynamic_maturity_days(corridor, rejection_class, amount)` to scale the canonical `CLASS_A/B/C` maturity window down when the payment will predictably resolve faster.

### Dynamic maturity floor

`predict_dynamic_maturity_days` clamps the result to:

```
max(ceil(predicted_p90_hours / 24), static_maturity_floor_days)
```

The floor prevents C9 from recommending a maturity shorter than the canonical minimum (QUANT-locked). When `using_dynamic = False`, the canonical path is indistinguishable from no-C9 operation.

---

## Why survival analysis specifically

Settlement time is **right-censored** at the maturity window: for any payment that has not settled by maturity, we know the settlement time is at least the maturity, but not the exact value. Standard regression models cannot handle this without throwing away the censored observations, which is most of the dataset for slow corridors. Survival models (Cox, AFT, parametric Weibull / log-normal) handle censoring natively, which is why C9 uses them.

This is also a **patentable** modelling choice in combination with the LIP base pipeline — using a survival model to set bridge-loan maturity windows on cross-border failed payments is novel. The C9 contribution is referenced in the forward technology disclosure ([`docs/legal/patent/Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md)).

## Env var reference

| Env | Default | Purpose |
|-----|---------|---------|
| `LIP_C9_ENABLED` | `0` | Gate — activate runtime wiring at pipeline construction |
| `LIP_C9_FIT_SAMPLES` | `512` | Number of synthetic samples used at boot fit |
| `LIP_C9_FIT_SEED` | `42` | Random seed for reproducibility |
| `LIP_C9_JOB_SAMPLES` | `256` | Samples used by the `analytics` batch job (`job.py`) |

## Operator signals

- **Boot log (enabled)** — `"C9 settlement predictor fitted on synthetic corpus (samples=<N> model=cox_ph|fallback)"`
- **Fit failure** — `"C9 settlement predictor fit failed (<exc>); falling back to static maturity."` WARNING
- **Prometheus metric** — `lip_c9_dynamic_maturity_hours` (histogram) — quantile-watchable
- **Alert** — `using_dynamic=False` rate > 50% over 1h ⇒ corridor coverage has drifted from training distribution; retrain or disable

## Cross-references

- **Reading order**: this file → `model.py` → `synthetic_data.py` → `job.py`
- **Model card**: [`../../models/c9-model-card.md`](../../models/c9-model-card.md)
- **Consumers**: `lip/risk/portfolio_risk.py`; `lip/c7_execution_agent/agent.py` (via `set_settlement_predictor` when enabled)
- **Pipeline integration**: `lip/api/runtime_pipeline.py::_build_settlement_predictor`
- **Maturity windows it scales down** (never below the floor): `lip/configs/rejection_taxonomy.yaml` `maturity_days` table (see [`configs.md`](configs.md))
- **Forward technology disclosure**: [`../../legal/patent/Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md)
- **Notification surface**: `lip/common/notification_service.py` (see [`common.md`](common.md))
- **Academic references**:
  - Cox DR, "Regression Models and Life-Tables," JRSS-B, 1972
  - Katzman et al., "DeepSurv," BMC Medical Research Methodology, 2018
  - Kvamme et al., "Time-to-Event Prediction with Neural Networks and Cox Regression," JMLR, 2019
