"""
test_p5_corporate_graph.py — TDD tests for P5 corporate graph data structures,
entity resolution, and corporate node features.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pytest

from lip.c1_failure_classifier.graph_builder import CorridorGraph, PaymentEdge
from lip.p5_cascade_engine.constants import (
    CORPORATE_EDGE_MIN_PAYMENTS_30D,  # noqa: F401 — import validates constant exists
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


_BIC_TO_CORP = {
    "COBADEFF": "BMW_CORP",
    "BNPAFRPP": "BMW_CORP",
    "DEUTDEFF": "BOSCH_CORP",
    "HSBCGB2L": "SIEMENS_CORP",
    "BARCGB22": "SIEMENS_CORP",
}


class TestEntityResolver:

    def test_basic_two_corporate_resolution(self):
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
        edge = cascade.adjacency["BMW_CORP"]["BOSCH_CORP"]
        assert edge.total_volume_30d == 300_000.0
        assert edge.payment_count_30d == 2

    def test_multi_bic_same_corporate(self):
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
        bmw = cascade.nodes["BMW_CORP"]
        assert "COBADEFF" in bmw.bics
        assert "BNPAFRPP" in bmw.bics

    def test_intra_corporate_transfer_filtered(self):
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
        assert cascade.node_count == 0

    def test_unmapped_bic_excluded(self):
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
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF",
                       amount_usd=100_000, dependency_score=0.3),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)
        assert cascade.edge_count == 0

    def test_zero_volume_edge_excluded(self):
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
        assert abs(edge.dependency_score - 0.5) < 1e-9

    def test_failure_rate_computation(self):
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
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        bic_graph = CorridorGraph(nodes=[], edges=[], adjacency={})
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)
        assert cascade.node_count == 0
        assert cascade.edge_count == 0

    def test_reverse_adjacency_built(self):
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
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="DEUTDEFF", amount_usd=100_000),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="DEUTDEFF", amount_usd=100_000),
        ]
        metadata = {
            "BMW_CORP": {"name_hash": "abc123", "sector": "Automobiles", "jurisdiction": "DE"},
            "BOSCH_CORP": {"name_hash": "def456", "sector": "Auto Components", "jurisdiction": "DE"},
        }
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP, corporate_metadata=metadata)
        cascade = resolver.resolve(bic_graph)
        assert cascade.nodes["BMW_CORP"].sector == "Automobiles"
        assert cascade.nodes["BOSCH_CORP"].sector == "Auto Components"

    def test_jurisdiction_from_bic_when_no_metadata(self):
        from lip.p5_cascade_engine.entity_resolver import CorporateEntityResolver

        edges = [
            _make_edge(uetr="u1", sending_bic="COBADEFF", receiving_bic="HSBCGB2L", amount_usd=100_000),
            _make_edge(uetr="u2", sending_bic="COBADEFF", receiving_bic="HSBCGB2L", amount_usd=100_000),
        ]
        bic_graph = _make_bic_graph(edges)
        resolver = CorporateEntityResolver(bic_to_corporate=_BIC_TO_CORP)
        cascade = resolver.resolve(bic_graph)
        assert cascade.nodes["BMW_CORP"].jurisdiction == "DE"
        assert cascade.nodes["SIEMENS_CORP"].jurisdiction == "GB"


class TestCorporateNodeFeatures:

    def _build_three_corp_graph(self):
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
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BMW_CORP")
        assert feats[0] == pytest.approx(0.0, abs=1e-6)
        assert feats[1] == pytest.approx(np.log1p(300_000), abs=1e-6)
        assert feats[2] == 0.0
        assert feats[3] == 2.0
        assert feats[4] == 0.0

    def test_feature_values_bosch(self):
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BOSCH_CORP")
        assert feats[2] == 2.0
        assert feats[3] == 0.0
        assert feats[4] == pytest.approx(0.6, abs=1e-6)

    def test_hhi_single_supplier(self):
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
        assert feats[5] == pytest.approx(1.0, abs=1e-6)

    def test_hhi_equal_two_suppliers(self):
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "BOSCH_CORP")
        assert feats[5] == pytest.approx(0.5102, abs=0.001)

    def test_isolated_node_returns_zeros(self):
        from lip.p5_cascade_engine.corporate_features import get_corporate_node_features

        cascade = self._build_three_corp_graph()
        feats = get_corporate_node_features(cascade, "NONEXISTENT_CORP")
        assert feats.shape == (CORPORATE_NODE_FEATURE_DIM,)
        assert np.all(feats == 0.0)


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
        assert "SIEMENS_CORP" not in deps

    def test_get_downstream_dependents_low_threshold(self):
        cascade = self._build_graph()
        deps = cascade.get_downstream_dependents("BMW_CORP", threshold=0.05)
        assert len(deps) == 2
