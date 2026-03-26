"""
test_portfolio_risk.py — Tests for portfolio risk aggregation engine.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lip.c3_repayment_engine.repayment_loop import ActiveLoan


class TestConcentration:
    """Test HHI and concentration limit checks."""

    def test_hhi_single_name(self):
        from lip.risk.concentration import compute_hhi
        # Single name = 100% concentration = HHI of 10000
        result = compute_hhi({"A": Decimal("1000000")})
        assert result == Decimal("10000")

    def test_hhi_two_equal(self):
        from lip.risk.concentration import compute_hhi
        result = compute_hhi({"A": Decimal("500000"), "B": Decimal("500000")})
        assert result == Decimal("5000")

    def test_hhi_empty(self):
        from lip.risk.concentration import compute_hhi
        result = compute_hhi({})
        assert result == Decimal("0")

    def test_concentration_within_limits(self):
        from lip.risk.concentration import check_concentration_limits
        exposures = {
            "A": Decimal("200000"),
            "B": Decimal("200000"),
            "C": Decimal("200000"),
            "D": Decimal("200000"),
            "E": Decimal("200000"),
        }
        result = check_concentration_limits(exposures)
        assert result.is_within_limits
        assert len(result.breaches) == 0

    def test_concentration_single_name_breach(self):
        from lip.risk.concentration import check_concentration_limits
        exposures = {
            "A": Decimal("800000"),  # 80% > 25% limit
            "B": Decimal("100000"),
            "C": Decimal("100000"),
        }
        result = check_concentration_limits(exposures)
        assert not result.is_within_limits
        assert any(b.breach_type == "SINGLE_NAME" for b in result.breaches)


class TestPortfolioRiskEngine:
    """Test the PortfolioRiskEngine."""

    def _make_loan(self, loan_id="L1", principal=Decimal("1000000"),
                   fee_bps=300, corridor="USD-EUR", uetr="test-uetr",
                   sending_bic="TESTBIC1", rejection_class="CLASS_B"):
        now = datetime.now(tz=timezone.utc)
        return ActiveLoan(
            loan_id=loan_id,
            uetr=uetr,
            individual_payment_id="pid-1",
            principal=principal,
            fee_bps=fee_bps,
            maturity_date=now + timedelta(days=7),
            rejection_class=rejection_class,
            corridor=corridor,
            funded_at=now,
        )

    def test_empty_portfolio_var(self):
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        engine = PortfolioRiskEngine()
        var = engine.compute_var()
        assert var.var_99 == Decimal("0")
        assert var.position_count == 0

    def test_add_and_remove_position(self):
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        engine = PortfolioRiskEngine()
        loan = self._make_loan()
        engine.add_position(loan, pd=0.05, lgd=0.45)
        assert len(engine.positions) == 1
        engine.remove_position("L1")
        assert len(engine.positions) == 0

    def test_parametric_var_positive(self):
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        engine = PortfolioRiskEngine()
        for i in range(5):
            loan = self._make_loan(
                loan_id=f"L{i}",
                uetr=f"uetr-{i}",
                principal=Decimal("2000000"),
            )
            engine.add_position(loan, pd=0.05, lgd=0.45)
        var = engine.compute_var()
        assert var.var_99 > Decimal("0")
        assert var.expected_loss > Decimal("0")
        assert var.position_count == 5

    def test_corridor_concentration(self):
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        engine = PortfolioRiskEngine()
        # All in same corridor
        for i in range(3):
            loan = self._make_loan(
                loan_id=f"L{i}", uetr=f"uetr-{i}",
                corridor="USD-EUR",
            )
            engine.add_position(loan, pd=0.03, lgd=0.40)
        conc = engine.compute_concentration("corridor")
        assert conc.hhi == Decimal("10000")  # 100% concentration

    def test_risk_summary(self):
        from lip.risk.portfolio_risk import PortfolioRiskEngine
        engine = PortfolioRiskEngine()
        loan = self._make_loan()
        engine.add_position(loan, pd=0.05, lgd=0.45)
        summary = engine.get_risk_summary()
        assert "var" in summary
        assert "corridor_concentration" in summary
        assert "bic_concentration" in summary


class TestMonteCarloVaR:
    """Test Monte Carlo VaR engine."""

    def test_empty_portfolio(self):
        from lip.risk.var_monte_carlo import MonteCarloVaREngine
        engine = MonteCarloVaREngine(num_simulations=100)
        result = engine.compute_var([])
        assert result.var_99 == Decimal("0")

    def test_single_position(self):
        from lip.risk.var_monte_carlo import MCPosition, MonteCarloVaREngine
        engine = MonteCarloVaREngine(num_simulations=1000, seed=42)
        positions = [
            MCPosition(
                loan_id="L1", principal=1_000_000,
                pd=0.10, lgd=0.45, corridor="USD-EUR", rejection_class="CLASS_B",
            ),
        ]
        result = engine.compute_var(positions)
        assert result.var_99 >= Decimal("0")
        assert result.expected_loss >= Decimal("0")

    def test_stress_scenarios(self):
        from lip.risk.var_monte_carlo import STRESS_SCENARIOS, MCPosition, MonteCarloVaREngine
        engine = MonteCarloVaREngine(num_simulations=500, seed=42)
        positions = [
            MCPosition(
                loan_id=f"L{i}", principal=2_000_000,
                pd=0.05, lgd=0.40, corridor="USD-EUR", rejection_class="CLASS_B",
            )
            for i in range(5)
        ]
        results = engine.run_stress_tests(positions, STRESS_SCENARIOS[:2])
        assert "BASELINE" in results
        assert "CORRIDOR_SHOCK" in results

    def test_higher_correlation_higher_var(self):
        from lip.risk.var_monte_carlo import MCPosition, MonteCarloVaREngine
        positions = [
            MCPosition(
                loan_id=f"L{i}", principal=1_000_000,
                pd=0.10, lgd=0.45, corridor="USD-EUR", rejection_class="CLASS_B",
            )
            for i in range(10)
        ]
        low_corr = MonteCarloVaREngine(num_simulations=5000, default_correlation=0.05, seed=42)
        high_corr = MonteCarloVaREngine(num_simulations=5000, default_correlation=0.50, seed=42)
        var_low = low_corr.compute_var(positions)
        var_high = high_corr.compute_var(positions)
        # Higher correlation should generally produce higher tail risk
        assert var_high.var_99 >= var_low.expected_loss


class TestStressTesting:
    """Test stress testing report generation."""

    def test_daily_report_generation(self):
        from lip.risk.stress_testing import generate_daily_var_report
        from lip.risk.var_monte_carlo import MCPosition
        positions = [
            MCPosition(
                loan_id="L1", principal=5_000_000,
                pd=0.05, lgd=0.40, corridor="USD-EUR", rejection_class="CLASS_B",
            ),
        ]
        report = generate_daily_var_report(positions, num_simulations=100)
        assert report.position_count == 1
        assert report.report_date

    def test_csv_export(self):
        from lip.risk.stress_testing import export_var_report_csv, generate_daily_var_report
        from lip.risk.var_monte_carlo import MCPosition
        positions = [
            MCPosition(
                loan_id="L1", principal=5_000_000,
                pd=0.05, lgd=0.40, corridor="USD-EUR", rejection_class="CLASS_B",
            ),
        ]
        report = generate_daily_var_report(positions, num_simulations=100)
        csv_output = export_var_report_csv(report)
        assert "BASELINE" in csv_output
        assert "var_99_usd" in csv_output

    def test_json_export(self):
        import json

        from lip.risk.stress_testing import export_var_report_json, generate_daily_var_report
        from lip.risk.var_monte_carlo import MCPosition
        positions = [
            MCPosition(
                loan_id="L1", principal=5_000_000,
                pd=0.05, lgd=0.40, corridor="USD-EUR", rejection_class="CLASS_B",
            ),
        ]
        report = generate_daily_var_report(positions, num_simulations=100)
        json_output = export_var_report_json(report)
        parsed = json.loads(json_output)
        assert "baseline_var" in parsed
