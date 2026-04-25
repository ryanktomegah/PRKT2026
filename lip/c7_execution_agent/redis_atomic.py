"""
redis_atomic.py — Atomic Redis operations using Lua scripts (ESG-02).

Prevents race conditions in offer state transitions by ensuring atomic
compare-and-set semantics. Uses Redis EVAL to execute Lua scripts
server-side.

ESG-02: Offer state transition race condition fix
- ELO accept() and background expire_stale_offers() can race
- Both check "is offer in PENDING" simultaneously
- Winner moves state, loser gets "offer not found" or "already resolved"
- Lua script ensures only one operation wins the transition
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Lua scripts for atomic operations
# ESG-02: Atomic offer acceptance with state check
_LUA_ACCEPT_OFFER = """
local offer_key = KEYS[1]
local pending_state = redis.call('HGET', offer_key, 'state')
if not pending_state or pending_state ~= 'PENDING' then
    return {err = 'OFFER_NOT_PENDING', state = pending_state or 'nil'}
end

local now = redis.call('TIME')
local expiry = redis.call('HGET', offer_key, 'expiry')
if expiry and tonumber(expiry) <= now then
    return {err = 'OFFER_EXPIRED', state = pending_state}
end

-- Atomically transition to ACCEPTED
redis.call('HSET', offer_key, 'state', 'ACCEPTED')
redis.call('HSET', offer_key, 'accepted_at', now)
redis.call('HSET', offer_key, 'elo_operator_id', ARGV[1])
redis.call('HSET', offer_key, 'acceptance_id', ARGV[2])

return {err = 'nil', state = 'ACCEPTED'}
"""

# ESG-02: Atomic offer expiry with state check
_LUA_EXPIRE_OFFER = """
local offer_key = KEYS[1]
local current_state = redis.call('HGET', offer_key, 'state')
if not current_state or current_state == 'ACCEPTED' or current_state == 'REJECTED' then
    -- Already resolved, no action needed
    return {err = 'ALREADY_RESOLVED', state = current_state}
end

if current_state ~= 'PENDING' then
    -- Not in pending state, ignore
    return {err = 'NOT_PENDING', state = current_state}
end

-- Atomically transition to EXPIRED
local now = redis.call('TIME')
redis.call('HSET', offer_key, 'state', 'EXPIRED')
redis.call('HSET', offer_key, 'expired_at', now)
redis.call('HSET', offer_key, 'expiry_reason', 'TIMEOUT')

return {err = 'nil', state = 'EXPIRED'}
"""

# ESG-02: Atomic offer rejection with state check
_LUA_REJECT_OFFER = """
local offer_key = KEYS[1]
local current_state = redis.call('HGET', offer_key, 'state')
if not current_state or current_state == 'ACCEPTED' or current_state == 'REJECTED' then
    return {err = 'ALREADY_RESOLVED', state = current_state}
end

if current_state ~= 'PENDING' then
    return {err = 'NOT_PENDING', state = current_state}
end

-- Atomically transition to REJECTED
local now = redis.call('TIME')
redis.call('HSET', offer_key, 'state', 'REJECTED')
redis.call('HSET', offer_key, 'rejected_at', now)
redis.call('HSET', offer_key, 'rejection_reason', ARGV[1])
redis.call('HSET', offer_key, 'elo_operator_id', ARGV[2])

return {err = 'nil', state = 'REJECTED'}
"""

# Offer state keys in Redis
_OFFER_KEY_PREFIX = "lip:offer:"
_OFFER_STATE_FIELD = "state"
_OFFER_EXPIRY_FIELD = "expiry"
_OFFER_ELO_OPERATOR_FIELD = "elo_operator_id"
_OFFER_ACCEPTANCE_ID_FIELD = "acceptance_id"
_OFFER_ACCEPTED_AT_FIELD = "accepted_at"
_OFFER_REJECTED_AT_FIELD = "rejected_at"
_OFFER_REJECTION_REASON_FIELD = "rejection_reason"


class AtomicOfferOperations:
    """Atomic Redis operations for offer state management (ESG-02).

    Wraps EVAL calls to Lua scripts that execute atomically on the
    Redis server, preventing race conditions between concurrent operations.

    Usage:
        client = create_redis_client()
        atomic_ops = AtomicOfferOperations(client)
        result = atomic_ops.accept_offer(offer_id, operator_id, acceptance_id)
    """

    def __init__(self, redis_client):
        """Initialize with a Redis client instance.

        Args:
            redis_client: redis.Redis instance from redis_factory.create_redis_client().
        """
        self._redis = redis_client
        # Pre-load Lua scripts to avoid parsing on every call
        self._accept_script = self._redis.register_script(_LUA_ACCEPT_OFFER)
        self._expire_script = self._redis.register_script(_LUA_EXPIRE_OFFER)
        self._reject_script = self._redis.register_script(_LUA_REJECT_OFFER)

    def _offer_key(self, offer_id: str) -> str:
        """Generate Redis key for an offer."""
        return f"{_OFFER_KEY_PREFIX}{offer_id}"

    def get_state(self, offer_id: str) -> Optional[str]:
        """Get the current state of an offer from Redis.

        This is a read operation and does not change state.

        Args:
            offer_id: The offer UUID.

        Returns:
            The state string (PENDING, ACCEPTED, REJECTED, EXPIRED) or None.
        """
        key = self._offer_key(offer_id)
        state = self._redis.hget(key, _OFFER_STATE_FIELD)
        return state.decode('utf-8') if state else None

    def accept_offer(
        self,
        offer_id: str,
        elo_operator_id: str,
        acceptance_id: str,
    ) -> dict:
        """Atomically transition an offer from PENDING to ACCEPTED (ESG-02).

        Uses a Lua script to ensure atomicity:
        1. Check if offer is in PENDING state
        2. Check if offer has not expired
        3. If both conditions pass, transition to ACCEPTED atomically

        Args:
            offer_id: The offer UUID to accept.
            elo_operator_id: ELO operator identifier for EU AI Act Art.14 audit trail.
            acceptance_id: UUID for the acceptance record.

        Returns:
            Dict with keys:
                'success': bool - True if transition succeeded
                'err': str - Error code if failed
                'state': str - Current state (if known)
        """
        now = int(datetime.now(tz=timezone.utc).timestamp())
        result = self._accept_script(
            keys=[self._offer_key(offer_id)],
            args=[elo_operator_id, acceptance_id, now],
        )
        return result

    def expire_offer(self, offer_id: str) -> dict:
        """Atomically expire a PENDING offer (ESG-02).

        Uses a Lua script to ensure atomicity:
        1. Check if offer is in PENDING state
        2. Check if offer is already resolved
        3. If in PENDING, transition to EXPIRED atomically

        Args:
            offer_id: The offer UUID to expire.

        Returns:
            Dict with keys:
                'success': bool - True if transition succeeded
                'err': str - Error code if failed
                'state': str - Current state (if known)
        """
        result = self._expire_script(
            keys=[self._offer_key(offer_id)],
            args=[],
        )
        return result

    def reject_offer(
        self,
        offer_id: str,
        elo_operator_id: str,
        rejection_reason: str,
    ) -> dict:
        """Atomically transition an offer from PENDING to REJECTED (ESG-02).

        Uses a Lua script to ensure atomicity:
        1. Check if offer is in PENDING state
        2. Check if offer is already resolved
        3. If in PENDING, transition to REJECTED atomically

        Args:
            offer_id: The offer UUID to reject.
            elo_operator_id: ELO operator identifier.
            rejection_reason: The rejection reason text.

        Returns:
            Dict with keys:
                'success': bool - True if transition succeeded
                'err': str - Error code if failed
                'state': str - Current state (if known)
        """
        result = self._reject_script(
            keys=[self._offer_key(offer_id)],
            args=[rejection_reason, elo_operator_id],
        )
        return result
