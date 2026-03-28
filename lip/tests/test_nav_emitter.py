"""
test_nav_emitter.py — TDD tests for NAVEventEmitter.

Tests per-tenant NAV snapshot computation, settlement history tracking,
and thread-safe deque access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c3_repayment_engine.nav_emitter import NAVEventEmitter
from lip.c3_repayment_engine.repayment_loop import ActiveLoan
from lip.common.schemas import NAVEvent


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_loan(
    licensee_id: str = "FINASTRA_EU_001",
    principal: str = "100000.00",
    loan_id: str = "LOAN-001",
    uetr: str = "uetr-001",
) -> ActiveLoan:
    return ActiveLoan(
        loan_id=loan_id,
        uetr=uetr,
        individual_payment_id="PMT-001",
        principal=Decimal(principal),
        fee_bps=300,
        maturity_date=_utcnow() + timedelta(days=3),
        rejection_class="CLASS_A",
        corridor="USD_EUR",
        funded_at=_utcnow(),
        licensee_id=licensee_id,
        deployment_phase="LICENSOR",
    )


class TestNAVSnapshotComputation:
    """Test the synchronous emit_snapshot() logic (no background thread)."""

    def test_single_tenant_nav_event(self):
        loans = [_make_loan(principal="100000.00"), _make_loan(principal="50000.00", loan_id="LOAN-002", uetr="uetr-002")]
        emitter = NAVEventEmitter(
            get_active_loans=lambda: loans,
            nav_callback=MagicMock(),
        )
        events = emitter.emit_snapshot()
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, NAVEvent)
        assert ev.tenant_id == "FINASTRA_EU_001"
        assert ev.active_loans == 2
        assert ev.total_exposure_usd == Decimal("150000.00")

    def test_multi_tenant_produces_separate_events(self):
        loans = [
            _make_loan(licensee_id="TENANT_A", principal="100000.00", loan_id="L1", uetr="u1"),
            _make_loan(licensee_id="TENANT_B", principal="200000.00", loan_id="L2", uetr="u2"),
            _make_loan(licensee_id="TENANT_A", principal="50000.00", loan_id="L3", uetr="u3"),
        ]
        emitter = NAVEventEmitter(get_active_loans=lambda: loans, nav_callback=MagicMock())
        events = emitter.emit_snapshot()
        assert len(events) == 2
        by_tenant = {e.tenant_id: e for e in events}
        assert by_tenant["TENANT_A"].active_loans == 2
        assert by_tenant["TENANT_A"].total_exposure_usd == Decimal("150000.00")
        assert by_tenant["TENANT_B"].active_loans == 1
        assert by_tenant["TENANT_B"].total_exposure_usd == Decimal("200000.00")

    def test_empty_licensee_skipped(self):
        """Bank-mode loans (empty licensee_id) are not included in NAV events."""
        loans = [_make_loan(licensee_id="")]
        emitter = NAVEventEmitter(get_active_loans=lambda: loans, nav_callback=MagicMock())
        events = emitter.emit_snapshot()
        assert len(events) == 0

    def test_no_loans_no_events(self):
        emitter = NAVEventEmitter(get_active_loans=lambda: [], nav_callback=MagicMock())
        events = emitter.emit_snapshot()
        assert len(events) == 0

    def test_callback_invoked_per_tenant(self):
        loans = [
            _make_loan(licensee_id="T1", loan_id="L1", uetr="u1"),
            _make_loan(licensee_id="T2", loan_id="L2", uetr="u2"),
        ]
        cb = MagicMock()
        emitter = NAVEventEmitter(get_active_loans=lambda: loans, nav_callback=cb)
        emitter.emit_snapshot()
        assert cb.call_count == 2


class TestSettlementHistory:
    """Test settlement tracking for settled_last_60min and trailing_loss_rate_30d."""

    def test_settled_last_60min(self):
        emitter = NAVEventEmitter(get_active_loans=lambda: [_make_loan()], nav_callback=MagicMock())
        now = _utcnow()
        emitter.record_settlement(
            tenant_id="FINASTRA_EU_001",
            amount=Decimal("50000.00"),
            timestamp=now - timedelta(minutes=30),
        )
        emitter.record_settlement(
            tenant_id="FINASTRA_EU_001",
            amount=Decimal("25000.00"),
            timestamp=now - timedelta(minutes=10),
        )
        events = emitter.emit_snapshot()
        assert len(events) == 1
        assert events[0].settled_last_60min == 2
        assert events[0].settled_amount_last_60min_usd == Decimal("75000.00")

    def test_old_settlements_excluded_from_60min(self):
        emitter = NAVEventEmitter(get_active_loans=lambda: [_make_loan()], nav_callback=MagicMock())
        now = _utcnow()
        emitter.record_settlement(
            tenant_id="FINASTRA_EU_001",
            amount=Decimal("50000.00"),
            timestamp=now - timedelta(hours=2),  # older than 60 min
        )
        events = emitter.emit_snapshot()
        assert events[0].settled_last_60min == 0
        assert events[0].settled_amount_last_60min_usd == Decimal("0")

    def test_trailing_loss_rate_defaults_to_zero(self):
        emitter = NAVEventEmitter(get_active_loans=lambda: [_make_loan()], nav_callback=MagicMock())
        events = emitter.emit_snapshot()
        assert events[0].trailing_loss_rate_30d == Decimal("0")

    def test_cross_tenant_settlement_isolation(self):
        """Settlements for tenant A don't appear in tenant B's NAV."""
        loans = [
            _make_loan(licensee_id="T_A", loan_id="L1", uetr="u1"),
            _make_loan(licensee_id="T_B", loan_id="L2", uetr="u2"),
        ]
        emitter = NAVEventEmitter(get_active_loans=lambda: loans, nav_callback=MagicMock())
        emitter.record_settlement(tenant_id="T_A", amount=Decimal("10000.00"), timestamp=_utcnow())
        events = emitter.emit_snapshot()
        by_tenant = {e.tenant_id: e for e in events}
        assert by_tenant["T_A"].settled_last_60min == 1
        assert by_tenant["T_B"].settled_last_60min == 0


class TestMetricsUpdate:
    """Test that emit_snapshot updates Prometheus gauge metrics."""

    def test_metrics_updated_per_tenant(self):
        loans = [_make_loan(principal="100000.00")]
        metrics = MagicMock()
        emitter = NAVEventEmitter(
            get_active_loans=lambda: loans,
            nav_callback=MagicMock(),
            metrics_collector=metrics,
        )
        emitter.emit_snapshot()
        # Should call add_gauge for active loans and exposure
        assert metrics.add_gauge.call_count >= 2
