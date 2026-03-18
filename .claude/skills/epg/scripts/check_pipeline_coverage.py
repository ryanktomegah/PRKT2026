#!/usr/bin/env python3
"""
check_pipeline_coverage.py
Verifies that pipeline.py's DECLINE handler covers all C7 status codes that should block funding.
Run from repo root: python .claude/skills/epg/scripts/check_pipeline_coverage.py

Exit 0 = all required statuses are covered (EPG-09/10 fixed)
Exit 1 = one or more statuses are missing from the DECLINE handler
"""

import sys
import re
from pathlib import Path

PIPELINE_PATH = Path("lip/pipeline.py")
AGENT_PATH    = Path("lip/c7_execution_agent/agent.py")

# Status codes that must be in the main `if c7_status in (...)` economic-decline tuple
REQUIRED_IN_DECLINE_TUPLE = {
    "DECLINE",
    "BLOCK",
    "PENDING_HUMAN_REVIEW",
    "CURRENCY_NOT_SUPPORTED",
    "BORROWER_NOT_ENROLLED",
    "BELOW_MIN_LOAN_AMOUNT",           # EPG-10
    "BELOW_MIN_CASH_FEE",              # EPG-10
    "LOAN_AMOUNT_MISMATCH",            # EPG-10
}

# Status codes handled via their own separate equality check (distinct outcomes)
REQUIRED_SEPARATE_HANDLERS = {
    "COMPLIANCE_HOLD_BLOCKS_BRIDGE",   # EPG-09 — uses outcome="COMPLIANCE_HOLD"
}


def get_decline_handler_statuses(pipeline_text: str) -> set[str]:
    """Extract all string literals inside the `if c7_status in (...)` block."""
    match = re.search(
        r'if c7_status in \((.*?)\):',
        pipeline_text,
        re.DOTALL,
    )
    if not match:
        print("ERROR: Could not find `if c7_status in (` block in pipeline.py")
        sys.exit(2)
    block = match.group(1)
    return set(re.findall(r'"([^"]+)"', block))


def get_all_c7_statuses(agent_text: str) -> set[str]:
    """Extract all string literals returned as 'status' from agent.py."""
    return set(re.findall(r'status\s*=\s*"([A-Z_]+)"', agent_text))


def get_separate_handler_statuses(pipeline_text: str) -> set[str]:
    """Find status codes handled via their own equality check (not inside the tuple)."""
    return set(re.findall(r'c7_status\s*==\s*"([^"]+)"', pipeline_text))


def main():
    if not PIPELINE_PATH.exists():
        print(f"ERROR: {PIPELINE_PATH} not found. Run from repo root.")
        sys.exit(2)

    pipeline_text = PIPELINE_PATH.read_text()
    agent_text = AGENT_PATH.read_text() if AGENT_PATH.exists() else ""

    in_tuple   = get_decline_handler_statuses(pipeline_text)
    separate   = get_separate_handler_statuses(pipeline_text)
    c7_all     = get_all_c7_statuses(agent_text)

    missing_from_tuple    = REQUIRED_IN_DECLINE_TUPLE - in_tuple
    missing_separate      = REQUIRED_SEPARATE_HANDLERS - separate

    print("=== Pipeline DECLINE handler coverage check ===")
    print(f"In decline tuple:         {sorted(in_tuple)}")
    print(f"Separate equality checks: {sorted(separate)}")
    print(f"C7 statuses found:        {sorted(c7_all)}")
    print()

    failed = False
    if missing_from_tuple:
        print(f"FAIL — Missing from DECLINE tuple: {sorted(missing_from_tuple)}")
        failed = True
    if missing_separate:
        print(f"FAIL — Missing separate handler:   {sorted(missing_separate)}")
        failed = True

    if failed:
        print("EPG-09 / EPG-10 are NOT fixed.")
        sys.exit(1)
    else:
        print("PASS — All required statuses are handled.")
        print("EPG-09 / EPG-10 fix verified.")
        sys.exit(0)


if __name__ == "__main__":
    main()
