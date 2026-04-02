# C7 Kill Switch: Rust Migration Technical Specification

**Status:** Approved — Priority 1, Language Architecture Migration Plan  
**Authors:** CIPHER (security review), QUANT (latency SLO), REX (regulatory)  
**Approved:** 2026-03-18 (EPIGNOSIS Architecture Review)  
**Target:** LIP C7 Execution Agent (`lip/c7_execution_agent/`)

---

## 1. Problem Statement

### 1.1 Why Python asyncio Is Architecturally Insufficient

The current kill switch in `kill_switch.py` uses Python threading and Redis to propagate halt signals. Under the following conditions, the "immediate" halt guarantee breaks down:

| Failure Mode | Python asyncio behaviour | Consequence |
|---|---|---|
| Long-running coroutine blocking the event loop | Kill check deferred until coroutine yields | New offer emitted after kill signal received |
| GIL contention under CPU load | Thread-based flag check delayed | Sub-millisecond latency guarantee violated |
| Redis unreachable | Falls back to in-memory flag per pod | Kill signal does not propagate across pods without Redis |
| Process OOM / SIGKILL | Thread state lost; no cross-process visibility | Kill flag invisible to sibling processes |
| Python `threading.Event.wait()` spin | CPU burns on monitor thread | Resource pressure degrades event loop |

The canonical definition of "immediately" in EU AI Act Art.14 and DORA Art.30 requires that a kill signal **preempts** execution rather than waiting for cooperative scheduling. Python asyncio's `next event loop tick` model is cooperative, not preemptive. A Rust binary with `AtomicBool` and OS-level signal handlers genuinely preempts.

### 1.2 Regulatory Obligation

- **EU AI Act Art.14** — Human oversight: kill switch must halt automated decisions at any time, without software changes.
- **EU AI Act Art.9** — Risk management: primary risk control; must activate within ≤ 1ms (well within the 94ms system SLO).
- **DORA Art.30** — All activations logged with timestamps and reason strings; audit trail must be tamper-evident.
- **SR 11-7** — Hard stop for model validators and risk officers; must not rely on in-model logic.

---

## 2. Architecture Design

### 2.1 Component Topology

```
┌─────────────────────────────────────────────────────────┐
│  Python / Go services (C7 Execution Agent)              │
│                                                         │
│  ┌──────────────────────┐   PyO3 FFI   ┌────────────┐  │
│  │  kill_switch_bridge  │◄────────────►│  Rust .so  │  │
│  │  (Python wrapper)    │              │  (libkill) │  │
│  └──────────┬───────────┘              └─────┬──────┘  │
│             │ fallback                        │         │
│  ┌──────────▼───────────┐              ┌─────▼──────┐  │
│  │  kill_switch.py      │              │  /dev/shm  │  │
│  │  (existing Python)   │              │  /lip_ks   │  │
│  └──────────────────────┘              └─────┬──────┘  │
└───────────────────────────────────────────── │─────────┘
                                               │
┌──────────────────────────────────────────────▼─────────┐
│  Rust kill switch binary (standalone process)           │
│                                                         │
│  AtomicBool (kill_flag)    ◄──── SIGUSR1 handler       │
│  AtomicBool (shutdown_flag) ◄── SIGTERM handler        │
│                                                         │
│  mmap / POSIX shm → /dev/shm/lip_kill_switch           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 State Machine

```
         ┌──────────┐
         │  NORMAL  │◄─────── reset_kill()
         └────┬─────┘
              │ activate_kill(reason)
              │ or SIGUSR1
              ▼
         ┌──────────┐
         │  KILLED  │  (fail-closed default when binary not running)
         └──────────┘
```

### 2.3 Fail-Closed Default

**Critical safety invariant:** If the Rust binary is not running or the shared memory segment is unreadable, the Python bridge reports `is_killed() = True`. No new offers are emitted. This is the fail-closed posture required by EU AI Act Art.9.

---

## 3. Memory Ordering Guarantees

### 3.1 AtomicBool Operations

```rust
use std::sync::atomic::{AtomicBool, Ordering};

static KILL_FLAG: AtomicBool = AtomicBool::new(false);

// Write side — kill activation (operator command or signal handler)
// Ordering::SeqCst: establishes a total sequential order visible to ALL threads
// and ALL CPUs. This is the strongest available ordering. Required here because:
//   1. The flag write must be globally visible before any subsequent load on
//      any thread observes it — even on processors with weak memory models (ARM).
//   2. No reads or writes in the current thread can be reordered past this store.
//   3. On x86 this compiles to MFENCE + MOV; on ARM to STLR (store-release
//      with full barrier). The overhead is ~5ns — negligible vs. the 1ms budget.
KILL_FLAG.store(true, Ordering::SeqCst);

// Read side — polling in offer-processing hot path
// Ordering::Acquire: guarantees that all memory operations that happened
// *before* the SeqCst store on the write side are visible to this thread
// after the load returns true. Specifically:
//   1. All writes performed before activate_kill() are visible here.
//   2. Prevents the compiler/CPU from hoisting reads of loan-state variables
//      past the flag check (which would allow stale reads of pre-kill state).
//   3. On x86 this is a plain MOV (x86 loads are already acquire-ordered);
//      on ARM this compiles to LDAR (load-acquire).
let is_killed = KILL_FLAG.load(Ordering::Acquire);
```

### 3.2 Rationale for Ordering Choices

| Operation | Ordering | Rationale |
|---|---|---|
| `store(true)` — activate | `SeqCst` | Must be globally visible across all CPUs before any subsequent read on any thread can observe the old value. Prevents kill signal being missed on weakly-ordered architectures (ARM Neoverse, Apple M-series). |
| `store(false)` — reset | `SeqCst` | Symmetric with activate — reset must also be globally ordered to prevent spurious kills after reset. |
| `load()` — read in hot path | `Acquire` | Sufficient to observe the `SeqCst` store reliably. Cheaper than `SeqCst` load on ARM. `Relaxed` would be incorrect — it cannot observe the happens-before edge established by `SeqCst` store. |

### 3.3 Shared Memory Ordering

The `AtomicBool` in POSIX shared memory (`/dev/shm/lip_kill_switch`) uses the same ordering guarantees. The mmap region is mapped with `MAP_SHARED` so that stores to the atomic are immediately visible to all mapping processes without a system call. The atomic itself is placed at a cache-line-aligned offset to prevent false sharing.

---

## 4. Signal Handler Design

### 4.1 Signals

| Signal | Action | Rationale |
|---|---|---|
| `SIGUSR1` | Activate kill switch | Application-defined; safe to use without affecting system tools. Chosen over `SIGINT`/`SIGTERM` because it does not trigger normal shutdown. |
| `SIGTERM` | Graceful shutdown of Rust binary | Standard container termination signal. Binary exits cleanly, leaving kill flag in place. |
| `SIGHUP` | Reset kill switch | Conventional "reload config" signal; repurposed for in-place reset without full restart. |

### 4.2 Signal Handler Safety

Signal handlers in Rust (via `signal_hook`) must only call async-signal-safe functions. The implementation:

1. Registers handlers using `signal_hook::flag::register` which atomically sets an `AtomicBool` — fully async-signal-safe.
2. The main loop polls the signal flag and performs the state transition (logging, shm update) from the non-signal context.
3. No `malloc`, `mutex`, or I/O calls inside signal handlers. All logging is deferred to the main loop.

### 4.3 Signal Delivery Failure Mode

If `SIGUSR1` cannot be delivered (process not running, PID mismatch), the Python bridge falls back to the PyO3 `activate_kill()` function which writes directly to the shared memory segment. The two paths are independent — signal delivery failure does not prevent activation.

---

## 5. Shared Memory Interface

### 5.1 Layout (`/dev/shm/lip_kill_switch`)

```
Offset  Size  Field
──────  ────  ─────────────────────────────────────────
0       1     kill_flag (AtomicBool, u8 0x00/0x01)
1       1     shutdown_flag (AtomicBool, u8 0x00/0x01)
2       2     reserved (padding to 4-byte boundary)
4       8     activated_at_unix_ms (AtomicI64, little-endian)
12      4     reason_len (AtomicU32, max 255)
16      256   reason_utf8 (fixed-size ring buffer, null-padded)
272     8     activation_count (AtomicU64, monotonic counter)
280     8     reserved
── total: 288 bytes (fits in 5 cache lines, no false sharing ──
```

All multi-byte fields are stored in little-endian byte order. The segment is created with permissions `0600` (owner read-write only) — see Section 9.1 for CIPHER sign-off rationale.

### 5.2 Access Protocol

- **Rust binary**: Creates and owns the segment. On startup, maps it and initialises all fields. On exit, leaves the segment in place (kill flag preserved across restarts).
- **Python bridge (via PyO3)**: Maps the segment read-write. Writes to `kill_flag` and `reason` directly when `activate_kill()` is called from Python operator command path.
- **Go offer router (future)**: Maps the segment read-only (`MAP_SHARED | PROT_READ`). Polls `kill_flag` on every offer dispatch.

### 5.3 Cleanup Policy

The segment is **not** unlinked on normal shutdown. This preserves the kill state across Rust binary restarts, preventing a window where the binary is restarting but old kill signals are not honoured. The segment is explicitly unlinked only by `reset_kill()`.

---

## 6. PyO3 Integration Layer

### 6.1 Python Module API

```python
# Import (available when Rust .so is compiled and installed)
import lip_kill_switch  # PyO3 module name

# Query state — maps to AtomicBool.load(Acquire)
killed: bool = lip_kill_switch.is_killed()

# Activate — maps to AtomicBool.store(true, SeqCst) + shm write
lip_kill_switch.activate_kill(reason="model_auc_drift")

# Reset — maps to AtomicBool.store(false, SeqCst) + shm unlink + reinit
lip_kill_switch.reset_kill()

# Status — full snapshot from shm
status: dict = lip_kill_switch.get_status()
# Returns: {
#   "killed": bool,
#   "activated_at_unix_ms": int | None,
#   "reason": str | None,
#   "activation_count": int,
#   "binary_running": bool,
# }
```

### 6.2 Thread Safety

The PyO3 module releases the GIL during all atomic operations and shm reads/writes. This allows concurrent Python threads (e.g., asyncio event loop thread + KMS monitor thread) to call `is_killed()` without blocking each other.

### 6.3 Error Handling

All PyO3 functions raise `RuntimeError` with descriptive messages on failure (shm not found, permission denied, invalid UTF-8 in reason). The Python bridge catches all such exceptions and falls back to the Python kill switch with a `CRITICAL` log.

---

## 7. Failure Modes

### 7.1 Rust Binary Crashes

**Detection:** Python bridge calls `get_status()` every 5 seconds in a background thread. If the call raises `RuntimeError` (shm unavailable), `binary_running` is set to `False`.

**Response:** Python bridge immediately sets `kill_switch_state = KILLED` (fail-closed). Prometheus metric `kill_switch_binary_up` goes to `0`. PagerDuty alert fires.

**Recovery:** Restart the Rust binary. It re-maps the existing shm segment (kill flag preserved). Python bridge detects `binary_running = True` on next poll. If kill flag was set before crash, state is preserved — manual `reset_kill()` is required.

### 7.2 Shared Memory Unavailable

**Cause:** `/dev/shm` full, permission error, kernel tmpfs unmounted.

**Response:** Same as 7.1 — fail-closed. Python bridge falls back to in-memory + Redis (existing `kill_switch.py`). Loud `CRITICAL` log: `"RUST KS SHM UNAVAILABLE — OPERATING IN DEGRADED PYTHON FALLBACK MODE"`.

**Recovery:** Resolve `/dev/shm` issue. Restart Rust binary. Manual verification that kill flag state is consistent.

### 7.3 Signal Delivery Fails

**Cause:** PID mismatch, process not running, capabilities removed.

**Response:** Python operator falls back to `lip_kill_switch.activate_kill(reason)` via PyO3 direct call, which writes to shm without requiring signal delivery. The signal path and the PyO3 direct path are independent.

### 7.4 Python Process Restarts, Kill Flag Still Set

**Behaviour:** On Python process restart, the bridge calls `get_status()`. If `killed = True`, the bridge initialises in KILLED state immediately — no offers are emitted before operator review. The Rust binary / shm is the persistent source of truth.

**Design intent:** This is correct behaviour. A restart during a kill event should not silently clear the kill state.

---

## 8. Testing Strategy

### 8.1 Rust Unit Tests (`lip/c7_execution_agent/rust_kill_switch/tests/`)

| Test | Coverage |
|---|---|
| `test_atomic_flag_default_false` | AtomicBool initialises to false (INACTIVE) |
| `test_activate_sets_flag` | store(SeqCst) sets flag; load(Acquire) observes it |
| `test_reset_clears_flag` | store(false, SeqCst) clears flag |
| `test_concurrent_reads` | 16 reader threads + 1 writer; no stale reads |
| `test_shm_create_and_read` | shm segment created, flag written, re-opened and read |
| `test_shm_persistence` | close and reopen segment; flag value persists |
| `test_reason_utf8_truncation` | reason > 255 bytes truncated safely |
| `test_activation_count_monotonic` | counter increments on each activate |

### 8.2 Signal Handling Tests (`test_signal.rs`)

| Test | Coverage |
|---|---|
| `test_sigusr1_activates_kill` | Send SIGUSR1 to self; poll until flag set (< 10ms) |
| `test_sigterm_sets_shutdown` | Send SIGTERM; `shutdown_flag` goes true |
| `test_sighup_resets_kill` | Activate, send SIGHUP; flag clears |
| `test_signal_handler_no_malloc` | Valgrind / sanitiser: no heap allocations in handler |

### 8.3 Python Integration Tests (`lip/tests/test_kill_switch_rust.py`)

| Test | Coverage |
|---|---|
| `test_fail_closed_without_rust_binary` | PyO3 not loaded → `is_killed() = True` |
| `test_bridge_fallback_warns` | Missing module → `CRITICAL` log emitted |
| `test_bridge_activate_python_path` | Fallback Python kill switch activates correctly |
| `test_bridge_reset_flow` | Activate → reset → INACTIVE in fallback mode |
| `test_bridge_concurrent_reads` | 10 threads reading `is_killed()` concurrently |
| `test_bridge_prometheus_metrics` | `kill_switch_state` metric present |
| `test_signal_activation` | Send SIGUSR1 to process; bridge detects state change |
| `test_shm_persistence_restart` | Simulate process restart with kill flag set |
| `test_rust_module_if_available` | Skip if PyO3 not compiled; else full integration |

### 8.4 Race Condition Tests

- Use Python `threading.Barrier` to synchronise 16 threads hitting `is_killed()` simultaneously.
- Run under `python -m pytest --forked` if available to detect state leakage between tests.

---

## 9. CI/CD Integration

### 9.1 CIPHER Sign-off: Shared Memory Permissions

Shared memory segment `/dev/shm/lip_kill_switch` is created with `mode=0o600` (owner read-write only). This is the minimum required permission. The Rust binary, PyO3 `.so`, and Go reader all run as the same UID (`lip-agent`, UID 9000) inside the container. No world-readable or group-readable permissions are granted. **CIPHER approves this design.**

### 9.2 Rust Toolchain in CI

Add to `.github/workflows/ci.yml`:

```yaml
- name: Install Rust toolchain
  uses: dtolnay/rust-toolchain@stable
  with:
    toolchain: stable
    targets: x86_64-unknown-linux-gnu

- name: Cache Rust build artifacts
  uses: Swatinem/rust-cache@v2
  with:
    workspaces: "lip/c7_execution_agent/rust_kill_switch -> target"

- name: Build and test Rust kill switch
  working-directory: lip/c7_execution_agent/rust_kill_switch
  run: cargo test --release
```

### 9.3 Docker Multi-Stage Build

```dockerfile
# Stage 1: Rust builder
FROM rust:1.77-slim AS rust-builder
WORKDIR /build/lip/c7_execution_agent/rust_kill_switch
COPY lip/c7_execution_agent/rust_kill_switch/ .
RUN cargo build --release

# Stage 2: PyO3 wheel builder
FROM rust:1.77-slim AS pyo3-builder
RUN apt-get update && apt-get install -y python3-dev python3-pip
RUN pip install maturin
WORKDIR /build/lip/c7_execution_agent/rust_kill_switch
COPY lip/c7_execution_agent/rust_kill_switch/ .
RUN maturin build --release --out /wheels

# Stage 3: Python runtime
FROM python:3.11-slim
COPY --from=rust-builder /build/lip/c7_execution_agent/rust_kill_switch/target/release/lip_kill_switch_bin /usr/local/bin/
COPY --from=pyo3-builder /wheels/*.whl /tmp/wheels/
RUN pip install /tmp/wheels/*.whl
```

### 9.4 PyO3 Wheel Building

Built with `maturin build --release`. The wheel name follows PEP 427: `lip_kill_switch-0.1.0-cp311-cp311-manylinux_2_17_x86_64.whl`. Published to the internal PyPI mirror.

---

## 10. Rollback Plan

### 10.1 Trigger Conditions

Roll back to Python-only kill switch if:
- Rust binary repeatedly crashes (> 3 times in 5 minutes)
- PyO3 import fails at startup
- Shared memory segment becomes corrupted
- Any latency regression > 10% on the 94ms SLO

### 10.2 Rollback Procedure

1. **Immediate (< 30 seconds):** Set environment variable `LIP_KS_FORCE_PYTHON=1`. The bridge checks this on every call and bypasses the Rust module entirely. No restart required.
2. **Graceful (next deployment):** Remove PyO3 wheel from requirements. Revert `kill_switch_bridge.py` import section.

### 10.3 Python Fallback During Normal Operation

Even without rollback, the Python fallback is always active as a secondary layer:

```
Rust module available? ──Yes──► Use PyO3 path (primary)
          │
          No (or LIP_KS_FORCE_PYTHON=1)
          │
          ▼
     Use kill_switch.py (fallback) — CRITICAL log emitted every 60s
```

The Python fallback uses Redis for cross-pod propagation (same as today). This is architecturally weaker but operationally correct.

---

## Appendix A: Memory Ordering Quick Reference

| Ordering | Compiles to (x86) | Compiles to (ARM) | Use case |
|---|---|---|---|
| `Relaxed` | MOV | STR / LDR | Counters where ordering doesn't matter |
| `Acquire` | MOV (load) | LDAR | Read side of a flag; see stores from paired Release/SeqCst |
| `Release` | MOV (store) | STLR | Write side with local barrier only |
| `SeqCst` | MFENCE + MOV | STLR + DMB ISH | Kill switch activate/reset; global total order |

For the kill switch, we use `SeqCst` on writes and `Acquire` on reads. This is the standard "publication" pattern: the writer publishes with maximum ordering; the reader observes with minimum ordering sufficient to see the publication. Using `SeqCst` on reads would be correct but adds unnecessary MFENCE overhead on ARM in the hot path.

---

## Appendix B: Latency Budget

| Operation | Budget | Implementation |
|---|---|---|
| `is_killed()` read (Python) | < 100ns | PyO3 → `AtomicBool::load(Acquire)` → return bool |
| `is_killed()` read (fallback) | < 1ms | Redis GET `lip:kill_switch` |
| `activate_kill()` (signal) | < 1ms | SIGUSR1 → signal handler → `AtomicBool::store(SeqCst)` |
| `activate_kill()` (PyO3) | < 500μs | Python call → PyO3 FFI → store → shm write |
| End-to-end system SLO | ≤ 94ms | QUANT-controlled — kill switch well within budget |

---

*Document version: 1.0 — 2026-04-02*  
*CIPHER reviewed: approved (shm permissions, signal handler safety)*  
*QUANT reviewed: approved (latency budget confirmed within 94ms SLO)*  
*REX reviewed: approved (EU AI Act Art.9/14, DORA Art.30 obligations met)*
