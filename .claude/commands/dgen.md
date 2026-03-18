---
description: Run the DGEN production data pipeline. Usage: /dgen [dry-run | 2m | 10m | <n-payments>]
argument-hint: "[dry-run|2m|10m|<n>]"
allowed-tools: Bash
---

Run the DGEN production pipeline from `/Users/tomegah/Documents/PRKT2026` using `~/.pyenv/versions/3.14.3/bin/python3` with `PYTHONPATH=.`.

Interpret `$ARGUMENTS`:

| Argument | Command |
|---|---|
| `dry-run` (or empty) | `python -m lip.dgen.run_production_pipeline --dry-run` (~30s, 10K records to `artifacts/production_data_dryrun/`) |
| `2m` | `python -m lip.dgen.run_production_pipeline --output-dir artifacts/production_data --n-payments 2000000 --n-aml 100000 --seed 42` |
| `10m` | `python -m lip.dgen.run_production_pipeline --output-dir artifacts/production_data_10m --n-payments 10000000 --n-aml 500000 --seed 42` |
| a raw number N | `python -m lip.dgen.run_production_pipeline --output-dir artifacts/production_data_custom --n-payments N --n-aml $(N/20) --seed 42` |

Run in background for anything larger than dry-run (takes minutes). Report: output path, record count, file sizes, and all validation check results (PASS/FAIL per check).

**NEVER commit the artifacts/ directory.** Output is gitignored by design — seed=42 + committed code is the version of record.

After completion, confirm the `payments_synthetic.parquet` is ready for C1 training with `/train`.
