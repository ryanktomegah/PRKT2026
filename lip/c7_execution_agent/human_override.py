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
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


@dataclass
class HumanOverrideRequest:
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
    request_id: str
    decision: OverrideDecision
    operator_id: str
    justification: str
    decided_at: datetime
    is_valid: bool = True


class HumanOverrideInterface:
    """EU AI Act Art.14 compliant human-in-the-loop override interface."""

    def __init__(self, requires_dual_approval: bool = False, timeout_seconds: float = 300):
        self._requires_dual_approval = requires_dual_approval
        self._timeout_seconds = timeout_seconds
        self._pending: Dict[str, HumanOverrideRequest] = {}
        self._responses: Dict[str, HumanOverrideResponse] = {}

    def request_override(
        self,
        uetr: str,
        original_decision: str,
        ai_confidence: float,
        reason: str,
    ) -> HumanOverrideRequest:
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
        return request_id in self._pending and not self.is_expired(request_id)

    def is_expired(self, request_id: str) -> bool:
        req = self._pending.get(request_id)
        if req is None:
            return True
        return datetime.now(tz=timezone.utc) > req.expires_at

    def get_pending_overrides(self) -> List[HumanOverrideRequest]:
        now = datetime.now(tz=timezone.utc)
        return [r for r in self._pending.values() if r.expires_at > now]
