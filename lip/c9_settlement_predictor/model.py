"""
model.py — Settlement time prediction via Cox Proportional Hazards.
C9 Spec: Predict time-to-settlement for payment rejection events.

Capital efficiency multiplier: a Class B EUR/USD payment between Tier 1 banks
might resolve in 18 hours. Static 7-day maturity wastes 6+ days of capital.
Dynamic maturity = faster capital rotation = more loans per unit of capital.

Survival analysis model: Cox proportional hazards via ``lifelines``.
Upgrade path: DeepSurv via ``pycox`` for non-linear interactions.

Reference:
  - Cox, "Regression Models and Life-Tables," JRSS-B, 1972
  - Katzman et al., "DeepSurv," BMC Medical Research Methodology, 2018
  - Kvamme et al., "Time-to-Event Prediction with Neural Networks," JMLR, 2019

Features:
  - corridor (categorical → one-hot)
  - rejection_class (A/B/C)
  - amount_usd (log-scaled)
  - hour_of_day (cyclical encoding)
  - day_of_week (cyclical encoding)
  - sending_bic_tier (1/2/3)
  - receiving_bic_tier (1/2/3)
  - historical_corridor_p50_hours
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from lip.common.constants import (
    MATURITY_CLASS_A_DAYS,
    MATURITY_CLASS_B_DAYS,
    MATURITY_CLASS_C_DAYS,
)

logger = logging.getLogger(__name__)

# Static maturity windows become fallback defaults when C9 is unavailable
_STATIC_MATURITY_HOURS: Dict[str, float] = {
    "CLASS_A": MATURITY_CLASS_A_DAYS * 24.0,
    "CLASS_B": MATURITY_CLASS_B_DAYS * 24.0,
    "CLASS_C": MATURITY_CLASS_C_DAYS * 24.0,
}

# Safety margin: predicted settlement time is multiplied by this factor
# to provide a buffer against early maturity. QUANT sign-off required.
SETTLEMENT_SAFETY_MARGIN = 1.5

# Minimum maturity in hours — even if the model predicts 2h settlement,
# the loan must be outstanding long enough to generate meaningful fee.
MIN_MATURITY_HOURS = 12.0

# Maximum maturity override — C9 cannot extend beyond the static window.
# If the model predicts longer settlement, fall back to static maturity.
MAX_MATURITY_OVERRIDE_FACTOR = 1.0  # 1.0 = cannot exceed static window


@dataclass(frozen=True)
class SettlementPrediction:
    """Result of a C9 settlement time prediction.

    Attributes:
        predicted_hours: Median predicted settlement time in hours.
        confidence_lower_hours: Lower bound of 80% prediction interval.
        confidence_upper_hours: Upper bound of 80% prediction interval.
        dynamic_maturity_hours: Recommended maturity (with safety margin).
        static_maturity_hours: Fallback static maturity from constants.
        using_dynamic: True if dynamic maturity is being used.
        inference_latency_ms: Wall-clock latency in milliseconds.
        model_type: "cox_ph" | "deepsurv" | "fallback".
    """
    predicted_hours: float
    confidence_lower_hours: float
    confidence_upper_hours: float
    dynamic_maturity_hours: float
    static_maturity_hours: float
    using_dynamic: bool
    inference_latency_ms: float
    model_type: str


def _encode_features(
    corridor: str,
    rejection_class: str,
    amount_usd: float,
    timestamp: Optional[datetime] = None,
    sending_bic_tier: int = 3,
    receiving_bic_tier: int = 3,
    historical_p50_hours: float = 0.0,
) -> np.ndarray:
    """Encode raw payment features into the C9 feature vector.

    Returns a 1D numpy array suitable for the Cox PH model.
    """
    features = []

    # Amount (log-scaled, clipped)
    features.append(math.log1p(max(amount_usd, 0)))

    # Rejection class one-hot: [is_A, is_B, is_C]
    features.append(1.0 if rejection_class == "CLASS_A" else 0.0)
    features.append(1.0 if rejection_class == "CLASS_B" else 0.0)
    features.append(1.0 if rejection_class == "CLASS_C" else 0.0)

    # BIC tiers
    features.append(float(sending_bic_tier))
    features.append(float(receiving_bic_tier))

    # Time-of-day cyclical encoding
    if timestamp is not None:
        hour = timestamp.hour + timestamp.minute / 60.0
        features.append(math.sin(2 * math.pi * hour / 24.0))
        features.append(math.cos(2 * math.pi * hour / 24.0))
        dow = timestamp.weekday()
        features.append(math.sin(2 * math.pi * dow / 7.0))
        features.append(math.cos(2 * math.pi * dow / 7.0))
    else:
        features.extend([0.0, 1.0, 0.0, 1.0])  # noon Monday default

    # Historical corridor settlement time
    features.append(historical_p50_hours)

    # Top corridors one-hot (top 5 by volume)
    top_corridors = ["USD-EUR", "EUR-USD", "GBP-USD", "USD-GBP", "EUR-GBP"]
    for c in top_corridors:
        features.append(1.0 if corridor == c else 0.0)

    return np.array(features, dtype=np.float64)


# Feature names matching _encode_features output order
FEATURE_NAMES: List[str] = [
    "log_amount_usd",
    "is_class_a", "is_class_b", "is_class_c",
    "sending_bic_tier", "receiving_bic_tier",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "historical_p50_hours",
    "corridor_usd_eur", "corridor_eur_usd", "corridor_gbp_usd",
    "corridor_usd_gbp", "corridor_eur_gbp",
]


class SettlementTimePredictor:
    """C9 settlement time predictor using Cox Proportional Hazards.

    When ``lifelines`` is installed, uses a real CoxPHFitter. Otherwise,
    falls back to a heuristic model based on rejection class and corridor
    calibrated from BIS/SWIFT GPI benchmarks.

    Parameters
    ----------
    safety_margin:
        Multiply predicted settlement time by this factor for maturity.
    min_maturity_hours:
        Floor on dynamic maturity.
    """

    def __init__(
        self,
        safety_margin: float = SETTLEMENT_SAFETY_MARGIN,
        min_maturity_hours: float = MIN_MATURITY_HOURS,
    ) -> None:
        self._safety_margin = safety_margin
        self._min_maturity_hours = min_maturity_hours
        self._model: Any = None
        self._fitted = False
        self._model_type = "fallback"
        self._baseline_hazard: Optional[np.ndarray] = None

        # Heuristic calibration from BIS/SWIFT GPI (used as fallback)
        self._heuristic_medians: Dict[str, float] = {
            "CLASS_A": 4.0,    # Routing errors resolve fast
            "CLASS_B": 36.0,   # Systemic delays
            "CLASS_C": 120.0,  # Liquidity/investigation
        }

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def model_type(self) -> str:
        return self._model_type

    def fit(self, X: np.ndarray, durations: np.ndarray, events: np.ndarray) -> None:
        """Fit the Cox PH model on training data.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(N, 16)`` from ``_encode_features``.
        durations:
            Settlement times in hours, shape ``(N,)``.
        events:
            Event indicator (1 = settled, 0 = censored), shape ``(N,)``.
        """
        try:
            import pandas as pd
            from lifelines import CoxPHFitter

            df = pd.DataFrame(X, columns=FEATURE_NAMES)
            df["duration"] = durations
            df["event"] = events

            cph = CoxPHFitter(penalizer=0.01)
            cph.fit(df, duration_col="duration", event_col="event")
            self._model = cph
            self._fitted = True
            self._model_type = "cox_ph"
            logger.info(
                "CoxPHFitter trained: %d observations, concordance=%.4f",
                len(X), cph.concordance_index_,
            )
        except ImportError:
            logger.info("lifelines not installed — using heuristic fallback model")
            self._fit_heuristic(X, durations, events)
        except Exception as exc:
            logger.warning("CoxPH fitting failed (%s) — using heuristic fallback", exc)
            self._fit_heuristic(X, durations, events)

    def _fit_heuristic(
        self, X: np.ndarray, durations: np.ndarray, events: np.ndarray
    ) -> None:
        """Fit a simple class-based median model as fallback."""
        # Compute median settlement time by rejection class
        for class_idx, class_name in enumerate(["CLASS_A", "CLASS_B", "CLASS_C"]):
            col_idx = 1 + class_idx  # is_class_a, is_class_b, is_class_c
            mask = (X[:, col_idx] == 1.0) & (events == 1)
            if mask.any():
                median = float(np.median(durations[mask]))
                self._heuristic_medians[class_name] = median

        self._fitted = True
        self._model_type = "fallback"
        logger.info(
            "Heuristic model fitted: medians=%s",
            {k: f"{v:.1f}h" for k, v in self._heuristic_medians.items()},
        )

    def predict(
        self,
        corridor: str,
        rejection_class: str,
        amount_usd: float,
        timestamp: Optional[datetime] = None,
        sending_bic_tier: int = 3,
        receiving_bic_tier: int = 3,
        historical_p50_hours: float = 0.0,
    ) -> SettlementPrediction:
        """Predict settlement time and recommend dynamic maturity.

        Parameters
        ----------
        corridor:
            Currency corridor (e.g. "USD-EUR").
        rejection_class:
            Rejection class: "CLASS_A", "CLASS_B", or "CLASS_C".
        amount_usd:
            Payment amount in USD.
        timestamp:
            Payment timestamp (for time-of-day features).
        sending_bic_tier:
            Tier of the sending BIC (1/2/3).
        receiving_bic_tier:
            Tier of the receiving BIC (1/2/3).
        historical_p50_hours:
            Historical P50 settlement time for this corridor.

        Returns
        -------
        SettlementPrediction
        """
        t0 = time.perf_counter()

        static_hours = _STATIC_MATURITY_HOURS.get(
            rejection_class, MATURITY_CLASS_B_DAYS * 24.0
        )

        features = _encode_features(
            corridor=corridor,
            rejection_class=rejection_class,
            amount_usd=amount_usd,
            timestamp=timestamp,
            sending_bic_tier=sending_bic_tier,
            receiving_bic_tier=receiving_bic_tier,
            historical_p50_hours=historical_p50_hours,
        )

        if self._model_type == "cox_ph" and self._model is not None:
            predicted, lower, upper = self._predict_cox(features)
        else:
            predicted, lower, upper = self._predict_heuristic(rejection_class)

        # Apply safety margin for dynamic maturity
        dynamic_hours = max(
            predicted * self._safety_margin,
            self._min_maturity_hours,
        )

        # Cannot exceed static window
        if dynamic_hours > static_hours * MAX_MATURITY_OVERRIDE_FACTOR:
            dynamic_hours = static_hours
            using_dynamic = False
        else:
            using_dynamic = True

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return SettlementPrediction(
            predicted_hours=round(predicted, 2),
            confidence_lower_hours=round(lower, 2),
            confidence_upper_hours=round(upper, 2),
            dynamic_maturity_hours=round(dynamic_hours, 2),
            static_maturity_hours=static_hours,
            using_dynamic=using_dynamic,
            inference_latency_ms=round(latency_ms, 3),
            model_type=self._model_type,
        )

    def _predict_cox(self, features: np.ndarray) -> tuple:
        """Predict using fitted CoxPHFitter."""
        import pandas as pd

        df = pd.DataFrame([features], columns=FEATURE_NAMES)
        survival_func = self._model.predict_survival_function(df)

        # Median survival time (where S(t) = 0.5)
        times = survival_func.index.values
        probs = survival_func.iloc[:, 0].values

        # Find median
        median_idx = np.searchsorted(-probs, -0.5)
        if median_idx < len(times):
            predicted = float(times[median_idx])
        else:
            predicted = float(times[-1])

        # 80% prediction interval (10th and 90th percentile)
        lower_idx = np.searchsorted(-probs, -0.9)
        upper_idx = np.searchsorted(-probs, -0.1)
        lower = float(times[min(lower_idx, len(times) - 1)])
        upper = float(times[min(upper_idx, len(times) - 1)])

        return predicted, lower, upper

    def _predict_heuristic(self, rejection_class: str) -> tuple:
        """Predict using class-based median heuristic."""
        median = self._heuristic_medians.get(rejection_class, 36.0)
        # Approximate 80% CI as ±50% of median
        lower = median * 0.5
        upper = median * 1.5
        return median, lower, upper

    def predict_dynamic_maturity_days(
        self,
        corridor: str,
        rejection_class: str,
        amount_usd: float,
        timestamp: Optional[datetime] = None,
        sending_bic_tier: int = 3,
        receiving_bic_tier: int = 3,
        historical_p50_hours: float = 0.0,
    ) -> int:
        """Convenience: return dynamic maturity in whole days (ceiling).

        Used by C7 ExecutionAgent to override the static maturity window.
        """
        pred = self.predict(
            corridor=corridor,
            rejection_class=rejection_class,
            amount_usd=amount_usd,
            timestamp=timestamp,
            sending_bic_tier=sending_bic_tier,
            receiving_bic_tier=receiving_bic_tier,
            historical_p50_hours=historical_p50_hours,
        )
        return max(1, math.ceil(pred.dynamic_maturity_hours / 24.0))
