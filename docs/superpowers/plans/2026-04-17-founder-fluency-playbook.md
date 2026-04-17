# Founder Fluency Playbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a version-controlled, in-repo Founder Fluency Playbook that turns the founder's existing fundraising documentation into production-grade spoken investor fluency across three weak-point volumes (Technical Depth, Patent/IP, Market/Timing).

**Architecture:** Static markdown artefacts under `docs/business/fundraising/founder-fluency/`. Three volumes × three layers (narrative / drill / bear-case) + master braided narrative + appendices + CHANGELOG discipline. No software — the "live-drill mode" is a convention for Claude Code sessions that reads the same markdown files as its script. Detailed design: `docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md`.

**Tech Stack:** Markdown, Git, GitHub. No code. No tests. Acceptance criteria per task replace unit tests (voice rulebook enforcement, structure-completeness checks, cross-reference integrity).

---

## Conventions used in this plan

- **"Acceptance criteria"** replaces "Write failing test → run test fail → implement → run test pass". For a writing artefact, the test is whether the produced file meets the structural and voice checklist in that task.
- Every task ends with a commit + push on the `codex/founder-fluency-playbook-design` branch (already created in brainstorming sprint; the spec commit `a2733ef` is the branch starting point).
- Every task that produces or updates a Playbook file also writes a `CHANGELOG.md` entry following the format defined in the spec.
- **Voice rulebook** (applies to every content task): short sentences, active verbs, numbers named exactly (spell them out first time, then digits), no weasel words ("kind of", "sort of", "basically", "essentially"), no apologies, no jargon without immediate plain-English gloss, anchors used consistently.
- **File paths are absolute** under the Playbook root `docs/business/fundraising/founder-fluency/`.

---

## Phase 0 — Scaffolding

Goal: Create the empty skeleton of the Playbook with mandatory headers. After Phase 0, the folder structure is fully in place; subsequent phases fill it.

### Task 0.1: Create folder structure and placeholder files

**Files:**
- Create: `docs/business/fundraising/founder-fluency/README.md`
- Create: `docs/business/fundraising/founder-fluency/CHANGELOG.md`
- Create: `docs/business/fundraising/founder-fluency/00-master-narrative.md`
- Create: `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md`
- Create: `docs/business/fundraising/founder-fluency/01-technical-depth/drill.md`
- Create: `docs/business/fundraising/founder-fluency/01-technical-depth/bear-case.md`
- Create: `docs/business/fundraising/founder-fluency/02-patent-ip/narrative.md`
- Create: `docs/business/fundraising/founder-fluency/02-patent-ip/drill.md`
- Create: `docs/business/fundraising/founder-fluency/02-patent-ip/bear-case.md`
- Create: `docs/business/fundraising/founder-fluency/03-market-timing/narrative.md`
- Create: `docs/business/fundraising/founder-fluency/03-market-timing/drill.md`
- Create: `docs/business/fundraising/founder-fluency/03-market-timing/bear-case.md`
- Create: `docs/business/fundraising/founder-fluency/appendix-numbers.md`
- Create: `docs/business/fundraising/founder-fluency/appendix-names.md`
- Create: `docs/business/fundraising/founder-fluency/bear-case-resolved.md`
- Create: `docs/business/fundraising/founder-fluency/session-log.md`

- [ ] **Step 1: Create all folders and empty files with the placeholder stub below**

Every file starts as a minimal stub with the right H1 and a one-line "this file will contain…" note so no file is silently empty in the repo.

Stub template for each narrative.md:
```markdown
# [Volume Name] — Narrative

_This file will contain four tiers (30-second / 2-minute / 5-minute / deep-dive) of the [volume] pitch, with one-sentence handoffs to adjacent volumes. Phase 2/3/4 populates this file._
```

Stub template for each drill.md:
```markdown
# [Volume Name] — Drill

_This file will contain the Q&A bank organised by persona × difficulty. Minimum 20 questions at launch, growing to ~50. Phase 2/3/4 populates; Phase 6 scales._
```

Stub template for each bear-case.md:
```markdown
# [Volume Name] — Bear Case

_This file will contain honest weaknesses with structured answers. Master Index at the top ranks entries by (likelihood asked × severity if fumbled). Phase 2/3/4 populates._
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- All 16 files exist at the paths listed above
- No file is zero bytes
- `ls -R docs/business/fundraising/founder-fluency/` matches the file layout in the spec

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/
git commit -m "docs(founder-fluency): scaffold Phase 0 folder structure and stubs"
```

---

### Task 0.2: Write README.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/README.md`

- [ ] **Step 1: Replace the stub with the full README content below**

```markdown
# Founder Fluency Playbook

A written, in-repo training artefact that turns the founder's fundraising documentation into production-grade spoken investor fluency. **This is not software.** Every file is a markdown document you read like a book.

## Who this is for

The founder, preparing for investor conversations. Secondary use: any team member who needs to represent LIP to investors.

## How it's organised

Three **volumes**, each covering one of the founder's weakest-feeling topics:
- **01-technical-depth/** — how LIP works, why it's fast, why the architecture is right
- **02-patent-ip/** — the novel claim, prior art, IP ownership
- **03-market-timing/** — TAM, why now, why this window

Each volume has three **layers**:
- **narrative.md** — the story, in four depth tiers (30-second / 2-minute / 5-minute / deep-dive). Read like a book.
- **drill.md** — the Q&A bank by investor persona × difficulty. Self-quiz or use live-drill mode.
- **bear-case.md** — honest weaknesses with structured answers. The layer that separates an owner from a pitcher.

Plus:
- **00-master-narrative.md** — the braided pitch that weaves all three volumes into one spoken story.
- **appendix-numbers.md** — single source of truth for every figure you may be asked to cite.
- **appendix-names.md** — people, firms, regulators, prior art.
- **CHANGELOG.md** — dated updates. Every number move, every bear-case evolution, every new investor question gets logged here.

## How to use it

**Primary mode — read.** Open any `narrative.md` and read it end-to-end. Re-read. The narratives are written in voice-ready prose — short sentences, active verbs, named anchors. Memorise the 30-second tier verbatim; absorb the structure of the others.

**Secondary mode — self-quiz.** Open any `drill.md`. Cover the "Gold-standard answer" block. Read the question, answer out loud, then reveal. Mark anything you flubbed.

**Optional mode — live-drill with Claude.** In a Claude Code session, say *"Drill me on the Technical volume"* or *"Gauntlet me on Patent"* or *"Bear-case deep dive, META-01"*. Claude reads `drill.md` as its script and plays investor. Grades at the end. You can always say *"pause"* or *"stop"* to exit.

## Session modes (for live-drill)

| Mode | Shape |
|---|---|
| Warm-up | 3 friendly questions, confidence-building |
| Targeted drill | Single persona × difficulty × volume; 5 questions |
| Gauntlet | 5 questions across personas, escalating, strict grading |
| Bear-case deep dive | One bear-case entry, adversarial persona, 5 different angles |

## Maintenance rituals (non-optional for this Playbook to stay honest)

| Ritual | Cadence | Purpose |
|---|---|---|
| Weekly Gauntlet | Weekly | 15 min, rotating volume |
| Pre-meeting prep | Before any investor call | Warm-up + Targeted drill on likely-topic volume |
| Monthly META drill | Monthly | Bear-case deep dive on META-01/02/03, rotating |
| Quarterly truth-calibration | Quarterly | Re-read every `bear-case.md`. Tag each Resolved / Evolved / New. Full-spectrum gauntlet; compare score to prior quarter |

## The hard rules

- No numbers spoken that aren't in `appendix-numbers.md`.
- No names spoken that aren't in `appendix-names.md`.
- No bear-case entry goes untouched for a quarter.
- Every real investor question ends up in `drill.md` within the week.
- Every change produces a `CHANGELOG.md` entry.

## Related documents

- Design spec: `docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md`
- Existing investor docs: `docs/business/Investor-Briefing-v2.1.md`, `docs/business/LIP_COMPLETE_NARRATIVE.md`, `docs/business/CLIENT_PERSPECTIVE_ANALYSIS.md`
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- All sections above present (Who / How organised / How to use / Session modes / Rituals / Hard rules / Related)
- No placeholders, no TBDs
- Passes voice rulebook (no weasel words, short sentences)

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/README.md
git commit -m "docs(founder-fluency): write Phase 0 README with usage + rituals"
```

---

### Task 0.3: Initialise CHANGELOG.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/CHANGELOG.md`

- [ ] **Step 1: Replace stub with initial CHANGELOG**

```markdown
# Founder Fluency Playbook — CHANGELOG

All material changes to the Playbook are logged here. Entry format:
`- [category] Description (file:ref)`

Categories:
- `[numbers]` — canonical number moved
- `[bear-case]` — bear-case entry evolved, resolved, or added
- `[drill]` — new drill question added (from real conversation)
- `[narrative]` — narrative tier rewritten
- `[structural]` — folder, file, or schema change

---

## 2026-04-17

- [structural] Phase 0 scaffolding complete: folder structure, README, CHANGELOG, stub files for all volumes and appendices.
```

- [ ] **Step 2: Commit**

```bash
git add docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): initialise CHANGELOG with Phase 0 entry"
```

---

### Task 0.4: Push Phase 0

- [ ] **Step 1: Push branch**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- `git log --oneline -5` shows three Phase 0 commits on top of the design spec commit `a2733ef`
- Branch is pushed and trackable on GitHub

---

## Phase 1 — Appendix-numbers + Appendix-names

Goal: Extract every canonical number and name from existing docs into single-source-of-truth files. Any narrative or drill answer in later phases cites these as authoritative.

### Task 1.1: Extract canonical numbers from existing docs

**Files:**
- Read: `docs/business/Investor-Briefing-v2.1.md`
- Read: `docs/business/Founder-Financial-Model.md`
- Read: `docs/business/Unit-Economics-Exhibit.md`
- Read: `docs/business/Revenue-Projection-Model.md`
- Read: `docs/business/Competitive-Landscape-Analysis.md`
- Read: `docs/business/Market-Fundamentals-Fact-Sheet.md`
- Read: `docs/business/LIP_COMPLETE_NARRATIVE.md`
- Read: `README.md` (repo root)
- Read: `CLAUDE.md` (for canonical constants)
- Read: `lip/common/constants.py` (for QUANT-locked constants)

- [ ] **Step 1: Grep for numbers and their context**

Search each file for numeric literals with context. Produce a working list. Focus on these categories:
- **Product/technical:** latency SLO, fee floor, maturity windows, test count, coverage %, C1 decision threshold, UETR TTL buffer, anything else QUANT-locked
- **Economics:** fee splits, warehouse terms, capital efficiency %, LTV/CAC, pricing tiers, bank fee shares
- **Market:** TAM, SAM, SOM, SWIFT volume, correspondent banking size, ISO 20022 migration deadline
- **Traction:** pilot bank count (currently zero), LOI count, test count
- **Compliance:** AML cap defaults, salt rotation period, license term

- [ ] **Step 2: Cross-check against canonical sources**

For every number extracted, verify against `lip/common/constants.py` or `CLAUDE.md`'s "Canonical Constants" section. If a number disagrees, flag it in the appendix with `⚠ DISCREPANCY` and list both sources. QUANT-locked constants (fee floor 300 bps, latency 94ms, etc.) are ground truth.

- [ ] **Step 3: Acceptance criteria**

Verify:
- At least 40 canonical numbers extracted and contextualised
- Every QUANT-locked constant from `CLAUDE.md` is represented
- Discrepancies between docs are flagged, not silently resolved

- [ ] **Step 4: No commit yet — output feeds Task 1.2**

---

### Task 1.2: Write appendix-numbers.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/appendix-numbers.md`

- [ ] **Step 1: Organise numbers into the template below**

```markdown
# Appendix — Canonical Numbers

Single source of truth for every figure the founder may cite in an investor conversation. **Any number spoken in a pitch must come from this file.** If a number needs to change, change it here first and propagate outward (update narratives, drill answers, bear-case text that reference it; log in CHANGELOG).

## Product & Technical

| Figure | Value | Source | Notes |
|---|---|---|---|
| Latency SLO | 94ms | `lip/common/constants.py` — QUANT-locked | End-to-end pacs.002 → loan offer |
| Fee floor | 300 bps | `lip/common/constants.py` — QUANT-locked | No code may produce a fee below this |
| Maturity — CLASS_A | 3 days | `lip/common/constants.py` | Technical/operational failures |
| Maturity — CLASS_B | 7 days | `lip/common/constants.py` | Systemic/processing delays |
| Maturity — CLASS_C | 21 days | `lip/common/constants.py` | Long-tail |
| C1 decision threshold (τ★) | 0.110 | `lip/common/constants.py` | |
| UETR TTL buffer | 45 days | `lip/common/constants.py` | |
| Salt rotation | 365 days, 30-day overlap | `CLAUDE.md` | |
| Tests passing | 1,284 | `README.md` line 3 | Update on every material test-count change |
| Coverage | 92% | `README.md` line 4 | |
| Components | 8 (C1-C8) + 3 (C9, P5, P10) | `README.md` | |

## Economics

| Figure | Value | Source | Notes |
|---|---|---|---|
| BPI fee share | 30% | `docs/business/Unit-Economics-Exhibit.md`; Capital-Partner-Strategy.md | Historical discrepancy with 15% — 30% is canonical |
| Warehouse eligibility threshold | 800 bps | `docs/business/Unit-Economics-Exhibit.md` | Two-tier pricing floor |
| (Add remaining economics figures from Task 1.1 extraction) | | | |

## Market

| Figure | Value | Source | Notes |
|---|---|---|---|
| Correspondent banking volume (global) | [extract from Market-Fundamentals-Fact-Sheet.md] | | |
| ISO 20022 migration deadline | [extract] | | |
| (Add remaining market figures) | | | |

## Traction

| Figure | Value | Source | Notes |
|---|---|---|---|
| Bank LOIs signed | 0 | Current state as of 2026-04-17 | Update when RBC signs |
| Production pilots live | 0 | Current state | META-02 bear case references this |
| (Add remaining traction figures) | | | |

## Compliance

| Figure | Value | Source | Notes |
|---|---|---|---|
| AML dollar cap default | 0 (unlimited) | `CLAUDE.md` EPG-16 | Per-licensee via C8 token |
| AML count cap default | 0 (unlimited) | `CLAUDE.md` EPG-16 | |
| (Add remaining compliance figures) | | | |

---

## Discrepancies flagged during Phase 1

[List any contradictions between source docs here. Resolution happens outside this file — this is the honest log of what didn't match.]

## Update protocol

When a figure changes:
1. Update the Value column here.
2. Grep the Playbook for the old value: `grep -r "OLD_VALUE" docs/business/fundraising/founder-fluency/`.
3. Update every narrative/drill/bear-case reference.
4. Log in `CHANGELOG.md` with category `[numbers]`.
```

- [ ] **Step 2: Fill all extracted numbers into the table rows marked `(Add remaining…)`**

Every row from Task 1.1's extraction must appear in exactly one category. Numbers extracted from multiple sources get a single canonical row with the primary Source column citing the ground-truth location (code > CLAUDE.md > spec docs > narrative docs, in that order).

- [ ] **Step 3: Acceptance criteria**

Verify:
- Every QUANT-locked constant appears in the Product & Technical section
- Every extracted number from Task 1.1 appears exactly once
- Discrepancies section is populated or explicitly says "None found"
- File passes voice rulebook (table cells should be terse — this is a reference doc, not prose)

- [ ] **Step 4: Update CHANGELOG and commit**

Add entry to `docs/business/fundraising/founder-fluency/CHANGELOG.md`:
```markdown
## 2026-04-17
- [numbers] Appendix-numbers.md populated with [N] canonical figures across Product/Economics/Market/Traction/Compliance categories.
```

```bash
git add docs/business/fundraising/founder-fluency/appendix-numbers.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): populate appendix-numbers.md with canonical figures"
```

---

### Task 1.3: Write appendix-names.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/appendix-names.md`

- [ ] **Step 1: Write the file with all named entities the founder may cite**

```markdown
# Appendix — Canonical Names

Single source of truth for every person, firm, regulator, standard, or prior-art reference the founder may cite in an investor conversation. **Any name spoken in a pitch must come from this file.** Canonical spelling and pronunciation matter — misnaming a regulator or a competitor is a visible tell.

## People

| Name | Role | Relevance | Spelling / pronunciation note |
|---|---|---|---|
| Bruce Ross | Head, RBC AI Group | Potential pilot champion | |
| (Add others referenced in existing pilot and investor docs) | | | |

## Firms / banks

| Name | Relevance | Spelling note |
|---|---|---|
| RBC (Royal Bank of Canada) | Primary pilot target; founder's current employer (META-01) | |
| RBCx | RBC's innovation arm | Lowercase "x" |
| JPMorgan Chase | Incumbent; holder of prior-art patent US7089207B1 | "JPMorgan" one word |
| BNY Mellon | Correspondent-banking incumbent | |
| Wise | Fintech competitor (FX rails, not LIP's wedge) | |
| Stripe | Fintech infrastructure competitor | |
| (Add remaining from Competitive-Landscape-Analysis.md) | | |

## Regulators and regimes

| Name | Jurisdiction | Relevance to LIP |
|---|---|---|
| AMLD6 | EU | Art. 10 criminal liability for legal persons; drives compliance-hold NEVER rule (EPG-19) |
| AMLD7 | EU (pending) | Bear-case B-MKT-05 |
| SR 11-7 | US (Federal Reserve) | Model governance — LIP's data cards and model cards structure |
| EU AI Act | EU | Art. 14 human oversight → EPG-18 C6 anomaly routing |
| DORA | EU | Operational resilience |
| FATF | International | Recommendation 13 (correspondent KYC), Recommendation 21 (tipping-off) |
| OFAC / SDN | US | Sanctions regime |

## Standards and protocols

| Name | Relevance | Spelling note |
|---|---|---|
| ISO 20022 | Core messaging standard; LIP reads pacs.002 rejections | "ISO 20022" with space |
| pacs.002 | The specific rejection message LIP intercepts | lowercase, period |
| SWIFT GPI | Global Payments Innovation; calibration source for synthetic corpus | |
| UETR | Unique End-to-end Transaction Reference | |
| BIC | Bank Identifier Code; governing-law derivation (EPG-14) | |

## Prior art and patents

| Reference | Owner | Relevance |
|---|---|---|
| US7089207B1 | JPMorgan Chase | Closest prior art; LIP's novelty is the extension to Tier 2/3 private counterparties via Damodaran industry-beta and Altman Z' thin-file models |
| (Add any other patents referenced in `docs/legal/patent/`) | | |

## Internal frameworks (LIP's own named concepts)

| Name | What it is | Why it matters in a pitch |
|---|---|---|
| Two-step classification | The core novel patent claim | Anchor phrase — repeat consistently |
| Conditional offer mechanism | The logic that gates loan offers on classification output | |
| Class A / B / C | Failure taxonomy tiers | CLASS_B label warning: systemic/processing delays only, NOT compliance holds |
| EPG decisions | EPIGNOSIS architecture review register (EPG-04 through EPG-23) | Shows governance maturity in diligence |
| Ford Principle | Team working model: agents push back on wrong direction | Evidence for META-03 framing |
| QUANT / CIPHER / REX / etc. | Named internal agents with authority over specific domains | Demonstrates deliberate governance |

## Update protocol

When a name is added (e.g. a new person becomes relevant, a new regulator enters the picture):
1. Add a row here.
2. Log in CHANGELOG with `[names]` category.
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- Every entity referenced in any existing fundraising doc is captured
- Every EPG decision referenced in CLAUDE.md has a named concept row
- Canonical spelling column is filled where spelling is non-obvious (RBCx lowercase x, etc.)

- [ ] **Step 3: Update CHANGELOG and commit**

```markdown
## 2026-04-17
- [names] Appendix-names.md populated with people, firms, regulators, standards, prior art, and internal frameworks.
```

```bash
git add docs/business/fundraising/founder-fluency/appendix-names.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): populate appendix-names.md"
```

---

### Task 1.4: Push Phase 1

- [ ] **Step 1: Push branch**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- `appendix-numbers.md` and `appendix-names.md` are both on remote
- Phase 1 CHANGELOG entries are on remote

---

## Phase 2 — Technical Depth volume

Goal: Complete `01-technical-depth/` — narrative (4 tiers), drill (20 questions minimum), bear-case (5-7 entries including META-02 and META-03 masters).

### Task 2.1: Choose Technical volume anchors

**Files:**
- Read: `README.md`, `docs/engineering/architecture.md`, `CLAUDE.md`
- Working output (no file change): list of 3-5 anchor phrases

- [ ] **Step 1: Read and extract candidate anchors**

Read the architecture documents and extract candidate anchor phrases — phrases that will be repeated verbatim across all four narrative tiers and every drill answer. Candidates typically include:
- A named technical mechanism (e.g. "two-step classification")
- A named performance number (e.g. "94 milliseconds")
- A named economic constant (e.g. "300 basis points fee floor")
- A named market trigger (e.g. "ISO 20022 migration window")
- A named architectural choice (e.g. "synthetic-first build")

- [ ] **Step 2: Commit to 3-5 anchors**

Pick the 3-5 that best carry the Technical story. Write them in the working output as a bulleted list with a one-sentence justification for each. These anchors lock — every Technical narrative tier must use them, and every Technical drill answer must route to at least one of them.

- [ ] **Step 3: Acceptance criteria**

Verify:
- Between 3 and 5 anchors chosen
- Each is a short phrase (under 6 words)
- Each is defensible in one sentence
- No anchor is abstract marketing language ("best-in-class", "innovative") — all are concrete

- [ ] **Step 4: Save anchors as a draft header in narrative.md (not yet committed)**

Open `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md` and add a header block (to be kept in final file):

```markdown
# Technical Depth — Narrative

**Canonical anchors (use verbatim across all tiers and drill answers):**
1. [Anchor 1] — [one-sentence justification]
2. [Anchor 2] — …
3. [Anchor 3] — …
(4-5 optional)
```

Do not commit yet — Task 2.2 continues the file.

---

### Task 2.2: Write Technical narrative Tier A (30-second)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md`

- [ ] **Step 1: Draft Tier A as exactly 3 sentences**

Append to the file under `## Tier A — 30-second`:

Structure (enforced):
- Sentence 1: What LIP does, in plain English.
- Sentence 2: Why it's hard (the technical problem).
- Sentence 3: The core trick (must include the primary anchor from Task 2.1).

Voice rulebook applies. Read aloud; must fit in 30 seconds at natural pace.

- [ ] **Step 2: Add the handoff line**

End Tier A with one sentence that points to the adjacent volumes:
*"…and that [primary anchor] is exactly what our patent claims — which is why the ISO 20022 migration window is our market-timing bet."*

Adapt wording to the actual anchors chosen in Task 2.1.

- [ ] **Step 3: Acceptance criteria**

Verify:
- Exactly 3 sentences in Tier A plus 1 handoff line
- Primary anchor appears verbatim
- Read aloud by hand, timed — under 30 seconds
- Voice rulebook passes (no weasel words, short sentences, active verbs, numbers named exactly)

- [ ] **Step 4: Do not commit yet — Task 2.3 continues**

---

### Task 2.3: Write Technical narrative Tier B (2-minute taxi-ride)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md`

- [ ] **Step 1: Draft Tier B — ~200 words, structured as 5-beat arc**

Append under `## Tier B — 2-minute`:

Structure (enforced):
1. **Problem** (~40 words) — what happens today when a cross-border payment fails.
2. **What everyone tries** (~40 words) — the existing partial solutions (manual bridge loans, treasury interventions) and why they're slow.
3. **Our insight** (~40 words) — the core observation that makes LIP possible.
4. **The mechanism** (~60 words) — name at least 2 anchors from Task 2.1; describe the pipeline at one-level-of-abstraction above code (C1 classifies, C2 prices, C7 executes).
5. **Outcome** (~20 words) — measured result; must include a canonical number from appendix-numbers.md.

- [ ] **Step 2: End with a one-sentence handoff to Patent volume**

- [ ] **Step 3: Acceptance criteria**

Verify:
- Five beats present and in order
- 180-220 word count (use a word counter)
- Read aloud — timed between 1m45s and 2m15s
- Minimum 2 anchors from Task 2.1 appear verbatim
- At least one number from appendix-numbers.md cited, in words-then-digits form on first use

- [ ] **Step 4: Do not commit yet**

---

### Task 2.4: Write Technical narrative Tier C (5-minute whiteboard)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md`

- [ ] **Step 1: Draft Tier C — ~500 words, 7-beat arc**

Append under `## Tier C — 5-minute`:

Structure (enforced):
1. **Problem** (~70 words) — expanded from Tier B; one concrete failure scenario (e.g. Deutsche Bank → Siemens pacs.002 rejection).
2. **What everyone tries** (~60 words) — JPMorgan incumbents, manual treasury, Wise/Stripe rails — and the specific gap each has.
3. **Why it fails** (~70 words) — the structural reason bridge lending didn't scale historically.
4. **Our insight** (~60 words) — two-step classification as the key unlock.
5. **The mechanism** (~120 words) — name C1/C2/C7 with one-sentence purpose each; walk the pipeline; cite the 94ms SLO; cite the 300 bps fee floor.
6. **Outcome** (~60 words) — what a successful loan offer looks like, with named numbers.
7. **What this unlocks** (~60 words) — the adjacency to Patent + Market (handoff).

- [ ] **Step 2: Acceptance criteria**

Verify:
- Seven beats present and in order
- 450-550 word count
- Read aloud — timed between 4m30s and 5m30s
- All chosen anchors from Task 2.1 appear at least once
- At least three numbers from appendix-numbers.md cited

- [ ] **Step 3: Do not commit yet**

---

### Task 2.5: Write Technical narrative Tier D (deep-dive)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md`

- [ ] **Step 1: Draft Tier D — ~1,500 words, full diligence answer**

Append under `## Tier D — Deep-dive`:

Structure (enforced):
1. **Problem, in detail** (~200 words) — scenario + failure statistics from SWIFT GPI
2. **Existing approaches and their gaps** (~200 words) — JPMorgan US7089207B1 (what it covers, what it misses), manual treasury, competitor solutions
3. **Our insight and why now** (~150 words) — link to ISO 20022 migration
4. **Architecture overview** (~300 words) — all 8 components C1-C8, purpose of each, data flow, which are ML and which are deterministic
5. **Key design decisions** (~300 words) — each with *why*: 94ms SLO, 300 bps floor, polyglot stack (Python/Rust/Go), synthetic-first build, Ford Principle governance
6. **Validation status** (~150 words) — 1,284 tests, 92% coverage, pre-production, synthetic corpus calibrated from SWIFT GPI — acknowledge META-02 honestly
7. **What ships next** (~100 words) — roadmap; RBC pilot as the gate

- [ ] **Step 2: Acceptance criteria**

Verify:
- Seven sections present
- 1,400-1,600 word count
- Every anchor from Task 2.1 appears multiple times
- META-02 honestly acknowledged in the Validation section
- No jargon without plain-English gloss
- Every number cited is in appendix-numbers.md

- [ ] **Step 3: Voice rulebook pass — full file**

Re-read the entire narrative.md (all four tiers). Apply voice rulebook line by line. Fix any:
- Weasel words
- Long sentences (split them)
- Approximated numbers ("roughly 100ms" → "ninety-four milliseconds")
- Passive voice
- Jargon without gloss

- [ ] **Step 4: Commit narrative.md**

```markdown
## 2026-04-17
- [narrative] Technical narrative.md written: 4 tiers (30s/2min/5min/deep-dive) with [N] anchors. Voice rulebook pass complete.
```

```bash
git add docs/business/fundraising/founder-fluency/01-technical-depth/narrative.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Technical narrative (4 tiers)"
```

---

### Task 2.6: Draft Technical drill.md — Warm and Probing tiers

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/drill.md`

- [ ] **Step 1: Replace stub with header block**

```markdown
# Technical Depth — Drill

Question bank organised by investor persona × difficulty. Cover the Gold-standard block when self-drilling.

**Canonical anchors** (every answer must touch at least one):
[Copy from narrative.md header]

**Question IDs:** `Q-TECH-NN` — append-only. Never renumber.

---
```

- [ ] **Step 2: Write 8 questions — 2 Warm per persona (4 personas × 2 = 8)**

For each persona (Generalist VC, Fintech Specialist, Bank-strategic, Adversarial), write 2 Warm-tier questions using the template:

```markdown
### Q-TECH-01 · Generalist VC · Warm
**Question:** "[plausible friendly-opener question in the persona's voice]"

**Gold-standard answer** (30-second spoken):
[Acknowledge → Anchor → Close. Write in speaking voice, not reading voice. 2-3 sentences max.]

**Anchors this answer must touch:**
- [Anchor A]
- [Anchor B] (optional)

**Don't-say-this traps:**
- ❌ [Specific phrase that weakens the answer]
- ❌ [Another specific trap]

**Bear-case pointer:** None (Warm tier usually doesn't enter bear territory)
```

Suggested Warm themes per persona:
- **Generalist VC:** *"Give me the one-minute overview"* / *"Why did you build this?"*
- **Fintech Specialist:** *"What's the wedge — why pacs.002 specifically?"* / *"How is this different from SWIFT GPI's own tooling?"*
- **Bank-strategic:** *"Walk me through what sits inside a bank when LIP runs"* / *"Is this on-prem, cloud, or hybrid?"*
- **Adversarial:** *"In one sentence, what have you actually built?"* / *"Is this real or is it a deck?"*

- [ ] **Step 3: Write 8 questions — 2 Probing per persona**

Probing tier tests whether the founder actually understands, not just recites. Suggested themes:
- **Generalist:** *"Why 94ms specifically?"* / *"Why a fee floor — why not market-priced?"*
- **Fintech:** *"Walk me through C1's architecture — GraphSAGE + TabTransformer + LightGBM, why all three?"* / *"What's your latency breakdown per component?"*
- **Bank-strategic:** *"My AML team would block this on day one. Convince me they won't."* / *"What happens when Kafka backs up under bank-throughput load?"*
- **Adversarial:** *"You have no production traffic. What do you actually know about your model's behaviour?"* / *"Why should I believe 94ms holds at scale?"*

- [ ] **Step 4: Acceptance criteria**

Verify:
- 16 questions total (8 Warm + 8 Probing, 2 per persona per tier)
- Every question has all 4 mandatory blocks (Question, Gold answer, Anchors, Don't-say)
- Every Gold answer uses Acknowledge → Anchor → Close structure
- Every Gold answer is under 80 words (30-second-speakable)
- Every Anchor block references at least one anchor from the narrative

- [ ] **Step 5: Do not commit yet — Task 2.7 continues**

---

### Task 2.7: Draft Technical drill.md — Adversarial and Crushing tiers

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/drill.md`

- [ ] **Step 1: Write 4 Adversarial-tier questions (1 per persona)**

These are designed to rattle. Suggested themes:
- **Generalist:** *"Non-technical founder, RBC employee, no production — convince me this isn't a pipe dream"* (routes to META-03 bear pointer)
- **Fintech:** *"Your fee floor is 300 bps. That's 3x Wise's FX margin. Why would any bank pay that?"*
- **Bank-strategic:** *"I've seen a hundred fintechs pitch liquidity to banks. Every one died in procurement. What's different?"*
- **Adversarial:** *"JPMorgan has the patent. You're a synthetic-data startup. What stops them from shipping this in 90 days?"*

- [ ] **Step 2: Write 4 Crushing-tier questions (1 per persona)**

These are the questions the founder dreads. Answers MUST include bear-case pointers. Suggested themes:
- **Generalist:** *"Walk me through what happens if RBC claims ownership of the IP under your employment clause"* (→ META-01)
- **Fintech:** *"Prove 94ms. Real traffic, real bank, real numbers — or admit you don't know"* (→ META-02)
- **Bank-strategic:** *"You will not get a pilot at a Tier 1 bank. Change my mind"* (→ B-MKT-02, B-MKT-06)
- **Adversarial:** *"You're not technical. If your senior engineer leaves tomorrow, what happens?"* (→ META-03)

- [ ] **Step 3: Acceptance criteria**

Verify:
- 8 new questions (4 Adversarial + 4 Crushing)
- Total drill.md now has 24 questions (exceeds 20 minimum)
- Every Crushing question has a bear-case pointer
- Every Gold answer for Crushing tier shows how to land the bear case without flinching
- Every Don't-say-this trap is specific (not "avoid being defensive" — an actual phrase)

- [ ] **Step 4: Commit drill.md**

```markdown
## 2026-04-17
- [drill] Technical drill.md populated with 24 questions (8 Warm + 8 Probing + 4 Adversarial + 4 Crushing). Exceeds 20-question launch floor.
```

```bash
git add docs/business/fundraising/founder-fluency/01-technical-depth/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Technical drill.md with 24 questions"
```

---

### Task 2.8: Write Technical bear-case.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/bear-case.md`

- [ ] **Step 1: Write the header with Master Index**

```markdown
# Technical Depth — Bear Case

**How to read this file:** Each entry below names a real weakness, writes an honest structured answer, and flags the don't-say traps. Master Index ranks entries by `(likelihood of being asked) × (severity if fumbled)`. Spend 50% of drill time on ranks 1-3.

## Master Index

| Rank | ID | Weakness | Resolution event |
|---|---|---|---|
| 1 | META-03 | Non-technical founder | (ongoing — no single event; fluency is proven continuously) |
| 2 | META-02 | No production traffic yet | First live UETR in RBC pilot |
| 3 | B-TECH-01 | Model performance on real data unknown | First real-traffic validation run |
| 4 | B-TECH-02 | 94ms SLO untested at bank throughput | Load test against bank-realistic traffic |
| 5 | B-TECH-03 | Polyglot stack = hiring/scaling risk | First external hire; engineering lead in place |
| 6 | B-TECH-04 | C4 Dispute Classifier single-vendor ML risk (Groq/Qwen3) | Second LLM backend validated |
| 7 | B-TECH-05 | Early infra fragility signals (PyTorch+LightGBM macOS deadlock) | CI-level regression gates in place |

---
```

- [ ] **Step 2: Write META-03 master entry**

```markdown
## META-03 — Non-technical founder who earned fluency
**(Master entry — referenced from all volumes; governs the founder-fit question)**

**Honest Truth:**
The founder's background is strategic, not engineering. They cannot personally write a line of production code in any LIP component.

**Structured Answer** (speak this, don't flinch):
1. Acknowledge cleanly — "Correct. My background is strategic, not engineering."
2. Show the work — "I've spent [N months] learning this architecture deeply enough to defend every decision personally. C1's GraphSAGE + TabTransformer + LightGBM choice, the 94-millisecond SLO, the 300-basis-point fee floor, the Rust velocity engine, the polyglot stack — I can walk you through the *why* of each, without an engineer in the room."
3. Evidence of governance — "Our Ford Principle codifies it: the team's job is to translate direction into correct technical decisions and push back when I'm wrong. Architecture reviews run through named internal agents — QUANT on financial math, CIPHER on security, REX on compliance. I steer; they push back; nothing merges that breaks a guardrail."
4. Close on the trade — "The fluency you're testing for is earned, not delegated."

**Don't-say-this:**
- ❌ "I rely on my team for the technical side." (hand-off language; sounds like you've given up)
- ❌ "I'm learning as we go." (undercuts the earned-fluency claim)
- ❌ Any apology. Acknowledge ≠ apologise.
- ❌ "Basically", "kind of", "sort of" — the whole voice rulebook applies under pressure here.

**Resolution Milestone:**
This weakness never fully resolves — it attenuates through demonstrated fluency over time. Proxy milestones: a pilot engineer review, an engineering hire co-signing architecture decisions, a published model card reviewed without a correction.

**Investor Intuition target:**
*"They're not a technical founder, but they've done the homework — they can hold the room without an engineer present."*

**Drill linkage:**
Q-TECH-17 (Adversarial-Generalist), Q-TECH-24 (Crushing-Adversarial).

---
```

- [ ] **Step 3: Write META-02 master entry**

```markdown
## META-02 — No production traffic yet
**(Master entry — referenced from Technical and Market volumes)**

**Honest Truth:**
Pre-production. All validation is on synthetic data + in-memory mocks. No bank has run LIP on real pacs.002 traffic. Model behaviour under real-world distributions is unknown.

**Structured Answer:**
1. Acknowledge cleanly — "That's correct. We're pre-production."
2. Reframe as design choice — "We chose synthetic-first so the full eight-component stack is right before we spend pilot goodwill. The synthetic corpus is calibrated from published SWIFT GPI failure-rate distributions — calibration doc available in diligence."
3. State the milestone — "RBC pilot is the gate. First live UETR by [quarter]."
4. Optional confidence signal — "1,284 tests passing, 92% coverage, every QUANT-locked constant traceable to code. Engineering discipline is visible; the gap is traffic, not rigour."

**Don't-say-this:**
- ❌ "We're basically ready, just need a pilot." (dismisses the gap)
- ❌ "No one has production data at this stage." (defensive + false for fintechs further along)
- ❌ "The synthetic data is as good as real." (DGEN would refuse this claim; never speak it)

**Resolution Milestone:**
First live UETR written by LIP in an RBC pilot.

**Investor Intuition target:**
*"They know where they are, they're not bluffing, they have a clear next step."*

**Drill linkage:**
Q-TECH-18 (Adversarial-Adversarial), Q-TECH-22 (Crushing-Fintech).

---
```

- [ ] **Step 4: Write entries B-TECH-01 through B-TECH-05**

Use the same six-field template (Honest Truth, Structured Answer, Don't-say-this, Resolution Milestone, Investor Intuition, Drill linkage). Content guidance:

- **B-TECH-01 — Model performance on real data unknown:** Closely related to META-02 but specifically about ML model quality. Acknowledge synthetic-to-real distribution shift risk. Milestone: first real-traffic validation with calibration drift measurement.
- **B-TECH-02 — 94ms SLO untested at bank throughput:** Load testing has been done at mocked throughput only. Milestone: load test against bank-realistic pacs.002 QPS.
- **B-TECH-03 — Polyglot stack = hiring/scaling risk:** Python + Rust (PyO3) + Go is harder to hire for than pure-Python. Reframe: deliberate choice for latency-critical paths; core team small and senior today; first external hire will be polyglot-comfortable or we accept the search cost.
- **B-TECH-04 — C4 Dispute Classifier depends on Groq/Qwen3:** Single-vendor ML risk. Reframe: C4 is not critical path for loan pricing (C2); C4 output is advisory with fallback; second LLM backend on roadmap.
- **B-TECH-05 — Early infra fragility signals (PyTorch+LightGBM macOS deadlock):** Honest truth is a local-dev issue, not production. Reframe: caught, documented in CLAUDE.md, workaround is deterministic (session-scoped autouse fixture). Evidence of rigour, not weakness.

- [ ] **Step 5: Acceptance criteria**

Verify:
- Master Index is complete and ranked
- META-02 and META-03 master entries present with all 6 fields
- B-TECH-01 through B-TECH-05 present with all 6 fields
- Every entry's Drill linkage points to real `Q-TECH-NN` IDs in drill.md (cross-check)
- No entry contains weasel words or apologies

- [ ] **Step 6: Commit bear-case.md**

```markdown
## 2026-04-17
- [bear-case] Technical bear-case.md populated: Master Index + META-02 + META-03 + B-TECH-01 through B-TECH-05. Drill linkage cross-checked.
```

```bash
git add docs/business/fundraising/founder-fluency/01-technical-depth/bear-case.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Technical bear-case.md with META-02, META-03, and 5 entries"
```

---

### Task 2.9: Push Phase 2

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- `01-technical-depth/` folder has all three files populated (no stubs remain)
- Branch is up to date on remote
- CHANGELOG reflects Phase 2 completion

---

## Phase 3 — Patent/IP volume

Goal: Complete `02-patent-ip/` — narrative (4 tiers), drill (20+ questions), bear-case including META-01 (RBC IP clause) master entry.

### Task 3.1: Choose Patent volume anchors

**Files:**
- Read: `docs/legal/patent/`
- Read: `docs/business/fundraising/ip-risk-pre-counsel-analysis-revised.md`
- Working output: 3-5 anchor phrases

- [ ] **Step 1: Read patent specs and prior-art analysis**

Extract candidate anchors. Likely candidates:
- *"Two-step classification + conditional offer mechanism"* (the core claim)
- *"Tier 2/3 private counterparties"* (the gap vs JPMorgan)
- *"Damodaran industry-beta"* and *"Altman Z' thin-file"* (the thin-file model)
- *"EPG-21 language scrub"* (no AML/SAR/OFAC terms in published claims)
- *"Non-provisional filing"* (the near-term milestone)

- [ ] **Step 2: Lock 3-5 anchors; update narrative.md header**

Same format as Task 2.1. Do not commit yet.

- [ ] **Step 3: Acceptance criteria**

Verify:
- Anchors are novel-claim-specific (not generic patent language)
- No anchor violates EPG-21 language scrub (no "AML", "SAR", "OFAC" — use "classification gate", "hold type discriminator")

---

### Task 3.2: Write Patent narrative (all 4 tiers)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/02-patent-ip/narrative.md`

- [ ] **Step 1: Write Tier A — 30 seconds, 3 sentences**

Structure:
- Sentence 1: What the patent claims (the core novel mechanism).
- Sentence 2: What prior art it improves on (JPMorgan US7089207B1 — name it).
- Sentence 3: Why examiners will grant it (the specific gap being closed).

- [ ] **Step 2: Write Tier B — 2 minutes, ~200 words**

5-beat arc adapted for IP:
1. The patent landscape today
2. What JPMorgan covers (US7089207B1) and what it misses
3. The LIP insight that fills the gap
4. The two-step classification + conditional offer claim structure
5. Filing status and near-term milestone

End with handoff to Market volume.

- [ ] **Step 3: Write Tier C — 5 minutes, ~500 words**

7-beat arc:
1. Why this patent matters (moat economics)
2. Prior art survey (JPMorgan, plus any others from `docs/legal/patent/`)
3. The specific novelty (two-step classification on ISO 20022 pacs.002)
4. The extension to Tier 2/3 via Damodaran/Altman
5. Language scrub and why (EPG-21 — no enumeration of block codes in claims)
6. Filing status (provisional done; non-provisional planned)
7. What could go wrong (examiner narrowing, §101 software patent risk) — handoff to bear case

- [ ] **Step 4: Write Tier D — deep-dive, ~1,500 words**

7 sections:
1. Problem the patent solves (in patent-office language, plain gloss)
2. Prior art analysis — JPMorgan US7089207B1 in detail; any others
3. The novel claim structure — two-step classification + conditional offer + Tier 2/3 extension
4. Claim language strategy — EPG-21 scrub rationale
5. Enforcement posture — what infringement looks like; what defensibility looks like
6. Risks — Alice/§101, examiner narrowing, RBC IP clause (META-01 reference)
7. Filing roadmap — provisional → non-provisional → PCT; timeline

- [ ] **Step 5: Voice rulebook pass across all four tiers**

- [ ] **Step 6: Commit narrative.md**

```markdown
## 2026-04-17
- [narrative] Patent narrative.md written: 4 tiers with IP-specific anchors. EPG-21 language scrub enforced throughout.
```

```bash
git add docs/business/fundraising/founder-fluency/02-patent-ip/narrative.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Patent narrative (4 tiers)"
```

---

### Task 3.3: Write Patent drill.md (20+ questions)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/02-patent-ip/drill.md`

- [ ] **Step 1: Header block with canonical anchors**

Same format as Task 2.6 Step 1, but Patent-specific.

- [ ] **Step 2: Write Warm and Probing tiers — 16 questions (2 per persona per tier)**

Suggested themes:
- **Generalist Warm:** *"Explain the patent to me in one minute"* / *"What does it stop other people from doing?"*
- **Generalist Probing:** *"How is this different from JPMorgan's patent?"* / *"What if the examiner narrows the claims?"*
- **Fintech Warm:** *"Is this a software patent — doesn't Alice make those hard?"* / *"What's the filing timeline?"*
- **Fintech Probing:** *"Walk me through the two-step classification claim specifically"* / *"What prevents an incumbent from designing around it?"*
- **Bank-strategic Warm:** *"Who else in the bank-lending space has patents here?"* / *"Does a licensee need the patent to be granted?"*
- **Bank-strategic Probing:** *"If a bank builds this in-house, are they infringing?"* / *"How does the patent interact with our licensing model?"*
- **Adversarial Warm:** *"Show me the provisional filing"* / *"How many claims did you draft?"*
- **Adversarial Probing:** *"Alice §101 — why does this survive?"* / *"Design-around in 6 months — impossible or trivial?"*

- [ ] **Step 3: Write Adversarial and Crushing tiers — 8 questions**

Adversarial themes (1 per persona):
- **Generalist:** *"Software patents are weak. You know this. Why should I value this one?"*
- **Fintech:** *"JPMorgan's patent predates yours and covers the category. You're a continuation, not a novel claim. Convince me otherwise."*
- **Bank-strategic:** *"My general counsel will say your patent is too narrow to matter. What's your response?"*
- **Adversarial:** *"Name a single patent in this space that's ever generated material value for a startup."*

Crushing themes (1 per persona, all with bear-case pointers):
- **Generalist:** *"Your employer RBC has an IP clause. What happens when they claim ownership?"* (→ META-01)
- **Fintech:** *"The examiner narrows to block-code-list infringement only. Your patent becomes worthless. What's the fallback?"* (→ B-PAT-04)
- **Bank-strategic:** *"You filed a provisional. Non-provisional deadline is [date]. Missing it means public disclosure wipes your rights. What's your plan?"* (→ B-PAT-03)
- **Adversarial:** *"Alice §101 rejection rate for fintech software patents is about 70%. Statistical base-rate says you lose. Argue."* (→ B-PAT-05)

- [ ] **Step 4: Acceptance criteria**

Verify:
- 24 questions total
- EPG-21 language scrub applied — no "AML", "SAR", "OFAC" anywhere
- Every Crushing question has a bear-case pointer
- META-01 appears in at least 2 drill answers (Crushing-Generalist + at least one Probing)

- [ ] **Step 5: Commit drill.md**

```bash
git add docs/business/fundraising/founder-fluency/02-patent-ip/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Patent drill.md with 24 questions"
```

---

### Task 3.4: Write Patent bear-case.md with META-01 master entry

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/02-patent-ip/bear-case.md`

- [ ] **Step 1: Header with Master Index**

```markdown
# Patent / IP — Bear Case

## Master Index

| Rank | ID | Weakness | Resolution event |
|---|---|---|---|
| 1 | META-01 | RBC IP clause could claim ownership | Employment counsel resolution + documented timeline of invention |
| 2 | B-PAT-01 | JPMorgan US7089207B1 prior art overlap | Non-provisional filing grants novel claims |
| 3 | B-PAT-02 | Provisional not yet non-provisional | Non-provisional filed |
| 4 | B-PAT-03 | Provisional deadline approaching | Same as above |
| 5 | B-PAT-04 | Examiner may narrow on two-step classification | Granted claim language |
| 6 | B-PAT-05 | Alice §101 software-patent risk | Claims drafted with concrete technical effect |
| 7 | B-PAT-06 | Competitive patents in pipeline we can't see | FTO (freedom-to-operate) opinion from counsel |

---
```

- [ ] **Step 2: Write META-01 master entry (extra care)**

This is the single highest-priority bear case in the entire Playbook. Drafting needs to be honest, non-defensive, and operationally concrete. Reference the existing analysis in `project_rbc_ip_clause_analysis.md` (founder's memory, summarised here).

```markdown
## META-01 — RBC IP clause
**(Master entry — highest priority across all volumes; referenced from Technical, Patent, and Market)**

**Honest Truth:**
The founder is a current RBC employee (Credit Management Resolution Officer, started 2026-01-12). RBC's offer letter contains a broad IP assignment clause covering anything conceived during employment — potentially including LIP. This is a real risk to the patent's ownership and to the founder's ability to commercialise independently.

**Structured Answer** (rehearsed verbatim until muscle memory):
1. Acknowledge the risk plainly — "I'm a current RBC employee. Their offer letter has an IP clause. This has to be addressed before non-provisional filing; I know it, counsel knows it."
2. State the documented timeline — "The invention was conceived before my RBC start date of January 12, 2026 — documented in [provisional filing date / repo commit history / independent development record]. Ownership attaches at conception, not at employment start, under [jurisdiction] IP law."
3. State the resolution path — "I have an employment counsel engaged on a structured resignation and IP assignment carve-out. The operating plan (Angle 6 from our internal analysis) is: resign, file non-provisional as independent inventor, approach RBC later as an external vendor. Independent counsel memo on file; available in diligence under NDA."
4. State the investor-protection mechanism — "Our SAFE and cap table are gated on resolution of this clause. No investor takes ownership risk without a clean chain of title."

**Don't-say-this:**
- ❌ "It's fine, the clause doesn't apply." (It's not fine and it does apply — this is the founder's weakest bluff and an experienced investor sees through it.)
- ❌ "RBC doesn't know about LIP." (Operational recklessness if true; dishonest if false.)
- ❌ "I'll resign when we close a round." (Timeline inversion — resignation must precede filing, not follow funding.)
- ❌ Any language that minimises the seriousness ("just a standard clause", "boilerplate") — investors mark this.

**Resolution Milestone:**
Three events, sequential:
1. Employment counsel memo on file documenting conception-date evidence and RBC clause analysis.
2. Founder resigns from RBC.
3. Non-provisional patent filed with founder as sole independent inventor; clean chain of title.

**Investor Intuition target:**
*"They have the hardest conversation planned. They're not pretending it isn't there. The resolution path is concrete and sequenced."*

**Drill linkage:**
Q-PAT-21 (Crushing-Generalist — RBC IP question directly), Q-TECH-17 (Adversarial-Generalist — cross-referenced from Technical), Q-MKT-NN (Market linkage TBD in Phase 4).

**Cross-volume references:**
- Referenced in: `01-technical-depth/bear-case.md` (pointer), `03-market-timing/bear-case.md` (pointer, pilot-path implications).
- Master entry location: this file.

---
```

- [ ] **Step 3: Write entries B-PAT-01 through B-PAT-06**

Same six-field template. Content guidance:

- **B-PAT-01 — JPMorgan US7089207B1 prior art overlap:** The patent is closest prior art. Novelty turns on Tier 2/3 extension. Reframe: novelty is specific, not sweeping.
- **B-PAT-02 — Provisional not yet non-provisional:** Provisional protects a 12-month window. Milestone: non-provisional on file before window expires.
- **B-PAT-03 — Provisional deadline approaching:** Timing risk. Counsel engagement timeline must complete before window closes. This is operational, not philosophical.
- **B-PAT-04 — Examiner may narrow on two-step classification:** Claims can be narrowed to specific implementations. Fallback: even narrowed claims preserve pilot-licensing posture.
- **B-PAT-05 — Alice §101 software-patent risk:** Real. Counter: LIP claims concrete technical effect (94ms SLO, measured improvement over manual processes). §101 survival turns on technical effect language.
- **B-PAT-06 — Competitive patents we can't see:** FTO opinion needed before pilot. Acknowledge openly.

- [ ] **Step 4: Acceptance criteria**

Verify:
- META-01 is the longest, most carefully written entry in the entire Playbook
- META-01 Drill linkage cross-references the Technical drill (Q-TECH-17) — confirm Q-TECH-17 actually exists
- Every B-PAT-NN entry has all six fields
- No Don't-say-this line is generic — all are specific phrases

- [ ] **Step 5: Commit bear-case.md**

```markdown
## 2026-04-17
- [bear-case] Patent bear-case.md populated: META-01 master entry (extra care for RBC IP clause) + B-PAT-01 through B-PAT-06.
```

```bash
git add docs/business/fundraising/founder-fluency/02-patent-ip/bear-case.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Patent bear-case with META-01 (RBC IP clause)"
```

---

### Task 3.5: Cross-reference META-01 from Technical and Market volumes

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/bear-case.md` (add pointer)
- Modify: `docs/business/fundraising/founder-fluency/03-market-timing/bear-case.md` (add pointer — will be empty until Phase 4 but scaffold the reference now)

- [ ] **Step 1: Add META-01 cross-reference block to Technical bear-case**

At the top of the Master Index section in `01-technical-depth/bear-case.md`, insert:

```markdown
## Cross-volume META references

See also: **META-01 (RBC IP clause)** — master entry in `02-patent-ip/bear-case.md`. Referenced here because the founder-employment angle intersects with the non-technical founder question (META-03).
```

- [ ] **Step 2: Same for Market bear-case**

(File is still a stub at this point; just add the cross-reference block for now; Phase 4 will fill the rest.)

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/01-technical-depth/bear-case.md docs/business/fundraising/founder-fluency/03-market-timing/bear-case.md
git commit -m "docs(founder-fluency): cross-reference META-01 from Technical and Market bear-cases"
```

---

### Task 3.6: Push Phase 3

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

---

## Phase 4 — Market/Timing volume

Goal: Complete `03-market-timing/` — narrative (4 tiers), drill (20+ questions), bear-case (5-7 entries + META-01 cross-link + META-02 cross-link).

### Task 4.1: Choose Market volume anchors

**Files:**
- Read: `docs/business/Market-Fundamentals-Fact-Sheet.md`
- Read: `docs/business/Competitive-Landscape-Analysis.md`
- Read: `docs/business/GTM-Strategy-v1.0.md`
- Working output: 3-5 anchor phrases

- [ ] **Step 1: Extract candidates**

Likely candidates:
- *"ISO 20022 migration window"* (November 2025 deadline / extensions)
- *"Correspondent banking stack"* (the specific segment LIP serves)
- *"Tier 2/3 private counterparties"* (the underserved segment, echoes Patent)
- *"Bridge-lending as a feature, not a bank"* (positioning)
- *"BPI is a technology platform, not a lender"* (licensing model)

- [ ] **Step 2: Lock 3-5 anchors; update narrative.md header**

---

### Task 4.2: Write Market narrative (all 4 tiers)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/03-market-timing/narrative.md`

- [ ] **Step 1: Tier A — 30 seconds**

3 sentences:
1. The market LIP serves (correspondent banking, pacs.002 failures).
2. Why now (ISO 20022 migration window).
3. Why LIP (licensing model, not balance-sheet lending).

- [ ] **Step 2: Tier B — 2 minutes, ~200 words**

5-beat arc:
1. Market problem (dollar volume of failed cross-border payments annually)
2. Incumbent responses (manual treasury, JPMorgan internal, Wise/Stripe on different rails)
3. The LIP insight (why a licensing platform unlocks a new segment)
4. Sizing — cite canonical numbers from appendix-numbers.md
5. Timing — ISO 20022 window + AMLD6 force-function

Handoff to Technical or Patent depending on what was spoken last.

- [ ] **Step 3: Tier C — 5 minutes, ~500 words**

7-beat arc:
1. Market size — global correspondent banking volume, pacs.002 failure rate
2. Segmentation — Tier 1 banks (internal solutions), Tier 2/3 (underserved; LIP's wedge)
3. Incumbent analysis — who serves what today, where the gap is
4. Regulatory drivers — ISO 20022 migration, AMLD6 compliance-hold infrastructure demand
5. LIP's entry strategy — licensing, not lending; bank-as-borrower structure (EPG-14)
6. Traction honesty — zero LOIs signed; RBC pilot path specified
7. Revenue trajectory — link to Revenue-Projection-Model.md figures

Handoff to Technical.

- [ ] **Step 4: Tier D — deep-dive, ~1,500 words**

7 sections:
1. Market sizing methodology — TAM/SAM/SOM derivation
2. Competitive landscape — JPMorgan, BNY, Wise, Stripe, correspondent-banking incumbents
3. Regulatory tailwinds — ISO 20022, AMLD6, DORA, EU AI Act
4. Regulatory headwinds — AMLD7 scenarios, compliance-hold enforcement risk
5. Entry sequence — RBCx → Transaction Banking → AI Group (Bruce Ross)
6. Revenue model — licensing tiers, fee-share economics
7. Risk scenarios — patent loss, pilot timeline slippage, regulatory reclassification (handoffs to bear case)

- [ ] **Step 5: Voice rulebook pass**

- [ ] **Step 6: Commit**

```markdown
## 2026-04-17
- [narrative] Market narrative.md written: 4 tiers with market/timing-specific anchors.
```

```bash
git add docs/business/fundraising/founder-fluency/03-market-timing/narrative.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Market narrative (4 tiers)"
```

---

### Task 4.3: Write Market drill.md (20+ questions)

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/03-market-timing/drill.md`

- [ ] **Step 1: Header + 24 questions across 4 personas × 4 tiers**

Use the same structure as Tasks 2.6/2.7/3.3. Suggested themes:
- **Generalist:** TAM/SAM/SOM basics, why-now, incumbent question
- **Fintech:** unit economics, corridor-level fee math, competitive response scenarios
- **Bank-strategic:** procurement cycle realism, pilot path, AML officer adoption friction
- **Adversarial:** TAM inflation, timing-slippage risk, incumbent 90-day copycat scenarios

Crushing-tier questions must include bear-case pointers (META-02 for traction, B-MKT-NN entries for specific market risks).

- [ ] **Step 2: Acceptance criteria**

Verify:
- 24 questions across 4 tiers
- Every number in gold answers traces to appendix-numbers.md
- No TAM figure is approximated — all cited canonically

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/03-market-timing/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Market drill.md with 24 questions"
```

---

### Task 4.4: Write Market bear-case.md

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/03-market-timing/bear-case.md`

- [ ] **Step 1: Master Index**

```markdown
# Market / Timing — Bear Case

## Cross-volume META references

- **META-01 (RBC IP clause)** — master in `02-patent-ip/bear-case.md`. Relevant here because the founder-employment angle touches pilot-path strategy (if RBC becomes the counterparty, conflict-of-interest emerges).
- **META-02 (No production traffic)** — master in `01-technical-depth/bear-case.md`. Relevant here because zero LOIs signed is the market-side expression of the same underlying gap.

## Master Index

| Rank | ID | Weakness | Resolution event |
|---|---|---|---|
| 1 | B-MKT-01 | No bank LOI signed yet | First LOI |
| 2 | B-MKT-02 | Bank procurement cycles 18-24 months | Pilot contract signed |
| 3 | B-MKT-03 | ISO 20022 migration deadline has slipped before | Deadline holds OR replacement regulatory driver identified |
| 4 | B-MKT-04 | AMLD7 could re-score unit economics | AMLD7 text finalised |
| 5 | B-MKT-05 | Incumbents (JPM, BNY) have internal liquidity solutions | Differentiation validated in pilot |
| 6 | B-MKT-06 | Correspondent banking volume declining in some corridors | Corridor-level volume analysis published |
| 7 | B-MKT-07 | Revenue lag 2-3 years from pilot to material ARR | Ramp curve published with pilot evidence |

---
```

- [ ] **Step 2: Write entries B-MKT-01 through B-MKT-07**

Six-field template. Content guidance:

- **B-MKT-01:** Zero LOIs. Reframe: RBC pilot path is specified with named channels (RBCx, Transaction Banking, AI Group). Milestone: first LOI.
- **B-MKT-02:** Procurement reality. Reframe: RBCx is an innovation-arm accelerator designed to shortcut this. Evidence from RBCx-like programs at other banks.
- **B-MKT-03:** ISO 20022 slippage history. Reframe: even if the deadline slips, the regulatory direction-of-travel is unchanged; AMLD6 compliance-hold infrastructure demand is a second force function.
- **B-MKT-04:** AMLD7 text not finalised. Reframe: monitoring; not building to a speculative regime.
- **B-MKT-05:** Incumbent internal solutions. Reframe: those solutions serve Tier 1 counterparties only; LIP's wedge is Tier 2/3 via Damodaran/Altman thin-file models (links to Patent narrative).
- **B-MKT-06:** Corridor decline. Reframe: TAM is not flat growth — it's redistribution; LIP is a function of failed-payment volume, not gross volume.
- **B-MKT-07:** Revenue lag. Reframe: realistic; capital plan matches; no revenue promise inside 24 months.

- [ ] **Step 3: Acceptance criteria**

Verify:
- Cross-volume META references at the top
- All 7 B-MKT entries present with six fields
- Every Resolution Milestone is named and concrete

- [ ] **Step 4: Commit**

```bash
git add docs/business/fundraising/founder-fluency/03-market-timing/bear-case.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write Market bear-case with 7 entries + META cross-refs"
```

---

### Task 4.5: Push Phase 4

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- All three volumes fully populated (no stubs remaining in 01-, 02-, 03- directories)
- CHANGELOG reflects Phase 4 completion

---

## Phase 5 — Master Narrative (braided)

Goal: Write `00-master-narrative.md` — the top-level braided pitch that weaves Technical + Patent + Market into one coherent spoken story.

### Task 5.1: Design the braid structure

**Files:**
- Read: all three `narrative.md` files just written
- Working output: braid outline

- [ ] **Step 1: Identify the 3-5 braid anchors**

These are the anchors that MUST appear in the master narrative and that carry the cross-topic story. Typically:
- Technical anchor (e.g. "two-step classification" or "94 milliseconds")
- Patent anchor (e.g. "novel claim on Tier 2/3 extension")
- Market anchor (e.g. "ISO 20022 migration window")
- One braid phrase that links them (e.g. "the same mechanism that defines our patent defines our speed defines our market window")

- [ ] **Step 2: Outline the braid arc**

The master narrative has four tiers, same depth structure as volumes, but each tier is **woven**:
- Tier A (30s): one sentence Technical, one sentence Patent, one sentence Market — tight braid.
- Tier B (2min): 5-beat arc where each beat touches at least 2 of the 3 topics.
- Tier C (5min): 7-beat arc where topics are introduced, woven, and closed.
- Tier D (deep-dive): ~2,000 words; the full braided case.

---

### Task 5.2: Write the master narrative

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/00-master-narrative.md`

- [ ] **Step 1: Replace stub with header + all 4 tiers**

Structure enforced the same way as volume narratives, but with the braid rule: **no tier is allowed to speak for more than 30 seconds about one topic without crossing into an adjacent topic.**

- [ ] **Step 2: Voice rulebook pass + braid check**

Additional check beyond voice rulebook: **read each tier and count how many sentences reference each topic.** Technical, Patent, Market should each appear in proportion — not 80% Technical. If proportions are skewed, rewrite.

- [ ] **Step 3: Acceptance criteria**

Verify:
- All 4 tiers present
- Each tier satisfies the braid rule
- Every anchor from all three volume narratives appears at least once
- Read aloud — timing hits 30s / 2min / 5min / deep-dive respectively

- [ ] **Step 4: Commit**

```markdown
## 2026-04-17
- [narrative] Master narrative 00-master-narrative.md written: braided pitch across all three volumes. Braid rule enforced.
```

```bash
git add docs/business/fundraising/founder-fluency/00-master-narrative.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): write master narrative (braided pitch)"
```

---

### Task 5.3: Push Phase 5

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

---

## Phase 6 — Scale-out drill banks to full load (50 questions per volume)

Goal: Grow each volume's drill.md from 24 questions (Phase 2/3/4 floor) to ~50 questions per volume. This is the "fully loaded" state the founder specified.

### Task 6.1: Scale Technical drill.md to 50 questions

**Files:**
- Modify: `docs/business/fundraising/founder-fluency/01-technical-depth/drill.md`

- [ ] **Step 1: Add 26 more questions (current 24 → target 50)**

Distribution:
- 8 more Warm (2 per persona) — themes: onboarding/licensing mechanics, integration surface, documentation, observability, SLA
- 8 more Probing (2 per persona) — themes: failure modes, model monitoring, feature engineering choices, governance (Ford Principle), EPG decisions
- 6 more Adversarial (1.5 per persona) — themes: scaling cliffs, engineering-team risk, dependency-graph fragility, SLO regression scenarios
- 4 more Crushing (1 per persona) — themes: cross-META scenarios that combine two or three weaknesses at once

- [ ] **Step 2: Acceptance criteria**

Verify:
- Technical drill.md now contains exactly 50 questions
- No question is a rephrasing of an existing one (dedup check: search for close paraphrases)
- New questions reference new angles — don't pile on the same themes

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/01-technical-depth/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): scale Technical drill.md to 50 questions (full load)"
```

---

### Task 6.2: Scale Patent drill.md to 50 questions

Same pattern as Task 6.1. Distribution identical. Themes for new Patent questions:
- Warm expansion: claim construction basics, filing mechanics, licensing-patent interaction
- Probing expansion: claim-chart walkthrough, continuation strategy, foreign filing (PCT)
- Adversarial expansion: design-around scenarios, patent trolling defence, invalidity art
- Crushing expansion: compound bear-case scenarios (RBC IP + §101 rejection simultaneously)

- [ ] **Step 1: Add 26 questions**

- [ ] **Step 2: Acceptance criteria** (same as 6.1)

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/02-patent-ip/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): scale Patent drill.md to 50 questions"
```

---

### Task 6.3: Scale Market drill.md to 50 questions

Same pattern. Themes:
- Warm expansion: sales cycle mechanics, deal-size segmentation, geographic TAM slicing
- Probing expansion: corridor-level unit economics, regulatory-regime-specific strategies
- Adversarial expansion: incumbent replication speed, ISO 20022 delay scenarios, AMLD7 re-score
- Crushing expansion: compound scenarios (patent loss + pilot timing slippage)

- [ ] **Step 1: Add 26 questions**

- [ ] **Step 2: Acceptance criteria**

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/03-market-timing/drill.md docs/business/fundraising/founder-fluency/CHANGELOG.md
git commit -m "docs(founder-fluency): scale Market drill.md to 50 questions"
```

---

### Task 6.4: Push Phase 6

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Acceptance criteria**

Verify:
- All three drill.md files have exactly 50 questions each (total 150)
- CHANGELOG reflects Phase 6 completion

---

## Phase 7 — First full-spectrum Gauntlet

Goal: Stress-test the Playbook by running a live Gauntlet session with the founder. Identify gaps where narrative anchors aren't catching drill questions, where bear-case entries don't survive pressure, where voice needs calibration.

### Task 7.1: Run the Gauntlet

**Files:**
- Append to: `docs/business/fundraising/founder-fluency/session-log.md`

- [ ] **Step 1: Founder invokes Gauntlet**

Founder says, in a Claude Code session: *"Gauntlet me across all three volumes."*

- [ ] **Step 2: Claude runs 5 questions**

Drawn from drill.md across all three volumes, escalating Warm → Crushing, rotating personas. Grade silently per the spec's 5-point rubric.

- [ ] **Step 3: Claude produces end-of-session block**

Paste-ready block appended to `session-log.md`:

```markdown
## Drill session — YYYY-MM-DD (Phase 7 Gauntlet)

- **Mode:** Full-spectrum Gauntlet, first run
- **Questions asked:** Q-XXX-NN, Q-XXX-NN, Q-XXX-NN, Q-XXX-NN, Q-XXX-NN
- **Score:** X/25
- **Strongest:** [observation]
- **Weakest:** [observation]
- **Trap hits:** [list]
- **Re-read recommendations:** [specific file/section references]
- **Gaps identified (fed into Phase 7.2):** [list]
```

- [ ] **Step 4: Acceptance criteria**

Verify:
- Session log entry exists
- Score is honest (Claude does not soften for encouragement)
- Gaps-identified list is concrete (not "needs more practice")

---

### Task 7.2: Close identified gaps

**Files:**
- Modify: any file that needs fixing based on Gauntlet findings (narratives, drills, or bear-cases)

- [ ] **Step 1: For each gap, produce a fix**

Each gap falls into one of three buckets:
- **Narrative gap:** anchor wasn't clear enough, or tier didn't set up the answer structurally. Fix the narrative.
- **Drill gap:** gold answer was misaligned with narrative anchors, or traps weren't specific enough. Fix the drill entry.
- **Bear-case gap:** structured answer didn't survive the pressure. Rewrite the entry.

Commit each fix separately (one commit per fixed entry) so the CHANGELOG clearly shows what shifted.

- [ ] **Step 2: Acceptance criteria**

Verify:
- Every gap identified in Task 7.1 has a corresponding commit
- CHANGELOG reflects each fix

- [ ] **Step 3: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

---

## Phase 8 — Voice calibration (founder-led)

Goal: Replace Claude's voice with the founder's. This is the non-optional milestone where the Playbook becomes genuinely the founder's own.

### Task 8.1: Read aloud, mark drift

**Files:**
- Read and annotate: all `narrative.md` files (3 volumes + master)

- [ ] **Step 1: Founder reads every narrative tier aloud**

For each file, for each tier, the founder reads aloud at full pace and marks:
- Sentences that don't feel like their voice (too Claude-like, too formal, too flat)
- Sentences that stumble or don't flow when spoken
- Jargon that the founder wouldn't naturally use
- Phrases that feel over-rehearsed

The marking mechanism: in-file comments using `<!-- VOICE: [reason] -->` inline. Each mark is a location for Claude to help rewrite in Task 8.2.

- [ ] **Step 2: Acceptance criteria**

Verify:
- Every narrative tier has been read aloud
- Comments are concrete (not "this whole paragraph is off")

---

### Task 8.2: Rewrite in founder voice

**Files:**
- Modify: marked passages in every narrative.md

- [ ] **Step 1: For each `<!-- VOICE: -->` mark, founder + Claude rewrite**

Process: founder says in their own words what they mean. Claude captures the phrasing. Claude proposes the rewrite in the founder's cadence. Founder approves or re-drafts.

The **structure stays fixed** (anchors, tier depth, 4-tier progression). Only the **prose** changes.

- [ ] **Step 2: Remove all `<!-- VOICE: -->` comments after rewrite**

- [ ] **Step 3: Re-read aloud**

Founder re-reads every tier aloud. If any sentence still feels off, mark and repeat.

- [ ] **Step 4: Acceptance criteria**

Verify:
- No `<!-- VOICE: -->` comments remain in any file
- Founder can read every narrative tier start-to-end at full pace without stumbling

- [ ] **Step 5: Commit**

```markdown
## 2026-04-17
- [narrative] Phase 8 voice calibration complete. All narratives now in founder voice. Playbook v1.0.
```

```bash
git add docs/business/fundraising/founder-fluency/
git commit -m "docs(founder-fluency): Phase 8 voice calibration — Playbook v1.0"
```

---

### Task 8.3: Calibrate drill and bear-case Gold answers

**Files:**
- Modify: all `drill.md` and `bear-case.md` files

- [ ] **Step 1: Sweep all Gold-standard answers and Structured Answers**

Apply the same voice calibration to every Gold-standard answer block in drill.md and every Structured Answer block in bear-case.md. The answers should now sound like the founder speaking, not like a staff memo.

- [ ] **Step 2: Acceptance criteria**

Verify:
- Every Gold answer is speakable at natural pace
- Don't-say-this blocks remain unchanged (they are structural, not voice-dependent)
- Anchors still appear verbatim (voice calibration is cadence, not substance)

- [ ] **Step 3: Commit**

```bash
git add docs/business/fundraising/founder-fluency/
git commit -m "docs(founder-fluency): voice calibration for drill + bear-case answers"
```

---

### Task 8.4: Final push and v1.0 tag

- [ ] **Step 1: Push**

```bash
git push origin codex/founder-fluency-playbook-design
```

- [ ] **Step 2: Tag v1.0**

```bash
git tag -a founder-fluency-v1.0 -m "Founder Fluency Playbook v1.0 — voice-calibrated"
git push origin founder-fluency-v1.0
```

- [ ] **Step 3: Open a draft PR for merge to main**

```bash
gh pr create --draft --title "docs(founder-fluency): Playbook v1.0 — Technical / Patent / Market" --body "$(cat <<'EOF'
## Summary
- Introduces the Founder Fluency Playbook at `docs/business/fundraising/founder-fluency/`
- Three volumes × three layers covering Technical Depth, Patent/IP, Market/Timing
- 150 drill questions, 19 bear-case entries, 3 META entries (RBC IP clause, no production traffic, non-technical founder who earned fluency)
- Master braided narrative + canonical appendices (numbers, names)
- Voice-calibrated in Phase 8

## Design reference
`docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md`

## Test plan
- [ ] Founder reads every narrative tier aloud without stumbling
- [ ] Every canonical number in drill/bear-case traces to `appendix-numbers.md`
- [ ] Every META-01 cross-reference lands at the Patent master entry
- [ ] First weekly Gauntlet completed with score ≥18/25

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Final acceptance criteria**

Verify:
- Branch pushed, tag pushed
- Draft PR opened
- Playbook v1.0 is complete: 4 narratives (3 volume + 1 master), 3 drill files (150 questions), 3 bear-case files, 2 appendices, README, CHANGELOG
- First entry in `session-log.md` exists (from Phase 7 Gauntlet)

---

## Post-v1 — Maintenance cadence kicks in

Once Phase 8 is complete, Playbook maintenance follows the ritual schedule specified in the spec and the README:

| Ritual | Cadence | Task expectation |
|---|---|---|
| Weekly Gauntlet | Every week | 15-min session; append log; update any drill/bear-case that surfaces gaps |
| Pre-meeting prep | Before any investor call | Warm-up + Targeted drill |
| Monthly META drill | Every month | Bear-case deep dive rotation: META-01 → META-02 → META-03 |
| Quarterly truth-calibration | Every quarter | Full re-read of bear-case files; tag each entry Resolved / Evolved / New; full-spectrum gauntlet scored and compared to prior quarter |
| Real-world question capture | Event-based | Every investor question from a real conversation ends up in drill.md within the week |

No further phase numbering. Each ritual produces CHANGELOG entries.

---

## Self-review notes

Plan written and self-reviewed for:
1. **Spec coverage:** every section of `2026-04-16-founder-fluency-playbook-design.md` has at least one implementing task.
2. **Placeholder scan:** no TBD/TODO/"fill in later" in Phase 0-5 content. Phase 6-8 deliberately leave content themes open because they are scale-out/calibration tasks where content depends on what was produced earlier.
3. **Type consistency:** all file paths, volume IDs (01-/02-/03-), question ID prefixes (`Q-TECH-`, `Q-PAT-`, `Q-MKT-`), and bear-case ID prefixes (`B-TECH-`, `B-PAT-`, `B-MKT-`, `META-01/02/03`) are consistent across tasks.
4. **Cross-references:** META-01 is referenced from Technical (Task 3.5), Patent master (Task 3.4), Market (Task 4.4). META-02 and META-03 masters are in Technical (Task 2.8) and cross-referenced from Market (Task 4.4). Drill linkage IDs are scaffolded; actual cross-check happens as part of Task 2.8/3.4/4.4 acceptance criteria.
