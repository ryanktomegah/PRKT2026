"""
pipeline.py — End-to-end LIP payment processing pipeline (Algorithm 1).
Architecture Spec v1.2 Section 3.

Algorithm 1: End-to-End Pipeline Processing Loop

For each payment event:
  1. C5 normalizes the raw event (done by caller; accepts NormalizedEvent)
  2. C1 extracts features + predicts failure_probability
  3. If failure_probability > threshold (τ* = 0.152):
     a. C4 checks for dispute (hard_block check)
     b. C6 checks AML velocity (hard_block check)
     c. C2 computes PD + fee_bps (annualized, 300bps floor)
     d. Decision Engine aggregates signals, generates LoanOffer
     e. C7 receives offer, applies kill switch / KMS checks
     f. If accepted: FUNDED state, C3 starts settlement monitoring
  4. Return PipelineResult with full audit trail

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, List, Optional

from lip.c3_repayment_engine.rejection_taxonomy import (
    RejectionClass,
    classify_rejection_code,
    is_dispute_block,
)
from lip.c3_repayment_engine.rejection_taxonomy import (
    maturity_days as get_maturity_days,
)
from lip.c3_repayment_engine.repayment_loop import ActiveLoan
from lip.c4_dispute_classifier.taxonomy import DisputeClass
from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.common.business_calendar import add_business_days, currency_to_jurisdiction
from lip.common.notification_service import NotificationEventType, NotificationService
from lip.common.redis_factory import create_redis_client
from lip.common.state_machines import (
    LoanState,
    LoanStateMachine,
    PaymentState,
    PaymentStateMachine,
)
from lip.common.uetr_tracker import UETRTracker
from lip.instrumentation import LatencyTracker
from lip.pipeline_result import PipelineResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAILURE_PROBABILITY_THRESHOLD: float = 0.152
"""τ* — Architecture Spec v1.2 Section 3 decision threshold.

NOTE (EPG-13/ARIA): τ* = 0.152 was optimised on the full C1 synthetic corpus,
which includes both bridgeable (Class A/B/C) and non-bridgeable (BLOCK) failure
events.  Optimisation on the bridgeable-only subset (enabled by the EPG-12/22
``is_bridgeable`` corpus label) is pending C1 retraining.  Until then, τ* is
conservatively biased: higher recall on the mixed population means some
non-bridgeable events pass the threshold gate and are later blocked by C7
taxonomy — the correct defence-in-depth sequence, but suboptimal in latency.
"""

_DISPUTE_BLOCK_CLASSES = frozenset({
    DisputeClass.DISPUTE_CONFIRMED.value,
    DisputeClass.DISPUTE_POSSIBLE.value,
    "DISPUTE_CONFIRMED",
    "DISPUTE_POSSIBLE",
})


# ---------------------------------------------------------------------------
# LIPPipeline
# ---------------------------------------------------------------------------

class LIPPipeline:
    """End-to-end LIP payment processing pipeline.

    All component dependencies are injected at construction time to enable
    testing with mock implementations.

    Parameters
    ----------
    c1_engine:
        Callable ``(payment_dict) -> dict`` matching the
        ``InferenceEngine.predict`` signature.  Must return at minimum:
        ``failure_probability``, ``above_threshold``, ``shap_top20``.
    c2_engine:
        Callable ``(payment_dict, borrower_dict) -> dict`` matching the
        ``PDInferenceEngine.predict`` signature.  Must return at minimum:
        ``pd_score``, ``fee_bps``, ``tier``, ``shap_values``.
    c4_classifier:
        ``DisputeClassifier`` instance.
    c6_checker:
        ``VelocityChecker`` instance.
    c7_agent:
        ``ExecutionAgent`` instance.
    c3_monitor:
        Optional ``SettlementMonitor`` instance.  When provided, funded loans
        are registered for settlement monitoring.
    stress_detector:
        Optional ``StressRegimeDetector`` instance for detecting corridor
        failure rate spikes.
    notification_service:
        Optional ``NotificationService`` instance.  When provided,
        ``COMPLIANCE_HOLD`` outcomes trigger a compliance-team notification
        (EPG-11).  If ``None``, no notification is sent.
    uetr_tracker:
        Optional ``UETRTracker`` instance for retry detection (GAP-04).
        If ``None``, a new local tracker is created.
    threshold:
        Decision threshold (default: ``FAILURE_PROBABILITY_THRESHOLD``).
    global_latency_tracker:
        Optional shared ``LatencyTracker`` for accumulating cross-call p50/p99
        statistics.
    """

    def __init__(
        self,
        c1_engine: Callable[[dict], dict],
        c2_engine: Callable[[dict, dict], dict],
        c4_classifier: Any,
        c6_checker: Any,
        c7_agent: Any,
        c3_monitor: Optional[Any] = None,
        stress_detector: Optional[Any] = None,
        notification_service: Optional[NotificationService] = None,
        uetr_tracker: Optional[UETRTracker] = None,
        threshold: float = FAILURE_PROBABILITY_THRESHOLD,
        global_latency_tracker: Optional[LatencyTracker] = None,
        corridor_rates: Optional[dict] = None,
        redis_client=None,
    ) -> None:
        self._c1 = c1_engine
        self._c2 = c2_engine
        self._c4 = c4_classifier
        self._c6 = c6_checker
        self._c7 = c7_agent
        self._c3 = c3_monitor
        self._stress_detector = stress_detector
        self._notification = notification_service
        self._uetr_tracker = uetr_tracker or UETRTracker()
        self.threshold = threshold
        self._global_tracker = global_latency_tracker
        # Per-corridor failure rates for C1 feature injection.
        # Keys: "EUR_USD", "GBP_USD", etc.  Values: failure_rate float.
        # Falls back to canonical midpoint (0.035) for unknown corridors.
        self._corridor_rates: dict = corridor_rates or {}
        # Redis client distributed to components that support it.
        # If not injected, attempt connection via REDIS_URL env var.
        # None = in-memory fallback (unit tests, local dev — no behavior change).
        self._redis_client = redis_client if redis_client is not None else create_redis_client()

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(
        self,
        event: NormalizedEvent,
        borrower: Optional[dict] = None,
        entity_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
        human_override_decision: Optional[str] = None,
    ) -> PipelineResult:
        """Run Algorithm 1 for a single payment event.

        Parameters
        ----------
        event:
            Normalized payment event (output of C5 EventNormalizer).
        borrower:
            Borrower-level data dict for C2 PD inference.  When ``None`` an
            empty dict is used (results in Tier-3 / thin-file treatment).
        entity_id:
            Entity identifier for C6 AML velocity check.  Defaults to
            ``event.sending_bic``.
        beneficiary_id:
            Beneficiary identifier for C6 AML velocity check.  Defaults to
            ``event.receiving_bic``.
        human_override_decision:
            When ``"APPROVE"``, signals that a human operator has reviewed this
            payment and approved proceeding.  C7 will skip the human review gate
            and continue to offer generation.  Used for pipeline re-entry after a
            ``PENDING_HUMAN_REVIEW`` outcome (EPG-26).

        Returns
        -------
        PipelineResult
            Full audit trail with component outputs, state machine states,
            and latency breakdown.
        """
        t_start = time.perf_counter()
        tracker = LatencyTracker()

        # --- GAP-04: Retry Detection ---------------------------------------
        if self._uetr_tracker.is_retry(event.uetr):
            logger.warning("Retry detected: uetr=%s - blocking to prevent double-funding", event.uetr)
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            return PipelineResult(
                outcome="RETRY_BLOCKED",
                uetr=event.uetr,
                failure_probability=0.0,
                above_threshold=False,
                total_latency_ms=total_ms,
            )

        # Fix (stress timing): Record corridor failure NOW — before C1/C7 — so the
        # stress detector's is_stressed() call inside C7 reflects this event.
        # Every non-retry event entering the pipeline is an underlying payment failure.
        if self._stress_detector:
            self._stress_detector.record_event(f"{event.currency}_USD", True)

        # Fix (early BLOCK): Short-circuit on FRAU / FRAD / DISP / DUPL rejection
        # codes before running C1. These are unconditional BLOCK codes — no ML needed.
        # Uses the same DISPUTE_BLOCKED outcome as the C4 path so callers see a
        # consistent API regardless of whether the block was caught early or via C4.
        if event.rejection_code and is_dispute_block(event.rejection_code):
            logger.warning(
                "Rejection code BLOCK: uetr=%s code=%s — skipping C1/C2/C7",
                event.uetr, event.rejection_code,
            )
            entry_id = self._log_block(event, 0.0, "dispute_blocked")
            self._uetr_tracker.record(event.uetr, "DISPUTE_BLOCKED")
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            return PipelineResult(
                outcome="DISPUTE_BLOCKED",
                uetr=event.uetr,
                failure_probability=0.0,
                above_threshold=False,
                dispute_hard_block=True,
                aml_passed=True,
                decision_entry_id=entry_id,
                payment_state=PaymentState.DISPUTE_BLOCKED.value,
                loan_state=LoanState.OFFER_PENDING.value,
                payment_state_history=[
                    PaymentState.MONITORING.value,
                    PaymentState.DISPUTE_BLOCKED.value,
                ],
                total_latency_ms=total_ms,
            )

        borrower = borrower or {}
        # EPG-28: composite (sending_bic, debtor_account) key so each end-customer
        # originator within a correspondent bank has its own velocity window.
        # Falls back to BIC-only when debtor_account is not available (non-SWIFT rails
        # or pacs.002 messages that don't carry DbtrAcct).
        if entity_id is None:
            entity_id = (
                f"{event.sending_bic}:{event.debtor_account}"
                if event.debtor_account
                else event.sending_bic
            )
        beneficiary_id = beneficiary_id or event.receiving_bic

        # Initialise state machines
        payment_sm = PaymentStateMachine()
        loan_sm = LoanStateMachine()
        state_history: List[str] = [payment_sm.current_state.value]

        def _record_payment_transition(new_state: PaymentState) -> None:
            payment_sm.transition(new_state)
            state_history.append(payment_sm.current_state.value)

        def _record_and_return(res: PipelineResult) -> PipelineResult:
            self._uetr_tracker.record(res.uetr, res.outcome)
            self._record_global(tracker, res.total_latency_ms)
            return res

        # --- Step 1: C1 inference -------------------------------------------
        payment_dict = self._event_to_payment_dict(event)
        with tracker.measure("c1"):
            c1_result = self._c1.predict(payment_dict) if hasattr(self._c1, "predict") else self._c1(payment_dict)

        failure_probability = float(c1_result["failure_probability"])
        above_threshold = failure_probability > self.threshold
        shap_top20 = c1_result.get("shap_top20", [])

        if not above_threshold:
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="BELOW_THRESHOLD",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=False,
                shap_top20=shap_top20,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # Transition: MONITORING → FAILURE_DETECTED
        _record_payment_transition(PaymentState.FAILURE_DETECTED)

        # --- Step 2: C4 + C6 in parallel -----------------------------------
        c4_result: dict = {}
        c6_result: Any = None

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_c4 = executor.submit(self._run_c4, event, tracker)
            f_c6 = executor.submit(self._run_c6, event, entity_id, beneficiary_id, tracker)
            c4_result = f_c4.result()
            c6_result = f_c6.result()

        # Extract dispute class
        dispute_class_raw = c4_result.get("dispute_class", DisputeClass.NOT_DISPUTE)
        dispute_class_str = (
            dispute_class_raw.value
            if hasattr(dispute_class_raw, "value")
            else str(dispute_class_raw)
        )
        dispute_hard_block = dispute_class_str in _DISPUTE_BLOCK_CLASSES

        # Extract AML result — fail-closed (EPG-27: was fail-open `else True` before fix)
        if c6_result is None:
            logger.error(
                "C6 AML check unavailable (returned None) — blocking payment uetr=%s",
                event.uetr,
            )
            entry_id = self._log_block(event, failure_probability, "aml_check_unavailable")
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="AML_CHECK_UNAVAILABLE",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=None,
                aml_hard_block=True,
                decision_entry_id=entry_id,
                payment_state=PaymentState.AML_BLOCKED.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history + [PaymentState.AML_BLOCKED.value],
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)
        aml_passed = bool(c6_result.passed)
        aml_hard_block = not aml_passed
        # EPG-18: extract anomaly soft flag (does not block — routes to human review)
        aml_anomaly_flagged = bool(getattr(c6_result, "anomaly_flagged", False)) if c6_result is not None else False
        anomaly_flagged = aml_anomaly_flagged  # alias used by C7 payment_context key

        # --- C4 hard block check -------------------------------------------
        if dispute_hard_block:
            _record_payment_transition(PaymentState.DISPUTE_BLOCKED)
            # Write a BLOCK decision log entry
            entry_id = self._log_block(event, failure_probability, "dispute_blocked")
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="DISPUTE_BLOCKED",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                dispute_hard_block=True,
                aml_passed=aml_passed,
                aml_hard_block=aml_hard_block,
                decision_entry_id=entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- C6 hard block check -------------------------------------------
        if aml_hard_block:
            _record_payment_transition(PaymentState.AML_BLOCKED)
            entry_id = self._log_block(event, failure_probability, "aml_blocked")
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="AML_BLOCKED",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                dispute_hard_block=False,
                aml_passed=False,
                aml_hard_block=True,
                decision_entry_id=entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- EPG-18: C6 anomaly gate (EU AI Act Art.14 human oversight) -----------
        # Anomaly flag is a soft advisory — does NOT trigger aml_hard_block.
        # EU AI Act Art.14 requires a human in the loop when an automated system
        # flags anomalous risk patterns. Route to PENDING_HUMAN_REVIEW instead of
        # making an autonomous FUNDED decision.
        if aml_anomaly_flagged:
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="PENDING_HUMAN_REVIEW",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=True,
                aml_anomaly_flagged=True,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- Step 3: C2 PD inference ---------------------------------------
        with tracker.measure("c2"):
            c2_result = (
                self._c2.predict(payment_dict, borrower)
                if hasattr(self._c2, "predict")
                else self._c2(payment_dict, borrower)
            )

        pd_estimate = float(c2_result["pd_score"])
        fee_bps = int(c2_result["fee_bps"])
        tier = int(c2_result.get("tier", 3))
        shap_values_c2 = c2_result.get("shap_values", [])

        # Determine maturity_days and rejection_class from rejection code
        maturity = self._derive_maturity_days(event.rejection_code)
        rejection_class_str = self._derive_rejection_class(event.rejection_code)

        # --- Step 5: C7 Execution decision (OFFER / DECLINE / BLOCK) -------
        payment_context = {
            "uetr": event.uetr,
            "individual_payment_id": event.individual_payment_id,
            "sending_bic": event.sending_bic,
            "failure_probability": failure_probability,
            "pd_score": pd_estimate,
            "fee_bps": fee_bps,
            "loan_amount": event.amount,
            # GAP-17: propagate the authoritative settlement amount so C7 can
            # validate the loan offer equals what the receiver is owed.
            # Falls back to event.amount when not present (same-currency rails).
            "original_payment_amount_usd": str(
                event.original_payment_amount_usd if event.original_payment_amount_usd is not None
                else event.amount
            ),
            "dispute_class": dispute_class_str,
            "aml_passed": aml_passed,
            "maturity_days": maturity,
            "rejection_code": event.rejection_code,
            "rejection_class": rejection_class_str,
            "corridor": f"{event.currency}_USD",
            # GAP-10/GAP-12: propagate currency so C7 can derive governing law
            # and apply FX risk policy checks.
            "currency": event.currency,
            # EPG-18: anomaly flag propagated for audit trail
            "aml_anomaly_flagged": aml_anomaly_flagged,
            # EPG-26: propagate human override decision for re-entry after review
            "human_override_decision": human_override_decision,
            # EPG-18: propagate C6 anomaly flag so C7 can route to human review
            "anomaly_flagged": anomaly_flagged,
        }

        with tracker.measure("c7"):
            c7_result = self._c7.process_payment(payment_context)

        c7_status = c7_result["status"]
        loan_offer = c7_result.get("loan_offer")
        decision_entry_id = c7_result.get("decision_entry_id")

        # --- Handle C7 COMPLIANCE_HOLD (EPG-09/10) -------------------------
        # Distinct from DECLINED: compliance/regulatory/legal holds have their own
        # audit obligation (FATF R.18/R.20, EU AMLD6 Art.10). Callers must be able
        # to distinguish a compliance hold from an economic decline in the audit trail.
        if c7_status == "COMPLIANCE_HOLD_BLOCKS_BRIDGE":
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="COMPLIANCE_HOLD",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=aml_passed,
                pd_estimate=pd_estimate,
                fee_bps=fee_bps,
                tier=tier,
                compliance_hold=True,
                decision_entry_id=decision_entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- Handle C7 HALT (kill switch / KMS) ----------------------------
        if c7_status == "HALT":
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="HALT",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=aml_passed,
                pd_estimate=pd_estimate,
                fee_bps=fee_bps,
                tier=tier,
                decision_entry_id=decision_entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- Handle C7 compliance hold block — distinct outcome for audit trail (EPG-09/10)
        if c7_status == "COMPLIANCE_HOLD_BLOCKS_BRIDGE":
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="COMPLIANCE_HOLD",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=aml_passed,
                pd_estimate=pd_estimate,
                fee_bps=fee_bps,
                tier=tier,
                shap_values_c2=shap_values_c2,
                loan_offer=None,
                decision_entry_id=decision_entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            # EPG-11: notify compliance team whenever a compliance hold blocks a bridge.
            if self._notification is not None:
                self._notification.notify(
                    NotificationEventType.COMPLIANCE_HOLD,
                    uetr=event.uetr,
                    payload={
                        "sending_bic": event.sending_bic,
                        "rejection_code": event.rejection_code,
                        "rejection_class": payment_context.get("rejection_class"),
                        "decision_entry_id": decision_entry_id,
                    },
                )
            return _record_and_return(result)

        # --- Handle C7 human review pending — park, not decline (EPG-26) ----
        if c7_status == "PENDING_HUMAN_REVIEW":
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="PENDING_HUMAN_REVIEW",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=aml_passed,
                pd_estimate=pd_estimate,
                fee_bps=fee_bps,
                tier=tier,
                shap_values_c2=shap_values_c2,
                loan_offer=None,
                decision_entry_id=decision_entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
                override_request_id=c7_result.get("override_request_id"),
            )
            return _record_and_return(result)

        # --- Handle C7 DECLINE / economic declines --------------------------
        if c7_status in (
            "DECLINE", "BLOCK",
            "CURRENCY_NOT_SUPPORTED", "BORROWER_NOT_ENROLLED",
            "BELOW_MIN_LOAN_AMOUNT",   # EPG-10: was falling through to FUNDED
            "BELOW_MIN_CASH_FEE",      # EPG-10: was falling through to FUNDED
            "LOAN_AMOUNT_MISMATCH",    # EPG-10: was falling through to FUNDED
        ):
            total_ms = (time.perf_counter() - t_start) * 1_000.0
            result = PipelineResult(
                outcome="DECLINED",
                uetr=event.uetr,
                failure_probability=failure_probability,
                above_threshold=True,
                shap_top20=shap_top20,
                dispute_class=dispute_class_str,
                aml_passed=aml_passed,
                pd_estimate=pd_estimate,
                fee_bps=fee_bps,
                tier=tier,
                shap_values_c2=shap_values_c2,
                loan_offer=None,
                decision_entry_id=decision_entry_id,
                payment_state=payment_sm.current_state.value,
                loan_state=loan_sm.current_state.value,
                payment_state_history=state_history,
                component_latencies=tracker.get_latest_all(),
                total_latency_ms=total_ms,
            )
            return _record_and_return(result)

        # --- OFFER accepted → FUNDED --------------------------------------
        # Transition: FAILURE_DETECTED → BRIDGE_OFFERED → FUNDED
        _record_payment_transition(PaymentState.BRIDGE_OFFERED)
        _record_payment_transition(PaymentState.FUNDED)

        # Transition loan state machine: OFFER_PENDING → ACTIVE
        loan_sm.transition(LoanState.ACTIVE)

        # GAP-02: Record the transaction in C6 after funding confirmed
        with tracker.measure("c6_record"):
            dollar_cap = None
            count_cap = None
            if hasattr(self._c7, "aml_dollar_cap_usd"):
                dollar_cap = Decimal(str(self._c7.aml_dollar_cap_usd))
            if hasattr(self._c7, "aml_count_cap"):
                count_cap = self._c7.aml_count_cap

            self._c6.record(
                entity_id, event.amount, beneficiary_id,
                dollar_cap_override=dollar_cap,
                count_cap_override=count_cap
            )

        # Register with C3 settlement monitor
        if self._c3 is not None and loan_offer is not None:
            self._register_with_c3(event, loan_offer, maturity)

        total_ms = (time.perf_counter() - t_start) * 1_000.0

        result = PipelineResult(
            outcome="FUNDED",
            uetr=event.uetr,
            failure_probability=failure_probability,
            above_threshold=True,
            shap_top20=shap_top20,
            dispute_class=dispute_class_str,
            dispute_hard_block=False,
            aml_passed=aml_passed,
            aml_hard_block=False,
            pd_estimate=pd_estimate,
            fee_bps=fee_bps,
            tier=tier,
            shap_values_c2=shap_values_c2,
            loan_offer=loan_offer,
            decision_entry_id=decision_entry_id,
            payment_state=payment_sm.current_state.value,
            loan_state=loan_sm.current_state.value,
            payment_state_history=state_history,
            component_latencies=tracker.get_latest_all(),
            total_latency_ms=total_ms,
        )
        return _record_and_return(result)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _run_c4(self, event: NormalizedEvent, tracker: LatencyTracker) -> dict:
        """Run C4 dispute classification in a thread, wrapped in latency tracking.

        Extracts the fields required by ``DisputeClassifier.classify`` from
        the normalised event and records wall-clock time under the ``'c4'``
        label.

        Args:
            event: :class:`~lip.c5_streaming.event_normalizer.NormalizedEvent`
                for the current payment.
            tracker: Per-call :class:`~lip.instrumentation.LatencyTracker` to
                record the C4 wall-clock duration.

        Returns:
            Raw dict returned by ``DisputeClassifier.classify``, containing
            at minimum a ``dispute_class`` key.
        """
        with tracker.measure("c4"):
            return self._c4.classify(
                rejection_code=event.rejection_code,
                narrative=event.narrative,
                amount=str(event.amount),
                currency=event.currency,
                counterparty=event.sending_bic,
            )

    def _run_c6(
        self,
        event: NormalizedEvent,
        entity_id: str,
        beneficiary_id: str,
        tracker: LatencyTracker,
    ):
        """Run C6 AML combined gate (sanctions → velocity → anomaly) in a thread.

        Accepts both AMLChecker (preferred) and legacy VelocityChecker instances.
        The result must expose a ``passed`` attribute.

        Args:
            event: :class:`~lip.c5_streaming.event_normalizer.NormalizedEvent`
                for the current payment.
            entity_id: Raw entity identifier for the velocity check
                (hashed internally by C6).
            beneficiary_id: Raw beneficiary identifier for the velocity check
                (hashed internally by C6).
            tracker: Per-call :class:`~lip.instrumentation.LatencyTracker` to
                record the C6 wall-clock duration.

        Returns:
            AML check result object exposing a ``passed: bool`` attribute.
            If ``None`` is returned, the pipeline treats it as ``AML_CHECK_UNAVAILABLE``
            and blocks the payment (fail-closed). Do not return ``None`` to mean "pass".
        """
        dollar_cap = None
        count_cap = None
        if hasattr(self._c7, "aml_dollar_cap_usd"):
            dollar_cap = Decimal(str(self._c7.aml_dollar_cap_usd))
        if hasattr(self._c7, "aml_count_cap"):
            count_cap = self._c7.aml_count_cap

        with tracker.measure("c6"):
            return self._c6.check(
                entity_id, event.amount, beneficiary_id,
                dollar_cap_override=dollar_cap,
                count_cap_override=count_cap,
            )

    def _log_block(
        self,
        event: NormalizedEvent,
        failure_probability: float,
        block_reason: str,
    ) -> Optional[str]:
        """Ask C7 to write a BLOCK decision log entry for audit trail purposes.

        Called when a payment is hard-blocked by C4 (dispute) or C6 (AML)
        before C2 or C7 are invoked.  Failures are swallowed and logged
        to avoid disrupting the pipeline result.

        Args:
            event: The normalised payment event being blocked.
            failure_probability: C1 failure probability score for the event.
            block_reason: Short string identifying the block cause —
                ``'dispute_blocked'`` or ``'aml_blocked'``.

        Returns:
            The ``decision_entry_id`` string from C7, or ``None`` when C7
            raises an exception.
        """
        try:
            ctx = {
                "uetr": event.uetr,
                "individual_payment_id": event.individual_payment_id,
                "failure_probability": failure_probability,
                "pd_score": 0.0,
                "fee_bps": 0,
                "loan_amount": str(event.amount),
                "dispute_class": (
                    "DISPUTE_CONFIRMED" if block_reason == "dispute_blocked" else "NOT_DISPUTE"
                ),
                "aml_passed": block_reason != "aml_blocked",
                "maturity_days": 0,
            }
            result = self._c7.process_payment(ctx)
            return result.get("decision_entry_id")
        except Exception:
            logger.exception("Failed to log BLOCK decision for uetr=%s", event.uetr)
            return None

    def _derive_maturity_days(self, rejection_code: Optional[str]) -> int:
        """Derive bridge-loan maturity days from the ISO 20022 rejection code.

        Delegates to ``classify_rejection_code`` and then ``get_maturity_days``
        from the C3 rejection taxonomy.  Defaults to 7 days (Class B) when the
        rejection code is absent, unrecognised, or maps to a zero-day window.

        Args:
            rejection_code: ISO 20022 rejection / return reason code, or
                ``None`` when the payment event carries no rejection code.

        Returns:
            Maturity window in calendar days: 3 (Class A), 7 (Class B),
            or 21 (Class C).  Always ≥ 1.
        """
        if not rejection_code:
            return 7
        try:
            cls = classify_rejection_code(rejection_code)
            days = get_maturity_days(cls)
            return days if days > 0 else 7
        except ValueError:
            return 7

    def _derive_rejection_class(self, rejection_code: Optional[str]) -> str:
        """Derive the rejection class string from the ISO 20022 rejection code.

        Returns the RejectionClass enum value as a string (e.g. "CLASS_A"),
        or "CLASS_B" as the safe default when the code is absent or unrecognised.

        Args:
            rejection_code: ISO 20022 rejection code, or None.

        Returns:
            Rejection class string: "CLASS_A", "CLASS_B", "CLASS_C", or "BLOCK".
        """
        if not rejection_code:
            return "CLASS_B"
        try:
            cls = classify_rejection_code(rejection_code)
            return cls.value
        except ValueError:
            return "CLASS_B"

    def _register_with_c3(
        self,
        event: NormalizedEvent,
        loan_offer: dict,
        maturity_days: int,
    ) -> None:
        """Register the funded loan with C3 settlement monitor.

        Creates an :class:`~lip.c3_repayment_engine.repayment_loop.ActiveLoan`
        from the event and offer fields and calls
        ``SettlementMonitor.register_loan``.  Exceptions are swallowed and
        logged to avoid disrupting the ``FUNDED`` pipeline result.

        Args:
            event: The normalised payment event for the funded payment.
            loan_offer: Dict returned by C7 containing at minimum
                ``loan_id`` and ``fee_bps``.
            maturity_days: Loan maturity window in calendar days derived
                from the rejection code class.
        """
        try:
            now_utc = datetime.now(tz=timezone.utc)
            # GAP-09: Use business days for maturity so weekend failures
            # don't expire before SWIFT settlement can be attempted.
            jurisdiction = currency_to_jurisdiction(event.currency)
            maturity_date = datetime.combine(
                add_business_days(now_utc.date(), maturity_days, jurisdiction),
                now_utc.time(),
                tzinfo=timezone.utc,
            )
            # Derive rejection class from the event's rejection code
            try:
                rej_class = classify_rejection_code(event.rejection_code).value if event.rejection_code else RejectionClass.CLASS_B.value
            except ValueError:
                rej_class = RejectionClass.CLASS_B.value
            loan = ActiveLoan(
                loan_id=loan_offer.get("loan_id", event.uetr),
                uetr=event.uetr,
                individual_payment_id=event.individual_payment_id,
                principal=Decimal(str(event.amount)),
                fee_bps=loan_offer.get("fee_bps", 300),
                maturity_date=maturity_date,
                rejection_class=rej_class,
                corridor=f"{event.currency}_USD",
                funded_at=now_utc,
                licensee_id=getattr(self._c7, "licensee_id", ""),
                deployment_phase=loan_offer.get("deployment_phase", "LICENSOR"),
            )
            self._c3.register_loan(loan)
            logger.info(
                "Loan registered with C3: loan_id=%s uetr=%s maturity=%s",
                loan.loan_id,
                loan.uetr,
                maturity_date.isoformat(),
            )
        except Exception:
            logger.exception("Failed to register loan with C3 for uetr=%s", event.uetr)

    def _event_to_payment_dict(self, event: NormalizedEvent) -> dict:
        """Convert a NormalizedEvent to the payment dict expected by C1/C2.

        ``corridor_stats`` is populated from the per-corridor failure rates
        supplied at construction time (``corridor_rates`` kwarg), falling back
        to the canonical midpoint (3.5%) from ``canonical_numbers.yaml`` for
        unknown corridors.  ``sender_stats`` and ``receiver_stats`` are empty
        dicts — features.py handles missing keys with defaults.

        Args:
            event: :class:`~lip.c5_streaming.event_normalizer.NormalizedEvent`
                to convert.

        Returns:
            Dict with keys: ``amount_usd``, ``currency_pair``,
            ``sending_bic``, ``receiving_bic``, ``timestamp``,
            ``corridor_stats``, ``sender_stats``, ``receiver_stats``,
            ``uetr``, ``rejection_code``, ``narrative``.
        """
        corridor_key = f"{event.currency}_USD"
        rate = self._corridor_rates.get(corridor_key, 0.035)
        return {
            "amount_usd": float(event.amount),
            "currency_pair": corridor_key,
            "sending_bic": event.sending_bic,
            "receiving_bic": event.receiving_bic,
            "timestamp": event.timestamp.isoformat(),
            "corridor_stats": {
                "failure_rate_7d": rate,
                "failure_rate_30d": rate,
            },
            "sender_stats": {},
            "receiver_stats": {},
            "uetr": event.uetr,
            "rejection_code": event.rejection_code,
            "narrative": event.narrative,
        }

    def _record_global(self, tracker: LatencyTracker, total_ms: float) -> None:
        """Forward the latest component latencies to the global tracker (if set).

        Allows a shared :class:`~lip.instrumentation.LatencyTracker` to
        accumulate cross-call P50/P99 statistics for the Prometheus metrics
        collector.  No-op when ``global_latency_tracker`` was not provided
        at construction time.

        Args:
            tracker: Per-call tracker holding this call's component latencies.
            total_ms: End-to-end wall-clock time for this pipeline invocation
                in milliseconds.
        """
        if self._global_tracker is None:
            return
        for component, latency in tracker.get_latest_all().items():
            self._global_tracker.record(component, latency)
        self._global_tracker.record("total", total_ms)
