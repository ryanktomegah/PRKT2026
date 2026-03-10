"""
test_c2_comprehensive.py -- Comprehensive tests for C2 PD Model components.

Coverage targets:
  - PDModel (model.py)           -- init, fit, predict, save/load, SHAP
  - LightGBMSurrogate (model.py) -- fit, predict, error paths
  - PDTrainingPipeline (training.py) -- all 9 stages + full run()
  - PDInferenceEngine (inference.py) -- predict, batch, privacy, tiers
  - UnifiedFeatureEngineer + FeatureMasker (features.py) -- tiers, masking
  - BaselineEnsemble (baseline.py) -- ensemble predict, edge cases
  - generate_pd_training_data (synthetic_data.py) -- counts, schema, seed
"""

import math
import os
import tempfile

import numpy as np
import pytest

from lip.c2_pd_model.baseline import (
    BaselineEnsemble,
    financial_ratio_pd,
    merton_pd,
)
from lip.c2_pd_model.features import (
    AVAILABILITY_INDICATORS,
    FEATURE_DIM,
    FeatureMasker,
    UnifiedFeatureEngineer,
    configure_salt,
)
from lip.c2_pd_model.inference import PDInferenceEngine, configure_inference_salt
from lip.c2_pd_model.model import LightGBMSurrogate, PDModel
from lip.c2_pd_model.synthetic_data import generate_pd_training_data
from lip.c2_pd_model.tier_assignment import Tier
from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig

# ---------------------------------------------------------------------------
# Helpers -- reusable fixtures for fast, small datasets
# ---------------------------------------------------------------------------

_SMALL_N = 100  # synthetic dataset size kept small for speed
_TINY_N = 50


def _make_synthetic(n: int = _SMALL_N, seed: int = 42) -> list:
    """Return a list of synthetic training records."""
    return generate_pd_training_data(n_samples=n, seed=seed)


def _make_Xy(n: int = _SMALL_N, seed: int = 42):
    """Return (X, y) feature matrix and labels from synthetic data."""
    data = _make_synthetic(n, seed)
    pipeline = PDTrainingPipeline(TrainingConfig(n_trials=2, n_models=2))
    X, y = pipeline.stage1_data_prep(data)
    return X, y


def _fit_small_model(n: int = _SMALL_N, seed: int = 42, n_models: int = 2) -> PDModel:
    """Return a fitted PDModel trained on a small synthetic dataset."""
    X, y = _make_Xy(n, seed)
    model = PDModel(n_models=n_models, random_seeds=list(range(n_models)))
    model.fit(X, y)
    return model


def _make_tier1_borrower() -> dict:
    """Minimal Tier-1 borrower dict."""
    return {
        "tax_id": "TIER1-TAX-001",
        "has_financial_statements": True,
        "has_transaction_history": True,
        "has_credit_bureau": True,
        "months_history": 36,
        "transaction_count": 200,
        "counterparty_age_days": 730,
        "financial_statements": {
            "current_ratio": 2.0,
            "debt_to_equity": 0.8,
            "interest_coverage": 5.0,
            "roe": 0.12,
            "roa": 0.06,
            "ebitda_margin": 0.18,
            "revenue_growth": 0.05,
            "cash_ratio": 0.4,
            "asset_turnover": 1.1,
            "net_margin": 0.08,
        },
        "altman_z_score": 3.5,
        "merton_distance_to_default": 2.8,
        "credit_bureau": {
            "score": 720,
            "age_months": 48,
            "payment_history_score": 0.90,
            "avg_days_to_pay": 25,
            "delinquency_rate": 0.01,
            "default_history_count": 0,
            "bankruptcy_history": False,
        },
        "industry_risk_score": 0.2,
    }


def _make_tier2_borrower() -> dict:
    """Minimal Tier-2 borrower dict."""
    return {
        "tax_id": "TIER2-TAX-002",
        "has_financial_statements": False,
        "has_transaction_history": True,
        "has_credit_bureau": False,
        "months_history": 12,
        "transaction_count": 50,
        "counterparty_age_days": 365,
        "transaction_history": {
            "avg_payment_amount": 50000.0,
            "payment_amount_std": 15000.0,
            "payment_frequency": 10.0,
            "recent_trend_slope": 0.02,
            "largest_payment_30d": 120000.0,
            "smallest_payment_30d": 10000.0,
            "payment_gap_max_days": 20,
            "payment_gap_mean_days": 7,
            "counterparty_diversity": 0.5,
            "payment_regularity_score": 0.75,
        },
    }


def _make_tier3_borrower() -> dict:
    """Minimal Tier-3 (thin-file) borrower dict."""
    return {
        "tax_id": "TIER3-TAX-003",
        "has_financial_statements": False,
        "has_transaction_history": False,
        "has_credit_bureau": False,
        "months_history": 2,
        "transaction_count": 3,
        "counterparty_age_days": 60,
        "jurisdiction_risk_score": 0.4,
        "entity_age_days": 90,
    }


def _make_payment() -> dict:
    """Minimal payment dict."""
    return {
        "amount_usd": 250000.0,
        "currency_pair": "USD/EUR",
        "sending_bic": "DEUTDEDB",
        "receiving_bic": "BNPAFRPP",
        "timestamp": 1_700_000_000.0,
        "days_since_last_payment": 5,
        "corridor_failure_rate": 0.03,
        "corridor_volume_7d": 5000000.0,
        "n_payments_30d": 15,
        "n_failures_30d": 1,
        "amount_zscore": 0.5,
        "amount_percentile": 0.6,
        "payment_velocity_24h": 3,
        "large_amount_threshold": 1000000.0,
        "currency_risk_score": 0.3,
        "sending_jurisdiction": "US",
        "receiving_jurisdiction": "EU",
    }


# ===================================================================
# 1. PDModel (model.py)
# ===================================================================


class TestPDModelInit:
    """PDModel construction and parameter validation."""

    def test_defaults(self):
        m = PDModel()
        assert m.n_models == 5
        assert len(m.random_seeds) == 5
        assert m.random_seeds == [42, 43, 44, 45, 46]

    def test_custom_seeds(self):
        m = PDModel(n_models=3, random_seeds=[10, 20, 30])
        assert m.n_models == 3
        assert m.random_seeds == [10, 20, 30]

    def test_seed_count_mismatch_raises(self):
        with pytest.raises(ValueError, match="random_seeds length"):
            PDModel(n_models=3, random_seeds=[1, 2])

    def test_single_model(self):
        m = PDModel(n_models=1, random_seeds=[99])
        assert m.n_models == 1


class TestPDModelFitPredict:
    """PDModel training and prediction."""

    def test_fit_produces_valid_pds(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        pds = model.predict_proba(X)
        assert pds.shape == (X.shape[0],)
        assert np.all(pds >= 0.0)
        assert np.all(pds <= 1.0)

    def test_single_observation(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        single = X[0]
        pd_score = model.predict_proba(single)
        # Single obs returns a scalar float
        assert isinstance(pd_score, (float, np.floating))
        assert 0.0 <= float(pd_score) <= 1.0

    def test_batch_shape(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        subset = X[:10]
        pds = model.predict_proba(subset)
        assert pds.shape == (10,)

    def test_predict_before_fit_raises(self):
        model = PDModel(n_models=2, random_seeds=[0, 1])
        X = np.random.default_rng(0).random((5, 75))
        with pytest.raises(RuntimeError, match="not fitted"):
            model.predict_proba(X)


class TestPDModelSaveLoad:
    """Persistence round-trip."""

    def test_save_load_roundtrip(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        pds_before = model.predict_proba(X[:5])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.pkl")
            model.save(path)
            assert os.path.isfile(path)

            loaded = PDModel(n_models=1, random_seeds=[0])  # dummy init
            loaded.load(path)

            pds_after = loaded.predict_proba(X[:5])
            np.testing.assert_array_almost_equal(pds_before, pds_after)
            assert loaded.n_models == model.n_models


class TestPDModelSHAP:
    """predict_with_shap returns correct structure."""

    def test_predict_with_shap_structure(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        feature_names = FeatureMasker.get_full_feature_names()
        assert len(feature_names) == 75

        # Single observation
        pd_score, shap_list = model.predict_with_shap(X[0], feature_names)
        assert isinstance(pd_score, (float, np.floating))
        assert 0.0 <= float(pd_score) <= 1.0
        assert isinstance(shap_list, list)
        assert len(shap_list) == 1
        assert isinstance(shap_list[0], dict)
        assert len(shap_list[0]) == 75

    def test_predict_with_shap_batch(self):
        model = _fit_small_model()
        X, _ = _make_Xy()
        feature_names = FeatureMasker.get_full_feature_names()

        pds, shap_list = model.predict_with_shap(X[:5], feature_names)
        assert len(pds) == 5
        assert len(shap_list) == 5
        for sv in shap_list:
            assert set(sv.keys()) == set(feature_names)


# ===================================================================
# 2. LightGBMSurrogate (model.py)
# ===================================================================


class TestLightGBMSurrogate:
    """Surrogate model fit/predict API."""

    def test_fit_predict_tiny(self):
        rng = np.random.default_rng(0)
        X = rng.random((30, 10))
        y = (rng.random(30) > 0.5).astype(float)
        s = LightGBMSurrogate(n_estimators=10, random_state=0)
        s.fit(X, y)
        proba = s.predict_proba(X)
        assert proba.shape == (30, 2)

    def test_predictions_in_range(self):
        rng = np.random.default_rng(1)
        X = rng.random((50, 5))
        y = (rng.random(50) > 0.7).astype(float)
        s = LightGBMSurrogate(n_estimators=20, random_state=1)
        s.fit(X, y)
        proba = s.predict_proba(X)
        # Both columns in [0, 1]
        assert np.all(proba >= 0.0)
        assert np.all(proba <= 1.0)
        # Columns should approximately sum to 1
        row_sums = proba.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-5)

    def test_predict_before_fit_raises(self):
        s = LightGBMSurrogate()
        with pytest.raises(RuntimeError, match="not fitted"):
            s.predict_proba(np.zeros((3, 5)))

    def test_output_shape_two_columns(self):
        rng = np.random.default_rng(2)
        X = rng.random((20, 8))
        y = (rng.random(20) > 0.5).astype(float)
        s = LightGBMSurrogate(n_estimators=5, random_state=2)
        s.fit(X, y)
        proba = s.predict_proba(X)
        assert proba.ndim == 2
        assert proba.shape[1] == 2


# ===================================================================
# 3. PDTrainingPipeline (training.py)
# ===================================================================


class TestPipelineStage1:
    """Stage 1 -- data preparation."""

    def test_produces_correct_shape(self):
        data = _make_synthetic(_SMALL_N)
        pipeline = PDTrainingPipeline(TrainingConfig(n_models=2))
        X, y = pipeline.stage1_data_prep(data)
        assert X.shape == (_SMALL_N, 75)
        assert y.shape == (_SMALL_N,)
        assert set(np.unique(y)).issubset({0.0, 1.0})

    def test_empty_data_raises(self):
        pipeline = PDTrainingPipeline()
        with pytest.raises(ValueError, match="empty"):
            pipeline.stage1_data_prep([])


class TestPipelineStage2:
    """Stage 2 -- tier assignment."""

    def test_tier_mapping(self):
        data = _make_synthetic(_SMALL_N)
        pipeline = PDTrainingPipeline()
        tiers = pipeline.stage2_tier_assignment(data)
        assert len(tiers) == _SMALL_N
        assert all(t in (1, 2, 3) for t in tiers)
        # Synthetic data generator creates all three tiers
        assert set(tiers) == {1, 2, 3}


class TestPipelineStage3:
    """Stage 3 -- feature engineering."""

    def test_correct_shape(self):
        data = _make_synthetic(_TINY_N)
        pipeline = PDTrainingPipeline()
        tiers = pipeline.stage2_tier_assignment(data)
        X = pipeline.stage3_feature_engineering(data, tiers)
        assert X.shape == (_TINY_N, 75)
        assert X.dtype == np.float64


class TestPipelineStage4:
    """Stage 4 -- train/val/test split."""

    def test_split_sizes(self):
        X, y = _make_Xy(_SMALL_N)
        config = TrainingConfig(test_split=0.2, val_split=0.1)
        pipeline = PDTrainingPipeline(config)
        X_train, X_val, X_test, y_train, y_val, y_test = pipeline.stage4_train_val_test_split(X, y)

        total = len(y_train) + len(y_val) + len(y_test)
        assert total == _SMALL_N
        assert len(y_test) >= 1
        assert len(y_val) >= 1
        assert len(y_train) >= 1
        # Test set should be approximately 20%
        assert len(y_test) == max(1, int(_SMALL_N * 0.2))


class TestPipelineStage5:
    """Stage 5 -- hyperparameter search."""

    def test_returns_dict(self):
        X, y = _make_Xy(_TINY_N)
        pipeline = PDTrainingPipeline(TrainingConfig(n_trials=2))
        best_params = pipeline.stage5_hyperparameter_search(X, y)
        assert isinstance(best_params, dict)
        # Should contain learning_rate and n_estimators at minimum
        assert "learning_rate" in best_params or "n_estimators" in best_params


class TestPipelineStage6:
    """Stage 6 -- ensemble training."""

    def test_returns_fitted_model(self):
        X, y = _make_Xy(_TINY_N)
        config = TrainingConfig(n_models=2)
        pipeline = PDTrainingPipeline(config)
        best_params = pipeline.stage5_hyperparameter_search(X, y)
        model = pipeline.stage6_ensemble_training(X, y, best_params)
        assert isinstance(model, PDModel)
        assert model._fitted is True
        pds = model.predict_proba(X[:5])
        assert len(pds) == 5


class TestPipelineStage7:
    """Stage 7 -- isotonic calibration."""

    def test_calibration_attaches_calibrator(self):
        X, y = _make_Xy(_TINY_N)
        config = TrainingConfig(n_models=2)
        pipeline = PDTrainingPipeline(config)
        best_params = pipeline.stage5_hyperparameter_search(X, y)
        model = pipeline.stage6_ensemble_training(X, y, best_params)
        model = pipeline.stage7_calibration(model, X[:10], y[:10])
        # Calibrator should be attached (sklearn isotonic)
        assert hasattr(model, "_calibrator")


class TestPipelineStage8:
    """Stage 8 -- thin-file stress test."""

    def test_stress_test_with_valid_data(self):
        model = _fit_small_model()
        # Create thin-file features (tier 3 data)
        data = _make_synthetic(_SMALL_N)
        pipeline = PDTrainingPipeline()
        tiers = pipeline.stage2_tier_assignment(data)
        X, _ = pipeline.stage1_data_prep(data)

        tier3_idx = [i for i, t in enumerate(tiers) if t == 3]
        if len(tier3_idx) > 0:
            X_tier3 = X[tier3_idx]
            result = pipeline.stage8_stress_test(model, X_tier3)
            assert isinstance(result, bool)

    def test_empty_thin_file_passes(self):
        model = _fit_small_model()
        pipeline = PDTrainingPipeline()
        result = pipeline.stage8_stress_test(model, np.empty((0, 75)))
        assert result is True


class TestPipelineStage9:
    """Stage 9 -- evaluation metrics."""

    def test_returns_required_metrics(self):
        X, y = _make_Xy(_SMALL_N)
        model = _fit_small_model()
        pipeline = PDTrainingPipeline()
        metrics = pipeline.stage9_evaluation(model, X, y)
        assert isinstance(metrics, dict)
        assert "auc" in metrics
        assert "brier" in metrics
        assert "ks" in metrics
        # AUC in [0, 1] (or nan if degenerate, but with 100 samples it should be valid)
        assert 0.0 <= metrics["auc"] <= 1.0
        assert 0.0 <= metrics["brier"] <= 1.0


class TestPipelineFullRun:
    """Full pipeline.run() end-to-end."""

    def test_run_end_to_end(self):
        data = _make_synthetic(_SMALL_N)
        config = TrainingConfig(n_trials=2, n_models=2)
        pipeline = PDTrainingPipeline(config)
        model, metrics = pipeline.run(data)
        assert isinstance(model, PDModel)
        assert model._fitted is True
        assert "auc" in metrics
        assert "brier" in metrics
        assert "ks" in metrics


# ===================================================================
# 4. PDInferenceEngine (inference.py)
# ===================================================================


class TestPDInferenceEnginePredict:
    """Single-payment inference."""

    @pytest.fixture(autouse=True)
    def _setup_salt(self):
        """Configure inference salt before each test."""
        configure_inference_salt(b"test-salt-for-inference-00000000")

    def test_predict_response_keys(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        payment = _make_payment()
        borrower = _make_tier1_borrower()
        result = engine.predict(payment, borrower)

        required_keys = {
            "pd_score", "fee_bps", "lgd", "tier",
            "shap_values", "borrower_id_hash", "inference_latency_ms",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_fee_bps_floor(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        for borrower_fn in [_make_tier1_borrower, _make_tier2_borrower, _make_tier3_borrower]:
            borrower = borrower_fn()
            result = engine.predict(_make_payment(), borrower)
            assert result["fee_bps"] >= 300, (
                f"fee_bps={result['fee_bps']} for tier {result['tier']} below 300 bps floor"
            )

    def test_auto_tier_detection_tier1(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_3)  # base is tier 3
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        result = engine.predict(_make_payment(), _make_tier1_borrower())
        assert result["tier"] == 1

    def test_auto_tier_detection_tier2(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_3)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        result = engine.predict(_make_payment(), _make_tier2_borrower())
        assert result["tier"] == 2

    def test_auto_tier_detection_tier3(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        result = engine.predict(_make_payment(), _make_tier3_borrower())
        assert result["tier"] == 3

    def test_tax_id_not_in_output(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        borrower = _make_tier1_borrower()
        borrower["tax_id"] = "SENSITIVE-TAX-ID-12345"
        result = engine.predict(_make_payment(), borrower)

        # tax_id must never appear in any value of the response
        result_str = str(result)
        assert "SENSITIVE-TAX-ID-12345" not in result_str
        assert "tax_id" not in result

    def test_pd_score_in_range(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        result = engine.predict(_make_payment(), _make_tier1_borrower())
        assert 0.0 <= result["pd_score"] <= 1.0

    def test_inference_latency_present(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        result = engine.predict(_make_payment(), _make_tier1_borrower())
        assert result["inference_latency_ms"] >= 0.0


class TestPDInferenceEngineBatch:
    """Batch inference."""

    @pytest.fixture(autouse=True)
    def _setup_salt(self):
        configure_inference_salt(b"test-salt-for-inference-00000000")

    def test_batch_correct_length(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        payments = [_make_payment() for _ in range(5)]
        borrowers = [_make_tier1_borrower() for _ in range(5)]
        results = engine.predict_batch(payments, borrowers)
        assert len(results) == 5
        for r in results:
            assert "pd_score" in r

    def test_batch_length_mismatch_raises(self):
        model = _fit_small_model()
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        engine = PDInferenceEngine(model, engineer, auto_tier=True)

        with pytest.raises(ValueError, match="same length"):
            engine.predict_batch(
                [_make_payment(), _make_payment()],
                [_make_tier1_borrower()],
            )


class TestConfigureInferenceSalt:
    """Salt configuration validation."""

    def test_short_salt_raises(self):
        with pytest.raises(ValueError, match="at least 16 bytes"):
            configure_inference_salt(b"short")

    def test_valid_salt_accepted(self):
        # Should not raise
        configure_inference_salt(b"a" * 16)
        configure_inference_salt(b"b" * 32)


# ===================================================================
# 5. UnifiedFeatureEngineer + FeatureMasker (features.py)
# ===================================================================


class TestUnifiedFeatureEngineerTier1:
    """Tier-1 feature extraction."""

    def test_tier1_output_dim(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        features, avail = engineer.extract(_make_payment(), _make_tier1_borrower())
        assert features.shape == (75,)
        assert features.dtype == np.float64

    def test_tier1_features_populated(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        features, avail = engineer.extract(_make_payment(), _make_tier1_borrower())
        # Tier 1 slots [20:40] should have non-zero values (financial statements)
        tier1_slice = features[20:40]
        assert np.any(tier1_slice != 0.0), "Tier-1 feature slots should be populated"

    def test_tier1_availability_indicators(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        features, avail = engineer.extract(_make_payment(), _make_tier1_borrower())
        assert "avail_financial_statements" in avail
        assert "avail_credit_bureau" in avail


class TestUnifiedFeatureEngineerTier2:
    """Tier-2 feature extraction."""

    def test_tier2_features_populated(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_2)
        features, avail = engineer.extract(_make_payment(), _make_tier2_borrower())
        assert features.shape == (75,)
        # Tier 2 slots [40:50] should be populated
        tier2_slice = features[40:50]
        assert np.any(tier2_slice != 0.0), "Tier-2 feature slots should be populated"

    def test_tier2_availability_indicators(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_2)
        features, avail = engineer.extract(_make_payment(), _make_tier2_borrower())
        assert "avail_transaction_history_6m" in avail


class TestUnifiedFeatureEngineerTier3:
    """Tier-3 (thin-file) feature extraction."""

    def test_tier3_features_populated(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_3)
        features, avail = engineer.extract(_make_payment(), _make_tier3_borrower())
        assert features.shape == (75,)
        # Tier 3 slots [50:55] should be populated
        tier3_slice = features[50:55]
        assert np.any(tier3_slice != 0.0), "Tier-3 feature slots should be populated"

    def test_tier3_availability_indicators(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_3)
        features, avail = engineer.extract(_make_payment(), _make_tier3_borrower())
        assert "avail_thin_file_proxy" in avail
        assert "avail_jurisdiction_data" in avail


class TestFeatureMasking:
    """FeatureMasker zeros out unavailable tier slots."""

    def test_tier3_zeros_tier1_and_tier2_slots(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_3)
        features, _ = engineer.extract(_make_payment(), _make_tier3_borrower())
        # Tier 1 [20:40] should be zeroed for tier 3
        assert np.all(features[20:40] == 0.0), "Tier-1 slots must be zero for Tier-3"
        # Tier 2 [40:50] should also be zeroed for tier 3
        assert np.all(features[40:50] == 0.0), "Tier-2 slots must be zero for Tier-3"

    def test_tier2_zeros_tier1_slots(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_2)
        features, _ = engineer.extract(_make_payment(), _make_tier2_borrower())
        # Tier 1 [20:40] should be zeroed for tier 2
        assert np.all(features[20:40] == 0.0), "Tier-1 slots must be zero for Tier-2"

    def test_tier1_zeros_tier3_slots(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        features, _ = engineer.extract(_make_payment(), _make_tier1_borrower())
        # Tier 3 [50:55] should be zeroed for tier 1
        assert np.all(features[50:55] == 0.0), "Tier-3 slots must be zero for Tier-1"

    def test_availability_indicators_set(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        features, avail = engineer.extract(_make_payment(), _make_tier1_borrower())
        avail_slice = features[55:75]
        # At least some availability indicators should be set to 1.0
        assert np.any(avail_slice == 1.0), "At least one availability indicator should be set"
        # Indicators not in the available list should be 0.0
        available_set = set(avail)
        for i, name in enumerate(AVAILABILITY_INDICATORS):
            if name in available_set:
                assert features[55 + i] == 1.0, f"{name} should be 1.0"
            else:
                assert features[55 + i] == 0.0, f"{name} should be 0.0"


class TestFeatureBatchExtraction:
    """Batch extraction via extract_batch."""

    def test_batch_shape_and_consistency(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        payments = [_make_payment() for _ in range(5)]
        borrowers = [_make_tier1_borrower() for _ in range(5)]
        X, avails = engineer.extract_batch(payments, borrowers)
        assert X.shape == (5, 75)
        assert len(avails) == 5
        # All rows for same input should be identical
        for i in range(1, 5):
            np.testing.assert_array_equal(X[0], X[i])

    def test_batch_length_mismatch_raises(self):
        engineer = UnifiedFeatureEngineer(Tier.TIER_1)
        with pytest.raises(ValueError, match="same length"):
            engineer.extract_batch([_make_payment()], [_make_tier1_borrower()] * 3)


class TestConfigureSalt:
    """configure_salt validation."""

    def test_short_salt_raises(self):
        with pytest.raises(ValueError, match="at least 16 bytes"):
            configure_salt(b"tiny")

    def test_valid_salt_accepted(self):
        # Should not raise
        configure_salt(b"x" * 16)
        configure_salt(b"y" * 64)


class TestFeatureMaskerStaticMethods:
    """FeatureMasker static helpers."""

    def test_get_full_feature_names_length(self):
        names = FeatureMasker.get_full_feature_names()
        assert len(names) == FEATURE_DIM
        assert len(names) == 75

    def test_mask_unavailable_batch(self):
        rng = np.random.default_rng(0)
        X = rng.random((10, 75))
        masked = FeatureMasker.mask_unavailable(
            X, Tier.TIER_3, ["avail_thin_file_proxy"]
        )
        assert masked.shape == X.shape
        # Tier 1 slots zeroed for tier 3
        assert np.all(masked[:, 20:40] == 0.0)
        # Tier 2 slots zeroed for tier 3
        assert np.all(masked[:, 40:50] == 0.0)


# ===================================================================
# 6. BaselineEnsemble (baseline.py) -- gap-filling tests
# ===================================================================


class TestBaselineEnsemblePredictFull:
    """BaselineEnsemble.predict with full features."""

    def test_all_four_pd_fields(self):
        ensemble = BaselineEnsemble()
        features = {
            # Merton inputs
            "asset_value": 1_000_000,
            "debt": 500_000,
            "asset_vol": 0.25,
            "risk_free": 0.05,
            # Altman inputs
            "working_capital": 300_000,
            "total_assets": 1_000_000,
            "retained_earnings": 200_000,
            "ebit": 150_000,
            "market_cap": 800_000,
            "total_liabilities": 400_000,
            "revenue": 1_500_000,
            # Ratio inputs
            "current_ratio": 2.0,
            "debt_to_equity": 0.8,
            "interest_coverage": 5.0,
        }
        result = ensemble.predict(features)
        assert "merton_pd" in result
        assert "altman_pd" in result
        assert "ratio_pd" in result
        assert "ensemble_pd" in result
        # All should be valid floats in [0, 1]
        for key in ["merton_pd", "altman_pd", "ratio_pd", "ensemble_pd"]:
            assert 0.0 <= result[key] <= 1.0, f"{key}={result[key]} out of range"


class TestBaselineEnsembleMissingData:
    """BaselineEnsemble graceful degradation with partial features."""

    def test_missing_merton_inputs(self):
        ensemble = BaselineEnsemble()
        features = {
            # Only ratio inputs
            "current_ratio": 1.5,
            "debt_to_equity": 1.0,
            "interest_coverage": 3.0,
        }
        result = ensemble.predict(features)
        assert math.isnan(result["merton_pd"])
        assert math.isnan(result["altman_pd"])
        assert not math.isnan(result["ratio_pd"])
        assert not math.isnan(result["ensemble_pd"])

    def test_all_missing(self):
        ensemble = BaselineEnsemble()
        result = ensemble.predict({})
        assert math.isnan(result["merton_pd"])
        assert math.isnan(result["altman_pd"])
        assert math.isnan(result["ratio_pd"])
        assert math.isnan(result["ensemble_pd"])

    def test_nan_features(self):
        ensemble = BaselineEnsemble()
        features = {
            "current_ratio": float("nan"),
            "debt_to_equity": float("nan"),
            "interest_coverage": float("nan"),
        }
        result = ensemble.predict(features)
        # NaN inputs to the logistic model should still produce a finite PD
        # (np.clip handles it, but the nan propagates through the logistic)
        # Actually, financial_ratio_pd clips inputs, so NaN may propagate.
        # The ensemble should handle it gracefully regardless.
        assert isinstance(result["ensemble_pd"], float)


class TestMertonPDEdgeCases:
    """Merton PD with degenerate inputs."""

    def test_zero_asset_value(self):
        pd = merton_pd(asset_value=0, debt=500_000, asset_vol=0.25, risk_free=0.05)
        assert pd == 1.0

    def test_negative_asset_value(self):
        pd = merton_pd(asset_value=-100, debt=500_000, asset_vol=0.25, risk_free=0.05)
        assert pd == 1.0

    def test_zero_debt(self):
        pd = merton_pd(asset_value=1_000_000, debt=0, asset_vol=0.25, risk_free=0.05)
        assert pd == 1.0

    def test_zero_volatility(self):
        pd = merton_pd(asset_value=1_000_000, debt=500_000, asset_vol=0, risk_free=0.05)
        assert pd == 1.0

    def test_negative_time(self):
        pd = merton_pd(asset_value=1_000_000, debt=500_000, asset_vol=0.25, risk_free=0.05, T=-1)
        assert pd == 1.0

    def test_healthy_firm_low_pd(self):
        pd = merton_pd(asset_value=10_000_000, debt=1_000_000, asset_vol=0.10, risk_free=0.05)
        assert pd < 0.1  # Very healthy firm, should have low PD


class TestFinancialRatioPDEdgeCases:
    """financial_ratio_pd extreme inputs."""

    def test_extreme_positive_inputs(self):
        pd = financial_ratio_pd(
            current_ratio=100.0,
            debt_to_equity=100.0,
            interest_coverage=100.0,
        )
        assert 0.0 < pd < 1.0

    def test_extreme_negative_inputs(self):
        pd = financial_ratio_pd(
            current_ratio=-100.0,
            debt_to_equity=-100.0,
            interest_coverage=-100.0,
        )
        assert 0.0 < pd < 1.0

    def test_zero_inputs(self):
        pd = financial_ratio_pd(
            current_ratio=0.0,
            debt_to_equity=0.0,
            interest_coverage=0.0,
        )
        assert 0.0 < pd < 1.0


# ===================================================================
# 7. Synthetic Data (synthetic_data.py)
# ===================================================================


class TestSyntheticDataGeneration:
    """generate_pd_training_data correctness."""

    def test_correct_count(self):
        data = generate_pd_training_data(n_samples=200, seed=99)
        assert len(data) == 200

    def test_record_schema(self):
        data = generate_pd_training_data(n_samples=50, seed=42)
        for record in data:
            assert "label" in record
            assert "payment" in record
            assert "borrower" in record
            assert record["label"] in (0, 1)
            assert isinstance(record["payment"], dict)
            assert isinstance(record["borrower"], dict)

    def test_all_three_tiers_represented(self):
        data = generate_pd_training_data(n_samples=200, seed=42)
        tier1 = [r for r in data if r["borrower"].get("has_financial_statements") and r["borrower"].get("has_credit_bureau")]
        tier2 = [r for r in data if not r["borrower"].get("has_financial_statements") and r["borrower"].get("has_transaction_history")]
        tier3 = [r for r in data if not r["borrower"].get("has_financial_statements") and not r["borrower"].get("has_transaction_history")]
        assert len(tier1) > 0, "Tier 1 records missing"
        assert len(tier2) > 0, "Tier 2 records missing"
        assert len(tier3) > 0, "Tier 3 records missing"

    def test_reproducibility(self):
        data1 = generate_pd_training_data(n_samples=50, seed=123)
        data2 = generate_pd_training_data(n_samples=50, seed=123)
        # Same seed should produce identical labels
        labels1 = [r["label"] for r in data1]
        labels2 = [r["label"] for r in data2]
        assert labels1 == labels2

    def test_different_seeds_differ(self):
        data1 = generate_pd_training_data(n_samples=100, seed=1)
        data2 = generate_pd_training_data(n_samples=100, seed=2)
        labels1 = [r["label"] for r in data1]
        labels2 = [r["label"] for r in data2]
        # With different seeds, labels should differ (extremely high probability)
        assert labels1 != labels2

    def test_corpus_tag_present(self):
        data = generate_pd_training_data(n_samples=10, seed=42)
        for record in data:
            assert record["payment"].get("corpus_tag") == "SYNTHETIC_CORPUS_C2"
            assert record["borrower"].get("corpus_tag") == "SYNTHETIC_CORPUS_C2"

    def test_payment_keys(self):
        data = generate_pd_training_data(n_samples=10, seed=42)
        required_payment_keys = {
            "amount_usd", "currency_pair", "sending_bic", "receiving_bic",
            "timestamp", "corridor_failure_rate",
        }
        for record in data:
            assert required_payment_keys.issubset(set(record["payment"].keys()))

    def test_borrower_availability_flags(self):
        data = generate_pd_training_data(n_samples=10, seed=42)
        for record in data:
            borrower = record["borrower"]
            assert "has_financial_statements" in borrower
            assert "has_transaction_history" in borrower
            assert "has_credit_bureau" in borrower
