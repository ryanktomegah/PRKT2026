"""
test_gap13_notifications.py — Tests for GAP-13:
Customer-facing notification framework for bridge-loan lifecycle events.
"""

from lip.common.notification_service import (
    NotificationEventType,
    NotificationRecord,
    NotificationService,
)

# ---------------------------------------------------------------------------
# 1–6: NotificationRecord + core notify() behaviour
# ---------------------------------------------------------------------------

class TestNotificationServiceCore:
    def test_notify_creates_record(self):
        """notify() returns a NotificationRecord with a non-empty id."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.LOAN_FUNDED, uetr="uetr-001")
        assert isinstance(record, NotificationRecord)
        assert record.notification_id

    def test_notify_correct_event_type(self):
        """Created record carries the correct event_type."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.LOAN_REPAID, uetr="uetr-002")
        assert record.event_type == NotificationEventType.LOAN_REPAID

    def test_notify_correct_uetr(self):
        """Created record carries the supplied UETR."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.OFFER_EXPIRED, uetr="uetr-003")
        assert record.uetr == "uetr-003"

    def test_notify_correct_licensee_id(self):
        """Created record carries the supplied licensee_id."""
        svc = NotificationService()
        record = svc.notify(
            NotificationEventType.LOAN_DECLINED, uetr="u", licensee_id="bank-abc"
        )
        assert record.licensee_id == "bank-abc"

    def test_notify_payload_attached(self):
        """Custom payload dict is preserved on the record."""
        svc = NotificationService()
        record = svc.notify(
            NotificationEventType.LOAN_FUNDED,
            uetr="u",
            payload={"loan_id": "L1", "amount": "500000"},
        )
        assert record.payload["loan_id"] == "L1"
        assert record.payload["amount"] == "500000"

    def test_notify_created_at_is_utc(self):
        """created_at is a timezone-aware UTC datetime."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u")
        assert record.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# 7–9: Retrieval and filtering
# ---------------------------------------------------------------------------

class TestNotificationRetrieval:
    def test_get_notification_by_id(self):
        """get_notification() returns the record for a known id."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u")
        fetched = svc.get_notification(record.notification_id)
        assert fetched is record

    def test_get_notifications_filter_by_licensee(self):
        """get_notifications(licensee_id=...) returns only that licensee's records."""
        svc = NotificationService()
        svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u1", licensee_id="bank-A")
        svc.notify(NotificationEventType.LOAN_REPAID, uetr="u2", licensee_id="bank-B")
        svc.notify(NotificationEventType.OFFER_EXPIRED, uetr="u3", licensee_id="bank-A")

        bank_a = svc.get_notifications(licensee_id="bank-A")
        assert len(bank_a) == 2
        assert all(r.licensee_id == "bank-A" for r in bank_a)

    def test_get_notifications_filter_by_event_type(self):
        """get_notifications(event_type=...) returns only that type."""
        svc = NotificationService()
        svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u1")
        svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u2")
        svc.notify(NotificationEventType.LOAN_REPAID, uetr="u3")

        funded = svc.get_notifications(event_type=NotificationEventType.LOAN_FUNDED)
        assert len(funded) == 2
        assert all(r.event_type == NotificationEventType.LOAN_FUNDED for r in funded)


# ---------------------------------------------------------------------------
# 10–12: Delivery callback and mark_delivered
# ---------------------------------------------------------------------------

class TestNotificationDelivery:
    def test_delivery_callback_fires(self):
        """Delivery callback is invoked once per notify() call."""
        delivered = []
        svc = NotificationService(delivery_callback=lambda r: delivered.append(r))
        svc.notify(NotificationEventType.OFFER_ACCEPTED, uetr="u")
        assert len(delivered) == 1

    def test_delivery_callback_marks_record_delivered(self):
        """After callback succeeds, record.delivered is True."""
        svc = NotificationService(delivery_callback=lambda r: None)
        record = svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u")
        assert record.delivered is True

    def test_delivery_callback_failure_does_not_lose_record(self):
        """If callback raises, the record is still persisted."""
        def bad_callback(r):
            raise RuntimeError("transport error")

        svc = NotificationService(delivery_callback=bad_callback)
        record = svc.notify(NotificationEventType.LOAN_DECLINED, uetr="u")
        # Record persisted even though delivery failed
        assert svc.get_notification(record.notification_id) is record
        assert record.delivered is False

    def test_mark_delivered_updates_flag(self):
        """mark_delivered() sets delivered=True for the given notification_id."""
        svc = NotificationService()
        record = svc.notify(NotificationEventType.LOAN_OVERDUE, uetr="u")
        assert record.delivered is False
        result = svc.mark_delivered(record.notification_id)
        assert result is True
        assert record.delivered is True

    def test_mark_delivered_returns_false_for_unknown_id(self):
        """mark_delivered() returns False for an unknown notification_id."""
        svc = NotificationService()
        assert svc.mark_delivered("nonexistent-id") is False


# ---------------------------------------------------------------------------
# 13–14: Webhook and record count
# ---------------------------------------------------------------------------

class TestNotificationWebhook:
    def test_register_webhook_stores_url(self):
        """register_webhook() updates the webhook_url property."""
        svc = NotificationService()
        assert svc.webhook_url is None
        svc.register_webhook("https://bank.example.com/lip/notify")
        assert svc.webhook_url == "https://bank.example.com/lip/notify"

    def test_record_count_increments(self):
        """record_count reflects the total number of notify() calls."""
        svc = NotificationService()
        assert svc.record_count == 0
        svc.notify(NotificationEventType.LOAN_FUNDED, uetr="u1")
        svc.notify(NotificationEventType.LOAN_REPAID, uetr="u2")
        assert svc.record_count == 2


# ---------------------------------------------------------------------------
# 15: All event types exercise
# ---------------------------------------------------------------------------

class TestAllEventTypes:
    def test_all_event_types_are_accepted(self):
        """NotificationService accepts all six NotificationEventType values."""
        svc = NotificationService()
        for et in NotificationEventType:
            record = svc.notify(et, uetr="u")
            assert record.event_type == et
        assert svc.record_count == len(NotificationEventType)
