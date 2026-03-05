"""
Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)

Public API for the LIP C1 Failure Classifier component.

Exposes:
    ClassifierModel           — Combined GraphSAGE + TabTransformer + MLP classifier.
    CorridorEmbeddingPipeline — Redis-backed 128-dim corridor embedding store.
    run_inference             — Convenience function for single-payment inference.
"""

from __future__ import annotations

import logging
from typing import Optional

from .embeddings import CorridorEmbeddingPipeline
from .model import ClassifierModel, create_default_model
from .inference import InferenceEngine

__all__ = [
    "ClassifierModel",
    "CorridorEmbeddingPipeline",
    "run_inference",
]

logger = logging.getLogger(__name__)


def run_inference(
    payment: dict,
    model: Optional[ClassifierModel] = None,
    embedding_pipeline: Optional[CorridorEmbeddingPipeline] = None,
    threshold: float = 0.5,
) -> dict:
    """Run real-time C1 failure classification on a single payment.

    This is the primary entry-point for callers that want a simple
    function-call interface without managing an :class:`InferenceEngine`
    instance directly.

    Parameters
    ----------
    payment:
        Raw payment dictionary containing at minimum the fields expected by
        :class:`~lip.c1_failure_classifier.features.TabularFeatureEngineer`.
    model:
        Pre-loaded :class:`ClassifierModel`.  When *None* a default
        randomly-initialised model is created via
        :func:`~lip.c1_failure_classifier.model.create_default_model`.
    embedding_pipeline:
        Pre-loaded :class:`CorridorEmbeddingPipeline`.  When *None* an
        in-memory pipeline is created automatically.
    threshold:
        Decision threshold applied to the raw sigmoid probability.

    Returns
    -------
    dict
        ClassifyResponse-compatible dictionary with keys:
        ``failure_probability``, ``above_threshold``,
        ``inference_latency_ms``, ``threshold_used``,
        ``corridor_embedding_used``, ``shap_top20``.
    """
    if model is None:
        logger.info("run_inference: no model supplied — creating default model")
        model = create_default_model()

    if embedding_pipeline is None:
        logger.info("run_inference: no embedding_pipeline supplied — using in-memory store")
        embedding_pipeline = CorridorEmbeddingPipeline(redis_client=None)

    engine = InferenceEngine(
        model=model,
        embedding_pipeline=embedding_pipeline,
        threshold=threshold,
    )
    return engine.predict(payment)
