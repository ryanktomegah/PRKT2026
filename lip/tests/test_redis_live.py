"""
test_redis_live.py — Live Redis integration tests for C6 velocity components.

Requires a running Redis instance:
    docker compose up redis -d

Run with:
    PYTHONPATH=. python -m pytest lip/tests/test_redis_live.py -m live -v

All tests are skipped automatically when Redis is unavailable.
"""
import os
import time
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# Skip the entire module when Redis is unreachable or REDIS_URL is unset
# ---------------------------------------------------------------------------

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    import redis as _redis_module
    _client = _redis_module.Redis.from_url(
        _REDIS_URL,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
        decode_responses=False,
    )
    _client.ping()
    _REDIS_AVAILABLE = True
except Exception:
    _REDIS_AVAILABLE = False

pytestmark = pytest.mark.live

_skip_no_redis = pytest.mark.skipif(
    not _REDIS_AVAILABLE,
    reason="Redis not reachable — start with `docker compose up redis -d`",
)


@pytest.fixture(scope="module")
def redis_client():
    client = _redis_module.Redis.from_url(
        _REDIS_URL,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
        decode_responses=False,
    )
    yield client
    # Cleanup test keys
    for key in client.scan_iter("lip:velocity:events:test_*"):
        client.delete(key)
    for key in client.scan_iter("lip:salt:*test*"):
        client.delete(key)


# ---------------------------------------------------------------------------
# RollingWindow CRUD
# ---------------------------------------------------------------------------

@_skip_no_redis
def test_rolling_window_add_and_get(redis_client):
    from lip.c6_aml_velocity.velocity import RollingWindow

    window = RollingWindow(window_seconds=86400, redis_client=redis_client)
    entity_hash = "test_entity_001"
    bene_hash = "test_bene_001"

    # Clean up before test
    key = f"lip:velocity:events:{entity_hash}"
    redis_client.delete(key)

    window.add(entity_hash, Decimal("1000.00"), bene_hash)
    window.add(entity_hash, Decimal("2000.00"), bene_hash)

    records = window.get_records(entity_hash)
    assert len(records) == 2
    total = sum(r[1] for r in records)
    assert total == Decimal("3000.00")

    vol = window.get_volume(entity_hash)
    assert vol == Decimal("3000.00")

    count = window.get_count(entity_hash)
    assert count == 2

    redis_client.delete(key)


@_skip_no_redis
def test_rolling_window_expiry(redis_client):
    from lip.c6_aml_velocity.velocity import RollingWindow

    # 2-second window
    window = RollingWindow(window_seconds=2, redis_client=redis_client)
    entity_hash = "test_entity_expiry"
    key = f"lip:velocity:events:{entity_hash}"
    redis_client.delete(key)

    window.add(entity_hash, Decimal("500.00"), "bene_x")
    assert window.get_count(entity_hash) == 1

    time.sleep(3)  # let window expire
    assert window.get_count(entity_hash) == 0

    redis_client.delete(key)


# ---------------------------------------------------------------------------
# Atomic Lua script
# ---------------------------------------------------------------------------

@_skip_no_redis
def test_atomic_check_and_record_passes(redis_client):
    from lip.c6_aml_velocity.velocity import RollingWindow

    window = RollingWindow(window_seconds=86400, redis_client=redis_client)
    entity_hash = "test_atomic_pass"
    key = f"lip:velocity:events:{entity_hash}"
    redis_client.delete(key)

    dollar_cap = Decimal("1000000")
    count_cap = 100
    passed, reason, vol, cnt = window.atomic_check_and_add(
        entity_hash, "bene_hash_abc", Decimal("50000"), dollar_cap, count_cap
    )
    assert passed is True
    assert reason == ""
    assert cnt == 0  # no prior records
    assert vol == Decimal("0")

    redis_client.delete(key)


@_skip_no_redis
def test_atomic_check_and_record_dollar_cap_blocked(redis_client):
    from lip.c6_aml_velocity.velocity import RollingWindow

    window = RollingWindow(window_seconds=86400, redis_client=redis_client)
    entity_hash = "test_atomic_dollar_cap"
    key = f"lip:velocity:events:{entity_hash}"
    redis_client.delete(key)

    dollar_cap = Decimal("100")
    count_cap = 1000

    # First pass: $90 — ok
    passed, _, _, _ = window.atomic_check_and_add(
        entity_hash, "bene_a", Decimal("90"), dollar_cap, count_cap
    )
    assert passed is True

    # Second: $90 — would bring total to $180, exceeds $100 cap
    passed, reason, _, _ = window.atomic_check_and_add(
        entity_hash, "bene_b", Decimal("90"), dollar_cap, count_cap
    )
    assert passed is False
    assert reason == "DOLLAR_CAP_EXCEEDED"

    redis_client.delete(key)


@_skip_no_redis
def test_atomic_lua_decimal_precision(redis_client):
    """Lua script handles Decimal amounts without floating-point drift."""
    from lip.c6_aml_velocity.velocity import RollingWindow

    window = RollingWindow(window_seconds=86400, redis_client=redis_client)
    entity_hash = "test_atomic_precision"
    key = f"lip:velocity:events:{entity_hash}"
    redis_client.delete(key)

    amount = Decimal("999999.99")
    cap = Decimal("1000000.00")
    passed, reason, vol, _ = window.atomic_check_and_add(
        entity_hash, "bene_prec", amount, cap, 1000
    )
    assert passed is True
    # A second transaction of $0.02 should push total over $1M
    passed2, reason2, _, _ = window.atomic_check_and_add(
        entity_hash, "bene_prec2", Decimal("0.02"), cap, 1000
    )
    assert passed2 is False
    assert reason2 == "DOLLAR_CAP_EXCEEDED"

    redis_client.delete(key)


# ---------------------------------------------------------------------------
# SaltRotation persist/reload
# ---------------------------------------------------------------------------

@_skip_no_redis
def test_salt_rotation_persist_and_reload(redis_client):
    from lip.c6_aml_velocity.salt_rotation import SaltRotation

    # Flush test salt keys
    for key in [b"lip:salt:current", b"lip:salt:previous"]:
        redis_client.delete(key)

    rotation = SaltRotation(redis_client=redis_client)
    salt1 = rotation.current_salt()

    # Reload from Redis — should return same salt
    rotation2 = SaltRotation(redis_client=redis_client)
    salt2 = rotation2.current_salt()
    assert salt1 == salt2

    for key in [b"lip:salt:current", b"lip:salt:previous"]:
        redis_client.delete(key)


# ---------------------------------------------------------------------------
# CrossLicensee aggregation
# ---------------------------------------------------------------------------

@_skip_no_redis
def test_cross_licensee_isolation(redis_client):
    from lip.c6_aml_velocity.velocity import VelocityChecker

    salt_a = b"licensee_a_salt_test"
    salt_b = b"licensee_b_salt_test"

    checker_a = VelocityChecker(salt=salt_a, redis_client=redis_client)
    checker_b = VelocityChecker(salt=salt_b, redis_client=redis_client)

    # Same entity_id should produce different hashes for different licensees
    entity_id = "BNPAFRPPXXX"
    hash_a = checker_a._hash_entity(entity_id)
    hash_b = checker_b._hash_entity(entity_id)

    assert hash_a != hash_b, "Cross-licensee isolation: same entity must hash differently per salt"

    # Clean up any keys created
    for h in [hash_a, hash_b]:
        redis_client.delete(f"lip:velocity:events:{h}")
