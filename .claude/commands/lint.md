---
description: Run ruff linter on the LIP codebase. Usage: /lint [fix]
argument-hint: "[fix]"
allowed-tools: Bash, Edit
---

Run `ruff check lip/` from `/Users/tomegah/Documents/PRKT2026` using `~/.pyenv/versions/3.14.3/bin/python3 -m ruff`.

If `$ARGUMENTS` is `fix`, run `ruff check lip/ --fix` first, then re-run `ruff check lip/` to confirm zero errors remain. For any errors that `--fix` cannot auto-resolve, read the offending file and fix them manually using Edit.

If no argument, just check and report.

**Goal is always zero errors.** Report the final count. If zero errors: confirm clean. If errors remain after fix attempt: show each one with the file path and line number, then fix them.

Never commit code with ruff errors.
