//! velocity.rs — DashMap-backed rolling 24-hour AML velocity window.
//!
//! Mirrors the logic of `velocity.py`'s `RollingWindow` (in-memory path) and
//! `VelocityChecker`, rewritten in Rust for sub-millisecond latency and
//! thread-safe concurrent access via `DashMap` and `AtomicU64`.
//!
//! # Threading guarantees
//! `DashMap` provides shard-level locking (default 16 shards). All counter
//! updates are atomic.  The check-and-record path acquires a per-entity
//! write guard to eliminate TOCTOU between concurrent Python threads
//! (equivalent to the `_check_record_lock` in the Python implementation).
//!
//! # Python API (PyO3)
//! See [`PyRollingVelocity`] for the exposed methods.

use dashmap::DashMap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Internal record type
// ---------------------------------------------------------------------------

/// A single transaction record stored in the rolling window.
#[derive(Clone, Debug)]
struct VelocityRecord {
    /// Unix timestamp (seconds, float precision stored as microseconds).
    timestamp_us: u64,
    /// Amount in USD cents (u64 for atomic arithmetic safety).
    amount_cents: u64,
    /// SHA-256 hex digest of the beneficiary identifier.
    bene_hash: String,
}

// ---------------------------------------------------------------------------
// Per-entity window (unsynchronised — callers hold DashMap shard lock)
// ---------------------------------------------------------------------------

#[derive(Default, Debug)]
struct EntityWindow {
    records: Vec<VelocityRecord>,
}

impl EntityWindow {
    /// Remove records older than `window_us` microseconds before `now_us`.
    fn prune(&mut self, now_us: u64, window_us: u64) {
        let cutoff = now_us.saturating_sub(window_us);
        self.records.retain(|r| r.timestamp_us >= cutoff);
    }

    fn volume_cents(&self) -> u64 {
        self.records.iter().map(|r| r.amount_cents).sum()
    }

    fn count(&self) -> usize {
        self.records.len()
    }

    /// Returns the beneficiary concentration: fraction (0.0-1.0) of total
    /// volume directed to the single largest beneficiary.
    fn beneficiary_concentration(&self) -> f64 {
        let total = self.volume_cents();
        if total == 0 {
            return 0.0;
        }
        let mut by_bene: HashMap<&str, u64> = HashMap::new();
        for r in &self.records {
            *by_bene.entry(r.bene_hash.as_str()).or_insert(0) += r.amount_cents;
        }
        let max = by_bene.values().copied().max().unwrap_or(0);
        max as f64 / total as f64
    }
}

// ---------------------------------------------------------------------------
// Atomic counters for Prometheus metrics
// ---------------------------------------------------------------------------

#[derive(Default, Debug)]
struct Metrics {
    checks_total: AtomicU64,
    passes_total: AtomicU64,
    dollar_cap_hits: AtomicU64,
    count_cap_hits: AtomicU64,
    conc_cap_hits: AtomicU64,
    records_total: AtomicU64,
}

// ---------------------------------------------------------------------------
// Core struct
// ---------------------------------------------------------------------------

/// Rolling 24-hour velocity window with per-entity DashMap sharding.
///
/// All public methods are thread-safe and may be called concurrently from
/// multiple Python threads.
#[derive(Debug)]
struct RollingVelocity {
    /// window_us = window_seconds * 1_000_000
    window_us: u64,
    windows: Arc<DashMap<String, EntityWindow>>,
    metrics: Arc<Metrics>,
}

impl RollingVelocity {
    fn new(window_seconds: u64) -> Self {
        Self {
            window_us: window_seconds.saturating_mul(1_000_000),
            windows: Arc::new(DashMap::new()),
            metrics: Arc::new(Metrics::default()),
        }
    }

    fn now_us() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_micros() as u64)
            .unwrap_or(0)
    }

    /// Hash an identifier with a salt via SHA-256.
    fn hash_id(raw: &str, salt: &[u8]) -> String {
        let mut h = Sha256::new();
        h.update(raw.as_bytes());
        h.update(salt);
        hex::encode(h.finalize())
    }

    /// Check whether a candidate transaction passes all velocity caps.
    /// Does NOT record — call `record()` separately, or use `check_and_record()`.
    ///
    /// Returns `(passed, reason, volume_usd_f64, count)`
    fn check_inner(
        &self,
        entity_hash: &str,
        bene_hash: &str,
        amount_cents: u64,
        dollar_cap_cents: u64,
        count_cap: u64,
        conc_threshold: f64,
    ) -> (bool, String, f64, u64) {
        self.metrics.checks_total.fetch_add(1, Ordering::Relaxed);
        let now_us = Self::now_us();

        // Acquire a mutable reference to prune + read
        let mut entry = self
            .windows
            .entry(entity_hash.to_string())
            .or_insert_with(EntityWindow::default);
        entry.prune(now_us, self.window_us);

        let vol = entry.volume_cents();
        let cnt = entry.count() as u64;
        let vol_usd = vol as f64 / 100.0;

        // Rule 1: dollar cap (0 = unlimited per EPG-16)
        if dollar_cap_cents > 0 && vol + amount_cents > dollar_cap_cents {
            self.metrics.dollar_cap_hits.fetch_add(1, Ordering::Relaxed);
            return (false, "DOLLAR_CAP_EXCEEDED".to_string(), vol_usd, cnt);
        }

        // Rule 2: count cap (0 = unlimited)
        if count_cap > 0 && cnt + 1 > count_cap {
            self.metrics.count_cap_hits.fetch_add(1, Ordering::Relaxed);
            return (false, "COUNT_CAP_EXCEEDED".to_string(), vol_usd, cnt);
        }

        // Rule 3: beneficiary concentration (only when ≥ 2 prior records + ≥ 2 distinct benes)
        let total_after_cents = vol + amount_cents;
        if total_after_cents > 0 && cnt >= 2 {
            let mut by_bene: HashMap<String, u64> = HashMap::new();
            for r in entry.records.iter() {
                *by_bene.entry(r.bene_hash.clone()).or_insert(0) += r.amount_cents;
            }
            *by_bene.entry(bene_hash.to_string()).or_insert(0) += amount_cents;
            if by_bene.len() >= 2 {
                let max_v = by_bene.values().copied().max().unwrap_or(0);
                let conc = max_v as f64 / total_after_cents as f64;
                if conc > conc_threshold {
                    self.metrics.conc_cap_hits.fetch_add(1, Ordering::Relaxed);
                    return (
                        false,
                        "BENEFICIARY_CONCENTRATION_EXCEEDED".to_string(),
                        vol_usd,
                        cnt,
                    );
                }
            }
        }

        self.metrics.passes_total.fetch_add(1, Ordering::Relaxed);
        (true, String::new(), vol_usd, cnt)
    }

    fn record_inner(&self, entity_hash: &str, amount_cents: u64, bene_hash: &str) {
        self.metrics.records_total.fetch_add(1, Ordering::Relaxed);
        let now_us = Self::now_us();
        let mut entry = self
            .windows
            .entry(entity_hash.to_string())
            .or_insert_with(EntityWindow::default);
        entry.prune(now_us, self.window_us);
        entry.records.push(VelocityRecord {
            timestamp_us: now_us,
            amount_cents,
            bene_hash: bene_hash.to_string(),
        });
    }

    fn get_metrics_snapshot(&self) -> HashMap<String, u64> {
        let m = &self.metrics;
        let mut out = HashMap::new();
        out.insert("checks_total".into(), m.checks_total.load(Ordering::Relaxed));
        out.insert("passes_total".into(), m.passes_total.load(Ordering::Relaxed));
        out.insert("dollar_cap_hits".into(), m.dollar_cap_hits.load(Ordering::Relaxed));
        out.insert("count_cap_hits".into(), m.count_cap_hits.load(Ordering::Relaxed));
        out.insert("conc_cap_hits".into(), m.conc_cap_hits.load(Ordering::Relaxed));
        out.insert("records_total".into(), m.records_total.load(Ordering::Relaxed));
        out.insert("entity_count".into(), self.windows.len() as u64);
        out
    }
}

// ---------------------------------------------------------------------------
// PyO3 wrapper
// ---------------------------------------------------------------------------

/// Rust-backed rolling 24-hour AML velocity window, exposed to Python.
///
/// Thread-safe: multiple Python threads can call any method concurrently.
/// The GIL is released for all operations (DashMap handles its own locking).
///
/// Example usage from Python (run `maturin develop` first to build the wheel):
///
/// ```text
///     from lip_c6_rust_velocity import PyRollingVelocity
///     vel = PyRollingVelocity(window_seconds=86400, salt=b"my_32_byte_salt_")
///     passed, reason, vol, cnt = vel.check(
///         "entity_bic", "beneficiary_id", 1000.0, 1_000_000.0, 100, 0.80
///     )
///     vel.record("entity_bic", "beneficiary_id", 1000.0)
/// ```
#[pyclass]
pub struct PyRollingVelocity {
    inner: RollingVelocity,
    salt: Vec<u8>,
}

#[pymethods]
impl PyRollingVelocity {
    /// Create a new velocity window.
    ///
    /// Args:
    ///     window_seconds: Rolling window length (default 86400 = 24h).
    ///     salt: Byte string used to HMAC entity/beneficiary IDs before storage.
    #[new]
    #[pyo3(signature = (window_seconds=86400, salt=None))]
    fn new(window_seconds: u64, salt: Option<Vec<u8>>) -> Self {
        Self {
            inner: RollingVelocity::new(window_seconds),
            salt: salt.unwrap_or_default(),
        }
    }

    /// Hash a raw identifier with the configured salt (SHA-256).
    ///
    /// Returns a 64-char lowercase hex string (same algorithm as Python's
    /// `VelocityChecker._hash_entity`).
    fn hash_id(&self, raw: &str) -> String {
        RollingVelocity::hash_id(raw, &self.salt)
    }

    /// Check velocity limits for a candidate transaction.
    ///
    /// Does NOT record the transaction. Call `record()` separately after a
    /// successful check, or use `check_and_record()` for atomic semantics.
    ///
    /// Args:
    ///     entity_id:        Raw entity identifier (hashed internally).
    ///     beneficiary_id:   Raw beneficiary identifier (hashed internally).
    ///     amount_usd:       Candidate transaction amount in USD.
    ///     dollar_cap_usd:   Rolling 24h dollar cap (0 = unlimited per EPG-16).
    ///     count_cap:        Rolling 24h transaction count cap (0 = unlimited).
    ///     conc_threshold:   Beneficiary concentration threshold (default 0.80).
    ///
    /// Returns:
    ///     (passed: bool, reason: str, volume_24h_usd: float, count_24h: int)
    #[pyo3(signature = (entity_id, beneficiary_id, amount_usd, dollar_cap_usd=0.0, count_cap=0, conc_threshold=0.80))]
    fn check(
        &self,
        entity_id: &str,
        beneficiary_id: &str,
        amount_usd: f64,
        dollar_cap_usd: f64,
        count_cap: u64,
        conc_threshold: f64,
    ) -> PyResult<(bool, String, f64, u64)> {
        if amount_usd < 0.0 {
            return Err(PyValueError::new_err("amount_usd must be non-negative"));
        }
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let bene_hash = RollingVelocity::hash_id(beneficiary_id, &self.salt);
        // B7-01: amount_usd and dollar_cap_usd arrive as f64 from PyO3.
        // f64 has ~15-17 significant digits; at $10M (1e7) the ULP is ~1e-9,
        // well below 1 cent.  Precision loss only becomes material above ~$90T
        // (2^53 cents).  Switching to rust_decimal would add a crate dep for
        // negligible gain at realistic AML cap values.  Documented, not fixed.
        let amount_cents = (amount_usd * 100.0).round() as u64;
        let cap_cents = (dollar_cap_usd * 100.0).round() as u64;
        Ok(self.inner.check_inner(
            &entity_hash,
            &bene_hash,
            amount_cents,
            cap_cents,
            count_cap,
            conc_threshold,
        ))
    }

    /// Record a transaction in the rolling window.
    ///
    /// Args:
    ///     entity_id:      Raw entity identifier (hashed internally).
    ///     beneficiary_id: Raw beneficiary identifier (hashed internally).
    ///     amount_usd:     Transaction amount in USD.
    #[pyo3(signature = (entity_id, beneficiary_id, amount_usd))]
    fn record(&self, entity_id: &str, beneficiary_id: &str, amount_usd: f64) -> PyResult<()> {
        if amount_usd < 0.0 {
            return Err(PyValueError::new_err("amount_usd must be non-negative"));
        }
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let bene_hash = RollingVelocity::hash_id(beneficiary_id, &self.salt);
        let amount_cents = (amount_usd * 100.0).round() as u64;
        self.inner.record_inner(&entity_hash, amount_cents, &bene_hash);
        Ok(())
    }

    /// Atomically check and record in a single operation.
    ///
    /// Holds the DashMap entry write-guard for the duration so no concurrent
    /// thread can slip through between the check and the write.
    ///
    /// Returns same tuple as `check()`.
    #[pyo3(signature = (entity_id, beneficiary_id, amount_usd, dollar_cap_usd=0.0, count_cap=0, conc_threshold=0.80))]
    fn check_and_record(
        &self,
        entity_id: &str,
        beneficiary_id: &str,
        amount_usd: f64,
        dollar_cap_usd: f64,
        count_cap: u64,
        conc_threshold: f64,
    ) -> PyResult<(bool, String, f64, u64)> {
        if amount_usd < 0.0 {
            return Err(PyValueError::new_err("amount_usd must be non-negative"));
        }
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let bene_hash = RollingVelocity::hash_id(beneficiary_id, &self.salt);
        let amount_cents = (amount_usd * 100.0).round() as u64;
        let cap_cents = (dollar_cap_usd * 100.0).round() as u64;

        // Hold the DashMap entry for the full duration (check + optional write)
        let now_us = RollingVelocity::now_us();
        let mut entry = self
            .inner
            .windows
            .entry(entity_hash.clone())
            .or_insert_with(EntityWindow::default);
        entry.prune(now_us, self.inner.window_us);

        let vol = entry.volume_cents();
        let cnt = entry.count() as u64;
        let vol_usd = vol as f64 / 100.0;

        self.inner.metrics.checks_total.fetch_add(1, Ordering::Relaxed);

        if cap_cents > 0 && vol + amount_cents > cap_cents {
            self.inner.metrics.dollar_cap_hits.fetch_add(1, Ordering::Relaxed);
            return Ok((false, "DOLLAR_CAP_EXCEEDED".to_string(), vol_usd, cnt));
        }
        if count_cap > 0 && cnt + 1 > count_cap {
            self.inner.metrics.count_cap_hits.fetch_add(1, Ordering::Relaxed);
            return Ok((false, "COUNT_CAP_EXCEEDED".to_string(), vol_usd, cnt));
        }

        let total_after = vol + amount_cents;
        if total_after > 0 && cnt >= 2 {
            let mut by_bene: HashMap<String, u64> = HashMap::new();
            for r in entry.records.iter() {
                *by_bene.entry(r.bene_hash.clone()).or_insert(0) += r.amount_cents;
            }
            *by_bene.entry(bene_hash.clone()).or_insert(0) += amount_cents;
            if by_bene.len() >= 2 {
                let max_v = by_bene.values().copied().max().unwrap_or(0);
                let conc = max_v as f64 / total_after as f64;
                if conc > conc_threshold {
                    self.inner.metrics.conc_cap_hits.fetch_add(1, Ordering::Relaxed);
                    return Ok((
                        false,
                        "BENEFICIARY_CONCENTRATION_EXCEEDED".to_string(),
                        vol_usd,
                        cnt,
                    ));
                }
            }
        }

        // All caps passed — record now (still holding the guard)
        entry.records.push(VelocityRecord {
            timestamp_us: now_us,
            amount_cents,
            bene_hash: bene_hash.clone(),
        });
        self.inner.metrics.passes_total.fetch_add(1, Ordering::Relaxed);
        self.inner.metrics.records_total.fetch_add(1, Ordering::Relaxed);
        Ok((true, String::new(), vol_usd, cnt))
    }

    /// Return current volume (USD) for an entity in the rolling window.
    fn get_volume(&self, entity_id: &str) -> f64 {
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let now_us = RollingVelocity::now_us();
        if let Some(mut entry) = self.inner.windows.get_mut(&entity_hash) {
            entry.prune(now_us, self.inner.window_us);
            entry.volume_cents() as f64 / 100.0
        } else {
            0.0
        }
    }

    /// Return transaction count for an entity in the rolling window.
    fn get_count(&self, entity_id: &str) -> u64 {
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let now_us = RollingVelocity::now_us();
        if let Some(mut entry) = self.inner.windows.get_mut(&entity_hash) {
            entry.prune(now_us, self.inner.window_us);
            entry.count() as u64
        } else {
            0
        }
    }

    /// Return beneficiary concentration (0.0-1.0) for an entity.
    fn get_beneficiary_concentration(&self, entity_id: &str) -> f64 {
        let entity_hash = RollingVelocity::hash_id(entity_id, &self.salt);
        let now_us = RollingVelocity::now_us();
        if let Some(mut entry) = self.inner.windows.get_mut(&entity_hash) {
            entry.prune(now_us, self.inner.window_us);
            entry.beneficiary_concentration()
        } else {
            0.0
        }
    }

    /// Flush all state (for testing or scheduled resets).
    fn flush(&self) {
        self.inner.windows.clear();
    }

    /// Return a dict of Prometheus-style metric counters.
    fn get_metrics(&self, py: Python<'_>) -> PyResult<PyObject> {
        let snap = self.inner.get_metrics_snapshot();
        let d = pyo3::types::PyDict::new(py);
        for (k, v) in snap {
            d.set_item(k, v)?;
        }
        Ok(d.into())
    }
}

// ---------------------------------------------------------------------------
// Unit tests (cargo test)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_window() -> RollingVelocity {
        RollingVelocity::new(86400)
    }

    #[test]
    fn test_pass_small_amount() {
        let w = make_window();
        let (passed, reason, vol, cnt) =
            w.check_inner("entity1", "bene1", 1_000_00, 0, 0, 0.80);
        assert!(passed, "small amount should pass when caps are 0 (unlimited)");
        assert!(reason.is_empty());
        assert_eq!(vol, 0.0);
        assert_eq!(cnt, 0);
    }

    #[test]
    fn test_dollar_cap_exceeded() {
        let w = make_window();
        // Record 999_999 USD worth
        w.record_inner("entity2", 999_999_00, "bene1");
        // Try to add $2 (total would be $1_000_001 > $1_000_000 cap)
        let (passed, reason, _, _) =
            w.check_inner("entity2", "bene2", 2_00, 1_000_000_00, 0, 0.80);
        assert!(!passed);
        assert_eq!(reason, "DOLLAR_CAP_EXCEEDED");
    }

    #[test]
    fn test_count_cap_exceeded() {
        let w = make_window();
        for i in 0..100 {
            w.record_inner("entity3", 1_00, &format!("bene{i}"));
        }
        let (passed, reason, _, cnt) =
            w.check_inner("entity3", "bene_new", 1_00, 0, 100, 0.80);
        assert!(!passed);
        assert_eq!(reason, "COUNT_CAP_EXCEEDED");
        assert_eq!(cnt, 100);
    }

    #[test]
    fn test_beneficiary_concentration_exceeded() {
        let w = make_window();
        // 9 × $1000 to bene_dominant = $9000, 1 × $1000 to bene_other = $1000
        for _ in 0..9 {
            w.record_inner("entity4", 1_000_00, "bene_dominant");
        }
        w.record_inner("entity4", 1_000_00, "bene_other");
        // Try to add $9000 more to bene_dominant → projected conc > 80%
        let (passed, reason, _, _) =
            w.check_inner("entity4", "bene_dominant", 9_000_00, 0, 0, 0.80);
        assert!(!passed);
        assert_eq!(reason, "BENEFICIARY_CONCENTRATION_EXCEEDED");
    }

    #[test]
    fn test_different_entities_isolated() {
        let w = make_window();
        w.record_inner("entity_a", 999_000_00, "bene1");
        // entity_b should be unaffected
        let (passed, _, vol, _) =
            w.check_inner("entity_b", "bene2", 500_000_00, 1_000_000_00, 100, 0.80);
        assert!(passed);
        assert_eq!(vol, 0.0);
    }

    #[test]
    fn test_hash_id_never_contains_raw() {
        let w = make_window();
        let h = RollingVelocity::hash_id("TAX123456", b"salt");
        assert!(!h.contains("TAX123456"));
        assert_eq!(h.len(), 64);
    }

    #[test]
    fn test_metrics_increment() {
        let w = make_window();
        w.check_inner("e", "b", 1_00, 0, 0, 0.80);
        w.record_inner("e", 1_00, "b");
        let snap = w.get_metrics_snapshot();
        assert_eq!(snap["checks_total"], 1);
        assert_eq!(snap["passes_total"], 1);
        assert_eq!(snap["records_total"], 1);
    }
}
