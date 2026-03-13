"""
offer_delivery.py — GAP-01: Loan offer delivery and acceptance protocol.

Manages the lifecycle: C7 OFFER decision → ELO delivery → acceptance/rejection → C3 activation.

Delivery states:
  PENDING  — offer delivered, awaiting ELO treasury response within offer_expiry window
  ACCEPTED — ELO confirmed; on_accept callback fires → C3 registers the ActiveLoan
  REJECTED — ELO declined; payment fails normally
  EXPIRED  — offer_expiry passed with no response; payment fails normally

Thread-safe: all state mutations are protected by an internal Lock.

Three-entity role mapping:
  MLO   — Money Lending Organisation (capital provider)
  MIPLO — Money In / Payment Lending Organisation (BPI platform)
  ELO   — Execution Lending Organisation (bank-side agent, this component)
"""

import enum
import logging
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from lip.common.schemas import LoanOfferAcceptance, LoanOfferDelivery, LoanOfferRejection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Outcome enum
# ---------------------------------------------------------------------------

class OfferDeliveryOutcome(str, enum.Enum):
    """Lifecycle state of a delivered loan offer."""

    PENDING  = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED  = "EXPIRED"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OfferNotFoundException(Exception):
    """Raised when accept/reject references an unknown offer_id."""


class OfferExpiredException(Exception):
    """Raised when accept/reject is called after the offer has expired."""


class OfferAlreadyResolvedException(Exception):
    """Raised when accept/reject is called on an already-resolved offer."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class OfferDeliveryService:
    """Manages loan offer delivery, acceptance, expiry, and rejection (GAP-01).

    Decouples the OFFER decision in C7 from the ELO's treasury confirmation.
    Tracks delivery state for every outstanding offer and fires optional
    callbacks so downstream components (C3) can react without polling.

    Intended usage
    --------------
    1. C7 ExecutionAgent calls ``deliver(offer_dict)`` for every OFFER decision.
    2. The ELO bank's treasury system calls ``accept`` or ``reject``.
    3. A background scheduler calls ``expire_stale_offers()`` periodically.
    4. C3 RepaymentLoop subscribes via ``on_accept`` to register ActiveLoan.

    Parameters
    ----------
    on_accept:
        Callback invoked synchronously when an offer is accepted.
        Intended for C3 loan registration. Signature: (LoanOfferAcceptance) -> None.
    on_reject:
        Callback invoked synchronously when an offer is rejected.
        Signature: (LoanOfferRejection) -> None.
    on_expire:
        Callback invoked synchronously per expired offer_id during
        ``expire_stale_offers()``. Signature: (offer_id: str) -> None.
    delivery_endpoint:
        Optional webhook URL stamped on every LoanOfferDelivery so the ELO
        treasury system knows where to POST acceptance/rejection callbacks.
        None in offline / test mode.
    """

    def __init__(
        self,
        on_accept: Optional[Callable[[LoanOfferAcceptance], None]] = None,
        on_reject: Optional[Callable[[LoanOfferRejection], None]] = None,
        on_expire: Optional[Callable[[str], None]] = None,
        delivery_endpoint: Optional[str] = None,
    ) -> None:
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._on_expire = on_expire
        self._delivery_endpoint = delivery_endpoint
        self._lock = threading.Lock()
        # offer_id (str) → LoanOfferDelivery
        self._pending: Dict[str, LoanOfferDelivery] = {}
        # offer_id (str) → LoanOfferAcceptance
        self._acceptances: Dict[str, LoanOfferAcceptance] = {}
        # offer_id (str) → LoanOfferRejection
        self._rejections: Dict[str, LoanOfferRejection] = {}
        # offer_ids that have been explicitly expired
        self._expired: set = set()

    # ── Delivery ─────────────────────────────────────────────────────────────

    def deliver(self, offer: dict) -> LoanOfferDelivery:
        """Register a C7 offer for ELO delivery and return the delivery record.

        Called by ExecutionAgent immediately after ``_build_loan_offer`` produces
        an OFFER decision. Converts the raw offer dict to a LoanOfferDelivery
        and stores it in PENDING state.

        Parameters
        ----------
        offer:
            Raw offer dict from ExecutionAgent._build_loan_offer. Expected keys:
            ``loan_id``, ``uetr``, ``loan_amount``, ``fee_bps``, ``maturity_days``,
            ``pd_score``, ``expires_at``. Optional: ``elo_entity_id``,
            ``fee_amount_usd``, ``rejection_code_class``.

        Returns
        -------
        LoanOfferDelivery
            The newly created delivery record in PENDING state.
        """
        uetr_raw = offer.get("uetr") or ""
        try:
            uetr_uuid = uuid.UUID(uetr_raw)
        except (ValueError, AttributeError):
            uetr_uuid = uuid.uuid4()

        delivery = LoanOfferDelivery(
            delivery_id=uuid.uuid4(),
            offer_id=uuid.UUID(offer["loan_id"]),
            uetr=uetr_uuid,
            elo_entity_id=offer.get("elo_entity_id", ""),
            principal_usd=Decimal(str(offer.get("loan_amount", "0"))),
            fee_bps=Decimal(str(offer.get("fee_bps", "300"))),
            fee_amount_usd=Decimal(str(offer.get("fee_amount_usd", "0"))),
            maturity_days=int(offer.get("maturity_days", 7)),
            rejection_code_class=offer.get("rejection_code_class", "B"),
            offer_expiry=datetime.fromisoformat(offer["expires_at"]),
            pd_score=float(offer.get("pd_score", 0.0)),
            delivery_endpoint=self._delivery_endpoint,
            delivered_at=datetime.now(tz=timezone.utc),
        )
        offer_id_str = str(delivery.offer_id)
        with self._lock:
            self._pending[offer_id_str] = delivery
        logger.info(
            "Offer delivered: offer_id=%s uetr=%s expiry=%s",
            offer_id_str,
            delivery.uetr,
            delivery.offer_expiry.isoformat(),
        )
        return delivery

    # ── Acceptance ───────────────────────────────────────────────────────────

    def accept(self, offer_id: str, elo_operator_id: str) -> LoanOfferAcceptance:
        """Record ELO acceptance of a pending offer.

        Validates that the offer exists, has not expired, and has not already
        been resolved. Moves the offer from PENDING to ACCEPTED and fires
        ``on_accept``.

        Parameters
        ----------
        offer_id:
            String UUID of the offer to accept.
        elo_operator_id:
            Non-empty operator identifier for the EU AI Act Art.14 audit trail.

        Returns
        -------
        LoanOfferAcceptance
            The created acceptance record.

        Raises
        ------
        ValueError
            If ``elo_operator_id`` is empty.
        OfferNotFoundException
            If ``offer_id`` is not known to the service.
        OfferExpiredException
            If the offer's ``offer_expiry`` has passed.
        OfferAlreadyResolvedException
            If the offer was already accepted or rejected.
        """
        if not elo_operator_id:
            raise ValueError("elo_operator_id is required for audit trail")

        with self._lock:
            self._check_resolvable(offer_id)
            delivery = self._pending.pop(offer_id)
            acceptance = LoanOfferAcceptance(
                acceptance_id=uuid.uuid4(),
                delivery_id=delivery.delivery_id,
                offer_id=delivery.offer_id,
                uetr=delivery.uetr,
                elo_entity_id=delivery.elo_entity_id,
                elo_operator_id=elo_operator_id,
                accepted_at=datetime.now(tz=timezone.utc),
            )
            self._acceptances[offer_id] = acceptance

        logger.info(
            "Offer accepted: offer_id=%s operator=%s uetr=%s",
            offer_id,
            elo_operator_id,
            acceptance.uetr,
        )
        if self._on_accept is not None:
            try:
                self._on_accept(acceptance)
            except Exception:
                logger.exception("on_accept callback raised for offer_id=%s", offer_id)
        return acceptance

    # ── Rejection ────────────────────────────────────────────────────────────

    def reject(
        self,
        offer_id: str,
        elo_operator_id: str,
        rejection_reason: str,
    ) -> LoanOfferRejection:
        """Record ELO rejection of a pending offer.

        Parameters
        ----------
        offer_id:
            String UUID of the offer to reject.
        elo_operator_id:
            Non-empty operator identifier for the audit trail.
        rejection_reason:
            Non-empty reason text; required for operational analysis.

        Returns
        -------
        LoanOfferRejection
            The created rejection record.

        Raises
        ------
        ValueError
            If ``elo_operator_id`` or ``rejection_reason`` is empty.
        OfferNotFoundException, OfferExpiredException, OfferAlreadyResolvedException
        """
        if not elo_operator_id:
            raise ValueError("elo_operator_id is required for audit trail")
        if not rejection_reason:
            raise ValueError("rejection_reason is required")

        with self._lock:
            self._check_resolvable(offer_id)
            delivery = self._pending.pop(offer_id)
            rejection = LoanOfferRejection(
                rejection_id=uuid.uuid4(),
                delivery_id=delivery.delivery_id,
                offer_id=delivery.offer_id,
                uetr=delivery.uetr,
                elo_entity_id=delivery.elo_entity_id,
                elo_operator_id=elo_operator_id,
                rejection_reason=rejection_reason,
                rejected_at=datetime.now(tz=timezone.utc),
            )
            self._rejections[offer_id] = rejection

        logger.info(
            "Offer rejected: offer_id=%s operator=%s reason=%r",
            offer_id,
            elo_operator_id,
            rejection_reason,
        )
        if self._on_reject is not None:
            try:
                self._on_reject(rejection)
            except Exception:
                logger.exception("on_reject callback raised for offer_id=%s", offer_id)
        return rejection

    # ── Expiry sweep ─────────────────────────────────────────────────────────

    def expire_stale_offers(self) -> List[str]:
        """Sweep PENDING offers whose offer_expiry has passed.

        Should be called periodically (e.g., every 60 seconds) by a background
        scheduler so expired offers are cleaned up and ``on_expire`` callbacks fired.

        Returns
        -------
        List[str]
            offer_id strings of offers newly moved to EXPIRED.
        """
        now = datetime.now(tz=timezone.utc)
        expired_ids: List[str] = []

        with self._lock:
            to_expire = [
                oid
                for oid, delivery in list(self._pending.items())
                if _is_expired(delivery, now)
            ]
            for oid in to_expire:
                self._pending.pop(oid)
                self._expired.add(oid)
                expired_ids.append(oid)

        for oid in expired_ids:
            logger.info("Offer expired: offer_id=%s", oid)
            if self._on_expire is not None:
                try:
                    self._on_expire(oid)
                except Exception:
                    logger.exception("on_expire callback raised for offer_id=%s", oid)

        return expired_ids

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_outcome(self, offer_id: str) -> OfferDeliveryOutcome:
        """Return the current lifecycle outcome for ``offer_id``.

        Raises
        ------
        OfferNotFoundException
            If ``offer_id`` is completely unknown to the service.
        """
        with self._lock:
            if offer_id in self._acceptances:
                return OfferDeliveryOutcome.ACCEPTED
            if offer_id in self._rejections:
                return OfferDeliveryOutcome.REJECTED
            if offer_id in self._expired:
                return OfferDeliveryOutcome.EXPIRED
            if offer_id in self._pending:
                return OfferDeliveryOutcome.PENDING
        raise OfferNotFoundException(f"offer_id {offer_id!r} not found")

    def get_acceptance(self, offer_id: str) -> Optional[LoanOfferAcceptance]:
        """Return the LoanOfferAcceptance for ``offer_id``, or None if not accepted."""
        with self._lock:
            return self._acceptances.get(offer_id)

    def get_rejection(self, offer_id: str) -> Optional[LoanOfferRejection]:
        """Return the LoanOfferRejection for ``offer_id``, or None if not rejected."""
        with self._lock:
            return self._rejections.get(offer_id)

    def get_pending_deliveries(self) -> List[LoanOfferDelivery]:
        """Return a snapshot of all PENDING (unresolved, unexpired) deliveries."""
        with self._lock:
            return list(self._pending.values())

    # ── Internal ─────────────────────────────────────────────────────────────

    def _check_resolvable(self, offer_id: str) -> None:
        """Assert offer_id can be accepted or rejected. Must be called within the lock.

        Raises the appropriate exception if the offer is already resolved,
        already expired, unknown, or has expired since delivery.
        """
        if offer_id in self._acceptances or offer_id in self._rejections:
            raise OfferAlreadyResolvedException(
                f"offer_id {offer_id!r} has already been resolved"
            )
        if offer_id in self._expired:
            raise OfferExpiredException(f"offer_id {offer_id!r} has expired")
        if offer_id not in self._pending:
            raise OfferNotFoundException(f"offer_id {offer_id!r} not found")
        # Check live expiry even if still nominally in _pending
        delivery = self._pending[offer_id]
        now = datetime.now(tz=timezone.utc)
        if _is_expired(delivery, now):
            self._pending.pop(offer_id)
            self._expired.add(offer_id)
            raise OfferExpiredException(
                f"offer_id {offer_id!r} expired at {delivery.offer_expiry.isoformat()}"
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_expired(delivery: LoanOfferDelivery, now: datetime) -> bool:
    """Return True if delivery.offer_expiry <= now (timezone-aware comparison)."""
    expiry = delivery.offer_expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= now
