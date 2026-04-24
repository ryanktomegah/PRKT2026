#!/usr/bin/env python3
"""
generate_c2_artifact.py — Train and save a signed C2 PD model artifact.

Usage:
    LIP_MODEL_HMAC_KEY=... PYTHONPATH=. python scripts/generate_c2_artifact.py
    PYTHONPATH=. python scripts/generate_c2_artifact.py \
        --hmac-key-file .secrets/c2_model_hmac_key \
        --output-dir artifacts/c2_trained
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from lip.c2_pd_model.synthetic_data import generate_pd_training_data
from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/c2_trained"),
        help="Directory to write c2_model.pkl and report metadata.",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=1200,
        help="Synthetic training sample count.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=2,
        help="Optuna trial count for the training pipeline.",
    )
    parser.add_argument(
        "--n-models",
        type=int,
        default=2,
        help="Ensemble size for PDModel.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for synthetic data and training.",
    )
    parser.add_argument(
        "--hmac-key-file",
        type=Path,
        default=None,
        help="Optional file containing the secure-pickle HMAC key.",
    )
    return parser.parse_args()


def _load_hmac_key(hmac_key_file: Path | None) -> str:
    if hmac_key_file is not None:
        key = hmac_key_file.read_text(encoding="utf-8").strip()
        os.environ["LIP_MODEL_HMAC_KEY"] = key
    key = os.environ.get("LIP_MODEL_HMAC_KEY", "").strip()
    if len(key.encode("utf-8")) < 32:
        raise SystemExit(
            "LIP_MODEL_HMAC_KEY must be set to at least 32 bytes, or provide --hmac-key-file."
        )
    return key


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger = logging.getLogger("generate_c2_artifact")

    _load_hmac_key(args.hmac_key_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Generating synthetic C2 training corpus: samples=%d seed=%d",
        args.n_samples,
        args.seed,
    )
    records = generate_pd_training_data(n_samples=args.n_samples, seed=args.seed)
    model, metrics = PDTrainingPipeline(
        TrainingConfig(
            n_trials=args.n_trials,
            n_models=args.n_models,
            random_seed=args.seed,
        )
    ).run(records)

    model_path = args.output_dir / "c2_model.pkl"
    report_path = args.output_dir / "c2_training_report.json"
    model.save(str(model_path))

    report = {
        "component": "C2",
        "status": "ok",
        "n_samples": args.n_samples,
        "n_trials": args.n_trials,
        "n_models": args.n_models,
        "seed": args.seed,
        "metrics": {k: float(v) for k, v in metrics.items()},
        "artifacts": {
            "model": str(model_path),
            "signature": f"{model_path}.sig",
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Saved signed C2 artifact to %s", model_path)
    logger.info("Saved C2 training report to %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
