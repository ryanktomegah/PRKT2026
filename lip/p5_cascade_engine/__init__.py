"""
p5_cascade_engine — P5 Supply Chain Cascade Detection & Prevention.

Sprint 3a: Corporate entity resolution layer.
Sprint 3b: Cascade propagation engine (BFS + intervention optimiser).
Sprint 3c-3d: C2/C7 integration.
"""
from .cascade_alerts import CascadeAlert, build_cascade_alert
from .cascade_propagation import (
    CascadePropagationEngine,
    CascadeResult,
    CascadeRiskNode,
)
from .corporate_features import get_corporate_node_features
from .corporate_graph import CascadeGraph, CorporateEdge, CorporateNode
from .entity_resolver import CorporateEntityResolver
from .intervention_optimizer import (
    InterventionAction,
    InterventionOptimizer,
    InterventionPlan,
)

__all__ = [
    "CascadeAlert",
    "CascadeGraph",
    "CascadePropagationEngine",
    "CascadeResult",
    "CascadeRiskNode",
    "CorporateEdge",
    "CorporateEntityResolver",
    "CorporateNode",
    "InterventionAction",
    "InterventionOptimizer",
    "InterventionPlan",
    "build_cascade_alert",
    "get_corporate_node_features",
]
