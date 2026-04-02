//! signal.rs — Linux signal handler registration.
//!
//! Registers async-signal-safe handlers using `signal_hook::flag::register`,
//! which atomically sets an `AtomicBool` — the only operation that is
//! unconditionally async-signal-safe. No malloc, mutex, or I/O inside handlers.
//!
//! Signal assignments:
//!   SIGUSR1 — activate kill switch
//!   SIGHUP  — reset kill switch
//!   SIGTERM — graceful shutdown of the Rust binary
//!
//! The main loop polls these flags and performs state transitions (logging,
//! shm updates) from non-signal context.

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use signal_hook::consts::{SIGHUP, SIGTERM, SIGUSR1};
use signal_hook::flag as signal_flag;

/// Signal flags polled by the main loop.
pub struct SignalFlags {
    /// Set by SIGUSR1 — main loop calls `crate::activate()` then clears.
    pub kill_requested: Arc<AtomicBool>,
    /// Set by SIGHUP — main loop calls `crate::reset()` then clears.
    pub reset_requested: Arc<AtomicBool>,
    /// Set by SIGTERM — main loop initiates graceful shutdown.
    pub shutdown_requested: Arc<AtomicBool>,
}

impl SignalFlags {
    /// Register OS signal handlers and return the flag set.
    ///
    /// # Safety
    ///
    /// `signal_hook::flag::register` is async-signal-safe — it only writes
    /// to an `AtomicBool` inside the handler. No unsafe code is required
    /// in this crate; safety is encapsulated by `signal_hook`.
    pub fn register() -> std::io::Result<Self> {
        let kill_requested = Arc::new(AtomicBool::new(false));
        let reset_requested = Arc::new(AtomicBool::new(false));
        let shutdown_requested = Arc::new(AtomicBool::new(false));

        // SIGUSR1: activate kill switch
        signal_flag::register(SIGUSR1, Arc::clone(&kill_requested))?;

        // SIGHUP: reset kill switch
        signal_flag::register(SIGHUP, Arc::clone(&reset_requested))?;

        // SIGTERM: graceful shutdown
        signal_flag::register(SIGTERM, Arc::clone(&shutdown_requested))?;

        Ok(SignalFlags {
            kill_requested,
            reset_requested,
            shutdown_requested,
        })
    }
}
