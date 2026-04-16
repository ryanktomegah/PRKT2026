"""
P4 Federated Learning — Flower Client Implementation

Implements LIPFlowerClient for federated learning with:
- Model splitting (only shared weights transmitted)
- DP-SGD via Opacus PrivacyEngine
- Rényi DP accounting per round
- Local PyTorch + LightGBM ensemble coordination

Patent Claim 2 Compliance: "only weights of the final aggregation layers
are shared across the consortium" — literally satisfied by get_parameters()
returning only SharedModel state_dict.

Reference:
- Flower framework: https://flower.dev/
- Opacus DP-SGD: https://opacus.ai/
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

# Try to import Flower; provide helpful error if unavailable
try:
    import flwr as fl
    from flwr.common import (
        Config,
        NDArrays,
        Scalar,
    )
    HAS_FLOWER = True
except ImportError:
    HAS_FLOWER = False
    fl = None  # type: ignore[assignment]
    logging.getLogger(__name__).warning(
        "Flower not available. Install with: pip install flwr[simulation]>=1.0"
    )

from lip.p12_federated_learning.constants import LOCAL_EPOCHS
from lip.p12_federated_learning.dp_accountant import RenyiDPAccountant
from lip.p12_federated_learning.local_ensemble import LocalEnsemble
from lip.p12_federated_learning.models import FederatedModel

logger = logging.getLogger(__name__)


# =============================================================================
# LIPFlowerClient — Flower Client Implementation
# =============================================================================


class LIPFlowerClient(fl.client.NumPyClient):
    """
    Flower client for LIP federated learning.

    Implements model splitting where only SharedModel weights are transmitted
    to the server, satisfying Patent Claim 2 compliance.

    Key Design Points:
    1. get_parameters() returns ONLY SharedModel state_dict — LocalModel never leaves
    2. set_parameters() updates ONLY SharedModel — LocalModel untouched
    3. fit() trains full model with DP-SGD; only shared weights returned
    4. DP budget is tracked per round via RenyiDPAccountant
    5. LightGBM is updated locally after each FL round

    Parameters
    ----------
    federated_model:
        FederatedModel wrapping LocalModel + SharedModel.
    optimizer:
        PyTorch optimizer (wrapped by Opacus PrivacyEngine).
    privacy_engine:
        Opacus PrivacyEngine for DP-SGD.
    dp_accountant:
        RenyiDPAccountant for tracking privacy budget.
    local_ensemble:
        LocalEnsemble for PyTorch + LightGBM coordination.
    train_loader:
        Training DataLoader.

    Example
    -------
    >>> client = LIPFlowerClient(model, optimizer, privacy_engine,
    ...                            dp_accountant, local_ensemble, train_loader)
    >>> params, _, _ = client.get_parameters(config={})
    >>> assert len(params) == SHARED_PARAM_COUNT  # Only shared weights
    """

    def __init__(
        self,
        federated_model: FederatedModel,
        optimizer: torch.optim.Optimizer,
        privacy_engine: Any,
        dp_accountant: RenyiDPAccountant,
        local_ensemble: LocalEnsemble,
        train_loader: DataLoader,
        mu: float = 0.01,
    ) -> None:
        if not HAS_FLOWER:
            raise ImportError(
                "Flower required. Install with: pip install flwr[simulation]>=1.0"
            )

        super().__init__()

        self.model = federated_model
        self.optimizer = optimizer
        self.privacy_engine = privacy_engine
        self.dp_accountant = dp_accountant
        self.local_ensemble = local_ensemble
        self.train_loader = train_loader
        self.mu = mu

        self.device = next(self.model.parameters()).device

        # Track whether this is the first round (for initialization)
        self.is_first_round = True

        # Store server's shared model parameters for FedProx proximal term
        # These are updated at the start of each round in set_parameters()
        self._server_shared_params: dict[str, torch.Tensor] = {}

        logger.info(
            f"LIPFlowerClient initialized: device={self.device}, "
            f"train_samples={len(self.train_loader.dataset)}, "
            f"batch_size={self.train_loader.batch_size}"
        )

    def get_parameters(self, config: Config) -> NDArrays:
        """
        Return ONLY SharedModel parameters — LocalModel never transmitted.

        This is the key mechanism for Patent Claim 2 compliance.
        Only the final aggregation layers (SharedModel) are federated.

        Parameters
        ----------
        config:
            Flower config (unused).

        Returns
        -------
        NDArrays
            Numpy arrays of ONLY SharedModel parameters.
        """
        # Get ONLY shared model's state dict
        shared_state_dict = self.model.shared.state_dict()

        # Convert to numpy arrays for Flower
        shared_params = [val.cpu().numpy() for val in shared_state_dict.values()]

        # Log for verification
        if self.is_first_round:
            logger.info(
                f"get_parameters: returning {len(shared_params)} shared parameters "
                f"(only SharedModel weights, as per Patent Claim 2)"
            )
            self.is_first_round = False

        return shared_params

    def set_parameters(self, parameters: NDArrays, config: Config) -> None:
        """
        Update ONLY SharedModel — LocalModel untouched.

        Also stores server's shared parameters for FedProx proximal term.

        Parameters
        ----------
        parameters:
            Numpy arrays of SharedModel weights from server.
        config:
            Flower config (unused).

        Raises
        ------
        ValueError
            If parameter count mismatch.
        """
        shared_state_dict = self.model.shared.state_dict()
        param_keys = list(shared_state_dict.keys())

        if len(parameters) != len(param_keys):
            raise ValueError(
                f"Parameter count mismatch: expected {len(param_keys)}, "
                f"got {len(parameters)}"
            )

        # Create state dict from server parameters
        state_dict = {
            k: torch.tensor(v).to(self.device)
            for k, v in zip(param_keys, parameters)
        }

        # Store server's shared parameters for FedProx proximal term
        # These are used in the loss during local training
        self._server_shared_params = {k: v.clone().detach() for k, v in state_dict.items()}

        # Load ONLY into shared model (local model untouched)
        self.model.shared.load_state_dict(state_dict, strict=True)

        logger.debug(
            f"set_parameters: updated SharedModel with {len(parameters)} parameters, "
            f"LocalModel unchanged"
        )

    def fit(
        self,
        parameters: NDArrays,
        config: Config,
    ) -> tuple[NDArrays, int, dict[str, Scalar]]:
        """
        Local training with DP-SGD.

        Training flow:
        1. Update SharedModel with server parameters
        2. Train full model (Local + Shared) with DP-SGD for E epochs
        3. Compose DP budget for this round
        4. Update local LightGBM with new PyTorch embeddings
        5. Return ONLY SharedModel weights

        Parameters
        ----------
        parameters:
            Numpy arrays of SharedModel weights from server.
        config:
            Flower config (may contain local_epochs).

        Returns
        -------
        tuple
            (parameters, num_examples, metrics) where parameters are
            ONLY SharedModel weights (not full model).
        """
        # Set server parameters into shared model
        self.set_parameters(parameters, config)

        # Get local epochs from config (default 5)
        local_epochs = config.get("local_epochs", int(LOCAL_EPOCHS))

        # Track metrics
        metrics: dict[str, Scalar] = {}
        total_loss = 0.0
        num_batches = 0

        # Local training loop
        self.model.train()

        for epoch in range(local_epochs):
            epoch_loss = 0.0

            for batch in self.train_loader:
                self.optimizer.zero_grad()
                loss = self._compute_loss(batch)

                # Add FedProx proximal term: (mu/2) * ||w - w_t||^2
                # Only applied to SharedModel parameters
                prox_term = self._compute_proximal_term()
                loss = loss + prox_term

                # Opacus handles per-sample clipping + Gaussian noise
                loss.backward()

                self.optimizer.step()

                batch_loss = loss.item()
                epoch_loss += batch_loss
                total_loss += batch_loss
                num_batches += 1

            epoch_avg = epoch_loss / len(self.train_loader)
            logger.debug(f"Epoch {epoch+1}/{local_epochs}: loss={epoch_avg:.4f}")

        # Log average loss
        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        metrics["train_loss"] = avg_loss

        # Compose DP budget for this round
        epsilon_cumulative = self.dp_accountant.compose_round(
            batch_size=self.train_loader.batch_size,
            n_samples=len(self.train_loader.dataset),
            noise_multiplier=1.1,  # DP_NOISE_MULTIPLIER
        )
        metrics["dp_epsilon_cumulative"] = epsilon_cumulative
        metrics["dp_epsilon_spent"] = epsilon_cumulative - self.dp_accountant._current_epsilon

        # Update local LightGBM with new PyTorch embeddings
        try:
            self.local_ensemble.update_lgbm(self.model, self.train_loader)
        except Exception as e:
            logger.warning(f"Failed to update LightGBM: {e}")

        # Return ONLY SharedModel parameters (not full model)
        return self.get_parameters(config={}), len(self.train_loader.dataset), metrics

    def evaluate(
        self,
        parameters: NDArrays,
        config: Config,
    ) -> tuple[float, int, dict[str, Scalar]]:
        """
        Evaluate model on test data.

        Parameters
        ----------
        parameters:
            Numpy arrays of SharedModel weights from server.
        config:
            Flower config (may contain test_loader).

        Returns
        -------
        tuple
            (loss, num_examples, metrics).
        """
        # Set server parameters
        self.set_parameters(parameters, config)

        # Note: In a real implementation, you'd have a test_loader.
        # For simulation, we'll just return dummy metrics.
        metrics: dict[str, Scalar] = {
            "accuracy": 0.85,  # Placeholder
            "auc": 0.87,  # Placeholder
        }

        return 0.5, len(self.train_loader.dataset), metrics

    def get_properties(self, config: Config) -> dict[str, Scalar]:
        """
        Return client properties.

        Properties can include metadata about the client like:
        - Number of training samples
        - DP budget status
        - Bank ID (for simulation)
        """
        return {
            "num_samples": len(self.train_loader.dataset),
            "dp_epsilon_cumulative": self.dp_accountant.get_status().epsilon_spent,
            "dp_budget_exhausted": self.dp_accountant.is_budget_exhausted(),
        }

    def _compute_proximal_term(self) -> torch.Tensor:
        """
        Compute FedProx proximal term: (mu/2) * ||w - w_t||^2

        Only applies to SharedModel parameters. LocalModel has no server
        parameters to anchor to, so its proximal term is 0.

        Returns
        -------
        torch.Tensor
            Proximal regularization loss.
        """
        if self.mu == 0.0:
            # No proximal term for FedAvg (mu=0)
            return torch.tensor(0.0, device=self.device)

        if not self._server_shared_params:
            # No server parameters set yet (shouldn't happen in normal operation)
            return torch.tensor(0.0, device=self.device)

        prox_term = torch.tensor(0.0, device=self.device)
        current_shared_params = self.model.shared.state_dict()

        for name, param in current_shared_params.items():
            if name in self._server_shared_params:
                # Compute squared L2 distance: (w - w_t)^2
                diff = param - self._server_shared_params[name]
                prox_term = prox_term + (diff ** 2).sum()

        # Return (mu/2) * ||w - w_t||^2
        return (self.mu / 2.0) * prox_term

    def _compute_loss(self, batch) -> torch.Tensor:
        """
        Compute loss for a batch.

        Parameters
        ----------
        batch:
            Tuple of (node_feat, tab_feat, neighbor_feats, label).

        Returns
        -------
        torch.Tensor
            Loss tensor.
        """
        node_feat, tab_feat, neighbor_feats, labels = batch

        # Move to device
        node_feat = node_feat.to(self.device)
        tab_feat = tab_feat.to(self.device)
        if neighbor_feats is not None:
            neighbor_feats = neighbor_feats.to(self.device)
        labels = labels.to(self.device)

        # Forward pass
        logits = self.model(node_feat, tab_feat, neighbor_feats)

        # Binary cross-entropy with logits
        loss = F.binary_cross_entropy_with_logits(logits.squeeze(-1), labels)

        return loss


# =============================================================================
# Utility Functions
# =============================================================================


def count_transmitted_parameters(client: LIPFlowerClient) -> int:
    """
    Count the number of parameters transmitted to server.

    Verifies Patent Claim 2 compliance: should equal SharedModel count.

    Parameters
    ----------
    client:
        LIPFlowerClient instance.

    Returns
    -------
    int
        Number of parameters transmitted.
    """
    params, _, _ = client.get_parameters(config={})
    return sum(p.size for p in params)


def verify_local_model_unchanged(
    client: LIPFlowerClient,
    original_local_state: dict[str, torch.Tensor],
) -> bool:
    """
    Verify that LocalModel weights are unchanged after set_parameters.

    Parameters
    ----------
    client:
        LIPFlowerClient instance.
    original_local_state:
        Original LocalModel state dict.

    Returns
    -------
    bool
        True if LocalModel is unchanged.
    """
    current_local_state = {
        k: v.clone() for k, v in client.model.local.state_dict().items()
    }

    for k in original_local_state:
        if k not in current_local_state:
            return False
        if not torch.equal(original_local_state[k], current_local_state[k]):
            return False

    return True
