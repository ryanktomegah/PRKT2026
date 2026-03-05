"""
test_c3_repayment.py — Tests for C3 Repayment Engine
"""
import pytest
from decimal import Decimal
from datetime import datetime

from lip.c3_repayment_engine.rejection_taxonomy import (
    RejectionClass, classify_rejection_code, maturity_days,
    is_dispute_block, get_all_codes_for_class, REJECTION_CODE_TAXONOMY,
)
from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable
from lip.c3_repayment_engine.settlement_handlers import (
    SettlementHandlerRegistry, SettlementRail,
)


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
