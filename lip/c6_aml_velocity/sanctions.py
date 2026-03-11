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
        name_hash = hashlib.sha256(normalized.encode()).hexdigest()
        hits: List[SanctionsHit] = []
        for list_name, entries in self._lists.items():
            matches = self._fuzzy_match(normalized, entries)
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
        """Compute Jaccard token-overlap similarity between name and each entry.

        Tokenises both strings on whitespace and computes::

            jaccard = |intersection| / |union|

        Only entries with ``jaccard > 0`` are returned.

        Args:
            name: Normalised (upper-cased, stripped) entity name.
            sanctions_set: Set of normalised sanctions entries to compare
                against.

        Returns:
            List of ``(entry, jaccard_score)`` tuples for all entries with
            any token overlap, sorted in insertion order (not by score).
        """
        results = []
        name_tokens = set(name.split())
        for entry in sanctions_set:
            entry_tokens = set(entry.split())
            if not entry_tokens:
                continue
            intersection = name_tokens & entry_tokens
            union = name_tokens | entry_tokens
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard > 0:
                results.append((entry, jaccard))
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
