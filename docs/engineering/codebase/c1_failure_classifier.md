# `lip/c1_failure_classifier/` — Payment Failure Prediction

> **The first ML gate in the pipeline.** Every `pacs.002` rejection event is scored here. A probability below τ\* (0.110) skips the whole downstream C4 / C6 / C2 / C7 chain — this is the throttle that keeps the 94ms SLO achievable.

**Source:** `lip/c1_failure_classifier/`
**Module count:** 14 Python files, 7,224 LoC (largest component)
**Test files:** 8 (`test_c1_{calibration,classifier,graphsage_neighbors,inference_types,lgbm_ensemble,oot_fallback,torch,training}.py`)
**Spec:** [`../specs/BPI_C1_Component_Spec_v1.0.md`](../specs/BPI_C1_Component_Spec_v1.0.md)
**Model card:** [`../../models/c1-model-card.md`](../../models/c1-model-card.md)
**Training data card:** [`../../models/c1-training-data-card.md`](../../models/c1-training-data-card.md)

---

## Purpose

C1 implements the **failure-probability gate**. Given a single ISO 20022 normalized event (BIC pair, corridor, amount, currency, timestamp, rejection code, narrative), it returns:

```python
{
    "failure_probability": 0.74,
    "above_threshold": True,           # probability >= τ* (0.110)
    "inference_latency_ms": 8.3,
    "threshold_used": 0.110,
    "corridor_embedding_used": True,   # whether the corridor lookup hit Redis
    "shap_top20": [                    # EU AI Act Art.13 transparency
        {"feature": "amount_log", "value": -1.87},
        ...
    ],
}
```

Pipeline behavior:
- `above_threshold = False` → short-circuit return (no downstream C4 / C6 / C2 / C7 calls)
- `above_threshold = True` → pipeline continues; `shap_top20` is carried into the decision log entry

---

## Architecture — the three-model stack

C1 is not a single model. It is an ensemble of three architectures that each see a different slice of the input signal:

| Model | File | Role | Why |
|-------|------|------|-----|
| **GraphSAGE** | `graphsage.py` / `graphsage_torch.py` | BIC-graph embeddings over corridor neighbourhoods | Cross-border failures correlate with structural position in the correspondent-banking graph — a peripheral BIC with thin nostro links fails differently from a central one |
| **TabTransformer** | `tabtransformer.py` / `tabtransformer_torch.py` | Tabular-feature attention over the 12 canonical features | Captures interaction effects between amount, corridor risk, and timing that a tree can't express cleanly |
| **LightGBM** | `model.py` ensemble (bagging, 5 models) | Residual catch-all on numeric features | Fast, robust, handles missing values without preprocessing — the production fallback when GPU/Torch unavailable |

The three produce calibrated probabilities that are stacked via a small MLP head (`model_torch.py::MLPHeadTorch`). Isotonic calibration (`calibration.py`) is applied to the ensemble output — not per-model — because the individual probabilities are trained with different losses and would re-miscalibrate.

### Artifact files

The trained C1 artifact directory is `artifacts/c1_trained/` (gitignored) and contains:

| File | Purpose | Required? |
|------|---------|-----------|
| `c1_model_parquet.pt` | PyTorch state dict: GraphSAGE + TabTransformer + MLP head | **Yes** — if missing, `TorchArtifactInferenceEngine.__init__` raises |
| `c1_lgbm_parquet.pkl` | LightGBM ensemble (pickled, HMAC-signed via `secure_pickle`) | Optional — falls through to torch-only if absent |
| `c1_calibrator.pkl` | Isotonic regression on ensemble output (HMAC-signed) | Optional — uses raw probabilities if absent |
| `c1_scaler.pkl` | StandardScaler for the 12 tabular features (HMAC-signed) | Optional — uses raw features if absent |
| `train_metrics_parquet.json` | Training AUC / F2 / ECE for the shipped checkpoint | Advisory only |

Current staging RC artifacts additionally include:

- `c1_calibrator.pkl.sig`
- `c1_scaler.pkl.sig`
- `f2_threshold.txt`

The RC snapshot trained on `2026-04-24` produced a best chronological OOT AUC of `0.8839` and a post-training summary AUC of `0.887623`.

All `.pkl` files load through `lip.common.secure_pickle.load()` — B13-01 pickle ban applies. Sign newly-produced artifacts with `scripts/sign_c1_artifacts.py`.

---

## Runtime loading (`inference.py` + `lip/api/runtime_pipeline.py`)

The runtime pipeline has a **tri-state fallback** for C1:

1. **`TorchArtifactInferenceEngine`** — preferred. Loads from `LIP_C1_MODEL_DIR` when the directory contains `c1_model_parquet.pt`. This is what staging uses. In the current RC the loader also expects signed `c1_lgbm_parquet.pkl`, `c1_calibrator.pkl`, and `c1_scaler.pkl` when those files are present.
2. **NumPy loader** — used when `LIP_C1_MODEL_DIR` is set but the `.pt` file is missing. Reads a legacy `.npz`-style checkpoint.
3. **`create_default_model()`** — deterministic untrained fallback. Used only when neither path above succeeds. Logs at INFO so operators can tell.

Controlled by these env vars:

| Env | Default | Purpose |
|-----|---------|---------|
| `LIP_C1_MODEL_DIR` | unset | Directory containing the C1 checkpoint bundle |
| `LIP_C1_THRESHOLD` | `0.110` (QUANT-locked) | τ\* override — should never change without QUANT sign-off |
| `LIP_REQUIRE_MODEL_ARTIFACTS` | `0` | When `1`, raise `RuntimeError` instead of falling back to the default model |
| `LIP_TORCH_NUM_THREADS` | `1` | Runtime thread cap used before loading torch artifacts to avoid BLAS deadlock |
| `LIP_TORCH_NUM_INTEROP_THREADS` | `1` | Interop thread cap paired with `LIP_TORCH_NUM_THREADS` |

### Latency instrumentation

Every prediction logs its wall-clock latency against two canonical thresholds defined in `inference.py`:

- `LATENCY_P50_TARGET_MS = 45` — log at DEBUG if exceeded
- `LATENCY_P99_TARGET_MS = 94` — log at WARNING if exceeded

The 94ms target is the QUANT-locked SLO ceiling — it is the entire LIP pipeline's p99 budget, not just C1's. If C1 alone exceeds it, the entire platform is breaching.

---

## Feature engineering (`features.py` + `graph_builder.py`)

### Tabular features (`TabularFeatureEngineer`)

Canonical 12-feature set (ordering matters for the PyTorch state dict):

1. `amount_log` — log1p(amount_usd)
2. `corridor_historical_failure_rate` — 30-day p50 from synthetic training corpus
3. `hour_of_day_sin`, `hour_of_day_cos` — cyclic
4. `day_of_week_sin`, `day_of_week_cos` — cyclic
5. `sending_bic_tier` — {1, 2, 3}
6. `receiving_bic_tier` — {1, 2, 3}
7. `is_weekend`
8. `is_holiday_jurisdiction_sending`
9. `is_holiday_jurisdiction_receiving`
10. `is_off_hours`

The 8-dim GraphSAGE node features (BIC centrality, corridor volume, failure density) are concatenated after the scaler is applied.

### BIC graph (`graph_builder.py`)

Builds a directed graph of `sending_bic → receiving_bic` edges weighted by historical volume. `get_node_features(bic)` returns an 8-dim vector; `get_neighbors(bic, k=5)` returns the 5 most-frequent corridor partners.

The graph is cached in-process — expensive to rebuild, but the synthetic training corpus has ~200 BICs so memory cost is negligible.

### Corridor embeddings (`embeddings.py::CorridorEmbeddingPipeline`)

Redis-backed LRU cache of 64-dim currency-pair embeddings. Cold start falls back to a currency-pair-mean bootstrap embedding; after ~100 corridor observations, the live-updated embedding replaces the bootstrap. Backed by `backend=redis` when `REDIS_URL` is set, `backend=in-memory` otherwise.

---

## Training pipeline (`training.py` + `training_torch.py`)

Two-phase training:

1. **Per-model pretraining** — each of the three architectures trains independently on the full corpus with its own loss. GraphSAGE uses link-prediction self-supervision before failure supervision; TabTransformer uses masked-feature reconstruction; LightGBM uses straight binary cross-entropy with bagging.
2. **Stacking + calibration** — the MLP head is trained on the held-out validation set using out-of-fold predictions from the three base models. Isotonic calibration is fitted last.

Run with: `PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic` or via `scripts/train_c1_on_parquet.py` for a single-component retrain.

---

## What C1 does NOT do

- **Does not classify dispute** — that is C4's job. Dispute classification runs *after* C1 passes the τ\* gate.
- **Does not do AML** — that is C6. C1 has no sanctions-list awareness.
- **Does not compute fee** — that is C2.
- **Does not decide to fund** — that is C7 (gated by C1+C4+C6+C2+kill switch+KMS+borrower registry).
- **Does not use the narrative text** — narrative is a C4 input. C1 operates on structured fields only.

C1's single job is "how likely is this payment to fail resolution within the classified maturity window, based purely on structural + temporal signals?"

---

## Cross-references

- **Pipeline orchestrator** — [`pipeline.md`](pipeline.md) § τ\* gate
- **Spec** — [`../specs/BPI_C1_Component_Spec_v1.0.md`](../specs/BPI_C1_Component_Spec_v1.0.md)
- **Model governance** — [`../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md) § C1
- **Canonical constants** — `lip/common/constants.py` (`FAILURE_PROBABILITY_THRESHOLD`, `LATENCY_P50_TARGET_MS`, `LATENCY_P99_TARGET_MS`)
- **Training data provenance** — [`../../models/c1-training-data-card.md`](../../models/c1-training-data-card.md)
- **Operator commands** — [`../../operations/deployment.md`](../../operations/deployment.md) § Self-Hosted Staging Deployment
