"""
test_settlement_predictor.py — Tests for C9 settlement time prediction.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from lip.c9_settlement_predictor.model import (
    FEATURE_NAMES,
    SettlementPrediction,
    SettlementTimePredictor,
    _encode_features,
)


class TestFeatureEncoding:
    """Test C9 feature encoding."""

    def test_feature_vector_length(self):
        features = _encode_features(
            corridor="USD-EUR",
            rejection_class="CLASS_B",
            amount_usd=1_000_000,
        )
        assert len(features) == len(FEATURE_NAMES)

    def test_rejection_class_one_hot(self):
        features_a = _encode_features(corridor="X", rejection_class="CLASS_A", amount_usd=1e6)
        features_b = _encode_features(corridor="X", rejection_class="CLASS_B", amount_usd=1e6)
        # is_class_a at index 1
        assert features_a[1] == 1.0
        assert features_a[2] == 0.0
        assert features_b[1] == 0.0
        assert features_b[2] == 1.0

    def test_corridor_one_hot(self):
        features = _encode_features(
            corridor="USD-EUR",
            rejection_class="CLASS_A",
            amount_usd=1e6,
        )
        # corridor_usd_eur at index 11
        assert features[11] == 1.0

    def test_timestamp_cyclical_encoding(self):
        ts = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)  # noon Sunday
        features = _encode_features(
            corridor="X", rejection_class="CLASS_A",
            amount_usd=1e6, timestamp=ts,
        )
        # hour_sin, hour_cos at indices 6, 7
        # At noon (12h): sin(2*pi*12/24) = sin(pi) ≈ 0
        assert abs(features[6]) < 0.01  # sin(pi) ≈ 0


class TestSettlementTimePredictor:
    """Test the settlement time predictor."""

    def test_unfitted_uses_heuristic(self):
        predictor = SettlementTimePredictor()
        result = predictor.predict(
            corridor="USD-EUR",
            rejection_class="CLASS_A",
            amount_usd=1_000_000,
        )
        assert isinstance(result, SettlementPrediction)
        assert result.model_type == "fallback"
        assert result.predicted_hours > 0

    def test_class_a_faster_than_class_c(self):
        predictor = SettlementTimePredictor()
        result_a = predictor.predict(corridor="X", rejection_class="CLASS_A", amount_usd=1e6)
        result_c = predictor.predict(corridor="X", rejection_class="CLASS_C", amount_usd=1e6)
        assert result_a.predicted_hours < result_c.predicted_hours

    def test_dynamic_maturity_within_static(self):
        predictor = SettlementTimePredictor()
        result = predictor.predict(
            corridor="USD-EUR",
            rejection_class="CLASS_B",
            amount_usd=1_000_000,
        )
        assert result.dynamic_maturity_hours <= result.static_maturity_hours

    def test_predict_dynamic_maturity_days(self):
        predictor = SettlementTimePredictor()
        days = predictor.predict_dynamic_maturity_days(
            corridor="USD-EUR",
            rejection_class="CLASS_A",
            amount_usd=1_000_000,
        )
        assert days >= 1

    def test_heuristic_fit(self):
        predictor = SettlementTimePredictor()
        X = np.zeros((100, len(FEATURE_NAMES)))
        # 50 class A, 50 class B
        X[:50, 1] = 1.0  # is_class_a
        X[50:, 2] = 1.0  # is_class_b
        durations = np.concatenate([
            np.full(50, 4.0),   # Class A: 4h
            np.full(50, 36.0),  # Class B: 36h
        ])
        events = np.ones(100)
        predictor.fit(X, durations, events)
        assert predictor.is_fitted
        result = predictor.predict(corridor="X", rejection_class="CLASS_A", amount_usd=1e6)
        assert result.predicted_hours == pytest.approx(4.0, abs=1.0)

    def test_safety_margin_applied(self):
        predictor = SettlementTimePredictor(safety_margin=2.0)
        result = predictor.predict(
            corridor="X",
            rejection_class="CLASS_A",
            amount_usd=1_000_000,
        )
        # Dynamic maturity should be at least predicted * 2
        assert result.dynamic_maturity_hours >= result.predicted_hours * 1.5

    def test_min_maturity_enforced(self):
        predictor = SettlementTimePredictor(min_maturity_hours=24.0)
        result = predictor.predict(
            corridor="X",
            rejection_class="CLASS_A",
            amount_usd=1_000_000,
        )
        assert result.dynamic_maturity_hours >= 24.0


class TestSyntheticData:
    """Test synthetic settlement data generation."""

    def test_generates_correct_shape(self):
        from lip.c9_settlement_predictor.synthetic_data import generate_settlement_data
        X, durations, events = generate_settlement_data(n_samples=100, seed=42)
        assert X.shape == (100, len(FEATURE_NAMES))
        assert durations.shape == (100,)
        assert events.shape == (100,)

    def test_durations_positive(self):
        from lip.c9_settlement_predictor.synthetic_data import generate_settlement_data
        _, durations, _ = generate_settlement_data(n_samples=100, seed=42)
        assert (durations > 0).all()

    def test_events_binary(self):
        from lip.c9_settlement_predictor.synthetic_data import generate_settlement_data
        _, _, events = generate_settlement_data(n_samples=100, seed=42)
        assert set(np.unique(events)).issubset({0.0, 1.0})

    def test_censoring_rate(self):
        from lip.c9_settlement_predictor.synthetic_data import generate_settlement_data
        _, _, events = generate_settlement_data(n_samples=10000, seed=42, censoring_rate=0.10)
        actual_rate = 1.0 - events.mean()
        assert abs(actual_rate - 0.10) < 0.03  # within 3% of target
