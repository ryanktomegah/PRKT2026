//! main.rs — Standalone kill switch binary entry point.
//!
//! Runs the signal handler loop. On SIGUSR1: activate. On SIGHUP: reset.
//! On SIGTERM: graceful shutdown (leaving kill flag in place).

use std::sync::atomic::Ordering;
use std::thread;
use std::time::Duration;

use lip_kill_switch::signal::SignalFlags;
use lip_kill_switch::{KILL_FLAG, SHUTDOWN_FLAG};

fn main() {
    env_logger::init();

    log::info!("lip_kill_switch binary starting — initialising signal handlers");

    let flags = SignalFlags::register().expect("Failed to register signal handlers");

    // Initialise shared memory segment.
    if let Err(e) = lip_kill_switch::shm::write_kill_state(false, "") {
        log::error!("Failed to initialise shm: {} — continuing without shm", e);
    }

    log::info!(
        "lip_kill_switch ready — SIGUSR1=activate SIGHUP=reset SIGTERM=shutdown"
    );

    // Main loop: poll signal flags every 10ms.
    loop {
        if flags
            .shutdown_requested
            .compare_exchange(true, false, Ordering::SeqCst, Ordering::Acquire)
            .is_ok()
        {
            SHUTDOWN_FLAG.store(true, Ordering::SeqCst);
            log::info!("SIGTERM received — shutting down gracefully (kill flag preserved)");
            break;
        }

        if flags
            .kill_requested
            .compare_exchange(true, false, Ordering::SeqCst, Ordering::Acquire)
            .is_ok()
        {
            lip_kill_switch::activate("SIGUSR1");
            log::error!("Kill switch ACTIVATED via SIGUSR1");
        }

        if flags
            .reset_requested
            .compare_exchange(true, false, Ordering::SeqCst, Ordering::Acquire)
            .is_ok()
        {
            lip_kill_switch::reset();
            log::warn!("Kill switch RESET via SIGHUP");
        }

        thread::sleep(Duration::from_millis(10));
    }

    let killed = KILL_FLAG.load(Ordering::Acquire);
    log::info!("lip_kill_switch exiting — kill_flag={}", killed);
}
