//! lib.rs — Core kill switch logic.
//!
//! # Memory Ordering Guarantees
//!
//! The kill flag uses two different orderings intentionally:
//!
//! - **Write side** (`activate`, `reset`): `Ordering::SeqCst`
//!   Establishes a total sequential order visible to ALL threads and ALL CPU
//!   cores. Required for a kill switch because:
//!   (a) On weakly-ordered architectures (ARM Neoverse, Apple M-series), a
//!       plain `Release` store can be reordered by the CPU before reaching the
//!       L1 cache of a reader on another core.
//!   (b) `SeqCst` inserts a full memory barrier (MFENCE on x86, DMB ISH on
//!       ARM) ensuring the write is globally visible before any subsequent
//!       instruction on *any* thread can execute.
//!   Cost: ~5 ns — negligible vs. the ≤ 1 ms activation budget.
//!
//! - **Read side** (`is_killed`): `Ordering::Acquire`
//!   Sufficient to observe a `SeqCst` store reliably. On x86 this compiles
//!   to a plain MOV (all x86 loads are acquire-ordered by hardware). On ARM
//!   it compiles to LDAR (load-acquire). Using `SeqCst` on reads would add
//!   an unnecessary MFENCE in the hot path on ARM.
//!
//!   `Relaxed` would be INCORRECT here: it cannot observe the happens-before
//!   edge established by the `SeqCst` store on the write side.

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

pub mod shm;
pub mod signal;

#[cfg(feature = "python")]
pub mod pyo3_bindings;

/// The kill flag. Initialised to `false` (INACTIVE).
/// Declared as a module-level static so signal handlers can reach it
/// without any pointer indirection.
pub static KILL_FLAG: AtomicBool = AtomicBool::new(false);

/// Graceful-shutdown flag, set by SIGTERM handler.
pub static SHUTDOWN_FLAG: AtomicBool = AtomicBool::new(false);

/// Activate the kill switch.
///
/// Uses `Ordering::SeqCst` — see module-level documentation for rationale.
/// All new loan offers must be rejected after this call returns.
pub fn activate(reason: &str) {
    // SeqCst write: globally visible across all CPUs before any subsequent
    // Acquire load on any thread can return true.
    KILL_FLAG.store(true, Ordering::SeqCst);

    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);

    log::error!(
        "KILL SWITCH ACTIVATED ts_ms={} reason=\"{}\"",
        ts,
        reason
    );

    // Persist to shared memory so sibling processes observe the state.
    if let Err(e) = shm::write_kill_state(true, reason) {
        log::error!("shm write failed on activate: {}", e);
    }
}

/// Reset the kill switch to INACTIVE.
///
/// Uses `Ordering::SeqCst` — symmetric with `activate` to ensure the reset
/// is globally ordered and cannot be reordered before any in-flight read.
pub fn reset() {
    // SeqCst write: prevents the CPU from reordering this store before any
    // preceding instruction, and forces all prior stores to be flushed.
    KILL_FLAG.store(false, Ordering::SeqCst);
    log::warn!("Kill switch RESET — resuming normal offer processing");

    if let Err(e) = shm::write_kill_state(false, "") {
        log::error!("shm write failed on reset: {}", e);
    }
}

/// Query the kill flag.
///
/// Uses `Ordering::Acquire` — see module-level documentation for rationale.
/// Returns `true` when the kill switch is active and all new offers must halt.
///
/// # Fail-closed default
///
/// If the shared memory segment is unavailable (Rust binary not running,
/// `/dev/shm` full, etc.) the Python bridge returns `true` (KILLED). This
/// function reflects only the in-process atomic flag; the fail-closed logic
/// lives in `kill_switch_bridge.py`.
pub fn is_killed() -> bool {
    // Acquire load: sufficient to observe the SeqCst store from activate().
    KILL_FLAG.load(Ordering::Acquire)
}

/// Point-in-time status snapshot.
#[derive(Debug, Clone)]
pub struct KillSwitchStatus {
    pub killed: bool,
    pub activated_at_unix_ms: Option<u64>,
    pub reason: Option<String>,
    pub activation_count: u64,
    pub binary_running: bool,
}

impl KillSwitchStatus {
    /// Read status from shared memory, falling back to in-process flag.
    pub fn read() -> Self {
        match shm::read_kill_status() {
            Ok(s) => s,
            Err(_) => KillSwitchStatus {
                killed: is_killed(),
                activated_at_unix_ms: None,
                reason: None,
                activation_count: 0,
                binary_running: true,
            },
        }
    }
}
