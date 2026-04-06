"""Tests for lip.integrity.claims_registry."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lip.integrity.claims_registry import (
    ClaimRejected,
    ClaimsRegistry,
)
from lip.integrity.evidence import (
    Claim,
    ClaimType,
    EvidenceRecord,
    EvidenceType,
    EvidenceVerdict,
    hash_data_blob,
    sign_claim,
    sign_evidence,
    utcnow,
)

_KEY = b"integrity_test__32bytes_________"


def _evidence(eid: str = "ev-1", auc: float = 0.887, age_hours: float = 0.0) -> EvidenceRecord:
    created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    rec = EvidenceRecord(
        evidence_id=eid,
        evidence_type=EvidenceType.METRIC_RUN,
        created_at=created,
        data_hash=hash_data_blob(b"data"),
        data_summary={"auc": auc, "f2": 0.62},
        source_module="C1",
    )
    return sign_evidence(rec, _KEY)


def _claim(cid: str = "c-1", evidence_ids: list[str] | None = None, value: float = 0.887) -> Claim:
    c = Claim(
        claim_id=cid,
        claim_type=ClaimType.PERFORMANCE_METRIC,
        claim_text=f"AUC is {value}",
        claimed_value=value,
        evidence_ids=evidence_ids or ["ev-1"],
        created_at=utcnow(),
    )
    return sign_claim(c, _KEY)


# ---------------------------------------------------------------------------


def test_submit_claim_with_valid_evidence():
    reg = ClaimsRegistry(_KEY)
    reg.register_evidence(_evidence())
    result = reg.submit_claim(_claim())

    assert result.verdict == EvidenceVerdict.VERIFIED
    assert result.evidence_count == 1
    assert result.freshest_evidence_age_hours < 1.0


def test_submit_claim_without_registered_evidence_raises():
    reg = ClaimsRegistry(_KEY)
    # Skip registering the evidence
    with pytest.raises(ClaimRejected) as exc:
        reg.submit_claim(_claim())
    assert exc.value.verdict == EvidenceVerdict.INSUFFICIENT
    assert "not in registry" in exc.value.reason


def test_submit_claim_with_stale_evidence():
    reg = ClaimsRegistry(_KEY, max_claim_age_hours=1)
    reg.register_evidence(_evidence(age_hours=10))  # 10h old, max 1h
    with pytest.raises(ClaimRejected) as exc:
        reg.submit_claim(_claim())
    assert exc.value.verdict == EvidenceVerdict.STALE


def test_metric_claim_mismatch():
    reg = ClaimsRegistry(_KEY)
    reg.register_evidence(_evidence(auc=0.85))
    # Claim that AUC = 0.99, evidence says 0.85 → mismatch
    assert reg.verify_metric_claim("auc", 0.99, "ev-1") is False


def test_metric_claim_within_tolerance():
    reg = ClaimsRegistry(_KEY)
    reg.register_evidence(_evidence(auc=0.887))
    assert reg.verify_metric_claim("auc", 0.8871, "ev-1", tolerance=0.001) is True
    assert reg.verify_metric_claim("auc", 0.887, "ev-1") is True


def test_get_evidence_chain_returns_linked_records():
    reg = ClaimsRegistry(_KEY)
    reg.register_evidence(_evidence("ev-1"))
    reg.register_evidence(_evidence("ev-2"))
    reg.submit_claim(_claim(evidence_ids=["ev-1", "ev-2"]))

    chain = reg.get_evidence_chain("c-1")
    assert len(chain) == 2
    assert {e.evidence_id for e in chain} == {"ev-1", "ev-2"}


def test_get_claims_for_audit_filters_by_date():
    reg = ClaimsRegistry(_KEY)
    reg.register_evidence(_evidence())
    reg.submit_claim(_claim())

    all_claims = reg.get_claims_for_audit()
    assert len(all_claims) == 1

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    future_claims = reg.get_claims_for_audit(since=future)
    assert future_claims == []
