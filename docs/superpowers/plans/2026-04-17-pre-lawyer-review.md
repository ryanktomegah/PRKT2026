# Pre-Lawyer Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the 4-week pre-lawyer review audit defined in `docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md` — delivering a Master Lawyer Packet, Fix Log, Inventor's Notebook, and Red-Flag Register.

**Architecture:** Risk-first triage over 4 sequential weeks: (1) IP & timing audit, (2) code quality deep dive, (3) product & integration, (4) synthesis. Fixes applied inline with frequent commits; findings captured in structured deliverables under `docs/legal/pre-lawyer-review/` and `docs/engineering/review/`. Four scheduled user checkpoints gate progression between weeks.

**Tech Stack:** Python 3.13, pytest, ruff, mypy, bandit, pip-audit, safety, gitleaks, Rust/cargo, Go/govulncheck, Docker, Kafka (Redpanda), Redis, MLflow, gh CLI, git.

**Spec reference:** `docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md`

---

## Preconditions (before starting Day 1)

- Working directory: `/Users/tomegah/PRKT2026`
- Branch: `codex/pre-lawyer-review` (already created, tracking `origin/codex/pre-lawyer-review`)
- User must surface pre-2026-02-27 (ideally pre-2026-01-12) evidence of LIP conception for Day 5. Direct message sent at end of Day 1 checkpoint.

---

# WEEK 1 — IP & TIMING AUDIT (Days 1–7)

## Day 1 — Scaffolding + Commit Forensics

### Task 1.1: Scaffold review directory structure

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/README.md`
- Create: `docs/engineering/review/2026-04-17/README.md`
- Create: `docs/engineering/review/2026-04-17/FIX_LOG.md`
- Create: `docs/legal/inventors-notebook/README.md`
- Create: `docs/legal/.red-flag-register.md` (local-only)
- Modify: `.gitignore` (add `docs/legal/.red-flag-register.md`)

- [ ] **Step 1: Add Red-Flag Register to `.gitignore`**

Append to `.gitignore`:
```
# Pre-lawyer review — local-only sensitive findings
docs/legal/.red-flag-register.md
```

- [ ] **Step 2: Verify ignore works**

Run: `git check-ignore -v docs/legal/.red-flag-register.md`
Expected: `.gitignore:<line>:docs/legal/.red-flag-register.md	docs/legal/.red-flag-register.md`

- [ ] **Step 3: Create `docs/legal/pre-lawyer-review/2026-04-17/README.md`**

```markdown
# Pre-Lawyer Review — 2026-04-17

Master Lawyer Packet output directory.

## Contents (populated during Week 4 synthesis)
- `executive-summary.md` — 2-page plain-English verdict (Day 25)
- `part-a-ip-timing-dossier.md` — IP & timing (Week 1 → Day 26)
- `part-b-third-party-license-audit.md` — deps, AI contributions, licenses (Weeks 1–2 → Day 26)
- `part-c-product-readiness-verdict.md` — claims vs. reality (Week 3 → Day 26)
- `part-d-code-quality-report-card.md` — module grades (Week 2 → Day 26)
- `part-e-appendices/` — commit forensics, prior-art, evidence timeline

Design: `docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md`
Plan: `docs/superpowers/plans/2026-04-17-pre-lawyer-review.md`
```

- [ ] **Step 4: Create `docs/engineering/review/2026-04-17/README.md`**

```markdown
# Code & Product Review — 2026-04-17

Technical review outputs. Feeds Parts C and D of the Master Lawyer Packet.

## Contents
- `FIX_LOG.md` — chronological record of fixes applied during the review
- `week-1-ip-timing/` — IP/timing audit evidence
- `week-2-code-quality/` — per-module code quality reports
- `week-3-product-integration/` — E2E, SLO, infra, model validation
- `week-4-synthesis/` — patent claim-to-code map, executive summary drafts
```

- [ ] **Step 5: Create `docs/engineering/review/2026-04-17/FIX_LOG.md`**

```markdown
# Fix Log — Pre-Lawyer Review 2026-04-17

Chronological record of every code/doc change made during the 4-week review.

Format per entry:
```
## YYYY-MM-DD — short title
- **Severity:** Critical / High / Medium / Low
- **Problem:** what was wrong
- **Fix:** what was changed
- **Commit:** <hash>
- **Verification:** how we know it's fixed
```

---

(No entries yet — Day 1 of review.)
```

- [ ] **Step 6: Create `docs/legal/inventors-notebook/README.md`**

```markdown
# Inventor's Notebook — LIP Conception & Reduction-to-Practice

Timestamped narrative of invention conception, development, and reduction-to-practice.
Primary audience: patent counsel.

## Structure
- `README.md` — this file
- `timeline.md` — chronological narrative (populated Day 23)
- `evidence/` — non-git evidence (chats, emails, notes, screenshots) user surfaces in Day 5

## Key dates (anchor points)
- 2026-01-12 — Ryan's RBC employment start (IP clause attaches)
- 2026-02-27 — First commit to PRKT2026 repo
- 2026-04-17 — Review begins
```

- [ ] **Step 7: Create `docs/legal/.red-flag-register.md` (LOCAL-ONLY)**

```markdown
# Red-Flag Register — Pre-Lawyer Review 2026-04-17

**CONFIDENTIAL — LOCAL ONLY. NOT TRACKED IN GIT.**

Items categorized as attorney work-product candidates vs. produceable facts.
Flag by privilege before sharing with counsel.

Format per entry:
```
## [ID] — short title
- **Status:** Open / Resolved / Accepted
- **Privilege:** Work-product / Produceable / Undetermined
- **Finding:** what was discovered
- **Location:** file:line or commit hash
- **Severity:** Critical / High / Medium / Low
- **Resolution:** what was done, or plan
```

---

(No entries yet — Day 1 of review.)
```

- [ ] **Step 8: Verify Red-Flag Register is untracked**

Run: `git status docs/legal/.red-flag-register.md`
Expected: no output (ignored file is silent)

Run: `git status docs/legal/`
Expected: `docs/legal/inventors-notebook/`, `docs/legal/pre-lawyer-review/` listed as untracked; `.red-flag-register.md` NOT listed.

- [ ] **Step 9: Commit scaffolding**

```bash
git add .gitignore docs/legal/pre-lawyer-review/ docs/legal/inventors-notebook/ docs/engineering/review/
git commit -m "chore(review): scaffold pre-lawyer review directories and Fix Log"
```

- [ ] **Step 10: Verify Red-Flag Register NOT in commit**

Run: `git show --stat HEAD | grep -i red-flag`
Expected: no output.

---

### Task 1.2: Generate complete commit timeline

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline.csv`
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline-summary.md`

- [ ] **Step 1: Dump all commits (all branches) to CSV**

Run:
```bash
mkdir -p docs/engineering/review/2026-04-17/week-1-ip-timing
git log --all --format='%H|%ai|%an|%ae|%s' > docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline.csv
```

- [ ] **Step 2: Count by author**

Run:
```bash
git log --all --format='%ae' | sort | uniq -c | sort -rn
```

Capture output. Expected authors: `naumryan66@gmail.com`, `ryanktomegah@gmail.com`, `noreply@anthropic.com` (Claude), `198982749+Copilot@users.noreply.github.com`, `41898282+github-actions[bot]@users.noreply.github.com`, `git@stash`, `tomegah@Tomegahs-MacBook-Air.local`.

- [ ] **Step 3: Count commits per week since RBC start**

Run:
```bash
git log --all --format='%ai' --after='2026-01-12' | awk '{print $1}' | cut -c1-7 | sort | uniq -c
```

Capture monthly distribution.

- [ ] **Step 4: Identify commits during off-hours (after 6pm local or weekends)**

Run:
```bash
git log --all --format='%ai|%an|%h|%s' --after='2026-01-12' | awk -F'|' '
  {
    split($1, dt, " ");
    split(dt[2], tm, ":");
    hour = tm[1]+0;
    cmd = "date -jf \"%Y-%m-%d\" \"" dt[1] "\" +%u 2>/dev/null || echo 0";
    cmd | getline dow; close(cmd);
    if (dow >= 6 || hour < 9 || hour >= 18) print $0;
  }' > docs/engineering/review/2026-04-17/week-1-ip-timing/commits-off-hours.txt
```

- [ ] **Step 5: Write commit-timeline-summary.md**

Create `docs/engineering/review/2026-04-17/week-1-ip-timing/commit-timeline-summary.md` with:
- Total commits, date range, branches
- Author breakdown table (author | email | commit count | % of total)
- Monthly volume chart (text-based)
- Off-hours commit count and % of human-authored commits
- 3 git identities of same person — note consolidation plan via `.mailmap` (Task 1.3)

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/
git commit -m "docs(review): add commit timeline CSV and summary for IP audit"
```

---

### Task 1.3: Consolidate 3 git identities via `.mailmap`

**Files:**
- Create: `.mailmap`

- [ ] **Step 1: Identify the 3 identities**

From Task 1.2 output, confirm identities for Ryan:
- `Ryan <naumryan66@gmail.com>`
- `ryanktomegah <ryanktomegah@gmail.com>`
- `Tomegah Ryan <tomegah@Tomegahs-MacBook-Air.local>`
- `YESHA <ryanktomegah@gmail.com>` (same email as ryanktomegah, different name)

- [ ] **Step 2: Choose canonical identity**

Canonical: `Ryan Tomegah <naumryan66@gmail.com>` (matches user's email on file per auto-memory).

- [ ] **Step 3: Write `.mailmap`**

Create `.mailmap` at repo root:
```
# Canonical author mapping (see git-check-mailmap, .mailmap docs)
Ryan Tomegah <naumryan66@gmail.com> <ryanktomegah@gmail.com>
Ryan Tomegah <naumryan66@gmail.com> <tomegah@Tomegahs-MacBook-Air.local>
Ryan Tomegah <naumryan66@gmail.com> Ryan <naumryan66@gmail.com>
Ryan Tomegah <naumryan66@gmail.com> ryanktomegah <ryanktomegah@gmail.com>
Ryan Tomegah <naumryan66@gmail.com> YESHA <ryanktomegah@gmail.com>
Ryan Tomegah <naumryan66@gmail.com> Tomegah Ryan <tomegah@Tomegahs-MacBook-Air.local>
```

- [ ] **Step 4: Verify consolidation**

Run: `git shortlog -sne --all | head -10`
Expected: `Ryan Tomegah <naumryan66@gmail.com>` shows combined count of all 3 previous identities. Bot identities unchanged.

- [ ] **Step 5: Commit**

```bash
git add .mailmap
git commit -m "chore(review): consolidate contributor identities via .mailmap"
```

---

### Task 1.4: Write IP & Timing appendix draft

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/appendix-commit-forensics.md`

- [ ] **Step 1: Draft appendix-commit-forensics.md**

Content sections:
1. **Scope** — what was audited, date range, branches
2. **Headline numbers** — 0 pre-RBC commits, 548 post-RBC commits, first commit 2026-02-27
3. **Author breakdown** — table with canonical identities post-mailmap
4. **AI-agent contribution volume** — % by Claude, Copilot, github-actions
5. **Off-hours analysis** — what fraction of human commits fall outside 9–6 weekdays
6. **Identity consolidation note** — reference to `.mailmap` commit
7. **Flags for counsel** — list anything counsel should know

- [ ] **Step 2: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/appendix-commit-forensics.md
git commit -m "docs(review): write commit forensics appendix for IP audit"
```

---

## Day 2 — RBC Contamination Scan

### Task 2.1: Define search terms and run contamination sweep

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-search-terms.md`
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-contamination-findings.md`

- [ ] **Step 1: Define search term list**

Create `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-search-terms.md`:
```markdown
# RBC Contamination Search Terms

## Organization names
- `RBC`, `Royal Bank`, `Royal Bank of Canada`, `RBCx`, `RBC Capital Markets`
- `Transaction Banking`, `AI Group`
- `CNRC`, `Canadian Imperial Bank` (cross-reference mis-labels)

## People
- `Bruce Ross`, `Dave McKay`, `Neil McLaughlin`
- Names Ryan may have learned internally (flag any appearing in commit/doc text)

## Systems / products (public)
- `Signature`, `RBC Direct Investing`, `InvestEase`, `NOMI`, `Avion`
- `Interac`, `e-Transfer` (public but contextual — flag for review)

## Systems / products (internal — red flags)
- Internal codenames, sprint names, JIRA ticket prefixes

## BIC codes starting with `ROYC` (RBC-owned BIC)
- `ROYCCAT2`, `ROYCCAT2XXX`, `ROYCUS33`, etc.

## Employment metadata
- Ryan's RBC employee ID (unknown to us — counsel will probe)
- Job title fragments: `Credit Management Resolution Officer`, `Resolution Officer`
- RBC office locations
```

- [ ] **Step 2: Grep all source and docs**

Run using Grep tool (not `grep` Bash):
- Grep pattern: `RBC|Royal Bank|RBCx|Transaction Banking|Bruce Ross`
- Path: entire repo
- Output mode: `content` with line numbers
- Save results to `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-raw-matches.txt`

- [ ] **Step 3: Grep RBC BIC codes**

Grep pattern: `ROYC[A-Z0-9]{4,8}`
Save to `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-bic-matches.txt`

- [ ] **Step 4: Grep job title**

Grep pattern: `Credit Management Resolution Officer|Resolution Officer`
Save to `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-job-title-matches.txt`

- [ ] **Step 5: Classify every match**

For each match, classify as:
- **A — Acceptable:** RBC as a named pilot target (public info, e.g., in `bank-pilot/` kit)
- **B — Attention:** RBC mentioned in generic context (verify no internal info revealed)
- **C — Contamination:** Internal RBC info (systems, names, processes learned at RBC)

Write classification table to `docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-contamination-findings.md`.

- [ ] **Step 6: Commit search log (no fixes yet)**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-*.md docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-*.txt
git commit -m "docs(review): capture RBC contamination scan raw results"
```

---

### Task 2.2: Review bank-pilot kit for RBC-sourced info

**Files:**
- Read: `docs/business/bank-pilot/` (all files)

- [ ] **Step 1: List bank-pilot files**

Run Glob with pattern `docs/business/bank-pilot/**/*` — enumerate.

- [ ] **Step 2: Read each file and check sources**

For every claim about RBC (financials, strategy, contacts, internal structure), verify source is public:
- Public filings (10-K, annual report, press release)
- Public website (rbc.com, rbccm.com)
- News articles
- Conference talks

Any claim without a citable public source → flag as contamination in `rbc-contamination-findings.md`.

- [ ] **Step 3: Append findings**

Update `rbc-contamination-findings.md` with bank-pilot kit review section.

- [ ] **Step 4: Apply fixes (if any contamination found)**

For each C-classified (contamination) finding:
- **If severity Critical (internal systems, employee names):** Fix immediately. Commit per fix with message `fix(review): remove RBC-sourced content from <file>`.
- **If severity High/Medium:** Fix within Day 2.
- Add Fix Log entry per fix.
- Add Red-Flag Register entry per finding.

- [ ] **Step 5: Commit findings + fixes**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/rbc-contamination-findings.md docs/engineering/review/2026-04-17/FIX_LOG.md
git commit -m "docs(review): complete RBC contamination scan with findings and fixes"
```

- [ ] **Step 6: Escalate if required**

If any Critical contamination found in patent-claim-critical code or docs (not just bank-pilot marketing), **STOP and message user per Escalation Trigger #1**. Do not proceed to Day 3 until resolved.

---

## Day 3 — Patent Language Scrub (EPG-21)

### Task 3.1: Identify patent-published materials

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/patent-scope-classification.md`

- [ ] **Step 1: List all files under `docs/legal/patent/`**

Run Glob `docs/legal/patent/**/*.md`. Capture list.

- [ ] **Step 2: Classify each file**

Per file, classify as:
- **Publishable** — will appear in filed patent (e.g., `provisional-spec.md`, `claims.md`)
- **Internal-only** — counsel briefing, strategy memos (no language scrub required)
- **Unknown** — flag for user decision

Write classification table.

- [ ] **Step 3: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/patent-scope-classification.md
git commit -m "docs(review): classify patent docs by publication scope"
```

---

### Task 3.2: Run banned-term grep against publishable docs

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/epg21-scrub-report.md`

- [ ] **Step 1: Define banned terms per EPG-21**

```
AML, SAR, OFAC, SDN, compliance investigation, tipping-off, suspicious activity, PEP
```

Plus BLOCK code enumeration: `DNOR`, `CNOR`, `RR01`, `RR02`, `RR03`, `RR04`, `AG01`, `LEGL` appearing together.

- [ ] **Step 2: Grep publishable docs**

For each file classified Publishable:
- Grep pattern: `\bAML\b|\bSAR\b|\bOFAC\b|\bSDN\b|compliance investigation|tipping-off|suspicious activity|\bPEP\b`
- Output mode: `content` with `-n`
- Case-insensitive

Aggregate matches per file.

- [ ] **Step 3: Grep for BLOCK code enumeration**

Grep pattern: `DNOR.{0,100}CNOR` (multiline enabled) — detects co-location of multiple BLOCK codes.

- [ ] **Step 4: Write `epg21-scrub-report.md`**

Sections:
1. Files scanned (publishable only)
2. Banned-term violations per file — before/after snippets
3. BLOCK-code enumeration violations
4. Replacement language per EPG-21 (`classification gate`, `hold type discriminator`, `bridgeability flag`, `procedural hold`, `investigatory hold`)

- [ ] **Step 5: Commit scrub report (no fixes yet)**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/epg21-scrub-report.md
git commit -m "docs(review): EPG-21 language scrub audit findings"
```

---

### Task 3.3: Apply language scrub fixes

**Files:**
- Modify: every publishable doc with a violation

- [ ] **Step 1: For each violation, apply EPG-21 replacement**

Per file, per violation, Edit in place:
- `AML` → `classification` or `hold type discriminator` (context-dependent)
- `SAR`, `OFAC`, `SDN`, `compliance investigation`, `tipping-off`, `suspicious activity`, `PEP` → remove entirely or replace with `procedural hold`, `investigatory hold`, `bridgeability flag`
- BLOCK code enumerations → collapse to "a code in the non-bridgeable set (see internal taxonomy)"

- [ ] **Step 2: Verify no banned terms remain**

Re-run Task 3.2 Step 2 grep. Expected: zero matches in Publishable files.

- [ ] **Step 3: Escalate if scrub involved externally-published material**

If any file to be scrubbed has been:
- Published on a public URL (blog, LinkedIn post, SEC filing)
- Shared with external parties (investors, banks)

**STOP and message user per Escalation Trigger #2.** Do not commit fixes until lawyer-approved strategy set.

- [ ] **Step 4: Append Fix Log entries**

One per fixed file. Severity High (patent-impacting).

- [ ] **Step 5: Commit**

```bash
git add docs/legal/patent/ docs/engineering/review/2026-04-17/FIX_LOG.md
git commit -m "fix(patent): apply EPG-21 language scrub to publishable docs"
```

---

## Day 4 — AI-Agent Contribution Inventory

### Task 4.1: Dump AI-authored commits per agent

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-claude.csv`
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-copilot.csv`
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-github-actions.csv`

- [ ] **Step 1: Dump Claude commits with file changes**

Run:
```bash
git log --all --author='noreply@anthropic.com' --format='%H|%ai|%s' --numstat > docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-claude-raw.txt
```

Parse into CSV with columns: commit_hash, date, subject, files_changed, insertions, deletions.

- [ ] **Step 2: Same for Copilot**

Run:
```bash
git log --all --author='Copilot' --format='%H|%ai|%s' --numstat > docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-copilot-raw.txt
```

- [ ] **Step 3: Same for github-actions bot**

Run:
```bash
git log --all --author='github-actions' --format='%H|%ai|%s' --numstat > docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-gha-raw.txt
```

- [ ] **Step 4: Commit raw dumps**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-*.txt docs/engineering/review/2026-04-17/week-1-ip-timing/ai-commits-*.csv
git commit -m "docs(review): dump AI-agent commit inventories"
```

---

### Task 4.2: Classify AI commits and build inventorship matrix

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/inventorship-matrix.md`

- [ ] **Step 1: Classify each AI commit**

For each commit in CSVs, classify as:
- **(a) User-directed** — commit traces to a human prompt/instruction; AI implemented under direction
- **(b) Autonomous cleanup** — formatting, renaming, test generation, docstring fixes
- **(c) Creative authorship** — novel algorithm, claim-relevant logic, architectural decision

Sort commits modifying files in `lip/c1_*`, `lip/c2_*`, `lip/c3_*`, `lip/c4_*`, `lip/pipeline.py`, `lip/common/` — these are patent-claim-critical.

- [ ] **Step 2: Load current patent claims**

Read `docs/legal/patent/` publishable materials. Extract the claim elements (1st/2nd step classification + conditional offer, B1/B2 sub-classification, thin-file PD, etc.).

- [ ] **Step 3: Map claim elements to commits**

For each claim element, identify:
- The commits that introduce the implementation
- Author of each (human vs. AI agent)
- Whether the creative step (novel logic) is human-authored

Table columns: claim element | file(s) | first-introducing commit | author | creative-step author | Thaler risk (Y/N)

- [ ] **Step 4: Flag Thaler-risk claims**

Per Thaler v. Vidal (2022), natural-person inventorship required. Any claim element where the creative step appears AI-authored is a risk. List remediation: rewrite under human direction with documented prompt/commit trail.

- [ ] **Step 5: Write `inventorship-matrix.md`**

Include: the mapping table, Thaler-risk summary, remediation list.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/inventorship-matrix.md
git commit -m "docs(review): build AI inventorship matrix and Thaler-risk analysis"
```

- [ ] **Step 7: Add Red-Flag Register entries**

For each Thaler-risk claim element, add entry to `docs/legal/.red-flag-register.md` (local-only). Do NOT commit (file is gitignored).

---

## Day 5 — Prior-Art & Prior-Conception Evidence Hunt

### Task 5.1: Verify external prior-art citation completeness

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/prior-art-audit.md`

- [ ] **Step 1: List cited prior art in patent docs**

Grep publishable patent docs for: `US\d{7}[B|A]\d`, `EP\d{7}`, `ISO 20022`, `Merton`, `KMV`, `Damodaran`, `Altman`. Capture every citation.

- [ ] **Step 2: Validate each citation**

For each citation, check:
- **US7089207B1** (JPMorgan, per README) — verify citation appears in filing materials
- ISO 20022 specifications — which version/sections
- Merton/KMV structural PD model — academic reference
- Damodaran industry beta — public dataset source
- Altman Z' — Altman, Edward. "Financial Ratios..." 1968

Write per-citation entry: citation | claim relevance | source link | verified (Y/N).

- [ ] **Step 3: Identify missing citations**

Known-adjacent prior art that should be cited but isn't:
- FX settlement risk systems (CLS Bank)
- Real-time payment failure detection (SWIFT gpi)
- ISO 20022 pacs.002 handling standards
- Correspondent banking credit limit tools

List gaps.

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/prior-art-audit.md
git commit -m "docs(review): audit patent prior-art citation completeness"
```

---

### Task 5.2: Prior-conception evidence questionnaire (user action)

**Files:**
- Create: `docs/legal/inventors-notebook/evidence-questionnaire.md`

- [ ] **Step 1: Write questionnaire for user**

Create `docs/legal/inventors-notebook/evidence-questionnaire.md`:

```markdown
# Prior-Conception Evidence Questionnaire

**Target:** Surface any artifact dated before 2026-02-27 (first commit)
— ideally before 2026-01-12 (RBC start) — that shows you thinking
about payment failures, SWIFT, cross-border settlement, bridge lending,
or the LIP concept.

## 1. AI chat history
- [ ] ChatGPT: export → search for `SWIFT`, `payment failure`, `pacs.002`,
      `bridge loan`, `correspondent banking`, `liquidity`
- [ ] Claude: same search
- [ ] Any other LLM you used

**How to search ChatGPT:** Settings → Data Controls → Export → wait for email → download.
Unzip → open `conversations.json` → search for terms. Note conversation dates.

**How to search Claude:** Account → Privacy → Download your data.

## 2. Notes apps
- [ ] Apple Notes — search keywords
- [ ] Notion — search keywords
- [ ] Obsidian / iA Writer / Bear — search

## 3. Emails
- [ ] Gmail search: `payment failure`, `SWIFT`, `correspondent bank`, `bridge loan`,
      `liquidity`, `LIP`, `BPI Technology`
- [ ] Include sent folder, drafts

## 4. Calendar
- [ ] Any meetings with the words "payment", "SWIFT", "banking", "fintech" before 2026-02-27

## 5. Social / professional
- [ ] LinkedIn posts or drafts about payments/fintech
- [ ] X/Twitter posts, likes, bookmarks
- [ ] Medium/Substack drafts

## 6. Physical / visual
- [ ] Whiteboard photos in camera roll
- [ ] Sketches in notebooks — photograph dated pages
- [ ] Voice memos

## 7. Other
- [ ] GitHub activity before 2026-02-27 on any account (gists, private repos, issues)
- [ ] Any Claude Code / Codex / Copilot session in other repos
- [ ] Domain registrations (bpi.tech? lip.io? check Whois history)

## How to hand off evidence to this review
1. Copy artifacts to `docs/legal/inventors-notebook/evidence/YYYY-MM/`
2. Name each file with ISO date prefix: `2025-11-15-chatgpt-swift-discussion.json`
3. Add a one-line description in `docs/legal/inventors-notebook/evidence/README.md`

Anything predating 2026-01-12 is gold. Anything between 2026-01-12 and 2026-02-27
that shows independent thinking (not RBC-sourced) also helps.
```

- [ ] **Step 2: Commit**

```bash
git add docs/legal/inventors-notebook/evidence-questionnaire.md
git commit -m "docs(review): prior-conception evidence questionnaire for user"
```

- [ ] **Step 3: Message user**

Send (via conversation): "Questionnaire is at `docs/legal/inventors-notebook/evidence-questionnaire.md`. Please work through it at your pace — even partial results help. Target: surface evidence by end of Day 5 if possible, but Day 7 checkpoint is the hard gate."

---

### Task 5.3: Create evidence intake directory

**Files:**
- Create: `docs/legal/inventors-notebook/evidence/README.md`
- Create: `docs/legal/inventors-notebook/evidence/.gitkeep`

- [ ] **Step 1: Create evidence intake docs**

Create `docs/legal/inventors-notebook/evidence/README.md`:

```markdown
# Evidence Index

Chronologically organized evidence of LIP conception and continuous development.

## Format
`YYYY-MM/YYYY-MM-DD-<type>-<short-description>.<ext>`

Types: `chat`, `email`, `note`, `calendar`, `linkedin`, `sketch`, `voice`, `screenshot`, `gist`

## Inventory

(Populated as evidence is surfaced.)

| Date | Type | Description | File | Relevance |
|------|------|-------------|------|-----------|
| — | — | — | — | — |
```

Create `docs/legal/inventors-notebook/evidence/.gitkeep`.

- [ ] **Step 2: Commit**

```bash
git add docs/legal/inventors-notebook/evidence/
git commit -m "docs(review): scaffold evidence intake directory"
```

---

## Day 6 — Chain-of-Title Draft

### Task 6.1: Build contributor ledger

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/contributor-ledger.md`

- [ ] **Step 1: Enumerate every identity that ever committed**

From Day 1 Task 1.2 output (post-`.mailmap`), list canonical identities with: name, email, commit count, first/last commit date, type (human/AI/automation).

- [ ] **Step 2: For each human identity, document employment context**

Columns: identity | employment during contribution period | did they sign an assignment | risk flag.

For Ryan's identity: "RBC employee 2026-01-12 onward; no separate LIP assignment signed; subject to RBC IP clause (see auto-memory project_rbc_ip_clause_analysis.md)."

- [ ] **Step 3: For each AI agent, document the operator**

Columns: bot identity | who directed it | terms of service | ownership of outputs.

Per Anthropic Claude ToS: output belongs to user. Per GitHub Copilot ToS: suggestions generated under your account. Verify.

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/contributor-ledger.md
git commit -m "docs(review): draft contributor ledger for chain-of-title"
```

---

### Task 6.2: Third-party content audit

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/third-party-content.md`

- [ ] **Step 1: Identify all third-party content from README**

From README §Architecture and §Getting Started:
- **Models/libs:** LightGBM, PyTorch, TabTransformer, GraphSAGE, Qwen3-32B (via Groq)
- **Data:** Damodaran industry beta (which year?), Altman Z' (public formula)
- **Standards:** ISO 20022 pacs.002 spec (licensed by SWIFT? or public?)
- **Infra:** Redpanda (Kafka-compatible), Redis, Docker, Kubernetes

- [ ] **Step 2: Read requirements files**

Read: `requirements.txt`, `requirements-ml.txt`, `lip/c3/rust_state_machine/Cargo.toml`, `lip/c5_streaming/*/go.mod`, `lip/c7_execution_agent/*/go.mod` (if exist — verify via Glob).

- [ ] **Step 3: License matrix**

Columns: dependency | version | license | commercial-use OK | regulated-finance OK | flag.

Focus especially on:
- Qwen3-32B / Groq API — **read Groq ToS for production banking use**
- Any GPL/AGPL deps (taint)
- Any non-commercial dataset licenses

- [ ] **Step 4: Commit (no fixes yet — fixes land in Week 2 Day 9)**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/third-party-content.md
git commit -m "docs(review): first-pass third-party content and license audit"
```

---

### Task 6.3: NewCo assignment prep

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-1-ip-timing/newco-assignment-checklist.md`

- [ ] **Step 1: Draft NewCo assignment checklist**

Content:
- Everything under `ryanktomegah/PRKT2026` (GitHub repo itself)
- All copies (local working trees, cloud backups)
- All patent assets (provisional, non-provisional when filed, priority dates)
- All trade secrets (AML corpus patterns, license HMAC seeds — these must NOT be in git)
- Domain names (check Whois for `bpi.tech`, `lip.*`, etc.)
- Bank pilot agreements (none yet, will be NewCo signatory)
- AI-agent outputs: confirm ownership flows from Ryan → NewCo under applicable provider ToS

Include: list of documents counsel will need to draft (Invention Assignment Agreement, IP Transfer Deed, etc.).

- [ ] **Step 2: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-1-ip-timing/newco-assignment-checklist.md
git commit -m "docs(review): NewCo assignment preparation checklist"
```

---

## Day 7 — Consolidation + Checkpoint

### Task 7.1: Assemble IP & Timing Dossier v1

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/part-a-ip-timing-dossier.md`

- [ ] **Step 1: Draft Part A**

Sections:
1. **Executive summary** (3 paragraphs)
2. **Timing finding** — 0 pre-RBC commits; implications for RBC IP clause defense
3. **Contamination scan outcome** — findings from Day 2 + applied fixes
4. **Patent language scrub** — EPG-21 compliance status
5. **AI-agent inventorship** — Thaler-risk claims and remediation status
6. **Prior-art & prior-conception** — cited art completeness; evidence gap status
7. **Chain-of-title** — contributor ledger + third-party content overview
8. **Open items for counsel** — explicit list of questions/decisions
9. **Appendices pointer** — links to Week 1 evidence files

- [ ] **Step 2: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/part-a-ip-timing-dossier.md
git commit -m "docs(review): assemble IP & Timing Dossier v1 (Part A)"
```

---

### Task 7.2: Open draft PR with Week 1 evidence

**Files:**
- (GitHub PR creation via `gh`)

- [ ] **Step 1: Verify branch is pushed and current**

Run: `git status` → `nothing to commit, working tree clean`. Run: `git push origin codex/pre-lawyer-review`.

- [ ] **Step 2: Open draft PR**

Run:
```bash
gh pr create --draft --title "Pre-lawyer review: IP & timing audit (Week 1)" --body "$(cat <<'EOF'
## Summary
Week 1 of the 4-week pre-lawyer review (risk-first triage).

- Scaffolded review directories, Fix Log, Inventor's Notebook, Red-Flag Register
- Consolidated 3 git identities via `.mailmap`
- Commit forensics: 0 pre-RBC commits, 548 post-RBC commits, first commit 2026-02-27
- RBC contamination scan: findings and fixes in `docs/engineering/review/2026-04-17/week-1-ip-timing/`
- EPG-21 patent language scrub: applied
- AI-agent inventorship matrix with Thaler-risk flags
- Prior-art audit + user evidence questionnaire
- Contributor ledger + NewCo assignment checklist
- **Part A (IP & Timing Dossier) assembled**

Design: `docs/superpowers/specs/2026-04-17-pre-lawyer-review-design.md`
Plan: `docs/superpowers/plans/2026-04-17-pre-lawyer-review.md`

## Test plan
- [ ] User reviews Part A and Fix Log entries
- [ ] User completes prior-conception evidence questionnaire
- [ ] User approves Week 2 start

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Save PR URL**

Capture returned URL; record in `docs/engineering/review/2026-04-17/FIX_LOG.md` under Day 7 entry.

---

### Task 7.3: Week 1 checkpoint — pause for user review

**USER CHECKPOINT — DO NOT PROCEED TO WEEK 2 WITHOUT APPROVAL.**

- [ ] **Step 1: Send checkpoint message to user**

Contents:
1. Week 1 summary: what was audited, what was found, what was fixed
2. Red-Flag Register summary (local-only counts — open/resolved/accepted by severity)
3. Open escalations, if any
4. Pre-Week-2 asks:
   - Evidence questionnaire progress (blocker for Day 23 Inventor's Notebook)
   - Approval to proceed to Week 2

- [ ] **Step 2: Wait for user approval**

Do not run Day 8 until user explicitly approves.

---

# WEEK 2 — CODE QUALITY DEEP DIVE (Days 8–14)

## Day 8 — Meta-Checks: Test Suite, Lint, Type Check, Security

### Task 8.1: Full test suite run

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/pytest-full-run.log`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/coverage-report.txt`

- [ ] **Step 1: Bring up local infra**

Run:
```bash
cd /Users/tomegah/PRKT2026
docker compose up -d
bash scripts/init_topics.sh
```

Expected: Redpanda + Redis containers running; 10 Kafka topics created.

- [ ] **Step 2: Run full test suite with coverage**

Run:
```bash
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_live.py \
  --cov=lip --cov-report=term --cov-report=html:docs/engineering/review/2026-04-17/week-2-code-quality/coverage-html \
  -v 2>&1 | tee docs/engineering/review/2026-04-17/week-2-code-quality/pytest-full-run.log
```

Expected runtime: ~12 min per CLAUDE.md. Wait with `TaskOutput(block=True, timeout=900000)` if auto-backgrounded.

- [ ] **Step 3: Verify claims**

From pytest output: capture actual test count and coverage %. Compare to README's 1284 tests / 92% coverage.

Any discrepancy ≥ 5% → flag as High severity in Fix Log (misleading badge).

- [ ] **Step 4: Extract failing tests (if any)**

Grep pytest log for `FAILED`. List each failure with file:test_name. For each:
- **Determine severity:** Critical (blocks prod/patent claim), High (misleading metric), Medium (flaky per CLAUDE.md allowlist), Low (skipped/xfailed).
- **Fix or defer:** Critical/High fix inline per Fix Policy; Medium/Low add to Week 4 list.

- [ ] **Step 5: Commit logs**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/pytest-full-run.log docs/engineering/review/2026-04-17/week-2-code-quality/coverage-report.txt
git commit -m "docs(review): full pytest + coverage run for week-2 meta-checks"
```

---

### Task 8.2: Lint, type check, and static security analysis

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/ruff-report.txt`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/mypy-report.txt`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/bandit-report.txt`

- [ ] **Step 1: Run ruff**

Run: `ruff check lip/ 2>&1 | tee docs/engineering/review/2026-04-17/week-2-code-quality/ruff-report.txt`
Expected: zero errors per CLAUDE.md badge.
If non-zero: fix inline, commit per-batch.

- [ ] **Step 2: Run mypy**

Run: `mypy lip/ 2>&1 | tee docs/engineering/review/2026-04-17/week-2-code-quality/mypy-report.txt`
Capture error count. No target; record for Code Quality Report Card.

- [ ] **Step 3: Install bandit if needed, then run**

Run:
```bash
pip install bandit
bandit -r lip/ -f txt -o docs/engineering/review/2026-04-17/week-2-code-quality/bandit-report.txt
```

Triage findings:
- **High severity + High confidence:** fix inline.
- **Medium/Low:** add to Week 4 fix list or mark accepted.

- [ ] **Step 4: Commit reports**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/*.txt docs/engineering/review/2026-04-17/week-2-code-quality/*.log
git commit -m "docs(review): ruff/mypy/bandit meta-check reports"
```

---

## Day 9 — Dependency & License Audit

### Task 9.1: Python dependency CVE and license audit

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/pip-audit.txt`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/python-licenses.csv`

- [ ] **Step 1: Install pip-audit and safety**

Run: `pip install pip-audit safety pip-licenses`

- [ ] **Step 2: Run pip-audit**

Run:
```bash
pip-audit -r requirements.txt -r requirements-ml.txt -f text | tee docs/engineering/review/2026-04-17/week-2-code-quality/pip-audit.txt
```

- [ ] **Step 3: Run safety check**

Run: `safety check -r requirements.txt -r requirements-ml.txt --full-report | tee docs/engineering/review/2026-04-17/week-2-code-quality/safety-check.txt`

- [ ] **Step 4: Extract license matrix**

Run: `pip-licenses --from=mixed --format=csv > docs/engineering/review/2026-04-17/week-2-code-quality/python-licenses.csv`

Flag any of: GPL-*, AGPL-*, SSPL, Commons Clause, non-commercial dataset licenses.

- [ ] **Step 5: Fix critical CVEs inline**

For each CVE rated Critical with a safe upgrade path: bump dep version, re-run tests, commit.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/pip-audit.txt docs/engineering/review/2026-04-17/week-2-code-quality/safety-check.txt docs/engineering/review/2026-04-17/week-2-code-quality/python-licenses.csv
git commit -m "docs(review): Python dependency CVE and license audit"
```

---

### Task 9.2: Rust and Go dependency audits

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/cargo-audit.txt`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/govulncheck.txt`

- [ ] **Step 1: Cargo audit on Rust projects**

Enumerate Rust projects via Glob `lip/**/Cargo.toml`. For each:
```bash
cd <rust-project-dir>
cargo audit 2>&1 | tee -a <repo-root>/docs/engineering/review/2026-04-17/week-2-code-quality/cargo-audit.txt
cd <repo-root>
```

- [ ] **Step 2: Govulncheck on Go projects**

Enumerate Go projects via Glob `lip/**/go.mod`. For each:
```bash
cd <go-project-dir>
govulncheck ./... 2>&1 | tee -a <repo-root>/docs/engineering/review/2026-04-17/week-2-code-quality/govulncheck.txt
cd <repo-root>
```

- [ ] **Step 3: Fix critical findings inline**

Same policy as Task 9.1 Step 5.

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/cargo-audit.txt docs/engineering/review/2026-04-17/week-2-code-quality/govulncheck.txt
git commit -m "docs(review): Rust and Go dependency audits"
```

---

### Task 9.3: Qwen3 / Groq ToS review + gitignore verification

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/groq-qwen3-tos-review.md`

- [ ] **Step 1: Fetch Groq ToS and Qwen3 model license**

Read Groq ToS (https://groq.com/terms or similar). Extract clauses on:
- Regulated-finance production use
- Banking/lending use-case restrictions
- Customer data handling, data retention
- SLAs for production

Fetch Qwen3-32B model card/license from Hugging Face (Apache 2.0 or Tongyi Qianwen License).

Document findings in `groq-qwen3-tos-review.md`.

- [ ] **Step 2: Escalate if blocked**

If Groq ToS forbids regulated-finance production use: **STOP and message user per Escalation Trigger #3.** Do not continue Day 9 until fallback strategy set (e.g., private Qwen3 inference on AWS Bedrock / GCP Vertex).

- [ ] **Step 3: Verify `artifacts/` and `c6_corpus_*.json` are gitignored**

Run:
```bash
git check-ignore -v artifacts/
git check-ignore -v lip/c6_aml_velocity/c6_corpus_example.json 2>&1 || echo "SAMPLE NOT TRACKED"
grep -E '^(artifacts|c6_corpus)' .gitignore
```

Expected: ignored per CLAUDE.md rules.

If `artifacts/` is tracked or any `c6_corpus_*.json` appears in git history: **STOP per Escalation Trigger #4.**

- [ ] **Step 4: Run gitleaks history scan**

Run:
```bash
pip install gitleaks-wrapper || brew install gitleaks
gitleaks detect --log-level=info --report-path docs/engineering/review/2026-04-17/week-2-code-quality/gitleaks-report.json
```

If any secret found in history: **STOP per Escalation Trigger #4.** Remediation (BFG/filter-repo) requires user approval.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/groq-qwen3-tos-review.md docs/engineering/review/2026-04-17/week-2-code-quality/gitleaks-report.json
git commit -m "docs(review): Groq/Qwen3 ToS review + secret history scan"
```

---

## Day 10 — Core Infrastructure Review

### Task 10.1: Pipeline.py deep review

**Files:**
- Read: `lip/pipeline.py`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-pipeline-review.md`

- [ ] **Step 1: Read full `pipeline.py`**

Use Read tool. Document: entry points, order of stages, dependencies, error-handling patterns.

- [ ] **Step 2: Identify 94ms SLO-critical path**

Trace the synchronous path from `pacs.002 in` → `LoanOffer/BLOCKED out`. List every function call in sequence with (measured or estimated) latency contribution.

- [ ] **Step 3: Evaluate split candidates**

For each logical section (>100 lines), evaluate whether extraction would:
- Reduce cognitive load (good)
- Add function-call overhead to SLO-critical path (bad — reject)

Only recommend splits that don't impact SLO.

- [ ] **Step 4: Grade on 5 axes**

Axes: correctness, tests, security, performance, maintainability. Each A–F with rationale.

- [ ] **Step 5: Apply any critical fixes found**

Per Fix Policy.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-pipeline-review.md
git commit -m "docs(review): pipeline.py deep review and grading"
```

---

### Task 10.2: Common, API, integrity modules

**Files:**
- Read: `lip/common/`, `lip/api/`, `lip/integrity/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-common-api-integrity-review.md`

- [ ] **Step 1: Read common/constants.py**

Verify QUANT-locked constants (300 bps, 3/7/21d, 94ms, τ★=0.110) are: single-source of truth, marked `Final`, imported (not duplicated) elsewhere, have comments citing commit hash + dataset scope per CLAUDE.md rule.

Grep for any duplicate literal of 300, 0.110, 94 in other files.

- [ ] **Step 2: Read api/ (FastAPI app)**

Check:
- AuthN/Z: does every endpoint require auth? Token validation against C8 license manager?
- Input validation: Pydantic models on all bodies, strict mode?
- Rate limits: implemented where?
- Error surfaces: do error responses leak internal state?

- [ ] **Step 3: Read integrity/**

Identify what invariants are enforced (structural integrity per README). Check tests cover failure paths.

- [ ] **Step 4: Grade each module**

A–F on 5 axes per module. Write to review doc.

- [ ] **Step 5: Apply critical fixes**

Per Fix Policy.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-common-api-integrity-review.md
git commit -m "docs(review): common/api/integrity modules review"
```

---

## Day 11 — C6 (AML/Velocity) + C8 (License Manager) Security Deep Dive

### Task 11.1: C6 AML/Velocity review

**Files:**
- Read: `lip/c6_aml_velocity/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c6-review.md`

- [ ] **Step 1: Read C6 Python + Rust**

Files include `velocity.py`, Rust velocity counters (Glob `lip/c6_*/src/*.rs` or equivalent).

- [ ] **Step 2: Verify PyO3 FFI boundary**

Check:
- All inputs validated before crossing FFI
- Rust panics caught on Python side (no `unwinding` across FFI)
- No `unsafe` blocks in Rust without justification comment

- [ ] **Step 3: Verify salt rotation**

Confirm implementation matches CLAUDE.md constants: 365d rotation, 30d overlap. Locate rotation trigger and current salt storage.

- [ ] **Step 4: Verify EPG-16 unlimited-cap guard**

Per CLAUDE.md: `aml_dollar_cap_usd=0` means unlimited, set per-licensee via C8 token. Find the guard in code; verify it's zero-is-unlimited semantics (not zero-blocks-all).

- [ ] **Step 5: Verify sanctions list freshness**

How is OFAC/EU list updated? Stale-list detection? Fail-closed on update failure?

- [ ] **Step 6: Corpus hygiene**

Confirm `c6_corpus_*.json` not in working tree (`git ls-files | grep c6_corpus` → empty). Verify `.gitignore` covers all variants.

- [ ] **Step 7: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 8: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c6-review.md
git commit -m "docs(review): C6 AML/velocity security review"
```

---

### Task 11.2: C8 License Manager review

**Files:**
- Read: `lip/c8_license_manager/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c8-review.md`

- [ ] **Step 1: Read C8 source**

Focus: HMAC-SHA256 implementation, boot validation, token shape, revocation.

- [ ] **Step 2: Verify HMAC key storage**

How is the HMAC key loaded at runtime? Env var? Secret manager? File?
If file: is the path in `.gitignore`? Has it ever been committed?
Cross-check against Day 9 gitleaks report.

- [ ] **Step 3: Verify EPG-17 token shape**

Per CLAUDE.md: `license_token.from_dict` must require `aml_dollar_cap_usd` AND `aml_count_cap` as explicit JSON fields. Verify by reading code.

Write a test (if not present): token parsing rejects dicts missing either field.

- [ ] **Step 4: Verify replay/tamper resistance**

Tokens include timestamp? Expiry? Nonce? Signature over full payload?

- [ ] **Step 5: Verify boot validation**

On process start, does C8 validate the license? Fail-closed if invalid/expired? Log the decision?

- [ ] **Step 6: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 7: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c8-review.md
git commit -m "docs(review): C8 license manager security review"
```

---

## Day 12 — C2 PD Model + Fee Logic + P5 Cascade

### Task 12.1: C2 PD model + Damodaran/Altman source verification

**Files:**
- Read: `lip/c2_pd_model/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c2-review.md`

- [ ] **Step 1: Read C2 source completely**

Focus: structural PD (Merton/KMV), Damodaran industry beta, Altman Z', fee pricing.

- [ ] **Step 2: Verify math against cited sources**

Per CLAUDE.md `feedback_verify_semantics_before_assessment.md`:
- Merton/KMV formulas: compare C2 implementation to canonical (Merton 1974 paper or KMV Moody's book)
- Damodaran: verify beta source (damodaran.online/damodaranonline), which year's data? Is version pinned?
- Altman Z': confirm formula for public/private, manufacturing/non-manufacturing variants

- [ ] **Step 3: Fee floor enforcement audit**

Grep all code paths that compute a fee. For each path, verify 300 bps clamp is applied.
Cases to check: base fee, spread, any adjustment, final output.

Write a test: fee function with low-PD input never returns < 300 bps.

- [ ] **Step 4: CLASS_B label correctness**

Verify per CLAUDE.md: `SETTLEMENT_P95_CLASS_B_HOURS = 53.58` is labelled "Systemic/processing delays", not AML/compliance. Grep docs for any old "AML/compliance" labeling.

- [ ] **Step 5: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c2-review.md
git commit -m "docs(review): C2 PD model and fee math review"
```

---

### Task 12.2: P5 Cascade Engine review

**Files:**
- Read: `lip/p5_cascade_engine/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-p5-review.md`

- [ ] **Step 1: Read P5 source**

Focus: propagation algorithm, bounds checking, systemic risk metric output.

- [ ] **Step 2: Sanity-check math**

Is the propagation operator well-defined? Convergence conditions? What prevents runaway amplification?

- [ ] **Step 3: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-p5-review.md
git commit -m "docs(review): P5 cascade engine review"
```

---

## Day 13 — ML Models: C1, C4, C9, dgen

### Task 13.1: C1 Failure Classifier review

**Files:**
- Read: `lip/c1_failure_classifier/`, `docs/models/c1-model-card.md`, `docs/models/c1-training-data-card.md`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c1-review.md`

- [ ] **Step 1: Read C1 source + model/data cards**

Focus: GraphSAGE + TabTransformer + LightGBM ensemble, τ★=0.110 threshold.

- [ ] **Step 2: Label leakage check**

For each feature: is it derivable only from data available *before* the decision moment? Flag any feature that uses post-decision info (e.g., settlement time, customer-contact timestamps).

- [ ] **Step 3: Data leakage check**

Train/val/test splits: are they temporally or entity-disjoint? Any overlap?

- [ ] **Step 4: OOT validation**

Does the model have an out-of-time validation record (per REX rule)? Locate it.

- [ ] **Step 5: SR 11-7 model card completeness**

Checklist per SR 11-7:
- Purpose + intended use
- Data sources + data card
- Methodology
- Performance metrics (by segment)
- Limitations
- Monitoring plan
- Governance/ownership

Flag gaps.

- [ ] **Step 6: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 7: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c1-review.md
git commit -m "docs(review): C1 failure classifier review"
```

---

### Task 13.2: C4 Dispute Classifier review

**Files:**
- Read: `lip/c4_dispute_classifier/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c4-review.md`

- [ ] **Step 1: Read C4 source**

Prefilter (Python) + LLM (Qwen3-32B via Groq). Negation suite at `lip/c4_dispute_classifier/negation.py`.

- [ ] **Step 2: Verify `/no_think` system prompt in place**

Per CLAUDE.md: Qwen3 must receive `/no_think` + regex strip. Verify.

- [ ] **Step 3: Verify prefilter FP rate**

Per CLAUDE.md: prefilter FP rate after Step 2a (commit 3808a74) is 4%. Re-run measurement. Compare.

- [ ] **Step 4: Validate on ≥100 cases**

Per CLAUDE.md: never conclude from <100 cases. Ensure latest measurements use full 500-case negation corpus.

- [ ] **Step 5: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c4-review.md
git commit -m "docs(review): C4 dispute classifier review"
```

---

### Task 13.3: C9 + dgen review

**Files:**
- Read: `lip/c9_settlement_predictor/`, `lip/dgen/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c9-dgen-review.md`

- [ ] **Step 1: C9 model card + metrics check**

Shallow review — confirm metrics exist, data source clear.

- [ ] **Step 2: dgen field semantics verification**

Per DGEN push-back rule: read synthetic corpus generator source, verify field semantics from implementation not from names.

- [ ] **Step 3: Calibration citations**

Every distribution/parameter in dgen: cite its calibration source. Flag missing citations.

- [ ] **Step 4: Grade + fixes**

A–F on 5 axes per module. Apply critical fixes inline.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c9-dgen-review.md
git commit -m "docs(review): C9 settlement predictor and dgen review"
```

---

## Day 14 — Polyglot Bridges + Code Quality Report Card

### Task 14.1: Rust FSM (C3) review

**Files:**
- Read: `lip/c3/rust_state_machine/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c3-review.md`

- [ ] **Step 1: Read Rust source**

State-machine implementation, PyO3 bindings.

- [ ] **Step 2: Correctness check**

Enumerate states + transitions. Verify no orphan states (unreachable) or dead-end states (no exit except success).

- [ ] **Step 3: Panic safety at FFI**

Every PyO3-exposed function: does panic unwind across FFI (undefined behavior) or catch?
Search for `unwrap()`, `expect()` — these panic.

- [ ] **Step 4: Unsafe block audit**

List every `unsafe` block. Justify each.

- [ ] **Step 5: Grade + fixes**

A–F on 5 axes. Apply critical fixes inline.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c3-review.md
git commit -m "docs(review): C3 Rust FSM review"
```

---

### Task 14.2: Go consumer (C5) and Go gRPC (C7) review

**Files:**
- Read: `lip/c5_streaming/`, `lip/c7_execution_agent/`
- Create: `docs/engineering/review/2026-04-17/week-2-code-quality/module-c5-c7-review.md`

- [ ] **Step 1: Read Go source (both)**

- [ ] **Step 2: C5 Kafka consumer audit**

Back-pressure: what happens under slow consumer? Offset commit semantics (at-least-once? at-most-once?). Partition rebalance handling.

- [ ] **Step 3: C7 gRPC audit**

Offer router: kill-switch path, latency budget within 94ms. Mutual TLS? AuthN?

- [ ] **Step 4: Grade + fixes**

A–F on 5 axes per module. Apply critical fixes inline.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-2-code-quality/module-c5-c7-review.md
git commit -m "docs(review): C5 streaming and C7 execution agent review"
```

---

### Task 14.3: Assemble Code Quality Report Card (Part D)

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/part-d-code-quality-report-card.md`

- [ ] **Step 1: Consolidate per-module grades**

Table columns: Module | Correctness | Tests | Security | Performance | Maintainability | Overall | Notes.

Rows: pipeline.py, common, api, integrity, C1, C2, C3, C4, C5, C6, C7, C8, C9, P5, P10, dgen.

- [ ] **Step 2: Executive narrative (1 page)**

Plain-English: how the code is overall, top 3 strengths, top 5 issues, top 5 fixes landed.

- [ ] **Step 3: Appendix pointer**

Link each module to its week-2 deep-dive doc.

- [ ] **Step 4: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/part-d-code-quality-report-card.md
git commit -m "docs(review): assemble Code Quality Report Card (Part D)"
```

---

### Task 14.4: Week 2 checkpoint — pause for user review

**USER CHECKPOINT — DO NOT PROCEED TO WEEK 3 WITHOUT APPROVAL.**

- [ ] **Step 1: Push all commits**

```bash
git push origin codex/pre-lawyer-review
```

- [ ] **Step 2: Update PR description with Week 2 summary**

```bash
gh pr edit --body "$(cat <<'EOF'
... [Week 1 summary] ...

## Week 2 — Code Quality Deep Dive
- Meta-checks: ruff/mypy/bandit/pytest/coverage reports
- Dependency + license audit (Python + Rust + Go)
- Groq/Qwen3 ToS review
- Module deep-dives: pipeline.py, common, api, integrity, C1-C9, P5, dgen, C3 Rust, C5/C7 Go
- **Part D (Code Quality Report Card) assembled**

## Test plan
- [ ] User reviews Part D
- [ ] User approves Week 3 start

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for user approval**

Do not run Day 15 until user explicitly approves.

---

# WEEK 3 — PRODUCT & INTEGRATION (Days 15–21)

## Day 15 — End-to-End Pipeline Test

### Task 15.1: Run E2E pipeline live

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/e2e-live-run.log`

- [ ] **Step 1: Verify infra running**

Run: `docker compose ps` → Redpanda + Redis healthy.

- [ ] **Step 2: Run live E2E tests**

Run:
```bash
PYTHONPATH=. python -m pytest lip/tests/test_e2e_live.py -m live -v \
  2>&1 | tee docs/engineering/review/2026-04-17/week-3-product-integration/e2e-live-run.log
```

- [ ] **Step 3: Capture trace through components**

For one successful `pacs.002 → LoanOffer` path:
- C5 ingestion timing
- C1 classifier latency + decision
- C6 AML screen result
- C2 PD/fee result
- C7 offer router
- Total end-to-end latency

Write trace to `docs/engineering/review/2026-04-17/week-3-product-integration/e2e-trace.md`.

- [ ] **Step 4: If E2E fails — STOP and fix**

If Day 15 fails, nothing else in Week 3 matters until green. Diagnose, fix, retry. Per spec Section 4.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/
git commit -m "docs(review): live E2E pipeline run + component trace"
```

---

## Day 16 — SLO & Performance

### Task 16.1: Latency validation under load

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/slo-validation.md`

- [ ] **Step 1: Run benchmark suite**

Locate benchmark harness (likely `scripts/benchmark*.py` or `lip/tests/` perf tests). Run with production-like load.

- [ ] **Step 2: Measure P50 / P95 / P99 latency**

Target: P99 ≤ 94ms per CLAUDE.md QUANT constant.

- [ ] **Step 3: Isolate flaky `test_slo_p99_94ms`**

Per CLAUDE.md: this test is flaky under CPU load. Run in isolation 10 times. If ≥ 7/10 pass, flakiness confirmed (not regression).

- [ ] **Step 4: Compare to `docs/engineering/benchmark-results.md`**

Real vs. claimed. Flag any claim that doesn't match reality.

- [ ] **Step 5: Write slo-validation.md**

Sections: methodology, measurements, real-vs-claimed table, flakiness analysis, recommendations.

- [ ] **Step 6: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/slo-validation.md
git commit -m "docs(review): SLO/performance validation"
```

---

## Day 17 — Infrastructure & CI/CD

### Task 17.1: K8s, Helm, Grafana review

**Files:**
- Read: `lip/infrastructure/`
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/infra-review.md`

- [ ] **Step 1: Enumerate infra assets**

Glob: `lip/infrastructure/**/*.yaml`, `lip/infrastructure/**/Chart.yaml`, Grafana dashboards.

- [ ] **Step 2: K8s manifest review**

Per manifest: resource limits, security context (non-root, read-only FS), network policies, secret sources (ConfigMap vs. Secret vs. external SM), probes.

- [ ] **Step 3: Helm chart review**

Values parameterization; dev/staging/prod separation; secrets injection mechanism.

- [ ] **Step 4: Secrets plumbing**

Critical: how do HMAC keys, API tokens, DB creds land in pods? Acceptable: external-secrets, sealed-secrets, Vault, cloud SM. Unacceptable: committed yaml, plain env in manifest.

If unacceptable found: Critical severity, fix or document mitigation plan.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/infra-review.md
git commit -m "docs(review): K8s/Helm/Grafana infra review"
```

---

### Task 17.2: CI/CD pipeline review

**Files:**
- Read: `.github/workflows/`
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/cicd-review.md`

- [ ] **Step 1: Enumerate workflows**

Glob: `.github/workflows/*.yml`.

- [ ] **Step 2: Per-workflow audit**

Triggers, gates, matrix, secrets access, OIDC, artifact handling, retention.

- [ ] **Step 3: Check CI health**

Run:
```bash
gh run list --repo ryanktomegah/PRKT2026 --limit 20
```

Recent failures? Flaky workflows? Log entries for ongoing issues.

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/cicd-review.md
git commit -m "docs(review): CI/CD pipeline review"
```

---

## Day 18 — Model Validation

### Task 18.1: Run C1 on dryrun data

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/c1-validation.md`

- [ ] **Step 1: Locate dryrun data**

`ls artifacts/production_data_dryrun/` — enumerate.

- [ ] **Step 2: Run C1 inference on dryrun**

Use `lip/train_all.py --help` to find the inference entry point, or locate `scripts/` validator.

- [ ] **Step 3: Compute AUC, precision, recall by segment**

Compare to claims in `docs/models/c1-model-card.md`. Flag discrepancies.

- [ ] **Step 4: OOT validation record**

Confirm (or populate) OOT validation doc per REX rule.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/c1-validation.md
git commit -m "docs(review): C1 model validation on dryrun data"
```

---

## Day 19 — Demo & Pilot Readiness

### Task 19.1: Walk bank-pilot kit as a banker

**Files:**
- Read: `docs/business/bank-pilot/`
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/demo-readiness.md`

- [ ] **Step 1: Read entire bank-pilot kit**

- [ ] **Step 2: Banker walkthrough**

Simulate: "I'm a VP at RBCx receiving this for the first time." Is the pitch coherent? Is the ask clear? Are the claims credible? Are the numbers auditable?

- [ ] **Step 3: Demo script assessment**

Can we run a demo tomorrow? What infrastructure is required? What data is fabricated vs. realistic?

- [ ] **Step 4: License Agreement readiness**

Per EPG-04/05: check that template has `hold_bridgeable` flag, `certified_by`, `certification_ts`, 3 warranties (certification, system integrity, indemnification).

Per EPG-14: check MRFA has B2B clause (originating bank is borrower), permanently-blocked-payment clause, governing law from BIC.

Gaps list → counsel to-do.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/demo-readiness.md
git commit -m "docs(review): demo and pilot readiness audit"
```

---

## Day 20 — Compliance & Governance

### Task 20.1: SR 11-7, EU AI Act, DORA audit

**Files:**
- Read: `docs/legal/compliance.md`, `docs/legal/governance/`, `docs/legal/decisions/`
- Create: `docs/engineering/review/2026-04-17/week-3-product-integration/compliance-audit.md`

- [ ] **Step 1: SR 11-7 coverage**

Per model (C1, C2, C4, C9): model card + data card + OOT validation + governance + monitoring plan. Grade each.

- [ ] **Step 2: EU AI Act Art.14 human-oversight (EPG-18)**

Per CLAUDE.md: C6 anomaly flag → PENDING_HUMAN_REVIEW. Verify in code, verify documentation.

- [ ] **Step 3: DORA operational resilience**

Incident response plan? BCP/DR? Third-party risk register?

- [ ] **Step 4: EPG Decision Register walkthrough**

EPG-04 through EPG-21: each has a decision, rationale, code/doc effects. Verify each is implemented or noted as open.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-3-product-integration/compliance-audit.md
git commit -m "docs(review): compliance and governance audit"
```

---

## Day 21 — Part C Assembly + Checkpoint

### Task 21.1: Assemble Product Readiness Verdict (Part C)

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/part-c-product-readiness-verdict.md`

- [ ] **Step 1: Draft Part C**

Sections:
1. Executive verdict (go/no-go for pilot)
2. E2E works? (from Day 15)
3. SLO holds? (from Day 16)
4. Infra pilot-ready? (from Day 17)
5. Models validated? (from Day 18)
6. Pilot kit demo-ready? (from Day 19)
7. Compliance pack complete? (from Day 20)
8. Top 5 gaps blocking pilot

- [ ] **Step 2: Refine Part B (third-party + license)**

Integrate Week 2 dep/license audit findings with Week 1 contributor ledger.

Create `docs/legal/pre-lawyer-review/2026-04-17/part-b-third-party-license-audit.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/part-b-third-party-license-audit.md docs/legal/pre-lawyer-review/2026-04-17/part-c-product-readiness-verdict.md
git commit -m "docs(review): assemble Parts B and C for Master Lawyer Packet"
```

---

### Task 21.2: Week 3 checkpoint — pause for user review

**USER CHECKPOINT — DO NOT PROCEED TO WEEK 4 WITHOUT APPROVAL.**

- [ ] **Step 1: Push all commits**

```bash
git push origin codex/pre-lawyer-review
```

- [ ] **Step 2: Update PR description with Week 3 summary**

- [ ] **Step 3: Wait for user approval**

Do not run Day 22 until user explicitly approves.

---

# WEEK 4 — SYNTHESIS & MASTER PACKET (Days 22–28)

## Day 22 — Patent Claim-to-Code Mapping

### Task 22.1: Build claim-to-code map

**Files:**
- Create: `docs/engineering/review/2026-04-17/week-4-synthesis/claim-to-code-map.md`

- [ ] **Step 1: Extract claim elements**

Read current publishable patent docs. Enumerate each independent and dependent claim.

- [ ] **Step 2: Locate implementing code per claim element**

Table: claim | element | file:line | status (implemented / partial / unsupported).

- [ ] **Step 3: Gap analysis**

Per gap, recommend either:
- Narrow claim to match actual code (preferred — claim robustness)
- Complete implementation to match claim (disclosure enablement)

- [ ] **Step 4: Commit**

```bash
git add docs/engineering/review/2026-04-17/week-4-synthesis/claim-to-code-map.md
git commit -m "docs(review): patent claim-to-code mapping and gap analysis"
```

---

## Day 23 — Inventor's Notebook Finalization

### Task 23.1: Write conception-to-practice timeline

**Files:**
- Create: `docs/legal/inventors-notebook/timeline.md`

- [ ] **Step 1: Ingest user's evidence**

From `docs/legal/inventors-notebook/evidence/` (surfaced in Week 1). If sparse: proceed with what exists plus a clear gap note.

- [ ] **Step 2: Build timeline narrative**

Sections:
1. **Pre-conception context** — Ryan's background, relevant prior experience
2. **Conception** — earliest evidence; interpretations acknowledged
3. **Reduction to practice** — from idea to working code; first commit dates
4. **RBC start overlap** — how LIP development relates to RBC duties (per RBC IP clause analysis)
5. **Post-RBC-start continuation** — evidence that work remained separate from RBC duties (personal time, personal equipment, no RBC resources)
6. **First external signals** — any pitch, filing, or disclosure to a third party

Each evidence item cited inline by filename.

- [ ] **Step 3: Commit**

```bash
git add docs/legal/inventors-notebook/timeline.md
git commit -m "docs(review): Inventor's Notebook conception-to-practice timeline"
```

---

## Day 24 — Week 4 Fix Punch List

### Task 24.1: Work medium-severity deferred fixes

**Files:**
- Various (as fixes demand)

- [ ] **Step 1: Consolidate deferred list from Weeks 2–3**

Aggregate Fix Log entries tagged "Week 4 fix list".

- [ ] **Step 2: Triage**

Per item: still applicable? Genuine value? Within scope for a single working day?

- [ ] **Step 3: Work items**

For each selected item:
- Apply fix
- Run affected tests
- Commit individually with descriptive message
- Append to Fix Log

Stop when list empty or day exhausted. Remaining items marked "deferred to post-review".

- [ ] **Step 4: Update Fix Log**

```bash
git add docs/engineering/review/2026-04-17/FIX_LOG.md
git commit -m "docs(review): Day 24 punch-list fixes logged"
```

---

## Day 25 — Executive Summary

### Task 25.1: Write 2-page executive summary

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/executive-summary.md`

- [ ] **Step 1: Draft`executive-summary.md`**

Structure:
1. **What LIP is** (1 paragraph, non-technical)
2. **Code quality verdict** (3 bullets — strong/weak/fixed)
3. **Product readiness verdict** (3 bullets — works/doesn't-work/needs)
4. **Top 5 IP risks** (each with counsel action)
5. **Top 5 actions for counsel** (prioritized checklist)

Target length: 2 pages (~800 words).

- [ ] **Step 2: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/executive-summary.md
git commit -m "docs(review): executive summary for Master Lawyer Packet"
```

---

## Day 26 — Master Packet Assembly

### Task 26.1: Stitch parts together, generate PDF

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/master-packet.md`
- Create: `docs/legal/pre-lawyer-review/2026-04-17/master-packet.pdf`

- [ ] **Step 1: Write master-packet.md**

Order:
1. Cover page (title, version, date, author, confidentiality notice)
2. TOC
3. Executive summary
4. Part A — IP & Timing Dossier
5. Part B — Third-Party & License Audit
6. Part C — Product Readiness Verdict
7. Part D — Code Quality Report Card
8. Part E — Appendices (index of appendix files)
9. Signing block for counsel

Use cross-links to sub-docs rather than inlining the full text.

- [ ] **Step 2: Generate PDF**

If `pandoc` available:
```bash
pandoc docs/legal/pre-lawyer-review/2026-04-17/master-packet.md \
  -o docs/legal/pre-lawyer-review/2026-04-17/master-packet.pdf \
  --toc --pdf-engine=xelatex
```

Otherwise: document PDF export steps for user to run.

- [ ] **Step 3: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/master-packet.md
# Only commit PDF if small (<1MB); large binaries avoid
git commit -m "docs(review): Master Lawyer Packet assembly"
```

---

## Day 27 — Red-Flag Register Finalization

### Task 27.1: Close or escalate every entry

**Files:**
- Modify: `docs/legal/.red-flag-register.md` (LOCAL-ONLY)

- [ ] **Step 1: Review every entry**

Per entry: status = Open / Resolved / Accepted. Privilege = Work-product / Produceable / Undetermined.

- [ ] **Step 2: Archive resolved**

Move to "Archive" section within same file (still local-only).

- [ ] **Step 3: Produce sanitized summary (git-committable)**

Create `docs/legal/pre-lawyer-review/2026-04-17/red-flag-summary.md`:
- Counts per (severity × status × privilege) — no specifics
- Notes: "Full Red-Flag Register retained locally under attorney work-product treatment."

- [ ] **Step 4: Commit sanitized summary only**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/red-flag-summary.md
git commit -m "docs(review): Red-Flag Register sanitized summary"
```

---

## Day 28 — Walkthrough Doc for User

### Task 28.1: Write walkthrough Q&A

**Files:**
- Create: `docs/legal/pre-lawyer-review/2026-04-17/walkthrough-qa.md`

- [ ] **Step 1: Anticipate user questions**

Write a Q&A doc pre-answering the questions a non-technical founder would have:
- "Is my patent still viable?"
- "What's the RBC clause risk, in plain English?"
- "Can I show this to a bank tomorrow?"
- "What do I pay lawyers to do first?"
- "How much of this will a lawyer actually read?"
- "What's the single worst finding?"
- "What's the single best finding?"
- "What's my homework before the meeting?"

Each answer short, concrete, with citation to the packet section.

- [ ] **Step 2: Commit**

```bash
git add docs/legal/pre-lawyer-review/2026-04-17/walkthrough-qa.md
git commit -m "docs(review): final walkthrough Q&A for user"
```

- [ ] **Step 3: Final push + PR mark-ready-for-review**

```bash
git push origin codex/pre-lawyer-review
gh pr ready
```

- [ ] **Step 4: Final user handoff message**

Summary message to user:
- Packet location
- PDF location (if generated)
- Walkthrough Q&A location
- Red-Flag Register reminder (local-only)
- Recommended meeting sequence by lawyer type

---

## Appendix A — Fix Log Entry Template

```
## YYYY-MM-DD — <short title>
- **Severity:** Critical | High | Medium | Low
- **Problem:** <what was wrong>
- **Fix:** <what was changed>
- **Commit:** <hash>
- **Verification:** <how we know it's fixed>
```

## Appendix B — Red-Flag Register Entry Template

```
## [RF-NNN] — <short title>
- **Status:** Open | Resolved | Accepted
- **Privilege:** Work-product | Produceable | Undetermined
- **Finding:** <what was discovered>
- **Location:** <file:line or commit hash>
- **Severity:** Critical | High | Medium | Low
- **Resolution:** <done, or plan>
```

## Appendix C — Per-Module Grade Rubric

| Grade | Criteria |
|-------|----------|
| A | Correct, well-tested, secure, performant, maintainable. Would ship to a bank. |
| B | Minor issues on ≤2 axes; ship with notes. |
| C | Moderate issues; ship only with explicit risk acceptance. |
| D | Material issues; do not ship without fixes. |
| F | Broken or unsafe; do not ship. |
