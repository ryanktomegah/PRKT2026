"""
run_production_pipeline.py — DGEN: Production Pipeline CLI Orchestrator
=======================================================================
Runs all 5 steps of the ISO 20022 synthetic data production pipeline:

  Step 1: Inspect public reference datasets (web_inspector)
  Step 2: Generate payments_synthetic.parquet + sample CSV (iso20022_payments)
  Step 3: Generate aml_synthetic.parquet (aml_production)
  Step 4: Save synthesis_parameters.json
  Step 5: Run statistical validation (statistical_validator_production)

Usage::

    # Dry-run: full pipeline on 10K records, completes in < 30 seconds
    python -m lip.dgen.run_production_pipeline --dry-run

    # Full production run (2M payments, 100K AML — 5–10 min on modern hardware)
    python -m lip.dgen.run_production_pipeline \\
        --output-dir artifacts/production_data \\
        --n-payments 2000000 \\
        --n-aml 100000 \\
        --seed 42

    # Custom volumes for experimentation
    python -m lip.dgen.run_production_pipeline \\
        --output-dir artifacts/production_data_small \\
        --n-payments 500000 \\
        --n-aml 20000

Output files (all written to --output-dir):
    payments_synthetic.parquet       — main payment event dataset
    payments_synthetic_sample.csv    — 10K-row quick-inspection sample
    aml_synthetic.parquet            — AML pattern dataset
    data_inspection_report.md        — per-source usability assessment
    synthesis_parameters.json        — all distribution parameters

IMPORTANT: Output directories are not committed to the repository.
           artifacts/ is listed in .gitignore.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DRY_RUN_N_PAYMENTS = 10_000
_DRY_RUN_N_AML = 1_000
_DRY_RUN_OUTPUT_DIR = "artifacts/production_data_dryrun"

_FULL_N_PAYMENTS = 2_000_000
_FULL_N_AML = 100_000
_FULL_OUTPUT_DIR = "artifacts/production_data"


def _banner(msg: str, width: int = 62) -> None:
    print(f"\n{'=' * width}")
    print(f"  {msg}")
    print(f"{'=' * width}")


def _step_header(step: int, name: str) -> float:
    print(f"\n[Step {step}] {name}")
    return time.time()


def _step_done(t0: float) -> None:
    print(f"  → done in {time.time() - t0:.1f}s")


def run_pipeline(
    output_dir: Path,
    n_payments: int,
    n_aml: int,
    seed: int,
    dry_run: bool,
) -> int:
    """Execute the full production pipeline.

    Returns 0 on success, 1 on validation failure, 2 on exception.
    """
    t_total = time.time()

    if dry_run:
        _banner("LIP DGEN — Production Pipeline  [DRY-RUN MODE]")
        print(f"  Records: {n_payments:,} payments | {n_aml:,} AML")
        print(f"  Output: {output_dir.resolve()}")
        print(f"  Seed: {seed}")
        print("  [DRY-RUN] All pipeline steps run at reduced scale for validation.")
    else:
        _banner("LIP DGEN — Production Pipeline")
        print(f"  Records: {n_payments:,} payments | {n_aml:,} AML")
        print(f"  Output: {output_dir.resolve()}")
        print(f"  Seed: {seed}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Dataset Inspection ──────────────────────────────────────────
    t0 = _step_header(1, "Dataset Inspection (web fetch + published priors)")
    try:
        from lip.dgen.web_inspector import run_all_inspections, write_inspection_report

        inspection_results = run_all_inspections()
        report_path = output_dir / "data_inspection_report.md"
        write_inspection_report(inspection_results, report_path)
        n_accessible = sum(1 for r in inspection_results if r.accessible)
        print(f"  Inspected {len(inspection_results)} datasets | {n_accessible} accessible")
        print(f"  Report → {report_path}")
    except Exception as exc:
        print(f"  FAILED: {exc}")
        return 2
    _step_done(t0)

    # ── Step 2: Generate Payment Events ─────────────────────────────────────
    # n_payments is the number of RJCT records; with success_multiplier=4.0
    # the total output is 5× that.
    t0 = _step_header(2, f"Generating {n_payments:,} RJCT + {n_payments * 4:,} success events (parquet)")
    try:
        import pandas as pd  # noqa: PLC0415

        from lip.dgen.iso20022_payments import (
            generate_payments,
            save_csv_sample,
            save_parquet,
        )

        df_payments = generate_payments(n=n_payments, seed=seed, success_multiplier=4.0)
        parquet_path = output_dir / "payments_synthetic.parquet"
        csv_path = output_dir / "payments_synthetic_sample.csv"

        print(f"  Generated {len(df_payments):,} records | {df_payments.memory_usage(deep=True).sum() / 1e6:.0f} MB in RAM")
        save_parquet(df_payments, parquet_path)
        save_csv_sample(df_payments, csv_path, n=10_000)
        parquet_size_mb = parquet_path.stat().st_size / 1e6
        print(f"  → {parquet_path} ({parquet_size_mb:.1f} MB)")
        print(f"  → {csv_path} (10K sample CSV)")

    except Exception as exc:
        print(f"  FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return 2
    _step_done(t0)

    # ── Step 3: Generate AML Dataset ────────────────────────────────────────
    t0 = _step_header(3, f"Generating {n_aml:,} AML pattern records (parquet)")
    try:
        from lip.dgen.aml_production import generate_aml_dataset

        aml_records = generate_aml_dataset(n_samples=n_aml, seed=seed + 1)
        df_aml = pd.DataFrame(aml_records)
        aml_path = output_dir / "aml_synthetic.parquet"
        df_aml.to_parquet(aml_path, engine="pyarrow", compression="snappy", index=False)
        n_flagged = int((df_aml["aml_flag"] == 1).sum())
        flag_rate = n_flagged / len(df_aml)
        print(f"  Generated {len(df_aml):,} records | AML flag rate: {flag_rate:.4f} ({n_flagged:,} flagged)")
        print(f"  → {aml_path} ({aml_path.stat().st_size / 1e6:.1f} MB)")

    except Exception as exc:
        print(f"  FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return 2
    _step_done(t0)

    # ── Step 4: Save Synthesis Parameters ───────────────────────────────────
    t0 = _step_header(4, "Saving synthesis_parameters.json")
    try:
        from lip.dgen.iso20022_payments import build_synthesis_parameters

        params = build_synthesis_parameters()
        params_path = output_dir / "synthesis_parameters.json"
        params_path.write_text(params.to_json(), encoding="utf-8")
        print(f"  → {params_path}")
        print(f"  Contains: {len(params.corridors)} corridors, {len(params.rejection_codes)} rejection codes")

    except Exception as exc:
        print(f"  FAILED: {exc}")
        return 2
    _step_done(t0)

    # ── Step 5: Statistical Validation ──────────────────────────────────────
    t0 = _step_header(5, "Statistical Validation")
    validation_passed = True
    try:
        from lip.dgen.statistical_validator_production import validate_aml, validate_payments

        print("\n  Payments dataset:")
        payments_report = validate_payments(df_payments)
        print("\n" + "\n".join(f"    {line_}" for line_ in payments_report.summary().splitlines()))

        print("\n  AML dataset:")
        aml_report = validate_aml(df_aml)
        print("\n" + "\n".join(f"    {line_}" for line_ in aml_report.summary().splitlines()))

        validation_passed = payments_report.passed and aml_report.passed

        # Embed validation results in a data card
        data_card = {
            "schema_version": "1.0",
            "data_card_type": "LIP_PRODUCTION_CORPUS",
            "generated_at": datetime.now(tz=timezone.utc).isoformat() + "Z",
            "generation_tool": "lip.dgen.run_production_pipeline",
            "dry_run": dry_run,
            "seed": seed,
            "regulatory_compliance": {
                "eu_ai_act_article": "10",
                "eu_ai_act_requirement": "Data governance and data management practices",
                "sr_11_7": "Out-of-time validation: 18-month temporal spread (2023-07 to 2025-01)",
                "data_type": "FULLY_SYNTHETIC — no real transaction data, no real BICs",
                "pii_present": False,
            },
            "datasets": {
                "payments_synthetic": {
                    "n_records": len(df_payments),
                    "file": str(parquet_path),
                    "validation": payments_report.to_dict(),
                },
                "aml_synthetic": {
                    "n_records": len(df_aml),
                    "file": str(aml_path),
                    "validation": aml_report.to_dict(),
                },
            },
            "intended_use": (
                "Training and validation of LIP ML components (C1, C6). "
                "NOT suitable for production inference. NOT real financial data."
            ),
            "prohibited_uses": [
                "Do not use as real transaction data",
                "Do not use aml_synthetic for live sanctions screening",
                "Do not commit output files to version control",
            ],
        }
        card_path = output_dir / "data_card.json"
        card_path.write_text(json.dumps(data_card, indent=2, default=str), encoding="utf-8")
        print(f"\n  Data card → {card_path}")

    except Exception as exc:
        print(f"  FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return 2
    _step_done(t0)

    # ── Final summary ────────────────────────────────────────────────────────
    total_time = time.time() - t_total
    overall_status = "PASS" if validation_passed else "FAIL — validation errors (see above)"

    if dry_run:
        _banner("LIP DGEN  [DRY-RUN]  Complete")
    else:
        _banner("LIP DGEN  Complete")

    print(f"  Total time    : {total_time:.1f}s")
    print(f"  Output dir    : {output_dir.resolve()}")
    print("  Files written : payments_synthetic.parquet, payments_synthetic_sample.csv,")
    print("                  aml_synthetic.parquet, data_inspection_report.md,")
    print("                  synthesis_parameters.json, data_card.json")
    print(f"  Validation    : {overall_status}")

    if dry_run:
        print("\n  [DRY-RUN] Pipeline validated successfully. Run without --dry-run for full scale.")

    return 0 if validation_passed else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="LIP DGEN: Production ISO 20022 Synthetic Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick validation (< 30s):
  python -m lip.dgen.run_production_pipeline --dry-run

  # Full production run:
  python -m lip.dgen.run_production_pipeline \\
      --output-dir artifacts/production_data \\
      --n-payments 2000000 --n-aml 100000

  # Custom volumes:
  python -m lip.dgen.run_production_pipeline \\
      --output-dir artifacts/production_data_small \\
      --n-payments 200000 --n-aml 10000
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            f"Run full pipeline on {_DRY_RUN_N_PAYMENTS:,} records "
            f"(output → {_DRY_RUN_OUTPUT_DIR}/). Completes in < 30s."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=_FULL_OUTPUT_DIR,
        help=f"Output directory (default: {_FULL_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--n-payments",
        type=int,
        default=_FULL_N_PAYMENTS,
        help=(
            f"Number of RJCT (failed) payment events to generate (default: {_FULL_N_PAYMENTS:,}). "
            "Total corpus = n_payments × 5 (4 success records per RJCT record)."
        ),
    )
    parser.add_argument(
        "--n-aml",
        type=int,
        default=_FULL_N_AML,
        help=f"Number of AML records to generate (default: {_FULL_N_AML:,})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Master random seed (default: 42)",
    )

    args = parser.parse_args(argv)

    # Apply dry-run overrides
    if args.dry_run:
        n_payments = _DRY_RUN_N_PAYMENTS
        n_aml = _DRY_RUN_N_AML
        output_dir = Path(_DRY_RUN_OUTPUT_DIR)
    else:
        n_payments = args.n_payments
        n_aml = args.n_aml
        output_dir = Path(args.output_dir)

    return run_pipeline(
        output_dir=output_dir,
        n_payments=n_payments,
        n_aml=n_aml,
        seed=args.seed,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
