# C6: AML Velocity

## Role in Pipeline

C6 is the **AML/CFT hard block gate**. It screens every payment that exceeds the C1 failure threshold through a three-stage gate: OFAC/EU/UN sanctions screening → velocity limits → anomaly detection. Any stage failure is a hard block; no bridge loan is offered.

## Algorithm 1 Position

```
C1 → C4 ∥ [C6] → hard block? → C2
```

C6 runs **in parallel with C4** (Step 2 of Algorithm 1).

## Processing Order (within C6)

```
1. SanctionsScreener  — OFAC / EU / UN list match (Jaccard ≥ 0.8)
2. VelocityChecker    — dollar cap + count cap + beneficiary concentration
3. AnomalyDetector    — Isolation Forest (or z-score fallback)
```

All three gates must pass; the first failure short-circuits the chain.

## Key Classes

| Class | File | Description |
|-------|------|-------------|
| `SanctionsScreener` | `sanctions.py` | OFAC/EU/UN list screening with Jaccard fuzzy match |
| `VelocityChecker` | `velocity.py` | 24-hour rolling-window velocity limits |
| `RollingWindow` | `velocity.py` | In-memory deque with `_cleanup_expired` |
| `AnomalyDetector` | `anomaly.py` | Isolation Forest with z-score fallback |
| `SaltRotationManager` | `salt_rotation.py` | Annual salt rotation with 30-day overlap |
| `AMLChecker` | `aml_checker.py` | Unified facade combining all three stages |

## Velocity Limits (AML Rules)

| Rule | Limit | Constant |
|------|-------|---------|
| Dollar cap | **$1,000,000** per entity per 24 h | `AML_DOLLAR_CAP_USD` |
| Count cap | **100** transactions per entity per 24 h | `AML_COUNT_CAP` |
| Beneficiary concentration | **>80%** to single beneficiary | `BENEFICIARY_CONCENTRATION` |

## Privacy Design (GDPR Art.25)

Raw entity identifiers are **never stored**. All window records use:

```
SHA-256(entity_id + salt)
```

The salt is provided by `SaltRotationManager`:
- **Annual rotation** (365 days) — old hash space is abandoned
- **30-day overlap window** — both salts accepted during transition
- **Per-licensee salt** — cross-licensee isolation; same entity ID produces different hashes for different licensees

## Salt Rotation Constants

| Constant | Value | Significance |
|----------|-------|-------------|
| `SALT_ROTATION_DAYS` | **365** | Full rotation cycle — **QUANT sign-off required** |
| `SALT_ROTATION_OVERLAP_DAYS` | **30** | Dual-salt overlap window — **QUANT sign-off required** |

## Anomaly Detection Features

8-dimensional feature vector (see `FEATURE_NAMES` in `anomaly.py`):

| Feature | Encoding |
|---------|---------|
| `amount_log` | `log1p(amount)` |
| `hour_sin` / `hour_cos` | Cyclical hour-of-day encoding |
| `day_sin` / `day_cos` | Cyclical day-of-week encoding |
| `velocity_ratio` | Current volume / 24h cap |
| `beneficiary_concentration` | Fraction to largest beneficiary |
| `amount_zscore` | Z-score within corridor history |

## Spec References

- Architecture Spec v1.2 §S11.3 — Salt rotation specification
- Architecture Spec v1.2 §4.5 — `VelocityRequest` / `VelocityResponse` schemas
- FATF Recommendation 10 — AML velocity controls for wire transfers
- GDPR Art.25 — Data protection by design (pseudonymisation via salted hash)
