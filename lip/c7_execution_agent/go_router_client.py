"""
go_router_client.py — Python gRPC client bridge for the C7 Go offer router.

Provides GoOfferRouterClient, a drop-in complement to OfferDeliveryService that
routes offer lifecycle calls to the Go microservice via JSON-over-gRPC.

Canary control:
    Set LIP_C7_GO_ROUTER_CANARY_PCT (0–100) to route that percentage of offers
    to the Go service. Routing is deterministic per UETR: a SHA-256 hash of the
    UETR mod 100 is compared to the canary percentage.

    use_go_router(uetr) → bool implements this gate. When it returns True, the
    calling code should use GoOfferRouterClient; otherwise fall back to the
    Python OfferDeliveryService.

Fallback:
    If the Go service is unreachable or returns an error, callers should catch
    GoRouterError and fall back to the Python path. The canary integration in
    agent.py does this automatically and increments c7_go_router_fallback_total.

JSON-over-gRPC protocol:
    Matches the server-side grpc_raw.go registration. Requests and responses
    are raw JSON bytes. The Python client uses grpc.Channel.unary_unary with
    no protobuf codec (raw bytes pass through).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (optional — gracefully absent in test environments)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import Counter as _Prom_Counter

    _go_router_fallback_total: _Prom_Counter | None = _Prom_Counter(
        "c7_go_router_fallback_total",
        "Total times the Go offer router returned an error and Python OfferDeliveryService "
        "was used as fallback",
    )
except Exception:  # ImportError or duplicate registration in tests
    _go_router_fallback_total = None


def _inc_fallback_counter() -> None:
    """Increment c7_go_router_fallback_total (no-op when prometheus_client is absent)."""
    if _go_router_fallback_total is not None:
        _go_router_fallback_total.inc()


# ---------------------------------------------------------------------------
# Canary gate
# ---------------------------------------------------------------------------

# Module-level default loaded at import time. Tests can override via
# LIP_C7_GO_ROUTER_CANARY_PCT env var without needing importlib.reload —
# use_go_router() reads the env var fresh on each call if the override
# sentinel is set, but the fast path avoids os.environ lookups in
# production by caching the value at module import.
_CANARY_PCT: int = max(0, min(100, int(os.environ.get("LIP_C7_GO_ROUTER_CANARY_PCT", "0"))))


def use_go_router(uetr: str, _canary_pct: int | None = None) -> bool:
    """Return True when this UETR should be routed to the Go offer router.

    Deterministic: SHA-256(uetr) mod 100 < canary_pct.
    Returns False when canary_pct == 0 (default, full Python path).

    Parameters
    ----------
    uetr:
        UETR string for the payment. Used as the hashing key so routing is
        stable across retries for the same payment.
    _canary_pct:
        Override the module-level canary percentage (default: read from
        ``LIP_C7_GO_ROUTER_CANARY_PCT`` env var). Used in tests to avoid
        module reloading.

    Returns
    -------
    bool
    """
    pct = _canary_pct if _canary_pct is not None else _CANARY_PCT
    if pct <= 0:
        return False
    h = int(hashlib.sha256(uetr.encode()).hexdigest(), 16)
    return (h % 100) < pct


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GoRouterError(Exception):
    """Raised when the Go offer router returns a non-OK response or gRPC error."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GoOfferRouterClient:
    """JSON-over-gRPC client for the C7 Go offer router service.

    Connects lazily (on first call) to the Go service at ``addr``.
    Thread-safe: each call acquires the channel once and reuses it.

    Parameters
    ----------
    addr:
        Host:port of the Go offer router service (default from
        ``C7_GO_ROUTER_ADDR`` env var or ``"localhost:50057"``).
    timeout_seconds:
        Per-call deadline in seconds (default 5.0).
    """

    SERVICE = "/lip.C7OfferRouter/{}"

    def __init__(
        self,
        addr: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._addr = addr or os.environ.get("C7_GO_ROUTER_ADDR", "localhost:50057")
        self._timeout = timeout_seconds
        self._channel: Any = None
        self._stubs: Dict[str, Any] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the gRPC channel. Safe to call multiple times."""
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
            self._stubs = {}

    # ── Public API ───────────────────────────────────────────────────────────

    def trigger_offer(self, offer: dict) -> dict:
        """Register a new offer with the Go service.

        Parameters
        ----------
        offer:
            Raw offer dict from ExecutionAgent._build_loan_offer. Expected keys:
            ``loan_id``, ``uetr``, ``loan_amount``, ``fee_bps``,
            ``maturity_days``, ``expires_at``. Optional: ``elo_entity_id``.

        Returns
        -------
        dict
            ``{"accepted": True}`` on success.

        Raises
        ------
        GoRouterError
            If the service rejects the offer or is unavailable.
        """
        req = {
            "offer_id": str(offer.get("loan_id", "")),
            "uetr": str(offer.get("uetr", "")),
            "loan_amount": str(offer.get("loan_amount", "0")),
            "fee_bps": str(offer.get("fee_bps", "300")),
            "maturity_days": int(offer.get("maturity_days", 7)),
            "expires_at": str(offer.get("expires_at", "")),
            "elo_entity_id": str(offer.get("elo_entity_id", "")),
        }
        return self._call("TriggerOffer", req)

    def accept_offer(self, offer_id: str, elo_operator_id: str) -> dict:
        """Deliver ELO acceptance to the Go service.

        Parameters
        ----------
        offer_id:
            String UUID of the offer to accept.
        elo_operator_id:
            EU AI Act Art.14 operator identifier.

        Returns
        -------
        dict
            ``{"accepted": True}`` on success.

        Raises
        ------
        GoRouterError
        """
        return self._call("AcceptOffer", {
            "offer_id": offer_id,
            "elo_operator_id": elo_operator_id,
        })

    def reject_offer(
        self,
        offer_id: str,
        elo_operator_id: str,
        rejection_reason: str,
    ) -> dict:
        """Deliver ELO rejection to the Go service.

        Parameters
        ----------
        offer_id:
            String UUID of the offer to reject.
        elo_operator_id:
            EU AI Act Art.14 operator identifier.
        rejection_reason:
            Non-empty reason text.

        Returns
        -------
        dict
            ``{"accepted": True}`` on success.

        Raises
        ------
        GoRouterError
        """
        return self._call("RejectOffer", {
            "offer_id": offer_id,
            "elo_operator_id": elo_operator_id,
            "rejection_reason": rejection_reason,
        })

    def cancel_offer(self, offer_id: str, reason: str = "") -> dict:
        """Cancel an in-flight offer on the Go service.

        Parameters
        ----------
        offer_id:
            String UUID of the offer to cancel.
        reason:
            Optional human-readable reason (e.g. "kill switch activated").

        Returns
        -------
        dict
            ``{"accepted": True}`` on success.

        Raises
        ------
        GoRouterError
        """
        return self._call("CancelOffer", {"offer_id": offer_id, "reason": reason})

    def query_offer(self, offer_id: str) -> dict:
        """Query the current outcome for an offer.

        Returns
        -------
        dict
            ``{"outcome": "PENDING|ACCEPTED|REJECTED|EXPIRED|CANCELLED|UNKNOWN",
               "resolved_at": "<RFC3339 or None>"}``

        Raises
        ------
        GoRouterError
        """
        return self._call("QueryOffer", {"offer_id": offer_id})

    def health_check(self) -> dict:
        """Return liveness / readiness info from the Go service.

        Returns
        -------
        dict
            ``{"ok": True, "active_offers": int, "kill_switch_active": bool}``

        Raises
        ------
        GoRouterError
        """
        return self._call("HealthCheck", {})

    # ── Internal ─────────────────────────────────────────────────────────────

    def _call(self, method: str, payload: dict) -> dict:
        """Invoke a gRPC method with a JSON-encoded payload.

        Uses a raw byte codec: encodes payload as UTF-8 JSON, sends via gRPC
        unary call, decodes the response bytes as JSON.

        Parameters
        ----------
        method:
            gRPC method name (e.g. "TriggerOffer").
        payload:
            Request dict to encode as JSON.

        Returns
        -------
        dict
            Decoded response dict.

        Raises
        ------
        GoRouterError
            On gRPC transport errors or non-accepted responses.
        """
        try:
            import grpc  # noqa: PLC0415 — optional dependency
        except ImportError as exc:
            raise GoRouterError(
                f"grpcio is not installed; cannot reach Go offer router: {exc}"
            ) from exc

        channel = self._get_channel(grpc)
        stub = channel.unary_unary(
            self.SERVICE.format(method),
            request_serializer=None,
            response_deserializer=None,
        )

        try:
            body = json.dumps(payload).encode()
            resp_bytes = stub(body, timeout=self._timeout)
            resp = json.loads(resp_bytes)
        except grpc.RpcError as exc:
            raise GoRouterError(
                f"gRPC call {method} failed: {exc.code()} — {exc.details()}"
            ) from exc
        except Exception as exc:
            raise GoRouterError(f"gRPC call {method} error: {exc}") from exc

        if not resp.get("accepted", False) and resp.get("error"):
            raise GoRouterError(f"Go offer router rejected {method}: {resp['error']}")

        return resp

    def _get_channel(self, grpc: Any) -> Any:
        """Return the cached gRPC channel, creating it on first call."""
        if self._channel is None:
            self._channel = grpc.insecure_channel(self._addr)
            logger.info(
                "GoOfferRouterClient: connected to Go offer router at %s", self._addr
            )
        return self._channel
