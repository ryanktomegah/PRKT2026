"""
test_c8_license.py — Unit tests for C8 LicenseToken and LicenseBootValidator.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from lip.c8_license_manager.boot_validator import LicenseBootValidator
from lip.c8_license_manager.license_token import (
    ALL_COMPONENTS,
    LicenseeContext,
    LicenseToken,
    sign_token,
    verify_token,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

_KEY = b"bpi-test-signing-key-32-bytes!!!"


def _make_token(
    licensee_id: str = "TEST_BANK_001",
    days_until_expiry: int = 365,
    max_tps: int = 500,
    aml_dollar_cap: int = 1000000,
    aml_count_cap: int = 100,
    components: list | None = None,
) -> LicenseToken:
    today = date.today()
    expiry = today + timedelta(days=days_until_expiry)
    return LicenseToken(
        licensee_id=licensee_id,
        issue_date=today.isoformat(),
        expiry_date=expiry.isoformat(),
        max_tps=max_tps,
        aml_dollar_cap_usd=aml_dollar_cap,
        aml_count_cap=aml_count_cap,
        permitted_components=components or list(ALL_COMPONENTS),
    )


# ── LicenseToken tests ───────────────────────────────────────────────────────

class TestLicenseToken:

    def test_sign_and_verify(self):
        token = _make_token()
        signed = sign_token(token, _KEY)
        assert signed.hmac_signature != ""
        assert verify_token(signed, _KEY)

    def test_wrong_key_fails(self):
        signed = sign_token(_make_token(), _KEY)
        wrong_key = b"wrong-key-for-verification!!!__"
        assert not verify_token(signed, wrong_key)

    def test_expired_token_fails(self):
        token = _make_token(days_until_expiry=-1)
        signed = sign_token(token, _KEY)
        assert not verify_token(signed, _KEY)

    def test_future_token_valid(self):
        token = _make_token(days_until_expiry=1)
        signed = sign_token(token, _KEY)
        assert verify_token(signed, _KEY)

    def test_unsigned_token_rejected(self):
        token = _make_token()
        # No signature — verify should fail immediately
        assert not verify_token(token, _KEY)

    def test_tampering_detected(self):
        signed = sign_token(_make_token(), _KEY)
        tampered = LicenseToken(
            licensee_id="EVIL_BANK",
            issue_date=signed.issue_date,
            expiry_date=signed.expiry_date,
            max_tps=signed.max_tps,
            aml_dollar_cap_usd=signed.aml_dollar_cap_usd,
            aml_count_cap=signed.aml_count_cap,
            permitted_components=signed.permitted_components,
            hmac_signature=signed.hmac_signature,  # reuse original sig
        )
        assert not verify_token(tampered, _KEY)

    def test_canonical_payload_is_deterministic(self):
        token = _make_token()
        assert token.canonical_payload() == token.canonical_payload()

    def test_components_sorted_in_payload(self):
        t1 = _make_token(components=["C7", "C1", "C3"])
        t2 = _make_token(components=["C1", "C3", "C7"])
        assert t1.canonical_payload() == t2.canonical_payload()

    def test_is_expired_true_past(self):
        token = _make_token(days_until_expiry=-1)
        assert token.is_expired()

    def test_is_expired_false_future(self):
        token = _make_token(days_until_expiry=30)
        assert not token.is_expired()

    def test_round_trip_dict(self):
        signed = sign_token(_make_token(), _KEY)
        restored = LicenseToken.from_dict(signed.to_dict())
        assert restored.licensee_id == signed.licensee_id
        assert restored.hmac_signature == signed.hmac_signature
        assert restored.aml_dollar_cap_usd == signed.aml_dollar_cap_usd
        assert restored.aml_count_cap == signed.aml_count_cap
        assert verify_token(restored, _KEY)

    def test_max_tps_preserved_after_sign(self):
        token = _make_token(max_tps=1000)
        signed = sign_token(token, _KEY)
        assert signed.max_tps == 1000

    def test_aml_caps_preserved_after_sign(self):
        token = _make_token(aml_dollar_cap=50000, aml_count_cap=5)
        signed = sign_token(token, _KEY)
        assert signed.aml_dollar_cap_usd == 50000
        assert signed.aml_count_cap == 5


# ── LicenseeContext tests ─────────────────────────────────────────────────────

class TestLicenseeContext:

    def test_fields(self):
        ctx = LicenseeContext(
            licensee_id="BANK_X",
            max_tps=200,
            aml_dollar_cap_usd=50000,
            aml_count_cap=5,
            permitted_components=["C1", "C7"],
            token_expiry="2027-01-01",
        )
        assert ctx.licensee_id == "BANK_X"
        assert ctx.max_tps == 200
        assert ctx.aml_dollar_cap_usd == 50000
        assert ctx.aml_count_cap == 5
        assert "C7" in ctx.permitted_components


# ── LicenseBootValidator tests ────────────────────────────────────────────────

class TestLicenseBootValidator:

    def _ks(self):
        """Return a mock KillSwitch that records activate() calls."""
        ks = MagicMock()
        ks.is_active.return_value = False
        return ks

    def _env_for(self, token: LicenseToken, key: bytes) -> dict:
        return {
            "LIP_LICENSE_TOKEN_JSON": json.dumps(token.to_dict()),
            "LIP_LICENSE_KEY_HEX": key.hex(),
        }

    def test_valid_token_returns_context(self, monkeypatch):
        signed = sign_token(_make_token(), _KEY)
        ks = self._ks()
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(signed.to_dict()))
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())

        validator = LicenseBootValidator(kill_switch=ks, required_component="C7")
        ctx = validator.validate()

        assert ctx is not None
        assert ctx.licensee_id == "TEST_BANK_001"
        ks.activate.assert_not_called()

    def test_missing_token_env_engages_kill_switch(self, monkeypatch):
        monkeypatch.delenv("LIP_LICENSE_TOKEN_JSON", raising=False)
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks)
        result = validator.validate()

        assert result is None
        ks.activate.assert_called_once()

    def test_missing_key_env_engages_kill_switch(self, monkeypatch):
        signed = sign_token(_make_token(), _KEY)
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(signed.to_dict()))
        monkeypatch.delenv("LIP_LICENSE_KEY_HEX", raising=False)
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks)
        result = validator.validate()

        assert result is None
        ks.activate.assert_called_once()

    def test_expired_token_engages_kill_switch(self, monkeypatch):
        expired = sign_token(_make_token(days_until_expiry=-1), _KEY)
        ks = self._ks()
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(expired.to_dict()))
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())

        validator = LicenseBootValidator(kill_switch=ks)
        result = validator.validate()

        assert result is None
        ks.activate.assert_called_once()

    def test_invalid_signature_engages_kill_switch(self, monkeypatch):
        signed = sign_token(_make_token(), _KEY)
        wrong_key = b"wrong-key-for-verification!!!__"
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(signed.to_dict()))
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", wrong_key.hex())
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks)
        result = validator.validate()

        assert result is None
        ks.activate.assert_called_once()

    def test_component_not_licensed_raises(self, monkeypatch):
        partial = sign_token(_make_token(components=["C1", "C2"]), _KEY)
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(partial.to_dict()))
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks, required_component="C7")
        with pytest.raises(RuntimeError, match="C7"):
            validator.validate()
        ks.activate.assert_called_once()

    def test_malformed_json_engages_kill_switch(self, monkeypatch):
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", "NOT_JSON{{{}}")
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks)
        result = validator.validate()

        assert result is None
        ks.activate.assert_called_once()

    def test_context_cached_after_validate(self, monkeypatch):
        signed = sign_token(_make_token(), _KEY)
        monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", json.dumps(signed.to_dict()))
        monkeypatch.setenv("LIP_LICENSE_KEY_HEX", _KEY.hex())
        ks = self._ks()

        validator = LicenseBootValidator(kill_switch=ks)
        ctx = validator.validate()
        assert validator.context is ctx
