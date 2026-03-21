"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

model.py — Combined C1 Classifier
GraphSAGE[384] + TabTransformer[88] → 472-dim → MLP(256→64→1) → sigmoid
C1 Spec Section 7
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

import numpy as np

from .graphsage import GRAPHSAGE_OUTPUT_DIM, GraphSAGEModel
from .tabtransformer import TABTRANSFORMER_INPUT_DIM, TabTransformerModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension constants
# ---------------------------------------------------------------------------

_COMBINED_DIM: int = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_INPUT_DIM  # 472
_RNG = np.random.default_rng(seed=7)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid for a scalar."""
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    exp_x = np.exp(x)
    return exp_x / (1.0 + exp_x)


def _sigmoid_arr(x: np.ndarray) -> np.ndarray:
    """Element-wise numerically stable sigmoid for an array."""
    result = np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-np.clip(x, -500, 500))),
        np.exp(np.clip(x, -500, 500)) / (1.0 + np.exp(np.clip(x, -500, 500))),
    )
    return result


def _xavier_uniform(in_dim: int, out_dim: int, rng: np.random.Generator) -> np.ndarray:
    limit = np.sqrt(6.0 / (in_dim + out_dim))
    return rng.uniform(-limit, limit, size=(in_dim, out_dim)).astype(np.float64)


# ---------------------------------------------------------------------------
# MLPHead
# ---------------------------------------------------------------------------

class MLPHead:
    """Two-hidden-layer MLP that maps the 472-dim fused embedding to [0,1].

    Architecture:
        472 → Linear(256) → ReLU → Dropout(0.3) →
              Linear(64)  → ReLU → Dropout(0.3) →
              Linear(1)   → Sigmoid

    Dropout is disabled at inference time (no ``training`` flag needed
    because this module is always used for inference only; training is
    handled at the pipeline level).

    Parameters
    ----------
    input_dim:
        Dimensionality of the concatenated GraphSAGE + TabTransformer vector.
    hidden1:
        Size of the first hidden layer.
    hidden2:
        Size of the second hidden layer.
    output_dim:
        Output size (1 for binary classification).
    """

    def __init__(
        self,
        input_dim: int = _COMBINED_DIM,
        hidden1: int = 256,
        hidden2: int = 64,
        output_dim: int = 1,
    ) -> None:
        self.input_dim = input_dim
        self.hidden1 = hidden1
        self.hidden2 = hidden2
        self.output_dim = output_dim

        self.W1: np.ndarray = _xavier_uniform(input_dim, hidden1, _RNG)
        self.b1: np.ndarray = np.zeros(hidden1, dtype=np.float64)

        self.W2: np.ndarray = _xavier_uniform(hidden1, hidden2, _RNG)
        self.b2: np.ndarray = np.zeros(hidden2, dtype=np.float64)

        self.W3: np.ndarray = _xavier_uniform(hidden2, output_dim, _RNG)
        self.b3: np.ndarray = np.zeros(output_dim, dtype=np.float64)

        # Adam optimizer state (moment vectors for each parameter)
        self._adam_t: int = 0
        self._adam_b1: float = 0.9
        self._adam_b2: float = 0.999
        self._adam_eps: float = 1e-8
        self._m_W1 = np.zeros_like(self.W1)
        self._v_W1 = np.zeros_like(self.W1)
        self._m_b1 = np.zeros_like(self.b1)
        self._v_b1 = np.zeros_like(self.b1)
        self._m_W2 = np.zeros_like(self.W2)
        self._v_W2 = np.zeros_like(self.W2)
        self._m_b2 = np.zeros_like(self.b2)
        self._v_b2 = np.zeros_like(self.b2)
        self._m_W3 = np.zeros_like(self.W3)
        self._v_W3 = np.zeros_like(self.W3)
        self._m_b3 = np.zeros_like(self.b3)
        self._v_b3 = np.zeros_like(self.b3)

    def forward(self, x: np.ndarray) -> float:
        """Compute the failure probability for a fused feature vector.

        Parameters
        ----------
        x:
            1-D array of shape ``(input_dim,)`` = ``(472,)``.

        Returns
        -------
        float
            Predicted failure probability in ``[0, 1]``.
        """
        x = np.asarray(x, dtype=np.float64).reshape(-1)
        h1 = _relu(x @ self.W1 + self.b1)       # (256,)
        h2 = _relu(h1 @ self.W2 + self.b2)      # (64,)
        logit = float((h2 @ self.W3 + self.b3)[0])
        return _sigmoid(logit)

    def forward_batch(self, x_batch: np.ndarray) -> np.ndarray:
        """Batch forward for B fused vectors.

        Parameters
        ----------
        x_batch:
            Shape ``(B, input_dim)``.

        Returns
        -------
        np.ndarray
            Shape ``(B,)`` — predicted failure probabilities in ``[0, 1]``.
        """
        x = np.asarray(x_batch, dtype=np.float64)   # (B, input_dim)
        h1 = _relu(x @ self.W1 + self.b1)           # (B, hidden1)
        h2 = _relu(h1 @ self.W2 + self.b2)          # (B, hidden2)
        logits = (h2 @ self.W3 + self.b3).reshape(-1)  # (B,)
        return _sigmoid_arr(logits)                  # (B,)

    def get_weights(self) -> dict:
        return {
            "W1": self.W1, "b1": self.b1,
            "W2": self.W2, "b2": self.b2,
            "W3": self.W3, "b3": self.b3,
        }

    def set_weights(self, weights: dict) -> None:
        self.W1 = np.asarray(weights["W1"], dtype=np.float64)
        self.b1 = np.asarray(weights["b1"], dtype=np.float64)
        self.W2 = np.asarray(weights["W2"], dtype=np.float64)
        self.b2 = np.asarray(weights["b2"], dtype=np.float64)
        self.W3 = np.asarray(weights["W3"], dtype=np.float64)
        self.b3 = np.asarray(weights["b3"], dtype=np.float64)

    def backward(
        self,
        x_input: np.ndarray,
        y_true: float,
        prob: float,
        alpha: float,
        lr: float,
    ) -> np.ndarray:
        """Analytical backpropagation through the MLP head.

        Computes gradients via chain rule through
        ``Linear → ReLU → Linear → ReLU → Linear → Sigmoid`` and updates
        all weight matrices and bias vectors in place.

        Parameters
        ----------
        x_input:
            The fused input vector of shape ``(input_dim,)`` that was fed into
            :meth:`forward`.
        y_true:
            Ground-truth binary label (0 or 1).
        prob:
            Predicted probability from the matching :meth:`forward` call.
        alpha:
            Asymmetric BCE positive-class weight (same value as used in loss).
        lr:
            Learning rate for the gradient update.

        Returns
        -------
        np.ndarray
            Gradient of the loss w.r.t. ``x_input``, shape ``(input_dim,)``.
            Consumed by upstream encoders (GraphSAGE / TabTransformer) to
            continue the backpropagation chain.
        """
        x = np.asarray(x_input, dtype=np.float64).reshape(-1)

        # Recompute forward intermediates needed for gradient computation
        pre_h1 = x @ self.W1 + self.b1             # (hidden1,)
        h1 = np.maximum(0.0, pre_h1)               # ReLU
        pre_h2 = h1 @ self.W2 + self.b2            # (hidden2,)
        h2 = np.maximum(0.0, pre_h2)               # ReLU

        # dL/d_logit for asymmetric BCE + sigmoid, combined:
        #   dL/d_logit = (1-alpha)*(1-y)*p  -  alpha*y*(1-p)
        p = float(np.clip(prob, 1e-12, 1.0 - 1e-12))
        y = float(y_true)
        d_logit = (1.0 - alpha) * (1.0 - y) * p - alpha * y * (1.0 - p)

        # --- Layer 3: logit = h2 @ W3 + b3 ---
        dW3 = np.outer(h2, np.array([d_logit]))    # (hidden2, 1)
        db3 = np.array([d_logit])                  # (1,)
        d_h2 = self.W3[:, 0] * d_logit             # (hidden2,)

        # --- Layer 2 ReLU ---
        d_pre_h2 = d_h2 * (pre_h2 > 0)            # (hidden2,)
        dW2 = np.outer(h1, d_pre_h2)              # (hidden1, hidden2)
        db2 = d_pre_h2.copy()
        d_h1 = self.W2 @ d_pre_h2                 # (hidden1,)

        # --- Layer 1 ReLU ---
        d_pre_h1 = d_h1 * (pre_h1 > 0)            # (hidden1,)
        dW1 = np.outer(x, d_pre_h1)               # (input_dim, hidden1)
        db1 = d_pre_h1.copy()
        d_x = self.W1 @ d_pre_h1                  # (input_dim,)

        # --- Adam update (replaces plain SGD) ---
        self._adam_t += 1
        t = self._adam_t
        b1_a, b2_a, eps_a = self._adam_b1, self._adam_b2, self._adam_eps

        def _adam(param: np.ndarray, grad: np.ndarray, m: np.ndarray, v: np.ndarray) -> None:
            m[:] = b1_a * m + (1.0 - b1_a) * grad
            v[:] = b2_a * v + (1.0 - b2_a) * grad ** 2
            m_hat = m / (1.0 - b1_a ** t)
            v_hat = v / (1.0 - b2_a ** t)
            param -= lr * m_hat / (np.sqrt(v_hat) + eps_a)

        _adam(self.W1, dW1, self._m_W1, self._v_W1)
        _adam(self.b1, db1, self._m_b1, self._v_b1)
        _adam(self.W2, dW2, self._m_W2, self._v_W2)
        _adam(self.b2, db2, self._m_b2, self._v_b2)
        _adam(self.W3, dW3, self._m_W3, self._v_W3)
        _adam(self.b3, db3, self._m_b3, self._v_b3)

        return d_x


# ---------------------------------------------------------------------------
# ClassifierModel
# ---------------------------------------------------------------------------

class ClassifierModel:
    """Combined C1 failure classifier.

    Fuses a GraphSAGE corridor embedding (384-dim) with a TabTransformer
    tabular representation (88-dim) into a 472-dim vector, then passes it
    through an MLP head to produce a failure probability.

    Parameters
    ----------
    graphsage:
        Pre-initialised :class:`~lip.c1_failure_classifier.graphsage.GraphSAGEModel`.
    tabtransformer:
        Pre-initialised :class:`~lip.c1_failure_classifier.tabtransformer.TabTransformerModel`.
    mlp:
        Pre-initialised :class:`MLPHead` with ``input_dim=472``.
    """

    def __init__(
        self,
        graphsage: GraphSAGEModel,
        tabtransformer: TabTransformerModel,
        mlp: MLPHead,
    ) -> None:
        self.graphsage = graphsage
        self.tabtransformer = tabtransformer
        self.mlp = mlp
        self.lgbm_model: Optional[Any] = None  # attached after stage5b training

        # R&D Upgrade: Probability Calibration (Isotonic)
        from .calibration import IsotonicCalibrator  # noqa: PLC0415
        self.calibrator = IsotonicCalibrator()

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(
        self,
        node_features: np.ndarray,
        neighbors_l1: List[np.ndarray],
        neighbors_l2: List[np.ndarray],
        tabular_features: np.ndarray,
        calibrate: bool = True,
    ) -> float:
        """Return the predicted failure probability for a payment.

        Parameters
        ----------
        node_features:
            8-dim feature vector for the sending BIC node.
        neighbors_l1:
            List of 8-dim vectors for hop-1 neighbours (k ≤ 5 at inference).
        neighbors_l2:
            List of 8-dim vectors for hop-2 neighbours.
        tabular_features:
            88-dim tabular feature vector from
            :class:`~lip.c1_failure_classifier.features.TabularFeatureEngineer`.
        calibrate:
            When True, apply the fitted Isotonic calibrator.

        Returns
        -------
        float
            Failure probability in ``[0, 1]``.
        """
        sage_emb = self.graphsage.forward(node_features, neighbors_l1, neighbors_l2)
        tab_emb = self.tabtransformer.forward(tabular_features)
        fused = np.concatenate([sage_emb, tab_emb])  # (472,)
        neural_prob = self.mlp.forward(fused)

        if self.lgbm_model is not None:
            # Slicing to last 88 dims ensures compatibility if a 96-dim fused vector was passed
            x_tab = np.asarray(tabular_features[-88:], dtype=np.float64).reshape(1, -1)
            lgbm_prob = float(self.lgbm_model.predict_proba(x_tab)[0, 1])
            raw_score = 0.5 * neural_prob + 0.5 * lgbm_prob
        else:
            raw_score = neural_prob

        if calibrate and self.calibrator._is_fitted:
            return float(self.calibrator.predict(np.array([raw_score]))[0])

        return raw_score

    # ------------------------------------------------------------------
    # Loss
    # ------------------------------------------------------------------

    @staticmethod
    def asymmetric_bce_loss(
        y_true: float,
        y_pred: float,
        alpha: float = 0.7,
    ) -> float:
        """Asymmetric binary cross-entropy loss (false negatives penalised more).

        .. math::
            \\mathcal{L} = -\\bigl[\\alpha \\cdot y \\log(p) + (1-\\alpha)(1-y)\\log(1-p)\\bigr]

        Setting ``alpha=0.7`` means missed failures (false negatives) are
        weighted 2.33× more than false positives.

        Parameters
        ----------
        y_true:
            Ground-truth binary label (0 or 1).
        y_pred:
            Predicted probability in ``(0, 1)``.
        alpha:
            Weight for the positive (failure) class.  ``0 < alpha < 1``.

        Returns
        -------
        float
            Scalar loss value ≥ 0.
        """
        eps = 1e-12
        p = float(np.clip(y_pred, eps, 1.0 - eps))
        y = float(y_true)
        return -(alpha * y * np.log(p) + (1.0 - alpha) * (1.0 - y) * np.log(1.0 - p))

    # ------------------------------------------------------------------
    # Threshold calibration
    # ------------------------------------------------------------------

    @staticmethod
    def select_f2_threshold(
        y_true: np.ndarray,
        y_scores: np.ndarray,
    ) -> float:
        """Select the decision threshold that maximises the F2-score.

        The F2-score weights recall twice as heavily as precision, which is
        appropriate for the C1 use-case where missing a genuine failure is
        more costly than a false alarm.

        .. math::
            F_2 = \\frac{5 \\cdot TP}{5 \\cdot TP + 4 \\cdot FN + FP}

        Parameters
        ----------
        y_true:
            Binary ground-truth labels, shape ``(n,)``.
        y_scores:
            Predicted probabilities, shape ``(n,)``.

        Returns
        -------
        float
            Optimal threshold in ``[0, 1]``.
        """
        y_true = np.asarray(y_true, dtype=np.float64)
        y_scores = np.asarray(y_scores, dtype=np.float64)

        thresholds = np.unique(y_scores)
        best_thresh = 0.5
        best_f2 = -1.0

        for thresh in thresholds:
            y_pred = (y_scores >= thresh).astype(np.float64)
            tp = float(np.sum((y_pred == 1) & (y_true == 1)))
            fp = float(np.sum((y_pred == 1) & (y_true == 0)))
            fn = float(np.sum((y_pred == 0) & (y_true == 1)))
            denom = 5 * tp + 4 * fn + fp
            f2 = (5 * tp / denom) if denom > 0 else 0.0
            if f2 > best_f2:
                best_f2 = f2
                best_thresh = float(thresh)

        logger.info("select_f2_threshold: best=%.4f  F2=%.4f", best_thresh, best_f2)
        return best_thresh

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save all sub-model weights under *path* as separate ``.npz`` files.

        Three files are written:

        - ``<path>/graphsage.npz``
        - ``<path>/tabtransformer.npz``
        - ``<path>/mlp.npz``

        Parameters
        ----------
        path:
            Directory path.  Created automatically if absent.
        """
        os.makedirs(path, exist_ok=True)
        self.graphsage.save_weights(os.path.join(path, "graphsage"))
        self.tabtransformer.save_weights(os.path.join(path, "tabtransformer"))
        np.savez(os.path.join(path, "mlp"), **self.mlp.get_weights())
        if self.lgbm_model is not None:
            import pickle
            with open(os.path.join(path, "lgbm.pkl"), "wb") as f:
                pickle.dump(self.lgbm_model, f)
        # Persist calibrator state so it survives save/load cycle
        if self.calibrator._is_fitted:
            import pickle
            with open(os.path.join(path, "calibrator.pkl"), "wb") as f:
                pickle.dump(self.calibrator, f)
        logger.info("ClassifierModel saved to %s", path)

    def load(self, path: str) -> None:
        """Load all sub-model weights from *path*.

        Parameters
        ----------
        path:
            Directory path previously used with :meth:`save`.
        """
        self.graphsage.load_weights(os.path.join(path, "graphsage.npz"))
        self.tabtransformer.load_weights(os.path.join(path, "tabtransformer.npz"))
        mlp_data = np.load(os.path.join(path, "mlp.npz"))
        self.mlp.set_weights(dict(mlp_data))
        lgbm_path = os.path.join(path, "lgbm.pkl")
        if os.path.exists(lgbm_path):
            import pickle
            with open(lgbm_path, "rb") as f:
                self.lgbm_model = pickle.load(f)
        # Restore calibrator if previously saved
        cal_path = os.path.join(path, "calibrator.pkl")
        if os.path.exists(cal_path):
            import pickle
            with open(cal_path, "rb") as f:
                self.calibrator = pickle.load(f)
            logger.info("Calibrator loaded (fitted=%s)", self.calibrator._is_fitted)
        logger.info("ClassifierModel loaded from %s", path)

    def save_weights(self, npz_path: str) -> None:
        """Save all neural-network weights to a single ``.npz`` file.

        Collects weight matrices from GraphSAGEModel, TabTransformerModel, and
        MLPHead, prefixes keys with ``sage__``, ``tab__``, and ``mlp__``, and
        writes them to *npz_path* via :func:`numpy.savez`.

        Parameters
        ----------
        npz_path:
            Destination file path, e.g. ``/tmp/c1_weights.npz``.
        """
        sage_w = {"sage__" + k: v for k, v in self.graphsage.get_weights_dict().items()}
        tab_w = {"tab__" + k: v for k, v in self.tabtransformer.get_weights_dict().items()}
        mlp_w = {"mlp__" + k: v for k, v in self.mlp.get_weights().items()}
        np.savez(npz_path, **sage_w, **tab_w, **mlp_w)
        logger.info("ClassifierModel weights saved to %s", npz_path)

    def load_weights(self, npz_path: str) -> None:
        """Load neural-network weights from a single ``.npz`` file.

        Parameters
        ----------
        npz_path:
            File path previously written by :meth:`save_weights`.
        """
        data = dict(np.load(npz_path))
        sage_w = {k[len("sage__"):]: v for k, v in data.items() if k.startswith("sage__")}
        tab_w = {k[len("tab__"):]: v for k, v in data.items() if k.startswith("tab__")}
        mlp_w = {k[len("mlp__"):]: v for k, v in data.items() if k.startswith("mlp__")}
        self.graphsage.set_weights_dict(sage_w)
        self.tabtransformer.set_weights_dict(tab_w)
        self.mlp.set_weights(mlp_w)
        logger.info("ClassifierModel weights loaded from %s", npz_path)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_default_model() -> ClassifierModel:
    """Instantiate a :class:`ClassifierModel` with default architecture.

    Weights are randomly initialised using the fixed seeds defined in each
    sub-module.  Call :meth:`ClassifierModel.load` to overlay trained weights.

    Returns
    -------
    ClassifierModel
        Ready-to-use (untrained) classifier.
    """
    graphsage = GraphSAGEModel()
    tabtransformer = TabTransformerModel()
    mlp = MLPHead()
    model = ClassifierModel(graphsage=graphsage, tabtransformer=tabtransformer, mlp=mlp)
    logger.info("create_default_model: ClassifierModel ready (dims 384+88→472→1)")
    return model
