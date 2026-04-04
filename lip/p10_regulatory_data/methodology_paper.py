"""
methodology_paper.py — Auto-generated methodology documentation for regulators.

Sprint 8: Generates a structured methodology document from P10 code constants
and module metadata. For regulator review during OSFI sandbox onboarding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lip.common.constants import (
    P10_AMOUNT_BUCKET_THRESHOLDS,
    P10_AMOUNT_BUCKETS,
    P10_CIRCULAR_EXPOSURE_MAX_LENGTH,
    P10_CIRCULAR_EXPOSURE_MIN_WEIGHT,
    P10_CONTAGION_MAX_HOPS,
    P10_CONTAGION_PROPAGATION_DECAY,
    P10_CONTAGION_STRESS_THRESHOLD,
    P10_DIFFERENTIAL_PRIVACY_EPSILON,
    P10_HHI_CONCENTRATION_THRESHOLD,
    P10_K_ANONYMITY_THRESHOLD,
    P10_MAX_HISTORY_PERIODS,
    P10_PRIVACY_BUDGET_CYCLE_DAYS,
    P10_PRIVACY_BUDGET_PER_CYCLE,
    P10_TELEMETRY_MIN_AMOUNT_USD,
    P10_TIMESTAMP_BUCKET_HOURS,
    P10_TREND_RISING_THRESHOLD,
    P10_TREND_WINDOW_PERIODS,
    SALT_ROTATION_DAYS,
    SALT_ROTATION_OVERLAP_DAYS,
)
from lip.p10_regulatory_data.methodology import MethodologyAppendix


@dataclass(frozen=True)
class MethodologyPaper:
    """Structured methodology document for regulator review."""

    version: str
    sections: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "sections": self.sections}

    def to_markdown(self) -> str:
        lines = [
            "# P10 Regulatory Data Product — Methodology Paper",
            "",
            f"**Version:** {self.version}",
            "",
        ]
        for title, content in self.sections.items():
            lines.append(f"## {title}")
            lines.append("")
            if isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"- **{k}:** {v}")
            elif isinstance(content, list):
                for item in content:
                    lines.append(f"- {item}")
            else:
                lines.append(str(content))
            lines.append("")
        return "\n".join(lines)


def generate_methodology_paper() -> MethodologyPaper:
    """Generate methodology paper from code constants and module metadata."""
    sections: dict[str, Any] = {}

    sections["1. Data Collection"] = {
        "Collection Frequency": f"Every {P10_TIMESTAMP_BUCKET_HOURS} hour(s)",
        "Minimum Payment Amount": f"${P10_TELEMETRY_MIN_AMOUNT_USD} USD",
        "Amount Buckets": ", ".join(P10_AMOUNT_BUCKETS),
        "Amount Bucket Thresholds": ", ".join(
            f"${t:,.0f}" for t in P10_AMOUNT_BUCKET_THRESHOLDS
        ),
        "Maximum History": (
            f"{P10_MAX_HISTORY_PERIODS} periods "
            f"({P10_MAX_HISTORY_PERIODS // 24} days)"
        ),
    }

    sections["2. Anonymization Layers"] = {
        "Layer 1 — Entity Hashing": (
            f"SHA-256 with rotating salt. "
            f"Salt rotation: every {SALT_ROTATION_DAYS} days, "
            f"{SALT_ROTATION_OVERLAP_DAYS}-day overlap for migration."
        ),
        "Layer 2 — k-Anonymity": (
            f"Suppression-based. k = {P10_K_ANONYMITY_THRESHOLD}. "
            f"Corridors with fewer than {P10_K_ANONYMITY_THRESHOLD} "
            f"distinct bank entities are suppressed entirely."
        ),
        "Layer 3 — Differential Privacy": (
            f"Laplace mechanism. epsilon = {P10_DIFFERENTIAL_PRIVACY_EPSILON}. "
            f"Noise scale b = sensitivity / epsilon. "
            f"Applied to failure rates and payment counts."
        ),
    }

    sections["3. Statistical Methodology"] = {
        "Failure Rate": (
            "failed_payments / total_payments per corridor per period"
        ),
        "HHI Concentration": (
            f"Herfindahl-Hirschman Index. "
            f"Threshold: {P10_HHI_CONCENTRATION_THRESHOLD}. "
            f"Computed per corridor and per jurisdiction."
        ),
        "Trend Detection": (
            f"Rising threshold: {P10_TREND_RISING_THRESHOLD} "
            f"over {P10_TREND_WINDOW_PERIODS} periods."
        ),
        "Contagion Simulation": (
            f"BFS propagation from shock corridor. "
            f"Decay factor: {P10_CONTAGION_PROPAGATION_DECAY}. "
            f"Max hops: {P10_CONTAGION_MAX_HOPS}. "
            f"Stress threshold: {P10_CONTAGION_STRESS_THRESHOLD}."
        ),
        "Circular Exposure": (
            f"DFS cycle detection. "
            f"Min edge weight: {P10_CIRCULAR_EXPOSURE_MIN_WEIGHT}. "
            f"Max cycle length: {P10_CIRCULAR_EXPOSURE_MAX_LENGTH}."
        ),
    }

    sections["4. Privacy Guarantees"] = {
        "Epsilon-Differential Privacy": (
            f"Each query consumes epsilon = {P10_DIFFERENTIAL_PRIVACY_EPSILON} "
            f"from corridor budget. Sequential composition theorem: "
            f"total privacy loss = sum of per-query epsilon."
        ),
        "Budget Lifecycle": (
            f"Budget per cycle: {P10_PRIVACY_BUDGET_PER_CYCLE}. "
            f"Cycle duration: {P10_PRIVACY_BUDGET_CYCLE_DAYS} days. "
            f"Max queries per corridor per cycle: "
            f"{int(P10_PRIVACY_BUDGET_PER_CYCLE / P10_DIFFERENTIAL_PRIVACY_EPSILON)}."
        ),
        "Exhaustion Behavior": (
            "When budget is exhausted, system serves stale cached results. "
            "No new noise is applied, preserving the privacy guarantee."
        ),
    }

    sections["5. Limitations"] = [
        (
            f"Requires minimum {P10_K_ANONYMITY_THRESHOLD} banks per corridor "
            f"for any output."
        ),
        (
            "12-month shadow period required before commercial launch "
            "for statistical validation."
        ),
        (
            "Re-identification residual risk exists if adversary "
            "has strong auxiliary data."
        ),
        "Corridor failure rates may diverge from BIS benchmarks with < 10 banks.",
        (
            "Budget exhaustion limits query frequency to ~10 per corridor "
            "per 30-day cycle."
        ),
    ]

    sections["6. Constants Reference"] = {
        "P10_K_ANONYMITY_THRESHOLD": str(P10_K_ANONYMITY_THRESHOLD),
        "P10_DIFFERENTIAL_PRIVACY_EPSILON": str(P10_DIFFERENTIAL_PRIVACY_EPSILON),
        "P10_PRIVACY_BUDGET_PER_CYCLE": str(P10_PRIVACY_BUDGET_PER_CYCLE),
        "P10_PRIVACY_BUDGET_CYCLE_DAYS": str(P10_PRIVACY_BUDGET_CYCLE_DAYS),
        "P10_TIMESTAMP_BUCKET_HOURS": str(P10_TIMESTAMP_BUCKET_HOURS),
        "P10_TELEMETRY_MIN_AMOUNT_USD": str(P10_TELEMETRY_MIN_AMOUNT_USD),
        "P10_CONTAGION_MAX_HOPS": str(P10_CONTAGION_MAX_HOPS),
        "P10_CONTAGION_PROPAGATION_DECAY": str(P10_CONTAGION_PROPAGATION_DECAY),
        "P10_CONTAGION_STRESS_THRESHOLD": str(P10_CONTAGION_STRESS_THRESHOLD),
        "P10_HHI_CONCENTRATION_THRESHOLD": str(P10_HHI_CONCENTRATION_THRESHOLD),
        "P10_TREND_RISING_THRESHOLD": str(P10_TREND_RISING_THRESHOLD),
        "P10_TREND_WINDOW_PERIODS": str(P10_TREND_WINDOW_PERIODS),
        "P10_MAX_HISTORY_PERIODS": str(P10_MAX_HISTORY_PERIODS),
        "P10_CIRCULAR_EXPOSURE_MIN_WEIGHT": str(P10_CIRCULAR_EXPOSURE_MIN_WEIGHT),
        "P10_CIRCULAR_EXPOSURE_MAX_LENGTH": str(P10_CIRCULAR_EXPOSURE_MAX_LENGTH),
        "SALT_ROTATION_DAYS": str(SALT_ROTATION_DAYS),
        "SALT_ROTATION_OVERLAP_DAYS": str(SALT_ROTATION_OVERLAP_DAYS),
    }

    return MethodologyPaper(
        version=MethodologyAppendix.VERSION,
        sections=sections,
    )
