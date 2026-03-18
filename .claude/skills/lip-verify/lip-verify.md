---
description: Verify LIP EPG fixes are correct in code — programmatic assertions against specific EPG behaviors. Run after each fix to confirm before marking DONE. Use /lip-verify [all | epg09 | epg24 | epg27 | aml | pipeline]
argument-hint: "[all | epg09 | epg24 | epg27 | aml | pipeline | <EPG-ID>]"
allowed-tools: Bash, Read, Grep
---

Run verification scripts that check EPG-specific behaviors in the actual source code.
These are NOT test runners — they are structural assertions that parse the source and
verify specific properties that the test suite may not cover.

Run from the repo root: `PYTHONPATH=. python .claude/skills/lip-verify/scripts/<script>.py`

---

## Verification map

| Argument | Script | EPG issues checked |
|----------|--------|--------------------|
| `epg09` or `pipeline` | `check_pipeline_coverage.py` | EPG-09, EPG-10 |
| `epg24` or `aml` | `check_sanctions_config.py` | EPG-24 |
| `epg27` | `check_failopen.py` | EPG-27 |
| `epg27b` | `check_c6_failclosed.py` | EPG-27 (runtime path) |
| `all` | run all scripts above | All of the above |

---

## What to do when a check fails

1. Read the failing script output carefully — it will print the exact file:line causing the failure
2. Read that file at that line before attempting any fix
3. Fix the source, re-run the check, confirm PASS before marking the EPG as DONE in `/epg done`

## What these checks do NOT cover

- Runtime behavior — these are static source assertions. An integration test in the
  pytest suite is still required to cover runtime behavior.
- C6 infrastructure availability (Redis, sanctions API) — those require live tests
- Human review re-entry path (EPG-26) — this is a structural design gap that requires
  a new component; a verification script cannot exist until the component is built

## After all checks pass

Run the fast test suite to confirm no regressions: `/test fast`
Then run the C7-specific suite to confirm gate behavior: `/test c7`
