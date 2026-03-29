"""
privacy_budget.py — Per-corridor differential privacy budget tracker.

Implements composition-based budget accounting: each query deducts epsilon
from the corridor's cycle budget. When exhausted, callers must serve stale
cached results.

Budget resets every P10_PRIVACY_BUDGET_CYCLE_DAYS (30 days).

All budget arithmetic uses Decimal (QUANT requirement).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict

from .constants import P10_PRIVACY_BUDGET_PER_CYCLE
from .telemetry_schema import PrivacyBudgetStatus


@dataclass
class _CorridorBudget:
    """Internal mutable budget state for one corridor."""

    budget_remaining: Decimal
    queries_executed: int = 0
    cycle_start: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


class PrivacyBudgetTracker:
    """Track per-corridor differential privacy budget consumption.

    Thread-safety: NOT thread-safe. Callers must synchronise externally
    if accessed from multiple threads (same pattern as PortfolioRiskEngine).
    """

    def __init__(self, budget_per_cycle: Decimal = P10_PRIVACY_BUDGET_PER_CYCLE):
        self._budget_per_cycle = budget_per_cycle
        self._corridors: Dict[str, _CorridorBudget] = {}

    def _ensure_corridor(self, corridor: str) -> _CorridorBudget:
        if corridor not in self._corridors:
            self._corridors[corridor] = _CorridorBudget(
                budget_remaining=self._budget_per_cycle,
            )
        return self._corridors[corridor]

    def deduct(self, corridor: str, epsilon: Decimal) -> None:
        """Deduct epsilon from corridor budget. Raises ValueError if exhausted."""
        cb = self._ensure_corridor(corridor)
        if cb.budget_remaining < epsilon:
            raise ValueError(
                f"Privacy budget exhausted for corridor {corridor}: "
                f"remaining={cb.budget_remaining}, requested={epsilon}"
            )
        cb.budget_remaining -= epsilon
        cb.queries_executed += 1

    def has_budget(self, corridor: str, epsilon: Decimal) -> bool:
        """Check whether corridor has sufficient budget for a query at epsilon."""
        cb = self._ensure_corridor(corridor)
        return cb.budget_remaining >= epsilon

    def get_status(self, corridor: str) -> PrivacyBudgetStatus:
        """Return current budget status for a corridor."""
        cb = self._ensure_corridor(corridor)
        spent = self._budget_per_cycle - cb.budget_remaining
        return PrivacyBudgetStatus(
            corridor=corridor,
            budget_total=float(self._budget_per_cycle),
            budget_spent=float(spent),
            budget_remaining=float(cb.budget_remaining),
            queries_executed=cb.queries_executed,
            cycle_start=cb.cycle_start,
            is_exhausted=cb.budget_remaining <= Decimal("0"),
        )

    def reset_all(self) -> None:
        """Reset all corridor budgets. Called at cycle boundary (every 30 days)."""
        self._corridors.clear()
