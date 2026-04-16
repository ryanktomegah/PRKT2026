"""
P4 Federated Learning — Local Ensemble Coordination

Coordinates PyTorch and LightGBM ensemble training locally.

Per architecture doc: "LightGBM: cannot be federated — trained locally only."

The ensemble uses a 50/50 blend of PyTorch and LightGBM predictions.
LightGBM is retrained locally after each federated learning round using the
updated PyTorch embeddings as features.

This local-only training ensures:
- LightGBM models never leave the bank (no transmission)
- Each bank's LightGBM adapts to local data characteristics
- The ensemble benefits from both global (PyTorch) and local (LightGBM) learning

Reference:
- Architecture doc: docs/models/federated-learning-architecture.md
- LightGBM documentation: https://lightgbm.readthedocs.io/
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

# Try to import LightGBM; provide helpful error if unavailable
try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    lgb = None  # type: ignore[assignment]
    logging.getLogger(__name__).warning(
        "LightGBM not available. Install with: pip install lightgbm"
    )

from lip.p12_federated_learning.constants import (
    ENSEMBLE_LGBM_WEIGHT,
    ENSEMBLE_PYTORCH_WEIGHT,
    LGBM_FORCE_COL_WISE,
    LGBM_LEARNING_RATE,
    LGBM_MAX_DEPTH,
    LGBM_NUM_LEAVES,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LocalEnsemble — PyTorch + LightGBM Coordinator
# =============================================================================


class LocalEnsemble:
    """
    Coordinate PyTorch and LightGBM ensemble locally.

    Manages the 50/50 ensemble of PyTorch and LightGBM predictions.
    LightGBM is retrained after each FL round using updated PyTorch embeddings.

    Parameters
    ----------
    lgbm_model:
        Pre-trained LightGBM classifier (can be None for lazy initialization).
    lgbm_params:
        LightGBM hyperparameters for retraining.

    Example
    -------
    >>> ensemble = LocalEnsemble()
    >>> ensemble.update_lgbm(pytorch_model, train_loader)
    >>> prob = ensemble.predict_ensemble(pytorch_model, sample_features)
    """

    def __init__(
        self,
        lgbm_model: lgb.LGBMClassifier | None = None,
        lgbm_params: dict[str, Any] | None = None,
    ) -> None:
        self.lgbm_model = lgbm_model

        if lgbm_params is None:
            lgbm_params = {
                "num_leaves": LGBM_NUM_LEAVES,
                "learning_rate": LGBM_LEARNING_RATE,
                "max_depth": LGBM_MAX_DEPTH,
                "force_col_wise": LGBM_FORCE_COL_WISE,
                "verbose": -1,
            }
        self.lgbm_params = lgbm_params

        logger.debug(
            f"LocalEnsemble initialized with lgbm_params={self.lgbm_params}"
        )

    def update_lgbm(
        self,
        pytorch_model: torch.nn.Module,
        data_loader: DataLoader,
    ) -> None:
        """
        Retrain local LightGBM using new PyTorch embeddings as features.

        Extracts embeddings from the PyTorch model and uses them as features
        for LightGBM. This allows LightGBM to benefit from federated PyTorch
        training while keeping all LightGBM training local.

        Parameters
        ----------
        pytorch_model:
            PyTorch model (FederatedModel or equivalent).
        data_loader:
            Training DataLoader.
        """
        if not HAS_LGBM:
            logger.warning("LightGBM not available, skipping update")
            return

        if self.lgbm_model is None:
            # Initialize empty model for first training
            self.lgbm_model = lgb.LGBMClassifier(**self.lgbm_params)

        # Extract embeddings from PyTorch model
        embeddings = []
        labels = []

        pytorch_model.eval()
        with torch.no_grad():
            for batch in data_loader:
                node_feat, tab_feat, neighbor_feats, label = batch

                # Get embeddings from PyTorch model
                # For FederatedModel, we need to extract local + shared representations
                # We'll access the internal structure to get the embeddings
                h2, tab_emb = pytorch_model.local(node_feat, tab_feat, neighbor_feats)

                # Concatenate local embeddings
                emb = torch.cat([h2, tab_emb], dim=1)  # (B, 384 + 256 = 640)
                embeddings.append(emb.cpu().numpy())
                labels.append(label.cpu().numpy())

        X = np.vstack(embeddings)
        y = np.concatenate(labels)

        # Retrain local LightGBM on new embeddings
        self.lgbm_model.fit(X, y, **self.lgbm_params)

        logger.debug(
            f"LightGBM retrained on {len(X):,} samples, "
            f"accuracy={self.lgbm_model.score(X, y):.4f}"
        )

    def predict_ensemble(
        self,
        pytorch_model: torch.nn.Module,
        node_feat: torch.Tensor,
        tab_feat: torch.Tensor,
        neighbor_feats: torch.Tensor | None = None,
    ) -> float:
        """
        Predict using 50/50 ensemble of PyTorch and LightGBM.

        Parameters
        ----------
        pytorch_model:
            PyTorch model.
        node_feat:
            Node features, shape (8,) or (B, 8).
        tab_feat:
            Tabular features, shape (88,) or (B, 88).
        neighbor_feats:
            Optional neighbor features, shape (k, 8) or (B, k, 8).

        Returns
        -------
        float
            Ensemble prediction (probability of failure).
        """
        # PyTorch prediction
        pytorch_model.eval()
        with torch.no_grad():
            # Handle both single sample and batch inputs
            if node_feat.dim() == 1:
                node_feat = node_feat.unsqueeze(0)
            if tab_feat.dim() == 1:
                tab_feat = tab_feat.unsqueeze(0)
            if neighbor_feats is not None and neighbor_feats.dim() == 2:
                neighbor_feats = neighbor_feats.unsqueeze(0)

            pt_logit = pytorch_model(node_feat, tab_feat, neighbor_feats)
            pt_prob = torch.sigmoid(pt_logit).item()

        # LightGBM prediction (if model exists)
        if self.lgbm_model is not None:
            # Get embeddings for LightGBM
            with torch.no_grad():
                h2, tab_emb = pytorch_model.local(node_feat, tab_feat, neighbor_feats)
                emb = torch.cat([h2, tab_emb], dim=1).numpy().reshape(1, -1)

            lgbm_prob = self.lgbm_model.predict_proba(emb)[0, 1]
        else:
            lgbm_prob = pt_prob  # Fall back to PyTorch only

        # 50/50 ensemble
        ensemble_prob = (
            ENSEMBLE_PYTORCH_WEIGHT * pt_prob
            + ENSEMBLE_LGBM_WEIGHT * lgbm_prob
        )

        return ensemble_prob

    def predict_batch_ensemble(
        self,
        pytorch_model: torch.nn.Module,
        node_feat: torch.Tensor,
        tab_feat: torch.Tensor,
        neighbor_feats: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Predict using 50/50 ensemble for a batch of samples.

        Parameters
        ----------
        pytorch_model:
            PyTorch model.
        node_feat:
            Node features, shape (B, 8).
        tab_feat:
            Tabular features, shape (B, 88).
        neighbor_feats:
            Optional neighbor features, shape (B, k, 8).

        Returns
        -------
        torch.Tensor
            Batch of ensemble predictions, shape (B,).
        """
        # PyTorch prediction
        pytorch_model.eval()
        with torch.no_grad():
            pt_logit = pytorch_model(node_feat, tab_feat, neighbor_feats)
            pt_prob = torch.sigmoid(pt_logit).squeeze(-1)  # (B,)

        # LightGBM prediction (if model exists)
        if self.lgbm_model is not None:
            with torch.no_grad():
                h2, tab_emb = pytorch_model.local(node_feat, tab_feat, neighbor_feats)
                emb = torch.cat([h2, tab_emb], dim=1).numpy()  # (B, 640)

            lgbm_prob = self.lgbm_model.predict_proba(emb)[:, 1]
            lgbm_prob = torch.tensor(lgbm_prob, dtype=torch.float32)
        else:
            lgbm_prob = pt_prob

        # 50/50 ensemble
        ensemble_prob = (
            ENSEMBLE_PYTORCH_WEIGHT * pt_prob
            + ENSEMBLE_LGBM_WEIGHT * lgbm_prob
        )

        return ensemble_prob

    def get_lgbm_feature_importance(self) -> dict[str, float] | None:
        """
        Get LightGBM feature importance if model is trained.

        Returns
        -------
        dict[str, float] or None
            Feature importance scores (feature_name -> importance).
        """
        if self.lgbm_model is None:
            return None

        # LightGBM feature names (0-639 = embedding dimensions)
        feature_names = [f"emb_{i}" for i in range(640)]
        importances = self.lgbm_model.feature_importances_

        return dict(zip(feature_names, importances))


# =============================================================================
# Utility Functions
# =============================================================================


def initialize_local_lgbm(
    train_loader: DataLoader,
    pytorch_model: torch.nn.Module,
    lgbm_params: dict[str, Any] | None = None,
) -> lgb.LGBMClassifier:
    """
    Initialize and train a local LightGBM model.

    Parameters
    ----------
    train_loader:
        Training DataLoader.
    pytorch_model:
        PyTorch model to extract embeddings.
    lgbm_params:
        LightGBM hyperparameters.

    Returns
    -------
    lgb.LGBMClassifier
        Trained LightGBM model.
    """
    if not HAS_LGBM:
        raise ImportError(
            "LightGBM required. Install with: pip install lightgbm"
        )

    if lgbm_params is None:
        lgbm_params = {
            "num_leaves": LGBM_NUM_LEAVES,
            "learning_rate": LGBM_LEARNING_RATE,
            "max_depth": LGBM_MAX_DEPTH,
            "force_col_wise": LGBM_FORCE_COL_WISE,
            "verbose": -1,
        }

    # Extract embeddings
    embeddings = []
    labels = []

    pytorch_model.eval()
    with torch.no_grad():
        for batch in train_loader:
            node_feat, tab_feat, neighbor_feats, label = batch
            h2, tab_emb = pytorch_model.local(node_feat, tab_feat, neighbor_feats)
            emb = torch.cat([h2, tab_emb], dim=1)
            embeddings.append(emb.cpu().numpy())
            labels.append(label.cpu().numpy())

    X = np.vstack(embeddings)
    y = np.concatenate(labels)

    # Train LightGBM
    model = lgb.LGBMClassifier(**lgbm_params)
    model.fit(X, y)

    logger.info(
        f"Initialized local LightGBM: {len(X):,} samples, "
        f"accuracy={model.score(X, y):.4f}"
    )

    return model


def verify_ensemble_correctness(
    ensemble: LocalEnsemble,
    pytorch_model: torch.nn.Module,
    test_loader: DataLoader,
) -> dict[str, float]:
    """
    Verify ensemble predictions are within expected bounds.

    Parameters
    ----------
    ensemble:
        LocalEnsemble instance.
    pytorch_model:
        PyTorch model.
    test_loader:
        Test DataLoader.

    Returns
    -------
    dict
        Verification metrics including:
        - ensemble_range: min/max ensemble predictions
        - pytorch_range: min/max PyTorch predictions
        - lgbm_range: min/max LightGBM predictions (if available)
    """
    pytorch_preds = []
    lgbm_preds = []
    ensemble_preds = []

    pytorch_model.eval()
    ensemble.lgbm_model.eval() if ensemble.lgbm_model is not None else None

    with torch.no_grad():
        for batch in test_loader:
            node_feat, tab_feat, neighbor_feats, _ = batch

            # PyTorch predictions
            pt_logit = pytorch_model(node_feat, tab_feat, neighbor_feats)
            pt_prob = torch.sigmoid(pt_logit).squeeze(-1)
            pytorch_preds.extend(pt_prob.cpu().numpy().tolist())

            # LightGBM predictions
            if ensemble.lgbm_model is not None:
                h2, tab_emb = pytorch_model.local(node_feat, tab_feat, neighbor_feats)
                emb = torch.cat([h2, tab_emb], dim=1).numpy()
                lgbm_prob = ensemble.lgbm_model.predict_proba(emb)[:, 1]
                lgbm_preds.extend(lgbm_prob.tolist())

            # Ensemble predictions
            ens_pred = ensemble.predict_batch_ensemble(
                pytorch_model, node_feat, tab_feat, neighbor_feats
            )
            ensemble_preds.extend(ens_pred.cpu().numpy().tolist())

    result = {
        "ensemble_min": min(ensemble_preds),
        "ensemble_max": max(ensemble_preds),
        "pytorch_min": min(pytorch_preds),
        "pytorch_max": max(pytorch_preds),
    }

    if lgbm_preds:
        result["lgbm_min"] = min(lgbm_preds)
        result["lgbm_max"] = max(lgbm_preds)

    # Verify ensemble predictions are within [0, 1]
    result["ensemble_valid"] = all(0.0 <= p <= 1.0 for p in ensemble_preds)

    return result
