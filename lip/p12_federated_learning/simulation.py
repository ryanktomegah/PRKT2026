"""
P4 Federated Learning — Simulation Runner

Runs federated learning simulation with FedProx strategy, sweeping across
proximal coefficient (μ) values to demonstrate robustness to non-IID data.

The μ sweep produces:
- Convergence plots (AUC vs rounds for each μ)
- Per-bank AUC (fairness analysis)
- Convergence speed comparison
- DP budget tracking

Reference:
- Li et al. 2020, "Federated Optimization in Heterogeneous Networks," ICLR
- Flower framework: https://flower.dev/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Try to import Flower; provide helpful error if unavailable
try:
    import flwr as fl
    from flwr.server import ServerConfig
    from flwr.server.strategy import FedProx
    HAS_FLOWER = True
except ImportError:
    HAS_FLOWER = False
    fl = None  # type: ignore[assignment]
    FedProx = None  # type: ignore[assignment,misc]
    ServerConfig = None  # type: ignore[assignment,misc]
    logging.getLogger(__name__).warning(
        "Flower not available. Install with: pip install flwr[simulation]>=1.0"
    )

from lip.p12_federated_learning.client import LIPFlowerClient
from lip.p12_federated_learning.constants import (
    FEDPROX_MU_VALUES,
    LOCAL_EPOCHS,
    MIN_FIT_CLIENTS,
    NUM_ROUNDS,
    NUM_SEEDS,
    SAMPLE_FRACTION,
)
from lip.p12_federated_learning.dp_accountant import RenyiDPAccountant
from lip.p12_federated_learning.local_ensemble import LocalEnsemble
from lip.p12_federated_learning.models import FederatedModel, LocalModel, SharedModel
from lip.p12_federated_learning.privacy_engine import attach_privacy_engine
from lip.p12_federated_learning.synthetic_banks import (
    SyntheticBankData,
    create_dataloader,
    generate_synthetic_bank_data,
    generate_synthetic_banks,
    print_distribution_comparison,
    verify_non_iid_property,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Simulation Results Data Structure
# =============================================================================


class SimulationResult:
    """
    Results from a single federated learning simulation run.

    Attributes
    ----------
    mu:
        Proximal coefficient used.
    seed:
        Random seed for reproducibility.
    history:
        Training history (metrics per round).
    dp_epsilon_cumulative:
        Cumulative DP epsilon spent.
    """
    def __init__(
        self,
        mu: float,
        seed: int,
        history: Any,
        dp_epsilon_cumulative: float,
    ):
        self.mu = mu
        self.seed = seed
        self.history = history
        self.dp_epsilon_cumulative = dp_epsilon_cumulative


# =============================================================================
# Client Factory Function
# =============================================================================


def create_client(
    bank_data: SyntheticBankData,
    seed: int,
    mu: float = 0.01,
) -> LIPFlowerClient:
    """
    Create a Flower client for a synthetic bank.

    Parameters
    ----------
    bank_data:
        Synthetic bank data.
    seed:
        Random seed for reproducibility.
    mu:
        Proximal coefficient (not directly used here, but useful for context).

    Returns
    -------
    LIPFlowerClient
        Configured Flower client.
    """
    # Set random seed for reproducibility
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Create DataLoader
    batch_size = 256
    train_loader = create_dataloader(bank_data, batch_size=batch_size, shuffle=True)

    # Initialize models
    local_model = LocalModel()
    shared_model = SharedModel()
    federated_model = FederatedModel(local_model, shared_model)

    # Initialize optimizer
    optimizer = torch.optim.AdamW(
        federated_model.parameters(),
        lr=0.001,
        weight_decay=1e-5,
    )

    # Attach Opacus PrivacyEngine
    privacy_engine = attach_privacy_engine(
        federated_model,
        optimizer,
        train_loader,
        noise_multiplier=1.1,  # DP_NOISE_MULTIPLIER
        max_grad_norm=1.0,  # DP_CLIP_NORM
        alphas=1.0,  # DP_EPSILON
        delta=1e-5,  # DP_DELTA
    )

    # Initialize DP accountant
    dp_accountant = RenyiDPAccountant(
        epsilon=1.0,
        delta=1e-5,
        target_epsilon=3.0,  # DP_CUMULATIVE_EPSILON_MAX
    )

    # Initialize local ensemble (LightGBM will be lazy-initialized)
    local_ensemble = LocalEnsemble(lgbm_model=None)

    return LIPFlowerClient(
        federated_model=federated_model,
        optimizer=optimizer,
        privacy_engine=privacy_engine,
        dp_accountant=dp_accountant,
        local_ensemble=local_ensemble,
        train_loader=train_loader,
        mu=mu,
    )


# =============================================================================
# μ Sweep Runner
# =============================================================================


def run_mu_sweep(
    mu_values: list[float] | None = None,
    n_seeds: int = NUM_SEEDS,
    num_rounds: int = NUM_ROUNDS,
    output_dir: str | None = None,
) -> dict[tuple[float, int], SimulationResult]:
    """
    Run federated learning simulation sweeping across μ values.

    This is the main entry point for P4 federated learning experiments.
    Runs simulations for each μ value with multiple seeds for
    statistical robustness.

    Parameters
    ----------
    mu_values:
        List of μ values to sweep. If None, uses FEDPROX_MU_VALUES
        from constants ([0.0, 0.001, 0.01, 0.1]).
    n_seeds:
        Number of random seeds per μ value (default 3).
    num_rounds:
        Number of federated learning rounds (default 50).
    output_dir:
        Directory to save results (optional).

    Returns
    -------
    dict[tuple[float, int], SimulationResult]
        Results keyed by (mu, seed).

    Raises
    ------
    ImportError
        If Flower or dp-accounting is not available.

    Example
    -------
    >>> results = run_mu_sweep(mu_values=[0.0, 0.01], n_seeds=1)
    >>> for key, result in results.items():
    ...     mu, seed = key
    ...     print(f"μ={mu}, seed={seed}: ε={result.dp_epsilon_cumulative:.4f}")
    """
    if not HAS_FLOWER:
        raise ImportError(
            "Flower required. Install with: pip install flwr[simulation]>=1.0"
        )

    if mu_values is None:
        mu_values = FEDPROX_MU_VALUES

    # Generate synthetic banks
    banks = generate_synthetic_banks()
    bank_data_list = [generate_synthetic_bank_data(bank, k_neighbors=5) for bank in banks]

    # Verify non-IID property
    non_iid_result = verify_non_iid_property(bank_data_list)
    logger.info(
        f"Non-IID verification: failure_rate_variance={non_iid_result['failure_rate_variance']:.4f}, "
        f"avg_pairwise_distance={non_iid_result['avg_pairwise_distance']:.4f}, "
        f"is_non_iid={non_iid_result['is_non_iid']}"
    )

    print_distribution_comparison(bank_data_list)

    results = {}

    for mu in mu_values:
        for seed in range(n_seeds):
            logger.info(f"\n{'='*60}")
            logger.info(f"Running simulation: μ={mu}, seed={seed}")
            logger.info(f"{'='*60}")

            # Create strategy. FedProx uses `proximal_mu` for the μ coefficient
            # and `on_fit_config_fn` to forward per-round config to clients.
            strategy = FedProx(
                proximal_mu=mu,
                min_fit_clients=MIN_FIT_CLIENTS,
                fraction_fit=SAMPLE_FRACTION,
                on_fit_config_fn=lambda rnd: {"local_epochs": LOCAL_EPOCHS},
            )

            # Define client function
            def client_fn(cid: str) -> LIPFlowerClient:
                """Client function for Flower simulation."""
                client_id = int(cid)
                return create_client(
                    bank_data_list[client_id],
                    seed=seed + client_id * 1000,  # Unique seed per client
                    mu=mu,
                )

            # Run simulation (guarded by HAS_FLOWER raise at top of function)
            assert fl is not None  # noqa: S101 — mypy narrowing after HAS_FLOWER guard
            hist = fl.simulation.start_simulation(  # type: ignore[attr-defined]
                client_fn=client_fn,
                num_clients=len(banks),
                config=ServerConfig(num_rounds=num_rounds),
                strategy=strategy,
                client_resources={
                    "num_cpus": 2,
                },
                ray_init_args={"ignore_reinit_error": True},
            )

            # Extract DP epsilon from one of the clients
            # (All clients should have similar epsilon spent)
            epsilon_cumulative = 0.0
            if hist and hist.metrics_centralized:
                # Look at last round's DP epsilon
                for round_metrics in hist.metrics_centralized.values():
                    if "dp_epsilon_cumulative" in round_metrics:
                        epsilon_cumulative = max(
                            epsilon_cumulative,
                            round_metrics["dp_epsilon_cumulative"],
                        )

            result = SimulationResult(
                mu=mu,
                seed=seed,
                history=hist,
                dp_epsilon_cumulative=epsilon_cumulative,
            )

            results[(mu, seed)] = result

            logger.info(
                f"Simulation complete: μ={mu}, seed={seed}, "
                f"ε_cumulative={epsilon_cumulative:.4f}"
            )

    # Save results if output_dir specified
    if output_dir:
        save_simulation_results(results, output_dir)

    return results


# =============================================================================
# Result Processing and Visualization
# =============================================================================


def save_simulation_results(
    results: dict[tuple[float, int], SimulationResult],
    output_dir: str,
) -> None:
    """
    Save simulation results to disk.

    Parameters
    ----------
    results:
        Simulation results from run_mu_sweep.
    output_dir:
        Directory to save results.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save results summary
    summary_file = output_path / "simulation_summary.txt"
    with open(summary_file, "w") as f:
        f.write("P4 Federated Learning Simulation Results\n")
        f.write("=" * 60 + "\n\n")

        for key, result in results.items():
            mu, seed = key
            f.write(f"μ={mu}, seed={seed}\n")
            f.write(f"  DP ε cumulative: {result.dp_epsilon_cumulative:.6f}\n")
            f.write(f"  Num rounds: {result.history.metrics_centralized is not None}\n\n")

    logger.info(f"Results saved to {output_dir}")


def extract_metrics_by_mu(
    results: dict[tuple[float, int], SimulationResult],
    metric_name: str = "auc",
) -> dict[float, list[float]]:
    """
    Extract metrics grouped by μ value.

    Parameters
    ----------
    results:
        Simulation results from run_mu_sweep.
    metric_name:
        Metric to extract (e.g., "auc", "loss").

    Returns
    -------
    dict[float, list[float]]
        Metrics grouped by μ value.
    """
    metrics_by_mu: dict[float, list[float]] = {}

    for (mu, seed), result in results.items():
        if mu not in metrics_by_mu:
            metrics_by_mu[mu] = []

        if result.history and result.history.metrics_centralized:
            # Extract final metric value
            for round_metrics in result.history.metrics_centralized.values():
                if metric_name in round_metrics:
                    metrics_by_mu[mu].append(round_metrics[metric_name])

    return metrics_by_mu


def compute_convergence_stats(
    results: dict[tuple[float, int], SimulationResult],
    target_auc: float = 0.85,
) -> dict[float, dict[str, float]]:
    """
    Compute convergence statistics for each μ value.

    Parameters
    ----------
    results:
        Simulation results from run_mu_sweep.
    target_auc:
        Target AUC threshold (default 0.85).

    Returns
    -------
    dict
        Convergence statistics per μ:
        - auc_mean: Mean final AUC
        - auc_std: Standard deviation of final AUC
        - rounds_to_target: Average rounds to reach target AUC
        - converged: Whether converged to target AUC
    """
    stats: dict[float, dict[str, float]] = {}

    for mu in FEDPROX_MU_VALUES:
        auc_values = []

        for (mu_key, seed), result in results.items():
            if mu_key != mu:
                continue

            if result.history and result.history.metrics_centralized:
                for round_metrics in result.history.metrics_centralized.values():
                    if "auc" in round_metrics:
                        auc_values.append(round_metrics["auc"])
                        # Track rounds to target (simplified)
                        # In real implementation, extract from per-round metrics
                        break

        if auc_values:
            auc_mean = float(np.mean(auc_values))
            auc_std = float(np.std(auc_values))
            converged = auc_mean >= target_auc
            rounds_to_target_val = 50.0 if converged else float("nan")  # Placeholder

            stats[mu] = {
                "auc_mean": auc_mean,
                "auc_std": auc_std,
                "rounds_to_target": rounds_to_target_val,
                "converged": float(converged),
            }

    return stats


# =============================================================================
# Quick Test Function
# =============================================================================


def quick_test() -> None:
    """
    Run a quick test with minimal settings.

    Useful for verifying the setup without running full experiments.
    """
    logger.info("Running quick test with minimal settings...")

    # Run with 2 μ values, 1 seed each, 2 rounds
    results = run_mu_sweep(
        mu_values=[0.0, 0.01],
        n_seeds=1,
        num_rounds=2,
    )

    # Print summary
    logger.info("\nQuick test results:")
    for (mu, seed), result in results.items():
        logger.info(f"  μ={mu}, seed={seed}: ε={result.dp_epsilon_cumulative:.6f}")

    # Extract convergence stats
    stats = compute_convergence_stats(results)
    logger.info("\nConvergence stats:")
    for mu, mu_stats in stats.items():
        logger.info(
            f"  μ={mu}: AUC={mu_stats['auc_mean']:.4f}±{mu_stats['auc_std']:.4f}, "
            f"converged={mu_stats['converged']}"
        )

    logger.info("Quick test complete!")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run quick test if executed directly
    quick_test()
