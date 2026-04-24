"""
test_e2e_latency.py — Latency instrumentation E2E tests.

Verifies:
  - LatencyTracker records component latencies correctly.
  - Pipeline populates component_latencies and total_latency_ms in PipelineResult.
  - p50 < 100ms for full in-process pipeline (no network I/O).
  - Latency breakdown is available per component.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.instrumentation import LatencyTracker
from lip.pipeline import LIPPipeline

from .conftest import _HMAC_KEY, _SALT, MockC1Engine, MockC2Engine, make_event


def _build_pipeline(failure_probability=0.80, global_tracker=None):
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    agent = ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=MockC1Engine(failure_probability),
        c2_engine=MockC2Engine(),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
        global_latency_tracker=global_tracker,
    )


# ===========================================================================
# LatencyTracker unit-level tests
# ===========================================================================

class TestLatencyTracker:

    def test_record_and_retrieve_latest(self):
        tracker = LatencyTracker()
        tracker.record("c1", 15.5)
        assert tracker.latest("c1") == 15.5

    def test_p50_single_sample(self):
        tracker = LatencyTracker()
        tracker.record("c1", 20.0)
        assert tracker.p50("c1") == 20.0

    def test_p50_multiple_samples(self):
        tracker = LatencyTracker()
        for v in [10.0, 20.0, 30.0]:
            tracker.record("c1", v)
        assert tracker.p50("c1") == 20.0

    def test_p99_returns_near_max(self):
        tracker = LatencyTracker()
        for v in range(100):
            tracker.record("comp", float(v))
        p99 = tracker.p99("comp")
        assert p99 is not None
        assert p99 >= 97.0

    def test_missing_component_returns_none(self):
        tracker = LatencyTracker()
        assert tracker.p50("nonexistent") is None
        assert tracker.p99("nonexistent") is None
        assert tracker.latest("nonexistent") is None

    def test_measure_context_manager_records_latency(self):
        tracker = LatencyTracker()
        with tracker.measure("test_comp"):
            time.sleep(0.001)
        assert tracker.latest("test_comp") is not None
        assert tracker.latest("test_comp") > 0.0

    def test_get_latest_all(self):
        tracker = LatencyTracker()
        tracker.record("c1", 10.0)
        tracker.record("c2", 5.0)
        latest = tracker.get_latest_all()
        assert "c1" in latest
        assert "c2" in latest
        assert latest["c1"] == 10.0
        assert latest["c2"] == 5.0

    def test_reset_clears_samples(self):
        tracker = LatencyTracker()
        tracker.record("c1", 10.0)
        tracker.reset()
        assert tracker.latest("c1") is None
        assert tracker.sample_count("c1") == 0


# ===========================================================================
# Pipeline latency integration tests
# ===========================================================================

class TestPipelineLatency:

    def test_pipeline_result_has_total_latency(self):
        pipeline = _build_pipeline()
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.total_latency_ms > 0.0

    def test_pipeline_result_has_component_latencies(self):
        pipeline = _build_pipeline()
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert isinstance(result.component_latencies, dict)
        # At minimum C1 should be recorded for any result
        assert "c1" in result.component_latencies

    def test_offered_pipeline_records_all_components(self):
        pipeline = _build_pipeline(failure_probability=0.80)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "OFFERED"
        latencies = result.component_latencies
        for comp in ("c1", "c4", "c6", "c2", "c7"):
            assert comp in latencies, f"Missing latency for component: {comp}"

    def test_below_threshold_only_has_c1_latency(self):
        pipeline = _build_pipeline(failure_probability=0.05)
        event = make_event(rejection_code="CURR")
        result = pipeline.process(event)
        assert result.outcome == "BELOW_THRESHOLD"
        # C4/C6/C2/C7 should not have been called
        assert "c4" not in result.component_latencies
        assert "c2" not in result.component_latencies

    def test_p50_latency_target(self):
        global_tracker = LatencyTracker()
        pipeline = _build_pipeline(global_tracker=global_tracker)

        # Run 10 times to get stable p50
        for _ in range(10):
            event = make_event(rejection_code="CURR", uetr=str(uuid.uuid4()))
            pipeline.process(event)

        p50 = global_tracker.p50("total")
        assert p50 is not None
        assert p50 < 100.0, f"p50 latency {p50:.1f}ms exceeds 100ms target"

    def test_global_tracker_accumulates_across_calls(self):
        global_tracker = LatencyTracker()
        pipeline = _build_pipeline(global_tracker=global_tracker)

        # Vary amount per iteration so tuple-based dedup (GAP-04) doesn't
        # flag identical (bic, bic, amount, currency) as manual retries.
        for i in range(5):
            event = make_event(
                rejection_code="CURR",
                uetr=str(uuid.uuid4()),
                amount=Decimal(str(1_000_000 + i * 100_000)),
            )
            pipeline.process(event)

        assert global_tracker.sample_count("total") == 5
        assert global_tracker.sample_count("c1") == 5
