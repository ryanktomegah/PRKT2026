"""
runtime_pipeline.py — Build a real LIPPipeline for runtime HTTP deployments.

This module wires production component classes into ``LIPPipeline`` so the
FastAPI app can expose a real processing endpoint instead of test doubles.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Tuple

from lip.c1_failure_classifier.embeddings import CorridorEmbeddingPipeline
from lip.c1_failure_classifier.inference import _DEFAULT_THRESHOLD, InferenceEngine
from lip.c1_failure_classifier.model import ClassifierModel, create_default_model
from lip.c2_pd_model.api import C2Service
from lip.c3_repayment_engine.repayment_loop import SettlementMonitor
from lip.c4_dispute_classifier.model import DisputeClassifier
from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c8_license_manager.license_token import LicenseeContext, ProcessorLicenseeContext
from lip.common.borrower_registry import BorrowerRegistry
from lip.common.known_entity_registry import KnownEntityRegistry
from lip.pipeline import LIPPipeline

logger = logging.getLogger(__name__)

_DEFAULT_AML_SALT = b"lip_staging_aml_salt_32_bytes__"


def real_pipeline_enabled() -> bool:
    raw = os.environ.get("LIP_API_ENABLE_REAL_PIPELINE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _decode_env_key(name: str) -> Optional[bytes]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    if len(raw) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in raw):
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        raise RuntimeError(
            f"{name} is neither valid base64 nor valid hex."
        )


def _load_aml_salt() -> bytes:
    raw = os.environ.get("LIP_AML_SALT", "").strip()
    if not raw:
        return _DEFAULT_AML_SALT
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode("utf-8")


def _build_c1_engine(redis_client=None) -> InferenceEngine:
    model = create_default_model()
    model_dir = os.environ.get("LIP_C1_MODEL_DIR", "").strip()
    source = "default"

    if model_dir:
        try:
            model.load(model_dir)
            source = f"artifact:{model_dir}"
        except Exception as exc:
            logger.warning(
                "Unable to load C1 model from %s (%s); using default model.",
                model_dir,
                exc,
            )
            model = create_default_model()

    threshold = float(os.environ.get("LIP_C1_THRESHOLD", _DEFAULT_THRESHOLD))
    embedding_pipeline = CorridorEmbeddingPipeline(redis_client=redis_client)
    logger.info("Runtime C1 engine ready (%s)", source)
    return InferenceEngine(
        model=model,
        embedding_pipeline=embedding_pipeline,
        threshold=threshold,
    )


def _build_decision_logger() -> DecisionLogger:
    key = _decode_env_key("LIP_DECISION_LOG_HMAC_KEY")
    if key is None:
        key = _decode_env_key("LIP_API_HMAC_KEY")
    if key is None:
        raise RuntimeError(
            "Real runtime pipeline requires LIP_DECISION_LOG_HMAC_KEY or "
            "LIP_API_HMAC_KEY for the C7 decision log."
        )
    return DecisionLogger(hmac_key=key)


def _build_c6_checker(redis_client=None) -> AMLChecker:
    velocity = VelocityChecker(salt=_load_aml_salt(), redis_client=redis_client)
    return AMLChecker(
        velocity_checker=velocity,
        entity_name_resolver=None,
        redis_client=redis_client,
    )


def build_runtime_pipeline(
    *,
    kill_switch: KillSwitch,
    settlement_monitor: SettlementMonitor,
    borrower_registry: BorrowerRegistry,
    known_entity_registry: KnownEntityRegistry,
    redis_client=None,
    license_context: Optional[LicenseeContext] = None,
) -> Tuple[LIPPipeline, Optional[ProcessorLicenseeContext]]:
    """Assemble a real runtime pipeline from production component classes."""
    decision_logger = _build_decision_logger()
    c7_agent = ExecutionAgent(
        kill_switch=kill_switch,
        decision_logger=decision_logger,
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=ExecutionConfig(borrower_registry=borrower_registry),
        licensee_context=license_context,
        known_entity_registry=known_entity_registry,
        redis_client=redis_client,
    )
    c1_engine = _build_c1_engine(redis_client=redis_client)
    c2_service = C2Service()

    pipeline = LIPPipeline(
        c1_engine=c1_engine.predict,
        c2_engine=c2_service.predict,
        c4_classifier=DisputeClassifier(),
        c6_checker=_build_c6_checker(redis_client=redis_client),
        c7_agent=c7_agent,
        c3_monitor=settlement_monitor,
        redis_client=redis_client,
    )

    processor_context = (
        license_context if isinstance(license_context, ProcessorLicenseeContext) else None
    )
    return pipeline, processor_context
