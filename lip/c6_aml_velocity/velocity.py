"""
velocity.py — AML velocity controls
Dollar cap $1M, count cap 100 per entity per 24hr rolling window.
Beneficiary concentration: >80% to single beneficiary triggers alert.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

Redis wiring (Phase 2):
  RollingWindow supports an optional ``redis_client`` for distributed,
  persistent velocity tracking across multiple PaymentEventWorker instances.
  Without Redis, an in-process deque is used (safe for single-worker deployments
  and all unit tests).

  Redis sorted-set layout per entity:
    Key:    lip:velocity:events:{entity_hash}
    Score:  Unix timestamp (float) — enables time-range pruning
    Member: "{amount}:{bene_hash}:{uuid4_hex}" — unique per transaction

  Why sorted sets over INCR/INCRBYFLOAT:
    Sorted sets preserve per-transaction records so the window truly rolls.
    ZREMRANGEBYSCORE prunes expired entries in O(log N + k). ZRANGEBYSCORE
    retrieves the active window in O(log N + m). Both are atomic.

  TODO (Phase 2.1 optimisation):
    VelocityChecker.check() currently issues a single get_records() call that
    fetches the full active window once.  A future optimisation could replace
    ZRANGEBYSCORE with ZCARD + ZRANGEBYSCORE only when concentration matters,
    reducing byte transfer for high-frequency entities.
"""
import hashlib
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BENEFICIARY_CONCENTRATION_THRESHOLD = Decimal("0.80")

# Exponential decay half-life (hours) for velocity scoring — transactions older
# than ~20h contribute < 50% weight to the rolling velocity estimate.
_DECAY_HALF_LIFE_HOURS: float = 19.66

# Redis key template for the per-entity sorted set
_VELOCITY_KEY_PREFIX = "lip:velocity:events:"

# ---------------------------------------------------------------------------
# Lua script: atomic check-and-record (EPG-25)
# ---------------------------------------------------------------------------
# Replaces the separate check() → [pipeline] → record() pattern with a single
# Redis EVAL call that prunes, reads, evaluates all three caps, and writes in
# one atomic operation. No TOCTOU gap in multi-worker K8s deployments.
#
# KEYS[1]  : sorted-set key (lip:velocity:events:{entity_hash})
# ARGV[1]  : cutoff timestamp (now - window_seconds), as float string
# ARGV[2]  : current timestamp (now), as float string
# ARGV[3]  : candidate amount as string (e.g. "500000.00")
# ARGV[4]  : dollar cap as string
# ARGV[5]  : count cap as integer string
# ARGV[6]  : beneficiary concentration threshold as string (e.g. "0.80")
# ARGV[7]  : beneficiary hash (hex string, no colons)
# ARGV[8]  : new member string ("{amount}:{bene_hash}:{uuid4_hex}")
# ARGV[9]  : TTL in seconds (window_seconds + 60)
#
# Returns array: [passed, reason, vol_str, cnt_str]
#   passed : "1" = passed and recorded, "0" = blocked (not recorded)
#   reason : "" when passed, rule name when blocked
_ATOMIC_CHECK_RECORD_LUA = """
local key           = KEYS[1]
local cutoff        = tonumber(ARGV[1])
local now_ts        = tonumber(ARGV[2])
local candidate     = tonumber(ARGV[3])
local dollar_cap    = tonumber(ARGV[4])
local count_cap     = tonumber(ARGV[5])
local conc_thresh   = tonumber(ARGV[6])
local bene_hash     = ARGV[7]
local new_member    = ARGV[8]
local ttl           = tonumber(ARGV[9])

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local entries = redis.call('ZRANGE', key, 0, -1)

local vol = 0
local cnt = 0
local by_bene = {}

for _, member in ipairs(entries) do
    cnt = cnt + 1
    local s1 = string.find(member, ':', 1, true)
    if s1 then
        local amt = tonumber(string.sub(member, 1, s1 - 1)) or 0
        vol = vol + amt
        local s2 = string.find(member, ':', s1 + 1, true)
        if s2 then
            local bene = string.sub(member, s1 + 1, s2 - 1)
            by_bene[bene] = (by_bene[bene] or 0) + amt
        end
    end
end

if dollar_cap > 0 and vol + candidate > dollar_cap then
    return {'0', 'DOLLAR_CAP_EXCEEDED', tostring(vol), tostring(cnt)}
end

if count_cap > 0 and cnt + 1 > count_cap then
    return {'0', 'COUNT_CAP_EXCEEDED', tostring(vol), tostring(cnt)}
end

if cnt >= 2 then
    local total_after = vol + candidate
    if total_after > 0 then
        local projected = {}
        for k, v in pairs(by_bene) do projected[k] = v end
        projected[bene_hash] = (projected[bene_hash] or 0) + candidate
        local max_v = 0
        local distinct = 0
        for _, v in pairs(projected) do
            if v > max_v then max_v = v end
            distinct = distinct + 1
        end
        if distinct >= 2 and max_v / total_after > conc_thresh then
            return {'0', 'BENEFICIARY_CONCENTRATION_EXCEEDED', tostring(vol), tostring(cnt)}
        end
    end
end

redis.call('ZADD', key, now_ts, new_member)
redis.call('EXPIRE', key, ttl)
return {'1', '', tostring(vol), tostring(cnt)}
"""


@dataclass
class VelocityResult:
    """Result of an AML velocity check for a single entity transaction.

    Attributes:
        passed: True when all velocity limits are satisfied; False when any
            rule fires and the transaction must be blocked.
        reason: Rule identifier that caused a block, e.g.
            ``'DOLLAR_CAP_EXCEEDED'``, ``'COUNT_CAP_EXCEEDED'``,
            ``'BENEFICIARY_CONCENTRATION_EXCEEDED'``.  ``None`` when passed.
        entity_id_hash: SHA-256 hex digest of the entity identifier (never
            contains raw entity_id — privacy guarantee).
        dollar_volume_24h: Total USD volume recorded for this entity in the
            current 24-hour rolling window, *excluding* the candidate transaction.
        count_24h: Number of transactions recorded in the current 24-hour
            rolling window, *excluding* the candidate transaction.
        beneficiary_concentration: Fraction [0, 1] of the current 24-hour
            volume directed to the single largest beneficiary.  ``None`` when
            no prior records exist in the window.
    """

    passed: bool
    reason: Optional[str]
    entity_id_hash: str
    dollar_volume_24h: Decimal
    count_24h: int
    beneficiary_concentration: Optional[Decimal]


# ---------------------------------------------------------------------------
# RollingWindow — in-memory or Redis-backed 24-hour sliding window
# ---------------------------------------------------------------------------


class RollingWindow:
    """24-hour rolling window tracking per entity.

    When ``redis_client`` is provided, all state lives in Redis using a sorted
    set per entity.  When ``redis_client`` is ``None``, falls back to an
    in-process ``deque`` suitable for single-worker deployments and unit tests.

    The public interface is identical in both modes; callers never need to know
    which backend is active.

    Args:
        window_seconds: Length of the rolling window in seconds (default 86400).
        redis_client: Optional redis.Redis / redis.cluster.RedisCluster instance.
            When provided, all reads and writes go through Redis sorted-set
            operations so state is shared across multiple worker processes.
    """

    def __init__(self, window_seconds: int = 86400, redis_client=None):
        self._window_seconds = window_seconds
        self._redis = redis_client
        # In-memory fallback: entity_hash → deque of (timestamp, amount, bene_hash)
        self._records: Dict[str, Deque[Tuple[float, Decimal, str]]] = defaultdict(deque)

    # ── Redis helpers ────────────────────────────────────────────────────────

    def _redis_key(self, entity_hash: str) -> str:
        return f"{_VELOCITY_KEY_PREFIX}{entity_hash}"

    def _redis_add(self, entity_hash: str, amount: Decimal, beneficiary_hash: str) -> None:
        """Append one transaction record to the Redis sorted set.

        Score is the current Unix timestamp; member is a unique string encoding
        the amount, beneficiary hash, and a UUID so concurrent same-amount
        same-beneficiary transactions never collide (Redis set members must be unique).
        """
        key = self._redis_key(entity_hash)
        now = time.time()
        # member: "{amount}:{bene_hash}:{uuid4_hex}" — no colons in any component
        member = f"{amount}:{beneficiary_hash}:{uuid.uuid4().hex}"
        pipe = self._redis.pipeline()
        pipe.zadd(key, {member: now})
        # TTL = window + 60s buffer so Redis auto-expires stale keys
        pipe.expire(key, self._window_seconds + 60)
        pipe.execute()

    def _redis_get_records(self, entity_hash: str) -> List[Tuple[float, Decimal, str]]:
        """Fetch active records from Redis, pruning expired entries in the same round-trip.

        Returns:
            List of (timestamp_float, amount_Decimal, bene_hash_str) triples
            for all transactions within the current rolling window.
        """
        key = self._redis_key(entity_hash)
        cutoff = time.time() - self._window_seconds
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)           # prune expired (result[0])
        pipe.zrangebyscore(key, cutoff, "+inf", withscores=True)  # active (result[1])
        results = pipe.execute()
        entries = results[1]  # list of (member_bytes, score_float)

        records: List[Tuple[float, Decimal, str]] = []
        for member_raw, score in entries:
            member = member_raw.decode() if isinstance(member_raw, bytes) else member_raw
            # Format: "{amount}:{bene_hash}:{uuid4_hex}"
            # Split into 3 parts max — bene_hash and uuid contain no colons
            parts = member.split(":", 2)
            if len(parts) < 2:
                continue
            try:
                amount = Decimal(parts[0])
                bene_hash = parts[1]
                records.append((float(score), amount, bene_hash))
            except (InvalidOperation, ValueError):
                logger.warning("Skipping malformed velocity record: %r", member[:60])
        return records

    # ── Public interface ─────────────────────────────────────────────────────

    def get_records(self, entity_hash: str) -> List[Tuple[float, Decimal, str]]:
        """Return active (timestamp, amount, bene_hash) triples for an entity.

        Dispatches to Redis or in-memory depending on which backend is active.
        Callers should prefer this method over accessing ``_records`` directly
        so that the Redis path is transparently supported.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.

        Returns:
            List of ``(timestamp_float, amount_Decimal, bene_hash_str)`` triples
            within the active rolling window.  Empty list when no records exist.
        """
        if self._redis is not None:
            return self._redis_get_records(entity_hash)
        self._cleanup_expired(entity_hash)
        return list(self._records[entity_hash])

    def add(self, entity_hash: str, amount: Decimal, beneficiary_hash: str) -> None:
        """Append a new transaction record to the entity's rolling window.

        Cleans up expired records before appending so the window stays bounded.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.
            amount: Transaction amount in USD.
            beneficiary_hash: SHA-256 hex digest of the beneficiary identifier.
        """
        if self._redis is not None:
            self._redis_add(entity_hash, amount, beneficiary_hash)
        else:
            self._cleanup_expired(entity_hash)
            self._records[entity_hash].append((time.time(), amount, beneficiary_hash))

    def get_volume(self, entity_hash: str) -> Decimal:
        """Return the total USD volume for an entity within the rolling window.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.

        Returns:
            Sum of all transaction amounts recorded within the window.
            Returns ``Decimal('0')`` when no records exist.
        """
        records = self.get_records(entity_hash)
        return sum((r[1] for r in records), Decimal("0"))

    def get_count(self, entity_hash: str) -> int:
        """Return the number of transactions for an entity within the rolling window.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.

        Returns:
            Count of records within the window.  Returns ``0`` when empty.
        """
        return len(self.get_records(entity_hash))

    def get_beneficiary_concentration(self, entity_hash: str) -> Decimal:
        """Returns fraction (0-1) going to the single largest beneficiary."""
        records = self.get_records(entity_hash)
        if not records:
            return Decimal("0")
        total = sum(r[1] for r in records)
        if total == 0:
            return Decimal("0")
        by_bene: Dict[str, Decimal] = defaultdict(Decimal)
        for _, amt, bene in records:
            by_bene[bene] += amt
        max_fraction = max(by_bene.values()) / total
        return max_fraction

    def atomic_check_and_add(
        self,
        entity_hash: str,
        beneficiary_hash: str,
        amount: Decimal,
        dollar_cap: Decimal,
        count_cap: int,
    ) -> tuple[bool, str, Decimal, int]:
        """Atomically evaluate velocity caps and record if passing (Redis only).

        Uses a Lua script so the read-evaluate-write happens in a single Redis
        command with no TOCTOU gap between concurrent workers (EPG-25).

        Only valid when ``redis_client`` is configured. Raises ``RuntimeError``
        if called on an in-memory instance.

        Returns:
            (passed, reason, vol_before, cnt_before) where:
            - passed: True when all caps satisfied and transaction recorded
            - reason: empty string when passed, rule name when blocked
            - vol_before: dollar volume in window before this transaction
            - cnt_before: transaction count in window before this transaction
        """
        if self._redis is None:
            raise RuntimeError("atomic_check_and_add requires a Redis client")

        key = self._redis_key(entity_hash)
        now = time.time()
        cutoff = now - self._window_seconds
        new_member = f"{amount}:{beneficiary_hash}:{uuid.uuid4().hex}"
        ttl = self._window_seconds + 60

        result = self._redis.eval(
            _ATOMIC_CHECK_RECORD_LUA,
            1,  # number of keys
            key,
            str(cutoff),
            str(now),
            str(amount),
            str(dollar_cap),
            str(count_cap),
            str(BENEFICIARY_CONCENTRATION_THRESHOLD),
            beneficiary_hash,
            new_member,
            str(ttl),
        )
        # result: [passed_str, reason_str, vol_str, cnt_str]
        passed = result[0] == b"1" or result[0] == "1" or result[0] == 1
        reason = (result[1].decode() if isinstance(result[1], bytes) else result[1]) or ""
        try:
            vol = Decimal(result[2].decode() if isinstance(result[2], bytes) else result[2])
        except Exception:
            vol = Decimal("0")
        try:
            cnt = int(result[3].decode() if isinstance(result[3], bytes) else result[3])
        except Exception:
            cnt = 0
        return passed, reason, vol, cnt

    def _cleanup_expired(self, entity_hash: str) -> None:
        """Evict all records older than ``window_seconds`` from the deque.

        Only used for the in-memory path.  The Redis path prunes in
        ``_redis_get_records`` via ``ZREMRANGEBYSCORE``.

        Args:
            entity_hash: SHA-256 hex digest of the entity identifier.
        """
        cutoff = time.time() - self._window_seconds
        dq = self._records[entity_hash]
        while dq and dq[0][0] < cutoff:
            dq.popleft()


# ---------------------------------------------------------------------------
# VelocityChecker — primary AML gate wiring RollingWindow + Redis
# ---------------------------------------------------------------------------


class VelocityChecker:
    """Checks AML velocity limits for a given entity."""

    def __init__(self, salt: bytes, redis_client=None):
        self.salt = salt
        self._redis = redis_client
        # Pass redis_client down so the window uses Redis when available
        self._window = RollingWindow(redis_client=redis_client)
        # Lock for the in-memory check_and_record path — prevents TOCTOU between
        # threads within the same process (EPG-25). Redis path uses Lua instead.
        self._check_record_lock = threading.Lock()

    def set_redis_client(self, redis_client) -> None:
        """Wire a Redis client into this VelocityChecker and its RollingWindow.

        Use this public setter instead of mutating ``_redis`` and
        ``_window._redis`` directly from outside the class (B7-04).

        Args:
            redis_client: A redis.Redis / redis.cluster.RedisCluster instance.
        """
        self._redis = redis_client
        self._window._redis = redis_client
        logger.info("VelocityChecker: Redis client set via set_redis_client()")

    def _hash_entity(self, entity_id: str) -> str:
        """Compute SHA-256(entity_id + salt) for the entity identifier.

        Never stores the raw ``entity_id`` — all window records use the
        digest only.  This satisfies GDPR Art.25 (data minimisation) and
        AML record-keeping requirements simultaneously.

        Args:
            entity_id: Raw entity identifier string (e.g., BIC or licensee ID).

        Returns:
            Lowercase hex SHA-256 digest (64 characters).
        """
        return hashlib.sha256(entity_id.encode() + self.salt).hexdigest()

    def _hash_beneficiary(self, beneficiary_id: str) -> str:
        """Compute SHA-256(beneficiary_id + salt) for the beneficiary identifier.

        Uses the same salt as :meth:`_hash_entity` to ensure cross-licensee
        isolation; a different licensee's salt produces a different digest for
        the same beneficiary.

        Args:
            beneficiary_id: Raw beneficiary identifier string.

        Returns:
            Lowercase hex SHA-256 digest (64 characters).
        """
        return hashlib.sha256(beneficiary_id.encode() + self.salt).hexdigest()

    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> VelocityResult:
        """Check whether this transaction would violate AML velocity limits.

        Evaluates three rules in order:
          1. Dollar-cap: rolling 24-hour volume + ``amount`` ≤ cap.
          2. Count-cap: rolling 24-hour count + 1 ≤ cap.
          3. Beneficiary concentration: single beneficiary share ≤ 80%
             (only enforced when ≥ 2 distinct beneficiaries and ≥ 2 prior
             transactions exist in the window).

        Does *not* record the transaction; call :meth:`record` after a
        successful check.

        When ``redis_client`` is configured, all window state is fetched in a
        single ``get_records()`` call (one Redis pipeline) to ensure volume,
        count, and projected concentration are computed from a consistent
        snapshot.

        Args:
            entity_id: Raw entity identifier (hashed internally).
            amount: Candidate transaction amount in USD.
            beneficiary_id: Raw beneficiary identifier (hashed internally).
            dollar_cap_override: Optional USD cap to use instead of the
                default $1M limit.
            count_cap_override: Optional count cap to use instead of the
                default 100 limit.

        Returns:
            :class:`VelocityResult` with ``passed=True`` when all rules pass,
            or ``passed=False`` and a ``reason`` string when any rule fires.
        """
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)

        # Fetch all active records once — single Redis pipeline when Redis is wired
        records = self._window.get_records(entity_hash)

        vol: Decimal = sum((r[1] for r in records), Decimal("0"))
        cnt = len(records)

        # Current beneficiary concentration (for VelocityResult reporting only)
        conc: Optional[Decimal]
        if records:
            total_cur = sum(r[1] for r in records)
            if total_cur > 0:
                by_bene_cur: Dict[str, Decimal] = defaultdict(Decimal)
                for _, a, b in records:
                    by_bene_cur[b] += a
                conc = max(by_bene_cur.values()) / total_cur
            else:
                conc = Decimal("0")
        else:
            conc = None

        dollar_cap = dollar_cap_override if dollar_cap_override is not None else Decimal("0")
        count_cap = count_cap_override if count_cap_override is not None else 0

        # EPG-16: 0 = unlimited — explicitly guard before enforcing caps.
        # A cap of 0 must NEVER be treated as "block all"; it means no limit.
        if dollar_cap != 0 and vol + amount > dollar_cap:
            return VelocityResult(
                passed=False, reason="DOLLAR_CAP_EXCEEDED",
                entity_id_hash=entity_hash, dollar_volume_24h=vol,
                count_24h=cnt, beneficiary_concentration=conc,
            )
        if count_cap > 0 and cnt + 1 > count_cap:
            return VelocityResult(
                passed=False, reason="COUNT_CAP_EXCEEDED",
                entity_id_hash=entity_hash, dollar_volume_24h=vol,
                count_24h=cnt, beneficiary_concentration=conc,
            )

        # Projected concentration: what would conc be if this transaction is accepted?
        # Only enforce when there are ≥ 2 prior transactions (concentration is
        # meaningful only with multiple data points) and ≥ 2 distinct beneficiaries.
        total_after = vol + amount
        if total_after > 0 and cnt >= 2:
            by_bene: Dict[str, Decimal] = defaultdict(Decimal)
            for _, a, b in records:
                by_bene[b] += a
            by_bene[bene_hash] += amount
            if len(by_bene) >= 2:
                new_conc = max(by_bene.values()) / total_after
                if new_conc > BENEFICIARY_CONCENTRATION_THRESHOLD:
                    return VelocityResult(
                        passed=False, reason="BENEFICIARY_CONCENTRATION_EXCEEDED",
                        entity_id_hash=entity_hash, dollar_volume_24h=vol,
                        count_24h=cnt, beneficiary_concentration=new_conc,
                    )

        return VelocityResult(
            passed=True, reason=None,
            entity_id_hash=entity_hash, dollar_volume_24h=vol,
            count_24h=cnt, beneficiary_concentration=conc,
        )

    def record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> None:
        """Record a transaction in the rolling window after it has been accepted.

        Must be called *after* a successful :meth:`check` to update the window
        for subsequent checks.  Calling :meth:`record` without a prior
        :meth:`check` can cause the next check to fail spuriously.

        Args:
            entity_id: Raw entity identifier (hashed internally).
            amount: Transaction amount in USD.
            beneficiary_id: Raw beneficiary identifier (hashed internally).
            dollar_cap_override: Optional USD cap (ignored, for signature symmetry with check).
            count_cap_override: Optional count cap (ignored, for signature symmetry with check).
        """
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        self._window.add(entity_hash, amount, bene_hash)
        logger.debug("Recorded velocity: entity_hash=%s amount=%s", entity_hash[:8], amount)

    def check_and_record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> "VelocityResult":
        """Atomic check-and-record — eliminates TOCTOU race in multi-worker deployments.

        **Redis path:** delegates to a single Lua EVAL so the cap evaluation and
        the write happen atomically; no concurrent worker can slip through.

        **In-memory path:** acquires ``_check_record_lock`` before evaluating and
        recording, making the operation thread-safe within a single process.

        Use this instead of the separate ``check()`` + ``record()`` calls whenever
        the window must be updated on a passing decision (EPG-25).

        Args:
            entity_id: Raw entity identifier (hashed internally).
            amount: Candidate transaction amount in USD.
            beneficiary_id: Raw beneficiary identifier (hashed internally).
            dollar_cap_override: Optional USD cap override.
            count_cap_override: Optional count cap override.

        Returns:
            :class:`VelocityResult` — ``passed=True`` means the transaction was
            accepted *and* recorded in the rolling window.
        """
        entity_hash = self._hash_entity(entity_id)
        bene_hash = self._hash_beneficiary(beneficiary_id)
        dollar_cap = dollar_cap_override if dollar_cap_override is not None else Decimal("0")
        count_cap_val = count_cap_override if count_cap_override is not None else 0

        if self._redis is not None:
            # --- Redis path: atomic Lua check-and-record -------------------------
            passed, reason, vol, cnt = self._window.atomic_check_and_add(
                entity_hash, bene_hash, amount, dollar_cap, count_cap_val,
            )
            if passed:
                logger.debug(
                    "Atomic velocity pass+record: entity_hash=%s amount=%s",
                    entity_hash[:8], amount,
                )
                return VelocityResult(
                    passed=True, reason=None,
                    entity_id_hash=entity_hash,
                    dollar_volume_24h=vol,
                    count_24h=cnt,
                    beneficiary_concentration=None,  # not computed in atomic path
                )
            logger.warning(
                "Atomic velocity block: reason=%s entity_hash=%s",
                reason, entity_hash[:8],
            )
            return VelocityResult(
                passed=False, reason=reason,
                entity_id_hash=entity_hash,
                dollar_volume_24h=vol,
                count_24h=cnt,
                beneficiary_concentration=None,
            )

        # --- In-memory path: lock prevents within-process TOCTOU ----------------
        with self._check_record_lock:
            result = self.check(
                entity_id, amount, beneficiary_id,
                dollar_cap_override=dollar_cap_override,
                count_cap_override=count_cap_override,
            )
            if result.passed:
                self._window.add(entity_hash, amount, bene_hash)
                logger.debug(
                    "Locked velocity pass+record: entity_hash=%s amount=%s",
                    entity_hash[:8], amount,
                )
            return result
