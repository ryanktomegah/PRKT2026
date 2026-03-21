"""
regulatory_export.py — CSV/JSON export formats for regulatory records.
GAP-14: DORA Art.19 events and SR 11-7 reports must be exportable in
        machine-readable formats for submission to competent authorities.
"""
from __future__ import annotations

import csv
import io
import json
from typing import List

from lip.common.regulatory_reporter import DORAAuditEvent, SR117ModelValidationReport


def export_dora_events_csv(events: List[DORAAuditEvent]) -> str:
    """Export DORA audit events as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "incident_id", "uetr", "event_type", "severity", "description",
        "occurred_at", "reported_at", "threshold_hours", "is_reportable",
        "within_threshold",
    ])
    for e in events:
        writer.writerow([
            e.incident_id, e.uetr or "", e.event_type, e.severity.value,
            e.description, e.occurred_at.isoformat(), e.reported_at.isoformat(),
            e.threshold_hours, e.is_reportable, e.within_threshold,
        ])
    return output.getvalue()


def export_dora_events_json(events: List[DORAAuditEvent]) -> str:
    """Export DORA audit events as JSON array."""
    records = []
    for e in events:
        records.append({
            "incident_id": e.incident_id,
            "uetr": e.uetr,
            "event_type": e.event_type,
            "severity": e.severity.value,
            "description": e.description,
            "occurred_at": e.occurred_at.isoformat(),
            "reported_at": e.reported_at.isoformat(),
            "threshold_hours": e.threshold_hours,
            "is_reportable": e.is_reportable,
            "within_threshold": e.within_threshold,
        })
    return json.dumps(records, indent=2)


def export_sr117_reports_csv(reports: List[SR117ModelValidationReport]) -> str:
    """Export SR 11-7 model validation reports as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "report_id", "model_id", "component", "validation_date",
        "auc_score", "feature_count", "passes_validation", "notes",
    ])
    for r in reports:
        writer.writerow([
            r.report_id, r.model_id, r.component,
            r.validation_date.isoformat(), r.auc_score, r.feature_count,
            r.passes_validation, r.notes,
        ])
    return output.getvalue()


def export_sr117_reports_json(reports: List[SR117ModelValidationReport]) -> str:
    """Export SR 11-7 model validation reports as JSON array."""
    records = []
    for r in reports:
        records.append({
            "report_id": r.report_id,
            "model_id": r.model_id,
            "component": r.component,
            "validation_date": r.validation_date.isoformat(),
            "auc_score": r.auc_score,
            "feature_count": r.feature_count,
            "passes_validation": r.passes_validation,
            "notes": r.notes,
        })
    return json.dumps(records, indent=2)
