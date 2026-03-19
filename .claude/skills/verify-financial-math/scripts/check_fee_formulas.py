#!/usr/bin/env python3
"""check_fee_formulas.py — Static scan for flat fee formula violations.

Detects: `principal * (fee_bps / 10_000)` without a subsequent `* (days / 365)` factor.
This is the QUANT-canonical formula guard: fee.py C2 Spec Section 9.

Usage:
    python3 check_fee_formulas.py [path/to/file.py | all]
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches flat fee: anything that computes (X * fee_bps / 10_000) or
# (X * (fee_bps / 10_000)) without a trailing * (.../ 365)
_FLAT_FEE_LINE = re.compile(
    r".*fee_bps\s*/\s*10_?000.*",
    re.IGNORECASE,
)

_ANNUALIZED_FACTOR = re.compile(
    r"/\s*365",
)

# settlement_amount_usd = principal + fee_term (without annualization)
_SETTLEMENT_FLAT = re.compile(
    r"settlement_amount_usd\s*=.*fee_bps\s*/\s*10_?000",
)

_EXPECTED_FLAT = re.compile(
    r"expected\s*=.*fee_bps\s*/\s*10_?000",
)


def _check_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, line, reason) violations."""
    violations = []
    lines = path.read_text().splitlines()

    in_docstring = False
    docstring_char = None

    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Track triple-quoted strings (docstrings / multiline strings) — skip their contents
        for q in ('"""', "'''"):
            if not in_docstring and line.count(q) >= 1:
                # Opening a docstring
                if line.count(q) == 1 or (line.count(q) == 2 and line.startswith(q) and line.endswith(q) and len(line) > 6):
                    in_docstring = True
                    docstring_char = q
                    break
                # Single-line docstring (opened and closed on same line) — skip
                # e.g. """short docstring"""
            elif in_docstring and q == docstring_char and q in line:
                in_docstring = False
                docstring_char = None
                break
        if in_docstring:
            continue

        # Skip comments
        if line.startswith("#"):
            continue

        # Skip the fee.py formula definition itself (it's correct)
        if "compute_loan_fee" in line or "FEE_FLOOR" in line:
            continue

        # Skip standalone rate extraction (rate = fee_bps / 10_000)
        # These are OK as intermediate variables if days factor follows
        if re.match(r"^\w+\s*=\s*[\w.]+\s*/\s*10_?000", line) and "fee_bps" not in line:
            continue

        # Check: settlement_amount or expected built with flat fee
        if _SETTLEMENT_FLAT.search(line) or _EXPECTED_FLAT.search(line):
            if not _ANNUALIZED_FACTOR.search(line):
                violations.append((
                    i,
                    raw_line,
                    "Flat fee in settlement_amount — missing × (days/365)",
                ))
            continue

        # Check: general fee_bps / 10_000 usage in an assignment
        if _FLAT_FEE_LINE.search(line) and "=" in line:
            # Check that the line (or it's being assigned to something that
            # later gets ×days) contains the annualized factor
            if not _ANNUALIZED_FACTOR.search(line):
                # Look at the next 3 lines for the days factor (multi-line expressions)
                context_window = "\n".join(lines[i - 1 : min(i + 3, len(lines))])
                if not _ANNUALIZED_FACTOR.search(context_window):
                    violations.append((
                        i,
                        raw_line,
                        "fee_bps / 10_000 without annualization (days/365) in context",
                    ))

    return violations


def _collect_py_files(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*.py")
        if ".venv" not in str(p)
        and "__pycache__" not in str(p)
        and ".claude" not in str(p)
        and "/tests/" not in str(p)  # test files reference wrong formula as counter-examples
    ]


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    root = Path(__file__).parent.parent.parent.parent.parent  # repo root (.claude/skills/name/scripts/)

    if arg == "all":
        files = _collect_py_files(root)
    else:
        target = Path(arg)
        if not target.is_absolute():
            target = root / target
        if not target.exists():
            print(f"ERROR: {target} not found")
            return 2
        files = [target]

    total_violations = 0
    for path in sorted(files):
        violations = _check_file(path)
        if violations:
            rel = path.relative_to(root)
            for lineno, line, reason in violations:
                print(f"FAIL  {rel}:{lineno}  — {reason}")
                print(f"      {line.strip()}")
                print(f"      FIX: add * ({{}}_days / 365) — see fee.py:136 for canonical form")
                print()
            total_violations += len(violations)

    if total_violations == 0:
        print(f"PASS  fee formula check — {len(files)} file(s) scanned, 0 violations")
        return 0
    else:
        print(f"FAIL  {total_violations} violation(s) found across {len(files)} file(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
