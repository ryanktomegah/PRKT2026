"""
backends.py — Pluggable LLM backends for C4 Dispute Classifier.

Current validated backend: Groq API (qwen/qwen3-32b) — requires outbound.
Future bank-side: GPTQ quantized local model (zero-outbound, GPU required).
Dev/staging/production: OpenAICompatibleBackend via env var.

Backend selection via LIP_C4_BACKEND env var:
  mock          — MockLLMBackend (default for tests/CI, no credentials needed)
  github_models — GitHub Models API (free, requires GITHUB_TOKEN)
                  Endpoint: https://models.inference.ai.azure.com
                  Models: Mistral-7B-Instruct (default), mistral-small, etc.
  groq          — Groq API (requires GROQ_API_KEY or GROQ_API_KEY_FILE)
                  Endpoint: https://api.groq.com/openai/v1
                  Model: qwen/qwen3-32b (default)
  openai_compat — Generic OpenAI-compatible endpoint
                  Requires: LIP_C4_BASE_URL, LIP_C4_API_KEY or LIP_C4_API_KEY_FILE, LIP_C4_MODEL

Architecture note: The zero-outbound K8s network policy in network-policies.yaml
applies to PRODUCTION bank-side containers. Dev/staging deployments (without
the C4 zero-outbound NetworkPolicy) may use the hosted backends below.
"""
import logging
import os
import time
from typing import Optional

from lip.common.circuit_breaker import CircuitBreaker
from lip.common.local_env import load_repo_env_file

logger = logging.getLogger(__name__)

# Allow local dev/test runs to pick up gitignored .env.local without
# hardcoding secrets into source or overriding real deployment env vars.
load_repo_env_file()

# Shared circuit breaker for all OpenAI-compatible API calls (GAP-19)
_api_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout_seconds=60.0,
    name="c4_llm_api",
)

# Default models for known hosted providers
_GITHUB_MODELS_DEFAULT = "Mistral-7B-Instruct"
_GROQ_DEFAULT = "qwen/qwen3-32b"
_GITHUB_BASE_URL = "https://models.inference.ai.azure.com"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def _read_secret(env_var: str, file_env_var: str) -> str:
    """Read a secret from env or a filesystem secret mount.

    Environment variables remain the primary path for local development.
    ``*_FILE`` supports mounted secret files in container runtimes.
    """
    value = os.environ.get(env_var, "").strip()
    if value:
        return value

    secret_path = os.environ.get(file_env_var, "").strip()
    if not secret_path:
        return ""

    try:
        with open(secret_path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError as exc:
        logger.warning("Unable to read secret file %s for %s: %s", secret_path, env_var, exc)
        return ""


def _classify_openai_error(exc: Exception) -> tuple[bool, bool]:
    """Return ``(retryable, timeout_like)`` for OpenAI-compatible client errors."""
    timeout_like = isinstance(exc, TimeoutError)
    connection_like = False
    rate_limited = False
    status_code = getattr(exc, "status_code", None)

    try:
        import openai as _openai  # noqa: PLC0415

        timeout_like = timeout_like or isinstance(exc, _openai.APITimeoutError)
        connection_like = isinstance(exc, _openai.APIConnectionError)
        rate_limited = isinstance(exc, _openai.RateLimitError)
    except ImportError:
        pass

    name = type(exc).__name__
    timeout_like = timeout_like or "Timeout" in name
    connection_like = connection_like or "Connection" in name
    rate_limited = rate_limited or "RateLimit" in name

    retryable = timeout_like or connection_like or rate_limited
    retryable = retryable or status_code in _RETRYABLE_STATUS_CODES
    return retryable, timeout_like


class OpenAICompatibleBackend:
    """
    LLM backend that calls any OpenAI-compatible REST API.

    Works with GitHub Models, Groq, Mistral AI, and any endpoint
    that implements the OpenAI Chat Completions API.

    Requires: pip install openai

    Args:
        base_url: API base URL (e.g. https://models.inference.ai.azure.com)
        api_key:  Authentication token (GitHub token, Groq API key, etc.)
        model:    Model identifier string
        timeout:  Hard client-side timeout in seconds (guards against hung connections)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 10.0,
        extra_body: Optional[dict] = None,
        max_retries: int = 2,
    ) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package required for OpenAICompatibleBackend. "
                "Install with: pip install openai"
            ) from exc
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._timeout = timeout
        self._extra_body = extra_body
        self._max_retries = max_retries
        logger.info(
            "OpenAICompatibleBackend initialised: base_url=%s model=%s",
            base_url,
            model,
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 20,
        timeout: float = 5.0,
    ) -> str:
        """
        Call the remote API and return the generated text.

        GAP-19: Wrapped with circuit breaker. On circuit open, raises
        CircuitOpenError; DisputeClassifier falls back to DISPUTE_POSSIBLE.

        Args:
            system_prompt: System instruction string.
            user_prompt:   User-facing payment details string.
            max_tokens:    Max tokens to generate (20 is enough for a 4-class label).
            timeout:       Per-call timeout; capped to self._timeout if smaller.

        Returns:
            Raw string returned by the model (caller validates against VALID_OUTPUT_TOKENS).

        Raises:
            TimeoutError: If the API call exceeds the timeout.
            CircuitOpenError: If the circuit breaker is open after repeated failures.
            Exception:    Other API errors (network, auth) propagate to DisputeClassifier
                          which falls back to DISPUTE_POSSIBLE.
        """
        effective_timeout = min(timeout, self._timeout)

        def _do_call():
            for attempt in range(self._max_retries + 1):
                try:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        timeout=effective_timeout,
                        extra_body=self._extra_body,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as exc:
                    retryable, timeout_like = _classify_openai_error(exc)
                    if retryable and attempt < self._max_retries:
                        backoff_seconds = min(0.5 * (2**attempt), 2.0)
                        logger.warning(
                            "OpenAICompatibleBackend transient error (%s); retrying in %.1fs "
                            "(attempt %d/%d)",
                            type(exc).__name__,
                            backoff_seconds,
                            attempt + 1,
                            self._max_retries,
                        )
                        time.sleep(backoff_seconds)
                        continue
                    if timeout_like:
                        raise TimeoutError(
                            f"OpenAICompatibleBackend: request timed out after {effective_timeout}s"
                        ) from exc
                    raise

        return _api_circuit_breaker.call(_do_call)


def create_backend(backend_type: Optional[str] = None):
    """
    Factory: instantiate the appropriate LLM backend from env vars.

    Falls back gracefully to MockLLMBackend if credentials are absent or the
    openai package is not installed — so CI always works without extra deps.

    Args:
        backend_type: Override for LIP_C4_BACKEND env var. If None, reads env.

    Returns:
        A backend with a generate(system_prompt, user_prompt, ...) method.
    """
    # Import here to avoid circular dependency (model.py imports backends.py)
    from lip.c4_dispute_classifier.model import MockLLMBackend

    resolved = backend_type or os.environ.get("LIP_C4_BACKEND", "mock")
    if resolved == "mock":
        logger.critical(
            "C4 using MockLLMBackend (no negation awareness). "
            "Set LIP_C4_BACKEND=groq|github_models|openai_compat for production. "
            "MockLLMBackend will misclassify negated disputes (e.g. 'no fraud').",
        )

    if resolved == "github_models":
        api_key = os.environ.get("GITHUB_TOKEN", "")
        model = os.environ.get("LIP_C4_MODEL", _GITHUB_MODELS_DEFAULT)
        if not api_key:
            logger.warning(
                "LIP_C4_BACKEND=github_models but GITHUB_TOKEN not set — "
                "falling back to MockLLMBackend"
            )
            return MockLLMBackend()
        try:
            return OpenAICompatibleBackend(_GITHUB_BASE_URL, api_key, model)
        except ImportError:
            logger.warning("openai package missing — falling back to MockLLMBackend")
            return MockLLMBackend()

    if resolved == "groq":
        api_key = _read_secret("GROQ_API_KEY", "GROQ_API_KEY_FILE")
        model = os.environ.get("LIP_C4_MODEL", _GROQ_DEFAULT)
        if not api_key:
            logger.warning(
                "LIP_C4_BACKEND=groq but GROQ_API_KEY/_FILE not set — "
                "falling back to MockLLMBackend"
            )
            return MockLLMBackend()
        try:
            return OpenAICompatibleBackend(_GROQ_BASE_URL, api_key, model)
        except ImportError:
            logger.warning("openai package missing — falling back to MockLLMBackend")
            return MockLLMBackend()

    if resolved == "openai_compat":
        base_url = os.environ.get("LIP_C4_BASE_URL", "")
        api_key = _read_secret("LIP_C4_API_KEY", "LIP_C4_API_KEY_FILE")
        model = os.environ.get("LIP_C4_MODEL", "")
        if not (base_url and api_key and model):
            logger.warning(
                "LIP_C4_BACKEND=openai_compat but LIP_C4_BASE_URL/API_KEY(_FILE)/MODEL not set — "
                "falling back to MockLLMBackend"
            )
            return MockLLMBackend()
        try:
            return OpenAICompatibleBackend(base_url, api_key, model)
        except ImportError:
            logger.warning("openai package missing — falling back to MockLLMBackend")
            return MockLLMBackend()

    # Default: "mock" or unrecognised value
    return MockLLMBackend()
