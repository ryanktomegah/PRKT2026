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

## C4 LLM Backend — Groq / Qwen3-32b (commit 2477ac2)

### Chosen model: `qwen/qwen3-32b` via Groq API
Benchmarked against llama-3.3-70b-versatile and openai/gpt-oss-120b on the 100-case
negation corpus through the full DisputeClassifier pipeline. qwen3-32b wins on:
- Multilingual FP: 0.0% vs llama's 10.0% — critical for cross-border SWIFT narratives
- Overall FP: 4.0% vs llama's 6.0%
- p95 latency: ~793ms vs llama's ~2375ms
- FN rate: 0.0% — tied with all alternatives

### Qwen3 thinking mode — NEVER use stop tokens
Qwen3-32b emits `<think>...</think>` chain-of-thought tokens before the classification
label. The ONLY correct suppression strategy is:
1. Append `\n/no_think` to the system prompt (documented Qwen3 directive)
2. Strip residual blocks with `re.compile(r"<think>.*?</think>", re.DOTALL)`

**DO NOT add `stop=["\n", " "]` or any stop tokens.** Stop tokens halt generation
*inside* an unclosed `<think>` block (the regex requires `</think>` to match), leaving
the raw `<think>` tag as the entire response → downstream token parser sees `<think>`
as the label → falls through to DISPUTE_POSSIBLE fallback → spurious test failures.
This was the root cause of 5 failing tests in the first integration test run.

### Groq project-level model permissions
Groq API keys are scoped to a project. Models listed in `client.models.list()` may
still return 403 `model_permission_blocked_project` if not enabled in project settings
at console.groq.com/settings/project/limits. Both API keys in use:
- `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` — qwen/qwen3-32b only
- `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` — broader model access

### Model comparison protocol — minimum 100 cases before switching
50-case evaluations produce statistically unreliable FP/FN estimates. In the model
comparison session, llama-3.3-70b showed 0% FP at n=50 but 6% FP at n=100 — the
50-case result was sample luck. Always run the full negation suite (n_per_category=20,
100 total) through `DisputeClassifier` (not raw LLM) before deciding to switch models.

### Integration test run command
```bash
GROQ_API_KEY=gsk_... PYTHONPATH=. python -m pytest lip/tests/test_c4_llm_integration.py -v
```
Tests are `@pytest.mark.slow` and auto-skipped without GROQ_API_KEY. All 17 pass in ~46s.
