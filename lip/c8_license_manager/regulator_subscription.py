"""
regulator_subscription.py — Regulator subscription token for P10 API access.

Sprint 6 (P10/C8 extension): add regulator-specific licensing token and
offline HMAC verification, mirroring the existing LicenseToken pattern.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

REGULATOR_SUBSCRIPTION_TIERS: tuple[str, ...] = (
    "STANDARD",
    "QUERY",
    "STRESS_TEST",
    "REALTIME",
)


def _to_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _compute_hmac(payload: bytes, key: bytes) -> str:
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class RegulatorSubscriptionToken:
    """License token for regulatory API consumers."""

    regulator_id: str
    regulator_name: str
    subscription_tier: str
    permitted_corridors: Optional[tuple[str, ...]]
    query_budget_monthly: int
    privacy_budget_allocation: float
    valid_from: datetime
    valid_until: datetime
    hmac_signature: str = ""

    def canonical_payload(self) -> bytes:
        payload = {
            "regulator_id": self.regulator_id,
            "regulator_name": self.regulator_name,
            "subscription_tier": self.subscription_tier,
            "permitted_corridors": (
                sorted(self.permitted_corridors)
                if self.permitted_corridors is not None
                else None
            ),
            "query_budget_monthly": self.query_budget_monthly,
            "privacy_budget_allocation": self.privacy_budget_allocation,
            "valid_from": _to_utc(self.valid_from).isoformat(),
            "valid_until": _to_utc(self.valid_until).isoformat(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def is_active(self, as_of: Optional[datetime] = None) -> bool:
        now = _to_utc(as_of or datetime.now(timezone.utc))
        return _to_utc(self.valid_from) <= now <= _to_utc(self.valid_until)

    def to_dict(self) -> dict:
        return {
            "regulator_id": self.regulator_id,
            "regulator_name": self.regulator_name,
            "subscription_tier": self.subscription_tier,
            "permitted_corridors": self.permitted_corridors,
            "query_budget_monthly": self.query_budget_monthly,
            "privacy_budget_allocation": self.privacy_budget_allocation,
            "valid_from": _to_utc(self.valid_from).isoformat(),
            "valid_until": _to_utc(self.valid_until).isoformat(),
            "hmac_signature": self.hmac_signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RegulatorSubscriptionToken":
        tier = str(data["subscription_tier"]).upper()
        if tier not in REGULATOR_SUBSCRIPTION_TIERS:
            raise ValueError(
                f"Unknown subscription_tier {tier!r} — valid: {REGULATOR_SUBSCRIPTION_TIERS}"
            )

        corridors = data.get("permitted_corridors")
        if corridors is not None:
            corridors = tuple(str(c) for c in corridors)

        token = cls(
            regulator_id=str(data["regulator_id"]),
            regulator_name=str(data["regulator_name"]),
            subscription_tier=tier,
            permitted_corridors=corridors,
            query_budget_monthly=int(data["query_budget_monthly"]),
            privacy_budget_allocation=float(data["privacy_budget_allocation"]),
            valid_from=_to_utc(datetime.fromisoformat(str(data["valid_from"]))),
            valid_until=_to_utc(datetime.fromisoformat(str(data["valid_until"]))),
            hmac_signature=str(data.get("hmac_signature", "")),
        )

        if token.query_budget_monthly <= 0:
            raise ValueError("query_budget_monthly must be positive")
        if token.privacy_budget_allocation <= 0:
            raise ValueError("privacy_budget_allocation must be positive")
        if _to_utc(token.valid_until) <= _to_utc(token.valid_from):
            raise ValueError("valid_until must be after valid_from")
        return token


def sign_regulator_token(
    token: RegulatorSubscriptionToken,
    signing_key: bytes,
) -> RegulatorSubscriptionToken:
    """Return a signed copy of ``token``."""
    signature = _compute_hmac(token.canonical_payload(), signing_key)
    return RegulatorSubscriptionToken(
        regulator_id=token.regulator_id,
        regulator_name=token.regulator_name,
        subscription_tier=token.subscription_tier,
        permitted_corridors=(
            tuple(token.permitted_corridors)
            if token.permitted_corridors is not None
            else None
        ),
        query_budget_monthly=token.query_budget_monthly,
        privacy_budget_allocation=token.privacy_budget_allocation,
        valid_from=token.valid_from,
        valid_until=token.valid_until,
        hmac_signature=signature,
    )


def verify_regulator_token(
    token: RegulatorSubscriptionToken,
    signing_key: bytes,
    as_of: Optional[datetime] = None,
) -> bool:
    """Return True if token signature is valid and token is active."""
    if not token.hmac_signature:
        logger.warning("Regulator subscription token has no signature")
        return False

    expected = _compute_hmac(token.canonical_payload(), signing_key)
    if not hmac.compare_digest(token.hmac_signature, expected):
        logger.error("Regulator token HMAC mismatch for regulator_id=%s", token.regulator_id)
        return False

    if not token.is_active(as_of=as_of):
        logger.error("Regulator token inactive for regulator_id=%s", token.regulator_id)
        return False

    return True


def encode_regulator_token(token: RegulatorSubscriptionToken) -> str:
    """Encode token into a compact bearer-safe string."""
    raw = json.dumps(token.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_regulator_token(encoded: str) -> RegulatorSubscriptionToken:
    """Decode token from compact bearer-safe string."""
    if not encoded:
        raise ValueError("encoded token is empty")
    pad = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((encoded + pad).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
        logger.error("Failed to decode regulator token: %s", e)
        raise ValueError("invalid encoded regulator token") from e
    return RegulatorSubscriptionToken.from_dict(payload)
