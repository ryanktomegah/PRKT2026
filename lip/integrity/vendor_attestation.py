"""vendor_attestation.py — Verify vendor attestation chains before onboarding.

Complements vendor_validator.py: even if a vendor's reports look real, their
machine-readable attestations (SOC2, ISO 27001, DORA, PCI DSS) must carry
valid HMAC signatures, must not be expired, and must form an unbroken chain
back to a known parent. The Delve pattern was selling certifications that
were never actually validated; this module makes "show me the signed
attestation chain" a precondition of onboarding.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from lip.common.encryption import sign_hmac_sha256, verify_hmac_sha256

DEFAULT_MAX_ATTESTATION_AGE_DAYS = 365


# ---------------------------------------------------------------------------
# Enums + models
# ---------------------------------------------------------------------------


class AttestationType(str, Enum):
    SOC2_TYPE2 = "SOC2_TYPE2"
    ISO_27001 = "ISO_27001"
    DORA_COMPLIANCE = "DORA_COMPLIANCE"
    PCI_DSS = "PCI_DSS"
    CUSTOM = "CUSTOM"


class VendorAttestation(BaseModel):
    """Machine-readable, cryptographically signed vendor attestation."""

    model_config = ConfigDict(frozen=True)

    attestation_id: str
    vendor_id: str
    attestation_type: AttestationType
    issued_at: datetime
    valid_until: datetime
    claims: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    issuer_public_key_id: str = ""
    chain_parent_id: str | None = None
    signature: str = ""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttestationResult:
    attestation_id: str
    is_valid: bool
    signature_ok: bool
    is_expired: bool
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChainVerificationResult:
    is_valid: bool
    chain_length: int
    gaps: list[str] = field(default_factory=list)
    expired_links: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OnboardingResult:
    vendor_id: str
    approved: bool
    missing_attestations: list[AttestationType] = field(default_factory=list)
    expired_attestations: list[str] = field(default_factory=list)
    chain_issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


def _canonical(att: VendorAttestation) -> bytes:
    payload = att.model_dump(mode="json")
    payload.pop("signature", None)
    return json.dumps(payload, sort_keys=True, default=str).encode()


def sign_attestation(attestation: VendorAttestation, key: bytes) -> VendorAttestation:
    """Return a copy of *attestation* with its signature populated."""
    if not attestation.claims:
        raise ValueError("attestation.claims must not be empty")
    sig = sign_hmac_sha256(_canonical(attestation), key)
    return attestation.model_copy(update={"signature": sig})


class AttestationChainVerifier:
    """Verify single attestations and full chains."""

    def __init__(
        self,
        hmac_key: bytes,
        max_attestation_age_days: int = DEFAULT_MAX_ATTESTATION_AGE_DAYS,
    ) -> None:
        if len(hmac_key) < 32:
            raise ValueError(
                f"HMAC key must be ≥ 32 bytes; got {len(hmac_key)} bytes."
            )
        self._key = hmac_key
        self._max_age = timedelta(days=max_attestation_age_days)

    # -- single attestation -----------------------------------------------

    def verify_attestation(self, attestation: VendorAttestation) -> AttestationResult:
        issues: list[str] = []

        if not attestation.signature:
            issues.append("signature missing")
            return AttestationResult(
                attestation_id=attestation.attestation_id,
                is_valid=False,
                signature_ok=False,
                is_expired=False,
                issues=issues,
            )

        sig_ok = verify_hmac_sha256(
            _canonical(attestation), attestation.signature, self._key
        )
        if not sig_ok:
            issues.append("signature does not verify")

        now = datetime.now(timezone.utc)
        is_expired = attestation.valid_until < now
        if is_expired:
            issues.append(f"expired at {attestation.valid_until.isoformat()}")

        is_aged = (now - attestation.issued_at) > self._max_age
        if is_aged:
            issues.append("attestation is older than max age window")

        if not attestation.claims:
            issues.append("attestation has no claims")

        is_valid = sig_ok and not is_expired and not is_aged and bool(attestation.claims)
        return AttestationResult(
            attestation_id=attestation.attestation_id,
            is_valid=is_valid,
            signature_ok=sig_ok,
            is_expired=is_expired,
            issues=issues,
        )

    # -- chain --------------------------------------------------------------

    def verify_chain(
        self, chain: list[VendorAttestation]
    ) -> ChainVerificationResult:
        """Verify a chain of attestations: each links to its parent, no gaps."""
        if not chain:
            return ChainVerificationResult(
                is_valid=False,
                chain_length=0,
                gaps=["chain is empty"],
            )

        gaps: list[str] = []
        expired: list[str] = []
        by_id = {a.attestation_id: a for a in chain}

        for att in chain:
            single = self.verify_attestation(att)
            if not single.signature_ok:
                gaps.append(f"{att.attestation_id}: signature invalid")
            if single.is_expired:
                expired.append(att.attestation_id)
            if att.chain_parent_id and att.chain_parent_id not in by_id:
                gaps.append(
                    f"{att.attestation_id}: parent {att.chain_parent_id} missing"
                )

        # Exactly one root (chain_parent_id == None) is expected
        roots = [a for a in chain if a.chain_parent_id is None]
        if len(roots) != 1:
            gaps.append(f"expected exactly 1 root attestation, found {len(roots)}")

        return ChainVerificationResult(
            is_valid=not gaps and not expired,
            chain_length=len(chain),
            gaps=gaps,
            expired_links=expired,
        )

    # -- onboarding -------------------------------------------------------

    def check_onboarding_requirements(
        self,
        vendor_id: str,
        attestations: list[VendorAttestation],
        required_types: list[AttestationType],
    ) -> OnboardingResult:
        """Check that *vendor_id* has every *required_types* attestation, valid + signed."""
        provided_types = set()
        expired: list[str] = []
        chain_issues: list[str] = []

        for att in attestations:
            if att.vendor_id != vendor_id:
                continue
            single = self.verify_attestation(att)
            if single.is_valid:
                provided_types.add(att.attestation_type)
            else:
                if single.is_expired:
                    expired.append(att.attestation_id)
                if not single.signature_ok:
                    chain_issues.append(
                        f"{att.attestation_id}: signature invalid"
                    )

        missing = [t for t in required_types if t not in provided_types]
        approved = not missing and not expired and not chain_issues
        return OnboardingResult(
            vendor_id=vendor_id,
            approved=approved,
            missing_attestations=missing,
            expired_attestations=expired,
            chain_issues=chain_issues,
        )
