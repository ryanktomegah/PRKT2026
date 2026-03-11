# C1: Failure Classifier

## Role in Pipeline

C1 is the **pipeline entry gate**. It consumes every normalised payment event produced by C5 and predicts the probability that the underlying SWIFT / FedNow / RTP / SEPA payment will fail to settle. Only events that exceed the failure-probability threshold τ* proceed to the downstream components (C4, C6, C2, C7).

## Algorithm 1 Position

```
C5 → [C1] → if failure_probability > τ* → C4 ∥ C6 → C2 → C7 → C3
```

C1 is **Step 1** of Algorithm 1 (Architecture Spec v1.2 §3).

## Key Classes

| Class / Function | File | Description |
|-----------------|------|-------------|
| `InferenceEngine` | `inference.py` | Production inference wrapper; calls predict pipeline |
| `FeatureExtractor` | `features.py` | Extracts tabular + graph features from payment dicts |
| `EnsembleModel` | `model.py` | Combines GraphSAGE + TabTransformer + LightGBM outputs |
| `CorridorEmbeddingStore` | `corridor_embeddings.py` | Loads per-currency-pair embeddings from Redis |

## Inputs / Outputs

**Input** — payment dict keys (produced by `LIPPipeline._event_to_payment_dict`):

| Key | Type | Description |
|-----|------|-------------|
| `uetr` | str | ISO 20022 UETR |
| `amount_usd` | float | Transaction amount normalised to USD |
| `currency_pair` | str | e.g. `'EUR_USD'` |
| `sending_bic` | str | BIC of originating bank |
| `receiving_bic` | str | BIC of destination bank |
| `timestamp` | str | ISO 8601 UTC event timestamp |
| `corridor_failure_rate` | float | Historical failure rate for this corridor |
| `rejection_code` | str \| None | ISO 20022 rejection code if already rejected |

**Output** dict keys:

| Key | Type | Description |
|-----|------|-------------|
| `failure_probability` | float | Predicted probability [0, 1] of payment failure |
| `above_threshold` | bool | `True` when `failure_probability > τ*` |
| `shap_top20` | list[dict] | Top-20 SHAP feature contributions |
| `inference_latency_ms` | float | Wall-clock inference time |
| `model_version` | str | Artefact version tag |

## Configuration Parameters

| Parameter | Default | Source |
|-----------|---------|--------|
| `threshold` | `0.152` | `FAILURE_PROBABILITY_THRESHOLD` in `pipeline.py` |
| `graphsage_k_train` | `10` | `GRAPHSAGE_K_TRAIN` in `constants.py` |
| `graphsage_k_infer` | `5` | `GRAPHSAGE_K_INFER` in `constants.py` |
| `asymmetric_bce_alpha` | `0.7` | `ASYMMETRIC_BCE_ALPHA` in `constants.py` |
| `fbeta_beta` | `2` | `FBETA_BETA` in `constants.py` |
| `corridor_embedding_dim` | `128` | `CORRIDOR_EMBEDDING_DIM` in `constants.py` |

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `τ*` | **0.152** | F2-optimal decision threshold — **QUANT sign-off required to change** |
| `GRAPHSAGE_OUTPUT_DIM` | 384 | GraphSAGE output dimension |
| `TABTRANSFORMER_OUTPUT_DIM` | 88 | TabTransformer output dimension |
| `COMBINED_INPUT_DIM` | 472 | `384 + 88` — ensemble head input size |
| `LATENCY_P99_TARGET_MS` | 94 ms | End-to-end SLO for the full pipeline |

## Known Performance Gaps

| Metric | XGBoost Baseline | Synthetic (2K) | Target | Real-World Est. |
|--------|-----------------|----------------|--------|-----------------|
| AUC | 0.739 | **0.9998** | **0.850** | 0.82–0.88 (ARIA) |
| Active features | 33/88 | **78/88** | 88/88 | — |
| P99 latency | ~45 ms (C1 share) | — | ≤ 94 ms (full pipeline) | Within SLO |

Synthetic AUC gap resolved 2026-03-11 via stats enrichment (commit `f38f0dc`).
Real-world target (0.850) requires pilot with anonymised SWIFT data under QUANT sign-off.

## Spec References

- Architecture Spec v1.2 §3 — Algorithm 1 decision threshold
- Architecture Spec v1.2 Appendix A — `GRAPHSAGE_K_TRAIN`, `COMBINED_INPUT_DIM`
- SR 11-7 §4.2 — Model validation requirements for ML classifiers
