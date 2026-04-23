"""
runtime_pipeline.py — Build a real LIPPipeline for runtime HTTP deployments.

This module wires production component classes into ``LIPPipeline`` so the
FastAPI app can expose a real processing endpoint instead of test doubles.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional, Protocol, Tuple

import numpy as np

from lip.c1_failure_classifier.embeddings import CorridorEmbeddingPipeline
from lip.c1_failure_classifier.features import TabularFeatureEngineer
from lip.c1_failure_classifier.graph_builder import BICGraphBuilder
from lip.c1_failure_classifier.inference import (
    _DEFAULT_THRESHOLD,
    LATENCY_P50_TARGET_MS,
    LATENCY_P99_TARGET_MS,
    InferenceEngine,
)
from lip.c1_failure_classifier.model import create_default_model
from lip.c2_pd_model.api import C2Service
from lip.c3_repayment_engine.repayment_loop import SettlementMonitor
from lip.c4_dispute_classifier.model import DisputeClassifier
from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.bic_name_resolver import build_bic_name_resolver
from lip.c6_aml_velocity.velocity import VelocityChecker
from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.c8_license_manager.license_token import LicenseeContext, ProcessorLicenseeContext
from lip.common import secure_pickle
from lip.common.borrower_registry import BorrowerRegistry
from lip.common.known_entity_registry import KnownEntityRegistry
from lip.pipeline import LIPPipeline

logger = logging.getLogger(__name__)

_DEFAULT_AML_SALT = b"lip_staging_aml_salt_32_bytes__"
_SHAP_TOP_N = 20


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


class _C1Predictor(Protocol):
    def predict(self, payment: dict) -> dict:
        ...


class TorchArtifactInferenceEngine:
    """Load and serve the trained C1 torch checkpoint format from ``artifacts/``."""

    def __init__(
        self,
        model_dir: Path,
        *,
        redis_client=None,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        import torch

        from lip.c1_failure_classifier.graphsage_torch import GraphSAGETorch
        from lip.c1_failure_classifier.model_torch import (
            ClassifierModelTorch,
            MLPHeadTorch,
        )
        from lip.c1_failure_classifier.tabtransformer_torch import TabTransformerTorch

        self._torch = torch
        self._model_dir = model_dir
        self._threshold = threshold
        self._tab_eng = TabularFeatureEngineer()
        self._graph = BICGraphBuilder()
        self._embedding_pipeline = CorridorEmbeddingPipeline(redis_client=redis_client)
        self._calibrator = None
        self._scaler = None

        model = ClassifierModelTorch(
            graphsage=GraphSAGETorch(),
            tabtransformer=TabTransformerTorch(),
            mlp_head=MLPHeadTorch(),
        )

        checkpoint_path = model_dir / "c1_model_parquet.pt"
        state_dict = self._load_torch_checkpoint(checkpoint_path)
        model.load_state_dict(state_dict)
        model.eval()
        model.lgbm_model = self._load_optional_pickle(model_dir / "c1_lgbm_parquet.pkl")
        self._calibrator = self._load_optional_pickle(model_dir / "c1_calibrator.pkl")
        self._scaler = self._load_optional_pickle(model_dir / "c1_scaler.pkl")
        self._model = model

    def _load_torch_checkpoint(self, checkpoint_path: Path) -> Any:
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"C1 checkpoint not found: {checkpoint_path}")
        try:
            state_dict = self._torch.load(
                checkpoint_path,
                map_location="cpu",
                weights_only=True,
            )
        except TypeError:
            state_dict = self._torch.load(checkpoint_path, map_location="cpu")
        return self._normalise_state_dict(state_dict)

    def _normalise_state_dict(self, state_dict: Any) -> dict[str, Any]:
        if not isinstance(state_dict, dict):
            raise TypeError("Expected a checkpoint state_dict mapping.")

        converted = dict(state_dict)
        for key in list(state_dict):
            if key.endswith("attn.in_proj_weight"):
                q_weight, k_weight, v_weight = state_dict[key].chunk(3, dim=0)
                prefix = key[: -len("in_proj_weight")]
                converted[f"{prefix}q_proj.weight"] = q_weight
                converted[f"{prefix}k_proj.weight"] = k_weight
                converted[f"{prefix}v_proj.weight"] = v_weight
                converted.pop(key, None)
            elif key.endswith("attn.in_proj_bias"):
                q_bias, k_bias, v_bias = state_dict[key].chunk(3, dim=0)
                prefix = key[: -len("in_proj_bias")]
                converted[f"{prefix}q_proj.bias"] = q_bias
                converted[f"{prefix}k_proj.bias"] = k_bias
                converted[f"{prefix}v_proj.bias"] = v_bias
                converted.pop(key, None)
        return converted

    def _load_optional_pickle(self, path: Path) -> Any:
        """Load a C1 supplementary artefact via secure_pickle.

        Returns ``None`` if the payload is absent, the HMAC sidecar is missing,
        or verification fails. The tri-state fallback in ``_build_c1_engine``
        then degrades to the default NumPy model rather than crashing the API.
        The B13-01 pickle ban forbids bypassing ``secure_pickle`` even for
        repository-owned artefacts — sign them with ``scripts/sign_c1_artifacts.py``
        before deploying, or the loader will reject them.
        """
        if not path.exists():
            return None
        try:
            return secure_pickle.load(path)
        except secure_pickle.SecurePickleError as exc:
            logger.warning(
                "C1 optional artefact %s failed secure_pickle load (%s); "
                "skipping (caller will fall back).",
                path,
                exc,
            )
            return None

    def _compute_shap_top20(self, tabular_features: np.ndarray) -> list[dict]:
        feature_names = self._tab_eng.feature_names()
        indexed = sorted(
            enumerate(tabular_features),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )[:_SHAP_TOP_N]
        return [
            {"feature": feature_names[index], "value": float(value)}
            for index, value in indexed
        ]

    def _check_latency(self, latency_ms: float) -> None:
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

    def predict(self, payment: dict) -> dict:
        t_start = time.perf_counter()

        tabular_features = self._tab_eng.extract(payment)
        sending_bic = str(payment.get("sending_bic", ""))
        node_features = self._graph.get_node_features(sending_bic)
        neighbor_features = [
            self._graph.get_node_features(neighbor_bic)
            for neighbor_bic in self._graph.get_neighbors(sending_bic, k=5)
        ]
        neighbor_array = (
            np.asarray(neighbor_features, dtype=np.float64)
            if neighbor_features else None
        )

        full_features = np.concatenate([node_features, tabular_features]).astype(np.float64)
        if self._scaler is not None:
            full_features = self._scaler.transform(full_features.reshape(1, -1)).reshape(-1)

        currency_pair = str(payment.get("currency_pair", "UNKNOWN"))
        corridor_embedding_used = self._embedding_pipeline.retrieve(currency_pair) is not None
        if not corridor_embedding_used:
            self._embedding_pipeline.cold_start_embedding(currency_pair, all_pairs=[])

        probability = float(
            self._model.predict_proba(
                node_features=full_features[:8],
                tabular_features=full_features,
                neighbor_features=neighbor_array,
            )
        )

        if self._calibrator is not None:
            try:
                probability = float(self._calibrator.predict(np.array([probability]))[0])
            except Exception as exc:
                logger.warning(
                    "Unable to apply C1 calibrator from %s (%s); using raw probability.",
                    self._model_dir,
                    exc,
                )

        latency_ms = (time.perf_counter() - t_start) * 1_000.0
        self._check_latency(latency_ms)

        return {
            "failure_probability": probability,
            "above_threshold": probability >= self._threshold,
            "inference_latency_ms": round(latency_ms, 3),
            "threshold_used": float(self._threshold),
            "corridor_embedding_used": corridor_embedding_used,
            "shap_top20": self._compute_shap_top20(tabular_features),
        }


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


def _build_c1_engine(redis_client=None) -> _C1Predictor:
    threshold = float(os.environ.get("LIP_C1_THRESHOLD", _DEFAULT_THRESHOLD))
    model_dir = os.environ.get("LIP_C1_MODEL_DIR", "").strip()
    require_artifacts = _env_flag("LIP_REQUIRE_MODEL_ARTIFACTS")

    if model_dir:
        model_path = Path(model_dir)
        if (model_path / "c1_model_parquet.pt").exists():
            try:
                engine = TorchArtifactInferenceEngine(
                    model_path,
                    redis_client=redis_client,
                    threshold=threshold,
                )
                logger.info("Runtime C1 engine ready (artifact:%s)", model_path)
                return engine
            except Exception as exc:
                logger.warning(
                    "Unable to load torch C1 artifacts from %s (%s); trying NumPy loader.",
                    model_path,
                    exc,
                )
                if require_artifacts:
                    raise RuntimeError(
                        "LIP_REQUIRE_MODEL_ARTIFACTS=1 but torch C1 artifacts "
                        f"failed to load from {model_path}"
                    ) from exc

    model = create_default_model()
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
            if require_artifacts:
                raise RuntimeError(
                    "LIP_REQUIRE_MODEL_ARTIFACTS=1 but C1 model failed to "
                    f"load from {model_dir}"
                ) from exc
            model = create_default_model()
    elif require_artifacts:
        raise RuntimeError(
            "LIP_REQUIRE_MODEL_ARTIFACTS=1 but LIP_C1_MODEL_DIR is not set."
        )

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
        entity_name_resolver=build_bic_name_resolver(),
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
