"""
test_p5_stress_bridge.py — TDD tests for C5 stress → P5 cascade bridge.

When C5 detects a corridor stress regime, the bridge identifies affected
corporates and runs cascade propagation from each.
"""
from __future__ import annotations

from lip.c5_streaming.stress_regime_detector import StressRegimeEvent
from lip.p5_cascade_engine.cascade_alerts import CascadeAlert
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)
from lip.p5_cascade_engine.stress_cascade_bridge import StressCascadeBridge


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


def _stress_event(corridor: str = "EUR_USD") -> StressRegimeEvent:
    return StressRegimeEvent(
        corridor=corridor,
        failure_rate_1h=0.15,
        baseline_rate=0.03,
        ratio=5.0,
        triggered_at=1711612800.0,
    )


class TestStressCascadeBridge:

    def test_stress_triggers_cascade_for_mapped_corporates(self):
        """Stress on EUR_USD corridor triggers cascade for BMW (mapped to EUR_USD)."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        corridor_map = {"EUR_USD": ["BMW"]}
        bridge = StressCascadeBridge(graph, corridor_map, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("EUR_USD"))

        assert len(alerts) == 1
        assert isinstance(alerts[0], CascadeAlert)
        assert alerts[0].origin_corporate_id == "BMW"

    def test_multiple_corporates_on_corridor(self):
        """Multiple corporates on same corridor = multiple propagation runs."""
        edges = [
            _make_edge("BMW", "BOSCH", 50_000_000, 0.8),
            _make_edge("SIEMENS", "BOSCH", 30_000_000, 0.7),
        ]
        graph = _build_graph(["BMW", "BOSCH", "SIEMENS"], edges)
        corridor_map = {"EUR_USD": ["BMW", "SIEMENS"]}
        bridge = StressCascadeBridge(graph, corridor_map, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("EUR_USD"))

        # Both should generate alerts (CVaR > $1M for each)
        assert len(alerts) == 2
        origins = {a.origin_corporate_id for a in alerts}
        assert origins == {"BMW", "SIEMENS"}

    def test_unmapped_corridor_returns_empty(self):
        """Unknown corridor returns no alerts."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        corridor_map = {"EUR_USD": ["BMW"]}
        bridge = StressCascadeBridge(graph, corridor_map, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("GBP_JPY"))

        assert len(alerts) == 0

    def test_below_cvar_threshold_filtered(self):
        """Corporate with small volume = CVaR below $1M = no alert."""
        edges = [_make_edge("SMALL_CORP", "OTHER", 500_000, 0.8)]
        graph = _build_graph(["SMALL_CORP", "OTHER"], edges)
        corridor_map = {"EUR_USD": ["SMALL_CORP"]}
        bridge = StressCascadeBridge(graph, corridor_map, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("EUR_USD"))

        assert len(alerts) == 0

    def test_trigger_type_is_corridor_stress(self):
        """Alert trigger type should be CORRIDOR_STRESS, not PAYMENT_FAILURE."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        corridor_map = {"EUR_USD": ["BMW"]}
        bridge = StressCascadeBridge(graph, corridor_map, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("EUR_USD"))

        assert len(alerts) == 1
        assert alerts[0].cascade_result.trigger_type == "CORRIDOR_STRESS"

    def test_empty_corridor_map(self):
        """Empty corridor map = no alerts for any event."""
        edges = [_make_edge("BMW", "BOSCH", 50_000_000, 0.8)]
        graph = _build_graph(["BMW", "BOSCH"], edges)
        bridge = StressCascadeBridge(graph, {}, budget_usd=100_000_000)

        alerts = bridge.on_stress_regime_event(_stress_event("EUR_USD"))

        assert len(alerts) == 0
