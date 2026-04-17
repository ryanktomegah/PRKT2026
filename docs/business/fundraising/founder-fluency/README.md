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
