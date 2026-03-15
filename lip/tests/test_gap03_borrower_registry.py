"""
test_gap03_borrower_registry.py — Integration tests for GAP-03: Enrolled borrower registry.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.pipeline import LIPPipeline

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"

@pytest.fixture
def execution_agent():
    ks = KillSwitch()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    ho = HumanOverrideInterface()
    dm = DegradedModeManager()
    cfg = ExecutionConfig(
        require_human_review_above_pd=0.99,
        enrolled_borrowers={"ENROLLED_BIC_1", "ENROLLED_BIC_2"}
    )
    return ExecutionAgent(ks, dl, ho, dm, cfg)

@pytest.fixture
def pipeline(execution_agent):
    c1 = MagicMock()
    c1.predict.return_value = {"failure_probability": 0.8, "above_threshold": True}
    c2 = MagicMock()
    c2.predict.return_value = {"pd_score": 0.05, "fee_bps": 300, "tier": 3}
    c4 = MagicMock()
    c4.classify.return_value = {"dispute_class": "NOT_DISPUTE"}
    c6 = MagicMock()
    c6.check.return_value = MagicMock(passed=True)

    return LIPPipeline(
        c1_engine=c1,
        c2_engine=c2,
        c4_classifier=c4,
        c6_checker=c6,
        c7_agent=execution_agent
    )

def _make_event(sending_bic: str):
    return NormalizedEvent(
        uetr="uetr-1",
        individual_payment_id="pid-1",
        sending_bic=sending_bic,
        receiving_bic="RECEIVER",
        amount=Decimal("10000"),
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="CURR",
        narrative=None,
        raw_source={}
    )

class TestGap03BorrowerRegistry:
    def test_enrolled_borrower_passes(self, pipeline):
        event = _make_event("ENROLLED_BIC_1")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"

    def test_unenrolled_borrower_blocked(self, pipeline):
        event = _make_event("UNKNOWN_BIC")
        result = pipeline.process(event)
        assert result.outcome == "DECLINED" # PipelineResult maps BLOCK/DECLINE to "DECLINED" outcome

        # Verify the decision log entry in the agent
        entry_id = result.decision_entry_id
        entry = pipeline._c7.decision_logger.get(entry_id)
        assert entry.decision_type == "BLOCK"

        # Check that we didn't just get a default decline
        # The agent should have logged the reason (though outcome doesn't show it directly)
        # We can't see 'halt_reason' in PipelineResult, but it's in C7's internal logic.

    def test_empty_registry_permits_all(self):
        # Default config has empty enrolled_borrowers
        agent = ExecutionAgent(
            KillSwitch(), DecisionLogger(hmac_key=_HMAC_KEY),
            HumanOverrideInterface(), DegradedModeManager()
        )
        c1 = MagicMock()
        c1.predict.return_value = {"failure_probability": 0.8, "above_threshold": True}
        c2 = MagicMock()
        c2.predict.return_value = {"pd_score": 0.05, "fee_bps": 300, "tier": 3}
        c4 = MagicMock()
        c4.classify.return_value = {"dispute_class": "NOT_DISPUTE"}
        c6 = MagicMock()
        c6.check.return_value = MagicMock(passed=True)

        pipe = LIPPipeline(c1, c2, c4, c6, agent)

        event = _make_event("ANY_BIC")
        result = pipe.process(event)
        assert result.outcome == "FUNDED"
