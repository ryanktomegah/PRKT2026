"""
test_gap_stress_detector.py — Verification of Corridor Stress Regime Detection.

Validates that:
  1. StressRegimeDetector accurately tracks rates.
  2. Spiking failures above multiplier triggers is_stressed.
  3. ExecutionAgent correctly triggers human review on stressed corridors.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c5_streaming.stress_regime_detector import StressRegimeDetector
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.common.borrower_registry import BorrowerRegistry
from lip.pipeline import LIPPipeline


class MockTime:
    def __init__(self, start_time: float = 1000.0):
        self.time = start_time
    def __call__(self):
        return self.time
    def advance(self, seconds: float):
        self.time += seconds

def test_stress_detector_logic():
    # baseline 10s, current 2s, multiplier 2.0, min 5 txns
    m_time = MockTime()
    detector = StressRegimeDetector(10, 2, 2.0, 5, time_func=m_time)
    corridor = "EUR_USD"

    # 1. Establish baseline of 10% failure (2/20)
    # Total baseline events = 20 (min_txns = 5)
    for _ in range(18):
        detector.record_event(corridor, False)
        m_time.advance(0.1)
    for _ in range(2):
        detector.record_event(corridor, True)
        m_time.advance(0.1)

    # Move time forward so current window is distinct from baseline
    m_time.advance(5.0)

    # Not stressed yet (not enough 1h/2s txns in current window)
    assert not detector.is_stressed(corridor)

    # 2. Spike failures in current window (e.g. 6/10 = 60%)
    for _ in range(4):
        detector.record_event(corridor, False)
        m_time.advance(0.1)
    for _ in range(6):
        detector.record_event(corridor, True)
        m_time.advance(0.1)

    # Baseline rate = 2/20 = 0.1
    # Current rate = 6/10 = 0.6
    # 0.6 > 0.1 * 2.0 (0.2) -> Stressed
    assert detector.is_stressed(corridor)

def test_agent_triggers_review_on_stress():
    detector = MagicMock(is_stressed=MagicMock(return_value=True))
    human_override = MagicMock()

    registry = BorrowerRegistry()
    registry.enroll("BORROWER")

    agent = ExecutionAgent(
        kill_switch=MagicMock(should_halt_new_offers=MagicMock(return_value=False)),
        decision_logger=MagicMock(),
        human_override=human_override,
        degraded_mode_manager=MagicMock(should_halt_new_offers=MagicMock(return_value=False), get_state_dict=MagicMock(return_value={"degraded_mode": False, "gpu_fallback": False, "kms_unavailable_gap": False})),
        stress_detector=detector,
        config=ExecutionConfig(borrower_registry=registry)
    )

    # Low PD (0.05) would normally NOT trigger human review (threshold 0.20)
    ctx = {
        "uetr": "uetr-1",
        "sending_bic": "BORROWER",
        "failure_probability": 0.5,
        "pd_score": 0.05,
        "corridor": "EUR_USD",
        "loan_amount": 1000,
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True
    }

    res = agent.process_payment(ctx)

    assert res["status"] == "PENDING_HUMAN_REVIEW"
    # Verify the reason mentions stress
    call_args = human_override.request_override.call_args
    assert "STRESS_REGIME" in call_args.kwargs["reason"]

def test_pipeline_integration_with_stress():
    detector = StressRegimeDetector(100, 100, 2.0, 1)

    registry = BorrowerRegistry()
    registry.enroll("SENDER")

    agent = ExecutionAgent(
        kill_switch=MagicMock(should_halt_new_offers=MagicMock(return_value=False)),
        decision_logger=MagicMock(),
        human_override=MagicMock(request_override=MagicMock(return_value=MagicMock(request_id="req-123"))),
        degraded_mode_manager=MagicMock(should_halt_new_offers=MagicMock(return_value=False), get_state_dict=MagicMock(return_value={"degraded_mode": False, "gpu_fallback": False, "kms_unavailable_gap": False})),
        stress_detector=detector,
        config=ExecutionConfig(borrower_registry=registry)
    )

    pipeline = LIPPipeline(
        c1_engine=MagicMock(return_value={"failure_probability": 0.2, "above_threshold": True}),
        c2_engine=MagicMock(return_value={"pd_score": 0.05, "fee_bps": 300}),
        c4_classifier=MagicMock(classify=MagicMock(return_value={"dispute_class": "NOT_DISPUTE"})),
        c6_checker=MagicMock(check=MagicMock(return_value=MagicMock(passed=True))),
        c7_agent=agent,
        stress_detector=detector
    )

    event = NormalizedEvent(
        uetr="uetr-stress",
        individual_payment_id="pmt-1",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=Decimal("1000"),
        currency="EUR",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="MS03",
        narrative="Test"
    )

    # 1. First event establishes some baseline (failure)
    pipeline.process(event)
    curr, base = detector.get_rates("EUR_USD")
    assert base > 0

    # 2. Mocking a stress condition is easier by directly recording to detector
    # but let's just verify the 'outcome' is being recorded.
    assert len(detector._history["EUR_USD"]) == 1
