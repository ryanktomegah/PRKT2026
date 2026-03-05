"""
baseline.py — Three-model baseline for benchmarking
C2 Spec Section 12: Merton model, Altman Z-score, Financial Ratio model

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import math
from decimal import Decimal
from typing import Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Merton Structural Model
# ---------------------------------------------------------------------------

_SQRT_TWO_PI_INV = 1.0 / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via math.erfc for zero-dependency implementation."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return _SQRT_TWO_PI_INV * math.exp(-0.5 * x * x)


def merton_pd(
    asset_value: float,
    debt: float,
    asset_vol: float,
    risk_free: float,
    T: float = 1.0,
) -> float:
    """Compute the risk-neutral Probability of Default using the Merton (1974) model.

    The firm defaults when its asset value falls below the face value of debt at
    maturity *T*.  The equity is modelled as a European call option on assets.

    Formula
    -------
    distance-to-default (d₂):

        d₂ = [ln(V/D) + (r - σ²/2)T] / (σ√T)

    PD = N(−d₂)   (risk-neutral default probability)

    Parameters
    ----------
    asset_value:
        Current total asset value *V*.
    debt:
        Face value of debt (default barrier) *D*.
    asset_vol:
        Annualised asset volatility *σ* (e.g. 0.20 for 20 %).
    risk_free:
        Continuously compounded risk-free rate *r*.
    T:
        Time to maturity in years (default 1.0).

    Returns
    -------
    float
        Risk-neutral PD in ``[0, 1]``.
    """
    if asset_value <= 0 or debt <= 0 or asset_vol <= 0 or T <= 0:
        return 1.0  # Degenerate inputs → treat as certain default

    try:
        d2 = (
            math.log(asset_value / debt)
            + (risk_free - 0.5 * asset_vol ** 2) * T
        ) / (asset_vol * math.sqrt(T))
    except (ValueError, ZeroDivisionError):
        return 1.0

    pd = _norm_cdf(-d2)
    return float(np.clip(pd, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Altman Z-score Model
# ---------------------------------------------------------------------------


def altman_z_score(
    working_capital: float,
    total_assets: float,
    retained_earnings: float,
    ebit: float,
    market_cap: float,
    total_liabilities: float,
    revenue: float,
) -> float:
    """Compute the original Altman (1968) Z-score for public manufacturing firms.

    Z = 1.2·X₁ + 1.4·X₂ + 3.3·X₃ + 0.6·X₄ + 1.0·X₅

    where:
      X₁ = Working Capital / Total Assets
      X₂ = Retained Earnings / Total Assets
      X₃ = EBIT / Total Assets
      X₄ = Market Capitalisation / Total Liabilities
      X₅ = Revenue / Total Assets

    Parameters
    ----------
    working_capital:
        Current assets minus current liabilities.
    total_assets:
        Total book value of assets.
    retained_earnings:
        Cumulative retained earnings.
    ebit:
        Earnings Before Interest and Taxes.
    market_cap:
        Market capitalisation of equity.
    total_liabilities:
        Total debt obligations (book value).
    revenue:
        Annual revenue.

    Returns
    -------
    float
        Z-score.  Higher values indicate lower distress risk.
        Zones: Z > 2.99 → safe; 1.81–2.99 → grey; Z < 1.81 → distress.
    """
    eps = 1e-9  # avoid division by zero
    ta = total_assets + eps
    tl = total_liabilities + eps

    x1 = working_capital / ta
    x2 = retained_earnings / ta
    x3 = ebit / ta
    x4 = market_cap / tl
    x5 = revenue / ta

    return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5


def altman_pd(z_score: float) -> float:
    """Map an Altman Z-score to an estimated PD.

    Zone definitions (Altman, 1968):

    * **Safe zone**:    Z > 2.99   → PD = 0.05
    * **Grey zone**:    1.81 < Z ≤ 2.99 → PD interpolated linearly from 0.50 to 0.05
    * **Distress zone**: Z ≤ 1.81  → PD = 0.75

    Parameters
    ----------
    z_score:
        Altman Z-score (output of :func:`altman_z_score`).

    Returns
    -------
    float
        Estimated PD in ``[0.05, 0.75]``.
    """
    if z_score > 2.99:
        return 0.05

    if z_score <= 1.81:
        return 0.75

    # Linear interpolation in grey zone [1.81, 2.99] → PD from 0.50 to 0.05
    # At Z = 1.81: PD = 0.50;  at Z = 2.99: PD = 0.05
    t = (z_score - 1.81) / (2.99 - 1.81)  # 0 at lower bound, 1 at upper bound
    pd = 0.50 - t * (0.50 - 0.05)
    return float(np.clip(pd, 0.05, 0.50))


# ---------------------------------------------------------------------------
# Financial-ratio logistic model
# ---------------------------------------------------------------------------

# Logistic regression coefficients derived from historical calibration.
# Intercept and three coefficients for [current_ratio, debt_to_equity, interest_coverage].
_LOGISTIC_INTERCEPT = 0.5
_LOGISTIC_COEF = np.array([-0.8, 0.6, -0.4])


def financial_ratio_pd(
    current_ratio: float,
    debt_to_equity: float,
    interest_coverage: float,
) -> float:
    """Estimate PD from three core financial ratios via a calibrated logistic model.

    The model applies the logistic function to a linear combination of:
    * **current_ratio** (liquidity): higher → lower PD.
    * **debt_to_equity** (leverage): higher → higher PD.
    * **interest_coverage** (solvency): higher → lower PD.

    Parameters
    ----------
    current_ratio:
        Current assets / current liabilities.
    debt_to_equity:
        Total debt / total equity.
    interest_coverage:
        EBIT / interest expense.

    Returns
    -------
    float
        Estimated PD in ``(0, 1)``.
    """
    x = np.array([current_ratio, debt_to_equity, interest_coverage], dtype=np.float64)
    # Clip extreme values for numerical stability
    x = np.clip(x, -100.0, 100.0)
    log_odds = _LOGISTIC_INTERCEPT + float(_LOGISTIC_COEF @ x)
    pd = 1.0 / (1.0 + math.exp(-log_odds))
    return float(np.clip(pd, 1e-6, 1 - 1e-6))


# ---------------------------------------------------------------------------
# BaselineEnsemble
# ---------------------------------------------------------------------------


class BaselineEnsemble:
    """Weighted ensemble of the three baseline PD models.

    Combines Merton, Altman, and financial-ratio models into a single ensemble
    PD used as a benchmark for the production LightGBM ensemble.

    Default weights: Merton 0.40, Altman 0.30, Ratio 0.30.  Weights are
    normalised internally so they need not sum to 1.0.

    Parameters
    ----------
    weights:
        Optional dict with keys ``'merton'``, ``'altman'``, ``'ratio'``
        specifying relative ensemble weights.
    """

    _DEFAULT_WEIGHTS = {"merton": 0.40, "altman": 0.30, "ratio": 0.30}

    def __init__(self, weights: Optional[dict] = None) -> None:
        raw = weights or self._DEFAULT_WEIGHTS
        total = sum(raw.values())
        self._weights = {k: v / total for k, v in raw.items()}

    def predict(self, features: dict) -> dict:
        """Compute PD estimates from all three baseline models and their ensemble.

        The *features* dict must contain at minimum the keys required by
        whichever sub-models are to be invoked.  Missing keys cause the
        corresponding model to default gracefully (returning ``float('nan')``).

        Parameters
        ----------
        features:
            Dict with the following optional key groups:

            **Merton**: ``asset_value``, ``debt``, ``asset_vol``, ``risk_free``,
            ``maturity_years`` (default 1.0).

            **Altman**: ``working_capital``, ``total_assets``, ``retained_earnings``,
            ``ebit``, ``market_cap``, ``total_liabilities``, ``revenue``.

            **Ratio**: ``current_ratio``, ``debt_to_equity``, ``interest_coverage``.

        Returns
        -------
        dict
            Keys: ``merton_pd``, ``altman_pd``, ``ratio_pd``, ``ensemble_pd``.
            All values are floats in ``[0, 1]`` (or ``float('nan')`` when
            insufficient data is available for a sub-model).
        """
        # Merton PD
        try:
            m_pd = merton_pd(
                asset_value=float(features["asset_value"]),
                debt=float(features["debt"]),
                asset_vol=float(features["asset_vol"]),
                risk_free=float(features.get("risk_free", 0.05)),
                T=float(features.get("maturity_years", 1.0)),
            )
        except (KeyError, TypeError, ValueError):
            m_pd = float("nan")

        # Altman PD
        try:
            z = altman_z_score(
                working_capital=float(features["working_capital"]),
                total_assets=float(features["total_assets"]),
                retained_earnings=float(features["retained_earnings"]),
                ebit=float(features["ebit"]),
                market_cap=float(features["market_cap"]),
                total_liabilities=float(features["total_liabilities"]),
                revenue=float(features["revenue"]),
            )
            a_pd = altman_pd(z)
        except (KeyError, TypeError, ValueError):
            a_pd = float("nan")

        # Financial ratio PD
        try:
            r_pd = financial_ratio_pd(
                current_ratio=float(features["current_ratio"]),
                debt_to_equity=float(features["debt_to_equity"]),
                interest_coverage=float(features["interest_coverage"]),
            )
        except (KeyError, TypeError, ValueError):
            r_pd = float("nan")

        # Weighted ensemble — skip NaN components
        components = {
            "merton": m_pd,
            "altman": a_pd,
            "ratio": r_pd,
        }
        valid = {k: v for k, v in components.items() if not math.isnan(v)}
        if valid:
            total_weight = sum(self._weights[k] for k in valid)
            ensemble = sum(
                self._weights[k] * v for k, v in valid.items()
            ) / total_weight
        else:
            ensemble = float("nan")

        return {
            "merton_pd": m_pd,
            "altman_pd": a_pd,
            "ratio_pd": r_pd,
            "ensemble_pd": ensemble,
        }
