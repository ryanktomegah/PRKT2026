"""
merton_kmv.py — Robust Merton-KMV Iterative Solver
Tier 1 R&D: Algorithmic Pedigree Upgrade

This module implements the iterative procedure to back out unobservable
asset value (V_A) and asset volatility (sigma_A) from observable equity
market value (V_E) and equity volatility (sigma_E).

Reference:
  Crosbie, P., & Bohn, J. (2003). "Modeling Default Risk". Moody's KMV.
"""

import logging
import math
from typing import Tuple

logger = logging.getLogger(__name__)

_SQRT_TWO_PI_INV = 1.0 / math.sqrt(2.0 * math.pi)

def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def _norm_pdf(x: float) -> float:
    return _SQRT_TWO_PI_INV * math.exp(-0.5 * x * x)

class MertonKMVSolver:
    """Iterative solver for implied asset value and volatility.

    Solves the system:
      1) V_E = V_A * N(d1) - D * exp(-r*T) * N(d2)
      2) sigma_E * V_E = N(d1) * sigma_A * V_A

    where:
      d1 = [ln(V_A/D) + (r + 0.5*sigma_A^2)*T] / (sigma_A * sqrt(T))
      d2 = d1 - sigma_A * sqrt(T)
    """

    def __init__(
        self,
        max_iter: int = 100,
        tolerance: float = 1e-6,
    ) -> None:
        self.max_iter = max_iter
        self.tolerance = tolerance

    def solve(
        self,
        equity_value: float,
        equity_vol: float,
        debt: float,
        risk_free: float,
        T: float
    ) -> Tuple[float, float, float]:
        """Back out V_A and sigma_A using an iterative search.

        Returns:
            (asset_value, asset_vol, distance_to_default)
        """
        if equity_value <= 0 or debt <= 0 or equity_vol <= 0:
            return 0.0, 0.0, -99.0

        # Initial guesses
        # 1. V_A ~ V_E + D
        # 2. sigma_A ~ sigma_E * (V_E / (V_E + D))
        v_a = equity_value + debt
        sigma_a = equity_vol * (equity_value / v_a)

        for i in range(self.max_iter):
            sqrt_t = math.sqrt(T)
            exp_rt = math.exp(-risk_free * T)

            # --- Internal Equations ---
            d1 = (math.log(v_a / debt) + (risk_free + 0.5 * sigma_a**2) * T) / (sigma_a * sqrt_t)
            d2 = d1 - sigma_a * sqrt_t

            n_d1 = _norm_cdf(d1)
            n_d2 = _norm_cdf(d2)

            if n_d1 < 1e-10:
                logger.warning(
                    "N(d1)=%.2e at iter %d — distressed firm, returning last valid iterate. "
                    "V_A=%.2f D=%.2f", n_d1, i, v_a, debt
                )
                break

            # Equity value from current guesses (Model V_E)
            v_e_model = v_a * n_d1 - debt * exp_rt * n_d2

            # Update sigma_A using relationship (2): sigma_A = (sigma_E * V_E) / (N(d1) * V_A)
            # This is the KMV 'fixed-point' approach
            denom_sigma = n_d1 * v_a
            if denom_sigma < 1e-12:
                sigma_a_new = sigma_a
            else:
                sigma_a_new = (equity_vol * equity_value) / denom_sigma

            # Update V_A using Newton-Raphson step for V_A
            # f(V_A) = V_A*N(d1) - D*exp(-rT)*N(d2) - V_E_actual
            # f'(V_A) = N(d1)
            v_a_new = v_a - (v_e_model - equity_value) / n_d1

            # Convergence check
            diff = abs(v_a_new - v_a) / v_a + abs(sigma_a_new - sigma_a) / sigma_a

            v_a = max(v_a_new, self.tolerance)  # Physical constraint: V_A > 0
            sigma_a = max(sigma_a_new, self.tolerance) # Physical constraint: sigma_A > 0

            if diff < self.tolerance:
                break
        else:
            logger.warning("Merton solver failed to converge after %d iterations", self.max_iter)

        # Final Distance to Default
        d1_final = (math.log(v_a / debt) + (risk_free + 0.5 * sigma_a**2) * T) / (sigma_a * math.sqrt(T))
        dd = d1_final - sigma_a * math.sqrt(T) # d2 is the market standard DD

        return v_a, sigma_a, dd

def compute_merton_dd(
    equity_value: float,
    equity_vol: float,
    debt: float,
    risk_free: float,
    T: float
) -> float:
    """Helper to get just the DD."""
    solver = MertonKMVSolver()
    _, _, dd = solver.solve(equity_value, equity_vol, debt, risk_free, T)
    return dd
