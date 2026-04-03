"""
p10_regulatory_data — P10 Regulatory Data Product: Privacy-Preserving Analytics.

Sprint 4a: Anonymizer foundation (entity hashing, k-anonymity, differential privacy).
Sprint 4b: Systemic risk engine (trend detection, HHI concentration, BFS contagion).
Sprint 5: Report generator (versioning, JSON/CSV/PDF rendering, methodology appendix).
"""
from .anonymizer import RegulatoryAnonymizer
from .circular_exposure import CircularExposure, detect_circular_exposures
from .concentration import ConcentrationResult, CorridorConcentrationAnalyzer
from .contagion import ContagionNode, ContagionResult, ContagionSimulator
from .methodology import MethodologyAppendix
from .privacy_budget import PrivacyBudgetTracker
from .report_metadata import (
    ReportIntegrityError,
    VersionedReport,
    create_versioned_report,
    verify_report_integrity,
)
from .report_renderer import ReportRenderer
from .systemic_risk import CorridorRiskSnapshot, SystemicRiskEngine, SystemicRiskReport
from .telemetry_schema import (
    AnonymizedCorridorResult,
    CorridorStatistic,
    PrivacyBudgetStatus,
    TelemetryBatch,
)

__all__ = [
    "AnonymizedCorridorResult",
    "CircularExposure",
    "ConcentrationResult",
    "ContagionNode",
    "ContagionResult",
    "ContagionSimulator",
    "CorridorConcentrationAnalyzer",
    "CorridorRiskSnapshot",
    "CorridorStatistic",
    "MethodologyAppendix",
    "PrivacyBudgetStatus",
    "PrivacyBudgetTracker",
    "RegulatoryAnonymizer",
    "ReportIntegrityError",
    "ReportRenderer",
    "SystemicRiskEngine",
    "SystemicRiskReport",
    "TelemetryBatch",
    "VersionedReport",
    "create_versioned_report",
    "detect_circular_exposures",
    "verify_report_integrity",
]
