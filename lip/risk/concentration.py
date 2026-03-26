"""
concentration.py — Corridor and BIC concentration metrics.
Implements Herfindahl-Hirschman Index (HHI) and single-name exposure limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConcentrationBreach:
    """A single concentration-limit violation."""

    entity: str
    exposure_pct: Decimal
    limit_pct: Decimal
    breach_type: str  # "SINGLE_NAME" or "HHI"


@dataclass
class ConcentrationResult:
    """Aggregate result of a concentration-limit check."""

    hhi: Decimal
    breaches: List[ConcentrationBreach] = field(default_factory=list)
    is_within_limits: bool = True


# ── Core functions ────────────────────────────────────────────────────────────


def compute_hhi(exposures: Dict[str, Decimal]) -> Decimal:
    """Compute the Herfindahl-Hirschman Index for a set of exposures.

    HHI = sum(share_i ** 2) where share_i = exposure_i / total.
    Result is normalised to basis points (range [0, 10_000]).
    An HHI above 2500 indicates a highly concentrated portfolio.

    Parameters
    ----------
    exposures:
        Mapping of entity name to absolute exposure amount.

    Returns
    -------
    Decimal in [0, 10000].

    Raises
    ------
    ValueError
        If *exposures* is empty or all values are zero.
    """
    if not exposures:
        return Decimal("0")

    total = sum(exposures.values())
    if total == 0:
        return Decimal("0")

    hhi = Decimal("0")
    for exposure in exposures.values():
        share = exposure / total
        # share is in [0, 1]; share^2 also in [0, 1]
        hhi += share * share

    # Normalise to basis-point scale: multiply by 10_000
    hhi_bps = (hhi * Decimal("10000")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return hhi_bps


def check_concentration_limits(
    exposures: Dict[str, Decimal],
    max_single_name_pct: Decimal = Decimal("0.25"),
    max_hhi: Decimal = Decimal("2500"),
) -> ConcentrationResult:
    """Check single-name and HHI concentration limits.

    Parameters
    ----------
    exposures:
        Mapping of entity name to absolute exposure amount.
    max_single_name_pct:
        Maximum allowable share for any single entity (default 25%).
    max_hhi:
        Maximum allowable HHI in basis points (default 2500).

    Returns
    -------
    ConcentrationResult with HHI, any breaches, and overall pass/fail.
    """
    if not exposures:
        return ConcentrationResult(
            hhi=Decimal("0"),
            breaches=[],
            is_within_limits=True,
        )

    total = sum(exposures.values())
    if total == 0:
        return ConcentrationResult(
            hhi=Decimal("0"),
            breaches=[],
            is_within_limits=True,
        )

    hhi = compute_hhi(exposures)
    breaches: List[ConcentrationBreach] = []

    # ── Single-name checks ────────────────────────────────────────────────
    for entity, exposure in exposures.items():
        share = (exposure / total).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        if share > max_single_name_pct:
            breaches.append(
                ConcentrationBreach(
                    entity=entity,
                    exposure_pct=share,
                    limit_pct=max_single_name_pct,
                    breach_type="SINGLE_NAME",
                )
            )

    # ── HHI check ─────────────────────────────────────────────────────────
    if hhi > max_hhi:
        breaches.append(
            ConcentrationBreach(
                entity="PORTFOLIO",
                exposure_pct=hhi,
                limit_pct=max_hhi,
                breach_type="HHI",
            )
        )

    is_within = len(breaches) == 0
    return ConcentrationResult(
        hhi=hhi,
        breaches=breaches,
        is_within_limits=is_within,
    )
