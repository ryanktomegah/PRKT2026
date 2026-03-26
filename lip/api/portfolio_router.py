"""
portfolio_router.py — MLO portfolio reporting API.
GAP-07: Institutional capital providers require real-time visibility into
active loan positions, aggregate exposure, and yield performance.

Endpoints:
  GET /portfolio/loans      — Active loans: UETR, maturity, principal, corridor
  GET /portfolio/exposure   — Aggregate exposure by corridor / tier / maturity class
  GET /portfolio/yield      — Cumulative yield and annualised return on active book

Architecture note:
  PortfolioReporter reads live state directly from the RepaymentLoop (via
  get_active_loans()) and the BPIRoyaltySettlement (for realised royalties).
  Both are passed in at construction time so the router is fully testable
  without running an HTTP server.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from lip.c2_pd_model.tier_assignment import Tier
from lip.common.known_entity_registry import KnownEntityRegistry
from lip.risk.portfolio_risk import PortfolioRiskEngine


def _tier_from_fee_bps(fee_bps: int) -> int:
    """Derive credit tier from annualised fee basis points.

    Tier 1: 300–539 bps  (investment-grade, listed)
    Tier 2: 540–899 bps  (private company, balance-sheet data)
    Tier 3: 900+ bps     (thin file)
    """
    if fee_bps < 540:
        return 1
    if fee_bps < 900:
        return 2
    return 3


class PortfolioReporter:
    """Computes portfolio metrics from live RepaymentLoop state.

    Args:
        repayment_loop: A ``RepaymentLoop`` instance with a
            ``get_active_loans()`` method.
        royalty_settlement: Optional ``BPIRoyaltySettlement`` for
            realised yield data.  When ``None``, yield figures are
            estimated from active book only.
        licensee_id: Optional filter — when provided, only loans for
            this licensee are included in all reports.
    """

    def __init__(
        self,
        repayment_loop: Any,
        royalty_settlement: Optional[Any] = None,
        licensee_id: Optional[str] = None,
        risk_engine: Optional[PortfolioRiskEngine] = None,
    ) -> None:
        self._loop = repayment_loop
        self._royalty = royalty_settlement
        self._licensee_id = licensee_id
        self._risk_engine = risk_engine

    def _get_loans(self):
        """Return active loans, optionally filtered by licensee."""
        loans = self._loop.get_active_loans()
        if self._licensee_id:
            loans = [loan for loan in loans if loan.licensee_id == self._licensee_id]
        return loans

    # ── GET /portfolio/loans ──────────────────────────────────────────────────

    def get_loans(self) -> List[Dict]:
        """All active loans with full position detail.

        Returns:
            List of dicts with keys:
              loan_id, uetr, principal_usd, fee_bps, tier,
              maturity_date, rejection_class, corridor, funded_at,
              days_to_maturity, licensee_id
        """
        now = datetime.now(tz=timezone.utc)
        result = []
        for loan in self._get_loans():
            days_to_maturity = (loan.maturity_date - now).days
            result.append({
                "loan_id": loan.loan_id,
                "uetr": loan.uetr,
                "principal_usd": str(loan.principal),
                "fee_bps": loan.fee_bps,
                "tier": _tier_from_fee_bps(loan.fee_bps),
                "maturity_date": loan.maturity_date.isoformat(),
                "rejection_class": loan.rejection_class,
                "corridor": loan.corridor,
                "funded_at": loan.funded_at.isoformat(),
                "days_to_maturity": days_to_maturity,
                "licensee_id": loan.licensee_id,
            })
        return result

    # ── GET /portfolio/exposure ───────────────────────────────────────────────

    def get_exposure(self) -> Dict:
        """Aggregate exposure by corridor, tier, and maturity class.

        Returns:
            Dict with keys:
              total_exposure_usd: str
              by_corridor: {corridor: {principal_usd, loan_count}}
              by_tier: {1: {principal_usd, loan_count}, 2: ..., 3: ...}
              by_maturity_class: {CLASS_A/B/C: {principal_usd, loan_count}}
        """
        by_corridor: Dict[str, Dict] = defaultdict(lambda: {"principal_usd": Decimal("0"), "loan_count": 0})
        by_tier: Dict[int, Dict] = defaultdict(lambda: {"principal_usd": Decimal("0"), "loan_count": 0})
        by_class: Dict[str, Dict] = defaultdict(lambda: {"principal_usd": Decimal("0"), "loan_count": 0})
        total = Decimal("0")

        for loan in self._get_loans():
            p = loan.principal
            total += p
            by_corridor[loan.corridor]["principal_usd"] += p
            by_corridor[loan.corridor]["loan_count"] += 1
            tier = _tier_from_fee_bps(loan.fee_bps)
            by_tier[tier]["principal_usd"] += p
            by_tier[tier]["loan_count"] += 1
            by_class[loan.rejection_class]["principal_usd"] += p
            by_class[loan.rejection_class]["loan_count"] += 1

        return {
            "total_exposure_usd": str(total),
            "loan_count": sum(v["loan_count"] for v in by_corridor.values()),
            "by_corridor": {
                k: {"principal_usd": str(v["principal_usd"]), "loan_count": v["loan_count"]}
                for k, v in by_corridor.items()
            },
            "by_tier": {
                k: {"principal_usd": str(v["principal_usd"]), "loan_count": v["loan_count"]}
                for k, v in by_tier.items()
            },
            "by_maturity_class": {
                k: {"principal_usd": str(v["principal_usd"]), "loan_count": v["loan_count"]}
                for k, v in by_class.items()
            },
        }

    # ── GET /portfolio/yield ──────────────────────────────────────────────────

    def get_yield(self) -> Dict:
        """Cumulative and estimated annualised yield on the active book.

        Realised royalties come from ``BPIRoyaltySettlement`` if wired.
        Accrued yield is estimated from the active loan book using the fee
        formula: fee = principal × (fee_bps/10000) × (funded_days/365).

        Returns:
            Dict with keys:
              accrued_fee_usd: estimated fee on active book since funding
              realised_royalty_usd: collected by BPI (from royalty settlement)
              book_principal_usd: total active principal
              estimated_annualised_yield_bps: avg weighted fee rate on active book
        """
        now = datetime.now(tz=timezone.utc)
        accrued_fee = Decimal("0")
        total_principal = Decimal("0")
        weighted_bps_sum = Decimal("0")

        for loan in self._get_loans():
            funded_days = max((now - loan.funded_at).total_seconds() / 86400, 0)
            fee = loan.principal * Decimal(str(loan.fee_bps)) / Decimal("10000") * Decimal(str(funded_days)) / Decimal("365")
            accrued_fee += fee
            total_principal += loan.principal
            weighted_bps_sum += loan.principal * Decimal(str(loan.fee_bps))

        estimated_yield_bps = (
            int(weighted_bps_sum / total_principal)
            if total_principal > 0 else 0
        )

        realised_royalty = Decimal("0")
        if self._royalty is not None:
            # Sum all monthly settlement reports for the current year
            year = now.year
            for month in range(1, now.month + 1):
                reports = self._royalty.generate_monthly_settlement(
                    month=month, year=year,
                    licensee_id=self._licensee_id,
                )
                for report in reports:
                    realised_royalty += report.total_royalty_usd

        return {
            "book_principal_usd": str(total_principal),
            "accrued_fee_usd": str(accrued_fee.quantize(Decimal("0.01"))),
            "realised_royalty_usd": str(realised_royalty),
            "estimated_annualised_yield_bps": estimated_yield_bps,
        }

    # ── GET /portfolio/risk ─────────────────────────────────────────────────

    def get_risk(self) -> Dict:
        """Portfolio risk summary: VaR, concentration, stress test results.

        Delegates to ``PortfolioRiskEngine`` when configured. Returns
        empty risk snapshot if no engine is wired.

        Returns:
            Dict with keys: var, corridor_concentration, bic_concentration,
            position_count, total_exposure.
        """
        if self._risk_engine is None:
            return {
                "var": {"var_99": "0", "var_95": "0", "expected_loss": "0",
                        "total_exposure": "0", "position_count": 0},
                "corridor_concentration": {"hhi": "0", "is_within_limits": True, "breaches": []},
                "bic_concentration": {"hhi": "0", "is_within_limits": True, "breaches": []},
                "position_count": 0,
                "total_exposure": "0",
            }
        return self._risk_engine.get_risk_summary()


# ---------------------------------------------------------------------------
# KnownEntityManager — GAP-11: known entity tier-override administration
# ---------------------------------------------------------------------------

class KnownEntityManager:
    """Administrative interface for the known-entity tier-override registry.

    Wraps a :class:`~lip.common.known_entity_registry.KnownEntityRegistry`
    and exposes CRUD operations suitable for HTTP API exposure.

    Args:
        registry: The underlying :class:`KnownEntityRegistry` instance.
            Changes made through this manager are reflected immediately.
    """

    def __init__(self, registry: KnownEntityRegistry) -> None:
        self._registry = registry

    def list_entities(self) -> List[Dict]:
        """Return all registered BIC → Tier overrides.

        Returns:
            List of dicts, each with keys ``bic`` (str) and ``tier`` (int).
        """
        return [
            {"bic": bic, "tier": int(tier)}
            for bic, tier in sorted(self._registry.list_all().items())
        ]

    def register(self, bic: str, tier: int) -> Dict:
        """Register a BIC with a manual tier override.

        Args:
            bic: SWIFT BIC code.
            tier: Tier value — 1, 2, or 3.

        Returns:
            Dict with keys ``bic``, ``tier``, ``status``.
        """
        self._registry.register(bic, Tier(tier))
        return {"bic": bic.upper(), "tier": tier, "status": "registered"}

    def unregister(self, bic: str) -> Dict:
        """Remove a BIC's tier override.

        Args:
            bic: SWIFT BIC code to remove.

        Returns:
            Dict with keys ``bic``, ``status``.
        """
        self._registry.unregister(bic)
        return {"bic": bic.upper(), "status": "unregistered"}


# ---------------------------------------------------------------------------
# Optional FastAPI router — only imported when FastAPI is available
# ---------------------------------------------------------------------------

try:
    from fastapi import APIRouter, Depends

    def make_portfolio_router(
        reporter: PortfolioReporter,
        auth_dependency=None,
    ) -> APIRouter:
        """Create a FastAPI APIRouter pre-bound to a ``PortfolioReporter`` instance.

        Usage::

            app = FastAPI()
            app.include_router(make_portfolio_router(reporter), prefix="/portfolio")

        Args:
            reporter: Configured :class:`PortfolioReporter` instance.
            auth_dependency: Optional FastAPI dependency for HMAC auth.

        Returns:
            :class:`~fastapi.APIRouter` with three endpoints.
        """
        deps = [Depends(auth_dependency)] if auth_dependency else []
        router = APIRouter(tags=["portfolio"], dependencies=deps)

        @router.get("/loans")
        def loans() -> List[Dict]:
            """All active bridge loans."""
            return reporter.get_loans()

        @router.get("/exposure")
        def exposure() -> Dict:
            """Aggregate exposure by corridor, tier, and maturity class."""
            return reporter.get_exposure()

        @router.get("/yield")
        def yield_report() -> Dict:
            """Cumulative and estimated annualised yield on active book."""
            return reporter.get_yield()

        @router.get("/risk")
        def risk_report() -> Dict:
            """Portfolio risk: VaR, concentration limits, and position count."""
            return reporter.get_risk()

        return router

    def make_known_entities_router(manager: KnownEntityManager, auth_dependency=None) -> APIRouter:
        """Create a FastAPI APIRouter for known-entity tier-override administration.

        Usage::

            app = FastAPI()
            app.include_router(
                make_known_entities_router(manager), prefix="/known-entities"
            )

        Args:
            manager: Configured :class:`KnownEntityManager` instance.

        Returns:
            :class:`~fastapi.APIRouter` with list, register, and delete endpoints.
        """
        deps = [Depends(auth_dependency)] if auth_dependency else []
        router = APIRouter(tags=["known-entities"], dependencies=deps)

        @router.get("")
        def list_entities() -> List[Dict]:
            """All registered BIC → Tier overrides."""
            return manager.list_entities()

        @router.post("")
        def register_entity(bic: str, tier: int) -> Dict:
            """Register a BIC with a manual tier override."""
            return manager.register(bic, tier)

        @router.delete("/{bic}")
        def delete_entity(bic: str) -> Dict:
            """Remove a BIC's tier override."""
            return manager.unregister(bic)

        return router

except ImportError:
    pass  # FastAPI not required for core pipeline operation
