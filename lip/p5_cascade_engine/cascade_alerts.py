"""
cascade_alerts.py — Cascade alert generation for bank risk desks.

Combines propagation + intervention into a structured alert with
severity classification and exclusivity window. Sprint 3d wires
this to C7 Cascade API endpoints.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .cascade_propagation import CascadePropagationEngine, CascadeResult
from .constants import (
    CASCADE_ALERT_EXCLUSIVITY_HOURS,
    CASCADE_ALERT_SEVERITY_HIGH_USD,
    CASCADE_ALERT_SEVERITY_MEDIUM_USD,
    CASCADE_ALERT_THRESHOLD_USD,
)
from .corporate_graph import CascadeGraph
from .intervention_optimizer import InterventionOptimizer, InterventionPlan

logger = logging.getLogger(__name__)


@dataclass
class CascadeAlert:
    """Structured cascade alert for bank risk desk consumption."""

    alert_id: str
    alert_type: str
    severity: str
    origin_corporate_id: str
    origin_sector: str
    origin_jurisdiction: str
    cascade_result: CascadeResult
    intervention_plan: Optional[InterventionPlan]
    timestamp: float
    expires_at: float


def build_cascade_alert(
    graph: CascadeGraph,
    origin_corporate_id: str,
    budget_usd: float,
    threshold: float = 0.50,
    trigger_type: str = "PAYMENT_FAILURE",
) -> Optional[CascadeAlert]:
    """Build a cascade alert if CVaR exceeds the alert threshold.

    Args:
        graph: Corporate-level CascadeGraph.
        origin_corporate_id: Corporate ID of the failed entity.
        budget_usd: Total bridge lending budget for intervention.
        threshold: Cascade probability threshold for propagation.
        trigger_type: "PAYMENT_FAILURE" or "CORRIDOR_STRESS".

    Returns:
        CascadeAlert if total CVaR >= CASCADE_ALERT_THRESHOLD_USD, else None.
    """
    engine = CascadePropagationEngine()
    cascade_result = engine.propagate(
        graph, origin_corporate_id, threshold=threshold, trigger_type=trigger_type
    )

    total_var = Decimal(str(cascade_result.total_value_at_risk_usd))
    if total_var < CASCADE_ALERT_THRESHOLD_USD:
        return None

    # Intervention plan
    optimizer = InterventionOptimizer()
    plan = optimizer.optimize(cascade_result, graph, budget_usd=budget_usd)

    # Severity classification
    if total_var >= CASCADE_ALERT_SEVERITY_HIGH_USD:
        severity = "HIGH"
    elif total_var >= CASCADE_ALERT_SEVERITY_MEDIUM_USD:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # Alert metadata
    now = time.time()
    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    alert_id = f"CASC-{date_str}-{int(now * 1000) % 100000:05d}"

    # Origin metadata
    origin_node = graph.nodes.get(origin_corporate_id)
    origin_sector = origin_node.sector if origin_node else "UNKNOWN"
    origin_jurisdiction = origin_node.jurisdiction if origin_node else "XX"

    return CascadeAlert(
        alert_id=alert_id,
        alert_type="CASCADE_PROPAGATION",
        severity=severity,
        origin_corporate_id=origin_corporate_id,
        origin_sector=origin_sector,
        origin_jurisdiction=origin_jurisdiction,
        cascade_result=cascade_result,
        intervention_plan=plan,
        timestamp=now,
        expires_at=now + CASCADE_ALERT_EXCLUSIVITY_HOURS * 3600,
    )
