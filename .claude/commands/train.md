# LIP Model Training

Train ML models for LIP components. Requires synthetic data to be generated first (run /dgen).

## Execution Protocol

1. Verify `artifacts/synthetic/` exists and contains valid corpora
2. Set `PYTHONPATH=.`
3. Train specific component or all:
   - All: `PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic`
   - C1 only: `PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic --components c1`
   - C2 only: `PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic --components c2`
   - C6 only: `PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic --components c6`
4. Report: model metrics (AUC, precision, recall), training time, artifacts saved

## Model Performance Targets
| Component | Metric | Current | Target |
|-----------|--------|---------|--------|
| C1 Failure Classifier | AUC | 0.739 | 0.850 |
| C1 Failure Classifier | F2-score | — | ≥ 0.80 |
| C2 PD Model | RMSE | — | ≤ 0.02 |
| C4 Dispute | FN rate | 0.08 | 0.02 |
| C6 AML | Precision | — | ≥ 0.95 |

## Canonical Constants (QUANT sign-off required to change)
- Failure threshold τ*: 0.152
- F-beta β: 2 (recall-weighted)
- Asymmetric BCE α: 0.7
- Fee floor: 300 bps annualized
- Latency SLO: ≤ 94ms

## Rules
- NEVER commit model artifacts to git
- Always validate model against canonical constants after training
- If AUC drops below 0.739 baseline, investigate data quality first
- Training requires `lip[ml]` extras installed
- Run from repo root: `/Users/halil/PRKT2026`
