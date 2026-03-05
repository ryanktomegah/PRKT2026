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
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ROTATION_INTERVAL_DAYS = 365
OVERLAP_DAYS = 30


@dataclass
class SaltRecord:
    salt: bytes
    created_at: datetime
    expires_at: datetime
    is_active: bool = True


class SaltRotationManager:
    """Manages annual salt rotation with 30-day dual-salt overlap."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._current: Optional[SaltRecord] = None
        self._previous: Optional[SaltRecord] = None
        self._init_salt()

    def _init_salt(self) -> None:
        loaded = self._load_salt("current")
        if loaded is None:
            salt = os.urandom(32)
            now = datetime.utcnow()
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
        now = datetime.utcnow()
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
        return datetime.utcnow() < cutoff

    def hash_with_current(self, value: str) -> str:
        return hashlib.sha256(value.encode() + self.get_current_salt()).hexdigest()

    def hash_with_previous(self, value: str) -> Optional[str]:
        prev = self.get_previous_salt()
        if prev is None:
            return None
        return hashlib.sha256(value.encode() + prev).hexdigest()

    def check_and_rotate_if_needed(self) -> bool:
        if self._current is None:
            self._init_salt()
        if datetime.utcnow() >= self._current.expires_at:  # type: ignore[union-attr]
            self.rotate_salt()
            return True
        return False

    def _store_salt(self, key: str, record: SaltRecord) -> None:
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
