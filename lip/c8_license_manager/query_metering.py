"""
query_metering.py — Regulatory API query metering and budget enforcement.

Sprint 6 (P10/C8 extension): per-query metering for billing and privacy-budget
controls on regulator subscriptions.

Phase 2 T2.2a: A backend abstraction separates state storage from the HMAC/
ledger logic. Two backends ship today:

  * :class:`_InMemoryMeteringBackend` — dict + threading.Lock. Powers the
    existing ``single_replica=True`` opt-in. State resets on restart and
    multiplies N× across replicas; callers must acknowledge this.
  * :class:`_RedisMeteringBackend` — Redis-backed counters with a Lua script
    performing atomic check-and-increment of both the query counter and the
    epsilon counter under a single server round-trip. Safe across replicas.

Both backends expose the same ``atomic_record`` / ``get_usage`` /
``get_monthly_entries`` interface so ``RegulatoryQueryMetering`` has no
storage-specific code paths.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Protocol

from .regulator_subscription import RegulatorSubscriptionToken

logger = logging.getLogger(__name__)


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

    def to_json_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "regulator_id": self.regulator_id,
            "endpoint": self.endpoint,
            "corridors_queried": list(self.corridors_queried),
            "epsilon_consumed": self.epsilon_consumed,
            "response_latency_ms": self.response_latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "billing_amount_usd": str(self.billing_amount_usd),
            "hmac_signature": self.hmac_signature,
        }

    @classmethod
    def from_json_dict(cls, d: dict) -> "QueryMeterEntry":
        return cls(
            query_id=d["query_id"],
            regulator_id=d["regulator_id"],
            endpoint=d["endpoint"],
            corridors_queried=tuple(d["corridors_queried"]),
            epsilon_consumed=float(d["epsilon_consumed"]),
            response_latency_ms=int(d["response_latency_ms"]),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            billing_amount_usd=Decimal(d["billing_amount_usd"]),
            hmac_signature=d["hmac_signature"],
        )


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------

class _MeteringBackend(Protocol):
    """Storage interface for monthly query + epsilon counters and entries."""

    def atomic_record(
        self,
        regulator_id: str,
        month: str,
        max_queries: int,
        max_epsilon: float,
        epsilon_cost: float,
        entry: QueryMeterEntry,
    ) -> tuple[int, float]:
        """Atomically check budgets and append the entry if both pass.

        Returns (new_query_count, new_epsilon_used).
        Raises QueryBudgetExceededError or PrivacyBudgetExceededError.
        """
        ...

    def get_usage(self, regulator_id: str, month: str) -> dict[str, float | int]:
        ...

    def get_monthly_entries(self, regulator_id: str, month: str) -> list[QueryMeterEntry]:
        ...


# ---------------------------------------------------------------------------
# In-memory backend (single_replica=True path)
# ---------------------------------------------------------------------------

class _InMemoryMeteringBackend:
    """Dict + threading.Lock backend. Same semantics as the pre-T2.2a code."""

    def __init__(self) -> None:
        self._entries: list[QueryMeterEntry] = []
        self._monthly_queries: dict[tuple[str, str], int] = {}
        self._monthly_epsilon: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def atomic_record(
        self,
        regulator_id: str,
        month: str,
        max_queries: int,
        max_epsilon: float,
        epsilon_cost: float,
        entry: QueryMeterEntry,
    ) -> tuple[int, float]:
        key = (regulator_id, month)
        with self._lock:
            query_count = self._monthly_queries.get(key, 0)
            epsilon_used = self._monthly_epsilon.get(key, 0.0)

            if query_count + 1 > max_queries:
                raise QueryBudgetExceededError(
                    f"Monthly query budget exhausted for regulator_id={regulator_id}"
                )
            epsilon_next = epsilon_used + float(epsilon_cost)
            if epsilon_next > max_epsilon + 1e-12:
                raise PrivacyBudgetExceededError(
                    f"Privacy budget exhausted for regulator_id={regulator_id}"
                )

            self._entries.append(entry)
            self._monthly_queries[key] = query_count + 1
            self._monthly_epsilon[key] = epsilon_next
            return query_count + 1, epsilon_next

    def get_usage(self, regulator_id: str, month: str) -> dict[str, float | int]:
        key = (regulator_id, month)
        with self._lock:
            return {
                "query_count": self._monthly_queries.get(key, 0),
                "epsilon_consumed": self._monthly_epsilon.get(key, 0.0),
            }

    def get_monthly_entries(self, regulator_id: str, month: str) -> list[QueryMeterEntry]:
        with self._lock:
            return [
                e
                for e in self._entries
                if e.regulator_id == regulator_id
                and e.timestamp.strftime("%Y-%m") == month
            ]


# ---------------------------------------------------------------------------
# Redis backend (multi-replica path)
# ---------------------------------------------------------------------------

# Lua script guarantees atomic (check budgets → increment counters → append
# entry → refresh TTL) in a single server round-trip. Returning a tuple lets
# Python distinguish between budget-exceeded outcomes without racing the
# counters with a subsequent GET.
_ATOMIC_RECORD_LUA = """
local q_key = KEYS[1]
local e_key = KEYS[2]
local list_key = KEYS[3]
local max_q = tonumber(ARGV[1])
local max_e = tonumber(ARGV[2])
local e_cost = tonumber(ARGV[3])
local entry_json = ARGV[4]
local ttl = tonumber(ARGV[5])

local q = tonumber(redis.call('GET', q_key) or '0')
local e = tonumber(redis.call('GET', e_key) or '0')

if q + 1 > max_q then
    return {0, 'query_budget', tostring(q), tostring(e)}
end
local e_next = e + e_cost
if e_next > max_e + 1e-12 then
    return {0, 'privacy_budget', tostring(q), tostring(e)}
end

redis.call('INCR', q_key)
redis.call('SET', e_key, tostring(e_next))
redis.call('RPUSH', list_key, entry_json)
if ttl > 0 then
    redis.call('EXPIRE', q_key, ttl)
    redis.call('EXPIRE', e_key, ttl)
    redis.call('EXPIRE', list_key, ttl)
end
return {1, 'ok', tostring(q + 1), tostring(e_next)}
"""

# Two full months. Previous-month data must survive long enough for end-of-
# month billing reconciliation, but unbounded retention is not the metering
# store's job — long-term history lives in the append-only audit ledger.
_MONTHLY_TTL_SECONDS = 62 * 24 * 3600

_QUERY_KEY = "lip:c8:metering:q:{regulator_id}:{month}"
_EPSILON_KEY = "lip:c8:metering:e:{regulator_id}:{month}"
_ENTRIES_KEY = "lip:c8:metering:entries:{regulator_id}:{month}"


class _RedisMeteringBackend:
    """Redis-backed metering store. Safe across replicas.

    The client must be a ``redis.Redis``-compatible object (real client,
    cluster client, or a test double exposing ``eval`` / ``get`` / ``lrange``).
    """

    def __init__(self, redis_client: Any, *, ttl_seconds: int = _MONTHLY_TTL_SECONDS) -> None:
        self._r = redis_client
        self._ttl = ttl_seconds

    def _decode(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    def atomic_record(
        self,
        regulator_id: str,
        month: str,
        max_queries: int,
        max_epsilon: float,
        epsilon_cost: float,
        entry: QueryMeterEntry,
    ) -> tuple[int, float]:
        q_key = _QUERY_KEY.format(regulator_id=regulator_id, month=month)
        e_key = _EPSILON_KEY.format(regulator_id=regulator_id, month=month)
        list_key = _ENTRIES_KEY.format(regulator_id=regulator_id, month=month)
        entry_json = json.dumps(entry.to_json_dict(), sort_keys=True, separators=(",", ":"))

        result = self._r.eval(
            _ATOMIC_RECORD_LUA,
            3,
            q_key,
            e_key,
            list_key,
            str(max_queries),
            repr(float(max_epsilon)),
            repr(float(epsilon_cost)),
            entry_json,
            str(self._ttl),
        )
        status, reason, q_now, e_now = (self._decode(x) for x in result)

        if status == "0":
            if reason == "query_budget":
                raise QueryBudgetExceededError(
                    f"Monthly query budget exhausted for regulator_id={regulator_id}"
                )
            raise PrivacyBudgetExceededError(
                f"Privacy budget exhausted for regulator_id={regulator_id}"
            )
        return int(q_now), float(e_now)

    def get_usage(self, regulator_id: str, month: str) -> dict[str, float | int]:
        q_key = _QUERY_KEY.format(regulator_id=regulator_id, month=month)
        e_key = _EPSILON_KEY.format(regulator_id=regulator_id, month=month)
        q_raw = self._r.get(q_key)
        e_raw = self._r.get(e_key)
        return {
            "query_count": int(self._decode(q_raw)) if q_raw is not None else 0,
            "epsilon_consumed": float(self._decode(e_raw)) if e_raw is not None else 0.0,
        }

    def get_monthly_entries(self, regulator_id: str, month: str) -> list[QueryMeterEntry]:
        list_key = _ENTRIES_KEY.format(regulator_id=regulator_id, month=month)
        raw = self._r.lrange(list_key, 0, -1)
        return [QueryMeterEntry.from_json_dict(json.loads(self._decode(b))) for b in raw]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RegulatoryQueryMetering:
    """Query metering + monthly budget enforcement for regulator subscriptions.

    Two deployment modes:

    * ``single_replica=True`` — in-memory dict + lock. Only safe for single-
      replica deploys or local tests. State resets on restart.
    * ``redis_client=<redis.Redis>`` — Redis-backed counters with Lua atomic
      check-and-increment. Safe across multiple replicas. TTL = 62 days so
      previous-month data survives for end-of-month reconciliation.

    Exactly one of ``single_replica`` or ``redis_client`` must be supplied.
    """

    def __init__(
        self,
        metering_key: bytes = b"",
        *,
        single_replica: bool = False,
        redis_client: Any = None,
    ) -> None:
        # Mode selection precedes metering_key check so the common
        # ``RegulatoryQueryMetering()`` test call gets the single_replica
        # error, not a confusing empty-key error.
        if redis_client is not None and single_replica:
            raise ValueError(
                "Pass exactly one of single_replica=True or redis_client — "
                "not both. Redis-backed mode implies multi-replica safety."
            )
        if redis_client is None and not single_replica:
            raise ValueError(
                "RegulatoryQueryMetering uses in-memory state that resets on "
                "redeploy and multiplies N× across replicas. Pass "
                "single_replica=True to acknowledge single-replica constraint, "
                "or configure a Redis-backed store (B3-04)."
            )
        # B3-08: empty HMAC key is trivially forgeable.
        if not metering_key:
            raise ValueError(
                "metering_key must be non-empty bytes. An empty key produces "
                "trivially forgeable HMAC audit entries. Load the signing key "
                "from an env var or secrets manager (B3-08)."
            )

        self._metering_key = metering_key
        self._backend: _MeteringBackend
        if redis_client is not None:
            self._backend = _RedisMeteringBackend(redis_client)
            logger.info(
                "RegulatoryQueryMetering running in Redis-backed multi-replica mode"
            )
        else:
            self._backend = _InMemoryMeteringBackend()
            logger.warning(
                "RegulatoryQueryMetering running with single_replica=True — "
                "state will not survive restarts or scale across replicas"
            )

    @staticmethod
    def _month_bucket(ts: datetime) -> str:
        return ts.strftime("%Y-%m")

    def assert_within_budget(
        self,
        token: RegulatorSubscriptionToken,
        epsilon_cost: float,
        as_of: Optional[datetime] = None,
    ) -> None:
        """Best-effort pre-check. Not the enforcement point — ``record_query``
        is atomic under the backend lock/Lua script. Two concurrent callers
        that both pass this pre-check will still be serialised correctly.
        """
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        usage = self._backend.get_usage(token.regulator_id, self._month_bucket(now))
        query_count = int(usage["query_count"])
        epsilon_used = float(usage["epsilon_consumed"])

        if query_count + 1 > token.query_budget_monthly:
            raise QueryBudgetExceededError(
                f"Monthly query budget exhausted for regulator_id={token.regulator_id}"
            )
        epsilon_next = epsilon_used + float(epsilon_cost)
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
        """Record one query and update monthly budget usage atomically.

        B3-01: the budget check and counter increment are atomic in both
        backends — lock-protected for in-memory, Lua-script-protected for
        Redis. No TOCTOU window between the check and the increment.
        """
        if response_latency_ms < 0:
            raise ValueError("response_latency_ms must be non-negative")

        now = at.astimezone(timezone.utc) if at else datetime.now(timezone.utc)
        month = self._month_bucket(now)

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

        self._backend.atomic_record(
            regulator_id=token.regulator_id,
            month=month,
            max_queries=token.query_budget_monthly,
            max_epsilon=token.privacy_budget_allocation,
            epsilon_cost=float(epsilon_consumed),
            entry=entry,
        )
        return entry

    def get_usage(
        self,
        regulator_id: str,
        as_of: Optional[datetime] = None,
    ) -> dict[str, float | int]:
        """Return current-month usage summary for one regulator."""
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        return self._backend.get_usage(regulator_id, self._month_bucket(now))

    def get_billing_summary(
        self,
        regulator_id: str,
        as_of: Optional[datetime] = None,
    ) -> dict:
        """Return comprehensive billing summary for one regulator (current month)."""
        now = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
        month = self._month_bucket(now)
        matching = self._backend.get_monthly_entries(regulator_id, month)

        query_count = len(matching)
        epsilon_consumed = sum(e.epsilon_consumed for e in matching)
        total_billing = sum(e.billing_amount_usd for e in matching)

        if matching:
            latencies = [e.response_latency_ms for e in matching]
            mean_latency_ms = sum(latencies) / len(latencies)
            sorted_latencies = sorted(latencies)
            p95_latency_ms = sorted_latencies[
                min(int(0.95 * len(sorted_latencies)), len(sorted_latencies) - 1)
            ]
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
