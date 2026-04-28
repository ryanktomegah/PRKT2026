"""
stress_regime_detector.py — Corridor Stress Regime Detection.

Monitors corridor failure rates in real-time. If the short-term (1h) failure
rate exceeds the long-term (24h) baseline by a configurable multiplier
(default 3.0), the corridor is declared a STRESS_REGIME.

This signal is used to:
  1. Trigger human review for all offers in the stressed corridor.
  2. Alert the licensee bank's risk desk via Kafka.
  3. Support P5 (Supply Chain Patent) cascade propagation logic.

Kafka emission (T2.1 production wiring)
---------------------------------------
:class:`StressRegimeEvent` is published to the ``lip.stress.regime`` topic
through an injected ``confluent_kafka.Producer``-compatible object with
bounded exponential-backoff retries. On persistent failure the event is
routed to the ``lip.dead.letter`` topic with a ``source-topic`` header so
operators can replay it. Only when the DLQ route itself fails does the
event fall through to :attr:`StressRegimeDetector.emitted_events` — that
in-memory list is now a last-resort diagnostic, not a normal production
code path.

Why retry + DLQ and not just best-effort:
  The stress-regime topic carries risk signals that trigger human review of
  every subsequent offer in a stressed corridor. A silently-dropped alert
  means the bank's risk desk never sees the spike. Even though the topic
  is configured ``exactly_once=False`` (duplicates are harmless at the
  consumer), silent drops are not acceptable.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Matches the worker's retry schedule (100ms / 200ms / 400ms) so operators
# see consistent behaviour across the C5 producer surface.
_EMIT_MAX_RETRIES = 3
_EMIT_BACKOFF_BASE_MS = 100
_DEAD_LETTER_TOPIC = "lip.dead.letter"


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
        rail: Optional payment rail for rail-aware stress buckets.
    """

    corridor: str
    failure_rate_1h: float
    baseline_rate: float
    ratio: float
    triggered_at: float
    rail: Optional[str] = None

    def to_json(self) -> str:
        """Serialise to a compact JSON string suitable for a Kafka payload."""
        payload = {
            "corridor": self.corridor,
            "failure_rate_1h": self.failure_rate_1h,
            "baseline_rate": self.baseline_rate,
            "ratio": self.ratio if self.ratio != float("inf") else None,
            "triggered_at": self.triggered_at,
        }
        if self.rail is not None:
            payload["rail"] = self.rail
        return json.dumps(payload)


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

        # (rail_key, corridor) -> deque of (unix_timestamp, is_failure)
        # Phase A follow-up (2026-04-26): rail-aware buckets so sub-day rails
        # (CBDC/FedNow/Nexus) can use tuned windows without contaminating the
        # SWIFT bucket. rail_key="" preserves the legacy single-bucket layout
        # for callers that don't pass rail=. See RAIL_STRESS_WINDOWS in
        # lip.common.constants for tuning rationale.
        self._history: Dict[Tuple[str, str], Deque[Tuple[float, bool]]] = defaultdict(deque)

        # In-memory event store — populated when Kafka is unavailable
        self.emitted_events: List[StressRegimeEvent] = []

    def _windows_for(self, rail: Optional[str]) -> Tuple[int, int, int]:
        """Return (baseline_seconds, current_seconds, min_txns) for *rail*.

        When rail is None or unknown, returns the constructor defaults.
        When rail is in ``RAIL_STRESS_WINDOWS``, returns the rail-specific
        tuning calibrated to that rail's loan duration.
        """
        if rail is None:
            return self.baseline_window, self.current_window, self.min_txns
        # Lazy import to avoid heavy module dependency at import time.
        from lip.common.constants import RAIL_STRESS_WINDOWS
        cfg = RAIL_STRESS_WINDOWS.get(rail.upper())
        if cfg is None:
            # Unknown rail → fall back to constructor defaults rather than
            # silently picking SWIFT settings. Logs once per unknown rail.
            logger.debug(
                "StressRegimeDetector: no per-rail windows for rail=%r — "
                "using constructor defaults (baseline=%ss, current=%ss, min=%d)",
                rail, self.baseline_window, self.current_window, self.min_txns,
            )
            return self.baseline_window, self.current_window, self.min_txns
        return cfg

    def _bucket_key(self, corridor: str, rail: Optional[str]) -> Tuple[str, str]:
        """Return the internal history-bucket key for (corridor, rail)."""
        return ("" if rail is None else rail.upper(), corridor)

    def record_event(
        self,
        corridor: str,
        is_failure: bool,
        rail: Optional[str] = None,
    ) -> None:
        """Record a payment outcome for a corridor.

        Args:
            corridor: Corridor identifier (e.g. ``"EUR_USD"``).
            is_failure: ``True`` if the payment failed / was rejected.
            rail: Optional payment rail (``"SWIFT"``, ``"CBDC_MBRIDGE"``,
                etc.). When provided, the event is recorded in a rail-specific
                bucket so subsequent ``is_stressed(rail=...)`` calls use
                the rail's tuned windows. When None (legacy callers), uses
                a shared default bucket — preserves existing behaviour.
        """
        key = self._bucket_key(corridor, rail)
        self._history[key].append((self._time(), is_failure))
        self._cleanup(corridor, rail=rail)

    def is_stressed(self, corridor: str, rail: Optional[str] = None) -> bool:
        """Return ``True`` if the corridor is currently in a stress regime.

        See class docstring for the full evaluation logic.

        Args:
            corridor: Corridor identifier.
            rail: Optional payment rail. When provided, evaluation uses
                the rail-specific window tuning from
                ``lip.common.constants.RAIL_STRESS_WINDOWS``. When None,
                uses constructor defaults — preserves legacy behaviour.
        """
        self._cleanup(corridor, rail=rail)
        history = self._history[self._bucket_key(corridor, rail)]
        baseline_window, current_window, min_txns = self._windows_for(rail)
        now = self._time()

        current_cutoff = now - current_window

        current_events = [h for h in history if h[0] >= current_cutoff]
        if len(current_events) < min_txns:
            return False

        current_failures = sum(1 for h in current_events if h[1])
        current_rate = current_failures / len(current_events)

        # Baseline: events older than the current window (still within baseline)
        baseline_events = [h for h in history if h[0] < current_cutoff]
        if len(baseline_events) < min_txns:
            return False

        baseline_failures = sum(1 for h in baseline_events if h[1])
        baseline_rate = baseline_failures / len(baseline_events)

        # Edge case: zero baseline with any current failures → stressed
        if baseline_rate == 0:
            return current_failures > 0

        return current_rate > (baseline_rate * self.multiplier)

    def check_and_emit(
        self,
        corridor: str,
        rail: Optional[str] = None,
    ) -> Optional[StressRegimeEvent]:
        """Evaluate stress and emit a :class:`StressRegimeEvent` if triggered.

        Call this after :meth:`record_event` to produce an event when the
        corridor crosses the threshold.  The caller is responsible for
        debouncing if continuous emission is undesired.

        Args:
            corridor: Corridor to evaluate.
            rail: Optional payment rail (forwarded to is_stressed and rate
                computation). When provided, uses rail-tuned windows.

        Returns:
            The emitted :class:`StressRegimeEvent`, or ``None`` if not stressed.
        """
        if not self.is_stressed(corridor, rail=rail):
            return None

        rate_1h, baseline = self._stress_window_rates(corridor, rail=rail)
        ratio = (rate_1h / baseline) if baseline > 0 else float("inf")
        event = StressRegimeEvent(
            corridor=corridor,
            failure_rate_1h=rate_1h,
            baseline_rate=baseline,
            ratio=ratio,
            triggered_at=self._time(),
            rail=rail.upper() if rail else None,
        )
        self._emit(event)
        return event

    def _stress_window_rates(
        self,
        corridor: str,
        rail: Optional[str] = None,
    ) -> Tuple[float, float]:
        """Return ``(current_rate, baseline_excl_current_rate)``.

        Uses the same window split as :meth:`is_stressed` so that
        :class:`StressRegimeEvent` ``ratio`` is directly comparable to
        ``threshold_multiplier``.
        """
        self._cleanup(corridor, rail=rail)
        history = self._history[self._bucket_key(corridor, rail)]
        _, current_window, _ = self._windows_for(rail)
        now = self._time()
        current_cutoff = now - current_window

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

    def get_rates(
        self,
        corridor: str,
        rail: Optional[str] = None,
    ) -> Tuple[float, float]:
        """Return ``(current_rate, baseline_rate)`` for a corridor.

        Both rates are in the range [0.0, 1.0].  Returns ``(0.0, 0.0)`` if
        no events have been recorded.
        """
        self._cleanup(corridor, rail=rail)
        history = self._history[self._bucket_key(corridor, rail)]
        _, current_window, _ = self._windows_for(rail)
        now = self._time()

        current_cutoff = now - current_window
        current_events = [h for h in history if h[0] >= current_cutoff]
        current_rate = (
            sum(1 for h in current_events if h[1]) / len(current_events)
            if current_events
            else 0.0
        )

        # Overall baseline (entire baseline window, including current period)
        baseline_rate = (
            sum(1 for h in history if h[1]) / len(history) if history else 0.0
        )

        return current_rate, baseline_rate

    def _emit(self, event: StressRegimeEvent) -> None:
        """Publish event to Kafka with retry + DLQ routing.

        Flow:
          1. If no producer is configured → prototype mode, keep in-memory.
          2. Else: retry ``produce()`` up to ``_EMIT_MAX_RETRIES`` with
             exponential backoff (100ms / 200ms / 400ms).
          3. If all retries fail → route to the dead-letter topic with a
             ``source-topic`` header.
          4. Only if DLQ routing *also* fails → fall back to in-memory.
             That is a diagnostic last resort; it means Kafka is
             comprehensively unreachable and the operator needs to know.
        """
        if self._producer is None:
            logger.warning(
                "No Kafka producer configured — StressRegimeEvent stored in-memory: "
                "corridor=%s ratio=%.2f",
                event.corridor,
                event.ratio,
            )
            self.emitted_events.append(event)
            return

        key = event.corridor.encode()
        value = event.to_json().encode()

        last_exc: Optional[BaseException] = None
        for attempt in range(_EMIT_MAX_RETRIES):
            try:
                self._producer.produce(  # type: ignore[attr-defined]
                    topic=self.STRESS_TOPIC,
                    key=key,
                    value=value,
                )
                # Non-blocking: trigger any pending delivery callbacks so
                # librdkafka reclaims buffers before the next record.
                self._producer.poll(0)  # type: ignore[attr-defined]
                logger.info(
                    "StressRegimeEvent emitted → Kafka: corridor=%s ratio=%.2f",
                    event.corridor,
                    event.ratio,
                )
                return
            except Exception as exc:  # broad: librdkafka can raise many types
                last_exc = exc
                backoff_ms = _EMIT_BACKOFF_BASE_MS * (2**attempt)
                logger.warning(
                    "StressRegimeEvent produce failed (attempt %d/%d, backoff %dms): %s",
                    attempt + 1,
                    _EMIT_MAX_RETRIES,
                    backoff_ms,
                    exc,
                )
                time.sleep(backoff_ms / 1000.0)

        # All retries exhausted → route to DLQ
        logger.error(
            "StressRegimeEvent produce exhausted retries, routing to DLQ: "
            "corridor=%s err=%s",
            event.corridor,
            last_exc,
        )
        try:
            self._producer.produce(  # type: ignore[attr-defined]
                topic=_DEAD_LETTER_TOPIC,
                key=key,
                value=value,
                headers={
                    "source-topic": self.STRESS_TOPIC,
                    "error": str(last_exc)[:200] if last_exc is not None else "unknown",
                },
            )
            self._producer.poll(0)  # type: ignore[attr-defined]
            return
        except Exception:
            # DLQ itself is down — this is the only path that hits the
            # in-memory fallback in production. Callers reading
            # emitted_events see what was uncapturable at the broker.
            logger.exception(
                "StressRegimeEvent DLQ route also failed — buffering in-memory: "
                "corridor=%s",
                event.corridor,
            )
            self.emitted_events.append(event)

    def _cleanup(self, corridor: str, rail: Optional[str] = None) -> None:
        """Evict records older than the rail's baseline window."""
        baseline_window, _, _ = self._windows_for(rail)
        cutoff = self._time() - baseline_window
        dq = self._history[self._bucket_key(corridor, rail)]
        while dq and dq[0][0] < cutoff:
            dq.popleft()
