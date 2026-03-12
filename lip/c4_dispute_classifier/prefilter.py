"""
prefilter.py — Rejection code pre-filter
C4 Spec Section 5.2: DISP/LEGL/FRAU/FRAD codes → immediate DISPUTE_CONFIRMED block
"""
import re
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
    # English — dispute variants (use stem "disput" to catch disputed/disputing)
    "disput",
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
    # German
    "bestritten",       # disputed/contested
    "betrug",           # fraud
    "betrügerisch",     # fraudulent
    "klage",            # lawsuit / legal claim
    "rückbuchung",      # chargeback
    "nicht genehmigt",  # not authorized
    "widerspruch",      # objection / dispute
    # French
    "contesté",         # contested
    "fraude",           # fraud
    "frauduleux",       # fraudulent
    "litige",           # dispute / litigation
    "non autorisé",     # not authorized
    "action en justice", # legal action
    "rétrofacturation", # chargeback
    # Spanish
    "disputado",        # disputed
    "fraude",           # fraud (also matches French — intentional)
    "fraudulento",      # fraudulent
    "no autorizado",    # not authorized
    "acción legal",     # legal action
    "contracargo",      # chargeback
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
# Negation detection helpers
# ---------------------------------------------------------------------------

_NEGATION_TOKENS: frozenset[str] = frozenset({
    # English
    "not", "no", "never", "neither", "nor", "without", "non",
    # German
    "kein", "keine", "nicht",
    # French
    "aucun", "aucune", "ne", "pas",
    # Spanish
    "sin", "ningún", "ninguna",
})

# ---------------------------------------------------------------------------
# Contraction expansion (applied before whitespace tokenisation)
# ---------------------------------------------------------------------------

# French clitic contractions — maps each contracted form (both straight and
# typographic apostrophe) to the expanded equivalent followed by a space so
# that "n'est" → "ne est" and the existing negation guard catches "ne".
_FRENCH_CONTRACTIONS: dict[str, str] = {
    "n'": "ne ",        # standard apostrophe
    "n\u2019": "ne ",   # typographic right single quotation mark (U+2019)
    "j'": "je ",
    "j\u2019": "je ",
    "l'": "le ",
    "l\u2019": "le ",
    "d'": "de ",
    "d\u2019": "de ",
    "qu'": "que ",
    "qu\u2019": "que ",
    "c'": "ce ",
    "c\u2019": "ce ",
    "s'": "se ",
    "s\u2019": "se ",
    "m'": "me ",
    "m\u2019": "me ",
    "t'": "te ",
    "t\u2019": "te ",
}


def _expand_contractions(text: str) -> str:
    """Expand French and Spanish contractions before whitespace tokenisation.

    French clitics (n', l', d', …) fuse with the following token and do not
    split on whitespace, so "n'est disputé" tokenises as ["n'est", "disputé"]
    and the negation token "ne" is never seen.  Expanding first produces
    ["ne", "est", "disputé"] and the existing ``_is_negated`` guard fires.

    Spanish ``del`` (de + el) and ``al`` (a + el) are grammatical contractions;
    expanding them prevents false negation matches while keeping "fraude" etc.
    detectable.
    """
    for contraction, expansion in _FRENCH_CONTRACTIONS.items():
        text = text.replace(contraction, expansion)
    # Spanish contracted prepositions — word-boundary guards against partial
    # matches inside longer words (e.g. "admiral", "idal").
    text = re.sub(r"\bdel\b", "de el", text)
    text = re.sub(r"\bal\b", "a el", text)
    return text


def _find_keyword_token_pos(tokens: list[str], kw: str) -> int | None:
    """Return the index of the token containing the first word of *kw*.

    Strips trailing punctuation before comparison so that "dispute." still
    matches stem "disput".
    """
    first_kw_tok = kw.split()[0]
    for i, tok in enumerate(tokens):
        if first_kw_tok in tok.rstrip(".,!?;:\"'()"):
            return i
    return None


def _is_negated(tokens: list[str], keyword_pos: int, window: int = 5) -> bool:
    """Return True if any negation token appears in the *window* tokens
    immediately before *keyword_pos*.

    Covers: "not a dispute", "no fraud", "ohne Betrug", "pas de litige",
            "sin fraude", and other patterns where a negation word precedes
            the dispute keyword within 5 whitespace-delimited tokens.
    """
    start = max(0, keyword_pos - window)
    return any(t in _NEGATION_TOKENS for t in tokens[start:keyword_pos])


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
        lowered = _expand_contractions(narrative.lower())
        tokens = lowered.split()

        for kw in _CONFIRMED_KEYWORDS:
            if kw in lowered:
                kw_pos = _find_keyword_token_pos(tokens, kw)
                if kw_pos is not None and _is_negated(tokens, kw_pos):
                    continue          # negated → skip this keyword
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
