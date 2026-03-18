#!/usr/bin/env python3
"""
check_failopen.py
Verifies EPG-27: C6 unavailability should fail-closed, not fail-open.

Exit 0 = EPG-27 fixed — `c6_result is None` no longer defaults to True
Exit 1 = EPG-27 still present — fail-open default remains
"""
import sys
import re
from pathlib import Path

PIPELINE_PATH = Path("lip/pipeline.py")


def main():
    if not PIPELINE_PATH.exists():
        print(f"ERROR: {PIPELINE_PATH} not found. Run from repo root.")
        sys.exit(2)

    source = PIPELINE_PATH.read_text()
    lines  = source.splitlines()

    print("=== EPG-27: AML fail-open default check ===")

    # The specific fail-open pattern: `c6_result is not None else True`
    fail_open = re.search(
        r'bool\s*\(\s*c6_result\.passed\s*\)\s*if\s*c6_result\s*is\s*not\s*None\s*else\s*True',
        source,
    )
    if fail_open:
        line_num = source[:fail_open.start()].count('\n') + 1
        print(f"FAIL — fail-open pattern still present at pipeline.py:{line_num}")
        print(f"       Line: {lines[line_num - 1].strip()}")
        print("       EPG-27 is NOT fixed.")
        sys.exit(1)

    # Confirm there's a fail-closed path instead
    fail_closed = re.search(
        r'(AML_CHECK_UNAVAILABLE|c6_result\s+is\s+None)',
        source,
    )
    if not fail_closed:
        print("WARNING — fail-open removed but no AML_CHECK_UNAVAILABLE outcome found.")
        print("          Verify the replacement logic is correct before marking DONE.")
        sys.exit(1)

    line_num = source[:fail_closed.start()].count('\n') + 1
    print(f"PASS — No fail-open default found. Fail-closed path at pipeline.py:{line_num}")
    print("EPG-27 fix verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
