#!/usr/bin/env python3
"""
train_all.py — End-to-end training orchestration for LIP models C1 and C2.

Usage:
    cd /home/user/PRKT2026
    PYTHONPATH=. python scripts/train_all.py [--c1-samples N] [--c2-samples N] [--epochs N] [--seed N]

Outputs:
    artifacts/c1_model.npz     — C1 weight checkpoint (best AUC epoch)
    artifacts/c2_model.json    — C2 LightGBM surrogate weights
    artifacts/train_metrics.json — Training metrics for both models

Spec coverage:
    C1: Architecture Spec sections 6-8 (GraphSAGE pre-train → TabTransformer pre-train → joint SGD → F2 calibration)
    C2: Architecture Spec sections 9-11 (Optuna HP search → ensemble → isotonic calibration → thin-file stress test)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# Ensure repo root is on PYTHONPATH when invoked directly
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_all")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_artifacts_dir() -> str:
    path = os.path.join(_REPO_ROOT, "artifacts")
    os.makedirs(path, exist_ok=True)
    return path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train LIP C1 and C2 models on synthetic data.")
    p.add_argument("--c1-samples", type=int, default=2000, help="C1 synthetic records (default: 2000)")
    p.add_argument("--c2-samples", type=int, default=2000, help="C2 synthetic records (default: 2000)")
    p.add_argument("--epochs", type=int, default=10, help="C1 joint training epochs (default: 10)")
    p.add_argument("--seed", type=int, default=42, help="Master random seed (default: 42)")
    p.add_argument("--skip-c1", action="store_true", help="Skip C1 training")
    p.add_argument("--skip-c2", action="store_true", help="Skip C2 training")
    return p.parse_args()


# ---------------------------------------------------------------------------
# C1 Training
# ---------------------------------------------------------------------------

def train_c1(n_samples: int, n_epochs: int, seed: int, artifacts_dir: str) -> dict:
    """Train C1 failure classifier on synthetic SWIFT payment data.

    Returns a metrics dict with keys: auc, threshold, training_time_s.
    """
    logger.info("=" * 60)
    logger.info("C1 FAILURE CLASSIFIER — starting training")
    logger.info("  samples=%d  epochs=%d  seed=%d", n_samples, n_epochs, seed)
    logger.info("=" * 60)

    from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset
    from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline

    t0 = time.time()

    logger.info("Generating %d synthetic payment records...", n_samples)
    data = generate_synthetic_dataset(n_samples=n_samples, seed=seed)
    logger.info("  Generated %d records (label distribution: %.1f%% failures)",
                len(data), 100 * sum(r["label"] for r in data) / len(data))

    config = TrainingConfig(
        n_epochs=n_epochs,
        batch_size=128,
        learning_rate=0.005,
        random_seed=seed,
    )
    pipeline = TrainingPipeline(config)

    logger.info("Running C1 training pipeline (9 stages)...")
    model, threshold, emb_pipeline = pipeline.run(data)

    elapsed = time.time() - t0
    logger.info("C1 training complete in %.1fs  threshold=%.4f", elapsed, threshold)

    # Save weights
    weight_path = os.path.join(artifacts_dir, "c1_model.npz")
    graphsage_weights = model.graphsage.get_weights_dict()
    tabtransformer_weights = model.tabtransformer.get_weights_dict()
    mlp_weights = {
        "mlp_W1": model.mlp.W1,
        "mlp_b1": model.mlp.b1,
        "mlp_W2": model.mlp.W2,
        "mlp_b2": model.mlp.b2,
        "mlp_W3": model.mlp.W3,
        "mlp_b3": model.mlp.b3,
    }
    import numpy as np
    save_dict = {}
    for k, v in {**graphsage_weights, **tabtransformer_weights, **mlp_weights}.items():
        save_dict[k] = v
    save_dict["threshold"] = np.array([threshold])
    np.savez(weight_path, **save_dict)
    logger.info("C1 weights saved → %s", weight_path)

    return {
        "model": "C1_FailureClassifier",
        "threshold": float(threshold),
        "training_time_s": round(elapsed, 2),
        "n_samples": len(data),
        "n_epochs": n_epochs,
        "weight_path": weight_path,
    }


# ---------------------------------------------------------------------------
# C2 Training
# ---------------------------------------------------------------------------

def train_c2(n_samples: int, seed: int, artifacts_dir: str) -> dict:
    """Train C2 PD model on synthetic borrower + payment data.

    Returns a metrics dict with keys: auc, brier_score, ks_stat, training_time_s.
    """
    logger.info("=" * 60)
    logger.info("C2 PD MODEL — starting training")
    logger.info("  samples=%d  seed=%d", n_samples, seed)
    logger.info("=" * 60)

    from lip.c2_pd_model.synthetic_data import generate_pd_training_data
    from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig

    t0 = time.time()

    logger.info("Generating %d synthetic PD records (Tier 1/2/3 stratified)...", n_samples)
    data = generate_pd_training_data(n_samples=n_samples, seed=seed)
    n_defaults = sum(r["label"] for r in data)
    logger.info("  Generated %d records  defaults=%d (%.1f%%)",
                len(data), n_defaults, 100 * n_defaults / len(data))

    config = TrainingConfig(
        n_trials=5,    # Reduced from 50 for synthetic data speed
        n_models=3,    # Reduced from 5 for speed
        random_seed=seed,
    )
    pipeline = PDTrainingPipeline(config)

    logger.info("Running C2 training pipeline (9 stages)...")
    pd_model, metrics = pipeline.run(data)

    elapsed = time.time() - t0
    logger.info("C2 training complete in %.1fs", elapsed)
    logger.info("  AUC=%.4f  Brier=%.4f  KS=%.4f",
                metrics.get("auc", 0), metrics.get("brier_score", 0), metrics.get("ks_stat", 0))

    # Save model (surrogate weights if LightGBM not available)
    model_path = os.path.join(artifacts_dir, "c2_model.json")
    try:
        pd_model.save(model_path)
        logger.info("C2 model saved → %s", model_path)
    except Exception as exc:
        logger.warning("C2 model save failed (non-critical): %s", exc)

    return {
        "model": "C2_PDModel",
        "auc": metrics.get("auc", 0),
        "brier_score": metrics.get("brier_score", 0),
        "ks_stat": metrics.get("ks_stat", 0),
        "training_time_s": round(elapsed, 2),
        "n_samples": len(data),
        "model_path": model_path,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    artifacts_dir = _ensure_artifacts_dir()

    all_metrics: dict = {}
    errors: list = []

    if not args.skip_c1:
        try:
            c1_metrics = train_c1(
                n_samples=args.c1_samples,
                n_epochs=args.epochs,
                seed=args.seed,
                artifacts_dir=artifacts_dir,
            )
            all_metrics["c1"] = c1_metrics
            logger.info("✓ C1 training succeeded")
        except Exception as exc:
            logger.error("✗ C1 training failed: %s", exc, exc_info=True)
            errors.append({"model": "C1", "error": str(exc)})
    else:
        logger.info("C1 training skipped (--skip-c1)")

    if not args.skip_c2:
        try:
            c2_metrics = train_c2(
                n_samples=args.c2_samples,
                seed=args.seed,
                artifacts_dir=artifacts_dir,
            )
            all_metrics["c2"] = c2_metrics
            logger.info("✓ C2 training succeeded")
        except Exception as exc:
            logger.error("✗ C2 training failed: %s", exc, exc_info=True)
            errors.append({"model": "C2", "error": str(exc)})
    else:
        logger.info("C2 training skipped (--skip-c2)")

    # Write metrics
    metrics_path = os.path.join(artifacts_dir, "train_metrics.json")
    report = {"metrics": all_metrics, "errors": errors}
    with open(metrics_path, "w") as fh:
        json.dump(report, fh, indent=2)
    logger.info("Metrics saved → %s", metrics_path)

    if errors:
        logger.error("%d model(s) failed. See %s for details.", len(errors), metrics_path)
        sys.exit(1)
    else:
        logger.info("All models trained successfully.")


if __name__ == "__main__":
    main()
