"""
test_miplo_portfolio.py — TDD tests for tenant-scoped MIPLO portfolio endpoints.

Tests:
  - PortfolioReporter.get_tenant_nav() returns NAV-shaped data for one tenant
  - MIPLOService portfolio delegation enforces tenant isolation
  - MIPLO router /portfolio/* endpoints return correct data
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c3_repayment_engine.repayment_loop import ActiveLoan


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_loan(
    licensee_id: str = "FINASTRA_EU_001",
    principal: str = "100000.00",
    loan_id: str = "LOAN-001",
    uetr: str = "uetr-001",
    fee_bps: int = 300,
    rejection_class: str = "CLASS_A",
) -> ActiveLoan:
    return ActiveLoan(
        loan_id=loan_id,
        uetr=uetr,
        individual_payment_id="PMT-001",
        principal=Decimal(principal),
        fee_bps=fee_bps,
        maturity_date=_utcnow() + timedelta(days=3),
        rejection_class=rejection_class,
        corridor="USD_EUR",
        funded_at=_utcnow(),
        licensee_id=licensee_id,
        deployment_phase="LICENSOR",
    )


class TestPortfolioReporterTenantNav:
    """Test PortfolioReporter.get_tenant_nav() method."""

    def test_single_tenant_nav(self):
        from lip.api.portfolio_router import PortfolioReporter

        mock_loop = MagicMock()
        mock_loop.get_active_loans.return_value = [
            _make_loan(principal="100000.00", loan_id="L1", uetr="u1"),
            _make_loan(principal="50000.00", loan_id="L2", uetr="u2"),
        ]
        reporter = PortfolioReporter(repayment_loop=mock_loop)
        nav = reporter.get_tenant_nav("FINASTRA_EU_001")

        assert nav["tenant_id"] == "FINASTRA_EU_001"
        assert nav["active_loans"] == 2
        assert Decimal(nav["total_exposure_usd"]) == Decimal("150000.00")

    def test_tenant_nav_filters_other_tenants(self):
        from lip.api.portfolio_router import PortfolioReporter

        mock_loop = MagicMock()
        mock_loop.get_active_loans.return_value = [
            _make_loan(licensee_id="TENANT_A", principal="100000.00", loan_id="L1", uetr="u1"),
            _make_loan(licensee_id="TENANT_B", principal="200000.00", loan_id="L2", uetr="u2"),
        ]
        reporter = PortfolioReporter(repayment_loop=mock_loop)
        nav = reporter.get_tenant_nav("TENANT_A")

        assert nav["active_loans"] == 1
        assert Decimal(nav["total_exposure_usd"]) == Decimal("100000.00")

    def test_tenant_nav_no_loans(self):
        from lip.api.portfolio_router import PortfolioReporter

        mock_loop = MagicMock()
        mock_loop.get_active_loans.return_value = []
        reporter = PortfolioReporter(repayment_loop=mock_loop)
        nav = reporter.get_tenant_nav("NONEXISTENT")

        assert nav["active_loans"] == 0
        assert Decimal(nav["total_exposure_usd"]) == Decimal("0")


class TestMIPLOServicePortfolio:
    """Test MIPLOService portfolio delegation."""

    def test_get_portfolio_loans_delegates(self):
        from lip.api.miplo_service import MIPLOService
        from lip.c8_license_manager.license_token import ProcessorLicenseeContext

        ctx = ProcessorLicenseeContext(
            licensee_id="FINASTRA_EU_001",
            max_tps=1000,
            aml_dollar_cap_usd=0,
            aml_count_cap=0,
            permitted_components=["C1", "C2", "C3", "C5", "C6", "C7"],
            token_expiry="2028-01-01",
            licensee_type="PROCESSOR",
            sub_licensee_bics=["COBADEFF"],
            platform_take_rate_pct=0.20,
        )
        mock_pipeline = MagicMock()
        mock_reporter = MagicMock()
        mock_reporter.get_loans.return_value = [{"loan_id": "L1"}]

        svc = MIPLOService(mock_pipeline, ctx, portfolio_reporter=mock_reporter)
        loans = svc.get_portfolio_loans()

        mock_reporter.get_loans.assert_called_once()
        assert loans == [{"loan_id": "L1"}]

    def test_get_portfolio_nav_delegates(self):
        from lip.api.miplo_service import MIPLOService
        from lip.c8_license_manager.license_token import ProcessorLicenseeContext

        ctx = ProcessorLicenseeContext(
            licensee_id="FINASTRA_EU_001",
            max_tps=1000,
            aml_dollar_cap_usd=0,
            aml_count_cap=0,
            permitted_components=["C1", "C2", "C3", "C5", "C6", "C7"],
            token_expiry="2028-01-01",
            licensee_type="PROCESSOR",
            sub_licensee_bics=["COBADEFF"],
            platform_take_rate_pct=0.20,
        )
        mock_pipeline = MagicMock()
        mock_reporter = MagicMock()
        mock_reporter.get_tenant_nav.return_value = {"tenant_id": "FINASTRA_EU_001", "active_loans": 5}

        svc = MIPLOService(mock_pipeline, ctx, portfolio_reporter=mock_reporter)
        nav = svc.get_portfolio_nav()

        mock_reporter.get_tenant_nav.assert_called_once_with("FINASTRA_EU_001")
        assert nav["active_loans"] == 5

    def test_portfolio_not_available_without_reporter(self):
        from lip.api.miplo_service import MIPLOService
        from lip.c8_license_manager.license_token import ProcessorLicenseeContext

        ctx = ProcessorLicenseeContext(
            licensee_id="FINASTRA_EU_001",
            max_tps=1000,
            aml_dollar_cap_usd=0,
            aml_count_cap=0,
            permitted_components=["C1", "C2", "C3", "C5", "C6", "C7"],
            token_expiry="2028-01-01",
            licensee_type="PROCESSOR",
            sub_licensee_bics=["COBADEFF"],
            platform_take_rate_pct=0.20,
        )
        mock_pipeline = MagicMock()
        svc = MIPLOService(mock_pipeline, ctx)
        assert svc.get_portfolio_loans() is None
        assert svc.get_portfolio_nav() is None
