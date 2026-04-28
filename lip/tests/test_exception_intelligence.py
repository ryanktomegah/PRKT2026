from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.exception_intelligence import ExceptionType, RecommendedAction, assess_exception


def test_iso_account_code_maps_to_account_or_address():
    assessment = assess_exception(
        outcome="BELOW_THRESHOLD",
        rail="SWIFT",
        rejection_code="AC01",
        maturity_hours=72.0,
        failure_probability=0.04,
        above_threshold=False,
    )

    assert assessment.exception_type == ExceptionType.ACCOUNT_OR_ADDRESS
    assert assessment.recommended_action == RecommendedAction.TELEMETRY_ONLY


def test_compliance_code_maps_to_hold():
    assessment = assess_exception(
        outcome="COMPLIANCE_HOLD",
        rail="SWIFT",
        rejection_code="RR04",
        maturity_hours=0.0,
        failure_probability=0.8,
        above_threshold=True,
        compliance_hold=True,
    )

    assert assessment.exception_type == ExceptionType.COMPLIANCE_OR_LEGAL_HOLD
    assert assessment.recommended_action == RecommendedAction.HOLD


def test_c4_dispute_block_maps_to_decline():
    assessment = assess_exception(
        outcome="DISPUTE_BLOCKED",
        rail="SWIFT",
        rejection_code="DISP",
        maturity_hours=0.0,
        failure_probability=0.8,
        above_threshold=True,
        dispute_hard_block=True,
    )

    assert assessment.exception_type == ExceptionType.DISPUTE_OR_COMMERCIAL_CONTEST
    assert assessment.recommended_action == RecommendedAction.DECLINE


def test_cross_rail_handoff_maps_to_offer_bridge_when_offer_exists():
    assessment = assess_exception(
        outcome="DOMESTIC_LEG_FAILURE",
        rail="FEDNOW",
        rejection_code="CURR",
        maturity_hours=24.0,
        failure_probability=0.8,
        above_threshold=True,
        aml_passed=True,
        pd_estimate=0.05,
        handoff_parent_uetr="SWIFT-PARENT-001",
        loan_offer_present=True,
    )

    assert assessment.exception_type == ExceptionType.CROSS_RAIL_HANDOFF_FAILURE
    assert assessment.recommended_action == RecommendedAction.OFFER_BRIDGE


def test_nexus_stub_clean_subday_offer_is_bridge_response():
    assessment = assess_exception(
        outcome="OFFERED",
        rail="CBDC_NEXUS",
        rejection_code="TIMO",
        maturity_hours=4.0,
        failure_probability=0.8,
        above_threshold=True,
        aml_passed=True,
        pd_estimate=0.05,
        loan_offer_present=True,
    )

    assert assessment.exception_type == ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY
    assert assessment.recommended_action == RecommendedAction.OFFER_BRIDGE
    assert assessment.is_subday is True


def test_nexus_stub_clean_subday_without_offer_is_guarantee_candidate():
    assessment = assess_exception(
        outcome="PENDING_HUMAN_REVIEW",
        rail="CBDC_NEXUS",
        rejection_code="TIMO",
        maturity_hours=4.0,
        failure_probability=0.8,
        above_threshold=True,
        aml_passed=True,
        pd_estimate=0.05,
    )

    assert assessment.exception_type == ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY
    assert assessment.recommended_action == RecommendedAction.GUARANTEE_CANDIDATE


def test_unknown_code_below_threshold_is_telemetry_only():
    assessment = assess_exception(
        outcome="BELOW_THRESHOLD",
        rail="SWIFT",
        rejection_code="NEWCODE",
        maturity_hours=0.0,
        failure_probability=0.05,
        above_threshold=False,
    )

    assert assessment.exception_type == ExceptionType.UNKNOWN
    assert assessment.recommended_action == RecommendedAction.TELEMETRY_ONLY


def test_pipeline_handoff_result_contains_exception_assessment():
    from lip.tests.conftest import make_event
    from lip.tests.test_e2e_pipeline import _make_pipeline

    pipeline = _make_pipeline(failure_probability=0.80, fee_bps=300)
    event = make_event(
        rejection_code="CURR",
        rail="FEDNOW",
        currency="USD",
        amount=Decimal("5000000.00"),
    )
    pipeline._uetr_tracker.register_handoff(
        parent_uetr="SWIFT-PARENT-001",
        child_uetr=event.uetr,
        child_rail="FEDNOW",
    )

    result = pipeline.process(event)

    assert result.outcome == "DOMESTIC_LEG_FAILURE"
    assert result.exception_assessment["exception_type"] == "CROSS_RAIL_HANDOFF_FAILURE"
    assert result.exception_assessment["recommended_action"] == "OFFER_BRIDGE"
    assert result.exception_assessment["signals"]["handoff_parent_uetr"] == "SWIFT-PARENT-001"


def test_pipeline_unknown_code_below_threshold_contains_telemetry_assessment():
    from lip.tests.conftest import make_event
    from lip.tests.test_e2e_pipeline import _make_pipeline

    pipeline = _make_pipeline(failure_probability=0.05)
    event = make_event(rejection_code="NEWCODE")

    result = pipeline.process(event)

    assert result.outcome == "BELOW_THRESHOLD"
    assert result.exception_assessment["exception_type"] == "UNKNOWN"
    assert result.exception_assessment["recommended_action"] == "TELEMETRY_ONLY"


def test_pipeline_major_outcomes_include_exception_assessment():
    from lip.c6_aml_velocity.velocity import VelocityChecker
    from lip.c7_execution_agent.kill_switch import KillSwitch
    from lip.tests.conftest import _SALT, make_event
    from lip.tests.test_e2e_pipeline import _TEST_DOLLAR_CAP_USD, _make_pipeline

    offered = _make_pipeline(failure_probability=0.80).process(make_event(rejection_code="CURR"))
    below = _make_pipeline(failure_probability=0.05).process(make_event(rejection_code="CURR"))
    dispute = _make_pipeline(failure_probability=0.80).process(make_event(rejection_code="DISP"))

    vc = VelocityChecker(salt=_SALT)
    entity_id = "exception_assessment_aml_entity"
    vc.record(entity_id, _TEST_DOLLAR_CAP_USD - Decimal("1"), "bene1")
    aml_pipeline = _make_pipeline(failure_probability=0.80)
    aml_pipeline._c6 = vc
    aml_pipeline._c7.aml_dollar_cap_usd = int(_TEST_DOLLAR_CAP_USD)
    aml = aml_pipeline.process(
        make_event(rejection_code="CURR", sending_bic=entity_id),
        entity_id=entity_id,
        beneficiary_id="bene2",
    )

    ks = KillSwitch()
    ks.activate("exception assessment test")
    halt = _make_pipeline(failure_probability=0.80, kill_switch=ks).process(
        make_event(rejection_code="CURR")
    )

    retry_pipeline = _make_pipeline(failure_probability=0.80)
    retry_event = make_event(rejection_code="CURR")
    retry_pipeline.process(retry_event)
    retry = retry_pipeline.process(retry_event)

    results = [offered, below, dispute, aml, halt, retry]
    assert [r.outcome for r in results] == [
        "OFFERED",
        "BELOW_THRESHOLD",
        "DISPUTE_BLOCKED",
        "AML_BLOCKED",
        "HALT",
        "RETRY_BLOCKED",
    ]
    assert all(r.exception_assessment for r in results)


def test_pipeline_stressed_corridor_assessment_is_human_review():
    from lip.tests.conftest import make_event
    from lip.tests.test_e2e_pipeline import _make_pipeline

    class _AlwaysStressedDetector:
        def record_event(self, corridor, is_failure, rail=None):
            return None

        def is_stressed(self, corridor, rail=None):
            return True

    detector = _AlwaysStressedDetector()
    pipeline = _make_pipeline(failure_probability=0.80)
    pipeline._stress_detector = detector
    pipeline._c7.stress_detector = detector

    result = pipeline.process(make_event(rejection_code="CURR"))

    assert result.outcome == "PENDING_HUMAN_REVIEW"
    assert result.exception_assessment["exception_type"] == "STRESS_REGIME"
    assert result.exception_assessment["recommended_action"] == "HUMAN_REVIEW"


def test_stress_regime_event_json_includes_rail_when_present():
    from lip.c5_streaming.stress_regime_detector import StressRegimeEvent

    event = StressRegimeEvent(
        corridor="CNY_HKD",
        failure_rate_1h=0.6,
        baseline_rate=0.1,
        ratio=6.0,
        triggered_at=1.0,
        rail="CBDC_MBRIDGE",
    )

    assert '"rail": "CBDC_MBRIDGE"' in event.to_json()


def test_miplo_process_defaults_rail_and_returns_exception_assessment():
    fastapi = pytest.importorskip("fastapi")
    TestClient = pytest.importorskip("fastapi.testclient").TestClient
    from lip.api.miplo_router import make_miplo_router

    captured_events: list[NormalizedEvent] = []

    class _Service:
        tenant_id = "TENANT-001"

        def process_payment(self, event, **kwargs):
            captured_events.append(event)
            return SimpleNamespace(
                outcome="DECLINED",
                uetr=event.uetr,
                failure_probability=0.8,
                above_threshold=True,
                loan_offer=None,
                decision_entry_id="entry-001",
                exception_assessment={
                    "exception_type": "UNKNOWN",
                    "recommended_action": "HUMAN_REVIEW",
                },
                pd_estimate=0.05,
                fee_bps=400,
                total_latency_ms=12.5,
            )

        def get_status(self):
            return {}

    app = fastapi.FastAPI()
    app.include_router(make_miplo_router(_Service()), prefix="/miplo")

    with TestClient(app) as client:
        old_response = client.post(
            "/miplo/process",
            json={
                "uetr": "u1",
                "sending_bic": "COBADEFF",
                "receiving_bic": "DEUTDEFF",
                "amount": "100.00",
                "currency": "USD",
                "rejection_code": "CURR",
            },
        )
        nexus_response = client.post(
            "/miplo/process",
            json={
                "uetr": "u2",
                "sending_bic": "COBADEFF",
                "receiving_bic": "DEUTDEFF",
                "amount": "100.00",
                "currency": "USD",
                "rail": "CBDC_NEXUS",
                "rejection_code": "TIMO",
            },
        )

    assert old_response.status_code == 200
    assert nexus_response.status_code == 200
    assert captured_events[0].rail == "SWIFT"
    assert captured_events[1].rail == "CBDC_NEXUS"
    assert nexus_response.json()["exception_assessment"]["exception_type"] == "UNKNOWN"
