"""claims_registry.py — No external claim without verifiable evidence.

Prevents the Delve failure mode of asserting metrics, compliance status, or
security posture without underlying evidence. Every Claim submitted to the
registry must reference at least one signed EvidenceRecord; numeric claims
are cross-checked against the evidence ``data_summary`` payload.

Usage::

    registry = ClaimsRegistry(hmac_key=key)
    ev_id = registry.register_evidence(signed_evidence)
    result = registry.submit_claim(signed_claim)  # raises ClaimRejected on failure
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lip.integrity.evidence import (
    Claim,
    EvidenceRecord,
    EvidenceVerdict,
    verify_claim,
    verify_evidence,
)

DEFAULT_MAX_CLAIM_AGE_HOURS = 720  # 30 days


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimVerificationResult:
    claim_id: str
    verdict: EvidenceVerdict
    evidence_count: int
    freshest_evidence_age_hours: float
    issues: list[str] = field(default_factory=list)


class ClaimRejected(Exception):
    """Raised when a claim cannot be emitted due to insufficient evidence."""

    def __init__(self, claim_id: str, verdict: EvidenceVerdict, reason: str) -> None:
        super().__init__(f"Claim {claim_id} rejected ({verdict.value}): {reason}")
        self.claim_id = claim_id
        self.verdict = verdict
        self.reason = reason


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ClaimsRegistry:
    """In-memory registry that enforces evidence-before-assertion."""

    def __init__(
        self,
        hmac_key: bytes,
        max_claim_age_hours: int = DEFAULT_MAX_CLAIM_AGE_HOURS,
    ) -> None:
        if len(hmac_key) < 32:
            raise ValueError(
                f"HMAC key must be ≥ 32 bytes; got {len(hmac_key)} bytes."
            )
        self._key = hmac_key
        self._evidence: dict[str, EvidenceRecord] = {}
        self._claims: dict[str, Claim] = {}
        self._max_age = timedelta(hours=max_claim_age_hours)

    # -- registration ------------------------------------------------------

    def register_evidence(self, evidence: EvidenceRecord) -> str:
        """Store a signed evidence record. Verifies the signature first.

        Raises ValueError if the signature does not verify.
        """
        if not verify_evidence(evidence, self._key):
            raise ValueError(
                f"Evidence {evidence.evidence_id} signature is invalid; "
                "cannot register unsigned or tampered evidence."
            )
        self._evidence[evidence.evidence_id] = evidence
        return evidence.evidence_id

    # -- submission --------------------------------------------------------

    def submit_claim(self, claim: Claim) -> ClaimVerificationResult:
        """Verify and store a claim. Raises ClaimRejected on failure.

        Checks performed, in order:
          1. Claim signature is valid.
          2. Claim references at least one EvidenceRecord (enforced by sign_claim).
          3. Every referenced EvidenceRecord exists in the registry.
          4. The freshest referenced evidence is within the staleness window.
        """
        issues: list[str] = []

        # 1. Signature
        if not verify_claim(claim, self._key):
            raise ClaimRejected(
                claim.claim_id,
                EvidenceVerdict.INSUFFICIENT,
                "claim signature missing or invalid",
            )

        # 2. evidence_ids non-empty already enforced by sign_claim, but
        # double-check defensively here.
        if not claim.evidence_ids:
            raise ClaimRejected(
                claim.claim_id,
                EvidenceVerdict.INSUFFICIENT,
                "claim references no evidence",
            )

        # 3. Every referenced evidence must be registered
        missing = [eid for eid in claim.evidence_ids if eid not in self._evidence]
        if missing:
            raise ClaimRejected(
                claim.claim_id,
                EvidenceVerdict.INSUFFICIENT,
                f"referenced evidence not in registry: {missing}",
            )

        # 4. Freshness — find the freshest referenced evidence
        now = datetime.now(timezone.utc)
        ages = [
            now - self._evidence[eid].created_at for eid in claim.evidence_ids
        ]
        freshest_age = min(ages)
        freshest_age_hours = freshest_age.total_seconds() / 3600.0

        if freshest_age > self._max_age:
            raise ClaimRejected(
                claim.claim_id,
                EvidenceVerdict.STALE,
                f"freshest evidence is {freshest_age_hours:.1f}h old "
                f"(max {self._max_age.total_seconds() / 3600:.0f}h)",
            )

        self._claims[claim.claim_id] = claim
        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            verdict=EvidenceVerdict.VERIFIED,
            evidence_count=len(claim.evidence_ids),
            freshest_evidence_age_hours=freshest_age_hours,
            issues=issues,
        )

    # -- metric cross-check ------------------------------------------------

    def verify_metric_claim(
        self,
        metric_name: str,
        claimed_value: float,
        evidence_id: str,
        tolerance: float = 0.001,
    ) -> bool:
        """Return True if the metric in the evidence's data_summary matches the claim.

        Used to catch the Delve pattern of asserting metrics that the
        underlying training run never produced. The evidence's
        ``data_summary[metric_name]`` must equal ``claimed_value`` within
        ``tolerance``.

        Raises ValueError if the evidence is not registered or the metric
        is not present in its data_summary.
        """
        if evidence_id not in self._evidence:
            raise ValueError(f"evidence {evidence_id} not registered")
        evidence = self._evidence[evidence_id]
        if metric_name not in evidence.data_summary:
            raise ValueError(
                f"metric {metric_name!r} not present in evidence "
                f"{evidence_id} data_summary"
            )
        actual = float(evidence.data_summary[metric_name])
        return abs(actual - float(claimed_value)) <= tolerance

    # -- accessors ---------------------------------------------------------

    def get_evidence_chain(self, claim_id: str) -> list[EvidenceRecord]:
        """Return all EvidenceRecords referenced by the named claim."""
        if claim_id not in self._claims:
            return []
        claim = self._claims[claim_id]
        return [
            self._evidence[eid]
            for eid in claim.evidence_ids
            if eid in self._evidence
        ]

    def get_claims_for_audit(
        self, since: datetime | None = None
    ) -> list[Claim]:
        """Return all registered claims, optionally filtered by created_at >= since."""
        if since is None:
            return list(self._claims.values())
        return [c for c in self._claims.values() if c.created_at >= since]

    def iter_evidence(self) -> list[EvidenceRecord]:
        """Return a snapshot of all registered evidence records."""
        return list(self._evidence.values())

    def evidence_count(self) -> int:
        return len(self._evidence)

    def claim_count(self) -> int:
        return len(self._claims)
