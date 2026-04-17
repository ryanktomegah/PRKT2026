# Founder Fluency Playbook — Design Spec

**Date:** 2026-04-16
**Author:** Claude (in collaboration with founder)
**Status:** Design approved, ready for implementation planning
**Target audience (v1):** Investors / fundraising conversations
**Extension path:** Bank Pilot, Counsel/IP, Regulator audiences (future phases)

---

## Problem statement

The founder (non-technical, strategic) needs to be fully articulate about LIP — what has been built, is being built, and will be built — to the degree of "owning it like one's own child." Existing fundraising documentation under `docs/business/` is extensive (Investor-Briefing-v2.1.md, Founder-Financial-Model.md, Unit-Economics-Exhibit.md, Competitive-Landscape-Analysis.md, LIP_COMPLETE_NARRATIVE.md, CLIENT_PERSPECTIVE_ANALYSIS.md, etc.) but is audience-diffuse and optimised for *reading*, not *speaking*.

The gap is **production-grade investor fluency**: the ability to deliver the pitch cold, survive 30 minutes of adversarial follow-up, and defend the three weakest-feeling topics — Technical Depth, Patent/IP, and Market/Timing — under pressure, without sounding rehearsed.

This spec describes a written, in-repo artefact (the **Founder Fluency Playbook**) that closes that gap. It is **not** software. It is a structured set of markdown documents, version-controlled in the repo, read and drilled by the founder, and maintained on a published cadence so it stays honest over time.

---

## Scope — v1

**In scope:**
- Three "volumes" covering the founder's three weakest-feeling investor topics: Technical Depth, Patent/IP, Market/Timing.
- Three "layers" per volume: Narrative (read), Drill (practice), Bear-case (honest weaknesses).
- A Master Narrative that braids all three volumes into one spoken pitch.
- Supporting appendices: canonical numbers, canonical names.
- A CHANGELOG discipline to keep the Playbook honest over time.
- An optional **Live-drill mode** where Claude plays the role of investor during Claude Code sessions (uses the same markdown files as its script — no additional tooling).

**Out of scope (v1):**
- Bank Pilot / Counsel / Regulator fluency volumes — reserved for future phases using the same pattern.
- Any non-markdown tooling (apps, UIs, scripts).
- Re-authoring of existing fundraising docs — this Playbook complements, not replaces, `Investor-Briefing-v2.1.md` et al.

---

## Constraints and principles

1. **Static written artefacts, not software.** All outputs are markdown files in the repo. The founder reads them like a book. No install, no login, no app.
2. **Founder voice, eventually.** Claude produces the first draft in clean founder-voice prose; the founder edits in Phase 8 to lock voice, cadence, and anchor phrases as genuinely their own.
3. **Four-tier zoom.** Every narrative supports 30-second, 2-minute, 5-minute, and deep-dive levels of depth.
4. **Anchors, not scripts.** Every answer routes to a small set of canonical anchors (e.g. "two-step classification", "94ms", "300 bps", "ISO 20022 pacs.002"). Memorise anchors, not paragraphs.
5. **Honest bear-case.** Every volume names its genuine weaknesses in writing, with structured non-defensive answers. Dishonesty in this layer is worse than absence of the layer.
6. **Voice rulebook enforced.** Short sentences. Active verbs. Named numbers. No weasel words ("kind of", "sort of", "basically"). No apologies.
7. **T3 ownership.** Designed to live with the project for years. Maintained via CHANGELOG + quarterly truth-calibration ritual.

---

## Architecture

### File layout

```
docs/business/fundraising/founder-fluency/
├── README.md                         ← how to use the Playbook + drill mode
├── CHANGELOG.md                      ← dated updates as project evolves (mandatory)
├── 00-master-narrative.md            ← braided story across all 3 volumes
├── 01-technical-depth/
│   ├── narrative.md                  ← 4-tier narrative (30s / 2min / 5min / deep-dive)
│   ├── drill.md                      ← Q&A bank by persona × difficulty
│   └── bear-case.md                  ← honest weaknesses + structured answers
├── 02-patent-ip/
│   ├── narrative.md
│   ├── drill.md
│   └── bear-case.md
├── 03-market-timing/
│   ├── narrative.md
│   ├── drill.md
│   └── bear-case.md
├── appendix-numbers.md               ← single source of truth for every canonical figure
├── appendix-names.md                 ← people, firms, regulators, prior art
├── bear-case-resolved.md             ← historical record of resolved weaknesses
└── session-log.md                    ← append-only log of drill sessions (optional)
```

### Three-layer structure inside every volume

**Layer 1 — Narrative (read).** Four tiers of depth:

| Tier | Length | Purpose | Memorisation |
|---|---|---|---|
| A — 30-second | 3 sentences | Elevator pitch, opener | Verbatim |
| B — 2-minute | ~200 words | Taxi-ride explanation | Structure + anchors |
| C — 5-minute | ~500 words | Whiteboard explanation, full story arc | Structure + anchors |
| D — Deep-dive | ~1,500 words | Diligence answer, fully absorbed | Absorbed, re-readable night-before |

Each tier ends with a **one-sentence handoff** to the adjacent volumes, training the founder to speak the braid naturally.

**Layer 2 — Drill (practice).** Question bank organised on two axes:

Personas (columns):
- Generalist VC
- Fintech specialist
- Bank-strategic / Corporate VC
- Adversarial / short-seller

Difficulty (rows):
- Warm
- Probing
- Adversarial
- Crushing

Minimum 20 questions per volume at launch, growing to ~50 per volume as real-world questions are captured from actual conversations.

Every drill entry has four mandatory blocks:

1. **Question** — the exact phrasing an investor would use, in their voice.
2. **Gold-standard answer** — 30-second spoken answer, structured *Acknowledge → Anchor → Close*.
3. **Anchors this answer must touch** — explicit list of canonical phrases/numbers the answer must hit.
4. **Don't-say-this traps** — hedges, apologies, weasel words that must never appear.

Optional fifth block: **Bear-case pointer** when the question enters honest-weakness territory.

**Layer 3 — Bear-case (honest weaknesses).** Every volume has `bear-case.md` with a Master Index at the top ranking entries by `(likelihood asked) × (severity if fumbled)`.

Each bear-case entry has six fields:

1. **Honest Truth** — what you'd admit privately to a mentor at 2am.
2. **Structured Answer** — numbered 3-4 step spoken answer: Acknowledge → Reframe → Milestone → (Optional) Confidence Signal.
3. **Don't-say-this** — defensive phrases, false dismissals, apologies.
4. **Resolution Milestone** — the named event that would cause this weakness to be retired.
5. **Investor Intuition** — one sentence describing the feeling the answer should produce in the room.
6. **Drill linkage** — IDs of drill questions that practice this entry.

**Meta bear-cases.** Three weaknesses span multiple volumes and get first-class treatment with extra drill coverage:

- **META-01 — RBC IP clause** (Patent + Founder + Market). Highest priority; referenced from all three volumes, master entry in Patent.
- **META-02 — No production traffic yet** (Technical + Market). Master in Technical.
- **META-03 — Non-technical founder who earned fluency** (Technical + Founder). The structured answer acknowledges cleanly, then shows the work: deliberate study time, every architectural decision personally understood and defensible, Ford Principle codifying team push-back. Investor intuition target: *"they're not a technical founder, but they've done the homework — they can hold the room without an engineer present."* Master in Technical.

### Master Narrative

`00-master-narrative.md` sits above the volumes as the **braided spoken pitch**. Written last because it needs all three volumes to exist. Weaves Technical + Patent + Market into one coherent arc so hybrid questions ("if your patent falls, what's left?") get fluent answers rather than flinches.

### Appendices

- **`appendix-numbers.md`** — single canonical source for every figure the founder may be asked to cite (94ms, 300 bps, $150T correspondent volume, 1284 tests, etc.). Any change propagates from here.
- **`appendix-names.md`** — people, firms, regulators, prior art (e.g. JPMorgan US7089207B1, Bruce Ross, RBCx, AMLD6, SR 11-7).

### Live-drill mode

Live-drill is **not software**. It is a documented convention for how Claude behaves when invoked in a Claude Code session with specific plain-English triggers. The `drill.md` files are Claude's script.

**Triggers:** Plain English — *"Drill me on the Technical volume"*, *"Investor mode: Fintech Specialist, Adversarial, Market"*, *"Gauntlet me on Patent"*, *"Bear-case deep dive, META-01"*.

**Session modes:**

| Mode | Shape |
|---|---|
| Warm-up | 3 Warm/Probing questions, friendly persona, confidence-building |
| Targeted drill | Single persona × difficulty × volume; 5 questions |
| Gauntlet | 5 questions random across personas, escalating Warm → Crushing, strict grading |
| Bear-case deep dive | One bear-case entry, Adversarial persona presses it 5 different ways |

**In-character discipline (hard rules):**
- Claude names persona + volume + mode + difficulty at session start.
- Claude stays in character throughout; no meta-commentary mid-session.
- Claude never hands the founder the answer during the session.
- Claude never softens the persona because the founder is struggling.
- Claude grades silently during the session and reveals scores only at the end.
- The founder can say *"pause"* or *"stop"* to exit character immediately.

**Grading rubric (5 points per question):**

| Dimension | Points | Test |
|---|---|---|
| Anchors hit | 2 | Did the answer name canonical anchors? |
| Traps avoided | 1 | Any hedges, apologies, weasel words? |
| Structure | 1 | Acknowledge → Anchor → Close shape recognisable? |
| Investor intuition | 1 | Would the persona leave with the intended feeling? |

**End-of-session artefact:** a paste-ready markdown block summarising score, strongest/weakest question, traps hit, and pointers into narrative/drill/bear-case files to re-read. Appended to `session-log.md` or discarded at founder's discretion.

---

## Maintenance rituals

| Ritual | Cadence | Purpose |
|---|---|---|
| Weekly Gauntlet | Every week | 15-min drill session, rotating volume, log appended |
| Pre-meeting prep | Event-based (before any investor call) | Warm-up + Targeted drill on likely-topic volume |
| Monthly META drill | Every month | Bear-case deep dive on META-01/02/03, rotating |
| Quarterly truth-calibration | Every quarter | Full re-read of every `bear-case.md`; tag each entry Resolved / Evolved / New; full-spectrum gauntlet scored and compared to prior quarter |

### CHANGELOG discipline

`CHANGELOG.md` at the root of `founder-fluency/` is mandatory. Four triggers require an entry:

1. A canonical number moves.
2. A bear-case resolves (also move entry to `bear-case-resolved.md`).
3. A bear-case evolves (rewrite Honest Truth + Structured Answer, log the delta).
4. A real investor conversation yields a new question (add to `drill.md`, log source).

Entry format:
```markdown
## YYYY-MM-DD
- [numbers] Description (file:ref)
- [bear-case] ID evolved/resolved: brief note
- [drill] Added Q-XXX-NN: "question text" (source)
```

---

## Voice rulebook (enforced in all narratives, drill answers, bear-case answers)

- Short sentences. One idea per sentence.
- Active verbs. *"We detect"* not *"the system is designed to detect"*.
- Numbers named exactly, not approximated. *"Ninety-four milliseconds"*, not *"under a tenth of a second"*.
- No weasel words. *"Kind of"*, *"sort of"*, *"basically"*, *"essentially"* are forbidden.
- No apologies. Acknowledgement is not apology.
- No jargon without immediate plain-English gloss.
- Named anchors used consistently — same phrasing every time.

The voice rulebook is enforced in drill mode via the `Traps avoided` grading dimension.

---

## Implementation phasing (sketch — detailed plan to be written by writing-plans skill)

1. **Phase 0 — Scaffolding.** Folder, README, CHANGELOG, empty appendices.
2. **Phase 1 — Appendix-numbers.** Pass over existing docs; extract every canonical number into single-source-of-truth file.
3. **Phase 2 — Technical volume.** Narrative (4 tiers) → Drill (20 questions min) → Bear-case (5-7 entries including META-02, META-03).
4. **Phase 3 — Patent volume.** Same shape; META-01 (RBC IP clause) written with extra care.
5. **Phase 4 — Market volume.** Same shape.
6. **Phase 5 — Master Narrative.** Braided pitch written last, after all three volumes exist.
7. **Phase 6 — Scale-out to full load.** Grow drill banks from 20 to 50 questions per volume.
8. **Phase 7 — First full-spectrum Gauntlet.** Founder drills live with Claude; identify gaps; iterate.
9. **Phase 8 — Voice calibration.** Founder edits narratives to replace Claude voice with founder voice. **Non-optional milestone.** This is where the Playbook becomes genuinely the founder's.

Each phase commits and pushes to GitHub (per founder's push-at-end-of-sprint feedback rule). Each phase produces a CHANGELOG entry.

---

## Extension plan — post-v1 audiences

Same three-layer pattern extends cleanly to three future audience sets, each in its own folder:

- **Bank Pilot fluency** — `docs/business/bank-pilot/founder-fluency/`. Volumes for RBCx, Transaction Banking, AI Group. Personas shift to Innovation Lead, AML Officer, LOB Head, Procurement. Bear-case dominated by deployment friction.
- **Counsel / IP fluency** — `docs/legal/patent/founder-fluency/`. Personas: patent counsel, RBC employment counsel, examiner-proxy. Bear-case dominated by META-01.
- **Regulator fluency** — `docs/legal/founder-fluency/`. Personas: EU regulator, US regulator, bank compliance officer, audit firm. Bear-case dominated by compliance-hold enforcement and model governance.

When v2 or later adds a second audience, the parent folder renames once from `docs/business/fundraising/founder-fluency/` to `docs/founder-fluency/` (or `docs/founder/`) — trivial rename, no content change. All content stays under the new root.

---

## Success criteria

The Playbook is working when:

1. The founder can open any `narrative.md` and read aloud at full pace without a flinch, stumble, or jargon fallback.
2. Gauntlet scores trend upward quarter-over-quarter (tracked in `session-log.md`).
3. Every investor question from a real conversation ends up in `drill.md` within the week.
4. META bear-cases are answered without defensive body-language in live settings (self-assessed post-meeting).
5. A year from now, CHANGELOG.md tells the honest story of what was learned, resolved, and still outstanding.

The Playbook is **not** working if:

- `bear-case.md` has been untouched for a quarter.
- The founder still reaches for Claude or an engineer mid-pitch to answer a Technical question.
- Numbers in narratives drift out of sync with `appendix-numbers.md`.
- The quarterly truth-calibration ritual gets skipped.

---

## Risks and honest limits of this design

- **Voice drift.** Claude-drafted narrative will read as Claude's voice until Phase 8 calibration happens. If Phase 8 is skipped, the Playbook will feel slightly off when spoken. Mitigation: Phase 8 is named non-optional in the build sequence.
- **Drift between v1 Playbook and canonical docs.** `appendix-numbers.md` is the single source of truth, but existing docs (`Investor-Briefing-v2.1.md`, `Founder-Financial-Model.md`) may diverge. Mitigation: Phase 1 extracts numbers *from* existing docs; subsequent updates flow *from* the appendix outward.
- **Staleness.** Without the quarterly ritual, the Playbook becomes dishonest quietly. Mitigation: ritual is written into the Playbook's README and tied to a calendar trigger.
- **Over-reliance on drill mode.** If drill mode becomes a substitute for reading + internalising the narrative, fluency will be shallow. Mitigation: drill mode is documented as supplementary, never primary.

---

## Open items (to be resolved during implementation)

- Exact anchor phrases per volume (decided during Phase 2-4 narrative drafting, then locked).
- Final ordering of bear-case entries within each volume's Master Index (decided at Phase 2-4).
- Whether `session-log.md` is committed to the repo or kept local (defer to founder preference after first session).

---

## Next step

Transition to **writing-plans** skill to produce a phased implementation plan matching the 9-phase sketch above.
