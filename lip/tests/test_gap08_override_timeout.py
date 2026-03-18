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


class TestEPG26ReentryContextStore:
    """EPG-26 regression: context store enables pipeline re-entry after human approval."""

    def test_store_and_pop_context(self):
        iface = HumanOverrideInterface()
        sentinel = object()
        iface.store_context("req-abc", sentinel)
        assert iface.pop_context("req-abc") is sentinel

    def test_pop_missing_returns_none(self):
        iface = HumanOverrideInterface()
        assert iface.pop_context("nonexistent") is None

    def test_pop_is_destructive(self):
        iface = HumanOverrideInterface()
        iface.store_context("req-xyz", "event_data")
        iface.pop_context("req-xyz")
        assert iface.pop_context("req-xyz") is None

    def test_full_reentry_flow_with_c7(self):
        """End-to-end: first pass parks, second pass with APPROVE produces OFFER."""
        from unittest.mock import MagicMock

        from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
        from lip.common.borrower_registry import BorrowerRegistry

        override_iface = HumanOverrideInterface(timeout_seconds=60)

        registry = BorrowerRegistry()
        registry.enroll("BORROW1")

        agent = ExecutionAgent(
            kill_switch=MagicMock(
                should_halt_new_offers=MagicMock(return_value=False),
                is_active=MagicMock(return_value=False),
            ),
            decision_logger=MagicMock(),
            human_override=override_iface,
            degraded_mode_manager=MagicMock(
                should_halt_new_offers=MagicMock(return_value=False),
                get_state_dict=MagicMock(return_value={
                    "degraded_mode": False, "gpu_fallback": False, "kms_unavailable_gap": False,
                }),
            ),
            config=ExecutionConfig(
                borrower_registry=registry,
                require_human_review_above_pd=0.10,  # low threshold — PD 0.5 triggers review
            ),
        )

        payment_ctx = {
            "uetr": "uetr-epg26",
            "individual_payment_id": "ipid-001",
            "sending_bic": "BORROW1",
            "failure_probability": 0.9,
            "pd_score": 0.50,           # above 0.10 → human review triggered
            "fee_bps": 350,
            "loan_amount": 50000,
            "original_payment_amount_usd": "50000",
            "dispute_class": "NOT_DISPUTE",
            "aml_passed": True,
            "maturity_days": 7,
            "rejection_code": "AM04",
            "rejection_class": "CLASS_A",
            "corridor": "USD_EUR",
            "currency": "USD",
        }

        # --- First pass: parks for human review ---
        result1 = agent.process_payment(payment_ctx)
        assert result1["status"] == "PENDING_HUMAN_REVIEW"
        request_id = result1["override_request_id"]
        assert request_id is not None

        # Caller stores context
        override_iface.store_context(request_id, payment_ctx)

        # Operator approves
        override_iface.submit_response(
            request_id,
            decision=__import__(
                "lip.c7_execution_agent.human_override", fromlist=["OverrideDecision"]
            ).OverrideDecision.APPROVE,
            operator_id="operator-001",
            justification="Reviewed — legitimate payment",
        )
        ctx_back = override_iface.pop_context(request_id)
        assert ctx_back is not None

        # --- Re-entry pass: human_override_decision="APPROVE" bypasses gate ---
        ctx_back["human_override_decision"] = "APPROVE"
        result2 = agent.process_payment(ctx_back)
        # Should proceed past the human review gate (OFFER or DECLINE based on PD logic)
        assert result2["status"] != "PENDING_HUMAN_REVIEW"
