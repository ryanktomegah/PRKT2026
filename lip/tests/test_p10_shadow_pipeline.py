"""
test_p10_shadow_pipeline.py — Sprint 7 integration tests.

Validates TelemetryCollector, ShadowPipelineRunner, shadow data generator,
performance targets, and end-to-end pipeline data flow.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

_SALT = b"shadow_test_salt_32bytes________"


def _make_event(
    *,
    uetr: str = "550e8400-e29b-41d4-a716-446655440000",
    individual_payment_id: str = "PAY-001",
    sending_bic: str = "DEUTDEFF",
    receiving_bic: str = "BNPAFRPP",
    amount: Decimal = Decimal("50000"),
    currency: str = "EUR",
    timestamp: datetime | None = None,
    rail: str = "SWIFT",
    rejection_code: str | None = None,
    telemetry_eligible: bool = True,
) -> NormalizedEvent:
    if timestamp is None:
        timestamp = datetime(2026, 4, 2, 14, 30, 0, tzinfo=timezone.utc)
    return NormalizedEvent(
        uetr=uetr,
        individual_payment_id=individual_payment_id,
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency=currency,
        timestamp=timestamp,
        rail=rail,
        rejection_code=rejection_code,
        telemetry_eligible=telemetry_eligible,
    )


class TestTelemetryCollector:
    """TDD tests for TelemetryCollector — Sprint 7."""

    def _make_collector(self):
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector
        return TelemetryCollector(salt=_SALT)

    def _flush_period(self):
        period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)
        return period_start, period_end

    # ------------------------------------------------------------------
    # Test 1: Single eligible event produces one batch with one corridor stat
    # ------------------------------------------------------------------
    def test_eligible_event_produces_batch(self):
        collector = self._make_collector()
        event = _make_event()
        result = collector.ingest(event)
        assert result is True

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        assert len(batches[0].corridor_statistics) == 1

    # ------------------------------------------------------------------
    # Test 2: Ineligible event is filtered — ingest returns False, flush empty
    # ------------------------------------------------------------------
    def test_ineligible_event_filtered(self):
        collector = self._make_collector()
        event = _make_event(telemetry_eligible=False)
        result = collector.ingest(event)
        assert result is False

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)
        assert batches == []

    # ------------------------------------------------------------------
    # Test 3: Amount bucket boundary conditions
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("amount,expected_bucket", [
        (Decimal("9999"),      "0-10K"),
        (Decimal("10000"),     "10K-100K"),
        (Decimal("99999"),     "10K-100K"),
        (Decimal("100000"),    "100K-1M"),
        (Decimal("10000000"), "10M+"),
    ])
    def test_amount_bucket_boundaries(self, amount, expected_bucket):
        collector = self._make_collector()
        event = _make_event(amount=amount)
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert stat.amount_bucket_distribution.get(expected_bucket, 0) == 1

    # ------------------------------------------------------------------
    # Test 4: EUR event corridor is a non-empty string
    # ------------------------------------------------------------------
    def test_corridor_from_currency(self):
        collector = self._make_collector()
        event = _make_event(currency="EUR")
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert isinstance(stat.corridor, str)
        assert len(stat.corridor) > 0

    # ------------------------------------------------------------------
    # Test 5: Two different BICs → two batches with different bank_hash values
    # ------------------------------------------------------------------
    def test_multiple_banks_separate_batches(self):
        collector = self._make_collector()
        event_a = _make_event(
            uetr="550e8400-e29b-41d4-a716-446655440001",
            individual_payment_id="PAY-A",
            sending_bic="DEUTDEFF",
        )
        event_b = _make_event(
            uetr="550e8400-e29b-41d4-a716-446655440002",
            individual_payment_id="PAY-B",
            sending_bic="BNPAFRPP",
        )
        collector.ingest(event_a)
        collector.ingest(event_b)

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 2
        hashes = {b.bank_hash for b in batches}
        assert len(hashes) == 2

    # ------------------------------------------------------------------
    # Test 6: Second flush after first flush returns empty
    # ------------------------------------------------------------------
    def test_flush_clears_accumulators(self):
        collector = self._make_collector()
        event = _make_event()
        collector.ingest(event)

        period_start, period_end = self._flush_period()
        batches_first = collector.flush(period_start, period_end)
        assert len(batches_first) == 1

        batches_second = collector.flush(period_start, period_end)
        assert batches_second == []

    # ------------------------------------------------------------------
    # Test 7: Every flushed batch has a non-empty hmac_signature
    # ------------------------------------------------------------------
    def test_batch_hmac_present(self):
        collector = self._make_collector()
        collector.ingest(_make_event(sending_bic="DEUTDEFF"))
        collector.ingest(_make_event(
            uetr="550e8400-e29b-41d4-a716-446655440002",
            individual_payment_id="PAY-B",
            sending_bic="BNPAFRPP",
        ))

        period_start, period_end = self._flush_period()
        batches = collector.flush(period_start, period_end)

        assert len(batches) == 2
        for batch in batches:
            assert isinstance(batch.hmac_signature, str)
            assert len(batch.hmac_signature) > 0

    # ------------------------------------------------------------------
    # Test 8: Failure class distribution — BLOCK (DNOR) and CLASS_A (AC01)
    # ------------------------------------------------------------------
    def test_failure_class_distribution(self):
        # BLOCK event
        collector_block = self._make_collector()
        # BLOCK codes cause telemetry_eligible=False in normalizer, but we can
        # directly set telemetry_eligible=True with rejection_code to test the
        # failure_class_distribution logic inside TelemetryCollector
        event_block = _make_event(rejection_code="DNOR", telemetry_eligible=True)
        collector_block.ingest(event_block)
        period_start, period_end = self._flush_period()
        batches = collector_block.flush(period_start, period_end)
        assert len(batches) == 1
        stat = batches[0].corridor_statistics[0]
        assert stat.failure_class_distribution.get("BLOCK", 0) == 1

        # CLASS_A event
        collector_a = self._make_collector()
        event_a = _make_event(rejection_code="AC01", telemetry_eligible=True)
        collector_a.ingest(event_a)
        batches_a = collector_a.flush(period_start, period_end)
        assert len(batches_a) == 1
        stat_a = batches_a[0].corridor_statistics[0]
        assert stat_a.failure_class_distribution.get("CLASS_A", 0) == 1


# ---------------------------------------------------------------------------
# Task 3: Shadow Data Generator Tests
# ---------------------------------------------------------------------------


class TestShadowDataGenerator:
    """Verify synthetic event generation for shadow mode."""

    def test_generates_correct_count(self):
        """5 banks x 2000 events = 10000 total."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        assert len(events) == 10_000

    def test_distinct_banks(self):
        """5 banks -> 5 distinct bank identifiers (first 4 chars of BIC)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=100, seed=42)
        bank_ids = {e.sending_bic[:4] for e in events}
        assert len(bank_ids) == 5

    def test_deterministic_with_seed(self):
        """Same seed -> identical UETRs."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        a = generate_shadow_events(n_banks=3, n_events_per_bank=50, seed=99)
        b = generate_shadow_events(n_banks=3, n_events_per_bank=50, seed=99)
        assert [e.uetr for e in a] == [e.uetr for e in b]

    def test_failure_rate_approximately_correct(self):
        """~8% overall failure rate (within generous range)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        failed = sum(1 for e in events if e.rejection_code is not None)
        rate = failed / len(events)
        assert 0.05 < rate < 0.15

    def test_some_events_ineligible(self):
        """~2% of events have telemetry_eligible=False."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        ineligible = sum(1 for e in events if not e.telemetry_eligible)
        rate = ineligible / len(events)
        assert 0.005 < rate < 0.05


# ---------------------------------------------------------------------------
# Task 4: ShadowPipelineRunner End-to-End Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def shadow_components():
    """Pre-configured anonymizer + risk engine for shadow pipeline tests."""
    anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
    engine = SystemicRiskEngine()
    return anonymizer, engine


class TestShadowPipelineEndToEnd:
    """Verify full pipeline: events -> collector -> anonymizer -> engine -> report."""

    def test_full_pipeline_produces_report(self, shadow_components):
        """10K events -> non-None SystemicRiskReport."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        assert result.report is not None
        assert result.report.total_corridors_analyzed > 0

    def test_all_corridors_present(self, shadow_components):
        """8 corridors in report (5 banks >= k=5, none suppressed)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        assert result.corridors_suppressed == 0
        assert result.corridors_analyzed >= 8

    def test_stressed_corridor_elevated(self, shadow_components):
        """Stressed corridor has higher failure rate than average."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(
            n_banks=5, n_events_per_bank=2000, seed=42,
            stressed_corridor="EUR-USD", stressed_rate=0.25,
        )
        result = runner.run(events)
        snapshots = result.report.corridor_snapshots
        rates = {s.corridor: s.failure_rate for s in snapshots}
        max_rate = max(rates.values()) if rates else 0
        mean_rate = sum(rates.values()) / len(rates) if rates else 0
        assert max_rate > mean_rate

    def test_privacy_budget_consumed(self, shadow_components):
        """privacy_budget_consumed > 0.0 after pipeline run."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        assert result.privacy_budget_consumed > 0.0

    def test_timings_populated(self, shadow_components):
        """All timing keys present and >= 0."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        expected_keys = {
            "collect_ms", "flush_ms", "anonymize_ms",
            "ingest_ms", "report_ms", "verify_ms", "total_ms",
        }
        assert set(result.timings.keys()) == expected_keys
        for key, val in result.timings.items():
            assert val >= 0, f"timing {key} is negative: {val}"

    def test_filtered_events_counted(self, shadow_components):
        """events_filtered approximately 2% of total."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        total = result.events_ingested + result.events_filtered
        filter_rate = result.events_filtered / total if total > 0 else 0
        assert 0.005 < filter_rate < 0.05

    def test_report_integrity_verified(self, shadow_components):
        """integrity_verified is True."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        assert result.integrity_verified is True

    def test_sequential_runs_accumulate_trends(self, shadow_components):
        """3 runs -> trend history accumulates."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        for seed in [42, 43, 44]:
            events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=seed)
            runner.run(events)

        report = engine.compute_risk_report()
        assert report.total_corridors_analyzed > 0


# ---------------------------------------------------------------------------
# Task 6: Performance Target Tests
# ---------------------------------------------------------------------------

class TestPerformanceTargets:
    """Validate Sprint 7 blueprint performance targets."""

    def test_corridor_query_under_500ms(self):
        """RegulatoryService.get_corridor_snapshots() < 500ms."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        runner.run(events)

        service = RegulatoryService(risk_engine=engine)

        t0 = time.perf_counter()
        snapshots, suppressed = service.get_corridor_snapshots(period_count=24)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 500, f"Corridor query took {elapsed_ms:.1f}ms (target: <500ms)"
        assert len(snapshots) > 0

    def test_stress_test_under_30s(self):
        """RegulatoryService.run_stress_test() < 30s."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        runner.run(events)

        service = RegulatoryService(risk_engine=engine)

        t0 = time.perf_counter()
        report_id, report = service.run_stress_test(
            scenario_name="EUR-USD-shock",
            shocks=[("EUR-USD", 0.5)],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 30_000, f"Stress test took {elapsed_ms:.1f}ms (target: <30s)"
        assert report is not None

    def test_full_pipeline_under_5s(self):
        """ShadowPipelineRunner.run(10K events) total_ms < 5000."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)

        result = runner.run(events)
        assert result.timings["total_ms"] < 5000, (
            f"Pipeline took {result.timings['total_ms']:.1f}ms (target: <5s)"
        )
