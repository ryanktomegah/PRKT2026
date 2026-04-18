# AI Inventorship Matrix & Thaler-Risk Analysis

**Date:** 2026-04-18
**Sprint:** Pre-Lawyer Review — Day 4, Task 4.2
**Branch:** `codex/pre-lawyer-review`
**Prepared for:** patent counsel (pre-non-provisional filing inventorship clearance)
**Source inventories (Task 4.1, commit `60c2215`):**
- `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-claude.csv` (43 commits)
- `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-copilot.csv` (64 commits)
- `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-github-actions.csv` (4 commits)

**Patent claims reference:** `docs/legal/patent/patent_claims_consolidated.md` at commit `c9f63bd` (post-EPG-21 scrub). Last change before this matrix was built was `c9f63bd` (Dependent Claim 4 heading rename). No material edits since; STOP condition #1 not triggered.

---

## 1. Scope

This matrix classifies each AI-authored commit that touches the **patent-claim-critical** code paths and maps the resulting claim elements back to the human or AI author who introduced and/or last materially edited each element. It is built to answer one question for counsel: *for each element of each patent claim, is the creative step attributable to a natural person, and is the human-direction paper trail durable under Thaler v. Vidal (2022)?*

**Claim-critical paths (per Task 4.2 spec):**
- `lip/c1_*` — C1 failure classifier (Family 1, Family 3 gate-1)
- `lip/c2_*` — C2 PD / fee / pricing (Family 1 routing target, Family 2 fee math)
- `lip/c3_*` — C3 repayment engine, rejection taxonomy, settlement (Family 1 taxonomy, Family 2 Redis idempotency)
- `lip/c4_*` — C4 dispute classifier (Family 3)
- `lip/pipeline.py` — pipeline orchestrator (Family 1 pipeline gate positions, Family 3 re-entry)
- `lip/common/` — shared schemas, constants, governing_law, business_calendar (Family 2 BIC/jurisdiction, Family 1/3 ISO 20022 types)

**Cross-referenced (not in 4.2's primary filter but referenced by claims):**
- `lip/c5_streaming/cbdc_normalizer.py` — Family 5 CBDC normalization (single commit, human-authored)
- `lip/c5_streaming/stress_regime_detector.py` — Family 5 stress regime detector (human-authored)
- `lip/c6_aml_velocity/anomaly.py` — Family 3 C6-anomaly human-review gate (Ind. Claim 1, C4 family: "independent hold-type anomaly flag")
- `lip/c7_execution_agent/agent.py`, `human_override.py` — Family 1 Dependent Claim 3 secondary-layer gate; Family 3 Ind. Claim 1 human-override interface
- `lip/p12_federated_learning/` — Family 4 federated learning (single commit, human-authored)

Commits touching **only** `docs/`, `tests/`, `.github/`, `requirements.txt`, or other non-claim-critical paths are summarized in aggregate (§5) rather than enumerated row-by-row.

---

## 2. Methodology

### 2.1 Classification categories
Every AI-authored commit was classified into exactly one of:
- **(a) User-directed** — commit body, co-authoring trailer, or linked EPG/GAP/Priority ticket attributes the instruction to Ryan (the named inventor). AI implemented under direction.
- **(b) Autonomous cleanup** — formatting, linting, rename, refactor, zero-delta PR seed, dependency bumps, test generation without novel logic, CI scaffolding.
- **(c) Creative authorship** — AI introduced a novel algorithm, a claim-relevant constant/threshold, architectural decision, or logic that survives unmodified into the claim-critical path as filed.

### 2.2 Author email patterns (from raw `%ae` logs, not mailmap-resolved)
- **AI authors:** `noreply@anthropic.com` (Claude), `198982749+Copilot@users.noreply.github.com` (GitHub Copilot), `41898282+github-actions[bot]@users.noreply.github.com` / `noreply@github.com` (GitHub Actions).
- **Human authors:** `tomegah@Tomegahs-MacBook-Air.local` (Ryan, local Mac — dominant post-EPIGNOSIS), `naumryan66@gmail.com` (Ryan, cloud/codespace), `ryanktomegah@gmail.com` (Ryan, GitHub web merge).

### 2.3 Paper-trail search — five locations (coded a–e)
For every AI creative-authorship candidate, the following locations were searched:
- **(a)** Prior commits by the user (Ryan) on the same file(s) — via `git log --follow -- <file>` filtered to human emails.
- **(b)** `docs/superpowers/plans/` — sprint plans / work directions.
- **(c)** `docs/superpowers/specs/` — design specs.
- **(d)** CLAUDE.md rule invocations referenced in the commit body (e.g., QUANT, ARIA, CIPHER, REX lens labels; EPG-## or GAP-## tags).
- **(e)** Commit body trailer for `Co-Authored-By: ryanktomegah` or `Directed-By:`.

The code column `paper_trail_locations_checked` lists which locations contained positive direction evidence.

### 2.4 "Last substantive human edit" determination
For every file, `git log --follow --format='%H %ae %s' -- <file>` was walked from newest to oldest, skipping commits where:
- Author email matches AI pattern above, OR
- Subject starts with `style:`, `chore:`, `fix: lint`, `rename:`, `docs:`, or is clearly formatting-only.

The first remaining commit is recorded as `last_human_substantive_edit_sha`. When a file has multiple contributors to the same element, the most-recent substantive touch on any contributing file is used.

### 2.5 Thaler-risk determination (conjunctive — **all three** required for Y)
Per Thaler v. Vidal, 43 F.4th 1207 (Fed. Cir. 2022), inventors under 35 U.S.C. §§ 100(f)–(g) and 115 must be natural persons. A claim element is flagged **Thaler risk = Y** only when:
1. The creative step (novel claim-relevant logic) is AI-authored, **AND**
2. Paper-trail search returns no human direction across **all five** locations (a–e), **AND**
3. No substantive human edit has occurred on the element since AI introduction.

Failing any one of (1)–(3) does **not** clear the claim — it means the mitigating factor must be documented so counsel can assess it. Conservative close calls are resolved toward Y with a footnote (per STOP condition #4).

---

## 3. Pre-Processing Notes (from Task 4.1 code-review reviewer)

Three upstream data artifacts in the CSVs required handling before classification logic was applied:

1. **`Co-authored-by:` baked into `subject` field of commit `f59be87b`** — the Copilot merge `Merge branch 'main' of https://github.com/YESHAPTNT/PRKT2026 into copilot/c6-velocity-sanctions-migration Co-authored-by: ryanktomegah <264463773+ryanktomegah@users.noreply.github.com>` has no blank-line separator between the subject and the trailer because the upstream git message was malformed. This caused the trailer string to be embedded inside the `subject` column in the CSV. **Mitigation:** When searching the `subject` column for paper-trail evidence of human direction (location e), the `Co-[Aa]uthored-[Bb]y:` substring is stripped before pattern-matching. The `ryanktomegah` trailer in `f59be87b` is **not** accepted as human-direction evidence because it is a Copilot–internal branch merge, not a merge of Ryan's work into Copilot's branch; the trailer is a GitHub-UI artifact of which PR author button was clicked, not an authorship claim.

2. **Copilot rows `10638f79` and `be1618d7` touch a file literally named `=2.7.0`** — a pip-install redirect bug (`pip install <pkg>=2.7.0` was mis-typed as a positional arg and created a file), not a real artifact. Flagged as noise and classified as **(b) autonomous cleanup** in both cases (`10638f79` is the deletion commit, `be1618d7` is the commit that accidentally created it).

3. **22 Copilot "Initial plan" rows have zero file delta** — these are PR-seed commits that Copilot creates when given a task; they contain the user's prompt text in the commit body but no code change. Classified as **(b) autonomous cleanup**, BUT each is treated as supporting evidence of user direction (location **d/e**) for the subsequent non-seed commits on the same Copilot PR branch. A 23rd "Initial plan" row (`23c2dba5`) touches `lip/pyproject.toml` — it is included in the non-seed cleanup bucket.

---

## 4. Per-Agent Summary Tables

### 4.1 Claude (43 commits total)

| Metric | Count |
|---|---|
| Total Claude commits in inventory | 43 |
| Claim-critical commits (touching `lip/c[1-4]_`, `lip/pipeline.py`, `lip/common/`) | 16 |
| (a) User-directed | 12 |
| (b) Autonomous cleanup | 4 |
| (c) Creative authorship | 0 |

Rationale: Claude's claim-critical commits are all directed work — `fix+forge:`, `fix(c4):`, `feat(quant):`, `fix(biz-model):`, `fix(c1): align latency SLO constants with canonical spec` all carry lens labels (QUANT, FORGE, QUANT-adjacent) or explicit lens-directed instruction. The `Fix all 183 ruff lint errors` (`a7540c3`) and `fix+forge: mypy type errors` (`a50f74c`) are pure cleanup. No Claude commit introduces a novel claim-element algorithm that survives unmodified into the current filed-claim logic.

### 4.2 Copilot (64 commits total)

| Metric | Count |
|---|---|
| Total Copilot commits in inventory | 64 |
| "Initial plan" zero-delta PR-seed commits | 22 |
| Claim-critical non-seed commits | 20 |
| (a) User-directed | 14 |
| (b) Autonomous cleanup (incl. 22 Initial plan + `=2.7.0` noise + rename/fmt) | 44 |
| (c) Creative authorship | 2* |

\* `f729cb60` (initial C3 repayment engine scaffold) and `09266264` (initial C1 failure classifier scaffold) introduced multi-module structure that *did* contain novel file layout decisions. However, every claim-relevant behaviour inside those scaffolds has since been materially rewritten by human commits (see §6 matrix: `rejection_taxonomy.py` last human edit `033fedf0`, `c3_repayment_engine/repayment_loop.py` last human edit `033fedf0`, C1 inference last human edit `5aeae675`). The initial scaffold decisions are therefore (c) but do not carry forward any Thaler-risk surface — see §7.

### 4.3 GitHub Actions (4 commits total)

| Metric | Count |
|---|---|
| Total GHA commits | 4 |
| Claim-critical commits | 0 |
| (a) User-directed | 0 |
| (b) Autonomous cleanup | 4 |
| (c) Creative authorship | 0 |

All 4 GHA commits are `chore(c6): refresh public-domain sanctions snapshot [skip ci]` writing to `lip/c6_aml_velocity/data/sanctions.json` — this file is a **data snapshot**, not a claim element. OFAC/UN sanctions lists are public-domain factual data; their automated refresh is not a patentable contribution.

### 4.4 Aggregate non-claim-critical volume (all three agents)

Commits touching only `docs/`, `tests/`, `.github/workflows/`, `Dockerfile*`, `requirements*.txt`, `*.md`, `lip/infrastructure/`, or `frontend/`:
- Claude: 27 (of 43)
- Copilot: 44 (of 64, including 22 Initial plan + Project2026 copy/* pre-lip-migration work)
- GHA: 4 (of 4)
- **Total non-claim-critical: 75**

These are not enumerated in §6 because they cannot introduce a patent claim element; however each was visually scanned during matrix construction to confirm no hidden claim-relevant logic leaked (e.g., a constant file under `lip/infrastructure/` was checked — none found).

---

## 5. Inventorship Matrix — Per Claim Element

**Column key:**
- `claim element` — short name of the claim element, with claim reference
- `file(s)` — primary implementation file(s)
- `first-introducing commit` — first commit that lands the element in claim-critical form
- `author` — `%ae` author of first-introducing commit (raw, not mailmap-resolved)
- `creative-step author` — who introduced the novel logic element (may differ from first-introducing if initial was scaffold-only)
- `last_human_substantive_edit_sha` — most-recent human commit that materially changed the element
- `last_human_substantive_edit_author` — `%ae` of that commit
- `paper_trail_locations_checked` — which of the five location codes (a–e) contained positive human-direction evidence
- `Thaler risk (Y/N)` — per §2.5 three-condition test

| # | claim element | file(s) | first-introducing commit | author | creative-step author | last_human_substantive_edit_sha | last_human_substantive_edit_author | paper_trail_locations_checked | Thaler risk (Y/N) |
|---|---|---|---|---|---|---|---|---|---|
| F1-I1-a | ISO 20022 rejection-code three-class taxonomy (permanent / systemic / hold-type) | `lip/c3_repayment_engine/rejection_taxonomy.py` | `f729cb60` | Copilot | Ryan (`be16c226`, `601753251`, EPG-01/02/03/07/08 moved codes to BLOCK) | `033fedf0` | `tomegah@Tomegahs-MacBook-Air.local` | a, b, d, e | N |
| F1-I1-b | Pipeline gate routing: short-circuit on hold-type vs. route to ML/PD/fee/disburse | `lip/pipeline.py`, `lip/c7_execution_agent/agent.py` | `cadf1905` (Copilot Phase 5 E2E) | Copilot | Ryan (EPG-09/10/27 fall-through fix `5564b40c`, EPG-19 compliance-hold block `770f70c8`) | `d5a1e28b` | `ryanktomegah@gmail.com` | a, b, d, e | N |
| F1-D2-a | Evaluate hold-type BEFORE permanent/systemic + logically distinct hold-type outcome | `lip/c7_execution_agent/agent.py`, `lip/pipeline.py` | `0ec874c5` (EPG-09/10 fixes) | `tomegah@...` (Ryan) | Ryan | `d5a1e28b` | `ryanktomegah@gmail.com` | a, d | N (fully human-authored) |
| F1-D2-b | Immutable decision-log entry with halt_reason for regulatory examination | `lip/c7_execution_agent/decision_log.py` | `9f623ce5` (Copilot initial C7 scaffold) | Copilot | Ryan (`a2b5d8a6` tenant_id threading; LicenseeContext wiring by Claude `467b9a7d` under CIPHER direction) | `d6b57305` | `tomegah@...` | a, b, d | N |
| F1-D3 | Defense-in-depth: primary gate + secondary `_COMPLIANCE_HOLD_CODES` frozenset gate in agent.py | `lip/c7_execution_agent/agent.py`, `lip/c3_repayment_engine/rejection_taxonomy.py`, `lip/common/compliance_hold_codes.json` | `770f70c8` (EPG-19 block set) | `tomegah@...` (Ryan) | Ryan | `dd6f7806` (consolidate to shared JSON) | `tomegah@...` | a, d | N (fully human-authored) |
| F1-D3-norm | Streaming normalization of proprietary rail codes → canonical ISO 20022 | `lip/c5_streaming/event_normalizer.py`, `lip/c5_streaming/cbdc_normalizer.py` | `ed31314a` (P5 CBDC normalizer PR #50) | `ryanktomegah@gmail.com` (Ryan) | Ryan | `ed31314a` | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored) |
| F1-D4 | Hold-type class = internal non-bridgeable taxonomy (external to claim) | `lip/c3_repayment_engine/rejection_taxonomy.py`, `lip/configs/rejection_taxonomy.yaml` | `be16c226` (EPG-01/03/07/08) | `tomegah@...` | Ryan | `033fedf0` | `tomegah@...` | a, d | N |
| F1-D5 | B1/B2 sub-classification — procedural-hold vs investigatory-hold + bridgeability cert | `lip/c7_execution_agent/agent.py`, `lip/common/schemas.py` (LoanOfferExpiry `class_b_eligible` pre-wire) | `3affea67` (EPG-23 pre-wire) | `tomegah@...` | Ryan (per EPG-04/05/19 in CLAUDE.md decisions) | `3affea67` | `tomegah@...` | a, d | N (fully human-authored; note: B1 path is currently `block-all`, awaiting EPG-04/05 license agreement per CLAUDE.md) |
| F2-I1-a | Multi-rail payment event normalization + unified original-payment-amount field | `lip/c5_streaming/event_normalizer.py`, `lip/common/schemas.py` | `9f623ce5` (Copilot C5/C6/C7 scaffold — `event_normalizer.py` shell) | Copilot | Ryan (`4a959af5` GAP-06 amount validation spec, `eea5daa1` P1+P3 integration) | `6e4b1ae8` | `tomegah@...` | a, b, d | N |
| F2-I1-b | Disbursement-amount validation within $0.01 tolerance | `lip/c7_execution_agent/agent.py`, `lip/pipeline.py` | `4a959af5` (GAP-06/17 SWIFT amount validation) | `naumryan66@gmail.com` (Ryan) | Ryan | `06871e65` | `ryanktomegah@gmail.com` | a, d | N (fully human-authored) |
| F2-I1-c | Governing-law jurisdiction from BIC chars 4–5 + currency fallback | `lip/common/governing_law.py` | `770f70c8` (EPG-14 BIC-first, replaced currency-based) | `tomegah@...` (Ryan) | Ryan | `770f70c8` | `tomegah@...` | a, d | N (fully human-authored; prior Claude-authored currency-based logic explicitly deleted per CLAUDE.md EPG-14 rule) |
| F2-I1-d | Business-day adjusted maturity + TARGET2/FEDWIRE/CHAPS holiday tables | `lip/common/business_calendar.py`, `lip/c7_execution_agent/human_override.py` | `5354150b` (GAP-07+08+09) | `naumryan66@gmail.com` (Ryan) | Ryan | `5354150b` | `naumryan66@gmail.com` | a, b, d | N (fully human-authored) |
| F2-I1-e | Partial-settlement policy + Redis idempotency-token preservation/consumption | `lip/c3_repayment_engine/repayment_loop.py`, `lip/c3_repayment_engine/settlement_handlers.py` | `f729cb60` (Copilot C3 scaffold) | Copilot | Ryan (`d4b593d4` tenant-scoped Redis, `c10cd6c4` GAP-05 royalty settlement, `033fedf0` taxonomy+settlement fail-closed) | `033fedf0` | `tomegah@...` | a, b, d, e | N |
| F2-D3 | CBDC rail 4-hour settlement buffer + CBDC-SC01→AC01, CBDC-KYC01→RR01, CBDC-LIQ01→AM04, CBDC-FIN01→TM01 mappings | `lip/c5_streaming/cbdc_normalizer.py` | `ed31314a` (P5 PR #50) | `ryanktomegah@gmail.com` (Ryan) | Ryan | `ed31314a` | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored via PR; P5 patent intentionally Ryan-authored from spec) |
| F2-D4 | Redis idempotency with preserve-on-partial + partial-settlement record dataclass | `lip/c3_repayment_engine/repayment_loop.py`, `lip/c3_repayment_engine/settlement_handlers.py` | `f729cb60` (Copilot scaffold had idempotency interface; partial-settlement fields added by Ryan) | Copilot (scaffold) / Ryan (partial-settlement fields) | Ryan | `033fedf0` | `tomegah@...` | a, b, d | N |
| F2-D5 | Jurisdiction derivation with currency-fallback then FEDWIRE-default | `lip/common/governing_law.py` | `770f70c8` (EPG-14) | `tomegah@...` (Ryan) | Ryan | `770f70c8` | `tomegah@...` | a, d | N (fully human-authored) |
| F2-D6 | SWIFT pacs.008 credit transfer with `LIP-BRIDGE-{uetr}` end-to-end ID, full 100% principal | `lip/c3_repayment_engine/settlement_handlers.py`, `lip/c7_execution_agent/agent.py` | `4a959af5` (GAP-06 SWIFT disbursement spec) | `naumryan66@gmail.com` (Ryan) | Ryan | `d4b593d4` | `tomegah@...` | a, d | N (fully human-authored) |
| F2-D7 | UETR deduplication tracker: 30-min window, 45-day TTL, (bicA, bicB, amount, ccy) key | `lip/c3_repayment_engine/uetr_mapping.py`, `lip/c3_repayment_engine/corridor_buffer.py` | `f729cb60` (Copilot C3 scaffold had uetr_mapping) | Copilot (interface) / Ryan (30-min window + tuple key + TTL) | Ryan (`d15e83ec` GAP-04 fix to uetr_tracker) | `033fedf0` | `tomegah@...` | a, b, d | N |
| F3-I1-a | First ML classification gate (C1 PD-of-failure threshold gating) | `lip/c1_failure_classifier/inference.py`, `lip/c1_failure_classifier/model.py` | `09266264` (Copilot initial C1 scaffold) | Copilot | Ryan (`0a949bed` vectorised SHAP by Claude under ARIA direction; `93816d72` threshold 0.360 retraining; `9f5504e3` threshold 0.110 recalibrated) | `5aeae675` | `tomegah@...` | a, b, d | N (scaffold was non-claim-specific; thresholds + gating calibrated by Ryan) |
| F3-I1-b | Two-stage prefilter: (a) empty→UNKNOWN without LLM, (b) keyword→hold-type without LLM | `lip/c4_dispute_classifier/prefilter.py` | `463f6208` (Copilot initial C4 scaffold — prefilter skeleton) | Copilot (skeleton) / Ryan (the two-stage semantics + keyword set) | Ryan (`3808a749` negation guard for keyword matching, `b7b09fd0` Step 2b Romance-language contraction, `5aeae675` EPG-19 full block set) | `5aeae675` | `tomegah@...` | a, b, d | N (Copilot contributed file skeleton; all claim-relevant prefilter logic is human-authored) |
| F3-I1-c | LLM classification (DISPUTE_CONFIRMED / NOT_DISPUTE) | `lip/c4_dispute_classifier/model.py`, `lip/c4_dispute_classifier/backends.py`, `lip/c4_dispute_classifier/prompt.py` | `463f6208` (Copilot C4 scaffold) | Copilot | Ryan (Qwen3 Groq backend + `/no_think` pattern in CLAUDE.md; `5aeae675` B10-10..18 Groq model fix) | `5aeae675` | `tomegah@...` | a, b, d | N |
| F3-I1-d | Human-override interface: configurable timeout + operator ID + justification + escalation | `lip/c7_execution_agent/human_override.py` | `5354150b` (GAP-08 override timeout) | `naumryan66@gmail.com` (Ryan) | Ryan | `d6b57305` | `tomegah@...` | a, d | N (fully human-authored) |
| F3-I1-e | Hold-type anomaly flag independent of classifier (C6 anomaly → human review) | `lip/c6_aml_velocity/anomaly.py`, `lip/pipeline.py` | `2636a637` (EPG-16/17/18/28 — anomaly routing) | `tomegah@...` (Ryan) | Ryan | `91e3dccb` | `tomegah@...` | a, d | N (fully human-authored per CLAUDE.md EPG-18) |
| F3-D2 | /no_think LLM latency reduction — terminal directive + empty stop-sequence + regex strip | `lip/c4_dispute_classifier/model.py`, `lip/c4_dispute_classifier/prompt.py` | Documented in CLAUDE.md 2026-03-16 | Ryan (CLAUDE.md rule) | Ryan | `5aeae675` | `tomegah@...` | a, d | N (rule is explicitly human-authored and codified in CLAUDE.md as "never add `stop=...` to Qwen3 calls") |
| F3-D3 | Adversarial training data generator — synthetic ISO 20022 camt.056 + pacs.002 shared UETR | `lip/c4_dispute_classifier/training.py`, `lip/dgen/c4_generator.py` | `f7496e83` ([DGEN] corpora) | `tomegah@...` (Ryan, pre-AI-era local commit) | Ryan | `f7496e83` | `tomegah@...` | a, d | N (fully human-authored) |
| F3-D4 | Pipeline re-entry context store — override ID → full payment event round-trip | `lip/c7_execution_agent/human_override.py`, `lip/pipeline.py` | `4dce6f60` (EPG-26 pipeline re-entry) | `tomegah@...` (Ryan) | Ryan | `d6b57305` | `tomegah@...` | a, d | N (fully human-authored per EPG-26) |
| F3-D5 | Dual-approval mode for human override | `lip/c7_execution_agent/human_override.py` | `5354150b` (GAP-08) | `naumryan66@gmail.com` (Ryan) | Ryan | `d6b57305` | `tomegah@...` | a, d | N (fully human-authored) |
| F4-I1 | Federated learning with DP-SGD + FedProx + Rényi DP accountant | `lip/p12_federated_learning/privacy_engine.py`, `dp_accountant.py`, `client.py`, `models.py` | `28afdd2a` (P12 PR #56) | `ryanktomegah@gmail.com` (Ryan) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N (fully human-authored via PR; Family 4 file never touched by any AI author) |
| F4-D2 | Layer partitioning — aggregate final layers only, keep counterparty-topology local | `lip/p12_federated_learning/models.py`, `lip/p12_federated_learning/local_ensemble.py` | `28afdd2a` | `ryanktomegah@gmail.com` (Ryan) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N |
| F4-D3 | FedProx proximal regularization μ in [0.001, 0.1] | `lip/p12_federated_learning/client.py`, `constants.py` | `28afdd2a` | `ryanktomegah@gmail.com` (Ryan) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N |
| F4-D4 | Phase 3 secure-aggregation upgrade (3-node threshold + semi-honest semantics) | `lip/p12_federated_learning/privacy_engine.py`, `docs/business/fundraising/Capital-Partner-Strategy.md` (Phase 3 spec) | `28afdd2a` + `55275b2e` (capital strategy) | `ryanktomegah@gmail.com` / `noreply@anthropic.com` (Claude wrote Capital-Partner-Strategy doc, not code) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N (code is fully human-authored; Claude wrote the capital-strategy *doc* under user direction) |
| F4-D5 | Asynchronous quorum aggregation — tolerate non-responding nodes without failing round | `lip/p12_federated_learning/simulation.py` | `28afdd2a` | `ryanktomegah@gmail.com` (Ryan) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N |
| F4-D6 | Communication budget fits SWIFT SWIFTNet channel (no dedicated bandwidth) | `docs/business/fundraising/Capital-Partner-Strategy.md`, `lip/p12_federated_learning/` | `28afdd2a` | `ryanktomegah@gmail.com` (Ryan) | Ryan | `28afdd2a` | `ryanktomegah@gmail.com` | a, b, c, d | N |
| F5-I1 | CBDC normalization & bridge lending (CBDC-smart-contract→AC01, KYC→RR01, LIQ→AM04) | `lip/c5_streaming/cbdc_normalizer.py` | `ed31314a` (P5 PR #50) | `ryanktomegah@gmail.com` (Ryan) | Ryan | `ed31314a` | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored) |
| F5-I2 | Corridor stress regime detector — 24h baseline, 1h stress, 3x multiplier, 20-txn min | `lip/c5_streaming/stress_regime_detector.py` | `eea5daa1` (P1+P3 integration, StressRegimeDetector) | `naumryan66@gmail.com` (Ryan) | Ryan | `211e7be2` (Phase 2 T2.1 DLQ routing, PR #54) | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored) |
| F5-D3 | Differential maturity by rail — 4h CBDC buffer, 45-day UETR TTL legacy | `lip/c5_streaming/cbdc_normalizer.py`, `lip/c3_repayment_engine/uetr_mapping.py` | `ed31314a` + earlier UETR TTL constants | `ryanktomegah@gmail.com` + `tomegah@...` | Ryan | `ed31314a` | `ryanktomegah@gmail.com` | a, b, d | N |
| F5-D4 | Statistical-significance gate — min 20 transactions on both windows independently | `lip/c5_streaming/stress_regime_detector.py` | `eea5daa1` | `naumryan66@gmail.com` (Ryan) | Ryan | `211e7be2` | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored) |
| F5-D5 | New-corridor zero-baseline conservative gate — declare stress on any single failure | `lip/c5_streaming/stress_regime_detector.py` | `eea5daa1` | `naumryan66@gmail.com` (Ryan) | Ryan | `211e7be2` | `ryanktomegah@gmail.com` | a, b, d | N (fully human-authored) |

### 5.1 Claim element ↔ commit mapping — element count

- **Family 1 (Taxonomy + Dual-Layer):** 7 elements mapped (I1-a, I1-b, D2-a, D2-b, D3, D3-norm, D4, D5). I1-a and F1-D3-norm are coded as one row each covering sub-bullets. **8 rows.**
- **Family 2 (Multi-Rail Settlement):** 10 elements (I1-a, I1-b, I1-c, I1-d, I1-e, D3, D4, D5, D6, D7). **10 rows.**
- **Family 3 (C4 Dispute + Human Override):** 8 elements (I1-a, I1-b, I1-c, I1-d, I1-e, D2, D3, D4, D5). **9 rows.**
- **Family 4 (Federated Learning):** 6 elements (I1, D2, D3, D4, D5, D6). **6 rows.**
- **Family 5 (CBDC + Stress Regime):** 5 elements (I1, I2, D3, D4, D5). **5 rows.**
- **Total matrix rows: 38 claim elements across 5 families.**

---

## 6. Thaler-Risk = Y Summary

**Count: 0 claim elements have Thaler risk = Y.**

All 38 claim elements satisfy at least one of the three Thaler-clearing conditions:
- Condition 1 fails (AI did not create the creative step) — applies to 33 of 38 elements where the creative step was human-authored from inception;
- Condition 2 fails (paper-trail search returned positive human-direction evidence in at least one of locations a–e) — applies to all remaining 5 elements (F1-I1-a, F1-I1-b, F1-D2-b, F2-I1-a, F2-I1-e, F3-I1-b, F3-I1-c — where initial scaffolds were Copilot-authored but the claim-relevant creative logic was subsequently introduced or rewritten under documented EPG/GAP direction);
- Condition 3 fails (substantive human edit has occurred on the element since any AI introduction) — all 38 elements have had a substantive human edit more recent than any AI author touch in the file history.

### 6.1 Near-Y elements (for counsel awareness, not remediation)

These are elements where an AI author has landed a scaffold that persists (even if the claim-relevant logic was subsequently rewritten by Ryan). They are NOT Thaler risk = Y but counsel may want contemporaneous human-authorship declarations on:

- **F1-I1-a (rejection_taxonomy.py)** — scaffold by Copilot `f729cb60`; all BLOCK-class assignments and the three-class-outcome shape are from Ryan commits `ac2f7b31`, `be16c226`, `601753251`, `033fedf0`. *Counsel note: declaration should specifically attest that taxonomy class boundaries (which codes go to BLOCK vs. DECLINE vs. RETRY) are Ryan's creative work post-EPIGNOSIS.*
- **F2-I1-a (event_normalizer.py)** — scaffold by Copilot `9f623ce5`; the `unified_original_payment_amount` field semantics and the multi-rail normalization schema were set by Ryan in `4a959af5` (GAP-06 spec) and `eea5daa1` (P1+P3).
- **F3-I1-b (prefilter.py)** — scaffold by Copilot `463f6208`; the two-stage semantics (empty→UNKNOWN, keyword→hold-type-indicator) were set by Ryan in `3808a7494`, `b7b09fd0`, `5aeae675`.
- **F3-I1-c (backends.py, model.py for C4 LLM)** — scaffold by Copilot `463f6208`; Qwen3 + Groq backend choice and `/no_think` trick are Ryan's, codified in CLAUDE.md C4 LLM Backend Rules (2026-03-16).
- **F3-I1-a (C1 inference gating)** — scaffold by Copilot `09266264`; threshold calibrations (0.110 current, from 0.360 via retraining) are Ryan's via `9f5504e3` and `93816d72`.

---

## 7. Remediation List

**No Thaler-risk = Y elements → no remediation required for today.**

For the five near-Y elements in §6.1, counsel should request the following at the declaration-of-inventorship stage (35 U.S.C. § 115 declaration + AIA inventor oath):

1. **Contemporaneous authorship declaration** attesting that the claim-relevant creative step (not the module skeleton) was the inventor's (Ryan's) work, with specific reference to the EPG-## or GAP-## ticket that directed each subsequent rewrite.
2. **Retention of EPIGNOSIS review archive** (`docs/legal/decisions/EPG-*.md`) as direct evidence of human direction for claim elements F1-D2-a/b, F1-D3, F1-D4, F1-D5, F2-I1-c, F2-D5, F3-I1-e, F3-D4.
3. **Retention of GAP review archive** (see docs/engineering/ GAP-01..17 artifacts, referenced in CLAUDE.md) as direct evidence for F2-I1-d, F2-I1-b, F3-I1-d, F3-D5.
4. **Retention of sprint plan `docs/superpowers/plans/2026-04-17-pre-lawyer-review.md`** and predecessor plans (2026-03-27 onward) as the documented direction trail.
5. **No pre-filing code rewrites required** — the three-condition Thaler test clears all 38 elements. Filing is not blocked by this matrix.

---

## 8. Caveats and Limitations

1. **Classification is heuristic.** The (a)/(b)/(c) bucketing of AI commits is a reviewer judgment call based on commit subject, files changed, and diff size. Edge cases (e.g., a Claude commit under a QUANT lens that also introduces an incidental new constant) were resolved conservatively toward (c) and then cleared by the Thaler three-condition test in a subsequent §5 row.

2. **The matrix does not prove inventorship.** It documents the *paper trail* for each claim element. Formal inventorship determination under 35 U.S.C. § 116 requires counsel analysis of conception + reduction-to-practice, not merely git history. The matrix is evidence-gathering, not legal conclusion.

3. **"Creative step" is interpreted narrowly.** The matrix treats an AI-authored file skeleton (e.g., Copilot initial C1/C3/C4 scaffolds) as NOT creative-step authorship when the claim-relevant logic inside was subsequently rewritten by a human. Counsel may take a different view — if so, the near-Y list in §6.1 identifies the exact re-exposure points.

4. **Mailmap is not applied.** The `%ae` values in the matrix are the raw commit-trailer emails (per 4.2 spec), which means Ryan's three addresses (`tomegah@Tomegahs-MacBook-Air.local`, `naumryan66@gmail.com`, `ryanktomegah@gmail.com`) appear as three distinct authors. They are the same natural person. This is a feature, not a bug — it preserves the actual commit-record for counsel review.

5. **Non-claim-critical AI work not enumerated.** 75 of 111 total AI commits (Claude 27, Copilot 44, GHA 4) are in non-claim-critical paths and are not individually scrutinized in §5. They were scanned in aggregate; no hidden claim-relevant logic was found. If counsel wishes full row-by-row coverage, the CSVs in `docs/engineering/review/2026-04-17/week-1-ip-timing/` contain all 111.

6. **Task 4.1 "22 Initial plan zero-delta" count is 22 of 23 Initial-plan rows.** The 23rd (`23c2dba5`) touches `lip/pyproject.toml` (a dep bump, not a claim element). No material effect on inventorship; noted for accuracy.

7. **STOP condition #3 was considered and cleared.** Every claim element in `patent_claims_consolidated.md` has at least one implementation file in `lip/` — there are no "claim-only, no code" elements to flag.

8. **Thaler v. Vidal is evolving law.** The Federal Circuit's 2022 opinion forecloses AI-as-inventor but does not fully define "creative step" attribution thresholds when AI is used as a tool under human direction. Counsel should validate the three-condition test in §2.5 against current 2026 USPTO guidance before relying on this matrix as a filing-clearance artifact.

---

*End of inventorship matrix. For the Red-Flag Register entries derived from this matrix, see `docs/legal/.red-flag-register.md` (gitignored, local-only).*
