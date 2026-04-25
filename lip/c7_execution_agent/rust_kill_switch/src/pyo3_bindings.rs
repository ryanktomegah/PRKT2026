//! pyo3_bindings.rs — PyO3 Python module exposing the kill switch.
//!
//! Exposes:
//!   `is_killed() -> bool`
//!   `activate_kill(reason: str)`
//!   `reset_kill()`
//!   `get_status() -> dict`
//!
//! All functions release the GIL during atomic operations so that concurrent
//! Python threads (asyncio event loop + KMS monitor) do not block each other.

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Return `True` when the kill switch is active (all new offers must halt).
///
/// Reads the `AtomicBool` with `Ordering::Acquire` — see `lib.rs` for the
/// full memory ordering rationale.
#[pyfunction]
fn is_killed(py: Python<'_>) -> bool {
    // Release GIL during the atomic load so asyncio threads don't contend.
    py.allow_threads(|| crate::is_killed())
}

/// Activate the kill switch.
///
/// Writes `true` to the `AtomicBool` with `Ordering::SeqCst` and persists
/// the state to `/dev/shm/lip_kill_switch`. Safe to call from operator
/// command path without signal delivery.
#[pyfunction]
#[pyo3(signature = (reason = ""))]
fn activate_kill(py: Python<'_>, reason: &str) -> PyResult<()> {
    py.allow_threads(|| crate::activate(reason));
    Ok(())
}

/// Reset the kill switch to INACTIVE and resume normal offer processing.
///
/// Writes `false` to the `AtomicBool` with `Ordering::SeqCst` and clears
/// the shared memory segment.
#[pyfunction]
fn reset_kill(py: Python<'_>) -> PyResult<()> {
    py.allow_threads(|| crate::reset());
    Ok(())
}

/// Return a dict snapshot of kill switch status.
///
/// Keys:
///   ``killed`` (bool), ``activated_at_unix_ms`` (int | None),
///   ``reason`` (str | None), ``activation_count`` (int),
///   ``binary_running`` (bool).
#[pyfunction]
fn get_status(py: Python<'_>) -> PyResult<PyObject> {
    let status = py.allow_threads(|| crate::KillSwitchStatus::read());

    let dict = PyDict::new(py);
    dict.set_item("killed", status.killed)?;
    dict.set_item(
        "activated_at_unix_ms",
        status.activated_at_unix_ms.map(|v| v as i64),
    )?;
    dict.set_item("reason", status.reason)?;
    dict.set_item("activation_count", status.activation_count)?;
    dict.set_item("binary_running", status.binary_running)?;

    Ok(dict.into())
}

/// Register the PyO3 module `lip_kill_switch`.
#[pymodule]
fn lip_kill_switch(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(is_killed, m)?)?;
    m.add_function(wrap_pyfunction!(activate_kill, m)?)?;
    m.add_function(wrap_pyfunction!(reset_kill, m)?)?;
    m.add_function(wrap_pyfunction!(get_status, m)?)?;
    Ok(())
}
