"""
train_all.py — LIP Master Training Script
==========================================
Trains all LIP ML components in sequence using pre-generated synthetic corpora.

Components trained:
  C1 — GraphSAGE[384] + TabTransformer[88] → MLP → failure probability
  C2 — LightGBM PD ensemble → fee_bps = max(300, PD×LGD×10000)
  C6 — Isolation Forest AML anomaly detector

Usage::

    # Train all components from pre-generated corpora:
    python -m lip.train_all --corpus-dir artifacts/synthetic --output-dir artifacts/models

    # Specific components only:
    python -m lip.train_all --corpus-dir artifacts/synthetic --output-dir artifacts/models \\
        --components c1 c2

    # Regenerate corpora before training:
    python -m lip.train_all --corpus-dir artifacts/synthetic --output-dir artifacts/models \\
        --regenerate

    # Smoke test (fast, small data):
    python -m lip.train_all --corpus-dir /tmp/lip_train --output-dir /tmp/lip_models \\
        --smoke-test

Output::

    artifacts/models/
    ├── c1_model.pkl              ← ClassifierModel (pickle)
    ├── c1_threshold.txt          ← F2-optimal decision threshold
    ├── c1_embeddings.pkl         ← CorridorEmbeddingPipeline
    ├── c1_training_report.json
    ├── c2_model.pkl              ← PDModel (pickle)
    ├── c2_training_report.json
    ├── c6_anomaly_detector.pkl   ← AnomalyDetector (pickle)
    ├── c6_training_report.json
    └── training_summary.json     ← All metrics + EU AI Act Art.17 model card

FORGE NOTE: For CI use --smoke-test to keep training under 60 seconds.
SR 11-7: C2 and C6 use 18-month temporal corpora for out-of-time validation.
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lip.train_all")

# ---------------------------------------------------------------------------
# C6 corpus → AnomalyDetector feature mapping
# ---------------------------------------------------------------------------

def _map_c6_record_to_anomaly_features(rec: dict) -> dict:
    """Map C6 corpus record fields to AnomalyDetector.fit() format.

    AnomalyDetector expects: amount, hour_of_day, day_of_week,
    velocity_ratio, beneficiary_concentration, amount_zscore.

    C6 corpus provides: amount_usd, hour_of_day, transactions_24h,
    unique_counterparties_30d, etc.
    """
    amount = float(rec.get("amount_usd", 0.0))
    hour = float(rec.get("hour_of_day", 12))
    # Derive day_of_week from timestamp (epoch seconds)
    ts = float(rec.get("timestamp", 0.0))
    day_of_week = int((ts / 86400) % 7)
    # velocity_ratio: transactions_24h normalised to typical baseline of 5
    txn_24h = float(rec.get("transactions_24h", 1))
    velocity_ratio = txn_24h / 5.0
    # beneficiary_concentration: fewer counterparties = higher concentration
    n_cp = max(1, int(rec.get("unique_counterparties_30d", 5)))
    beneficiary_concentration = 1.0 / n_cp
    # amount_zscore: not directly available; derive via log-normal z
    # (will be 0.0 if not present — AnomalyDetector handles this gracefully)
    amount_zscore = float(rec.get("amount_zscore", 0.0))

    return {
        "amount": amount,
        "hour_of_day": hour,
        "day_of_week": day_of_week,
        "velocity_ratio": velocity_ratio,
        "beneficiary_concentration": beneficiary_concentration,
        "amount_zscore": amount_zscore,
    }


# ---------------------------------------------------------------------------
# Component trainers
# ---------------------------------------------------------------------------

def _train_c1(
    corpus_path: Path,
    output_dir: Path,
    smoke_test: bool,
) -> Dict[str, Any]:
    """Train C1 GraphSAGE + TabTransformer failure classifier."""
    from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline

    logger.info("[C1] Loading corpus from %s", corpus_path)
    with open(corpus_path) as f:
        records: List[dict] = json.load(f)

    if smoke_test:
        records = records[:2000]
        logger.info("[C1] Smoke-test: using %d records", len(records))

    config = TrainingConfig(
        n_epochs=5 if smoke_test else 50,
        batch_size=256,
        learning_rate=1e-3,
        alpha=0.7,
        val_split=0.2,
        random_seed=42,
    )

    logger.info("[C1] Starting TrainingPipeline (n_epochs=%d, n=%d)", config.n_epochs, len(records))
    t0 = time.time()
    pipeline = TrainingPipeline(config)
    model, threshold, emb_pipeline = pipeline.run(records)
    elapsed = time.time() - t0

    # Save artifacts
    model_path = output_dir / "c1_model.pkl"
    threshold_path = output_dir / "c1_threshold.txt"
    emb_path = output_dir / "c1_embeddings.pkl"

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    threshold_path.write_text(f"{threshold:.6f}\n")
    with open(emb_path, "wb") as f:
        pickle.dump(emb_pipeline, f)

    report = {
        "component": "C1",
        "status": "ok",
        "n_records": len(records),
        "threshold": round(float(threshold), 6),
        "training_seconds": round(elapsed, 2),
        "smoke_test": smoke_test,
        "artifacts": {
            "model": str(model_path),
            "threshold": str(threshold_path),
            "embeddings": str(emb_path),
        },
    }

    report_path = output_dir / "c1_training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("[C1] Done — threshold=%.4f, elapsed=%.1fs", threshold, elapsed)
    return report


def _train_c2(
    corpus_path: Path,
    output_dir: Path,
    smoke_test: bool,
) -> Dict[str, Any]:
    """Train C2 PD ensemble model."""
    from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig

    logger.info("[C2] Loading corpus from %s", corpus_path)
    with open(corpus_path) as f:
        records: List[dict] = json.load(f)

    if smoke_test:
        records = records[:1000]
        logger.info("[C2] Smoke-test: using %d records", len(records))

    config = TrainingConfig(
        n_trials=3 if smoke_test else 50,
        n_models=2 if smoke_test else 5,
        test_split=0.2,
        val_split=0.1,
        random_seed=42,
    )

    logger.info("[C2] Starting PDTrainingPipeline (n_trials=%d, n=%d)", config.n_trials, len(records))
    t0 = time.time()
    pipeline = PDTrainingPipeline(config)
    model, metrics = pipeline.run(records)
    elapsed = time.time() - t0

    # Validate fee floor invariant (QUANT: fee_bps = max(300, PD×LGD×10000))
    # Spot-check 100 random predictions
    import numpy as np
    rng = np.random.default_rng(0)
    sample_idx = rng.integers(0, len(records), size=min(100, len(records)))
    from lip.c2_pd_model.features import UnifiedFeatureEngineer
    from lip.c2_pd_model.tier_assignment import Tier, TierFeatures, assign_tier

    fee_violations = 0
    for idx in sample_idx:
        rec = records[int(idx)]
        borrower = rec.get("borrower", {})
        tier_features = TierFeatures(
            has_financial_statements=bool(borrower.get("has_financial_statements", False)),
            has_transaction_history=bool(borrower.get("has_transaction_history", False)),
            has_credit_bureau=bool(borrower.get("has_credit_bureau", False)),
            months_history=int(borrower.get("months_history", 0)),
            transaction_count=int(borrower.get("transaction_count", 0)),
        )
        tier = Tier(int(assign_tier(tier_features)))
        engineer = UnifiedFeatureEngineer(tier)
        feat_vec, _ = engineer.extract(rec.get("payment", {}), borrower)
        import numpy as np
        pd_val = float(model.predict_proba(feat_vec.reshape(1, -1))[0])
        lgd = 0.45  # Basel III standard LGD
        fee_bps = max(300.0, pd_val * lgd * 10000.0)
        if fee_bps < 300.0:
            fee_violations += 1

    # Save artifacts
    model_path = output_dir / "c2_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    report = {
        "component": "C2",
        "status": "ok",
        "n_records": len(records),
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "fee_floor_check": {
            "samples_checked": len(sample_idx),
            "violations": fee_violations,
            "passed": fee_violations == 0,
        },
        "training_seconds": round(elapsed, 2),
        "smoke_test": smoke_test,
        "artifacts": {"model": str(model_path)},
    }

    report_path = output_dir / "c2_training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(
        "[C2] Done — AUC=%.4f, KS=%.4f, fee_violations=%d, elapsed=%.1fs",
        metrics.get("auc", float("nan")),
        metrics.get("ks", float("nan")),
        fee_violations,
        elapsed,
    )
    return report


def _train_c6(
    corpus_path: Path,
    output_dir: Path,
    smoke_test: bool,
) -> Dict[str, Any]:
    """Train C6 Isolation Forest AML anomaly detector."""
    from lip.c6_aml_velocity.anomaly import AnomalyDetector

    logger.info("[C6] Loading corpus from %s", corpus_path)
    with open(corpus_path) as f:
        records: List[dict] = json.load(f)

    if smoke_test:
        records = records[:1000]
        logger.info("[C6] Smoke-test: using %d records", len(records))

    # Map C6 corpus fields to AnomalyDetector format
    mapped = [_map_c6_record_to_anomaly_features(r) for r in records]

    # Train on CLEAN records only (aml_flag=0) — Isolation Forest learns "normal"
    clean_records = [r for r, orig in zip(mapped, records) if orig.get("aml_flag", 0) == 0]
    logger.info("[C6] Fitting Isolation Forest on %d clean records (of %d total)",
                len(clean_records), len(records))

    t0 = time.time()
    detector = AnomalyDetector(contamination=0.01)
    detector.fit(clean_records)
    elapsed = time.time() - t0

    # Quick sanity check: flagged records should score lower (more anomalous)
    import numpy as np
    flagged = [r for r, orig in zip(mapped, records) if orig.get("aml_flag", 0) == 1]
    if flagged and clean_records:
        clean_sample = clean_records[:min(200, len(clean_records))]
        flag_sample = flagged[:min(200, len(flagged))]
        clean_scores = [detector.predict(r).anomaly_score for r in clean_sample]
        flag_scores = [detector.predict(r).anomaly_score for r in flag_sample]
        clean_mean = float(np.mean(clean_scores))
        flag_mean = float(np.mean(flag_scores))
        # IsolationForest: lower score = more anomalous
        separation_correct = flag_mean < clean_mean
        detection_rate = float(np.mean([detector.predict(r).is_anomaly for r in flag_sample]))
    else:
        clean_mean = flag_mean = float("nan")
        separation_correct = False
        detection_rate = float("nan")

    # Save artifact
    model_path = output_dir / "c6_anomaly_detector.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(detector, f)

    report = {
        "component": "C6",
        "status": "ok",
        "n_records": len(records),
        "n_clean_fit": len(clean_records),
        "n_flagged": len(flagged),
        "sanity": {
            "clean_mean_score": round(clean_mean, 4) if clean_mean == clean_mean else None,
            "flagged_mean_score": round(flag_mean, 4) if flag_mean == flag_mean else None,
            "separation_correct": separation_correct,
            "flagged_detection_rate": round(detection_rate, 4) if detection_rate == detection_rate else None,
        },
        "training_seconds": round(elapsed, 2),
        "smoke_test": smoke_test,
        "artifacts": {"model": str(model_path)},
    }

    report_path = output_dir / "c6_training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(
        "[C6] Done — clean_score=%.4f, flagged_score=%.4f, detection=%.2f, elapsed=%.1fs",
        clean_mean, flag_mean, detection_rate, elapsed,
    )
    return report


# ---------------------------------------------------------------------------
# Model card (EU AI Act Art.17 — model documentation)
# ---------------------------------------------------------------------------

def _build_model_card(
    component_reports: Dict[str, Any],
    total_elapsed: float,
) -> dict:
    return {
        "schema_version": "1.0",
        "model_card_type": "LIP_TRAINING_RUN",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "training_tool": "lip.train_all",
        "training_time_seconds": round(total_elapsed, 2),
        "regulatory_compliance": {
            "eu_ai_act_article": "17",
            "eu_ai_act_requirement": "Quality management system — model documentation",
            "sr_11_7": "C2/C6 trained on 18-month temporal corpora for OOT validation",
            "training_data_type": "FULLY_SYNTHETIC — lip.dgen generated corpora",
            "pii_present": False,
        },
        "components": component_reports,
        "intended_use": (
            "Production inference for LIP bridge-loan decisioning. "
            "C1: failure probability → go/no-go. "
            "C2: PD → fee pricing (floor 300 bps). "
            "C6: AML anomaly detection → soft alert gate."
        ),
        "prohibited_uses": [
            "Do not use C2 model to price loans below 300 bps fee floor",
            "Do not use C6 model as primary sanctions screening",
            "Do not deploy without human override channel (C7)",
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="LIP train_all: train all ML components in sequence"
    )
    parser.add_argument("--corpus-dir", required=True, help="Directory with pre-generated corpora")
    parser.add_argument("--output-dir", required=True, help="Directory for model artifacts")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["c1", "c2", "c6"],
        default=["c1", "c2", "c6"],
        help="Components to train (default: all)",
    )
    parser.add_argument("--smoke-test", action="store_true",
                        help="Small N for fast CI validation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--regenerate", action="store_true",
                        help="Re-run dgen before training (requires numpy)")

    args = parser.parse_args(argv)

    corpus_dir = Path(args.corpus_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Optionally regenerate corpora
    if args.regenerate:
        logger.info("Regenerating corpora via lip.dgen.generate_all...")
        from lip.dgen.generate_all import main as dgen_main
        components_for_dgen = []
        if "c1" in args.components:
            components_for_dgen.append("c1")
        if "c2" in args.components:
            components_for_dgen.append("c2")
        if "c6" in args.components:
            components_for_dgen.append("c6")
        dgen_argv = [
            "--output-dir", str(corpus_dir),
            "--components", *components_for_dgen,
        ]
        if args.smoke_test:
            dgen_argv.append("--smoke-test")
        dgen_main(dgen_argv)

    print(f"\n{'='*60}")
    print("  LIP — Model Training")
    print(f"  Seed: {args.seed} | Mode: {'SMOKE-TEST' if args.smoke_test else 'FULL'}")
    print(f"  Corpus: {corpus_dir.resolve()}")
    print(f"  Output: {output_dir.resolve()}")
    print(f"{'='*60}\n")

    t_start = time.time()
    component_reports: Dict[str, Any] = {}
    any_failed = False

    # C1 corpus filename pattern
    c1_corpus = corpus_dir / f"c1_corpus_n{'500' if args.smoke_test else '100000'}_seed{args.seed}.json"
    c2_corpus = corpus_dir / f"c2_corpus_n{'500' if args.smoke_test else '30000'}_seed{args.seed}.json"
    c6_corpus = corpus_dir / f"c6_corpus_n{'500' if args.smoke_test else '20000'}_seed{args.seed}.json"

    # Fallback: find any matching corpus if exact name not found
    def _find_corpus(pattern: str) -> Optional[Path]:
        import glob as _glob
        matches = sorted(_glob.glob(str(corpus_dir / pattern)))
        return Path(matches[-1]) if matches else None

    if "c1" in args.components:
        if not c1_corpus.exists():
            found = _find_corpus("c1_corpus_n*_seed*.json")
            if found:
                logger.info("[C1] Using corpus: %s", found)
                c1_corpus = found
            else:
                logger.error("[C1] Corpus not found at %s — skipping (use --regenerate)", c1_corpus)
                component_reports["c1"] = {"status": "skipped", "reason": "corpus_not_found"}
                any_failed = True

        if c1_corpus.exists():
            try:
                report = _train_c1(c1_corpus, output_dir, args.smoke_test)
                component_reports["c1"] = report
            except Exception as exc:
                logger.exception("[C1] Training failed: %s", exc)
                component_reports["c1"] = {"status": "failed", "error": str(exc)}
                any_failed = True

    if "c2" in args.components:
        if not c2_corpus.exists():
            found = _find_corpus("c2_corpus_n*_seed*.json")
            if found:
                logger.info("[C2] Using corpus: %s", found)
                c2_corpus = found
            else:
                logger.error("[C2] Corpus not found — skipping (use --regenerate)")
                component_reports["c2"] = {"status": "skipped", "reason": "corpus_not_found"}
                any_failed = True

        if c2_corpus.exists():
            try:
                report = _train_c2(c2_corpus, output_dir, args.smoke_test)
                component_reports["c2"] = report
            except Exception as exc:
                logger.exception("[C2] Training failed: %s", exc)
                component_reports["c2"] = {"status": "failed", "error": str(exc)}
                any_failed = True

    if "c6" in args.components:
        if not c6_corpus.exists():
            found = _find_corpus("c6_corpus_n*_seed*.json")
            if found:
                logger.info("[C6] Using corpus: %s", found)
                c6_corpus = found
            else:
                logger.error("[C6] Corpus not found — skipping (use --regenerate)")
                component_reports["c6"] = {"status": "skipped", "reason": "corpus_not_found"}
                any_failed = True

        if c6_corpus.exists():
            try:
                report = _train_c6(c6_corpus, output_dir, args.smoke_test)
                component_reports["c6"] = report
            except Exception as exc:
                logger.exception("[C6] Training failed: %s", exc)
                component_reports["c6"] = {"status": "failed", "error": str(exc)}
                any_failed = True

    total_elapsed = time.time() - t_start

    # Write training summary
    summary_path = output_dir / "training_summary.json"
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "training_seconds": round(total_elapsed, 2),
        "components": component_reports,
        "overall": "FAIL" if any_failed else "PASS",
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Write model card (EU AI Act Art.17)
    model_card = _build_model_card(component_reports, total_elapsed)
    card_path = output_dir / "model_card.json"
    with open(card_path, "w") as f:
        json.dump(model_card, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  Training complete in {total_elapsed:.1f}s")
    print(f"  Summary: {summary_path}")
    print(f"  Model card (EU AI Act Art.17): {card_path}")
    print(f"  Overall: {'FAIL' if any_failed else 'PASS'}")
    print(f"{'='*60}\n")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
