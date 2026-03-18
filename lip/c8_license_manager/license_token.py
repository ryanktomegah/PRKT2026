"""
license_token.py — BPI license token: issuance and offline verification.
C8 Spec Section 1.

Token structure (canonical JSON, sorted keys, UTF-8):
  licensee_id        — unique licensee identifier assigned by BPI
  issue_date         — ISO-8601 date of issuance (YYYY-MM-DD)
  expiry_date        — ISO-8601 date of expiry   (YYYY-MM-DD)
  max_tps            — maximum transactions per second licensed
  permitted_components — list of component IDs licensed (e.g. ["C1","C2",...])
  hmac_signature     — hex HMAC-SHA256 of canonical payload (all other fields)

Signing key:
  BPI holds the HMAC secret; licensees receive signed tokens but NEVER the key.
  Key rotation: aligned with SALT_ROTATION_DAYS (365-day cycle).
  Key distribution: out-of-band (secure BPI→licensee channel at contract time).

HMAC vs. asymmetric signing:
  HMAC-SHA256 is used for simplicity and speed.  Upgrade path to RSA-PSS or
  ECDSA (P-256) is straightforward if public verifiability is required for
  sub-licensee audits.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# Component IDs recognised by the token validator
ALL_COMPONENTS: List[str] = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]


@dataclass
class LicenseToken:
    """Signed BPI license token.

    Attributes
    ----------
    licensee_id:
        Unique identifier assigned by BPI to the licensee bank
        (e.g. ``"HSBC_UK_001"``).
    issue_date:
        Date the token was signed by BPI (ISO format ``YYYY-MM-DD``).
    expiry_date:
        Date after which the token is invalid (ISO format ``YYYY-MM-DD``).
    max_tps:
        Maximum transactions per second this license permits.  C7 enforces
        this cap; sustained excess triggers a degraded-mode alert.
    permitted_components:
        Subset of ``ALL_COMPONENTS`` the licensee is licensed to operate.
        Typically the full set for a full-platform license.
    hmac_signature:
        Hex-encoded HMAC-SHA256 over the canonical payload (all other fields
        serialised as JSON with sorted keys, UTF-8 encoded).  Empty string
        on an unsigned (draft) token.
    """

    licensee_id: str
    issue_date: str
    expiry_date: str
    max_tps: int
    aml_dollar_cap_usd: int = 1000000
    aml_count_cap: int = 100
    min_loan_amount_usd: int = 500000
    permitted_components: List[str] = field(default_factory=lambda: list(ALL_COMPONENTS))
    hmac_signature: str = ""

    # ── helpers ──────────────────────────────────────────────────────────────

    def canonical_payload(self) -> bytes:
        """Return the UTF-8 bytes that are signed/verified.

        All fields except ``hmac_signature`` serialised as JSON (sorted keys).
        """
        payload = {
            "licensee_id": self.licensee_id,
            "issue_date": self.issue_date,
            "expiry_date": self.expiry_date,
            "max_tps": self.max_tps,
            "aml_dollar_cap_usd": self.aml_dollar_cap_usd,
            "aml_count_cap": self.aml_count_cap,
            "min_loan_amount_usd": self.min_loan_amount_usd,
            "permitted_components": sorted(self.permitted_components),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def is_expired(self, as_of: Optional[date] = None) -> bool:
        """Return ``True`` if the token's expiry date has passed."""
        check_date = as_of or datetime.now(tz=timezone.utc).date()
        expiry = date.fromisoformat(self.expiry_date)
        return check_date > expiry

    def to_dict(self) -> dict:
        return {
            "licensee_id": self.licensee_id,
            "issue_date": self.issue_date,
            "expiry_date": self.expiry_date,
            "max_tps": self.max_tps,
            "aml_dollar_cap_usd": self.aml_dollar_cap_usd,
            "aml_count_cap": self.aml_count_cap,
            "min_loan_amount_usd": self.min_loan_amount_usd,
            "permitted_components": self.permitted_components,
            "hmac_signature": self.hmac_signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LicenseToken":
        return cls(
            licensee_id=data["licensee_id"],
            issue_date=data["issue_date"],
            expiry_date=data["expiry_date"],
            max_tps=int(data["max_tps"]),
            aml_dollar_cap_usd=int(data.get("aml_dollar_cap_usd", 1000000)),
            aml_count_cap=int(data.get("aml_count_cap", 100)),
            min_loan_amount_usd=int(data.get("min_loan_amount_usd", 500000)),
            permitted_components=list(data.get("permitted_components", ALL_COMPONENTS)),
            hmac_signature=data.get("hmac_signature", ""),
        )


@dataclass
class LicenseeContext:
    """Runtime context derived from a validated LicenseToken.

    Passed to C6 (salt namespace), C7 (TPS cap), and audit logging.

    Attributes
    ----------
    licensee_id:
        Same as ``LicenseToken.licensee_id``.
    max_tps:
        TPS ceiling enforced by C7.
    aml_dollar_cap_usd:
        24h aggregate bridge loan volume permitted per BIC.
    aml_count_cap:
        24h aggregate bridge loan count permitted per BIC.
    permitted_components:
        Components this instance is authorised to run.
    token_expiry:
        Expiry date for monitoring / alerting.
    """

    licensee_id: str
    max_tps: int
    aml_dollar_cap_usd: int
    aml_count_cap: int
    permitted_components: List[str]
    token_expiry: str
    min_loan_amount_usd: int = 500000


# ── Token signing and verification ───────────────────────────────────────────


def _compute_hmac(payload: bytes, key: bytes) -> str:
    """Return hex HMAC-SHA256 of *payload* under *key*."""
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def sign_token(token: LicenseToken, signing_key: bytes) -> LicenseToken:
    """Sign *token* with BPI's *signing_key* and return a new signed token.

    Only BPI should call this function — the signing key is BPI's secret.
    The returned token has ``hmac_signature`` populated.

    Parameters
    ----------
    token:
        Unsigned ``LicenseToken`` (``hmac_signature`` ignored / overwritten).
    signing_key:
        BPI HMAC secret (raw bytes, minimum 32 bytes recommended).

    Returns
    -------
    LicenseToken
        A new ``LicenseToken`` with ``hmac_signature`` set.
    """
    sig = _compute_hmac(token.canonical_payload(), signing_key)
    return LicenseToken(
        licensee_id=token.licensee_id,
        issue_date=token.issue_date,
        expiry_date=token.expiry_date,
        max_tps=token.max_tps,
        aml_dollar_cap_usd=token.aml_dollar_cap_usd,
        aml_count_cap=token.aml_count_cap,
        min_loan_amount_usd=token.min_loan_amount_usd,
        permitted_components=list(token.permitted_components),
        hmac_signature=sig,
    )


def verify_token(
    token: LicenseToken,
    signing_key: bytes,
    as_of: Optional[date] = None,
) -> bool:
    """Verify that *token* is authentic and not expired.

    Parameters
    ----------
    token:
        ``LicenseToken`` to verify (must have ``hmac_signature`` set).
    signing_key:
        BPI HMAC secret (same key used for signing).
    as_of:
        Date to use for expiry check.  Defaults to today (UTC).

    Returns
    -------
    bool
        ``True`` iff the HMAC is valid AND the token is not expired.
    """
    if not token.hmac_signature:
        logger.warning("License token has no signature — rejecting")
        return False

    expected = _compute_hmac(token.canonical_payload(), signing_key)
    sig_valid = hmac.compare_digest(token.hmac_signature, expected)

    if not sig_valid:
        logger.error("License token HMAC mismatch for licensee=%s", token.licensee_id)
        return False

    if token.is_expired(as_of=as_of):
        logger.error(
            "License token expired: licensee=%s expiry=%s",
            token.licensee_id,
            token.expiry_date,
        )
        return False

    return True
