"""Tests for lip.integrity.compliance_enforcer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lip.integrity.compliance_enforcer import (
    ComplianceEvidenceEnforcer,
    compute_proof_of_freshness,
    jaccard_similarity,
)
from lip.integrity.evidence import EvidenceType, verify_evidence

_KEY = b"integrity_test__32bytes_________"


def _enf() -> ComplianceEvidenceEnforcer:
    return ComplianceEvidenceEnforcer(hmac_key=_KEY)


# ---------------------------------------------------------------------------
# wrap_report_generation
# ---------------------------------------------------------------------------


def test_wrap_report_binds_data_hash():
    enf = _enf()
    live_data = {"auc": 0.887, "f2": 0.62, "n_samples": 10_000}

    def generator(live_data: dict) -> dict:  # noqa: ARG001
        return {"summary": "Model approved", "auc": 0.887}

    report, evidence = enf.wrap_report_generation(generator, live_data, source_module="C1")

    assert report["summary"] == "Model approved"
    assert evidence.evidence_type == EvidenceType.COMPLIANCE_REPORT
    assert evidence.data_hash == compute_proof_of_freshness(live_data)
    assert verify_evidence(evidence, _KEY) is True


def test_proof_of_freshness_matches_round_trip():
    enf = _enf()
    live_data = {"k": "v", "n": 42}

    _, evidence = enf.wrap_report_generation(lambda _d: "rpt", live_data)
    assert enf.verify_proof_of_freshness(evidence, live_data) is True


def test_proof_of_freshness_tampered_data_fails():
    enf = _enf()
    live_data = {"auc": 0.887}

    _, evidence = enf.wrap_report_generation(lambda _d: "rpt", live_data)

    tampered = {"auc": 0.999}  # different data
    assert enf.verify_proof_of_freshness(evidence, tampered) is False


# ---------------------------------------------------------------------------
# Boilerplate detection
# ---------------------------------------------------------------------------


def test_boilerplate_detection_identical_reports_flagged():
    enf = _enf()
    text = (
        "Annual SOC 2 Type II report. Controls effective. "
        "Zero security incidents. Zero personnel changes."
    )
    corpus = [("rep-A", text), ("rep-B", text)]
    result = enf.detect_boilerplate(text, corpus)

    assert result.is_boilerplate is True
    assert result.max_similarity == 1.0
    assert result.most_similar_report_id in {"rep-A", "rep-B"}
    assert result.unique_content_ratio == 0.0


def test_boilerplate_detection_unique_report_passes():
    enf = _enf()
    target = (
        "C1 model card: AUC=0.887, F2=0.6245, calibration ECE=0.068. "
        "Trained on 10M synthetic ISO 20022 events."
    )
    corpus = [
        ("rep-A", "Database migration succeeded; rollback procedure verified."),
        ("rep-B", "Quarterly financial summary; revenue grew 12% YoY."),
    ]
    result = enf.detect_boilerplate(target, corpus)

    assert result.is_boilerplate is False
    assert result.max_similarity < 0.5


def test_boilerplate_detection_empty_corpus():
    enf = _enf()
    result = enf.detect_boilerplate("anything", [])
    assert result.is_boilerplate is False
    assert result.unique_content_ratio == 1.0


# ---------------------------------------------------------------------------
# Timestamp validation
# ---------------------------------------------------------------------------


def test_report_timestamp_before_observation_period_rejected():
    enf = _enf()
    period_end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    report_dt = datetime(2026, 5, 1, tzinfo=timezone.utc)  # 1 month BEFORE end
    assert enf.validate_report_timestamps(report_dt, period_end) is False


def test_report_timestamp_after_observation_period_accepted():
    enf = _enf()
    period_end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    report_dt = period_end + timedelta(days=14)
    assert enf.validate_report_timestamps(report_dt, period_end) is True


# ---------------------------------------------------------------------------
# Jaccard similarity primitives
# ---------------------------------------------------------------------------


def test_jaccard_similarity_identical_and_disjoint():
    assert jaccard_similarity("hello world", "hello world") == 1.0
    # Truly disjoint character n-grams
    assert jaccard_similarity("aaaa", "zzzz") == 0.0
