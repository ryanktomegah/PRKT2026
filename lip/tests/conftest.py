"""
conftest.py — Shared E2E fixtures for LIP integration and pipeline tests.

All fixtures use in-memory state only; no external services required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c3_repayment_engine.repayment_loop import RepaymentLoop, SettlementMonitor
from lip.c3_repayment_engine.settlement_handlers import SettlementHandlerRegistry
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable
from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.instrumentation import LatencyTracker
from lip.pipeline import LIPPipeline

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

_SALT = b"e2e_test_salt___32bytes_________"
_HMAC_KEY = b"e2e_test_hmac___32bytes_________"

# τ* = 0.152 from Architecture Spec v1.2 Section 3
THRESHOLD = 0.152

# High / low probability values for tests
PROB_ABOVE = 0.80   # clearly above threshold
PROB_BELOW = 0.05   # clearly below threshold


# ---------------------------------------------------------------------------
# Mock C1 engine
# ---------------------------------------------------------------------------

class MockC1Engine:
    """Deterministic C1 failure-prediction stub for E2E tests.

    Returns a configurable ``failure_probability`` with 20 dummy SHAP values.
    """

    def __init__(self, failure_probability: float = PROB_ABOVE) -> None:
        self.failure_probability = failure_probability

    def predict(self, payment: dict) -> dict:
        fp = self.failure_probability
        return {
            "failure_probability": fp,
            "above_threshold": fp > THRESHOLD,
            "inference_latency_ms": 1.0,
            "threshold_used": THRESHOLD,
            "corridor_embedding_used": False,
            "shap_top20": [{"feature": f"feat_{i}", "value": round(0.01 * (i + 1), 4)} for i in range(20)],
        }


# ---------------------------------------------------------------------------
# Mock C2 engine
# ---------------------------------------------------------------------------

class MockC2Engine:
    """Deterministic C2 PD-model stub for E2E tests."""

    def __init__(
        self,
        pd_score: float = 0.05,
        fee_bps: int = 300,
        tier: int = 3,
    ) -> None:
        self.pd_score = pd_score
        self._fee_bps = fee_bps
        self.tier = tier

    def predict(self, payment: dict, borrower: dict) -> dict:
        # Tier-3 / thin-file borrower: always apply fee floor
        is_thin = not (
            borrower.get("has_financial_statements")
            or borrower.get("has_transaction_history")
            or borrower.get("has_credit_bureau")
        )
        tier = 3 if is_thin else self.tier
        return {
            "pd_score": self.pd_score,
            "fee_bps": self._fee_bps,
            "tier": tier,
            "shap_values": [{"feature": f"f_{i}", "value": 0.01} for i in range(20)],
            "borrower_id_hash": "mock_borrower_hash",
            "inference_latency_ms": 1.0,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hmac_key() -> bytes:
    return _HMAC_KEY


@pytest.fixture
def salt() -> bytes:
    return _SALT


@pytest.fixture
def decision_logger(hmac_key) -> DecisionLogger:
    return DecisionLogger(hmac_key=hmac_key)


@pytest.fixture
def kill_switch() -> KillSwitch:
    return KillSwitch()


@pytest.fixture
def degraded_mode() -> DegradedModeManager:
    return DegradedModeManager()


@pytest.fixture
def execution_agent(kill_switch, decision_logger, degraded_mode) -> ExecutionAgent:
    """C7 ExecutionAgent with permissive config (high human-review threshold)."""
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        kill_switch=kill_switch,
        decision_logger=decision_logger,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=degraded_mode,
        config=cfg,
    )


@pytest.fixture
def velocity_checker(salt) -> VelocityChecker:
    return VelocityChecker(salt=salt)


@pytest.fixture
def dispute_classifier() -> DisputeClassifier:
    return DisputeClassifier(llm_backend=MockLLMBackend())


@pytest.fixture
def uetr_mapping() -> UETRMappingTable:
    return UETRMappingTable()


@pytest.fixture
def settlement_monitor(uetr_mapping) -> SettlementMonitor:
    registry = SettlementHandlerRegistry.create_default()
    from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer
    cb = CorridorBuffer()
    return SettlementMonitor(
        handler_registry=registry,
        uetr_mapping=uetr_mapping,
        corridor_buffer=cb,
    )


@pytest.fixture
def repayment_records():
    """Mutable list that the repayment callback appends to."""
    return []


@pytest.fixture
def repayment_loop(settlement_monitor, repayment_records) -> RepaymentLoop:
    def _callback(record: dict) -> None:
        repayment_records.append(record)

    return RepaymentLoop(monitor=settlement_monitor, repayment_callback=_callback)


@pytest.fixture
def latency_tracker() -> LatencyTracker:
    return LatencyTracker()


@pytest.fixture
def mock_c1(request) -> MockC1Engine:
    """Default: above-threshold failure probability."""
    prob = getattr(request, "param", PROB_ABOVE)
    return MockC1Engine(failure_probability=prob)


@pytest.fixture
def mock_c2() -> MockC2Engine:
    return MockC2Engine(pd_score=0.05, fee_bps=300, tier=3)


@pytest.fixture
def pipeline(
    mock_c1,
    mock_c2,
    dispute_classifier,
    velocity_checker,
    execution_agent,
    settlement_monitor,
    latency_tracker,
) -> LIPPipeline:
    """Default pipeline wired with mock C1/C2 and real C4/C6/C7/C3."""
    return LIPPipeline(
        c1_engine=mock_c1,
        c2_engine=mock_c2,
        c4_classifier=dispute_classifier,
        c6_checker=velocity_checker,
        c7_agent=execution_agent,
        c3_monitor=settlement_monitor,
        global_latency_tracker=latency_tracker,
    )


# ---------------------------------------------------------------------------
# Event factory helpers
# ---------------------------------------------------------------------------

def make_event(
    uetr: Optional[str] = None,
    rejection_code: str = "CURR",      # CLASS_B → 7-day maturity
    narrative: Optional[str] = None,
    amount: Decimal = Decimal("100000"),
    currency: str = "USD",
    sending_bic: str = "AAAAGB2LXXX",
    receiving_bic: str = "BBBBDE2LXXX",
    rail: str = "SWIFT",
) -> NormalizedEvent:
    """Factory for NormalizedEvent instances used in E2E tests."""
    return NormalizedEvent(
        uetr=uetr or str(uuid.uuid4()),
        individual_payment_id=str(uuid.uuid4()),
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency=currency,
        timestamp=datetime.now(tz=timezone.utc),
        rail=rail,
        rejection_code=rejection_code,
        narrative=narrative,
        raw_source={},
    )


@pytest.fixture
def normal_event() -> NormalizedEvent:
    """Class-B RJCT event (CURR code) — happy-path fixture."""
    return make_event(rejection_code="CURR", narrative=None)


@pytest.fixture
def dispute_event() -> NormalizedEvent:
    """Event with a dispute narrative that triggers C4 hard block."""
    return make_event(rejection_code="DISP", narrative="This invoice is disputed")


@pytest.fixture
def aml_event() -> NormalizedEvent:
    """Event that will trigger AML block (caller must pre-fill the velocity window)."""
    return make_event(rejection_code="CURR", narrative=None, sending_bic="AML_ENTITY_BIC")
