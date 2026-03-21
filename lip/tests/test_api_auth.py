"""Tests for API authentication (HMAC-SHA256)."""
from __future__ import annotations

import time

from lip.api.auth import sign_request, verify_request

_KEY = b"test_hmac_key___32bytes_________!"


class TestHMACAuth:
    def test_sign_and_verify_roundtrip(self):
        auth = sign_request("GET", "/admin/platform/summary", b"", _KEY)
        assert verify_request(auth, "GET", "/admin/platform/summary", b"", _KEY)

    def test_sign_and_verify_with_body(self):
        body = b'{"bic": "JPMORGAN", "tier": 1}'
        auth = sign_request("POST", "/known-entities", body, _KEY)
        assert verify_request(auth, "POST", "/known-entities", body, _KEY)

    def test_wrong_key_fails(self):
        auth = sign_request("GET", "/test", b"", _KEY)
        wrong_key = b"wrong_key_______32bytes_________"
        assert not verify_request(auth, "GET", "/test", b"", wrong_key)

    def test_wrong_path_fails(self):
        auth = sign_request("GET", "/admin/summary", b"", _KEY)
        assert not verify_request(auth, "GET", "/admin/other", b"", _KEY)

    def test_wrong_method_fails(self):
        auth = sign_request("GET", "/test", b"", _KEY)
        assert not verify_request(auth, "POST", "/test", b"", _KEY)

    def test_tampered_body_fails(self):
        body = b'{"ok": true}'
        auth = sign_request("POST", "/test", body, _KEY)
        assert not verify_request(auth, "POST", "/test", b'{"ok": false}', _KEY)

    def test_expired_timestamp_fails(self):
        old_ts = int(time.time()) - 400  # > 5 min
        auth = sign_request("GET", "/test", b"", _KEY, timestamp=old_ts)
        assert not verify_request(auth, "GET", "/test", b"", _KEY)

    def test_future_timestamp_within_window(self):
        future_ts = int(time.time()) + 200  # < 5 min
        auth = sign_request("GET", "/test", b"", _KEY, timestamp=future_ts)
        assert verify_request(auth, "GET", "/test", b"", _KEY)

    def test_invalid_header_format(self):
        assert not verify_request("Bearer token", "GET", "/test", b"", _KEY)
        assert not verify_request("HMAC-SHA256 badformat", "GET", "/test", b"", _KEY)
        assert not verify_request("", "GET", "/test", b"", _KEY)

    def test_non_numeric_timestamp(self):
        assert not verify_request("HMAC-SHA256 abc:deadbeef", "GET", "/test", b"", _KEY)


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lip.api.auth import make_hmac_dependency

    class TestHMACDependency:
        def _make_app(self):
            from fastapi import Depends
            app = FastAPI()
            dep = make_hmac_dependency(_KEY)

            @app.get("/protected", dependencies=[Depends(dep)])
            def protected():
                return {"ok": True}

            return TestClient(app)

        def test_valid_auth(self):
            client = self._make_app()
            auth = sign_request("GET", "/protected", b"", _KEY)
            resp = client.get("/protected", headers={"Authorization": auth})
            assert resp.status_code == 200

        def test_missing_auth(self):
            client = self._make_app()
            resp = client.get("/protected")
            assert resp.status_code == 401

        def test_invalid_auth(self):
            client = self._make_app()
            resp = client.get("/protected", headers={"Authorization": "HMAC-SHA256 0:bad"})
            assert resp.status_code == 401

except ImportError:
    pass
