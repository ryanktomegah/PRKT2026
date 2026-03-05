"""
instrumentation.py — Pipeline latency tracking and per-component timing.
Architecture Spec v1.2 Section 3: E2E latency p50 < 100ms target.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from __future__ import annotations

import statistics
import time
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional


class LatencyTracker:
    """Records per-component and end-to-end latency samples.

    Supports recording explicit values, a context-manager for automatic timing,
    and p50/p99 percentile queries over accumulated samples.

    Architecture Spec v1.2 Section 3 target:
        p50 < 100 ms for the full in-process pipeline (no network I/O).
    """

    def __init__(self) -> None:
        self._samples: Dict[str, List[float]] = {}

    # ── Recording ─────────────────────────────────────────────────────────────

    def record(self, component: str, latency_ms: float) -> None:
        """Record a single latency observation for a named component.

        Parameters
        ----------
        component:
            Short name for the pipeline component (e.g. ``"c1"``, ``"total"``).
        latency_ms:
            Observed latency in milliseconds.
        """
        self._samples.setdefault(component, []).append(latency_ms)

    @contextmanager
    def measure(self, component: str) -> Generator[None, None, None]:
        """Context manager that times the enclosed block and records the result.

        Parameters
        ----------
        component:
            Name of the component being timed.

        Example
        -------
        >>> tracker = LatencyTracker()
        >>> with tracker.measure("c1"):
        ...     result = c1_engine.predict(payment)
        """
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1_000.0
            self.record(component, elapsed_ms)

    # ── Queries ───────────────────────────────────────────────────────────────

    def p50(self, component: str) -> Optional[float]:
        """Return the median (p50) latency in ms for *component*, or None."""
        samples = self._samples.get(component, [])
        if not samples:
            return None
        return statistics.median(samples)

    def p99(self, component: str) -> Optional[float]:
        """Return the 99th-percentile latency in ms for *component*, or None."""
        samples = self._samples.get(component, [])
        if not samples:
            return None
        sorted_s = sorted(samples)
        idx = max(0, int(len(sorted_s) * 0.99) - 1)
        return sorted_s[idx]

    def latest(self, component: str) -> Optional[float]:
        """Return the most recently recorded latency for *component*, or None."""
        samples = self._samples.get(component, [])
        return samples[-1] if samples else None

    def get_latest_all(self) -> Dict[str, float]:
        """Return a dict of ``{component: last_recorded_ms}`` for all tracked components."""
        return {
            comp: samples[-1]
            for comp, samples in self._samples.items()
            if samples
        }

    def sample_count(self, component: str) -> int:
        """Return the number of recorded samples for *component*."""
        return len(self._samples.get(component, []))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all recorded samples."""
        self._samples.clear()
