---
description: Check that a code change has all required agent sign-offs before committing. Use /sign-off <file-or-EPG-ID> to get the sign-off checklist and verify each agent's domain requirements are met.
argument-hint: "<file-path | EPG-ID>"
allowed-tools: Read, Grep, Glob, Bash
---

Before any commit that touches compliance, security, or financial math code, the relevant
agents must review and agree. This skill checks which agents are required and walks through
each one's domain-specific checklist.

Read `authority_matrix.md` in this folder to determine which agents are required for the
given file or EPG issue. Then, for each required agent, read their file in `.claude/agents/`
and apply their domain checklist.

---

## How to use

**`/sign-off <file-path>`** — Given a file path, determine which agents must review it,
apply their checklists, report any violations.

**`/sign-off <EPG-ID>`** — Given an EPG ID, look it up in `../epg/state.json` to find
the owner agents, then apply their checklists to the files that need to change.

---

## Reporting format

For each required agent:

```
### CIPHER sign-off
Required because: change touches aml_checker.py (AML gate)
Checklist:
  ✅ No AML typology patterns committed to version control
  ✅ entity_name_resolver is not optional / defaults are fail-closed
  ⚠️  Jaccard threshold at 0.8 — still misses one-word extensions of sanctioned names
  ✅ No c6_corpus_*.json files staged
Decision: APPROVED with note on threshold
```

---

## Final output

Print a summary:
- APPROVED: all required agents cleared
- BLOCKED: one or more agents have open violations — list them
- Do not suggest committing if any agent is BLOCKED
