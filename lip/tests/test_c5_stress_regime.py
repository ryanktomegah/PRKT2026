"""
test_c5_stress_regime.py — Unit tests for StressRegimeDetector.

Tests cover:
  - Spike detection across the 3x threshold
  - Below-threshold: not stressed
  - Insufficient transactions in 1h window
  - Zero-baseline edge case (new corridor)
  - check_and_emit() returning StressRegimeEvent
  - check_and_emit() returning None when not stressed
  - In-memory fallback when no Kafka producer is configured
  - Kafka producer emit path (mocked)
  - Old record eviction (cleanup)
  - get_rates() accuracy
  - STRESS_TOPIC constant
  - StressRegimeEvent JSON serialisation
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from lip.c5_streaming.stress_regime_detector import StressRegimeDetector, StressRegimeEvent

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_detector(
    now: float = 1_000_000.0,
    min_txns: int = 5,
    multiplier: float = 3.0,
) -> tuple[StressRegimeDetector, list]:
    """Return (detector, clock) where clock[0] is the injectable time value."""
    clock: list[float] = [now]
    det = StressRegimeDetector(
        baseline_window_seconds=86400,
        current_window_seconds=3600,
        threshold_multiplier=multiplier,
        min_transactions_for_signal=min_txns,
        time_func=lambda: clock[0],
    )
    return det, clock


def _pump(det: StressRegimeDetector, corridor: str, n_total: int, n_fail: int) -> None:
    """Record n_total events for a corridor at the current clock time."""
    for i in range(n_total):
        det.record_event(corridor, is_failure=(i < n_fail))


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestIsStressed:
    def test_spike_detected_above_threshold(self):
        """1h rate = 75%, baseline = 10% → ratio=7.5 > 3.0 → stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        # Baseline events 2h before "now" (outside 1h window)
        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)  # 10% baseline

        # Current events 10min before "now"
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=15)  # 75% current

        clock[0] = now
        assert det.is_stressed("EUR_USD") is True

    def test_below_threshold_not_stressed(self):
        """1h rate = 20%, baseline = 10% → ratio=2.0 < 3.0 → not stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)  # 10% baseline

        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=4)  # 20% current

        clock[0] = now
        assert det.is_stressed("EUR_USD") is False

    def test_insufficient_current_transactions(self):
        """Fewer than min_txns events in 1h window → not stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=10)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)  # 10% baseline

        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=5, n_fail=5)  # 100% current — but only 5 events

        clock[0] = now
        assert det.is_stressed("EUR_USD") is False

    def test_insufficient_baseline_transactions(self):
        """Fewer than min_txns events in baseline window → not stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=10)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=3, n_fail=0)  # only 3 baseline events

        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=20)  # 100% current

        clock[0] = now
        assert det.is_stressed("EUR_USD") is False

    def test_zero_baseline_with_failures_stressed(self):
        """Baseline rate = 0%, current has failures → corridor is stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "GBP_USD", n_total=20, n_fail=0)  # 0% baseline

        clock[0] = now - 600
        _pump(det, "GBP_USD", n_total=10, n_fail=8)  # 80% current

        clock[0] = now
        assert det.is_stressed("GBP_USD") is True

    def test_zero_baseline_no_current_failures_not_stressed(self):
        """Baseline rate = 0%, current rate = 0% → not stressed."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "GBP_USD", n_total=20, n_fail=0)

        clock[0] = now - 600
        _pump(det, "GBP_USD", n_total=10, n_fail=0)

        clock[0] = now
        assert det.is_stressed("GBP_USD") is False

    def test_unknown_corridor_not_stressed(self):
        """An unrecorded corridor has no history → never stressed."""
        det, _ = _make_detector()
        assert det.is_stressed("XXX_YYY") is False

    def test_exact_threshold_not_stressed(self):
        """Rate exactly at threshold is NOT stressed (strictly greater than required)."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5, multiplier=3.0)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=10, n_fail=1)  # 10% baseline

        clock[0] = now - 600
        # Exactly 30% = 10% × 3.0 → NOT > threshold
        _pump(det, "EUR_USD", n_total=10, n_fail=3)

        clock[0] = now
        assert det.is_stressed("EUR_USD") is False


class TestCheckAndEmit:
    def test_returns_event_when_stressed(self):
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=15)
        clock[0] = now

        event = det.check_and_emit("EUR_USD")
        assert event is not None
        assert isinstance(event, StressRegimeEvent)
        assert event.corridor == "EUR_USD"
        assert event.failure_rate_1h > 0
        assert event.ratio > det.multiplier

    def test_returns_none_when_not_stressed(self):
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=3)
        clock[0] = now

        event = det.check_and_emit("EUR_USD")
        assert event is None

    def test_event_stored_in_memory_when_no_kafka(self):
        """Without a Kafka producer, events go to emitted_events list."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=5)

        clock[0] = now - 7200
        _pump(det, "USD_JPY", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "USD_JPY", n_total=20, n_fail=15)
        clock[0] = now

        assert len(det.emitted_events) == 0
        event = det.check_and_emit("USD_JPY")
        assert event is not None
        assert len(det.emitted_events) == 1
        assert det.emitted_events[0] is event

    def test_kafka_producer_called_when_configured(self):
        """When a Kafka producer is injected, produce() is called correctly."""
        now = 1_000_000.0
        clock: list[float] = [now]

        mock_producer = MagicMock()
        det = StressRegimeDetector(
            baseline_window_seconds=86400,
            current_window_seconds=3600,
            threshold_multiplier=3.0,
            min_transactions_for_signal=5,
            time_func=lambda: clock[0],
            kafka_producer=mock_producer,
        )

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=15)
        clock[0] = now

        event = det.check_and_emit("EUR_USD")
        assert event is not None

        # Kafka produce() should have been called once
        mock_producer.produce.assert_called_once()
        call_kwargs = mock_producer.produce.call_args
        assert call_kwargs.kwargs["topic"] == StressRegimeDetector.STRESS_TOPIC
        assert call_kwargs.kwargs["key"] == b"EUR_USD"

        # poll() should have been called to flush delivery callbacks
        mock_producer.poll.assert_called_once_with(0)

        # In-memory fallback should be empty
        assert len(det.emitted_events) == 0

    def test_kafka_produce_retries_then_routes_to_dlq(self, monkeypatch):
        """T2.1: on persistent produce failure, retry then route to DLQ.

        Previously the detector silently buffered the event in-memory on
        the first failure. That is a silent-drop risk on a risk-alert
        topic. The new contract is: retry N times with exponential backoff,
        then publish to ``lip.dead.letter`` with a ``source-topic`` header.
        """
        import lip.c5_streaming.stress_regime_detector as srd

        # Don't actually sleep in the retry loop
        monkeypatch.setattr(srd.time, "sleep", lambda *_: None)

        now = 1_000_000.0
        clock: list[float] = [now]

        mock_producer = MagicMock()
        produce_calls: list = []

        def _produce_side_effect(*, topic, key, value, headers=None):
            produce_calls.append((topic, headers))
            if topic == StressRegimeDetector.STRESS_TOPIC:
                raise RuntimeError("Kafka unavailable")
            # DLQ succeeds
            return None

        mock_producer.produce.side_effect = _produce_side_effect

        det = StressRegimeDetector(
            baseline_window_seconds=86400,
            current_window_seconds=3600,
            threshold_multiplier=3.0,
            min_transactions_for_signal=5,
            time_func=lambda: clock[0],
            kafka_producer=mock_producer,
        )

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=15)
        clock[0] = now

        event = det.check_and_emit("EUR_USD")
        assert event is not None

        # 3 retries against the stress topic, then 1 DLQ publish = 4 calls
        stress_attempts = [t for t, _ in produce_calls if t == StressRegimeDetector.STRESS_TOPIC]
        dlq_attempts = [h for t, h in produce_calls if t == "lip.dead.letter"]
        assert len(stress_attempts) == 3, (
            f"expected 3 retries against stress topic, got {len(stress_attempts)}"
        )
        assert len(dlq_attempts) == 1, (
            f"expected 1 DLQ route, got {len(dlq_attempts)}"
        )
        assert dlq_attempts[0]["source-topic"] == StressRegimeDetector.STRESS_TOPIC

        # In-memory fallback must stay empty — DLQ succeeded
        assert det.emitted_events == []

    def test_kafka_and_dlq_both_fail_falls_back_to_memory(self, monkeypatch):
        """In-memory fallback is a last resort when DLQ is also unreachable."""
        import lip.c5_streaming.stress_regime_detector as srd

        monkeypatch.setattr(srd.time, "sleep", lambda *_: None)

        now = 1_000_000.0
        clock: list[float] = [now]

        mock_producer = MagicMock()
        mock_producer.produce.side_effect = RuntimeError("cluster unreachable")

        det = StressRegimeDetector(
            baseline_window_seconds=86400,
            current_window_seconds=3600,
            threshold_multiplier=3.0,
            min_transactions_for_signal=5,
            time_func=lambda: clock[0],
            kafka_producer=mock_producer,
        )

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=20, n_fail=2)
        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=20, n_fail=15)
        clock[0] = now

        event = det.check_and_emit("EUR_USD")
        assert event is not None
        assert len(det.emitted_events) == 1
        assert det.emitted_events[0] is event


class TestGetRates:
    def test_correct_rates(self):
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=1)

        clock[0] = now - 7200
        _pump(det, "EUR_USD", n_total=10, n_fail=1)  # 10% historical

        clock[0] = now - 600
        _pump(det, "EUR_USD", n_total=10, n_fail=8)  # 80% current

        clock[0] = now
        rate_1h, baseline = det.get_rates("EUR_USD")

        assert rate_1h == pytest.approx(0.8)
        # Baseline rate is over full 24h window (all events): 9/20 = 45%
        assert baseline == pytest.approx(9 / 20)

    def test_no_events_returns_zeros(self):
        det, _ = _make_detector()
        rate_1h, baseline = det.get_rates("NEW_CORRIDOR")
        assert rate_1h == 0.0
        assert baseline == 0.0


class TestCleanup:
    def test_old_records_evicted(self):
        """Records older than baseline_window are evicted on next access."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=1)

        # Record events 25h ago (outside 24h baseline window)
        clock[0] = now - 90000  # 25h ago
        _pump(det, "EUR_USD", n_total=100, n_fail=100)

        clock[0] = now
        # After cleanup, history should be empty
        det._cleanup("EUR_USD")
        assert len(det._history["EUR_USD"]) == 0

    def test_recent_records_not_evicted(self):
        """Records within the baseline window are retained."""
        now = 1_000_000.0
        det, clock = _make_detector(now=now, min_txns=1)

        clock[0] = now - 3600  # 1h ago — within 24h window
        _pump(det, "EUR_USD", n_total=10, n_fail=5)

        clock[0] = now
        det._cleanup("EUR_USD")
        assert len(det._history["EUR_USD"]) == 10


class TestStressRegimeEvent:
    def test_to_json_contains_all_fields(self):
        event = StressRegimeEvent(
            corridor="EUR_USD",
            failure_rate_1h=0.75,
            baseline_rate=0.10,
            ratio=7.5,
            triggered_at=1_000_000.0,
        )
        payload = json.loads(event.to_json())
        assert payload["corridor"] == "EUR_USD"
        assert payload["failure_rate_1h"] == pytest.approx(0.75)
        assert payload["baseline_rate"] == pytest.approx(0.10)
        assert payload["ratio"] == pytest.approx(7.5)
        assert payload["triggered_at"] == pytest.approx(1_000_000.0)

    def test_to_json_inf_ratio_serialised_as_null(self):
        """float('inf') must not break JSON serialisation — represented as null."""
        event = StressRegimeEvent(
            corridor="GBP_USD",
            failure_rate_1h=0.5,
            baseline_rate=0.0,
            ratio=float("inf"),
            triggered_at=1_000_000.0,
        )
        payload = json.loads(event.to_json())
        assert payload["ratio"] is None


class TestConstants:
    def test_stress_topic(self):
        assert StressRegimeDetector.STRESS_TOPIC == "lip.stress.regime"

    def test_stress_regime_constants_in_module(self):
        from lip.common.constants import STRESS_REGIME_MIN_TXNS, STRESS_REGIME_MULTIPLIER

        assert STRESS_REGIME_MULTIPLIER == 3.0
        assert STRESS_REGIME_MIN_TXNS == 20
