"""
test_p10_shadow_pipeline.py — TDD tests for P10 TelemetryCollector.

Sprint 7: Shadow pipeline — first component in the data flow:
  NormalizedEvent (C5) → TelemetryCollector → TelemetryBatch → RegulatoryAnonymizer
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent

_SALT = b"shadow_test_salt_32bytes________"


def _make_event(
    *,
    uetr: str = "550e8400-e29b-41d4-a716-446655440000",
    individual_payment_id: str = "PAY-001",
    sending_bic: str = "DEUTDEFF",
    receiving_bic: str = "BNPAFRPP",
    amount: Decimal = Decimal("50000"),
    currency: str = "EUR",
    timestamp: datetime | None = None,
    rail: str = "SWIFT",
    rejection_code: str | None = None,
    telemetry_eligible: bool = True,
) -> NormalizedEvent:
    if timestamp is None:
        timestamp = datetime(2026, 4, 2, 14, 30, 0, tzinfo=timezone.utc)
    return NormalizedEvent(
        uetr=uetr,
        individual_payment_id=individual_payment_id,
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency=currency,
        timestamp=timestamp,
        rail=rail,
        rejection_code=rejection_code,
        telemetry_eligible=telemetry_eligible,
    )


class TestTelemetryCollector:
    """TDD tests for TelemetryCollector — Sprint 7."""

    def _make_collector(self):
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector
        return TelemetryCollector(salt=_SALT)

    def _flush_period(self):
        period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)
        return period_start, period_end

    # ------------------------------------------------------------------
    # Test 1: Single eligible event produces one batch with one corridor stat
    # ------------------------------------------------------------------
    def test_eligible_event_produces_batch(self):
        collector = self._make_collector()
        event = _make_event()
        result = collector.ingest(event)
        assert result is True

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        assert len(batches[0].corridor_statistics) == 1

    # ------------------------------------------------------------------
    # Test 2: Ineligible event is filtered — ingest returns False, flush empty
    # ------------------------------------------------------------------
    def test_ineligible_event_filtered(self):
        collector = self._make_collector()
        event = _make_event(telemetry_eligible=False)
        result = collector.ingest(event)
        assert result is False

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)
        assert batches == []

    # ------------------------------------------------------------------
    # Test 3: Amount bucket boundary conditions
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("amount,expected_bucket", [
        (Decimal("9999"),      "0-10K"),
        (Decimal("10000"),     "10K-100K"),
        (Decimal("99999"),     "10K-100K"),
        (Decimal("100000"),    "100K-1M"),
        (Decimal("10000000"), "10M+"),
    ])
    def test_amount_bucket_boundaries(self, amount, expected_bucket):
        collector = self._make_collector()
        event = _make_event(amount=amount)
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert stat.amount_bucket_distribution.get(expected_bucket, 0) == 1

    # ------------------------------------------------------------------
    # Test 4: EUR event corridor is a non-empty string
    # ------------------------------------------------------------------
    def test_corridor_from_currency(self):
        collector = self._make_collector()
        event = _make_event(currency="EUR")
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert isinstance(stat.corridor, str)
        assert len(stat.corridor) > 0

    # ------------------------------------------------------------------
    # Test 5: Two different BICs → two batches with different bank_hash values
    # ------------------------------------------------------------------
    def test_multiple_banks_separate_batches(self):
        collector = self._make_collector()
        event_a = _make_event(
            uetr="550e8400-e29b-41d4-a716-446655440001",
            individual_payment_id="PAY-A",
            sending_bic="DEUTDEFF",
        )
        event_b = _make_event(
            uetr="550e8400-e29b-41d4-a716-446655440002",
            individual_payment_id="PAY-B",
            sending_bic="BNPAFRPP",
        )
        collector.ingest(event_a)
        collector.ingest(event_b)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 2
        hashes = {b.bank_hash for b in batches}
        assert len(hashes) == 2

    # ------------------------------------------------------------------
    # Test 6: Second flush after first flush returns empty
    # ------------------------------------------------------------------
    def test_flush_clears_accumulators(self):
        collector = self._make_collector()
        event = _make_event()
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches_first = collector.flush(period_start, period_end)
        assert len(batches_first) == 1

        batches_second = collector.flush(period_start, period_end)
        assert batches_second == []

    # ------------------------------------------------------------------
    # Test 7: Every flushed batch has a non-empty hmac_signature
    # ------------------------------------------------------------------
    def test_batch_hmac_present(self):
        collector = self._make_collector()
        collector.ingest(_make_event(sending_bic="DEUTDEFF"))
        collector.ingest(_make_event(
            uetr="550e8400-e29b-41d4-a716-446655440002",
            individual_payment_id="PAY-B",
            sending_bic="BNPAFRPP",
        ))

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 2
        for batch in batches:
            assert isinstance(batch.hmac_signature, str)
            assert len(batch.hmac_signature) > 0

    # ------------------------------------------------------------------
    # Test 8: Failure class distribution — BLOCK (DNOR) and CLASS_A (AC01)
    # ------------------------------------------------------------------
    def test_failure_class_distribution(self):
        # BLOCK event
        collector_block = self._make_collector()
        # BLOCK codes cause telemetry_eligible=False in normalizer, but we can
        # directly set telemetry_eligible=True with rejection_code to test the
        # failure_class_distribution logic inside TelemetryCollector
        event_block = _make_event(rejection_code="DNOR", telemetry_eligible=True)
        collector_block.ingest(event_block)
        period_start, period_end = self._flush_period()
        batches = collector_block.flush(period_start, period_end)
        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert stat.failure_class_distribution.get("BLOCK", 0) == 1

        # CLASS_A event
        collector_a = self._make_collector()
        event_a = _make_event(rejection_code="AC01", telemetry_eligible=True)
        collector_a.ingest(event_a)
        batches_a = collector_a.flush(period_start, period_end)
        assert len(batches_a) == 1
        stat_a = batches_a[0].corridor_statistics[0]
        assert stat_a.failure_class_distribution.get("CLASS_A", 0) == 1
