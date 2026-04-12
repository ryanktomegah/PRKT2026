# Next-Session Production Push — Plan and Handoff Prompt

**Created**: 2026-04-11
**Owner**: Ryan Tomegah (founder, non-technical)
**Scope**: Option C — remaining patent families in code + Phase-2 production stubs + infrastructure hardening
**Target session**: Fresh Claude Code terminal, clean context
**Prior work closed**: B1–B13 hardening sprint (see `docs/engineering/review/2026-04-08/RESOLUTION-STATUS.md`)

---

## Part 1 — Why this document exists

The founder is non-technical. He sets direction. The previous session compiled
the BPI/LIP status report (`docs/business/Project-Status-Report-2026-04-11.md`)
and verified that the 12 Critical code-review findings from 2026-04-08 were
already fixed by the B1–B13 hardening sprint (see commits `eb93fc8`, `1a183fc`,
`dd6f780`, `6b4c55f`, `f4bb1d5`, `8d4b0c7`, `6e03d06`, `7610c82`, `a3a59d5`).

The founder now wants to push forward on what's not yet in code. That is
**Option C — the full package**:

1. Patent families that exist as spec only → turn into code.
2. Modules that work with in-memory mocks → wire to real infrastructure (Kafka, Redis, mTLS).
3. Cloud deployment readiness that's templated but not executed.

This document is the **handoff plan** for the next session. Parts 3–5 describe
the scope. **Part 7 is a paste-ready prompt** the founder will hand to a fresh
AI in a new terminal.

The next AI should do its own research and build its own context — this doc
tells it where to look, not what to conclude.

---

## Part 2 — Hard constraints and non-negotiables

Any work in the next session must respect these. They are non-negotiable:

### Canonical constants (CLAUDE.md-level; QUANT/CIPHER/REX authority)

| Constant | Value | Enforced by |
|---|---|---|
| Fee floor | 300 bps | `assert` is banned; must be explicit raise — already enforced (B10-08 fix) |
| CLASS_A maturity | 3 days | `lip/common/constants.py` |
| CLASS_B maturity | 7 days | `lip/common/constants.py` |
| CLASS_C maturity | 21 days | `lip/common/constants.py` |
| BLOCK class | 0 days | `lip/common/constants.py` |
| UETR TTL buffer | 45 days | salt rotation 365d + 30d overlap |
| Latency SLO | ≤ 94 ms | measured in `lip/tests/` |
| AML caps | default 0 = unlimited, set per-licensee via C8 | EPG-16 |

**Never change these without the responsible agent's sign-off.** QUANT is the
floor on fee math. CIPHER is the floor on AML/security. REX is the floor on
regulatory compliance.

### EPG decisions (see CLAUDE.md §"EPIGNOSIS Architecture Review")

- **EPG-19 — Compliance holds NEVER bridged**: DNOR, CNOR, RR01, RR02, RR03, RR04, AG01, LEGL. All 8 are BLOCK class. Defense-in-depth: Layer 1 in `rejection_taxonomy.py`, Layer 2 in `agent.py` `_COMPLIANCE_HOLD_CODES`. The canonical list now lives in `lip/common/block_codes.json` (B6-01 fix). Do **not** add another copy anywhere.
- **EPG-14 — Borrower is originating bank (B2B interbank)**: governing law derived from BIC chars 4–5, not currency. See `lip/common/governing_law.py`.
- **EPG-04/05 — `hold_bridgeable` API**: pilot banks must push a boolean certification from their internal compliance system. Never ask banks for a hold reason (FATF-prohibited tipping-off). Class B stays block-all in code until this API is contracted.
- **EPG-18 — C6 anomaly → PENDING_HUMAN_REVIEW**: EU AI Act Art. 14 human oversight.
- **EPG-20/21 — Patent language scrub**: never use "AML", "SAR", "OFAC", "SDN", "PEP", "tipping-off", "compliance investigation", or "suspicious activity" in any published patent spec. Use "classification gate", "hold type discriminator", "bridgeability flag", "procedural hold", "investigatory hold". Do not enumerate BLOCK codes in any claim — that is a circumvention roadmap.

### Code-level rules (CLAUDE.md §"Key Rules")

- Never commit `artifacts/` (model binaries, generated data).
- Never commit `c6_corpus_*.json` (AML typology patterns).
- Never commit API keys, tokens, or secrets — use `.env` (gitignored) or GitHub Actions secrets.
- Always run `ruff check lip/` — zero errors before commit.
- Always run `python -m pytest lip/tests/` before commit.
- Never derive governing law from currency — use BIC chars 4–5 (EPG-14).
- Never infer field semantics from names — always read the source.
- Never use `--no-verify` on commits or `--force` on pushes to main.
- `assert` is banned for load-bearing invariants — use explicit `if ... raise`.

### Team-agent protocol (CLAUDE.md §"The Ford Principle")

Before any implementation:

1. State what you understand the request to be — flag ambiguity.
2. Ask the single most important clarifying question if requirements are unclear.
3. State intended approach and *why* — including trade-offs.
4. Flag risk, conflict with canonical constants, or disagreement with the stated approach.
5. Only then implement.

Agents push back on bad instructions. An agent that executes a bad instruction
has failed even if the code runs.

---

## Part 3 — What Option C covers (scope breakdown)

### Tier 1 — Patent code, priority-order

Filing provisional P1 establishes priority date for all families including
those not yet in code. But "in code" increases defensibility and eliminates
"it's just a paper patent" objections from a pilot bank or acquirer. Order
below reflects strategic value per unit of effort.

#### T1.1 — P5 CBDC normalization (Family 5, partially implemented)

- **What exists**: `lip/c5_streaming/stress_regime_detector.py` (3.0x threshold, 20-tx minimum, Kafka emission) and `lip/p5_cascade_engine/` (7+ modules). Stress regime detection is done.
- **What is missing (paper only)**:
  - CBDC-to-ISO 20022 normalization layer — ingest CBDC payment events (e-CNY, e-EUR testnet, Sand Dollar format) and emit canonical ISO 20022 pacs.00x records.
  - Differential maturity by rail (4h CBDC vs. 45-day UETR for legacy correspondent).
- **Implementation sketch**:
  - New module: `lip/c5_streaming/cbdc_normalizer.py`.
  - Input schemas: e-CNY (PBoC), e-EUR (ECB experimental), Sand Dollar (CBB). Reference specs and links in the patent doc at `docs/legal/patent/Future-Technology-Disclosure-v2.1.md` Extension E.
  - Output: canonical pacs.008/pacs.002 messages routed through the existing C5 pipeline.
  - Maturity policy: extend `lip/common/constants.py` with a `RAIL_MATURITY_HOURS` map; C3 looks up maturity from the rail tag on the UETR record.
- **Estimated size**: 600–1000 LOC, ~20 tests, 2–3 days of AI-driven dev.

#### T1.2 — P4 Federated Learning (Family 4, paper only)

- **What exists**: ML training paths for C1 (GraphSAGE + TabTransformer + LightGBM) in `lip/c1_failure_classifier/training.py`.
- **What is missing (paper only)**:
  - Differentially private gradient aggregation across bank participants.
  - Layer partitioning (GraphSAGE global, TabTransformer local).
  - FedProx non-IID regularization.
  - Secure Aggregation is Phase 3 — do **not** ship in this sprint.
- **Implementation sketch**:
  - New package: `lip/p4_federated_learning/`.
  - Client (bank side) sends local gradient updates with Laplace noise calibrated to `PRIVACY_BUDGET_PER_ROUND`.
  - Server performs FedAvg / FedProx aggregation; gradient norms clipped to bound sensitivity.
  - Reuse `lip/p10_regulatory_data/anonymizer.py` DP machinery (already hardened in B8-01/02 fixes) for noise calibration.
  - CIPHER sign-off required on the crypto boundary; QUANT sign-off required on noise-calibration math.
- **Estimated size**: 1500–2500 LOC, ~35 tests, 4–6 days.

#### T1.3 — Continuation disclosures in code (Extensions A–G)

`docs/legal/patent/Future-Technology-Disclosure-v2.1.md` lists 7 continuation
disclosures. Two are partially coded (B, G). The rest are paper only. Code
implementation is **not** required to file continuations — but it prevents
the "unsupported claim" objection from a patent examiner.

Priority ranking **inside T1.3**:

1. **Extension B — Supply Chain Cascade Detection and Prevention** (P5 continuation). `lip/p5_cascade_engine/` already models bank-to-bank cascades. Extend to corporate supply-chain graphs. Reuses existing graph primitives. Low effort, high defensive value.
2. **Extension G — Adversarial Cancellation Detection** (C5 continuation). `lip/c5_streaming/cancellation_detector.py` is a stub. Flesh out the detection heuristics against synthetic adversarial cancellation patterns.
3. **Extension A — Pre-Emptive Liquidity Portfolio Management** (P4 continuation). Build on T1.2 federated learning outputs.
4. **Extensions C, D, E, F** — defer. Lower marginal value; extensions C (autonomous treasury agent) and F (multi-party distributed architecture) need architectural work that is premature.

Estimated combined size for 1–3: 2000–3000 LOC, 6–8 days.

### Tier 2 — Phase-2 production stubs

Modules that pass their own tests today but use mocks or in-memory state that
won't survive a real pilot. Some of these are already tagged with CLAUDE.md
notes. Each item below is a blocker for pilot go-live, not for pilot demo.

#### T2.1 — Kafka production wiring

- **Stress regime detector** (`lip/c5_streaming/stress_regime_detector.py`): Kafka emission path exists but the in-process producer needs to be swapped for `confluent_kafka` (librdkafka-backed) with idempotent producer config — `enable.idempotence=true`, `acks=all`, `max.in.flight.requests.per.connection=5` (matches Go consumer; already aligned per B6-06 fix).
- **Go consumer** (`lip/c5_streaming/go_consumer/`): already hardened for exactly-once semantics (B6-02 fix — no offset commit on error paths). Confirm TLS defaults (B6-04/05 fix).
- **DLQ routing**: ensure all error paths route to DLQ with correlation_id + UETR; zero silent drops.

#### T2.2 — Redis-backed multi-replica state

- **C8 query metering** (`lip/c8_license_manager/query_metering.py`): `single_replica=True` opt-in is in place (B3-04 fix). For real multi-replica, add Redis-backed store behind the same interface. INCR + expiry keyed by `(regulator_id, month_bucket)`.
- **Rust velocity counters** (`lip/c6_aml_velocity/rust_velocity/`): same story — `single_replica=True` opt-in in place (B7-02). Add Redis-backed counter with Lua atomic check-and-increment.
- **C6 structuring detector**: in-memory state needs Redis backing (B7-10 flagged).

#### T2.3 — mTLS everywhere

- gRPC routes between C5 consumer → C7 router are TLS-default now (B6-04 fix). Extend to mutual TLS — issue client certs via cert-manager in K8s.
- Redis connections use TLS; Kafka uses SSL. Document the trust chain in `docs/operations/security-trust-chain.md`.

#### T2.4 — Observability wiring

- Grafana dashboards exist as templates. Wire to a real Prometheus scrape endpoint in each service.
- Datadog/OpenTelemetry tracing on the critical path (C5 → C1 → C7) to validate the 94ms SLO under load, not just in isolation.
- Structured logs with UETR + correlation_id on every log line crossing a service boundary.

#### T2.5 — Dependency CVE remediation (Dependabot backlog)

As of 2026-04-11, GitHub Dependabot flags **16 open alerts** on `origin/main`:
**4 critical, 8 high, 2 medium, 2 low** — all from two packages. The B12-01
hardening added upper version bounds (preventing supply-chain rollout); this
work moves the bounds forward after verifying upstream fixes.

**mlflow (13 alerts)** — pinned `mlflow>=2.10.0,<3.0` in `requirements-ml.txt`.
Actual usage is 3 `log_metric` calls in `lip/c1_failure_classifier/training.py`
(training-time telemetry, not runtime). Most criticals are against the MLflow
**tracking server** (RCE, command injection, path traversal, auth bypass) —
which BPI does not deploy. Attack surface for the client library is narrower,
but Dependabot flags on package presence regardless.

| Severity | CVE | Summary |
|----------|-----|---------|
| Critical | CVE-2026-0545 | FastAPI `/ajax-api/3.0/jobs/*` endpoints missing authN/authZ |
| Critical | CVE-2025-15379 | Command Injection |
| Critical | CVE-2025-15036 | Path traversal |
| Critical | CVE-2026-2635 | Default password authentication bypass |
| High | CVE-2026-2033 | Tracking server artifact handler directory traversal RCE |
| High | CVE-2025-15381 | Tracing + Assessments unauthorized access |
| High | CVE-2025-15031 | Arbitrary file write via tar traversal |
| High | CVE-2025-14287 | Command injection in `mlflow/sagemaker/__init__.py` |
| High | CVE-2025-10279 | Temp file created in directory with insecure permissions |
| High | CVE-2025-14279 | DNS rebinding — missing Origin header validation |
| High | CVE-2024-37059 | Unsafe deserialization |
| Medium | CVE-2026-33865 | Stored XSS via YAML parsing of MLmodel artifacts |
| Medium | CVE-2026-33866 | AJAX endpoint authorization bypass |

**Recommended fix path** (in order of preference):

1. **Remove mlflow from the runtime/training paths** — replace 3 `log_metric`
   calls with structured logging (stdlib `logging` + JSON formatter, or
   OpenTelemetry metrics from T2.4). This eliminates the entire dependency.
   Roughly 10 lines of code change + requirement removal.
2. If the founder wants to keep mlflow for experimentation, move it to a
   `requirements-dev.txt` / extras group so it's not in the production
   wheel. Bump pin to latest fixed version: `mlflow>=3.x,<4.0` (verify
   latest at time of work; check release notes for CVE coverage).
3. Document in `docs/operations/security-trust-chain.md` that the MLflow
   **server** is never deployed inside the BPI cluster — only the client
   library is used, and only in training-time CI jobs.

**cryptography (3 alerts)** — pinned `cryptography>=42.0.0,<44.0` in
`requirements.txt`. Used throughout for HMAC, AES-GCM, license tokens,
secure_pickle. Load-bearing.

| Severity | CVE | Summary |
|----------|-----|---------|
| High | CVE-2026-26007 | Missing subgroup validation for SECT elliptic curves — subgroup attack |
| Low | CVE-2026-34073 | Incomplete DNS name constraint enforcement on peer names |
| Low | CVE-2024-12797 | Vulnerable OpenSSL bundled in cryptography wheels |

**Recommended fix path**:

1. Verify current latest `cryptography` release patches all three (expect
   46.x as of April 2026). Read upstream CHANGELOG for the three CVE IDs.
2. Bump upper bound in `requirements.txt`: `cryptography>=44.0.0,<47.0`
   (or whatever the next-major-minus-one is at the time of the work).
3. Re-run full test suite — cryptography touches HMAC paths that must
   stay signature-compatible for existing license tokens. If the bump
   changes any canonical output (unlikely but possible), coordinate with
   CIPHER before merging.
4. Audit the codebase for SECT curve usage specifically (the high-sev
   CVE). If we're on NIST P-256 / P-384 or Curve25519 everywhere (which
   is the likely case — SECT curves are rare in modern crypto), the
   subgroup attack does not apply to us and the bump is just upstream
   hygiene.

**Verification step**: after the bumps land, push to main and confirm
Dependabot closes the alerts on the next scan. Remaining alerts (if any)
must be explicitly dismissed with justification, not ignored.

**Agent ownership**: CIPHER primary (crypto boundary + security posture),
FORGE secondary (dependency hygiene + CI impact). QUANT does not sign —
this is not financial math. REX does not sign — this is not regulatory.

### Tier 3 — Infrastructure hardening

- **Cloud deployment**: pick GCP or AWS, provision via Terraform (not yet written) or extend Helm charts. GCP is probably the right pick for Canadian/US data residency flexibility; AWS is the bank-familiar option. FORGE makes the call.
- **CI**: 11 pipelines exist. Add a nightly "contract-test" pipeline that spins up the full stack against synthetic pilot-bank traffic.
- **Secrets management**: move any remaining local `.env` references to SOPS or GCP Secret Manager / AWS Secrets Manager.

### Out of scope

- Business blockers (RBC IP clause, patent filing, pilot License Agreement, pre-seed capital) — these are not code.
- Further code review — B1–B13 closed everything Critical + most Highs.
- Backwards-compat shims — the codebase is pre-pilot; refactor freely.

---

## Part 4 — Suggested phasing

| Phase | Scope | Estimated duration (AI-driven) |
|-------|-------|-------------------------------|
| **Phase 0 — T2.5 (Dependabot CVE remediation)** | Smallest, fastest, clears 16 open alerts on main. Unblocks clean security posture before any other work. | 0.5–1 day |
| **Phase 1 — T1.1 (CBDC normalizer)** | Smallest patent code. Gets a win on the board. | 2–3 days |
| **Phase 2 — T2.1 + T2.2 (Kafka + Redis production wiring)** | Pilot-go-live prerequisite. Founder-valuable. | 3–5 days |
| **Phase 3 — T1.2 (P4 Federated Learning)** | Biggest patent payoff; depends on DP machinery already hardened. | 4–6 days |
| **Phase 4 — T1.3 (Extensions B + G + A in that order)** | Patent-continuation defensibility. Can run in parallel with Phase 5. | 6–8 days |
| **Phase 5 — T2.3 + T2.4 (mTLS + observability)** | Pilot-go-live prerequisite. | 3–4 days |
| **Phase 6 — T3 (cloud deployment)** | Founder + FORGE together. Externally-dependent (cloud account provisioning). | 2–4 weeks including procurement |

**Why Phase 0 goes first:** clearing the Dependabot board is a ~half-day of
work that removes a persistent red banner on the GitHub repo and a real (if
narrow) attack surface. Every subsequent phase adds code; starting with a
clean security posture means any *new* alerts that appear during Phases 1–6
are attributable to new code, not pre-existing debt. It is also the lowest
risk: no canonical-constant changes, no patent-language concerns, no ML
retraining.

Total AI-driven code time: ~3–4 weeks of session-by-session work. Phases 1–5
all happen in terminal; Phase 6 requires cloud account + some founder
involvement.

---

## Part 5 — How the next AI should orient

The next session starts from empty context. Before writing any code, the AI
must do its own research. This is not hand-holding; it is the Ford Principle.
An AI that skips orientation and writes code will hit the same class of
mistake the user called out in `feedback_verify_semantics_before_assessment.md`.

### Orientation checklist (the prompt in Part 7 instructs the AI to complete this)

- [ ] Read `/Users/tomegah/PRKT2026/CLAUDE.md` in full.
- [ ] Read `/Users/tomegah/PRKT2026/PROGRESS.md` — current sprint state.
- [ ] Read `/Users/tomegah/PRKT2026/docs/business/Project-Status-Report-2026-04-11.md` — strategic context.
- [ ] Read `/Users/tomegah/PRKT2026/docs/engineering/review/2026-04-08/RESOLUTION-STATUS.md` — what was closed.
- [ ] Read `/Users/tomegah/PRKT2026/docs/engineering/Next-Session-Production-Push-Plan.md` — this file.
- [ ] Read `/Users/tomegah/PRKT2026/docs/legal/patent/patent_claims_consolidated.md` — what P4 and P5 actually claim.
- [ ] Read `/Users/tomegah/PRKT2026/docs/legal/patent/Future-Technology-Disclosure-v2.1.md` — Extensions A–G detail.
- [ ] Read `/Users/tomegah/PRKT2026/docs/engineering/default-execution-protocol.md` — codex/* branch workflow, plan-before-implement, draft-PR-by-default.
- [ ] Run: `git log --oneline -40` — see latest commits.
- [ ] Run: `ls lip/` — see module layout.
- [ ] Run: `python -m pytest lip/tests/ -m "not slow" --co -q | head -50` — get a feel for the test surface.
- [ ] Read `lip/common/constants.py` — all canonical values.
- [ ] Read `lip/common/block_codes.json` — EPG-19 consolidated list.
- [ ] Read `lip/p10_regulatory_data/anonymizer.py` — reference for DP machinery before implementing T1.2.
- [ ] Read `lip/c5_streaming/stress_regime_detector.py` — reference point for T1.1.
- [ ] Read `lip/p5_cascade_engine/cascade_propagation.py` — reference point for Extension B.
- [ ] Pull live Dependabot list via `gh api repos/ryanktomegah/PRKT2026/dependabot/alerts --paginate` — verify the 2026-04-11 snapshot in T2.5 is still accurate.

Total orientation: 45–75 minutes of reading. This is mandatory.

### What the AI should NOT do

- Do **not** trust this doc over the actual code. If this doc says "X is at
  path Y" and Y doesn't exist, read the code and surface the discrepancy.
  This doc was written 2026-04-11; file paths may drift.
- Do **not** start implementing without picking ONE phase first and drafting
  a design plan the founder can approve.
- Do **not** file or draft patents — that is a legal-counsel task, not a
  code task. Patent code is here to support existing claims, not to write
  new ones.
- Do **not** touch the RBC IP clause or pilot License Agreement — those are
  legal-counsel tasks. Flag them if related; don't try to resolve them.
- Do **not** assume the founder is technical. Write plans in plain language.
  When you must show code, explain it. Use the Ford Principle — restate what
  you heard, flag ambiguity, propose approach, flag trade-offs, wait for OK.

---

## Part 6 — Verification and sign-off protocol per phase

Each phase in Part 4 ends with:

1. `ruff check lip/` — zero errors.
2. `python -m pytest lip/tests/ -m "not slow"` — green.
3. Full suite (~12 min) on CI.
4. Draft PR on `codex/phase-N-<slug>` branch.
5. Commit + push at phase completion (feedback_push_to_github.md).
6. Founder review of the PR description, not the diff.
7. Merge on founder OK.
8. Update `PROGRESS.md` with what landed.

Per-phase agent sign-offs required:

| Phase | Must sign | Why |
|-------|-----------|-----|
| T1.1 CBDC | NOVA (payments protocol), REX (regulatory disclosure of CBDC handling) | CBDC ingest crosses jurisdictional regulatory lines |
| T1.2 Federated Learning | ARIA (ML), QUANT (DP noise math), CIPHER (crypto boundary), REX (data-card update) | Four-way sign-off — this is the highest-risk item |
| T1.3 Extensions | REX (patent-language scrub — no AML/SAR/OFAC/PEP in code comments either) | EPG-20/21 scope extends to code comments that may end up in published artifacts |
| T2.1 Kafka | FORGE | Pipeline infrastructure |
| T2.2 Redis | CIPHER (no AML state written in plaintext), FORGE | Multi-replica state + security |
| T2.3 mTLS | CIPHER, FORGE | Certificate trust chain |
| T2.4 Observability | FORGE, CIPHER (ensure no PII/UETR leaked to logs unhashed) | Logs can leak |
| T2.5 Dependabot CVEs | CIPHER (crypto boundary), FORGE (dep hygiene + CI) | 16 open alerts; mlflow + cryptography bumps |
| T3 Cloud | FORGE, CIPHER (provider security posture), REX (data residency) | Picking a cloud crosses regulatory lines |

---

## Part 7 — The paste-ready prompt for the next session

Copy everything between the `<<<BEGIN>>>` and `<<<END>>>` markers into a fresh
Claude Code terminal session. Do not edit it — it is self-contained.

```text
<<<BEGIN>>>

You are picking up the BPI / LIP codebase mid-flight. The founder is Ryan
Tomegah — strategic, non-technical. He runs the Ford Principle: your job is
not to execute orders but to translate direction into correct technical
decisions and push back before implementing anything flawed.

## Your first task: orient yourself

Do not write code yet. Do not propose a plan yet. Do the following reads in
order and build your own mental model:

1. Read /Users/tomegah/PRKT2026/CLAUDE.md — full file, no skimming.
2. Read /Users/tomegah/PRKT2026/PROGRESS.md — current sprint state.
3. Read /Users/tomegah/PRKT2026/docs/business/Project-Status-Report-2026-04-11.md
   — strategic context, pilot blockers, replacement-cost analysis.
4. Read /Users/tomegah/PRKT2026/docs/engineering/review/2026-04-08/RESOLUTION-STATUS.md
   — all Critical code-review findings are closed. Do not re-raise them.
5. Read /Users/tomegah/PRKT2026/docs/engineering/Next-Session-Production-Push-Plan.md
   — your scope (Option C), phasing, per-phase sign-off requirements.
6. Read /Users/tomegah/PRKT2026/docs/legal/patent/patent_claims_consolidated.md
   — what P4 Federated Learning and P5 CBDC actually claim.
7. Read /Users/tomegah/PRKT2026/docs/legal/patent/Future-Technology-Disclosure-v2.1.md
   — Extensions A–G detail.
8. Read /Users/tomegah/PRKT2026/docs/engineering/default-execution-protocol.md
   — codex/* branch workflow; plan-before-implement; draft-PR-by-default.
9. Run: git -C /Users/tomegah/PRKT2026 log --oneline -40.
10. Run: ls /Users/tomegah/PRKT2026/lip/ and note the module layout.
11. Read /Users/tomegah/PRKT2026/lip/common/constants.py — canonical values.
12. Read /Users/tomegah/PRKT2026/lip/common/block_codes.json — EPG-19 list.
13. Read /Users/tomegah/PRKT2026/lip/p10_regulatory_data/anonymizer.py — the
    DP machinery you'll reuse if you tackle P4 Federated Learning.
14. Read /Users/tomegah/PRKT2026/lip/c5_streaming/stress_regime_detector.py —
    reference point if you tackle CBDC normalizer.
15. Read /Users/tomegah/PRKT2026/lip/p5_cascade_engine/cascade_propagation.py —
    reference point if you tackle Extension B (supply-chain cascades).
16. Pull live Dependabot alerts to verify the 2026-04-11 snapshot is still
    current:
      gh api repos/ryanktomegah/PRKT2026/dependabot/alerts --paginate \
        -q '.[] | select(.state == "open") |
            "\(.security_advisory.severity)|\(.dependency.package.ecosystem)|
             \(.dependency.package.name)|
             \(.security_advisory.cve_id // .security_advisory.ghsa_id)|
             \(.security_advisory.summary)"'
    Expect mlflow (13) and cryptography (3) dominating. If the list has
    materially changed, treat the live output as source of truth and
    flag the drift to the founder.

Also check the founder's auto-memory at
/Users/tomegah/.claude/projects/-Users-tomegah/memory/MEMORY.md
and each file it links. This gives you the founder's preferences and context
from prior sessions (RBC employment status, IP clause concerns, income
classification rules, fee decomposition rules, autonomy grant: make technical
decisions yourself).

When you finish orientation, report back to the founder with:
- What you understand the scope to be (Option C per the plan doc).
- Which phase you propose to start with and why. The plan's Part 4
  recommends Phase 0 = T2.5 Dependabot CVE remediation (half-day, clears
  the security board before new code lands). Phase 1 = CBDC normalizer
  is the smallest patent-code item if you prefer to start there. Disagree
  with either recommendation if you have a reason.
- The single most important clarifying question, if any. Not ten — one.
- The agent sign-offs you'll need for your proposed phase.

## Your scope (Option C)

Tier 1 — Patent code:
  T1.1 P5 CBDC normalization layer (new module: lip/c5_streaming/cbdc_normalizer.py)
  T1.2 P4 Federated Learning (new package: lip/p4_federated_learning/)
  T1.3 Continuation Extensions B, G, A (in that order)

Tier 2 — Phase-2 production stubs:
  T2.1 Kafka production wiring (confluent_kafka producer, idempotent config)
  T2.2 Redis-backed multi-replica state (C8 metering, Rust velocity, C6 structuring)
  T2.3 mTLS everywhere + cert-manager
  T2.4 Observability (Prometheus/Grafana wiring, OTel tracing, UETR in logs)
  T2.5 Dependabot CVE remediation — 16 open alerts on main (4 crit, 8 high,
       2 med, 2 low). Two packages: mlflow (13 alerts; client-only usage,
       consider removing) and cryptography (3 alerts; load-bearing, bump
       upper version bound). Full CVE table and fix paths in plan doc
       section T2.5. CIPHER + FORGE sign.

Tier 3 — Infrastructure:
  T3 Cloud deployment (GCP or AWS — FORGE picks)

Suggested phasing in plan doc Part 4. Recommended starting point is
**Phase 0 = T2.5 Dependabot remediation** — half-day of work that clears
the security board before any new code lands, so future alerts are
attributable to new code rather than pre-existing debt.

Deliver phase-by-phase, not all at once. Each phase ends with a codex/*
branch, draft PR, commit+push, and founder OK.

## Hard constraints (do not negotiate)

- 300 bps fee floor. Never below. QUANT is the final authority.
- EPG-19: never bridge compliance holds. Single BLOCK list in
  lip/common/block_codes.json — do not create another copy.
- EPG-20/21: no "AML", "SAR", "OFAC", "SDN", "PEP", "tipping-off" in any
  patent-related code comment or published artifact. Use "classification
  gate", "hold type discriminator", "bridgeability flag".
- Never commit secrets, AML typology patterns, or model binaries.
- `assert` is banned for load-bearing invariants — use explicit raise.
- ruff check lip/ must be zero errors before commit.
- python -m pytest lip/tests/ must be green before commit.
- Never --no-verify, never --force to main.
- Every phase: codex/phase-N-<slug> branch, commit, push, draft PR.
- Make technical decisions yourself — the founder is non-technical.
  But for anything that changes canonical constants, affects AML logic,
  or changes patent-language scope, get the responsible agent sign-off
  named in plan doc Part 6 before merging.

## The Ford Principle

Before any non-trivial change:
1. State what you understand the request to be. Flag ambiguity.
2. Ask one clarifying question if something is unclear — just one.
3. State your intended approach and why — include trade-offs.
4. Flag any risk, canonical-constant conflict, or disagreement with
   the stated approach.
5. Only then implement.

An agent that executes a bad instruction has failed even if the code runs.

## What NOT to do

- Do not re-run the 2026-04-08 code review; it is closed.
- Do not touch the RBC IP clause or pilot License Agreement — legal tasks.
- Do not file or draft patents — legal-counsel tasks.
- Do not add features beyond what Option C scopes.
- Do not ship all phases in one mega-PR. One phase at a time.
- Do not assume any file path in the plan doc is still valid — verify.

## Ready check

When you have finished orientation, confirm by writing a short message to
the founder that covers:
- One sentence: what you understand the project to be.
- One sentence: which phase you propose to start with and why.
- Zero or one clarifying questions.
- Required sign-offs for your chosen phase.

Then wait for the founder's go-ahead. Do not write code before the founder
says go. Once go: produce a design plan, get approval, then implement.

<<<END>>>
```

---

## Part 8 — What the founder should do between sessions

1. **Do not** start implementing anything from this plan yourself — wait for
   the next AI session.
2. **Do** read the `Project-Status-Report-2026-04-11.md` and the
   `RESOLUTION-STATUS.md` file so you can answer the AI if it asks
   clarifying questions.
3. **Do** confirm that the pilot-blocker legal work (RBC IP clause, P1
   provisional, License Agreement) is in motion with counsel — Option C is
   technical defensibility work, not a substitute for the legal path.
4. **Do** pick one of Phase 1 (CBDC normalizer, safest win) or Phase 2
   (Kafka+Redis production wiring, pilot-go-live prerequisite) as the
   starting phase for the next AI — or let the AI pick via Ford Principle.
5. **Do** capitalize the patent-counsel engagement ($15K–$25K first tranche)
   even if code work on Option C is in flight — the code supports the
   claims but the priority date comes from the filing.

---

## Part 9 — Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-04-11 | Initial draft after B1–B13 sprint closure | Claude Opus 4.6 |
| 2026-04-11 | Add T2.5 (Dependabot CVE remediation — 16 open alerts); insert Phase 0 at front of phasing table; update paste-ready prompt and orientation checklists to reference live Dependabot fetch | Claude Opus 4.6 |
