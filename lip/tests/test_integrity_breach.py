"""Tests for lip.integrity.breach_protocol."""
from __future__ import annotations

import pytest

from lip.integrity.breach_protocol import (
    PROHIBITED_ASSURANCES,
    BreachDisclosureWorkflow,
    DisclosureState,
    SecurityEvent,
    SecurityEventSeverity,
)
from lip.integrity.evidence import hash_data_blob, utcnow

_KEY = b"integrity_test__32bytes_________"


def _wf() -> BreachDisclosureWorkflow:
    return BreachDisclosureWorkflow(hmac_key=_KEY)


def _event(eid: str = "evt-1") -> SecurityEvent:
    return SecurityEvent(
        event_id=eid,
        severity=SecurityEventSeverity.HIGH,
        event_type="CONFIG_EXPOSURE",
        description="Public Google Sheet contained draft audit reports.",
        affected_systems=["audit-pipeline"],
        detected_at=utcnow(),
        detected_by="security-monitor",
        data_hash=hash_data_blob(b"raw forensic snapshot"),
    )


# ---------------------------------------------------------------------------


def test_log_security_event_is_immutable():
    wf = _wf()
    eid = wf.log_security_event(_event())
    assert eid == "evt-1"
    assert wf.event_count() == 1

    # Re-logging the same event_id is forbidden
    with pytest.raises(ValueError, match="append-only"):
        wf.log_security_event(_event())


def test_disclosure_blocks_all_prohibited_phrases():
    wf = _wf()
    wf.log_security_event(_event())

    # Each phrase from PROHIBITED_ASSURANCES, in turn, must trigger a block
    for phrase in PROHIBITED_ASSURANCES:
        text = f"We are pleased to confirm that {phrase}. Operations continue normally."
        result = wf.validate_disclosure_text(text, "evt-1")
        assert result.is_valid is False, f"Phrase should have been blocked: {phrase!r}"
        assert phrase in result.prohibited_phrases_found
        assert phrase in result.requires_forensic_evidence


def test_disclosure_allows_factual_statements():
    wf = _wf()
    wf.log_security_event(_event())

    factual = (
        "On 2026-04-06, BPI detected a configuration exposure affecting the "
        "audit-pipeline system. Forensic investigation is in progress. We "
        "will provide a complete update within 72 hours and are not making "
        "conclusions about scope until that work is complete."
    )
    result = wf.validate_disclosure_text(factual, "evt-1")
    assert result.is_valid is True
    assert result.prohibited_phrases_found == []


def test_workflow_state_transitions_through_signoff():
    wf = _wf()
    wf.log_security_event(_event())
    assert wf.get_state("evt-1") == DisclosureState.DETECTED

    wf.generate_disclosure_draft("evt-1")
    assert wf.get_state("evt-1") == DisclosureState.DISCLOSURE_DRAFTED

    ok = wf.require_signoff("evt-1", signoff_by="legal-counsel")
    assert ok is True
    assert wf.get_state("evt-1") == DisclosureState.REVIEWED

    # Signoff cannot be applied twice (state has advanced past DRAFTED)
    assert wf.require_signoff("evt-1", signoff_by="someone-else") is False


def test_generate_disclosure_marks_unknowns_explicitly():
    wf = _wf()
    wf.log_security_event(_event())
    draft = wf.generate_disclosure_draft("evt-1")
    assert "[UNKNOWN - INVESTIGATION REQUIRED]" in draft.template_text
    assert any("UNKNOWN" in u for u in draft.unknown_facts)
    assert "not making any conclusions" in draft.template_text.lower()


def test_audit_trail_chronological_and_complete():
    wf = _wf()
    wf.log_security_event(_event())
    wf.generate_disclosure_draft("evt-1")
    wf.require_signoff("evt-1", signoff_by="legal-counsel")

    trail = wf.get_audit_trail("evt-1")
    assert len(trail) == 3
    actions = [entry["action"] for entry in trail]
    assert actions == ["EVENT_LOGGED", "DRAFT_GENERATED", "SIGNOFF"]
    # Timestamps must be monotonically non-decreasing
    timestamps = [entry["timestamp"] for entry in trail]
    assert timestamps == sorted(timestamps)
