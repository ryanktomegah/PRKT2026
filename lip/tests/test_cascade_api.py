"""
test_cascade_api.py — TDD tests for Sprint 3d C7 Cascade Intervention API.

Tests cascade service layer and router endpoints using in-memory CascadeGraph.
"""
from __future__ import annotations

import time
from typing import Dict

import pytest

from lip.api.cascade_service import CascadeService, InterventionStatus  # noqa: F401
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)


def _build_test_graph() -> CascadeGraph:
    """Build a deterministic test graph for cascade API tests.

    Topology:
        CORP_A (origin) --0.90--> CORP_B --0.85--> CORP_D
                        \\--0.80--> CORP_C

    CORP_A is in AUTO sector, DE jurisdiction.
    CORP_B and CORP_C are CORP_A's direct dependents.
    CORP_D is a second-hop dependent via CORP_B.
    """
    nodes = {
        "CORP_A": CorporateNode(
            corporate_id="CORP_A",
            name_hash="hash_a",
            bics=frozenset({"DEUTDEFF"}),
            sector="AUTO",
            jurisdiction="DE",
            total_outgoing_volume_30d=5_000_000.0,
        ),
        "CORP_B": CorporateNode(
            corporate_id="CORP_B",
            name_hash="hash_b",
            bics=frozenset({"COBADEFF"}),
            sector="PARTS",
            jurisdiction="DE",
            total_incoming_volume_30d=3_000_000.0,
        ),
        "CORP_C": CorporateNode(
            corporate_id="CORP_C",
            name_hash="hash_c",
            bics=frozenset({"BNPAFRPP"}),
            sector="LOGISTICS",
            jurisdiction="FR",
            total_incoming_volume_30d=2_000_000.0,
        ),
        "CORP_D": CorporateNode(
            corporate_id="CORP_D",
            name_hash="hash_d",
            bics=frozenset({"HSBCGB2L"}),
            sector="STEEL",
            jurisdiction="GB",
            total_incoming_volume_30d=1_500_000.0,
        ),
    }

    edges = [
        CorporateEdge(
            source_corporate_id="CORP_A",
            target_corporate_id="CORP_B",
            total_volume_30d=3_000_000.0,
            payment_count_30d=50,
            dependency_score=0.90,
        ),
        CorporateEdge(
            source_corporate_id="CORP_A",
            target_corporate_id="CORP_C",
            total_volume_30d=2_000_000.0,
            payment_count_30d=30,
            dependency_score=0.80,
        ),
        CorporateEdge(
            source_corporate_id="CORP_B",
            target_corporate_id="CORP_D",
            total_volume_30d=1_500_000.0,
            payment_count_30d=20,
            dependency_score=0.85,
        ),
    ]

    adjacency: Dict[str, Dict[str, CorporateEdge]] = {
        "CORP_A": {"CORP_B": edges[0], "CORP_C": edges[1]},
        "CORP_B": {"CORP_D": edges[2]},
    }
    reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = {
        "CORP_B": {"CORP_A": edges[0]},
        "CORP_C": {"CORP_A": edges[1]},
        "CORP_D": {"CORP_B": edges[2]},
    }

    return CascadeGraph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
        node_count=4,
        edge_count=3,
        avg_dependency_score=0.85,
        build_timestamp=time.time(),
    )


# ── Cascade Service Tests ───────────────────────────────────────────────────


class TestCascadeServiceAnalyze:

    def test_analyze_returns_alert_for_known_corporate(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        assert alert.alert_id.startswith("CASC-")
        assert alert.severity in ("HIGH", "MEDIUM")
        assert alert.origin_corporate_id == "CORP_A"

    def test_analyze_returns_none_for_unknown_corporate(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_UNKNOWN")
        assert alert is None

    def test_analyze_stores_alert_for_later_retrieval(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        retrieved = svc.get_alert(alert.alert_id)
        assert retrieved is not None
        assert retrieved.alert_id == alert.alert_id

    def test_analyze_custom_budget(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A", budget_usd=100.0)
        # Small budget — optimizer may not be able to intervene much
        assert alert is not None

    def test_analyze_custom_trigger_type(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A", trigger_type="CORRIDOR_STRESS")
        assert alert is not None
        assert alert.cascade_result.trigger_type == "CORRIDOR_STRESS"


class TestCascadeServiceListAlerts:

    def test_list_alerts_empty(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alerts = svc.list_alerts()
        assert alerts == []

    def test_list_alerts_after_analyze(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        svc.analyze("CORP_A")
        alerts = svc.list_alerts()
        assert len(alerts) == 1

    def test_list_alerts_severity_filter(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        svc.analyze("CORP_A")
        # Filter for severity that doesn't match
        alerts = svc.list_alerts(severity="LOW")
        assert len(alerts) == 0

    def test_list_alerts_active_only_excludes_expired(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        # Force expire
        svc._alerts[alert.alert_id].expires_at = time.time() - 1
        alerts = svc.list_alerts(active_only=True)
        assert len(alerts) == 0
        # All alerts still returns it
        all_alerts = svc.list_alerts(active_only=False)
        assert len(all_alerts) == 1


class TestCascadeServiceGetAlert:

    def test_get_alert_found(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        detail = svc.get_alert(alert.alert_id)
        assert detail is not None
        assert detail.origin_corporate_id == "CORP_A"

    def test_get_alert_not_found(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        assert svc.get_alert("CASC-NONEXISTENT") is None


class TestCascadeServiceExecuteIntervention:

    def test_execute_valid_intervention(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        assert alert.intervention_plan is not None
        priorities = [a.priority for a in alert.intervention_plan.interventions]
        status = svc.execute_intervention(alert.alert_id, priorities[:1])
        assert status is not None
        assert status.status == "EXECUTED"
        assert len(status.executed_actions) == 1
        assert status.total_bridge_amount_usd > 0

    def test_execute_unknown_alert_returns_none(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        status = svc.execute_intervention("CASC-NONEXISTENT", [1])
        assert status is None

    def test_execute_expired_alert_returns_expired_status(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        svc._alerts[alert.alert_id].expires_at = time.time() - 1
        status = svc.execute_intervention(alert.alert_id, [1])
        assert status is not None
        assert status.status == "EXPIRED"

    def test_execute_invalid_priorities_returns_empty(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        status = svc.execute_intervention(alert.alert_id, [999])
        assert status is not None
        assert status.status == "EXECUTED"
        assert len(status.executed_actions) == 0

    def test_get_intervention_status(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        alert = svc.analyze("CORP_A")
        assert alert is not None
        priorities = [a.priority for a in alert.intervention_plan.interventions]
        svc.execute_intervention(alert.alert_id, priorities)
        status = svc.get_intervention_status(alert.alert_id)
        assert status is not None
        assert status.status == "EXECUTED"


class TestCascadeServiceGraphQuery:

    def test_get_corporate_neighbors_known(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        neighborhood = svc.get_corporate_neighbors("CORP_A")
        assert neighborhood is not None
        assert neighborhood.corporate_id == "CORP_A"
        assert neighborhood.sector == "AUTO"
        assert len(neighborhood.downstream) == 2  # CORP_B, CORP_C
        assert len(neighborhood.upstream) == 0

    def test_get_corporate_neighbors_unknown(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        assert svc.get_corporate_neighbors("CORP_UNKNOWN") is None

    def test_get_corporate_neighbors_with_upstream(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        neighborhood = svc.get_corporate_neighbors("CORP_B")
        assert neighborhood is not None
        assert len(neighborhood.upstream) == 1  # CORP_A
        assert len(neighborhood.downstream) == 1  # CORP_D

    def test_get_graph_summary(self):
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        summary = svc.get_graph_summary()
        assert summary.node_count == 4
        assert summary.edge_count == 3
        assert summary.avg_dependency_score == pytest.approx(0.85, abs=0.01)


# ── Cascade Router Tests (FastAPI TestClient) ───────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from lip.api.cascade_router import make_cascade_router

    def _make_test_app() -> tuple:
        """Create a FastAPI test app with cascade router."""
        graph = _build_test_graph()
        svc = CascadeService(graph, default_budget_usd=10_000_000.0)
        app = FastAPI()
        app.include_router(make_cascade_router(svc), prefix="/cascade")
        return app, svc

    class TestCascadeRouterAnalyze:

        def test_post_analyze_success(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.post(
                "/cascade/analyze", json={"corporate_id": "CORP_A"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["alert_id"] is not None
            assert data["severity"] in ("HIGH", "MEDIUM")
            assert data["total_value_at_risk_usd"] > 0
            assert data["nodes_at_risk"] > 0

        def test_post_analyze_unknown_corporate(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.post(
                "/cascade/analyze", json={"corporate_id": "UNKNOWN"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["alert_id"] is None
            assert data["total_value_at_risk_usd"] == 0

        def test_post_analyze_custom_budget(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.post(
                "/cascade/analyze",
                json={"corporate_id": "CORP_A", "budget_usd": 500.0},
            )
            assert resp.status_code == 200

    class TestCascadeRouterAlertList:

        def test_get_alerts_empty(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.get("/cascade/alerts")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

        def test_get_alerts_after_analyze(self):
            app, svc = _make_test_app()
            svc.analyze("CORP_A")
            client = TestClient(app)
            resp = client.get("/cascade/alerts")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["alerts"][0]["origin_corporate_id"] == "CORP_A"

        def test_get_alerts_severity_filter(self):
            app, svc = _make_test_app()
            svc.analyze("CORP_A")
            client = TestClient(app)
            resp = client.get("/cascade/alerts?severity=LOW")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

    class TestCascadeRouterAlertDetail:

        def test_get_alert_detail(self):
            app, svc = _make_test_app()
            alert = svc.analyze("CORP_A")
            assert alert is not None
            client = TestClient(app)
            resp = client.get(f"/cascade/alerts/{alert.alert_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["alert_id"] == alert.alert_id
            assert len(data["interventions"]) > 0

        def test_get_alert_detail_not_found(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.get("/cascade/alerts/CASC-NONEXISTENT")
            assert resp.status_code == 404

    class TestCascadeRouterExecute:

        def test_execute_intervention(self):
            app, svc = _make_test_app()
            alert = svc.analyze("CORP_A")
            assert alert is not None
            client = TestClient(app)
            resp = client.post(
                f"/cascade/alerts/{alert.alert_id}/execute",
                json={"action_priorities": [1]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "EXECUTED"

        def test_execute_not_found(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.post(
                "/cascade/alerts/CASC-NONEXISTENT/execute",
                json={"action_priorities": [1]},
            )
            assert resp.status_code == 404

        def test_execute_expired(self):
            app, svc = _make_test_app()
            alert = svc.analyze("CORP_A")
            assert alert is not None
            svc._alerts[alert.alert_id].expires_at = time.time() - 1
            client = TestClient(app)
            resp = client.post(
                f"/cascade/alerts/{alert.alert_id}/execute",
                json={"action_priorities": [1]},
            )
            assert resp.status_code == 410

    class TestCascadeRouterGraph:

        def test_get_corporate_neighborhood(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.get("/cascade/graph/CORP_A")
            assert resp.status_code == 200
            data = resp.json()
            assert data["corporate_id"] == "CORP_A"
            assert data["sector"] == "AUTO"
            assert len(data["downstream"]) == 2

        def test_get_corporate_not_found(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.get("/cascade/graph/UNKNOWN")
            assert resp.status_code == 404

        def test_get_graph_summary(self):
            app, _ = _make_test_app()
            client = TestClient(app)
            resp = client.get("/cascade/graph")
            assert resp.status_code == 200
            data = resp.json()
            assert data["node_count"] == 4
            assert data["edge_count"] == 3

except ImportError:
    pass  # FastAPI not installed — skip router tests
