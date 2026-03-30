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


class TestCorridorFailureRate:
    """Corridor failure rate aggregation and trend detection."""

    def _make_result(self, corridor="EUR-USD", failure_rate=0.05, total_payments=500,
                     failed_payments=25, bank_count=5, stale=False, period_label="2029-08-01T14:00Z"):
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult
        return AnonymizedCorridorResult(
            corridor=corridor,
            period_label=period_label,
            total_payments=total_payments,
            failed_payments=failed_payments,
            failure_rate=failure_rate,
            bank_count=bank_count,
            k_anonymity_satisfied=True,
            privacy_budget_remaining=4.5,
            noise_applied=True,
            stale=stale,
        )

    def test_ingest_single_period(self):
        """Single ingestion produces one snapshot per corridor."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([self._make_result()])
        trend = engine.get_corridor_trend("EUR-USD")
        assert len(trend) == 1
        assert trend[0].corridor == "EUR-USD"
        assert trend[0].failure_rate == pytest.approx(0.05)

    def test_ingest_multiple_periods_builds_history(self):
        """Multiple ingestions build time-series history."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        for i in range(5):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{10+i:02d}:00Z",
                                  failure_rate=0.05 + i * 0.01)
            ])
        trend = engine.get_corridor_trend("EUR-USD")
        assert len(trend) == 5

    def test_rising_trend_detection(self):
        """Failure rate rising >10% -> RISING."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        # 3 periods at 0.05, then 3 periods at 0.07 (40% increase)
        for i in range(3):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{10+i:02d}:00Z", failure_rate=0.05)
            ])
        for i in range(3):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{13+i:02d}:00Z", failure_rate=0.07)
            ])
        trend = engine.get_corridor_trend("EUR-USD")
        direction, magnitude = engine.compute_trend_direction(trend)
        assert direction == "RISING"
        assert magnitude > 0.10

    def test_falling_trend_detection(self):
        """Failure rate falling >10% -> FALLING."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        for i in range(3):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{10+i:02d}:00Z", failure_rate=0.10)
            ])
        for i in range(3):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{13+i:02d}:00Z", failure_rate=0.07)
            ])
        trend = engine.get_corridor_trend("EUR-USD")
        direction, magnitude = engine.compute_trend_direction(trend)
        assert direction == "FALLING"
        assert magnitude < -0.10

    def test_stable_trend_detection(self):
        """Failure rate within +/-10% -> STABLE."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        for i in range(6):
            engine.ingest_results([
                self._make_result(period_label=f"2029-08-01T{10+i:02d}:00Z", failure_rate=0.05)
            ])
        trend = engine.get_corridor_trend("EUR-USD")
        direction, magnitude = engine.compute_trend_direction(trend)
        assert direction == "STABLE"

    def test_stale_data_flagged(self):
        """Stale result -> snapshot.contains_stale_data=True."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([self._make_result(stale=True)])
        trend = engine.get_corridor_trend("EUR-USD")
        assert trend[0].contains_stale_data is True

    def test_empty_history_empty_report(self):
        """No ingested data -> empty report."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        report = engine.compute_risk_report()
        assert report.total_corridors_analyzed == 0
        assert len(report.corridor_snapshots) == 0


class TestSystemicRiskIntegration:
    """Full pipeline integration."""

    def _make_result(self, corridor="EUR-USD", failure_rate=0.05, total_payments=500,
                     failed_payments=25, bank_count=5, stale=False, period_label="2029-08-01T14:00Z"):
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult
        return AnonymizedCorridorResult(
            corridor=corridor,
            period_label=period_label,
            total_payments=total_payments,
            failed_payments=failed_payments,
            failure_rate=failure_rate,
            bank_count=bank_count,
            k_anonymity_satisfied=True,
            privacy_budget_remaining=4.5,
            noise_applied=True,
            stale=stale,
        )

    def test_full_pipeline_ingest_report(self):
        """Ingest results -> compute risk report."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([
            self._make_result(corridor="EUR-USD", failure_rate=0.05, total_payments=500),
            self._make_result(corridor="GBP-EUR", failure_rate=0.08, total_payments=300),
        ])
        report = engine.compute_risk_report()
        assert report.total_corridors_analyzed == 2
        assert len(report.corridor_snapshots) == 2
        assert report.overall_failure_rate > 0.0
        assert report.highest_risk_corridor in ("EUR-USD", "GBP-EUR")

    def test_thread_safety_concurrent_access(self):
        """Concurrent ingest + compute doesn't crash."""
        import threading

        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        errors = []

        def ingest_worker():
            try:
                for i in range(50):
                    engine.ingest_results([
                        self._make_result(period_label=f"2029-08-01T{i%24:02d}:00Z")
                    ])
            except Exception as e:
                errors.append(e)

        def compute_worker():
            try:
                for _ in range(50):
                    engine.compute_risk_report()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=ingest_worker),
            threading.Thread(target=compute_worker),
            threading.Thread(target=ingest_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_systemic_risk_score_bounded(self):
        """Score always in [0.0, 1.0]."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([
            self._make_result(corridor="EUR-USD", failure_rate=0.95, total_payments=10000),
        ])
        report = engine.compute_risk_report()
        assert 0.0 <= report.systemic_risk_score <= 1.0

    def test_risk_report_includes_concentration(self):
        """Report has valid concentration_hhi field."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([
            self._make_result(corridor="EUR-USD", total_payments=900),
            self._make_result(corridor="GBP-EUR", total_payments=50),
            self._make_result(corridor="USD-JPY", total_payments=50),
        ])
        report = engine.compute_risk_report()
        assert report.concentration_hhi >= 0.0
        assert report.concentration_hhi <= 1.0

    def test_clear_history_resets(self):
        """clear_history() empties all accumulated data."""
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        engine = SystemicRiskEngine()
        engine.ingest_results([self._make_result()])
        engine.clear_history()
        report = engine.compute_risk_report()
        assert report.total_corridors_analyzed == 0
