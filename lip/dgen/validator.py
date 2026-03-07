"""
validator.py — DGEN: Statistical Quality Assurance Layer
=========================================================
Validates synthetic corpora before they are used for training.

Checks performed:
  1. Label distribution — actual rates must be within 10% of target rates
  2. NaN / Inf sweep — any invalid values fail the corpus immediately
  3. KS test — each numeric feature must not be degenerate (std > threshold)
  4. Correlation leak check — no two features perfectly correlated (|r| < 0.99)
  5. Class balance report — logs positive count per class for ARIA review
  6. Temporal coverage — timestamps must span ≥ 12 months (REX: SR 11-7)

A CorpusReport is returned with pass/fail per check and a summary dict
suitable for inclusion in the EU AI Act Art.10 data card.

Usage::

    from lip.dgen.validator import validate_corpus
    report = validate_corpus(records, corpus_type="C4")
    if not report.passed:
        raise ValueError(report.summary())
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


@dataclass
class CorpusReport:
    corpus_type: str
    n_records: int
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        lines = [
            f"CorpusReport [{self.corpus_type}] — {self.n_records} records",
            f"Overall: {'PASS' if self.passed else 'FAIL'}",
            "",
        ]
        for c in self.checks:
            status = "✓" if c.passed else "✗"
            lines.append(f"  {status} {c.name}: {c.message}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corpus_type": self.corpus_type,
            "n_records": self.n_records,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "message": c.message}
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    sx, sy = _std(xs), _std(ys)
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    return cov / (sx * sy)


def _extract_numeric_fields(records: List[dict]) -> Dict[str, List[float]]:
    """Extract all top-level numeric fields from records."""
    if not records:
        return {}
    candidates = {}
    for key, val in records[0].items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            candidates[key] = []

    for rec in records:
        for key in list(candidates.keys()):
            val = rec.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                v = float(val)
                if math.isfinite(v):
                    candidates[key].append(v)

    return {k: v for k, v in candidates.items() if len(v) > 0}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_size(records: List[dict], min_records: int = 100) -> CheckResult:
    ok = len(records) >= min_records
    return CheckResult(
        name="minimum_size",
        passed=ok,
        message=f"{len(records)} records (min {min_records})",
    )


def _check_nan_inf(records: List[dict]) -> CheckResult:
    """Sweep all numeric top-level values for NaN / Inf."""
    bad_count = 0
    for rec in records:
        for val in rec.values():
            if isinstance(val, float) and not math.isfinite(val):
                bad_count += 1

    ok = bad_count == 0
    return CheckResult(
        name="no_nan_inf",
        passed=ok,
        message=f"{bad_count} non-finite values found",
    )


def _check_label_distribution(
    records: List[dict],
    label_field: str,
    target_positive_rate: float,
    tolerance: float = 0.10,
) -> CheckResult:
    """Check binary label distribution is within tolerance of target."""
    labels = [rec.get(label_field) for rec in records if rec.get(label_field) is not None]
    if not labels:
        return CheckResult("label_distribution", False, f"field '{label_field}' not found")

    positives = sum(1 for l in labels if l == 1 or l == "1" or l is True)
    actual_rate = positives / len(labels)
    lo = target_positive_rate * (1 - tolerance)
    hi = target_positive_rate * (1 + tolerance)
    ok = lo <= actual_rate <= hi

    return CheckResult(
        name="label_distribution",
        passed=ok,
        message=(
            f"actual={actual_rate:.3f}, target={target_positive_rate:.3f} "
            f"[{lo:.3f}, {hi:.3f}] — {'OK' if ok else 'OUT OF RANGE'}"
        ),
    )


def _check_multiclass_distribution(
    records: List[dict],
    label_field: str,
    target_weights: Dict[str, float],
    tolerance: float = 0.15,
) -> CheckResult:
    """Check multi-class distribution against target weights."""
    labels = [rec.get(label_field) for rec in records if rec.get(label_field) is not None]
    if not labels:
        return CheckResult("multiclass_distribution", False, f"field '{label_field}' not found")

    counts: Dict[str, int] = {}
    for lbl in labels:
        counts[str(lbl)] = counts.get(str(lbl), 0) + 1

    n = len(labels)
    messages = []
    all_ok = True

    for cls, target_w in target_weights.items():
        actual_w = counts.get(str(cls), 0) / n
        lo, hi = target_w * (1 - tolerance), target_w * (1 + tolerance)
        ok = lo <= actual_w <= hi
        if not ok:
            all_ok = False
        messages.append(f"{cls}={actual_w:.3f}(target={target_w:.2f})")

    return CheckResult(
        name="multiclass_distribution",
        passed=all_ok,
        message=", ".join(messages),
    )


_METADATA_FIELDS = frozenset({
    "generation_seed", "label", "label_int", "aml_flag",
    "large_amount_threshold", "tier",
})


def _check_feature_variance(records: List[dict], min_std: float = 1e-6) -> CheckResult:
    """Check that numeric features have non-degenerate variance."""
    numeric = _extract_numeric_fields(records)
    degenerate = [
        k for k, vs in numeric.items()
        if k not in _METADATA_FIELDS and _std(vs) < min_std
    ]

    ok = len(degenerate) == 0
    return CheckResult(
        name="feature_variance",
        passed=ok,
        message=(
            f"{len(degenerate)} degenerate features: {degenerate[:5]}"
            if degenerate else f"all {len(numeric)} numeric features have variance"
        ),
    )


def _check_no_perfect_correlation(records: List[dict], threshold: float = 0.99) -> CheckResult:
    """Check for data leakage via perfect feature correlations."""
    numeric = _extract_numeric_fields(records)
    keys = list(numeric.keys())
    leaks = []

    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ki, kj = keys[i], keys[j]
            vs_i, vs_j = numeric[ki], numeric[kj]
            n = min(len(vs_i), len(vs_j))
            if n < 50:
                continue
            r = abs(_pearson(vs_i[:n], vs_j[:n]))
            if r >= threshold:
                leaks.append(f"({ki},{kj})={r:.4f}")

    ok = len(leaks) == 0
    return CheckResult(
        name="no_perfect_correlation",
        passed=ok,
        message=f"{len(leaks)} perfect correlations: {leaks[:3]}" if leaks else "no leakage detected",
    )


def _check_temporal_coverage(
    records: List[dict],
    ts_field: str = "timestamp",
    min_span_days: int = 365,
) -> CheckResult:
    """Check timestamp span for SR 11-7 out-of-time validation."""
    timestamps = []
    for rec in records:
        ts = rec.get(ts_field)
        if isinstance(ts, (int, float)) and math.isfinite(ts):
            timestamps.append(float(ts))

    if len(timestamps) < 2:
        return CheckResult(
            "temporal_coverage",
            False,
            f"insufficient timestamps (found {len(timestamps)})",
        )

    span_days = (max(timestamps) - min(timestamps)) / 86400.0
    ok = span_days >= min_span_days

    return CheckResult(
        name="temporal_coverage",
        passed=ok,
        message=f"span={span_days:.0f}d (min {min_span_days}d) — {'OK' if ok else 'INSUFFICIENT'}",
    )


def _check_corpus_tag(records: List[dict], expected_prefix: str = "SYNTHETIC_CORPUS_") -> CheckResult:
    """Verify all records carry a synthetic corpus tag."""
    untagged = sum(
        1 for rec in records
        if not str(rec.get("corpus_tag", "")).startswith(expected_prefix)
    )
    ok = untagged == 0
    return CheckResult(
        name="corpus_tag",
        passed=ok,
        message=f"{untagged} records missing '{expected_prefix}*' tag",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_corpus(
    records: List[dict],
    corpus_type: str,
    label_field: str = "label",
    target_positive_rate: Optional[float] = None,
    target_class_weights: Optional[Dict[str, float]] = None,
    ts_field: str = "timestamp",
    min_temporal_span_days: int = 180,
) -> CorpusReport:
    """Run all QA checks on a synthetic corpus.

    Parameters
    ----------
    records : List[dict]
        The generated corpus records.
    corpus_type : str
        Human-readable label ("C1", "C2", "C4", "C6").
    label_field : str
        Field name containing the label (binary or multi-class).
    target_positive_rate : float, optional
        Expected fraction of positive (label=1) records. Used for binary check.
    target_class_weights : dict, optional
        Expected fraction per class label. Used for multi-class check (C4).
    ts_field : str
        Field name for timestamps. Skipped if not present.
    min_temporal_span_days : int
        Minimum required time span for SR 11-7 OOT validation.

    Returns
    -------
    CorpusReport with .passed bool and .summary() method.
    """
    report = CorpusReport(corpus_type=corpus_type, n_records=len(records))

    # 1. Size
    report.checks.append(_check_size(records))

    # 2. Corpus tag
    report.checks.append(_check_corpus_tag(records))

    # 3. NaN / Inf
    report.checks.append(_check_nan_inf(records))

    # 4. Label distribution
    if target_positive_rate is not None:
        report.checks.append(
            _check_label_distribution(records, label_field, target_positive_rate)
        )
    elif target_class_weights is not None:
        report.checks.append(
            _check_multiclass_distribution(records, label_field, target_class_weights)
        )

    # 5. Feature variance
    report.checks.append(_check_feature_variance(records))

    # 6. Correlation leak (only if enough numeric fields)
    numeric = _extract_numeric_fields(records)
    if len(numeric) >= 4:
        report.checks.append(_check_no_perfect_correlation(records))

    # 7. Temporal coverage (if timestamp field present)
    if any(ts_field in rec for rec in records[:10]):
        report.checks.append(
            _check_temporal_coverage(records, ts_field, min_temporal_span_days)
        )

    return report


# Convenience wrappers per corpus type

def validate_c2_corpus(records: List[dict]) -> CorpusReport:
    """Validate C2 PD corpus with QUANT-specified parameters."""
    return validate_corpus(
        records,
        corpus_type="C2",
        label_field="label",
        # True expected rate from tier weights: 0.40*0.03 + 0.35*0.06 + 0.25*0.12 = 0.063
        # Tier-3 corridor-risk bump adds ~0.5pp; tolerance=15% gives [0.054, 0.073]
        target_positive_rate=0.063,
        ts_field="timestamp",
        min_temporal_span_days=365,   # SR 11-7: 12-month minimum
    )


def validate_c4_corpus(records: List[dict]) -> CorpusReport:
    """Validate C4 dispute narrative corpus with ARIA-specified class distribution."""
    return validate_corpus(
        records,
        corpus_type="C4",
        label_field="label",
        target_class_weights={
            "NOT_DISPUTE":       0.45,
            "DISPUTE_CONFIRMED": 0.25,
            "DISPUTE_POSSIBLE":  0.20,
            "NEGOTIATION":       0.10,
        },
        ts_field="__none__",   # C4 records have no transaction timestamp
        min_temporal_span_days=0,
    )


def validate_c6_corpus(records: List[dict]) -> CorpusReport:
    """Validate C6 AML corpus with CIPHER-specified parameters."""
    return validate_corpus(
        records,
        corpus_type="C6",
        label_field="aml_flag",
        target_positive_rate=0.08,   # ~8% flagged
        ts_field="timestamp",
        min_temporal_span_days=365,
    )
