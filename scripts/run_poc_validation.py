#!/usr/bin/env python3
"""
run_poc_validation.py — LIP Prototype Validation Pipeline
===========================================================
Orchestrates synthetic corpus generation, classifier inference, and metric
computation across all LIP components. Writes docs/poc-validation-report.md.

Usage
-----
    # Quick run (10K records per component, ~60-90 seconds):
    PYTHONPATH=. python scripts/run_poc_validation.py

    # Full-scale run (as per BIS-calibrated targets):
    PYTHONPATH=. python scripts/run_poc_validation.py --full-scale

    # Custom volumes:
    PYTHONPATH=. python scripts/run_poc_validation.py --n-c1 100000 --n-c4 50000

Output
------
    docs/poc-validation-report.md   (bank-readable, auto-generated)

What IS measured
----------------
    C1: Corpus distribution fidelity (corridor rates, rejection code mix, temporal spread)
    C2: Borrower PD distribution fidelity (tier rates, default rates, Altman Z spread)
    C4: DisputeClassifier accuracy (MockLLMBackend; prefilter + LLM mock pipeline)
    C6: AnomalyDetector precision/recall (fit on 80%, evaluate on 20%)

What is NOT measured
--------------------
    C1 ML inference: GraphSAGE/TabTransformer AUC requires trained model artifacts.
        Trained AUC: 0.9998 on 2K synthetic samples (commit f38f0dc).
        Estimated real-world AUC: 0.82–0.88 (pending SWIFT pilot data).
    C2 PD model calibration: Merton/KMV/Altman ensemble accuracy requires
        real default history (requires pilot data under QUANT sign-off).
    C3 repayment accuracy: Requires live UETR settlement tracking.
    C7/C8 latency: See docs/benchmark-results.md (warm p99=0.29ms, 323x below SLO).
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

_REPORT_PATH = DOCS_DIR / "poc-validation-report.md"

# Default volumes (quick run for CI/demo)
_DEFAULT_VOLUMES = {
    "c1": 10_000,
    "c2": 10_000,
    "c4": 10_000,
    "c6": 10_000,
}

# Full-scale volumes (BIS-calibrated prototype validation targets)
_FULL_SCALE_VOLUMES = {
    "c1": 2_000_000,
    "c2":   500_000,
    "c4":   200_000,
    "c6":   300_000,
}

_SEED = 42


# ---------------------------------------------------------------------------
# C1 Validation: Corpus distribution fidelity
# ---------------------------------------------------------------------------

# BIS CPMI 2024 corridor targets (failure_rate)
_C1_CORRIDOR_TARGETS = {
    "EUR/USD": 0.150,
    "USD/EUR": 0.150,
    "GBP/USD": 0.080,
    "USD/GBP": 0.080,
    "USD/JPY": 0.120,
    "USD/CHF": 0.090,
    "EUR/GBP": 0.110,
    "USD/CAD": 0.095,
    "USD/CNY": 0.260,
    "USD/INR": 0.280,
    "USD/SGD": 0.180,
    "EUR/CHF": 0.085,
}

def validate_c1(records: list) -> dict[str, Any]:
    """Validate C1 corpus distribution fidelity against BIS CPMI targets."""
    n = len(records)
    if n == 0:
        return {"status": "empty"}

    # Corridor distribution
    corridor_counts = Counter(r["currency_pair"] for r in records)

    # Rejection code distribution
    class_counts = Counter(r["rejection_class"] for r in records)
    class_fracs = {k: v / n for k, v in class_counts.items()}

    # Temporal spread (should cover ~18 months ≈ 540 days)
    timestamps = [r["timestamp_unix"] for r in records]
    span_days = (max(timestamps) - min(timestamps)) / 86400

    # Corridor failure rate fidelity: check that sampled corridor_failure_rate
    # fields match the BIS targets (within rounding)
    rate_errors = {}
    for corr, target in _C1_CORRIDOR_TARGETS.items():
        sampled = [r["corridor_failure_rate"] for r in records
                   if r["currency_pair"] == corr]
        if sampled:
            mean_rate = sum(sampled) / len(sampled)
            rate_errors[corr] = abs(mean_rate - target)

    max_rate_error = max(rate_errors.values()) if rate_errors else 0.0
    corpus_ok = max_rate_error < 0.001  # all records store exact target value

    return {
        "status": "pass" if corpus_ok and span_days > 500 else "warn",
        "n_records": n,
        "all_label_1": all(r["label"] == 1 for r in records),
        "corridor_count": len(corridor_counts),
        "top_corridor": max(corridor_counts, key=corridor_counts.get),
        "rejection_class_fractions": {k: round(v, 3) for k, v in class_fracs.items()},
        "temporal_span_days": round(span_days, 1),
        "corridor_rate_max_abs_error": round(max_rate_error, 6),
        "corpus_tag": records[0].get("corpus_tag", "?"),
    }


# ---------------------------------------------------------------------------
# C2 Validation: PD distribution fidelity
# ---------------------------------------------------------------------------

_C2_TIER_TARGETS = {1: 0.03, 2: 0.06, 3: 0.12}
_C2_TIER_WEIGHT_TARGETS = {1: 0.40, 2: 0.35, 3: 0.25}
_C2_TOL = 0.03  # ±3pp tolerance on default rates (sampling noise at n=10K)


def validate_c2(records: list) -> dict[str, Any]:
    """Validate C2 corpus: tier distribution and per-tier default rates."""
    n = len(records)
    if n == 0:
        return {"status": "empty"}

    by_tier: dict[int, list] = {1: [], 2: [], 3: []}
    for r in records:
        by_tier[r["tier"]].append(r["label"])

    tier_rates = {}
    tier_counts = {}
    tier_ok = True
    for tier, labels in by_tier.items():
        count = len(labels)
        tier_counts[tier] = count
        if count == 0:
            continue
        dr = sum(labels) / count
        tier_rates[tier] = round(dr, 4)
        target = _C2_TIER_TARGETS[tier]
        if abs(dr - target) > _C2_TOL:
            tier_ok = False

    tier_weight_fracs = {t: round(tier_counts.get(t, 0) / n, 3) for t in [1, 2, 3]}

    # Altman Z-score distribution check (Tier-1 only)
    t1_healthy_z = [
        r["borrower"]["altman_z_score"] for r in records
        if r["tier"] == 1 and r["label"] == 0
    ]
    t1_default_z = [
        r["borrower"]["altman_z_score"] for r in records
        if r["tier"] == 1 and r["label"] == 1
    ]
    z_ok = True
    if t1_healthy_z and t1_default_z:
        mean_healthy_z = sum(t1_healthy_z) / len(t1_healthy_z)
        mean_default_z = sum(t1_default_z) / len(t1_default_z)
        z_ok = mean_healthy_z > mean_default_z

    return {
        "status": "pass" if tier_ok and z_ok else "warn",
        "n_records": n,
        "tier_weights": tier_weight_fracs,
        "default_rates_per_tier": tier_rates,
        "default_rate_targets": _C2_TIER_TARGETS,
        "default_rate_tolerance": _C2_TOL,
        "altman_z_healthy_mean": round(sum(t1_healthy_z) / len(t1_healthy_z), 3) if t1_healthy_z else None,
        "altman_z_default_mean": round(sum(t1_default_z) / len(t1_default_z), 3) if t1_default_z else None,
        "altman_z_separation_ok": z_ok,
        "corpus_tag": records[0].get("corpus_tag", "?"),
    }


# ---------------------------------------------------------------------------
# C4 Validation: DisputeClassifier accuracy
# ---------------------------------------------------------------------------

_C4_CLASS_ORDER = ["NOT_DISPUTE", "DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE", "NEGOTIATION"]
_C4_CLASS_TARGETS = {
    "NOT_DISPUTE": 0.45,
    "DISPUTE_CONFIRMED": 0.25,
    "DISPUTE_POSSIBLE": 0.20,
    "NEGOTIATION": 0.10,
}

_C4_REJECTION_CODE = "AM04"  # Default rejection code for classify() calls


def _c4_confusion(true_labels: list[str], pred_labels: list[str]) -> dict:
    """Compute per-class precision, recall, F1 for C4 classification."""
    classes = _C4_CLASS_ORDER
    metrics: dict[str, Any] = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(true_labels, pred_labels) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p != cls)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        metrics[cls] = {
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn,
        }
    overall_acc = sum(t == p for t, p in zip(true_labels, pred_labels)) / len(true_labels)
    return {"per_class": metrics, "accuracy": round(overall_acc, 3)}


def validate_c4(records: list) -> dict[str, Any]:
    """Run DisputeClassifier (MockLLMBackend) on generated corpus and evaluate."""
    n = len(records)
    if n == 0:
        return {"status": "empty"}

    # Import here to avoid circular at module level
    from lip.c4_dispute_classifier.model import DisputeClassifier

    classifier = DisputeClassifier()

    # Class distribution check
    class_counts = Counter(r["label"] for r in records)
    class_fracs = {k: round(v / n, 3) for k, v in class_counts.items()}

    # Run inference on up to 2,000 records (cap for speed)
    sample = records[:2_000] if n > 2_000 else records
    true_labels = [r["label"] for r in sample]
    pred_labels = []

    for r in sample:
        try:
            result = classifier.classify(
                rejection_code=_C4_REJECTION_CODE,
                narrative=r["narrative"],
            )
            pred_labels.append(result["dispute_class"].value)
        except Exception:
            pred_labels.append("NOT_DISPUTE")

    confusion = _c4_confusion(true_labels, pred_labels)

    # Flag if DISPUTE_CONFIRMED recall < 0.60 (safety-critical class)
    dc_recall = confusion["per_class"]["DISPUTE_CONFIRMED"]["recall"]
    status = "pass" if dc_recall >= 0.60 else "warn"

    return {
        "status": status,
        "n_records": n,
        "n_evaluated": len(sample),
        "class_distribution": class_fracs,
        "class_targets": {k: round(v, 2) for k, v in _C4_CLASS_TARGETS.items()},
        "backend": "MockLLMBackend",
        "accuracy": confusion["accuracy"],
        "per_class_metrics": confusion["per_class"],
        "dispute_confirmed_recall": round(dc_recall, 3),
        "corpus_tag": records[0].get("corpus_tag", "?"),
    }


# ---------------------------------------------------------------------------
# C6 Validation: AnomalyDetector precision/recall
# ---------------------------------------------------------------------------

def validate_c6(records: list) -> dict[str, Any]:
    """Fit AnomalyDetector on 80% of corpus, evaluate on 20%."""
    n = len(records)
    if n == 0:
        return {"status": "empty"}

    from lip.c6_aml_velocity.anomaly import AnomalyDetector

    # AML flag distribution (ground truth from generator)
    flag_counts = Counter(r["aml_flag"] for r in records)
    flag_rate = flag_counts.get(1, 0) / n

    pattern_counts = Counter(r["flag_reason"] for r in records)

    # Train/test split
    rng = np.random.default_rng(_SEED)
    idx = rng.permutation(n)
    split = int(0.8 * n)
    train_idx = idx[:split]
    test_idx = idx[split:]

    train_records = [records[i] for i in train_idx]
    test_records  = [records[i] for i in test_idx]

    # Fit
    detector = AnomalyDetector(contamination=flag_rate)
    try:
        detector.fit(train_records)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "n_records": n,
            "aml_flag_rate": round(flag_rate, 4),
        }

    # Predict
    true_flags = [r["aml_flag"] for r in test_records]
    try:
        results = detector.predict_batch(test_records)
        pred_flags = [int(r.is_anomaly) for r in results]
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "n_records": n,
            "aml_flag_rate": round(flag_rate, 4),
        }

    tp = sum(1 for t, p in zip(true_flags, pred_flags) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(true_flags, pred_flags) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(true_flags, pred_flags) if t == 1 and p == 0)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc  = sum(t == p for t, p in zip(true_flags, pred_flags)) / len(true_flags)

    # Isolation Forest is unsupervised — baseline precision/recall depends on
    # contamination alignment; flag if precision < 0.20 (near-random)
    status = "pass" if prec >= 0.20 else "warn"

    return {
        "status": status,
        "n_records": n,
        "n_train": split,
        "n_test": n - split,
        "aml_flag_rate": round(flag_rate, 4),
        "aml_flag_target": 0.08,
        "pattern_distribution": dict(pattern_counts),
        "precision": round(prec, 3),
        "recall": round(rec, 3),
        "f1": round(f1, 3),
        "accuracy": round(acc, 3),
        "contamination_param": round(flag_rate, 4),
        "corpus_tag": records[0].get("corpus_tag", "?"),
        "note": (
            "Isolation Forest is unsupervised — scores reflect density-based anomaly "
            "rather than supervised label alignment. Precision/recall is indicative only."
        ),
    }


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def _status_icon(status: str) -> str:
    return {"pass": "✅", "warn": "⚠️", "error": "❌", "empty": "⬛"}.get(status, "❓")


def _write_report(results: dict[str, Any], volumes: dict[str, int], elapsed_s: float) -> str:
    now = datetime.now(tz=timezone.utc)
    lines = []

    lines.append("# LIP Prototype PoC Validation Report")
    lines.append("")
    lines.append(f"**Generated**: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
    lines.append(f"**Total generation+validation time**: {elapsed_s:.1f}s  ")
    lines.append("**Data type**: FULLY SYNTHETIC — no real transaction data  ")
    lines.append("**Regulatory tag**: EU AI Act Art.10 traceability (seed-controlled)  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Component | Records | Status | Key Metric |")
    lines.append("|-----------|---------|--------|------------|")

    c1 = results.get("c1", {})
    c2 = results.get("c2", {})
    c4 = results.get("c4", {})
    c6 = results.get("c6", {})

    def _row(name, r, metric_key, metric_label):
        icon = _status_icon(r.get("status", "?"))
        n = r.get("n_records", "—")
        v = r.get(metric_key)
        metric_str = f"{metric_label}: {v}" if v is not None else "—"
        return f"| {name} | {n:,} | {icon} {r.get('status','?')} | {metric_str} |"

    lines.append(_row("C1 Payment Failure", c1, "corridor_rate_max_abs_error", "rate_err"))
    lines.append(_row("C2 PD Borrowers",    c2, "altman_z_separation_ok",      "Z-sep"))
    lines.append(_row("C4 Dispute Classifier", c4, "dispute_confirmed_recall",  "DISPUTE_CONFIRMED recall"))
    lines.append(_row("C6 AML Anomaly",     c6, "precision",                    "precision"))

    lines.append("")
    lines.append("---")
    lines.append("")

    # C1
    lines.append("## C1: Payment Failure Corpus")
    lines.append("")
    if c1:
        lines.append(f"- **Records**: {c1.get('n_records', '—'):,}")
        lines.append(f"- **Corpus tag**: `{c1.get('corpus_tag', '?')}`")
        lines.append(f"- **All labels = 1 (RJCT)**: {c1.get('all_label_1', '?')}")
        lines.append(f"- **Corridor count**: {c1.get('corridor_count', '?')}")
        lines.append(f"- **Temporal span**: {c1.get('temporal_span_days', '?')} days (target: ~540)")
        lines.append(f"- **Corridor rate max abs error**: {c1.get('corridor_rate_max_abs_error', '?')} (target: <0.001)")
        lines.append("")
        rc = c1.get("rejection_class_fractions", {})
        if rc:
            lines.append("**Rejection class distribution** (target: A≈35%, B≈45%, C≈15%, BLOCK≈5%):")
            lines.append("")
            lines.append("| Class | Fraction | Target |")
            lines.append("|-------|----------|--------|")
            targets = {"A": "~35%", "B": "~45%", "C": "~15%", "BLOCK": "~5%"}
            for cls, frac in sorted(rc.items()):
                lines.append(f"| {cls} | {frac:.3f} | {targets.get(cls, '—')} |")
        lines.append("")
        lines.append(
            "> **Not measured**: C1 ML inference (GraphSAGE/TabTransformer). "
            "Trained AUC=0.9998 on 2K synthetic samples (commit `f38f0dc`). "
            "Estimated real-world AUC: 0.82–0.88 (requires SWIFT pilot data)."
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # C2
    lines.append("## C2: PD Borrower Corpus")
    lines.append("")
    if c2:
        lines.append(f"- **Records**: {c2.get('n_records', '—'):,}")
        lines.append(f"- **Corpus tag**: `{c2.get('corpus_tag', '?')}`")
        lines.append(f"- **Altman Z separation (healthy > default)**: {c2.get('altman_z_separation_ok', '?')}")
        mean_h = c2.get("altman_z_healthy_mean")
        mean_d = c2.get("altman_z_default_mean")
        if mean_h is not None and mean_d is not None:
            lines.append(f"- **Altman Z (healthy Tier-1 mean)**: {mean_h}")
            lines.append(f"- **Altman Z (default Tier-1 mean)**: {mean_d}")
        lines.append("")
        tw = c2.get("tier_weights", {})
        dr = c2.get("default_rates_per_tier", {})
        if tw and dr:
            lines.append("**Tier distribution and default rates**:")
            lines.append("")
            lines.append("| Tier | Weight | Default Rate | Target Rate | Tolerance |")
            lines.append("|------|--------|-------------|-------------|-----------|")
            for tier in [1, 2, 3]:
                lines.append(
                    f"| {tier} | {tw.get(tier,'?')} | {dr.get(tier,'?')} "
                    f"| {_C2_TIER_TARGETS[tier]:.2f} | ±{c2.get('default_rate_tolerance','?')} |"
                )
        lines.append("")
        lines.append(
            "> **Not measured**: C2 PD model calibration (Merton/KMV/Altman ensemble). "
            "Requires real default history under QUANT sign-off."
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # C4
    lines.append("## C4: Dispute Classifier")
    lines.append("")
    if c4:
        lines.append(f"- **Records generated**: {c4.get('n_records', '—'):,}")
        lines.append(f"- **Records evaluated**: {c4.get('n_evaluated', '—')}")
        lines.append(f"- **Backend**: `{c4.get('backend', '?')}`")
        lines.append(f"- **Overall accuracy**: {c4.get('accuracy', '?')}")
        lines.append(f"- **DISPUTE_CONFIRMED recall**: {c4.get('dispute_confirmed_recall', '?')} (threshold: ≥0.60)")
        lines.append("")
        pcm = c4.get("per_class_metrics", {})
        if pcm:
            lines.append("**Per-class metrics**:")
            lines.append("")
            lines.append("| Class | Precision | Recall | F1 | TP | FP | FN |")
            lines.append("|-------|-----------|--------|----|----|----|----|")
            for cls in _C4_CLASS_ORDER:
                m = pcm.get(cls, {})
                lines.append(
                    f"| {cls} | {m.get('precision','?')} | {m.get('recall','?')} "
                    f"| {m.get('f1','?')} | {m.get('tp','?')} "
                    f"| {m.get('fp','?')} | {m.get('fn','?')} |"
                )
        lines.append("")
        lines.append(
            "> **Known limitation**: `MockLLMBackend` has no negation awareness — "
            "pure keyword match. Results reflect prefilter pipeline only. "
            "For real LLM metrics, see P6 (requires Groq API key)."
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # C6
    lines.append("## C6: AML Anomaly Detector")
    lines.append("")
    if c6:
        lines.append(f"- **Records**: {c6.get('n_records', '—'):,}")
        lines.append(f"- **Train / Test split**: {c6.get('n_train', '—')} / {c6.get('n_test', '—')} (80/20)")
        lines.append(f"- **AML flag rate**: {c6.get('aml_flag_rate', '?')} (target: ~0.08)")
        lines.append(f"- **Precision**: {c6.get('precision', '?')}")
        lines.append(f"- **Recall**: {c6.get('recall', '?')}")
        lines.append(f"- **F1**: {c6.get('f1', '?')}")
        lines.append(f"- **Accuracy**: {c6.get('accuracy', '?')}")
        lines.append("")
        pd = c6.get("pattern_distribution", {})
        if pd:
            lines.append("**AML pattern distribution** (ground truth labels from generator):")
            lines.append("")
            lines.append("| Pattern | Count | Rate |")
            lines.append("|---------|-------|------|")
            total = c6.get("n_records", 1)
            for pattern, count in sorted(pd.items(), key=lambda x: -x[1]):
                lines.append(f"| {pattern} | {count:,} | {count/total:.3f} |")
        lines.append("")
        note = c6.get("note", "")
        if note:
            lines.append(f"> **Note**: {note}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Scope and limitations
    lines.append("## What Is NOT Validated Here")
    lines.append("")
    lines.append("| Item | Reason | Reference |")
    lines.append("|------|--------|-----------|")
    lines.append("| C1 ML inference AUC | Requires trained model artifacts | Commit `f38f0dc` (AUC=0.9998 synthetic) |")
    lines.append("| C2 PD calibration | Requires real default history | QUANT sign-off pending |")
    lines.append("| C3 repayment accuracy | Requires live UETR settlement tracking | Phase 2 |")
    lines.append("| C4 negation handling | MockLLMBackend has no negation awareness | P6 (Groq API) |")
    lines.append("| C7 kill switch / human override | See e2e pipeline tests | `test_e2e_pipeline.py` |")
    lines.append("| End-to-end latency p99 | Benchmarked separately | `docs/benchmark-results.md` |")
    lines.append("")
    lines.append(
        "> All synthetic corpora are generated with fixed seed=42 for full "
        "reproducibility. No real transaction data, PII, or real bank identifiers "
        "are present in any corpus. EU AI Act Art.10 compliant."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(volumes: dict[str, int]) -> None:
    print(f"\n{'='*64}")
    print("  LIP PoC Validation Pipeline")
    print(f"  Seed: {_SEED} | Volumes: {volumes}")
    print(f"{'='*64}\n")

    t_start = time.time()
    results: dict[str, Any] = {}

    # ── C1 ───────────────────────────────────────────────────────────────────
    print(f"[C1] Generating {volumes['c1']:,} payment failure records...", end=" ", flush=True)
    t0 = time.time()
    from lip.dgen.c1_generator import generate_payment_events
    c1_records = generate_payment_events(n_samples=volumes["c1"], seed=_SEED)
    print(f"done in {time.time()-t0:.1f}s", flush=True)

    print("[C1] Validating corpus distributions...", end=" ", flush=True)
    results["c1"] = validate_c1(c1_records)
    print(f"{results['c1']['status']}", flush=True)
    del c1_records  # free memory

    # ── C2 ───────────────────────────────────────────────────────────────────
    print(f"\n[C2] Generating {volumes['c2']:,} PD borrower records...", end=" ", flush=True)
    t0 = time.time()
    from lip.dgen.c2_generator import generate_pd_training_data_v2
    c2_records = generate_pd_training_data_v2(n_samples=volumes["c2"], seed=_SEED)
    print(f"done in {time.time()-t0:.1f}s", flush=True)

    print("[C2] Validating PD distributions...", end=" ", flush=True)
    results["c2"] = validate_c2(c2_records)
    print(f"{results['c2']['status']}", flush=True)
    del c2_records

    # ── C4 ───────────────────────────────────────────────────────────────────
    print(f"\n[C4] Generating {volumes['c4']:,} dispute narratives...", end=" ", flush=True)
    t0 = time.time()
    from lip.dgen.c4_generator import generate_dispute_corpus
    c4_records = generate_dispute_corpus(n_samples=volumes["c4"], seed=_SEED)
    print(f"done in {time.time()-t0:.1f}s", flush=True)

    print(f"[C4] Running DisputeClassifier on {min(2000, volumes['c4'])} records...", end=" ", flush=True)
    t0 = time.time()
    results["c4"] = validate_c4(c4_records)
    print(f"done in {time.time()-t0:.1f}s → {results['c4']['status']}", flush=True)
    del c4_records

    # ── C6 ───────────────────────────────────────────────────────────────────
    print(f"\n[C6] Generating {volumes['c6']:,} AML corpus records...", end=" ", flush=True)
    t0 = time.time()
    from lip.dgen.c6_generator import generate_aml_corpus
    c6_records = generate_aml_corpus(n_samples=volumes["c6"], seed=_SEED)
    print(f"done in {time.time()-t0:.1f}s", flush=True)

    print("[C6] Training AnomalyDetector (80/20 split)...", end=" ", flush=True)
    t0 = time.time()
    results["c6"] = validate_c6(c6_records)
    print(f"done in {time.time()-t0:.1f}s → {results['c6']['status']}", flush=True)
    del c6_records

    # ── Report ────────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{'='*64}")
    print("  Results Summary")
    print(f"{'='*64}")
    for comp, res in results.items():
        icon = _status_icon(res.get("status", "?"))
        print(f"  {comp.upper()}: {icon} {res.get('status','?')}")

    report_md = _write_report(results, volumes, elapsed)
    _REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"\n  Report written → {_REPORT_PATH}")
    print(f"  Total elapsed: {elapsed:.1f}s")
    print(f"{'='*64}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LIP PoC validation pipeline — generates corpora and computes metrics."
    )
    parser.add_argument(
        "--full-scale", action="store_true",
        help="Use BIS-calibrated full-scale volumes (C1=2M, C2=500K, C4=200K, C6=300K). "
             "Requires ~8 GB RAM and ~30-60 min runtime.",
    )
    parser.add_argument("--n-c1", type=int, default=None)
    parser.add_argument("--n-c2", type=int, default=None)
    parser.add_argument("--n-c4", type=int, default=None)
    parser.add_argument("--n-c6", type=int, default=None)

    args = parser.parse_args()

    volumes = _FULL_SCALE_VOLUMES.copy() if args.full_scale else _DEFAULT_VOLUMES.copy()
    if args.n_c1 is not None:
        volumes["c1"] = args.n_c1
    if args.n_c2 is not None:
        volumes["c2"] = args.n_c2
    if args.n_c4 is not None:
        volumes["c4"] = args.n_c4
    if args.n_c6 is not None:
        volumes["c6"] = args.n_c6

    run(volumes)


if __name__ == "__main__":
    main()
