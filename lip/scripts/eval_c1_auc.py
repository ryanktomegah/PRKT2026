"""eval_c1_auc.py — Train C1 on synthetic data and print val_auc.

Uses a manual training loop (same as test_c1_training.py) with a
deterministic head/tail split that is independent of pipeline-internal RNG.

Usage:
    PYTHONPATH=. python lip/scripts/eval_c1_auc.py [--n_samples N] [--n_epochs E]

Defaults: --n_samples 500 --n_epochs 20 (runs in < 3 minutes)

Outputs to stdout:
    val_auc=<float>  threshold=<float>  n_train=<int>  n_val=<int>

Saves neural-network weights to /tmp/c1_weights.npz after training.
"""
from __future__ import annotations

import argparse

import numpy as np
import sklearn.preprocessing as _skl_pre

from lip.c1_failure_classifier.features import TabularFeatureEngineer
from lip.c1_failure_classifier.graphsage import GraphSAGEModel
from lip.c1_failure_classifier.model import ClassifierModel, MLPHead
from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset
from lip.c1_failure_classifier.tabtransformer import TabTransformerModel
from lip.c1_failure_classifier.training import _compute_auc


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate C1 val AUC on synthetic data")
    parser.add_argument("--n_samples", type=int, default=500)
    parser.add_argument("--n_epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val_split", type=float, default=0.2)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--alpha", type=float, default=0.7)
    parser.add_argument("--weights_out", type=str, default="/tmp/c1_weights.npz")
    parser.add_argument("--scale", action="store_true",
                        help="Apply StandardScaler (fit on train, transform val)")
    args = parser.parse_args()

    # ── Generate data ────────────────────────────────────────────────────────
    data = generate_synthetic_dataset(n_samples=args.n_samples, seed=args.seed)

    # ── Extract features (tabular 88-dim) ────────────────────────────────────
    tab_eng = TabularFeatureEngineer()
    X = np.stack([tab_eng.extract(r) for r in data], axis=0).astype(np.float64)
    y = np.array([r["label"] for r in data], dtype=np.float64)

    # ── Deterministic head/tail split (no pipeline-internal RNG dependency) ──
    n_val = max(1, int(len(data) * args.val_split))
    X_val, y_val = X[:n_val], y[:n_val]
    X_train, y_train = X[n_val:], y[n_val:]

    # ── Optional StandardScaler (fit on train only — no val leakage) ─────────
    scaler_desc = "no_scaling"
    if args.scale:
        scaler = _skl_pre.StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_val = scaler.transform(X_val)
        scaler_desc = "standard_scaled"
        print(f"  [scaling] StandardScaler applied — mean_abs_mean="
              f"{abs(scaler.mean_).mean():.4f}  mean_scale={scaler.scale_.mean():.4f}",
              flush=True)

    n_train = len(y_train)
    n_pos_train = int(y_train.sum())
    n_pos_val = int(y_val.sum())

    # ── Initialise sub-models ─────────────────────────────────────────────────
    graphsage = GraphSAGEModel()
    tabtransformer = TabTransformerModel()
    mlp = MLPHead()

    graphsage_input_dim = 8
    rng = np.random.default_rng(args.seed)
    lr = args.lr
    alpha = args.alpha

    best_auc = -1.0
    best_mlp_w = None
    best_sage_w = None
    best_tab_w = None

    # ── Training loop ─────────────────────────────────────────────────────────
    for epoch in range(args.n_epochs):
        total_loss = 0.0
        indices = rng.permutation(n_train)

        for i in indices:
            x_tab = X_train[i]
            tab_emb = tabtransformer.forward(x_tab)
            node_feat = x_tab[:graphsage_input_dim]
            sage_emb = graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            prob = mlp.forward(fused)
            label = float(y_train[i])

            # Asymmetric BCE loss
            p_clipped = float(np.clip(prob, 1e-7, 1 - 1e-7))
            if label == 1.0:
                total_loss += -alpha * np.log(p_clipped)
            else:
                total_loss += -(1 - alpha) * np.log(1 - p_clipped)

            d_fused = mlp.backward(fused, label, prob, alpha, lr)
            graphsage.backward_empty_neighbors(node_feat, d_fused[:graphsage.output_dim], lr)
            tabtransformer.backward(x_tab, d_fused[graphsage.output_dim:], lr)

        # Val AUC for checkpoint selection
        val_scores: list[float] = []
        for i in range(len(X_val)):
            x_tab = X_val[i]
            tab_emb = tabtransformer.forward(x_tab)
            node_feat = x_tab[:graphsage_input_dim]
            sage_emb = graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            val_scores.append(float(mlp.forward(fused)))

        epoch_auc = _compute_auc(y_val, np.array(val_scores))
        avg_loss = total_loss / max(1, n_train)
        print(f"  epoch {epoch + 1:>3d}/{args.n_epochs}  loss={avg_loss:.5f}  val_auc={epoch_auc:.4f}",
              flush=True)

        if epoch_auc > best_auc:
            best_auc = epoch_auc
            best_mlp_w = mlp.get_weights()
            best_sage_w = graphsage.get_weights_dict()
            best_tab_w = tabtransformer.get_weights_dict()

    # ── Restore best checkpoint ───────────────────────────────────────────────
    if best_mlp_w is not None:
        mlp.set_weights(best_mlp_w)
        graphsage.set_weights_dict(best_sage_w)  # type: ignore[arg-type]
        tabtransformer.set_weights_dict(best_tab_w)  # type: ignore[arg-type]

    # ── Final val evaluation ──────────────────────────────────────────────────
    final_scores: list[float] = []
    for i in range(len(X_val)):
        x_tab = X_val[i]
        tab_emb = tabtransformer.forward(x_tab)
        node_feat = x_tab[:graphsage_input_dim]
        sage_emb = graphsage.forward(node_feat, [], [])
        fused = np.concatenate([sage_emb, tab_emb])
        final_scores.append(float(mlp.forward(fused)))

    val_auc = _compute_auc(y_val, np.array(final_scores))

    # ── Simple F2-max threshold ───────────────────────────────────────────────
    best_threshold = 0.5
    best_f2 = -1.0
    for thr in np.linspace(0.01, 0.99, 99):
        preds = (np.array(final_scores) >= thr).astype(float)
        tp = float(((preds == 1) & (y_val == 1)).sum())
        fp = float(((preds == 1) & (y_val == 0)).sum())
        fn = float(((preds == 0) & (y_val == 1)).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f2 = (5 * prec * rec) / (4 * prec + rec) if (4 * prec + rec) > 0 else 0.0
        if f2 > best_f2:
            best_f2 = f2
            best_threshold = float(thr)

    # ── Save weights ──────────────────────────────────────────────────────────
    model = ClassifierModel(graphsage=graphsage, tabtransformer=tabtransformer, mlp=mlp)
    model.save_weights(args.weights_out)

    # ── Report ────────────────────────────────────────────────────────────────
    print(
        f"\nval_auc={val_auc:.4f}  threshold={best_threshold:.4f}  "
        f"n_train={len(X_train)}  n_val={n_val}  "
        f"n_pos_train={n_pos_train}  n_pos_val={n_pos_val}  "
        f"n_epochs={args.n_epochs}  best_auc={best_auc:.4f}  "
        f"scaling={scaler_desc}"
    )


if __name__ == "__main__":
    main()
