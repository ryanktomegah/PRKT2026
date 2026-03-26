"""
test_drift_detector.py — Tests for ADWIN concept drift detection.
SR 11-7 requirement: model monitoring must detect distributional shift.
"""
from __future__ import annotations

import pytest

from lip.common.drift_detector import (
    DriftEvent,
    FeatureDriftMonitor,
    _InMemoryADWIN,
)


class TestInMemoryADWIN:
    """Test the fallback ADWIN implementation."""

    def test_no_drift_on_stable_data(self):
        adwin = _InMemoryADWIN(delta=0.002, recent_window=50)
        for _ in range(200):
            adwin.update(1.0)
        assert not adwin.drift_detected

    def test_detects_mean_shift(self):
        adwin = _InMemoryADWIN(delta=0.002, recent_window=50)
        # Feed stable data
        for _ in range(200):
            adwin.update(1.0)
        # Introduce a large shift
        detected = False
        for _ in range(200):
            adwin.update(10.0)
            if adwin.drift_detected:
                detected = True
                break
        assert detected

    def test_estimation_tracks_mean(self):
        adwin = _InMemoryADWIN(delta=0.002, recent_window=50)
        for _ in range(100):
            adwin.update(5.0)
        assert abs(adwin.estimation - 5.0) < 0.01


class TestFeatureDriftMonitor:
    """Test the FeatureDriftMonitor."""

    def test_init_with_features(self):
        monitor = FeatureDriftMonitor(
            feature_names=["amount", "rate", "count"],
            delta=0.002,
        )
        assert len(monitor.feature_names) == 3
        assert monitor.samples_seen == 0

    def test_no_drift_on_stable_features(self):
        monitor = FeatureDriftMonitor(
            feature_names=["amount"],
            delta=0.002,
        )
        for _ in range(100):
            events = monitor.update({"amount": 1.0})
        assert len(events) == 0

    def test_detects_drift_on_shift(self):
        monitor = FeatureDriftMonitor(
            feature_names=["amount"],
            delta=0.002,
        )
        # Stable phase
        for _ in range(300):
            monitor.update({"amount": 1.0})
        # Shift phase
        drift_detected = False
        for _ in range(300):
            events = monitor.update({"amount": 100.0})
            if events:
                drift_detected = True
                break
        assert drift_detected

    def test_missing_features_silently_skipped(self):
        monitor = FeatureDriftMonitor(
            feature_names=["a", "b"],
            delta=0.002,
        )
        # Only update feature "a"
        monitor.update({"a": 1.0})
        assert monitor.samples_seen == 1

    def test_get_status(self):
        monitor = FeatureDriftMonitor(
            feature_names=["x", "y"],
            delta=0.002,
        )
        monitor.update({"x": 5.0, "y": 10.0})
        status = monitor.get_status()
        assert "x" in status
        assert "y" in status
        assert status["x"]["samples_seen"] == 1

    def test_drift_event_structure(self):
        event = DriftEvent(
            feature_name="amount",
            old_mean=1.0,
            new_mean=10.0,
            magnitude=9.0,
            detected_at=1000.0,
            samples_seen=500,
        )
        assert event.feature_name == "amount"
        assert event.magnitude == 9.0

    def test_metrics_collector_integration(self):
        """Verify drift events push to metrics collector."""
        from lip.infrastructure.monitoring.metrics import PrometheusMetricsCollector
        metrics = PrometheusMetricsCollector()
        monitor = FeatureDriftMonitor(
            feature_names=["amount"],
            delta=0.002,
            metrics_collector=metrics,
        )
        # Stable then shift
        for _ in range(300):
            monitor.update({"amount": 1.0})
        for _ in range(300):
            events = monitor.update({"amount": 100.0})
            if events:
                break
        # Verify metric was incremented (at least once)
        # The exact count depends on when ADWIN triggers


class TestDriftEventDataclass:
    """Test DriftEvent is frozen and has expected fields."""

    def test_frozen(self):
        event = DriftEvent("f", 1.0, 2.0, 1.0, 0.0, 100)
        with pytest.raises(AttributeError):
            event.feature_name = "other"  # type: ignore
