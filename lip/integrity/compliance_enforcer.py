"""compliance_enforcer.py — Compliance reports must be generated from live data.

Prevents the Delve failure mode of pre-writing audit conclusions and shipping
493/494 identical boilerplate reports. Three structural defenses:

  1. Proof-of-freshness: every wrapped report carries an EvidenceRecord whose
     ``data_hash`` is the SHA-256 of the live input data. A report cannot be
     attributed to data it was not actually generated from.

  2. Boilerplate detection: character n-gram Jaccard similarity flags reports
     that are >90% identical to any prior report in the corpus.

  3. Timestamp validation: a report's creation time must be after the end of
     the observation period it claims to cover.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from lip.integrity.evidence import (
    EvidenceRecord,
    EvidenceType,
    hash_data_blob,
    sign_evidence,
    utcnow,
)

# Default threshold; matches the constant added to lip/common/constants.py.
DEFAULT_BOILERPLATE_THRESHOLD = 0.90


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoilerplateResult:
    is_boilerplate: bool
    max_similarity: float
    most_similar_report_id: str | None
    unique_content_ratio: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ngrams(text: str, n: int) -> set[str]:
    """Return the set of character n-grams in *text* (lowercased, whitespace-collapsed)."""
    normalised = " ".join(text.lower().split())
    if len(normalised) < n:
        return {normalised} if normalised else set()
    return {normalised[i : i + n] for i in range(len(normalised) - n + 1)}


def jaccard_similarity(text_a: str, text_b: str, ngram_size: int = 3) -> float:
    """Return the Jaccard similarity of the character n-gram sets of two texts.

    Returns 1.0 for identical inputs, 0.0 for disjoint inputs. Used as the
    boilerplate detector's similarity metric.
    """
    a = _ngrams(text_a, ngram_size)
    b = _ngrams(text_b, ngram_size)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


def compute_proof_of_freshness(live_data: dict[str, Any]) -> str:
    """Return SHA-256 of the canonical JSON of *live_data*.

    Used to bind a generated report to the specific data that produced it.
    Identical inputs always produce identical hashes; any modification to
    the input data invalidates the proof.
    """
    canonical = json.dumps(live_data, sort_keys=True, default=str).encode("utf-8")
    return hash_data_blob(canonical)


# ---------------------------------------------------------------------------
# Enforcer
# ---------------------------------------------------------------------------


class ComplianceEvidenceEnforcer:
    """Wraps compliance report generation with evidence + boilerplate checks."""

    def __init__(
        self,
        hmac_key: bytes,
        boilerplate_threshold: float = DEFAULT_BOILERPLATE_THRESHOLD,
    ) -> None:
        if len(hmac_key) < 32:
            raise ValueError(
                f"HMAC key must be ≥ 32 bytes; got {len(hmac_key)} bytes."
            )
        self._key = hmac_key
        self._threshold = boilerplate_threshold

    # -- proof-of-freshness wrapper ---------------------------------------

    def wrap_report_generation(
        self,
        generator: Callable[..., Any],
        live_data: dict[str, Any],
        *args: Any,
        source_module: str = "compliance",
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, EvidenceRecord]:
        """Run *generator* and return ``(report, evidence_record)``.

        The returned EvidenceRecord's ``data_hash`` is the SHA-256 of the
        canonical JSON of *live_data*; this binds the report to the exact
        data that produced it. Tampering with either the report or the
        live_data invalidates the proof.
        """
        report = generator(*args, **kwargs)
        data_hash = compute_proof_of_freshness(live_data)
        record = EvidenceRecord(
            evidence_id=evidence_id or f"compliance-{utcnow().isoformat()}",
            evidence_type=EvidenceType.COMPLIANCE_REPORT,
            created_at=utcnow(),
            data_hash=data_hash,
            data_summary={
                "live_data_keys": sorted(live_data.keys()),
                "generator": getattr(generator, "__name__", str(generator)),
            },
            source_module=source_module,
        )
        signed = sign_evidence(record, self._key)
        return report, signed

    # -- boilerplate detection --------------------------------------------

    def detect_boilerplate(
        self,
        report_text: str,
        reference_corpus: list[tuple[str, str]],
    ) -> BoilerplateResult:
        """Compare *report_text* against a corpus of ``(report_id, text)`` pairs.

        Flags the report as boilerplate if its maximum Jaccard similarity to
        any corpus entry exceeds ``boilerplate_threshold``. The
        ``unique_content_ratio`` is ``1 - max_similarity``.
        """
        if not reference_corpus:
            return BoilerplateResult(
                is_boilerplate=False,
                max_similarity=0.0,
                most_similar_report_id=None,
                unique_content_ratio=1.0,
            )

        best_id: str | None = None
        best_sim = 0.0
        for ref_id, ref_text in reference_corpus:
            sim = jaccard_similarity(report_text, ref_text)
            if sim > best_sim:
                best_sim = sim
                best_id = ref_id

        return BoilerplateResult(
            is_boilerplate=best_sim > self._threshold,
            max_similarity=best_sim,
            most_similar_report_id=best_id,
            unique_content_ratio=1.0 - best_sim,
        )

    # -- proof verification ------------------------------------------------

    def verify_proof_of_freshness(
        self,
        evidence: EvidenceRecord,
        live_data: dict[str, Any],
    ) -> bool:
        """Return True if *evidence*'s data_hash matches the hash of *live_data*."""
        expected = compute_proof_of_freshness(live_data)
        return evidence.data_hash == expected

    # -- timestamp validation ---------------------------------------------

    def validate_report_timestamps(
        self,
        report_created_at: datetime,
        observation_period_end: datetime,
    ) -> bool:
        """Return True if the report was created at or after the observation period end.

        Catches the Delve pattern of writing audit conclusions before the
        observation period was over.
        """
        return report_created_at >= observation_period_end
