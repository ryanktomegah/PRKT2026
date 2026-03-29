"""
metrics.py — Prometheus metrics for LIP.
Tracks: inference latency p50/p99, queue depth, AUC drift, feature drift.

When ``prometheus_client`` is installed, metrics are registered in the default
Prometheus CollectorRegistry and exposed via ``generate_latest()`` for scraping.
The ``/metrics`` HTTP endpoint is wired in ``api/app.py``.

When ``prometheus_client`` is NOT installed (e.g. unit tests), all metrics are
tracked in-memory with the same API surface — zero behavioural difference from
the caller's perspective.
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

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

# GAP operational metrics
METRIC_FX_BLOCK_RATE = "lip_fx_block_rate"
METRIC_PARTIAL_SETTLEMENT_RATE = "lip_partial_settlement_rate"
METRIC_SHORTFALL_TOTAL_USD = "lip_shortfall_total_usd"
METRIC_BORROWER_ENROLLMENTS = "lip_borrower_enrollments_total"
METRIC_NOTIFICATIONS = "lip_notifications_total"
METRIC_HUMAN_OVERRIDE_REQUESTS = "lip_human_override_requests_total"
METRIC_HUMAN_OVERRIDE_EXPIRED = "lip_human_override_expired_total"
METRIC_ROYALTY_COLLECTED_USD = "lip_royalty_collected_usd"
METRIC_KAFKA_PRODUCER_ERRORS = "lip_kafka_producer_errors"

# Drift detection metrics (SR 11-7 ongoing monitoring)
METRIC_FEATURE_DRIFT = "lip_feature_drift_detected"
METRIC_FEATURE_DRIFT_MAGNITUDE = "lip_feature_drift_magnitude"

# Portfolio risk metrics
METRIC_PORTFOLIO_VAR_99 = "lip_portfolio_var_99_usd"
METRIC_PORTFOLIO_CONCENTRATION_HHI = "lip_portfolio_concentration_hhi"

# Conformal prediction metrics
METRIC_CONFORMAL_COVERAGE = "lip_conformal_coverage"
METRIC_CONFORMAL_INTERVAL_WIDTH = "lip_conformal_interval_width"

# P3 — Platform Licensing (MIPLO) metrics
METRIC_MIPLO_API_LATENCY = "lip_miplo_api_latency_ms"
METRIC_MIPLO_REQUEST_COUNT = "lip_miplo_requests_total"
METRIC_PROCESSOR_TX_COUNT = "lip_processor_transactions_total"
METRIC_PROCESSOR_GROSS_FEE = "lip_processor_gross_fee_usd"
METRIC_PROCESSOR_NET_FEE = "lip_processor_net_fee_usd"
METRIC_CONTAINER_HEARTBEAT = "lip_container_heartbeat_timestamp"
METRIC_TENANT_ISOLATION_VIOLATION = "lip_tenant_isolation_violations_total"
METRIC_TENANT_ACTIVE_LOANS = "lip_tenant_active_loans"
METRIC_TENANT_EXPOSURE_USD = "lip_tenant_exposure_usd"

# P10 — Regulatory Data Product (Anonymizer) metrics
METRIC_P10_BATCHES_PROCESSED = "lip_p10_batches_processed_total"
METRIC_P10_CORRIDORS_SUPPRESSED = "lip_p10_corridors_suppressed_total"
METRIC_P10_SUPPRESSION_RATE = "lip_p10_suppression_rate"
METRIC_P10_NOISE_APPLIED = "lip_p10_noise_applied_total"
METRIC_P10_BUDGET_EXHAUSTED = "lip_p10_budget_exhausted_total"
METRIC_P10_STALE_RESULTS = "lip_p10_stale_results_total"
METRIC_P10_PRIVACY_BUDGET_REMAINING = "lip_p10_privacy_budget_remaining"


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

        When ``prometheus_client`` is installed, registers real Histogram,
        Gauge, and Counter instruments in the default CollectorRegistry.
        These are scraped by Prometheus via the ``/metrics`` HTTP endpoint
        (see ``api/app.py``).

        Falls back to in-memory counters and gauges when the library is not
        installed (e.g., in unit tests).

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
        self._prom_histogram = None
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_counters: Dict[str, Any] = {}
        try:
            import prometheus_client as prom
            self._prom_available = True
            # Real Prometheus instruments — scraped via /metrics
            self._prom_histogram = prom.Histogram(
                "lip_inference_latency_seconds",
                "C1/C2 inference latency",
                ["component"],
                buckets=[0.005, 0.010, 0.025, 0.045, 0.050, 0.075, 0.094, 0.100, 0.250, 0.500],
            )
            self._prom_gauges["auc"] = prom.Gauge(
                "lip_model_auc", "Model AUC by component", ["component"],
            )
            self._prom_gauges["queue_depth"] = prom.Gauge(
                "lip_queue_depth", "Kafka consumer queue depth",
            )
            self._prom_gauges["degraded_mode"] = prom.Gauge(
                "lip_degraded_mode_active", "1 if any component is degraded",
            )
            self._prom_gauges["kill_switch"] = prom.Gauge(
                "lip_kill_switch_active_gauge", "1 if kill switch is engaged",
            )
            self._prom_gauges["drift_magnitude"] = prom.Gauge(
                "lip_feature_drift_magnitude_gauge", "Latest drift magnitude", ["feature"],
            )
            self._prom_gauges["var_99"] = prom.Gauge(
                "lip_portfolio_var_99", "99th percentile Value at Risk in USD",
            )
            self._prom_gauges["hhi"] = prom.Gauge(
                "lip_portfolio_hhi", "Herfindahl-Hirschman Index by dimension", ["dimension"],
            )
            self._prom_gauges["conformal_coverage"] = prom.Gauge(
                "lip_conformal_coverage_gauge", "Conformal prediction coverage", ["component"],
            )
            self._prom_gauges["conformal_width"] = prom.Gauge(
                "lip_conformal_interval_width_gauge", "Conformal interval width", ["component"],
            )
            self._prom_counters["drift"] = prom.Counter(
                "lip_feature_drift_total", "Drift events detected", ["feature"],
            )
            self._prom_counters["loan_offers"] = prom.Counter(
                "lip_loan_offers_counter", "Total loan offers generated",
            )
            self._prom_counters["repayments"] = prom.Counter(
                "lip_repayments_counter", "Total repayments processed",
            )
            logger.info("prometheus_client wired — real metrics registered in default registry")
        except ImportError:
            logger.debug("prometheus_client not installed; using in-memory metrics")

    # ── latency ──────────────────────────────────────────────────────────────

    def record_inference_latency(self, latency_ms: float, component: str = "c1") -> None:
        """Record an inference latency sample and warn if it exceeds the SLO.

        When ``prometheus_client`` is available, also pushes the observation
        to the real Histogram (in seconds, per Prometheus convention).

        Args:
            latency_ms: Observed inference time in milliseconds.
            component: Short component identifier (default ``'c1'``).
        """
        self._inference_latency.record(latency_ms)
        if self._prom_histogram is not None:
            self._prom_histogram.labels(component=component).observe(latency_ms / 1000.0)
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
        if "auc" in self._prom_gauges:
            self._prom_gauges["auc"].labels(component=component).set(auc)
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

    def add_gauge(self, metric: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a named gauge metric to an absolute value.

        Args:
            metric: Prometheus metric name.
            value: Gauge value.
            labels: Optional label dict.
        """
        key = metric + str(sorted((labels or {}).items()))
        self._gauges[key] = value

    def get_gauge(self, metric: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Return the current value of a named gauge metric.

        Args:
            metric: Prometheus metric name.
            labels: Optional label dict.

        Returns:
            Gauge value (0.0 if never set).
        """
        key = metric + str(sorted((labels or {}).items()))
        return self._gauges.get(key, 0.0)

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

    def generate_latest(self) -> bytes:
        """Return Prometheus exposition format for the ``/metrics`` endpoint.

        When ``prometheus_client`` is installed, delegates to the library's
        ``generate_latest()`` function which serialises all registered
        instruments.  Returns an empty bytes object when the library is
        not available.

        Returns:
            Prometheus text exposition format as bytes.
        """
        if not self._prom_available:
            return b""
        try:
            from prometheus_client import generate_latest
            return generate_latest()
        except Exception as exc:
            logger.error("Failed to generate Prometheus metrics: %s", exc)
            return b""

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
