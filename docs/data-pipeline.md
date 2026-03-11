# LIP Data Pipeline Reference

## Synthetic Data Generators (`lip/dgen/`)

LIP ships synthetic data generators for all components that require training data.

```bash
# Generate all synthetic datasets
PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic

# Individual generators
PYTHONPATH=. python -m lip.dgen.c1_generator --output-dir artifacts/synthetic
PYTHONPATH=. python -m lip.dgen.c2_generator --output-dir artifacts/synthetic
PYTHONPATH=. python -m lip.dgen.c4_generator --output-dir artifacts/synthetic
PYTHONPATH=. python -m lip.dgen.c6_generator --output-dir artifacts/synthetic
```

Generated files are written to `artifacts/synthetic/` which is **gitignored** — never commit training artefacts.

## Model Training Commands

```bash
# Train all models (requires generated data in artifacts/synthetic)
PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic

# Train individual components
PYTHONPATH=. python lip/c1_failure_classifier/train.py --data-dir artifacts/synthetic
PYTHONPATH=. python lip/c2_pd_model/train.py --data-dir artifacts/synthetic
PYTHONPATH=. python lip/c4_dispute_classifier/train.py --data-dir artifacts/synthetic
PYTHONPATH=. python lip/c6_aml_velocity/anomaly.py --fit  # fit anomaly detector
```

## C1 Failure Classifier — Performance Gap

> **Status**: Known gap under active improvement.

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| AUC (ROC) | **0.739** | **0.850** | −0.111 |
| P99 latency | ~45 ms | ≤ 94 ms (full pipeline) | Within SLO |

The test `test_trained_model_auc_beats_random` currently fails because the synthetic training data does not produce sufficient signal for the ensemble (GraphSAGE + TabTransformer + LightGBM) to reach the target AUC. This is a **known training data quality gap**, not a code defect.

**Root cause**: Synthetic payment data lacks the complex temporal patterns and corridor-specific failure correlations present in real SWIFT payment streams.

**Resolution path**:
1. Increase synthetic data volume (current: ~10K, target: ~1M events)
2. Tune GraphSAGE neighbourhood sampling (`GRAPHSAGE_K_TRAIN`, `GRAPHSAGE_K_INFER`)
3. Hyperparameter sweep on asymmetric BCE loss (`ASYMMETRIC_BCE_ALPHA = 0.7`)
4. Pilot with real (anonymised) payment failure data under QUANT sign-off

Constants in `constants.py`:
```python
ML_BASELINE_AUC = Decimal("0.739")  # current
ML_TARGET_AUC   = Decimal("0.850")  # target
```

## C4 Dispute Classifier — Performance Gap

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| False-negative rate | **8%** | **2%** | −6 percentage points |

**Root cause**: Keyword pre-filter misses idiomatic and non-English dispute language. LLM backend not yet integrated.

**Resolution path**:
1. Integrate LLM backend (planned: Claude or GPT-4 via `HybridAIService`)
2. Expand multilingual negation patterns in `NegationHandler`
3. Add adversarial dispute examples to training corpus

Constants:
```python
DISPUTE_FN_CURRENT = Decimal("0.08")  # 8% current FN rate
DISPUTE_FN_TARGET  = Decimal("0.02")  # 2% target FN rate
```

## Model Artefact Policy

| Rule | Detail |
|------|--------|
| **Gitignore** | `artifacts/` is always gitignored — never commit model weights |
| **Versioning** | All artefacts tagged with a version string stored in `model_version` field |
| **Registry** | Production artefacts stored in the configured model registry (S3 or GCS) |
| **Validation** | Every deployed artefact must pass the component's test suite before promotion |

## C6 Anomaly Detector Fitting

The `AnomalyDetector` must be fitted on historical transaction data before use in production:

```python
from lip.c6_aml_velocity.anomaly import AnomalyDetector

detector = AnomalyDetector(contamination=0.01)  # 1% contamination rate
detector.fit(historical_transactions)  # list of transaction dicts

# Persist the fitted model
import joblib
joblib.dump(detector, "artifacts/c6_anomaly_detector.joblib")
```

When `fit()` has not been called, `predict()` returns `is_anomaly=False` with a warning log — this is safe for boot but must be corrected before production use.

## Training Data — Never Commit

The following patterns are gitignored and must **never** appear in git history:

```gitignore
artifacts/
c6_corpus_*.json    # AML training corpus — regulatory sensitivity
*.joblib            # Fitted model artefacts
*.pkl               # Pickle artefacts
```
