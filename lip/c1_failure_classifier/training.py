"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

training.py — C1 Training Pipeline (9 stages)
C1 Spec Section 10
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .graph_builder import BICGraphBuilder, PaymentEdge
from .features import FeaturePipeline, TabularFeatureEngineer, TABULAR_FEATURE_DIM
from .graphsage import GraphSAGEModel
from .tabtransformer import TabTransformerModel
from .model import ClassifierModel, MLPHead, create_default_model
from .embeddings import CorridorEmbeddingPipeline


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    e = np.exp(x)
    return e / (1.0 + e)


def _compute_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Compute ROC-AUC via the trapezoidal rule."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_scores = np.asarray(y_scores, dtype=np.float64)
    if len(np.unique(y_true)) < 2:
        return 0.5
    order = np.argsort(-y_scores)
    y_sorted = y_true[order]
    n_pos = float(np.sum(y_true))
    n_neg = float(len(y_true) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    tpr_vals = np.cumsum(y_sorted) / n_pos
    fpr_vals = np.cumsum(1.0 - y_sorted) / n_neg
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    auc = float(_trapz(tpr_vals, fpr_vals))
    return max(0.0, min(1.0, abs(auc)))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class TrainingConfig:
    """Hyper-parameter configuration for the C1 training pipeline.

    Attributes
    ----------
    n_epochs:
        Number of full passes over the training data.
    batch_size:
        Mini-batch size for gradient updates.
    learning_rate:
        Initial learning rate for gradient-based optimisation.
    alpha:
        Asymmetric BCE weight for the positive (failure) class.
    k_neighbors_train:
        GraphSAGE neighbourhood sample size during training.
    k_neighbors_infer:
        GraphSAGE neighbourhood sample size at inference.
    val_split:
        Fraction of data held out for validation / threshold calibration.
    random_seed:
        Seed for all RNG operations to ensure reproducibility.
    """

    n_epochs: int = 50
    batch_size: int = 256
    learning_rate: float = 1e-3
    alpha: float = 0.7
    k_neighbors_train: int = 10
    k_neighbors_infer: int = 5
    val_split: float = 0.2
    random_seed: int = 42


# ---------------------------------------------------------------------------
# TrainingPipeline
# ---------------------------------------------------------------------------

class TrainingPipeline:
    """9-stage end-to-end training pipeline for the C1 Failure Classifier.

    Each stage is exposed as a standalone method so that individual stages
    can be re-run independently (e.g., to recalibrate thresholds without
    retraining the full model).

    Parameters
    ----------
    config:
        :class:`TrainingConfig` instance.  Defaults to the standard
        production configuration when not provided.
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self.config = config or TrainingConfig()
        self._rng = np.random.default_rng(seed=self.config.random_seed)

    # ------------------------------------------------------------------
    # Stage 1 — Data validation
    # ------------------------------------------------------------------

    def stage1_data_validation(self, data: List[dict]) -> List[dict]:
        """Validate and clean the raw payment dataset.

        Removes records with missing critical fields and coerces types.
        Logs the number of dropped records.

        Required fields: ``uetr``, ``sending_bic``, ``receiving_bic``,
        ``amount_usd``, ``timestamp``, ``currency_pair``, ``label``.

        Parameters
        ----------
        data:
            Raw payment records as a list of dicts.

        Returns
        -------
        List[dict]
            Validated records.
        """
        required = {"uetr", "sending_bic", "receiving_bic", "amount_usd",
                    "timestamp", "currency_pair", "label"}
        valid: List[dict] = []
        dropped = 0

        for record in data:
            if not required.issubset(record.keys()):
                dropped += 1
                continue
            try:
                record["amount_usd"] = float(record["amount_usd"])
                record["timestamp"] = float(record["timestamp"])
                record["label"] = int(record["label"])
            except (ValueError, TypeError):
                dropped += 1
                continue
            if record["amount_usd"] < 0:
                dropped += 1
                continue
            if record["label"] not in (0, 1):
                dropped += 1
                continue
            valid.append(record)

        logger.info(
            "stage1_data_validation: %d valid, %d dropped", len(valid), dropped
        )
        return valid

    # ------------------------------------------------------------------
    # Stage 2 — Graph construction
    # ------------------------------------------------------------------

    def stage2_graph_construction(self, data: List[dict]) -> BICGraphBuilder:
        """Build the BIC-pair multigraph from validated payment records.

        Parameters
        ----------
        data:
            Validated payment records (output of :meth:`stage1_data_validation`).

        Returns
        -------
        BICGraphBuilder
            Populated graph builder.
        """
        builder = BICGraphBuilder()
        for record in data:
            edge = PaymentEdge(
                uetr=str(record.get("uetr", "")),
                sending_bic=str(record["sending_bic"]),
                receiving_bic=str(record["receiving_bic"]),
                amount_usd=float(record["amount_usd"]),
                currency_pair=str(record["currency_pair"]),
                timestamp=float(record["timestamp"]),
                features={"failed": bool(record.get("label", 0))},
            )
            builder.add_payment(edge)

        graph = builder.build_graph()
        logger.info(
            "stage2_graph_construction: %d nodes, %d edges",
            len(graph.nodes), len(graph.edges),
        )
        return builder

    # ------------------------------------------------------------------
    # Stage 3 — Feature extraction
    # ------------------------------------------------------------------

    def stage3_feature_extraction(
        self,
        data: List[dict],
        graph: BICGraphBuilder,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract tabular feature matrix and label vector.

        Parameters
        ----------
        data:
            Validated payment records.
        graph:
            Populated :class:`BICGraphBuilder`.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            - ``X`` of shape ``(n, 88)`` — tabular feature matrix.
            - ``y`` of shape ``(n,)``    — binary labels.
        """
        pipeline = FeaturePipeline(graph_builder=graph)
        X_rows: List[np.ndarray] = []
        y_rows: List[int] = []

        for record in data:
            features = pipeline.extract_all(record)
            X_rows.append(features["tabular"])
            y_rows.append(int(record["label"]))

        X = np.stack(X_rows, axis=0).astype(np.float64)
        y = np.array(y_rows, dtype=np.float64)
        logger.info("stage3_feature_extraction: X=%s, y=%s", X.shape, y.shape)
        return X, y

    # ------------------------------------------------------------------
    # Stage 4 — Train/validation split
    # ------------------------------------------------------------------

    def stage4_train_val_split(
        self, X: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Randomly split data into train and validation sets.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(n, 88)``.
        y:
            Label vector of shape ``(n,)``.

        Returns
        -------
        Tuple
            ``(X_train, X_val, y_train, y_val)`` where val size is
            ``config.val_split * n``.
        """
        n = len(y)
        n_val = max(1, int(n * self.config.val_split))
        indices = self._rng.permutation(n)
        val_idx = indices[:n_val]
        train_idx = indices[n_val:]

        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        logger.info(
            "stage4_train_val_split: train=%d, val=%d", len(train_idx), len(val_idx)
        )
        return X_train, X_val, y_train, y_val

    # ------------------------------------------------------------------
    # Stage 5 — GraphSAGE pre-training
    # ------------------------------------------------------------------

    def stage5_graphsage_pretrain(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> GraphSAGEModel:
        """Pre-train the GraphSAGE model using a temporary linear classification head.

        Runs a mini-batch SGD loop with a temporary ``(384→1)`` linear head on
        top of the GraphSAGE output.  Gradients for GraphSAGE layer weights are
        computed analytically via :meth:`~GraphSAGEModel.backward_empty_neighbors`
        (empty-neighbour approximation — no graph connectivity available in the
        tabular batch setting).  The temporary head is discarded after pre-training.

        Parameters
        ----------
        X_train:
            Training feature matrix of shape ``(n_train, 88)``.
        y_train:
            Training labels of shape ``(n_train,)``.

        Returns
        -------
        GraphSAGEModel
            Initialised and pre-trained GraphSAGE model.
        """
        model = GraphSAGEModel()
        n = len(y_train)
        # Temporary linear head: (output_dim → 1)
        rng = np.random.default_rng(seed=self.config.random_seed)
        limit = np.sqrt(6.0 / (model.output_dim + 1))
        W_head = rng.uniform(-limit, limit, size=(model.output_dim, 1)).astype(np.float64)
        b_head = np.zeros(1, dtype=np.float64)

        pre_epochs = min(5, self.config.n_epochs)
        lr = self.config.learning_rate
        alpha = self.config.alpha
        batch_size = self.config.batch_size

        for epoch in range(pre_epochs):
            total_loss = 0.0
            indices = rng.permutation(n)
            n_batches = max(1, n // batch_size)
            for b in range(n_batches):
                batch_idx = indices[b * batch_size: (b + 1) * batch_size]
                for i in batch_idx:
                    node_feat = X_train[i][:model.input_dim]
                    sage_emb = model.forward(node_feat, [], [])
                    logit = float((sage_emb @ W_head + b_head).item())
                    p = _sigmoid(logit)
                    y = float(y_train[i])
                    loss = ClassifierModel.asymmetric_bce_loss(y, p, alpha)
                    total_loss += loss

                    # Gradient through temporary head
                    d_logit = (1.0 - alpha) * (1.0 - y) * p - alpha * y * (1.0 - p)
                    dW_head = sage_emb[:, None] * d_logit   # (384, 1)
                    db_head = np.array([d_logit])
                    d_sage_emb = W_head[:, 0] * d_logit     # (384,)

                    # Update GraphSAGE weights
                    model.backward_empty_neighbors(node_feat, d_sage_emb, lr)
                    W_head -= lr * dW_head
                    b_head -= lr * db_head

            avg_loss = total_loss / max(1, n)
            logger.debug("stage5 pre-train epoch %d — avg_loss=%.5f", epoch + 1, avg_loss)

        logger.info(
            "stage5_graphsage_pretrain: %d pre-train epochs complete", pre_epochs
        )
        return model

    # ------------------------------------------------------------------
    # Stage 6 — TabTransformer pre-training
    # ------------------------------------------------------------------

    def stage6_tabtransformer_pretrain(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> TabTransformerModel:
        """Pre-train the TabTransformer on the tabular feature matrix.

        Runs a lightweight supervised pre-training loop (5 epochs) with a
        temporary ``(88→1)`` linear head.  Analytical backpropagation is used
        for the output projection (``W_out``) and FFN sub-layers of each
        transformer block via :meth:`~TabTransformerModel.backward`.

        Parameters
        ----------
        X_train:
            Training feature matrix ``(n_train, 88)``.
        y_train:
            Training labels ``(n_train,)``.

        Returns
        -------
        TabTransformerModel
            Initialised and pre-trained TabTransformer model.
        """
        model = TabTransformerModel()
        n = len(y_train)
        rng = np.random.default_rng(seed=self.config.random_seed + 1)
        limit = np.sqrt(6.0 / (model.output_dim + 1))
        W_head = rng.uniform(-limit, limit, size=(model.output_dim, 1)).astype(np.float64)
        b_head = np.zeros(1, dtype=np.float64)

        pre_epochs = min(5, self.config.n_epochs)
        lr = self.config.learning_rate
        alpha = self.config.alpha
        batch_size = self.config.batch_size

        for epoch in range(pre_epochs):
            total_loss = 0.0
            indices = rng.permutation(n)
            n_batches = max(1, n // batch_size)
            for b in range(n_batches):
                batch_idx = indices[b * batch_size: (b + 1) * batch_size]
                for i in batch_idx:
                    x_tab = X_train[i]
                    tab_emb = model.forward(x_tab)
                    logit = float((tab_emb @ W_head + b_head).item())
                    p = _sigmoid(logit)
                    y = float(y_train[i])
                    loss = ClassifierModel.asymmetric_bce_loss(y, p, alpha)
                    total_loss += loss

                    # Gradient through temporary head
                    d_logit = (1.0 - alpha) * (1.0 - y) * p - alpha * y * (1.0 - p)
                    dW_head = tab_emb[:, None] * d_logit    # (88, 1)
                    db_head = np.array([d_logit])
                    d_tab_emb = W_head[:, 0] * d_logit      # (88,)

                    # Update TabTransformer weights
                    model.backward(x_tab, d_tab_emb, lr)
                    W_head -= lr * dW_head
                    b_head -= lr * db_head

            avg_loss = total_loss / max(1, n)
            logger.debug("stage6 pre-train epoch %d — avg_loss=%.5f", epoch + 1, avg_loss)

        logger.info(
            "stage6_tabtransformer_pretrain: %d pre-train epochs complete", pre_epochs
        )
        return model

    # ------------------------------------------------------------------
    # Stage 7 — Joint training
    # ------------------------------------------------------------------

    def stage7_joint_training(
        self,
        graphsage: GraphSAGEModel,
        tabtransformer: TabTransformerModel,
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> ClassifierModel:
        """Joint end-to-end SGD training of GraphSAGE + TabTransformer + MLP.

        Assembles the :class:`ClassifierModel` from pre-trained sub-models
        and runs ``n_epochs`` of mini-batch SGD with the asymmetric BCE loss
        (``alpha=0.7``).  Backpropagation is fully analytical for the MLP head
        and analytically approximate for the encoder components (L2-normalisation
        and attention Jacobians are treated as identity matrices).

        Best-AUC checkpoint tracking is performed on the training set (no held-out
        set is available at this stage — validation is done in stage 8).

        Parameters
        ----------
        graphsage:
            Pre-trained :class:`GraphSAGEModel`.
        tabtransformer:
            Pre-trained :class:`TabTransformerModel`.
        X_train:
            Training feature matrix ``(n_train, 88)``.
        y_train:
            Training labels ``(n_train,)``.

        Returns
        -------
        ClassifierModel
            Assembled and jointly-trained classifier (best-AUC checkpoint).
        """
        mlp = MLPHead()
        model = ClassifierModel(
            graphsage=graphsage,
            tabtransformer=tabtransformer,
            mlp=mlp,
        )

        n = len(y_train)
        n_batches = max(1, n // self.config.batch_size)
        lr = self.config.learning_rate
        alpha = self.config.alpha
        graphsage_input_dim = graphsage.input_dim

        logger.info(
            "stage7_joint_training: %d samples, %d batches/epoch, %d epochs",
            n, n_batches, self.config.n_epochs,
        )

        # Best-AUC checkpoint (in memory)
        best_auc: float = -1.0
        best_mlp_w: Optional[dict] = None
        best_sage_w: Optional[dict] = None
        best_tab_w: Optional[dict] = None

        for epoch in range(self.config.n_epochs):
            total_loss = 0.0
            indices = self._rng.permutation(n)

            for b in range(n_batches):
                batch_idx = indices[b * self.config.batch_size: (b + 1) * self.config.batch_size]
                for i in batch_idx:
                    x_tab = X_train[i]
                    tab_emb = tabtransformer.forward(x_tab)
                    node_feat = x_tab[:graphsage_input_dim]
                    sage_emb = graphsage.forward(node_feat, [], [])
                    fused = np.concatenate([sage_emb, tab_emb])
                    prob = mlp.forward(fused)
                    y = float(y_train[i])

                    total_loss += ClassifierModel.asymmetric_bce_loss(y, prob, alpha=alpha)

                    # --- Backprop through MLP head ---
                    d_fused = mlp.backward(fused, y, prob, alpha, lr)

                    # --- Backprop into GraphSAGE (first 384 dims of d_fused) ---
                    d_sage = d_fused[:graphsage.output_dim]
                    graphsage.backward_empty_neighbors(node_feat, d_sage, lr)

                    # --- Backprop into TabTransformer (last 88 dims of d_fused) ---
                    d_tab = d_fused[graphsage.output_dim:]
                    tabtransformer.backward(x_tab, d_tab, lr)

            avg_loss = total_loss / max(1, n)

            # Compute training-set AUC for checkpoint selection
            scores: List[float] = []
            for i in range(n):
                x_tab = X_train[i]
                tab_emb = tabtransformer.forward(x_tab)
                node_feat = x_tab[:graphsage_input_dim]
                sage_emb = graphsage.forward(node_feat, [], [])
                fused = np.concatenate([sage_emb, tab_emb])
                scores.append(mlp.forward(fused))
            auc = _compute_auc(y_train, np.array(scores))

            logger.debug(
                "Joint training epoch %d — avg_loss=%.5f  train_auc=%.4f",
                epoch + 1, avg_loss, auc,
            )

            # Save best checkpoint
            if auc > best_auc:
                best_auc = auc
                best_mlp_w = mlp.get_weights()
                best_sage_w = graphsage.get_weights_dict()
                best_tab_w = tabtransformer.get_weights_dict()

        # Restore best checkpoint
        if best_mlp_w is not None:
            mlp.set_weights(best_mlp_w)
            graphsage.set_weights_dict(best_sage_w)  # type: ignore[arg-type]
            tabtransformer.set_weights_dict(best_tab_w)  # type: ignore[arg-type]
            logger.info(
                "stage7_joint_training: restored best checkpoint (train_auc=%.4f)", best_auc
            )

        logger.info("stage7_joint_training: complete")
        return model

    # ------------------------------------------------------------------
    # Stage 8 — Threshold calibration
    # ------------------------------------------------------------------

    def stage8_threshold_calibration(
        self,
        model: ClassifierModel,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> float:
        """Compute F2-optimal decision threshold on the validation set.

        Parameters
        ----------
        model:
            Trained :class:`ClassifierModel`.
        X_val:
            Validation feature matrix ``(n_val, 88)``.
        y_val:
            Validation labels ``(n_val,)``.

        Returns
        -------
        float
            F2-optimal threshold in ``[0, 1]``.
        """
        scores: List[float] = []
        for x_tab in X_val:
            tab_emb = model.tabtransformer.forward(x_tab)
            node_feat = x_tab[:8]
            sage_emb = model.graphsage.forward(node_feat, [], [])
            fused = np.concatenate([sage_emb, tab_emb])
            scores.append(model.mlp.forward(fused))

        y_scores = np.array(scores, dtype=np.float64)
        threshold = ClassifierModel.select_f2_threshold(y_val, y_scores)
        logger.info("stage8_threshold_calibration: threshold=%.4f", threshold)
        return threshold

    # ------------------------------------------------------------------
    # Stage 9 — Embedding generation
    # ------------------------------------------------------------------

    def stage9_embedding_generation(
        self,
        model: ClassifierModel,
        data: List[dict],
    ) -> CorridorEmbeddingPipeline:
        """Build the corridor embedding store from the trained model.

        Parameters
        ----------
        model:
            Trained :class:`ClassifierModel`.
        data:
            Full payment dataset (train + val).

        Returns
        -------
        CorridorEmbeddingPipeline
            Populated in-memory embedding store.
        """
        pipeline = CorridorEmbeddingPipeline(redis_client=None)
        count = pipeline.rebuild_all(data, model)
        logger.info("stage9_embedding_generation: %d embeddings generated", count)
        return pipeline

    # ------------------------------------------------------------------
    # run — orchestrate all 9 stages
    # ------------------------------------------------------------------

    def run(
        self, data: List[dict]
    ) -> Tuple[ClassifierModel, float, CorridorEmbeddingPipeline]:
        """Execute all 9 pipeline stages sequentially with timing logs.

        Parameters
        ----------
        data:
            Raw payment records.

        Returns
        -------
        Tuple
            ``(trained_model, f2_threshold, embedding_pipeline)``
        """
        timings: Dict[str, float] = {}

        def _run_stage(name: str, fn, *args):
            t0 = time.perf_counter()
            result = fn(*args)
            elapsed = time.perf_counter() - t0
            timings[name] = elapsed
            logger.info("%-45s %.3f s", name + ":", elapsed)
            return result

        validated = _run_stage("stage1_data_validation", self.stage1_data_validation, data)
        graph = _run_stage("stage2_graph_construction", self.stage2_graph_construction, validated)
        X, y = _run_stage("stage3_feature_extraction", self.stage3_feature_extraction, validated, graph)
        X_train, X_val, y_train, y_val = _run_stage("stage4_train_val_split", self.stage4_train_val_split, X, y)
        graphsage = _run_stage("stage5_graphsage_pretrain", self.stage5_graphsage_pretrain, X_train, y_train)
        tabtransformer = _run_stage("stage6_tabtransformer_pretrain", self.stage6_tabtransformer_pretrain, X_train, y_train)
        model = _run_stage("stage7_joint_training", self.stage7_joint_training, graphsage, tabtransformer, X_train, y_train)
        threshold = _run_stage("stage8_threshold_calibration", self.stage8_threshold_calibration, model, X_val, y_val)
        emb_pipeline = _run_stage("stage9_embedding_generation", self.stage9_embedding_generation, model, validated)

        total = sum(timings.values())
        logger.info("TrainingPipeline.run complete — total %.3f s", total)
        return model, threshold, emb_pipeline
