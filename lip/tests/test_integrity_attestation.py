"""Tests for lip.integrity.vendor_attestation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lip.integrity.vendor_attestation import (
    AttestationChainVerifier,
    AttestationType,
    VendorAttestation,
    sign_attestation,
)

_KEY = b"integrity_test__32bytes_________"
_NOW = datetime.now(timezone.utc)


def _att(
    aid: str,
    vendor_id: str = "v-1",
    att_type: AttestationType = AttestationType.SOC2_TYPE2,
    valid_for_days: int = 365,
    parent: str | None = None,
    issued_at: datetime | None = None,
) -> VendorAttestation:
    issued = issued_at or _NOW
    a = VendorAttestation(
        attestation_id=aid,
        vendor_id=vendor_id,
        attestation_type=att_type,
        issued_at=issued,
        valid_until=issued + timedelta(days=valid_for_days),
        claims=["controls effective"],
        chain_parent_id=parent,
        issuer_public_key_id="key-1",
    )
    return sign_attestation(a, _KEY)


# ---------------------------------------------------------------------------


def test_verify_valid_attestation():
    v = AttestationChainVerifier(_KEY)
    result = v.verify_attestation(_att("a-1"))
    assert result.is_valid is True
    assert result.signature_ok is True
    assert result.is_expired is False


def test_verify_expired_attestation_rejected():
    v = AttestationChainVerifier(_KEY)
    expired = _att(
        "a-old",
        valid_for_days=10,
        issued_at=_NOW - timedelta(days=400),
    )
    result = v.verify_attestation(expired)
    assert result.is_valid is False
    assert result.is_expired is True


def test_verify_chain_no_gaps():
    v = AttestationChainVerifier(_KEY)
    root = _att("root")
    child = _att("child-1", parent="root")
    grandchild = _att("gc-1", parent="child-1")
    result = v.verify_chain([root, child, grandchild])
    assert result.is_valid is True
    assert result.chain_length == 3
    assert result.gaps == []


def test_verify_chain_with_gap_detected():
    v = AttestationChainVerifier(_KEY)
    root = _att("root")
    orphan = _att("orphan", parent="missing-parent")
    result = v.verify_chain([root, orphan])
    assert result.is_valid is False
    assert any("missing-parent" in g for g in result.gaps)


def test_onboarding_all_required_types_present():
    v = AttestationChainVerifier(_KEY)
    atts = [
        _att("a1", att_type=AttestationType.SOC2_TYPE2),
        _att("a2", att_type=AttestationType.ISO_27001),
    ]
    result = v.check_onboarding_requirements(
        "v-1",
        atts,
        required_types=[AttestationType.SOC2_TYPE2, AttestationType.ISO_27001],
    )
    assert result.approved is True
    assert result.missing_attestations == []


def test_onboarding_missing_type_blocks_approval():
    v = AttestationChainVerifier(_KEY)
    atts = [_att("a1", att_type=AttestationType.SOC2_TYPE2)]
    result = v.check_onboarding_requirements(
        "v-1",
        atts,
        required_types=[AttestationType.SOC2_TYPE2, AttestationType.DORA_COMPLIANCE],
    )
    assert result.approved is False
    assert AttestationType.DORA_COMPLIANCE in result.missing_attestations
