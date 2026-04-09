"""
_test_env.py — Import-time test environment setup.

Importing this module has the side effect of setting environment variables
required by the LIP production code paths that the test suite exercises.
Intended to be imported before any ``lip.*`` module in ``conftest.py`` so
that the env is in place by the time test collection starts.

Current side effects:
  * ``LIP_MODEL_HMAC_KEY`` — set to a deterministic 32-byte test key so
    ``lip.common.secure_pickle.load()`` (B10-01 / B10-02) can verify
    sidecars produced by test-time ``secure_pickle.dump()`` calls. The
    key is not a secret and has no production value; it exists solely
    to allow the fail-closed HMAC check to succeed under pytest.

Never hardcode a production key here. Rotate ``LIP_MODEL_HMAC_KEY`` via
``monkeypatch.setenv`` inside individual tests if you need to test
key-related behaviour.
"""
from __future__ import annotations

import os

_TEST_MODEL_HMAC_KEY = "lip_test_model_hmac_key__32b____"
assert len(_TEST_MODEL_HMAC_KEY.encode("utf-8")) >= 32, (
    "LIP test HMAC key must be at least 32 bytes"
)
os.environ.setdefault("LIP_MODEL_HMAC_KEY", _TEST_MODEL_HMAC_KEY)
