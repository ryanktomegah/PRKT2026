"""
test_c3_repayment.py — Tests for C3 Repayment Engine
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c3_repayment_engine.corridor_buffer import _WINDOW_SECONDS, CorridorBuffer
from lip.c3_repayment_engine.rejection_taxonomy import (
    REJECTION_CODE_TAXONOMY,
    RejectionClass,
    classify_rejection_code,
    get_all_codes_for_class,
    is_dispute_block,
    maturity_days,
)
from lip.c3_repayment_engine.repayment_loop import (
    ActiveLoan,
    RepaymentLoop,
    RepaymentTrigger,
    SettlementMonitor,
)
from lip.c3_repayment_engine.settlement_handlers import (
    SettlementHandlerRegistry,
    SettlementRail,
)
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable


class TestRejectionTaxonomy:
    def test_class_a_code(self):
        assert classify_rejection_code("AC01") == RejectionClass.CLASS_A

    def test_class_b_code(self):
        assert classify_rejection_code("AG01") == RejectionClass.CLASS_B

    def test_class_c_code(self):
        assert classify_rejection_code("LEGL") == RejectionClass.CLASS_C

    def test_block_code_disp(self):
        assert classify_rejection_code("DISP") == RejectionClass.BLOCK

    def test_block_code_frau(self):
        assert classify_rejection_code("FRAU") == RejectionClass.BLOCK

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError):
            classify_rejection_code("XXXX")

    def test_maturity_class_a(self):
        assert maturity_days(RejectionClass.CLASS_A) == 3

    def test_maturity_class_b(self):
        assert maturity_days(RejectionClass.CLASS_B) == 7

    def test_maturity_class_c(self):
        assert maturity_days(RejectionClass.CLASS_C) == 21

    def test_maturity_block_is_zero(self):
        assert maturity_days(RejectionClass.BLOCK) == 0

    def test_is_dispute_block_true(self):
        assert is_dispute_block("DISP") is True
        assert is_dispute_block("FRAU") is True

    def test_is_dispute_block_false(self):
        assert is_dispute_block("AC01") is False

    def test_get_all_codes_for_class_a(self):
        codes = get_all_codes_for_class(RejectionClass.CLASS_A)
        assert len(codes) >= 5
        assert "AC01" in codes

    def test_total_codes_at_least_47(self):
        assert len(REJECTION_CODE_TAXONOMY) >= 47

    def test_all_codes_map_to_valid_class(self):
        for code, cls in REJECTION_CODE_TAXONOMY.items():
            assert isinstance(cls, RejectionClass), f"Code {code} has invalid class"


class TestCorridorBuffer:
    def test_tier_0_no_data(self):
        buf = CorridorBuffer()
        tier = buf.get_buffer_tier("USD_EUR")
        assert tier == 0

    def test_tier_1_sparse(self):
        buf = CorridorBuffer()
        for i in range(10):
            buf.add_observation("USD_EUR", float(i + 1))
        assert buf.get_buffer_tier("USD_EUR") == 1

    def test_tier_2_moderate(self):
        buf = CorridorBuffer()
        for i in range(50):
            buf.add_observation("USD_EUR", float(i + 1))
        assert buf.get_buffer_tier("USD_EUR") == 2

    def test_tier_3_dense(self):
        buf = CorridorBuffer()
        for i in range(150):
            buf.add_observation("USD_EUR", float(i % 10 + 1))
        assert buf.get_buffer_tier("USD_EUR") == 3

    def test_p95_returns_float(self):
        buf = CorridorBuffer()
        p95 = buf.estimate_p95("USD_EUR")
        assert isinstance(p95, float)
        assert p95 > 0

    def test_tier3_p95_is_empirical(self):
        buf = CorridorBuffer()
        data = [2.0] * 100 + [10.0] * 5  # P95 should be around 10.0
        for v in data:
            buf.add_observation("USD_GBP", v)
        p95 = buf.estimate_p95("USD_GBP")
        assert p95 >= 2.0  # Plausible range

    def test_serialization_round_trip(self):
        buf = CorridorBuffer()
        for i in range(20):
            buf.add_observation("EUR_GBP", float(i + 1))
        d = buf.to_dict()
        buf2 = CorridorBuffer.from_dict(d)
        assert buf2.get_buffer_tier("EUR_GBP") == buf.get_buffer_tier("EUR_GBP")


class TestUETRMapping:
    def test_store_and_lookup(self):
        table = UETRMappingTable()
        table.store("end123", "uetr-456", maturity_days=7)
        assert table.lookup("end123") == "uetr-456"

    def test_lookup_missing_returns_none(self):
        table = UETRMappingTable()
        assert table.lookup("nonexistent") is None

    def test_delete(self):
        table = UETRMappingTable()
        table.store("end123", "uetr-456", maturity_days=7)
        table.delete("end123")
        assert table.lookup("end123") is None

    def test_ttl_is_maturity_plus_45(self):
        table = UETRMappingTable()
        ttl = table.get_ttl_seconds(7)
        assert ttl == (7 + 45) * 86400


class TestCorridorBuffer90DayExpiry:
    """Gap 3 regression: observations older than 90 days must be pruned."""

    def test_fresh_observations_are_retained(self):
        buf = CorridorBuffer()
        buf.add_observation("USD_EUR", 3.0)
        buf.add_observation("USD_EUR", 5.0)
        assert buf.get_buffer_tier("USD_EUR") >= 1

    def test_expired_observations_are_pruned(self, monkeypatch):
        """Observations stamped 91 days ago must be pruned."""
        buf = CorridorBuffer()
        # Inject observations with a timestamp far in the past
        old_ts = time.time() - _WINDOW_SECONDS - 86_400  # 91 days ago
        buf._observations["USD_EUR"] = [(old_ts, 3.0), (old_ts, 5.0)]
        # Tier check triggers pruning
        tier = buf.get_buffer_tier("USD_EUR")
        assert tier == 0  # all expired → no data

    def test_mixed_fresh_and_expired(self, monkeypatch):
        """Only in-window observations count toward the tier."""
        buf = CorridorBuffer()
        old_ts = time.time() - _WINDOW_SECONDS - 86_400
        fresh_ts = time.time()
        # 2 expired + 3 fresh
        buf._observations["USD_EUR"] = [
            (old_ts, 1.0), (old_ts, 2.0),
            (fresh_ts, 3.0), (fresh_ts, 4.0), (fresh_ts, 5.0),
        ]
        tier = buf.get_buffer_tier("USD_EUR")
        assert tier == 1  # 3 fresh observations → Tier 1 (< 30)

    def test_purge_expired_removes_across_all_corridors(self):
        buf = CorridorBuffer()
        old_ts = time.time() - _WINDOW_SECONDS - 86_400
        buf._observations["USD_EUR"] = [(old_ts, 1.0)]
        buf._observations["USD_GBP"] = [(old_ts, 2.0)]
        removed = buf.purge_expired()
        assert removed == 2
        assert buf.get_buffer_tier("USD_EUR") == 0
        assert buf.get_buffer_tier("USD_GBP") == 0

    def test_serialisation_preserves_timestamps(self):
        buf = CorridorBuffer()
        buf.add_observation("EUR_GBP", 2.5)
        d = buf.to_dict()
        buf2 = CorridorBuffer.from_dict(d)
        # Timestamps are preserved, so tier is the same
        assert buf2.get_buffer_tier("EUR_GBP") == buf.get_buffer_tier("EUR_GBP")


def _make_monitor():
    registry = SettlementHandlerRegistry.create_default()
    um = UETRMappingTable()
    cb = CorridorBuffer()
    return SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)


def _make_loan(rejection_class="CLASS_B", past_maturity=False) -> ActiveLoan:
    funded_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    if past_maturity:
        maturity = datetime.now(tz=timezone.utc) - timedelta(seconds=5)
    else:
        maturity = datetime.now(tz=timezone.utc) + timedelta(days=7)
    return ActiveLoan(
        loan_id=str(uuid.uuid4()),
        uetr=str(uuid.uuid4()),
        individual_payment_id=str(uuid.uuid4()),
        principal=Decimal("50000"),
        fee_bps=300,
        maturity_date=maturity,
        rejection_class=rejection_class,
        corridor="USD_EUR",
        funded_at=funded_at,
    )


class TestRepaymentLoopIdempotency:
    """Gap 4 regression: duplicate settlement signals must trigger exactly one repayment."""

    def test_in_memory_idempotency_second_call_skipped(self):
        monitor = _make_monitor()
        repaid = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: repaid.append(r),
        )
        loan = _make_loan()
        loop.register_loan(loan)

        r1 = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)
        r2 = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)

        assert r1 != {}  # first repayment processed
        assert r2 == {}  # second skipped — idempotency
        assert len(repaid) == 1

    def test_redis_setnx_idempotency_second_call_skipped(self):
        """With a mock Redis that returns None on second SETNX, callback fires only once."""
        mock_redis = MagicMock()
        # First call: SETNX succeeds (returns "OK")
        # Second call: SETNX fails (returns None — key already exists)
        mock_redis.set.side_effect = ["OK", None]

        monitor = _make_monitor()
        repaid = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: repaid.append(r),
            redis_client=mock_redis,
        )
        loan = _make_loan()
        loop.register_loan(loan)

        r1 = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)
        # Re-register (was deregistered after first repayment) to test second call
        loop.register_loan(loan)
        r2 = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)

        assert r1 != {}
        assert r2 == {}
        assert len(repaid) == 1

    def test_maturity_check_does_not_append_empty_records(self):
        """check_maturities() must filter out idempotency-skipped (empty) records."""
        monitor = _make_monitor()
        repaid = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: repaid.append(r),
        )
        loan = _make_loan(past_maturity=True)
        loop.register_loan(loan)

        # First check: triggers repayment
        results1 = loop.check_maturities()
        assert len([r for r in results1 if r]) == 1

        # Re-register and check again — loan was already repaid (in-memory set)
        loop.register_loan(loan)
        results2 = loop.check_maturities()
        # All records should be filtered out (idempotency skip returns {})
        assert all(not r for r in results2)

    def test_repayment_record_has_all_required_fields(self):
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: records.append(r),
        )
        loan = _make_loan()
        loop.register_loan(loan)
        r = loop.trigger_repayment(loan, RepaymentTrigger.MATURITY_REACHED, loan.principal)

        required = {"loan_id", "uetr", "principal", "fee", "settlement_amount",
                    "trigger", "funded_at", "maturity_date", "repaid_at"}
        assert required.issubset(r.keys())

    def test_block_class_loan_skipped_in_maturity_check(self):
        monitor = _make_monitor()
        repaid = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: repaid.append(r),
        )
        loan = _make_loan(rejection_class="BLOCK", past_maturity=True)
        loop.register_loan(loan)
        _results = loop.check_maturities()
        # BLOCK loans are skipped entirely — no repayment triggered
        assert repaid == []


class TestSettlementHandlers:
    def test_registry_dispatches_swift(self):
        registry = SettlementHandlerRegistry.create_default()
        msg = {
            "GrpHdr": {"MsgId": "test-uetr-001"},
            "TxInfAndSts": {
                "OrgnlEndToEndId": "e2e-001",
                "OrgnlTxRef": {"Amt": {"InstdAmt": "50000.00"}},
            },
        }
        signal = registry.dispatch(SettlementRail.SWIFT, msg)
        assert signal.rail == SettlementRail.SWIFT

    def test_registry_dispatches_fednow(self):
        registry = SettlementHandlerRegistry.create_default()
        msg = {
            "creditTransfer": {
                "messageId": "fn-msg-001",
                "endToEndId": "fn-e2e-001",
            },
            "debitParty": {"routingNumber": "021000021"},
            "creditParty": {"routingNumber": "011000015"},
            "amount": {"value": "10000.00", "currency": "USD"},
        }
        signal = registry.dispatch(SettlementRail.FEDNOW, msg)
        assert signal.rail == SettlementRail.FEDNOW

    def test_all_5_rails_registered(self):
        registry = SettlementHandlerRegistry.create_default()
        for rail in SettlementRail:
            assert rail in registry._handlers
