# Sprint 2d — Multi-Tenant Settlement Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make C3 settlement tracking tenant-aware with per-tenant NAV emission, settlement→revenue metering bridging, tenant-scoped Redis keys, and MIPLO portfolio endpoints.

**Architecture:** Option C — query-time filtering + selective Redis scoping. C3's internal data structures stay single-namespace (UETR is globally unique by SWIFT UUID v4 spec). New code is strictly additive: SettlementCallbackBridge replaces the no-op repayment callback, NAVEventEmitter runs a 60-minute background scheduler, and MIPLO portfolio endpoints enforce tenant isolation via the existing MIPLOService gateway. The fee waterfall in `trigger_repayment()` is QUANT-protected and untouched except for passing `tenant_id` to `_claim_repayment()`.

**Tech Stack:** Python 3.14, dataclasses, threading, Decimal, Pydantic v2, FastAPI, pytest

**Spec:** `docs/superpowers/specs/2026-03-28-sprint-2d-multi-tenant-settlement-design.md`

---

## Context

This is Sprint 2d of a 23-session build program. It follows:
- Sprint 2a: C8 processor tokens + revenue metering (RevenueMetering class exists)
- Sprint 2b: C6 cross-tenant velocity isolation (tenant-scoped Redis keys pattern)
- Sprint 2c: C7 MIPLO API gateway (MIPLOService, miplo_router, pipeline TenantContext threading)

**What this enables:** After this sprint, processor deployments will have per-tenant NAV snapshots for dashboards, settlement events flowing to revenue metering for billing, and tenant-scoped portfolio queries via the MIPLO API.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/tests/test_settlement_bridge.py` | TDD: bridge routing, bank vs processor mode |
| Create | `lip/tests/test_nav_emitter.py` | TDD: NAV emission, settlement history, thread safety |
| Create | `lip/tests/test_miplo_portfolio.py` | TDD: tenant-scoped portfolio endpoints |
| Create | `lip/c3_repayment_engine/settlement_bridge.py` | Settlement callback → royalty + revenue + NAV |
| Create | `lip/c3_repayment_engine/nav_emitter.py` | Per-tenant NAVEvent emission scheduler |
| Modify | `lip/c3_repayment_engine/repayment_loop.py:252-291` | Add tenant_id to `_claim_repayment()` Redis key |
| Modify | `lip/c3_repayment_engine/repayment_loop.py:346` | Pass `tenant_id=loan.licensee_id` at call site |
| Modify | `lip/c3_repayment_engine/__init__.py` | Export NAVEventEmitter, SettlementCallbackBridge |
| Modify | `lip/api/portfolio_router.py:43-103` | Add `get_tenant_nav()` to PortfolioReporter |
| Modify | `lip/api/miplo_service.py:38-130` | Add `portfolio_reporter` param + delegation methods |
| Modify | `lip/api/miplo_router.py:63-129` | Add `/miplo/portfolio/*` endpoints |
| Modify | `lip/api/app.py:46-178` | Wire bridge, NAV emitter, revenue metering, MIPLO portfolio |

---

## Task 1: TDD Tests — SettlementCallbackBridge

**Files:**
- Create: `lip/tests/test_settlement_bridge.py`

- [ ] **Step 1: Write the test file**

```python
"""
test_settlement_bridge.py — TDD tests for SettlementCallbackBridge.

Tests bridge routing: bank-mode (royalty only) vs processor-mode (royalty + revenue + NAV).
QUANT domain: verifies Decimal passthrough to RevenueMetering.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_settlement_bridge.py -v 2>&1 | head -15`
Expected: ImportError for `SettlementCallbackBridge`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_settlement_bridge.py
git commit -m "test(c3): add TDD tests for SettlementCallbackBridge — bank vs processor routing"
```

---

## Task 2: Implement SettlementCallbackBridge

**Files:**
- Create: `lip/c3_repayment_engine/settlement_bridge.py`

- [ ] **Step 1: Write the implementation**

```python
"""
settlement_bridge.py — Routes C3 repayment events to downstream consumers.

Replaces the no-op lambda in app.py with a bridge that fans out to:
  1. BPIRoyaltySettlement.record_repayment() — always (bank + processor mode)
  2. RevenueMetering.record_transaction() — processor mode only
  3. NAVEventEmitter.record_settlement() — processor mode only

Implements __call__ so it can be passed directly as RepaymentLoop's
repayment_callback parameter (Callable[[dict], None]).
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class SettlementCallbackBridge:
    """Fan-out bridge for C3 repayment events.

    Bank mode: only ``royalty_settlement`` is required.
    Processor mode: add ``revenue_metering``, ``nav_emitter``, and
    ``platform_take_rate_pct`` for tenant-scoped revenue tracking.
    """

    def __init__(
        self,
        royalty_settlement,
        revenue_metering=None,
        nav_emitter=None,
        platform_take_rate_pct: Optional[Decimal] = None,
    ) -> None:
        self._royalty = royalty_settlement
        self._revenue = revenue_metering
        self._nav = nav_emitter
        self._take_rate = platform_take_rate_pct

    def upgrade_to_processor_mode(
        self,
        revenue_metering,
        nav_emitter,
        platform_take_rate_pct: Decimal,
    ) -> None:
        """Upgrade a bank-mode bridge to processor mode.

        Called by app.py when processor_context is available. This avoids
        reconstructing RepaymentLoop (which takes the bridge as a callback)
        and prevents private attribute mutation from outside the class.
        """
        self._revenue = revenue_metering
        self._nav = nav_emitter
        self._take_rate = platform_take_rate_pct

    def __call__(self, repayment_record: dict) -> None:
        """Route a repayment event to all configured downstream consumers.

        Each consumer is called independently — a failure in one does not
        block the others.  Exceptions are logged but not re-raised.
        """
        # 1. BPI royalty recording (always — bank + processor mode)
        try:
            self._royalty.record_repayment(repayment_record)
        except Exception as exc:
            logger.error(
                "Royalty recording failed for uetr=%s: %s",
                repayment_record.get("uetr"),
                exc,
            )

        tenant_id = repayment_record.get("licensee_id", "")
        if not tenant_id:
            return  # Bank-originated — no processor paths

        # 2. Revenue metering (processor mode)
        if self._revenue is not None and self._take_rate is not None:
            try:
                self._revenue.record_transaction(
                    tenant_id=tenant_id,
                    uetr=repayment_record["uetr"],
                    gross_fee_usd=Decimal(repayment_record["fee"]),
                    platform_take_rate_pct=self._take_rate,
                )
            except Exception as exc:
                logger.error(
                    "Revenue metering failed for uetr=%s tenant=%s: %s",
                    repayment_record.get("uetr"),
                    tenant_id,
                    exc,
                )

        # 3. NAV settlement history (processor mode)
        if self._nav is not None:
            try:
                self._nav.record_settlement(
                    tenant_id=tenant_id,
                    amount=Decimal(repayment_record["settlement_amount"]),
                    timestamp=datetime.fromisoformat(repayment_record["repaid_at"]),
                )
            except Exception as exc:
                logger.error(
                    "NAV settlement recording failed for uetr=%s tenant=%s: %s",
                    repayment_record.get("uetr"),
                    tenant_id,
                    exc,
                )
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_settlement_bridge.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c3_repayment_engine/settlement_bridge.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/c3_repayment_engine/settlement_bridge.py
git commit -m "feat(c3): add SettlementCallbackBridge — fan-out to royalty, revenue metering, NAV"
```

---

## Task 3: TDD Tests — NAVEventEmitter

**Files:**
- Create: `lip/tests/test_nav_emitter.py`

- [ ] **Step 1: Write the test file**

```python
"""
test_nav_emitter.py — TDD tests for NAVEventEmitter.

Tests per-tenant NAV snapshot computation, settlement history tracking,
and thread-safe deque access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_nav_emitter.py -v 2>&1 | head -15`
Expected: ImportError for `NAVEventEmitter`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_nav_emitter.py
git commit -m "test(c3): add TDD tests for NAVEventEmitter — per-tenant snapshot, settlement history"
```

---

## Task 4: Implement NAVEventEmitter

**Files:**
- Create: `lip/c3_repayment_engine/nav_emitter.py`

- [ ] **Step 1: Write the implementation**

```python
"""
nav_emitter.py — Per-tenant NAV snapshot emitter.
P3 Platform Licensing, C3 extension (Sprint 2d).

Emits NAVEvent (schemas.py) per active tenant every 60 minutes.
Settlement history tracked in a thread-safe rolling deque for
settled_last_60min computation.

trailing_loss_rate_30d defaults to Decimal("0") — real loss-rate
computation requires default/loss event tracking (Sprint 5).
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Deque, Dict, List, Optional, Tuple

from lip.common.schemas import NAVEvent
from lip.infrastructure.monitoring.metrics import (
    METRIC_TENANT_ACTIVE_LOANS,
    METRIC_TENANT_EXPOSURE_USD,
)

logger = logging.getLogger(__name__)

_SIXTY_MINUTES = timedelta(minutes=60)
_THIRTY_DAYS = timedelta(days=30)


@dataclass
class _SettlementRecord:
    """Internal record for settlement history tracking."""
    tenant_id: str
    amount: Decimal
    timestamp: datetime


class NAVEventEmitter:
    """Per-tenant NAV snapshot emitter with settlement history.

    Args:
        get_active_loans: Callable returning List[ActiveLoan] — typically
            ``repayment_loop.get_active_loans`` (bound method).
        nav_callback: Called with each NAVEvent (one per tenant per cycle).
        interval_seconds: Background emission interval (default 3600 = 60 min).
        metrics_collector: Optional PrometheusMetricsCollector for gauge updates.
    """

    def __init__(
        self,
        get_active_loans: Callable,
        nav_callback: Callable[[NAVEvent], None],
        interval_seconds: int = 3600,
        metrics_collector=None,
    ) -> None:
        self._get_active_loans = get_active_loans
        self._nav_callback = nav_callback
        self._interval = interval_seconds
        self._metrics = metrics_collector

        # Settlement history: tenant_id → deque of (timestamp, amount)
        self._history: Dict[str, Deque[_SettlementRecord]] = defaultdict(
            lambda: deque(maxlen=100_000)
        )
        self._history_lock = threading.Lock()

        # Background thread control
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Settlement history ────────────────────────────────────────────────────

    def record_settlement(
        self,
        tenant_id: str,
        amount: Decimal,
        timestamp: datetime,
    ) -> None:
        """Record a settlement for NAV history tracking.

        Called by SettlementCallbackBridge on the RepaymentLoop thread.
        Thread-safe via _history_lock.
        """
        record = _SettlementRecord(tenant_id=tenant_id, amount=amount, timestamp=timestamp)
        with self._history_lock:
            self._history[tenant_id].append(record)

    def _get_settled_last_60min(self, tenant_id: str, now: datetime) -> Tuple[int, Decimal]:
        """Return (count, total_amount) of settlements in the last 60 minutes."""
        cutoff = now - _SIXTY_MINUTES
        count = 0
        total = Decimal("0")
        with self._history_lock:
            for rec in self._history.get(tenant_id, []):
                if rec.timestamp >= cutoff:
                    count += 1
                    total += rec.amount
        return count, total

    def _purge_old_history(self, now: datetime) -> None:
        """Remove settlement records older than 30 days."""
        cutoff = now - _THIRTY_DAYS
        with self._history_lock:
            for tenant_id in list(self._history.keys()):
                dq = self._history[tenant_id]
                while dq and dq[0].timestamp < cutoff:
                    dq.popleft()
                if not dq:
                    del self._history[tenant_id]

    # ── NAV snapshot ──────────────────────────────────────────────────────────

    def emit_snapshot(self) -> List[NAVEvent]:
        """Compute and emit per-tenant NAV events (synchronous).

        Groups active loans by licensee_id, computes NAV fields,
        invokes nav_callback per tenant, and updates metrics.

        Returns list of emitted NAVEvent objects (useful for testing).
        """
        now = datetime.now(tz=timezone.utc)
        loans = self._get_active_loans()

        # Group by tenant
        by_tenant: Dict[str, list] = defaultdict(list)
        for loan in loans:
            if loan.licensee_id:
                by_tenant[loan.licensee_id].append(loan)

        events: List[NAVEvent] = []
        for tenant_id, tenant_loans in sorted(by_tenant.items()):
            active_count = len(tenant_loans)
            total_exposure = sum(
                (loan.principal for loan in tenant_loans), Decimal("0")
            )
            settled_count, settled_amount = self._get_settled_last_60min(tenant_id, now)

            nav = NAVEvent(
                tenant_id=tenant_id,
                active_loans=active_count,
                total_exposure_usd=total_exposure,
                settled_last_60min=settled_count,
                settled_amount_last_60min_usd=settled_amount,
                trailing_loss_rate_30d=Decimal("0"),  # Sprint 5: real loss tracking
                timestamp=now,
            )
            events.append(nav)

            try:
                self._nav_callback(nav)
            except Exception as exc:
                logger.error(
                    "NAV callback failed for tenant=%s: %s", tenant_id, exc
                )

            # Update metrics
            if self._metrics is not None:
                self._metrics.add_gauge(
                    METRIC_TENANT_ACTIVE_LOANS,
                    float(active_count),
                    {"tenant_id": tenant_id},
                )
                self._metrics.add_gauge(
                    METRIC_TENANT_EXPOSURE_USD,
                    float(total_exposure),
                    {"tenant_id": tenant_id},
                )

        # Purge stale history periodically
        self._purge_old_history(now)

        return events

    # ── Background thread ─────────────────────────────────────────────────────

    def start(self, interval_seconds: Optional[int] = None) -> None:
        """Start the background NAV emission thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("NAVEventEmitter already running; ignoring duplicate start.")
            return

        interval = interval_seconds or self._interval
        self._stop_event.clear()

        def _loop() -> None:
            logger.info(
                "NAVEventEmitter thread started (interval=%ds).", interval,
            )
            while not self._stop_event.wait(timeout=interval):
                try:
                    events = self.emit_snapshot()
                    if events:
                        logger.info(
                            "NAV emission: %d tenant(s) snapshotted.", len(events)
                        )
                except Exception as exc:
                    logger.exception("Error in NAV emission cycle: %s", exc)
            logger.info("NAVEventEmitter thread stopped.")

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="NAVEventEmitter"
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the NAV emission thread to stop and wait for exit."""
        if self._thread is None:
            return
        logger.info("Stopping NAVEventEmitter thread...")
        self._stop_event.set()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            logger.warning("NAVEventEmitter thread did not stop within timeout.")
        self._thread = None
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_nav_emitter.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c3_repayment_engine/nav_emitter.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/c3_repayment_engine/nav_emitter.py
git commit -m "feat(c3): add NAVEventEmitter — per-tenant NAV snapshots with settlement history"
```

---

## Task 5: Tenant-Scoped Redis Idempotency Keys

**Files:**
- Modify: `lip/c3_repayment_engine/repayment_loop.py:252-291` (`_claim_repayment`)
- Modify: `lip/c3_repayment_engine/repayment_loop.py:346` (`trigger_repayment` call site)

- [ ] **Step 1: Write tests for Redis key scoping**

Add to `lip/tests/test_settlement_bridge.py` (append at end):

```python
class TestRedisKeyScoping:
    """Test that _claim_repayment() uses tenant-scoped Redis keys."""

    def test_tenant_scoped_redis_key(self):
        """Processor mode: key = lip:{tenant_id}:repaid:{uetr}."""
        from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor, ActiveLoan, RepaymentTrigger
        from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry

        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # claim succeeds

        monitor = SettlementMonitor(
            handler_registry=SettlementHandlerRegistry.create_default(),
            uetr_mapping={},
            corridor_buffer={},
        )
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=MagicMock(),
            redis_client=mock_redis,
        )
        result = loop._claim_repayment("test-uetr", 7, tenant_id="FINASTRA_EU_001")
        assert result is True

        # Verify Redis key format
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key == "lip:FINASTRA_EU_001:repaid:test-uetr"

    def test_bank_mode_redis_key_unchanged(self):
        """Bank mode (no tenant): key = lip:repaid:{uetr} (backward compat)."""
        from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
        from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry

        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        monitor = SettlementMonitor(
            handler_registry=SettlementHandlerRegistry.create_default(),
            uetr_mapping={},
            corridor_buffer={},
        )
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=MagicMock(),
            redis_client=mock_redis,
        )
        result = loop._claim_repayment("test-uetr", 7, tenant_id="")
        assert result is True

        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key == "lip:repaid:test-uetr"

    def test_in_memory_fallback_still_works(self):
        """In-memory idempotency (no Redis) works regardless of tenant_id."""
        from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
        from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry

        monitor = SettlementMonitor(
            handler_registry=SettlementHandlerRegistry.create_default(),
            uetr_mapping={},
            corridor_buffer={},
        )
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=MagicMock(),
        )
        assert loop._claim_repayment("uetr-1", 7, tenant_id="T1") is True
        assert loop._claim_repayment("uetr-1", 7, tenant_id="T1") is False  # duplicate
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_settlement_bridge.py::TestRedisKeyScoping -v 2>&1 | head -20`
Expected: TypeError — `_claim_repayment()` got unexpected keyword argument `tenant_id`

- [ ] **Step 3: Modify `_claim_repayment()` to accept tenant_id**

In `lip/c3_repayment_engine/repayment_loop.py`, change the signature at line 252:

**Old (line 252):**
```python
    def _claim_repayment(self, uetr: str, maturity_days: int) -> bool:
```

**New:**
```python
    def _claim_repayment(self, uetr: str, maturity_days: int, tenant_id: str = "") -> bool:
```

And change the Redis key construction at line 265:

**Old (line 265):**
```python
                key = f"{_REDIS_REPAID_PREFIX}{uetr}"
```

**New:**
```python
                key = f"lip:{tenant_id}:repaid:{uetr}" if tenant_id else f"{_REDIS_REPAID_PREFIX}{uetr}"
```

- [ ] **Step 4: Modify `trigger_repayment()` call site**

At line 346, change:

**Old:**
```python
        if not self._claim_repayment(loan.uetr, maturity_days):
```

**New:**
```python
        if not self._claim_repayment(loan.uetr, maturity_days, tenant_id=loan.licensee_id):
```

- [ ] **Step 5: Run Redis scoping tests + all existing C3 tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_settlement_bridge.py::TestRedisKeyScoping lip/tests/test_c3_repayment.py -v 2>&1 | tail -20`
Expected: ALL PASS

- [ ] **Step 6: Run ruff**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c3_repayment_engine/repayment_loop.py`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add lip/c3_repayment_engine/repayment_loop.py lip/tests/test_settlement_bridge.py
git commit -m "feat(c3): tenant-scoped Redis idempotency keys — lip:{tenant_id}:repaid:{uetr}"
```

---

## Task 6: Update C3 __init__.py Exports

**Files:**
- Modify: `lip/c3_repayment_engine/__init__.py`

- [ ] **Step 1: Add exports**

Add to imports (after existing imports at lines 10-12):
```python
from .nav_emitter import NAVEventEmitter
from .settlement_bridge import SettlementCallbackBridge
```

Add to `__all__` list (after line 19):
```python
    "NAVEventEmitter",
    "SettlementCallbackBridge",
```

- [ ] **Step 2: Run ruff**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c3_repayment_engine/__init__.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add lip/c3_repayment_engine/__init__.py
git commit -m "feat(c3): export NAVEventEmitter and SettlementCallbackBridge"
```

---

## Task 7: TDD Tests + Implementation — MIPLO Portfolio Endpoints

**Files:**
- Create: `lip/tests/test_miplo_portfolio.py`
- Modify: `lip/api/portfolio_router.py` (add `get_tenant_nav()`)
- Modify: `lip/api/miplo_service.py` (add `portfolio_reporter` + delegation)
- Modify: `lip/api/miplo_router.py` (add portfolio endpoints)

- [ ] **Step 1: Write the test file**

```python
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

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_portfolio.py -v 2>&1 | head -20`
Expected: AttributeError — `get_tenant_nav` not found on PortfolioReporter

- [ ] **Step 3: Add `get_tenant_nav()` to PortfolioReporter**

In `lip/api/portfolio_router.py`, add after `get_risk()` method (after the `get_risk` method's return statement, before the `make_portfolio_router` function):

```python
    # ── GET /miplo/portfolio/nav (tenant-scoped) ────────────────────────────

    def get_tenant_nav(self, tenant_id: str) -> Dict:
        """Return NAVEvent-shaped data for a single tenant (synchronous query).

        Used by MIPLO portfolio endpoints for processor dashboards.
        Filters active loans by licensee_id at query time.
        """
        now = datetime.now(tz=timezone.utc)
        loans = [
            loan for loan in self._loop.get_active_loans()
            if loan.licensee_id == tenant_id
        ]
        total_exposure = sum(
            (loan.principal for loan in loans), Decimal("0")
        )
        return {
            "tenant_id": tenant_id,
            "active_loans": len(loans),
            "total_exposure_usd": str(total_exposure),
            "timestamp": now.isoformat(),
        }
```

- [ ] **Step 4: Add portfolio methods to MIPLOService**

In `lip/api/miplo_service.py`, modify the constructor (line 45-59) to accept `portfolio_reporter`:

Add `portfolio_reporter=None` parameter after `metrics_collector=None`:

```python
    def __init__(
        self,
        pipeline,
        processor_context: ProcessorLicenseeContext,
        metrics_collector=None,
        portfolio_reporter=None,
    ):
```

Add `self._portfolio = portfolio_reporter` after `self._metrics = metrics_collector` (line 59).

Then add portfolio delegation methods before `get_status()`:

```python
    def get_portfolio_loans(self):
        """Return active loans for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_loans()

    def get_portfolio_exposure(self):
        """Return exposure breakdown for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_exposure()

    def get_portfolio_nav(self):
        """Return NAV snapshot for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_tenant_nav(self._tenant_id)
```

- [ ] **Step 5: Add portfolio endpoints to MIPLO router**

In `lip/api/miplo_router.py`, add three endpoints inside `make_miplo_router()` before `return router` (before line 129):

```python
        @router.get("/portfolio/loans", dependencies=deps)
        async def portfolio_loans():
            """Active loans for this processor's tenant."""
            result = miplo_service.get_portfolio_loans()
            if result is None:
                raise HTTPException(status_code=503, detail="Portfolio reporting not configured")
            return result

        @router.get("/portfolio/exposure", dependencies=deps)
        async def portfolio_exposure():
            """Exposure breakdown for this processor's tenant."""
            result = miplo_service.get_portfolio_exposure()
            if result is None:
                raise HTTPException(status_code=503, detail="Portfolio reporting not configured")
            return result

        @router.get("/portfolio/nav", dependencies=deps)
        async def portfolio_nav():
            """Latest NAV snapshot for this processor's tenant."""
            result = miplo_service.get_portfolio_nav()
            if result is None:
                raise HTTPException(status_code=503, detail="Portfolio reporting not configured")
            return result
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_portfolio.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run ruff on modified files**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/portfolio_router.py lip/api/miplo_service.py lip/api/miplo_router.py`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add lip/api/portfolio_router.py lip/api/miplo_service.py lip/api/miplo_router.py lip/tests/test_miplo_portfolio.py
git commit -m "feat(miplo): add tenant-scoped portfolio endpoints — /miplo/portfolio/loans, exposure, nav"
```

---

## Task 8: Wire Everything in app.py + Full Regression

**Files:**
- Modify: `lip/api/app.py:46-178`

- [ ] **Step 1: Modify app.py — replace no-op callback with SettlementCallbackBridge**

In `lip/api/app.py`, replace the repayment_loop construction block (lines 74-77):

**Old:**
```python
        repayment_loop = RepaymentLoop(
            monitor=settlement_monitor,
            repayment_callback=lambda event: logger.info("Repayment event: %s", event),
        )
```

**New:**
```python
        from lip.c3_repayment_engine.settlement_bridge import SettlementCallbackBridge

        # Bank mode default: bridge routes to royalty settlement only
        settlement_bridge = SettlementCallbackBridge(
            royalty_settlement=royalty_settlement,
        )
        repayment_loop = RepaymentLoop(
            monitor=settlement_monitor,
            repayment_callback=settlement_bridge,
        )
```

- [ ] **Step 2: Modify app.py — wire processor-mode NAV + revenue in MIPLO block**

Replace the MIPLO conditional block (lines 163-172):

**Old:**
```python
        # MIPLO gateway (P3 processor deployments — conditional)
        if pipeline is not None and processor_context is not None:
            from lip.api.miplo_router import make_miplo_router
            from lip.api.miplo_service import MIPLOService

            miplo_svc = MIPLOService(pipeline, processor_context, metrics_collector)
            application.include_router(
                make_miplo_router(miplo_svc, auth_dependency=auth_dep),
                prefix="/miplo",
            )
```

**New:**
```python
        # MIPLO gateway (P3 processor deployments — conditional)
        if pipeline is not None and processor_context is not None:
            from decimal import Decimal as _Decimal

            from lip.api.miplo_router import make_miplo_router
            from lip.api.miplo_service import MIPLOService
            from lip.c3_repayment_engine.nav_emitter import NAVEventEmitter
            from lip.c8_license_manager.revenue_metering import RevenueMetering

            # Revenue metering for processor fee splits
            revenue_metering = RevenueMetering()

            # NAV emitter — wired to repayment_loop.get_active_loans after construction
            nav_emitter = NAVEventEmitter(
                get_active_loans=repayment_loop.get_active_loans,
                nav_callback=lambda nav: logger.info("NAV event: tenant=%s loans=%d", nav.tenant_id, nav.active_loans),
                metrics_collector=metrics_collector,
            )

            # Upgrade settlement bridge to processor mode (public method, not private mutation)
            settlement_bridge.upgrade_to_processor_mode(
                revenue_metering=revenue_metering,
                nav_emitter=nav_emitter,
                platform_take_rate_pct=_Decimal(str(processor_context.platform_take_rate_pct)),
            )

            # Tenant-scoped portfolio reporter for MIPLO
            miplo_portfolio_reporter = PortfolioReporter(
                repayment_loop=repayment_loop,
                royalty_settlement=royalty_settlement,
                licensee_id=processor_context.licensee_id,
                risk_engine=risk_engine,
            )

            miplo_svc = MIPLOService(
                pipeline, processor_context, metrics_collector,
                portfolio_reporter=miplo_portfolio_reporter,
            )
            application.include_router(
                make_miplo_router(miplo_svc, auth_dependency=auth_dep),
                prefix="/miplo",
            )

            # Start NAV emission background thread + register shutdown hook
            nav_emitter.start()
            _shutdown_hooks.append(nav_emitter.stop)
```

- [ ] **Step 3: Run ruff**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/app.py`
Expected: no errors

- [ ] **Step 4: Run full test suite (regression check)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -q 2>&1 | tail -20`
Expected: all tests pass, zero failures

- [ ] **Step 5: Run ruff on entire lip/ directory**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/`
Expected: zero errors

- [ ] **Step 6: Commit**

```bash
git add lip/api/app.py
git commit -m "feat(app): wire SettlementCallbackBridge, NAVEventEmitter, and MIPLO portfolio for processor mode"
```

---

## Verification Checklist

Before declaring Sprint 2d complete:

1. [ ] `ruff check lip/` — zero errors
2. [ ] `python -m pytest lip/tests/test_settlement_bridge.py -v` — all bridge + Redis scoping tests pass
3. [ ] `python -m pytest lip/tests/test_nav_emitter.py -v` — all NAV emitter tests pass
4. [ ] `python -m pytest lip/tests/test_miplo_portfolio.py -v` — all MIPLO portfolio tests pass
5. [ ] `python -m pytest lip/tests/test_c3_repayment.py -v` — all existing C3 tests pass (backward compat)
6. [ ] `python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py` — no regressions
7. [ ] Manual: `_claim_repayment()` accepts `tenant_id` and produces `lip:{tenant_id}:repaid:{uetr}` key
8. [ ] Manual: SettlementCallbackBridge `__call__` routes to all 3 consumers in processor mode
9. [ ] Manual: NAVEventEmitter groups by `licensee_id`, skips empty, emits `NAVEvent` per tenant
10. [ ] Manual: `/miplo/portfolio/nav` returns tenant-scoped data
11. [ ] Manual: No secrets, artifacts/, or c6_corpus_*.json in any committed file

---

## CIPHER / QUANT Review Notes

**QUANT — Fee Path Untouched:**
The only change to `trigger_repayment()` is passing `tenant_id=loan.licensee_id` to `_claim_repayment()`. The fee waterfall (lines 349-378) is not modified. Revenue metering receives the computed fee as a `Decimal(repayment_record["fee"])` string conversion — same pattern as Sprint 2a.

**CIPHER — Redis Key Chain of Trust:**
`lip:{tenant_id}:repaid:{uetr}` where tenant_id = `loan.licensee_id` = `C7.licensee_id` = C8 boot-validated `ProcessorLicenseeContext.licensee_id`. HMAC-signed at source.

**CIPHER — Settlement Bridge Fault Isolation:**
Each downstream consumer (royalty, revenue, NAV) is wrapped in independent try/except. A Redis failure in royalty recording does not block revenue metering or NAV history tracking.

---

## Next Session: Sprint 2e or Sprint 3a

After Sprint 2d, the P3 multi-tenant foundation is complete (2a→2d). Options:
- Sprint 2e: Integration testing — end-to-end processor deployment flow
- Sprint 3a: Begin P4/P5/P6 product builds on the shared infrastructure
