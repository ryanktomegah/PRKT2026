# Bridgepoint Intelligence — P4 v0 Implementation Blueprint
## Pre-Emptive Liquidity Facility: Predictive Delay Intelligence & Automated Standby Drawdown
## Survival Analysis Architecture, ERP Integration Model & Corporate Treasury Playbook
Version 1.0 | Confidential | March 2026

---

## Table of Contents
1. Executive Summary
2. Part 1 — Why This Product Does Not Exist (And Why It Should)
3. Part 2 — Legal Entity & Facility Structure
4. Part 3 — Technical Architecture: From Survival Curve to Facility Drawdown
5. Part 4 — Revenue Architecture
6. Part 5 — C-Component Engineering Map
7. Part 6 — ERP Integration Architecture
8. Part 7 — Consolidated Engineering Timeline
9. Part 8 — What Stays in the Long-Horizon P4 Patent
10. Part 9 — Risk Register

---

## 1. Executive Summary

This document is the engineering, legal, and commercial blueprint for launching P4 v0 — the Pre-Emptive Liquidity Facility — a product that offers corporate treasurers a standby credit facility that activates *before* a payment fails, not after. The facility is triggered by Bridgepoint's C9 Cox Proportional Hazards survival model, which predicts settlement delay probability for each incoming payment in real time.

**Why this matters:** The global cost of failed payments is $118.5B/year (Accuity/LexisNexis, 2021). But the cost of *anticipated* failed payments — the treasury resources, overdraft facilities, and opportunity costs that corporates bear while waiting for delayed payments — is estimated at 3–5× the direct failure cost. A $50M payment that arrives 7 days late costs the receiving corporate $50M × 7/365 × overdraft rate (~500 bps) = $47,945 in direct interest cost, plus unquantifiable operational disruption. P4 eliminates this cost by pre-positioning liquidity before the delay materialises.

**Why nobody has built this:** Three prerequisites had to converge simultaneously, and until Bridgepoint, they never have:

1. **Real-time payment settlement prediction** — requires a trained survival model on actual payment settlement data. SWIFT gpi has existed since 2017, but no one has built a Cox PH model on gpi tracking data to predict settlement time at the individual payment level. Bridgepoint's C9 (`SettlementTimePredictor` in `lip/c9_settlement_predictor/model.py`) is the first implementation.

2. **Triggering mechanism that operates before failure** — existing products (Taulia, C2FO, PrimeRevenue) operate on *invoices*, not *payments*. They accelerate payment of an invoice that already exists. P4 operates on the *settlement prediction* of a payment that has already been initiated but not yet settled — a fundamentally different triggering point in the payment lifecycle.

3. **Integrated lending infrastructure** — the facility drawdown requires a bank partner (ELO) with pre-approved credit lines. Bridgepoint's existing Phase 1/2/3 bank deployment model provides this infrastructure already. P4 is not a new product from scratch — it is a new triggering mechanism on top of existing lending infrastructure.

**Core thesis:** P4 v0 does not require a new lending licence, a new bank partner, or a new ML model. It requires a hazard rate extraction API on the existing C9 Cox PH survival model, a Payment Expectation Graph that aggregates corporate expected payments from ERP data, and a facility lifecycle manager that connects the prediction to the bank's credit decision. The lending infrastructure (C7 execution, C3 settlement monitoring, C8 licensing) is reused unchanged.

**Engineering summary:**

| Component | P4 v0 Impact | Effort |
|-----------|-------------|--------|
| C1 — ML Failure Classifier | No change | 0 |
| C2 — PD Pricing Engine | Extend: facility pricing (commitment + utilization fees) | 2–3 weeks |
| C3 — Settlement Monitor | Extend: facility settlement trigger, auto-drawdown on delay | 2 weeks |
| C4 — Dispute Classifier | No change | 0 |
| C5 — ISO 20022 Processor | No change | 0 |
| C6 — AML / Security | Minor: facility velocity monitoring | 1 week |
| C7 — Bank Integration Layer | Extend: facility offer/accept/draw/repay API, ERP connector interface | 6–8 weeks |
| C8 — Licensing & Metering | Extend: facility fee accrual, commitment fee metering | 2–3 weeks |
| C9 — Settlement Predictor | Extend: hazard rate extraction API, confidence-gated facility trigger | 3–4 weeks |
| NEW — Payment Expectation Graph | New module: corporate expected payment DAG from ERP + observed data | 4–5 weeks |
| NEW — Facility Lifecycle Manager | New module: state machine for OFFERED → ACCEPTED → ACTIVE → DRAWN → REPAID | 2–3 weeks |

Total engineering effort: ~22–28 engineer-weeks across 2 senior engineers.
Calendar time: ~7 months from greenlight.
Target: Shadow run Q3 2028; Live pilot Q1 2029 (requires 12 months of C9 production settlement data for model validation).

---

## 2. Part 1 — Why This Product Does Not Exist (And Why It Should)

### 2.1 The Gap in the Market

Every existing working capital product operates *after* a trigger event that has already occurred:

| Product | Trigger | When It Activates | Limitation |
|---------|---------|-------------------|------------|
| **Invoice factoring** (Taulia, C2FO) | Invoice issued | After invoice exists, before payment due date | Prices based on invoice age, not settlement probability. Cannot predict delays. |
| **Supply chain finance** (PrimeRevenue, Citi SCF) | Buyer approves invoice | After buyer confirms, before payment date | Only works with pre-approved buyer-supplier pairs. No prediction capability. |
| **Bridge lending** (Bridgepoint P2) | Payment fails | After failure detected | Reactive — corporate has already experienced the cash flow gap. |
| **Overdraft facilities** (banks) | Account goes negative | After cash runs out | Expensive (500+ bps), punitive, damages credit relationship. |
| **Cash forecasting** (Kyriba, HighRadius, Trovata) | Historical patterns | Forecast accuracy degrades beyond 7 days; no per-payment granularity | Tells you cash *might* be short; doesn't provide liquidity when it is. |

**P4 fills the gap between "invoice exists" and "payment fails":**

```
Invoice issued → Payment initiated → [P4 OPERATES HERE] → Payment settles (or fails)
                                          │
                                     C9 predicts P(delay) > 0.85
                                     Facility pre-positioned
                                     Corporate never feels the gap
```

This is the only product in the market that uses real-time settlement prediction to pre-position liquidity. The closest comparisons — Kyriba's AI Cash Forecasting ($400M+ revenue parent) and HighRadius Treasury ($3.1B valuation, IDC Leader 2025-2026) — forecast cash positions at the portfolio level. Neither predicts individual payment settlement times. Neither triggers liquidity provisioning.

### 2.2 Why The Survival Model Makes This Possible

The Cox Proportional Hazards model is the correct statistical framework for P4 because it answers the exact question P4 needs answered: "What is the probability that this specific payment will take longer than X hours to settle?"

**Existing C9 implementation** (`lip/c9_settlement_predictor/model.py`, 386 lines):

- **Model type:** Cox PH (semi-parametric survival analysis, Cox 1972)
- **Features (16-dimensional):**
  - `log_amount_usd` — larger payments settle slower (correspondent banking queue priority)
  - Rejection class one-hot: CLASS_A (routing), CLASS_B (systemic), CLASS_C (liquidity/sanctions)
  - BIC tiers (sender, receiver): Tier 1 banks settle 20% faster than Tier 3
  - Cyclical time-of-day / day-of-week: after-hours penalty +15%, weekend +30%
  - Historical P50 hours for corridor
  - Top-5 corridor one-hot (USD-EUR, EUR-GBP, USD-CNY, EUR-JPY, USD-GBP)
- **Output:** `SettlementPrediction` with `predicted_hours`, `confidence_lower_hours`, `confidence_upper_hours`, `dynamic_maturity_hours`
- **Calibration:** CLASS_A LogNormal(μ=1.4, σ=0.6) → median 4h; CLASS_B LogNormal(μ=3.6, σ=0.5) → median 36h; CLASS_C LogNormal(μ=4.8, σ=0.4) → median 120h
- **Safety margin:** 1.5× on dynamic maturity (SETTLEMENT_SAFETY_MARGIN constant, QUANT sign-off required)
- **Fallback heuristic:** When lifelines library unavailable, uses BIS/SWIFT gpi-calibrated medians

**What P4 adds to C9:** A hazard rate extraction API that converts the survival curve into a probability statement:

```
P(delay > threshold_hours) = S(threshold_hours | features)
```

Where `S(t)` is the survival function from the fitted Cox PH model. The hazard rate `h(t)` = `-dlog(S(t))/dt` gives the instantaneous rate of settlement at time `t`, conditional on not having settled by `t`. This is computed directly from the existing model coefficients — **no retraining required**.

### 2.3 Academic Validation

The application of survival analysis to payment settlement prediction has sparse but growing academic support:

- **Cox PH in financial time-to-event:** Well-established in credit risk (time to default), insurance (time to claim), and healthcare (time to readmission). Application to payment settlement timing is novel but methodologically identical.
- **DeepSurv:** Lee et al. (2018) demonstrate that neural network-based survival models achieve 16.15% higher concordance index than random survival forests on similar time-to-event financial data. This is the documented upgrade path from C9's Cox PH baseline.
- **No published prior art** on Cox PH applied specifically to cross-border payment settlement timing. This is a publishable contribution and supports P4 patent claims. BPI should consider publishing a whitepaper (with carefully redacted implementation details) to establish academic priority.

---

## 3. Part 2 — Legal Entity & Facility Structure

### 3.1 Why Standby Facility (Not Revolving Credit)

The optimal legal structure for P4 v0 is an uncommitted standby facility, not a revolving credit line. The reasons are regulatory, commercial, and strategic:

**Basel III / CRR III capital treatment:**

| Facility Type | Credit Conversion Factor (CCF) | Bank Capital Charge | BPI Implication |
|---------------|-------------------------------|--------------------|--------------------|
| Committed revolving credit | 40% (CRR III, effective 2025) | 40% × RWA on full facility limit | Bank must hold capital against entire facility — expensive |
| Uncommitted standby facility | 0% (current); rising to 10% by 2033 | Near-zero capital charge | Bank's cost is minimal — P4 is economically attractive |

**Critical structural requirement:** For the facility to remain "uncommitted" under Basel III, the bank must retain final approval right on every drawdown. BPI's role is to *recommend* a drawdown based on C9 prediction — the bank's credit system makes the final decision. This is not a limitation; it is the design. BPI provides intelligence, not credit decisions. The bank retains regulatory responsibility, and the facility avoids the 40% CCF that would make it uneconomical.

**Legal opinion required:** Basel counsel must confirm that BPI's predictive trigger + bank's automated approval (with override capability) constitutes an "uncommitted" facility under CRR Article 111. The key question: does a pre-approved automated response to BPI's trigger constitute a "commitment"? Precedent suggests no — so long as the bank can override any individual drawdown without penalty.

### 3.2 Entity Stack

```
CORPORATE TREASURY (Facility Beneficiary)
Role: Expected payment data provider (via ERP API), facility beneficiary
Integration: ERP → Payment Expectation Graph → C9 hazard predictions
         │
         │  Facility Master Agreement (bank ↔ corporate)
         │  Technology Schedule (BPI intelligence embedded, white-label)
         │  ERP Data Sharing Consent (corporate → BPI, anonymised)
         │
BANK / ELO PARTNER (Facility Provider)
Role: Credit decision maker, facility funder, lender of record
Mechanism: Receives BPI hazard predictions → auto-approves drawdowns below pre-set thresholds
           → manual review above thresholds
Revenue: Utilization fee (bps on drawn) + commitment fee (bps on undrawn)
         │
         │  Technology Licensing Agreement (bank ↔ BPI, same as P2)
         │  Predictive Intelligence Addendum (P4-specific terms)
         │  Data Processing Agreement (GDPR Art. 28)
         │
BRIDGEPOINT INTELLIGENCE INC. (Canada — BC ULC)
Role: Predictive intelligence provider, facility recommendation engine
Revenue: BPI intelligence premium (10–25 bps) + share of bank's facility fees
         (Phase 1: 30% royalty; Phase 2: 55% co-lending; Phase 3: 80% MLO)
Does NOT: Hold credit risk, make credit decisions, disburse funds
```

### 3.3 Facility Master Agreement Structure

The Facility Master Agreement between bank and corporate includes a BPI Technology Schedule that governs the predictive trigger:

| Clause | Content |
|--------|---------|
| **Trigger definition** | Facility drawdown is recommended when BPI C9 model predicts P(delay > corporate_threshold_hours) > confidence_gate (default 0.85) |
| **Bank override right** | Bank retains absolute right to decline any recommended drawdown without penalty or explanation. Required for "uncommitted" Basel III classification. |
| **Auto-approval thresholds** | Bank pre-sets: max auto-approve amount (e.g., $1M), max auto-approve per day (e.g., $5M), restricted corridors, restricted BIC lists |
| **Corporate consent** | Corporate consents to ERP data sharing (anonymised payment expectations) with BPI for prediction purposes |
| **Pricing** | Commitment fee: [25–75] bps p.a. on facility limit. Utilization fee: [150–250] bps on drawn amount. BPI premium: included in utilization fee, not separately disclosed to corporate. |
| **Repayment** | Auto-repayment on UETR settlement confirmation (same C3 loop as P2 bridge lending). If payment permanently fails, maturity-based repayment per standard facility terms. |
| **Liability limitation** | BPI provides predictive intelligence only. No liability for prediction accuracy. Bank retains credit risk. Corporate retains operational risk. |

---

## 4. Part 3 — Technical Architecture: From Survival Curve to Facility Drawdown

### 4.1 Payment Expectation Graph (New Data Structure)

The Payment Expectation Graph is a directed acyclic graph representing a corporate's expected incoming payments over a configurable horizon (default: 30 days). Each node is an expected payment; edges represent dependencies (e.g., payment B is contingent on payment A settling first).

**Data Sources:**
1. **ERP integration** (primary): SAP S/4HANA, Oracle Cloud ERP, or Kyriba expose expected receivables via API
2. **Observed payment patterns** (secondary): BPI's own observation of payment flows through the bank/ELO, enriched with historical settlement times
3. **Corporate manual input** (fallback): Treasury team manually registers expected payments in BPI portal

**Graph Node Schema:**
```json
{
  "node_id": "PEG-2028-0742",
  "corporate_id": "hashed:abc123",
  "source": "ERP_SAP",
  "payment": {
    "expected_from_bic": "DEUTDEFF",
    "amount_usd": 1250000.00,
    "currency": "EUR",
    "expected_date": "2028-08-14",
    "corridor": "EU-APAC",
    "erp_confidence": 0.95,
    "dependency_type": "INVOICE",
    "invoice_id": "INV-2028-4521",
    "payment_terms": "NET30"
  },
  "prediction": {
    "c9_delay_probability": null,
    "c9_predicted_hours": null,
    "trigger_grade": null,
    "last_predicted_at": null
  },
  "facility": {
    "eligible": true,
    "recommended_amount_usd": null,
    "facility_id": null,
    "status": "MONITORING"
  },
  "dependencies": ["PEG-2028-0738"],
  "created_at": "2028-08-01T00:00:00Z"
}
```

**Graph Construction Algorithm:**

1. **Ingest:** Pull expected receivables from ERP (batch: daily; incremental: every 4 hours)
2. **Enrich:** For each expected payment, query C9 for settlement prediction using corridor + BIC features
3. **Score:** Compute P(delay > corporate_threshold) for each payment
4. **Prioritise:** Rank payments by: (a) delay probability, (b) amount, (c) corporate cash buffer impact
5. **Trigger:** For payments where P(delay) > FACILITY_MIN_CONFIDENCE (0.85) AND amount > facility minimum, generate facility recommendation
6. **Update:** As new data arrives (SWIFT gpi tracking updates, ERP changes), re-score affected payments

### 4.2 Hazard Model (C9 Extension)

**New API surface on existing C9 model:**

```python
class SettlementTimePredictor:
    # ... existing methods ...

    def predict_delay_hazard(
        self,
        payment: PaymentFeatures,
        threshold_hours: float,
        confidence_level: float = 0.80,
    ) -> HazardPrediction:
        """
        Compute P(settlement_time > threshold_hours) for a specific payment.

        Uses the fitted Cox PH survival function S(t|X) where X is the
        payment's feature vector. No retraining — extracts hazard rate
        from existing model coefficients.

        Args:
            payment: Feature vector (corridor, amount, BIC tiers, etc.)
            threshold_hours: Corporate's cash buffer horizon
            confidence_level: Width of prediction interval (default 80%)

        Returns:
            HazardPrediction with delay_probability, confidence_interval,
            recommended_facility_amount, and trigger_grade.
        """
```

**HazardPrediction Schema:**
```json
{
  "delay_probability": 0.87,
  "confidence_interval": {
    "lower": 0.79,
    "upper": 0.93
  },
  "predicted_settlement_hours": 42.3,
  "threshold_hours": 24.0,
  "recommended_facility_amount_usd": 1250000.00,
  "trigger_grade": "A",
  "model_type": "cox_ph",
  "feature_importance": {
    "corridor_EU_APAC": 0.31,
    "log_amount_usd": 0.22,
    "bic_tier_sender": 0.18,
    "rejection_class_B": 0.15,
    "time_features": 0.14
  }
}
```

**Trigger Grades:**

| Grade | Delay Probability | CI Width | Action | Volume Target |
|-------|------------------|----------|--------|---------------|
| **A** | > 0.95 | < 10% | Auto-recommend to bank | Start here (Phase 1) |
| **B** | 0.85–0.95 | < 20% | Recommend with medium confidence | Phase 2 (after 6 months validation) |
| **C** | 0.70–0.85 | < 30% | Advisory only — corporate notified, no facility trigger | Phase 3 (after 12 months) |

### 4.3 Facility Lifecycle: End-to-End

```
T-72h   ERP data ingested → Payment Expectation Graph updated
        Node PEG-2028-0742: €1.25M from DEUTDEFF, expected 2028-08-14
        C9 queried → P(delay > 24h) = 0.67 → Grade C → advisory only

T-24h   C9 re-queried with fresh SWIFT gpi data (payment now in transit)
        P(delay > 24h) rises to 0.89 → Grade B → facility recommended
        Reason: corridor EU-APAC experiencing elevated delay rate (C5 stress)

T-18h   Bank auto-approval system evaluates BPI recommendation:
        ✓ Amount ($1.25M) < auto-approve threshold ($2M)
        ✓ Corporate within credit limit
        ✓ Corridor not restricted
        → Facility approved. Status: OFFERED

T-16h   Corporate treasury receives notification (via ERP integration or BPI portal):
        "Pre-emptive facility available: €1.25M at 200 bps utilization"
        Corporate accepts → Status: ACCEPTED

T-12h   C9 re-queried: P(delay > 24h) = 0.91 → Grade A
        Automatic drawdown triggered (corporate pre-authorised auto-draw for Grade A)
        C7 instructs bank/ELO to transfer €1.25M to corporate settlement account
        → Status: DRAWN

T+0     Expected payment date. Two outcomes:

        OUTCOME A — Payment arrives on time:
          C3 detects pacs.002 settlement confirmation
          Facility auto-repaid from settled payment proceeds
          Corporate charged: 18h × (200 bps / 8760h) × €1.25M = €51.37
          Net cost to corporate: €51.37 (vs. $47,945 if they'd used overdraft for 7 days)
          → Status: REPAID

        OUTCOME B — Payment delayed (as predicted):
          Corporate has €1.25M pre-positioned — no cash gap
          C3 continues monitoring UETR
          When payment eventually settles (e.g., T+5d):
            Facility auto-repaid from settled proceeds
            Corporate charged: 5d × (200 bps / 365) × €1.25M = €342.47
            → Status: REPAID

        OUTCOME C — Payment permanently fails:
          Escalates to standard bridge lending workflow (P2)
          Facility converts to term loan at maturity-based pricing
          Corporate repays per standard facility terms
          → Status: CONVERTED_TO_TERM
```

### 4.4 State Machine

```
MONITORING → ELIGIBLE → RECOMMENDED → OFFERED → ACCEPTED → DRAWN → REPAID
                                                    │                  │
                                                    ├→ DECLINED        ├→ CONVERTED_TO_TERM
                                                    ├→ EXPIRED         └→ DEFAULTED
                                                    └→ WITHDRAWN
```

Each transition is logged as an immutable `FacilityDecisionLogEntry` with: facility_id, uetr, corporate_id (hashed), bank_id, amount, trigger_grade, c9_delay_probability, timestamp, decision_type, and HMAC signature.

---

## 5. Part 4 — Revenue Architecture

### 5.1 Fee Structure

| Fee Type | Rate | Charged To | When | BPI Share |
|----------|------|------------|------|-----------|
| **Commitment fee** | 25–75 bps p.a. on facility limit | Corporate | Continuously (daily accrual, quarterly invoice) | Phase 1: 30%, Phase 2: 55%, Phase 3: 80% |
| **Utilization fee** | 150–250 bps annualised on drawn amount | Corporate | On drawdown, prorated to actual hours drawn | Same phase split |
| **BPI intelligence premium** | 10–25 bps (embedded in utilization fee) | Bank (not disclosed to corporate) | On each facility recommendation that converts to drawdown | 100% BPI (technology licensing revenue) |
| **Setup fee** (optional) | $50K–$250K per corporate onboarding | Corporate | One-time | Phase 1: 30%, Phase 2: 55%, Phase 3: 80% |

### 5.2 Revenue Projections (Three Scenarios)

**Assumptions:** Average facility limit $5M per corporate. Average utilization rate 15% (most facilities are precautionary, not drawn). Average drawn duration 3 days. 300 corporates by Year 5.

| Scenario | Corporates | Avg Facility | Utilization | Annual Revenue | BPI Share (Phase 1) |
|----------|-----------|-------------|-------------|---------------|---------------------|
| **Conservative** | 100 | $3M | 10% | $12M | $3.6M |
| **Base** | 300 | $5M | 15% | $45M | $13.5M |
| **Upside** | 500 | $8M | 20% | $120M | $36M |

These figures are incremental to bridge lending (P2) revenue — P4 does not cannibalise P2 because it operates on a different trigger point (pre-failure vs post-failure).

### 5.3 Why Corporates Will Pay

The value proposition is asymmetric: the corporate pays 150–250 bps for hours (not days) of liquidity, versus:
- **Overdraft:** 500+ bps, punitive, damages banking relationship
- **Factoring:** 200–500 bps, involves selling receivables (balance sheet impact)
- **Nothing:** Payment arrives late, corporate misses its own supplier payments, cascade begins (P5 territory)

At 200 bps utilization for 3 days on $1.25M, the corporate pays $205. For this cost, they eliminate the risk of a multi-day cash gap that could cost 10–100× more in operational disruption, missed payments, and supplier relationship damage.

---

## 6. Part 5 — C-Component Engineering Map

### 6.1 C1 — ML Failure Classifier
**Status: NO CHANGE**

C1 classifies payment failure type. P4 does not trigger on failure — it triggers on predicted delay. C1's output is consumed by C9 (the failure class is a feature in the settlement prediction model), but C1 itself is unchanged.

### 6.2 C2 — PD Pricing Engine
**Status: EXTEND — Facility Pricing (~2–3 weeks)**

C2 currently computes bridge loan pricing (PD → fee bps). P4 requires C2 to also compute facility pricing, which has two components:

1. **Commitment fee:** Function of corporate credit quality and facility limit. Uses the same PD framework but with a different fee schedule (25–75 bps vs 300+ bps for bridge lending) because the expected loss is lower (facility may never be drawn).

2. **Utilization fee:** Function of delay probability, drawn amount, and expected draw duration. Higher delay probability → lower expected loss (the prediction was right, the payment will arrive, the draw is short-term) → lower utilization fee. This is counter-intuitive but correct: a highly confident prediction is LESS risky for the bank, not more.

**New method in C2:**
```python
def compute_facility_pricing(
    self,
    corporate_pd: float,          # Corporate credit quality (from external rating or internal model)
    facility_limit_usd: Decimal,   # Total facility size
    delay_probability: float,      # From C9 hazard model
    expected_draw_hours: float,    # From C9 settlement prediction
    deployment_phase: str,         # LICENSOR | HYBRID | FULL_MLO
) -> FacilityPricing:
    """
    Compute commitment + utilization fee for a pre-emptive facility.
    QUANT sign-off required before deployment.
    """
```

### 6.3 C3 — Settlement Monitor
**Status: EXTEND — Facility Settlement Trigger (~2 weeks)**

C3 currently monitors UETR and triggers auto-repayment for bridge loans. P4 extends C3 to also trigger auto-repayment for facility drawdowns.

**C3 Extension: Facility Auto-Repayment**

When C3 detects pacs.002 settlement for a UETR that is associated with a drawn facility:
1. Calculate actual drawn duration (settlement_time - drawdown_time)
2. Compute final utilization fee based on actual duration (not predicted duration)
3. Instruct bank/ELO to repay facility from settled payment proceeds
4. Update facility status: DRAWN → REPAID
5. Emit settlement event to C8 for revenue metering

This is architecturally identical to the existing bridge loan auto-repayment — the only difference is the fee calculation method and the state machine transitions.

### 6.4 C6 — AML / Security
**Status: MINOR — Facility Velocity Monitoring (~1 week)**

New monitoring rule to prevent facility abuse — a scenario where a corporate draws facilities on payments it knows will arrive on time, using the facility as a free short-term loan:

```
IF corporate draws facility
   AND payment settles within 2 hours of drawdown
   AND this pattern occurs 3+ times in 30 days
THEN flag for compliance review (potential facility gaming)
```

### 6.5 C7 — Bank Integration Layer
**Status: EXTEND — Highest Engineering Effort (~6–8 weeks)**

**C7 Extension 1: Facility API (~4–5 weeks)**

Four new endpoints for facility lifecycle management:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/facility/recommend` | BPI recommends facility to bank based on C9 prediction |
| `POST` | `/api/v1/facility/{id}/offer` | Bank offers facility to corporate |
| `POST` | `/api/v1/facility/{id}/accept` | Corporate accepts facility |
| `POST` | `/api/v1/facility/{id}/draw` | Drawdown triggered (auto or manual) |
| `POST` | `/api/v1/facility/{id}/repay` | Settlement-triggered repayment |
| `GET` | `/api/v1/facility/{id}` | Facility status query |
| `GET` | `/api/v1/facility/portfolio` | All active facilities for corporate/bank |

**Recommendation Payload (BPI → Bank):**
```json
{
  "recommendation_id": "REC-20280814-0001",
  "corporate_id": "hashed:abc123",
  "payment": {
    "uetr": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "source_bic": "DEUTDEFF",
    "amount_usd": 1250000.00,
    "expected_date": "2028-08-14",
    "corridor": "EU-APAC"
  },
  "prediction": {
    "delay_probability": 0.89,
    "trigger_grade": "B",
    "predicted_settlement_hours": 42.3,
    "confidence_interval": {"lower": 0.79, "upper": 0.93},
    "model_version": "cox_ph_v2.1"
  },
  "facility_recommendation": {
    "recommended_amount_usd": 1250000.00,
    "commitment_fee_bps": 50,
    "utilization_fee_bps": 200,
    "auto_draw_eligible": true,
    "recommended_draw_trigger": "GRADE_A_CONFIRMED"
  },
  "timestamp": "2028-08-13T06:00:00Z"
}
```

**C7 Extension 2: ERP Connector Interface (~2–3 weeks)**

Abstract base class for ERP integration:

```python
class ERPConnector(ABC):
    """Abstract base for corporate ERP integration.
    Implementations: SAPConnector, OracleConnector, KyribaConnector.
    Stubs in P4 v0; real implementations in Phase 2.
    """

    @abstractmethod
    def get_expected_receivables(
        self,
        corporate_id: str,
        horizon_days: int = 30,
    ) -> List[ExpectedPayment]: ...

    @abstractmethod
    def notify_facility_status(
        self,
        corporate_id: str,
        facility_id: str,
        status: str,
    ) -> bool: ...
```

**ERP Integration Targets (Phase 2):**
- **Kyriba:** Natural hub — connects 10,000+ ERP instances (SAP, Oracle, D365). API-first. Bank of America CashPro API partnership (51% increase in API-using clients, 2024).
- **SAP S/4HANA:** Treasury module exposes receivables via OData/REST. 440,000+ customers globally.
- **Oracle Cloud ERP:** Cash Management module with REST API. Growing in mid-market.

### 6.6 C8 — Licensing & Metering
**Status: EXTEND — Facility Fee Accrual (~2–3 weeks)**

**C8 Extension 1: Commitment Fee Accrual**
Daily accrual of commitment fee on facility limit:
```
daily_commitment_fee = (facility_limit × commitment_fee_bps / 10000) / 365
```
Accrued daily, invoiced quarterly. C8 maintains running total per corporate.

**C8 Extension 2: Utilization Fee Metering**
Per-drawdown fee based on actual drawn duration:
```
utilization_fee = (drawn_amount × utilization_fee_bps / 10000) × (drawn_hours / 8760)
```
Computed at repayment (when actual duration is known). Metered to BPI for revenue recognition.

**C8 Extension 3: Intelligence Premium Tracking**
BPI's intelligence premium (10–25 bps) is tracked separately from the bank's facility fees. This creates a clean revenue line for BPI's technology licensing business, separate from the lending economics.

### 6.7 C9 — Settlement Predictor
**Status: EXTEND — Hazard Rate API (~3–4 weeks)**

**C9 Extension 1: Hazard Rate Extraction (~2 weeks)**
New `predict_delay_hazard()` method extracts P(delay > threshold) from the existing Cox PH survival function. No retraining — pure mathematical transformation of existing model output.

**C9 Extension 2: Confidence Gating (~1 week)**
Only generate facility recommendations when the prediction confidence interval width is below the grade threshold. This prevents facilities being triggered on low-confidence predictions.

**C9 Extension 3: Continuous Re-scoring (~1 week)**
As new SWIFT gpi tracking data arrives (every few minutes), re-score all active Payment Expectation Graph nodes. If a payment's delay probability crosses a trigger grade boundary, emit an event to the Facility Lifecycle Manager.

---

## 7. Part 6 — ERP Integration Architecture

### 7.1 Data Flow

```
SAP S/4HANA / Oracle / Kyriba (Corporate ERP)
    │
    │ REST API (batch daily + incremental 4-hourly)
    │ Fields: invoice_id, counterparty, amount, currency, expected_date, payment_terms
    │
    v
PAYMENT EXPECTATION GRAPH (new BPI module)
    │
    │ C9 enrichment: for each expected payment, query settlement prediction
    │
    v
HAZARD MODEL (C9 extension)
    │
    │ P(delay > threshold) per payment
    │ Trigger grade assignment (A/B/C)
    │
    v
FACILITY LIFECYCLE MANAGER (new BPI module)
    │
    │ Grade A/B → facility recommendation to bank
    │ Grade C → advisory to corporate
    │
    v
BANK / ELO (C7)
    │
    │ Auto-approve or manual review
    │ Facility offer → corporate accept → drawdown
    │
    v
C3 SETTLEMENT MONITOR
    │
    │ UETR tracking → pacs.002 settlement → auto-repayment
    │
    v
C8 REVENUE METERING
    │
    │ Commitment fee accrual + utilization fee + intelligence premium
```

### 7.2 Privacy Architecture

Corporate ERP data is sensitive. P4's privacy model:

| Data | Treatment |
|------|-----------|
| Corporate identity | Hashed (`lip/common/encryption.py` — SHA-256 + rotating salt) |
| Invoice IDs | Hashed before storage in BPI systems |
| Payment amounts | Stored encrypted at rest (AES-256-GCM) |
| Counterparty BICs | Used for C9 prediction features; not stored beyond prediction lifecycle |
| ERP data retention | 90 days maximum; auto-purged after facility lifecycle completes |

CIPHER review required before any corporate ERP data enters BPI systems.

---

## 8. Part 7 — Consolidated Engineering Timeline

### 8.1 Build Plan: Q1–Q3 2028

| Sprint | Weeks | Components | Deliverable | Owner |
|--------|-------|------------|-------------|-------|
| Sprint 1 | W1–W3 | C9 Extensions 1–2 | Hazard rate API + confidence gating. No retraining. | Backend Eng 1 |
| Sprint 2 | W4–W5 | C9 Extension 3 + Facility State Machine | Continuous re-scoring + state machine (MONITORING → REPAID) | Backend Eng 1 |
| Sprint 3 | W6–W10 | Payment Expectation Graph | New module: graph construction, ERP connector interface, scoring engine | Backend Eng 2 |
| Sprint 4 | W11–W13 | C2 Extension | Facility pricing: commitment + utilization fee computation. QUANT sign-off gate. | Backend Eng 1 |
| Sprint 5 | W14–W19 | C7 Extensions 1–2 | Facility API (recommend/offer/accept/draw/repay) + ERP connector stubs | Backend Eng 1 + 2 |
| Sprint 6 | W20–W22 | C3 Extension + C6 Minor | Facility auto-repayment trigger + facility velocity monitoring | Backend Eng 2 |
| Sprint 7 | W23–W25 | C8 Extensions 1–3 | Commitment accrual, utilization metering, intelligence premium tracking | Backend Eng 1 |
| Sprint 8 | W26–W28 | Integration test | End-to-end: ERP → graph → C9 → recommend → offer → draw → settle → repay → meter | Both |

Total: ~22–28 engineer-weeks, 2 senior engineers.
Calendar time: ~7 months.

### 8.2 Parallel Validation Track

**Critical dependency: 12 months of C9 production data.**

P4 cannot go live until C9 has been running in production (on actual bridge lending payments, via P2) for at least 12 months. This production data is needed to:
1. Validate C9 prediction accuracy on real payment settlement times (not synthetic data)
2. Calibrate trigger grade thresholds (A/B/C boundaries) on observed hit rates
3. Build the survival curve for new corridors not in the training data
4. Compute confidence intervals from production residuals

**Shadow Run (6 months before live):**
- C9 hazard predictions computed for all incoming payments
- Facility recommendations generated but NOT executed
- After-the-fact comparison: did the prediction match actual settlement time?
- Threshold calibration: adjust Grade A/B/C boundaries to achieve target false positive rates

### 8.3 Parallel Legal Track

| Milestone | Owner | Timeline |
|-----------|-------|----------|
| Basel counsel opinion on "uncommitted" classification | BPI legal + external counsel | W1–W4 |
| Draft Facility Master Agreement template | BPI legal + bank counsel | W4–W8 |
| Draft ERP Data Sharing Consent template | BPI legal + privacy counsel | W6–W10 |
| Draft BPI Predictive Intelligence Addendum | BPI legal + patent counsel | W8–W12 |
| Corporate pilot agreement (1–3 corporates via existing bank partner) | BPI commercial + bank partner | W20–W24 |
| Shadow run with pilot corporates | All tracks | W24–W28 |
| Live pilot: 1–3 corporates, one corridor, €5–10M facility cap | All tracks | W28+ |

---

## 9. Part 8 — What Stays in the Long-Horizon P4 Patent

| Feature | Why Not in 2028 | Target |
|---------|----------------|--------|
| **DeepSurv neural survival model** (replaces Cox PH) | Requires 100K+ settlement observations for training; Cox PH works with 10K+ | 2030–2031 |
| **Portfolio-level gap distribution** (multiple corporates optimised simultaneously) | Patent Claim 4 covers this explicitly; requires 50+ corporate deployments | 2029–2031 |
| **Automatic facility drawdown without bank approval** (committed facility) | Basel III 40% CCF makes committed facilities uneconomical at current scale | When BPI transitions to Phase 3 (own balance sheet) |
| **Cross-corporate netting** (Corporate A's surplus covers Corporate B's gap) | Legal complexity; requires multi-corporate credit agreement | 2030+ |
| **Real-time ERP integration** (minute-level, not 4-hourly) | ERP APIs not designed for real-time push; requires webhook infrastructure at corporate | Phase 2 (after pilot validates value) |

---

## 10. Part 9 — Risk Register (P4 v0 Specific)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **C9 prediction accuracy insufficient** — model predicts delays that don't materialise (false positives) or misses delays that do (false negatives) | Medium | Critical | Confidence gating: start with Grade A only (P > 0.95). 6-month shadow run before live. False positive tolerance: <10% at Grade A. Continuous recalibration from production data. |
| **Corporate ERP data too unreliable** — expected receivables don't match actual payments | High | High | Confidence scoring per ERP source. Fallback: use only BPI-observed payment patterns (no ERP), accept lower coverage but higher accuracy. Phase 1 targets corporates with mature ERP (SAP S/4HANA). |
| **Basel III reclassification** — regulator rules BPI's auto-trigger makes facility "committed" (40% CCF) | Medium | High | Bank retains absolute override right. Legal opinion from Basel counsel before launch. Structure as "recommendation" not "instruction". If reclassified: utilization fee must increase to cover bank's higher capital charge (~20–30 bps additional). |
| **Corporate gaming** — treasury draws facility on payments they know will arrive on time (free short-term loan) | Medium | Medium | C6 velocity monitoring: flag corporates who draw and get repaid within 2 hours, 3+ times in 30 days. Commitment fee ensures BPI/bank earn revenue even on undrawn facilities. |
| **DeepSurv paper retraction or methodology challenge** | Low | Low | Cox PH is established methodology (Cox, 1972; 50+ years of validation). DeepSurv is optional upgrade, not dependency. C9 heuristic fallback (BIS/SWIFT gpi calibrated medians) always available. |
| **ERP vendor changes API or deprecates endpoint** | Medium | Medium | Abstract ERPConnector base class means BPI only needs to update one implementation per vendor. Kyriba partnership provides stable API commitment. Phase 1 uses BPI-observed data as primary source. |
| **Corporate defaults on facility** — payment permanently fails AND corporate cannot repay | Low | High | Same credit risk management as P2 bridge lending. Bank retains credit decision authority. Corporate's credit limit governs total facility exposure. Facility converts to term loan (CONVERTED_TO_TERM state). |
| **Liability claim** — corporate claims BPI prediction was wrong and caused them to over-rely on facility | Low | Critical | Liability limitation in Facility Master Agreement: BPI provides predictive intelligence only, not credit advice. Bank makes all credit decisions. Corporate retains operational responsibility. Legal opinion required on fiduciary duty scope. |
| **Competitor replicates** — bank builds internal prediction model | Medium | Medium | P4 patent claims the Payment Expectation Graph + hazard model + auto-drawdown mechanism as individually protectable elements. Bank's internal R&D timeline: 3–5 years. P4 patent filed Year 3 from provisional — predates any bank programme. Data moat: BPI's cross-bank settlement data (from multiple deployments) is more predictive than any single bank's internal data. |
| **Cannibalisation of P2 bridge lending** — P4 prevents failures that would have generated bridge lending revenue | Low | Medium | P4 and P2 trigger at different lifecycle points. P4 pre-positions liquidity; P2 bridges after failure. If P4 prevents a failure, the bridge loan was never needed — this is a BETTER outcome for the corporate and the bank. Revenue shift from utilization-heavy (P2) to commitment-heavy (P4) is actually more predictable and higher-margin. |

---

End of Document

---

Bridgepoint Intelligence Inc.
Internal Use Only — Strictly Confidential — Attorney-Client Privileged
Document ID: P4-v0-Implementation-Blueprint-v1.0.md
Date: March 27, 2026
Supersedes: N/A (first version)
Next review: Upon completion of Sprint 3 (Payment Expectation Graph) or upon receipt of Basel counsel opinion on facility classification
