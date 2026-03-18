"""
stress_regime_detector.py — Corridor Stress Regime Detection.

Monitors corridor failure rates in real-time. If the short-term (1h) failure
rate exceeds the long-term (24h) baseline by a configurable multiplier
(default 3.0), the corridor is declared a STRESS_REGIME.

This signal is used to:
  1. Trigger human review for all offers in the stressed corridor.
  2. Alert the licensee bank's risk desk via Kafka.
  3. Support P5 (Supply Chain Patent) cascade propagation logic.

Kafka emission: :class:`StressRegimeEvent` is published to the
``lip.stress.regime`` topic via best-effort fire-and-forget. On failure
(or when no Kafka producer is configured), events accumulate in
:attr:`StressRegimeDetector.emitted_events` for prototype-mode inspection.

# PHASE-2-STUB: In production, wire a confluent_kafka.Producer to the bank's
# Redpanda/Kafka cluster using KafkaConfig credentials. Replace in-memory
# fallback with a dead-letter queue flushed to the ``lip.dead.letter`` topic.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StressRegimeEvent:
    """Emitted when a corridor failure rate spikes above the stress threshold.

    Attributes:
        corridor: Corridor identifier (e.g. ``"EUR_USD"``).
        failure_rate_1h: Current 1-hour rolling failure rate (0.0–1.0).
        baseline_rate: 24-hour baseline failure rate (0.0–1.0).
        ratio: ``failure_rate_1h / baseline_rate``.  ``float('inf')`` when
            baseline is zero and current failures are non-zero.
        triggered_at: Unix timestamp (seconds) when the event was produced.
    """

    corridor: str
    failure_rate_1h: float
    baseline_rate: float
    ratio: float
    triggered_at: float

    def to_json(self) -> str:
        """Serialise to a compact JSON string suitable for a Kafka payload."""
        return json.dumps(
            {
                "corridor": self.corridor,
                "failure_rate_1h": self.failure_rate_1h,
                "baseline_rate": self.baseline_rate,
                "ratio": self.ratio if self.ratio != float("inf") else None,
                "triggered_at": self.triggered_at,
            }
        )


class StressRegimeDetector:
    """Detects anomalous failure rate spikes per corridor.

    Uses two overlapping rolling windows on the same deque:

    * **Baseline window** (default 24 h): All events kept in memory.
      The baseline failure rate is computed over the slice
      ``[now - baseline_window, now - current_window]``.
    * **Current window** (default 1 h): The most recent slice
      ``[now - current_window, now]``.

    A corridor is declared *stressed* when:

    1. The current window has at least ``min_transactions_for_signal`` events.
    2. The baseline window (excluding current) has at least
       ``min_transactions_for_signal`` events.
    3. ``current_rate > baseline_rate * threshold_multiplier``.

    Args:
        baseline_window_seconds: Window for baseline calculation
            (default 86400 = 24 h).
        current_window_seconds: Short-term window for spike detection
            (default 3600 = 1 h).
        threshold_multiplier: Ratio above which the corridor is declared
            stressed. Default 3.0 — **QUANT sign-off required to change**.
        min_transactions_for_signal: Minimum transaction count needed in both
            windows before a stress signal is valid. Prevents false positives
            on thin traffic corridors.
        time_func: Override for :func:`time.time`; useful in unit tests.
        kafka_producer: Optional ``confluent_kafka.Producer`` instance.
            When provided, :class:`StressRegimeEvent` objects are published
            to :attr:`STRESS_TOPIC`. When absent, events are stored in
            :attr:`emitted_events` (in-memory prototype mode).
    """

    STRESS_TOPIC = "lip.stress.regime"

    def __init__(
        self,
        baseline_window_seconds: int = 86400,
        current_window_seconds: int = 3600,
        threshold_multiplier: float = 3.0,
        min_transactions_for_signal: int = 20,
        time_func: Optional[Callable[[], float]] = None,
        kafka_producer: Optional[object] = None,
    ) -> None:
        self.baseline_window = baseline_window_seconds
        self.current_window = current_window_seconds
        self.multiplier = threshold_multiplier
        self.min_txns = min_transactions_for_signal
        self._time: Callable[[], float] = time_func or time.time
        self._producer = kafka_producer

        # corridor -> deque of (unix_timestamp, is_failure)
        self._history: Dict[str, Deque[Tuple[float, bool]]] = defaultdict(deque)

        # In-memory event store — populated when Kafka is unavailable
        self.emitted_events: List[StressRegimeEvent] = []

    def record_event(self, corridor: str, is_failure: bool) -> None:
        """Record a payment outcome for a corridor.

        Args:
            corridor: Corridor identifier (e.g. ``"EUR_USD"``).
            is_failure: ``True`` if the payment failed / was rejected.
        """
        self._history[corridor].append((self._time(), is_failure))
        self._cleanup(corridor)

    def is_stressed(self, corridor: str) -> bool:
        """Return ``True`` if the corridor is currently in a stress regime.

        See class docstring for the full evaluation logic.
        """
        self._cleanup(corridor)
        history = self._history[corridor]
        now = self._time()

        current_cutoff = now - self.current_window

        current_events = [h for h in history if h[0] >= current_cutoff]
        if len(current_events) < self.min_txns:
            return False

        current_failures = sum(1 for h in current_events if h[1])
        current_rate = current_failures / len(current_events)

        # Baseline: events older than the current window (still within 24h)
        baseline_events = [h for h in history if h[0] < current_cutoff]
        if len(baseline_events) < self.min_txns:
            return False

        baseline_failures = sum(1 for h in baseline_events if h[1])
        baseline_rate = baseline_failures / len(baseline_events)

        # Edge case: zero baseline with any current failures → stressed
        if baseline_rate == 0:
            return current_failures > 0

        return current_rate > (baseline_rate * self.multiplier)

    def check_and_emit(self, corridor: str) -> Optional[StressRegimeEvent]:
        """Evaluate stress and emit a :class:`StressRegimeEvent` if triggered.

        Call this after :meth:`record_event` to produce an event when the
        corridor crosses the threshold.  The caller is responsible for
        debouncing if continuous emission is undesired.

        Args:
            corridor: Corridor to evaluate.

        Returns:
            The emitted :class:`StressRegimeEvent`, or ``None`` if not stressed.
        """
        if not self.is_stressed(corridor):
            return None

        rate_1h, baseline = self._stress_window_rates(corridor)
        ratio = (rate_1h / baseline) if baseline > 0 else float("inf")
        event = StressRegimeEvent(
            corridor=corridor,
            failure_rate_1h=rate_1h,
            baseline_rate=baseline,
            ratio=ratio,
            triggered_at=self._time(),
        )
        self._emit(event)
        return event

    def _stress_window_rates(self, corridor: str) -> Tuple[float, float]:
        """Return ``(current_1h_rate, baseline_excl_current_rate)``.

        Uses the same window split as :meth:`is_stressed` so that
        :class:`StressRegimeEvent` ``ratio`` is directly comparable to
        ``threshold_multiplier``.
        """
        self._cleanup(corridor)
        history = self._history[corridor]
        now = self._time()
        current_cutoff = now - self.current_window

        current_events = [h for h in history if h[0] >= current_cutoff]
        current_rate = (
            sum(1 for h in current_events if h[1]) / len(current_events)
            if current_events
            else 0.0
        )
        baseline_events = [h for h in history if h[0] < current_cutoff]
        baseline_rate = (
            sum(1 for h in baseline_events if h[1]) / len(baseline_events)
            if baseline_events
            else 0.0
        )
        return current_rate, baseline_rate

    def get_rates(self, corridor: str) -> Tuple[float, float]:
        """Return ``(current_rate_1h, baseline_rate_24h)`` for a corridor.

        Both rates are in the range [0.0, 1.0].  Returns ``(0.0, 0.0)`` if
        no events have been recorded.
        """
        self._cleanup(corridor)
        history = self._history[corridor]
        now = self._time()

        current_cutoff = now - self.current_window
        current_events = [h for h in history if h[0] >= current_cutoff]
        current_rate = (
            sum(1 for h in current_events if h[1]) / len(current_events)
            if current_events
            else 0.0
        )

        # Overall baseline (entire 24h window, including current hour)
        baseline_rate = (
            sum(1 for h in history if h[1]) / len(history) if history else 0.0
        )

        return current_rate, baseline_rate

    def _emit(self, event: StressRegimeEvent) -> None:
        """Publish event to Kafka or fall back to in-memory list."""
        if self._producer is not None:
            try:
                self._producer.produce(  # type: ignore[attr-defined]
                    topic=self.STRESS_TOPIC,
                    key=event.corridor.encode(),
                    value=event.to_json().encode(),
                )
                self._producer.poll(0)  # type: ignore[attr-defined]  # trigger delivery callbacks (non-blocking)
                logger.info(
                    "StressRegimeEvent emitted → Kafka: corridor=%s ratio=%.2f",
                    event.corridor,
                    event.ratio,
                )
            except Exception:
                logger.exception(
                    "Kafka emit failed; buffering StressRegimeEvent in-memory: corridor=%s",
                    event.corridor,
                )
                self.emitted_events.append(event)
        else:
            # PHASE-2-STUB: replace with confluent_kafka.Producer in production
            logger.warning(
                "No Kafka producer configured — StressRegimeEvent stored in-memory: "
                "corridor=%s ratio=%.2f",
                event.corridor,
                event.ratio,
            )
            self.emitted_events.append(event)

    def _cleanup(self, corridor: str) -> None:
        """Evict records older than ``baseline_window`` seconds."""
        cutoff = self._time() - self.baseline_window
        dq = self._history[corridor]
        while dq and dq[0][0] < cutoff:
            dq.popleft()
