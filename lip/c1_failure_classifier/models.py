"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

models.py — PyTorch C1 Failure Classifier models
C1 Spec Sections 5, 6, 7

Contains:
  GraphSAGEEncoder  — 2-layer GraphSAGE (SAGEConv, MEAN aggregator)
  TabTransformerEncoder — Categorical embedding + transformer + continuous passthrough
  C1Model           — Combined model: GraphSAGE + TabTransformer + MLP head
  AsymmetricBCELoss — α-weighted BCE loss (α=0.7 default)

All classes fall back gracefully when CUDA is unavailable.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy torch imports — graceful fallback when PyTorch is not installed
# ---------------------------------------------------------------------------

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch import Tensor

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TORCH_AVAILABLE = False
    logger.warning(
        "PyTorch not installed — lip.c1_failure_classifier.models will not "
        "be functional.  Install with: pip install 'lip[gnn]'"
    )

try:
    from torch_geometric.nn import SAGEConv  # type: ignore[import-untyped]

    _PYG_AVAILABLE = True
except ImportError:
    _PYG_AVAILABLE = False
    logger.info(
        "torch-geometric not installed — GraphSAGEEncoder unavailable. "
        "Install with: pip install 'lip[gnn]'"
    )


def _check_torch() -> None:
    """Raise if torch is not available."""
    if not _TORCH_AVAILABLE:
        raise ImportError(
            "PyTorch is required for models.py. Install with: pip install 'lip[gnn]'"
        )


# ---------------------------------------------------------------------------
# GraphSAGEEncoder — C1 Spec Section 5
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class GraphSAGEEncoder(nn.Module):
        """2-layer GraphSAGE encoder with MEAN aggregation.

        C1 Spec Section 5:
        - Layer 1: in_channels=28 → hidden=128, ReLU
        - Layer 2: hidden=128 → out_channels=128, ReLU
        - L2-normalised output embeddings
        - Edge representation: Linear(128+128+26 → 128)

        Parameters
        ----------
        in_channels : int
            Node feature dimensionality (default 28).
        hidden_channels : int
            Hidden layer size (default 128).
        out_channels : int
            Output embedding size (default 128).
        edge_dim : int
            Edge attribute dimensionality (default 26).
        """

        def __init__(
            self,
            in_channels: int = 28,
            hidden_channels: int = 128,
            out_channels: int = 128,
            edge_dim: int = 26,
        ) -> None:
            super().__init__()
            self.in_channels = in_channels
            self.hidden_channels = hidden_channels
            self.out_channels = out_channels
            self.edge_dim = edge_dim

            if _PYG_AVAILABLE:
                self.conv1 = SAGEConv(in_channels, hidden_channels, aggr="mean")
                self.conv2 = SAGEConv(hidden_channels, out_channels, aggr="mean")
            else:
                # Fallback linear layers when torch-geometric is not installed
                self.conv1_linear = nn.Linear(in_channels, hidden_channels)
                self.conv2_linear = nn.Linear(hidden_channels, out_channels)

            # Edge representation: concat(sender_emb, receiver_emb, edge_attr)
            self.edge_mlp = nn.Linear(
                out_channels + out_channels + edge_dim, out_channels
            )

        def forward(
            self,
            x: Tensor,
            edge_index: Tensor,
            edge_attr: Optional[Tensor] = None,
        ) -> tuple[Tensor, Tensor]:
            """Forward pass producing node and corridor edge embeddings.

            Parameters
            ----------
            x : Tensor
                Node features of shape ``[N, in_channels]``.
            edge_index : Tensor
                Edge connectivity ``[2, E]``.
            edge_attr : Tensor, optional
                Edge features ``[E, edge_dim]``.

            Returns
            -------
            tuple[Tensor, Tensor]
                - ``node_embeddings`` of shape ``[N, out_channels]``
                - ``corridor_edge_emb`` of shape ``[E, out_channels]``
            """
            if _PYG_AVAILABLE:
                h = F.relu(self.conv1(x, edge_index))
                h = F.relu(self.conv2(h, edge_index))
            else:
                # Fallback: ignore graph structure, just transform features
                h = F.relu(self.conv1_linear(x))
                h = F.relu(self.conv2_linear(h))

            # L2 normalise node embeddings
            node_embeddings = F.normalize(h, p=2, dim=-1)

            # Build corridor edge embeddings
            if edge_attr is None:
                edge_attr = torch.zeros(
                    edge_index.size(1), self.edge_dim, device=x.device
                )

            sender_emb = node_embeddings[edge_index[0]]    # [E, out_channels]
            receiver_emb = node_embeddings[edge_index[1]]   # [E, out_channels]
            edge_input = torch.cat(
                [sender_emb, receiver_emb, edge_attr], dim=-1
            )  # [E, out_channels*2 + edge_dim]
            corridor_edge_emb = self.edge_mlp(edge_input)   # [E, out_channels]

            return node_embeddings, corridor_edge_emb

    # -----------------------------------------------------------------------
    # TabTransformerEncoder — C1 Spec Section 6
    # -----------------------------------------------------------------------

    class TabTransformerEncoder(nn.Module):
        """Categorical-embedding TabTransformer for tabular features.

        C1 Spec Section 6:
        - 8 categorical features, each embedded to dim=32
        - 4 transformer layers, 8 heads, d_model=256, ffn_dim=128
        - 8 continuous features passed through directly
        - Output: LayerNorm(transformer[256]) || continuous[8] → Linear(264→88)

        Parameters
        ----------
        vocab_sizes : dict[str, int]
            Vocabulary size for each categorical feature.
        embed_dim : int
            Per-feature embedding dimension (default 32).
        num_layers : int
            Transformer encoder layers (default 4).
        num_heads : int
            Attention heads per layer (default 8).
        ffn_dim : int
            Feed-forward inner dimension (default 128).
        n_cont : int
            Number of continuous features (default 8).
        output_dim : int
            Output dimensionality (default 88).
        dropout : float
            Dropout rate in transformer (default 0.1).
        """

        # Default vocabulary sizes per C1 spec
        DEFAULT_VOCAB_SIZES: Dict[str, int] = {
            "rejection_code": 64,
            "amount_tier": 4,
            "currency_pair": 128,
            "sender_country": 64,
            "receiver_country": 64,
            "rejection_code_class": 4,
            "is_month_end": 2,
            "is_quarter_end": 2,
        }

        def __init__(
            self,
            vocab_sizes: Optional[Dict[str, int]] = None,
            embed_dim: int = 32,
            num_layers: int = 4,
            num_heads: int = 8,
            ffn_dim: int = 128,
            n_cont: int = 8,
            output_dim: int = 88,
            dropout: float = 0.1,
        ) -> None:
            super().__init__()

            self.vocab_sizes = vocab_sizes or self.DEFAULT_VOCAB_SIZES
            self.embed_dim = embed_dim
            self.n_cont = n_cont
            self.output_dim = output_dim
            self.cat_feature_names = list(self.vocab_sizes.keys())
            n_cat = len(self.cat_feature_names)

            # d_model = n_cat * embed_dim
            d_model = n_cat * embed_dim  # 8 * 32 = 256

            # Per-feature embeddings
            self.embeddings = nn.ModuleDict(
                {
                    name: nn.Embedding(vs, embed_dim)
                    for name, vs in self.vocab_sizes.items()
                }
            )

            # Transformer encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=num_heads,
                dim_feedforward=ffn_dim,
                dropout=dropout,
                activation="gelu",
                batch_first=True,
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer, num_layers=num_layers
            )

            # Output layer norm and projection
            self.layer_norm = nn.LayerNorm(d_model)
            self.output_proj = nn.Linear(d_model + n_cont, output_dim)

        def forward(
            self,
            cat_features: Dict[str, Tensor],
            cont_features: Tensor,
        ) -> Tensor:
            """Forward pass.

            Parameters
            ----------
            cat_features : dict[str, Tensor]
                Mapping of feature name → integer index tensor ``[B]``.
            cont_features : Tensor
                Continuous features ``[B, n_cont]``.

            Returns
            -------
            Tensor
                Output representation ``[B, output_dim]``.
            """
            # Embed each categorical feature → [B, embed_dim]
            embedded = []
            for name in self.cat_feature_names:
                idx = cat_features[name]
                embedded.append(self.embeddings[name](idx))

            # Concatenate embeddings → [B, n_cat * embed_dim] = [B, 256]
            cat_emb = torch.cat(embedded, dim=-1)

            # Transformer expects [B, seq_len, d_model]; treat as single-token
            cat_emb = cat_emb.unsqueeze(1)  # [B, 1, 256]
            trans_out = self.transformer(cat_emb)  # [B, 1, 256]
            trans_out = trans_out.squeeze(1)  # [B, 256]
            trans_out = self.layer_norm(trans_out)

            # Concatenate with continuous features
            combined = torch.cat([trans_out, cont_features], dim=-1)  # [B, 264]
            return self.output_proj(combined)  # [B, 88]

    # -----------------------------------------------------------------------
    # AsymmetricBCELoss — C1 Spec Section 7.3
    # -----------------------------------------------------------------------

    class AsymmetricBCELoss(nn.Module):
        """Asymmetric binary cross-entropy loss.

        C1 Spec Section 7.3:
        loss = -(alpha * y * log(p) + (1 - alpha) * (1 - y) * log(1 - p))

        With alpha = 0.7, false negatives (missed failures) are penalised
        more heavily than false positives.

        Parameters
        ----------
        alpha : float
            Weight for the positive class (default 0.7).
        """

        def __init__(self, alpha: float = 0.7) -> None:
            super().__init__()
            self.alpha = alpha

        def forward(self, y_pred: Tensor, y_true: Tensor) -> Tensor:
            """Compute asymmetric BCE loss.

            Parameters
            ----------
            y_pred : Tensor
                Predicted probabilities in ``(0, 1)``, shape ``[B]`` or ``[B, 1]``.
            y_true : Tensor
                Ground-truth labels (0 or 1), shape ``[B]`` or ``[B, 1]``.

            Returns
            -------
            Tensor
                Scalar loss value.
            """
            y_pred = y_pred.view(-1)
            y_true = y_true.view(-1).float()
            eps = 1e-7
            p = y_pred.clamp(eps, 1.0 - eps)
            loss = -(
                self.alpha * y_true * torch.log(p)
                + (1.0 - self.alpha) * (1.0 - y_true) * torch.log(1.0 - p)
            )
            return loss.mean()

    # -----------------------------------------------------------------------
    # C1Model — C1 Spec Section 7
    # -----------------------------------------------------------------------

    class C1Model(nn.Module):
        """Combined C1 Failure Classifier (PyTorch).

        Architecture (C1 Spec Section 7):
        - Input: graph_context [B, 384] = sender[128] + receiver[128] + corridor[128]
                 tabular_output [B, 88]  from TabTransformerEncoder
        - Combined: concat → [B, 472]
        - MLP head:
            Linear(472 → 256) + ReLU + Dropout(0.2)
            Linear(256 → 64)  + ReLU + Dropout(0.2)
            Linear(64  → 1)   + Sigmoid

        Parameters
        ----------
        graph_dim : int
            Graph context dimensionality (default 384).
        tab_dim : int
            TabTransformer output dimensionality (default 88).
        dropout : float
            Dropout rate in MLP head (default 0.2).
        """

        def __init__(
            self,
            graph_dim: int = 384,
            tab_dim: int = 88,
            dropout: float = 0.2,
        ) -> None:
            super().__init__()
            combined_dim = graph_dim + tab_dim  # 472

            self.mlp = nn.Sequential(
                nn.Linear(combined_dim, 256),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(256, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, 1),
                nn.Sigmoid(),
            )

        def forward(
            self,
            graph_context: Tensor,
            tabular_output: Tensor,
        ) -> Tensor:
            """Compute failure probability.

            Parameters
            ----------
            graph_context : Tensor
                Graph context ``[B, 384]`` = concat(sender_emb, receiver_emb, corridor_emb).
            tabular_output : Tensor
                TabTransformer output ``[B, 88]``.

            Returns
            -------
            Tensor
                Failure probability ``[B, 1]``.
            """
            combined = torch.cat([graph_context, tabular_output], dim=-1)  # [B, 472]
            return self.mlp(combined)  # [B, 1]

else:
    # Stubs when PyTorch is not available — allows import without crash
    class GraphSAGEEncoder:  # type: ignore[no-redef]
        """Stub: PyTorch not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install 'lip[gnn]'")

    class TabTransformerEncoder:  # type: ignore[no-redef]
        """Stub: PyTorch not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install 'lip[gnn]'")

    class C1Model:  # type: ignore[no-redef]
        """Stub: PyTorch not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install 'lip[gnn]'")

    class AsymmetricBCELoss:  # type: ignore[no-redef]
        """Stub: PyTorch not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required. Install with: pip install 'lip[gnn]'")
