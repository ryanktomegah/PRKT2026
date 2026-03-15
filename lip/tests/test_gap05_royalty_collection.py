"""
test_gap05_royalty_collection.py — Integration tests for GAP-05: BPI royalty collection.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lip.common.royalty_settlement import BPIRoyaltySettlement


@pytest.fixture
def settlement():
    return BPIRoyaltySettlement()

def _make_repayment(uetr: str, royalty: str, licensee: str = "BANK_A", month: int = 3):
    return {
        "loan_id": f"loan-{uetr}",
        "uetr": uetr,
        "individual_payment_id": f"pid-{uetr}",
        "principal": "10000",
        "fee": "100",
        "platform_royalty": royalty,
        "net_fee_to_entities": "85",
        "licensee_id": licensee,
        "repaid_at": datetime(2026, month, 15, tzinfo=timezone.utc).isoformat()
    }

class TestGap05RoyaltyCollection:
    def test_record_single_royalty(self, settlement):
        repayment = _make_repayment("uetr-1", "15.00")
        settlement.record_repayment(repayment)

        reports = settlement.generate_monthly_settlement(month=3, year=2026)
        assert len(reports) == 1
        report = reports[0]
        assert report.licensee_id == "BANK_A"
        assert report.total_royalty_usd == Decimal("15.00")
        assert report.transaction_count == 1
        assert report.records[0].uetr == "uetr-1"

    def test_aggregate_multiple_royalties(self, settlement):
        settlement.record_repayment(_make_repayment("uetr-1", "10.00"))
        settlement.record_repayment(_make_repayment("uetr-2", "20.00"))
        settlement.record_repayment(_make_repayment("uetr-3", "5.00", licensee="BANK_B"))

        # Test BANK_A aggregation
        reports_a = settlement.generate_monthly_settlement(month=3, year=2026, licensee_id="BANK_A")
        assert len(reports_a) == 1
        assert reports_a[0].total_royalty_usd == Decimal("30.00")
        assert reports_a[0].transaction_count == 2

        # Test all aggregation
        reports_all = settlement.generate_monthly_settlement(month=3, year=2026)
        assert len(reports_all) == 2
        total_all = sum((r.total_royalty_usd for r in reports_all), Decimal("0"))
        assert total_all == Decimal("35.00")

    def test_filter_by_month_and_year(self, settlement):
        settlement.record_repayment(_make_repayment("uetr-march", "10.00", month=3))
        settlement.record_repayment(_make_repayment("uetr-april", "20.00", month=4))

        march = settlement.generate_monthly_settlement(month=3, year=2026)
        assert len(march) == 1
        assert march[0].total_royalty_usd == Decimal("10.00")

        april = settlement.generate_monthly_settlement(month=4, year=2026)
        assert len(april) == 1
        assert april[0].total_royalty_usd == Decimal("20.00")

    def test_invalid_repayment_swallowed_and_logged(self, settlement, caplog):
        # Missing fields
        settlement.record_repayment({"uetr": "bad"})
        assert "Failed to record royalty" in caplog.text

        reports = settlement.generate_monthly_settlement(month=3, year=2026)
        assert len(reports) == 0
