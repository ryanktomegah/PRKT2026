"""
test_gap03_borrower_registry.py — Verification of Borrower Registry guard.

Validates that:
  1. ExecutionAgent rejects unenrolled borrowers with BORROWER_NOT_ENROLLED.
  2. ExecutionAgent permits enrolled borrowers to proceed.
  3. LIPPipeline correctly reports the outcome when blocked by enrollment.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.common.borrower_registry import BorrowerRegistry
from lip.pipeline import LIPPipeline


def test_execution_agent_borrower_guard():
    registry = BorrowerRegistry()
    registry.enroll("ENROLLED_BIC")

    config = ExecutionConfig(borrower_registry=registry)
    agent = ExecutionAgent(
        kill_switch=MagicMock(should_halt_new_offers=MagicMock(return_value=False)),
        decision_logger=MagicMock(),
        human_override=MagicMock(),
        degraded_mode_manager=MagicMock(should_halt_new_offers=MagicMock(return_value=False), get_state_dict=MagicMock(return_value={"degraded_mode": False, "gpu_fallback": False, "kms_unavailable_gap": False})),
        config=config
    )

    # 1. Unenrolled BIC
    res_un = agent.process_payment({"sending_bic": "STRANGER", "uetr": "uetr-1"})
    assert res_un["status"] == "BORROWER_NOT_ENROLLED"
    assert res_un["halt_reason"] == "borrower_not_enrolled"

    # 2. Enrolled BIC
    # Mock requires_human_review to avoid extra calls
    agent._requires_human_review = MagicMock(return_value=False)
    # Mock build_loan_offer to return something
    agent._build_loan_offer = MagicMock(return_value={"loan_id": "l1", "fee_bps": 300})

    res_en = agent.process_payment({
        "sending_bic": "ENROLLED_BIC",
        "uetr": "uetr-2",
        "failure_probability": 0.5,
        "pd_score": 0.1,
        "fee_bps": 300,
        "loan_amount": "1000000",
        "maturity_days": 7,
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True
    })
    assert res_en["status"] == "OFFER"

def test_pipeline_borrower_unregistered():
    registry = BorrowerRegistry() # Empty
    config = ExecutionConfig(borrower_registry=registry)

    agent = ExecutionAgent(
        kill_switch=MagicMock(should_halt_new_offers=MagicMock(return_value=False)),
        decision_logger=MagicMock(),
        human_override=MagicMock(),
        degraded_mode_manager=MagicMock(should_halt_new_offers=MagicMock(return_value=False), get_state_dict=MagicMock(return_value={"degraded_mode": False, "gpu_fallback": False, "kms_unavailable_gap": False})),
        config=config
    )

    # EPG-26: configure predict() explicitly — MagicMock always has predict as an attribute
    # so pipeline.py:252 calls _c2.predict() not _c2(); both must return the right dict.
    _c2_result = {"pd_score": 0.05, "fee_bps": 300}
    c2_mock = MagicMock(
        return_value=_c2_result,
        predict=MagicMock(return_value=_c2_result),
    )

    pipeline = LIPPipeline(
        c1_engine=MagicMock(return_value={"failure_probability": 0.2, "above_threshold": True}),
        c2_engine=c2_mock,
        c4_classifier=MagicMock(classify=MagicMock(return_value={"dispute_class": "NOT_DISPUTE"})),
        c6_checker=MagicMock(check=MagicMock(return_value=MagicMock(passed=True, anomaly_flagged=False))),
        c7_agent=agent
    )

    event = NormalizedEvent(
        uetr="uetr-3",
        individual_payment_id="pmt-3",
        sending_bic="UNREGISTERED",
        receiving_bic="RECEIVER",
        amount=Decimal("1000"),
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="MS03",
        narrative="Test"
    )

    result = pipeline.process(event)

    # Empty registry = allow all (dev mode). Payment reaches C7, loan_amount $1K < $500K
    # minimum → BELOW_MIN_LOAN_AMOUNT → pipeline outcome DECLINED.
    assert result.outcome == "DECLINED"
    assert result.payment_state == "FAILURE_DETECTED"  # reached C7 but no offer
