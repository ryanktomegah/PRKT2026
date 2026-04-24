"""
drift_detector.py — ADWIN concept drift detection for LIP model features.
SR 11-7 requirement: ongoing monitoring of model inputs for distributional shift.

Uses the ADWIN (ADaptive WINdowing) algorithm from the River library:
  - Bifet & Gavalda, "Learning from Time-Changing Data with Adaptive Windowing," SDM 2007
  - Automatically adjusts window size based on rate of change
  - No hyperparameters to tune (uses Hoeffding bounds internally)

Each monitored feature gets its own ADWIN detector. When the mean of recent
observations deviates significantly from the historical mean, a drift event
is emitted. The confidence level (delta) defaults to 0.002 per the paper's
recommendation for production monitoring.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Metric name for Prometheus drift alerts
METRIC_FEATURE_DRIFT = "lip_feature_drift_detected"
METRIC_FEATURE_DRIFT_MAGNITUDE = "lip_feature_drift_magnitude"


@dataclass(frozen=True)
class DriftEvent:
    """Emitted when ADWIN detects a distributional shift in a feature.

    Attributes:
        feature_name: Name of the feature that drifted.
        old_mean: Mean value in the historical window (pre-drift).
        new_mean: Mean value in the recent window (post-drift).
        magnitude: Absolute difference between old and new means.
        detected_at: Unix timestamp when drift was detected.
        samples_seen: Total number of observations processed.
    """
    feature_name: str
    old_mean: float
    new_mean: float
    magnitude: float
    detected_at: float
    samples_seen: int


def _try_import_river_adwin():
    """Import ADWIN from river, returning None if unavailable."""
    try:
        from river.drift import ADWIN  # type: ignore[import-not-found]
        return ADWIN
    except ImportError:
        return None


class _InMemoryADWIN:
    """Minimal ADWIN fallback when river is not installed.

    Uses a simple sliding-window z-test approximation. Not as statistically
    rigorous as the real ADWIN (no adaptive windowing), but sufficient to
    exercise the drift detection pipeline in tests without requiring the
    river dependency.

    The window compares the last ``recent_window`` observations against
    the full history. A drift is detected when the absolute difference in
    means exceeds ``threshold`` standard deviations.
    """

    def __init__(self, delta: float = 0.002, recent_window: int = 100) -> None:
        self.delta = delta
        self._values: list = []
        self._recent_window = recent_window
        self._detected_change = False
        # ADWIN API compatibility
        self.estimation = 0.0
        self._old_estimation = 0.0

    def update(self, value: float) -> "_InMemoryADWIN":
        self._values.append(value)
        n = len(self._values)
        self.estimation = sum(self._values) / n if n > 0 else 0.0

        self._detected_change = False
        if n > self._recent_window * 2:
            old_vals = self._values[:-self._recent_window]
            new_vals = self._values[-self._recent_window:]
            old_mean = sum(old_vals) / len(old_vals)
            new_mean = sum(new_vals) / len(new_vals)
            self._old_estimation = old_mean

            # Variance of old window
            if len(old_vals) > 1:
                variance = sum((v - old_mean) ** 2 for v in old_vals) / (len(old_vals) - 1)
                std = variance ** 0.5
                if std > 0 and abs(new_mean - old_mean) > 3.0 * std:
                    self._detected_change = True
                    self._old_estimation = old_mean
                    self.estimation = new_mean
        return self

    @property
    def drift_detected(self) -> bool:
        return self._detected_change


class FeatureDriftMonitor:
    """Monitors a set of named features for concept drift using ADWIN.

    Usage::

        monitor = FeatureDriftMonitor(
            feature_names=["amount_usd", "failure_rate_24h", "bic_degree"],
            delta=0.002,
        )

        # Called after each inference
        events = monitor.update({"amount_usd": 1.5e6, "failure_rate_24h": 0.04, ...})
        for event in events:
            logger.warning("Drift detected: %s", event)

    Parameters
    ----------
    feature_names:
        Names of the features to monitor. Should be the top-N most important
        C1 features (recommended: top 10 by SHAP importance).
    delta:
        ADWIN significance parameter. Lower = fewer false positives, slower
        detection. Default 0.002 per Bifet & Gavalda (2007).
    metrics_collector:
        Optional ``PrometheusMetricsCollector`` for emitting drift gauges.
    """

    def __init__(
        self,
        feature_names: List[str],
        delta: float = 0.002,
        metrics_collector=None,
    ) -> None:
        self._feature_names = list(feature_names)
        self._delta = delta
        self._metrics = metrics_collector
        self._samples_seen = 0

        # Try real ADWIN, fall back to in-memory approximation
        ADWIN = _try_import_river_adwin()
        self._detectors: Dict[str, Any] = {}
        self._using_river = ADWIN is not None

        for name in self._feature_names:
            if ADWIN is not None:
                self._detectors[name] = ADWIN(delta=delta)
            else:
                self._detectors[name] = _InMemoryADWIN(delta=delta)

        if not self._using_river:
            logger.info(
                "river not installed — using in-memory ADWIN fallback for %d features",
                len(feature_names),
            )
        else:
            logger.info(
                "FeatureDriftMonitor initialised with ADWIN (delta=%.4f) for %d features",
                delta, len(feature_names),
            )

    @property
    def feature_names(self) -> List[str]:
        """Return the list of monitored feature names."""
        return list(self._feature_names)

    @property
    def using_river(self) -> bool:
        """True if using real ADWIN from river; False if using fallback."""
        return self._using_river

    def update(self, feature_values: Dict[str, float]) -> List[DriftEvent]:
        """Feed new feature observations and return any drift events.

        Parameters
        ----------
        feature_values:
            Dict mapping feature name → observed value. Missing features
            are silently skipped (allows partial updates).

        Returns
        -------
        List[DriftEvent]
            Drift events detected on this update (empty if no drift).
        """
        self._samples_seen += 1
        events: List[DriftEvent] = []

        for name in self._feature_names:
            if name not in feature_values:
                continue

            value = float(feature_values[name])
            detector = self._detectors[name]

            if self._using_river:
                # River ADWIN API
                old_mean = detector.estimation
                detector.update(value)
                if detector.drift_detected:
                    new_mean = detector.estimation
                    magnitude = abs(new_mean - old_mean)
                    event = DriftEvent(
                        feature_name=name,
                        old_mean=old_mean,
                        new_mean=new_mean,
                        magnitude=magnitude,
                        detected_at=time.time(),
                        samples_seen=self._samples_seen,
                    )
                    events.append(event)
                    logger.warning(
                        "ADWIN drift detected: feature=%s old_mean=%.4f new_mean=%.4f "
                        "magnitude=%.4f samples=%d",
                        name, old_mean, new_mean, magnitude, self._samples_seen,
                    )
            else:
                # Fallback ADWIN
                old_mean = detector._old_estimation
                detector.update(value)
                if detector.drift_detected:
                    new_mean = detector.estimation
                    magnitude = abs(new_mean - old_mean)
                    event = DriftEvent(
                        feature_name=name,
                        old_mean=old_mean,
                        new_mean=new_mean,
                        magnitude=magnitude,
                        detected_at=time.time(),
                        samples_seen=self._samples_seen,
                    )
                    events.append(event)
                    logger.warning(
                        "Drift detected (fallback): feature=%s magnitude=%.4f samples=%d",
                        name, magnitude, self._samples_seen,
                    )

        # Emit Prometheus metrics
        if self._metrics and events:
            for event in events:
                self._metrics.increment(
                    METRIC_FEATURE_DRIFT,
                    labels={"feature": event.feature_name},
                )
                self._metrics.add_gauge(
                    METRIC_FEATURE_DRIFT_MAGNITUDE,
                    event.magnitude,
                    labels={"feature": event.feature_name},
                )

        return events

    def get_status(self) -> Dict[str, Dict]:
        """Return current monitoring status for each feature.

        Returns
        -------
        Dict[str, Dict]
            Mapping of feature name → status dict with keys:
            ``estimation`` (current mean), ``samples_seen``, ``using_river``.
        """
        status = {}
        for name in self._feature_names:
            det = self._detectors[name]
            status[name] = {
                "estimation": det.estimation,
                "samples_seen": self._samples_seen,
                "using_river": self._using_river,
            }
        return status

    @property
    def samples_seen(self) -> int:
        """Total number of observations processed."""
        return self._samples_seen
