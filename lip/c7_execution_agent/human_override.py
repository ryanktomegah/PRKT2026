"""
human_override.py — EU AI Act Article 14 human-in-the-loop override.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OverrideDecision(str, Enum):
    """Possible outcomes of a human override review.

    Attributes:
        APPROVE: Operator endorses the AI decision; loan offer proceeds.
        REJECT: Operator countermands the AI decision; the offer is blocked.
            A non-empty ``justification`` is required by
            :meth:`~HumanOverrideInterface.submit_response`.
        ESCALATE: Operator defers to a higher authority; the request
            remains pending until re-assigned or expired.
    """

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


@dataclass
class HumanOverrideRequest:
    """A pending request for human review of an AI-generated decision.

    Attributes:
        request_id: UUID4 string uniquely identifying this override request.
        uetr: ISO 20022 Unique End-to-End Transaction Reference of the
            payment under review.
        original_decision: The AI-generated decision that triggered the
            override request (e.g., ``'BRIDGE_OFFERED'``, ``'BLOCKED_AML'``).
        ai_confidence: Model confidence score [0, 1] for ``original_decision``.
            Lower values typically trigger override requests.
        reason_for_override: Human-readable description of why the AI
            decision requires human review.
        requested_at: UTC datetime when the override was requested.
        expires_at: UTC datetime after which the request is no longer
            actionable (``requested_at + timeout_seconds``).
        operator_id: Identifier of the operator assigned to review this
            request, or ``None`` if unassigned.
    """

    request_id: str
    uetr: str
    original_decision: str
    ai_confidence: float
    reason_for_override: str
    requested_at: datetime
    expires_at: datetime
    operator_id: Optional[str] = None


@dataclass
class HumanOverrideResponse:
    """The recorded outcome of a human override review.

    Attributes:
        request_id: UUID4 string echoing the :class:`HumanOverrideRequest`
            this response resolves.
        decision: The operator's :class:`OverrideDecision`.
        operator_id: Non-empty identifier of the operator who submitted
            this response (required for EU AI Act Art.14 audit trail).
        justification: Free-text explanation.  Required (non-empty) for
            ``REJECT`` decisions.
        decided_at: UTC datetime when the response was submitted.
        is_valid: ``True`` if the response passed all validation rules;
            always ``True`` for responses created by
            :meth:`~HumanOverrideInterface.submit_response`.
    """

    request_id: str
    decision: OverrideDecision
    operator_id: str
    justification: str
    decided_at: datetime
    is_valid: bool = True


class HumanOverrideInterface:
    """EU AI Act Art.14 compliant human-in-the-loop override interface."""

    def __init__(
        self,
        requires_dual_approval: bool = False,
        timeout_seconds: float = 300,
        timeout_action: str = "DECLINE",
    ):
        if timeout_action not in ("DECLINE", "OFFER"):
            raise ValueError(
                f"timeout_action must be 'DECLINE' or 'OFFER', got '{timeout_action}'"
            )
        self._requires_dual_approval = requires_dual_approval
        self._timeout_seconds = timeout_seconds
        # GAP-08: Configurable outcome when a review request expires with no
        # human response. Default is DECLINE (conservative); licensees may
        # configure OFFER for low-PD edge cases where speed outweighs review.
        self.timeout_action = timeout_action
        self._pending: Dict[str, HumanOverrideRequest] = {}
        self._responses: Dict[str, HumanOverrideResponse] = {}

    def request_override(
        self,
        uetr: str,
        original_decision: str,
        ai_confidence: float,
        reason: str,
    ) -> HumanOverrideRequest:
        """Create and register a new human override request.

        Generates a UUID4 ``request_id`` and sets ``expires_at`` to
        ``now + timeout_seconds``.  The request is stored in
        :attr:`_pending` until a response is submitted or it expires.

        Args:
            uetr: ISO 20022 UETR of the payment requiring review.
            original_decision: AI decision string that triggered this
                override (e.g., ``'BRIDGE_OFFERED'``).
            ai_confidence: Confidence score [0, 1] of the AI decision.
            reason: Human-readable reason for requesting operator review.

        Returns:
            The newly created :class:`HumanOverrideRequest`.
        """
        request_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)
        req = HumanOverrideRequest(
            request_id=request_id,
            uetr=uetr,
            original_decision=original_decision,
            ai_confidence=ai_confidence,
            reason_for_override=reason,
            requested_at=now,
            expires_at=now + timedelta(seconds=self._timeout_seconds),
        )
        self._pending[request_id] = req
        logger.info("Override requested: %s uetr=%s confidence=%.2f", request_id, uetr, ai_confidence)
        return req

    def submit_response(
        self,
        request_id: str,
        decision: OverrideDecision,
        operator_id: str,
        justification: str,
    ) -> HumanOverrideResponse:
        """Record a human operator's decision for a pending override request.

        Validates that the request has not expired, that ``operator_id`` is
        non-empty, and that ``justification`` is non-empty for ``REJECT``
        decisions.  Moves the request from :attr:`_pending` to
        :attr:`_responses` on success.

        Args:
            request_id: UUID4 string of the :class:`HumanOverrideRequest` to
                resolve.
            decision: The operator's :class:`OverrideDecision`.
            operator_id: Non-empty operator identifier for the audit trail.
            justification: Explanation for the decision; required non-empty
                for ``REJECT`` decisions (EU AI Act Art.14).

        Returns:
            The recorded :class:`HumanOverrideResponse`.

        Raises:
            ValueError: If ``operator_id`` is empty, if ``justification`` is
                empty for a ``REJECT`` decision, or if the request has
                expired.
        """
        if not operator_id:
            raise ValueError("operator_id is required for override responses")
        if decision == OverrideDecision.REJECT and not justification:
            raise ValueError("justification is required for REJECT decisions")
        if self.is_expired(request_id):
            raise ValueError(f"Override request {request_id} has expired")
        resp = HumanOverrideResponse(
            request_id=request_id,
            decision=decision,
            operator_id=operator_id,
            justification=justification,
            decided_at=datetime.now(tz=timezone.utc),
        )
        self._responses[request_id] = resp
        self._pending.pop(request_id, None)
        logger.info("Override response: %s decision=%s operator=%s", request_id, decision, operator_id)
        return resp

    def is_pending(self, request_id: str) -> bool:
        """Return True when the request exists and has not yet expired.

        Args:
            request_id: UUID4 string of the override request.

        Returns:
            ``True`` if the request is in :attr:`_pending` and within its
            timeout window; ``False`` otherwise.
        """
        return request_id in self._pending and not self.is_expired(request_id)

    def is_expired(self, request_id: str) -> bool:
        """Return True when the override request has passed its expiry time.

        Returns ``True`` also for unknown ``request_id`` values (defensive).

        Args:
            request_id: UUID4 string of the override request.

        Returns:
            ``True`` if expired or unknown; ``False`` if still within the
            timeout window.
        """
        req = self._pending.get(request_id)
        if req is None:
            return True
        return datetime.now(tz=timezone.utc) > req.expires_at

    def resolve_expired(self, request_id: str) -> str:
        """Return the configured ``timeout_action`` for an expired request.

        GAP-08: Provides the definitive outcome (``"DECLINE"`` or ``"OFFER"``)
        when a human review request times out with no operator response.  The
        caller (e.g., a polling process or callback) uses this to close the
        pending UETR with a logged terminal decision.

        Args:
            request_id: UUID4 string of the override request.

        Returns:
            The string ``"DECLINE"`` or ``"OFFER"``, according to
            ``self.timeout_action``.

        Raises:
            ValueError: If the request has *not* yet expired (i.e., is still
                pending).  Prevents premature resolution.
            ValueError: If the request ID is unknown (defensive).
        """
        if request_id not in self._pending and request_id not in self._responses:
            raise ValueError(f"Unknown override request: {request_id}")
        if request_id in self._pending and not self.is_expired(request_id):
            raise ValueError(
                f"Override request {request_id} has not yet expired; cannot resolve."
            )
        # Remove from pending if still there (clean up)
        self._pending.pop(request_id, None)
        logger.info(
            "Override expired: %s resolved as %s", request_id, self.timeout_action
        )
        return self.timeout_action

    def get_pending_overrides(self) -> List[HumanOverrideRequest]:
        """Return all non-expired pending override requests.

        Filters out any requests whose ``expires_at`` has passed but have
        not yet been explicitly resolved.

        Returns:
            List of active :class:`HumanOverrideRequest` objects ordered by
            insertion time.
        """
        now = datetime.now(tz=timezone.utc)
        return [r for r in self._pending.values() if r.expires_at > now]
