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

---

## FIX-013 — 2026-04-17

- **Severity:** Low
- **Problem:** Code-quality re-review flagged two defects: (1) blockquote sentence-split in `docs/engineering/specs/BPI_C7_Component_Spec_v1.0_Part2.md` §18.2 — a prior fix had pulled "The adapter layer carries integration" inside the `>` continuation lines while "risk that does not resolve until pilot onboarding." dangled as a loose fragment below the blockquote, rendering as a broken separate paragraph; (2) LinkedIn citation for Bruce Ross in `docs/business/bank-pilot/rbc-pilot-strategy.md` was opaque about why LinkedIn was used instead of the 2024 Annual Report, leaving reader uncertain about source weight.
- **Fix:** (1) Restructured Part2 blockquote placement using Option A — sentence restored whole before the blockquote; blockquote placed on its own break between the paragraph and the Mitigation block, with no continuation lines trailing into prose. (2) Annotated LinkedIn citation as `[LinkedIn — role formed Feb 2026, post-dates 2024 Annual Report]` to make the source-weight choice transparent.
- **Commit:** cfa337b
- **Verification:** Both issues manually re-read in rendered Markdown preview; no `>` prefix missing on any continuation line; no stray sentence fragments dangle.

---

## FIX-014 — 2026-04-18

- **Severity:** High
- **Problem:** `docs/legal/patent/patent_claims_consolidated.md` lines 9–10 (original numbering) contained a block-quote attestation that explicitly named banned terms: "The terms AML, SAR, OFAC, PEP, money laundering, and tipping-off do not appear in these claims." Per EPG-21, no published patent document may contain any of these regulatory terms, including in self-compliance declarations.
- **Fix:** Deleted the two-line banned-term name-drop sentence from the block-quote. Retained the opening line referencing the substitution table. Block-quote collapsed from 3 lines to 1.
- **Commit:** (pending — backfill after commit)
- **Verification:** `grep -iP '\bAML\b|\bSAR\b|\bOFAC\b|\bPEP\b|money laundering|tipping-off' docs/legal/patent/patent_claims_consolidated.md` returns zero matches.

---

## FIX-015 — 2026-04-18

- **Severity:** High
- **Problem:** `docs/legal/patent/patent_claims_consolidated.md` line 43 (original numbering) — Dependent Claim 4 enumerated all 8 BLOCK codes as explicit claim elements: RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, LEGL. Per EPG-21: "Do not enumerate: the BLOCK code list must not appear in any claim — it is a circumvention roadmap. Claim the existence of the gate, not its contents." This is a structural EPG-21 Item 4 violation. The source document's own self-declaration of EPG-21 compliance was incorrect on both the banned-term and BLOCK-code dimensions.
- **Fix:** Collapsed enumeration to canonical EPG-21 Item 4 pattern.
  - **Before:** `...comprises at least the following ISO 20022 rejection reason codes: RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, and LEGL; wherein each code in the hold-type classification class independently triggers a hold-type classification outcome regardless of any other pipeline conditions.`
  - **After:** `...comprises at least a code in the non-bridgeable set defined in an internal taxonomy external to this claim, wherein each code in the hold-type classification class independently triggers a hold-type classification outcome regardless of any other pipeline conditions.`
- **Commit:** (pending — backfill after commit)
- **Verification:** `grep -P '\b(DNOR|CNOR|RR02|RR03|RR04|AG01|LEGL)\b' docs/legal/patent/patent_claims_consolidated.md` returns zero matches. `grep -P '\bRR01\b' docs/legal/patent/patent_claims_consolidated.md` returns exactly 2 matches (CBDC normalization tables, lines 81 and 215 post-edit).

---

## FIX-016 — 2026-04-18

- **Severity:** High
- **Problem:** `docs/legal/patent/patent_claims_consolidated.md` line 256 (original numbering) — Cross-Patent Notes section contained a self-attestation sentence: "No AML, SAR, OFAC, PEP, or money laundering language appears in any claim." This sentence (a) names banned terms, violating EPG-21, and (b) is a self-compliance declaration that is attorney's work, not claimant's work.
- **Fix:** Replaced the paragraph with the operational note only. Removed the banned-term name-drop and the self-compliance attestation. Retained the substitution-table reference and the terminology-in-use note.
- **Commit:** (pending — backfill after commit)
- **Verification:** `grep -iP '\bAML\b|\bSAR\b|\bOFAC\b|\bPEP\b|money laundering' docs/legal/patent/patent_claims_consolidated.md` returns zero matches.

---

## FIX-017 — 2026-04-18

- **Severity:** High
- **Problem:** `docs/legal/patent/patent_claims_consolidated.md` line 260 (original numbering) — "What Is Deliberately Not Claimed" section contained: "The enumeration in Family 1 Dependent Claim 4 uses open 'comprising at least' language and covers only the hold-type class, not the hard-block class. The hard-block code list belongs in the specification description only." After FIX-015 collapsed the enumeration, this sentence is (a) factually false (no enumeration remains in the claim) and (b) a self-defending legal argument that does not belong in a claim document.
- **Fix:** Replaced the stale/false rationale with: "The specific enumeration of ISO 20022 rejection codes that trigger a hold-type outcome is held in the internal taxonomy referenced by the claim, and is not disclosed in any independent or dependent claim." The leading EPG-21 sentence ("Per EPG-21: the specific enumeration…does not appear in any independent claim") was retained.
- **Commit:** (pending — backfill after commit)
- **Verification:** No reference to Dependent Claim 4 enumeration in the "What Is Deliberately Not Claimed" section; replaced with taxonomy-reference sentence. Triggered by FIX-015.

---

## FIX-018 — 2026-04-18

- **Severity:** Low (decision log — no edit applied)
- **Problem:** `docs/legal/patent/patent_claims_consolidated.md` contains RR01 at lines 82 and 216 (original numbering; lines 81 and 215 post-edit) inside CBDC normalization prose and translation tables. Flagged during EPG-21 BLOCK-code sweep.
- **Fix:** No edit applied. INTENTIONALLY RETAINED. Rationale: these occurrences are functional ISO-code mappings in CBDC normalization mechanism descriptions (`CBDC-KYC01 to RR01`), not BLOCK-code enumerations in claim bodies. EPG-21 scope targets claim-body enumerations of BLOCK codes as a circumvention roadmap; single-code appearances in technical mechanism descriptions are not in scope.
- **Commit:** no commit — decision record only
- **Verification:** Flag for counsel confirmation during lawyer session. Counsel should confirm whether RR01 appearances in CBDC normalization tables are acceptable or should be obfuscated further.
