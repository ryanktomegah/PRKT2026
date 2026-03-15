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
    from fastapi import APIRouter

    def make_admin_router(admin_service: BPIAdminService) -> APIRouter:
        """Create a FastAPI APIRouter pre-bound to a ``BPIAdminService`` instance.

        Usage::

            app = FastAPI()
            app.include_router(make_admin_router(service), prefix="/admin")

        Args:
            admin_service: Configured :class:`BPIAdminService` instance.

        Returns:
            :class:`~fastapi.APIRouter` with three endpoints.
        """
        router = APIRouter(tags=["admin"])

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

        return router

except ImportError:
    pass  # FastAPI not required for core pipeline operation
