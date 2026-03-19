---
description: Pre-flight check before launching any C1 training run — verifies feature pipeline health, corpus label variance, and smoke-test AUC. Run before ANY training run longer than 5 minutes. Catches in 60s what would otherwise fail silently after 8h.
argument-hint: "[--parquet path/to/file.parquet] [--smoke | --static-only]"
allowed-tools: Bash, Read, Grep
---

## Why this exists

C1 training runs take 60–90 minutes on 1M samples. The following bugs were caught
*after* 8h+ runs instead of before:

1. Corridor stats providing 2/17 keys → 48 of 88 features always zero
2. StandardScaler not called → amount_usd_raw (50M+) dominated all features
3. DGEN sampling uniform across corridors → zero correlation between any feature and label
4. BIC stats key name mismatch (`volume_7d` vs `volume_24h`) → wrong features loaded

This skill runs a 60-second smoke test and static checks that would have caught all four.

## Usage

```bash
# Full check: static + smoke test (recommended, ~90s)
PYTHONPATH=. python3 .claude/skills/verify-c1-readiness/scripts/check_c1_readiness.py \
    --parquet artifacts/production_data_mixed/payments_synthetic.parquet

# Static-only: no training, no parquet needed (~5s)
PYTHONPATH=. python3 .claude/skills/verify-c1-readiness/scripts/check_c1_readiness.py \
    --static-only

# Custom parquet path
PYTHONPATH=. python3 .claude/skills/verify-c1-readiness/scripts/check_c1_readiness.py \
    --parquet artifacts/production_data_10m/payments_synthetic.parquet
```

## Pass criteria

**Static checks (always run):**
- `_s_stats` provides all keys that `features.py` reads from `sender_stats`
- `_r_stats` provides all keys that `features.py` reads from `receiver_stats`
- `_c_stats` provides all keys that `features.py` reads from `corridor_stats`
- StandardScaler is called BEFORE stage5/6/7 in `training_torch.py`
- No zero-variance feature blocs > 5 consecutive features from stats dicts

**Corpus checks (run when parquet provided):**
- Corridor failure rate variance: max/min ratio ≥ 2.0 (at least 2× spread)
- Global label rate: 5%–40% (not extreme imbalance)
- Top-3 features have |corr| > 0.05 with label

**Smoke test (run when parquet provided unless --static-only):**
- 5000 samples, 2 epochs, must complete without error
- Smoke val_AUC > 0.55 (above naive chance)

## When a check fails

1. Print the exact failure with file:line reference
2. Do NOT launch the full training run
3. Fix the issue, re-run this check, then proceed

## Gotchas

- The smoke test uses `--sample 5000 --epochs 2`; a low AUC here is expected (~0.55–0.65)
  but a value of exactly 0.50 or NaN means gradient is not flowing
- `consecutive_failures=0` in all records is acceptable (static parquet has no ordering)
- SWIFT features (vec[83-87]) being always 0 is acceptable (no GPI in synthetic data)
- If StandardScaler is fitted on train but NOT applied to val before AUC scoring,
  val_AUC will be artificially low — check `training_torch.py` for `X_val = scaler.transform(X_val)`
