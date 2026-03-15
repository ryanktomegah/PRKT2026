"""
notification_service.py — Customer-facing notification framework.
GAP-13: Bridge loan events must be surfaced to the borrower/ELO
        for operational transparency and regulatory traceability.

Notification event types:
  LOAN_FUNDED    — Bridge disbursement confirmed (C3 loan registered)
  LOAN_REPAID    — Repayment settled and loan deregistered
  LOAN_OVERDUE   — Maturity reached without settlement signal
  OFFER_EXPIRED  — Loan offer window elapsed without ELO acceptance
  LOAN_DECLINED  — C7 returned DECLINE / BLOCK / CURRENCY_NOT_SUPPORTED
  OFFER_ACCEPTED — ELO treasury accepted the loan offer

Design:
  NotificationService is a pure in-process bus; actual HTTP delivery is
  delegated to an optional ``delivery_callback``.  This keeps the core
  platform independent of transport (webhook, Kafka, SMTP) while providing
  a complete, auditable notification log for regulatory inspection.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------

class NotificationEventType(str, Enum):
    """Lifecycle events that trigger customer-facing notifications (GAP-13)."""

    LOAN_FUNDED = "LOAN_FUNDED"
    """Bridge disbursement sent; C3 has registered the ActiveLoan."""

    LOAN_REPAID = "LOAN_REPAID"
    """Repayment sweep completed; loan deregistered from C3."""

    LOAN_OVERDUE = "LOAN_OVERDUE"
    """Maturity date reached with no incoming settlement signal."""

    OFFER_EXPIRED = "OFFER_EXPIRED"
    """15-minute offer acceptance window closed without ELO response."""

    LOAN_DECLINED = "LOAN_DECLINED"
    """C7 declined the payment (DECLINE / BLOCK / CURRENCY_NOT_SUPPORTED)."""

    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    """ELO treasury accepted the loan offer; disbursement pending."""


# ---------------------------------------------------------------------------
# Notification record
# ---------------------------------------------------------------------------

@dataclass
class NotificationRecord:
    """Immutable audit record for a single notification event.

    Attributes
    ----------
    notification_id:
        UUID string; unique per notification.
    event_type:
        One of the :class:`NotificationEventType` values.
    uetr:
        SWIFT UETR of the payment that triggered this notification.
    licensee_id:
        Hashed/opaque identifier of the BPI licensee (bank) for
        multi-tenant filtering.
    payload:
        Arbitrary event-specific metadata (loan_id, amount, etc.).
    created_at:
        UTC timestamp of notification creation.
    delivered:
        True once the ``delivery_callback`` has confirmed delivery.
    """

    notification_id: str
    event_type: NotificationEventType
    uetr: str
    licensee_id: str
    payload: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    delivered: bool = False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class NotificationService:
    """Manages customer-facing bridge-loan event notifications (GAP-13).

    All notifications are stored in memory for audit retrieval.  An optional
    ``delivery_callback`` handles outbound transport (webhook POST, Kafka
    publish, SMTP).  If the callback raises, the notification is still
    persisted — delivery failure does not suppress the event log.

    Parameters
    ----------
    webhook_url:
        Default webhook endpoint stamped on each record (informational only).
    delivery_callback:
        Called synchronously for each notification.  Signature:
        ``(NotificationRecord) -> None``.  Exceptions are caught and logged.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        delivery_callback: Optional[Callable[[NotificationRecord], None]] = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._delivery_callback = delivery_callback
        self._records: Dict[str, NotificationRecord] = {}

    # ── Core notification dispatch ────────────────────────────────────────────

    def notify(
        self,
        event_type: NotificationEventType,
        uetr: str,
        licensee_id: str = "",
        payload: Optional[Dict] = None,
    ) -> NotificationRecord:
        """Create and deliver a notification record.

        Parameters
        ----------
        event_type:
            Lifecycle event that triggered this notification.
        uetr:
            SWIFT UETR of the associated payment.
        licensee_id:
            Opaque BPI licensee identifier for multi-tenant filtering.
        payload:
            Optional dict with event-specific context (loan_id, amount, …).

        Returns
        -------
        NotificationRecord
            The created record; ``delivered`` is True if the callback succeeded.
        """
        record = NotificationRecord(
            notification_id=str(uuid.uuid4()),
            event_type=event_type,
            uetr=uetr,
            licensee_id=licensee_id,
            payload=payload or {},
        )
        self._records[record.notification_id] = record
        logger.info(
            "Notification created: id=%s type=%s uetr=%s licensee=%s",
            record.notification_id, event_type.value, uetr, licensee_id,
        )

        if self._delivery_callback is not None:
            try:
                self._delivery_callback(record)
                record.delivered = True
                logger.debug(
                    "Notification delivered: id=%s", record.notification_id
                )
            except Exception as exc:
                logger.warning(
                    "Notification delivery failed: id=%s error=%s",
                    record.notification_id, exc,
                )

        return record

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_notification(self, notification_id: str) -> Optional[NotificationRecord]:
        """Return a single notification record by ID, or None."""
        return self._records.get(notification_id)

    def get_notifications(
        self,
        licensee_id: Optional[str] = None,
        event_type: Optional[NotificationEventType] = None,
    ) -> List[NotificationRecord]:
        """Return all notifications matching the optional filters.

        Parameters
        ----------
        licensee_id:
            When provided, restrict to notifications for this licensee.
        event_type:
            When provided, restrict to this event type.
        """
        records = list(self._records.values())
        if licensee_id is not None:
            records = [r for r in records if r.licensee_id == licensee_id]
        if event_type is not None:
            records = [r for r in records if r.event_type == event_type]
        return records

    def mark_delivered(self, notification_id: str) -> bool:
        """Manually mark a notification as delivered.

        Returns True if the record was found and updated, False otherwise.
        """
        record = self._records.get(notification_id)
        if record is None:
            return False
        record.delivered = True
        return True

    # ── Configuration ─────────────────────────────────────────────────────────

    def register_webhook(self, url: str) -> None:
        """Update the webhook URL for outbound delivery metadata."""
        self._webhook_url = url
        logger.debug("Webhook registered: %s", url)

    @property
    def webhook_url(self) -> Optional[str]:
        """Current outbound webhook URL, or None."""
        return self._webhook_url

    @property
    def record_count(self) -> int:
        """Total notifications created in this session."""
        return len(self._records)
