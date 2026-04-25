# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LIP (Liquidity Intelligence Platform) — real-time payment failure detection and automated bridge lending for correspondent banks. ISO 20022 native, 94ms p99 SLO, patent-pending. Built by BPI Technology.

The founder is non-technical and strategic. Make architecture, design, code-review, and tooling decisions yourself. Escalate only business/strategic questions: pricing, patent scope, pilot strategy, canonical constants, anything touching the IP/RBC situation.

## Daily commands

| What | Command |
|------|---------|
| Install (dev) | `pip install -e "lip/[all]"` |
| Lint (must be zero on touched files) | `ruff check lip/` |
| Type check | `mypy lip/` |
| Fast tests (~3 min, excludes slow ML) | `PYTHONPATH=. python -m pytest lip/tests/ -m "not slow"` |
| Full tests (~12 min) | `PYTHONPATH=. python -m pytest lip/tests/` |
| Single file | `PYTHONPATH=. python -m pytest lip/tests/test_<name>.py -v` |
| Local infra (Redpanda + Redis) | `docker compose up -d && bash scripts/init_topics.sh` |
| Training entry point | `PYTHONPATH=. python lip/train_all.py --help` |
| Staging deploy (local) | `./scripts/deploy_staging_self_hosted.sh --profile <p>` where `<p>` ∈ {`local-core`, `local-full-non-gpu`, `gpu-full`, `analytics`, `streaming-flink`} (canonical: `scripts/deploy_staging_self_hosted.sh:8`) |

`PYTHONPATH=.` is required from the repo root for imports to resolve. Long pytest runs are auto-backgrounded by the Bash tool — wait with `TaskOutput(block=True)`.

## Architecture

**Pipeline** (synchronous, ≤94ms): `pacs.002 → C5 → C6 → C1 → C4 → C2 → C7` produces a `PipelineResult` with `outcome ∈ {OFFERED, DISPUTE_BLOCKED, AML_BLOCKED, BELOW_THRESHOLD, HALT, DECLINED, PENDING_HUMAN_REVIEW, RETRY_BLOCKED, COMPLIANCE_HOLD, AML_CHECK_UNAVAILABLE, SYSTEM_ERROR}`.

**Lifecycle** (async, post-pipeline): `OFFERED` is **not** funded exposure. `OFFERED → FUNDED` requires an **explicit ELO acceptance callback** — C3 activates and exposure begins only on that transition. Source: `lip/pipeline_result.py:30-32`, `lip/common/state_machines.py:123-128`.

```
MONITORING → FAILURE_DETECTED → BRIDGE_OFFERED ─┬→ OFFER_DECLINED (terminal)
                                                ├→ OFFER_EXPIRED  (terminal)
                                                └→ FUNDED ─┬→ REPAID / BUFFER_REPAID (terminal)
                                                           ├→ DEFAULTED              (terminal)
                                                           ├→ REPAYMENT_PENDING      (transient)
                                                           └→ CANCELLATION_ALERT     (camt.056/pacs.004 recall)
```

The pipeline short-circuits to a terminal outcome on dispute / AML / compliance hold; those payments never reach `BRIDGE_OFFERED`.

| Component | Purpose | Stack |
|-----------|---------|-------|
| C1 | Failure classifier | GraphSAGE + TabTransformer + LightGBM (PyTorch) |
| C2 | PD model + fee pricing | Merton/KMV + Damodaran + Altman Z' (LightGBM) |
| C3 | Repayment FSM (post-FUNDED) | UETR polling + settlement monitoring (Rust via PyO3) |
| C4 | Dispute classifier | Qwen3-32B via Groq with negation-aware prefilter |
| C5 | Streaming ingestion | Kafka + ISO 20022 normalisation (Go consumer) |
| C6 | AML / velocity | Sanctions + velocity counters (Rust via PyO3) |
| C7 | Execution agent (offer generation) | Loan execution + kill switch (Go gRPC router) |
| C8 | License manager | HMAC-SHA256 token enforcement (cross-cutting) |
| P5 / P10 / P12 | Cascade engine, regulatory data product, federated learning | Patent extensions |

Production package is `lip/`. FastAPI surface is `lip/api/`. Schemas/constants/state machines in `lip/common/`. Mixed-language subsystems are colocated with their Python wrappers (`lip/c3/rust_state_machine/`, `lip/c5_streaming/go_consumer/`, etc.).

For depth: `README.md`, `docs/INDEX.md`, `docs/engineering/architecture.md`.

## Non-negotiables

These never relax — even with explicit instruction to do so, push back and explain why.

1. **BLOCK-class payments are NEVER bridged.** Two subsets, both BLOCK-class in `lip/c3_repayment_engine/rejection_taxonomy.py` and listed in `lip/common/block_codes.json` (canonical):
   - **EPG-19 compliance hold** (8 codes): `DNOR, CNOR, RR01, RR02, RR03, RR04, AG01, LEGL`. Outcome must be `COMPLIANCE_HOLD` with `compliance_hold=True` on `PipelineResult` (EPG-09/10).
   - **Dispute / fraud** (4 codes): `DISP, DUPL, FRAD, FRAU`. Outcome `DISPUTE_BLOCKED`.
   - `MS03` and `NARR` are CLASS_B (systemic delays, 7-day maturity), **not** BLOCK — they may be bridged. The narrative point that banks may use ambiguous codes like MS03/NARR to comply with FATF R.21 tipping-off rules is a separate compliance-visibility *limit*, not a code-classification rule.
   Defense-in-depth: Layer 1 in `rejection_taxonomy.py` (BLOCK class, pipeline short-circuit) + Layer 2 in `agent.py` (`_COMPLIANCE_HOLD_CODES`, C7 gate). Bypassing the EPG-19 subset triggers AMLD6 Art.10 criminal liability for the bank. Source: EPG-19, `lip/common/block_codes.json`.

2. **Fee floor is 300 bps.** No code path may produce a fee below this. Located: `lip/common/constants.py`. Below this, the math doesn't work. Lower floors require a full pricing redesign, not a constant change.

3. **AML typology patterns NEVER commit.** `c6_corpus_*.json` is gitignored — generate fresh via `PYTHONPATH=. python -m lip.dgen.generate_all`. Patterns in version control are a circumvention roadmap.

4. **Governing law derives from BIC, not currency.** `bic_to_jurisdiction()` in `lip/common/governing_law.py` uses BIC chars 4-5. `_build_loan_offer` in `agent.py` uses BIC-first with currency fallback. Currency is wrong for cross-border correspondent banking. Source: EPG-14.

5. **Patent claim language NEVER mentions** `AML`, `SAR`, `OFAC`, `SDN`, "compliance investigation", "tipping-off", "suspicious activity", or "PEP". Use neutral terms: classification gate, hold type discriminator, bridgeability flag, procedural hold, investigatory hold. **Never enumerate the BLOCK code list in any claim** — it is a circumvention roadmap. Claim the existence of the gate, not its contents. Source: EPG-20/21.

6. **NEVER fabricate or curate pre-RBC-employment evidence for IP ownership.** Founder confirmed 2026-04-18 that LIP was conceived during RBC employment. Any artefact arguing otherwise (back-dated notes, curated chat exports, retimed commits, "After leaving RBC..." framing) is fraud and converts a contractual problem into a criminal one. **Halt all patent filing and RBC outreach until counsel opines** on (a) clause enforceability under BC employment law, (b) unrelated-to-business carve-out, and (c) waiver/license-back path. The honest path forward is counsel-led.

7. **NEVER skip hooks** (`--no-verify`, `--no-gpg-sign`) or **force-push to main**. Diagnose root causes; don't bypass. If a pre-commit hook fails, fix the underlying issue and create a NEW commit (the original commit didn't happen, so `--amend` would modify the previous commit).

8. **NEVER commit secrets.** `.env`, `.secrets/`, license tokens, HMAC keys, API keys, the GH PAT — all gitignored. If a key appears in any file being committed, stop and refuse.

9. **Bank-fee shares ALWAYS decompose into capital return + distribution premium.** Phase 2 = 30% capital return + 30% distribution premium; Phase 3 = 0% capital return + 25% distribution premium. Never report a single "bank share %" without the breakdown — it primes Phase 3 negotiation traps.

10. **Phase 1 income is "royalty"; Phase 2/3 income is "lending revenue".** Misclassifying creates Canadian tax problems (SR&ED, HST, income tax category). Use income-type-neutral names like `bpi_fee_share` in code and schemas; reserve `royalty` for Phase 1 / Licensor scope only.

## Canonical constants

Change requires explicit founder sign-off — these are business decisions, not technical ones.

| Constant | Value | Location |
|----------|-------|----------|
| Fee floor | 300 bps | `lip/common/constants.py` |
| Maturity CLASS_A | 3 days | same |
| Maturity CLASS_B | 7 days | same |
| Maturity CLASS_C | 21 days | same |
| Maturity BLOCK | 0 days | same |
| C1 decision threshold (τ★) | 0.110 | same |
| Latency SLO | ≤ 94ms | same |
| UETR TTL buffer | 45 days | same |
| Salt rotation | 365 days, 30-day overlap | same |
| AML caps (`aml_dollar_cap_usd`, `aml_count_cap`) | default sentinel `_AML_CAP_UNSET` (-1) — must be set explicitly per-token at boot; `LicenseBootValidator` rejects tokens with the sentinel. `0` means "unlimited" (valid, explicit); `-1` means "unset" (rejected). | EPG-16/17, B3-03 fix in `lip/c8_license_manager/license_token.py:42-87` |

Citation rule: when updating measured values in `constants.py`, cite commit hash + dataset scope in the comment (see `DISPUTE_FN_CURRENT` for the format).

## How to work in this codebase

**Before acting:**

1. State your understanding of the request and flag any ambiguity.
2. State your intended approach and the main tradeoff.
3. Push back if the direction is technically wrong — even when the founder is the one suggesting it. An agent that executes a flawed instruction without questioning it has failed, even if the code runs.
4. Then implement.

**Match ceremony to risk — do not gold-plate trivial work, do not under-think sensitive work.**

| Tier | Examples | Process |
|------|----------|---------|
| **0 — Trivial** | Doc moves, branch hygiene, root cleanup, comment fixes, README updates, dependency-free renames | Just do it. Commit directly to main. No CI, no PR. |
| **1 — Routine** | Refactors, dep pin tweaks, infra config, new tests for existing code, lint fixes, docs with new claims | `ruff check` on touched files. Commit to main if green. PR optional. |
| **2 — Substantive** | New features, schema changes, API surface changes, model retraining, new components, anything with a public surface | `codex/<topic>` branch, draft PR, run relevant `pytest` subset, paste verification commands in PR body. |
| **3 — Sensitive** | Fee math, AML/sanctions code, IP/patent text, model architecture, canonical constants, anything in `lip/c2/fee.py`, `lip/c2/cascade*`, `lip/c6/`, `lip/c8/`, `lip/common/constants.py`, `lip/common/governing_law.py`, or any model-deployment path | Re-read the non-negotiables. Document reasoning in PR. Run full `pytest`. State explicitly which non-negotiable applies. Out-of-time validation record + data card required for model deployments (REX). |

**Field semantics rule:** Before assessing any data, metric, or code behaviour — **or summarising system behaviour in any document, including this one** — read the source implementation and docstrings to verify the semantics of every field, state, or outcome. Never infer meaning from field names, prior summaries, README descriptions, or surface patterns alone.
- Origin 2026-03-17: `is_permanent_failure.mean()` was misread as "failure rate" when the field means "rejection is permanent vs recoverable" — produced a wrong quality report.
- Origin 2026-04-25: CLAUDE.md was authored with a 4-element pipeline-outcome list and an `OFFER → C3` arrow, both derived from the README's surface description. Source (`pipeline_result.py`, `state_machines.py`) defines 12 outcome strings and gates `OFFERED → FUNDED` on an explicit ELO acceptance callback. **Even authoring this file is not exempt from the rule.**

**Mistake → rule generalization:** When you make a mistake — yours or you spot one in the code — add a generalized rule to this file that prevents the *class* of error, not just the specific instance. Always err broader. ("I misread `is_permanent_failure`" becomes "verify field semantics before drawing statistical conclusions" — never "remember to check `is_permanent_failure`".)

**Verification before completion:** Don't claim "fixed", "passing", or "done" without running the verification commands and confirming output. Evidence before assertions.

**Sprint discipline:** `git push` at the end of each session. Commits are not visible on GitHub until pushed. The founder watches the contribution graph.

## Codebase quirks (real gotchas)

- **C4 `MockLLMBackend` has no negation awareness** (`lip/c4_dispute_classifier/model.py:88-93`) — it re-fires on "fraud"/"dispute" after prefilter passes. Use **prefilter-only FP rate** (not full-pipeline accuracy) as the C4 quality metric. Negation suite at `lip/c4_dispute_classifier/negation.py` generates 500 cases (5 categories × `n_per_category=100`, drawn from ~20 base templates per category and cycled).

- **C4 Qwen3 backend rules:** Don't add `stop=["\n"," "]` to Groq calls — breaks generation inside `<think>` blocks. Use `/no_think` in system prompt + regex strip. Groq models in `models.list()` can still 403 — verify project permissions at console.groq.com. Never conclude on FP/FN rates from <100 cases. Don't switch model from `qwen/qwen3-32b` without a full 100-case negation corpus run.

- **PyTorch + LightGBM deadlock on macOS** in the same pytest process. Any test file using both must include a session-scoped autouse fixture: `torch.set_num_threads(1); torch.set_num_interop_threads(1)`.

- **PyTorch pin:** `torch>=2.6.0`. `torch==2.2.0` is unavailable on the CPU wheel index.

- **`test_e2e_pipeline.py` is fully in-memory** (8 mock scenarios, no Kafka/Redis required). Safe to run without infra. Do NOT `--ignore` it.

- **`test_e2e_live.py` requires live Redpanda at localhost:9092** — marked `@pytest.mark.live`, auto-skips when infra is down (the marker handles skipping; there is no default `--ignore` in `pyproject.toml addopts`). Run explicitly with infra up: `PYTHONPATH=. python -m pytest lip/tests/test_e2e_live.py -m live -v`. To exclude from a default run when infra is partially up, add `--ignore=lip/tests/test_e2e_live.py` per `AGENTS.md`.

- **`test_slo_p99_94ms`** in `test_c1_classifier.py` is timing-flaky — fails under CPU load, passes in isolation. Not a regression signal.

- **CLASS_B label is "systemic/processing delay", NOT "compliance/AML hold".** Compliance holds are BLOCK class and are never bridged. The 53.58h CLASS_B settlement value cannot be used to calibrate compliance-hold resolution times.

- **Trained model binaries are committed.** `artifacts/c1_trained/` and `artifacts/c2_trained/` (~8MB total, HMAC-signed sidecars) are runtime code dependencies — Dockerfiles COPY them, tests assert on them, production loads via `LIP_C1_MODEL_DIR` and `LIP_C2_MODEL_PATH`. Training corpora and intermediate outputs (`training_corpus_*/`, `production_data_*/`, `intermediate_*/`, `synthetic/`) stay gitignored — regenerable from seed.

- **MLflow was removed (T2.5, 2026-04-12)** — eliminated a 13-CVE Dependabot surface. Don't reintroduce.

- **C2 model load path:** runtime pipeline loads C2 via `LIP_C2_MODEL_PATH` + signed pickle through `secure_pickle`. Never load raw pickle from `artifacts/`. Generate fresh signed artifact: `PYTHONPATH=. python scripts/generate_c2_artifact.py --hmac-key-file .secrets/c2_model_hmac_key`.

- **Real-pipeline activation:** `LIP_API_ENABLE_REAL_PIPELINE=true` switches `lip-api` from stub to the real runtime pipeline. Staging defaults: see `docs/operations/deployment.md`.

## GitHub auth

`gh` PAT at `.secrets/github_token` (gitignored, 600 perms, scopes: `repo` + `workflow` + `read:org`). Load with `gh auth login --with-token < .secrets/github_token`.

**Known issue (Darwin 25.x):** `gh` API calls may fail with `tls: failed to verify certificate: x509: OSStatus -26276` on this machine. Root cause is macOS Security framework cgo path; affects all Go binaries doing TLS via Security framework, not just gh. `git` push/pull works fine (uses libcurl). Out-of-session fix: macOS update or keychain reset. In-session workaround: use `git` directly.

## References

- `README.md` — project overview, architecture diagram, quick start, repository layout
- `AGENTS.md` — repository contributor guidelines (build, style, commits, PRs)
- `docs/INDEX.md` — role-based reading paths (engineer, compliance, counsel, pilot, investor, DevOps)
- `docs/engineering/architecture.md` — Algorithm 1, FSMs, Redis/Kafka schemas, patent mapping
- `docs/engineering/developer-guide.md` — full setup, test commands, contribution guidelines
- `docs/legal/decisions/` — EPG decision register (EPG-04 through EPG-21, with rationale)
- `docs/legal/compliance.md` — SR 11-7, EU AI Act, DORA, AML, GDPR mappings
- `docs/models/` — C1/C2 model cards + training data cards (EU AI Act Art.10)
- `docs/operations/deployment.md` — staging profiles, env vars, model-source verification
