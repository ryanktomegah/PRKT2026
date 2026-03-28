"""
p5_cascade_engine — P5 Supply Chain Cascade Detection & Prevention.

Sprint 3a: Corporate entity resolution layer.
Sprint 3b: Cascade propagation engine (BFS + intervention optimiser).
Sprint 3c-3d: C2/C7 integration.
"""
from .corporate_features import get_corporate_node_features
from .corporate_graph import CascadeGraph, CorporateEdge, CorporateNode
from .entity_resolver import CorporateEntityResolver

__all__ = [
    "CascadeGraph",
    "CorporateEdge",
    "CorporateEntityResolver",
    "CorporateNode",
    "get_corporate_node_features",
]
