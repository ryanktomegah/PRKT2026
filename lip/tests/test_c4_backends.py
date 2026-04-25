"""
test_c4_backends.py — Tests for C4 pluggable LLM backends.
Covers: factory fallback logic, OpenAICompatibleBackend, missing-package guard.
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class TestCreateBackendFactory(unittest.TestCase):
    """create_backend() factory returns correct type based on env vars."""

    def test_default_returns_mock(self):
        """No env var → MockLLMBackend."""
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LIP_C4_BACKEND", None)
            backend = create_backend()
        self.assertIsInstance(backend, MockLLMBackend)

    def test_explicit_mock_returns_mock(self):
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        backend = create_backend("mock")
        self.assertIsInstance(backend, MockLLMBackend)

    def test_github_models_no_token_falls_back_to_mock(self):
        """github_models with no GITHUB_TOKEN → graceful fallback to Mock."""
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            backend = create_backend("github_models")
        self.assertIsInstance(backend, MockLLMBackend)

    def test_groq_no_key_falls_back_to_mock(self):
        """groq with no GROQ_API_KEY → graceful fallback to Mock."""
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GROQ_API_KEY", None)
            os.environ.pop("GROQ_API_KEY_FILE", None)
            backend = create_backend("groq")
        self.assertIsInstance(backend, MockLLMBackend)

    def test_openai_compat_missing_vars_falls_back_to_mock(self):
        """openai_compat with no base_url/api_key/model → fallback."""
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        with patch.dict(os.environ, {}, clear=False):
            for k in ("LIP_C4_BASE_URL", "LIP_C4_API_KEY", "LIP_C4_MODEL"):
                os.environ.pop(k, None)
            backend = create_backend("openai_compat")
        self.assertIsInstance(backend, MockLLMBackend)

    def test_unknown_backend_type_returns_mock(self):
        from lip.c4_dispute_classifier.backends import create_backend
        from lip.c4_dispute_classifier.model import MockLLMBackend

        backend = create_backend("nonexistent_backend")
        self.assertIsInstance(backend, MockLLMBackend)

    def test_github_models_with_token_constructs_openai_backend(self):
        """github_models + GITHUB_TOKEN + openai installed → OpenAICompatibleBackend."""
        from lip.c4_dispute_classifier.backends import (
            OpenAICompatibleBackend,
            create_backend,
        )

        # Build a minimal fake openai module so we don't need the real package
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = MagicMock(return_value=MagicMock())
        with patch.dict(sys.modules, {"openai": fake_openai}):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}):
                backend = create_backend("github_models")
        self.assertIsInstance(backend, OpenAICompatibleBackend)


class TestOpenAICompatibleBackend(unittest.TestCase):
    """OpenAICompatibleBackend.generate() delegates to openai.OpenAI correctly."""

    def _make_backend(self):
        """Build backend with a fully mocked openai.OpenAI client."""
        from lip.c4_dispute_classifier.backends import OpenAICompatibleBackend

        fake_openai = types.ModuleType("openai")
        mock_client_cls = MagicMock()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        fake_openai.OpenAI = mock_client_cls

        with patch.dict(sys.modules, {"openai": fake_openai}):
            backend = OpenAICompatibleBackend(
                base_url="https://example.com",
                api_key="test_key",
                model="test-model",
            )
        # Swap out the internal client with our mock
        backend._client = mock_client
        return backend, mock_client

    def test_generate_returns_stripped_content(self):
        backend, mock_client = self._make_backend()

        mock_choice = MagicMock()
        mock_choice.message.content = "  NOT_DISPUTE  "
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = backend.generate("sys", "user", max_tokens=20, timeout=5.0)
        self.assertEqual(result, "NOT_DISPUTE")

    def test_generate_passes_correct_messages(self):
        backend, mock_client = self._make_backend()

        mock_choice = MagicMock()
        mock_choice.message.content = "DISPUTE_CONFIRMED"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        backend.generate("sys_text", "user_text", max_tokens=10, timeout=3.0)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "sys_text"})
        self.assertEqual(messages[1], {"role": "user", "content": "user_text"})
        self.assertEqual(call_kwargs["max_tokens"], 10)

    def test_generate_raises_timeout_on_api_timeout(self):
        """openai APITimeoutError (or any exception with 'Timeout' in name) → TimeoutError."""
        backend, mock_client = self._make_backend()

        # Simulate openai.APITimeoutError (name contains "Timeout" → caught by backends.py)
        class APITimeoutError(Exception):
            pass

        mock_client.chat.completions.create.side_effect = APITimeoutError("timed out")

        with self.assertRaises(TimeoutError):
            backend.generate("sys", "user")

    def test_missing_openai_package_raises_import_error(self):
        """If openai is not installed, ImportError is raised at construction."""
        # Temporarily remove openai from sys.modules
        saved = sys.modules.get("openai")
        sys.modules["openai"] = None  # type: ignore[assignment]
        try:
            # Force re-import of the backends module to pick up missing openai
            if "lip.c4_dispute_classifier.backends" in sys.modules:
                del sys.modules["lip.c4_dispute_classifier.backends"]
            from lip.c4_dispute_classifier.backends import OpenAICompatibleBackend

            with self.assertRaises(ImportError):
                OpenAICompatibleBackend("https://x.com", "key", "model")
        finally:
            if saved is None:
                sys.modules.pop("openai", None)
            else:
                sys.modules["openai"] = saved
            # Reload backends to restore clean state
            if "lip.c4_dispute_classifier.backends" in sys.modules:
                del sys.modules["lip.c4_dispute_classifier.backends"]


class TestDisputeClassifierBackendSelection(unittest.TestCase):
    """DisputeClassifier picks the right backend based on LIP_C4_BACKEND."""

    def test_no_backend_raises(self):
        """B10-05: DisputeClassifier must refuse silent MockLLMBackend fallback."""
        from lip.c4_dispute_classifier.model import DisputeClassifier

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LIP_C4_BACKEND", None)
            with self.assertRaises(ValueError, msg="single_replica"):
                DisputeClassifier()

    def test_explicit_injection_overrides_env(self):
        """Injected backend always wins, regardless of env var."""
        from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend

        sentinel = MockLLMBackend()
        with patch.dict(os.environ, {"LIP_C4_BACKEND": "github_models"}):
            dc = DisputeClassifier(llm_backend=sentinel)
        self.assertIs(dc._backend, sentinel)


if __name__ == "__main__":
    unittest.main()
