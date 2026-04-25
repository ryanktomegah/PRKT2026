"""
test_license_token_canonical.py — B3-02 regression test for HMAC canonical payload.

Before the 2026-04-09 fix, ``canonical_payload``, ``to_dict``, ``from_dict``,
and ``sign_token`` each maintained independent hand-enumerated field lists.
Adding a new field to the ``LicenseToken`` dataclass without updating all four
lists left the field **unsigned** — a privilege-escalation primitive where a
licensee could flip the flag client-side and still pass HMAC verification.

The fix derives the canonical payload from ``dataclasses.fields()``, so new
fields are automatically included in the HMAC.  ``sign_token`` uses
``dataclasses.replace`` instead of field-by-field copy.

These tests enforce:
1. Every dataclass field (except hmac_signature) appears in canonical_payload.
2. Adding a field to a subclass changes the HMAC.
3. schema_version is present and included in signing.
4. sign/verify round-trip with the new canonical derivation works correctly.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date, timedelta

from lip.c8_license_manager.license_token import (
    LicenseToken,
    sign_token,
    verify_token,
)

_KEY = b"test-key-for-b302-regression-!!!"


def _make_token(**overrides) -> LicenseToken:
    today = date.today()
    defaults = {
        "licensee_id": "TEST_BANK_001",
        "issue_date": today.isoformat(),
        "expiry_date": (today + timedelta(days=30)).isoformat(),
        "max_tps": 100,
        "aml_dollar_cap_usd": 0,
        "aml_count_cap": 0,
    }
    defaults.update(overrides)
    return LicenseToken(**defaults)  # type: ignore[arg-type]


class TestCanonicalPayloadCoversAllFields:
    """Every dataclass field except hmac_signature must be in the canonical payload."""

    def test_all_fields_in_canonical_payload(self):
        """B3-02: canonical_payload includes every field except hmac_signature."""
        token = _make_token()
        payload_bytes = token.canonical_payload()
        payload_str = payload_bytes.decode("utf-8")

        for f in dataclasses.fields(token):
            if f.name == "hmac_signature":
                continue
            assert '"' + f.name + '":' in payload_str or f'"{f.name}":' in payload_str, (
                f"Field {f.name!r} is missing from canonical_payload. "
                "B3-02 regression — unsigned field = privilege escalation."
            )

    def test_hmac_signature_excluded_from_canonical_payload(self):
        token = _make_token(hmac_signature="deadbeef")
        payload_str = token.canonical_payload().decode("utf-8")
        assert "hmac_signature" not in payload_str


class TestSchemaVersion:
    """B3-05: schema_version is signed and present in canonical payload."""

    def test_schema_version_in_payload(self):
        token = _make_token()
        payload_str = token.canonical_payload().decode("utf-8")
        assert '"schema_version":1' in payload_str

    def test_different_schema_version_changes_hmac(self):
        t1 = _make_token(schema_version=1)
        t2 = _make_token(schema_version=2)
        s1 = sign_token(t1, _KEY)
        s2 = sign_token(t2, _KEY)
        assert s1.hmac_signature != s2.hmac_signature

    def test_sign_verify_round_trip(self):
        token = _make_token()
        signed = sign_token(token, _KEY)
        assert signed.schema_version == 1
        assert verify_token(signed, _KEY)


class TestNewFieldAutoSigned:
    """B3-02 core invariant: adding a field changes the HMAC automatically."""

    def test_subclass_with_new_field_changes_hmac(self):
        """A subclass with a new bool field must produce a different HMAC
        than the base class — proving the field is included in the signature
        without any manual list update.
        """

        @dataclass
        class ExtendedToken(LicenseToken):
            cross_currency_allowed: bool = False

        base = _make_token()
        extended = ExtendedToken(
            **{f.name: getattr(base, f.name) for f in dataclasses.fields(base)},
            cross_currency_allowed=True,
        )

        base_payload = base.canonical_payload()
        ext_payload = extended.canonical_payload()

        assert base_payload != ext_payload, (
            "Extended token with a new field should produce a different "
            "canonical payload. B3-02 regression — field not auto-included."
        )

    def test_subclass_sign_verify_works(self):
        """Extended tokens can be signed and verified — no hand-maintained
        field list blocks them.
        """

        @dataclass
        class ExtendedToken(LicenseToken):
            new_feature_flag: bool = False

        ext = ExtendedToken(
            licensee_id="TEST_BANK",
            issue_date=date.today().isoformat(),
            expiry_date=(date.today() + timedelta(days=30)).isoformat(),
            max_tps=50,
            aml_dollar_cap_usd=0,
            aml_count_cap=0,
            new_feature_flag=True,
        )

        signed = sign_token(ext, _KEY)
        assert signed.hmac_signature != ""
        assert verify_token(signed, _KEY)


class TestToDictFromDictRoundTrip:
    """to_dict / from_dict must be consistent with all fields."""

    def test_round_trip_preserves_all_fields(self):
        token = _make_token(
            licensee_type="PROCESSOR",
            sub_licensee_bics=["DEUTDEFF", "COBADEFF"],
            annual_minimum_usd=50000,
            performance_premium_pct=0.15,
            platform_take_rate_pct=0.05,
        )
        d = token.to_dict()
        restored = LicenseToken.from_dict(d)
        assert restored.licensee_id == token.licensee_id
        assert restored.schema_version == token.schema_version
        assert restored.sub_licensee_bics == token.sub_licensee_bics

    def test_to_dict_includes_schema_version(self):
        token = _make_token()
        d = token.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == 1

    def test_sign_to_dict_from_dict_verify(self):
        """Full sign → serialize → deserialize → verify round-trip."""
        signed = sign_token(_make_token(), _KEY)
        d = signed.to_dict()
        restored = LicenseToken.from_dict(d)
        assert verify_token(restored, _KEY)
