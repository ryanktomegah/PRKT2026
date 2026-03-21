"""Tests for GAP-05: Royalty batch scheduler."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from lip.common.royalty_batch import RoyaltyBatchScheduler
from lip.common.royalty_settlement import BPIRoyaltySettlement


class TestRoyaltyBatchScheduler:
    def _make_settlement_with_records(self):
        settlement = BPIRoyaltySettlement()
        # Add some records for the previous month
        now = datetime.now(tz=timezone.utc)
        if now.month == 1:
            target_month = 12
            target_year = now.year - 1
        else:
            target_month = now.month - 1
            target_year = now.year

        settlement.record_repayment({
            "uetr": "test-uetr-1",
            "licensee_id": "LIC001",
            "platform_royalty": "150.00",
            "repaid_at": datetime(target_year, target_month, 15, tzinfo=timezone.utc).isoformat(),
            "loan_id": "loan-1",
        })
        settlement.record_repayment({
            "uetr": "test-uetr-2",
            "licensee_id": "LIC001",
            "platform_royalty": "250.00",
            "repaid_at": datetime(target_year, target_month, 20, tzinfo=timezone.utc).isoformat(),
            "loan_id": "loan-2",
        })
        return settlement, target_month, target_year

    def test_generate_now_default_previous_month(self):
        settlement, month, year = self._make_settlement_with_records()
        scheduler = RoyaltyBatchScheduler(settlement)
        reports = scheduler.generate_now()
        assert len(reports) == 1
        assert reports[0].licensee_id == "LIC001"
        assert reports[0].total_royalty_usd == Decimal("400.00")
        assert reports[0].transaction_count == 2

    def test_generate_now_explicit_month(self):
        settlement, month, year = self._make_settlement_with_records()
        scheduler = RoyaltyBatchScheduler(settlement)
        reports = scheduler.generate_now(month=month, year=year)
        assert len(reports) == 1
        assert reports[0].month == month
        assert reports[0].year == year

    def test_generate_now_empty_month(self):
        settlement = BPIRoyaltySettlement()
        scheduler = RoyaltyBatchScheduler(settlement)
        reports = scheduler.generate_now(month=1, year=2020)
        assert reports == []

    def test_start_stop(self):
        settlement = BPIRoyaltySettlement()
        scheduler = RoyaltyBatchScheduler(settlement, check_interval_seconds=0.1)
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    def test_idempotent_start(self):
        settlement = BPIRoyaltySettlement()
        scheduler = RoyaltyBatchScheduler(settlement, check_interval_seconds=0.1)
        scheduler.start()
        scheduler.start()  # second call should be no-op
        assert scheduler.is_running
        scheduler.stop()
