"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

inference.py — Real-time C1 inference with SHAP and latency tracking
"""

from __future__ import annotations

import logging
import time
from typing import List

import numpy as np

from .embeddings import CorridorEmbeddingPipeline
from .features import TabularFeatureEngineer
from .graph_builder import BICGraphBuilder
from .model import ClassifierModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLA constants
# ---------------------------------------------------------------------------

LATENCY_P50_TARGET_MS: float = 100.0
"""50th-percentile inference latency target (milliseconds)."""

LATENCY_P99_TARGET_MS: float = 200.0
"""99th-percentile inference latency budget (milliseconds)."""

_SHAP_TOP_N: int = 20
_SHAP_STEPS: int = 50  # gradient approximation steps


# ---------------------------------------------------------------------------
# InferenceEngine
# ---------------------------------------------------------------------------

class InferenceEngine:
    """Real-time C1 payment failure inference engine.

    Wraps a trained :class:`~lip.c1_failure_classifier.model.ClassifierModel`
    and a :class:`~lip.c1_failure_classifier.embeddings.CorridorEmbeddingPipeline`
    to deliver single-payment predictions with SHAP explanations and
    latency telemetry.

    Parameters
    ----------
    model:
        Trained :class:`ClassifierModel`.
    embedding_pipeline:
        :class:`CorridorEmbeddingPipeline` for corridor embeddings.
    threshold:
        Decision threshold applied to the raw probability.  Predictions
        with ``failure_probability >= threshold`` are flagged.
    """

    def __init__(
        self,
        model: ClassifierModel,
        embedding_pipeline: CorridorEmbeddingPipeline,
        threshold: float = 0.5,
    ) -> None:
        self.model = model
        self.embedding_pipeline = embedding_pipeline
        self.threshold = threshold
        self._tab_eng = TabularFeatureEngineer()
        self._graph = BICGraphBuilder()
        logger.info(
            "InferenceEngine ready — threshold=%.4f, P99_target=%.0f ms",
            threshold, LATENCY_P99_TARGET_MS,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, payment: dict) -> dict:
        """Run a single-payment failure prediction.

        Parameters
        ----------
        payment:
            Raw payment dictionary.  See
            :class:`~lip.c1_failure_classifier.features.TabularFeatureEngineer`
            for expected fields.

        Returns
        -------
        dict
            ClassifyResponse-compatible payload:

            - ``failure_probability`` (float): sigmoid output ∈ [0, 1].
            - ``above_threshold`` (bool): ``failure_probability >= threshold``.
            - ``inference_latency_ms`` (float): wall-clock latency in ms.
            - ``threshold_used`` (float): decision threshold.
            - ``corridor_embedding_used`` (bool): whether a stored embedding
              was found (``False`` = cold-started).
            - ``shap_top20`` (List[dict]): top-20 SHAP feature attributions.
        """
        t_start = time.perf_counter()

        # --- Feature extraction ---
        tabular_features = self._tab_eng.extract(payment)

        # --- Node / graph features ---
        sending_bic: str = str(payment.get("sending_bic", ""))
        _receiving_bic: str = str(payment.get("receiving_bic", ""))
        node_features = self._graph.get_node_features(sending_bic)
        neighbors_l1_feats = [
            self._graph.get_node_features(nbr)
            for nbr in self._graph.get_neighbors(sending_bic, k=5)
        ]
        neighbors_l2_feats: List[np.ndarray] = []
        for nbr in self._graph.get_neighbors(sending_bic, k=5):
            neighbors_l2_feats.extend(
                self._graph.get_node_features(n2)
                for n2 in self._graph.get_neighbors(nbr, k=3)
            )

        # --- Corridor embedding (with cold-start fallback) ---
        currency_pair: str = str(payment.get("currency_pair", "UNKNOWN"))
        corridor_emb = self.embedding_pipeline.retrieve(currency_pair)
        corridor_embedding_used = corridor_emb is not None
        if not corridor_embedding_used:
            corridor_emb = self.embedding_pipeline.cold_start_embedding(
                currency_pair, all_pairs=[]
            )

        # --- Model inference ---
        failure_probability = self.model.predict_proba(
            node_features=node_features,
            neighbors_l1=neighbors_l1_feats,
            neighbors_l2=neighbors_l2_feats,
            tabular_features=tabular_features,
        )

        # --- SHAP approximation ---
        baseline = np.zeros_like(tabular_features, dtype=np.float64)
        shap_top20 = self._compute_shap_approximation(tabular_features, baseline)

        # --- Latency ---
        latency_ms = (time.perf_counter() - t_start) * 1_000.0
        self._check_latency(latency_ms)

        return {
            "failure_probability": float(failure_probability),
            "above_threshold": bool(failure_probability >= self.threshold),
            "inference_latency_ms": round(latency_ms, 3),
            "threshold_used": float(self.threshold),
            "corridor_embedding_used": corridor_embedding_used,
            "shap_top20": shap_top20,
        }

    # ------------------------------------------------------------------
    # SHAP approximation
    # ------------------------------------------------------------------

    def _compute_shap_approximation(
        self,
        tabular_features: np.ndarray,
        baseline: np.ndarray,
    ) -> List[dict]:
        """Approximate SHAP values via integrated gradients on the tabular head.

        Uses the integrated gradients method
        (Sundararajan et al., 2017) with ``_SHAP_STEPS`` interpolation points
        between *baseline* and *tabular_features*.  Only the TabTransformer +
        MLP path is used (GraphSAGE embeddings are treated as fixed context).

        Parameters
        ----------
        tabular_features:
            88-dim feature vector for the prediction of interest.
        baseline:
            88-dim reference input (typically zeros).

        Returns
        -------
        List[dict]
            Top-20 feature attributions sorted by absolute value, each a dict
            ``{'feature': str, 'value': float}``.
        """
        x = tabular_features.astype(np.float64)
        b = baseline.astype(np.float64)
        delta = x - b

        # Approximate integrated gradient via finite differences
        grads = np.zeros_like(x)
        for step in range(1, _SHAP_STEPS + 1):
            alpha = step / _SHAP_STEPS
            interpolated = b + alpha * delta

            # Numerical gradient: perturb each feature by eps
            eps = 1e-4
            tab_emb_center = self.model.tabtransformer.forward(interpolated)
            # Use a zero node-embedding for SHAP (isolate tabular contribution)
            from .graphsage import GRAPHSAGE_OUTPUT_DIM
            sage_emb_zero = np.zeros(GRAPHSAGE_OUTPUT_DIM, dtype=np.float64)
            fused_center = np.concatenate([sage_emb_zero, tab_emb_center])
            prob_center = self.model.mlp.forward(fused_center)

            for i in range(len(x)):
                x_plus = interpolated.copy()
                x_plus[i] += eps
                tab_emb_plus = self.model.tabtransformer.forward(x_plus)
                fused_plus = np.concatenate([sage_emb_zero, tab_emb_plus])
                prob_plus = self.model.mlp.forward(fused_plus)
                grads[i] += (prob_plus - prob_center) / eps

        # Integrated gradient attribution
        attributions = (grads / _SHAP_STEPS) * delta

        # Retrieve feature names
        feature_names = self._tab_eng.feature_names()

        # Build top-20 list sorted by absolute attribution
        indexed = sorted(
            enumerate(attributions),
            key=lambda iv: abs(iv[1]),
            reverse=True,
        )[:_SHAP_TOP_N]

        return [
            {"feature": feature_names[i], "value": float(v)}
            for i, v in indexed
        ]

    # ------------------------------------------------------------------
    # Latency monitoring
    # ------------------------------------------------------------------

    def _check_latency(self, latency_ms: float) -> None:
        """Log a warning when latency exceeds the P99 SLA target.

        Parameters
        ----------
        latency_ms:
            Observed inference latency in milliseconds.
        """
        if latency_ms > LATENCY_P99_TARGET_MS:
            logger.warning(
                "Inference latency %.1f ms exceeds P99 target %.0f ms",
                latency_ms, LATENCY_P99_TARGET_MS,
            )
        elif latency_ms > LATENCY_P50_TARGET_MS:
            logger.debug(
                "Inference latency %.1f ms exceeds P50 target %.0f ms",
                latency_ms, LATENCY_P50_TARGET_MS,
            )
