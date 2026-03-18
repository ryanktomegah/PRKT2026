---
description: Analyse the current state of LIP platform gaps — what's open, what's closed, what's next. Usage: /gap [list|<gap-id>|new <description>]
argument-hint: "[list|<GAP-id>|new <description>]"
allowed-tools: Read, Grep, Bash
---

Analyse LIP platform gaps using PROGRESS.md and the codebase as sources of truth.

Interpret `$ARGUMENTS`:

**`list` or empty:**
Read `PROGRESS.md` and grep for any `GAP-` references across the codebase. Produce a table:
- All known GAPs with status (COMPLETE / OPEN / IN PROGRESS)
- Group by component (C1–C8, infra, data)
- Highlight any that are open with no owner

**`<GAP-id>` (e.g. `GAP-05`):**
Search `PROGRESS.md` and all source files for references to that GAP. Report: what the gap was, what was done to close it, which files were changed, and whether tests cover it.

**`new <description>`:**
Given a description of a new gap, do the following:
1. Assign the next sequential GAP number (find the highest existing number first)
2. Identify which component(s) it belongs to
3. Read the relevant source files to understand the current state
4. Write a precise gap statement: what is missing, what the correct behaviour should be, which files need to change
5. Add it to PROGRESS.md in the appropriate session section
6. Suggest an implementation approach

Always ground gap analysis in actual code — read the source, don't rely on PROGRESS.md descriptions alone.
