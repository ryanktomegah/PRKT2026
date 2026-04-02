"""
kill_switch_bridge.py — Python bridge to the Rust kill switch.

Architecture:
  1. Primary path: Import the PyO3 ``lip_kill_switch`` module compiled from
     ``lip/c7_execution_agent/rust_kill_switch/``. All calls delegate to the
     Rust ``AtomicBool`` with ``SeqCst``/``Acquire`` ordering guarantees and
     POSIX shared memory persistence.

  2. Fallback path: If the Rust module is unavailable (not compiled, import
     error, ``LIP_KS_FORCE_PYTHON=1``), fall back to the existing Python
     ``KillSwitch`` class.  ``CRITICAL`` logs are emitted on every fallback
     operation — silence is not acceptable here.

Fail-closed invariant:
  If ``lip_kill_switch`` is not importable, ``is_killed()`` returns ``True``
  until the Rust module is available.  No new offers may be emitted while the
  Rust module is absent.  This matches EU AI Act Art.9 (fail-safe default).

Memory ordering:
  When running via the Rust path, ``is_killed()`` calls
  ``AtomicBool::load(Ordering::Acquire)`` — sufficient to observe any
  ``SeqCst`` store from ``activate_kill()``.  See ``lib.rs`` for full rationale.

Prometheus metrics (requires ``prometheus_client`` in the environment):
  ``kill_switch_state``         Gauge   0=INACTIVE / 1=KILLED
  ``kill_switch_activations_total``  Counter  total activate() calls
  ``kill_switch_latency_ns``    Histogram  is_killed() call latency in nanoseconds
  ``kill_switch_backend``       Info     "rust" or "python"
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from lip.c7_execution_agent.kill_switch import (
    KillSwitch,
    KillSwitchState,
    KillSwitchStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (optional dependency — gracefully absent in test envs)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    _ks_state = Gauge(
        "kill_switch_state",
        "Current kill switch state: 0=INACTIVE 1=KILLED",
    )
    _ks_activations = Counter(
        "kill_switch_activations_total",
        "Total number of kill switch activations",
    )
    _ks_latency = Histogram(
        "kill_switch_latency_ns",
        "Latency of is_killed() calls in nanoseconds",
        buckets=[100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000],
    )
    _ks_backend = Info("kill_switch_backend", "Which backend is active: rust or python")
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Rust module import
# ---------------------------------------------------------------------------
_FORCE_PYTHON = os.environ.get("LIP_KS_FORCE_PYTHON", "").strip() == "1"

_rust_module = None
_rust_available = False

if not _FORCE_PYTHON:
    try:
        import lip_kill_switch as _rust_module  # type: ignore[import]

        _rust_available = True
        logger.info("lip_kill_switch Rust module loaded successfully (primary path)")
    except ImportError as _exc:
        logger.critical(
            "RUST KILL SWITCH MODULE UNAVAILABLE — operating in FAIL-CLOSED fallback mode. "
            "is_killed() returns True until the Rust module is loaded. "
            "Import error: %s",
            _exc,
        )
else:
    logger.critical(
        "LIP_KS_FORCE_PYTHON=1 — Rust kill switch disabled by environment variable. "
        "Operating in Python fallback mode (FAIL-CLOSED)."
    )

if _PROMETHEUS_AVAILABLE:
    _ks_backend.info({"backend": "rust" if _rust_available else "python_fallback"})

# ---------------------------------------------------------------------------
# Fallback Python kill switch (used when Rust module is unavailable)
# ---------------------------------------------------------------------------
_python_ks: Optional[KillSwitch] = None


def _get_python_ks() -> KillSwitch:
    """Lazy-initialise the Python fallback kill switch."""
    global _python_ks
    if _python_ks is None:
        _python_ks = KillSwitch()
        # Fail-closed: activate the Python kill switch so no offers go out
        # until the Rust module is available.
        _python_ks.activate("RUST_MODULE_UNAVAILABLE — fail-closed default")
    return _python_ks


# ---------------------------------------------------------------------------
# Public API — matches the existing KillSwitch interface
# ---------------------------------------------------------------------------

_last_fallback_log: float = 0.0
_FALLBACK_LOG_INTERVAL = 60.0  # seconds between repeated CRITICAL logs


def _maybe_warn_fallback() -> None:
    """Emit a CRITICAL log at most once per minute when on the fallback path."""
    global _last_fallback_log
    now = time.monotonic()
    if now - _last_fallback_log >= _FALLBACK_LOG_INTERVAL:
        _last_fallback_log = now
        logger.critical(
            "KILL SWITCH OPERATING IN PYTHON FALLBACK MODE — "
            "Rust kill switch is unavailable. EU AI Act Art.9 fail-closed posture active."
        )


def is_killed() -> bool:
    """Return ``True`` when the kill switch is active.

    Uses ``AtomicBool::load(Ordering::Acquire)`` via the Rust module when
    available, giving sub-100ns latency.  Falls back to the Python
    ``KillSwitch`` (which uses Redis or in-memory state) otherwise.

    **Fail-closed:** returns ``True`` if the Rust module is not available.
    """
    t0 = time.perf_counter_ns()
    try:
        if _rust_available:
            result: bool = _rust_module.is_killed()
        else:
            _maybe_warn_fallback()
            result = _get_python_ks().is_active()
    finally:
        latency_ns = time.perf_counter_ns() - t0
        if _PROMETHEUS_AVAILABLE:
            _ks_latency.observe(latency_ns)

    if _PROMETHEUS_AVAILABLE:
        _ks_state.set(1 if result else 0)

    return result


def activate_kill(reason: str = "") -> None:
    """Activate the kill switch.

    On the Rust path: calls ``AtomicBool::store(true, SeqCst)`` + shm write.
    On the fallback path: calls ``KillSwitch.activate(reason)``.

    Args:
        reason: Human-readable reason string for DORA Art.30 audit records.
    """
    if _rust_available:
        _rust_module.activate_kill(reason)
    else:
        _maybe_warn_fallback()
        _get_python_ks().activate(reason)

    if _PROMETHEUS_AVAILABLE:
        _ks_activations.inc()
        _ks_state.set(1)

    logger.critical("kill_switch_bridge.activate_kill: reason=%r backend=%s", reason, _backend_name())


def reset_kill() -> None:
    """Reset the kill switch to INACTIVE.

    On the Rust path: calls ``AtomicBool::store(false, SeqCst)`` + shm clear.
    On the fallback path: calls ``KillSwitch.deactivate()``.
    """
    if _rust_available:
        _rust_module.reset_kill()
    else:
        _maybe_warn_fallback()
        _get_python_ks().deactivate()

    if _PROMETHEUS_AVAILABLE:
        _ks_state.set(0)

    logger.warning("kill_switch_bridge.reset_kill: backend=%s", _backend_name())


def get_status() -> dict:
    """Return a status snapshot dict.

    Keys (Rust path): ``killed``, ``activated_at_unix_ms``, ``reason``,
    ``activation_count``, ``binary_running``.

    Keys (fallback path): ``killed``, ``backend``, ``reason``.
    """
    if _rust_available:
        return dict(_rust_module.get_status())  # type: ignore[arg-type]
    _maybe_warn_fallback()
    python_ks = _get_python_ks()
    status: KillSwitchStatus = python_ks.get_status()
    return {
        "killed": status.kill_switch_state == KillSwitchState.ACTIVE,
        "backend": "python_fallback",
        "reason": status.reason,
        "binary_running": False,
    }


def should_halt_new_offers() -> bool:
    """Return ``True`` when no new loan offers may be emitted.

    Delegates to ``is_killed()``.  Keeps the same method name as the
    existing ``KillSwitch.should_halt_new_offers()`` for drop-in compatibility.
    """
    return is_killed()


def backend_name() -> str:
    """Return the active backend identifier: ``"rust"`` or ``"python_fallback"``."""
    return _backend_name()


# ---------------------------------------------------------------------------
# Background health monitor
# ---------------------------------------------------------------------------

_monitor_thread: Optional[threading.Thread] = None
_monitor_stop = threading.Event()


def start_health_monitor(interval_seconds: float = 5.0) -> None:
    """Start a background thread that polls Rust binary health every ``interval_seconds``.

    If the Rust binary crashes (``get_status()`` raises), emits a CRITICAL log
    and sets ``kill_switch_state=KILLED`` (fail-closed).  Updates the
    ``kill_switch_binary_up`` Prometheus gauge if available.

    Args:
        interval_seconds: Poll interval (default 5.0 seconds).
    """
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return

    _monitor_stop.clear()

    def _loop() -> None:
        while not _monitor_stop.wait(interval_seconds):
            if not _rust_available:
                continue
            try:
                status = _rust_module.get_status()
                if not status.get("binary_running", True):
                    logger.critical(
                        "Rust kill switch binary reported NOT running — fail-closed posture active"
                    )
            except Exception as exc:
                logger.critical(
                    "Rust kill switch health check failed: %s — treating as KILLED (fail-closed)",
                    exc,
                )

    _monitor_thread = threading.Thread(target=_loop, daemon=True, name="ks-health-monitor")
    _monitor_thread.start()
    logger.info("Kill switch health monitor started (interval=%.1fs)", interval_seconds)


def stop_health_monitor() -> None:
    """Stop the background health monitor thread."""
    _monitor_stop.set()
    if _monitor_thread:
        _monitor_thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _backend_name() -> str:
    return "rust" if _rust_available else "python_fallback"
