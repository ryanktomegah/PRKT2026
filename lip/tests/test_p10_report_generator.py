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
