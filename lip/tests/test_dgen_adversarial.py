"""
test_dgen_adversarial.py — Verification of adversarial scenario generation in DGEN.
Part of Tier 2 R&D: Adversarial Resilience.
"""
from lip.dgen.c3_generator import generate_repayment_corpus


def test_recall_attack_generation():
    """Verify that RECALL_ATTACK scenarios are produced and correctly labeled."""
    n_samples = 1000
    records = generate_repayment_corpus(n_samples=n_samples, seed=42)

    recalls = [r for r in records if r["scenario"] == "RECALL_ATTACK"]

    # We expect roughly 3% (30 out of 1000)
    assert len(recalls) > 0

    for r in recalls:
        # Check adversarial properties
        assert r["label"] == 1
        assert r["is_settled"] is False
        assert r["settlement_amount_usd"] == 0.0
        assert r["repayment_triggered_by"] == "CAMT056_RECALL_PENDING"

        meta = r["cancellation_metadata"]
        assert meta is not None
        assert meta["is_adversarial"] is True
        assert meta["message_type"] == "camt.056"
        assert meta["reason_code"] == "CUST"

def test_label_consistency():
    """Verify that problematic outcomes always have label=1."""
    records = generate_repayment_corpus(n_samples=500, seed=123)

    for r in records:
        if r["scenario"] in ("TIMEOUT", "RECALL_ATTACK"):
            assert r["label"] == 1
        elif r["scenario"] == "SUCCESS":
            assert r["label"] == 0
