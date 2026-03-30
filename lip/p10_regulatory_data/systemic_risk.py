"""
systemic_risk.py — Systemic risk analytics engine.

Consumes AnonymizedCorridorResult objects from the Sprint 4a anonymizer
and produces systemic risk intelligence: corridor failure rate trends,
concentration metrics, and risk reports.

Thread-safe via threading.Lock (matches PortfolioRiskEngine pattern).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .concentration import CorridorConcentrationAnalyzer
from .constants import (
    P10_MAX_HISTORY_PERIODS,
    P10_TREND_RISING_THRESHOLD,
    P10_TREND_WINDOW_PERIODS,
)
from .contagion import ContagionSimulator
from .telemetry_schema import AnonymizedCorridorResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorridorRiskSnapshot:
    """Point-in-time risk summary for one corridor."""

    corridor: str
    period_label: str
    failure_rate: float
    total_payments: int
    failed_payments: int
    bank_count: int
    trend_direction: str  # "RISING", "FALLING", "STABLE"
    trend_magnitude: float  # rate of change vs prior period
    contains_stale_data: bool


@dataclass(frozen=True)
class SystemicRiskReport:
    """Full systemic risk assessment across all corridors."""

    timestamp: float
    corridor_snapshots: List[CorridorRiskSnapshot]
    overall_failure_rate: float
    highest_risk_corridor: str
    concentration_hhi: float
    systemic_risk_score: float  # 0.0-1.0
    stale_corridor_count: int
    total_corridors_analyzed: int


class SystemicRiskEngine:
    """Cross-institutional payment failure analytics.

    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: Dict[str, List[CorridorRiskSnapshot]] = defaultdict(list)
        self._concentration = CorridorConcentrationAnalyzer()
        self._contagion = ContagionSimulator()
        self._max_history = P10_MAX_HISTORY_PERIODS
        self._trend_window = P10_TREND_WINDOW_PERIODS
        self._trend_threshold = float(P10_TREND_RISING_THRESHOLD)

    def ingest_results(self, results: List[AnonymizedCorridorResult]) -> None:
        """Ingest anonymized results into the time-series history.

        Thread-safe. Each result is converted to a CorridorRiskSnapshot
        and appended to the per-corridor history.
        """
        with self._lock:
            for r in results:
                # Get current trend from existing history
                existing = self._history[r.corridor]
                direction, magnitude = self._compute_trend_from_list(
                    existing, r.failure_rate,
                )

                snapshot = CorridorRiskSnapshot(
                    corridor=r.corridor,
                    period_label=r.period_label,
                    failure_rate=r.failure_rate,
                    total_payments=r.total_payments,
                    failed_payments=r.failed_payments,
                    bank_count=r.bank_count,
                    trend_direction=direction,
                    trend_magnitude=magnitude,
                    contains_stale_data=r.stale,
                )
                self._history[r.corridor].append(snapshot)

                # Trim to max history
                if len(self._history[r.corridor]) > self._max_history:
                    self._history[r.corridor] = self._history[r.corridor][
                        -self._max_history :
                    ]

    def compute_risk_report(self) -> SystemicRiskReport:
        """Compute full systemic risk report from accumulated history.

        Thread-safe.
        """
        with self._lock:
            if not self._history:
                return SystemicRiskReport(
                    timestamp=time.time(),
                    corridor_snapshots=[],
                    overall_failure_rate=0.0,
                    highest_risk_corridor="",
                    concentration_hhi=0.0,
                    systemic_risk_score=0.0,
                    stale_corridor_count=0,
                    total_corridors_analyzed=0,
                )

            # Get latest snapshot per corridor
            latest_snapshots: List[CorridorRiskSnapshot] = []
            corridor_volumes: Dict[str, float] = {}
            stale_count = 0
            total_payments_all = 0
            total_failed_all = 0

            for corridor, history in self._history.items():
                if not history:
                    continue
                latest = history[-1]
                # Recompute trend with full history
                direction, magnitude = self.compute_trend_direction(history)
                snapshot = CorridorRiskSnapshot(
                    corridor=latest.corridor,
                    period_label=latest.period_label,
                    failure_rate=latest.failure_rate,
                    total_payments=latest.total_payments,
                    failed_payments=latest.failed_payments,
                    bank_count=latest.bank_count,
                    trend_direction=direction,
                    trend_magnitude=magnitude,
                    contains_stale_data=latest.contains_stale_data,
                )
                latest_snapshots.append(snapshot)
                corridor_volumes[corridor] = float(latest.total_payments)
                total_payments_all += latest.total_payments
                total_failed_all += latest.failed_payments
                if latest.contains_stale_data:
                    stale_count += 1

            # Overall failure rate (volume-weighted)
            overall_rate = (
                total_failed_all / total_payments_all
                if total_payments_all > 0
                else 0.0
            )

            # Highest risk corridor
            highest_risk = max(latest_snapshots, key=lambda s: s.failure_rate)

            # Concentration HHI
            conc_result = self._concentration.compute_corridor_concentration(
                corridor_volumes,
            )

            # Systemic risk score = failure_rate * (1 + concentration_penalty)
            concentration_penalty = max(0.0, conc_result.hhi - 0.25)
            systemic_score = min(1.0, overall_rate * (1.0 + concentration_penalty))

            return SystemicRiskReport(
                timestamp=time.time(),
                corridor_snapshots=latest_snapshots,
                overall_failure_rate=overall_rate,
                highest_risk_corridor=highest_risk.corridor,
                concentration_hhi=conc_result.hhi,
                systemic_risk_score=systemic_score,
                stale_corridor_count=stale_count,
                total_corridors_analyzed=len(latest_snapshots),
            )

    def get_corridor_trend(
        self,
        corridor: str,
        periods: int = 24,
    ) -> List[CorridorRiskSnapshot]:
        """Return last N periods of risk snapshots for a corridor."""
        with self._lock:
            history = self._history.get(corridor, [])
            return list(history[-periods:])

    def compute_trend_direction(
        self,
        snapshots: List[CorridorRiskSnapshot],
    ) -> Tuple[str, float]:
        """Compute RISING/FALLING/STABLE + magnitude from recent snapshots.

        Compares average failure rate of last ``trend_window`` periods
        against prior ``trend_window`` periods.
        """
        window = self._trend_window
        if len(snapshots) < window * 2:
            return ("STABLE", 0.0)

        recent = snapshots[-window:]
        prior = snapshots[-(window * 2) : -window]

        recent_avg = sum(s.failure_rate for s in recent) / len(recent)
        prior_avg = sum(s.failure_rate for s in prior) / len(prior)

        if prior_avg == 0:
            return ("STABLE", 0.0)

        magnitude = (recent_avg - prior_avg) / prior_avg

        if magnitude > self._trend_threshold:
            return ("RISING", magnitude)
        elif magnitude < -self._trend_threshold:
            return ("FALLING", magnitude)
        else:
            return ("STABLE", magnitude)

    def clear_history(self) -> None:
        """Reset all accumulated data."""
        with self._lock:
            self._history.clear()

    def _compute_trend_from_list(
        self,
        history: List[CorridorRiskSnapshot],
        new_rate: float,
    ) -> Tuple[str, float]:
        """Compute trend including a hypothetical new rate."""
        window = self._trend_window
        if len(history) < window * 2 - 1:
            return ("STABLE", 0.0)

        # Prior window from history
        prior = (
            history[-(window * 2 - 1) : -(window - 1)]
            if len(history) >= window * 2 - 1
            else []
        )
        if len(prior) < window:
            return ("STABLE", 0.0)

        # Recent window = last (window-1) from history + new_rate
        recent_from_hist = history[-(window - 1) :]
        recent_rates = [s.failure_rate for s in recent_from_hist] + [new_rate]

        recent_avg = sum(recent_rates) / len(recent_rates)
        prior_avg = sum(s.failure_rate for s in prior) / len(prior)

        if prior_avg == 0:
            return ("STABLE", 0.0)

        magnitude = (recent_avg - prior_avg) / prior_avg

        if magnitude > self._trend_threshold:
            return ("RISING", magnitude)
        elif magnitude < -self._trend_threshold:
            return ("FALLING", magnitude)
        else:
            return ("STABLE", magnitude)
