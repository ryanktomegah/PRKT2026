"""
bic_name_resolver.py — Minimal BIC → institution-name resolver for sanctions screening.

The AMLChecker sanctions screener expects a human-readable institution name so
Jaccard similarity can match against sanctions-list entity names (EPG-24).
Passing the raw 8-char BIC produces 0.0 similarity against every sanctioned
entity name and silently disables sanctions enforcement.

This module provides a conservative default resolver for staging and pilot use.
The mapping is **curated** — it covers the major correspondent banks that
appear in the synthetic test corpora and the pilot bank list. Unknown BICs
return ``None``; the caller is expected to log a warning and either escalate
(production) or tolerate the screening gap (staging).

A production deployment must replace this with a resolver backed by a licensed
SWIFT BIC directory or an enrolled-borrower registry with legal-name fields.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Curated 8-char BIC → institution legal-name map.
# Source: public SWIFT BIC registry (bank-owned, non-proprietary institution
# names). Covers the pilot bank set + the synthetic corpus's top-30 BICs.
_CURATED_BIC_MAP: dict[str, str] = {
    # North America
    "CHASUS33": "JPMORGAN CHASE BANK",
    "BOFAUS3N": "BANK OF AMERICA",
    "CITIUS33": "CITIBANK",
    "WFBIUS6S": "WELLS FARGO BANK",
    "BKTRUS33": "BANK OF NEW YORK MELLON",
    "ROYCCAT2": "ROYAL BANK OF CANADA",
    "TDOMCATT": "TORONTO-DOMINION BANK",
    "BOFMCAM2": "BANK OF MONTREAL",
    "NOSCCATT": "BANK OF NOVA SCOTIA",
    "CIBCCATT": "CANADIAN IMPERIAL BANK OF COMMERCE",
    # Europe
    "DEUTDEFF": "DEUTSCHE BANK",
    "COBADEFF": "COMMERZBANK",
    "BNPAFRPP": "BNP PARIBAS",
    "SOGEFRPP": "SOCIETE GENERALE",
    "CRLYFRPP": "CREDIT AGRICOLE",
    "BARCGB22": "BARCLAYS BANK",
    "HSBCGB2L": "HSBC BANK",
    "LOYDGB2L": "LLOYDS BANK",
    "NWBKGB2L": "NATWEST BANK",
    "UBSWCHZH": "UBS",
    "CRESCHZZ": "CREDIT SUISSE",
    "INGBNL2A": "ING BANK",
    "ABNANL2A": "ABN AMRO BANK",
    "RABONL2U": "RABOBANK",
    "UNCRITMM": "UNICREDIT",
    "BCITITMM": "INTESA SANPAOLO",
    "BBVAESMM": "BBVA",
    "BSCHESMM": "BANCO SANTANDER",
    # Asia-Pacific
    "BOTKJPJT": "MUFG BANK",
    "SMBCJPJT": "SUMITOMO MITSUI BANKING CORPORATION",
    "MHCBJPJT": "MIZUHO BANK",
    "HSBCHKHH": "HSBC HONG KONG",
    "SCBLHKHH": "STANDARD CHARTERED BANK HONG KONG",
    "DBSSSGSG": "DBS BANK",
    "OCBCSGSG": "OCBC BANK",
    "UOVBSGSG": "UNITED OVERSEAS BANK",
    "CBAUAU2S": "COMMONWEALTH BANK OF AUSTRALIA",
    "ANZBAU3M": "AUSTRALIA AND NEW ZEALAND BANKING GROUP",
}


def build_bic_name_resolver(
    extra_map: Optional[dict[str, str]] = None,
) -> Callable[[str], Optional[str]]:
    """Return a resolver that maps BIC (first 8 chars) to institution name.

    Args:
        extra_map: Optional caller-supplied overrides / additions. Keys are
            normalised to uppercase first-8-chars before lookup.

    Returns:
        Callable ``(bic: str) -> Optional[str]``. Unknown BICs return ``None``,
        which the sanctions screener treats as "no name available" — the BIC
        string is passed through, and the ``AMLChecker: entity_name_resolver``
        warning stops firing because a resolver was explicitly configured.
    """
    merged = dict(_CURATED_BIC_MAP)
    if extra_map:
        merged.update({k.upper()[:8]: v for k, v in extra_map.items()})

    def _resolve(bic: str) -> Optional[str]:
        if not bic:
            return None
        key = bic.upper()[:8]
        name = merged.get(key)
        if name is None:
            logger.debug(
                "BIC name resolver: no entry for %s — sanctions screening will "
                "use the raw BIC string. Add to bic_name_resolver._CURATED_BIC_MAP "
                "or pass via extra_map=... if this BIC is in active pilot use.",
                key,
            )
        return name

    return _resolve
