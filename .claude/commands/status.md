---
description: Show a full health dashboard for the LIP project — git state, test count, lint, artifacts, training status.
allowed-tools: Bash, Read
---

Produce a concise health dashboard for the LIP project. Work from `/Users/tomegah/Documents/PRKT2026`. Run the following checks in parallel where possible, then format the output as a clean table/summary.

**Checks to run:**

1. **Git** — `git log --oneline -5` (last 5 commits) + `git status --short` (dirty files)
2. **Tests** — `python3 -m pytest lip/tests/ --ignore=lip/tests/test_e2e_live.py --co -q 2>/dev/null | tail -3` (count without running)
3. **Lint** — `~/.pyenv/versions/3.14.3/bin/python3 -m ruff check lip/ --statistics 2>&1 | tail -5`
4. **Artifacts** — `ls -lh artifacts/production_data_10m/*.parquet artifacts/*.pt artifacts/*.json 2>/dev/null` (what's on disk, sizes)
5. **Training** — check if `artifacts/train_metrics_parquet.json` exists; if so, read and show val_AUC, F2 threshold, ECE
6. **Python env** — confirm `~/.pyenv/versions/3.14.3/bin/python3 -c "import torch, numpy, pandas, lightgbm; print('OK')"` works

Format the dashboard with clear sections. Flag anything that needs attention: lint errors, failing tests, missing artifacts, or stale git state.
