"""
test_gap02_aml_caps.py — Integration tests for GAP-02: licensee-configurable AML caps.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.pipeline import LIPPipeline

_SALT = b"test_salt_32bytes_long_exactly__"
_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"

@pytest.fixture
def velocity_checker():
    return VelocityChecker(salt=_SALT)

@pytest.fixture
def execution_agent():
    ks = KillSwitch()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    ho = HumanOverrideInterface()
    dm = DegradedModeManager()
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        ks, dl, ho, dm, cfg,
        licensee_id="TEST_BANK",
        aml_dollar_cap_usd=50000,  # Custom cap
        aml_count_cap=5            # Custom cap
    )

@pytest.fixture
def pipeline(velocity_checker, execution_agent):
    c1 = MagicMock()
    c1.predict.return_value = {"failure_probability": 0.5, "above_threshold": True}
    c2 = MagicMock()
    c2.predict.return_value = {"pd_score": 0.05, "fee_bps": 300, "tier": 3}
    c4 = MagicMock()
    c4.classify.return_value = {"dispute_class": "NOT_DISPUTE"}

    return LIPPipeline(
        c1_engine=c1,
        c2_engine=c2,
        c4_classifier=c4,
        c6_checker=velocity_checker,
        c7_agent=execution_agent
    )

def _make_event(amount: Decimal = Decimal("10000")):
    return NormalizedEvent(
        uetr="uetr-1",
        individual_payment_id="pid-1",
        sending_bic="SENDER",
        receiving_bic="RECEIVER",
        amount=amount,
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code="CURR",
        narrative=None,
        raw_source={}
    )

class TestGap02AmlCaps:
    def test_custom_dollar_cap_enforced(self, pipeline, velocity_checker):
        # Cap is 50,000. Record 45,000.
        velocity_checker.record("SENDER", Decimal("45000"), "RECEIVER")

        # 10,000 should exceed 50,000 cap
        event = _make_event(amount=Decimal("10000"))
        result = pipeline.process(event)

        assert result.outcome == "AML_BLOCKED"
        assert result.aml_passed is False
        assert result.aml_hard_block is True

    def test_custom_count_cap_enforced(self, pipeline, velocity_checker):
        # Cap is 5. Record 5 small transactions.
        for i in range(5):
            velocity_checker.record("SENDER", Decimal("100"), f"BENE_{i}")

        # 6th should exceed cap
        event = _make_event(amount=Decimal("100"))
        result = pipeline.process(event)

        assert result.outcome == "AML_BLOCKED"
        assert result.aml_passed is False
        assert result.aml_hard_block is True

    def test_default_caps_still_work_if_not_set(self):
        # Agent with default caps (1M, 100)
        agent = ExecutionAgent(
            KillSwitch(), DecisionLogger(hmac_key=_HMAC_KEY),
            HumanOverrideInterface(), DegradedModeManager()
        )
        vc = VelocityChecker(salt=_SALT)

        c1 = MagicMock()
        c1.predict.return_value = {"failure_probability": 0.5, "above_threshold": True}
        c2 = MagicMock()
        c4 = MagicMock()
        c4.classify.return_value = {"dispute_class": "NOT_DISPUTE"}

        pipe = LIPPipeline(c1, c2, c4, vc, agent)

        # 500,000 should pass (under 1M)
        event = _make_event(amount=Decimal("500000"))
        result = pipe.process(event)
        assert result.outcome != "AML_BLOCKED"
