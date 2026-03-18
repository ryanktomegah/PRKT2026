#!/usr/bin/env python3
"""
check_sanctions_config.py
Verifies EPG-24: entity_name_resolver is not optional (must not default to None).

Exit 0 = EPG-24 fixed — resolver is required at construction time
Exit 1 = EPG-24 still present — resolver defaults to None
"""
import sys
import re
from pathlib import Path

AML_CHECKER_PATH = Path("lip/c6_aml_velocity/aml_checker.py")


def main():
    if not AML_CHECKER_PATH.exists():
        print(f"ERROR: {AML_CHECKER_PATH} not found. Run from repo root.")
        sys.exit(2)

    source = AML_CHECKER_PATH.read_text()

    print("=== EPG-24: Sanctions resolver configuration check ===")

    # Check 1: Does the constructor still have entity_name_resolver=None?
    fail_open_pattern = re.search(
        r'def __init__\s*\([^)]*entity_name_resolver\s*=\s*None',
        source,
        re.DOTALL,
    )
    if fail_open_pattern:
        line_num = source[:fail_open_pattern.start()].count('\n') + 1
        print(f"FAIL — entity_name_resolver=None default still present at line ~{line_num}")
        print("       Sanctions screening is disabled by default (EPG-24 not fixed).")
        sys.exit(1)

    # Check 2: Is there a ConfigurationError or similar guard when resolver is None?
    has_guard = bool(re.search(
        r'(ConfigurationError|raise\s+\w*Error|raise\s+ValueError)[^\n]*resolver',
        source,
    ))

    # Check 3: Does the fallback still use entity_id as the name?
    has_fallback = bool(re.search(
        r'if self\._resolve_name else entity_id',
        source,
    ))

    if has_fallback:
        print("FAIL — Fallback `else entity_id` still present — BIC codes still used as names.")
        sys.exit(1)

    print("PASS — entity_name_resolver is no longer optional with a None default.")
    if has_guard:
        print("       ConfigurationError guard detected.")
    print("EPG-24 fix verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
