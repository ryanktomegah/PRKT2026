"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

graphsage_torch.py — PyTorch GraphSAGE 2-layer model
Mirrors graphsage.py but uses nn.Module for DataLoader + GPU support.
C1 Spec Section 5 — empty-neighbour training (zeros aggregation).
Output: 384-dimensional corridor embedding.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Dimension constants (mirror graphsage.py)
# ---------------------------------------------------------------------------

GRAPHSAGE_INPUT_DIM: int = 8
GRAPHSAGE_HIDDEN_DIM: int = 256
GRAPHSAGE_OUTPUT_DIM: int = 384


# ---------------------------------------------------------------------------
# GraphSAGETorch
# ---------------------------------------------------------------------------


class GraphSAGETorch(nn.Module):
    """2-layer GraphSAGE (PyTorch) with empty-neighbour (zero) aggregation.

    During training, neighbour lists are empty — the aggregated vector is
    always zero.  The forward pass therefore computes:

    - Layer 1:  ``cat([x, zeros(B,8)])``   → ``Linear(16,256)`` → ReLU → L2-norm
    - Layer 2:  ``cat([h1, zeros(B,256)])`` → ``Linear(512,384)`` → ReLU → L2-norm

    Xavier-uniform initialisation matches the NumPy reference implementation.

    Parameters
    ----------
    input_dim:
        Raw node feature dimensionality (default 8).
    hidden_dim:
        Hidden representation size after layer 1 (default 256).
    output_dim:
        Final embedding size (default 384).
    """

    def __init__(
        self,
        input_dim: int = GRAPHSAGE_INPUT_DIM,
        hidden_dim: int = GRAPHSAGE_HIDDEN_DIM,
        output_dim: int = GRAPHSAGE_OUTPUT_DIM,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # Layer 1: concat(self[8], agg_nbr[8]) → 256
        self.layer1 = nn.Linear(2 * input_dim, hidden_dim)
        # Layer 2: concat(h1[256], agg_nbr[256]) → 384
        self.layer2 = nn.Linear(2 * hidden_dim, output_dim)

        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier-uniform initialisation (matches NumPy _xavier_uniform)."""
        nn.init.xavier_uniform_(self.layer1.weight)
        nn.init.zeros_(self.layer1.bias)
        nn.init.xavier_uniform_(self.layer2.weight)
        nn.init.zeros_(self.layer2.bias)

    def forward(
        self,
        x: torch.Tensor,
        neighbor_feats: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute the 384-dim GraphSAGE embedding for a batch of nodes.

        Parameters
        ----------
        x:
            Node feature tensor of shape ``(B, 8)``.
        neighbor_feats:
            Optional neighbor feature tensor of shape ``(B, k, 8)``.
            When ``None``, zero aggregation (empty-neighbour path) is used —
            identical to the legacy single-argument call, preserving checkpoint
            compatibility (weight shapes are unchanged).

        Returns
        -------
        torch.Tensor
            Shape ``(B, 384)``, L2-normalised along dim=1.
        """
        B = x.shape[0]
        device = x.device

        # Layer 1 aggregation: mean-pool raw neighbor features
        if neighbor_feats is None:
            agg1 = torch.zeros(B, self.input_dim, device=device, dtype=x.dtype)
        else:
            agg1 = neighbor_feats.mean(dim=1)  # (B, 8)

        h1 = F.relu(self.layer1(torch.cat([x, agg1], dim=1)))  # (B, 256)
        h1 = F.normalize(h1, p=2, dim=1)

        # Layer 2 aggregation: apply layer1 to each neighbor's raw features,
        # then mean-pool the resulting hidden representations
        if neighbor_feats is None:
            agg2 = torch.zeros(B, self.hidden_dim, device=device, dtype=x.dtype)
        else:
            k = neighbor_feats.shape[1]
            nbr_flat = neighbor_feats.reshape(B * k, self.input_dim)  # (B*k, 8)
            zeros_nbr = torch.zeros(B * k, self.input_dim, device=device, dtype=x.dtype)
            h1_nbr = F.relu(self.layer1(torch.cat([nbr_flat, zeros_nbr], dim=1)))  # (B*k, 256)
            h1_nbr = F.normalize(h1_nbr, p=2, dim=1)
            agg2 = h1_nbr.reshape(B, k, self.hidden_dim).mean(dim=1)  # (B, 256)

        h2 = F.relu(self.layer2(torch.cat([h1, agg2], dim=1)))  # (B, 384)
        h2 = F.normalize(h2, p=2, dim=1)

        return h2
