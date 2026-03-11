"""
degraded_mode.py — GPU/KMS failure handling.
GPU failure → CPU fallback, logs degraded_mode=True.
KMS failure → halt new offers, logs kms_unavailable_gap.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DegradedReason(str, Enum):
    """Root cause categories for entering degraded operating mode.

    Attributes:
        GPU_FAILURE: CUDA device unavailable; inference falls back to CPU.
            New offers are *not* halted — only latency SLOs may be affected.
        KMS_FAILURE: Key Management Service unreachable; new loan offers are
            halted until KMS recovers (Architecture Spec S2.5).
        MODEL_LOAD_FAILURE: Model artefact could not be loaded at startup or
            during a hot-swap; inference may use a stale cached version.
        NETWORK_FAILURE: External network unreachable (e.g., corridor-data
            endpoints); predictions may use cached embeddings.
    """

    GPU_FAILURE = "GPU_FAILURE"
    KMS_FAILURE = "KMS_FAILURE"
    MODEL_LOAD_FAILURE = "MODEL_LOAD_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"


@dataclass
class DegradedState:
    """Point-in-time snapshot of the degraded operating mode.

    Attributes:
        is_degraded: ``True`` when any degraded mode is active.
        reason: :class:`DegradedReason` that caused the current degraded mode,
            or ``None`` when operating normally.
        degraded_since: UTC datetime when degraded mode was entered, or
            ``None`` when not degraded.
        gpu_fallback_to_cpu: ``True`` when GPU failure has triggered CPU
            fallback inference.  Only set when ``reason == GPU_FAILURE``.
        kms_unavailable_gap_seconds: Seconds elapsed since KMS became
            unavailable.  Populated lazily by
            :meth:`~DegradedModeManager.get_kms_gap_seconds`; ``None`` in
            this snapshot (compute via the method instead).
    """

    is_degraded: bool = False
    reason: Optional[DegradedReason] = None
    degraded_since: Optional[datetime] = None
    gpu_fallback_to_cpu: bool = False
    kms_unavailable_gap_seconds: Optional[float] = None


class DegradedModeManager:
    """Tracks and manages degraded operating modes."""

    def __init__(self) -> None:
        """Initialise with a clean (non-degraded) state."""
        self.current_state = DegradedState()

    def enter_degraded_mode(self, reason: DegradedReason, gpu_fallback: bool = False) -> None:
        """Record entry into a degraded operating mode and emit an error log.

        Sets ``gpu_fallback_to_cpu=True`` only when ``reason`` is
        :attr:`~DegradedReason.GPU_FAILURE` and ``gpu_fallback=True``.

        Args:
            reason: :class:`DegradedReason` describing why degraded mode was
                entered.
            gpu_fallback: When ``True`` and ``reason == GPU_FAILURE``, enables
                CPU-fallback inference.
        """
        self.current_state = DegradedState(
            is_degraded=True,
            reason=reason,
            degraded_since=datetime.now(tz=timezone.utc),
            gpu_fallback_to_cpu=gpu_fallback and reason == DegradedReason.GPU_FAILURE,
        )
        logger.error("Entered degraded mode: reason=%s gpu_fallback=%s", reason, gpu_fallback)

    def exit_degraded_mode(self) -> None:
        """Clear degraded mode and return to normal operating state.

        Logs the previous reason for post-incident review and resets
        :attr:`current_state` to a clean :class:`DegradedState`.
        """
        logger.info("Exiting degraded mode (was: %s)", self.current_state.reason)
        self.current_state = DegradedState()

    def is_degraded(self) -> bool:
        """Return True when any degraded mode is currently active.

        Returns:
            ``True`` if :attr:`current_state.is_degraded` is set.
        """
        return self.current_state.is_degraded

    def should_use_cpu(self) -> bool:
        """True if GPU failed and CPU fallback is enabled."""
        return (
            self.current_state.reason == DegradedReason.GPU_FAILURE
            and self.current_state.gpu_fallback_to_cpu
        )

    def should_halt_new_offers(self) -> bool:
        """True if KMS is unavailable."""
        return self.current_state.reason == DegradedReason.KMS_FAILURE

    def get_kms_gap_seconds(self) -> Optional[float]:
        """Return elapsed seconds since KMS failure was first recorded.

        Used to populate the ``kms_unavailable_gap`` field in
        :class:`~lip.common.schemas.DecisionLogEntry` and for DORA Art.30
        incident metrics.

        Returns:
            Elapsed seconds as a float, or ``None`` when the current
            degraded reason is not KMS-related or ``degraded_since`` is
            unset.
        """
        if self.current_state.reason != DegradedReason.KMS_FAILURE:
            return None
        if self.current_state.degraded_since is None:
            return None
        return (datetime.now(tz=timezone.utc) - self.current_state.degraded_since).total_seconds()

    def get_state_dict(self) -> dict:
        """Returns fields suitable for inclusion in DecisionLogEntry."""
        return {
            "degraded_mode": self.current_state.is_degraded,
            "gpu_fallback": self.current_state.gpu_fallback_to_cpu,
            "kms_unavailable_gap": self.get_kms_gap_seconds(),
        }
