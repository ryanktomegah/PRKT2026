"""train_c1_on_parquet.py — C1 training adapter for production parquet data.

Loads the ISO 20022 synthetic parquet produced by the DGEN production pipeline,
applies column mapping/renaming to match the C1 TrainingPipeline record format,
pre-computes corridor/BIC failure-rate statistics from the *full* corpus (up to
10 M rows) before sampling, then trains C1 via TrainingPipelineTorch.train_torch().

Column mapping applied:
    bic_sender          → sending_bic
    bic_receiver        → receiving_bic
    label           → label (1=RJCT failed payment, 0=successful payment; BLOCK RJCT excluded)
    timestamp_utc (ISO) → timestamp (float, Unix epoch)
    corridor            → corridor_stats.failure_rate_{7d,30d}  (full-corpus rate)
    bic_sender          → sender_stats.failure_rate_30d          (full-corpus rate)
    bic_receiver        → receiver_stats.failure_rate_30d        (full-corpus rate)

Pass-through columns (no rename needed):
    currency_pair, amount_usd, uetr, rejection_code

Usage
-----
# Smoke test (fast, ~60s)
PYTHONPATH=. python scripts/train_c1_on_parquet.py \\
    --parquet artifacts/production_data_10m/payments_synthetic.parquet \\
    --sample 5000 --epochs 2

# Full production run
PYTHONPATH=. python scripts/train_c1_on_parquet.py \\
    --parquet artifacts/production_data_10m/payments_synthetic.parquet \\
    --sample 1000000 --epochs 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import torch

# Import dynamically so the filter stays in sync as the taxonomy evolves.
# Any code added to BLOCK in rejection_taxonomy.py is automatically excluded
# from C1 training — no manual list maintenance required.
from lip.c3_repayment_engine.rejection_taxonomy import is_dispute_block

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_c1_on_parquet")

# ---------------------------------------------------------------------------
# Parquet → records adapter
# ---------------------------------------------------------------------------


def _load_corridor_rates_from_synthesis_params(params_path: str) -> dict:
    """Load authoritative corridor failure rates from synthesis_parameters.json.

    The parquet contains only RJCT events, so computing failure rates from
    it yields the Class A fraction (~35% uniformly) — not the probability
    a payment attempt fails. The true per-corridor rates (8–28%) live in
    synthesis_parameters.json and must be used instead.

    Corridor names in the params file use slashes ("EUR/USD"); the parquet
    uses hyphens ("EUR-USD"). This function normalises to hyphen format.

    Returns an empty dict if the file is not found (caller falls back to
    the parquet-computed rates with a warning).
    """
    p = Path(params_path)
    if not p.exists():
        return {}
    with open(p) as fh:
        params = json.load(fh)
    rates = {}
    for corridor in params.get("corridors", []):
        name_hyphen = corridor["name"].replace("/", "-")
        rates[name_hyphen] = corridor["failure_rate"]
    return rates


def load_parquet_as_records(
    path: str,
    sample_n: int = 1_000_000,
    seed: int = 42,
    synthesis_params_path: str | None = None,
) -> List[dict]:
    """Load and adapt the DGEN parquet to the C1 TrainingPipeline record format.

    Corridor failure rates are loaded from ``synthesis_parameters.json``
    (the authoritative BIS/CPMI-calibrated values) rather than computed
    from the parquet.  Computing from the parquet yields ~35% uniformly
    for every corridor because the parquet contains only RJCT events and
    ``is_permanent_failure`` measures Class A fraction, not payment failure
    probability.

    BIC failure rates are still computed from the full corpus before sampling.

    Parameters
    ----------
    path:
        Path to ``payments_synthetic.parquet``.
    sample_n:
        Maximum number of records to pass to the training pipeline.
        Set to 0 or None to use the full corpus.
    seed:
        Random seed for reproducible sampling.
    synthesis_params_path:
        Path to ``synthesis_parameters.json``.  Defaults to
        ``<parquet_dir>/synthesis_parameters.json``.

    Returns
    -------
    List[dict]
        Records in C1 TrainingPipeline format.
    """
    t0 = time.perf_counter()
    logger.info("Reading parquet: %s", path)
    df = pd.read_parquet(path)
    logger.info(
        "Loaded %d rows × %d cols in %.1f s",
        len(df), len(df.columns), time.perf_counter() - t0,
    )

    # ------------------------------------------------------------------
    # Step 1 — Load authoritative corridor failure rates from
    # synthesis_parameters.json (BIS/CPMI-calibrated, 8–28% range).
    # Fall back to parquet-computed rates only if the file is missing.
    # ------------------------------------------------------------------
    if synthesis_params_path is None:
        synthesis_params_path = str(Path(path).parent / "synthesis_parameters.json")

    corridor_rates = _load_corridor_rates_from_synthesis_params(synthesis_params_path)
    if corridor_rates:
        logger.info(
            "Corridor failure rates loaded from synthesis_parameters.json: "
            "%d corridors (range %.0f%%–%.0f%%)",
            len(corridor_rates),
            min(corridor_rates.values()) * 100,
            max(corridor_rates.values()) * 100,
        )
    else:
        logger.warning(
            "synthesis_parameters.json not found at %s — "
            "falling back to parquet-computed corridor rates (will be ~35%% uniformly, "
            "carrying no discriminating signal). Generate the parquet with "
            "run_production_pipeline.py to get the params file.",
            synthesis_params_path,
        )
        corridor_rates = df.groupby("corridor")["is_permanent_failure"].mean().to_dict()

    # ------------------------------------------------------------------
    # Step 1b — Filter BLOCK-class rejection codes BEFORE computing BIC
    # stats. These codes are intercepted before C1 at inference (early
    # exit in pipeline.py). Training on them teaches C1 a decision
    # boundary that doesn't exist in production.
    # The filter uses is_dispute_block() so it stays in sync with
    # rejection_taxonomy.py automatically — no manual list maintenance.
    # Currently: DISP, FRAU, FRAD, DUPL, DNOR, LEGL
    # ------------------------------------------------------------------
    n_before = len(df)
    block_mask = df["rejection_code"].apply(
        lambda c: is_dispute_block(str(c)) if pd.notna(c) else False
    )
    df = df[~block_mask].reset_index(drop=True)
    n_filtered = n_before - len(df)
    logger.info(
        "BLOCK filter: removed %d records (%.1f%% of corpus) — "
        "rejection codes: %s",
        n_filtered,
        100.0 * n_filtered / n_before,
        sorted(df["rejection_code"].dropna().unique().tolist())[:5],  # sample for log
    )

    # BIC-level failure rates are computed from the mixed corpus (successes + RJCT).
    # df["label"] = 1 for RJCT events, 0 for successes — so groupby mean gives
    # the actual per-BIC failure rate (fraction of failed payment attempts).
    # This is the correct, calibrated signal: better than the previous proxy
    # (Class A fraction from is_permanent_failure).
    logger.info("Computing BIC failure rates from filtered %d-row corpus…", len(df))
    bic_send_rates: dict = df.groupby("bic_sender")["label"].mean().to_dict()
    bic_recv_rates: dict = df.groupby("bic_receiver")["label"].mean().to_dict()
    logger.info(
        "Stats computed: %d corridors, %d sending BICs, %d receiving BICs",
        len(corridor_rates), len(bic_send_rates), len(bic_recv_rates),
    )

    # ------------------------------------------------------------------
    # Step 2 — Sample (memory-safe: full corpus freed after this point)
    # ------------------------------------------------------------------
    full_n = len(df)
    if sample_n and len(df) > sample_n:
        df = df.sample(n=sample_n, random_state=seed).reset_index(drop=True)
        logger.info("Sampled %d / %d records (seed=%d)", len(df), full_n, seed)

    # ------------------------------------------------------------------
    # Step 3 — Column renames and type coercions
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Label: Option C — use df["label"] directly from the mixed corpus.
    #
    # DGEN generates both successful payments (label=0) and RJCT events
    # (label=1). After the BLOCK filter above, the remaining corpus is:
    #   - Successful payments: label=0 (natural negative class)
    #   - Non-BLOCK RJCT events: label=1 (positive class — LIP bridges)
    #
    # This is ground-truth labelling: C1 learns to separate real failures
    # from real successes, not a proxy class. No computation needed.
    # ------------------------------------------------------------------
    n_pos = int((df["label"] == 1).sum())
    n_neg = int((df["label"] == 0).sum())
    logger.info(
        "Label distribution (Option C, mixed corpus): "
        "%d pos (RJCT) / %d neg (success) — ratio %.2f:1",
        n_pos, n_neg, (n_pos / n_neg) if n_neg > 0 else float("inf"),
    )
    if n_neg == 0:
        raise RuntimeError(
            "Label is degenerate: 0 negative examples (no success records found). "
            "Regenerate the parquet with generate_payments(success_multiplier > 0). "
            "The existing 10M RJCT-only parquet must be replaced."
        )
    if n_pos == 0:
        raise RuntimeError(
            "Label is degenerate: 0 positive examples (all records are successes). "
            "Check the BLOCK filter and parquet contents."
        )

    df = df.rename(
        columns={
            "bic_sender": "sending_bic",
            "bic_receiver": "receiving_bic",
        }
    )

    # timestamp_utc (ISO 8601 string) → float Unix timestamp
    # format='ISO8601' handles both with and without fractional seconds
    ts = pd.to_datetime(df["timestamp_utc"], format="ISO8601", utc=True)
    df["timestamp"] = ts.astype("int64") / 1e9

    # Convenience time fields (not required by C1 but useful for debugging)
    df["hour_of_day"] = ts.dt.hour
    df["day_of_week"] = ts.dt.dayofweek

    # Top-level corridor_failure_rate (informational; also embedded below)
    df["corridor_failure_rate"] = (
        df["corridor"].map(corridor_rates).fillna(0.0)
    )

    # ------------------------------------------------------------------
    # Step 4 — Inject pre-computed stats into per-record sub-dicts
    # features.py reads corridor_stats / sender_stats / receiver_stats;
    # embedding the full-corpus rates here ensures they flow through
    # TabularFeatureEngineer.extract() even though the graph is built
    # from the sample only.
    # ------------------------------------------------------------------
    corridor_stats_col = df["corridor"].map(
        lambda c: {
            "failure_rate_7d": corridor_rates.get(c, 0.0),
            "failure_rate_30d": corridor_rates.get(c, 0.0),
        }
    )
    sender_stats_col = df["sending_bic"].map(
        lambda b: {"failure_rate_30d": bic_send_rates.get(b, 0.0)}
    )
    receiver_stats_col = df["receiving_bic"].map(
        lambda b: {"failure_rate_30d": bic_recv_rates.get(b, 0.0)}
    )
    df["corridor_stats"] = corridor_stats_col
    df["sender_stats"] = sender_stats_col
    df["receiver_stats"] = receiver_stats_col

    records = df.to_dict("records")
    logger.info("Adapter complete: %d records ready for C1 pipeline", len(records))
    return records


# ---------------------------------------------------------------------------
# AUC helper (reused from training.py — avoid circular import)
# ---------------------------------------------------------------------------


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
    auc = float(_trapz(tpr_vals, fpr_vals))
    return max(0.0, min(1.0, abs(auc)))


# ---------------------------------------------------------------------------
# Main training orchestrator
# ---------------------------------------------------------------------------


def train(
    parquet_path: str,
    sample_n: int,
    n_epochs: int,
    seed: int,
    output_dir: str,
) -> None:
    """End-to-end: load parquet → adapt → train C1 → save checkpoint + metrics."""
    # Avoid LightGBM+PyTorch BLAS deadlock on macOS (see CLAUDE.md)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)

    from lip.c1_failure_classifier.training import TrainingConfig
    from lip.c1_failure_classifier.training_torch import TrainingPipelineTorch

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # ---------- Load and adapt parquet ----------
    records = load_parquet_as_records(parquet_path, sample_n=sample_n, seed=seed)

    # ---------- Configure training ----------
    config = TrainingConfig(
        n_epochs=n_epochs,
        batch_size=256,
        learning_rate=1e-3,
        alpha=0.7,
        k_neighbors_train=10,
        k_neighbors_infer=5,
        val_split=0.2,
        random_seed=seed,
    )
    pipeline = TrainingPipelineTorch(config=config)

    # ---------- Train ----------
    t_train_start = time.perf_counter()
    logger.info("Starting train_torch on %d records, %d epochs…", len(records), n_epochs)
    model = pipeline.train_torch(records)
    train_elapsed = time.perf_counter() - t_train_start
    logger.info("train_torch complete in %.1f s", train_elapsed)

    # ---------- Compute val AUC from model ----------
    # Re-run stages 1–4 to get validation split for metrics
    from lip.c1_failure_classifier.training import TrainingPipeline

    np_pipeline = TrainingPipeline(config=config)
    validated = np_pipeline.stage1_data_validation(records)
    graph = np_pipeline.stage2_graph_construction(validated)
    X, y, bics = np_pipeline.stage3_feature_extraction(validated, graph)
    X_train, X_val, y_train, y_val, bic_train, bic_val = np_pipeline.stage4_train_val_split(
        X, y, bics
    )

    model.eval()
    import torch as _torch
    with _torch.no_grad():
        node_feat = _torch.tensor(X_val[:, :8], dtype=_torch.float32)
        tab_feat = _torch.tensor(X_val[:, 8:], dtype=_torch.float32)
        logits = model(node_feat, tab_feat, None).squeeze(1)
        scores = _torch.sigmoid(logits).cpu().numpy()
    val_auc = _compute_auc(y_val, scores)
    logger.info("Validation AUC: %.4f", val_auc)

    # F2-optimal threshold
    best_f2, best_thresh = 0.0, 0.5
    for thresh in np.linspace(0.05, 0.95, 91):
        preds = (scores >= thresh).astype(int)
        tp = float(np.sum((preds == 1) & (y_val == 1)))
        fp = float(np.sum((preds == 1) & (y_val == 0)))
        fn = float(np.sum((preds == 0) & (y_val == 1)))
        prec = tp / (tp + fp + 1e-9)
        rec = tp / (tp + fn + 1e-9)
        f2 = (5 * prec * rec) / (4 * prec + rec + 1e-9)
        if f2 > best_f2:
            best_f2, best_thresh = f2, float(thresh)
    logger.info("F2-optimal threshold: %.3f  (F2=%.4f)", best_thresh, best_f2)

    # ECE (10-bin calibration error)
    n_bins = 10
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n_val = len(y_val)
    for i in range(n_bins):
        mask = (scores >= bin_boundaries[i]) & (scores < bin_boundaries[i + 1])
        if mask.sum() == 0:
            continue
        avg_conf = scores[mask].mean()
        avg_acc = y_val[mask].mean()
        ece += (mask.sum() / n_val) * abs(avg_conf - avg_acc)
    logger.info("ECE (10-bin): %.4f", ece)

    # ---------- Save checkpoint ----------
    ckpt_path = output / "c1_model_parquet.pt"
    _torch.save(model.state_dict(), ckpt_path)
    logger.info("Checkpoint saved: %s", ckpt_path)

    # ---------- Save metrics ----------
    metrics = {
        "val_auc": round(val_auc, 6),
        "f2_threshold": round(best_thresh, 4),
        "f2_score": round(best_f2, 6),
        "ece": round(ece, 6),
        "n_records": len(records),
        "n_epochs": n_epochs,
        "train_elapsed_s": round(train_elapsed, 1),
        "parquet_path": parquet_path,
        "sample_n": sample_n,
        "seed": seed,
    }
    metrics_path = output / "train_metrics_parquet.json"
    with open(metrics_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    logger.info("Metrics saved: %s", metrics_path)

    print("\n===== C1 Training Complete =====")
    print(f"  val_AUC      : {val_auc:.4f}")
    print(f"  F2 threshold : {best_thresh:.3f}  (F2={best_f2:.4f})")
    print(f"  ECE          : {ece:.4f}")
    print(f"  elapsed      : {train_elapsed:.1f} s")
    print(f"  checkpoint   : {ckpt_path}")
    print(f"  metrics      : {metrics_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train C1 failure classifier on production parquet data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--parquet",
        default="artifacts/production_data_10m/payments_synthetic.parquet",
        help="Path to payments_synthetic.parquet from DGEN production pipeline.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=1_000_000,
        help="Number of records to sample for training (0 = full corpus).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        help="Joint training epochs (stages 5–7).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling and training.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory for checkpoint and metrics output.",
    )
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    args = _parse_args(argv)

    parquet = Path(args.parquet)
    if not parquet.exists():
        logger.error("Parquet not found: %s", parquet)
        logger.error(
            "Generate it first with:\n"
            "  PYTHONPATH=. python -m lip.dgen.run_production_pipeline "
            "--output-dir artifacts/production_data_10m "
            "--n-payments 10000000 --n-aml 500000 --seed 42"
        )
        return 1

    train(
        parquet_path=str(parquet),
        sample_n=args.sample,
        n_epochs=args.epochs,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
