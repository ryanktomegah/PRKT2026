# Sprint 3a — P5 Corporate-Level Graph Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the corporate entity resolution layer that elevates BIC-level payment graphs to corporate-level supply chain graphs for P5 cascade analysis.

**Architecture:** A new `lip/p5_cascade_engine/` module contains data structures (`CorporateNode`, `CorporateEdge`, `CascadeGraph`), entity resolution (`CorporateEntityResolver`), 8-dim corporate feature vectors, and Brandes betweenness centrality. The module consumes `CorridorGraph` from C1's `BICGraphBuilder` and produces a `CascadeGraph` that Sprint 3b's cascade propagation engine will consume.

**Tech Stack:** Python 3.14, dataclasses, numpy, pytest, ruff

---

## Context

This is Session 6 of a 23-session build program. Sprint 3a is the first session for P5 (Supply Chain Cascade). The existing BICGraphBuilder (lip/c1_failure_classifier/graph_builder.py) builds BIC-to-BIC payment graphs with `PaymentEdge` objects carrying Bayesian-smoothed `dependency_score` values. This sprint creates a new module that lifts those BIC-level graphs to corporate-level graphs by aggregating payment edges between the same pair of corporates.

**Key existing data structures consumed by this sprint:**
- `PaymentEdge` (graph_builder.py:30) — fields: `uetr`, `sending_bic`, `receiving_bic`, `amount_usd`, `currency_pair`, `timestamp`, `dependency_score`, `observation_count`, `features` (dict with optional `"failed"` boolean key)
- `CorridorGraph` (graph_builder.py:68) — fields: `nodes` (List[str] of BICs), `edges` (List[PaymentEdge]), `adjacency` (nested dict {sender: {receiver: [PaymentEdge]}})

**What this enables:** After this session, Sprint 3b can build the BFS cascade propagation algorithm on top of `CascadeGraph`, Sprint 3c can compute cascade-adjusted PD, and Sprint 3d can build the coordinated intervention API.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/p5_cascade_engine/__init__.py` | Module exports |
| Create | `lip/p5_cascade_engine/constants.py` | P5 cascade thresholds (QUANT-protected) |
| Create | `lip/p5_cascade_engine/corporate_graph.py` | CorporateNode, CorporateEdge, CascadeGraph dataclasses |
| Create | `lip/p5_cascade_engine/entity_resolver.py` | CorporateEntityResolver — BIC graph → corporate graph |
| Create | `lip/p5_cascade_engine/corporate_features.py` | 8-dim corporate node feature extraction |
| Create | `lip/tests/test_p5_corporate_graph.py` | TDD tests for all Sprint 3a components |
| Create | `lip/tests/test_p5_centrality.py` | TDD tests for Brandes betweenness centrality |

---

## Task 1: P5 Constants + Module Scaffold

**Files:**
- Create: `lip/p5_cascade_engine/__init__.py`
- Create: `lip/p5_cascade_engine/constants.py`

- [ ] **Step 1: Create module directory and __init__.py**

```bash
mkdir -p lip/p5_cascade_engine
```

Write `lip/p5_cascade_engine/__init__.py`:

```python
"""
p5_cascade_engine — P5 Supply Chain Cascade Detection & Prevention.

Sprint 3a: Corporate entity resolution layer.
Sprint 3b: Cascade propagation engine (BFS + intervention optimiser).
Sprint 3c-3d: C2/C7 integration.
"""
```

- [ ] **Step 2: Write constants.py**

Write `lip/p5_cascade_engine/constants.py`:

```python
"""
P5 cascade engine constants.

All thresholds require QUANT sign-off to change (per P5 blueprint §7.6).
"""
from decimal import Decimal

# ── Cascade propagation thresholds (QUANT sign-off required) ─────────────────
CASCADE_INTERVENTION_THRESHOLD = 0.70
"""Minimum cascade probability to include a node in intervention plan."""

CASCADE_ALERT_THRESHOLD_USD = Decimal("1000000")
"""$1M — minimum cascade value at risk to trigger bank alert."""

CASCADE_ALERT_DEPENDENCY_THRESHOLD = 0.50
"""Minimum dependency_score for C3 to trigger cascade re-evaluation."""

CASCADE_MAX_HOPS = 5
"""Maximum BFS depth. Academic evidence: >95% of cascade value within 3 hops."""

CASCADE_DISCOUNT_CAP = Decimal("0.30")
"""Maximum PD reduction from cascade discount (prevents gaming)."""

INTERVENTION_BUDGET_SHARE = Decimal("0.25")
"""Maximum fraction of bank bridge lending capacity for cascade interventions."""

# ── Entity resolution ────────────────────────────────────────────────────────
CORPORATE_EDGE_MIN_PAYMENTS_30D = 2
"""Minimum payment count to form a corporate edge (filters noise)."""

CORPORATE_CENTRALITY_BATCH_INTERVAL_HOURS = 4
"""Hours between betweenness centrality recomputation."""

# ── Corporate feature vector ─────────────────────────────────────────────────
CORPORATE_NODE_FEATURE_DIM = 8
"""8-dimensional corporate node feature vector."""
```

- [ ] **Step 3: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/p5_cascade_engine/__init__.py lip/p5_cascade_engine/constants.py
git commit -m "feat(p5): scaffold cascade engine module with QUANT-protected constants"
```

---

## Task 2: Corporate Graph Data Structures — TDD Tests

**Files:**
- Create: `lip/tests/test_p5_corporate_graph.py`

- [ ] **Step 1: Write test file with data structure + entity resolution + feature tests**

Write `lip/tests/test_p5_corporate_graph.py`:

```python
"""
test_p5_corporate_graph.py — TDD tests for P5 corporate graph data structures,
entity resolution, and corporate node features.

Covers:
  - CorporateNode, CorporateEdge, CascadeGraph construction
  - CorporateEntityResolver.resolve() — multi-BIC, intra-corporate filter, edge cases
  - Corporate node feature extraction — 8-dim vector, edge case guards
"""
from __future__ import annotations

import numpy as np
import pytest

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p5_cascade_engine.constants import (
    CORPORATE_EDGE_MIN_PAYMENTS_30D,
    CORPORATE_NODE_FEATURE_DIM,
)


def _make_edge(
    uetr: str = "u1",
    sending_bic: str = "COBADEFF",
    receiving_bic: str = "DEUTDEFF",
    amount_usd: float = 100_000.0,
    currency_pair: str = "USD_EUR",
    timestamp: float = 1_700_000_000.0,
    dependency_score: float = 0.3,
    failed: bool = False,
) -> PaymentEdge:
    return PaymentEdge(
        uetr=uetr,
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount_usd=amount_usd,
        currency_pair=currency_pair,
        timestamp=timestamp,
        dependency_score=dependency_score,
        features={"failed": failed},
    )


def _make_bic_graph(edges: list[PaymentEdge]) -> CorridorGraph:
    """Build a CorridorGraph from a list of PaymentEdge objects."""
    from collections import defaultdict

    adjacency: dict = defaultdict(lambda: defaultdict(list))
    nodes_set: set = set()
    for e in edges:
        adjacency[e.sending_bic][e.receiving_bic].append(e)
        nodes_set.add(e.sending_bic)
        nodes_set.add(e.receiving_bic)
    return CorridorGraph(
        nodes=sorted(nodes_set),
        edges=list(edges),
        adjacency={k: dict(v) for k, v in adjacency.items()},
    )


# BIC → corporate mapping for tests
_BIC_TO_CORP = {
    "COBADEFF": "BMW_CORP",       # BMW uses Commerzbank
    "BNPAFRPP": "BMW_CORP",       # BMW also uses BNP Paribas
    "DEUTDEFF": "BOSCH_CORP",     # Bosch uses Deutsche Bank
    "HSBCGB2L": "SIEMENS_CORP",   # Siemens uses HSBC
    "BARCGB22": "SIEMENS_CORP",   # Siemens also uses Barclays
}


# ── CorporateEntityResolver Tests ────────────────────────────────────────────


class TestEntityResolver:

    def test_basic_two_corporate_resolution(self):
        """Two corporates, one BIC each, two payments → one corporate edge."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=200_000, dependency_score=0.4),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.node_count == 2
        assert cascade.edge_count == 1
        assert "BMW_CORP" in cascade.nodes
        assert "BOSCH_CORP" in cascade.nodes

        # Check corporate edge
        edge = cascade.adjacency["BMW_CORP"]["BOSCH_CORP"]
        assert edge.total_volume_30d == 300_000.0
        assert edge.payment_count_30d == 2

    def test_multi_bic_same_corporate(self):
        """BMW uses two BICs (COBADEFF + BNPAFRPP) → both aggregate to BMW_CORP."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
            _make_edge(uetr="u2", sending_bic="BNPAFRPP", receiving_bic="DEUTDEFF",
                       amount_usd=200_000, dependency_score=0.5),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.node_count == 2
        edge = cascade.adjacency["BMW_CORP"]["BOSCH_CORP"]
        assert edge.total_volume_30d == 300_000.0

        # BMW node should list both BICs
        bmw = cascade.nodes["BMW_CORP"]
        assert "COBADEFF" in bmw.bics
        assert "BNPAFRPP" in bmw.bics

    def test_intra_corporate_transfer_filtered(self):
        """BMW's COBADEFF → BMW's BNPAFRPP is intra-corporate, must be excluded."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="BNPAFRPP",
                       amount_usd=500_000, dependency_score=0.9),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="BNPAFRPP",
                       amount_usd=500_000, dependency_score=0.9),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.edge_count == 0
        assert cascade.node_count == 0  # no inter-corporate edges means no nodes

    def test_unmapped_bic_excluded(self):
        """BIC not in mapping is silently excluded."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="UNKNOWNBIC", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.5),
            _make_edge(uetr="u2", sending_bic="UNKNOWNBIC", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.5),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.edge_count == 0

    def test_minimum_payment_count_filter(self):
        """Corporate edge with < CORPORATE_EDGE_MIN_PAYMENTS_30D payments is excluded."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
            # Only 1 payment — below threshold of 2
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.edge_count == 0

    def test_zero_volume_edge_excluded(self):
        """Edges with amount_usd <= 0 are excluded (prevents div-by-zero)."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=0.0, dependency_score=0.3),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=0.0, dependency_score=0.3),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.edge_count == 0

    def test_dependency_score_volume_weighted(self):
        """Corporate dependency_score = volume-weighted mean of BIC-level scores."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.2),
            _make_edge(uetr="u2", sending_bic="BNPAFRPP", receiving_bic="DEUTDEFF",
                       amount_usd=300_000, dependency_score=0.6),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        edge = cascade.adjacency["BMW_CORP"]["BOSCH_CORP"]
        # Weighted: (100K * 0.2 + 300K * 0.6) / (100K + 300K) = 200K / 400K = 0.5
        assert abs(edge.dependency_score - 0.5) < 1e-9

    def test_failure_rate_computation(self):
        """failure_rate_30d = fraction of edges with features['failed'] == True."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, failed=True),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, failed=False),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        edge = cascade.adjacency["BMW_CORP"]["BOSCH_CORP"]
        assert abs(edge.failure_rate_30d - 0.5) < 1e-9

    def test_empty_graph(self):
        """Empty CorridorGraph produces empty CascadeGraph."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        bic_graph = CorridorGraph(nodes=[], edges=[], adjacency={})
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert cascade.node_count == 0
        assert cascade.edge_count == 0

    def test_reverse_adjacency_built(self):
        """reverse_adjacency enables downstream lookups."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        assert "BOSCH_CORP" in cascade.reverse_adjacency
        assert "BMW_CORP" in cascade.reverse_adjacency["BOSCH_CORP"]

    def test_corporate_metadata_applied(self):
        """Sector and jurisdiction from metadata override BIC-derived defaults."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000),
        ]
        metadata = {
            "BMW_CORP": {"name_hash": "abc123", "sector": "Automobiles", "jurisdiction": "DE"},
            "BOSCH_CORP": {"name_hash": "def456", "sector": "Auto Components", "jurisdiction": "DE"},
        }
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(
            bic_to_corporate=_BIC_TO_CORP,
            corporate_metadata=metadata,
        )
        cascade = resolver.resolve(bic_graph)

        assert cascade.nodes["BMW_CORP"].sector == "Automobiles"
        assert cascade.nodes["BOSCH_CORP"].sector == "Auto Components"

    def test_jurisdiction_from_bic_when_no_metadata(self):
        """Without metadata, jurisdiction derived from BIC chars 4-5."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=100_000),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=100_000),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        # COBADEFF → chars 4-5 = "DE", HSBCGB2L → chars 4-5 = "GB"
        assert cascade.nodes["BMW_CORP"].jurisdiction == "DE"
        assert cascade.nodes["SIEMENS_CORP"].jurisdiction == "GB"


# ── Corporate Node Features Tests ────────────────────────────────────────────


class TestCorporateNodeFeatures:

    def _build_three_corp_graph(self):
        """BMW → Bosch, BMW → Siemens, Siemens → Bosch (triangle)."""
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.4),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.4),
            _make_edge(uetr="u3", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=50_000, dependency_score=0.2),
            _make_edge(uetr="u4", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=50_000, dependency_score=0.2),
            _make_edge(uetr="u5", sending_bic="HSBCGB2L", receiving_bic="DEUTDEFF",
                       amount_usd=75_000, dependency_score=0.6),
            _make_edge(uetr="u6", sending_bic="HSBCGB2L", receiving_bic="DEUTDEFF",
                       amount_usd=75_000, dependency_score=0.6),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        return resolver.resolve(bic_graph)

    def test_feature_vector_shape(self):
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BMW_CORP")
        assert isinstance(feats, np.ndarray)
        assert feats.shape == (CORPORATE_NODE_FEATURE_DIM,)

    def test_feature_values_bmw(self):
        """BMW: outgoing only (no incoming), 2 customers, 0 suppliers."""
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BMW_CORP")

        # idx 0: log1p(incoming) — BMW has no incoming → log1p(0) = 0
        assert feats[0] == pytest.approx(0.0, abs=1e-6)
        # idx 1: log1p(outgoing) — BMW sends 100K+100K+50K+50K = 300K
        assert feats[1] == pytest.approx(np.log1p(300_000), abs=1e-6)
        # idx 2: supplier_count — 0 (no incoming edges)
        assert feats[2] == 0.0
        # idx 3: customer_count — 2 (Bosch + Siemens)
        assert feats[3] == 2.0
        # idx 4: max_dependency_score — 0.0 (no upstream deps)
        assert feats[4] == 0.0

    def test_feature_values_bosch(self):
        """Bosch: incoming from BMW + Siemens, no outgoing."""
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BOSCH_CORP")

        # idx 2: supplier_count — 2 (BMW + Siemens)
        assert feats[2] == 2.0
        # idx 3: customer_count — 0 (no outgoing edges)
        assert feats[3] == 0.0
        # idx 4: max_dependency_score — max(0.4 from BMW, 0.6 from Siemens) = 0.6
        assert feats[4] == pytest.approx(0.6, abs=1e-6)

    def test_hhi_single_supplier(self):
        """Single supplier → HHI = 1.0 (maximum concentration)."""
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.5),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.5),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)

        feats = get_corporate_node_features(cascade, "BOSCH_CORP")
        # idx 5: HHI — single supplier = 1.0
        assert feats[5] == pytest.approx(1.0, abs=1e-6)

    def test_hhi_equal_two_suppliers(self):
        """Two equal suppliers → HHI = 0.5."""
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BOSCH_CORP")

        # Bosch receives: 200K from BMW, 150K from Siemens
        # shares: 200/350 = 0.5714, 150/350 = 0.4286
        # HHI = 0.5714^2 + 0.4286^2 = 0.3265 + 0.1837 = 0.5102
        assert feats[5] == pytest.approx(0.5102, abs=0.001)

    def test_isolated_node_returns_zeros(self):
        """Node not in the graph → zeros(8)."""
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "NONEXISTENT_CORP")
        assert feats.shape == (CORPORATE_NODE_FEATURE_DIM,)
        assert np.all(feats == 0.0)


# ── CascadeGraph Query Method Tests ──────────────────────────────────────────


class TestCascadeGraphQueries:

    def _build_graph(self):
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.8),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.8),
            _make_edge(uetr="u3", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=50_000, dependency_score=0.1),
            _make_edge(uetr="u4", sending_bic="COBADEFF", receiving_bic="HSBCGB2L",
                       amount_usd=50_000, dependency_score=0.1),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        return resolver.resolve(bic_graph)

    def test_get_downstream_dependents_above_threshold(self):
        cascade = self._build_graph()
        deps = cascade.get_downstream_dependents("BMW_CORP", threshold=0.5)
        assert "BOSCH_CORP" in deps
        assert "SIEMENS_CORP" not in deps  # dep score 0.1 < 0.5

    def test_get_downstream_dependents_low_threshold(self):
        cascade = self._build_graph()
        deps = cascade.get_downstream_dependents("BMW_CORP", threshold=0.05)
        assert len(deps) == 2  # Both Bosch and Siemens
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py -v 2>&1 | head -15`
Expected: ImportError for `CorporateEntityResolver`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_p5_corporate_graph.py
git commit -m "test(p5): add TDD test suite for corporate graph — entity resolution, features, queries"
```

---

## Task 3: Corporate Graph Data Structures

**Files:**
- Create: `lip/p5_cascade_engine/corporate_graph.py`

- [ ] **Step 1: Write corporate_graph.py**

```python
"""
corporate_graph.py — Corporate-level graph data structures for P5 cascade engine.

CorporateNode: represents a corporate entity transacting via one or more BICs.
CorporateEdge: directed supply chain payment edge between two corporates.
CascadeGraph: immutable snapshot of the corporate-level directed graph.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CorporateNode:
    """A corporate entity in the supply chain graph.

    corporate_id is an opaque bank-provided hash — BPI never sees the real name.
    bics is the frozenset of BIC codes through which this corporate transacts.
    """

    corporate_id: str
    name_hash: str = ""
    bics: FrozenSet[str] = field(default_factory=frozenset)
    sector: str = "UNKNOWN"
    jurisdiction: str = "XX"
    total_incoming_volume_30d: float = 0.0
    total_outgoing_volume_30d: float = 0.0
    dependency_scores: Dict[str, float] = field(default_factory=dict)
    cascade_centrality: float = 0.0


@dataclass
class CorporateEdge:
    """Directed supply chain payment edge between two corporates.

    Aggregated from BIC-level PaymentEdge objects via CorporateEntityResolver.
    dependency_score is the volume-weighted mean of BIC-level scores.
    """

    source_corporate_id: str
    target_corporate_id: str
    total_volume_30d: float = 0.0
    payment_count_30d: int = 0
    dependency_score: float = 0.0
    failure_rate_30d: float = 0.0
    avg_settlement_hours: float = 0.0
    last_payment_timestamp: float = 0.0


@dataclass
class CascadeGraph:
    """Snapshot of the corporate-level directed graph.

    Immutable in structure (no add/remove after construction).
    CorporateNode.cascade_centrality is updated by compute_centrality().
    """

    nodes: Dict[str, CorporateNode] = field(default_factory=dict)
    edges: List[CorporateEdge] = field(default_factory=list)
    adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = field(default_factory=dict)
    build_timestamp: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    avg_dependency_score: float = 0.0
    max_cascade_centrality_node: str = ""

    def get_downstream_dependents(
        self, corporate_id: str, threshold: float = 0.2
    ) -> List[str]:
        """Return corporate IDs downstream with dependency_score >= threshold."""
        targets = self.adjacency.get(corporate_id, {})
        return [
            cid for cid, edge in targets.items()
            if edge.dependency_score >= threshold
        ]

    def get_corporates_on_corridor(self, corridor: str) -> List[str]:
        """Return corporate IDs with payment volume on the given corridor.

        Corridor format: 'USD_EUR' (currency pair from PaymentEdge.currency_pair).
        Requires edge-level corridor tracking (stored during resolve()).
        """
        # Will be implemented when corridor metadata is added to CorporateEdge
        # For now, returns empty (Sprint 3b will add corridor tracking)
        return []

    def compute_centrality(self) -> None:
        """Compute betweenness centrality for all nodes (Brandes algorithm).

        Updates each CorporateNode.cascade_centrality in place.
        O(V * E) — run as batch job, not real-time.
        """
        if not self.nodes:
            return

        centrality = _brandes_betweenness(self.adjacency, set(self.nodes.keys()))

        max_centrality = 0.0
        max_node = ""
        for corp_id, score in centrality.items():
            self.nodes[corp_id].cascade_centrality = score
            if score > max_centrality:
                max_centrality = score
                max_node = corp_id

        self.max_cascade_centrality_node = max_node
        logger.info(
            "compute_centrality: %d nodes, max_centrality=%.4f at %s",
            len(self.nodes), max_centrality, max_node,
        )


def _brandes_betweenness(
    adjacency: Dict[str, Dict[str, CorporateEdge]],
    all_nodes: set,
) -> Dict[str, float]:
    """Compute betweenness centrality using Brandes (2001) algorithm.

    Unweighted variant — we care about path structure, not path cost.
    Returns {corporate_id: centrality_score} normalized to [0, 1].

    Algorithm for each source s:
      1. BFS from s → compute shortest path counts σ(s, t) and predecessors
      2. Back-propagate dependency δ from leaves to source
      3. Accumulate centrality for intermediate nodes
    """
    cb: Dict[str, float] = {v: 0.0 for v in all_nodes}

    for s in all_nodes:
        # BFS phase
        stack: list = []
        predecessors: Dict[str, list] = {v: [] for v in all_nodes}
        sigma: Dict[str, int] = {v: 0 for v in all_nodes}
        sigma[s] = 1
        dist: Dict[str, int] = {v: -1 for v in all_nodes}
        dist[s] = 0
        queue: deque = deque([s])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adjacency.get(v, {}):
                if w not in all_nodes:
                    continue
                if dist[w] < 0:
                    queue.append(w)
                    dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)

        # Back-propagation phase
        delta: Dict[str, float] = {v: 0.0 for v in all_nodes}
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]

    # Normalize to [0, 1]
    n = len(all_nodes)
    if n > 2:
        normalization = (n - 1) * (n - 2)
        for v in cb:
            cb[v] /= normalization

    return cb
```

- [ ] **Step 2: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/corporate_graph.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add lip/p5_cascade_engine/corporate_graph.py
git commit -m "feat(p5): add CorporateNode, CorporateEdge, CascadeGraph data structures + Brandes centrality"
```

---

## Task 4: Corporate Entity Resolver

**Files:**
- Create: `lip/p5_cascade_engine/entity_resolver.py`

- [ ] **Step 1: Write entity_resolver.py**

```python
"""
entity_resolver.py — Elevate BIC-level payment graphs to corporate-level cascade graphs.

The enrolled bank provides a {bic: corporate_id} mapping. This module aggregates
BIC-level PaymentEdge objects into CorporateEdge objects using volume-weighted
dependency scores, filters intra-corporate transfers, and builds the CascadeGraph.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p5_cascade_engine.constants import CORPORATE_EDGE_MIN_PAYMENTS_30D
from lip.p5_cascade_engine.corporate_graph import (
    CascadeGraph,
    CorporateEdge,
    CorporateNode,
)

logger = logging.getLogger(__name__)


class CorporateEntityResolver:
    """Resolves BIC-level payment edges to corporate-level supply chain edges.

    The bank provides a mapping: {bic: corporate_id}. This class aggregates
    all BIC-level edges between two corporates into a single CorporateEdge
    with aggregated volume, dependency, and failure rate.
    """

    def __init__(
        self,
        bic_to_corporate: Dict[str, str],
        corporate_metadata: Optional[Dict[str, Dict]] = None,
    ) -> None:
        """
        Args:
            bic_to_corporate: Bank-provided mapping {bic: corporate_id}.
                BICs not in this mapping are excluded from the corporate graph.
            corporate_metadata: Optional {corporate_id: {"name_hash": ..., "sector": ..., "jurisdiction": ...}}.
                When not provided, jurisdiction derived from BIC chars 4-5,
                sector defaults to "UNKNOWN".
        """
        self._mapping = dict(bic_to_corporate)
        self._metadata = corporate_metadata or {}

    def resolve(self, bic_graph: CorridorGraph) -> CascadeGraph:
        """Elevate a BIC-level graph to a corporate-level cascade graph.

        Algorithm:
        1. Map each PaymentEdge to (source_corp, target_corp)
        2. Filter: unmapped BICs, intra-corporate, zero-volume
        3. Aggregate by corporate pair: volume, count, dependency, failure rate
        4. Filter: min payment count
        5. Build CorporateNode for each unique corporate
        6. Construct CascadeGraph with adjacency + reverse_adjacency
        """
        # Phase 1: Aggregate BIC edges to corporate pairs
        pair_edges: Dict[tuple, List[PaymentEdge]] = defaultdict(list)
        corp_bics: Dict[str, Set[str]] = defaultdict(set)

        for edge in bic_graph.edges:
            src_corp = self._mapping.get(edge.sending_bic)
            tgt_corp = self._mapping.get(edge.receiving_bic)

            # Skip unmapped BICs
            if src_corp is None or tgt_corp is None:
                continue
            # Skip intra-corporate transfers
            if src_corp == tgt_corp:
                continue
            # Skip zero-volume edges
            if edge.amount_usd <= 0:
                continue

            pair_edges[(src_corp, tgt_corp)].append(edge)
            corp_bics[src_corp].add(edge.sending_bic)
            corp_bics[tgt_corp].add(edge.receiving_bic)

        # Phase 2: Build CorporateEdge from aggregated edges
        corporate_edges: List[CorporateEdge] = []

        for (src_corp, tgt_corp), edges in pair_edges.items():
            if len(edges) < CORPORATE_EDGE_MIN_PAYMENTS_30D:
                continue

            total_volume = sum(e.amount_usd for e in edges)
            payment_count = len(edges)

            # Volume-weighted dependency score
            dep_score = sum(e.amount_usd * e.dependency_score for e in edges) / total_volume

            # Failure rate
            failed_count = sum(1 for e in edges if e.features.get("failed", False))
            failure_rate = failed_count / payment_count

            max_ts = max(e.timestamp for e in edges)

            corporate_edges.append(CorporateEdge(
                source_corporate_id=src_corp,
                target_corporate_id=tgt_corp,
                total_volume_30d=total_volume,
                payment_count_30d=payment_count,
                dependency_score=dep_score,
                failure_rate_30d=failure_rate,
                avg_settlement_hours=0.0,  # C9 integration in Sprint 3b
                last_payment_timestamp=max_ts,
            ))

        # Phase 3: Build adjacency structures
        adjacency: Dict[str, Dict[str, CorporateEdge]] = defaultdict(dict)
        reverse_adjacency: Dict[str, Dict[str, CorporateEdge]] = defaultdict(dict)

        for ce in corporate_edges:
            adjacency[ce.source_corporate_id][ce.target_corporate_id] = ce
            reverse_adjacency[ce.target_corporate_id][ce.source_corporate_id] = ce

        # Phase 4: Build CorporateNode for each unique corporate in edges
        all_corp_ids: Set[str] = set()
        for ce in corporate_edges:
            all_corp_ids.add(ce.source_corporate_id)
            all_corp_ids.add(ce.target_corporate_id)

        nodes: Dict[str, CorporateNode] = {}
        for corp_id in all_corp_ids:
            meta = self._metadata.get(corp_id, {})

            # Jurisdiction: from metadata, or from primary BIC chars 4-5
            jurisdiction = meta.get("jurisdiction", "")
            if not jurisdiction:
                bics = corp_bics.get(corp_id, set())
                if bics:
                    primary_bic = sorted(bics)[0]
                    jurisdiction = primary_bic[4:6] if len(primary_bic) >= 6 else "XX"
                else:
                    jurisdiction = "XX"

            # Volumes
            incoming = sum(
                e.total_volume_30d for e in reverse_adjacency.get(corp_id, {}).values()
            )
            outgoing = sum(
                e.total_volume_30d for e in adjacency.get(corp_id, {}).values()
            )

            # Dependency scores (upstream → score)
            dep_scores = {
                src: e.dependency_score
                for src, e in reverse_adjacency.get(corp_id, {}).items()
            }

            nodes[corp_id] = CorporateNode(
                corporate_id=corp_id,
                name_hash=meta.get("name_hash", ""),
                bics=frozenset(corp_bics.get(corp_id, set())),
                sector=meta.get("sector", "UNKNOWN"),
                jurisdiction=jurisdiction,
                total_incoming_volume_30d=incoming,
                total_outgoing_volume_30d=outgoing,
                dependency_scores=dep_scores,
            )

        # Phase 5: Compute summary statistics
        avg_dep = 0.0
        if corporate_edges:
            avg_dep = sum(e.dependency_score for e in corporate_edges) / len(corporate_edges)

        cascade = CascadeGraph(
            nodes=nodes,
            edges=corporate_edges,
            adjacency=dict(adjacency),
            reverse_adjacency=dict(reverse_adjacency),
            build_timestamp=time.time(),
            node_count=len(nodes),
            edge_count=len(corporate_edges),
            avg_dependency_score=avg_dep,
        )

        logger.info(
            "resolve: %d BIC edges → %d corporate nodes, %d corporate edges (avg dep=%.3f)",
            len(bic_graph.edges), cascade.node_count, cascade.edge_count, avg_dep,
        )

        return cascade
```

- [ ] **Step 2: Run the entity resolution tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py::TestEntityResolver -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/entity_resolver.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add lip/p5_cascade_engine/entity_resolver.py
git commit -m "feat(p5): implement CorporateEntityResolver — BIC graph to corporate graph elevation"
```

---

## Task 5: Corporate Node Features

**Files:**
- Create: `lip/p5_cascade_engine/corporate_features.py`

- [ ] **Step 1: Write corporate_features.py**

```python
"""
corporate_features.py — 8-dimensional corporate node feature extraction.

Feature vector (CORPORATE_NODE_FEATURE_DIM = 8):
  [0] total_incoming_volume_30d  — log1p of incoming USD
  [1] total_outgoing_volume_30d  — log1p of outgoing USD
  [2] supplier_count             — distinct upstream corporates
  [3] customer_count             — distinct downstream corporates
  [4] max_dependency_score       — highest dependency on any sender
  [5] hhi_supplier_concentration — HHI of incoming payment volumes
  [6] failure_rate_30d           — volume-weighted avg failure rate
  [7] cascade_centrality         — betweenness centrality

Edge case guards:
  - Empty dependency_scores: max_dependency_score = 0.0
  - Zero incoming volume: hhi = 0.0, failure_rate = 0.0
  - Unknown node: returns np.zeros(8)
"""
from __future__ import annotations

import math

import numpy as np

from lip.p5_cascade_engine.constants import CORPORATE_NODE_FEATURE_DIM
from lip.p5_cascade_engine.corporate_graph import CascadeGraph


def get_corporate_node_features(
    graph: CascadeGraph, corporate_id: str
) -> np.ndarray:
    """Return 8-dimensional feature vector for a corporate node.

    Args:
        graph: The CascadeGraph containing the corporate node.
        corporate_id: The corporate entity ID to extract features for.

    Returns:
        np.ndarray of shape (CORPORATE_NODE_FEATURE_DIM,) with dtype float64.
        Returns zeros for unknown corporate IDs (isolated/missing nodes).
    """
    node = graph.nodes.get(corporate_id)
    if node is None:
        return np.zeros(CORPORATE_NODE_FEATURE_DIM, dtype=np.float64)

    # [0] log1p incoming volume
    f_incoming = math.log1p(node.total_incoming_volume_30d)

    # [1] log1p outgoing volume
    f_outgoing = math.log1p(node.total_outgoing_volume_30d)

    # [2] supplier count (upstream corporates)
    upstream = graph.reverse_adjacency.get(corporate_id, {})
    f_supplier_count = float(len(upstream))

    # [3] customer count (downstream corporates)
    downstream = graph.adjacency.get(corporate_id, {})
    f_customer_count = float(len(downstream))

    # [4] max dependency score
    f_max_dep = max(node.dependency_scores.values(), default=0.0)

    # [5] HHI of incoming payment volumes
    f_hhi = _compute_hhi(graph, corporate_id)

    # [6] volume-weighted failure rate
    f_failure_rate = _compute_failure_rate(graph, corporate_id)

    # [7] cascade centrality
    f_centrality = node.cascade_centrality

    return np.array(
        [f_incoming, f_outgoing, f_supplier_count, f_customer_count,
         f_max_dep, f_hhi, f_failure_rate, f_centrality],
        dtype=np.float64,
    )


def _compute_hhi(graph: CascadeGraph, corporate_id: str) -> float:
    """Herfindahl-Hirschman index of incoming payment volume concentration.

    HHI = sum(share_i^2) where share_i = volume_from_supplier_i / total_incoming.
    HHI = 1.0 → single supplier (max concentration).
    HHI → 0.0 → highly diversified.
    Returns 0.0 if no incoming volume.
    """
    upstream = graph.reverse_adjacency.get(corporate_id, {})
    if not upstream:
        return 0.0

    total = sum(e.total_volume_30d for e in upstream.values())
    if total <= 0:
        return 0.0

    return sum((e.total_volume_30d / total) ** 2 for e in upstream.values())


def _compute_failure_rate(graph: CascadeGraph, corporate_id: str) -> float:
    """Volume-weighted average failure rate across incoming edges.

    Returns 0.0 if no incoming volume.
    """
    upstream = graph.reverse_adjacency.get(corporate_id, {})
    if not upstream:
        return 0.0

    total = sum(e.total_volume_30d for e in upstream.values())
    if total <= 0:
        return 0.0

    return sum(
        e.total_volume_30d * e.failure_rate_30d for e in upstream.values()
    ) / total
```

- [ ] **Step 2: Run the feature tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py::TestCorporateNodeFeatures -v`
Expected: ALL PASS

- [ ] **Step 3: Run the query tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py::TestCascadeGraphQueries -v`
Expected: ALL PASS

- [ ] **Step 4: Run ALL tests in the file**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/corporate_features.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add lip/p5_cascade_engine/corporate_features.py
git commit -m "feat(p5): implement 8-dim corporate node feature extraction with edge case guards"
```

---

## Task 6: Centrality Tests + Verification

**Files:**
- Create: `lip/tests/test_p5_centrality.py`

- [ ] **Step 1: Write centrality test file**

Write `lip/tests/test_p5_centrality.py`:

```python
"""
test_p5_centrality.py — Tests for Brandes betweenness centrality on CascadeGraph.

Tests use known graph topologies with analytically computable centrality values:
  - Star graph: center has highest centrality
  - Chain graph: middle nodes have highest centrality
  - Diamond graph: junction nodes have highest centrality
  - Single node: centrality = 0
"""
from __future__ import annotations

import pytest

from lip.c1_failure_classifier.graph_builder import PaymentEdge, CorridorGraph
from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver
from lip.p5_cascade_engine.corporate_graph import CascadeGraph, CorporateNode, CorporateEdge


def _make_edge(uetr, s_bic, r_bic, amount=100_000.0):
    return PaymentEdge(
        uetr=uetr, sending_bic=s_bic, receiving_bic=r_bic,
        amount_usd=amount, currency_pair="USD_EUR",
        timestamp=1_700_000_000.0, dependency_score=0.5,
        features={},
    )


def _build_cascade_direct(edges_spec: list[tuple]) -> CascadeGraph:
    """Build a CascadeGraph directly from (source, target) corporate pairs.

    Bypasses entity resolver for topology-controlled tests.
    """
    from collections import defaultdict

    corp_edges = []
    adj: dict = defaultdict(dict)
    rev: dict = defaultdict(dict)
    all_corps: set = set()

    for src, tgt in edges_spec:
        ce = CorporateEdge(
            source_corporate_id=src,
            target_corporate_id=tgt,
            total_volume_30d=100_000.0,
            payment_count_30d=5,
            dependency_score=0.5,
        )
        corp_edges.append(ce)
        adj[src][tgt] = ce
        rev[tgt][src] = ce
        all_corps.add(src)
        all_corps.add(tgt)

    nodes = {
        c: CorporateNode(corporate_id=c) for c in all_corps
    }

    return CascadeGraph(
        nodes=nodes,
        edges=corp_edges,
        adjacency=dict(adj),
        reverse_adjacency=dict(rev),
        node_count=len(nodes),
        edge_count=len(corp_edges),
    )


class TestBrandesCentrality:

    def test_star_graph_center_highest(self):
        """Star: A→B, A→C, A→D. Center A has highest centrality (but 0 in
        directed star since no shortest paths pass THROUGH A — it's the source)."""
        graph = _build_cascade_direct([("A", "B"), ("A", "C"), ("A", "D")])
        graph.compute_centrality()

        # In a directed star from A, there are no shortest paths through any node
        # (B, C, D have no outgoing edges, so no paths pass through them)
        # All centrality = 0
        for node in graph.nodes.values():
            assert node.cascade_centrality == pytest.approx(0.0, abs=1e-6)

    def test_chain_graph_middle_highest(self):
        """Chain: A→B→C→D. B and C sit on shortest paths."""
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()

        # B sits on paths A→C, A→D (2 paths)
        # C sits on paths A→D, B→D (2 paths)
        # A and D sit on 0 paths (endpoints)
        assert graph.nodes["A"].cascade_centrality == pytest.approx(0.0, abs=1e-6)
        assert graph.nodes["D"].cascade_centrality == pytest.approx(0.0, abs=1e-6)
        assert graph.nodes["B"].cascade_centrality > 0
        assert graph.nodes["C"].cascade_centrality > 0

    def test_chain_b_and_c_equal(self):
        """In A→B→C→D, B and C have equal centrality (symmetric chain)."""
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()

        assert graph.nodes["B"].cascade_centrality == pytest.approx(
            graph.nodes["C"].cascade_centrality, abs=1e-6
        )

    def test_diamond_junction_highest(self):
        """Diamond: A→B, A→C, B→D, C→D. No intermediate junctions in this
        topology — B and C are parallel, neither is on the other's shortest path."""
        graph = _build_cascade_direct([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])
        graph.compute_centrality()

        # B is on A→D path (through B), C is on A→D path (through C)
        # But there are 2 shortest paths A→D, so each intermediate gets 0.5 credit
        assert graph.nodes["B"].cascade_centrality == pytest.approx(
            graph.nodes["C"].cascade_centrality, abs=1e-6
        )

    def test_single_node_zero_centrality(self):
        """Single node with no edges → centrality = 0."""
        nodes = {"SOLO": CorporateNode(corporate_id="SOLO")}
        graph = CascadeGraph(nodes=nodes, node_count=1)
        graph.compute_centrality()

        assert graph.nodes["SOLO"].cascade_centrality == 0.0

    def test_empty_graph(self):
        """Empty graph → no-op."""
        graph = CascadeGraph()
        graph.compute_centrality()  # Should not raise

    def test_max_cascade_centrality_node_set(self):
        """After compute_centrality, max_cascade_centrality_node is populated."""
        graph = _build_cascade_direct([("A", "B"), ("B", "C"), ("C", "D")])
        graph.compute_centrality()

        assert graph.max_cascade_centrality_node in ("B", "C")

    def test_centrality_normalized_0_to_1(self):
        """All centrality values should be in [0, 1] after normalization."""
        graph = _build_cascade_direct([
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"),
            ("A", "C"), ("B", "D"),
        ])
        graph.compute_centrality()

        for node in graph.nodes.values():
            assert 0.0 <= node.cascade_centrality <= 1.0
```

- [ ] **Step 2: Run centrality tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_centrality.py -v`
Expected: ALL PASS (Brandes implementation was written in Task 3)

- [ ] **Step 3: Commit**

```bash
git add lip/tests/test_p5_centrality.py
git commit -m "test(p5): add Brandes betweenness centrality tests — star, chain, diamond topologies"
```

---

## Task 7: Update __init__.py Exports + Regression

**Files:**
- Modify: `lip/p5_cascade_engine/__init__.py`

- [ ] **Step 1: Update exports**

Write `lip/p5_cascade_engine/__init__.py`:

```python
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
```

- [ ] **Step 2: Run all Sprint 3a tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_p5_corporate_graph.py lip/tests/test_p5_centrality.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run ruff on entire p5 module**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/p5_cascade_engine/`
Expected: no errors

- [ ] **Step 4: Run C1 regression tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_c1_classifier.py -v 2>&1 | tail -10`
Expected: ALL PASS (we didn't touch C1)

- [ ] **Step 5: Ruff check entire lip/**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/`
Expected: zero errors

- [ ] **Step 6: Commit**

```bash
git add lip/p5_cascade_engine/__init__.py
git commit -m "feat(p5): export CascadeGraph, CorporateEntityResolver, get_corporate_node_features"
```

- [ ] **Step 7: Push to GitHub**

Run: `git push origin main`
Expected: success

---

## Verification Checklist

Before declaring Sprint 3a complete:

1. [ ] `ruff check lip/` — zero errors
2. [ ] `python -m pytest lip/tests/test_p5_corporate_graph.py -v` — all entity resolution + feature tests pass
3. [ ] `python -m pytest lip/tests/test_p5_centrality.py -v` — all centrality tests pass
4. [ ] `python -m pytest lip/tests/test_c1_classifier.py -v` — no C1 regressions
5. [ ] Manual: CorporateEntityResolver.resolve() consumes CorridorGraph from BICGraphBuilder.build_graph()
6. [ ] Manual: Intra-corporate transfers (same corporate, different BICs) are filtered
7. [ ] Manual: Dependency score aggregation uses volume-weighted mean
8. [ ] Manual: Feature vector is shape (8,) with correct edge case guards
9. [ ] Manual: Brandes centrality normalized to [0, 1]
10. [ ] Pushed to GitHub

---

## QUANT / CIPHER Review Notes

**QUANT:** Dependency score aggregation uses `sum(w_i * d_i) / sum(w_i)` — exact float arithmetic, no rounding needed (this is graph analytics, not financial math). HHI is standard. Brandes algorithm is O(V*E), academically well-established.

**CIPHER:** `corporate_id` is an opaque bank-provided hash. No PII in the graph. `name_hash` is SHA-256 for deduplication, not for display. The `bic_to_corporate` mapping is provided by the enrolled bank — BPI does not perform entity resolution from payment patterns.

---

## Next Session: Sprint 3b (Cascade Propagation Engine)

Sprint 3b builds the core BFS cascade propagation algorithm on top of CascadeGraph:
- `CascadePropagationEngine.propagate()` — BFS with probability multiplication and threshold pruning
- `InterventionOptimizer` — greedy weighted set cover for intervention planning
- `CascadeAlert` generation for bank risk desks
