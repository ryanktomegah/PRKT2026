"""
api.py — HTTP wrapper for the C2 PD model.

Exposes a minimal FastAPI surface for staging and local deployments:
  - GET /health/live
  - GET /health/ready
  - POST /predict
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

from lip.c8_license_manager.runtime import enforce_component_license

from .features import FeatureMasker, UnifiedFeatureEngineer
from .inference import PDInferenceEngine, configure_inference_salt
from .model import PDModel
from .tier_assignment import TierFeatures, assign_tier

logger = logging.getLogger(__name__)

_DEFAULT_INFERENCE_SALT = b"lip_staging_c2_salt_32_bytes____"


class C2PredictRequest(BaseModel):
    payment: dict[str, Any] = Field(default_factory=dict)
    borrower: dict[str, Any] = Field(default_factory=dict)


def _load_salt() -> bytes:
    raw = os.environ.get("LIP_C2_INFERENCE_SALT", "").strip()
    if not raw:
        return _DEFAULT_INFERENCE_SALT

    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode("utf-8")


def _bootstrap_model() -> PDModel:
    """Train a tiny deterministic model for staging when no artifact exists."""
    rng = np.random.default_rng(42)
    n_features = len(FeatureMasker.get_full_feature_names())
    X = rng.normal(loc=0.0, scale=1.0, size=(32, n_features))
    # Inject a stable signal so the ensemble is always trainable.
    X[:16, 0] += 2.0
    y = np.array([0] * 16 + [1] * 16, dtype=np.float64)

    model = PDModel(n_models=1, random_seeds=[42])
    model.fit(
        X,
        y,
        model_params={
            "n_estimators": 12,
            "learning_rate": 0.1,
            "max_depth": 3,
        },
    )
    return model


def _load_or_bootstrap_model() -> tuple[PDModel, str]:
    model_path = os.environ.get("LIP_C2_MODEL_PATH", "/models/c2_model.pkl").strip()
    model = PDModel()
    if model_path and os.path.exists(model_path):
        try:
            model.load(model_path)
            return model, "artifact"
        except Exception as exc:
            logger.warning(
                "Failed to load C2 model artifact at %s (%s); falling back to bootstrap model.",
                model_path,
                exc,
            )

    return _bootstrap_model(), "bootstrap"


class C2Service:
    def __init__(
        self,
        model: Optional[PDModel] = None,
        salt: Optional[bytes] = None,
    ) -> None:
        if model is None:
            self._model, self.model_source = _load_or_bootstrap_model()
        else:
            self._model = model
            self.model_source = "injected"
        self._salt = salt or _load_salt()

    def predict(self, payment: dict[str, Any], borrower: dict[str, Any]) -> dict[str, Any]:
        configure_inference_salt(self._salt)
        tier = assign_tier(
            TierFeatures(
                has_financial_statements=bool(
                    borrower.get("has_financial_statements", False)
                ),
                has_transaction_history=bool(
                    borrower.get("has_transaction_history", False)
                ),
                has_credit_bureau=bool(borrower.get("has_credit_bureau", False)),
                months_history=int(borrower.get("months_history", 0)),
                transaction_count=int(borrower.get("transaction_count", 0)),
            )
        )
        engine = PDInferenceEngine(
            self._model,
            UnifiedFeatureEngineer(tier),
            auto_tier=True,
        )
        return engine.predict(payment, borrower)


def create_app(service: Optional[C2Service] = None) -> FastAPI:
    enforce_component_license("C2")
    c2_service = service or C2Service()
    app = FastAPI(title="LIP C2 PD Model", version="1.0.0")

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/predict")
    def predict(payload: C2PredictRequest) -> dict[str, Any]:
        return c2_service.predict(payload.payment, payload.borrower)

    app.state.c2_service = c2_service
    return app


app = create_app()
