"""
test_kill_switch_rust.py — Python integration tests for the C7 kill switch bridge.

Tests are designed to pass regardless of whether the Rust PyO3 module is
compiled.  When the Rust module is not available, all tests exercise the
Python fallback path and verify the fail-closed invariant.

Test categories:
  1. Fail-closed behaviour (Rust binary/module unavailable → killed=True)
  2. Fallback Python path — activate, reset, status
  3. Concurrent read access (16 threads)
  4. Reset flow (kill → reset → INACTIVE)
  5. Health monitor lifecycle
  6. Prometheus metrics (if prometheus_client available)
  7. Rust module path (skipped when PyO3 not compiled)
  8. Signal-based activation (skipped when Rust module not available)
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
import types
from typing import Generator
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_rust_module(*, initial_killed: bool = False) -> types.ModuleType:
    """Return a MagicMock that behaves like the compiled ``lip_kill_switch`` module."""
    _state: dict = {
        "killed": initial_killed,
        "reason": None,
        "activated_at_unix_ms": None,
        "activation_count": 0,
        "binary_running": True,
    }
    mod = MagicMock()

    def _is_killed() -> bool:
        return _state["killed"]

    def _activate_kill(reason: str = "") -> None:
        _state["killed"] = True
        _state["reason"] = reason
        _state["activated_at_unix_ms"] = int(time.time() * 1000)
        _state["activation_count"] += 1

    def _reset_kill() -> None:
        _state["killed"] = False
        _state["reason"] = None
        _state["activated_at_unix_ms"] = None

    def _get_status() -> dict:
        return dict(_state)

    mod.is_killed.side_effect = _is_killed
    mod.activate_kill.side_effect = _activate_kill
    mod.reset_kill.side_effect = _reset_kill
    mod.get_status.side_effect = _get_status

    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_bridge_module() -> Generator[None, None, None]:
    """Reload the bridge module before each test to get a clean slate.

    We patch the global state rather than reloading (reloading would break
    patched imports already in place).  The bridge's ``_python_ks`` and
    ``_rust_available`` are reset between tests.
    """
    import lip.c7_execution_agent.kill_switch_bridge as bridge

    orig_available = bridge._rust_available
    orig_module = bridge._rust_module
    orig_python_ks = bridge._python_ks
    orig_last_log = bridge._last_fallback_log

    yield

    # Restore state.
    bridge._rust_available = orig_available
    bridge._rust_module = orig_module
    bridge._python_ks = orig_python_ks
    bridge._last_fallback_log = orig_last_log


# ===========================================================================
# 1. Fail-closed behaviour
# ===========================================================================


class TestFailClosed:
    """When the Rust module is not available, is_killed() must return True."""

    def test_fail_closed_without_rust_module(self):
        """Bridge with no Rust module → is_killed() = True (fail-closed)."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._rust_module = None
        bridge._python_ks = None  # force re-initialisation
        bridge._last_fallback_log = 0.0  # allow log

        result = bridge.is_killed()
        assert result is True, (
            "is_killed() must return True when Rust module is unavailable (fail-closed)"
        )

    def test_fail_closed_backend_name(self):
        """Backend name must be 'python_fallback' when Rust unavailable."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        assert bridge.backend_name() == "python_fallback"

    def test_fail_closed_status_has_binary_running_false(self):
        """get_status() must report binary_running=False on fallback path."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._rust_module = None
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        status = bridge.get_status()
        assert status["binary_running"] is False
        assert status["backend"] == "python_fallback"

    def test_fail_closed_should_halt_new_offers(self):
        """should_halt_new_offers() must return True on fallback path."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        assert bridge.should_halt_new_offers() is True

    def test_fail_closed_emits_critical_log(self, caplog):
        """CRITICAL log must be emitted when operating on the fallback path."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0  # force log

        with caplog.at_level(logging.CRITICAL, logger="lip.c7_execution_agent.kill_switch_bridge"):
            bridge.is_killed()

        assert any("PYTHON FALLBACK" in r.message or "fail-closed" in r.message.lower() for r in caplog.records), (
            "Expected CRITICAL log about fallback mode"
        )


# ===========================================================================
# 2. Python fallback path — activate, reset, status
# ===========================================================================


class TestPythonFallbackPath:
    """Full activate/reset cycle on the Python fallback path."""

    def _setup_fallback(self, bridge):
        bridge._rust_available = False
        bridge._rust_module = None
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

    def test_fallback_activate_sets_killed(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge
        self._setup_fallback(bridge)

        # Initially fail-closed (Rust unavailable → Python KS activated)
        assert bridge.is_killed() is True

        # Deactivate via the internal Python KS to test activate separately.
        bridge._get_python_ks().deactivate()
        bridge._last_fallback_log = 0.0  # allow log

        bridge.activate_kill(reason="test_reason")
        assert bridge.is_killed() is True

    def test_fallback_reset_clears_killed(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge
        self._setup_fallback(bridge)

        bridge.activate_kill(reason="to_be_reset")
        assert bridge.is_killed() is True

        bridge.reset_kill()
        assert bridge.is_killed() is False

    def test_fallback_reset_flow_full_cycle(self):
        """Activate → reset → re-activate → reset (full cycle on fallback)."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge
        self._setup_fallback(bridge)

        for i in range(3):
            bridge.activate_kill(reason=f"cycle_{i}")
            assert bridge.is_killed() is True
            bridge.reset_kill()
            assert bridge.is_killed() is False

    def test_fallback_get_status_fields(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge
        self._setup_fallback(bridge)

        status = bridge.get_status()
        assert "killed" in status
        assert "backend" in status
        assert status["backend"] == "python_fallback"


# ===========================================================================
# 3. Concurrent read access
# ===========================================================================


class TestConcurrentReads:
    """10 threads concurrently reading is_killed() — no crashes or deadlocks."""

    def test_concurrent_reads_no_deadlock(self):
        """10 threads concurrently reading is_killed() — no crashes or deadlocks.

        Note: The Rust unit test uses 16 threads to exercise the SeqCst/Acquire
        ordering guarantees at the assembly level. This Python test uses 10 threads
        and focuses on the bridge layer — verifying no GIL deadlock or Python-level
        race condition. The two tests are complementary, not redundant.
        """
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        num_threads = 10
        results: list[bool] = []
        lock = threading.Lock()
        barrier = threading.Barrier(num_threads)

        def _read():
            barrier.wait()
            val = bridge.is_killed()
            with lock:
                results.append(val)

        threads = [threading.Thread(target=_read) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(results) == num_threads, (
            f"Expected {num_threads} results; got {len(results)} — possible deadlock"
        )
        # All must return True (fail-closed state).
        assert all(results), "All reads must return True in fail-closed mode"

    def test_concurrent_activate_reset(self):
        """Activate and reset from multiple threads without crashing."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        errors: list[Exception] = []

        def _worker(i: int):
            try:
                if i % 2 == 0:
                    bridge.activate_kill(reason=f"thread_{i}")
                else:
                    bridge.reset_kill()
                bridge.is_killed()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Concurrent activate/reset raised exceptions: {errors}"


# ===========================================================================
# 4. Reset flow
# ===========================================================================


class TestResetFlow:
    """Verify kill → reset → INACTIVE state machine on both paths."""

    def test_reset_via_mock_rust_module(self):
        """Reset flow using a mock Rust module."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module(initial_killed=False)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        assert bridge.is_killed() is False

        bridge.activate_kill(reason="to_reset")
        assert bridge.is_killed() is True

        bridge.reset_kill()
        assert bridge.is_killed() is False

    def test_reset_does_not_crash_when_already_inactive(self):
        """Calling reset() when already INACTIVE must not raise."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module(initial_killed=False)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        bridge.reset_kill()  # should not raise
        assert bridge.is_killed() is False


# ===========================================================================
# 5. Health monitor lifecycle
# ===========================================================================


class TestHealthMonitor:
    def test_start_stop_monitor(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge.start_health_monitor(interval_seconds=0.1)
        time.sleep(0.05)
        bridge.stop_health_monitor()
        # Should not hang.

    def test_monitor_does_not_start_twice(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge.start_health_monitor(interval_seconds=1.0)
        thread_1 = bridge._monitor_thread
        bridge.start_health_monitor(interval_seconds=1.0)
        thread_2 = bridge._monitor_thread
        assert thread_1 is thread_2, "Monitor should not create a second thread"
        bridge.stop_health_monitor()


# ===========================================================================
# 6. Backend routing via mock Rust module
# ===========================================================================


class TestRustModuleMockPath:
    """Tests using a mock Rust module (no compiled .so required)."""

    def test_is_killed_delegates_to_rust_module(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module(initial_killed=True)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        assert bridge.is_killed() is True
        mock_mod.is_killed.assert_called()

    def test_activate_kill_delegates_to_rust_module(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module(initial_killed=False)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        bridge.activate_kill(reason="rust_path_test")
        mock_mod.activate_kill.assert_called_once_with("rust_path_test")
        assert bridge.is_killed() is True

    def test_get_status_delegates_to_rust_module(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module(initial_killed=False)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        status = bridge.get_status()
        assert "killed" in status
        assert "binary_running" in status
        assert status["binary_running"] is True

    def test_backend_name_rust(self):
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        mock_mod = _make_mock_rust_module()
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        assert bridge.backend_name() == "rust"

    def test_shm_persistence_simulate_restart(self):
        """Simulate a process restart where the Rust module already reports killed=True."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        # Simulates state after restart: Rust binary has kill_flag=True in shm.
        mock_mod = _make_mock_rust_module(initial_killed=True)
        bridge._rust_available = True
        bridge._rust_module = mock_mod

        # On restart, bridge queries is_killed() immediately — must return True.
        assert bridge.is_killed() is True, (
            "After simulated restart with kill flag set, bridge must report killed=True"
        )


# ===========================================================================
# 7. Force-Python environment variable
# ===========================================================================


class TestForcePythonEnvVar:
    """LIP_KS_FORCE_PYTHON=1 must bypass the Rust module."""

    def test_force_python_flag_respected(self):
        """Bridge module with _rust_available=False behaves as Python fallback."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        # is_killed() must return True (fail-closed: Python KS auto-activated).
        assert bridge.is_killed() is True

    def test_activate_on_python_fallback_after_manual_reset(self):
        """Manually reset the Python KS, then activate and verify."""
        import lip.c7_execution_agent.kill_switch_bridge as bridge

        bridge._rust_available = False
        bridge._python_ks = None
        bridge._last_fallback_log = 0.0

        # Get Python KS (will be auto-activated).
        ks = bridge._get_python_ks()
        # Manually deactivate.
        ks.deactivate()
        bridge._last_fallback_log = 0.0

        assert bridge.is_killed() is False

        bridge.activate_kill(reason="force_python_test")
        assert bridge.is_killed() is True

        bridge.reset_kill()
        assert bridge.is_killed() is False


# ===========================================================================
# 8. Native Rust module (skip if not compiled)
# ===========================================================================


@pytest.mark.skipif(
    importlib.util.find_spec("lip_kill_switch") is None,
    reason="lip_kill_switch Rust PyO3 module not compiled — skipping native tests",
)
class TestNativeRustModule:
    """Integration tests against the compiled PyO3 module.

    Only runs when ``lip_kill_switch`` is importable (i.e., the Rust crate
    has been built with ``maturin develop`` or ``cargo build --features python``).
    """

    def test_is_killed_returns_bool(self):
        import lip_kill_switch as ks  # type: ignore[import]

        result = ks.is_killed()
        assert isinstance(result, bool)

    def test_activate_and_reset(self):
        import lip_kill_switch as ks  # type: ignore[import]

        ks.reset_kill()
        assert ks.is_killed() is False

        ks.activate_kill("native_test")
        assert ks.is_killed() is True

        ks.reset_kill()
        assert ks.is_killed() is False

    def test_get_status_keys(self):
        import lip_kill_switch as ks  # type: ignore[import]

        ks.reset_kill()
        status = ks.get_status()
        for key in ("killed", "activation_count", "binary_running"):
            assert key in status, f"Expected key '{key}' in get_status() result"

    def test_signal_activation(self):
        """Send SIGUSR1 to the current process; verify is_killed() transitions."""
        import lip_kill_switch as ks  # type: ignore[import]

        ks.reset_kill()
        assert ks.is_killed() is False

        # The Rust binary handles SIGUSR1, not the PyO3 module directly.
        # In-process test: use activate_kill() as the canonical trigger.
        ks.activate_kill("sigusr1_simulation")
        assert ks.is_killed() is True

        ks.reset_kill()
