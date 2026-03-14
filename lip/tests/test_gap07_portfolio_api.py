"""
test_gap07_portfolio_api.py — Tests for GAP-07:
MLO portfolio reporting (loans, exposure, yield).
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.api.portfolio_router import PortfolioReporter, _tier_from_fee_bps
from lip.c3_repayment_engine.repayment_loop import ActiveLoan
from lip.common.royalty_settlement import BPIRoyaltySettlement


def _make_loan(
    loan_id: str,
    uetr: str,
    principal: str = "5000000",
    fee_bps: int = 300,
    corridor: str = "USD_EUR",
    rejection_class: str = "CLASS_B",
    licensee_id: str = "BANK_A",
    days_to_maturity: int = 5,
) -> ActiveLoan:
    now = datetime.now(tz=timezone.utc)
    from datetime import timedelta
    return ActiveLoan(
        loan_id=loan_id,
        uetr=uetr,
        individual_payment_id=f"pid-{loan_id}",
        principal=Decimal(principal),
        fee_bps=fee_bps,
        maturity_date=now + timedelta(days=days_to_maturity),
        rejection_class=rejection_class,
        corridor=corridor,
        funded_at=now,
        licensee_id=licensee_id,
    )


@pytest.fixture
def repayment_loop():
    """Mock RepaymentLoop with two active loans."""
    loop = MagicMock()
    loans = [
        _make_loan("loan-1", "uetr-1", principal="5000000", fee_bps=300, corridor="USD_EUR"),
        _make_loan("loan-2", "uetr-2", principal="3000000", fee_bps=600, corridor="GBP_USD",
                   rejection_class="CLASS_A", licensee_id="BANK_B"),
    ]
    loop.get_active_loans.return_value = loans
    return loop


@pytest.fixture
def reporter(repayment_loop):
    return PortfolioReporter(repayment_loop)


class TestTierDerivation:
    def test_300_bps_is_tier1(self):
        assert _tier_from_fee_bps(300) == 1

    def test_539_bps_is_tier1(self):
        assert _tier_from_fee_bps(539) == 1

    def test_540_bps_is_tier2(self):
        assert _tier_from_fee_bps(540) == 2

    def test_900_bps_is_tier3(self):
        assert _tier_from_fee_bps(900) == 3


class TestPortfolioLoans:
    def test_returns_all_active_loans(self, reporter):
        loans = reporter.get_loans()
        assert len(loans) == 2

    def test_loan_fields_present(self, reporter):
        loan = reporter.get_loans()[0]
        assert "loan_id" in loan
        assert "uetr" in loan
        assert "principal_usd" in loan
        assert "fee_bps" in loan
        assert "tier" in loan
        assert "maturity_date" in loan
        assert "corridor" in loan
        assert "days_to_maturity" in loan

    def test_tier_derived_correctly(self, reporter):
        loans = reporter.get_loans()
        tier1_loan = next(loan for loan in loans if loan["fee_bps"] == 300)
        tier2_loan = next(loan for loan in loans if loan["fee_bps"] == 600)
        assert tier1_loan["tier"] == 1
        assert tier2_loan["tier"] == 2

    def test_licensee_filter(self, repayment_loop):
        reporter_filtered = PortfolioReporter(repayment_loop, licensee_id="BANK_A")
        loans = reporter_filtered.get_loans()
        assert len(loans) == 1
        assert loans[0]["licensee_id"] == "BANK_A"


class TestPortfolioExposure:
    def test_total_exposure(self, reporter):
        exposure = reporter.get_exposure()
        assert exposure["total_exposure_usd"] == "8000000"
        assert exposure["loan_count"] == 2

    def test_by_corridor(self, reporter):
        exposure = reporter.get_exposure()
        assert "USD_EUR" in exposure["by_corridor"]
        assert "GBP_USD" in exposure["by_corridor"]
        assert exposure["by_corridor"]["USD_EUR"]["principal_usd"] == "5000000"

    def test_by_tier(self, reporter):
        exposure = reporter.get_exposure()
        assert 1 in exposure["by_tier"]
        assert 2 in exposure["by_tier"]

    def test_by_maturity_class(self, reporter):
        exposure = reporter.get_exposure()
        assert "CLASS_B" in exposure["by_maturity_class"]
        assert "CLASS_A" in exposure["by_maturity_class"]


class TestPortfolioYield:
    def test_yield_fields_present(self, reporter):
        y = reporter.get_yield()
        assert "book_principal_usd" in y
        assert "accrued_fee_usd" in y
        assert "realised_royalty_usd" in y
        assert "estimated_annualised_yield_bps" in y

    def test_book_principal_matches_exposure(self, reporter):
        y = reporter.get_yield()
        assert y["book_principal_usd"] == "8000000"

    def test_realised_royalty_from_settlement(self, repayment_loop):
        settlement = BPIRoyaltySettlement()
        # Record two royalties for current month
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        settlement.record_repayment({
            "uetr": "uetr-rep-1",
            "loan_id": "loan-rep-1",
            "individual_payment_id": "pid-rep-1",
            "principal": "5000000",
            "fee": "500",
            "platform_royalty": "75.00",
            "net_fee_to_entities": "425",
            "licensee_id": "BANK_A",
            "repaid_at": now.isoformat(),
        })
        reporter_with_settlement = PortfolioReporter(repayment_loop, royalty_settlement=settlement)
        y = reporter_with_settlement.get_yield()
        assert Decimal(y["realised_royalty_usd"]) == Decimal("75.00")

    def test_estimated_yield_bps_is_weighted_average(self, reporter):
        """Weighted average fee bps: (5M×300 + 3M×600) / 8M = (1.5M + 1.8M) / 8M = 3.3M/8M ≈ 412."""
        y = reporter.get_yield()
        assert y["estimated_annualised_yield_bps"] == 412
