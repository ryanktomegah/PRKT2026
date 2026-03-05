"""
prefilter.py — Rejection code pre-filter
C4 Spec Section 5.2: DISP/LEGL/FRAU/FRAD codes → immediate DISPUTE_CONFIRMED block
"""
from dataclasses import dataclass
from typing import Optional

from .taxonomy import DisputeClass


# ---------------------------------------------------------------------------
# Rejection code sets
# ---------------------------------------------------------------------------

# Codes that unconditionally map to DISPUTE_CONFIRMED and trigger an immediate
# payment block.  These match standard ISO 20022 / SWIFT rejection reason codes
# used for fraud, legal, and explicit dispute submissions.
IMMEDIATE_BLOCK_CODES: frozenset = frozenset({
    "DISP",   # Dispute (explicit)
    "LEGL",   # Legal order / regulatory hold
    "FRAU",   # Fraud
    "FRAD",   # Fraudulent instruction
    "DUPL",   # Duplicate payment (implies contested transaction)
})

# Codes that are indicative of a dispute but cannot be confirmed without
# further review — classified conservatively as DISPUTE_POSSIBLE.
POSSIBLE_CODES: frozenset = frozenset({
    "MD06",   # Refund request by end customer
    "CUST",   # Requested by customer (ambiguous intent)
    "MS02",   # Not specified by agent (unknown rejection reason)
})

# ---------------------------------------------------------------------------
# Narrative keyword banks
# ---------------------------------------------------------------------------

# Phrase fragments that, when found in the free-text narrative, escalate to
# DISPUTE_CONFIRMED regardless of rejection code.
_CONFIRMED_KEYWORDS: tuple = (
    "dispute",
    "fraud",
    "unauthorized",
    "unauthorised",
    "not authorised",
    "not authorized",
    "did not authorize",
    "did not authorise",
    "fraudulent",
    "contested",
    "chargeback",
    "clawback",
    "legal action",
    "legal hold",
)

# Phrase fragments that map to NEGOTIATION.
_NEGOTIATION_KEYWORDS: tuple = (
    "negotiate",
    "negotiation",
    "settlement",
    "partial settlement",
    "partial payment",
    "partial",
    "agreed amount",
    "offer accepted",
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PreFilterResult:
    """Result returned by the pre-filter stage."""

    triggered: bool
    """True when the pre-filter produced a conclusive classification."""

    dispute_class: DisputeClass
    """The assigned DisputeClass (always present, defaults to NOT_DISPUTE when
    not triggered so callers can safely read this field)."""

    rejection_code: Optional[str]
    """The rejection code that triggered this result, if applicable."""

    reason: str
    """Human-readable explanation of why this result was produced."""


# ---------------------------------------------------------------------------
# PreFilter class
# ---------------------------------------------------------------------------

class PreFilter:
    """
    Fast, rule-based pre-filter that short-circuits LLM inference for
    well-known rejection codes and high-confidence narrative patterns.

    When *triggered* is True the caller should return the pre-filter result
    immediately without invoking the LLM.
    """

    def check(
        self,
        rejection_code: Optional[str],
        narrative: Optional[str] = None,
    ) -> PreFilterResult:
        """
        Evaluate a payment rejection against the pre-filter rule set.

        Args:
            rejection_code: ISO 20022 / SWIFT rejection reason code, or None.
            narrative: Free-text payment narrative, or None.

        Returns:
            A :class:`PreFilterResult`.  Callers should check ``triggered``
            before deciding whether to proceed to LLM inference.
        """
        normalised_code = rejection_code.strip().upper() if rejection_code else None

        # --- 1. Immediate-block rejection codes ---
        if normalised_code and normalised_code in IMMEDIATE_BLOCK_CODES:
            return PreFilterResult(
                triggered=True,
                dispute_class=DisputeClass.DISPUTE_CONFIRMED,
                rejection_code=normalised_code,
                reason=(
                    f"Rejection code '{normalised_code}' is in the immediate-block "
                    "set (DISP/LEGL/FRAU/FRAD/DUPL) — classified as DISPUTE_CONFIRMED."
                ),
            )

        # --- 2. Possible-dispute rejection codes ---
        if normalised_code and normalised_code in POSSIBLE_CODES:
            return PreFilterResult(
                triggered=True,
                dispute_class=DisputeClass.DISPUTE_POSSIBLE,
                rejection_code=normalised_code,
                reason=(
                    f"Rejection code '{normalised_code}' is in the possible-dispute "
                    "set (MD06/CUST/MS02) — classified as DISPUTE_POSSIBLE."
                ),
            )

        # --- 3. Narrative keyword scan ---
        if narrative:
            keyword_class = self._check_narrative_keywords(narrative)
            if keyword_class is not None:
                return PreFilterResult(
                    triggered=True,
                    dispute_class=keyword_class,
                    rejection_code=normalised_code,
                    reason=(
                        f"Narrative keyword scan produced '{keyword_class.value}' — "
                        "pre-filter triggered without code match."
                    ),
                )

        # --- 4. No pre-filter applies — proceed to LLM ---
        return PreFilterResult(
            triggered=False,
            dispute_class=DisputeClass.NOT_DISPUTE,
            rejection_code=normalised_code,
            reason="No pre-filter rule matched; forwarding to LLM classifier.",
        )

    def _check_narrative_keywords(self, narrative: str) -> Optional[DisputeClass]:
        """
        Scan *narrative* for high-signal keyword phrases.

        Confirmed keywords are checked before negotiation keywords so that a
        narrative containing both (e.g. "fraud settlement offer") is classified
        conservatively as DISPUTE_CONFIRMED.

        Returns:
            A :class:`DisputeClass` if a keyword matched, else ``None``.
        """
        lowered = narrative.lower()

        for kw in _CONFIRMED_KEYWORDS:
            if kw in lowered:
                return DisputeClass.DISPUTE_CONFIRMED

        for kw in _NEGOTIATION_KEYWORDS:
            if kw in lowered:
                return DisputeClass.NEGOTIATION

        return None


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def apply_prefilter(
    rejection_code: Optional[str],
    narrative: Optional[str] = None,
) -> PreFilterResult:
    """
    Convenience wrapper that creates a :class:`PreFilter` and calls
    :meth:`~PreFilter.check`.

    Args:
        rejection_code: ISO 20022 / SWIFT rejection reason code, or None.
        narrative: Free-text payment narrative, or None.

    Returns:
        A :class:`PreFilterResult`.
    """
    return PreFilter().check(rejection_code, narrative)
