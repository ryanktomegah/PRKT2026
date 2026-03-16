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

> **Status**: Synthetic-data AUC gap **RESOLVED** (2026-03-11). Real-world AUC estimated 0.82–0.88.

| Metric | Baseline | Synthetic AUC (2K samples) | Target | Real-World Estimate |
|--------|----------|---------------------------|--------|---------------------|
| AUC (ROC) | 0.739 | **0.9998** | **0.850** | 0.82–0.88 (ARIA est.) |
| Active features | 33/88 | **78/88** | 88/88 | — |
| P99 latency | ~45 ms | — | ≤ 94 ms (full pipeline) | Within SLO |

**Root cause resolved (2026-03-11)**: 55 of 88 features were permanently zero because
`generate_synthetic_dataset` did not populate `sender_stats`, `receiver_stats`, or
`corridor_stats` sub-dicts. `TabularFeatureEngineer.extract()` silently fell back to 0.0
for all three dicts, leaving the model a 33-feature classifier.

**Fix applied** (commit `f38f0dc`):
- `_compute_bic_corridor_stats()` aggregation pass populates per-BIC and per-corridor stats
- Leave-one-out failure rates prevent label leakage
- Per-corridor `failure_rate_multiplier` replaces 3-bucket region_type approach (33 corridors × individual rates)
- Per-BIC `failure_multiplier` gives 35 institutions distinct risk profiles

**Important caveat**: The synthetic AUC of 0.9998 is achievable because labels are
deterministically generated from features with zero label noise. Real-world AUC will be lower
(estimated 0.82–0.88) due to irreducible noise in live SWIFT streams. The improvement
demonstrates that the model can now *use* all 88 features correctly — the signal quality on
real data will determine the production ceiling.

**Remaining steps for production readiness**:
1. Pilot with real (anonymised) payment failure data under QUANT sign-off
2. Out-of-time (OOT) test set evaluation (train/val/test AUC gap must be ≤ 3%)
3. Calibration check (Brier score, reliability diagram)

Constants in `constants.py` (do not change without QUANT sign-off):
```python
ML_BASELINE_AUC = Decimal("0.739")  # historical XGBoost baseline
ML_TARGET_AUC   = Decimal("0.850")  # production target (real-world data)
```

## C4 Dispute Classifier — Performance (updated 2026-03-16)

| Backend | FN rate | FP rate | Notes |
|---------|---------|---------|-------|
| MockLLMBackend (keyword) | 47.2% | 0.1% | Baseline — no negation awareness |
| **qwen/qwen3-32b via Groq** | **0.0%** | **4.0%** | Production backend (commit 2477ac2) |

**LLM backend is integrated**: `qwen/qwen3-32b` via Groq OpenAI-compatible API.
Measured on 100-case negation corpus (20 per category) through full `DisputeClassifier`
pipeline (prefilter + LLM). Multilingual FP = 0.0% (FR/DE/ES/AR narratives).

**Remaining gap**: `conditional_negation` category accuracy = 10% — the LLM conservatively
treats "unless X, this becomes a dispute" as DISPUTE_CONFIRMED. This is acceptable for
LIP's risk posture (false alarm is safer than a missed dispute).

Constants:
```python
DISPUTE_FN_CURRENT = Decimal("0.0000")  # LLM=qwen/qwen3-32b n=100 (2026-03-16)
DISPUTE_FN_TARGET  = Decimal("0.02")    # target false-negative rate
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
