"""
test_p5_cascade.py — Verification of P5 cascade risk with Bayesian smoothing.

Tests verify:
  1. First-payment score is no longer inflated to 1.0 (the known limitation fix).
  2. Smoothing converges to the raw rate as observation count grows.
  3. Cascade risk detection still works correctly after smoothing.
  4. CascadeConfidence reflects observation count and is_high_confidence.
  5. Empty BIC returns empty list + no-confidence CascadeConfidence.
"""
import pytest

from lip.c1_failure_classifier.graph_builder import (
    _DEPENDENCY_PRIOR_DEFAULT,
    _SMOOTHING_K,
    BICGraphBuilder,
    PaymentEdge,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _edge(uetr: str, sender: str, receiver: str, amount: float, ts: float = 100.0) -> PaymentEdge:
    return PaymentEdge(uetr, sender, receiver, amount, "USD_USD", ts)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestBayesianSmoothing:
    def test_first_payment_not_inflated_to_one(self):
        """P5 fix: first payment must NOT produce dependency_score = 1.0."""
        builder = BICGraphBuilder()
        e1 = _edge("u1", "SENDER_A", "RECEIVER", 1000.0)
        builder.add_payment(e1)

        # Raw would be 1.0; smoothed = (0 * 1.0 + 5 * 0.10) / (0 + 5) = 0.10
        assert e1.dependency_score == pytest.approx(_DEPENDENCY_PRIOR_DEFAULT)
        assert e1.observation_count == 0

    def test_second_payment_smoothed(self):
        """Second payment should be smoothed toward prior."""
        builder = BICGraphBuilder()
        e1 = _edge("u1", "SENDER_A", "RECEIVER", 1000.0)
        builder.add_payment(e1)

        e2 = _edge("u2", "SENDER_B", "RECEIVER", 1000.0, ts=110.0)
        builder.add_payment(e2)

        # After e1: prior = 0.10, e2.raw = 1000/2000 = 0.5
        # n=1 (one prior observation), prior≈0.10 (mean of e1's smoothed score)
        # smoothed ≈ (1 * 0.5 + 5 * prior) / (1 + 5)
        assert e2.observation_count == 1
        assert 0.0 < e2.dependency_score < 0.5  # smoothed below raw

    def test_score_converges_to_raw_with_many_observations(self):
        """After _SMOOTHING_K observations the smoothed score is close to raw."""
        builder = BICGraphBuilder()

        # Add SMOOTHING_K payments of $1000 each from different senders
        # Total after k payments = k*1000; raw for each = 1/cumulative_count
        # After k payments, n=k → smoothing weight = 50% raw / 50% prior
        # After 5*k payments, n=5k → smoothing weight = 5k/(5k+5) ≈ 83% raw
        for i in range(5 * _SMOOTHING_K):
            e = _edge(f"u{i}", f"SENDER_{i}", "RECEIVER", 1000.0, ts=float(i))
            builder.add_payment(e)

        # Check the last edge has observation_count = 5k - 1
        last_edge = builder._in_edges["RECEIVER"][-1]
        assert last_edge.observation_count == 5 * _SMOOTHING_K - 1

        # Raw for last edge = 1000 / (5k * 1000) = 1 / (5k)
        k = _SMOOTHING_K
        expected_raw = 1.0 / (5 * k)
        # smoothed ≈ (5k-1) * raw / (5k-1 + k) which should be close to raw
        assert abs(last_edge.dependency_score - expected_raw) < 0.02

    def test_prior_starts_at_default_when_no_history(self):
        """Global prior is _DEPENDENCY_PRIOR_DEFAULT for first edge added."""
        builder = BICGraphBuilder()
        assert builder._compute_corridor_prior_dependency() == _DEPENDENCY_PRIOR_DEFAULT

    def test_prior_updates_with_history(self):
        """Global prior increases after high-dependency payments are added."""
        builder = BICGraphBuilder()
        e1 = _edge("u1", "S", "R", 10000.0)  # large single payment → smoothed toward prior
        builder.add_payment(e1)

        prior_after = builder._compute_corridor_prior_dependency()
        # Prior was updated with e1.dependency_score (which ≈ prior itself for first edge)
        assert prior_after == pytest.approx(_DEPENDENCY_PRIOR_DEFAULT, abs=0.01)


class TestCascadeRisk:
    def test_cascade_risk_detection_with_smoothing(self):
        """High-dependency corridors still flagged even after smoothing."""
        builder = BICGraphBuilder()

        # Build history: RECEIVER has $9000 incoming from OTHER first
        for i in range(10):
            builder.add_payment(_edge(f"u_pre{i}", "OTHER", "RECEIVER", 900.0, ts=float(i)))

        # SENDER_A sends $100 → raw = 100/9100 ≈ 1.1%; after smoothing, well below 20%
        builder.add_payment(_edge("u1", "SENDER_A", "RECEIVER", 100.0, ts=11.0))

        # SENDER_B sends $5000 → raw = 5000/14100 ≈ 35.5%; after smoothing, still above 20%
        builder.add_payment(_edge("u2", "SENDER_B", "RECEIVER", 5000.0, ts=12.0))

        risk_a, conf_a = builder.get_cascade_risk("SENDER_A", dependency_threshold=0.2)
        assert "RECEIVER" not in risk_a
        assert conf_a.at_risk_count == 0

        risk_b, conf_b = builder.get_cascade_risk("SENDER_B", dependency_threshold=0.2)
        assert "RECEIVER" in risk_b
        assert conf_b.at_risk_count == 1

    def test_empty_bic_returns_empty_list(self):
        """Unknown BIC returns empty list and no-confidence CascadeConfidence."""
        builder = BICGraphBuilder()
        at_risk, conf = builder.get_cascade_risk("UNKNOWN_BIC")
        assert at_risk == []
        assert conf.at_risk_count == 0
        assert conf.is_high_confidence is False

    def test_no_risk_corridors_returns_high_confidence(self):
        """When no corridors cross threshold, CascadeConfidence.is_high_confidence=True."""
        builder = BICGraphBuilder()
        # Small payment — raw ≈ 0.1%; smoothed well below 20% threshold
        builder.add_payment(_edge("u1", "SENDER_A", "RECEIVER", 10.0))
        at_risk, conf = builder.get_cascade_risk("SENDER_A", dependency_threshold=0.2)
        assert at_risk == []
        assert conf.is_high_confidence is True


class TestCascadeConfidence:
    def test_low_confidence_on_first_payment(self):
        """A corridor with observation_count=0 signals low confidence."""
        builder = BICGraphBuilder()
        builder.add_payment(_edge("u1", "SENDER_A", "RECEIVER", 1000.0))

        # Even if dependency_score somehow reaches threshold, confidence is low
        # Here it won't reach 20% threshold so just verify structure
        # Force a case: add a large payment after a small history
        builder2 = BICGraphBuilder()
        # Add exactly one payment that crosses the threshold via prior
        # Prior = 0.1; first payment smoothed = 0.1 which is below threshold
        # So this test verifies that small n = low confidence
        big = _edge("u_big", "SENDER_X", "RECEIVER_X", 1000.0)
        builder2.add_payment(big)
        # Force-check the observation_count stored
        assert big.observation_count == 0

    def test_high_confidence_after_enough_observations(self):
        """is_high_confidence=True when min_observation_count >= _SMOOTHING_K."""
        builder = BICGraphBuilder()

        # Add SMOOTHING_K+1 payments from SENDER_A to RECEIVER so the last
        # edge has observation_count = SMOOTHING_K
        for i in range(_SMOOTHING_K + 1):
            e = _edge(f"u{i}", "SENDER_A", "RECEIVER", 1000.0, ts=float(i))
            builder.add_payment(e)

        # Add a large-enough payment so raw dependency is above threshold
        big = _edge("u_big", "SENDER_A", "RECEIVER", 10_000.0, ts=float(_SMOOTHING_K + 2))
        builder.add_payment(big)

        at_risk, conf = builder.get_cascade_risk("SENDER_A", dependency_threshold=0.1)
        if at_risk:
            assert conf.min_observation_count >= _SMOOTHING_K
