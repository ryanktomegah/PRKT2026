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
from .methodology_paper import MethodologyPaper, generate_methodology_paper
from .privacy_audit import (
    AttackResult,
    BudgetAuditResult,
    DPVerificationResult,
    KAnonymityProof,
    PrivacyAuditReport,
    frequency_attack,
    generate_audit_report,
    k_anonymity_proof,
    temporal_linkage_attack,
    uniqueness_attack,
    verify_budget_composition,
    verify_dp_distribution,
)
from .privacy_budget import PrivacyBudgetTracker
from .regulator_onboarding import (
    ChecklistItem,
    ComplianceMapping,
    OnboardingChecklist,
    generate_compliance_mapping,
    generate_onboarding_checklist,
    generate_sample_data_package,
)
from .report_metadata import (
    ReportIntegrityError,
    VersionedReport,
    create_versioned_report,
    verify_report_integrity,
)
from .report_renderer import ReportRenderer
from .shadow_runner import ShadowPipelineRunner, ShadowRunResult
from .systemic_risk import CorridorRiskSnapshot, SystemicRiskEngine, SystemicRiskReport
from .telemetry_collector import TelemetryCollector
from .telemetry_schema import (
    AnonymizedCorridorResult,
    CorridorStatistic,
    PrivacyBudgetStatus,
    TelemetryBatch,
)

__all__ = [
    "AnonymizedCorridorResult",
    "AttackResult",
    "BudgetAuditResult",
    "ChecklistItem",
    "CircularExposure",
    "ComplianceMapping",
    "ConcentrationResult",
    "ContagionNode",
    "ContagionResult",
    "ContagionSimulator",
    "CorridorConcentrationAnalyzer",
    "CorridorRiskSnapshot",
    "CorridorStatistic",
    "DPVerificationResult",
    "KAnonymityProof",
    "MethodologyAppendix",
    "MethodologyPaper",
    "OnboardingChecklist",
    "PrivacyAuditReport",
    "PrivacyBudgetStatus",
    "PrivacyBudgetTracker",
    "RegulatoryAnonymizer",
    "ReportIntegrityError",
    "ReportRenderer",
    "ShadowPipelineRunner",
    "ShadowRunResult",
    "SystemicRiskEngine",
    "SystemicRiskReport",
    "TelemetryBatch",
    "TelemetryCollector",
    "VersionedReport",
    "create_versioned_report",
    "detect_circular_exposures",
    "frequency_attack",
    "generate_audit_report",
    "generate_compliance_mapping",
    "generate_methodology_paper",
    "generate_onboarding_checklist",
    "generate_sample_data_package",
    "k_anonymity_proof",
    "temporal_linkage_attack",
    "uniqueness_attack",
    "verify_budget_composition",
    "verify_dp_distribution",
    "verify_report_integrity",
]
