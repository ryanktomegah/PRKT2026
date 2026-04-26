"""
test_cbdc_normalizer.py — CBDC rail normalizer tests (P5 patent).

Covers:
  - Per-rail normalization for e-CNY, e-EUR, Sand Dollar
  - CBDC failure code → ISO 20022 mapping
  - Dispatcher routing CBDC_* rails from EventNormalizer
  - RAIL_MATURITY_HOURS lookup (legacy + CBDC)
  - Unknown-rail fail-closed semantics (ValueError, not silent default)
  - EPG-20/21: no AML/SAR/OFAC/PEP language leaked through narrative fields
"""
import unittest
from datetime import datetime
from decimal import Decimal

import pytest

from lip.c5_streaming.cbdc_normalizer import (
    CBDC_FAILURE_CODE_MAP,
    CBDCNormalizer,
    get_rail_maturity_hours,
    normalize_cbdc_failure_code,
)
from lip.c5_streaming.event_normalizer import EventNormalizer, NormalizedEvent
from lip.common.constants import RAIL_MATURITY_HOURS, UETR_TTL_BUFFER_DAYS

# ---------------------------------------------------------------------------
# e-CNY (PBoC)
# ---------------------------------------------------------------------------

class TestNormalizeECNY(unittest.TestCase):

    def _msg(self, **overrides) -> dict:
        base = {
            "transaction_id": "ECNY-TX-001",
            "payment_reference": "PAYREF-001",
            "wallet_id_sender": "WALLET-SND-001",
            "wallet_id_receiver": "WALLET-RCV-001",
            "institution_bic_sender": "ICBKCNBJXXX",
            "institution_bic_receiver": "BOFAUS3NXXX",
            "amount": "50000.00",
            "currency": "CNY",
            "timestamp": "2026-04-10T09:15:00",
            "failure_code": "CBDC-LIQ01",
            "failure_description": "Liquidity pool below threshold",
        }
        base.update(overrides)
        return base

    def setUp(self):
        self.n = CBDCNormalizer()

    def test_rail_is_cbdc_ecny(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertEqual(event.rail, "CBDC_ECNY")

    def test_uetr_from_transaction_id(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertEqual(event.uetr, "ECNY-TX-001")

    def test_amount_parsed_as_decimal(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertIsInstance(event.amount, Decimal)
        self.assertEqual(event.amount, Decimal("50000.00"))

    def test_currency_defaults_to_cny(self):
        msg = self._msg()
        msg.pop("currency")
        event = self.n.normalize_ecny(msg)
        self.assertEqual(event.currency, "CNY")

    def test_sending_bic_prefers_institution_over_wallet(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertEqual(event.sending_bic, "ICBKCNBJXXX")

    def test_sending_bic_falls_back_to_wallet_when_missing(self):
        msg = self._msg()
        msg.pop("institution_bic_sender")
        event = self.n.normalize_ecny(msg)
        self.assertEqual(event.sending_bic, "WALLET-SND-001")

    def test_rejection_code_mapped_to_iso(self):
        event = self.n.normalize_ecny(self._msg())
        # CBDC-LIQ01 → AM04 (InsufficientFunds)
        self.assertEqual(event.rejection_code, "AM04")

    def test_narrative_preserved(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertEqual(event.narrative, "Liquidity pool below threshold")

    def test_timestamp_parsed(self):
        event = self.n.normalize_ecny(self._msg())
        self.assertIsInstance(event.timestamp, datetime)

    def test_raw_source_preserved(self):
        msg = self._msg()
        event = self.n.normalize_ecny(msg)
        self.assertEqual(event.raw_source, msg)


# ---------------------------------------------------------------------------
# e-EUR (ECB experimental)
# ---------------------------------------------------------------------------

class TestNormalizeEEUR(unittest.TestCase):

    def _msg(self, **overrides) -> dict:
        base = {
            "tx_hash": "0xabc123deadbeef",
            "end_to_end_id": "E2E-EEUR-001",
            "sender_iban": "DE89370400440532013000",
            "receiver_iban": "FR1420041010050500013M02606",
            "sender_bic": "DEUTDEFFXXX",
            "receiver_bic": "BNPAFRPPXXX",
            "amount": "25000.00",
            "currency": "EUR",
            "created_at": "2026-04-10T11:00:00",
            "error_code": "CBDC-FIN01",
            "error_message": "Finality window exceeded",
        }
        base.update(overrides)
        return base

    def setUp(self):
        self.n = CBDCNormalizer()

    def test_rail_is_cbdc_eeur(self):
        event = self.n.normalize_eeur(self._msg())
        self.assertEqual(event.rail, "CBDC_EEUR")

    def test_uetr_from_tx_hash(self):
        event = self.n.normalize_eeur(self._msg())
        self.assertEqual(event.uetr, "0xabc123deadbeef")

    def test_rejection_code_mapped(self):
        event = self.n.normalize_eeur(self._msg())
        # CBDC-FIN01 → TM01
        self.assertEqual(event.rejection_code, "TM01")

    def test_currency_eur(self):
        event = self.n.normalize_eeur(self._msg())
        self.assertEqual(event.currency, "EUR")

    def test_narrative_from_error_message(self):
        event = self.n.normalize_eeur(self._msg())
        self.assertEqual(event.narrative, "Finality window exceeded")


# ---------------------------------------------------------------------------
# Sand Dollar (CBB)
# ---------------------------------------------------------------------------

class TestNormalizeSandDollar(unittest.TestCase):

    def _msg(self, **overrides) -> dict:
        base = {
            "reference_id": "SD-REF-001",
            "payment_id": "SD-PAY-001",
            "sender_wallet": "SD-WALLET-SND",
            "receiver_wallet": "SD-WALLET-RCV",
            "sender_institution_bic": "CBBAASNXXXX",
            "receiver_institution_bic": "BOFAUS3NXXX",
            "amount": "500.00",
            "currency": "BSD",
            "event_time": "2026-04-10T14:22:00",
            "status_code": "CBDC-SC01",
            "status_message": "Smart contract execution failure",
        }
        base.update(overrides)
        return base

    def setUp(self):
        self.n = CBDCNormalizer()

    def test_rail_is_cbdc_sand_dollar(self):
        event = self.n.normalize_sand_dollar(self._msg())
        self.assertEqual(event.rail, "CBDC_SAND_DOLLAR")

    def test_uetr_from_reference_id(self):
        event = self.n.normalize_sand_dollar(self._msg())
        self.assertEqual(event.uetr, "SD-REF-001")

    def test_rejection_code_mapped(self):
        event = self.n.normalize_sand_dollar(self._msg())
        # CBDC-SC01 → AC01
        self.assertEqual(event.rejection_code, "AC01")

    def test_currency_bsd(self):
        event = self.n.normalize_sand_dollar(self._msg())
        self.assertEqual(event.currency, "BSD")


# ---------------------------------------------------------------------------
# Failure code mapping
# ---------------------------------------------------------------------------

class TestFailureCodeMapping(unittest.TestCase):

    def test_known_codes_map_to_iso(self):
        assert normalize_cbdc_failure_code("CBDC-SC01") == "AC01"
        assert normalize_cbdc_failure_code("CBDC-KYC01") == "RR01"
        assert normalize_cbdc_failure_code("CBDC-LIQ01") == "AM04"
        assert normalize_cbdc_failure_code("CBDC-FIN01") == "TM01"
        assert normalize_cbdc_failure_code("CBDC-CRY01") == "DS02"
        assert normalize_cbdc_failure_code("CBDC-NET01") == "MS03"

    def test_code_normalization_case_and_whitespace(self):
        assert normalize_cbdc_failure_code("  cbdc-sc01  ") == "AC01"

    def test_none_input_returns_none(self):
        assert normalize_cbdc_failure_code(None) is None
        assert normalize_cbdc_failure_code("") is None

    def test_unknown_code_passes_through_for_fail_closed(self):
        # Per the module docstring: unknown codes pass through with a warning
        # so downstream taxonomy applies its BLOCK default (fail-closed).
        assert normalize_cbdc_failure_code("CBDC-UNKNOWN-99") == "CBDC-UNKNOWN-99"

    def test_kyc_code_maps_to_generic_rr01_not_compliance_term(self):
        """EPG-20/21: KYC failures map to the generic MissingDebtorAccount code,
        not an AML/SAR-tagged value. RR01 is the correct ISO 20022 equivalent."""
        assert CBDC_FAILURE_CODE_MAP["CBDC-KYC01"] == "RR01"
        assert CBDC_FAILURE_CODE_MAP["CBDC-KYC02"] == "RR02"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class TestCBDCDispatcher(unittest.TestCase):

    def test_normalize_routes_ecny(self):
        n = CBDCNormalizer()
        event = n.normalize("CBDC_ECNY", {
            "transaction_id": "T1", "amount": "1", "currency": "CNY",
            "timestamp": "2026-04-10T00:00:00",
        })
        self.assertEqual(event.rail, "CBDC_ECNY")

    def test_normalize_routes_eeur(self):
        n = CBDCNormalizer()
        event = n.normalize("CBDC_EEUR", {
            "tx_hash": "0x1", "amount": "1", "currency": "EUR",
            "created_at": "2026-04-10T00:00:00",
        })
        self.assertEqual(event.rail, "CBDC_EEUR")

    def test_normalize_routes_sand_dollar(self):
        n = CBDCNormalizer()
        event = n.normalize("CBDC_SAND_DOLLAR", {
            "reference_id": "R1", "amount": "1", "currency": "BSD",
            "event_time": "2026-04-10T00:00:00",
        })
        self.assertEqual(event.rail, "CBDC_SAND_DOLLAR")

    def test_normalize_rejects_unknown_rail(self):
        with pytest.raises(ValueError, match="Unknown CBDC rail"):
            CBDCNormalizer().normalize("CBDC_RUBLE", {})

    def test_event_normalizer_dispatches_cbdc_to_cbdc_normalizer(self):
        """EventNormalizer.normalize() must route CBDC_* rails to CBDCNormalizer
        without additional branching in the legacy handler block."""
        n = EventNormalizer()
        event = n.normalize("CBDC_ECNY", {
            "transaction_id": "TX-DISPATCH-001",
            "amount": "100", "currency": "CNY",
            "timestamp": "2026-04-10T00:00:00",
            "failure_code": "CBDC-LIQ01",
        })
        self.assertIsInstance(event, NormalizedEvent)
        self.assertEqual(event.rail, "CBDC_ECNY")
        self.assertEqual(event.rejection_code, "AM04")

    def test_event_normalizer_rejects_unknown_rail(self):
        with pytest.raises(ValueError, match="Unknown rail"):
            EventNormalizer().normalize("VISA_DIRECT", {})


# ---------------------------------------------------------------------------
# Maturity lookup
# ---------------------------------------------------------------------------

class TestRailMaturity(unittest.TestCase):

    def test_cbdc_rails_four_hours(self):
        assert RAIL_MATURITY_HOURS["CBDC_ECNY"] == 4.0
        assert RAIL_MATURITY_HOURS["CBDC_EEUR"] == 4.0
        assert RAIL_MATURITY_HOURS["CBDC_SAND_DOLLAR"] == 4.0

    def test_swift_and_sepa_match_uetr_ttl(self):
        expected = float(UETR_TTL_BUFFER_DAYS * 24)
        assert RAIL_MATURITY_HOURS["SWIFT"] == expected
        assert RAIL_MATURITY_HOURS["SEPA"] == expected

    def test_domestic_instant_rails_same_day(self):
        assert RAIL_MATURITY_HOURS["FEDNOW"] == 24.0
        assert RAIL_MATURITY_HOURS["RTP"] == 24.0

    def test_get_rail_maturity_hours_is_case_insensitive(self):
        assert get_rail_maturity_hours("cbdc_ecny") == 4.0
        assert get_rail_maturity_hours("  SWIFT  ") == float(UETR_TTL_BUFFER_DAYS * 24)

    def test_get_rail_maturity_hours_rejects_unknown_rail(self):
        """Unknown rails must raise ValueError, never silently default
        (otherwise a typo in corridor config would quietly use the wrong window)."""
        with pytest.raises(ValueError, match="Unknown rail"):
            get_rail_maturity_hours("CBDC_UNKNOWN")


# ---------------------------------------------------------------------------
# EPG-20/21 patent language scrub
# ---------------------------------------------------------------------------

class TestMBridgeFailureCodes(unittest.TestCase):
    """Phase B groundwork: consensus + cross-chain bridge failure codes."""

    def test_cf01_maps_to_am04_settlement_failed(self):
        # Consensus not reached -> closest ISO 20022 analog is AM04
        # (settlement-amount problem / liquidity at the network level).
        assert normalize_cbdc_failure_code("CBDC-CF01") == "AM04"

    def test_cb01_maps_to_ff01_protocol_mismatch(self):
        # Cross-chain bridge failure between mBridge participating ledgers.
        assert normalize_cbdc_failure_code("CBDC-CB01") == "FF01"


class TestPatentLanguageScrub(unittest.TestCase):
    """Verify no AML/SAR/OFAC/PEP terms leaked into module-level strings.

    The CBDC normalizer is part of the P5 patent family; its source and
    the code/description dict values must not contain compliance-investigation
    language per EPG-21."""

    FORBIDDEN_TERMS = ("AML", "SAR", "OFAC", "SDN", "PEP", "tipping-off", "suspicious")

    def test_failure_code_map_values_clean(self):
        for term in self.FORBIDDEN_TERMS:
            for mapped in CBDC_FAILURE_CODE_MAP.values():
                assert term.upper() not in mapped.upper(), (
                    f"EPG-21 violation: mapping contains {term!r}"
                )
