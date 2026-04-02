/// lib.rs — lip_c3_rust_state_machine PyO3 module entrypoint
///
/// Rust crate exposing C3 repayment engine state machine core to Python
/// via PyO3. Architecture Spec v1.2 Sections S6, S7, S8.
///
/// Build with maturin:
///   cd lip/c3/rust_state_machine && maturin develop
///
/// See docs/specs/c3_state_machine_migration.md for full interface contract.
pub mod iso20022;
pub mod pyo3_bindings;
pub mod state_machine;
pub mod taxonomy;

use pyo3::prelude::*;

/// LIP C3 Repayment Engine — Rust-backed state machine core.
///
/// Exports:
///   PaymentStateMachine — payment lifecycle state machine
///   classify_rejection_code(code) -> str
///   maturity_days_for_class(rejection_class) -> int
///   is_block_code(code) -> bool
///   extract_camt054_fields(raw_message) -> dict
///   extract_pacs008_fields(raw_message) -> dict
#[pymodule]
fn lip_c3_rust_state_machine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    pyo3_bindings::register(m)?;
    // Module version string for runtime introspection
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
