"""
uetr_tracker.py — Retry detection for payment UETRs.
GAP-04: Prevent double-funding when banks retry manual payments.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple


class UETRTracker:
    """Tracks processed UETRs to detect and block retries (GAP-04).

    In production, this should be backed by a distributed store (e.g. Redis)
    with a TTL of 24–48 hours. This implementation uses an in-memory
    dictionary with thread-safe access and a rolling 30-minute window by default.
    """

    def __init__(self, ttl_seconds: int = 1800, redis_client=None) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._redis = redis_client
        self._processed: Dict[str, Tuple[str, float]] = {}  # uetr -> (outcome, timestamp)

    def is_retry(self, uetr: str) -> bool:
        """Return True if the UETR has already been processed within the TTL."""
        self._cleanup_expired()
        with self._lock:
            return uetr in self._processed

    def get_outcome(self, uetr: str) -> Optional[str]:
        """Return the outcome of a previously processed UETR, or None."""
        self._cleanup_expired()
        with self._lock:
            res = self._processed.get(uetr)
            return res[0] if res else None

    def record(self, uetr: str, outcome: str) -> None:
        """Record the outcome of a processed UETR with the current timestamp."""
        self._cleanup_expired()
        with self._lock:
            self._processed[uetr] = (outcome, time.time())

    def _cleanup_expired(self) -> None:
        """Remove entries older than the TTL from the in-memory store."""
        cutoff = time.time() - self._ttl
        with self._lock:
            # Create a list of keys to delete to avoid "dictionary changed size during iteration"
            expired = [u for u, (o, ts) in self._processed.items() if ts < cutoff]
            for u in expired:
                del self._processed[u]

    def clear(self) -> None:
        """Clear all tracked UETRs (mainly for testing)."""
        with self._lock:
            self._processed.clear()
