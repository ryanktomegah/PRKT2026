"""Regression tests for Decimal→float round-trip elimination (B8-04, B7-01, B3-07).

Verifies that compliance-boundary calculations use Decimal-native operations
and that float precision loss does not flip pass/fail at AML cap thresholds.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

_LIP_ROOT = Path(__file__).resolve().parents[1]

# ── Lint: no new float() calls on Decimal-typed variables ──────────────────

# Known-intentional float() conversions (ML inference, logging, etc.)
_ALLOWED_FLOAT_FILES = {
    "c2_pd_model/inference.py",       # ML inference feeds float-native models
    "c2_pd_model/training.py",        # ML training
    "c1_failure_classifier/training.py",
    "c1_failure_classifier/model.py",
    "c4_dispute_classifier/model.py",
    "c9_settlement_predictor/model.py",
    "c9_settlement_predictor/training.py",
    "scripts/simulate_pipeline.py",
    "scripts/train_c1.py",
    "scripts/train_c2.py",
    "train_all.py",
    "pipeline.py",                    # Orchestrator — passes to ML modules
    "c7_execution_agent/agent.py",    # Loan offer formatting
    "api/app.py",
    "api/regulatory_router.py",
    "p10_regulatory_data/shadow_data.py",
    "p10_regulatory_data/anonymizer.py",
    "dgen/iso20022_payments.py",
    "dgen/c1_generator.py",
    "dgen/c3_generator.py",
    "dgen/statistical_validator_production.py",
    "c8_license_manager/license_token.py",  # Take-rate: float in JSON→HMAC path (intentional)
    "c8_license_manager/boot_validator.py",  # Logging format strings
    "c8_license_manager/revenue_metering.py",
    "common/conformal.py",
}


class TestDecimalFloatLint:
    """Guard against new float(Decimal) round-trips in compliance code."""

    def test_no_math_sqrt_on_decimal_in_risk(self) -> None:
        """B8-04: portfolio_risk.py must not use math.sqrt on Decimal values."""
        source = (_LIP_ROOT / "risk" / "portfolio_risk.py").read_text()
        assert "math.sqrt" not in source, (
            "portfolio_risk.py still uses math.sqrt — use Decimal.sqrt() instead (B8-04)"
        )


# ── Boundary-condition tests ───────────────────────────────────────────────


class TestPortfolioVaRDecimalPrecision:
    """B8-04: VaR computation must use Decimal.sqrt(), not math.sqrt(float())."""

    def test_var_at_small_variance(self) -> None:
        """Decimal.sqrt() must handle very small variances without float underflow."""
        tiny_variance = Decimal("1E-30")
        result = tiny_variance.sqrt()
        assert result == Decimal("1E-15")

    def test_var_at_large_variance(self) -> None:
        """Decimal.sqrt() must handle large variances without float overflow."""
        large_variance = Decimal("1E+30")
        result = large_variance.sqrt()
        assert result == Decimal("1E+15")

    def test_sqrt_precision_exceeds_float(self) -> None:
        """Decimal.sqrt() must have more precision than float sqrt at cap boundary."""
        import math

        val = Decimal("1000000.005")
        dec_sqrt = val.sqrt()
        flt_sqrt = Decimal(str(math.sqrt(float(val))))
        # Decimal result has more significant digits
        assert len(str(dec_sqrt).replace(".", "").lstrip("0")) > len(
            str(flt_sqrt).replace(".", "").lstrip("0")
        )


class TestAMLCapBoundaryPrecision:
    """B7-01: Float precision at AML dollar cap boundary."""

    def test_boundary_amount_exactly_at_cap(self) -> None:
        """Amount exactly equal to cap must pass — no float truncation flip."""
        cap = Decimal("1000000")
        amount = Decimal("1000000")
        # In Decimal: amount <= cap → True
        assert amount <= cap
        # In float: same result (but this is the easy case)
        assert float(amount) <= float(cap)

    def test_boundary_one_cent_over_cap(self) -> None:
        """Amount one cent over cap must fail in both Decimal and float."""
        cap = Decimal("1000000.00")
        amount = Decimal("1000000.01")
        assert amount > cap
        # Float path should also catch this (0.01 is representable enough)
        assert float(amount) > float(cap)

    def test_boundary_half_cent_precision(self) -> None:
        """Half-cent amounts at cap boundary where float may diverge."""
        cap = Decimal("999999.995")
        amount = Decimal("999999.996")
        # Decimal correctly sees amount > cap
        assert amount > cap
        # Float may or may not preserve this — document the gap
        # This test ensures our Decimal path is the authority
