"""
var_monte_carlo.py — Monte Carlo Value-at-Risk with Gaussian copula.
Upgrade from parametric VaR (portfolio_risk.py) to correlated defaults.

Bank risk committee requirement: parametric VaR is a start; Monte Carlo
with correlated defaults is what Basel IRB expects.

Reference: Li, "On Default Correlation: A Copula Function Approach,"
Journal of Fixed Income, 2000.

Algorithm:
  1. For each simulation (10,000 default):
     a. Draw correlated uniform variables via Gaussian copula
     b. Compare to each position's PD to determine default/no-default
     c. Compute portfolio loss = sum(LGD_i * EAD_i) for defaulted positions
  2. VaR_99 = 99th percentile of the loss distribution
  3. Expected Shortfall (CVaR) = mean of losses exceeding VaR_99
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default simulation parameters
DEFAULT_NUM_SIMULATIONS = 10_000
DEFAULT_CORRELATION = 0.20  # 20% default correlation (conservative estimate)
DEFAULT_CONFIDENCE_LEVELS = (0.95, 0.99, 0.999)


@dataclass(frozen=True)
class MonteCarloVaRResult:
    """Result of a Monte Carlo VaR simulation.

    Attributes:
        var_95: 95th percentile loss.
        var_99: 99th percentile loss.
        var_999: 99.9th percentile loss.
        expected_shortfall_99: Mean loss exceeding VaR_99 (CVaR).
        expected_loss: Mean portfolio loss.
        total_exposure: Total EAD across all positions.
        position_count: Number of positions.
        num_simulations: Number of Monte Carlo runs.
        correlation: Default correlation used.
        computation_time_ms: Wall-clock time in milliseconds.
        loss_distribution_percentiles: P1, P5, P10, ..., P99 of loss distribution.
    """
    var_95: Decimal
    var_99: Decimal
    var_999: Decimal
    expected_shortfall_99: Decimal
    expected_loss: Decimal
    total_exposure: Decimal
    position_count: int
    num_simulations: int
    correlation: float
    computation_time_ms: float
    loss_distribution_percentiles: Dict[str, float] = field(default_factory=dict)


@dataclass
class MCPosition:
    """Position for Monte Carlo simulation."""
    loan_id: str
    principal: float  # EAD in USD
    pd: float         # probability of default [0, 1]
    lgd: float        # loss given default [0, 1]
    corridor: str
    rejection_class: str


@dataclass(frozen=True)
class StressScenario:
    """Defines a stress scenario for stress testing.

    Attributes:
        name: Scenario identifier.
        description: Human-readable description.
        pd_multiplier: Factor applied to all PDs.
        lgd_multiplier: Factor applied to all LGDs.
        correlation_override: Override default correlation.
        corridor_shocks: Per-corridor PD multiplier overrides.
    """
    name: str
    description: str
    pd_multiplier: float = 1.0
    lgd_multiplier: float = 1.0
    correlation_override: Optional[float] = None
    corridor_shocks: Dict[str, float] = field(default_factory=dict)


# Pre-defined stress scenarios
STRESS_SCENARIOS: List[StressScenario] = [
    StressScenario(
        name="BASELINE",
        description="No stress applied — baseline portfolio risk.",
    ),
    StressScenario(
        name="CORRIDOR_SHOCK",
        description="Emerging market corridor PDs triple; G10 unaffected.",
        corridor_shocks={
            "USD-CNY": 3.0, "CNY-USD": 3.0,
            "USD-INR": 3.0, "INR-USD": 3.0,
            "USD-BRL": 3.0, "BRL-USD": 3.0,
            "USD-TRY": 5.0, "TRY-USD": 5.0,
            "USD-ZAR": 3.0, "ZAR-USD": 3.0,
        },
    ),
    StressScenario(
        name="MULTI_NAME_DEFAULT",
        description="All PDs increase 2x, correlation rises to 40%.",
        pd_multiplier=2.0,
        correlation_override=0.40,
    ),
    StressScenario(
        name="SETTLEMENT_EXTENSION",
        description="LGDs increase 50% due to extended settlement times.",
        lgd_multiplier=1.5,
    ),
    StressScenario(
        name="SEVERE_STRESS",
        description="PDs 3x, LGDs 1.5x, correlation 50%. 2008-level scenario.",
        pd_multiplier=3.0,
        lgd_multiplier=1.5,
        correlation_override=0.50,
    ),
]


class MonteCarloVaREngine:
    """Monte Carlo VaR engine with Gaussian copula for correlated defaults.

    Parameters
    ----------
    num_simulations:
        Number of Monte Carlo simulation runs.
    default_correlation:
        Pairwise default correlation (single-factor model).
    seed:
        Random seed for reproducibility.
    """

    def __init__(
        self,
        num_simulations: int = DEFAULT_NUM_SIMULATIONS,
        default_correlation: float = DEFAULT_CORRELATION,
        seed: int = 42,
    ) -> None:
        self._num_sims = num_simulations
        self._correlation = default_correlation
        self._seed = seed

    def compute_var(
        self,
        positions: List[MCPosition],
        scenario: Optional[StressScenario] = None,
    ) -> MonteCarloVaRResult:
        """Run Monte Carlo VaR simulation.

        Parameters
        ----------
        positions:
            Portfolio positions with PD, LGD, and EAD.
        scenario:
            Optional stress scenario to apply.

        Returns
        -------
        MonteCarloVaRResult
        """
        t0 = time.perf_counter()

        if not positions:
            return MonteCarloVaRResult(
                var_95=Decimal("0"), var_99=Decimal("0"), var_999=Decimal("0"),
                expected_shortfall_99=Decimal("0"), expected_loss=Decimal("0"),
                total_exposure=Decimal("0"), position_count=0,
                num_simulations=self._num_sims, correlation=self._correlation,
                computation_time_ms=0.0,
            )

        n = len(positions)
        correlation = self._correlation

        # Apply scenario
        pds = np.array([p.pd for p in positions], dtype=np.float64)
        lgds = np.array([p.lgd for p in positions], dtype=np.float64)
        eads = np.array([p.principal for p in positions], dtype=np.float64)

        if scenario is not None:
            pds = pds * scenario.pd_multiplier
            lgds = lgds * scenario.lgd_multiplier
            if scenario.correlation_override is not None:
                correlation = scenario.correlation_override
            # Apply corridor-specific shocks
            for i, pos in enumerate(positions):
                if pos.corridor in scenario.corridor_shocks:
                    pds[i] *= scenario.corridor_shocks[pos.corridor]

        # Clip PDs to [0, 1]
        pds = np.clip(pds, 0.0, 1.0)
        lgds = np.clip(lgds, 0.0, 1.0)

        total_exposure = float(np.sum(eads))

        # Gaussian copula simulation
        losses = self._simulate_losses(pds, lgds, eads, correlation, n)

        # Compute VaR at multiple confidence levels
        var_95 = float(np.percentile(losses, 95))
        var_99 = float(np.percentile(losses, 99))
        var_999 = float(np.percentile(losses, 99.9))
        expected_loss = float(np.mean(losses))

        # Expected Shortfall (CVaR) at 99%
        tail_mask = losses >= var_99
        if tail_mask.any():
            es_99 = float(np.mean(losses[tail_mask]))
        else:
            es_99 = var_99

        # Percentile distribution for reporting
        percentile_keys = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentiles = {
            f"p{p}": round(float(np.percentile(losses, p)), 2)
            for p in percentile_keys
        }

        computation_ms = (time.perf_counter() - t0) * 1000.0

        return MonteCarloVaRResult(
            var_95=Decimal(str(round(var_95, 2))),
            var_99=Decimal(str(round(var_99, 2))),
            var_999=Decimal(str(round(var_999, 2))),
            expected_shortfall_99=Decimal(str(round(es_99, 2))),
            expected_loss=Decimal(str(round(expected_loss, 2))),
            total_exposure=Decimal(str(round(total_exposure, 2))),
            position_count=n,
            num_simulations=self._num_sims,
            correlation=correlation,
            computation_time_ms=round(computation_ms, 3),
            loss_distribution_percentiles=percentiles,
        )

    def _simulate_losses(
        self,
        pds: np.ndarray,
        lgds: np.ndarray,
        eads: np.ndarray,
        correlation: float,
        n_positions: int,
    ) -> np.ndarray:
        """Simulate portfolio losses using Gaussian copula.

        Single-factor model: each obligor's latent variable is
            Z_i = sqrt(rho) * M + sqrt(1-rho) * epsilon_i
        where M ~ N(0,1) is the systematic factor and epsilon_i ~ N(0,1)
        is the idiosyncratic factor. Default occurs when Phi(Z_i) < PD_i.
        """
        rng = np.random.default_rng(self._seed)

        # Correlation matrix: single-factor model
        sqrt_rho = math.sqrt(max(0, correlation))
        sqrt_1_minus_rho = math.sqrt(max(0, 1 - correlation))

        # Systematic factor: shared across all positions per simulation
        M = rng.standard_normal(self._num_sims)  # (num_sims,)

        # Idiosyncratic factors: independent per position
        epsilon = rng.standard_normal((self._num_sims, n_positions))  # (num_sims, n)

        # Latent variable
        Z = sqrt_rho * M[:, np.newaxis] + sqrt_1_minus_rho * epsilon  # (num_sims, n)

        # Convert to uniform via Phi (normal CDF)
        from scipy.stats import norm
        U = norm.cdf(Z)  # (num_sims, n)

        # Default indicator: default when U < PD
        defaults = (U < pds[np.newaxis, :]).astype(np.float64)  # (num_sims, n)

        # Portfolio loss per simulation
        position_losses = defaults * lgds[np.newaxis, :] * eads[np.newaxis, :]
        portfolio_losses = np.sum(position_losses, axis=1)  # (num_sims,)

        return portfolio_losses

    def run_stress_tests(
        self,
        positions: List[MCPosition],
        scenarios: Optional[List[StressScenario]] = None,
    ) -> Dict[str, MonteCarloVaRResult]:
        """Run VaR across multiple stress scenarios.

        Parameters
        ----------
        positions:
            Portfolio positions.
        scenarios:
            List of stress scenarios. Defaults to ``STRESS_SCENARIOS``.

        Returns
        -------
        Dict[str, MonteCarloVaRResult]
            Mapping of scenario name → VaR result.
        """
        if scenarios is None:
            scenarios = STRESS_SCENARIOS

        results = {}
        for scenario in scenarios:
            logger.info("Running stress scenario: %s", scenario.name)
            result = self.compute_var(positions, scenario)
            results[scenario.name] = result
            logger.info(
                "  VaR_99=%s  ES_99=%s  EL=%s",
                result.var_99, result.expected_shortfall_99, result.expected_loss,
            )

        return results
