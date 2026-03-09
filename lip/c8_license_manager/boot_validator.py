"""
boot_validator.py — License validation at C7 container boot.
C8 Spec Section 2.

LicenseBootValidator is called once at startup (before any loan offers).
If validation fails, it engages the C7 KillSwitch so no offers are issued.

Environment variables read:
  LIP_LICENSE_TOKEN_JSON  — JSON string of the signed LicenseToken
  LIP_LICENSE_KEY_HEX     — hex-encoded BPI signing key (32+ bytes)
                             (In production, injected via secrets manager / KMS.)

Failure modes:
  - Token env var missing    → KillSwitch engaged, reason="license_missing"
  - Token JSON parse error   → KillSwitch engaged, reason="license_parse_error"
  - HMAC invalid             → KillSwitch engaged, reason="license_invalid"
  - Token expired            → KillSwitch engaged, reason="license_expired"
  - Component not licensed   → raises RuntimeError (hard fail at boot)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from .license_token import LicenseeContext, LicenseToken, verify_token

logger = logging.getLogger(__name__)

_TOKEN_ENV = "LIP_LICENSE_TOKEN_JSON"
_KEY_ENV = "LIP_LICENSE_KEY_HEX"


class LicenseBootValidator:
    """Validates the BPI license token at container boot.

    Parameters
    ----------
    kill_switch:
        C7 ``KillSwitch`` instance.  ``engage()`` is called on any
        validation failure so no loan offers are issued.
    required_component:
        The component ID this instance runs (e.g. ``"C7"``).  Validation
        fails hard if the token does not permit this component.
    """

    def __init__(self, kill_switch: object, required_component: str = "C7") -> None:
        self._ks = kill_switch
        self._required_component = required_component
        self._context: Optional[LicenseeContext] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def validate(self) -> Optional[LicenseeContext]:
        """Run license validation.  Returns ``LicenseeContext`` on success.

        On any failure the C7 KillSwitch is engaged and ``None`` is returned.
        Callers must check the return value before proceeding.

        Returns
        -------
        LicenseeContext or None
        """
        token, key = self._load_token_and_key()
        if token is None or key is None:
            return None

        if not verify_token(token, key):
            self._engage("license_invalid_or_expired")
            return None

        if self._required_component not in token.permitted_components:
            msg = (
                f"License does not permit component {self._required_component} "
                f"for licensee={token.licensee_id}"
            )
            logger.critical(msg)
            self._engage("component_not_licensed")
            raise RuntimeError(msg)

        ctx = LicenseeContext(
            licensee_id=token.licensee_id,
            max_tps=token.max_tps,
            permitted_components=token.permitted_components,
            token_expiry=token.expiry_date,
        )
        self._context = ctx
        logger.info(
            "License validated: licensee=%s expiry=%s max_tps=%d",
            ctx.licensee_id,
            ctx.token_expiry,
            ctx.max_tps,
        )
        return ctx

    @property
    def context(self) -> Optional[LicenseeContext]:
        """Return the validated ``LicenseeContext``, or ``None`` if not validated."""
        return self._context

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_token_and_key(self):
        token_json = os.environ.get(_TOKEN_ENV)
        key_hex = os.environ.get(_KEY_ENV)

        if not token_json:
            logger.critical("License token not found (env var %s missing)", _TOKEN_ENV)
            self._engage("license_missing")
            return None, None

        if not key_hex:
            logger.critical("License signing key not found (env var %s missing)", _KEY_ENV)
            self._engage("license_missing")
            return None, None

        try:
            data = json.loads(token_json)
            token = LicenseToken.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.critical("License token parse error: %s", exc)
            self._engage("license_parse_error")
            return None, None

        try:
            key = bytes.fromhex(key_hex)
        except ValueError as exc:
            logger.critical("License key hex decode error: %s", exc)
            self._engage("license_parse_error")
            return None, None

        return token, key

    def _engage(self, reason: str) -> None:
        logger.critical("Engaging kill switch: reason=%s", reason)
        self._ks.activate(reason=reason)
