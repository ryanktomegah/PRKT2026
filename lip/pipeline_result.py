"""
pipeline_result.py — PipelineResult dataclass for the LIP end-to-end pipeline.
Architecture Spec v1.2 Section 3.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PipelineResult:
    """Result of a single payment event processed through the LIP pipeline.

    Attributes
    ----------
    outcome:
        Final pipeline outcome. One of:
        ``"FUNDED"`` | ``"DISPUTE_BLOCKED"`` | ``"AML_BLOCKED"`` |
        ``"BELOW_THRESHOLD"`` | ``"HALT"`` | ``"DECLINED"`` | ``"PENDING_HUMAN_REVIEW"`` |
        ``"RETRY_BLOCKED"`` | ``"COMPLIANCE_HOLD"`` | ``"AML_CHECK_UNAVAILABLE"``

        ``"PENDING_HUMAN_REVIEW"`` — C7 human review gate triggered; payment is parked
        pending operator decision. ``override_request_id`` is populated. Caller must store
        the original event keyed by ``override_request_id`` and re-submit via
        ``pipeline.process(event, human_override_decision="APPROVE")`` after approval (EPG-26).

        ``"COMPLIANCE_HOLD"`` — C7 detected an active compliance/regulatory hold on this
        payment (rejection codes: RR04, AG01, LEGL). Distinct from ``"DECLINED"`` to support
        regulatory audit trail requirements (FATF R.18/R.20, SR 11-7). No loan offer generated.

        ``"AML_CHECK_UNAVAILABLE"`` — C6 AML gate returned None (unavailable / timed out).
        Fail-closed: treated as a hard block. No loan offer generated.
    uetr:
        Unique end-to-end transaction reference from the input event.
    failure_probability:
        C1 predicted failure probability in [0, 1].
    above_threshold:
        ``True`` when ``failure_probability > FAILURE_PROBABILITY_THRESHOLD`` (τ* = 0.152).
    shap_top20:
        Top-20 SHAP feature attributions from C1.
    dispute_class:
        C4 dispute classification result (e.g. ``"NOT_DISPUTE"``), or ``None`` if C4
        was not reached (below threshold).
    dispute_hard_block:
        ``True`` when C4 returned a hard-block class (DISPUTE_CONFIRMED / DISPUTE_POSSIBLE).
    aml_passed:
        ``True`` when C6 AML velocity check passed; ``None`` if C6 was not reached.
    aml_hard_block:
        ``True`` when C6 flagged a hard block (velocity cap exceeded).
    pd_estimate:
        C2 probability-of-default score in [0, 1], or ``None`` if C2 was not reached.
    fee_bps:
        Annualized fee in basis points (≥ 300 floor), or ``None`` if C2 not reached.
    tier:
        C2 borrower tier (1, 2, or 3), or ``None`` if C2 not reached.
    shap_values_c2:
        Per-feature SHAP contributions from C2, or empty list if not reached.
    loan_offer:
        Loan offer dict from C7 ExecutionAgent, or ``None`` if no offer was made.
    decision_entry_id:
        ID of the ``DecisionLogEntry`` written by C7, or ``None``.
    payment_state:
        Final payment state-machine state (string value of ``PaymentState``).
    loan_state:
        Final loan state-machine state (string value of ``LoanState``), or ``None``
        when no loan was created.
    payment_state_history:
        Ordered list of payment state transitions recorded during pipeline execution.
    component_latencies:
        Per-component wall-clock latency in milliseconds:
        ``{"c1": 20.3, "c2": 3.1, "c4": 2.5, "c6": 1.8, "c7": 0.5}``.
    total_latency_ms:
        End-to-end wall-clock latency in milliseconds.
    """

    # Core outcome
    outcome: str
    uetr: str

    # C1 output
    failure_probability: float
    above_threshold: bool
    shap_top20: List[dict] = field(default_factory=list)

    # C4 output
    dispute_class: Optional[str] = None
    dispute_hard_block: bool = False

    # C6 output
    aml_passed: Optional[bool] = None
    aml_hard_block: bool = False
    aml_anomaly_flagged: bool = False  # EPG-18: soft alert from C6 anomaly detector

    # Compliance hold (EPG-09/10)
    compliance_hold: bool = False  # True when C7 blocked on a compliance/regulatory hold

    # C2 output
    pd_estimate: Optional[float] = None
    fee_bps: Optional[int] = None
    tier: Optional[int] = None
    shap_values_c2: List[dict] = field(default_factory=list)

    # C7 output
    loan_offer: Optional[dict] = None
    decision_entry_id: Optional[str] = None
    # EPG-26: populated when outcome == "PENDING_HUMAN_REVIEW" — used by caller
    # to store context and re-enter the pipeline after human approval.
    override_request_id: Optional[str] = None

    # State machine states
    payment_state: Optional[str] = None
    loan_state: Optional[str] = None
    payment_state_history: List[str] = field(default_factory=list)

    # Latency
    component_latencies: Dict[str, float] = field(default_factory=dict)
    total_latency_ms: float = 0.0
