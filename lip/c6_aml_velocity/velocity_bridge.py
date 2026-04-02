"""
velocity_bridge.py — Python bridge to the Rust-backed C6 velocity counters.

Architecture:
  1. Primary path: Import the PyO3 ``lip_c6_rust_velocity`` module compiled from
     ``lip/c6_aml_velocity/rust_velocity/``.  All velocity counter operations
     delegate to the Rust ``PyRollingVelocity`` backed by ``DashMap`` and
     Rust atomics for sub-millisecond, thread-safe concurrent access.

  2. Fallback path: If the Rust module is unavailable (not compiled, wrong
     Python ABI, or ``LIP_C6_FORCE_PYTHON=1`` env var set), the bridge
     falls back to the existing pure-Python ``VelocityChecker``.  A
     ``UserWarning`` is emitted on each process startup — fallback is not
     silent.

Performance:
  Rust path: ≤ 0.5ms p99 for check/record (DashMap shard lock, no Python GIL).
  Python path: ~2–5ms p99 (threading.Lock contention at high concurrency).

Prometheus metrics (requires ``prometheus_client`` in the environment):
  ``c6_velocity_check_latency_seconds``  Histogram  check() latency
  ``c6_velocity_backend``                Info       "rust" or "python"
  ``c6_velocity_rust_metrics``           Gauge      per-metric from Rust counters
"""
from __future__ import annotations

import logging
import os
import warnings
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt to import the compiled Rust extension
# ---------------------------------------------------------------------------

_FORCE_PYTHON = os.environ.get("LIP_C6_FORCE_PYTHON", "0") == "1"

try:
    if _FORCE_PYTHON:
        raise ImportError("LIP_C6_FORCE_PYTHON=1 — forcing Python fallback")
    import lip_c6_rust_velocity as _rust  # type: ignore[import]

    _RUST_AVAILABLE = True
    logger.debug(
        "lip_c6_rust_velocity loaded (version %s): Rust-backed C6 velocity active.",
        getattr(_rust, "__version__", "unknown"),
    )
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False
    warnings.warn(
        "lip_c6_rust_velocity Rust extension not found. "
        "Falling back to pure-Python C6 velocity counters. "
        "Build the Rust extension with: "
        "cd lip/c6_aml_velocity/rust_velocity && maturin build --release && "
        "pip install target/wheels/*.whl",
        UserWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Prometheus metrics (optional — gracefully absent)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import Histogram, Info

    _vel_latency = Histogram(
        "c6_velocity_check_latency_seconds",
        "C6 velocity check() latency in seconds",
        buckets=[0.0001, 0.0005, 0.001, 0.002, 0.005, 0.010, 0.050, 0.100],
    )
    _vel_backend = Info("c6_velocity_backend", "C6 velocity backend (rust or python)")
    _vel_backend.info({"backend": "rust" if _RUST_AVAILABLE else "python"})
    _HAS_PROMETHEUS = True
except (ImportError, ValueError):
    # ValueError: Prometheus metric already registered (e.g. module reload in tests)
    _vel_latency = None  # type: ignore[assignment]
    _HAS_PROMETHEUS = False

# ---------------------------------------------------------------------------
# Public API: RustVelocityChecker (unified interface)
# ---------------------------------------------------------------------------


class RustVelocityChecker:
    """Rolling 24-hour AML velocity checker backed by Rust or pure Python.

    Presents the same check/record/check_and_record interface as the existing
    ``VelocityChecker`` from ``velocity.py``, so it is a drop-in replacement
    for the pipeline's C6 gate.

    When the Rust extension is available, all operations delegate to
    ``PyRollingVelocity`` (DashMap + atomics, thread-safe without GIL).
    When unavailable, falls back to ``VelocityChecker`` (in-process deque).

    Args:
        salt: Byte string used to hash entity/beneficiary IDs before storage.
              Must be the same salt as used by the enclosing ``AMLChecker``
              to ensure cross-licensee isolation (EPG-24).
        window_seconds: Rolling window length in seconds (default 86400 = 24h).
        redis_client: Optional Redis client forwarded to the Python fallback.
                      Ignored when the Rust extension is active (Rust uses
                      in-process DashMap; Redis wiring is a future extension).
    """

    RUST_AVAILABLE: bool = _RUST_AVAILABLE

    def __init__(
        self,
        salt: bytes,
        window_seconds: int = 86400,
        redis_client=None,
    ) -> None:
        self._salt = salt
        if _RUST_AVAILABLE:
            self._rust_vel = _rust.PyRollingVelocity(
                window_seconds=window_seconds,
                salt=list(salt),
            )
            self._py_vel = None
        else:
            from lip.c6_aml_velocity.velocity import VelocityChecker

            self._rust_vel = None
            self._py_vel = VelocityChecker(salt=salt, redis_client=redis_client)

    def check(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ):
        """Check velocity limits.  Returns a VelocityResult-compatible object."""
        import time

        t0 = time.monotonic()
        try:
            if _RUST_AVAILABLE:
                return self._check_rust(
                    entity_id, amount, beneficiary_id,
                    dollar_cap_override, count_cap_override,
                )
            return self._py_vel.check(
                entity_id, amount, beneficiary_id,
                dollar_cap_override, count_cap_override,
            )
        finally:
            if _HAS_PROMETHEUS and _vel_latency is not None:
                _vel_latency.observe(time.monotonic() - t0)

    def _check_rust(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal],
        count_cap_override: Optional[int],
    ):
        from lip.c6_aml_velocity.velocity import VelocityResult

        dollar_cap = float(dollar_cap_override) if dollar_cap_override is not None else 0.0
        count_cap = count_cap_override if count_cap_override is not None else 0
        passed, reason, vol_usd, cnt = self._rust_vel.check(
            entity_id, beneficiary_id, float(amount),
            dollar_cap, count_cap, 0.80,
        )
        entity_hash = self._rust_vel.hash_id(entity_id)
        conc = self._rust_vel.get_beneficiary_concentration(entity_id)
        return VelocityResult(
            passed=passed,
            reason=reason if reason else None,
            entity_id_hash=entity_hash,
            dollar_volume_24h=Decimal(str(round(vol_usd, 2))),
            count_24h=int(cnt),
            beneficiary_concentration=Decimal(str(round(conc, 6))) if conc > 0 else None,
        )

    def record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ) -> None:
        """Record a transaction in the rolling window."""
        if _RUST_AVAILABLE:
            self._rust_vel.record(entity_id, beneficiary_id, float(amount))
        else:
            self._py_vel.record(
                entity_id, amount, beneficiary_id,
                dollar_cap_override, count_cap_override,
            )

    def check_and_record(
        self,
        entity_id: str,
        amount: Decimal,
        beneficiary_id: str,
        dollar_cap_override: Optional[Decimal] = None,
        count_cap_override: Optional[int] = None,
    ):
        """Atomically check and record (preferred for production use).

        Rust path: holds the DashMap entry write-guard for the full duration
        so no concurrent thread can slip through between the check and write.

        Python path: acquires ``_check_record_lock`` (thread-safe within
        a single process; use Redis path for multi-worker).
        """
        if _RUST_AVAILABLE:
            from lip.c6_aml_velocity.velocity import VelocityResult

            dollar_cap = float(dollar_cap_override) if dollar_cap_override is not None else 0.0
            count_cap = count_cap_override if count_cap_override is not None else 0
            passed, reason, vol_usd, cnt = self._rust_vel.check_and_record(
                entity_id, beneficiary_id, float(amount),
                dollar_cap, count_cap, 0.80,
            )
            entity_hash = self._rust_vel.hash_id(entity_id)
            conc = self._rust_vel.get_beneficiary_concentration(entity_id)
            return VelocityResult(
                passed=passed,
                reason=reason if reason else None,
                entity_id_hash=entity_hash,
                dollar_volume_24h=Decimal(str(round(vol_usd, 2))),
                count_24h=int(cnt),
                beneficiary_concentration=Decimal(str(round(conc, 6))) if conc > 0 else None,
            )
        return self._py_vel.check_and_record(
            entity_id, amount, beneficiary_id,
            dollar_cap_override, count_cap_override,
        )

    def _hash_entity(self, entity_id: str) -> str:
        """Return the hashed entity ID (for test/audit use)."""
        if _RUST_AVAILABLE:
            return self._rust_vel.hash_id(entity_id)
        return self._py_vel._hash_entity(entity_id)

    def get_rust_metrics(self) -> dict:
        """Return Rust-side atomic metric counters (Rust path only; {} on Python path)."""
        if _RUST_AVAILABLE:
            return dict(self._rust_vel.get_metrics())
        return {}

    def flush(self) -> None:
        """Flush all window state (for testing / scheduled resets)."""
        if _RUST_AVAILABLE:
            self._rust_vel.flush()
        else:
            self._py_vel._window._records.clear()
