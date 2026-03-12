"""
test_c4_contraction_expansion.py — C4 Step 2b: Romance language contraction expansion

Validates that French clitics (n', l', d', …) and Spanish contracted prepositions
(del, al) are expanded before whitespace tokenisation so that the negation guard in
_is_negated() can recognise "ne" and suppress false DISPUTE_CONFIRMED results.
"""
from lip.c4_dispute_classifier.prefilter import _expand_contractions, apply_prefilter
from lip.c4_dispute_classifier.taxonomy import DisputeClass  # noqa: E402

# ---------------------------------------------------------------------------
# Unit tests — _expand_contractions()
# ---------------------------------------------------------------------------


class TestExpandContractions:
    def test_standard_apostrophe_n(self) -> None:
        assert _expand_contractions("n'est frauduleux") == "ne est frauduleux"

    def test_typographic_apostrophe_n(self) -> None:
        # U+2019 RIGHT SINGLE QUOTATION MARK — common in pasted text
        assert _expand_contractions("n\u2019est frauduleux") == "ne est frauduleux"

    def test_multiple_contractions_in_one_string(self) -> None:
        result = _expand_contractions("il n'a pas l'autorisé")
        assert "ne " in result
        assert "le " in result
        assert "n'" not in result

    def test_spanish_del_word_boundary(self) -> None:
        # "del" expands; "admiral" must not be touched
        result = _expand_contractions("pago del fraude — admiral sin culpa")
        assert "de el fraude" in result
        assert "admiral" in result  # partial match guard

    def test_spanish_al_word_boundary(self) -> None:
        result = _expand_contractions("referente al fraude")
        assert "a el fraude" in result

    def test_no_mutation_on_clean_text(self) -> None:
        text = "payment not authorized"
        assert _expand_contractions(text) == text


# ---------------------------------------------------------------------------
# Integration tests — apply_prefilter() with French contraction inputs
# ---------------------------------------------------------------------------


class TestFrenchContractionNegation:
    def test_n_est_negates_dispute(self) -> None:
        """n'est expands to 'ne est'; 'ne' suppresses the CONFIRMED result."""
        result = apply_prefilter(None, "ce virement n'est disputé")
        assert result.dispute_class != DisputeClass.DISPUTE_CONFIRMED

    def test_n_a_with_pas_negates_litige(self) -> None:
        """Double negation (ne + pas) — both tokens visible after expansion."""
        result = apply_prefilter(None, "paiement n'a pas de litige")
        assert result.dispute_class != DisputeClass.DISPUTE_CONFIRMED

    def test_n_y_negates_litige(self) -> None:
        """n'y avait — 'ne' before 'litige'."""
        result = apply_prefilter(None, "il n'y avait litige ici")
        assert result.dispute_class != DisputeClass.DISPUTE_CONFIRMED

    def test_typographic_apostrophe_negation(self) -> None:
        """Typographic apostrophe (U+2019) must be expanded like the standard one."""
        result = apply_prefilter(None, "n\u2019est frauduleux")
        assert result.dispute_class != DisputeClass.DISPUTE_CONFIRMED

    def test_c_est_does_not_suppress_fraud(self) -> None:
        """c' → 'ce ' — 'ce' is NOT a negation token; dispute must still fire."""
        result = apply_prefilter(None, "c'est une fraude évidente")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED


# ---------------------------------------------------------------------------
# Integration tests — Spanish contraction expansion preserves dispute signal
# ---------------------------------------------------------------------------


class TestSpanishContractionExpansion:
    def test_del_fraude_still_detected(self) -> None:
        """'del fraude' → 'de el fraude'; 'de', 'el' are not negation tokens."""
        result = apply_prefilter(None, "pago del fraude reportado")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED

    def test_al_fraude_still_detected(self) -> None:
        """'al fraude' → 'a el fraude'; no negation introduced."""
        result = apply_prefilter(None, "referente al fraude")
        assert result.triggered is True
        assert result.dispute_class == DisputeClass.DISPUTE_CONFIRMED
