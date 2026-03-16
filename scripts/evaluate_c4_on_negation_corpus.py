#!/usr/bin/env python3
"""
evaluate_c4_on_negation_corpus.py — C4 Dispute Classifier: Full Negation Corpus Evaluation
============================================================================================
Runs the 500-case negation test suite through the real Groq LLM backend
and reports FN/FP rates per category. Updates common/constants.py if
the measured rate differs significantly from the current constant.

Usage:
    export GROQ_API_KEY=gsk_...
    PYTHONPATH=. python scripts/evaluate_c4_on_negation_corpus.py

    # Dry run (no constants update):
    PYTHONPATH=. python scripts/evaluate_c4_on_negation_corpus.py --no-update

    # Smaller sample for quick validation:
    PYTHONPATH=. python scripts/evaluate_c4_on_negation_corpus.py --n-per-category 20

Output:
    - Console report with per-category FN/FP rates
    - Optional update to lip/common/constants.py (DISPUTE_FN_CURRENT)

What is measured:
    False Negative Rate: DISPUTE_CONFIRMED cases incorrectly classified as
    anything other than DISPUTE_CONFIRMED.
    False Positive Rate: NOT_DISPUTE cases incorrectly classified as
    DISPUTE_CONFIRMED (triggered by negated dispute keywords).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "qwen/qwen3-32b"
_NO_THINK_SUFFIX = "\n/no_think"
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class _Qwen3GroqBackend:
    """Groq-hosted Qwen3-32b with thinking mode disabled."""

    def __init__(self) -> None:
        from openai import OpenAI
        self._client = OpenAI(base_url=_GROQ_BASE_URL, api_key=GROQ_API_KEY)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 20,
        timeout: float = 15.0,
    ) -> str:
        resp = self._client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt + _NO_THINK_SUFFIX},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=64,
            temperature=0.0,   # greedy decoding for reproducibility
            # No stop tokens — /no_think suppresses <think> blocks;
            # _THINK_PATTERN strips residual. stop=[" "] halts generation
            # inside an unclosed <think> tag, breaking the regex.
            timeout=timeout,
        )
        raw = resp.choices[0].message.content or ""
        return _THINK_PATTERN.sub("", raw).strip()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def run_evaluation(n_per_category: int = 100) -> dict:
    from lip.c4_dispute_classifier.model import DisputeClassifier
    from lip.c4_dispute_classifier.negation import generate_negation_test_suite

    backend = _Qwen3GroqBackend()
    classifier = DisputeClassifier(llm_backend=backend, timeout_seconds=15.0)
    cases = generate_negation_test_suite(n_per_category=n_per_category)

    total = len(cases)
    print(f"\n{'='*64}")
    print(f"  C4 Negation Corpus Evaluation — {_GROQ_MODEL}")
    print(f"  Cases: {total} ({n_per_category} per category)")
    print(f"  Time: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*64}\n")

    # Results by category
    results: dict[str, list[dict]] = defaultdict(list)

    for i, case in enumerate(cases):
        # Rate limit guard: Groq large models ~30 req/min free tier
        if i > 0 and i % 25 == 0:
            print(f"  [{i}/{total}] Pausing 5s for rate limit...")
            time.sleep(5.0)

        rejection_code = case.rejection_code or "AM04"
        t0 = time.monotonic()
        try:
            result = classifier.classify(
                rejection_code=rejection_code,
                narrative=case.narrative,
            )
            predicted = result["dispute_class"].value
            latency_ms = (time.monotonic() - t0) * 1000.0
        except Exception as e:
            predicted = "ERROR"
            latency_ms = (time.monotonic() - t0) * 1000.0
            print(f"  ERROR on case {i}: {e}")

        expected = case.expected_class.value
        correct = (predicted == expected)

        results[case.category.value].append({
            "case_id": case.case_id,
            "narrative": case.narrative[:80],
            "expected": expected,
            "predicted": predicted,
            "correct": correct,
            "latency_ms": latency_ms,
        })

        if i % 50 == 0:
            correct_so_far = sum(
                r["correct"] for cat_results in results.values()
                for r in cat_results
            )
            total_so_far = sum(len(v) for v in results.values())
            print(f"  [{i+1}/{total}] Running accuracy: {correct_so_far}/{total_so_far} "
                  f"= {correct_so_far/max(total_so_far,1):.1%}")

        time.sleep(0.5)  # ~2 req/s baseline pacing

    return dict(results)


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_metrics(results: dict) -> dict:
    """Compute FN/FP rates per category and overall."""
    summary = {}

    all_records = [r for cat in results.values() for r in cat]
    total = len(all_records)
    correct_total = sum(r["correct"] for r in all_records)

    for category, records in sorted(results.items()):
        n = len(records)
        correct = sum(r["correct"] for r in records)

        # False negatives: expected DISPUTE_CONFIRMED, got something else
        dispute_cases = [r for r in records if r["expected"] == "DISPUTE_CONFIRMED"]
        fn = sum(1 for r in dispute_cases if not r["correct"])
        fn_rate = fn / len(dispute_cases) if dispute_cases else None

        # False positives: expected NOT_DISPUTE, got DISPUTE_CONFIRMED
        not_dispute_cases = [r for r in records if r["expected"] == "NOT_DISPUTE"]
        fp = sum(1 for r in not_dispute_cases
                 if r["predicted"] == "DISPUTE_CONFIRMED")
        fp_rate = fp / len(not_dispute_cases) if not_dispute_cases else None

        # Latency
        latencies = [r["latency_ms"] for r in records]
        p50 = sorted(latencies)[int(0.50 * len(latencies))]
        p95 = sorted(latencies)[int(0.95 * len(latencies))]

        summary[category] = {
            "n": n,
            "accuracy": correct / n,
            "fn_dispute_confirmed": fn,
            "fn_rate": fn_rate,
            "fp_not_dispute": fp,
            "fp_rate": fp_rate,
            "latency_p50_ms": round(p50, 1),
            "latency_p95_ms": round(p95, 1),
        }

    # Overall
    all_dispute = [r for r in all_records if r["expected"] == "DISPUTE_CONFIRMED"]
    all_not = [r for r in all_records if r["expected"] == "NOT_DISPUTE"]
    overall_fn = sum(1 for r in all_dispute if not r["correct"])
    overall_fp = sum(1 for r in all_not if r["predicted"] == "DISPUTE_CONFIRMED")

    summary["_OVERALL"] = {
        "n": total,
        "accuracy": correct_total / total,
        "fn_dispute_confirmed": overall_fn,
        "fn_rate": overall_fn / len(all_dispute) if all_dispute else None,
        "fp_not_dispute": overall_fp,
        "fp_rate": overall_fp / len(all_not) if all_not else None,
    }

    return summary


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def print_report(metrics: dict, model: str) -> None:
    print(f"\n{'='*64}")
    print(f"  RESULTS — {model}")
    print(f"{'='*64}\n")

    print(f"  {'Category':<35} {'Acc':>6} {'FN%':>6} {'FP%':>6} {'p95ms':>7}")
    print(f"  {'─'*60}")

    for category, m in sorted(metrics.items()):
        if category == "_OVERALL":
            continue
        acc_str = f"{m['accuracy']:.1%}"
        fn_str = f"{m['fn_rate']:.1%}" if m["fn_rate"] is not None else "  N/A"
        fp_str = f"{m['fp_rate']:.1%}" if m["fp_rate"] is not None else "  N/A"
        p95_str = f"{m['latency_p95_ms']:.0f}" if "latency_p95_ms" in m else "—"
        print(f"  {category:<35} {acc_str:>6} {fn_str:>6} {fp_str:>6} {p95_str:>7}")

    print(f"  {'─'*60}")
    ov = metrics["_OVERALL"]
    fn_str = f"{ov['fn_rate']:.1%}" if ov["fn_rate"] is not None else "N/A"
    fp_str = f"{ov['fp_rate']:.1%}" if ov["fp_rate"] is not None else "N/A"
    print(f"  {'OVERALL':<35} {ov['accuracy']:>6.1%} {fn_str:>6} {fp_str:>6}")
    print("\n  MockLLMBackend baseline (from poc-validation-report.md):")
    print(f"  {'MOCK':<35} {'59.9%':>6} {'47.2%':>6} {'0.1%':>6}")
    print(f"\n{'='*64}\n")


# ---------------------------------------------------------------------------
# Constants update
# ---------------------------------------------------------------------------

def update_constants(fn_rate: float, commit_hash: str = "evaluate_c4") -> None:
    """Update DISPUTE_FN_CURRENT in lip/common/constants.py."""
    constants_path = REPO_ROOT / "lip" / "common" / "constants.py"
    content = constants_path.read_text()

    # Find existing DISPUTE_FN_CURRENT line
    import re as re_mod
    pattern = re_mod.compile(r"^DISPUTE_FN_CURRENT\s*=.*$", re_mod.MULTILINE)
    new_line = (
        f"DISPUTE_FN_CURRENT = {fn_rate:.4f}  "
        f"# LLM={_GROQ_MODEL} n=500 commit={commit_hash}"
    )
    if pattern.search(content):
        updated = pattern.sub(new_line, content)
        constants_path.write_text(updated)
        print(f"  Updated DISPUTE_FN_CURRENT = {fn_rate:.4f} in {constants_path}")
    else:
        print(f"  NOTE: DISPUTE_FN_CURRENT not found in {constants_path} — skipping update.")
        print(f"  Add manually: {new_line}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate C4 DisputeClassifier on negation corpus using real LLM."
    )
    parser.add_argument(
        "--n-per-category", type=int, default=100,
        help="Cases per negation category (default: 100 = 500 total).",
    )
    parser.add_argument(
        "--no-update", action="store_true",
        help="Do not update constants.py with measured FN rate.",
    )
    args = parser.parse_args()

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set.", file=sys.stderr)
        print("  Get a free key at console.groq.com", file=sys.stderr)
        print("  Then: export GROQ_API_KEY=gsk_...", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI  # noqa: F401
    except ImportError:
        print("ERROR: openai package required. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    results = run_evaluation(n_per_category=args.n_per_category)
    metrics = compute_metrics(results)
    print_report(metrics, model=_GROQ_MODEL)

    overall_fn_rate = metrics["_OVERALL"]["fn_rate"]

    if not args.no_update and overall_fn_rate is not None:
        print(f"\nUpdating constants.py with FN rate = {overall_fn_rate:.4f}...")
        update_constants(fn_rate=overall_fn_rate, commit_hash=_GROQ_MODEL)
    elif args.no_update:
        print(f"\n--no-update specified. Measured FN rate: {overall_fn_rate:.4f}")
        print("To update manually, add to constants.py:")
        print(f"  DISPUTE_FN_CURRENT = {overall_fn_rate:.4f}  # LLM={_GROQ_MODEL} n=500")
    else:
        print("\nNo FN rate computed (no DISPUTE_CONFIRMED cases in corpus?).")


if __name__ == "__main__":
    main()
