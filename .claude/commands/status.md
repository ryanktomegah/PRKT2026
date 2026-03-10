# LIP Project Status

Get a comprehensive status report of the LIP project.

## Execution Protocol

1. **Git status**: `git status && git log --oneline -5`
2. **CI health**: `gh run list --limit 5`
3. **Open PRs**: `gh pr list --state open`
4. **Open issues**: `gh issue list --state open`
5. **Test suite**: `PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q --tb=no` (quick pass/fail)
6. **Lint check**: `ruff check lip/ --statistics` (summary only)
7. **Dependabot alerts**: `gh api repos/YESHAPTNT/PRKT2026/dependabot/alerts --jq '.[].security_advisory.summary' 2>/dev/null | head -10`

## Report Format
```
## LIP Status Report — {date}

### Git
- Branch: {branch}
- Last commit: {hash} {message}
- Clean working tree: {yes/no}

### CI
- Latest run: {status} ({workflow}, {duration})
- Open PRs: {count}
- Open issues: {count}

### Tests
- Pass: {n} / Fail: {n} / Skip: {n}
- Coverage: {n}%

### Lint
- Errors: {n}
- Warnings: {n}

### Security
- Dependabot alerts: {count}

### Next Actions
- {prioritized list based on findings}
```
