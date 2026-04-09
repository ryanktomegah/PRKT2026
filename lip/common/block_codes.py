"""
block_codes.py — Authoritative BLOCK-class rejection codes (single source of truth).

B6-01 / B11-02 / B13-02: Before this module existed, the BLOCK-class rejection
code list was hand-maintained in at least four independent locations across
three languages (Python event_normalizer, Python telemetry_collector, Rust
taxonomy.rs, Go normalizer.go), plus a wholly-incorrect copy in DGEN's
c1_generator.py that put EPG-19 compliance-hold codes in CLASS_B/C. A new
SWIFT rejection code added to one site but not the others created a silent
gap in EPG-19 enforcement.

This module reads ``lip/common/block_codes.json`` at import time and exposes:

* ``EPG19_COMPLIANCE_HOLD_CODES`` — the 8-code compliance-hold subset
  (DNOR, CNOR, RR01-RR04, AG01, LEGL). Defense-in-depth: blocked at
  Layer 1 (pipeline short-circuit) and Layer 2 (C7 gate). REX final
  authority — never bridgeable.
* ``DISPUTE_FRAUD_BLOCK_CODES`` — the 4-code dispute/fraud subset
  (DISP, DUPL, FRAD, FRAU). Hard-blocked before C1 in pipeline.py.
* ``ALL_BLOCK_CODES`` — union of the two (12 codes), suitable for any
  callsite that needs the full BLOCK class.

The Rust crate (``lip/c3/rust_state_machine/src/taxonomy.rs``) embeds the
same JSON via ``include_str!`` at compile time. The cross-language drift
regression test (``lip/tests/test_block_code_drift.py``, B13-02) asserts
all consumers stay in sync with the JSON ground truth.

CIPHER note: this file contains ISO 20022 rejection code identifiers only.
No AML typology patterns, no narrative descriptions, no enumeration of
BLOCK behaviour rules — those would violate the EPG-21 patent-language
scrub. Code names alone are publicly documented in the ISO 20022
specification and carry no adversarial value.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import FrozenSet

_JSON_PATH = Path(__file__).resolve().parent / "block_codes.json"


def _load() -> dict:
    """Read block_codes.json from disk. Fail-closed on any error."""
    try:
        with _JSON_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to load BLOCK-codes ground truth at {_JSON_PATH}: {exc}. "
            "This file is required for EPG-19 enforcement; refusing to start."
        ) from exc


_DATA = _load()

EPG19_COMPLIANCE_HOLD_CODES: FrozenSet[str] = frozenset(_DATA["epg19_compliance_hold"])
"""8-code EPG-19 compliance-hold set — never bridgeable. REX final authority."""

DISPUTE_FRAUD_BLOCK_CODES: FrozenSet[str] = frozenset(_DATA["dispute_fraud_block"])
"""4-code dispute/fraud set — hard-blocked before C1."""

ALL_BLOCK_CODES: FrozenSet[str] = EPG19_COMPLIANCE_HOLD_CODES | DISPUTE_FRAUD_BLOCK_CODES
"""Union of the two sets — full BLOCK class (12 codes)."""


# Sanity invariants checked at import time. If these fire, the JSON has been
# tampered with or the LIP defense-in-depth model is misconfigured.
if len(EPG19_COMPLIANCE_HOLD_CODES) != 8:
    raise RuntimeError(
        f"EPG-19 compliance-hold set must have exactly 8 codes "
        f"(got {len(EPG19_COMPLIANCE_HOLD_CODES)}); check block_codes.json"
    )
if len(DISPUTE_FRAUD_BLOCK_CODES) != 4:
    raise RuntimeError(
        f"Dispute/fraud BLOCK set must have exactly 4 codes "
        f"(got {len(DISPUTE_FRAUD_BLOCK_CODES)}); check block_codes.json"
    )
if EPG19_COMPLIANCE_HOLD_CODES & DISPUTE_FRAUD_BLOCK_CODES:
    raise RuntimeError(
        "EPG-19 and dispute/fraud sets must be disjoint; check block_codes.json"
    )


__all__ = [
    "EPG19_COMPLIANCE_HOLD_CODES",
    "DISPUTE_FRAUD_BLOCK_CODES",
    "ALL_BLOCK_CODES",
]
