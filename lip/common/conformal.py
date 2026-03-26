"""
conformal.py — Split conformal prediction for LIP model outputs.
EU AI Act Art.13 transparency requirement: guaranteed-coverage confidence intervals.
SR 11-7: principled model uncertainty quantification for examiner review.

Reference: Angelopoulos & Bates, "Conformal Prediction: A Gentle Introduction,"
Foundations and Trends in ML, 2023.

Algorithm:
  1. During calibration: compute nonconformity scores on a held-out calibration set
     scores_i = |y_i - ŷ_i| for regression, or 1 - f(x_i)_{y_i} for classification
  2. At inference: prediction interval = [ŷ - q, ŷ + q]
     where q = quantile(scores, ceil((n+1)(1-α))/n)

Latency: <1ms per prediction (split conformal is a single quantile lookup).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from lip.common.constants import FEE_FLOOR_BPS

logger = logging.getLogger(__name__)

# ── Uncertainty pricing ──────────────────────────────────────────────────────
# 50% fee increase per unit of interval width.  Conservative — wider uncertainty
# means higher credit risk, which should be priced into the fee.
UNCERTAINTY_SCALE_FACTOR = 0.5


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConformalInterval:
    lower: float
    upper: float
    point: float
    width: float
    coverage_level: float


# ── Pure-numpy split conformal predictor ─────────────────────────────────────

class ConformalPredictor:
    """Distribution-free prediction intervals via split conformal prediction.

    Works with any point-prediction model. No distributional assumptions.
    Calibrate once on a held-out set, then wrap every inference with an interval.
    """

    def __init__(self, coverage_level: float = 0.90) -> None:
        if not 0.0 < coverage_level < 1.0:
            raise ValueError(
                f"coverage_level must be in (0, 1), got {coverage_level}"
            )
        self._coverage_level = coverage_level
        self._scores: Optional[np.ndarray] = None
        self._quantile: Optional[float] = None

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_calibrated(self) -> bool:
        return self._quantile is not None

    @property
    def coverage_level(self) -> float:
        return self._coverage_level

    @property
    def calibration_size(self) -> int:
        if self._scores is None:
            return 0
        return len(self._scores)

    # ── Calibration ──────────────────────────────────────────────────────

    def calibrate(self, predictions: np.ndarray, actuals: np.ndarray) -> None:
        predictions = np.asarray(predictions, dtype=np.float64).ravel()
        actuals = np.asarray(actuals, dtype=np.float64).ravel()

        if len(predictions) != len(actuals):
            raise ValueError(
                f"predictions and actuals must have the same length, "
                f"got {len(predictions)} and {len(actuals)}"
            )
        if len(predictions) < 2:
            raise ValueError(
                "Need at least 2 calibration samples for a meaningful quantile"
            )

        # Nonconformity scores: absolute residuals
        self._scores = np.sort(np.abs(actuals - predictions))
        n = len(self._scores)

        # Conformal quantile level: ceil((n+1)(1-alpha)) / n
        alpha = 1.0 - self._coverage_level
        quantile_level = math.ceil((n + 1) * (1.0 - alpha)) / n
        # Clamp to [0, 1] — when n is small, ceil can push above 1.0
        quantile_level = min(quantile_level, 1.0)

        self._quantile = float(np.quantile(self._scores, quantile_level))

        logger.info(
            "Conformal predictor calibrated: n=%d, coverage=%.2f, quantile=%.6f",
            n, self._coverage_level, self._quantile,
        )

    # ── Inference ────────────────────────────────────────────────────────

    def predict_interval(self, point_prediction: float) -> ConformalInterval:
        if not self.is_calibrated:
            raise RuntimeError(
                "ConformalPredictor is not calibrated — call calibrate() first"
            )
        q = self._quantile  # type: ignore[assignment]
        lower = point_prediction - q
        upper = point_prediction + q
        return ConformalInterval(
            lower=lower,
            upper=upper,
            point=point_prediction,
            width=upper - lower,
            coverage_level=self._coverage_level,
        )

    def predict_intervals_batch(
        self, predictions: np.ndarray
    ) -> list[ConformalInterval]:
        predictions = np.asarray(predictions, dtype=np.float64).ravel()
        return [self.predict_interval(float(p)) for p in predictions]


# ── MAPIE wrapper (optional dependency) ──────────────────────────────────────

def _try_import_mapie():
    """Import MapieRegressor from MAPIE, returning None if unavailable."""
    try:
        from mapie.regression import MapieRegressor
        return MapieRegressor
    except ImportError:
        return None


_MapieRegressor = _try_import_mapie()


if _MapieRegressor is not None:

    class MAPIEConformalPredictor:
        """Conformal predictor backed by MAPIE's MapieRegressor.

        Use this when you have a scikit-learn–compatible estimator and want
        MAPIE's richer conformalization strategies (jackknife+, CV+, etc.).
        Falls back to ConformalPredictor if MAPIE is not installed.
        """

        def __init__(
            self,
            estimator,
            *,
            method: str = "plus",
            coverage_level: float = 0.90,
        ) -> None:
            if not 0.0 < coverage_level < 1.0:
                raise ValueError(
                    f"coverage_level must be in (0, 1), got {coverage_level}"
                )
            self._coverage_level = coverage_level
            self._mapie = _MapieRegressor(
                estimator=estimator,
                method=method,
            )
            self._fitted = False

        @property
        def is_calibrated(self) -> bool:
            return self._fitted

        @property
        def coverage_level(self) -> float:
            return self._coverage_level

        def fit(self, X: np.ndarray, y: np.ndarray) -> None:
            self._mapie.fit(X, y)
            self._fitted = True
            logger.info(
                "MAPIEConformalPredictor fitted: n=%d, coverage=%.2f",
                len(y), self._coverage_level,
            )

        def predict_intervals_batch(
            self, X: np.ndarray
        ) -> list[ConformalInterval]:
            if not self._fitted:
                raise RuntimeError(
                    "MAPIEConformalPredictor is not fitted — call fit() first"
                )
            alpha = 1.0 - self._coverage_level
            y_pred, y_pis = self._mapie.predict(X, alpha=alpha)

            intervals: list[ConformalInterval] = []
            for i in range(len(y_pred)):
                lower = float(y_pis[i, 0, 0])
                upper = float(y_pis[i, 1, 0])
                point = float(y_pred[i])
                intervals.append(ConformalInterval(
                    lower=lower,
                    upper=upper,
                    point=point,
                    width=upper - lower,
                    coverage_level=self._coverage_level,
                ))
            return intervals

    logger.debug("MAPIE available — MAPIEConformalPredictor registered")

else:
    logger.debug(
        "MAPIE not installed — using pure-numpy ConformalPredictor only"
    )


# ── Fee adjustment for model uncertainty ─────────────────────────────────────

def uncertainty_fee_adjustment(
    interval_width: float,
    baseline_fee_bps: int,
) -> int:
    """Adjust fee upward based on prediction interval width.

    Wider uncertainty → higher credit risk → higher fee.  Economically correct:
    the lender should be compensated for bearing more model uncertainty.

    Formula:
        adjusted = baseline_fee_bps * (1 + interval_width * UNCERTAINTY_SCALE_FACTOR)
        return max(adjusted, FEE_FLOOR_BPS)

    Parameters
    ----------
    interval_width:
        Width of the conformal prediction interval (upper - lower).
    baseline_fee_bps:
        Unadjusted fee in basis points from the C2 PD model.

    Returns
    -------
    int
        Adjusted fee in integer basis points, floored at FEE_FLOOR_BPS (300).
    """
    adjusted = baseline_fee_bps * (1.0 + interval_width * UNCERTAINTY_SCALE_FACTOR)
    floor = int(FEE_FLOOR_BPS)
    return max(math.ceil(adjusted), floor)
