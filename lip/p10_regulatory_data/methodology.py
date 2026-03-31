"""
methodology.py — P10 analytical methodology appendix.

Static template attached to every regulatory report. Version-tracked
independently — methodology version bumps when any analytical method changes.
"""
from __future__ import annotations

from typing import Dict


class MethodologyAppendix:
    """P10 methodology documentation template.

    Version-tracked independently from reports. When methodology changes,
    version bumps and all subsequent reports reference the new version.
    """

    VERSION = "P10-METH-v1.0"

    _SECTIONS: Dict[str, str] = {
        "data_collection": (
            "Data is collected from anonymized telemetry feeds across enrolled "
            "banks. Entity identifiers are hashed using SHA-256 with a rotating "
            "salt (365-day rotation, 30-day overlap). Corridor-level statistics "
            "are subject to k-anonymity suppression (k >= 5): corridors with "
            "fewer than 5 contributing banks are excluded from published results. "
            "Differential privacy noise (Laplace mechanism, epsilon = 0.5) is "
            "applied to failure rate statistics to prevent inference attacks."
        ),
        "corridor_failure_rate": (
            "Failure rates are computed as volume-weighted ratios of failed "
            "payments to total payments per corridor per period. Periods are "
            "1-hour windows. Trend detection compares the average failure rate "
            "over the most recent 3 periods against the prior 3 periods. A "
            "relative change exceeding +10% is classified as RISING, below "
            "-10% as FALLING, and within +/-10% as STABLE."
        ),
        "concentration_analysis": (
            "Concentration is measured using the Herfindahl-Hirschman Index "
            "(HHI) on a 0.0 to 1.0 scale, where 1.0 indicates a single "
            "corridor or jurisdiction captures all volume. The effective count "
            "equals 1/HHI. A corridor or jurisdiction is flagged as concentrated "
            "when HHI >= 0.25 (equivalent to fewer than 4 equally-sized "
            "entities). Both corridor-level and jurisdiction-level HHI are "
            "computed; jurisdictions are derived by splitting corridor pairs "
            "(e.g., EUR-USD assigns half volume to EUR, half to USD)."
        ),
        "contagion_simulation": (
            "Contagion is modeled via breadth-first search (BFS) propagation on "
            "a corridor dependency graph. Edge weights are Jaccard similarity "
            "coefficients between the bank sets of connected corridors. Stress "
            "propagates with a per-hop decay factor of 0.7 and is pruned when "
            "the propagated stress level falls below 0.05. Maximum propagation "
            "depth is 5 hops. The systemic risk score from contagion equals "
            "the volume-weighted sum of stress levels across all affected "
            "corridors, clamped to [0, 1]."
        ),
        "systemic_risk_score": (
            "The overall systemic risk score combines the volume-weighted "
            "failure rate with a concentration penalty: "
            "score = weighted_failure_rate * (1 + max(0, HHI - 0.25)), "
            "clamped to the range [0.0, 1.0]. This penalizes systems where "
            "high failure rates coincide with concentrated corridor volumes."
        ),
        "data_quality": (
            "Each corridor snapshot is flagged if it contains stale data "
            "(telemetry older than the current aggregation window). The total "
            "count of stale corridors is reported alongside the corridor count. "
            "Suppressed corridors (below k-anonymity threshold) are counted "
            "but not published. Privacy budget consumption (cumulative epsilon) "
            "is tracked per reporting cycle."
        ),
        "limitations": (
            "In the current version (v0), corridor dependency graphs use "
            "synthetic bank sets derived from shared currency zones. Real bank "
            "hash sets require live telemetry ingestion across 5+ enrolled "
            "banks. Minimum 5 banks per corridor are required for k-anonymity "
            "compliance. Correlation structure between corridors is approximated "
            "via Jaccard similarity of bank sets, which may underestimate true "
            "dependencies in corridors sharing non-bank intermediaries."
        ),
    }

    @classmethod
    def get_text(cls) -> str:
        """Full methodology text for report appendix."""
        parts = []
        for title, body in cls._SECTIONS.items():
            heading = title.replace("_", " ").title()
            parts.append(f"{heading}\n{body}")
        return "\n\n".join(parts)

    @classmethod
    def get_sections(cls) -> Dict[str, str]:
        """Methodology as named sections for JSON embedding."""
        return dict(cls._SECTIONS)
