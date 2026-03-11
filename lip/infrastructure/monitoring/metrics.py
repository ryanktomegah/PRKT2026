"""
metrics.py — Prometheus metrics for LIP.
Tracks: inference latency p50/p99, queue depth, AUC drift.
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

logger = logging.getLogger(__name__)

# Prometheus metric names
METRIC_INFERENCE_LATENCY = "lip_inference_latency_ms"
METRIC_QUEUE_DEPTH = "lip_inference_queue_depth"
METRIC_AUC = "lip_model_auc"
METRIC_FAILURE_RATE = "lip_payment_failure_rate"
METRIC_DISPUTE_FN_RATE = "lip_dispute_false_negative_rate"
METRIC_LOAN_OFFER_COUNT = "lip_loan_offers_total"
METRIC_REPAYMENT_COUNT = "lip_repayments_total"
METRIC_DEGRADED_MODE = "lip_degraded_mode"
METRIC_KILL_SWITCH = "lip_kill_switch_active"


@dataclass
class LatencyTracker:
    """Rolling window latency tracker for p50/p99 computation."""

    window_size: int = 1000
    _samples: Deque[float] = field(default_factory=deque)

    def record(self, latency_ms: float) -> None:
        """Append a latency sample and evict the oldest if the window is full.

        Args:
            latency_ms: Observed latency in milliseconds.
        """
        self._samples.append(latency_ms)
        if len(self._samples) > self.window_size:
            self._samples.popleft()

    def p50(self) -> Optional[float]:
        """Return the 50th-percentile (median) latency from the rolling window.

        Returns:
            Median latency in milliseconds, or ``None`` when no samples
            have been recorded yet.
        """
        if not self._samples:
            return None
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * 0.50)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def p99(self) -> Optional[float]:
        """Return the 99th-percentile latency from the rolling window.

        This is the canonical SLO metric compared against the 94ms threshold
        (``LATENCY_P99_TARGET_MS`` in ``constants.py``).

        Returns:
            P99 latency in milliseconds, or ``None`` when no samples have
            been recorded yet.
        """
        if not self._samples:
            return None
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def count(self) -> int:
        """Return the number of samples currently held in the rolling window.

        Returns:
            Sample count (0 to ``window_size``).
        """
        return len(self._samples)


class PrometheusMetricsCollector:
    """
    Prometheus metrics collector for LIP.
    In production, uses the prometheus_client library.
    Falls back to in-memory counters for testing.
    """

    def __init__(self, push_gateway: Optional[str] = None):
        """Initialise the collector, optionally with a Prometheus push gateway.

        Attempts to import ``prometheus_client``; falls back to in-memory
        counters and gauges when the library is not installed (e.g., in
        unit tests).

        Args:
            push_gateway: Optional ``host:port`` of the Prometheus
                Pushgateway.  When ``None``, :meth:`push_to_gateway` is a
                no-op.
        """
        self._push_gateway = push_gateway
        self._inference_latency = LatencyTracker()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._prom_available = False
        try:
            import prometheus_client  # noqa: F401
            self._prom_available = True
        except ImportError:
            logger.debug("prometheus_client not installed; using in-memory metrics")

    # ── latency ──────────────────────────────────────────────────────────────

    def record_inference_latency(self, latency_ms: float, component: str = "c1") -> None:
        """Record an inference latency sample and warn if it exceeds the SLO.

        Logs a warning when ``latency_ms > 94`` to surface SLO breaches in
        the application log before a PagerDuty alert fires.

        Args:
            latency_ms: Observed inference time in milliseconds.
            component: Short component identifier (default ``'c1'``).
        """
        self._inference_latency.record(latency_ms)
        if latency_ms > 94:
            logger.warning("P99 latency threshold exceeded: %.1fms component=%s", latency_ms, component)

    def get_latency_p50(self) -> Optional[float]:
        """Return the current P50 inference latency from the rolling window.

        Returns:
            P50 latency in milliseconds, or ``None`` if no samples recorded.
        """
        return self._inference_latency.p50()

    def get_latency_p99(self) -> Optional[float]:
        """Return the current P99 inference latency from the rolling window.

        Returns:
            P99 latency in milliseconds, or ``None`` if no samples recorded.
        """
        return self._inference_latency.p99()

    # ── queue depth ──────────────────────────────────────────────────────────

    def set_queue_depth(self, depth: int) -> None:
        """Update the Kafka consumer queue depth gauge.

        Args:
            depth: Current number of unprocessed messages in the queue.
        """
        self._gauges[METRIC_QUEUE_DEPTH] = float(depth)

    def get_queue_depth(self) -> float:
        """Return the last-recorded Kafka consumer queue depth.

        Returns:
            Queue depth as a float (0.0 when not yet set).
        """
        return self._gauges.get(METRIC_QUEUE_DEPTH, 0.0)

    # ── model quality ────────────────────────────────────────────────────────

    def set_auc(self, auc: float, component: str = "c1") -> None:
        """Update the model AUC gauge for a component and warn on drift.

        Logs a warning when ``auc < 0.80`` to surface model quality
        degradation before it triggers a full AUC drift alert.

        Args:
            auc: Current AUC value [0, 1].
            component: Short component identifier (default ``'c1'``).
        """
        self._gauges[f"{METRIC_AUC}_{component}"] = auc
        if auc < 0.80:
            logger.warning("AUC drift alert: %.3f below 0.80 threshold", auc)

    def get_auc(self, component: str = "c1") -> Optional[float]:
        """Return the last-recorded AUC for a component.

        Args:
            component: Short component identifier (default ``'c1'``).

        Returns:
            AUC value [0, 1], or ``None`` if not yet set.
        """
        return self._gauges.get(f"{METRIC_AUC}_{component}")

    # ── counters ─────────────────────────────────────────────────────────────

    def increment(self, metric: str, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a named counter metric by 1.

        Labels are serialised into the key to support basic label
        dimensionality without a full Prometheus registry.

        Args:
            metric: Prometheus metric name (use constants defined at the
                top of this module, e.g., ``METRIC_LOAN_OFFER_COUNT``).
            labels: Optional dict of label name→value pairs.
        """
        key = metric + str(sorted((labels or {}).items()))
        self._counters[key] = self._counters.get(key, 0) + 1

    def get_counter(self, metric: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Return the current value of a named counter metric.

        Args:
            metric: Prometheus metric name.
            labels: Optional dict of label name→value pairs (must match
                exactly what was passed to :meth:`increment`).

        Returns:
            Current counter value (0 if never incremented).
        """
        key = metric + str(sorted((labels or {}).items()))
        return self._counters.get(key, 0)

    # ── system state ─────────────────────────────────────────────────────────

    def set_degraded_mode(self, is_degraded: bool) -> None:
        """Update the degraded-mode binary gauge (0.0 or 1.0).

        Args:
            is_degraded: ``True`` when any component is in degraded mode.
        """
        self._gauges[METRIC_DEGRADED_MODE] = 1.0 if is_degraded else 0.0

    def set_kill_switch(self, is_active: bool) -> None:
        """Update the kill-switch binary gauge (0.0 or 1.0).

        Args:
            is_active: ``True`` when the kill switch is engaged.
        """
        self._gauges[METRIC_KILL_SWITCH] = 1.0 if is_active else 0.0

    # ── push ─────────────────────────────────────────────────────────────────

    def push_to_gateway(self, job: str = "lip") -> bool:
        """Push all metrics to the Prometheus Pushgateway.

        No-op when ``prometheus_client`` is not installed or no push gateway
        is configured.

        Args:
            job: Prometheus job label for the pushed metrics (default
                ``'lip'``).

        Returns:
            ``True`` if the push succeeded; ``False`` otherwise.
        """
        if not self._prom_available or not self._push_gateway:
            return False
        try:
            import prometheus_client
            prometheus_client.push_to_gateway(self._push_gateway, job=job,
                                              registry=prometheus_client.REGISTRY)
            return True
        except Exception as exc:
            logger.error("Failed to push metrics: %s", exc)
            return False

    def snapshot(self) -> dict:
        """Return a snapshot of all current metrics."""
        return {
            "inference_latency_p50_ms": self.get_latency_p50(),
            "inference_latency_p99_ms": self.get_latency_p99(),
            "inference_latency_count": self._inference_latency.count(),
            "queue_depth": self.get_queue_depth(),
            "auc_c1": self.get_auc("c1"),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }
