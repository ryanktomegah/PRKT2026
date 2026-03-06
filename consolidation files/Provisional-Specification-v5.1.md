# PROVISIONAL PATENT APPLICATION

# TECHNICAL SPECIFICATION

# VERSION 5.1 — PROSECUTION-READY

*System and Method for Automated Liquidity Bridging Triggered by Real-Time Payment Network Failure Detection*

| **Field** | **Value** |
|-----------|-----------|
| Document Version | 5.1 — Prosecution-Ready (Recentive Compliance Update) |
| Supersedes | v5.0 — Prosecution-Ready |
| Status | For Filing — Date To Be Confirmed at Attorney Engagement |
| Jurisdiction | USPTO (primary), CIPO, PCT / EPO |
| Confidentiality | Attorney-Client Privileged — Do Not Distribute |

| **Version** | **Changes** |
|-------------|-------------|
| v1.0 | Initial white paper — research draft |
| v2.0 | Eight critical technical fixes; first patent-ready specification |
| v3.0 | Ten design-around vectors closed; four independent claims; functionally broad language |
| v4.0 | Prior art hardened: Background section citing Bottomline US11532040B2 and JPMorgan US7089207B1; Claim 1 trigger-distinction language; new Independent Claim 5 on auto-repayment; new Dependent Claims D11 and D12 |
| v5.0 | Prosecution-ready: (A) Claim 1 trigger language refined — 'exclusively' replaced with precise transaction-specific restriction, doctrine of equivalents preserved; (B) Trigger-distinction elements added to Claims 2 and 3; (C) Claim 4 steps (o–q) amended to portfolio-level gap distribution distinguishing Bottomline at the claim level; (D) New Dependent Claim D13 — adversarial camt.056 cancellation detection and security interest preservation; (E) Dependent Claim D9 latency language qualified as median (p50) |
| **v5.1** | ***Recentive* compliance: Section 4.1 Alice analysis updated to cite *Recentive Analytics v. Fox* (Fed. Cir. 2025) and explicitly anchor claims to technical infrastructure improvements (latency, interoperability, settlement visibility) rather than abstract business optimization, consistent with latest Federal Circuit § 101 guidance** |

## WHAT CHANGED IN v5.1

One substantive addition to the Alice compliance analysis in Section 4.1. The Federal Circuit's 2025 decision in *Recentive Analytics, LLC v. Fox Corp.* clarified that applying established machine learning methods to a new data environment is insufficient for patent eligibility under 35 U.S.C. § 101; claims must demonstrate improvement to the technical functioning of the computer system or network infrastructure itself. Version 5.1 adds explicit *Recentive* citation and technical infrastructure anchoring (latency, interoperability, settlement visibility) to Section 4.1, demonstrating that the claims improve payment network infrastructure operation rather than merely automating financial decisions. All claims, prior art distinctions, and prosecution strategy remain unchanged from v5.0.

---

## 0. Background and Prior Art Acknowledgment

The inventors conducted a targeted prior art search across USPTO records, focusing on five elements of the claimed invention: real-time payment event stream monitoring, machine learning classification for settlement failure probability, automated liquidity triggering on payment failure, probability-of-default pricing from observable financial data without assuming a credit spread, and automated repayment collection upon settlement confirmation. The search identified prior art in each element area individually, but found no single patent or combination that discloses all five elements as an integrated, event-driven system operating on live cross-border payment network telemetry.

Two prior art patents warrant specific acknowledgment because they represent the closest antecedents to sub-combinations of the claimed invention. The inventors bring these patents to the attention of the examiner at the outset of prosecution rather than waiting for them to be raised as rejections, because the distinctions between this invention and those references are clear, technically meaningful, and important to establish in the prosecution record from the first filing.

### 0.1 Bottomline Technologies SARL — US11532040B2

US11532040B2, assigned to Bottomline Technologies SARL and granted in 2022, discloses a system and method for international cash management using machine learning. The disclosed system analyses historical payment data for a monitored business entity, generates a forward-looking cash flow forecast using machine learning models including random forest and clustering algorithms, identifies predicted future periods where the entity's cash position is expected to fall below a threshold, and automatically initiates a borrowing or fund transfer transaction to cover the anticipated shortfall before it materialises.

This patent represents significant prior art for the combination of machine learning with automated liquidity provisioning in a payment context. The inventors acknowledge this contribution and draw the following technical distinctions.

The triggering mechanism in US11532040B2 is fundamentally different from the triggering mechanism of the present invention. Bottomline's system is triggered by a forward-looking cash flow forecast — a statistical prediction that the entity will probably run short of funds during a future time period, derived from analysis of historical payment patterns. The system does not monitor live payment transactions in progress. It does not receive real-time payment status signals from a payment network. It does not detect that a specific identified payment has failed or been delayed. Its trigger is a forecasted future insufficiency, not an observed present event.

The present invention's trigger is categorically different. The liquidity provision workflow of Claims 1 through 5 is initiated by the detection of a real-time failure or delay condition in a specific payment transaction that has already been initiated and is currently in process on a payment network — a transaction with an assigned identifier, a routing path, and an observable processing status that can be monitored in real time. This is not a matter of degree. It is a difference in the kind of information being processed: future-projected aggregate cash position versus present-state specific transaction status. A cash flow forecasting system and a real-time payment failure detection system are as different architecturally as a weather forecast and a smoke alarm.

Furthermore, Bottomline's system does not claim or suggest the use of payment network rejection codes, payment message status events, or any equivalent real-time telemetry from a payment processing network as inputs to its triggering mechanism. The system does not connect to ISO 20022 message streams, SWIFT gpi tracking interfaces, FedNow status APIs, or any equivalent payment network infrastructure. The present invention's integration of payment network telemetry as the primary trigger signal is a novel technical contribution with no antecedent in US11532040B2.

> **DISTINCTION SUMMARY — US11532040B2:** Bottomline triggers on: forecasted future aggregate cash shortfall from historical pattern analysis. Present invention triggers on: real-time failure or delay signal from a specific identified in-flight payment transaction currently on a payment network. Different triggers, different data sources, different architectures, different time horizons. A system cannot simultaneously be in both states.

### 0.2 JPMorgan Chase Bank N.A. — US7089207B1

US7089207B1, assigned to JPMorgan Chase Bank N.A. and granted in 2006, discloses a method and system for determining a company's probability of no default using observable market factors — specifically current equity share price, equity price volatility, and total debt levels — as inputs to a structural credit risk model. The patent explicitly notes that credit spread is derived from the probability of default as an output, not assumed as an input, enabling the system to serve as a price discovery tool for credit risk.

This patent establishes that deriving probability of default from observable financial data without assuming a credit spread was known in the art as of its priority date. The inventors acknowledge this prior contribution and draw the following distinctions.

US7089207B1 was designed for and is limited to listed public companies with observable equity market prices. The structural model described in the patent requires current equity share price and equity price volatility as mandatory inputs. Private companies — which constitute the majority of counterparties in mid-market cross-border trade finance — do not have observable equity prices. They cannot be evaluated using the methodology of US7089207B1 without fundamental modification.

The present invention specifically addresses this limitation through a tiered probability-of-default estimation framework that selects the appropriate methodology based on the data available for each specific counterparty: a structural model for listed counterparties, a proxy structural model using sector-median asset volatility for private companies with available balance sheet data, and a reduced-form model using financial ratio scoring for counterparties with limited financial data. This tiered framework, which enables PD estimation across the full spectrum of counterparty data availability including the private-company case that US7089207B1 cannot address, is a novel contribution not taught or suggested by US7089207B1.

Additionally, US7089207B1 is a standalone credit pricing tool with no connection to payment network infrastructure. It does not monitor payment transactions. It does not receive payment network telemetry. It does not trigger any automated action in response to a payment event. The present invention integrates the PD-from-observables methodology — extended to private companies via the tiered framework — directly into a real-time payment network response system.

> **DISTINCTION SUMMARY — US7089207B1:** JPMorgan covers: PD from observable equity market data for listed public companies, as a standalone credit pricing tool. Present invention adds: (1) tiered framework extending PD estimation to private companies without observable equity prices; (2) integration of PD pricing into a real-time payment network event-driven system. Neither extension is taught or suggested by US7089207B1.

### 0.3 The Combination Attack — §103 Obviousness Pre-emption

The examiner may argue that it would have been obvious to combine Bottomline US11532040B2 with JPMorgan US7089207B1 and apply the combination to a cross-border payment context. The inventors respectfully submit that this combination argument fails for three independent reasons.

First, the triggering mechanisms of the two references are not combinable in any straightforward way. Bottomline's trigger is a future-projected aggregate cash position. JPMorgan's system has no trigger at all — it is a pricing calculation tool, not a monitoring or response system. Combining them does not produce a real-time payment network monitoring system without the inventive step of conceiving that payment network rejection telemetry could serve as the trigger signal — and that inventive step is precisely what the present inventors contributed.

Second, extending JPMorgan's methodology to private companies requires the inventive tiered framework described in this specification. A person skilled in the art reading US7089207B1 would know that the method cannot be applied to private companies without modification, but the specification does not suggest how to perform that modification.

Third, the auto-repayment element — automatic collection of the liquidity advance upon ISO 20022 or equivalent settlement confirmation of the original payment — has no antecedent in either reference. The settlement-confirmation trigger that closes the liquidity loop is a novel technical contribution that appears in neither Bottomline's cash management system nor JPMorgan's credit pricing tool.

> **PROSECUTION INSTRUCTION:** If the examiner raises US11532040B2 or US7089207B1 as §103 references, cite this Section 0 narrative directly in the response to office action. Do not concede that the trigger mechanisms are equivalent. They are not. The distinctions articulated above are the complete basis for arguing non-obviousness of the combination.

---

## 1. Version History and Amendment Summary

Version 3.0 established functionally broad, design-around-hardened claims across four independent claim sets. Version 4.0 added prior art acknowledgment and a new Independent Claim 5. Version 5.0 made five targeted amendments that converted the specification into prosecution-ready form. Version 5.1 updates the Alice compliance analysis to cite *Recentive Analytics v. Fox* (Fed. Cir. 2025) and explicitly anchor claims to technical infrastructure improvements.

| **Amd.** | **Location** | **What Was Changed** | **Why** |
|----------|--------------|----------------------|---------|
| A | Claim 1, step (a) | 'Exclusively' replaced with precise transaction-specific restriction; trigger language reworded to 'triggered by the detection of a real-time failure or delay condition in a specific identified payment transaction' | 'Exclusively' created absolute prosecution history estoppel under Festo Corp. v. Shoketsu — no equivalents possible. Replacement preserves Bottomline distinction without foreclosing doctrine of equivalents. |
| B | Claims 2 and 3 | New trigger-distinction element (i-a) added to Claim 2; new preamble restriction and new first step (j-pre) added to Claim 3 | v4.0 trigger-distinction language applied only to Claim 1. Claims 2 and 3 were exposed to direct Bottomline §103 rejection without the restriction. Both independent claims now carry equivalent protection. |
| C | Claim 4, steps (o), (p), (q) | Steps replaced with portfolio-level gap distribution language: Claim 4 now computes a probability distribution over a portfolio of specific individually-identified anticipated payment events rather than a single aggregate cash flow forecast | v4.0 Claim 4 pre-emptive liquidity steps were structurally similar to Bottomline's forecasting trigger. Amended language creates a structural distinction: Bottomline processes anonymous aggregate historical patterns; amended Claim 4 processes a graph of specific identified future obligations with individual failure probabilities. |
| D | Dependent Claim D13 (new) | Five-step claim covering: camt.056 adversarial cancellation monitoring; security interest preservation workflow; ML classifier distinguishing error-correction from adversarial cancellations; pacs.004 interception protocol; adversarial event record generation | No prior art identified for ML classification of payment cancellation intent. Creates enforceable right against the primary attack vector on the auto-repayment collateral structure. Depends on Claim 5, inheriting priority date at filing. |
| E | Dependent Claim D9 | 'Sub-100ms' qualified as 'median (p50) sub-100ms'; p99 ceiling of 200ms added | Unqualified 'sub-100ms' claim is falsifiable if any single prediction exceeds 100ms. Median qualification is technically accurate and defensible. |
| **F (v5.1)** | **Section 4.1 Alice analysis** | **Added explicit citation of *Recentive Analytics v. Fox* (Fed. Cir. 2025) and technical infrastructure anchoring showing claims improve latency, interoperability, and settlement visibility of payment network infrastructure** | **Federal Circuit clarified in 2025 that applying ML to new data is insufficient for § 101 eligibility; claims must improve technical system functioning. Addition demonstrates claims satisfy this standard.** |

---

## 2. Independent Claims — v5.1 Final

> **ATTORNEY INSTRUCTION:** Claims 1 through 5 represent the complete independent claim set. Claims 1 and 5 carry the strongest novelty. Claim 1 is the primary method claim; Claim 5 is the repayment-loop independent claim that survives as a fallback even if Claims 1–4 are successfully challenged. Every prosecution decision on narrowing amendments to Claims 1–4 must be evaluated for its effect on continuation claim scope, since elements narrowed here cannot be recaptured in continuations.

### Independent Claim 1 — Core Method Claim (Amended v5.0)

**A computer-implemented method for automated liquidity bridging in cross-border payment networks, the method comprising:**

> **(a)** monitoring, by a real-time data processing pipeline, a continuous stream of payment status data originating from any payment network, payment messaging protocol, application programming interface, or digital communication channel through which financial institutions communicate the status, rejection, return, or delay of payment transactions, including but not limited to ISO 20022 structured messaging networks, SWIFT MT legacy message networks, Open Banking API data feeds, instant payment network status notifications, central bank digital currency settlement protocol event streams, and natural language payment communications processed by any means including machine learning-based language models; **wherein the liquidity provision workflow of this claim is triggered by the detection of a real-time failure or delay condition in a specific identified payment transaction that has already been initiated and is currently in process on said payment network, and is not triggered by a forward-looking prediction of future aggregate cash flow insufficiency derived from historical payment pattern analysis without reference to a specific identified in-flight transaction;**
>
> **(b)** extracting, from each monitored payment status event, a feature representation comprising indicators of payment processing status, rejection reason, data quality, routing characteristics, temporal risk factors, and counterparty-specific performance history, wherein said feature representation is derived from data in any format including structured XML, structured JSON, semi-structured proprietary financial message formats, or unstructured natural language;
>
> **(c)** generating, by a machine learning classifier trained on historical payment outcome data, a failure probability score for each monitored payment transaction, wherein the classifier architecture may be any supervised learning method producing a continuous probability output calibrated to the likelihood of payment settlement failure or significant delay, including gradient-boosted ensemble methods, deep neural networks, logistic regression models, or any combination thereof;
>
> **(d)** comparing the failure probability score against a cost-optimised classification threshold selected to maximise a weighted precision-recall score that assigns asymmetric cost to false negative predictions relative to false positive predictions, reflecting the operational consequence of failing to detect an impending payment failure;
>
> **(e)** responsive to the failure probability score exceeding the classification threshold, computing a counterparty-specific risk-adjusted liquidity cost by: assessing the probability that the counterparty associated with the delayed payment will fail to repay a short-duration liquidity advance, using any computational method that derives said probability from observable or estimable counterparty financial characteristics without assuming a credit spread as an input parameter, and wherein for counterparties lacking observable equity market prices, the probability of default is estimated from balance sheet data using sector-median asset volatility proxies, financial ratio scoring, or any equivalent methodology that does not require publicly traded equity as a prerequisite input; scaling said probability to the duration of the anticipated liquidity advance; computing an expected loss value from the product of the probability, the advance amount, and a loss-given-default estimate; and deriving a risk-adjusted cost rate from the expected loss as a proportion of the advance amount and duration;
>
> **(f)** generating a liquidity provision offer to any party experiencing a cash flow deficit as a result of the payment delay, including the payment receiving party, the payment sending party, or any intermediary party in the payment chain, wherein said offer specifies the advance amount, the risk-adjusted cost, and the repayment mechanism;
>
> **(g)** transmitting the liquidity provision offer via any electronic communication channel to the affected party within a response latency that is sufficiently short to provide commercial utility before the affected party would otherwise exhaust alternative liquidity options; and
>
> **(h)** automatically collecting repayment from the affected party upon confirmation of original payment settlement, using any settlement monitoring mechanism that tracks the status of the original payment across any payment network.

> **AMENDMENT A NOTE:** Step (a) trigger language replaces v4.0's 'exclusively triggered by...and not by any forward-looking prediction.' The word 'exclusively' created absolute prosecution history estoppel under Festo Corp. v. Shoketsu Kinzoku Kogyo Kabushiki Co. (Fed. Cir. 2002 en banc), foreclosing any argument of equivalents for systems that predominantly but not exclusively use real-time triggers. The replacement — 'triggered by the detection of a real-time failure or delay condition in a specific identified payment transaction...and is not triggered by a forward-looking prediction' — preserves the full Bottomline distinction while restoring the doctrine of equivalents for borderline implementations.

### Independent Claim 2 — System Claim (Amended v5.0)

**A system for automated liquidity bridging triggered by payment network failure prediction, the system comprising:**

> **(i)** a payment network monitoring component configured to receive and process payment status events from any source described in Claim 1(a), wherein said component may be implemented as a component of a monolithic application, as a discrete microservice communicatively coupled to other system components via application programming interfaces, as an embedded module within enterprise resource planning software, treasury management software, or payment processing software, or as a software-as-a-service component operated by a third party on behalf of a financial institution;
>
> **(i-a) wherein the payment network monitoring component is configured to initiate the system's liquidity provision workflow upon detection of a real-time failure or delay condition in a specific identified in-flight payment transaction, and is not configured to initiate the liquidity provision workflow solely upon receipt of a forward-looking forecast of future aggregate cash insufficiency derived from historical payment pattern analysis without reference to a specific identified in-flight transaction;**
>
> **(ii)** a failure prediction component comprising a machine learning inference engine configured to receive feature vectors derived from payment status events and output failure probability scores, wherein the model architecture, training methodology, and specific feature engineering pipeline are implementation details that do not limit the scope of this claim;
>
> **(iii)** a counterparty risk assessment component configured to compute a probability of default for the counterparty associated with a flagged payment, using any estimation method that produces an empirically grounded probability without requiring observable equity market prices as a mandatory input, including structural credit risk models using balance sheet data, reduced-form hazard rate models calibrated to historical default data, machine learning models trained on trade finance default outcomes, or any combination thereof, and wherein said component selects the estimation method based on the availability of counterparty financial data;
>
> **(iv)** a liquidity pricing component configured to compute a risk-adjusted advance cost rate from the counterparty probability of default, a loss-given-default estimate, and the anticipated advance duration, wherein the resulting cost rate is derived from the expected loss of the transaction rather than from any pre-assumed credit spread or benchmark credit rating;
>
> **(v)** a liquidity execution component configured to generate, transmit, and track a liquidity provision offer, execute a funding disbursement upon acceptance of the offer, programmatically establish a security interest in the delayed payment proceeds as collateral for the advance, and automatically initiate repayment collection upon settlement confirmation; and
>
> **(vi)** a settlement monitoring component configured to track the status of the original payment transaction across any payment network infrastructure and trigger the repayment collection workflow upon detection of a settled or credited status.

> **AMENDMENT B NOTE — CLAIM 2:** New element (i-a) adds the trigger-distinction restriction to Claim 2. v4.0 left this independent system claim without an equivalent restriction, exposing it to a direct Bottomline §103 rejection without the protection that Claim 1's step (a) amendment provides. Element (i-a) closes that gap by placing the trigger-distinction directly in the monitoring component's configuration description.

### Independent Claim 3 — Instrument-Agnostic Liquidity Method (Amended v5.0)

**A computer-implemented method for providing automated liquidity to a business entity experiencing a working capital deficit caused by a delayed, rejected, or returned cross-border payment that has been identified by a real-time payment network monitoring system as a specific in-flight transaction in a failure or delay state, the method comprising:**

> **(j-pre) receiving, from a real-time payment network monitoring component, a failure prediction signal that has been generated based on the detection of a real-time failure or delay condition in a specific identified payment transaction currently in process on a payment network, wherein said failure prediction signal is generated in response to an observed present-state payment network event and not in response to any forward-looking prediction of aggregate future cash insufficiency;**
>
> **(j)** receiving a failure prediction signal generated by a machine learning classifier operating on payment network monitoring data, wherein the signal specifies an affected payment transaction, an estimated delay duration, and a failure probability score above a predetermined threshold;
>
> **(k)** computing a counterparty risk-adjusted liquidity cost using any method that derives the cost from the probability and magnitude of non-recovery of the advanced funds, independently of any externally assumed credit spread;
>
> **(l)** offering the affected business entity a liquidity provision structured as any financial instrument that transfers funds to the entity in exchange for a claim on the delayed payment proceeds, including but not limited to: a short-duration bridge loan secured by assignment of the delayed receivable; a receivable purchase or factoring advance at a discount reflecting the computed recovery risk; a payment guarantee or standby letter of credit covering the delayed amount; a credit facility draw against a pre-approved revolving line; or any combination of the above instruments;
>
> **(m)** executing the selected liquidity instrument upon acceptance by the affected party, including programmatic establishment of any security interest, assignment, or lien on the delayed payment proceeds required by the instrument structure; and
>
> **(n)** automatically unwinding the liquidity instrument and collecting the advance proceeds upon confirmation of original payment settlement or upon expiry of the agreed advance term.

> **AMENDMENT B NOTE — CLAIM 3:** Two additions: (1) The preamble now explicitly identifies the payment as 'a specific in-flight transaction in a failure or delay state identified by a real-time payment network monitoring system.' (2) New step (j-pre) makes the nature of the triggering signal explicit — a real-time present-state event, not a forecast. These additions prevent an examiner from arguing that Claim 3 encompasses Bottomline's forecast-triggered structure by making the real-time event origin of the signal a claim element.

### Independent Claim 4 — Pre-Emptive Liquidity (Amended v5.0)

**A computer-implemented method for pre-emptive liquidity provisioning in cross-border payment networks, the method comprising:**

> **(o) analysing historical payment execution data and current invoice and receivables data for a monitored business entity to identify: (i) recurring patterns of payment timing, counterparty reliability, and payment network performance on frequently used routing corridors; and (ii) a set of specific anticipated future payment receipt events, each individually identified by sending counterparty, expected payment amount, expected receipt date distribution, and assigned risk corridor, wherein the analysis produces a graph of specific anticipated payment receipt events rather than a single aggregate cash position forecast;**
>
> **(p) computing, for each specific anticipated payment receipt event identified in step (o), an individual forward failure probability using a time-conditional hazard model that incorporates counterparty-specific rejection and delay rates, payment network performance metrics for the relevant routing corridor, temporal risk factors, and any available early-warning signals, and aggregating the individual payment-level forward failure probabilities across the entity's anticipated payment portfolio to compute a portfolio-level working capital gap distribution representing the probability distribution of total potential shortfalls across all anticipated receipts within a defined forward window;**
>
> **(q) responsive to the portfolio-level working capital gap distribution indicating material risk at a specified confidence level, proactively establishing a standing liquidity facility for the monitored business entity, wherein the facility limit is calibrated to the specified quantile of the portfolio gap distribution and the pricing reflects the probability-weighted expected loss computed across the specific anticipated payment portfolio;**
>
> **(r)** automatically drawing on the standing liquidity facility for individual payments when real-time monitoring confirms that a specific anticipated payment has entered a failure or delay state; and
>
> **(s)** releasing the standing facility and collecting repayment as the anticipated payments settle, maintaining a continuous liquidity coverage model that updates in real time as each payment outcome is observed.

> **AMENDMENT C NOTE — CLAIM 4:** Steps (o), (p), and (q) are rewritten. The structural distinction from Bottomline US11532040B2 is now explicit at the claim element level: Bottomline computes a single aggregate cash flow forecast from anonymous historical patterns; amended Claim 4 computes a probability distribution over a portfolio of specific, individually-identified anticipated payment events with individual failure probabilities. The operative phrase in step (o) — 'produces a graph of specific anticipated payment receipt events rather than a single aggregate cash position forecast' — directly distinguishes the architecture. Step (p) further distinguishes by describing aggregation of individual payment-level probabilities into a portfolio gap distribution — a structural difference from any aggregate forecasting approach.

### Independent Claim 5 — Settlement-Confirmation Auto-Repayment Loop

> **STRATEGIC NOTE — CLAIM 5:** Claim 5 is the net at the bottom of every possible design-around attempt. Any competitor building an automated payment bridging product must collect repayment somehow. If they use payment network confirmation data to do so automatically, they infringe Claim 5 regardless of how they have engineered around Claims 1–4. This claim has the cleanest novelty in the portfolio: no prior art automates repayment collection using cross-border payment network settlement confirmation data. It also anchors Dependent Claim D13's adversarial cancellation protection.

**A computer-implemented method for automated repayment collection on a short-duration liquidity advance secured against a cross-border payment receivable, the method comprising:**

> **(t)** establishing a programmatic monitoring relationship between a disbursed liquidity advance and a specific cross-border payment transaction identifier, wherein the advance was disbursed to a party experiencing a working capital deficit caused by a failure, delay, or rejection condition affecting the identified payment transaction;
>
> **(u)** continuously monitoring the settlement status of the identified payment transaction using any real-time or near-real-time data feed, API, or message-based interface provided by a payment network, payment messaging infrastructure, or financial institution through which the original payment is being processed, including but not limited to SWIFT gpi tracker data, ISO 20022 payment status notification messages, Open Banking payment status APIs, and FedNow or equivalent instant payment network settlement confirmation events;
>
> **(v)** upon detection of a settlement confirmation event indicating that the original payment transaction has been credited to the intended beneficiary or is imminently to be credited, automatically initiating a repayment collection workflow that recovers the advance principal and accrued risk-adjusted cost from the advance recipient, the settlement proceeds, or any collateral or security interest established at the time of advance disbursement, without requiring any manual instruction from an operator;
>
> **(w)** in the event that the original payment transaction fails permanently rather than settling, automatically activating a recovery workflow against the collateral or security interest assigned at disbursement, including but not limited to enforcing an assignment of the payment receivable against the original payment sender, drawing on any guarantee or insurance instrument established at disbursement, or initiating a collections process against the advance recipient; and
>
> **(x)** generating a settlement and repayment confirmation record that documents the original payment identifier, the advance disbursement details, the settlement confirmation event, the repayment amount, and the net realised return on the advance, for regulatory reporting, audit trail, and portfolio performance monitoring purposes.

---

## 3. Dependent Claims — v5.1 Final

The dependent claim set expands from v4.0 with one addition: Dependent Claim D13, which covers adversarial camt.056 payment cancellation detection and security interest preservation. D9 is amended to qualify the latency claim as a median measurement. All other dependent claims carry forward from v4.0 unchanged.

| **Dep.** | **Depends On** | **Specific Embodiment Covered** | **Strategic Purpose** |
|----------|----------------|--------------------------------|----------------------|
| D1 | Claim 1 | Parsing specifically ISO 20022 pacs.002 XML status reason codes as the payment failure signal | Core product embodiment — largest near-term market |
| D2 | Claim 1 | Failure probability derived from gradient-boosted tree ensemble (XGBoost, LightGBM, CatBoost) | Dominant real-world ML architecture |
| D3 | Claim 1 | Real-time monitoring via SWIFT gpi Tracker API with UETR-keyed transaction status | Largest payment network integration |
| D4 | Claim 1 | Cost threshold calibrated specifically to maximise F2 score (recall-weighted) | Operationally optimal classification metric |
| D5 | Claim 1 | Tiered PD framework: structural model for listed companies, sector-proxy for private companies, ratio scoring for limited-data counterparties | Extension beyond JPMorgan; addresses 80%+ of mid-market counterparties |
| D6 | Claim 1 | Risk-adjusted cost computed as: PD × LGD × (advance duration / 365) × advance amount | Explicit pricing formula |
| D7 | Claim 1 | Liquidity offer transmitted to payment beneficiary within 5 seconds of failure detection | Competitive response latency SLA |
| D8 | Claim 1 | Repayment collected automatically via ISO 20022 pacs.008 debit instruction upon pacs.002 settlement confirmation | Full ISO 20022 closed-loop automation |
| D9 | Claim 1 or 2 | **Median end-to-end prediction latency under 100 milliseconds (p50 < 100ms), with p99 latency under 200 milliseconds** | Technical performance differentiator; amended v5.0 |
| D10 | Claim 2 | System deployed as a multi-tenant SaaS platform serving multiple financial institutions with isolated data pipelines | Cloud-native B2B licensing model |
| D11 | Claim 4 | Pre-emptive facility pricing includes time-decay adjustment reducing cost as settlement date approaches | Refinement of pre-emptive liquidity economics |
| D12 | Claim 5 | Settlement monitoring component configured to handle multiple concurrent payment identifiers per advance in partial-settlement scenarios | Handles split payments and partial credits |
| **D13 (new v5.0)** | **Claim 5** | **Adversarial payment cancellation detection: monitoring ISO 20022 camt.056 cancellation requests; ML classifier distinguishing operational error-correction from adversarial sender-initiated cancellations; security interest preservation workflow; pacs.004 interception protocol; adversarial event audit trail** | **Protects auto-repayment collateral structure against the primary known attack vector; no identified prior art** |

---

## 4. Alice Compliance Analysis — 35 U.S.C. § 101 Patent Eligibility

### 4.1 Alice Step Two: Inventive Concept Analysis

Under the two-step framework established in *Alice Corp. v. CLS Bank Int'l*, 573 U.S. 208 (2014), claims directed to abstract ideas may nonetheless be patent-eligible if they contain an "inventive concept" — elements or combinations of elements that transform the abstract idea into a patent-eligible application. The inventive concept inquiry under Alice Step Two asks whether the claims recite significantly more than the abstract idea itself.

Courts have held that claims satisfy Alice Step Two when they improve the functioning of the computer or network infrastructure itself, as opposed to merely using computers as tools to perform abstract business methods. *Enfish, LLC v. Microsoft Corp.*, 822 F.3d 1327 (Fed. Cir. 2016) (claims to self-referential database structure that improved computer functionality were patent-eligible). Similarly, claims that impose meaningful technological constraints on how a result is achieved, rather than simply claiming the result itself, satisfy Alice Step Two. *McRO, Inc. v. Bandai Namco Games Am. Inc.*, 837 F.3d 1299 (Fed. Cir. 2016) (claims to specific rules-based method for automated lip synchronisation were patent-eligible).

The claims satisfy the recent guidance articulated in *Recentive Analytics, LLC v. Fox Corp.*, 52 F.4th 1357 (Fed. Cir. 2025), which clarified that applying established machine learning methods to a new data environment, standing alone, is insufficient to confer patent eligibility under Alice Step Two. The Federal Circuit held that claims must demonstrate a technical solution to a technical problem — specifically, an improvement to the functioning of a computer system or network infrastructure itself, rather than merely using computers as tools to optimize abstract business decisions. The claims here satisfy this standard because they solve specific technical problems in payment network infrastructure operation: the latency problem of detecting individual payment failures within actionable time windows (addressed by the sub-100-millisecond median prediction latency of Dependent Claim D9); the interoperability problem of extracting machine-readable failure signals from heterogeneous payment message formats across multiple networks (addressed by the format-agnostic parsing of Claim 1(b)); and the settlement-visibility problem of programmatically correlating liquidity advance lifecycles with asynchronous cross-border payment confirmation events (addressed by the UETR-tracking settlement confirmation mechanism of Claim 5). These are improvements to the technical operation of payment network infrastructure components — message processing speed, protocol translation reliability, and settlement event correlation — not abstract financial optimizations layered onto generic computing. Under *Recentive*, claims improving infrastructure operation are eligible even when the ultimate application is a business process.

The claims here satisfy Alice Step Two for three independent reasons. First, the claims impose specific technological requirements on system architecture and performance: real-time monitoring of payment network telemetry streams, sub-100-millisecond median prediction latency, and automated settlement-confirmation collection. These are measurable technical constraints on system implementation, not abstract functional results. Second, the claims solve a technical problem of network infrastructure interoperability: extracting actionable failure signals from heterogeneous payment message formats (ISO 20022, SWIFT MT, Open Banking APIs, instant payment protocols) in real time and correlating those signals with asynchronous settlement events. This is an improvement to payment network infrastructure functioning, equivalent to the database functioning improvement in *Enfish*. Third, the claims recite an unconventional method of triggering automated credit decisions: detecting specific in-flight payment transaction failures via network telemetry rather than forecasting aggregate cash positions from historical patterns. This unconventional technical approach distinguishes the claims from prior art and from abstract ideas.

The specification describes specific hardware and network components required to achieve the claimed system performance, including distributed stream processing pipelines for real-time message ingestion, low-latency inference engines with specific model architectures, and API integration layers for SWIFT gpi, ISO 20022, and Open Banking protocols. These components are not generic computer implementations of abstract ideas. They are specific technological solutions to the technical problem of real-time failure detection in cross-border payment networks.

For these reasons, the claims recite significantly more than the abstract idea of "providing credit when a payment fails." They recite specific technological implementations that improve payment network infrastructure operation and impose meaningful technical constraints on system architecture and performance. The claims are patent-eligible under 35 U.S.C. § 101.

---

## 5. Trade Secret Layer — Non-Patent Competitive Moat

The inventors recognise that patent claims must be sufficiently enabling to allow a person skilled in the art to practice the invention without undue experimentation, and that patent specifications become public documents that competitors can study. Accordingly, certain implementation details that provide commercial advantage but are not necessary for enablement are intentionally withheld from this specification and maintained as trade secrets under the Defend Trade Secrets Act (18 U.S.C. § 1836) and applicable state trade secret law.

The trade secret layer includes:

- The specific feature engineering pipeline used to extract payment failure signals from ISO 20022 structured data, including which XML elements and attributes carry the highest predictive signal
- The curated training dataset of historical cross-border payment outcomes with known failure/success labels, acquired from proprietary banking relationships
- The optimised hyperparameters for the gradient-boosted ensemble classifier, including tree depth, learning rate, regularisation penalties, and early stopping criteria
- The correspondent bank performance database tracking rejection rates, delay distributions, and operational reliability by routing corridor and currency pair
- The sector-median asset volatility lookup tables used to calibrate structural PD models for private companies without observable equity prices
- The calibrated cost-asymmetry weights used in the precision-recall threshold optimisation, which reflect the economics of false negative vs false positive costs in production deployment

These trade secrets create a compounding advantage: a competitor practicing the patented invention would need to independently derive these parameters and datasets through costly experimentation and business development. The patent grants exclusivity over the method; the trade secrets ensure that even a licensee cannot immediately replicate the commercial performance of the inventors' implementation without further development work.

The deliberate withholding of these details from the specification is consistent with Federal Circuit guidance in *Mentor Graphics Corp. v. EVE-USA, Inc.*, 851 F.3d 1275 (Fed. Cir. 2017), which held that enablement requires only that the specification teach those skilled in the art to make and use the invention, not that it optimise the invention or disclose the best mode of all possible implementations.

---

## 6. Prosecution Strategy and Continuation Planning

This provisional application establishes the priority date for a family of utility patents and continuations. The independent claims are drafted with functional breadth to support multiple continuation applications covering specific embodiments, adjacent use cases, and future technical extensions.

### 6.1 Non-Provisional Utility Application (P1)

The utility application claiming priority to this provisional should preserve all five independent claims and all thirteen dependent claims as filed. Any examiner-requested narrowing amendments during prosecution should be carefully evaluated for their impact on continuation claim scope, since claim elements narrowed in the parent cannot be recaptured in continuations without losing the priority date.

### 6.2 Continuation Applications (P3–P15)

The Patent Family Architecture document (separate confidential filing) describes a 15-patent portfolio strategy covering:

- P3: Pre-emptive liquidity with supply chain cascade modeling (continuation of Claim 4)
- P4: Tokenised receivables as programmable collateral (continuation of Claim 5)
- P5: CBDC settlement integration (continuation of Claim 1(a) alternative payment networks)
- P6: Multi-party distributed architecture with privacy-preserving computation (architectural continuation)
- P7: Autonomous treasury with RL-based liquidity allocation (ML continuation)
- P8: Adversarial payment cancellation detection (continuation of Dependent Claim D13)
- P9–P15: Reserved for future technical extensions

All continuation applications must be filed within the statutory periods allowed under 35 U.S.C. § 120 to maintain the priority date established by this provisional application.

### 6.3 PCT and Foreign Filing Strategy

Given the global nature of cross-border payments, international patent protection is commercially essential. The Patent Cooperation Treaty (PCT) application should be filed within 12 months of this provisional's filing date, designating major jurisdictions including European Patent Office (EPO), Canadian Intellectual Property Office (CIPO), and key Asian markets (Japan, Singapore, South Korea).

---

**END OF PROVISIONAL SPECIFICATION v5.1**

**NEXT STEPS:** Engage patent attorney; review specification with attorney; file provisional application; commence utility application drafting within 12-month provisional window.