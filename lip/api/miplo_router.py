"""
miplo_router.py — MIPLO API Gateway HTTP endpoints.
P3 Platform Licensing: processor-facing REST API.

Endpoints:
  POST /miplo/process — Submit a payment for tenant-scoped pipeline execution.
  GET  /miplo/status  — Processor container status (tenant info, authorized BICs).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from datetime import datetime, timezone
    from decimal import Decimal

    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    class MIPLOProcessRequest(BaseModel):
        """Payment event submitted by a processor for pipeline execution."""

        uetr: str = Field(..., description="Unique End-to-End Transaction Reference")
        individual_payment_id: str = Field(
            default="", description="ISO 20022 individual payment ID"
        )
        sending_bic: str = Field(..., description="Originator bank BIC")
        receiving_bic: str = Field(..., description="Beneficiary bank BIC")
        amount: str = Field(..., description="Payment amount as Decimal string")
        currency: str = Field(..., description="ISO 4217 currency code")
        rejection_code: str = Field(..., description="ISO 20022 rejection reason code")
        narrative: str = Field(default="", description="Free-text payment narrative")
        debtor_account: str = Field(
            default="", description="Debtor account identifier (IBAN or Othr.Id)"
        )
        borrower: Optional[dict] = Field(
            default=None, description="Borrower-level data for C2 PD inference"
        )
        entity_id: Optional[str] = Field(
            default=None, description="Override entity ID for C6 velocity"
        )
        beneficiary_id: Optional[str] = Field(
            default=None, description="Override beneficiary ID for C6 velocity"
        )

    class MIPLOProcessResponse(BaseModel):
        """Pipeline result scoped to the processor's tenant."""

        outcome: str
        uetr: str
        tenant_id: str
        failure_probability: float
        above_threshold: bool
        loan_offer: Optional[dict] = None
        decision_entry_id: Optional[str] = None
        pd_estimate: Optional[float] = None
        fee_bps: Optional[int] = None
        total_latency_ms: float = 0.0

    def make_miplo_router(miplo_service: Any, auth_dependency=None) -> APIRouter:
        """Factory that builds the MIPLO API router.

        Follows the same pattern as make_admin_router and make_portfolio_router.
        The miplo_service is captured by closure — no global state.
        """
        router = APIRouter(tags=["miplo"])

        if auth_dependency is not None:
            deps = [Depends(auth_dependency)]
        else:
            deps = []

        @router.post("/process", response_model=MIPLOProcessResponse, dependencies=deps)
        async def process_payment(request: MIPLOProcessRequest):
            """Submit a payment event for tenant-scoped LIP pipeline execution.

            The sending_bic must be in the processor's authorized sub_licensee_bics
            (validated via C8 license token). Returns 403 if not authorized.
            """
            from lip.c5_streaming.event_normalizer import NormalizedEvent

            event = NormalizedEvent(
                uetr=request.uetr,
                individual_payment_id=request.individual_payment_id,
                sending_bic=request.sending_bic,
                receiving_bic=request.receiving_bic,
                amount=Decimal(request.amount),
                currency=request.currency,
                timestamp=datetime.now(tz=timezone.utc),
                rail="SWIFT",
                rejection_code=request.rejection_code,
                narrative=request.narrative,
                debtor_account=request.debtor_account or None,
            )

            from lip.api.miplo_service import UnauthorizedBICError

            try:
                result = miplo_service.process_payment(
                    event=event,
                    borrower=request.borrower,
                    entity_id=request.entity_id,
                    beneficiary_id=request.beneficiary_id,
                )
            except UnauthorizedBICError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

            return MIPLOProcessResponse(
                outcome=result.outcome,
                uetr=result.uetr,
                tenant_id=miplo_service.tenant_id,
                failure_probability=result.failure_probability,
                above_threshold=result.above_threshold,
                loan_offer=result.loan_offer,
                decision_entry_id=result.decision_entry_id,
                pd_estimate=result.pd_estimate,
                fee_bps=result.fee_bps,
                total_latency_ms=result.total_latency_ms,
            )

        @router.get("/status", dependencies=deps)
        async def get_status():
            """Return processor container status (tenant info, authorized BICs)."""
            return miplo_service.get_status()

        return router

except ImportError:
    logger.debug("FastAPI not installed — MIPLO router not available")

    def make_miplo_router(*args, **kwargs):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the MIPLO router")
