# PROVISIONAL PATENT APPLICATION

# TECHNICAL SPECIFICATION

# VERSION 5.3 — PROSECUTION-READY

*System and Method for Automated Liquidity Bridging Triggered by Real-Time Payment Network Failure Detection*

| **Field** | **Value** |
|-----------|-----------|
| Document Version | 5.3 — Prosecution-Ready (Claim Support & Filing Strategy Alignment) |
| Supersedes | v5.2 — Prosecution-Ready (§101 Re-Anchor) |
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
| v5.1 | *Recentive* compliance: Section 4.1 Alice analysis updated to cite *Recentive Analytics v. Fox* (Fed. Cir. 2025) and explicitly anchor claims to technical infrastructure improvements. **[SUPERSEDED — Recentive citation removed in v5.2. See below.]** |
| **v5.2** | ***Recentive Analytics v. Fox* citation removed from Section 4.1 and all materials. That case is adverse authority — the Federal Circuit held the claims in Recentive patent-ineligible under § 101. Citing it in support of eligibility is a prosecution error that invites examiner rebuttal. §101 analysis re-anchored exclusively on *Enfish, LLC v. Microsoft Corp.* (Fed. Cir. 2016) and *McRO, Inc. v. Bandai Namco Games Am. Inc.* (Fed. Cir. 2016). All technical infrastructure improvement arguments preserved and strengthened under those anchors. Amendment table entry F revised. No other claim, prior art, or prosecution strategy changes.** |
| **v5.3** | **Claim-support and filing-strategy alignment update: added Section 0.4 addressing US20250086644A1; added written-description support paragraph for natural-language payment communications; made Claim 5 self-contained by adding an express disbursement step before monitoring; added claim-specific §101 support for Claims 3 and 4; corrected continuation-planning section to align with the portfolio architecture, including Japan and Hong Kong in foreign strategy and an explicit continuation-versus-CIP caveat.** |

---

## WHAT CHANGED IN v5.3

Version 5.3 makes four targeted improvements to prosecution readiness without changing the portfolio thesis.

First, Section 0 adds a new prior-art distinction narrative for US20250086644A1. The current specification already addressed Bottomline and JPMorgan, but an examiner could also combine Bottomline with a newer real-time payment-monitoring reference. Section 0.4 now pre-empts that vector directly.

Second, Claim 5 is made fully self-contained by adding an explicit disbursement step before the settlement-monitoring relationship is established. This removes any argument that the claim presupposes an already-disbursed advance without claiming the disbursement event itself.

Third, the written-description record is strengthened for two claim families that were at risk of avoidable challenge. Section 1.1 now expressly supports natural-language payment communications as an alternative input channel for Claim 1(a), and Section 4 adds claim-specific §101 support for Claims 3 and 4 rather than relying only on the general Alice narrative.

Fourth, the continuation-planning and foreign-filing sections are reconciled to the portfolio architecture document. The text now uses the current portfolio mapping, adds Japan and Hong Kong to the filing strategy, and states explicitly that some long-horizon extensions may need CIP treatment if prosecution counsel concludes the parent disclosure is insufficient for pure continuation treatment.

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

### 0.4 US20250086644A1 — Real-Time Payment Monitoring Reference

The prior art matrix also identifies US20250086644A1 as a potentially relevant reference because it appears to concern real-time monitoring of payment events and automated system response to observed failure signals. To the extent an examiner combines US20250086644A1 with Bottomline US11532040B2 or any other liquidity-management reference, the present specification distinguishes that combination on the same integrated-system grounds set out above.

US20250086644A1 may speak to real-time event monitoring, but the present invention is not merely a monitoring system. The claims here integrate five elements into a single event-driven architecture: transaction-specific payment failure detection, calibrated machine-learning classification, counterparty risk-adjusted liquidity pricing without assumed credit spread, automated offer generation and disbursement, and settlement-confirmation auto-repayment keyed to the original in-flight payment identifier. The inventors are not aware of any disclosure in US20250086644A1 of that complete closed-loop architecture.

Even if US20250086644A1 were combined with Bottomline, the combination would still require the inventive step of tying transaction-specific payment telemetry to automated settlement-linked repayment and to the tiered PD framework for private and thin-file counterparties. The monitoring reference would at most provide one component of the overall architecture. It would not teach the integrated trigger-to-pricing-to-repayment loop that defines the present claims.

---

## 1. Version History and Amendment Summary

### 1.1 Additional Written Description Support — Natural Language Payment Communications

In some embodiments, payment status data is communicated in unstructured natural language rather than in structured payment network messages. Examples include email instructions between correspondent operations teams, bank portal messages, support tickets, chat messages, and recorded or transcribed voice communications concerning the status, rejection, return, or delay of a specific payment. In these embodiments, the payment monitoring component applies a natural language processing pipeline to extract payment identifiers, status indicators, counterparties, timestamps, and rejection or delay reasons from the unstructured text, and normalises the extracted fields into the system's standard internal event representation.

The natural language processing pipeline may be implemented using any text classification, sequence labelling, information extraction, or transformer-based language modelling technique fine-tuned on financial communications corpora. The output of the pipeline is not the natural-language text itself, but a structured event record compatible with the same downstream feature extraction and inference pipeline used for ISO 20022, SWIFT MT, API, or other structured message formats.

Version 3.0 established functionally broad, design-around-hardened claims across four independent claim sets. Version 4.0 added prior art acknowledgment and a new Independent Claim 5. Version 5.0 made five targeted amendments that converted the specification into prosecution-ready form. Version 5.1 updated the Alice compliance analysis. Version 5.2 removes the *Recentive* citation from Section 4.1 and re-anchors the §101 analysis exclusively on *Enfish* and *McRO*.

| **Amd.** | **Location** | **What Was Changed** | **Why** |
|----------|--------------|----------------------|---------|
| A | Claim 1, step (a) | 'Exclusively' replaced with precise transaction-specific restriction; trigger language reworded to 'triggered by the detection of a real-time failure or delay condition in a specific identified payment transaction' | 'Exclusively' created absolute prosecution history estoppel under *Festo Corp. v. Shoketsu* — no equivalents possible. Replacement preserves Bottomline distinction without foreclosing doctrine of equivalents. |
| B | Claims 2 and 3 | New trigger-distinction element (i-a) added to Claim 2; new preamble restriction and new first step (j-pre) added to Claim 3 | v4.0 trigger-distinction language applied only to Claim 1. Claims 2 and 3 were exposed to direct Bottomline §103 rejection without the restriction. Both independent claims now carry equivalent protection. |
| C | Claim 4, steps (o), (p), (q) | Steps replaced with portfolio-level gap distribution language: Claim 4 now computes a probability distribution over a portfolio of specific individually-identified anticipated payment events rather than a single aggregate cash flow forecast | v4.0 Claim 4 pre-emptive liquidity steps were structurally similar to Bottomline's forecasting trigger. Amended language creates a structural distinction: Bottomline processes anonymous aggregate historical patterns; amended Claim 4 processes a graph of specific identified future obligations with individual failure probabilities. |
| D | Dependent Claim D13 (new) | Five-step claim covering: camt.056 adversarial cancellation monitoring; security interest preservation workflow; ML classifier distinguishing error-correction from adversarial cancellations; pacs.004 interception protocol; adversarial event record generation | No prior art identified for ML classification of payment cancellation intent. Creates enforceable right against the primary attack vector on the auto-repayment collateral structure. Depends on Claim 5, inheriting priority date at filing. |
| E | Dependent Claim D9 | 'Sub-100ms' qualified as 'median (p50) sub-100ms'; p99 ceiling of 200ms added | Unqualified 'sub-100ms' claim is falsifiable if any single prediction exceeds 100ms. Median qualification is technically accurate and defensible. |
| F (v5.1) | Section 4.1 | Added *Recentive Analytics v. Fox* citation and technical infrastructure anchoring. **[REVERSED in v5.2 — see Amendment G.]** | Intended to address Federal Circuit's 2025 guidance. Drafting error — see Amendment G. |
| **G (v5.2)** | **Section 4.1** | ***Recentive Analytics v. Fox* citation removed in full. §101 analysis re-anchored exclusively on *Enfish v. Microsoft* and *McRO v. Bandai Namco*. Technical infrastructure improvement arguments (latency, interoperability, settlement visibility) preserved and strengthened under those anchors.** | ***Recentive* is adverse authority — the Federal Circuit held the claims ineligible in that case. Citing an adverse holding in support of eligibility creates an easily exploitable prosecution vulnerability. *Enfish* and *McRO* are affirmative precedents where claims were held eligible on grounds directly applicable here. The §101 position is stronger, cleaner, and examination-ready without *Recentive*.** |
| **H (v5.3)** | **Sections 0.4, 1.1, Claim 5, Sections 4.2-4.3, Section 6** | **Added US20250086644A1 distinction narrative; added natural-language monitoring written-description support; inserted explicit disbursement step into Claim 5; added claim-specific Alice analysis for Claims 3 and 4; aligned continuation and foreign filing strategy with the portfolio architecture.** | **Closes foreseeable §103, §112, and strategy-consistency objections before prosecution begins.** |

---

## 2. Independent Claims — v5.3 Final

> **ATTORNEY INSTRUCTION:** Claims 1 through 5 represent the complete independent claim set. Claims 1 and 5 carry the strongest novelty. Claim 1 is the primary method claim; Claim 5 is the repayment-loop independent claim that survives as a fallback even if Claims 1–4 are successfully challenged. Every prosecution decision on narrowing amendments to Claims 1–4 must be evaluated for its effect on continuation claim scope, since elements narrowed here cannot be recaptured in continuations. v5.3 changes are targeted to claim support and self-containment, not to the core novelty theory.

### Independent Claim 1 — Core Method Claim

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

### Independent Claim 2 — System Claim

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

### Independent Claim 3 — Instrument-Agnostic Liquidity Method

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

### Independent Claim 4 — Pre-Emptive Liquidity

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

### Independent Claim 5 — Settlement-Confirmation Auto-Repayment Loop

> **STRATEGIC NOTE — CLAIM 5:** Claim 5 is the net at the bottom of every possible design-around attempt. Any competitor building an automated payment bridging product must collect repayment somehow. If they use payment network confirmation data to do so automatically, they infringe Claim 5 regardless of how they have engineered around Claims 1–4. This claim has the cleanest novelty in the portfolio: no prior art automates repayment collection using cross-border payment network settlement confirmation data. It also anchors Dependent Claim D13's adversarial cancellation protection.

**A computer-implemented method for automated repayment collection on a short-duration liquidity advance secured against a cross-border payment receivable, the method comprising:**

> **(t0)** disbursing a short-duration liquidity advance to a party experiencing a cash flow deficit caused by a failure, delay, or rejection affecting an identified cross-border payment transaction, and programmatically recording the advance identifier, the disbursement amount, and the payment transaction identifier as linked records in a loan ledger;
>
> **(t)** establishing a programmatic monitoring relationship between the disbursed liquidity advance of step (t0) and a specific cross-border payment transaction identified by a unique transaction reference assigned by the originating payment network, wherein said unique transaction reference is the individual UETR or equivalent network-assigned identifier that uniquely identifies the specific in-flight payment across all processing nodes;
>
> **(u)** continuously monitoring the settlement status of the identified payment transaction using any real-time or near-real-time data feed, API, or message-based interface provided by a payment network, payment messaging infrastructure, or financial institution through which the original payment is being processed, including but not limited to SWIFT gpi tracker data, ISO 20022 payment status notification messages, Open Banking payment status APIs, and FedNow or equivalent instant payment network settlement confirmation events;
>
> **(v)** upon detection of a settlement confirmation event indicating that the original payment transaction has been credited to the intended beneficiary or is imminently to be credited, automatically initiating a repayment collection workflow that recovers the advance principal and accrued risk-adjusted cost from the advance recipient, the settlement proceeds, or any collateral or security interest established at the time of advance disbursement, without requiring any manual instruction from an operator;
>
> **(w)** in the event that the original payment transaction fails permanently rather than settling, automatically activating a recovery workflow against the collateral or security interest assigned at disbursement, including but not limited to enforcing an assignment of the payment receivable against the original payment sender, drawing on any guarantee or insurance instrument established at disbursement, or initiating a collections process against the advance recipient; and
>
> **(x)** generating a settlement and repayment confirmation record that documents the original payment identifier, the individual UETR or equivalent unique transaction reference, the advance disbursement details, the settlement confirmation event, the repayment amount, and the net realised return on the advance, for regulatory reporting, audit trail, and portfolio performance monitoring purposes.

> **CLAIM 5 NOTE — v5.3:** Step (t0) has been added so Claim 5 expressly claims disbursement rather than presupposing it, and steps (t) and (x) continue to include "individual UETR" explicitly by name, consistent with claim language standards established across the LIP patent family.

---

## 3. Dependent Claims — v5.3 Final

The dependent claim set is unchanged from v5.1 except that D3 and D8 are updated to include "individual UETR" language explicitly, consistent with the family-wide UETR verbatim requirement.

| **Dep.** | **Depends On** | **Specific Embodiment Covered** | **Strategic Purpose** |
|----------|----------------|--------------------------------|----------------------|
| D1 | Claim 1 | Parsing specifically ISO 20022 pacs.002 XML status reason codes as the payment failure signal | Core product embodiment — largest near-term market |
| D2 | Claim 1 | Failure probability derived from gradient-boosted tree ensemble (XGBoost, LightGBM, CatBoost) | Dominant real-world ML architecture |
| D3 | Claim 1 | Real-time monitoring via SWIFT gpi Tracker API with individual UETR-keyed transaction status tracking per identified in-flight payment | Largest payment network integration; individual UETR explicit |
| D4 | Claim 1 | Cost threshold calibrated specifically to maximise F2 score (recall-weighted) | Operationally optimal classification metric |
| D5 | Claim 1 | Tiered PD framework: structural model for listed companies, sector-proxy for private companies, ratio scoring for limited-data counterparties | Extension beyond JPMorgan; addresses 80%+ of mid-market counterparties |
| D6 | Claim 1 | Risk-adjusted cost computed as: PD × LGD × (advance duration / 365) × advance amount | Explicit pricing formula |
| D7 | Claim 1 | Liquidity offer transmitted to payment beneficiary within 5 seconds of failure detection | Competitive response latency SLA |
| D8 | Claim 1 | Repayment collected automatically via ISO 20022 pacs.008 debit instruction upon pacs.002 settlement confirmation for the individual UETR of the original in-flight payment | Full ISO 20022 closed-loop; individual UETR explicit |
| D9 | Claim 1 or 2 | **Median end-to-end prediction latency under 100 milliseconds (p50 < 100ms), with p99 latency under 200 milliseconds** | Technical performance differentiator; median-qualified v5.0 |
| D10 | Claim 2 | System deployed as a multi-tenant SaaS platform serving multiple financial institutions with isolated data pipelines | Cloud-native B2B licensing model |
| D11 | Claim 4 | Pre-emptive facility pricing includes time-decay adjustment reducing cost as settlement date approaches | Refinement of pre-emptive liquidity economics |
| D12 | Claim 5 | Settlement monitoring component configured to handle multiple concurrent payment identifiers per advance in partial-settlement scenarios | Handles split payments and partial credits |
| D13 | Claim 5 | Adversarial payment cancellation detection: monitoring ISO 20022 camt.056 cancellation requests for the individual UETR under monitoring; ML classifier distinguishing operational error-correction from adversarial sender-initiated cancellations; security interest preservation workflow; pacs.004 interception protocol; adversarial event audit trail | Protects auto-repayment collateral structure against primary known attack vector; individual UETR explicit |

### Dependent Claim D13 — Adversarial Cancellation Detection

**A computer-implemented method according to Claim 5, further comprising:**

> **(u)** wherein the monitoring of step (u) further comprises detecting ISO 20022 camt.056 payment cancellation request messages transmitted by the original payment sender during the settlement monitoring period, and wherein receipt of a camt.056 cancellation request for a payment against which a liquidity advance has been disbursed triggers an immediate security interest enforcement workflow on the assigned receivable collateral, preventing the cancellation from extinguishing the lender's claim on the settlement proceeds.

---

## 4. Alice Compliance Analysis — 35 U.S.C. § 101 Patent Eligibility

### 4.1 Alice Step Two: Inventive Concept Analysis

Under the two-step framework established in *Alice Corp. v. CLS Bank Int'l*, 573 U.S. 208 (2014), claims directed to abstract ideas may nonetheless be patent-eligible if they contain an "inventive concept" — elements or combinations of elements that transform the abstract idea into a patent-eligible application. The inventive concept inquiry under Alice Step Two asks whether the claims recite significantly more than the abstract idea itself.

The governing affirmative precedents are *Enfish, LLC v. Microsoft Corp.*, 822 F.3d 1327 (Fed. Cir. 2016) and *McRO, Inc. v. Bandai Namco Games Am. Inc.*, 837 F.3d 1299 (Fed. Cir. 2016). Under *Enfish*, claims satisfy Alice Step Two when they improve the functioning of the computer or network infrastructure itself, as opposed to merely using computers as tools to perform abstract business methods. The Federal Circuit in *Enfish* found that a self-referential database structure that improved computer memory usage and processing speed was patent-eligible precisely because the improvement targeted the technical operation of the system — not merely the result the system produced. Under *McRO*, claims that impose specific, meaningful technological rules and constraints on how a result is achieved — rather than simply claiming the result in functional terms — satisfy Alice Step Two. The Federal Circuit in *McRO* held that specific rules-based methods with defined technical steps are patent-eligible even when the end result could be characterised as an abstract output.

The claims here satisfy both *Enfish* and *McRO* for three independent reasons, each grounded in improvements to the technical operation of payment network infrastructure — not in the abstract financial decision the system enables.

**First — Latency improvement to payment network processing infrastructure (*Enfish* analogy):** The claims impose specific, measurable technical constraints on payment network message processing speed. Dependent Claim D9 requires median end-to-end prediction latency under 100 milliseconds (p50 < 100ms) with p99 under 200 milliseconds. This is not a characterisation of the business result (a loan offer is made quickly); it is a technical performance specification for the real-time payment network monitoring and machine learning inference pipeline. Achieving this latency requires specific distributed stream processing architectures — Apache Flink-class stream processors, in-memory feature caching, hardware-accelerated inference — that are distinguishable from generic computer implementations. The claims improve the speed at which actionable failure signals are extracted from live payment network telemetry, directly improving the technical operation of the monitoring pipeline, in the same manner that the self-referential table in *Enfish* improved the technical operation of database memory management.

**Second — Interoperability improvement across heterogeneous payment network protocols (*Enfish* + *McRO* combined):** The claims solve a specific technical problem in payment network infrastructure: extracting machine-readable failure signals from heterogeneous message formats across multiple incompatible networks simultaneously. Claim 1(b) requires extracting a unified feature representation from payment data in structured XML (ISO 20022), structured JSON (Open Banking), semi-structured proprietary formats (SWIFT MT), and unstructured natural language — normalising these into a common inference-ready representation in real time. This protocol translation and normalisation function is an improvement to the technical interoperability of payment network monitoring infrastructure, directly comparable to the database interoperability improvement in *Enfish*. It is not a generic use of machine learning on financial data; it is a specific technical method for reconciling incompatible network protocol outputs into a unified real-time signal.

**Third — Settlement visibility improvement via UETR-keyed correlation (*McRO* analogy):** The claims impose a specific technological rule for correlating liquidity advance lifecycles with asynchronous cross-border payment confirmation events: the individual UETR — the unique transaction reference assigned by the originating payment network to a specific identified in-flight payment — serves as the persistent key that links the real-time failure signal in Claim 1(a), the ML inference in Claim 1(c), the offer generation in Claim 1(f), and the automated repayment collection in Claims 5(t) and 5(x) across all processing stages. This UETR-keyed correlation is not an abstract result ("repayment happens automatically"); it is a specific technical mechanism that solves the settlement visibility problem — the inability of existing systems to programmatically correlate asynchronous settlement events on cross-border payment networks with previously disbursed liquidity positions. Under *McRO*, this specific rules-based technical approach is precisely what distinguishes patent-eligible claims from abstract functional claims.

The specification describes the hardware and software components required to achieve these technical improvements: distributed stream processing pipelines for real-time ISO 20022 message ingestion, low-latency machine learning inference engines with specific model architectures operating on UETR-keyed feature vectors, and individual UETR-based API integration layers for SWIFT gpi, FedNow, and Open Banking settlement confirmation events. These are not generic computer implementations of an abstract financial idea. They are specific technological solutions to specific technical problems in payment network infrastructure operation.

For these reasons, the claims recite significantly more than the abstract idea of "providing credit when a payment fails." The claims recite specific technological implementations that improve payment network infrastructure operation — processing latency, protocol interoperability, and settlement event correlation — and impose meaningful, measurable technical constraints on system architecture and performance. The claims are patent-eligible under 35 U.S.C. § 101 under the standards established in *Enfish* and *McRO*.

> **PROSECUTION INSTRUCTION — §101:** If the examiner raises an Alice § 101 rejection, respond by leading with *Enfish* (infrastructure improvement) and *McRO* (specific rules, not abstract result). Develop each of the three infrastructure improvement arguments above in detail. Do not cite *Recentive Analytics, LLC v. Fox Corp.* — that case resulted in a finding of ineligibility and constitutes adverse authority. Do not distinguish from *Recentive*; doing so draws the examiner's attention to a case the examiner may not have identified and invites a rejection grounded in it.

### 4.2 Claim-Specific Eligibility Support for Claim 3

Claim 3 should not be characterised at a high level as merely "offering financing against a receivable." Read as drafted, Claim 3 is directed to a specific technical workflow in which an instrument-agnostic liquidity action is triggered by a real-time failure prediction signal arising from a specific in-flight payment, priced using computationally derived risk measures, and executed together with programmatic establishment of a security interest in the delayed payment proceeds. The inventive concept is not the abstract economic idea of financing; it is the technical integration of machine-generated payment-failure detection, instrument selection, and automated collateral linkage within a real-time payment-network response pipeline.

Under *McRO*, this claim imposes a defined sequence of constrained computational steps rather than claiming the desired business outcome at a high level of abstraction. Under *Enfish*, the claim improves the operation of the payment-processing infrastructure by enabling system-level conversion of heterogeneous payment-failure telemetry into an executable, secured liquidity instrument without manual intervention.

### 4.3 Claim-Specific Eligibility Support for Claim 4

Claim 4 should not be characterised as a generic forecast of future cash position. The claim is directed to a specific computational method that identifies specific anticipated payment events, assigns each such event an individual failure probability, aggregates those event-level probabilities into a portfolio-level gap distribution, and then calibrates a standing facility to a quantile of that distribution. This is a constrained computational architecture operating on identified payment events and their dynamically updated probability structure, not a generic financial planning abstraction.

The inventive concept lies in the graph-based and event-specific computational framework by which future liquidity risk is represented and acted upon. In *McRO* terms, the claim recites a defined rules-based method for converting a portfolio of anticipated payment events into a quantified liquidity-control action. In *Enfish* terms, the claim improves the technical operation of liquidity-monitoring infrastructure by replacing static aggregate cash forecasting with a machine-processable portfolio model tied to specific anticipated transactions and updated through ongoing payment-network observations.

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

### 6.1 Non-Provisional Utility Application (P2)

The utility application claiming priority to this provisional should preserve all five independent claims and all thirteen dependent claims as filed. Any examiner-requested narrowing amendments during prosecution should be carefully evaluated for their impact on continuation claim scope, since claim elements narrowed in the parent cannot be recaptured in continuations without losing the priority date.

### 6.2 Continuation Applications (P3–P15)

The Patent Family Architecture document (separate confidential filing) describes a 15-patent portfolio strategy covering:

- P3: Multi-party distributed architecture and adversarial cancellation detection
- P4: Pre-emptive liquidity portfolio management
- P5: Supply chain cascade detection and pre-emptive cascade prevention
- P6: CBDC settlement integration
- P7: Tokenised receivables as programmable collateral
- P8: Autonomous treasury management
- P9–P15: interoperability, regulatory reporting, embedded distribution, continuous learning, sustainability, AI-native infrastructure, and quantum-resistant monitoring extensions as described in the portfolio architecture document

All continuation applications must be filed within the statutory periods allowed under 35 U.S.C. § 120 to maintain the priority date established by this provisional application. Counsel should nonetheless evaluate each later extension separately to determine whether the parent disclosure is sufficient for pure continuation treatment or whether a continuation-in-part is required for any genuinely new matter.

### 6.3 PCT and Foreign Filing Strategy

Given the global nature of cross-border payments, international patent protection is commercially essential. The Patent Cooperation Treaty (PCT) application should be filed within 12 months of this provisional's filing date, designating major jurisdictions including the European Patent Office (EPO), Canadian Intellectual Property Office (CIPO), Japan Patent Office (JPO), and key Asian markets such as Singapore and South Korea. Hong Kong should be included in the foreign filing plan through the appropriate local registration or re-registration path tied to a recognised base patent.

---

**END OF PROVISIONAL SPECIFICATION v5.3**

**Supersedes:** v5.2 (§101 re-anchor)
**Key changes:** US20250086644A1 distinction added; natural-language written-description support added; Claim 5 disbursement step added; claim-specific §101 support added for Claims 3 and 4; foreign filing and continuation planning aligned with the portfolio strategy.
**Claims:** Narrowly updated from v5.2 for self-containment and support; no change to core novelty theory.
**Next step:** Engage patent attorney; review v5.3 with attorney; file provisional; commence P2 utility drafting.
*Internal use only. Stealth mode active. March 4, 2026.*
*Lead: LEX | Review: All agents*
