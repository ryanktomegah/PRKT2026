"""
royalty_batch.py — Monthly royalty batch settlement scheduler.
GAP-05: Triggers generate_monthly_settlement() on the 1st business day of
        each month. Also triggerable manually via admin endpoint.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, List, Optional

from lip.common.royalty_settlement import BPIRoyaltySettlement, MonthlySettlementReport

logger = logging.getLogger(__name__)


class RoyaltyBatchScheduler:
    """Triggers monthly royalty settlement generation.

    Parameters
    ----------
    royalty_settlement:
        :class:`~lip.common.royalty_settlement.BPIRoyaltySettlement` instance.
    notification_service:
        Optional notification service for ROYALTY_SETTLEMENT_GENERATED events.
    redis_client:
        Optional Redis client for storing generated reports.
    check_interval_seconds:
        How often to check if settlement is due (default 3600s = 1h).
    """

    def __init__(
        self,
        royalty_settlement: BPIRoyaltySettlement,
        notification_service: Any = None,
        redis_client: Any = None,
        check_interval_seconds: float = 3600.0,
    ) -> None:
        self._settlement = royalty_settlement
        self._notification = notification_service
        self._redis = redis_client
        self._interval = check_interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_generated_month: Optional[str] = None  # "YYYY-MM"

    def generate_now(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[MonthlySettlementReport]:
        """Manually trigger settlement generation for a specific month.

        Defaults to the previous month if not specified.
        """
        now = datetime.now(tz=timezone.utc)
        if month is None or year is None:
            # Default to previous month
            if now.month == 1:
                month = 12
                year = now.year - 1
            else:
                month = now.month - 1
                year = now.year

        reports = self._settlement.generate_monthly_settlement(month=month, year=year)
        logger.info(
            "Royalty batch generated: month=%d year=%d reports=%d",
            month, year, len(reports),
        )

        # Store to Redis if available
        if self._redis is not None and reports:
            try:
                import json
                key = f"lip:royalty:settlement:{year}:{month:02d}"
                data = json.dumps([
                    {
                        "licensee_id": r.licensee_id,
                        "month": r.month,
                        "year": r.year,
                        "total_royalty_usd": str(r.total_royalty_usd),
                        "transaction_count": r.transaction_count,
                        "generated_at": r.generated_at.isoformat(),
                    }
                    for r in reports
                ])
                self._redis.set(key, data.encode())
                logger.debug("Royalty settlement stored to Redis: %s", key)
            except Exception as exc:
                logger.warning("Failed to store royalty settlement to Redis: %s", exc)

        # Notify
        if self._notification is not None and reports:
            try:
                from lip.common.notification_service import NotificationEventType
                for report in reports:
                    self._notification.notify(
                        event_type=NotificationEventType.LOAN_REPAID,
                        uetr="BATCH_SETTLEMENT",
                        licensee_id=report.licensee_id,
                        payload={
                            "type": "ROYALTY_SETTLEMENT_GENERATED",
                            "month": month,
                            "year": year,
                            "total_royalty_usd": str(report.total_royalty_usd),
                            "transaction_count": report.transaction_count,
                        },
                    )
            except Exception as exc:
                logger.warning("Royalty batch notification failed: %s", exc)

        self._last_generated_month = f"{year}-{month:02d}"
        return reports

    def _is_first_business_day(self) -> bool:
        """Check if today is the 1st business day of the month (Mon–Fri, day 1–3)."""
        now = datetime.now(tz=timezone.utc)
        # Weekday: 0=Mon, 5=Sat, 6=Sun
        if now.weekday() >= 5:
            return False
        # On the 1st, or the 2nd/3rd if the 1st was a weekend
        if now.day == 1:
            return True
        if now.day == 2 and datetime(now.year, now.month, 1).weekday() >= 5:
            return True
        if now.day == 3 and datetime(now.year, now.month, 1).weekday() == 6:
            return True
        return False

    def _should_generate(self) -> bool:
        now = datetime.now(tz=timezone.utc)
        current_key = f"{now.year}-{now.month:02d}"
        if self._last_generated_month == current_key:
            return False  # Already generated this month
        return self._is_first_business_day()

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="royalty-batch")
        self._thread.start()
        logger.info("Royalty batch scheduler started (interval=%.0fs)", self._interval)

    def stop(self) -> None:
        """Stop the background scheduler thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
        logger.info("Royalty batch scheduler stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self._should_generate():
                    self.generate_now()
            except Exception:
                logger.exception("Royalty batch scheduler error")
            self._stop_event.wait(timeout=self._interval)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
