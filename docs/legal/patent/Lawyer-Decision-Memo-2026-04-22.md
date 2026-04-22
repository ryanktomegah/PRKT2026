# Lawyer Decision Memo
## Open Audit Findings Requiring Counsel

**Date:** 2026-04-22
**Prepared from:** `Bridgepoint_Master_Audit_Report.md` and `docs/engineering/Audit-findings-tracking.md`
**Purpose:** isolate the remaining issues that are no longer drafting problems and now require legal or tax advice before filing or pilot launch.

---

## Snapshot

Document-side remediation is substantially complete. The audit tracker now shows `42/48` findings completed. The remaining open items are counsel-dependent decisions, not missing writeups.

## Open Items

### 1. Micro-Entity Eligibility Confirmation

**Audit finding:** #4

**Why counsel is needed:** The documents still assume USPTO micro-entity pricing in places, but eligibility depends on inventor filing history, prior-year income threshold, and assignment status. Filing at micro-entity rates without qualification creates avoidable enforceability risk.

**Decision needed from counsel:**
- Is micro-entity status defensible for the inventor at the planned utility filing date?
- If not clearly defensible, should Bridgepoint default to small-entity fees instead?

**Recommended output:** one-paragraph written determination for the filing record.

### 2. Claim 1 / Claim-Scope Review of Residual Narrowing Risk

**Audit finding:** #5

**Why counsel is needed:** The current prosecution-ready draft removed the original absolute-language issue identified in the older audit cycle, but counsel should still confirm that the trigger-distinction language now used in the independent claims preserves the intended doctrine-of-equivalents position and does not create a new narrowing problem in prosecution.

**Decision needed from counsel:**
- Does the current trigger language distinguish Bottomline cleanly without over-narrowing the claim set?
- Are there any phrases counsel wants softened or relocated before P2 drafting begins?

**Recommended output:** markup or short written redline guidance on Claim 1 and related trigger language in Claims 2-4.

### 3. Continuation vs. CIP Determination for P6, P7, and P8

**Audit finding:** #17

**Why counsel is needed:** The portfolio architecture now states the caveat explicitly, but only counsel can determine whether the foundational provisional package supports pure continuation treatment for the CBDC, tokenized receivable, and autonomous treasury extensions, or whether any of them require continuation-in-part treatment.

**Decision needed from counsel:**
- For P6, P7, and P8, does the filed parent disclosure support continuation claims under 35 U.S.C. `§120`?
- If not, which claim families need CIP treatment, and what is the practical filing-sequencing consequence?

**Recommended output:** extension-by-extension table with columns: `Pure continuation support`, `CIP required`, `Reason`, `Urgency`.

### 4. Lending-Licence / Regulatory-Structure Opinion

**Audit finding:** #40

**Why counsel is needed:** This is the main remaining non-document blocker to pilot launch. The playbook now frames the issue, but the company still needs an actual legal opinion on whether the contemplated bridge structure requires lending licences in British Columbia and related operating jurisdictions, or whether the bank-partnered structure keeps Bridgepoint outside licensing scope.

**Decision needed from counsel:**
- Does Bridgepoint require a lending or money-lender licence for the Phase 1 pilot structure in British Columbia?
- If the answer depends on structure, which structure is safest: bank-funded pilot, shadow-mode pilot, marketplace model, or another path?
- What additional steps are required before any live-funded pilot?

**Recommended output:** written regulatory opinion covering BC first, with notes on Ontario and any near-term cross-border implications.

## Suggested Counsel Review Order

1. Lending-licence / pilot-structure opinion
2. Micro-entity eligibility confirmation
3. Continuation vs. CIP table for P6/P7/P8
4. Final claim-scope review of trigger language

## Documents To Hand To Counsel

- `docs/legal/patent/Provisional-Specification-v5.3.md`
- `docs/legal/patent/Future-Technology-Disclosure-v2.1.md`
- `docs/legal/patent/Patent-Family-Architecture-v2.1.md`
- `docs/operations/Operational-Playbook-v2.1.md`
- `docs/engineering/Audit-findings-tracking.md`
- `Bridgepoint_Master_Audit_Report.md`

## Suggested Email Subject

`Bridgepoint: four pre-filing legal decisions requiring counsel review`

