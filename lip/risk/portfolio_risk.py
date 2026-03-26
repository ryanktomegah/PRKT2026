"""
portfolio_risk.py — Portfolio-level risk aggregation for LIP.
Required for capital partner conversations (Phase 2).

No bank risk committee will approve deployment without answering
"what is our maximum loss at 99% confidence over 10 days?"
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

from lip.c3_repayment_engine.repayment_loop import ActiveLoan
from lip.risk.concentration import ConcentrationResult, check_concentration_limits

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PortfolioVaR:
    """Parametric Value-at-Risk result (frozen — immutable snapshot)."""

    var_99: Decimal
    var_95: Decimal
    expected_loss: Decimal
    total_exposure: Decimal
    position_count: int
    confidence_level: float
    horizon_days: int


@dataclass
class RiskPosition:
    """Internal representation of a single risk-bearing position."""

    loan_id: str
    corridor: str
    bic: str
    principal: Decimal
    pd: float
    lgd: float
    rejection_class: str
    maturity_days: int


# ── Portfolio Risk Engine ─────────────────────────────────────────────────────


class PortfolioRiskEngine:
    """Portfolio-level risk aggregation for the LIP loan book.

    Thread-safe: all mutations to the internal positions dictionary are
    guarded by a ``threading.Lock``.

    Parametric VaR formula (per-position contribution, then aggregated)::

        EL   = sum(PD_i * LGD_i * EAD_i)
        UL_var = sum(PD_i * (1 - PD_i) * LGD_i^2 * EAD_i^2)
        UL_std = sqrt(UL_var)
        VaR_99 = EL + 2.326 * UL_std   (normal, 99%)
        VaR_95 = EL + 1.645 * UL_std   (normal, 95%)

    Time-horizon scaling: ``sqrt(horizon_days / maturity_days_i)`` applied
    per position before aggregation.
    """

    # Normal quantile constants
    _Z_99 = Decimal("2.326")
    _Z_95 = Decimal("1.645")

    def __init__(
        self,
        max_single_name_pct: float = 0.25,
        max_corridor_hhi: int = 2500,
        var_confidence: float = 0.99,
        var_horizon_days: int = 10,
    ) -> None:
        self._max_single_name_pct = Decimal(str(max_single_name_pct))
        self._max_corridor_hhi = Decimal(str(max_corridor_hhi))
        self._var_confidence = var_confidence
        self._var_horizon_days = var_horizon_days

        self._positions: Dict[str, RiskPosition] = {}
        self._lock = threading.Lock()

    # ── Position management ───────────────────────────────────────────────

    def add_position(self, loan: ActiveLoan, pd: float, lgd: float) -> None:
        """Register an active loan as a risk position.

        Parameters
        ----------
        loan:
            An ``ActiveLoan`` from the repayment engine.
        pd:
            Probability of default (annualised, in [0, 1]).
        lgd:
            Loss given default (fraction, in [0, 1]).
        """
        maturity_delta = loan.maturity_date - loan.funded_at
        maturity_days = max(maturity_delta.days, 1)  # floor at 1 day

        # Extract BIC from the loan's licensee_id if available,
        # otherwise derive from corridor (first currency's implicit BIC).
        bic = loan.licensee_id if loan.licensee_id else loan.corridor

        position = RiskPosition(
            loan_id=loan.loan_id,
            corridor=loan.corridor,
            bic=bic,
            principal=loan.principal,
            pd=pd,
            lgd=lgd,
            rejection_class=loan.rejection_class,
            maturity_days=maturity_days,
        )

        with self._lock:
            self._positions[loan.loan_id] = position

    def remove_position(self, loan_id: str) -> None:
        """Remove a position by loan ID.

        Raises
        ------
        KeyError
            If *loan_id* is not in the current position set.
        """
        with self._lock:
            del self._positions[loan_id]

    @property
    def positions(self) -> List[RiskPosition]:
        """Return a snapshot of current positions (copy, not live view)."""
        with self._lock:
            return list(self._positions.values())

    # ── VaR computation ───────────────────────────────────────────────────

    def compute_var(self) -> PortfolioVaR:
        """Compute parametric (variance-covariance) VaR for the portfolio.

        Assumes independent defaults (no correlation) — conservative for a
        diversified book, aggressive for concentrated corridors.  The
        concentration module should be checked alongside VaR.

        Returns
        -------
        PortfolioVaR
            Frozen dataclass with VaR_99, VaR_95, expected loss, etc.
        """
        with self._lock:
            snapshot = list(self._positions.values())

        if not snapshot:
            return PortfolioVaR(
                var_99=Decimal("0"),
                var_95=Decimal("0"),
                expected_loss=Decimal("0"),
                total_exposure=Decimal("0"),
                position_count=0,
                confidence_level=self._var_confidence,
                horizon_days=self._var_horizon_days,
            )

        el_total = Decimal("0")
        ul_variance_total = Decimal("0")
        total_exposure = Decimal("0")

        horizon = Decimal(str(self._var_horizon_days))

        for pos in snapshot:
            ead = pos.principal
            total_exposure += ead

            pd_d = Decimal(str(pos.pd))
            lgd_d = Decimal(str(pos.lgd))
            maturity_d = Decimal(str(pos.maturity_days))

            # Time-horizon scaling factor: sqrt(horizon / maturity)
            time_scale = Decimal(
                str(math.sqrt(float(horizon) / float(maturity_d)))
            )

            # Expected loss contribution
            el_i = pd_d * lgd_d * ead * time_scale
            el_total += el_i

            # Unexpected-loss variance contribution
            # UL_var_i = PD * (1 - PD) * LGD^2 * EAD^2 * (horizon / maturity)
            ul_var_i = (
                pd_d
                * (Decimal("1") - pd_d)
                * lgd_d * lgd_d
                * ead * ead
                * time_scale * time_scale
            )
            ul_variance_total += ul_var_i

        # Portfolio unexpected-loss standard deviation
        ul_std = Decimal(str(math.sqrt(float(ul_variance_total))))

        var_99 = (el_total + self._Z_99 * ul_std).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        var_95 = (el_total + self._Z_95 * ul_std).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        el_total = el_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return PortfolioVaR(
            var_99=var_99,
            var_95=var_95,
            expected_loss=el_total,
            total_exposure=total_exposure,
            position_count=len(snapshot),
            confidence_level=self._var_confidence,
            horizon_days=self._var_horizon_days,
        )

    # ── Concentration ─────────────────────────────────────────────────────

    def compute_concentration(
        self, dimension: str = "corridor"
    ) -> ConcentrationResult:
        """Compute concentration metrics along a given dimension.

        Parameters
        ----------
        dimension:
            ``"corridor"`` groups positions by corridor key (e.g. USD_EUR).
            ``"bic"`` groups by originating-bank BIC / licensee ID.

        Returns
        -------
        ConcentrationResult
            HHI, any breaches, and overall pass/fail.

        Raises
        ------
        ValueError
            If *dimension* is not ``"corridor"`` or ``"bic"``.
        """
        if dimension not in ("corridor", "bic"):
            raise ValueError(
                f"dimension must be 'corridor' or 'bic', got '{dimension}'"
            )

        with self._lock:
            snapshot = list(self._positions.values())

        exposures: Dict[str, Decimal] = {}
        for pos in snapshot:
            key = pos.corridor if dimension == "corridor" else pos.bic
            exposures[key] = exposures.get(key, Decimal("0")) + pos.principal

        return check_concentration_limits(
            exposures=exposures,
            max_single_name_pct=self._max_single_name_pct,
            max_hhi=self._max_corridor_hhi,
        )

    # ── Summary ───────────────────────────────────────────────────────────

    def get_risk_summary(self) -> dict:
        """Produce a full risk report as a plain dictionary.

        Returns
        -------
        dict
            Keys: ``var``, ``concentration_corridor``, ``concentration_bic``,
            ``position_count``, ``total_exposure``.
        """
        var_result = self.compute_var()
        conc_corridor = self.compute_concentration("corridor")
        conc_bic = self.compute_concentration("bic")

        return {
            "var": {
                "var_99": str(var_result.var_99),
                "var_95": str(var_result.var_95),
                "expected_loss": str(var_result.expected_loss),
                "total_exposure": str(var_result.total_exposure),
                "position_count": var_result.position_count,
                "confidence_level": var_result.confidence_level,
                "horizon_days": var_result.horizon_days,
            },
            "corridor_concentration": {
                "hhi": str(conc_corridor.hhi),
                "is_within_limits": conc_corridor.is_within_limits,
                "breaches": [
                    {
                        "entity": b.entity,
                        "exposure_pct": str(b.exposure_pct),
                        "limit_pct": str(b.limit_pct),
                        "breach_type": b.breach_type,
                    }
                    for b in conc_corridor.breaches
                ],
            },
            "bic_concentration": {
                "hhi": str(conc_bic.hhi),
                "is_within_limits": conc_bic.is_within_limits,
                "breaches": [
                    {
                        "entity": b.entity,
                        "exposure_pct": str(b.exposure_pct),
                        "limit_pct": str(b.limit_pct),
                        "breach_type": b.breach_type,
                    }
                    for b in conc_bic.breaches
                ],
            },
            "position_count": var_result.position_count,
            "total_exposure": str(var_result.total_exposure),
        }
