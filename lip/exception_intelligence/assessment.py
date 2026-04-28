"""Deterministic v1 Exception OS assessment rules.

The module is deliberately read-only with respect to financial behavior. It
classifies an already-computed pipeline outcome and recommends the next
operational response without changing C1/C2/C4/C6/C7 gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from lip.c3_repayment_engine.rejection_taxonomy import (
    RejectionClass,
    classify_rejection_code,
)


class ExceptionType(str, Enum):
    TECHNICAL_RETRYABLE = "TECHNICAL_RETRYABLE"
    ACCOUNT_OR_ADDRESS = "ACCOUNT_OR_ADDRESS"
    INSUFFICIENT_FUNDS_OR_LIQUIDITY = "INSUFFICIENT_FUNDS_OR_LIQUIDITY"
    COMPLIANCE_OR_LEGAL_HOLD = "COMPLIANCE_OR_LEGAL_HOLD"
    DISPUTE_OR_COMMERCIAL_CONTEST = "DISPUTE_OR_COMMERCIAL_CONTEST"
    SANCTIONS_AML_RISK = "SANCTIONS_AML_RISK"
    CROSS_RAIL_HANDOFF_FAILURE = "CROSS_RAIL_HANDOFF_FAILURE"
    SETTLEMENT_TIMEOUT_OR_FINALITY = "SETTLEMENT_TIMEOUT_OR_FINALITY"
    STRESS_REGIME = "STRESS_REGIME"
    UNKNOWN = "UNKNOWN"


class RecommendedAction(str, Enum):
    RETRY = "RETRY"
    HOLD = "HOLD"
    DECLINE = "DECLINE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    OFFER_BRIDGE = "OFFER_BRIDGE"
    GUARANTEE_CANDIDATE = "GUARANTEE_CANDIDATE"
    TELEMETRY_ONLY = "TELEMETRY_ONLY"


@dataclass(frozen=True)
class ExceptionAssessment:
    exception_type: ExceptionType
    recommended_action: RecommendedAction
    reason_code: str
    reason: str
    rail: Optional[str]
    maturity_hours: Optional[float]
    is_subday: bool
    confidence: float
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["exception_type"] = self.exception_type.value
        payload["recommended_action"] = self.recommended_action.value
        return payload


_ACCOUNT_OR_ADDRESS_CODES = frozenset({
    "AC01",
    "AC04",
    "AC06",
    "AGNT",
    "BE01",
    "BE05",
    "INVB",
    "INVR",
    "MD01",
    "MD02",
    "RC01",
})
_INSUFFICIENT_FUNDS_CODES = frozenset({"AM01", "AM02", "AM04", "AM06", "AM09", "AM12", "UMKA"})
_SETTLEMENT_FINALITY_CODES = frozenset({"ED05", "RCON", "TIMO", "CBDC-CF01", "CBDC-CB01"})
_TECHNICAL_CODES = frozenset({
    "AG02",
    "AM03",
    "AM05",
    "AM10",
    "CURR",
    "CVCY",
    "DT01",
    "ED01",
    "ED03",
    "FF01",
    "FF03",
    "FF05",
    "FOCR",
    "NARR",
    "NOAS",
    "NOOR",
    "OPAY",
    "PCOR",
    "PTNA",
    "QMIS",
    "SVNR",
    "TECH",
    "UPAY",
})
_COMPLIANCE_OR_LEGAL_CODES = frozenset({"AG01", "CNOR", "DNOR", "LEGL", "RR01", "RR02", "RR03", "RR04"})
_DISPUTE_CODES = frozenset({"DISP", "DUPL", "FRAD", "FRAU", "MD06", "CUST", "INDM", "MS02"})


def assess_exception(
    *,
    outcome: str,
    rail: Optional[str],
    rejection_code: Optional[str],
    maturity_hours: Optional[float],
    failure_probability: float,
    above_threshold: bool,
    dispute_hard_block: bool = False,
    aml_hard_block: bool = False,
    aml_passed: Optional[bool] = None,
    compliance_hold: bool = False,
    pd_estimate: Optional[float] = None,
    c7_status: Optional[str] = None,
    handoff_parent_uetr: Optional[str] = None,
    stress_regime: bool = False,
    loan_offer_present: bool = False,
    extra_signals: Optional[dict[str, Any]] = None,
) -> ExceptionAssessment:
    """Classify a completed pipeline result into an Exception OS assessment."""

    code = _normalise_code(rejection_code)
    mapped_type = _map_rejection_code(code, rail=rail, maturity_hours=maturity_hours)
    known_code = _is_known_code(code)
    rejection_class = _rejection_class(code)
    is_subday = bool(maturity_hours is not None and maturity_hours < 24.0)
    existing_bridge_offer = outcome in {"OFFERED", "DOMESTIC_LEG_FAILURE"} or loan_offer_present
    signals = {
        "outcome": outcome,
        "rejection_code": code,
        "rejection_class": rejection_class.value if rejection_class else None,
        "failure_probability": failure_probability,
        "above_threshold": above_threshold,
        "pd_estimate": pd_estimate,
        "dispute_hard_block": dispute_hard_block,
        "aml_passed": aml_passed,
        "aml_hard_block": aml_hard_block,
        "compliance_hold": compliance_hold,
        "c7_status": c7_status,
        "handoff_parent_uetr": handoff_parent_uetr,
        "stress_regime": stress_regime,
    }
    if extra_signals:
        signals.update(extra_signals)

    if outcome == "RETRY_BLOCKED":
        return _assessment(
            ExceptionType.TECHNICAL_RETRYABLE,
            RecommendedAction.HOLD,
            "RETRY_BLOCKED",
            "Duplicate or retry-like payment context was blocked before bridge eligibility.",
            rail,
            maturity_hours,
            is_subday,
            0.92,
            signals,
        )

    if compliance_hold or outcome == "COMPLIANCE_HOLD" or code in _COMPLIANCE_OR_LEGAL_CODES:
        return _assessment(
            ExceptionType.COMPLIANCE_OR_LEGAL_HOLD,
            RecommendedAction.HOLD,
            f"COMPLIANCE_HOLD_{code or 'OUTCOME'}",
            "Compliance, legal, or regulatory hold prevents an automated bridge response.",
            rail,
            maturity_hours,
            is_subday,
            0.95,
            signals,
        )

    if outcome in {"AML_BLOCKED", "AML_CHECK_UNAVAILABLE"} or aml_hard_block:
        return _assessment(
            ExceptionType.SANCTIONS_AML_RISK,
            RecommendedAction.HOLD,
            f"AML_GATE_{outcome}",
            "C6 AML/sanctions gate blocked or could not verify the payment.",
            rail,
            maturity_hours,
            is_subday,
            0.92,
            signals,
        )

    if outcome == "DISPUTE_BLOCKED" or dispute_hard_block or code in _DISPUTE_CODES:
        return _assessment(
            ExceptionType.DISPUTE_OR_COMMERCIAL_CONTEST,
            RecommendedAction.DECLINE,
            f"DISPUTE_{code or 'C4'}",
            "Dispute, fraud, duplicate, or commercial contest signal blocks bridge eligibility.",
            rail,
            maturity_hours,
            is_subday,
            0.93,
            signals,
        )

    if not above_threshold or outcome == "BELOW_THRESHOLD":
        return _assessment(
            mapped_type,
            RecommendedAction.TELEMETRY_ONLY,
            f"BELOW_C1_THRESHOLD_{code or 'NO_CODE'}",
            "C1 score is below the bridge decision threshold; retain the exception signal as telemetry only.",
            rail,
            maturity_hours,
            is_subday,
            0.84 if known_code else 0.62,
            signals,
        )

    if handoff_parent_uetr:
        action = (
            RecommendedAction.OFFER_BRIDGE
            if existing_bridge_offer
            else RecommendedAction.HUMAN_REVIEW
        )
        return _assessment(
            ExceptionType.CROSS_RAIL_HANDOFF_FAILURE,
            action,
            "CROSS_RAIL_PARENT_UETR",
            "A domestic or instant-rail leg failed with a registered upstream parent UETR.",
            rail,
            maturity_hours,
            is_subday,
            0.9,
            signals,
        )

    if stress_regime:
        return _assessment(
            ExceptionType.STRESS_REGIME,
            RecommendedAction.HUMAN_REVIEW,
            "STRESSED_RAIL_CORRIDOR",
            "The rail/corridor is in a stress regime; route the exception for human review.",
            rail,
            maturity_hours,
            is_subday,
            0.88,
            signals,
        )

    if outcome == "SYSTEM_ERROR":
        return _assessment(
            ExceptionType.UNKNOWN,
            RecommendedAction.HUMAN_REVIEW,
            "SYSTEM_ERROR",
            "Pipeline component failure prevented a complete exception decision.",
            rail,
            maturity_hours,
            is_subday,
            0.5,
            signals,
        )

    if code is not None and not known_code:
        return _assessment(
            ExceptionType.UNKNOWN,
            RecommendedAction.HUMAN_REVIEW,
            f"UNKNOWN_REJECTION_CODE_{code}",
            "Rejection code is not in the deterministic v1 taxonomy; review before responding.",
            rail,
            maturity_hours,
            is_subday,
            0.52,
            signals,
        )

    if existing_bridge_offer:
        return _assessment(
            mapped_type,
            RecommendedAction.OFFER_BRIDGE,
            f"C7_OFFER_{code or 'NO_CODE'}",
            "Existing pipeline gates produced a bridge offer; Exception OS records the exception type.",
            rail,
            maturity_hours,
            is_subday,
            0.86 if known_code else 0.6,
            signals,
        )

    if is_subday and _clean_underwriting_signals(dispute_hard_block, aml_passed, pd_estimate):
        return _assessment(
            mapped_type
            if mapped_type != ExceptionType.UNKNOWN
            else ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY,
            RecommendedAction.GUARANTEE_CANDIDATE,
            f"SUBDAY_ADVISORY_{code or 'NO_CODE'}",
            "Sub-day rail exception with clean gates is eligible for advisory guarantee-candidate metadata.",
            rail,
            maturity_hours,
            is_subday,
            0.76 if known_code else 0.58,
            signals,
        )

    if outcome in {"HALT", "PENDING_HUMAN_REVIEW"}:
        return _assessment(
            mapped_type,
            RecommendedAction.HUMAN_REVIEW,
            f"{outcome}_{code or 'NO_CODE'}",
            "Pipeline parked or halted the payment; human review is the appropriate response.",
            rail,
            maturity_hours,
            is_subday,
            0.78 if known_code else 0.55,
            signals,
        )

    if outcome == "DECLINED":
        return _assessment(
            mapped_type,
            RecommendedAction.DECLINE,
            f"C7_DECLINE_{code or 'NO_CODE'}",
            "C7 declined the bridge after upstream risk gates completed.",
            rail,
            maturity_hours,
            is_subday,
            0.8 if known_code else 0.55,
            signals,
        )

    return _assessment(
        mapped_type,
        RecommendedAction.HUMAN_REVIEW if above_threshold else RecommendedAction.TELEMETRY_ONLY,
        f"UNKNOWN_OUTCOME_{outcome}",
        "No deterministic v1 Exception OS rule matched this outcome.",
        rail,
        maturity_hours,
        is_subday,
        0.5,
        signals,
    )


def _assessment(
    exception_type: ExceptionType,
    action: RecommendedAction,
    reason_code: str,
    reason: str,
    rail: Optional[str],
    maturity_hours: Optional[float],
    is_subday: bool,
    confidence: float,
    signals: dict[str, Any],
) -> ExceptionAssessment:
    return ExceptionAssessment(
        exception_type=exception_type,
        recommended_action=action,
        reason_code=reason_code,
        reason=reason,
        rail=rail,
        maturity_hours=maturity_hours,
        is_subday=is_subday,
        confidence=confidence,
        signals=signals,
    )


def _normalise_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return code.strip().upper()


def _is_known_code(code: Optional[str]) -> bool:
    if code is None:
        return False
    if code.startswith("CBDC-"):
        return True
    try:
        classify_rejection_code(code)
        return True
    except ValueError:
        return False


def _rejection_class(code: Optional[str]) -> Optional[RejectionClass]:
    if code is None:
        return None
    try:
        return classify_rejection_code(code)
    except ValueError:
        return None


def _map_rejection_code(
    code: Optional[str],
    *,
    rail: Optional[str],
    maturity_hours: Optional[float],
) -> ExceptionType:
    if code is None:
        return (
            ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY
            if _is_subday_rail(rail, maturity_hours)
            else ExceptionType.UNKNOWN
        )
    if code in _COMPLIANCE_OR_LEGAL_CODES:
        return ExceptionType.COMPLIANCE_OR_LEGAL_HOLD
    if code in _DISPUTE_CODES:
        return ExceptionType.DISPUTE_OR_COMMERCIAL_CONTEST
    if code in _ACCOUNT_OR_ADDRESS_CODES:
        return ExceptionType.ACCOUNT_OR_ADDRESS
    if code in _INSUFFICIENT_FUNDS_CODES:
        return ExceptionType.INSUFFICIENT_FUNDS_OR_LIQUIDITY
    if code in _SETTLEMENT_FINALITY_CODES:
        return ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY
    if code in _TECHNICAL_CODES:
        return (
            ExceptionType.SETTLEMENT_TIMEOUT_OR_FINALITY
            if _is_subday_rail(rail, maturity_hours)
            else ExceptionType.TECHNICAL_RETRYABLE
        )
    return ExceptionType.UNKNOWN


def _is_subday_rail(rail: Optional[str], maturity_hours: Optional[float]) -> bool:
    if maturity_hours is not None and maturity_hours < 24.0:
        return True
    return bool(rail and rail.upper().startswith("CBDC_"))


def _clean_underwriting_signals(
    dispute_hard_block: bool,
    aml_passed: Optional[bool],
    pd_estimate: Optional[float],
) -> bool:
    return not dispute_hard_block and aml_passed is True and pd_estimate is not None
