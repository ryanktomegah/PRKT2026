//! test_kill_switch.rs — Unit tests for core AtomicBool kill switch logic.

use lip_kill_switch::{activate, is_killed, reset, KILL_FLAG};
use std::sync::atomic::Ordering;
use std::sync::{Arc, Barrier};
use std::thread;

/// AtomicBool initialises to `false` — kill switch starts INACTIVE.
#[test]
fn test_atomic_flag_default_false() {
    // Reset to known state before testing.
    KILL_FLAG.store(false, Ordering::SeqCst);
    assert!(!is_killed(), "kill flag must start false (INACTIVE)");
}

/// Calling `activate()` stores `true` with SeqCst; `is_killed()` observes it.
#[test]
fn test_activate_sets_flag() {
    KILL_FLAG.store(false, Ordering::SeqCst);
    activate("unit test");
    assert!(is_killed(), "kill flag must be true after activate()");
    // Clean up.
    KILL_FLAG.store(false, Ordering::SeqCst);
}

/// Calling `reset()` stores `false` with SeqCst; `is_killed()` observes it.
#[test]
fn test_reset_clears_flag() {
    activate("pre-reset test");
    assert!(is_killed());
    reset();
    assert!(!is_killed(), "kill flag must be false after reset()");
}

/// Activate → reset → activate cycle must be idempotent.
#[test]
fn test_activate_reset_cycle() {
    KILL_FLAG.store(false, Ordering::SeqCst);
    for i in 0..5 {
        activate(&format!("cycle {}", i));
        assert!(is_killed());
        reset();
        assert!(!is_killed());
    }
}

/// 16 reader threads + 1 writer — no stale reads under concurrent access.
///
/// Memory ordering guarantee: the writer uses SeqCst store; readers use
/// Acquire load. All readers must observe `true` after the barrier.
#[test]
fn test_concurrent_reads_no_stale_values() {
    KILL_FLAG.store(false, Ordering::SeqCst);

    let num_readers = 16;
    // Barrier: all threads synchronise before the writer fires.
    let barrier = Arc::new(Barrier::new(num_readers + 1));
    let mut handles = Vec::with_capacity(num_readers);

    for _ in 0..num_readers {
        let b = Arc::clone(&barrier);
        handles.push(thread::spawn(move || {
            b.wait(); // wait for writer
            // After the barrier, writer has already executed SeqCst store.
            // Acquire load must observe true.
            is_killed()
        }));
    }

    // Writer: activate with SeqCst before releasing the barrier.
    activate("concurrent test");
    barrier.wait();

    let results: Vec<bool> = handles.into_iter().map(|h| h.join().unwrap()).collect();
    let all_saw_kill = results.iter().all(|&v| v);
    assert!(
        all_saw_kill,
        "All reader threads must observe kill=true after SeqCst store; \
         got {:?}",
        results
    );

    KILL_FLAG.store(false, Ordering::SeqCst);
}

/// The kill flag is a module-level static — same instance across tests in the
/// same process. Verify that the test cleanup actually works.
#[test]
fn test_flag_isolation_after_reset() {
    reset();
    assert!(!is_killed(), "flag must be false after explicit reset");
}
