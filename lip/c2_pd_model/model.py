"""
model.py — 5x LightGBM ensemble with soft voting
C2 Spec Section 7: Three-tier framework internalized as feature

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

N_ESTIMATORS = 5
_DEFAULT_SEEDS = [42, 43, 44, 45, 46]


# ---------------------------------------------------------------------------
# Backend selection helpers
# ---------------------------------------------------------------------------


def _make_lgbm_model(random_seed: int, **params) -> Any:
    """Return a LightGBM classifier; falls back to sklearn GBC if unavailable."""
    try:
        import lightgbm as lgb  # noqa: PLC0415

        defaults = dict(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective="binary",
            metric="auc",
            random_state=random_seed,
            verbose=-1,
            n_jobs=-1,
        )
        defaults.update(params)
        return lgb.LGBMClassifier(**defaults)  # type: ignore[arg-type]
    except ImportError:
        logger.info(
            "lightgbm not installed; falling back to sklearn GradientBoostingClassifier."
        )
        return _make_sklearn_model(random_seed, **params)


def _make_sklearn_model(random_seed: int, **params) -> Any:
    """Return a sklearn GradientBoostingClassifier with sensible defaults."""
    from sklearn.ensemble import GradientBoostingClassifier  # noqa: PLC0415

    defaults = dict(
        n_estimators=params.get("n_estimators", 200),
        learning_rate=params.get("learning_rate", 0.05),
        max_depth=params.get("max_depth", 5),
        subsample=params.get("subsample", 0.8),
        random_state=random_seed,
    )
    return GradientBoostingClassifier(**defaults)


# ---------------------------------------------------------------------------
# LightGBMSurrogate
# ---------------------------------------------------------------------------


class LightGBMSurrogate:
    """Pure-numpy surrogate that mimics the LightGBM classifier API.

    Used as a last-resort fallback when neither *lightgbm* nor *scikit-learn*
    is available.  Implements a minimal gradient-boosted approximation via a
    simple logistic model with additive residual fitting.

    In practice, the pipeline always prefers the real LightGBM (or sklearn GBC)
    backend and this class is only instantiated in constrained test environments.
    """

    def __init__(self, n_estimators: int = 50, learning_rate: float = 0.1,
                 random_state: int = 42) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.random_state = random_state
        self._trees: list = []
        self._base_score: float = 0.5
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LightGBMSurrogate":
        """Fit a simplified gradient-boosted logistic model on (X, y)."""
        rng = np.random.default_rng(self.random_state)
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        p = np.full(len(y), np.mean(y))
        self._base_score = float(np.mean(y))
        self._trees = []

        for _ in range(self.n_estimators):
            # Gradient of log-loss: r = y - p
            residuals = y - p
            # Fit a depth-1 stump: split on the feature with highest residual correlation
            n_features = X.shape[1]
            sample_idx = rng.choice(len(y), size=min(256, len(y)), replace=False)
            Xs, rs = X[sample_idx], residuals[sample_idx]

            best_feat, best_thresh, best_gain = 0, 0.0, -np.inf
            for f in range(n_features):
                col = Xs[:, f]
                thresh = float(np.median(col))
                left = rs[col <= thresh]
                right = rs[col > thresh]
                gain = (
                    (np.sum(left) ** 2 / (len(left) + 1e-9))
                    + (np.sum(right) ** 2 / (len(right) + 1e-9))
                )
                if gain > best_gain:
                    best_gain, best_feat, best_thresh = gain, f, thresh

            left_mask = X[:, best_feat] <= best_thresh
            left_val = np.mean(residuals[left_mask]) if left_mask.any() else 0.0
            right_val = np.mean(residuals[~left_mask]) if (~left_mask).any() else 0.0
            self._trees.append((best_feat, best_thresh, left_val, right_val))

            # Update probabilities
            preds = np.where(left_mask, left_val, right_val)
            log_odds = np.log(p / (1 - p + 1e-9) + 1e-9) + self.learning_rate * preds
            p = 1.0 / (1.0 + np.exp(-log_odds))
            p = np.clip(p, 1e-6, 1 - 1e-6)

        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return class probabilities as shape ``(N, 2)``."""
        if not self._fitted:
            raise RuntimeError("Model not fitted yet.")
        X = np.asarray(X, dtype=np.float64)
        log_odds = np.full(len(X), np.log(self._base_score / (1 - self._base_score + 1e-9)))
        for feat, thresh, left_val, right_val in self._trees:
            left_mask = X[:, feat] <= thresh
            update = np.where(left_mask, left_val, right_val)
            log_odds += self.learning_rate * update
        p = 1.0 / (1.0 + np.exp(-log_odds))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.column_stack([1 - p, p])


# ---------------------------------------------------------------------------
# PDModel
# ---------------------------------------------------------------------------


class PDModel:
    """Five-model LightGBM ensemble for Probability of Default estimation.

    C2 Spec Section 7 — soft-voting ensemble of models trained with different
    random seeds to reduce variance.  The three-tier framework is *not* a
    routing mechanism; all tiers are handled by the same model, with tier
    identity encoded as features in the input vector.

    Parameters
    ----------
    n_models:
        Number of ensemble members (default 5).
    random_seeds:
        List of integer seeds, one per ensemble member.  Length must match
        *n_models*.
    """

    def __init__(
        self,
        n_models: int = N_ESTIMATORS,
        random_seeds: Optional[List[int]] = None,
    ) -> None:
        if random_seeds is None:
            random_seeds = _DEFAULT_SEEDS[:n_models]
        if len(random_seeds) != n_models:
            raise ValueError(
                f"random_seeds length {len(random_seeds)} != n_models {n_models}"
            )
        self.n_models = n_models
        self.random_seeds = random_seeds
        self._models: List[Any] = []
        self._fitted = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_params: Optional[Dict] = None,
    ) -> None:
        """Train all ensemble members on (X, y).

        Parameters
        ----------
        X:
            Feature matrix of shape ``(N, 75)``.
        y:
            Binary labels of shape ``(N,)`` where 1 = default event.
        model_params:
            Optional dict of hyperparameters forwarded to each model constructor.
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if model_params is None:
            model_params = {}

        self._models = []
        for seed in self.random_seeds:
            try:
                model = _make_lgbm_model(seed, **model_params)
            except Exception:
                logger.warning(
                    "Both LightGBM and sklearn unavailable — using LightGBMSurrogate.",
                    exc_info=False,
                )
                model = LightGBMSurrogate(random_state=seed)

            model.fit(X, y)
            self._models.append(model)
            logger.debug("Trained ensemble member %d / %d", len(self._models), self.n_models)

        self._fitted = True
        logger.info("PDModel training complete: %d models.", self.n_models)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Soft-voting ensemble PD prediction.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(N, 75)`` or ``(75,)`` for a single obs.

        Returns
        -------
        np.ndarray
            PD scores in ``[0, 1]``, shape ``(N,)``.
        """
        self._require_fitted()
        X = np.asarray(X, dtype=np.float64)
        single = X.ndim == 1
        if single:
            X = X[np.newaxis, :]

        proba_sum = np.zeros(len(X), dtype=np.float64)
        for model in self._models:
            p = model.predict_proba(X)
            # predict_proba returns (N, 2); column 1 is P(default=1)
            proba_sum += p[:, 1]

        pd_scores = proba_sum / self.n_models
        pd_scores = np.clip(pd_scores, 0.0, 1.0)
        return pd_scores[0] if single else pd_scores

    def predict_with_shap(
        self,
        X: np.ndarray,
        feature_names: List[str],
    ) -> Tuple[np.ndarray, List[dict]]:
        """Return PD scores alongside per-feature SHAP values.

        Attempts to use ``shap.TreeExplainer`` on the *first* ensemble member.
        Falls back to a zero-SHAP response if shap is not installed or the
        explainer raises an error.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(N, 75)`` or ``(75,)`` for a single obs.
        feature_names:
            Ordered list of feature names matching columns of *X* (length 75).

        Returns
        -------
        Tuple[np.ndarray, List[dict]]
            * ``pd_scores`` — shape ``(N,)``
            * ``shap_values_list`` — list of N dicts mapping feature name → SHAP value
        """
        self._require_fitted()
        X = np.asarray(X, dtype=np.float64)
        single = X.ndim == 1
        if single:
            X = X[np.newaxis, :]

        pd_scores = self.predict_proba(X)

        shap_matrix: Optional[np.ndarray] = None
        try:
            import shap as _shap  # noqa: PLC0415

            explainer = _shap.TreeExplainer(self._models[0])
            raw = explainer.shap_values(X)
            # Some versions return list [neg_class, pos_class]; take positive class
            if isinstance(raw, list):
                raw = raw[1]
            shap_matrix = np.asarray(raw, dtype=np.float64)
        except Exception as exc:
            logger.debug("SHAP unavailable (%s); returning zero SHAP values.", exc)
            shap_matrix = np.zeros_like(X)

        shap_values_list = [
            {name: float(val) for name, val in zip(feature_names, row)}
            for row in shap_matrix
        ]

        if single:
            return float(pd_scores[0]), shap_values_list  # type: ignore[return-value]
        return pd_scores, shap_values_list

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialise the full ensemble to a pickle file at *path*.

        Parameters
        ----------
        path:
            Destination file path.  Directories must exist.
        """
        self._require_fitted()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        payload = {
            "n_models": self.n_models,
            "random_seeds": self.random_seeds,
            "models": self._models,
        }
        with open(path, "wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("PDModel saved to %s", path)

    def load(self, path: str) -> None:
        """Deserialise an ensemble from a pickle file at *path*.

        Parameters
        ----------
        path:
            Source file path produced by :meth:`save`.
        """
        with open(path, "rb") as fh:
            payload = pickle.load(fh)  # noqa: S301 — trusted model artifacts only
        self.n_models = payload["n_models"]
        self.random_seeds = payload["random_seeds"]
        self._models = payload["models"]
        self._fitted = True
        logger.info("PDModel loaded from %s (%d models)", path, self.n_models)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError(
                "PDModel is not fitted. Call fit() or load() before inference."
            )
