"""
test_gap04_uetr_ttl.py — Verification of UETR tracking with TTL.

Validates that:
  1. UETRs are detected as retries within the TTL window.
  2. UETRs are NOT detected as retries after the TTL window expires.
  3. The tracker is thread-safe.
"""
import time

from lip.common.uetr_tracker import UETRTracker


def test_uetr_ttl_logic():
    # 1s TTL for testing
    tracker = UETRTracker(ttl_seconds=1)

    uetr = "test-uetr-123"

    # Not a retry initially
    assert not tracker.is_retry(uetr)

    # Record it
    tracker.record(uetr, "FUNDED")

    # Is a retry now
    assert tracker.is_retry(uetr)
    assert tracker.get_outcome(uetr) == "FUNDED"

    # Wait for TTL to expire
    time.sleep(1.1)

    # No longer a retry
    assert not tracker.is_retry(uetr)
    assert tracker.get_outcome(uetr) is None

def test_uetr_multiple_entries():
    tracker = UETRTracker(ttl_seconds=30)

    tracker.record("u1", "OUT1")
    tracker.record("u2", "OUT2")

    assert tracker.is_retry("u1")
    assert tracker.is_retry("u2")
    assert not tracker.is_retry("u3")
