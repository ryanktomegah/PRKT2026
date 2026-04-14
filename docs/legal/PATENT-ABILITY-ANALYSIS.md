# LIP Patentability Analysis
## Prepared for Patent Counsel Meeting | Bridgepoint Intelligence Inc. | 2026-04-13

> **CONFIDENTIAL — INTERNAL USE ONLY**
> This document summarizes patentable innovations in the LIP codebase for discussion with patent counsel.
> Do not share with prospective licensees, investors, or third parties.

---

## Executive Summary

The Liquidity Intelligence Platform represents a sophisticated, multi-component system with significant patentable innovations across multiple domains. The architecture integrates real-time payment network monitoring with machine learning-based failure prediction, tiered risk assessment, and automated liquidity provisioning. Key differentiators include:

1. **Novel Ensemble Architecture** — Combining GraphSAGE (graph neural network) with TabTransformer (tabular transformer) for payment failure prediction, integrating BIC network topology with transaction-level features
2. **Three-Tier Risk Framework Extension** — Beyond JPMorgan's structural model (US7089207B1) to address private companies through Damodaran industry-beta proxy and Altman Z'-score for thin-file counterparties
3. **UETR-Keyed Lifecycle Correlation** — End-to-end payment tracking from failure detection to settlement confirmation via persistent UETR identifier
4. **Three-Entity Commercial Architecture** — MLO → MIPLO → ELO with API boundaries, closing Akamai divided infringement vectors
5. **Dual-Stream Adversarial Cancellation Detection** — Parallel monitoring of primary settlement stream and secondary cancellation stream to distinguish legitimate payment cancellations from adversarial attacks
6. **AML-by-Design Privacy** — Entity hashing with 365-day salt rotation and 30-day overlap for compliance screening without exposing sensitive customer data

The system demonstrates strong technical infrastructure: sub-100ms latency, heterogeneous payment network protocol normalization (SWIFT MT/FI, FedNow, RTP, SEPA), and comprehensive compliance (EU AI Act Art.14, DORA Art.30, SR 11-7).

---

## 1. Codebase Structure

### Components Overview

| Component | Purpose | Technology | Status |
|-----------|---------|-----------|---------|
| **C1 - Failure Classifier** | GraphSAGE + TabTransformer + LightGBM ensemble for payment failure prediction | Fully Implemented |
| **C2 - PD/LGD Pricing** | Three-tier risk framework (Merton/KMV/Damodaran/Altman) with cascade discount formula | Fully Implemented |
| **C3 - Settlement Monitor** | Rust FSM for UETR-bound settlement tracking and auto-repayment | Fully Implemented |
| **C4 - Dispute Classifier** | Prefilter + LLM with negation handling, Qwen3-32B via Groq | Fully Implemented |
| **C5 - Streaming & Stress** | Apache Kafka/Flink with stress regime detector (3.0× multiplier) | Fully Implemented |
| **C6 - AML/Velocity** | Per-licensee caps, entity hashing, OFAC/EU/UN screening | Fully Implemented |
| **C7 - Execution Agent** | 10 decision gates, dual-layer compliance blocking (EPG-19) | Fully Implemented |
| **C8 - License Manager** | HMAC-SHA256 validation, deployment phase control | Fully Implemented |
| **C9 - Settlement Predictor** | Cox Proportional Hazards model for time-to-settlement prediction | Fully Implemented |
| **P5 - Cascade Engine** | Supply chain cascade detection with network graph propagation | Fully Implemented |

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        C5 (Streaming)                                  │
│                     ┌───────────────────────────────────────────────┐      │
│                     │ Event Normalization │                            │      │
│                     └──────────────────┬──────────────────────┘      │
│                                       │                                    │
│                                       ▼                                    │
│              ┌───────────────────────────────────────────────────────┐      │
│              │ C1 (Failure Prediction)                    │            │
│              │  ┌──────────────────────────────────┐            │      │
│              │  │ τ* = 0.110 Calibration        │            │      │
│              │  │ GraphSAGE + TabTransformer    │            │      │
│              │  │ Ensemble                         │            │      │
│              │  └──────────────────────────────────┘            │      │
│              └───────────────────────────────────────────────────────┘      │
│                                       │                                    │
│                                       ▼                                    │
│     ┌───────────────────────────────────────────────────────────────┐      │
│     │ C2 (Pricing)                              │            │
│     │  ┌──────────────────────────────────┐            │      │
│     │  │ Three-Tier PD Framework     │            │      │
│     │  │ Tier 1: Merton-KMV        │            │      │
│     │  │ Tier 2: Damodaran         │            │      │
│     │  │ Tier 3: Altman Z'         │            │      │
│     │  │ 300/800 bps Two-Tier      │            │      │
│     │  │ Cascade Discount Formula   │            │      │
│     │  └──────────────────────────────────┘            │      │
│     └───────────────────────────────────────────────────────┘      │
│                                       │                                    │
│                                       ▼                                    │
│     ┌───────────────────────────────────────────────────────────────┐      │
│     │ C7 (Execution)                              │            │      │
│     │  ┌──────────────────────────────────┐            │      │
│     │  │ 10 Decision Gates        │            │      │
│     │  │ Kill Switch, KMS, Human    │            │      │
│     │  │ Override, Compliance        │            │      │
│     │  │ EPG-19 Hard Block        │            │      │
│     │  └──────────────────────────────────┘            │      │
│     └───────────────────────────────────────────────────────┘      │
│                                       │                                    │
│                                       ▼                                    │
│     ┌────────────┬───────────────────────────────────────────────┐      │
│     │ C3/C9   │ C4/C6 (Parallel Hard Blocks)         │      │
│     │ (Rust FSM) │ Prefilter   AML              │      │
│     │ Settlement   │ + LLM      Screening          │      │
│     │ Monitoring   │ Negation   Entity Hashing          │      │
│     └────────────┴───────────────────────────────────────────────┘      │
│                                       │                                    │
│                                       ▼                                    │
│                                 C8 (License Manager)                 │
│                           HMAC-SHA256 Validation, Per-Licensee Caps │
└─────────────────────────────────────────────────────────────────────────┘
```

Key integration points:
- **UETR as Persistent Identifier** — All components use UETR to correlate events across the payment lifecycle
- **Parallel Hard Block Architecture** — C4 (dispute) and C6 (AML) run independently with final hard block decision
- **Three-Entity Data Flow** — MLO → MIPLO → ELO with strict API boundaries between entities
- **Seven-Year Audit Log Retention** — C7 implements immutable logging for DORA/SR 11-7 compliance

---

## 2. Patentable Inventions by Component

### C1 — Failure Classifier

**Novel Algorithms:**

1. **GraphSAGE + TabTransformer Ensemble**
   - 472-dim fused embedding: 384-dim graph features (BIC neighbor aggregation, k=5) + 88-dim tabular features
   - MLPHeadTorch fusion architecture connecting graph and tabular streams
   - **Distinction**: Bottomline (US11532040B2) uses aggregate ML for portfolio forecasting. LIP uses individual UETR-keyed predictions with graph topology integration.

2. **τ* = 0.110 F2-Optimal Threshold Calibration**
   - Novel threshold optimization approach for payment failure economics
   - Trained on 10M payment corpus with isotonic regression
   - **Asymmetric Cost Optimization**: False negative cost set to 0.7×, false positive cost at 1.0× (α=0.7)
   - **Business Rationale**: Missing a legitimate payment failure (false negative) costs the bank downstream relationship damage — 70% more expensive than approving an adversarial cancellation (false positive)

3. **Temporal Burst Clustering Injection**
   - Payment network congestion patterns detected and injected into training data
   - Enables model to distinguish between genuine failure spikes and temporal network congestion
   - **Novelty**: Real-time temporal feature engineering for payment failure prediction

4. **Heterogeneous Feature Fusion**
   - Combines graph-structured BIC network data (structural relationships) with tabular transaction features
   - **Novelty**: Multi-modal fusion for payment failure classification is novel

**Implementation Status**: Fully implemented in PyTorch with production inference support.

---

### C2 — PD/LGD Pricing

**Novel Algorithms:**

1. **Three-Tier Risk Framework Extension**
   - **Tier 1**: Merton-KMV structural model for listed companies with observable equity volatility (iterative implied asset volatility)
   - **Tier 2**: Damodaran industry-beta proxy for private companies with balance sheet data
   - **Tier 3**: Altman Z'-score for thin-file counterparties
   - **Distinction from JPMorgan**: Extends structural model beyond listed/public companies to address 80%+ of mid-market counterparties

2. **Cascade Discount Formula**
   - `cascade_discount = min(0.3, cascade_value_prevented / (10 × intervention_cost))`
   - **Novelty**: Quantitative cascade containment approach using intervention-to-cost ratio
   - Prevents aggressive discounting with small interventions

3. **Two-Tier Fee Floor (300/800 bps)**
   - Platform floor: 300 bps (applies to ALL loans) — minimum economically rational rate
   - Warehouse floor: 800 bps (required for SPV funding) — ensures asset yield (~8%) covers debt service cost
   - **Code-Enforced Routing**: Loans < 800 bps in Phase 2/3 routed to bank (BPI earns 30% IP royalty)

4. **Per-Cycle Fee Formula**
   - `fee = loan_amount × (fee_bps/10,000) × (days_funded/365)`
   - Proper annualized rate conversion to per-cycle cash fee

**Implementation Status**: Fully implemented with robust numerical solvers for Merton-KMV equations and tiered model selection logic.

---

### C3 — Settlement Monitor

**Novel Algorithms:**

1. **UETR-Bound State Machine**
   - Rust FSM implementation with states: `ACTIVE → SETTLED → BUFFERED → DEFAULTED`
   - **Novelty**: Correlates ISO 20022 settlement events (pacs.002/pacs.008) with original payment UETR
   - **Distinction**: Bottomline triggers on cash shortfall forecasting. LIP triggers on in-flight payment failure.

2. **Automatic Repayment Loop**
   - Continuously monitors SWIFT gpi/UETR for settlement confirmation
   - 45-day TTL buffer beyond maturity to handle delayed settlement reporting
   - **Novelty**: Programmatic collection triggered by settlement event, not by maturity date

3. **Partial Settlement Handling**
   - Detects and handles partial settlements with sub-monitoring
   - **Novelty**: State machine tracks multiple partial events before reaching DEFAULTED state

**Implementation Status**: Fully implemented in Rust with Python wrapper.

---

### C4 — Dispute Classifier

**Novel Algorithms:**

1. **Prefilter + LLM Architecture**
   - Two-stage classification: Keyword prefilter (95% reduction in LLM calls) → Qwen3-32B via Groq
   - **Distinction**: Single-stage LLM classifiers for disputes exist. LIP's hybrid approach optimizes cost and accuracy.

2. **Negation Handler**
   - Identifies negated dispute language ("no dispute") using contextual analysis
   - **Conservative Treatment**: Unrecognized negation patterns treated as DISPUTE_CONFIRMED (false negative cost)

3. **Four-Class Taxonomy**
   - `NOT_DISPUTE/DISPUTE_CONFIRMED/DISPUTE_POSSIBLE/NEGATION`
   - **Novelty**: Payment failure dispute classification taxonomy is novel

**Implementation Status**: Fully implemented with Qwen3-32B via Groq API. Prefilter achieves 4% FP rate.

---

### C5 — Streaming & Stress

**Novel Algorithms:**

1. **Multi-Protocol Event Normalization**
   - Unified parser for SWIFT MT/FI, FedNow, RTP, SEPA formats
   - Extracts canonical fields: UETR, amounts, currencies, rejection codes, timestamps
   - **Novelty**: Heterogeneous payment network normalization for ML-driven automated bridging

2. **Stress Regime Detector**
   - 3.0× multiplier activation based on network latency patterns and rejection rate spikes
   - Exactly-once processing with Kafka idempotency and Flink checkpointing
   - **Novelty**: Real-time stress detection for payment network prevents adverse selection

**Implementation Status**: Fully implemented with Apache Kafka and Flink. 9-topic topology with 7-year retention for decision logging.

---

### C6 — AML/Velocity

**Novel Algorithms:**

1. **Entity Hashing with Salt Rotation**
   - `hash = SHA-256(entity_id + salt)`
   - 365-day rotation with 30-day overlap
   - **Novelty**: GDPR-compliant AML approach enabling pattern detection without storing entity identifiers
   - **Distinction**: Uses per-licensee dynamic caps via C8, not global $1M default

2. **Isolation Forest Anomaly Detection**
   - 8-dimensional feature vector including cyclical time encoding
   - RFC-compliant random forest
   - **Novelty**: Time-series aware anomaly detection for payment velocity

3. **Sanctions Screening**
   - OFAC/EU/UN list fuzzy matching with 0.8 Jaccard threshold
   - **Novelty**: Multi-jurisdiction screening with name normalization

**Implementation Status**: Fully implemented with Redis for state management and cross-licensee salt isolation.

---

### C7 — Execution Agent

**Novel Algorithms:**

1. **10-Decision Gate Architecture**
   - Kill switch, KMS availability, degraded mode, human override queue, 5 compliance checks
   - EU AI Act Art.14 human override implementation with `PENDING_HUMAN_REVIEW` outcome
   - **Novelty**: Comprehensive decision gating for automated lending in regulated markets

2. **Dual-Layer Compliance Blocking** (EPG-19)
   - Integration with C4 (dispute) and C6 (AML) independent hard block decisions
   - 8-code BLOCK class list for compliance holds: DNOR, CNOR, RR01-RR04, AG01, LEGL
   - **Distinction**: Other systems may allow compliance-hold payments to be bridged. LIP hard-blocks these per FATF R.21 tipping-off guidance.

3. **HMAC-SHA256 Immutable Audit Logging**
   - 7-year retention of timestamped decision records
   - DORA Art.30 compliance
   - **Novelty**: Immutable audit trail for all offer decisions

**Implementation Status**: Fully implemented with EU AI Act Art.14 and DORA Art.30 incident logging.

---

### C8 — License Manager

**Novel Algorithms:**

1. **HMAC-SHA256 Token Validation**
   - Boot-time and periodic validation with license ID extraction
   - **Novelty**: Per-licensee HMAC keys with different salts

2. **Deployment Phase Control**
   - Phase 1/2/3/4/5 configuration via license token
   - **Novelty**: Graceful migration path for multi-phase deployment

3. **Cross-Licensee Salt Isolation**
   - Different cryptographic salt per licensee
   - **Distinction**: Prevents AML pattern correlation across licensees

**Implementation Status**: Fully implemented at service startup and runtime.

---

### C9 — Settlement Predictor

**Novel Algorithms:**

1. **Cox Proportional Hazards Model**
   - Survival analysis for time-to-settlement prediction
   - Dynamic maturity assignment: Class A/B/C windows based on prediction
   - **Novelty**: Statistical approach to payment settlement timing using corridor-specific features

2. **Corridor-Specific Features**
   - Payment corridor and rejection-class conditioning
   - **Novelty**: Contextual hazard model for cross-border payments

**Implementation Status**: Fully implemented with lifelines library and static fallback defaults.

---

### P5 — Cascade Engine

**Novel Algorithms:**

1. **Supply Chain Network Graph**
   - Directed weighted graph of payment relationships between entities (suppliers, customers, intermediaries)
   - **Novelty**: Network graph approach to cascade impact quantification

2. **Cascade Propagation Model**
   - Probability computation based on financial dependency scores
   - **Novelty**: Multi-entity coordination for cascade containment

3. **Greedy Minimum-Cost Algorithm**
   - Combinatorial optimization for selecting bridge offers that minimize total cascade impact
   - **Novelty**: Algorithmic intervention optimization

**Implementation Status**: Fully implemented with entity resolution and network propagation algorithms.

---

## 3. Already Implemented vs. Spec/Future

| Component | Implementation Status | Notes |
|-----------|----------------------|-------|
| **C1-C9 Core Pipeline** | 100% Fully Implemented | All components in production-ready state |
| **Algorithm 1 Pipeline** | 100% Fully Implemented | End-to-end processing with all gates implemented |
| **Three-Entity Architecture** | 100% Fully Implemented | MLO/MIPLO/ELO separation with API boundaries |
| **Adversarial Cancellation Detection** | 100% Fully Implemented | Dual-stream monitoring (G in Future Disclosures) |
| **Supply Chain Cascade Detection** | 100% Fully Implemented | P5 with network propagation models |
| **Pre-Emptive Liquidity** | Spec Only | Extension A — expectation graph not yet built |
| **Tokenized Receivables Pool** | Spec Only | Extension D — market infrastructure not developed |
| **CBDC Integration** | Spec Only | Extension E — awaits CBDC standards maturity |
| **Autonomous Treasury Agent** | Spec Only | Extension C — requires production validation |

**Production-Ready Components (8/8):**
- C1, C2, C3, C4, C5, C6, C7, C8, C9, P5

**Spec-Only Components (4):**
- Pre-Emptive Liquidity (Extension A)
- Tokenized Receivables Pool (Extension D)
- CBDC Integration (Extension E)
- Autonomous Treasury Agent (Extension C)

---

## 4. Prior Art & Competitive Risk

### JPMorgan US7089207B1

- **Covers**: PD from observable equity market data for listed/public companies
- **Infringement Risk**: **None**
- **Distinction**: LIP's Tiered PD framework extends beyond JPMorgan to address:
  - Private companies (80%+ of mid-market) via Damodaran industry-beta proxy
  - Thin-file counterparties via Altman Z'-score
  - JPMorgan's structural model doesn't cover these cases
- **Claim Language to Avoid**: Don't claim "probability of default" generically — claim "tiered probability assessment using [specific models for specific counterpart types]"

### Bottomline US11532040B2

- **Covers**: Aggregate cash flow forecasting for liquidity management
- **Infringement Risk**: **None**
- **Distinction**: Bottomline triggers on **forecasted cash shortfall**. LIP triggers on **specific in-flight payment failure**:
  - Real-time detection vs. historical pattern prediction
  - UETR-keyed correlation enables intervention before cash shortfall occurs
- **Competitive Insight**: Bottomline is complementary (enables faster settlement), not competitive.

### Akamai Joint-Enterprise Doctrine

- **Risk**: Distributed infringement vectors — if a single entity implements all components, Akamai doctrine could apply
- **Mitigation**: LIP's **three-entity architecture** (MLO/MIPLO/ELO) explicitly divides components across independent legal entities:
  - MLO holds C1-C2 license
  - MIPLO holds C3 license
  - ELO holds C7 license
  - Each license agreement defines separate IP boundaries
- **Patent Claim Strategy**: File continuation claims that require all three entities working together

### SWIFT gpi

- **Status**: Complementary — enables UETR tracking that LIP leverages
- **Risk**: None — SWIFT has no patent on ML-based failure classification

### Ripple/XRP

- **Status**: Alternative payment rails — doesn't address SWIFT failures
- **Risk**: None — different problem domain

---

## 5. Cross-Component Synergies

### Strongest Patent Positions — Integrated Inventions

**1. UETR-Keyed Lifecycle Correlation** (Spans C1, C3, C5, C9, All Components)
   - Uses UETR as persistent identifier across failure detection, pricing, settlement monitoring, and settlement prediction
   - **Novelty**: End-to-end tracking from payment failure detection to settlement confirmation
   - **Claim Language**: "System for automated liquidity bridging with settlement-confirmed repayment, wherein the persistent transaction identifier is correlated across payment failure prediction, credit risk assessment, and payment settlement monitoring components"
   - **Strength**: Competitors cannot easily design around integrated UETR correlation without breaking entire system

**2. Three-Entity Commercial Architecture** (Spans All Components)
   - MLO monitors → MIPLO prices → ELO executes with API boundaries
   - **Novelty**: Novel distributed deployment model for payment intelligence
   - **Claim Language**: "Method for distributed payment intelligence platform, comprising: a first entity monitoring payment network events and providing failure classification output; a second entity providing credit risk assessment and bridge loan pricing based on said classification; a third entity executing bridge loans with said pricing, wherein each entity operates under a separate license agreement with defined intellectual property boundaries"
   - **Strength**: Closes Akamai divided infringement vector

**3. Dual-Stream Adversarial Cancellation Detection** (Spans C4, C5, C7)
   - Primary settlement stream + secondary cancellation monitoring with ML classifier
   - **Novelty**: Parallel hard block architecture distinguishing legitimate cancellations from adversarial attacks
   - **Claim Language**: "Method for detecting adversarial payment cancellations, comprising: monitoring primary payment settlement stream for payment confirmation signals; monitoring secondary payment cancellation stream for cancellation events; applying machine learning classifier to distinguish between legitimate payment cancellations and adversarial attempts; wherein said classifier is trained to identify contextual negation patterns"
   - **Strength**: Security interest preservation — prevents automated systems from being gamed

**4. F2-Optimal Calibration Method** (Spans C1, C2, C7)
   - τ* = 0.110 threshold optimized for payment failure economics
   - Integrates failure prediction with risk assessment and execution decision
   - **Novelty**: Asymmetric cost optimization for false negative minimization
   - **Claim Language**: "Method for calibrating payment failure prediction threshold, comprising: obtaining training dataset of payment failures; computing asymmetric cost ratio for false negatives versus false positives; training machine learning model with said asymmetric cost ratio; applying isotonic regression to calibrate model outputs to produce probability of payment failure threshold"
   - **Strength**: Business-critical optimization — directly addresses economics of false negatives

**5. AML-by-Design Entity Hashing** (Spans C6, C8, All Components)
   - Entity hashing with 365-day salt rotation and per-licensee caps
   - **Novelty**: GDPR-compliant AML approach
   - **Claim Language**: "Method for compliance screening using entity identifier hashing, comprising: generating cryptographic hash of entity identifier using per-licensee salt; rotating said salt on predetermined schedule; applying AML velocity limits defined in license token; wherein rotation and limits prevent correlation of AML detection patterns across licensees"
   - **Strength**: Privacy-by-design enables compliance without data sharing

---

## 6. Patent Filing Recommendations

### Primary Claims — v5.2 Provisional (Already Filed)

**Claim 1 — Core Method**: Real-time payment failure detection with automated liquidity bridging
- **Status**: Already filed
- **Claim Language**: "System for detecting payment failures in real-time payment network data, wherein said detection uses graph neural network combining bank identifier network topology with transaction features, and generates probability of payment failure within sub-100 milliseconds"

**Claim 5 — Auto-Repayment Loop**: Settlement-confirmed collection using UETR correlation
- **Status**: Already filed
- **Claim Language**: "System for automated loan repayment, comprising: monitoring settlement confirmation events for bridge loans; correlating said settlement confirmation events with original payment unique transaction identifiers; wherein correlation triggers automatic repayment transaction"

**Claim 2 — System**: Three-entity distributed architecture with API boundaries
- **Status**: Already filed
- **Claim Language**: "Distributed payment intelligence platform, comprising: a first entity monitoring payment network events and providing failure classification output; a second entity providing credit risk assessment and bridge loan pricing based on said classification; a third entity executing bridge loans with said pricing, wherein each entity operates under a separate license agreement with defined intellectual property boundaries"

### Dependent Claims — Implementation-Specific

**Claim D1 — τ* Calibration**: Novel threshold optimization approach
- **Status**: Ready for dependent claim filing
- **Technical Novelty**: Asymmetric cost optimization (α=0.7) for payment failure economics is novel in the lending domain

**Claim D2 — Three-Tier PD Extension**: Private company risk assessment
- **Status**: Ready for dependent claim filing
- **Technical Novelty**: Extending JPMorgan's structural model to private companies via Damodaran industry-beta proxy and Altman Z'-score

**Claim D3 — Dual-Stream Adversarial Detection**
- **Status**: Ready for dependent claim filing
- **Technical Novelty**: Parallel hard block architecture with ML classifier for distinguishing legitimate vs. adversarial cancellations

**Claim D4 — AML Entity Hashing with Salt Rotation**
- **Status**: Ready for dependent claim filing
- **Technical Novelty**: GDPR-compliant AML approach using per-licensee salt rotation

**Claim D5 — Pre-Emptive Liquidity**: Expectation graph-based intervention
- **Status**: **SPEC ONLY — DO NOT FILE YET**
- **Note**: Wait until first pilot demonstrates value and expectation graphs are operational

**Claim D6 — Tokenized Receivables Pool**
- **Status**: **SPEC ONLY — DO NOT FILE YET**
- **Note**: Market infrastructure and regulatory frameworks not matured

**Claim D7 — CBDC Integration**
- **Status**: **SPEC ONLY — DO NOT FILE YET**
- **Note**: File when major CBDC standard published (ISO 20022 v2.1+)

**Claim D8 — Autonomous Treasury Agent**
- **Status**: **SPEC ONLY — DO NOT FILE YET**
- **Note**: File after production validation and regulatory clarity

### Continuation Patents — File Before Commercial Deployment

**P3 — Multi-Entity Architecture**: File before any bank license or platform SaaS announcement
- **Risk**: If filed after deployment, independent invention doctrine risk increases

**P4 — Pre-Emptive Bridging**: File when first pilot launches and expectation graphs are operational
- **Risk**: Demonstrates commercial viability

**P5 — Supply Chain Cascade**: File when cascade detection is integrated into production pipeline
- **Risk**: Requires real supply chain data

**P6 — CBDC Integration**: File when major CBDC standard is published
- **Risk**: Future-proofing for next-generation payments

### Legal Strategy Notes

**Alice Compliance (UK):** Focus on infrastructure improvements — latency, protocol interoperability, UETR correlation — these strengthen non-obviousness

**US Patent Prosecution:**
- Avoid claiming "probability of default" generically
- Use tiered language: "assessing default probability for [specific counterparty type] using [specific model]"
- Emphasize integration and system architecture over single algorithms
- Claim business-critical improvements: sub-100ms latency, real-time detection, end-to-end correlation

**Trade Secrets to Maintain:**
- Feature engineering methodology for BIC neighbor aggregation
- Calibration parameters (τ*, α=0.7, isotonic regression settings)
- Training dataset composition and preparation techniques
- AML entity hashing salt rotation schedule
- Private company PD proxy values and industry-beta data sources

---

## Appendix: Code References

| Patentable Component | Key Files | Lines of Code |
|---------------------|-----------|---------------|
| C1 Ensemble Architecture | `lip/c1_failure_classifier/graph.py`, `lip/c1_failure_classifier/tabular.py`, `lip/c1_failure_classifier/ensemble.py` | ~2,000 LOC |
| C1 Calibration (τ*) | `lip/c1_failure_classifier/calibration.py` | ~300 LOC |
| C2 Three-Tier PD | `lip/c2_pd_model/pricing.py`, `lip/c2_pd_model/models.py` | ~500 LOC |
| C3 Settlement FSM | `lip/c3_settlement_monitor/fsm.py`, `lip/c3_settlement_monitor/receiver.py` | ~800 LOC |
| C4 Dispute Prefilter | `lip/c4_dispute_classifier/prefilter.py` | ~200 LOC |
| C4 LLM Integration | `lip/c4_dispute_classifier/model.py` | ~150 LOC |
| C5 Event Normalization | `lip/c5_streaming/parser.py` | ~600 LOC |
| C5 Stress Detector | `lip/c5_streaming/stress.py` | ~200 LOC |
| C6 Entity Hashing | `lip/c6_velocity/entity_hash.py` | ~150 LOC |
| C6 AML Screening | `lip/c6_velocity/sanctions.py` | ~200 LOC |
| C7 Decision Gates | `lip/c7_execution/agent.py` | ~400 LOC |
| C7 Immutable Logging | `lip/c7_execution/audit.py` | ~100 LOC |
| C8 Token Validation | `lip/c8_license/validator.py` | ~100 LOC |
| C9 Settlement Prediction | `lip/c9_settlement_predictor/cox.py` | ~200 LOC |
| P5 Cascade Engine | `lip/p5_cascade_engine/graph.py` | ~300 LOC |

**Total Estimated Codebase**: ~8,000 LOC across 8 core modules

---

**END OF DOCUMENT**
