"""
rate_limiter.py — Token-bucket rate limiter (in-memory with Redis upgrade path).

Reusable across routers. One bucket per key (API key / regulator ID).
Thread-safe via threading.Lock.

IMPORTANT — Multi-replica deployment (B2-11):
  This limiter is per-pod in-memory. In an N-replica deployment each pod
  maintains an independent bucket, so the effective limit is N× the configured
  rate per unique key.  To enforce a cluster-wide rate limit, pass a Redis
  client via the ``redis_client`` constructor argument.  When a Redis client
  is provided, INCR+TTL is used for atomic distributed counting.  When Redis
  is unavailable the limiter falls back to in-memory and logs a WARNING at
  startup so the operator is aware.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Token-bucket rate limiter with optional Redis backend (B2-11).

    Each key gets ``rate`` tokens per ``period_seconds``.  Tokens refill
    continuously (proportional to elapsed time).  When a key's bucket is
    empty, ``check_and_consume`` returns False.

    Thread-safe.

    Parameters
    ----------
    rate:
        Maximum requests per ``period_seconds`` per key.
    period_seconds:
        Token refill window in seconds.
    redis_client:
        Optional Redis client.  When provided, uses Redis INCR+TTL for
        cluster-wide rate limiting.  When ``None``, falls back to in-memory
        buckets with a startup WARNING (N-replica deployments will see N×
        effective limit).
    """

    def __init__(
        self,
        rate: int = 100,
        period_seconds: int = 3600,
        redis_client: Optional[Any] = None,
    ):
        self._rate = rate
        self._period = period_seconds
        self._redis = redis_client
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

        if redis_client is None:
            logger.warning(
                "TokenBucketRateLimiter: no Redis client provided — using per-pod "
                "in-memory buckets. In multi-replica deployments the effective rate "
                "limit is N× the configured value (%d req/%ds per pod). "
                "Pass a redis_client to enforce a cluster-wide limit.",
                rate,
                period_seconds,
            )

    def check_and_consume(self, key: str) -> bool:
        """Consume one token for ``key``.

        Returns True if the request is allowed, False if rate-limited.
        Delegates to Redis when configured (B2-11).
        """
        allowed, _ = self.check_and_consume_with_remaining(key)
        return allowed

    def check_and_consume_with_remaining(self, key: str) -> Tuple[bool, int]:
        """Consume one token and return (allowed, remaining) atomically.

        When a Redis client is configured, uses INCR+TTL for distributed,
        cluster-wide rate limiting.  Falls back to in-memory token bucket
        when Redis is unavailable.

        Single lock acquisition avoids TOCTOU between remaining() and
        check_and_consume() calls.
        """
        if self._redis is not None:
            return self._check_redis(key)
        return self._check_memory(key)

    def _check_redis(self, key: str) -> Tuple[bool, int]:
        """Redis-backed INCR+TTL rate check (cluster-wide, B2-11)."""
        redis_client = self._redis
        if redis_client is None:
            return self._check_memory(key)
        redis_key = f"ratelimit:{key}:{int(time.time()) // self._period}"
        try:
            count = redis_client.incr(redis_key)
            if count == 1:
                redis_client.expire(redis_key, self._period)
            remaining = max(0, self._rate - int(count))
            allowed = int(count) <= self._rate
            return allowed, remaining
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Redis rate-limit check failed for key=%s; falling back to in-memory: %s",
                key, exc,
            )
            return self._check_memory(key)

    def _check_memory(self, key: str) -> Tuple[bool, int]:
        """In-memory token-bucket rate check."""
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(self._rate), now))

            elapsed = now - last_refill
            refill = elapsed * (self._rate / self._period)
            tokens = min(float(self._rate), tokens + refill)

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = (tokens, now)
                return True, int(tokens)
            else:
                self._buckets[key] = (tokens, now)
                return False, 0

    def remaining(self, key: str) -> int:
        """Return number of tokens remaining for ``key``."""
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(self._rate), now))

            elapsed = now - last_refill
            refill = elapsed * (self._rate / self._period)
            tokens = min(float(self._rate), tokens + refill)

            return int(tokens)
