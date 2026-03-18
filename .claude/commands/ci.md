---
description: Check GitHub Actions CI status for the LIP repo. Usage: /ci [watch|logs|<run-id>]
argument-hint: "[watch|logs|<run-id>]"
allowed-tools: Bash
---

Check GitHub Actions CI status for `ryanktomegah/PRKT2026` using the `gh` CLI.

Interpret `$ARGUMENTS`:

| Argument | Action |
|---|---|
| empty | `gh run list --repo ryanktomegah/PRKT2026 --limit 5` — show last 5 runs with status |
| `watch` | `gh run list --repo ryanktomegah/PRKT2026 --limit 1` then `gh run watch <latest-run-id>` |
| `logs` | Get the latest failed run ID and show its logs: `gh run view <id> --log-failed` |
| a numeric run ID | `gh run view $ARGUMENTS --log-failed --repo ryanktomegah/PRKT2026` |

If the latest run failed, automatically fetch its failed logs and summarise what broke and why. Cross-reference with local test results if relevant.

If `gh` returns an auth error, remind the user: `gh auth login --with-token <<< "ghp_..."` with a token scoped to `repo + workflow + read:org`.
