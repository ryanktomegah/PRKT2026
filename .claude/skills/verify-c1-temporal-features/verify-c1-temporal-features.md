---
description: Verify C1 temporal feature distinctness — checks windowed failure rates (1d/7d/30d) are not duplicated and consecutive_failures is non-zero. Run after modifying train_c1_on_parquet.py.
argument-hint: "[path/to/payments.parquet] [--sample N]"
allowed-tools: Bash, Read
---

Run the C1 temporal feature verification script to confirm that the 8 reclaimed feature slots carry distinct signal.

```bash
PYTHONPATH=. python scripts/check_temporal_features.py $ARGUMENTS
```

After running, report:
1. Whether all 6 correlation checks pass (corr < 0.999 between 1d/7d/30d rates)
2. Whether consecutive_failures has non-zero standard deviation for both sender and receiver
3. The per-feature mean/std/min/max table for vec[64-72]
4. If any check fails: whether DGEN temporal clustering is needed before full training
