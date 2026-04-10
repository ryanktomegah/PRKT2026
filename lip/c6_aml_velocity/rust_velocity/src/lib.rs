//! lip_c6_rust_velocity — C6 AML velocity counters and sanctions screening
//!
//! Exposed to Python via PyO3. Two components:
//!   - [`velocity`]: DashMap-backed rolling 24-hour window counters with Rust atomics.
//!   - [`sanctions`]: Aho-Corasick + Jaccard token-overlap sanctions screener.
//!
//! Python callers import the wheel via `import lip_c6_rust_velocity` and fall back
//! to the pure-Python implementation when the wheel is unavailable (see
//! `velocity_bridge.py` and `sanctions_bridge.py`).
//!
//! Build with maturin:
//!   cd lip/c6_aml_velocity/rust_velocity && maturin develop
//!
//! See docs/specs/c6_velocity_sanctions_migration.md for full design rationale.

pub mod sanctions;
pub mod velocity;

use pyo3::prelude::*;

/// LIP C6 AML Velocity & Sanctions — Rust-backed core.
///
/// Exports:
///   PyRollingVelocity   — rolling 24h velocity window (DashMap + atomics)
///   PySanctionsScreener — OFAC/EU/UN sanctions screener (Aho-Corasick + Jaccard)
///   health_check()      — returns dict with build metadata
#[pymodule]
fn lip_c6_rust_velocity(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Velocity counters
    m.add_class::<velocity::PyRollingVelocity>()?;

    // Sanctions screener
    m.add_class::<sanctions::PySanctionsScreener>()?;

    // Module version and health check
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(health_check, m)?)?;

    Ok(())
}

/// Return a dict with build metadata for health checks / Prometheus.
#[pyfunction]
fn health_check(py: Python<'_>) -> PyResult<PyObject> {
    let d = pyo3::types::PyDict::new(py);
    d.set_item("ok", true)?;
    d.set_item("version", env!("CARGO_PKG_VERSION"))?;
    d.set_item("backend", "lip_c6_rust_velocity")?;
    Ok(d.into())
}
