"""
test_structuring_detector_redis.py — Phase 2 T2.2c.

Verifies the Redis-backed StructuringDetector path:
  * Per-entity Redis hash with tenant-scoped fields accumulates volume
    via HINCRBYFLOAT (atomic at the hash-field level).
  * Cross-tenant read via HGETALL returns the correct combined-volume
    / tenant-count view for the check() call.
  * Redis mode does not require single_replica=True and is rejected
    if both modes are passed together.

Uses an in-process hash fake rather than a live Redis server; live-Redis
coverage lives in test_e2e_live.py (``@pytest.mark.live``).
"""
from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from lip.c6_aml_velocity.tenant_velocity import StructuringDetector

# ---------------------------------------------------------------------------
# Minimal Redis fake for HINCRBYFLOAT / HGETALL / pipeline
# ---------------------------------------------------------------------------

class _FakeRedisHash:
    """Subset of ``redis.Redis`` used by StructuringDetector."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def hincrbyfloat(self, key: str, field: str, amount: float) -> float:
        with self._lock:
            bucket = self._hashes.setdefault(key, {})
            cur = float(bucket.get(field, "0"))
            nxt = cur + amount
            bucket[field] = repr(nxt)
            return nxt

    def hgetall(self, key: str) -> dict:
        with self._lock:
            bucket = self._hashes.get(key, {})
            # Real redis returns bytes — mimic that so _decode is exercised
            return {
                k.encode("utf-8"): v.encode("utf-8")
                for k, v in bucket.items()
            }

    def expire(self, key: str, seconds: int) -> bool:
        return True  # TTL not simulated

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, r: _FakeRedisHash) -> None:
        self._r = r
        self._ops: list[tuple[str, tuple]] = []

    def hincrbyfloat(self, *args):
        self._ops.append(("hincrbyfloat", args))
        return self

    def expire(self, *args):
        self._ops.append(("expire", args))
        return self

    def execute(self):
        results = []
        for name, args in self._ops:
            results.append(getattr(self._r, name)(*args))
        self._ops.clear()
        return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConstructorGuards:

    def test_redis_mode_does_not_require_single_replica(self):
        d = StructuringDetector(redis_client=_FakeRedisHash())
        assert d is not None

    def test_both_modes_is_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            StructuringDetector(single_replica=True, redis_client=_FakeRedisHash())

    def test_neither_mode_is_rejected(self):
        with pytest.raises(ValueError, match="single_replica"):
            StructuringDetector()


class TestRedisRecordAndCheck:

    def test_single_tenant_not_flagged(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        d.record("ent-hash-1", "TENANT_A", Decimal("50000"))
        result = d.check("ent-hash-1", dollar_cap=Decimal("10000"))
        assert result.tenant_count == 1
        assert result.combined_volume == Decimal("50000")
        assert result.flagged is False  # only 1 tenant

    def test_two_tenants_over_cap_flagged(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        d.record("ent-hash-1", "TENANT_A", Decimal("6000"))
        d.record("ent-hash-1", "TENANT_B", Decimal("5000"))
        result = d.check("ent-hash-1", dollar_cap=Decimal("10000"))
        assert result.tenant_count == 2
        assert result.combined_volume == Decimal("11000")
        assert result.flagged is True

    def test_two_tenants_below_cap_not_flagged(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        d.record("ent-hash-1", "TENANT_A", Decimal("1000"))
        d.record("ent-hash-1", "TENANT_B", Decimal("2000"))
        result = d.check("ent-hash-1", dollar_cap=Decimal("10000"))
        assert result.tenant_count == 2
        assert result.flagged is False

    def test_unlimited_cap_never_flagged(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        d.record("ent-hash-1", "TENANT_A", Decimal("10_000_000"))
        d.record("ent-hash-1", "TENANT_B", Decimal("10_000_000"))
        result = d.check("ent-hash-1", dollar_cap=Decimal("0"))
        assert result.tenant_count == 2
        assert result.flagged is False  # cap=0 means unlimited

    def test_tenant_set_preserved_across_record_calls(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        d.record("ent-hash-1", "TENANT_A", Decimal("100"))
        d.record("ent-hash-1", "TENANT_A", Decimal("200"))
        d.record("ent-hash-1", "TENANT_B", Decimal("50"))
        result = d.check("ent-hash-1", dollar_cap=Decimal("10000"))
        assert result.tenants == frozenset({"TENANT_A", "TENANT_B"})
        assert result.combined_volume == Decimal("350")

    def test_unknown_entity_returns_zero_state(self):
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)
        result = d.check("no-such-entity", dollar_cap=Decimal("10000"))
        assert result.tenant_count == 0
        assert result.combined_volume == Decimal("0")
        assert result.tenants == frozenset()
        assert result.flagged is False


class TestRedisAtomicity:

    def test_hincrbyfloat_is_atomic_under_concurrency(self):
        """FATF R.21: the same entity appearing across tenants concurrently
        must produce the correct combined-volume view even when many threads
        record at once. HINCRBYFLOAT provides field-level atomicity at the
        Redis server — the fake mirrors that with a lock."""
        r = _FakeRedisHash()
        d = StructuringDetector(redis_client=r)

        def worker(tenant: str, amount: Decimal, n: int) -> None:
            for _ in range(n):
                d.record("ent-concurrent", tenant, amount)

        threads = [
            threading.Thread(target=worker, args=("TENANT_A", Decimal("1"), 100)),
            threading.Thread(target=worker, args=("TENANT_B", Decimal("1"), 100)),
            threading.Thread(target=worker, args=("TENANT_C", Decimal("1"), 100)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = d.check("ent-concurrent", dollar_cap=Decimal("500"))
        assert result.tenant_count == 3
        assert result.combined_volume == Decimal("300")
        assert result.flagged is False  # 300 < 500 cap
