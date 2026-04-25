# macOS performance note: run with:
# METAL_DEVICE_WRAPPER_TYPE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# Disabling Metal API Validation and capping OMP/MKL threads recovers
# ~62% wall time on Apple Silicon (298s → 114s at n=10K).

"""eval_c1_auc_torch.py — Benchmark NumPy vs PyTorch C1 training.

Trains on synthetic data at n=1000 for both NumPy and PyTorch pipelines,
then runs the PyTorch pipeline at n=50000 to demonstrate scalability.
Reports val_auc and wall-clock time for each run.

Usage:
    PYTHONPATH=. python lip/scripts/eval_c1_auc_torch.py [options]

Options:
    --n_samples_small N   Sample count for small comparison (default 1000)
    --n_samples_large N   Sample count for large torch run (default 50000)
    --n_epochs E          Epochs for all runs (default 20)
    --lr LR               Learning rate (default 0.01 numpy / 1e-3 torch)
    --alpha A             Asymmetric BCE alpha (default 0.7)
    --seed S              Random seed (default 42)
    --val_split V         Validation fraction (default 0.2)
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import torch

from lip.c1_failure_classifier.features import TabularFeatureEngineer
from lip.c1_failure_classifier.graphsage import GraphSAGEModel as GraphSAGENumPy
from lip.c1_failure_classifier.model import MLPHead
from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset
from lip.c1_failure_classifier.tabtransformer import TabTransformerModel as TabTransformerNumPy
from lip.c1_failure_classifier.training import TrainingConfig, _compute_auc

# ---------------------------------------------------------------------------
# NumPy training loop (mirrors eval_c1_auc.py)
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    e = np.exp(x)
    return e / (1.0 + e)


def _run_numpy(X_train, y_train, X_val, y_val, n_epochs: int, lr: float, alpha: float):
    """Train C1 neural components with the NumPy pipeline."""
    graphsage = GraphSAGENumPy()
    tabtransformer = TabTransformerNumPy()
    mlp = MLPHead()

    rng = np.random.default_rng(42)
    best_auc = -1.0
    best_mlp_w = best_sage_w = best_tab_w = None

    for _ in range(n_epochs):
        indices = rng.permutation(len(y_train))
        for i in indices:
            x_tab = X_train[i]
            tab_emb = tabtransformer.forward(x_tab)
            node_feat = x_tab[:8]
            sage_emb = graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            prob = mlp.forward(fused)
            label = float(y_train[i])

            d_fused = mlp.backward(fused, label, prob, alpha, lr)
            graphsage.backward_empty_neighbors(node_feat, d_fused[:384], lr)
            tabtransformer.backward(x_tab, d_fused[384:], lr)

        # Val AUC checkpoint
        val_scores = []
        for i in range(len(X_val)):
            x_tab = X_val[i]
            tab_emb = tabtransformer.forward(x_tab)
            node_feat = x_tab[:8]
            sage_emb = graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            val_scores.append(float(mlp.forward(fused)))
        auc = _compute_auc(y_val, np.array(val_scores))
        if auc > best_auc:
            best_auc = auc
            best_mlp_w = mlp.get_weights()
            best_sage_w = graphsage.get_weights_dict()
            best_tab_w = tabtransformer.get_weights_dict()

    if best_mlp_w is not None:
        assert best_sage_w is not None
        assert best_tab_w is not None
        mlp.set_weights(best_mlp_w)
        graphsage.set_weights_dict(best_sage_w)
        tabtransformer.set_weights_dict(best_tab_w)

    return best_auc


# ---------------------------------------------------------------------------
# PyTorch training loop
# ---------------------------------------------------------------------------


def _run_torch(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_epochs: int,
    lr: float,
    config: TrainingConfig,
) -> float:
    """Train C1 neural components with the PyTorch pipeline."""
    from lip.c1_failure_classifier.training_torch import TrainingPipelineTorch

    pipeline = TrainingPipelineTorch(config=config)
    sage = pipeline.stage5_graphsage_pretrain_torch(X_train, y_train)
    tab = pipeline.stage6_tabtransformer_pretrain_torch(X_train, y_train)
    model = pipeline.stage7_joint_training_torch(
        sage, tab, X_train, y_train, X_val, y_val
    )

    model.eval()
    with torch.no_grad():
        nf = torch.tensor(X_val[:, :8], dtype=torch.float32)
        tf = torch.tensor(X_val, dtype=torch.float32)
        logits = model(nf, tf).squeeze(1)
        scores = torch.sigmoid(logits).numpy()

    return _compute_auc(y_val.astype(np.float64), scores.astype(np.float64))


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------


def _build_dataset(n: int, seed: int, val_split: float):
    data = generate_synthetic_dataset(n_samples=n, seed=seed)
    tab_eng = TabularFeatureEngineer()
    tab_feats = np.stack([tab_eng.extract(r) for r in data], axis=0).astype(np.float64)
    # Prepend 8-dim zeros for graph node features: no BICGraphBuilder is
    # available in this eval context so graph dims are zero-filled.
    # X shape: (n, 96) = [node_8d ‖ tab_88d], matching the production pipeline.
    node_zeros = np.zeros((len(data), 8), dtype=np.float64)
    X = np.concatenate([node_zeros, tab_feats], axis=1)
    y = np.array([r["is_failure"] for r in data], dtype=np.float64)
    n_val = max(1, int(n * val_split))
    return X[:n_val], y[:n_val], X[n_val:], y[n_val:]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark NumPy vs PyTorch C1 training")
    parser.add_argument("--n_samples_small", type=int, default=1000)
    parser.add_argument("--n_samples_large", type=int, default=50000)
    parser.add_argument("--n_epochs", type=int, default=20)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--alpha", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val_split", type=float, default=0.2)
    args = parser.parse_args()

    config = TrainingConfig(
        n_epochs=args.n_epochs,
        batch_size=256,
        learning_rate=1e-3,
        alpha=args.alpha,
        val_split=args.val_split,
        random_seed=args.seed,
    )

    # ── NumPy: n_samples_small ────────────────────────────────────────────────
    X_val, y_val, X_train, y_train = _build_dataset(
        args.n_samples_small, args.seed, args.val_split
    )
    t0 = time.perf_counter()
    numpy_auc = _run_numpy(
        X_train, y_train, X_val, y_val, args.n_epochs, args.lr, args.alpha
    )
    numpy_time = time.perf_counter() - t0
    print(
        f"numpy:  n={args.n_samples_small:<6d}  epochs={args.n_epochs}  "
        f"auc={numpy_auc:.4f}  time={numpy_time:.1f}s"
    )

    # ── PyTorch: n_samples_small ──────────────────────────────────────────────
    t0 = time.perf_counter()
    torch_auc_small = _run_torch(
        X_train, y_train, X_val, y_val, args.n_epochs, 1e-3, config
    )
    torch_time_small = time.perf_counter() - t0
    print(
        f"torch:  n={args.n_samples_small:<6d}  epochs={args.n_epochs}  "
        f"auc={torch_auc_small:.4f}  time={torch_time_small:.1f}s"
    )

    # ── PyTorch: n_samples_large ──────────────────────────────────────────────
    X_val_l, y_val_l, X_train_l, y_train_l = _build_dataset(
        args.n_samples_large, args.seed, args.val_split
    )
    t0 = time.perf_counter()
    torch_auc_large = _run_torch(
        X_train_l, y_train_l, X_val_l, y_val_l, args.n_epochs, 1e-3, config
    )
    torch_time_large = time.perf_counter() - t0
    print(
        f"torch:  n={args.n_samples_large:<6d}  epochs={args.n_epochs}  "
        f"auc={torch_auc_large:.4f}  time={torch_time_large:.1f}s"
    )


if __name__ == "__main__":
    main()
