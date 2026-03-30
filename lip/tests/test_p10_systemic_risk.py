"""
test_p10_systemic_risk.py — TDD tests for P10 Systemic Risk Engine.

QUANT domain: HHI concentration, contagion propagation, trend detection.
"""
from __future__ import annotations

import pytest


class TestConcentration:
    """QUANT domain — HHI concentration metrics."""

    def test_single_corridor_max_concentration(self):
        """One corridor = HHI 1.0 (maximum)."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        result = analyzer.compute_corridor_concentration({"EUR-USD": 1000})
        assert result.hhi == pytest.approx(1.0)
        assert result.is_concentrated is True
        assert result.effective_count == pytest.approx(1.0)

    def test_four_equal_corridors_boundary(self):
        """4 equal corridors = HHI 0.25 (threshold boundary)."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        volumes = {"EUR-USD": 250, "GBP-EUR": 250, "USD-JPY": 250, "AUD-NZD": 250}
        result = analyzer.compute_corridor_concentration(volumes)
        assert result.hhi == pytest.approx(0.25)
        assert result.is_concentrated is True  # >= threshold

    def test_dispersed_corridors_not_concentrated(self):
        """10 equal corridors = HHI 0.10 (well below threshold)."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        volumes = {f"COR-{i}": 100 for i in range(10)}
        result = analyzer.compute_corridor_concentration(volumes)
        assert result.hhi == pytest.approx(0.10)
        assert result.is_concentrated is False

    def test_highly_concentrated(self):
        """One dominant corridor = concentrated."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        volumes = {"EUR-USD": 900, "GBP-EUR": 50, "USD-JPY": 50}
        result = analyzer.compute_corridor_concentration(volumes)
        assert result.hhi > 0.25
        assert result.is_concentrated is True

    def test_jurisdiction_extraction(self):
        """EUR-USD -> half volume to EUR, half to USD."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        volumes = {"EUR-USD": 1000, "GBP-EUR": 1000}
        result = analyzer.compute_jurisdiction_concentration(volumes)
        # EUR gets 500+500=1000, USD gets 500, GBP gets 500 -> total 2000
        # shares: EUR=0.5, USD=0.25, GBP=0.25
        # HHI = 0.25 + 0.0625 + 0.0625 = 0.375
        assert result.hhi == pytest.approx(0.375)
        assert result.dimension == "jurisdiction"

    def test_top_entities_ranked(self):
        """Top entities sorted by share descending, limited to 5."""
        from lip.p10_regulatory_data.concentration import CorridorConcentrationAnalyzer
        analyzer = CorridorConcentrationAnalyzer()
        volumes = {f"COR-{i}": (10 - i) * 100 for i in range(8)}
        result = analyzer.compute_corridor_concentration(volumes)
        assert len(result.top_entities) == 5
        assert result.top_entities[0][1] >= result.top_entities[1][1]


class TestContagion:
    """QUANT domain — BFS contagion propagation."""

    def test_build_dependency_graph_jaccard(self):
        """Jaccard similarity: {A,B,C} ∩ {B,C,D} / {A,B,C} ∪ {B,C,D} = 2/4 = 0.5."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator()
        bank_sets = {
            "EUR-USD": {"A", "B", "C"},
            "GBP-EUR": {"B", "C", "D"},
        }
        graph = sim.build_dependency_graph(bank_sets)
        assert graph["EUR-USD"]["GBP-EUR"] == pytest.approx(0.5)
        assert graph["GBP-EUR"]["EUR-USD"] == pytest.approx(0.5)

    def test_single_hop_propagation(self):
        """Stress propagates: shock * edge_weight * decay."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator(propagation_decay=0.7)
        graph = {"A": {"B": 0.8}, "B": {"A": 0.8}}
        result = sim.simulate(graph, "A", shock_magnitude=1.0)
        b_node = next(n for n in result.affected_corridors if n.corridor == "B")
        assert b_node.stress_level == pytest.approx(0.56)
        assert b_node.hop_distance == 1

    def test_multi_hop_respects_max_hops(self):
        """Chain A->B->C->D->E->F: max_hops=3 stops at D."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator(propagation_decay=1.0, max_hops=3, stress_threshold=0.0)
        graph = {
            "A": {"B": 1.0}, "B": {"A": 1.0, "C": 1.0},
            "C": {"B": 1.0, "D": 1.0}, "D": {"C": 1.0, "E": 1.0},
            "E": {"D": 1.0, "F": 1.0}, "F": {"E": 1.0},
        }
        result = sim.simulate(graph, "A", shock_magnitude=1.0)
        affected = {n.corridor for n in result.affected_corridors}
        assert "B" in affected and "C" in affected and "D" in affected
        assert "E" not in affected and "F" not in affected
        assert result.max_propagation_depth == 3

    def test_threshold_pruning(self):
        """Weak propagation pruned below threshold."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator(propagation_decay=0.1, stress_threshold=0.05)
        graph = {"A": {"B": 0.5, "C": 0.5}, "B": {}, "C": {}}
        result = sim.simulate(graph, "A", shock_magnitude=1.0)
        # B stress = 1.0 * 0.5 * 0.1 = 0.05 -> at threshold, included
        assert len(result.affected_corridors) == 2

    def test_disconnected_corridors_unaffected(self):
        """Isolated corridor not in results."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator()
        graph = {"A": {"B": 0.8}, "B": {"A": 0.8}, "C": {}}
        result = sim.simulate(graph, "A", shock_magnitude=1.0)
        affected = {n.corridor for n in result.affected_corridors}
        assert "C" not in affected

    def test_circular_graph_no_infinite_loop(self):
        """Visited set prevents re-processing."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator(propagation_decay=0.9, stress_threshold=0.01)
        graph = {"A": {"B": 1.0}, "B": {"C": 1.0}, "C": {"A": 1.0}}
        result = sim.simulate(graph, "A", shock_magnitude=1.0)
        assert result.max_propagation_depth <= 3

    def test_zero_shock_no_propagation(self):
        """Zero shock magnitude -> empty result."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator()
        graph = {"A": {"B": 1.0}, "B": {"A": 1.0}}
        result = sim.simulate(graph, "A", shock_magnitude=0.0)
        assert len(result.affected_corridors) == 0

    def test_full_scenario_five_corridors(self):
        """5-corridor known topology produces valid systemic risk score."""
        from lip.p10_regulatory_data.contagion import ContagionSimulator
        sim = ContagionSimulator(propagation_decay=0.7, stress_threshold=0.05)
        bank_sets = {
            "EUR-USD": {"B1", "B2", "B3", "B4", "B5"},
            "GBP-EUR": {"B1", "B2", "B3", "B6", "B7"},
            "USD-JPY": {"B3", "B4", "B8", "B9", "B10"},
            "AUD-NZD": {"B11", "B12", "B13", "B14", "B15"},
            "ZAR-BRL": {"B1", "B16", "B17", "B18", "B19"},
        }
        graph = sim.build_dependency_graph(bank_sets)
        volumes = {"EUR-USD": 5000, "GBP-EUR": 3000, "USD-JPY": 2000,
                    "AUD-NZD": 1000, "ZAR-BRL": 500}
        result = sim.simulate(graph, "EUR-USD", shock_magnitude=0.8,
                              corridor_volumes=volumes)
        assert result.origin_corridor == "EUR-USD"
        assert 0.0 <= result.systemic_risk_score <= 1.0
        assert len(result.affected_corridors) >= 1
