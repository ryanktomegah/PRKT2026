"""
test_regulatory_reporting.py — Tests for automated regulatory report generation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from lip.compliance.model_card_generator import (
    export_dora_report_json,
    export_eu_ai_act_report_json,
    export_model_card_json,
    export_model_card_markdown,
    export_sr117_report_json,
    generate_dora_incident_report,
    generate_eu_ai_act_report,
    generate_model_card,
    generate_sr117_report,
)


class TestModelCard:
    """Test model card generation."""

    def test_generate_c1_model_card(self):
        card = generate_model_card(
            component="C1",
            model_metadata={
                "model_id": "lip-c1-v1",
                "version": "1.0.0",
                "feature_count": 88,
                "ensemble_size": 5,
            },
            training_results={
                "data_size": 2_000_000,
                "date_range": "2025-01-01 to 2025-12-31",
                "is_synthetic": True,
                "calibration_method": "isotonic",
                "calibration_error": 0.0687,
            },
            evaluation_results={
                "metrics": {"auc": 0.8871, "f2": 0.6245},
                "eval_data_size": 500_000,
            },
        )
        assert card.component == "C1"
        assert card.model_id == "lip-c1-v1"
        assert card.training_data_is_synthetic
        assert card.evaluation_metrics["auc"] == 0.8871

    def test_json_export(self):
        card = generate_model_card(
            component="C2",
            model_metadata={"feature_count": 75, "ensemble_size": 5},
            training_results={"data_size": 100000, "is_synthetic": True},
            evaluation_results={"metrics": {"auc": 0.85}},
        )
        json_str = export_model_card_json(card)
        parsed = json.loads(json_str)
        assert parsed["component"] == "C2"

    def test_markdown_export(self):
        card = generate_model_card(
            component="C1",
            model_metadata={
                "feature_count": 88,
                "ensemble_size": 5,
                "conformal_coverage_level": 0.90,
                "conformal_calibration_size": 10000,
                "drift_features_monitored": 10,
            },
            training_results={"data_size": 2000000, "is_synthetic": True},
            evaluation_results={"metrics": {"auc": 0.887}},
        )
        md = export_model_card_markdown(card)
        assert "# Model Card" in md
        assert "C1" in md
        assert "Conformal Coverage" in md
        assert "Drift Monitoring" in md


class TestDORAIncidentReport:
    """Test DORA Art.19 incident report generation."""

    def test_generate_report(self):
        now = datetime.now(timezone.utc)
        report = generate_dora_incident_report(
            incident_id="INC-2026-001",
            incident_type="MODEL_DEGRADATION",
            description="C1 AUC dropped below 0.80 threshold.",
            affected_components=["C1", "C7"],
            detection_time=now,
            root_cause="Feature distribution shift in USD-CNY corridor.",
            remediation_steps=["Retrained C1 model", "Updated feature pipeline"],
            classification="SIGNIFICANT",
        )
        assert report.incident_id == "INC-2026-001"
        assert report.classification == "SIGNIFICANT"
        assert report.cross_border_impact
        assert not report.data_breach

    def test_json_export(self):
        now = datetime.now(timezone.utc)
        report = generate_dora_incident_report(
            incident_id="INC-001",
            incident_type="TEST",
            description="Test incident",
            affected_components=["C1"],
            detection_time=now,
            root_cause="Test",
            remediation_steps=["Fix"],
        )
        json_str = export_dora_report_json(report)
        parsed = json.loads(json_str)
        assert parsed["incident_id"] == "INC-001"


class TestSR117Report:
    """Test SR 11-7 validation report generation."""

    def test_passing_report(self):
        report = generate_sr117_report(
            model_id="lip-c1-v1",
            component="C1",
            metrics={"auc": 0.887, "f2": 0.625, "ece": 0.068, "feature_count": 88},
            drift_config={"method": "ADWIN", "features_count": 10, "frequency": "Per-inference"},
            conformal_config={"target": 0.90, "actual": 0.91},
        )
        assert report.passes_validation
        assert report.auc_score == 0.887
        assert report.conformal_coverage_target == 0.90

    def test_failing_report(self):
        report = generate_sr117_report(
            model_id="lip-c1-v1",
            component="C1",
            metrics={"auc": 0.60},  # Below 0.75 threshold
            drift_config={"method": "ADWIN", "features_count": 10},
        )
        assert not report.passes_validation

    def test_json_export(self):
        report = generate_sr117_report(
            model_id="lip-c1-v1",
            component="C1",
            metrics={"auc": 0.85},
            drift_config={"method": "ADWIN"},
        )
        json_str = export_sr117_report_json(report)
        parsed = json.loads(json_str)
        assert parsed["model_id"] == "lip-c1-v1"


class TestEUAIActReport:
    """Test EU AI Act Art.61 post-market monitoring report."""

    def test_generate_report(self):
        report = generate_eu_ai_act_report(
            reporting_period=("2026-01-01", "2026-03-31"),
            monitoring_data={
                "total_inferences": 150000,
                "drift_events_detected": 3,
                "drift_events_resolved": 3,
                "conformal_coverage": 0.91,
                "incidents_count": 0,
                "risk_level": "LOW",
            },
        )
        assert report.total_inferences == 150000
        assert report.risk_level == "LOW"

    def test_json_export(self):
        report = generate_eu_ai_act_report(
            reporting_period=("2026-01-01", "2026-03-31"),
            monitoring_data={"total_inferences": 100},
        )
        json_str = export_eu_ai_act_report_json(report)
        parsed = json.loads(json_str)
        assert parsed["system_name"] == "LIP — Liquidity Intelligence Platform"
