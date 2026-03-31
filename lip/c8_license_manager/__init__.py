"""
C8 — LIP License Manager
BPI technology licensor enforcement layer.

Validates that deployed LIP instances are authorized by a BPI-signed license
token.  License tokens are issued offline by BPI at contract time; the licensee
embeds the token in their deployment environment.  No network call is required
for validation — validation is offline HMAC-SHA256 verification against BPI's
signing key.

Boot flow:
  1. LicenseBootValidator.validate() reads token from env / file at C7 startup.
  2. If invalid or expired, KillSwitch.engage() is called — no loan offers issued.
  3. Valid token exposes LicenseeContext to downstream components (C6 salt
     namespacing, C7 TPS cap, audit logs).

Components exposed:
  LicenseToken       — token dataclass + sign / verify
  LicenseeContext    — runtime config derived from a validated token
  LicenseBootValidator — boot-time validation wired into C7 KillSwitch
"""

from .boot_validator import LicenseBootValidator
from .license_token import (
    LicenseeContext,
    LicenseToken,
    ProcessorLicenseeContext,
    sign_token,
    verify_token,
)
from .query_metering import (
    PrivacyBudgetExceededError,
    QueryBudgetExceededError,
    QueryMeterEntry,
    RegulatoryQueryMetering,
)
from .regulator_subscription import (
    REGULATOR_SUBSCRIPTION_TIERS,
    RegulatorSubscriptionToken,
    decode_regulator_token,
    encode_regulator_token,
    sign_regulator_token,
    verify_regulator_token,
)

__all__ = [
    "LicenseToken",
    "LicenseeContext",
    "ProcessorLicenseeContext",
    "LicenseBootValidator",
    "sign_token",
    "verify_token",
    "RegulatorSubscriptionToken",
    "REGULATOR_SUBSCRIPTION_TIERS",
    "sign_regulator_token",
    "verify_regulator_token",
    "encode_regulator_token",
    "decode_regulator_token",
    "QueryMeterEntry",
    "RegulatoryQueryMetering",
    "QueryBudgetExceededError",
    "PrivacyBudgetExceededError",
]
