"""
test_kill_switch_comprehensive.py — Comprehensive KillSwitch coverage tests.

Targets uncovered lines in kill_switch.py (65% -> 90%+):
  - Redis-backed activate / deactivate / is_active (lines 70, 78, 83-84)
  - check_kms success / failure / recovery (lines 88-101)
  - kms_unavailable_gap_seconds calculation (line 118)
  - start_kms_monitor / stop_kms_monitor threading (lines 121-129, 132-135)

All Redis and KMS interactions are mocked; no external services required.
"""
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lip.c7_execution_agent.kill_switch import (
    KillSwitch,
    KillSwitchState,
    KMSState,
    KillSwitchStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_redis():
    """Return a MagicMock that behaves like a minimal Redis client."""
    store: dict[str, bytes] = {}
    redis = MagicMock()

    def _set(key, value):
        store[key] = value.encode() if isinstance(value, str) else value

    def _get(key):
        return store.get(key)

    def _delete(key):
        store.pop(key, None)

    redis.set = MagicMock(side_effect=_set)
    redis.get = MagicMock(side_effect=_get)
    redis.delete = MagicMock(side_effect=_delete)
    return redis


def _mock_kms(*, should_fail: bool = False):
    """Return a MagicMock KMS client whose ping() raises on demand."""
    kms = MagicMock()
    if should_fail:
        kms.ping.side_effect = ConnectionError("KMS unreachable")
    return kms


# ===========================================================================
# 1-2. activate / deactivate in-memory state
# ===========================================================================

class TestActivateDeactivateState:
    def test_activate_sets_state_to_active(self):
        ks = KillSwitch()
        ks.activate("regulatory hold")
        assert ks._kill_switch_state == KillSwitchState.ACTIVE
        assert ks._activated_at is not None
        assert ks._reason == "regulatory hold"

    def test_deactivate_clears_state(self):
        ks = KillSwitch()
        ks.activate("test")
        ks.deactivate()
        assert ks._kill_switch_state == KillSwitchState.INACTIVE
        assert ks._activated_at is None
        assert ks._reason is None


# ===========================================================================
# 3-5. Redis-backed activate / deactivate / is_active
# ===========================================================================

class TestRedisIntegration:
    def test_activate_with_mock_redis(self):
        redis = _mock_redis()
        ks = KillSwitch(redis_client=redis)
        ks.activate("redis test")
        redis.set.assert_called_once_with("lip:kill_switch", "ACTIVE")

    def test_deactivate_with_mock_redis(self):
        redis = _mock_redis()
        ks = KillSwitch(redis_client=redis)
        ks.activate("setup")
        ks.deactivate()
        redis.delete.assert_called_once_with("lip:kill_switch")

    def test_is_active_reads_from_redis(self):
        redis = _mock_redis()
        ks = KillSwitch(redis_client=redis)
        # Before activation, redis returns None -> not active
        assert ks.is_active() is False
        # Activate writes to redis store
        ks.activate("reason")
        assert ks.is_active() is True
        # Deactivate removes from redis store
        ks.deactivate()
        assert ks.is_active() is False

    def test_is_active_redis_returns_non_active_value(self):
        """If redis contains a value that is not 'ACTIVE', is_active returns False."""
        redis = MagicMock()
        redis.get.return_value = b"SOMETHING_ELSE"
        ks = KillSwitch(redis_client=redis)
        assert ks.is_active() is False


# ===========================================================================
# 6-8. check_kms: success / failure / recovery
# ===========================================================================

class TestCheckKMS:
    def test_check_kms_no_client_returns_available(self):
        """When no kms_client is provided, check_kms always returns AVAILABLE."""
        ks = KillSwitch(kms_client=None)
        assert ks.check_kms() == KMSState.AVAILABLE

    def test_check_kms_success_returns_available(self):
        kms = _mock_kms(should_fail=False)
        ks = KillSwitch(kms_client=kms)
        result = ks.check_kms()
        assert result == KMSState.AVAILABLE
        kms.ping.assert_called_once()

    def test_check_kms_failure_returns_unavailable(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        result = ks.check_kms()
        assert result == KMSState.UNAVAILABLE
        assert ks._kms_unavailable_since is not None

    def test_check_kms_failure_sets_unavailable_since_once(self):
        """Repeated failures should not update _kms_unavailable_since after the first."""
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()
        first_ts = ks._kms_unavailable_since
        assert first_ts is not None
        # Second failure should NOT overwrite the timestamp
        ks.check_kms()
        assert ks._kms_unavailable_since == first_ts

    def test_check_kms_recovery_clears_unavailable(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        # First: fail
        ks.check_kms()
        assert ks._kms_state == KMSState.UNAVAILABLE
        assert ks._kms_unavailable_since is not None
        # Now: recover
        kms.ping.side_effect = None  # stop failing
        result = ks.check_kms()
        assert result == KMSState.AVAILABLE
        assert ks._kms_state == KMSState.AVAILABLE
        assert ks._kms_unavailable_since is None


# ===========================================================================
# 9-10. kms_unavailable_gap_seconds
# ===========================================================================

class TestKMSUnavailableGap:
    def test_kms_unavailable_gap_returns_seconds(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()  # triggers unavailability
        gap = ks.kms_unavailable_gap_seconds()
        assert gap is not None
        assert isinstance(gap, float)
        assert gap >= 0.0

    def test_kms_unavailable_gap_none_when_not_unavailable(self):
        ks = KillSwitch()
        assert ks.kms_unavailable_gap_seconds() is None

    def test_kms_unavailable_gap_increases_over_time(self):
        """Gap should be non-decreasing (monotonic) over successive calls."""
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()
        gap1 = ks.kms_unavailable_gap_seconds()
        # Allow a tiny bit of wall-clock progression
        gap2 = ks.kms_unavailable_gap_seconds()
        assert gap2 >= gap1


# ===========================================================================
# 11-13. should_halt_new_offers (composite logic)
# ===========================================================================

class TestShouldHalt:
    def test_should_halt_when_kill_switch_active(self):
        ks = KillSwitch()
        ks.activate("halt test")
        assert ks.should_halt_new_offers() is True

    def test_should_halt_when_kms_unavailable(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()  # sets KMS to UNAVAILABLE
        assert ks.should_halt_new_offers() is True

    def test_should_not_halt_when_both_clear(self):
        kms = _mock_kms(should_fail=False)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()
        assert ks.should_halt_new_offers() is False

    def test_should_halt_when_both_kill_switch_and_kms_down(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.activate("double fault")
        ks.check_kms()
        assert ks.should_halt_new_offers() is True


# ===========================================================================
# 14. get_status structure
# ===========================================================================

class TestGetStatus:
    def test_get_status_structure(self):
        ks = KillSwitch()
        status = ks.get_status()
        assert isinstance(status, KillSwitchStatus)
        assert status.kill_switch_state == KillSwitchState.INACTIVE
        assert status.kms_state == KMSState.AVAILABLE
        assert status.activated_at is None
        assert status.kms_unavailable_since is None
        assert status.reason is None

    def test_get_status_after_activate(self):
        ks = KillSwitch()
        ks.activate("reason X")
        status = ks.get_status()
        assert status.kill_switch_state == KillSwitchState.ACTIVE
        assert status.activated_at is not None
        assert status.reason == "reason X"

    def test_get_status_reflects_kms_unavailable(self):
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)
        ks.check_kms()
        status = ks.get_status()
        assert status.kms_state == KMSState.UNAVAILABLE
        assert status.kms_unavailable_since is not None

    def test_get_status_with_redis_active(self):
        """get_status uses is_active() which should read from redis when available."""
        redis = _mock_redis()
        ks = KillSwitch(redis_client=redis)
        ks.activate("redis status")
        status = ks.get_status()
        assert status.kill_switch_state == KillSwitchState.ACTIVE


# ===========================================================================
# 15. start_kms_monitor / stop_kms_monitor
# ===========================================================================

class TestKMSMonitor:
    def test_start_and_stop_kms_monitor(self):
        """Monitor thread starts, calls check_kms at least once, then stops cleanly."""
        kms = _mock_kms(should_fail=False)
        ks = KillSwitch(kms_client=kms)

        # Use a very short interval so the test completes quickly
        ks.start_kms_monitor(interval=0.05)

        # Verify the monitor thread is alive
        assert ks._monitor_thread is not None
        assert ks._monitor_thread.is_alive()

        # Wait long enough for at least one check_kms invocation
        time.sleep(0.15)

        ks.stop_kms_monitor()

        # Thread should be cleaned up
        assert ks._monitor_thread is None
        # check_kms should have been called at least once via the loop
        assert kms.ping.call_count >= 1

    def test_monitor_detects_kms_failure(self):
        """Monitor loop should detect KMS failure and set state to UNAVAILABLE."""
        kms = _mock_kms(should_fail=True)
        ks = KillSwitch(kms_client=kms)

        ks.start_kms_monitor(interval=0.05)
        time.sleep(0.15)
        ks.stop_kms_monitor()

        assert ks._kms_state == KMSState.UNAVAILABLE

    def test_stop_without_start_is_safe(self):
        """Calling stop_kms_monitor without a prior start must not raise."""
        ks = KillSwitch()
        ks.stop_kms_monitor()  # should be no-op
        assert ks._monitor_thread is None

    def test_monitor_stop_event_is_set(self):
        """After stop, the internal _stop_event should be set."""
        kms = _mock_kms(should_fail=False)
        ks = KillSwitch(kms_client=kms)
        ks.start_kms_monitor(interval=0.05)
        time.sleep(0.1)
        ks.stop_kms_monitor()
        assert ks._stop_event.is_set()

    def test_monitor_restart_after_stop(self):
        """Monitor can be restarted after being stopped."""
        kms = _mock_kms(should_fail=False)
        ks = KillSwitch(kms_client=kms)

        # First run
        ks.start_kms_monitor(interval=0.05)
        time.sleep(0.1)
        ks.stop_kms_monitor()
        first_call_count = kms.ping.call_count

        # Second run
        ks.start_kms_monitor(interval=0.05)
        time.sleep(0.1)
        ks.stop_kms_monitor()

        # Should have accumulated more calls
        assert kms.ping.call_count > first_call_count
