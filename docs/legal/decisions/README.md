# EPG Decision Register

> **What this is.** Every architectural and policy decision in LIP that constrains future work has an EPG-XX code. Until now, those codes were scattered across `CLAUDE.md`, `EPIGNOSIS_ARCHITECTURE_REVIEW.md`, and `PROGRESS.md`. This directory is the index — one row per decision, one file per decision, with status, owner, source, and rationale.
>
> **Authority.** Decisions in this register are operative. The code refuses to violate them. They override the `docs/` reader layer when in conflict. Only the listed decision owner can change them, and only with a new EPG-XX entry.

**Last updated:** 2026-04-07

---

## Decision Index

| Code | Title | Status | Decided | Owner | File |
|------|-------|--------|---------|-------|------|
| EPG-01 | KYC-failure rejection codes (RR01–RR03) → BLOCK class | ✅ Implemented | 2026-03-18 | REX | (see commit `be16c22`, `rejection_taxonomy.py`) |
| EPG-02 | DNOR (DebtorNotAllowedToSend) → BLOCK class | ✅ Implemented | 2026-03-18 | REX | (commit `be16c22`) |
| EPG-03 | CNOR (CreditorNotAllowedToReceive) → BLOCK class | ✅ Implemented | 2026-03-18 | REX | (commit `be16c22`) |
| EPG-04 | Bridgeability Certification API — `hold_bridgeable` flag (FATF-compliant alternative to a hold-reason API) | 🟡 Code-ready, contractually open | 2026-03-19 | REX + CIPHER | [`EPG-04-05_hold_bridgeable.md`](EPG-04-05_hold_bridgeable.md) |
| EPG-05 | License Agreement warranties accompanying `hold_bridgeable` (certification, system integrity, indemnification) | 🟡 Code-ready, contractually open | 2026-03-19 | REX | [`EPG-04-05_hold_bridgeable.md`](EPG-04-05_hold_bridgeable.md) |
| EPG-07 | RR04 (RegulatoryReason) → BLOCK class | ✅ Implemented | 2026-03-18 | REX | (commit `be16c22`) |
| EPG-08 | AG01 (TransactionForbidden) and LEGL (LegalDecision) → BLOCK class | ✅ Implemented | 2026-03-18 | REX | (commit `be16c22`) |
| EPG-09 | Compliance hold audit trail — `outcome="COMPLIANCE_HOLD"` distinct from `"DECLINED"` | ✅ Implemented | 2026-03-18 | REX | [`EPG-09-10_compliance_hold_audit.md`](EPG-09-10_compliance_hold_audit.md) |
| EPG-10 | `compliance_hold: bool` field on `PipelineResult` | ✅ Implemented | 2026-03-18 | REX | [`EPG-09-10_compliance_hold_audit.md`](EPG-09-10_compliance_hold_audit.md) |
| EPG-14 | The borrower is the originating bank BIC, not the end customer (B2B interbank credit facility) | 🟡 Code fixed; legal contract open | 2026-03-18 | REX (unanimous team) | [`EPG-14_borrower_identity.md`](EPG-14_borrower_identity.md) |
| EPG-16 | AML caps must be set explicitly per-token via C8 license token; `0` is valid (means "unlimited"); dataclass default is sentinel `_AML_CAP_UNSET` (-1), rejected by boot validator (B3-03 hardening, 2026-04-08) | ✅ Implemented + B3-03 hardened | 2026-03-18 (B3-03: 2026-04-08) | CIPHER | [`EPG-16-18_aml_caps_human_review.md`](EPG-16-18_aml_caps_human_review.md) |
| EPG-17 | Explicit cap enforcement at boot — `license_token.from_dict` requires `aml_dollar_cap_usd` and `aml_count_cap` as mandatory JSON fields | ✅ Implemented | 2026-03-18 | CIPHER | [`EPG-16-18_aml_caps_human_review.md`](EPG-16-18_aml_caps_human_review.md) |
| EPG-18 | C6 anomaly flag → `PENDING_HUMAN_REVIEW` (EU AI Act Art. 14 human oversight) | ✅ Implemented | 2026-03-18 | REX | [`EPG-16-18_aml_caps_human_review.md`](EPG-16-18_aml_caps_human_review.md) |
| EPG-19 | LIP must NEVER bridge any payment where the originating bank's compliance system raised a hold (DNOR, CNOR, RR01–RR04, AG01, LEGL) — defense-in-depth at two layers | ✅ Implemented + permanently locked | 2026-03-18 | REX (unanimous: REX + CIPHER + NOVA) | [`EPG-19_compliance_hold_bridging.md`](EPG-19_compliance_hold_bridging.md) |
| EPG-20 | Patent counsel briefing — core novel claim is two-step classification + conditional offer logic | 🟡 Pending non-provisional filing | 2026-03-19 | Founder + counsel | [`EPG-20-21_patent_briefing.md`](EPG-20-21_patent_briefing.md) |
| EPG-21 | Patent language scrub — no "AML"/"SAR"/"OFAC"/"SDN"/"compliance investigation"/"tipping-off"/"suspicious activity"/"PEP" anywhere in published spec; do not enumerate the BLOCK code list | 🟡 Pending non-provisional filing | 2026-03-19 | Founder + counsel | [`EPG-20-21_patent_briefing.md`](EPG-20-21_patent_briefing.md) |
| EPG-23 | `class_b_eligible=False` pre-wired in `LoanOfferExpiry` records for ARIA data cut | ✅ Implemented | 2026-03-19 | ARIA | (see `CLAUDE.md` EPG-19 entry) |

### Status legend

- ✅ **Implemented** — code-enforced; nothing further required from any party
- 🟡 **Code-ready, contractually open** — code is in place; the binding action is on legal counsel, a pilot bank, or patent counsel
- 🔴 **Not started** — neither code nor contract in place
- ⚪ **Superseded** — replaced by a later EPG decision (with link)

---

## How to use this register

- **If you are reviewing code**: any time you see behaviour that looks "wrong" or "overly conservative" — refusing a payment, blocking a class, requiring a flag — search this directory for the EPG code referenced in the relevant comment or commit message. The decision is here.
- **If you are negotiating with a pilot bank**: every 🟡 entry is a contractual obligation the bank must accept. Do not concede any of them without REX sign-off.
- **If you are adding a new decision**: create `EPG-{NN}_{slug}.md` here, add a row above, and reference it from the relevant `CLAUDE.md` section.
- **If you are reverting a decision**: do not delete the file. Mark it superseded, link to the new EPG, and leave the rationale chain intact.

---

## Cross-references

- Source rationale lives in: [`/CLAUDE.md`](../../CLAUDE.md) § EPIGNOSIS Architecture Review — Team Decisions
- The internal audit that produced these decisions: [`/docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md`](../../engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md)
- Implementation history: [`/PROGRESS.md`](../../PROGRESS.md)
- Open contractual obligations: [`../../engineering/OPEN_BLOCKERS.md`](../../engineering/OPEN_BLOCKERS.md)
