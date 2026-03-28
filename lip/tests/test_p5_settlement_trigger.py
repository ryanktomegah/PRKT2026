"""
test_p5_settlement_trigger.py — TDD tests for cascade settlement trigger.

When C3 detects a payment failure on a high-dependency edge, the trigger
evaluates whether it should generate a cascade alert.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.cascade_alerts import CascadeAlert
from lip.p5_cascade_engine.cascade_settlement_trigger import CascadeSettlementTrigger
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.constants import CASCADE_ALERT_DEPENDENCY_THRESHOLD


def _make_node(cid: str) -> CorporateNode:
    return CorporateNode(corporate_id=cid)


def _make_edge(src: str, tgt: str, volume: float, dep: float) -> CorporateEdge:
    return CorporateEdge(
        source_corporate_id=src,
        target_corporate_id=tgt,
        total_volume_30d=volume,
        payment_count_30d=10,
        dependency_score=dep,
    )


def _build_graph(node_ids: list[str], edges: list[CorporateEdge]) -> CascadeGraph:
    nodes = {cid: _make_node(cid) for cid in node_ids}
    adjacency: dict = {cid: {} for cid in node_ids}
    reverse_adjacency: dict = {cid: {} for cid in node_ids}
    for e in edges:
        adjacency.setdefault(e.source_corporate_id, {})[e.target_corporate_id] = e
        reverse_adjacency.setdefault(e.target_corporate_id, {})[e.source_corporate_id] = e
    return CascadeGraph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
        node_count=len(nodes),
        edge_count=len(edges),
    )


_BIC_TO_CORP = {
    "COBADEFF": "BMW",
    "DEUTDEFF": "BOSCH",
    "HSBCGB2L": "SIEMENS",
}


class TestCascadeSettlementTrigger:

    def test_high_dependency_failure_triggers_alert(self):
        """Payment failure on high-dep edge (dep=0.8 > 0.50) triggers cascade."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        trigger = CascadeSettlementTrigger(graph, _BIC_TO_CORP, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="COBADEFF",
            receiving_bic="DEUTDEFF",
            amount_usd=5_000_000,
            dependency_score=0.8,
        )

        assert alert is not None
        assert isinstance(alert, CascadeAlert)
        assert alert.origin_corporate_id == "BMW"

    def test_low_dependency_filtered(self):
        """Payment failure on low-dep edge (dep=0.3 < 0.50) does NOT trigger."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.3)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        trigger = CascadeSettlementTrigger(graph, _BIC_TO_CORP, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="COBADEFF",
            receiving_bic="DEUTDEFF",
            amount_usd=5_000_000,
            dependency_score=0.3,
        )

        assert alert is None

    def test_unmapped_bic_returns_none(self):
        """Unknown BIC (not in mapping) returns None."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        trigger = CascadeSettlementTrigger(graph, _BIC_TO_CORP, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="UNKNOWN_BIC",
            receiving_bic="DEUTDEFF",
            amount_usd=5_000_000,
            dependency_score=0.8,
        )

        assert alert is None

    def test_intra_corporate_returns_none(self):
        """Same corporate on both sides = intra-corporate, no cascade."""
        bic_to_corp = {"COBADEFF": "BMW", "BNPAFRPP": "BMW"}
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        trigger = CascadeSettlementTrigger(graph, bic_to_corp, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="COBADEFF",
            receiving_bic="BNPAFRPP",
            amount_usd=5_000_000,
            dependency_score=0.8,
        )

        assert alert is None

    def test_below_cvar_threshold_returns_none(self):
        """CVaR below $1M = no alert even with high dependency."""
        edges = [_make_edge("BMW", "BOSCH", 500_000, 0.8)]  # 0.8 * 500K = 400K < $1M
        graph = _build_graph(["BMW", "BOSCH"], edges)
        trigger = CascadeSettlementTrigger(graph, _BIC_TO_CORP, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="COBADEFF",
            receiving_bic="DEUTDEFF",
            amount_usd=100_000,
            dependency_score=0.8,
        )

        assert alert is None

    def test_alert_has_intervention_plan(self):
        """Alert includes intervention plan when CVaR is significant."""
        edges = [
            _make_edge("BMW", "BOSCH", 50_000_000, 0.8),
            _make_edge("BOSCH", "SIEMENS", 20_000_000, 0.7),
        ]
        graph = _build_graph(["BMW", "BOSCH", "SIEMENS"], edges)
        trigger = CascadeSettlementTrigger(graph, _BIC_TO_CORP, budget_usd=100_000_000)

        alert = trigger.on_settlement_failure(
            sending_bic="COBADEFF",
            receiving_bic="DEUTDEFF",
            amount_usd=5_000_000,
            dependency_score=0.8,
        )

        assert alert is not None
        assert alert.intervention_plan is not None
