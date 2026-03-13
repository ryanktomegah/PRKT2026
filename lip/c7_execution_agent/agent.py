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
        offer_delivery: Optional[OfferDeliveryService] = None,
    ) -> None:
        self.kill_switch = kill_switch
        self.decision_logger = decision_logger
        self.human_override = human_override
        self.degraded_mode_manager = degraded_mode_manager
        self.config = config or ExecutionConfig()
        self.licensee_id = licensee_id
        self._tps_limiter = _TPSLimiter(max_tps=max_tps)
        self.offer_delivery = offer_delivery

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
            req = self.human_override.request_override(
                uetr=uetr,
                original_decision="OFFER",
                ai_confidence=failure_prob,
                reason=f"PD {pd_score:.3f} exceeds review threshold {self.config.require_human_review_above_pd}",
            )
            logger.info("Human review requested: %s", req.request_id)
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

        # 5. Build offer and deliver to ELO treasury if delivery service is wired
        offer = self._build_loan_offer(payment_context, pd_score, fee_bps)
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

    def _build_loan_offer(self, payment_context: dict, pd: float, fee_bps: int) -> dict:
        loan_amount = Decimal(str(payment_context.get("loan_amount", "0")))
        capped = min(loan_amount, self.config.max_loan_amount)
        maturity_days = int(payment_context.get("maturity_days", 7))
        return {
            "loan_id": str(uuid.uuid4()),
            "uetr": payment_context.get("uetr"),
            "loan_amount": str(capped),
            "fee_bps": fee_bps,
            "maturity_days": maturity_days,
            "pd_score": pd,
            "offered_at": datetime.now(tz=timezone.utc).isoformat(),
            "expires_at": (datetime.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat(),
        }

    def _requires_human_review(self, payment_context: dict) -> bool:
        pd = float(payment_context.get("pd_score", 0.0))
        return pd > self.config.require_human_review_above_pd

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
