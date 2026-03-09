"""
model.py — LLM dispute classification
C4 Spec Sections 6-7: Logit-constrained 4-class output, timeout safety
Architecture: GPTQ quantized model, bank-side container, zero outbound
"""
import logging
import os
import time
from typing import Optional

from .multilingual import MultilingualNarrativeProcessor
from .prefilter import PreFilter
from .prompt import DisputePromptBuilder
from .taxonomy import DisputeClass, from_logit_token, timeout_fallback

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INFERENCE_TIMEOUT_SECONDS: float = 5.0

# The model is logit-constrained to emit exactly one of these four tokens.
# Any other output is treated as an unrecoverable parse error and falls back
# to DISPUTE_POSSIBLE (conservative).
VALID_OUTPUT_TOKENS: frozenset = frozenset({
    "NOT_DISPUTE",
    "DISPUTE_CONFIRMED",
    "DISPUTE_POSSIBLE",
    "NEGOTIATION",
})


# ---------------------------------------------------------------------------
# MockLLMBackend
# ---------------------------------------------------------------------------

class MockLLMBackend:
    """
    Keyword-heuristic placeholder for the production GPTQ model.

    Used when the real model weights are not available (unit tests, CI,
    local development without GPU).  The heuristic deliberately mirrors the
    pre-filter keyword logic so that end-to-end tests remain deterministic.

    Args:
        simulate_timeout: When True the backend raises :class:`TimeoutError`
                          after ``timeout`` seconds to exercise the safety path.
    """

    def __init__(self, simulate_timeout: bool = False) -> None:
        self.simulate_timeout = simulate_timeout

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 20,
        timeout: float = 5.0,
    ) -> str:
        """
        Return one of the four valid output tokens based on keyword heuristics.

        Args:
            system_prompt: The system instruction (not used by heuristic).
            user_prompt:   The user-facing payment details string.
            max_tokens:    Max tokens to generate (not used by heuristic).
            timeout:       Wall-clock timeout in seconds.

        Returns:
            One of ``NOT_DISPUTE``, ``DISPUTE_CONFIRMED``,
            ``DISPUTE_POSSIBLE``, ``NEGOTIATION``.

        Raises:
            TimeoutError: If ``simulate_timeout`` is True and *timeout* has
                          been exceeded (simulated).
        """
        if self.simulate_timeout:
            time.sleep(timeout + 0.1)
            raise TimeoutError(
                f"MockLLMBackend: simulated timeout after {timeout}s"
            )

        lowered = user_prompt.lower()

        if "fraud" in lowered or "unauthorized" in lowered or "unauthorised" in lowered:
            return "DISPUTE_CONFIRMED"
        if "negotiate" in lowered or "negotiation" in lowered or "settlement" in lowered:
            return "NEGOTIATION"
        if "dispute" in lowered:
            return "DISPUTE_POSSIBLE"
        return "NOT_DISPUTE"


# ---------------------------------------------------------------------------
# DisputeClassifier
# ---------------------------------------------------------------------------

class DisputeClassifier:
    """
    Primary C4 dispute classifier.

    Pipeline:
      1. Pre-filter (rejection codes + narrative keywords) — fast path.
      2. Language detection and narrative normalisation.
      3. Prompt construction.
      4. LLM inference with timeout guard.
      5. Output token validation and parsing.

    Args:
        llm_backend:      LLM backend instance.  Defaults to
                          :class:`MockLLMBackend` when ``None``.
        timeout_seconds:  Wall-clock inference timeout.  On expiry the
                          classifier returns ``DISPUTE_POSSIBLE``
                          (conservative safety fallback).
    """

    def __init__(
        self,
        llm_backend=None,
        timeout_seconds: float = INFERENCE_TIMEOUT_SECONDS,
    ) -> None:
        if llm_backend is not None:
            self._backend = llm_backend
        elif os.environ.get("LIP_C4_BACKEND", "mock") != "mock":
            from .backends import create_backend
            self._backend = create_backend()
        else:
            self._backend = MockLLMBackend()
        self._timeout = timeout_seconds
        self._prefilter = PreFilter()
        self._prompt_builder = DisputePromptBuilder()
        self._narrative_processor = MultilingualNarrativeProcessor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        rejection_code: Optional[str],
        narrative: Optional[str],
        amount: str = "",
        currency: str = "",
        counterparty: str = "",
    ) -> dict:
        """
        Classify a single payment rejection.

        Args:
            rejection_code: ISO 20022 / SWIFT rejection reason code.
            narrative:      Free-text payment narrative.
            amount:         Transaction amount string (e.g. "1500.00").
            currency:       ISO 4217 currency code (e.g. "EUR").
            counterparty:   BIC or counterparty identifier.

        Returns:
            dict with keys:

            - ``dispute_class``        (:class:`~taxonomy.DisputeClass`)
            - ``confidence``           (float, 1.0 for rule-based, 0.9 for LLM)
            - ``prefilter_triggered``  (bool)
            - ``language``             (str, ISO 639-1)
            - ``inference_latency_ms`` (float)
            - ``timeout_occurred``     (bool)
        """
        t_start = time.monotonic()

        # --- Step 1: Pre-filter ---
        pf_result = self._prefilter.check(rejection_code, narrative)
        if pf_result.triggered:
            elapsed_ms = (time.monotonic() - t_start) * 1000.0
            logger.debug(
                "prefilter triggered: code=%s class=%s reason=%s",
                rejection_code,
                pf_result.dispute_class.value,
                pf_result.reason,
            )
            return {
                "dispute_class": pf_result.dispute_class,
                "confidence": 1.0,
                "prefilter_triggered": True,
                "language": "EN",
                "inference_latency_ms": elapsed_ms,
                "timeout_occurred": False,
            }

        # --- Step 2: Language detection and narrative normalisation ---
        clean_narrative, language = self._narrative_processor.process(
            narrative or ""
        )

        # --- Step 3: Build prompt ---
        prompt = self._prompt_builder.build(
            rejection_code=rejection_code or "N/A",
            narrative=clean_narrative,
            amount=amount,
            currency=currency,
            counterparty=counterparty,
            language=language,
        )

        # --- Step 4: LLM inference with timeout guard ---
        timeout_occurred = False
        raw_output: Optional[str] = None
        try:
            raw_output = self._backend.generate(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                max_tokens=20,
                timeout=self._timeout,
            )
        except TimeoutError:
            timeout_occurred = True
            logger.warning(
                "LLM inference timeout after %.1fs — returning DISPUTE_POSSIBLE",
                self._timeout,
            )
        except Exception as exc:  # noqa: BLE001
            timeout_occurred = True
            logger.error(
                "LLM inference error: %s — returning DISPUTE_POSSIBLE", exc
            )

        elapsed_ms = (time.monotonic() - t_start) * 1000.0

        if timeout_occurred or raw_output is None:
            return {
                "dispute_class": timeout_fallback(),
                "confidence": 0.5,
                "prefilter_triggered": False,
                "language": language,
                "inference_latency_ms": elapsed_ms,
                "timeout_occurred": True,
            }

        # --- Step 5: Parse and validate output token ---
        token = raw_output.strip().upper()
        if token not in VALID_OUTPUT_TOKENS:
            logger.warning(
                "LLM returned unexpected token '%s' — falling back to DISPUTE_POSSIBLE",
                raw_output,
            )
            dispute_class = DisputeClass.DISPUTE_POSSIBLE
            confidence = 0.5
        else:
            dispute_class = from_logit_token(token)
            confidence = 0.9

        return {
            "dispute_class": dispute_class,
            "confidence": confidence,
            "prefilter_triggered": False,
            "language": language,
            "inference_latency_ms": elapsed_ms,
            "timeout_occurred": False,
        }

    def classify_batch(self, cases: list) -> list:
        """
        Classify a batch of payment rejections.

        Args:
            cases: List of dicts, each containing the keyword arguments
                   accepted by :meth:`classify` (``rejection_code``,
                   ``narrative``, and optionally ``amount``, ``currency``,
                   ``counterparty``).

        Returns:
            List of result dicts in the same order as *cases*.
        """
        results = []
        for case in cases:
            result = self.classify(
                rejection_code=case.get("rejection_code"),
                narrative=case.get("narrative"),
                amount=case.get("amount", ""),
                currency=case.get("currency", ""),
                counterparty=case.get("counterparty", ""),
            )
            results.append(result)
        return results


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def classify_dispute(
    rejection_code: Optional[str],
    narrative: Optional[str],
) -> DisputeClass:
    """
    Convenience function for single-shot dispute classification.

    Creates a :class:`DisputeClassifier` with default settings and returns
    the :class:`~taxonomy.DisputeClass` only.

    Args:
        rejection_code: ISO 20022 / SWIFT rejection reason code, or None.
        narrative:      Free-text payment narrative, or None.

    Returns:
        The classified :class:`~taxonomy.DisputeClass`.
    """
    classifier = DisputeClassifier()
    result = classifier.classify(rejection_code=rejection_code, narrative=narrative)
    return result["dispute_class"]
