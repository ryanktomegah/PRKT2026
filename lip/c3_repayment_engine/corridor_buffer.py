"""
corridor_buffer.py — 4-tier corridor buffer bootstrap model
Architecture Spec S11.4: P95 settlement latency estimation

Observations are stored with timestamps and pruned on a 90-day rolling window
(Architecture Spec S11.4). The estimation tier is re-evaluated after pruning.

Tier 0: Conservative defaults (no data)
Tier 1: Sparse data (< 30 observations)
Tier 2: Moderate data (30-100 observations)
Tier 3: Pure P95 from data (> 100 observations)
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Tier thresholds — Architecture Spec S11.4
_TIER1_MIN = 1
_TIER1_MAX = 29
_TIER2_MIN = 30
_TIER2_MAX = 100
_TIER3_MIN = 101

_P95_PERCENTILE = 95.0
_WINDOW_DAYS = 90
_WINDOW_SECONDS: float = _WINDOW_DAYS * 86_400.0

# Bootstrap CI convergence tolerance — Efron & Tibshirani (1993) §13.3.
# Iteration stops when successive P95 estimates differ by less than this factor.
_BOOTSTRAP_CONVERGENCE: float = 1.01979


def _default_corridor_defaults() -> dict:
    # Tier 0 defaults (days) — Architecture Spec S11.4
    # Updated 2026-03-16 against data-derived P95 values from payments_synthetic.parquet
    # (2M records, seed=42, BIS/SWIFT GPI calibrated):
    #   Class A (routing/account):   P95 =   7.05h = 0.29 days  → major corridors ~0.3d
    #   Class B (compliance holds):  P95 =  53.58h = 2.23 days  → major corridors ~2.5d
    #   Class C (liquidity/timing):  P95 = 170.67h = 7.11 days  → DEFAULT 7.0 days confirmed
    # Defaults represent the weighted mix across all rejection classes for each corridor.
    # Canonical hours available in lip.common.constants.SETTLEMENT_P95_CLASS_{A,B,C}_HOURS.
    return {
        "USD_EUR": 3.0,
        "USD_GBP": 3.0,
        "USD_JPY": 1.5,
        "USD_CNY": 5.0,
        "EUR_GBP": 1.5,
        "EUR_USD": 3.0,
        "GBP_USD": 3.0,
        "DEFAULT": 7.0,
    }


@dataclass
class CorridorBufferDefaults:
    """Tier 0 conservative defaults for major currency corridors.

    Keys are formatted as ``<FROM>_<TO>`` (e.g. ``USD_EUR``).
    The ``DEFAULT`` key is used as a fallback for unknown corridors.
    Values represent P95 settlement latency in calendar days.
    """

    defaults: dict = field(default_factory=_default_corridor_defaults)

    def get(self, corridor: str) -> float:
        """Return the default P95 latency for a corridor, falling back to DEFAULT."""
        normalised = corridor.strip().upper()
        return self.defaults.get(normalised, self.defaults.get("DEFAULT", 7.0))


class CorridorBuffer:
    """Maintains per-corridor settlement-time observations and estimates P95.

    Observations are stored as ``(timestamp_unix, settlement_days)`` tuples.
    Entries older than ``_WINDOW_DAYS`` (90 days) are pruned automatically
    on every write and before any P95 estimation.

    The estimation tier is determined by the number of *valid* (in-window)
    observations per corridor:
      - Tier 0 (0 obs)     → use CorridorBufferDefaults
      - Tier 1 (1–29 obs)  → default × 1.5 (conservative padding)
      - Tier 2 (30–100 obs)→ 50 % empirical P95 + 50 % default
      - Tier 3 (> 100 obs) → pure empirical P95
    """

    def __init__(self, defaults: Optional[CorridorBufferDefaults] = None) -> None:
        self._defaults = defaults or CorridorBufferDefaults()
        # Stores (timestamp_unix, settlement_days) tuples per corridor
        self._observations: Dict[str, List[Tuple[float, float]]] = {}

    # ── Observation management ────────────────────────────────────────────────

    def add_observation(self, corridor: str, settlement_days: float) -> None:
        """Record an observed settlement latency (in days) for a corridor.

        The observation is tagged with the current wall-clock timestamp for
        90-day rolling-window enforcement.

        Args:
            corridor: Corridor key, e.g. ``"USD_EUR"``.
            settlement_days: Observed settlement latency in calendar days.
        """
        if settlement_days < 0:
            raise ValueError(
                f"settlement_days must be non-negative, got {settlement_days}"
            )
        key = corridor.strip().upper()
        self._observations.setdefault(key, [])
        self._prune(key)
        self._observations[key].append((time.time(), float(settlement_days)))
        logger.debug(
            "Corridor %s: added observation %.2f days (n=%d)",
            key, settlement_days, len(self._observations[key]),
        )

    # ── Rolling-window pruning ─────────────────────────────────────────────────

    def _prune(self, key: str) -> None:
        """Remove observations older than the 90-day rolling window."""
        cutoff = time.time() - _WINDOW_SECONDS
        before = len(self._observations.get(key, []))
        self._observations[key] = [
            (ts, days)
            for ts, days in self._observations.get(key, [])
            if ts >= cutoff
        ]
        after = len(self._observations[key])
        if before != after:
            logger.debug(
                "Corridor %s: pruned %d expired observation(s) (window=%d days)",
                key, before - after, _WINDOW_DAYS,
            )

    def purge_expired(self) -> int:
        """Purge expired observations from all corridors.

        Returns the total number of observations removed.
        """
        total_removed = 0
        for key in list(self._observations.keys()):
            before = len(self._observations[key])
            self._prune(key)
            total_removed += before - len(self._observations[key])
        if total_removed:
            logger.info(
                "purge_expired: removed %d observation(s) across all corridors",
                total_removed,
            )
        return total_removed

    # ── Tier detection ────────────────────────────────────────────────────────

    def get_buffer_tier(self, corridor: str) -> int:
        """Return the estimation tier for the corridor (0, 1, 2, or 3)."""
        key = corridor.strip().upper()
        self._prune(key)
        n = len(self._observations.get(key, []))
        if n == 0:
            return 0
        if n <= _TIER1_MAX:
            return 1
        if n <= _TIER2_MAX:
            return 2
        return 3

    # ── P95 estimation ────────────────────────────────────────────────────────

    def estimate_p95(self, corridor: str) -> float:
        """Estimate the P95 settlement latency (days) for the corridor.

        Blending strategy is determined by the observation tier after
        applying the 90-day rolling window:
          Tier 0 → default
          Tier 1 → default × 1.5
          Tier 2 → 0.5 × empirical_p95 + 0.5 × default
          Tier 3 → empirical_p95
        """
        key = corridor.strip().upper()
        self._prune(key)
        tier = self.get_buffer_tier(key)
        default_p95 = self._defaults.get(key)

        if tier == 0:
            logger.debug("Corridor %s Tier 0: using default %.2f days", key, default_p95)
            return default_p95

        observations = [days for _, days in self._observations[key]]
        empirical_p95 = float(np.percentile(observations, _P95_PERCENTILE))

        if tier == 1:
            result = default_p95 * 1.5
            logger.debug(
                "Corridor %s Tier 1 (n=%d): conservative %.2f days",
                key, len(observations), result,
            )
            return result

        if tier == 2:
            result = 0.5 * empirical_p95 + 0.5 * default_p95
            logger.debug(
                "Corridor %s Tier 2 (n=%d): blended %.2f days "
                "(empirical=%.2f, default=%.2f)",
                key, len(observations), result, empirical_p95, default_p95,
            )
            return result

        # Tier 3
        logger.debug(
            "Corridor %s Tier 3 (n=%d): pure empirical P95 = %.2f days",
            key, len(observations), empirical_p95,
        )
        return empirical_p95

    # ── Maturity extension ────────────────────────────────────────────────────

    def get_maturity_extension(self, corridor: str) -> int:
        """Return additional whole days to add to the base maturity window.

        The extension is the ceiling of the P95 estimate, rounded to the nearest
        integer day.  This is layered on top of the rejection-class maturity.
        """
        p95 = self.estimate_p95(corridor)
        extension = int(np.ceil(p95))
        logger.debug(
            "Corridor %s maturity extension: +%d days (P95=%.2f)",
            corridor.strip().upper(), extension, p95,
        )
        return extension

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise the buffer state to a plain dict (JSON-safe).

        Observations are stored as ``[timestamp, days]`` pairs to preserve
        the rolling-window state across restarts.
        """
        return {
            "defaults": dict(self._defaults.defaults),
            "observations": {
                corridor: [[ts, days] for ts, days in obs]
                for corridor, obs in self._observations.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CorridorBuffer":
        """Restore a CorridorBuffer from a serialised dict."""
        defaults = CorridorBufferDefaults(defaults=dict(d.get("defaults", {})))
        instance = cls(defaults=defaults)
        for corridor, obs in d.get("observations", {}).items():
            parsed: List[Tuple[float, float]] = []
            for entry in obs:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    parsed.append((float(entry[0]), float(entry[1])))
                else:
                    # Legacy format: bare float — stamp with current time
                    parsed.append((time.time(), float(entry)))
            instance._observations[corridor.upper()] = parsed
        return instance
