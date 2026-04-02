"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

inference_types.py — Pydantic-strict request/response types for the C1 inference endpoint.

All public objects in this module are importable from
``lip.c1_failure_classifier``.  The typed API is additive and
backwards-compatible: the legacy ``InferenceEngine.predict(dict) -> dict``
path is unchanged.

See docs/specs/c1_inference_endpoint_typing.md for the full contract.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_BIC_LENGTHS = frozenset({8, 11})
_CURRENCY_PAIR_RE = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")
_MIN_AMOUNT_USD: float = 0.01


# ---------------------------------------------------------------------------
# SHAPEntry — component of ClassifyResponse
# ---------------------------------------------------------------------------


class SHAPEntry(BaseModel):
    """A single feature attribution from the integrated-gradient SHAP approximation.

    Attributes
    ----------
    feature:
        Feature name as returned by
        :meth:`~lip.c1_failure_classifier.features.TabularFeatureEngineer.feature_names`.
    value:
        Signed integrated-gradient attribution for this feature.
    """

    feature: str
    value: float


# ---------------------------------------------------------------------------
# ClassifyRequest — typed inference input
# ---------------------------------------------------------------------------


class ClassifyRequest(BaseModel):
    """Pydantic-strict typed input for the C1 failure classification endpoint.

    All required fields are validated on construction; a ``ValidationError``
    is raised (and caught by :meth:`InferenceEngine.predict_validated`) for
    any schema violation.

    Attributes
    ----------
    payment_id:
        Optional idempotency key.  Echoed in the response; not used by the
        model.
    sending_bic:
        ISO 9362 Bank Identifier Code of the originating bank (8 or 11
        characters).
    receiving_bic:
        ISO 9362 BIC of the receiving bank (8 or 11 characters).
    amount_usd:
        Notional transaction amount in USD.  Must be ≥ 0.01.
    currency_pair:
        Corridor identifier in ``CCY1_CCY2`` format (e.g. ``"USD_EUR"``).
    transaction_type:
        ISO 20022 message type (e.g. ``"pacs.002"``).  Optional.
    timestamp_utc:
        POSIX timestamp for the payment event.  Defaults to ``None``
        (the inference engine substitutes ``time.time()`` if needed).
    metadata:
        Arbitrary pass-through dict; ignored by the model.
    """

    payment_id: Optional[str] = None
    sending_bic: str
    receiving_bic: str
    amount_usd: float = Field(..., ge=_MIN_AMOUNT_USD)
    currency_pair: str
    transaction_type: Optional[str] = None
    timestamp_utc: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    @field_validator("sending_bic", "receiving_bic")
    @classmethod
    def _validate_bic(cls, value: str, info: Any) -> str:
        if len(value) not in _BIC_LENGTHS:
            raise ValueError(
                f"{info.field_name} must be 8 or 11 characters; "
                f"got {len(value)!r} for {value!r}"
            )
        return value

    @field_validator("currency_pair")
    @classmethod
    def _validate_currency_pair(cls, value: str) -> str:
        if not _CURRENCY_PAIR_RE.match(value):
            raise ValueError(
                f"currency_pair must match CCY1_CCY2 (e.g. USD_EUR); got {value!r}"
            )
        return value

    # ------------------------------------------------------------------
    # Cross-field validator
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_bics_differ_warning(self) -> "ClassifyRequest":
        """Warn (not reject) when sending and receiving BIC are identical.

        Same-BIC payments are unusual but not technically invalid at the
        schema level (e.g. internal book transfers).
        """
        # No hard rejection — just a note for future monitoring hooks.
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict compatible with the legacy predict() API."""
        d: Dict[str, Any] = {
            "sending_bic": self.sending_bic,
            "receiving_bic": self.receiving_bic,
            "amount_usd": self.amount_usd,
            "currency_pair": self.currency_pair,
        }
        if self.payment_id is not None:
            d["payment_id"] = self.payment_id
        if self.transaction_type is not None:
            d["transaction_type"] = self.transaction_type
        if self.timestamp_utc is not None:
            d["timestamp_utc"] = self.timestamp_utc
        if self.metadata:
            d.update(self.metadata)
        return d


# ---------------------------------------------------------------------------
# ClassifyResponse — typed inference output
# ---------------------------------------------------------------------------


class ClassifyResponse(BaseModel):
    """Pydantic-strict typed output for a successful C1 classification.

    Attributes
    ----------
    failure_probability:
        Sigmoid output ∈ [0, 1].
    above_threshold:
        ``True`` when ``failure_probability >= threshold_used``.
    inference_latency_ms:
        Wall-clock end-to-end inference latency in milliseconds.
    threshold_used:
        Decision threshold applied to ``failure_probability``.
    corridor_embedding_used:
        ``True`` when a stored corridor embedding was found; ``False``
        when a cold-start embedding was synthesised.
    shap_top20:
        Top-20 feature attributions sorted by absolute value (descending).
        May contain fewer than 20 entries for low-dimensional inputs.
    payment_id:
        Echo of ``ClassifyRequest.payment_id``; ``None`` when the request
        had no payment ID.
    """

    failure_probability: float = Field(..., ge=0.0, le=1.0)
    above_threshold: bool
    inference_latency_ms: float = Field(..., ge=0.0)
    threshold_used: float = Field(..., ge=0.0, le=1.0)
    corridor_embedding_used: bool
    shap_top20: List[SHAPEntry]
    payment_id: Optional[str] = None

    @classmethod
    def from_dict(
        cls,
        raw: dict,
        payment_id: Optional[str] = None,
    ) -> "ClassifyResponse":
        """Construct from the legacy ``predict()`` output dict.

        Parameters
        ----------
        raw:
            Dict returned by :meth:`InferenceEngine.predict`.
        payment_id:
            Optional payment ID to echo into the response.
        """
        shap_entries = [SHAPEntry(**entry) for entry in raw.get("shap_top20", [])]
        return cls(
            failure_probability=raw["failure_probability"],
            above_threshold=raw["above_threshold"],
            inference_latency_ms=raw["inference_latency_ms"],
            threshold_used=raw["threshold_used"],
            corridor_embedding_used=raw["corridor_embedding_used"],
            shap_top20=shap_entries,
            payment_id=payment_id,
        )


# ---------------------------------------------------------------------------
# ClassifyError — typed error envelope
# ---------------------------------------------------------------------------


class ClassifyError(BaseModel):
    """Structured error returned by :meth:`InferenceEngine.predict_validated`
    when input validation or inference fails.

    Attributes
    ----------
    error_type:
        ``"VALIDATION_ERROR"`` for Pydantic schema violations;
        ``"INFERENCE_ERROR"`` for unexpected runtime failures.
    message:
        Human-readable description of the failure.
    field:
        Dot-path of the offending field for field-level validation errors;
        ``None`` for cross-field or runtime errors.
    payment_id:
        Echo of ``payment_id`` extracted from the raw input when available;
        ``None`` otherwise.
    """

    error_type: Literal["VALIDATION_ERROR", "INFERENCE_ERROR"]
    message: str
    field: Optional[str] = None
    payment_id: Optional[str] = None
