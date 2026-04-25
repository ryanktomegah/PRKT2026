"""
test_negation_suite.py — C4 negation test suite validation
C4 Spec Section 10: 500 cases across 5 categories
"""

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend
from lip.c4_dispute_classifier.negation import (
    NegationCategory,
    NegationTestRunner,
    generate_negation_test_suite,
)
from lip.c4_dispute_classifier.taxonomy import DisputeClass


class TestNegationSuiteGeneration:
    def test_generates_500_cases(self):
        suite = generate_negation_test_suite(n_per_category=100)
        assert len(suite) == 500

    def test_all_five_categories_represented(self):
        suite = generate_negation_test_suite(n_per_category=100)
        categories = {c.category for c in suite}
        assert NegationCategory.STANDARD_NEGATION in categories
        assert NegationCategory.DOUBLE_NEGATION in categories
        assert NegationCategory.IMPLICIT_NEGATION in categories
        assert NegationCategory.CONDITIONAL_NEGATION in categories
        assert NegationCategory.MULTILINGUAL_NEGATION in categories

    def test_each_category_has_100_cases(self):
        suite = generate_negation_test_suite(n_per_category=100)
        from collections import Counter
        counts = Counter(c.category for c in suite)
        for cat in NegationCategory:
            assert counts[cat] == 100, f"Category {cat} has {counts[cat]} cases, expected 100"

    def test_all_cases_have_expected_class(self):
        suite = generate_negation_test_suite(n_per_category=10)
        for case in suite:
            assert isinstance(case.expected_class, DisputeClass)

    def test_all_cases_have_narrative(self):
        suite = generate_negation_test_suite(n_per_category=10)
        for case in suite:
            assert isinstance(case.narrative, str)
            assert len(case.narrative) > 0

    def test_cases_have_unique_ids(self):
        suite = generate_negation_test_suite(n_per_category=100)
        ids = [c.case_id for c in suite]
        assert len(ids) == len(set(ids))


class TestNegationCategories:
    def test_standard_negation_cases_expected_not_dispute(self):
        """Standard negations like 'not disputed' should expect NOT_DISPUTE."""
        suite = generate_negation_test_suite(n_per_category=100)
        standard = [c for c in suite if c.category == NegationCategory.STANDARD_NEGATION]
        not_dispute_count = sum(1 for c in standard if c.expected_class == DisputeClass.NOT_DISPUTE)
        # Majority should be NOT_DISPUTE
        assert not_dispute_count > 50

    def test_implicit_negation_cases_not_dispute(self):
        """Implicit negations like 'payment settled' should be NOT_DISPUTE."""
        suite = generate_negation_test_suite(n_per_category=100)
        implicit = [c for c in suite if c.category == NegationCategory.IMPLICIT_NEGATION]
        not_dispute_count = sum(1 for c in implicit if c.expected_class == DisputeClass.NOT_DISPUTE)
        assert not_dispute_count > 50

    def test_multilingual_cases_have_language_set(self):
        suite = generate_negation_test_suite(n_per_category=100)
        multi = [c for c in suite if c.category == NegationCategory.MULTILINGUAL_NEGATION]
        languages = {c.language for c in multi}
        # Should have at least 2 languages
        assert len(languages) >= 2


class TestNegationTestRunner:
    def test_runner_returns_results_dict(self):
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        runner = NegationTestRunner(classifier=clf)
        # Use small suite for speed
        suite = generate_negation_test_suite(n_per_category=5)
        results = runner.run_suite(suite)
        assert "total" in results
        assert "passed" in results
        assert "failed" in results
        assert "accuracy" in results
        assert "by_category" in results

    def test_runner_counts_add_up(self):
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        runner = NegationTestRunner(classifier=clf)
        suite = generate_negation_test_suite(n_per_category=5)
        results = runner.run_suite(suite)
        assert results["passed"] + results["failed"] == results["total"]

    def test_accuracy_in_valid_range(self):
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        runner = NegationTestRunner(classifier=clf)
        suite = generate_negation_test_suite(n_per_category=5)
        results = runner.run_suite(suite)
        assert 0.0 <= results["accuracy"] <= 1.0
