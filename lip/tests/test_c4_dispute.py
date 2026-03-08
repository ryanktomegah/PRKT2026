"""
test_c4_dispute.py — Tests for C4 Dispute Classifier
"""

from lip.c4_dispute_classifier.model import DisputeClassifier, classify_dispute
from lip.c4_dispute_classifier.multilingual import LanguageDetector
from lip.c4_dispute_classifier.prefilter import apply_prefilter
from lip.c4_dispute_classifier.prompt import DisputePromptBuilder
from lip.c4_dispute_classifier.taxonomy import DisputeClass, is_blocking, timeout_fallback


class TestTaxonomy:
    def test_four_classes_defined(self):
        classes = list(DisputeClass)
        assert len(classes) == 4

    def test_is_blocking_confirmed(self):
        assert is_blocking(DisputeClass.DISPUTE_CONFIRMED) is True

    def test_is_blocking_possible(self):
        assert is_blocking(DisputeClass.DISPUTE_POSSIBLE) is True

    def test_not_blocking_not_dispute(self):
        assert is_blocking(DisputeClass.NOT_DISPUTE) is False

    def test_not_blocking_negotiation(self):
        assert is_blocking(DisputeClass.NEGOTIATION) is False

    def test_timeout_fallback_is_possible(self):
        assert timeout_fallback() == DisputeClass.DISPUTE_POSSIBLE


class TestPreFilter:
    def test_disp_code_triggers_confirmed(self):
        result = apply_prefilter("DISP")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED

    def test_frau_code_triggers_confirmed(self):
        result = apply_prefilter("FRAU")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED

    def test_legl_code_triggers_confirmed(self):
        result = apply_prefilter("LEGL")
        assert result.triggered is True

    def test_normal_code_not_triggered(self):
        result = apply_prefilter("AC01")
        assert result.triggered is False

    def test_none_code_not_triggered(self):
        result = apply_prefilter(None)
        assert result.triggered is False

    def test_fraud_narrative_triggers(self):
        result = apply_prefilter(None, narrative="This is a fraudulent transaction")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED

    def test_negotiate_narrative_triggers_negotiation(self):
        result = apply_prefilter(None, narrative="We want to negotiate a partial settlement")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.NEGOTIATION


class TestDisputeClassifier:
    def test_classify_returns_dict(self):
        clf = DisputeClassifier()
        result = clf.classify(rejection_code="AC01", narrative="Payment failed due to wrong IBAN")
        assert "dispute_class" in result
        assert "inference_latency_ms" in result

    def test_prefilter_shortcircuits(self):
        clf = DisputeClassifier()
        result = clf.classify(rejection_code="DISP", narrative="")
        assert result["prefilter_triggered"] is True
        assert result["dispute_class"] == DisputeClass.DISPUTE_CONFIRMED

    def test_fraud_narrative_classified(self):
        clf = DisputeClassifier()
        result = clf.classify(rejection_code=None, narrative="Unauthorized fraudulent charge")
        assert result["dispute_class"] in (DisputeClass.DISPUTE_CONFIRMED, DisputeClass.DISPUTE_POSSIBLE)

    def test_normal_narrative_not_dispute(self):
        clf = DisputeClassifier()
        result = clf.classify(rejection_code="AM04", narrative="Insufficient funds in account")
        assert result["dispute_class"] in (DisputeClass.NOT_DISPUTE, DisputeClass.DISPUTE_POSSIBLE)

    def test_classify_convenience_function(self):
        cls = classify_dispute("AC01", "Wrong account number")
        assert isinstance(cls, DisputeClass)

    def test_timeout_fallback_is_possible(self):
        """On timeout, classifier must return DISPUTE_POSSIBLE (conservative)."""
        assert timeout_fallback() == DisputeClass.DISPUTE_POSSIBLE


class TestLanguageDetector:
    def test_english_default(self):
        detector = LanguageDetector()
        lang = detector.detect("Payment failed due to insufficient funds")
        assert lang == "EN"

    def test_german_detection(self):
        detector = LanguageDetector()
        lang = detector.detect("Zahlung fehlgeschlagen wegen nicht ausreichender Deckung")
        assert lang == "DE"

    def test_supported_languages(self):
        detector = LanguageDetector()
        for lang in ["EN", "DE", "FR", "ES"]:
            assert detector.is_supported(lang)


class TestPromptBuilder:
    def test_build_returns_system_and_user(self):
        builder = DisputePromptBuilder()
        result = builder.build(
            rejection_code="AC01",
            narrative="Wrong account number",
            amount="50000",
            currency="USD",
            counterparty="Test Corp",
        )
        assert "system" in result
        assert "user" in result

    def test_system_prompt_contains_classes(self):
        builder = DisputePromptBuilder()
        result = builder.build("AC01", "test", "1000", "USD", "Corp")
        system = result["system"]
        assert "NOT_DISPUTE" in system
        assert "DISPUTE_CONFIRMED" in system
        assert "DISPUTE_POSSIBLE" in system
        assert "NEGOTIATION" in system
