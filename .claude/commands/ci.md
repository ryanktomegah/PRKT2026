# LIP CI/CD Operations

Monitor and manage GitHub Actions CI pipelines.

## Execution Protocol

1. Check latest CI runs: `gh run list --limit 10`
2. If any failed: `gh run view <run-id> --log-failed`
3. Check PR status: `gh pr list --state open`
4. Report: pass/fail, which jobs failed, suggested fixes

## CI Pipeline (`.github/workflows/ci.yml`)
Jobs:
1. **lint** — `ruff check lip/` (zero errors required)
2. **typecheck** — `mypy lip/` (warnings OK, errors block)
3. **test** — `pytest lip/tests/ --ignore=test_e2e_pipeline.py --cov=lip`
4. Coverage must be ≥ 84%

## Training Pipelines
| Workflow | Trigger | What It Does |
|----------|---------|--------------|
| train_c1.yml | Manual dispatch | Generate C1 corpus + train failure classifier |
| train_c2.yml | Manual dispatch | Generate C2 corpus + train PD model |
| train_c4.yml | Manual dispatch | Generate C4 corpus + train dispute classifier |
| train_c6.yml | Manual dispatch | Generate C6 corpus + train AML model |
| update-sanctions.yml | Weekly cron | Refresh OFAC/EU sanctions lists |

## Other Workflows
| Workflow | Purpose |
|----------|---------|
| claude.yml | Claude PR Assistant |
| claude-code-review.yml | Claude Code Review on PRs |

## Rules
- CI must pass before merging any PR
- If lint fails: fix locally with `ruff check lip/ --fix`
- If tests fail: investigate root cause, don't just skip the test
- Coverage regression below 84% blocks merge
- Concurrency group cancels stale queued runs
