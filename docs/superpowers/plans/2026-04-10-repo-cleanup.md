# Repository Cleanup & Documentation Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform PRKT2026 from an organically-grown 6-week sprint repo into a professionally organized, audience-navigable public repository — clean root, audience-based docs/, no sensitive material, no cache bloat.

**Architecture:** 14 sequential phases executed as 28 atomic tasks. File operations first (delete/move), content updates second (cross-references), major rewrites last (README, INDEX). This ordering prevents broken intermediate states and makes each commit independently sensible.

**Tech Stack:** git (mv, rm, add, commit), bash, sed, Python (pytest for final verification)

---

## Pre-Flight

### Task 1: Create Safety Branch

**Files:** none (git operation only)

- [ ] **Step 1: Create backup branch**

```bash
cd /Users/tomegah/PRKT2026
git branch backup/pre-reorg
git branch -v | grep backup
```

Expected output: `  backup/pre-reorg  <sha>  <last commit message>`

- [ ] **Step 2: Confirm you are on main**

```bash
git branch --show-current
```

Expected: `main`

- [ ] **Step 3: Verify backup was created (do NOT switch to it)**

```bash
git log --oneline -1 backup/pre-reorg
```

Expected: same commit hash as HEAD. No commit needed — this task creates no tracked changes.

---

## Phase 0: Local Filesystem Cleanup

### Task 2: Delete Cache Directories and Stale Artifacts

These are all untracked/gitignored files. `git status` will show no changes after this task.

**Files:** `pytest-of-tomegah/`, `.mypy_cache/`, `torchinductor_tomegah/`, `.DS_Store` files, `.coverage`, `mlflow.db`, `artifacts/c1_trained/c1_trained/`

- [ ] **Step 1: Delete large cache directories**

```bash
cd /Users/tomegah/PRKT2026
rm -rf pytest-of-tomegah/
rm -rf .mypy_cache/
rm -rf torchinductor_tomegah/
```

- [ ] **Step 2: Delete stale local artifacts**

```bash
rm -f .coverage
rm -f mlflow.db
rm -rf "artifacts/c1_trained/c1_trained/"
```

- [ ] **Step 3: Delete .DS_Store files**

```bash
find . -name ".DS_Store" -not -path "./.git/*" -delete
```

- [ ] **Step 4: Verify no git impact**

```bash
git status --short
```

Expected: empty output (or only pre-existing tracked modifications — nothing related to the deletions above, since all are gitignored/untracked).

- [ ] **Step 5: Spot-check disk savings**

```bash
du -sh . --exclude=.git
```

Expected: significantly less than 646 MB (roughly 280-290 MB now).

---

## Phase 1: .gitignore Fix

### Task 3: Add Missing Ignore Patterns

**Files:** `.gitignore`

- [ ] **Step 1: Add `.mypy_cache/` to Test caches section**

Edit `.gitignore`. After line 32 (`htmlcov/`), add:

```
.mypy_cache/
```

- [ ] **Step 2: Add `torchinductor_*/` at end of file**

Append to `.gitignore`:

```
# PyTorch inductor compilation cache
torchinductor_*/
```

- [ ] **Step 3: Verify file looks correct**

```bash
tail -5 .gitignore
```

Expected:
```
pytest-of-*/
# PyTorch inductor compilation cache
torchinductor_*/
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add .mypy_cache/ and torchinductor_*/ to .gitignore"
```

---

## Phase 2: Private Repo Extraction

### Task 4: Copy Sensitive Files to Private Repo

**MANUAL USER ACTION REQUIRED.** Claude cannot create a GitHub repo for you.

- [ ] **Step 1: Create private GitHub repo**

On GitHub, create: `ryanktomegah/PRKT2026-private` (private visibility).

- [ ] **Step 2: Clone private repo locally**

```bash
cd /Users/tomegah
git clone git@github.com:ryanktomegah/PRKT2026-private.git
cd PRKT2026-private
mkdir -p fundraising governance business
```

- [ ] **Step 3: Copy fundraising docs**

```bash
cp /Users/tomegah/PRKT2026/docs/fundraising/ip-risk-pre-counsel-analysis.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/ip-risk-pre-counsel-analysis-revised.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/ip-risk-analysis-prompt.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/ff-round-structure.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/valuation-analysis.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/safe-agreement-template.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/nda-template.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/investor-risk-disclosure.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/pre-fundraising-checklist.md fundraising/
cp /Users/tomegah/PRKT2026/docs/fundraising/generate_nda_docx.py fundraising/
cp /Users/tomegah/PRKT2026/docs/governance/Founder-Protection-Strategy.md governance/
cp "/Users/tomegah/PRKT2026/consolidation files/Capital-Partner-Strategy.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Founder-Financial-Model.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Revenue-Projection-Model.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Investor-Briefing-v2.1.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Revenue-Acceleration-Analysis.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Section-85-Rollover-Briefing-v1.1.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/GTM-Strategy-v1.0.md" business/
cp "/Users/tomegah/PRKT2026/consolidation files/Unit-Economics-Exhibit.md" business/
```

- [ ] **Step 4: Commit and push private repo**

```bash
cd /Users/tomegah/PRKT2026-private
git add .
git commit -m "chore: initial import of sensitive business and legal docs from PRKT2026"
git push -u origin main
```

- [ ] **Step 5: Verify all 20 files are in private repo**

```bash
find . -not -path "./.git/*" -type f | wc -l
```

Expected: `20`

### Task 5: Remove Sensitive Files from PRKT2026

**Files:** 20 files deleted from PRKT2026

- [ ] **Step 1: Remove fundraising directory**

```bash
cd /Users/tomegah/PRKT2026
git rm docs/fundraising/ip-risk-pre-counsel-analysis.md
git rm docs/fundraising/ip-risk-pre-counsel-analysis-revised.md
git rm docs/fundraising/ip-risk-analysis-prompt.md
git rm docs/fundraising/ff-round-structure.md
git rm docs/fundraising/valuation-analysis.md
git rm docs/fundraising/safe-agreement-template.md
git rm docs/fundraising/nda-template.md
git rm docs/fundraising/investor-risk-disclosure.md
git rm docs/fundraising/pre-fundraising-checklist.md
git rm docs/fundraising/generate_nda_docx.py
git rm docs/governance/Founder-Protection-Strategy.md
```

- [ ] **Step 2: Remove sensitive consolidation files**

```bash
git rm "consolidation files/Capital-Partner-Strategy.md"
git rm "consolidation files/Founder-Financial-Model.md"
git rm "consolidation files/Revenue-Projection-Model.md"
git rm "consolidation files/Investor-Briefing-v2.1.md"
git rm "consolidation files/Revenue-Acceleration-Analysis.md"
git rm "consolidation files/Section-85-Rollover-Briefing-v1.1.md"
git rm "consolidation files/GTM-Strategy-v1.0.md"
git rm "consolidation files/Unit-Economics-Exhibit.md"
```

- [ ] **Step 3: Verify staging**

```bash
git status --short | grep "^D"
```

Expected: 20 lines starting with `D ` (deleted).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove sensitive fundraising, governance, and business docs (moved to private repo)"
```

---

## Phase 3: Delete Duplicates and Legacy Files

### Task 6: Remove Duplicates, Binaries, and Legacy Script

**Files:** 4 deletions

- [ ] **Step 1: Delete duplicate gap analysis**

```bash
cd /Users/tomegah/PRKT2026
git rm "consolidation files/BPI_Gap_Analysis_v2.0 (1).md"
```

- [ ] **Step 2: Delete .docx binary files (canonical .md versions exist)**

```bash
git rm "consolidation files/01_Provisional_Specification_v5.docx"
git rm "consolidation files/07_Academic_Paper_v2.docx"
```

- [ ] **Step 3: Delete legacy scripts/train_all.py**

```bash
git rm scripts/train_all.py
```

- [ ] **Step 4: Verify staging**

```bash
git status --short | grep "^D"
```

Expected: 4 lines.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove duplicate files, .docx binaries, and legacy scripts/train_all.py"
```

---

## Phase 4: Create New Directory Structure

### Task 7: Create Target Directories

**Files:** new empty directories (git doesn't track empty dirs — the moves in later tasks will populate them)

- [ ] **Step 1: Create all new directories**

```bash
cd /Users/tomegah/PRKT2026
mkdir -p docs/engineering/specs
mkdir -p docs/engineering/blueprints
mkdir -p docs/engineering/research
mkdir -p docs/engineering/review
mkdir -p docs/engineering/benchmark-data
mkdir -p docs/engineering/codebase
mkdir -p docs/legal/patent
mkdir -p docs/legal/governance
mkdir -p docs/legal/decisions
mkdir -p docs/business
mkdir -p docs/operations
mkdir -p docs/models
```

Note: `docs/engineering/` already exists with `default-execution-protocol.md` — this is fine.

- [ ] **Step 2: Verify**

```bash
find docs -maxdepth 2 -type d | sort
```

Expected to include all the new directories above.

No commit yet — empty directories don't stage.

---

## Phase 5: Decompose `consolidation files/`

### Task 8: Move Patent Specifications

**Files:** 4 moves to `docs/legal/patent/`

- [ ] **Step 1: Move patent spec files**

```bash
cd /Users/tomegah/PRKT2026
git mv "consolidation files/Provisional-Specification-v5.1.md"    docs/legal/patent/
git mv "consolidation files/Provisional-Specification-v5.2.md"    docs/legal/patent/
git mv "consolidation files/Patent-Family-Architecture-v2.1.md"   docs/legal/patent/
git mv "consolidation files/Future-Technology-Disclosure-v2.1.md" docs/legal/patent/
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: move patent specifications to docs/legal/patent/"
```

### Task 9: Move Component Specs and Merge Migration Specs

**Files:** 22 moves to `docs/engineering/specs/`

- [ ] **Step 1: Move BPI component and architecture specs**

```bash
cd /Users/tomegah/PRKT2026
git mv "consolidation files/BPI_Architecture_Specification_v1.2.md"            docs/engineering/specs/
git mv "consolidation files/BPI_C1_Component_Spec_v1.0.md"                     docs/engineering/specs/
git mv "consolidation files/BPI_C2_Component_Spec_v1.0.md"                     docs/engineering/specs/
git mv "consolidation files/BPI_C3_Component_Spec_v1.0_Part1.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C3_Component_Spec_v1.0_Part2.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C4_Component_Spec_v1.0.md"                     docs/engineering/specs/
git mv "consolidation files/BPI_C5_Component_Spec_v1.0_Part1.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C5_Component_Spec_v1.0_Part2.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C6_Component_Spec_v1.0.md"                     docs/engineering/specs/
git mv "consolidation files/BPI_C7_Component_Spec_v1.0_Part1.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C7_Component_Spec_v1.0_Part2.md"               docs/engineering/specs/
git mv "consolidation files/BPI_C7_Bank_Deployment_Guide_v1.0.md"              docs/engineering/specs/
git mv "consolidation files/BPI_Gap_Analysis_v2.0.md"                          docs/engineering/specs/
git mv "consolidation files/BPI_Internal_Build_Validation_Roadmap_v1.0.md"     docs/engineering/specs/
git mv "consolidation files/BPI_Open_Questions_Resolution_v1.0.md"             docs/engineering/specs/
```

- [ ] **Step 2: Merge existing docs/specs/ migration specs into docs/engineering/specs/**

```bash
git mv docs/specs/c1_inference_endpoint_typing.md  docs/engineering/specs/
git mv docs/specs/c2_fee_formula_hardening.md       docs/engineering/specs/
git mv docs/specs/c3_state_machine_migration.md     docs/engineering/specs/
git mv docs/specs/c5_kafka_consumer_migration.md    docs/engineering/specs/
git mv docs/specs/c6_velocity_sanctions_migration.md docs/engineering/specs/
git mv docs/specs/c7_kill_switch_migration.md       docs/engineering/specs/
git mv docs/specs/c7_offer_routing_migration.md     docs/engineering/specs/
```

- [ ] **Step 3: Remove now-empty docs/specs/ directory**

```bash
rmdir docs/specs
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: move component specs and migration specs to docs/engineering/specs/"
```

### Task 10: Move Implementation Blueprints

**Files:** 6 moves to `docs/engineering/blueprints/`

- [ ] **Step 1: Move blueprints**

```bash
cd /Users/tomegah/PRKT2026
git mv "consolidation files/P3-v0-Implementation-Blueprint.md"  docs/engineering/blueprints/
git mv "consolidation files/P4-v0-Implementation-Blueprint.md"  docs/engineering/blueprints/
git mv "consolidation files/P5-v0-Implementation-Blueprint.md"  docs/engineering/blueprints/
git mv "consolidation files/P7-v0-Implementation-Blueprint.md"  docs/engineering/blueprints/
git mv "consolidation files/P8-v0-Implementation-Blueprint.md"  docs/engineering/blueprints/
git mv "consolidation files/P10-v0-Implementation-Blueprint.md" docs/engineering/blueprints/
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: move implementation blueprints to docs/engineering/blueprints/"
```

### Task 11: Move Governance Records

**Files:** 3 moves to `docs/legal/governance/`

- [ ] **Step 1: Move sign-off and SR 11-7 governance docs**

```bash
cd /Users/tomegah/PRKT2026
git mv "consolidation files/BPI_Architecture_SignOff_Record_v1.1.md"  docs/legal/governance/
git mv "consolidation files/BPI_Architecture_SignOff_Record_v1.2.md"  docs/legal/governance/
git mv "consolidation files/BPI_SR11-7_Model_Governance_Pack_v1.0.md" docs/legal/governance/
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: move architecture sign-off records and SR 11-7 governance pack to docs/legal/governance/"
```

### Task 12: Move Remaining Consolidation Files and Remove Directory

**Files:** 6 moves + directory removal

- [ ] **Step 1: Move academic paper to research**

```bash
cd /Users/tomegah/PRKT2026
git mv "consolidation files/Academic-Paper-v2.1.md"  docs/engineering/research/
```

- [ ] **Step 2: Move business docs**

```bash
git mv "consolidation files/Competitive-Landscape-Analysis.md"  docs/business/
git mv "consolidation files/Market-Fundamentals-Fact-Sheet.md"  docs/business/
```

- [ ] **Step 3: Move operations docs**

```bash
git mv "consolidation files/Operational-Playbook-v2.1.md"  docs/operations/
git mv "consolidation files/Master-Action-Plan-2026.md"     docs/operations/
```

- [ ] **Step 4: Move developer workflow doc**

```bash
git mv "consolidation files/DEVELOPMENT-START-PROMPT.md"  docs/engineering/
```

- [ ] **Step 5: Verify consolidation files/ is now empty**

```bash
ls "consolidation files/"
```

Expected: empty output (no files listed).

- [ ] **Step 6: Remove the directory**

```bash
rmdir "consolidation files"
```

- [ ] **Step 7: Verify directory is gone**

```bash
ls "consolidation files" 2>&1
```

Expected: `ls: consolidation files: No such file or directory`

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: move remaining consolidation files; remove empty consolidation files/ directory"
```

---

## Phase 6: Move Root Narrative Files

### Task 13: Relocate Root-Level Analysis Documents

**Files:** 3 moves (PROGRESS.md stays at root)

- [ ] **Step 1: Move analysis docs to audience-based locations**

```bash
cd /Users/tomegah/PRKT2026
git mv CLIENT_PERSPECTIVE_ANALYSIS.md   docs/business/
git mv LIP_COMPLETE_NARRATIVE.md        docs/business/
git mv EPIGNOSIS_ARCHITECTURE_REVIEW.md docs/engineering/review/
```

- [ ] **Step 2: Verify root is clean**

```bash
ls *.md
```

Expected: only `README.md`, `PROGRESS.md`, `CLAUDE.md`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: move root narrative files to docs/business/ and docs/engineering/review/"
```

---

## Phase 7: Reorganize Existing `docs/` Files

### Task 14: Reorganize Engineering Docs

**Files:** 10 moves + codebase/ directory move

- [ ] **Step 1: Move engineering reference docs**

```bash
cd /Users/tomegah/PRKT2026
git mv docs/architecture.md          docs/engineering/
git mv docs/developer-guide.md       docs/engineering/
git mv docs/api-reference.md         docs/engineering/
git mv docs/data-pipeline.md         docs/engineering/
git mv docs/benchmark-results.md     docs/engineering/
git mv docs/poc-validation-report.md docs/engineering/
git mv docs/OPEN_BLOCKERS.md         docs/engineering/
```

- [ ] **Step 2: Move research docs**

```bash
git mv docs/pedigree-rd-roadmap.md  docs/engineering/research/
git mv docs/technical-rd-memo.md    docs/engineering/research/
```

- [ ] **Step 3: Move codebase/ reference directory**

```bash
git mv docs/codebase docs/engineering/codebase
```

- [ ] **Step 4: Move benchmark data directory**

```bash
git mv docs/benchmark-results docs/engineering/benchmark-data
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: reorganize engineering docs into docs/engineering/"
```

### Task 15: Reorganize Legal Docs

**Files:** 5 moves + decisions/ directory move

- [ ] **Step 1: Move compliance and legal docs**

```bash
cd /Users/tomegah/PRKT2026
git mv docs/compliance.md                     docs/legal/
git mv docs/patent_claims_consolidated.md     docs/legal/patent/
git mv docs/patent_counsel_briefing.md        docs/legal/patent/
git mv docs/bpi_license_agreement_clauses.md  docs/legal/
git mv docs/c6_sanctions_audit.md             docs/legal/
```

- [ ] **Step 2: Move decisions/ register**

```bash
git mv docs/decisions docs/legal/decisions
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: reorganize legal and compliance docs into docs/legal/"
```

### Task 16: Reorganize Model Cards and ML Research

**Files:** 5 moves

- [ ] **Step 1: Move model cards and ML architecture docs**

```bash
cd /Users/tomegah/PRKT2026
git mv docs/c1-model-card.md                 docs/models/
git mv docs/c2-model-card.md                 docs/models/
git mv docs/c1-training-data-card.md         docs/models/
git mv docs/federated-learning-architecture.md docs/models/
git mv docs/cbdc-protocol-research.md        docs/models/
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: move model cards and ML research to docs/models/"
```

### Task 17: Reorganize Operations and Business Docs

**Files:** 1 move + bank-pilot directory move

- [ ] **Step 1: Move deployment doc**

```bash
cd /Users/tomegah/PRKT2026
git mv docs/deployment.md  docs/operations/
```

- [ ] **Step 2: Move bank-pilot directory under business**

```bash
git mv docs/bank-pilot  docs/business/bank-pilot
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: move deployment doc to docs/operations/ and bank-pilot/ under docs/business/"
```

### Task 18: Track Untracked Code Review Files

**Files:** `docs/review/2026-04-08/` (14 untracked files) → `docs/engineering/review/2026-04-08/`

- [ ] **Step 1: Move the untracked review directory**

```bash
cd /Users/tomegah/PRKT2026
mv docs/review/2026-04-08  docs/engineering/review/2026-04-08
rmdir docs/review
```

- [ ] **Step 2: Stage and commit**

```bash
git add docs/engineering/review/2026-04-08/
git commit -m "docs: track code review reports in docs/engineering/review/2026-04-08/"
```

- [ ] **Step 3: Verify the directory is now tracked**

```bash
git ls-files docs/engineering/review/2026-04-08/ | wc -l
```

Expected: `14`

---

## Phase 8: Fix All Cross-References

### Task 19: Fix Cross-References in docs/engineering/codebase/

These 7 files contain references to `consolidation files/` that now need to point to the new locations.

**Files to edit:**
- `docs/engineering/codebase/README.md`
- `docs/engineering/codebase/pipeline.md`
- `docs/engineering/codebase/compliance.md`
- `docs/engineering/codebase/risk.md`
- `docs/engineering/codebase/p5_cascade_engine.md`
- `docs/engineering/codebase/p10_regulatory_data.md`
- `docs/engineering/codebase/c9_settlement_predictor.md`

- [ ] **Step 1: Find all stale references in codebase/**

```bash
cd /Users/tomegah/PRKT2026
grep -rn "consolidation.files\|consolidation%20files" docs/engineering/codebase/
```

Review every match. For each one, update the link to its new path. General mapping:

| Old path | New path |
|----------|----------|
| `../consolidation files/BPI_C*.md` | `../specs/BPI_C*.md` |
| `../consolidation files/BPI_Architecture*.md` | `../specs/BPI_Architecture*.md` |
| `../consolidation files/P*-Blueprint.md` | `../blueprints/P*-Blueprint.md` |
| `../consolidation files/BPI_SR11-7*.md` | `../governance/BPI_SR11-7*.md` (relative: `../../legal/governance/`) |
| `../consolidation files/Academic-Paper*.md` | `../research/Academic-Paper*.md` |
| `../../consolidation files/...` | Adjust depth accordingly |

- [ ] **Step 2: Verify zero stale refs remain**

```bash
grep -rn "consolidation.files\|consolidation%20files" docs/engineering/codebase/
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add docs/engineering/codebase/
git commit -m "docs: fix consolidation files/ cross-references in docs/engineering/codebase/"
```

### Task 20: Fix Cross-References in docs/legal/decisions/ and Other Moved Docs

**Files:**
- `docs/legal/decisions/EPG-20-21_patent_briefing.md` — refs to `consolidation files/`
- `docs/legal/decisions/README.md` — refs to `EPIGNOSIS_ARCHITECTURE_REVIEW.md` (now at `../../engineering/review/`)
- `docs/legal/decisions/EPG-19_compliance_hold_bridging.md` — same EPIGNOSIS ref
- `docs/engineering/DEVELOPMENT-START-PROMPT.md` — 7 `consolidation files/` refs
- `docs/engineering/OPEN_BLOCKERS.md` — 1 `consolidation files/` ref
- `docs/business/LIP_COMPLETE_NARRATIVE.md` — 2 `consolidation files/` refs
- `docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md` — 2 `consolidation files/` refs

- [ ] **Step 1: Find all remaining stale refs across docs/**

```bash
cd /Users/tomegah/PRKT2026
grep -rn "consolidation.files\|consolidation%20files" docs/
grep -rn "EPIGNOSIS_ARCHITECTURE_REVIEW" docs/
grep -rn "CLIENT_PERSPECTIVE_ANALYSIS" docs/
grep -rn "LIP_COMPLETE_NARRATIVE" docs/
```

- [ ] **Step 2: Fix EPG-20-21 patent briefing**

Update the 2 `consolidation files/` references in `docs/legal/decisions/EPG-20-21_patent_briefing.md` to point to `docs/legal/patent/`.

- [ ] **Step 3: Fix decisions README and EPG-19**

Update `EPIGNOSIS_ARCHITECTURE_REVIEW.md` references. Old relative path (from `docs/decisions/`): `../../EPIGNOSIS_ARCHITECTURE_REVIEW.md`. New relative path (from `docs/legal/decisions/`): `../../engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md`.

Edit both `docs/legal/decisions/README.md` and `docs/legal/decisions/EPG-19_compliance_hold_bridging.md`.

- [ ] **Step 4: Fix DEVELOPMENT-START-PROMPT.md**

Update all 7 `consolidation files/` references in `docs/engineering/DEVELOPMENT-START-PROMPT.md` to point to new locations under `docs/engineering/specs/`, `docs/legal/patent/`, etc.

- [ ] **Step 5: Fix OPEN_BLOCKERS.md**

Update the 1 `consolidation files/` reference in `docs/engineering/OPEN_BLOCKERS.md`.

- [ ] **Step 6: Fix LIP_COMPLETE_NARRATIVE.md**

Update the 2 `consolidation files/` references in `docs/business/LIP_COMPLETE_NARRATIVE.md`.

- [ ] **Step 7: Fix EPIGNOSIS_ARCHITECTURE_REVIEW.md internal links**

Update the 2 `consolidation files/` references in `docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md`.

- [ ] **Step 8: Final check — zero stale refs in entire repo**

```bash
grep -rn "consolidation.files\|consolidation%20files" . --exclude-dir=.git
```

Expected: zero matches.

- [ ] **Step 9: Fix stale docs/ paths in existing files (path depth changes)**

Some files in `docs/legal/decisions/` previously lived at `docs/decisions/` — their relative paths to sibling docs are now one level deeper. Run:

```bash
grep -rn "\.\./architecture\|\.\./developer-guide\|\.\./compliance\|\.\./deployment\|\.\./api-reference" docs/
```

Update any relative links that break due to the directory restructuring. When a file moved from `docs/foo.md` to `docs/subdir/foo.md`, all links relative to the old location need +1 `../` added.

- [ ] **Step 10: Commit all cross-reference fixes**

```bash
git add -A
git commit -m "docs: fix all internal cross-references after reorganization"
```

---

## Phase 9: Rewrite README.md

### Task 21: Rewrite README.md

**Files:** `README.md`

Replace the entire contents of `README.md` with the following. Keep the existing badges (tests, coverage, ruff, python version) if present — update counts to match current (1284 tests, 92% coverage):

- [ ] **Step 1: Write new README.md**

```markdown
# LIP — Liquidity Intelligence Platform

[![Tests](https://img.shields.io/badge/tests-1284%20passing-brightgreen)](https://github.com/ryanktomegah/PRKT2026/actions)
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)](https://github.com/ryanktomegah/PRKT2026/actions)
[![Ruff](https://img.shields.io/badge/ruff-0%20errors-brightgreen)](https://docs.astral.sh/ruff/)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://python.org)

Real-time payment failure detection and automated bridge lending for correspondent banks.
Built by BPI Technology. Patent-pending.

---

## What LIP Does

When a cross-border SWIFT payment fails (ISO 20022 `pacs.002` rejection), LIP detects it in milliseconds, classifies the failure type, assesses the borrowing bank's credit risk, and conditionally offers a short-term bridge loan — all within a 94ms SLO. Banks license LIP as a technology platform; BPI does not hold deposits or make loans directly.

---

## Architecture

```
pacs.002 rejection
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  C5 Streaming          ISO 20022 normalisation, Kafka ingestion (Go)        │
│  C6 AML/Velocity       Sanctions screening, velocity limits (Rust + Python) │
│  C1 Failure Classifier GraphSAGE + TabTransformer + LightGBM failure pred.  │
│  C4 Dispute Classifier LLM-based dispute detection (Qwen3-32B / Groq)       │
│  C2 PD Model           Tiered structural PD + LGD + fee pricing             │
│  C3 Repayment Engine   UETR polling, settlement monitoring (Rust FSM)       │
│  C7 Execution Agent    Loan execution, kill switch, Go gRPC router          │
│  C8 License Manager    HMAC-SHA256 token enforcement (cross-cutting)        │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
  LoanOffer or BLOCKED/DECLINED/COMPLIANCE_HOLD
```

| Component | Purpose | Key Tech |
|-----------|---------|----------|
| C1 — Failure Classifier | Predict payment failure probability | GraphSAGE, TabTransformer, LightGBM |
| C2 — PD Model | Tiered PD/LGD + fee pricing | Merton/KMV, Damodaran, Altman Z' |
| C3 — Repayment Engine | Settlement monitoring + auto-repayment | UETR polling, Rust FSM (PyO3) |
| C4 — Dispute Classifier | Hard-block disputed payments | Qwen3-32B via Groq |
| C5 — Streaming | ISO 20022 normalisation + ingestion | Kafka (Go consumer) |
| C6 — AML/Velocity | OFAC/EU sanctions + velocity limits | Rust velocity counters (PyO3) |
| C7 — Execution Agent | Loan execution with safety controls | Go gRPC offer router, kill switch |
| C8 — License Manager | Technology licensing enforcement | HMAC-SHA256, boot validation |

**Additional modules:** C9 (Settlement Predictor), P5 (Cascade Engine), P10 (Regulatory Data Product)

---

## Canonical Constants

These values are **QUANT-locked** — never change without explicit QUANT sign-off (see CLAUDE.md):

| Constant | Value | Location |
|----------|-------|----------|
| Fee floor | 300 bps | `lip/common/constants.py` |
| Maturity CLASS_A | 3 days | `lip/common/constants.py` |
| Maturity CLASS_B | 7 days | `lip/common/constants.py` |
| Maturity CLASS_C | 21 days | `lip/common/constants.py` |
| C1 decision threshold (τ★) | 0.110 | `lip/common/constants.py` |
| Latency SLO | ≤ 94ms | `lip/common/constants.py` |
| UETR TTL buffer | 45 days | `lip/common/constants.py` |

---

## Getting Started

### Prerequisites

- Python 3.13+
- Docker (for local Kafka + Redis)
- Go 1.22+ (for C5/C7 microservices)
- Rust 1.77+ (for C3/C6 PyO3 extensions)

### Local Infrastructure

```bash
# Start Redpanda (Kafka-compatible) + Redis
docker compose up -d

# Initialize Kafka topics (10 topics, 7-year retention on decision log)
bash scripts/init_topics.sh
```

### Install Dependencies

```bash
pip install -r requirements.txt
# ML training only:
pip install -r requirements-ml.txt
```

### Run Tests

```bash
# Fast iteration (excludes slow ML training tests)
PYTHONPATH=. python -m pytest lip/tests/ -m "not slow" -v

# Full suite (~12 min)
PYTHONPATH=. python -m pytest lip/tests/ -v

# Lint (must be zero errors before any commit)
ruff check lip/
```

### Train Models

```bash
# Train all models (C1, C2, C6) — requires artifacts/ directory
PYTHONPATH=. python lip/train_all.py --help
```

---

## Documentation

Documentation is organized by audience:

| Audience | Entry Point |
|----------|-------------|
| All roles | [`docs/INDEX.md`](docs/INDEX.md) — role-based reading paths |
| Engineers | [`docs/engineering/`](docs/engineering/) — architecture, dev guide, specs, review |
| Legal / Compliance | [`docs/legal/`](docs/legal/) — compliance, patent specs, EPG decisions |
| Business / Pilots | [`docs/business/`](docs/business/) — client analysis, RBC pilot kit |
| Operations | [`docs/operations/`](docs/operations/) — deployment, playbooks |
| ML / Models | [`docs/models/`](docs/models/) — model cards, federated learning |

**Quick links:**
- [Architecture](docs/engineering/architecture.md)
- [Developer Guide](docs/engineering/developer-guide.md)
- [API Reference](docs/engineering/api-reference.md)
- [Compliance (SR 11-7, EU AI Act, DORA)](docs/legal/compliance.md)
- [C1 Model Card](docs/models/c1-model-card.md)
- [EPG Decision Register](docs/legal/decisions/)
- [RBC Pilot Kit](docs/business/bank-pilot/)
- [Benchmark Results](docs/engineering/benchmark-results.md)

---

## Repository Layout

```
PRKT2026/
├── README.md                    ← This file
├── CLAUDE.md                    ← Claude Code project configuration
├── PROGRESS.md                  ← Development session tracker
├── docker-compose.yml           ← Local Redpanda + Redis
├── requirements.txt             ← Core Python dependencies
├── requirements-ml.txt          ← ML training dependencies
│
├── lip/                         ← Production Python package
│   ├── pipeline.py              ← Algorithm 1 — main orchestrator (1107 lines)
│   ├── c1_failure_classifier/   ← ML failure prediction
│   ├── c2_pd_model/             ← Structural PD + fee pricing
│   ├── c3_repayment_engine/     ← Settlement monitoring
│   ├── c3/rust_state_machine/   ← Rust FSM (PyO3)
│   ├── c4_dispute_classifier/   ← LLM dispute detection
│   ├── c5_streaming/            ← Kafka ingestion + Go consumer
│   ├── c6_aml_velocity/         ← Sanctions + Rust velocity engine
│   ├── c7_execution_agent/      ← Loan execution + Go gRPC router
│   ├── c8_license_manager/      ← HMAC licensing
│   ├── c9_settlement_predictor/ ← Settlement prediction
│   ├── p5_cascade_engine/       ← Systemic risk propagation
│   ├── p10_regulatory_data/     ← Regulator data product (DP)
│   ├── common/                  ← Schemas, constants, state machines
│   ├── api/                     ← FastAPI application
│   ├── dgen/                    ← Synthetic data generation
│   ├── infrastructure/          ← Docker, Kubernetes, Helm, Grafana
│   ├── integrity/               ← Structural integrity enforcement
│   ├── risk/                    ← Portfolio risk utilities
│   └── tests/                   ← 1284 tests, 92% coverage
│
├── scripts/                     ← Training, benchmarking, validation CLI
│
├── docs/
│   ├── INDEX.md                 ← Role-based entry point
│   ├── engineering/             ← Architecture, specs, developer guides
│   │   ├── specs/               ← BPI_C1-C7 specs + migration specs (22 files)
│   │   ├── blueprints/          ← P3-P10 implementation blueprints
│   │   ├── codebase/            ← Subsystem reference docs (14 files)
│   │   ├── review/              ← Code review reports
│   │   └── research/            ← Academic paper, R&D memos
│   ├── legal/
│   │   ├── patent/              ← Patent specs, claims, counsel briefing
│   │   ├── decisions/           ← EPG decision register (EPG-04 through EPG-21)
│   │   └── governance/          ← Sign-off records, SR 11-7 governance pack
│   ├── business/
│   │   └── bank-pilot/          ← RBC pilot kit (7 docs)
│   ├── operations/              ← Deployment, playbooks
│   ├── models/                  ← Model cards, federated learning, CBDC research
│   └── superpowers/             ← Sprint plans and design specs
│
└── .github/workflows/           ← CI/CD, model training, deploy pipelines
```

---

## Patent Coverage

LIP's core patent claim covers the **two-step classification + conditional offer mechanism** for ISO 20022 payment failures — specifically the novel extension to Tier 2/3 private counterparties using Damodaran industry-beta and Altman Z' thin-file models (gap in JPMorgan US7089207B1).

See [`docs/legal/patent/`](docs/legal/patent/) for provisional specifications and patent family architecture.

---

## Key Rules (Non-Negotiable)

- **Never bridge compliance-hold payments** (EPG-19): DNOR, CNOR, RR01-RR04, AG01, LEGL are permanently blocked — AMLD6 Art.10 criminal liability applies.
- **Fee floor is 300 bps** (QUANT authority): No code may produce a fee below this without explicit QUANT sign-off and documented justification.
- **Never commit AML typology patterns** (`c6_corpus_*.json`): CIPHER rule — generate fresh with dgen.
- **Governing law from BIC, not currency** (EPG-14): `bic_to_jurisdiction()` uses BIC chars 4-5.

---

## License

Proprietary. © BPI Technology. All rights reserved. Patent pending.
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l README.md
```

Expected: approximately 185-200 lines.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README.md with new docs/ structure, updated metrics, and clean layout"
```

---

## Phase 10–11: Update CLAUDE.md and PROGRESS.md

### Task 22: Update CLAUDE.md

**Files:** `CLAUDE.md`

Add a Documentation Structure section so agents know where to find docs.

- [ ] **Step 1: Insert documentation structure section**

Add the following block to `CLAUDE.md` immediately after the `## Repository` section (after the test/lint commands block, before `## Execution Protocol`):

```markdown
## Documentation Structure

Docs are organized by audience under `docs/`. When you need a file, look here first:

| Audience | Directory | Key Files |
|----------|-----------|-----------|
| Engineers | `docs/engineering/` | architecture.md, developer-guide.md, api-reference.md, specs/, blueprints/, codebase/ |
| Legal / Compliance | `docs/legal/` | compliance.md, patent/, decisions/ (EPG register), governance/ |
| Business | `docs/business/` | CLIENT_PERSPECTIVE_ANALYSIS.md, LIP_COMPLETE_NARRATIVE.md, bank-pilot/ |
| Operations | `docs/operations/` | deployment.md, Operational-Playbook-v2.1.md |
| ML Models | `docs/models/` | c1-model-card.md, c2-model-card.md, c1-training-data-card.md |
| All Roles | `docs/INDEX.md` | Role-based reading paths (banker, engineer, compliance, counsel) |
```

- [ ] **Step 2: Verify CLAUDE.md looks correct (spot-check)**

```bash
grep -n "Documentation Structure" CLAUDE.md
```

Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add documentation structure overview to CLAUDE.md"
```

### Task 23: Update PROGRESS.md

**Files:** `PROGRESS.md`

- [ ] **Step 1: Append hardening sprint summary**

Read the git log to gather the hardening sprint context:

```bash
git log --oneline main --since="2026-03-21" | head -60
```

Then append to `PROGRESS.md` the following section (after the last existing session entry):

```markdown
---

## Session: Hardening Sprint — Code Review Day + B1–B13 Remediation (2026-04-01 to 2026-04-10)

**Focus:** Security, correctness, and robustness hardening following comprehensive code review (2026-04-08 review, 13 batches, 30+ findings).

### Completed

**Security & Correctness (B-series findings):**
- B3-02: Fixed unsigned HMAC fields — `dataclasses.fields()` introspection ensures new LicenseToken fields are auto-included in canonical payload
- B3-01: TOCTOU race in DP budget accounting — addressed with atomic operations
- B6-01: Compliance BLOCK code drift resolved — single source of truth via `_COMPLIANCE_HOLD_CODES` frozenset in agent.py (EPG-19 defense-in-depth)
- B6-02: Kafka offset commit fixed on error paths
- B8-01/02: Federated learning DP composition and fail-open privacy fallback hardened
- B9-01: Intervention fee floor violation patched (was 200bps, now enforces FEE_FLOOR_BPS=300)
- B10-01/02: Pickle deserialization hardened (`secure_pickle.py`, hash verification)
- B11-01/02: DGEN mislabeling issues corrected
- AML encapsulation tightened (CIPHER review)
- Fail-closed defaults enforced across pipeline gates
- Decimal precision fixes in fee arithmetic (Decimal vs. float)
- Rust/Go compilation and CI pipeline repairs
- HMAC enforcement across all signed structures
- Sanctions screening improvements (C6 hardening)

**Test Suite:**
- 1284 tests passing, 92% coverage

### Current State (2026-04-10)

**Engineering blockers:** None.

**Legal/contractual blockers (non-engineering):**
1. Patent non-provisional filing — pending patent counsel engagement
2. Pilot bank LOI — `hold_bridgeable` API clause language required before RBCx engagement
3. MRFA B2B clause — unconditional repayment language (not contingent on underlying payment)
4. BPI License Agreement — AML disclosure / indemnification clause

**Repository reorganization (this session):** Full docs restructure, consolidation files/ decomposed, sensitive docs moved to private repo, audience-based docs/ hierarchy established.
```

- [ ] **Step 2: Commit**

```bash
git add PROGRESS.md
git commit -m "docs: update PROGRESS.md with hardening sprint summary and current project state"
```

---

## Phase 12: Rewrite INDEX.md

### Task 24: Rewrite docs/INDEX.md

**Files:** `docs/INDEX.md`

This is the repository's front door. Complete rewrite required — all `consolidation files/` references are gone, investor reading path is removed (private repo), all paths updated to new structure.

- [ ] **Step 1: Write new INDEX.md**

```markdown
# LIP Documentation Index

**This is your entry point.** Find your role below and follow the reading path.

---

## Reading Paths by Role

### A. New Team Member / Contributor

Start here to understand what you're working on:

1. [`../README.md`](../README.md) — Project overview, architecture diagram, quick start
2. [`engineering/architecture.md`](engineering/architecture.md) — Algorithm 1, component pipeline, state machines
3. [`engineering/developer-guide.md`](engineering/developer-guide.md) — Setup, test commands, agent team structure
4. [`engineering/data-pipeline.md`](engineering/data-pipeline.md) — Synthetic data generation, training workflow
5. [`engineering/codebase/README.md`](engineering/codebase/README.md) — Subsystem reference index
6. [`../CLAUDE.md`](../CLAUDE.md) — Agent team roles, canonical constants, non-negotiable rules

### B. Engineer (Component Work)

6. [`engineering/specs/BPI_Architecture_Specification_v1.2.md`](engineering/specs/BPI_Architecture_Specification_v1.2.md) — Full architecture spec
7. [`engineering/specs/`](engineering/specs/) — Component specs (BPI_C1–C7) and migration specs
8. [`engineering/blueprints/`](engineering/blueprints/) — P3–P10 implementation blueprints
9. [`legal/decisions/`](legal/decisions/) — EPG decision register (EPG-04 through EPG-21)
10. [`engineering/OPEN_BLOCKERS.md`](engineering/OPEN_BLOCKERS.md) — Current engineering blockers
11. [`engineering/review/2026-04-08/INDEX.md`](engineering/review/2026-04-08/INDEX.md) — Code review findings (B1–B13)

### C. Compliance Officer / Regulator

1. [`legal/compliance.md`](legal/compliance.md) — SR 11-7, EU AI Act Art.9/13/14/17/61, DORA Art.30, AML, GDPR
2. [`models/c1-model-card.md`](models/c1-model-card.md) — C1 model card (AUC 0.8871, τ★=0.110, ECE 0.069)
3. [`models/c2-model-card.md`](models/c2-model-card.md) — C2 model card (PD tiers, fee floor)
4. [`models/c1-training-data-card.md`](models/c1-training-data-card.md) — Training data card (EU AI Act Art.10)
5. [`legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md) — SR 11-7 governance pack
6. [`legal/governance/BPI_Architecture_SignOff_Record_v1.2.md`](legal/governance/BPI_Architecture_SignOff_Record_v1.2.md) — Architecture sign-off
7. [`legal/decisions/EPG-19_compliance_hold_bridging.md`](legal/decisions/EPG-19_compliance_hold_bridging.md) — Never-bridge rule (unanimous team decision)
8. [`engineering/poc-validation-report.md`](engineering/poc-validation-report.md) — PoC validation on synthetic corpus

### D. Patent Counsel

1. [`legal/patent/Provisional-Specification-v5.2.md`](legal/patent/Provisional-Specification-v5.2.md) — Latest provisional specification
2. [`legal/patent/Patent-Family-Architecture-v2.1.md`](legal/patent/Patent-Family-Architecture-v2.1.md) — Patent family architecture
3. [`legal/patent/patent_claims_consolidated.md`](legal/patent/patent_claims_consolidated.md) — Consolidated claims
4. [`legal/patent/Future-Technology-Disclosure-v2.1.md`](legal/patent/Future-Technology-Disclosure-v2.1.md) — Future tech disclosure
5. [`legal/patent/patent_counsel_briefing.md`](legal/patent/patent_counsel_briefing.md) — Pre-session briefing for counsel
6. [`legal/decisions/EPG-20-21_patent_briefing.md`](legal/decisions/EPG-20-21_patent_briefing.md) — Language scrub rules (no AML/SAR/OFAC in claims)
7. [`engineering/research/Academic-Paper-v2.1.md`](engineering/research/Academic-Paper-v2.1.md) — Academic publication draft

### E. Pilot Bank Contact (RBC)

1. [`business/bank-pilot/rbc-pilot-strategy.md`](business/bank-pilot/rbc-pilot-strategy.md) — Pilot approach and strategy
2. [`business/bank-pilot/commercial-overview.md`](business/bank-pilot/commercial-overview.md) — Commercial overview
3. [`business/bank-pilot/integration-guide.md`](business/bank-pilot/integration-guide.md) — Technical integration guide
4. [`business/bank-pilot/api-reference.md`](business/bank-pilot/api-reference.md) — API reference for bank integration
5. [`business/bank-pilot/demo-walkthrough.md`](business/bank-pilot/demo-walkthrough.md) — Demo walkthrough
6. [`business/bank-pilot/gcp-demo-setup.md`](business/bank-pilot/gcp-demo-setup.md) — GCP demo environment setup
7. [`business/bank-pilot/legal-prerequisites.md`](business/bank-pilot/legal-prerequisites.md) — Legal prerequisites before pilot

### F. DevOps / Infrastructure

1. [`operations/deployment.md`](operations/deployment.md) — Docker, Kubernetes, Helm, HPA config
2. [`engineering/architecture.md`](engineering/architecture.md) — Redis schemas, Kafka topics, service topology
3. [`engineering/benchmark-results.md`](engineering/benchmark-results.md) — p99 latency = 0.29ms (warm), SLO = 94ms
4. [`engineering/benchmark-data/`](engineering/benchmark-data/) — Raw benchmark CSV and JSON

---

## Map of `docs/`

```
docs/
├── INDEX.md                         ← You are here
│
├── engineering/                     ← For developers and engineers
│   ├── architecture.md              ← Algorithm 1, state machines, Redis/Kafka schemas
│   ├── developer-guide.md           ← Setup, test commands, agent roles
│   ├── api-reference.md             ← REST API reference
│   ├── data-pipeline.md             ← Synthetic data generation, training
│   ├── benchmark-results.md         ← p99 latency benchmarks
│   ├── poc-validation-report.md     ← PoC validation results
│   ├── OPEN_BLOCKERS.md             ← Current engineering blockers
│   ├── DEVELOPMENT-START-PROMPT.md  ← Claude Code session initialization
│   ├── default-execution-protocol.md ← Mandatory execution protocol
│   ├── specs/                       ← Component specs + migration specs
│   │   ├── BPI_Architecture_Specification_v1.2.md
│   │   ├── BPI_C1_Component_Spec_v1.0.md   ← ... through BPI_C7
│   │   ├── c1_inference_endpoint_typing.md ← ... migration specs
│   │   └── ... (22 files total)
│   ├── blueprints/                  ← Implementation blueprints
│   │   ├── P3-v0-Implementation-Blueprint.md
│   │   └── ... (P4, P5, P7, P8, P10)
│   ├── codebase/                    ← Subsystem reference docs (14 files)
│   │   ├── README.md                ← Index of subsystem docs
│   │   ├── pipeline.md, api.md, common.md, risk.md, ...
│   ├── review/                      ← Code review reports
│   │   ├── EPIGNOSIS_ARCHITECTURE_REVIEW.md  ← 87KB deep architecture audit
│   │   └── 2026-04-08/              ← Code review (13 batches, B1–B13 findings)
│   │       ├── INDEX.md
│   │       └── 01-integrity-common.md ... 13-tests.md
│   ├── research/                    ← Academic paper, R&D
│   │   ├── Academic-Paper-v2.1.md
│   │   ├── pedigree-rd-roadmap.md
│   │   └── technical-rd-memo.md
│   └── benchmark-data/              ← Raw benchmark data
│       ├── c5_baseline_10ktps.csv
│       └── c5_baseline_10ktps.json
│
├── legal/                           ← For compliance, counsel, regulators
│   ├── compliance.md                ← SR 11-7, EU AI Act, DORA, AML, GDPR
│   ├── bpi_license_agreement_clauses.md
│   ├── c6_sanctions_audit.md
│   ├── patent/                      ← Patent specifications and briefings
│   │   ├── Provisional-Specification-v5.2.md  ← Latest provisional
│   │   ├── Provisional-Specification-v5.1.md
│   │   ├── Patent-Family-Architecture-v2.1.md
│   │   ├── Future-Technology-Disclosure-v2.1.md
│   │   ├── patent_claims_consolidated.md
│   │   └── patent_counsel_briefing.md
│   ├── decisions/                   ← EPG decision register
│   │   ├── README.md                ← Decision register index
│   │   ├── EPG-04-05_hold_bridgeable.md
│   │   ├── EPG-09-10_compliance_hold_audit.md
│   │   ├── EPG-14_borrower_identity.md
│   │   ├── EPG-16-18_aml_caps_human_review.md
│   │   ├── EPG-19_compliance_hold_bridging.md
│   │   └── EPG-20-21_patent_briefing.md
│   └── governance/                  ← Sign-off records and governance
│       ├── BPI_Architecture_SignOff_Record_v1.1.md
│       ├── BPI_Architecture_SignOff_Record_v1.2.md
│       └── BPI_SR11-7_Model_Governance_Pack_v1.0.md
│
├── business/                        ← For pilots, strategy, market analysis
│   ├── CLIENT_PERSPECTIVE_ANALYSIS.md  ← Bank COO perspective, 5 critical gaps
│   ├── LIP_COMPLETE_NARRATIVE.md       ← Business model, patent moat, pipeline story
│   ├── Competitive-Landscape-Analysis.md
│   ├── Market-Fundamentals-Fact-Sheet.md
│   └── bank-pilot/                  ← RBC pilot kit (7 docs)
│       ├── rbc-pilot-strategy.md
│       ├── commercial-overview.md
│       ├── integration-guide.md
│       ├── api-reference.md
│       ├── demo-walkthrough.md
│       ├── gcp-demo-setup.md
│       └── legal-prerequisites.md
│
├── operations/                      ← For DevOps and deployment
│   ├── deployment.md                ← K8s, Helm, HPA, CI/CD
│   ├── Operational-Playbook-v2.1.md
│   └── Master-Action-Plan-2026.md
│
├── models/                          ← For ML engineers and auditors
│   ├── c1-model-card.md             ← M-01: AUC 0.8871, τ★=0.110, ECE 0.069
│   ├── c2-model-card.md             ← M-02: B2B MRFA, Tier 1/2/3 PD
│   ├── c1-training-data-card.md     ← 10M synthetic corpus metadata
│   ├── federated-learning-architecture.md  ← P12 patent, FedProx, DP-SGD
│   └── cbdc-protocol-research.md   ← P9 patent, mBridge/ECB DLT/FedNow
│
└── superpowers/                     ← Sprint planning artifacts
    ├── plans/                       ← Sprint implementation plans
    └── specs/                       ← Sprint design specs
```

---

## Quick Reference

| What you want | Where to look |
|---------------|---------------|
| Run the tests | `PYTHONPATH=. python -m pytest lip/tests/ -m "not slow"` |
| Lint the code | `ruff check lip/` |
| Start local infra | `docker compose up -d && bash scripts/init_topics.sh` |
| Train C1 model | `PYTHONPATH=. python lip/train_all.py --component c1` |
| Fee floor value | `lip/common/constants.py` — `FEE_FLOOR_BPS = 300` |
| C1 threshold (τ★) | `lip/common/constants.py` — `TAU_STAR = 0.110` |
| Why we never bridge compliance holds | [`legal/decisions/EPG-19_compliance_hold_bridging.md`](legal/decisions/EPG-19_compliance_hold_bridging.md) |
| Current open blockers | [`engineering/OPEN_BLOCKERS.md`](engineering/OPEN_BLOCKERS.md) |
| Latest code review | [`engineering/review/2026-04-08/INDEX.md`](engineering/review/2026-04-08/INDEX.md) |
| Patent latest draft | [`legal/patent/Provisional-Specification-v5.2.md`](legal/patent/Provisional-Specification-v5.2.md) |

---

## Maintenance

- When adding a new doc, add it to this index under the appropriate role-based path
- When a decision is made (EPG-XX), add it to `legal/decisions/` and update `legal/decisions/README.md`
- Model cards must be updated whenever a model is retrained (REX authority)
- The `engineering/OPEN_BLOCKERS.md` is the authoritative blocker list — keep it current
- Investor and financial documents are maintained in a separate private repository
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l docs/INDEX.md
```

Expected: approximately 170-190 lines.

- [ ] **Step 3: Commit**

```bash
git add docs/INDEX.md
git commit -m "docs: rewrite INDEX.md with audience-based reading paths and updated docs/ map"
```

---

## Phase 13: Final Verification and Push

### Task 25: Verify Repository Integrity

- [ ] **Step 1: Zero consolidation files references**

```bash
cd /Users/tomegah/PRKT2026
grep -r "consolidation.files\|consolidation%20files" . --exclude-dir=.git
```

Expected: zero matches.

- [ ] **Step 2: Zero stale root-file references in docs/**

```bash
grep -rn "\.\./CLIENT_PERSPECTIVE_ANALYSIS\|\.\./EPIGNOSIS_ARCHITECTURE\|\.\./LIP_COMPLETE_NARRATIVE" docs/
```

These files are now inside docs/ so any `../` prefix pointing to the old root location is stale. Update any matches found.

- [ ] **Step 3: Verify consolidation files directory is gone**

```bash
ls "consolidation files" 2>&1
```

Expected: `ls: consolidation files: No such file or directory`

- [ ] **Step 4: Verify docs/ root is clean (no files that should be in subdirs)**

```bash
ls docs/*.md
```

Expected: only `INDEX.md`

- [ ] **Step 5: Run the test suite to confirm no code references broke**

```bash
PYTHONPATH=. python -m pytest lip/tests/ -m "not slow" -x -q 2>&1 | tail -5
```

Expected: `X passed` with zero failures. The test suite tests Python source code only — no doc paths are imported — but this confirms the reorganization didn't accidentally touch the wrong files.

- [ ] **Step 6: Lint**

```bash
ruff check lip/
```

Expected: `All checks passed.`

- [ ] **Step 7: Git status is clean**

```bash
git status --short
```

Expected: empty output.

### Task 26: Push to GitHub

- [ ] **Step 1: View final commit log**

```bash
git log --oneline -16
```

Expected: 14-15 commits since `backup/pre-reorg`.

- [ ] **Step 2: Push main**

```bash
git push origin main
```

- [ ] **Step 3: Verify on GitHub**

```bash
gh browse
```

Or visit `https://github.com/ryanktomegah/PRKT2026`. Confirm:
- Root shows only `README.md`, `CLAUDE.md`, `PROGRESS.md`, config files
- `consolidation files/` is gone
- `docs/` shows `engineering/`, `legal/`, `business/`, `operations/`, `models/`, `superpowers/`
- `docs/fundraising/` and `docs/governance/` are gone

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task(s) |
|------------------|---------|
| Delete cache/temp dirs (~360 MB) | Task 2 |
| .gitignore missing patterns | Task 3 |
| Sensitive docs → private repo | Tasks 4-5 |
| Duplicate/legacy deletions | Task 6 |
| Patent specs → docs/legal/patent/ | Task 8 |
| Component specs → docs/engineering/specs/ | Task 9 |
| Blueprints → docs/engineering/blueprints/ | Task 10 |
| Governance records → docs/legal/governance/ | Task 11 |
| Academic paper, business, ops, dev prompt | Task 12 |
| Remove consolidation files/ directory | Task 12 |
| Root narratives → docs/ subdirs | Task 13 |
| Engineering docs reorganized | Task 14 |
| Legal docs reorganized | Task 15 |
| Model cards organized | Task 16 |
| Operations and business organized | Task 17 |
| Untracked review files tracked | Task 18 |
| Cross-references in codebase/ fixed | Task 19 |
| Cross-references in decisions/ and others fixed | Task 20 |
| README.md rewritten | Task 21 |
| CLAUDE.md docs structure added | Task 22 |
| PROGRESS.md hardening sprint added | Task 23 |
| INDEX.md complete rewrite | Task 24 |
| Final verification + push | Tasks 25-26 |

All 12 spec phases covered. ✓

### No Placeholders

All code blocks, commands, and expected outputs are fully specified. ✓

### Type Consistency

No code signatures involved — this is a file operations plan. All paths are consistent with the confirmed `ls` output of the actual repository. ✓
