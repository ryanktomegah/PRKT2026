# Sprint 3d — C7 Coordinated Intervention API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the P5 cascade engine through 5 C7 API endpoints — enabling bank risk desks to trigger cascade analysis, review intervention plans, execute bridge loans, and query the corporate dependency graph.

**Architecture:** New `cascade_service.py` (service layer with in-memory alert store + TTL eviction) and `cascade_router.py` (FastAPI router factory with Pydantic request/response models), wired into `app.py` via existing conditional router pattern. All business logic delegated to existing P5 cascade engine classes.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, dataclasses, pytest, ruff

---

## Context

This is Session 9 of a 23-session build program. Sprint 3d is the final sprint for P5 Supply Chain Cascade Detection & Prevention. After this session, the cascade engine is fully operational with an HTTP API for bank interaction.

**What exists:** CascadeGraph (3a), BFS propagation + CVaR + intervention optimizer + cascade alerts (3b), C2/C3/C5 integration bridges (3c).

**What this builds:** 5 HTTP endpoints following the established `make_<router>(service, auth_dep)` factory pattern. The service layer manages cascade alert lifecycle (create → active → executed/expired) with lazy TTL eviction.

**Established patterns to follow:**
- `lip/api/miplo_router.py` — router factory with closure-captured service
- `lip/api/miplo_service.py` — service layer with business logic
- `lip/api/app.py` — conditional wiring in `create_app()`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/tests/test_cascade_api.py` | TDD test suite (written first) |
| Create | `lip/api/cascade_service.py` | Alert lifecycle, graph queries, intervention tracking |
| Create | `lip/api/cascade_router.py` | 5 HTTP endpoints + Pydantic models |
| Modify | `lip/api/app.py` | Wire cascade router (conditional on cascade_graph) |

---

## Task 1: Write TDD Test Suite

**Files:**
- Create: `lip/tests/test_cascade_api.py`

- [ ] **Step 1: Write the complete test file**

```python
"""
test_cascade_api.py — TDD tests for Sprint 3d C7 Cascade Intervention API.

Tests cascade service layer and router endpoints using in-memory CascadeGraph.
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Dict, List, Optional

import pytest

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

from lip.api.cascade_service import CascadeService, InterventionStatus


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
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_cascade_api.py -v 2>&1 | head -20`
Expected: ImportError for `cascade_service` and `cascade_router`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_cascade_api.py
git commit -m "test(api): add TDD test suite for Sprint 3d cascade intervention API"
```

---

## Task 2: Implement Cascade Service

**Files:**
- Create: `lip/api/cascade_service.py`

- [ ] **Step 1: Write the cascade service implementation**

```python
"""
cascade_service.py — Cascade intervention service layer.

Manages CascadeGraph, alert lifecycle (create → active → executed/expired),
and intervention execution tracking. In-memory storage for v0.

Sprint 3d: C7 Coordinated Intervention API (P5 Supply Chain Cascade).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lip.p5_cascade_engine.cascade_alerts import CascadeAlert, build_cascade_alert
from lip.p5_cascade_engine.corporate_graph import CascadeGraph

logger = logging.getLogger(__name__)


@dataclass
class InterventionStatus:
    """Tracks execution state of a cascade intervention."""

    alert_id: str
    status: str  # "PENDING", "EXECUTED", "EXPIRED"
    executed_actions: List[int] = field(default_factory=list)
    total_bridge_amount_usd: float = 0.0
    total_value_prevented_usd: float = 0.0
    executed_at: Optional[float] = None


@dataclass
class CorporateNeighborhood:
    """Dependency neighborhood for a single corporate."""

    corporate_id: str
    sector: str
    jurisdiction: str
    cascade_centrality: float
    upstream: List[dict] = field(default_factory=list)
    downstream: List[dict] = field(default_factory=list)


@dataclass
class GraphSummary:
    """High-level graph metadata."""

    node_count: int
    edge_count: int
    avg_dependency_score: float
    max_centrality_node: str
    build_timestamp: float


class CascadeService:
    """Cascade alert lifecycle management and graph queries.

    Holds a CascadeGraph reference and an in-memory alert store with
    lazy TTL eviction. Delegates cascade analysis to build_cascade_alert()
    and intervention optimization to InterventionOptimizer (via the alert).
    """

    def __init__(self, cascade_graph: CascadeGraph, default_budget_usd: float):
        self._graph = cascade_graph
        self._budget = default_budget_usd
        self._alerts: Dict[str, CascadeAlert] = {}
        self._intervention_status: Dict[str, InterventionStatus] = {}

    def analyze(
        self,
        corporate_id: str,
        budget_usd: Optional[float] = None,
        trigger_type: str = "PAYMENT_FAILURE",
    ) -> Optional[CascadeAlert]:
        """Trigger cascade analysis for a corporate.

        Delegates to build_cascade_alert(). If CVaR >= threshold, stores
        the alert for later retrieval and returns it.
        """
        budget = budget_usd if budget_usd is not None else self._budget
        alert = build_cascade_alert(
            graph=self._graph,
            origin_corporate_id=corporate_id,
            budget_usd=budget,
            trigger_type=trigger_type,
        )
        if alert is not None:
            self._alerts[alert.alert_id] = alert
            logger.info(
                "analyze: alert=%s severity=%s cvar=%.0f corporate=%s",
                alert.alert_id,
                alert.severity,
                alert.cascade_result.total_value_at_risk_usd,
                corporate_id,
            )
        return alert

    def list_alerts(
        self,
        severity: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CascadeAlert]:
        """List alerts with optional severity filter and active-only flag."""
        now = time.time()
        results = []
        for alert in self._alerts.values():
            if active_only and alert.expires_at < now:
                continue
            if severity is not None and alert.severity != severity:
                continue
            results.append(alert)
        return sorted(results, key=lambda a: a.timestamp, reverse=True)

    def get_alert(self, alert_id: str) -> Optional[CascadeAlert]:
        """Get a specific alert by ID. Returns expired alerts too."""
        return self._alerts.get(alert_id)

    def execute_intervention(
        self, alert_id: str, action_priorities: List[int]
    ) -> Optional[InterventionStatus]:
        """Execute selected interventions from an alert's plan.

        Returns None if alert not found. Returns EXPIRED status if
        the alert's exclusivity window has passed.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None

        now = time.time()
        if alert.expires_at < now:
            status = InterventionStatus(alert_id=alert_id, status="EXPIRED")
            self._intervention_status[alert_id] = status
            return status

        # Find matching interventions
        executed = []
        total_bridge = 0.0
        total_value = 0.0
        if alert.intervention_plan is not None:
            for action in alert.intervention_plan.interventions:
                if action.priority in action_priorities:
                    executed.append(action.priority)
                    total_bridge += action.bridge_amount_usd
                    total_value += action.cascade_value_prevented_usd

        status = InterventionStatus(
            alert_id=alert_id,
            status="EXECUTED",
            executed_actions=executed,
            total_bridge_amount_usd=total_bridge,
            total_value_prevented_usd=total_value,
            executed_at=now,
        )
        self._intervention_status[alert_id] = status
        logger.info(
            "execute_intervention: alert=%s actions=%d bridge=%.0f value_prevented=%.0f",
            alert_id,
            len(executed),
            total_bridge,
            total_value,
        )
        return status

    def get_intervention_status(self, alert_id: str) -> Optional[InterventionStatus]:
        """Get execution status for an alert."""
        return self._intervention_status.get(alert_id)

    def get_corporate_neighbors(
        self, corporate_id: str
    ) -> Optional[CorporateNeighborhood]:
        """Get upstream and downstream dependency neighborhood."""
        node = self._graph.nodes.get(corporate_id)
        if node is None:
            return None

        downstream = []
        for target_id, edge in self._graph.adjacency.get(corporate_id, {}).items():
            downstream.append({
                "corporate_id": target_id,
                "dependency_score": edge.dependency_score,
                "volume_30d": edge.total_volume_30d,
            })

        upstream = []
        for source_id, edge in self._graph.reverse_adjacency.get(
            corporate_id, {}
        ).items():
            upstream.append({
                "corporate_id": source_id,
                "dependency_score": edge.dependency_score,
                "volume_30d": edge.total_volume_30d,
            })

        return CorporateNeighborhood(
            corporate_id=corporate_id,
            sector=node.sector,
            jurisdiction=node.jurisdiction,
            cascade_centrality=node.cascade_centrality,
            upstream=upstream,
            downstream=downstream,
        )

    def get_graph_summary(self) -> GraphSummary:
        """Return high-level graph metadata."""
        return GraphSummary(
            node_count=self._graph.node_count,
            edge_count=self._graph.edge_count,
            avg_dependency_score=self._graph.avg_dependency_score,
            max_centrality_node=self._graph.max_cascade_centrality_node,
            build_timestamp=self._graph.build_timestamp,
        )
```

- [ ] **Step 2: Run service tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_cascade_api.py -k "TestCascadeService" -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/cascade_service.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/api/cascade_service.py
git commit -m "feat(api): add cascade service — alert lifecycle, graph queries, intervention tracking"
```

---

## Task 3: Implement Cascade Router

**Files:**
- Create: `lip/api/cascade_router.py`

- [ ] **Step 1: Write the cascade router implementation**

```python
"""
cascade_router.py — C7 Coordinated Intervention API HTTP endpoints.
Sprint 3d: P5 Supply Chain Cascade Detection & Prevention.

Endpoints:
  POST /cascade/analyze              — Trigger cascade analysis for a corporate
  GET  /cascade/alerts               — List active alerts (optional severity filter)
  GET  /cascade/alerts/{alert_id}    — Get specific alert with intervention plan
  POST /cascade/alerts/{alert_id}/execute — Execute selected interventions
  GET  /cascade/graph/{corporate_id} — Query corporate dependency neighborhood
  GET  /cascade/graph                — Graph summary metadata
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    # ── Request / Response Models ────────────────────────────────────────────

    class CascadeAnalyzeRequest(BaseModel):
        """Request to trigger cascade analysis."""

        corporate_id: str = Field(..., description="Corporate ID to analyze")
        budget_usd: Optional[float] = Field(
            default=None, description="Override intervention budget (USD)"
        )
        trigger_type: str = Field(
            default="PAYMENT_FAILURE",
            description="PAYMENT_FAILURE or CORRIDOR_STRESS",
        )

    class CascadeAnalyzeResponse(BaseModel):
        """Result of cascade analysis."""

        alert_id: Optional[str] = None
        severity: Optional[str] = None
        total_value_at_risk_usd: float = 0.0
        cascade_amplification_factor: float = 0.0
        nodes_at_risk: int = 0
        intervention_count: int = 0
        total_intervention_cost_usd: float = 0.0
        total_value_prevented_usd: float = 0.0
        expires_at: Optional[float] = None

    class CascadeAlertSummary(BaseModel):
        """Summary of one alert in the list."""

        alert_id: str
        severity: str
        origin_corporate_id: str
        origin_sector: str
        total_value_at_risk_usd: float
        intervention_count: int
        timestamp: float
        expires_at: float
        is_expired: bool

    class CascadeAlertListResponse(BaseModel):
        """List of cascade alerts."""

        alerts: List[CascadeAlertSummary]
        total: int

    class InterventionDetail(BaseModel):
        """One intervention action in an alert."""

        priority: int
        source_corporate_id: str
        target_corporate_id: str
        bridge_amount_usd: float
        cascade_value_prevented_usd: float
        cost_efficiency_ratio: float

    class CascadeAlertDetailResponse(BaseModel):
        """Full detail for a single alert."""

        alert_id: str
        severity: str
        origin_corporate_id: str
        origin_sector: str
        origin_jurisdiction: str
        total_value_at_risk_usd: float
        cascade_amplification_factor: float
        nodes_at_risk: int
        max_hops_reached: int
        trigger_type: str
        interventions: List[InterventionDetail]
        total_intervention_cost_usd: float
        total_value_prevented_usd: float
        budget_utilization_pct: float
        timestamp: float
        expires_at: float
        execution_status: Optional[str] = None

    class ExecuteInterventionRequest(BaseModel):
        """Request to execute selected interventions."""

        action_priorities: List[int] = Field(
            ..., description="Priority indices of interventions to execute"
        )

    class ExecuteInterventionResponse(BaseModel):
        """Result of intervention execution."""

        alert_id: str
        status: str
        executed_actions: List[int]
        total_bridge_amount_usd: float
        total_value_prevented_usd: float

    class NeighborEdge(BaseModel):
        """One edge in a corporate neighborhood."""

        corporate_id: str
        dependency_score: float
        volume_30d: float

    class CorporateNeighborhoodResponse(BaseModel):
        """Dependency neighborhood for a corporate."""

        corporate_id: str
        sector: str
        jurisdiction: str
        cascade_centrality: float
        upstream: List[NeighborEdge]
        downstream: List[NeighborEdge]

    class GraphSummaryResponse(BaseModel):
        """High-level graph metadata."""

        node_count: int
        edge_count: int
        avg_dependency_score: float
        max_centrality_node: str
        build_timestamp: float

    # ── Router Factory ───────────────────────────────────────────────────────

    def make_cascade_router(cascade_service: Any, auth_dependency=None) -> APIRouter:
        """Factory that builds the C7 Cascade Intervention API router.

        Follows the same pattern as make_miplo_router, make_admin_router, etc.
        The cascade_service is captured by closure — no global state.
        """
        router = APIRouter(tags=["cascade"])

        if auth_dependency is not None:
            deps = [Depends(auth_dependency)]
        else:
            deps = []

        @router.post("/analyze", response_model=CascadeAnalyzeResponse, dependencies=deps)
        async def analyze(request: CascadeAnalyzeRequest):
            """Trigger cascade analysis for a corporate entity.

            Runs BFS propagation from the specified corporate, computes CVaR,
            and generates an intervention plan if CVaR >= $1M threshold.
            """
            alert = cascade_service.analyze(
                corporate_id=request.corporate_id,
                budget_usd=request.budget_usd,
                trigger_type=request.trigger_type,
            )
            if alert is None:
                return CascadeAnalyzeResponse()

            plan = alert.intervention_plan
            return CascadeAnalyzeResponse(
                alert_id=alert.alert_id,
                severity=alert.severity,
                total_value_at_risk_usd=alert.cascade_result.total_value_at_risk_usd,
                cascade_amplification_factor=alert.cascade_result.cascade_amplification_factor,
                nodes_at_risk=alert.cascade_result.nodes_above_threshold,
                intervention_count=len(plan.interventions) if plan else 0,
                total_intervention_cost_usd=plan.total_cost_usd if plan else 0.0,
                total_value_prevented_usd=plan.total_value_prevented_usd if plan else 0.0,
                expires_at=alert.expires_at,
            )

        @router.get("/alerts", response_model=CascadeAlertListResponse, dependencies=deps)
        async def list_alerts(
            severity: Optional[str] = None,
            active_only: bool = True,
        ):
            """List cascade alerts with optional severity filter."""
            now = time.time()
            alerts = cascade_service.list_alerts(
                severity=severity, active_only=active_only
            )
            summaries = [
                CascadeAlertSummary(
                    alert_id=a.alert_id,
                    severity=a.severity,
                    origin_corporate_id=a.origin_corporate_id,
                    origin_sector=a.origin_sector,
                    total_value_at_risk_usd=a.cascade_result.total_value_at_risk_usd,
                    intervention_count=(
                        len(a.intervention_plan.interventions) if a.intervention_plan else 0
                    ),
                    timestamp=a.timestamp,
                    expires_at=a.expires_at,
                    is_expired=a.expires_at < now,
                )
                for a in alerts
            ]
            return CascadeAlertListResponse(alerts=summaries, total=len(summaries))

        @router.get(
            "/alerts/{alert_id}",
            response_model=CascadeAlertDetailResponse,
            dependencies=deps,
        )
        async def get_alert_detail(alert_id: str):
            """Get full detail for a specific cascade alert."""
            alert = cascade_service.get_alert(alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

            plan = alert.intervention_plan
            interventions = []
            if plan:
                for action in plan.interventions:
                    interventions.append(
                        InterventionDetail(
                            priority=action.priority,
                            source_corporate_id=action.source_corporate_id,
                            target_corporate_id=action.target_corporate_id,
                            bridge_amount_usd=action.bridge_amount_usd,
                            cascade_value_prevented_usd=action.cascade_value_prevented_usd,
                            cost_efficiency_ratio=action.cost_efficiency_ratio,
                        )
                    )

            exec_status = cascade_service.get_intervention_status(alert_id)

            return CascadeAlertDetailResponse(
                alert_id=alert.alert_id,
                severity=alert.severity,
                origin_corporate_id=alert.origin_corporate_id,
                origin_sector=alert.origin_sector,
                origin_jurisdiction=alert.origin_jurisdiction,
                total_value_at_risk_usd=alert.cascade_result.total_value_at_risk_usd,
                cascade_amplification_factor=alert.cascade_result.cascade_amplification_factor,
                nodes_at_risk=alert.cascade_result.nodes_above_threshold,
                max_hops_reached=alert.cascade_result.max_hops_reached,
                trigger_type=alert.cascade_result.trigger_type,
                interventions=interventions,
                total_intervention_cost_usd=plan.total_cost_usd if plan else 0.0,
                total_value_prevented_usd=plan.total_value_prevented_usd if plan else 0.0,
                budget_utilization_pct=plan.budget_utilization_pct if plan else 0.0,
                timestamp=alert.timestamp,
                expires_at=alert.expires_at,
                execution_status=exec_status.status if exec_status else None,
            )

        @router.post(
            "/alerts/{alert_id}/execute",
            response_model=ExecuteInterventionResponse,
            dependencies=deps,
        )
        async def execute_intervention(alert_id: str, request: ExecuteInterventionRequest):
            """Execute selected interventions from an alert's plan.

            The action_priorities list specifies which interventions (by priority
            index) to execute. Returns 404 if alert not found, 410 if expired.
            """
            status = cascade_service.execute_intervention(
                alert_id=alert_id, action_priorities=request.action_priorities
            )
            if status is None:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
            if status.status == "EXPIRED":
                raise HTTPException(
                    status_code=410,
                    detail=f"Alert {alert_id} exclusivity window has expired",
                )

            return ExecuteInterventionResponse(
                alert_id=status.alert_id,
                status=status.status,
                executed_actions=status.executed_actions,
                total_bridge_amount_usd=status.total_bridge_amount_usd,
                total_value_prevented_usd=status.total_value_prevented_usd,
            )

        @router.get(
            "/graph/{corporate_id}",
            response_model=CorporateNeighborhoodResponse,
            dependencies=deps,
        )
        async def get_corporate_neighborhood(corporate_id: str):
            """Query a corporate's upstream and downstream dependencies."""
            neighborhood = cascade_service.get_corporate_neighbors(corporate_id)
            if neighborhood is None:
                raise HTTPException(
                    status_code=404, detail=f"Corporate {corporate_id} not found"
                )

            return CorporateNeighborhoodResponse(
                corporate_id=neighborhood.corporate_id,
                sector=neighborhood.sector,
                jurisdiction=neighborhood.jurisdiction,
                cascade_centrality=neighborhood.cascade_centrality,
                upstream=[
                    NeighborEdge(**e) for e in neighborhood.upstream
                ],
                downstream=[
                    NeighborEdge(**e) for e in neighborhood.downstream
                ],
            )

        @router.get("/graph", response_model=GraphSummaryResponse, dependencies=deps)
        async def get_graph_summary():
            """Return high-level graph metadata."""
            summary = cascade_service.get_graph_summary()
            return GraphSummaryResponse(
                node_count=summary.node_count,
                edge_count=summary.edge_count,
                avg_dependency_score=summary.avg_dependency_score,
                max_centrality_node=summary.max_centrality_node,
                build_timestamp=summary.build_timestamp,
            )

        return router

except ImportError:
    logger.debug("FastAPI not installed — cascade router not available")

    def make_cascade_router(*args, **kwargs):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the cascade router")
```

- [ ] **Step 2: Run all tests (service + router)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_cascade_api.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/cascade_router.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/api/cascade_router.py
git commit -m "feat(api): add cascade router — 5 endpoints for intervention API"
```

---

## Task 4: Wire Cascade Router into app.py

**Files:**
- Modify: `lip/api/app.py` (add cascade wiring after MIPLO block)

- [ ] **Step 1: Add cascade_graph parameter and router wiring**

Add `cascade_graph=None` parameter to `create_app()`, then add the cascade router wiring block after the MIPLO block (before `return application`):

```python
        # Cascade intervention API (P5 — available in bank + processor mode)
        if cascade_graph is not None:
            from lip.api.cascade_router import make_cascade_router
            from lip.api.cascade_service import CascadeService

            cascade_svc = CascadeService(cascade_graph, default_budget_usd=10_000_000.0)
            application.include_router(
                make_cascade_router(cascade_svc, auth_dependency=auth_dep),
                prefix="/cascade",
            )
```

- [ ] **Step 2: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/app.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add lip/api/app.py
git commit -m "feat(api): wire cascade router into create_app() (conditional on cascade_graph)"
```

---

## Task 5: Full Regression Test

- [ ] **Step 1: Run all cascade API tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_cascade_api.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run all P5 tests (regression)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_*.py lip/tests/test_c2_cascade_pricing.py lip/tests/test_cascade_api.py -v`
Expected: ALL PASS (87 P5 + 21 cascade API tests)

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -k "not (test_returns_dict or test_returns_fitted or test_calibration_attaches or test_run_end_to_end)" -q 2>&1 | tail -20`
Expected: ~1750+ tests pass, zero failures

- [ ] **Step 4: Run ruff on full lip/ directory**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/`
Expected: zero errors

---

## Verification Checklist

Before declaring Session 9 complete:

1. [ ] `python -m pytest lip/tests/test_cascade_api.py -v` — all tests pass
2. [ ] `python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py` — no regressions
3. [ ] `ruff check lip/` — zero errors
4. [ ] POST /cascade/analyze returns alert with CVaR and intervention plan
5. [ ] GET /cascade/alerts returns list with severity filter
6. [ ] GET /cascade/alerts/{id} returns full detail with interventions
7. [ ] POST /cascade/alerts/{id}/execute returns execution status
8. [ ] GET /cascade/graph/{id} returns corporate neighborhood
9. [ ] GET /cascade/graph returns graph summary
10. [ ] Expired alerts return 410 on execute, still visible in list(active_only=false)
11. [ ] Unknown alert IDs return 404
12. [ ] Service follows router factory pattern (make_cascade_router)
13. [ ] No secrets, artifacts/, or c6_corpus_*.json committed
