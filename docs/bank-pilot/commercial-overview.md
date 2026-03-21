# LIP Commercial Overview

> BPI Lending Intelligence Platform — Three-Phase Deployment Model

---

## What LIP Does

LIP processes ISO 20022 payment failure events (pacs.002, pacs.008) and determines in real time whether a bridge loan is appropriate. When a cross-border payment fails due to a technical or procedural error, LIP classifies the failure, assesses credit risk, and — if all gates pass — funds a short-term bridge loan so the beneficiary receives payment on time while the error is resolved.

The platform runs entirely within the bank's infrastructure. BPI provides the technology; the bank provides the capital and origination.

---

## Three-Phase Deployment Model

### Phase 1 — LICENSOR (Technology License)

The bank deploys LIP on its own infrastructure using a technology license from BPI.

| Parameter | Value |
|-----------|-------|
| **BPI role** | Technology licensor (IP provider) |
| **Bank role** | Capital provider, originator, operator |
| **BPI revenue share** | 15% royalty on bridge loan fees |
| **Bank revenue share** | 85% of bridge loan fees |
| **BPI balance sheet exposure** | None |
| **Revenue classification** | Royalty income (IP licensing) |
| **Fee floor** | 300 basis points annualised |

**Phase 1 is the pilot engagement.** The bank funds all bridge loans from its own balance sheet, retains 85% of fee revenue, and pays BPI a 15% technology royalty. BPI has zero balance sheet exposure — pure licensing revenue.

---

### Phase 2 — HYBRID (Co-Lending)

BPI co-funds bridge loans alongside the bank's capital.

| Parameter | Value |
|-----------|-------|
| **BPI role** | Co-lender + technology provider |
| **Bank role** | Co-lender, originator |
| **BPI revenue share** | 40% of bridge loan fees |
| **Bank revenue share** | 60% of bridge loan fees |
| **BPI balance sheet exposure** | Proportional to co-funding share |
| **Revenue classification** | Lending revenue (not royalty) |

**Tax and legal distinction:** Phase 2 revenue is lending revenue, not royalty income. This has different tax treatment, capital requirements, and regulatory obligations compared to Phase 1. The distinction is material for both parties' financial reporting.

---

### Phase 3 — FULL_MLO (Managed Lending Operations)

BPI manages the full lending stack. The bank provides origination and distribution.

| Parameter | Value |
|-----------|-------|
| **BPI role** | Full-stack lending operator (MLO) |
| **Bank role** | Originator, distribution channel |
| **BPI revenue share** | 75% of bridge loan fees |
| **Bank revenue share** | 25% of bridge loan fees |
| **BPI balance sheet exposure** | Full |
| **Revenue classification** | Lending revenue |

---

## Fee Decomposition

Bridge loan fees are decomposed into two components:

**Capital return component:** Compensates the capital provider for the time value of money and credit risk. This is the baseline return any lender would require.

**Distribution premium:** Compensates the originator/distributor for payment flow access, bank relationship, and regulatory infrastructure. This premium reflects the value of the bank's distribution channel.

| Phase | Capital Return | Distribution Premium | Total BPI Share |
|-------|---------------|---------------------|----------------|
| Phase 1 | 0% (bank funds) | 15% royalty | 15% |
| Phase 2 | ~25% (pro-rata) | ~15% | 40% |
| Phase 3 | ~60% (full funding) | ~15% | 75% |

This decomposition is critical for Phase 3 negotiations: the distribution premium remains stable across phases because the bank's distribution value doesn't change. What changes is who provides capital. Separating these components prevents a bank from arguing that the Phase 3 split should be lower because "they're still providing the same distribution" — the premium already accounts for that.

---

## Corridor Economics Example

**Scenario:** EUR→USD corridor, $1M payment, Class A failure (3-day maturity), Tier 1 counterparty (investment-grade, known entity).

| Item | Calculation | Value |
|------|-----------|-------|
| Principal | — | $1,000,000 |
| Fee rate | 300 bps annualised (Tier 1 floor) | 3.00% p.a. |
| Maturity | Class A (technical error) | 3 days |
| **Total fee** | $1M × 3.00% × 3/365 | **$246.58** |
| **BPI Phase 1 share** (15% royalty) | $246.58 × 15% | **$36.99** |
| **Bank Phase 1 share** (85%) | $246.58 × 85% | **$209.59** |

**At scale (illustrative):**

| Metric | Monthly | Annual |
|--------|---------|--------|
| Payment failures processed | 10,000 | 120,000 |
| Bridgeable (after all gates) | 3,000 | 36,000 |
| Average principal | $500,000 | — |
| Average fee per loan | $200 | — |
| **Total fee revenue** | $600,000 | $7,200,000 |
| **BPI Phase 1 royalty** | $90,000 | $1,080,000 |
| **Bank Phase 1 revenue** | $510,000 | $6,120,000 |

These figures are illustrative. Actual volumes depend on the bank's payment corridor mix, failure rates, and the proportion of failures that pass all classification gates.

---

## Tier Pricing

| Tier | Entity Type | Fee Range (bps) | Maturity Classes |
|------|------------|----------------|-----------------|
| **Tier 1** | Investment-grade, listed | 300–539 | A, C |
| **Tier 2** | Private company, balance-sheet data | 540–899 | A, C |
| **Tier 3** | Thin file (no history) | 900–1500 | A, C |

- **Class A** (technical errors): 3-day maturity — missing data, format errors, account number issues
- **Class B** (procedural holds): Currently blocked — requires Bridgeability Certification API integration (see Legal Prerequisites)
- **Class C** (systemic/processing): 21-day maturity — correspondent chain delays, regulatory processing

Known-entity registration allows investment-grade banks to be classified as Tier 1 immediately, bypassing the thin-file default.

---

## What the Bank Gets

1. **New revenue stream** on payment failures that currently generate zero revenue
2. **Customer retention** — beneficiaries receive payment on time despite technical failures
3. **Automated credit decisioning** — no manual underwriting for bridge loans
4. **Regulatory compliance built-in** — DORA Art.19, SR 11-7, EU AI Act Art.14
5. **Kill switch** — human oversight with one-click emergency halt
6. **Zero infrastructure build** — LIP deploys as containers on bank's existing K8s

## What BPI Gets

1. **Phase 1:** Pure royalty income with zero balance sheet risk
2. **Phase 2/3:** Lending revenue with balance sheet participation
3. **Patent protection** on the two-step classification + conditional offer mechanism
4. **Platform lock-in** — LIP's ML models improve with the bank's data; switching costs increase over time
