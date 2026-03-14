"""
test_gap08_override_timeout.py — Integration tests for GAP-08:
Human override timeout outcome (configurable DECLINE / OFFER).
"""
import time

import pytest

from lip.c7_execution_agent.human_override import HumanOverrideInterface


@pytest.fixture
def decline_interface():
    """Default interface with timeout_action=DECLINE."""
    return HumanOverrideInterface(timeout_seconds=0.05, timeout_action="DECLINE")


@pytest.fixture
def offer_interface():
    """Interface configured with timeout_action=OFFER."""
    return HumanOverrideInterface(timeout_seconds=0.05, timeout_action="OFFER")


class TestGap08OverrideTimeout:
    def test_default_timeout_action_is_decline(self):
        """HumanOverrideInterface default timeout_action must be DECLINE."""
        iface = HumanOverrideInterface()
        assert iface.timeout_action == "DECLINE"

    def test_offer_timeout_action_configured(self, offer_interface):
        """Licensee can configure timeout_action=OFFER."""
        assert offer_interface.timeout_action == "OFFER"

    def test_invalid_timeout_action_raises(self):
        """Invalid timeout_action values must be rejected at construction."""
        with pytest.raises(ValueError, match="timeout_action"):
            HumanOverrideInterface(timeout_action="APPROVE")

    def test_resolve_expired_decline(self, decline_interface):
        """Expired request resolves to DECLINE when timeout_action=DECLINE."""
        req = decline_interface.request_override(
            uetr="uetr-1", original_decision="OFFER",
            ai_confidence=0.7, reason="High PD"
        )
        time.sleep(0.1)  # Let the 50ms timeout elapse
        result = decline_interface.resolve_expired(req.request_id)
        assert result == "DECLINE"

    def test_resolve_expired_offer(self, offer_interface):
        """Expired request resolves to OFFER when timeout_action=OFFER."""
        req = offer_interface.request_override(
            uetr="uetr-2", original_decision="OFFER",
            ai_confidence=0.6, reason="Borderline PD"
        )
        time.sleep(0.1)
        result = offer_interface.resolve_expired(req.request_id)
        assert result == "OFFER"

    def test_resolve_non_expired_raises(self, decline_interface):
        """Resolving a non-expired request must raise ValueError."""
        req = decline_interface.request_override(
            uetr="uetr-3", original_decision="OFFER",
            ai_confidence=0.5, reason="Test"
        )
        # Request is fresh — not expired yet
        with pytest.raises(ValueError, match="not yet expired"):
            decline_interface.resolve_expired(req.request_id)

    def test_resolve_unknown_raises(self, decline_interface):
        """Resolving an unknown request ID must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown override request"):
            decline_interface.resolve_expired("nonexistent-id")

    def test_resolve_removes_from_pending(self, decline_interface):
        """After resolve_expired, the request is removed from pending list."""
        req = decline_interface.request_override(
            uetr="uetr-4", original_decision="OFFER",
            ai_confidence=0.8, reason="Test"
        )
        time.sleep(0.1)
        decline_interface.resolve_expired(req.request_id)
        assert not decline_interface.is_pending(req.request_id)
        assert len(decline_interface.get_pending_overrides()) == 0
