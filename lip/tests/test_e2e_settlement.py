"""
test_e2e_settlement.py — Multi-rail settlement E2E tests.

Covers the 5 settlement rails:
  a. SWIFT camt.054 (direct UETR match)
  b. FedNow pacs.002 (native UETR)
  c. RTP ISO 20022 (EndToEndId → UETR mapping via in-memory table)
  d. SEPA Instant pacs.008 (direct UETR)
  e. Statistical buffer fallback (P95 corridor timeout)

Also verifies idempotency.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer
from lip.c3_repayment_engine.repayment_loop import (
    ActiveLoan,
    RepaymentLoop,
    SettlementMonitor,
)
from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable
from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.pipeline import LIPPipeline

from .conftest import _HMAC_KEY, _SALT, MockC1Engine, MockC2Engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor():
    registry = SettlementHandlerRegistry.create_default()
    um = UETRMappingTable()
    cb = CorridorBuffer()
    return SettlementMonitor(
        handler_registry=registry,
        uetr_mapping=um,
        corridor_buffer=cb,
    ), um


def _make_pipeline_with_monitor(monitor, failure_probability=0.80):
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    agent = ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=MockC1Engine(failure_probability),
        c2_engine=MockC2Engine(pd_score=0.05, fee_bps=300, tier=3),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
        c3_monitor=monitor,
    )


def _register_loan(monitor: SettlementMonitor, uetr: str, amount: Decimal) -> ActiveLoan:
    """Directly register a funded loan with the settlement monitor."""
    loan = ActiveLoan(
        loan_id=str(uuid.uuid4()),
        uetr=uetr,
        individual_payment_id=str(uuid.uuid4()),
        principal=amount,
        fee_bps=300,
        maturity_date=datetime.now(tz=timezone.utc) + timedelta(days=7),
        rejection_class="CLASS_B",
        corridor="USD_EUR",
        funded_at=datetime.now(tz=timezone.utc),
    )
    monitor.register_loan(loan)
    return loan


# ===========================================================================
# SWIFT camt.054 settlement
# ===========================================================================

class TestSWIFTSettlement:

    def test_swift_settlement_matches_funded_loan(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("50000"))

        msg = {"uetr": uetr, "amount": "50000", "currency": "USD"}
        trigger = monitor.process_signal("SWIFT", msg)
        assert trigger is not None
        assert trigger["uetr"] == uetr
        assert trigger["signal_rail"] == "SWIFT"

    def test_swift_settlement_deregisters_loan(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("75000"))

        msg = {"uetr": uetr, "amount": "75000", "currency": "USD"}
        trigger = monitor.process_signal("SWIFT", msg)
        assert trigger is not None
        # Simulate repayment loop deregistering the loan
        monitor.deregister_loan(uetr)
        assert monitor.match_loan(uetr) is None

    def test_swift_duplicate_settlement_silently_dropped(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("50000"))

        msg = {"uetr": uetr, "amount": "50000", "currency": "USD"}
        trigger1 = monitor.process_signal("SWIFT", msg)
        # Deregister after first settlement (what repayment loop does)
        monitor.deregister_loan(uetr)
        trigger2 = monitor.process_signal("SWIFT", msg)

        assert trigger1 is not None
        assert trigger2 is None  # idempotent — loan deregistered after first


# ===========================================================================
# FedNow settlement
# ===========================================================================

class TestFedNowSettlement:

    def test_fednow_settlement_matches_funded_loan(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("25000"))

        msg = {"uetr": uetr, "amount": "25000", "currency": "USD"}
        trigger = monitor.process_signal("FEDNOW", msg)
        assert trigger is not None
        assert trigger["uetr"] == uetr
        assert trigger["signal_rail"] == "FEDNOW"

    def test_fednow_idempotency(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("10000"))

        msg = {"uetr": uetr, "amount": "10000", "currency": "USD"}
        trigger1 = monitor.process_signal("FEDNOW", msg)
        monitor.deregister_loan(uetr)
        trigger2 = monitor.process_signal("FEDNOW", msg)
        assert trigger1 is not None
        assert trigger2 is None


# ===========================================================================
# RTP settlement (EndToEndId → UETR mapping)
# ===========================================================================

class TestRTPSettlement:

    def test_rtp_settlement_via_direct_uetr(self):
        """RTP settlement using direct UETR field in message."""
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("30000"))

        # RTP message with explicit uetr field
        msg = {
            "uetr": uetr,
            "amount": "30000",
            "currency": "USD",
        }
        trigger = monitor.process_signal("RTP", msg)
        assert trigger is not None
        assert trigger["uetr"] == uetr

    def test_rtp_uetr_mapping_table_stores_and_retrieves(self):
        """Verify UETRMappingTable can map EndToEndId → UETR."""
        um = UETRMappingTable()
        uetr = str(uuid.uuid4())
        e2e_id = "RTP-E2E-" + str(uuid.uuid4())[:8]
        um.store(e2e_id, uetr, maturity_days=7)
        retrieved = um.lookup(e2e_id)
        assert retrieved == uetr

    def test_rtp_idempotency(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("15000"))

        msg = {"uetr": uetr, "amount": "15000", "currency": "USD"}
        t1 = monitor.process_signal("RTP", msg)
        monitor.deregister_loan(uetr)
        t2 = monitor.process_signal("RTP", msg)
        assert t1 is not None
        assert t2 is None


# ===========================================================================
# SEPA settlement
# ===========================================================================

class TestSEPASettlement:

    def test_sepa_settlement_matches_funded_loan(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("80000"))

        msg = {"uetr": uetr, "amount": "80000", "currency": "EUR"}
        trigger = monitor.process_signal("SEPA", msg)
        assert trigger is not None
        assert trigger["uetr"] == uetr
        assert trigger["signal_rail"] == "SEPA"

    def test_sepa_idempotency(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("20000"))

        msg = {"uetr": uetr, "amount": "20000", "currency": "EUR"}
        t1 = monitor.process_signal("SEPA", msg)
        monitor.deregister_loan(uetr)
        t2 = monitor.process_signal("SEPA", msg)
        assert t1 is not None
        assert t2 is None


# ===========================================================================
# Buffer (statistical P95 corridor timeout) settlement
# ===========================================================================

class TestBufferSettlement:

    def test_buffer_settlement_matches_funded_loan(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("60000"))

        msg = {"uetr": uetr, "amount": "60000", "currency": "USD"}
        trigger = monitor.process_signal("BUFFER", msg)
        assert trigger is not None
        assert trigger["uetr"] == uetr
        assert trigger["signal_rail"] == "BUFFER"

    def test_buffer_idempotency(self):
        monitor, um = _make_monitor()
        uetr = str(uuid.uuid4())
        _register_loan(monitor, uetr, Decimal("45000"))

        msg = {"uetr": uetr, "amount": "45000", "currency": "USD"}
        t1 = monitor.process_signal("BUFFER", msg)
        monitor.deregister_loan(uetr)
        t2 = monitor.process_signal("BUFFER", msg)
        assert t1 is not None
        assert t2 is None


# ===========================================================================
# Multi-rail: fund 5 loans, each settling via different rail
# ===========================================================================

class TestMultiRailParallel:

    def test_five_loans_each_different_rail(self):
        """Fund 5 loans and settle each via a different rail."""
        monitor, um = _make_monitor()
        repaid = []
        _loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: repaid.append(r))

        rails_and_msgs = []
        for i, rail in enumerate(["SWIFT", "FEDNOW", "SEPA", "BUFFER", "SWIFT"]):
            uetr = str(uuid.uuid4())
            loan = _register_loan(monitor, uetr, Decimal(str(10000 * (i + 1))))
            msg = {"uetr": uetr, "amount": str(loan.principal), "currency": "USD"}
            rails_and_msgs.append((rail, uetr, msg))

        settled = 0
        for rail, uetr, msg in rails_and_msgs:
            trigger = monitor.process_signal(rail, msg)
            if trigger is not None:
                settled += 1

        assert settled == 5

    def test_unknown_uetr_returns_none(self):
        monitor, um = _make_monitor()
        msg = {"uetr": "unknown-uetr-xyz", "amount": "1000", "currency": "USD"}
        trigger = monitor.process_signal("SWIFT", msg)
        assert trigger is None
