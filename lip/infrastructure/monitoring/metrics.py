"""
metrics.py — Prometheus metrics for LIP.
Tracks: inference latency p50/p99, queue depth, AUC drift.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

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
        self._samples.append(latency_ms)
        if len(self._samples) > self.window_size:
            self._samples.popleft()

    def p50(self) -> Optional[float]:
        if not self._samples:
            return None
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * 0.50)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def p99(self) -> Optional[float]:
        if not self._samples:
            return None
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def count(self) -> int:
        return len(self._samples)


class PrometheusMetricsCollector:
    """
    Prometheus metrics collector for LIP.
    In production, uses the prometheus_client library.
    Falls back to in-memory counters for testing.
    """

    def __init__(self, push_gateway: Optional[str] = None):
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
        self._inference_latency.record(latency_ms)
        if latency_ms > 200:
            logger.warning("P99 latency threshold exceeded: %.1fms component=%s", latency_ms, component)

    def get_latency_p50(self) -> Optional[float]:
        return self._inference_latency.p50()

    def get_latency_p99(self) -> Optional[float]:
        return self._inference_latency.p99()

    # ── queue depth ──────────────────────────────────────────────────────────

    def set_queue_depth(self, depth: int) -> None:
        self._gauges[METRIC_QUEUE_DEPTH] = float(depth)

    def get_queue_depth(self) -> float:
        return self._gauges.get(METRIC_QUEUE_DEPTH, 0.0)

    # ── model quality ────────────────────────────────────────────────────────

    def set_auc(self, auc: float, component: str = "c1") -> None:
        self._gauges[f"{METRIC_AUC}_{component}"] = auc
        if auc < 0.80:
            logger.warning("AUC drift alert: %.3f below 0.80 threshold", auc)

    def get_auc(self, component: str = "c1") -> Optional[float]:
        return self._gauges.get(f"{METRIC_AUC}_{component}")

    # ── counters ─────────────────────────────────────────────────────────────

    def increment(self, metric: str, labels: Optional[Dict[str, str]] = None) -> None:
        key = metric + str(sorted((labels or {}).items()))
        self._counters[key] = self._counters.get(key, 0) + 1

    def get_counter(self, metric: str, labels: Optional[Dict[str, str]] = None) -> int:
        key = metric + str(sorted((labels or {}).items()))
        return self._counters.get(key, 0)

    # ── system state ─────────────────────────────────────────────────────────

    def set_degraded_mode(self, is_degraded: bool) -> None:
        self._gauges[METRIC_DEGRADED_MODE] = 1.0 if is_degraded else 0.0

    def set_kill_switch(self, is_active: bool) -> None:
        self._gauges[METRIC_KILL_SWITCH] = 1.0 if is_active else 0.0

    # ── push ─────────────────────────────────────────────────────────────────

    def push_to_gateway(self, job: str = "lip") -> bool:
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
