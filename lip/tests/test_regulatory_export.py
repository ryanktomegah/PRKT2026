"""Tests for GAP-14: Regulatory export formats."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from lip.common.regulatory_export import (
    export_dora_events_csv,
    export_dora_events_json,
    export_sr117_reports_csv,
    export_sr117_reports_json,
)
from lip.common.regulatory_reporter import (
    DORAAuditEvent,
    DORASeverity,
    SR117ModelValidationReport,
)


def _make_dora_event(**kwargs):
    defaults = {
        "incident_id": "inc-001",
        "uetr": "uetr-001",
        "event_type": "KILL_SWITCH_ACTIVATED",
        "severity": DORASeverity.MAJOR,
        "description": "Kill switch activated by operator",
        "occurred_at": datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
        "reported_at": datetime(2026, 3, 20, 12, 30, 0, tzinfo=timezone.utc),
        "threshold_hours": 4,
        "is_reportable": True,
    }
    defaults.update(kwargs)
    return DORAAuditEvent(**defaults)


def _make_sr117_report(**kwargs):
    defaults = {
        "report_id": "rpt-001",
        "model_id": "c1-v2.1",
        "component": "C1_FAILURE_CLASSIFIER",
        "validation_date": datetime(2026, 3, 20, tzinfo=timezone.utc),
        "auc_score": 0.85,
        "feature_count": 42,
        "passes_validation": True,
        "notes": "Production validation run",
    }
    defaults.update(kwargs)
    return SR117ModelValidationReport(**defaults)


class TestDORAExport:
    def test_csv_empty(self):
        result = export_dora_events_csv([])
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1  # header only

    def test_csv_single_event(self):
        event = _make_dora_event()
        result = export_dora_events_csv([event])
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1][0] == "inc-001"
        assert rows[1][3] == "MAJOR"

    def test_json_empty(self):
        result = export_dora_events_json([])
        data = json.loads(result)
        assert data == []

    def test_json_single_event(self):
        event = _make_dora_event()
        result = export_dora_events_json([event])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["incident_id"] == "inc-001"
        assert data[0]["severity"] == "MAJOR"
        assert data[0]["is_reportable"] is True

    def test_json_multiple_events(self):
        events = [
            _make_dora_event(incident_id="inc-001"),
            _make_dora_event(incident_id="inc-002", severity=DORASeverity.SIGNIFICANT),
        ]
        result = export_dora_events_json(events)
        data = json.loads(result)
        assert len(data) == 2


class TestSR117Export:
    def test_csv_empty(self):
        result = export_sr117_reports_csv([])
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1

    def test_csv_single_report(self):
        report = _make_sr117_report()
        result = export_sr117_reports_csv([report])
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1][0] == "rpt-001"
        assert rows[1][4] == "0.85"

    def test_json_single_report(self):
        report = _make_sr117_report()
        result = export_sr117_reports_json([report])
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["model_id"] == "c1-v2.1"
        assert data[0]["passes_validation"] is True
        assert data[0]["auc_score"] == 0.85
