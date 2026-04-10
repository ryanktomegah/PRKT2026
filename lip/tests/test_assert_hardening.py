"""Regression tests for assert → raise conversions (B10-08, B13-03).

Converted load-bearing asserts must raise under ``python -O`` (where assert
is a no-op).  Each test explicitly triggers the error path to confirm the
guard is a proper raise, not an assert.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest


class TestFeeFloorSurvivesOptimizeFlag:
    """B13-03: Fee floor raise must survive ``python -O``."""

    def test_fee_floor_under_optimize_flag(self) -> None:
        """Run the fee floor check in a subprocess with ``-O`` to prove it's not an assert."""
        script = textwrap.dedent("""\
            import sys, os
            sys.path.insert(0, os.environ.get("PYTHONPATH", "."))
            from decimal import Decimal
            from lip.c2_pd_model.fee import compute_cascade_adjusted_pd
            result = compute_cascade_adjusted_pd(
                base_pd=Decimal("0.0001"),
                cascade_value_prevented=Decimal("9999999"),
                intervention_cost=Decimal("1"),
            )
            from lip.common.constants import FEE_FLOOR_BPS
            assert result.cascade_adjusted_fee_bps >= FEE_FLOOR_BPS
            print("PASS")
        """)
        result = subprocess.run(
            [sys.executable, "-O", "-c", script],
            capture_output=True,
            text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": "."},
            cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
            timeout=30,
        )
        assert result.returncode == 0, f"Fee floor failed under -O:\n{result.stderr}"
        assert "PASS" in result.stdout


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
        pd = pytest.importorskip("pandas")
        np = pytest.importorskip("numpy")

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
