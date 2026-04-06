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
import re
from decimal import Decimal
from typing import Optional

from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.constants import PROCESSOR_TAKE_RATE_MAX_PCT, PROCESSOR_TAKE_RATE_MIN_PCT

from .license_token import (
    _AML_CAP_UNSET,
    LicenseeContext,
    LicenseToken,
    ProcessorLicenseeContext,
    verify_token,
)

logger = logging.getLogger(__name__)

_TOKEN_ENV = "LIP_LICENSE_TOKEN_JSON"
_KEY_ENV = "LIP_LICENSE_KEY_HEX"

_BIC_PATTERN = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")


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

    def __init__(self, kill_switch: KillSwitch, required_component: str = "C7") -> None:
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

        # EPG-16/17: reject tokens that never had aml_dollar_cap_usd explicitly set.
        # A missing cap silently defaults to $1M, which is inoperable for
        # correspondent banking and violates deployment-time enforcement requirements.
        if token.aml_dollar_cap_usd == _AML_CAP_UNSET:
            logger.critical(
                "License token is missing aml_dollar_cap_usd for licensee=%s — "
                "cap must be explicitly set in the BPI provisioning token",
                token.licensee_id,
            )
            self._engage("aml_cap_not_configured")
            return None

        # Processor-specific validation (P3 Platform Licensing)
        if token.licensee_type == "PROCESSOR":
            if not token.sub_licensee_bics:
                logger.critical(
                    "Processor token has no sub_licensee_bics for licensee=%s",
                    token.licensee_id,
                )
                self._engage("processor_no_sub_licensees")
                return None

            for bic in token.sub_licensee_bics:
                if not _BIC_PATTERN.match(bic):
                    logger.critical(
                        "Invalid BIC format %r in sub_licensee_bics for licensee=%s",
                        bic,
                        token.licensee_id,
                    )
                    self._engage("processor_invalid_bic")
                    return None

            take_rate = Decimal(str(token.platform_take_rate_pct))
            if not (PROCESSOR_TAKE_RATE_MIN_PCT <= take_rate <= PROCESSOR_TAKE_RATE_MAX_PCT):
                logger.critical(
                    "Processor take rate %.2f%% outside bounds [%.0f%%, %.0f%%] for licensee=%s",
                    token.platform_take_rate_pct * 100,
                    float(PROCESSOR_TAKE_RATE_MIN_PCT) * 100,
                    float(PROCESSOR_TAKE_RATE_MAX_PCT) * 100,
                    token.licensee_id,
                )
                self._engage("processor_take_rate_out_of_bounds")
                return None

        if self._required_component not in token.permitted_components:
            msg = (
                f"License does not permit component {self._required_component} "
                f"for licensee={token.licensee_id}"
            )
            logger.critical(msg)
            self._engage("component_not_licensed")
            raise RuntimeError(msg)

        ctx: LicenseeContext
        if token.licensee_type == "PROCESSOR":
            ctx = ProcessorLicenseeContext(
                licensee_id=token.licensee_id,
                max_tps=token.max_tps,
                aml_dollar_cap_usd=token.aml_dollar_cap_usd,
                aml_count_cap=token.aml_count_cap,
                min_loan_amount_usd=token.min_loan_amount_usd,
                deployment_phase=token.deployment_phase,
                permitted_components=token.permitted_components,
                token_expiry=token.expiry_date,
                licensee_type=token.licensee_type,
                sub_licensee_bics=list(token.sub_licensee_bics),
                annual_minimum_usd=token.annual_minimum_usd,
                performance_premium_pct=token.performance_premium_pct,
                platform_take_rate_pct=token.platform_take_rate_pct,
            )
        else:
            ctx = LicenseeContext(
                licensee_id=token.licensee_id,
                max_tps=token.max_tps,
                aml_dollar_cap_usd=token.aml_dollar_cap_usd,
                aml_count_cap=token.aml_count_cap,
                min_loan_amount_usd=token.min_loan_amount_usd,
                deployment_phase=token.deployment_phase,
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
