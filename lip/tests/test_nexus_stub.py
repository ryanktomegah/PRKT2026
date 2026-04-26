"""
test_nexus_stub.py — Project Nexus stub normalizer (PHASE-2-STUB).

Smoke-level coverage: stub returns a well-formed NormalizedEvent and the
EventNormalizer dispatcher routes CBDC_NEXUS to it. Real schema lands
when NGP publishes ISO 20022 specs (expected 2026; onboarding mid-2027).
"""
from decimal import Decimal

from lip.c5_streaming.event_normalizer import EventNormalizer, NormalizedEvent
from lip.c5_streaming.nexus_normalizer import NexusNormalizer
from lip.common.constants import RAIL_MATURITY_HOURS


def _msg() -> dict:
    return {
        "transaction_id": "NEXUS-STUB-001",
        "end_to_end_id": "E2E-NEXUS-001",
        "sender_bic": "SBINGB2LXXX",
        "receiver_bic": "MAYBSGSGXXX",
        "amount": "10000.00",
        "currency": "INR",
        "timestamp": "2026-04-25T12:00:00",
        "status_reason_code": "AC04",
        "status_reason_description": "Closed account",
    }


class TestNexusStub:

    def test_rail_is_cbdc_nexus(self):
        event = NexusNormalizer().normalize(_msg())
        assert event.rail == "CBDC_NEXUS"

    def test_amount_and_currency(self):
        event = NexusNormalizer().normalize(_msg())
        assert event.amount == Decimal("10000.00")
        assert event.currency == "INR"

    def test_dispatcher_routes_cbdc_nexus(self):
        event = EventNormalizer().normalize("CBDC_NEXUS", _msg())
        assert isinstance(event, NormalizedEvent)
        assert event.rail == "CBDC_NEXUS"

    def test_rail_maturity_4h(self):
        assert RAIL_MATURITY_HOURS["CBDC_NEXUS"] == 4.0

    def test_dispatcher_does_not_route_nexus_to_mbridge(self):
        # Regression: distinct from CBDC_MBRIDGE.
        event = EventNormalizer().normalize("CBDC_NEXUS", _msg())
        assert event.rail != "CBDC_MBRIDGE"

    def test_rejection_code_passes_through(self):
        # ISO 20022 native — no proprietary code map needed.
        event = NexusNormalizer().normalize(_msg())
        assert event.rejection_code == "AC04"

    def test_uetr_from_transaction_id(self):
        event = NexusNormalizer().normalize(_msg())
        assert event.uetr == "NEXUS-STUB-001"
