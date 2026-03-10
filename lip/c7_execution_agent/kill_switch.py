"""
kill_switch.py — Kill switch and KMS unavailability behavior.
Architecture Spec S2.5:
  Kill switch activated → halt ALL new offers, preserve funded loans, buffer settlements.
  KMS unavailable → halt new offers, preserve funded loans, buffer settlements, auto-recover.

Regulatory obligations covered by this module:
  EU AI Act Art.14  — Human oversight: kill switch is the operator's mechanism to override
    automated credit decisions at any time without software changes required.
  EU AI Act Art.9   — Risk management: kill switch is the primary risk-management control
    for halting automated decisions in response to an adverse event.
  DORA Art.30       — ICT operational resilience: kill switch activations must be logged with
    a reason string; KMS unavailability gap is tracked for incident reporting.
  SR 11-7 (Fed/OCC) — Model risk management: human override capability is mandatory; this
    module provides the hard stop that can be triggered by model validators or risk officers.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class KillSwitchState(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class KMSState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class KillSwitchStatus:
    kill_switch_state: KillSwitchState
    kms_state: KMSState
    activated_at: Optional[datetime] = None
    kms_unavailable_since: Optional[datetime] = None
    reason: Optional[str] = None


class KillSwitch:
    """Kill switch with KMS availability monitoring."""

    def __init__(self, redis_client=None, kms_client=None):
        self._redis = redis_client
        self._kms_client = kms_client
        self._kill_switch_state = KillSwitchState.INACTIVE
        self._kms_state = KMSState.AVAILABLE
        self._activated_at: Optional[datetime] = None
        self._kms_unavailable_since: Optional[datetime] = None
        self._reason: Optional[str] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def activate(self, reason: str = "") -> None:
        self._kill_switch_state = KillSwitchState.ACTIVE
        self._activated_at = datetime.now(tz=timezone.utc)
        self._reason = reason
        if self._redis:
            self._redis.set("lip:kill_switch", "ACTIVE")
        logger.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate(self) -> None:
        self._kill_switch_state = KillSwitchState.INACTIVE
        self._activated_at = None
        self._reason = None
        if self._redis:
            self._redis.delete("lip:kill_switch")
        logger.info("Kill switch deactivated")

    def is_active(self) -> bool:
        if self._redis:
            val = self._redis.get("lip:kill_switch")
            return val is not None and val.decode() == "ACTIVE"
        return self._kill_switch_state == KillSwitchState.ACTIVE

    def check_kms(self) -> KMSState:
        if self._kms_client is None:
            return KMSState.AVAILABLE
        try:
            self._kms_client.ping()
            if self._kms_state == KMSState.UNAVAILABLE:
                logger.info("KMS recovered after %.1fs gap", self.kms_unavailable_gap_seconds() or 0)
                self._kms_state = KMSState.AVAILABLE
                self._kms_unavailable_since = None
        except Exception as exc:
            if self._kms_state == KMSState.AVAILABLE:
                self._kms_unavailable_since = datetime.now(tz=timezone.utc)
                logger.error("KMS unavailable: %s", exc)
            self._kms_state = KMSState.UNAVAILABLE
        return self._kms_state

    def get_status(self) -> KillSwitchStatus:
        return KillSwitchStatus(
            kill_switch_state=KillSwitchState.ACTIVE if self.is_active() else KillSwitchState.INACTIVE,
            kms_state=self._kms_state,
            activated_at=self._activated_at,
            kms_unavailable_since=self._kms_unavailable_since,
            reason=self._reason,
        )

    def should_halt_new_offers(self) -> bool:
        return self.is_active() or self._kms_state == KMSState.UNAVAILABLE

    def kms_unavailable_gap_seconds(self) -> Optional[float]:
        if self._kms_unavailable_since is None:
            return None
        return (datetime.now(tz=timezone.utc) - self._kms_unavailable_since).total_seconds()

    def start_kms_monitor(self, interval: int = 30) -> None:
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.wait(interval):
                self.check_kms()

        self._monitor_thread = threading.Thread(target=_loop, daemon=True, name="kms-monitor")
        self._monitor_thread.start()
        logger.info("KMS monitor started (interval=%ds)", interval)

    def stop_kms_monitor(self) -> None:
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
