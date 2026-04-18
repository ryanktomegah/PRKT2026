# Patent Document Publication-Scope Classification

**Task:** 3.1 (Pre-Lawyer Review, Day 3)
**Date:** 2026-04-18
**EPG Reference:** EPG-20 / EPG-21
**Purpose:** Determine which patent docs require the EPG-21 language scrub (Task 3.3) by separating publishable content from internal strategy memos.

---

## Classification Criteria

**Publishable** — content will appear in the filed patent or a public filing (the provisional specification, the claims, a technology disclosure intended for USPTO/external consumption). Test: "If this file's content were to appear verbatim in a USPTO filing or public patent document, is that intentional?" If yes → Publishable.

**Internal-only** — counsel briefing memos, family/architecture strategy, prosecution roadmaps, continuation planning. Test: "Is this a working document FOR our patent counsel rather than content FROM the patent?" If yes → Internal-only. These are attorney work-product / privileged strategy memos.

**Unknown** — the file's intent is genuinely ambiguous (e.g., mixes public claim language with internal strategy commentary). Flag for user decision. Used sparingly — default to stronger signal.

---

## Classification Table

| File | Classification | Evidence | Scrub Required? |
|---|---|---|---|
| `docs/legal/patent/Provisional-Specification-v5.2.md` | **Publishable** | `Status: For Filing — Date To Be Confirmed at Attorney Engagement` | **Yes** |
| `docs/legal/patent/Provisional-Specification-v5.1.md` | **Publishable** | `Status: For Filing — Date To Be Confirmed at Attorney Engagement` | **Yes** — superseded but still a filing-ready draft |
| `docs/legal/patent/patent_claims_consolidated.md` | **Publishable** | `For Patent Counsel Review — Pre-Non-Provisional Filing` — clean claim language formatted as USPTO claims | **Yes** |
| `docs/legal/patent/Future-Technology-Disclosure-v2.1.md` | **Publishable** | `Priority Date: To be established at provisional patent filing — all extensions described herein are to be preserved for claim with that priority date`; contains Draft Claim Elements for each extension | **Yes** |
| `docs/legal/patent/Patent-Family-Architecture-v2.1.md` | **Internal-only** | `This is a strategic roadmap, not a legal filing. It tells you what to file, when to file it…`; `Confidentiality: Strictly Confidential — Attorney-Client Privileged — Do Not Distribute` | No |
| `docs/legal/patent/patent_counsel_briefing.md` | **Internal-only** | `EPG-20 / EPG-21 — Handle in single session before non-provisional filing`; a briefing memo instructing counsel on what to claim and what to avoid — no claim text of its own | No |

---

## Per-File Notes

### Provisional-Specification-v5.2.md

- **Classification:** Publishable
- **Primary evidence:** `"Document Version: 5.2 — Prosecution-Ready (§101 Re-Anchor)"` and `"Status: For Filing — Date To Be Confirmed at Attorney Engagement"` — the document explicitly declares itself the filing artefact.
- **Secondary signal:** Supersedes v5.1; v5.2 is the current "for filing" version. Contains complete independent claims (Claims 1–5) and dependent claims D1–D13 with formal USPTO-formatted claim language.
- **Scrub implications:** This is the primary scrub target for Task 3.3. Must be checked for all EPG-21 banned terms. Note that `patent_claims_consolidated.md` line 8 states the scrub has already been applied there — v5.2 must be independently verified since it was drafted before EPG-21 was codified.

---

### Provisional-Specification-v5.1.md

- **Classification:** Publishable
- **Primary evidence:** `"Status: For Filing — Date To Be Confirmed at Attorney Engagement"` — same declaration as v5.2; this was the filing-ready version before the §101 Recentive correction.
- **Secondary signal:** Formally superseded by v5.2 (v5.2 metadata reads `"Supersedes: v5.1"`). However, it remains a filing-ready provisional draft and its content could be filed if v5.2 were abandoned. It contains the identical claim set to v5.2 plus the now-removed Recentive citation; it warrants scrubbing for completeness and to prevent the superseded draft from leaking regulated language.
- **Scrub implications:** Lower priority than v5.2 (superseded), but the claim text is identical and any banned terms present in v5.1 are almost certainly present in v5.2. Scrubbing both is correct.

---

### patent_claims_consolidated.md

- **Classification:** Publishable
- **Primary evidence:** `"For Patent Counsel Review — Pre-Non-Provisional Filing"` — content is structured as formal USPTO claim language across four patent families. Line 8 also contains a self-declared scrub note: `"Language scrub rule (EPG-21): All regulatory language has been replaced per the substitution table in patent_counsel_briefing.md. The terms AML, SAR, OFAC, PEP, money laundering, and tipping-off do not appear in these claims."` This declaration must be verified by Task 3.2 grep — it is a claim, not a guarantee.
- **Secondary signal:** Contains Patent Families 1–4 with independent and dependent claims in formal claim-draft structure, plus adversarial training data claim language. Filename lacks a version suffix, suggesting it is a working consolidated draft rather than a finalized artefact — but its content is unambiguously claim text.
- **Scrub implications:** File asserts it is already scrubbed. Task 3.2 grep must confirm. If banned terms are found, Task 3.3 must correct them despite the self-declaration.

---

### Future-Technology-Disclosure-v2.1.md

- **Classification:** Publishable
- **Primary evidence:** `"Priority Date: To be established at provisional patent filing — all extensions described herein are to be preserved for claim with that priority date"` — the document's explicit legal function is to establish prior disclosure for continuation filings. It is the disclosure record that will support P3–P10 at USPTO. Each extension section includes `"Draft Claim Elements for Continuation Filing"` with formal claim-element language (e.g., `"(a) analysing a historical and forward-looking payment receipt data stream…"`).
- **Secondary signal:** `"Document Version: 2.1 — Prosecution-Ready"`. The FTD is not itself filed at USPTO, but its contents are functionally equivalent to a continuation provisional — they constitute the technical disclosure record upon which continuation claims will rest. If the continuation application text quotes or reproduces these elements, the language becomes public. Treating as publishable is correct.
- **Scrub implications:** Contains detailed technical descriptions of seven system extensions, including Extension G (Adversarial Cancellation Detection) with AML-adjacent terminology risk. EPG-21 scrub required. Also note: BLOCK code enumeration risk is elevated here because the Draft Claim Elements sections may enumerate hold codes when describing gatekeeping logic.

---

### Patent-Family-Architecture-v2.1.md

- **Classification:** Internal-only
- **Primary evidence:** `"This is a strategic roadmap, not a legal filing. It tells you what to file, when to file it, what each patent covers, and why the filing order matters."` (HOW TO READ THIS DOCUMENT block, line 21). Also: `"Confidentiality: Strictly Confidential — Attorney-Client Privileged — Do Not Distribute"`.
- **Secondary signal:** Contains royalty projections, prosecution strategy instructions (e.g., `"Resist narrowing at every stage. Argue for broad interpretation."`), continuation filing calendar, competitive threat analysis, and the Akamai design-around strategy. None of this is claim text or specification content.
- **Scrub implications:** Internal-only — out of scope for EPG-21 scrub. Noted for completeness: this document contains candid strategy commentary (e.g., prosecution resistance instructions, competitor analysis) that would be damaging if disclosed. Its confidential status should be maintained.

---

### patent_counsel_briefing.md

- **Classification:** Internal-only
- **Primary evidence:** `"EPG-20 / EPG-21 — Handle in single session before non-provisional filing"` — framed as an agenda item for a counsel briefing session, not as content to be filed. Contains the EPG-21 substitution table (the instruction to counsel on what to replace) rather than claim text.
- **Secondary signal:** 75 lines total; no claims, no technical specification sections, no claim-element language. The document tells counsel what the invention is, what to claim, what language to avoid, and what NOT to claim (the B2 enumeration). Pure briefing memo structure.
- **Scrub implications:** Internal-only — out of scope for EPG-21 scrub. This document is the SOURCE of the EPG-21 substitution table, so it necessarily contains banned terms (they appear in the left column of the substitution table). This is correct and expected — a briefing memo for counsel documenting what terms to remove is not itself a publishable filing.

---

## Summary

- **Total files:** 6
- **Publishable:** 4 → feed into Task 3.2 grep scope
  - `Provisional-Specification-v5.2.md` (primary — current for-filing version)
  - `Provisional-Specification-v5.1.md` (superseded but scrub warranted)
  - `patent_claims_consolidated.md` (self-declares scrub complete — requires Task 3.2 verification)
  - `Future-Technology-Disclosure-v2.1.md` (prosecution-ready disclosure underpinning P3–P10)
- **Internal-only:** 2 → out of scope for EPG-21 scrub
  - `Patent-Family-Architecture-v2.1.md`
  - `patent_counsel_briefing.md`
- **Unknown:** 0

---

## Open Items

None. All 6 files classified without ambiguity.

**Advisory for Task 3.2 (grep scope):** Run banned-term grep against these 4 files only:
1. `docs/legal/patent/Provisional-Specification-v5.2.md`
2. `docs/legal/patent/Provisional-Specification-v5.1.md`
3. `docs/legal/patent/patent_claims_consolidated.md`
4. `docs/legal/patent/Future-Technology-Disclosure-v2.1.md`

**Advisory for Task 3.3 (scrub):** `patent_claims_consolidated.md` self-declares EPG-21 compliance at line 8. Do not skip it from Task 3.2 verification on the strength of that declaration — verify first, then determine whether Task 3.3 work is required on that file.
