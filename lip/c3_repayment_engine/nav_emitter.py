"""
nav_emitter.py — Per-tenant NAV snapshot emitter.
P3 Platform Licensing, C3 extension (Sprint 2d).

Emits NAVEvent (schemas.py) per active tenant every 60 minutes.
Settlement history tracked in a thread-safe rolling deque for
settled_last_60min computation.

trailing_loss_rate_30d defaults to Decimal("0") — real loss-rate
computation requires default/loss event tracking (Sprint 5).
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from lip.common.schemas import NAVEvent
from lip.infrastructure.monitoring.metrics import (
    METRIC_TENANT_ACTIVE_LOANS,
    METRIC_TENANT_EXPOSURE_USD,
)

logger = logging.getLogger(__name__)

_SIXTY_MINUTES = timedelta(minutes=60)
_THIRTY_DAYS = timedelta(days=30)


@dataclass
class _SettlementRecord:
    """Internal record for settlement history tracking."""
    tenant_id: str
    amount: Decimal
    timestamp: datetime


class NAVEventEmitter:
    """Per-tenant NAV snapshot emitter with settlement history.

    Args:
        get_active_loans: Callable returning List[ActiveLoan] — typically
            ``repayment_loop.get_active_loans`` (bound method).
        nav_callback: Called with each NAVEvent (one per tenant per cycle).
        interval_seconds: Background emission interval (default 3600 = 60 min).
        metrics_collector: Optional PrometheusMetricsCollector for gauge updates.
    """

    def __init__(
        self,
        get_active_loans: Callable,
        nav_callback: Callable[[NAVEvent], None],
        interval_seconds: int = 3600,
        metrics_collector: object = None,
    ) -> None:
        self._get_active_loans = get_active_loans
        self._nav_callback = nav_callback
        self._interval = interval_seconds
        self._metrics = metrics_collector

        # Settlement history: tenant_id -> deque of _SettlementRecord
        self._history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100_000)
        )
        self._history_lock = threading.Lock()

        # Background thread control
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- Settlement history -------------------------------------------------

    def record_settlement(
        self,
        tenant_id: str,
        amount: Decimal,
        timestamp: datetime,
    ) -> None:
        """Record a settlement for NAV history tracking.

        Called by SettlementCallbackBridge on the RepaymentLoop thread.
        Thread-safe via _history_lock.
        """
        record = _SettlementRecord(
            tenant_id=tenant_id, amount=amount, timestamp=timestamp,
        )
        with self._history_lock:
            self._history[tenant_id].append(record)

    def _get_settled_last_60min(
        self, tenant_id: str, now: datetime,
    ) -> Tuple[int, Decimal]:
        """Return (count, total_amount) of settlements in the last 60 minutes."""
        cutoff = now - _SIXTY_MINUTES
        count = 0
        total = Decimal("0")
        with self._history_lock:
            for rec in self._history.get(tenant_id, []):
                if rec.timestamp >= cutoff:
                    count += 1
                    total += rec.amount
        return count, total

    def _purge_old_history(self, now: datetime) -> None:
        """Remove settlement records older than 30 days."""
        cutoff = now - _THIRTY_DAYS
        with self._history_lock:
            for tenant_id in list(self._history.keys()):
                dq = self._history[tenant_id]
                while dq and dq[0].timestamp < cutoff:
                    dq.popleft()
                if not dq:
                    del self._history[tenant_id]

    # -- NAV snapshot -------------------------------------------------------

    def emit_snapshot(self) -> List[NAVEvent]:
        """Compute and emit per-tenant NAV events (synchronous).

        Groups active loans by licensee_id, computes NAV fields,
        invokes nav_callback per tenant, and updates metrics.

        Returns list of emitted NAVEvent objects (useful for testing).
        """
        now = datetime.now(tz=timezone.utc)
        loans = self._get_active_loans()

        # Group by tenant
        by_tenant: Dict[str, list] = defaultdict(list)
        for loan in loans:
            if loan.licensee_id:
                by_tenant[loan.licensee_id].append(loan)

        events: List[NAVEvent] = []
        for tenant_id, tenant_loans in sorted(by_tenant.items()):
            active_count = len(tenant_loans)
            total_exposure = sum(
                (loan.principal for loan in tenant_loans), Decimal("0"),
            )
            settled_count, settled_amount = self._get_settled_last_60min(
                tenant_id, now,
            )

            nav = NAVEvent(
                tenant_id=tenant_id,
                active_loans=active_count,
                total_exposure_usd=total_exposure,
                settled_last_60min=settled_count,
                settled_amount_last_60min_usd=settled_amount,
                trailing_loss_rate_30d=Decimal("0"),  # Sprint 5: real loss tracking
                timestamp=now,
            )
            events.append(nav)

            try:
                self._nav_callback(nav)
            except Exception as exc:
                logger.error(
                    "NAV callback failed for tenant=%s: %s", tenant_id, exc,
                )

            # Update metrics
            if self._metrics is not None:
                self._metrics.add_gauge(
                    METRIC_TENANT_ACTIVE_LOANS,
                    float(active_count),
                    {"tenant_id": tenant_id},
                )
                self._metrics.add_gauge(
                    METRIC_TENANT_EXPOSURE_USD,
                    float(total_exposure),
                    {"tenant_id": tenant_id},
                )

        # Purge stale history periodically
        self._purge_old_history(now)

        return events

    # -- Background thread --------------------------------------------------

    def start(self, interval_seconds: Optional[int] = None) -> None:
        """Start the background NAV emission thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning(
                "NAVEventEmitter already running; ignoring duplicate start.",
            )
            return

        interval = interval_seconds or self._interval
        self._stop_event.clear()

        def _loop() -> None:
            logger.info(
                "NAVEventEmitter thread started (interval=%ds).", interval,
            )
            while not self._stop_event.wait(timeout=interval):
                try:
                    events = self.emit_snapshot()
                    if events:
                        logger.info(
                            "NAV emission: %d tenant(s) snapshotted.",
                            len(events),
                        )
                except Exception as exc:
                    logger.exception("Error in NAV emission cycle: %s", exc)
            logger.info("NAVEventEmitter thread stopped.")

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="NAVEventEmitter",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the NAV emission thread to stop and wait for exit."""
        if self._thread is None:
            return
        logger.info("Stopping NAVEventEmitter thread...")
        self._stop_event.set()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            logger.warning(
                "NAVEventEmitter thread did not stop within timeout.",
            )
        self._thread = None
