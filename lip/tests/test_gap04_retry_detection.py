"""
test_gap04_retry_detection.py — Integration tests for GAP-04: Retry detection.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.common.uetr_tracker import UETRTracker
from lip.pipeline import LIPPipeline


@pytest.fixture
def uetr_tracker():
    return UETRTracker()

@pytest.fixture
def pipeline(uetr_tracker):
    c1 = MagicMock()
    c1.predict.return_value = {"failure_probability": 0.8, "above_threshold": True}
    c2 = MagicMock()
    c2.predict.return_value = {"pd_score": 0.05, "fee_bps": 300, "tier": 3}
    c4 = MagicMock()
    c4.classify.return_value = {"dispute_class": "NOT_DISPUTE"}
    c6 = MagicMock()
    c6.check.return_value = MagicMock(passed=True, anomaly_flagged=False)
    c7 = MagicMock()
    c7.process_payment.return_value = {"status": "OFFER", "loan_offer": {"loan_id": "L1", "fee_bps": 300}}
    c7.aml_dollar_cap_usd = 1000000
    c7.aml_count_cap = 100

    return LIPPipeline(
        c1_engine=c1,
        c2_engine=c2,
        c4_classifier=c4,
        c6_checker=c6,
        c7_agent=c7,
        uetr_tracker=uetr_tracker
    )

def _make_event(uetr: str):
    return NormalizedEvent(
        uetr=uetr,
        individual_payment_id="pid-1",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=Decimal("10000"),
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="CURR",
        narrative=None,
        raw_source={}
    )

class TestGap04RetryDetection:
    def test_first_run_succeeds_and_records(self, pipeline, uetr_tracker):
        uetr = "uetr-unique-1"
        event = _make_event(uetr)

        result = pipeline.process(event)
        assert result.outcome == "OFFERED"
        assert uetr_tracker.is_retry(uetr)
        assert uetr_tracker.get_outcome(uetr) == "OFFERED"

    def test_second_run_is_blocked(self, pipeline, uetr_tracker):
        uetr = "uetr-retry-1"
        event = _make_event(uetr)

        # First process
        pipeline.process(event)

        # Second process with same UETR
        result = pipeline.process(event)
        assert result.outcome == "RETRY_BLOCKED"
        # Ensure it didn't call C1 again (if it was recorded correctly)
        # We can verify by looking at the outcome in the tracker
        assert uetr_tracker.get_outcome(uetr) == "OFFERED"

    def test_different_payments_not_blocked(self, pipeline):
        """Genuinely different payments (different amounts) should not be blocked."""
        event_a = NormalizedEvent(
            uetr="uetr-a",
            individual_payment_id="pid-a",
            sending_bic="SENDER",
            receiving_bic="RECEIVER",
            amount=Decimal("10000"),
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )
        event_b = NormalizedEvent(
            uetr="uetr-b",
            individual_payment_id="pid-b",
            sending_bic="SENDER",
            receiving_bic="RECEIVER",
            amount=Decimal("50000"),  # different amount — not a retry
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )
        p1 = pipeline.process(event_a)
        p2 = pipeline.process(event_b)

        assert p1.outcome == "OFFERED"
        assert p2.outcome == "OFFERED"

    def test_failed_outcomes_also_recorded(self, pipeline, uetr_tracker):
        # Mock C7 to DECLINE
        pipeline._c7.process_payment.return_value = {"status": "DECLINE", "loan_offer": None}

        uetr = "uetr-decline"
        pipeline.process(_make_event(uetr))

        assert uetr_tracker.get_outcome(uetr) == "DECLINED"

        # Retry should still be blocked even if original was DECLINED
        result = pipeline.process(_make_event(uetr))
        assert result.outcome == "RETRY_BLOCKED"


class TestGap04TupleBasedRetryDetection:
    """GAP-04 full fix: detect manual retries with NEW UETRs but same payment details."""

    def test_new_uetr_same_payment_details_blocked(self, pipeline, uetr_tracker):
        """Manual retry: new UETR, same (sending_bic, receiving_bic, amount, currency)."""
        event1 = NormalizedEvent(
            uetr="uetr-original-001",
            individual_payment_id="pid-1",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("1000000"),
            currency="EUR",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )
        event2 = NormalizedEvent(
            uetr="uetr-manual-retry-001",  # NEW UETR
            individual_payment_id="pid-2",
            sending_bic="DEUTDEFF",          # same sender
            receiving_bic="BNPAFRPP",        # same receiver
            amount=Decimal("1000000"),       # same amount
            currency="EUR",                  # same currency
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )

        result1 = pipeline.process(event1)
        assert result1.outcome == "OFFERED"

        result2 = pipeline.process(event2)
        assert result2.outcome == "RETRY_BLOCKED"

    def test_new_uetr_same_details_fx_tolerance(self, pipeline, uetr_tracker):
        """Manual retry with FX rounding: amount differs by < 0.01%."""
        event1 = NormalizedEvent(
            uetr="uetr-fx-001",
            individual_payment_id="pid-1",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("1000000.00"),
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="AC01",
        )
        event2 = NormalizedEvent(
            uetr="uetr-fx-002",               # NEW UETR
            individual_payment_id="pid-2",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("1000050.00"),      # +0.005% — within 0.01% tolerance
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="AC01",
        )

        result1 = pipeline.process(event1)
        assert result1.outcome == "OFFERED"

        result2 = pipeline.process(event2)
        assert result2.outcome == "RETRY_BLOCKED"

    def test_different_sender_not_blocked(self, pipeline, uetr_tracker):
        """Different sending_bic should NOT be blocked as retry."""
        event1 = NormalizedEvent(
            uetr="uetr-diff-sender-001",
            individual_payment_id="pid-1",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("500000"),
            currency="EUR",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )
        event2 = NormalizedEvent(
            uetr="uetr-diff-sender-002",
            individual_payment_id="pid-2",
            sending_bic="COBADEFF",            # DIFFERENT sender
            receiving_bic="BNPAFRPP",
            amount=Decimal("500000"),
            currency="EUR",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="CURR",
        )

        result1 = pipeline.process(event1)
        assert result1.outcome == "OFFERED"

        result2 = pipeline.process(event2)
        assert result2.outcome == "OFFERED"  # different sender — not a retry

    def test_different_amount_beyond_tolerance_not_blocked(self, pipeline, uetr_tracker):
        """Amount difference > 0.01% should NOT be blocked."""
        event1 = NormalizedEvent(
            uetr="uetr-amt-001",
            individual_payment_id="pid-1",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("1000000"),
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="AC01",
        )
        event2 = NormalizedEvent(
            uetr="uetr-amt-002",
            individual_payment_id="pid-2",
            sending_bic="DEUTDEFF",
            receiving_bic="BNPAFRPP",
            amount=Decimal("1001000"),          # +0.1% — BEYOND tolerance
            currency="USD",
            timestamp=datetime.now(tz=timezone.utc),
            rail="SWIFT",
            rejection_code="AC01",
        )

        result1 = pipeline.process(event1)
        assert result1.outcome == "OFFERED"

        result2 = pipeline.process(event2)
        assert result2.outcome == "OFFERED"  # amount too different — not a retry
