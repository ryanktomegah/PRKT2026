# Appendix — Commit Forensics

**Purpose:** Lawyer-facing factual appendix consolidating the commit-history audit performed in Tasks 1.1–1.3 of the Week 1 IP & Timing workstream.
**Generated:** 2026-04-17
**Author:** Pre-lawyer review, Task 1.4
**Audience:** External IP / employment counsel
**Companion documents in this directory:**
- `commit-timeline-summary.md` — Task 1.2 narrative summary (primary source)
- `commit-timeline.csv` — raw per-commit data (hash, author-date, author name, email, subject)
- `commits-off-hours.txt` — enumerated off-hours commits
- `/.mailmap` (repo root) — canonical identity mapping, added in commit `153e398`

This appendix is **descriptive only**. It states facts observable in the git history of the PRKT2026 repository and does not draw legal conclusions. Interpretation of any fact (e.g., whether off-hours timestamps support a "personal time" defense, whether AI-agent authorship affects inventorship, whether the timing gap supports or undermines prior conception) is reserved for counsel.

---

## 1. Scope

- **Repository audited:** `ryanktomegah/PRKT2026` (origin on GitHub) — local working tree at `/Users/tomegah/PRKT2026`.
- **Branches covered:** all local and remote — **63 branches total** (15 local + 48 remote, 50 unique names after dedup). Audit used `git log --all`, so detached and unmerged work is included.
- **Date range of commits observed:** 2026-02-27 09:16:30 PST through 2026-04-17 21:47:xx PDT (first commit → latest commit at time of this appendix).
- **RBC employment start (IP-clause trigger date):** 2026-01-12.
- **Timeframe of interest for IP timing:** any commit before 2026-01-12 (pre-employment, outside the clause) versus any commit on or after 2026-01-12 (in-scope of the clause).
- **Timestamp convention:** author-date (`%ai`), in the author's local timezone (America/Los_Angeles throughout). Committer-date (`%ci`) is not used because rebases and cherry-picks can drift it.
- **Methodology:** see Section 6 and the methodology appendix of `commit-timeline-summary.md` for regeneration commands.

---

## 2. Headline numbers

| Metric | Value |
|---|---:|
| Commits authored before RBC start (2026-01-12) | **0** |
| Commits authored on/after RBC start | **554** (100% of repo) |
| First commit in repository (author-date) | **2026-02-27 09:16:30 PST** |
| Most recent commit at time of this appendix | **2026-04-17 21:47 PDT** |
| Days from RBC start to first commit | **46 days** |
| Branches audited (local + remote, dedup) | **63 / 50 unique** |

The repository contains **zero pre-employment commits**. The entire git history was authored during Ryan's RBC tenure.

**Reconciliation with Task 1.2 snapshot:** the Task 1.2 summary reports 551 total commits as of the 2026-04-17 snapshot. The current figure (554) reflects the three commits added since that snapshot: the Task 1.2 fix commit (`abb750e`), the Task 1.3 mailmap commit (`153e398`), and the Task 1.4 commit that finalises this appendix. All three are post-2026-01-12 and are Ryan-authored; none change the headline conclusion (0 pre-RBC commits).

---

## 3. Author breakdown (canonical identities post-`.mailmap`)

After applying `.mailmap` (commit `153e398`), the contributor set collapses to five distinct identities. `git log --all --use-mailmap` on the current tree produces:

| Canonical author | Email | Commits | % of 554 | Type |
|---|---|---:|---:|---|
| Ryan Tomegah | naumryan66@gmail.com | **440** | 79.4% | Human (founder) |
| copilot-swe-agent[bot] | 198982749+Copilot@users.noreply.github.com | 64 | 11.6% | AI agent (GitHub Copilot) |
| Claude | noreply@anthropic.com | 43 | 7.8% | AI agent (Claude Code) |
| github-actions[bot] | 41898282+github-actions[bot]@users.noreply.github.com | 4 | 0.7% | CI automation |
| git stash | git@stash | 3 | 0.5% | Stash-restore artefact, not a real identity |
| **Total** | | **554** | 100.0% | |

**Human vs. non-human split:** 440 human commits (79.4%), 114 non-human commits (20.6%).

**No third-party human contributors.** Only one natural person appears in the post-mailmap history.

### Pre-mailmap identities (for audit traceability)

Before the `.mailmap` commit, the 440 human commits were split across four distinct git identities that all belong to Ryan Tomegah:

| Pre-mailmap name | Pre-mailmap email | Notes |
|---|---|---|
| Tomegah Ryan | tomegah@Tomegahs-MacBook-Air.local | Laptop default git identity |
| Ryan | naumryan66@gmail.com | Personal Gmail |
| ryanktomegah | ryanktomegah@gmail.com | Primary personal Gmail (older account) |
| YESHA | ryanktomegah@gmail.com | Same email as `ryanktomegah`, different display name |

These are all the same person. Consolidation is visual only (see Section 6).

---

## 4. AI-agent contribution volume

Three bot-class identities contribute code or automated changes to this repository. Quantities are as observed in `git log --all --use-mailmap`:

| Bot identity | Commits | % of 554 | What it does |
|---|---:|---:|---|
| copilot-swe-agent[bot] | 64 | 11.6% | GitHub Copilot SWE Agent — completes assigned issues, opens pull requests authored under the bot identity |
| Claude (noreply@anthropic.com) | 43 | 7.8% | Claude Code — author identity on commits generated by the Claude Code CLI, including co-authored commits |
| github-actions[bot] | 4 | 0.7% | GitHub Actions workflow commits (e.g., release metadata, version bumps) |
| **AI-agent / automation subtotal** | **111** | **20.0%** | |
| git stash | 3 | 0.5% | Artefact identity for `git stash` restore; not an AI system |

**Combined AI-agent + automation share:** 20.0% of all commits. Excluding `github-actions[bot]` and `git stash` (which are plumbing/automation, not generative AI), the strictly-AI share is **107 / 554 = 19.3%**.

**Note for counsel:** "authored by" in git metadata does not map cleanly to "inventorship" as a legal concept. Many of the Copilot and Claude commits reflect the AI agent being directed by Ryan to implement a specification he authored; others contain suggestions originated by the agent. Per-commit authorship classification (human-originated vs. agent-originated contribution) is out of scope for this appendix and is tracked as **Task 4.2 — AI inventorship matrix** in the Week 4 plan.

---

## 5. Off-hours analysis

"Off-hours" is defined here as any author-timestamp that falls **outside Monday–Friday 09:00–17:59 local time**. That is, weekends in full (Sat/Sun any hour), plus weekday evenings (18:00 onward), plus weekday early mornings (before 09:00). All computations use the author-date timezone recorded in the commit (America/Los_Angeles throughout).

### 5.1 All commits (including bots)

| Window | Commits | % of 554 |
|---|---:|---:|
| Weekday business hours (Mon–Fri 09:00–17:59) | 175 | 31.6% |
| Weekday early morning (Mon–Fri, before 09:00) | 93 | 16.8% |
| Weekday evening (Mon–Fri, 18:00 onward) | 121 | 21.8% |
| Weekend (Sat/Sun, any hour) | 165 | 29.8% |
| **Off-hours total (evenings + weekends + early morning)** | **379** | **68.4%** |

### 5.2 Human-authored commits only (bots excluded)

This is the figure of primary interest for the IP-timing narrative — it isolates Ryan's direct authorship.

| Bucket | Commits | % of 440 |
|---|---:|---:|
| Business hours (Mon–Fri 09:00–17:59) | 152 | 34.5% |
| **Off-hours (evenings + weekends + early morning)** | **288** | **65.5%** |

Approximately two-thirds of Ryan's human-authored commits carry off-hours timestamps.

**Reconciliation with Task 1.2:** Task 1.2 reported 285 / 437 = 65.2% for human off-hours on the 2026-04-17 snapshot. Current figures (288 / 440 = 65.5%) include the three additional commits authored after the Task 1.2 snapshot, all three authored after 21:00 local time (off-hours). The underlying proportion is unchanged.

### 5.3 Caveat on timestamp-based inference

A commit's author-timestamp records when `git commit` was run on the local machine. It does **not** record:
- when the code in the commit was *written* (the work may span hours or days before the commit itself);
- whether the author was physically on their employer's premises or on personal equipment at the moment of commit;
- whether the author was on PTO, a statutory holiday, a lunch break, or otherwise not engaged in RBC work during business-hours commits;
- whether the author-timestamp has been modified (timestamps can be manually set via `--date` or rewritten via filter-branch; no evidence of such manipulation is presented here, but the possibility exists as a factual matter).

Accordingly, the 65.5% off-hours figure is **descriptive of the commit record**, not dispositive of the underlying question "was this work done on personal time?"

The raw enumeration of the 376+ off-hours commits (as of the Task 1.2 snapshot) is available at `commits-off-hours.txt` in this directory for per-commit inspection.

---

## 6. Identity consolidation note

Prior to Task 1.3, Ryan Tomegah's commits were distributed across four distinct git author strings (two display names x two emails, plus a laptop-hostname identity). This is a common artefact of committing from multiple machines and email accounts over time; it is not evidence of multiple contributors.

**Consolidation mechanism.** Commit `153e398` ("chore(review): consolidate contributor identities via .mailmap") added a `.mailmap` file to the repository root that maps every historical Ryan identity to a single canonical string:

```
Ryan Tomegah <naumryan66@gmail.com>
```

**Important technical note for counsel.** `.mailmap` is a **display-level** mechanism only. It does not rewrite history. The underlying commit objects still carry their original author names and emails. Every git tool that honours mailmap (`git log`, `git shortlog`, `git blame`, `git annotate`) will show the canonical identity; tools or forensic exports that do not honour mailmap will show the pre-consolidation identities. The `git log --use-mailmap` flag (used throughout this appendix) forces mailmap resolution. Tasks 1.1 and 1.2 source data were captured pre-mailmap and show the four historical identities; this appendix is the first document generated post-mailmap.

No history rewrite, rebase, or force-push was performed as part of consolidation. All original commit hashes are preserved.

---

## 7. Flags for counsel

The following are factual observations that appear material to an IP / employment-law review of this repository. They are presented without legal interpretation.

1. **46-day gap between RBC start and first commit.** RBC employment began 2026-01-12; the first commit in this repository is 2026-02-27. There is **no git-record evidence in this repository of pre-employment conception or implementation**. Evidence of prior conception (if any) would have to come from sources outside git — e.g., notebooks, emails, prior repositories, design documents, napkin sketches — and is the subject of a separate workstream (Day 5 / Task 5.2 — Prior-Conception Evidence Hunt).

2. **Zero pre-employment commits.** All 554 commits in the repository post-date the RBC IP clause attaching. The IP-timing defense cannot rely on "this repo existed before I joined RBC." Any defense must be grounded either in (a) work authored on personal time and equipment after employment began, or (b) prior-conception evidence external to this repository.

3. **AI-agent authorship is ~20% of commits.** Claude Code (43), Copilot (64), and GitHub Actions (4) together author 111 / 554 commits (20.0%). Inventorship and IP-clause implications of AI-agent-authored contributions are a known open question and are scheduled for analysis in **Task 4.2 — AI inventorship matrix**. Counsel should be aware of the volume at this appendix stage.

4. **~65% of human commits are off-hours.** 288 / 440 = 65.5% of Ryan-authored commits carry weekend or evening/early-morning timestamps. This is descriptive of the commit record; see Section 5.3 for caveats on what timestamps do and do not prove.

5. **~35% of human commits (152 / 440) fall in Mon–Fri 09:00–17:59.** These are not automatically "on RBC time" — lunch breaks, PTO, statutory holidays, flex-time arrangements, and bot-assisted merges where Ryan only pushed the commit during business hours all fall into this bucket. Per-commit classification against Ryan's RBC calendar / PTO log is in scope for later tasks if counsel requests it.

6. **Multiple historical git identities.** Four pre-mailmap identities resolve to one natural person (see Section 6). A forensic tool that does not honour `.mailmap` will see the four identities; counsel should flag mailmap-aware processing to any third-party forensics vendor engaged.

7. **63 branches (15 local + 48 remote).** Substantial work-in-progress state. Any discovery exercise or assignment inventory will need to cover all branches, not just the default branch. All quantitative figures in this appendix use `git log --all` and therefore include branch-only commits.

8. **No evidence of history rewriting.** No `git filter-branch`, `git filter-repo`, force-push to main/master, or rebase-that-drops-commits appears in the reflog-accessible history. The `.mailmap` is additive and non-destructive.

9. **Repository is hosted on public GitHub (`ryanktomegah/PRKT2026`).** All commits are visible to GitHub. Repository visibility (public vs. private) and any prior-art / novelty implications of public posting are distinct from the IP-timing question and are addressed separately in the patent-strategy workstream.

10. **Codebase references canonical business constants (fee floors, SLO thresholds, BIC-based jurisdiction logic) that encode design decisions made during the audit period.** Counsel may wish to cross-reference the EPIGNOSIS architecture review decisions (recorded in `/CLAUDE.md` and `docs/legal/decisions/`) when assessing which design elements were conceived when.

---

## Methodology (summary)

- Raw data: `git log --all --use-mailmap --pretty='%H|%ai|%aN|%aE|%s'` piped to `commit-timeline.csv`. Field separator `|` verified unused in subjects and author strings.
- Business hours: `09:00 <= hour < 18:00` in author local timezone; a commit at exactly 18:00 counts as evening/off-hours.
- Day-of-week: Darwin `date -jf "%Y-%m-%d" YYYY-MM-DD +%u` (ISO: Mon=1 … Sun=7); weekend = `dow >= 6`. Spot-checked against calendar (2026-04-17 = Fri = 5; 2026-04-18 = Sat = 6).
- Bot filter: author name match on `copilot-swe-agent[bot]`, `Claude` (email `noreply@anthropic.com`), `github-actions[bot]`, and `git stash`.
- Mailmap: `.mailmap` at repo root, loaded by the `--use-mailmap` flag.
- Full regeneration recipe: see `commit-timeline-summary.md` methodology section.

All numerical claims in this appendix are reproducible from the commands above applied to the repository at or after commit `153e398`.
