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

    # -----------------------------------------------------------------------
    # Comprehensive stats from full corpus (post-BLOCK filter, pre-sample)
    # All 88 tabular features in features.py read from these dicts; leaving
    # any key missing produces a structural zero for the entire training run.
    # -----------------------------------------------------------------------
    logger.info("Computing comprehensive stats from filtered %d-row corpus…", len(df))

    global_failure_rate = float(df["label"].mean())

    # Parse timestamps once for windowed volume computation
    ts_full = pd.to_datetime(df["timestamp_utc"], format="ISO8601", utc=True)
    ts_unix_full = ts_full.astype("int64") / 1e9
    df["_ts"] = ts_unix_full

    # ---- Corridor stats ----
    c_grp = df.groupby("corridor")
    c_ts_max = c_grp["_ts"].max()
    c_ts_min = c_grp["_ts"].min()
    c_tx_count = c_grp["label"].count()
    c_avg = c_grp["amount_usd"].mean()
    c_std = c_grp["amount_usd"].std().fillna(0.0)
    c_max_amt = c_grp["amount_usd"].max()
    c_min_amt = c_grp["amount_usd"].min()
    c_p50 = c_grp["amount_usd"].quantile(0.5)
    c_p95 = c_grp["amount_usd"].quantile(0.95)
    c_ucurr = c_grp["currency_pair"].nunique()
    c_age_days = ((c_ts_max - c_ts_min) / 86400).clip(lower=1.0)
    c_tx_per_day = c_tx_count / c_age_days

    # Windowed volumes via temporary mask columns
    df["_c_ts_max"] = df["corridor"].map(c_ts_max)
    df["_c_in_7d"] = df["_ts"] >= (df["_c_ts_max"] - 7 * 86400)
    df["_c_in_30d"] = df["_ts"] >= (df["_c_ts_max"] - 30 * 86400)
    c_vol_7d = (
        df[df["_c_in_7d"]].groupby("corridor")["amount_usd"].sum()
        .reindex(c_tx_count.index, fill_value=0.0)
    )
    c_vol_30d = (
        df[df["_c_in_30d"]].groupby("corridor")["amount_usd"].sum()
        .reindex(c_tx_count.index, fill_value=0.0)
    )
    c_vel_24h = c_tx_per_day            # avg daily rate ≈ velocity_24h
    c_vel_1h = c_vel_24h / 24.0

    # ---- Sender BIC stats ----
    s_grp = df.groupby("bic_sender")
    s_tx_count = s_grp["label"].count()
    s_fail_rate = s_grp["label"].mean()
    s_avg = s_grp["amount_usd"].mean()
    s_std = s_grp["amount_usd"].std().fillna(0.0)
    s_age_days = ((s_grp["_ts"].max() - s_grp["_ts"].min()) / 86400).clip(lower=1.0)
    s_uniq_recv = s_grp["bic_receiver"].nunique()
    s_vol_24h = s_grp["amount_usd"].sum() / s_age_days
    s_large = (
        df[df["amount_usd"] > 100_000].groupby("bic_sender")["label"].count()
        .reindex(s_tx_count.index, fill_value=0)
    )
    s_pct_large = s_large / s_tx_count
    # Herfindahl currency concentration
    _s_cp = df.groupby(["bic_sender", "currency_pair"]).size().reset_index(name="_n")
    _s_tot = _s_cp.groupby("bic_sender")["_n"].transform("sum")
    _s_cp["_sq"] = (_s_cp["_n"] / _s_tot) ** 2
    s_curr_conc = _s_cp.groupby("bic_sender")["_sq"].sum()
    # in_degree for senders = number of distinct BICs that send TO each BIC
    bic_in_deg = df.groupby("bic_receiver")["bic_sender"].nunique()

    # ---- Receiver BIC stats ----
    r_grp = df.groupby("bic_receiver")
    r_tx_count = r_grp["label"].count()
    r_fail_rate = r_grp["label"].mean()
    r_avg = r_grp["amount_usd"].mean()
    r_std = r_grp["amount_usd"].std().fillna(0.0)
    r_age_days = ((r_grp["_ts"].max() - r_grp["_ts"].min()) / 86400).clip(lower=1.0)
    r_uniq_send = r_grp["bic_sender"].nunique()
    r_vol_24h = r_grp["amount_usd"].sum() / r_age_days
    r_large = (
        df[df["amount_usd"] > 100_000].groupby("bic_receiver")["label"].count()
        .reindex(r_tx_count.index, fill_value=0)
    )
    r_pct_large = r_large / r_tx_count
    _r_cp = df.groupby(["bic_receiver", "currency_pair"]).size().reset_index(name="_n")
    _r_tot = _r_cp.groupby("bic_receiver")["_n"].transform("sum")
    _r_cp["_sq"] = (_r_cp["_n"] / _r_tot) ** 2
    r_curr_conc = _r_cp.groupby("bic_receiver")["_sq"].sum()
    # out_degree for receivers = number of distinct BICs each BIC sends to
    bic_out_deg = s_uniq_recv

    # Windowed failure rates for senders (1d, 7d) — distinct signal for vec[64-66]
    s_ts_max_ser = s_grp["_ts"].max()
    df["_s_ts_max"] = df["bic_sender"].map(s_ts_max_ser)
    df["_s_in_1d"] = df["_ts"] >= (df["_s_ts_max"] - 86400)
    df["_s_in_7d"] = df["_ts"] >= (df["_s_ts_max"] - 7 * 86400)
    s_fail_1d = (
        df[df["_s_in_1d"]].groupby("bic_sender")["label"].mean()
        .reindex(s_tx_count.index)
        .fillna(s_fail_rate)
    )
    s_fail_7d = (
        df[df["_s_in_7d"]].groupby("bic_sender")["label"].mean()
        .reindex(s_tx_count.index)
        .fillna(s_fail_rate)
    )

    # Windowed failure rates for receivers (1d, 7d) — distinct signal for vec[67-69]
    r_ts_max_ser = r_grp["_ts"].max()
    df["_r_ts_max"] = df["bic_receiver"].map(r_ts_max_ser)
    df["_r_in_1d"] = df["_ts"] >= (df["_r_ts_max"] - 86400)
    df["_r_in_7d"] = df["_ts"] >= (df["_r_ts_max"] - 7 * 86400)
    r_fail_1d = (
        df[df["_r_in_1d"]].groupby("bic_receiver")["label"].mean()
        .reindex(r_tx_count.index)
        .fillna(r_fail_rate)
    )
    r_fail_7d = (
        df[df["_r_in_7d"]].groupby("bic_receiver")["label"].mean()
        .reindex(r_tx_count.index)
        .fillna(r_fail_rate)
    )

    # Consecutive failures per BIC — trailing label=1 streak from most recent tx
    # vec[70] (sender), vec[72] (receiver) — previously always 0
    _s_sorted = df[["bic_sender", "_ts", "label"]].sort_values(["bic_sender", "_ts"])
    s_consec = (
        _s_sorted.groupby("bic_sender")["label"]
        .apply(lambda s: int(s.iloc[::-1].cumprod().sum()))
    )
    _r_sorted = df[["bic_receiver", "_ts", "label"]].sort_values(["bic_receiver", "_ts"])
    r_consec = (
        _r_sorted.groupby("bic_receiver")["label"]
        .apply(lambda s: int(s.iloc[::-1].cumprod().sum()))
    )

    # Drop temporary columns and convert to dicts for fast lookup
    df.drop(
        columns=[
            "_ts", "_c_ts_max", "_c_in_7d", "_c_in_30d",
            "_s_ts_max", "_s_in_1d", "_s_in_7d",
            "_r_ts_max", "_r_in_1d", "_r_in_7d",
        ],
        inplace=True,
    )

    c_tx_count_d = c_tx_count.to_dict()
    c_avg_d = c_avg.to_dict()
    c_std_d = c_std.to_dict()
    c_max_d = c_max_amt.to_dict()
    c_min_d = c_min_amt.to_dict()
    c_p50_d = c_p50.to_dict()
    c_p95_d = c_p95.to_dict()
    c_ucurr_d = c_ucurr.to_dict()
    c_age_d = c_age_days.to_dict()
    c_txpd_d = c_tx_per_day.to_dict()
    c_vol7_d = c_vol_7d.to_dict()
    c_vol30_d = c_vol_30d.to_dict()
    c_vel24_d = c_vel_24h.to_dict()
    c_vel1_d = c_vel_1h.to_dict()

    s_fail_d = s_fail_rate.to_dict()
    s_tx_d = s_tx_count.to_dict()
    s_avg_d = s_avg.to_dict()
    s_std_d = s_std.to_dict()
    s_age_d = s_age_days.to_dict()
    s_recv_d = s_uniq_recv.to_dict()
    s_vol24_d = s_vol_24h.to_dict()
    s_pct_d = s_pct_large.to_dict()
    s_conc_d = s_curr_conc.to_dict()
    bic_in_d = bic_in_deg.to_dict()

    r_fail_d = r_fail_rate.to_dict()
    r_tx_d = r_tx_count.to_dict()
    r_avg_d = r_avg.to_dict()
    r_std_d = r_std.to_dict()
    r_age_d = r_age_days.to_dict()
    r_send_d = r_uniq_send.to_dict()
    r_vol24_d = r_vol_24h.to_dict()
    r_pct_d = r_pct_large.to_dict()
    r_conc_d = r_curr_conc.to_dict()
    bic_out_d = bic_out_deg.to_dict()

    s_fail_1d_d = s_fail_1d.to_dict()
    s_fail_7d_d = s_fail_7d.to_dict()
    r_fail_1d_d = r_fail_1d.to_dict()
    r_fail_7d_d = r_fail_7d.to_dict()
    s_consec_d = s_consec.to_dict()
    r_consec_d = r_consec.to_dict()

    logger.info(
        "Stats computed: %d corridors, %d sending BICs, %d receiving BICs",
        len(c_tx_count), len(s_tx_count), len(r_tx_count),
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
    # Step 4 — Inject comprehensive pre-computed stats into per-record
    # sub-dicts.  All 88 tabular features in features.py read from these
    # dicts — filling every key eliminates the ~48-feature structural-zero
    # problem that collapsed AUC to ~0.50.
    # ------------------------------------------------------------------
    def _c_stats(c: str) -> dict:
        fr = corridor_rates.get(c, 0.0)
        return {
            "failure_rate_7d": fr,
            "failure_rate_30d": fr,
            "tx_count": int(c_tx_count_d.get(c, 0)),
            "volume_7d": float(c_vol7_d.get(c, 0.0)),
            "volume_30d": float(c_vol30_d.get(c, 0.0)),
            "avg_amount": float(c_avg_d.get(c, 0.0)),
            "std_amount": float(c_std_d.get(c, 0.0)),
            "max_amount": float(c_max_d.get(c, 0.0)),
            "min_amount": float(c_min_d.get(c, 0.0)),
            "p50_amount": float(c_p50_d.get(c, 0.0)),
            "p95_amount": float(c_p95_d.get(c, 0.0)),
            "unique_currencies": int(c_ucurr_d.get(c, 1)),
            "age_days": float(c_age_d.get(c, 1.0)),
            "tx_per_day": float(c_txpd_d.get(c, 0.0)),
            "velocity_1h": float(c_vel1_d.get(c, 0.0)),
            "velocity_24h": float(c_vel24_d.get(c, 0.0)),
            "consecutive_failures": 0,
        }

    def _s_stats(b: str) -> dict:
        fr = float(s_fail_d.get(b, 0.0))
        return {
            "failure_rate_30d": fr,
            "failure_rate_7d": float(s_fail_7d_d.get(b, fr)),
            "failure_rate_1d": float(s_fail_1d_d.get(b, fr)),
            "tx_count": int(s_tx_d.get(b, 0)),
            "out_degree": int(s_recv_d.get(b, 0)),
            "in_degree": int(bic_in_d.get(b, 0)),
            "volume_24h": float(s_vol24_d.get(b, 0.0)),
            "avg_amount": float(s_avg_d.get(b, 0.0)),
            "std_amount": float(s_std_d.get(b, 0.0)),
            "age_days": float(s_age_d.get(b, 1.0)),
            "currency_concentration": float(s_conc_d.get(b, 0.0)),
            "unique_receivers": int(s_recv_d.get(b, 0)),
            "pct_large_tx": float(s_pct_d.get(b, 0.0)),
            "consecutive_failures": int(s_consec_d.get(b, 0)),
        }

    def _r_stats(b: str) -> dict:
        fr = float(r_fail_d.get(b, 0.0))
        return {
            "failure_rate_30d": fr,
            "failure_rate_7d": float(r_fail_7d_d.get(b, fr)),
            "failure_rate_1d": float(r_fail_1d_d.get(b, fr)),
            "tx_count": int(r_tx_d.get(b, 0)),
            "out_degree": int(bic_out_d.get(b, 0)),
            "in_degree": int(r_send_d.get(b, 0)),
            "volume_24h": float(r_vol24_d.get(b, 0.0)),
            "avg_amount": float(r_avg_d.get(b, 0.0)),
            "std_amount": float(r_std_d.get(b, 0.0)),
            "age_days": float(r_age_d.get(b, 1.0)),
            "currency_concentration": float(r_conc_d.get(b, 0.0)),
            "unique_senders": int(r_send_d.get(b, 0)),
            "pct_large_tx": float(r_pct_d.get(b, 0.0)),
            "consecutive_failures": int(r_consec_d.get(b, 0)),
        }

    df["corridor_stats"] = df["corridor"].map(_c_stats)
    df["sender_stats"] = df["sending_bic"].map(_s_stats)
    df["receiver_stats"] = df["receiving_bic"].map(_r_stats)

    # amount_zscore per corridor (used as FX volatility proxy, features.py vec[78])
    df["amount_zscore"] = (
        (df["amount_usd"] - df["corridor"].map(c_avg_d))
        / (df["corridor"].map(c_std_d).clip(lower=1e-9))
    )
    # global failure rate proxy (features.py vec[73])
    df["global_failure_rate_24h"] = global_failure_rate

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
    timestamps = np.array([float(r.get("timestamp_unix", 0.0)) for r in validated])
    X_train, X_val, y_train, y_val, bic_train, bic_val = np_pipeline.stage4_train_val_split(
        X, y, bics, timestamps
    )

    # Apply the same StandardScaler that was fitted during train_torch
    if pipeline.feature_scaler is not None:
        X_val = pipeline.feature_scaler.transform(X_val)

    model.eval()
    import torch as _torch
    from lip.c1_failure_classifier.training_torch import _build_neighbor_tensor

    # Build val neighbor tensor using the same graph used during training.
    # Passing None here would collapse AUC to ~0.5 because the model was
    # trained with neighbor features — this was the bug in the original eval.
    val_nbr = _build_neighbor_tensor(bic_val, graph, config.k_neighbors_infer)

    with _torch.no_grad():
        node_feat = _torch.tensor(X_val[:, :8], dtype=_torch.float32)
        tab_feat = _torch.tensor(X_val[:, 8:], dtype=_torch.float32)
        logits = model(node_feat, tab_feat, val_nbr).squeeze(1)
        scores_torch = _torch.sigmoid(logits).cpu().numpy()

    # Also evaluate LightGBM component of the ensemble
    lgbm_scores = None
    if hasattr(model, "lgbm_model") and model.lgbm_model is not None:
        lgbm_scores = model.lgbm_model.predict_proba(X_val[:, 8:])[:, 1]
        val_auc_lgbm = _compute_auc(y_val, lgbm_scores)
        logger.info("Validation AUC (LightGBM): %.4f", val_auc_lgbm)

    # Ensemble: 50/50 average of PyTorch and LightGBM scores
    if lgbm_scores is not None:
        scores = 0.5 * scores_torch + 0.5 * lgbm_scores
        val_auc_torch = _compute_auc(y_val, scores_torch)
        val_auc = _compute_auc(y_val, scores)
        logger.info("Validation AUC (PyTorch only): %.4f", val_auc_torch)
        logger.info("Validation AUC (ensemble 50/50): %.4f", val_auc)
    else:
        scores = scores_torch
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

    # ECE (10-bin calibration error) — PRE-calibration
    from lip.c1_failure_classifier.calibration import IsotonicCalibrator, compute_ece

    ece_pre = compute_ece(scores, y_val)
    logger.info("ECE pre-calibration (10-bin): %.4f", ece_pre)

    # ---------- Isotonic calibration (stage 7b) ----------
    # Split val set: first 60% for calibrator fitting, last 40% for ECE eval.
    # This prevents overfitting the calibrator to the same data used to measure ECE.
    n_cal = int(len(y_val) * 0.6)
    cal_scores, eval_scores = scores[:n_cal], scores[n_cal:]
    cal_labels, eval_labels = y_val[:n_cal], y_val[n_cal:]

    calibrator = IsotonicCalibrator()
    calibrator.fit(cal_scores, cal_labels)

    # Measure ECE improvement on held-out eval portion
    calibrated_eval = calibrator.predict(eval_scores)
    ece_post = compute_ece(calibrated_eval, eval_labels)
    logger.info("ECE post-calibration (10-bin): %.4f (was %.4f)", ece_post, ece_pre)

    # Re-compute F2 threshold on calibrated scores (full val set)
    calibrated_all = calibrator.predict(scores)
    best_f2_cal, best_thresh_cal = 0.0, 0.5
    for thresh in np.linspace(0.05, 0.95, 91):
        preds = (calibrated_all >= thresh).astype(int)
        tp = float(np.sum((preds == 1) & (y_val == 1)))
        fp = float(np.sum((preds == 1) & (y_val == 0)))
        fn = float(np.sum((preds == 0) & (y_val == 1)))
        prec = tp / (tp + fp + 1e-9)
        rec = tp / (tp + fn + 1e-9)
        f2 = (5 * prec * rec) / (4 * prec + rec + 1e-9)
        if f2 > best_f2_cal:
            best_f2_cal, best_thresh_cal = f2, float(thresh)
    logger.info(
        "F2 threshold (calibrated): %.3f (F2=%.4f) vs raw: %.3f (F2=%.4f)",
        best_thresh_cal, best_f2_cal, best_thresh, best_f2,
    )
    # Use calibrated threshold as the deployment threshold
    best_thresh = best_thresh_cal
    best_f2 = best_f2_cal

    # ---------- Save F2 threshold to well-known path ----------
    thresh_path = output / "f2_threshold.txt"
    thresh_path.write_text(f"{best_thresh:.4f}\n")
    logger.info("F2 threshold written: %s → %.4f", thresh_path, best_thresh)

    # ---------- Save checkpoint ----------
    ckpt_path = output / "c1_model_parquet.pt"
    _torch.save(model.state_dict(), ckpt_path)
    logger.info("Checkpoint saved: %s", ckpt_path)

    # Save LightGBM separately — torch.save(state_dict) only saves PyTorch
    # parameters; model.lgbm_model is a sklearn object and must be pickled.
    import pickle

    if hasattr(model, "lgbm_model") and model.lgbm_model is not None:
        lgbm_path = output / "c1_lgbm_parquet.pkl"
        with open(lgbm_path, "wb") as fh:
            pickle.dump(model.lgbm_model, fh)
        logger.info("LightGBM checkpoint saved: %s", lgbm_path)

    # ---------- Save calibrator (isotonic) ----------
    calibrator_path = output / "c1_calibrator.pkl"
    with open(calibrator_path, "wb") as fh:
        pickle.dump(calibrator, fh)
    logger.info("Calibrator saved: %s", calibrator_path)

    # ---------- Save StandardScaler ----------
    if pipeline.feature_scaler is not None:
        scaler_path = output / "c1_scaler.pkl"
        with open(scaler_path, "wb") as fh:
            pickle.dump(pipeline.feature_scaler, fh)
        logger.info("StandardScaler saved: %s", scaler_path)

    # ---------- Save metrics ----------
    metrics = {
        "val_auc": round(val_auc, 6),
        "val_auc_torch": round(val_auc_torch if lgbm_scores is not None else val_auc, 6),
        "val_auc_lgbm": round(val_auc_lgbm, 6) if lgbm_scores is not None else None,
        "f2_threshold": round(best_thresh, 4),
        "f2_score": round(best_f2, 6),
        "ece_pre_calibration": round(ece_pre, 6),
        "ece_post_calibration": round(ece_post, 6),
        "ece": round(ece_post, 6),
        "n_records": len(records),
        "n_epochs": n_epochs,
        "train_elapsed_s": round(train_elapsed, 1),
        "parquet_path": parquet_path,
        "sample_n": sample_n,
        "seed": seed,
        "validation_split": "chronological_oot",
    }
    metrics_path = output / "train_metrics_parquet.json"
    with open(metrics_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    logger.info("Metrics saved: %s", metrics_path)

    print("\n═══════════════════════════════════════════════════")
    print("  C1 TRAINING COMPLETE")
    print("  ─────────────────────")
    print(f"  Records:     {len(records):,} (sampled from corpus)")
    print(f"  Val AUC:     {val_auc:.4f}")
    print(f"  F2 score:    {best_f2:.4f}")
    print(f"  F2 threshold: {best_thresh:.4f} (calibrated)")
    print(f"  ECE pre:     {ece_pre:.4f}")
    print(f"  ECE post:    {ece_post:.4f}")
    print(f"  Elapsed:     {train_elapsed:.1f} s")
    print(f"  Checkpoint:  {ckpt_path}")
    print(f"  Calibrator:  {calibrator_path}")
    print(f"  Metrics:     {metrics_path}")
    print(f"  Threshold:   {thresh_path}")
    print("")
    print("  ACTION REQUIRED:")
    print("  Update lip/pipeline.py line 64:")
    print(f"    FAILURE_PROBABILITY_THRESHOLD: float = {best_thresh:.4f}")
    print("═══════════════════════════════════════════════════")


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
