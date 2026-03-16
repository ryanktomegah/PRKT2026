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
- Active branch: `main`
- Package root: `lip/` (pyproject.toml lives here)
- Tests: `lip/tests/` — run with `python -m pytest lip/tests/`
- Full suite ~3 min; use `-m "not slow"` for iteration
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
- Always run `python -m pytest lip/tests/` before committing
- test_e2e_pipeline.py uses in-memory mocks — no live Redis/Kafka required; safe to run locally

## Test Suite Notes
- Full suite (excl. e2e) takes ~12 min (722s, ~980 tests); exclude e2e for speed: `--ignore=lip/tests/test_e2e_pipeline.py`
- `test_slo_p99_94ms` (test_c1_classifier.py) is a FLAKY TIMING test — fails under CPU load, passes in isolation; not a regression signal
- Long pytest runs are auto-backgrounded by the Bash tool; wait with `TaskOutput(block=True, timeout=600000)` and kill competing runs with `TaskStop` before starting a new one

## PyTorch / ML Dependencies
- `torch==2.2.0` unavailable on CPU wheel index; minimum available is 2.6.0 — pin as `torch>=2.6.0`
- LightGBM (OpenMP) + PyTorch BLAS deadlock on macOS in the same pytest process; any test file using both must include a session-scoped autouse fixture: `torch.set_num_threads(1); torch.set_num_interop_threads(1)`

## C4 Dispute Classifier Notes
- `MockLLMBackend` (model.py:87-93) has no negation awareness — pure keyword match.
  After prefilter passes through, MockLLMBackend re-fires on "fraud"/"dispute" etc.
  Use **prefilter-only FP rate** (not full-pipeline accuracy) as the C4 Step 2x metric.
- Negation test suite: `lip/c4_dispute_classifier/negation.py` — 500 cases, 5 categories,
  20 templates per category cycled. Run via inline `PYTHONPATH=. python3` snippet.
- Prefilter FP rate after Step 2a (commit 3808a74): 4% (was ~62%).
  FN rate: 1% on negation suite; not yet validated on full synthetic corpus.
- When updating measured values in `lip/common/constants.py`, cite commit hash +
  dataset scope in the comment (see DISPUTE_FN_CURRENT for example).

## C4 LLM Backend Rules (learned 2026-03-16)
- Model: `qwen/qwen3-32b` via Groq. Do NOT switch without a full 100-case negation corpus run.
- Never add `stop=["\n"," "]` to Qwen3 calls — breaks generation inside `<think>` blocks. Use `/no_think` in system prompt + regex strip only.
- Groq models appearing in `models.list()` can still 403 — check project permissions at console.groq.com before assuming a model is available.
- Always benchmark model changes through the full `DisputeClassifier` pipeline (prefilter + LLM), not raw LLM calls — the prefilter masks FN differences.
- Never conclude on FP/FN rates from fewer than 100 cases — small samples produce misleading zeros.
