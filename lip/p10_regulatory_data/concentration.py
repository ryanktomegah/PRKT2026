"""
concentration.py — Corridor and jurisdiction concentration metrics.

Implements Herfindahl-Hirschman Index (HHI) on 0.0-1.0 scale for
corridor-level payment volume concentration. Used by SystemicRiskEngine
to detect concentration risk across the cross-border payment network.

QUANT authority: HHI formula, threshold calibration.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .constants import P10_HHI_CONCENTRATION_THRESHOLD


@dataclass(frozen=True)
class ConcentrationResult:
    """HHI concentration measurement for one dimension."""

    dimension: str  # "corridor" or "jurisdiction"
    hhi: float  # 0.0 (perfectly dispersed) to 1.0 (single entity)
    effective_count: float  # 1/HHI — equivalent number of equal participants
    is_concentrated: bool  # hhi >= P10_HHI_CONCENTRATION_THRESHOLD
    top_entities: List[Tuple[str, float]]  # (entity_id, share) top 5


class CorridorConcentrationAnalyzer:
    """Compute HHI concentration metrics from corridor volume data.

    HHI formula: sum(share_i^2) where share_i = volume_i / total_volume.
    Scale: 0.0-1.0 (not basis points). HHI >= 0.25 = "highly concentrated"
    (fewer than 4 effective participants).

    Thread-safety: stateless — safe for concurrent use.
    """

    _threshold = float(P10_HHI_CONCENTRATION_THRESHOLD)

    def compute_corridor_concentration(
        self,
        corridor_volumes: Dict[str, float],
    ) -> ConcentrationResult:
        """HHI across corridors by payment volume."""
        hhi, effective_count, top = self._compute_hhi(corridor_volumes)
        return ConcentrationResult(
            dimension="corridor",
            hhi=hhi,
            effective_count=effective_count,
            is_concentrated=hhi >= self._threshold,
            top_entities=top,
        )

    def compute_jurisdiction_concentration(
        self,
        corridor_volumes: Dict[str, float],
    ) -> ConcentrationResult:
        """HHI across jurisdictions (extracted from corridor pairs).

        Jurisdiction extraction: corridor "EUR-USD" contributes half its
        volume to "EUR" and half to "USD".
        """
        jurisdiction_volumes: Dict[str, float] = defaultdict(float)
        for corridor, volume in corridor_volumes.items():
            parts = corridor.split("-")
            if len(parts) == 2:
                jurisdiction_volumes[parts[0]] += volume / 2.0
                jurisdiction_volumes[parts[1]] += volume / 2.0
            else:
                jurisdiction_volumes[corridor] += volume

        hhi, effective_count, top = self._compute_hhi(dict(jurisdiction_volumes))
        return ConcentrationResult(
            dimension="jurisdiction",
            hhi=hhi,
            effective_count=effective_count,
            is_concentrated=hhi >= self._threshold,
            top_entities=top,
        )

    @staticmethod
    def _compute_hhi(
        volumes: Dict[str, float],
    ) -> Tuple[float, float, List[Tuple[str, float]]]:
        """Compute HHI, effective count, and top-5 entities from volumes.

        Returns:
            (hhi, effective_count, top_entities) where hhi is on [0, 1] scale.
        """
        if not volumes:
            return 0.0, 0.0, []

        total = sum(volumes.values())
        if total <= 0:
            return 0.0, 0.0, []

        shares = {k: v / total for k, v in volumes.items()}
        hhi = sum(s * s for s in shares.values())
        effective_count = 1.0 / hhi if hhi > 0 else 0.0

        # Top 5 by share descending
        sorted_entities = sorted(shares.items(), key=lambda x: x[1], reverse=True)
        top_entities = sorted_entities[:5]

        return hhi, effective_count, top_entities
