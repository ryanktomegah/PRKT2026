"""
test_gap15_admin_monitoring.py — Tests for GAP-15:
BPI admin / multi-tenant monitoring API.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.api.admin_router import BPIAdminService, LicenseeStats
from lip.c3_repayment_engine.repayment_loop import ActiveLoan, RepaymentLoop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loan(loan_id=None, licensee_id="bank-A", principal="1000000.00") -> ActiveLoan:
    return ActiveLoan(
        loan_id=loan_id or str(uuid.uuid4()),
        uetr=str(uuid.uuid4()),
        individual_payment_id="pid-001",
        principal=Decimal(principal),
        fee_bps=300,
        maturity_date=datetime.now(tz=timezone.utc) + timedelta(days=7),
        rejection_class="CLASS_B",
        corridor="USD_USD",
        funded_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
        licensee_id=licensee_id,
    )


def _make_loop_with_loans(loans: list) -> RepaymentLoop:
    """Build a RepaymentLoop with mocked monitor and pre-registered loans."""
    monitor = MagicMock()
    monitor.get_active_loans.return_value = loans
    loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: None)
    for loan in loans:
        loop.register_loan(loan)
    return loop


# ---------------------------------------------------------------------------
# 1–3: RepaymentLoop.get_active_loans() (prerequisite for GAP-15)
# ---------------------------------------------------------------------------

class TestRepaymentLoopGetActiveLoans:
    def test_get_active_loans_empty_initially(self):
        """RepaymentLoop.get_active_loans() returns empty list when no loans registered."""
        monitor = MagicMock()
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: None)
        assert loop.get_active_loans() == []

    def test_get_active_loans_returns_registered_loans(self):
        """Loans registered via register_loan() appear in get_active_loans()."""
        loop = _make_loop_with_loans([_make_loan("L1"), _make_loan("L2")])
        active = loop.get_active_loans()
        assert len(active) == 2
        ids = {loan.loan_id for loan in active}
        assert ids == {"L1", "L2"}

    def test_get_active_loans_returns_snapshot(self):
        """get_active_loans() returns a list copy — not a live reference."""
        loan = _make_loan("L1")
        loop = _make_loop_with_loans([loan])
        snap1 = loop.get_active_loans()
        snap2 = loop.get_active_loans()
        # Not the same list object
        assert snap1 is not snap2


# ---------------------------------------------------------------------------
# 4–7: BPIAdminService.list_licensees()
# ---------------------------------------------------------------------------

class TestListLicensees:
    def test_list_licensees_empty_platform(self):
        """With no active loans, list_licensees() returns empty list."""
        loop = _make_loop_with_loans([])
        svc = BPIAdminService(loop)
        assert svc.list_licensees() == []

    def test_list_licensees_returns_unique_ids(self):
        """Multiple loans for the same licensee are deduplicated."""
        loans = [
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-B"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        licensees = svc.list_licensees()
        assert sorted(licensees) == ["bank-A", "bank-B"]

    def test_list_licensees_sorted(self):
        """list_licensees() returns IDs in sorted order."""
        loans = [_make_loan(licensee_id="bank-Z"), _make_loan(licensee_id="bank-A")]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        licensees = svc.list_licensees()
        assert licensees == sorted(licensees)

    def test_list_licensees_excludes_empty_ids(self):
        """Loans with empty licensee_id are excluded from the list."""
        loans = [
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id=""),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        licensees = svc.list_licensees()
        assert licensees == ["bank-A"]


# ---------------------------------------------------------------------------
# 8–10: BPIAdminService.get_licensee_stats()
# ---------------------------------------------------------------------------

class TestGetLicenseeStats:
    def test_stats_active_loan_count(self):
        """get_licensee_stats() returns correct active_loan_count."""
        loans = [
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-B"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        stats = svc.get_licensee_stats("bank-A")
        assert stats.active_loan_count == 2

    def test_stats_total_principal(self):
        """get_licensee_stats() sums principal across all active loans."""
        loans = [
            _make_loan(licensee_id="bank-A", principal="1000000.00"),
            _make_loan(licensee_id="bank-A", principal="2000000.00"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        stats = svc.get_licensee_stats("bank-A")
        assert stats.total_principal_usd == Decimal("3000000.00")

    def test_stats_zero_for_unknown_licensee(self):
        """get_licensee_stats() for a non-existent licensee returns zero counts."""
        loop = _make_loop_with_loans([])
        svc = BPIAdminService(loop)
        stats = svc.get_licensee_stats("unknown-bank")
        assert stats.active_loan_count == 0
        assert stats.total_principal_usd == Decimal("0")

    def test_stats_returns_licensee_stats_type(self):
        """Return value is a LicenseeStats instance."""
        loans = [_make_loan(licensee_id="bank-A")]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        stats = svc.get_licensee_stats("bank-A")
        assert isinstance(stats, LicenseeStats)
        assert stats.licensee_id == "bank-A"


# ---------------------------------------------------------------------------
# 11–13: BPIAdminService.get_platform_summary()
# ---------------------------------------------------------------------------

class TestGetPlatformSummary:
    def test_platform_summary_empty(self):
        """Empty platform returns zeroes in all fields."""
        svc = BPIAdminService(_make_loop_with_loans([]))
        summary = svc.get_platform_summary()
        assert summary["total_active_loans"] == 0
        assert summary["total_licensees"] == 0
        assert summary["total_principal_usd"] == "0"

    def test_platform_summary_total_loans(self):
        """total_active_loans counts all active loans across all licensees."""
        loans = [
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-B"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        assert svc.get_platform_summary()["total_active_loans"] == 3

    def test_platform_summary_total_licensees(self):
        """total_licensees counts distinct licensee IDs across the platform."""
        loans = [
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-A"),
            _make_loan(licensee_id="bank-B"),
            _make_loan(licensee_id="bank-C"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        assert svc.get_platform_summary()["total_licensees"] == 3

    def test_platform_summary_total_principal(self):
        """total_principal_usd sums all active loan principals platform-wide."""
        loans = [
            _make_loan(licensee_id="bank-A", principal="1000000.00"),
            _make_loan(licensee_id="bank-B", principal="2000000.00"),
            _make_loan(licensee_id="bank-C", principal="500000.00"),
        ]
        svc = BPIAdminService(_make_loop_with_loans(loans))
        summary = svc.get_platform_summary()
        assert summary["total_principal_usd"] == "3500000.00"
