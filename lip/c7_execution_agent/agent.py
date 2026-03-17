"""
agent.py — C7 Bank-side execution orchestration (ELO).
Coordinates C1–C6 components. Zero outbound from C7 container.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import collections
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from lip.c2_pd_model.fee import compute_loan_fee, compute_tiered_fee_floor
from lip.c5_streaming.stress_regime_detector import StressRegimeDetector
from lip.c8_license_manager.license_token import LicenseeContext
from lip.common.borrower_registry import BorrowerRegistry
from lip.common.business_calendar import currency_to_jurisdiction
from lip.common.constants import (
    MIN_CASH_FEE_USD,
    MIN_LOAN_AMOUNT_CLASS_A_USD,
    MIN_LOAN_AMOUNT_CLASS_B_USD,
    MIN_LOAN_AMOUNT_CLASS_C_USD,
    MIN_LOAN_AMOUNT_USD,
)
from lip.common.fx_risk_policy import FXRiskConfig
from lip.common.governing_law import law_for_jurisdiction
from lip.common.known_entity_registry import KnownEntityRegistry

from .decision_log import DecisionLogEntryData, DecisionLogger
from .degraded_mode import DegradedModeManager
from .human_override import HumanOverrideInterface
from .kill_switch import KillSwitch
from .offer_delivery import OfferDeliveryService

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    high_risk_threshold: float = 0.8
    max_loan_amount: Decimal = field(default_factory=lambda: Decimal("10000000"))
    auto_approve_threshold: float = 0.95
    require_human_review_above_pd: float = 0.20
    borrower_registry: BorrowerRegistry = field(default_factory=BorrowerRegistry)


class _TPSLimiter:
    """Sliding-window TPS limiter (thread-safe).

    Records call timestamps in a deque and rejects calls when the count
    in the past 1-second window exceeds ``max_tps``.  0 means unlimited.
    """

    def __init__(self, max_tps: int = 0) -> None:
        self.max_tps = max_tps
        self._timestamps: collections.deque = collections.deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if the call is within the TPS budget."""
        if self.max_tps <= 0:
            return True
        now = time.monotonic()
        cutoff = now - 1.0
        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_tps:
                return False
            self._timestamps.append(now)
            return True


class ExecutionAgent:
    """Bank-side execution orchestrator (ELO).

    Parameters
    ----------
    licensee_id:
        BPI licensee identifier (from C8 ``LicenseeContext``).  Stamped on
        every ``DecisionLogEntry`` for multi-licensee audit traceability.
    max_tps:
        Maximum transactions per second permitted by the BPI license.
        0 = unlimited (default, for unlicensed test environments).
        When the limit is exceeded ``process_payment`` returns HALT with
        reason ``"tps_limit_exceeded"``.
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        decision_logger: DecisionLogger,
        human_override: HumanOverrideInterface,
        degraded_mode_manager: DegradedModeManager,
        config: Optional[ExecutionConfig] = None,
        licensee_id: str = "",
        max_tps: int = 0,
        aml_dollar_cap_usd: int = 1000000,
        aml_count_cap: int = 100,
        min_loan_amount_usd: int = 500000,
        licensee_context: Optional[LicenseeContext] = None,
        stress_detector: Optional[StressRegimeDetector] = None,
        offer_delivery: Optional[OfferDeliveryService] = None,
        known_entity_registry: Optional[KnownEntityRegistry] = None,
        fx_risk_config: Optional[FXRiskConfig] = None,
    ) -> None:
        self.kill_switch = kill_switch
        self.decision_logger = decision_logger
        self.human_override = human_override
        self.degraded_mode_manager = degraded_mode_manager
        self.config = config or ExecutionConfig()

        if licensee_context:
            self.licensee_id = licensee_context.licensee_id
            self.max_tps = licensee_context.max_tps
            self.aml_dollar_cap_usd = licensee_context.aml_dollar_cap_usd
            self.aml_count_cap = licensee_context.aml_count_cap
            self.min_loan_amount_usd = licensee_context.min_loan_amount_usd
        else:
            self.licensee_id = licensee_id
            self.max_tps = max_tps
            self.aml_dollar_cap_usd = aml_dollar_cap_usd
            self.aml_count_cap = aml_count_cap
            self.min_loan_amount_usd = min_loan_amount_usd

        self._tps_limiter = _TPSLimiter(max_tps=self.max_tps)
        self.stress_detector = stress_detector
        self.offer_delivery = offer_delivery
        self._known_entity_registry = known_entity_registry
        self._fx_risk_config = fx_risk_config

    # ── main processing entry point ──────────────────────────────────────────

    def process_payment(self, payment_context: dict) -> dict:
        """
        Orchestrate the execution decision for a payment.

        Returns dict with keys:
          status           — HALT | OFFER | DECLINE
          loan_offer       — dict or None
          decision_entry_id — str or None
          halt_reason      — str or None
        """
        uetr = payment_context.get("uetr", str(uuid.uuid4()))
        individual_payment_id = payment_context.get("individual_payment_id", "")

        # 0. License TPS cap guard (C8)
        if not self._tps_limiter.allow():
            logger.warning("TPS limit exceeded for licensee=%s uetr=%s", self.licensee_id, uetr)
            return {"status": "HALT", "loan_offer": None, "decision_entry_id": None, "halt_reason": "tps_limit_exceeded"}

        # 1. Kill-switch / KMS guard
        if self.kill_switch.should_halt_new_offers() or self.degraded_mode_manager.should_halt_new_offers():
            reason = "kill_switch_active" if self.kill_switch.is_active() else "kms_unavailable"
            logger.warning("Halting new offer for uetr=%s reason=%s", uetr, reason)
            return {"status": "HALT", "loan_offer": None, "decision_entry_id": None, "halt_reason": reason}

        # 1b. Borrower enrollment guard (GAP-03)
        # Semantics: empty registry = allow-all (dev/test default).
        # Populated registry = strict enrollment enforcement (production).
        sending_bic = payment_context.get("sending_bic", "")
        registry = self.config.borrower_registry
        if registry.list_enrolled() and not registry.is_enrolled(sending_bic):
            logger.warning("Borrower not enrolled: bic=%s uetr=%s", sending_bic, uetr)
            # Use BLOCK status for unenrolled borrowers as it's a policy-based hard gate
            failure_prob = float(payment_context.get("failure_probability", 0.0))
            pd_score = float(payment_context.get("pd_score", 0.0))
            fee_bps = int(payment_context.get("fee_bps", 300))
            loan_amount = Decimal(str(payment_context.get("loan_amount", "0")))
            dispute_class = str(payment_context.get("dispute_class", "NOT_DISPUTE"))
            aml_passed = bool(payment_context.get("aml_passed", True))

            entry_id = self._log_decision(
                uetr, individual_payment_id, "BLOCK",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
            return {
                "status": "BORROWER_NOT_ENROLLED",
                "loan_offer": None,
                "decision_entry_id": entry_id,
                "halt_reason": "borrower_not_enrolled"
            }

        failure_prob = float(payment_context.get("failure_probability", 0.0))
        pd_score = float(payment_context.get("pd_score", 0.0))
        fee_bps = int(payment_context.get("fee_bps", 300))
        loan_amount = Decimal(str(payment_context.get("loan_amount", "0")))
        dispute_class = str(payment_context.get("dispute_class", "NOT_DISPUTE"))
        aml_passed = bool(payment_context.get("aml_passed", True))

        # 2. AML / dispute block
        if not aml_passed:
            entry_id = self._log_decision(
                uetr, individual_payment_id, "BLOCK",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
                human_override=False,
            )
            return {"status": "BLOCK", "loan_offer": None, "decision_entry_id": entry_id, "halt_reason": "aml_blocked"}

        if dispute_class in ("DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE"):
            entry_id = self._log_decision(
                uetr, individual_payment_id, "BLOCK",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
                human_override=False,
            )
            return {"status": "BLOCK", "loan_offer": None, "decision_entry_id": entry_id, "halt_reason": "dispute_blocked"}

        # 3. Human review gate
        human_override_applied = False
        if self._requires_human_review(payment_context):
            pd_limit = self.config.require_human_review_above_pd
            corridor = payment_context.get("corridor", "UNKNOWN")
            is_stressed = self.stress_detector.is_stressed(corridor) if self.stress_detector else False

            review_reason = f"PD {pd_score:.3f} exceeds review threshold {pd_limit}"
            if is_stressed:
                review_reason = f"STRESS_REGIME detected in corridor {corridor}. Manual review mandatory."

            req = self.human_override.request_override(
                uetr=uetr,
                original_decision="OFFER",
                ai_confidence=failure_prob,
                reason=review_reason,
            )
            logger.info("Human review requested: %s - reason: %s", req.request_id, review_reason)
            # In production, this would block until a response arrives.
            # Here we return a PENDING status and let the caller poll.
            return {
                "status": "PENDING_HUMAN_REVIEW",
                "loan_offer": None,
                "decision_entry_id": None,
                "halt_reason": None,
                "override_request_id": req.request_id,
            }

        # 4. Decline low-probability payments
        if failure_prob < 0.10:
            entry_id = self._log_decision(
                uetr, individual_payment_id, "DECLINE",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
            return {"status": "DECLINE", "loan_offer": None, "decision_entry_id": entry_id, "halt_reason": None}

        # 4b. GAP-12: FX risk policy gate — block unsupported currencies before offer
        if self._fx_risk_config is not None:
            currency = payment_context.get("currency", self._fx_risk_config.bank_base_currency)
            if not self._fx_risk_config.is_supported(currency):
                logger.warning(
                    "Currency not supported by FX risk policy: currency=%s policy=%s uetr=%s",
                    currency,
                    self._fx_risk_config.policy.value,
                    uetr,
                )
                entry_id = self._log_decision(
                    uetr, individual_payment_id, "CURRENCY_NOT_SUPPORTED",
                    failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
                )
                return {
                    "status": "CURRENCY_NOT_SUPPORTED",
                    "loan_offer": None,
                    "decision_entry_id": entry_id,
                    "halt_reason": "currency_not_supported",
                }

        # 4c. Class-aware minimum loan amount gate (QUANT+NOVA, 2026-03-17)
        # Class A (3d): $1.5M — routing errors resolve in ~7h; sub-$1.5M yield
        #   is destroyed by early repayment and cannot absorb one default at EU LGD.
        # Class B (7d): $700K — compliance holds run near full term; breakeven ~$652K.
        # Class C (21d): $500K — liquidity/sanctions holds run to maturity; always economic.
        # Licensee C8 token can override via min_loan_amount_usd for edge cases.
        rejection_class = str(payment_context.get("rejection_class", "")).upper()
        _CLASS_MINIMUMS = {
            "CLASS_A": MIN_LOAN_AMOUNT_CLASS_A_USD,
            "CLASS_B": MIN_LOAN_AMOUNT_CLASS_B_USD,
            "CLASS_C": MIN_LOAN_AMOUNT_CLASS_C_USD,
        }
        class_floor = _CLASS_MINIMUMS.get(rejection_class, MIN_LOAN_AMOUNT_USD)
        # Licensee token override applies when it is stricter than the class floor
        licensee_floor = Decimal(str(self.min_loan_amount_usd))
        effective_loan_min = max(class_floor, licensee_floor)

        if loan_amount < effective_loan_min:
            logger.info(
                "Loan amount below class minimum: amount=%s min=%s class=%s uetr=%s",
                loan_amount, effective_loan_min, rejection_class, uetr,
            )
            entry_id = self._log_decision(
                uetr, individual_payment_id, "DECLINE",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
            return {
                "status": "BELOW_MIN_LOAN_AMOUNT",
                "loan_offer": None,
                "decision_entry_id": entry_id,
                "halt_reason": "below_min_loan_amount",
            }

        # 4d. Minimum cash fee gate — decline when projected revenue is uneconomic
        maturity_days_val = int(payment_context.get("maturity_days", 7))
        tiered_floor = compute_tiered_fee_floor(loan_amount)
        effective_bps = tiered_floor if tiered_floor > Decimal(str(fee_bps)) else Decimal(str(fee_bps))
        projected_fee = compute_loan_fee(loan_amount, effective_bps, maturity_days_val)
        if projected_fee < MIN_CASH_FEE_USD:
            logger.info(
                "Projected cash fee below minimum: fee=%s min=%s uetr=%s",
                projected_fee, MIN_CASH_FEE_USD, uetr,
            )
            entry_id = self._log_decision(
                uetr, individual_payment_id, "DECLINE",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
            return {
                "status": "BELOW_MIN_CASH_FEE",
                "loan_offer": None,
                "decision_entry_id": entry_id,
                "halt_reason": "below_min_cash_fee",
            }

        # 5. Build offer — returns None if GAP-17 amount mismatch detected
        offer = self._build_loan_offer(payment_context, pd_score, fee_bps)
        if offer is None:
            entry_id = self._log_decision(
                uetr, individual_payment_id, "LOAN_AMOUNT_MISMATCH",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
            return {
                "status": "LOAN_AMOUNT_MISMATCH",
                "loan_offer": None,
                "decision_entry_id": entry_id,
                "halt_reason": "loan_amount_mismatch",
            }

        delivery_id: Optional[str] = None
        if self.offer_delivery is not None:
            delivery = self.offer_delivery.deliver(offer)
            delivery_id = str(delivery.delivery_id)
            logger.info(
                "Offer delivery registered: offer_id=%s delivery_id=%s",
                offer["loan_id"],
                delivery_id,
            )
        entry_id = self._log_decision(
            uetr, individual_payment_id, "OFFER",
            failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            human_override=human_override_applied,
        )
        return {
            "status": "OFFER",
            "loan_offer": offer,
            "decision_entry_id": entry_id,
            "halt_reason": None,
            "delivery_id": delivery_id,
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_loan_offer(self, payment_context: dict, pd: float, fee_bps: int) -> Optional[dict]:
        # Defense-in-depth: enforce tiered fee floor even if C2 returns a lower value.
        # Primary enforcement is in C2 fee.py; this is the second gate.
        # Tiered floor: <$500K→500bps, $500K–$2M→400bps, ≥$2M→300bps (canonical floor).
        loan_amount = Decimal(str(payment_context.get("loan_amount", "0")))
        tiered_floor = int(compute_tiered_fee_floor(loan_amount))
        fee_bps = max(fee_bps, tiered_floor)

        # GAP-17: Validate that the loan amount equals the original payment
        # amount the receiver is owed. ±$0.01 tolerance covers FX rounding.
        original_amt = Decimal(str(payment_context.get("original_payment_amount_usd", loan_amount)))
        if abs(loan_amount - original_amt) > Decimal("0.01"):
            logger.error(
                "LOAN_AMOUNT_MISMATCH: loan_amount=%s original_payment_amount_usd=%s uetr=%s",
                loan_amount,
                original_amt,
                payment_context.get("uetr"),
            )
            return None

        capped = min(loan_amount, self.config.max_loan_amount)
        maturity_days = int(payment_context.get("maturity_days", 7))
        loan_id = str(uuid.uuid4())
        uetr = str(payment_context.get("uetr", ""))

        # GAP-06: Build SWIFT pacs.008 disbursement message so ELO can populate
        # EndToEndId and RmtInf/Ustrd on the outbound bridge credit transfer.
        from lip.common.swift_disbursement import build_disbursement_message
        swift_msg = build_disbursement_message(uetr, loan_id, capped)

        # GAP-10: Derive governing law from payment corridor currency (MRFA clause 4).
        loan_currency = payment_context.get("currency", "USD")
        governing_law = law_for_jurisdiction(currency_to_jurisdiction(loan_currency))

        return {
            "loan_id": loan_id,
            "uetr": uetr,
            "loan_amount": str(capped),
            "fee_bps": fee_bps,
            "maturity_days": maturity_days,
            "pd_score": pd,
            "offered_at": datetime.now(tz=timezone.utc).isoformat(),
            "expires_at": (datetime.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat(),
            "swift_disbursement_ref": swift_msg.end_to_end_id,
            "swift_remittance_info": swift_msg.remittance_info,
            "governing_law": governing_law,
            "loan_currency": loan_currency,
        }

    def _requires_human_review(self, payment_context: dict) -> bool:
        pd = float(payment_context.get("pd_score", 0.0))
        if pd > self.config.require_human_review_above_pd:
            return True

        corridor = payment_context.get("corridor", "UNKNOWN")
        if self.stress_detector and self.stress_detector.is_stressed(corridor):
            return True

        return False

    def _log_decision(
        self,
        uetr: str,
        individual_payment_id: str,
        decision_type: str,
        failure_probability: float,
        pd_score: float,
        fee_bps: int,
        loan_amount: Decimal,
        dispute_class: str,
        aml_passed: bool,
        human_override: bool = False,
    ) -> str:
        state = self.degraded_mode_manager.get_state_dict()
        entry = DecisionLogEntryData(
            entry_id=str(uuid.uuid4()),
            uetr=uetr,
            individual_payment_id=individual_payment_id,
            decision_type=decision_type,
            decision_timestamp=datetime.now(tz=timezone.utc).isoformat(),
            failure_probability=failure_probability,
            pd_score=pd_score,
            fee_bps=fee_bps,
            loan_amount=str(loan_amount),
            dispute_class=dispute_class,
            aml_passed=aml_passed,
            human_override=human_override,
            degraded_mode=state["degraded_mode"],
            gpu_fallback=state["gpu_fallback"],
            kms_unavailable_gap=state["kms_unavailable_gap"],
            licensee_id=self.licensee_id,
        )
        return self.decision_logger.log(entry)

    def get_status(self) -> dict:
        status = self.kill_switch.get_status()
        return {
            "kill_switch": status.kill_switch_state.value,
            "kms": status.kms_state.value,
            "degraded": self.degraded_mode_manager.is_degraded(),
            "pending_overrides": len(self.human_override.get_pending_overrides()),
        }
