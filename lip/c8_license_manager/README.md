# C8: License Manager

## Role in Pipeline

C8 is a **cross-cutting infrastructure component** — not part of the linear Algorithm 1 flow, but invoked at every service startup and periodically during runtime. It validates that the deploying entity holds a valid LIP license token and stamps all decision log entries with the `licensee_id`.

## Algorithm 1 Position

```
[C8: boot validation] → ALL components initialise → pipeline starts
         │
         └─ periodic token refresh checks (background)
```

C8 runs **before** any pipeline processing and in the background **throughout** platform operation.

## Key Classes

| Class / Function | File | Description |
|-----------------|------|-------------|
| `LicenseManager` | `manager.py` | Token validation, boot check, licensee_id extraction |
| `HMACTokenValidator` | `validator.py` | HMAC-SHA256 signature verification |
| `LicenseToken` | `token.py` | Dataclass representing a parsed license token |
| `validate_boot` | `manager.py` | Entry point called at service startup |

## Token Structure

LIP license tokens are HMAC-SHA256 signed JWT-style structures containing:

| Field | Description |
|-------|-------------|
| `licensee_id` | Unique identifier for the deploying bank/institution |
| `issued_at` | UTC datetime of token issuance |
| `expires_at` | UTC token expiry |
| `permitted_volume_usd` | Maximum 24-hour bridge-loan volume authorised |
| `signature` | HMAC-SHA256 over the canonical payload |

## Boot Validation

On startup, `validate_boot()`:
1. Loads the token from `LIP_LICENSE_TOKEN` environment variable
2. Verifies the HMAC-SHA256 signature against the BPI public key
3. Checks token is not expired
4. Extracts and stores `licensee_id` for downstream use

**If validation fails, the service refuses to start.** This is a hard requirement — no token, no operation.

## Cross-Licensee Salt Isolation

C8's `licensee_id` is used as a namespace seed for C6's `SaltRotationManager`. Different licensees receive different salts, ensuring:
- Entity hashes from Licensee A cannot be correlated with hashes from Licensee B
- A compromise of one licensee's Redis store does not expose another's AML patterns

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `SALT_ROTATION_DAYS` | 365 | Salt lifecycle tied to license renewal cycle |
| `PLATFORM_ROYALTY_RATE` | 0.15 | Royalty rate embedded in license terms |

## Spec References

- Architecture Spec v1.2 §S11 — License management specification
- Architecture Spec v1.2 §S11.3 — Cross-licensee salt rotation
- Patent Claims 2(i–vi) — System architecture components including licensing
