"""
uetr_mapping.py — RTP EndToEndId → UETR Redis mapping
Architecture Spec S11.2: TTL = maturity_days + 45 days
"""
import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

UETR_KEY_PREFIX = "lip:uetr_map:"
DEFAULT_TTL_DAYS = 45  # Extra retention days beyond maturity window

# Amortized cleanup: sweep in-memory store every N store/lookup calls
_CLEANUP_INTERVAL = 50


def _sha256_hex(value: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 string (used for key hashing)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class UETRMappingTable:
    """Maps RTP EndToEndId values to UETRs with configurable TTL.

    When a Redis client is supplied, keys are stored in Redis with an
    explicit TTL (``maturity_days + DEFAULT_TTL_DAYS`` days converted to
    seconds).  If no Redis client is provided the table falls back to an
    in-memory dict — appropriate for testing and single-process deployments.

    Key format: ``lip:uetr_map:<sha256(end_to_end_id)>``

    Architecture Spec S11.2: TTL = maturity_days + 45 days
    """

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        # In-memory fallback: maps key → (uetr, expiry_timestamp_unix)
        self._store: dict[str, tuple[str, float]] = {}
        self._op_count: int = 0  # counter for amortized cleanup

    # ── Public API ────────────────────────────────────────────────────────────

    def store(self, end_to_end_id: str, uetr: str, maturity_days: int) -> None:
        """Persist an EndToEndId → UETR mapping.

        Args:
            end_to_end_id: The RTP EndToEndId originating from the payment message.
            uetr: The corresponding UETR for the SWIFT/cross-rail leg.
            maturity_days: Base maturity window in days (from rejection class).
                           TTL is extended by ``DEFAULT_TTL_DAYS`` for safety margin.
        """
        key = self._make_key(end_to_end_id)
        ttl_seconds = self.get_ttl_seconds(maturity_days)

        if self._redis is not None:
            self._redis.setex(key, ttl_seconds, uetr)
            logger.debug(
                "Redis store: %s → %s (TTL=%ds, maturity=%dd)",
                end_to_end_id, uetr, ttl_seconds, maturity_days,
            )
        else:
            expiry = time.time() + ttl_seconds
            self._store[key] = (uetr, expiry)
            logger.debug(
                "In-memory store: %s → %s (TTL=%ds, expires_at=%.0f)",
                end_to_end_id, uetr, ttl_seconds, expiry,
            )
            self._maybe_evict()

    def lookup(self, end_to_end_id: str) -> Optional[str]:
        """Return the UETR for the given EndToEndId, or None if not found / expired."""
        key = self._make_key(end_to_end_id)

        if self._redis is not None:
            raw = self._redis.get(key)
            if raw is None:
                logger.debug("Redis lookup miss: %s", end_to_end_id)
                return None
            uetr = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            logger.debug("Redis lookup hit: %s → %s", end_to_end_id, uetr)
            return uetr

        entry = self._store.get(key)
        if entry is None:
            logger.debug("In-memory lookup miss: %s", end_to_end_id)
            return None
        uetr, expiry = entry
        if time.time() > expiry:
            del self._store[key]
            logger.debug("In-memory lookup expired and evicted: %s", end_to_end_id)
            return None
        self._maybe_evict()
        logger.debug("In-memory lookup hit: %s → %s", end_to_end_id, uetr)
        return uetr

    def delete(self, end_to_end_id: str) -> None:
        """Remove the mapping for the given EndToEndId."""
        key = self._make_key(end_to_end_id)

        if self._redis is not None:
            deleted = self._redis.delete(key)
            logger.debug(
                "Redis delete: %s (key=%s, deleted=%s)",
                end_to_end_id, key, bool(deleted),
            )
        else:
            existed = self._store.pop(key, None) is not None
            logger.debug(
                "In-memory delete: %s (existed=%s)", end_to_end_id, existed
            )

    # ── Amortized cleanup ──────────────────────────────────────────────────────

    def _maybe_evict(self) -> None:
        """Evict expired entries from in-memory store every _CLEANUP_INTERVAL operations."""
        self._op_count += 1
        if self._op_count % _CLEANUP_INTERVAL != 0:
            return
        now = time.time()
        expired_keys = [k for k, (_, expiry) in self._store.items() if now > expiry]
        for k in expired_keys:
            del self._store[k]
        if expired_keys:
            logger.debug(
                "In-memory TTL cleanup: evicted %d expired entry/entries",
                len(expired_keys),
            )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _make_key(self, end_to_end_id: str) -> str:
        """Build the Redis/store key for an EndToEndId.

        The EndToEndId is SHA-256 hashed before inclusion in the key to keep
        key lengths bounded and avoid special-character issues in Redis.
        """
        hashed = _sha256_hex(end_to_end_id)
        return f"{UETR_KEY_PREFIX}{hashed}"

    @staticmethod
    def get_ttl_seconds(maturity_days: int) -> int:
        """Return TTL in seconds: (maturity_days + DEFAULT_TTL_DAYS) × 86400.

        Args:
            maturity_days: Base maturity window in days.

        Returns:
            Total TTL in seconds.
        """
        total_days = maturity_days + DEFAULT_TTL_DAYS
        return total_days * 86_400
