# Technical Depth — Narrative

**Canonical anchors (use verbatim across all tiers and every drill answer):**
1. **two-step classification + conditional offer mechanism** — The core patent claim: C1 classifies the failure type first; C2 prices risk only if that classification clears; no offer issues without the gate passing.
2. **ninety-four millisecond SLO** — End-to-end latency from pacs.002 arrival to loan offer output, QUANT-locked at p99.
3. **three-hundred basis point fee floor** — Minimum annualised bridge loan fee, QUANT-locked; every loan that executes is capital-positive.
4. **ISO 20022 migration window** — SWIFT's structured rejection codes made real-time failure classification tractable for the first time.
5. **synthetic-first build** — The full pipeline was validated against two million synthetic records before any live bank traffic, so the system arrives at a pilot ready — not asking the bank to be a beta tester.

---

## Tier A — 30-second

LIP detects a failed cross-border SWIFT payment, classifies the failure type in real time, and conditionally offers the originating bank a short-term bridge loan — all before a treasury officer opens their inbox.
The technical problem is that no prior system could distinguish a routing error from a sanctions hold fast enough to price and offer credit at machine speed.
Our answer is the two-step classification + conditional offer mechanism: C1 classifies the rejection code, and C2 prices risk only when that classification clears — delivering a priced offer within the ninety-four millisecond SLO.
That mechanism is exactly what our patent claims — and the ISO 20022 migration window is why the timing is right now.

---

## Tier B — 2-minute (taxi-ride)

**Problem.** A cross-border B2B payment fails. The bank's treasury team learns about it hours later via a batch report. The underlying trade stops. Across thirty-one point six trillion dollars ($31.6T) in annual B2B volume, this gap costs one hundred eighteen point five billion dollars ($118.5B) per year in aggregate.

**What everyone tries.** Banks manually arrange overnight bridge facilities. Treasury teams intervene case by case. Manual review takes hours, pricing is guesswork, and the decision arrives after the damage is done.

**Our insight.** The ISO 20022 migration window created structured rejection codes inside every pacs.002 message. Those codes predict the bridge maturity and the credit risk. No prior system built a real-time classification layer on top of them.

**The mechanism.** The two-step classification + conditional offer mechanism: C1 (Failure Classifier) reads the rejection code and counterparty graph to assign a failure class. C2 (PD Model) prices the bridge only if C1 clears, applying the three-hundred basis point fee floor. C7 (Execution Agent) issues the offer. The ninety-four millisecond SLO means a priced offer arrives before a human opens the case.

**Outcome.** A live demo priced a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge at seven hundred six basis points in real time.

That mechanism is the core of our patent portfolio — the Patent volume walks through the specific claims.

---

## Tier C — 5-minute (whiteboard)

**1. Problem.**
Deutsche Bank sends a SWIFT payment to Siemens AG's account at BNY Mellon. BNY Mellon rejects it with a pacs.002 — rejection code MS03, a beneficiary account mismatch. The payment was for €4.2M against a supply chain settlement. Deutsche Bank's treasury team discovers the rejection ninety minutes later in a batch report. The bridge window — the period where a short-term loan resolves the liquidity gap — is already closing. This scenario repeats across three to five percent of thirty-one point six trillion dollars ($31.6T) in annual cross-border B2B volume.

**2. What everyone tries.**
JPMorgan holds the closest prior art: US7089207B1, covering static bridge loans for listed counterparties. Banks with strong correspondent relationships negotiate overnight facilities manually. Wise operates efficient FX rails for consumer and SMB transfers. None of these approaches operate in real time, price credit dynamically, or classify the failure type before deciding whether to lend.

**3. Why it fails.**
Without knowing why a payment failed, a lender cannot price the bridge. A routing error resolves in three days (Class A). A systemic delay resolves in seven days (Class B). A sanctions hold is never bridgeable (BLOCK class — eight permanently blocked rejection codes). A lender who cannot distinguish these cases either over-lends into compliance risk or under-lends and misses the window. Manual processes default to slow and conservative.

**4. Our insight.**
The ISO 20022 migration window changed the data landscape. Structured pacs.002 rejection codes, combined with corridor-level graph signals and counterparty history, are sufficient to classify failures in real time. The two-step classification + conditional offer mechanism — classify first, price second, offer only if the classification clears — converts that signal into a machine-speed credit decision.

**5. The mechanism.**
C1 (Failure Classifier) runs a GraphSAGE graph neural network, a TabTransformer, and LightGBM to assign a failure probability and class. Above a calibrated 0.110 threshold, C4 (Dispute Classifier) and C6 (AML/Velocity) run in parallel. If both pass, C2 (PD Model) prices the bridge — Merton/KMV for listed counterparties, Damodaran industry-beta for private companies, Altman Z' for thin-file borrowers — never below the three-hundred basis point fee floor. C7 (Execution Agent) issues the offer via Go gRPC. C3 (Repayment Engine) monitors UETR settlement and triggers auto-repayment on confirmation. End-to-end: the ninety-four millisecond SLO at p99.

**6. Outcome.**
On the live demo: a two-million eight-hundred ninety-thousand-dollar ($2,890,000) bridge, nine-day maturity, seven hundred six basis points, total fee five thousand and thirty-three dollars ($5,033). C1 probability: twenty-five point four percent (25.4%). Full pipeline, start to finish, on a synthetic pacs.002.

**7. What this unlocks.**
The two-step classification + conditional offer mechanism is the core of our provisional patent. The ISO 20022 migration window narrows as incumbents complete migration — our synthetic-first build means we arrive at a pilot with coverage, not a prototype. The Patent volume covers the specific claims; the Market volume quantifies the addressable bridge volume classification makes reachable.

---

## Tier D — Deep-dive

### 1. Problem in detail

Cross-border B2B payments carry thirty-one point six trillion dollars ($31.6T) annually. Three to five percent fail on first attempt — disrupting between two point six billion and four point four billion dollars ($2.6B–$4.4B) in daily value. SWIFT GPI tracks ninety-two percent of transactions credited within twenty-four hours; the remaining eight percent are stuck, rejected, or under investigation. The FSB 2024 G20 report shows only five point nine percent (5.9%) of B2B services settle within one hour, against a seventy-five percent target.

When a pacs.002 rejection arrives, the originating bank faces three problems simultaneously. A liquidity gap: the beneficiary is unpaid and the underlying obligation — supplier invoice, margin call, payroll — does not pause. A classification problem: the rejection code carries information about why the payment failed, but no automated system interprets it into a credit-relevant failure class. A pricing problem: no real-time model prices a bridge loan against the specific failure type and counterparty profile. The result is a gap measured in hours that costs the global financial system one hundred eighteen point five billion dollars ($118.5B) per year.

Correspondent banks have capital. The problem is the absence of a real-time classification and pricing layer that converts a rejection code into a defensible, priced, auto-executing loan offer before the liquidity window closes.

---

### 2. Existing approaches and their gaps

JPMorgan Chase holds US7089207B1 — the closest prior art. That patent covers automated bridge loans for listed counterparties with pre-negotiated static terms. Three structural gaps make it insufficient. First, coverage is Tier 1 only: listed companies. Private counterparties — the majority of correspondent banking volume — are out of scope. Second, bridge terms are static: fixed duration and rate set at contract time, not derived from the rejection event. Third, the patent predates ISO 20022 migration; it does not classify rejection codes or condition the offer on a failure taxonomy.

Bottomline Technologies (US11532040B2) covers ML-based aggregate cash flow forecasting. Bottomline operates at portfolio level; LIP acts at individual payment level, keyed on a UETR. That distinction is the primary §103 obviousness defense.

Manual treasury intervention is the de facto response at most banks: identify the rejection, call the correspondent, arrange an overnight facility. Typical elapsed time: three to six hours. Pricing is relationship-driven, not risk-adjusted.

Wise and Ripple address different problems. Wise serves consumer and SMB transfers. Ripple's On-Demand Liquidity uses XRP for pre-funded corridor settlement. Neither addresses real-time failure classification and conditional bridge lending at the five-hundred-thousand-dollar to five-million-dollar correspondent banking scale.

The gap is consistent: no existing approach builds a real-time classification layer that interprets a rejection code, assigns a failure class, and conditionally prices a bridge loan within a latency envelope compatible with automated execution.

---

### 3. Our insight and why now

The ISO 20022 migration window created a data environment that did not previously exist. SWIFT's coexistence period produced structured, machine-readable pacs.002 messages carrying standardised rejection codes. Those codes classify into three actionable tiers: Class A (routing errors, three-day maturity), Class B (systemic delays, seven-day maturity), and Class C (liquidity or investigation holds, twenty-one-day maturity). Eight codes — DNOR, CNOR, RR01 through RR04, AG01, LEGL — map to BLOCK class and are never bridged, on three independent grounds: structuring/layering risk under FATF recommendations, AMLD6 Article 10 criminal liability, and repayment mechanics that break for payments that never settle.

Before ISO 20022, rejection data was unstructured. Classification at machine speed was not tractable. No incumbent has yet built the classification layer on top of the new data.

The synthetic-first build means LIP does not need live bank data to validate. The two-million-record corpus, calibrated from SWIFT GPI timing distributions, enables end-to-end validation before any pilot. The window is a timing advantage that narrows as incumbents complete migration.

---

### 4. Architecture overview

LIP has eight core components (C1–C8).

**C1 — Failure Classifier** (ML). GraphSAGE generates corridor embeddings from counterparty relationship graphs. A TabTransformer processes tabular payment features. LightGBM combines both. C1 outputs a failure probability; above the 0.110 threshold, a failure class. This is the first step of the two-step classification + conditional offer mechanism.

**C2 — PD Model** (ML + deterministic). Tiered credit pricing: Merton/KMV for listed counterparties, Damodaran industry-beta for private companies, Altman Z' for thin-file borrowers. Output: probability of default, loss-given-default, and fee in basis points — floored at three hundred basis points. Conformal prediction intervals cap upward fee adjustment at a two-times multiplier. This is the second step of the mechanism.

**C3 — Repayment Engine** (deterministic). Rust finite state machine (PyO3) that polls UETR status and auto-repays on confirmation. Settlement P95: 7.05 hours (Class A), 53.58 hours (Class B), 170.67 hours (Class C) — calibrated from BIS/SWIFT GPI analytics.

**C4 — Dispute Classifier** (ML). Qwen3-32B via Groq. Hard-blocks disputed payments. Runs in parallel with C6.

**C5 — Streaming** (deterministic). Go Kafka consumer. Normalises ISO 20022 pacs.002 messages. Entry point for all payment events.

**C6 — AML/Velocity** (deterministic). Rust velocity counters (PyO3) screen entity-level transaction frequency plus OFAC and EU sanctions. Anomalies route to PENDING_HUMAN_REVIEW under EU AI Act Article 14.

**C7 — Execution Agent** (deterministic). Go gRPC router that issues the loan offer after checking kill switch, KMS availability, and human-override flags. The conditional offer logic is enforced here.

**C8 — License Manager** (deterministic). HMAC-SHA256 token validation that enforces per-licensee AML caps and feature flags at boot time.

---

### 5. Key design decisions

**Ninety-four millisecond SLO.** The p99 latency target is a product requirement. A five-second answer arrives after the human has already made calls. The ninety-four millisecond SLO was derived from C1 inference benchmarks (median forty-five milliseconds at p50) plus C2 pricing, C6 velocity check, and C7 execution overhead, with margin for serialisation. The SLO is QUANT-locked: changing it requires QUANT sign-off because it directly constrains which model architectures are feasible.

**Three-hundred basis point fee floor.** At the Class A minimum — one million five hundred thousand dollars ($1,500,000) over three days — three hundred basis points annualised generates approximately $185 in cash fee. Below that floor, the loan is capital-negative after cost of funds. The floor is structural. Phase 1 loans (bank-funded) generate thirty percent as BPI royalty; the floor ensures that royalty is always positive.

**Polyglot stack (Python, Rust, Go).** Python owns the ML inference path (C1, C2, C4): the ecosystem is there and latency is acceptable. Rust owns the performance-critical deterministic paths (C3 repayment FSM, C6 velocity counters): microsecond consistency matters and GC pauses are unacceptable. Go owns the network I/O paths (C5 Kafka consumer, C7 gRPC router): native concurrency primitives. Each language is used where it carries a genuine advantage.

**Synthetic-first build.** The two-million-record synthetic corpus (seed 42, calibrated from SWIFT GPI settlement timing distributions) was built before any live bank traffic was available. This was a deliberate architecture choice: a system that requires live production data to validate is asking the pilot bank to be a beta tester. The synthetic-first build means the system arrives at the RBC pilot with one thousand two hundred eighty-four (1,284) passing tests and ninety-two percent (92%) coverage.

**Ford Principle governance.** QUANT controls all fee arithmetic — nothing merges that changes fee logic without QUANT sign-off. CIPHER controls AML patterns and cryptographic primitives — typology patterns are never committed to version control. REX controls regulatory compliance — no model ships without a data card and out-of-time validation record. This is the audit trail a Tier 1 bank's model risk committee will demand under SR 11-7 and OSFI E-23.

---

### 6. Validation status

One thousand two hundred eighty-four (1,284) tests pass. Coverage is ninety-two percent (92%). The end-to-end pipeline runs in memory against mock C1/C2 outputs across eight scenarios with no live Redis or Kafka infrastructure required.

The corpus is synthetic. This is the honest statement of where the system stands: the two-million-record payments corpus was generated using SWIFT GPI settlement timing distributions as calibration anchors. It is not live bank transaction data. The C1 model's baseline AUC of 0.739 and target AUC of 0.850 are measured against that synthetic corpus. Conformal prediction intervals on C2 fee outputs carry a ninety percent (90%) coverage guarantee on synthetic data — coverage on live data will differ until the model is retrained on production traffic.

LIP is pre-production. No live bank traffic has flowed through the pipeline. No production latency profile exists. The ninety-four millisecond SLO is a design target validated on local hardware benchmarks, not a measured p99 from a live deployment.

The RBC pilot is the gate. Every number in this section should be read as: validated on a carefully constructed synthetic corpus, not yet verified on live traffic. The synthetic-to-live gap closes when the first bank connects a live pacs.002 stream.

---

### 7. What ships next

The RBC pilot gates everything. The approach: resign from RBC, file the provisional patent, then approach RBC and other Tier 1 banks as an external vendor. RBC AI Group (Bruce Ross) and RBCx (Sid Paquette) are the primary entry points.

Three items must precede the pilot: the MRFA names the originating bank as borrower and includes the hold_bridgeable certification warranty (EPG-04/EPG-05); the provisional filing establishes patent priority before external disclosure; C8 license token deployment sets per-licensee AML caps at the pilot bank.

After the pilot, the roadmap moves from Phase 1 licensing (bank funds 100%, BPI earns thirty percent royalty) to Phase 2 hybrid capital (fifty-five percent BPI share) to Phase 3 full MLO (eighty percent BPI share). The two-step classification + conditional offer mechanism is the technology that earns the right to reach Phase 3.
