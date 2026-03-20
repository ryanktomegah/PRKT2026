#!/usr/bin/env python3
"""
check_temporal_features.py — Verify C1 temporal feature distinctness.

Loads a sample from a payments parquet, runs the training adapter,
and checks that windowed failure rates (1d/7d/30d) carry distinct signal
and consecutive_failures is non-zero.

Usage:
    python scripts/check_temporal_features.py [path/to/payments.parquet] [--sample N]

Exit code: 0 = all checks pass, 1 = any check fails.
"""
import argparse
import sys
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Verify C1 temporal feature distinctness")
    parser.add_argument("parquet", nargs="?", default=None, help="Path to payments parquet")
    parser.add_argument("--sample", type=int, default=5000, help="Sample size (default 5000)")
    args = parser.parse_args()

    # ── Locate parquet ────────────────────────────────────────────────────────
    if args.parquet:
        parquet_path = args.parquet
    else:
        # Try default locations
        candidates = [
            "artifacts/payments.parquet",
            "artifacts/bic_risk_corpus.parquet",
            "/tmp/lip_smoke_corpus/c1_corpus.parquet",
        ]
        parquet_path = next((p for p in candidates if Path(p).exists()), None)
        if parquet_path is None:
            print("ERROR: no parquet found. Pass path as argument or generate with DGEN.")
            sys.exit(1)

    print(f"Loading {args.sample} records from {parquet_path}…")

    # ── Import training adapter ───────────────────────────────────────────────
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.train_c1_on_parquet import _adapt_parquet_to_records

    records = _adapt_parquet_to_records(parquet_path, sample_n=args.sample, seed=42)
    print(f"Adapter returned {len(records)} records")

    if len(records) < 100:
        print("ERROR: too few records for meaningful correlation analysis (<100)")
        sys.exit(1)

    # ── Import feature extractor ──────────────────────────────────────────────
    from lip.c1_failure_classifier.features import FeaturePipeline

    pipeline = FeaturePipeline()
    vecs = []
    for rec in records:
        result = pipeline.extract(rec)
        vecs.append(result.tabular)

    vecs = np.array(vecs, dtype=np.float32)
    print(f"Feature matrix: {vecs.shape}")

    # ── Feature indices (from features.py _build_feature_names) ──────────────
    # Sender: vec[64]=fail_1d, vec[65]=fail_7d, vec[66]=fail_30d, vec[70]=consec
    # Receiver: vec[67]=fail_1d, vec[68]=fail_7d, vec[69]=fail_30d, vec[72]=consec
    IDX_S_FAIL_1D  = 64
    IDX_S_FAIL_7D  = 65
    IDX_S_FAIL_30D = 66
    IDX_R_FAIL_1D  = 67
    IDX_R_FAIL_7D  = 68
    IDX_R_FAIL_30D = 69
    IDX_S_CONSEC   = 70
    IDX_R_CONSEC   = 72

    # ── Check 1: windowed failure rates are not identical ─────────────────────
    failures = []

    def corr(a, b):
        """Pearson correlation, NaN-safe."""
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() < 10:
            return 1.0  # too few points — fail conservatively
        a, b = a[mask], b[mask]
        if np.std(a) < 1e-9 or np.std(b) < 1e-9:
            return 1.0  # constant — duplicate signal
        return float(np.corrcoef(a, b)[0, 1])

    checks = [
        ("sender fail_1d vs fail_30d",   IDX_S_FAIL_1D,  IDX_S_FAIL_30D, 0.999),
        ("sender fail_7d vs fail_30d",   IDX_S_FAIL_7D,  IDX_S_FAIL_30D, 0.999),
        ("sender fail_1d vs fail_7d",    IDX_S_FAIL_1D,  IDX_S_FAIL_7D,  0.999),
        ("receiver fail_1d vs fail_30d", IDX_R_FAIL_1D,  IDX_R_FAIL_30D, 0.999),
        ("receiver fail_7d vs fail_30d", IDX_R_FAIL_7D,  IDX_R_FAIL_30D, 0.999),
        ("receiver fail_1d vs fail_7d",  IDX_R_FAIL_1D,  IDX_R_FAIL_7D,  0.999),
    ]
    for label, i, j, threshold in checks:
        r = corr(vecs[:, i], vecs[:, j])
        status = "PASS" if r < threshold else "FAIL"
        print(f"  [{status}] corr({label}) = {r:.4f}  (threshold < {threshold})")
        if status == "FAIL":
            failures.append(f"corr({label}) = {r:.4f} ≥ {threshold} — windowed rates still duplicated")

    # ── Check 2: consecutive_failures has non-zero variance ───────────────────
    for label, idx in [("sender_consec", IDX_S_CONSEC), ("receiver_consec", IDX_R_CONSEC)]:
        std = float(np.std(vecs[:, idx]))
        mean = float(np.mean(vecs[:, idx]))
        status = "PASS" if std > 0 else "FAIL"
        print(f"  [{status}] {label}: mean={mean:.3f}  std={std:.3f}  (need std > 0)")
        if status == "FAIL":
            failures.append(f"{label} std=0 — all zeros, consecutive_failures not computed")

    # ── Per-feature stats for the 8 reclaimed slots ───────────────────────────
    print("\nPer-feature stats for reclaimed slots (vec[64-72]):")
    for i, name in [
        (64, "s_fail_1d"), (65, "s_fail_7d"),  (66, "s_fail_30d"),
        (67, "r_fail_1d"), (68, "r_fail_7d"),  (69, "r_fail_30d"),
        (70, "s_consec"),  (72, "r_consec"),
    ]:
        col = vecs[:, i]
        finite = col[np.isfinite(col)]
        print(
            f"  vec[{i:2d}] {name:15s}  "
            f"mean={np.mean(finite):.4f}  std={np.std(finite):.4f}  "
            f"min={np.min(finite):.4f}  max={np.max(finite):.4f}"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  ✗ {f}")
        print()
        print("If windowed rates are still correlated ≥ 0.999, DGEN may generate failures")
        print("uniformly across time per BIC. Run with a larger corpus or verify DGEN")
        print("temporal failure clustering with: python scripts/check_dgen_temporal.py")
        sys.exit(1)
    else:
        print("PASS — all temporal feature checks passed. Reclaimed 8 feature slots carry distinct signal.")
        sys.exit(0)


if __name__ == "__main__":
    main()
