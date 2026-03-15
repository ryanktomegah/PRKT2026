"""
test_gap10_governing_law.py — Tests for GAP-10:
Governing-law / jurisdiction field on LoanOffer.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.business_calendar import currency_to_jurisdiction
from lip.common.governing_law import law_for_jurisdiction
from lip.common.schemas import LoanOffer

_HMAC_KEY = b"test_hmac_key_gap10_governing_law"


def _make_agent(**kwargs):
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=DecisionLogger(hmac_key=_HMAC_KEY),
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
        **kwargs,
    )


def _make_context(currency: str = "USD") -> dict:
    return {
        "uetr": str(uuid.uuid4()),
        "individual_payment_id": "pid-gap10",
        "sending_bic": "TESTBIC1",
        "failure_probability": 0.9,
        "pd_score": 0.05,
        "fee_bps": 300,
        "loan_amount": "1000000.00",
        "original_payment_amount_usd": "1000000.00",
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True,
        "maturity_days": 7,
        "currency": currency,
    }


def _make_loan_offer(**overrides) -> LoanOffer:
    """Build a valid LoanOffer Pydantic instance for schema validation tests."""
    defaults = dict(
        offer_id=uuid.uuid4(),
        uetr=uuid.uuid4(),
        mlo_entity_id="mlo-001",
        miplo_entity_id="miplo-001",
        elo_entity_id="elo-001",
        principal_usd=Decimal("1000000"),
        fee_bps=Decimal("300"),
        fee_amount_usd=Decimal("575.34"),
        maturity_days=7,
        rejection_code_class="B",
        offer_expiry=datetime.now(tz=timezone.utc) + timedelta(minutes=15),
        pd_score=0.05,
        created_at=datetime.now(tz=timezone.utc),
    )
    defaults.update(overrides)
    return LoanOffer(**defaults)


# ---------------------------------------------------------------------------
# 1–4: pure governing_law module tests
# ---------------------------------------------------------------------------

class TestGoverningLawMapping:
    def test_law_for_usd_is_new_york(self):
        """USD corridor → FEDWIRE jurisdiction → NEW_YORK governing law."""
        jurisdiction = currency_to_jurisdiction("USD")
        assert law_for_jurisdiction(jurisdiction) == "NEW_YORK"

    def test_law_for_eur_is_eu_luxembourg(self):
        """EUR corridor → TARGET2 jurisdiction → EU_LUXEMBOURG governing law."""
        jurisdiction = currency_to_jurisdiction("EUR")
        assert law_for_jurisdiction(jurisdiction) == "EU_LUXEMBOURG"

    def test_law_for_gbp_is_england_wales(self):
        """GBP corridor → CHAPS jurisdiction → ENGLAND_WALES governing law."""
        jurisdiction = currency_to_jurisdiction("GBP")
        assert law_for_jurisdiction(jurisdiction) == "ENGLAND_WALES"

    def test_law_for_unknown_jurisdiction_is_unknown(self):
        """Jurisdiction not in the mapping table returns 'UNKNOWN'."""
        assert law_for_jurisdiction("NONEXISTENT_JURISDICTION") == "UNKNOWN"


# ---------------------------------------------------------------------------
# 5–7: C7 ExecutionAgent produces governing_law in loan offer dict
# ---------------------------------------------------------------------------

class TestC7OfferGoverningLaw:
    def test_c7_offer_contains_governing_law_usd(self):
        """USD payment context → NEW_YORK governing law in offer dict."""
        agent = _make_agent()
        result = agent.process_payment(_make_context("USD"))
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["governing_law"] == "NEW_YORK"

    def test_c7_eur_corridor_governing_law(self):
        """EUR payment context → EU_LUXEMBOURG governing law."""
        agent = _make_agent()
        result = agent.process_payment(_make_context("EUR"))
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["governing_law"] == "EU_LUXEMBOURG"

    def test_c7_gbp_corridor_governing_law(self):
        """GBP payment context → ENGLAND_WALES governing law."""
        agent = _make_agent()
        result = agent.process_payment(_make_context("GBP"))
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["governing_law"] == "ENGLAND_WALES"


# ---------------------------------------------------------------------------
# 8–10: LoanOffer schema and loan_currency field
# ---------------------------------------------------------------------------

class TestLoanOfferSchemaGoverningLaw:
    def test_loan_offer_schema_accepts_governing_law(self):
        """LoanOffer schema validates when governing_law is explicitly set."""
        offer = _make_loan_offer(governing_law="NEW_YORK", loan_currency="USD")
        assert offer.governing_law == "NEW_YORK"
        assert offer.loan_currency == "USD"

    def test_loan_offer_schema_default_governing_law_is_unknown(self):
        """LoanOffer defaults governing_law to 'UNKNOWN' for backwards compat."""
        offer = _make_loan_offer()
        assert offer.governing_law == "UNKNOWN"

    def test_loan_offer_dict_contains_loan_currency(self):
        """C7 offer dict carries loan_currency matching the payment currency."""
        agent = _make_agent()
        result = agent.process_payment(_make_context("GBP"))
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["loan_currency"] == "GBP"
