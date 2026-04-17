# Founder Fluency Playbook — Implementation Plan

> **For agentic workers:** Each task is a discrete writing unit with a single commit. Phases are sequential; within a phase, tasks may be executed in parallel only where explicitly marked. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Founder Fluency Playbook v1 — a written, in-repo artefact that gives the non-technical strategic founder production-grade investor fluency across Technical Depth, Patent/IP, and Market/Timing volumes, plus a braided Master Narrative, appendices, drill banks, and bear-case entries. Design spec: `docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md`.

**Architecture:** 9 sequential phases broken into 18 atomic tasks. Scaffolding first, then single-source-of-truth appendix (drives all downstream numbers), then the three volumes (Technical → Patent → Market), then the braided Master Narrative, then scale-out and calibration. Each phase ends with a commit + push + CHANGELOG entry per the founder's push-at-end-of-sprint rule.

**Tech Stack:** Markdown only. No code, no tests, no CI impact. Verification is manual (founder read-aloud + drill-mode gauntlet).

**IP Safety:** Docs-only work. No patent-family algorithms, no code changes. META-01 (RBC IP clause) is explicitly addressed in Phase 3's bear-case layer — writing the bear-case entry is not itself an IP-exposing act, since the clause analysis already exists in `docs/business/fundraising/ip-risk-pre-counsel-analysis-revised.md`.

---

## Pre-Flight

### Task 1: Branch + baseline verification

**Files:** none (git operation only)

- [ ] **Step 1: Confirm current branch**

```bash
cd /Users/tomegah/PRKT2026
git branch --show-current
```

Expected: `codex/founder-fluency-playbook-design` (the design-spec commit `a2733ef` already lives here).

- [ ] **Step 2: Sync with main and rebase if behind**

```bash
git fetch origin main
git rebase origin/main
```

- [ ] **Step 3: Confirm design spec is present**

```bash
ls docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md
```

Expected: file exists. If missing, stop — the spec is a prerequisite.

---

## Phase 0 — Scaffolding

### Task 2: Create folder structure + skeleton files

**Files:** `docs/business/fundraising/founder-fluency/` (new directory tree)

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p docs/business/fundraising/founder-fluency/{01-technical-depth,02-patent-ip,03-market-timing}
```

- [ ] **Step 2: Create empty skeleton files with H1 headers only**

Create the following files, each with just an H1 line and a `**Status:** skeleton — populated in Phase N.` placeholder:

- `founder-fluency/README.md` — "How to use this Playbook"
- `founder-fluency/CHANGELOG.md` — entry `## 2026-04-17\n- [scaffolding] Playbook folder initialised`
- `founder-fluency/00-master-narrative.md`
- `founder-fluency/01-technical-depth/narrative.md`
- `founder-fluency/01-technical-depth/drill.md`
- `founder-fluency/01-technical-depth/bear-case.md`
- `founder-fluency/02-patent-ip/{narrative,drill,bear-case}.md` (3 files)
- `founder-fluency/03-market-timing/{narrative,drill,bear-case}.md` (3 files)
- `founder-fluency/appendix-numbers.md`
- `founder-fluency/appendix-names.md`
- `founder-fluency/bear-case-resolved.md`

No `session-log.md` yet — deferred per spec open-item (founder preference after first session).

- [ ] **Step 3: Populate README.md with usage + drill-mode triggers**

Content: three sections — "Reading order" (pointing to narrative.md files in order 01 → 02 → 03 → 00), "Drill mode" (listing plain-English triggers verbatim from spec §Live-drill mode), "Maintenance rituals" (copy the four-row table from spec §Maintenance rituals). No bluff-writing — link to the spec for full detail.

- [ ] **Step 4: Commit + push**

```bash
git add docs/business/fundraising/founder-fluency/
git commit -m "docs(founder-fluency): phase 0 — scaffold folder tree + README"
git push origin codex/founder-fluency-playbook-design
```

---

## Phase 1 — Appendix Numbers (single source of truth)

### Task 3: Extract canonical numbers from existing fundraising docs

**Files:** `founder-fluency/appendix-numbers.md` (populate), `founder-fluency/CHANGELOG.md` (entry)

- [ ] **Step 1: Read existing canonical sources in full**

Source docs to read (do NOT infer numbers — read them):
- `docs/business/Investor-Briefing-v2.1.md`
- `docs/business/Founder-Financial-Model.md`
- `docs/business/Unit-Economics-Exhibit.md`
- `docs/business/Revenue-Projection-Model.md`
- `docs/business/Market-Fundamentals-Fact-Sheet.md`
- `docs/business/Competitive-Landscape-Analysis.md`
- `lip/common/constants.py` (for 300 bps, 94ms, 45-day UETR TTL, maturity classes)

- [ ] **Step 2: Organise numbers into 4 groups in appendix-numbers.md**

Groups:
1. **Technical constants** (94ms SLO, 300 bps floor, 800 bps warehouse floor, 45-day UETR, CLASS_A/B/C maturity, 1284 tests — verify count with `find lip/tests -name 'test_*.py' | xargs grep -c '^def test_'`)
2. **Market numbers** ($150T correspondent volume, addressable market slices — cite source doc + section)
3. **Financial model** (fee split 30%/70% BPI/bank, royalty definition per `feedback_income_classification.md`, unit economics per-tx)
4. **Product scale** (# of rails supported, # of patent families P1-P12, # of ISO 20022 message types handled)

Each entry format:
```markdown
- **Label:** Value — source: `<file>:<section>` — last verified: 2026-04-17
```

- [ ] **Step 3: Flag any number with conflicting values across docs**

If Investor-Briefing says X and Founder-Financial-Model says Y, do NOT pick one silently. Add a `⚠️ CONFLICT` note under that entry listing both values with their sources. The founder resolves these in Phase 8 (voice calibration) or sooner if blocking.

- [ ] **Step 4: Add CHANGELOG entry**

```markdown
## 2026-04-17
- [numbers] Populated appendix-numbers.md from Investor-Briefing v2.1, Founder-Financial-Model, Unit-Economics-Exhibit, constants.py
- [numbers] N conflicts flagged for founder resolution (if any)
```

- [ ] **Step 5: Commit + push**

```bash
git add docs/business/fundraising/founder-fluency/
git commit -m "docs(founder-fluency): phase 1 — extract canonical numbers to appendix"
git push origin codex/founder-fluency-playbook-design
```

### Task 4: Populate appendix-names

**Files:** `founder-fluency/appendix-names.md`

- [ ] **Step 1: Extract named entities from existing docs**

Categories:
- **People:** Bruce Ross (RBC AI Group), founder, any named advisors
- **Firms:** JPMorgan, Deutsche Bank, Siemens (from EPG-14 example), RBCx, RBC Transaction Banking
- **Regulators:** FATF, AMLD6, SR 11-7, EU AI Act, DORA, OFAC, SDN
- **Prior art / patents:** JPMorgan US7089207B1, any other patents cited in `docs/legal/patent/`
- **Standards:** ISO 20022, pacs.002/pacs.008, SWIFT, SEPA, FedNow, RTP, UETR
- **Internal codenames:** P1-P12 patent families, C1-C8 components, QUANT/NOVA/CIPHER/REX/ARIA/DGEN/FORGE team agents, EPG-01 through EPG-23

Each entry: one-line neutral description. No marketing spin. Purpose is pronunciation + recall aid.

- [ ] **Step 2: Commit + push** (combine with Task 5 if chronologically tight)

---

## Phase 2 — Technical Depth Volume

### Task 5: Technical narrative (4 tiers)

**Files:** `01-technical-depth/narrative.md`

Work product per spec §Architecture → Three-layer structure → Layer 1.

- [ ] **Step 1: Draft Tier A (30-second, 3 sentences, verbatim memorisation)**

Covers: what LIP does (bridge loan against stuck payment) + how it knows which to bridge (two-step classification against ISO 20022 event taxonomy) + why this matters (94ms, not a payments processor). No jargon without gloss.

- [ ] **Step 2: Draft Tier B (2-minute, ~200 words, structure+anchors)**

Expand Tier A into: (1) the problem payments world has — stuck payments cost working capital, (2) what classification unlocks — CLASS_A vs BLOCK, (3) the 300 bps floor as a QUANT discipline, (4) the 45-day UETR TTL as the resolution window. End with handoff sentence to Patent volume.

- [ ] **Step 3: Draft Tier C (5-minute, ~500 words, whiteboard shape)**

Full arc: ISO 20022 event → C1 classifier → taxonomy gate → C2 PD model → fee floor → C3 repayment → C5 streaming → C7 offer. Anchors every number. End with handoff to both Patent (patent surrounds the two-step gate) and Market (why this only works now, not 5 years ago).

- [ ] **Step 4: Draft Tier D (deep-dive, ~1500 words, diligence answer)**

Every architectural choice defensible. Include: why two-step classification vs. one-step, why ISO 20022 vs proprietary schema, why QUANT fee floor at 300 bps not 200 or 400, why Flower for FL not centralised, why Rényi DP accounting. Cites `lip/common/constants.py` + relevant EPG decisions.

- [ ] **Step 5: Voice-rulebook pass**

Re-read for: short sentences, active verbs, no weasel words, named numbers, anchor consistency. Spec §Voice rulebook.

- [ ] **Step 6: Commit + push**

```bash
git commit -m "docs(founder-fluency): phase 2 — technical narrative (4 tiers)"
git push origin codex/founder-fluency-playbook-design
```

### Task 6: Technical drill bank (20 questions minimum at launch)

**Files:** `01-technical-depth/drill.md`

Structure per spec §Layer 2: matrix of Personas × Difficulty.

- [ ] **Step 1: Build the matrix header**

4 personas × 4 difficulty tiers = 16 cells. 20 questions minimum means some cells get 2 questions; prioritise density in Adversarial × Fintech-specialist and Crushing × Short-seller.

- [ ] **Step 2: Write questions**

Each entry has 4 mandatory blocks: Question / Gold-standard answer (Acknowledge→Anchor→Close) / Anchors this answer must touch / Don't-say-this traps. Optional fifth block: bear-case pointer.

Seed question list (founder expands in Phase 7):
1. "Walk me through what happens in the 94ms." (Probing, Fintech)
2. "Why not just use a proprietary event schema — ISO 20022 is slow." (Adversarial, Fintech)
3. "You're a non-technical founder. How do you know your team shipped the right architecture?" (Adversarial, Generalist) — routes to META-03
4. "Show me one place your 300 bps floor would be wrong." (Crushing, Fintech)
5. "You have no production traffic. How is any of this validated?" (Crushing, Short-seller) — routes to META-02
6. ... (15 more covering C1 classifier, C2 PD model, FL privacy budget, fee discipline, latency profile, failure modes, rail coverage)

- [ ] **Step 3: Commit + push**

### Task 7: Technical bear-case entries

**Files:** `01-technical-depth/bear-case.md`

Per spec §Layer 3 — 6 fields per entry + Master Index ranking by (likelihood × severity).

- [ ] **Step 1: Write entries for 5-7 technical bear-cases**

Required entries:
- **META-02 master — No production traffic yet** (full 6-field entry)
- **META-03 master — Non-technical founder who earned fluency** (full 6-field entry — pattern from spec §Meta bear-cases)
- **Synthetic data overfitting risk** (DGEN-adjacent)
- **FL privacy-utility tradeoff honesty** (Opacus noise hurts model quality — acknowledge + roadmap)
- **Latency SLO under real bank load** (94ms is measured on synthetic traffic)
- **C1 classifier label leakage** (cite ARIA's model card caveats)
- **Test count ≠ correctness** (1284 tests is a vanity number if scenarios miss)

- [ ] **Step 2: Write Master Index at top of file**

Rank by (likelihood asked × severity if fumbled). META-02 and META-03 at top.

- [ ] **Step 3: Commit + push**

---

## Phase 3 — Patent / IP Volume

### Task 8: Patent narrative (4 tiers)

**Files:** `02-patent-ip/narrative.md`

Same 4-tier structure. Anchors:
- "Two-step classification + conditional offer" (the core claim per EPG-20)
- "Language-scrubbed spec" (EPG-21)
- "12-family portfolio P1–P12"
- "Pre-RBC-employment filing strategy" — CAREFUL phrasing here per META-01

- [ ] **Step 1: Draft 4 tiers**

Tier D must walk the patent family tree (P1 core, P4/P12 FL, P5 CBDC/cascade, P7 tokenization, P8 treasury, P10 regulatory) with one-sentence claim summary per family — no code, no algorithm disclosure.

- [ ] **Step 2: Commit + push**

### Task 9: Patent drill bank

**Files:** `02-patent-ip/drill.md`

- [ ] **Step 1: Write 20 questions**

Heavy weight on:
- "What stops a big bank from copying you?" (Probing, every persona)
- "Your RBC employment IP clause — walk me through it." (Crushing, every persona) — routes to META-01
- "Is JPMorgan's US7089207B1 prior art against you?" (Adversarial, Fintech)
- "How is language scrub not just security-through-obscurity?" (Adversarial, Short-seller)
- "What's your FTO opinion, and who wrote it?" (Crushing, Bank-strategic)

- [ ] **Step 2: Commit + push**

### Task 10: Patent bear-case — META-01 extra-care entry

**Files:** `02-patent-ip/bear-case.md`

Per spec §Meta bear-cases: "META-01 — RBC IP clause — Highest priority; referenced from all three volumes, master entry in Patent."

- [ ] **Step 1: Read the existing IP risk analysis in full**

Source: `docs/business/fundraising/ip-risk-pre-counsel-analysis-revised.md`. This is the canonical truth — the bear-case answer cannot contradict it. Also read `project_rbc_ip_clause_analysis.md` memory entry for strategic framing.

- [ ] **Step 2: Write META-01 master entry (6 fields, extra-careful)**

- **Honest Truth:** RBC offer letter contains broad IP assignment covering anything conceived during employment. 0 of 439 commits predate employment start. This is not a solved problem.
- **Structured Answer (4 steps):** (1) Acknowledge the clause exists and is broad. (2) Reframe: the work at issue is technical+market research that predates the employment pattern, documented in public fundraising materials. (3) Milestone: employment counsel engagement + pre-employment evidence hunt + potential patent-assignment carve-out negotiation. (4) Confidence signal: the founder is handling this head-on, not hiding it.
- **Don't-say-this:** "It's not really an issue" / "My lawyer said..." (unless actually engaged) / "RBC wouldn't actually enforce..." / any minimising phrase
- **Resolution Milestone:** Signed carve-out from RBC or employment counsel written opinion ring-fencing pre-employment work
- **Investor Intuition:** "This founder is looking the risk in the face, not hoping it goes away"
- **Drill linkage:** Q-PAT-01, Q-PAT-03, Q-MKT-05 (cross-volume)

- [ ] **Step 3: Write 4-6 other patent bear-cases**

- Claim narrowness under examiner pressure
- JPMorgan US7089207B1 prior-art exposure
- FTO opinion not yet written
- Defensive-only posture (not asserting claims yet)
- Language-scrub might not survive adversarial inspection

- [ ] **Step 4: Commit + push**

---

## Phase 4 — Market / Timing Volume

### Task 11: Market narrative (4 tiers)

**Files:** `03-market-timing/narrative.md`

Anchors: $150T correspondent volume, ISO 20022 mandate timing (CBPR+, Target2), Basel III treatment of stuck payments, why-now (ISO 20022 migration completes the event taxonomy prerequisite).

- [ ] **Step 1: Draft 4 tiers**
- [ ] **Step 2: Commit + push**

### Task 12: Market drill bank

**Files:** `03-market-timing/drill.md`

- [ ] **Step 1: Write 20 questions**

Questions must include:
- "Why hasn't an incumbent done this already?" (Probing → Adversarial, every persona)
- "TAM math — walk me through how you got to X." (Probing, Fintech)
- "5-year-from-now scenario — what kills this company?" (Crushing, Short-seller)
- "Geographic coverage — why start with US correspondent flows?" (Probing, Bank-strategic)

- [ ] **Step 2: Commit + push**

### Task 13: Market bear-case

**Files:** `03-market-timing/bear-case.md`

Entries (5-7):
- Incumbent defensive response (Ripple, Visa B2B Connect, bank consortiums)
- TAM compression if ISO 20022 migration slows
- Bank appetite for third-party intermediation (procurement friction)
- Regulatory arbitrage risk (cross-border fee bridging flagged by regulator)
- META-01 cross-volume pointer (founder/market risk intertwined)

- [ ] **Step 1: Write entries + Master Index**
- [ ] **Step 2: Commit + push**

---

## Phase 5 — Master Narrative (braided)

### Task 14: Write 00-master-narrative.md

**Files:** `founder-fluency/00-master-narrative.md`

Per spec §Master Narrative: "Written last because it needs all three volumes to exist."

- [ ] **Step 1: Draft 4 tiers of the braided pitch**

Structure: Technical hook → Patent moat → Market timing → close. Each handoff sentence from the volume narratives becomes a transition in the master. No new anchors introduced — every number/phrase must already exist in a volume narrative or the appendix.

- [ ] **Step 2: Verify hybrid-question coverage**

Read the master aloud. The test: can it be interrupted at any handoff and still end in the right place? If a hybrid question like "if your patent falls, what's left?" gets a flinch, the braid is wrong — rewrite.

- [ ] **Step 3: Commit + push**

---

## Phase 6 — Scale-out drill banks (20 → 50 per volume)

### Task 15: Expand Technical drill bank to ~50 questions

**Files:** `01-technical-depth/drill.md`

- [ ] **Step 1: Fill empty matrix cells**

Prioritise coverage over density: every Persona×Difficulty cell gets at least 2 questions before any cell gets a 5th.

- [ ] **Step 2: Add real-world questions (post-conversation capture)**

Reserve a `## Captured from real conversations` subsection. Empty at launch — fills as founder has actual investor meetings and adds questions with source attribution per spec §CHANGELOG discipline trigger #4.

- [ ] **Step 3: Commit + push**

### Task 16: Expand Patent + Market drill banks to ~50 each

**Files:** `02-patent-ip/drill.md`, `03-market-timing/drill.md`

- [ ] **Step 1: Same coverage-first approach per volume**
- [ ] **Step 2: Commit + push (one commit per volume or combined — founder's call)**

---

## Phase 7 — First full-spectrum Gauntlet (live session)

### Task 17: Drill-mode dry-run + session log kickoff

**Files:** `founder-fluency/session-log.md` (new, if founder opts in)

- [ ] **Step 1: Founder triggers drill mode**

Founder says: *"Gauntlet me, full spectrum."* Claude plays 5 questions escalating Warm → Crushing, random personas across all 3 volumes. Grades silently, reveals at end.

- [ ] **Step 2: Log session (if founder opts in)**

Append to `session-log.md` per spec §Live-drill mode end-of-session artefact.

- [ ] **Step 3: Identify gaps**

Any anchor that failed to land, any trap hit, any bear-case pointer that confused — these are edit targets for Phase 8.

- [ ] **Step 4: Commit + push (session-log addition if opted in)**

---

## Phase 8 — Voice calibration (NON-OPTIONAL)

### Task 18: Founder edits narratives to own the voice

**Files:** all `narrative.md` files + `00-master-narrative.md`

Per spec §Implementation phasing: "Non-optional milestone. This is where the Playbook becomes genuinely the founder's."

- [ ] **Step 1: Founder reads each narrative aloud and edits in place**

Claude does not write this phase. The founder edits. Claude's role is: answer voice questions, flag if an edit contradicts a canonical number (routes back to appendix), never re-introduce Claude-voice phrasing.

- [ ] **Step 2: Lock anchor phrases**

Once an anchor phrase is edited into founder-voice form, it is locked — every other mention across all files updates to match. This is a find-and-replace exercise (cross-reference discipline).

- [ ] **Step 3: CHANGELOG entry — voice calibration complete**

```markdown
## YYYY-MM-DD
- [voice] Phase 8 voice calibration complete; anchors locked; Playbook is now founder-voice
```

- [ ] **Step 4: Commit + push + open PR**

```bash
git commit -m "docs(founder-fluency): phase 8 — voice calibration (founder)"
git push origin codex/founder-fluency-playbook-design
gh pr create --repo ryanktomegah/PRKT2026 --draft --title "Founder Fluency Playbook v1" --body-file <(cat <<'EOF'
## Plan
Implements the Founder Fluency Playbook v1 per spec at `docs/superpowers/specs/2026-04-16-founder-fluency-playbook-design.md`. Nine phases, 18 atomic tasks, docs-only.

## Design Decisions
- Markdown-only, in-repo. No tooling, no software.
- `appendix-numbers.md` is the single source of truth; all volume narratives cite it.
- META-01 (RBC IP clause) gets master entry in Patent + cross-volume pointers.
- Phase 8 voice calibration is non-optional — marks the Playbook as genuinely the founder's.

## Test Evidence
- Voice-rulebook pass on every narrative tier
- Full-spectrum gauntlet (Phase 7) grades captured in session-log.md
- Anchor consistency verified via cross-reference check

## Risks/Gaps
- Real investor questions not yet captured — drill banks start at launch density, grow with conversations.
- `session-log.md` commitment is optional per founder preference (spec open-item).
EOF
)
```

---

## Success Criteria (from spec §Success criteria)

The plan is successfully executed when:

1. All 18 tasks committed + pushed
2. Each phase has a CHANGELOG entry
3. Phase 7 gauntlet produces a scored session log
4. Phase 8 voice calibration is marked complete in CHANGELOG
5. Every number in every narrative resolves to a row in `appendix-numbers.md`
6. META-01, META-02, META-03 all have master entries + cross-volume pointers
7. PR opened, draft, with Plan/Design/Test/Risks sections per Protocol Guard

---

## Out of Scope (per spec)

- Bank Pilot / Counsel / Regulator fluency volumes (future phases)
- Any non-markdown tooling
- Re-authoring existing fundraising docs

---

## Notes on execution

- **IP safety:** This plan touches zero code and zero patent-family algorithms. It is safe-harbor work under the unresolved RBC IP clause blocker.
- **Branch:** Continue on `codex/founder-fluency-playbook-design` — the design-spec commit is already there.
- **Push cadence:** Commit + push at end of every task per founder's push-at-end-of-sprint rule. Don't batch.
- **Conflict handling:** If `appendix-numbers.md` surfaces a conflict between Investor-Briefing and Founder-Financial-Model, do NOT silently pick — flag to founder and resolve before depending on that number in a volume narrative.
- **Ford Principle:** The founder sets direction. If a volume narrative draft seems wrong in spirit (not just in voice), push back before finishing the tier — don't ship a flawed draft hoping Phase 8 will fix it.
