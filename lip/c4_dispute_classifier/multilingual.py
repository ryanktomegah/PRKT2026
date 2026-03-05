"""
multilingual.py — Language detection and non-English handling
C4 Spec Section 11: EN, DE, FR, ES support
"""
import re
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: frozenset = frozenset({"EN", "DE", "FR", "ES"})


# ---------------------------------------------------------------------------
# Language detection patterns
# ---------------------------------------------------------------------------
# Each entry is a list of compiled regex patterns.  A language is considered
# detected when at least two of its patterns match the candidate text.

LANGUAGE_PATTERNS: dict = {
    "DE": [
        re.compile(r"\b(nicht|keine|kein)\b", re.IGNORECASE),
        re.compile(r"\b(zahlung|bezahlung)\b", re.IGNORECASE),
        re.compile(r"\b(betrag|beträge)\b", re.IGNORECASE),
        re.compile(r"\b(konto|kontonummer)\b", re.IGNORECASE),
        re.compile(r"\b(überweisung|überweisungen)\b", re.IGNORECASE),
        re.compile(r"\b(streit|streitig|bestreiten)\b", re.IGNORECASE),
        re.compile(r"\b(betrug|betrügerisch)\b", re.IGNORECASE),
        re.compile(r"\b(genehmigt|nicht\s+genehmigt)\b", re.IGNORECASE),
        re.compile(r"\b(verhandlung|verhandeln)\b", re.IGNORECASE),
        re.compile(r"\b(rückbuchung|rückzahlung)\b", re.IGNORECASE),
    ],
    "FR": [
        re.compile(r"\b(paiement|paiements)\b", re.IGNORECASE),
        re.compile(r"\b(montant|montants)\b", re.IGNORECASE),
        re.compile(r"\b(compte|comptes)\b", re.IGNORECASE),
        re.compile(r"\b(virement|virements)\b", re.IGNORECASE),
        re.compile(r"\b(litige|contestation)\b", re.IGNORECASE),
        re.compile(r"\b(fraude|frauduleux|frauduleuse)\b", re.IGNORECASE),
        re.compile(r"\b(non\s+autorisé|pas\s+autorisé)\b", re.IGNORECASE),
        re.compile(r"\b(négociation|négocier)\b", re.IGNORECASE),
        re.compile(r"\b(remboursement|rembourser)\b", re.IGNORECASE),
        re.compile(r"\b(règlement|résolution)\b", re.IGNORECASE),
    ],
    "ES": [
        re.compile(r"\b(pago|pagos)\b", re.IGNORECASE),
        re.compile(r"\b(monto|importe|cantidad)\b", re.IGNORECASE),
        re.compile(r"\b(cuenta|cuentas)\b", re.IGNORECASE),
        re.compile(r"\b(transferencia|transferencias)\b", re.IGNORECASE),
        re.compile(r"\b(disputa|disputado|impugnar)\b", re.IGNORECASE),
        re.compile(r"\b(fraude|fraudulento)\b", re.IGNORECASE),
        re.compile(r"\b(no\s+autorizado|sin\s+autorización)\b", re.IGNORECASE),
        re.compile(r"\b(negociación|negociar)\b", re.IGNORECASE),
        re.compile(r"\b(reembolso|devolución)\b", re.IGNORECASE),
        re.compile(r"\b(acuerdo|resolución)\b", re.IGNORECASE),
    ],
}

# Minimum pattern matches required to declare a language detection hit.
_DETECTION_THRESHOLD: int = 2


# ---------------------------------------------------------------------------
# Language-specific dispute keyword banks
# ---------------------------------------------------------------------------

DISPUTE_KEYWORDS_BY_LANGUAGE: dict = {
    "DE": {
        "confirmed": [
            "streit",
            "streitig",
            "bestreiten",
            "betrug",
            "betrügerisch",
            "nicht genehmigt",
            "nicht autorisiert",
            "unautorisiert",
            "rückbuchung",
            "klage",
        ],
        "negotiation": [
            "verhandlung",
            "verhandeln",
            "teilzahlung",
            "teilbetrag",
            "einigung",
            "kompromiss",
        ],
    },
    "FR": {
        "confirmed": [
            "litige",
            "contestation",
            "fraude",
            "frauduleux",
            "non autorisé",
            "pas autorisé",
            "chargeback",
            "opposition",
            "action en justice",
        ],
        "negotiation": [
            "négociation",
            "règlement",
            "paiement partiel",
            "accord partiel",
            "offre acceptée",
        ],
    },
    "ES": {
        "confirmed": [
            "disputa",
            "disputado",
            "fraude",
            "fraudulento",
            "no autorizado",
            "sin autorización",
            "impugnar",
            "cargo revertido",
            "acción legal",
        ],
        "negotiation": [
            "negociación",
            "negociar",
            "pago parcial",
            "acuerdo parcial",
            "oferta aceptada",
        ],
    },
}


# ---------------------------------------------------------------------------
# LanguageDetector
# ---------------------------------------------------------------------------

class LanguageDetector:
    """
    Lightweight, regex-based language detector for the four supported
    languages: EN, DE, FR, ES.

    Returns ``'EN'`` as the default when no non-English language is
    confidently detected.
    """

    def detect(self, text: str) -> str:
        """
        Detect the primary language of *text*.

        Scores each non-English language by counting pattern matches.
        The language with the highest score above the detection threshold
        is returned.  If no language exceeds the threshold, ``'EN'`` is
        returned.

        Args:
            text: Input text (narrative or any free-form string).

        Returns:
            ISO 639-1 language code: one of ``'EN'``, ``'DE'``, ``'FR'``, ``'ES'``.
        """
        if not text or not text.strip():
            return "EN"

        scores: dict = {}
        for lang, patterns in LANGUAGE_PATTERNS.items():
            score = sum(1 for pattern in patterns if pattern.search(text))
            scores[lang] = score

        best_lang = max(scores, key=lambda k: scores[k])
        if scores[best_lang] >= _DETECTION_THRESHOLD:
            return best_lang

        return "EN"

    def is_supported(self, lang: str) -> bool:
        """Return True if *lang* is in the supported language set."""
        return lang.strip().upper() in SUPPORTED_LANGUAGES


# ---------------------------------------------------------------------------
# MultilingualNarrativeProcessor
# ---------------------------------------------------------------------------

class MultilingualNarrativeProcessor:
    """
    Processes payment narratives with language detection and normalisation.

    Combines :class:`LanguageDetector` with text cleaning and keyword
    extraction to prepare narratives for downstream pre-filter and LLM
    inference stages.
    """

    def __init__(self, detector: Optional[LanguageDetector] = None) -> None:
        self._detector = detector if detector is not None else LanguageDetector()

    def process(self, narrative: str) -> Tuple[str, str]:
        """
        Clean and detect the language of *narrative*.

        Args:
            narrative: Raw payment narrative string.

        Returns:
            A tuple ``(cleaned_narrative, detected_language)`` where
            ``cleaned_narrative`` is normalised and ``detected_language`` is
            an ISO 639-1 code.
        """
        detected_language = self._detector.detect(narrative)
        cleaned = self.normalize_narrative(narrative, detected_language)
        return cleaned, detected_language

    def normalize_narrative(self, narrative: str, language: str) -> str:
        """
        Normalise a narrative string.

        Operations (language-agnostic):
          1. Strip leading/trailing whitespace.
          2. Collapse internal whitespace runs to single spaces.
          3. Lowercase.

        Args:
            narrative: Raw narrative string.
            language:  Detected language code (reserved for future
                       language-specific normalisation rules).

        Returns:
            Normalised narrative string.
        """
        if not narrative:
            return ""
        normalised = narrative.strip()
        normalised = re.sub(r"\s+", " ", normalised)
        normalised = normalised.lower()
        return normalised

    def extract_dispute_keywords(self, narrative: str, language: str) -> list:
        """
        Extract dispute-related keywords from *narrative* for the given *language*.

        Checks both English keyword banks (via inline constants) and the
        language-specific banks in :data:`DISPUTE_KEYWORDS_BY_LANGUAGE`.

        Args:
            narrative: Normalised narrative text.
            language:  ISO 639-1 language code.

        Returns:
            List of found keyword strings (may be empty).
        """
        lowered = narrative.lower()
        found: list = []

        # English baseline keywords (always checked)
        _en_confirmed = [
            "dispute", "fraud", "unauthorized", "unauthorised",
            "not authorised", "not authorized", "did not authorize",
            "fraudulent", "contested", "chargeback",
        ]
        _en_negotiation = [
            "negotiate", "negotiation", "settlement", "partial",
        ]
        for kw in _en_confirmed + _en_negotiation:
            if kw in lowered and kw not in found:
                found.append(kw)

        # Language-specific keywords
        lang_upper = language.strip().upper()
        if lang_upper in DISPUTE_KEYWORDS_BY_LANGUAGE:
            lang_banks = DISPUTE_KEYWORDS_BY_LANGUAGE[lang_upper]
            for kw_list in lang_banks.values():
                for kw in kw_list:
                    if kw in lowered and kw not in found:
                        found.append(kw)

        return found
