"""
anomaly.py — Isolation Forest anomaly detection.
Falls back to z-score detection if sklearn is not available.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import logging
import math
from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "amount_log", "hour_sin", "hour_cos", "day_sin", "day_cos",
    "velocity_ratio", "beneficiary_concentration", "amount_zscore",
]


@dataclass
class AnomalyResult:
    is_anomaly: bool
    anomaly_score: float
    features_used: List[str]


class AnomalyDetector:
    """Isolation Forest anomaly detection with z-score fallback."""

    def __init__(self, contamination: float = 0.01):
        self.contamination = contamination
        self._model: Optional[Any] = None
        self._fitted = False
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

    def _extract_features(self, transaction: dict) -> np.ndarray:
        amount = float(transaction.get("amount", 0))
        hour = float(transaction.get("hour_of_day", 12))
        day = float(transaction.get("day_of_week", 3))
        velocity_ratio = float(transaction.get("velocity_ratio", 1.0))
        bene_conc = float(transaction.get("beneficiary_concentration", 0.5))
        amount_zscore = float(transaction.get("amount_zscore", 0.0))
        amount_log = math.log1p(amount)
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        day_sin = math.sin(2 * math.pi * day / 7)
        day_cos = math.cos(2 * math.pi * day / 7)
        return np.array([
            amount_log, hour_sin, hour_cos, day_sin, day_cos,
            velocity_ratio, bene_conc, amount_zscore,
        ], dtype=float)

    def fit(self, transactions: List[dict]) -> None:
        X = np.array([self._extract_features(t) for t in transactions])
        try:
            from sklearn.ensemble import IsolationForest
            self._model = IsolationForest(contamination=self.contamination, random_state=42)
            self._model.fit(X)
            logger.info("IsolationForest fitted on %d samples", len(transactions))
        except ImportError:
            logger.warning("sklearn not available; using z-score fallback")
            self._mean = X.mean(axis=0)
            self._std = X.std(axis=0) + 1e-8
        self._fitted = True

    def predict(self, transaction: dict) -> AnomalyResult:
        if not self._fitted:
            logger.warning(
                "AnomalyDetector.predict() called before fit() — returning is_anomaly=False. "
                "Call fit() with historical transactions before using the detector in production."
            )
        features = self._extract_features(transaction)
        if self._model is not None:
            score = float(self._model.score_samples(features.reshape(1, -1))[0])
            # IsolationForest.predict() returns -1 for anomalies, 1 for inliers
            label = int(self._model.predict(features.reshape(1, -1))[0])
            is_anomaly = label == -1
            return AnomalyResult(is_anomaly=is_anomaly, anomaly_score=score, features_used=FEATURE_NAMES)
        if self._mean is not None:
            z = np.abs((features - self._mean) / self._std)
            score = float(z.max())
            is_anomaly = score > 3.0
            return AnomalyResult(is_anomaly=is_anomaly, anomaly_score=score, features_used=FEATURE_NAMES)
        return AnomalyResult(is_anomaly=False, anomaly_score=0.0, features_used=FEATURE_NAMES)

    def predict_batch(self, transactions: List[dict]) -> List[AnomalyResult]:
        return [self.predict(t) for t in transactions]
