# LIP Project — Claude Code Configuration

## GitHub CLI Access
`gh` is installed. Authentication requires `GH_TOKEN` environment variable or
`gh auth login` with a Personal Access Token scoped to `repo` + `workflow` + `read:org`.

To authenticate once:
```bash
gh auth login --with-token <<< "ghp_your_token_here"
```

After auth, Claude can:
- Check CI run status: `gh run list --repo ryanktomegah/PRKT2026`
- View failed logs: `gh run view <run-id> --log-failed`
- List open issues: `gh issue list`
- Create PRs: `gh pr create`

## Repository
- Repo: `ryanktomegah/PRKT2026`
- Active branch: `claude/consolidate-file-updates-CIPGP`
- Package root: `lip/` (pyproject.toml lives here)
- Tests: `lip/tests/` — run with `python -m pytest lip/tests/`
- Lint: `ruff check lip/` — must be zero errors before commit
- PYTHONPATH must be set to repo root for imports to resolve

## Team Agents
| Codename | Domain |
|----------|--------|
| ARIA     | ML/AI — C1, C2, C4 training |
| NOVA     | Payments — C3, C5, C7, ISO 20022 |
| REX      | Regulatory — DORA, EU AI Act, SR 11-7 |
| CIPHER   | Security — C6, AML, cryptography |
| QUANT    | Financial math — fee arithmetic, PD/LGD |
| FORGE    | DevOps — K8s, Kafka, CI/CD |
| DGEN     | Data generation — synthetic corpora for all components |

## Canonical Constants (never change without QUANT sign-off)
- Fee floor: 300 bps
- Maturity: CLASS_A=3d, CLASS_B=7d, CLASS_C=21d, BLOCK=0d
- UETR TTL buffer: 45 days
- Salt rotation: 365 days, 30-day overlap
- Latency SLO: ≤ 94ms

## Key Rules
- NEVER commit `artifacts/` (model binaries, generated data)
- NEVER commit `c6_corpus_*.json` (AML typology patterns — CIPHER rule)
- Always run `ruff check lip/` before committing
- Always run `python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py` before committing
- test_e2e_pipeline.py requires live Redis/Kafka — excluded from local CI
