"""
governing_law.py — GAP-10: Governing-law mapping for cross-border bridge loans.

Maps the settlement jurisdiction to the contractual governing law required by
MRFA clause 4 for enforceability of cross-border bridge-loan agreements.

Supported jurisdictions → governing laws:
  FEDWIRE  → NEW_YORK      (US law; Fed-wire-settled USD payments)
  CHAPS    → ENGLAND_WALES (English law; CHAPS-settled GBP payments)
  TARGET2  → EU_LUXEMBOURG (Luxembourg law; ECB-settled EUR payments)
  UNKNOWN  → UNKNOWN       (fallback; contract requires manual review)
"""
from __future__ import annotations

from typing import Literal

GoverningLaw = Literal["NEW_YORK", "ENGLAND_WALES", "EU_LUXEMBOURG", "UNKNOWN"]

_JURISDICTION_TO_LAW: dict[str, GoverningLaw] = {
    "FEDWIRE": "NEW_YORK",
    "CHAPS": "ENGLAND_WALES",
    "TARGET2": "EU_LUXEMBOURG",
}


def law_for_jurisdiction(jurisdiction: str) -> GoverningLaw:
    """Map a settlement jurisdiction to the contractual governing law.

    Args:
        jurisdiction: Settlement system identifier — ``"FEDWIRE"``,
            ``"CHAPS"``, or ``"TARGET2"``.  Case-insensitive.

    Returns:
        :data:`GoverningLaw` literal string.  Returns ``"UNKNOWN"`` for any
        jurisdiction not in the mapping table; callers should treat
        ``"UNKNOWN"`` as requiring manual legal review before disbursement.
    """
    return _JURISDICTION_TO_LAW.get(jurisdiction.upper(), "UNKNOWN")
