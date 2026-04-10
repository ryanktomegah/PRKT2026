"""
test_c1_oot_fallback.py — Tests for C1 OOT split random fallback warning (B10-04).

Verifies that the C1 training pipeline warns when falling back to random
split, and raises in strict mode.
"""
from __future__ import annotations

import logging

import numpy as np
import pytest

from lip.c1_failure_classifier.training import TrainingConfig, TrainingPipeline


def _make_data(n: int = 200):
    """Create minimal feature matrix and labels for split testing."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((n, 10))
    y = rng.integers(0, 2, size=n).astype(np.float32)
    return X, y


class TestOOTFallbackWarning:
    def test_random_fallback_warns(self, caplog):
        """When timestamps are None, stage4 must log a WARNING."""
        config = TrainingConfig(val_split=0.2)
        pipeline = TrainingPipeline(config)
        X, y = _make_data()
        with caplog.at_level(logging.WARNING):
            pipeline.stage4_train_val_split(X, y, timestamps=None)
        assert any("RANDOM split" in r.message for r in caplog.records), (
            "No WARNING about random fallback logged"
        )

    def test_chronological_split_no_warning(self, caplog):
        """When timestamps are provided, no random-fallback warning."""
        config = TrainingConfig(val_split=0.2)
        pipeline = TrainingPipeline(config)
        X, y = _make_data()
        timestamps = np.arange(len(y), dtype=np.float64)
        with caplog.at_level(logging.WARNING):
            pipeline.stage4_train_val_split(X, y, timestamps=timestamps)
        assert not any("RANDOM split" in r.message for r in caplog.records)

    def test_strict_oot_raises_without_timestamps(self):
        """strict_oot=True must raise ValueError when timestamps are missing."""
        config = TrainingConfig(val_split=0.2, strict_oot=True)
        pipeline = TrainingPipeline(config)
        X, y = _make_data()
        with pytest.raises(ValueError, match="strict_oot"):
            pipeline.stage4_train_val_split(X, y, timestamps=None)

    def test_strict_oot_ok_with_timestamps(self):
        """strict_oot=True must not raise when timestamps are provided."""
        config = TrainingConfig(val_split=0.2, strict_oot=True)
        pipeline = TrainingPipeline(config)
        X, y = _make_data()
        timestamps = np.arange(len(y), dtype=np.float64)
        # Should not raise
        result = pipeline.stage4_train_val_split(X, y, timestamps=timestamps)
        assert len(result) >= 4
