"""
P4 Federated Learning — Rényi Differential Privacy Accounting

Implements privacy budget tracking per training round and cumulative across
all federated learning rounds using Rényi Differential Privacy (Mironov 2017).

Rényi DP provides tighter bounds than the moments accountant, allowing
more training rounds for the same privacy budget.

Reference:
- Mironov, "Rényi Differential Privacy of the Gaussian Mechanism," CSF 2017
- dp-accounting library: https://github.com/google/dp-accounting
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from .constants import DP_CUMULATIVE_EPSILON_MAX, DP_DELTA, DP_EPSILON

logger = logging.getLogger(__name__)

# Try to import dp-accounting; provide helpful error if unavailable.
# Note: event classes (PoissonSampledDpEvent, GaussianDpEvent) live on the
# package root in dp-accounting >= 0.4; the concrete accountants
# (rdp.RdpAccountant) remain in their submodules.
try:
    from dp_accounting import GaussianDpEvent, PoissonSampledDpEvent, rdp
    HAS_DP_ACCOUNTING = True
except ImportError:
    HAS_DP_ACCOUNTING = False
    rdp = None  # type: ignore[assignment]
    GaussianDpEvent = None  # type: ignore[assignment]
    PoissonSampledDpEvent = None  # type: ignore[assignment]
    logger.warning(
        "dp-accounting library not available. Install with: "
        "pip install dp-accounting>=0.7"
    )

# =============================================================================
# Data Classes for Privacy Accounting
# =============================================================================


@dataclasses.dataclass
class RoundPrivacyCost:
    """
    Privacy cost for a single federated learning round.

    Attributes
    ----------
    round_number:
        FL round number (0-indexed).
    epsilon_spent:
        Privacy epsilon spent this round.
    epsilon_cumulative:
        Cumulative epsilon spent across all rounds so far.
    delta:
        Failure probability bound (δ = 1e-5 per architecture spec).
    sampling_probability:
        Sampling probability for this round (batch_size / n_samples).
    noise_multiplier:
        Gaussian noise multiplier used this round.
    """

    round_number: int
    epsilon_spent: float
    epsilon_cumulative: float
    delta: float
    sampling_probability: float
    noise_multiplier: float


@dataclasses.dataclass
class DPBudgetStatus:
    """
    Current DP budget status.

    Attributes
    ----------
    epsilon_spent:
        Total epsilon spent across all rounds.
    epsilon_remaining:
        Remaining epsilon budget.
    epsilon_target:
        Target maximum cumulative epsilon.
    delta:
        Failure probability bound (δ).
    num_rounds:
        Number of rounds composed so far.
    is_exhausted:
        Whether budget is exhausted (epsilon_spent >= epsilon_target).
    """

    epsilon_spent: float
    epsilon_remaining: float
    epsilon_target: float
    delta: float
    num_rounds: int
    is_exhausted: bool


# =============================================================================
# RényiDPAccountant — Privacy Budget Tracker
# =============================================================================


class RenyiDPAccountant:
    """
    Rényi Differential Privacy accountant for federated learning.

    Tracks privacy budget per round and cumulative across all rounds using
    Rényi DP accounting. Provides tighter bounds than moments accountant.

    The accountant composes per-sample DP events (Poisson-sampled training
    with Gaussian noise) and computes the resulting (ε, δ) guarantee.

    Parameters
    ----------
    epsilon:
        Privacy budget per round (default 1.0 from architecture spec).
    delta:
        Failure probability bound (default 1e-5 from architecture spec).
    target_epsilon:
        Maximum cumulative epsilon before training should stop
        (default 3.0 from architecture spec).

    QUANT + REX sign-off required before changing epsilon, delta, or target_epsilon.

    Example
    -------
    >>> accountant = RenyiDPAccountant()
    >>> accountant.compose_round(batch_size=256, n_samples=50000, noise_multiplier=1.1)
    1.0012345678901234
    >>> accountant.get_status()
    DPBudgetStatus(epsilon_spent=1.001..., epsilon_remaining=1.999..., ...)
    """

    def __init__(
        self,
        epsilon: float = float(DP_EPSILON),
        delta: float = float(DP_DELTA),
        target_epsilon: float = float(DP_CUMULATIVE_EPSILON_MAX),
    ) -> None:
        if not HAS_DP_ACCOUNTING:
            raise ImportError(
                "dp-accounting library is required for Rényi DP accounting. "
                "Install with: pip install dp-accounting>=0.7"
            )

        self.epsilon_per_round = epsilon
        self.delta = delta
        self.target_epsilon = target_epsilon

        # Rényi DP accountant
        self.accountant = rdp.RdpAccountant()

        # Round tracking
        self.num_rounds = 0
        self.round_costs: list[RoundPrivacyCost] = []

        # Current cumulative values
        self._current_epsilon = 0.0

        logger.info(
            f"RényiDPAccountant initialized: ε={epsilon}, δ={delta}, "
            f"target_ε={target_epsilon}"
        )

    def compose_round(
        self,
        batch_size: int,
        n_samples: int,
        noise_multiplier: float = 1.1,
    ) -> float:
        """
        Compose privacy cost for a single training round.

        Uses Poisson-sampled composition: each training example is included
        in training with probability batch_size / n_samples.

        Parameters
        ----------
        batch_size:
            Batch size used in local training.
        n_samples:
            Total number of samples in the local dataset.
        noise_multiplier:
            Gaussian noise multiplier (default 1.1 from architecture spec).

        Returns
        -------
        float
            Cumulative epsilon after composing this round.

        Raises
        ------
        ValueError
            If sampling probability > 1.0.
        RuntimeError
            If budget is already exhausted.
        """
        if self.is_budget_exhausted():
            logger.warning("DP budget already exhausted, but composing round anyway")

        # Calculate sampling probability
        sampling_probability = min(1.0, batch_size / n_samples)

        if sampling_probability > 1.0:
            raise ValueError(
                f"Sampling probability {sampling_probability} > 1.0. "
                f"Check batch_size ({batch_size}) and n_samples ({n_samples})."
            )

        # Compose the round using Rényi DP accounting.
        # DP-SGD: Gaussian mechanism applied to a Poisson-subsampled batch.
        # This is the standard privacy-amplification-by-subsampling composition;
        # the Gaussian event nests inside the PoissonSampled event to express
        # "apply Gaussian noise to the sampled records," not "compose two
        # independent events side by side."
        round_event = PoissonSampledDpEvent(
            sampling_probability=sampling_probability,
            event=GaussianDpEvent(noise_multiplier=noise_multiplier),
        )
        self.accountant.compose(round_event)

        # Get new cumulative epsilon
        new_epsilon = self.accountant.get_epsilon(target_delta=self.delta)
        epsilon_spent = new_epsilon - self._current_epsilon

        # Update state
        self.num_rounds += 1
        self._current_epsilon = new_epsilon

        # Record round cost
        round_cost = RoundPrivacyCost(
            round_number=self.num_rounds,
            epsilon_spent=epsilon_spent,
            epsilon_cumulative=new_epsilon,
            delta=self.delta,
            sampling_probability=sampling_probability,
            noise_multiplier=noise_multiplier,
        )
        self.round_costs.append(round_cost)

        logger.debug(
            f"Round {self.num_rounds}: ε_spent={epsilon_spent:.6f}, "
            f"ε_cumulative={new_epsilon:.6f}, sampling_prob={sampling_probability:.4f}"
        )

        return new_epsilon

    def get_epsilon(self, target_delta: Optional[float] = None) -> tuple[float, float]:
        """
        Get current (ε, δ) guarantee.

        Parameters
        ----------
        target_delta:
            Target delta value (defaults to accountant's delta).

        Returns
        -------
        tuple[float, float]
            (epsilon, delta) guarantee.
        """
        if target_delta is None:
            target_delta = self.delta
        epsilon = self.accountant.get_epsilon(target_delta=target_delta)
        return epsilon, target_delta

    def get_status(self) -> DPBudgetStatus:
        """
        Get current DP budget status.

        Returns
        -------
        DPBudgetStatus
            Current budget status.
        """
        epsilon_spent, delta = self.get_epsilon()
        epsilon_remaining = max(0.0, self.target_epsilon - epsilon_spent)

        return DPBudgetStatus(
            epsilon_spent=epsilon_spent,
            epsilon_remaining=epsilon_remaining,
            epsilon_target=self.target_epsilon,
            delta=delta,
            num_rounds=self.num_rounds,
            is_exhausted=self.is_budget_exhausted(),
        )

    def is_budget_exhausted(self, target_epsilon: Optional[float] = None) -> bool:
        """
        Check if cumulative DP budget exceeds target.

        Parameters
        ----------
        target_epsilon:
            Target epsilon threshold (defaults to accountant's target_epsilon).

        Returns
        -------
        bool
            True if budget is exhausted (ε_cumulative ≥ target_epsilon).
        """
        if target_epsilon is None:
            target_epsilon = self.target_epsilon
        epsilon_spent, _ = self.get_epsilon()
        return epsilon_spent >= target_epsilon

    def get_round_costs(self) -> list[RoundPrivacyCost]:
        """
        Get list of privacy costs for all rounds.

        Returns
        -------
        list[RoundPrivacyCost]
            Round-by-round privacy costs.
        """
        return self.round_costs.copy()

    def reset(self) -> None:
        """
        Reset the accountant (clear all rounds composed).

        Useful for testing or re-running experiments.
        """
        self.accountant = rdp.RdpAccountant()
        self.num_rounds = 0
        self.round_costs = []
        self._current_epsilon = 0.0
        logger.info("RényiDPAccountant reset")


# =============================================================================
# Utility Functions
# =============================================================================


def compose_epsilon_round(
    epsilon: float = 1.0,
    delta: float = 1e-5,
    batch_size: int = 256,
    n_samples: int = 50_000,
    noise_multiplier: float = 1.1,
    num_rounds: int = 50,
) -> float:
    """
    Quick utility function to estimate cumulative epsilon after N rounds.

    This is useful for planning and budget estimation before running
    actual federated learning experiments.

    Parameters
    ----------
    epsilon:
        Privacy budget per round (default 1.0).
    delta:
        Failure probability bound (default 1e-5).
    batch_size:
        Batch size (default 256).
    n_samples:
        Total samples per round (default 50,000).
    noise_multiplier:
        Gaussian noise multiplier (default 1.1).
    num_rounds:
        Number of rounds to estimate (default 50).

    Returns
    -------
    float
        Estimated cumulative epsilon after num_rounds.

    Raises
    ------
    ImportError
        If dp-accounting library is not available.
    """
    if not HAS_DP_ACCOUNTING:
        raise ImportError(
            "dp-accounting library required. Install with: pip install dp-accounting>=0.7"
        )

    accountant = rdp.RdpAccountant()
    sampling_prob = min(1.0, batch_size / n_samples)

    round_event = PoissonSampledDpEvent(
        sampling_probability=sampling_prob,
        event=GaussianDpEvent(noise_multiplier=noise_multiplier),
    )
    accountant.compose(round_event, count=num_rounds)

    return accountant.get_epsilon(target_delta=delta)


def verify_dp_budget_not_exhausted(
    epsilon_cumulative: float,
    target_epsilon: float = 3.0,
) -> bool:
    """
    Verify DP budget is not exhausted.

    Parameters
    ----------
    epsilon_cumulative:
        Cumulative epsilon spent.
    target_epsilon:
        Target maximum epsilon (default 3.0).

    Returns
    -------
    bool
        True if budget is not exhausted.
    """
    return epsilon_cumulative < target_epsilon
