"""
report_metadata.py — Versioned regulatory report dataclass.

Sprint 5: Immutable report with content hash integrity.
Wraps SystemicRiskReport (Sprint 4b) with version tracking.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from lip.p10_regulatory_data.systemic_risk import SystemicRiskReport


class ReportIntegrityError(Exception):
    """Raised when a report's content hash does not match its stored hash."""


@dataclass(frozen=True)
class VersionedReport:
    """Immutable versioned regulatory report."""

    report_id: str
    version: str
    generated_at: float
    period_start: str
    period_end: str
    methodology_version: str
    content_hash: str
    report: SystemicRiskReport
    supersedes: Optional[str] = None
    hmac_signature: Optional[str] = None


def _compute_content_hash(report: SystemicRiskReport) -> str:
    """SHA-256 over deterministic JSON serialization of the report.

    B8-13: ``report.timestamp`` is deliberately excluded. Timestamp is a
    generation-time metadata field, not report content — including it would
    make two reports with identical analytical findings produce different
    hashes just because they were generated at different wall-clock times,
    breaking content-level deduplication and audit comparison.
    """
    data = {
        "overall_failure_rate": report.overall_failure_rate,
        "highest_risk_corridor": report.highest_risk_corridor,
        "concentration_hhi": report.concentration_hhi,
        "systemic_risk_score": report.systemic_risk_score,
        "stale_corridor_count": report.stale_corridor_count,
        "total_corridors_analyzed": report.total_corridors_analyzed,
        "corridor_snapshots": [
            {
                "corridor": s.corridor,
                "period_label": s.period_label,
                "failure_rate": s.failure_rate,
                "total_payments": s.total_payments,
                "failed_payments": s.failed_payments,
                "bank_count": s.bank_count,
                "trend_direction": s.trend_direction,
                "trend_magnitude": s.trend_magnitude,
                "contains_stale_data": s.contains_stale_data,
            }
            for s in report.corridor_snapshots
        ],
    }
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def create_versioned_report(
    report: SystemicRiskReport,
    version: str = "1.0",
    supersedes: Optional[str] = None,
    period_start: str = "",
    period_end: str = "",
) -> VersionedReport:
    """Factory that builds a VersionedReport with computed content hash."""
    from lip.p10_regulatory_data.methodology import MethodologyAppendix

    return VersionedReport(
        report_id=f"RPT-{uuid.uuid4().hex[:12].upper()}",
        version=version,
        generated_at=time.time(),
        period_start=period_start,
        period_end=period_end,
        methodology_version=MethodologyAppendix.VERSION,
        content_hash=_compute_content_hash(report),
        report=report,
        supersedes=supersedes,
    )


def verify_report_integrity(vr: VersionedReport) -> bool:
    """Verify content hash matches. Raises ReportIntegrityError on mismatch."""
    expected = _compute_content_hash(vr.report)
    if vr.content_hash != expected:
        raise ReportIntegrityError(
            f"Report {vr.report_id} integrity check failed: "
            f"expected {expected}, got {vr.content_hash}"
        )
    return True
