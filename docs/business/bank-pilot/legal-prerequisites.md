# LIP Legal Prerequisites Checklist

> Requirements that must be in place before pilot bank LOI signature.
> Current technical status: see [`../../CURRENT_STATE.md`](../../CURRENT_STATE.md). This checklist remains gating even when the engineering RC is ready.

---

## 1. Bridgeability Certification API (EPG-04/05)

The most critical legal prerequisite. LIP cannot distinguish between technical payment failures and regulatory/compliance holds. The bank must expose a binary certification signal.

### API Requirement

The bank must implement and maintain a Bridgeability Certification API ("BC API") that returns, for each payment failure event:

```
hold_bridgeable:    boolean
    true  = payment is eligible for a bridge loan under bank's internal
            compliance policies
    false = payment is subject to a hold rendering a bridge loan unlawful

certified_by:       string
    Unique identifier of the automated compliance system that generated
    this certification

certification_ts:   ISO 8601 datetime (UTC)
    Timestamp of certification

uetr:               string (UUID v4)
    Unique End-to-End Transaction Reference
```

### Structure

This follows the FATF Recommendation 13 correspondent KYC certification structure: the bank certifies the payment's bridgeability without disclosing the reason for any hold. BPI never sees why a payment was held — only whether it is safe to bridge.

### Three Warranties Required

**1. Certification Warranty**

The bank warrants that any `hold_bridgeable: true` payment is not, at the time of certification, subject to:
- A freeze, block, or hold by any government authority (including sanctions authorities)
- An internal hold arising from suspicious activity monitoring
- An incomplete KYC/KYB/EDD process
- A court order, injunction, or judicial freeze
- Any hold arising from applicable anti-money laundering, counter-terrorist financing, or sanctions law

**2. System Integrity Warranty**

The bank warrants that all certifications are generated exclusively by an automated compliance system with:
- No manual entry or manual override capability for the `hold_bridgeable` value
- Documented change management requiring compliance function approval
- Access controls preventing individual modification of certification outcomes
- Audit log retained for minimum 7 years
- Annual internal audit review

**3. Indemnification**

The bank indemnifies BPI for all losses arising from:
- Any `hold_bridgeable: true` certification where the payment was under a hold at certification time
- Any breach of the certification or system integrity warranties

**Negotiation lever:** Without the system integrity warranty (Warranty #2), Class B payments remain permanently blocked in LIP. The bank loses all B1 bridge loan revenue — the revenue opportunity from unlocking B1 should be quantified before negotiation.

### LIP Behaviour

- `hold_bridgeable: false` → hard block, no bridge offer generated, no override possible
- BC API unavailable/degraded → treated as `hold_bridgeable: false` (fail-closed)
- Class B remains block-all until the BC API is live and certified

---

## 2. Master Receivables Financing Agreement (MRFA) — EPG-14

### B2B Interbank Structure

The MRFA must establish that bridge loans are B2B interbank credit facilities:

- **Borrower:** The enrolled originating bank (e.g., Deutsche Bank), NOT the end customer (e.g., Siemens)
- **Repayment:** Unconditional — due at maturity regardless of whether the underlying payment settles
- **Governing law:** Derived from the borrower bank's BIC jurisdiction (chars 4–5), not from payment currency

### Required Clauses

| Clause | Description | Priority |
|--------|-------------|----------|
| **B2B interbank clause** | Originating bank is borrower; repayment not contingent on underlying payment | Tier 1 — blocking |
| **Permanently-blocked-payment clause** | Repayment due at maturity regardless of payment outcome | Tier 1 — blocking |
| **Screening limitation indemnity** | Bank indemnifies BPI for C6 screen limitations (LIP cannot see bank's internal holds or reporting history) | Tier 1 — blocking |

---

## 3. Regulatory Compliance

### DORA Art.19 — ICT Incident Reporting

LIP generates DORA-compliant incident reports (kill switch activations, system failures, anomaly events). The bank is responsible for submitting these to their National Competent Authority.

**Bank obligation:** Integrate LIP's `/admin/regulatory/dora/export` endpoint into their NCA reporting workflow.

### SR 11-7 — Model Risk Management

LIP includes two ML models requiring quarterly validation:
- **C1** — Failure classifier (binary classification, F-beta optimised)
- **C2** — PD model (probability of default, tiered fee assignment)

LIP pre-generates validation reports accessible via `/admin/regulatory/sr117/export`. The bank's model risk management team must:
- Review quarterly validation reports
- Maintain model cards (provided by BPI)
- Document out-of-time validation results
- Submit to the relevant regulatory authority

### EU AI Act Art.14 — Human Oversight

LIP satisfies Art.14 through:
- **Kill switch:** Human operator can halt all new origination instantly
- **C6 anomaly flags:** Suspicious patterns route to `PENDING_HUMAN_REVIEW` — a human must clear before proceeding
- **Decision log:** 7-year retention of all pipeline decisions with full audit trail

**Bank obligation:** Designate a human oversight function with authority to engage the kill switch and review C6 anomaly flags.

---

## 4. Language Requirements (EPG-20/21)

### Prohibited Terms

The following terms must NOT appear in any published specification, patent filing, marketing material, or bank-facing document:

| Prohibited | Use Instead |
|-----------|-------------|
| AML | (do not reference) |
| SAR | (do not reference) |
| OFAC | (do not reference) |
| SDN | (do not reference) |
| Compliance investigation | (do not reference) |
| Tipping-off | (do not reference) |
| Suspicious activity | (do not reference) |
| PEP | (do not reference) |

### Approved Terminology

| Concept | Approved Term |
|---------|--------------|
| Classification of payment failures | Classification gate |
| Compliance-hold detection | Hold type discriminator |
| Bank's bridgeability certification | Bridgeability flag |
| Technical/procedural hold | Procedural hold |
| Investigation-related hold | Investigatory hold |

### Patent Filing Rule

Patent claims must cover the existence of the classification gate mechanism, not enumerate the specific codes or categories it blocks. Enumerating the block list in a claim creates a circumvention roadmap.

---

## 5. Pre-LOI Checklist

| Item | Owner | Status | Blocking? |
|------|-------|--------|-----------|
| BC API specification reviewed by bank CTO | Bank | Pending | Yes |
| Three warranties agreed in principle | Bank Legal + BPI Legal | Pending | Yes |
| MRFA B2B interbank clause drafted | BPI Legal | Pending | Yes |
| MRFA permanently-blocked-payment clause drafted | BPI Legal | Pending | Yes |
| Screening limitation indemnity drafted | BPI Legal | Pending | Yes |
| DORA reporting integration plan | Bank Ops | Pending | No |
| SR 11-7 model governance assignment | Bank MRM | Pending | No |
| Human oversight function designated | Bank Compliance | Pending | No |
| Language scrub of all bank-facing materials | BPI | Pending | Yes |
| Patent counsel briefing scheduled | BPI Legal | Pending | No |

---

## 6. Sequence

1. **Before first bank meeting:** Language scrub complete, commercial overview prepared
2. **First meeting:** Commercial overview + demo walkthrough
3. **Second meeting:** Technical integration guide + BC API specification
4. **Legal review:** Bank's legal team reviews MRFA clauses + warranty package
5. **LOI signature:** All Tier 1 blocking items resolved
6. **Integration:** Bank builds BC API, BPI deploys LIP to bank infrastructure
7. **Go-live:** Health checks pass, first Class A bridge loan funded
