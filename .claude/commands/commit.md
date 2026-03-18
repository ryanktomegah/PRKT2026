---
description: Lint → test (fast) → commit with a well-formed message. Usage: /commit ["message"] — runs ruff and fast tests first, refuses to commit if either fails.
argument-hint: "[commit message]"
allowed-tools: Bash, Edit, Read, Glob, Grep
---

Execute the LIP pre-commit checklist in order. Work from `/Users/tomegah/Documents/PRKT2026` with `PYTHONPATH=.` and `~/.pyenv/versions/3.14.3/bin/python3`.

**Step 1 — Lint:**
Run `python3 -m ruff check lip/`. If errors exist, fix them (auto-fix first, then manual Edit). Re-run until zero errors. Do NOT proceed with a dirty lint.

**Step 2 — Fast tests:**
Run `python -m pytest lip/tests/ -m "not slow" --ignore=lip/tests/test_e2e_live.py -q`. If any tests fail (excluding `test_slo_p99_94ms` which is a known flaky timing test), diagnose and fix before proceeding. Do NOT commit broken tests.

**Step 3 — Stage and commit:**
- Run `git status` to see what's staged/unstaged.
- NEVER stage or commit: `artifacts/`, `c6_corpus_*.json`, `.env`, any file with credentials.
- Stage relevant files explicitly by name (never `git add -A` blindly).
- If `$ARGUMENTS` is provided, use it as the commit message. Otherwise, write a message from the diff that is concise, imperative, and explains *why* not just *what*.
- Always append: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`
- Pass the message via HEREDOC to avoid shell escaping issues.

**Step 4 — Confirm:**
Run `git status` after commit to confirm the working tree is clean.

If any step fails, stop and report clearly. Never use `--no-verify`.
