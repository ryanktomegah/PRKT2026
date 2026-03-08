"""
generate_all.py — DGEN Master Orchestration Script
====================================================
Generates all LIP synthetic training corpora in a single invocation.

Usage
-----
    # Full generation (all components, default volumes):
    python -m lip.dgen.generate_all --output-dir artifacts/synthetic

    # Specific components only:
    python -m lip.dgen.generate_all --output-dir artifacts/synthetic --components c2 c4

    # Quick smoke-test (small N):
    python -m lip.dgen.generate_all --output-dir /tmp/dgen_test --smoke-test

    # Custom volumes:
    python -m lip.dgen.generate_all --output-dir artifacts/synthetic \\
        --n-c1 100000 --n-c2 30000 --n-c4 15000 --n-c6 20000

Output format
-------------
    artifacts/synthetic/
    ├── c1_corpus_n100000_seed42.json
    ├── c2_corpus_n30000_seed42.json
    ├── c4_corpus_n15000_seed42.json
    ├── c6_corpus_n20000_seed42.json   ← generated but NOT committed to repo
    ├── validation_report.json
    └── data_card.json                 ← EU AI Act Art.10 data lineage

CIPHER NOTE: c6_corpus_* is generated to --output-dir but the .gitignore
entry `artifacts/synthetic/c6_*` prevents it from being committed.

FORGE NOTE: For CI runs, use --smoke-test to keep generation under 30 seconds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional: try importing numpy early to give a clear error
# ---------------------------------------------------------------------------
try:
    import numpy as np  # noqa: F401
except ImportError:
    print("ERROR: numpy is required. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Volume defaults (ARIA + QUANT team consensus)
# ---------------------------------------------------------------------------

_DEFAULT_VOLUMES = {
    "c1": 100_000,
    "c2":  30_000,
    "c3":  25_000,
    "c4":  15_000,
    "c6":  20_000,
}

_SMOKE_VOLUMES = {
    "c1": 500,
    "c2": 500,
    "c3": 500,
    "c4": 500,
    "c6": 500,
}

_DEFAULT_SEED = 42


# ---------------------------------------------------------------------------
# Checksum helper (FORGE: integrity verification)
# ---------------------------------------------------------------------------

def _sha256_of_records(records: List[dict]) -> str:
    payload = json.dumps(records, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Component generators
# ---------------------------------------------------------------------------

def _generate_c1(n: int, seed: int) -> List[dict]:
    """C1: SWIFT payment failure records (existing generator)."""
    from lip.c1_failure_classifier.synthetic_data import generate_synthetic_dataset
    return generate_synthetic_dataset(n_samples=n, seed=seed)


def _generate_c2(n: int, seed: int) -> List[dict]:
    """C2: PD model records with QUANT-validated correlated financials (v2)."""
    from lip.dgen.c2_generator import generate_pd_training_data_v2
    return generate_pd_training_data_v2(n_samples=n, seed=seed)


def _generate_c3(n: int, seed: int) -> List[dict]:
    """C3: Bridge-loan repayment scenarios across all 5 settlement rails."""
    from lip.dgen.c3_generator import generate_repayment_corpus
    return generate_repayment_corpus(n_samples=n, seed=seed)


def _generate_c4(n: int, seed: int) -> List[dict]:
    """C4: Dispute narrative text (template-based, no LLM dependency)."""
    from lip.dgen.c4_generator import generate_dispute_corpus
    return generate_dispute_corpus(n_samples=n, seed=seed)


def _generate_c6(n: int, seed: int) -> List[dict]:
    """C6: AML pattern corpus (CIPHER: never committed)."""
    from lip.dgen.c6_generator import generate_aml_corpus
    return generate_aml_corpus(n_samples=n, seed=seed)


_GENERATORS = {
    "c1": _generate_c1,
    "c2": _generate_c2,
    "c3": _generate_c3,
    "c4": _generate_c4,
    "c6": _generate_c6,
}

# Validator wrappers (returns None if no specific validator)
def _get_validator(component: str):
    if component == "c1":
        from lip.dgen.validator import validate_c1_corpus
        return validate_c1_corpus
    elif component == "c2":
        from lip.dgen.validator import validate_c2_corpus
        return validate_c2_corpus
    elif component == "c3":
        from lip.dgen.validator import validate_c3_corpus
        return validate_c3_corpus
    elif component == "c4":
        from lip.dgen.validator import validate_c4_corpus
        return validate_c4_corpus
    elif component == "c6":
        from lip.dgen.validator import validate_c6_corpus
        return validate_c6_corpus
    return None


# ---------------------------------------------------------------------------
# Data card (EU AI Act Art.10)
# ---------------------------------------------------------------------------

def _build_data_card(
    component_results: Dict[str, Dict[str, Any]],
    generation_time_s: float,
) -> dict:
    """Build EU AI Act Art.10 data card for all generated corpora."""
    return {
        "schema_version": "1.0",
        "data_card_type": "LIP_SYNTHETIC_CORPUS",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "generation_tool": "lip.dgen.generate_all",
        "generation_time_seconds": round(generation_time_s, 2),
        "regulatory_compliance": {
            "eu_ai_act_article": "10",
            "eu_ai_act_requirement": "Data governance and data management practices",
            "sr_11_7": "Out-of-time validation supported via temporal structure in C2/C6",
            "data_type": "FULLY_SYNTHETIC — no real transaction data",
            "pii_present": False,
        },
        "corpora": component_results,
        "intended_use": (
            "Training and validation of LIP ML components (C1, C2, C4, C6). "
            "NOT suitable for production inference. NOT real financial data."
        ),
        "prohibited_uses": [
            "Do not use as real transaction data",
            "Do not use C6 corpus for sanctions screening",
            "Do not commit C6 corpus to version control",
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="DGEN: Generate all LIP synthetic training corpora"
    )
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["c1", "c2", "c3", "c4", "c6"],
        default=["c1", "c2", "c3", "c4", "c6"],
        help="Which components to generate (default: all)",
    )
    parser.add_argument("--smoke-test", action="store_true", help="Small N for CI smoke test")
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    parser.add_argument("--n-c1", type=int, default=None)
    parser.add_argument("--n-c2", type=int, default=None)
    parser.add_argument("--n-c3", type=int, default=None)
    parser.add_argument("--n-c4", type=int, default=None)
    parser.add_argument("--n-c6", type=int, default=None)
    parser.add_argument("--fail-on-validation-error", action="store_true", default=True)
    parser.add_argument("--no-fail-on-validation-error", dest="fail_on_validation_error", action="store_false")

    args = parser.parse_args(argv)

    volumes = _SMOKE_VOLUMES.copy() if args.smoke_test else _DEFAULT_VOLUMES.copy()
    if args.n_c1 is not None:
        volumes["c1"] = args.n_c1
    if args.n_c2 is not None:
        volumes["c2"] = args.n_c2
    if args.n_c3 is not None:
        volumes["c3"] = args.n_c3
    if args.n_c4 is not None:
        volumes["c4"] = args.n_c4
    if args.n_c6 is not None:
        volumes["c6"] = args.n_c6

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("  DGEN — LIP Synthetic Data Generation")
    print(f"  Seed: {args.seed} | Mode: {'SMOKE-TEST' if args.smoke_test else 'FULL'}")
    print(f"  Output: {output_dir.resolve()}")
    print(f"{'='*60}\n")

    t_start = time.time()
    component_results: Dict[str, Any] = {}
    validation_failed = False

    for component in args.components:
        n = volumes[component]
        generator = _GENERATORS[component]
        validator = _get_validator(component)

        print(f"[{component.upper()}] Generating {n:,} records (seed={args.seed})...", end=" ", flush=True)
        t0 = time.time()

        try:
            records = generator(n, args.seed)
        except Exception as e:
            print(f"FAILED: {e}")
            component_results[component] = {"status": "generation_failed", "error": str(e)}
            continue

        elapsed = time.time() - t0
        checksum = _sha256_of_records(records)

        print(f"done in {elapsed:.1f}s | sha256={checksum[:16]}...")

        # Validate
        val_result = None
        if validator is not None:
            print(f"[{component.upper()}] Validating...", end=" ", flush=True)
            report = validator(records)
            print(f"{'PASS' if report.passed else 'FAIL'}")
            print(report.summary())
            print()
            val_result = report.to_dict()
            if not report.passed and args.fail_on_validation_error:
                validation_failed = True

        # Save
        filename = f"{component}_corpus_n{n}_seed{args.seed}.json"
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            json.dump(records, f, default=str)

        # Checksum file
        checksum_path = output_dir / f"{filename}.sha256"
        checksum_path.write_text(f"{checksum}  {filename}\n")

        positive_count = sum(
            1 for r in records
            if r.get("label") == 1 or r.get("aml_flag") == 1
        )

        component_results[component] = {
            "status": "ok",
            "n_records": len(records),
            "positive_count": positive_count,
            "positive_rate": round(positive_count / len(records), 4),
            "output_file": str(filepath),
            "sha256": checksum,
            "generation_seconds": round(elapsed, 2),
            "validation": val_result,
        }

        print(f"[{component.upper()}] Saved → {filepath}")
        print(f"[{component.upper()}] Positive rate: {positive_count}/{len(records)} = {positive_count/len(records):.3f}")
        print()

    total_elapsed = time.time() - t_start

    # Write validation report
    val_report_path = output_dir / "validation_report.json"
    with open(val_report_path, "w") as f:
        json.dump(component_results, f, indent=2, default=str)

    # Write data card (EU AI Act Art.10)
    data_card = _build_data_card(component_results, total_elapsed)
    data_card_path = output_dir / "data_card.json"
    with open(data_card_path, "w") as f:
        json.dump(data_card, f, indent=2, default=str)

    print(f"{'='*60}")
    print(f"  DGEN complete in {total_elapsed:.1f}s")
    print(f"  Validation report: {val_report_path}")
    print(f"  Data card (EU AI Act Art.10): {data_card_path}")
    print(f"  Overall: {'FAIL — validation errors' if validation_failed else 'PASS'}")
    print(f"{'='*60}\n")

    return 1 if validation_failed else 0


if __name__ == "__main__":
    sys.exit(main())
