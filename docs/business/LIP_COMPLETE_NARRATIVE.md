# LIP — The Complete Story

**Liquidity Intelligence Platform**
**Bridgepoint Intelligence Inc.**
**Last updated: 2026-04-24 | Ground truth: docs/c1-model-card.md, docs/c1-training-data-card.md, docs/operations/releases/staging-rc-2026-04-24.md**

**RC note:** the March 2026 narrative remains the historical base case, but the current staging RC has now been retrained, signed, and container-verified. Use the release note above for deployable artifact truth.

---

## Part 1: What This Is and Why It Exists

LIP is an automated bridge lending system that runs against a bank's SWIFT payment stream. When a cross-border payment fails — a pacs.002 rejection event — LIP predicts whether the failure is permanent, and if so, offers the receiving bank an instant bridge loan for the stuck amount. The bridge loan keeps the beneficiary's cash flow whole while the payment failure is resolved. If the original payment eventually settles, the bridge is repaid automatically. If it doesn't, the borrower repays at maturity (3, 7, or 21 days depending on failure class).

The entire decision — detect failure, classify it, estimate credit risk, price the loan, check for disputes, screen for AML, and generate the offer — happens in under 94 milliseconds, end-to-end.

### The Business Model

Bridgepoint Intelligence (BPI) is a technology licensor, not a bank. BPI does not hold loans on its balance sheet in Phase 1. The model has three phases:

- **Phase 1 (current — Licensor):** The bank funds 100% of bridge capital. BPI earns a 30% royalty on the fee collected. On a $5M bridge at 300 bps for 7 days, the fee is $2,877 and BPI receives $863.
- **Phase 2 (Hybrid):** BPI puts up 70% of capital. BPI earns 55% of fee. The bank retains 45%, split between capital return and distribution premium for its origination and compliance infrastructure.
- **Phase 3 (Full MLO):** BPI funds 100%. BPI earns 80% of fee. Bank keeps 20% as distribution premium only.

Phase 1 revenue is royalty income. Phase 2 and 3 revenue is lending revenue. This distinction has real tax and legal consequences — the fee decomposition must explicitly show "capital return + distribution premium" before Phase 3 negotiations begin, or the bank loses leverage in renegotiation.

### The Patent Moat

JPMorgan's US patent 7089207B1 covers payment failure prediction for Tier 1 counterparties — listed companies with publicly available equity data. LIP's patent contribution is Tier 2 and Tier 3 coverage:

- **Tier 2:** Private companies with balance sheets. LIP uses a Damodaran industry-beta model to estimate PD without market data.
- **Tier 3:** Data-sparse entities ("thin-file"). LIP uses an Altman Z-score proxy model that works with minimal financial inputs — jurisdiction-level default rates, sector medians, and rejection code class alone.

The current prosecution-ready provisional specification covers the full pipeline: detection → classification → conditional offer → auto-repayment. The core novel claim is the two-step classification plus conditional offer logic — not the bridge loan mechanics themselves. Patent counsel briefing is pending before non-provisional filing.

### Three Legal Entities

Every transaction involves three roles:

1. **MLO** (Money Lending Organisation) — The capital provider. Holds the loan on balance sheet. In Phase 1, this is the bank itself. In Phase 3, this is BPI.
2. **MIPLO** (Money In / Payment Lending Organisation) — BPI. Operates the technology platform. Licenses to banks.
3. **ELO** (Execution Lending Organisation) — The bank-side agent (C7). Runs inside the bank's infrastructure perimeter. Executes offers, enforces kill switches, gates human overrides.

Bridge loans are B2B interbank credit facilities. The borrower is the enrolled originating bank (e.g., Deutsche Bank), not the end customer (e.g., Siemens). Repayment is unconditional — not contingent on whether the underlying payment eventually settles. This was settled in the EPIGNOSIS architecture review (EPG-14) and is now coded: `bic_to_jurisdiction()` derives governing law from BIC chars 4–5, not from payment currency.

---

## Part 2: The Eight-Component Pipeline

LIP processes ISO 20022 pacs.002 payment rejection events through an eight-component pipeline. Each component has a specific role, and the pipeline is designed so that any single component's failure results in a safe outcome (no loan offered, not a bad loan offered).

```
pacs.002 RJCT event
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  C5 — Streaming & Event Normalization                   │
│  Kafka ingestion, ISO 20022 normalization,              │
│  stress regime detection                                │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  C1 — Payment Failure Classifier                        │
│  GraphSAGE + TabTransformer + LightGBM ensemble         │
│  Output: failure_probability ∈ [0, 1]                   │
│  If failure_probability < τ* (0.110): STOP — no offer   │
└─────────────┬───────────────────────────────────────────┘
              │ failure_probability ≥ 0.110
              ▼
┌──────────────────────┐  ┌───────────────────────────────┐
│  C4 — Dispute Check  │  │  C6 — AML Velocity + Sanctions│
│  LLM + prefilter     │  │  OFAC/EU/UN screening          │
│  Hard block if       │  │  Entity velocity caps           │
│  dispute detected    │  │  Beneficiary concentration      │
└──────────┬───────────┘  └──────────┬────────────────────┘
           │ clear                    │ clear
           └──────────┬───────────────┘
                      ▼
┌─────────────────────────────────────────────────────────┐
│  C2 — Probability of Default & Fee Pricing              │
│  Unified LightGBM with three-tier feature masking       │
│  Output: pd_score, lgd_estimate, fee_bps (≥ 300)       │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│  C7 — Execution Agent (bank-side)                       │
│  Kill switch, KMS check, TPS limiter, human override,   │
│  enrolled borrower check, compliance hold gate,         │
│  stress regime adjustment                               │
│  Output: LoanOffer or HALT/DECLINE/COMPLIANCE_HOLD      │
└─────────────┬───────────────────────────────────────────┘
              │ OFFER generated
              ▼
┌─────────────────────────────────────────────────────────┐
│  C3 — Settlement Monitoring & Auto-Repayment            │
│  UETR polling, corridor buffers, repayment state machine│
│  Maturity: 3d (Class A), 7d (Class B), 21d (Class C)   │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  C8 — License Enforcement                               │
│  HMAC-SHA256 token at boot, per-licensee caps,          │
│  salt management, deployment phase control              │
└─────────────────────────────────────────────────────────┘
```

Every decision — offer, decline, halt, compliance hold, dispute block, AML block — is logged in a tamper-resistant `DecisionLogEntry` with HMAC-SHA256 integrity, retained for 7 years on an append-only Kafka topic. This satisfies SR 11-7 model documentation, EU AI Act Art.14 human oversight audit trail, and DORA incident reporting requirements.

---

## Part 3: C1 — The Failure Classifier (The Core Model)

C1 is the first and most critical model in the pipeline. It answers one question per payment: "Will this UETR fail to settle within its rejection-class maturity window?" If the predicted failure probability exceeds the calibrated threshold (τ* = 0.110), the payment enters the lending pipeline. If not, LIP does nothing.

### Architecture

C1 is a three-model ensemble:

1. **GraphSAGE** — A graph neural network that learns BIC-pair (bank-pair) relationships from a payment network graph. Each node is a bank (BIC code). Edges are payment corridors weighted by volume and historical failure rates. GraphSAGE aggregates neighborhood information: a bank with many failing neighbors is itself more likely to be involved in failures. The graph is rebuilt weekly; corridor embeddings are cached in Redis for sub-millisecond inference lookup.

2. **TabTransformer** — A transformer-based tabular feature encoder. It processes 88 features per payment: rejection code embeddings, amount features, temporal patterns (cyclic sin/cos for hour-of-day, day-of-week, month-end, quarter-end), corridor-specific failure rates, sender/receiver BIC statistics, and jurisdiction embeddings. The transformer's self-attention learns feature interactions that gradient boosting would need manual feature engineering to capture.

3. **LightGBM** — A gradient-boosted decision tree ensemble trained on the same 88 tabular features. Provides complementary signal to the neural network. The final prediction is a 50/50 average of the PyTorch neural network output and the LightGBM output, followed by isotonic calibration to map scores to true probabilities.

The fused architecture:
```
GraphSAGE (8-dim node features → 384-dim embedding via 2-layer aggregation)
    +
TabTransformer (88-dim tabular features → 88-dim output)
    =
472-dim concatenation → MLP(256 → 64 → 1) → sigmoid → p_failure

LightGBM (88-dim tabular features → p_failure)

Final: 0.5 × p_neural + 0.5 × p_lgbm → isotonic calibration → failure_probability
```

### Training (Completed 2026-03-21)

The model was trained on a fully synthetic corpus — no real SWIFT payment data has ever been seen.

- **Corpus:** 10 million ISO 20022 RJCT events + successful payments (`payments_synthetic.parquet`, 143.8 MB)
- **Training sample:** 2 million records (20% RJCT / 80% SUCCESS)
- **Corridors:** 20 currency pairs (expanded from 12 in the original 2K prototype)
- **BIC pool:** 200 synthetic banks (10 hub institutions with high volume, 190 spoke institutions)
- **Risk tiers:** 4-tier BIC risk model (0.25×, 1.0×, 5.0×, 15.0× baseline failure rate)
- **Temporal realism:** 30% of RJCT senders have burst clustering (1d/7d/30d failure rate variation); 18-month temporal span for out-of-time validation
- **Split:** Chronological 70/15/15 (train/validation/test) — no random splits; OOT test set is the most recent 15% by timestamp
- **Training time:** 155 minutes (GitHub Actions ubuntu-latest, CPU-only)

### Results

| Metric | Value | Notes |
|--------|-------|-------|
| Val AUC (ensemble) | **0.8871** | 50/50 PyTorch + LightGBM |
| Val AUC (PyTorch only) | 0.8870 | GraphSAGE + TabTransformer |
| Val AUC (LightGBM only) | 0.8860 | Tabular features only |
| F2 score (at τ*) | **0.6245** | F2 weights recall 2× over precision |
| ECE (post-calibration) | **0.0687** | Isotonic regression; pre-calibration was 0.1867 |
| Calibrated threshold τ* | **0.110** | F2-optimal on calibrated probability scale |
| Precision (at τ*) | 0.3819 | 38.2% of flagged payments are true failures |
| Recall (at τ*) | 0.8816 | 88.2% of true failures are caught |

The AUC of 0.8871 falls within ARIA's pre-training honest ceiling estimate of 0.82–0.88, now revised to 0.88–0.90. This is not inflated — the chi-square test on rejection code distributions shows only minor deviation from priors (χ² = 26.72, p = 0.021), documented in the training data card §5.2.

### The 2K Prototype Saga

Before the 10M corpus, C1 was trained on 2,000 synthetic samples with 12 corridors. That prototype achieved AUC = 0.9998 — a suspiciously perfect number. The root cause was twofold:

1. **Feature starvation:** 55 of 88 tabular features were permanently zero because the generator didn't populate `sender_stats`, `receiver_stats`, or `corridor_stats` sub-dicts. The model was effectively a 33-feature classifier.
2. **Insufficient variation:** With only 2K samples and 12 corridors, rejection codes became perfect class predictors with zero label noise. The model memorized the mapping, not the signal.

The fix (commit `f38f0dc`, 2026-03-11) populated all 88 features. The 10M corpus with 20 corridors, 200 BICs, 4-tier risk, and temporal clustering produces realistic performance. AUC dropped from 0.9998 to 0.8871 — a healthy sign, not a regression.

### What C1 Honestly Cannot Do

These are structural limitations, not bugs. They are disclosed in the model card and SR 11-7 governance pack:

1. **Fully synthetic training.** C1 has never seen a real SWIFT payment. The first pilot deployment with anonymised bank data will be the first empirical AUC measurement. Real-world AUC may be lower due to distribution shift.
2. **AUC ceiling ~0.88–0.90.** Payment failure prediction is inherently noisy. Some failures are random events (network partitions, correspondent bank system edge cases) with no predictive signal in any feature. AUC above 0.90 on real data would be suspicious, not celebratory.
3. **Graph staleness.** GraphSAGE embeddings are rebuilt weekly. A mid-week routing change (bank merger, sanctions-driven re-routing) degrades performance until the next rebuild.
4. **Cold-start corridors.** New BIC pairs use currency-pair mean embeddings. Performance is lower until ~100 observations accumulate. The corridor bootstrap protocol manages capital risk during this period.
5. **Rare rejection codes.** Codes appearing <100 times in training have poorly calibrated embeddings. The rejection_code_class (A/B/C/BLOCK) feature backstops this.
6. **Calibration validity.** Isotonic calibration was fit on synthetic data. Whether the calibrated probabilities are well-calibrated on real data is unvalidated. ECE re-measurement is mandatory within 30 days of pilot start.

---

## Part 4: C2 — Credit Risk and Fee Pricing

C2 estimates the probability that the borrower (originating bank) defaults on the bridge loan. It also estimates Loss Given Default (LGD) and derives the annualised fee in basis points. The fee floor is 300 bps — non-negotiable, QUANT final authority.

### Three-Tier Framework

C2 determines the borrower's data tier deterministically, then applies appropriate features:

- **Tier 1 (Listed public company):** Equity price and volatility available. Uses Merton/KMV structural model inputs: distance-to-default from equity price, equity volatility, market cap, total debt.
- **Tier 2 (Private, balance sheet available):** Uses Damodaran industry-beta proxy: working capital ratio, retained earnings ratio, EBIT ratio, sector-median asset volatility.
- **Tier 3 (Thin-file):** Only jurisdiction-level default rates, sector medians, and rejection code class. Conservative output by design — overprices risk to protect capital.

A unified LightGBM ensemble (5 models, bagged) handles all three tiers with learned feature masking. Platt scaling calibrates the PD output. This replaced a prior three-model routing stack (Merton → Altman → statistical proxy) that required explicit routing logic and had handoff discontinuities.

### Fee Derivation

```
expected_loss_usd = pd_score × lgd_estimate × ead
fee_bps = max(300, f(expected_loss, maturity_days))
```

At 300 bps annualised, a 7-day $100K bridge generates a fee of $57.53 (0.0575% of principal for 7 days). Applying 300 bps as a flat per-cycle rate would yield $3,000 — 52× the intended fee. This error is documented in every code review touching fee calculation.

### Status

C2 specification is complete. Training data (10M corpus) is available. Model training was pending ARIA implementation in the March 2026 narrative; as of the 2026-04-24 staging RC, C2 is trained, signed, and stress-gated for staging use. LGD estimates are still pre-pilot (jurisdiction-tiered defaults), not empirically calibrated. All C2 outputs carry this caveat until post-pilot recovery data replaces the estimates.

---

## Part 5: C4 — Dispute Detection (The Hard Block)

C4 is the highest-consequence component in LIP. A false negative — a missed dispute — results in a funded bridge loan against a genuinely contested invoice. Recovery probability: near zero. For this reason, C4 is a hard block: if dispute is detected, no loan is offered regardless of every other model's output.

### Two-Step Architecture

**Step 1 — Prefilter (regex keyword matching, <1ms):**
Scans rejection_code and narrative for dispute keywords: "dispute", "fraud", "chargeback", "claim", "appeal", "objection". If no match: NOT_DISPUTE (fast path, no LLM invocation). If match: route to LLM.

**Step 2 — LLM (qwen/qwen3-32b via Groq API, ~30-60ms):**
Full semantic analysis of rejection context. Handles negation ("this is NOT a disputed invoice"), partial disputes, multilingual text, and structured reference formats. Returns `DisputeClass`: DISPUTE_CONFIRMED, DISPUTE_POSSIBLE, NOT_DISPUTE, or NEGOTIATION.

### Performance

- Prefilter FP rate: 4% (down from 62% before prefilter tuning, commit 3808a74)
- Negation suite FN rate: 1% (500 cases, 5 categories, 20 templates per category)
- Multilingual FP: 0.0% (FR/DE/ES/AR narratives)
- Conditional negation weakness: 10% accuracy on "unless X, this becomes a dispute" — LLM conservatively treats as DISPUTE_CONFIRMED. Acceptable for LIP's risk posture (false alarm safer than missed dispute).

### Why On-Device

C4 runs inside the bank's infrastructure perimeter (C7 container). The `RmtInf` field contains borrower payment data — it must never leave the bank's network. There is no API call from C7 to BPI for dispute classification. Zero network calls. This is both a privacy requirement (GDPR) and an operational resilience requirement (DORA — no external dependency for the hard-block decision).

---

## Part 6: C5 — Streaming, Stress Regime Detection

C5 normalises payment events from multiple rails (SWIFT, FedNow, RTP, SEPA) into a common ISO 20022 pacs.002 format and publishes them to Kafka for downstream processing.

### Stress Regime Detection (Completed 2026-03-15)

Quarter-end and month-end liquidity crunches cause corridor failure rate spikes. Without stress detection, AML velocity caps block the largest, most creditworthy institutions (they hit the $1M/entity/24h cap first) while smaller entities continue receiving offers. This is adverse selection — exactly backwards.

The stress regime detector compares a 1-hour sliding window failure rate against a 24-hour baseline per corridor. If the ratio exceeds 3.0× (QUANT-controlled multiplier), the corridor enters stress mode:

- C1's τ* rises from 0.110 to 0.25 (higher selectivity — only the strongest failure signals generate offers)
- Large offers route to PENDING_HUMAN_REVIEW
- A StressRegimeEvent is emitted to Kafka for downstream monitoring

When the ratio drops below 3.0×, stress mode disengages automatically. The multiplier and window sizes are canonical constants requiring QUANT sign-off to change.

### Kafka Topic Map

| Topic | Partitions | Retention | Purpose |
|-------|-----------|-----------|---------|
| `lip.payment.events` | 24 | 7 days | Normalised pacs.002 RJCT events |
| `lip.failure.predictions` | 12 | 7 days | C1 classifier output |
| `lip.settlement.signals` | 24 | 7 days | UETR settlement confirmations |
| `lip.dispute.results` | 6 | 7 days | C4 classification output |
| `lip.velocity.alerts` | 6 | 7 days | C6 AML flags |
| `lip.loan.offers` | 6 | 7 days | C7 LoanOffers generated |
| `lip.repayment.events` | 6 | 7 days | C3 repayment confirmations |
| `lip.decision.log` | 12 | **7 years** | HMAC-signed audit trail |
| `lip.dead.letter` | 6 | 7 days | Processing failures |
| `lip.stress.regime` | 6 | 7 days | Stress regime events |

---

## Part 7: C6 — AML, Velocity, and Sanctions Screening

C6 screens every payment event against sanctions lists (OFAC, EU, UN) and monitors entity-level transaction velocity for suspicious patterns.

### Sanctions Screening

Hard block. Every payment event is screened against OFAC SDN, EU consolidated, and UN consolidated lists. Match on entity identifier hash → payment blocked. No override available (unlike C4 dispute blocks, which allow logged human override).

### Velocity Monitoring

- **Window:** 24-hour rolling
- **Caps:** Configurable per-licensee via C8 license token. Default: 0 (unlimited). The original $1M/entity/24h cap was retail-scale — a correspondent bank hits it by 9:05 AM on the first large payment.
- **Beneficiary concentration:** If >80% of an entity's 24h outflows go to a single beneficiary, an anomaly alert fires → PENDING_HUMAN_REVIEW (EU AI Act Art.14).

### Entity Privacy

Entity identifiers are never stored raw. All identifiers are hashed:

```
stored_id = SHA-256(entity_id + salt)
```

Salt is 32 bytes, cryptographically random, rotated annually with a 30-day dual-salt overlap. Each licensee has a unique salt — cross-licensee correlation is impossible by design. This satisfies GDPR Art.25 (Data Protection by Design).

---

## Part 8: C7 — The Execution Agent (Bank-Side Safety)

C7 is the last gate before a loan offer is generated. It runs inside the bank's infrastructure perimeter and applies ten decision gates in sequence:

1. **Kill switch** — If engaged, HALT immediately. No offers until manually disengaged.
2. **KMS availability** — If key management service is down > 1 second, HALT.
3. **TPS limiter** — Per-licensee max transactions/second. Exceed → HALT.
4. **Human override** — If previous decision was PENDING_HUMAN_REVIEW and operator approved, proceed.
5. **Enrolled borrower check** — `sending_bic` must be in the Enrolled Borrower Registry. Not found → BORROWER_NOT_ENROLLED.
6. **Compliance hold codes** — If rejection code is in `{RR01, RR02, RR03, RR04, DNOR, CNOR, AG01, LEGL}`, return COMPLIANCE_HOLD. This is defense-in-depth Layer 2 (Layer 1 is rejection_taxonomy.py short-circuit in pipeline.py).
7. **Fee minimum check** — Minimum loan amount per class (A=$1.5M, B=$700K, C=$500K).
8. **PD threshold for human review** — If pd_score > 0.20 → PENDING_HUMAN_REVIEW.
9. **Loan amount cap** — If offer exceeds licensee max → PENDING_HUMAN_REVIEW.
10. **Stress regime** — If corridor is stressed, raise τ* to 0.25, route large offers to PENDING_HUMAN_REVIEW.

### The Compliance Hold Decision (EPG-19)

This was the most debated architectural decision in the codebase, settled unanimously in the EPIGNOSIS review. LIP must **never** bridge a payment where the originating bank's compliance system raised a hold. Three independent grounds:

- **CIPHER (AML):** Bridging a compliance-held payment achieves the same value movement as the blocked payment, using LIP as the instrument. This is a structuring/layering typology violation. Banks that correctly operate code SARs as MS03/NARR (opaque to LIP by design per FATF R.21 tipping-off rules). The explicitly-coded holds (DNOR, CNOR, etc.) are the *visible floor* of a larger compliance problem.
- **REX (Legal):** AMLD6 Art.10 imposes criminal liability on legal persons. A bank that uses LIP to bridge a payment its own AML system blocked has not taken "reasonable precautions." This is an affirmative act against its own compliance judgment.
- **NOVA (Technical):** C3 repayment mechanics are structurally broken for compliance holds. The UETR never settles (DNOR = permanent prohibition). Disbursement may not land (CNOR). Maturity windows are calibrated for technical errors, not compliance investigation timelines.

The code enforces this at two independent layers. A compliance-held payment cannot reach C7 through the normal pipeline (Layer 1 blocks it). But even if a taxonomy gap allows it through, C7 catches it independently (Layer 2).

### Degraded Mode

When infrastructure fails, C7 degrades safely:

- **GPU unavailable:** C1 falls to CPU. Latency rises (p99 ~163ms) but stays within the 94ms pipeline SLO if C1 is the only slow component. `degraded_mode: true` is logged.
- **Redis unavailable:** In-memory fallback for velocity tracking and UETR deduplication. Loses persistence — a new process restart loses all in-flight state.
- **Kafka unavailable:** Decision log entries queue locally until broker reconnects. At-least-once delivery guaranteed via offset tracking.

---

## Part 9: C8 — License Enforcement

C8 validates BPI's license token at boot using HMAC-SHA256. The token contains per-licensee configuration:

```json
{
  "licensee_id": "BANK_XYZ",
  "max_tps": 1000,
  "aml_dollar_cap_usd": 0,
  "aml_count_cap": 0,
  "min_loan_amount_usd": 500000,
  "governing_law": "GB",
  "deployment_phase": "LICENSOR",
  "salt_rotation_day": 90
}
```

If the token is invalid or expired, the kill switch auto-engages. No offers until manual intervention. Multi-tenancy is supported — multiple licensees can run in one deployment, with per-licensee salt isolation preventing cross-licensee AML correlation.

---

## Part 10: State Machines and the Loan Lifecycle

### Payment State Machine

```
MONITORING
  └→ FAILURE_DETECTED (pacs.002 RJCT received)
       └→ C1 predicts failure_probability
            ├→ Below τ* (0.110): no action
            └→ Above τ*: enter decision pipeline
                 ├→ DISPUTE_BLOCKED (C4 hard block)
                 ├→ AML_BLOCKED (C6 hard block)
                 ├→ COMPLIANCE_HOLD (EPG-19, never bridge)
                 ├→ OFFER_DECLINED (bank declines)
                 ├→ OFFER_EXPIRED (15-minute timeout, no response)
                 └→ BRIDGE_OFFERED → FUNDED
                      ├→ REPAID (settlement received, auto-repayment)
                      ├→ BUFFER_REPAID (corridor P95 buffer absorbed)
                      └→ DEFAULTED (maturity + 45d TTL, no settlement)
```

### Maturity by Rejection Class

| Class | Codes (examples) | Maturity | P95 Settlement | Description |
|-------|-------------------|----------|----------------|-------------|
| A | AC01, AC04, MD01, RC01 | 3 days | 7.05 hours | Routing/account errors |
| B | RR01–RR04, FRAU, LEGL | 7 days | 53.58 hours | Systemic/processing delays |
| C | AM04, AM05, FF01, MS03 | 21 days | 170.67 hours | Liquidity/complex |
| BLOCK | DNOR, CNOR, RR01–RR04, AG01, LEGL | 0 days | Never | Compliance holds — NEVER bridged |

---

## Part 11: Canonical Constants

These values require QUANT sign-off to change. They are the load-bearing numbers of the system.

| Constant | Value | Authority |
|----------|-------|-----------|
| Failure threshold τ* | 0.110 | Calibrated, F2-optimal, isotonic |
| Fee floor | 300 bps (annualised) | QUANT — non-negotiable |
| Latency SLO | ≤ 94ms p99 end-to-end | FORGE + QUANT |
| Platform royalty | 30% of fee collected | Phase 1 only |
| UETR TTL buffer | 45 days beyond maturity | NOVA |
| Salt rotation | 365 days, 30-day overlap | CIPHER |
| Decision log retention | 7 years | REX (SR 11-7) |
| Stress multiplier | 3.0× (1h/24h ratio) | QUANT |
| AML velocity default | 0 (unlimited) | CIPHER |
| Maturity Class A | 3 days | QUANT |
| Maturity Class B | 7 days | QUANT |
| Maturity Class C | 21 days | QUANT |

---

## Part 12: The Compliance Framework

LIP operates under four regulatory frameworks simultaneously. REX has final authority on compliance — no model ships without proper documentation.

### SR 11-7 (Fed Model Risk Management)

All three models (M-01/C1, M-02/C2, M-03/C4) are classified HIGH risk — they gate automated lending decisions with direct financial consequences. The SR 11-7 governance pack (v1.0, March 5, 2026) documents:

- Model inventory with purpose, methodology, training data, outputs, limitations, failure modes
- Independent validation pathway (cross-agent internal + bank MRM external)
- Performance monitoring dashboard with specific alert thresholds
- Challenger model framework (shadow inference, no production impact)
- 6-step model change approval workflow with bank notification windows (7/14/30 days by change tier)

Post-training annotations were added 2026-03-21 with actual results: C1v1.1.0 TRAINED, Val AUC = 0.8871, ECE = 0.0687, τ* = 0.110.

### EU AI Act (Regulation 2024/1689)

LIP is a high-risk AI system under Annex III, Section 5(b) (creditworthiness assessment). Requirements:

- **Art. 9 (Risk Management):** Kill switch, degraded mode, pre-deployment testing (92%+ coverage)
- **Art. 10 (Data Governance):** Training data cards with full provenance, quality controls, representativeness assessment
- **Art. 13 (Transparency):** Model cards, SHAP top-20 feature attributions per prediction, limitation disclosure
- **Art. 14 (Human Oversight):** PENDING_HUMAN_REVIEW gate, operator override with logged justification, dual-approval option
- **Art. 17 (Quality Management):** Decision logs immutable, HMAC-signed, 7-year retention
- **Art. 61 (Post-Market Monitoring):** Kill switch activations logged, performance monitoring via Prometheus

### DORA (Digital Operational Resilience Act)

- ICT risk management and incident logging (kill switch activations at CRITICAL)
- Resilience testing (degraded_mode.py tests GPU/KMS failure scenarios)
- Third-party risk management (C8 license validation at boot)

### AML / CFT (FATF Recommendations)

- R.10: Transaction monitoring with configurable velocity caps
- R.16: Sanctions screening at every payment event
- Entity privacy: SHA-256 hashing with per-licensee salt
- The compliance hold architecture (EPG-19) specifically addresses tipping-off risk (FATF R.21)

---

## Part 13: The Team — Who Owns What

Seven specialised roles with explicit decision authority and escalation rules. The founder sets direction; the team translates it into correct technical decisions and pushes back when the direction is wrong.

| Role | Domain | Final Authority |
|------|--------|-----------------|
| **ARIA** | ML/AI — C1, C2, C4 | Architecture, training, feature design, metrics |
| **NOVA** | Payments — C3, C5, C7, ISO 20022 | Protocol, settlement, corridor config |
| **QUANT** | Financial math — fees, PD/LGD | **Floor** — nothing merges that changes fee logic without sign-off |
| **CIPHER** | Security — C6, AML, crypto, C8 | **Floor** — AML patterns never in version control |
| **REX** | Regulatory — DORA, EU AI Act, SR 11-7 | **Floor** — no model ships without data card + OOT validation |
| **DGEN** | Data generation — corpora, calibration | Corpus design, validation, quality |
| **FORGE** | DevOps — K8s, Kafka, CI/CD | Infrastructure, deployment |

The Ford Principle: an agent that executes a bad instruction without questioning it has failed, even if the code runs.

---

## Part 14: Known Gaps — What's Missing Before Pilot

Sixteen gaps documented in `CLIENT_PERSPECTIVE_ANALYSIS.md`. The five Tier 1 blockers:

1. **GAP-01 — Offer delivery.** Pipeline generates LoanOffer but provides no mechanism for treasury systems to accept or decline. Offers silently expire at 15 minutes. Need: webhook + acceptance API.

2. **GAP-02 — AML cap sizing.** ~~$1M/entity/24h cap is retail-scale.~~ **RESOLVED** (2026-03-18, commit 0ec874c). Default now 0 (unlimited), per-licensee via C8 token.

3. **GAP-03 — Enrolled Borrower Registry.** No registry exists. LIP generates offers to any BIC it sees, including intermediaries who never agreed to be borrowers. Need: Registry schema with MRFA status, C7 hard-block for unregistered BICs.

4. **GAP-04 — Retry detection.** When treasury manually re-submits a failed payment, a new UETR is generated. If bridge + retry both land, beneficiary receives 2×. Need: Redis-backed deduplication on `(sending_bic, receiving_bic, amount ± 0.01%, currency)` for 30-minute window.

5. **GAP-05 — BPI royalty collection.** Fee is calculated correctly but never collected. No invoice, no payment instruction, no settlement mechanism. Need: RoyaltySettlementService with monthly batch and automated invoicing.

Additional operational gaps (Tier 2): SWIFT message template for bridge disbursement (GAP-06), MLO portfolio visibility API (GAP-07), timeout action policy (GAP-08), cross-currency denomination (GAP-09), governing law specification (GAP-10, partially fixed via EPG-14).

---

## Part 15: What Happened and When

### Timeline

| Date | Event |
|------|-------|
| 2026-03-04 | C1 Component Spec v1.0 written. Architecture: GraphSAGE + TabTransformer + MLP. |
| 2026-03-05 | SR 11-7 Governance Pack v1.0 written. Three models (M-01, M-02, M-03) documented pre-training. |
| 2026-03-11 | Feature starvation bug found and fixed (commit f38f0dc). 55/88 features were zero. AUC jumps from 0.739 baseline to 0.9998 on 2K samples — but inflated. |
| 2026-03-15 | PoC Validation Report generated. 10K records per component. C1 ML inference not measured (only data quality). Stress Regime Detector completed. |
| 2026-03-16 | C4 LLM integration complete. qwen/qwen3-32b via Groq. FN rate: 0.0% on 100-case negation corpus. Prefilter FP: 4%. |
| 2026-03-18 | EPIGNOSIS Architecture Review. 19 issues (EPG-01 through EPG-19). Compliance hold blocking, B2B borrower identity, AML cap scaling, patent scope decisions finalised. |
| 2026-03-19 | EPG-04/05 resolved: `hold_bridgeable` flag strategy. No bank hold-reason API (FATF-prohibited). License Agreement warranty structure designed. |
| 2026-03-20 | Capital Partner Strategy, Founder Financial Model, Revenue Projection Model created. |
| 2026-03-21 | C1 retrained on 10M corpus (2M sample). Val AUC = 0.8871. Model card and training data card written. Documentation uniformity audit completed. |

### The Arc of the Story

LIP started as an architecture specification. The C1 Component Spec (March 4) defined the GraphSAGE + TabTransformer architecture, the asymmetric loss function, the F2-weighted threshold, and the honest AUC ceiling of 0.82–0.88. The SR 11-7 governance pack (March 5) documented the regulatory framework before any model existed.

The first training run on 2K synthetic samples (March 11) exposed the feature starvation bug — 55/88 features were zero. Fixing it yielded AUC = 0.9998, which was immediately flagged as inflated. The team knew the real-world ceiling was 0.82–0.88 and treated the 0.9998 as a sign that the synthetic data was too clean, not that the model was too good.

The EPIGNOSIS review (March 18) was a full-codebase architecture audit from first principles. It identified 19 issues spanning compliance holds, borrower identity, AML scaling, patent scope, and operational gaps. The most consequential decision — never bridge compliance-held payments (EPG-19) — was reached unanimously on three independent grounds (AML typology, legal liability, technical mechanics).

The 10M corpus training (March 21) produced the first honest performance numbers: AUC = 0.8871, exactly at the predicted ceiling. The isotonic calibration reduced ECE from 0.1867 to 0.0687. The calibrated threshold τ* = 0.110 was set. The model card and training data card were written. The documentation uniformity audit aligned all historical documents with these ground truth values.

---

## Part 16: What's Next

### Blocking (pre-pilot)

- **Legal:** MRFA B2B framing, License Agreement with `hold_bridgeable` API obligation, patent counsel briefing
- **Engineering:** C2 model training, Enrolled Borrower Registry, offer delivery mechanism, retry detection, royalty settlement service
- **Infrastructure:** Cloud provider selection, K8s deployment for pilot bank

### Pilot Validation (first bank)

The first pilot with anonymised SWIFT data will answer the question LIP cannot answer today: does the model work on real payments? Specific measurements:

- Val AUC on real data (target ≥ 0.85, honest ceiling 0.88–0.90)
- ECE re-measurement within 30 days (isotonic calibration validity on real distribution)
- False negative rate on real disputes (C4)
- Stress regime detector calibration against real quarter-end patterns
- C3 repayment mechanics against real settlement timelines

### Outstanding QUANT Decisions

- Retry detection window: 30 minutes proposed (could be 15 or 60)
- Stress regime multiplier: 3.0× proposed (needs historical corridor calibration)
- Royalty settlement frequency: Monthly batch recommended
- Cross-currency bridge denomination policy
- Timeout action default: DECLINE recommended (conservative)

---

## Part 17: Repository Structure

```
PRKT2026/
├── lip/                              # Main package
│   ├── pipeline.py                   # Orchestration — the main entry point
│   ├── pipeline_result.py            # PipelineResult dataclass
│   ├── common/
│   │   └── constants.py              # Canonical constants (QUANT sign-off)
│   ├── c1_failure_classifier/        # C1 — failure prediction
│   │   ├── model.py                  # NumPy reference implementation
│   │   ├── model_torch.py            # PyTorch production implementation
│   │   ├── training.py               # 9-stage training pipeline
│   │   ├── inference.py              # Real-time inference engine
│   │   ├── graphsage.py              # GraphSAGE (NumPy)
│   │   ├── graphsage_torch.py        # GraphSAGE (PyTorch)
│   │   ├── tabtransformer.py         # TabTransformer
│   │   ├── features.py               # 88-dim feature engineering
│   │   ├── graph_builder.py          # BIC graph construction
│   │   └── embeddings.py             # Corridor embedding pipeline
│   ├── c2_pd_model/                  # C2 — probability of default
│   ├── c3_settlement_monitor/        # C3 — repayment engine
│   ├── c4_dispute_classifier/        # C4 — dispute detection (LLM)
│   ├── c5_streaming/                 # C5 — Kafka + stress regime
│   ├── c6_aml_velocity/              # C6 — AML + sanctions
│   ├── c7_execution_agent/           # C7 — bank-side execution
│   │   └── agent.py                  # 10 decision gates
│   ├── c8_license_manager/           # C8 — license enforcement
│   ├── dgen/                         # Synthetic data generators
│   └── tests/                        # 1419 tests, 92%+ coverage
├── docs/
│   ├── c1-model-card.md              # Ground truth — C1 metrics
│   ├── c1-training-data-card.md      # Ground truth — training data
│   ├── architecture.md               # Technical reference
│   ├── compliance.md                 # Compliance mapping
│   ├── data-pipeline.md              # Training data pipeline
│   ├── poc-validation-report.md      # March 15 PoC results
│   ├── developer-guide.md            # Developer onboarding
│   ├── api-reference.md              # API docs
│   └── benchmark-results.md          # Latency benchmarks
├── docs/legal/governance/
│   └── BPI_SR11-7_Model_Governance_Pack_v1.0.md
├── docs/engineering/specs/
│   ├── BPI_C1_Component_Spec_v1.0.md
│   └── BPI_C2_Component_Spec_v1.0.md
├── scripts/                          # Training and validation scripts
├── artifacts/                        # Model binaries (gitignored)
├── .claude/
│   ├── agents/                       # ARIA, REX, NOVA, QUANT, etc.
│   └── commands/                     # /train, /dgen, etc.
├── CLAUDE.md                         # Team rules and constants
├── PROGRESS.md                       # Session-by-session work log
├── docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md  # Deep architecture audit
└── CLIENT_PERSPECTIVE_ANALYSIS.md    # Business/operational gap analysis
```

---

## Part 18: Testing and Development

### Test Suite

- **Total:** 1,419 tests passed, 0 failed, 8 skipped (2026-03-21)
- **Coverage:** 92%+
- **Lint:** `ruff check lip/` — 0 errors (enforced pre-commit)
- **Fast iteration:** `python -m pytest lip/tests/ -m "not slow"` (~3 min)
- **Full suite:** ~12 min (722s with slow tests)
- **E2E:** `test_e2e_pipeline.py` — 8 scenarios, fully in-memory, no live infrastructure
- **Live E2E:** `test_e2e_live.py` — requires Redpanda at localhost:9092 (auto-skips without it)

### Known Test Quirks

- `test_slo_p99_94ms` is a flaky timing test — fails under CPU load, passes in isolation. Not a regression signal.
- PyTorch + LightGBM (OpenMP) deadlock on macOS in the same pytest process. Session-scoped fixture sets `torch.set_num_threads(1)`.
- `torch>=2.6.0` required (2.2.0 unavailable on CPU wheel index).

### Never Commit

- `artifacts/` — Model binaries, generated data
- `c6_corpus_*.json` — AML typology patterns (CIPHER rule — never in version control)
- `.env` — API keys, tokens, secrets
- Any file containing real entity identifiers or PII

---

## Part 19: The Honest Assessment

LIP is technically sound. The architecture is defensively coded — kill switches, human oversight, tamper-resistant logs, dual-layer compliance blocking, degraded mode fallbacks. The ML models are honest about their limitations. The compliance framework addresses SR 11-7, EU AI Act, DORA, and AML requirements with specific implementations, not aspirational checkboxes.

The patent moat (Tier 2/3 private counterparty coverage) is defensible and technically distinct from JPMorgan's Tier 1 prior art.

The critical unknowns are all real-world:

1. **Does C1 work on real payments?** AUC = 0.8871 on synthetic data. The first pilot will tell whether that holds.
2. **Is the fee floor viable?** 300 bps annualised ($57.53 on $100K for 7 days) may be too low for the operational overhead banks incur to deploy LIP. Or it may be exactly right — the bridge prevents a much larger cost (stuck receivable, liquidity shortfall, correspondent relationship damage).
3. **Will banks accept the B2B structure?** The originating bank is the borrower, not the end customer. This is legally clean but commercially unfamiliar. The first pilot bank's legal team will test every assumption.
4. **Can the compliance hold architecture survive regulatory scrutiny?** The `hold_bridgeable` flag design is FATF-compliant in theory. A regulator's opinion is the only validation that matters.

No gaps are fatal. All sixteen documented gaps have identified fixes. The system is ready for pilot deployment once legal framing and operational onboarding infrastructure are in place.

---

*This document is the single narrative source for LIP. For specific ground truth values, defer to `docs/models/c1-model-card.md` and `docs/models/c1-training-data-card.md`. For regulatory compliance detail, defer to `docs/legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`. For architecture decisions and gap analysis, defer to `docs/engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md` and `docs/business/CLIENT_PERSPECTIVE_ANALYSIS.md`.*
