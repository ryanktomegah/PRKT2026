"""
repayment_loop.py — Settlement monitoring and auto-repayment trigger logic
Architecture Spec S2.3: Dual-signal repayment

Idempotency (Architecture Spec S11.2):
  Redis SETNX ensures exactly one RepaymentInstruction per UETR across
  distributed Flink instances.  Key: ``lip:repaid:{uetr}``
  TTL: maturity_days + 45 days.
  Falls back to an in-memory set when Redis is unavailable.
"""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Callable, Dict, List, Optional

from lip.c2_pd_model.fee import compute_loan_fee, compute_platform_royalty
from lip.common.deployment_phase import DeploymentPhase, get_phase_config
from lip.common.partial_settlement import PartialSettlementPolicy

from .rejection_taxonomy import RejectionClass
from .settlement_handlers import SettlementHandlerRegistry, SettlementRail

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Domain types ───────────────────────────────────────────────────────────────

@dataclass
class ActiveLoan:
    """Represents a live loan position tracked by the repayment engine.

    Attributes:
        loan_id: Unique loan identifier within the LIP system.
        uetr: SWIFT Unique End-to-end Transaction Reference (UUID format).
        individual_payment_id: Payment-leg identifier (e.g. RTP EndToEndId).
        principal: Loan principal in the settlement currency.
        fee_bps: Fee in basis points charged by the MLO/MIPLO.
        maturity_date: Absolute UTC datetime after which buffer repayment triggers.
        rejection_class: String representation of the RejectionClass that sized the
                         maturity window (e.g. ``"CLASS_A"``).
        corridor: Corridor key used for buffer P95 estimation, e.g. ``"USD_EUR"``.
        funded_at: UTC datetime when the loan was funded.
    """

    loan_id: str
    uetr: str
    individual_payment_id: str
    principal: Decimal
    fee_bps: int
    maturity_date: datetime
    rejection_class: str
    corridor: str
    funded_at: datetime
    licensee_id: str = ""
    deployment_phase: str = "LICENSOR"


class RepaymentTrigger(str, Enum):
    SETTLEMENT_CONFIRMED = "SETTLEMENT_CONFIRMED"
    MATURITY_REACHED = "MATURITY_REACHED"
    BUFFER_SETTLEMENT = "BUFFER_SETTLEMENT"
    MANUAL = "MANUAL"


# ── Settlement monitor ────────────────────────────────────────────────────────

class SettlementMonitor:
    """Processes incoming settlement signals and matches them to active loans.

    Responsibilities:
      - Accept raw settlement messages from any of the 5 supported rails.
      - Dispatch to the correct handler via SettlementHandlerRegistry.
      - Resolve the UETR via UETRMappingTable for RTP EndToEndId messages.
      - Match the resolved signal against the active loan registry.
      - Return a repayment trigger dict when a match is found.
    """

    def __init__(
        self,
        handler_registry: SettlementHandlerRegistry,
        uetr_mapping,
        corridor_buffer,
    ) -> None:
        self._registry = handler_registry
        self._uetr_mapping = uetr_mapping
        self._corridor_buffer = corridor_buffer
        self._active_loans: Dict[str, ActiveLoan] = {}  # keyed by uetr
        self._lock = threading.Lock()

    def register_loan(self, loan: ActiveLoan) -> None:
        """Add a loan to the monitor's active loan registry."""
        with self._lock:
            self._active_loans[loan.uetr] = loan
            logger.info(
                "Loan registered: loan_id=%s uetr=%s maturity=%s",
                loan.loan_id, loan.uetr, loan.maturity_date.isoformat(),
            )

    def deregister_loan(self, uetr: str) -> Optional[ActiveLoan]:
        """Remove and return a loan from the active registry."""
        with self._lock:
            loan = self._active_loans.pop(uetr, None)
            if loan:
                logger.info("Loan deregistered: uetr=%s loan_id=%s", uetr, loan.loan_id)
            return loan

    def process_signal(self, rail: str, raw_message: dict) -> Optional[dict]:
        """Process an incoming settlement signal for a given rail.

        Steps:
          1. Dispatch the raw message to the appropriate handler.
          2. For RTP, resolve EndToEndId → UETR via the mapping table.
          3. Match the UETR against the active loan registry.
          4. Return a repayment trigger dict, or None if no match.

        Args:
            rail: String name of the settlement rail (e.g. ``"SWIFT"``).
            raw_message: Rail-specific raw message payload.

        Returns:
            A repayment trigger dict with keys ``loan_id``, ``uetr``,
            ``trigger``, ``settlement_amount``, ``signal_rail``, and
            ``triggered_at``; or None if no matching loan was found.
        """
        try:
            settlement_rail = SettlementRail(rail.upper())
        except ValueError:
            logger.error("Unknown settlement rail: %s", rail)
            return None

        try:
            signal = self._registry.dispatch(settlement_rail, raw_message)
        except Exception as exc:
            logger.exception("Handler dispatch failed for rail %s: %s", rail, exc)
            return None

        # For RTP, the UETR may need to be resolved from the EndToEndId.
        uetr = signal.uetr
        if settlement_rail is SettlementRail.RTP and not uetr:
            uetr = self._uetr_mapping.lookup(signal.individual_payment_id) or ""
            logger.debug(
                "RTP UETR resolution: EndToEndId=%s → uetr=%s",
                signal.individual_payment_id, uetr,
            )

        loan = self.match_loan(uetr)
        if loan is None:
            logger.debug(
                "No active loan matched for uetr=%s rail=%s", uetr, rail
            )
            return None

        logger.info(
            "Settlement matched: loan_id=%s uetr=%s rail=%s amount=%s %s",
            loan.loan_id, uetr, rail, signal.amount, signal.currency,
        )
        return {
            "loan_id": loan.loan_id,
            "uetr": uetr,
            "trigger": RepaymentTrigger.SETTLEMENT_CONFIRMED,
            "settlement_amount": signal.amount,
            "signal_rail": rail,
            "rejection_code": signal.rejection_code,
            "triggered_at": _utcnow().isoformat(),
        }

    def match_loan(self, uetr: str) -> Optional[ActiveLoan]:
        """Return the ActiveLoan matching the given UETR, or None."""
        with self._lock:
            return self._active_loans.get(uetr)

    def get_active_loans(self) -> List[ActiveLoan]:
        """Return a snapshot of all currently active loans."""
        with self._lock:
            return list(self._active_loans.values())


# ── Repayment loop ────────────────────────────────────────────────────────────

_REDIS_REPAID_PREFIX = "lip:repaid:"
_REDIS_REPAID_TTL_EXTRA_DAYS = 45  # TTL buffer beyond maturity_days


class RepaymentLoop:
    """Orchestrates settlement monitoring and maturity-based repayment triggers.

    The loop maintains the active loan registry, delegates settlement signal
    processing to SettlementMonitor, and periodically checks for maturity
    breaches that require buffer repayment.

    Architecture Spec S2.3: Dual-signal repayment:
      Signal 1 — Settlement confirmed on the external rail (SWIFT/FedNow/RTP/SEPA).
      Signal 2 — Maturity timer elapsed → buffer settlement triggered.

    Idempotency (Architecture Spec S11.2):
      When ``redis_client`` is provided, a Redis SETNX claim is placed on
      ``lip:repaid:{uetr}`` before any repayment is processed.  A second
      signal for the same UETR will find the key already set and be dropped.
      Without Redis, an in-memory set provides single-process idempotency.
    """

    def __init__(
        self,
        monitor: SettlementMonitor,
        repayment_callback: Callable[[dict], None],
        redis_client=None,
        partial_settlement_policy: Optional[PartialSettlementPolicy] = None,
    ) -> None:
        self._monitor = monitor
        self._callback = repayment_callback
        self._redis = redis_client
        self._partial_settlement_policy = partial_settlement_policy
        self._active_loans: Dict[str, ActiveLoan] = {}  # loan_id → ActiveLoan
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # In-memory idempotency fallback (single-process only)
        self._repaid_uetrs: set = set()

    # ── Loan lifecycle ────────────────────────────────────────────────────────

    def register_loan(self, loan: ActiveLoan) -> None:
        """Add a loan to both the repayment loop and the settlement monitor."""
        with self._lock:
            self._active_loans[loan.loan_id] = loan
        self._monitor.register_loan(loan)
        logger.info(
            "RepaymentLoop: loan registered loan_id=%s uetr=%s", loan.loan_id, loan.uetr
        )

    def _deregister_loan(self, loan_id: str) -> Optional[ActiveLoan]:
        with self._lock:
            loan = self._active_loans.pop(loan_id, None)
        if loan:
            self._monitor.deregister_loan(loan.uetr)
        return loan

    def get_active_loans(self) -> List[ActiveLoan]:
        """Return a snapshot of all currently active loans (keyed by loan_id)."""
        with self._lock:
            return list(self._active_loans.values())

    # ── Repayment dispatch ────────────────────────────────────────────────────

    def _claim_repayment(self, uetr: str, maturity_days: int) -> bool:
        """Attempt to claim exclusive repayment rights for a UETR.

        Returns True if the claim succeeded (this instance should process the
        repayment).  Returns False if another instance already claimed it.

        Uses Redis SETNX when available; falls back to an in-memory set for
        single-process deployments.

        TTL = maturity_days + _REDIS_REPAID_TTL_EXTRA_DAYS (days).
        """
        if self._redis is not None:
            try:
                key = f"{_REDIS_REPAID_PREFIX}{uetr}"
                ttl_seconds = (maturity_days + _REDIS_REPAID_TTL_EXTRA_DAYS) * 86_400
                result = self._redis.set(key, "1", nx=True, ex=ttl_seconds)
                if result is None:
                    logger.info(
                        "Idempotency: repayment already claimed in Redis for uetr=%s — skipping",
                        uetr,
                    )
                    return False
                logger.debug("Idempotency: Redis claim acquired for uetr=%s", uetr)
                return True
            except Exception as exc:
                logger.warning(
                    "Redis SETNX failed for uetr=%s (%s); falling back to in-memory idempotency",
                    uetr, exc,
                )

        # In-memory fallback
        with self._lock:
            if uetr in self._repaid_uetrs:
                logger.info(
                    "Idempotency: repayment already processed (in-memory) for uetr=%s — skipping",
                    uetr,
                )
                return False
            self._repaid_uetrs.add(uetr)
        return True

    def trigger_repayment(
        self,
        loan: ActiveLoan,
        trigger: RepaymentTrigger,
        settlement_amount: Decimal,
    ) -> dict:
        """Build a repayment record, invoke the callback, and deregister the loan.

        Before processing, acquires an idempotency claim via Redis SETNX (or
        in-memory set) to prevent duplicate repayments when multiple Flink
        instances process the same UETR concurrently.

        Returns:
            A repayment record dict with standardised fields, or an empty dict
            if the repayment was already processed (idempotency skip).
        """
        # Derive maturity_days from loan state for TTL calculation
        maturity_days = 7  # default (Class B)
        try:
            from .rejection_taxonomy import RejectionClass
            cls_map = {
                RejectionClass.CLASS_A.value: 3,
                RejectionClass.CLASS_B.value: 7,
                RejectionClass.CLASS_C.value: 21,
            }
            maturity_days = cls_map.get(loan.rejection_class, 7)
        except Exception:
            pass

        # GAP-16: Partial settlement handling (checked BEFORE idempotency claim
        # so REQUIRE_FULL does not consume the Redis SETNX token)
        _is_partial = settlement_amount < loan.principal
        _shortfall = loan.principal - settlement_amount if _is_partial else Decimal("0")
        _shortfall_pct = (
            float(_shortfall / loan.principal) if _is_partial and loan.principal > 0 else 0.0
        )
        if _is_partial and self._partial_settlement_policy is not None:
            if self._partial_settlement_policy == PartialSettlementPolicy.REQUIRE_FULL:
                logger.info(
                    "Partial settlement (REQUIRE_FULL): loan_id=%s shortfall=%s (%.1f%%) — loan kept active",
                    loan.loan_id, _shortfall, _shortfall_pct * 100,
                )
                return {
                    "status": "PARTIAL_PENDING",
                    "loan_id": loan.loan_id,
                    "uetr": loan.uetr,
                    "settlement_amount": str(settlement_amount),
                    "shortfall_amount": str(_shortfall),
                    "shortfall_pct": _shortfall_pct,
                    "is_partial": True,
                }
            # ACCEPT_PARTIAL: fall through — fee computed on settlement_amount below

        if not self._claim_repayment(loan.uetr, maturity_days):
            return {}

        now = _utcnow()
        days_funded = max(1, (now - loan.funded_at.replace(tzinfo=timezone.utc)
                              if loan.funded_at.tzinfo is None
                              else now - loan.funded_at).days)
        # GAP-16: under ACCEPT_PARTIAL compute fee on actual settled amount
        effective_principal = (
            settlement_amount
            if _is_partial and self._partial_settlement_policy == PartialSettlementPolicy.ACCEPT_PARTIAL
            else loan.principal
        )
        fee = compute_loan_fee(effective_principal, Decimal(str(loan.fee_bps)), days_funded)

        # Phase-aware BPI fee share: resolve from loan's deployment phase.
        # Phase 1 (LICENSOR) → 30% royalty; Phase 2 (HYBRID) → 55%; Phase 3 (FULL_MLO) → 80%.
        try:
            phase = DeploymentPhase(loan.deployment_phase)
        except ValueError:
            phase = DeploymentPhase.LICENSOR
        phase_cfg = get_phase_config(phase)

        bpi_fee_share_usd = compute_platform_royalty(fee, royalty_rate=phase_cfg.bpi_fee_share)
        net_fee_to_entities = fee - bpi_fee_share_usd
        bank_share_usd = net_fee_to_entities

        # Decompose bank share into capital return + distribution premium (Phase 2/3)
        from decimal import ROUND_HALF_UP
        bank_capital_return_usd = (
            fee * phase_cfg.bank_capital_return_share
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        bank_distribution_premium_usd = bank_share_usd - bank_capital_return_usd

        repayment_record = {
            "loan_id": loan.loan_id,
            "uetr": loan.uetr,
            "individual_payment_id": loan.individual_payment_id,
            "principal": str(loan.principal),
            "fee": str(fee),
            # Primary field (replaces platform_royalty semantically for Phase 2/3)
            "bpi_fee_share_usd": str(bpi_fee_share_usd),
            # Backward-compat alias — royalty_settlement.py reads this key
            "platform_royalty": str(bpi_fee_share_usd),
            "net_fee_to_entities": str(net_fee_to_entities),
            "bank_capital_return_usd": str(bank_capital_return_usd),
            "bank_distribution_premium_usd": str(bank_distribution_premium_usd),
            "income_type": phase_cfg.income_type,
            "deployment_phase": phase.value,
            "licensee_id": loan.licensee_id,
            "fee_bps": loan.fee_bps,
            "settlement_amount": str(settlement_amount),
            "corridor": loan.corridor,
            "rejection_class": loan.rejection_class,
            "trigger": trigger.value,
            "funded_at": loan.funded_at.isoformat(),
            "maturity_date": loan.maturity_date.isoformat(),
            "repaid_at": _utcnow().isoformat(),
            "is_partial": _is_partial,
            "shortfall_amount": str(_shortfall),
            "shortfall_pct": _shortfall_pct,
        }
        logger.info(
            "Repayment triggered: loan_id=%s trigger=%s amount=%s",
            loan.loan_id, trigger.value, settlement_amount,
        )
        try:
            self._callback(repayment_record)
        except Exception as exc:
            logger.exception(
                "Repayment callback raised for loan_id=%s: %s", loan.loan_id, exc
            )
        self._deregister_loan(loan.loan_id)
        return repayment_record

    # ── Maturity check ────────────────────────────────────────────────────────

    def check_maturities(self) -> List[dict]:
        """Inspect all active loans and trigger buffer repayment for matured loans.

        A loan is considered matured when ``_utcnow() >= loan.maturity_date``.
        BLOCK-class loans (maturity_days == 0) are skipped here — they must be
        resolved through the dispute path.

        Returns:
            List of repayment records for every loan that was triggered.
        """
        now = _utcnow()
        triggered: List[dict] = []

        with self._lock:
            snapshot = list(self._active_loans.values())

        for loan in snapshot:
            # Skip BLOCK loans — no automated bridge repayment
            if loan.rejection_class == RejectionClass.BLOCK.value:
                logger.debug(
                    "Skipping BLOCK loan in maturity check: loan_id=%s", loan.loan_id
                )
                continue

            maturity_dt = loan.maturity_date
            if maturity_dt.tzinfo is None:
                maturity_dt = maturity_dt.replace(tzinfo=timezone.utc)

            if now >= maturity_dt:
                logger.info(
                    "Maturity reached: loan_id=%s uetr=%s maturity=%s",
                    loan.loan_id, loan.uetr, maturity_dt.isoformat(),
                )
                record = self.trigger_repayment(
                    loan,
                    RepaymentTrigger.MATURITY_REACHED,
                    loan.principal,  # repay full principal on maturity
                )
                if record:  # empty dict means idempotency skip
                    triggered.append(record)

        return triggered

    # ── Background monitoring loop ────────────────────────────────────────────

    def run_monitoring_loop(self, interval_seconds: int = 30) -> None:
        """Start the background monitoring thread.

        The thread calls ``check_maturities()`` every ``interval_seconds``
        seconds until ``stop()`` is called.  It is safe to call this method
        multiple times — a second call is a no-op if the thread is alive.

        Args:
            interval_seconds: Poll interval in seconds (default 30).
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Monitoring loop already running; ignoring duplicate start.")
            return

        self._stop_event.clear()

        def _loop() -> None:
            logger.info(
                "RepaymentLoop monitoring thread started (interval=%ds).",
                interval_seconds,
            )
            while not self._stop_event.wait(timeout=interval_seconds):
                try:
                    triggered = self.check_maturities()
                    if triggered:
                        logger.info(
                            "Maturity check: %d repayment(s) triggered.", len(triggered)
                        )
                except Exception as exc:
                    logger.exception("Error in maturity check iteration: %s", exc)
            logger.info("RepaymentLoop monitoring thread stopped.")

        self._thread = threading.Thread(target=_loop, daemon=True, name="RepaymentLoop")
        self._thread.start()

    def stop(self) -> None:
        """Signal the monitoring thread to stop and wait for it to exit."""
        if self._thread is None:
            return
        logger.info("Stopping RepaymentLoop monitoring thread…")
        self._stop_event.set()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            logger.warning("RepaymentLoop thread did not stop within timeout.")
        self._thread = None
