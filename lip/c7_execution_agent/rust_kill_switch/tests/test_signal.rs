//! test_signal.rs — Signal handler integration tests.
//!
//! Sends real Unix signals to the current process and verifies the
//! AtomicBool flags are set correctly.
//!
//! Note: these tests are inherently sequential and must not run in parallel
//! with tests that modify KILL_FLAG (use `cargo test -- --test-threads=1`
//! or isolate in a separate binary).

use lip_kill_switch::signal::SignalFlags;
use lip_kill_switch::{is_killed, reset, KILL_FLAG};
use std::sync::atomic::Ordering;
use std::thread;
use std::time::Duration;

/// Send SIGUSR1 to self → `kill_requested` flag set within 50ms.
///
/// Note: 50ms is a deliberately conservative CI timeout to allow for OS
/// scheduler jitter. The actual signal delivery latency is typically < 1ms;
/// the kill switch activation budget (spec Appendix B) is ≤ 1ms.
/// This test verifies correctness, not operational latency.
#[test]
fn test_sigusr1_sets_kill_requested_flag() {
    let flags = SignalFlags::register().expect("register signal handlers");

    // Ensure clean state.
    flags
        .kill_requested
        .store(false, Ordering::SeqCst);
    KILL_FLAG.store(false, Ordering::SeqCst);

    // Send SIGUSR1 to self.
    unsafe { libc::kill(libc::getpid(), libc::SIGUSR1) };

    // Poll for the flag to be set (signal may be delivered asynchronously).
    let deadline = std::time::Instant::now() + Duration::from_millis(50);
    let mut seen = false;
    while std::time::Instant::now() < deadline {
        if flags.kill_requested.load(Ordering::Acquire) {
            seen = true;
            break;
        }
        thread::sleep(Duration::from_millis(1));
    }

    assert!(
        seen,
        "SIGUSR1 must set kill_requested within 50ms"
    );

    // Simulate what the main loop does: consume the flag and activate.
    flags.kill_requested.store(false, Ordering::SeqCst);
    lip_kill_switch::activate("SIGUSR1 test");
    assert!(is_killed(), "kill flag must be set after simulated SIGUSR1 handling");

    reset();
}

/// Send SIGTERM to self → `shutdown_requested` flag set within 50ms.
///
/// The 50ms timeout is a conservative CI margin for scheduler jitter;
/// actual signal delivery is typically sub-millisecond.
#[test]
fn test_sigterm_sets_shutdown_requested_flag() {
    let flags = SignalFlags::register().expect("register signal handlers");
    flags.shutdown_requested.store(false, Ordering::SeqCst);

    unsafe { libc::kill(libc::getpid(), libc::SIGTERM) };

    let deadline = std::time::Instant::now() + Duration::from_millis(50);
    let mut seen = false;
    while std::time::Instant::now() < deadline {
        if flags.shutdown_requested.load(Ordering::Acquire) {
            seen = true;
            break;
        }
        thread::sleep(Duration::from_millis(1));
    }

    assert!(seen, "SIGTERM must set shutdown_requested within 50ms");
    flags.shutdown_requested.store(false, Ordering::SeqCst);
}

/// Send SIGHUP to self → `reset_requested` flag set within 50ms.
///
/// The 50ms timeout is a conservative CI margin for scheduler jitter;
/// actual signal delivery is typically sub-millisecond.
#[test]
fn test_sighup_sets_reset_requested_flag() {
    let flags = SignalFlags::register().expect("register signal handlers");
    flags.reset_requested.store(false, Ordering::SeqCst);

    // First activate so there is something to reset.
    KILL_FLAG.store(true, Ordering::SeqCst);

    unsafe { libc::kill(libc::getpid(), libc::SIGHUP) };

    let deadline = std::time::Instant::now() + Duration::from_millis(50);
    let mut seen = false;
    while std::time::Instant::now() < deadline {
        if flags.reset_requested.load(Ordering::Acquire) {
            seen = true;
            break;
        }
        thread::sleep(Duration::from_millis(1));
    }

    assert!(seen, "SIGHUP must set reset_requested within 50ms");

    // Simulate main loop consuming the flag and resetting.
    flags.reset_requested.store(false, Ordering::SeqCst);
    reset();
    assert!(!is_killed(), "kill flag must be false after simulated SIGHUP reset");
}
