"""
uetr_tracker.py — Retry detection for payment UETRs.
GAP-04: Prevent double-funding when banks retry manual payments.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UETRTracker:
    """Tracks processed UETRs to detect and block retries (GAP-04).

    Prevents double-funding in two scenarios:
    1. Systemic Replay: Exact same UETR re-submitted.
    2. Operational Retry: Manual re-keying with NEW UETR but same details.

    In production, this should be backed by a distributed store (e.g. Redis).
    This implementation uses in-memory dictionaries with thread-safe access.
    """

    def __init__(self, ttl_seconds: int = 1800, redis_client=None) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._redis = redis_client

        # Primary index: uetr -> (outcome, timestamp)
        self._processed: Dict[str, Tuple[str, float]] = {}

        # Secondary index for manual retries (GAP-04):
        # (sending_bic, receiving_bic, currency) -> List[(amount, uetr, timestamp)]
        # We group by BIC pair + currency to enable efficient fuzzy amount matching.
        self._tuple_index: Dict[Tuple[str, str, str], List[Tuple[Decimal, str, float]]] = defaultdict(list)

    def is_retry(self, uetr: str, context: Optional[dict] = None) -> bool:
        """Return True if the UETR or an equivalent payment has been processed.

        Args:
            uetr: The Unique End-to-end Transaction Reference.
            context: Optional payment context for tuple-based matching.
                     Expected keys: 'sending_bic', 'receiving_bic', 'amount', 'currency'.
        """
        self._cleanup_expired()

        with self._lock:
            # 1. Exact UETR match (Systemic Replay)
            if uetr in self._processed:
                return True

            # 2. Tuple-based match (Operational Retry)
            if context:
                return self._is_tuple_match(uetr, context)

            return False

    def get_outcome(self, uetr: str) -> Optional[str]:
        """Return the outcome of a previously processed UETR, or None."""
        self._cleanup_expired()
        with self._lock:
            res = self._processed.get(uetr)
            return res[0] if res else None

    def record(self, uetr: str, outcome: str, context: Optional[dict] = None) -> None:
        """Record the outcome of a processed UETR."""
        self._cleanup_expired()
        now = time.time()

        with self._lock:
            # Update primary index
            self._processed[uetr] = (outcome, now)

            # Update secondary tuple index if context provided
            if context:
                try:
                    s_bic = context.get("sending_bic")
                    r_bic = context.get("receiving_bic")
                    amt_str = str(context.get("amount", "0"))
                    amt = Decimal(amt_str)
                    curr = context.get("currency")

                    if s_bic and r_bic and curr:
                        key = (s_bic, r_bic, curr)
                        self._tuple_index[key].append((amt, uetr, now))
                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning("Failed to index payment tuple for UETR %s: %s", uetr, e)

    def _is_tuple_match(self, current_uetr: str, context: dict) -> bool:
        """Check for a fuzzy match in the tuple index."""
        try:
            s_bic = context.get("sending_bic")
            r_bic = context.get("receiving_bic")
            curr = context.get("currency")
            amt_str = str(context.get("amount", "0"))
            current_amt = Decimal(amt_str)

            if not (s_bic and r_bic and curr):
                return False

            key = (s_bic, r_bic, curr)
            candidates = self._tuple_index.get(key, [])

            for (hist_amt, hist_uetr, _) in candidates:
                # Skip self-match (should correspond to _processed check, but for safety)
                if hist_uetr == current_uetr:
                    continue

                # GAP-04 Requirement: ±0.01% tolerance for FX rounding
                # If amounts are zero, strict equality
                if current_amt == 0:
                    if hist_amt == 0:
                        return True
                    continue

                diff = abs(current_amt - hist_amt)
                pct_diff = diff / current_amt

                if pct_diff <= Decimal("0.0001"): # 0.01%
                    logger.warning(
                        "RETRY DETECTED: Tuple match found. New UETR: %s matches Old UETR: %s. "
                        "Amount diff: %s%%", current_uetr, hist_uetr, pct_diff * 100
                    )
                    return True

            return False

        except Exception as e:
            logger.error("Error during tuple matching for UETR %s: %s", current_uetr, e)
            return False

    def _cleanup_expired(self) -> None:
        """Remove entries older than the TTL from in-memory stores."""
        cutoff = time.time() - self._ttl
        with self._lock:
            # Cleanup primary index
            expired_uetrs = [u for u, (o, ts) in self._processed.items() if ts < cutoff]
            for u in expired_uetrs:
                del self._processed[u]

            # Cleanup tuple index
            empty_keys = []
            for key, entries in self._tuple_index.items():
                # Keep only fresh entries
                fresh_entries = [e for e in entries if e[2] >= cutoff]
                if len(fresh_entries) != len(entries):
                    self._tuple_index[key] = fresh_entries
                if not fresh_entries:
                    empty_keys.append(key)

            for k in empty_keys:
                del self._tuple_index[k]

    def clear(self) -> None:
        """Clear all tracked UETRs (mainly for testing)."""
        with self._lock:
            self._processed.clear()
            self._tuple_index.clear()
