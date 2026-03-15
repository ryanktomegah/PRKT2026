"""
test_gap14_regulatory_reporting.py — Tests for GAP-14:
Regulatory reporting formats for DORA Article 19 and Fed SR 11-7.
"""
from datetime import datetime, timedelta, timezone

from lip.common.regulatory_reporter import (
    DORA_MAJOR_REPORTING_THRESHOLD_HOURS,
    DORA_SIGNIFICANT_REPORTING_THRESHOLD_HOURS,
    SR117_MINIMUM_AUC,
    DORASeverity,
    RegulatoryReporter,
    SR117ModelValidationReport,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# 1–6: DORA audit event creation
# ---------------------------------------------------------------------------

class TestDORAAuditEventCreation:
    def test_create_major_event_is_reportable(self):
        """MAJOR severity events must be filed with the competent authority."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            event_type="KILL_SWITCH_ACTIVATED",
            severity=DORASeverity.MAJOR,
            description="Global kill-switch fired during peak window.",
            occurred_at=_now(),
        )
        assert event.is_reportable is True

    def test_create_significant_event_is_reportable(self):
        """SIGNIFICANT severity events are also reportable."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            event_type="AML_BLOCK_SPIKE",
            severity=DORASeverity.SIGNIFICANT,
            description="Unusual AML block rate detected.",
            occurred_at=_now(),
        )
        assert event.is_reportable is True

    def test_create_minor_event_is_not_reportable(self):
        """MINOR events are internal only — no regulatory filing required."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            event_type="DEGRADED_MODE_ENTERED",
            severity=DORASeverity.MINOR,
            description="KMS unavailable for 30 s; fell back to cached key.",
            occurred_at=_now(),
        )
        assert event.is_reportable is False

    def test_major_event_has_4h_threshold(self):
        """DORA Art.19: MAJOR incidents must be reported within 4 hours."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            "SYSTEM_OUTAGE", DORASeverity.MAJOR, "desc", _now()
        )
        assert event.threshold_hours == DORA_MAJOR_REPORTING_THRESHOLD_HOURS
        assert event.threshold_hours == 4

    def test_significant_event_has_24h_threshold(self):
        """DORA Art.19: SIGNIFICANT incidents have a 24-hour filing deadline."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            "HIGH_FAILURE_RATE", DORASeverity.SIGNIFICANT, "desc", _now()
        )
        assert event.threshold_hours == DORA_SIGNIFICANT_REPORTING_THRESHOLD_HOURS
        assert event.threshold_hours == 24

    def test_event_has_unique_incident_id(self):
        """Each DORA event receives a distinct incident_id."""
        reporter = RegulatoryReporter()
        e1 = reporter.create_dora_event("E1", DORASeverity.MAJOR, "d", _now())
        e2 = reporter.create_dora_event("E2", DORASeverity.MAJOR, "d", _now())
        assert e1.incident_id != e2.incident_id

    def test_uetr_attached_when_provided(self):
        """Optional UETR is preserved on the event record."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            "PAYMENT_BLOCKED", DORASeverity.SIGNIFICANT, "desc",
            _now(), uetr="uetr-xyz"
        )
        assert event.uetr == "uetr-xyz"


# ---------------------------------------------------------------------------
# 7–9: within_threshold property
# ---------------------------------------------------------------------------

class TestDORAWithinThreshold:
    def test_within_threshold_true_when_just_created(self):
        """Event reported immediately is always within threshold."""
        reporter = RegulatoryReporter()
        event = reporter.create_dora_event(
            "IMMEDIATE", DORASeverity.MAJOR, "desc", _now()
        )
        assert event.within_threshold is True

    def test_within_threshold_false_when_late(self):
        """Event where occurred_at was 10h ago is outside the 4h MAJOR threshold."""
        reporter = RegulatoryReporter()
        occurred = _now() - timedelta(hours=10)
        event = reporter.create_dora_event(
            "LATE", DORASeverity.MAJOR, "desc", occurred
        )
        assert event.within_threshold is False

    def test_get_reportable_events_excludes_minor(self):
        """get_reportable_events() returns only MAJOR and SIGNIFICANT records."""
        reporter = RegulatoryReporter()
        reporter.create_dora_event("M", DORASeverity.MAJOR, "d", _now())
        reporter.create_dora_event("S", DORASeverity.SIGNIFICANT, "d", _now())
        reporter.create_dora_event("N", DORASeverity.MINOR, "d", _now())

        reportable = reporter.get_reportable_events()
        assert len(reportable) == 2
        assert all(e.severity != DORASeverity.MINOR for e in reportable)

    def test_get_all_dora_events_includes_minor(self):
        """get_all_dora_events() returns every event regardless of severity."""
        reporter = RegulatoryReporter()
        reporter.create_dora_event("M", DORASeverity.MAJOR, "d", _now())
        reporter.create_dora_event("N", DORASeverity.MINOR, "d", _now())
        assert len(reporter.get_all_dora_events()) == 2


# ---------------------------------------------------------------------------
# 10–14: SR 11-7 model validation reports
# ---------------------------------------------------------------------------

class TestSR117Reports:
    def test_create_sr117_report(self):
        """create_sr117_report() returns an SR117ModelValidationReport."""
        reporter = RegulatoryReporter()
        report = reporter.create_sr117_report(
            model_id="c1-v1.2.0",
            component="C1_FAILURE_CLASSIFIER",
            validation_date=_now(),
            auc_score=0.9998,
            feature_count=88,
        )
        assert isinstance(report, SR117ModelValidationReport)
        assert report.model_id == "c1-v1.2.0"
        assert report.component == "C1_FAILURE_CLASSIFIER"

    def test_sr117_passes_at_high_auc(self):
        """AUC of 0.9998 (C1 synthetic result) passes SR 11-7 threshold."""
        reporter = RegulatoryReporter()
        report = reporter.create_sr117_report(
            "c1-v1", "C1_FAILURE_CLASSIFIER", _now(), auc_score=0.9998, feature_count=88
        )
        assert report.passes_validation is True

    def test_sr117_passes_at_boundary_auc(self):
        """AUC exactly at SR117_MINIMUM_AUC (0.75) passes validation."""
        reporter = RegulatoryReporter()
        report = reporter.create_sr117_report(
            "c1-v2", "C1_FAILURE_CLASSIFIER", _now(), auc_score=SR117_MINIMUM_AUC, feature_count=50
        )
        assert report.passes_validation is True

    def test_sr117_fails_below_threshold(self):
        """AUC below 0.75 fails SR 11-7 validation — model must not be deployed."""
        reporter = RegulatoryReporter()
        report = reporter.create_sr117_report(
            "c1-bad", "C1_FAILURE_CLASSIFIER", _now(), auc_score=0.60, feature_count=20
        )
        assert report.passes_validation is False

    def test_get_sr117_reports(self):
        """get_sr117_reports() returns all created reports."""
        reporter = RegulatoryReporter()
        reporter.create_sr117_report("c1", "C1", _now(), 0.85, 88)
        reporter.create_sr117_report("c2", "C2", _now(), 0.82, 45)
        reporter.create_sr117_report("c4", "C4", _now(), 0.91, 30)
        reports = reporter.get_sr117_reports()
        assert len(reports) == 3
        components = {r.component for r in reports}
        assert components == {"C1", "C2", "C4"}

    def test_sr117_notes_preserved(self):
        """Free-text notes are stored on the report for committee review."""
        reporter = RegulatoryReporter()
        report = reporter.create_sr117_report(
            "c1", "C1", _now(), 0.85, 88,
            notes="Validated on 2K synthetic samples. Real-world AUC est. 0.82–0.88."
        )
        assert "synthetic" in report.notes
