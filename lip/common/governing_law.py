"""
governing_law.py — GAP-10 / EPG-14: Governing-law mapping for cross-border bridge loans.

Maps the settlement jurisdiction to the contractual governing law required by
MRFA clause 4 for enforceability of cross-border bridge-loan agreements.

Supported jurisdictions → governing laws:
  FEDWIRE  → NEW_YORK      (US law; Fed-wire-settled USD payments)
  CHAPS    → ENGLAND_WALES (English law; CHAPS-settled GBP payments)
  TARGET2  → EU_LUXEMBOURG (Luxembourg law; ECB-settled EUR payments)
  UNKNOWN  → UNKNOWN       (fallback; contract requires manual review)

EPG-14 (REX, 2026-03-18): Governing law must be derived from the enrolled
originating bank's jurisdiction (BIC country code), NOT the payment currency.
Using payment currency as a proxy is wrong for cross-border correspondent
banking — e.g., a EUR-denominated payment from a US bank (BIC chars 4-5 = "US")
should be governed by New York law (FEDWIRE), not Luxembourg law (TARGET2).
``bic_to_jurisdiction()`` implements this correctly. ``law_for_jurisdiction()``
remains the authority for jurisdiction → law conversion.
"""
from __future__ import annotations

from typing import Literal

GoverningLaw = Literal["NEW_YORK", "ENGLAND_WALES", "EU_LUXEMBOURG", "UNKNOWN"]

_JURISDICTION_TO_LAW: dict[str, GoverningLaw] = {
    "FEDWIRE": "NEW_YORK",
    "CHAPS": "ENGLAND_WALES",
    "TARGET2": "EU_LUXEMBOURG",
}

# Eurozone (TARGET2) country codes — ISO 3166-1 alpha-2.
# Only eurozone members whose central banks participate in TARGET2 settlement.
# Non-eurozone EU members (CZ, HU, PL, SE, etc.) are excluded — they may use
# their own RTGS systems. Add them when LIP expands to those corridors.
_TARGET2_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT", "BE", "CY", "EE", "FI", "FR", "DE", "GR", "IE", "IT",
    "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES",
})


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


def bic_to_jurisdiction(bic: str) -> str:
    """Derive the settlement jurisdiction from the BIC's country code.

    BIC format: AAAABBCCXXX — chars 0-3 bank code, chars 4-5 ISO 3166-1 alpha-2
    country code, chars 6-7 location, chars 8-10 optional branch.

    This is the correct way to derive governing law for a bridge loan:
    the originating bank's jurisdiction (not the payment currency) determines
    which RTGS system governs the settlement and therefore which law applies
    to the MRFA repayment obligation.

    EPG-14 (REX, 2026-03-18): Currency-based jurisdiction derivation is wrong for
    cross-border correspondent banking. Use this function as the primary lookup;
    fall back to currency-based derivation only when the BIC is absent or yields
    UNKNOWN (e.g., non-standard BICs or corridors not yet mapped).

    Args:
        bic: ISO 9362 BIC/SWIFT code (8 or 11 chars).  Shorter strings or
            empty strings return ``"UNKNOWN"``.

    Returns:
        Settlement jurisdiction string: ``"FEDWIRE"``, ``"CHAPS"``,
        ``"TARGET2"``, or ``"UNKNOWN"``.
    """
    if not bic or len(bic) < 6:
        return "UNKNOWN"
    country = bic[4:6].upper()
    if country == "US":
        return "FEDWIRE"
    if country == "GB":
        return "CHAPS"
    if country in _TARGET2_COUNTRY_CODES:
        return "TARGET2"
    return "UNKNOWN"
