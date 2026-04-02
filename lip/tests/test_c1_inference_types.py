"""
test_c1_inference_types.py — Tests for C1 inference endpoint Pydantic typing.

Covers:
  - ClassifyRequest schema validation (valid, invalid, edge cases)
  - ClassifyResponse schema construction and from_dict()
  - ClassifyError schema construction
  - InferenceEngine.predict_validated() happy path, validation errors,
    and inference errors
  - run_inference_typed() convenience function
  - Property-based testing (hypothesis) — random valid dicts never crash
  - Golden vector — known payment always returns probability ∈ [0, 1]
  - Backwards-compatibility: predict() still returns a plain dict
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from lip.c1_failure_classifier import (
    ClassifyError,
    ClassifyRequest,
    ClassifyResponse,
    CorridorEmbeddingPipeline,
    SHAPEntry,
    run_inference_typed,
)
from lip.c1_failure_classifier.inference import InferenceEngine
from lip.c1_failure_classifier.model import create_default_model

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> InferenceEngine:
    return InferenceEngine(
        model=create_default_model(),
        embedding_pipeline=CorridorEmbeddingPipeline(),
    )


_VALID_PAYMENT = {
    "sending_bic": "AAAAGB2L",
    "receiving_bic": "BBBBDE2L",
    "amount_usd": 250_000.0,
    "currency_pair": "USD_EUR",
}

_VALID_PAYMENT_WITH_OPTIONAL = {
    **_VALID_PAYMENT,
    "payment_id": "PAY-001",
    "transaction_type": "pacs.002",
    "timestamp_utc": 1700000000.0,
    "metadata": {"internal_ref": "ABC"},
}


# ---------------------------------------------------------------------------
# ClassifyRequest — valid construction
# ---------------------------------------------------------------------------


class TestClassifyRequestValid:
    def test_minimal_required_fields(self):
        req = ClassifyRequest(**_VALID_PAYMENT)
        assert req.sending_bic == "AAAAGB2L"
        assert req.receiving_bic == "BBBBDE2L"
        assert req.amount_usd == 250_000.0
        assert req.currency_pair == "USD_EUR"
        assert req.payment_id is None
        assert req.transaction_type is None
        assert req.timestamp_utc is None
        assert req.metadata is None

    def test_all_optional_fields(self):
        req = ClassifyRequest(**_VALID_PAYMENT_WITH_OPTIONAL)
        assert req.payment_id == "PAY-001"
        assert req.transaction_type == "pacs.002"
        assert req.timestamp_utc == 1700000000.0
        assert req.metadata == {"internal_ref": "ABC"}

    def test_11char_bic_accepted(self):
        req = ClassifyRequest(
            sending_bic="AAAAGB2LXXX",
            receiving_bic="BBBBDE2LXXX",
            amount_usd=100.0,
            currency_pair="GBP_EUR",
        )
        assert req.sending_bic == "AAAAGB2LXXX"

    def test_minimum_amount_exactly_accepted(self):
        req = ClassifyRequest(
            sending_bic="AAAAGB2L",
            receiving_bic="BBBBDE2L",
            amount_usd=0.01,
            currency_pair="USD_EUR",
        )
        assert req.amount_usd == 0.01

    def test_to_dict_contains_required_fields(self):
        req = ClassifyRequest(**_VALID_PAYMENT)
        d = req.to_dict()
        assert d["sending_bic"] == "AAAAGB2L"
        assert d["amount_usd"] == 250_000.0
        assert d["currency_pair"] == "USD_EUR"

    def test_to_dict_includes_payment_id_when_set(self):
        req = ClassifyRequest(**_VALID_PAYMENT_WITH_OPTIONAL)
        d = req.to_dict()
        assert d["payment_id"] == "PAY-001"

    def test_to_dict_omits_none_optional_fields(self):
        req = ClassifyRequest(**_VALID_PAYMENT)
        d = req.to_dict()
        assert "payment_id" not in d
        assert "timestamp_utc" not in d

    def test_to_dict_spreads_metadata(self):
        req = ClassifyRequest(**_VALID_PAYMENT_WITH_OPTIONAL)
        d = req.to_dict()
        assert d.get("internal_ref") == "ABC"

    def test_various_currency_pairs(self):
        for pair in ["USD_EUR", "GBP_JPY", "CHF_SGD"]:
            req = ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=1.0,
                currency_pair=pair,
            )
            assert req.currency_pair == pair


# ---------------------------------------------------------------------------
# ClassifyRequest — invalid inputs / validation errors
# ---------------------------------------------------------------------------


class TestClassifyRequestInvalid:
    def test_missing_sending_bic(self):
        with pytest.raises(ValidationError) as exc_info:
            ClassifyRequest(
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )
        assert "sending_bic" in str(exc_info.value)

    def test_missing_receiving_bic(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )

    def test_missing_amount_usd(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                currency_pair="USD_EUR",
            )

    def test_missing_currency_pair(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
            )

    def test_amount_zero_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=0.0,
                currency_pair="USD_EUR",
            )
        errors = exc_info.value.errors()
        assert any("amount_usd" in str(e.get("loc", "")) for e in errors)

    def test_negative_amount_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=-100.0,
                currency_pair="USD_EUR",
            )

    def test_amount_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=0.009,
                currency_pair="USD_EUR",
            )

    def test_bic_too_short_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ClassifyRequest(
                sending_bic="SHORT",
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )
        errors = exc_info.value.errors()
        assert any("sending_bic" in str(e.get("loc", "")) for e in errors)

    def test_bic_9chars_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2LX",  # 9 chars — neither 8 nor 11
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )

    def test_bic_10chars_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2LXX",  # 10 chars
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )

    def test_receiving_bic_invalid_length(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BAD",
                amount_usd=100.0,
                currency_pair="USD_EUR",
            )

    def test_currency_pair_no_underscore(self):
        with pytest.raises(ValidationError) as exc_info:
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd=100.0,
                currency_pair="USDEUR",
            )
        errors = exc_info.value.errors()
        assert any("currency_pair" in str(e.get("loc", "")) for e in errors)

    def test_currency_pair_wrong_format(self):
        for bad in ["usd_eur", "USD-EUR", "US_EUR", "USD_EU", "1SD_EUR"]:
            with pytest.raises(ValidationError):
                ClassifyRequest(
                    sending_bic="AAAAGB2L",
                    receiving_bic="BBBBDE2L",
                    amount_usd=100.0,
                    currency_pair=bad,
                )

    def test_amount_string_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyRequest(
                sending_bic="AAAAGB2L",
                receiving_bic="BBBBDE2L",
                amount_usd="not_a_number",  # type: ignore[arg-type]
                currency_pair="USD_EUR",
            )


# ---------------------------------------------------------------------------
# SHAPEntry
# ---------------------------------------------------------------------------


class TestSHAPEntry:
    def test_construction(self):
        entry = SHAPEntry(feature="amount_log", value=0.042)
        assert entry.feature == "amount_log"
        assert entry.value == pytest.approx(0.042)

    def test_negative_value_allowed(self):
        entry = SHAPEntry(feature="hour_sin", value=-0.019)
        assert entry.value < 0


# ---------------------------------------------------------------------------
# ClassifyResponse
# ---------------------------------------------------------------------------


class TestClassifyResponse:
    def _raw(self) -> dict:
        return {
            "failure_probability": 0.37,
            "above_threshold": True,
            "inference_latency_ms": 12.5,
            "threshold_used": 0.11,
            "corridor_embedding_used": False,
            "shap_top20": [{"feature": "amount_log", "value": 0.042}],
        }

    def test_from_dict_basic(self):
        resp = ClassifyResponse.from_dict(self._raw())
        assert resp.failure_probability == pytest.approx(0.37)
        assert resp.above_threshold is True
        assert resp.threshold_used == pytest.approx(0.11)
        assert len(resp.shap_top20) == 1
        assert resp.shap_top20[0].feature == "amount_log"

    def test_from_dict_echoes_payment_id(self):
        resp = ClassifyResponse.from_dict(self._raw(), payment_id="PAY-X")
        assert resp.payment_id == "PAY-X"

    def test_probability_out_of_range_rejected(self):
        raw = self._raw()
        raw["failure_probability"] = 1.5
        with pytest.raises(ValidationError):
            ClassifyResponse(**raw)

    def test_negative_probability_rejected(self):
        raw = self._raw()
        raw["failure_probability"] = -0.01
        with pytest.raises(ValidationError):
            ClassifyResponse(**raw)

    def test_empty_shap_allowed(self):
        raw = self._raw()
        raw["shap_top20"] = []
        resp = ClassifyResponse(**raw)
        assert resp.shap_top20 == []

    def test_serialise_roundtrip(self):
        resp = ClassifyResponse.from_dict(self._raw(), payment_id="R1")
        data = resp.model_dump()
        restored = ClassifyResponse(**data)
        assert restored.failure_probability == resp.failure_probability
        assert restored.payment_id == "R1"


# ---------------------------------------------------------------------------
# ClassifyError
# ---------------------------------------------------------------------------


class TestClassifyError:
    def test_validation_error_construction(self):
        err = ClassifyError(
            error_type="VALIDATION_ERROR",
            message="amount_usd must be ≥ 0.01",
            field="amount_usd",
        )
        assert err.error_type == "VALIDATION_ERROR"
        assert err.field == "amount_usd"
        assert err.payment_id is None

    def test_inference_error_construction(self):
        err = ClassifyError(
            error_type="INFERENCE_ERROR",
            message="model raised RuntimeError",
        )
        assert err.error_type == "INFERENCE_ERROR"
        assert err.field is None

    def test_invalid_error_type_rejected(self):
        with pytest.raises(ValidationError):
            ClassifyError(
                error_type="UNKNOWN_TYPE",  # type: ignore[arg-type]
                message="bad",
            )

    def test_payment_id_echoed(self):
        err = ClassifyError(
            error_type="VALIDATION_ERROR",
            message="bad bic",
            payment_id="PAY-ERR",
        )
        assert err.payment_id == "PAY-ERR"


# ---------------------------------------------------------------------------
# InferenceEngine.predict_validated() — happy path
# ---------------------------------------------------------------------------


class TestPredictValidated:
    def test_returns_classify_response_for_valid_dict(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)

    def test_returns_classify_response_for_classify_request(self, engine):
        req = ClassifyRequest(**_VALID_PAYMENT)
        result = engine.predict_validated(req)
        assert isinstance(result, ClassifyResponse)

    def test_probability_in_range(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert 0.0 <= result.failure_probability <= 1.0

    def test_above_threshold_consistent(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        expected = result.failure_probability >= result.threshold_used
        assert result.above_threshold == expected

    def test_shap_top20_list_of_shap_entries(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert isinstance(result.shap_top20, list)
        for entry in result.shap_top20:
            assert isinstance(entry, SHAPEntry)
            assert isinstance(entry.feature, str)
            assert isinstance(entry.value, float)

    def test_payment_id_echoed_in_response(self, engine):
        payment = {**_VALID_PAYMENT, "payment_id": "ECHO-ME"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyResponse)
        assert result.payment_id == "ECHO-ME"

    def test_payment_id_none_when_absent(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert result.payment_id is None

    def test_with_optional_fields(self, engine):
        result = engine.predict_validated(_VALID_PAYMENT_WITH_OPTIONAL)
        assert isinstance(result, ClassifyResponse)
        assert result.payment_id == "PAY-001"

    def test_11char_bic_accepted(self, engine):
        payment = {
            **_VALID_PAYMENT,
            "sending_bic": "AAAAGB2LXXX",
            "receiving_bic": "BBBBDE2LXXX",
        }
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyResponse)


# ---------------------------------------------------------------------------
# InferenceEngine.predict_validated() — validation errors
# ---------------------------------------------------------------------------


class TestPredictValidatedErrors:
    def test_missing_required_field_returns_classify_error(self, engine):
        result = engine.predict_validated({"sending_bic": "AAAAGB2L"})
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"

    def test_zero_amount_returns_classify_error(self, engine):
        payment = {**_VALID_PAYMENT, "amount_usd": 0.0}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"
        assert result.field is not None
        assert "amount_usd" in result.field

    def test_negative_amount_returns_classify_error(self, engine):
        payment = {**_VALID_PAYMENT, "amount_usd": -1.0}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"

    def test_invalid_bic_returns_classify_error(self, engine):
        payment = {**_VALID_PAYMENT, "sending_bic": "SHORT"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"
        assert result.field is not None
        assert "sending_bic" in result.field

    def test_invalid_currency_pair_returns_classify_error(self, engine):
        payment = {**_VALID_PAYMENT, "currency_pair": "USDEUR"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"
        assert result.field is not None
        assert "currency_pair" in result.field

    def test_payment_id_echoed_in_validation_error(self, engine):
        payment = {**_VALID_PAYMENT, "amount_usd": -99.0, "payment_id": "BAD-PAY"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.payment_id == "BAD-PAY"

    def test_payment_id_none_when_absent_in_error(self, engine):
        payment = {"sending_bic": "AAAAGB2L"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.payment_id is None

    def test_string_amount_returns_classify_error(self, engine):
        payment = {**_VALID_PAYMENT, "amount_usd": "bad"}
        result = engine.predict_validated(payment)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"
        assert result.field is not None
        assert "amount_usd" in result.field

    def test_empty_dict_returns_classify_error(self, engine):
        result = engine.predict_validated({})
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"

    def test_inference_error_returned_on_model_crash(self, engine, monkeypatch):
        def _crash(_payment_dict):
            raise RuntimeError("simulated model failure")

        monkeypatch.setattr(engine, "predict", _crash)
        result = engine.predict_validated(_VALID_PAYMENT)
        assert isinstance(result, ClassifyError)
        assert result.error_type == "INFERENCE_ERROR"
        assert "simulated model failure" in result.message


# ---------------------------------------------------------------------------
# run_inference_typed() convenience function
# ---------------------------------------------------------------------------


class TestRunInferenceTyped:
    def test_valid_dict_returns_classify_response(self):
        result = run_inference_typed(_VALID_PAYMENT)
        assert isinstance(result, ClassifyResponse)

    def test_classify_request_object_accepted(self):
        req = ClassifyRequest(**_VALID_PAYMENT)
        result = run_inference_typed(req)
        assert isinstance(result, ClassifyResponse)

    def test_invalid_dict_returns_classify_error(self):
        result = run_inference_typed({"sending_bic": "AAAAGB2L"})
        assert isinstance(result, ClassifyError)
        assert result.error_type == "VALIDATION_ERROR"

    def test_returns_classify_error_for_zero_amount(self):
        bad = {**_VALID_PAYMENT, "amount_usd": 0.0}
        result = run_inference_typed(bad)
        assert isinstance(result, ClassifyError)


# ---------------------------------------------------------------------------
# Backwards-compatibility: predict() still returns plain dict
# ---------------------------------------------------------------------------


class TestBackwardsCompatibility:
    def test_predict_returns_dict(self, engine):
        result = engine.predict(_VALID_PAYMENT)
        assert isinstance(result, dict)

    def test_predict_has_all_legacy_keys(self, engine):
        result = engine.predict(_VALID_PAYMENT)
        for key in (
            "failure_probability",
            "above_threshold",
            "inference_latency_ms",
            "threshold_used",
            "corridor_embedding_used",
            "shap_top20",
        ):
            assert key in result

    def test_predict_not_pydantic_model(self, engine):
        result = engine.predict(_VALID_PAYMENT)
        assert not isinstance(result, ClassifyResponse)


# ---------------------------------------------------------------------------
# Golden vector — deterministic output shape/range
# ---------------------------------------------------------------------------


class TestGoldenVector:
    _GOLDEN_PAYMENT = {
        "payment_id": "GOLDEN-001",
        "sending_bic": "DEUTDEDB",
        "receiving_bic": "ICICINBB",
        "amount_usd": 1_000_000.0,
        "currency_pair": "EUR_INR",
        "transaction_type": "pacs.008",
        "timestamp_utc": 1711929600.0,
    }

    def test_golden_vector_returns_response(self, engine):
        result = engine.predict_validated(self._GOLDEN_PAYMENT)
        assert isinstance(result, ClassifyResponse)

    def test_golden_vector_probability_in_range(self, engine):
        result = engine.predict_validated(self._GOLDEN_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert 0.0 <= result.failure_probability <= 1.0

    def test_golden_vector_shap_non_empty(self, engine):
        result = engine.predict_validated(self._GOLDEN_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert len(result.shap_top20) > 0

    def test_golden_vector_payment_id_echoed(self, engine):
        result = engine.predict_validated(self._GOLDEN_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        assert result.payment_id == "GOLDEN-001"

    def test_golden_vector_shap_sorted_by_abs(self, engine):
        result = engine.predict_validated(self._GOLDEN_PAYMENT)
        assert isinstance(result, ClassifyResponse)
        values = [abs(e.value) for e in result.shap_top20]
        assert values == sorted(values, reverse=True)


# ---------------------------------------------------------------------------
# Property-based tests (hypothesis) — random valid payments never crash
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _BIC8 = st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=8, max_size=8
    )
    _BIC11 = st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=11, max_size=11
    )
    _BIC = st.one_of(_BIC8, _BIC11)
    _CCY3 = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=3, max_size=3)
    _PAIR = st.builds(lambda a, b: f"{a}_{b}", _CCY3, _CCY3)

    _HAS_HYPOTHESIS = True

    # Shared engine for all property-based tests — avoid recreating model per example.
    _pb_engine = InferenceEngine(
        model=create_default_model(),
        embedding_pipeline=CorridorEmbeddingPipeline(),
    )

    class TestPropertyBased:
        @given(
            sending_bic=_BIC,
            receiving_bic=_BIC,
            amount=st.floats(
                min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False
            ),
            pair=_PAIR,
        )
        @settings(max_examples=50, deadline=2000)
        def test_valid_random_payment_never_crashes(
            self, sending_bic, receiving_bic, amount, pair
        ):
            result = _pb_engine.predict_validated({
                "sending_bic": sending_bic,
                "receiving_bic": receiving_bic,
                "amount_usd": amount,
                "currency_pair": pair,
            })
            # Must return either a ClassifyResponse or a ClassifyError (never raise)
            assert isinstance(result, (ClassifyResponse, ClassifyError))

        @given(
            amount=st.one_of(
                st.floats(max_value=0.0, allow_nan=False),
                st.just(None),
                st.text(min_size=1),
            )
        )
        @settings(max_examples=30, deadline=2000)
        def test_invalid_amount_always_returns_classify_error(self, amount):
            result = _pb_engine.predict_validated({
                "sending_bic": "AAAAGB2L",
                "receiving_bic": "BBBBDE2L",
                "amount_usd": amount,
                "currency_pair": "USD_EUR",
            })
            assert isinstance(result, ClassifyError)
            assert result.error_type == "VALIDATION_ERROR"

except ImportError:
    _HAS_HYPOTHESIS = False
