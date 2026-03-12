"""
test_simulation_script.py — Regression tests for lip/scripts/simulate_pipeline.py

Calls the simulation script via subprocess (N=500, seed=42) to keep each test
fast (<10s) while still exercising the full pipeline end-to-end.

Tests
-----
1. test_simulation_runs_cleanly       — exit code 0, all 4 section headers present
2. test_fee_floor_never_violated      — min bps in distribution ≥ 300
3. test_royalty_math                  — BPI royalty ≈ 15% of total fee (±1%)
4. test_integrity_checks_all_pass     — all 4 ✅ markers present in output
"""

from __future__ import annotations

import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent  # lip/tests/ → lip/ → PRKT2026/
_SCRIPT = _REPO_ROOT / "lip" / "scripts" / "simulate_pipeline.py"
_N = 500
_SEED = 42


def _run() -> subprocess.CompletedProcess:
    """Run the simulation with N=500, seed=42 and capture output."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--n-payments", str(_N), "--seed", str(_SEED)],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(_REPO_ROOT)},
        cwd=str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimulationScript:
    """Regression suite for the simulate_pipeline CLI script."""

    def test_simulation_runs_cleanly(self) -> None:
        """Script exits 0 and all four report sections are present in stdout."""
        result = _run()
        assert result.returncode == 0, (
            f"Script exited {result.returncode}.\n"
            f"stderr:\n{result.stderr}\n"
            f"stdout:\n{result.stdout}"
        )
        for header in ("VOLUME", "FEE REVENUE", "FEE DISTRIBUTION", "LATENCY"):
            assert header in result.stdout, (
                f"Section '{header}' missing from output.\n{result.stdout}"
            )

    def test_fee_floor_never_violated(self) -> None:
        """Minimum fee in the distribution must be ≥ 300 bps (spec floor)."""
        result = _run()
        assert result.returncode == 0

        # Match "Min:   NNN" in the FEE DISTRIBUTION section
        m = re.search(r"Min:\s+(\d+)", result.stdout)
        if m is None:
            # No funded loans in this run — floor trivially satisfied
            return
        min_bps = int(m.group(1))
        assert min_bps >= 300, (
            f"Fee floor violated: min fee_bps = {min_bps} < 300.\n{result.stdout}"
        )

    def test_royalty_math(self) -> None:
        """BPI royalty must be within 1% of 15% of total fee revenue."""
        result = _run()
        assert result.returncode == 0

        fee_m = re.search(r"Total fee USD:\s+\$([0-9,]+\.\d{2})", result.stdout)
        roy_m = re.search(r"BPI royalty \(15%\):\s+\$([0-9,]+\.\d{2})", result.stdout)

        if fee_m is None or roy_m is None:
            # No funded loans — royalty math trivially satisfied
            return

        total_fee = Decimal(fee_m.group(1).replace(",", ""))
        bpi_royalty = Decimal(roy_m.group(1).replace(",", ""))

        if total_fee == Decimal("0"):
            return

        ratio = float(bpi_royalty / total_fee)
        assert abs(ratio - 0.15) < 0.01, (
            f"Royalty ratio {ratio:.4f} deviates from 0.15 by more than 1%.\n"
            f"total_fee={total_fee}, bpi_royalty={bpi_royalty}"
        )

    def test_integrity_checks_all_pass(self) -> None:
        """All four INTEGRITY CHECKS lines must show ✅ in the output."""
        result = _run()
        assert result.returncode == 0

        checks = [
            "Fee floor (≥300 bps)",
            "Royalty (15% of fee)",
            "Kill switch fail-safe",
            "UETR present all loans",
        ]
        for check in checks:
            pattern = re.escape(check) + r".*✅"
            assert re.search(pattern, result.stdout), (
                f"Integrity check not passing: '{check}'\n{result.stdout}"
            )
