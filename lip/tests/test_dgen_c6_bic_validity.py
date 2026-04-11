"""
test_dgen_c6_bic_validity.py — B11-09 regression test.

Ensures every BIC used by the C6 synthetic corpus generator conforms to
ISO 9362 format (8 or 11 alphanumeric chars). Previously ``TRANSC000``
(9 chars) slipped through and would fail the C8 boot validator BIC regex
``^[A-Z0-9]{8}([A-Z0-9]{3})?$``.
"""
from __future__ import annotations

import re

from lip.dgen.c6_generator import _HIGH_RISK_JURISDICTIONS, _STANDARD_BICS

# Mirror of the authoritative BIC regex used by boot_validator.py:46.
_BIC_PATTERN = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")


def test_high_risk_jurisdictions_are_valid_bics():
    """B11-09: every high-risk BIC must be 8 or 11 chars, all uppercase alnum."""
    for bic in _HIGH_RISK_JURISDICTIONS:
        assert _BIC_PATTERN.match(bic), (
            f"High-risk jurisdiction BIC {bic!r} is not a valid 8/11-char BIC"
        )


def test_standard_bics_are_valid_bics():
    """Sanity check: the standard BIC pool also conforms."""
    for bic in _STANDARD_BICS:
        assert _BIC_PATTERN.match(bic), (
            f"Standard BIC {bic!r} is not a valid 8/11-char BIC"
        )


def test_no_nine_character_bics():
    """B11-09 specific guard: no 9-character strings sneak back in."""
    for bic in _HIGH_RISK_JURISDICTIONS + _STANDARD_BICS:
        assert len(bic) in (8, 11), (
            f"BIC {bic!r} has invalid length {len(bic)}; must be 8 or 11"
        )
