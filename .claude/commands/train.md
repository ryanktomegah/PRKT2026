---
description: Train C1 on the production parquet. Usage: /train [smoke | full | <sample-size> <epochs>]
argument-hint: "[smoke|full|<sample> <epochs>]"
allowed-tools: Bash, Read
---

Run C1 training from `/Users/tomegah/Documents/PRKT2026` using `~/.pyenv/versions/3.14.3/bin/python3` with `PYTHONPATH=.`.

The parquet is expected at `artifacts/production_data_10m/payments_synthetic.parquet`. If it doesn't exist, tell the user to run `/dgen 10m` first.

Interpret `$ARGUMENTS`:

| Argument | Command |
|---|---|
| `smoke` (or empty) | `python scripts/train_c1_on_parquet.py --sample 5000 --epochs 2` (~60s, validates adapter only) |
| `full` | `python scripts/train_c1_on_parquet.py --sample 1000000 --epochs 20` (production run, ~2h on CPU) |
| `<N> <E>` (two numbers) | `python scripts/train_c1_on_parquet.py --sample N --epochs E` |

Run full training in background. After completion (smoke or full), read `artifacts/train_metrics_parquet.json` and report:
- `val_AUC` — target ≥ 0.85 on held-out test set (actual 2026-03-21: 0.8871)
- `f2_threshold` — optimal decision boundary
- `ece` — calibration error
- `train_elapsed_s` — wall time

**Context:** val_AUC on current 10M corpus is 0.8871 — within honest ceiling of 0.88–0.90. Prior synthetic runs on 2K samples showed inflated 0.9998 due to insufficient feature variation. Current corpus with 20 corridors, 4-tier BIC risk, and temporal clustering produces realistic performance.

Checkpoint saved to `artifacts/c1_model_parquet.pt` — NEVER commit this file.
