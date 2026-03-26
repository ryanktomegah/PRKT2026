"""
model_card_generator.py — Automated model card and regulatory report generation.

Generates:
  1. Model Cards — populated from model metadata + training results
  2. DORA Art.19 incident reports — formatted for regulator submission
  3. SR 11-7 validation reports — ongoing model risk management
  4. EU AI Act Art.61 post-market monitoring reports

REX authority: all templates and content must be reviewed by REX before
submission to any regulatory body.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model Card (EU AI Act Art.13, SR 11-7 Section IV)
# ---------------------------------------------------------------------------

@dataclass
class ModelCard:
    """Standardised model card for LIP ML components.

    Based on Mitchell et al., "Model Cards for Model Reporting," FAT* 2019,
    adapted for EU AI Act Art.13 and Fed SR 11-7 requirements.
    """
    # Identification
    model_id: str
    model_name: str
    component: str  # C1, C2, C4, C9
    version: str
    created_at: str

    # Intended use
    intended_use: str
    intended_users: str
    out_of_scope_uses: str

    # Training data
    training_data_description: str
    training_data_size: int
    training_data_date_range: str
    training_data_is_synthetic: bool
    training_data_caveats: str

    # Evaluation
    evaluation_metrics: Dict[str, float]  # e.g. {"auc": 0.887, "f2": 0.625}
    evaluation_data_description: str
    evaluation_data_size: int

    # Ethical considerations
    ethical_considerations: str
    fairness_analysis: str

    # Limitations
    known_limitations: str
    performance_caveats: str

    # Quantitative analysis
    feature_count: int = 0
    ensemble_size: int = 0
    calibration_method: str = ""
    calibration_error: float = 0.0

    # Conformal prediction (if applicable)
    conformal_coverage_level: Optional[float] = None
    conformal_calibration_size: Optional[int] = None

    # Drift monitoring
    drift_features_monitored: int = 0
    drift_detector_type: str = ""

    # Regulatory references
    regulatory_references: List[str] = field(default_factory=list)


def generate_model_card(
    component: str,
    model_metadata: Dict[str, Any],
    training_results: Dict[str, Any],
    evaluation_results: Dict[str, Any],
) -> ModelCard:
    """Generate a model card from training and evaluation metadata.

    Parameters
    ----------
    component:
        Component identifier (e.g. "C1", "C2").
    model_metadata:
        Dict with keys: model_id, model_name, version, created_at,
        feature_count, ensemble_size, etc.
    training_results:
        Dict with keys: data_size, date_range, is_synthetic,
        calibration_method, calibration_error, etc.
    evaluation_results:
        Dict with keys: metrics (dict of metric_name → value),
        eval_data_size, eval_data_description, etc.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Component-specific defaults
    intended_use_map = {
        "C1": "Predict probability of cross-border payment failure from ISO 20022 pacs.002 events.",
        "C2": "Estimate probability of default on bridge loan principal for BIC-level counterparties.",
        "C4": "Classify payment rejection narratives as disputes vs. non-disputes.",
        "C9": "Predict settlement time for rejected payments using survival analysis.",
    }

    return ModelCard(
        model_id=model_metadata.get("model_id", f"lip-{component.lower()}-v1"),
        model_name=model_metadata.get("model_name", f"LIP {component} Model"),
        component=component,
        version=model_metadata.get("version", "1.0.0"),
        created_at=model_metadata.get("created_at", now),
        intended_use=intended_use_map.get(component, "See component documentation."),
        intended_users="Bank risk teams, capital partners, regulatory examiners.",
        out_of_scope_uses=(
            "Not validated for retail lending, consumer credit scoring, or "
            "any use outside the cross-border bridge loan context."
        ),
        training_data_description=training_results.get(
            "data_description", "Synthetic ISO 20022 payment events."
        ),
        training_data_size=training_results.get("data_size", 0),
        training_data_date_range=training_results.get("date_range", "N/A"),
        training_data_is_synthetic=training_results.get("is_synthetic", True),
        training_data_caveats=training_results.get(
            "caveats",
            "Model trained entirely on synthetic data. AUC reflects ability to learn "
            "generated patterns, not real-world generalization. Retraining on pilot "
            "bank data is required before production deployment (Phase 3).",
        ),
        evaluation_metrics=evaluation_results.get("metrics", {}),
        evaluation_data_description=evaluation_results.get(
            "eval_data_description", "Temporal hold-out from synthetic corpus."
        ),
        evaluation_data_size=evaluation_results.get("eval_data_size", 0),
        ethical_considerations=(
            "Model operates at institution (BIC) level, not individual level. "
            "No personal data processed. Borrower identity hashed with SHA-256."
        ),
        fairness_analysis=(
            "Corridor-level AUC monitored for performance disparities. "
            "ADWIN drift detection on top features ensures ongoing monitoring."
        ),
        known_limitations=(
            "1. Trained on synthetic data only — will require retraining on real data. "
            "2. GraphSAGE embeddings may not generalize to unseen BIC topologies. "
            "3. Calibration (ECE) validated only on synthetic temporal hold-out."
        ),
        performance_caveats=training_results.get("performance_caveats", ""),
        feature_count=model_metadata.get("feature_count", 0),
        ensemble_size=model_metadata.get("ensemble_size", 5),
        calibration_method=training_results.get("calibration_method", "isotonic"),
        calibration_error=training_results.get("calibration_error", 0.0),
        conformal_coverage_level=model_metadata.get("conformal_coverage_level"),
        conformal_calibration_size=model_metadata.get("conformal_calibration_size"),
        drift_features_monitored=model_metadata.get("drift_features_monitored", 0),
        drift_detector_type=model_metadata.get("drift_detector_type", "ADWIN"),
        regulatory_references=[
            "EU AI Act Art.13 — Transparency requirements",
            "EU AI Act Art.17 — Quality management system",
            "Fed SR 11-7 — Model Risk Management",
            "DORA Art.30 — ICT risk management",
        ],
    )


def export_model_card_json(card: ModelCard) -> str:
    """Serialize a ModelCard to JSON."""
    return json.dumps(asdict(card), indent=2, default=str)


def export_model_card_markdown(card: ModelCard) -> str:
    """Render a ModelCard as Markdown (for human review)."""
    lines = [
        f"# Model Card: {card.model_name}",
        "",
        f"**Model ID:** {card.model_id}  ",
        f"**Component:** {card.component}  ",
        f"**Version:** {card.version}  ",
        f"**Created:** {card.created_at}  ",
        "",
        "## Intended Use",
        card.intended_use,
        "",
        f"**Intended Users:** {card.intended_users}  ",
        f"**Out of Scope:** {card.out_of_scope_uses}",
        "",
        "## Training Data",
        card.training_data_description,
        f"- **Size:** {card.training_data_size:,} samples",
        f"- **Date Range:** {card.training_data_date_range}",
        f"- **Synthetic:** {'Yes' if card.training_data_is_synthetic else 'No'}",
        "",
        f"**Caveats:** {card.training_data_caveats}",
        "",
        "## Evaluation Metrics",
    ]
    for metric, value in card.evaluation_metrics.items():
        lines.append(f"- **{metric}:** {value}")
    lines.extend([
        "",
        f"**Evaluation Data:** {card.evaluation_data_description}",
        f"**Evaluation Size:** {card.evaluation_data_size:,} samples",
        "",
        "## Model Architecture",
        f"- **Features:** {card.feature_count}",
        f"- **Ensemble Size:** {card.ensemble_size}",
        f"- **Calibration:** {card.calibration_method} (ECE={card.calibration_error:.4f})",
    ])
    if card.conformal_coverage_level is not None:
        lines.append(
            f"- **Conformal Coverage:** {card.conformal_coverage_level:.0%} "
            f"(calibration set: {card.conformal_calibration_size or 'N/A'})"
        )
    if card.drift_features_monitored > 0:
        lines.append(
            f"- **Drift Monitoring:** {card.drift_detector_type} on "
            f"{card.drift_features_monitored} features"
        )
    lines.extend([
        "",
        "## Ethical Considerations",
        card.ethical_considerations,
        "",
        "## Known Limitations",
        card.known_limitations,
        "",
        "## Regulatory References",
    ])
    for ref in card.regulatory_references:
        lines.append(f"- {ref}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DORA Art.19 Incident Report
# ---------------------------------------------------------------------------

@dataclass
class DORAIncidentReport:
    """DORA Art.19 ICT-related incident report for regulatory submission.

    Must be submitted to the competent authority within the time thresholds
    defined in DORA Art.19(4).
    """
    incident_id: str
    classification: str  # MAJOR | SIGNIFICANT | MINOR
    incident_type: str
    description: str
    affected_components: List[str]
    detection_timestamp: str
    resolution_timestamp: Optional[str]
    root_cause: str
    remediation_steps: List[str]
    impact_assessment: str
    data_breach: bool
    cross_border_impact: bool
    reporting_entity: str = "BPI Technology Ltd"
    regulatory_framework: str = "DORA Art.19"


def generate_dora_incident_report(
    incident_id: str,
    incident_type: str,
    description: str,
    affected_components: List[str],
    detection_time: datetime,
    root_cause: str,
    remediation_steps: List[str],
    classification: str = "SIGNIFICANT",
    resolution_time: Optional[datetime] = None,
) -> DORAIncidentReport:
    """Generate a DORA Art.19 incident report."""
    return DORAIncidentReport(
        incident_id=incident_id,
        classification=classification,
        incident_type=incident_type,
        description=description,
        affected_components=affected_components,
        detection_timestamp=detection_time.isoformat(),
        resolution_timestamp=resolution_time.isoformat() if resolution_time else None,
        root_cause=root_cause,
        remediation_steps=remediation_steps,
        impact_assessment=(
            f"Affected {len(affected_components)} component(s). "
            f"Classification: {classification}."
        ),
        data_breach=False,
        cross_border_impact=True,  # LIP is inherently cross-border
    )


def export_dora_report_json(report: DORAIncidentReport) -> str:
    """Serialize a DORA incident report to JSON."""
    return json.dumps(asdict(report), indent=2, default=str)


# ---------------------------------------------------------------------------
# SR 11-7 Validation Report
# ---------------------------------------------------------------------------

@dataclass
class SR117ValidationReport:
    """SR 11-7 model validation report for Fed/OCC examination.

    Covers: model description, data quality, performance metrics,
    limitations, ongoing monitoring, and governance.
    """
    report_id: str
    model_id: str
    component: str
    validation_date: str
    validator: str

    # Model performance
    auc_score: float
    f2_score: float
    calibration_error: float
    out_of_time_auc: Optional[float]

    # Data quality
    training_data_quality: str
    feature_count: int
    missing_data_treatment: str

    # Monitoring
    drift_detection_method: str
    drift_features_count: int
    monitoring_frequency: str

    # Conformal prediction
    conformal_coverage_target: Optional[float]
    conformal_coverage_actual: Optional[float]

    # Governance
    model_owner: str
    review_frequency: str
    passes_validation: bool
    validation_notes: str

    # Regulatory
    regulatory_framework: str = "Fed SR 11-7 / OCC 2011-12"


def generate_sr117_report(
    model_id: str,
    component: str,
    metrics: Dict[str, float],
    drift_config: Dict[str, Any],
    conformal_config: Optional[Dict[str, float]] = None,
) -> SR117ValidationReport:
    """Generate an SR 11-7 validation report from model metrics."""
    now = datetime.now(timezone.utc)

    auc = metrics.get("auc", 0.0)
    passes = auc >= 0.75  # minimum acceptable AUC threshold

    return SR117ValidationReport(
        report_id=f"SR117-{component}-{now.strftime('%Y%m%d')}",
        model_id=model_id,
        component=component,
        validation_date=now.isoformat(),
        validator="LIP Automated Validation System",
        auc_score=auc,
        f2_score=metrics.get("f2", 0.0),
        calibration_error=metrics.get("ece", 0.0),
        out_of_time_auc=metrics.get("oot_auc"),
        training_data_quality=(
            "Synthetic data generated from BIS/SWIFT GPI calibrated distributions. "
            "See model card for detailed caveats."
        ),
        feature_count=int(metrics.get("feature_count", 0)),
        missing_data_treatment="Features with missing values imputed to corridor-level medians.",
        drift_detection_method=drift_config.get("method", "ADWIN"),
        drift_features_count=drift_config.get("features_count", 0),
        monitoring_frequency=drift_config.get("frequency", "Per-inference"),
        conformal_coverage_target=(
            conformal_config.get("target") if conformal_config else None
        ),
        conformal_coverage_actual=(
            conformal_config.get("actual") if conformal_config else None
        ),
        model_owner="BPI Engineering / ARIA",
        review_frequency="Quarterly or upon material model change",
        passes_validation=passes,
        validation_notes=(
            f"AUC={auc:.4f} {'meets' if passes else 'FAILS'} minimum threshold (0.75). "
            f"Model trained on synthetic data — revalidation required after real data retraining."
        ),
    )


def export_sr117_report_json(report: SR117ValidationReport) -> str:
    """Serialize an SR 11-7 report to JSON."""
    return json.dumps(asdict(report), indent=2, default=str)


# ---------------------------------------------------------------------------
# EU AI Act Art.61 Post-Market Monitoring Report
# ---------------------------------------------------------------------------

@dataclass
class EUAIActMonitoringReport:
    """EU AI Act Art.61 post-market monitoring report.

    Required for high-risk AI systems operating in financial services.
    """
    report_id: str
    system_name: str
    reporting_period_start: str
    reporting_period_end: str

    # Performance monitoring
    total_inferences: int
    auc_trend: List[Dict[str, Any]]  # [{date, auc, component}]
    drift_events_detected: int
    drift_events_resolved: int

    # Conformal prediction monitoring
    conformal_coverage_achieved: Optional[float]
    conformal_interval_width_mean: Optional[float]

    # Incidents
    incidents_count: int
    incidents_summary: str

    # Risk assessment
    risk_level: str  # HIGH | MEDIUM | LOW
    risk_changes: str

    # Corrective actions
    corrective_actions_taken: List[str]
    planned_improvements: List[str]

    # Compliance
    regulatory_framework: str = "EU AI Act Art.61"
    generated_at: str = ""


def generate_eu_ai_act_report(
    reporting_period: tuple,
    monitoring_data: Dict[str, Any],
) -> EUAIActMonitoringReport:
    """Generate an EU AI Act Art.61 post-market monitoring report."""
    now = datetime.now(timezone.utc)
    start, end = reporting_period

    return EUAIActMonitoringReport(
        report_id=f"EUAI-PMM-{now.strftime('%Y%m%d')}",
        system_name="LIP — Liquidity Intelligence Platform",
        reporting_period_start=start if isinstance(start, str) else start.isoformat(),
        reporting_period_end=end if isinstance(end, str) else end.isoformat(),
        total_inferences=monitoring_data.get("total_inferences", 0),
        auc_trend=monitoring_data.get("auc_trend", []),
        drift_events_detected=monitoring_data.get("drift_events_detected", 0),
        drift_events_resolved=monitoring_data.get("drift_events_resolved", 0),
        conformal_coverage_achieved=monitoring_data.get("conformal_coverage"),
        conformal_interval_width_mean=monitoring_data.get("conformal_width_mean"),
        incidents_count=monitoring_data.get("incidents_count", 0),
        incidents_summary=monitoring_data.get("incidents_summary", "No incidents reported."),
        risk_level=monitoring_data.get("risk_level", "MEDIUM"),
        risk_changes=monitoring_data.get(
            "risk_changes",
            "No material changes to risk profile during reporting period.",
        ),
        corrective_actions_taken=monitoring_data.get("corrective_actions", []),
        planned_improvements=monitoring_data.get("planned_improvements", []),
        generated_at=now.isoformat(),
    )


def export_eu_ai_act_report_json(report: EUAIActMonitoringReport) -> str:
    """Serialize an EU AI Act report to JSON."""
    return json.dumps(asdict(report), indent=2, default=str)
