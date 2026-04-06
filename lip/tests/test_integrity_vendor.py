"""Tests for lip.integrity.vendor_validator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lip.integrity.vendor_validator import (
    VendorIndependenceCheck,
    VendorIntegrityValidator,
    VendorReport,
    VendorType,
)

_PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_PERIOD_END = datetime(2026, 3, 31, tzinfo=timezone.utc)
_AFTER_PERIOD = _PERIOD_END + timedelta(days=14)


def _report(
    rid: str,
    vendor_id: str = "v-1",
    client: str = "client-A",
    text: str = "Real audit findings: 3 medium and 1 low control gap identified.",
    incidents: int = 4,
    issued_at: datetime | None = None,
) -> VendorReport:
    return VendorReport(
        report_id=rid,
        vendor_id=vendor_id,
        vendor_name="Honest Auditors LLP",
        vendor_type=VendorType.COMPLIANCE_CERTIFIER,
        client_name=client,
        observation_period_start=_PERIOD_START,
        observation_period_end=_PERIOD_END,
        report_issued_at=issued_at or _AFTER_PERIOD,
        conclusions=["Controls partially effective"],
        incidents_found=incidents,
        report_text=text,
    )


# ---------------------------------------------------------------------------
# 1. Independence
# ---------------------------------------------------------------------------


def test_independence_check_same_entity_fails():
    v = VendorIntegrityValidator()
    chk = VendorIndependenceCheck(
        vendor_id="v-1",
        implementer_entity="Acme Compliance LLC",
        examiner_entity="Acme Compliance LLC",
    )
    assert v.check_independence(chk) is False


def test_independence_check_different_entities_passes():
    v = VendorIntegrityValidator()
    chk = VendorIndependenceCheck(
        vendor_id="v-1",
        implementer_entity="Internal Engineering",
        examiner_entity="External Big4 LLP",
    )
    assert v.check_independence(chk) is True


# ---------------------------------------------------------------------------
# 2. Boilerplate
# ---------------------------------------------------------------------------


def test_boilerplate_vendor_reports_flagged():
    v = VendorIntegrityValidator()
    boilerplate_text = (
        "Annual SOC 2 Type II report. Controls effective. Zero incidents. "
        "Zero personnel changes. No exceptions noted."
    )
    target = _report("r-A", text=boilerplate_text)
    corpus = [
        target,
        _report("r-B", client="client-B", text=boilerplate_text),
        _report("r-C", client="client-C", text=boilerplate_text),
    ]
    result = v.detect_report_boilerplate(target, corpus)
    assert result.is_boilerplate is True
    assert result.max_similarity == 1.0


def test_unique_vendor_reports_pass():
    v = VendorIntegrityValidator()
    target = _report(
        "r-A",
        text="Findings for client-A: missing MFA on legacy admin accounts; remediation tracked.",
    )
    corpus = [
        target,
        _report(
            "r-B",
            client="client-B",
            text="Findings for client-B: stale TLS certificates on three internal services.",
        ),
    ]
    result = v.detect_report_boilerplate(target, corpus)
    assert result.is_boilerplate is False
    assert result.max_similarity < 0.9


# ---------------------------------------------------------------------------
# 3. Freshness
# ---------------------------------------------------------------------------


def test_evidence_freshness_report_predates_observation_end_rejected():
    v = VendorIntegrityValidator()
    bad = _report("r-bad", issued_at=_PERIOD_END - timedelta(days=10))
    result = v.check_evidence_freshness(bad)
    assert result.is_fresh is False
    assert "BEFORE" in (result.issue or "")


def test_evidence_freshness_report_after_observation_passes():
    v = VendorIntegrityValidator()
    good = _report("r-good", issued_at=_AFTER_PERIOD)
    result = v.check_evidence_freshness(good)
    assert result.is_fresh is True


# ---------------------------------------------------------------------------
# 4. Zero-incident anomaly
# ---------------------------------------------------------------------------


def test_zero_incidents_anomaly_flagged():
    v = VendorIntegrityValidator()
    # 100 reports, 99 with zero incidents → 99% ratio, > 95% threshold
    reports = [
        _report(f"r-{i}", client=f"c-{i}", incidents=0) for i in range(99)
    ] + [_report("r-99", client="c-99", incidents=2)]
    result = v.check_zero_incidents_anomaly("v-1", reports)
    assert result.is_anomalous is True
    assert result.zero_incident_ratio == 0.99
    assert result.total_reports == 100


def test_zero_incidents_normal_ratio_passes():
    v = VendorIntegrityValidator()
    # 50% zero-incident — normal for a competent auditor
    reports = [_report(f"r-{i}", client=f"c-{i}", incidents=0) for i in range(5)] + [
        _report(f"r-{5+i}", client=f"c-{5+i}", incidents=3) for i in range(5)
    ]
    result = v.check_zero_incidents_anomaly("v-1", reports)
    assert result.is_anomalous is False


# ---------------------------------------------------------------------------
# Aggregate validate_vendor
# ---------------------------------------------------------------------------


def test_full_validation_all_pass():
    v = VendorIntegrityValidator()
    target = _report(
        "r-good",
        text="Findings for Acme Bank: 2 control gaps in change management; remediated.",
        incidents=2,
    )
    corpus = [
        target,
        _report(
            "r-other",
            client="other-bank",
            text="Findings for OtherBank: 4 IAM issues; tracking.",
            incidents=4,
        ),
    ]
    independence = VendorIndependenceCheck(
        vendor_id="v-1",
        implementer_entity="BPI Engineering",
        examiner_entity="External Auditors LLP",
    )
    result = v.validate_vendor(target, corpus, independence)
    assert result.passes is True
    assert result.independence_ok is True
    assert result.boilerplate_ok is True
    assert result.freshness_ok is True
    assert result.incident_pattern_ok is True
    assert result.issues == []


def test_full_validation_one_failure_blocks_vendor():
    v = VendorIntegrityValidator()
    # Bad: report issued before observation end
    bad = _report("r-bad", issued_at=_PERIOD_END - timedelta(days=5))
    independence = VendorIndependenceCheck(
        vendor_id="v-1",
        implementer_entity="BPI Engineering",
        examiner_entity="External Auditors LLP",
    )
    result = v.validate_vendor(bad, [bad], independence)
    assert result.passes is False
    assert result.freshness_ok is False
    assert any("BEFORE" in issue for issue in result.issues)
