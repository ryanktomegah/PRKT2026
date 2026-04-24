"""
api.py — HTTP wrapper for the C4 dispute classifier.

Exposes a minimal FastAPI surface for staging and bank-side container runs:
  - GET /health/live
  - GET /health/ready
  - POST /classify
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lip.c8_license_manager.runtime import enforce_component_license

from .model import DisputeClassifier


class C4ClassifyRequest(BaseModel):
    rejection_code: Optional[str] = None
    narrative: Optional[str] = None
    amount: str = ""
    currency: str = ""
    counterparty: str = ""


def _serialize_result(result: dict) -> dict:
    serialized = dict(result)
    dispute_class = serialized.get("dispute_class")
    if dispute_class is not None and hasattr(dispute_class, "value"):
        serialized["dispute_class"] = dispute_class.value
    return serialized


def create_app(classifier: Optional[DisputeClassifier] = None) -> FastAPI:
    enforce_component_license("C4")
    c4_classifier = classifier
    app = FastAPI(title="LIP C4 Dispute Classifier", version="1.0.0")

    def get_classifier() -> DisputeClassifier:
        nonlocal c4_classifier
        if c4_classifier is None:
            try:
                c4_classifier = DisputeClassifier()
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail="C4 dispute classifier backend is not configured.",
                ) from exc
        return c4_classifier

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/classify")
    def classify(payload: C4ClassifyRequest) -> dict:
        result = get_classifier().classify(
            rejection_code=payload.rejection_code,
            narrative=payload.narrative,
            amount=payload.amount,
            currency=payload.currency,
            counterparty=payload.counterparty,
        )
        return _serialize_result(result)

    return app


app = create_app()
