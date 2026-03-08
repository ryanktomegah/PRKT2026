"""
test_e2e_decision_log.py — Decision log integrity E2E tests.

Verifies:
  - Every pipeline execution produces exactly one DecisionLogEntry.
  - Entry contains all required fields.
  - HMAC-SHA256 signature is valid.
  - Tampered entries fail verification.
  - kms_unavailable_gap flag set during KMS outage.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogEntryData, DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager, DegradedReason
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.pipeline import LIPPipeline

from .conftest import _HMAC_KEY, _SALT, MockC1Engine, MockC2Engine, make_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pipeline_with_logger(failure_probability=0.80, degraded=None):
    dm = degraded or DegradedModeManager()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    ks = KillSwitch()
    agent = ExecutionAgent(
        kill_switch=ks,
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=dm,
        config=cfg,
    )
    pipeline = LIPPipeline(
        c1_engine=MockC1Engine(failure_probability),
        c2_engine=MockC2Engine(),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
    )
    return pipeline, dl


# ===========================================================================
# Decision log entry existence
# ===========================================================================

class TestDecisionLogEntry:

    def test_funded_pipeline_produces_one_entry(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "FUNDED"
        assert result.decision_entry_id is not None
        entry = dl.get(result.decision_entry_id)
        assert entry is not None

    def test_entry_uetr_matches_event(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.uetr == event.uetr

    def test_entry_contains_failure_probability(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert abs(entry.failure_probability - 0.80) < 1e-6

    def test_entry_contains_pd_estimate(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.pd_score >= 0.0

    def test_entry_fee_bps_is_annualized_floor(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.fee_bps >= 300

    def test_entry_has_degraded_mode_flag(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        # Normal operation: degraded_mode should be False
        assert entry.degraded_mode is False

    def test_entry_kms_gap_is_none_in_normal_operation(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.kms_unavailable_gap is None

    def test_entry_decision_type_is_offer(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.decision_type == "OFFER"


# ===========================================================================
# HMAC signature verification
# ===========================================================================

class TestHMACSignature:

    def test_signature_is_present(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        assert entry.entry_signature != ""

    def test_signature_verifies_successfully(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert dl.verify(result.decision_entry_id) is True

    def test_tampered_entry_fails_verification(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        entry = dl.get(result.decision_entry_id)
        # Tamper with the fee_bps field
        entry.fee_bps = 9999
        # Signature should now be invalid
        assert dl.verify(result.decision_entry_id) is False

    def test_different_hmac_key_fails_verification(self):
        """Verifying with a different key must fail."""
        dl_correct = DecisionLogger(hmac_key=_HMAC_KEY)
        dl_wrong = DecisionLogger(hmac_key=b"wrong_key_32bytes_______________")

        entry = DecisionLogEntryData(
            entry_id="",
            uetr="test-uetr",
            individual_payment_id="test-pid",
            decision_type="OFFER",
            decision_timestamp=datetime.now(tz=timezone.utc).isoformat(),
            failure_probability=0.80,
            pd_score=0.05,
            fee_bps=300,
            loan_amount="100000",
            dispute_class="NOT_DISPUTE",
            aml_passed=True,
        )
        entry_id = dl_correct.log(entry)
        assert dl_correct.verify(entry_id) is True

        # Try to verify with wrong key — must fail
        stolen_entry = dl_correct.get(entry_id)
        # Manually check the signature using the wrong key
        dl_wrong._store[entry_id] = stolen_entry
        assert dl_wrong.verify(entry_id) is False

    def test_get_by_uetr_returns_entries(self):
        pipeline, dl = _build_pipeline_with_logger(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        _result = pipeline.process(event)
        entries = dl.get_by_uetr(event.uetr)
        assert len(entries) >= 1
        assert entries[0].uetr == event.uetr


# ===========================================================================
# KMS gap flag in decision log
# ===========================================================================

class TestKMSGapDecisionLog:

    def test_kms_gap_set_during_kms_failure(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)

        # During KMS failure, new offers are halted — but the state_dict
        # should record kms_unavailable_gap
        state = dm.get_state_dict()
        assert state["kms_unavailable_gap"] is not None
        assert state["kms_unavailable_gap"] >= 0.0

    def test_kms_gap_none_after_recovery(self):
        dm = DegradedModeManager()
        dm.enter_degraded_mode(DegradedReason.KMS_FAILURE)
        dm.exit_degraded_mode()
        state = dm.get_state_dict()
        assert state["kms_unavailable_gap"] is None
