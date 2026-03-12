"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

tabtransformer_torch.py — PyTorch TabTransformer
Mirrors tabtransformer.py but uses nn.Module for DataLoader + GPU support.
C1 Spec Section 6 — 4 attention layers, 8 heads, 32-dim per head (total 256).
Output: 88-dimensional tabular representation.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Constants (mirror tabtransformer.py)
# ---------------------------------------------------------------------------

TABTRANSFORMER_INPUT_DIM: int = 88
TABTRANSFORMER_NUM_LAYERS: int = 4
TABTRANSFORMER_NUM_HEADS: int = 8
TABTRANSFORMER_EMBED_DIM: int = 32   # per-head; total = 8 * 32 = 256


# ---------------------------------------------------------------------------
# TransformerLayer helper
# ---------------------------------------------------------------------------


class _TransformerLayer(nn.Module):
    """Single TabTransformer encoder block (PyTorch).

    Follows the original TabTransformer paper sub-layer order:

    1. Multi-head self-attention
    2. Add & LayerNorm
    3. Position-wise FFN (256 → 64 → 256, GELU)
    4. Add & LayerNorm

    Parameters
    ----------
    model_dim:
        Total attention dimensionality (``num_heads * embed_dim``).
    num_heads:
        Number of self-attention heads.
    ff_dim:
        Inner FFN dimensionality (default 64 — matches NumPy reference).
    """

    def __init__(
        self,
        model_dim: int = TABTRANSFORMER_NUM_HEADS * TABTRANSFORMER_EMBED_DIM,
        num_heads: int = TABTRANSFORMER_NUM_HEADS,
        ff_dim: int = 64,
    ) -> None:
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=model_dim,
            num_heads=num_heads,
            batch_first=True,
        )
        self.ln1 = nn.LayerNorm(model_dim)
        self.ff1 = nn.Linear(model_dim, ff_dim)
        self.ff2 = nn.Linear(ff_dim, model_dim)
        self.ln2 = nn.LayerNorm(model_dim)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.ff1.weight)
        nn.init.zeros_(self.ff1.bias)
        nn.init.xavier_uniform_(self.ff2.weight)
        nn.init.zeros_(self.ff2.bias)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """Apply one encoder block.

        Parameters
        ----------
        h:
            Input of shape ``(B, 1, model_dim)`` (single-token sequence).

        Returns
        -------
        torch.Tensor
            Same shape as input.
        """
        # Multi-head self-attention + residual + LayerNorm
        attn_out, _ = self.attn(h, h, h)
        h = self.ln1(h + attn_out)

        # FFN with GELU + residual + LayerNorm
        ff = self.ff2(F.gelu(self.ff1(h)))
        h = self.ln2(h + ff)

        return h


# ---------------------------------------------------------------------------
# TabTransformerTorch
# ---------------------------------------------------------------------------


class TabTransformerTorch(nn.Module):
    """Full 4-layer TabTransformer (PyTorch).

    Architecture (C1 Spec §6):

    1. ``proj_in``:  Linear(88, 256) — treat the 88-dim vector as one token
    2. 4 × :class:`_TransformerLayer`
    3. Pool (squeeze) — seq_len=1, so trivial
    4. ``proj_out``: Linear(256, 88)

    Parameters
    ----------
    input_dim:
        Raw tabular feature dimensionality (default 88).
    num_layers:
        Number of transformer encoder layers (default 4).
    num_heads:
        Attention heads per layer (default 8).
    embed_dim:
        Per-head dimension (default 32; total attention dim = 256).
    output_dim:
        Output representation size (default 88).
    """

    def __init__(
        self,
        input_dim: int = TABTRANSFORMER_INPUT_DIM,
        num_layers: int = TABTRANSFORMER_NUM_LAYERS,
        num_heads: int = TABTRANSFORMER_NUM_HEADS,
        embed_dim: int = TABTRANSFORMER_EMBED_DIM,
        output_dim: int = TABTRANSFORMER_INPUT_DIM,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        model_dim = num_heads * embed_dim  # 256

        self.proj_in = nn.Linear(input_dim, model_dim)
        self.layers = nn.ModuleList(
            [_TransformerLayer(model_dim=model_dim, num_heads=num_heads) for _ in range(num_layers)]
        )
        self.proj_out = nn.Linear(model_dim, output_dim)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.proj_in.weight)
        nn.init.zeros_(self.proj_in.bias)
        nn.init.xavier_uniform_(self.proj_out.weight)
        nn.init.zeros_(self.proj_out.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Transform a batch of tabular feature vectors.

        Parameters
        ----------
        x:
            Input tensor of shape ``(B, 88)``.

        Returns
        -------
        torch.Tensor
            Shape ``(B, 88)``.
        """
        # Project to model dim and add sequence dimension (seq_len=1)
        h = self.proj_in(x).unsqueeze(1)  # (B, 1, 256)

        for layer in self.layers:
            h = layer(h)

        # Pool: squeeze the trivial sequence dimension
        pooled = h.squeeze(1)              # (B, 256)
        return self.proj_out(pooled)       # (B, 88)
