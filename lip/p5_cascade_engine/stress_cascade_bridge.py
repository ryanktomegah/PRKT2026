"""
stress_cascade_bridge.py — C5 StressRegimeEvent → P5 cascade propagation bridge.

When C5 detects a corridor stress regime, this bridge:
  1. Looks up corporates with payment volume on the stressed corridor
  2. Runs cascade propagation from each affected corporate
  3. Returns alerts for corporates where CVaR >= threshold

Integration: C5 emits StressRegimeEvent → app layer calls bridge.on_stress_regime_event()
→ P5 cascade engine runs BFS propagation → CascadeAlerts returned.

The corridor_to_corporates mapping is built during entity resolution (Sprint 3a)
and passed to this bridge at construction time. This keeps CascadeGraph immutable.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from lip.c5_streaming.stress_regime_detector import StressRegimeEvent

from .cascade_alerts import CascadeAlert, build_cascade_alert
from .corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


class StressCascadeBridge:
    """Bridges C5 corridor stress events to P5 cascade analysis.

    Requires a pre-built corridor_to_corporates mapping:
    {"EUR_USD": ["BMW", "SIEMENS"], "GBP_EUR": ["HSBC_CORP"]}

    This mapping is derived during entity resolution by examining which
    corporates have payment volume on each currency corridor.
    """

    def __init__(
        self,
        cascade_graph: CascadeGraph,
        corridor_to_corporates: Dict[str, List[str]],
        budget_usd: float = 0.0,
    ) -> None:
        self._graph = cascade_graph
        self._corridor_map = corridor_to_corporates
        self._budget_usd = budget_usd

    def on_stress_regime_event(self, event: StressRegimeEvent) -> List[CascadeAlert]:
        """Process a C5 stress regime event and return cascade alerts.

        For each corporate on the stressed corridor, runs cascade propagation.
        Returns only alerts where CVaR >= CASCADE_ALERT_THRESHOLD_USD.

        Args:
            event: StressRegimeEvent from C5 StressRegimeDetector.

        Returns:
            List of CascadeAlert (may be empty if no corporate exceeds threshold).
        """
        corporates = self._corridor_map.get(event.corridor, [])
        if not corporates:
            logger.debug("No corporates mapped to corridor %s", event.corridor)
            return []

        alerts: List[CascadeAlert] = []
        for corp_id in corporates:
            alert = build_cascade_alert(
                self._graph,
                origin_corporate_id=corp_id,
                budget_usd=self._budget_usd,
                trigger_type="CORRIDOR_STRESS",
            )
            if alert is not None:
                alerts.append(alert)
                logger.info(
                    "Stress cascade alert: corridor=%s, corp=%s, cvar=%.0f",
                    event.corridor,
                    corp_id,
                    alert.cascade_result.total_value_at_risk_usd,
                )

        return alerts
