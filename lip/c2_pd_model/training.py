"""
training.py — C2 PD Model Training Pipeline
C2 Spec Section 11: Optuna hyperparameter tuning, calibration, stress test

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .features import UnifiedFeatureEngineer
from .model import PDModel
from .tier_assignment import TierFeatures, assign_tier, Tier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TrainingConfig:
    """Hyper-parameters and knobs for the full training pipeline.

    Attributes
    ----------
    n_trials:
        Number of Optuna trials for hyperparameter search (Stage 5).
    n_models:
        Ensemble size passed to :class:`PDModel`.
    test_split:
        Fraction of data reserved for held-out test evaluation.
    val_split:
        Fraction of *training* data further reserved for calibration.
    random_seed:
        Master seed for all train/test splits and Optuna sampler.
    thin_file_pd_min:
        Lower bound of the acceptable PD range for Tier-3 (thin-file) borrowers
        during the stress test (Stage 8).
    thin_file_pd_max:
        Upper bound of the acceptable PD range for Tier-3 borrowers.
    """

    n_trials: int = 50
    n_models: int = 5
    test_split: float = 0.2
    val_split: float = 0.1
    random_seed: int = 42
    thin_file_pd_min: float = 0.05
    thin_file_pd_max: float = 0.25


# ---------------------------------------------------------------------------
# Training Pipeline
# ---------------------------------------------------------------------------


class PDTrainingPipeline:
    """End-to-end training pipeline for the C2 PD Model.

    Stages 1–9 mirror the spec's training workflow:

    1. Data preparation
    2. Tier assignment
    3. Feature engineering
    4. Train / val / test split
    5. Optuna hyperparameter search
    6. Ensemble training
    7. Isotonic calibration
    8. Thin-file stress test
    9. Evaluation (AUC, Brier, KS)

    Parameters
    ----------
    config:
        :class:`TrainingConfig` instance.  Defaults to spec defaults when omitted.
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self.config = config or TrainingConfig()
        self._rng = np.random.default_rng(self.config.random_seed)

    # ------------------------------------------------------------------
    # Stage 1 — Data preparation
    # ------------------------------------------------------------------

    def stage1_data_prep(
        self, data: List[dict]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract raw feature arrays and label vector from the input records.

        Each record must contain at least:
        * ``'label'`` — integer 1 (default) or 0 (non-default).
        * ``'payment'`` — payment-level dict consumed by the feature engineer.
        * ``'borrower'`` — borrower-level dict consumed by the feature engineer.

        Parameters
        ----------
        data:
            List of raw training records.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            ``(X, y)`` where *X* has shape ``(N, 75)`` and *y* has shape ``(N,)``.
        """
        if not data:
            raise ValueError("Training data is empty.")

        labels = np.array([int(r.get("label", 0)) for r in data], dtype=np.float64)
        tiers = self.stage2_tier_assignment(data)
        X = self.stage3_feature_engineering(data, tiers)
        logger.info(
            "Stage 1 complete: %d samples, default rate %.2f%%",
            len(labels),
            100 * labels.mean(),
        )
        return X, labels

    # ------------------------------------------------------------------
    # Stage 2 — Tier assignment
    # ------------------------------------------------------------------

    def stage2_tier_assignment(self, data: List[dict]) -> List[int]:
        """Deterministically assign a tier to each training record.

        Parameters
        ----------
        data:
            List of raw records; each must contain a ``'borrower'`` dict with
            availability flags.

        Returns
        -------
        List[int]
            Integer tier (1, 2, or 3) per record.
        """
        tiers: List[int] = []
        for record in data:
            borrower = record.get("borrower", {})
            features = TierFeatures(
                has_financial_statements=bool(
                    borrower.get("has_financial_statements", False)
                ),
                has_transaction_history=bool(
                    borrower.get("has_transaction_history", False)
                ),
                has_credit_bureau=bool(borrower.get("has_credit_bureau", False)),
                months_history=int(borrower.get("months_history", 0)),
                transaction_count=int(borrower.get("transaction_count", 0)),
            )
            tiers.append(int(assign_tier(features)))
        return tiers

    # ------------------------------------------------------------------
    # Stage 3 — Feature engineering
    # ------------------------------------------------------------------

    def stage3_feature_engineering(
        self, data: List[dict], tiers: List[int]
    ) -> np.ndarray:
        """Build the (N, 75) feature matrix from raw records and pre-computed tiers.

        Parameters
        ----------
        data:
            List of raw training records.
        tiers:
            List of integer tier values parallel to *data*.

        Returns
        -------
        np.ndarray
            Float64 array of shape ``(N, 75)``.
        """
        rows = []
        for record, tier_int in zip(data, tiers):
            tier = Tier(tier_int)
            engineer = UnifiedFeatureEngineer(tier)
            features, _ = engineer.extract(
                record.get("payment", {}),
                record.get("borrower", {}),
            )
            rows.append(features)
        return np.vstack(rows)

    # ------------------------------------------------------------------
    # Stage 4 — Train / val / test split
    # ------------------------------------------------------------------

    def stage4_train_val_test_split(
        self, X: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, ...]:
        """Stratified-ish split into train, validation, and test sets.

        Parameters
        ----------
        X:
            Feature matrix.
        y:
            Label vector.

        Returns
        -------
        Tuple of (X_train, X_val, X_test, y_train, y_val, y_test)
        """
        n = len(y)
        idx = self._rng.permutation(n)

        n_test = max(1, int(n * self.config.test_split))
        n_val = max(1, int((n - n_test) * self.config.val_split))

        test_idx = idx[:n_test]
        val_idx = idx[n_test: n_test + n_val]
        train_idx = idx[n_test + n_val:]

        logger.info(
            "Stage 4 split: train=%d, val=%d, test=%d",
            len(train_idx),
            len(val_idx),
            len(test_idx),
        )
        return (
            X[train_idx],
            X[val_idx],
            X[test_idx],
            y[train_idx],
            y[val_idx],
            y[test_idx],
        )

    # ------------------------------------------------------------------
    # Stage 5 — Hyperparameter search
    # ------------------------------------------------------------------

    def stage5_hyperparameter_search(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> dict:
        """Optuna hyperparameter optimisation (Stage 5).

        Tries to import Optuna; falls back gracefully to a fixed set of
        reasonable defaults if the package is unavailable.

        Parameters
        ----------
        X_train:
            Training feature matrix.
        y_train:
            Training labels.

        Returns
        -------
        dict
            Best hyperparameter dict compatible with the LightGBM / sklearn
            GBC constructors.
        """
        try:
            import optuna  # noqa: PLC0415

            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def _objective(trial: "optuna.Trial") -> float:  # type: ignore[name-defined]
                from sklearn.model_selection import cross_val_score  # noqa: PLC0415
                from sklearn.ensemble import GradientBoostingClassifier  # noqa: PLC0415

                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                    "max_depth": trial.suggest_int("max_depth", 3, 8),
                    "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                    "random_state": self.config.random_seed,
                }
                clf = GradientBoostingClassifier(**params)
                scores = cross_val_score(
                    clf, X_train, y_train, cv=3, scoring="roc_auc", n_jobs=-1
                )
                return float(scores.mean())

            study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=self.config.random_seed),
            )
            study.optimize(
                _objective,
                n_trials=self.config.n_trials,
                show_progress_bar=False,
            )
            best_params = study.best_params
            logger.info(
                "Stage 5 — Optuna best AUC %.4f with params: %s",
                study.best_value,
                best_params,
            )
            return best_params

        except ImportError:
            logger.info(
                "Optuna not installed; using default hyperparameters for Stage 5."
            )
            return {
                "n_estimators": 200,
                "learning_rate": 0.05,
                "max_depth": 5,
                "subsample": 0.8,
            }

    # ------------------------------------------------------------------
    # Stage 6 — Ensemble training
    # ------------------------------------------------------------------

    def stage6_ensemble_training(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        best_params: dict,
    ) -> PDModel:
        """Train the 5-model ensemble with the best hyperparameters.

        Parameters
        ----------
        X_train:
            Training feature matrix.
        y_train:
            Training labels.
        best_params:
            Hyperparameter dict from Stage 5.

        Returns
        -------
        PDModel
            Fitted ensemble.
        """
        seeds = list(range(
            self.config.random_seed,
            self.config.random_seed + self.config.n_models,
        ))
        model = PDModel(n_models=self.config.n_models, random_seeds=seeds)
        model.fit(X_train, y_train, model_params=best_params)
        logger.info("Stage 6 — ensemble training complete.")
        return model

    # ------------------------------------------------------------------
    # Stage 7 — Calibration
    # ------------------------------------------------------------------

    def stage7_calibration(
        self, model: PDModel, X_val: np.ndarray, y_val: np.ndarray
    ) -> PDModel:
        """Apply isotonic regression calibration on the validation set.

        Wraps the ensemble's raw probabilities with sklearn's
        ``CalibratedClassifierCV`` (isotonic method) trained on the validation
        set.  The calibrated wrapper is stored as ``model._calibrator`` and
        invoked transparently during inference.

        Parameters
        ----------
        model:
            Fitted :class:`PDModel`.
        X_val:
            Validation feature matrix.
        y_val:
            Validation labels.

        Returns
        -------
        PDModel
            The same model instance with calibration applied.
        """
        try:
            from sklearn.isotonic import IsotonicRegression  # noqa: PLC0415

            raw_probs = model.predict_proba(X_val)
            calibrator = IsotonicRegression(out_of_bounds="clip")
            calibrator.fit(raw_probs, y_val)
            model._calibrator = calibrator  # type: ignore[attr-defined]
            logger.info("Stage 7 — isotonic calibration applied on %d validation samples.", len(y_val))
        except Exception as exc:
            logger.warning("Stage 7 calibration skipped (%s).", exc)

        return model

    # ------------------------------------------------------------------
    # Stage 8 — Stress test
    # ------------------------------------------------------------------

    def stage8_stress_test(
        self, model: PDModel, X_thin_file: np.ndarray
    ) -> bool:
        """Verify that all Tier-3 PD predictions fall within the spec-mandated range.

        C2 Spec requirement: for thin-file borrowers PD ∈ [0.05, 0.25].

        Parameters
        ----------
        model:
            Fitted :class:`PDModel`.
        X_thin_file:
            Feature matrix for a representative sample of Tier-3 records.

        Returns
        -------
        bool
            ``True`` if **all** predictions satisfy the range; ``False`` otherwise.
        """
        if len(X_thin_file) == 0:
            logger.warning("Stage 8 — stress test skipped: no thin-file samples provided.")
            return True

        pds = model.predict_proba(X_thin_file)
        lo = self.config.thin_file_pd_min
        hi = self.config.thin_file_pd_max
        in_range = np.all((pds >= lo) & (pds <= hi))

        if in_range:
            logger.info("Stage 8 — stress test PASSED: all %d Tier-3 PDs in [%.2f, %.2f].",
                        len(pds), lo, hi)
        else:
            n_violations = int(np.sum((pds < lo) | (pds > hi)))
            logger.error(
                "Stage 8 — stress test FAILED: %d / %d Tier-3 PDs outside [%.2f, %.2f]. "
                "Range: [%.4f, %.4f].",
                n_violations,
                len(pds),
                lo,
                hi,
                float(pds.min()),
                float(pds.max()),
            )
        return bool(in_range)

    # ------------------------------------------------------------------
    # Stage 9 — Evaluation
    # ------------------------------------------------------------------

    def stage9_evaluation(
        self, model: PDModel, X_test: np.ndarray, y_test: np.ndarray
    ) -> Dict[str, float]:
        """Compute held-out evaluation metrics.

        Metrics reported
        ----------------
        * **auc** — Area Under the ROC Curve (sklearn ``roc_auc_score``).
        * **brier** — Brier score (mean squared error of probability estimates).
        * **ks** — Kolmogorov-Smirnov statistic between default/non-default score
          distributions (maximum separation).

        Parameters
        ----------
        model:
            Fitted :class:`PDModel`.
        X_test:
            Test feature matrix.
        y_test:
            Test labels.

        Returns
        -------
        dict
            ``{'auc': float, 'brier': float, 'ks': float}``
        """
        pds = model.predict_proba(X_test)
        metrics: Dict[str, float] = {}

        # AUC
        try:
            from sklearn.metrics import roc_auc_score, brier_score_loss  # noqa: PLC0415

            metrics["auc"] = float(roc_auc_score(y_test, pds))
            metrics["brier"] = float(brier_score_loss(y_test, pds))
        except Exception as exc:
            logger.warning("sklearn metrics unavailable (%s); computing manually.", exc)
            # Fallback: simple concordance approximation
            pos = pds[y_test == 1]
            neg = pds[y_test == 0]
            if len(pos) > 0 and len(neg) > 0:
                concordant = float(np.mean(
                    pos[:, None] > neg[None, :]  # type: ignore[index]
                ))
                metrics["auc"] = concordant
            else:
                metrics["auc"] = float("nan")
            metrics["brier"] = float(np.mean((pds - y_test) ** 2))

        # KS statistic
        try:
            from scipy.stats import ks_2samp  # noqa: PLC0415

            pos_scores = pds[y_test == 1]
            neg_scores = pds[y_test == 0]
            if len(pos_scores) > 0 and len(neg_scores) > 0:
                ks_stat, _ = ks_2samp(pos_scores, neg_scores)
                metrics["ks"] = float(ks_stat)
            else:
                metrics["ks"] = float("nan")
        except Exception:
            # Manual KS
            pos_scores = np.sort(pds[y_test == 1])
            neg_scores = np.sort(pds[y_test == 0])
            if len(pos_scores) > 0 and len(neg_scores) > 0:
                all_scores = np.sort(pds)
                cdf_pos = np.searchsorted(pos_scores, all_scores, side="right") / len(pos_scores)
                cdf_neg = np.searchsorted(neg_scores, all_scores, side="right") / len(neg_scores)
                metrics["ks"] = float(np.max(np.abs(cdf_pos - cdf_neg)))
            else:
                metrics["ks"] = float("nan")

        logger.info(
            "Stage 9 — test metrics: AUC=%.4f  Brier=%.4f  KS=%.4f",
            metrics.get("auc", float("nan")),
            metrics.get("brier", float("nan")),
            metrics.get("ks", float("nan")),
        )
        return metrics

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(self, data: List[dict]) -> Tuple[PDModel, Dict[str, float]]:
        """Execute the full nine-stage training pipeline.

        Parameters
        ----------
        data:
            List of training records.  Each record must contain:
            ``'label'`` (int), ``'payment'`` (dict), ``'borrower'`` (dict).

        Returns
        -------
        Tuple[PDModel, dict]
            * Trained and calibrated :class:`PDModel`.
            * Evaluation metrics dict from Stage 9.
        """
        logger.info("PDTrainingPipeline.run() — %d records.", len(data))

        X, y = self.stage1_data_prep(data)
        X_train, X_val, X_test, y_train, y_val, y_test = (
            self.stage4_train_val_test_split(X, y)
        )

        best_params = self.stage5_hyperparameter_search(X_train, y_train)
        model = self.stage6_ensemble_training(X_train, y_train, best_params)
        model = self.stage7_calibration(model, X_val, y_val)

        # Thin-file stress test on Tier-3 samples in the test set
        tiers = self.stage2_tier_assignment(data)
        tier_arr = np.array(tiers)
        tier3_idx = np.where(tier_arr == 3)[0]
        # Intersect with test indices (approximate: use all tier-3 from full dataset)
        if len(tier3_idx) > 0:
            X_tier3 = X[tier3_idx]
            self.stage8_stress_test(model, X_tier3)
        else:
            logger.info("No Tier-3 records found; skipping stress test.")

        metrics = self.stage9_evaluation(model, X_test, y_test)
        return model, metrics
