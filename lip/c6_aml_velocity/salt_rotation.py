"""
salt_rotation.py — Annual salt rotation with 30-day dual-salt overlap.
Architecture Spec S11.3

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ROTATION_INTERVAL_DAYS = 365
OVERLAP_DAYS = 30


@dataclass
class SaltRecord:
    """Persistent record for a single salt generation cycle.

    Attributes:
        salt: 32 random bytes produced by :func:`os.urandom`.  Never logged
            or transmitted; stored in Redis as a hex string with a TTL.
        created_at: UTC datetime when this salt was generated.
        expires_at: UTC datetime after which this salt should be rotated
            (``created_at + ROTATION_INTERVAL_DAYS``).
        is_active: ``True`` while this is the current active salt;
            ``False`` after it has been promoted to ``previous`` by
            :meth:`~SaltRotationManager.rotate_salt`.
    """

    salt: bytes
    created_at: datetime
    expires_at: datetime
    is_active: bool = True


class SaltRotationManager:
    """Manages annual salt rotation with 30-day dual-salt overlap."""

    def __init__(self, redis_client=None):
        """Initialise the manager and load or generate the current salt.

        If a ``current`` salt record exists in Redis it is loaded; otherwise
        a fresh 32-byte salt is generated and persisted.  The ``previous``
        salt (if any) is also loaded for the overlap window.

        Args:
            redis_client: Optional Redis client for persistent salt storage.
                When ``None`` the manager operates in-memory only (suitable
                for testing; not recommended for production cross-licensee
                deployments).
        """
        self._redis = redis_client
        self._current: Optional[SaltRecord] = None
        self._previous: Optional[SaltRecord] = None
        self._init_salt()

    def _init_salt(self) -> None:
        """Load the current salt from Redis or generate a new one.

        Called automatically by :meth:`__init__`.  Safe to call again if the
        salt record is ever cleared (e.g., Redis flush during tests).
        """
        loaded = self._load_salt("current")
        if loaded is None:
            salt = os.urandom(32)
            now = datetime.now(tz=timezone.utc)
            self._current = SaltRecord(
                salt=salt,
                created_at=now,
                expires_at=now + timedelta(days=ROTATION_INTERVAL_DAYS),
            )
            self._store_salt("current", self._current)
        else:
            self._current = loaded
        self._previous = self._load_salt("previous")

    def get_current_salt(self) -> bytes:
        """Return the active 32-byte salt for hashing new entity identifiers.

        Re-initialises the manager if the current salt record is missing
        (defensive guard against in-memory resets).

        Returns:
            Active salt bytes.
        """
        if self._current is None:
            self._init_salt()
        return self._current.salt  # type: ignore[union-attr]

    def get_previous_salt(self) -> Optional[bytes]:
        """Returns previous salt only during the 30-day overlap window."""
        if self._previous is None:
            return None
        if not self.is_in_overlap_period():
            return None
        return self._previous.salt

    def rotate_salt(self) -> Tuple[bytes, bytes]:
        """Generates new salt, promotes current to previous. Returns (new, old)."""
        old_salt = self.get_current_salt()
        new_salt = os.urandom(32)
        now = datetime.now(tz=timezone.utc)
        self._previous = self._current
        self._previous.is_active = False  # type: ignore[union-attr]
        self._store_salt("previous", self._previous)
        self._current = SaltRecord(
            salt=new_salt,
            created_at=now,
            expires_at=now + timedelta(days=ROTATION_INTERVAL_DAYS),
        )
        self._store_salt("current", self._current)
        logger.info("Salt rotated at %s", now.isoformat())
        return new_salt, old_salt

    def is_in_overlap_period(self) -> bool:
        """True if within OVERLAP_DAYS of the last rotation."""
        if self._previous is None:
            return False
        cutoff = self._current.created_at + timedelta(days=OVERLAP_DAYS)  # type: ignore[union-attr]
        return datetime.now(tz=timezone.utc) < cutoff

    def hash_with_current(self, value: str) -> str:
        """Compute SHA-256(value + current_salt) hex digest.

        Use for all new entity/beneficiary hashes in normal operation.

        Args:
            value: Raw string to hash (e.g., entity ID or BIC).

        Returns:
            Lowercase 64-character hex digest.
        """
        return hashlib.sha256(value.encode() + self.get_current_salt()).hexdigest()

    def hash_with_previous(self, value: str) -> Optional[str]:
        """Compute SHA-256(value + previous_salt) only within the overlap window.

        Returns ``None`` outside the 30-day overlap window or when no previous
        salt exists.  Used to re-hash legacy records during the transition
        period before they expire from the rolling window.

        Args:
            value: Raw string to hash.

        Returns:
            Lowercase 64-character hex digest, or ``None`` outside the overlap
            window.
        """
        prev = self.get_previous_salt()
        if prev is None:
            return None
        return hashlib.sha256(value.encode() + prev).hexdigest()

    def check_and_rotate_if_needed(self) -> bool:
        """Rotate the salt if the current record has passed its expiry date.

        Intended to be called periodically (e.g., daily cron job) rather than
        on every request.

        Returns:
            ``True`` if a rotation was performed, ``False`` otherwise.
        """
        if self._current is None:
            self._init_salt()
        if datetime.now(tz=timezone.utc) >= self._current.expires_at:  # type: ignore[union-attr]
            self.rotate_salt()
            return True
        return False

    def _store_salt(self, key: str, record: SaltRecord) -> None:
        """Persist a salt record to Redis with an appropriate TTL.

        ``current`` records are stored with a ``ROTATION_INTERVAL_DAYS``
        TTL; ``previous`` records with an ``OVERLAP_DAYS`` TTL so they
        expire automatically after the overlap window closes.

        Args:
            key: Redis sub-key suffix — ``'current'`` or ``'previous'``.
            record: :class:`SaltRecord` to serialise and store.
        """
        if self._redis:
            import json
            data = {
                "salt": record.salt.hex(),
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
                "is_active": record.is_active,
            }
            ttl = OVERLAP_DAYS * 86400 if key == "previous" else ROTATION_INTERVAL_DAYS * 86400
            self._redis.setex(f"lip:salt:{key}", ttl, json.dumps(data))

    def _load_salt(self, key: str) -> Optional[SaltRecord]:
        """Load and deserialise a salt record from Redis.

        Returns ``None`` when no Redis client is configured or when the key
        does not exist (e.g., first boot or after TTL expiry).

        Args:
            key: Redis sub-key suffix — ``'current'`` or ``'previous'``.

        Returns:
            Deserialised :class:`SaltRecord`, or ``None`` if unavailable.
        """
        if self._redis:
            import json
            raw = self._redis.get(f"lip:salt:{key}")
            if raw is None:
                return None
            data = json.loads(raw)
            return SaltRecord(
                salt=bytes.fromhex(data["salt"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                is_active=data["is_active"],
            )
        return None
