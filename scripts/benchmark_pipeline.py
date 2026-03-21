#!/usr/bin/env python3
"""
benchmark_pipeline.py — End-to-end LIP pipeline latency benchmark.

Measures wall-clock latency for 1,000 synthetic payment events processed
through the full C1→C4∥C6→C2→C7→C3 pipeline.

Two measurement modes
---------------------
MOCK MODE (default):
    C1 and C2 use deterministic mock engines returning pre-set probabilities.
    Measures: pipeline orchestration, C4 keyword prefilter, C6 velocity
              check + record, C7 decision + HMAC signing, LoanOffer assembly.
    Does NOT include: GNN/TabTransformer/LightGBM inference or SHAP.

COLD vs WARM path:
    First 100 events = cold (JIT compilation, thread pool startup).
    Remaining 900 events = warm (steady-state; used for SLO assessment).

Outputs
-------
- Console: per-percentile table
- docs/benchmark-results.md: auto-generated report (suitable for bank CTO review)

Usage
-----
    PYTHONPATH=. python scripts/benchmark_pipeline.py
    PYTHONPATH=. python scripts/benchmark_pipeline.py --n 2000 --cold 200

SLO target: p99 ≤ 94ms (canonical; LATENCY_SLO_MS in constants.py)
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

# ── ensure repo root is importable ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c5_streaming.event_normalizer import NormalizedEvent
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.constants import LATENCY_SLO_MS
from lip.pipeline import LIPPipeline

# ── Mock engines (no ML inference) ───────────────────────────────────────────

class _MockC1:
    """Returns a fixed failure probability — no GNN/SHAP overhead."""

    def __init__(self, failure_probability: float = 0.80) -> None:
        self._fp = failure_probability

    def predict(self, event: NormalizedEvent) -> dict:
        return {
            "failure_probability": self._fp,
            "inference_latency_ms": 0.0,
            "shap_top20": [],
        }


class _MockC2:
    """Returns a fixed PD + fee — no LightGBM ensemble overhead."""

    def __init__(self, pd_score: float = 0.05, fee_bps: int = 300, tier: int = 3) -> None:
        self._pd = pd_score
        self._fee = fee_bps
        self._tier = tier

    def predict(self, event: NormalizedEvent, failure_probability: float) -> dict:
        return {
            "pd_score": self._pd,
            "fee_bps": self._fee,
            "tier": self._tier,
        }


# ── Synthetic event factory ───────────────────────────────────────────────────

# ISO 20022 rejection codes sampled from BIS CPMI statistics:
#   Class A (3d maturity): ~35%  — minor technical rejects
#   Class B (7d maturity): ~45%  — liquidity / cover rejects
#   Class C (21d maturity): ~20% — compliance / sanctions suspensions
_REJECTION_CODES = (
    # Class A
    ["AC01"] * 7 + ["AC04"] * 5 + ["AC06"] * 3 +
    # Class B
    ["AM04"] * 9 + ["AM05"] * 6 + ["CUST"] * 5 + ["RR01"] * 4 +
    # Class C
    ["FRAU"] * 4 + ["NOAS"] * 4 + ["LEGL"] * 3 + ["AC13"] * 3
)

_CURRENCIES = ["USD"] * 55 + ["EUR"] * 20 + ["GBP"] * 15 + ["JPY"] * 5 + ["CAD"] * 5

_BICS = [f"BANK{i:04d}XX" for i in range(1, 51)]   # 50 synthetic BICs


def _make_event(seed: int) -> NormalizedEvent:
    """Create a deterministic synthetic NormalizedEvent from a seed integer."""
    rng = seed  # simple LCG for reproducibility
    bic_idx = rng % len(_BICS)
    curr_idx = (rng * 31337) % len(_CURRENCIES)
    code_idx = (rng * 97) % len(_REJECTION_CODES)
    amount = Decimal(str(1_000 + (rng * 7919) % 9_000_000))

    return NormalizedEvent(
        uetr=str(uuid.UUID(int=rng * 999983 % (2**128))),
        individual_payment_id=f"IPID-{seed:06d}",
        sending_bic=_BICS[bic_idx],
        receiving_bic=_BICS[(bic_idx + 1) % len(_BICS)],
        amount=amount,
        currency=_CURRENCIES[curr_idx],
        rejection_code=_REJECTION_CODES[code_idx],
        rail="SWIFT",
        timestamp=datetime.now(tz=timezone.utc),
    )


# ── Pipeline factory ──────────────────────────────────────────────────────────

_HMAC_KEY = b"benchmark-hmac-key-32-bytes-long!!"
_SALT = b"benchmark-salt-32-bytes-long!!!!!"


def _build_pipeline(failure_probability: float = 0.80) -> LIPPipeline:
    """Build pipeline with mock ML components and real C4/C6/C7."""
    ks = KillSwitch()
    dm = DegradedModeManager()
    dl = DecisionLogger(hmac_key=_HMAC_KEY)
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)  # disable human review
    agent = ExecutionAgent(
        kill_switch=ks,
        decision_logger=dl,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=dm,
        config=cfg,
    )
    return LIPPipeline(
        c1_engine=_MockC1(failure_probability),
        c2_engine=_MockC2(),
        c4_classifier=DisputeClassifier(llm_backend=MockLLMBackend()),
        c6_checker=VelocityChecker(salt=_SALT),
        c7_agent=agent,
    )


# ── Benchmark runner ──────────────────────────────────────────────────────────

def _percentile(data: List[float], p: float) -> float:
    """Return the p-th percentile (0–100) of sorted data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    lo = int(k)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[-1]
    frac = k - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def run_benchmark(n_events: int = 1000, n_cold: int = 100) -> dict:
    """Run the benchmark and return a results dict."""
    print("Building pipeline (mock C1/C2, real C4+C6+C7)...")
    pipeline = _build_pipeline(failure_probability=0.80)

    events = [_make_event(i) for i in range(n_events)]

    cold_latencies: List[float] = []
    warm_latencies: List[float] = []
    outcomes: dict[str, int] = {}

    print(f"Running {n_events} events ({n_cold} cold, {n_events - n_cold} warm)...")

    for i, event in enumerate(events):
        t0 = time.perf_counter()
        result = pipeline.process(event)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        status = result.outcome if hasattr(result, "outcome") else str(result.get("outcome", "?"))
        outcomes[status] = outcomes.get(status, 0) + 1

        if i < n_cold:
            cold_latencies.append(elapsed_ms)
        else:
            warm_latencies.append(elapsed_ms)

        if (i + 1) % 100 == 0:
            print(f"  [{i + 1:>4}/{n_events}] last={elapsed_ms:.1f}ms")

    warm = warm_latencies
    cold = cold_latencies

    results = {
        "n_events": n_events,
        "n_cold": n_cold,
        "n_warm": len(warm),
        "slo_ms": LATENCY_SLO_MS,
        "cold": {
            "p50":  _percentile(cold, 50),
            "p95":  _percentile(cold, 95),
            "p99":  _percentile(cold, 99),
            "p999": _percentile(cold, 99.9),
            "mean": statistics.mean(cold) if cold else 0.0,
            "max":  max(cold) if cold else 0.0,
        },
        "warm": {
            "p50":  _percentile(warm, 50),
            "p95":  _percentile(warm, 95),
            "p99":  _percentile(warm, 99),
            "p999": _percentile(warm, 99.9),
            "mean": statistics.mean(warm) if warm else 0.0,
            "max":  max(warm) if warm else 0.0,
        },
        "outcomes": outcomes,
        "slo_passed": _percentile(warm, 99) <= LATENCY_SLO_MS,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    return results


def _print_table(results: dict) -> None:
    """Print a human-readable summary table."""
    slo = results["slo_ms"]
    warm = results["warm"]
    cold = results["cold"]

    print("\n" + "=" * 60)
    print("  LIP Pipeline Latency Benchmark")
    print("=" * 60)
    print("  Mode:       mock C1/C2, real C4+C6+C7+HMAC")
    print(f"  Events:     {results['n_events']} ({results['n_cold']} cold, {results['n_warm']} warm)")
    print(f"  SLO target: p99 ≤ {slo}ms (LATENCY_SLO_MS)")
    print()
    print(f"  {'Metric':<12} {'COLD':>12} {'WARM':>12}")
    print(f"  {'-'*12} {'-'*12} {'-'*12}")
    for label, key in [("p50", "p50"), ("p95", "p95"), ("p99", "p99"), ("p999", "p999"), ("mean", "mean"), ("max", "max")]:
        cold_val = f"{cold[key]:.2f}ms"
        warm_val = f"{warm[key]:.2f}ms"
        flag = " ← SLO" if key == "p99" else ""
        print(f"  {label:<12} {cold_val:>12} {warm_val:>12}{flag}")
    print()
    slo_status = "✓ PASS" if results["slo_passed"] else "✗ FAIL"
    print(f"  SLO status: {slo_status} (warm p99={warm['p99']:.2f}ms vs {slo}ms)")
    print()
    print("  Outcome distribution (warm):")
    for outcome, count in sorted(results["outcomes"].items(), key=lambda x: -x[1]):
        print(f"    {outcome}: {count}")
    print("=" * 60)


def _write_report(results: dict, output_path: str) -> None:
    """Write a markdown benchmark report."""
    warm = results["warm"]
    cold = results["cold"]
    slo = results["slo_ms"]
    slo_status = "PASS ✓" if results["slo_passed"] else "FAIL ✗"

    lines = [
        "# LIP Pipeline Latency Benchmark Results",
        "",
        f"**Generated**: {results['timestamp']}  ",
        "**Mode**: Mock C1/C2, real C4 + C6 + C7 (HMAC decision log)  ",
        f"**Events**: {results['n_events']} total ({results['n_cold']} cold warm-up, {results['n_warm']} warm steady-state)  ",
        f"**SLO target**: p99 ≤ {slo}ms (`LATENCY_SLO_MS` in `common/constants.py`)  ",
        "",
        "## What Is Measured",
        "",
        "The benchmark exercises the **full pipeline execution path** excluding ML inference:",
        "",
        "| Stage | Measured? | Notes |",
        "|-------|-----------|-------|",
        "| C1 failure classifier | Mock only | Returns fixed 0.80 prob; GNN+TabTransformer+SHAP NOT timed |",
        "| C2 PD model | Mock only | Returns fixed PD=0.05, fee=300bps; LightGBM ensemble NOT timed |",
        "| C4 dispute classifier | **Real** | Keyword prefilter + MockLLMBackend (same as CI) |",
        "| C6 AML velocity | **Real** | In-memory counters + Jaccard OFAC match |",
        "| C7 execution agent | **Real** | 10-gate decision + HMAC-SHA256 signing + LoanOffer assembly |",
        "| Pipeline orchestration | **Real** | ThreadPoolExecutor for C4∥C6, gate logic, state machines |",
        "",
        "> **Note**: Add real C1/C2 inference time (train models, run `scripts/train_all.py`) for full SLO validation.",
        "> Real-world C1 inference with `_SHAP_STEPS=5` is estimated at 10–40ms; see `c1_failure_classifier/inference.py:36`.",
        "",
        "## Results",
        "",
        "### Cold Path (first 100 events — JIT + thread pool startup)",
        "",
        "| Metric | Latency |",
        "|--------|---------|",
        f"| p50    | {cold['p50']:.2f} ms |",
        f"| p95    | {cold['p95']:.2f} ms |",
        f"| p99    | {cold['p99']:.2f} ms |",
        f"| p99.9  | {cold['p999']:.2f} ms |",
        f"| mean   | {cold['mean']:.2f} ms |",
        f"| max    | {cold['max']:.2f} ms |",
        "",
        "### Warm Path (steady-state — used for SLO assessment)",
        "",
        "| Metric | Latency | SLO |",
        "|--------|---------|-----|",
        f"| p50    | {warm['p50']:.2f} ms | — |",
        f"| p95    | {warm['p95']:.2f} ms | — |",
        f"| **p99**    | **{warm['p99']:.2f} ms** | **≤ {slo}ms** |",
        f"| p99.9  | {warm['p999']:.2f} ms | — |",
        f"| mean   | {warm['mean']:.2f} ms | — |",
        f"| max    | {warm['max']:.2f} ms | — |",
        "",
        f"### SLO Verdict: {slo_status}",
        "",
        f"Warm-path p99 = **{warm['p99']:.2f}ms** vs SLO target of **{slo}ms**.",
        "",
    ]

    if results["slo_passed"]:
        headroom = slo - warm["p99"]
        lines += [
            f"Pipeline has **{headroom:.1f}ms headroom** at p99 before real ML inference.",
            "Add measured C1+C2 inference latency (train models first) to validate full SLO.",
        ]
    else:
        excess = warm["p99"] - slo
        lines += [
            f"Pipeline **exceeds SLO by {excess:.1f}ms** even before adding ML inference.",
            "Consider: reducing C7 gate count, switching to async HMAC signing, or revising SLO with QUANT sign-off.",
        ]

    lines += [
        "",
        "## Outcome Distribution (warm path)",
        "",
        "| Outcome | Count |",
        "|---------|-------|",
    ]
    for outcome, count in sorted(results["outcomes"].items(), key=lambda x: -x[1]):
        lines.append(f"| {outcome} | {count} |")

    lines += [
        "",
        "## Methodology Notes",
        "",
        "- Latency = wall-clock `time.perf_counter()` delta wrapping `LIPPipeline.process()`",
        "- Cold path: first 100 events (JIT warm-up, Python GC pressure, thread pool creation)",
        "- Warm path: remaining events (steady-state, used for SLO verdict)",
        "- Events: 1,000 synthetic ISO 20022 RJCT events with randomised BIC/currency/rejection-code",
        "- UETR uniqueness: guaranteed per event (UUID from seed); no RETRY_BLOCKED events",
        "- Failure probability set to 0.80 (above τ*=0.110) → all warm events reach C7",
        "- VelocityChecker: in-memory Redis mock (no network I/O)",
        "- DecisionLogger: in-memory HMAC (no disk I/O)",
        "",
        "---",
        "_Auto-generated by `scripts/benchmark_pipeline.py` — do not edit manually._",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nReport written to: {output_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LIP pipeline latency benchmark")
    parser.add_argument("--n", type=int, default=1000, help="Total events (default: 1000)")
    parser.add_argument("--cold", type=int, default=100, help="Cold warm-up events (default: 100)")
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "benchmark-results.md"),
        help="Output markdown file path",
    )
    args = parser.parse_args()

    results = run_benchmark(n_events=args.n, n_cold=args.cold)
    _print_table(results)
    _write_report(results, args.output)

    sys.exit(0 if results["slo_passed"] else 1)


if __name__ == "__main__":
    main()
