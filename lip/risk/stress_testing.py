"""
stress_testing.py — Stress scenario framework and automated reporting.
Generates daily VaR reports for bank risk committees.

Integrates:
  - MonteCarloVaREngine for loss simulation
  - PortfolioRiskEngine for concentration metrics
  - StressScenarios for multi-scenario analysis
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lip.risk.var_monte_carlo import (
    STRESS_SCENARIOS,
    MCPosition,
    MonteCarloVaREngine,
    MonteCarloVaRResult,
    StressScenario,
)

logger = logging.getLogger(__name__)


@dataclass
class DailyVaRReport:
    """Automated daily VaR report for risk committee.

    Attributes:
        report_date: Date of the report (UTC).
        baseline_var: Baseline (unstressed) VaR result.
        stressed_results: VaR results per stress scenario.
        total_exposure_usd: Total portfolio exposure.
        position_count: Number of active positions.
        top_concentrations: Top-5 corridor concentrations by exposure.
        generated_at: Timestamp of report generation.
        computation_time_ms: Total computation time.
    """
    report_date: str
    baseline_var: Dict[str, Any]
    stressed_results: Dict[str, Dict[str, Any]]
    total_exposure_usd: str
    position_count: int
    top_concentrations: List[Dict[str, str]]
    generated_at: str
    computation_time_ms: float


def generate_daily_var_report(
    positions: List[MCPosition],
    num_simulations: int = 10_000,
    correlation: float = 0.20,
    scenarios: Optional[List[StressScenario]] = None,
) -> DailyVaRReport:
    """Generate a daily VaR report across stress scenarios.

    Parameters
    ----------
    positions:
        Active portfolio positions.
    num_simulations:
        Monte Carlo simulation count.
    correlation:
        Default correlation for copula model.
    scenarios:
        Stress scenarios to run (defaults to STRESS_SCENARIOS).

    Returns
    -------
    DailyVaRReport
    """
    t0 = time.perf_counter()
    now = datetime.now(timezone.utc)

    engine = MonteCarloVaREngine(
        num_simulations=num_simulations,
        default_correlation=correlation,
    )

    # Baseline VaR
    baseline = engine.compute_var(positions)

    # Stressed VaR
    if scenarios is None:
        scenarios = STRESS_SCENARIOS
    stressed = engine.run_stress_tests(positions, scenarios)

    # Concentration analysis
    corridor_exposure: Dict[str, float] = {}
    for pos in positions:
        corridor_exposure[pos.corridor] = corridor_exposure.get(pos.corridor, 0.0) + pos.principal
    total = sum(corridor_exposure.values()) or 1.0
    top_5 = sorted(corridor_exposure.items(), key=lambda x: x[1], reverse=True)[:5]
    top_concentrations = [
        {"corridor": c, "exposure_usd": f"{e:.2f}", "pct": f"{e/total*100:.1f}%"}
        for c, e in top_5
    ]

    computation_ms = (time.perf_counter() - t0) * 1000.0

    return DailyVaRReport(
        report_date=now.strftime("%Y-%m-%d"),
        baseline_var=_var_to_dict(baseline),
        stressed_results={name: _var_to_dict(result) for name, result in stressed.items()},
        total_exposure_usd=str(baseline.total_exposure),
        position_count=baseline.position_count,
        top_concentrations=top_concentrations,
        generated_at=now.isoformat(),
        computation_time_ms=round(computation_ms, 3),
    )


def _var_to_dict(result: MonteCarloVaRResult) -> Dict[str, Any]:
    """Convert MonteCarloVaRResult to a JSON-serializable dict."""
    return {
        "var_95_usd": str(result.var_95),
        "var_99_usd": str(result.var_99),
        "var_999_usd": str(result.var_999),
        "expected_shortfall_99_usd": str(result.expected_shortfall_99),
        "expected_loss_usd": str(result.expected_loss),
        "total_exposure_usd": str(result.total_exposure),
        "position_count": result.position_count,
        "correlation": result.correlation,
        "num_simulations": result.num_simulations,
        "computation_time_ms": result.computation_time_ms,
        "loss_distribution": result.loss_distribution_percentiles,
    }


def export_var_report_json(report: DailyVaRReport) -> str:
    """Serialize a DailyVaRReport to JSON."""
    return json.dumps(asdict(report), indent=2, default=str)


def export_var_report_csv(report: DailyVaRReport) -> str:
    """Serialize a DailyVaRReport to CSV (one row per scenario)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "report_date", "scenario", "var_95_usd", "var_99_usd", "var_999_usd",
        "expected_shortfall_99_usd", "expected_loss_usd", "total_exposure_usd",
        "position_count", "correlation", "num_simulations",
    ])

    # Baseline row
    b = report.baseline_var
    writer.writerow([
        report.report_date, "BASELINE",
        b.get("var_95_usd"), b.get("var_99_usd"), b.get("var_999_usd"),
        b.get("expected_shortfall_99_usd"), b.get("expected_loss_usd"),
        b.get("total_exposure_usd"), b.get("position_count"),
        b.get("correlation"), b.get("num_simulations"),
    ])

    # Stressed rows
    for scenario_name, s in report.stressed_results.items():
        writer.writerow([
            report.report_date, scenario_name,
            s.get("var_95_usd"), s.get("var_99_usd"), s.get("var_999_usd"),
            s.get("expected_shortfall_99_usd"), s.get("expected_loss_usd"),
            s.get("total_exposure_usd"), s.get("position_count"),
            s.get("correlation"), s.get("num_simulations"),
        ])

    return output.getvalue()
