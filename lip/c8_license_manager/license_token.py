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

import dataclasses
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import ClassVar, List, Optional

from lip.common.constants import MIN_LOAN_AMOUNT_USD

logger = logging.getLogger(__name__)

# Component IDs recognised by the token validator
ALL_COMPONENTS: List[str] = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]

# EPG-16/17: sentinel marking an AML dollar cap that was never explicitly configured.
# Any token that omits aml_dollar_cap_usd from its JSON receives this value.
# LicenseBootValidator rejects tokens with this sentinel (kill switch engaged).
_AML_CAP_UNSET: int = -1

# Valid deployment phase values — must match DeploymentPhase enum in deployment_phase.py.
# Duplicated here as strings to avoid a circular import on the token module.
_VALID_PHASES: frozenset = frozenset({"LICENSOR", "HYBRID", "FULL_MLO"})
_VALID_LICENSEE_TYPES: frozenset = frozenset({"BANK", "PROCESSOR"})


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

    schema_version: int = 1  # B3-02/B3-05: bump on every field add
    licensee_id: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    max_tps: int = 0
    # B3-03: Default to sentinel (-1) instead of 0 (unlimited). Programmatic
    # construction must set caps explicitly; from_dict() sets them from JSON.
    # 0 = unlimited (valid, explicit); -1 = unset (rejected by boot validator).
    aml_dollar_cap_usd: int = _AML_CAP_UNSET  # EPG-16: must be set explicitly
    aml_count_cap: int = _AML_CAP_UNSET       # EPG-16: must be set explicitly
    min_loan_amount_usd: int = int(MIN_LOAN_AMOUNT_USD)
    deployment_phase: str = "LICENSOR"  # Phase 1=LICENSOR, Phase 2=HYBRID, Phase 3=FULL_MLO
    licensee_type: str = "BANK"  # "BANK" (direct) or "PROCESSOR" (platform licensing)
    sub_licensee_bics: List[str] = field(default_factory=list)  # Processor: authorised bank BICs
    annual_minimum_usd: int = 0  # Annual minimum commitment ($0 = none)
    performance_premium_pct: float = 0.0  # % of above-baseline revenue
    platform_take_rate_pct: float = 0.0  # Processor's take rate
    permitted_components: List[str] = field(default_factory=lambda: list(ALL_COMPONENTS))
    hmac_signature: str = ""

    # ── helpers ──────────────────────────────────────────────────────────────

    # B3-02: fields excluded from the canonical payload (not signed).
    _CANONICAL_EXCLUDE: ClassVar[frozenset] = frozenset({"hmac_signature"})

    def canonical_payload(self) -> bytes:
        """Return the UTF-8 bytes that are signed/verified.

        B3-02: derived from ``dataclasses.fields(self)`` so that adding a new
        field to the dataclass automatically includes it in the HMAC.  No
        hand-maintained field list — adding a field and forgetting to update
        this method is no longer possible.

        List-valued fields are sorted for deterministic serialization.
        """
        payload = {}
        for f in dataclasses.fields(self):
            if f.name in self._CANONICAL_EXCLUDE:
                continue
            value = getattr(self, f.name)
            if isinstance(value, list):
                value = sorted(value)
            payload[f.name] = value
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def is_expired(self, as_of: Optional[date] = None) -> bool:
        """Return ``True`` if the token's expiry date has passed."""
        check_date = as_of or datetime.now(tz=timezone.utc).date()
        expiry = date.fromisoformat(self.expiry_date)
        return check_date > expiry

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LicenseToken":
        phase = data.get("deployment_phase", "LICENSOR")
        if phase not in _VALID_PHASES:
            raise ValueError(
                f"Unknown deployment_phase {phase!r} — valid values: {sorted(_VALID_PHASES)}"
            )
        licensee_type = data.get("licensee_type", "BANK")
        if licensee_type not in _VALID_LICENSEE_TYPES:
            raise ValueError(
                f"Unknown licensee_type {licensee_type!r} — valid values: {sorted(_VALID_LICENSEE_TYPES)}"
            )
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            licensee_id=data["licensee_id"],
            issue_date=data["issue_date"],
            expiry_date=data["expiry_date"],
            max_tps=int(data["max_tps"]),
            aml_dollar_cap_usd=int(data["aml_dollar_cap_usd"]),   # EPG-17: required field — no silent default
            aml_count_cap=int(data["aml_count_cap"]),              # EPG-17: required field — no silent default
            min_loan_amount_usd=int(data.get("min_loan_amount_usd", MIN_LOAN_AMOUNT_USD)),
            deployment_phase=phase,
            licensee_type=licensee_type,
            sub_licensee_bics=list(data.get("sub_licensee_bics", [])),
            annual_minimum_usd=int(data.get("annual_minimum_usd", 0)),
            performance_premium_pct=float(data.get("performance_premium_pct", 0.0)),
            platform_take_rate_pct=float(data.get("platform_take_rate_pct", 0.0)),
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
    min_loan_amount_usd: int = int(MIN_LOAN_AMOUNT_USD)
    deployment_phase: str = "LICENSOR"


@dataclass
class ProcessorLicenseeContext(LicenseeContext):
    """Runtime context for a processor licensee (P3 Platform Licensing).

    Extends LicenseeContext with processor-specific fields for
    sub-licensee BIC validation and revenue metering configuration.
    """

    licensee_type: str = "PROCESSOR"
    sub_licensee_bics: List[str] = field(default_factory=list)
    annual_minimum_usd: int = 0
    performance_premium_pct: float = 0.0
    platform_take_rate_pct: float = 0.0


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
    # B3-02: use dataclasses.replace instead of field-by-field copy so new
    # fields are automatically carried through without a hand-maintained list.
    return dataclasses.replace(token, hmac_signature=sig)


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
        logger.debug(
            "License token has no signature — rejecting (licensee=%s)",
            token.licensee_id[:8] + "…" if len(token.licensee_id) > 8 else token.licensee_id,
        )
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
