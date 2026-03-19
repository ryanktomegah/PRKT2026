#!/usr/bin/env python3
"""check_corpus_signal.py — Analyse a payments parquet for C1 training signal quality.

Detects zero-signal corpora in < 30s. Run after DGEN, before training.

Usage:
    python3 check_corpus_signal.py path/to/payments.parquet [--sample N]
    python3 check_corpus_signal.py path/to/payments.parquet --sample 0  # full corpus
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

_failures: list[str] = []


def _check(ok: bool, msg: str, hint: str = "") -> bool:
    symbol = PASS if ok else FAIL
    print(f"  {symbol}  {msg}")
    if not ok:
        if hint:
            print(f"        → {hint}")
        _failures.append(msg)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("parquet", type=Path, help="Path to payments parquet file")
    parser.add_argument("--sample", type=int, default=200_000,
                        help="Rows to sample for analysis (0 = full corpus)")
    args = parser.parse_args()

    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        print("ERROR: pandas and numpy required. Install with: pip install pandas numpy pyarrow")
        return 2

    if not args.parquet.exists():
        print(f"ERROR: Parquet not found at {args.parquet}")
        return 2

    print(f"\n{'='*60}")
    print(f"CORPUS SIGNAL CHECK: {args.parquet.name}")
    print(f"{'='*60}")

    # ── Load ─────────────────────────────────────────────────────────────────
    print(f"\nLoading parquet...")
    df = pd.read_parquet(args.parquet)
    n_total = len(df)
    print(f"  Total rows: {n_total:,}")

    if args.sample and n_total > args.sample:
        df = df.sample(n=args.sample, random_state=42)
        print(f"  Sampled:    {len(df):,}")

    # ── Label column ─────────────────────────────────────────────────────────
    label_col = None
    for candidate in ("label", "is_permanent_failure"):
        if candidate in df.columns:
            label_col = candidate
            break

    if label_col is None:
        print(f"\n{FAIL}  No label column found. Columns: {list(df.columns)}")
        return 1

    y = df[label_col].astype(float)
    global_rate = float(y.mean())

    print(f"\n[1] Class balance")
    _check(
        0.03 <= global_rate <= 0.45,
        f"Label rate {global_rate:.1%}  ({int(y.sum()):,} pos / {int((1-y).sum()):,} neg)",
        "Extreme imbalance — check DGEN params or BLOCK filter exclusion",
    )

    # ── Per-corridor analysis ─────────────────────────────────────────────────
    print(f"\n[2] Per-corridor failure rates")
    if "corridor" not in df.columns:
        print(f"  {WARN}  No 'corridor' column — skipping")
    else:
        corridor_rates = df.groupby("corridor")[label_col].agg(["mean", "count"]).sort_values("mean")
        corridor_rates.columns = ["failure_rate", "count"]

        rate_min = float(corridor_rates["failure_rate"].min())
        rate_max = float(corridor_rates["failure_rate"].max())
        rate_std = float(corridor_rates["failure_rate"].std())
        ratio = rate_max / max(rate_min, 1e-6)

        for corridor, row in corridor_rates.iterrows():
            bar = "█" * int(row["failure_rate"] * 40)
            print(f"  {corridor:<15} {row['failure_rate']:5.1%}  {bar}")

        print(f"\n  min={rate_min:.1%}  max={rate_max:.1%}  std={rate_std:.3f}  ratio={ratio:.1f}×")

        _check(
            ratio >= 2.0,
            f"Corridor failure rate spread ≥ 2× (actual: {ratio:.1f}×)",
            "All corridors look similar — DGEN _CORRIDOR_FAILURE_WEIGHTS likely not applied. "
            "Check iso20022_payments.py: RJCT events must sample corridors by failure_rate × volume_weight",
        )

        _check(
            rate_std > 0.02,
            f"Corridor failure rate std dev {rate_std:.3f} > 0.02 (real variance exists)",
            f"std={rate_std:.4f} is near zero — the feature will have no discriminative power",
        )

    # ── Raw feature correlations ──────────────────────────────────────────────
    print(f"\n[3] Raw column correlations with label")
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != label_col]

    correlations = {}
    for col in numeric_cols:
        try:
            corr = float(df[col].corr(y))
            if abs(corr) > 0.01:
                correlations[col] = corr
        except Exception:
            pass

    if correlations:
        sorted_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        print(f"  Top 10 by |correlation|:")
        for col, corr in sorted_corrs[:10]:
            direction = "+" if corr > 0 else ""
            bar = "█" * int(abs(corr) * 200)
            print(f"  {col:<35} {direction}{corr:.4f}  {bar}")

        max_corr = max(abs(v) for v in correlations.values())
        _check(
            max_corr >= 0.05,
            f"At least one feature has |corr| ≥ 0.05 with label (best: {max_corr:.4f})",
            "No feature correlates with label — model will plateau at AUC ≈ 0.50 regardless of epochs",
        )

        if "corridor" in df.columns:
            corridor_enc = df["corridor"].astype("category").cat.codes.astype(float)
            corr_c = float(corridor_enc.corr(y))
            _check(
                abs(corr_c) >= 0.03,
                f"Corridor (encoded) ↔ label |corr| ≥ 0.03 (actual: {corr_c:+.4f})",
                "Corridor has zero correlation with label — DGEN weighting bug",
            )
    else:
        print(f"  {WARN}  No numeric columns with meaningful correlation found")

    # ── Amount distribution ────────────────────────────────────────────────────
    if "amount_usd" in df.columns:
        print(f"\n[4] Amount distribution (sanity check)")
        amt = df["amount_usd"]
        print(f"  p1={amt.quantile(0.01):>12,.0f}  p50={amt.quantile(0.50):>12,.0f}  p99={amt.quantile(0.99):>12,.0f}")
        print(f"  mean={amt.mean():>10,.0f}  std={amt.std():>11,.0f}  max={amt.max():>12,.0f}")
        _check(
            amt.max() < 100_000_000,
            f"Max amount ${amt.max():,.0f} < $100M (no outlier contamination)",
            "Extreme amount outliers will dominate features if StandardScaler is not applied",
        )

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    if _failures:
        print(f"RESULT: FAIL — {len(_failures)} issue(s) found:")
        for f in _failures:
            print(f"  ✗ {f}")
        print("\nDo NOT train on this corpus — fix the data generation issues first.")
        return 1
    else:
        print(f"RESULT: PASS — corpus signal looks healthy. Run /verify-c1-readiness next.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
