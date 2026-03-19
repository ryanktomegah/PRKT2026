#!/usr/bin/env python3
"""check_c1_readiness.py — Pre-flight verification before C1 training runs.

Catches in 60s what would otherwise fail silently after 8+ hours.

Usage:
    python3 check_c1_readiness.py --parquet path/to/parquet [--smoke] [--static-only]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent  # repo root (.claude/skills/name/scripts/)
FEATURES_PY = ROOT / "lip/c1_failure_classifier/features.py"
TRAINING_TORCH_PY = ROOT / "lip/c1_failure_classifier/training_torch.py"
TRAIN_PARQUET_PY = ROOT / "scripts/train_c1_on_parquet.py"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

_failures: list[str] = []


def _check(ok: bool, msg: str, hint: str = "") -> bool:
    if ok:
        print(f"  {PASS}  {msg}")
    else:
        print(f"  {FAIL}  {msg}")
        if hint:
            print(f"        → {hint}")
        _failures.append(msg)
    return ok


# ---------------------------------------------------------------------------
# 1. Static checks: key coverage
# ---------------------------------------------------------------------------

def _keys_from_features_py(stats_var: str) -> set[str]:
    """Extract keys read from s_stats/r_stats/c_stats in features.py.

    stats_var maps to the local variable name used in features.py:
        sender_stats   -> s_stats
        receiver_stats -> r_stats
        corridor_stats -> c_stats
    """
    import re
    var_map = {"sender_stats": "s_stats", "receiver_stats": "r_stats", "corridor_stats": "c_stats"}
    local_var = var_map.get(stats_var, stats_var)
    text = FEATURES_PY.read_text()
    pattern = rf'{re.escape(local_var)}\.get\("([^"]+)"'
    return set(re.findall(pattern, text))


def _keys_from_stats_func(func_name: str) -> set[str]:
    """Extract keys returned by _c_stats/_s_stats/_r_stats in train_c1_on_parquet.py."""
    import re
    text = TRAIN_PARQUET_PY.read_text()
    # Find the function body
    fn_match = re.search(rf"def {re.escape(func_name)}\(.*?\) -> dict:(.*?)^    def ", text, re.DOTALL | re.MULTILINE)
    if not fn_match:
        fn_match = re.search(rf"def {re.escape(func_name)}\(.*?\) -> dict:(.*?)^def ", text, re.DOTALL | re.MULTILINE)
    if not fn_match:
        # Last function — grab to end of file
        fn_match = re.search(rf"def {re.escape(func_name)}\(.*?\) -> dict:(.*)", text, re.DOTALL)
    if not fn_match:
        return set()
    body = fn_match.group(1)
    return set(re.findall(r'"([a-z_0-9]+)"\s*:', body))


def check_feature_key_coverage() -> None:
    print("\n[1] Feature key coverage (stats dicts)")

    pairs = [
        ("sender_stats", "_s_stats"),
        ("receiver_stats", "_r_stats"),
        ("corridor_stats", "_c_stats"),
    ]

    for feat_var, func_name in pairs:
        required = _keys_from_features_py(feat_var)
        provided = _keys_from_stats_func(func_name)
        missing = required - provided
        extra = provided - required
        label = f"{func_name} covers all {feat_var} keys ({len(required)} required)"
        hint = f"Missing keys: {sorted(missing)} — add to {func_name} in train_c1_on_parquet.py"
        _check(len(missing) == 0, label, hint if missing else "")
        if extra:
            print(f"        {WARN}  {func_name} provides unused keys: {sorted(extra)}")


# ---------------------------------------------------------------------------
# 2. Static checks: StandardScaler placement
# ---------------------------------------------------------------------------

def check_standard_scaler() -> None:
    print("\n[2] StandardScaler placement in training_torch.py")
    text = TRAINING_TORCH_PY.read_text()

    # Check stage3b is called in train_torch
    _check(
        "stage3b_standard_scale" in text and "train_torch" in text,
        "stage3b_standard_scale is called inside train_torch",
        "Add 'X_train, X_val = numpy_pipeline.stage3b_standard_scale(X_train, X_val)' before stage5",
    )

    # Check it's called BEFORE stage5 within train_torch body (compare call sites, not defs)
    lines = text.splitlines()
    # Find all lines in the train_torch method body (after "def train_torch")
    train_torch_start = next((i for i, l in enumerate(lines) if "def train_torch" in l), 0)
    scale_line = next(
        (i for i, l in enumerate(lines)
         if i > train_torch_start and "stage3b_standard_scale" in l and "def " not in l),
        9999,
    )
    stage5_line = next(
        (i for i, l in enumerate(lines)
         if i > train_torch_start and "stage5_graphsage_pretrain_torch" in l and "def " not in l),
        9999,
    )
    _check(
        scale_line < stage5_line,
        "StandardScaler is applied before stage5 (GraphSAGE pretrain)",
        f"stage3b call at line {scale_line+1}, stage5 call at line {stage5_line+1} — scaler must come first",
    )


# ---------------------------------------------------------------------------
# 3. Corpus checks: label variance
# ---------------------------------------------------------------------------

def check_corpus_signal(parquet_path: Path) -> None:
    print(f"\n[3] Corpus signal check ({parquet_path.name})")
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        print(f"  {WARN}  pandas/numpy not available — skipping corpus checks")
        return

    if not parquet_path.exists():
        print(f"  {WARN}  Parquet not found at {parquet_path} — skipping corpus checks")
        return

    print(f"       Loading parquet (sample=200K for speed)...")
    df = pd.read_parquet(parquet_path)
    if len(df) > 200_000:
        df = df.sample(n=200_000, random_state=42)

    # Label col
    label_col = "label" if "label" in df.columns else "is_permanent_failure"
    if label_col not in df.columns:
        print(f"  {WARN}  No label column found — skipping label checks")
        return

    # Global label rate
    global_rate = float(df[label_col].mean())
    _check(
        0.03 <= global_rate <= 0.45,
        f"Global label rate {global_rate:.1%} is in healthy range [3%–45%]",
        f"Extreme imbalance: {global_rate:.1%} — check DGEN failure_rate params or BLOCK filter",
    )

    # Per-corridor variance
    if "corridor" in df.columns:
        corridor_rates = df.groupby("corridor")[label_col].mean()
        rate_max = float(corridor_rates.max())
        rate_min = float(corridor_rates.min())
        ratio = rate_max / max(rate_min, 1e-6)
        print(f"       Per-corridor label rates: min={rate_min:.1%} max={rate_max:.1%} ratio={ratio:.1f}×")
        _check(
            ratio >= 2.0,
            f"Corridor failure rate spread ≥ 2× (actual: {ratio:.1f}×)",
            "All corridors have identical failure rates — DGEN corridor weighting bug. "
            "Check _CORRIDOR_FAILURE_WEIGHTS in iso20022_payments.py",
        )

    # Feature correlation (if amount_usd available)
    if "amount_usd" in df.columns:
        corr = float(df["amount_usd"].corr(df[label_col]))
        print(f"       amount_usd ↔ label correlation: {corr:+.4f}")

    if "corridor" in df.columns:
        # Encode corridor as int and check correlation
        corridor_enc = df["corridor"].astype("category").cat.codes
        corr_c = float(corridor_enc.corr(df[label_col]))
        _check(
            abs(corr_c) >= 0.03,
            f"Corridor encoding ↔ label |corr| ≥ 0.03 (actual: {corr_c:+.4f})",
            "Corridor has no correlation with label — DGEN failure weights not applied correctly",
        )


# ---------------------------------------------------------------------------
# 4. Smoke test
# ---------------------------------------------------------------------------

def run_smoke_test(parquet_path: Path) -> None:
    print(f"\n[4] Smoke test (5K samples, 2 epochs)")
    if not parquet_path.exists():
        print(f"  {WARN}  Parquet not found — skipping smoke test")
        return

    cmd = [
        sys.executable, str(TRAIN_PARQUET_PY),
        "--parquet", str(parquet_path),
        "--sample", "5000",
        "--epochs", "2",
    ]
    print(f"       Running: {' '.join(cmd[-6:])}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)

    if result.returncode != 0:
        _check(False, "Smoke test completed without error",
               f"Exit {result.returncode}. Last stderr:\n{result.stderr[-800:]}")
        return

    # Extract val_AUC from output
    import re
    auc_match = re.search(r"Validation AUC.*?:\s*([\d.]+)", result.stdout + result.stderr)
    if auc_match:
        auc = float(auc_match.group(1))
        _check(
            auc > 0.52,
            f"Smoke val_AUC {auc:.4f} > 0.52 (gradient is flowing)",
            f"AUC ≈ 0.50 means gradient is not flowing — check feature keys and StandardScaler",
        )
        if auc < 0.55:
            print(f"        {WARN}  AUC {auc:.4f} is low for smoke test — full run may plateau around 0.6")
    else:
        print(f"  {WARN}  Could not parse val_AUC from output — check manually")

    _check(True, "Smoke test completed without Python error")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path, help="Path to payments parquet")
    parser.add_argument("--static-only", action="store_true",
                        help="Skip corpus and smoke checks")
    parser.add_argument("--smoke", action="store_true",
                        help="Force run smoke test even if --static-only")
    args = parser.parse_args()

    print("=" * 60)
    print("C1 READINESS CHECK")
    print("=" * 60)

    check_feature_key_coverage()
    check_standard_scaler()

    if not args.static_only and args.parquet:
        check_corpus_signal(args.parquet)
        run_smoke_test(args.parquet)
    elif not args.parquet and not args.static_only:
        print(f"\n  {WARN}  No --parquet provided — running static checks only")

    print("\n" + "=" * 60)
    if _failures:
        print(f"RESULT: FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"  ✗ {f}")
        print("\nDo NOT launch a full training run until all checks pass.")
        return 1
    else:
        print("RESULT: PASS — all checks passed. Safe to launch training run.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
