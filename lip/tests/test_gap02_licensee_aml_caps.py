"""
test_gap02_licensee_aml_caps.py — Verification of licensee-specific AML caps.

Validates that:
  1. LicenseeContext caps are correctly loaded into ExecutionAgent.
  2. VelocityChecker.check() respects overrides passed from ExecutionAgent.
  3. LIPPipeline.process() correctly records transactions using overrides.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent
from lip.c8_license_manager.license_token import LicenseeContext
from lip.pipeline import LIPPipeline


def test_execution_agent_init_from_context():
    ctx = LicenseeContext(
        licensee_id="TEST_BANK",
        max_tps=50,
        aml_dollar_cap_usd=500000,
        aml_count_cap=10,
        permitted_components=["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
        token_expiry="2026-12-31"
    )

    agent = ExecutionAgent(
        kill_switch=MagicMock(),
        decision_logger=MagicMock(),
        human_override=MagicMock(),
        degraded_mode_manager=MagicMock(),
        licensee_context=ctx
    )

    assert agent.licensee_id == "TEST_BANK"
    assert agent.max_tps == 50
    assert agent.aml_dollar_cap_usd == 500000
    assert agent.aml_count_cap == 10

def test_pipeline_respects_licensee_caps():
    # 1. Setup checker with low caps
    checker = VelocityChecker(salt=b"test-salt")

    # 2. Setup Agent with very low caps (e.g. $100)
    ctx = LicenseeContext(
        licensee_id="TEST_BANK",
        max_tps=50,
        aml_dollar_cap_usd=100,
        aml_count_cap=5,
        permitted_components=["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
        token_expiry="2026-12-31"
    )
    agent = ExecutionAgent(
        kill_switch=MagicMock(),
        decision_logger=MagicMock(),
        human_override=MagicMock(),
        degraded_mode_manager=MagicMock(),
        licensee_context=ctx
    )

    # 3. Setup Pipeline
    pipeline = LIPPipeline(
        c1_engine=MagicMock(return_value={"failure_probability": 0.2, "above_threshold": True}),
        c2_engine=MagicMock(return_value={"pd_score": 0.05, "fee_bps": 300}),
        c4_classifier=MagicMock(classify=MagicMock(return_value={"dispute_class": "NOT_DISPUTE"})),
        c6_checker=checker,
        c7_agent=agent
    )

    event = NormalizedEvent(
        uetr="uetr-1",
        individual_payment_id="pmt-1",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=Decimal("150"), # Exceeds $100 cap
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="MS03",
        narrative="Test"
    )

    result = pipeline.process(event)

    assert result.outcome == "AML_BLOCKED"
    assert not result.aml_passed

    # 4. Test with amount within cap
    event_ok = NormalizedEvent(
        uetr="uetr-2",
        individual_payment_id="pmt-2",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=Decimal("50"), # Within $100 cap
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="MS03",
        narrative="Test"
    )

    # Mock C7 to succeed
    agent.process_payment = MagicMock(return_value={
        "status": "OFFER",
        "loan_offer": {"loan_id": "loan-1", "fee_bps": 300},
        "decision_entry_id": "entry-1"
    })

    result_ok = pipeline.process(event_ok)
    assert result_ok.outcome == "FUNDED"
    assert result_ok.aml_passed

    # 5. Verify it was recorded (subsequent $60 payment should fail now as 50 + 60 > 100)
    event_fail = NormalizedEvent(
        uetr="uetr-3",
        individual_payment_id="pmt-3",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=Decimal("60"),
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="MS03",
        narrative="Test"
    )

    result_fail = pipeline.process(event_fail)
    assert result_fail.outcome == "AML_BLOCKED"
