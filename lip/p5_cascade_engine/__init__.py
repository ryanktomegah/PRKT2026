"""
p5_cascade_engine — P5 Supply Chain Cascade Detection & Prevention.

Sprint 3a: Corporate entity resolution layer.
Sprint 3b: Cascade propagation engine (BFS + intervention optimiser).
Sprint 3c: C2 cascade-adjusted PD, C3 settlement trigger, C5 stress bridge.
Sprint 3d: C7 coordinated intervention API.
"""
from .cascade_alerts import CascadeAlert, build_cascade_alert
from .cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
    CascadeRiskNode,
)
from .cascade_settlement_trigger import CascadeSettlementTrigger
from .corporate_features import get_corporate_node_features
from .corporate_graph import CascadeGraph, CorporateEdge, CorporateNode
from .entity_resolver import CorporateEntityResolver
from .intervention_optimizer import (
    InterventionAction,
    InterventionOptimizer,
    InterventionPlan,
)
from .stress_cascade_bridge import StressCascadeBridge

__all__ = [
    "CascadeAlert",
    "CascadeGraph",
    "CascadePropagationEngine",
    "CascadeResult",
    "CascadeRiskNode",
    "CascadeSettlementTrigger",
    "CorporateEdge",
    "CorporateEntityResolver",
    "CorporateNode",
    "InterventionAction",
    "InterventionOptimizer",
    "InterventionPlan",
    "StressCascadeBridge",
    "build_cascade_alert",
    "get_corporate_node_features",
]
