"""
p10_regulatory_data — P10 Regulatory Data Product: Privacy-Preserving Analytics.

Sprint 4a: Anonymizer foundation (entity hashing, k-anonymity, differential privacy).
"""
from .anonymizer import RegulatoryAnonymizer
from .privacy_budget import PrivacyBudgetTracker
from .telemetry_schema import (
    AnonymizedCorridorResult,
    CorridorStatistic,
    PrivacyBudgetStatus,
    TelemetryBatch,
)

__all__ = [
    "AnonymizedCorridorResult",
    "CorridorStatistic",
    "PrivacyBudgetStatus",
    "PrivacyBudgetTracker",
    "RegulatoryAnonymizer",
    "TelemetryBatch",
]
