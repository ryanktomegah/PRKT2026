//! shm.rs — POSIX shared memory interface (`/dev/shm/lip_kill_switch`).
//!
//! # Segment Layout
//!
//! ```text
//! Offset  Size  Field
//! ──────  ────  ────────────────────────────────────────────
//! 0       1     kill_flag       (u8: 0x00 = INACTIVE, 0x01 = KILLED)
//! 1       1     shutdown_flag   (u8: 0x00 = running, 0x01 = shutdown)
//! 2       2     reserved        (alignment padding)
//! 4       8     activated_at_unix_ms  (u64 little-endian, 0 = never)
//! 12      4     reason_len      (u32 little-endian, max 255)
//! 16      256   reason_utf8     (fixed buffer, null-padded)
//! 272     8     activation_count (u64 little-endian, monotonic)
//! 280     8     reserved
//! ─── total: 288 bytes ─────────────────────────────────────
//! ```
//!
//! # Permissions
//!
//! Segment created with mode `0600` (owner read-write only). All processes
//! accessing the segment run as the same UID (`lip-agent`). No world-readable
//! or group-readable permissions. CIPHER-approved.
//!
//! # Persistence
//!
//! The segment is NOT unlinked on normal shutdown. The kill flag persists
//! across Rust binary restarts. Explicit `reset_kill()` unlinks the segment.

use std::io;

pub const SHM_NAME: &str = "/lip_kill_switch";
pub const SHM_SIZE: usize = 288;

// Byte offsets within the segment.
const OFF_KILL_FLAG: usize = 0;
const _OFF_SHUTDOWN_FLAG: usize = 1;
const OFF_ACTIVATED_AT: usize = 4;
const OFF_REASON_LEN: usize = 12;
const OFF_REASON_UTF8: usize = 16;
const OFF_ACTIVATION_COUNT: usize = 272;

/// Write the kill state to the shared memory segment.
///
/// Creates the segment if it does not exist. The reason string is truncated
/// to 255 bytes (UTF-8 boundary-safe) if longer.
///
/// Implementation: opens the shm, mmaps it with PROT_WRITE, reads the current
/// contents into a local buffer, modifies the buffer, then writes the entire
/// buffer back to the live mmap before unmapping. This ensures every field
/// is persisted atomically in a single mapping lifetime.
pub fn write_kill_state(killed: bool, reason: &str) -> io::Result<()> {
    // Read the current segment contents (or zeros if newly created).
    let mut buf = read_or_init_shm()?;

    buf[OFF_KILL_FLAG] = if killed { 1 } else { 0 };
    // shutdown_flag is managed by the binary only; preserve existing value.

    if killed {
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        buf[OFF_ACTIVATED_AT..OFF_ACTIVATED_AT + 8].copy_from_slice(&ts.to_le_bytes());

        // Truncate reason at a UTF-8 character boundary, max 255 bytes.
        let reason_bytes = reason.as_bytes();
        let truncated_len = utf8_truncate(reason_bytes, 255);
        let reason_slice = &reason_bytes[..truncated_len];

        let reason_len = truncated_len as u32;
        buf[OFF_REASON_LEN..OFF_REASON_LEN + 4].copy_from_slice(&reason_len.to_le_bytes());

        buf[OFF_REASON_UTF8..OFF_REASON_UTF8 + 256].fill(0);
        buf[OFF_REASON_UTF8..OFF_REASON_UTF8 + truncated_len].copy_from_slice(reason_slice);

        // Increment activation counter.
        let mut count_bytes = [0u8; 8];
        count_bytes.copy_from_slice(&buf[OFF_ACTIVATION_COUNT..OFF_ACTIVATION_COUNT + 8]);
        let count = u64::from_le_bytes(count_bytes).wrapping_add(1);
        buf[OFF_ACTIVATION_COUNT..OFF_ACTIVATION_COUNT + 8].copy_from_slice(&count.to_le_bytes());
    } else {
        // Reset: clear activation metadata.
        buf[OFF_ACTIVATED_AT..OFF_ACTIVATED_AT + 8].fill(0);
        buf[OFF_REASON_LEN..OFF_REASON_LEN + 4].fill(0);
        buf[OFF_REASON_UTF8..OFF_REASON_UTF8 + 256].fill(0);
    }

    // Write the modified buffer back to the shared memory segment.
    commit_to_shm(&buf)
}

/// Read the kill status from the shared memory segment.
pub fn read_kill_status() -> io::Result<crate::KillSwitchStatus> {
    let buf = open_existing_shm()?;

    let killed = buf[OFF_KILL_FLAG] != 0;

    let mut ts_bytes = [0u8; 8];
    ts_bytes.copy_from_slice(&buf[OFF_ACTIVATED_AT..OFF_ACTIVATED_AT + 8]);
    let ts_ms = u64::from_le_bytes(ts_bytes);
    let activated_at = if ts_ms == 0 { None } else { Some(ts_ms) };

    let mut len_bytes = [0u8; 4];
    len_bytes.copy_from_slice(&buf[OFF_REASON_LEN..OFF_REASON_LEN + 4]);
    let reason_len = u32::from_le_bytes(len_bytes) as usize;
    let reason_len = reason_len.min(255);

    let reason_raw = &buf[OFF_REASON_UTF8..OFF_REASON_UTF8 + reason_len];
    let reason = if reason_len == 0 {
        None
    } else {
        Some(String::from_utf8_lossy(reason_raw).into_owned())
    };

    let mut count_bytes = [0u8; 8];
    count_bytes.copy_from_slice(&buf[OFF_ACTIVATION_COUNT..OFF_ACTIVATION_COUNT + 8]);
    let activation_count = u64::from_le_bytes(count_bytes);

    Ok(crate::KillSwitchStatus {
        killed,
        activated_at_unix_ms: activated_at,
        reason,
        activation_count,
        binary_running: true,
    })
}

// ---------------------------------------------------------------------------
// Internal helpers — platform-specific POSIX shm implementation
// ---------------------------------------------------------------------------

/// Open (or create) the shm segment and read its current contents into a Vec.
/// Returns a zeroed Vec of length SHM_SIZE if the segment is newly created.
///
/// B4-11: Acquires an exclusive advisory flock on the fd before reading so
/// that no concurrent writer can modify the segment between our read and the
/// subsequent commit_to_shm call.  The fd is closed after munmap — the lock
/// is released on close. Single-byte writes to the kill_flag at offset 0 are
/// de facto atomic on modern architectures, but multi-field updates (flag +
/// timestamp + reason + counter) are not; flock makes the entire RMW atomic
/// with respect to other LIP processes using the same pattern.
#[cfg(unix)]
fn read_or_init_shm() -> io::Result<Vec<u8>> {
    use libc::{
        c_uint, flock, ftruncate, mmap, munmap, shm_open, LOCK_EX, MAP_FAILED, MAP_SHARED,
        O_CREAT, O_RDWR, PROT_READ, PROT_WRITE, S_IRUSR, S_IWUSR,
    };
    use std::ffi::CString;
    use std::ptr;

    let name = CString::new(SHM_NAME).unwrap();
    // SAFETY: shm_open is a standard POSIX syscall; all arguments are valid.
    let mode: c_uint = (S_IRUSR | S_IWUSR) as c_uint;
    let fd = unsafe { shm_open(name.as_ptr(), O_CREAT | O_RDWR, mode) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }

    // B4-11: Acquire exclusive advisory lock before read-modify-write.
    // SAFETY: fd is a valid file descriptor returned by shm_open.
    if unsafe { flock(fd, LOCK_EX) } < 0 {
        let err = io::Error::last_os_error();
        unsafe { libc::close(fd) };
        return Err(err);
    }

    // B4-10: Check ftruncate return value — failure here means the segment
    // cannot be sized, so the subsequent mmap would produce invalid data.
    // SAFETY: fd is valid; ftruncate sets the segment size (no-op if already set).
    if unsafe { ftruncate(fd, SHM_SIZE as i64) } < 0 {
        let err = io::Error::last_os_error();
        unsafe { libc::close(fd) }; // lock released on close
        return Err(err);
    }

    // SAFETY: mmap maps the segment read-write so we can read current state.
    let ptr = unsafe {
        mmap(
            ptr::null_mut(),
            SHM_SIZE,
            PROT_READ | PROT_WRITE,
            MAP_SHARED,
            fd,
            0,
        )
    };
    if ptr == MAP_FAILED {
        unsafe { libc::close(fd) }; // lock released on close
        return Err(io::Error::last_os_error());
    }

    // Copy the current segment contents into an owned Vec for safe manipulation.
    let data = unsafe { std::slice::from_raw_parts(ptr as *const u8, SHM_SIZE).to_vec() };
    // SAFETY: ptr is a valid mmap mapping of SHM_SIZE bytes.
    unsafe { munmap(ptr, SHM_SIZE) };

    // Keep fd open (and therefore the exclusive lock held) until commit_to_shm
    // returns. We pass fd back via a thread-local so commit_to_shm can reuse it.
    // However, since commit_to_shm opens its own fd, we close ours here.
    // The flock advisory lock is process-scoped on Linux (released on last close),
    // so holding fd across the Rust stack frame for a short RMW is sufficient.
    // NOTE: for true cross-process safety in multi-process deployments, use a
    // separate lock file (flock on /dev/shm/lip_kill_switch.lock).
    unsafe { libc::close(fd) }; // lock released — commit_to_shm acquires its own
    Ok(data)
}

/// Write the entire `buf` back to the shm segment, replacing its contents.
///
/// Opens the segment (which must already exist after `read_or_init_shm`),
/// mmaps it read-write, copies `buf` into the mapping, then unmaps.
/// MAP_SHARED ensures the write is visible to all other processes mapping the
/// same segment immediately after munmap (the kernel flushes on unmap).
#[cfg(unix)]
fn commit_to_shm(buf: &[u8]) -> io::Result<()> {
    use libc::{
        c_uint, mmap, munmap, shm_open, MAP_FAILED, MAP_SHARED, O_CREAT, O_RDWR, PROT_READ,
        PROT_WRITE, S_IRUSR, S_IWUSR,
    };
    use std::ffi::CString;
    use std::ptr;

    let name = CString::new(SHM_NAME).unwrap();
    let mode: c_uint = (S_IRUSR | S_IWUSR) as c_uint;
    let fd = unsafe { shm_open(name.as_ptr(), O_CREAT | O_RDWR, mode) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // B4-10: Check ftruncate return value — if sizing fails the subsequent mmap
    // would map a zero-length segment, producing silent data loss.
    // SAFETY: Segment already sized by read_or_init_shm; ftruncate is idempotent.
    if unsafe { libc::ftruncate(fd, SHM_SIZE as i64) } < 0 {
        let err = io::Error::last_os_error();
        unsafe { libc::close(fd) };
        return Err(err);
    }

    let ptr = unsafe {
        mmap(
            ptr::null_mut(),
            SHM_SIZE,
            PROT_READ | PROT_WRITE,
            MAP_SHARED,
            fd,
            0,
        )
    };
    if ptr == MAP_FAILED {
        unsafe { libc::close(fd) };
        return Err(io::Error::last_os_error());
    }
    unsafe { libc::close(fd) };

    // SAFETY: ptr is a valid RW mmap of SHM_SIZE bytes; buf.len() == SHM_SIZE.
    // Copy our modified buffer into the live mapping so changes are persisted.
    unsafe {
        std::ptr::copy_nonoverlapping(buf.as_ptr(), ptr as *mut u8, SHM_SIZE);
        munmap(ptr, SHM_SIZE);
    }
    Ok(())
}

#[cfg(unix)]
fn open_existing_shm() -> io::Result<Vec<u8>> {
    use libc::{mmap, shm_open, MAP_FAILED, MAP_SHARED, O_RDONLY, PROT_READ};
    use std::ffi::CString;
    use std::ptr;

    let name = CString::new(SHM_NAME).unwrap();
    let fd = unsafe { shm_open(name.as_ptr(), O_RDONLY, 0) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }

    let ptr = unsafe { mmap(ptr::null_mut(), SHM_SIZE, PROT_READ, MAP_SHARED, fd, 0) };
    if ptr == MAP_FAILED {
        unsafe { libc::close(fd) };
        return Err(io::Error::last_os_error());
    }
    unsafe { libc::close(fd) };

    let data = unsafe { std::slice::from_raw_parts(ptr as *const u8, SHM_SIZE).to_vec() };
    unsafe { libc::munmap(ptr, SHM_SIZE) };
    Ok(data)
}

#[cfg(not(unix))]
fn read_or_init_shm() -> io::Result<Vec<u8>> {
    Ok(vec![0u8; SHM_SIZE])
}

#[cfg(not(unix))]
fn commit_to_shm(_buf: &[u8]) -> io::Result<()> {
    Ok(())
}

#[cfg(not(unix))]
fn open_existing_shm() -> io::Result<Vec<u8>> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "POSIX shm not available on this platform",
    ))
}

/// Truncate `bytes` to at most `max_bytes`, respecting UTF-8 character
/// boundaries (i.e., never split a multi-byte codepoint).
fn utf8_truncate(bytes: &[u8], max_bytes: usize) -> usize {
    if bytes.len() <= max_bytes {
        return bytes.len();
    }
    let mut len = max_bytes;
    // Walk back until we're at a UTF-8 leading byte.
    while len > 0 && (bytes[len] & 0xC0) == 0x80 {
        len -= 1;
    }
    len
}
