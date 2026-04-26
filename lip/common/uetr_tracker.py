"""
uetr_tracker.py — Retry detection for payment UETRs.
GAP-04: Prevent double-funding when banks retry manual payments.
Phase C: cross-rail handoff registration (SWIFT -> FedNow last-mile etc).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from lip.common.constants import UETR_TTL_BUFFER_DAYS

logger = logging.getLogger(__name__)

_UETR_TTL_SECONDS: int = UETR_TTL_BUFFER_DAYS * 24 * 3600  # 45 days in seconds

# Run cleanup every N calls to avoid O(n) cost on every call.
_CLEANUP_INTERVAL = 1000

# Phase C — cross-rail handoff TTL.
# A SWIFT pacs.008 with US-domestic destination is typically forwarded via
# FedNow last-mile within seconds. 30 minutes covers retry, network jitter,
# and any reasonable processing delay. Beyond that window, the link is stale.
_HANDOFF_TTL_MINUTES = 30
_VALID_HANDOFF_RAILS: frozenset[str] = frozenset({"FEDNOW", "RTP", "SEPA"})


class UETRTracker:
    """Tracks processed UETRs to detect and block retries (GAP-04).

    Prevents double-funding in two scenarios:
    1. Systemic Replay: Exact same UETR re-submitted.
    2. Operational Retry: Manual re-keying with NEW UETR but same details.

    When a Redis client is provided it is used as the primary dedup store via
    SETNX + TTL (distributed, survives restarts).  When redis_client is None
    the tracker falls back to an in-memory dict and logs a WARNING at init time.
    """

    def __init__(self, ttl_seconds: int = _UETR_TTL_SECONDS, redis_client=None) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._redis = redis_client
        self._call_counter = 0

        if self._redis is None:
            logger.warning(
                "UETRTracker: no Redis client provided — falling back to in-memory "
                "deduplication.  This is NOT suitable for multi-process or distributed "
                "deployments.  Provide a Redis client for production use."
            )

        # Primary index: uetr -> (outcome, timestamp)
        self._processed: Dict[str, Tuple[str, float]] = {}

        # Secondary index for manual retries (GAP-04):
        # (sending_bic, receiving_bic, currency) -> List[(amount, uetr, timestamp)]
        # We group by BIC pair + currency to enable efficient fuzzy amount matching.
        self._tuple_index: Dict[Tuple[str, str, str], List[Tuple[Decimal, str, float]]] = defaultdict(list)

        # Phase C — cross-rail handoff index (child_uetr -> (parent_uetr, registered_at)).
        # In-memory by default; production deployments should back with Redis (T2.2).
        self._handoffs: Dict[str, Tuple[str, datetime]] = {}

    def is_retry(self, uetr: str, context: Optional[dict] = None) -> bool:
        """Return True if the UETR or an equivalent payment has been processed.

        Args:
            uetr: The Unique End-to-end Transaction Reference.
            context: Optional payment context for tuple-based matching.
                     Expected keys: 'sending_bic', 'receiving_bic', 'amount', 'currency'.
        """
        self._maybe_cleanup()

        # 1. Exact UETR match via Redis (if available)
        if self._redis is not None:
            redis_key = f"uetr:{uetr}"
            if self._redis.exists(redis_key):
                return True

        with self._lock:
            # 1. Exact UETR match (in-memory fallback or secondary check)
            # Check TTL inline so that expired entries are not treated as
            # duplicates even when periodic cleanup has not run yet.
            if uetr in self._processed:
                _, recorded_at = self._processed[uetr]
                if time.time() - recorded_at < self._ttl:
                    return True

            # 2. Tuple-based match (Operational Retry)
            if context:
                return self._is_tuple_match(uetr, context)

            return False

    def get_outcome(self, uetr: str) -> Optional[str]:
        """Return the outcome of a previously processed UETR, or None.

        Returns None for entries that have exceeded the TTL even if they have
        not yet been removed by the periodic cleanup sweep.
        """
        self._maybe_cleanup()
        with self._lock:
            res = self._processed.get(uetr)
            if res is None:
                return None
            outcome, recorded_at = res
            if time.time() - recorded_at >= self._ttl:
                return None
            return outcome

    def record(self, uetr: str, outcome: str, context: Optional[dict] = None) -> None:
        """Record the outcome of a processed UETR."""
        self._maybe_cleanup()
        now = time.time()

        # Persist to Redis when available (SETNX + TTL for distributed dedup)
        if self._redis is not None:
            redis_key = f"uetr:{uetr}"
            self._redis.set(redis_key, outcome, nx=True, ex=self._ttl)

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
        """Check for a fuzzy match in the tuple index.

        Raises on unexpected exceptions (fail-closed): an exception during
        duplicate detection must never be silently swallowed.
        """
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

            # GAP-04 Requirement: ±0.01% tolerance for FX rounding.
            # If amounts are zero, strict equality
            if current_amt == 0:
                if hist_amt == 0:
                    return True
                continue

            diff = abs(current_amt - hist_amt)
            pct_diff = diff / current_amt

            if pct_diff <= Decimal("0.0001"):  # 0.01%
                logger.warning(
                    "RETRY DETECTED: Tuple match found. New UETR: %s matches Old UETR: %s. "
                    "Amount diff: %s%%", current_uetr, hist_uetr, pct_diff * 100
                )
                return True

        return False

    def _maybe_cleanup(self) -> None:
        """Periodically remove expired in-memory entries (every _CLEANUP_INTERVAL calls)."""
        with self._lock:
            self._call_counter += 1
            if self._call_counter < _CLEANUP_INTERVAL:
                return
            self._call_counter = 0
        self._cleanup_expired()

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
            self._handoffs.clear()

    # ── Phase C: cross-rail handoff tracking ───────────────────────────────

    def register_handoff(
        self,
        parent_uetr: str,
        child_uetr: str,
        child_rail: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Register a domestic-rail handoff for a cross-border UETR.

        When a SWIFT pacs.008 indicates a US/EU/UK domestic destination, the
        receiving correspondent bank may settle the last mile via a domestic
        instant rail (FedNow, RTP, SEPA Instant). The domestic rail message
        carries its own UETR (or end-to-end ID), distinct from the upstream
        SWIFT UETR.

        This method links the upstream (parent) and downstream (child) UETRs
        so a domestic-leg failure can be routed to the parent for bridge
        eligibility — addressing the cross-rail settlement detection gap
        flagged in Master-Action-Plan-2026.md:378 (P9 continuation hook).

        Patent angle: detecting settlement confirmation from disparate payment
        network rails for a single UETR-tracked payment.

        Args:
            parent_uetr: Upstream cross-border UETR (typically SWIFT).
            child_uetr: Downstream domestic-rail UETR / end-to-end ID.
            child_rail: One of FEDNOW, RTP, SEPA.
            timestamp: Override registration time (default: now). Used in tests.

        Raises:
            ValueError: child_rail is not a recognised handoff rail.
        """
        if child_rail.upper() not in _VALID_HANDOFF_RAILS:
            raise ValueError(
                f"child_rail must be one of {sorted(_VALID_HANDOFF_RAILS)}; "
                f"got {child_rail!r}"
            )
        ts = timestamp or datetime.now(timezone.utc)
        with self._lock:
            self._handoffs[child_uetr] = (parent_uetr, ts)

    def find_parent(
        self, child_uetr: str, at: Optional[datetime] = None
    ) -> Optional[str]:
        """Reverse lookup: given a child UETR, return its parent if within TTL.

        Returns None when no handoff is registered or when the registration
        is older than _HANDOFF_TTL_MINUTES.
        """
        with self._lock:
            entry = self._handoffs.get(child_uetr)
        if entry is None:
            return None
        parent, registered_at = entry
        now = at or datetime.now(timezone.utc)
        if (now - registered_at) > timedelta(minutes=_HANDOFF_TTL_MINUTES):
            return None
        return parent
