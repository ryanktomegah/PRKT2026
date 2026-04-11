"""
admin_router.py — BPI admin / multi-tenant monitoring API.
GAP-15: BPI operators require platform-wide visibility into licensee
        activity, active loan positions, and aggregate exposure across
        all tenants.

Endpoints (prefix: /admin):
  GET /admin/platform/summary          — Platform-wide aggregated stats
  GET /admin/licensees                 — List all active licensee IDs
  GET /admin/licensees/{id}/stats      — Per-licensee loan count + principal

Architecture note:
  BPIAdminService reads live state from RepaymentLoop.get_active_loans()
  which returns ActiveLoan objects indexed by loan_id.  This is the
  authoritative source — it reflects exactly what is outstanding at the
  moment of the query without any caching layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class LicenseeStats:
    """Per-licensee active portfolio snapshot.

    Attributes
    ----------
    licensee_id:
        Opaque BPI licensee identifier (hashed BIC or license ID).
    active_loan_count:
        Number of live bridge loans for this licensee.
    total_principal_usd:
        Sum of principal across all active loans.
    """

    licensee_id: str
    active_loan_count: int
    total_principal_usd: Decimal


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BPIAdminService:
    """Multi-tenant platform monitoring for BPI admin console (GAP-15).

    Aggregates live loan data from a :class:`~lip.c3_repayment_engine.repayment_loop.RepaymentLoop`
    to provide tenant-level and platform-level operational dashboards.

    Parameters
    ----------
    repayment_loop:
        Any object exposing ``get_active_loans() -> List[ActiveLoan]``.
        Using ``Any`` avoids a circular import from admin_router → repayment_loop
        while remaining fully type-safe in practice.
    """

    def __init__(self, repayment_loop: Any) -> None:
        self._loop = repayment_loop

    def list_licensees(self) -> List[str]:
        """Return sorted list of unique licensee IDs with active loans.

        Licensees with no active loans are not included — they have nothing
        for the admin to monitor in real-time.
        """
        loans = self._loop.get_active_loans()
        return sorted({loan.licensee_id for loan in loans if loan.licensee_id})

    def get_licensee_stats(self, licensee_id: str) -> LicenseeStats:
        """Return active loan count and total principal for one licensee.

        Parameters
        ----------
        licensee_id:
            Opaque licensee identifier.  Returns stats with zero values if
            the licensee has no active loans (rather than raising).
        """
        loans = [
            loan
            for loan in self._loop.get_active_loans()
            if loan.licensee_id == licensee_id
        ]
        total = sum((loan.principal for loan in loans), Decimal("0"))
        return LicenseeStats(
            licensee_id=licensee_id,
            active_loan_count=len(loans),
            total_principal_usd=total,
        )

    def get_platform_summary(self) -> Dict:
        """Return a platform-wide aggregate snapshot across all licensees.

        Returns
        -------
        dict with keys:
          total_active_loans: int
          total_licensees: int
          total_principal_usd: str (Decimal-serialised)
        """
        loans = self._loop.get_active_loans()
        total_principal = sum((loan.principal for loan in loans), Decimal("0"))
        licensees = {loan.licensee_id for loan in loans if loan.licensee_id}
        logger.debug(
            "Platform summary: %d loans, %d licensees, $%s principal",
            len(loans), len(licensees), total_principal,
        )
        return {
            "total_active_loans": len(loans),
            "total_licensees": len(licensees),
            "total_principal_usd": str(total_principal),
        }


# ---------------------------------------------------------------------------
# Optional FastAPI router — only imported when FastAPI is available
# ---------------------------------------------------------------------------

try:
    from fastapi import APIRouter, Depends, Query
    from fastapi.responses import PlainTextResponse

    def make_admin_router(
        admin_service: BPIAdminService,
        regulatory_reporter: Any = None,
        auth_dependency: Any = None,
        risk_engine: Any = None,
    ) -> APIRouter:
        """Create a FastAPI APIRouter pre-bound to a ``BPIAdminService`` instance.

        Usage::

            app = FastAPI()
            app.include_router(make_admin_router(service), prefix="/admin")

        Args:
            admin_service: Configured :class:`BPIAdminService` instance.
            regulatory_reporter: Optional :class:`RegulatoryReporter` for export endpoints.
            auth_dependency: Optional FastAPI dependency for HMAC auth.

        Returns:
            :class:`~fastapi.APIRouter` with admin and export endpoints.
        """
        deps = [Depends(auth_dependency)] if auth_dependency else []
        router = APIRouter(tags=["admin"], dependencies=deps)

        @router.get("/platform/summary")
        def platform_summary() -> Dict:
            """Platform-wide aggregate: loans, licensees, total principal."""
            return admin_service.get_platform_summary()

        @router.get("/licensees")
        def list_licensees() -> Dict:
            """All licensee IDs that currently have active loans."""
            return {"licensees": admin_service.list_licensees()}

        @router.get("/licensees/{licensee_id}/stats")
        def licensee_stats(licensee_id: str) -> Dict:
            """Per-licensee active loan count and total principal."""
            stats = admin_service.get_licensee_stats(licensee_id)
            return {
                "licensee_id": stats.licensee_id,
                "active_loan_count": stats.active_loan_count,
                "total_principal_usd": str(stats.total_principal_usd),
            }

        # ── Regulatory export endpoints (GAP-14) ──────────────────────────
        if regulatory_reporter is not None:
            from lip.common.regulatory_export import (
                export_dora_events_csv,
                export_dora_events_json,
                export_sr117_reports_csv,
                export_sr117_reports_json,
            )

            @router.get("/regulatory/dora/export")
            def export_dora(fmt: str = Query("json", alias="format")):
                """Export DORA audit events as CSV or JSON."""
                events = regulatory_reporter.get_all_dora_events()
                if fmt == "csv":
                    return PlainTextResponse(
                        export_dora_events_csv(events),
                        media_type="text/csv",
                    )
                return PlainTextResponse(
                    export_dora_events_json(events),
                    media_type="application/json",
                )

            @router.get("/regulatory/sr117/export")
            def export_sr117(fmt: str = Query("json", alias="format")):
                """Export SR 11-7 model validation reports as CSV or JSON."""
                reports = regulatory_reporter.get_sr117_reports()
                if fmt == "csv":
                    return PlainTextResponse(
                        export_sr117_reports_csv(reports),
                        media_type="text/csv",
                    )
                return PlainTextResponse(
                    export_sr117_reports_json(reports),
                    media_type="application/json",
                )

        # ── Stress testing endpoints (Phase 2.6) ──────────────────────────
        _STRESS_TEST_MAX_ITERATIONS = 100
        _STRESS_TEST_MAX_SECONDS = 10

        if risk_engine is not None:
            @router.post("/stress-test")
            def run_stress_test(num_simulations: int = 100) -> Dict:
                """Run Monte Carlo VaR stress test on current portfolio.

                Hard limits: max 100 iterations, max 10s wall time.
                Returns 400 if requested limits exceed caps.
                """
                import json as _json
                import threading

                from fastapi import HTTPException as _HTTPException

                from lip.risk.stress_testing import (
                    export_var_report_json,
                    generate_daily_var_report,
                )
                from lip.risk.var_monte_carlo import (
                    MCPosition,
                )

                if num_simulations > _STRESS_TEST_MAX_ITERATIONS:
                    raise _HTTPException(
                        status_code=400,
                        detail=(
                            f"num_simulations exceeds maximum allowed value "
                            f"({_STRESS_TEST_MAX_ITERATIONS})"
                        ),
                    )

                positions = [
                    MCPosition(
                        loan_id=pos.loan_id,
                        principal=float(pos.principal),
                        pd=pos.pd,
                        lgd=pos.lgd,
                        corridor=pos.corridor,
                        rejection_class=pos.rejection_class,
                    )
                    for pos in risk_engine.positions
                ]

                result_holder: Dict = {}
                error_holder: list = []

                def _run():
                    try:
                        report = generate_daily_var_report(
                            positions, num_simulations=num_simulations
                        )
                        result_holder["report"] = report
                    except Exception as exc:  # noqa: BLE001
                        error_holder.append(exc)

                t = threading.Thread(target=_run, daemon=True)
                t.start()
                t.join(timeout=_STRESS_TEST_MAX_SECONDS)
                if t.is_alive():
                    raise _HTTPException(
                        status_code=400,
                        detail=(
                            f"Stress test exceeded maximum allowed duration "
                            f"({_STRESS_TEST_MAX_SECONDS}s)"
                        ),
                    )
                if error_holder:
                    raise error_holder[0]

                return _json.loads(export_var_report_json(result_holder["report"]))

        # ── Model card generation endpoint (Phase 2.7) ────────────────────
        @router.post("/model-card")
        def generate_model_card_endpoint(
            component: str = "C1",
        ) -> Dict:
            """Generate a regulatory model card for the specified component.

            Returns 501 if real model card data is not available.
            Never returns forged or placeholder regulatory documentation.
            """
            from fastapi import HTTPException as _HTTPException

            # Model card generation requires validated training results and
            # evaluation metrics from the live model registry. Returning
            # placeholder data would constitute forged SR 11-7 documentation.
            # When a real model card pipeline is wired, replace this guard.
            raise _HTTPException(
                status_code=501,
                detail=(
                    f"Model card for component '{component}' is not available. "
                    "Real training results and evaluation metrics must be "
                    "provided by the model registry before a regulatory model "
                    "card can be generated."
                ),
            )

        return router

except ImportError:
    pass  # FastAPI not required for core pipeline operation
