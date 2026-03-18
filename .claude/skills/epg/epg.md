---
description: LIP EPG issue tracker — list open issues, start a fix, mark complete with commit hash, check sign-offs. Use when fixing, verifying, or reviewing progress on Epignosis Architecture Review issues.
argument-hint: "[list | fix <EPG-ID> | done <EPG-ID> <commit> | verify | next]"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

You are coordinating the team's work through the EPG issue register for the LIP platform.
State is persisted in `state.json` in this skill folder — read it at the start of every invocation
and write it back when status changes. Never infer status from git history alone — the state
file is the source of truth for in-progress / done tracking.

Also read `gotchas.md` in this folder before making any code change recommendation.

---

## Commands

### `/epg list`
Read `state.json` and print a formatted table grouped by tier:
- Tier 0 (hotfixes), Tier 1 (pre-pilot), Tier 2 (pre-commercial), Tier 3 (model governance), Tier 4 (strategic)
- Show: ID | Severity | Owner | Status | Commit (if done)
- Highlight any issue marked `IN_PROGRESS`
- Count: X done, Y in progress, Z open total

### `/epg next`
Read `state.json`, find the highest-priority OPEN issue (lowest tier number, then lowest EPG
number within that tier), print a full work brief:
- Issue ID, title, severity, owner agents
- The exact code location(s) that need to change (file:line)
- Required sign-offs before committing
- Which `lip-verify` check to run after fixing

### `/epg fix <EPG-ID>`
Mark the issue as `IN_PROGRESS` in `state.json`. Print:
- Full description of what needs to change and why (read EPIGNOSIS_ARCHITECTURE_REVIEW.md for the section)
- Exact files and lines to edit
- Sign-off requirements (from authority matrix in `../sign-off/authority_matrix.md`)
- The verification command to run after fixing
Then read the relevant source files and proceed to implement the fix.

### `/epg done <EPG-ID> <commit>`
Mark the issue as `DONE` with the given commit hash in `state.json`.
Run the corresponding verification script from `../lip-verify/scripts/` if one exists.
If verification fails, revert the status to `IN_PROGRESS` and report the failure.

### `/epg verify`
Run ALL verification scripts in `../lip-verify/scripts/` that correspond to DONE issues.
Report pass/fail per issue. Any issue whose verification script fails should be reverted to `IN_PROGRESS`.

---

## Sign-off rules (enforced before marking DONE)

| Change type | Required sign-offs |
|-------------|-------------------|
| Any change to `pipeline.py` decision gates | NOVA |
| Any change to `_COMPLIANCE_HOLD_CODES` or AML blocking logic | CIPHER + REX |
| Any change to `rejection_taxonomy.yaml` | NOVA + REX + QUANT |
| Any change to fee math or loan minimums in `constants.py` | QUANT |
| Any change to `aml_checker.py`, `sanctions.py`, `velocity.py` | CIPHER |
| Any change to `human_override.py` or review routing | REX + NOVA |
| Any change to `DecisionLogEntry` schema | REX |

Sign-off means: the relevant agent file in `.claude/agents/` was consulted and agreed.
Record which agents were consulted in the `state.json` `signoffs` field for the issue.

---

## Reading the state file

`state.json` structure:
```json
{
  "EPG-09": {
    "status": "OPEN",
    "tier": 0,
    "severity": "CRITICAL",
    "owner": ["NOVA"],
    "commit": null,
    "signoffs": [],
    "notes": ""
  }
}
```

Valid statuses: `OPEN`, `IN_PROGRESS`, `DONE`, `BLOCKED`, `WONT_FIX`
