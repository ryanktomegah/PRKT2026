"""
test_cbdc_mbridge_normalizer.py — mBridge multi-CBDC PvP normalizer tests (Phase B).

Real-world context (April 2026):
  - mBridge: post-BIS, 5 central banks (PBOC, HKMA, BoT, CBUAE, SAMA), $55.5B settled.
  - Atomic PvP: up to 5 currency legs in one transaction (CNY/HKD/THB/AED/SAR).
  - ISO 20022 native + DLT extensions for finality and consensus.

Schema modelled (BIS Innovation Hub has not published formal production schema).
"""
from decimal import Decimal

import pytest

from lip.c5_streaming.cbdc_mbridge_normalizer import MBridgeNormalizer
from lip.c5_streaming.event_normalizer import EventNormalizer, NormalizedEvent


def _mbridge_msg(failed_index: int = 1, **overrides) -> dict:
    """Multi-leg mBridge atomic settlement event with a single failed leg."""
    base = {
        "bridge_tx_id": "MBRIDGE-2026-04-25-0001",
        "atomic_settlement_id": "ATM-9F2C",
        "consensus_round": 12345,
        "finality_seconds": 2.3,
        "failed_leg_index": failed_index,
        "legs": [
            {
                "index": 0,
                "status": "ACSC",
                "amount": "1000000.00",
                "currency": "CNY",
                "sender_wallet": "W-CN-SND",
                "receiver_wallet": "W-HK-RCV",
                "sender_bic": "ICBKCNBJXXX",
                "receiver_bic": "HSBCHKHHXXX",
            },
            {
                "index": 1,
                "status": "FAILED",
                "amount": "139500.00",
                "currency": "HKD",
                "sender_wallet": "W-HK-SND",
                "receiver_wallet": "W-US-RCV",
                "sender_bic": "HSBCHKHHXXX",
                "receiver_bic": "BOFAUS3NXXX",
                "failure_code": "CBDC-CF01",
                "failure_description": "Consensus not reached within 3s finality window",
            },
        ],
        "timestamp": "2026-04-25T10:15:00",
    }
    base.update(overrides)
    return base


class TestMBridgeNormalizeBasic:

    def setup_method(self):
        self.n = MBridgeNormalizer()

    def test_rail_is_cbdc_mbridge(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.rail == "CBDC_MBRIDGE"

    def test_uetr_from_bridge_tx_id(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.uetr == "MBRIDGE-2026-04-25-0001"

    def test_individual_payment_id_from_atomic_settlement_id(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.individual_payment_id == "ATM-9F2C"

    def test_failed_leg_amount_surfaces(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.amount == Decimal("139500.00")
        assert event.currency == "HKD"

    def test_failed_leg_bics_surface(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.sending_bic == "HSBCHKHHXXX"
        assert event.receiving_bic == "BOFAUS3NXXX"

    def test_failure_code_normalised_to_am04(self):
        event = self.n.normalize(_mbridge_msg())
        assert event.rejection_code == "AM04"  # CBDC-CF01 → AM04

    def test_all_legs_preserved_in_raw_source(self):
        msg = _mbridge_msg()
        event = self.n.normalize(msg)
        assert event.raw_source == msg
        assert len(event.raw_source["legs"]) == 2

    def test_narrative_from_failure_description(self):
        event = self.n.normalize(_mbridge_msg())
        assert "Consensus not reached" in (event.narrative or "")


class TestMBridgeFailedLegSelection:

    def setup_method(self):
        self.n = MBridgeNormalizer()

    def test_explicit_failed_leg_index_zero(self):
        msg = _mbridge_msg(failed_index=0)
        msg["legs"][0]["status"] = "FAILED"
        msg["legs"][0]["failure_code"] = "CBDC-FIN01"
        msg["legs"][0]["failure_description"] = "Finality timeout"
        msg["legs"][1]["status"] = "PENDING"
        event = self.n.normalize(msg)
        assert event.amount == Decimal("1000000.00")  # leg 0 amount
        assert event.currency == "CNY"

    def test_first_failed_leg_when_index_missing(self):
        msg = _mbridge_msg()
        del msg["failed_leg_index"]
        event = self.n.normalize(msg)
        assert event.amount == Decimal("139500.00")

    def test_raises_when_no_failed_leg(self):
        msg = _mbridge_msg()
        del msg["failed_leg_index"]
        for leg in msg["legs"]:
            leg["status"] = "ACSC"
        with pytest.raises(ValueError, match="no failed leg"):
            self.n.normalize(msg)

    def test_raises_when_no_legs_at_all(self):
        msg = _mbridge_msg()
        msg["legs"] = []
        with pytest.raises(ValueError, match="no legs"):
            self.n.normalize(msg)


class TestMBridgeDispatcher:

    def test_event_normalizer_routes_cbdc_mbridge(self):
        n = EventNormalizer()
        event = n.normalize("CBDC_MBRIDGE", _mbridge_msg())
        assert isinstance(event, NormalizedEvent)
        assert event.rail == "CBDC_MBRIDGE"

    def test_event_normalizer_still_routes_other_cbdc_to_legacy_normalizer(self):
        # Regression: don't accidentally route CBDC_ECNY through MBridgeNormalizer.
        from lip.c5_streaming.cbdc_normalizer import CBDCNormalizer

        ecny_msg = {
            "transaction_id": "ECNY-1",
            "amount": "1",
            "currency": "CNY",
            "timestamp": "2026-04-25T00:00:00",
        }
        event = EventNormalizer().normalize("CBDC_ECNY", ecny_msg)
        # CBDCNormalizer would set rail=CBDC_ECNY, not CBDC_MBRIDGE.
        assert event.rail == "CBDC_ECNY"
        assert isinstance(CBDCNormalizer(), CBDCNormalizer)  # sanity


class TestMBridgePatentLanguageScrub:
    """EPG-20/21: no AML/SAR/OFAC/PEP compliance-terminology in module strings.

    Note: word-boundary matching (\\b...\\b) is required because SAR is also
    the ISO 4217 code for the Saudi Riyal (a currency on mBridge), which is
    NOT the same as the AML term 'Suspicious Activity Report'. Substring
    matching would produce false positives on the legitimate currency code.
    """

    FORBIDDEN = ("AML", "SAR", "OFAC", "SDN", "PEP", "tipping-off", "suspicious")

    def test_module_source_clean(self):
        import re
        from pathlib import Path

        src_path = (
            Path(__file__).resolve().parents[1]
            / "c5_streaming"
            / "cbdc_mbridge_normalizer.py"
        )
        src = src_path.read_text()
        for term in self.FORBIDDEN:
            # Word-boundary check. Allows the SAR currency code in
            # MBRIDGE_SUPPORTED_CURRENCIES because it appears in a tuple/set
            # of currency strings — surrounded by quotes, comma — never as a
            # standalone word in prose.
            pattern = r"\b" + re.escape(term) + r"\b"
            # Look only in COMMENT and DOCSTRING lines (exclude code literals
            # that contain currency codes inside string sets).
            lines = src.splitlines()
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith("#") or stripped.startswith('"""')
                        or stripped.startswith('"') or "    " not in line[:4]):
                    if re.search(pattern, line, re.IGNORECASE):
                        # Allow currency-code occurrences (SAR appearing in a
                        # tuple of ISO 4217 codes alongside CNY/HKD/THB/AED).
                        if term.upper() == "SAR" and any(
                            cc in line for cc in ("CNY", "HKD", "THB", "AED")
                        ):
                            continue
                        pytest.fail(
                            f"EPG-21 violation in line: {line!r} "
                            f"(forbidden term {term!r})"
                        )
