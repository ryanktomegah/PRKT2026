"""
shadow_runner.py — P10 shadow mode pipeline orchestrator.

Sprint 7: Wires TelemetryCollector -> RegulatoryAnonymizer -> SystemicRiskEngine
-> VersionedReport into a single run() call with per-stage timing.

No infrastructure dependencies. Designed for pytest, CLI scripts, and notebooks.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.report_metadata import (
    ReportIntegrityError,
    VersionedReport,
    create_versioned_report,
    verify_report_integrity,
)
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine, SystemicRiskReport
from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

if TYPE_CHECKING:
    from lip.c5_streaming.event_normalizer import NormalizedEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowRunResult:
    """Output of a single shadow pipeline run."""

    report: SystemicRiskReport
    versioned_report: VersionedReport
    events_ingested: int
    events_filtered: int
    batches_produced: int
    corridors_analyzed: int
    corridors_suppressed: int
    privacy_budget_consumed: float
    timings: dict[str, float] = field(default_factory=dict)
    integrity_verified: bool = False


class ShadowPipelineRunner:
    """Orchestrates the full P10 pipeline on in-memory event streams.

    Usage::

        runner = ShadowPipelineRunner(salt, anonymizer, risk_engine)
        result = runner.run(events)
        print(result.report.systemic_risk_score)
        print(result.timings)  # per-stage wall-clock ms
    """

    def __init__(
        self,
        salt: bytes,
        anonymizer: RegulatoryAnonymizer,
        risk_engine: SystemicRiskEngine,
    ) -> None:
        self._salt = salt
        self._anonymizer = anonymizer
        self._risk_engine = risk_engine

    def run(
        self,
        events: list[NormalizedEvent],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> ShadowRunResult:
        """Run the full P10 pipeline on a list of NormalizedEvent.

        Stages (each timed):
          1. Collect — feed events into TelemetryCollector
          2. Flush — drain into TelemetryBatch objects
          3. Anonymize — 3-layer privacy pipeline
          4. Ingest — feed anonymized results into risk engine
          5. Report — compute systemic risk report
          6. Verify — create versioned report + integrity check
        """
        total_start = time.perf_counter()
        timings: dict[str, float] = {}

        if period_start is None:
            period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
        if period_end is None:
            period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

        # Stage 1: Collect
        t0 = time.perf_counter()
        collector = TelemetryCollector(salt=self._salt)
        for event in events:
            collector.ingest(event)
        timings["collect_ms"] = (time.perf_counter() - t0) * 1000

        events_ingested = collector.events_ingested
        events_filtered = collector.events_filtered

        # Stage 2: Flush
        t0 = time.perf_counter()
        batches = collector.flush(period_start, period_end)
        timings["flush_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 3: Anonymize
        t0 = time.perf_counter()
        anon_results = self._anonymizer.anonymize_batch(batches)
        timings["anonymize_ms"] = (time.perf_counter() - t0) * 1000

        corridors_analyzed = len(anon_results)
        # Count unique corridors across all batches to determine suppression
        batch_corridors: set[str] = set()
        for b in batches:
            for cs in b.corridor_statistics:
                batch_corridors.add(cs.corridor)
        corridors_suppressed = max(0, len(batch_corridors) - corridors_analyzed)

        # Privacy budget consumed (epsilon per corridor that had noise applied)
        budget_consumed = sum(
            float(self._anonymizer.epsilon)
            for r in anon_results
            if r.noise_applied
        )

        # Stage 4: Ingest
        t0 = time.perf_counter()
        self._risk_engine.ingest_results(anon_results)
        timings["ingest_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 5: Report
        t0 = time.perf_counter()
        report = self._risk_engine.compute_risk_report()
        timings["report_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 6: Verify
        t0 = time.perf_counter()
        versioned = create_versioned_report(report)
        try:
            verify_report_integrity(versioned)
            integrity_ok = True
        except ReportIntegrityError:
            integrity_ok = False
            logger.error("Report integrity verification failed!")
        timings["verify_ms"] = (time.perf_counter() - t0) * 1000

        timings["total_ms"] = (time.perf_counter() - total_start) * 1000

        return ShadowRunResult(
            report=report,
            versioned_report=versioned,
            events_ingested=events_ingested,
            events_filtered=events_filtered,
            batches_produced=len(batches),
            corridors_analyzed=corridors_analyzed,
            corridors_suppressed=corridors_suppressed,
            privacy_budget_consumed=budget_consumed,
            timings=timings,
            integrity_verified=integrity_ok,
        )
