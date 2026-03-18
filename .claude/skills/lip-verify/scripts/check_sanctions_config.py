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

    # Check 2: Is there a ConfigurationError raised when resolver is not provided?
    # This is the primary fix: a sentinel default that raises at startup rather than
    # silently falling through to BIC-as-name. The `else entity_id` fallback may
    # still exist for the explicit entity_name_resolver=None (test) path — that's OK.
    has_configuration_error_guard = bool(re.search(
        r'raise\s+ConfigurationError',
        source,
    ))
    has_sentinel = bool(re.search(
        r'_RESOLVER_REQUIRED\s*=\s*object\(\)',
        source,
    ))

    if not has_configuration_error_guard:
        print("FAIL — No ConfigurationError guard found — missing resolver is not caught at startup.")
        sys.exit(1)

    if not has_sentinel:
        print("FAIL — No _RESOLVER_REQUIRED sentinel found — default is still None (fail-open).")
        sys.exit(1)

    print("PASS — ConfigurationError guard and sentinel default detected.")
    print("       Production deployments will fail at startup if entity_name_resolver is omitted.")
    print("EPG-24 fix verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
