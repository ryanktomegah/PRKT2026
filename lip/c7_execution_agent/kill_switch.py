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
    """Operational state of the kill switch.

    Attributes:
        ACTIVE: Kill switch engaged; all new loan offers must be halted.
            Funded loans and settlement buffering continue unaffected.
        INACTIVE: Normal operating mode; kill switch is not engaged.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class KMSState(str, Enum):
    """Availability state of the Key Management Service (KMS).

    A KMS outage triggers the same halt-new-offers behaviour as an active
    kill switch (Architecture Spec S2.5).

    Attributes:
        AVAILABLE: KMS is reachable and responding to ``ping()`` calls.
        UNAVAILABLE: KMS has not responded; new offers are halted until
            recovery.  The unavailability gap is tracked for DORA Art.30
            incident reporting.
    """

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class KillSwitchStatus:
    """Point-in-time snapshot of kill switch and KMS state.

    Attributes:
        kill_switch_state: Current :class:`KillSwitchState`.
        kms_state: Current :class:`KMSState`.
        activated_at: UTC datetime when the kill switch was last activated,
            or ``None`` when inactive.
        kms_unavailable_since: UTC datetime when KMS first became unavailable
            in the current outage, or ``None`` when KMS is available.
        reason: Human-readable reason string supplied to :meth:`KillSwitch.activate`,
            or ``None`` when inactive.
    """

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
        self._state_lock = threading.Lock()

    def activate(self, reason: str = "") -> None:
        """Engage the kill switch and halt all new loan offers immediately.

        Sets the Redis key ``lip:kill_switch = ACTIVE`` when a Redis client is
        configured so that all pipeline workers across pods observe the halt.
        Logs at ``CRITICAL`` level for DORA Art.30 incident records.

        Args:
            reason: Human-readable description of why the kill switch was
                activated (e.g., ``'model_auc_drift'``, ``'regulatory_audit'``).
                Required for DORA incident reporting; an empty string is
                accepted but not recommended.
        """
        with self._state_lock:
            self._kill_switch_state = KillSwitchState.ACTIVE
            self._activated_at = datetime.now(tz=timezone.utc)
            self._reason = reason
        if self._redis:
            self._redis.set("lip:kill_switch", "ACTIVE")
        logger.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate(self) -> None:
        """Disengage the kill switch and resume normal offer processing.

        Deletes the Redis key ``lip:kill_switch`` so that all pipeline workers
        observe the recovery.  Resets in-memory state including
        ``activated_at`` and ``reason``.
        """
        with self._state_lock:
            self._kill_switch_state = KillSwitchState.INACTIVE
            self._activated_at = None
            self._reason = None
        if self._redis:
            self._redis.delete("lip:kill_switch")
        logger.info("Kill switch deactivated")

    def is_active(self) -> bool:
        """Return True when the kill switch is currently engaged.

        When a Redis client is configured, queries Redis directly so that
        in-memory state stays consistent across multiple pods.  Falls back
        to in-memory state when no Redis client is available.

        Returns:
            ``True`` if the kill switch is active; ``False`` otherwise.
        """
        if self._redis:
            val = self._redis.get("lip:kill_switch")
            return val is not None and val.decode() == "ACTIVE"
        with self._state_lock:
            return self._kill_switch_state == KillSwitchState.ACTIVE

    def check_kms(self) -> KMSState:
        """Probe the KMS and update internal availability state.

        Calls ``kms_client.ping()``; any exception is treated as unavailability.
        Transitions:
          * AVAILABLE → UNAVAILABLE on first exception (records ``kms_unavailable_since``).
          * UNAVAILABLE → AVAILABLE on successful ping (logs the gap duration).

        Returns:
            Current :class:`KMSState` after the probe.
        """
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
        """Return a point-in-time snapshot of kill switch and KMS state.

        When no Redis client is configured, all state is read atomically under
        the state lock.  When Redis is configured, ``is_active()`` queries Redis
        for the authoritative distributed state.

        Returns:
            :class:`KillSwitchStatus` dataclass with all state fields.
        """
        with self._state_lock:
            in_memory_active = self._kill_switch_state == KillSwitchState.ACTIVE
            activated_at = self._activated_at
            reason = self._reason
        # Query Redis (if configured) after releasing the lock — Redis call
        # must not be made while holding the in-memory lock to avoid deadlock.
        is_active = self.is_active() if self._redis else in_memory_active
        return KillSwitchStatus(
            kill_switch_state=KillSwitchState.ACTIVE if is_active else KillSwitchState.INACTIVE,
            kms_state=self._kms_state,
            activated_at=activated_at,
            kms_unavailable_since=self._kms_unavailable_since,
            reason=reason,
        )

    def should_halt_new_offers(self) -> bool:
        """Return True when either the kill switch or KMS unavailability requires halting.

        This is the primary safety gate checked by C7 before processing any
        loan offer.  Both conditions produce the same outcome: halt new offers,
        preserve funded loans, buffer settlements (Architecture Spec S2.5).

        Returns:
            ``True`` if new offers must be halted; ``False`` for normal
            operation.
        """
        return self.is_active() or self._kms_state == KMSState.UNAVAILABLE

    def kms_unavailable_gap_seconds(self) -> Optional[float]:
        """Return the elapsed seconds since KMS first became unavailable.

        Used by :meth:`check_kms` to log the recovery gap and by
        ``AlertManager.alert_kms_failure`` for DORA Art.30 incident records.

        Returns:
            Elapsed seconds as a float, or ``None`` when KMS is currently
            available (no ongoing outage).
        """
        if self._kms_unavailable_since is None:
            return None
        return (datetime.now(tz=timezone.utc) - self._kms_unavailable_since).total_seconds()

    def start_kms_monitor(self, interval: int = 30) -> None:
        """Start a background daemon thread that polls KMS every ``interval`` seconds.

        The thread is a daemon so it does not block process shutdown.
        Only one monitor thread may run at a time; call :meth:`stop_kms_monitor`
        before starting a new one.

        Args:
            interval: Polling interval in seconds (default 30).
        """
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.wait(interval):
                self.check_kms()

        self._monitor_thread = threading.Thread(target=_loop, daemon=True, name="kms-monitor")
        self._monitor_thread.start()
        logger.info("KMS monitor started (interval=%ds)", interval)

    def stop_kms_monitor(self) -> None:
        """Signal the KMS monitor thread to stop and wait up to 5 seconds for it to exit.

        Safe to call even when no monitor thread is running.
        """
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
