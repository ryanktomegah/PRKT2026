"""
test_conformal.py — Tests for conformal prediction layer.
EU AI Act Art.13 transparency requirement.
"""
from __future__ import annotations

import numpy as np
import pytest


class TestConformalPredictor:
    """Test the split conformal prediction implementation."""

    def _make_predictor(self, coverage=0.90):
        from lip.common.conformal import ConformalPredictor
        return ConformalPredictor(coverage_level=coverage)

    def test_not_calibrated_initially(self):
        cp = self._make_predictor()
        assert not cp.is_calibrated

    def test_calibrate_stores_quantile(self):
        cp = self._make_predictor(coverage=0.90)
        predictions = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        actuals = np.array([0.15, 0.18, 0.35, 0.38, 0.55])
        cp.calibrate(predictions, actuals)
        assert cp.is_calibrated
        assert cp.calibration_size == 5

    def test_predict_interval_returns_correct_structure(self):
        cp = self._make_predictor(coverage=0.90)
        predictions = np.random.default_rng(42).uniform(0, 1, 100)
        actuals = predictions + np.random.default_rng(43).normal(0, 0.05, 100)
        cp.calibrate(predictions, actuals)

        interval = cp.predict_interval(0.5)
        assert interval.lower <= interval.point <= interval.upper
        assert interval.width > 0
        assert interval.coverage_level == 0.90

    def test_higher_coverage_wider_interval(self):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 200)
        actuals = preds + rng.normal(0, 0.05, 200)

        cp90 = self._make_predictor(coverage=0.90)
        cp90.calibrate(preds, actuals)
        interval90 = cp90.predict_interval(0.5)

        cp99 = self._make_predictor(coverage=0.99)
        cp99.calibrate(preds, actuals)
        interval99 = cp99.predict_interval(0.5)

        assert interval99.width >= interval90.width

    def test_batch_prediction(self):
        cp = self._make_predictor(coverage=0.90)
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100)
        actuals = preds + rng.normal(0, 0.05, 100)
        cp.calibrate(preds, actuals)

        batch_preds = np.array([0.1, 0.5, 0.9])
        intervals = cp.predict_intervals_batch(batch_preds)
        assert len(intervals) == 3
        assert all(iv.lower <= iv.point <= iv.upper for iv in intervals)

    def test_coverage_property(self):
        cp = self._make_predictor(coverage=0.95)
        assert cp.coverage_level == 0.95

    def test_raises_if_not_calibrated(self):
        cp = self._make_predictor()
        with pytest.raises(RuntimeError):
            cp.predict_interval(0.5)


class TestUncertaintyFeeAdjustment:
    """Test the fee adjustment based on conformal interval width."""

    def test_zero_width_no_adjustment(self):
        from lip.common.conformal import uncertainty_fee_adjustment
        result = uncertainty_fee_adjustment(0.0, 300)
        assert result == 300

    def test_wider_interval_higher_fee(self):
        from lip.common.conformal import uncertainty_fee_adjustment
        fee_narrow = uncertainty_fee_adjustment(0.1, 300)
        fee_wide = uncertainty_fee_adjustment(0.5, 300)
        assert fee_wide > fee_narrow

    def test_floor_still_applies(self):
        from lip.common.conformal import uncertainty_fee_adjustment
        # Even with zero baseline, floor from constants applies
        result = uncertainty_fee_adjustment(0.1, 300)
        assert result >= 300
