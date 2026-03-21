# LIP — Epignosis Architecture Review
## Deep Knowledge Audit: Design Decisions, Compliance Gaps, and Operational Risks

> **INTERNAL — NOT FOR DISTRIBUTION**
>
> This document is a comprehensive architecture and design audit of the LIP platform, conducted
> from first principles. It examines every significant decision — from the patent scope down to
> individual rejection code classifications — against the question: *do we understand what this
> system actually does, who it serves, and where it will fail?*
>
> The word **epignosis** (Greek: ἐπίγνωσις) means precise, thorough, experiential knowledge
> as opposed to surface-level familiarity. That is the standard this review holds.
>
> Every issue documented here is grounded in the actual codebase. File and line references are
> provided throughout. Nothing in this document is speculative — it is derived from reading the
> source. Issues are rated **CRITICAL**, **HIGH**, **MEDIUM**, or **LOW** based on their
> potential to cause legal liability, operational failure, or commercial damage in a live
> bank deployment.
>
> **Last codebase sync: 2026-03-18 — `main` branch at commit `fe09cb6`.**
> Status column in the issue register reflects current code state as of this sync.
> `OPEN` = not yet addressed. `ESCALATED` = new information makes the issue worse than
> originally assessed. `PARTIAL` = partially addressed but not closed.

---

## TABLE OF CONTENTS

1. [What This System Actually Is — A Precise Description](#1-what-this-system-actually-is)
2. [The AML/KYC Lending Problem — Your Original Question](#2-the-amlkyc-lending-problem)
   - 2.1 What the system does protect against
   - 2.2 Gap A — RR01–RR03: KYC failures that get 3-day bridge loans
   - 2.3 Gap B — DNOR and CNOR: prohibited parties that get funded
   - 2.4 Gap C — The bank's own AML system is structurally opaque to LIP
   - 2.5 Gap D — Generic rejection codes that hide AML reasoning
   - 2.6 Gap E — The PD model does not price regulatory outcome risk
   - 2.7 Gap F — Taxonomy and C7 gate are misaligned on RR04
3. [Compliance Hold Audit Trail is Mislabeled](#3-compliance-hold-audit-trail-is-mislabeled)
4. [C1 Training Data and AML Rejection Codes](#4-c1-training-data-and-aml-rejection-codes)
5. [The Borrower Identity Problem — Who Actually Signs the MRFA](#5-the-borrower-identity-problem)
6. [The AML Velocity Cap is Retail-Scaled for an Institutional Product](#6-the-aml-velocity-cap-is-retail-scaled)
7. [Anomaly Detection is Advisory-Only and Should Not Be](#7-anomaly-detection-is-advisory-only)
8. [Class B Settlement Time is Labeled "Compliance/AML Holds" — And Nobody Noticed](#8-class-b-settlement-and-compliance-holds)
9. [The Patent Scope and Compliance Reality Tension](#9-patent-scope-and-compliance-reality)
10. [C1 Misalignment — Failure Predictor vs. Bridgeability Predictor](#10-c1-misalignment)
11. [GAP-01 Revisited — The Offer Delivery Problem in Compliance Context](#11-gap-01-revisited)
12. [What the System Gets Right — Genuine Strengths](#12-what-the-system-gets-right)
13. [Sanctions Screening Disabled by Default](#13-sanctions-screening-disabled-by-default)
14. [AML Velocity Check TOCTOU Race Condition](#14-aml-velocity-check-toctou-race-condition)
15. [Human Review Dead End — No Pipeline Re-entry Path](#15-human-review-dead-end)
16. [AML Fail-Open Default — C6 Exception Passes Payments](#16-aml-fail-open-default)
17. [Velocity Cap Tracks BIC, Not Economic Entity](#17-velocity-cap-tracks-bic-not-economic-entity)
18. [Master Issue Register](#18-master-issue-register)
19. [Recommended Resolution Priority Order](#19-recommended-resolution-priority-order)

---

## 1. What This System Actually Is — A Precise Description

Before any issue can be evaluated, the system must be understood precisely. The following is
not a summary — it is a technically grounded description of what LIP does, to whom, and under
what legal structure.

**LIP (Liquidity Intelligence Platform)** is a real-time payment failure detection and
automated bridge lending orchestration system. Bridgepoint Intelligence (BPI) licenses the
software to correspondent banks. The bank deploys LIP inside its own infrastructure. BPI
earns a 15% royalty on bridge loan fees collected. The bank provides capital, executes all
transactions, bears all credit risk, and maintains all regulatory relationships.

**The three-entity structure:**
- **MLO (Money Lending Organisation):** Capital provider — the bank's own balance sheet or
  an external private credit partner.
- **MIPLO (Money In/Payment Lending Organisation):** BPI — the technology licensor that
  operates the intelligence engine and collects royalties.
- **ELO (Execution Lending Organisation):** The bank-side C7 agent that executes loan
  instructions within the bank's own systems.

**The eight-component pipeline:**

| Component | Role | Hard Gate? |
|-----------|------|-----------|
| C5 | Kafka streaming ingestion, ISO 20022 normalization | Pre-pipeline |
| C1 | ML failure classifier (GraphSAGE + TabTransformer + LightGBM) | Yes — τ*=0.110 |
| C4 | LLM dispute classifier (Qwen3-32b via Groq) | Yes — hard block on dispute |
| C6 | AML gate: sanctions + velocity + anomaly | Yes — hard block on AML |
| C2 | Structural PD + LGD + fee pricing (Merton/KMV, Damodaran, Altman Z') | No — pricing only |
| C7 | Execution agent: kill switch, KMS, compliance hold codes, offer delivery | Yes — multiple gates |
| C3 | Settlement monitor, auto-repayment on UETR settlement | Post-funding |
| C8 | HMAC-SHA256 license token enforcement | Pre-boot |

**What triggers the pipeline:** A `pacs.002` payment rejection/status event from SWIFT (or
FedNow/RTP/SEPA normalised to ISO 20022 format by C5). This is a payment that has already
been rejected by the network or a counterparty bank. LIP detects this rejection and decides
whether to bridge it.

**What "bridging" means operationally:** The bridge loan disburses the full original payment
amount to the intended receiver, funded by the bank's own balance sheet. The fee is collected
separately at repayment. The underlying failed payment is expected to eventually settle, at
which point C3 auto-repays the bridge principal from the settlement proceeds. If the underlying
payment never settles, the bridge loan defaults.

**The canonical constants that govern the system (QUANT-controlled, never change without
sign-off):**

| Constant | Value | Significance |
|----------|-------|-------------|
| Failure threshold τ* | 0.110 | F2-optimal gate (calibrated) — tuned to minimize false negatives |
| Fee floor | 300 bps annualized | Minimum economically viable bridge loan fee |
| Latency SLO | ≤ 94ms end-to-end | Architecture Spec v1.2 |
| UETR TTL buffer | 45 days | Deduplication window beyond maximum maturity |
| Platform royalty | 15% of fee | BPI technology licensor share |
| AML dollar cap | $1M/entity/24h | Per-entity rolling velocity cap |
| AML count cap | 100 txns/entity/24h | Per-entity transaction count cap |
| CLASS_A maturity | 3 days | Routing/account errors |
| CLASS_B maturity | 7 days | Systemic/compliance holds |
| CLASS_C maturity | 21 days | Investigation/complex cases |

---

## 2. The AML/KYC Lending Problem — Your Original Question

**Your question:** "When we give loans for transfers that were blocked because of AML/KYC
cases, that is illegal, right?"

**The answer is yes — and it is more nuanced than a single yes/no.** What makes this
analysis important is that the system partially prevents this in multiple places, but has
specific, identifiable holes that a regulator reviewing a live deployment would find.

### 2.1 What the System DOES Protect Against

Three independent layers prevent lending against AML/KYC-flagged payments:

**Layer 1 — BLOCK-class rejection codes at pipeline entry** (`pipeline.py:200-223`)

The pipeline checks the ISO 20022 rejection code before running C1. If the code is in the
BLOCK class (`FRAU`, `FRAD`, `DISP`, `DUPL`), the payment is immediately terminated as
`DISPUTE_BLOCKED` with no ML evaluation. This check runs in microseconds before any
inference occurs.

```
File: lip/pipeline.py, lines 200-223
if event.rejection_code and is_dispute_block(event.rejection_code):
    → return DISPUTE_BLOCKED (no C1, no C2, no C7)
```

**Layer 2 — C6 AML Gate** (`lip/c6_aml_velocity/aml_checker.py`)

C6 runs three sub-checks in series before any offer is generated:
1. Sanctions screening against OFAC/EU/UN lists (hard block on ≥ 0.8 confidence hit)
2. Velocity controls ($1M/entity/24h dollar cap, 100-txn count cap, >80% beneficiary
   concentration — all hard blocks)
3. Anomaly detection (soft flag — advisory only, does not block)

If sanctions or velocity checks fail, the pipeline returns `AML_BLOCKED` and no offer is
generated.

**Layer 3 — `_COMPLIANCE_HOLD_CODES` in C7 Execution Agent**
(`lip/c7_execution_agent/agent.py:55-59`)

This is the most important layer for the AML/KYC lending question. C7 contains an explicit
set of ISO 20022 rejection codes that indicate the bank has placed an active compliance,
regulatory, or legal hold on the specific payment. Any payment whose rejection code is in
this set is returned as `COMPLIANCE_HOLD_BLOCKS_BRIDGE` with no offer.

```python
_COMPLIANCE_HOLD_CODES: frozenset[str] = frozenset({
    "RR04",   # RegulatoryReason — bank flagged for regulatory review
    "AG01",   # TransactionForbidden — bank explicitly forbidden transaction
    "LEGL",   # LegalDecision — court order, garnishment, or sanctions legal hold
})
```

This set was signed off by REX and CIPHER on 2026-03-17, citing FATF R.18/R.20,
EU AMLD6 Art.10, and US BSA §1010.410. The legal basis is sound.

These three layers together mean: the system was designed with awareness of the lending-on-
compliance-hold problem, and made specific decisions to prevent it. **However, the protection
has gaps.**

---

### 2.2 Gap A — RR01–RR03: KYC Failures That Get 3-Day Bridge Loans

**Severity: HIGH**

**The problem:** Three ISO 20022 rejection codes represent KYC failures — situations where the
bank cannot verify the identity of a payment party — and they are classified as `CLASS_A`
(3-day bridge) in the rejection taxonomy. They are **not** in `_COMPLIANCE_HOLD_CODES`.

| Code | Meaning | Classification | Bridge Loan? |
|------|---------|---------------|-------------|
| RR01 | MissingDebtorAccountOrIdentification | CLASS_A | Yes — 3 days |
| RR02 | MissingDebtorNameOrAddress | CLASS_A | Yes — 3 days |
| RR03 | MissingCreditorNameOrAddress | CLASS_A | Yes — 3 days |
| RR04 | RegulatoryReason | CLASS_A | **No — blocked in C7** |

The design logic appears to be: RR04 is the catch-all regulatory hold, so only RR04 needs
blocking. But this misses the regulatory intent behind RR01–RR03.

**Why this is a legal risk:**

`RR01` means the bank cannot identify the debtor's account. This is a Know-Your-Customer
failure at the account identification level. `RR02` means the bank does not have the debtor's
name or address. `RR03` means the creditor's name or address is missing. These are not
technical formatting errors — they are situations where a party to a financial transaction
cannot be identified.

Under FATF Recommendation 16 (Wire Transfer Rule) and the EU Funds Transfer Regulation
(2015/847), a payment must carry complete originator and beneficiary information. A bank that
processes a bridge loan for a payment where it cannot identify the sender is potentially:
- Providing financial services to an unidentified party
- Enabling a transaction that bypasses the Wire Transfer Rule
- Creating a structuring opportunity (original payment coded as unidentified + bridge loan
  to fund it = value moves while identity verification is pending)

**The code evidence:**

```yaml
# File: lip/configs/rejection_taxonomy.yaml, lines 38-42
RR01: "MissingDebtorAccountOrIdentification"   → class_a (3-day bridge)
RR02: "MissingDebtorNameOrAddress"             → class_a (3-day bridge)
RR03: "MissingCreditorNameOrAddress"           → class_a (3-day bridge)
RR04: "RegulatoryReason"                       → class_a (3-day bridge, but C7 blocks)
```

**Resolution:**

Option A (recommended): Add `RR01`, `RR02`, `RR03` to `_COMPLIANCE_HOLD_CODES` in
`agent.py`. These payments should return `COMPLIANCE_HOLD_BLOCKS_BRIDGE`, not receive offers.

Option B (alternative): Move `RR01`, `RR02`, `RR03` to the `BLOCK` class in
`rejection_taxonomy.yaml`, making them unconditionally non-bridgeable at pipeline entry —
consistent with the treatment of `FRAU`, `FRAD`, `DISP`, `DUPL`.

Option B provides better defense-in-depth because the taxonomy-level block fires before C1
runs, meaning no ML inference, no fee calculation, and no audit trail that looks like a
"declined offer" rather than a "categorically excluded payment."

REX and CIPHER sign-off required before implementing either option.

---

### 2.3 Gap B — DNOR and CNOR: Prohibited Parties That Get Funded

**Severity: HIGH**

**The problem:** Two ISO 20022 codes explicitly state that a party to the payment is
**not allowed** in this transaction, and neither is blocked by `_COMPLIANCE_HOLD_CODES`.

| Code | Meaning | Classification | Bridge Loan? |
|------|---------|---------------|-------------|
| DNOR | DebtorNotAllowedToSend | CLASS_B | Yes — 7 days |
| CNOR | CreditorNotAllowedToReceive | CLASS_C | Yes — 21 days |

**Why `DNOR` is the more serious risk:**

`DNOR` means the sending entity has been prohibited from originating this transaction. The
prohibition could be:
- A sanctions-related restriction placed by the bank's compliance team
- A regulatory restriction (e.g., a financial institution under supervisory action whose
  outbound transfers are restricted)
- An internal risk control (the bank has suspended this entity's ability to send funds
  pending a compliance review)

A bridge loan for a `DNOR` payment means the system is instructing the bank to fund the
payment that the bank's own system said the sender is not allowed to make. This is not a
technical failure — it is a compliance decision being overridden by LIP.

**Why `CNOR` is also problematic:**

`CNOR` means the receiving entity is not allowed to receive funds in this context. This
could indicate a blocked account, a restricted jurisdiction, or a compliance hold on the
beneficiary. A 21-day bridge loan to a receiver that the bank has said cannot receive funds
is similarly concerning.

**The code evidence:**

```yaml
# File: lip/configs/rejection_taxonomy.yaml, lines 55-62
class_b:
  DNOR: "DebtorNotAllowedToSend"    → 7-day bridge loan eligible

class_c:
  CNOR: "CreditorNotAllowedToReceive" → 21-day bridge loan eligible
```

Neither code appears in `_COMPLIANCE_HOLD_CODES` (`agent.py:55-59`).

**Resolution:**

Add `DNOR` and `CNOR` to `_COMPLIANCE_HOLD_CODES`. The reason is the same as for
`RR01–RR03`: these codes indicate the bank has made a compliance decision about a party to
the transaction. LIP should not override that decision by funding the payment.

Alternatively, consider whether `DNOR` should be in the `BLOCK` class in the taxonomy,
given that it is functionally similar to `FRAU` (the sending entity is prohibited, not just
temporarily failed). REX should make this determination.

**The asymmetry to document explicitly:**

`AG01` (TransactionForbidden) IS in `_COMPLIANCE_HOLD_CODES` but `DNOR` (DebtorNotAllowed
ToSend) and `CNOR` (CreditorNotAllowedToReceive) are not. This inconsistency suggests the
`_COMPLIANCE_HOLD_CODES` set was designed around regulatory-hold semantics (the bank has a
hold on the transaction) rather than prohibition semantics (the bank has prohibited a party).
Both semantics should be covered.

---

### 2.4 Gap C — The Bank's Own AML System is Structurally Opaque to LIP

**Severity: HIGH (architectural, no code fix)**

**The problem:** This is the deepest conceptual issue in the AML/KYC lending analysis, and it
has no code fix. It requires contractual and operational resolution.

A `pacs.002` rejection event that reaches LIP has **already been processed by the bank's own
upstream compliance system.** The pacs.002 event IS the bank's compliance system's output —
it is the message saying "this payment was rejected." LIP then runs C6, its own AML check,
against the same payment.

These are not the same check.

**The bank's AML system knows:**
- The full payment history of the sending entity, across all payment rails
- The internal risk classification of the counterparty (PEP, high-risk jurisdiction, etc.)
- The narrative context of why this specific payment was flagged (pattern matching,
  ML model outputs, human review decisions)
- Internal suspicious activity reports filed on this entity
- Correspondent banking due diligence records
- Regulatory subpoenas or law enforcement holds

**LIP's C6 knows:**
- Whether the entity name matches its own OFAC/EU/UN sanctions list (via fuzzy matching)
- Whether the entity has exceeded $1M in 24-hour volume or 100 transactions today
- Whether the entity is sending >80% of volume to a single beneficiary
- Whether the transaction looks statistically anomalous compared to past behavior

These are completely different information sets. A payment can pass LIP's C6 (no sanctions
hit, no velocity cap exceeded) while having been blocked by the bank's AML system for reasons
LIP will never see.

**The critical logic failure:**

The `_COMPLIANCE_HOLD_CODES` gate partially addresses this by catching cases where the bank
**correctly codes its rejection reason.** If the bank's AML team blocks a payment and codes
it as `RR04` (RegulatoryReason), LIP correctly blocks the bridge. But this relies entirely
on the bank accurately encoding its compliance decision in the ISO 20022 rejection code.

**What the gate cannot catch:**

A bank's AML system flags a payment as suspicious but the payment reaches SWIFT with a generic
rejection code (e.g., `MS03: NotSpecifiedReasonAgentGenerated`) because the compliance team
does not want to disclose the specific reason in the payment message — standard practice to
avoid tipping off a subject. LIP sees `MS03`, classifies it as CLASS_B (7-day bridge), passes
all gates, and generates a bridge loan offer.

**This is not a theoretical edge case.** It is standard banking practice to obscure the
reason for compliance-related payment failures. The explicit guidance from FATF and FinCEN is
that financial institutions should NOT disclose in payment messages that a transaction is
being reviewed for suspicious activity (to prevent "tipping off" — see FATF R.21).

So the very regulation that LIP is designed to comply with (FATF) creates the mechanism by
which LIP's compliance gates are systematically bypassed.

**The contractual resolution:**

This cannot be fixed in code. The bank licensing LIP must be contractually required, as a
condition of the license, to:
1. Configure their core banking/AML system to pass compliance hold flags to LIP via a separate
   secure API channel — not encoded in pacs.002 rejection codes
2. Maintain a "real-time compliance hold register" that C7 can query before generating any offer
3. Accept that LIP will only block compliance-hold payments it can be informed about, and that
   the bank is responsible for all holds it fails to communicate

This should appear as a mandatory clause in the BPI License Agreement template (C8/REX domain).

---

### 2.5 Gap D — Generic Rejection Codes That Hide AML Reasoning

**Severity: MEDIUM-HIGH**

This is the operational manifestation of Gap C, documented separately because it has a
specific, identifiable set of codes.

**The codes:**

| Code | Meaning | Classification | Bridge eligible? | Risk |
|------|---------|---------------|-----------------|------|
| MS02 | NotSpecifiedReasonCustomerGenerated | CLASS_B | Yes — 7 days | Medium |
| MS03 | NotSpecifiedReasonAgentGenerated | CLASS_B | Yes — 7 days | High |
| NARR | Narrative (reason in free text) | CLASS_B | Yes — 7 days | Medium |
| MS02, NOAS | Various generic/no-response codes | CLASS_B | Yes — 7 days | Medium |

`MS03` (NotSpecifiedReasonAgentGenerated) is the code a bank uses when it has decided not to
specify the reason for rejection — precisely the code used to conceal AML-related holds.

**The tipping-off dynamic:**

FATF Recommendation 21 prohibits financial institutions from disclosing to the customer or
counterparty that a suspicious activity report (SAR) has been filed. This means if a bank's
AML system fires a SAR on a payment, the bank will often reject the payment with a generic
code rather than `RR04` (RegulatoryReason) — because `RR04` effectively signals "we have a
regulatory concern" to the other party.

LIP's `_COMPLIANCE_HOLD_CODES` cannot catch SAR-related rejections by design. The more
accurately the bank follows FATF R.21, the more payments will bypass LIP's compliance gates.

**Resolution:**

As with Gap C, the resolution is contractual and operational rather than technical:
1. The BPI License Agreement should include an indemnity clause stating that BPI is not liable
   for bridge loans made on payments where the bank failed to communicate a compliance hold
   through the agreed hold register API
2. The bank's compliance team should configure their AML system to push holds to LIP's C7
   compliance hold register API (to be built) rather than relying on rejection code classification
3. Document this limitation explicitly in the bank-facing compliance pack (to be produced)

---

### 2.6 Gap E — The PD Model Does Not Price Regulatory Outcome Risk

**Severity: MEDIUM**

**The problem:** C2's PD model uses Merton/KMV structural models, Damodaran industry-beta
thin-file estimation, and Altman Z' scoring to assess credit risk. These models measure the
probability that the **borrower cannot repay** — counterparty credit risk. They do not measure
the probability that the **underlying payment never settles** due to regulatory outcome.

**Why this matters for compliance-adjacent payments:**

For a payment with rejection code `CLASS_B`, the `constants.py` comment reads:

```python
# File: lip/common/constants.py, line 94
SETTLEMENT_P95_CLASS_B_HOURS = 53.58   # Compliance/AML holds — BIS/SWIFT GPI target 53.6h
```

The system's own authors labeled Class B settlement times as "Compliance/AML holds." This
means a significant fraction of Class B bridge loans are on payments that were blocked for
compliance reasons. Those payments face a different default profile than credit-risk-driven
failures.

**The difference in default dynamics:**

- **Credit-risk failure** (e.g., `AM04: InsufficientFunds`): The payment failed because the
  sender didn't have the money. The PD model correctly assesses: can the sender repay a 7-day
  bridge loan? Merton/KMV is the right tool.
- **Compliance-hold failure** (e.g., `DNOR`, or `MS03` covering an AML flag): The payment
  failed because a compliance system blocked it. The question is not "can the sender repay?"
  but "will this payment ever settle?" If the compliance investigation concludes the payment
  is suspicious and permanently blocks it, the underlying payment never settles, C3 waits
  indefinitely, and the bridge loan ultimately DEFAULTs.

The Merton/KMV model says nothing about the probability of a compliance investigation
concluding adversely. A bank with AAA credit (PD near zero) can still have a payment
permanently blocked by regulators.

**The resulting risk exposure:**

Bridge loans on compliance-hold payments that eventually become permanent blocks will default
at a rate that C2 does not predict. The 300bps fee floor was calibrated against credit LGD,
not against regulatory-outcome default rates. If 15% of Class B loans are on permanently-
blocked compliance holds (a plausible assumption given that `SETTLEMENT_P95_CLASS_B_HOURS`
is labeled "Compliance/AML holds"), the actual LGD for Class B may significantly exceed
the model's estimate.

**The quantification gap:**

There is no data in the codebase on what percentage of CLASS_B bridge loan defaults in the
synthetic corpus resulted from "compliance hold that became permanent" vs. "settlement
genuinely delayed but eventually completed." The synthetic data generator (`c1_generator.py`)
generates rejection codes from the taxonomy but does not model the outcome distribution of
compliance-hold payments differently from credit-failure payments.

**Resolution:**

1. **Short-term:** REX and QUANT should document this pricing gap explicitly in the C2 model
   card. The fee floor for CLASS_B loans should acknowledge that regulatory-outcome default
   risk is not captured in the PD model.
2. **Medium-term:** The synthetic data generator for C2 should model compliance-hold outcomes
   separately (e.g., `DNOR`, `MS03`, `CNOR` codes should have a higher default rate than
   credit-failure codes in the training distribution).
3. **Long-term:** A separate "regulatory outcome probability" feature should be added to C2,
   using the rejection code class as a signal. Payments with compliance-adjacent codes should
   carry a regulatory-outcome premium on top of the Merton/KMV PD score.

---

### 2.7 Gap F — Taxonomy and C7 Gate are Misaligned on RR04

**Severity: LOW-MEDIUM**

**The problem:** `RR04` (RegulatoryReason) is correctly blocked in C7's
`_COMPLIANCE_HOLD_CODES`. But in `rejection_taxonomy.yaml`, it is classified as `CLASS_A`
(3-day bridge).

```yaml
# File: lip/configs/rejection_taxonomy.yaml, line 43
RR04: "RegulatoryReason"  → class_a  (3-day maturity assigned)
```

```python
# File: lip/c7_execution_agent/agent.py, line 56
"RR04",   # RegulatoryReason — bank flagged this payment for regulatory review
```

**The defense-in-depth gap:**

For `FRAU`, `FRAD`, `DISP`, `DUPL` — the BLOCK-class codes — the pipeline terminates
before C1 runs. There is no offer, no PD calculation, no C7 evaluation. The taxonomy is
the primary gate.

For `RR04`, the taxonomy assigns a 3-day maturity (CLASS_A). The pipeline evaluates C1,
runs C4 and C6, calls C2 for a fee calculation, and then C7 blocks it. C7 is the *only*
gate preventing a bridge loan on a regulatory hold payment. If C7's compliance hold gate
were ever removed, bypassed, or modified (human override, code change, degraded mode), the
pipeline would fully fund a bridge loan on a regulatory hold payment because the taxonomy
says CLASS_A.

**The correct behavior:**

`RR04` should be in the `BLOCK` class in `rejection_taxonomy.yaml`. This would make C7's
`_COMPLIANCE_HOLD_CODES` check a redundant second gate (defense-in-depth), not the primary
and only gate. The same logic applies to `AG01`, `LEGL`, `DNOR`, and `CNOR`.

A payment that the taxonomy has classified as BLOCK cannot receive a bridge loan regardless
of what C7 does — because the pipeline terminates at pipeline entry before any inference runs.

**Resolution:**

Move `RR04`, `AG01`, `LEGL`, `DNOR`, and `CNOR` to the `BLOCK` class in
`rejection_taxonomy.yaml`. Update `_COMPLIANCE_HOLD_CODES` in `agent.py` to serve as
defense-in-depth for codes that survive taxonomy screening (e.g., because C5's normalizer
mapped a FedNow/RTP code to one of these ISO 20022 equivalents).

QUANT sign-off required (changes maturity distribution). REX and CIPHER sign-off required
(compliance classification). NOVA sign-off required (affects C3 settlement monitoring scope).

---

## 3. Compliance Hold Pipeline Fall-Through — ESCALATED

**Severity: CRITICAL** *(was MEDIUM when originally written as an audit trail issue —
escalated 2026-03-18 after verifying current code state)*

**What changed:** Commit `fe09cb6` (2026-03-17) added `COMPLIANCE_HOLD_BLOCKS_BRIDGE`
to C7's execution agent correctly. `pipeline.py` was **not updated** in that commit and
was not changed since. The compliance hold status code is unrecognised by the pipeline.

**The actual current behavior:**

```python
# File: lip/pipeline.py, line 418 — current state
if c7_status in (
    "DECLINE", "BLOCK", "PENDING_HUMAN_REVIEW",
    "CURRENCY_NOT_SUPPORTED", "BORROWER_NOT_ENROLLED"
    # ← "COMPLIANCE_HOLD_BLOCKS_BRIDGE" is ABSENT from this list
):
    return PipelineResult(outcome="DECLINED", ...)

# --- OFFER accepted → FUNDED ----------------------------------
# This branch is reached for ANY c7_status not handled above,
# including "COMPLIANCE_HOLD_BLOCKS_BRIDGE"
_record_payment_transition(PaymentState.BRIDGE_OFFERED)   # ← fires
_record_payment_transition(PaymentState.FUNDED)           # ← fires
loan_sm.transition(LoanState.ACTIVE)                      # ← fires
```

A payment blocked by C7's compliance hold gate returns from C7 with `status =
"COMPLIANCE_HOLD_BLOCKS_BRIDGE"` and `loan_offer = None`. The pipeline does not recognise
this status, falls through to the FUNDED section, transitions the state machines to
`BRIDGE_OFFERED → FUNDED`, and returns `PipelineResult(outcome="FUNDED", loan_offer=None)`.

**What this means in production:**
- The DecisionLogEntry (written by C7 before returning) correctly records the block
- The PipelineResult returned to the caller says `outcome="FUNDED"` — the opposite
- Any system reading PipelineResult to determine whether a loan was made (e.g., a bank's
  treasury integration, a monitoring dashboard, the C3 registration call) believes the
  payment was funded
- C3 registration is skipped only because `loan_offer is None` — a silent guard, not an
  explicit block
- The UETR tracker records this UETR as `"FUNDED"` — blocking any retry from being
  re-processed as a fresh event

**The same fall-through exists for three other C7 status codes:**

| C7 Status | In pipeline DECLINE list? | Falls through to FUNDED? |
|-----------|--------------------------|--------------------------|
| `COMPLIANCE_HOLD_BLOCKS_BRIDGE` | No | Yes |
| `BELOW_MIN_LOAN_AMOUNT` | No | Yes |
| `BELOW_MIN_CASH_FEE` | No | Yes |
| `LOAN_AMOUNT_MISMATCH` | No | Yes |

All four return `loan_offer=None` from C7. C3 registration is silently skipped for all four.
All four produce `outcome="FUNDED"` in the pipeline result — a misclassification.

**The test coverage gap that allowed this:**

Commit `fe09cb6` added `test_c7_execution.py::TestComplianceHoldGate` — 7 tests that
correctly verify C7's behaviour in isolation. None test the full `LIPPipeline.process()`
with a compliance-hold rejection code. The pipeline-level fall-through is not covered.

**Resolution:**

Add all four missing status codes to the pipeline DECLINE handler at `pipeline.py:418`:

```python
if c7_status in (
    "DECLINE", "BLOCK", "PENDING_HUMAN_REVIEW",
    "CURRENCY_NOT_SUPPORTED", "BORROWER_NOT_ENROLLED",
    "COMPLIANCE_HOLD_BLOCKS_BRIDGE",   # ← add
    "BELOW_MIN_LOAN_AMOUNT",           # ← add
    "BELOW_MIN_CASH_FEE",              # ← add
    "LOAN_AMOUNT_MISMATCH",            # ← add
):
```

Additionally, `COMPLIANCE_HOLD_BLOCKS_BRIDGE` should produce a distinct outcome
(`"COMPLIANCE_HOLD"` rather than `"DECLINED"`) — the audit trail concern documented
below in the original EPG-09 analysis remains valid and must be addressed in the same fix.

**What this means for the audit trail:**

The `DecisionLogEntry` — retained for 7 years under SR 11-7 and EU AI Act Article 17 — will
record a compliance-hold block as `decision_type="DECLINED"`, indistinguishable from economic
declines (loan too small, fee below minimum, etc.).

**Why this is a regulatory reporting gap:**

FATF Recommendation 20 requires that financial institutions file Suspicious Transaction
Reports (STRs) when they have reasonable grounds to suspect money laundering. FATF
Recommendation 18 requires banks to maintain an AML compliance program with a compliance
function that monitors transactions.

When regulators review the 7-year decision log — which they will, in a supervisory review
or examination — they will look for evidence that:
1. The bank correctly identified compliance-hold payments
2. Those holds were enforced (no bridge loan was generated)
3. The compliance team was informed of each hold detection

If compliance-hold blocks are logged as `"DECLINED"`, regulators cannot:
- Distinguish between "we declined this loan for economic reasons" and "we detected this
  payment was under a regulatory hold and blocked it"
- Verify that the bank's compliance team received notifications for each hold detection
- Audit the completeness of the compliance hold detection rate over time

**The specific fields that are wrong:**

In `DecisionLogEntry` (inferred from `_log_decision` call at `agent.py:462-494`), the
`decision_type` field should have a distinct value for compliance holds. Currently:
- Economic decline: `decision_type="DECLINE"` — correct
- AML block: `decision_type="BLOCK"` — correct (this is what `aml_passed=False` produces)
- Compliance hold block: `decision_type="DECLINED"` — **incorrect** — loses the distinction

**Resolution:**

1. Add `"COMPLIANCE_HOLD"` as a distinct `decision_type` value in `DecisionLogEntry`
2. Update `pipeline.py` to map `COMPLIANCE_HOLD_BLOCKS_BRIDGE` to `outcome="COMPLIANCE_HOLD"`
   rather than `"DECLINED"`
3. Update the `PipelineResult` schema to include `compliance_hold: bool` field
4. Ensure compliance hold events trigger a notification to the bank's compliance team via
   the notification service (`common/notification_service.py`) — not just a decision log entry

This change requires REX sign-off and should be implemented before any production deployment.

---

## 4. C1 Training Data and AML Rejection Codes

**Severity: MEDIUM**

**The problem:** C1 is trained on synthetic data generated by `lip/dgen/c1_generator.py`
using the full ISO 20022 rejection code taxonomy. This means C1's training corpus includes
payments with `DNOR`, `MS03`, `CNOR`, and other compliance-adjacent codes, labeled as
"payment failures." C1 learns that these events indicate high failure probability.

**The τ* threshold alignment issue:**

C1's threshold τ*=0.110 was optimized using the F2 metric (FBETA_BETA=2 in `constants.py`),
which weights false negatives more heavily than false positives. The rationale is that missing
a real failure (failing to offer a bridge) is more costly than incorrectly identifying one.

But this optimization assumes that all payment failures are equally bridgeable. They are not.
A payment flagged for AML is a real failure in C1's terms (the payment did fail), but it is
NOT a failure that should be bridged. The training objective says "maximize recall on all
failures" when the correct objective is "maximize recall on bridgeable failures."

**The practical consequence:**

C1 will score compliance-hold payments with high failure probability because it was trained
to do so. These payments will then correctly be blocked downstream (by C7's compliance hold
gate). But the pipeline has already run C4, C6, C2, and most of C7 before the block fires.
This means:
1. Computational resources are wasted on payments that should be short-circuited at entry
2. The C2 fee calculation exists in the decision log for a payment that was blocked for
   compliance reasons — a potential audit trail confusion point
3. The τ*=0.110 threshold, having been optimized to catch these payments, is inherently
   "polluted" by compliance-hold examples that inflate the apparent recall

**The deeper issue — what C1 actually measures:**

C1 is described as a "failure predictor" — it predicts the probability that a payment has
genuinely failed in a way that should be bridged. But what it actually predicts is the
probability that a payment matches the pattern of any ISO 20022 rejection event in its
training corpus.

These are not the same. The correct formulation would be:

> C1 should predict P(payment failed in a bridgeable way | pacs.002 features)

But the training data does not distinguish "bridgeable failure" from "compliance-blocked
failure." The label used is simply "did this payment fail?" — which is true for both.

**Resolution:**

1. **ARIA and DGEN:** Create a separate label in the C1 training corpus that distinguishes
   bridgeable failures from compliance-hold failures. Rejection codes in the BLOCK class and
   the proposed expanded compliance hold set should be labeled differently from Class A/B/C
   bridgeable failures.
2. **QUANT:** Re-evaluate τ*=0.110 once the training corpus is relabeled. The optimal
   threshold on a clean "bridgeable failures only" corpus may differ from the current value.
3. **ARIA:** Document this labeling gap in the C1 model card under SR 11-7 requirements.
   The model card should state that C1 AUC was measured on a corpus that includes non-
   bridgeable failures, and that the operational AUC on bridgeable failures only is unknown.
4. **REX:** This constitutes a known model limitation that must appear in the EU AI Act
   Article 13 transparency documentation before any regulated deployment.

---

## 5. The Borrower Identity Problem — Who Actually Signs the MRFA

**Severity: HIGH (operational/legal)**

**The problem:** LIP uses `sending_bic` as the borrower entity throughout the pipeline — for
C6 AML velocity checks, C2 PD model evaluation, C7 enrollment checks, and C3 loan
registration. But in the correspondent banking context, `sending_bic` is almost always
**another bank**, not a corporate entity.

**The three-layer correspondent banking reality:**

1. **End customer** (Siemens treasury): Instructs their bank to make a payment
2. **Originating bank** (Deutsche Bank Siemens account): Sends payment instruction to
   correspondent
3. **Correspondent bank** (JPMorgan): Actually executes the SWIFT payment — and runs LIP

The `sending_bic` that LIP sees is Deutsche Bank (the originating bank), not Siemens (the
end customer who is economically responsible for the payment).

**The MRFA enrollment gap:**

The CLIENT_PERSPECTIVE_ANALYSIS.md correctly identifies that only enrolled BICs can be
borrowers. But enrollment happens at the bank level (Deutsche Bank's BIC). The MRFA is
between JPMorgan and Deutsche Bank. If the bridge loan defaults, JPMorgan has a claim against
Deutsche Bank — not against Siemens, who was the ultimate sender.

This is commercially coherent for bank-to-bank payments. But it creates three problems:

**Problem 1 — PD model is pricing the wrong entity**

C2's Merton/KMV model is assessing Deutsche Bank's probability of default. Deutsche Bank is
a Tier 1 bank with a near-zero PD, so the fee will be near the floor (300bps). But the
**economic risk** is Siemens' ability to pay its underlying invoice, which drives whether
the payment was sent in good faith and whether it will eventually settle. Siemens' PD is
not in the model.

**Problem 2 — The bridge loan may fund a payment the originating bank never authorized**

If Deutsche Bank's own system rejected the payment (and generated the pacs.002 that LIP
sees), and LIP offers to bridge it, who is authorizing the bridge? Deutsche Bank (as the
enrolled borrower and signing party to the MRFA) is implicitly authorizing every bridge that
LIP generates on their `sending_bic`. But Deutsche Bank's operations team may not know this
is happening in real time.

This is the "no delivery mechanism" problem (GAP-01) compounded: not only does the bank not
receive the offer, but the bank may not even know that a bridge was authorized in their name
on a payment their own system failed.

**Problem 3 — Thin-file treatment of institutional BICs**

C2 falls back to Tier-3 (Damodaran industry-beta) for entities with no credit profile. The
patent's core contribution is this thin-file coverage. But a SWIFT BIC is almost never truly
thin-file — every BIC belongs to a regulated financial institution that has publicly available
credit data (ratings, annual reports, supervisory disclosures). The thin-file path should
essentially never fire for a bank BIC. If it does, it indicates the borrower registry has
not been populated with credit data for an enrolled entity, which is an operational gap.

**Resolution:**

1. **Legal/REX:** The MRFA template should clearly specify whether the borrower is the
   originating bank (the `sending_bic` entity), the end corporate customer, or both. The
   current architecture implies it is the originating bank. This must be explicitly documented.
2. **C2/ARIA:** The PD model should include the originating bank's tier classification as a
   feature, not just use it as the thin-file fallback signal. All enrolled BICs should have
   an explicit tier assignment in the borrower registry, not just those with rich credit data.
3. **NOVA:** Evaluate whether C3's repayment loop should monitor the originating bank's
   relationship with its correspondent (not just the UETR of the underlying payment) as a
   repayment signal.

---

## 6. The AML Velocity Cap is Retail-Scaled for an Institutional Product

**Severity: MEDIUM (already identified as GAP-02 in CLIENT_PERSPECTIVE_ANALYSIS)**

**This issue is already documented but deserves re-examination from the compliance angle.**

```python
# File: lip/common/constants.py, lines 52-54
AML_DOLLAR_CAP_USD = 1_000_000     # per entity per 24 hr rolling window
AML_COUNT_CAP      = 100           # transactions per entity per 24 hr
```

The CLIENT_PERSPECTIVE_ANALYSIS.md correctly identifies that $1M/entity/24h is inoperably
small for correspondent banking. A Tier 1 correspondent bank processing $50B–$4T in daily
SWIFT volume would hit this cap on its first large payment every morning.

**The compliance angle that is NOT in the existing analysis:**

The velocity cap exists to detect structuring (breaking up transactions to evade detection).
Structuring thresholds are set relative to the regulatory reporting threshold in the
jurisdiction — in the US, this is $10,000 (BSA/CTR filing threshold), and structuring just
below $10,000 is a federal offense.

For institutional correspondent banking, the relevant threshold is not $10,000 but the
bank's internal large-value payment monitoring threshold, which is typically $1M–$10M per
single transaction (and correspondent banks regularly process payments of $100M+).

Setting the AML velocity cap at $1M means LIP is calibrated to detect retail-scale
structuring behavior in an institutional payment context. An institutional entity processing
$500M across 3 transactions in a day would hit both the dollar cap ($500M > $1M) and the
count cap (if they have >100 institutional payments). Both blocks are incorrect — not because
the entity is structuring, but because $1M is the wrong scale for the customer.

**The licensee override mechanism:**

The licensee context (`LicenseeContext` from C8) allows per-licensee overrides of both caps:
```python
# File: lip/c7_execution_agent/agent.py, lines 137-143
if licensee_context:
    self.aml_dollar_cap_usd = licensee_context.aml_dollar_cap_usd
    self.aml_count_cap = licensee_context.aml_count_cap
```

This is the correct design. But the *default* values being retail-scale means that any bank
that deploys LIP without explicitly configuring their licensee context will have an inoperable
AML cap from day one.

**Resolution:**

1. The default `AML_DOLLAR_CAP_USD` should be raised to $0 (unlimited) or a clearly
   documented "deployment-time required configuration" flag should prevent LIP from starting
   without an explicit AML cap configured in the licensee context
2. The C8 license token validation should require `aml_dollar_cap_usd` and `aml_count_cap`
   to be explicitly set (not defaulted) for any production deployment
3. The bank-facing deployment checklist should list AML cap configuration as a mandatory
   pre-go-live step with explicit guidance on appropriate values by bank type

---

## 7. Anomaly Detection is Advisory-Only and Should Not Be

**Severity: MEDIUM**

**The problem:**

```python
# File: lip/c6_aml_velocity/aml_checker.py, lines 228-252
# Step 3: Anomaly detection (soft flag only — does not block, appended to reasons)
if self._anomaly is not None:
    anomaly_result = self._anomaly.predict(txn)
    if anomaly_result.is_anomaly:
        anomaly_flagged = True
        triggered_rules.append("ANOMALY_SOFT_ALERT")
        logger.info("Anomaly soft alert: ...")

# [continues to generate offer]
return AMLResult(passed=True, ...)
```

When the anomaly detector fires, `passed=True` is still returned. The pipeline receives
`aml_passed=True` and proceeds to generate an offer. The anomaly flag appears in the
`triggered_rules` list but does not trigger any escalation.

**Why this is inconsistent with the system's risk posture:**

C7 already has a `_requires_human_review` function that triggers `PENDING_HUMAN_REVIEW`
when PD exceeds 0.20 or when a stress regime is detected. The EU AI Act Article 14 human
oversight requirement is implemented as an automatic escalation path for high-risk decisions.

An anomaly detection firing — from an ML model that detected statistically unusual behavior
in a financial transaction — is exactly the kind of signal that should trigger human review.
The current implementation generates an advisory log entry and then funds the loan anyway.
This is inconsistent with how every other risk signal in the system is handled.

**The specific EU AI Act risk:**

Article 14 of the EU AI Act requires that high-risk AI systems allow human oversight to:
"detect and correct, as soon as possible, errors, failures, and inconsistencies that arise
during use."

An anomaly-flagged transaction that proceeds to funding without human review is a case where
a potential error signal was generated and ignored. In a post-incident regulatory review,
this will be difficult to defend.

**Resolution:**

The anomaly detector's `is_anomaly` flag should be propagated to C7 as part of the payment
context, and C7's `_requires_human_review` function should check for it:

```python
# In c7_execution_agent/agent.py, _requires_human_review:
if payment_context.get("anomaly_flagged"):
    return True
```

This routes anomaly-flagged transactions to `PENDING_HUMAN_REVIEW`, consistent with the
treatment of high-PD transactions and stress-regime transactions.

CIPHER sign-off required (AML scope change). REX sign-off required (EU AI Act Art.14
compliance). QUANT sign-off required (impact on offer throughput).

---

## 8. Class B Settlement Time is Labeled "Compliance/AML Holds" — And Nobody Noticed

**Severity: MEDIUM (indicator of deeper design assumption)**

This is not a bug — it is a revealed assumption that deserves explicit team alignment.

```python
# File: lip/common/constants.py, lines 92-95
SETTLEMENT_P95_CLASS_A_HOURS = 7.05    # Routing/account errors   — BIS/SWIFT GPI target 7.0h
SETTLEMENT_P95_CLASS_B_HOURS = 53.58   # Compliance/AML holds     — BIS/SWIFT GPI target 53.6h
SETTLEMENT_P95_CLASS_C_HOURS = 170.67  # Liquidity/timing         — BIS/SWIFT GPI target 171.0h
```

The system's own authors — in canonical constants that require QUANT sign-off to change —
have explicitly labeled Class B settlement times as corresponding to "Compliance/AML holds."

**What this label reveals:**

The team designed the 7-day CLASS_B maturity window specifically to accommodate compliance
and AML hold durations. They calibrated the settlement P95 against BIS/SWIFT GPI data for
compliance hold resolution. This means a significant fraction of Class B bridge loans were
always expected to be on compliance-flagged payments.

**The unasked question:**

If CLASS_B is "Compliance/AML holds" — and the system funds 7-day bridge loans for
CLASS_B payments — then the team accepted, as a design premise, that LIP would routinely
fund bridge loans on payments that are under compliance or AML holds.

The `_COMPLIANCE_HOLD_CODES` gate blocks the most explicit compliance holds (`RR04`, `AG01`,
`LEGL`). But `DNOR`, `CNOR`, and generic codes (`MS03`) are CLASS_B — the very class labeled
"Compliance/AML holds" — and they are not blocked.

This suggests the design team had two conflicting mental models:
1. "We detect compliance holds by rejection code and block them" (→ `_COMPLIANCE_HOLD_CODES`)
2. "CLASS_B is compliance/AML holds and the 7-day maturity is calibrated for them" (→ constants)

Model 1 says compliance holds should be blocked. Model 2 says they should be funded with
7-day bridges. These cannot both be correct.

**Resolution:**

The team needs explicit alignment on whether LIP's intended use case includes bridging
payments that are under compliance review (with appropriate risk controls) or categorically
excludes them. This is a product design question, not a code question.

If the answer is "categorically exclude compliance-hold payments," then:
- `DNOR`, `CNOR`, and all explicitly compliance-adjacent CLASS_B codes should be moved to BLOCK
- The calibration comment in constants.py should be revised to remove the "Compliance/AML holds" label
- C2's pricing model should not be calibrated against Class B compliance-hold settlement P95

If the answer is "include compliance-hold payments with appropriate controls," then:
- The `_COMPLIANCE_HOLD_CODES` gate should be revised to a narrower set of codes that
  represent hard legal blocks rather than general compliance holds
- C2's pricing model needs a regulatory-outcome risk premium for compliance-adjacent codes
- The patent claims should explicitly include compliance-hold bridging as a use case

This question must be resolved by the founder with legal counsel before any regulated deployment.

---

## 9. Patent Scope and Compliance Reality Tension

**Severity: STRATEGICALLY IMPORTANT**

**The problem:**

The LIP patent claims cover "bridge lending triggered by real-time payment network failure
detection" broadly. The dependent claims include specific ISO 20022 rejection codes as
triggering events. The compliance-adjacent codes (`DNOR`, `MS03`, `CLASS_B` codes broadly)
are in the taxonomy that C3 uses to derive maturity windows — meaning the patent's scope
could be read as covering bridge lending on compliance-flagged failures.

**The specific risk:**

A sophisticated patent challenger, or a regulator reviewing LIP's technology, could argue:
1. The patent claims the system processes all ISO 20022 rejection codes as potential bridge
   loan triggers
2. Several of those codes represent compliance holds (DNOR, MS03, CLASS_B broadly)
3. Therefore the patent-claimed invention includes facilitating value movement on compliance-
   hold payments

If a bridge loan is ever made on a compliance-hold payment (through any of the gaps identified
above), the patent's breadth becomes a liability rather than an asset — it demonstrates that
the system was designed to do exactly what the illegal outcome shows it did.

**The FATF tipping-off interaction:**

There is a second tension. The patent specification describes the system's ability to detect
and bridge failures that a bank's AML system has flagged with generic codes (because of
FATF R.21 tipping-off prohibition). If this capability is described in the patent, it could
be read as: "the invention bridges payments that the bank's AML system has obscured with
generic codes to avoid FATF tipping-off." That is an extremely dangerous characterization in
a regulatory context.

**Resolution:**

1. Patent counsel should review all independent and dependent claims to ensure compliance-hold
   codes are either explicitly excluded from the triggering events or clearly described as
   non-triggering
2. The patent specification should include explicit language that the invention is designed
   for technically-failed payments only, not for payments under active compliance investigation
3. The `_COMPLIANCE_HOLD_CODES` sign-off (REX/CIPHER, 2026-03-17) and the compliance-adjacent
   code exclusions (Gaps A–D above) should be documented in the prosecution history to
   establish intent to exclude compliance-hold bridging from the patent claims

---

## 10. C1 Misalignment — Failure Predictor vs. Bridgeability Predictor

**Severity: MEDIUM**

**The problem:** C1 is described and trained as a "failure predictor" — it predicts whether a
payment has genuinely failed. But what the system needs is a "bridgeability predictor" — it
needs to predict whether a payment failure is of a type that should be bridged.

These are subtly different.

**The misalignment in the F2 threshold optimization:**

```python
# File: lip/common/constants.py, line 42
ASYMMETRIC_BCE_ALPHA = 0.7   # false negatives more costly
FBETA_BETA           = 2     # F2-optimal threshold
```

The F2 metric was chosen because "false negatives are more costly" — missing a bridgeable
failure is worse than incorrectly flagging a non-failure. This is correct for a bridgeability
predictor. But if C1 is trained on all payment failures (including compliance holds, fraud,
disputes), then minimizing false negatives means minimizing the rate at which C1 misses ANY
failure — including compliance holds and disputed transactions that should never be bridged.

The result: C1 is tuned to be maximally sensitive, and then the system relies on C4, C6, and
C7 to filter out the things C1 should not have flagged in the first place. This is correct
architecturally (defense-in-depth), but it means C1's τ*=0.110 threshold is calibrated on
a mixed population, and its "failure rate" statistics include non-bridgeable events.

**The AUC gap this creates:**

The current C1 AUC is 0.9998 on synthetic data (`docs/compliance.md`). The production target
is 0.850 on real SWIFT data. This gap is documented as a known risk. But the AUC metric is
measured against "did the payment fail?" — not against "was this a payment that should have
been bridged?" The 0.9998 synthetic AUC is optimistic even as a baseline because it includes
compliance-hold payments as positive examples.

**Resolution:**

1. **ARIA and DGEN:** Create a "bridgeability" label for the C1 training corpus:
   - `bridgeable=True`: CLASS_A/B/C codes that are not compliance-adjacent
   - `bridgeable=False`: BLOCK-class codes + proposed expanded compliance hold set
2. Re-train C1 and re-optimize τ* against the bridgeability label rather than the failure label
3. Report both AUCs: failure AUC (as currently measured) and bridgeability AUC (new metric)
4. **REX:** Update the EU AI Act Article 13 documentation to correctly describe C1's training
   objective as "bridgeable payment failure detection" rather than "payment failure detection"

---

## 11. GAP-01 Revisited — The Offer Delivery Problem in Compliance Context

**Severity: MEDIUM (compliance dimension of an already-known gap)**

GAP-01 (the absence of an offer delivery mechanism) is documented in the existing
CLIENT_PERSPECTIVE_ANALYSIS.md. This section adds the compliance dimension.

**The compliance-specific risk of unfulfilled offers:**

Every bridge loan offer that LIP generates is logged in the `DecisionLogEntry` with
`decision_type="OFFER"`. When the offer expires unfunded (because there is no delivery
mechanism — GAP-01), what happens to that log entry?

The 7-year retention requirement means every expired offer sits in the decision log forever,
appearing as a loan offer that was never accepted. For compliance-adjacent payments where C7
generated an offer, this creates a log entry showing "LIP offered a bridge loan on payment
X at time T." If a regulator later determines that payment X was suspicious, the log entry
showing an offer was generated (even if unfunded) is evidence that LIP's system evaluated
the payment as bridgeable.

**The expired offer audit trail problem:**

In a regulatory examination:
- Regulator: "Show me all bridge loan offers made on payments involving Entity X."
- Bank: "Here are 47 offers." (Includes expired unfunded offers)
- Regulator: "You generated 47 offers on this entity's payments. Were any of them
  compliance-hold payments?"
- Bank: "15 of them were compliance-hold blocks (`COMPLIANCE_HOLD_BLOCKS_BRIDGE`),
  logged as `DECLINED`." (This is the Gap in Section 3 above)

Wait — but with the current taxonomy gaps (Gaps A-D), some compliance-adjacent payments
may have generated `"OFFER"` log entries (before C7 blocked them on a downstream code). And
with compliance holds logged as `DECLINED`, the bank cannot cleanly distinguish.

**Resolution:**

This reinforces the urgency of Section 3 (compliance hold audit trail) and the taxonomy
fixes (Gaps A-D). The offer delivery mechanism (GAP-01) and the compliance hold log
distinction must both be resolved before any production deployment to ensure the 7-year
audit trail is interpretable by regulators.

---

## 12. What the System Gets Right — Genuine Strengths

A complete review must also document what works, so the team can protect these strengths
as gaps are closed.

### 12.1 The Three-Layer Block Architecture

The combination of taxonomy-level blocks (BLOCK class in `rejection_taxonomy.yaml`), C6 AML
gate, and C7 `_COMPLIANCE_HOLD_CODES` is genuinely well-designed. No single component is
solely responsible for preventing illegal lending. This defense-in-depth approach is correct
and should be preserved and extended (by filling the gaps identified in this review), not
replaced with a single-gate approach.

### 12.2 Kill Switch and KMS Unavailability Behavior

The `KillSwitch.activate()` and `DegradedModeManager` implementations are production-quality.
The KMS unavailability behavior (halt new offers when the key management system is unreachable)
is specifically designed to prevent the system from operating without cryptographic guarantees.
This is exactly the kind of fail-safe that regulators look for. The DORA Article 30 incident
logging is real.

### 12.3 HMAC-Signed Decision Logs

7-year Kafka retention with HMAC-SHA256 integrity on every `DecisionLogEntry` is genuine
compliance infrastructure. The tamper-resistance is real and will stand up to regulatory
examination. The weakness (compliance holds logged as DECLINED) is a semantic issue, not
an integrity issue.

### 12.4 Per-Licensee Rotating AML Entity Hash

```
stored_identifier = SHA-256(entity_id + per_licensee_salt)
```

Annual salt rotation with 30-day overlap, unique per-licensee, cryptographically random
32-byte salts. This is correct GDPR privacy-by-design. The guarantee that cross-licensee
entity correlation is impossible is real and patent-worthy.

### 12.5 UETR Deduplication (Retry Detection)

The `UETRTracker` prevents the same UETR from being funded twice. Combined with the
tuple-based retry detection spec (GAP-04), this addresses one of the highest-probability
operational failure modes (double-funding from manual retries). The implementation in
`pipeline.py` runs before C1, meaning even if C1 would score a retry highly, it is blocked
at pipeline entry.

### 12.6 Human Override with Timeout Enforcement

The `HumanOverrideInterface` with configurable timeout and dual-approval option is genuine
Article 14 compliance, not a stub. The override audit trail (operator_id + justification) is
exactly what regulators look for in an AI system that makes automated lending decisions.

### 12.7 The 300bps Fee Floor with Economic Justification

The tiered fee floor ($500K = 500bps, $500K–$2M = 400bps, ≥$2M = 300bps) with explicit
breakeven analysis per rejection class is not arbitrary. The reasoning in `constants.py`
documents the economic rationale for each tier. QUANT's requirement for sign-off on any
change protects the minimum viable economics of the platform.

### 12.8 C8 Licensee Context Override Architecture

The ability for the C8 license token to override AML caps, TPS limits, and loan minimums
per licensee is the correct architectural response to the heterogeneity of the bank
deployment context. A regional bank and a Tier 1 correspondent bank need different caps.
The problem is that the defaults are misconfigured (Gap 6), not that the architecture
is wrong.

---

## 13. Sanctions Screening Disabled by Default

**Severity: CRITICAL**

**The problem:** C6's sanctions screening is structurally disabled in any deployment that does
not explicitly wire a name-resolver function — which is the default.

**The code evidence:**

```python
# File: lip/c6_aml_velocity/aml_checker.py, line 107
def __init__(self, ..., entity_name_resolver=None, ...):
    self._resolve_name = entity_name_resolver

# File: lip/c6_aml_velocity/aml_checker.py — entity resolution in check()
sender_name = entity_name or (self._resolve_name(entity_id) if self._resolve_name else entity_id)
```

When `entity_name_resolver` is `None` (the default), `self._resolve_name` is falsy, so
the ternary falls back to `entity_id` itself. In correspondent banking, `entity_id` is a
SWIFT BIC code — a machine-readable bank identifier like `"BNPAFRPPXXX"`.

This BIC code is then passed to the sanctions screener as the entity "name."

**What the sanctions screener does with a BIC code:**

```python
# File: lip/c6_aml_velocity/sanctions.py — Jaccard token-overlap matcher
# "BNPAFRPPXXX" vs "BANK OF IRAN"
# tokens(BIC) = {"BNPAFRPPXXX"}  (one token)
# tokens(sanctioned) = {"BANK", "OF", "IRAN"}
# intersection = 0
# Jaccard = 0 / 4 = 0.0  → no hit
```

BIC codes contain no tokens in common with any human-readable sanctioned entity name. The
Jaccard score will be 0.0 for every comparison. Every payment passes sanctions screening.

**The screener's own documentation acknowledges this:**

```python
# File: lip/c6_aml_velocity/sanctions.py — entity_id parameter docstring
# "entity_id: currently unused; reserved for future exact-ID screening
#  against LEI/BIC databases"
```

Exact-ID screening against LEI/BIC databases — the correct mechanism for institutional
entity screening — is not implemented. It is reserved for future work.

**The additional name-matching gap (even when a resolver is provided):**

Even with a correct name resolver, the 0.8 Jaccard threshold misses partial name matches:

```
"BANK OF IRAN INTERNATIONAL"  vs  "BANK OF IRAN"
tokens: {"BANK","OF","IRAN","INTERNATIONAL"}  vs  {"BANK","OF","IRAN"}
intersection = 3, union = 4 → Jaccard = 0.75 < 0.80 → NOT a sanctions hit
```

A sanctioned entity with a subsidiary name one word longer than the list entry evades
the screen.

**What this means operationally:**

In a default deployment (no entity_name_resolver configured), the C6 sanctions layer passes
`aml_passed=True` for every payment regardless of counterparty. The three-layer AML
protection documented in Section 2.1 is reduced to two layers: BLOCK-class taxonomy check
and velocity caps. Sanctions enforcement is silently disabled.

**Resolution:**

1. **CIPHER:** `entity_name_resolver` must be a required constructor parameter — not
   optional with a fallback to `entity_id`. Passing `None` should raise a
   `ConfigurationError` at startup, not silently disable sanctions.
2. **CIPHER:** Implement the LEI/BIC exact-ID screening path that the docstring says is
   "reserved for future work." This is the only correct approach for institutional BIC-based
   entity IDs.
3. **CIPHER:** Lower the Jaccard threshold from 0.80 to 0.65–0.70 OR switch to a
   token-containment metric (does the screened name fully contain the sanctions list name?).
   The current threshold allows one-word additions to sanctioned names to evade detection.
4. **FORGE:** Add a deployment-time check that refuses to start C6 without an explicitly
   configured entity name resolver. This should be a fatal error, not a warning.

REX and CIPHER sign-off required. FORGE deployment checklist must be updated.

---

## 14. AML Velocity Check TOCTOU Race Condition

**Severity: HIGH**

**The problem:** C6's velocity checker separates the AML cap evaluation (`check()`) from
the volume recording (`record()`) into two independent, non-atomic Redis operations. In a
multi-worker Kubernetes deployment, this creates a classic Time-of-Check/Time-of-Use
(TOCTOU) race condition.

**The code evidence:**

```python
# File: lip/c6_aml_velocity/velocity.py
def check(self, entity_id, amount_usd):
    """Read rolling window — does NOT write."""
    current_volume = self._redis.get_rolling_window_sum(entity_id, window=86400)
    current_count  = self._redis.get_rolling_window_count(entity_id, window=86400)
    if current_volume + amount_usd > self.dollar_cap:
        return VelocityResult(passed=False, reason="DOLLAR_CAP_EXCEEDED")
    if current_count + 1 > self.count_cap:
        return VelocityResult(passed=False, reason="COUNT_CAP_EXCEEDED")
    return VelocityResult(passed=True)

def record(self, entity_id, amount_usd):
    """Write to rolling window — called after C2+C7 complete."""
    self._redis.push_rolling_window(entity_id, amount_usd, timestamp=now())
```

The gap between `check()` and `record()` spans the entire C2 + C7 execution — at minimum
~60–80ms in the nominal path. In a K8s pod deployment with N workers processing payments
concurrently, this window allows the following race:

```
Worker 1: check(EntityX, $600K)  → current_volume=$500K  → PASSED ($1.1M < $1M? No wait)
          Actually: $500K + $600K = $1.1M > $1M → should FAIL

Wait — let me restate correctly:
Entity has $400K recorded so far today.

Worker 1: check(EntityX, $400K) → $400K+$400K = $800K < $1M → PASSED
Worker 2: check(EntityX, $400K) → $400K+$400K = $800K < $1M → PASSED (same snapshot)
Worker 3: check(EntityX, $400K) → $400K+$400K = $800K < $1M → PASSED (same snapshot)

Worker 1: record(EntityX, $400K) → Redis now shows $800K
Worker 2: record(EntityX, $400K) → Redis now shows $1.2M (cap exceeded — but loan funded)
Worker 3: record(EntityX, $400K) → Redis now shows $1.6M (cap exceeded — but loan funded)
```

Three payments pass the $1M cap because all three checked before any recorded. The effective
exposure is (N–1) × amount per concurrent batch.

**The production severity:**

At p50 pipeline latency of 45ms and C2+C7 accounting for ~30ms of that, the TOCTOU window
is ~30ms. A K8s deployment with the default `HPA_SCALE_OUT_QUEUE_DEPTH=100` can have up to
dozens of concurrent workers. For a correspondent bank processing high-volume payment
failures, multiple concurrent events for the same sending BIC are not rare.

The architecture specification's AML section does not document any atomicity guarantee
for velocity checks. There is no Redis `MULTI/EXEC` transaction, no Lua script, and no
distributed lock.

**Resolution:**

1. **CIPHER:** Replace the separate `check()` + `record()` pattern with an atomic
   Redis Lua script that performs check-and-reserve in a single operation:
   ```lua
   -- Pseudo-code: atomic check-and-increment
   local current = redis.call('GET', key)
   if current + amount > cap then return 0 end
   redis.call('INCRBY', key, amount)
   redis.call('EXPIRE', key, 86400)
   return 1
   ```
2. **CIPHER:** Until the atomic implementation is deployed, document this as a known
   limitation in the compliance model card. The effective AML velocity cap under concurrent
   load is higher than the configured value.
3. **FORGE:** Add a concurrency stress test to the CI suite that fires 10 concurrent
   pipeline calls for the same entity at the $1M boundary and asserts that exactly one
   passes, nine are blocked.

CIPHER sign-off required. QUANT sign-off required (impacts throughput/latency SLO).

---

## 15. Human Review Dead End — No Pipeline Re-entry Path

**Severity: HIGH**

**The problem:** When C7's `_requires_human_review` check fires (high-PD decision, stress
regime, or — per EPG-18 — anomaly flag), the pipeline returns `PENDING_HUMAN_REVIEW` and
exits. The human operator's decision is stored in `HumanOverrideInterface`, but there is no
mechanism that causes the pipeline to re-evaluate the payment after the human decides.

**The code evidence:**

```python
# File: lip/c7_execution_agent/human_override.py
def request_override(self, uetr, payment_context, ...):
    """Creates a pending override request — stores it, returns request_id."""
    ...

def submit_response(self, request_id, operator_id, decision, justification):
    """Operator stores their approval or rejection — returns stored record."""
    ...

def resolve_expired(self, request_id):
    """Returns timeout_action if request has expired — returns timeout_action value."""
    ...
```

None of these methods trigger a pipeline re-evaluation. The pipeline caller (e.g., a
Kafka consumer or an API endpoint) receives `PENDING_HUMAN_REVIEW` and must know, on its
own, to: (a) poll or subscribe for the human decision, (b) re-submit the payment event to
the pipeline with the human decision attached, and (c) handle the case where the payment's
maturity window expires before the human decides.

**No such caller logic exists in the codebase.** The pipeline has no callback registration
interface. The `UETRTracker` records the UETR when the payment first enters the pipeline —
which means a re-submission of the same UETR will be blocked as a duplicate at pipeline
entry (line 185–195 in `pipeline.py`), before it reaches C7 where the human decision
would be checked.

**The operational consequence:**

Every payment that triggers human review is permanently stuck. The human can approve or
reject it, but the decision goes nowhere. The payment's bridge loan window closes. The
payment is effectively declined by timeout, regardless of what the human decides.

For high-PD payments (C7's current trigger), the stress-regime and anomaly-flagged payments
that reach `PENDING_HUMAN_REVIEW` in a production deployment will accumulate indefinitely
in the `HumanOverrideInterface` store with no mechanism for resolution.

**The EU AI Act Article 14 implication:**

Article 14 requires human oversight to include the ability for humans to "intervene in the
operation of the high-risk AI system" and "override the outputs." If the override mechanism
exists in code but has no effect on the system's actual behavior (because there is no
re-entry path), the Article 14 compliance is a compliance-by-paperwork rather than by
operational effect.

**Resolution:**

1. **NOVA:** The `UETRTracker` must be updated to support a "pending human review" state
   that does not block re-submission. A UETR in this state should allow re-entry to the
   pipeline exactly once (with the human decision attached as a flag in the payment context).
2. **FORGE:** Implement a human review worker: a separate process that polls
   `HumanOverrideInterface` for decided reviews and re-submits approved payments to the
   pipeline Kafka topic with a `human_approved=True` flag.
3. **NOVA:** The pipeline's `process()` method should accept an optional
   `human_override_decision` parameter. If present and valid, it bypasses the
   `_requires_human_review` check in C7.
4. **REX:** Document the human review re-entry flow in the EU AI Act Article 14 compliance
   record. Until the re-entry path is implemented, any payment requiring human review is
   effectively declined — this is a conservative behavior but must be documented as the
   current operational reality.

NOVA + FORGE + REX sign-off required before any regulated deployment.

---

## 16. AML Fail-Open Default — C6 Exception Passes Payments

**Severity: HIGH**

**The problem:** The pipeline has a hardcoded fail-open default for C6 AML results. If C6
raises an unhandled exception, errors out, or returns `None`, the pipeline treats the
payment as having passed all AML checks.

**The code evidence:**

```python
# File: lip/pipeline.py, line 291
aml_passed = bool(c6_result.passed) if c6_result is not None else True
```

The `else True` branch is the fail-open default. If `c6_result` is `None` — because C6
timed out, threw an exception that was caught upstream, or was called with a configuration
that returned no result — the pipeline proceeds as if AML checks passed.

**Why `c6_result` can be `None`:**

In the pipeline's C6 call path, if `AMLChecker.check()` raises an exception, the pipeline
wraps it in a try/except block and assigns `c6_result = None` (or the equivalent of a
null result). The intent is to maintain availability — if AML infrastructure is down, the
pipeline should not halt. But the fail-open behavior means that AML infrastructure downtime
silently disables all AML screening.

**This is architecturally inverted from every other gate in the system:**

| Component | Unavailability behavior | Direction |
|-----------|------------------------|-----------|
| C8 KMS unavailable | Halt new offers | **Fail-closed** |
| Kill switch active | Block all pipelines | **Fail-closed** |
| C4 dispute classifier unavailable | Block (DISPUTE_DETECTION_UNAVAILABLE) | **Fail-closed** |
| **C6 AML unavailable** | **Pass all payments** | **Fail-open** |

The AML gate — the component most directly relevant to legal exposure — is the only
gate that fails open. Every other safety-critical component fails closed.

**The stress-regime amplification:**

A Kafka consumer lag spike, Redis connection pool exhaustion, or sanctions list API
timeout could cause C6 to fail. These exact conditions are also more likely during
high-volume stress periods — precisely when AML velocity monitoring is most important.
The system is most likely to disable AML screening during the periods when AML screening
is most needed.

**Resolution:**

1. **CIPHER:** Change the `c6_result is None` branch to fail-closed:
   ```python
   # Current (fail-open):
   aml_passed = bool(c6_result.passed) if c6_result is not None else True
   # Corrected (fail-closed):
   if c6_result is None:
       return PipelineResult(outcome="AML_CHECK_UNAVAILABLE", ...)
   aml_passed = bool(c6_result.passed)
   ```
2. **FORGE:** C6 unavailability should trigger a DORA Art.30 incident log entry and an
   alert to the bank's operations team — it is not a silent degraded mode.
3. **REX:** Document `AML_CHECK_UNAVAILABLE` as a distinct outcome in the decision log
   taxonomy. Regulators must be able to distinguish "AML check ran and passed" from
   "AML check did not run."

CIPHER, FORGE, and REX sign-off required. This is a fail-closed/fail-open architectural
decision — QUANT must also review for throughput impact.

---

## 17. Velocity Cap Tracks BIC, Not Economic Entity

**Severity: MEDIUM-HIGH**

**The problem:** The AML velocity caps (`AML_DOLLAR_CAP_USD = $1M/24h`,
`AML_COUNT_CAP = 100/24h`) are enforced per `entity_id`, and `entity_id` is the SWIFT BIC
of the sending bank. In correspondent banking, one BIC represents an entire bank institution,
not a single economic actor.

**Why BIC-level velocity tracking is the wrong unit:**

Deutsche Bank (`DEUTDEDB`) processes payments for thousands of corporate clients. Under
the current implementation:

- **If the cap is meant to detect structuring by a single economic entity:** Using Deutsche
  Bank's BIC means Siemens AG and BMW AG share the same velocity window. Neither company
  is structuring — but if their combined payments on a given day exceed $1M, LIP flags
  Deutsche Bank as a velocity-cap hit. This produces false positives and blocks legitimate
  institutional payments.

- **If the cap is meant to monitor Deutsche Bank itself as a counterparty:** The $1M/24h
  cap is inoperably small for a Tier 1 bank (as documented in EPG-16), and no single
  wire transfer at the correspondent banking level would be below that threshold anyway.

There is no scenario where BIC-level velocity tracking at $1M/24h is the correct policy
for correspondent banking. The unit of measurement is wrong for the product.

**The entity resolution dependency:**

The correct entity for velocity tracking is the end economic sender — the corporate
entity instructing its bank to make the payment. This entity identifier is in the
pacs.002 payment message (the `Dbtr` field, originator BIC + account). The current
pipeline extracts `sending_bic` as the entity ID throughout — it does not separately
extract the ultimate originator.

This is the same entity resolution problem identified in EPG-14 (borrower identity) and
EPG-24 (sanctions screening). All three AML components have the same root cause: the
pipeline uses the correspondent bank's BIC as a proxy for the economic actor, which is
wrong for all three purposes.

**The sanctions-velocity interaction:**

If Entity A at Deutsche Bank is on the OFAC SDN list, their entity-level sanctions
screening requires resolving "Entity A" — not "Deutsche Bank." Velocity tracking for
Entity A requires counting Entity A's transactions — not all Deutsche Bank transactions.
Without end-entity extraction, both sanctions screening and velocity tracking operate on
the wrong identifier.

**Resolution:**

1. **NOVA:** Extract the `Dbtr` (originator) BIC + account pair from the pacs.002 event
   in C5 during normalization. This is a richer entity identifier than `sending_bic` alone.
2. **CIPHER:** The velocity cap should use a composite entity key:
   `(sending_bic, originator_account_hash)` — the correspondent bank plus the specific
   account at that bank. This correctly scopes velocity tracking to the economic entity.
3. **QUANT:** The $1M/24h cap should be re-evaluated with the correct entity granularity.
   At end-entity granularity, $1M/24h may be appropriate for corporate clients; at BIC
   granularity it is inoperable.
4. **ARIA/DGEN:** The C1 training corpus should include entity-level features
   (originator account hash) as a signal, not just sending BIC, to capture entity-level
   behavioral patterns.

CIPHER sign-off required. NOVA sign-off required (pacs.002 field extraction change
affects C5 normalization). QUANT sign-off required (cap value changes).

---

## 18. Master Issue Register

All issues identified in this review, consolidated for tracking and assignment.

| ID | Issue | Section | Severity | Owner | Status |
|----|-------|---------|----------|-------|--------|
| EPG-01 | RR01–RR03 (KYC failures) not blocked — receive 3-day bridges | 2.2 | HIGH | REX + CIPHER | Open |
| EPG-02 | DNOR (DebtorNotAllowedToSend) not blocked — receives 7-day bridge | 2.3 | HIGH | REX + CIPHER | Open |
| EPG-03 | CNOR (CreditorNotAllowedToReceive) not blocked — receives 21-day bridge | 2.3 | HIGH | REX + CIPHER | Open |
| EPG-04 | Bank's own AML system structurally opaque to LIP (Gap C) | 2.4 | HIGH | REX + Legal | Open (contractual) |
| EPG-05 | Generic codes MS02/MS03/NARR hide AML reasoning and bypass all gates | 2.5 | MEDIUM-HIGH | REX + Legal | Open (contractual) |
| EPG-06 | PD model prices credit risk but not regulatory outcome risk | 2.6 | MEDIUM | QUANT + ARIA | Open |
| EPG-07 | RR04 in CLASS_A taxonomy — C7 is the only gate (no defense-in-depth) | 2.7 | LOW-MEDIUM | NOVA + REX | Open |
| EPG-08 | AG01, LEGL in CLASS_B/C taxonomy — same taxonomy/gate misalignment | 2.7 | LOW-MEDIUM | NOVA + REX | Open |
| EPG-09 | COMPLIANCE_HOLD_BLOCKS_BRIDGE maps to "DECLINED" in audit log — fall-through to FUNDED | 3 | CRITICAL | REX + NOVA | **ESCALATED** |
| EPG-10 | No distinct PipelineResult outcome for compliance hold blocks — 3 other statuses also fall through | 3 | CRITICAL | NOVA | **ESCALATED** |
| EPG-11 | Compliance hold blocks don't trigger compliance team notification | 3 | HIGH | REX + FORGE | **ESCALATED** |
| EPG-12 | C1 trained on all failures including non-bridgeable ones | 4 | MEDIUM | ARIA + DGEN | Open |
| EPG-13 | τ*=0.110 optimized on mixed population (bridgeable + non-bridgeable) | 4 | MEDIUM | ARIA + QUANT | Open |
| EPG-14 | sending_bic is the bank, not the end customer — MRFA and PD are misaligned | 5 | HIGH | REX + ARIA | Open |
| EPG-15 | Thin-file C2 fires on institutional BICs with public credit data | 5 | MEDIUM | ARIA | Open |
| EPG-16 | Default AML dollar cap $1M inoperable for correspondent banking | 6 | MEDIUM | CIPHER + NOVA | Open |
| EPG-17 | C8 token must require explicit AML cap — no deployment-time enforcement | 6 | MEDIUM | CIPHER + FORGE | Open |
| EPG-18 | Anomaly detection advisory-only — should trigger human review | 7 | MEDIUM | CIPHER + REX | Open |
| EPG-19 | CLASS_B labeled "Compliance/AML holds" in constants but not treated as such | 8 | MEDIUM | Founder decision | Open |
| EPG-20 | Patent claims may implicitly cover compliance-hold bridging | 9 | STRATEGIC | Legal + REX | Open |
| EPG-21 | FATF tipping-off interaction could appear in patent prosecution record | 9 | STRATEGIC | Legal | Open |
| EPG-22 | C1 training objective should be bridgeability, not failure detection | 10 | MEDIUM | ARIA + DGEN | Open |
| EPG-23 | Expired offer log entries are indistinguishable from funded offers | 11 | MEDIUM | NOVA + REX | Open |
| EPG-24 | Sanctions screening disabled by default — BIC codes passed as entity names, Jaccard = 0 | 13 | CRITICAL | CIPHER + FORGE | Open |
| EPG-25 | AML velocity check TOCTOU — check() and record() are non-atomic; concurrent workers bypass cap | 14 | HIGH | CIPHER | Open |
| EPG-26 | Human review dead end — PENDING_HUMAN_REVIEW has no pipeline re-entry path; human decision goes nowhere | 15 | HIGH | NOVA + FORGE + REX | Open |
| EPG-27 | AML fail-open default — C6 unavailability passes all payments (`c6_result is None → True`) | 16 | HIGH | CIPHER + FORGE | Open |
| EPG-28 | Velocity cap tracks BIC not economic entity — wrong unit for correspondent banking | 17 | MEDIUM-HIGH | CIPHER + NOVA + QUANT | Open |

---

## 19. Recommended Resolution Priority Order

### Tier 0 — Immediate Hotfixes (Active Defects in Deployed Code)

These are defects where current code, if executed, produces incorrect or illegal behavior.
They are not design gaps — they are bugs that must be patched before any further testing.

0. **EPG-09, EPG-10, EPG-11 (ESCALATED)** — Fix `pipeline.py:418` to handle
   `COMPLIANCE_HOLD_BLOCKS_BRIDGE`, `BELOW_MIN_LOAN_AMOUNT`, `BELOW_MIN_CASH_FEE`, and
   `LOAN_AMOUNT_MISMATCH`. Four-line code change. All four currently produce
   `outcome="FUNDED"` in the PipelineResult despite being declines. NOVA must fix today.

   **EPG-27** — Change C6 fail-open to fail-closed in `pipeline.py:291`. The one-line
   change (`else True` → `return PipelineResult(outcome="AML_CHECK_UNAVAILABLE")`) inverts
   a fundamentally wrong safety property. CIPHER sign-off, FORGE deployment.

   **EPG-24** — Make `entity_name_resolver` a required constructor parameter in
   `AMLChecker`. Every deployment running with the current default has sanctions screening
   disabled. CIPHER sign-off.

### Tier 1 — Before Any Bank Pilot (Legal / Regulatory Risk)

These issues create direct legal or regulatory exposure if a live deployment processes
even one payment incorrectly. They must be resolved before any production pilot.

1. **EPG-01, EPG-02, EPG-03** — Add `RR01`, `RR02`, `RR03`, `DNOR`, `CNOR` to
   `_COMPLIANCE_HOLD_CODES`. Three-line code change with REX+CIPHER sign-off. Highest
   priority because it closes concrete AML/KYC lending vulnerabilities.

2. **EPG-25** — Implement atomic Redis check-and-reserve for velocity caps. The current
   TOCTOU race allows payments to bypass AML dollar and count caps under concurrent load.
   CIPHER must design the Lua script; FORGE deploys and adds concurrency CI test.

3. **EPG-26** — Implement human review re-entry path. Until resolved, every
   `PENDING_HUMAN_REVIEW` payment is silently timed out. This makes EU AI Act Article 14
   human oversight compliance non-operational. NOVA + FORGE design and implement.

4. **EPG-04, EPG-05** — Draft the contractual requirement for banks to provide a compliance
   hold register API. This cannot wait for implementation — it must be in the first version
   of the BPI License Agreement. REX and legal counsel work only.

5. **EPG-07, EPG-08** — Move `RR04`, `AG01`, `LEGL` to BLOCK class in taxonomy for
   defense-in-depth. This is a YAML file change and QUANT/REX sign-off.

### Tier 2 — Before First Commercial License (Operational Viability)

These issues will prevent the first commercial deployment from functioning correctly, even
if they do not create legal exposure.

6. **EPG-16, EPG-17** — Fix default AML cap and enforce explicit configuration in C8 token.
   Without this, any correspondent bank deploying LIP will be inoperable by 9 AM.

7. **EPG-28** — Fix velocity cap entity granularity: use composite
   `(sending_bic, originator_account_hash)` key instead of bare BIC. Required before
   AML velocity tracking has any meaning for end-entity detection.

8. **EPG-14** — Clarify MRFA borrower entity (bank vs. end customer). Required before any
   bank signs a legal agreement with an enrolled borrower.

9. **EPG-18** — Route anomaly-flagged transactions to human review. Required for EU AI Act
   Article 14 compliance in regulated jurisdictions.

### Tier 3 — Before First Regulated-Jurisdiction Deployment (Model Governance)

These issues are required for SR 11-7 / EU AI Act compliance in regulated markets.

10. **EPG-12, EPG-13, EPG-22** — Relabel C1 training corpus for bridgeability, re-optimize τ*.
    Required for SR 11-7 model documentation and EU AI Act Article 13.

11. **EPG-06** — Document regulatory-outcome default risk gap in C2 model card. Required for
    SR 11-7 model risk management.

12. **EPG-15** — Ensure enrolled institutional BICs have explicit tier assignments, preventing
    thin-file fallback for entities with public credit data.

### Tier 4 — Strategic / Long-Term

13. **EPG-19** — Founder-level product decision: does LIP fund compliance-hold Class B
    payments or not? This decision has cascading implications for patent claims, fee calibration,
    and C6 design.

14. **EPG-20, EPG-21** — Patent counsel review of compliance-hold code coverage in claims.
    Required before P1 non-provisional filing.

15. **EPG-23** — Offer log entry lifecycle management (relates to GAP-01 resolution).

---

## Document Metadata

**Prepared by:** Epignosis architecture review, March 2026
**Last updated:** 2026-03-18 — Sections 13–17 added (EPG-24–28); EPG-09/10/11 escalated to CRITICAL; Tier 0 priority order added
**Codebase commit:** Current `main` branch, PRKT2026 repository — sync at commit `fe09cb6`
**Key files reviewed:**
- `lip/pipeline.py` (Algorithm 1, full execution flow)
- `lip/c7_execution_agent/agent.py` (compliance hold codes, execution gates)
- `lip/c6_aml_velocity/aml_checker.py` (AML gate architecture)
- `lip/configs/rejection_taxonomy.yaml` (rejection code classification)
- `lip/common/constants.py` (canonical constants, settlement P95 labels)
- `docs/compliance.md` (SR 11-7, EU AI Act, DORA, AML/CFT)
- `CLIENT_PERSPECTIVE_ANALYSIS.md` (operational gaps 1–17)
- `consolidation files/BPI_Gap_Analysis_v2.0.md` (licensing model gaps)
- `consolidation files/BPI_Architecture_Specification_v1.2.md` (three-entity model)
- `CLAUDE.md` (canonical constants, agent sign-off authorities)

**Review standard:** Every issue in this document was derived from reading the actual source.
No issue is speculative. All code references are precise. No semantics were inferred from
field names — source implementation was read for every assessment.

**Next step:** Team working session to triage the Master Issue Register (Section 13) by
Tier, assign owners from the agent table in CLAUDE.md, and schedule resolution in the
Master Action Plan.
