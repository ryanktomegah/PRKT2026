"""
regulatory_service.py — Regulatory API service layer.

Orchestrates SystemicRiskEngine, CorridorConcentrationAnalyzer, and
ContagionSimulator into API-ready responses. Manages in-memory report
cache with TTL eviction.

Sprint 4c: no new financial math — all computation delegates to Sprint 4b.
Sprint 5: CachedReport replaced by VersionedReport.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from lip.p10_regulatory_data.concentration import (
    ConcentrationResult,
    CorridorConcentrationAnalyzer,
)
from lip.p10_regulatory_data.constants import (
    P10_DIFFERENTIAL_PRIVACY_EPSILON,
    P10_K_ANONYMITY_THRESHOLD,
)
from lip.p10_regulatory_data.contagion import ContagionResult, ContagionSimulator
from lip.p10_regulatory_data.methodology import MethodologyAppendix
from lip.p10_regulatory_data.report_metadata import (
    VersionedReport,
    create_versioned_report,
    verify_report_integrity,
)
from lip.p10_regulatory_data.report_renderer import ReportRenderer
from lip.p10_regulatory_data.systemic_risk import (
    CorridorRiskSnapshot,
    SystemicRiskEngine,
)
from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

logger = logging.getLogger(__name__)


class RegulatoryService:
    """Regulatory API business logic orchestration.

    Wraps SystemicRiskEngine, CorridorConcentrationAnalyzer, ContagionSimulator.
    Manages in-memory report cache with TTL eviction.
    Thread-safe (delegates to thread-safe engines).
    """

    def __init__(
        self,
        risk_engine: SystemicRiskEngine,
        report_ttl_seconds: float = 3600.0,
        max_cached_reports: int = 100,
    ):
        self._engine = risk_engine
        self._concentration = CorridorConcentrationAnalyzer()
        self._contagion = ContagionSimulator()
        self._report_ttl = report_ttl_seconds
        self._max_reports = max_cached_reports
        self._reports: Dict[str, VersionedReport] = {}
        self._lock = threading.Lock()
        self._query_count: int = 0
        self._renderer = ReportRenderer()

    def _increment_query_count(self) -> None:
        with self._lock:
            self._query_count += 1

    def get_corridor_snapshots(
        self,
        period_count: int = 24,
        min_bank_count: int = 5,
    ) -> Tuple[List[CorridorRiskSnapshot], int]:
        """Get latest corridor snapshots, filtering by k-anonymity.

        Returns (published_snapshots, suppressed_count).
        Corridors with bank_count < min_bank_count are suppressed.
        """
        self._increment_query_count()
        report = self._engine.compute_risk_report()
        published = []
        suppressed = 0
        for snapshot in report.corridor_snapshots:
            if snapshot.bank_count >= min_bank_count:
                published.append(snapshot)
            else:
                suppressed += 1
        return published, suppressed

    def get_corridor_trend(
        self,
        corridor_id: str,
        periods: int = 24,
    ) -> List[CorridorRiskSnapshot]:
        """Get time-series for one corridor."""
        self._increment_query_count()
        return self._engine.get_corridor_trend(corridor_id, periods)

    def get_concentration(
        self,
        dimension: str = "corridor",
    ) -> ConcentrationResult:
        """Compute HHI concentration for corridor or jurisdiction dimension.

        Extracts corridor volumes from the engine's current report.
        """
        self._increment_query_count()
        report = self._engine.compute_risk_report()
        volumes = {
            s.corridor: float(s.total_payments)
            for s in report.corridor_snapshots
        }
        if not volumes:
            volumes = {"__empty__": 1.0}

        if dimension == "jurisdiction":
            return self._concentration.compute_jurisdiction_concentration(volumes)
        return self._concentration.compute_corridor_concentration(volumes)

    def simulate_contagion(
        self,
        shock_corridor: str,
        shock_magnitude: float = 1.0,
        max_hops: int = 5,
    ) -> ContagionResult:
        """Run contagion simulation from a shock corridor.

        Builds a corridor dependency graph from the current report's
        corridor names using synthetic bank sets (real bank hash sets
        require live telemetry ingestion via RegulatoryAnonymizer).
        """
        self._increment_query_count()
        report = self._engine.compute_risk_report()
        corridors = [s.corridor for s in report.corridor_snapshots]

        # Build synthetic bank sets for graph construction.
        # Corridors sharing a currency zone share some banks.
        bank_sets: Dict[str, set] = {}
        bank_counter = 0
        currency_banks: Dict[str, set] = {}
        for corridor in corridors:
            parts = corridor.split("-")
            corridor_banks: set = set()
            for part in parts:
                if part not in currency_banks:
                    currency_banks[part] = {
                        f"SB{bank_counter + i}" for i in range(3)
                    }
                    bank_counter += 3
                corridor_banks |= currency_banks[part]
            bank_sets[corridor] = corridor_banks

        if shock_corridor not in bank_sets:
            bank_sets[shock_corridor] = {f"SB{bank_counter}"}

        sim = ContagionSimulator(max_hops=max_hops)
        graph = sim.build_dependency_graph(bank_sets)
        volumes = {
            s.corridor: float(s.total_payments)
            for s in report.corridor_snapshots
        }
        return sim.simulate(graph, shock_corridor, shock_magnitude, volumes)

    def generate_report(
        self,
        period_start: str = "",
        period_end: str = "",
    ) -> VersionedReport:
        """Generate a new versioned report from current engine state."""
        self._increment_query_count()
        report = self._engine.compute_risk_report()
        vr = create_versioned_report(
            report=report,
            period_start=period_start,
            period_end=period_end,
        )
        with self._lock:
            self._reports[vr.report_id] = vr
            if len(self._reports) > self._max_reports:
                oldest_key = min(
                    self._reports, key=lambda k: self._reports[k].generated_at
                )
                del self._reports[oldest_key]
        return vr

    def render_report(
        self,
        report_id: str,
        fmt: str = "json",
    ) -> Tuple[str | bytes, str]:
        """Render a cached report in the requested format.
        Returns (content, content_type).
        """
        vr = self.get_report(report_id)
        if vr is None:
            raise ValueError(f"Report {report_id} not found")
        if fmt == "csv":
            return self._renderer.render_csv(vr), "text/csv"
        if fmt == "pdf":
            return self._renderer.render_pdf(vr), "application/pdf"
        return self._renderer.render_json(vr), "application/json"

    def get_version_chain(self, report_id: str) -> List[VersionedReport]:
        """Trace the version history for a report.
        V0: returns single-element list. Full chain via supersedes deferred.
        """
        vr = self.get_report(report_id)
        if vr is None:
            return []
        return [vr]

    def run_stress_test(
        self,
        scenario_name: str,
        shocks: List[Tuple[str, float]],
    ) -> Tuple[str, VersionedReport]:
        """Run multi-shock stress test.

        Creates a temporary engine clone, ingests synthetic elevated-failure
        results, computes a report, and caches it. Does NOT pollute the main engine.
        """
        self._increment_query_count()

        # Create a fresh engine for the stress test.
        # Must hold the source engine's lock while copying history.
        stress_engine = SystemicRiskEngine()
        with self._engine._lock:
            for corridor, history in self._engine._history.items():
                stress_engine._history[corridor] = list(history)

        # Ingest synthetic shocks
        synthetic_results = []
        for corridor, magnitude in shocks:
            synthetic_results.append(
                AnonymizedCorridorResult(
                    corridor=corridor,
                    period_label="STRESS-TEST",
                    total_payments=1000,
                    failed_payments=int(1000 * magnitude),
                    failure_rate=magnitude,
                    bank_count=10,
                    k_anonymity_satisfied=True,
                    privacy_budget_remaining=5.0,
                    noise_applied=False,
                    stale=False,
                )
            )
        stress_engine.ingest_results(synthetic_results)

        # Compute report on stress engine
        report = stress_engine.compute_risk_report()
        vr = create_versioned_report(report=report)

        # Cache the report
        with self._lock:
            self._reports[vr.report_id] = vr
            if len(self._reports) > self._max_reports:
                oldest_key = min(
                    self._reports, key=lambda k: self._reports[k].generated_at
                )
                del self._reports[oldest_key]
        return vr.report_id, vr

    def get_report(self, report_id: str) -> Optional[VersionedReport]:
        """Retrieve cached report by ID. Returns None if expired/missing."""
        with self._lock:
            cached = self._reports.get(report_id)
            if cached is None:
                return None
            if time.time() - cached.generated_at > self._report_ttl:
                del self._reports[report_id]
                return None
            verify_report_integrity(cached)
            return cached

    def get_metadata(self) -> Dict[str, Any]:
        """Return API and data metadata."""
        report = self._engine.compute_risk_report()
        return {
            "api_version": "1.0.0",
            "data_freshness": {
                "corridors_monitored": report.total_corridors_analyzed,
                "stale_corridors": report.stale_corridor_count,
                "total_queries": self._query_count,
            },
            "methodology": {
                "k_anonymity_threshold": P10_K_ANONYMITY_THRESHOLD,
                "differential_privacy_epsilon": float(
                    P10_DIFFERENTIAL_PRIVACY_EPSILON
                ),
                "methodology_version": MethodologyAppendix.VERSION,
            },
            "rate_limit": {
                "requests_per_hour": 100,
            },
        }
