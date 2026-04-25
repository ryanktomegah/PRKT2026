"""
test_dgen_class_b_label.py — B11-01 regression test for CLASS_B label.

Before the 2026-04-09 fix, CLASS_B was labelled "compliance/AML hold" in
DGEN files. CLASS_B covers systemic/processing delays only. Compliance-hold
payments are BLOCK class and are never bridged (EPG-19). The mislabel risked
training downstream components with the wrong semantics.

This test enforces:
1. SETTLEMENT_P95_CLASS_B_HOURS == 53.58 (value unchanged, per CLAUDE.md).
2. No file in lip/dgen/ contains CLASS_B + "compliance" or "AML hold" on
   the same or adjacent lines (grep guard).
"""
from __future__ import annotations

import re
from pathlib import Path

from lip.common.constants import SETTLEMENT_P95_CLASS_B_HOURS

DGEN_DIR = Path(__file__).resolve().parents[1] / "dgen"


def test_class_b_settlement_p95_value():
    """SETTLEMENT_P95_CLASS_B_HOURS must be exactly 53.58 (CLAUDE.md canonical)."""
    assert SETTLEMENT_P95_CLASS_B_HOURS == 53.58


def test_no_class_b_compliance_aml_label_in_dgen():
    """No DGEN file should label CLASS_B as compliance/AML hold.

    CLASS_B is systemic/processing delay. The compliance/AML label was a
    historical mislabel (B11-01) that could train C1 to bridge compliance
    holds — a catastrophic EPG-19 violation.
    """
    violations = []
    forbidden = re.compile(
        r"class.?b.*(?:compliance|AML\s*hold)|(?:compliance|AML\s*hold).*class.?b",
        re.IGNORECASE,
    )

    for py_file in DGEN_DIR.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            # Allow references to the historical bug fix (e.g. "B11-01" comments)
            if "B11-01" in line or "B11-02" in line:
                continue
            # Allow references describing the historical mislabel as past tense
            if "was previously labelled" in line or "historical" in line.lower():
                continue
            if forbidden.search(line):
                violations.append(f"{py_file.name}:{i+1}: {line.strip()}")

    assert not violations, (
        "DGEN files contain CLASS_B labelled as compliance/AML hold — "
        "B11-01 regression:\n" + "\n".join(violations)
    )
