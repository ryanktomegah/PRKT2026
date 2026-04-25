# Pre-Lawyer Review — Complete Code Quality, Product QA, and IP Readiness Audit

**Status:** Approved for planning
**Date:** 2026-04-17
**Owner:** Ryan (founder) — execution by Claude Code autonomously
**Target end date:** 2026-05-15 (4 weeks)

---

## 1. Context

Ryan is preparing to meet with multiple lawyers to address the full pre-commercial legal stack:

- **IP / patent counsel** — patent filing (provisional → non-provisional)
- **Employment counsel** — RBC IP assignment clause exposure (RBC start: 2026-01-12)
- **Corporate counsel** — NewCo formation and IP assignment
- **Litigation / pre-litigation counsel** — readiness for a potential RBC dispute

The primary driver of the review, however, is **code and product quality**: Ryan wants an honest audit of LIP (Liquidity Intelligence Platform) before it becomes commercially load-bearing.

A critical timing fact surfaced during scoping:

- First commit: **2026-02-27** — ~6 weeks AFTER RBC employment start
- Pre-RBC commits: **0**
- Post-RBC commits: **548**
- Authors: Ryan (3 git identities: `Ryan`, `YESHA`, `Tomegah Ryan`), `Claude`, `Copilot`, `github-actions`, `git stash`

This reshapes priorities — employment/IP-clause risk dominates because the git timeline provides zero timestamp evidence of pre-employment conception. Counsel will need non-git evidence to establish prior conception.

## 2. Scope decisions

| Decision | Choice | Rationale |
|---|---|---|
| Lawyer types | All four (IP, employment, corporate, litigation) | Master packet addresses each |
| Timeline | 3–4 weeks (thorough) | Approved Option C; investor/lawyer-grade due-diligence packet |
| Approach | **A: Risk-first triage** | Biggest risk (IP/timing) surfaces first; re-scope possible if dealbreakers found |
| Fix authority | **Autonomous for all fixes** | Per `feedback_cto_autonomy.md` |
| Red-Flag Register location | **Local-only** (`docs/legal/.red-flag-register.md`, gitignored) | Public-repo + discovery risk |
| Day-28 walkthrough format | Written walkthrough doc (user reads at own pace, responds inline) | Default |

## 3. Deliverables

Four outputs, two for user / two for lawyers:

### 3.1 Master Lawyer Packet
Hand-off artifact for the lawyer meeting.
- **Executive summary** — 2 pages, plain-English, non-technical
- **Part A — IP & Timing Dossier** — patent readiness, RBC exposure, chain-of-title
- **Part B — Third-Party & License Audit** — deps, AI contributions, license compliance
- **Part C — Product Readiness Verdict** — claims vs. reality, demo-readiness
- **Part D — Code Quality Report Card** — module grades, critical fixes, tests
- **Part E — Appendices** — commit forensics, prior-art log, evidence timeline, prior conception index

### 3.2 Fix Log
Running record of issues found and fixes applied directly to code. Each entry: problem, severity, fix commit, verification.

### 3.3 Inventor's Notebook Bootstrap
Reconstructed timeline of conception + reduction-to-practice evidence (pre-RBC and post-RBC), gathering non-git evidence: chats, emails, Notion/Notes, voice memos, etc.

### 3.4 Red-Flag Register
Confidential list of risky-but-unresolved items. Categorized by privilege (attorney work-product candidates vs. produceable facts). **Local-only, gitignored.**

### 3.5 Storage

```
docs/legal/pre-lawyer-review/2026-04-17/    ← Master Lawyer Packet (Parts A, B, E)
docs/engineering/review/2026-04-17/          ← Parts C, D (code + product review)
docs/legal/inventors-notebook/               ← Evidence bootstrap
docs/legal/.red-flag-register.md             ← Sensitive findings (LOCAL-ONLY, gitignored)
docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md  ← This document
```

## 4. Week-by-week plan

### Week 1 — IP & Timing Audit (Days 1–7)

**Day 1 — Commit forensics.**
Timestamp every commit vs. RBC start. Author pattern analysis. Consolidate 3 git identities via `.mailmap`. Output: `appendix-commit-forensics.md`.

**Day 2 — RBC contamination scan.**
Grep for `RBC`, `Royal Bank`, RBC BIC codes, employee names, RBCx, Transaction Banking, internal system names, AI Group, Bruce Ross, client names. Cross-reference EPG decisions. Review bank-pilot kit for RBC-internal-only info. Output: contamination log with severity per finding.

**Day 3 — Patent language scrub (EPG-21).**
Verify no `AML`, `SAR`, `OFAC`, `SDN`, `compliance investigation`, `tipping-off`, `suspicious activity`, `PEP` in patent-published materials. Classify docs as "publishable" vs "internal-only". Verify BLOCK code list not enumerated in published claims. Fix violations directly. Output: scrub report with before/after.

**Day 4 — AI-agent contribution inventory.**
Classify every Claude/Copilot commit as (a) user-directed, (b) autonomous cleanup, (c) original creative authorship. Map each patent claim to human-directed commits. Flag Thaler v. Vidal inventorship risk. Output: inventorship matrix + remediation list.

**Day 5 — Prior-art & prior-conception evidence hunt.**
Verify external prior art (US7089207B1 JPMorgan, ISO 20022, Damodaran, Altman Z') completeness. User produces non-git evidence (chats, emails, Notion/Notes, LinkedIn, photos) via one-page questionnaire. Output: evidence inventory + gaps list.

**Day 6 — Chain-of-title draft.**
Contributor ledger. Third-party content (Damodaran, Altman Z', LightGBM, Qwen3, TabTransformer, GraphSAGE) + licenses. NewCo assignment prep. Output: chain-of-title draft.

**Day 7 — Consolidation + pause.**
Assemble IP & Timing Dossier v1. Populate Red-Flag Register. Git push. User review checkpoint. Re-scope if dealbreakers found.

**Pre-Week 1 action items for user:**
1. Prior-conception evidence search (~30 min): old ChatGPT/Claude chats, Notion, Notes, emails, LinkedIn DMs — anything pre-2026-02-27, ideally pre-2026-01-12, showing thinking about payment failures, SWIFT, or bridge lending.

### Week 2 — Code Quality Deep Dive (Days 8–14)

**Day 8 — Meta-checks.**
Run full test suite. Verify README's "1284 tests, 92% coverage". `ruff check lip/` zero errors. `mypy lip/`. `bandit -r lip/`. Coverage breakdown per module.

**Day 9 — Dependency & license audit.**
`pip-audit`, `safety check`. License scan (LightGBM, PyTorch, Qwen3/Groq ToS for regulated finance, Damodaran data, Altman Z'). `cargo audit` C3/C6. `govulncheck` C5/C7. Verify `artifacts/` and `c6_corpus_*.json` gitignored.

**Day 10 — Core infrastructure.**
`pipeline.py` (1107 lines) — trace 94ms SLO-critical path before any split. `common/` — QUANT constants single-source. `api/` — authN/Z, validation, rate limits. `integrity/` — invariants + failure-path tests.

**Day 11 — Security-critical: C6 + C8.**
C6: Rust velocity counters FFI boundary, salt rotation (365d/30d), OFAC/EU list freshness, EPG-16 unlimited-cap guard. C8: HMAC-SHA256, key storage, boot validation, revocation, replay protection, EPG-17 token shape. Corpus hygiene. `gitleaks` history scan.

**Day 12 — Financial math: C2 + fee + P5.**
C2: Merton/KMV, Damodaran beta, Altman Z' — read source implementations, verify field semantics. Fee floor enforcement every code path clamps at 300 bps. CLASS_B label correctness (systemic/processing, not AML). P5 cascade propagation bounds.

**Day 13 — ML models: C1, C4, C9, dgen.**
C1: GraphSAGE + TabTransformer + LightGBM — label leakage, data leakage, OOT validation, SR 11-7 model card completeness. C4: Qwen3-32B/Groq prefilter + LLM, negation handling, 100+ case validation, `/no_think` system prompt. C9: model card + metrics. dgen: field semantics from generator source, calibration citations.

**Day 14 — Polyglot bridges + consolidation.**
C3 Rust FSM: state-machine correctness, panic safety, unsafe blocks. C5 Go consumer: ingestion, back-pressure. C7 Go gRPC: offer router, kill switch, latency budget. Assemble Code Quality Report Card (Part D): A–F per module on correctness / tests / security / performance / maintainability.

**Fix policy:**

| Severity | Example | Action |
|---|---|---|
| Critical | Committed secret, SQL injection, auth bypass, incorrect fee formula | Fix same day, commit individually, Fix Log entry |
| High | Test failure, silent data corruption, CVE in used dep | Fix within Week 2 |
| Medium | Oversized file, missing type hints, flaky timing test | Week 4 fix list |
| Low | Style, docstring gaps | Note only |

### Week 3 — Product & Integration (Days 15–21)

**Day 15 — End-to-end pipeline test.** `docker compose up -d`, init Kafka topics, feed synthetic `pacs.002`, trace C1→C6→C2→C7 live (`test_e2e_live.py`). Output: E2E trace + go/no-go verdict.

**Day 16 — SLO & performance validation.** Latency P99 ≤94ms under load. Isolate flaky `test_slo_p99_94ms` from real regressions. Throughput. Reconcile against `benchmark-results.md`.

**Day 17 — Infrastructure & CI/CD.** K8s/Helm, Grafana, `.github/workflows/`, MLflow, secrets plumbing. `gh run list` CI health.

**Day 18 — Model validation.** Run C1 against `artifacts/production_data_dryrun/`. Verify claimed AUC/precision/recall. OOT validation. Model cards match reality.

**Day 19 — Demo & pilot readiness.** Walk `docs/business/bank-pilot/` as a banker. License Agreement template for `hold_bridgeable` flag (EPG-04/05). MRFA B2B clause (EPG-14). Demo-ready checklist + gaps.

**Day 20 — Compliance & governance.** SR 11-7, EU AI Act Art.14 (EPG-18), DORA, data cards, audit trails, EPG Decision Register (EPG-04 through EPG-21).

**Day 21 — Consolidation + pause.** Assemble Product Readiness Verdict (Part C), refine Part B. Update Red-Flag Register. Git push. User review checkpoint.

### Week 4 — Synthesis & Master Packet (Days 22–28)

**Day 22 — Patent claim-to-code mapping.** For every claim, locate implementing code. Gaps = narrow claim OR complete code (enablement).

**Day 23 — Inventor's Notebook finalization.** Timestamped narrative: conception → reduction-to-practice → first commit → post-RBC continuation.

**Day 24 — Fix Week 4 punch list.** Medium-severity items deferred from Weeks 2–3.

**Day 25 — Executive summary.** 2-page plain-English front matter: what LIP is, code-quality verdict, product-readiness verdict, top 5 IP risks, top 5 counsel actions.

**Day 26 — Master Packet assembly.** Parts A–E + exec summary. Cross-links, TOC, version stamp, signing block. PDF export.

**Day 27 — Red-Flag Register finalization.** Close items, categorize by privilege, archive resolved.

**Day 28 — Walkthrough doc for user.** Written Q&A walkthrough: likely user questions pre-answered, inline follow-up for anything unclear.

## 5. Operating protocol

### From saved feedback (applies across all weeks)
- Sequential subagent dispatch (never 3+ in parallel).
- Git push at end of each sprint (contribution graph stays current).
- Autonomous technical calls (no per-decision check-ins).
- Verify semantics from source before assessing code/data.
- Meta-rule: any caught mistake produces a generalized CLAUDE.md rule.

### Checkpoints (4 scheduled)
- End of Day 7 — before Week 2
- End of Day 14 — before Week 3
- End of Day 21 — before Week 4
- End of Day 28 — before packet goes to counsel

### Escalation triggers (stop + message user immediately)
1. RBC contamination in patent-claim-critical code or docs.
2. EPG-21 banned language already externally published (blog, LinkedIn, public filing).
3. Third-party license materially blocks commercial pilot path (e.g., Qwen3/Groq ToS forbids regulated-finance production).
4. Security finding suggesting key/corpus/secret already exposed publicly.
5. Any destructive or irreversible action (git history rewrites, force-push to `main`, branch deletion) — **never taken without explicit user approval even under autonomy**.

### Non-escalation (handle silently, report at checkpoint)
Bug fixes, test additions, refactors, lint, language scrubs, dep bumps, doc edits, `.mailmap` consolidation.

### Communication cadence
- End of each day: one-line Fix Log entry.
- End of each week: checkpoint doc with findings + next-week preview.
- On escalation: direct message with `STOP — need decision` prefix.

### Task tracking
Live task list via TaskCreate, one task per day's workstream. Names map 1:1 to this plan.

## 6. Definition of done

- Master Lawyer Packet (Parts A–E + exec summary) committed to `docs/legal/pre-lawyer-review/2026-04-17/` and PDF-exported.
- Fix Log reflects every code change made during the review.
- Inventor's Notebook populated with user-surfaced evidence.
- Red-Flag Register local-only, closed items archived.
- Contributor ledger clean, `.mailmap` in place.
- Four scheduled checkpoints all signed off.
- `git push` current.

## 7. Open items / risks

- **User must surface pre-2026-02-27 evidence in Week 1 Day 5.** If none exists, patent strategy shifts to "conceived but undocumented" (weaker ground) — counsel call.
- **If Day 1–2 confirm RBC contamination in claim-critical code**, we re-scope before investing in code quality review.
- **If Day 17 finds secrets in git history**, remediation (BFG, filter-repo) affects the commit timeline which is itself evidence — requires explicit user approval.
- **Groq / Qwen3 ToS** is an unknown-unknown until Day 9. If it forbids regulated-finance production, the C4 architecture may need a fallback path before any pilot.
