"""
test_secure_pickle.py — Unit tests for the secure-pickle wrapper (B10-01/02).

Verifies that lip.common.secure_pickle:
  1. Round-trips arbitrary objects when the sidecar is intact.
  2. Refuses to load when the sidecar is missing.
  3. Refuses to load when the payload is tampered.
  4. Refuses to load when the sidecar is tampered.
  5. Refuses to load when the HMAC key is wrong.
  6. Refuses to load when no key is available (env var unset, no override).
  7. Refuses to load when the key is shorter than 32 bytes.
  8. Never falls through to raw pickle.load on any failure.

These are the load-bearing integrity guarantees that B10-01 and B10-02
depend on. If any of these flip to "best effort", the RCE is back.
"""
from __future__ import annotations

import pytest

from lip.common.secure_pickle import (
    SecurePickleError,
    dump,
    load,
)

_GOOD_KEY = b"unit_test_key___fully_32_bytes__"
_OTHER_KEY = b"unit_test_key___OTHER_32_bytes__"


def test_roundtrip_with_explicit_key(tmp_path):
    obj = {"weights": [1.0, 2.0, 3.0], "label": "c1-lgbm"}
    path = tmp_path / "model.pkl"

    dump(obj, path, hmac_key=_GOOD_KEY)
    assert path.exists()
    assert path.with_name(path.name + ".sig").exists()

    loaded = load(path, hmac_key=_GOOD_KEY)
    assert loaded == obj


def test_missing_sidecar_refused(tmp_path):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)
    sig = path.with_name(path.name + ".sig")
    sig.unlink()

    with pytest.raises(SecurePickleError, match="sidecar missing"):
        load(path, hmac_key=_GOOD_KEY)


def test_tampered_payload_refused(tmp_path):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)

    # Flip a byte in the payload.
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(bytes(raw))

    with pytest.raises(SecurePickleError, match="HMAC verification failed"):
        load(path, hmac_key=_GOOD_KEY)


def test_tampered_sidecar_refused(tmp_path):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)
    sig = path.with_name(path.name + ".sig")
    # Replace with a valid-looking but incorrect hex digest.
    sig.write_text("0" * 64, encoding="utf-8")

    with pytest.raises(SecurePickleError, match="HMAC verification failed"):
        load(path, hmac_key=_GOOD_KEY)


def test_wrong_key_refused(tmp_path):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)

    with pytest.raises(SecurePickleError, match="HMAC verification failed"):
        load(path, hmac_key=_OTHER_KEY)


def test_no_key_refused(tmp_path, monkeypatch):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)

    monkeypatch.delenv("LIP_MODEL_HMAC_KEY", raising=False)
    with pytest.raises(SecurePickleError, match="HMAC key not available"):
        load(path)  # no explicit key, env unset


def test_short_key_refused(tmp_path):
    path = tmp_path / "model.pkl"
    # Attempting to write with a short key must also fail — dump is fail-closed.
    with pytest.raises(SecurePickleError, match="too short"):
        dump({"a": 1}, path, hmac_key=b"too_short")


def test_missing_payload_refused(tmp_path):
    path = tmp_path / "does_not_exist.pkl"
    with pytest.raises(SecurePickleError, match="not found"):
        load(path, hmac_key=_GOOD_KEY)


def test_empty_sidecar_refused(tmp_path):
    path = tmp_path / "model.pkl"
    dump({"a": 1}, path, hmac_key=_GOOD_KEY)
    sig = path.with_name(path.name + ".sig")
    sig.write_text("", encoding="utf-8")

    with pytest.raises(SecurePickleError, match="Empty signature sidecar"):
        load(path, hmac_key=_GOOD_KEY)


def test_env_var_key_path_works(tmp_path, monkeypatch):
    """Verify the production code path: key comes from the env var."""
    key_str = "env_var_test_key___fully_32_byte"
    assert len(key_str.encode("utf-8")) == 32
    monkeypatch.setenv("LIP_MODEL_HMAC_KEY", key_str)

    path = tmp_path / "model.pkl"
    dump({"a": 1}, path)  # no explicit key
    loaded = load(path)  # no explicit key
    assert loaded == {"a": 1}
