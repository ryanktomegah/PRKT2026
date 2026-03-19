---
description: Analyse a payments parquet corpus for training signal quality — reports per-corridor label rates, feature-label correlations, and class balance. Run after generating any new DGEN corpus and before launching C1 training. Catches zero-signal corpora in under 30s.
argument-hint: "[path/to/payments.parquet] [--sample N]"
allowed-tools: Bash, Read
---

## What this checks

A C1 training corpus must have discriminative signal in the features. Past failures:

- **DGEN uniform sampling bug**: all 12 corridors had exactly 20% label rate →
  `corr(corridor_failure_rate, label) = 0.028 ≈ 0` → AUC stuck at 0.50 after 20 epochs
- **Feature key mismatches**: 48/88 features were structural zeros because stats dicts
  used wrong key names → AUC stuck at 0.50 despite correct labels

This script catches both in < 30 seconds.

## Usage

```bash
# Quick check (200K sample)
PYTHONPATH=. python3 .claude/skills/check-training-signal/scripts/check_corpus_signal.py \
    artifacts/production_data_mixed/payments_synthetic.parquet

# Full corpus check
PYTHONPATH=. python3 .claude/skills/check-training-signal/scripts/check_corpus_signal.py \
    artifacts/production_data_10m/payments_synthetic.parquet --sample 0
```

## What good output looks like

```
Per-corridor failure rates:
  EUR-USD  : 12.7%  ← should vary
  GBP-USD  : 33.9%  ← good spread
  ...
  Ratio max/min: 2.7×  ✓ (need ≥ 2.0×)

Top feature correlations with label:
  corridor_failure_rate_raw  : +0.182  ✓
  sending_bic_failure_rate   : +0.091  ✓
  amount_usd                 : -0.031

Class balance: 12.1% positive — acceptable
```

## Red flags

- Max/min corridor failure rate ratio < 2.0× → DGEN `_CORRIDOR_FAILURE_WEIGHTS` not applied
- Top feature correlation < 0.03 → no signal, training will plateau at AUC ≈ 0.50
- Corridor rates all identical → uniform sampling bug
- Label rate > 45% or < 3% → corpus generation issue

## After this check

If signal looks good, run `/verify-c1-readiness` for the full pre-flight (including smoke test).
