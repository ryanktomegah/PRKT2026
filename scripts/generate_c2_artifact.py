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
        help="Synthetic training sample count when --corpus is not provided.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Optional DGEN C2 corpus JSON path. When provided, --n-samples is ignored.",
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
    parser.add_argument(
        "--min-auc",
        type=float,
        default=0.70,
        help="Fail if the trained model AUC is below this gate.",
    )
    parser.add_argument(
        "--require-stress-pass",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail without writing a model artifact if the Tier-3 stress gate fails.",
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

    if args.corpus is not None:
        logger.info("Loading C2 training corpus: %s", args.corpus)
        with args.corpus.open(encoding="utf-8") as fh:
            records = json.load(fh)
        corpus_source = str(args.corpus)
    else:
        logger.info(
            "Generating synthetic C2 training corpus: samples=%d seed=%d",
            args.n_samples,
            args.seed,
        )
        records = generate_pd_training_data(n_samples=args.n_samples, seed=args.seed)
        corpus_source = "lip.c2_pd_model.synthetic_data.generate_pd_training_data"

    if not isinstance(records, list) or not records:
        raise SystemExit("C2 corpus must be a non-empty JSON list of records.")

    model, metrics = PDTrainingPipeline(
        TrainingConfig(
            n_trials=args.n_trials,
            n_models=args.n_models,
            random_seed=args.seed,
        )
    ).run(records)

    auc = float(metrics.get("auc", 0.0))
    stress_test_passed = bool(metrics.get("stress_test_passed", True))
    auc_passed = auc >= args.min_auc
    stress_gate_passed = (not args.require_stress_pass) or stress_test_passed
    status = "ok" if auc_passed and stress_gate_passed else "failed"

    model_path = args.output_dir / "c2_model.pkl"
    report_path = args.output_dir / "c2_training_report.json"

    report = {
        "component": "C2",
        "status": status,
        "corpus_source": corpus_source,
        "n_records": len(records),
        "n_trials": args.n_trials,
        "n_models": args.n_models,
        "seed": args.seed,
        "min_auc": args.min_auc,
        "require_stress_pass": args.require_stress_pass,
        "stress_test_passed": stress_test_passed,
        "metrics": {
            k: bool(v) if isinstance(v, bool) else float(v)
            for k, v in metrics.items()
        },
        "artifacts": {
            "model": str(model_path),
            "signature": f"{model_path}.sig",
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Saved C2 training report to %s", report_path)
    if not auc_passed:
        raise SystemExit(f"C2 AUC {auc:.4f} is below gate {args.min_auc:.4f}.")
    if not stress_gate_passed:
        raise SystemExit("C2 Tier-3 stress gate failed; refusing to write signed artifact.")
    model.save(str(model_path))
    logger.info("Saved signed C2 artifact to %s", model_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
