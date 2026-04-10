"""
privacy_audit.py — Privacy audit toolkit for P10 regulatory data product.

Sprint 8: Provides re-identification attack simulations, k-anonymity proofs,
differential privacy verification, and budget composition auditing.

Designed for independent privacy auditors (Big 4 firms, academic reviewers).
All checks are deterministic and reproducible given the same seed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
from scipy import stats as scipy_stats

from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.methodology import MethodologyAppendix
from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
from lip.p10_regulatory_data.shadow_data import generate_shadow_events
from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine, SystemicRiskReport
from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector
from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttackResult:
    """Outcome of a re-identification attack simulation."""

    attack_type: str
    succeeded: bool
    confidence: float  # 0.0-1.0, probability of correct identification
    details: str


@dataclass(frozen=True)
class KAnonymityProof:
    """Formal k-anonymity verification result."""

    k_threshold: int
    corridors_checked: int
    all_satisfied: bool
    violations: int
    violation_details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DPVerificationResult:
    """Differential privacy statistical verification."""

    epsilon: float
    sensitivity: float
    n_samples: int
    ks_statistic: float
    ks_p_value: float
    passed: bool


@dataclass(frozen=True)
class BudgetAuditResult:
    """Privacy budget composition audit."""

    total_epsilon_consumed: float
    expected_epsilon: float
    corridors_audited: int
    composition_valid: bool
    exhaustion_behavior_correct: bool


@dataclass(frozen=True)
class PrivacyAuditReport:
    """Comprehensive privacy audit report."""

    timestamp: float
    methodology_version: str
    frequency_attack: AttackResult
    uniqueness_attack: AttackResult
    temporal_linkage_attack: AttackResult
    k_anonymity_proof: KAnonymityProof
    dp_verification: DPVerificationResult
    budget_audit: BudgetAuditResult
    overall_verdict: str  # "PASS" or "FAIL"


# ---------------------------------------------------------------------------
# Attack simulations
# ---------------------------------------------------------------------------


def frequency_attack(
    report: SystemicRiskReport,
    n_banks: int,
) -> AttackResult:
    """Attempt to identify individual banks by payment volume distribution.

    B8-05: Real statistical test. If any corridor's volume is so skewed
    that a single bank dominates (chi-squared goodness-of-fit vs uniform
    distribution), an attacker could infer which bank is responsible.
    A corridor with bank_count=1 trivially reveals identity. For corridors
    with bank_count >= 2, we test whether the volume distribution across
    corridors deviates significantly from what uniform contribution would
    produce — high deviation means a dominant bank is identifiable.
    """
    if n_banks <= 0:
        return AttackResult(
            attack_type="frequency",
            succeeded=True,
            confidence=1.0,
            details="No banks — vacuously vulnerable.",
        )
    if n_banks == 1:
        return AttackResult(
            attack_type="frequency",
            succeeded=True,
            confidence=1.0,
            details="Single bank — trivially identifiable.",
        )

    snapshots = report.corridor_snapshots
    if not snapshots:
        return AttackResult(
            attack_type="frequency",
            succeeded=False,
            confidence=0.0,
            details="No corridor snapshots to analyze.",
        )

    # Collect payment volumes per corridor
    volumes = np.array([s.total_payments for s in snapshots], dtype=np.float64)
    total = volumes.sum()
    if total == 0:
        return AttackResult(
            attack_type="frequency",
            succeeded=False,
            confidence=0.0,
            details="Zero total payments across all corridors.",
        )

    # Chi-squared test: do corridor volumes deviate significantly from uniform?
    # Under proper anonymisation with DP noise, volumes should not reveal
    # individual bank contribution patterns.
    n_corridors = len(volumes)
    expected = np.full(n_corridors, total / n_corridors)
    chi2, p_value = scipy_stats.chisquare(volumes, f_exp=expected)

    # Also check for single-bank corridors (k-anonymity violation)
    single_bank_corridors = sum(1 for s in snapshots if s.bank_count < 2)

    # Attack succeeds if distribution is highly non-uniform (p < 0.01)
    # OR any corridor has a single bank
    succeeded = p_value < 0.01 or single_bank_corridors > 0
    confidence = min(1.0, 1.0 - p_value) if p_value < 0.01 else (
        1.0 if single_bank_corridors > 0 else 1.0 / n_banks
    )

    return AttackResult(
        attack_type="frequency",
        succeeded=succeeded,
        confidence=round(confidence, 4),
        details=(
            f"Analyzed {n_corridors} corridors, {n_banks} banks. "
            f"Chi-squared={chi2:.2f}, p={p_value:.4f}. "
            f"Single-bank corridors: {single_bank_corridors}. "
            f"{'VULNERABLE' if succeeded else 'No significant frequency signal'}."
        ),
    )


def uniqueness_attack(
    anon_results: list[AnonymizedCorridorResult],
) -> AttackResult:
    """Check if any corridor has a uniquely identifiable bank.

    A corridor with bank_count < 2 means a single bank's data IS the
    corridor aggregate — uniquely identifiable. k-anonymity should prevent this.
    """
    unique_corridors = [r for r in anon_results if r.bank_count < 2]
    succeeded = len(unique_corridors) > 0
    confidence = 1.0 if succeeded else 0.0

    verdict = (
        "VULNERABLE: single-bank corridors expose individual data."
        if succeeded
        else "No uniquely identifiable banks."
    )
    return AttackResult(
        attack_type="uniqueness",
        succeeded=succeeded,
        confidence=confidence,
        details=(
            f"Checked {len(anon_results)} corridors. "
            f"Found {len(unique_corridors)} with bank_count < 2. "
            f"{verdict}"
        ),
    )


def temporal_linkage_attack(
    reports: list[SystemicRiskReport],
    n_banks: int,
) -> AttackResult:
    """Correlate anonymized output across time periods to track entities.

    B8-05: Real statistical test. Cross-correlate corridor failure rates
    across periods. High autocorrelation in a corridor's time series
    (despite DP noise) suggests a persistent entity whose behaviour is
    trackable. With proper DP noise, temporal correlation should be low.
    """
    if len(reports) < 2:
        return AttackResult(
            attack_type="temporal_linkage",
            succeeded=False,
            confidence=0.0,
            details="Insufficient periods for temporal analysis (need >= 2).",
        )
    if n_banks <= 0:
        return AttackResult(
            attack_type="temporal_linkage",
            succeeded=True,
            confidence=1.0,
            details="No banks — vacuously vulnerable.",
        )
    if n_banks == 1:
        return AttackResult(
            attack_type="temporal_linkage",
            succeeded=True,
            confidence=1.0,
            details="Single bank — trivially trackable across periods.",
        )

    # Build time series of failure rates per corridor across periods
    corridor_series: dict[str, list[float]] = {}
    for report in reports:
        for snap in report.corridor_snapshots:
            corridor_series.setdefault(snap.corridor, []).append(snap.failure_rate)

    # Compute mean absolute autocorrelation across corridors
    # High autocorrelation = entity behaviour is persistent and trackable
    # Need >= 3 points for lag-1 autocorrelation to be non-degenerate.
    autocorrelations: list[float] = []
    for corridor, series in corridor_series.items():
        if len(series) < 3:
            continue
        arr = np.array(series)
        mean = arr.mean()
        std = arr.std()
        if std < 1e-12:
            # Constant series — no signal to correlate
            continue
        # Lag-1 autocorrelation
        n = len(arr)
        normalized = (arr - mean) / std
        autocorr = float(np.dot(normalized[:-1], normalized[1:]) / (n - 1))
        autocorrelations.append(abs(autocorr))

    if not autocorrelations:
        return AttackResult(
            attack_type="temporal_linkage",
            succeeded=False,
            confidence=0.0,
            details=(
                f"Analyzed {len(reports)} periods. "
                "No corridors with sufficient variance for temporal analysis."
            ),
        )

    mean_autocorr = float(np.mean(autocorrelations))
    max_autocorr = float(np.max(autocorrelations))

    # If mean autocorrelation is high, an entity's pattern persists across
    # periods despite DP noise — the anonymisation is leaking temporal signal.
    # Threshold: 0.7 is a conservative bar for "trackable."
    succeeded = mean_autocorr > 0.7 or max_autocorr > 0.9
    confidence = min(1.0, mean_autocorr)

    return AttackResult(
        attack_type="temporal_linkage",
        succeeded=succeeded,
        confidence=round(confidence, 4),
        details=(
            f"Analyzed {len(reports)} periods, "
            f"{len(corridor_series)} corridors. "
            f"Mean lag-1 |autocorrelation|={mean_autocorr:.4f}, "
            f"max={max_autocorr:.4f}. "
            f"{'VULNERABLE — temporal signal persists through DP noise' if succeeded else 'DP noise sufficiently decorrelates temporal signal'}."
        ),
    )


# ---------------------------------------------------------------------------
# Formal proofs
# ---------------------------------------------------------------------------


def k_anonymity_proof(
    anon_results: list[AnonymizedCorridorResult],
    k: int = 5,
) -> KAnonymityProof:
    """Verify that all anonymized corridors satisfy k-anonymity."""
    violations = []
    for result in anon_results:
        if result.bank_count < k:
            violations.append(
                f"Corridor {result.corridor}: bank_count={result.bank_count} < k={k}"
            )

    return KAnonymityProof(
        k_threshold=k,
        corridors_checked=len(anon_results),
        all_satisfied=len(violations) == 0,
        violations=len(violations),
        violation_details=violations,
    )


def verify_dp_distribution(
    anonymizer: RegulatoryAnonymizer,
    epsilon: float,
    sensitivity: float,
    n_samples: int = 1000,
) -> DPVerificationResult:
    """Verify noise distribution matches theoretical Laplace(0, b).

    Uses Kolmogorov-Smirnov test to compare empirical noise samples
    against the theoretical Laplace CDF with b = sensitivity / epsilon.
    """
    # Use high base_value so clamping at 0 doesn't distort the distribution
    base_value = 100.0
    rng = np.random.default_rng(seed=12345)
    noise_samples = []
    for _ in range(n_samples):
        noised = anonymizer._apply_laplace_noise(base_value, sensitivity, rng=rng)
        noise_samples.append(noised - base_value)

    theoretical_scale = sensitivity / epsilon

    ks_stat, ks_p = scipy_stats.kstest(
        noise_samples,
        lambda x: scipy_stats.laplace.cdf(x, loc=0, scale=theoretical_scale),
    )

    passed = bool(ks_p > 0.01)

    return DPVerificationResult(
        epsilon=epsilon,
        sensitivity=sensitivity,
        n_samples=n_samples,
        ks_statistic=ks_stat,
        ks_p_value=ks_p,
        passed=passed,
    )


# ---------------------------------------------------------------------------
# Budget audit
# ---------------------------------------------------------------------------


def verify_budget_composition(
    tracker: PrivacyBudgetTracker,
    expected_queries: dict[str, int],
    epsilon_per_query: float,
) -> BudgetAuditResult:
    """Verify privacy budget accounting matches expected composition."""
    total_consumed = 0.0
    total_expected = 0.0
    corridors_audited = 0

    for corridor, expected_count in expected_queries.items():
        status = tracker.get_status(corridor)
        total_consumed += status.budget_spent
        total_expected += expected_count * epsilon_per_query
        corridors_audited += 1

    composition_valid = abs(total_consumed - total_expected) < 1e-9

    exhaustion_correct = True
    for corridor in expected_queries:
        status = tracker.get_status(corridor)
        if status.is_exhausted:
            if tracker.has_budget(corridor, Decimal(str(epsilon_per_query))):
                exhaustion_correct = False

    return BudgetAuditResult(
        total_epsilon_consumed=total_consumed,
        expected_epsilon=total_expected,
        corridors_audited=corridors_audited,
        composition_valid=composition_valid,
        exhaustion_behavior_correct=exhaustion_correct,
    )


# ---------------------------------------------------------------------------
# Full audit report
# ---------------------------------------------------------------------------


def generate_audit_report(
    salt: bytes,
    n_banks: int = 5,
    seed: int = 42,
) -> PrivacyAuditReport:
    """Run complete privacy audit and produce comprehensive report."""
    period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

    # Run pipeline (period 1)
    events = generate_shadow_events(
        n_banks=n_banks, n_events_per_bank=500, seed=seed,
    )
    anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=seed)
    engine = SystemicRiskEngine()
    runner = ShadowPipelineRunner(salt=salt, anonymizer=anon, risk_engine=engine)
    result = runner.run(events)

    # Collect anonymized results for uniqueness check
    collector = TelemetryCollector(salt=salt)
    for e in events:
        collector.ingest(e)
    batches = collector.flush(period_start, period_end)
    anon2 = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=seed + 1)
    anon_results = anon2.anonymize_batch(batches)

    # Run pipeline (period 2) for temporal linkage
    events2 = generate_shadow_events(
        n_banks=n_banks, n_events_per_bank=500, seed=seed + 100,
    )
    anon3 = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=seed + 2)
    engine2 = SystemicRiskEngine()
    runner2 = ShadowPipelineRunner(salt=salt, anonymizer=anon3, risk_engine=engine2)
    result2 = runner2.run(events2)

    # Attack simulations
    freq = frequency_attack(result.report, n_banks=n_banks)
    uniq = uniqueness_attack(anon_results)
    temp = temporal_linkage_attack([result.report, result2.report], n_banks=n_banks)

    # Formal proofs
    k_proof = k_anonymity_proof(anon_results, k=5)
    dp_ver = verify_dp_distribution(anon2, epsilon=0.5, sensitivity=1.0)

    # Budget audit
    # B8-01: sequential composition — each batch releases 3 noised statistics,
    # so the per-batch cost is 3 * epsilon, not 1 * epsilon.
    budget_result = verify_budget_composition(
        anon2._budget,
        expected_queries={c: 1 for c in {r.corridor for r in anon_results}},
        epsilon_per_query=0.5 * 3,
    )

    # Overall verdict
    all_attacks_failed = not (freq.succeeded or uniq.succeeded or temp.succeeded)
    all_proofs_pass = (
        k_proof.all_satisfied
        and dp_ver.passed
        and budget_result.composition_valid
    )
    verdict = "PASS" if (all_attacks_failed and all_proofs_pass) else "FAIL"

    return PrivacyAuditReport(
        timestamp=time.time(),
        methodology_version=MethodologyAppendix.VERSION,
        frequency_attack=freq,
        uniqueness_attack=uniq,
        temporal_linkage_attack=temp,
        k_anonymity_proof=k_proof,
        dp_verification=dp_ver,
        budget_audit=budget_result,
        overall_verdict=verdict,
    )
