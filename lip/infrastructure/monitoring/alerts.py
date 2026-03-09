"""
alerts.py — PagerDuty alerting for LIP degraded mode and KMS failure.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AlertEvent(str, Enum):
    DEGRADED_MODE_ENTERED = "degraded_mode_entered"
    KMS_FAILURE = "kms_failure"
    GPU_FAILURE = "gpu_failure"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    AUC_DRIFT = "auc_drift"
    LATENCY_P99_EXCEEDED = "latency_p99_exceeded"
    QUEUE_DEPTH_HIGH = "queue_depth_high"
    SALT_ROTATION_DUE = "salt_rotation_due"


@dataclass
class Alert:
    event: AlertEvent
    severity: AlertSeverity
    summary: str
    details: dict
    component: str


class PagerDutyAlerter:
    """PagerDuty alerting integration."""

    def __init__(self, integration_key: Optional[str] = None, dry_run: bool = False):
        self._key = integration_key
        self._dry_run = dry_run

    def send(self, alert: Alert) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Alert: %s | %s | %s", alert.severity, alert.event, alert.summary)
            return True
        if self._key is None:
            logger.warning("PagerDuty integration key not configured; alert dropped: %s", alert.event)
            return False
        # In production, use the PagerDuty Events v2 API
        import json
        import urllib.request
        payload = {
            "routing_key": self._key,
            "event_action": "trigger",
            "payload": {
                "summary": alert.summary,
                "severity": alert.severity.value,
                "source": f"lip/{alert.component}",
                "custom_details": alert.details,
            },
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://events.pagerduty.com/v2/enqueue",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 202
        except Exception as exc:
            logger.error("PagerDuty alert failed: %s", exc)
            return False


class AlertManager:
    """Central alert management for all LIP components."""

    def __init__(self, alerter: Optional[PagerDutyAlerter] = None):
        self._alerter = alerter or PagerDutyAlerter(dry_run=True)

    def alert_degraded_mode(self, reason: str, component: str) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.DEGRADED_MODE_ENTERED,
            severity=AlertSeverity.CRITICAL,
            summary=f"LIP {component} entered degraded mode: {reason}",
            details={"reason": reason, "component": component},
            component=component,
        ))

    def alert_kms_failure(self, gap_seconds: float) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.KMS_FAILURE,
            severity=AlertSeverity.CRITICAL,
            summary=f"KMS unavailable for {gap_seconds:.1f}s; new offers halted",
            details={"gap_seconds": gap_seconds},
            component="c7",
        ))

    def alert_kill_switch(self, reason: str) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.KILL_SWITCH_ACTIVATED,
            severity=AlertSeverity.CRITICAL,
            summary=f"Kill switch activated: {reason}",
            details={"reason": reason},
            component="c7",
        ))

    def alert_auc_drift(self, current_auc: float, baseline_auc: float) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.AUC_DRIFT,
            severity=AlertSeverity.ERROR,
            summary=f"C1 AUC drifted: {current_auc:.3f} vs baseline {baseline_auc:.3f}",
            details={"current_auc": current_auc, "baseline_auc": baseline_auc},
            component="c1",
        ))

    def alert_latency_p99(self, latency_ms: float, threshold_ms: float = 94) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.LATENCY_P99_EXCEEDED,
            severity=AlertSeverity.WARNING,
            summary=f"Inference P99 latency {latency_ms:.1f}ms exceeds {threshold_ms}ms threshold",
            details={"latency_ms": latency_ms, "threshold_ms": threshold_ms},
            component="c1",
        ))

    def alert_queue_depth(self, depth: int, threshold: int = 100) -> None:
        self._alerter.send(Alert(
            event=AlertEvent.QUEUE_DEPTH_HIGH,
            severity=AlertSeverity.WARNING,
            summary=f"Inference queue depth {depth} exceeds HPA scale-out threshold {threshold}",
            details={"queue_depth": depth, "hpa_threshold": threshold},
            component="c5",
        ))
