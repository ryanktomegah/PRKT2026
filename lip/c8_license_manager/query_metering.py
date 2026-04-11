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
    corridors_queried: tuple[str, ...]
    epsilon_consumed: float
    response_latency_ms: int
    timestamp: datetime
    billing_amount_usd: Decimal
    hmac_signature: str


class RegulatoryQueryMetering:
    """In-memory query metering with monthly budget enforcement."""

    def __init__(
        self,
        metering_key: bytes = b"",
        *,
        single_replica: bool = False,
    ) -> None:
        # single_replica is checked first so that callers who omit it get the
        # informative "single_replica=True required" error, not a key error.
        if not single_replica:
            raise ValueError(
                "RegulatoryQueryMetering uses in-memory state that resets on "
                "redeploy and multiplies N× across replicas. Pass "
                "single_replica=True to acknowledge single-replica constraint, "
                "or configure a Redis-backed store (B3-04)."
            )
        # B3-08: an empty HMAC key produces trivially forgeable audit entries.
        # Callers must supply a real secret, e.g. loaded from an env var or
        # secrets manager. The default b"" is left only to avoid a TypeError
        # on the common test that calls RegulatoryQueryMetering() (no args)
        # which must still get the single_replica ValueError above.
        if not metering_key:
            raise ValueError(
                "metering_key must be non-empty bytes. An empty key produces "
                "trivially forgeable HMAC audit entries. Load the signing key "
                "from an env var or secrets manager (B3-08)."
            )
        import logging
        logging.getLogger(__name__).warning(
            "RegulatoryQueryMetering running with single_replica=True — "
            "state will not survive restarts or scale across replicas"
        )
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
        """Raise if recording another query would exceed token budgets.

        This is a fast-path pre-check that callers may use to avoid expensive
        work before calling record_query.  It is NOT the enforcement point —
        record_query performs an atomic check-and-increment under a single lock
        hold (B3-01 fix).  Two concurrent threads that both pass this pre-check
        will still be serialised correctly inside record_query.
        """
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
        """Record one query and update monthly budget usage.

        B3-01: the budget check and counter increment are atomic — both happen
        under a single ``self._lock`` hold.  The old code called
        ``assert_within_budget`` (which acquired/released the lock) and then
        took the lock *again* to increment, leaving a TOCTOU window where two
        threads at budget−1 could both pass the check and both increment.
        """
        if response_latency_ms < 0:
            raise ValueError("response_latency_ms must be non-negative")

        now = at.astimezone(timezone.utc) if at else datetime.now(timezone.utc)
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
            corridors_queried=tuple(corridors_queried),
            epsilon_consumed=float(epsilon_consumed),
            response_latency_ms=response_latency_ms,
            timestamp=now,
            billing_amount_usd=billing_amount_usd,
            hmac_signature=signature,
        )

        # B3-01: atomic check-and-increment under a single lock hold.
        with self._lock:
            query_count = self._monthly_queries.get(key, 0)
            epsilon_used = self._monthly_epsilon.get(key, 0.0)

            if query_count + 1 > token.query_budget_monthly:
                raise QueryBudgetExceededError(
                    f"Monthly query budget exhausted for regulator_id={token.regulator_id}"
                )
            epsilon_next = epsilon_used + float(epsilon_consumed)
            if epsilon_next > token.privacy_budget_allocation + 1e-12:
                raise PrivacyBudgetExceededError(
                    f"Privacy budget exhausted for regulator_id={token.regulator_id}"
                )

            self._entries.append(entry)
            self._monthly_queries[key] = query_count + 1
            self._monthly_epsilon[key] = epsilon_next

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

    def get_billing_summary(
        self,
        regulator_id: str,
        as_of: Optional[datetime] = None,
    ) -> dict:
        """Return comprehensive billing summary for one regulator (current month)."""
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        month = self._month_bucket(now)

        with self._lock:
            matching = [
                e
                for e in self._entries
                if e.regulator_id == regulator_id
                and self._month_bucket(e.timestamp) == month
            ]

        query_count = len(matching)
        epsilon_consumed = sum(e.epsilon_consumed for e in matching)
        total_billing = sum(e.billing_amount_usd for e in matching)

        if matching:
            latencies = [e.response_latency_ms for e in matching]
            mean_latency_ms = sum(latencies) / len(latencies)
            sorted_latencies = sorted(latencies)
            p95_latency_ms = sorted_latencies[min(int(0.95 * len(sorted_latencies)), len(sorted_latencies) - 1)]
        else:
            mean_latency_ms = 0.0
            p95_latency_ms = 0

        endpoints_breakdown: dict[str, int] = {}
        for e in matching:
            endpoints_breakdown[e.endpoint] = endpoints_breakdown.get(e.endpoint, 0) + 1

        corridors_set: set[str] = set()
        for e in matching:
            for c in e.corridors_queried:
                corridors_set.add(c)
        corridors_queried = sorted(corridors_set)

        timestamps = [e.timestamp for e in matching]
        first_query_at = min(timestamps).isoformat() if timestamps else None
        last_query_at = max(timestamps).isoformat() if timestamps else None

        return {
            "query_count": query_count,
            "epsilon_consumed": epsilon_consumed,
            "total_billing_usd": str(total_billing),
            "mean_latency_ms": mean_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "endpoints_breakdown": endpoints_breakdown,
            "corridors_queried": corridors_queried,
            "first_query_at": first_query_at,
            "last_query_at": last_query_at,
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
