"""vendor_validator.py — Catch rubber-stamp vendors before onboarding.

Prevents the Delve failure mode where a "compliance certifier" pre-writes
audit conclusions, uses captive auditors, and ships 493/494 identical
boilerplate reports. Four structural checks:

  1. Independence: implementer ≠ examiner. Same entity producing AND
     auditing the work is a structural conflict of interest.

  2. Boilerplate: Jaccard similarity >90% across the same vendor's reports
     for different clients = templated, not real audit work.

  3. Freshness: report_issued_at must be after observation_period_end.
     Conclusions written before the observation period was over are
     fabricated by definition.

  4. Zero-incident anomaly: a vendor whose reports claim zero incidents
     across >95% of clients is statistically suspicious. Real audits find
     things; the Delve pattern was every report claiming perfection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from lip.integrity.compliance_enforcer import (
    DEFAULT_BOILERPLATE_THRESHOLD,
    BoilerplateResult,
    jaccard_similarity,
)

# Default threshold; matches the constant added to lip/common/constants.py.
DEFAULT_ZERO_INCIDENT_THRESHOLD = 0.95


# ---------------------------------------------------------------------------
# Enums + models
# ---------------------------------------------------------------------------


class VendorType(str, Enum):
    COMPLIANCE_CERTIFIER = "COMPLIANCE_CERTIFIER"
    AUDITOR = "AUDITOR"
    INFRA_PROVIDER = "INFRA_PROVIDER"
    DATA_VENDOR = "DATA_VENDOR"
    SOFTWARE_VENDOR = "SOFTWARE_VENDOR"


class VendorReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    vendor_id: str
    vendor_name: str
    vendor_type: VendorType
    client_name: str
    observation_period_start: datetime
    observation_period_end: datetime
    report_issued_at: datetime
    conclusions: list[str] = Field(default_factory=list)
    incidents_found: int = 0
    report_text: str = ""


class VendorIndependenceCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor_id: str
    implementer_entity: str
    examiner_entity: str
    relationship_flags: list[str] = Field(default_factory=list)

    @property
    def is_independent(self) -> bool:
        return self.implementer_entity.strip().lower() != self.examiner_entity.strip().lower()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceFreshnessResult:
    is_fresh: bool
    report_date: datetime
    observation_end: datetime
    gap_hours: float
    issue: str | None


@dataclass(frozen=True)
class ZeroIncidentResult:
    is_anomalous: bool
    vendor_id: str
    total_reports: int
    reports_with_zero_incidents: int
    zero_incident_ratio: float


@dataclass(frozen=True)
class VendorValidationResult:
    vendor_id: str
    passes: bool
    independence_ok: bool
    boilerplate_ok: bool
    freshness_ok: bool
    incident_pattern_ok: bool
    issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class VendorIntegrityValidator:
    """Runs the four structural checks against a vendor report."""

    def __init__(
        self,
        boilerplate_threshold: float = DEFAULT_BOILERPLATE_THRESHOLD,
        zero_incident_threshold: float = DEFAULT_ZERO_INCIDENT_THRESHOLD,
    ) -> None:
        self._boilerplate_threshold = boilerplate_threshold
        self._zero_incident_threshold = zero_incident_threshold

    # -- 1. Independence ---------------------------------------------------

    def check_independence(self, check: VendorIndependenceCheck) -> bool:
        """Return True if the implementer and examiner are distinct entities."""
        return check.is_independent

    # -- 2. Boilerplate ----------------------------------------------------

    def detect_report_boilerplate(
        self,
        report: VendorReport,
        corpus: list[VendorReport],
    ) -> BoilerplateResult:
        """Compare *report* against other reports in *corpus* (excluding itself).

        Flags as boilerplate if any other report has Jaccard similarity
        above ``boilerplate_threshold``. The corpus is filtered to other
        clients of the same vendor — that is the Delve pattern.
        """
        peers = [
            r
            for r in corpus
            if r.vendor_id == report.vendor_id and r.report_id != report.report_id
        ]
        if not peers:
            return BoilerplateResult(
                is_boilerplate=False,
                max_similarity=0.0,
                most_similar_report_id=None,
                unique_content_ratio=1.0,
            )

        best_id: str | None = None
        best_sim = 0.0
        for p in peers:
            sim = jaccard_similarity(report.report_text, p.report_text)
            if sim > best_sim:
                best_sim = sim
                best_id = p.report_id

        return BoilerplateResult(
            is_boilerplate=best_sim > self._boilerplate_threshold,
            max_similarity=best_sim,
            most_similar_report_id=best_id,
            unique_content_ratio=1.0 - best_sim,
        )

    # -- 3. Freshness ------------------------------------------------------

    def check_evidence_freshness(self, report: VendorReport) -> EvidenceFreshnessResult:
        """Reject if report_issued_at < observation_period_end."""
        gap = report.report_issued_at - report.observation_period_end
        gap_hours = gap.total_seconds() / 3600.0
        if gap_hours < 0:
            return EvidenceFreshnessResult(
                is_fresh=False,
                report_date=report.report_issued_at,
                observation_end=report.observation_period_end,
                gap_hours=gap_hours,
                issue=(
                    f"Report issued {-gap_hours:.1f}h BEFORE the observation period "
                    "ended — conclusions are fabricated by definition."
                ),
            )
        return EvidenceFreshnessResult(
            is_fresh=True,
            report_date=report.report_issued_at,
            observation_end=report.observation_period_end,
            gap_hours=gap_hours,
            issue=None,
        )

    # -- 4. Zero-incident anomaly -----------------------------------------

    def check_zero_incidents_anomaly(
        self,
        vendor_id: str,
        reports: list[VendorReport],
    ) -> ZeroIncidentResult:
        """Flag if >95% of a vendor's reports claim zero incidents."""
        vendor_reports = [r for r in reports if r.vendor_id == vendor_id]
        total = len(vendor_reports)
        if total == 0:
            return ZeroIncidentResult(
                is_anomalous=False,
                vendor_id=vendor_id,
                total_reports=0,
                reports_with_zero_incidents=0,
                zero_incident_ratio=0.0,
            )
        zeros = sum(1 for r in vendor_reports if r.incidents_found == 0)
        ratio = zeros / total
        return ZeroIncidentResult(
            is_anomalous=ratio >= self._zero_incident_threshold,
            vendor_id=vendor_id,
            total_reports=total,
            reports_with_zero_incidents=zeros,
            zero_incident_ratio=ratio,
        )

    # -- aggregate --------------------------------------------------------

    def validate_vendor(
        self,
        report: VendorReport,
        corpus: list[VendorReport],
        independence: VendorIndependenceCheck,
    ) -> VendorValidationResult:
        """Run all four checks and return the aggregate result.

        ``passes`` is True iff every individual check passes. The corpus
        for boilerplate detection should include the report itself plus its
        peers; for the zero-incident check, the corpus should include all
        of the vendor's reports across clients.
        """
        issues: list[str] = []

        independence_ok = self.check_independence(independence)
        if not independence_ok:
            issues.append(
                f"vendor {report.vendor_id}: implementer == examiner "
                f"({independence.implementer_entity})"
            )

        boilerplate_result = self.detect_report_boilerplate(report, corpus)
        boilerplate_ok = not boilerplate_result.is_boilerplate
        if not boilerplate_ok:
            issues.append(
                f"report {report.report_id}: {boilerplate_result.max_similarity:.2%} "
                f"similar to {boilerplate_result.most_similar_report_id}"
            )

        freshness_result = self.check_evidence_freshness(report)
        freshness_ok = freshness_result.is_fresh
        if not freshness_ok and freshness_result.issue:
            issues.append(freshness_result.issue)

        incident_result = self.check_zero_incidents_anomaly(report.vendor_id, corpus)
        incident_pattern_ok = not incident_result.is_anomalous
        if not incident_pattern_ok:
            issues.append(
                f"vendor {report.vendor_id}: zero-incident ratio "
                f"{incident_result.zero_incident_ratio:.2%} across "
                f"{incident_result.total_reports} reports — anomalous."
            )

        return VendorValidationResult(
            vendor_id=report.vendor_id,
            passes=all(
                [independence_ok, boilerplate_ok, freshness_ok, incident_pattern_ok]
            ),
            independence_ok=independence_ok,
            boilerplate_ok=boilerplate_ok,
            freshness_ok=freshness_ok,
            incident_pattern_ok=incident_pattern_ok,
            issues=issues,
        )
