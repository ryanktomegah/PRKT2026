# LIP — Open Blockers Register

> **What this is.** Every item that stands between LIP and a live pilot bank deployment, lifted out of `PROGRESS.md` so it does not have to be hunted for. One row per blocker, with owner, gating decision, and downstream impact.
>
> **What this is NOT.** This is not the full engineering backlog. Engineering work is tracked in `PROGRESS.md`. This register lists only items that block a live pilot bank deployment.

**Last updated:** 2026-04-24
**Engineering blocker count:** 0
**Legal/contractual/patent blocker count:** 4 (all critical-path)

---

## Critical Path to Pilot Launch

The items below are the current critical path. They are **independent** — none of them blocks the others — but all must be complete before LIP can fund a single bridge in production. There are no open engineering blockers; production deployments must still set `REDIS_URL` and `LIP_REQUIRE_DURABLE_OFFER_STORE=1` so startup fails closed if durable offer storage is unavailable.

### 🔴 BLOCKER-01 — Legal counsel engagement: MRFA explicit B2B framing

| Field | Value |
|-------|-------|
| **Owner** | Founder + external legal counsel |
| **Gates** | All pilot deployments |
| **Decision reference** | [`decisions/EPG-14_borrower_identity.md`](decisions/EPG-14_borrower_identity.md) |
| **What is needed** | A Master Receivables Financing Agreement (MRFA) template with: (a) explicit B2B clause naming the originating bank BIC as borrower; (b) unconditional repayment clause (repayment due at maturity regardless of whether the original payment ever settles or is permanently blocked) |
| **Why it blocks** | Without this, any bridge LIP funds is structurally a consumer/SMB loan to the end customer, which triggers consumer credit licensing in every jurisdiction and makes the model uneconomic |
| **Cannot be done by engineering** | The text must be drafted by counsel. Engineering has done its part — `bic_to_jurisdiction()` and the BIC-first `_build_loan_offer` are in code. |
| **Downstream impact if delayed** | No pilot bank will sign an LOI without this MRFA template. No LOI = no License Agreement = no production deployment. |

---

### 🔴 BLOCKER-02 — BPI License Agreement language

| Field | Value |
|-------|-------|
| **Owner** | Founder + external legal counsel |
| **Gates** | All pilot deployments; Class B unlock |
| **Decision references** | [`decisions/EPG-04-05_hold_bridgeable.md`](decisions/EPG-04-05_hold_bridgeable.md), [`decisions/EPG-19_compliance_hold_bridging.md`](decisions/EPG-19_compliance_hold_bridging.md), [`decisions/EPG-14_borrower_identity.md`](decisions/EPG-14_borrower_identity.md) |
| **What is needed** | License Agreement language covering: (a) `hold_bridgeable` API obligation with the three warranties from EPG-05 (certification, system integrity, indemnification); (b) compliance-hold register API clause from EPG-19; (c) explicit AML disclosure that C6 does not see the bank's internal compliance holds (EPG-14 item 4) |
| **Why it blocks** | All three are non-negotiable. Without (a), Class B remains permanently block-all in code, the bank loses all B1 LIP revenue, and there is no commercial reason for either party to continue. Without (b) and (c), BPI carries regulatory exposure for compliance failures it cannot see. |
| **Cannot be done by engineering** | This is contract drafting, not code. The code-side hooks already exist. |
| **Critical sequencing** | The warranty language must appear in the pilot bank **Letter of Intent** *before* the bank's legal team sees any draft of the License Agreement. Starting from a deficient LOI = months of renegotiation. |
| **Downstream impact if delayed** | Pilot bank cannot sign. Even if they sign without warranty #2, Class B revenue never opens. |

---

### 🔴 BLOCKER-03 — Patent filing (non-provisional)

| Field | Value |
|-------|-------|
| **Owner** | Founder + patent counsel |
| **Gates** | Defensible IP position; investor diligence; any external technical disclosure |
| **Decision references** | [`decisions/EPG-20-21_patent_briefing.md`](decisions/EPG-20-21_patent_briefing.md) |
| **What is needed** | Non-provisional patent filing based on [`docs/legal/patent/Provisional-Specification-v5.3.md`](../legal/patent/Provisional-Specification-v5.3.md), with: (a) claims scoped to two-step classification + conditional offer logic per EPG-20; (b) language scrub per EPG-21 (no AML/SAR/OFAC/SDN/PEP/etc.); (c) BLOCK code list NOT enumerated; (d) clean-room re-implementation if any reviewer-provided text was incorporated; and (e) written counsel confirmation of filing-fee status before any USPTO submission so the company does not assume micro-entity eligibility without basis. Pre-counsel risk analysis already complete in [`docs/business/fundraising/ip-risk-pre-counsel-analysis.md`](../business/fundraising/ip-risk-pre-counsel-analysis.md) (140 KB). |
| **Why it blocks** | The provisional gives 12 months of priority. Without the non-provisional, the moat decays and any external technical conversation (RBC, FF round, future hires) erodes the trade-secret position. |
| **Cannot be done by engineering** | This is patent prosecution work. |
| **Downstream impact if delayed** | Reduced defensibility of the Tier 2/3 contribution that is the entire competitive moat against JPMorgan US7089207B1. |

---

### 🔴 BLOCKER-04 — Bridgeability Certification API warranties in pilot bank LOI

| Field | Value |
|-------|-------|
| **Owner** | Founder + pilot bank champion |
| **Gates** | Pilot bank LOI; License Agreement scope |
| **Decision reference** | [`decisions/EPG-04-05_hold_bridgeable.md`](decisions/EPG-04-05_hold_bridgeable.md) |
| **What is needed** | The three warranties from EPG-05 (certification, system integrity, indemnification) included verbatim in the pilot bank LOI before the bank's legal team reviews any draft |
| **Why it blocks** | This is the same content as BLOCKER-02 but tracked separately because the *moment* it must appear is at LOI stage, not License Agreement stage. Missing this window means restarting negotiation from a worse position. |
| **Cannot be done by engineering** | This is commercial / legal sequencing work. |
| **Downstream impact if delayed** | Class B never unlocks for that pilot bank. B1 revenue is the largest single revenue line in the financial model. |

---

## Open Engineering Decisions (parameter calibration only)

These are not blockers in the contractual sense — none of them stops the code from running — but each one needs QUANT or BPI team sign-off before pilot data is treated as authoritative. Source: `PROGRESS.md` § Key Open Decisions.

| Item | Proposed value | Needs |
|------|----------------|-------|
| `RETRY_DETECTION_WINDOW_MINUTES` | 30 minutes | Pilot SWIFT data to confirm; could be 15 or 60 depending on observed retry latency |
| `STRESS_REGIME_FAILURE_RATE_MULTIPLIER` | 3.0 | Calibration against historical corridor stress events |
| GAP-05 settlement frequency | Monthly batch | Could be weekly or per-event; QUANT decision |
| GAP-08 timeout_action default | DECLINE (conservative) | Licensee may configure to OFFER per their risk appetite |
| GAP-12 FX risk policy | Open | Who denominates the bridge loan in cross-currency corridors? |

---

## Class B Unlock Sequence (purely mechanical once gating is cleared)

Class B is currently block-all in production. Unlocking it is **not** an engineering blocker — the code path is wired and `class_b_eligible=False` is pre-set in `LoanOfferExpiry` records (EPG-23) for ARIA's data cut. Unlock requires three things in this order:

1. **Pilot bank signs License Agreement** with `hold_bridgeable` API obligation (BLOCKER-02 + BLOCKER-04) ← *currently blocking*
2. **Bank CTO builds the B1 API integration** on the bank side (their work, not BPI's) ← *follows step 1*
3. **Code flip**: Class B block-all → B1/B2 split; ARIA retraining triggered ← *purely mechanical, ~1 day of engineering*

There is no meaningful engineering work in step 3. Steps 1 and 2 are entirely outside engineering control.

---

## Recently Closed Blockers

For confidence that this register is real and not aspirational, here is what *was* on the critical path and is no longer:

### Engineering — all closed as of 2026-04-24

| Closed item | Resolution |
|-------------|------------|
| GAP-01: No loan acceptance protocol | Protocol shipped; offer creation now returns `OFFERED` until ELO acceptance |
| ENGINEERING-BLOCKER-01: Durable offer-delivery state | Closed 2026-04-24. `OfferDeliveryService` now supports Redis-backed durable delivery/offer/acceptance/rejection/expiry state with atomic pending-to-terminal transitions. `build_runtime_pipeline()` supports `LIP_REQUIRE_DURABLE_OFFER_STORE=1` to fail startup when Redis is unavailable. |
| GAP-02: AML velocity caps unscalable | Per-licensee caps via C8 token (EPG-16/17) |
| GAP-03: No enrolled borrower registry | `BorrowerRegistry` + C7 first-gate check + `BORROWER_NOT_ENROLLED` state |
| GAP-04: No retry detection | Redis-ready `UETRTracker` with 30-min TTL + tuple-based dedup |
| GAP-05: No BPI royalty collection | `BPIRoyaltySettlement` monthly batch from C3 callback |
| GAP-06: No SWIFT message spec for bridge disbursement | Done |
| GAP-07: No portfolio reporting API for MLO | Done |
| GAP-08: Human override timeout outcome undefined | Done (DECLINE default, configurable) |
| GAP-09: Calendar-day maturities misfire on non-business days | Done |
| GAP-10: No governing law / jurisdiction field on LoanOffer | Done (BIC-derived, EPG-14) |
| GAP-11: Thin-file Tier 3 for creditworthy established banks | Done |
| GAP-12: FX risk undefined for cross-currency corridors | Engineering scaffold done; policy decision still open above |
| GAP-13: No customer-facing notification framework | Done |
| GAP-14: No regulatory reporting format (DORA, SR 11-7) | Done (`regulatory_reporter.py`) |
| GAP-15: No BPI admin / multi-tenant monitoring | Done |
| GAP-16: Partial settlement handling undefined | Done |
| GAP-17: Disbursement amount not anchored | Done (`original_payment_amount_usd` in NormalizedEvent + `_build_loan_offer` validation) |
| C2 model card | Done (`docs/c2-model-card.md`) |
| C6 Redis Phase 2 | Done (atomic Lua script, TOCTOU-safe, multi-instance K8s) |
| C1/C2 temporal OOT split | Done (chronological split in training pipelines) |
| C4 docstrings/manifests | Done |
| CI httpx dependency | Done |
| 9 infrastructure hardening items (PSS labels, securityContext, NetworkPolicy, Redis TLS, etc.) | All done (commit `221158b`) |
| EPG-09/10/16/17/18 | Implemented (commit `0ec874c`) |
| EPG-14 governing law fix | Implemented |
| EPG-19 defense-in-depth (Layer 1 + Layer 2) | Implemented |

### Decisions — all settled

EPG-01 through EPG-23 are all decided. The 🟡 status on some of them refers only to the **contractual** dependency, not to any open architectural question. See [`decisions/README.md`](decisions/README.md).

---

## How to use this register

- **If you are a banker reading this**: BLOCKER-02 and BLOCKER-04 affect you. Your legal team will need to review the warranty language. Start there.
- **If you are an investor reading this**: there are zero engineering blockers. The four critical-path items are legal and patent work, with clear owners. This is the position you want to see at FF round — capital is going into deal closing, not into rebuilding code.
- **If you are a developer reading this**: do not propose engineering work that depends on Class B being unlocked. Class B is gated on BLOCKER-02, not on anything you can write. The five "Open Engineering Decisions" above are the only parameters where engineering input is currently solicited.
- **If you are the founder reading this**: the four blockers are the only thing standing between you and a live pilot. None of them is an engineering problem. All of them are calendar-and-meeting problems with external counterparties.

## Maintenance

When a blocker is resolved, move it to "Recently Closed" with the resolution method and date. When a new blocker emerges, add it to the critical path with owner and gating decision. Do not let blockers drift back into `PROGRESS.md` — that file is a session log, not a decision register.
