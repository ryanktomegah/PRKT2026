"""
test_p5_cascade_alerts.py — TDD tests for cascade alert generation.

Tests cover: severity classification, alert_id format, below-threshold
returns None, exclusivity window, end-to-end alert generation.
"""
from __future__ import annotations

import pytest

from lip.p5_cascade_engine.cascade_alerts import build_cascade_alert
from lip.p5_cascade_engine.constants import (
    CASCADE_ALERT_EXCLUSIVITY_HOURS,
)
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)


def _make_node(cid: str, sector: str = "UNKNOWN", jur: str = "XX") -> CorporateNode:
    return CorporateNode(corporate_id=cid, sector=sector, jurisdiction=jur)


def _make_edge(
    src: str, tgt: str, volume: float = 1000000.0, dep: float = 0.8
) -> CorporateEdge:
    return CorporateEdge(
        source_corporate_id=src,
        target_corporate_id=tgt,
        total_volume_30d=volume,
        payment_count_30d=10,
        dependency_score=dep,
    )


def _build_graph(
    nodes: dict[str, CorporateNode], edges: list[CorporateEdge]
) -> CascadeGraph:
    adjacency: dict = {cid: {} for cid in nodes}
    reverse_adjacency: dict = {cid: {} for cid in nodes}
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


class TestCascadeAlertSeverity:
    """Severity classification based on CVaR."""

    def test_high_severity(self):
        """CVaR >= $10M -> HIGH."""
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B", "Auto Parts", "DE"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.8)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.severity == "HIGH"

    def test_medium_severity(self):
        """CVaR >= $1M but < $10M -> MEDIUM."""
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 5_000_000, 0.8)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.severity == "MEDIUM"

    def test_below_threshold_returns_none(self):
        """CVaR < $1M -> no alert."""
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 500_000, 0.8)]  # 0.8 * 500K = 400K < 1M
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is None


class TestCascadeAlertStructure:
    """Alert structure and metadata."""

    def test_alert_id_format(self):
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.alert_id.startswith("CASC-")
        assert alert.alert_type == "CASCADE_PROPAGATION"

    def test_exclusivity_window(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.expires_at == pytest.approx(
            alert.timestamp + CASCADE_ALERT_EXCLUSIVITY_HOURS * 3600, abs=1
        )

    def test_alert_carries_origin_metadata(self):
        nodes = {
            "A": _make_node("A", "Automobiles", "DE"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.origin_corporate_id == "A"
        assert alert.origin_sector == "Automobiles"
        assert alert.origin_jurisdiction == "DE"

    def test_alert_has_intervention_plan(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.intervention_plan is not None
        assert len(alert.intervention_plan.interventions) >= 1

    def test_alert_has_cascade_result(self):
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
        }
        edges = [_make_edge("A", "B", 50_000_000, 0.9)]
        graph = _build_graph(nodes, edges)

        alert = build_cascade_alert(graph, "A", budget_usd=100_000_000)

        assert alert is not None
        assert alert.cascade_result.origin_corporate_id == "A"
        assert alert.cascade_result.total_value_at_risk_usd > 0

    def test_unknown_origin_returns_none(self):
        graph = CascadeGraph()
        alert = build_cascade_alert(graph, "UNKNOWN", budget_usd=100_000_000)
        assert alert is None
