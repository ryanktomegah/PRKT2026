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
    OFAC = "OFAC"
    EU = "EU"
    UN = "UN"


@dataclass
class SanctionsHit:
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
        return len(self.screen(entity_name)) == 0
