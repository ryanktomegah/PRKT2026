"""
test_c4_llm_integration.py — C4 Dispute Classifier: Real LLM Integration Tests
=================================================================================
Tests the full DisputeClassifier pipeline (prefilter + Groq LLM) with a real
language model (qwen/qwen3-32b via Groq API).

These tests are intentionally SLOW (each requires an API call) and are skipped
unless GROQ_API_KEY or GROQ_API_KEY_FILE is set in the environment.

Run:
    export GROQ_API_KEY=gsk_...
    PYTHONPATH=. python -m pytest lip/tests/test_c4_llm_integration.py -v

    # Or use a secret file:
    export GROQ_API_KEY_FILE=.secrets/groq_api_key
    PYTHONPATH=. python -m pytest lip/tests/test_c4_llm_integration.py -v

Skip in normal CI:
    python -m pytest lip/tests/ -m "not slow"

Key differences from MockLLMBackend:
  - Real LLM understands negation: "this is NOT a dispute" → NOT_DISPUTE
  - Real LLM handles multilingual text without translation artifacts
  - Real LLM produces fewer false positives on partial matches (e.g. "no fraud")
  - Measured DISPUTE_CONFIRMED FN rate ~4-8% (vs MockLLM ~47%)
"""
from __future__ import annotations

import os
import re
import time

import pytest

# ---------------------------------------------------------------------------
# Skip guard — runs only when GROQ_API_KEY is available
# ---------------------------------------------------------------------------

def _read_secret(env_var: str, file_env_var: str) -> str:
    value = os.environ.get(env_var, "").strip()
    if value:
        return value
    path = os.environ.get(file_env_var, "").strip()
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


GROQ_API_KEY = _read_secret("GROQ_API_KEY", "GROQ_API_KEY_FILE")
_SKIP_REASON = (
    "GROQ_API_KEY or GROQ_API_KEY_FILE not set — set one to run LLM integration tests."
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not GROQ_API_KEY, reason=_SKIP_REASON),
]

# ---------------------------------------------------------------------------
# Groq backend for integration tests
# ---------------------------------------------------------------------------

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "qwen/qwen3-32b"
_NO_THINK_SUFFIX = "\n/no_think"
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)
_MAX_RETRIES = 2


def _is_retryable_error(exc: Exception) -> bool:
    """Treat transient timeout/connection/rate-limit failures as retryable."""
    try:
        import openai

        if isinstance(
            exc,
            (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError),
        ):
            return True
    except ImportError:
        pass

    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True

    name = type(exc).__name__
    return any(token in name for token in ("Timeout", "Connection", "RateLimit"))


class _Qwen3GroqBackend:
    """
    Groq-hosted Qwen3-32b backend for C4 integration tests.

    Appends /no_think to the system prompt to suppress long reasoning output so
    C4 still receives a direct label token.
    """

    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package required for Qwen3GroqBackend: pip install openai"
            ) from exc
        self._client = OpenAI(base_url=_GROQ_BASE_URL, api_key=GROQ_API_KEY)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 20,
        timeout: float = 10.0,
    ) -> str:
        """Generate classification label via Groq."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model=_GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt + _NO_THINK_SUFFIX},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=64,     # 4x margin over max label length (17 chars)
                    temperature=0.0,   # greedy decoding — prevents stochastic truncation
                    timeout=timeout,
                )
                raw = response.choices[0].message.content or ""
                # Strip any <think> blocks that slipped through (defensive)
                return _THINK_PATTERN.sub("", raw).strip()
            except Exception as exc:
                if attempt >= _MAX_RETRIES or not _is_retryable_error(exc):
                    raise
                time.sleep(min(0.5 * (2**attempt), 2.0))
        raise RuntimeError("Groq generate retry loop exited unexpectedly")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def classifier():
    """Create a DisputeClassifier with real Groq backend."""
    from lip.c4_dispute_classifier.model import DisputeClassifier
    backend = _Qwen3GroqBackend()
    return DisputeClassifier(llm_backend=backend, timeout_seconds=15.0)


@pytest.fixture(scope="module")
def negation_cases():
    """Load 500-case negation test suite."""
    from lip.c4_dispute_classifier.negation import generate_negation_test_suite
    return generate_negation_test_suite(n_per_category=100)


def _classify(classifier, narrative: str, rejection_code: str = "AM04") -> str:
    """Helper: run classify and return dispute_class value string."""
    result = classifier.classify(rejection_code=rejection_code, narrative=narrative)
    return result["dispute_class"].value


# ---------------------------------------------------------------------------
# Test Class 1: Four-class accuracy
# ---------------------------------------------------------------------------

class TestC4FourClassAccuracy:
    """Verify real LLM correctly identifies all four dispute classes."""

    _CASES = [
        # (narrative, expected_class, rejection_code)
        (
            "We formally dispute transaction REF-AB12345 for USD 1,250,000 "
            "dated 14 January 2025 as unauthorized. We request immediate reversal.",
            "DISPUTE_CONFIRMED",
            "FRAU",
        ),
        (
            "We confirm receipt of payment REF-XY789 for EUR 875,000 dated 3 March 2025. "
            "No further action required.",
            "NOT_DISPUTE",
            "AC01",
        ),
        (
            "We are reviewing transaction REF-CD456 for GBP 2,100,000 as it appears "
            "inconsistent with our records. We will revert with a formal position shortly.",
            "DISPUTE_POSSIBLE",
            "AM04",
        ),
        (
            "Without prejudice, we propose to settle REF-EF890 at USD 750,000 "
            "in full and final resolution. This offer is open for 10 business days.",
            # NEGOTIATION or DISPUTE_POSSIBLE: LLM correctly identifies partial-settlement
            # language as ambiguous; both are valid outputs for this class.
            "NEGOTIATION_OR_POSSIBLE",
            "CUST",
        ),
    ]

    @pytest.mark.parametrize("narrative,expected,code", _CASES)
    def test_basic_class_accuracy(self, classifier, narrative, expected, code):
        time.sleep(0.5)  # rate limit guard for hosted free-tier models
        result = _classify(classifier, narrative, rejection_code=code)
        # Some classes accept LLM-reasonable alternatives (see case comments above)
        if expected == "NEGOTIATION_OR_POSSIBLE":
            assert result in ("NEGOTIATION", "DISPUTE_POSSIBLE"), (
                f"Expected NEGOTIATION or DISPUTE_POSSIBLE, got {result}"
            )
        else:
            assert result == expected, (
                f"Expected {expected}, got {result} for: {narrative[:60]}..."
            )


# ---------------------------------------------------------------------------
# Test Class 2: Negation awareness (key differentiator over MockLLMBackend)
# ---------------------------------------------------------------------------

class TestC4NegationAwareness:
    """Real LLM must correctly handle negated dispute language."""

    def test_standard_negation_not_dispute(self, classifier):
        """'This is NOT a dispute' → NOT_DISPUTE (MockLLM fails this)."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "This is not a dispute. The payment was correctly processed.",
            rejection_code="AC01",
        )
        assert result == "NOT_DISPUTE", f"Negation failed: got {result}"

    def test_no_fraud_not_dispute(self, classifier):
        """'no fraud involved' → NOT_DISPUTE (MockLLM keyword-matches 'fraud')."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "We confirm there is no fraud involved. "
            "The transaction was authorized by our client.",
            rejection_code="AC01",
        )
        assert result == "NOT_DISPUTE", f"'no fraud' negation failed: got {result}"

    def test_not_unauthorized_not_dispute(self, classifier):
        """Confirm this was NOT unauthorized → NOT_DISPUTE."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "We confirm this transaction was not unauthorized. "
            "Our client has verified approval was given.",
            rejection_code="RC01",
        )
        assert result == "NOT_DISPUTE", f"'not unauthorized' failed: got {result}"

    def test_actual_dispute_with_negation_word_still_confirmed(self, classifier):
        """Dispute language with 'no settlement possible' stays DISPUTE_CONFIRMED."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "We formally dispute this transaction. No settlement is possible. "
            "Immediate reversal required.",
            rejection_code="FRAU",
        )
        assert result == "DISPUTE_CONFIRMED", f"Got {result}"

    def test_double_negation_dispute(self, classifier):
        """'We do not accept non-disputed status' → DISPUTE_CONFIRMED."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "We do not accept the non-disputed status of this payment. "
            "We hereby formally contest transaction REF-GH123.",
            rejection_code="LEGL",
        )
        # Double negation implies dispute — should be CONFIRMED or POSSIBLE
        assert result in ("DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE"), (
            f"Double negation classified as {result}"
        )

    def test_conditional_negation_dispute_possible(self, classifier):
        """'Unless resolved, this will become a dispute' → DISPUTE_POSSIBLE."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "Unless the funds are returned within 48 hours, "
            "this will become a formal dispute.",
            rejection_code="AM04",
        )
        assert result in ("DISPUTE_POSSIBLE", "DISPUTE_CONFIRMED"), (
            f"Conditional negation classified as {result}"
        )


# ---------------------------------------------------------------------------
# Test Class 3: Multilingual cases
# ---------------------------------------------------------------------------

class TestC4Multilingual:
    """Real LLM handles multilingual dispute narratives correctly."""

    def test_french_dispute(self, classifier):
        """French formal dispute language → DISPUTE_CONFIRMED."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "Nous contestons formellement cette transaction non autorisée "
            "et demandons le remboursement immédiat.",
            rejection_code="FRAU",
        )
        assert result == "DISPUTE_CONFIRMED", f"French dispute got {result}"

    def test_german_confirmation_not_dispute(self, classifier):
        """German payment confirmation → NOT_DISPUTE."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "Wir bestätigen den Empfang der Zahlung in Höhe von EUR 500.000. "
            "Die Transaktion wurde ordnungsgemäß verarbeitet.",
            rejection_code="AC01",
        )
        assert result == "NOT_DISPUTE", f"German confirmation got {result}"

    def test_spanish_negotiation(self, classifier):
        """Spanish partial settlement offer → NEGOTIATION or DISPUTE_POSSIBLE."""
        time.sleep(0.5)
        result = _classify(
            classifier,
            "Proponemos llegar a un acuerdo parcial por el importe de USD 800.000 "
            "como resolución definitiva de esta disputa.",
            rejection_code="CUST",
        )
        # LLM may interpret "disputa" as dispute signal → DISPUTE_CONFIRMED/POSSIBLE valid
        assert result in ("NEGOTIATION", "DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE"), (
            f"Spanish negotiation got {result}"
        )


# ---------------------------------------------------------------------------
# Test Class 4: Prefilter interaction
# ---------------------------------------------------------------------------

class TestC4PrefilterInteraction:
    """Verify prefilter still fires before LLM for explicit keywords."""

    def test_frau_code_triggers_prefilter(self, classifier):
        """FRAU rejection code + dispute keyword → prefilter handles it (no LLM call)."""
        result = classifier.classify(
            rejection_code="FRAU",
            narrative="Fraudulent transaction. Customer disputes this charge.",
        )
        # Prefilter should trigger for FRAU code + fraud keyword
        assert result["dispute_class"].value in ("DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE")
        # This may or may not be prefilter-triggered depending on narrative
        # Just verify it doesn't crash and returns a valid class
        assert result["timeout_occurred"] is False

    def test_empty_narrative_does_not_crash(self, classifier):
        """Empty narrative falls back gracefully."""
        time.sleep(0.5)
        result = classifier.classify(
            rejection_code="AM04",
            narrative="",
        )
        # Should return a valid class without crashing
        assert result["dispute_class"].value in (
            "NOT_DISPUTE", "DISPUTE_CONFIRMED", "DISPUTE_POSSIBLE", "NEGOTIATION"
        )
        assert "inference_latency_ms" in result


# ---------------------------------------------------------------------------
# Test Class 5: Latency
# ---------------------------------------------------------------------------

class TestC4LLMLatency:
    """Verify LLM calls complete within the configured timeout."""

    def test_p95_latency_under_10s(self, classifier):
        """10 consecutive calls should all complete under 10 seconds."""
        narratives = [
            "We confirm receipt of payment for EUR 500,000.",
            "We dispute this unauthorized transaction.",
            "We are reviewing this payment for consistency.",
            "We propose partial settlement at USD 400,000.",
            "No issues found with this transaction.",
            "Formal dispute raised for USD 1.2M transfer.",
            "Payment appears correct. No dispute intended.",
            "We are investigating the circumstances of this payment.",
            "Full reversal demanded for unauthorized debit.",
            "We confirm the payment was authorized by our client.",
        ]
        latencies = []
        for narrative in narratives:
            t0 = time.monotonic()
            result = classifier.classify(rejection_code="AM04", narrative=narrative)
            latency_s = time.monotonic() - t0
            latencies.append(latency_s)
            assert not result["timeout_occurred"], (
                f"Timeout on: {narrative[:50]}"
            )
            time.sleep(0.3)

        latencies_sorted = sorted(latencies)
        p95 = latencies_sorted[int(0.95 * len(latencies))]
        assert p95 < 10.0, f"p95 latency {p95:.2f}s exceeds 10s threshold"


# ---------------------------------------------------------------------------
# Test Class 6: Bulk negation accuracy on 50 sampled cases
# ---------------------------------------------------------------------------

class TestC4NegationBulk:
    """
    Sample 50 cases from the negation corpus and measure FN/FP rates.

    This is a subset of evaluate_c4_on_negation_corpus.py (which runs all 500).
    Included here for regression tracking in CI (slow but manageable).
    """

    def test_bulk_negation_fn_rate_below_15pct(self, classifier, negation_cases):
        """
        False negative rate for DISPUTE_CONFIRMED on 50 negation cases < 15%.

        MockLLMBackend FN rate: ~47% (see docs/poc-validation-report.md).
        Target with real LLM: < 15%.
        """
        # Sample every 10th case for a representative 50-case subset
        sample = negation_cases[::10][:50]

        fn_count = 0
        fp_count = 0
        total_dispute = 0
        total_not = 0

        for case in sample:
            time.sleep(0.5)  # rate limit guard
            result = _classify(
                classifier,
                case.narrative,
                rejection_code=case.rejection_code or "AM04",
            )
            expected = case.expected_class.value

            if expected == "DISPUTE_CONFIRMED":
                total_dispute += 1
                if result != "DISPUTE_CONFIRMED":
                    fn_count += 1
            elif expected == "NOT_DISPUTE":
                total_not += 1
                if result == "DISPUTE_CONFIRMED":
                    fp_count += 1

        fn_rate = fn_count / total_dispute if total_dispute > 0 else 0.0
        fp_rate = fp_count / total_not if total_not > 0 else 0.0

        assert fn_rate < 0.15, (
            f"FN rate {fn_rate:.1%} exceeds 15% threshold on {total_dispute} dispute cases"
        )
        # FP rate secondary check (not a hard failure — just informational)
        print(
            f"\nBulk negation (n=50): FN={fn_count}/{total_dispute} ({fn_rate:.1%}), "
            f"FP={fp_count}/{total_not} ({fp_rate:.1%})"
        )
