//! sanctions.rs — Rust-backed sanctions screener for C6 AML.
//!
//! Provides two-tier screening:
//!   1. **Exact/substring pass**: Aho-Corasick automaton for fast multi-pattern
//!      substring matching across all entries in O(n + m).  A hit here means
//!      the query is a substring of (or equals) a sanctions entry.
//!   2. **Jaccard token-overlap**: Tokenises both query and each entry on
//!      whitespace; computes |A ∩ B| / |A ∪ B|.  Returns hits ≥ threshold
//!      (default 0.8), identical to `sanctions.py`'s `_fuzzy_match`.
//!
//! # Python API
//! See [`PySanctionsScreener`] for the full PyO3-exposed interface.
//!
//! # Compliance note
//! The current matching logic (Jaccard token-overlap with 0.8 threshold) does
//! NOT handle transliterated names or phonetic matches.  This is an audit
//! finding — see `docs/c6_sanctions_audit.md`.  The Rust port matches the
//! Python implementation exactly so there is no compliance regression.

use aho_corasick::{AhoCorasick, AhoCorasickBuilder, MatchKind};
use pyo3::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

/// Source list identifier for a sanctions entry.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
enum ListName {
    Ofac,
    Eu,
    Un,
}

impl ListName {
    fn as_str(&self) -> &'static str {
        match self {
            ListName::Ofac => "OFAC",
            ListName::Eu => "EU",
            ListName::Un => "UN",
        }
    }

    fn from_str(s: &str) -> Option<Self> {
        match s.to_uppercase().as_str() {
            "OFAC" => Some(ListName::Ofac),
            "EU" => Some(ListName::Eu),
            "UN" => Some(ListName::Un),
            _ => None,
        }
    }
}

/// Represents a hit returned by the screener.
#[derive(Clone, Debug)]
struct Hit {
    entity_name_hash: String,
    list_name: ListName,
    confidence: f64,
    reference: String,
}

// ---------------------------------------------------------------------------
// Metric counters
// ---------------------------------------------------------------------------

#[derive(Default, Debug)]
struct SanctionsMetrics {
    screens_total: AtomicU64,
    hits_total: AtomicU64,
    misses_total: AtomicU64,
    exact_hits: AtomicU64,
    fuzzy_hits: AtomicU64,
    load_calls: AtomicU64,
    flush_calls: AtomicU64,
}

// ---------------------------------------------------------------------------
// Core screener
// ---------------------------------------------------------------------------

struct SanctionsScreener {
    /// entries[i] = (list_name, upper-cased entry)
    entries: Vec<(ListName, String)>,
    /// Aho-Corasick automaton for fast substring pre-filter.
    /// Rebuilt on every `load()` / `flush()` call.
    ac: AhoCorasick,
    /// Confidence threshold (default 0.8, matching Python).
    threshold: f64,
    metrics: SanctionsMetrics,
}

impl SanctionsScreener {
    fn new(threshold: f64) -> Self {
        Self {
            entries: Vec::new(),
            ac: AhoCorasickBuilder::new()
                .match_kind(MatchKind::LeftmostFirst)
                .build::<_, &str>([])
                .expect("empty AC build never fails"),
            threshold,
            metrics: SanctionsMetrics::default(),
        }
    }

    /// Replace all entries and rebuild the Aho-Corasick automaton.
    fn load(&mut self, entries_by_list: HashMap<String, Vec<String>>) {
        self.metrics.load_calls.fetch_add(1, Ordering::Relaxed);
        self.entries.clear();
        for (list_str, names) in &entries_by_list {
            let Some(list) = ListName::from_str(list_str) else {
                continue;
            };
            for name in names {
                let upper = name.trim().to_uppercase();
                if !upper.is_empty() {
                    self.entries.push((list.clone(), upper));
                }
            }
        }
        self.rebuild_ac();
    }

    fn rebuild_ac(&mut self) {
        let patterns: Vec<&str> = self.entries.iter().map(|(_, e)| e.as_str()).collect();
        self.ac = AhoCorasickBuilder::new()
            .match_kind(MatchKind::LeftmostFirst)
            .ascii_case_insensitive(false) // entries already upper-cased
            .build(patterns)
            .unwrap_or_else(|_| {
                AhoCorasickBuilder::new()
                    .build::<_, &str>([])
                    .expect("empty AC build never fails")
            });
    }

    fn flush(&mut self) {
        self.metrics.flush_calls.fetch_add(1, Ordering::Relaxed);
        self.entries.clear();
        self.rebuild_ac();
    }

    /// SHA-256 hash of the normalised name (hex string).
    fn hash_name(normalised: &str) -> String {
        let mut h = Sha256::new();
        h.update(normalised.as_bytes());
        hex::encode(h.finalize())
    }

    /// Compute Jaccard token-overlap between `query_tokens` and `entry`.
    ///
    /// Identical algorithm to Python's `SanctionsScreener._fuzzy_match`:
    ///   jaccard = |A ∩ B| / |A ∪ B|
    fn jaccard(query_tokens: &HashSet<&str>, entry: &str) -> f64 {
        let entry_tokens: HashSet<&str> = entry.split_whitespace().collect();
        if entry_tokens.is_empty() {
            return 0.0;
        }
        let intersection = query_tokens.intersection(&entry_tokens).count();
        if intersection == 0 {
            return 0.0;
        }
        let union = query_tokens.union(&entry_tokens).count();
        intersection as f64 / union as f64
    }

    fn screen(&self, entity_name: &str) -> Vec<Hit> {
        self.metrics.screens_total.fetch_add(1, Ordering::Relaxed);
        let normalised = entity_name.trim().to_uppercase();
        let name_hash = Self::hash_name(&normalised);
        let query_tokens: HashSet<&str> = normalised.split_whitespace().collect();

        let mut hits: Vec<Hit> = Vec::new();

        // Tier 1: collect candidate entry indices via Aho-Corasick substring match.
        // Any entry that is a substring of the query (or matches exactly) is a
        // candidate for exact scoring (confidence = 1.0).
        let mut exact_indices: HashSet<usize> = HashSet::new();
        for mat in self.ac.find_iter(normalised.as_str()) {
            exact_indices.insert(mat.pattern().as_usize());
        }

        // Tier 2: Jaccard scan over ALL entries (same as Python, no pre-filter for fuzzy).
        // Entries confirmed by Aho-Corasick (substring of query) receive confidence 1.0.
        // All other entries use the Jaccard score directly.
        for (idx, (list_name, entry)) in self.entries.iter().enumerate() {
            let confidence = if exact_indices.contains(&idx) {
                // AC confirmed this entry is a substring of the normalised query —
                // full confidence. (Single-token entries should not be loaded to
                // avoid false positives on short substrings like "CORP".)
                1.0_f64
            } else {
                Self::jaccard(&query_tokens, entry)
            };

            if confidence >= self.threshold {
                hits.push(Hit {
                    entity_name_hash: name_hash.clone(),
                    list_name: list_name.clone(),
                    confidence,
                    reference: entry.clone(),
                });
            }
        }

        if hits.is_empty() {
            self.metrics.misses_total.fetch_add(1, Ordering::Relaxed);
        } else {
            self.metrics.hits_total.fetch_add(hits.len() as u64, Ordering::Relaxed);
            let exact_hit_count = hits.iter().filter(|h| h.confidence >= 1.0).count();
            self.metrics.exact_hits.fetch_add(exact_hit_count as u64, Ordering::Relaxed);
            let fuzzy_hit_count = hits.len() - exact_hit_count;
            self.metrics.fuzzy_hits.fetch_add(fuzzy_hit_count as u64, Ordering::Relaxed);
        }

        hits
    }

    fn is_clear(&self, entity_name: &str) -> bool {
        self.screen(entity_name).is_empty()
    }

    fn get_metrics_snapshot(&self) -> HashMap<String, u64> {
        let m = &self.metrics;
        let mut out = HashMap::new();
        out.insert("screens_total".into(), m.screens_total.load(Ordering::Relaxed));
        out.insert("hits_total".into(), m.hits_total.load(Ordering::Relaxed));
        out.insert("misses_total".into(), m.misses_total.load(Ordering::Relaxed));
        out.insert("exact_hits".into(), m.exact_hits.load(Ordering::Relaxed));
        out.insert("fuzzy_hits".into(), m.fuzzy_hits.load(Ordering::Relaxed));
        out.insert("load_calls".into(), m.load_calls.load(Ordering::Relaxed));
        out.insert("flush_calls".into(), m.flush_calls.load(Ordering::Relaxed));
        out.insert("entry_count".into(), self.entries.len() as u64);
        out
    }
}

// ---------------------------------------------------------------------------
// PyO3 wrapper
// ---------------------------------------------------------------------------

/// Rust-backed OFAC/EU/UN sanctions screener exposed to Python via PyO3.
///
/// Uses Aho-Corasick for fast exact/substring pre-screening and Jaccard
/// token-overlap for fuzzy matching — identical algorithm to `sanctions.py`.
///
/// Example usage from Python (run `maturin develop` first to build the wheel):
///
/// ```text
///     from lip_c6_rust_velocity import PySanctionsScreener
///     screener = PySanctionsScreener()
///     screener.load({"OFAC": ["ACME SHELL CORP"], "EU": [], "UN": []})
///     hits = screener.screen("ACME SHELL CORP")
///     is_ok = screener.is_clear("CLEAN COMPANY INC")
/// ```
///
/// Thread safety: the screener uses interior mutability for load/flush
/// (protected by a RwLock). `screen` and `is_clear` acquire a read guard.
#[pyclass]
pub struct PySanctionsScreener {
    inner: parking_lot::RwLock<SanctionsScreener>,
}

#[pymethods]
impl PySanctionsScreener {
    /// Create a new screener.
    ///
    /// Args:
    ///     threshold: Minimum Jaccard confidence to return a hit (default 0.8).
    #[new]
    #[pyo3(signature = (threshold=0.8))]
    fn new(threshold: f64) -> Self {
        Self {
            inner: parking_lot::RwLock::new(SanctionsScreener::new(threshold)),
        }
    }

    /// Load sanctions entries from a dict of list_name → [names].
    ///
    /// Args:
    ///     entries: Dict mapping list names ("OFAC", "EU", "UN") to lists of
    ///              entity name strings (will be normalised to uppercase).
    ///
    /// Replaces all previously loaded entries and rebuilds the Aho-Corasick
    /// automaton.
    fn load(&self, entries: HashMap<String, Vec<String>>) {
        self.inner.write().load(entries);
    }

    /// Flush all loaded entries (resets to empty state).
    fn flush(&self) {
        self.inner.write().flush();
    }

    /// Screen an entity name against all loaded sanctions lists.
    ///
    /// Normalises to uppercase before matching. Returns only hits with
    /// confidence ≥ threshold.
    ///
    /// Args:
    ///     entity_name: Human-readable entity name string.
    ///
    /// Returns:
    ///     List of dicts, each containing:
    ///       - ``entity_name_hash`` (str): SHA-256 hex digest of normalised name.
    ///       - ``list_name`` (str): "OFAC", "EU", or "UN".
    ///       - ``confidence`` (float): Jaccard/match confidence [0, 1].
    ///       - ``reference`` (str): Matched sanctions entry (uppercase canonical).
    fn screen(&self, py: Python<'_>, entity_name: &str) -> PyResult<PyObject> {
        let hits = self.inner.read().screen(entity_name);
        let result = pyo3::types::PyList::empty(py);
        for hit in hits {
            let d = pyo3::types::PyDict::new(py);
            d.set_item("entity_name_hash", &hit.entity_name_hash)?;
            d.set_item("list_name", hit.list_name.as_str())?;
            d.set_item("confidence", hit.confidence)?;
            d.set_item("reference", &hit.reference)?;
            result.append(d)?;
        }
        Ok(result.into())
    }

    /// Return True if the entity has no hits on any loaded list.
    ///
    /// Args:
    ///     entity_name: Human-readable entity name string.
    fn is_clear(&self, entity_name: &str) -> bool {
        self.inner.read().is_clear(entity_name)
    }

    /// Return number of loaded sanctions entries across all lists.
    fn entry_count(&self) -> usize {
        self.inner.read().entries.len()
    }

    /// Return a dict of Prometheus-style metric counters.
    fn get_metrics(&self, py: Python<'_>) -> PyResult<PyObject> {
        let snap = self.inner.read().get_metrics_snapshot();
        let d = pyo3::types::PyDict::new(py);
        for (k, v) in snap {
            d.set_item(k, v)?;
        }
        Ok(d.into())
    }

    /// Health check: returns dict with `ok`, `entry_count`, `backend`.
    fn health_check(&self, py: Python<'_>) -> PyResult<PyObject> {
        let count = self.inner.read().entries.len();
        let d = pyo3::types::PyDict::new(py);
        d.set_item("ok", true)?;
        d.set_item("entry_count", count)?;
        d.set_item("backend", "rust_velocity")?;
        Ok(d.into())
    }
}

// ---------------------------------------------------------------------------
// Unit tests (cargo test)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_screener() -> SanctionsScreener {
        let mut s = SanctionsScreener::new(0.8);
        let mut map = HashMap::new();
        map.insert(
            "OFAC".to_string(),
            vec![
                "ACME SHELL CORP".to_string(),
                "DUMMY SANCTIONS ENTITY".to_string(),
                "TEST BLOCKED PARTY".to_string(),
            ],
        );
        map.insert(
            "EU".to_string(),
            vec!["EU BLOCKED ENTITY".to_string(), "TEST EU SANCTIONS".to_string()],
        );
        map.insert(
            "UN".to_string(),
            vec!["UN BLOCKED ENTITY".to_string(), "TEST UN SANCTIONS".to_string()],
        );
        s.load(map);
        s
    }

    #[test]
    fn test_clear_entity_passes() {
        let s = make_screener();
        assert!(s.is_clear("CLEAN COMPANY INC"));
    }

    #[test]
    fn test_exact_match_detected() {
        let s = make_screener();
        let hits = s.screen("ACME SHELL CORP");
        assert!(!hits.is_empty(), "ACME SHELL CORP must be flagged");
        assert!(hits[0].confidence >= 0.8);
    }

    #[test]
    fn test_partial_match_detected_jaccard() {
        let s = make_screener();
        // "TEST BLOCKED PARTY" shares 3/3 tokens with query — jaccard = 1.0
        let hits = s.screen("TEST BLOCKED PARTY");
        assert!(!hits.is_empty());
        let ofac_hits: Vec<_> = hits.iter().filter(|h| h.list_name == ListName::Ofac).collect();
        assert!(!ofac_hits.is_empty());
    }

    #[test]
    fn test_low_overlap_does_not_hit() {
        let s = make_screener();
        // "RANDOM WORD" shares no tokens with any sanctions entry
        let hits = s.screen("RANDOM WORD COMPANY UNRELATED");
        assert!(hits.is_empty(), "no overlap should produce no hits");
    }

    #[test]
    fn test_hash_never_contains_raw_name() {
        let s = make_screener();
        let hits = s.screen("TEST BLOCKED PARTY");
        for hit in hits {
            assert!(!hit.entity_name_hash.contains("TEST BLOCKED PARTY"));
            assert_eq!(hit.entity_name_hash.len(), 64);
        }
    }

    #[test]
    fn test_eu_list_detected() {
        let s = make_screener();
        let hits = s.screen("EU BLOCKED ENTITY");
        let eu_hits: Vec<_> = hits.iter().filter(|h| h.list_name == ListName::Eu).collect();
        assert!(!eu_hits.is_empty(), "EU BLOCKED ENTITY must be flagged on EU list");
    }

    #[test]
    fn test_un_list_detected() {
        let s = make_screener();
        let hits = s.screen("UN BLOCKED ENTITY");
        let un_hits: Vec<_> = hits.iter().filter(|h| h.list_name == ListName::Un).collect();
        assert!(!un_hits.is_empty(), "UN BLOCKED ENTITY must be flagged on UN list");
    }

    #[test]
    fn test_flush_clears_entries() {
        let mut s = make_screener();
        assert!(!s.is_clear("ACME SHELL CORP"));
        s.flush();
        assert!(s.is_clear("ACME SHELL CORP"), "after flush nothing should match");
    }

    #[test]
    fn test_case_insensitive_normalisation() {
        let s = make_screener();
        // Lowercase input should match because we normalise to uppercase
        let hits = s.screen("acme shell corp");
        assert!(!hits.is_empty(), "case-insensitive normalisation must work");
    }

    #[test]
    fn test_metrics_increment_on_screen() {
        let s = make_screener();
        s.screen("ACME SHELL CORP");
        s.screen("CLEAN COMPANY INC");
        let snap = s.get_metrics_snapshot();
        assert_eq!(snap["screens_total"], 2);
        assert!(snap["hits_total"] > 0, "ACME SHELL CORP should produce hits");
        assert!(snap["misses_total"] > 0, "CLEAN COMPANY INC should be a miss");
    }

    #[test]
    fn test_threshold_respected() {
        let mut s = SanctionsScreener::new(1.0); // only exact matches
        let mut map = HashMap::new();
        map.insert("OFAC".to_string(), vec!["EXACT ENTITY NAME".to_string()]);
        s.load(map);
        // Partial match: 2/3 tokens overlap → jaccard = 2/4 = 0.5 → below 1.0 threshold
        let hits = s.screen("EXACT ENTITY OTHER");
        assert!(hits.is_empty(), "partial match below threshold 1.0 should not fire");
        // Full exact match → jaccard = 1.0 → fires
        let hits = s.screen("EXACT ENTITY NAME");
        assert!(!hits.is_empty());
    }

    #[test]
    fn test_whitespace_name_trimmed() {
        let s = make_screener();
        let hits = s.screen("  ACME SHELL CORP  ");
        assert!(!hits.is_empty(), "leading/trailing whitespace must be trimmed before match");
    }

    /// SDN-style real-world test vectors (anonymised/representative).
    #[test]
    fn test_sdn_transliteration_gap() {
        // Current implementation does NOT handle transliterations.
        // "АКМЭ ШЕЛЛ КОРП" (Cyrillic) should NOT match "ACME SHELL CORP".
        // This test documents the known compliance gap (see sanctions audit).
        let s = make_screener();
        let hits = s.screen("АКМЭ ШЕЛЛ КОРП");
        assert!(
            hits.is_empty(),
            "Transliterated Cyrillic does not match (known gap — see audit doc)"
        );
    }

    #[test]
    fn test_alias_requires_explicit_entry() {
        // Aliases not in the loaded list will not be detected.
        // Callers must load aliases separately via the loader.
        let mut s = SanctionsScreener::new(0.8);
        let mut map = HashMap::new();
        map.insert("OFAC".to_string(), vec!["OFFICIAL NAME".to_string()]);
        s.load(map);
        // Alias not loaded — should be clear
        let hits = s.screen("UNOFFICIAL ALIAS");
        assert!(hits.is_empty(), "unloaded alias must not match");
    }
}
