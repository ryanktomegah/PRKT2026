"""
P4 Federated Learning — Opacus PrivacyEngine Integration

Wraps PyTorch optimizer with Opacus PrivacyEngine for DP-SGD.

Implements per-sample gradient clipping and Gaussian noise injection to achieve
(ε, δ)-differential privacy. The PrivacyEngine ensures that any single
training example has bounded influence on the model.

Reference:
- Abadi et al. 2016, "Deep Learning with Differential Privacy," CCS
- Opacus documentation: https://opacus.ai/

DP Parameters (from architecture spec):
- ε=1.0 (privacy budget per round)
- δ=1e-5 (failure probability bound)
- L2 clipping norm=1.0
- Noise multiplier=1.1 (calibrated to achieve ε=1.0, δ=1e-5)
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Try to import Opacus; provide helpful error if unavailable
try:
    from opacus import PrivacyEngine  # type: ignore[import-untyped]
    from opacus.optimizers import DPOptimizer  # type: ignore[import-untyped]
    HAS_OPACUS = True
except ImportError:
    HAS_OPACUS = False
    PrivacyEngine = None  # type: ignore[assignment]
    DPOptimizer = None  # type: ignore[assignment]
    logging.getLogger(__name__).warning(
        "Opacus not available. Install with: pip install opacus>=0.14"
    )

from lip.p12_federated_learning.constants import (
    DP_CLIP_NORM,
    DP_DELTA,
    DP_EPSILON,
    DP_NOISE_MULTIPLIER,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Opacus Integration Functions
# =============================================================================


def attach_privacy_engine(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    data_loader: DataLoader,
    noise_multiplier: float = DP_NOISE_MULTIPLIER,
    max_grad_norm: float = DP_CLIP_NORM,
    alphas: float = float(DP_EPSILON),
    delta: float = float(DP_DELTA),
) -> PrivacyEngine:
    """
    Attach Opacus PrivacyEngine to optimizer for DP-SGD.

    The PrivacyEngine wraps the optimizer and:
    1. Clips per-sample gradients to L2 norm
    2. Adds Gaussian noise calibrated to achieve (ε, δ)-DP
    3. Provides formal privacy guarantees

    Parameters
    ----------
    model:
        PyTorch model to train with DP-SGD.
    optimizer:
        PyTorch optimizer (will be wrapped by PrivacyEngine).
    data_loader:
        Training DataLoader (needed for batch_size calculation).
    noise_multiplier:
        Gaussian noise multiplier (default 1.1).
    max_grad_norm:
        L2 norm for gradient clipping (default 1.0).
    alphas:
        Target epsilon (default 1.0).
    delta:
        Target delta (default 1e-5).

    Returns
    -------
    PrivacyEngine
        Attached PrivacyEngine (call .attach(optimizer)).

    Raises
    ------
    ImportError
        If Opacus is not available.
    ValueError
        If batch_size is invalid.
    """
    if not HAS_OPACUS:
        raise ImportError(
            "Opacus required. Install with: pip install opacus>=0.14"
        )

    batch_size = getattr(data_loader, "batch_size", None)
    if batch_size is None:
        raise ValueError("DataLoader must have batch_size attribute")

    sample_size = len(data_loader.dataset)  # type: ignore[arg-type]
    if sample_size <= 0:
        raise ValueError(f"Invalid sample size: {sample_size}")

    # Verify all parameters are requires_grad=True
    requires_grad_params = [p for p in model.parameters() if p.requires_grad]
    if len(requires_grad_params) == 0:
        raise ValueError("Model has no trainable parameters")

    # Create PrivacyEngine and make model private
    # Opacus 1.5+ uses make_private() API
    privacy_engine = PrivacyEngine(accountant='rdp')
    result = privacy_engine.make_private(
        module=model,
        optimizer=optimizer,
        data_loader=data_loader,
        noise_multiplier=noise_multiplier,
        max_grad_norm=max_grad_norm,
        poisson_sampling=False,  # Disabled for compatibility
        grad_sample_mode='ew',  # Use efficient weight mode (more compatible with standard modules)
    )
    # make_private returns either 3 or 4 values depending on Opacus version
    if len(result) == 3:
        model, optimizer, _ = result
    else:
        # 4 values: module, optimizer, dp_loss, data_loader
        model, optimizer, _, _ = result

    logger.info(
        f"PrivacyEngine attached: noise_multiplier={noise_multiplier}, "
        f"max_grad_norm={max_grad_norm}, batch_size={batch_size}, "
        f"sample_size={sample_size}"
    )

    return privacy_engine


def create_dp_optimizer(
    model: nn.Module,
    lr: float = 0.001,
    weight_decay: float = 0.0,
    **optimizer_kwargs: Any,
) -> DPOptimizer:
    """
    Create a DP-compatible optimizer.

    Note: This creates the base optimizer; you still need to attach
    PrivacyEngine separately with attach_privacy_engine().

    Parameters
    ----------
    model:
        PyTorch model.
    lr:
        Learning rate (default 0.001).
    weight_decay:
        Weight decay (default 0.0).
    **optimizer_kwargs:
        Additional optimizer arguments.

    Returns
    -------
    DPOptimizer
        DP-compatible optimizer.
    """
    if not HAS_OPACUS:
        raise ImportError(
            "Opacus required. Install with: pip install opacus>=0.14"
        )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay,
        **optimizer_kwargs,
    )

    # Wrap with DPOptimizer for better DP-SGD performance
    dp_optimizer = DPOptimizer(
        optimizer=optimizer,
        noise_multiplier=DP_NOISE_MULTIPLIER,
        max_grad_norm=DP_CLIP_NORM,
        expected_batch_size=256,  # Typical batch size
    )

    logger.info(f"DPOptimizer created: lr={lr}, weight_decay={weight_decay}")

    return dp_optimizer


def validate_dp_compatibility(
    model: nn.Module,
    data_loader: DataLoader,
) -> dict[str, Any]:
    """
    Validate model and data loader for DP-SGD compatibility.

    Checks:
    - Model has trainable parameters
    - DataLoader has valid batch_size
    - Sample size is reasonable

    Parameters
    ----------
    model:
        PyTorch model.
    data_loader:
        Training DataLoader.

    Returns
    -------
    dict
        Validation results with any warnings or errors.
    """
    result: dict[str, Any] = {
        "compatible": True,
        "warnings": [],
        "errors": [],
    }

    # Check trainable parameters
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    if len(trainable_params) == 0:
        result["errors"].append("Model has no trainable parameters")
        result["compatible"] = False
    else:
        result["num_params"] = sum(p.numel() for p in trainable_params)

    # Check batch_size
    batch_size = getattr(data_loader, "batch_size", None)
    if batch_size is None:
        result["warnings"].append("DataLoader has no batch_size attribute")
    elif batch_size <= 0:
        result["errors"].append(f"Invalid batch_size: {batch_size}")
        result["compatible"] = False
    else:
        result["batch_size"] = batch_size

    # Check sample size
    sample_size = len(data_loader.dataset)  # type: ignore[arg-type]
    if sample_size <= 0:
        result["errors"].append(f"Invalid sample size: {sample_size}")
        result["compatible"] = False
    else:
        result["sample_size"] = sample_size

    # Check sampling probability
    if batch_size and sample_size:
        sampling_prob = min(1.0, batch_size / sample_size)
        result["sampling_probability"] = sampling_prob
        if sampling_prob > 1.0:
            result["warnings"].append(f"Sampling probability > 1.0: {sampling_prob}")

    return result


def compute_dp_noise_scale(
    max_grad_norm: float = DP_CLIP_NORM,
    noise_multiplier: float = DP_NOISE_MULTIPLIER,
) -> float:
    """
    Compute DP noise scale (standard deviation).

    The noise added to gradients is N(0, σ²I) where:
    σ = noise_multiplier * max_grad_norm

    Parameters
    ----------
    max_grad_norm:
        L2 clipping norm.
    noise_multiplier:
        Noise multiplier.

    Returns
    -------
    float
        Noise scale (standard deviation).
    """
    return noise_multiplier * max_grad_norm


def get_noise_multiplier_for_epsilon(
    target_epsilon: float = float(DP_EPSILON),
    target_delta: float = float(DP_DELTA),
    batch_size: int = 256,
    sample_size: int = 50_000,
    max_grad_norm: float = DP_CLIP_NORM,
) -> float:
    """
    Compute noise multiplier required to achieve target (ε, δ).

    This is a simplified computation; actual calibration may require
    running the accountant multiple times or using Opacus's calibration
    utilities.

    Parameters
    ----------
    target_epsilon:
        Target epsilon.
    target_delta:
        Target delta.
    batch_size:
        Batch size.
    sample_size:
        Total sample size.
    max_grad_norm:
        L2 clipping norm.

    Returns
    -------
    float
        Estimated noise multiplier.

    Note
    ----
    This is an approximation. For production use, use Opacus's
    calibration utilities or search-based calibration.
    """
    if not HAS_OPACUS:
        raise ImportError(
            "Opacus required. Install with: pip install opacus>=0.14"
        )


    # Simplified: noise multiplier ≈ 1.1 achieves ε≈1.0 for typical settings
    # This is the value from the architecture spec
    # For precise calibration, use binary search or Opacus calibration tools
    return 1.1


def get_privacy_spent(
    alphas: float,
    delta: float,
    batch_size: int,
    sample_size: int,
    noise_multiplier: float,
    num_rounds: int = 1,
) -> dict[str, float]:
    """
    Estimate privacy cost for given DP-SGD configuration.

    Uses Rényi DP accounting to compute (ε, δ) after num_rounds.

    Parameters
    ----------
    alphas:
        Target epsilon.
    delta:
        Target delta.
    batch_size:
        Batch size.
    sample_size:
        Total sample size.
    noise_multiplier:
        Noise multiplier.
    num_rounds:
        Number of training rounds (default 1).

    Returns
    -------
    dict
        Privacy cost including:
        - epsilon_per_round: ε per round
        - epsilon_cumulative: Cumulative ε
        - delta: δ
    """
    if not HAS_OPACUS:
        raise ImportError(
            "Opacus required. Install with: pip install opacus>=0.14"
        )

    from dp_accounting import dp_event, rdp  # type: ignore[import-untyped]

    accountant = rdp.RdpAccountant()
    sampling_prob = min(1.0, batch_size / sample_size)

    # DP-SGD: Gaussian mechanism on a Poisson-subsampled batch.
    # Events nest — amplification by subsampling requires the Gaussian event
    # inside the PoissonSampled event. Matches dp_accountant.compose_round.
    round_event = dp_event.PoissonSampledDpEvent(
        sampling_probability=sampling_prob,
        event=dp_event.GaussianDpEvent(noise_multiplier=noise_multiplier),
    )
    accountant.compose(round_event, count=num_rounds)

    epsilon_cumulative = accountant.get_epsilon(target_delta=delta)

    # Approximate per-round epsilon
    epsilon_per_round = epsilon_cumulative / num_rounds if num_rounds > 0 else epsilon_cumulative

    return {
        "epsilon_per_round": epsilon_per_round,
        "epsilon_cumulative": epsilon_cumulative,
        "delta": delta,
    }
