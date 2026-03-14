"""
uetr_tracker.py — Retry detection for payment UETRs.
GAP-04: Prevent double-funding when banks retry manual payments.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional


class UETRTracker:
    """Tracks processed UETRs to detect and block retries.

    In production, this would be backed by a distributed store (e.g. Redis)
    with a TTL of 24–48 hours.  This implementation uses an in-memory
    dictionary with thread-safe access.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processed: Dict[str, str] = {}  # uetr -> outcome

    def is_retry(self, uetr: str) -> bool:
        """Return True if the UETR has already been processed."""
        with self._lock:
            return uetr in self._processed

    def get_outcome(self, uetr: str) -> Optional[str]:
        """Return the outcome of a previously processed UETR, or None."""
        with self._lock:
            return self._processed.get(uetr)

    def record(self, uetr: str, outcome: str) -> None:
        """Record the outcome of a processed UETR."""
        with self._lock:
            self._processed[uetr] = outcome

    def clear(self) -> None:
        """Clear all tracked UETRs (mainly for testing)."""
        with self._lock:
            self._processed.clear()
