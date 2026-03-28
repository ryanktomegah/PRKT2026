"""
test_settlement_bridge.py — TDD tests for SettlementCallbackBridge.

Tests bridge routing: bank-mode (royalty only) vs processor-mode (royalty + revenue + NAV).
QUANT domain: verifies Decimal passthrough to RevenueMetering.
"""
from __future__ import annotations

from datetime import datetime, timezone  # noqa: F401 — timezone used in implementation phase
from decimal import Decimal
from unittest.mock import MagicMock, call  # noqa: F401 — call used in implementation phase

import pytest  # noqa: F401 — pytest fixtures used in implementation phase

from lip.c3_repayment_engine.settlement_bridge import SettlementCallbackBridge


def _make_repayment_record(
    licensee_id: str = "FINASTRA_EU_001",
    uetr: str = "test-uetr-001",
    fee: str = "1500.00",
    settlement_amount: str = "100000.00",
) -> dict:
    """Minimal repayment_record matching trigger_repayment() output."""
    return {
        "loan_id": "LOAN-001",
        "uetr": uetr,
        "individual_payment_id": "PMT-001",
        "principal": "100000.00",
        "fee": fee,
        "bpi_fee_share_usd": "450.00",
        "platform_royalty": "450.00",
        "net_fee_to_entities": "1050.00",
        "bank_capital_return_usd": "0.00",
        "bank_distribution_premium_usd": "1050.00",
        "income_type": "ROYALTY",
        "deployment_phase": "LICENSOR",
        "licensee_id": licensee_id,
        "fee_bps": 300,
        "settlement_amount": settlement_amount,
        "corridor": "USD_EUR",
        "rejection_class": "CLASS_A",
        "trigger": "SETTLEMENT_CONFIRMED",
        "funded_at": "2027-01-01T00:00:00+00:00",
        "maturity_date": "2027-01-04T00:00:00+00:00",
        "repaid_at": "2027-01-02T12:00:00+00:00",
        "is_partial": False,
        "shortfall_amount": "0",
        "shortfall_pct": 0.0,
    }


class TestBridgeBankMode:
    """Bank mode: royalty_settlement only, no revenue metering or NAV."""

    def test_bank_mode_calls_royalty(self):
        royalty = MagicMock()
        bridge = SettlementCallbackBridge(royalty_settlement=royalty)
        record = _make_repayment_record()
        bridge(record)
        royalty.record_repayment.assert_called_once_with(record)

    def test_bank_mode_skips_revenue_metering(self):
        royalty = MagicMock()
        bridge = SettlementCallbackBridge(royalty_settlement=royalty)
        bridge(_make_repayment_record())
        # No revenue_metering set — should not raise

    def test_bank_mode_skips_nav_emitter(self):
        royalty = MagicMock()
        bridge = SettlementCallbackBridge(royalty_settlement=royalty)
        bridge(_make_repayment_record())
        # No nav_emitter set — should not raise


class TestBridgeProcessorMode:
    """Processor mode: royalty + revenue metering + NAV emitter."""

    def test_processor_mode_calls_all_three(self):
        royalty = MagicMock()
        revenue = MagicMock()
        nav = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            revenue_metering=revenue,
            nav_emitter=nav,
            platform_take_rate_pct=Decimal("0.20"),
        )
        record = _make_repayment_record()
        bridge(record)

        royalty.record_repayment.assert_called_once_with(record)
        revenue.record_transaction.assert_called_once()
        nav.record_settlement.assert_called_once()

    def test_revenue_metering_receives_decimal_args(self):
        royalty = MagicMock()
        revenue = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            revenue_metering=revenue,
            platform_take_rate_pct=Decimal("0.20"),
        )
        bridge(_make_repayment_record(fee="1500.00"))

        args = revenue.record_transaction.call_args
        assert args.kwargs["tenant_id"] == "FINASTRA_EU_001"
        assert args.kwargs["uetr"] == "test-uetr-001"
        assert args.kwargs["gross_fee_usd"] == Decimal("1500.00")
        assert args.kwargs["platform_take_rate_pct"] == Decimal("0.20")

    def test_nav_emitter_receives_settlement_data(self):
        royalty = MagicMock()
        nav = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            nav_emitter=nav,
        )
        bridge(_make_repayment_record(settlement_amount="100000.00"))

        args = nav.record_settlement.call_args
        assert args.kwargs["tenant_id"] == "FINASTRA_EU_001"
        assert args.kwargs["amount"] == Decimal("100000.00")
        assert isinstance(args.kwargs["timestamp"], datetime)

    def test_empty_licensee_skips_revenue_and_nav(self):
        """Bank-originated repayments (empty licensee_id) skip processor paths."""
        royalty = MagicMock()
        revenue = MagicMock()
        nav = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            revenue_metering=revenue,
            nav_emitter=nav,
            platform_take_rate_pct=Decimal("0.20"),
        )
        bridge(_make_repayment_record(licensee_id=""))

        royalty.record_repayment.assert_called_once()
        revenue.record_transaction.assert_not_called()
        nav.record_settlement.assert_not_called()

    def test_royalty_exception_does_not_block_revenue(self):
        """If royalty recording fails, revenue metering still fires."""
        royalty = MagicMock()
        royalty.record_repayment.side_effect = Exception("Redis down")
        revenue = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            revenue_metering=revenue,
            platform_take_rate_pct=Decimal("0.20"),
        )
        # Should not raise
        bridge(_make_repayment_record())
        revenue.record_transaction.assert_called_once()

    def test_revenue_exception_does_not_block_nav(self):
        """If revenue metering fails, NAV emitter still fires."""
        royalty = MagicMock()
        revenue = MagicMock()
        revenue.record_transaction.side_effect = Exception("Decimal overflow")
        nav = MagicMock()
        bridge = SettlementCallbackBridge(
            royalty_settlement=royalty,
            revenue_metering=revenue,
            nav_emitter=nav,
            platform_take_rate_pct=Decimal("0.20"),
        )
        bridge(_make_repayment_record())
        nav.record_settlement.assert_called_once()

    def test_upgrade_to_processor_mode(self):
        """Bank-mode bridge can be upgraded to processor mode via public method."""
        royalty = MagicMock()
        bridge = SettlementCallbackBridge(royalty_settlement=royalty)

        revenue = MagicMock()
        nav = MagicMock()
        bridge.upgrade_to_processor_mode(
            revenue_metering=revenue,
            nav_emitter=nav,
            platform_take_rate_pct=Decimal("0.20"),
        )

        bridge(_make_repayment_record())
        royalty.record_repayment.assert_called_once()
        revenue.record_transaction.assert_called_once()
        nav.record_settlement.assert_called_once()

    def test_callable_protocol(self):
        """Bridge must be callable (used as RepaymentLoop callback)."""
        royalty = MagicMock()
        bridge = SettlementCallbackBridge(royalty_settlement=royalty)
        assert callable(bridge)
