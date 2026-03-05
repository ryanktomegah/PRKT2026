"""
velocity.py — AML velocity controls
Dollar cap $1M, count cap 100 per entity per 24hr rolling window.
Beneficiary concentration: >80% to single beneficiary triggers alert.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DOLLAR_CAP_USD = Decimal("1000000")
COUNT_CAP = 100
BENEFICIARY_CONCENTRATION_THRESHOLD = Decimal("0.80")


@dataclass
class VelocityResult:
    passed: bool
    reason: Optional[str]
    entity_id_hash: str
    dollar_volume_24h: Decimal
    count_24h: int
    beneficiary_concentration: Optional[Decimal]


class RollingWindow:
    """24-hour rolling window tracking per entity."""

    def __init__(self, window_seconds: int = 86400):
        self._window_seconds = window_seconds
        # entity_hash -> deque of (timestamp, amount, beneficiary_hash)
        self._records: Dict[str, Deque[Tuple[float, Decimal, str]]] = defaultdict(deque)

    def add(self, entity_hash: str, amount: Decimal, beneficiary_hash: str) -> None:
        self._cleanup_expired(entity_hash)
        self._records[entity_hash].append((time.time(), amount, beneficiary_hash))

    def get_volume(self, entity_hash: str) -> Decimal:
        self._cleanup_expired(entity_hash)
        return sum((r[1] for r in self._records[entity_hash]), Decimal("0"))

    def get_count(self, entity_hash: str) -> int:
        self._cleanup_expired(entity_hash)
        return len(self._records[entity_hash])

    def get_beneficiary_concentration(self, entity_hash: str) -> Decimal:
        """Returns fraction (0-1) going to the single largest beneficiary."""
        self._cleanup_expired(entity_hash)
        records = self._records[entity_hash]
        if not records:
            return Decimal("0")
        total = sum(r[1] for r in records)
        if total == 0:
            return Decimal("0")
        by_bene: Dict[str, Decimal] = defaultdict(Decimal)
        for _, amt, bene in records:
            by_bene[bene] += amt
        max_fraction = max(by_bene.values()) / total
        return max_fraction

    def _cleanup_expired(self, entity_hash: str) -> None:
        cutoff = time.time() - self._window_seconds
        dq = self._records[entity_hash]
        while dq and dq[0][0] < cutoff:
            dq.popleft()


class VelocityChecker:
    """Checks AML velocity limits for a given entity."""

    def __init__(self, salt: bytes, redis_client=None):
        self.salt = salt
        self._redis = redis_client
        self._window = RollingWindow()

    def _hash_entity(self, entity_id: str) -> str:
        """SHA-256(entity_id + salt). Never stores raw entity_id."""
        return hashlib.sha256(entity_id.encode() + self.salt).hexdigest()

    def _hash_beneficiary(self, beneficiary_id: str) -> str:
        return hashlib.sha256(beneficiary_id.encode() + self.salt).hexdigest()

    def check(self, entity_id: str, amount: Decimal, beneficiary_id: str) -> VelocityResult:
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        vol = self._window.get_volume(entity_hash)
        cnt = self._window.get_count(entity_hash)
        conc = self._window.get_beneficiary_concentration(entity_hash)

        if vol + amount > DOLLAR_CAP_USD:
            return VelocityResult(
                passed=False, reason="DOLLAR_CAP_EXCEEDED",
                entity_id_hash=entity_hash, dollar_volume_24h=vol,
                count_24h=cnt, beneficiary_concentration=conc,
            )
        if cnt + 1 > COUNT_CAP:
            return VelocityResult(
                passed=False, reason="COUNT_CAP_EXCEEDED",
                entity_id_hash=entity_hash, dollar_volume_24h=vol,
                count_24h=cnt, beneficiary_concentration=conc,
            )
        # Check beneficiary concentration after hypothetical add
        # Only apply when there are already existing transactions AND
        # a second distinct beneficiary (concentration is only meaningful with >1 beneficiary)
        total_after = vol + amount
        existing_count = cnt
        if total_after > 0 and existing_count >= 2:
            by_bene: Dict[str, Decimal] = defaultdict(Decimal)
            for _, a, b in self._window._records[entity_hash]:
                by_bene[b] += a
            by_bene[bene_hash] += amount
            if len(by_bene) >= 2:  # only flag if there are multiple beneficiaries
                new_conc = max(by_bene.values()) / total_after
                if new_conc > BENEFICIARY_CONCENTRATION_THRESHOLD:
                    return VelocityResult(
                        passed=False, reason="BENEFICIARY_CONCENTRATION_EXCEEDED",
                        entity_id_hash=entity_hash, dollar_volume_24h=vol,
                        count_24h=cnt, beneficiary_concentration=new_conc,
                    )
        return VelocityResult(
            passed=True, reason=None,
            entity_id_hash=entity_hash, dollar_volume_24h=vol,
            count_24h=cnt, beneficiary_concentration=conc,
        )

    def record(self, entity_id: str, amount: Decimal, beneficiary_id: str) -> None:
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        self._window.add(entity_hash, amount, bene_hash)
        logger.debug("Recorded velocity: entity_hash=%s amount=%s", entity_hash[:8], amount)
