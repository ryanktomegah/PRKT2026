# LIP API Reference

All schemas are defined in `lip/common/schemas.py` using Pydantic v2.
All monetary amounts use `Decimal` for precision. All timestamps are timezone-aware UTC `datetime`.

---

## Pipeline Result: Exception OS v1

Every `PipelineResult` includes `exception_assessment: dict`.

| Field | Type | Description |
|-------|------|-------------|
| `exception_type` | `str` | One of `TECHNICAL_RETRYABLE`, `ACCOUNT_OR_ADDRESS`, `INSUFFICIENT_FUNDS_OR_LIQUIDITY`, `COMPLIANCE_OR_LEGAL_HOLD`, `DISPUTE_OR_COMMERCIAL_CONTEST`, `SANCTIONS_AML_RISK`, `CROSS_RAIL_HANDOFF_FAILURE`, `SETTLEMENT_TIMEOUT_OR_FINALITY`, `STRESS_REGIME`, `UNKNOWN` |
| `recommended_action` | `str` | One of `RETRY`, `HOLD`, `DECLINE`, `HUMAN_REVIEW`, `OFFER_BRIDGE`, `GUARANTEE_CANDIDATE`, `TELEMETRY_ONLY` |
| `reason_code` | `str` | Stable deterministic rule identifier |
| `reason` | `str` | Short operational explanation |
| `rail` | `str \| None` | Source rail, e.g. `SWIFT`, `FEDNOW`, `CBDC_NEXUS` |
| `maturity_hours` | `float \| None` | Rail-aware maturity used for the response context |
| `is_subday` | `bool` | `True` when maturity is under 24 hours |
| `confidence` | `float [0,1]` | Rule confidence, not a model probability |
| `signals` | `dict` | Auditable input signals used by the rule |

`GUARANTEE_CANDIDATE` is advisory metadata only in v1. It does not create a guarantee product, loan economics, or funding path.

---

## MIPLO API: `/miplo/process`

### `MIPLOProcessRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uetr` | `str` | Yes | Unique End-to-End Transaction Reference |
| `individual_payment_id` | `str` | No | ISO 20022 individual payment ID |
| `sending_bic` | `str` | Yes | Originator bank BIC |
| `receiving_bic` | `str` | Yes | Beneficiary bank BIC |
| `amount` | `str` | Yes | Payment amount as Decimal string |
| `currency` | `str` | Yes | ISO 4217 currency code |
| `rail` | `str` | No | Payment rail; defaults to `SWIFT` for backward compatibility |
| `rejection_code` | `str` | Yes | ISO 20022 rejection reason code |
| `narrative` | `str` | No | Free-text payment narrative |
| `debtor_account` | `str` | No | Debtor account identifier |
| `borrower` | `dict \| None` | No | Borrower data for C2 PD inference |
| `entity_id` | `str \| None` | No | Override entity ID for C6 velocity |
| `beneficiary_id` | `str \| None` | No | Override beneficiary ID for C6 velocity |

### `MIPLOProcessResponse`

| Field | Type | Description |
|-------|------|-------------|
| `outcome` | `str` | Final pipeline outcome |
| `uetr` | `str` | Echo of request UETR |
| `tenant_id` | `str` | Processor tenant ID |
| `failure_probability` | `float` | C1 score |
| `above_threshold` | `bool` | Whether C1 crossed `tau*` |
| `loan_offer` | `dict \| None` | C7 offer when produced |
| `decision_entry_id` | `str \| None` | C7 decision log entry |
| `exception_assessment` | `dict \| None` | Exception OS v1 assessment |
| `pd_estimate` | `float \| None` | C2 PD score |
| `fee_bps` | `int \| None` | Annualised bridge fee |
| `total_latency_ms` | `float` | End-to-end latency |

---

## C1: Failure Classifier (§4.2)

### `ClassifyRequest`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `uetr` | `UUID` | required | ISO 20022 UETR (UUIDv4) |
| `individual_payment_id` | `str` | 1–256 chars | Originating-bank payment ID |
| `corridor` | `str` | required | ISO 4217 pair, e.g. `'USD/EUR'` |
| `amount_usd` | `Decimal` | > 0 | Transaction amount normalised to USD |
| `sender_entity_id` | `str` | required | Hashed/pseudonymised sender ID |
| `receiver_entity_id` | `str` | required | Hashed/pseudonymised receiver ID |
| `rejection_code` | `str \| None` | optional | ISO 20022 rejection code |
| `event_timestamp` | `datetime` | required UTC | Payment event timestamp |
| `additional_features` | `dict` | default `{}` | Extra features forwarded to model |

### `ClassifyResponse`

| Field | Type | Description |
|-------|------|-------------|
| `uetr` | `UUID` | Echo of request UETR |
| `failure_probability` | `float [0,1]` | Predicted failure probability |
| `shap_top20` | `list[dict]` | Top-20 SHAP contributions (`feature`, `value`, `shap_value`) |
| `corridor_embedding_used` | `bool` | Whether corridor embedding was applied |
| `inference_latency_ms` | `float` | Wall-clock inference time |
| `threshold_used` | `float [0,1]` | F2-optimal threshold applied (τ* = 0.110, calibrated) |
| `above_threshold` | `bool` | `True` when `failure_probability >= threshold_used` |
| `model_version` | `str` | Model artefact version tag |
| `inference_timestamp` | `datetime UTC` | Inference timestamp |

---

## C2: PD Model (§4.3)

### `PDRequest`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `uetr` | `UUID` | required | ISO 20022 UETR |
| `loan_amount` | `Decimal` | > 0 | Bridge principal in USD |
| `corridor` | `str` | required | ISO 4217 pair |
| `sender_entity_id` | `str` | required | Hashed sender ID |
| `receiver_entity_id` | `str` | required | Hashed receiver ID |
| `rejection_code_class` | `str` | pattern `^[ABC]$` | Maturity class (A=3d, B=7d, C=21d) |
| `failure_probability` | `float [0,1]` | required | C1 upstream score |
| `event_timestamp` | `datetime UTC` | required | Payment event timestamp |

### `PDResponse`

| Field | Type | Description |
|-------|------|-------------|
| `pd_score` | `float [0,1]` | Probability of default |
| `fee_bps` | `Decimal ≥ 300` | **ANNUALISED** rate in basis points |
| `days_funded` | `int ≥ 1` | Maturity window (A=3, B=7, C=21) |
| `expected_fee_usd` | `Decimal ≥ 0` | Pre-computed fee |
| `recommended_action` | `str` | `'OFFER_BRIDGE'`, `'DECLINE'`, or `'MANUAL_REVIEW'` |
| `model_version` | `str` | Model artefact version |
| `inference_timestamp` | `datetime UTC` | Inference timestamp |

> **⚠️ Fee Formula Warning** — `fee_bps` is an **ANNUALISED** rate:
> ```
> per_cycle_fee = loan_amount × (fee_bps / 10_000) × (days_funded / 365)
> ```
> 300 bps annualised ≈ 0.0575% per 7-day cycle.
> **DO NOT** apply `fee_bps` as a flat per-cycle rate.

---

## C4: Dispute Classifier (§4.4)

### `DisputeClass` Enum

| Value | Hard Block | Description |
|-------|-----------|-------------|
| `NOT_DISPUTE` | No | Operational failure; bridge eligible |
| `DISPUTE_CONFIRMED` | **Yes** | Explicit commercial dispute |
| `DISPUTE_POSSIBLE` | **Yes** | Ambiguous; blocked conservatively |
| `NEGOTIATION` | **Yes** | Partial payment / resolution in progress |

### `DisputeRequest` / `DisputeResponse`

Key `DisputeResponse` fields:

| Field | Type | Description |
|-------|------|-------------|
| `dispute_class` | `DisputeClass` | C4 classifier output |
| `confidence` | `float [0,1]` | Softmax confidence for predicted class |
| `class_probabilities` | `dict[str, float]` | Softmax probabilities for all classes |
| `false_negative_risk` | `float [0,1]` | Model-estimated FN risk (target < 0.02) |
| `recommended_action` | `str` | e.g. `'BLOCK_AND_INVESTIGATE'` |

---

## C6: AML Velocity Check (§4.5)

### `VelocityResponse`

| Field | Type | Description |
|-------|------|-------------|
| `blocked` | `bool` | `True` when any velocity rule triggered |
| `triggered_rules` | `list[str]` | e.g. `['DOLLAR_CAP_EXCEEDED']` |
| `projected_24h_volume_usd` | `Decimal ≥ 0` | Volume after including this transaction |
| `projected_24h_count` | `int ≥ 0` | Count after including this transaction |
| `beneficiary_concentration_ratio` | `Decimal [0,1]` | Fraction going to largest beneficiary |
| `check_timestamp` | `datetime UTC` | Timestamp of this velocity check |

---

## C7: Bridge Loan Offer & Execution (§4.6)

### `LoanOffer`

| Field | Type | Description |
|-------|------|-------------|
| `offer_id` | `UUID` | Unique offer identifier |
| `uetr` | `UUID` | Underlying payment UETR |
| `mlo_entity_id` | `str` | Hashed MLO identifier |
| `miplo_entity_id` | `str` | Hashed MIPLO identifier |
| `elo_entity_id` | `str` | Hashed ELO identifier |
| `principal_usd` | `Decimal > 0` | Bridge loan principal |
| `fee_bps` | `Decimal ≥ 300` | **ANNUALISED** fee rate |
| `fee_amount_usd` | `Decimal ≥ 0` | Pre-computed fee |
| `maturity_days` | `int ≥ 1` | Loan maturity (A=3, B=7, C=21) |
| `rejection_code_class` | `str ^[ABC]$` | Class determining maturity |
| `offer_expiry` | `datetime UTC` | Offer expiry deadline |
| `pd_score` | `float [0,1]` | C2 PD score at offer time |
| `created_at` | `datetime UTC` | Creation timestamp |

### `ExecutionConfirmation`

| Field | Type | Description |
|-------|------|-------------|
| `confirmation_id` | `UUID` | Unique confirmation ID |
| `offer_id` | `UUID` | Accepted `LoanOffer.offer_id` |
| `funded_amount_usd` | `Decimal > 0` | Disbursed amount |
| `settlement_account` | `str` | Tokenised settlement account reference |
| `funded_at` | `datetime UTC` | Disbursement timestamp |
| `expected_repayment_at` | `datetime UTC` | Repayment deadline |

---

## C3: Settlement & Repayment (§4.7)

### `SettlementSignal` / `RepaymentConfirmation`

Key `RepaymentConfirmation` fields:

| Field | Type | Description |
|-------|------|-------------|
| `principal_repaid_usd` | `Decimal ≥ 0` | Principal repaid |
| `fee_repaid_usd` | `Decimal ≥ 0` | Fee repaid |
| `platform_royalty_usd` | `Decimal ≥ 0` | `15% × fee_repaid_usd` → BPI |
| `net_fee_to_entities_usd` | `Decimal ≥ 0` | `85% × fee_repaid_usd` → MLO/MIPLO/ELO |
| `total_repaid_usd` | `Decimal ≥ 0` | Principal + fee |
| `shortfall_usd` | `Decimal ≥ 0` | Outstanding balance (0 = full repayment) |
| `repayment_type` | `str` | `'FULL'`, `'BUFFER'`, or `'DEFAULT'` |

---

## Immutable Audit Log (§4.8)

### `DecisionLogEntry`

> **Retention**: 7 years on `lip.decision.log` Kafka topic.
> **Immutability**: `ConfigDict(frozen=True)` — no post-creation mutation.
> **Tamper detection**: `entry_signature` is HMAC-SHA256 over the canonical serialisation.

| Field | Type | Description |
|-------|------|-------------|
| `log_id` | `UUID` | Unique log entry ID |
| `uetr` | `UUID` | Payment UETR |
| `component` | `str` | e.g. `'C7_EXECUTION_AGENT'` |
| `decision` | `str` | e.g. `'BRIDGE_OFFERED'`, `'BLOCKED_AML'` |
| `input_hash` | `str` | SHA-256 of serialised input (tamper detection) |
| `output_hash` | `str` | SHA-256 of serialised output |
| `model_version` | `str \| None` | Model artefact version if ML was used |
| `inference_latency_ms` | `float \| None` | Inference time in ms |
| `kms_unavailable_gap` | `timedelta \| None` | KMS outage duration during request |
| `degraded_mode` | `bool` | `True` when produced under degraded operation |
| `gpu_fallback` | `bool` | `True` when CPU fallback was used |
| `entry_signature` | `str` | HMAC-SHA256 hex digest |
| `created_at` | `datetime UTC` | Entry creation timestamp |
