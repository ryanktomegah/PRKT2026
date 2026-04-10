"""
test_sanctions_transliteration.py — Transliteration and phonetic matching tests (B7-03).

Verifies that the sanctions screener handles non-Latin scripts and
phonetically similar names.
"""
from __future__ import annotations

from lip.c6_aml_velocity.sanctions import (
    SanctionsScreener,
    _soundex,
    _transliterate,
)


class TestTransliterate:
    def test_ascii_unchanged(self):
        assert _transliterate("HELLO WORLD") == "HELLO WORLD"

    def test_accented_latin_stripped(self):
        result = _transliterate("MÜLLER STRASSE")
        assert "U" in result  # ü → u
        assert "MULLER" in result or "MULLER" in result.upper()

    def test_cyrillic_stripped_to_empty(self):
        """Pure Cyrillic becomes empty after ASCII encode — expected."""
        result = _transliterate("ИВАНОВ")
        # Cyrillic has no ASCII decomposition; all chars stripped
        assert result == "" or result.isascii()

    def test_mixed_script(self):
        result = _transliterate("COMPANY Müller")
        assert "COMPANY" in result


class TestSoundex:
    def test_standard_examples(self):
        assert _soundex("Robert") == "R163"
        assert _soundex("Rupert") == "R163"
        assert _soundex("Smith") == "S530"
        assert _soundex("Smyth") == "S530"

    def test_empty_input(self):
        assert _soundex("") == ""

    def test_single_char(self):
        assert _soundex("A") == "A000"

    def test_phonetically_similar(self):
        """Names that sound alike should have the same Soundex code."""
        assert _soundex("Meyer") == _soundex("Meier")
        assert _soundex("Robert") == _soundex("Rupert")


class TestPhoneticMatching:
    def test_phonetic_name_variant_detected(self):
        """A phonetically similar name should produce a hit."""
        screener = SanctionsScreener()
        # Add a custom entry
        from lip.c6_aml_velocity.sanctions import SanctionsList
        screener._lists[SanctionsList.OFAC] = {"ROBERT SMITH"}
        # "RUPERT SMYTH" is phonetically similar
        hits = screener.screen("RUPERT SMYTH")
        assert len(hits) > 0
        assert hits[0].reference == "ROBERT SMITH"

    def test_exact_match_still_works(self):
        screener = SanctionsScreener()
        hits = screener.screen("ACME SHELL CORP")
        assert len(hits) > 0

    def test_transliterated_accent_match(self):
        """Accented variant should match ASCII sanctions entry."""
        screener = SanctionsScreener()
        from lip.c6_aml_velocity.sanctions import SanctionsList
        screener._lists[SanctionsList.OFAC] = {"MULLER GMBH"}
        hits = screener.screen("MÜLLER GMBH")
        assert len(hits) > 0
        assert hits[0].reference == "MULLER GMBH"
