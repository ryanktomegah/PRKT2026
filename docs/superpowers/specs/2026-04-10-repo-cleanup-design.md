# PRKT2026 Repository Cleanup & Documentation Overhaul — Design Spec

**Date**: 2026-04-10
**Status**: Draft
**Scope**: Full repository reorganization, documentation restructure, file cleanup

---

## Context

PRKT2026 (LIP — Liquidity Intelligence Platform) has grown organically over 6 weeks of intense AI-assisted development (471 commits, 7 AI agents). The result: a technically sound codebase (`lip/`) surrounded by scattered documentation across 3 tiers (`consolidation files/`, `docs/`, root-level narratives), ~360 MB of cached artifacts, duplicate files, sensitive business documents in a public repo, and a root directory cluttered with large analysis files.

**Goal**: Transform the repository into a clean, professionally organized project with audience-based documentation, no sensitive material exposed, and every file in its logical place.

**Non-goals**: We do NOT touch the `lip/` source package, `docs/superpowers/`, or `.claude/` configuration. The codebase is well-organized; only the surrounding documentation and repository hygiene need work.

---

## Decisions (User-Confirmed)

| Decision | Choice |
|----------|--------|
| Sensitive business docs | Move to private repo, remove from PRKT2026 |
| `consolidation files/` (46 files, space in name) | Decompose into `docs/` subdirectories, delete directory |
| Root narrative files | Move to `docs/`; keep PROGRESS.md at root |
| Docs organization principle | Audience-based: engineering, legal, business, operations, models |
| Master-Action-Plan-2026.md | Keep in `docs/operations/` (not private repo) |
| .docx binary files | Delete (`.md` equivalents are canonical) |
| Extra sensitive files (ip-risk-analysis-prompt, Unit-Economics-Exhibit) | Private repo |

---

## Phase 0: Local Filesystem Cleanup

**No git operations. Untracked/gitignored files only.**

| Target | Size | Action |
|--------|------|--------|
| `pytest-of-tomegah/` | 109 MB | `rm -rf` |
| `.mypy_cache/` | 250 MB | `rm -rf` |
| `torchinductor_tomegah/` | 0 B | `rm -rf` |
| `.DS_Store` files (4 locations) | ~38 KB | `rm -f` |
| `.coverage` | 53 KB | `rm -f` |
| `mlflow.db` | 963 KB | `rm -f` |
| `artifacts/c1_trained/c1_trained/` | ~10 MB | `rm -rf` (nested duplicate) |

**Recovery**: ~360 MB disk space

---

## Phase 1: .gitignore Update

Add missing patterns to `/Users/tomegah/PRKT2026/.gitignore`:

```
.mypy_cache/
torchinductor_*/
```

**Commit**: `chore: add .mypy_cache/ and torchinductor_*/ to .gitignore`

---

## Phase 2: Private Repo Extraction

**Prerequisite**: User creates private GitHub repo.

### Files to remove (20 total):

**From `docs/fundraising/` (entire directory, 10 files):**
- ip-risk-pre-counsel-analysis.md (143 KB)
- ip-risk-pre-counsel-analysis-revised.md
- ip-risk-analysis-prompt.md
- ff-round-structure.md
- valuation-analysis.md
- safe-agreement-template.md
- nda-template.md
- investor-risk-disclosure.md
- pre-fundraising-checklist.md
- generate_nda_docx.py

**From `docs/governance/` (entire directory, 1 file):**
- Founder-Protection-Strategy.md (42 KB)

**From `consolidation files/` (9 files):**
- Capital-Partner-Strategy.md
- Founder-Financial-Model.md
- Revenue-Projection-Model.md
- Investor-Briefing-v2.1.md
- Revenue-Acceleration-Analysis.md
- Section-85-Rollover-Briefing-v1.1.md
- GTM-Strategy-v1.0.md (66 KB)
- Unit-Economics-Exhibit.md

**Commit**: `chore: remove sensitive fundraising, governance, and business docs (moved to private repo)`

---

## Phase 3: Delete Duplicates & Legacy

| File | Reason |
|------|--------|
| `consolidation files/BPI_Gap_Analysis_v2.0 (1).md` | Exact duplicate of `BPI_Gap_Analysis_v2.0.md` |
| `consolidation files/01_Provisional_Specification_v5.docx` | `.md` version is canonical |
| `consolidation files/07_Academic_Paper_v2.docx` | `.md` version is canonical |
| `scripts/train_all.py` | Legacy duplicate of `lip/train_all.py` |

**Commit**: `chore: remove duplicate files and legacy scripts/train_all.py`

---

## Phase 4: Create New Directory Structure

```bash
mkdir -p docs/engineering/{specs,blueprints,research,review,benchmark-data}
mkdir -p docs/legal/{patent,governance}
mkdir -p docs/business
mkdir -p docs/operations
mkdir -p docs/models
```

---

## Phase 5: Decompose `consolidation files/`

### 5a: Patent docs → `docs/legal/patent/`
- Provisional-Specification-v5.1.md
- Provisional-Specification-v5.2.md
- Patent-Family-Architecture-v2.1.md
- Future-Technology-Disclosure-v2.1.md

### 5b: Component & architecture specs → `docs/engineering/specs/`
- BPI_Architecture_Specification_v1.2.md
- BPI_C1 through BPI_C7 Component Specs (11 files)
- BPI_Gap_Analysis_v2.0.md
- BPI_Internal_Build_Validation_Roadmap_v1.0.md
- BPI_Open_Questions_Resolution_v1.0.md
- BPI_C7_Bank_Deployment_Guide_v1.0.md

Also merge existing `docs/specs/` migration specs (7 files) into `docs/engineering/specs/`.

### 5c: Implementation blueprints → `docs/engineering/blueprints/`
- P3-v0 through P10-v0 Implementation Blueprints (6 files)

### 5d: Sign-off & governance records → `docs/legal/governance/`
- BPI_Architecture_SignOff_Record_v1.1.md
- BPI_Architecture_SignOff_Record_v1.2.md
- BPI_SR11-7_Model_Governance_Pack_v1.0.md

### 5e: Academic paper → `docs/engineering/research/`
- Academic-Paper-v2.1.md

### 5f: Business docs → `docs/business/`
- Competitive-Landscape-Analysis.md
- Market-Fundamentals-Fact-Sheet.md

### 5g: Operations docs → `docs/operations/`
- Operational-Playbook-v2.1.md
- Master-Action-Plan-2026.md

### 5h: Remaining
- DEVELOPMENT-START-PROMPT.md → `docs/engineering/`
- Remove empty `consolidation files/` directory

**Commits**: One per sub-step (5a-5h), or consolidated into 2-3 logical commits.

---

## Phase 6: Move Root Narrative Files

| File | Destination |
|------|-------------|
| CLIENT_PERSPECTIVE_ANALYSIS.md (52 KB) | `docs/business/` |
| EPIGNOSIS_ARCHITECTURE_REVIEW.md (87 KB) | `docs/engineering/review/` |
| LIP_COMPLETE_NARRATIVE.md (44 KB) | `docs/business/` |

**PROGRESS.md stays at root.**

**Commit**: `docs: move root narrative files to audience-based docs/ subdirectories`

---

## Phase 7: Reorganize Existing `docs/` Files

### Engineering
- architecture.md → `docs/engineering/`
- developer-guide.md → `docs/engineering/`
- data-pipeline.md → `docs/engineering/`
- benchmark-results.md → `docs/engineering/`
- api-reference.md → `docs/engineering/`
- OPEN_BLOCKERS.md → `docs/engineering/`
- poc-validation-report.md → `docs/engineering/`
- pedigree-rd-roadmap.md → `docs/engineering/research/`
- technical-rd-memo.md → `docs/engineering/research/`
- `docs/codebase/` → `docs/engineering/codebase/`
- `docs/benchmark-results/` → `docs/engineering/benchmark-data/`

### Legal
- compliance.md → `docs/legal/`
- patent_claims_consolidated.md → `docs/legal/patent/`
- patent_counsel_briefing.md → `docs/legal/patent/`
- bpi_license_agreement_clauses.md → `docs/legal/`
- c6_sanctions_audit.md → `docs/legal/`
- `docs/decisions/` → `docs/legal/decisions/`

### Models
- c1-model-card.md → `docs/models/`
- c2-model-card.md → `docs/models/`
- c1-training-data-card.md → `docs/models/`
- federated-learning-architecture.md → `docs/models/`
- cbdc-protocol-research.md → `docs/models/`

### Operations
- deployment.md → `docs/operations/`

### Business
- `docs/bank-pilot/` → `docs/business/bank-pilot/`

### Track untracked review docs
- `docs/review/2026-04-08/` (14 files) → `docs/engineering/review/2026-04-08/`

---

## Phase 8: Fix All Cross-References

**~20 files** need internal link updates. Key targets:

| File | Impact |
|------|--------|
| `docs/INDEX.md` | **Complete rewrite** — 24+ stale `consolidation files/` refs, all reading paths |
| `README.md` | **Complete rewrite** — repo layout, all docs/ links |
| `docs/engineering/codebase/*.md` (7 files) | Update `consolidation files/` refs to new paths |
| `docs/legal/decisions/*.md` (3 files) | Update refs to EPIGNOSIS review, consolidation files |
| `docs/engineering/DEVELOPMENT-START-PROMPT.md` | 7 `consolidation files/` refs |
| `docs/business/LIP_COMPLETE_NARRATIVE.md` | 2 `consolidation files/` refs |
| `docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md` | 2 `consolidation files/` refs |
| `PROGRESS.md` | Refs to moved files |
| `CLAUDE.md` | Add docs structure overview |

**Verification**: `grep -r "consolidation files" docs/` and `grep -r "consolidation%20files" docs/` must return zero results after this phase.

**Commit**: `docs: update all internal cross-references after reorganization`

---

## Phase 9: README.md Rewrite

Full rewrite including:
- Updated repository layout diagram (new `docs/` tree)
- Current metrics (1284 tests, 92% coverage)
- Component table (C1-C8 + C9, P5, P10)
- Navigation to audience-based docs
- Quick start guide
- Architecture overview
- Patent coverage summary
- Remove all references to `consolidation files/`

**Commit**: `docs: rewrite README.md for new docs/ structure`

---

## Phase 10: CLAUDE.md Update

- Add documentation structure overview section
- Verify no stale path references
- DO NOT touch canonical constants, agent roles, or EPG decisions

**Commit**: `docs: add documentation structure overview to CLAUDE.md`

---

## Phase 11: PROGRESS.md Update

- Add hardening sprint entries (107 commits since last update on 2026-03-21)
- Update test count and coverage metrics
- Add repository reorganization entry
- Fix any refs to moved files

**Commit**: `docs: update PROGRESS.md with hardening sprint and current metrics`

---

## Phase 12: INDEX.md Complete Rewrite

The docs front door — complete rewrite:
- Remove "Three Documentation Layers" concept
- Update all 6 role-based reading paths
- Replace investor reading path with private repo note
- Rewrite docs/ map to reflect new structure
- Update Quick Reference table

**Commit**: `docs: rewrite INDEX.md for audience-based docs/ structure`

---

## Final Directory Tree

```
PRKT2026/
├── .claude/                     (preserved)
├── .github/workflows/           (preserved)
├── .gitignore                   (updated)
├── CLAUDE.md                    (updated)
├── PROGRESS.md                  (updated)
├── README.md                    (rewritten)
├── docker-compose.yml           (preserved)
├── requirements.txt             (preserved)
├── requirements-ml.txt          (preserved)
├── lip/                         (UNTOUCHED — production package)
├── scripts/                     (train_all.py removed)
├── docs/
│   ├── INDEX.md                 (rewritten entry point)
│   ├── engineering/
│   │   ├── architecture.md
│   │   ├── developer-guide.md
│   │   ├── api-reference.md
│   │   ├── data-pipeline.md
│   │   ├── benchmark-results.md
│   │   ├── poc-validation-report.md
│   │   ├── OPEN_BLOCKERS.md
│   │   ├── DEVELOPMENT-START-PROMPT.md
│   │   ├── default-execution-protocol.md
│   │   ├── specs/               (22 files: BPI specs + migration specs)
│   │   ├── blueprints/          (6 files: P3-P10 blueprints)
│   │   ├── codebase/            (14 files: subsystem reference)
│   │   ├── review/              (EPIGNOSIS + 2026-04-08 code review)
│   │   ├── research/            (academic paper, R&D memos)
│   │   └── benchmark-data/      (CSV + JSON baselines)
│   ├── legal/
│   │   ├── compliance.md
│   │   ├── bpi_license_agreement_clauses.md
│   │   ├── c6_sanctions_audit.md
│   │   ├── patent/              (6 files: specs, claims, briefing)
│   │   ├── decisions/           (7 files: EPG register)
│   │   └── governance/          (3 files: sign-off, SR 11-7)
│   ├── business/
│   │   ├── CLIENT_PERSPECTIVE_ANALYSIS.md
│   │   ├── LIP_COMPLETE_NARRATIVE.md
│   │   ├── Competitive-Landscape-Analysis.md
│   │   ├── Market-Fundamentals-Fact-Sheet.md
│   │   └── bank-pilot/          (7 files: RBC pilot kit)
│   ├── operations/
│   │   ├── deployment.md
│   │   ├── Operational-Playbook-v2.1.md
│   │   └── Master-Action-Plan-2026.md
│   ├── models/
│   │   ├── c1-model-card.md
│   │   ├── c2-model-card.md
│   │   ├── c1-training-data-card.md
│   │   ├── federated-learning-architecture.md
│   │   └── cbdc-protocol-research.md
│   └── superpowers/             (PRESERVED as-is)
```

---

## Commit Plan (14 commits)

| # | Message | Files |
|---|---------|-------|
| 1 | `chore: add .mypy_cache/ and torchinductor_*/ to .gitignore` | 1 |
| 2 | `chore: remove sensitive docs (moved to private repo)` | 20 deletions |
| 3 | `chore: remove duplicates and legacy scripts/train_all.py` | 4 deletions |
| 4 | `docs: move patent specs to docs/legal/patent/` | 4 moves |
| 5 | `docs: move component specs and migration specs to docs/engineering/specs/` | 22 moves |
| 6 | `docs: move blueprints to docs/engineering/blueprints/` | 6 moves |
| 7 | `docs: move governance records to docs/legal/governance/` | 3 moves |
| 8 | `docs: move remaining consolidation files; remove directory` | ~8 moves |
| 9 | `docs: move root narratives to docs/business/ and docs/engineering/review/` | 3 moves |
| 10 | `docs: reorganize existing docs/ into audience-based structure` | ~30 moves |
| 11 | `docs: update all cross-references` | ~20 edits |
| 12 | `docs: rewrite README.md` | 1 rewrite |
| 13 | `docs: update CLAUDE.md, PROGRESS.md` | 2 updates |
| 14 | `docs: rewrite INDEX.md for new structure` | 1 rewrite |

---

## Verification

1. `git branch backup/pre-reorg` before starting
2. `grep -r "consolidation files" .` returns 0 results (excluding .git/)
3. `grep -r "consolidation%20files" .` returns 0 results
4. `PYTHONPATH=. python -m pytest lip/tests/` — all 1284+ tests pass
5. Markdown link checker on all `.md` files
6. `ls "consolidation files" 2>/dev/null` returns "No such file"
7. `git status` is clean after final commit
8. Private repo contains all 20 extracted files
