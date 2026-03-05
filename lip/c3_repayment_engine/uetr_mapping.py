"""
uetr_mapping.py — RTP EndToEndId → UETR Redis mapping
Architecture Spec S11.2: TTL = maturity_days + 45 days
"""
import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

UETR_KEY_PREFIX = "lip:uetr_map:"
DEFAULT_TTL_DAYS = 45  # Extra retention days beyond maturity window


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
        self._store: dict[str, str] = {}  # fallback in-memory store

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
            self._store[key] = uetr
            logger.debug(
                "In-memory store: %s → %s (TTL not enforced in fallback)",
                end_to_end_id, uetr,
            )

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

        uetr = self._store.get(key)
        if uetr is None:
            logger.debug("In-memory lookup miss: %s", end_to_end_id)
        else:
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
