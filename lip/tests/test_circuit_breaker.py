"""Tests for GAP-19: Circuit breaker."""
from __future__ import annotations

import time

import pytest

from lip.common.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_successful_calls_stay_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(10):
            result = cb.call(lambda: 42)
            assert result == 42
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects_calls(self):
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: 42)

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        time.sleep(0.15)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.1)
        with pytest.raises(ValueError):
            cb.call(self._raise_value_error)
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(ValueError):
            cb.call(self._raise_value_error)
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        result = cb.call(lambda: 99)
        assert result == 99

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        # 2 failures, then success, then 2 more failures should not open
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        cb.call(lambda: "ok")
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(self._raise_value_error)
        assert cb.state == CircuitState.CLOSED

    @staticmethod
    def _raise_value_error():
        raise ValueError("test failure")
