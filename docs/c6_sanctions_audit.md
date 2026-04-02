# C6 Sanctions Logic Audit

**Date:** 2026-04-02  
**Author:** CIPHER (C6 AML Security Domain)  
**Status:** APPROVED — Rust port confirmed compliance-parity with Python

---

## 1. Purpose

This document audits the existing `sanctions.py` matching logic before the C6
Rust migration (Priority 4) to ensure the Rust port does not regress compliance.
It documents:

- The exact matching algorithm used
- What the algorithm does and does not cover
- Known compliance gaps
- Test vectors used to verify parity between Python and Rust backends
- Recommendations for closing gaps in a future revision

---

## 2. Current Python Matching Logic (`sanctions.py`)

### 2.1 Normalisation

All entity names are normalised to **uppercase with leading/trailing whitespace
stripped** before comparison:

```python
normalized = entity_name.upper().strip()
```

### 2.2 Matching Algorithm: Jaccard Token-Overlap

The screener uses **Jaccard token-overlap similarity** (`_fuzzy_match`):

```
jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

where A and B are the token sets of the query and sanctions entry,
respectively, after splitting on whitespace.

**Hit threshold:** `confidence >= 0.8`

Only hits meeting this threshold are returned by `screen()`.

### 2.3 Privacy — Entity Name Hashing

Raw entity names are **never stored**. `SanctionsHit.entity_name_hash` is the
SHA-256 digest of the normalised name:

```python
name_hash = hashlib.sha256(normalized.encode()).hexdigest()
```

This satisfies GDPR Art.25 data minimisation for AML record-keeping.

---

## 3. What the Current Algorithm Covers

| Capability | Supported | Notes |
|---|---|---|
| Exact full match | ✅ | Jaccard = 1.0 when A = B |
| All-token overlap | ✅ | Jaccard = 1.0 |
| High-overlap partial match | ✅ | Jaccard ≥ 0.8 (e.g. 4/5 tokens shared) |
| Case-insensitive matching | ✅ | Normalised to uppercase |
| Leading/trailing whitespace | ✅ | `.strip()` applied |
| Multi-list (OFAC, EU, UN) | ✅ | Scans all three lists |
| Alias resolution | ⚠️ | Only if alias is explicitly loaded in the JSON list |
| Transliterated names (Cyrillic, Arabic, etc.) | ❌ | **Known gap — see §4** |
| Phonetic matching (Soundex, Metaphone) | ❌ | **Known gap — see §4** |
| Name component reordering (surname/forename swap) | ⚠️ | Partial: tokens are unordered sets, so "JOHN SMITH" matches "SMITH JOHN" |
| Abbreviated names ("IBM" → "INTERNATIONAL BUSINESS MACHINES") | ❌ | **Known gap** |

---

## 4. Known Compliance Gaps

### Gap 1: No Transliteration / Script Normalisation

OFAC SDN entries frequently include names transliterated from Arabic, Cyrillic,
Chinese, Korean, and other scripts into Latin characters. The current
implementation does **not** perform reverse transliteration — a Cyrillic
query ("АКМЭ ШЕЛЛ КОРП") will not match the Latin SDN entry ("ACME SHELL CORP").

**Impact:** Queries submitted in non-Latin scripts will produce false negatives
on current SDN entries.

**Regulatory expectation:** OFAC Guidance on Sanctions Compliance Programs
(May 2019) explicitly requires "reasonable and comprehensive" screening of
transliterated names.

**Recommendation:** Integrate a transliteration library (e.g. `anyascii` in
Python, or a Rust transliteration crate such as `unidecode`) to normalise
non-Latin scripts to ASCII before matching. This is a **Tier 1** gap requiring
remediation before production bank deployment.

### Gap 2: No Phonetic Matching

Names may be misspelled (e.g. "AKME SHEL CORP") and still refer to a sanctioned
entity. Phonetic algorithms (Soundex, Double Metaphone, Jaro-Winkler) would
catch these.

**Recommendation:** Add a Jaro-Winkler pass for token-level matching (threshold
≥ 0.9 per token) alongside the Jaccard set-level check. This is a **Tier 2** gap.

### Gap 3: Alias Loading is Manual

Aliases must be loaded into the sanctions JSON by the `sanctions_loader.py`
tool. If the loader does not extract all alias fields from the source lists
(OFAC SDN, UN XML, EU CFSP XML), those aliases will not be screened.

The `sanctions_loader.py` does extract `NAME_ORIGINAL_SCRIPT` (UN XML) and
`nameAlias/@wholeName` (EU XML). OFAC SDN aliases are in separate AKA records
not yet extracted by the current loader.

**Recommendation:** Extend `fetch_ofac_names()` to also extract AKA records
(column 11 in SDN CSV). This is a **Tier 2** gap.

---

## 5. Rust Port — Compliance Parity Verification

The Rust implementation (`lip/c6_aml_velocity/rust_velocity/src/sanctions.rs`)
uses **identical Jaccard token-overlap logic** as the Python implementation.

Key design decisions in the Rust port:

1. **Aho-Corasick pre-filter**: Built from all loaded entries. Any query that
   contains a loaded entry as a substring is identified instantly (O(n+m)).
   This serves as a fast path for exact substring matches, which receive a
   confidence bonus (max capped at 1.0).

2. **Full Jaccard scan**: All entries are scanned with Jaccard similarity —
   same as Python. The AC pre-filter does not replace the Jaccard scan; it
   supplements it.

3. **Same normalisation**: Uppercase + strip, identical to Python.

4. **Same threshold**: 0.8, configurable on `PySanctionsScreener(threshold=...)`.

### Parity Test Results

| Test Vector | Python Result | Rust Result | Match |
|---|---|---|---|
| `"ACME SHELL CORP"` vs OFAC | HIT (1.0) | HIT (1.0) | ✅ |
| `"acme shell corp"` (lowercase) | HIT | HIT | ✅ |
| `"  ACME SHELL CORP  "` (whitespace) | HIT | HIT | ✅ |
| `"ACME SHELL COMPANY"` (2/4 overlap, 0.5) | MISS | MISS | ✅ |
| `"TEST BLOCKED PARTY"` vs OFAC | HIT | HIT | ✅ |
| `"EU BLOCKED ENTITY"` vs EU | HIT | HIT | ✅ |
| `"UN BLOCKED ENTITY"` vs UN | HIT | HIT | ✅ |
| `"CLEAN COMPANY INC"` | MISS | MISS | ✅ |
| `"АКМЭ ШЕЛЛ КОРП"` (Cyrillic) | MISS | MISS | ✅ (known gap, consistent) |
| `"ACME FRONT COMPANY"` (unloaded alias) | MISS | MISS | ✅ |

**Conclusion: Zero compliance regressions from the Rust port.** Both backends
produce identical results for all test vectors. The known transliteration gap
exists in both and must be addressed in a future iteration (not introduced by
the Rust migration).

---

## 6. Test Coverage

Compliance parity is verified by:

- `lip/tests/test_c6_rust_velocity.py` — Python-level parity and bridge tests  
  - `TestSanctionsComplianceVectors` — all audit vectors above  
  - `TestRustPythonParityVelocity` — velocity backend parity
  - `TestPythonFallbackPath` — bridge fallback behaviour

- `lip/c6_aml_velocity/rust_velocity/src/sanctions.rs` (Rust unit tests)  
  - 10 unit tests covering exact match, Jaccard, EU/UN list, flush, metrics, and
    the transliteration gap documentation test

---

## 7. Recommendations Summary

| Priority | Gap | Action |
|---|---|---|
| **Tier 1 — Required before bank pilot** | No transliteration | Add `anyascii` / Rust `unidecode` normalisation pass |
| **Tier 2 — Recommended** | No phonetic matching | Add Jaro-Winkler token-level similarity |
| **Tier 2 — Recommended** | OFAC AKA records not loaded | Extend `fetch_ofac_names()` to parse AKA CSV column |
| **Tier 3 — Future** | No abbreviation resolution | Map common abbreviations ("IBM" → "INTERNATIONAL BUSINESS MACHINES") |

---

## 8. Sign-off

| Role | Decision |
|---|---|
| **CIPHER** | ✅ Rust port approved — compliance-parity confirmed, known gaps documented |
| **REX** | ⚠️ Tier 1 transliteration gap must be closed before bank pilot |
| **QUANT** | N/A — no fee arithmetic in sanctions module |
