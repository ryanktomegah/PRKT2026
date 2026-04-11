# EPG-19 — Compliance-Hold Bridging: NEVER

**Status:** ✅ Implemented + permanently locked
**Decided:** 2026-03-18
**Decision authority:** REX (final), unanimous with CIPHER and NOVA
**Source rationale:** [`/CLAUDE.md`](../../CLAUDE.md) § EPG-19 (full deliberation)
**Source audit:** [`/docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md`](../../engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md)
**Implementation history:** [`/PROGRESS.md`](../../PROGRESS.md) (search "EPG-19")

---

## Decision

LIP must **never** bridge any payment where the originating bank's compliance system raised a hold. The eight ISO 20022 codes that constitute compliance holds are:

| Code | Meaning | Reason |
|------|---------|--------|
| DNOR | DebtorNotAllowedToSend | Compliance prohibition |
| CNOR | CreditorNotAllowedToReceive | Compliance prohibition |
| RR01 | MissingDebtorAccountOrIdentification | KYC failure |
| RR02 | MissingDebtorNameOrAddress | KYC failure |
| RR03 | MissingCreditorNameOrAddress | KYC failure |
| RR04 | RegulatoryReason | Regulatory prohibition |
| AG01 | TransactionForbidden | Bank-level prohibition |
| LEGL | LegalDecision | Court / regulatory hold |

This decision is **non-negotiable** and **non-configurable**. It cannot be turned off by license token, environment variable, or runtime flag.

## Three independent grounds (any one is sufficient)

1. **CIPHER (security/AML).** Bridging a compliance-held payment is a structuring/layering typology violation. FATF R.21 tipping-off rules mean correctly-operating banks often code SARs as MS03/NARR — the explicitly-coded holds we *can* see are the visible floor of a much larger compliance problem. We must assume there is more we cannot see.

2. **REX (regulatory).** AMLD6 Art. 10 imposes criminal liability on legal persons. A bank that uses its LIP deployment to bridge a payment its own AML system blocked has not taken "reasonable precautions" — and BPI as the technology licensor inherits exposure.

3. **NOVA (payments protocol).** Even setting aside the legal issues, C3 repayment mechanics are structurally broken for compliance holds. UETR never settles for DNOR (permanent prohibition). Disbursement may not land for CNOR. Maturity windows are calibrated for technical-error resolution timelines, not compliance investigation timelines.

## Defense in depth

LIP enforces this at **two independent layers**, so a bug in one cannot bypass the policy:

- **Layer 1 — pipeline short-circuit.** All eight codes are BLOCK class in `lip/common/rejection_taxonomy.py`. The pipeline rejects them before C7 ever sees them.
- **Layer 2 — C7 gate.** `_COMPLIANCE_HOLD_CODES` in `lip/c7_execution_agent/agent.py` re-checks at the execution agent. Even if a future change accidentally promotes one of these codes out of BLOCK class at Layer 1, Layer 2 still refuses.

## What this decision does NOT cover

This decision is about what LIP must refuse on its own. It does not give LIP any visibility into payments the bank has internally flagged but coded as MS03/NARR (the FATF tipping-off problem). For that, see [`EPG-04-05_hold_bridgeable.md`](EPG-04-05_hold_bridgeable.md) — the contractual `hold_bridgeable` certification that the bank's compliance system must emit per payment.

## Open dependency (contractual, not code)

The BPI License Agreement must require pilot banks to push compliance holds (and the broader category of payments their compliance system would not certify as bridgeable) to the dedicated `hold_bridgeable` API in EPG-04/05. The code cannot see SAR-coded payments without this contractual layer. **This is a gap legal counsel must close before any bank pilot goes live.** See [`../OPEN_BLOCKERS.md`](../OPEN_BLOCKERS.md).

## Why this is logged as a permanent decision

EPG-19 is the kind of policy that gets quietly relaxed under commercial pressure — a pilot bank says "in our case the hold was administrative" and asks for an exception. The unanimous three-grounds structure exists so that no single team member can grant such an exception unilaterally. Any future change requires a new EPG-XX entry with REX, CIPHER, and NOVA all signing on, and a new pair of code-layer enforcements. Until then, the answer is no.
