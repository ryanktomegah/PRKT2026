# PROVISIONAL PATENT APPLICATION
## TECHNICAL SPECIFICATION
### VERSION 4.0 — PRIOR ART HARDENED

**System and Method for Automated Liquidity Bridging  
Triggered by Real-Time Payment Network Failure Detection**

---

| Field | Value |
|---|---|
| Document Version | 4.0 — Prior Art Hardened |
| Supersedes | v3.0 (Design-Around Hardened) |
| Filing Basis Date | February 2026 |
| Status | For Attorney Review — Not Filed |
| Jurisdiction | USPTO (primary), CIPO, PCT / EPO |

| Version | Date | Changes |
|---|---|---|
| 1.0 | Jan 2025 | Initial white paper — research draft |
| 2.0 | Feb 2026 | Eight critical technical fixes incorporated; first patent-ready specification |
| 3.0 | Feb 2026 | Ten design-around vectors closed; four independent claims; functionally broad language |
| 4.0 | Feb 2026 | Prior art hardened: Background section citing Bottomline US11532040B2 and JPMorgan US7089207B1; Claim 1 trigger-distinction language; new Independent Claim 5 on auto-repayment |

> **WHAT CHANGED IN v4.0:** A targeted prior art search identified two patents that create a §103 obviousness risk when combined: Bottomline Technologies US11532040B2 (ML-driven automated borrowing triggered by forecasted cash shortfall) and JPMorgan Chase US7089207B1 (PD pricing from observable market data without assumed credit spread). Three surgical amendments address this risk without narrowing the core claims. Details in Section 0 and the amended claim language in Section 2.

---

## 0. Background and Prior Art Acknowledgment

The inventors conducted a targeted prior art search across USPTO records, focusing on five elements of the claimed invention: real-time payment event stream monitoring, machine learning classification for settlement failure probability, automated liquidity triggering on payment failure, probability-of-default pricing from observable financial data without assuming a credit spread, and automated repayment collection upon settlement confirmation. The search identified prior art in each element area individually, but found no single patent or combination that discloses all five elements as an integrated, event-driven system operating on live cross-border payment network telemetry.

Two prior art patents warrant specific acknowledgment because they represent the closest antecedents to sub-combinations of the claimed invention. The inventors bring these patents to the attention of the examiner at the outset of prosecution rather than waiting for them to be raised as rejections, because the distinctions between this invention and those references are clear, technically meaningful, and important to establish in the prosecution record from the first filing.

### 0.1 Bottomline Technologies SARL — US11532040B2

US11532040B2, assigned to Bottomline Technologies SARL and granted in 2022, discloses a system and method for international cash management using machine learning. The disclosed system analyses historical payment data for a monitored business entity, generates a forward-looking cash flow forecast using machine learning models including random forest and clustering algorithms, identifies predicted future periods where the entity's cash position is expected to fall below a threshold, and automatically initiates a borrowing or fund transfer transaction to cover the anticipated shortfall before it materialises.

This patent represents significant prior art for the combination of machine learning with automated liquidity provisioning in a payment context. The inventors acknowledge this contribution and draw the following technical distinctions.

The triggering mechanism in US11532040B2 is fundamentally different from the triggering mechanism of the present invention. Bottomline's system is triggered by a forward-looking cash flow forecast — a statistical prediction that the entity will probably run short of funds during a future time period, derived from analysis of historical payment patterns. The system does not monitor live payment transactions in progress. It does not receive real-time payment status signals from a payment network. It does not detect that a specific identified payment has failed or been delayed. Its trigger is a forecasted future insufficiency, not an observed present event.

The present invention's trigger is categorically different. The liquidity provision workflow of Claims 1 through 5 is initiated exclusively by the detection of a real-time failure or delay condition in a specific payment transaction that has already been initiated and is currently in process on a payment network — a transaction with an assigned identifier, a routing path, and an observable processing status that can be monitored in real time. This distinction is not a matter of degree. It is a difference in the kind of information being processed: future-projected aggregate cash position versus present-state specific transaction status. A cash flow forecasting system and a real-time payment failure detection system are as different architecturally as a weather forecast and a smoke alarm. Both involve risk prediction, but they operate on fundamentally different signals, at fundamentally different time horizons, with fundamentally different technical implementations.

Furthermore, Bottomline's system does not claim or suggest the use of payment network rejection codes, payment message status events, or any equivalent real-time telemetry from a payment processing network as inputs to its triggering mechanism. The system does not connect to ISO 20022 message streams, SWIFT gpi tracking interfaces, FedNow status APIs, or any equivalent payment network infrastructure. The present invention's integration of payment network telemetry as the primary trigger signal is a novel technical contribution with no antecedent in US11532040B2.

> **DISTINCTION SUMMARY — US11532040B2:** Bottomline triggers on: forecasted future cash shortfall from historical pattern analysis. Present invention triggers on: real-time failure signal from a specific in-flight payment transaction currently on a payment network. These are different triggers, different data sources, different architectures, and different time horizons. A system cannot be in both states simultaneously.

### 0.2 JPMorgan Chase Bank N.A. — US7089207B1

US7089207B1, assigned to JPMorgan Chase Bank N.A. and granted in 2006, discloses a method and system for determining a company's probability of no default. The method uses observable market factors — specifically current equity share price, equity price volatility, and total debt levels — as inputs to a structural credit risk model that derives a probability of default as an output. The patent explicitly notes that credit spread is derived from the probability of default as an output of the system, not assumed as an input, enabling the system to serve as a price discovery tool for credit risk.

This patent establishes that the concept of deriving probability of default from observable financial data without assuming a credit spread as an input was known in the art as of its priority date. The inventors acknowledge this prior contribution and draw the following distinctions.

US7089207B1 was designed for and is limited to listed public companies with observable equity market prices. The structural model described in the patent requires current equity share price and equity price volatility as mandatory inputs. Private companies — which constitute the majority of counterparties in mid-market cross-border trade finance, the primary commercial context of the present invention — do not have observable equity prices. They cannot be evaluated using the methodology of US7089207B1 without fundamental modification.

The present invention specifically and explicitly addresses this limitation through a tiered probability-of-default estimation framework that selects the appropriate methodology based on the data available for each specific counterparty. For listed counterparties with observable equity data, the system applies a structural model analogous to that of US7089207B1. For private counterparties with available balance sheet data but no observable equity prices, the system applies a proxy-based structural model using sector-median asset volatility sourced from published financial research databases. For counterparties with limited financial data, the system applies a reduced-form model using financial ratio scoring mapped to historical default rate tables. This tiered framework, which enables PD estimation across the full spectrum of counterparty data availability including the private-company case that US7089207B1 cannot address, is a novel contribution not taught or suggested by US7089207B1.

Additionally, US7089207B1 is a standalone credit pricing tool with no connection to payment network infrastructure. It does not monitor payment transactions. It does not receive payment network telemetry. It does not trigger any automated action in response to a payment event. The present invention integrates the PD-from-observables methodology — extended to private companies via the tiered framework — directly into a real-time payment network response system, an integration that requires novel system architecture and produces a commercially distinct product with no antecedent in US7089207B1.

> **DISTINCTION SUMMARY — US7089207B1:** JPMorgan covers: PD from observable equity market data for listed public companies, as a standalone credit pricing tool. Present invention adds: (1) tiered framework extending PD estimation to private companies without observable equity prices; (2) integration of PD pricing into a real-time payment network event-driven system. Neither extension is taught or suggested by US7089207B1.

### 0.3 The Combination Attack — §103 Obviousness Pre-emption

The examiner may argue that it would have been obvious to a person skilled in the art to combine Bottomline US11532040B2 (ML-driven automated liquidity triggered by detected cash risk) with JPMorgan US7089207B1 (PD pricing from observable financial data) and apply the combination to a cross-border payment context. The inventors respectfully submit that this combination argument fails for three independent reasons.

First, the triggering mechanisms of the two references are not combinable in any straightforward way. Bottomline's trigger is a future-projected aggregate cash position. JPMorgan's system has no trigger at all — it is a pricing calculation tool, not a monitoring or response system. Combining them does not produce a real-time payment network monitoring system without the inventive step of conceiving that payment network rejection telemetry could serve as the trigger signal — and that inventive step is precisely what the present inventors contributed.

Second, extending JPMorgan's methodology to private companies requires the inventive tiered framework described in this specification. A person skilled in the art reading US7089207B1 would know that the method cannot be applied to private companies without modification, but the specification does not suggest how to perform that modification. The tiered approach using sector-median asset volatility proxies and reduced-form fallback models is not obvious from US7089207B1 alone or from the general state of the art in 2026.

Third, the auto-repayment element — automatic collection of the liquidity advance upon ISO 20022 or equivalent settlement confirmation of the original payment — has no antecedent in either reference. The settlement-confirmation trigger that closes the liquidity loop is a novel technical contribution that appears in neither Bottomline's cash management system nor JPMorgan's credit pricing tool, and it is not obvious from their combination.

> **PROSECUTION INSTRUCTION:** If the examiner raises US11532040B2 or US7089207B1 as §103 references, cite this Section 0 narrative directly in the response to office action. The distinctions articulated above are the basis for arguing non-obviousness of the combination. Do not concede that the trigger mechanisms are equivalent. They are not.

---

## 1. Version History and Amendment Summary

Version 3.0 established functionally broad, design-around-hardened claims across four independent claim sets. Version 4.0 adds three targeted amendments in direct response to a prior art search that identified two patents warranting specific distinction. Nothing in the core invention has changed. The amendments sharpen the legal description of the invention's boundaries without narrowing the scope of any claim element.

| Amd. | Location | What Was Added | Why |
|---|---|---|---|
| **A** | New Section 0 | Full prior art acknowledgment: Bottomline US11532040B2 and JPMorgan US7089207B1 cited, described, and distinguished | Pre-empts §103 combination attack; controls examiner narrative from day one |
| **B** | Claim 1, step (a) — trigger language | One precision sentence explicitly restricting the trigger to a real-time in-flight payment failure event, not a forecast | Directly closes the Bottomline §103 vector at the claim language level |
| **C** | New Independent Claim 5 | Settlement-confirmation auto-repayment elevated from dependent claim status to standalone independent claim | Prior art search confirmed this element is the cleanest novelty; deserves its own independent protection |

---

## 2. Independent Claims — v4.0 Final

> **ATTORNEY INSTRUCTION:** Claims 1 through 4 are carried forward from v3.0 with one targeted amendment to Claim 1 (Amendment B — marked clearly below). Claim 5 is entirely new in v4.0 (Amendment C). Dependent claims follow in Section 3. The amendment to Claim 1 should be treated as the definitive claim language and supersedes all earlier versions.

### Independent Claim 1 — Core Method Claim (Amended in v4.0)

**A computer-implemented method for automated liquidity bridging in cross-border payment networks, the method comprising:**

(a) monitoring, by a real-time data processing pipeline, a continuous stream of payment status data originating from any payment network, payment messaging protocol, application programming interface, or digital communication channel through which financial institutions communicate the status, rejection, return, or delay of payment transactions, including but not limited to ISO 20022 structured messaging networks, SWIFT MT legacy message networks, Open Banking API data feeds, instant payment network status notifications, central bank digital currency settlement protocol event streams, and natural language payment communications processed by any means including machine learning-based language models; **wherein the liquidity provision workflow of this claim is initiated exclusively by the detection of a real-time failure or delay condition in a specific identified payment transaction that has already been initiated and is currently in process on said payment network — and not by any forward-looking prediction of future aggregate cash flow insufficiency derived from historical payment pattern analysis without reference to a specific in-flight transaction;**

(b) extracting, from each monitored payment status event, a feature representation comprising indicators of payment processing status, rejection reason, data quality, routing characteristics, temporal risk factors, and counterparty-specific performance history, wherein said feature representation is derived from data in any format including structured XML, structured JSON, semi-structured proprietary financial message formats, or unstructured natural language;

(c) generating, by a machine learning classifier trained on historical payment outcome data, a failure probability score for each monitored payment transaction, wherein the classifier architecture may be any supervised learning method producing a continuous probability output calibrated to the likelihood of payment settlement failure or significant delay, including gradient-boosted ensemble methods, deep neural networks, logistic regression models, or any combination thereof;

(d) comparing the failure probability score against a cost-optimised classification threshold selected to maximise a weighted precision-recall score that assigns asymmetric cost to false negative predictions relative to false positive predictions, reflecting the operational consequence of failing to detect an impending payment failure;

(e) responsive to the failure probability score exceeding the classification threshold, computing a counterparty-specific risk-adjusted liquidity cost by: assessing the probability that the counterparty associated with the delayed payment will fail to repay a short-duration liquidity advance, using any computational method that derives said probability from observable or estimable counterparty financial characteristics without assuming a credit spread as an input parameter, and wherein for counterparties lacking observable equity market prices, the probability of default is estimated from balance sheet data using sector-median asset volatility proxies, financial ratio scoring, or any equivalent methodology that does not require publicly traded equity as a prerequisite input; scaling said probability to the duration of the anticipated liquidity advance; computing an expected loss value from the product of the probability, the advance amount, and a loss-given-default estimate; and deriving a risk-adjusted cost rate from the expected loss as a proportion of the advance amount and duration;

(f) generating a liquidity provision offer to any party experiencing a cash flow deficit as a result of the payment delay, including the payment receiving party, the payment sending party, or any intermediary party in the payment chain, wherein said offer specifies the advance amount, the risk-adjusted cost, and the repayment mechanism;

(g) transmitting the liquidity provision offer via any electronic communication channel to the affected party within a response latency that is sufficiently short to provide commercial utility before the affected party would otherwise exhaust alternative liquidity options; and

(h) automatically collecting repayment from the affected party upon confirmation of original payment settlement, using any settlement monitoring mechanism that tracks the status of the original payment across any payment network.

> **AMENDMENT B MARKER:** The bolded trigger-distinction language in step (a) — beginning 'wherein the liquidity provision workflow' — is the v4.0 amendment. It explicitly excludes the Bottomline US11532040B2 trigger mechanism from the scope of Claim 1 by requiring a real-time in-flight transaction event, not a forecast. The additional private-company PD language in step (e) explicitly extends beyond the scope of JPMorgan US7089207B1.

---

### Independent Claim 2 — System Claim (Unchanged from v3.0)

**A system for automated liquidity bridging triggered by payment network failure prediction, the system comprising:**

(i) a payment network monitoring component configured to receive and process payment status events from any source described in Claim 1(a), wherein said component may be implemented as a component of a monolithic application, as a discrete microservice communicatively coupled to other system components via application programming interfaces, as an embedded module within enterprise resource planning software, treasury management software, or payment processing software, or as a software-as-a-service component operated by a third party on behalf of a financial institution;

(ii) a failure prediction component comprising a machine learning inference engine configured to receive feature vectors derived from payment status events and output failure probability scores, wherein the model architecture, training methodology, and specific feature engineering pipeline are implementation details that do not limit the scope of this claim;

(iii) a counterparty risk assessment component configured to compute a probability of default for the counterparty associated with a flagged payment, using any estimation method that produces an empirically grounded probability without requiring observable equity market prices as a mandatory input, including structural credit risk models using balance sheet data, reduced-form hazard rate models calibrated to historical default data, machine learning models trained on trade finance default outcomes, or any combination thereof, and wherein said component selects the estimation method based on the availability of counterparty financial data;

(iv) a liquidity pricing component configured to compute a risk-adjusted advance cost rate from the counterparty probability of default, a loss-given-default estimate, and the anticipated advance duration, wherein the resulting cost rate is derived from the expected loss of the transaction rather than from any pre-assumed credit spread or benchmark credit rating;

(v) a liquidity execution component configured to generate, transmit, and track a liquidity provision offer, execute a funding disbursement upon acceptance of the offer, programmatically establish a security interest in the delayed payment proceeds as collateral for the advance, and automatically initiate repayment collection upon settlement confirmation; and

(vi) a settlement monitoring component configured to track the status of the original payment transaction across any payment network infrastructure and trigger the repayment collection workflow upon detection of a settled or credited status.

---

### Independent Claim 3 — Instrument-Agnostic Liquidity Method (Unchanged from v3.0)

**A computer-implemented method for providing automated liquidity to a business entity experiencing a working capital deficit caused by a delayed, rejected, or returned cross-border payment, the method comprising:**

(j) receiving a failure prediction signal generated by a machine learning classifier operating on payment network monitoring data, wherein the signal specifies an affected payment transaction, an estimated delay duration, and a failure probability score above a predetermined threshold;

(k) computing a counterparty risk-adjusted liquidity cost using any method that derives the cost from the probability and magnitude of non-recovery of the advanced funds, independently of any externally assumed credit spread;

(l) offering the affected business entity a liquidity provision structured as any financial instrument that transfers funds to the entity in exchange for a claim on the delayed payment proceeds, including but not limited to: a short-duration bridge loan secured by assignment of the delayed receivable; a receivable purchase or factoring advance at a discount reflecting the computed recovery risk; a payment guarantee or standby letter of credit covering the delayed amount; a credit facility draw against a pre-approved revolving line; or any combination of the above instruments;

(m) executing the selected liquidity instrument upon acceptance by the affected party, including programmatic establishment of any security interest, assignment, or lien on the delayed payment proceeds required by the instrument structure; and

(n) automatically unwinding the liquidity instrument and collecting the advance proceeds upon confirmation of original payment settlement or upon expiry of the agreed advance term.

---

### Independent Claim 4 — Pre-Emptive Liquidity (Unchanged from v3.0)

**A computer-implemented method for pre-emptive liquidity provisioning in cross-border payment networks, the method comprising:**

(o) analysing historical payment execution data for a monitored business entity to identify recurring patterns of payment timing, counterparty reliability, seasonal cash flow cycles, and payment network performance on frequently used routing corridors;

(p) computing a forward-looking failure probability distribution for anticipated future payment receipts within a defined forward window, based on historical counterparty-specific rejection and delay rates, current payment network performance metrics, temporal risk factors, and any available early-warning signals in the payment network;

(q) responsive to the forward-looking failure probability exceeding a threshold indicating material working capital risk within the forward window, proactively offering a standing liquidity facility to the monitored business entity, wherein the facility limit is calibrated to the estimated maximum cumulative payment gap and the pricing reflects the probability-weighted expected loss across the anticipated payment portfolio;

(r) automatically drawing on the standing liquidity facility for individual payments when real-time monitoring confirms that a specific anticipated payment has entered a failure or delay state; and

(s) releasing the standing facility and collecting repayment as the anticipated payments settle, maintaining a continuous liquidity coverage model that updates in real time as each payment outcome is observed.

---

### Independent Claim 5 — Settlement-Confirmation Auto-Repayment Loop (NEW in v4.0)

> **AMENDMENT C — WHY THIS CLAIM IS NEW:** Prior art search confirmed that no existing patent specifically automates repayment collection upon ISO 20022 or equivalent settlement confirmation of an original cross-border payment. This element has the cleanest novelty of all five invention elements. Elevating it to an independent claim creates a fallback that survives even if Claims 1–4 were successfully challenged, and it stands as independently valuable IP covering the settlement monitoring and repayment automation mechanism regardless of how the liquidity is originated.

**A computer-implemented method for automated repayment collection on a short-duration liquidity advance secured against a cross-border payment receivable, the method comprising:**

(t) establishing a programmatic monitoring relationship between a disbursed liquidity advance and a specific cross-border payment transaction identifier, wherein the advance was disbursed to a party experiencing a working capital deficit caused by a failure, delay, or rejection condition affecting the identified payment transaction;

(u) continuously monitoring the settlement status of the identified payment transaction using any real-time or near-real-time data feed, API, or message-based interface provided by a payment network, payment messaging infrastructure, or financial institution through which the original payment is being processed, including but not limited to SWIFT gpi tracker data, ISO 20022 payment status notification messages, Open Banking payment status APIs, and FedNow or equivalent instant payment network settlement confirmation events;

(v) upon detection of a settlement confirmation event indicating that the original payment transaction has been credited to the intended beneficiary or is imminently to be credited, automatically initiating a repayment collection workflow that recovers the advance principal and accrued risk-adjusted cost from the advance recipient, the settlement proceeds, or any collateral or security interest established at the time of advance disbursement, without requiring any manual instruction from an operator;

(w) in the event that the original payment transaction fails permanently rather than settling, automatically activating a recovery workflow against the collateral or security interest assigned at disbursement, including but not limited to enforcing an assignment of the payment receivable against the original payment sender, drawing on any guarantee or insurance instrument established at disbursement, or initiating a collections process against the advance recipient; and

(x) generating a settlement and repayment confirmation record that documents the original payment identifier, the advance disbursement details, the settlement confirmation event, the repayment amount, and the net realised return on the advance, for regulatory reporting, audit trail, and portfolio performance monitoring purposes.

> **STRATEGIC NOTE — CLAIM 5:** Claim 5 is valuable independent of the rest of the portfolio because it covers the settlement loop that any competitor building a payment-triggered liquidity product must implement. Even a competitor who designs around Claims 1–4 entirely — using a different trigger, a different pricing model, a different instrument — still needs to collect repayment automatically upon settlement. If they do so using payment network confirmation data, they infringe Claim 5. This claim is the net at the bottom of every possible design-around attempt.

---

## 3. Dependent Claims — Updated for v4.0

The dependent claim table is expanded from v3.0 with two additions: D11, which provides a specific embodiment of the Claim 5 auto-repayment loop using SWIFT gpi UETR tracking as the settlement confirmation data source; and D12, which provides a claim covering the private-company PD estimation methodology as a specific dependent on Claim 1.

| Dep. | Depends On | Specific Embodiment Covered | Strategic Purpose |
|---|---|---|---|
| D1 | Claim 1 | Parsing specifically ISO 20022 pacs.002 XML status reason codes as the payment failure signal | Core product embodiment — largest near-term market |
| D2 | Claim 1 | Failure probability derived from SWIFT gpi UETR real-time tracking data as the monitoring data source | Covers gpi-specific pipeline; most commercially deployed |
| D3 | Claim 1 | Classification threshold optimised using F-beta score with beta = 2, weighting recall twice as heavily as precision | Specific threshold methodology; unconventional — supports Alice Step 2 |
| D4 | Claim 2 | PD computed using iterative KMV-style structural model for listed counterparties with observable equity market data | Tier 1 PD — covers public company counterparties |
| D5 | Claim 2 | PD computed using sector-median asset volatility proxy from Damodaran or equivalent published database for private counterparties | Tier 2 PD — most commercially relevant; extends beyond JPMorgan US7089207B1 |
| D6 | Claim 2 | PD computed using Altman Z'-score mapped to S&P or Moody's historical default rate tables for data-sparse counterparties | Tier 3 PD fallback — completes the private-company coverage |
| D7 | Claim 3 | Liquidity instrument is specifically a bridge loan secured by legal assignment of the delayed payment receivable to the lender | Core bridge loan product — most legally familiar to banking partners |
| D8 | Claim 3 | Liquidity instrument is specifically a receivable purchase executed at a CVA-derived discount to face value | Covers factoring/invoice finance angle; closes Instrument Design-Around |
| D9 | Claim 1 | Failure prediction pipeline operates at sub-100ms inference latency from payment status event receipt to failure probability output | Alice defence — anchors claims to specific measurable technical performance |
| D10 | Claim 2 | System implemented as an embedded software module within enterprise resource planning, treasury management, or payment processing software operated by a third party | Closes embedded finance design-around explicitly |
| **D11** | **Claim 5** | **Settlement confirmation detected via SWIFT gpi UETR tracker data showing payment credited to beneficiary bank, triggering automated repayment collection within 60 seconds of confirmation** | **Specific embodiment of Claim 5 for the SWIFT gpi ecosystem — largest current market** |
| **D12** | **Claim 1** | **Probability of default for private counterparties without publicly traded equity is estimated using total assets as asset value proxy, sector-median asset return volatility, and hazard rate scaling to bridge loan duration** | **Codifies the exact private-company methodology that distinguishes from JPMorgan US7089207B1** |

*Bold rows D11 and D12 are new in v4.0.*

---

## 4. Alice Doctrine Compliance — Updated for v4.0

The Alice Corp. v. CLS Bank (2014) two-step analysis applies to all five independent claims. The prior art acknowledgment in Section 0 strengthens the Alice analysis by establishing, in the prosecution record, that the claimed invention represents a specific non-obvious technical improvement over the closest known prior art — not merely a generic application of known financial methods to a computer.

### 4.1 Step 1 — Are the Claims Directed to an Abstract Idea?

Claims 1 and 5 describe specific technical improvements to real-time payment network infrastructure. The sub-100ms inference latency requirement in Dependent Claim D9 anchors the technical improvement to a measurable performance standard. The settlement confirmation monitoring architecture of Claim 5 describes a specific technical integration between payment network status event processing and automated financial workflow execution. Following Enfish, LLC v. Microsoft Corp. (Fed. Cir. 2016), both claims are directed to improvements in how a specific technical system — a payment processing and monitoring infrastructure — operates, not to abstract financial methods that merely happen to be implemented on a computer.

Claims 2 and 3 describe a novel system architecture integrating two previously isolated technical domains: payment network telemetry processing and automated credit risk assessment. Following McRO, Inc. v. Bandai Namco (Fed. Cir. 2016), these claims are patent-eligible because the improvement is to the technical functioning of the integrated system, not merely to the business outcome.

Claim 4 describes a method for computing a portfolio-level forward failure probability distribution and calibrating a standing financial facility to that distribution in real time. The continuous update mechanism — recalibrating the probability model and facility position as each payment settles or fails — is a specific unconventional computational method with no analog in prior art, satisfying the Enfish technical improvement standard.

### 4.2 Step 2 — Inventive Concept

Step 2 is met independently by each of the following inventive concepts, any one of which would be sufficient:

- **Real-time in-flight transaction event trigger** — the specific restriction of the liquidity trigger to a present-state failure event in an identified in-process transaction (not a forecast) is an unconventional system design choice that distinguishes the invention from all prior art.

- **Tiered PD estimation framework for private companies** — the automatic selection of a PD methodology based on counterparty data availability, including the private-company proxy approach, is an unconventional computational architecture with no antecedent.

- **F-beta cost-weighted threshold optimisation** — calibrating the classifier threshold using a domain-specific cost ratio that weights false negatives asymmetrically is an unconventional machine learning application technique.

- **Settlement-confirmation automated repayment loop** — the specific integration of payment network settlement event monitoring with automated advance repayment collection, without manual instruction, is a novel technical mechanism with no antecedent in prior art.

- **Pre-emptive portfolio gap distribution model** — computing a portfolio-level working capital gap distribution and calibrating a standing facility to its 95th percentile is a novel quantitative method with no antecedent in payment infrastructure prior art.

---

## 5. Trade Secret Layer — The Jurisdiction-Agnostic Moat

Design-Around Vector 10 identified that geographic arbitrage — building the system from a non-patent jurisdiction and serving global clients via API — cannot be blocked by patent law alone. This section documents the trade secret assets that provide competitive protection regardless of where a competitor operates. These assets are specifically excluded from the patent disclosure to preserve their trade secret status.

| Trade Secret Asset | Classification | Why It Cannot Be Replicated From Patent Disclosure Alone |
|---|---|---|
| Calibrated ML model weights and feature importance rankings | **CRITICAL** | The patent discloses the architecture and training methodology. The specific weights, the feature importance order, and the threshold calibration values derived from live payment data cannot be reverse-engineered from the architecture description alone. |
| Correspondent bank BIC-pair performance database | **CRITICAL** | Historical rejection rates, average processing times, and compliance hold frequencies for thousands of specific BIC-pair routing combinations. Built from banking partnership data. Cannot be reconstructed without equivalent proprietary data access. |
| CVA parameter calibrations by sector and corridor | **HIGH** | The specific LGD values by industry sector, the friction adjustment parameters by currency corridor, and the PD mapping tables derived from live bridge loan portfolio performance are proprietary. The formula structure is disclosed; the calibrated values are not. |
| Error code failure probability priors | **HIGH** | The initialising probability values for each ISO 20022 rejection reason code, calibrated from thousands of historical payment outcomes. The patent discloses these exist; it does not disclose what they are. |
| Supply chain relationship network graph | **CRITICAL** | As the system accumulates data on payment patterns, it builds a proprietary graph of supply chain payment relationships. This network topology is the foundation of the Cascade Prevention extension and cannot be built without years of live deployment data. |
| Private-company sector volatility calibration database | **HIGH** | The specific sector-median asset volatility values used in the Tier 2 PD framework, sourced from proprietary analysis of trade finance default outcomes rather than from published databases. The methodology is disclosed; the proprietary calibrations are not. |

> **THE COMPOUNDING ADVANTAGE:** Each year of live deployment makes the trade secret layer stronger. The ML model improves. The BIC-pair database grows. The private-company volatility calibrations become more precise. A competitor who reads the patent in 2030 and attempts to build the system from scratch will produce a system that performs materially worse than the 2026 version of ours — not because the patent blocked them, but because they lack the proprietary training data and calibrations built from live deployments. By 2035 that performance gap is insurmountable.

---

## 6. Complete Prior Art Matrix — All Five Invention Elements

| # | Invention Element | Closest Prior Art | Nature of Overlap | Novelty Assessment |
|---|---|---|---|---|
| 1 | Real-time payment event stream monitoring | US20250086644A1 (unassigned 2024); US20200126066A1 (Mastercard) | Real-time monitoring of payment events and automated response to failure signal | **MODERATE** — prior art monitors payment events but does not connect to ML failure prediction + liquidity provisioning chain |
| 2 | ML classifier for settlement failure probability | US20250086644A1 (unassigned); US11526859B1 (Bottomline) | ML applied to payment transaction classification and cash flow forecasting | **MODERATE** — ML on payment data exists; the specific failure probability scoring on in-flight transactions does not |
| 3 | Automated liquidity trigger on real-time payment failure | US11532040B2 (Bottomline) — closest; US20200126066A1 (Mastercard) | Bottomline: ML → automated borrowing on forecast shortfall. Mastercard: payment failure → card fallback | **STRONG** — no prior art triggers a liquidity advance from a real-time in-flight transaction failure event |
| 4 | PD pricing from observable financials without assumed credit spread | US7089207B1 (JPMorgan) — direct overlap on methodology for listed companies | JPMorgan derives PD from equity market data without credit spread assumption — same mathematical approach | **MODERATE** for listed companies; **STRONG** for private companies via tiered framework which JPMorgan does not cover |
| 5 | Auto-repayment on settlement confirmation | US20080086410A1 (general cash advance) — structural analog only | Repayment tied to future billing event — analogous structure but no payment network integration | **STRONG** — no prior art automates repayment collection using cross-border payment network settlement confirmation data |

> **OVERALL NOVELTY VERDICT:** The integrated five-element system — real-time in-flight payment failure detection → ML probability scoring → automated liquidity offer → PD-derived pricing without assumed credit spread → settlement-confirmation auto-repayment — does not exist in any single prior art reference or any obvious combination of prior art references. The white space is confirmed. The prior art acknowledgment in Section 0 and the claim amendments in Section 2 ensure this white space is legally defended from the first day of prosecution.
