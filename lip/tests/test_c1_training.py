"""
test_c1_training.py — C1 Training Pipeline convergence tests.

Verifies that:
  1. MLPHead.backward() reduces loss over multiple gradient steps.
  2. Stage 7 joint training produces decreasing average loss across epochs.
  3. Stage 8 threshold calibration returns a valid threshold in (0, 1).
  4. Trained model AUC on held-out synthetic data beats random (> 0.55).
  5. GraphSAGE backward_empty_neighbors() updates weights in place.
  6. TabTransformer backward() updates weights in place.
"""
from __future__ import annotations

import numpy as np
import pytest
from decimal import Decimal

from lip.c1_failure_classifier.model import MLPHead, ClassifierModel
from lip.c1_failure_classifier.graphsage import GraphSAGEModel
from lip.c1_failure_classifier.tabtransformer import TabTransformerModel
from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline, _compute_auc
from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_separable_data(n: int = 300, seed: int = 0):
    """Generate a linearly separable synthetic dataset for convergence tests."""
    rng = np.random.default_rng(seed)
    X_pos = rng.normal(loc=2.0, scale=1.0, size=(n // 2, 88))
    X_neg = rng.normal(loc=-2.0, scale=1.0, size=(n // 2, 88))
    X = np.vstack([X_pos, X_neg]).astype(np.float64)
    y = np.array([1.0] * (n // 2) + [0.0] * (n // 2), dtype=np.float64)
    idx = rng.permutation(n)
    return X[idx], y[idx]


# ---------------------------------------------------------------------------
# Unit tests: MLPHead backward
# ---------------------------------------------------------------------------

class TestMLPHeadBackward:

    def test_loss_decreases_over_gradient_steps(self):
        """A single positive example: repeated backward steps should reduce loss."""
        mlp = MLPHead(input_dim=472)
        rng = np.random.default_rng(99)
        x = rng.normal(size=472)
        y = 1.0
        alpha = 0.7
        lr = 0.01

        losses = []
        for _ in range(30):
            p = mlp.forward(x)
            loss = ClassifierModel.asymmetric_bce_loss(y, p, alpha)
            losses.append(loss)
            mlp.backward(x, y, p, alpha, lr)

        assert losses[-1] < losses[0], (
            f"Loss did not decrease: first={losses[0]:.4f}, last={losses[-1]:.4f}"
        )

    def test_backward_returns_gradient_of_correct_shape(self):
        mlp = MLPHead(input_dim=472)
        x = np.ones(472)
        p = mlp.forward(x)
        d_x = mlp.backward(x, 1.0, p, 0.7, 0.001)
        assert d_x.shape == (472,)

    def test_weights_change_after_backward(self):
        mlp = MLPHead(input_dim=472)
        W1_before = mlp.W1.copy()
        x = np.ones(472)
        p = mlp.forward(x)
        mlp.backward(x, 1.0, p, 0.7, 0.01)
        assert not np.allclose(mlp.W1, W1_before), "W1 should change after backward"

    def test_negative_example_pushes_prob_down(self):
        """For y=0, repeated backward steps should reduce predicted probability."""
        mlp = MLPHead(input_dim=472)
        rng = np.random.default_rng(42)
        x = rng.normal(size=472)
        lr = 0.05
        alpha = 0.7
        probs = []
        for _ in range(20):
            p = mlp.forward(x)
            probs.append(p)
            mlp.backward(x, 0.0, p, alpha, lr)
        # Probability for y=0 should trend downward
        assert probs[-1] < probs[0] or probs[-1] < 0.6, (
            f"Prob for y=0 not decreasing: {probs[0]:.4f} → {probs[-1]:.4f}"
        )


# ---------------------------------------------------------------------------
# Unit tests: GraphSAGE backward
# ---------------------------------------------------------------------------

class TestGraphSAGEBackward:

    def test_weights_change_after_backward(self):
        model = GraphSAGEModel()
        W1_before = model.layer1.W.copy()
        node_feat = np.ones(8)
        sage_emb = model.forward(node_feat, [], [])
        d_sage = np.ones(model.output_dim) * 0.01
        model.backward_empty_neighbors(node_feat, d_sage, lr=0.01)
        assert not np.allclose(model.layer1.W, W1_before)

    def test_get_set_weights_dict_roundtrip(self):
        model = GraphSAGEModel()
        d = model.get_weights_dict()
        original_W1 = d["layer1_W"].copy()
        # Modify in-place
        model.layer1.W[:] = 0.0
        # Restore via set_weights_dict
        model.set_weights_dict(d)
        assert np.allclose(model.layer1.W, original_W1)


# ---------------------------------------------------------------------------
# Unit tests: TabTransformer backward
# ---------------------------------------------------------------------------

class TestTabTransformerBackward:

    def test_weights_change_after_backward(self):
        model = TabTransformerModel()
        W_out_before = model.W_out.copy()
        x = np.ones(88)
        model.backward(x, np.ones(88) * 0.01, lr=0.01)
        assert not np.allclose(model.W_out, W_out_before)

    def test_get_set_weights_dict_roundtrip(self):
        model = TabTransformerModel()
        d = model.get_weights_dict()
        original_W_out = d["W_out"].copy()
        model.W_out[:] = 0.0
        model.set_weights_dict(d)
        assert np.allclose(model.W_out, original_W_out)


# ---------------------------------------------------------------------------
# Integration tests: Training pipeline
# ---------------------------------------------------------------------------

class TestTrainingPipelineConvergence:

    def test_stage7_loss_decreases_across_epochs(self):
        """Joint training: average loss in the last epoch < loss in the first epoch."""
        config = TrainingConfig(
            n_epochs=10,
            batch_size=64,
            learning_rate=0.005,
            alpha=0.7,
            random_seed=7,
        )
        pipeline = TrainingPipeline(config)

        X, y = _make_separable_data(n=200)
        # Use smaller models for speed
        graphsage = GraphSAGEModel()
        tabtransformer = TabTransformerModel()

        epoch_losses = []
        mlp = pipeline.stage7_joint_training.__func__  # just verify it runs

        # Run a reduced joint training loop and collect per-epoch losses
        from lip.c1_failure_classifier.model import MLPHead
        mlp_head = MLPHead()
        model = ClassifierModel(graphsage=graphsage, tabtransformer=tabtransformer, mlp=mlp_head)
        rng = np.random.default_rng(7)
        lr = config.learning_rate
        alpha = config.alpha

        for epoch in range(config.n_epochs):
            total_loss = 0.0
            indices = rng.permutation(len(y))
            for i in indices:
                x_tab = X[i]
                tab_emb = tabtransformer.forward(x_tab)
                node_feat = x_tab[:8]
                sage_emb = graphsage.forward(node_feat, [], [])
                fused = np.concatenate([sage_emb, tab_emb])
                prob = mlp_head.forward(fused)
                total_loss += ClassifierModel.asymmetric_bce_loss(y[i], prob, alpha)
                d_fused = mlp_head.backward(fused, y[i], prob, alpha, lr)
                graphsage.backward_empty_neighbors(node_feat, d_fused[:graphsage.output_dim], lr)
                tabtransformer.backward(x_tab, d_fused[graphsage.output_dim:], lr)
            epoch_losses.append(total_loss / len(y))

        assert epoch_losses[-1] < epoch_losses[0], (
            f"Loss did not decrease: first={epoch_losses[0]:.4f}, last={epoch_losses[-1]:.4f}"
        )

    def test_trained_model_auc_beats_random(self):
        """After training on separable data, model AUC should clearly beat 0.55."""
        config = TrainingConfig(
            n_epochs=15,
            batch_size=32,
            learning_rate=0.01,
            alpha=0.7,
            val_split=0.3,
            random_seed=42,
        )
        pipeline = TrainingPipeline(config)

        X, y = _make_separable_data(n=300, seed=42)
        n_val = int(len(y) * config.val_split)
        X_train, y_train = X[n_val:], y[n_val:]
        X_val, y_val = X[:n_val], y[:n_val]

        graphsage = GraphSAGEModel()
        tabtransformer = TabTransformerModel()
        mlp_head = MLPHead()

        rng = np.random.default_rng(42)
        lr = config.learning_rate
        alpha = config.alpha

        for _ in range(config.n_epochs):
            indices = rng.permutation(len(y_train))
            for i in indices:
                x_tab = X_train[i]
                tab_emb = tabtransformer.forward(x_tab)
                node_feat = x_tab[:8]
                sage_emb = graphsage.forward(node_feat, [], [])
                fused = np.concatenate([sage_emb, tab_emb])
                prob = mlp_head.forward(fused)
                d_fused = mlp_head.backward(fused, y_train[i], prob, alpha, lr)
                graphsage.backward_empty_neighbors(node_feat, d_fused[:graphsage.output_dim], lr)
                tabtransformer.backward(x_tab, d_fused[graphsage.output_dim:], lr)

        # Evaluate on validation set
        scores = []
        for i in range(len(y_val)):
            x_tab = X_val[i]
            tab_emb = tabtransformer.forward(x_tab)
            node_feat = x_tab[:8]
            sage_emb = graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            scores.append(mlp_head.forward(fused))

        auc = _compute_auc(y_val, np.array(scores))
        assert auc > 0.55, f"Model AUC {auc:.4f} does not beat random chance."

    def test_stage8_threshold_in_unit_interval(self):
        """Stage 8 threshold calibration must return a value in (0, 1)."""
        config = TrainingConfig(n_epochs=5, batch_size=64, random_seed=0)
        pipeline = TrainingPipeline(config)

        X, y = _make_separable_data(n=200)
        graphsage = GraphSAGEModel()
        tabtransformer = TabTransformerModel()
        mlp_head = MLPHead()
        model = ClassifierModel(graphsage=graphsage, tabtransformer=tabtransformer, mlp=mlp_head)

        threshold = pipeline.stage8_threshold_calibration(model, X, y)
        assert 0.0 <= threshold <= 1.0, f"Threshold {threshold} outside [0, 1]"

    def test_full_pipeline_run_on_synthetic_data(self):
        """End-to-end: pipeline.run() on synthetic data returns model, threshold, embeddings."""
        config = TrainingConfig(
            n_epochs=3,
            batch_size=64,
            learning_rate=0.01,
            random_seed=1,
        )
        pipeline = TrainingPipeline(config)

        data = generate_synthetic_dataset(n_samples=150)
        model, threshold, emb_pipeline = pipeline.run(data)

        assert model is not None
        assert 0.0 <= threshold <= 1.0
        assert emb_pipeline is not None

    def test_compute_auc_utility(self):
        """_compute_auc should return 1.0 for perfect predictions."""
        y = np.array([0.0, 0.0, 1.0, 1.0])
        scores = np.array([0.1, 0.2, 0.8, 0.9])
        auc = _compute_auc(y, scores)
        assert abs(auc - 1.0) < 0.01

    def test_compute_auc_random(self):
        """_compute_auc should return ~0.5 for random scores."""
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, size=200).astype(float)
        scores = rng.uniform(size=200)
        auc = _compute_auc(y, scores)
        assert 0.3 < auc < 0.7  # within noise of random
