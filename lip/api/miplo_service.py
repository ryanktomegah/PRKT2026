"""
miplo_service.py — MIPLO API Gateway service layer.
P3 Platform Licensing: validates sub-licensee BICs and threads TenantContext.

The MIPLO (Money In / Payment Lending Organisation) is the processor role
in the P3 three-entity model. This service validates that each payment's
sending_bic is authorized under the processor's C8 license token, then
calls the LIP pipeline with a tenant-scoped TenantContext.
"""
from __future__ import annotations

import logging
from typing import Optional

from lip.c8_license_manager.license_token import ProcessorLicenseeContext
from lip.common.schemas import TenantContext
from lip.infrastructure.monitoring.metrics import (
    METRIC_MIPLO_REQUEST_COUNT,
    METRIC_TENANT_ISOLATION_VIOLATION,
)

logger = logging.getLogger(__name__)


class UnauthorizedBICError(Exception):
    """Raised when a payment's sending_bic is not in the processor's sub_licensee_bics.

    This is a tenant isolation violation — the BIC is not authorized to transact
    through this processor's deployment. Logged as a security event.
    """

    def __init__(self, bic: str, tenant_id: str):
        self.bic = bic
        self.tenant_id = tenant_id
        super().__init__(f"BIC {bic!r} not authorized for tenant {tenant_id!r}")


class MIPLOService:
    """MIPLO API Gateway — validates BICs and threads TenantContext through pipeline.

    Constructed once at container boot from ProcessorLicenseeContext (C8 validated).
    Immutable after construction — TenantContext is frozen.
    """

    def __init__(
        self,
        pipeline,
        processor_context: ProcessorLicenseeContext,
        metrics_collector=None,
        portfolio_reporter=None,
    ):
        self._pipeline = pipeline
        self._tenant_id = processor_context.licensee_id
        self._sub_licensee_bics: frozenset[str] = frozenset(processor_context.sub_licensee_bics)
        self._tenant_context = TenantContext(
            tenant_id=self._tenant_id,
            sub_licensee_bics=list(processor_context.sub_licensee_bics),
            deployment_phase=processor_context.deployment_phase,
        )
        self._metrics = metrics_collector
        self._portfolio = portfolio_reporter

    @property
    def tenant_id(self) -> str:
        """Processor tenant identifier from C8 license token."""
        return self._tenant_id

    @property
    def tenant_context(self) -> TenantContext:
        """Frozen TenantContext for this processor deployment."""
        return self._tenant_context

    def validate_bic(self, sending_bic: str) -> bool:
        """Check if sending_bic is authorized under this processor's license."""
        return sending_bic in self._sub_licensee_bics

    def process_payment(
        self,
        event,
        borrower=None,
        entity_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
    ):
        """Run a payment through the tenant-scoped LIP pipeline.

        Validates that event.sending_bic is in the processor's sub_licensee_bics.
        Raises UnauthorizedBICError if not — this is a hard gate, not a soft flag.

        Args:
            event: NormalizedEvent from C5.
            borrower: Optional borrower-level data for C2 PD inference.
            entity_id: Optional entity override for C6 velocity.
            beneficiary_id: Optional beneficiary override for C6 velocity.

        Returns:
            PipelineResult from the tenant-scoped pipeline execution.

        Raises:
            UnauthorizedBICError: If sending_bic not in sub_licensee_bics.
        """
        if not self.validate_bic(event.sending_bic):
            logger.warning(
                "BIC isolation violation: bic=%s tenant=%s",
                event.sending_bic,
                self._tenant_id,
            )
            if self._metrics:
                self._metrics.increment(
                    METRIC_TENANT_ISOLATION_VIOLATION,
                    {"tenant_id": self._tenant_id},
                )
            raise UnauthorizedBICError(event.sending_bic, self._tenant_id)

        if self._metrics:
            self._metrics.increment(METRIC_MIPLO_REQUEST_COUNT)

        return self._pipeline.process(
            event=event,
            borrower=borrower,
            entity_id=entity_id,
            beneficiary_id=beneficiary_id,
            tenant_context=self._tenant_context,
        )

    # ── Portfolio delegation (tenant-scoped) ─────────────────────────────────

    def get_portfolio_loans(self):
        """Return active loans for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_loans()

    def get_portfolio_exposure(self):
        """Return exposure breakdown for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_exposure()

    def get_portfolio_nav(self):
        """Return NAV snapshot for this processor's tenant."""
        if self._portfolio is None:
            return None
        return self._portfolio.get_tenant_nav(self._tenant_id)

    def get_status(self) -> dict:
        """Return processor container status for the /miplo/status endpoint."""
        return {
            "tenant_id": self._tenant_id,
            "sub_licensee_bics": sorted(self._sub_licensee_bics),
            "deployment_phase": self._tenant_context.deployment_phase,
        }
