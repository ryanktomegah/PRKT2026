"""
query_metering.py — Regulatory API query metering and budget enforcement.

Sprint 6 (P10/C8 extension): per-query metering for billing and privacy-budget
controls on regulator subscriptions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .regulator_subscription import RegulatorSubscriptionToken


class QueryBudgetExceededError(RuntimeError):
    """Raised when a regulator has consumed the monthly query budget."""


class PrivacyBudgetExceededError(RuntimeError):
    """Raised when a regulator has consumed the monthly privacy budget."""


@dataclass(frozen=True)
class QueryMeterEntry:
    """Immutable record of a single regulatory API query."""

    query_id: str
    regulator_id: str
    endpoint: str
    corridors_queried: list[str]
    epsilon_consumed: float
    response_latency_ms: int
    timestamp: datetime
    billing_amount_usd: Decimal
    hmac_signature: str


class RegulatoryQueryMetering:
    """In-memory query metering with monthly budget enforcement."""

    def __init__(self, metering_key: bytes = b"") -> None:
        self._metering_key = metering_key
        self._entries: list[QueryMeterEntry] = []
        self._monthly_queries: dict[tuple[str, str], int] = {}
        self._monthly_epsilon: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _month_bucket(ts: datetime) -> str:
        return ts.strftime("%Y-%m")

    def assert_within_budget(
        self,
        token: RegulatorSubscriptionToken,
        epsilon_cost: float,
        as_of: Optional[datetime] = None,
    ) -> None:
        """Raise if recording another query would exceed token budgets."""
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        key = (token.regulator_id, self._month_bucket(now))
        with self._lock:
            query_count = self._monthly_queries.get(key, 0)
            epsilon_used = self._monthly_epsilon.get(key, 0.0)

        if query_count + 1 > token.query_budget_monthly:
            raise QueryBudgetExceededError(
                f"Monthly query budget exhausted for regulator_id={token.regulator_id}"
            )

        epsilon_next = epsilon_used + float(epsilon_cost)
        # tiny tolerance for floating-point drift
        if epsilon_next > token.privacy_budget_allocation + 1e-12:
            raise PrivacyBudgetExceededError(
                f"Privacy budget exhausted for regulator_id={token.regulator_id}"
            )

    def record_query(
        self,
        token: RegulatorSubscriptionToken,
        endpoint: str,
        corridors_queried: list[str],
        epsilon_consumed: float,
        response_latency_ms: int,
        billing_amount_usd: Decimal,
        at: Optional[datetime] = None,
    ) -> QueryMeterEntry:
        """Record one query and update monthly budget usage."""
        if response_latency_ms < 0:
            raise ValueError("response_latency_ms must be non-negative")

        now = at.astimezone(timezone.utc) if at else datetime.now(timezone.utc)
        self.assert_within_budget(token=token, epsilon_cost=epsilon_consumed, as_of=now)
        month = self._month_bucket(now)
        key = (token.regulator_id, month)

        query_id = f"QRY-{uuid.uuid4().hex[:12].upper()}"
        signature = self._sign_entry(
            query_id=query_id,
            regulator_id=token.regulator_id,
            endpoint=endpoint,
            corridors_queried=corridors_queried,
            epsilon_consumed=epsilon_consumed,
            response_latency_ms=response_latency_ms,
            timestamp=now,
            billing_amount_usd=billing_amount_usd,
        )

        entry = QueryMeterEntry(
            query_id=query_id,
            regulator_id=token.regulator_id,
            endpoint=endpoint,
            corridors_queried=list(corridors_queried),
            epsilon_consumed=float(epsilon_consumed),
            response_latency_ms=response_latency_ms,
            timestamp=now,
            billing_amount_usd=billing_amount_usd,
            hmac_signature=signature,
        )

        with self._lock:
            self._entries.append(entry)
            self._monthly_queries[key] = self._monthly_queries.get(key, 0) + 1
            self._monthly_epsilon[key] = self._monthly_epsilon.get(key, 0.0) + float(
                epsilon_consumed
            )

        return entry

    def get_usage(
        self,
        regulator_id: str,
        as_of: Optional[datetime] = None,
    ) -> dict[str, float | int]:
        """Return current-month usage summary for one regulator."""
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        key = (regulator_id, self._month_bucket(now))
        with self._lock:
            return {
                "query_count": self._monthly_queries.get(key, 0),
                "epsilon_consumed": self._monthly_epsilon.get(key, 0.0),
            }

    def _sign_entry(
        self,
        query_id: str,
        regulator_id: str,
        endpoint: str,
        corridors_queried: list[str],
        epsilon_consumed: float,
        response_latency_ms: int,
        timestamp: datetime,
        billing_amount_usd: Decimal,
    ) -> str:
        if not self._metering_key:
            return ""
        payload = {
            "query_id": query_id,
            "regulator_id": regulator_id,
            "endpoint": endpoint,
            "corridors_queried": sorted(corridors_queried),
            "epsilon_consumed": float(epsilon_consumed),
            "response_latency_ms": response_latency_ms,
            "timestamp": timestamp.isoformat(),
            "billing_amount_usd": str(billing_amount_usd),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._metering_key, raw, hashlib.sha256).hexdigest()
