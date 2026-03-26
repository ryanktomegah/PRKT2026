"""
test_cancellation_detector.py — Tests for adversarial cancellation detection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from lip.c5_streaming.cancellation_detector import (
    CancellationAlert,
    CancellationDetector,
    CancellationEvent,
    normalize_camt056,
    normalize_pacs004,
)


def _make_cancellation_event(
    uetr: str = "test-uetr-001",
    cancellation_type: str = "CAMT056",
    requesting_bic: str = "TESTBIC1XXX",
    reason_code: str = "CUST",
    amount: Decimal = Decimal("1000000"),
) -> CancellationEvent:
    return CancellationEvent(
        uetr=uetr,
        cancellation_type=cancellation_type,
        requesting_bic=requesting_bic,
        reason_code=reason_code,
        amount=amount,
        currency="USD",
        timestamp=datetime.now(timezone.utc),
    )


class TestCancellationDetector:
    """Test the CancellationDetector."""

    def test_no_alert_without_funded_loan(self):
        detector = CancellationDetector()
        event = _make_cancellation_event()
        alerts = detector.process_cancellation(event)
        # No funded loan → no post-funding alert (may have repeat sender alert)
        assert not any(a.alert_type == "RAPID_RECALL" for a in alerts)

    def test_rapid_recall_alert(self):
        detector = CancellationDetector(suspicion_window_seconds=60)
        # Register a funded loan
        detector.register_funding("test-uetr-001")
        # Send cancellation immediately
        event = _make_cancellation_event(uetr="test-uetr-001")
        alerts = detector.process_cancellation(event)
        rapid_alerts = [a for a in alerts if a.alert_type == "RAPID_RECALL"]
        assert len(rapid_alerts) == 1
        assert rapid_alerts[0].severity == "HIGH"
        assert rapid_alerts[0].recommended_action == "HUMAN_REVIEW"

    def test_post_funding_recall_alert(self):
        detector = CancellationDetector(suspicion_window_seconds=1)
        # Register funding in the past
        from datetime import timedelta
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        detector.register_funding("test-uetr-002", funded_at=past)
        # Send cancellation now (outside rapid window)
        event = _make_cancellation_event(uetr="test-uetr-002")
        alerts = detector.process_cancellation(event)
        post_alerts = [a for a in alerts if a.alert_type == "POST_FUNDING_RECALL"]
        assert len(post_alerts) == 1
        assert post_alerts[0].severity == "MEDIUM"

    def test_repeat_sender_alert(self):
        detector = CancellationDetector(sender_recall_threshold=2)
        # Same sender, multiple recalls
        for i in range(3):
            event = _make_cancellation_event(
                uetr=f"uetr-{i}",
                requesting_bic="REPEAT_BIC",
            )
            alerts = detector.process_cancellation(event)
        # Third recall should trigger REPEAT_SENDER
        repeat_alerts = [a for a in alerts if a.alert_type == "REPEAT_SENDER"]
        assert len(repeat_alerts) >= 1

    def test_deregister_funding(self):
        detector = CancellationDetector()
        detector.register_funding("test-uetr")
        assert detector.get_funded_loan_count() == 1
        detector.deregister_funding("test-uetr")
        assert detector.get_funded_loan_count() == 0

    def test_funded_loan_count(self):
        detector = CancellationDetector()
        detector.register_funding("uetr-1")
        detector.register_funding("uetr-2")
        assert detector.get_funded_loan_count() == 2


class TestCamt056Normalization:
    """Test camt.056 message normalization."""

    def test_basic_camt056(self):
        msg = {
            "Assgnmt": {
                "CreDtTm": "2025-06-15T12:00:00+00:00",
                "Assgnr": {
                    "Agt": {"FinInstnId": {"BIC": "TESTBIC1XXX"}},
                },
            },
            "Undrlyg": {
                "TxInf": {
                    "OrgnlUETR": "test-uetr-123",
                    "CxlRsnInf": {
                        "Rsn": {"Cd": "CUST"},
                    },
                    "OrgnlIntrBkSttlmAmt": {"value": "500000", "Ccy": "EUR"},
                },
            },
        }
        event = normalize_camt056(msg)
        assert event.uetr == "test-uetr-123"
        assert event.cancellation_type == "CAMT056"
        assert event.requesting_bic == "TESTBIC1XXX"
        assert event.reason_code == "CUST"
        assert event.amount == Decimal("500000")

    def test_missing_fields_handled(self):
        event = normalize_camt056({})
        assert event.cancellation_type == "CAMT056"
        assert event.uetr == ""


class TestPacs004Normalization:
    """Test pacs.004 message normalization."""

    def test_basic_pacs004(self):
        msg = {
            "GrpHdr": {
                "CreDtTm": "2025-06-15T12:00:00+00:00",
                "InstgAgt": {"FinInstnId": {"BIC": "RETBIC1XXX"}},
            },
            "TxInf": {
                "OrgnlUETR": "return-uetr-456",
                "RtrRsnInf": {
                    "Rsn": {"Cd": "FOCR"},
                },
                "RtrdIntrBkSttlmAmt": {"value": "750000", "Ccy": "USD"},
            },
        }
        event = normalize_pacs004(msg)
        assert event.uetr == "return-uetr-456"
        assert event.cancellation_type == "PACS004"
        assert event.requesting_bic == "RETBIC1XXX"
        assert event.reason_code == "FOCR"


class TestCancellationAlertDataclass:
    """Test CancellationAlert structure."""

    def test_recommended_action_always_human_review(self):
        alert = CancellationAlert(
            uetr="test",
            alert_type="RAPID_RECALL",
            severity="HIGH",
            description="Test alert",
            cancellation_event=_make_cancellation_event(),
            time_since_funding_seconds=10.0,
            sender_recall_count_24h=1,
        )
        assert alert.recommended_action == "HUMAN_REVIEW"
