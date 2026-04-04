"""Tests for methodology paper and regulator onboarding (Sprint 8, Tasks 4-5)."""
from __future__ import annotations

from lip.p10_regulatory_data.methodology import MethodologyAppendix
from lip.p10_regulatory_data.methodology_paper import (
    MethodologyPaper,
    generate_methodology_paper,
)
from lip.p10_regulatory_data.regulator_onboarding import (
    ComplianceMapping,
    OnboardingChecklist,
    generate_compliance_mapping,
    generate_onboarding_checklist,
    generate_sample_data_package,
)

_SALT = b"onboard_test_salt_32bytes_______"


# ---- Methodology Paper ----


class TestMethodologyPaper:

    def test_generates_all_sections(self):
        paper = generate_methodology_paper()
        assert isinstance(paper, MethodologyPaper)
        assert paper.version == MethodologyAppendix.VERSION
        expected_sections = [
            "1. Data Collection",
            "2. Anonymization Layers",
            "3. Statistical Methodology",
            "4. Privacy Guarantees",
            "5. Limitations",
            "6. Constants Reference",
        ]
        for section in expected_sections:
            assert section in paper.sections, f"Missing section: {section}"

    def test_to_dict_returns_valid_structure(self):
        paper = generate_methodology_paper()
        d = paper.to_dict()
        assert "version" in d
        assert "sections" in d
        assert isinstance(d["sections"], dict)

    def test_to_markdown_contains_all_sections(self):
        paper = generate_methodology_paper()
        md = paper.to_markdown()
        assert "# P10 Regulatory Data Product" in md
        assert "## 1. Data Collection" in md
        assert "## 6. Constants Reference" in md
        assert "P10_K_ANONYMITY_THRESHOLD" in md

    def test_constants_reference_has_all_p10_constants(self):
        paper = generate_methodology_paper()
        consts = paper.sections["6. Constants Reference"]
        expected_keys = [
            "P10_K_ANONYMITY_THRESHOLD",
            "P10_DIFFERENTIAL_PRIVACY_EPSILON",
            "P10_PRIVACY_BUDGET_PER_CYCLE",
            "P10_CONTAGION_MAX_HOPS",
            "SALT_ROTATION_DAYS",
        ]
        for key in expected_keys:
            assert key in consts, f"Missing constant: {key}"


# ---- Onboarding Checklist ----


class TestOnboardingChecklist:

    def test_checklist_all_pass(self):
        checklist = generate_onboarding_checklist(salt=_SALT, n_banks=5, seed=42)
        assert isinstance(checklist, OnboardingChecklist)
        assert checklist.all_passed is True
        assert len(checklist.items) == 12

    def test_checklist_reports_integrity_status(self):
        checklist = generate_onboarding_checklist(salt=_SALT)
        integrity_item = next(
            i for i in checklist.items if i.name == "integrity_verification_passing"
        )
        assert integrity_item.status == "PASS"
        assert "SHA-256" in integrity_item.evidence

    def test_checklist_has_timestamp(self):
        checklist = generate_onboarding_checklist(salt=_SALT)
        assert checklist.timestamp > 0


# ---- Sample Data Package ----


class TestSampleDataPackage:

    def test_package_complete(self):
        pkg = generate_sample_data_package(salt=_SALT, seed=42)
        expected_keys = [
            "events_count",
            "events_filtered",
            "batches_produced",
            "corridors_analyzed",
            "corridors_suppressed",
            "report_summary",
            "versioned_report",
            "privacy_budget_consumed",
            "integrity_verified",
        ]
        for key in expected_keys:
            assert key in pkg, f"Missing key: {key}"
        assert pkg["integrity_verified"] is True

    def test_report_summary_has_risk_score(self):
        pkg = generate_sample_data_package(salt=_SALT)
        summary = pkg["report_summary"]
        assert "systemic_risk_score" in summary
        assert 0.0 <= summary["systemic_risk_score"] <= 1.0


# ---- Compliance Mapping ----


class TestComplianceMapping:

    def test_covers_dora_articles(self):
        mappings = generate_compliance_mapping()
        assert len(mappings) == 8
        articles = {m.dora_article for m in mappings}
        # Should cover Art. 31-42 range
        assert any("Art. 31" in a for a in articles)
        assert any("Art. 42" in a for a in articles)

    def test_all_implemented(self):
        mappings = generate_compliance_mapping()
        for m in mappings:
            assert isinstance(m, ComplianceMapping)
            assert m.status == "IMPLEMENTED"
            assert len(m.evidence) > 0
