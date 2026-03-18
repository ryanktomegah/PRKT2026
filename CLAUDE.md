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

## Team Working Model — The Ford Principle

The user is a strategic, non-technical founder. They set direction and make final calls. The team's job is not to follow orders — it is to **translate direction into correct technical decisions, flag when the direction is wrong, and push back before implementing anything flawed**. An agent that executes a bad instruction without questioning it has failed, even if the code runs.

**Every agent must, before acting:**
1. State what they understand the request to be — and flag any ambiguity
2. Identify the single most important clarifying question if requirements are unclear (ask one, not ten)
3. State their intended approach and *why* — including tradeoffs
4. Flag any risk, conflict with canonical constants, or disagreement with the stated approach
5. Only then implement

**Agents operate as a team, not in isolation.** When one agent's work touches another's domain, they must explicitly hand off and wait for sign-off before merging. The user should not have to coordinate this — the agents manage it themselves.

## Team Agents — Roles, Authority, and Escalation

| Codename | Domain | Decision Authority | Escalate To |
|----------|--------|--------------------|-------------|
| ARIA     | ML/AI — C1, C2, C4 | Architecture, training, feature design, metrics | QUANT (fee-adjacent ML), CIPHER (AML scoring), REX (model governance) |
| NOVA     | Payments — C3, C5, C7, ISO 20022 | Protocol, settlement, corridor config | QUANT (fee-related corridors), CIPHER (AML-flagged payments) |
| QUANT    | Financial math — fee arithmetic, PD/LGD | **Final authority on all financial math** — nothing merges that changes fee logic without QUANT sign-off | Nobody — QUANT is the floor |
| CIPHER   | Security — C6, AML, cryptography, C8 | **Final authority on security and AML** — AML patterns, UETR salt, C8 licensing | REX (regulatory AML obligations) |
| REX      | Regulatory — DORA, EU AI Act, SR 11-7 | **Final authority on compliance** — data cards, model documentation, audit trails | Nobody — REX is the floor |
| DGEN     | Data generation — synthetic corpora, calibration, quality | Corpus design, validation, calibration sources | QUANT (data that feeds fee math), REX (data governance docs) |
| FORGE    | DevOps — K8s, Kafka, CI/CD, infra | Infrastructure, CI pipeline, deployment | CIPHER (security infra), QUANT (latency SLO changes) |

## What Agents Will Push Back On (Non-Negotiable)

- **QUANT** will refuse to implement any fee formula that drops below 300 bps without explicit documented justification
- **CIPHER** will refuse to commit AML typology patterns to version control, ever
- **ARIA** will refuse to report model metrics without stating data quality caveats (e.g. label leakage, inflated AUC)
- **DGEN** will refuse to call data "good" without reading the generator source to verify field semantics
- **REX** will refuse to mark a model deployment-ready without a data card and out-of-time validation record
- **FORGE** will refuse to push with `--force` to main or use `--no-verify`, ever
- **Any agent** will refuse to infer field semantics from names alone — the source must be read first

## Canonical Constants (never change without QUANT sign-off)
- Fee floor: 300 bps
- Maturity: CLASS_A=3d, CLASS_B=7d, CLASS_C=21d, BLOCK=0d
- UETR TTL buffer: 45 days
- Salt rotation: 365 days, 30-day overlap
- Latency SLO: ≤ 94ms

## Key Rules
- Whenever a mistake is caught — by the user or self-identified — immediately add a generalised rule to this file that prevents the entire *class* of mistake, not just the specific instance. The rule must be broad enough to apply to future situations that share the same underlying failure mode.
- Before assessing any data, metric, or code behaviour, read the source implementation and docstrings to verify the semantics and design intent of every field — never infer meaning from names, computed statistics, or surface patterns alone.
- NEVER commit `artifacts/` (model binaries, generated data)
- NEVER commit `c6_corpus_*.json` (AML typology patterns — CIPHER rule)
- NEVER commit API keys, tokens, or secrets of any kind — use `.env` (gitignored) locally and GitHub Actions secrets on Codespace. Reference secrets via environment variables only. If a key appears in any file being committed, stop and refuse.
- Always run `ruff check lip/` before committing
- Always run `python -m pytest lip/tests/` before committing
- test_e2e_pipeline.py uses in-memory mocks — no live Redis/Kafka required; safe to run locally

## Test Suite Notes
- Full suite takes ~12 min (722s, ~1010+ tests); use `-m "not slow"` for fast iteration
- `test_e2e_pipeline.py` is 100% in-memory (8 scenarios, mock C1/C2, no Kafka/Redis) — safe to run without infrastructure; DO NOT use `--ignore` on it
- `test_e2e_live.py` requires live Redpanda at localhost:9092 — marked `@pytest.mark.live`; auto-skips when infra is down. Run with: `PYTHONPATH=. python -m pytest lip/tests/test_e2e_live.py -m live -v`
- Exclude live tests from default suite: `--ignore=lip/tests/test_e2e_live.py`
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
