"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

graphsage.py — GraphSAGE 2-layer model with MEAN aggregator
C1 Spec Section 5: k=10 training neighbors, k=5 inference neighbors
Output: 384-dimensional corridor embedding
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension constants
# ---------------------------------------------------------------------------

GRAPHSAGE_INPUT_DIM: int = 8
"""Node feature dimensionality — matches NODE_FEATURE_DIM in features.py."""

GRAPHSAGE_HIDDEN_DIM: int = 256
"""Hidden layer size after layer-1 aggregation."""

GRAPHSAGE_OUTPUT_DIM: int = 384
"""Output embedding dimensionality (C1 Spec §5.3)."""

_RNG = np.random.default_rng(seed=42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relu(x: np.ndarray) -> np.ndarray:
    """Element-wise ReLU activation."""
    return np.maximum(0.0, x)


def _l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """L2-normalise a 1-D vector."""
    norm = np.linalg.norm(x)
    return x / (norm + eps)


def _xavier_uniform(in_dim: int, out_dim: int, rng: np.random.Generator) -> np.ndarray:
    """Xavier uniform weight initialisation."""
    limit = np.sqrt(6.0 / (in_dim + out_dim))
    return rng.uniform(-limit, limit, size=(in_dim, out_dim)).astype(np.float64)


# ---------------------------------------------------------------------------
# MeanAggregator
# ---------------------------------------------------------------------------

class MeanAggregator:
    """Aggregates a list of neighbour feature vectors by element-wise mean.

    If no neighbours are provided the zero vector of length *dim* is returned,
    ensuring a safe fallback for isolated nodes.
    """

    def aggregate(
        self,
        neighbor_features: List[np.ndarray],
        dim: int,
    ) -> np.ndarray:
        """Return the mean of *neighbor_features*, or zeros if the list is empty.

        Parameters
        ----------
        neighbor_features:
            List of 1-D arrays, each of length *dim*.
        dim:
            Expected feature dimensionality used to construct the zero-vector
            fallback.

        Returns
        -------
        np.ndarray
            Shape ``(dim,)``, dtype ``float64``.
        """
        if not neighbor_features:
            return np.zeros(dim, dtype=np.float64)
        stacked = np.stack([f.astype(np.float64) for f in neighbor_features], axis=0)
        return np.mean(stacked, axis=0)


# ---------------------------------------------------------------------------
# GraphSAGELayer
# ---------------------------------------------------------------------------

class GraphSAGELayer:
    """Single GraphSAGE layer with MEAN aggregation and optional activation.

    The layer concatenates the self-feature vector with the mean-aggregated
    neighbour features and applies a learned linear transformation:

    .. math::
        h_v^{(l)} = \\sigma\\!\\left(W \\cdot [h_v^{(l-1)} \\,\\|\\, \\bar{h}_{\\mathcal{N}(v)}^{(l-1)}]\\right)

    Parameters
    ----------
    in_dim:
        Dimensionality of the input node features.
    out_dim:
        Dimensionality of the output representation.
    activation:
        Activation function name.  Supported: ``'relu'``, ``'none'``.
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        activation: str = "relu",
    ) -> None:
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.activation = activation.lower()
        self._aggregator = MeanAggregator()

        # Weight matrix: input is concatenation of [self, agg_neighbor]
        concat_dim = 2 * in_dim
        self.W: np.ndarray = _xavier_uniform(concat_dim, out_dim, _RNG)
        self.b: np.ndarray = np.zeros(out_dim, dtype=np.float64)

    def forward(
        self,
        node_features: np.ndarray,
        neighbor_features: List[np.ndarray],
    ) -> np.ndarray:
        """Compute the layer output for a single node.

        Parameters
        ----------
        node_features:
            1-D array of length ``in_dim`` representing the node's current
            representation.
        neighbor_features:
            List of 1-D arrays, each of length ``in_dim``, representing the
            *k* sampled neighbours' current representations.

        Returns
        -------
        np.ndarray
            Shape ``(out_dim,)``, dtype ``float64``.
        """
        h_self = node_features.astype(np.float64)
        h_agg = self._aggregator.aggregate(neighbor_features, self.in_dim)

        h_concat = np.concatenate([h_self, h_agg])          # (2 * in_dim,)
        h_out = h_concat @ self.W + self.b                  # (out_dim,)

        if self.activation == "relu":
            h_out = _relu(h_out)

        return _l2_normalize(h_out)

    def get_weights(self) -> dict:
        """Serialise layer parameters as a plain dict of numpy arrays."""
        return {"W": self.W, "b": self.b}

    def set_weights(self, weights: dict) -> None:
        """Load layer parameters from a dict of numpy arrays."""
        self.W = np.asarray(weights["W"], dtype=np.float64)
        self.b = np.asarray(weights["b"], dtype=np.float64)


# ---------------------------------------------------------------------------
# GraphSAGEModel
# ---------------------------------------------------------------------------

class GraphSAGEModel:
    """2-layer GraphSAGE model producing 384-dimensional corridor embeddings.

    Architecture (C1 Spec §5):

    - Layer 1:  [8 || 8]   → linear(256) → ReLU → L2-norm  → (256,)
    - Layer 2:  [256 || 256] → linear(384) → ReLU → L2-norm → (384,)

    Training uses k=10 sampled neighbours; inference uses k=5.

    This is a **pure-numpy** implementation — no PyTorch or TensorFlow
    dependencies are required, ensuring portability across all LIP
    deployment environments.

    Parameters
    ----------
    input_dim:
        Dimensionality of raw node features.
    hidden_dim:
        Hidden representation size after layer 1.
    output_dim:
        Final embedding size (corridor representation).
    """

    def __init__(
        self,
        input_dim: int = GRAPHSAGE_INPUT_DIM,
        hidden_dim: int = GRAPHSAGE_HIDDEN_DIM,
        output_dim: int = GRAPHSAGE_OUTPUT_DIM,
    ) -> None:
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        self.layer1 = GraphSAGELayer(input_dim, hidden_dim, activation="relu")
        self.layer2 = GraphSAGELayer(hidden_dim, output_dim, activation="relu")

        logger.debug(
            "GraphSAGEModel initialised: %d → %d → %d",
            input_dim, hidden_dim, output_dim,
        )

    def forward(
        self,
        node_features: np.ndarray,
        neighbors_l1: List[np.ndarray],
        neighbors_l2: List[np.ndarray],
    ) -> np.ndarray:
        """Compute the 2-hop GraphSAGE embedding for a node.

        Parameters
        ----------
        node_features:
            Raw 8-dim node feature vector for the target node.
        neighbors_l1:
            List of raw 8-dim node feature vectors for the target node's
            direct (hop-1) neighbours.
        neighbors_l2:
            List of raw 8-dim node feature vectors for the hop-2 neighbours
            (neighbours of neighbours, used to update ``neighbors_l1``
            representations before aggregating into the target).

        Returns
        -------
        np.ndarray
            Shape ``(384,)``, dtype ``float64``.
        """
        # --- Layer 1: update each hop-1 neighbour using hop-2 context ---
        h1_neighbors: List[np.ndarray] = []
        for nbr_feat in neighbors_l1:
            # Each hop-1 neighbour uses the global hop-2 pool as its context.
            h1_nbr = self.layer1.forward(nbr_feat, neighbors_l2)
            h1_neighbors.append(h1_nbr)

        # --- Layer 1: update the target node ---
        h1_self = self.layer1.forward(node_features, neighbors_l1)

        # --- Layer 2: update the target node using hop-1 representations ---
        h2 = self.layer2.forward(h1_self, h1_neighbors)

        return h2

    def save_weights(self, path: str) -> None:
        """Persist model weights to a ``.npz`` file.

        Parameters
        ----------
        path:
            Destination file path.  The ``.npz`` extension is appended
            automatically by :func:`numpy.savez` if not present.
        """
        l1 = self.layer1.get_weights()
        l2 = self.layer2.get_weights()
        np.savez(
            path,
            layer1_W=l1["W"],
            layer1_b=l1["b"],
            layer2_W=l2["W"],
            layer2_b=l2["b"],
        )
        logger.info("GraphSAGEModel weights saved to %s", path)

    def load_weights(self, path: str) -> None:
        """Load model weights from a ``.npz`` file.

        Parameters
        ----------
        path:
            Source file path (with or without the ``.npz`` extension).
        """
        data = np.load(path)
        self.layer1.set_weights({"W": data["layer1_W"], "b": data["layer1_b"]})
        self.layer2.set_weights({"W": data["layer2_W"], "b": data["layer2_b"]})
        logger.info("GraphSAGEModel weights loaded from %s", path)

    def get_weights_dict(self) -> dict:
        """Return a shallow copy of all layer weights as a plain dict."""
        return {
            "layer1_W": self.layer1.W.copy(),
            "layer1_b": self.layer1.b.copy(),
            "layer2_W": self.layer2.W.copy(),
            "layer2_b": self.layer2.b.copy(),
        }

    def set_weights_dict(self, d: dict) -> None:
        """Restore weights from a dict previously returned by :meth:`get_weights_dict`."""
        self.layer1.W = np.asarray(d["layer1_W"], dtype=np.float64)
        self.layer1.b = np.asarray(d["layer1_b"], dtype=np.float64)
        self.layer2.W = np.asarray(d["layer2_W"], dtype=np.float64)
        self.layer2.b = np.asarray(d["layer2_b"], dtype=np.float64)

    def backward_empty_neighbors(
        self,
        node_features: np.ndarray,
        d_sage_emb: np.ndarray,
        lr: float,
    ) -> None:
        """Approximate analytical backprop for the empty-neighbour training case.

        During batch training, neighbour lists are empty (no graph connectivity
        in the tabular batch).  The aggregated neighbour vector is therefore the
        zero vector, simplifying the forward pass to two linear + ReLU layers
        that operate on ``[node_feat ‖ 0]`` concatenations.

        The L2-normalisation Jacobian is approximated as the identity matrix to
        keep computation tractable (the normalisation is close to identity for
        unit-scale embeddings after a few warm-up steps).

        Parameters
        ----------
        node_features:
            Raw 8-dim node feature vector used in the matching forward call.
        d_sage_emb:
            Gradient of the loss w.r.t. the 384-dim GraphSAGE output,
            propagated back from the MLP head.
        lr:
            Learning rate for in-place weight update.
        """
        node_feat = node_features.astype(np.float64)
        zeros_in = np.zeros(self.input_dim, dtype=np.float64)
        zeros_hid = np.zeros(self.hidden_dim, dtype=np.float64)

        # --- Layer 1 forward (empty neighbours → zero agg) ---
        h_concat1 = np.concatenate([node_feat, zeros_in])   # (2*input_dim,)
        pre1 = h_concat1 @ self.layer1.W + self.layer1.b    # (hidden_dim,)
        h1 = np.maximum(0.0, pre1)                          # ReLU (before L2_norm)

        # --- Layer 2 forward (empty neighbours → zero agg) ---
        h_concat2 = np.concatenate([h1, zeros_hid])         # (2*hidden_dim,)
        pre2 = h_concat2 @ self.layer2.W + self.layer2.b    # (output_dim,)

        # --- Layer 2 backward (L2_norm ≈ identity) ---
        d_pre2 = d_sage_emb * (pre2 > 0)                    # (output_dim,)
        dW2 = np.outer(h_concat2, d_pre2)                   # (2*hidden_dim, output_dim)
        db2 = d_pre2.copy()
        d_h_concat2 = self.layer2.W @ d_pre2                # (2*hidden_dim,)
        d_h1 = d_h_concat2[:self.hidden_dim]                # (hidden_dim,)

        # --- Layer 1 backward (L2_norm ≈ identity) ---
        d_pre1 = d_h1 * (pre1 > 0)                          # (hidden_dim,)
        dW1 = np.outer(h_concat1, d_pre1)                   # (2*input_dim, hidden_dim)
        db1 = d_pre1.copy()

        # Update weights in place (gradient clipping: max element-wise ±1.0)
        _gc = 1.0
        self.layer1.W -= lr * np.clip(dW1, -_gc, _gc)
        self.layer1.b -= lr * np.clip(db1, -_gc, _gc)
        self.layer2.W -= lr * np.clip(dW2, -_gc, _gc)
        self.layer2.b -= lr * np.clip(db2, -_gc, _gc)
