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

## Documentation Structure

Docs are organised by audience under `docs/`. When you need a file, look here:

| Audience | Directory | Key Files |
|----------|-----------|-----------|
| Engineers | `docs/engineering/` | architecture.md, developer-guide.md, api-reference.md, specs/, blueprints/, codebase/ |
| Legal / Compliance | `docs/legal/` | compliance.md, patent/, decisions/ (EPG register), governance/ |
| Business | `docs/business/` | CLIENT_PERSPECTIVE_ANALYSIS.md, LIP_COMPLETE_NARRATIVE.md, bank-pilot/, fundraising/ |
| Operations | `docs/operations/` | deployment.md, Operational-Playbook-v2.1.md |
| ML Models | `docs/models/` | c1-model-card.md, c2-model-card.md, c1-training-data-card.md |
| All Roles | `docs/INDEX.md` | Role-based reading paths (banker, engineer, compliance, counsel) |

## Execution Protocol (Mandatory)
- Follow `docs/engineering/default-execution-protocol.md` for every task.
- Required defaults: `codex/*` branch workflow, plan/design before implementation,
  commit+push at task completion, and draft PR by default with test evidence.

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

## Lens Activation — When to Invoke Each Agent

**Default: auto-approve.** Invoke a lens ONLY when the change touches its trigger paths or concerns below. Everything else proceeds without a lens review. The Ford Principle still applies universally (state understanding, flag ambiguity, explain approach), but a full role invocation is not required for work outside a lens's domain.

This cuts ceremony while preserving veto power. The Non-Negotiable rules in the next section remain absolute regardless of trigger.

| Lens | Invoke when changes touch… | Auto-approve when… |
|------|---------------------------|--------------------|
| QUANT  | `lip/c2_pd_model/fee.py`, `lip/c2_pd_model/cascade*`, any fee/PD/LGD arithmetic, canonical fee constants, warehouse eligibility logic, latency SLO | Docs referencing QUANT constants without changing them; tests that exercise existing invariants; unrelated code paths |
| CIPHER | `lip/c6_*`, `lip/c8_*`, `lip/common/aml*`, crypto primitives, salt/key rotation, UETR salting, auth, licensing tokens, any file matching `c6_corpus_*` | Changes with no path match above and no new network/secret handling |
| REX    | Model deployment code, data cards (`docs/models/`), model cards, audit-trail logic, `rejection_taxonomy.py`, compliance-hold gate in `agent.py`, `docs/legal/decisions/` | Internal refactors that ship no model and touch no compliance-coded logic |
| ARIA   | `lip/c1_*`, `lip/c2_*`, `lip/c4_*` model architecture, training loops, feature engineering, metric reporting | Infra, docs, and tests that do not make a new model-quality claim |
| NOVA   | `lip/c3_*`, `lip/c5_*`, `lip/c7_*`, ISO 20022 message handling, BIC routing, `governing_law.py`, settlement/corridor config | Non-payment paths |
| DGEN   | `synthetic_banks.py`, synthetic corpus generators, calibration source changes, quality/distribution claims on generated data | Consuming synthetic data without asserting its quality |
| FORGE  | `.github/workflows/`, `Dockerfile*`, `pyproject.toml` dep changes, `requirements*.txt`, K8s manifests, deployment scripts | Application code that does not change CI, deps, or deployment |

**Single-lens heuristic.** When the work clearly touches exactly one lens, invoke only that lens. Cross-lens invocation (e.g., QUANT + CIPHER together) is required only when the escalation column in the table above actually applies — e.g., ARIA touching fee-adjacent ML must hand off to QUANT; NOVA touching AML-flagged payments must hand off to CIPHER.

**Hand-off rule unchanged.** Cross-domain work still hands off explicitly rather than going silent. The streamlining is in when to start the review, not in whether to hand off once one is underway.

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
- AML caps: default 0 (unlimited); set per-licensee in C8 token (EPG-16)

## EPIGNOSIS Architecture Review — Team Decisions (2026-03-18)

### EPG-19: Compliance-hold bridging — NEVER (REX final authority, unanimous)
LIP must never bridge any payment where the originating bank's compliance system raised a hold:
DNOR, CNOR, RR01, RR02, RR03, RR04, AG01, LEGL. Three independent grounds:
- **CIPHER**: Bridging a compliance-held payment is a structuring/layering typology violation.
  FATF R.21 tipping-off means correctly-operating banks often code SARs as MS03/NARR — the
  explicitly-coded holds are the *visible floor* of a larger compliance problem.
- **REX**: AMLD6 Art.10 criminal liability for legal persons. A bank that uses its LIP deployment
  to bridge a payment its own AML system blocked has not taken "reasonable precautions."
- **NOVA**: C3 repayment mechanics are structurally broken for compliance holds — UETR never
  settles (DNOR = permanent prohibition), disbursement may not land (CNOR), maturity windows
  miscalibrated for compliance investigation timelines vs. technical errors.
**Defense-in-depth**: All 8 codes are BLOCK class in rejection_taxonomy.py (Layer 1 — pipeline
short-circuit) AND listed in `_COMPLIANCE_HOLD_CODES` in agent.py (Layer 2 — C7 gate).
**Open legal requirement**: BPI License Agreement must require banks to push compliance holds
to a dedicated API register (EPG-04/EPG-05). The code cannot see SAR-coded payments — this
is a contractual gap that legal counsel must close before any bank pilot.

### EPG-14: Who is the borrower — B2B interbank, originating bank (REX final authority, unanimous)
The MRFA runs to the enrolled originating bank BIC (Deutsche Bank), not the end customer (Siemens).
Bridge loans are B2B interbank credit facilities. Five required actions before B2B structure is operable:
1. **MRFA explicit B2B clause** — originating bank is borrower; repayment unconditional (not
   contingent on underlying payment settling). Legal counsel required. (Tier 1, blocking)
2. **MRFA permanently-blocked-payment clause** — repayment due at maturity regardless. (Tier 1)
3. **Governing law from BIC, not currency** — FIXED in code (EPG-14 code fix, commit see PROGRESS.md).
   `bic_to_jurisdiction()` in governing_law.py uses BIC chars 4–5; `_build_loan_offer` in agent.py
   uses BIC-first with currency fallback. (Tier 2 — done)
4. **BPI License Agreement AML disclosure** — C6 screen does not see bank's internal compliance
   holds or SAR history. Indemnity clause required. (Tier 1, blocking)
5. **C2 model card** — document that 300bps floor prices bank PD (near-zero for Tier 1), not
   end-customer credit risk. (Tier 3 — documentation only)
**CIPHER warning**: B2B structure is NOT an OFAC shield. If bridge funds ultimately benefit a
sanctioned person, OFAC strict liability applies regardless of who the nominal borrower is.

### EPG-09/10/16/17/18 — Implemented (2026-03-18, commit 0ec874c)
- EPG-09/10: outcome="COMPLIANCE_HOLD" (distinct from "DECLINED"), compliance_hold=True on PipelineResult
- EPG-16: AML caps default 0 (unlimited), per-licensee via C8 token; 0=unlimited guard in velocity.py
- EPG-17: license_token.from_dict requires aml_dollar_cap_usd and aml_count_cap as explicit JSON fields
- EPG-18: C6 anomaly flag → PENDING_HUMAN_REVIEW (EU AI Act Art.14 human oversight)

### EPG-04/05: License Agreement strategy (2026-03-19)
**Do NOT ask banks for a hold reason API — this is FATF-prohibited.** Ask for a `hold_bridgeable: bool` certification flag instead:
```
hold_bridgeable: boolean          # set by bank's internal compliance system
certified_by: system_id           # bank compliance system identifier
certification_ts: ISO-8601        # timestamp of certification
```
Bank sets flag per internal policy without disclosing why a hold was raised. BPI hard-blocks on `false`, may offer on `true`. Mirrors FATF R.13 correspondent KYC cert structure.
License Agreement must include three warranties from the bank:
1. **Certification warranty** — any `hold_bridgeable=true` payment is not under OFAC/SDN, SAR, PEP investigation, court freeze, or any hold rendering a bridge unlawful at time of cert.
2. **System integrity warranty** — cert is generated by automated compliance system with documented controls; no manual flag override.
3. **Indemnification** — bank indemnifies BPI for all regulatory fines/enforcement/reputational damages if BPI funds on `hold_bridgeable=true` and payment proves to have been under a hold at cert time.
Bank negotiation lever: without warranty #2, Class B stays block-all permanently — bank loses all B1 LIP revenue.
**Critical path**: language must be in pilot bank LOI *before* their legal team reviews any draft. Starting from a deficient structure = months of renegotiation.

### EPG-19: B1 unlock is gated on EPG-04/05 — no further founder decision needed (2026-03-19)
Block-all Class B is enforced in code and will remain so until:
1. Pilot bank signs license agreement with `hold_bridgeable` API obligation (EPG-04/05)
2. CTO builds B1 API integration
3. Code flip: Class B block-all → B1/B2 split; ARIA retraining triggered
Step 3 is purely mechanical. `class_b_eligible=False` pre-wired in `LoanOfferExpiry` records (EPG-23) for ARIA data cut.

### EPG-20/21: Patent counsel briefing (single session, before non-provisional filing)
**Core novel claim**: two-step classification + conditional offer logic — not the bridge loan mechanics.
Claims must cover: (1) classification of ISO 20022 events against failure taxonomy, (2) conditional gating by classification result, (3) B1/B2 sub-classification mechanism even though currently coded block-all.
**Language scrub** (EPG-21): no "AML", "SAR", "OFAC", "SDN", "compliance investigation", "tipping-off", "suspicious activity", or "PEP" anywhere in published spec. Replace with: "classification gate", "hold type discriminator", "bridgeability flag", "procedural hold", "investigatory hold".
**Do not enumerate**: the BLOCK code list must not appear in any claim — it is a circumvention roadmap. Claim the existence of the gate, not its contents.

### CLASS_B label warning (QUANT + REX must align before changing)
`SETTLEMENT_P95_CLASS_B_HOURS = 53.58` was previously labelled "Compliance/AML holds" — WRONG.
CLASS_B covers systemic/processing delays only. Compliance-hold payments are BLOCK class and are
never bridged. The label has been corrected in constants.py. The value (53.58h) must NOT be used
to calibrate compliance-hold resolution time expectations.

## Key Rules
- Whenever a mistake is caught — by the user or self-identified — immediately add a generalised rule to this file that prevents the entire *class* of mistake, not just the specific instance. The rule must be broad enough to apply to future situations that share the same underlying failure mode.
- Before assessing any data, metric, or code behaviour, read the source implementation and docstrings to verify the semantics and design intent of every field — never infer meaning from names, computed statistics, or surface patterns alone.
- NEVER commit `artifacts/` (model binaries, generated data)
- NEVER commit `c6_corpus_*.json` (AML typology patterns — CIPHER rule)
- NEVER commit API keys, tokens, or secrets of any kind — use `.env` (gitignored) locally and GitHub Actions secrets on Codespace. Reference secrets via environment variables only. If a key appears in any file being committed, stop and refuse.
- Never derive governing law from payment currency — use the enrolled BIC's country code (chars 4–5). Currency is wrong for cross-border correspondent banking. (EPG-14 rule)
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
