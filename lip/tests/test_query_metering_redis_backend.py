"""
test_query_metering_redis_backend.py — Phase 2 T2.2a.

Verifies :class:`_RedisMeteringBackend` performs an atomic check-and-increment
across the query and epsilon counters via the Lua script, and that
``RegulatoryQueryMetering`` constructed with ``redis_client=`` uses the Redis
backend end-to-end.

Uses a minimal in-process Redis fake (``_FakeRedis``) that implements just the
subset of commands the backend issues: ``eval``, ``get``, ``set``, ``incr``,
``rpush``, ``lrange``, ``expire``. The Lua script is interpreted by a tiny
Python port so the test does not depend on a live Redis server — every
behaviour the production code observes goes through the same interface.

Live-Redis coverage is deferred to ``test_e2e_live.py`` (infrastructure
required, marked ``@pytest.mark.live``).
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lip.c8_license_manager.query_metering import (
    PrivacyBudgetExceededError,
    QueryBudgetExceededError,
    QueryMeterEntry,
    RegulatoryQueryMetering,
    _RedisMeteringBackend,
)
from lip.c8_license_manager.regulator_subscription import RegulatorSubscriptionToken

_METERING_KEY = b"redis_backend_test_key_32bytes!!"


# ---------------------------------------------------------------------------
# Minimal Redis fake
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Subset of the ``redis.Redis`` surface used by the metering backend.

    Emulates the Lua script's transactional semantics by acquiring a lock
    around ``eval``: the real Redis evaluates Lua atomically on a single
    thread, so this fake serialises ``eval`` calls to reproduce that."""

    def __init__(self) -> None:
        self._store: dict[str, str | list[str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        v = self._store.get(key)
        if v is None or isinstance(v, list):
            return None
        return v.encode("utf-8")

    def set(self, key: str, value: str) -> bool:
        self._store[key] = str(value)
        return True

    def incr(self, key: str) -> int:
        cur = int(self._store.get(key, "0"))
        cur += 1
        self._store[key] = str(cur)
        return cur

    def rpush(self, key: str, value: str) -> int:
        lst = self._store.setdefault(key, [])
        assert isinstance(lst, list)
        lst.append(value)
        return len(lst)

    def lrange(self, key: str, start: int, stop: int):
        lst = self._store.get(key, [])
        if not isinstance(lst, list):
            return []
        if stop == -1:
            sliced = lst[start:]
        else:
            sliced = lst[start:stop + 1]
        return [s.encode("utf-8") for s in sliced]

    def expire(self, key: str, seconds: int) -> bool:
        # TTL is not simulated — the real backend contract is "set expiry,
        # don't observe it." Tests asserting TTL are in the live suite.
        return True

    def eval(self, script: str, num_keys: int, *args):  # noqa: D401
        """Interpret the metering Lua script. Any other script is rejected."""
        if "atomic_record" not in script and "q_key" not in script:
            raise AssertionError("Unexpected Lua script passed to _FakeRedis")
        with self._lock:
            keys = args[:num_keys]
            argv = args[num_keys:]
            q_key, e_key, list_key = keys
            max_q = int(argv[0])
            max_e = float(argv[1])
            e_cost = float(argv[2])
            entry_json = argv[3]
            ttl = int(argv[4])

            q_raw = self._store.get(q_key)
            q = int(q_raw) if isinstance(q_raw, str) else 0
            e_raw = self._store.get(e_key)
            e = float(e_raw) if isinstance(e_raw, str) else 0.0

            if q + 1 > max_q:
                return [b"0", b"query_budget", str(q).encode(), repr(e).encode()]
            e_next = e + e_cost
            if e_next > max_e + 1e-12:
                return [b"0", b"privacy_budget", str(q).encode(), repr(e).encode()]

            self._store[q_key] = str(q + 1)
            self._store[e_key] = repr(e_next)
            lst = self._store.setdefault(list_key, [])
            assert isinstance(lst, list)
            lst.append(entry_json)
            # ttl is a no-op in the fake
            _ = ttl
            return [b"1", b"ok", str(q + 1).encode(), repr(e_next).encode()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_token(
    *, query_budget: int = 100, privacy_budget: float = 10.0
) -> RegulatorSubscriptionToken:
    now = datetime.now(timezone.utc)
    return RegulatorSubscriptionToken(
        regulator_id="REG-REDIS-001",
        regulator_name="Redis Test Regulator",
        subscription_tier="standard",
        permitted_corridors=None,
        query_budget_monthly=query_budget,
        privacy_budget_allocation=privacy_budget,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
    )


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def meter(fake_redis):
    return RegulatoryQueryMetering(
        metering_key=_METERING_KEY,
        redis_client=fake_redis,
    )


# ---------------------------------------------------------------------------
# Constructor guards
# ---------------------------------------------------------------------------

class TestConstructorGuards:

    def test_redis_mode_does_not_require_single_replica(self, fake_redis):
        meter = RegulatoryQueryMetering(
            metering_key=_METERING_KEY,
            redis_client=fake_redis,
        )
        assert meter is not None

    def test_both_modes_is_rejected(self, fake_redis):
        with pytest.raises(ValueError, match="exactly one"):
            RegulatoryQueryMetering(
                metering_key=_METERING_KEY,
                single_replica=True,
                redis_client=fake_redis,
            )

    def test_neither_mode_is_rejected(self):
        with pytest.raises(ValueError, match="single_replica"):
            RegulatoryQueryMetering(metering_key=_METERING_KEY)

    def test_empty_metering_key_rejected_in_redis_mode(self, fake_redis):
        with pytest.raises(ValueError, match="metering_key"):
            RegulatoryQueryMetering(metering_key=b"", redis_client=fake_redis)


# ---------------------------------------------------------------------------
# End-to-end behaviour via the public API
# ---------------------------------------------------------------------------

class TestRecordQueryThroughRedis:

    def test_record_query_returns_entry_with_signature(self, meter):
        token = _make_token()
        entry = meter.record_query(
            token=token,
            endpoint="/corridors",
            corridors_queried=["USD_EUR"],
            epsilon_consumed=0.1,
            response_latency_ms=10,
            billing_amount_usd=Decimal("0.05"),
        )
        assert isinstance(entry, QueryMeterEntry)
        assert entry.hmac_signature  # non-empty

    def test_usage_counts_increment(self, meter):
        token = _make_token()
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=[],
            epsilon_consumed=0.1, response_latency_ms=1,
            billing_amount_usd=Decimal("0.01"),
        )
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=[],
            epsilon_consumed=0.2, response_latency_ms=1,
            billing_amount_usd=Decimal("0.01"),
        )
        usage = meter.get_usage(token.regulator_id)
        assert usage["query_count"] == 2
        assert abs(usage["epsilon_consumed"] - 0.3) < 1e-9

    def test_query_budget_blocks_further_queries(self, meter):
        token = _make_token(query_budget=2)
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=[],
            epsilon_consumed=0.1, response_latency_ms=1,
            billing_amount_usd=Decimal("0.01"),
        )
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=[],
            epsilon_consumed=0.1, response_latency_ms=1,
            billing_amount_usd=Decimal("0.01"),
        )
        with pytest.raises(QueryBudgetExceededError):
            meter.record_query(
                token=token, endpoint="/a", corridors_queried=[],
                epsilon_consumed=0.1, response_latency_ms=1,
                billing_amount_usd=Decimal("0.01"),
            )

    def test_privacy_budget_blocks_further_queries(self, meter):
        token = _make_token(privacy_budget=0.3)
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=[],
            epsilon_consumed=0.2, response_latency_ms=1,
            billing_amount_usd=Decimal("0.01"),
        )
        with pytest.raises(PrivacyBudgetExceededError):
            meter.record_query(
                token=token, endpoint="/a", corridors_queried=[],
                epsilon_consumed=0.2, response_latency_ms=1,
                billing_amount_usd=Decimal("0.01"),
            )

    def test_billing_summary_reads_entries_from_redis(self, meter):
        token = _make_token()
        meter.record_query(
            token=token, endpoint="/a", corridors_queried=["USD_EUR"],
            epsilon_consumed=0.1, response_latency_ms=12,
            billing_amount_usd=Decimal("0.05"),
        )
        meter.record_query(
            token=token, endpoint="/b", corridors_queried=["EUR_JPY"],
            epsilon_consumed=0.1, response_latency_ms=20,
            billing_amount_usd=Decimal("0.05"),
        )
        summary = meter.get_billing_summary(token.regulator_id)
        assert summary["query_count"] == 2
        assert sorted(summary["corridors_queried"]) == ["EUR_JPY", "USD_EUR"]
        assert summary["endpoints_breakdown"] == {"/a": 1, "/b": 1}
        assert Decimal(summary["total_billing_usd"]) == Decimal("0.10")


# ---------------------------------------------------------------------------
# Budget-race regression (B3-01 preserved in Redis mode)
# ---------------------------------------------------------------------------

class TestBudgetRaceUnderConcurrency:
    """B3-01: the Lua script must serialise concurrent record_query calls so
    that exactly query_budget_monthly queries succeed and the rest are
    rejected — no two threads can slip past the check simultaneously."""

    def _worker(self, meter, token, results, idx):
        try:
            meter.record_query(
                token=token, endpoint="/a", corridors_queried=[],
                epsilon_consumed=0.01, response_latency_ms=1,
                billing_amount_usd=Decimal("0.01"),
            )
            results[idx] = True
        except QueryBudgetExceededError:
            results[idx] = False

    def test_query_budget_race_redis_backend(self, meter):
        token = _make_token(query_budget=10, privacy_budget=10.0)
        n_threads = 50
        results = [None] * n_threads
        threads = [
            threading.Thread(target=self._worker, args=(meter, token, results, i))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        accepted = sum(1 for r in results if r is True)
        assert accepted == 10, f"expected exactly 10 accepted, got {accepted}"


# ---------------------------------------------------------------------------
# Backend-level directed tests
# ---------------------------------------------------------------------------

class TestRedisBackendDirect:
    """Direct unit tests on the backend to lock down the Lua-interpretation
    edge cases the public API doesn't surface."""

    def test_get_usage_returns_zero_for_missing_bucket(self, fake_redis):
        backend = _RedisMeteringBackend(fake_redis)
        usage = backend.get_usage("REG-MISSING", "2026-04")
        assert usage == {"query_count": 0, "epsilon_consumed": 0.0}

    def test_entries_persist_after_multiple_records(self, fake_redis, meter):
        token = _make_token()
        for _ in range(3):
            meter.record_query(
                token=token, endpoint="/a", corridors_queried=[],
                epsilon_consumed=0.1, response_latency_ms=1,
                billing_amount_usd=Decimal("0.01"),
            )
        backend = _RedisMeteringBackend(fake_redis)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        entries = backend.get_monthly_entries(token.regulator_id, month)
        assert len(entries) == 3
        for e in entries:
            assert e.regulator_id == token.regulator_id
