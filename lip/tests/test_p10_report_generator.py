"""
test_p10_report_generator.py — TDD tests for P10 Report Generator.

Sprint 5: Multi-format report rendering, versioning, methodology.
"""
from __future__ import annotations

import pytest


class TestVersionedReport:
    """VersionedReport immutability, hashing, and versioning."""

    @staticmethod
    def _make_report():
        """Create a SystemicRiskReport for testing."""
        from lip.p10_regulatory_data.systemic_risk import (
            CorridorRiskSnapshot,
            SystemicRiskReport,
        )

        return SystemicRiskReport(
            timestamp=1700000000.0,
            corridor_snapshots=[
                CorridorRiskSnapshot(
                    corridor="EUR-USD",
                    period_label="2029-08-01T14:00Z",
                    failure_rate=0.10,
                    total_payments=1000,
                    failed_payments=100,
                    bank_count=10,
                    trend_direction="STABLE",
                    trend_magnitude=0.0,
                    contains_stale_data=False,
                ),
            ],
            overall_failure_rate=0.10,
            highest_risk_corridor="EUR-USD",
            concentration_hhi=1.0,
            systemic_risk_score=0.10,
            stale_corridor_count=0,
            total_corridors_analyzed=1,
        )

    def test_frozen_immutability(self):
        """VersionedReport cannot be mutated after construction."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr = create_versioned_report(report=report)
        with pytest.raises(AttributeError):
            vr.version = "2.0"

    def test_content_hash_is_sha256(self):
        """Content hash is a 64-char hex SHA-256 digest."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr = create_versioned_report(report=report)
        assert len(vr.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in vr.content_hash)

    def test_deterministic_hash(self):
        """Same report produces same content hash."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        vr1 = create_versioned_report(report=report)
        vr2 = create_versioned_report(report=report)
        assert vr1.content_hash == vr2.content_hash

    def test_supersedes_chain(self):
        """Corrected report has supersedes pointing to original."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        report = self._make_report()
        original = create_versioned_report(report=report)
        corrected = create_versioned_report(
            report=report,
            version="1.1",
            supersedes=original.report_id,
        )
        assert corrected.supersedes == original.report_id
        assert corrected.version == "1.1"
        assert original.supersedes is None

    def test_integrity_verification_passes(self):
        """verify_integrity returns True when hash matches."""
        from lip.p10_regulatory_data.report_metadata import (
            create_versioned_report,
            verify_report_integrity,
        )

        report = self._make_report()
        vr = create_versioned_report(report=report)
        assert verify_report_integrity(vr) is True

    def test_integrity_verification_fails(self):
        """Tampered hash raises ReportIntegrityError."""
        import dataclasses

        from lip.p10_regulatory_data.report_metadata import (
            ReportIntegrityError,
            create_versioned_report,
            verify_report_integrity,
        )

        report = self._make_report()
        vr = create_versioned_report(report=report)
        tampered = dataclasses.replace(vr, content_hash="0" * 64)
        with pytest.raises(ReportIntegrityError):
            verify_report_integrity(tampered)


class TestMethodologyAppendix:
    """Methodology appendix template tests."""

    def test_version_string(self):
        """VERSION matches expected format."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        assert MethodologyAppendix.VERSION == "P10-METH-v1.0"

    def test_all_seven_sections_present(self):
        """get_sections() returns all 7 methodology sections."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        sections = MethodologyAppendix.get_sections()
        assert len(sections) == 7
        expected_keys = [
            "data_collection",
            "corridor_failure_rate",
            "concentration_analysis",
            "contagion_simulation",
            "systemic_risk_score",
            "data_quality",
            "limitations",
        ]
        for key in expected_keys:
            assert key in sections, f"Missing section: {key}"
            assert len(sections[key]) > 50, f"Section {key} too short"

    def test_text_references_constants(self):
        """Full text references actual P10 constant values."""
        from lip.p10_regulatory_data.methodology import MethodologyAppendix

        text = MethodologyAppendix.get_text()
        assert "k >= 5" in text or "k=5" in text or "k ≥ 5" in text
        assert "epsilon" in text.lower() or "ε" in text
        assert "0.25" in text  # HHI threshold
        assert "0.7" in text or "0.70" in text  # decay


class TestReportRendererJSON:
    """JSON report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        """Create a VersionedReport for testing."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report

        return create_versioned_report(
            report=TestVersionedReport._make_report(),
            period_start="2029-08-01T00:00Z",
            period_end="2029-08-01T23:59Z",
        )

    def test_valid_json_with_required_fields(self):
        """JSON output is valid and contains all metadata fields."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_json(vr)
        data = json.loads(output)
        assert data["report_id"] == vr.report_id
        assert data["version"] == vr.version
        assert data["content_hash"] == vr.content_hash
        assert data["methodology_version"] == vr.methodology_version
        assert "corridor_snapshots" in data

    def test_deterministic_ordering(self):
        """Same report produces identical JSON key ordering."""
        from lip.p10_regulatory_data.report_metadata import create_versioned_report
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        report = TestVersionedReport._make_report()
        vr1 = create_versioned_report(report=report)
        vr2 = create_versioned_report(report=report)
        renderer = ReportRenderer()
        j1 = renderer.render_json(vr1)
        j2 = renderer.render_json(vr2)
        import json

        d1 = json.loads(j1)
        d2 = json.loads(j2)
        assert list(d1.keys()) == list(d2.keys())

    def test_methodology_appendix_included(self):
        """JSON output includes methodology sections."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        data = json.loads(renderer.render_json(vr))
        assert "methodology" in data
        assert "data_collection" in data["methodology"]
        assert len(data["methodology"]) == 7

    def test_statistical_floats_rounded(self):
        """Statistical floats are rounded to 6 decimal places."""
        import json

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        data = json.loads(renderer.render_json(vr))
        snapshot = data["corridor_snapshots"][0]
        fr_str = str(snapshot["failure_rate"])
        if "." in fr_str:
            assert len(fr_str.split(".")[1]) <= 6


class TestReportRendererCSV:
    """CSV report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        return TestReportRendererJSON._make_versioned_report()

    def test_metadata_header_comments(self):
        """CSV starts with # comment header containing metadata."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        lines = output.split("\n")
        comment_lines = [line for line in lines if line.startswith("#")]
        assert len(comment_lines) >= 3
        header_text = "\n".join(comment_lines)
        assert vr.report_id in header_text
        assert vr.content_hash in header_text

    def test_one_row_per_corridor(self):
        """Data section has one row per corridor snapshot."""
        import csv
        import io

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        data_lines = [line for line in output.split("\n") if line and not line.startswith("#")]
        if data_lines and data_lines[0].startswith("\ufeff"):
            data_lines[0] = data_lines[0][1:]
        reader = csv.reader(io.StringIO("\n".join(data_lines)))
        rows = list(reader)
        assert len(rows) >= 3  # header + 1 data row + 1 summary row

    def test_summary_footer_present(self):
        """CSV ends with a summary row."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        assert "SUMMARY" in output or "overall_failure_rate" in output.lower()

    def test_utf8_bom_prefix(self):
        """CSV output starts with UTF-8 BOM for Excel compatibility."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_csv(vr)
        assert output.startswith("\ufeff")


class TestReportRendererPDF:
    """PDF report rendering tests."""

    @staticmethod
    def _make_versioned_report():
        return TestReportRendererJSON._make_versioned_report()

    def test_pdf_magic_bytes(self):
        """PDF output starts with %PDF magic bytes."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_pdf(vr)
        assert isinstance(output, bytes)
        assert output[:5] == b"%PDF-"

    def test_pdf_contains_metadata(self):
        """PDF contains report ID and title."""
        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        output = renderer.render_pdf(vr)
        text = output.decode("latin-1")
        assert "Systemic Risk Report" in text
        assert vr.report_id in text

    def test_pdf_import_error_without_fpdf2(self):
        """render_pdf raises ImportError if fpdf2 not installed."""
        from unittest.mock import patch

        from lip.p10_regulatory_data.report_renderer import ReportRenderer

        vr = self._make_versioned_report()
        renderer = ReportRenderer()
        with patch.dict("sys.modules", {"fpdf": None}):
            with pytest.raises(ImportError, match="fpdf2"):
                renderer.render_pdf(vr)


class TestServiceIntegration:
    """Service layer integration with VersionedReport."""

    @staticmethod
    def _make_engine_with_data():
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results([
            AnonymizedCorridorResult(
                corridor="EUR-USD",
                period_label="2029-08-01T14:00Z",
                total_payments=1000,
                failed_payments=100,
                failure_rate=0.10,
                bank_count=10,
                k_anonymity_satisfied=True,
                privacy_budget_remaining=4.5,
                noise_applied=True,
                stale=False,
            ),
        ])
        return engine

    def test_generate_report_produces_versioned_report(self):
        """generate_report() returns a VersionedReport."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.report_metadata import VersionedReport

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        assert isinstance(vr, VersionedReport)
        assert vr.report_id.startswith("RPT-")
        assert vr.version == "1.0"

    def test_render_report_json(self):
        """render_report with fmt='json' returns JSON string."""
        import json

        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        content, content_type = service.render_report(vr.report_id, fmt="json")
        assert content_type == "application/json"
        data = json.loads(content)
        assert data["report_id"] == vr.report_id

    def test_render_report_csv(self):
        """render_report with fmt='csv' returns CSV string."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        content, content_type = service.render_report(vr.report_id, fmt="csv")
        assert content_type == "text/csv"
        assert vr.report_id in content

    def test_stress_test_produces_versioned_report(self):
        """run_stress_test() returns VersionedReport."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.report_metadata import VersionedReport

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        report_id, vr = service.run_stress_test(
            scenario_name="test-scenario",
            shocks=[("EUR-USD", 0.9)],
        )
        assert isinstance(vr, VersionedReport)
        assert vr.report_id == report_id

    def test_version_chain_single_report(self):
        """get_version_chain returns a list containing the single report."""
        from lip.api.regulatory_service import RegulatoryService

        engine = self._make_engine_with_data()
        service = RegulatoryService(risk_engine=engine)
        vr = service.generate_report()
        chain = service.get_version_chain(vr.report_id)
        assert len(chain) == 1
        assert chain[0].report_id == vr.report_id
