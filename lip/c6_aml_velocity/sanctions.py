"""
sanctions.py — OFAC/EU/UN sanctions screening.
Zero external network calls; local list loaded at startup.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import logging
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SanctionsList(str, Enum):
    """Supported sanctions list identifiers.

    Values map to keys in the JSON file loaded by
    :meth:`~SanctionsScreener._load_lists`.

    Attributes:
        OFAC: U.S. Office of Foreign Assets Control SDN / consolidated list.
        EU: European Union consolidated financial-sanctions list.
        UN: United Nations Security Council consolidated list.
    """

    OFAC = "OFAC"
    EU = "EU"
    UN = "UN"


@dataclass
class SanctionsHit:
    """A single positive match between a screened entity and a sanctions entry.

    Attributes:
        entity_name_hash: SHA-256 hex digest of the normalised (upper-cased,
            stripped) entity name.  Raw names are never stored.
        list_name: Which sanctions list produced this hit (OFAC, EU, or UN).
        confidence: Jaccard token-overlap similarity score in [0, 1].  Only
            hits with ``confidence >= 0.8`` are returned by
            :meth:`~SanctionsScreener.screen`.
        reference: The matched entry string from the sanctions list
            (upper-cased canonical form).
    """

    entity_name_hash: str
    list_name: SanctionsList
    confidence: float
    reference: str


MOCK_SANCTIONS_ENTRIES: dict = {
    SanctionsList.OFAC: {"ACME SHELL CORP", "DUMMY SANCTIONS ENTITY", "TEST BLOCKED PARTY"},
    SanctionsList.EU: {"EU BLOCKED ENTITY", "TEST EU SANCTIONS"},
    SanctionsList.UN: {"UN BLOCKED ENTITY", "TEST UN SANCTIONS"},
}


def _transliterate(text: str) -> str:
    """NFKD-normalize and transliterate to ASCII (B7-03).

    Decomposes Unicode characters into base + combining marks via NFKD,
    then strips combining marks (accents, diacritics). Non-Latin scripts
    (Cyrillic, Arabic, CJK) lose their non-ASCII chars — this is
    intentional: the transliterated form is used as a secondary matching
    signal alongside the original.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    # Strip combining characters (category M = Mark)
    ascii_form = "".join(ch for ch in nfkd if not unicodedata.category(ch).startswith("M"))
    # Replace remaining non-ASCII with empty string
    return ascii_form.encode("ascii", "ignore").decode("ascii")


def _soundex(name: str) -> str:
    """Compute American Soundex code for a single word (B7-03).

    Returns a 4-character code (letter + 3 digits). Returns empty string
    for empty input. Only processes ASCII alphabetic characters.
    """
    # Standard Soundex mapping
    _MAP = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    alpha = "".join(ch for ch in name.upper() if ch.isalpha())
    if not alpha:
        return ""
    code = alpha[0]
    prev_digit = _MAP.get(alpha[0], "0")
    for ch in alpha[1:]:
        digit = _MAP.get(ch, "0")
        if digit != "0" and digit != prev_digit:
            code += digit
        prev_digit = digit if digit != "0" else prev_digit
        if len(code) == 4:
            break
    return code.ljust(4, "0")


def _soundex_tokens(text: str) -> set[str]:
    """Compute soundex codes for all tokens in a string."""
    codes = set()
    for token in text.split():
        code = _soundex(token)
        if code:
            codes.add(code)
    return codes


class SanctionsScreener:
    """Screens entities against OFAC/EU/UN sanctions lists."""

    def __init__(self, lists_path: Optional[str] = None):
        self._lists: dict = {}
        if lists_path:
            self._load_lists(lists_path)
        else:
            self._lists = {k: set(v) for k, v in MOCK_SANCTIONS_ENTRIES.items()}

    def _load_lists(self, path: str) -> None:
        """Load sanctions entries from a JSON file into memory.

        The JSON file must be a dict mapping :class:`SanctionsList` value
        strings to lists of entity name strings, e.g.::

            {"OFAC": ["ENTITY A", "ENTITY B"], "EU": [...], "UN": [...]}

        Falls back to :data:`MOCK_SANCTIONS_ENTRIES` if the file is not found.

        Args:
            path: Filesystem path to the JSON sanctions list file.
        """
        import json
        import os
        if not os.path.exists(path):
            logger.warning("Sanctions list file not found: %s; using mock data", path)
            self._lists = {k: set(v) for k, v in MOCK_SANCTIONS_ENTRIES.items()}
            return
        with open(path) as f:
            data = json.load(f)
        for list_name in SanctionsList:
            self._lists[list_name] = set(data.get(list_name.value, []))

    def screen(self, entity_name: str, entity_id: Optional[str] = None) -> List[SanctionsHit]:
        """Screen an entity name against all loaded sanctions lists.

        Normalises the name (upper-case, strip whitespace) before matching.
        Only returns hits where :meth:`_fuzzy_match` confidence >= 0.8.

        Args:
            entity_name: Human-readable entity name to screen.
            entity_id: Optional entity identifier (currently unused; reserved
                for future exact-ID screening against LEI / BIC databases).

        Returns:
            List of :class:`SanctionsHit` objects — empty when the entity
            is clear on all lists.
        """
        normalized = entity_name.upper().strip()
        # B7-03: Transliterate non-Latin scripts for cross-script matching
        transliterated = _transliterate(normalized).upper().strip()
        name_hash = hashlib.sha256(normalized.encode()).hexdigest()
        hits: List[SanctionsHit] = []
        for list_name, entries in self._lists.items():
            # Match on both original and transliterated forms
            matches = self._fuzzy_match(normalized, entries)
            if transliterated != normalized:
                translit_matches = self._fuzzy_match(transliterated, entries)
                # Merge: keep the higher confidence for each entry
                match_dict = dict(matches)
                for entry, conf in translit_matches:
                    if entry not in match_dict or conf > match_dict[entry]:
                        match_dict[entry] = conf
                matches = list(match_dict.items())
            for matched, confidence in matches:
                if confidence >= 0.8:
                    hits.append(SanctionsHit(
                        entity_name_hash=name_hash,
                        list_name=list_name,
                        confidence=confidence,
                        reference=matched,
                    ))
        return hits

    def _fuzzy_match(self, name: str, sanctions_set: Set[str]) -> List[Tuple[str, float]]:
        """Compute combined Jaccard + phonetic similarity (B7-03).

        Primary signal: Jaccard token-overlap on surface tokens.
        Secondary signal: Soundex phonetic token-overlap. The final score
        is ``max(jaccard, phonetic_jaccard * 0.9)`` — phonetic matches are
        slightly discounted since they can produce more false positives.

        Args:
            name: Normalised (upper-cased, stripped) entity name.
            sanctions_set: Set of normalised sanctions entries to compare
                against.

        Returns:
            List of ``(entry, score)`` tuples for all entries with
            any token or phonetic overlap, sorted in insertion order.
        """
        results = []
        name_tokens = set(name.split())
        name_phonetic = _soundex_tokens(name)
        for entry in sanctions_set:
            entry_tokens = set(entry.split())
            if not entry_tokens:
                continue
            # Surface token overlap
            intersection = name_tokens & entry_tokens
            union = name_tokens | entry_tokens
            jaccard = len(intersection) / len(union) if union else 0.0
            # Phonetic token overlap (B7-03)
            entry_phonetic = _soundex_tokens(entry)
            phonetic_union = name_phonetic | entry_phonetic
            phonetic_intersection = name_phonetic & entry_phonetic
            phonetic_jaccard = (
                len(phonetic_intersection) / len(phonetic_union)
                if phonetic_union else 0.0
            )
            # Combined score: best of surface or discounted phonetic
            score = max(jaccard, phonetic_jaccard * 0.9)
            if score > 0:
                results.append((entry, score))
        return results

    def is_clear(self, entity_name: str) -> bool:
        """Return True when the entity name has no hits on any sanctions list.

        Convenience wrapper around :meth:`screen`.

        Args:
            entity_name: Human-readable entity name to check.

        Returns:
            ``True`` if :meth:`screen` returns an empty list, ``False``
            otherwise.
        """
        return len(self.screen(entity_name)) == 0
