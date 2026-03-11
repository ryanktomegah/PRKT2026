"""
test_c1_lgbm_ensemble.py — Tests for LightGBM ensemble integration in C1.

Validates that:
  1. TrainingPipeline.run() attaches lgbm_model to ClassifierModel.
  2. predict_proba uses the 50/50 ensemble when lgbm_model is present.
  3. LightGBM alone achieves AUC > 0.800 on separable tabular data.
  4. lgbm.pkl is saved/loaded correctly during model persistence.
  5. The ensemble combines neural + LightGBM with equal (0.5/0.5) weights.

C1 Spec Section 7 — GraphSAGE[384] + TabTransformer[88] + LightGBM ensemble.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import lightgbm as lgb
import numpy as np
from sklearn.metrics import roc_auc_score

from lip.c1_failure_classifier.graphsage import GRAPHSAGE_INPUT_DIM
from lip.c1_failure_classifier.model import create_default_model
from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset
from lip.c1_failure_classifier.tabtransformer import TABTRANSFORMER_INPUT_DIM
from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline

# ---------------------------------------------------------------------------
# Dimension aliases (canonical values live in the production modules)
# ---------------------------------------------------------------------------

_NODE_FEAT_DIM = GRAPHSAGE_INPUT_DIM      # 8
_TAB_FEAT_DIM = TABTRANSFORMER_INPUT_DIM  # 88
_N_NEIGHBORS: list[np.ndarray] = []      # empty neighbor lists for inference


# ---------------------------------------------------------------------------
# Shared LightGBM fixture factory
# ---------------------------------------------------------------------------

def _make_lgbm_classifier(
    n_samples: int = 20,
    n_estimators: int = 5,
    random_seed: int = 1,
) -> lgb.LGBMClassifier:
    """Fit a minimal LightGBM with guaranteed both-class labels present."""
    rng = np.random.default_rng(seed=random_seed)
    X = rng.standard_normal((n_samples, _TAB_FEAT_DIM))
    y = rng.integers(0, 2, size=n_samples)
    y[0], y[1] = 0, 1  # ensure both classes present regardless of random draw
    clf = lgb.LGBMClassifier(n_estimators=n_estimators, verbose=-1, random_state=random_seed)
    clf.fit(X, y)
    return clf


# ---------------------------------------------------------------------------
# Test 1: lgbm_model is attached after TrainingPipeline.run()
# ---------------------------------------------------------------------------


class TestLGBMModelAttachedAfterRun:
    """TrainingPipeline.run() must attach a fitted LGBMClassifier to the model."""

    def test_lgbm_model_attached_after_run(self):
        data = generate_synthetic_dataset(n_samples=200)
        cfg = TrainingConfig(n_epochs=2, batch_size=64, random_seed=0)
        pipeline = TrainingPipeline(config=cfg)

        model, _threshold, _emb = pipeline.run(data)

        assert model.lgbm_model is not None, "lgbm_model must be attached after run()"
        assert isinstance(model.lgbm_model, lgb.LGBMClassifier)


# ---------------------------------------------------------------------------
# Test 2: predict_proba uses the 50/50 ensemble when lgbm_model is present
# ---------------------------------------------------------------------------


class TestPredictProbaUsesEnsemble:
    """When lgbm_model is attached, predict_proba blends neural + LightGBM."""

    def _make_minimal_lgbm(self) -> lgb.LGBMClassifier:
        return _make_lgbm_classifier(n_samples=20, n_estimators=5, random_seed=1)

    def test_predict_proba_in_unit_interval(self):
        model = create_default_model()
        model.lgbm_model = self._make_minimal_lgbm()

        rng = np.random.default_rng(seed=2)
        node_feat = rng.standard_normal(_NODE_FEAT_DIM)
        tab_feat = rng.standard_normal(_TAB_FEAT_DIM)

        prob = model.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_ensemble_differs_from_neural_only(self):
        """With lgbm attached, the output should differ from neural-only output."""
        model = create_default_model()

        rng = np.random.default_rng(seed=3)
        node_feat = rng.standard_normal(_NODE_FEAT_DIM)
        tab_feat = rng.standard_normal(_TAB_FEAT_DIM)

        # Neural-only prediction
        neural_only = model.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        # Attach lgbm and get ensemble prediction
        model.lgbm_model = self._make_minimal_lgbm()
        ensemble = model.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        # They differ because LightGBM contributes a distinct signal
        assert neural_only != ensemble, (
            "Ensemble result must differ from neural-only result when lgbm_model is attached"
        )


# ---------------------------------------------------------------------------
# Test 3: AUC benchmark on separable data
# ---------------------------------------------------------------------------


class TestAUCBenchmarkSeparableData:
    """LightGBM alone should achieve AUC > 0.800 on clearly separable 88-dim data.

    Marked fast — uses stage5b_lightgbm_pretrain directly, not the full run().
    """

    def test_auc_above_threshold_on_separable_data(self):
        rng = np.random.default_rng(seed=42)
        n_per_class = 150

        # Separable clusters: positives centred at +1.5, negatives at -1.5
        X_pos = rng.standard_normal((n_per_class, _TAB_FEAT_DIM)) + 1.5
        X_neg = rng.standard_normal((n_per_class, _TAB_FEAT_DIM)) - 1.5
        X = np.vstack([X_pos, X_neg])
        y = np.concatenate([np.ones(n_per_class), np.zeros(n_per_class)])

        # 80/20 train/test split
        idx = rng.permutation(len(y))
        n_train = int(0.8 * len(y))
        train_idx, test_idx = idx[:n_train], idx[n_train:]
        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[test_idx], y[test_idx]

        pipeline = TrainingPipeline()
        lgbm_model = pipeline.stage5b_lightgbm_pretrain(X_train, y_train)

        y_scores = lgbm_model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_scores)

        assert auc > 0.800, f"Expected AUC > 0.800 on separable data, got {auc:.4f}"


# ---------------------------------------------------------------------------
# Test 4: lgbm save/load roundtrip
# ---------------------------------------------------------------------------


class TestLGBMSaveLoadRoundtrip:
    """lgbm.pkl must be saved and loaded correctly, preserving predict_proba output."""

    def _fit_minimal_lgbm(self) -> lgb.LGBMClassifier:
        return _make_lgbm_classifier(n_samples=30, n_estimators=10, random_seed=10)

    def test_lgbm_pkl_created_on_save(self, tmp_path):
        model = create_default_model()
        model.lgbm_model = self._fit_minimal_lgbm()

        model.save(str(tmp_path))

        lgbm_path = tmp_path / "lgbm.pkl"
        assert lgbm_path.exists(), "lgbm.pkl must be written by model.save()"

    def test_lgbm_loaded_after_roundtrip(self, tmp_path):
        model = create_default_model()
        model.lgbm_model = self._fit_minimal_lgbm()

        model.save(str(tmp_path))

        model2 = create_default_model()
        model2.load(str(tmp_path))

        assert model2.lgbm_model is not None, "lgbm_model must be restored after load()"

    def test_lgbm_predict_proba_matches_after_roundtrip(self, tmp_path):
        model = create_default_model()
        model.lgbm_model = self._fit_minimal_lgbm()

        rng = np.random.default_rng(seed=11)
        node_feat = rng.standard_normal(_NODE_FEAT_DIM)
        tab_feat = rng.standard_normal(_TAB_FEAT_DIM)

        prob_before = model.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        model.save(str(tmp_path))

        model2 = create_default_model()
        model2.load(str(tmp_path))

        prob_after = model2.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        assert abs(prob_before - prob_after) < 1e-9, (
            f"predict_proba must match after save/load: before={prob_before}, after={prob_after}"
        )


# ---------------------------------------------------------------------------
# Test 5: Ensemble weights are exactly 50/50
# ---------------------------------------------------------------------------


class TestEnsembleWeightsAreEqual:
    """The C1 ensemble must combine neural + LightGBM with equal 0.5 / 0.5 weights.

    C1 Spec Section 7: return 0.5 * neural_prob + 0.5 * lgbm_prob
    """

    def test_ensemble_is_fifty_fifty(self):
        model = create_default_model()

        # Mock LightGBM to always return probability 0.6 for class 1
        mock_lgbm = MagicMock()
        mock_lgbm.predict_proba.return_value = np.array([[0.4, 0.6]])
        model.lgbm_model = mock_lgbm

        rng = np.random.default_rng(seed=99)
        node_feat = rng.standard_normal(_NODE_FEAT_DIM)
        tab_feat = rng.standard_normal(_TAB_FEAT_DIM)

        # Force the neural path to return exactly 0.4 by patching mlp.forward
        with patch.object(model.mlp, "forward", return_value=0.4):
            result = model.predict_proba(node_feat, _N_NEIGHBORS, _N_NEIGHBORS, tab_feat)

        expected = 0.5 * 0.4 + 0.5 * 0.6  # = 0.5
        assert abs(result - expected) < 1e-9, (
            f"Expected 50/50 ensemble: 0.5*0.4 + 0.5*0.6 = {expected}, got {result}"
        )
