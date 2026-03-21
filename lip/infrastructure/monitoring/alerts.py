"""
alerts.py — PagerDuty alerting for LIP degraded mode and KMS failure.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """PagerDuty Events v2 severity levels, mapped to LIP operational urgency.

    Attributes:
        CRITICAL: Immediate action required; page on-call.  Used for kill
            switch activations, KMS failures, and GPU failures.
        ERROR: Significant issue; attention needed within the hour.  Used
            for AUC drift exceeding thresholds.
        WARNING: Potential issue; review within the shift.  Used for P99
            latency breaches and queue depth spikes.
        INFO: Informational; no immediate action required.  Used for
            scheduled salt rotation reminders.
    """

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AlertEvent(str, Enum):
    """Enumeration of named alert conditions across all LIP components.

    Attributes:
        DEGRADED_MODE_ENTERED: Any component entered a degraded operating mode.
        KMS_FAILURE: Key Management Service is unreachable; new offers halted.
        GPU_FAILURE: CUDA device unavailable; inference has fallen back to CPU.
        KILL_SWITCH_ACTIVATED: Operator or automated system activated the kill
            switch; all new offers halted immediately.
        AUC_DRIFT: C1 model AUC has drifted below the monitoring threshold
            (baseline 0.739; target 0.850).
        LATENCY_P99_EXCEEDED: P99 inference latency exceeded the 94ms SLO.
        QUEUE_DEPTH_HIGH: Kafka consumer queue depth exceeded the HPA
            scale-out threshold (100 messages).
        SALT_ROTATION_DUE: C6 AML salt has reached its 365-day rotation
            deadline and requires rotation.
    """

    DEGRADED_MODE_ENTERED = "degraded_mode_entered"
    KMS_FAILURE = "kms_failure"
    GPU_FAILURE = "gpu_failure"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    AUC_DRIFT = "auc_drift"
    LATENCY_P99_EXCEEDED = "latency_p99_exceeded"
    QUEUE_DEPTH_HIGH = "queue_depth_high"
    SALT_ROTATION_DUE = "salt_rotation_due"
    FX_BLOCK_RATE_HIGH = "fx_block_rate_high"
    SHORTFALL_RATE_HIGH = "shortfall_rate_high"


@dataclass
class Alert:
    """A structured alert payload ready for dispatch via :class:`PagerDutyAlerter`.

    Attributes:
        event: :class:`AlertEvent` categorising the alert.
        severity: :class:`AlertSeverity` controlling PagerDuty routing.
        summary: Human-readable one-line summary (used as PagerDuty
            incident title).
        details: Arbitrary key-value pairs included as
            ``custom_details`` in the PagerDuty Events v2 payload.
        component: Short LIP component identifier (e.g., ``'c1'``,
            ``'c6'``, ``'c7'``) appended to the PagerDuty source string
            as ``lip/<component>``.
    """

    event: AlertEvent
    severity: AlertSeverity
    summary: str
    details: dict
    component: str


class PagerDutyAlerter:
    """PagerDuty alerting integration."""

    def __init__(self, integration_key: Optional[str] = None, dry_run: bool = False):
        """Initialise the alerter with a PagerDuty Events v2 integration key.

        Args:
            integration_key: PagerDuty routing/integration key for the
                target service.  When ``None`` and ``dry_run=False``,
                alerts are dropped with a warning log.
            dry_run: When ``True``, alerts are logged at INFO level and
                never sent to PagerDuty (useful for staging environments).
        """
        self._key = integration_key
        self._dry_run = dry_run

    def send(self, alert: Alert) -> bool:
        """Send an alert to PagerDuty via the Events v2 API.

        In dry-run mode, logs the alert at INFO level and returns ``True``
        without making any network call.  When no integration key is
        configured and not in dry-run mode, drops the alert with a warning.

        Args:
            alert: :class:`Alert` payload to dispatch.

        Returns:
            ``True`` when the alert was accepted (HTTP 202) or dry-run
            mode is active; ``False`` when no key is configured or the
            HTTP request fails.
        """
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
        """Initialise with an optional custom alerter.

        Args:
            alerter: :class:`PagerDutyAlerter` to use for dispatching
                alerts.  Defaults to a dry-run alerter when ``None``.
        """
        self._alerter = alerter or PagerDutyAlerter(dry_run=True)

    def alert_degraded_mode(self, reason: str, component: str) -> None:
        """Send a CRITICAL alert when any LIP component enters degraded mode.

        Args:
            reason: Human-readable degradation reason (e.g.,
                ``'GPU_FAILURE'``, ``'KMS_FAILURE'``).
            component: Short component identifier (e.g., ``'c7'``).
        """
        self._alerter.send(Alert(
            event=AlertEvent.DEGRADED_MODE_ENTERED,
            severity=AlertSeverity.CRITICAL,
            summary=f"LIP {component} entered degraded mode: {reason}",
            details={"reason": reason, "component": component},
            component=component,
        ))

    def alert_kms_failure(self, gap_seconds: float) -> None:
        """Send a CRITICAL alert when KMS becomes unavailable.

        Args:
            gap_seconds: Seconds elapsed since KMS first became unavailable.
                Included in the PagerDuty details for DORA Art.30 incident
                reporting.
        """
        self._alerter.send(Alert(
            event=AlertEvent.KMS_FAILURE,
            severity=AlertSeverity.CRITICAL,
            summary=f"KMS unavailable for {gap_seconds:.1f}s; new offers halted",
            details={"gap_seconds": gap_seconds},
            component="c7",
        ))

    def alert_kill_switch(self, reason: str) -> None:
        """Send a CRITICAL alert when the kill switch is activated.

        Args:
            reason: The reason string supplied to
                :meth:`~lip.c7_execution_agent.kill_switch.KillSwitch.activate`.
        """
        self._alerter.send(Alert(
            event=AlertEvent.KILL_SWITCH_ACTIVATED,
            severity=AlertSeverity.CRITICAL,
            summary=f"Kill switch activated: {reason}",
            details={"reason": reason},
            component="c7",
        ))

    def alert_auc_drift(self, current_auc: float, baseline_auc: float) -> None:
        """Send an ERROR alert when C1 model AUC drifts below threshold.

        Args:
            current_auc: Current observed AUC value from the monitoring job.
            baseline_auc: Baseline AUC at last model validation (canonical
                baseline is 0.739; target is 0.850).
        """
        self._alerter.send(Alert(
            event=AlertEvent.AUC_DRIFT,
            severity=AlertSeverity.ERROR,
            summary=f"C1 AUC drifted: {current_auc:.3f} vs baseline {baseline_auc:.3f}",
            details={"current_auc": current_auc, "baseline_auc": baseline_auc},
            component="c1",
        ))

    def alert_latency_p99(self, latency_ms: float, threshold_ms: float = 94) -> None:
        """Send a WARNING alert when P99 inference latency exceeds the SLO.

        Args:
            latency_ms: Observed P99 latency in milliseconds.
            threshold_ms: SLO threshold in milliseconds (default 94ms per
                Architecture Spec v1.2).
        """
        self._alerter.send(Alert(
            event=AlertEvent.LATENCY_P99_EXCEEDED,
            severity=AlertSeverity.WARNING,
            summary=f"Inference P99 latency {latency_ms:.1f}ms exceeds {threshold_ms}ms threshold",
            details={"latency_ms": latency_ms, "threshold_ms": threshold_ms},
            component="c1",
        ))

    def alert_queue_depth(self, depth: int, threshold: int = 100) -> None:
        """Send a WARNING alert when the Kafka consumer queue depth is high.

        Args:
            depth: Current queue depth (number of unprocessed messages).
            threshold: HPA scale-out threshold (default 100; see
                ``HPA_SCALE_OUT_QUEUE_DEPTH`` in ``constants.py``).
        """
        self._alerter.send(Alert(
            event=AlertEvent.QUEUE_DEPTH_HIGH,
            severity=AlertSeverity.WARNING,
            summary=f"Inference queue depth {depth} exceeds HPA scale-out threshold {threshold}",
            details={"queue_depth": depth, "hpa_threshold": threshold},
            component="c5",
        ))

    def alert_fx_block_rate(self, corridor: str, block_rate: float, threshold: float = 0.20) -> None:
        """Send a WARNING alert when FX block rate exceeds threshold in a corridor.

        Args:
            corridor: Corridor identifier (e.g., ``'USD_EUR'``).
            block_rate: Fraction of payments blocked by FX policy in the window.
            threshold: Alert threshold (default 20%).
        """
        self._alerter.send(Alert(
            event=AlertEvent.FX_BLOCK_RATE_HIGH,
            severity=AlertSeverity.WARNING,
            summary=f"FX block rate {block_rate:.1%} in corridor {corridor} exceeds {threshold:.0%}",
            details={"corridor": corridor, "block_rate": block_rate, "threshold": threshold},
            component="c7",
        ))

    def alert_shortfall_rate(self, rate: float, threshold: float = 0.05) -> None:
        """Send a WARNING alert when partial settlement rate exceeds threshold.

        Args:
            rate: Fraction of settlements that were partial in the window.
            threshold: Alert threshold (default 5%).
        """
        self._alerter.send(Alert(
            event=AlertEvent.SHORTFALL_RATE_HIGH,
            severity=AlertSeverity.WARNING,
            summary=f"Partial settlement rate {rate:.1%} exceeds {threshold:.0%} threshold",
            details={"rate": rate, "threshold": threshold},
            component="c3",
        ))
