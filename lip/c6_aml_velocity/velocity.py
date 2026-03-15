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
from typing import Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DOLLAR_CAP_USD = Decimal("1000000")
COUNT_CAP = 100
BENEFICIARY_CONCENTRATION_THRESHOLD = Decimal("0.80")


@dataclass
class VelocityResult:
    """Result of an AML velocity check for a single entity transaction.

    Attributes:
        passed: True when all velocity limits are satisfied; False when any
            rule fires and the transaction must be blocked.
        reason: Rule identifier that caused a block, e.g.
            ``'DOLLAR_CAP_EXCEEDED'``, ``'COUNT_CAP_EXCEEDED'``,
            ``'BENEFICIARY_CONCENTRATION_EXCEEDED'``.  ``None`` when passed.
        entity_id_hash: SHA-256 hex digest of the entity identifier (never
            contains raw entity_id — privacy guarantee).
        dollar_volume_24h: Total USD volume recorded for this entity in the
            current 24-hour rolling window, *excluding* the candidate transaction.
        count_24h: Number of transactions recorded in the current 24-hour
            rolling window, *excluding* the candidate transaction.
        beneficiary_concentration: Fraction [0, 1] of the current 24-hour
            volume directed to the single largest beneficiary.  ``None`` when
            no prior records exist in the window.
    """

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
        """Append a new transaction record to the entity's rolling window.

        Cleans up expired records before appending so the window stays bounded.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.
            amount: Transaction amount in USD.
            beneficiary_hash: SHA-256 hex digest of the beneficiary identifier.
        """
        self._cleanup_expired(entity_hash)
        self._records[entity_hash].append((time.time(), amount, beneficiary_hash))

    def get_volume(self, entity_hash: str) -> Decimal:
        """Return the total USD volume for an entity within the rolling window.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.

        Returns:
            Sum of all transaction amounts recorded within the window.
            Returns ``Decimal('0')`` when no records exist.
        """
        self._cleanup_expired(entity_hash)
        return sum((r[1] for r in self._records[entity_hash]), Decimal("0"))

    def get_count(self, entity_hash: str) -> int:
        """Return the number of transactions for an entity within the rolling window.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.

        Returns:
            Count of records within the window.  Returns ``0`` when empty.
        """
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
        """Evict all records older than ``window_seconds`` from the deque.

        Uses a left-pop loop which is O(k) where k is the number of expired
        records — amortised O(1) per transaction in steady state.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.
        """
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
        """Compute SHA-256(entity_id + salt) for the entity identifier.

        Never stores the raw ``entity_id`` — all window records use the
        digest only.  This satisfies GDPR Art.25 (data minimisation) and
        AML record-keeping requirements simultaneously.

        Args:
            entity_id: Raw entity identifier string (e.g., BIC or licensee ID).

        Returns:
            Lowercase hex SHA-256 digest (64 characters).
        """
        return hashlib.sha256(entity_id.encode() + self.salt).hexdigest()

    def _hash_beneficiary(self, beneficiary_id: str) -> str:
        """Compute SHA-256(beneficiary_id + salt) for the beneficiary identifier.

        Uses the same salt as :meth:`_hash_entity` to ensure cross-licensee
        isolation; a different licensee's salt produces a different digest for
        the same beneficiary.

        Args:
            beneficiary_id: Raw beneficiary identifier string.

        Returns:
            Lowercase hex SHA-256 digest (64 characters).
        """
        return hashlib.sha256(beneficiary_id.encode() + self.salt).hexdigest()

    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> VelocityResult:
        """Check whether this transaction would violate AML velocity limits.

        Evaluates three rules in order:
          1. Dollar-cap: rolling 24-hour volume + ``amount`` ≤ cap.
          2. Count-cap: rolling 24-hour count + 1 ≤ cap.
          3. Beneficiary concentration: single beneficiary share ≤ 80%
             (only enforced when ≥ 2 distinct beneficiaries and ≥ 2 prior
             transactions exist in the window).

        Does *not* record the transaction; call :meth:`record` after a
        successful check.

        Args:
            entity_id: Raw entity identifier (hashed internally).
            amount: Candidate transaction amount in USD.
            beneficiary_id: Raw beneficiary identifier (hashed internally).
            dollar_cap_override: Optional USD cap to use instead of the
                default $1M limit.
            count_cap_override: Optional count cap to use instead of the
                default 100 limit.

        Returns:
            :class:`VelocityResult` with ``passed=True`` when all rules pass,
            or ``passed=False`` and a ``reason`` string when any rule fires.
        """
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        vol = self._window.get_volume(entity_hash)
        cnt = self._window.get_count(entity_hash)
        conc = self._window.get_beneficiary_concentration(entity_hash)

        dollar_cap = dollar_cap_override if dollar_cap_override is not None else DOLLAR_CAP_USD
        count_cap = count_cap_override if count_cap_override is not None else COUNT_CAP

        if vol + amount > dollar_cap:
            return VelocityResult(
                passed=False, reason="DOLLAR_CAP_EXCEEDED",
                entity_id_hash=entity_hash, dollar_volume_24h=vol,
                count_24h=cnt, beneficiary_concentration=conc,
            )
        if cnt + 1 > count_cap:
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

    def record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> None:
        """Record a transaction in the rolling window after it has been accepted.

        Must be called *after* a successful :meth:`check` to update the window
        for subsequent checks.  Calling :meth:`record` without a prior
        :meth:`check` can cause the next check to fail spuriously.

        Args:
            entity_id: Raw entity identifier (hashed internally).
            amount: Transaction amount in USD.
            beneficiary_id: Raw beneficiary identifier (hashed internally).
            dollar_cap_override: Optional USD cap (ignored, for signature symmetry with check).
            count_cap_override: Optional count cap (ignored, for signature symmetry with check).
        """
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        self._window.add(entity_hash, amount, bene_hash)
        logger.debug("Recorded velocity: entity_hash=%s amount=%s", entity_hash[:8], amount)
