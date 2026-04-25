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

**Current RC note (2026-04-24):** the staging RC uses a 5M generated corpus, a 2M training sample, signed supplementary artifacts (`c1_calibrator.pkl`, `c1_scaler.pkl`, `c1_lgbm_parquet.pkl`), and a best chronological OOT AUC of `0.8839` with post-training summary AUC `0.887623`. The March 2026 10M-corpus baseline below is still the canonical historical production reference until the full remote production retrain is restored.

> **Status**: Feature gap **RESOLVED** (2026-03-11). Production model **TRAINED** (2026-03-21, C1v1.1.0). Val AUC = 0.8871 on 10M synthetic corpus (2M sample, 20 corridors).

| Metric | Baseline | Post-Fix (2K, 2026-03-11) | Production (2M/10M, 2026-03-21) | Target |
|--------|----------|---------------------------|--------------------------------|--------|
| Val AUC | 0.739 | 0.9998 (inflated) | **0.8871** | 0.850 |
| Active features | 33/88 | 78/88 | **96** (8 node + 88 tabular) | 88+ |
| ECE | — | — | **0.0687** (isotonic calibration) | < 0.08 |
| F2 score | — | — | **0.6245** (at τ*=0.110) | — |
| P99 latency | ~45 ms | — | Within SLO | ≤ 94 ms |

**Root cause resolved (2026-03-11)**: 55 of 88 features were permanently zero because
`generate_synthetic_dataset` did not populate `sender_stats`, `receiver_stats`, or
`corridor_stats` sub-dicts. `TabularFeatureEngineer.extract()` silently fell back to 0.0
for all three dicts, leaving the model a 33-feature classifier.

**Fix applied** (commit `f38f0dc`):
- `_compute_bic_corridor_stats()` aggregation pass populates per-BIC and per-corridor stats
- Leave-one-out failure rates prevent label leakage
- Per-corridor `failure_rate_multiplier` replaces 3-bucket region_type approach (33 corridors × individual rates)
- Per-BIC `failure_multiplier` gives 35 institutions distinct risk profiles

**Important caveat**: The 2K-sample AUC of 0.9998 was inflated due to insufficient feature
variation in the small synthetic corpus. The production 10M corpus (20 corridors, 200 BICs
with 4-tier risk, temporal clustering) produces realistic performance — Val AUC 0.8871 is
within the honest ceiling of 0.88–0.90 with no data leakage indication.

**Remaining steps for production readiness**:
1. Pilot with real (anonymised) payment failure data under QUANT sign-off
2. ~~Out-of-time (OOT) test set evaluation~~ — **DONE** (chronological 70/15/15 split implemented)
3. ~~Calibration check~~ — **DONE** (isotonic calibration, ECE reduced from 0.1867 to 0.0687)

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
