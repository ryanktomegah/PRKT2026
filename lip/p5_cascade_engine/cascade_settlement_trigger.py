"""
cascade_settlement_trigger.py — C3 settlement failure → P5 cascade evaluation.

When C3 detects a payment failure on a high-dependency edge, this trigger
evaluates whether the failure should generate a cascade alert for the bank.

Integration point: C3 RepaymentLoop calls trigger.on_settlement_failure()
when a payment fails. The trigger resolves BICs to corporates and delegates
to build_cascade_alert().
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from .cascade_alerts import CascadeAlert, build_cascade_alert
from .constants import CASCADE_ALERT_DEPENDENCY_THRESHOLD
from .corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


class CascadeSettlementTrigger:
    """Bridges C3 settlement failures to P5 cascade analysis.

    Filters: dependency_score threshold, BIC mapping, intra-corporate.
    If filters pass, delegates to build_cascade_alert() for full
    propagation + intervention planning.
    """

    def __init__(
        self,
        cascade_graph: CascadeGraph,
        bic_to_corporate: Dict[str, str],
        budget_usd: float = 0.0,
    ) -> None:
        self._graph = cascade_graph
        self._bic_to_corp = bic_to_corporate
        self._budget_usd = budget_usd

    def on_settlement_failure(
        self,
        sending_bic: str,
        receiving_bic: str,
        amount_usd: float,
        dependency_score: float,
    ) -> Optional[CascadeAlert]:
        """Evaluate whether a settlement failure triggers cascade analysis.

        Returns CascadeAlert if:
          1. dependency_score >= CASCADE_ALERT_DEPENDENCY_THRESHOLD (0.50)
          2. Both BICs resolve to known corporates
          3. Sending and receiving corporates are different (not intra-corporate)
          4. Total cascade CVaR >= CASCADE_ALERT_THRESHOLD_USD ($1M)

        Returns None if any filter fails.
        """
        # Filter 1: dependency threshold
        if dependency_score < CASCADE_ALERT_DEPENDENCY_THRESHOLD:
            return None

        # Filter 2: BIC resolution
        source_corp = self._bic_to_corp.get(sending_bic)
        target_corp = self._bic_to_corp.get(receiving_bic)
        if source_corp is None or target_corp is None:
            logger.debug(
                "Unmapped BIC: sending=%s target=%s", sending_bic, receiving_bic
            )
            return None

        # Filter 3: intra-corporate
        if source_corp == target_corp:
            return None

        # Delegate to cascade engine (Filter 4: CVaR threshold applied inside)
        logger.info(
            "Settlement failure trigger: %s -> %s (dep=%.2f, amount=$%.0f)",
            source_corp,
            target_corp,
            dependency_score,
            amount_usd,
        )
        return build_cascade_alert(
            self._graph,
            origin_corporate_id=source_corp,
            budget_usd=self._budget_usd,
            trigger_type="PAYMENT_FAILURE",
        )
