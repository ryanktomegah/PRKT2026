"""
borrower_registry.py — GAP-03: Enrolled Borrower Registry.

Before LIP can offer a bridge loan, the sending BIC (the borrower) must have
explicitly enrolled in the service by signing a Master Receivables Finance
Agreement (MRFA).

The ``BorrowerRegistry`` is the authoritative source of truth for these
enrollments. C7 (Execution Agent) checks this registry as the very first gate
in the decision pipeline. If a sender is not enrolled, the pipeline returns
``BORROWER_NOT_ENROLLED`` and halts.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional, Set

logger = logging.getLogger(__name__)

_REDIS_KEY = "lip:borrower:enrolled"


class BorrowerRegistry:
    """Manages the set of BICs authorized to receive bridge loan offers.

    Thread-safe via ``threading.Lock`` (GAP-21).
    Optional Redis persistence (GAP-03): write-through on mutate,
    in-memory authoritative for reads, Redis for restart recovery.

    Parameters
    ----------
    enrolled_bics:
        Optional initial set of enrolled BIC codes.
    redis_client:
        Optional Redis client. When None, pure in-memory operation.
    """

    def __init__(
        self,
        enrolled_bics: Optional[Set[str]] = None,
        redis_client: Any = None,
    ) -> None:
        self._lock = threading.Lock()
        self._redis = redis_client
        self._enrolled: Set[str] = set()
        if enrolled_bics:
            for bic in enrolled_bics:
                self._enrolled.add(bic.upper())
        # Load from Redis on init
        if self._redis is not None:
            self._load_from_redis()

    def _load_from_redis(self) -> None:
        try:
            members = self._redis.smembers(_REDIS_KEY)
            if members:
                for m in members:
                    val = m.decode() if isinstance(m, bytes) else str(m)
                    self._enrolled.add(val.upper())
                logger.info("Loaded %d enrolled BICs from Redis", len(members))
        except Exception as exc:
            logger.warning("Failed to load enrolled BICs from Redis: %s", exc)

    def enroll(self, bic: str) -> None:
        """Add a BIC to the registry.

        Args:
            bic: SWIFT BIC code to enroll.
        """
        normalized = bic.upper()
        with self._lock:
            self._enrolled.add(normalized)
        if self._redis is not None:
            try:
                self._redis.sadd(_REDIS_KEY, normalized)
            except Exception as exc:
                logger.warning("Redis sadd failed for BIC %s: %s", normalized, exc)

    def unenroll(self, bic: str) -> None:
        """Remove a BIC from the registry.

        Args:
            bic: SWIFT BIC code to remove.
        """
        normalized = bic.upper()
        with self._lock:
            self._enrolled.discard(normalized)
        if self._redis is not None:
            try:
                self._redis.srem(_REDIS_KEY, normalized)
            except Exception as exc:
                logger.warning("Redis srem failed for BIC %s: %s", normalized, exc)

    def is_enrolled(self, bic: str) -> bool:
        """Return True if the BIC is enrolled.

        Args:
            bic: SWIFT BIC code to check.
        """
        normalized = bic.upper()
        with self._lock:
            if normalized in self._enrolled:
                return True
        # Fallback to Redis check if not in memory
        if self._redis is not None:
            try:
                if self._redis.sismember(_REDIS_KEY, normalized):
                    with self._lock:
                        self._enrolled.add(normalized)
                    return True
            except Exception as exc:
                logger.warning("Redis sismember failed for BIC %s: %s", normalized, exc)
        return False

    def list_enrolled(self) -> Set[str]:
        """Return a copy of the enrolled BICs set."""
        with self._lock:
            return set(self._enrolled)
