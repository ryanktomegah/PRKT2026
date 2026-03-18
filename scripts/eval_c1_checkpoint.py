"""eval_c1_checkpoint.py — Re-evaluate a saved C1 checkpoint with correct neighbor features.

Fixes the measurement bug in the original train_c1_on_parquet.py eval where
neighbor_feats=None was passed to a model trained with neighbor features,
collapsing AUC to ~0.5. Also adds LightGBM and ensemble evaluation.

Usage
-----
PYTHONPATH=. python scripts/eval_c1_checkpoint.py \
    --parquet artifacts/production_data_mixed/payments_synthetic.parquet \
    --checkpoint artifacts/c1_model_parquet.pt \
    --sample 1000000 --seed 42
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval_c1_checkpoint")

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def _compute_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=np.float64)
    y_scores = np.asarray(y_scores, dtype=np.float64)
    if len(np.unique(y_true)) < 2:
        return 0.5
    order = np.argsort(-y_scores)
    y_sorted = y_true[order]
    n_pos = float(np.sum(y_true))
    n_neg = float(len(y_true) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    tpr_vals = np.cumsum(y_sorted) / n_pos
    fpr_vals = np.cumsum(1.0 - y_sorted) / n_neg
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    return float(max(0.0, min(1.0, abs(_trapz(tpr_vals, fpr_vals)))))


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True)
    parser.add_argument("--checkpoint", default="artifacts/c1_model_parquet.pt")
    parser.add_argument("--sample", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args(argv)

    from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline
    from lip.c1_failure_classifier.training_torch import _build_neighbor_tensor
    from lip.c1_failure_classifier.model_torch import ClassifierModelTorch
    from lip.c1_failure_classifier.graphsage_torch import GraphSAGETorch
    from lip.c1_failure_classifier.tabtransformer_torch import TabTransformerTorch
    from lip.c1_failure_classifier.model_torch import MLPHeadTorch
    from scripts.train_c1_on_parquet import load_parquet_as_records

    records = load_parquet_as_records(args.parquet, sample_n=args.sample, seed=args.seed)

    config = TrainingConfig(
        n_epochs=20, batch_size=256, learning_rate=1e-3, alpha=0.7,
        k_neighbors_train=10, k_neighbors_infer=5, val_split=0.2, random_seed=args.seed,
    )

    np_pipeline = TrainingPipeline(config=config)
    validated = np_pipeline.stage1_data_validation(records)
    graph = np_pipeline.stage2_graph_construction(validated)
    X, y, bics = np_pipeline.stage3_feature_extraction(validated, graph)
    _, X_val, _, y_val, _, bic_val = np_pipeline.stage4_train_val_split(X, y, bics)

    # Load checkpoint
    graphsage = GraphSAGETorch()
    tabtransformer = TabTransformerTorch(input_dim=88)
    mlp_head = MLPHeadTorch()
    model = ClassifierModelTorch(graphsage=graphsage, tabtransformer=tabtransformer, mlp_head=mlp_head)
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    logger.info("Checkpoint loaded: %s", args.checkpoint)

    # Build val neighbor tensor correctly
    val_nbr = _build_neighbor_tensor(bic_val, graph, config.k_neighbors_infer)

    with torch.no_grad():
        node_feat = torch.tensor(X_val[:, :8], dtype=torch.float32)
        tab_feat = torch.tensor(X_val[:, 8:], dtype=torch.float32)
        logits = model(node_feat, tab_feat, val_nbr).squeeze(1)
        scores_torch = torch.sigmoid(logits).cpu().numpy()

    val_auc_torch = _compute_auc(y_val, scores_torch)
    logger.info("val_AUC (PyTorch, with neighbors): %.4f", val_auc_torch)

    # LightGBM — reload from checkpoint dir if available
    lgbm_path = Path(args.checkpoint).parent / "c1_lgbm_parquet.pkl"
    ensemble_auc = None
    lgbm_auc = None
    if lgbm_path.exists():
        import pickle
        with open(lgbm_path, "rb") as fh:
            lgbm_model = pickle.load(fh)
        lgbm_scores = lgbm_model.predict_proba(X_val[:, 8:])[:, 1]
        lgbm_auc = _compute_auc(y_val, lgbm_scores)
        logger.info("val_AUC (LightGBM): %.4f", lgbm_auc)
        ensemble_scores = 0.5 * scores_torch + 0.5 * lgbm_scores
        ensemble_auc = _compute_auc(y_val, ensemble_scores)
        logger.info("val_AUC (ensemble 50/50): %.4f", ensemble_auc)
    else:
        logger.warning("LightGBM checkpoint not found at %s — skipping ensemble eval", lgbm_path)

    # F2 on torch scores
    best_f2, best_thresh = 0.0, 0.5
    scores_for_f2 = (0.5 * scores_torch + 0.5 * lgbm_scores) if lgbm_auc else scores_torch
    for thresh in np.linspace(0.05, 0.95, 91):
        preds = (scores_for_f2 >= thresh).astype(int)
        tp = float(np.sum((preds == 1) & (y_val == 1)))
        fp = float(np.sum((preds == 1) & (y_val == 0)))
        fn = float(np.sum((preds == 0) & (y_val == 1)))
        prec = tp / (tp + fp + 1e-9)
        rec = tp / (tp + fn + 1e-9)
        f2 = (5 * prec * rec) / (4 * prec + rec + 1e-9)
        if f2 > best_f2:
            best_f2, best_thresh = f2, float(thresh)

    print("\n===== C1 Eval (corrected) =====")
    print(f"  val_AUC (PyTorch+neighbors) : {val_auc_torch:.4f}")
    if lgbm_auc:
        print(f"  val_AUC (LightGBM)          : {lgbm_auc:.4f}")
        print(f"  val_AUC (ensemble 50/50)    : {ensemble_auc:.4f}")
    print(f"  F2 threshold                : {best_thresh:.3f}  (F2={best_f2:.4f})")

    metrics = {
        "val_auc_torch_with_neighbors": round(val_auc_torch, 6),
        "val_auc_lgbm": round(lgbm_auc, 6) if lgbm_auc else None,
        "val_auc_ensemble": round(ensemble_auc, 6) if ensemble_auc else None,
        "f2_threshold": round(best_thresh, 4),
        "f2_score": round(best_f2, 6),
        "n_val": int(len(y_val)),
    }
    out = Path(args.output_dir) / "train_metrics_parquet.json"
    with open(out, "w") as fh:
        json.dump(metrics, fh, indent=2)
    logger.info("Updated metrics saved: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
