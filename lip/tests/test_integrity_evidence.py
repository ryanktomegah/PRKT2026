"""Tests for lip.integrity.evidence — shared evidence primitives."""
from __future__ import annotations

import pytest

from lip.integrity.evidence import (
    Claim,
    ClaimType,
    EvidenceRecord,
    EvidenceType,
    _canonical_json,
    hash_data_blob,
    sign_claim,
    sign_evidence,
    utcnow,
    verify_claim,
    verify_evidence,
)

_KEY = b"integrity_test__32bytes_________"


def _make_evidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev-001",
        claim_id="",
        evidence_type=EvidenceType.METRIC_RUN,
        created_at=utcnow(),
        data_hash=hash_data_blob(b"raw training summary"),
        data_summary={"auc": 0.887, "f2": 0.6245},
        source_module="C1",
    )


def _make_claim() -> Claim:
    return Claim(
        claim_id="claim-001",
        claim_type=ClaimType.PERFORMANCE_METRIC,
        claim_text="C1 validation AUC is 0.887",
        claimed_value=0.887,
        evidence_ids=["ev-001"],
        created_at=utcnow(),
    )


# ---------------------------------------------------------------------------
# 1. Sign + verify round-trip
# ---------------------------------------------------------------------------


def test_sign_and_verify_evidence_round_trip():
    record = _make_evidence()
    signed = sign_evidence(record, _KEY)

    assert signed.signature != ""
    assert verify_evidence(signed, _KEY) is True


# ---------------------------------------------------------------------------
# 2. Tampered evidence fails verification
# ---------------------------------------------------------------------------


def test_tampered_evidence_fails_verification():
    signed = sign_evidence(_make_evidence(), _KEY)

    # Mutate a field by constructing a new record with a different summary;
    # the original signature must no longer verify.
    tampered = signed.model_copy(update={"data_summary": {"auc": 0.999}})

    assert verify_evidence(tampered, _KEY) is False


# ---------------------------------------------------------------------------
# 3. hash_data_blob is deterministic
# ---------------------------------------------------------------------------


def test_hash_data_blob_deterministic():
    blob = b"identical input bytes"
    assert hash_data_blob(blob) == hash_data_blob(blob)
    assert hash_data_blob(b"a") != hash_data_blob(b"b")
    # SHA-256 hex digest is 64 characters
    assert len(hash_data_blob(blob)) == 64


# ---------------------------------------------------------------------------
# 4. Claim signing requires evidence_ids
# ---------------------------------------------------------------------------


def test_sign_claim_requires_evidence_ids():
    unbacked = Claim(
        claim_id="bad-claim",
        claim_type=ClaimType.PERFORMANCE_METRIC,
        claim_text="AUC is 0.99",
        claimed_value=0.99,
        evidence_ids=[],  # empty -> forbidden
        created_at=utcnow(),
    )

    with pytest.raises(ValueError, match="evidence_ids"):
        sign_claim(unbacked, _KEY)

    # Backed claim signs and verifies
    signed = sign_claim(_make_claim(), _KEY)
    assert verify_claim(signed, _KEY) is True


# ---------------------------------------------------------------------------
# 5. Canonical JSON excludes the signature field
# ---------------------------------------------------------------------------


def test_canonical_json_excludes_signature():
    signed = sign_evidence(_make_evidence(), _KEY)

    payload = _canonical_json(signed)
    assert b"signature" not in payload, (
        "Canonical JSON must exclude the signature field, otherwise "
        "self-referential signing would be impossible."
    )

    # Re-signing the same record yields the same signature (determinism check)
    second = sign_evidence(
        signed.model_copy(update={"signature": ""}),
        _KEY,
    )
    assert second.signature == signed.signature
