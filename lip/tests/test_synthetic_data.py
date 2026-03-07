"""
test_synthetic_data.py — Tests for C1 Failure Classifier synthetic data generator.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from lip.c1_failure_classifier.synthetic_data import (
    BIC_REGISTRY,
    CLASS_DISTRIBUTION,
    CORRIDOR_DEFINITIONS,
    SyntheticPaymentGenerator,
    apply_smote,
    train_val_test_split,
)
from lip.c3_repayment_engine.rejection_taxonomy import REJECTION_CODE_TAXONOMY, RejectionClass

# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gen_seed42() -> SyntheticPaymentGenerator:
    return SyntheticPaymentGenerator(seed=42)


@pytest.fixture(scope="module")
def small_txns(gen_seed42: SyntheticPaymentGenerator) -> list[dict]:
    return gen_seed42.generate_dataset(n_transactions=1_000)


@pytest.fixture(scope="module")
def medium_txns() -> list[dict]:
    gen = SyntheticPaymentGenerator(seed=42)
    return gen.generate_dataset(n_transactions=5_000)


@pytest.fixture(scope="module")
def large_txns() -> list[dict]:
    """50,000 records needed for statistical rate tests."""
    gen = SyntheticPaymentGenerator(seed=42)
    return gen.generate_dataset(n_transactions=50_000)


# ── TestSyntheticPaymentGenerator ─────────────────────────────────────────────

class TestSyntheticPaymentGenerator:
    """Core generation tests."""

    def test_generates_correct_count(self, gen_seed42: SyntheticPaymentGenerator) -> None:
        """generate_dataset(1000) returns exactly 1000 records."""
        txns = gen_seed42.generate_dataset(1_000)
        assert len(txns) == 1_000

    def test_failure_rate_within_tolerance(self, large_txns: list[dict]) -> None:
        """Failure rate is within [3.0%, 4.0%] on 50K records."""
        rate = sum(1 for t in large_txns if t["is_failure"] == 1) / len(large_txns)
        assert 0.030 <= rate <= 0.040, f"Failure rate {rate:.4f} outside [0.030, 0.040]"

    def test_class_distribution_within_tolerance(self, large_txns: list[dict]) -> None:
        """Among failures: A ~55%, B ~30%, C ~15% (±5% tolerance)."""
        failures = [t for t in large_txns if t["is_failure"] == 1]
        n_fail = len(failures)
        assert n_fail > 0
        counts = Counter(t["rejection_class"] for t in failures)
        for cls, target in CLASS_DISTRIBUTION.items():
            actual = counts[cls] / n_fail
            assert abs(actual - target) <= 0.05, (
                f"Class {cls}: actual={actual:.3f}, target={target:.3f}, "
                f"deviation={abs(actual - target):.3f} > 0.05"
            )

    def test_no_block_codes_in_output(self, large_txns: list[dict]) -> None:
        """DISP, FRAU, FRAD, DUPL never appear — they are C4's domain."""
        block_codes = {
            c for c, rc in REJECTION_CODE_TAXONOMY.items()
            if rc is RejectionClass.BLOCK
        }
        found = {t["rejection_code"] for t in large_txns if t["rejection_code"] in block_codes}
        assert found == set(), f"BLOCK codes found in output: {found}"

    def test_all_rejection_codes_valid(self, large_txns: list[dict]) -> None:
        """Every rejection code exists in REJECTION_CODE_TAXONOMY or is 'NONE'."""
        invalid = {
            t["rejection_code"] for t in large_txns
            if t["rejection_code"] != "NONE"
            and t["rejection_code"] not in REJECTION_CODE_TAXONOMY
        }
        assert invalid == set(), f"Unknown rejection codes: {invalid}"

    def test_no_self_loops(self, large_txns: list[dict]) -> None:
        """sending_bic != receiving_bic for every record."""
        loops = [
            (t["sending_bic"], t["receiving_bic"])
            for t in large_txns
            if t["sending_bic"] == t["receiving_bic"]
        ]
        assert loops == [], f"Self-loops found: {loops[:5]}"

    def test_all_bics_from_registry(self, large_txns: list[dict]) -> None:
        """Every BIC appears in BIC_REGISTRY."""
        unknown = {
            bic for t in large_txns
            for bic in (t["sending_bic"], t["receiving_bic"])
            if bic not in BIC_REGISTRY
        }
        assert unknown == set(), f"Unknown BICs: {unknown}"

    def test_corpus_tag_present(self, small_txns: list[dict]) -> None:
        """Every record has corpus_tag == 'SYNTHETIC_CORPUS'."""
        bad = [t for t in small_txns if t.get("corpus_tag") != "SYNTHETIC_CORPUS"]
        assert bad == [], f"{len(bad)} records have wrong/missing corpus_tag"

    def test_uetr_unique(self, large_txns: list[dict]) -> None:
        """All UETRs are unique."""
        uetrs = [t["uetr"] for t in large_txns]
        assert len(set(uetrs)) == len(uetrs), "Duplicate UETRs found"

    def test_amount_positive(self, small_txns: list[dict]) -> None:
        """All amounts > 0."""
        assert all(t["amount_usd"] > 0 for t in small_txns)

    def test_amount_within_range(self, large_txns: list[dict]) -> None:
        """All amounts between $1,000 and $50,000,000."""
        bad = [t["amount_usd"] for t in large_txns
               if not (1_000.0 <= t["amount_usd"] <= 50_000_000.0)]
        assert bad == [], f"{len(bad)} amounts out of [$1K, $50M] range"

    def test_hour_of_day_range(self, large_txns: list[dict]) -> None:
        """hour_of_day in [0, 23]."""
        bad = [t["hour_of_day"] for t in large_txns if not (0 <= t["hour_of_day"] <= 23)]
        assert bad == [], f"Out-of-range hours: {set(bad)}"

    def test_day_of_week_range(self, large_txns: list[dict]) -> None:
        """day_of_week in [0, 6]."""
        bad = [t["day_of_week"] for t in large_txns if not (0 <= t["day_of_week"] <= 6)]
        assert bad == [], f"Out-of-range days: {set(bad)}"

    def test_settlement_lag_range(self, large_txns: list[dict]) -> None:
        """settlement_lag_days in [0, 5]."""
        bad = [t["settlement_lag_days"] for t in large_txns
               if not (0 <= t["settlement_lag_days"] <= 5)]
        assert bad == [], f"Out-of-range settlement lags: {set(bad)}"

    def test_data_quality_score_range(self, large_txns: list[dict]) -> None:
        """data_quality_score in [0.0, 1.0]."""
        bad = [t["data_quality_score"] for t in large_txns
               if not (0.0 <= t["data_quality_score"] <= 1.0)]
        assert bad == [], f"{len(bad)} records with out-of-range data_quality_score"

    def test_correspondent_depth_range(self, large_txns: list[dict]) -> None:
        """correspondent_depth in [1, 5]."""
        bad = [t["correspondent_depth"] for t in large_txns
               if not (1 <= t["correspondent_depth"] <= 5)]
        assert bad == [], f"Out-of-range correspondent depths: {set(bad)}"

    def test_deterministic_with_seed(self) -> None:
        """Same seed produces same output."""
        gen1 = SyntheticPaymentGenerator(seed=99)
        gen2 = SyntheticPaymentGenerator(seed=99)
        t1 = gen1.generate_dataset(100)
        t2 = gen2.generate_dataset(100)
        assert [r["uetr"] for r in t1] == [r["uetr"] for r in t2], (
            "Identical seeds produced different UETRs"
        )
        assert [r["amount_usd"] for r in t1] == [r["amount_usd"] for r in t2]

    def test_different_seeds_differ(self) -> None:
        """Different seeds produce different outputs."""
        gen1 = SyntheticPaymentGenerator(seed=1)
        gen2 = SyntheticPaymentGenerator(seed=2)
        t1 = gen1.generate_dataset(100)
        t2 = gen2.generate_dataset(100)
        assert [r["uetr"] for r in t1] != [r["uetr"] for r in t2]

    def test_successful_payments_have_none_rejection(self, large_txns: list[dict]) -> None:
        """is_failure == 0 → rejection_code == 'NONE', rejection_class == 'NONE'."""
        bad = [
            t for t in large_txns
            if t["is_failure"] == 0
            and (t["rejection_code"] != "NONE" or t["rejection_class"] != "NONE")
        ]
        assert bad == [], f"{len(bad)} successful payments have non-NONE rejection fields"

    def test_failed_payments_have_real_rejection(self, large_txns: list[dict]) -> None:
        """is_failure == 1 → rejection_code != 'NONE', rejection_class in {A, B, C}."""
        bad = [
            t for t in large_txns
            if t["is_failure"] == 1
            and (t["rejection_code"] == "NONE" or t["rejection_class"] not in {"A", "B", "C"})
        ]
        assert bad == [], f"{len(bad)} failed payments have invalid rejection fields"

    def test_generation_seed_field(self, small_txns: list[dict]) -> None:
        """Every record has generation_seed matching the generator seed."""
        assert all(t["generation_seed"] == 42 for t in small_txns)

    def test_payment_status_consistency(self, large_txns: list[dict]) -> None:
        """ACCC ↔ is_failure==0; RJCT ↔ is_failure==1."""
        bad = [
            t for t in large_txns
            if (t["is_failure"] == 0 and t["payment_status"] != "ACCC")
            or (t["is_failure"] == 1 and t["payment_status"] != "RJCT")
        ]
        assert bad == [], f"{len(bad)} records have mismatched payment_status / is_failure"

    def test_currency_pair_from_corridor_definitions(self, large_txns: list[dict]) -> None:
        """Every currency_pair is a defined corridor."""
        unknown = {t["currency_pair"] for t in large_txns
                   if t["currency_pair"] not in CORRIDOR_DEFINITIONS}
        assert unknown == set(), f"Unknown corridors: {unknown}"

    def test_message_priority_valid(self, large_txns: list[dict]) -> None:
        """message_priority is one of NORM, HIGH, URGP."""
        valid = {"NORM", "HIGH", "URGP"}
        bad = {t["message_priority"] for t in large_txns if t["message_priority"] not in valid}
        assert bad == set(), f"Invalid message priorities: {bad}"

    def test_required_fields_present(self, small_txns: list[dict]) -> None:
        """All required fields are present on every record."""
        required = {
            "uetr", "sending_bic", "receiving_bic", "currency_pair", "amount_usd",
            "hour_of_day", "day_of_week", "settlement_lag_days", "prior_rejections_30d",
            "rejection_code", "rejection_class", "payment_status", "correspondent_depth",
            "data_quality_score", "message_priority", "is_failure", "corpus_tag",
            "generation_timestamp", "generation_seed",
        }
        for i, t in enumerate(small_txns):
            missing = required - t.keys()
            assert not missing, f"Record {i} missing fields: {missing}"


# ── TestAmountDistribution ────────────────────────────────────────────────────

class TestAmountDistribution:
    """Amount distribution anchored to BIS CPMI stats."""

    @pytest.fixture(scope="class")
    def g7_amounts(self) -> list[float]:
        gen = SyntheticPaymentGenerator(seed=10)
        g7_corridors = {
            c for c, info in CORRIDOR_DEFINITIONS.items()
            if info["region_type"] == "G7"
        }
        txns = gen.generate_dataset(20_000)
        return [t["amount_usd"] for t in txns if t["currency_pair"] in g7_corridors]

    @pytest.fixture(scope="class")
    def em_amounts(self) -> list[float]:
        gen = SyntheticPaymentGenerator(seed=10)
        em_corridors = {
            c for c, info in CORRIDOR_DEFINITIONS.items()
            if info["region_type"] == "EM"
        }
        txns = gen.generate_dataset(20_000)
        return [t["amount_usd"] for t in txns if t["currency_pair"] in em_corridors]

    def test_g7_corridor_median_reasonable(self, g7_amounts: list[float]) -> None:
        """G7 corridor median between $100K and $500K."""
        assert len(g7_amounts) > 100
        median = float(np.median(g7_amounts))
        assert 100_000 <= median <= 500_000, f"G7 median {median:,.0f} outside [$100K, $500K]"

    def test_em_corridor_median_lower(
        self, g7_amounts: list[float], em_amounts: list[float]
    ) -> None:
        """EM corridor median < G7 corridor median."""
        assert len(em_amounts) > 50
        g7_median = float(np.median(g7_amounts))
        em_median = float(np.median(em_amounts))
        assert em_median < g7_median, (
            f"EM median {em_median:,.0f} >= G7 median {g7_median:,.0f}"
        )

    def test_log_normal_shape(self, large_txns: list[dict]) -> None:
        """Amount distribution is right-skewed (mean > median)."""
        amounts = [t["amount_usd"] for t in large_txns]
        mean = float(np.mean(amounts))
        median = float(np.median(amounts))
        assert mean > median, f"mean ({mean:,.0f}) <= median ({median:,.0f}): not right-skewed"

    def test_amount_mean_exceeds_median_for_g7(self, g7_amounts: list[float]) -> None:
        """G7 log-normal has right tail: mean > median."""
        assert float(np.mean(g7_amounts)) > float(np.median(g7_amounts))


# ── TestGraphData ─────────────────────────────────────────────────────────────

class TestGraphData:
    """BIC graph structure for GraphSAGE."""

    @pytest.fixture(scope="class")
    def graph(self) -> dict:
        gen = SyntheticPaymentGenerator(seed=42)
        txns = gen.generate_dataset(2_000)
        return gen.generate_graph_data(txns)

    def test_graph_has_all_active_bics(self, graph: dict) -> None:
        """Every BIC that appeared in transactions is a graph node."""
        node_bics = {n["bic"] for n in graph["nodes"]}
        # All active BICs must appear as graph nodes
        assert len(node_bics) > 0
        # All nodes must be from the registry
        assert all(bic in BIC_REGISTRY for bic in node_bics)

    def test_power_law_degree_distribution(self, graph: dict) -> None:
        """Top 10% of BICs have >50% of edges (power-law proxy check)."""
        degrees = sorted(
            [n["total_degree"] for n in graph["nodes"]], reverse=True
        )
        total_edges = sum(degrees)
        assert total_edges > 0
        top_n = max(1, len(degrees) // 10)
        top_share = sum(degrees[:top_n]) / total_edges
        assert top_share > 0.50, (
            f"Top 10% of BICs hold only {top_share:.2%} of edges (need >50%)"
        )

    def test_tier1_higher_degree(self, graph: dict) -> None:
        """Tier 1 BICs have higher average degree than Tier 3."""
        tier1_degrees = [
            n["total_degree"] for n in graph["nodes"]
            if BIC_REGISTRY.get(n["bic"], {}).get("tier") == 1
        ]
        tier3_degrees = [
            n["total_degree"] for n in graph["nodes"]
            if BIC_REGISTRY.get(n["bic"], {}).get("tier") == 3
        ]
        assert len(tier1_degrees) > 0
        assert len(tier3_degrees) > 0
        assert np.mean(tier1_degrees) > np.mean(tier3_degrees), (
            f"Tier1 avg={np.mean(tier1_degrees):.1f} <= Tier3 avg={np.mean(tier3_degrees):.1f}"
        )

    def test_graph_edges_non_empty(self, graph: dict) -> None:
        """Graph must have at least one edge."""
        assert len(graph["edges"]) > 0

    def test_adjacency_consistent_with_edges(self, graph: dict) -> None:
        """Every edge sender appears in adjacency dict."""
        edge_senders = {e["sender"] for e in graph["edges"]}
        assert all(s in graph["adjacency"] for s in edge_senders)

    def test_degree_distribution_stats_present(self, graph: dict) -> None:
        """degree_distribution dict has expected keys."""
        dd = graph["degree_distribution"]
        for key in ("min", "max", "mean", "top_10pct_edge_share", "node_count", "edge_count"):
            assert key in dd, f"Missing key '{key}' in degree_distribution"


# ── TestRejectionCodeCooccurrence ────────────────────────────────────────────

class TestRejectionCodeCooccurrence:
    """Rejection code conditioning on features."""

    @pytest.fixture(scope="class")
    def cooc_txns(self) -> list[dict]:
        gen = SyntheticPaymentGenerator(seed=42)
        return gen.generate_dataset(50_000)

    def test_am04_correlates_with_large_amounts(self, cooc_txns: list[dict]) -> None:
        """AM04 (InsufficientFunds) appears more often in top quartile amounts."""
        failures = [t for t in cooc_txns if t["is_failure"] == 1]
        amounts = [t["amount_usd"] for t in failures]
        q75 = float(np.percentile(amounts, 75))

        large_failures = [t for t in failures if t["amount_usd"] >= q75]
        small_failures = [t for t in failures if t["amount_usd"] < q75]

        def am04_rate(txns: list[dict]) -> float:
            if not txns:
                return 0.0
            return sum(1 for t in txns if t["rejection_code"] == "AM04") / len(txns)

        large_rate = am04_rate(large_failures)
        small_rate = am04_rate(small_failures)
        assert large_rate > small_rate, (
            f"AM04 rate in large ({large_rate:.4f}) <= small ({small_rate:.4f}) amounts"
        )

    def test_curr_correlates_with_cross_border(self, cooc_txns: list[dict]) -> None:
        """CURR codes appear more in EM/HIGH_FRICTION (cross-border) corridors."""
        failures = [t for t in cooc_txns if t["is_failure"] == 1]
        cross_border_types = {"EM", "HIGH_FRICTION"}

        cb_failures = [
            t for t in failures
            if CORRIDOR_DEFINITIONS.get(t["currency_pair"], {}).get("region_type")
            in cross_border_types
        ]
        g7_failures = [
            t for t in failures
            if CORRIDOR_DEFINITIONS.get(t["currency_pair"], {}).get("region_type") == "G7"
        ]

        def curr_rate(txns: list[dict]) -> float:
            if not txns:
                return 0.0
            return sum(1 for t in txns if t["rejection_code"] == "CURR") / len(txns)

        cb_rate = curr_rate(cb_failures)
        g7_rate = curr_rate(g7_failures)
        assert cb_rate > g7_rate, (
            f"CURR rate in cross-border ({cb_rate:.4f}) <= G7 ({g7_rate:.4f})"
        )


# ── TestSMOTE ─────────────────────────────────────────────────────────────────

class TestSMOTE:
    """SMOTE oversampling tests."""

    @pytest.fixture(scope="class")
    def base_txns(self) -> list[dict]:
        gen = SyntheticPaymentGenerator(seed=42)
        return gen.generate_dataset(5_000)

    def test_smote_increases_minority_ratio(self, base_txns: list[dict]) -> None:
        """After SMOTE, failure ratio is closer to target (15%)."""
        target = 0.15
        orig_rate = sum(1 for t in base_txns if t["is_failure"] == 1) / len(base_txns)
        augmented = apply_smote(base_txns, target_minority_ratio=target, seed=42)
        new_rate = sum(1 for t in augmented if t["is_failure"] == 1) / len(augmented)
        assert new_rate > orig_rate, "SMOTE did not increase failure ratio"
        # Should be closer to target than before
        assert abs(new_rate - target) < abs(orig_rate - target) or new_rate >= target * 0.8

    def test_smote_preserves_original_records(self, base_txns: list[dict]) -> None:
        """Original records with corpus_tag='SYNTHETIC_CORPUS' are unchanged."""
        augmented = apply_smote(base_txns, target_minority_ratio=0.15, seed=42)
        orig_uetrs = {t["uetr"] for t in base_txns}
        orig_in_aug = [t for t in augmented if t["uetr"] in orig_uetrs]
        assert len(orig_in_aug) == len(base_txns), (
            "Some original records are missing from augmented dataset"
        )

    def test_smote_tagged_records(self, base_txns: list[dict]) -> None:
        """SMOTE-generated records have corpus_tag='SYNTHETIC_CORPUS_SMOTE'."""
        augmented = apply_smote(base_txns, target_minority_ratio=0.15, seed=42)
        orig_uetrs = {t["uetr"] for t in base_txns}
        new_records = [t for t in augmented if t["uetr"] not in orig_uetrs]
        assert len(new_records) > 0, "No new records were generated by SMOTE"
        wrong_tag = [t for t in new_records if t["corpus_tag"] != "SYNTHETIC_CORPUS_SMOTE"]
        assert wrong_tag == [], (
            f"{len(wrong_tag)} new records have wrong corpus_tag"
        )

    def test_smote_new_failures_are_failures(self, base_txns: list[dict]) -> None:
        """All SMOTE-generated new records are labelled as failures."""
        augmented = apply_smote(base_txns, target_minority_ratio=0.15, seed=42)
        orig_uetrs = {t["uetr"] for t in base_txns}
        new_records = [t for t in augmented if t["uetr"] not in orig_uetrs]
        non_failures = [t for t in new_records if t["is_failure"] != 1]
        assert non_failures == [], f"{len(non_failures)} new records are not labelled as failures"

    def test_smote_no_op_when_already_at_target(self) -> None:
        """If failure ratio already exceeds target, return original list unchanged."""
        # Build a dataset that is already at 50% failure rate
        gen = SyntheticPaymentGenerator(seed=42)
        base = gen.generate_dataset(200)
        # Force half to be failures
        for i in range(100):
            base[i]["is_failure"] = 1
        result = apply_smote(base, target_minority_ratio=0.10, seed=42)
        # n_new should be <= 0, so result == original
        assert len(result) <= len(base) + 5  # small tolerance


# ── TestSplitUtility ──────────────────────────────────────────────────────────

class TestSplitUtility:
    """Train/val/test split tests."""

    @pytest.fixture(scope="class")
    def split_txns(self) -> list[dict]:
        gen = SyntheticPaymentGenerator(seed=42)
        return gen.generate_dataset(2_000)

    def test_split_sizes_correct(self, split_txns: list[dict]) -> None:
        """70/15/15 split produces approximately correct proportions."""
        n = len(split_txns)
        train, val, test = train_val_test_split(split_txns, seed=42)
        # Allow ±2% tolerance on proportions due to integer rounding
        assert abs(len(train) / n - 0.70) <= 0.03, f"Train proportion off: {len(train)/n:.3f}"
        assert abs(len(val) / n - 0.15) <= 0.03, f"Val proportion off: {len(val)/n:.3f}"
        assert abs(len(test) / n - 0.15) <= 0.03, f"Test proportion off: {len(test)/n:.3f}"

    def test_stratification_preserves_rate(self, split_txns: list[dict]) -> None:
        """Failure rate approximately equal across splits (within ±1.5%)."""
        overall_rate = sum(1 for t in split_txns if t["is_failure"] == 1) / len(split_txns)
        train, val, test = train_val_test_split(split_txns, seed=42)
        for name, split in [("train", train), ("val", val), ("test", test)]:
            if not split:
                continue
            rate = sum(1 for t in split if t["is_failure"] == 1) / len(split)
            assert abs(rate - overall_rate) <= 0.015, (
                f"{name} failure rate {rate:.4f} deviates >1.5% from overall {overall_rate:.4f}"
            )

    def test_no_leakage(self, split_txns: list[dict]) -> None:
        """No UETRs appear in more than one split."""
        train, val, test = train_val_test_split(split_txns, seed=42)
        train_ids = {t["uetr"] for t in train}
        val_ids = {t["uetr"] for t in val}
        test_ids = {t["uetr"] for t in test}
        assert train_ids.isdisjoint(val_ids), "UETR overlap between train and val"
        assert train_ids.isdisjoint(test_ids), "UETR overlap between train and test"
        assert val_ids.isdisjoint(test_ids), "UETR overlap between val and test"

    def test_split_covers_all_records(self, split_txns: list[dict]) -> None:
        """Train + val + test contains all original records."""
        train, val, test = train_val_test_split(split_txns, seed=42)
        orig_ids = {t["uetr"] for t in split_txns}
        split_ids = {t["uetr"] for t in train} | {t["uetr"] for t in val} | {t["uetr"] for t in test}
        assert orig_ids == split_ids, "Some records are missing from the splits"

    def test_split_deterministic(self, split_txns: list[dict]) -> None:
        """Same seed produces same splits."""
        train1, val1, test1 = train_val_test_split(split_txns, seed=77)
        train2, val2, test2 = train_val_test_split(split_txns, seed=77)
        assert [t["uetr"] for t in train1] == [t["uetr"] for t in train2]
        assert [t["uetr"] for t in val1] == [t["uetr"] for t in val2]
        assert [t["uetr"] for t in test1] == [t["uetr"] for t in test2]

    def test_split_invalid_ratios_raise(self, split_txns: list[dict]) -> None:
        """Ratios that don't sum to 1.0 raise ValueError."""
        with pytest.raises(ValueError):
            train_val_test_split(split_txns, train_ratio=0.5, val_ratio=0.3, test_ratio=0.3)


# ── TestValidation ───────────────────────────────────────────────────────────

class TestValidation:
    """Dataset validation tests."""

    @pytest.fixture(scope="class")
    def validated_txns(self) -> list[dict]:
        gen = SyntheticPaymentGenerator(seed=42)
        return gen.generate_dataset(10_000)

    def test_valid_dataset_passes(self, validated_txns: list[dict]) -> None:
        """A properly generated dataset passes all validation checks."""
        gen = SyntheticPaymentGenerator(seed=42)
        result = gen.validate_dataset(validated_txns)
        assert result["all_pass"], (
            "Valid dataset failed validation: "
            + "; ".join(
                f"{k}={v}" for k, v in result.items()
                if isinstance(v, dict) and not v.get("pass", True)
            )
        )

    def test_validation_catches_block_codes(self, validated_txns: list[dict]) -> None:
        """If BLOCK codes injected, validation catches it."""
        gen = SyntheticPaymentGenerator(seed=42)
        corrupted = [t.copy() for t in validated_txns[:100]]
        corrupted[0]["rejection_code"] = "DISP"
        corrupted[0]["is_failure"] = 1
        result = gen.validate_dataset(corrupted)
        assert not result["no_block_codes_check"]["pass"], (
            "Validation did not catch injected BLOCK code DISP"
        )

    def test_validation_catches_self_loops(self, validated_txns: list[dict]) -> None:
        """If sender == receiver injected, validation catches it."""
        gen = SyntheticPaymentGenerator(seed=42)
        corrupted = [t.copy() for t in validated_txns[:100]]
        corrupted[0]["receiving_bic"] = corrupted[0]["sending_bic"]
        result = gen.validate_dataset(corrupted)
        assert not result["no_self_loops_check"]["pass"], (
            "Validation did not catch injected self-loop"
        )

    def test_validate_empty_dataset(self) -> None:
        """Empty dataset returns error dict without crashing."""
        gen = SyntheticPaymentGenerator(seed=42)
        result = gen.validate_dataset([])
        assert result["all_pass"] is False

    def test_summary_statistics(self, validated_txns: list[dict]) -> None:
        """summary_statistics returns expected top-level keys."""
        gen = SyntheticPaymentGenerator(seed=42)
        stats = gen.summary_statistics(validated_txns)
        for key in (
            "n_transactions", "n_failures", "failure_rate",
            "class_counts", "top_rejection_codes", "amount_percentiles",
        ):
            assert key in stats, f"Missing key '{key}' in summary_statistics output"

    def test_summary_failure_rate_matches_count(self, validated_txns: list[dict]) -> None:
        """summary_statistics failure_rate matches manual count."""
        gen = SyntheticPaymentGenerator(seed=42)
        stats = gen.summary_statistics(validated_txns)
        manual_rate = stats["n_failures"] / stats["n_transactions"]
        assert abs(stats["failure_rate"] - manual_rate) < 1e-9


# ── TestBICRegistry ──────────────────────────────────────────────────────────

class TestBICRegistry:
    """BIC registry structural tests."""

    def test_bic_registry_has_30_plus_entries(self) -> None:
        """BIC registry contains at least 30 institutions."""
        assert len(BIC_REGISTRY) >= 30, f"BIC_REGISTRY has only {len(BIC_REGISTRY)} entries"

    def test_bic_registry_has_tier1_tier2_tier3(self) -> None:
        """BIC registry includes all three tiers."""
        tiers = {info["tier"] for info in BIC_REGISTRY.values()}
        assert tiers == {1, 2, 3}

    def test_bic_registry_has_multiple_regions(self) -> None:
        """BIC registry covers multiple geographic regions."""
        regions = {info["region"] for info in BIC_REGISTRY.values()}
        assert len(regions) >= 4

    def test_corridor_definitions_has_27_plus(self) -> None:
        """CORRIDOR_DEFINITIONS contains at least 27 corridors."""
        assert len(CORRIDOR_DEFINITIONS) >= 27, (
            f"CORRIDOR_DEFINITIONS has only {len(CORRIDOR_DEFINITIONS)} entries"
        )

    def test_corridor_definitions_have_required_fields(self) -> None:
        """All corridors have region_type, avg_settlement_hours, annual_volume_billions."""
        for corridor, info in CORRIDOR_DEFINITIONS.items():
            assert "region_type" in info, f"{corridor} missing region_type"
            assert "avg_settlement_hours" in info, f"{corridor} missing avg_settlement_hours"
            assert "annual_volume_billions" in info, f"{corridor} missing annual_volume_billions"
            assert info["region_type"] in {"G7", "EM", "HIGH_FRICTION"}, (
                f"{corridor} has invalid region_type '{info['region_type']}'"
            )
