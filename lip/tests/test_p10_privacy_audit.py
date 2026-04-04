"""Tests for the P10 privacy audit kit (Sprint 8)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.privacy_audit import (
    AttackResult,
    BudgetAuditResult,
    DPVerificationResult,
    KAnonymityProof,
    PrivacyAuditReport,
    frequency_attack,
    generate_audit_report,
    k_anonymity_proof,
    temporal_linkage_attack,
    uniqueness_attack,
    verify_budget_composition,
    verify_dp_distribution,
)
from lip.p10_regulatory_data.privacy_budget import PrivacyBudgetTracker
from lip.p10_regulatory_data.shadow_data import generate_shadow_events
from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector
from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

_SALT = b"audit_test_salt_32bytes_________"
_PERIOD_START = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
_PERIOD_END = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)


def _run_pipeline(n_banks: int = 5, seed: int = 42):
    """Helper: run full shadow pipeline and return (result, anonymizer)."""
    events = generate_shadow_events(n_banks=n_banks, n_events_per_bank=500, seed=seed)
    anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=seed)
    engine = SystemicRiskEngine()
    runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anon, risk_engine=engine)
    result = runner.run(events)
    return result, anon


def _get_anon_results(n_banks: int = 5, k: int = 5, seed: int = 42):
    """Helper: generate events, collect, anonymize, return results."""
    events = generate_shadow_events(n_banks=n_banks, n_events_per_bank=500, seed=seed)
    collector = TelemetryCollector(salt=_SALT)
    for e in events:
        collector.ingest(e)
    batches = collector.flush(_PERIOD_START, _PERIOD_END)
    anon = RegulatoryAnonymizer(k=k, epsilon=Decimal("0.5"), rng_seed=seed + 10)
    return anon.anonymize_batch(batches), anon


# ---- Frequency Attack ----


class TestFrequencyAttack:

    def test_frequency_attack_fails_with_5_banks(self):
        result, _ = _run_pipeline(n_banks=5)
        attack = frequency_attack(result.report, n_banks=5)
        assert isinstance(attack, AttackResult)
        assert attack.attack_type == "frequency"
        assert attack.succeeded is False

    def test_frequency_attack_returns_confidence(self):
        result, _ = _run_pipeline(n_banks=5)
        attack = frequency_attack(result.report, n_banks=5)
        assert 0.0 <= attack.confidence <= 1.0
        assert abs(attack.confidence - 0.2) < 1e-9  # 1/5


# ---- Uniqueness Attack ----


class TestUniquenessAttack:

    def test_uniqueness_attack_fails_with_k_anonymity(self):
        anon_results, _ = _get_anon_results(n_banks=5, k=5)
        attack = uniqueness_attack(anon_results)
        assert isinstance(attack, AttackResult)
        assert attack.attack_type == "uniqueness"
        assert attack.succeeded is False

    def test_uniqueness_attack_detects_insufficient_k(self):
        """With k=1 and 1 bank, all corridors have bank_count=1 — uniquely identifiable."""
        anon_results, _ = _get_anon_results(n_banks=1, k=1)
        attack = uniqueness_attack(anon_results)
        assert attack.succeeded is True


# ---- Temporal Linkage Attack ----


class TestTemporalLinkageAttack:

    def test_temporal_linkage_fails_with_noise(self):
        results = []
        for seed in [42, 43]:
            r, _ = _run_pipeline(n_banks=5, seed=seed)
            results.append(r)
        attack = temporal_linkage_attack(
            [r.report for r in results], n_banks=5,
        )
        assert isinstance(attack, AttackResult)
        assert attack.attack_type == "temporal_linkage"
        assert attack.succeeded is False

    def test_temporal_linkage_insufficient_periods(self):
        result, _ = _run_pipeline(n_banks=5)
        attack = temporal_linkage_attack([result.report], n_banks=5)
        assert attack.succeeded is False
        assert attack.confidence == 0.0


# ---- K-Anonymity Proof ----


class TestKAnonymityProof:

    def test_proof_passes_with_5_banks(self):
        anon_results, _ = _get_anon_results(n_banks=5, k=5)
        proof = k_anonymity_proof(anon_results, k=5)
        assert isinstance(proof, KAnonymityProof)
        assert proof.all_satisfied is True
        assert proof.violations == 0

    def test_proof_reports_violations(self):
        fake_result = AnonymizedCorridorResult(
            corridor="TEST-FAKE",
            period_label="2026-04-02T14:00Z",
            total_payments=100,
            failed_payments=10,
            failure_rate=0.1,
            bank_count=3,
            k_anonymity_satisfied=False,
            privacy_budget_remaining=4.5,
            noise_applied=True,
            stale=False,
        )
        proof = k_anonymity_proof([fake_result], k=5)
        assert proof.all_satisfied is False
        assert proof.violations == 1

    def test_proof_checks_all_corridors(self):
        anon_results, _ = _get_anon_results(n_banks=5, k=5)
        proof = k_anonymity_proof(anon_results, k=5)
        assert proof.corridors_checked == len(anon_results)
        assert proof.corridors_checked > 0


# ---- DP Verification ----


class TestDPVerification:

    def test_laplace_distribution_matches(self):
        anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=42)
        result = verify_dp_distribution(
            anonymizer=anon, epsilon=0.5, sensitivity=1.0, n_samples=1000,
        )
        assert isinstance(result, DPVerificationResult)
        assert result.passed is True
        assert result.ks_p_value > 0.01

    def test_wrong_epsilon_fails_verification(self):
        anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=42)
        result = verify_dp_distribution(
            anonymizer=anon, epsilon=5.0, sensitivity=1.0, n_samples=1000,
        )
        assert result.passed is False

    def test_verification_returns_statistics(self):
        anon = RegulatoryAnonymizer(k=5, epsilon=Decimal("0.5"), rng_seed=42)
        result = verify_dp_distribution(
            anonymizer=anon, epsilon=0.5, sensitivity=1.0, n_samples=500,
        )
        assert result.n_samples == 500
        assert result.ks_statistic >= 0.0


# ---- Budget Audit ----


class TestBudgetAudit:

    def test_budget_composition_valid(self):
        tracker = PrivacyBudgetTracker()
        tracker.deduct("EUR-USD", Decimal("0.5"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        tracker.deduct("GBP-EUR", Decimal("0.5"))
        result = verify_budget_composition(
            tracker, expected_queries={"EUR-USD": 2, "GBP-EUR": 1}, epsilon_per_query=0.5,
        )
        assert isinstance(result, BudgetAuditResult)
        assert result.composition_valid is True

    def test_budget_exhaustion_detected(self):
        tracker = PrivacyBudgetTracker(budget_per_cycle=Decimal("1.0"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        tracker.deduct("EUR-USD", Decimal("0.5"))
        assert not tracker.has_budget("EUR-USD", Decimal("0.5"))
        result = verify_budget_composition(
            tracker, expected_queries={"EUR-USD": 2}, epsilon_per_query=0.5,
        )
        assert result.composition_valid is True
        assert result.exhaustion_behavior_correct is True


# ---- Full Audit Report ----


class TestAuditReport:

    def test_generate_audit_report_produces_verdict(self):
        report = generate_audit_report(salt=_SALT, n_banks=5, seed=42)
        assert isinstance(report, PrivacyAuditReport)
        assert report.methodology_version is not None
        assert report.overall_verdict in ("PASS", "FAIL")

    def test_audit_report_passes_with_proper_config(self):
        report = generate_audit_report(salt=_SALT, n_banks=5, seed=42)
        assert report.overall_verdict == "PASS"
        assert report.k_anonymity_proof.all_satisfied is True
        assert report.dp_verification.passed is True
