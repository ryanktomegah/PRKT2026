# LIP Lint & Type Check

Run linting and type checking across the entire LIP codebase.

## Execution Protocol

1. Run `ruff check lip/` — report any violations
2. Run `mypy lip/` — report type errors
3. If violations found: fix them automatically where safe, explain what was changed
4. Re-run checks to confirm clean

## Rules
- ruff config: line-length=100, target=py310, select E/F/W/I, ignore E501
- mypy config: python 3.10, strict=false, ignore_missing_imports=true
- NEVER commit with ruff errors — this blocks CI
- Auto-fixable issues (import sorting, unused imports): fix silently
- Non-trivial issues: explain the fix before applying
- Run from repo root: `/Users/halil/PRKT2026`
