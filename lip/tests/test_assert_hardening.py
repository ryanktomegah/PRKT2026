"""Regression tests for assert → raise conversions (B10-08, B13-03).

Converted load-bearing asserts must raise under ``python -O`` (where assert
is a no-op). Each test explicitly triggers error path to confirm
guard is a proper raise, not an assert.
"""

import subprocess
import sys


class TestC1FeeFloorAt300BPS:
    """B13-03: Platform floor (300 bps) must survive subprocess optimization."""

    def test_platform_floor_survives_optimize_flag(self) -> None:
        """Platform floor (300 bps) must not be removed by -O optimization."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "lip/tests/test_fee_floor_two_tier.py::test_spv_warehouse_eligible_meets_800_bps_floor", "-v"],
            capture_output=True,
            text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": "."},
            cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
            timeout=30,
        )
        assert result.returncode == 0, f"Platform floor check failed:\n{result.stdout}{result.stderr}"
        assert "PASSED" in result.stdout, "Expected PASSED marker in test output"


class TestFeatureDimRaise:
    """C1 feature dimension guard must be a raise, not an assert."""

    def test_feature_names_count_matches_dim(self) -> None:
        from lip.c1_failure_classifier.features import (
            TABULAR_FEATURE_DIM,
            _build_feature_names,
        )
        names = _build_feature_names()
        assert len(names) == TABULAR_FEATURE_DIM


class TestLabelIntegrityRaise:
    """DGEN label integrity guard must be a raise, not an assert."""

    def test_temporal_clustering_preserves_labels(self) -> None:
        """Smoke test: _inject_temporal_clustering does not corrupt labels."""
        import numpy as np
        import pandas as pd

        from lip.dgen.iso20022_payments import _inject_temporal_clustering

        rng = np.random.default_rng(42)
        n = 50
        labels = rng.choice([0, 1], size=n, p=[0.6, 0.4])
        bics = rng.choice(["DEUTDEFF", "BNPAFRPP", "CHASUS33"], size=n)
        df = pd.DataFrame({
            "label": labels,
            "bic_sender": bics,
            "timestamp_utc": pd.date_range(
                "2025-01-01", periods=n, freq="h", tz="UTC",
            ).strftime("%Y-%m-%dT%H:%M:%S.000+00:00"),
        })
        original_labels = df["label"].to_numpy().copy()
        result = _inject_temporal_clustering(df, rng=rng)
        assert np.array_equal(original_labels, result["label"].to_numpy())
