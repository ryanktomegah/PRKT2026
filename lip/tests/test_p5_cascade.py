"""
test_p5_cascade.py — Verification of supply chain cascade propagation (P5).
Part of Tier 3 R&D: Network Topology.
"""
from lip.c1_failure_classifier.graph_builder import BICGraphBuilder, PaymentEdge


def test_dependency_score_calculation():
    builder = BICGraphBuilder()

    # 1. First payment to RECEIVER: $1000
    # Total receivables = 1000, dependency = 1.0
    e1 = PaymentEdge("u1", "SENDER_A", "RECEIVER", 1000.0, "USD_USD", 100.0)
    builder.add_payment(e1)
    assert e1.dependency_score == 1.0

    # 2. Second payment to RECEIVER: $1000
    # Total receivables = 2000, dependency = 0.5
    e2 = PaymentEdge("u2", "SENDER_B", "RECEIVER", 1000.0, "USD_USD", 110.0)
    builder.add_payment(e2)
    assert e2.dependency_score == 0.5

def test_cascade_risk_detection():
    builder = BICGraphBuilder()

    # Setup: RECEIVER has $10,000 total incoming
    builder.add_payment(PaymentEdge("u0", "OTHER", "RECEIVER", 9000.0, "USD_USD", 50.0))

    # SENDER_A sends $100 -> 100/9100 = ~1% dependency (Low risk)
    builder.add_payment(PaymentEdge("u1", "SENDER_A", "RECEIVER", 100.0, "USD_USD", 100.0))

    # SENDER_B sends $5000 -> 5000/14100 = ~35% dependency (High risk)
    builder.add_payment(PaymentEdge("u2", "SENDER_B", "RECEIVER", 5000.0, "USD_USD", 110.0))

    # Check cascade risk
    risk_a = builder.get_cascade_risk("SENDER_A", dependency_threshold=0.2)
    assert "RECEIVER" not in risk_a

    risk_b = builder.get_cascade_risk("SENDER_B", dependency_threshold=0.2)
    assert "RECEIVER" in risk_b
