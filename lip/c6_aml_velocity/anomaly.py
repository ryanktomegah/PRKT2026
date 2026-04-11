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
    """Result of a single-transaction anomaly detection inference.

    Attributes:
        is_anomaly: ``True`` when the transaction is classified as anomalous.
            With Isolation Forest, this corresponds to a predict label of
            ``-1``; with z-score fallback, when ``max(|z|) > 3.0``.
        anomaly_score: Raw model output score.  For Isolation Forest this is
            the ``score_samples`` value (more negative = more anomalous);
            for z-score fallback it is ``max(|z|)`` across all features.
        features_used: List of feature names passed to the model, in order.
            Always equal to :data:`FEATURE_NAMES`.
    """

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
        """Transform a transaction dict into the 8-dimensional feature vector.

        Applies log1p to amount and sine/cosine cyclical encoding to hour
        and day-of-week to prevent ordinal leakage across midnight/week
        boundaries.

        Args:
            transaction: Dict with optional keys ``amount``,
                ``hour_of_day`` [0, 23], ``day_of_week`` [0, 6],
                ``velocity_ratio``, ``beneficiary_concentration``,
                ``amount_zscore``.  Missing keys default to safe neutral
                values.

        Returns:
            1-D float64 numpy array of shape ``(8,)`` matching
            :data:`FEATURE_NAMES` order.
        """
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
        """Train the anomaly detector on historical transaction data.

        Attempts to use ``sklearn.ensemble.IsolationForest``; falls back to
        computing per-feature mean and std for z-score detection when sklearn
        is unavailable.

        After fitting, :attr:`_fitted` is set to ``True`` and
        :meth:`predict` will return model-backed scores.

        Args:
            transactions: List of transaction dicts in the format expected by
                :meth:`_extract_features`.  Should contain several hundred
                or more samples for meaningful Isolation Forest calibration.
        """
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
        """Score a single transaction for anomalousness.

        Returns a safe ``is_anomaly=False`` result if called before
        :meth:`fit` (with a warning log); callers in the C6 pipeline must
        call :meth:`fit` before production use.

        Args:
            transaction: Transaction dict in the format expected by
                :meth:`_extract_features`.

        Returns:
            :class:`AnomalyResult` with the anomaly flag and raw score.
        """
        if not self._fitted:
            raise RuntimeError(
                "AnomalyDetector.predict() called before fit(). "
                "Call fit() with historical transactions before using the detector in production. "
                "Silent False would allow anomalous transactions to pass unflagged (B7-08)."
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
        """Score a batch of transactions for anomalousness.

        Delegates to :meth:`predict` for each transaction.  For large batches
        consider using the sklearn model's vectorised ``predict`` directly.

        Args:
            transactions: List of transaction dicts.

        Returns:
            List of :class:`AnomalyResult` objects in the same order as input.
        """
        return [self.predict(t) for t in transactions]
