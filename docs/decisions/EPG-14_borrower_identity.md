# EPG-14 — Who Is the Borrower: B2B Interbank, Originating Bank

**Status:** 🟡 Code fixed; legal contract open
**Decided:** 2026-03-18
**Decision authority:** REX (final), unanimous team
**Source rationale:** [`/CLAUDE.md`](../../CLAUDE.md) § EPG-14
**Related:** [`EPG-19_compliance_hold_bridging.md`](EPG-19_compliance_hold_bridging.md), [`EPG-04-05_hold_bridgeable.md`](EPG-04-05_hold_bridgeable.md)

---

## Decision

The Master Receivables Financing Agreement (MRFA) runs to the **enrolled originating bank BIC** (e.g. Deutsche Bank), not the end customer (e.g. Siemens). LIP bridge loans are **B2B interbank credit facilities**, not consumer or SMB credit.

## Why this matters

The naive framing — "LIP funds the customer until their failed payment goes through" — would make BPI a consumer/SMB lender in every jurisdiction it operates in. That triggers consumer credit licensing in most jurisdictions, KYC obligations on the end customer (which BPI cannot perform without seeing the bank's KYC file), GDPR Art. 26 co-controllership, and a long list of capital and disclosure rules that make the model uneconomic.

The B2B interbank framing avoids all of that. The bank is the borrower, the bank already has KYC on its own customer, and the credit risk LIP prices is the **bank's** PD (near-zero for a Tier 1 institution), not the end customer's. The end customer is a beneficiary of the funded payment, not a counterparty to LIP.

## Required actions

Five actions must be complete before the B2B structure is operationally valid. Tier 1 items are blocking; Tier 2 is done in code; Tier 3 is documentation.

| # | Action | Tier | Status |
|---|--------|------|--------|
| 1 | MRFA explicit B2B clause — originating bank is borrower; repayment unconditional (NOT contingent on the underlying payment settling) | 1 (blocking) | 🟡 Legal counsel required |
| 2 | MRFA permanently-blocked-payment clause — repayment due at maturity regardless of whether the original payment ever settles | 1 (blocking) | 🟡 Legal counsel required |
| 3 | Governing law derived from BIC, not currency | 2 | ✅ Done in code (`bic_to_jurisdiction()` in `governing_law.py` uses BIC chars 4–5; `_build_loan_offer` in `agent.py` is BIC-first with currency fallback) |
| 4 | BPI License Agreement AML disclosure — explicit acknowledgement that C6 does NOT see the bank's internal compliance holds or SAR history; indemnity clause required | 1 (blocking) | 🟡 Legal counsel required (overlaps with EPG-04/05) |
| 5 | C2 model card — document that the 300 bps fee floor prices bank PD (near-zero for Tier 1), not end-customer credit risk | 3 (documentation) | ✅ Done (`docs/c2-model-card.md`) |

## CIPHER warning

The B2B structure is **not an OFAC shield.** OFAC strict liability applies regardless of who the nominal borrower is. If bridge funds ultimately benefit a sanctioned person — even if the legal counterparty is the bank — OFAC violation attaches. This is why C6 sanctions screening runs on the underlying payment context, not just the bank BIC. Anyone proposing to skip C6 because "the borrower is the bank" is wrong and must be refused at code review.

## Why "currency" was wrong for governing law

The earlier code derived governing law from payment currency (USD → New York law, EUR → Frankfurt law, etc.). This is structurally wrong for cross-border correspondent banking, where a USD payment can route through banks in five jurisdictions and the relevant counterparty law is the **enrolled bank's** jurisdiction, not the currency's home jurisdiction. Use BIC chars 4–5 (the country code in the SWIFT BIC standard). This rule is now in `CLAUDE.md` Key Rules.

## Open dependency

The three Tier 1 contractual items above are not engineering work — they require legal counsel and a willing pilot bank. See [`../OPEN_BLOCKERS.md`](../OPEN_BLOCKERS.md).
