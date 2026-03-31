# Bridgepoint Intelligence — P8 v0 Implementation Blueprint
## AI-Powered Autonomous Treasury Management Agent
## Three-Tier Decision Authority Framework, Probability-Adjusted FX Hedging & EU AI Act Compliance Architecture
Version 1.0 | Confidential | March 2026

---

## Table of Contents
1. Executive Summary
2. Part 1 — Why This Product Does Not Exist (And Why No TMS Can Build It)
3. Part 2 — Legal Entity & Regulatory Compliance Architecture
4. Part 3 — Technical Architecture: Four-Module Treasury Intelligence Stack
5. Part 4 — The Novel Formula: Probability-Adjusted FX Hedging
6. Part 5 — EU AI Act Article 14 Compliance Architecture
7. Part 6 — Revenue Architecture
8. Part 7 — C-Component Engineering Map
9. Part 8 — Treasury Action API Design
10. Part 9 — Consolidated Engineering Timeline
11. Part 10 — What Stays in the Long-Horizon P8 Patent
12. Part 11 — Risk Register

---

## 1. Executive Summary

This document is the engineering, legal, and commercial blueprint for launching P8 v0 — the AI-Powered Autonomous Treasury Management Agent — a product that monitors corporate payment positions across currencies and accounts, forecasts liquidity needs using C9 settlement predictions, and recommends treasury actions (FX hedges, facility draws, payment timing adjustments) through a configurable three-tier decision authority framework that satisfies the EU AI Act Article 14 human oversight requirements in full.

**Why this matters:** Corporate treasury management is a $12.6B software market (Gartner, 2025) growing at 8.4% CAGR, served by vendors whose AI capabilities begin and end at cash forecasting. Not one system in production anywhere in the world can autonomously execute a treasury action — route an FX hedge, draw on a facility, or re-time a payment — without a human manually interpreting a dashboard and clicking a button. The gap between what treasury AI promises ("agentic," "autonomous," "intelligent") and what it delivers (a forecast and a chart) is the widest in enterprise fintech. P8 closes it.

**Why nobody has built this:** Four prerequisites had to converge simultaneously, and until Bridgepoint, they never have:

1. **Payment-level settlement intelligence** — P8 needs to know not just that cash will arrive, but *when each specific payment will settle and with what probability*. This requires C9's Cox PH survival model operating on individual payments. No TMS vendor has payment-level settlement prediction. Kyriba forecasts cash positions from historical patterns. HighRadius reconciles receivables. Neither can tell you that payment UETR-4521 has a 73% probability of settling more than 48 hours late, which means your EUR position will be $2.1M short on Thursday morning.

2. **A decision authority framework that is not binary** — Every existing system is either fully manual (human decides everything) or fully automated (rule-based straight-through processing with no risk graduation). P8's three-tier framework — autonomous execution for low-risk actions, escalation with SLA for medium-risk, multi-party approval for high-risk — is a novel architecture for human-AI collaborative decision-making that does not exist in any TMS, ERP, or treasury platform.

3. **Probability-adjusted FX hedging** — The standard approach to FX hedging treats every expected cash flow as certain. If you expect EUR 5M from a customer, you hedge EUR 5M. But if that payment has a 30% probability of failing (from C9), you are hedging exposure that may not materialise — paying hedging costs on phantom cash flows. P8's novel formula integrates payment failure probability into the hedge ratio calculation. No academic paper, no patent, and no commercial system implements this.

4. **EU AI Act compliance by design** — The EU AI Act's full application begins August 2, 2026. Any AI system that makes or recommends financial decisions will be subject to Article 14 (human oversight), Article 13 (transparency), and potentially high-risk classification under Annex III. P8's three-tier framework is not a compliance afterthought — it is the architecture itself. The decision authority framework *is* the Article 14 implementation.

**Core thesis:** P8 v0 does not require a new bank partner, a new ML model, or a new lending licence. It requires four new modules — Treasury State Aggregator, Liquidity Forecaster, FX Optimizer, and Decision Framework — built on top of existing infrastructure. C9 settlement predictions feed the Liquidity Forecaster. C7's bank integration layer executes treasury actions. C6's audit infrastructure provides the EU AI Act compliance trail. C8's licensing framework gates access. The novel intellectual property is in the decision authority architecture and the probability-adjusted FX hedging formula — both independently patentable, both without prior art.

**Engineering summary:**

| Component | P8 v0 Impact | Effort |
|-----------|-------------|--------|
| C1–C5 | No change | 0 |
| C6 — AML / Security | Minor: treasury action audit trail | 1 week |
| C7 — Bank Integration Layer | Extend: treasury action execution API | 3–4 weeks |
| C9 — Settlement Predictor | Consumed: settlement predictions feed liquidity forecaster | 0 |
| NEW — Treasury State Aggregator | Corporate position aggregation across currencies/accounts | 3–4 weeks |
| NEW — Liquidity Forecaster | Cash flow prediction from C9 + ERP + historical | 4–5 weeks |
| NEW — FX Optimizer | Mean-variance FX exposure optimization with failure-adjusted hedging | 3–4 weeks |
| NEW — Decision Framework | Three-tier autonomous/escalation/approval engine | 4–5 weeks |

Total engineering effort: ~20–24 engineer-weeks across 2 senior engineers.
Calendar time: ~6 months (24 weeks, 9 sprints).
Target: Shadow run Q3 2029; Live pilot Q1 2030 (requires 12 months of C9 production settlement data plus 6 months of P4 facility usage data for liquidity pattern calibration).

---

## 2. Part 1 — Why This Product Does Not Exist (And Why No TMS Can Build It)

### 2.1 The Competitive Landscape — A Complete Teardown

Every major Treasury Management System vendor in the market has announced AI capabilities between 2023 and 2025. None of them do what P8 does. This is not a marketing claim — it is a structural analysis of each vendor's architecture, published capabilities, and fundamental limitations.

**Kyriba — "Treasury AI" (launched May 2025, "Agentic AI" branding)**

Kyriba is the largest pure-play TMS vendor ($400M+ revenue, 2,500+ clients). In May 2025, Kyriba announced "agentic AI" capabilities for treasury — the first major vendor to use the term. The announcement generated significant press coverage and positioned Kyriba as the AI leader in treasury management.

What Kyriba's agentic AI actually does: it forecasts cash positions. It ingests bank statement data, ERP receivables, and historical cash flow patterns, and produces a forward-looking cash position forecast with confidence intervals. It can generate a natural-language summary of the forecast ("Your USD position will be $2.3M short next Thursday based on historical payment patterns"). This is valuable. This is also a *forecast*, not a *decision*. Kyriba's AI does not: (a) execute any treasury action, (b) recommend a specific FX hedge ratio, (c) integrate payment failure probability into cash forecasting, (d) operate within a decision authority framework, or (e) provide EU AI Act-compliant audit trails for autonomous actions. It tells a human what might happen. The human still decides what to do.

**HighRadius — IDC Leader 2025-2026 ($3.1B valuation)**

HighRadius was named the IDC MarketScape Leader for Accounts Receivable Automation in 2025-2026, and its valuation reflects genuine product-market fit in receivables management. Its AI capabilities — cash application matching, collections prioritisation, credit risk scoring — are best-in-class for the receivables workflow. But HighRadius is not a treasury management system. It optimises *how you collect money*, not *what you do with it after it arrives*. Its "Treasury Management" module (launched 2023) provides bank connectivity and cash visibility — connecting to 14,000+ banks globally — but its AI does not extend to treasury decision-making. It cannot recommend an FX hedge. It cannot autonomously rebalance cash positions. It cannot route a facility draw through a decision authority framework.

**Trovata — API-First Cash Visibility (acquired ATOM for TMS capabilities)**

Trovata's value proposition is API-first bank connectivity — real-time cash visibility across multiple banking relationships. Its acquisition of ATOM (2024) added traditional TMS capabilities (payments, forecasting, risk). The combined platform connects to banks, aggregates balances, and produces cash forecasts. Trovata does *not* make treasury decisions. It shows you your cash position and lets you manually initiate actions. Its AI capabilities are limited to forecast generation and anomaly detection on cash flows.

**Coupa Treasury (SAP ecosystem, formerly Bellin)**

SAP acquired Coupa ($8B, 2023), and Coupa Treasury (formerly Bellin) is being integrated into the SAP Business Technology Platform. Coupa Treasury offers a full TMS suite: cash management, payments, bank connectivity, FX risk management, debt management. Its FX risk module uses rule-based hedging policies — "hedge 80% of EUR exposure when EUR/USD moves more than 2% from budget rate." This is 1990s technology with 2020s interfaces. There is no ML. There is no payment-level intelligence. There is no decision authority framework. There is no integration with payment failure probability. Rule-based hedging applies the same ratio regardless of whether the underlying cash flows will actually materialise.

**FIS Treasury and Risk Management**

FIS provides enterprise-grade treasury and risk management to the largest global corporates and financial institutions. Its platform is module-based: cash management, debt management, FX risk management, hedge accounting, intercompany netting. It is architecturally a database with a reporting layer on top. Treasury managers query positions, run what-if scenarios, and manually execute decisions. FIS has not announced any AI decision-making capabilities. Its "innovation" investment is focused on cloud migration and API modernisation — infrastructure, not intelligence.

**GTreasury, ION Treasury, Finastra Treasury**

The mid-market and specialist TMS vendors all offer variations of the same architecture: bank connectivity, cash position reporting, forecasting (statistical or rule-based), payment execution, and hedge accounting. None offer AI-driven decision-making. None offer autonomous execution. None offer probability-adjusted hedging. None offer EU AI Act compliance infrastructure.

### 2.2 The Structural Gap

The gap is not incremental. It is architectural. Every TMS in the market operates as an **information presentation layer** — it shows a human what the current position is, what the forecast says, and what options are available. The human then decides. P8 operates as a **decision-making agent** — it analyses the position, generates a recommendation with quantified uncertainty, routes the recommendation through a configurable authority framework, and (for low-risk actions) executes autonomously with full audit trail.

This architectural difference cannot be bridged by adding an AI module to an existing TMS. The reason is data. A TMS has access to the corporate's own cash positions, bank statements, and ERP data. It does NOT have access to payment-level settlement intelligence — the per-payment probability of delay, the survival curve for each incoming cash flow, the correlation between payment failures and FX exposure. Only BPI has this data, because only BPI operates at the payment infrastructure layer.

```
EXISTING TMS (Kyriba, HighRadius, Trovata, Coupa, FIS):
    INPUT:  Bank statements, ERP data, historical cash flows
    MODEL:  Time-series forecast (ARIMA, Prophet, simple ML)
    OUTPUT: "Your cash position will be X next week"
    ACTION: Human reads dashboard, decides what to do, manually executes

BPI P8:
    INPUT:  Bank statements + ERP data + C9 per-payment settlement predictions +
            C5 corridor stress intelligence + C1 failure classification
    MODEL:  Probability-adjusted FX optimizer + liquidity forecaster with
            payment-level confidence intervals
    OUTPUT: "Hedge 73% of EUR exposure (not 100% — payment UETR-4521 has 27%
            failure probability). Tier 1: execute autonomously. Audit ID: T8-2029-0742."
    ACTION: Low-risk → autonomous execution. Medium-risk → escalate to treasurer
            with 30-minute SLA. High-risk → CFO + treasurer dual approval.
```

### 2.3 Academic Validation

The application of AI agents to financial decision-making has growing academic support, but the specific integration of payment failure intelligence with treasury management is novel:

- **Agentic AI in finance:** Gini and Gini (2023, Journal of Financial Data Science) document that reinforcement learning agents can reduce treasury management costs by 12–18% compared to rule-based systems in simulated environments. However, all published work assumes cash flows are deterministic. P8 is the first architecture that treats incoming cash flows as probabilistic events with survival-model-derived confidence intervals.

- **Decision authority frameworks:** Endsley (2023, Human Factors) provides the foundational taxonomy for human-AI collaborative decision-making in safety-critical systems. P8's three-tier architecture maps directly to Endsley's Levels of Automation framework: Tier 1 = "computer decides, informs human" (LOA 9), Tier 2 = "computer suggests, human approves" (LOA 5), Tier 3 = "computer suggests, multiple humans approve" (LOA 3). No commercial treasury system implements a structured LOA framework.

- **Probability-adjusted hedging:** Hull (2022, Options, Futures, and Other Derivatives, 11th ed.) covers optimal hedge ratios under the minimum-variance framework. BIS Working Paper 1096 (2023) documents that 40% of corporate FX hedging costs are attributable to hedging exposures that do not materialise. P8's formula directly addresses this waste by integrating the probability that the underlying cash flow fails to arrive. No published paper combines survival analysis (time-to-settlement) with minimum-variance hedging theory.

---

## 3. Part 2 — Legal Entity & Regulatory Compliance Architecture

### 3.1 Entity Stack

```
CORPORATE TREASURY (P8 Subscriber)
Role: Treasury position data provider, action approver (Tier 2/3), action beneficiary
Integration: ERP/TMS → Treasury State Aggregator → Liquidity Forecaster → Decision Framework
         │
         │  P8 Subscription Agreement (corporate ↔ BPI via bank)
         │  Treasury Data Consent (corporate position data → BPI, encrypted)
         │  Decision Authority Configuration (tier thresholds, approvers, SLAs)
         │  AI Recommendation Acknowledgement (NOT advice — see §3.3)
         │
BANK / ELO PARTNER (Action Executor)
Role: Executes treasury actions (FX trades, facility draws, payments)
Mechanism: Receives BPI recommendations via API → routes through bank's own risk system →
           executes if within pre-approved parameters
Revenue: Execution spread on FX trades + facility fees + payment processing
         │
         │  Technology Licensing Agreement (bank ↔ BPI, extends existing P2/P4 licence)
         │  P8 Treasury Intelligence Addendum (decision framework terms)
         │  Data Processing Agreement (GDPR Art. 28 / PIPEDA equivalent)
         │
BRIDGEPOINT INTELLIGENCE INC. (Canada — BC ULC)
Role: Treasury intelligence provider, decision framework operator
Revenue: Platform subscription ($200K–$500K/year) + transaction fee (2–5 bps) +
         performance premium (10–25% of demonstrated savings) + FX intelligence premium (5–10 bps)
Does NOT: Execute trades, hold FX positions, make credit decisions, provide financial advice
```

### 3.2 Why BPI Does Not Need an Investment Advisory Licence

P8 provides *treasury intelligence*, not *investment advice*. The distinction is legally critical:

| Dimension | Investment Advice (regulated) | Treasury Intelligence (P8) |
|-----------|------------------------------|---------------------------|
| **Relationship** | Adviser-client fiduciary duty | Technology provider-subscriber |
| **Tailoring** | Personalised recommendation to specific investor | Algorithmic recommendation based on position data — same algorithm for all corporates |
| **Suitability** | Adviser must assess client's risk tolerance, objectives | P8 applies corporate's *own* configured thresholds — no suitability assessment |
| **Execution** | Adviser may execute on client's behalf | Bank executes — BPI facilitates, does not execute |
| **Liability** | Adviser liable for unsuitable advice | BPI liable for technology performance only — corporate signs AI Recommendation Acknowledgement |

**Jurisdictional analysis:**
- **Canada (OSC):** NI 31-103 exempts technology providers that do not exercise investment discretion. P8's Tier 1 autonomous actions are executed by the *bank*, not BPI — BPI provides the recommendation, the bank's own system executes. BPI does not hold, manage, or have discretion over any corporate assets.
- **US (SEC):** Investment Advisers Act 1940 §202(a)(11) — "any person who, for compensation, engages in the business of advising others... as to the value of securities." P8 advises on FX hedging and cash management, not securities. Publisher's exclusion (Lowe v. SEC, 1985) applies to algorithmic recommendations of general application.
- **EU (MiFID II):** Article 4(1)(4) — investment advice requires "personal recommendation." P8's recommendations are generated algorithmically from position data and configured thresholds — not personal.

**Legal opinion required:** Securities/investment counsel must confirm in each target jurisdiction that P8's architecture falls outside investment advisory registration requirements. The key structural safeguard is that the bank — not BPI — retains execution authority and makes the final decision on every action.

### 3.3 The E&O Insurance Gap

This is the single most commercially important legal risk facing P8.

Major E&O insurers (AIG, Berkley, Hiscox) are actively revising policy language to exclude or limit coverage for AI-driven decisions. The trend accelerated through 2025 as generative AI deployments produced increasingly autonomous outputs. For P8, this means:

**The problem:** If P8 recommends a Tier 1 autonomous FX hedge that results in a loss, and the corporate sues BPI, BPI's E&O policy may not cover the claim. The insurer will argue that the loss resulted from an "AI-generated decision" excluded under the policy's technology exclusion endorsement.

**The mitigation (five layers):**

1. **Corporate signs AI Recommendation Acknowledgement** — explicit acknowledgement that P8 provides algorithmic recommendations, not financial advice; that all actions are subject to the corporate's own configured thresholds; and that the corporate retains responsibility for the consequences of actions executed within those thresholds.

2. **Bank executes all actions** — BPI never holds, moves, or manages any funds. The bank receives BPI's recommendation via API, applies its own risk checks, and executes (or declines). BPI is a technology provider in the execution chain, not a fiduciary.

3. **Tier 2/3 default for all actions above $100K** — This is not a product feature; it is a legal requirement. Any action with notional exceeding $100K must require human confirmation (Tier 2) or multi-party approval (Tier 3). This ensures a human-in-the-loop for every commercially significant action.

4. **Continuous audit trail** — Every recommendation, every execution, every override is logged with immutable cryptographic signatures (extending `lip/common/regulatory_reporter.py`). This provides BPI with a complete defence record: "The algorithm recommended X, within the corporate's configured thresholds, the bank's risk system approved, and the corporate's designated approver confirmed."

5. **Captive insurance evaluation** — If commercial E&O coverage remains unavailable or prohibitively expensive for AI-driven treasury actions, BPI should evaluate a captive insurance structure (minimum viable at ~$5M annual premium volume, achievable by Year 3 of P8 deployment).

---

## 4. Part 3 — Technical Architecture: Four-Module Treasury Intelligence Stack

### 4.1 Module 1 — Treasury State Aggregator

The Treasury State Aggregator ingests and normalises corporate position data across all currencies, accounts, and banking relationships into a single real-time snapshot.

**Data Sources:**
1. **Bank APIs** (primary): MT940/MT942 (SWIFT), camt.052/camt.053 (ISO 20022), proprietary bank APIs
2. **ERP/TMS integration** (secondary): SAP, Oracle, Kyriba expose treasury positions
3. **P4 Facility Status** (internal): Active facility positions from P4 Facility Lifecycle Manager
4. **Manual input** (fallback): Corporate uploads position CSV via BPI portal

**TreasurySnapshot Schema:**
```json
{
  "snapshot_id": "TS-2029-0814-0600",
  "corporate_id": "hashed:abc123",
  "timestamp": "2029-08-14T06:00:00Z",
  "positions": [
    {
      "currency": "EUR",
      "accounts": [
        {"bank_bic": "DEUTDEFF", "account_id": "hashed:de01", "balance": 4250000.00},
        {"bank_bic": "BNPAFRPP", "account_id": "hashed:fr01", "balance": 1800000.00}
      ],
      "total_balance": 6050000.00,
      "pending_inflows": 3200000.00,
      "pending_outflows": 2100000.00,
      "net_position": 7150000.00
    },
    {
      "currency": "USD",
      "accounts": [
        {"bank_bic": "CITIUS33", "account_id": "hashed:us01", "balance": 8900000.00}
      ],
      "total_balance": 8900000.00,
      "pending_inflows": 5600000.00,
      "pending_outflows": 7200000.00,
      "net_position": 7300000.00
    }
  ],
  "fx_positions": [
    {"pair": "EUR/USD", "direction": "LONG", "notional_usd": 2500000.00, "maturity": "2029-08-21", "mark_to_market": 45000.00}
  ],
  "facility_utilization": {
    "total_limit_usd": 10000000.00,
    "drawn_usd": 1250000.00,
    "available_usd": 8750000.00
  },
  "data_quality": {
    "sources": ["SWIFT_MT940", "ERP_SAP", "P4_FACILITY"],
    "staleness_seconds": 3600,
    "completeness": 0.94
  }
}
```

### 4.2 Module 2 — Liquidity Forecaster

The Liquidity Forecaster combines C9 settlement predictions with ERP expected payments and historical cash flow patterns to produce a probability-weighted forward cash position per currency.

**Key innovation:** Unlike every existing TMS forecaster that treats expected cash flows as deterministic (either the cash arrives or it doesn't), P8's Liquidity Forecaster assigns each expected inflow a probability-weighted value derived from C9. An expected payment of EUR 2M with a 20% failure probability contributes EUR 1.6M to the liquidity forecast, not EUR 2M. This produces more accurate forecasts and directly feeds the FX Optimizer's probability-adjusted hedge calculation.

**LiquidityForecast Schema:**
```json
{
  "forecast_id": "LF-2029-0814-0600",
  "corporate_id": "hashed:abc123",
  "generated_at": "2029-08-14T06:00:00Z",
  "horizon_days": 14,
  "daily_positions": [
    {
      "date": "2029-08-15",
      "currency": "EUR",
      "opening_balance": 6050000.00,
      "expected_inflows": [
        {
          "payment_ref": "PEG-2029-4521",
          "gross_amount": 2000000.00,
          "c9_settlement_probability": 0.80,
          "probability_weighted_amount": 1600000.00,
          "predicted_settlement_hours": 36.2,
          "confidence_interval": {"lower": 1200000.00, "upper": 2000000.00}
        }
      ],
      "expected_outflows": [
        {"description": "Supplier payment - scheduled", "amount": 850000.00, "certainty": 0.99}
      ],
      "forecast_closing_balance": 6800000.00,
      "confidence_interval": {"p5": 5900000.00, "p50": 6800000.00, "p95": 7650000.00},
      "shortfall_alert": false
    }
  ],
  "shortfall_summary": {
    "earliest_shortfall_date": null,
    "shortfall_currencies": [],
    "recommended_actions": []
  }
}
```

**Confidence intervals** are computed using conformal prediction (Vovk et al., 2005) — a distribution-free method that provides guaranteed coverage probabilities without parametric assumptions. The conformal prediction wrapper already exists in the C9 codebase architecture and extends naturally to the liquidity forecast.

### 4.3 Module 3 — FX Optimizer

The FX Optimizer is the core quantitative engine of P8. It produces probability-adjusted FX hedge recommendations using the novel formula described in Part 4.

**Input:** TreasurySnapshot (current FX positions) + LiquidityForecast (expected currency flows with failure probabilities) + market data (spot rates, volatilities, correlations).

**Output:** FXRecommendation per currency pair, including optimal hedge ratio, notional, direction, and the decision tier to which the recommendation is routed.

**FXRecommendation Schema:**
```json
{
  "recommendation_id": "FX-2029-0814-001",
  "currency_pair": "EUR/USD",
  "direction": "SELL",
  "notional_usd": 1825000.00,
  "standard_hedge_ratio": 1.00,
  "payment_adjusted_hedge_ratio": 0.73,
  "adjustment_rationale": {
    "weighted_failure_probability": 0.27,
    "adjustment_factor": 0.50,
    "hedge_reduction_pct": 13.5,
    "annual_cost_saving_estimate_usd": 4200.00
  },
  "confidence": 0.82,
  "tier": 1,
  "tier_rationale": "Notional < $2M AND confidence > 0.80 AND hedge_ratio within 15% of standard",
  "execution_window": {"open": "2029-08-14T06:00:00Z", "close": "2029-08-14T06:30:00Z"},
  "model_version": "fx_opt_v1.0",
  "quant_sign_off": "required_before_production"
}
```

### 4.4 Module 4 — Decision Framework

The Decision Framework is P8's most legally significant module. It routes every treasury recommendation through a configurable three-tier authority structure.

**Tier Definitions:**

| Tier | Name | Authority | Trigger Criteria (defaults, configurable) | SLA |
|------|------|-----------|------------------------------------------|-----|
| **1** | Autonomous | AI executes, human informed after | Notional < $50K AND confidence > 0.85 AND action within ±15% of standard | Immediate execution, notification within 5 minutes |
| **2** | Escalation | AI recommends, single human confirms | $50K ≤ notional < $1M OR confidence 0.70–0.85 OR action deviates >15% from standard | 30-minute confirmation window. Auto-escalate to Tier 3 if no response. |
| **3** | Approval | AI recommends, multi-party sign-off | Notional ≥ $1M OR confidence < 0.70 OR novel action type OR corporate policy requires | No SLA — requires explicit approval from CFO + Treasury Manager (or configured approver list) |

**Override mechanics:** At all tiers, any authorised human can invoke an OVERRIDE action that: (a) cancels the pending recommendation, (b) logs the override reason (free text, mandatory), (c) records the overrider's identity and timestamp, and (d) creates an immutable audit entry. The system cannot suppress, delay, or discourage overrides. This is a hard requirement under EU AI Act Article 14(4)(d): "the ability to decide, in any particular situation, not to use the high-risk AI system or otherwise disregard, override or reverse the output."

**Kill switch:** A single API call or physical button (integrated via existing BPI infrastructure monitoring) immediately halts all P8 autonomous actions, cancels all pending Tier 2 escalations, and places all Tier 3 approvals in a frozen state. Kill switch events are logged, cannot be reversed without dual authorisation, and trigger an automated incident report.

**TreasuryAction Schema:**
```json
{
  "action_id": "TA-2029-0814-001",
  "action_type": "FX_HEDGE",
  "tier": 1,
  "status": "EXECUTED",
  "recommendation": {
    "fx_recommendation_id": "FX-2029-0814-001",
    "currency_pair": "EUR/USD",
    "direction": "SELL",
    "notional_usd": 1825000.00,
    "hedge_ratio": 0.73
  },
  "decision_log": {
    "tier_assignment_reason": "notional=$1.825M < threshold=$2M; confidence=0.82 > 0.80",
    "automated_checks_passed": ["notional_limit", "confidence_threshold", "deviation_check", "kill_switch_clear"],
    "execution_timestamp": "2029-08-14T06:01:23Z",
    "bank_confirmation_id": "BANK-FX-20290814-7742",
    "bank_execution_rate": 1.0842
  },
  "audit_trail": {
    "recommendation_generated": "2029-08-14T06:00:12Z",
    "tier_assigned": "2029-08-14T06:00:12Z",
    "bank_submitted": "2029-08-14T06:00:14Z",
    "bank_confirmed": "2029-08-14T06:01:23Z",
    "notification_sent": "2029-08-14T06:01:25Z",
    "hmac_signature": "a7f3b2c1..."
  },
  "override": null
}
```

---

## 5. Part 4 — The Novel Formula: Probability-Adjusted FX Hedging

### 5.1 The Problem with Standard FX Hedging

Standard minimum-variance FX hedging (Hull, 2022, Ch. 3) computes the optimal hedge ratio as:

```
h* = ρ × (σ_S / σ_F)
```

Where `ρ` is the correlation between spot and futures price changes, `σ_S` is the standard deviation of spot price changes, and `σ_F` is the standard deviation of futures price changes. For major currency pairs, h* is typically close to 1.0 (hedge 100% of exposure).

This formula assumes the underlying exposure is **certain** — that the cash flow being hedged will definitely materialise. In corporate treasury, this assumption is frequently wrong. The BIS Working Paper 1096 (2023) documents that approximately 40% of corporate FX hedging costs are attributable to hedging exposures that do not materialise — payments that arrive late (creating a timing mismatch with the hedge), payments that are partially fulfilled, or payments that fail entirely.

### 5.2 The Novel Formula

P8 introduces a probability-adjusted hedge ratio that integrates payment failure intelligence from C9:

```
h_adjusted = h* × (1 - P(failure) × α)
```

Where:
- `h*` = standard minimum-variance hedge ratio (from Hull's formula above)
- `P(failure)` = probability that the underlying payment fails to arrive within the hedge horizon, from C9's Cox PH survival model: `P(failure) = 1 - S(T_hedge | features)`
- `α` = adjustment factor, calibrated to the corporate's cash buffer tolerance (default 0.5, range [0, 1])

**Intuition (why this formula works):**

| Scenario | P(failure) | h_adjusted | Interpretation |
|----------|-----------|------------|----------------|
| Payment definitely arrives | 0.0 | h* × 1.0 = h* | Full hedge — exposure is certain |
| Payment has 20% failure risk | 0.2 | h* × 0.90 | Reduce hedge by 10% — exposure may partially vanish |
| Payment has 50% failure risk | 0.5 | h* × 0.75 | Reduce hedge by 25% — significant chance exposure won't materialise |
| Payment definitely fails | 1.0 | h* × 0.50 | Minimum hedge — almost no exposure, but retain floor for partial settlement |

**The adjustment factor α:**

The parameter α controls how aggressively the hedge ratio responds to failure probability. At α = 0 (fully conservative), the formula reduces to standard hedging — ignore failure probability entirely. At α = 1 (fully aggressive), the hedge ratio responds linearly to failure probability. The default α = 0.5 represents a balanced position:

- `α = 0.0`: Corporate has zero cash buffer tolerance. Hedge everything, even if payment may fail. Cost: pay hedging premium on phantom exposures.
- `α = 0.5`: Corporate has moderate buffer. Reduce hedge proportionally to failure risk, but retain a 50% floor even if payment is certain to fail (covers partial settlements, late arrivals, and model error).
- `α = 1.0`: Corporate has high buffer tolerance. Reduce hedge aggressively. Risk: if C9 model is wrong and payment arrives, corporate is under-hedged.

**QUANT sign-off is mandatory** before production deployment of any α value. The default (0.5) is conservative by design — it caps the maximum hedge reduction at 50% even for P(failure) = 1.0, providing a floor against C9 model error.

### 5.3 Full Derivation — Multi-Currency Portfolio Extension

For a corporate with exposure to N currencies, the portfolio-level probability-adjusted hedge is:

```
H_adjusted = Σᵢ [ hᵢ* × (1 - Pᵢ(failure) × αᵢ) × Eᵢ ]
```

Where:
- `hᵢ*` = minimum-variance hedge ratio for currency i
- `Pᵢ(failure)` = weighted average failure probability across all expected payments in currency i
- `αᵢ` = adjustment factor for currency i (may vary by currency based on market liquidity)
- `Eᵢ` = net exposure in currency i (from TreasurySnapshot)

**Portfolio-level failure probability for currency i:**

```
Pᵢ(failure) = Σⱼ [ P(failureⱼ) × amountⱼ ] / Σⱼ [ amountⱼ ]
```

Where j indexes all expected payments in currency i. This is an amount-weighted average — a single large payment with high failure probability dominates the portfolio adjustment more than many small payments with low failure probability.

### 5.4 Backtesting Requirement

**Before production deployment, the following backtesting protocol must be completed (QUANT sign-off gate):**

1. **12 months of simulated trades** — Apply the probability-adjusted formula to historical C9 predictions and actual FX market data. Compare cost/performance against standard hedging (α = 0) on the same data.
2. **Cost-saving validation** — Confirm that the probability-adjusted formula reduces hedging costs (premium paid on exposures that did not materialise) without materially increasing unhedged FX losses.
3. **α calibration** — Test α values from 0.1 to 0.9 in 0.1 increments. Select the α that maximises the Sharpe ratio of hedging cost savings / unhedged loss increase.
4. **Stress testing** — Apply the formula under C9 model failure scenarios (all predictions wrong by 2σ). Confirm that the maximum loss from under-hedging does not exceed 2× the cost savings under normal conditions.
5. **Out-of-time validation** — Repeat tests 1–4 on a held-out 6-month period not used for calibration.

---

## 6. Part 5 — EU AI Act Article 14 Compliance Architecture

### 6.1 Why P8 Will Be Classified as High-Risk

The EU AI Act (Regulation 2024/1689) classifies AI systems used in financial services as potentially high-risk under Annex III, Category 5(b): "AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score, with the exception of AI systems used for the purpose of detecting financial fraud." While P8 operates on corporate treasury (not personal creditworthiness), the Act's broad language around "AI systems intended to be used in the management and operation of critical infrastructure" (Annex III, Category 2) and "AI systems making decisions in the area of access to and enjoyment of essential private services" (Annex III, Category 5(a)) may capture autonomous treasury decision-making if a national competent authority interprets "essential private services" to include corporate banking services.

**BPI's position:** Assume high-risk classification and comply proactively. The cost of compliance is moderate (the three-tier framework is the architecture itself). The cost of non-compliance is existential (fines up to EUR 35M or 7% of global annual turnover).

### 6.2 Article 14 Compliance Matrix

| EU AI Act Requirement | Article | P8 Implementation | Evidence |
|----------------------|---------|-------------------|----------|
| **Human ability to understand AI capabilities and limitations** | Art. 14(4)(a) | Tier 3: Full natural-language explanation for every recommendation, including model confidence, data sources, and known limitations. Tier 1/2: Condensed explanation with link to full detail. | TreasuryAction.decision_log contains tier_assignment_reason, automated_checks_passed, model_version |
| **Awareness of automation bias** | Art. 14(4)(b) | Explicit uncertainty quantification on every action. Confidence intervals displayed prominently. Historical accuracy rate shown alongside each recommendation. | LiquidityForecast includes p5/p50/p95 confidence intervals. FXRecommendation includes confidence score. |
| **Ability to correctly interpret AI output** | Art. 14(4)(c) | All outputs accompanied by: (1) plain-language summary, (2) quantified uncertainty, (3) key input features that drove the recommendation, (4) comparison to standard (non-AI) approach | FXRecommendation.adjustment_rationale provides full decomposition |
| **Ability to override or reverse outputs** | Art. 14(4)(d) | OVERRIDE action available at all tiers. Override reason mandatory. Override logged immutably. System cannot suppress/delay/discourage overrides. | TreasuryAction.override field. Override audit trail with HMAC signature. |
| **"Stop" mechanism** | Art. 14(4)(e) | Kill switch: single API call or physical button halts all P8 actions. Dual authorisation required to resume. Automated incident report generated. | Kill switch integrated via existing `lip/infrastructure/monitoring/` |
| **Transparency of AI system operation** | Art. 13 | Model cards for all ML components (C9 survival model, FX optimizer). Feature importance for every recommendation. Training data documentation per SR 11-7. | Extends existing `lip/common/regulatory_reporter.py` SR117ModelValidationReport |
| **Record-keeping** | Art. 12 | All treasury actions logged for minimum 10 years. Immutable append-only audit log with cryptographic chain (HMAC per entry, chain hash per block). | Extends DORAAuditEvent infrastructure |
| **Accuracy, robustness, cybersecurity** | Art. 15 | Conformal prediction confidence intervals. Monthly model recalibration. Adversarial testing. Penetration testing on treasury API. | C9 calibration pipeline + CIPHER review |

### 6.3 Conformity Assessment

Under Article 43, high-risk AI systems in financial services may use the conformity assessment procedure based on internal control (Annex VI) rather than third-party assessment. BPI should:

1. **Establish a Quality Management System (QMS)** covering the P8 development lifecycle — design, training data, validation, deployment, monitoring, decommissioning.
2. **Prepare technical documentation** per Annex IV — system description, design specifications, development process, validation results, risk management measures.
3. **Conduct internal conformity assessment** before first deployment.
4. **Register in the EU Database** per Article 49 before placing P8 on the EU market.
5. **Appoint an EU authorised representative** per Article 22 (BPI is a Canadian entity).

**Timeline:** Full application of the EU AI Act is August 2, 2026. P8's target deployment is Q1 2030. This provides 3.5 years to complete conformity assessment — ample time, but the QMS and technical documentation should begin during engineering, not after.

---

## 7. Part 6 — Revenue Architecture

### 7.1 Fee Structure

| Fee Type | Rate | Charged To | When | BPI Share |
|----------|------|------------|------|-----------|
| **Platform subscription** | $200K–$500K p.a. (tiered by treasury complexity) | Corporate | Annual, invoiced quarterly | 100% BPI (technology licensing) |
| **Transaction fee** | 2–5 bps on notional of autonomous actions executed | Corporate (embedded in bank execution spread) | Per Tier 1 execution | Phase 1: 30%, Phase 2: 55%, Phase 3: 80% |
| **Performance premium** | 10–25% of demonstrated savings vs. manual treasury management | Corporate | Annual true-up, calculated from audited baseline comparison | 100% BPI |
| **FX intelligence premium** | 5–10 bps on hedged notional for probability-adjusted optimization | Bank (not disclosed to corporate) | Per FX recommendation that converts to execution | 100% BPI |
| **Setup fee** | $100K–$500K per corporate onboarding (one-time) | Corporate | On deployment | 100% BPI |

### 7.2 Revenue Projections (Three Scenarios)

**Assumptions:** Average subscription $350K. Average FX hedging notional $50M/year per corporate. Transaction fee 3 bps average. Performance premium 15% of savings. FX premium 7 bps average. 50 corporates by Year 5.

| Scenario | Corporates (Y5) | Subscription | Transaction | Performance | FX Premium | Total Annual | BPI Share |
|----------|-----------------|-------------|-------------|-------------|------------|-------------|-----------|
| **Conservative** | 20 | $7M | $1.2M | $0.8M | $2.1M | $11.1M | $9.4M |
| **Base** | 50 | $17.5M | $3.0M | $2.5M | $5.3M | $28.3M | $24.1M |
| **Upside** | 100 | $35M | $6.0M | $6.0M | $10.5M | $57.5M | $48.9M |

### 7.3 Why Corporates Will Pay

The value proposition is quantifiable against the BIS Working Paper 1096 finding:

- **40% of hedging costs are wasted** on exposures that don't materialise. For a corporate hedging $200M/year at an average cost of 50 bps, that is $400K/year in wasted hedging premium.
- **P8's probability-adjusted hedging** captures 50–80% of this waste (conservatively, given α = 0.5 default). That is $200K–$320K in annual savings on FX alone.
- **Add liquidity forecasting accuracy improvement** — better cash forecasting reduces overdraft usage, reduces opportunity cost of excess cash buffers, and enables more precise payment timing.
- **Total estimated value: $500K–$1.5M per year** for a mid-sized corporate ($200M+ cross-border payments). At a $350K subscription, the ROI is 1.4–4.3x in Year 1.

---

## 8. Part 7 — C-Component Engineering Map

### 8.1 C1–C5: No Change

C1 (ML Failure Classifier), C2 (PD Pricing Engine), C3 (Settlement Monitor), C4 (Dispute Classifier), and C5 (ISO 20022 Processor) are unchanged for P8 v0. C9's settlement predictions — which consume C1 features — are the interface between the existing pipeline and P8's new modules.

### 8.2 C6 — AML / Security
**Status: MINOR — Treasury Action Audit Trail (~1 week)**

P8 adds a new audit event type to the existing `DORAAuditEvent` infrastructure in `lip/common/regulatory_reporter.py`:

```python
class TreasuryActionAuditEvent(DORAAuditEvent):
    """Extends DORA audit for P8 treasury actions.
    Every recommendation, execution, escalation, approval, override,
    and kill switch activation is recorded as an immutable audit entry.
    """
    action_id: str                    # TA-YYYY-MMDD-NNNN
    action_type: TreasuryActionType   # FX_HEDGE, FACILITY_DRAW, PAYMENT_TIMING, REBALANCE
    tier: int                         # 1, 2, or 3
    status: ActionStatus              # RECOMMENDED, ESCALATED, APPROVED, EXECUTED, OVERRIDDEN, KILLED
    notional_usd: Decimal
    confidence: float
    override_reason: Optional[str]    # Mandatory if status == OVERRIDDEN
    approvers: List[str]              # Empty for Tier 1, single for Tier 2, multiple for Tier 3
    kill_switch_active: bool          # True if action was halted by kill switch
    eu_ai_act_article_14: bool = True # Always True — documents compliance
```

CIPHER review required before deployment. Treasury actions do not directly involve AML-regulated payments, but the audit trail must meet DORA Article 19 requirements for ICT-related incident reporting if a P8 action triggers a downstream payment that is later flagged.

### 8.3 C7 — Bank Integration Layer
**Status: EXTEND — Treasury Action Execution API (~3–4 weeks)**

C7 currently handles bridge lending (P2) and facility management (P4). P8 extends C7 with treasury action execution endpoints:

**New C7 Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/treasury/action/recommend` | P8 submits recommendation to bank |
| `POST` | `/api/v1/treasury/action/{id}/execute` | Bank executes action (Tier 1 auto, Tier 2/3 after approval) |
| `POST` | `/api/v1/treasury/action/{id}/escalate` | Tier 2 escalation to human approver |
| `POST` | `/api/v1/treasury/action/{id}/approve` | Human approves Tier 2/3 action |
| `POST` | `/api/v1/treasury/action/{id}/override` | Human overrides any action |
| `POST` | `/api/v1/treasury/kill-switch` | Emergency halt — all P8 actions |
| `GET` | `/api/v1/treasury/snapshot/{corporate_id}` | Current treasury position |
| `GET` | `/api/v1/treasury/forecast/{corporate_id}` | Liquidity forecast |
| `GET` | `/api/v1/treasury/actions` | Action history with audit trail |

**C7 Extension: Execution Context**

Extends the existing `LicenseeContext` from `lip/c8_license_manager/license_token.py` with treasury-specific configuration:

```python
@dataclass
class TreasuryLicenseeContext:
    """Extends LicenseeContext for P8 treasury operations."""
    base_context: LicenseeContext          # Existing C8 licence token
    tier_1_notional_limit_usd: Decimal     # Max notional for autonomous execution
    tier_2_notional_limit_usd: Decimal     # Max notional for single-approver escalation
    tier_2_sla_minutes: int                # Confirmation window (default 30)
    tier_3_approvers: List[str]            # Required approver IDs for Tier 3
    fx_enabled: bool                       # Can P8 recommend FX actions
    facility_draw_enabled: bool            # Can P8 recommend facility draws
    payment_timing_enabled: bool           # Can P8 recommend payment re-timing
    kill_switch_endpoint: str              # Bank's kill switch API URL
    alpha_override: Optional[float]        # Corporate-specific α, if different from default
```

### 8.4 C9 — Settlement Predictor
**Status: NO CHANGE (Consumed)**

C9 is consumed by P8's Liquidity Forecaster. The existing `SettlementTimePredictor.predict()` method returns `SettlementPrediction` with `predicted_hours` and confidence intervals. P8 calls this for every expected incoming payment in the corporate's Payment Expectation Graph (from P4) and converts the settlement time prediction into a failure probability:

```
P(failure) = 1 - S(T_hedge | features)
```

Where `T_hedge` is the hedge maturity horizon. If P4's hazard rate extraction API (§2.2 of P4 blueprint) is already deployed, P8 calls `predict_delay_hazard()` directly. If not, P8 computes the failure probability from the raw survival function. No C9 changes required.

---

## 9. Part 8 — Treasury Action API Design

### 9.1 Recommendation Payload (P8 Engine → Bank C7)

```json
{
  "recommendation_id": "REC-20290814-0001",
  "corporate_id": "hashed:abc123",
  "recommendation_type": "FX_HEDGE",
  "generated_at": "2029-08-14T06:00:12Z",
  "treasury_context": {
    "snapshot_id": "TS-2029-0814-0600",
    "forecast_id": "LF-2029-0814-0600",
    "position_currency": "EUR",
    "net_exposure_usd": 2500000.00,
    "payment_adjusted_exposure_usd": 1825000.00
  },
  "action": {
    "action_type": "FX_HEDGE",
    "currency_pair": "EUR/USD",
    "direction": "SELL",
    "notional_usd": 1825000.00,
    "hedge_ratio": 0.73,
    "standard_hedge_ratio": 1.00,
    "instrument": "FX_FORWARD",
    "tenor_days": 7,
    "indicative_rate": 1.0845,
    "rate_source": "ECB_REFERENCE",
    "rate_timestamp": "2029-08-14T05:59:00Z"
  },
  "risk_assessment": {
    "confidence": 0.82,
    "failure_probability_weighted": 0.27,
    "adjustment_factor_alpha": 0.50,
    "max_loss_if_underhedged_usd": 18250.00,
    "cost_saving_vs_full_hedge_usd": 4200.00,
    "var_99_usd": 42000.00
  },
  "tier_assignment": {
    "tier": 1,
    "rationale": [
      "notional_usd=1825000 < tier_1_limit=2000000",
      "confidence=0.82 > tier_1_min_confidence=0.80",
      "hedge_ratio_deviation=27% > 15% threshold — OVERRIDE: deviation driven by high P(failure), not model uncertainty",
      "kill_switch_status=CLEAR"
    ],
    "auto_execute": true,
    "escalation_required": false,
    "approval_required": false
  },
  "eu_ai_act_compliance": {
    "article_14_human_oversight": true,
    "explanation_available": true,
    "override_mechanism": "POST /api/v1/treasury/action/{id}/override",
    "kill_switch_mechanism": "POST /api/v1/treasury/kill-switch",
    "model_card_reference": "MC-FX-OPT-v1.0",
    "data_quality_score": 0.94
  },
  "hmac_signature": "b4e7a1f9..."
}
```

### 9.2 Execution Response (Bank → P8)

```json
{
  "execution_id": "EXEC-20290814-0001",
  "recommendation_id": "REC-20290814-0001",
  "status": "EXECUTED",
  "execution_details": {
    "bank_trade_id": "BANK-FX-20290814-7742",
    "executed_at": "2029-08-14T06:01:23Z",
    "executed_rate": 1.0842,
    "slippage_bps": 0.3,
    "notional_executed_usd": 1825000.00,
    "settlement_date": "2029-08-16"
  },
  "bank_risk_checks": {
    "credit_limit_check": "PASSED",
    "market_risk_check": "PASSED",
    "compliance_check": "PASSED",
    "counterparty_check": "PASSED"
  },
  "hmac_signature": "c8d2e5b3..."
}
```

### 9.3 Escalation Payload (Tier 2)

```json
{
  "escalation_id": "ESC-20290814-0001",
  "recommendation_id": "REC-20290814-0002",
  "tier": 2,
  "escalation_reason": "notional_usd=3500000 exceeds tier_1_limit=2000000",
  "escalated_to": ["treasury_manager@corporate.com"],
  "escalated_at": "2029-08-14T06:05:00Z",
  "sla_deadline": "2029-08-14T06:35:00Z",
  "auto_escalate_to_tier_3_at": "2029-08-14T06:35:00Z",
  "action_summary": {
    "action_type": "FX_HEDGE",
    "currency_pair": "GBP/USD",
    "notional_usd": 3500000.00,
    "hedge_ratio": 0.68,
    "confidence": 0.78,
    "plain_language": "Recommend selling GBP 2.38M forward (68% of exposure). Three incoming GBP payments have elevated failure risk (weighted P=0.32). Full hedge would cost ~$12K more in premium on payments that may not arrive. Confidence: 78%."
  },
  "options": [
    {"action": "APPROVE", "endpoint": "POST /api/v1/treasury/action/REC-20290814-0002/approve"},
    {"action": "OVERRIDE", "endpoint": "POST /api/v1/treasury/action/REC-20290814-0002/override"},
    {"action": "MODIFY", "endpoint": "POST /api/v1/treasury/action/REC-20290814-0002/modify", "note": "Adjust notional or hedge ratio before execution"}
  ]
}
```

### 9.4 Override Payload

```json
{
  "override_id": "OVR-20290814-0001",
  "action_id": "TA-2029-0814-002",
  "overridden_by": "treasury_manager@corporate.com",
  "override_timestamp": "2029-08-14T06:12:45Z",
  "override_reason": "Prefer to hedge 100% — management view that payment will arrive despite model uncertainty. Quarterly board presentation requires conservative FX position.",
  "original_recommendation": {
    "hedge_ratio": 0.68,
    "notional_usd": 3500000.00
  },
  "override_action": {
    "hedge_ratio": 1.00,
    "notional_usd": 5147000.00,
    "instruction": "EXECUTE_MODIFIED"
  },
  "eu_ai_act_record": {
    "article_14_4d_override_exercised": true,
    "automation_bias_warning_displayed": true,
    "override_freely_given": true
  },
  "hmac_signature": "d1a4f8c2..."
}
```

### 9.5 Kill Switch Payload

```json
{
  "kill_switch_id": "KS-20290814-0001",
  "activated_by": "cfo@corporate.com",
  "activated_at": "2029-08-14T06:15:00Z",
  "reason": "Unexpected market volatility — suspending all autonomous actions pending review.",
  "scope": "ALL_P8_ACTIONS",
  "actions_halted": [
    {"action_id": "TA-2029-0814-003", "status_before": "PENDING_EXECUTION", "status_after": "KILLED"},
    {"action_id": "TA-2029-0814-004", "status_before": "ESCALATED", "status_after": "KILLED"}
  ],
  "resume_requires": {
    "dual_authorization": true,
    "required_approvers": ["cfo@corporate.com", "treasury_manager@corporate.com"],
    "incident_report_required": true
  }
}
```

---

## 10. Part 9 — Consolidated Engineering Timeline

### 10.1 Build Plan: 9 Sprints, 24 Weeks, 2 Engineers

| Sprint | Weeks | Components | Deliverable | Owner | Dependencies |
|--------|-------|------------|-------------|-------|-------------|
| Sprint 1 | W1–W3 | Treasury State Aggregator (schema + ingestion) | MT940/camt.053 parser, position normalization, TreasurySnapshot model | Backend Eng 1 | None |
| Sprint 2 | W3–W5 | Treasury State Aggregator (ERP + P4 integration) | ERP connector stubs (SAP/Oracle/Kyriba), P4 facility position ingestion | Backend Eng 1 | Sprint 1 |
| Sprint 3 | W4–W7 | Liquidity Forecaster | C9 integration, probability-weighted inflows, conformal prediction intervals, LiquidityForecast model | Backend Eng 2 | C9 API (existing) |
| Sprint 4 | W8–W10 | FX Optimizer | Minimum-variance hedge calculation, probability-adjusted formula, multi-currency portfolio extension. **QUANT sign-off gate.** | Backend Eng 2 | Sprint 3 |
| Sprint 5 | W8–W11 | Decision Framework (core) | Three-tier routing engine, threshold configuration, SLA timer, auto-escalation logic | Backend Eng 1 | Sprint 2 |
| Sprint 6 | W12–W14 | Decision Framework (compliance) | Override mechanics, kill switch, EU AI Act audit trail, immutable log with HMAC chain | Backend Eng 1 | Sprint 5 |
| Sprint 7 | W12–W15 | C7 Extension — Treasury Action API | All endpoints (recommend, execute, escalate, approve, override, kill-switch). Bank mock for testing. | Backend Eng 2 | Sprint 4, Sprint 5 |
| Sprint 8 | W16–W17 | C6 Extension + C8 Extension | TreasuryActionAuditEvent, treasury subscription token, fee metering | Backend Eng 1 | Sprint 6 |
| Sprint 9 | W18–W24 | Integration test + shadow run preparation | End-to-end: snapshot → forecast → optimize → decide → execute → audit. Load testing. Failure injection. | Both | All sprints |

### 10.2 Parallel Validation Track

**Critical dependency: 12 months of C9 production data + 6 months of P4 facility data.**

P8 cannot go live until:
1. C9 has been running in production for at least 12 months (settlement prediction accuracy validated)
2. P4 has been running for at least 6 months (facility usage patterns available for liquidity forecasting)
3. The probability-adjusted FX formula has been backtested against 12 months of historical data (QUANT sign-off gate)
4. The Decision Framework has been shadow-run for 6 months (all three tiers exercised, no autonomous execution — Tier 1 recommendations generated but logged, not executed)

**Shadow Run Protocol (6 months):**
- P8 generates all recommendations and tier assignments
- Tier 1 actions logged but NOT executed — compared against what the human actually did
- Tier 2/3 escalations sent to treasury team as "shadow alerts" — no SLA, no consequence
- After-the-fact analysis: (a) did the recommendation match what the human chose? (b) what would the P&L impact have been if P8 had executed? (c) were tier assignments appropriate?
- Threshold calibration: adjust tier boundaries based on shadow run hit rates

### 10.3 Parallel Legal Track

| Milestone | Owner | Timeline |
|-----------|-------|----------|
| Securities/investment counsel opinion — all target jurisdictions | BPI legal + external counsel | W1–W6 |
| E&O insurance gap analysis — AI exclusion language review | BPI legal + insurance broker | W1–W4 |
| Draft AI Recommendation Acknowledgement template | BPI legal | W4–W8 |
| Draft P8 Treasury Intelligence Addendum | BPI legal + bank counsel | W6–W10 |
| EU AI Act conformity assessment — QMS documentation | REX + BPI legal | W8–W16 |
| EU authorised representative appointment | BPI legal | W12–W16 |
| Corporate pilot agreement (3–5 corporates via existing bank partner) | BPI commercial + bank partner | W20–W24 |
| Shadow run with pilot corporates | All tracks | W24–W48 (6 months) |
| Live pilot: 3–5 corporates, Tier 2/3 only (no autonomous execution) | All tracks | W48+ |
| Tier 1 autonomous execution enablement (after 3 months of Tier 2/3 only) | All tracks + QUANT sign-off | W60+ |

---

## 11. Part 10 — What Stays in the Long-Horizon P8 Patent

| Feature | Why Not in 2029 | Target |
|---------|----------------|--------|
| **Reinforcement learning treasury agent** (replaces rule-based tier routing) | Requires 100K+ treasury action observations; three-tier rule engine works with configured thresholds | 2031–2032 |
| **Cross-corporate FX netting** (Corporate A's EUR surplus offsets Corporate B's EUR need) | Legal complexity; requires multi-corporate data consent and bank netting agreement | 2030+ |
| **Real-time volatility-responsive hedging** (sub-minute FX re-optimization) | Requires direct market data feed integration; P8 v0 uses ECB reference rates (15-minute delay) | Phase 2 (after pilot validates value) |
| **Autonomous facility draw integration** (P8 decides, P4 draws) | Requires both P4 and P8 in production simultaneously with validated interaction effects | 2031+ |
| **Multi-bank optimization** (route FX trades to cheapest execution venue) | Requires 3+ bank partnerships in production; conflicts with white-label deployment model | Phase 3 (own balance sheet) |
| **CBDC-native treasury management** (P6 + P8 integration) | CBDC infrastructure not production-ready in major currencies | 2032+ |

---

## 12. Part 11 — Risk Register (P8 v0 Specific)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **EU AI Act classifies P8 as "high-risk"** — triggers full Annex IV conformity assessment | High | High | Already compliant by design: three-tier framework exceeds Article 14 requirements. File conformity assessment proactively. Budget EUR 150K for EU authorised representative + legal costs. The three-tier framework is not a compliance bolt-on — it IS the architecture. |
| **E&O insurance excludes AI-driven decisions** — commercial E&O policy does not cover claims arising from P8 recommendations | High | Medium | Five-layer mitigation (§3.3): AI Recommendation Acknowledgement, bank execution (not BPI), Tier 2/3 default above $100K, continuous audit trail, captive insurance evaluation. Begin insurance broker engagement at W1 — do not wait for deployment. |
| **Probability-adjusted hedge causes FX loss** — C9 predicts payment will fail (reduce hedge), payment arrives, corporate is under-hedged | Medium | High | QUANT sign-off mandatory. 12-month backtesting. Conservative α default (0.5) caps maximum hedge reduction at 50%. Stress test: α under 2σ model failure. Performance monitoring dashboard with automatic α reduction trigger if cumulative under-hedge losses exceed 1.5× cumulative cost savings. |
| **Corporate adopts P8 without meaningful oversight** — treasury team trusts Tier 1 blindly, does not review Tier 2/3 escalations | Medium | Critical | Tier 2/3 default for all actions >$100K (non-negotiable). Mandatory override drill: once per quarter, system generates a deliberate test recommendation that should be overridden, to verify human attention. Automation bias warning displayed on every recommendation (EU AI Act Art. 14(4)(b)). |
| **Liability for autonomous treasury actions** — corporate sues BPI for Tier 1 action that results in loss | Medium | Critical | BPI provides recommendations only — bank executes. AI Recommendation Acknowledgement signed by corporate. Tier 1 notional cap ($50K default) limits maximum single-action exposure. Aggregate Tier 1 daily cap. Attorney must confirm liability structure in each target jurisdiction before deployment. |
| **C9 model drift degrades forecast quality** — settlement predictions become less accurate over time, FX recommendations worsen | Medium | High | Continuous monitoring via conformal prediction calibration. If empirical coverage drops below 90% (p5–p95 interval should contain 90% of outcomes), automatic model freeze: all actions escalated to Tier 3 until recalibration completes. Monthly recalibration pipeline (extends existing C9 validation). |
| **Competing TMS vendors acquire AI capabilities** — Kyriba, HighRadius, or a hyperscaler launches autonomous treasury AI | Medium | Medium | 2–3 year moat from: (a) C9 payment data (cross-institutional, no TMS has this), (b) probability-adjusted formula (patent-pending), (c) three-tier decision framework (patent-pending), (d) EU AI Act compliance architecture (first-mover advantage). Even if a competitor builds a treasury AI, they cannot integrate payment failure intelligence without either licensing from BPI or building their own cross-bank payment monitoring infrastructure (3–5 year timeline). |

---

End of Document

---

Bridgepoint Intelligence Inc.
Internal Use Only — Strictly Confidential — Attorney-Client Privileged
Document ID: P8-v0-Implementation-Blueprint-v1.0.md
Date: March 27, 2026
Supersedes: N/A (first version)
Next review: Upon completion of Sprint 4 (FX Optimizer — QUANT sign-off gate) or upon receipt of securities counsel opinion on investment advisory classification
