"""
taxonomy.py — C4 4-class dispute taxonomy
C4 Spec: NOT_DISPUTE, DISPUTE_CONFIRMED, DISPUTE_POSSIBLE, NEGOTIATION
"""
from enum import Enum
from typing import Optional


class DisputeClass(str, Enum):
    NOT_DISPUTE = "NOT_DISPUTE"                # No dispute indicators
    DISPUTE_CONFIRMED = "DISPUTE_CONFIRMED"    # Definitive dispute
    DISPUTE_POSSIBLE = "DISPUTE_POSSIBLE"      # Unclear, conservative (also timeout fallback)
    NEGOTIATION = "NEGOTIATION"                # Active negotiation underway


DISPUTE_CLASS_DESCRIPTIONS: dict = {
    DisputeClass.NOT_DISPUTE: (
        "Normal payment failure or rejection with no dispute indicators. "
        "The payer accepts the outcome or the failure is technical/administrative."
    ),
    DisputeClass.DISPUTE_CONFIRMED: (
        "Definitive dispute raised by payer or counterparty. Includes fraud, "
        "unauthorised transactions, explicit dispute submissions, and legal challenges."
    ),
    DisputeClass.DISPUTE_POSSIBLE: (
        "Possible dispute with insufficient information to confirm. "
        "Used as conservative fallback on timeout or ambiguous narratives."
    ),
    DisputeClass.NEGOTIATION: (
        "Active negotiation or partial settlement is underway between parties. "
        "Outcome not yet determined; payment may be partially fulfilled."
    ),
}

# Classes that require an immediate payment block (conservative safety measure)
DISPUTE_REQUIRES_BLOCK: set = {
    DisputeClass.DISPUTE_CONFIRMED,
    DisputeClass.DISPUTE_POSSIBLE,
}


def is_blocking(cls: DisputeClass) -> bool:
    """Return True if this dispute class requires an immediate payment block."""
    return cls in DISPUTE_REQUIRES_BLOCK


def timeout_fallback() -> DisputeClass:
    """
    Return the safe fallback class when classification times out.

    Always returns DISPUTE_POSSIBLE (conservative): on timeout we cannot
    confirm the absence of a dispute, so we block rather than pass through.
    """
    return DisputeClass.DISPUTE_POSSIBLE


# Mapping of raw LLM output tokens to DisputeClass values.
# The model is logit-constrained to emit exactly one of these tokens.
_TOKEN_MAP: dict = {
    "NOT_DISPUTE": DisputeClass.NOT_DISPUTE,
    "DISPUTE_CONFIRMED": DisputeClass.DISPUTE_CONFIRMED,
    "DISPUTE_POSSIBLE": DisputeClass.DISPUTE_POSSIBLE,
    "NEGOTIATION": DisputeClass.NEGOTIATION,
}


def from_logit_token(token: str) -> DisputeClass:
    """
    Map a model output token to a DisputeClass.

    Args:
        token: Raw string emitted by the LLM (expected to be one of the four
               valid output tokens after logit-constraining).

    Returns:
        The corresponding DisputeClass.

    Raises:
        ValueError: If *token* does not match any known class token.
    """
    normalised = token.strip().upper()
    if normalised not in _TOKEN_MAP:
        raise ValueError(
            f"Unknown logit token '{token}'. "
            f"Valid tokens: {list(_TOKEN_MAP.keys())}"
        )
    return _TOKEN_MAP[normalised]
