"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

model_torch.py — PyTorch combined C1 classifier
GraphSAGETorch[384] + TabTransformerTorch[88] → 472-dim → MLPHeadTorch → logit
C1 Spec Section 7.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .graphsage_torch import GRAPHSAGE_OUTPUT_DIM, GraphSAGETorch
from .tabtransformer_torch import TABTRANSFORMER_INPUT_DIM, TabTransformerTorch

logger = logging.getLogger(__name__)

_COMBINED_DIM: int = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_INPUT_DIM  # 472


# ---------------------------------------------------------------------------
# MLPHeadTorch
# ---------------------------------------------------------------------------


class MLPHeadTorch(nn.Module):
    """MLP head that maps the 472-dim fused embedding to a single logit.

    Architecture:
        472 → Linear(256) → ReLU → Linear(64) → ReLU → Linear(1)

    Returns raw logits (no sigmoid).  Use ``torch.sigmoid`` at inference time
    or ``BCEWithLogitsLoss`` during training.

    Parameters
    ----------
    input_dim:
        Dimensionality of the concatenated GraphSAGE + TabTransformer vector.
    hidden1, hidden2:
        Hidden layer sizes.
    """

    def __init__(
        self,
        input_dim: int = _COMBINED_DIM,
        hidden1: int = 256,
        hidden2: int = 64,
    ) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden1)
        self.fc2 = nn.Linear(hidden1, hidden2)
        self.fc3 = nn.Linear(hidden2, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.zeros_(self.fc1.bias)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.zeros_(self.fc2.bias)
        nn.init.xavier_uniform_(self.fc3.weight)
        nn.init.zeros_(self.fc3.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute logits for a batch of fused feature vectors.

        Parameters
        ----------
        x:
            Shape ``(B, 472)``.

        Returns
        -------
        torch.Tensor
            Shape ``(B, 1)`` — raw logits (no sigmoid applied).
        """
        h = F.relu(self.fc1(x))
        h = F.relu(self.fc2(h))
        return self.fc3(h)


# ---------------------------------------------------------------------------
# ClassifierModelTorch
# ---------------------------------------------------------------------------


class ClassifierModelTorch(nn.Module):
    """Combined C1 failure classifier (PyTorch).

    Fuses GraphSAGETorch (384-dim) and TabTransformerTorch (88-dim) outputs
    into a 472-dim vector, then passes through MLPHeadTorch to produce a
    failure probability.

    LightGBM ensemble is attached post-training (same 50/50 blend as the
    NumPy :class:`ClassifierModel`).

    Parameters
    ----------
    graphsage:
        Pre-initialised :class:`GraphSAGETorch`.
    tabtransformer:
        Pre-initialised :class:`TabTransformerTorch`.
    mlp_head:
        Pre-initialised :class:`MLPHeadTorch`.
    """

    def __init__(
        self,
        graphsage: GraphSAGETorch,
        tabtransformer: TabTransformerTorch,
        mlp_head: MLPHeadTorch,
    ) -> None:
        super().__init__()
        self.graphsage = graphsage
        self.tabtransformer = tabtransformer
        self.mlp_head = mlp_head
        self.lgbm_model: Optional[Any] = None  # attached after stage5b

    def forward(
        self,
        node_feat: torch.Tensor,
        tab_feat: torch.Tensor,
        neighbor_feats: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass returning logits.

        Parameters
        ----------
        node_feat:
            Shape ``(B, 8)`` — node features.
        tab_feat:
            Shape ``(B, 88)`` — tabular features.
        neighbor_feats:
            Optional shape ``(B, k, 8)`` — BIC graph neighbor features.
            When ``None``, GraphSAGE uses zero aggregation (legacy path).

        Returns
        -------
        torch.Tensor
            Shape ``(B, 1)`` — raw logits.
        """
        sage_emb = self.graphsage(node_feat, neighbor_feats)  # (B, 384)
        tab_emb = self.tabtransformer(tab_feat)                # (B, 88)
        fused = torch.cat([sage_emb, tab_emb], dim=1)          # (B, 472)
        return self.mlp_head(fused)                            # (B, 1)

    def predict_proba(
        self,
        node_features: np.ndarray,
        tabular_features: np.ndarray,
        neighbor_features: Optional[np.ndarray] = None,
    ) -> float:
        """Return the predicted failure probability for a single payment.

        Parameters
        ----------
        node_features:
            8-dim numpy array for the sending BIC node.
        tabular_features:
            Full feature vector (96-dim, node features prepended to tabular).
        neighbor_features:
            Optional ``(k, 8)`` numpy array of neighbor node features.
            When ``None``, GraphSAGE uses zero aggregation.

        Returns
        -------
        float
            Failure probability in ``[0, 1]``.
        """
        self.eval()
        with torch.no_grad():
            nf = torch.tensor(node_features, dtype=torch.float32).unsqueeze(0)
            tf = torch.tensor(tabular_features, dtype=torch.float32).unsqueeze(0)
            if neighbor_features is not None:
                nbr = torch.tensor(neighbor_features, dtype=torch.float32).unsqueeze(0)
            else:
                nbr = None
            logit = self(nf, tf, nbr)
            neural_prob = float(torch.sigmoid(logit).item())

        if self.lgbm_model is not None:
            x_tab = np.asarray(tabular_features, dtype=np.float64).reshape(1, -1)
            lgbm_prob = float(self.lgbm_model.predict_proba(x_tab)[0, 1])
            return 0.5 * neural_prob + 0.5 * lgbm_prob
        return neural_prob
