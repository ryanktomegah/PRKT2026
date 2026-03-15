"""
regulatory_reporter.py — Regulatory reporting formats for LIP.
GAP-14: Production bridge-lending platforms require machine-readable
        audit events for two distinct regulatory regimes:

  DORA Article 19 (EU Digital Operational Resilience Act):
    Major ICT incidents must be reported within 4 hours of classification.
    Significant incidents within 24 hours.
    LIP generates DORAAuditEvent records for every material operational
    disruption (kill-switch activations, AML blocks, system degradations).

  Fed SR 11-7 (Supervisory Guidance on Model Risk Management):
    All deployed ML models must have documented validation reports covering
    AUC/performance metrics, feature counts, and approval status.
    LIP generates SR117ModelValidationReport records for C1, C2, and C4.

Architecture note:
  RegulatoryReporter is a pure in-process registry — it does not transmit
  to regulatory APIs directly.  The BPI compliance team retrieves records
  via the admin router and submits them through their own channels.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DORA constants (Article 19)
# ---------------------------------------------------------------------------

DORA_MAJOR_REPORTING_THRESHOLD_HOURS: int = 4
"""DORA Article 19: major ICT incidents must be reported within 4 hours."""

DORA_SIGNIFICANT_REPORTING_THRESHOLD_HOURS: int = 24
"""DORA Article 19: significant incidents reported within 24 hours."""

# SR 11-7 minimum validation AUC for production deployment
SR117_MINIMUM_AUC: float = 0.75


# ---------------------------------------------------------------------------
# DORA audit event
# ---------------------------------------------------------------------------

class DORASeverity(str, Enum):
    """DORA Article 18 severity classification for ICT incidents."""

    MAJOR = "MAJOR"
    """Requires 4-hour initial report to competent authority."""

    SIGNIFICANT = "SIGNIFICANT"
    """Requires 24-hour initial report."""

    MINOR = "MINOR"
    """Internal record only; no regulatory filing required."""


@dataclass
class DORAAuditEvent:
    """DORA Article 19 ICT incident record for regulatory reporting.

    Attributes
    ----------
    incident_id:
        UUID string; unique per event.
    uetr:
        SWIFT UETR of the payment associated with this incident, if any.
    event_type:
        Machine-readable incident category (e.g. ``"KILL_SWITCH_ACTIVATED"``).
    severity:
        :class:`DORASeverity` classification.
    description:
        Human-readable description for the regulatory filing.
    occurred_at:
        UTC timestamp when the incident was first observed.
    reported_at:
        UTC timestamp when this record was created by LIP.
    threshold_hours:
        Reporting deadline in hours from occurred_at
        (4 for MAJOR, 24 for SIGNIFICANT).
    is_reportable:
        True for MAJOR and SIGNIFICANT — False for MINOR (internal only).
    """

    incident_id: str
    uetr: Optional[str]
    event_type: str
    severity: DORASeverity
    description: str
    occurred_at: datetime
    reported_at: datetime
    threshold_hours: int
    is_reportable: bool

    @property
    def within_threshold(self) -> bool:
        """True when reported_at is within threshold_hours of occurred_at."""
        delta_hours = (self.reported_at - self.occurred_at).total_seconds() / 3600
        return delta_hours <= self.threshold_hours

    @property
    def hours_to_deadline(self) -> float:
        """Hours remaining before the regulatory reporting deadline."""
        elapsed = (self.reported_at - self.occurred_at).total_seconds() / 3600
        return max(0.0, self.threshold_hours - elapsed)


# ---------------------------------------------------------------------------
# SR 11-7 model validation report
# ---------------------------------------------------------------------------

@dataclass
class SR117ModelValidationReport:
    """Fed SR 11-7 model validation record for LIP ML components.

    Attributes
    ----------
    report_id:
        UUID string; unique per validation run.
    model_id:
        Artefact version tag of the model being validated.
    component:
        LIP component identifier, e.g. ``"C1_FAILURE_CLASSIFIER"``.
    validation_date:
        UTC date of the validation run.
    auc_score:
        Achieved AUC on the validation dataset.
    feature_count:
        Number of active features in the model.
    passes_validation:
        True when auc_score >= SR117_MINIMUM_AUC (0.75).
    notes:
        Free-text notes for the model risk committee.
    """

    report_id: str
    model_id: str
    component: str
    validation_date: datetime
    auc_score: float
    feature_count: int
    passes_validation: bool
    notes: str = ""


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class RegulatoryReporter:
    """Produces and stores DORA Art.19 and SR 11-7 regulatory records (GAP-14).

    Records are held in memory and surfaced via the admin router for the BPI
    compliance team to submit to the appropriate competent authority.
    """

    def __init__(self) -> None:
        self._dora_events: Dict[str, DORAAuditEvent] = {}
        self._sr117_reports: Dict[str, SR117ModelValidationReport] = {}

    # ── DORA ─────────────────────────────────────────────────────────────────

    def create_dora_event(
        self,
        event_type: str,
        severity: DORASeverity,
        description: str,
        occurred_at: datetime,
        uetr: Optional[str] = None,
    ) -> DORAAuditEvent:
        """Create and store a DORA Article 19 incident record.

        Parameters
        ----------
        event_type:
            Machine-readable incident category string.
        severity:
            :class:`DORASeverity` value.
        description:
            Human-readable summary for the regulatory filing.
        occurred_at:
            UTC timestamp of the incident's first observation.
        uetr:
            Associated SWIFT UETR, if applicable.

        Returns
        -------
        DORAAuditEvent
            The created record.
        """
        if severity == DORASeverity.MAJOR:
            threshold_hours = DORA_MAJOR_REPORTING_THRESHOLD_HOURS
        else:
            threshold_hours = DORA_SIGNIFICANT_REPORTING_THRESHOLD_HOURS

        event = DORAAuditEvent(
            incident_id=str(uuid.uuid4()),
            uetr=uetr,
            event_type=event_type,
            severity=severity,
            description=description,
            occurred_at=occurred_at,
            reported_at=datetime.now(tz=timezone.utc),
            threshold_hours=threshold_hours,
            is_reportable=severity in (DORASeverity.MAJOR, DORASeverity.SIGNIFICANT),
        )
        self._dora_events[event.incident_id] = event
        logger.info(
            "DORA event created: id=%s type=%s severity=%s reportable=%s",
            event.incident_id, event_type, severity.value, event.is_reportable,
        )
        return event

    def get_all_dora_events(self) -> List[DORAAuditEvent]:
        """Return all DORA audit events (MAJOR, SIGNIFICANT, and MINOR)."""
        return list(self._dora_events.values())

    def get_reportable_events(self) -> List[DORAAuditEvent]:
        """Return only events that require regulatory filing (MAJOR + SIGNIFICANT)."""
        return [e for e in self._dora_events.values() if e.is_reportable]

    def get_dora_event(self, incident_id: str) -> Optional[DORAAuditEvent]:
        """Return a single DORA event by incident_id, or None."""
        return self._dora_events.get(incident_id)

    # ── SR 11-7 ───────────────────────────────────────────────────────────────

    def create_sr117_report(
        self,
        model_id: str,
        component: str,
        validation_date: datetime,
        auc_score: float,
        feature_count: int,
        notes: str = "",
    ) -> SR117ModelValidationReport:
        """Create and store a Fed SR 11-7 model validation report.

        Parameters
        ----------
        model_id:
            Artefact version tag of the validated model.
        component:
            LIP component identifier (e.g. ``"C1_FAILURE_CLASSIFIER"``).
        validation_date:
            UTC timestamp of the validation run.
        auc_score:
            Achieved AUC on the validation hold-out set.
        feature_count:
            Number of active model features.
        notes:
            Free-text notes for the model risk committee.

        Returns
        -------
        SR117ModelValidationReport
            The created report; ``passes_validation`` is True when
            ``auc_score >= SR117_MINIMUM_AUC`` (0.75).
        """
        passes = auc_score >= SR117_MINIMUM_AUC
        report = SR117ModelValidationReport(
            report_id=str(uuid.uuid4()),
            model_id=model_id,
            component=component,
            validation_date=validation_date,
            auc_score=auc_score,
            feature_count=feature_count,
            passes_validation=passes,
            notes=notes,
        )
        self._sr117_reports[report.report_id] = report
        logger.info(
            "SR 11-7 report created: id=%s model=%s component=%s auc=%.4f passes=%s",
            report.report_id, model_id, component, auc_score, passes,
        )
        return report

    def get_sr117_reports(self) -> List[SR117ModelValidationReport]:
        """Return all SR 11-7 model validation reports."""
        return list(self._sr117_reports.values())

    def get_sr117_report(self, report_id: str) -> Optional[SR117ModelValidationReport]:
        """Return a single SR 11-7 report by report_id, or None."""
        return self._sr117_reports.get(report_id)
