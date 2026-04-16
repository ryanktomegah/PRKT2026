"""
P4 Federated Learning — Model Splitting Architecture

Implements model splitting for federated learning where:
- LocalModel: Never transmitted (stays at each bank)
- SharedModel: Federated via Flower (aggregated across consortium)
- FederatedModel: Opacus-compatible wrapper (unified for DP-SGD, split for FL)

Patent Claim 2 Compliance: "only weights of the final aggregation layers
are shared across the consortium" — literally satisfied by this architecture.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

# Import existing GraphSAGE and TabTransformer components
from lip.c1_failure_classifier.graphsage_torch import (
    GRAPHSAGE_HIDDEN_DIM,
    GRAPHSAGE_INPUT_DIM,
    GRAPHSAGE_OUTPUT_DIM,
)
from lip.c1_failure_classifier.tabtransformer_torch import (
    TABTRANSFORMER_EMBED_DIM,
    TABTRANSFORMER_INPUT_DIM,
    TABTRANSFORMER_NUM_HEADS,
    TABTRANSFORMER_NUM_LAYERS,
    TabTransformerTorch,
)

# Compute model dim from embed dim and num heads
TABTRANSFORMER_MODEL_DIM = TABTRANSFORMER_NUM_HEADS * TABTRANSFORMER_EMBED_DIM

logger = logging.getLogger(__name__)


# =============================================================================
# LocalModel — Never Transmitted (Stays at Each Bank)
# =============================================================================


class LocalModel(nn.Module):
    """
    Local model components that never leave the bank.

    Encodes institution-specific topology and borrower identifiers:
    - GraphSAGE layers 1-2: Capture local counterparty topology
    - TabTransformer embedding: Map tabular features to model dimension

    These weights are NEVER transmitted in federated learning, satisfying
    Patent Claim 2's "only weights of the final aggregation layers are shared."

    Parameters
    ----------
    graphsage_input_dim:
        GraphSAGE node feature dimension (default 8).
    graphsage_hidden_dim:
        GraphSAGE hidden layer dimension (default 256).
    tabtransformer_input_dim:
        TabTransformer input dimension (default 88).
    tabtransformer_embed_dim:
        TabTransformer embedding dimension (default 256).
    """

    def __init__(
        self,
        graphsage_input_dim: int = GRAPHSAGE_INPUT_DIM,
        graphsage_hidden_dim: int = GRAPHSAGE_HIDDEN_DIM,
        tabtransformer_input_dim: int = TABTRANSFORMER_INPUT_DIM,
        tabtransformer_embed_dim: int = TABTRANSFORMER_MODEL_DIM,
    ) -> None:
        super().__init__()
        self.graphsage_input_dim = graphsage_input_dim
        self.graphsage_hidden_dim = graphsage_hidden_dim
        self.tabtransformer_embed_dim = tabtransformer_embed_dim

        # GraphSAGE Layer 1: (8 + 8) → 256 (concat self + agg neighbors)
        self.gsage_layer1 = nn.Linear(2 * graphsage_input_dim, graphsage_hidden_dim)

        # GraphSAGE Layer 2: (256 + 256) → 384 (concat layer1_out + agg neighbors)
        # We'll concat layer 1 output with aggregated layer 1 neighbor outputs
        # The aggregation of layer 1 neighbor outputs gives us 256-dim
        self.gsage_layer2 = nn.Linear(2 * graphsage_hidden_dim, GRAPHSAGE_OUTPUT_DIM)

        # TabTransformer embedding: 88 → 256
        self.tab_transformer_embed = nn.Linear(
            tabtransformer_input_dim, tabtransformer_embed_dim
        )

        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier-uniform initialization (matches existing models)."""
        nn.init.xavier_uniform_(self.gsage_layer1.weight)
        nn.init.zeros_(self.gsage_layer1.bias)
        nn.init.xavier_uniform_(self.gsage_layer2.weight)
        nn.init.zeros_(self.gsage_layer2.bias)
        nn.init.xavier_uniform_(self.tab_transformer_embed.weight)
        nn.init.zeros_(self.tab_transformer_embed.bias)

    def forward(
        self,
        node_feat: torch.Tensor,
        tab_feat: torch.Tensor,
        neighbor_feats: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass through local components only.

        Parameters
        ----------
        node_feat:
            Node features, shape (B, 8).
        tab_feat:
            Tabular features, shape (B, 88).
        neighbor_feats:
            Optional neighbor features for GraphSAGE aggregation.
            Shape (B, k, 8) where k is number of neighbors.

        Returns
        -------
        tuple[torch.Tensor, torch.Tensor]
            - GraphSAGE layer 2 output (B, 384)
            - TabTransformer embedding (B, 256)
        """
        B = node_feat.shape[0]
        device = node_feat.device

        # === GraphSAGE Layer 1 ===
        # Layer 1 aggregation: mean-pool raw neighbor features
        if neighbor_feats is None:
            agg1 = torch.zeros(B, self.graphsage_input_dim, device=device, dtype=node_feat.dtype)
        else:
            k = neighbor_feats.shape[1]
            agg1 = neighbor_feats.mean(dim=1)  # (B, 8)

        h1 = F.relu(self.gsage_layer1(torch.cat([node_feat, agg1], dim=1)))  # (B, 256)
        h1 = F.normalize(h1, p=2, dim=1)

        # === GraphSAGE Layer 2 ===
        # For layer 2, we need to aggregate layer 1 outputs of neighbors
        # Apply layer 1 to each neighbor's features
        if neighbor_feats is None:
            agg2 = torch.zeros(B, self.graphsage_hidden_dim, device=device, dtype=h1.dtype)
        else:
            k = neighbor_feats.shape[1]
            nbr_flat = neighbor_feats.reshape(B * k, self.graphsage_input_dim)  # (B*k, 8)
            zeros_nbr = torch.zeros(
                B * k, self.graphsage_input_dim, device=device, dtype=nbr_flat.dtype
            )
            h1_nbr = F.relu(
                self.gsage_layer1(torch.cat([nbr_flat, zeros_nbr], dim=1))
            )  # (B*k, 256)
            h1_nbr = F.normalize(h1_nbr, p=2, dim=1)
            agg2 = h1_nbr.reshape(B, k, self.graphsage_hidden_dim).mean(dim=1)  # (B, 256)

        h2 = F.relu(self.gsage_layer2(torch.cat([h1, agg2], dim=1)))  # (B, 384)
        h2 = F.normalize(h2, p=2, dim=1)

        # === TabTransformer Embedding ===
        # Extract tabular features (skip first 8 dims which are node features)
        tab_feat_only = tab_feat[:, self.graphsage_input_dim:]  # (B, 80)
        # Concatenate node features for full 88-dim input (consistent with original)
        tab_feat_full = torch.cat([node_feat, tab_feat_only], dim=1)  # (B, 88)
        tab_emb = self.tab_transformer_embed(tab_feat_full)  # (B, 256)

        return h2, tab_emb


# =============================================================================
# SharedModel — Federated via Flower (Aggregated Across Consortium)
# =============================================================================


class SharedModel(nn.Module):
    """
    Shared model components federated via Flower.

    Encodes cross-bank failure patterns:
    - GraphSAGE final aggregation layer: Combines local and shared representations
    - TabTransformer encoder: Full 4-layer transformer (shared attention patterns)
    - MLP head: Final classification layer (shared decision boundary)

    These weights ARE transmitted in federated learning, aggregated across
    consortium banks via FedProx strategy.

    Parameters
    ----------
    graphsage_output_dim:
        GraphSAGE layer 2 output dimension (default 384).
    tabtransformer_embed_dim:
        TabTransformer embedding dimension (default 256).
    tabtransformer_num_layers:
        Number of transformer encoder layers (default 4).
    tabtransformer_num_heads:
        Number of attention heads (default 8).
    mlp_hidden1, mlp_hidden2:
        MLP head hidden layer sizes.
    """

    def __init__(
        self,
        graphsage_output_dim: int = GRAPHSAGE_OUTPUT_DIM,
        tabtransformer_embed_dim: int = TABTRANSFORMER_MODEL_DIM,
        tabtransformer_num_layers: int = TABTRANSFORMER_NUM_LAYERS,
        tabtransformer_num_heads: int = TABTRANSFORMER_NUM_HEADS,
        mlp_hidden1: int = 256,
        mlp_hidden2: int = 64,
    ) -> None:
        super().__init__()
        self.graphsage_output_dim = graphsage_output_dim
        self.tabtransformer_embed_dim = tabtransformer_embed_dim
        self.combined_input_dim = graphsage_output_dim + tabtransformer_embed_dim

        # GraphSAGE final aggregation layer: (384 + 256) → 384
        # Concatenates GraphSAGE L2 output with TabTransformer embedding
        self.gsage_final = nn.Linear(self.combined_input_dim, graphsage_output_dim)

        # TabTransformer encoder: 4 layers of self-attention
        self.tab_transformer_enc = TabTransformerTorch(
            input_dim=tabtransformer_embed_dim,
            num_layers=tabtransformer_num_layers,
            num_heads=tabtransformer_num_heads,
            output_dim=tabtransformer_embed_dim,
        )

        # MLP head: 640 → 256 → 64 → 1
        self.mlp_fc1 = nn.Linear(self.combined_input_dim, mlp_hidden1)
        self.mlp_fc2 = nn.Linear(mlp_hidden1, mlp_hidden2)
        self.mlp_fc3 = nn.Linear(mlp_hidden2, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier-uniform initialization."""
        nn.init.xavier_uniform_(self.gsage_final.weight)
        nn.init.zeros_(self.gsage_final.bias)
        nn.init.xavier_uniform_(self.mlp_fc1.weight)
        nn.init.zeros_(self.mlp_fc1.bias)
        nn.init.xavier_uniform_(self.mlp_fc2.weight)
        nn.init.zeros_(self.mlp_fc2.bias)
        nn.init.xavier_uniform_(self.mlp_fc3.weight)
        nn.init.zeros_(self.mlp_fc3.bias)

    def forward(
        self,
        gsage_h2: torch.Tensor,
        tab_emb: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass through shared components.

        Parameters
        ----------
        gsage_h2:
            GraphSAGE layer 2 output from LocalModel, shape (B, 384).
        tab_emb:
            TabTransformer embedding from LocalModel, shape (B, 256).

        Returns
        -------
        torch.Tensor
            Raw logits, shape (B, 1). Apply sigmoid externally for probabilities.
        """
        # === GraphSAGE Final Aggregation ===
        # Concatenate local GraphSAGE L2 output with TabTransformer embedding
        gsage_final = self.gsage_final(torch.cat([gsage_h2, tab_emb], dim=1))  # (B, 384)
        gsage_final = F.normalize(gsage_final, p=2, dim=1)

        # === TabTransformer Encoder ===
        # Pass embedding through full transformer
        tab_enc = self.tab_transformer_enc(tab_emb)  # (B, 256)

        # === MLP Head ===
        fused = torch.cat([gsage_final, tab_enc], dim=1)  # (B, 640)
        h1 = F.relu(self.mlp_fc1(fused))  # (B, 256)
        h2 = F.relu(self.mlp_fc2(h1))  # (B, 64)
        logits = self.mlp_fc3(h2)  # (B, 1)

        return logits


# =============================================================================
# FederatedModel — Opacus-Compatible Wrapper
# =============================================================================


class FederatedModel(nn.Module):
    """
    Unified module for DP-SGD; split for FL transmission.

    **Purpose**: Reconciles two competing constraints:
    1. Opacus PrivacyEngine requires a single nn.Module for per-sample gradients
    2. Federated learning requires partial parameter transmission (only shared weights)

    **Solution**: Wrap LocalModel + SharedModel in single nn.Module for training,
    but slice state_dict for Flower transmission (only shared weights).

    **Elegant Alignment**: Because LIPFlowerClient only returns SharedModel weights,
    Flower's FedProx strategy calculates proximal penalty based only on shared
    parameters. Local layers have no global w_t to anchor to, so they naturally
    have a proximal term of 0. No custom strategy required.

    Parameters
    ----------
    local_model:
        LocalModel instance (never transmitted).
    shared_model:
        SharedModel instance (federated via Flower).
    """

    local: LocalModel
    shared: SharedModel

    def __init__(self, local_model: LocalModel, shared_model: SharedModel) -> None:
        super().__init__()
        self.local = local_model
        self.shared = shared_model

    def forward(
        self,
        node_feat: torch.Tensor,
        tab_feat: torch.Tensor,
        neighbor_feats: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Full forward pass through local → shared components.

        Required for DP-SGD to compute per-sample gradients end-to-end.

        Parameters
        ----------
        node_feat:
            Node features, shape (B, 8).
        tab_feat:
            Tabular features, shape (B, 88).
        neighbor_feats:
            Optional neighbor features for GraphSAGE aggregation.
            Shape (B, k, 8) where k is number of neighbors.

        Returns
        -------
        torch.Tensor
            Raw logits, shape (B, 1).
        """
        # Local model forward: GraphSAGE L1-2 + TabTransformer embed
        h2, tab_emb = self.local(node_feat, tab_feat, neighbor_feats)

        # Shared model forward: GraphSAGE final + TT enc + MLP head
        return self.shared(h2, tab_emb)


# =============================================================================
# Utility Functions
# =============================================================================


def count_parameters(model: nn.Module, only_trainable: bool = True) -> int:
    """
    Count the number of parameters in a model.

    Parameters
    ----------
    model:
        PyTorch model.
    only_trainable:
        If True, only count trainable parameters.

    Returns
    -------
    int
        Number of parameters.
    """
    return sum(
        p.numel()
        for p in model.parameters()
        if not only_trainable or p.requires_grad
    )


def get_shared_parameter_count() -> int:
    """
    Get the expected number of shared parameters for validation.

    Used to verify Patent Claim 2 compliance: only shared layers transmitted.

    Returns
    -------
    int
        Expected number of shared parameters.
    """
    shared = SharedModel()
    return count_parameters(shared)


def get_local_parameter_count() -> int:
    """
    Get the number of local parameters (never transmitted).

    Returns
    -------
    int
        Number of local parameters.
    """
    local = LocalModel()
    return count_parameters(local)


def get_total_parameter_count() -> int:
    """
    Get total parameters (local + shared).

    Returns
    -------
    int
        Total number of parameters.
    """
    local = LocalModel()
    shared = SharedModel()
    federated = FederatedModel(local, shared)
    return count_parameters(federated)
