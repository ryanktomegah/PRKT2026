"""
api.py — HTTP wrapper for the C6 AML gate.

Exposes a minimal FastAPI surface for staging and local deployments:
  - GET /health/live
  - GET /health/ready
  - POST /check
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from lip.c8_license_manager.runtime import enforce_component_license
from lip.common.logging_setup import configure_app_logging
from lip.common.redis_factory import create_redis_client

from .aml_checker import AMLChecker
from .bic_name_resolver import build_bic_name_resolver
from .velocity import VelocityChecker

configure_app_logging()

_DEFAULT_SALT = b"lip_staging_aml_salt_32_bytes__"


class AMLCheckRequest(BaseModel):
    entity_id: str
    amount: str
    beneficiary_id: str
    entity_name: Optional[str] = None
    beneficiary_name: Optional[str] = None
    dollar_cap_override: Optional[str] = None
    count_cap_override: Optional[int] = None


def _load_salt() -> bytes:
    raw = os.environ.get("LIP_AML_SALT", "").strip()
    if not raw:
        return _DEFAULT_SALT

    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode("utf-8")


def _serialize_result(result) -> dict:
    return {
        "passed": result.passed,
        "reason": result.reason,
        "anomaly_flagged": result.anomaly_flagged,
        "triggered_rules": list(result.triggered_rules),
        "sanctions_hits": list(result.sanctions_hits),
        "structuring_flagged": result.structuring_flagged,
        "velocity_result": None
        if result.velocity_result is None
        else {
            "passed": result.velocity_result.passed,
            "reason": result.velocity_result.reason,
            "entity_id_hash": result.velocity_result.entity_id_hash,
            "dollar_volume_24h": str(result.velocity_result.dollar_volume_24h),
            "count_24h": result.velocity_result.count_24h,
            "beneficiary_concentration": None
            if result.velocity_result.beneficiary_concentration is None
            else str(result.velocity_result.beneficiary_concentration),
        },
    }


def create_app(checker: Optional[AMLChecker] = None) -> FastAPI:
    enforce_component_license("C6")
    # Wire Redis when REDIS_URL is configured so StructuringDetector and
    # VelocityChecker use shared state across replicas instead of in-memory
    # fallbacks (the in-memory path emits single_replica warnings at boot).
    redis_client = create_redis_client() if not checker else None
    aml_checker = checker or AMLChecker(
        velocity_checker=VelocityChecker(salt=_load_salt(), redis_client=redis_client),
        entity_name_resolver=build_bic_name_resolver(),
        redis_client=redis_client,
    )
    app = FastAPI(title="LIP C6 AML Velocity", version="1.0.0")

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/check")
    def check(payload: AMLCheckRequest) -> dict:
        result = aml_checker.check(
            entity_id=payload.entity_id,
            amount=Decimal(payload.amount),
            beneficiary_id=payload.beneficiary_id,
            entity_name=payload.entity_name,
            beneficiary_name=payload.beneficiary_name,
            dollar_cap_override=None
            if payload.dollar_cap_override is None
            else Decimal(payload.dollar_cap_override),
            count_cap_override=payload.count_cap_override,
        )
        return _serialize_result(result)

    return app


app = create_app()
