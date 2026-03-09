"""
schemas.py — LIP Pydantic v2 API contracts
Architecture Spec v1.2 Section 4

All monetary amounts use Decimal for precision.
All timestamps are timezone-aware UTC datetimes.
"""
from __future__ import annotations

import enum
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Taxonomy enum  (S4.4)
# ---------------------------------------------------------------------------

class DisputeClass(str, enum.Enum):
    """Four-class taxonomy for C4 Dispute Classifier output (Architecture Spec S4.4).

    NOT_DISPUTE        — Operational delay; no buyer-seller conflict. Bridge eligible.
    DISPUTE_CONFIRMED  — Explicit commercial dispute. Hard block.
    DISPUTE_POSSIBLE   — Ambiguous language. Hard block (conservative).
    NEGOTIATION        — Partial payment / dispute resolution in progress. Hard block.
    """
    NOT_DISPUTE       = "NOT_DISPUTE"
    DISPUTE_CONFIRMED = "DISPUTE_CONFIRMED"
    DISPUTE_POSSIBLE  = "DISPUTE_POSSIBLE"
    NEGOTIATION       = "NEGOTIATION"


# ---------------------------------------------------------------------------
# S4.2  Failure Classifier
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    """Input payload for the C1 Failure Classifier endpoint (S4.2)."""

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(
        ...,
        description="ISO 20022 Unique End-to-End Transaction Reference (UUIDv4).",
    )
    individual_payment_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Originating-bank payment identifier.",
    )
    corridor: str = Field(
        ...,
        description="ISO 4217 currency pair, e.g. 'USD/EUR'.",
    )
    amount_usd: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Transaction amount normalised to USD.",
    )
    sender_entity_id: str = Field(
        ...,
        description="Hashed/pseudonymised sender entity identifier.",
    )
    receiver_entity_id: str = Field(
        ...,
        description="Hashed/pseudonymised receiver entity identifier.",
    )
    rejection_code: str | None = Field(
        default=None,
        description="ISO 20022 rejection code if the payment has already failed.",
    )
    event_timestamp: datetime = Field(
        ...,
        description="UTC timestamp of the payment event.",
    )
    additional_features: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary extra features forwarded to the model.",
    )


class ClassifyResponse(BaseModel):
    """Output payload from the C1 Failure Classifier endpoint (S4.2)."""

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(..., description="Echo of the request UETR.")
    individual_payment_id: str = Field(..., description="Echo of the request payment ID.")
    failure_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model-estimated probability [0, 1] that this payment will fail.",
    )
    shap_top20: list[dict[str, Any]] = Field(
        ...,
        max_length=20,
        description=(
            "Top-20 SHAP feature contributions, each entry a dict with keys "
            "'feature', 'value', 'shap_value'."
        ),
    )
    corridor_embedding_used: bool = Field(
        ...,
        description="True when a corridor-specific embedding was applied during inference.",
    )
    inference_latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock inference time in milliseconds.",
    )
    threshold_used: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Decision threshold (F2-optimal) applied to produce above_threshold.",
    )
    above_threshold: bool = Field(
        ...,
        description="True when failure_probability >= threshold_used.",
    )
    model_version: str = Field(..., description="Deployed model artefact version tag.")
    inference_timestamp: datetime = Field(
        ...,
        description="UTC timestamp at which inference was performed.",
    )


# ---------------------------------------------------------------------------
# S4.3  Probability-of-Default (PD) Model
# ---------------------------------------------------------------------------

class PDRequest(BaseModel):
    """Input payload for the C2 PD Model endpoint (S4.3)."""

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(..., description="ISO 20022 UETR.")
    loan_amount: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Requested bridge-loan principal in USD.",
    )
    corridor: str = Field(..., description="ISO 4217 currency pair, e.g. 'USD/EUR'.")
    sender_entity_id: str = Field(..., description="Hashed sender entity identifier.")
    receiver_entity_id: str = Field(..., description="Hashed receiver entity identifier.")
    rejection_code_class: str = Field(
        ...,
        pattern=r"^[ABC]$",
        description="Rejection-code maturity class: A (3d), B (7d), or C (21d).",
    )
    failure_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Upstream failure probability from C1 Classifier.",
    )
    event_timestamp: datetime = Field(..., description="UTC event timestamp.")


class PDResponse(BaseModel):
    """Output payload from the C2 PD Model endpoint (S4.3).

    Fee calculation reference (Architecture Spec v1.2 Appendix A):
        per_cycle_fee = loan_amount * (fee_bps / 10_000) * (days_funded / 365)
    The fee_bps field is an ANNUALIZED rate.  300 bps annualized ≈ 0.0575% per 7-day cycle.
    DO NOT apply fee_bps as a flat per-cycle rate.
    """

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(..., description="Echo of the request UETR.")
    pd_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of default for the proposed bridge loan.",
    )
    fee_bps: Decimal = Field(
        ...,
        ge=Decimal("300"),
        description=(
            "ANNUALIZED rate in basis points.  "
            "Per-cycle fee = loan_amount * (fee_bps/10000) * (days_funded/365).  "
            "Floor: 300 bps annualized = 0.0575% per 7-day cycle.  "
            "DO NOT apply as flat per-cycle rate."
        ),
    )
    days_funded: int = Field(
        ...,
        ge=1,
        description="Maturity window in days derived from rejection_code_class (A=3, B=7, C=21).",
    )
    expected_fee_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Pre-computed fee: loan_amount * (fee_bps/10000) * (days_funded/365).",
    )
    recommended_action: str = Field(
        ...,
        description="One of: 'OFFER_BRIDGE', 'DECLINE', 'MANUAL_REVIEW'.",
    )
    model_version: str = Field(..., description="Deployed PD model artefact version tag.")
    inference_timestamp: datetime = Field(..., description="UTC inference timestamp.")


# ---------------------------------------------------------------------------
# S4.4  Dispute Classifier
# ---------------------------------------------------------------------------

class DisputeRequest(BaseModel):
    """Input payload for the C4 Dispute Classifier endpoint (S4.4)."""

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(..., description="ISO 20022 UETR.")
    individual_payment_id: str = Field(..., description="Originating-bank payment identifier.")
    rejection_code: str = Field(
        ...,
        description="ISO 20022 rejection / return reason code.",
    )
    amount_usd: Decimal = Field(..., gt=Decimal("0"), description="Transaction amount in USD.")
    sender_entity_id: str = Field(..., description="Hashed sender entity identifier.")
    receiver_entity_id: str = Field(..., description="Hashed receiver entity identifier.")
    corridor: str = Field(..., description="ISO 4217 currency pair.")
    narrative: str | None = Field(
        default=None,
        max_length=2048,
        description="Free-text payment narrative or remittance information.",
    )
    event_timestamp: datetime = Field(..., description="UTC event timestamp.")


class DisputeResponse(BaseModel):
    """Output payload from the C4 Dispute Classifier endpoint (S4.4)."""

    model_config = ConfigDict(frozen=True)

    uetr: UUID = Field(..., description="Echo of the request UETR.")
    dispute_class: DisputeClass = Field(
        ...,
        description=(
            "C4 classifier output: NOT_DISPUTE | DISPUTE_CONFIRMED | "
            "DISPUTE_POSSIBLE | NEGOTIATION."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Softmax confidence for the predicted class.",
    )
    class_probabilities: dict[str, float] = Field(
        ...,
        description="Softmax probability for each DisputeClass member.",
    )
    false_negative_risk: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Model-estimated risk of a false-negative outcome for this classification.  "
            "Target < 0.02 (Architecture Spec Appendix A)."
        ),
    )
    recommended_action: str = Field(
        ...,
        description=(
            "Suggested downstream action, e.g. 'BLOCK_AND_INVESTIGATE', "
            "'ROUTE_TO_COMPLIANCE', 'STANDARD_RECOVERY'."
        ),
    )
    model_version: str = Field(..., description="Deployed classifier artefact version tag.")
    inference_timestamp: datetime = Field(..., description="UTC inference timestamp.")


# ---------------------------------------------------------------------------
# S4.5  AML Velocity Check
# ---------------------------------------------------------------------------

class VelocityRequest(BaseModel):
    """Input payload for the C6 AML Velocity Check endpoint (S4.5)."""

    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(..., description="Hashed entity identifier being checked.")
    transaction_amount_usd: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Amount of the candidate transaction in USD.",
    )
    beneficiary_entity_id: str = Field(
        ...,
        description="Hashed beneficiary / counterparty identifier.",
    )
    event_timestamp: datetime = Field(..., description="UTC timestamp of the candidate event.")
    rolling_24h_volume_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total USD volume transacted by entity_id in the preceding 24-hour window.",
    )
    rolling_24h_count: int = Field(
        ...,
        ge=0,
        description="Number of transactions by entity_id in the preceding 24-hour window.",
    )
    beneficiary_24h_volume_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description=(
            "USD volume sent to beneficiary_entity_id by entity_id "
            "in the preceding 24-hour window."
        ),
    )


class VelocityResponse(BaseModel):
    """Output payload from the C6 AML Velocity Check endpoint (S4.5)."""

    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(..., description="Echo of the request entity_id.")
    blocked: bool = Field(
        ...,
        description=(
            "True when any velocity rule is triggered and the transaction must be blocked."
        ),
    )
    triggered_rules: list[str] = Field(
        default_factory=list,
        description=(
            "List of rule identifiers that fired, e.g. "
            "['DOLLAR_CAP_EXCEEDED', 'COUNT_CAP_EXCEEDED', 'BENEFICIARY_CONCENTRATION']."
        ),
    )
    projected_24h_volume_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="rolling_24h_volume_usd + transaction_amount_usd.",
    )
    projected_24h_count: int = Field(
        ...,
        ge=0,
        description="rolling_24h_count + 1.",
    )
    beneficiary_concentration_ratio: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("1"),
        description=(
            "beneficiary_24h_volume_usd / projected_24h_volume_usd "
            "(0 when projected volume is zero)."
        ),
    )
    check_timestamp: datetime = Field(..., description="UTC timestamp of this velocity check.")


# ---------------------------------------------------------------------------
# S4.6  Bridge Loan Offer and Execution Confirmation
# ---------------------------------------------------------------------------

class LoanOffer(BaseModel):
    """Bridge-loan offer generated by MLO and forwarded to ELO/C7 (S4.6).

    Fee calculation (Architecture Spec v1.2 Appendix A):
        fee_amount_usd = principal_usd * (fee_bps / 10_000) * (maturity_days / 365)
    fee_bps is an ANNUALIZED rate; 300 bps floor.
    """

    model_config = ConfigDict(frozen=True)

    offer_id: UUID = Field(..., description="Unique identifier for this loan offer.")
    uetr: UUID = Field(..., description="ISO 20022 UETR of the underlying payment.")
    mlo_entity_id: str = Field(..., description="Hashed MLO entity identifier.")
    miplo_entity_id: str = Field(..., description="Hashed MIPLO entity identifier.")
    elo_entity_id: str = Field(..., description="Hashed ELO entity identifier.")
    principal_usd: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Bridge-loan principal amount in USD.",
    )
    fee_bps: Decimal = Field(
        ...,
        ge=Decimal("300"),
        description=(
            "ANNUALIZED fee rate in basis points (floor 300 bps).  "
            "fee_amount_usd = principal_usd * (fee_bps/10000) * (maturity_days/365)."
        ),
    )
    fee_amount_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Pre-computed fee in USD.",
    )
    maturity_days: int = Field(
        ...,
        ge=1,
        description="Loan maturity in days (Class A=3, B=7, C=21).",
    )
    rejection_code_class: str = Field(
        ...,
        pattern=r"^[ABC]$",
        description="Rejection-code class that determined maturity_days.",
    )
    offer_expiry: datetime = Field(
        ...,
        description="UTC datetime after which this offer is no longer valid.",
    )
    pd_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability-of-default score from C2 at time of offer generation.",
    )
    created_at: datetime = Field(..., description="UTC creation timestamp.")


class ExecutionConfirmation(BaseModel):
    """Confirmation from ELO/C7 that a bridge loan has been funded (S4.6)."""

    model_config = ConfigDict(frozen=True)

    confirmation_id: UUID = Field(..., description="Unique identifier for this confirmation.")
    offer_id: UUID = Field(..., description="Echo of the accepted LoanOffer.offer_id.")
    uetr: UUID = Field(..., description="ISO 20022 UETR of the underlying payment.")
    elo_entity_id: str = Field(..., description="Hashed ELO entity identifier.")
    funded_amount_usd: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Actual disbursed amount in USD (must equal offer principal_usd).",
    )
    settlement_account: str = Field(
        ...,
        description="Hashed/tokenised destination settlement account reference.",
    )
    funded_at: datetime = Field(..., description="UTC timestamp of fund disbursement.")
    expected_repayment_at: datetime = Field(
        ...,
        description="UTC deadline for full repayment (funded_at + maturity_days).",
    )


# ---------------------------------------------------------------------------
# S4.7  Settlement Signal and Repayment Confirmation
# ---------------------------------------------------------------------------

class SettlementSignal(BaseModel):
    """Inbound settlement notification received by MIPLO triggering repayment (S4.7)."""

    model_config = ConfigDict(frozen=True)

    signal_id: UUID = Field(..., description="Unique identifier for this settlement signal.")
    uetr: UUID = Field(..., description="ISO 20022 UETR of the settled payment.")
    miplo_entity_id: str = Field(..., description="Hashed MIPLO entity identifier.")
    settled_amount_usd: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Amount received in the settlement in USD.",
    )
    settlement_timestamp: datetime = Field(
        ...,
        description="UTC timestamp of confirmed settlement.",
    )
    swift_message_ref: str | None = Field(
        default=None,
        description="SWIFT message reference (e.g., MT202 / pacs.009 MsgId) if available.",
    )
    buffer_applied: bool = Field(
        default=False,
        description=(
            "True when the settlement amount partially covers principal + fee "
            "(buffer-repayment path)."
        ),
    )


class RepaymentConfirmation(BaseModel):
    """Confirmation that C3 Repayment Engine has processed a repayment (S4.7)."""

    model_config = ConfigDict(frozen=True)

    repayment_id: UUID = Field(..., description="Unique identifier for this repayment record.")
    offer_id: UUID = Field(..., description="LoanOffer.offer_id being repaid.")
    uetr: UUID = Field(..., description="ISO 20022 UETR of the underlying payment.")
    principal_repaid_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Principal component repaid in USD.",
    )
    fee_repaid_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Fee component repaid in USD.",
    )
    platform_royalty_usd: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="BPI platform operator royalty (PLATFORM_ROYALTY_RATE × fee_repaid_usd).",
    )
    net_fee_to_entities_usd: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Fee retained by MLO/MIPLO/ELO after platform royalty deduction.",
    )
    total_repaid_usd: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total amount repaid (principal_repaid_usd + fee_repaid_usd).",
    )
    shortfall_usd: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Outstanding balance after repayment (0 for full repayment).",
    )
    repayment_type: str = Field(
        ...,
        description="One of: 'FULL', 'BUFFER', 'DEFAULT'.",
    )
    signal_id: UUID = Field(
        ...,
        description="SettlementSignal.signal_id that triggered this repayment.",
    )
    repaid_at: datetime = Field(..., description="UTC timestamp of repayment processing.")


# ---------------------------------------------------------------------------
# S4.8  Decision Log Entry
# ---------------------------------------------------------------------------

class DecisionLogEntry(BaseModel):
    """Immutable audit record for every LIP decision (S4.8).

    Retained for DECISION_LOG_RETENTION_YEARS (7 years, Architecture Spec Appendix A).
    entry_signature is an HMAC-SHA256 hex digest over the serialised payload,
    produced by encryption.sign_hmac_sha256.
    """

    model_config = ConfigDict(frozen=True)

    log_id: UUID = Field(..., description="Unique identifier for this log entry.")
    uetr: UUID = Field(..., description="ISO 20022 UETR of the payment this decision concerns.")
    component: str = Field(
        ...,
        description=(
            "Originating LIP component, e.g. 'C1_FAILURE_CLASSIFIER', "
            "'C2_PD_MODEL', 'C3_REPAYMENT_ENGINE', 'C4_DISPUTE_CLASSIFIER', "
            "'C6_AML_VELOCITY', 'C7_EXECUTION_AGENT'."
        ),
    )
    decision: str = Field(
        ...,
        description="Human-readable decision outcome, e.g. 'BRIDGE_OFFERED', 'BLOCKED_AML'.",
    )
    input_hash: str = Field(
        ...,
        description="SHA-256 hex digest of the serialised input payload (for tamper detection).",
    )
    output_hash: str = Field(
        ...,
        description="SHA-256 hex digest of the serialised output payload.",
    )
    model_version: str | None = Field(
        default=None,
        description="Model artefact version tag if an ML model was invoked.",
    )
    inference_latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Inference wall-clock time in milliseconds (None for non-ML decisions).",
    )
    kms_unavailable_gap: timedelta | None = Field(
        default=None,
        description=(
            "Duration for which KMS was unavailable during this request, "
            "None when KMS was fully available."
        ),
    )
    degraded_mode: bool = Field(
        default=False,
        description=(
            "True when this decision was produced under degraded-mode operation "
            "(e.g., KMS unavailable, cached model weights)."
        ),
    )
    gpu_fallback: bool = Field(
        default=False,
        description="True when inference fell back from GPU to CPU.",
    )
    entry_signature: str = Field(
        ...,
        description=(
            "HMAC-SHA256 hex digest over the canonical serialisation of this entry "
            "(excluding entry_signature itself), produced by encryption.sign_hmac_sha256."
        ),
    )
    created_at: datetime = Field(..., description="UTC creation timestamp.")
