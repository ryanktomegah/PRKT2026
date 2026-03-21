"""
circuit_breaker.py — Circuit breaker pattern for external service calls.
GAP-19: C4 Groq API calls need protection against cascading failures.

States: CLOSED → OPEN (on N failures) → HALF_OPEN (after timeout) → CLOSED (on success)
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and calls are rejected."""


class CircuitBreaker:
    """Thread-safe circuit breaker for wrapping external service calls.

    Parameters
    ----------
    failure_threshold:
        Number of consecutive failures before the circuit opens.
    recovery_timeout_seconds:
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
    name:
        Human-readable name for logging.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        name: str = "circuit_breaker",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds
        self._name = name
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._success_count = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit %s transitioning OPEN → HALF_OPEN", self._name)
            return self._state

    def call(self, fn, *args, **kwargs):
        """Execute ``fn`` through the circuit breaker.

        Raises
        ------
        CircuitOpenError
            When the circuit is OPEN and the recovery timeout has not elapsed.
        """
        current = self.state

        if current == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit '{self._name}' is OPEN after {self._failure_count} failures"
            )

        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            self._record_failure()
            raise exc

        self._record_success()
        return result

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            self._success_count = 0
            if self._failure_count >= self._failure_threshold and self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit %s opened after %d consecutive failures",
                    self._name,
                    self._failure_count,
                )

    def _record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info("Circuit %s recovered: HALF_OPEN → CLOSED", self._name)
            self._failure_count = 0
            self._success_count += 1

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
