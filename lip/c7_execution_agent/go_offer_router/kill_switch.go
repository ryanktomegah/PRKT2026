// kill_switch.go — Shared-memory kill switch reader for the C7 Go offer router.
//
// Reads the Rust-written /dev/shm/lip_kill_switch segment.
//
// Segment layout (mirrors shm.rs):
//
//	Offset  Size  Field
//	──────  ────  ────────────────────────────────────────────
//	0       1     kill_flag  (u8: 0x00 = INACTIVE, 0x01 = KILLED)
//	1       1     shutdown_flag
//	2       2     reserved
//	4       8     activated_at_unix_ms
//	12      4     reason_len
//	16      256   reason_utf8
//	272     8     activation_count
//	280     8     reserved
//	─── total: 288 bytes ─────────────────────────────────────
//
// Fail-closed invariant:
//
//	If the SHM file cannot be opened or read, IsKilled() returns true.
//	This matches the Python kill_switch_bridge.py fail-closed posture.
package main

import (
	"log/slog"
	"os"
	"sync/atomic"
	"time"
)

const (
	// killFlagOffset is the byte offset of the kill flag in the SHM segment.
	killFlagOffset = 0

	// shmPollInterval is how often the background monitor refreshes the kill
	// flag. Lower intervals reduce reaction latency. 100ms matches the Rust
	// binary's signal poll interval.
	shmPollInterval = 100 * time.Millisecond
)

// KillSwitchReader reads the Rust kill switch from POSIX shared memory.
// It maintains an in-memory atomic copy updated by a background goroutine
// so that hot-path IsKilled() calls never block on file I/O.
type KillSwitchReader struct {
	shmPath  string
	killed   atomic.Bool
	log      *slog.Logger
	stopCh   chan struct{}
}

// NewKillSwitchReader creates a reader targeting shmPath.
// Performs an initial read; if the file is missing, killed=true (fail-closed).
func NewKillSwitchReader(shmPath string, log *slog.Logger) *KillSwitchReader {
	r := &KillSwitchReader{
		shmPath: shmPath,
		log:     log,
		stopCh:  make(chan struct{}),
	}
	r.refresh()
	return r
}

// IsKilled returns true when the kill switch is active.
// Reads from an atomic bool updated by the background goroutine — sub-100ns.
func (r *KillSwitchReader) IsKilled() bool {
	return r.killed.Load()
}

// StartMonitor launches the background polling goroutine.
// Call Stop() to shut it down cleanly.
func (r *KillSwitchReader) StartMonitor() {
	go func() {
		ticker := time.NewTicker(shmPollInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				r.refresh()
			case <-r.stopCh:
				return
			}
		}
	}()
}

// Stop shuts down the background monitor.
func (r *KillSwitchReader) Stop() {
	close(r.stopCh)
}

// refresh reads the SHM file and updates the atomic flag.
// On any I/O error, sets killed=true (fail-closed).
func (r *KillSwitchReader) refresh() {
	flag, err := readSHMKillFlag(r.shmPath)
	if err != nil {
		if !r.killed.Load() {
			r.log.Error("kill switch SHM read failed — fail-closed (killed=true)",
				"path", r.shmPath, "err", err)
		}
		r.killed.Store(true)
		return
	}
	prev := r.killed.Swap(flag)
	if prev != flag {
		if flag {
			r.log.Warn("kill switch activated (read from SHM)", "path", r.shmPath)
		} else {
			r.log.Info("kill switch deactivated (read from SHM)", "path", r.shmPath)
		}
	}
}

// readSHMKillFlag reads byte 0 of the SHM file.
// Returns true if the byte is 0x01, false if 0x00.
// Returns an error for any I/O failure.
func readSHMKillFlag(path string) (bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return false, err
	}
	defer f.Close()

	buf := make([]byte, 1)
	_, err = f.ReadAt(buf, killFlagOffset)
	if err != nil {
		return false, err
	}
	return buf[0] == 0x01, nil
}
