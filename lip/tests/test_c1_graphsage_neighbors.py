"""
test_c1_graphsage_neighbors.py — Tests for BIC graph neighbor signal in GraphSAGETorch.

Verifies that:
  1. Real neighbor features change the GraphSAGETorch embedding.
  2. All-zero neighbor tensor produces the same result as the None (legacy) path.
  3. _build_neighbor_tensor handles cold-start (unknown BIC) without exception.
  4. stage5_graphsage_pretrain_torch runs end-to-end with a real graph.
  5. train_torch() end-to-end with real BIC graph neighbors returns probabilities in [0, 1].
"""
from __future__ import annotations

import os

import numpy as np
import pytest
import torch

from lip.c1_failure_classifier.graph_builder import BICGraphBuilder, PaymentEdge
from lip.c1_failure_classifier.graphsage_torch import GraphSAGETorch
from lip.c1_failure_classifier.training import TrainingConfig
from lip.c1_failure_classifier.training_torch import (
    TrainingPipelineTorch,
    _build_neighbor_tensor,
)


# LightGBM (OpenMP) + PyTorch BLAS deadlock prevention on macOS
@pytest.fixture(scope="session", autouse=True)
def _torch_single_thread():
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # already set by another session fixture or parallel work has started


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_graph() -> BICGraphBuilder:
    """Build a small BIC graph with known neighbor structure.

    AAAAAA01 → BBBBBB01 (10 payments, large volume)
    AAAAAA01 → CCCCCC01 (1 payment, small volume)
    So get_neighbors("AAAAAA01", k=2) returns ["BBBBBB01", "CCCCCC01"].
    """
    builder = BICGraphBuilder()
    for i in range(10):
        builder.add_payment(
            PaymentEdge(
                uetr=f"uetr-{i}",
                sending_bic="AAAAAA01",
                receiving_bic="BBBBBB01",
                amount_usd=1_000_000.0 + i * 10_000,
                currency_pair="USD_EUR",
                timestamp=1_700_000_000.0 + i,
                features={"failed": i % 3 == 0},
            )
        )
    builder.add_payment(
        PaymentEdge(
            uetr="uetr-extra",
            sending_bic="AAAAAA01",
            receiving_bic="CCCCCC01",
            amount_usd=5_000.0,
            currency_pair="USD_GBP",
            timestamp=1_700_000_100.0,
            features={"failed": False},
        )
    )
    return builder


# ---------------------------------------------------------------------------
# Test 1 & 2 — GraphSAGETorch.forward() with neighbor_feats
# ---------------------------------------------------------------------------


class TestGraphSAGENeighborForward:
    def test_neighbor_forward_differs_from_zero_forward(self):
        """Real neighbor features change the GraphSAGETorch embedding."""
        torch.manual_seed(0)
        model = GraphSAGETorch()
        model.eval()

        x = torch.randn(1, 8)
        nbr = torch.randn(1, 3, 8)  # non-zero neighbor features

        with torch.no_grad():
            emb_no_nbr = model(x, None)
            emb_with_nbr = model(x, nbr)

        assert emb_no_nbr.shape == (1, 384)
        assert emb_with_nbr.shape == (1, 384)
        assert not torch.allclose(emb_no_nbr, emb_with_nbr), (
            "Real (non-zero) neighbor features must change the embedding"
        )

    def test_cold_start_neighbor_matches_zero_forward(self):
        """All-zero neighbor tensor produces identical output to None path.

        Valid on a freshly initialised model where all biases are zero:
        layer1(zeros(B*k, 16)) = 0 exactly, so both paths use zero aggregation.
        """
        model = GraphSAGETorch()
        # Xavier init guarantees zero biases; verify before relying on it
        assert torch.all(model.layer1.bias == 0), "layer1.bias must be 0 on init"
        assert torch.all(model.layer2.bias == 0), "layer2.bias must be 0 on init"

        model.eval()
        torch.manual_seed(1)
        x = torch.randn(2, 8)
        k = 4
        nbr_zeros = torch.zeros(2, k, 8)

        with torch.no_grad():
            emb_none = model(x, None)
            emb_zeros = model(x, nbr_zeros)

        assert torch.allclose(emb_none, emb_zeros, atol=1e-6), (
            "All-zero neighbor tensor must match None path on a fresh model"
        )


# ---------------------------------------------------------------------------
# Test 3 — _build_neighbor_tensor cold-start
# ---------------------------------------------------------------------------


class TestBuildNeighborTensor:
    def test_build_neighbor_tensor_cold_start(self):
        """Unknown BIC returns (1, k, 8) all-zeros tensor without exception."""
        graph = _make_minimal_graph()
        bics = ["UNKNOWN_BIC_XYZ"]
        k = 5

        result = _build_neighbor_tensor(bics, graph, k)

        assert result.shape == (1, k, 8), f"Expected (1, {k}, 8), got {result.shape}"
        assert torch.all(result == 0.0), "Cold-start BIC must produce an all-zero tensor"
        assert result.dtype == torch.float32


# ---------------------------------------------------------------------------
# Test 4 — stage5 with real graph
# ---------------------------------------------------------------------------


class TestStage5WithGraph:
    def test_stage5_pretrain_with_graph_runs(self):
        """stage5_graphsage_pretrain_torch returns a valid GraphSAGETorch."""
        torch.manual_seed(42)
        rng = np.random.default_rng(42)
        n = 30
        X_train = rng.normal(size=(n, 96)).astype(np.float64)  # 96-dim (8 node + 88 tab)
        y_train = (rng.random(n) > 0.7).astype(np.float64)
        bic_train = ["AAAAAA01"] * 20 + ["BBBBBB01"] * 10

        graph = _make_minimal_graph()
        config = TrainingConfig(n_epochs=2, batch_size=16)
        pipe = TrainingPipelineTorch(config=config)

        model = pipe.stage5_graphsage_pretrain_torch(X_train, y_train, graph, bic_train)

        assert isinstance(model, GraphSAGETorch)
        model.eval()
        with torch.no_grad():
            out = model(torch.randn(4, 8))
        assert out.shape == (4, 384)


# ---------------------------------------------------------------------------
# Test 5 — full train_torch() end-to-end
# ---------------------------------------------------------------------------


class TestTrainTorchEndToEnd:
    def test_train_torch_end_to_end_with_graph(self):
        """Full train_torch() on 50 synthetic records returns probabilities in [0, 1]."""
        from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset

        records = generate_synthetic_dataset(n_samples=50, seed=7)
        config = TrainingConfig(n_epochs=2, batch_size=16, val_split=0.2)
        pipe = TrainingPipelineTorch(config=config)
        model = pipe.train_torch(records)

        rng = np.random.default_rng(7)
        node_features = rng.random(8).astype(np.float32)
        tab_features = rng.random(96).astype(np.float32)  # full 96-dim X

        prob = model.predict_proba(node_features, tab_features)

        assert isinstance(prob, float), "predict_proba must return a float"
        assert 0.0 <= prob <= 1.0, f"Probability {prob!r} is out of [0, 1]"
