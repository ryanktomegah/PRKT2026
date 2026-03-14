"""
test_gap06_swift_disbursement.py — Integration tests for GAP-06:
SWIFT pacs.008 message spec for bridge disbursements.
"""
from decimal import Decimal

import pytest

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.swift_disbursement import build_disbursement_message

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"
_TEST_UETR = "550e8400-e29b-41d4-a716-446655440000"
_TEST_LOAN_ID = "loan-abc-123"


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


def _offer_context(loan_amount: str = "10000.00", original_amount: str = "10000.00") -> dict:
    """Minimal payment_context that passes all guards and reaches _build_loan_offer."""
    return {
        "uetr": _TEST_UETR,
        "individual_payment_id": "pid-1",
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


class TestGap06SwiftDisbursement:
    def test_end_to_end_id_format(self):
        """end_to_end_id must be 'LIP-BRIDGE-{original_uetr}'."""
        msg = build_disbursement_message(_TEST_UETR, _TEST_LOAN_ID, Decimal("10000"))
        assert msg.end_to_end_id == f"LIP-BRIDGE-{_TEST_UETR}"

    def test_remittance_info_contains_uetr_and_loan_id(self):
        """remittance_info must reference both original UETR and loan ID."""
        msg = build_disbursement_message(_TEST_UETR, _TEST_LOAN_ID, Decimal("5000000"))
        assert _TEST_UETR in msg.remittance_info
        assert _TEST_LOAN_ID in msg.remittance_info

    def test_message_is_immutable(self):
        """BridgeDisbursementMessage is frozen — fields cannot be mutated."""
        msg = build_disbursement_message(_TEST_UETR, _TEST_LOAN_ID, Decimal("1000"))
        with pytest.raises((AttributeError, TypeError)):
            msg.end_to_end_id = "tampered"  # type: ignore[misc]

    def test_offer_dict_contains_swift_fields(self, agent):
        """C7 loan offer must include swift_disbursement_ref and swift_remittance_info."""
        ctx = _offer_context()
        result = agent.process_payment(ctx)

        assert result["status"] == "OFFER"
        offer = result["loan_offer"]
        assert "swift_disbursement_ref" in offer
        assert "swift_remittance_info" in offer
        assert offer["swift_disbursement_ref"].startswith("LIP-BRIDGE-")
        assert _TEST_UETR in offer["swift_disbursement_ref"]

    def test_swift_ref_links_back_to_original_uetr(self, agent):
        """The SWIFT disbursement ref must embed the original payment UETR."""
        ctx = _offer_context()
        result = agent.process_payment(ctx)

        assert result["status"] == "OFFER"
        offer = result["loan_offer"]
        assert offer["swift_disbursement_ref"] == f"LIP-BRIDGE-{_TEST_UETR}"
        assert _TEST_UETR in offer["swift_remittance_info"]
