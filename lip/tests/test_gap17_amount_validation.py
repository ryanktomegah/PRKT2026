"""
test_gap17_amount_validation.py — Integration tests for GAP-17:
Disbursement amount anchored to original payment amount.
"""
from decimal import Decimal

import pytest

from lip.c5_streaming.event_normalizer import EventNormalizer
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"
_TEST_UETR = "660e8400-e29b-41d4-a716-446655441111"


@pytest.fixture
def agent():
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=DecisionLogger(hmac_key=_HMAC_KEY),
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
    )


def _make_context(loan_amount: str, original_amount: str) -> dict:
    """Build a minimal payment_context with explicit loan and original amounts."""
    return {
        "uetr": _TEST_UETR,
        "individual_payment_id": "pid-17",
        "sending_bic": "TESTBIC1",
        "failure_probability": 0.9,
        "pd_score": 0.05,
        "fee_bps": 300,
        "loan_amount": loan_amount,
        "original_payment_amount_usd": original_amount,
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True,
        "maturity_days": 7,
    }


class TestGap17AmountValidation:
    def test_exact_match_produces_offer(self, agent):
        """loan_amount == original_payment_amount_usd → OFFER."""
        ctx = _make_context("5000000.00", "5000000.00")
        result = agent.process_payment(ctx)
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["loan_amount"] == "5000000.00"

    def test_within_tolerance_produces_offer(self, agent):
        """Difference ≤ $0.01 (FX rounding) → OFFER."""
        ctx = _make_context("5000000.00", "5000000.009")
        result = agent.process_payment(ctx)
        assert result["status"] == "OFFER"

    def test_mismatch_beyond_tolerance_returns_loan_amount_mismatch(self, agent):
        """Difference > $0.01 → LOAN_AMOUNT_MISMATCH, no loan offer issued."""
        ctx = _make_context("4900000.00", "5000000.00")
        result = agent.process_payment(ctx)
        assert result["status"] == "LOAN_AMOUNT_MISMATCH"
        assert result["loan_offer"] is None
        assert result["halt_reason"] == "loan_amount_mismatch"

    def test_mismatch_logged_in_decision_log(self, agent):
        """LOAN_AMOUNT_MISMATCH must produce a decision log entry."""
        ctx = _make_context("1000.00", "5000000.00")
        result = agent.process_payment(ctx)
        assert result["status"] == "LOAN_AMOUNT_MISMATCH"
        entry_id = result["decision_entry_id"]
        assert entry_id is not None
        entry = agent.decision_logger.get(entry_id)
        assert entry.decision_type == "LOAN_AMOUNT_MISMATCH"

    def test_normalized_event_swift_populates_original_amount(self):
        """SWIFT normalizer reads IntrBkSttlmAmt into original_payment_amount_usd."""
        msg = {
            "GrpHdr": {"MsgId": _TEST_UETR, "CreDtTm": "2026-03-14T10:00:00"},
            "TxInfAndSts": {
                "OrgnlEndToEndId": "pid-test",
                "StsRsnInf": {"Rsn": {"Cd": "CURR"}},
                "OrgnlTxRef": {
                    "Amt": {"InstdAmt": {"value": "4900000.00", "Ccy": "EUR"}}
                },
            },
            "DbtrAgt": {"FinInstnId": {"BIC": "SNDRBIC1"}},
            "IntrBkSttlmAmt": {"value": "5000000.00", "Ccy": "USD"},
        }
        event = EventNormalizer().normalize_swift(msg)
        assert event.original_payment_amount_usd == Decimal("5000000.00")
        # The instructed amount (EUR) is distinct from settlement amount (USD)
        assert event.amount == Decimal("4900000.00")

    def test_normalized_event_without_settlement_field_is_none(self):
        """When IntrBkSttlmAmt is absent, original_payment_amount_usd is None."""
        msg = {
            "GrpHdr": {"MsgId": _TEST_UETR, "CreDtTm": "2026-03-14T10:00:00"},
            "TxInfAndSts": {
                "OrgnlEndToEndId": "pid-test",
                "StsRsnInf": {},
                "OrgnlTxRef": {
                    "Amt": {"InstdAmt": {"value": "10000.00", "Ccy": "USD"}}
                },
            },
        }
        event = EventNormalizer().normalize_swift(msg)
        assert event.original_payment_amount_usd is None
