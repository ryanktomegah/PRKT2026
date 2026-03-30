"""
p10_regulatory_data — P10 Regulatory Data Product: Privacy-Preserving Analytics.

Sprint 4a: Anonymizer foundation (entity hashing, k-anonymity, differential privacy).
Sprint 4b: Systemic risk engine (trend detection, HHI concentration, BFS contagion).
"""
from .anonymizer import RegulatoryAnonymizer
from .concentration import ConcentrationResult, CorridorConcentrationAnalyzer
from .contagion import ContagionNode, ContagionResult, ContagionSimulator
from .privacy_budget import PrivacyBudgetTracker
from .systemic_risk import CorridorRiskSnapshot, SystemicRiskEngine, SystemicRiskReport
from .telemetry_schema import (
    AnonymizedCorridorResult,
    CorridorStatistic,
    PrivacyBudgetStatus,
    TelemetryBatch,
)

__all__ = [
    "AnonymizedCorridorResult",
    "ConcentrationResult",
    "ContagionNode",
    "ContagionResult",
    "ContagionSimulator",
    "CorridorConcentrationAnalyzer",
    "CorridorRiskSnapshot",
    "CorridorStatistic",
    "PrivacyBudgetStatus",
    "PrivacyBudgetTracker",
    "RegulatoryAnonymizer",
    "SystemicRiskEngine",
    "SystemicRiskReport",
    "TelemetryBatch",
]
