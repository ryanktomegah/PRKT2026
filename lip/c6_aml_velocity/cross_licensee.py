"""
cross_licensee.py — SHA-256 hashed cross-licensee velocity aggregation.
Privacy-preserving: entities cannot be de-anonymized across licensees.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


def cross_licensee_hash(tax_id: str, salt: bytes) -> str:
    """SHA-256(tax_id + salt). Hex digest. Never returns raw tax_id."""
    return hashlib.sha256(tax_id.encode() + salt).hexdigest()


class CrossLicenseeAggregator:
    """Aggregates velocity across licensees using privacy-preserving hashes."""

    def __init__(self, salt: bytes, shared_redis_client=None):
        self.salt = salt
        self._redis = shared_redis_client
        self._store: dict = {}

    def _make_key(self, hashed_id: str, metric: str) -> str:
        return f"lip:cl_velocity:{hashed_id}:{metric}"

    def get_cross_licensee_volume(self, tax_id: str) -> Decimal:
        hashed = cross_licensee_hash(tax_id, self.salt)
        key = self._make_key(hashed, "volume")
        if self._redis:
            val = self._redis.get(key)
            return Decimal(val.decode()) if val else Decimal("0")
        return Decimal(self._store.get(key, "0"))

    def get_cross_licensee_count(self, tax_id: str) -> int:
        hashed = cross_licensee_hash(tax_id, self.salt)
        key = self._make_key(hashed, "count")
        if self._redis:
            val = self._redis.get(key)
            return int(val) if val else 0
        return int(self._store.get(key, 0))

    def record(self, tax_id: str, amount: Decimal) -> None:
        hashed = cross_licensee_hash(tax_id, self.salt)
        vol_key = self._make_key(hashed, "volume")
        cnt_key = self._make_key(hashed, "count")
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incrbyfloat(vol_key, float(amount))
            pipe.incr(cnt_key)
            pipe.execute()
        else:
            self._store[vol_key] = str(Decimal(self._store.get(vol_key, "0")) + amount)
            self._store[cnt_key] = int(self._store.get(cnt_key, 0)) + 1
        logger.debug("Cross-licensee record: hash=%s amount=%s", hashed[:8], amount)
