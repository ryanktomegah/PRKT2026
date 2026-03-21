"""
auth.py — HMAC-SHA256 API authentication for LIP endpoints.
GAP-07/GAP-15 hardening: Portfolio and admin endpoints must be authenticated.

Header format:
  Authorization: HMAC-SHA256 <timestamp>:<hex_digest>

Where digest = HMAC-SHA256(key, "timestamp|method|path|body")
Timestamp must be within 5 minutes of server time (replay prevention).
Health endpoints are exempt.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from lip.common.encryption import sign_hmac_sha256, verify_hmac_sha256

logger = logging.getLogger(__name__)

# 5-minute replay window
_REPLAY_WINDOW_SECONDS = 300


def verify_request(
    authorization: str,
    method: str,
    path: str,
    body: bytes,
    hmac_key: bytes,
) -> bool:
    """Verify an HMAC-SHA256 signed API request.

    Parameters
    ----------
    authorization:
        Full Authorization header value.
    method:
        HTTP method (GET, POST, etc.).
    path:
        Request path (e.g., /admin/platform/summary).
    body:
        Raw request body bytes (empty bytes for GET).
    hmac_key:
        HMAC signing key.

    Returns
    -------
    bool
        True if the signature is valid and within the replay window.
    """
    if not authorization.startswith("HMAC-SHA256 "):
        return False

    token = authorization[len("HMAC-SHA256 "):]
    parts = token.split(":", 1)
    if len(parts) != 2:
        return False

    timestamp_str, hex_digest = parts

    try:
        request_ts = int(timestamp_str)
    except ValueError:
        return False

    now = int(time.time())
    if abs(now - request_ts) > _REPLAY_WINDOW_SECONDS:
        logger.warning("HMAC replay window exceeded: request_ts=%d now=%d", request_ts, now)
        return False

    message = f"{timestamp_str}|{method.upper()}|{path}|".encode() + body
    return verify_hmac_sha256(message, hex_digest, hmac_key)


def sign_request(
    method: str,
    path: str,
    body: bytes,
    hmac_key: bytes,
    timestamp: Optional[int] = None,
) -> str:
    """Generate an Authorization header for an API request.

    Utility for clients and tests.

    Returns
    -------
    str
        Complete Authorization header value.
    """
    ts = timestamp or int(time.time())
    message = f"{ts}|{method.upper()}|{path}|".encode() + body
    digest = sign_hmac_sha256(message, hmac_key)
    return f"HMAC-SHA256 {ts}:{digest}"


try:
    from fastapi import HTTPException, Request

    def make_hmac_dependency(hmac_key: bytes):
        """Create a FastAPI dependency that enforces HMAC-SHA256 auth.

        Usage::

            hmac_dep = make_hmac_dependency(key)
            router = APIRouter(dependencies=[Depends(hmac_dep)])

        Args:
            hmac_key: HMAC signing key bytes.

        Returns:
            An async callable suitable for ``Depends()``.
        """

        async def _verify_hmac(request: Request) -> None:
            auth_header = request.headers.get("authorization", "")
            if not auth_header:
                raise HTTPException(status_code=401, detail="Missing Authorization header")

            body = await request.body()
            if not verify_request(auth_header, request.method, request.url.path, body, hmac_key):
                raise HTTPException(status_code=401, detail="Invalid HMAC signature")

        return _verify_hmac

except ImportError:
    pass  # FastAPI not required for core pipeline operation
