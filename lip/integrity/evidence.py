"""evidence.py — Shared evidence primitives for the Integrity Shield.

Foundation layer used by every other integrity module. Defines:
  * EvidenceRecord — cryptographically signed artifact backing a claim.
  * Claim          — an external assertion that must reference evidence.
  * EvidenceVerdict — outcome of verifying a claim against its evidence.

All signing/verification delegates to ``lip.common.encryption.sign_hmac_sha256``
and ``verify_hmac_sha256``. Canonical JSON serialisation mirrors the pattern in
``lip.c7_execution_agent.decision_log.DecisionLogger._entry_to_canonical_json``:
sorted keys, ``default=str`` for non-JSON types, ``signature`` field excluded
from the hash input so a record can be signed in place.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lip.common.encryption import sign_hmac_sha256, verify_hmac_sha256

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    """Category of underlying data captured by an EvidenceRecord."""

    METRIC_RUN = "METRIC_RUN"
    COMPLIANCE_REPORT = "COMPLIANCE_REPORT"
    OSS_SCAN = "OSS_SCAN"
    FORENSIC_LOG = "FORENSIC_LOG"


class ClaimType(str, Enum):
    """Category of external assertion that must be evidence-backed."""

    PERFORMANCE_METRIC = "PERFORMANCE_METRIC"
    COMPLIANCE_STATUS = "COMPLIANCE_STATUS"
    IP_OWNERSHIP = "IP_OWNERSHIP"
    SECURITY_POSTURE = "SECURITY_POSTURE"


class EvidenceVerdict(str, Enum):
    """Outcome of verifying a claim against its referenced evidence."""

    VERIFIED = "VERIFIED"
    INSUFFICIENT = "INSUFFICIENT"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class EvidenceRecord(BaseModel):
    """Cryptographically signed evidence backing a claim.

    The ``signature`` field is HMAC-SHA256 over the canonical JSON of every
    other field; tampering with any field invalidates the signature.
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    claim_id: str = ""  # populated when a Claim references this evidence
    evidence_type: EvidenceType
    created_at: datetime
    data_hash: str  # SHA-256 hex digest of the underlying data blob
    data_summary: dict[str, Any] = Field(default_factory=dict)
    source_module: str
    signature: str = ""


class Claim(BaseModel):
    """An external assertion that BPI is making.

    A Claim cannot be emitted unless ``evidence_ids`` is non-empty and every
    referenced EvidenceRecord verifies. The ``expires_at`` field encodes a
    freshness window; stale claims must be refreshed against new evidence.
    """

    model_config = ConfigDict(frozen=True)

    claim_id: str
    claim_type: ClaimType
    claim_text: str
    claimed_value: Any
    evidence_ids: list[str]
    created_at: datetime
    expires_at: datetime | None = None
    signature: str = ""


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_data_blob(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*.

    Used to bind an EvidenceRecord to its underlying data blob via the
    ``data_hash`` field. Deterministic: identical input always produces
    identical output.
    """
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Canonical JSON serialisation
# ---------------------------------------------------------------------------


def _canonical_json(model: BaseModel) -> bytes:
    """Return the canonical JSON of *model* with the ``signature`` field removed.

    Mirrors the pattern in DecisionLogger._entry_to_canonical_json: sorted
    keys, ``default=str`` for non-JSON types (datetime, Decimal, UUID), and
    the signature field excluded so the model can be signed in place.
    """
    payload = model.model_dump(mode="json")
    payload.pop("signature", None)
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# Sign / verify
# ---------------------------------------------------------------------------


def sign_evidence(record: EvidenceRecord, key: bytes) -> EvidenceRecord:
    """Return a copy of *record* with its ``signature`` field populated.

    Uses HMAC-SHA256 over the canonical JSON of all non-signature fields.
    The returned record is a new (frozen) instance — the original is not
    mutated.
    """
    canonical = _canonical_json(record)
    signature = sign_hmac_sha256(canonical, key)
    return record.model_copy(update={"signature": signature})


def verify_evidence(record: EvidenceRecord, key: bytes) -> bool:
    """Return True if *record*'s signature is a valid HMAC over its fields.

    Returns False if the signature is empty, malformed, or does not match
    the recomputed HMAC. Uses constant-time comparison via
    ``verify_hmac_sha256``.
    """
    if not record.signature:
        return False
    canonical = _canonical_json(record)
    return verify_hmac_sha256(canonical, record.signature, key)


def sign_claim(claim: Claim, key: bytes) -> Claim:
    """Return a copy of *claim* with its ``signature`` populated.

    Raises ValueError if ``evidence_ids`` is empty: a claim with no
    referenced evidence is structurally invalid and must not be signed.
    """
    if not claim.evidence_ids:
        raise ValueError(
            "Claim must reference at least one EvidenceRecord via evidence_ids; "
            "unbacked claims are forbidden by the Integrity Shield."
        )
    canonical = _canonical_json(claim)
    signature = sign_hmac_sha256(canonical, key)
    return claim.model_copy(update={"signature": signature})


def verify_claim(claim: Claim, key: bytes) -> bool:
    """Return True if *claim*'s signature is valid AND ``evidence_ids`` is non-empty."""
    if not claim.signature or not claim.evidence_ids:
        return False
    canonical = _canonical_json(claim)
    return verify_hmac_sha256(canonical, claim.signature, key)


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime`` for evidence timestamps."""
    return datetime.now(timezone.utc)
