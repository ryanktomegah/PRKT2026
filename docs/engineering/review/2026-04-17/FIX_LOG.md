# Fix Log — Pre-Lawyer Review 2026-04-17

Chronological record of every code/doc change made during the 4-week review.

Format per entry:
- **Severity:** Critical / High / Medium / Low
- **Problem:** what was wrong
- **Fix:** what was changed
- **Commit:** <hash>
- **Verification:** how we know it's fixed

---

## FIX-001 — 2026-04-17

- **Severity:** Critical
- **Problem:** `docs/business/bank-pilot/rbc-pilot-strategy.md:17` contained the phrase "your former division" in the Erica Nielsen row — a first-person admission that Ryan's internal RBC history was used to author the document. Direct leakage vector.
- **Fix:** Removed "your former division" from the Erica Nielsen row. New text: `LOW — retail-focused, not relevant to LIP`.
- **Commit:** 63096ed
- **Verification:** `grep -n "your former division" docs/business/bank-pilot/rbc-pilot-strategy.md` returns zero results.

---

## FIX-002 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/bank-pilot/rbc-pilot-strategy.md` was titled "Internal Planning Document" and headered "CONFIDENTIAL — BPI internal use only" — the "Internal" label and "CONFIDENTIAL" framing, if ever produced in litigation, reinforces that the document is an insider's operational plan rather than a post-separation founder's external strategy.
- **Fix:** Changed title to "BPI Planning Document"; changed header label from "CONFIDENTIAL" to "DRAFT".
- **Commit:** c187d6d
- **Verification:** File header now reads `DRAFT — BPI internal use only`.

---

## FIX-003 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/bank-pilot/rbc-pilot-strategy.md:47` attributed a verbatim personal quote to Sid Paquette ("What's the problem, what's the size of the prize, and why are you best suited to solve it?") — sounds like corridor/internal knowledge rather than a published public source.
- **Fix:** Replaced with neutral paraphrase citing rbcx.com intake guidance as the reference. Also removed matching first-person Sid Paquette attribution in Section 5 header.
- **Commit:** c187d6d
- **Verification:** No quoted phrase directly attributed to Sid Paquette by name in the file.

---

## FIX-004 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/bank-pilot/rbc-pilot-strategy.md:108` stated "RBC wants $1B in AI-generated enterprise value by 2027" — a specific internal financial target with no verifiable public source. Sounds like internal corridor knowledge.
- **Fix:** Replaced with "AI Group is actively seeking demonstrable AI use cases with revenue impact" — a neutral, publicly supportable characterisation.
- **Commit:** c187d6d
- **Verification:** No "$1B" AI target language in the file.

---

## FIX-005 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/GTM-Strategy-v1.0.md:185` listed "institutional knowledge of internal processes and people" as a *reason* RBC is the first target — an explicit self-incriminating statement that insider access was a selection criterion.
- **Fix:** Replaced with "Founder has prior banking experience" — neutral framing that conveys relevant background without claiming insider advantage.
- **Commit:** c187d6d
- **Verification:** No "institutional knowledge of internal processes" language in the file.

---

## FIX-006 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/GTM-Strategy-v1.0.md:186` contained "hunting for AI-generated P&L use cases" — internal-corridor framing with no public source attributable.
- **Fix:** Replaced with "mandate to scale AI use cases across the enterprise" — a neutral characterisation consistent with publicly reported AI Group mandate.
- **Commit:** c187d6d
- **Verification:** Phrase "hunting for AI-generated P&L" no longer present.

---

## FIX-007 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/GTM-Strategy-v1.0.md:189` attributed verbatim personal questions to Sid Paquette by name ("What's the problem? What's the size of the prize? Why are you best suited to solve it?").
- **Fix:** Replaced with neutral paraphrase citing RBCx's intake questions without direct personal attribution.
- **Commit:** c187d6d
- **Verification:** No quoted phrase attributed to Sid Paquette in the row.

---

## FIX-008 — 2026-04-17

- **Severity:** High
- **Problem:** `docs/business/GTM-Strategy-v1.0.md:194` stated "Bruce Ross's AI Group needs demonstrable AI P&L by 2027" — specific internal performance target with no public source.
- **Fix:** Replaced with "Bruce Ross's AI Group is actively seeking AI use cases with measurable revenue impact" — neutral, publicly supportable.
- **Commit:** c187d6d
- **Verification:** No "2027" AI P&L deadline language in the row.

---

## FIX-009 — 2026-04-17

- **Severity:** Critical
- **Problem:** `docs/business/GTM-Strategy-v1.0.md:196` (Founder framing) included "The Credit Management desk handles the fallout after these failures — I know what those conversations look like" — a direct admission that internal RBC operational knowledge (from Ryan's Credit Management Resolution Officer role) was used to frame the pitch. This is direct insider-knowledge leakage.
- **Fix:** Replaced the entire Founder framing with approved language from rbc-pilot-strategy.md Section 6, which uses only post-separation framing ("I have experience in Canadian banking operations, including at RBC. After leaving…").
- **Commit:** c187d6d
- **Verification:** No reference to "Credit Management desk" or internal operational conversations in the row.

---

## FIX-010 — 2026-04-17

- **Severity:** Medium (patent hygiene)
- **Problem:** `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part1.md:748-750` listed `RBCCoreAdapter`, `CitiCoreAdapter`, `BNSCoreAdapter` as example implementation class names in a patent-claim-adjacent spec. Per EPG-20/21, specs must not name specific banks in claim-bearing passages.
- **Fix:** Renamed all three to generic placeholders: `BankACoreAdapter`, `BankBCoreAdapter`, `BankCCoreAdapter`.
- **Commit:** c187d6d
- **Verification:** No bank-name-prefixed adapter names in the file.

---

## FIX-011 — 2026-04-17

- **Severity:** Medium (patent hygiene)
- **Problem:** `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part2.md:689` referenced `CitiCoreAdapter`, `RBCCoreAdapter` by name in the same patent-adjacent spec (Section 18.2).
- **Fix:** Replaced with `BankACoreAdapter`, `BankBCoreAdapter`.
- **Commit:** c187d6d
- **Verification:** No bank-name-prefixed adapter names in Part2.md.

---

## FIX-012 — 2026-04-18

- **Severity:** Low
- **Problem:** Revenue-share inconsistency in `docs/business/bank-pilot/commercial-overview.md`: Phase 1 summary tables state BPI=30% / Bank=70%, but the fee worked example (lines 95-96) states BPI=15% / Bank=85%. Flagged as a commercial-misrepresentation risk for any pilot bank reading contradictory revenue terms.
- **Fix:** Logged to Red-Flag Register as RFR-011 for commercial team triage. No content change applied — requires founder decision on the correct split before reconciliation.
- **Commit:** (no commit — tracking only)
- **Verification:** Entry RFR-011 present in `docs/legal/.red-flag-register.md`.
