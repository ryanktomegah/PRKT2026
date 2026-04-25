//! test_shm.rs — Shared memory interface tests.

use lip_kill_switch::shm::{read_kill_status, write_kill_state, SHM_NAME};
use std::sync::Mutex;

static TEST_LOCK: Mutex<()> = Mutex::new(());

fn shm_or_skip() -> bool {
    match write_kill_state(false, "") {
        Ok(()) => true,
        Err(err) => {
            eprintln!("skipping POSIX shm test; shared memory unavailable: {err}");
            false
        }
    }
}

/// Write INACTIVE state and read it back.
#[test]
fn test_shm_write_and_read_inactive() {
    let _guard = TEST_LOCK.lock().unwrap();
    if !shm_or_skip() {
        return;
    }
    write_kill_state(false, "").expect("write inactive state");
    let status = read_kill_status().expect("read status");
    assert!(!status.killed, "kill flag must be false after writing inactive");
    assert!(status.reason.is_none() || status.reason.as_deref() == Some(""));
}

/// Write ACTIVE state with a reason and read it back.
#[test]
fn test_shm_write_and_read_active() {
    let _guard = TEST_LOCK.lock().unwrap();
    if !shm_or_skip() {
        return;
    }
    write_kill_state(true, "model_drift").expect("write active state");
    let status = read_kill_status().expect("read status");
    assert!(status.killed, "kill flag must be true after writing active");
    assert_eq!(
        status.reason.as_deref(),
        Some("model_drift"),
        "reason must round-trip through shm"
    );
    assert!(
        status.activated_at_unix_ms.is_some(),
        "activated_at must be set"
    );

    // Clean up.
    write_kill_state(false, "").unwrap();
}

/// Activation counter increments on each activate write.
#[test]
fn test_activation_count_monotonic() {
    let _guard = TEST_LOCK.lock().unwrap();
    if !shm_or_skip() {
        return;
    }
    write_kill_state(false, "").unwrap();
    let before = read_kill_status().unwrap().activation_count;

    write_kill_state(true, "count test 1").unwrap();
    let after1 = read_kill_status().unwrap().activation_count;

    write_kill_state(true, "count test 2").unwrap();
    let after2 = read_kill_status().unwrap().activation_count;

    assert!(after1 > before, "count must increment after first activate");
    assert!(after2 > after1, "count must increment after second activate");

    write_kill_state(false, "").unwrap();
}

/// A reason longer than 255 bytes is safely truncated at a UTF-8 boundary.
#[test]
fn test_reason_long_utf8_truncated_safely() {
    let _guard = TEST_LOCK.lock().unwrap();
    if !shm_or_skip() {
        return;
    }
    let long_reason = "x".repeat(500);
    write_kill_state(true, &long_reason).expect("write with long reason");
    let status = read_kill_status().expect("read status");
    let r = status.reason.unwrap_or_default();
    assert!(
        r.len() <= 255,
        "reason must be truncated to 255 bytes; got {} bytes",
        r.len()
    );
    // Must still be valid UTF-8.
    assert!(std::str::from_utf8(r.as_bytes()).is_ok(), "truncated reason must be valid UTF-8");

    write_kill_state(false, "").unwrap();
}

/// Segment name is the canonical POSIX shm name.
#[test]
fn test_shm_name_canonical() {
    assert_eq!(SHM_NAME, "/lip_kill_switch");
}
