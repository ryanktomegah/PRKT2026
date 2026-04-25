# EPG-21 Language Scrub Audit Report

**Task:** 3.2 (Pre-Lawyer Review, Day 3)
**Date:** 2026-04-18
**EPG Reference:** EPG-20 / EPG-21
**Scope:** 4 Publishable patent docs (per Task 3.1 classification, commit 9f4e0c1)
**Status:** AUDIT ONLY — no fixes applied in this task; fixes deferred to Task 3.3

---

## Scope

**Files scanned (4 publishable):**
1. `docs/legal/patent/Provisional-Specification-v5.2.md`
2. `docs/legal/patent/Provisional-Specification-v5.1.md`
3. `docs/legal/patent/patent_claims_consolidated.md`
4. `docs/legal/patent/Future-Technology-Disclosure-v2.1.md`

**Files skipped (2 internal-only):**
- `docs/legal/patent/Patent-Family-Architecture-v2.1.md` — internal-only per Task 3.1 classification; not filing-bound
- `docs/legal/patent/patent_counsel_briefing.md` — internal-only; intentionally contains banned terms as the substitution-table source document. Grepping it would produce false positives.

---

## Section 1 — Banned-term violations (per file)

Pattern applied (case-insensitive, word-boundary): `\bAML\b|\bSAR\b|\bOFAC\b|\bSDN\b|compliance investigation|tipping-off|suspicious activity|\bPEP\b`

### Provisional-Specification-v5.2.md

- **Banned-term matches:** 0

Zero banned-term matches. No replacements required.

---

### Provisional-Specification-v5.1.md

- **Banned-term matches:** 0

Zero banned-term matches. No replacements required.

---

### patent_claims_consolidated.md

- **Banned-term matches:** 3 (lines 9, 10, 256 — all in internal-facing header/footer commentary, not in claim body text)

| Line | Term | Matched line (trimmed) |
|---|---|---|
| 9 | AML, SAR, OFAC, PEP | `> substitution table in 'patent_counsel_briefing.md'. The terms AML, SAR, OFAC, PEP,` |
| 10 | tipping-off | `> money laundering, and tipping-off do not appear in these claims.` |
| 256 | AML, SAR, OFAC, PEP | `All claims use the substitution table from 'patent_counsel_briefing.md'. No AML, SAR, OFAC, PEP, or money laundering language appears in any claim.` |

**Context note:** Lines 9–10 are inside a block-quote preamble (prefixed `>`). Line 256 is a trailing attestation comment. Both are meta-commentary asserting EPG-21 compliance — they are NOT claim text. However, they name banned terms in a publishable document. EPG-21 prohibits these terms "anywhere in published spec" without qualification; the attestation context does not exempt them.

**Proposed replacement (not applied — for Task 3.3 reference):**
- Lines 9–10 block-quote: Remove the term enumeration entirely; replace with a generic reference — e.g., `"The terms in the EPG-21 substitution table do not appear in these claims."`
- Line 256 attestation: Same — replace with `"All claims use the EPG-21 substitution table. No prohibited language appears in any claim."`

---

### Future-Technology-Disclosure-v2.1.md

- **Banned-term matches:** 0

Zero banned-term matches. No replacements required.

---

## Section 2 — BLOCK-code enumeration violations

### Co-location (multiline DNOR…CNOR within 200 chars)

| File | Line | Co-located codes | Context |
|---|---|---|---|
| `patent_claims_consolidated.md` | 43 | RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, LEGL (all 8) | Dependent Claim 4 — "Hold-Type Code Enumeration (Open)" — full enumerated list as claim elements |

### Individual BLOCK-code occurrences

| File | Line | Code(s) | Context |
|---|---|---|---|
| `patent_claims_consolidated.md` | 43 | RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, LEGL | Dependent Claim 4 body — all 8 BLOCK codes enumerated as required hold-type classification members |
| `patent_claims_consolidated.md` | 82 | RR01 | Dependent Claim 3 (System claim set) — CBDC normalization translation table: `CBDC-KYC01 to RR01` |
| `patent_claims_consolidated.md` | 216 | RR01 | Independent Claim 1 (CBDC Normalization set) — `CBDC KYC failures into RR01` |
| `Provisional-Specification-v5.2.md` | — | none | Zero BLOCK-code occurrences |
| `Provisional-Specification-v5.1.md` | — | none | Zero BLOCK-code occurrences |
| `Future-Technology-Disclosure-v2.1.md` | — | none | Zero BLOCK-code occurrences |

---

## Section 3 — Structural concerns (beyond word-substitution)

### Concern 3-A: Dependent Claim 4 — Full BLOCK-code enumeration in a filed claim (CRITICAL)

**File:** `patent_claims_consolidated.md`, line 43
**Claim:** Dependent Claim 4, titled "Hold-Type Code Enumeration (Open)"

The claim text reads:

> "…wherein the hold-type classification class comprises **at least** the following ISO 20022 rejection reason codes: **RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, and LEGL**; wherein each code in the hold-type classification class independently triggers a hold-type classification outcome regardless of any other pipeline conditions."

This directly violates EPG-21 Item 4: *"the BLOCK code list must not appear in any claim."*

The "at least" open-ended language does not mitigate the concern — it enumerates the exact circumvention-roadmap set as claim elements, which discloses the non-bridgeable taxonomy to adversarial actors. This is precisely the pattern EPG-21 was designed to prevent.

**This cannot be resolved by word-substitution alone.** The entire claim needs restructuring — either:
1. Remove Dependent Claim 4 from the filing, OR
2. Redraft to claim the existence and function of the classification gate without enumerating its members, e.g., *"wherein the hold-type classification class is defined by a non-bridgeable code registry maintained separately from this specification."*

Counsel must weigh in before filing. This is a **blocking structural concern** for Task 3.3.

---

### Concern 3-B: RR01 in CBDC normalization claims (lines 82 and 216) — Low-risk but flag for counsel

**File:** `patent_claims_consolidated.md`, lines 82 and 216

`RR01` (Regulatory Reason 01 — KYC failure) appears in two claims as part of a CBDC failure-code translation table (`CBDC-KYC01 → RR01`). Unlike the Dependent Claim 4 enumeration, these are translation-mapping claims rather than an enumeration of the non-bridgeable set — they do not enumerate BLOCK codes as a hold-type class.

`RR01` is also a valid ISO 20022 code outside the BLOCK context (it is used for KYC normalization across many rail types). Whether its appearance here constitutes a BLOCK-code disclosure is contextually ambiguous.

**Assessment:** Lower risk than Concern 3-A, but counsel should confirm whether `RR01` appearing in the CBDC normalization chain connects readers to the BLOCK taxonomy. A conservative fix would be to use the generic form ("a KYC failure rejection reason code") rather than the specific code value.

**This is a counsel-decision item, not a word-substitution item.**

---

## Section 4 — Replacement mapping (EPG-21 canonical map, for Task 3.3)

| Banned Term | Context-sensitive replacements |
|---|---|
| AML | `classification gate` / `hold type discriminator` (context-dependent) |
| SAR | remove, or `procedural hold` |
| OFAC | remove, or `procedural hold` |
| SDN | remove, or `procedural hold` |
| compliance investigation | `investigatory hold` |
| tipping-off | remove (entire clause usually needs rephrasing) |
| suspicious activity | `procedural hold` / `bridgeability flag` |
| PEP | remove, or `investigatory hold` |
| BLOCK-code list | Collapse to: "a code in the non-bridgeable set (see internal taxonomy)" |

**Task 3.3 note on `patent_claims_consolidated.md` lines 9, 10, 256:** The banned terms appear only in meta-commentary/attestation text, not in claim bodies. The replacement action is deletion of the enumeration, not substitution — see Section 1 findings above.

---

## Summary

- **Total files audited:** 4
- **Files with any banned-term match:** 1 (`patent_claims_consolidated.md` — meta-commentary only, not claim body)
- **Files with any BLOCK-code enumeration:** 1 (`patent_claims_consolidated.md`)
- **Structural (claim-restructuring) concerns:** 2 (Concerns 3-A and 3-B; 3-A is blocking)
- **Total distinct line-level findings:** 6
  - Banned-term: lines 9, 10, 256 (3 lines)
  - BLOCK-code: lines 43, 82, 216 (3 lines)
- **Files clean across all checks:** 3 (v5.2, v5.1, FTD-v2.1)

---

## Escalation flags for Task 3.3

### FLAG 1 — BLOCKING: Dependent Claim 4 requires claim restructuring before filing

`patent_claims_consolidated.md` line 43 enumerates all 8 BLOCK codes as claim elements in Dependent Claim 4. This is a structural violation of EPG-21 Item 4 that word-substitution cannot resolve. Task 3.3 must **not** simply delete the code names and leave the claim structure intact — the claim itself must be redrafted or removed. **Counsel decision required before filing.**

### FLAG 2 — COUNSEL DECISION: RR01 in CBDC normalization claims

`patent_claims_consolidated.md` lines 82 and 216 reference `RR01` in a translation-mapping context rather than as a BLOCK-code enumeration. Whether this constitutes a BLOCK-code disclosure is ambiguous. Counsel should confirm whether conservative replacement (generic ISO code description) is warranted.

### FLAG 3 — MINOR: Banned-term names in attestation commentary

`patent_claims_consolidated.md` lines 9, 10, and 256 name banned terms (AML, SAR, OFAC, PEP, tipping-off) in meta-commentary asserting their absence from the claims. EPG-21 prohibits these terms anywhere in the published spec. Task 3.3 can resolve these by word-substitution/deletion without founder or counsel input.
