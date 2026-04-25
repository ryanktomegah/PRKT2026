"""
test_velocity_bridge_redis_routing.py — Phase 2 T2.2b.

When a ``redis_client`` is passed to :class:`RustVelocityChecker`, the bridge
must route to the Python + Redis path for multi-replica safety, even when the
Rust extension is available. The Rust DashMap has no Redis sync, so using
Rust with a redis_client would silently lose distributed consistency — that
is the specific failure mode this routing fix prevents (B7-02 / T2.2b).

These tests assert:
  1. Passing a redis_client does NOT require single_replica=True (safe by default).
  2. Passing a redis_client uses the Python path (``self._rust_vel is None``)
     regardless of whether Rust is loaded in this process.
  3. Passing neither redis_client nor single_replica=True still raises.
  4. The Python+Redis path produces the same VelocityResult shape as the
     other paths — no interface drift.
"""
from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from lip.c6_aml_velocity.velocity_bridge import RustVelocityChecker

_SALT = b"t2_2b_velocity_bridge_test_salt_"


# ---------------------------------------------------------------------------
# Minimal Redis fake — ZADD/ZRANGEBYSCORE/ZREMRANGEBYSCORE + pipeline + eval
# ---------------------------------------------------------------------------

class _FakeRedisZSet:
    """Subset of ``redis.Redis`` used by RollingWindow in velocity.py.

    Reuses the zset semantics: score-ordered members under one key, with
    ``zadd``, ``zrangebyscore``, ``zremrangebyscore``, and ``pipeline``."""

    def __init__(self) -> None:
        self._zsets: dict[str, list[tuple[float, str]]] = {}
        self._lock = threading.Lock()

    # --- primitives -------------------------------------------------------

    def zadd(self, key: str, mapping: dict) -> int:
        with self._lock:
            bucket = self._zsets.setdefault(key, [])
            added = 0
            for member, score in mapping.items():
                bucket.append((float(score), str(member)))
                added += 1
            bucket.sort()
            return added

    def expire(self, key: str, seconds: int) -> bool:
        return True  # TTL not simulated

    def zremrangebyscore(self, key: str, min_score, max_score) -> int:
        with self._lock:
            bucket = self._zsets.get(key, [])
            lo = float("-inf") if min_score in ("-inf", float("-inf")) else float(min_score)
            hi = float("inf") if max_score in ("+inf", float("inf")) else float(max_score)
            before = len(bucket)
            self._zsets[key] = [(s, m) for (s, m) in bucket if not (lo <= s <= hi)]
            return before - len(self._zsets[key])

    def zrangebyscore(self, key: str, min_score, max_score, withscores: bool = False):
        with self._lock:
            bucket = self._zsets.get(key, [])
            lo = float("-inf") if min_score in ("-inf", float("-inf")) else float(min_score)
            hi = float("inf") if max_score in ("+inf", float("inf")) else float(max_score)
            out = [(m, s) for (s, m) in bucket if lo <= s <= hi]
            if withscores:
                return [(m.encode("utf-8"), s) for (m, s) in out]
            return [m.encode("utf-8") for (m, _s) in out]

    # --- Lua eval (used by check_and_record atomic path) ------------------

    def eval(self, script: str, num_keys: int, *args):
        # The Lua script issues ZREMRANGEBYSCORE + ZRANGE + (conditional) ZADD.
        # The test does not exercise check_and_record on Redis path in this
        # suite — if it does, this method raises so the gap is obvious.
        raise AssertionError(
            "FakeRedisZSet.eval called — extend this fake to cover "
            "check_and_record Lua before asserting against it."
        )

    # --- pipeline ---------------------------------------------------------

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis: _FakeRedisZSet) -> None:
        self._r = redis
        self._ops: list[tuple[str, tuple, dict]] = []

    def zadd(self, *args, **kwargs):
        self._ops.append(("zadd", args, kwargs))
        return self

    def expire(self, *args, **kwargs):
        self._ops.append(("expire", args, kwargs))
        return self

    def zremrangebyscore(self, *args, **kwargs):
        self._ops.append(("zremrangebyscore", args, kwargs))
        return self

    def zrangebyscore(self, *args, **kwargs):
        self._ops.append(("zrangebyscore", args, kwargs))
        return self

    def execute(self):
        results = []
        for name, args, kwargs in self._ops:
            results.append(getattr(self._r, name)(*args, **kwargs))
        self._ops.clear()
        return results


# ---------------------------------------------------------------------------
# Routing behaviour
# ---------------------------------------------------------------------------

class TestRedisClientRouting:

    def test_redis_client_does_not_require_single_replica(self):
        """Safe-by-default: passing a redis_client implies multi-replica safety."""
        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        assert checker is not None

    def test_redis_client_routes_to_python_path(self):
        """Rust bridge must be bypassed when redis_client is provided — Rust
        has no Redis sync, so keeping it would silently drop distributed state."""
        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        assert checker._rust_vel is None, (
            "With redis_client, Rust path must be bypassed regardless of "
            "_RUST_AVAILABLE — otherwise multi-replica state is silently lost"
        )
        assert checker._py_vel is not None

    def test_redis_client_sets_uses_redis_flag(self):
        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        assert checker._uses_redis is True

    def test_no_redis_no_flag_still_rejected(self):
        with pytest.raises(ValueError, match="single_replica"):
            RustVelocityChecker(salt=_SALT)

    def test_single_replica_without_redis_uses_in_memory(self):
        checker = RustVelocityChecker(salt=_SALT, single_replica=True)
        assert checker._uses_redis is False
        # Either Rust or Python in-memory depending on extension availability —
        # both modes expose the same interface.
        assert (checker._rust_vel is not None) or (checker._py_vel is not None)


# ---------------------------------------------------------------------------
# Python+Redis path produces the same VelocityResult shape
# ---------------------------------------------------------------------------

class TestRedisPathResultShape:

    def test_check_returns_velocity_result_shape(self):
        from lip.c6_aml_velocity.velocity import VelocityResult

        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        result = checker.check(
            entity_id="BIC-TEST",
            amount=Decimal("1000.00"),
            beneficiary_id="BENE-1",
            dollar_cap_override=Decimal("1000000"),
            count_cap_override=1000,
        )
        assert isinstance(result, VelocityResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "entity_id_hash")
        assert hasattr(result, "dollar_volume_24h")
        assert hasattr(result, "count_24h")

    def test_record_then_check_sees_volume(self):
        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        checker.record(
            entity_id="BIC-TEST",
            amount=Decimal("5000.00"),
            beneficiary_id="BENE-1",
        )
        result = checker.check(
            entity_id="BIC-TEST",
            amount=Decimal("100.00"),
            beneficiary_id="BENE-1",
            dollar_cap_override=Decimal("1000000"),
            count_cap_override=1000,
        )
        assert result.dollar_volume_24h >= Decimal("5000.00")
        assert result.count_24h >= 1

    def test_get_rust_metrics_empty_in_redis_mode(self):
        fake = _FakeRedisZSet()
        checker = RustVelocityChecker(salt=_SALT, redis_client=fake)
        assert checker.get_rust_metrics() == {}
