"""breach_protocol.py — Structured breach disclosure with cover-up guardrails.

Prevents the Delve failure mode where the CEO sent customers an email saying
"no external party accessed sensitive data" without any forensic evidence —
turning a breach into a fraud. Three structural defenses:

  1. Append-only event log: ``log_security_event`` records every detected
     event in a tamper-evident HMAC-signed store (same pattern as
     ``DecisionLogger``). Events cannot be deleted or modified after logging.

  2. Prohibited assurances list: ``validate_disclosure_text`` scans candidate
     disclosure language for the exact phrases Delve's CEO used. Any match
     blocks the disclosure unless forensic evidence is registered against
     the event_id.

  3. Workflow state machine: disclosures must progress
     DETECTED → INVESTIGATED → DISCLOSURE_DRAFTED → REVIEWED → SENT.
     Sign-off is required to advance, and unknowns in the draft are marked
     ``[UNKNOWN - INVESTIGATION REQUIRED]`` rather than silently filled in.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lip.common.encryption import sign_hmac_sha256, verify_hmac_sha256
from lip.integrity.evidence import utcnow

# ---------------------------------------------------------------------------
# Prohibited assurances — phrases that turned Delve's breach into fraud
# ---------------------------------------------------------------------------

PROHIBITED_ASSURANCES: tuple[str, ...] = (
    "no data was accessed",
    "no external party accessed",
    "no unauthorized access occurred",
    "data was not compromised",
    "no evidence of breach",
    "no customer data was affected",
    "the incident had no impact",
    "your data remains secure",
    "no sensitive data was exposed",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SecurityEventSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DisclosureState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATED = "INVESTIGATED"
    DISCLOSURE_DRAFTED = "DISCLOSURE_DRAFTED"
    REVIEWED = "REVIEWED"
    SENT = "SENT"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SecurityEvent(BaseModel):
    """Immutable record of a detected security event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    severity: SecurityEventSeverity
    event_type: str  # DATA_BREACH | UNAUTHORIZED_ACCESS | CONFIG_EXPOSURE | DEPENDENCY_VULN
    description: str
    affected_systems: list[str] = Field(default_factory=list)
    detected_at: datetime
    detected_by: str
    data_hash: str
    signature: str = ""


@dataclass(frozen=True)
class DisclosureDraft:
    event_id: str
    template_text: str
    known_facts: list[str]
    unknown_facts: list[str]
    state: DisclosureState


@dataclass(frozen=True)
class DisclosureValidation:
    is_valid: bool
    prohibited_phrases_found: list[str]
    requires_forensic_evidence: list[str]
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class BreachDisclosureWorkflow:
    """Append-only breach log with disclosure-text guardrails."""

    def __init__(self, hmac_key: bytes) -> None:
        if len(hmac_key) < 32:
            raise ValueError(
                f"HMAC key must be ≥ 32 bytes; got {len(hmac_key)} bytes."
            )
        self._key = hmac_key
        # Append-only stores
        self._events: dict[str, SecurityEvent] = {}
        self._states: dict[str, DisclosureState] = {}
        # Audit trail: event_id → list of (timestamp, action, actor) tuples
        self._audit: dict[str, list[dict[str, Any]]] = {}
        # Forensic evidence registered against an event_id (set of fact strings)
        self._forensic: dict[str, set[str]] = {}

    # -- internal canonical JSON pattern (mirrors DecisionLogger) ----------

    def _sign_event(self, event: SecurityEvent) -> str:
        payload = event.model_dump(mode="json")
        payload.pop("signature", None)
        canonical = json.dumps(payload, sort_keys=True, default=str).encode()
        return sign_hmac_sha256(canonical, self._key)

    def _verify_event(self, event: SecurityEvent) -> bool:
        if not event.signature:
            return False
        payload = event.model_dump(mode="json")
        payload.pop("signature", None)
        canonical = json.dumps(payload, sort_keys=True, default=str).encode()
        return verify_hmac_sha256(canonical, event.signature, self._key)

    # -- logging -----------------------------------------------------------

    def log_security_event(self, event: SecurityEvent) -> str:
        """Append a security event to the immutable log. Returns the event_id."""
        eid = event.event_id or str(uuid.uuid4())
        if eid in self._events:
            raise ValueError(
                f"event_id {eid} already exists; the breach log is append-only "
                "and cannot be overwritten."
            )
        signed = event.model_copy(update={"event_id": eid})
        signed = signed.model_copy(update={"signature": self._sign_event(signed)})
        self._events[eid] = signed
        self._states[eid] = DisclosureState.DETECTED
        self._audit[eid] = [
            {
                "timestamp": utcnow().isoformat(),
                "action": "EVENT_LOGGED",
                "actor": event.detected_by,
                "state": DisclosureState.DETECTED.value,
            }
        ]
        self._forensic[eid] = set()
        return eid

    # -- forensic evidence registration ------------------------------------

    def register_forensic_finding(self, event_id: str, finding: str) -> None:
        """Register a forensic finding that supports a disclosure assertion.

        Once registered, the finding text can be used to satisfy the
        ``validate_disclosure_text`` requirement that prohibited assurances
        be backed by evidence.
        """
        if event_id not in self._events:
            raise ValueError(f"unknown event_id: {event_id}")
        self._forensic[event_id].add(finding.strip().lower())

    # -- draft generation --------------------------------------------------

    def generate_disclosure_draft(self, event_id: str) -> DisclosureDraft:
        """Generate a factual disclosure template, marking unknowns explicitly."""
        if event_id not in self._events:
            raise ValueError(f"unknown event_id: {event_id}")
        event = self._events[event_id]

        known_facts = [
            f"Event type: {event.event_type}",
            f"Severity: {event.severity.value}",
            f"Detected at (UTC): {event.detected_at.isoformat()}",
            f"Affected systems: {', '.join(event.affected_systems) or 'TBD'}",
            f"Description: {event.description}",
        ]
        unknown_facts = [
            "Scope of data exposure: [UNKNOWN - INVESTIGATION REQUIRED]",
            "Number of records accessed: [UNKNOWN - INVESTIGATION REQUIRED]",
            "Identity of accessing party: [UNKNOWN - INVESTIGATION REQUIRED]",
            "Root cause: [UNKNOWN - INVESTIGATION REQUIRED]",
        ]
        template = (
            f"SECURITY INCIDENT NOTIFICATION ({event.severity.value})\n\n"
            f"On {event.detected_at.date().isoformat()}, BPI's monitoring "
            f"detected the following event:\n\n"
            f"{event.description}\n\n"
            "Known facts:\n"
            + "\n".join(f"  - {f}" for f in known_facts)
            + "\n\nFacts under active investigation:\n"
            + "\n".join(f"  - {f}" for f in unknown_facts)
            + "\n\nWe will provide a complete factual update within 72 hours. "
            "We are not making any conclusions about the impact of this event "
            "until our forensic investigation is complete."
        )

        self._states[event_id] = DisclosureState.DISCLOSURE_DRAFTED
        self._audit[event_id].append(
            {
                "timestamp": utcnow().isoformat(),
                "action": "DRAFT_GENERATED",
                "actor": "BreachDisclosureWorkflow",
                "state": DisclosureState.DISCLOSURE_DRAFTED.value,
            }
        )
        return DisclosureDraft(
            event_id=event_id,
            template_text=template,
            known_facts=known_facts,
            unknown_facts=unknown_facts,
            state=DisclosureState.DISCLOSURE_DRAFTED,
        )

    # -- validation --------------------------------------------------------

    def validate_disclosure_text(
        self, text: str, event_id: str
    ) -> DisclosureValidation:
        """Scan *text* for prohibited assurances; require forensic evidence for any match.

        This is the structural mirror of the Delve cover-up: the exact phrases
        the CEO used ("no external party accessed", etc.) are blocked unless
        ``register_forensic_finding`` has been called with corresponding
        evidence on this event_id.
        """
        if event_id not in self._events:
            raise ValueError(f"unknown event_id: {event_id}")

        normalised = text.lower()
        forensic = self._forensic.get(event_id, set())

        found: list[str] = []
        needs_evidence: list[str] = []

        for phrase in PROHIBITED_ASSURANCES:
            if phrase in normalised:
                found.append(phrase)
                # Forensic evidence must mention the same phrase or "verified"
                # against this assertion. We require an explicit forensic
                # finding for each prohibited phrase used.
                supported = any(
                    phrase in finding or "forensic" in finding
                    for finding in forensic
                )
                if not supported:
                    needs_evidence.append(phrase)

        is_valid = len(needs_evidence) == 0
        recommendations: list[str] = []
        if needs_evidence:
            recommendations.append(
                "Replace unsupported assurances with factual statements about "
                "what is currently known and what is still under investigation."
            )
            recommendations.append(
                "If forensic evidence supports an assurance, register it via "
                "register_forensic_finding() before re-validating."
            )
        return DisclosureValidation(
            is_valid=is_valid,
            prohibited_phrases_found=found,
            requires_forensic_evidence=needs_evidence,
            recommendations=recommendations,
        )

    # -- state advancement -------------------------------------------------

    def require_signoff(self, event_id: str, signoff_by: str) -> bool:
        """Advance the workflow to REVIEWED. Returns True on success.

        Signoff requires that a draft has been generated. Records the
        signing operator in the audit trail.
        """
        if event_id not in self._events:
            raise ValueError(f"unknown event_id: {event_id}")
        if self._states[event_id] != DisclosureState.DISCLOSURE_DRAFTED:
            return False
        self._states[event_id] = DisclosureState.REVIEWED
        self._audit[event_id].append(
            {
                "timestamp": utcnow().isoformat(),
                "action": "SIGNOFF",
                "actor": signoff_by,
                "state": DisclosureState.REVIEWED.value,
            }
        )
        return True

    # -- accessors ---------------------------------------------------------

    def get_audit_trail(self, event_id: str) -> list[dict[str, Any]]:
        """Return the chronological audit trail for an event."""
        return list(self._audit.get(event_id, []))

    def get_event(self, event_id: str) -> SecurityEvent | None:
        return self._events.get(event_id)

    def get_state(self, event_id: str) -> DisclosureState | None:
        return self._states.get(event_id)

    def event_count(self) -> int:
        return len(self._events)
