"""
test_c1_torch.py — PyTorch C1 neural component tests.

Verifies:
  1. GraphSAGETorch forward shape + L2-norm
  2. TabTransformerTorch forward shape
  3. Gradient flow through ClassifierModelTorch (all params receive grad)
  4. Training convergence: AUC > 0.55 after 10 epochs on separable data
  5. Batch consistency: forward(x[0:1]) ≈ forward(x)[0]
  6. GPU forward (skipped if CUDA unavailable)
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from lip.c1_failure_classifier.graphsage_torch import GraphSAGETorch
from lip.c1_failure_classifier.model_torch import (
    ClassifierModelTorch,
    MLPHeadTorch,
)
from lip.c1_failure_classifier.tabtransformer_torch import TabTransformerTorch
from lip.c1_failure_classifier.training import _compute_auc

# ---------------------------------------------------------------------------
# Session fixture — prevent LightGBM OpenMP / PyTorch BLAS thread deadlock
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _limit_torch_threads():
    """Limit PyTorch intra/inter-op threads to 1.

    LightGBM initialises OpenMP before these tests run.  On macOS, the
    OpenMP and PyTorch BLAS thread pools deadlock unless PyTorch is
    constrained to a single thread.  Setting these here (in a session-scoped
    autouse fixture) ensures they take effect before the first BLAS call
    (``nn.MultiheadAttention`` forward) and do not affect NumPy inference.
    """
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # already set by an earlier session fixture (e.g. test_c1_graphsage_neighbors.py)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_separable_data(n: int = 200, seed: int = 42):
    """Linearly separable 96-dim dataset matching the production pipeline layout.

    X shape is (n, 96): first 8 dims are zero-filled graph node features,
    dims 8-95 are the 88-dim tabular feature block.
    """
    rng = np.random.default_rng(seed)
    X_pos = rng.normal(loc=2.0, scale=1.0, size=(n // 2, 96))
    X_neg = rng.normal(loc=-2.0, scale=1.0, size=(n // 2, 96))
    X = np.vstack([X_pos, X_neg]).astype(np.float32)
    y = np.array([1.0] * (n // 2) + [0.0] * (n // 2), dtype=np.float32)
    idx = rng.permutation(n)
    return X[idx], y[idx]


def _build_model() -> ClassifierModelTorch:
    """Instantiate a fresh ClassifierModelTorch with production-pipeline dims."""
    return ClassifierModelTorch(
        graphsage=GraphSAGETorch(),
        tabtransformer=TabTransformerTorch(input_dim=96),
        mlp_head=MLPHeadTorch(),
    )


# ---------------------------------------------------------------------------
# Test 1 — GraphSAGETorch forward shape + L2-norm
# ---------------------------------------------------------------------------


def test_graphsage_forward_shape():
    """Output shape must be (4, 384) and rows must be unit L2-norm."""
    model = GraphSAGETorch()
    x = torch.rand(4, 8)
    out = model(x)

    assert out.shape == (4, 384), f"Expected (4, 384), got {out.shape}"

    norms = torch.norm(out, p=2, dim=1)
    assert torch.allclose(norms, torch.ones(4), atol=1e-5), (
        f"L2 norms not ≈ 1.0: {norms}"
    )


# ---------------------------------------------------------------------------
# Test 2 — TabTransformerTorch forward shape
# ---------------------------------------------------------------------------


def test_tabtransformer_forward_shape():
    """Output shape must be (4, 88)."""
    model = TabTransformerTorch()
    x = torch.rand(4, 88)
    out = model(x)

    assert out.shape == (4, 88), f"Expected (4, 88), got {out.shape}"


# ---------------------------------------------------------------------------
# Test 3 — Gradient flow
# ---------------------------------------------------------------------------


def test_gradient_flow():
    """All parameters must receive a non-zero gradient after one backward pass."""
    model = _build_model()
    model.train()

    node_feat = torch.rand(8, 8)
    tab_feat = torch.rand(8, 96)
    labels = torch.randint(0, 2, (8, 1)).float()

    criterion = torch.nn.BCEWithLogitsLoss()
    logits = model(node_feat, tab_feat)
    loss = criterion(logits, labels)
    loss.backward()

    dead_params = []
    for name, param in model.named_parameters():
        if param.grad is None or param.grad.abs().sum().item() == 0:
            dead_params.append(name)

    assert not dead_params, f"Zero-gradient parameters: {dead_params}"


# ---------------------------------------------------------------------------
# Test 4 — Training convergence
# ---------------------------------------------------------------------------


def test_training_convergence():
    """AUC must exceed 0.55 after 10 training epochs on separable data."""
    X, y = _make_separable_data(n=200, seed=42)

    # 80/20 split
    n_val = 40
    X_val, y_val = X[:n_val], y[:n_val]
    X_train, y_train = X[n_val:], y[n_val:]

    model = _build_model()
    criterion = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([7.0 / 3.0])
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    node_feats_train = torch.tensor(X_train[:, :8])
    tab_feats_train = torch.tensor(X_train)
    labels_train = torch.tensor(y_train).unsqueeze(1)

    model.train()
    for _ in range(10):
        optimizer.zero_grad()
        logits = model(node_feats_train, tab_feats_train)
        loss = criterion(logits, labels_train)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        nf_val = torch.tensor(X_val[:, :8])
        tf_val = torch.tensor(X_val)
        logits_val = model(nf_val, tf_val).squeeze(1)
        scores = torch.sigmoid(logits_val).numpy()

    auc = _compute_auc(y_val.astype(np.float64), scores.astype(np.float64))
    assert auc > 0.55, f"AUC too low after 10 epochs: {auc:.4f}"


# ---------------------------------------------------------------------------
# Test 5 — Batch consistency
# ---------------------------------------------------------------------------


def test_batch_consistency():
    """Single-sample forward must match the corresponding row in a batch forward."""
    model = _build_model()
    model.eval()

    torch.manual_seed(0)
    node_feat = torch.rand(4, 8)
    tab_feat = torch.rand(4, 96)

    with torch.no_grad():
        batch_out = model(node_feat, tab_feat)                        # (4, 1)
        single_out = model(node_feat[0:1], tab_feat[0:1])            # (1, 1)

    assert torch.allclose(single_out, batch_out[0:1], atol=1e-4), (
        f"Batch inconsistency: single={single_out.item():.6f}  "
        f"batch[0]={batch_out[0].item():.6f}"
    )


# ---------------------------------------------------------------------------
# Test 6 — GPU (skipped if CUDA unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_gpu_if_available():
    """Model must produce near-identical results on GPU vs CPU."""
    torch.manual_seed(99)
    node_feat = torch.rand(4, 8)
    tab_feat = torch.rand(4, 96)

    model_cpu = _build_model()
    model_cpu.eval()
    with torch.no_grad():
        cpu_out = model_cpu(node_feat, tab_feat)

    model_gpu = _build_model()
    model_gpu.load_state_dict(model_cpu.state_dict())
    model_gpu = model_gpu.cuda()
    model_gpu.eval()
    with torch.no_grad():
        gpu_out = model_gpu(node_feat.cuda(), tab_feat.cuda()).cpu()

    assert torch.allclose(gpu_out, cpu_out, atol=1e-4), (
        f"GPU/CPU discrepancy: max_diff={torch.max(torch.abs(gpu_out - cpu_out)).item()}"
    )
