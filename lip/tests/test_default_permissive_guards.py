"""Regression tests for default-permissive fallback hardening (B10-07, B3-03, B9-04, B10-05).

Each module that previously used an insecure default must now refuse
construction/usage without explicit configuration or an opt-in flag.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend


class TestZeroByteSaltRefused:
    """B10-07: Hash operations must fail if salt not configured."""

    def test_inference_salt_not_configured_raises(self) -> None:
        """PDInferenceEngine.predict must raise if inference salt is None."""
        import lip.c2_pd_model.inference as inf

        original = inf._INFERENCE_SALT
        try:
            inf._INFERENCE_SALT = None
            engine = inf.PDInferenceEngine.__new__(inf.PDInferenceEngine)
            # Attempting predict should raise before any model call
            with pytest.raises(RuntimeError, match="salt not configured"):
                engine.predict(
                    payment={"amount_usd": 1000},
                    borrower={"tax_id": "TX123"},
                )
        finally:
            inf._INFERENCE_SALT = original

    def test_run_inference_none_salt_raises(self) -> None:
        """run_inference with salt=None must raise ValueError."""
        from lip.c2_pd_model import run_inference

        with pytest.raises(ValueError, match="explicit salt"):
            run_inference(
                model=MagicMock(),
                payment={"amount_usd": 1000},
                borrower={},
                salt=None,
            )


class TestAMLCapsDefaultSentinel:
    """B3-03: LicenseToken default AML caps must be sentinel, not 0."""

    def test_default_caps_are_sentinel(self) -> None:
        from lip.c8_license_manager.license_token import (
            _AML_CAP_UNSET,
            LicenseToken,
        )

        token = LicenseToken(licensee_id="TEST")
        assert token.aml_dollar_cap_usd == _AML_CAP_UNSET
        assert token.aml_count_cap == _AML_CAP_UNSET

    def test_explicit_zero_is_valid_unlimited(self) -> None:
        from lip.c8_license_manager.license_token import LicenseToken

        token = LicenseToken(
            licensee_id="TEST",
            aml_dollar_cap_usd=0,
            aml_count_cap=0,
        )
        assert token.aml_dollar_cap_usd == 0
        assert token.aml_count_cap == 0


class TestMockLLMBackendRefused:
    """B10-05: DisputeClassifier must not silently fall back to MockLLMBackend."""

    def test_no_backend_no_env_raises(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LIP_C4_BACKEND", None)
            with pytest.raises(ValueError, match="No LLM backend"):
                DisputeClassifier()

    def test_explicit_mock_backend_succeeds(self) -> None:
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        assert clf._backend is not None

    def test_env_backend_succeeds(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"LIP_C4_BACKEND": "github_models"}):
            with patch(
                "lip.c4_dispute_classifier.backends.create_backend",
                return_value=MockLLMBackend(),
            ):
                clf = DisputeClassifier()
                assert clf._backend is not None


class TestBudgetRequired:
    """B9-04: P5 cascade budget must be explicitly provided."""

    def test_settlement_trigger_requires_budget(self) -> None:
        from lip.p5_cascade_engine.cascade_settlement_trigger import (
            CascadeSettlementTrigger,
        )

        with pytest.raises(TypeError):
            CascadeSettlementTrigger(
                cascade_graph=MagicMock(),
                bic_to_corporate={},
            )

    def test_stress_bridge_requires_budget(self) -> None:
        from lip.p5_cascade_engine.stress_cascade_bridge import StressCascadeBridge

        with pytest.raises(TypeError):
            StressCascadeBridge(
                cascade_graph=MagicMock(),
                corridor_to_corporates={},
            )
