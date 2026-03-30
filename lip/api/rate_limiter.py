"""
rate_limiter.py — In-memory token-bucket rate limiter.

Reusable across routers. One bucket per key (API key / regulator ID).
Thread-safe via threading.Lock.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


class TokenBucketRateLimiter:
    """In-memory token-bucket rate limiter.

    Each key gets ``rate`` tokens per ``period_seconds``. Tokens refill
    continuously (proportional to elapsed time). When a key's bucket
    is empty, ``check_and_consume`` returns False.

    Thread-safe.
    """

    def __init__(self, rate: int = 100, period_seconds: int = 3600):
        self._rate = rate
        self._period = period_seconds
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check_and_consume(self, key: str) -> bool:
        """Consume one token for ``key``.

        Returns True if the request is allowed, False if rate-limited.
        """
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(self._rate), now))

            elapsed = now - last_refill
            refill = elapsed * (self._rate / self._period)
            tokens = min(float(self._rate), tokens + refill)
            last_refill = now

            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, last_refill)
                return True
            else:
                self._buckets[key] = (tokens, last_refill)
                return False

    def check_and_consume_with_remaining(self, key: str) -> Tuple[bool, int]:
        """Consume one token and return (allowed, remaining) atomically.

        Single lock acquisition avoids TOCTOU between remaining() and
        check_and_consume() calls.
        """
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
