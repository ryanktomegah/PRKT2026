# Commit Timeline Summary — IP & Timing Audit

**Generated:** 2026-04-17
**Author:** Pre-lawyer review, Task 1.2
**Source data:** `commit-timeline.csv` (this directory) — `git log --all` of the PRKT2026 repo

---

## 1. Scope

- **Total commits (all branches, all time):** 551
- **First commit in repo:** 2026-02-27 09:16:30 -0800
- **Most recent commit:** 2026-04-17 21:31:42 -0700
- **RBC employment start date (IP-clause trigger):** 2026-01-12
- **Commits authored after RBC start:** 551 (100% — no commits exist before 2026-01-12)
- **Branches present locally + remote:** 63 (15 local + 48 remote)
- **Unique branch names (dedup local/remote):** 50

All commit history of this repository was authored during Ryan's RBC employment. There is no pre-employment code baseline in this repo.

---

## 2. Author breakdown

| Author name (git) | Email | Commits | % of total |
|---|---|---:|---:|
| Tomegah Ryan | tomegah@Tomegahs-MacBook-Air.local | 312 | 56.6% |
| Ryan | naumryan66@gmail.com | 73 | 13.2% |
| copilot-swe-agent[bot] | 198982749+Copilot@users.noreply.github.com | 64 | 11.6% |
| ryanktomegah / YESHA | ryanktomegah@gmail.com | 52 | 9.4% |
| Claude | noreply@anthropic.com | 43 | 7.8% |
| github-actions[bot] | 41898282+github-actions[bot]@users.noreply.github.com | 4 | 0.7% |
| git stash | git@stash | 3 | 0.5% |
| **Total** | | **551** | **99.8%** |

(Percentage column sums to 99.8% due to per-row rounding; row-count column sums to 551/551 (100%).)

### Identity consolidation

Three of the above identities are the **same person (Ryan Tomegah)** committing from different machines / accounts:

1. `tomegah@Tomegahs-MacBook-Air.local` ("Tomegah Ryan") — laptop default git identity
2. `naumryan66@gmail.com` ("Ryan") — personal Gmail
3. `ryanktomegah@gmail.com` ("ryanktomegah" / "YESHA") — primary personal Gmail (matches user email on file)

Combined, these three identities account for **437 / 551 = 79.3%** of all commits (all human-authored work).

The remaining 114 commits (20.7%) are **bots**:
- Copilot SWE agent: 64
- Claude Code (noreply@anthropic.com): 43
- GitHub Actions: 4
- `git stash` (stash-restored commits, not a real identity): 3

**Consolidation plan:** Task 1.3 will add a `.mailmap` file mapping all three Ryan identities to a single canonical `Ryan Tomegah <ryanktomegah@gmail.com>` entry so that downstream tooling (`git log`, `git shortlog`, `blame`) and forensic reporting present a single human author.

---

## 3. Monthly volume

Commits per calendar month, all authors, since RBC start (2026-01-12):

| Month | Commits | Bar |
|---|---:|---|
| 2026-02 (Feb) |  19 | ### |
| 2026-03 (Mar) | 311 | ############################################### |
| 2026-04 (Apr, 1–17) | 221 | ################################ |

### Weekly volume (ISO weeks)

| ISO week | Dates | Commits | Bar |
|---|---|---:|---|
| 2026-W09 | Feb 23 – Mar 01 |  19 | ### |
| 2026-W10 | Mar 02 – Mar 08 |  58 | ############ |
| 2026-W11 | Mar 09 – Mar 15 |  77 | ############### |
| 2026-W12 | Mar 16 – Mar 22 |  84 | ################# |
| 2026-W13 | Mar 23 – Mar 29 |  67 | ############# |
| 2026-W14 | Mar 30 – Apr 05 |  76 | ############### |
| 2026-W15 | Apr 06 – Apr 12 | 123 | ######################## |
| 2026-W16 | Apr 13 – Apr 17 |  47 | ######### (partial week, 5 days) |

Velocity peaked in W15 (week of Apr 6, 123 commits) — this coincides with the P5 CBDC normalizer and P12 federated-learning ships.

---

## 4. Off-hours activity

"Off-hours" is defined here as any commit authored **outside Monday–Friday 09:00–17:59 local time** (i.e., weekends OR weekday evenings/early mornings). All timestamps use the author's local timezone as recorded in git (`%ai`), which for Ryan is `America/Los_Angeles` (PST/PDT).

### All commits (including bots)

| Time window | Commits | % of 551 |
|---|---:|---:|
| Weekday business hours (Mon–Fri 09:00–17:59) | 175 | 31.8% |
| Weekday early morning (Mon–Fri, before 9am) |  93 | 16.9% |
| Weekday evening (Mon–Fri, 6pm onward) | 118 | 21.4% |
| Weekend (Sat/Sun, any hour) | 165 | 29.9% |
| **Off-hours total** | **376** | **68.2%** |

### Human-authored commits only (bots excluded)

This is the figure that matters for the IP-timing argument — "was this work done on personal time?"

| Bucket | Commits | % of 437 human commits |
|---|---:|---:|
| Business hours (Mon–Fri 09:00–17:59) | 152 | 34.8% |
| **Off-hours (evenings + weekends + early morning)** | **285** | **65.2%** |

Two-thirds of Ryan's commits were authored outside business hours. The raw list of the 376 off-hours commits (including bot commits that happened at off-hours times) is in `commits-off-hours.txt`.

### Caveat — business-hours commits

152 human commits (34.8%) fall inside Mon–Fri 09:00–17:59. Not all of these are automatically "done on RBC time":
- Lunch breaks, PTO days, and statutory holidays fall inside this window
- Ryan is a credit-management Resolution Officer (post-front-office) — some weeks may have flex hours
- Some timestamps may be Copilot/Claude bot co-authored work where Ryan only pushed the commit outside work hours (to be investigated in Task 1.4, commit forensics)

Task 1.4 will cross-reference each business-hours commit against Ryan's RBC calendar / PTO log to classify them individually. For now, note that the **default assumption for a lawyer-facing narrative is that ~65% of work is unambiguously off-hours**, and the remaining ~35% requires case-by-case timestamp-vs-calendar reconciliation.

---

## 5. Key takeaways for counsel

1. **No pre-employment code baseline exists in this repo.** All 551 commits occurred after the RBC IP clause attached on 2026-01-12. No pre-2026-01-12 commits exist in this repo. Pre-employment conception evidence, if any, would need to come from sources outside this git history.
2. **The repo is a solo-founder project with bot assistance.** 437 of 551 commits (79.3%) trace to Ryan across three git identities; the remaining 114 are AI-assistant or CI bot commits. No third-party human contributors.
3. **65% of human commits are off-hours.** Primary activity windows are weekday evenings and weekends — consistent with the "built on personal time, on personal equipment" IP-defense framing.
4. **Three git identities need consolidation (Task 1.3).** Before any external disclosure, a `.mailmap` will collapse these into a single canonical Ryan Tomegah identity.
5. **~35% of human commits (152/437) fall within Mon–Fri 09:00–17:59 and will be individually classified in Task 1.4.** These are not automatically a problem (lunch, PTO, flex, bot-assisted merges) but need individual treatment before a clean IP-timing narrative can be given to counsel.

---

## Methodology notes

- CSV uses `|` as field separator. Verified zero occurrences of `|` in commit subjects, author names, or emails before generating.
- Business hours defined as 09:00 <= hour_of_day < 18:00 in the author's local timezone — a commit at 6:00pm is classified as evening/off-hours.
- Off-hours calculation uses the `-jf` form of Darwin `date` for day-of-week math (ISO: Mon=1 … Sun=7); weekend = `dow >= 6`. Cross-checked against known dates (2026-04-17 = Fri = 5; 2026-04-18 = Sat = 6; 2026-04-19 = Sun = 7).
- All counts include every branch (`--all`), not just the default branch.
- Timestamps are author-date (`%ai`), which is the time Ryan wrote the commit, not committer-date (which can drift on rebase).

To regenerate the CSV from the repo, run:

```
git log --all --pretty='%H|%ai|%an|%ae|%s' > commit-timeline.csv
```
