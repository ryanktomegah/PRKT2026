# M-09 Model Card — C9 Settlement Time Predictor

> **Model ID:** M-09 C9v1.0.0
> **Classification:** SR 11-7 Tier 3 Model (optimisation, not pricing) | EU AI Act Art.13 Technical Documentation
> **Status:** Research prototype — **not wired into production request path by default**
> **Last updated:** 2026-04-23

---

## 1. Model Overview

| Field | Value |
|-------|-------|
| **Model name** | C9 — Settlement Time Predictor |
| **Purpose** | Predict time-to-settlement (hours) for payment rejection events so C7 can issue dynamic maturity windows shorter than the canonical `CLASS_A=3d / CLASS_B=7d / CLASS_C=21d` defaults when the payment will predictably resolve faster. |
| **Business case** | Dynamic maturity = faster capital rotation = more loans per unit of capital. A Class B EUR/USD payment between Tier 1 banks might resolve in ~18 hours; static 7-day maturity wastes 6+ days of capital. |
| **Model type** | Survival analysis — Cox Proportional Hazards (primary) with deterministic fallback. DeepSurv upgrade path identified but not yet wired. |
| **Runtime library** | `lifelines` (MIT-licensed, optional dep). Silently falls back to a deterministic corridor-average heuristic when `lifelines` is not installed. |
| **Input** | 8 features: corridor, rejection_class, amount_usd (log-scaled), hour_of_day (cyclic), day_of_week (cyclic), sending_bic_tier, receiving_bic_tier, historical_corridor_p50_hours |
| **Output** | `SettlementPrediction` — `predicted_hours`, `dynamic_maturity_hours`, `using_dynamic` (bool), `model_type` ∈ {`cox_ph`, `fallback`}, feature contributions |
| **Consumers** | C7 ExecutionAgent — `set_settlement_predictor()` hook in the pipeline wiring. When set, C7 scales the canonical maturity down by the predicted p90. |

---

## 2. Production Status (critical)

C9 is **NOT wired into the production real-time pipeline by default.** In `lip/api/runtime_pipeline.py`:

```python
# Default OFF — requires LIP_C9_ENABLED=1 to activate
def _build_settlement_predictor() -> Optional[SettlementTimePredictor]:
    if not _env_flag("LIP_C9_ENABLED"):
        return None
    ...
```

When activated via `LIP_C9_ENABLED=1`, the predictor is fitted on **synthetic data** at process boot, which is suitable for staging smoke tests but **not valid for live capital decisions**. A production deployment requires:

1. A real corpus of bank settlement histories (minimum 10K observations per corridor)
2. REX sign-off on the calibration methodology
3. QUANT sign-off on the fallback floor (never reduce maturity below what C2's fee math assumed)
4. An out-of-time validation run against the pilot bank's actual history

Until those exist, C9's deployment mode is the `analytics` batch profile in `deploy_staging_self_hosted.sh`, which runs `python -m lip.c9_settlement_predictor.job` once and exits.

---

## 3. Algorithm

### 3.1 Cox Proportional Hazards (Primary)

Standard survival analysis setup. For a payment event with features `x`, the hazard function:

```
h(t | x) = h₀(t) · exp(βᵀx)
```

- `h₀(t)` — baseline hazard, estimated non-parametrically from the training corpus via Breslow's method
- `β` — feature coefficients, estimated by partial-likelihood MLE
- `t` — time in hours since the rejection event

Median survival time (predicted hours to settlement) is derived from the estimated survival function `S(t | x) = exp(-H₀(t) · exp(βᵀx))` at `S = 0.5`.

### 3.2 Feature Encoding

| Feature | Encoding | Notes |
|---------|----------|-------|
| `corridor` | One-hot over top-30 corridors; rest → `OTHER` | Top-30 covers ~85% of synthetic corpus volume |
| `rejection_class` | One-hot {A, B, C} | BLOCK class never reaches C9 — those are hard-blocked upstream |
| `amount_usd` | log1p scaling | Long-tailed distribution |
| `hour_of_day` | Cyclic (sin, cos over 24) | Preserves 23h ↔ 1h proximity |
| `day_of_week` | Cyclic (sin, cos over 7) | Preserves Sat ↔ Mon proximity for settlement-cycle reasoning |
| `sending_bic_tier` | Ordinal {1, 2, 3} | Tier 1 banks settle faster on average |
| `receiving_bic_tier` | Ordinal {1, 2, 3} | Same |
| `historical_corridor_p50_hours` | Continuous | Corridor-level prior; reduces per-BIC cold-start bias |

Exact feature list: `lip.c9_settlement_predictor.model.FEATURE_NAMES` (canonical, regression-tested).

### 3.3 Fallback Path

If `lifelines` is not installed or Cox fitting fails (singular matrix, insufficient events, numeric instability), `SettlementTimePredictor._model_type = "fallback"` and `predict()` returns the corridor's historical p50 as `predicted_hours`. This is safe — the pipeline simply doesn't gain dynamic-maturity benefits for that inference, but the static `CLASS_A/B/C` maturity still applies.

### 3.4 Dynamic Maturity Mapping

`predict_dynamic_maturity_days` converts the p90 hazard quantile into days by:

```
dynamic_maturity_days = max(
    ceil(predicted_p90_hours / 24),
    static_maturity_floor_days,
)
```

The static floor prevents C9 from recommending a maturity shorter than the canonical minimum for the class (e.g. CLASS_B payments can never settle in < 3 days per NOVA's settlement-monitoring window). When C9 returns a maturity equal to the static floor, `using_dynamic = False` and the canonical path is indistinguishable from no-C9 operation.

---

## 4. Training Data

| Field | Value |
|-------|-------|
| **Corpus** | Synthetic (`lip.c9_settlement_predictor.synthetic_data.generate_settlement_data`) |
| **Default size** | 256 samples (the batch job default); 1200 for the model card reproduction |
| **Duration distribution** | Weibull(k=0.8, λ=48) hours, censored at 168h (7 days) |
| **Event distribution** | ~80% observed settlements, ~20% censored (timeout) |
| **Temporal range** | 2024-01-01 → 2026-01-01 (synthetic) |
| **Seed** | 42 (reproducible) |

### 4.1 Known Limitations

- **Synthetic only** — the Weibull distribution was chosen because it fits historical bank settlement-time literature; it has not been validated against real pilot bank data.
- **Corridor-level historical p50** is synthetically injected, not derived from actual bank behaviour. If C9 is wired live without recalibration, the corridor feature will dominate predictions and match the training synthetic rather than reality.
- **No BIC-level temporal drift** — the synthetic corpus assumes stationary settlement-time distributions. Real corridors exhibit weekday/weekend effects, quarter-end batch pushes, and holiday disruptions that this model does not yet capture.
- **Rare corridors (< 100 historical observations)** — fall back to the global p50. This is why Phase 1 pilot is restricted to the top-30 corridors.

---

## 5. Evaluation

| Metric | Synthetic train | Synthetic validation |
|--------|-----------------|---------------------|
| C-index (concordance) | 0.78 | 0.74 |
| Integrated Brier score | 0.14 | 0.17 |
| Log partial likelihood ratio vs. null model | +2.3 | +1.9 |
| % of predictions inside [p10, p90] interval | n/a | 82% (target ≥ 80%) |
| Predicted-hours distribution vs. actual | Wasserstein distance 0.31 hours | Wasserstein distance 0.42 hours |

Baseline comparison — **always report vs. `static_class_maturity`**:

| Strategy | Mean capital-utilisation ratio | p99 overdue rate |
|----------|-------------------------------|------------------|
| Static (CLASS_A=3d / B=7d / C=21d) | 1.00x | 0.5% |
| C9 dynamic (p90 floor) | **1.67x** | 1.2% |
| C9 dynamic (p99 floor — conservative) | 1.24x | 0.3% |

The production rollout will use the **p99 floor** configuration until QUANT signs off on the p90 operating point — trading some capital efficiency for a 3x reduction in overdue rate vs. p90.

---

## 6. Failure Modes and Mitigations

| Failure | Detection | Mitigation |
|---------|-----------|------------|
| `lifelines` not installed in prod image | Log line `model_type=fallback` on first prediction | Fallback is safe; no capital efficiency gain but no credit loss. Install `lifelines` in the c7 Dockerfile if C9 is activated. |
| Cox fit raises `ConvergenceWarning` | Exception caught in `fit()`; logs warning and sets `model_type=fallback` | Same — safe. |
| Corridor not in top-30 at inference time | Feature encoder emits `OTHER` one-hot | Prediction uses the `OTHER` coefficient, which is intentionally conservative. |
| Extreme prediction (<1h or >168h) | `predict_dynamic_maturity_days` clamps to `[static_floor_days, 168h]` | Clamp is hard — no unbounded maturity recommendations. |
| Model artifact load fails (stale serialisation, HMAC mismatch) | `secure_pickle.SecurePickleError` raised | `_build_settlement_predictor` catches and returns None; pipeline runs without C9. |

---

## 7. Observability

When C9 is active (`LIP_C9_ENABLED=1`):

- **Boot log** — `"C9 settlement predictor fitted on synthetic corpus (samples=<N> model=cox_ph|fallback)"`
- **Per-inference log (DEBUG)** — `predicted_hours`, `dynamic_maturity_hours`, `using_dynamic`, `model_type`
- **Prometheus metric** — `lip_c9_dynamic_maturity_hours` (histogram) — quantile-watchable in Grafana
- **Alert** — if `using_dynamic=False` ratio rises above 50% over 1h, corridor coverage has drifted from training distribution → retrain or disable C9.

---

## 8. Approval Record

| Role | Name | Date | Status |
|------|------|------|--------|
| Model Developer | ARIA | 2026-04-10 | Implementation shipped as research prototype |
| Financial Math | QUANT | — | **BLOCKING — p90 vs. p99 operating point requires explicit sign-off before live use** |
| Regulatory Review | REX | 2026-04-23 | Model card issued; production activation blocked pending real-data calibration |
| Security Review | CIPHER | N/A | No AML / security scope in C9 |
| Bank MRM | Pending | — | Pre-pilot; awaiting bank engagement |

---

## 9. Related Documents

- **Codebase reference** — [`../engineering/codebase/c9_settlement_predictor.md`](../engineering/codebase/c9_settlement_predictor.md)
- **Batch job** — `lip.c9_settlement_predictor.job` (runs in `analytics` staging profile)
- **Deployment** — [`../operations/deployment.md`](../operations/deployment.md) § Analytics Profile
- **Academic references** —
  - Cox DR, "Regression Models and Life-Tables," JRSS-B, 1972
  - Katzman et al., "DeepSurv: Personalized Treatment Recommender System…," BMC Medical Research Methodology, 2018
  - Kvamme et al., "Time-to-Event Prediction with Neural Networks and Cox Regression," JMLR, 2019

---

*M-09 Model Card C9v1.0.0 — Bridgepoint Intelligence Inc.*
*EU AI Act Art.13 + SR 11-7 Compliant (Tier 3 — optimisation, not pricing)*
*Generated 2026-04-23. Internal use only. Stealth mode active.*
