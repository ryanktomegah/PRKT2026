"""
override_sweeper.py — Periodic sweep for expired human override requests.
GAP-08: Unresolved override requests must be automatically resolved after
        their timeout window using the configured timeout_action (DECLINE or OFFER).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

try:
    from lip.common.notification_service import NotificationEventType as _NotificationEventType
except ImportError:
    _NotificationEventType = None  # type: ignore[misc]

logger = logging.getLogger(__name__)


class OverrideSweeper:
    """Periodically scans for expired human override requests and resolves them.

    Parameters
    ----------
    human_override:
        :class:`~lip.c7_execution_agent.human_override.HumanOverrideInterface` to scan.
    decision_logger:
        Optional :class:`~lip.c7_execution_agent.decision_log.DecisionLogger` for audit.
    notification_service:
        Optional :class:`~lip.common.notification_service.NotificationService` for alerts.
    sweep_interval_seconds:
        How often to scan for expired requests (default 30s).
    """

    def __init__(
        self,
        human_override: Any,
        decision_logger: Any = None,
        notification_service: Any = None,
        sweep_interval_seconds: float = 30.0,
    ) -> None:
        self._override = human_override
        self._decision_logger = decision_logger
        self._notification_service = notification_service
        self._interval = sweep_interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._resolved_count = 0

    def start(self) -> None:
        """Start the background sweeper thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="override-sweeper")
        self._thread.start()
        logger.info("Override sweeper started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        """Stop the background sweeper thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
        logger.info("Override sweeper stopped (resolved=%d)", self._resolved_count)

    def sweep_once(self) -> int:
        """Run a single sweep and return the number of expired requests resolved."""
        resolved = 0
        # B4-15: Use the public get_all_pending_requests() method instead of
        # accessing the private _pending attribute directly. This method returns
        # all pending requests (including expired ones) under the lock, giving
        # us a consistent snapshot without coupling to internal representation.
        pending = self._override.get_all_pending_requests()
        for req in pending:
            if not self._override.is_expired(req.request_id):
                continue
            try:
                action = self._override.resolve_expired(req.request_id)
                self._resolved_count += 1
                resolved += 1
                logger.info(
                    "Sweeper resolved expired override: request_id=%s uetr=%s action=%s",
                    req.request_id,
                    req.uetr,
                    action,
                )

                # Notify if notification service is wired
                # B4-16: NotificationEventType imported at module level (not inside method)
                if self._notification_service is not None and _NotificationEventType is not None:
                    try:
                        event_type = (
                            _NotificationEventType.LOAN_DECLINED
                            if action == "DECLINE"
                            else _NotificationEventType.OFFER_ACCEPTED
                        )
                        self._notification_service.notify(
                            event_type=event_type,
                            uetr=req.uetr,
                            payload={
                                "reason": "override_expired",
                                "timeout_action": action,
                                "request_id": req.request_id,
                            },
                        )
                    except Exception as exc:
                        logger.warning("Sweeper notification failed: %s", exc)

            except ValueError:
                # Already resolved or not expired — race condition, skip
                pass

        return resolved

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.sweep_once()
            except Exception:
                logger.exception("Override sweeper error")
            self._stop_event.wait(timeout=self._interval)

    @property
    def resolved_count(self) -> int:
        return self._resolved_count

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
