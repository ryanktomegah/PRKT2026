"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

training_torch.py — PyTorch training pipeline for C1 neural components.
Stages 1–4 are delegated to the existing NumPy TrainingPipeline.
Stages 5–7 (GraphSAGE pre-train, TabTransformer pre-train, joint training)
use DataLoader-based mini-batches for 100K+ sample scalability.
LightGBM (stage 5b) is unchanged.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .graph_builder import BICGraphBuilder
from .graphsage_torch import GraphSAGETorch
from .model_torch import ClassifierModelTorch, MLPHeadTorch
from .tabtransformer_torch import TabTransformerTorch
from .training import TrainingConfig, TrainingPipeline, _compute_auc

logger = logging.getLogger(__name__)

# pos_weight for BCEWithLogitsLoss: α/(1-α) = 0.7/0.3 = 7/3 ≈ 2.3333
# Equivalent gradient direction to the NumPy asymmetric BCE (α=0.7)
_POS_WEIGHT = torch.tensor([7.0 / 3.0])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_tensor(arr: np.ndarray, dtype=torch.float32) -> torch.Tensor:
    return torch.tensor(arr, dtype=dtype)


def _eval_auc_torch(
    model: ClassifierModelTorch,
    X: np.ndarray,
    y: np.ndarray,
    neighbor_feats: Optional[torch.Tensor] = None,
) -> float:
    """Compute AUC for a ClassifierModelTorch on numpy arrays."""
    model.eval()
    with torch.no_grad():
        node_feat = _to_tensor(X[:, :8])
        tab_feat = _to_tensor(X[:, 8:])
        logits = model(node_feat, tab_feat, neighbor_feats).squeeze(1)
        scores = torch.sigmoid(logits).cpu().numpy()
    return _compute_auc(y, scores)


def _build_neighbor_tensor(
    bics: List[str],
    graph: BICGraphBuilder,
    k: int,
    input_dim: int = 8,
) -> torch.Tensor:
    """Build a (N, k, input_dim) float32 tensor of neighbor node features.

    For each BIC, retrieves up to ``k`` neighbors by outbound USD volume via
    :meth:`BICGraphBuilder.get_neighbors`, then looks up their 8-dim node
    feature vectors via :meth:`BICGraphBuilder.get_node_features`.  Pads
    with zeros for any missing neighbors (cold-start safe — no exceptions).

    Performance: pre-computes a lookup table over unique BICs only (typically
    ~75 unique values), then uses vectorised numpy indexing over the full N
    records — avoiding an O(N) Python loop that stalls on large datasets.

    Parameters
    ----------
    bics:
        List of N sending BIC codes (one per training record).
    graph:
        Populated :class:`BICGraphBuilder`.
    k:
        Number of neighbors to sample per BIC.
    input_dim:
        Node feature dimensionality (default 8).

    Returns
    -------
    torch.Tensor
        Shape ``(N, k, input_dim)``, dtype ``float32``.
    """
    unique_bics = list(dict.fromkeys(bics))  # preserve order, deduplicate
    bic_to_idx = {bic: i for i, bic in enumerate(unique_bics)}

    # Build lookup table over unique BICs only (e.g. 75, not 800K)
    lookup = np.zeros((len(unique_bics), k, input_dim), dtype=np.float32)
    for i, bic in enumerate(unique_bics):
        neighbors = graph.get_neighbors(bic, k)
        for j, nbr in enumerate(neighbors):
            lookup[i, j] = graph.get_node_features(nbr)

    # Vectorised mapping: 800K records → their unique-BIC index
    indices = np.array([bic_to_idx.get(bic, 0) for bic in bics], dtype=np.intp)
    return torch.tensor(lookup[indices], dtype=torch.float32)


# ---------------------------------------------------------------------------
# TrainingPipelineTorch
# ---------------------------------------------------------------------------


class TrainingPipelineTorch:
    """PyTorch training pipeline for C1 neural components (stages 5–7).

    Stages 1–4 (data validation, graph construction, feature extraction,
    train/val split) are delegated to the existing :class:`TrainingPipeline`.

    Parameters
    ----------
    config:
        :class:`TrainingConfig` instance (default production config).
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self.config = config or TrainingConfig()
        self.feature_scaler = None  # fitted StandardScaler, set by train_torch

    # ------------------------------------------------------------------
    # Stage 5 — GraphSAGE pre-training (PyTorch)
    # ------------------------------------------------------------------

    def stage5_graphsage_pretrain_torch(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        graph: Optional[BICGraphBuilder] = None,
        bic_train: Optional[List[str]] = None,
    ) -> GraphSAGETorch:
        """Pre-train the GraphSAGE model for 5 epochs with a temporary linear head.

        Uses a ``(384→1)`` temporary head and :class:`BCEWithLogitsLoss` with
        ``pos_weight=7/3`` (equivalent to α=0.7 asymmetric BCE).  When
        ``graph`` and ``bic_train`` are provided, real BIC corridor neighbors
        are used for aggregation; otherwise zero aggregation (legacy path).

        Parameters
        ----------
        X_train:
            Training feature matrix ``(n_train, 96)``.
        y_train:
            Training labels ``(n_train,)``.
        graph:
            Optional populated :class:`BICGraphBuilder` for neighbor lookup.
        bic_train:
            Optional list of sending BIC codes (one per training record).

        Returns
        -------
        GraphSAGETorch
            Pre-trained GraphSAGE module.
        """
        graphsage = GraphSAGETorch()
        temp_head = nn.Linear(graphsage.output_dim, 1)
        nn.init.xavier_uniform_(temp_head.weight)

        node_feats = _to_tensor(X_train[:, :graphsage.input_dim])
        labels = _to_tensor(y_train).unsqueeze(1)

        use_graph = graph is not None and bic_train is not None
        if use_graph:
            nbr_tensor = _build_neighbor_tensor(bic_train, graph, self.config.k_neighbors_train)
            dataset = TensorDataset(node_feats, labels, nbr_tensor)
        else:
            dataset = TensorDataset(node_feats, labels)
        loader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

        optimizer = torch.optim.Adam(
            list(graphsage.parameters()) + list(temp_head.parameters()),
            lr=self.config.learning_rate,
            betas=(0.9, 0.999),
            eps=1e-8,
        )
        criterion = nn.BCEWithLogitsLoss(pos_weight=_POS_WEIGHT)

        pre_epochs = min(5, self.config.n_epochs)
        graphsage.train()
        temp_head.train()

        for epoch in range(pre_epochs):
            total_loss = 0.0
            for batch in loader:
                x_batch, y_batch = batch[0], batch[1]
                nbr_batch = batch[2] if use_graph else None
                optimizer.zero_grad()
                emb = graphsage(x_batch, nbr_batch)    # (B, 384)
                logits = temp_head(emb)                # (B, 1)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(x_batch)
            avg = total_loss / len(y_train)
            logger.debug("stage5_torch pretrain epoch %d — avg_loss=%.5f", epoch + 1, avg)

        logger.info("stage5_graphsage_pretrain_torch: %d epochs complete", pre_epochs)
        graphsage.eval()
        return graphsage

    # ------------------------------------------------------------------
    # Stage 6 — TabTransformer pre-training (PyTorch)
    # ------------------------------------------------------------------

    def stage6_tabtransformer_pretrain_torch(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> TabTransformerTorch:
        """Pre-train the TabTransformer for 5 epochs with a temporary linear head.

        Uses a ``(88→1)`` temporary head on the 88-dim output and
        :class:`BCEWithLogitsLoss` with ``pos_weight=7/3``.

        Parameters
        ----------
        X_train:
            Training feature matrix ``(n_train, 96)``.
        y_train:
            Training labels ``(n_train,)``.

        Returns
        -------
        TabTransformerTorch
            Pre-trained TabTransformer module.
        """
        tabtransformer = TabTransformerTorch(input_dim=88)
        temp_head = nn.Linear(tabtransformer.output_dim, 1)
        nn.init.xavier_uniform_(temp_head.weight)

        tab_feats = _to_tensor(X_train[:, 8:])
        labels = _to_tensor(y_train).unsqueeze(1)

        dataset = TensorDataset(tab_feats, labels)
        loader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

        optimizer = torch.optim.Adam(
            list(tabtransformer.parameters()) + list(temp_head.parameters()),
            lr=self.config.learning_rate,
            betas=(0.9, 0.999),
            eps=1e-8,
        )
        criterion = nn.BCEWithLogitsLoss(pos_weight=_POS_WEIGHT)

        pre_epochs = min(5, self.config.n_epochs)
        tabtransformer.train()
        temp_head.train()

        for epoch in range(pre_epochs):
            total_loss = 0.0
            for x_batch, y_batch in loader:
                optimizer.zero_grad()
                emb = tabtransformer(x_batch)          # (B, 88)
                logits = temp_head(emb)                # (B, 1)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(x_batch)
            avg = total_loss / len(y_train)
            logger.debug("stage6_torch pretrain epoch %d — avg_loss=%.5f", epoch + 1, avg)

        logger.info("stage6_tabtransformer_pretrain_torch: %d epochs complete", pre_epochs)
        tabtransformer.eval()
        return tabtransformer

    # ------------------------------------------------------------------
    # Stage 7 — Joint training (PyTorch)
    # ------------------------------------------------------------------

    def stage7_joint_training_torch(
        self,
        graphsage: GraphSAGETorch,
        tabtransformer: TabTransformerTorch,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        graph: Optional[BICGraphBuilder] = None,
        bic_train: Optional[List[str]] = None,
        bic_val: Optional[List[str]] = None,
    ) -> ClassifierModelTorch:
        """Joint end-to-end training with best-AUC checkpoint.

        Assembles :class:`ClassifierModelTorch` from pre-trained sub-models
        and trains for ``n_epochs`` using Adam with asymmetric BCE loss.
        Best-AUC checkpoint on the validation set (or training set if val
        is not provided) is restored before returning.  When ``graph`` and
        ``bic_train`` are provided, real BIC corridor neighbors are wired
        through the GraphSAGE aggregation path.

        Parameters
        ----------
        graphsage:
            Pre-trained :class:`GraphSAGETorch`.
        tabtransformer:
            Pre-trained :class:`TabTransformerTorch`.
        X_train, y_train:
            Training data ``(n_train, 96)`` and labels.
        X_val, y_val:
            Optional validation data for checkpoint selection.
        graph:
            Optional populated :class:`BICGraphBuilder` for neighbor lookup.
        bic_train:
            Optional list of sending BIC codes for training records.
        bic_val:
            Optional list of sending BIC codes for validation records.

        Returns
        -------
        ClassifierModelTorch
            Assembled and jointly-trained classifier (best-AUC checkpoint).
        """
        mlp_head = MLPHeadTorch()
        model = ClassifierModelTorch(
            graphsage=graphsage,
            tabtransformer=tabtransformer,
            mlp_head=mlp_head,
        )

        node_feats = _to_tensor(X_train[:, :8])
        tab_feats = _to_tensor(X_train[:, 8:])
        labels = _to_tensor(y_train).unsqueeze(1)

        use_graph = graph is not None and bic_train is not None
        if use_graph:
            nbr_train = _build_neighbor_tensor(bic_train, graph, self.config.k_neighbors_train)
            dataset = TensorDataset(node_feats, tab_feats, labels, nbr_train)
        else:
            dataset = TensorDataset(node_feats, tab_feats, labels)
        loader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=self.config.learning_rate,
            betas=(0.9, 0.999),
            eps=1e-8,
        )
        criterion = nn.BCEWithLogitsLoss(pos_weight=_POS_WEIGHT)

        # Checkpoint state
        best_auc: float = -1.0
        best_state: Optional[dict] = None

        ckpt_X = X_val if X_val is not None else X_train
        ckpt_y = y_val if y_val is not None else y_train
        ckpt_label = "val" if X_val is not None else "train"

        # Pre-compute neighbor tensor for checkpoint eval set
        if use_graph:
            ckpt_bics = bic_val if (bic_val is not None and X_val is not None) else bic_train
            ckpt_nbr: Optional[torch.Tensor] = _build_neighbor_tensor(
                ckpt_bics, graph, self.config.k_neighbors_infer
            )
        else:
            ckpt_nbr = None

        logger.info(
            "stage7_joint_training_torch: %d samples, %d epochs",
            len(y_train), self.config.n_epochs,
        )

        for epoch in range(self.config.n_epochs):
            model.train()
            total_loss = 0.0
            for batch in loader:
                nf_batch, tf_batch, y_batch = batch[0], batch[1], batch[2]
                nbr_batch = batch[3] if use_graph else None
                optimizer.zero_grad()
                logits = model(nf_batch, tf_batch, nbr_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(y_batch)

            avg_loss = total_loss / len(y_train)
            auc = _eval_auc_torch(model, ckpt_X, ckpt_y, ckpt_nbr)
            logger.info(
                "Joint training epoch %d/%d — avg_loss=%.5f  %s_auc=%.4f",
                epoch + 1, self.config.n_epochs, avg_loss, ckpt_label, auc,
            )

            if auc > best_auc:
                best_auc = auc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if best_state is not None:
            model.load_state_dict(best_state)
            logger.info(
                "stage7_joint_training_torch: restored best checkpoint (%s_auc=%.4f)",
                ckpt_label, best_auc,
            )

        model.eval()
        return model

    # ------------------------------------------------------------------
    # train_torch — orchestrate full pipeline
    # ------------------------------------------------------------------

    def train_torch(
        self,
        records: List[dict],
    ) -> ClassifierModelTorch:
        """Train C1 with PyTorch stages 5–7, reusing NumPy stages 1–4.

        Stages 1–4 (data validation, graph construction, feature extraction,
        train/val split) are executed by :class:`TrainingPipeline`.  Stages
        5–7 use PyTorch DataLoaders.  Stage 5b (LightGBM) is unchanged and
        attached to the returned model for the 50/50 ensemble.

        Parameters
        ----------
        records:
            Raw payment records (same format as :meth:`TrainingPipeline.run`).

        Returns
        -------
        ClassifierModelTorch
            Fully trained classifier with optional LightGBM attached.
        """
        numpy_pipeline = TrainingPipeline(config=self.config)

        t0 = time.perf_counter()
        validated = numpy_pipeline.stage1_data_validation(records)
        graph = numpy_pipeline.stage2_graph_construction(validated)
        X, y, bics = numpy_pipeline.stage3_feature_extraction(validated, graph)
        timestamps = np.array([float(r.get("timestamp_unix", 0.0)) for r in validated])
        X_train, X_val, y_train, y_val, bic_train, bic_val = numpy_pipeline.stage4_train_val_split(X, y, bics, timestamps)
        logger.info("Stages 1–4 complete in %.3f s", time.perf_counter() - t0)

        t0 = time.perf_counter()
        X_train, X_val = numpy_pipeline.stage3b_standard_scale(X_train, X_val)
        self.feature_scaler = numpy_pipeline._feature_scaler
        logger.info("Stage 3b (StandardScaler) complete in %.3f s", time.perf_counter() - t0)

        t0 = time.perf_counter()
        lgbm_model = numpy_pipeline.stage5b_lightgbm_pretrain(X_train[:, 8:], y_train)
        logger.info("Stage 5b (LightGBM) complete in %.3f s", time.perf_counter() - t0)

        t0 = time.perf_counter()
        graphsage = self.stage5_graphsage_pretrain_torch(X_train, y_train, graph, bic_train)
        logger.info("Stage 5 (GraphSAGE torch pretrain) complete in %.3f s", time.perf_counter() - t0)

        t0 = time.perf_counter()
        tabtransformer = self.stage6_tabtransformer_pretrain_torch(X_train, y_train)
        logger.info("Stage 6 (TabTransformer torch pretrain) complete in %.3f s", time.perf_counter() - t0)

        t0 = time.perf_counter()
        model = self.stage7_joint_training_torch(
            graphsage, tabtransformer, X_train, y_train, X_val, y_val, graph, bic_train, bic_val
        )
        logger.info("Stage 7 (joint training) complete in %.3f s", time.perf_counter() - t0)

        model.lgbm_model = lgbm_model
        logger.info("train_torch: complete")
        return model
