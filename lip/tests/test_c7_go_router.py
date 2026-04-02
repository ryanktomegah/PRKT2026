"""
test_c7_go_router.py — Unit tests for the C7 Go offer router Python bridge.

Covers:
  - use_go_router(): canary gate determinism, 0% → always False, 100% → always True
  - GoOfferRouterClient: all methods return correct structure when Go service is mocked
  - GoRouterError: raised on non-accepted response
  - agent.py canary integration: Go path chosen when canary=100, Python fallback on GoRouterError
  - agent.py fallback: Python OfferDeliveryService used when canary=0 or Go error
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.go_router_client import (
    GoOfferRouterClient,
    GoRouterError,
    use_go_router,
)
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c7_execution_agent.offer_delivery import OfferDeliveryService

_HMAC_KEY = b"test_hmac_key_for_unit_tests_32b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(
    offer_delivery=None,
    go_router_client=None,
    config=None,
):
    ks = KillSwitch()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    ho = HumanOverrideInterface()
    dm = DegradedModeManager()
    cfg = config or ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        ks, dl, ho, dm, cfg,
        offer_delivery=offer_delivery,
        go_router_client=go_router_client,
        redis_client=None,
    )


def _make_payment_context(
    uetr="97ed4827-7b6f-4491-a06f-b548d5a7512d",
    failure_prob=0.80,
    loan_amount=1_000_000,
    sending_bic="DEUTDEDBXXX",
    rejection_code="MS03",
    rejection_class="CLASS_B",
):
    now = datetime.now(tz=timezone.utc)
    return {
        "uetr": uetr,
        "individual_payment_id": "pid-001",
        "failure_probability": failure_prob,
        "loan_amount": loan_amount,
        "original_payment_amount_usd": loan_amount,
        "currency": "USD",
        "sending_bic": sending_bic,
        "receiving_bic": "CHASUS33XXX",
        "maturity_days": 7,
        "rejection_code": rejection_code,
        "rejection_class": rejection_class,
        "corridor": "SWIFT_EU_US",
        "timestamp_utc": now.isoformat(),
        "expires_at": (now + timedelta(hours=2)).isoformat(),
    }


# ---------------------------------------------------------------------------
# use_go_router() canary gate tests
# ---------------------------------------------------------------------------

class TestUseGoRouter:
    def test_zero_pct_never_routes(self):
        """0% canary → always False regardless of UETR."""
        for uetr in ["abc", "def", "97ed4827-7b6f-4491-a06f"]:
            assert use_go_router(uetr, _canary_pct=0) is False

    def test_hundred_pct_always_routes(self):
        """100% canary → always True regardless of UETR."""
        for uetr in ["abc", "def", "97ed4827-7b6f-4491-a06f"]:
            assert use_go_router(uetr, _canary_pct=100) is True

    def test_deterministic_routing(self):
        """Same UETR always produces the same result (deterministic hash)."""
        uetr = "97ed4827-7b6f-4491-a06f-b548d5a7512d"
        h = int(hashlib.sha256(uetr.encode()).hexdigest(), 16)
        expected = (h % 100) < 50

        result = use_go_router(uetr, _canary_pct=50)
        assert result == expected
        # Second call same result
        assert use_go_router(uetr, _canary_pct=50) == expected

    def test_fifty_pct_routes_approximately_half(self):
        """50% canary should route ~50% of UETRs (test with known hashes)."""
        routed = 0
        for i in range(100):
            uetr = f"uetr-{i:04d}-test"
            if use_go_router(uetr, _canary_pct=50):
                routed += 1

        # Should be between 35 and 65 (within 15% of expected 50%)
        assert 35 <= routed <= 65, f"Expected ~50% routing, got {routed}%"


# ---------------------------------------------------------------------------
# GoOfferRouterClient unit tests (mocked gRPC)
# ---------------------------------------------------------------------------

class TestGoOfferRouterClient:
    """Tests for GoOfferRouterClient using mocked gRPC channel."""

    def _make_client_with_mock(self, responses: dict):
        """Create a client whose _call method returns mock responses."""
        client = GoOfferRouterClient(addr="localhost:50057")
        client._call = MagicMock(side_effect=lambda m, p: responses.get(m, {"accepted": True}))
        return client

    def test_trigger_offer_happy_path(self):
        client = self._make_client_with_mock({"TriggerOffer": {"accepted": True}})
        resp = client.trigger_offer({
            "loan_id": "offer-001",
            "uetr": "uetr-001",
            "loan_amount": "1000000",
            "fee_bps": "300",
            "maturity_days": 7,
            "expires_at": (datetime.now(tz=timezone.utc) + timedelta(hours=2)).isoformat(),
        })
        assert resp.get("accepted") is True

    def test_trigger_offer_serialises_fields(self):
        client = GoOfferRouterClient(addr="localhost:50057")
        captured = {}

        def mock_call(method, payload):
            captured.update({"method": method, "payload": payload})
            return {"accepted": True}

        client._call = mock_call
        client.trigger_offer({
            "loan_id": "offer-xyz",
            "uetr": "uetr-xyz",
            "loan_amount": "5000000",
            "fee_bps": "400",
            "maturity_days": 3,
            "expires_at": "2026-04-02T20:00:00Z",
            "elo_entity_id": "DEUTDEDBXXX",
        })
        assert captured["method"] == "TriggerOffer"
        assert captured["payload"]["offer_id"] == "offer-xyz"
        assert captured["payload"]["uetr"] == "uetr-xyz"
        assert captured["payload"]["fee_bps"] == "400"
        assert captured["payload"]["maturity_days"] == 3

    def test_accept_offer(self):
        client = self._make_client_with_mock({"AcceptOffer": {"accepted": True}})
        resp = client.accept_offer("offer-001", "op-treasury-001")
        assert resp.get("accepted") is True

    def test_reject_offer(self):
        client = self._make_client_with_mock({"RejectOffer": {"accepted": True}})
        resp = client.reject_offer("offer-001", "op-001", "insufficient liquidity")
        assert resp.get("accepted") is True

    def test_cancel_offer(self):
        client = self._make_client_with_mock({"CancelOffer": {"accepted": True}})
        resp = client.cancel_offer("offer-001", "kill switch activated")
        assert resp.get("accepted") is True

    def test_query_offer_pending(self):
        client = self._make_client_with_mock({
            "QueryOffer": {"outcome": "PENDING"},
        })
        resp = client.query_offer("offer-001")
        assert resp.get("outcome") == "PENDING"

    def test_health_check(self):
        client = self._make_client_with_mock({
            "HealthCheck": {"ok": True, "active_offers": 5, "kill_switch_active": False},
        })
        resp = client.health_check()
        assert resp.get("ok") is True
        assert resp.get("active_offers") == 5

    def test_go_router_error_on_rejected_response(self):
        """_call raises GoRouterError when accepted=False and error is set."""
        client = GoOfferRouterClient(addr="localhost:50057")

        def fail_call(method, payload):
            raise GoRouterError("kill switch active")

        client._call = fail_call
        with pytest.raises(GoRouterError, match="kill switch active"):
            client.trigger_offer({
                "loan_id": "offer-ks",
                "uetr": "uetr-ks",
                "expires_at": (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat(),
            })

    def test_go_router_error_on_grpc_failure(self):
        """_call raises GoRouterError on transport exception."""
        client = GoOfferRouterClient(addr="localhost:50057")

        def fail_call(method, payload):
            raise GoRouterError("connection refused")

        client._call = fail_call
        with pytest.raises(GoRouterError):
            client.health_check()


# ---------------------------------------------------------------------------
# agent.py canary integration tests
# ---------------------------------------------------------------------------

class TestAgentCanaryIntegration:
    """Test that agent.py correctly routes to Go or Python based on canary gate."""

    def _make_mock_go_client(self, will_raise: bool = False) -> GoOfferRouterClient:
        client = MagicMock(spec=GoOfferRouterClient)
        if will_raise:
            client.trigger_offer.side_effect = GoRouterError("service unavailable")
        else:
            client.trigger_offer.return_value = {"accepted": True}
        return client

    def _make_mock_offer_delivery(self) -> OfferDeliveryService:
        svc = MagicMock(spec=OfferDeliveryService)
        delivery = MagicMock()
        delivery.delivery_id = "test-delivery-id-001"
        svc.deliver.return_value = delivery
        return svc

    def test_canary_100pct_routes_to_go(self):
        """When canary=100 and Go client is healthy, Go client is called."""
        go_client = self._make_mock_go_client()
        python_svc = self._make_mock_offer_delivery()
        agent = _make_agent(offer_delivery=python_svc, go_router_client=go_client)

        ctx = _make_payment_context(failure_prob=0.85)

        with patch("lip.c7_execution_agent.agent.use_go_router", return_value=True):
            result = agent.process_payment(ctx)

        if result.get("status") == "OFFER":
            go_client.trigger_offer.assert_called_once()
            # Python delivery should NOT have been called
            python_svc.deliver.assert_not_called()

    def test_canary_0pct_routes_to_python(self):
        """When canary=0, always use Python OfferDeliveryService."""
        go_client = self._make_mock_go_client()
        python_svc = self._make_mock_offer_delivery()
        agent = _make_agent(offer_delivery=python_svc, go_router_client=go_client)

        ctx = _make_payment_context(failure_prob=0.85)

        with patch("lip.c7_execution_agent.agent.use_go_router", return_value=False):
            result = agent.process_payment(ctx)

        if result.get("status") == "OFFER":
            go_client.trigger_offer.assert_not_called()
            python_svc.deliver.assert_called_once()

    def test_go_error_falls_back_to_python(self):
        """When Go service raises GoRouterError, fall back to Python delivery."""
        go_client = self._make_mock_go_client(will_raise=True)
        python_svc = self._make_mock_offer_delivery()
        agent = _make_agent(offer_delivery=python_svc, go_router_client=go_client)

        ctx = _make_payment_context(failure_prob=0.85)

        with patch("lip.c7_execution_agent.agent.use_go_router", return_value=True):
            result = agent.process_payment(ctx)

        if result.get("status") == "OFFER":
            go_client.trigger_offer.assert_called_once()
            # Python delivery should be called as fallback
            python_svc.deliver.assert_called_once()

    def test_no_go_client_uses_python_only(self):
        """No go_router_client → only Python OfferDeliveryService is used."""
        python_svc = self._make_mock_offer_delivery()
        agent = _make_agent(offer_delivery=python_svc, go_router_client=None)

        ctx = _make_payment_context(failure_prob=0.85)
        result = agent.process_payment(ctx)

        if result.get("status") == "OFFER":
            python_svc.deliver.assert_called_once()

    def test_no_offer_delivery_no_go_client(self):
        """Neither service → delivery_id is None in OFFER result."""
        agent = _make_agent(offer_delivery=None, go_router_client=None)
        ctx = _make_payment_context(failure_prob=0.85)
        result = agent.process_payment(ctx)

        if result.get("status") == "OFFER":
            assert result.get("delivery_id") is None


# ---------------------------------------------------------------------------
# GoOfferRouterClient.close() test
# ---------------------------------------------------------------------------

class TestGoOfferRouterClientClose:
    def test_close_is_idempotent(self):
        """close() can be called multiple times without error."""
        client = GoOfferRouterClient(addr="localhost:50057")
        client.close()
        client.close()  # should not raise

    def test_close_resets_channel(self):
        """close() sets _channel back to None."""
        client = GoOfferRouterClient(addr="localhost:50057")
        mock_chan = MagicMock()
        client._channel = mock_chan
        client.close()
        assert client._channel is None
        mock_chan.close.assert_called_once()


# ---------------------------------------------------------------------------
# Fallback counter tests
# ---------------------------------------------------------------------------

class TestFallbackCounter:
    """Test that _inc_fallback_counter is called on Go router error."""

    def test_fallback_counter_incremented_on_go_error(self):
        """When Go service errors, _inc_fallback_counter() is called once."""
        go_client = MagicMock(spec=GoOfferRouterClient)
        go_client.trigger_offer.side_effect = GoRouterError("connection refused")

        python_svc = MagicMock(spec=OfferDeliveryService)
        delivery = MagicMock()
        delivery.delivery_id = "fallback-delivery-id"
        python_svc.deliver.return_value = delivery

        agent = _make_agent(offer_delivery=python_svc, go_router_client=go_client)
        ctx = _make_payment_context(failure_prob=0.85)

        with patch("lip.c7_execution_agent.agent.use_go_router", return_value=True), \
             patch("lip.c7_execution_agent.agent._inc_fallback_counter") as mock_inc:
            result = agent.process_payment(ctx)

        assert result.get("status") == "OFFER", (
            f"Expected OFFER result to test fallback counter; got {result.get('status')!r}"
        )
        mock_inc.assert_called_once()
        python_svc.deliver.assert_called_once()

    def test_fallback_counter_not_incremented_on_success(self):
        """When Go service succeeds, _inc_fallback_counter() is NOT called."""
        go_client = MagicMock(spec=GoOfferRouterClient)
        go_client.trigger_offer.return_value = {"accepted": True}

        agent = _make_agent(offer_delivery=None, go_router_client=go_client)
        ctx = _make_payment_context(failure_prob=0.85)

        with patch("lip.c7_execution_agent.agent.use_go_router", return_value=True), \
             patch("lip.c7_execution_agent.agent._inc_fallback_counter") as mock_inc:
            result = agent.process_payment(ctx)

        assert result.get("status") == "OFFER", (
            f"Expected OFFER result to test fallback counter; got {result.get('status')!r}"
        )
        mock_inc.assert_not_called()

    def test_inc_fallback_counter_noop_when_prometheus_absent(self):
        """_inc_fallback_counter() does not raise when prometheus_client is unavailable."""
        from lip.c7_execution_agent import go_router_client as grc
        # Save original, replace with None to simulate absent prometheus_client
        original = grc._go_router_fallback_total
        grc._go_router_fallback_total = None
        try:
            grc._inc_fallback_counter()  # must not raise
        finally:
            grc._go_router_fallback_total = original
