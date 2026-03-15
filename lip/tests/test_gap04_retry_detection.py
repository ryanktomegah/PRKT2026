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
    c6.check.return_value = MagicMock(passed=True)
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
        assert result.outcome == "FUNDED"
        assert uetr_tracker.is_retry(uetr)
        assert uetr_tracker.get_outcome(uetr) == "FUNDED"

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
        assert uetr_tracker.get_outcome(uetr) == "FUNDED"

    def test_different_uetrs_not_blocked(self, pipeline):
        p1 = pipeline.process(_make_event("uetr-a"))
        p2 = pipeline.process(_make_event("uetr-b"))

        assert p1.outcome == "FUNDED"
        assert p2.outcome == "FUNDED"

    def test_failed_outcomes_also_recorded(self, pipeline, uetr_tracker):
        # Mock C7 to DECLINE
        pipeline._c7.process_payment.return_value = {"status": "DECLINE", "loan_offer": None}

        uetr = "uetr-decline"
        pipeline.process(_make_event(uetr))

        assert uetr_tracker.get_outcome(uetr) == "DECLINED"

        # Retry should still be blocked even if original was DECLINED
        result = pipeline.process(_make_event(uetr))
        assert result.outcome == "RETRY_BLOCKED"
