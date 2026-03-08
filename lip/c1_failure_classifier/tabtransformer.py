"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

tabtransformer.py — TabTransformer with 4 attention layers
C1 Spec Section 6: 8 heads, 32-dim per categorical embedding
Output: 88-dimensional tabular representation
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TABTRANSFORMER_INPUT_DIM: int = 88
"""Raw tabular feature dimensionality (matches TABULAR_FEATURE_DIM)."""

TABTRANSFORMER_NUM_LAYERS: int = 4
"""Number of stacked transformer layers."""

TABTRANSFORMER_NUM_HEADS: int = 8
"""Number of self-attention heads per layer."""

TABTRANSFORMER_EMBED_DIM: int = 32
"""Per-head embedding dimension; total attention dim = num_heads * embed_dim = 256."""

_RNG = np.random.default_rng(seed=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _gelu(x: np.ndarray) -> np.ndarray:
    """GELU activation (approximate version for the FFN sub-layer)."""
    x = np.clip(x, -20.0, 20.0)  # prevent cubic-term overflow; tanh saturates well before ±20
    return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x ** 3)))


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    x_shifted = x - np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x_shifted)
    return exp_x / (np.sum(exp_x, axis=axis, keepdims=True) + 1e-12)


def _layer_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Apply layer normalisation over the last axis."""
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    return gamma * (x - mean) / np.sqrt(var + eps) + beta


def _xavier_uniform(in_dim: int, out_dim: int, rng: np.random.Generator) -> np.ndarray:
    limit = np.sqrt(6.0 / (in_dim + out_dim))
    return rng.uniform(-limit, limit, size=(in_dim, out_dim)).astype(np.float64)


# ---------------------------------------------------------------------------
# MultiHeadAttention
# ---------------------------------------------------------------------------

class MultiHeadAttention:
    """Pure-numpy multi-head self-attention module.

    The total model dimension is ``num_heads * embed_dim``.  Weights are
    split per head to allow independent projection spaces.

    Parameters
    ----------
    embed_dim:
        Dimensionality of each attention head's Q/K/V projections.
    num_heads:
        Number of parallel attention heads.
    """

    def __init__(
        self,
        embed_dim: int = TABTRANSFORMER_EMBED_DIM,
        num_heads: int = TABTRANSFORMER_NUM_HEADS,
    ) -> None:
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.model_dim = embed_dim * num_heads  # 256 by default

        # Per-head Q, K, V projections: each maps (model_dim,) → (embed_dim,)
        self.W_q: List[np.ndarray] = [
            _xavier_uniform(self.model_dim, embed_dim, _RNG) for _ in range(num_heads)
        ]
        self.W_k: List[np.ndarray] = [
            _xavier_uniform(self.model_dim, embed_dim, _RNG) for _ in range(num_heads)
        ]
        self.W_v: List[np.ndarray] = [
            _xavier_uniform(self.model_dim, embed_dim, _RNG) for _ in range(num_heads)
        ]
        # Output projection: (model_dim,) → (model_dim,)
        self.W_o: np.ndarray = _xavier_uniform(self.model_dim, self.model_dim, _RNG)
        self.b_o: np.ndarray = np.zeros(self.model_dim, dtype=np.float64)

        self._scale: float = embed_dim ** -0.5

    def forward(
        self,
        Q: np.ndarray,
        K: np.ndarray,
        V: np.ndarray,
    ) -> np.ndarray:
        """Compute multi-head scaled dot-product attention.

        Parameters
        ----------
        Q, K, V:
            Input arrays of shape ``(seq_len, model_dim)`` where
            ``model_dim = num_heads * embed_dim``.  For the tabular case
            ``seq_len`` corresponds to the number of feature tokens.

        Returns
        -------
        np.ndarray
            Shape ``(seq_len, model_dim)``, same as the inputs.
        """
        head_outputs: List[np.ndarray] = []

        for h in range(self.num_heads):
            # Project to head space: (seq_len, embed_dim)
            q_h = Q @ self.W_q[h]
            k_h = K @ self.W_k[h]
            v_h = V @ self.W_v[h]

            # Scaled dot-product attention: (seq_len, seq_len)
            scores = (q_h @ k_h.T) * self._scale
            attn = _softmax(scores, axis=-1)

            # Weighted sum of values: (seq_len, embed_dim)
            head_outputs.append(attn @ v_h)

        # Concatenate heads → (seq_len, model_dim)
        concat = np.concatenate(head_outputs, axis=-1)
        return concat @ self.W_o + self.b_o

    def get_weights(self) -> dict:
        """Return a serialisable dict of all weight arrays."""
        d: dict = {"W_o": self.W_o, "b_o": self.b_o}
        for h in range(self.num_heads):
            d[f"W_q_{h}"] = self.W_q[h]
            d[f"W_k_{h}"] = self.W_k[h]
            d[f"W_v_{h}"] = self.W_v[h]
        return d

    def set_weights(self, weights: dict) -> None:
        """Load weights from a dict of numpy arrays."""
        self.W_o = np.asarray(weights["W_o"], dtype=np.float64)
        self.b_o = np.asarray(weights["b_o"], dtype=np.float64)
        for h in range(self.num_heads):
            self.W_q[h] = np.asarray(weights[f"W_q_{h}"], dtype=np.float64)
            self.W_k[h] = np.asarray(weights[f"W_k_{h}"], dtype=np.float64)
            self.W_v[h] = np.asarray(weights[f"W_v_{h}"], dtype=np.float64)


# ---------------------------------------------------------------------------
# TabTransformerLayer
# ---------------------------------------------------------------------------

class TabTransformerLayer:
    """One TabTransformer encoder block.

    Sub-layers (following the original TabTransformer paper):

    1. Multi-head self-attention
    2. Add & LayerNorm
    3. Position-wise feed-forward network (FFN) with GELU
    4. Add & LayerNorm

    Parameters
    ----------
    embed_dim:
        Per-head embedding dimension.
    num_heads:
        Number of attention heads.
    ff_dim:
        Inner dimensionality of the FFN (point-wise).
    """

    def __init__(
        self,
        embed_dim: int = TABTRANSFORMER_EMBED_DIM,
        num_heads: int = TABTRANSFORMER_NUM_HEADS,
        ff_dim: int = 64,
    ) -> None:
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.model_dim = embed_dim * num_heads  # 256

        self.attention = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)

        # Layer norm 1 (post-attention)
        self.ln1_gamma = np.ones(self.model_dim, dtype=np.float64)
        self.ln1_beta = np.zeros(self.model_dim, dtype=np.float64)

        # Feed-forward sub-layer
        self.W_ff1: np.ndarray = _xavier_uniform(self.model_dim, ff_dim, _RNG)
        self.b_ff1: np.ndarray = np.zeros(ff_dim, dtype=np.float64)
        self.W_ff2: np.ndarray = _xavier_uniform(ff_dim, self.model_dim, _RNG)
        self.b_ff2: np.ndarray = np.zeros(self.model_dim, dtype=np.float64)

        # Layer norm 2 (post-FFN)
        self.ln2_gamma = np.ones(self.model_dim, dtype=np.float64)
        self.ln2_beta = np.zeros(self.model_dim, dtype=np.float64)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Apply one transformer encoder block.

        Parameters
        ----------
        x:
            Input tensor of shape ``(seq_len, model_dim)``.

        Returns
        -------
        np.ndarray
            Shape ``(seq_len, model_dim)`` — same as input.
        """
        # --- Multi-head self-attention + residual ---
        attn_out = self.attention.forward(x, x, x)
        x = _layer_norm(x + attn_out, self.ln1_gamma, self.ln1_beta)

        # --- Position-wise FFN + residual ---
        ff = _gelu(x @ self.W_ff1 + self.b_ff1) @ self.W_ff2 + self.b_ff2
        x = _layer_norm(x + ff, self.ln2_gamma, self.ln2_beta)

        return x

    def get_weights(self) -> dict:
        d = {
            "W_ff1": self.W_ff1, "b_ff1": self.b_ff1,
            "W_ff2": self.W_ff2, "b_ff2": self.b_ff2,
            "ln1_gamma": self.ln1_gamma, "ln1_beta": self.ln1_beta,
            "ln2_gamma": self.ln2_gamma, "ln2_beta": self.ln2_beta,
        }
        d.update({f"attn_{k}": v for k, v in self.attention.get_weights().items()})
        return d

    def set_weights(self, weights: dict) -> None:
        self.W_ff1 = np.asarray(weights["W_ff1"], dtype=np.float64)
        self.b_ff1 = np.asarray(weights["b_ff1"], dtype=np.float64)
        self.W_ff2 = np.asarray(weights["W_ff2"], dtype=np.float64)
        self.b_ff2 = np.asarray(weights["b_ff2"], dtype=np.float64)
        self.ln1_gamma = np.asarray(weights["ln1_gamma"], dtype=np.float64)
        self.ln1_beta = np.asarray(weights["ln1_beta"], dtype=np.float64)
        self.ln2_gamma = np.asarray(weights["ln2_gamma"], dtype=np.float64)
        self.ln2_beta = np.asarray(weights["ln2_beta"], dtype=np.float64)
        attn_weights = {
            k[len("attn_"):]: v
            for k, v in weights.items()
            if k.startswith("attn_")
        }
        self.attention.set_weights(attn_weights)


# ---------------------------------------------------------------------------
# TabTransformerModel
# ---------------------------------------------------------------------------

class TabTransformerModel:
    """Full 4-layer TabTransformer for tabular failure-prediction features.

    Architecture (C1 Spec §6):

    1. Linear projection: ``input_dim → model_dim``
    2. 4 × :class:`TabTransformerLayer`
    3. Mean-pool over sequence dimension → ``(model_dim,)``
    4. Linear head:  ``model_dim → output_dim``

    The model is purely numpy; no ML framework is required.

    Parameters
    ----------
    input_dim:
        Dimensionality of the raw tabular feature vector (default 88).
    num_layers:
        Number of transformer encoder layers (default 4).
    num_heads:
        Attention heads per layer (default 8).
    embed_dim:
        Per-head dimension (default 32; total attention dim = 256).
    output_dim:
        Output representation size (default 88 to match the spec).
    """

    def __init__(
        self,
        input_dim: int = TABTRANSFORMER_INPUT_DIM,
        num_layers: int = TABTRANSFORMER_NUM_LAYERS,
        num_heads: int = TABTRANSFORMER_NUM_HEADS,
        embed_dim: int = TABTRANSFORMER_EMBED_DIM,
        output_dim: int = TABTRANSFORMER_INPUT_DIM,
    ) -> None:
        self.input_dim = input_dim
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.embed_dim = embed_dim
        self.output_dim = output_dim
        self.model_dim = embed_dim * num_heads  # 256

        # Input projection: (input_dim,) → (1, model_dim) token
        self.W_in: np.ndarray = _xavier_uniform(input_dim, self.model_dim, _RNG)
        self.b_in: np.ndarray = np.zeros(self.model_dim, dtype=np.float64)

        self.layers: List[TabTransformerLayer] = [
            TabTransformerLayer(embed_dim=embed_dim, num_heads=num_heads, ff_dim=64)
            for _ in range(num_layers)
        ]

        # Output projection: model_dim → output_dim
        self.W_out: np.ndarray = _xavier_uniform(self.model_dim, output_dim, _RNG)
        self.b_out: np.ndarray = np.zeros(output_dim, dtype=np.float64)

        logger.debug(
            "TabTransformerModel: %d → %d → %d (%d layers, %d heads)",
            input_dim, self.model_dim, output_dim, num_layers, num_heads,
        )

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Transform a tabular feature vector into an 88-dim representation.

        The raw feature vector is treated as a single token and passed
        through the transformer stack.

        Parameters
        ----------
        x:
            1-D array of shape ``(input_dim,)`` or 2-D ``(1, input_dim)``.

        Returns
        -------
        np.ndarray
            Shape ``(output_dim,)`` = ``(88,)``, dtype ``float64``.
        """
        x = np.asarray(x, dtype=np.float64).reshape(-1)

        # Project to model dimension — treat as a (1, model_dim) sequence
        h = (x @ self.W_in + self.b_in).reshape(1, self.model_dim)  # (1, model_dim)

        # Pass through transformer layers
        for layer in self.layers:
            h = layer.forward(h)

        # Mean-pool over sequence (trivial here as seq_len=1)
        pooled = np.mean(h, axis=0)  # (model_dim,)

        # Output projection
        out = pooled @ self.W_out + self.b_out  # (output_dim,)
        return out.astype(np.float64)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_weights(self, path: str) -> None:
        """Save all model weights to a ``.npz`` file.

        Parameters
        ----------
        path:
            Destination file path (extension added automatically).
        """
        arrays: dict = {
            "W_in": self.W_in,
            "b_in": self.b_in,
            "W_out": self.W_out,
            "b_out": self.b_out,
        }
        for i, layer in enumerate(self.layers):
            for k, v in layer.get_weights().items():
                arrays[f"layer{i}_{k}"] = v
        np.savez(path, **arrays)
        logger.info("TabTransformerModel weights saved to %s", path)

    def load_weights(self, path: str) -> None:
        """Load model weights from a ``.npz`` file.

        Parameters
        ----------
        path:
            Source file path.
        """
        data = np.load(path)
        self.W_in = np.asarray(data["W_in"], dtype=np.float64)
        self.b_in = np.asarray(data["b_in"], dtype=np.float64)
        self.W_out = np.asarray(data["W_out"], dtype=np.float64)
        self.b_out = np.asarray(data["b_out"], dtype=np.float64)
        for i, layer in enumerate(self.layers):
            layer_weights = {
                k[len(f"layer{i}_"):]: np.asarray(v, dtype=np.float64)
                for k, v in data.items()
                if k.startswith(f"layer{i}_")
            }
            layer.set_weights(layer_weights)
        logger.info("TabTransformerModel weights loaded from %s", path)

    def get_weights_dict(self) -> dict:
        """Return a shallow copy of all model weights as a plain dict."""
        d = {
            "W_in": self.W_in.copy(),
            "b_in": self.b_in.copy(),
            "W_out": self.W_out.copy(),
            "b_out": self.b_out.copy(),
        }
        for i, layer in enumerate(self.layers):
            for k, v in layer.get_weights().items():
                d[f"layer{i}_{k}"] = v.copy()
        return d

    def set_weights_dict(self, d: dict) -> None:
        """Restore weights from a dict previously returned by :meth:`get_weights_dict`."""
        self.W_in = np.asarray(d["W_in"], dtype=np.float64)
        self.b_in = np.asarray(d["b_in"], dtype=np.float64)
        self.W_out = np.asarray(d["W_out"], dtype=np.float64)
        self.b_out = np.asarray(d["b_out"], dtype=np.float64)
        for i, layer in enumerate(self.layers):
            layer_weights = {
                k[len(f"layer{i}_"):]: np.asarray(v, dtype=np.float64)
                for k, v in d.items()
                if k.startswith(f"layer{i}_")
            }
            layer.set_weights(layer_weights)

    def backward(
        self,
        x_input: np.ndarray,
        d_tab_emb: np.ndarray,
        lr: float,
    ) -> None:
        """Analytical backprop through W_out, FFN sub-layers, and W_in.

        Attention weight matrices are not updated — their Jacobian is complex
        and the signal through the residual path is sufficient for the reference
        implementation.  LayerNorm and residual connections are approximated:
        the residual is treated as a straight-through path and the LayerNorm
        Jacobian is approximated as the identity.

        Parameters
        ----------
        x_input:
            The raw 88-dim tabular feature vector fed into :meth:`forward`.
        d_tab_emb:
            Gradient of the loss w.r.t. the 88-dim TabTransformer output,
            propagated back from the MLP head.
        lr:
            Learning rate for in-place weight updates.
        """
        x = np.asarray(x_input, dtype=np.float64).reshape(-1)
        d_out = np.asarray(d_tab_emb, dtype=np.float64)

        # Recompute forward pass, caching layer inputs
        h = (x @ self.W_in + self.b_in).reshape(1, self.model_dim)  # (1, model_dim)
        h_cache: List[np.ndarray] = [h.copy()]
        for layer in self.layers:
            h = layer.forward(h)
            h_cache.append(h.copy())
        pooled = np.mean(h, axis=0)  # (model_dim,) — trivial for seq_len=1

        # --- Backprop output projection ---
        dW_out = np.outer(pooled, d_out)    # (model_dim, output_dim)
        db_out = d_out.copy()
        d_pooled = self.W_out @ d_out       # (model_dim,)

        # seq_len=1 → mean-pool is identity
        d_h = d_pooled.reshape(1, self.model_dim)

        # --- Backprop through transformer FFN layers (reverse order) ---
        for i in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[i]
            h_in_0 = h_cache[i][0]   # (model_dim,) — input to this layer

            # Recompute FFN intermediates (approximating attn+LN as identity)
            ff_pre = h_in_0 @ layer.W_ff1 + layer.b_ff1    # (ff_dim,)
            ff_act = _gelu(ff_pre)                           # (ff_dim,)

            d_h_0 = d_h[0]  # (model_dim,)

            # Gradient through FFN output layer: ff_out = ff_act @ W_ff2 + b_ff2
            dW_ff2 = np.outer(ff_act, d_h_0)               # (ff_dim, model_dim)
            db_ff2 = d_h_0.copy()
            d_ff_act = layer.W_ff2 @ d_h_0                 # (ff_dim,)

            # GELU gradient (exact formula); clip ff_pre to match forward-pass clipping
            _c = 0.044715
            _scale = np.sqrt(2.0 / np.pi)
            ff_pre_safe = np.clip(ff_pre, -20.0, 20.0)
            tanh_arg = _scale * (ff_pre_safe + _c * ff_pre_safe ** 3)
            tanh_val = np.tanh(tanh_arg)
            sech2 = 1.0 - tanh_val ** 2
            d_gelu_dx = (
                0.5 * (1.0 + tanh_val)
                + 0.5 * ff_pre_safe * sech2 * _scale * (1.0 + 3.0 * _c * ff_pre_safe ** 2)
            )
            d_ff_pre = d_ff_act * d_gelu_dx                # (ff_dim,)

            dW_ff1 = np.outer(h_in_0, d_ff_pre)            # (model_dim, ff_dim)
            db_ff1 = d_ff_pre.copy()

            # Residual path: d_h carries through unchanged (straight-through)
            # FFN input gradient also flows back (approximate LN as identity)
            d_h_prev_0 = d_h_0 + layer.W_ff1 @ d_ff_pre   # (model_dim,)
            d_h = d_h_prev_0.reshape(1, self.model_dim)

            # Update FFN weights in place (gradient clipping: max element-wise ±1.0)
            _gc = 1.0
            layer.W_ff2 -= lr * np.clip(dW_ff2, -_gc, _gc)
            layer.b_ff2 -= lr * np.clip(db_ff2, -_gc, _gc)
            layer.W_ff1 -= lr * np.clip(dW_ff1, -_gc, _gc)
            layer.b_ff1 -= lr * np.clip(db_ff1, -_gc, _gc)

        # --- Backprop input projection ---
        d_h_0 = d_h[0]                          # (model_dim,)
        dW_in = np.outer(x, d_h_0)             # (input_dim, model_dim)
        db_in = d_h_0.copy()

        # Update projection weights in place (gradient clipping: max element-wise ±1.0)
        _gc = 1.0
        self.W_in  -= lr * np.clip(dW_in,  -_gc, _gc)
        self.b_in  -= lr * np.clip(db_in,  -_gc, _gc)
        self.W_out -= lr * np.clip(dW_out, -_gc, _gc)
        self.b_out -= lr * np.clip(db_out, -_gc, _gc)
