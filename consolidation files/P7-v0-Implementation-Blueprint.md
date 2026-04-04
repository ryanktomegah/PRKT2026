# Bridgepoint Intelligence — P7 v0 Implementation Blueprint
## Tokenised Receivable Liquidity Pool Architecture
## Luxembourg SV Structure, ERC-3643 Token Design, Cash Waterfall & Capital Markets Integration
Version 2.0 | Confidential | March 2026

---

## Table of Contents
1. Executive Summary
2. Part 1 — Why This Product Does Not Exist (And Why Tokenised Receivables Are Different)
3. Part 2 — Legal Entity & Jurisdiction Architecture
4. Part 3 — Token Architecture
5. Part 4 — Cash Waterfall
6. Part 5 — Revenue Architecture & Financial Projections
7. Part 6 — C-Component Engineering Map
8. Part 7 — Investor Acquisition Strategy & Secondary Market Design
9. Part 8 — Consolidated Engineering Timeline
10. Part 9 — What Stays in the Long-Horizon P7 Patent
11. Part 10 — Risk Register

---

## 1. Executive Summary

This document is the engineering, legal, and commercial blueprint for launching P7 v0 — the Tokenised Receivable Liquidity Pool — a product that packages Bridgepoint's bridge loan receivables into a Luxembourg securitisation vehicle with compartmentalised risk tranches, issues ERC-3643 compliant tokenised notes to institutional investors, and uses BPI's existing UETR-driven settlement engine as a first-party oracle to trigger automated cash waterfall distributions upon payment settlement.

**Why this matters:** The global Real World Asset (RWA) tokenisation market reached $24 billion in mid-2025, growing 308% over three years (CoinDesk, June 2025). BCG and Ripple project this market to reach $18.9 trillion by 2033. BlackRock's BUIDL tokenised treasury fund alone holds $1.9 billion. Franklin Templeton's BENJI fund manages $742 million on-chain. Yet every one of these products tokenises the same thing: government bonds, money market instruments, or long-duration private credit. Not a single product in the $24 billion RWA market tokenises ultra-short-duration payment receivables with real-time settlement observability. P7 creates this asset class.

**Why nobody has built this:** Three prerequisites had to converge simultaneously, and until Bridgepoint, they never have:

1. **A portfolio of ultra-short-duration receivables with observable settlement** — BPI's bridge loans have 3-21 day duration and settle against SWIFT UETR-tracked payments. The settlement signal is cryptographically verifiable in real time. No other originator has receivables with this combination of short duration and observable settlement. Invoice factoring receivables (Centrifuge, Maple Finance) have 30-90 day duration and no real-time settlement signal. Treasury tokenisation (BlackRock BUIDL, Ondo Finance) holds government bonds with 10-30 year underlying duration. BPI's receivable pool is structurally unique.

2. **ML-driven credit assessment with real-time portfolio NAV** — BPI's C2 PD Pricing Engine computes probability of default, CVA, and LGD for every bridge loan in real time. The C3 Settlement Monitor provides continuous UETR status updates. Together, these components enable a Net Asset Value computation that updates every 60 minutes — not quarterly, not monthly, but hourly. No other tokenised fund has this capability because no other originator has ML-driven, payment-level credit intelligence.

3. **A first-party settlement oracle** — The critical innovation. When a SWIFT pacs.002 settlement confirmation arrives, BPI's C3 Settlement Monitor generates an ECDSA-signed attestation that is posted on-chain. This is not a third-party oracle (Chainlink, Pyth) reading a data feed — it is the settlement monitoring system itself attesting to settlement. The oracle IS the settlement engine. This eliminates the oracle trust gap that plagues every other tokenised receivable structure.

**Core thesis:** P7 v0 does not require a decentralised on-chain Dutch auction or CBDC rails. It requires a Luxembourg securitisation compartment, ERC-3643 compliant tokenised notes, and Bridgepoint's existing UETR-driven settlement engine acting as a first-party oracle. The total new engineering is 20-24 weeks of work for two senior engineers on top of the existing C1-C8 infrastructure.

**Engineering summary:**

| Component | P7 v0 Impact | Effort |
|-----------|-------------|--------|
| C1 — ML Failure Classifier | No change | 0 |
| C2 — PD Pricing Engine | No change | 0 |
| C3 — Settlement Monitor | Extend: Oracle Signing Service + NAV Feed + Dispute Alert | 5-7 weeks |
| C4 — Dispute Classifier | No change (minor output routing) | 1-2 days |
| C5 — ISO 20022 Processor | No change | 0 |
| C6 — AML / Security | Minor extend: circular exposure rule | 1 week |
| C7 — Bank Integration Layer | Extend: Sub-participation API + Repayment Confirm | 8-10 weeks |
| C8 — Licensing & Metering | Extend: SV fee accrual + performance fee + intra-group licensing | 3-4 weeks |

**Total: ~20-24 engineer-weeks, 2 senior engineers. Target: Live external investor pilot Q4 2026.**

---

## 2. Part 1 — Why This Product Does Not Exist (And Why Tokenised Receivables Are Different)

### 1.1 The RWA Tokenisation Market — $24 Billion of the Wrong Asset Classes

The RWA tokenisation market is large, growing, and structurally homogeneous. Nearly every tokenised asset falls into one of four categories, none of which captures the asset class P7 creates.

**Category 1: Government Bonds & Money Market Instruments**

| Product | AUM | Asset | Duration | Yield Source | Settlement Signal |
|---------|-----|-------|----------|-------------|-------------------|
| BlackRock BUIDL | $1.9B | US Treasuries, repo | 10-30yr underlying; overnight repo | Risk-free rate (SOFR) | None — sovereign bonds have no "settlement event" |
| Franklin Templeton BENJI (FOBXX) | $742M | US Government money market | Overnight to 13 weeks | T-bill yield | None |
| Ondo Finance USDY | $600M+ | US Treasuries | Short-term | ~4.8% | None |
| Ondo Finance OUSG | $200M+ | Short-term government bonds | 3-12 months | Government bond yield | None |

These products are essentially wrapper tokens around government bonds. They provide on-chain access to risk-free rate. They are valuable — BlackRock's $1.9B BUIDL proves the demand. But they are commoditised: once you have the regulatory licence and the fund structure, the underlying asset (US Treasuries) is identical across all providers. There is no information advantage, no ML pricing, no settlement intelligence. The tokens represent a claim on an asset that never fails, never defaults, and never needs to be monitored.

**Category 2: Private Credit & Structured Lending**

| Platform | TVL/AUM | Asset | Duration | Credit Assessment | Settlement Signal |
|----------|---------|-------|----------|-------------------|-------------------|
| Centrifuge | $1.1B active loans | Invoices, trade finance, SME loans | 30-180 days | Manual underwriting + off-chain credit memos | None — no UETR, no real-time tracking |
| Maple Finance | $800M+ originated | Institutional lending | 30-90 days | Manual credit committee | None — borrower self-reports repayment |
| Goldfinch | $200M+ | Emerging market lending | 12-36 months | Off-chain "trust through consensus" | None — manual collection agents |
| Figure Technologies | $21B originated (home equity) | HELOCs, mortgages | 5-30 years | Traditional credit scoring (FICO) | Monthly self-reporting |

These platforms tokenise real credit risk, but they share three structural limitations:

1. **No real-time settlement observability.** When a Centrifuge borrower repays, the system learns about it when the borrower (or a service provider) reports the repayment. There is no cryptographic proof that settlement occurred. The NAV update depends on trust in the reporting party.

2. **No ML-driven credit assessment.** Credit decisions are made by humans reading credit memos or by simple rule-based models. None of these platforms has a production ML model that prices individual receivable risk in real time. Centrifuge's "risk groups" are manually assigned categories, not ML predictions.

3. **Long duration creates illiquidity.** A 90-day invoice or a 5-year HELOC cannot offer daily liquidity without maturity transformation risk. These platforms either lock investors in for the duration or require a deep secondary market (which does not yet exist for most tokenised credit).

**Category 3: Real Estate Tokenisation**

Real estate tokenisation (RealT, Lofty, Republic) converts property ownership into tokens. Duration is measured in years to decades. Liquidity is minimal. Valuation is subjective (appraisals, not market prices). There is no settlement signal — rental income accrues monthly, property values change quarterly (if at all). This category is structurally incompatible with the ultra-short-duration, observable-settlement profile of BPI's receivables.

**Category 4: Commodity & Fund Tokenisation**

PAXG (gold-backed tokens), Swarm Markets (equities on-chain), Backed Finance (tokenised ETFs). These are asset wrappers that provide blockchain access to traditional instruments. The underlying asset determines all characteristics; the token adds portability but no intelligence.

### 1.2 Why Payment Receivables Are a Structurally Different Asset Class

BPI's bridge loan receivables have five characteristics that, in combination, do not exist in any other tokenised asset:

| Characteristic | BPI Receivables | Government Bonds (BUIDL) | Private Credit (Centrifuge) | Real Estate |
|----------------|----------------|--------------------------|----------------------------|-------------|
| **Duration** | 3-21 days | 10-30 years | 30-180 days | 5-30 years |
| **Settlement observability** | Real-time UETR tracking via C3 `SettlementMonitor` | None (sovereign risk-free) | None (manual reporting) | None (monthly accrual) |
| **Credit assessment** | ML-driven (C1 + C2: failure probability, PD, CVA, LGD) | N/A (risk-free) | Manual credit committee | Appraisal-based |
| **NAV update frequency** | Hourly (C3 NAV Event Feed) | Daily (bond pricing) | Weekly to monthly | Quarterly to annually |
| **Oracle type** | First-party (C3 IS the settlement monitor) | Not needed | Third-party or self-reported | Not applicable |

The combination of ultra-short duration + real-time settlement observability + ML credit pricing creates something that has no precedent in either traditional securitisation or tokenised finance: **a debt instrument that resolves to cash in days, with cryptographic proof of resolution, priced by a production ML model.**

This is not merely a "tokenised receivable" — that already exists (Centrifuge does it). This is a **settlement-observable, ML-priced, oracle-attested token** — a new primitive in the capital markets taxonomy.

### 1.3 The Three Innovations That Make P7 Novel

**Innovation 1: UETR-Bound Token**

Every token in the P7 pool is backed by a bridge loan whose underlying payment is tracked by a SWIFT Unique End-to-end Transaction Reference (UETR). The `ActiveLoan` dataclass in `lip/c3_repayment_engine/repayment_loop.py` contains the UETR, and the `SettlementMonitor.process_signal()` method matches incoming settlement signals (from any of 5 supported rails: SWIFT, FedNow, RTP, SEPA, BACS) to the active loan via UETR lookup.

No other tokenised receivable has this. Centrifuge tokens are backed by invoices — PDFs. Maple tokens are backed by loan agreements — legal documents. BPI tokens are backed by receivables whose settlement is observable in real time on the payment network. The token's lifecycle is cryptographically bound to the payment's lifecycle.

**Innovation 2: ML-Priced Tranching**

The C2 PD Pricing Engine determines the risk bucket of every bridge loan. `compute_loan_fee()` in `lip/c2_pd_model/fee.py` prices each loan based on ML-derived failure probability, corridor risk, and counterparty characteristics. This pricing feeds directly into the tranche allocation engine:

- Loans with PD < 0.05 and CLASS_A rejection (routing errors, 3-day maturity) → eligible for Class A Senior Notes
- Loans with 0.05 < PD < 0.15 and CLASS_B rejection (systemic delays, 7-day maturity) → Class B Mezzanine Notes
- All loans contribute to the aggregate pool; the tranche structure determines the loss absorption waterfall

No other token platform uses a production ML model for real-time credit risk assessment of individual pool assets. Centrifuge's risk groups are manually assigned. Maple's credit decisions are committee-based. Ondo's assets are risk-free government bonds that require no credit assessment at all.

**Innovation 3: Oracle-Triggered Automated Waterfall**

When C3 detects a pacs.002 settlement confirmation for a bridge loan, the Oracle Signing Service generates an ECDSA attestation and calls `confirmSettlement(uetr, amount, signature)` on the smart contract. This triggers the automated cash waterfall — distributions flow to Class A, then Class B, then Class E holders, without manual intervention.

The waterfall executes in seconds, not quarters. Traditional securitisation vehicles distribute cash flows monthly or quarterly, after a servicer manually reconciles payments and an administrator manually calculates NAV. BPI's waterfall is automated at the protocol level: settlement confirmation → on-chain attestation → smart contract execution → token holder distribution.

### 1.4 Academic Validation

The structural innovations in P7 are supported by a growing body of academic and institutional research:

**BIS Innovation Hub — Project Agora (2024-2026)**

The Bank for International Settlements' Project Agora, launched April 2024 with expected results in H1 2026, explores how tokenisation can improve cross-border payments. The project validates the core thesis that integrating messaging, reconciliation, and settlement into a single programmable platform creates efficiency gains that are not achievable with traditional infrastructure. P7's oracle-triggered waterfall is a concrete implementation of this thesis applied to securitisation.

**BIS Annual Economic Report (2025) — Unified Ledger**

The BIS 2025 Annual Economic Report proposes a "tokenised unified ledger" where central bank money, commercial bank deposits, and government bonds share a single programmable platform. The report establishes that tokenisation "integrates messaging, reconciliation and settlement into a single operation." P7's architecture — where the settlement signal triggers distribution without intermediate reconciliation — is an institutional implementation of this principle.

**ECB Exploratory Work on Tokenised Settlement (2024)**

The ECB's 2024 exploratory programme, the most comprehensive of its kind globally with 50 trials and experiments across nine EU jurisdictions, demonstrated clear market demand for DLT-based settlement in central bank money. European issuers have placed close to EUR 4 billion in DLT-based fixed-income instruments since 2021. P7's ERC-3643 notes sit within this established European institutional framework.

**Basel Committee Cryptoasset Standards (July 2024, implementation January 2026)**

The Basel Committee finalised its prudential framework for banks' cryptoasset exposures. Group 1a (tokenised traditional financial instruments) receive the same capital treatment as their non-tokenised equivalents. This means P7's tokenised notes, as debt securities backed by receivables, qualify for standard Basel risk-weight treatment — not the punitive Group 2 treatment applied to unbacked crypto assets. The capital memo referenced in Section 2.3 of this document will demonstrate Group 1a qualification.

**Federal Reserve Bank of New York — Project Pine (2025)**

The NY Fed and BIS Innovation Hub's Project Pine found that central banks could deploy smart-contract-based policy tools in a tokenised financial system. While P7 does not require CBDC integration (v0 operates with fiat settlement), Project Pine validates the programmable waterfall architecture as compatible with future central bank infrastructure.

### 1.5 Why Existing Platforms Cannot Build P7

| Platform | Why They Cannot Replicate P7 |
|----------|------------------------------|
| **Centrifuge** | No payment network integration. No UETR tracking. No ML credit model. Their oracle is a "pool operator" who manually reports repayments. Building a first-party settlement oracle would require becoming a payment infrastructure provider — a fundamentally different business. |
| **Maple Finance** | Institutional lending with manual credit assessment. No per-loan real-time monitoring. Their competitive advantage is borrower relationships, not technology. Replicating C1-C3 is a multi-year engineering programme. |
| **Goldfinch** | Emerging market focus with off-chain underwriting. "Trust through consensus" model is philosophically incompatible with ML-driven credit assessment. No payment infrastructure integration. |
| **Ondo Finance** | Government bond wrapper. Their entire infrastructure is built around custody of traditional financial instruments, not origination of receivables. They have no lending infrastructure, no ML models, no settlement monitoring. |
| **Figure Technologies** | Closest structural analogue — they tokenise home equity loans on Provenance blockchain ($21B originated, AAA-rated securitisation from S&P/Moody's). But HELOCs are 5-30 year duration with monthly self-reporting. No real-time settlement observability. No ML pricing engine. Figure would need to enter an entirely different market (payment receivables) to compete with P7. |
| **BlackRock / Franklin Templeton** | The asset management giants have the distribution and the regulatory relationships, but their tokenised products are fund wrappers around government bonds. Building P7 would require: (a) a bridge lending infrastructure, (b) an ML credit engine, (c) a settlement monitoring system, (d) bank partnerships for origination. This is a 3-5 year build from scratch. |

### 1.6 The Market Opportunity

The addressable market for P7 is defined by two dimensions:

**Dimension 1: BPI bridge loan origination volume**

P7's pool is sourced from BPI's own bridge lending activity (P2/P3). As BPI scales across bank partners and corridors, the pool of tokenisable receivables grows proportionally.

| Year | Projected Bridge Loan Volume (Annual) | Average Outstanding Pool (AUM) | Source |
|------|--------------------------------------|-------------------------------|--------|
| Year 1 (2027) | EUR 500M - 1B | EUR 25-100M | 1-3 bank partners, 2-4 corridors |
| Year 2 (2028) | EUR 2-5B | EUR 100-500M | 5-10 bank partners, 6-10 corridors |
| Year 3 (2029) | EUR 5-15B | EUR 250M - 1B | 10-20 bank partners, global corridors |
| Year 5 (2031) | EUR 20-50B | EUR 1-5B | Full network scale |

**Dimension 2: Institutional demand for ultra-short-duration yield**

The addressable investor pool includes every institutional investor that currently allocates to money market funds, commercial paper, or ultra-short-duration fixed income. This is a multi-trillion dollar allocation category. P7 offers:

- Higher yield than government money market (SOFR + 150-600 bps vs. SOFR flat)
- Shorter effective duration than most commercial paper (3-21 days vs. 30-270 days)
- Real-time NAV transparency (hourly updates, not daily)
- ML-driven credit assessment (not agency ratings that lag by months)
- Programmable liquidity (smart contract-enforced redemption, not T+2 wire transfer)

The market for tokenised private credit already reached $3.2 billion by March 2026, up 180% from $1.14 billion at the start of 2025. P7 targets the intersection of this growing market with the ultra-short-duration money market allocation — a segment that currently has zero tokenised products.

---

## 3. Part 2 — Legal Entity & Jurisdiction Architecture

### 2.1 Why Luxembourg

Five mutually reinforcing reasons place Luxembourg as the only credible jurisdiction for P7 v0:

**1. Luxembourg Securitisation Law (as amended 9 February 2022)**

The 2022 amendments to the Law of 22 March 2004 transformed Luxembourg securitisation into the most flexible regime in the EU. SVs can originate and purchase loans without a banking licence. Active portfolio management is permitted (critical — BPI's ML-driven pool composition requires active management). The law broadened the definition of "securities" to "financial instruments," explicitly accommodating DLT-native issuance. SVs may now be fully or partially financed by borrowings, and can be structured as any corporate form (SA, SCA, SARL, SCS, SCSp). Luxembourg's Law of 22 January 2021 (Blockchain Law II) explicitly allows dematerialised securities to be recorded on a DLT — meaning ERC-3643 tokens issued by the SV are legally recognised securities under Luxembourg law.

**2. Statutory compartment ring-fencing**

Multiple legally segregated compartments per SV. Investors in Compartment A (EU-APAC corridor) have zero legal recourse to Compartment B (EU-North America corridor) assets. This is not contractual segregation (which can be challenged in insolvency) — it is statutory ring-fencing under the Securitisation Law. Each compartment operates as an economically independent vehicle while sharing a single legal entity, administrator, and auditor. This reduces fixed costs by 60-70% compared to incorporating separate SPVs per corridor.

**3. MiCA + EU Prospectus Regulation alignment**

MiCA (Markets in Crypto-Assets Regulation, fully applicable 30 December 2024, transitional provisions until 1 July 2026) explicitly excludes tokenised securities that fall under existing financial regulation (MiFID II, Prospectus Regulation). P7's notes are debt securities — they are regulated under the Prospectus Regulation, not MiCA. This is a feature, not a bug: it means P7 tokens inherit the established regulatory framework for debt securities while benefiting from DLT transferability.

Private placement exemption under the EU Prospectus Regulation: offerings to fewer than 150 non-qualified investors per EU member state, or with a minimum denomination of EUR 100,000, are exempt from the full prospectus requirement. P7 v0 uses both exemptions — Class A minimum denomination is EUR 500,000, and initial distribution targets fewer than 50 qualified investors.

ESMA's October 2025 guidelines further clarify DLT integrations, permitting hybrid models where tokenised bonds comply simultaneously with MiFID II and DLT-specific requirements.

**4. Tax efficiency**

SVs benefit from Luxembourg's participation exemption regime. Income derived from the securitisation activity (interest spread, servicing fees) is subject to corporate tax only on the SV's net margin after paying investors. Advance Tax Rulings (ATRs) provide certainty on tax treatment before launch. The Canada-Luxembourg tax treaty (in force since 2000, amended by the 2012 MLI) protects BPI's technology licensing fees and management fees from double taxation — a material advantage for BPI Inc.'s Canadian domicile.

**5. Operational ecosystem**

Luxembourg has the deepest bench of securitisation service providers in Europe:

- **Administrators:** CACEIS, SocGen Securities Services, Alter Domus, Apex Group, TMF Group
- **Legal:** Loyens & Loeff, DLA Piper, Linklaters, Allen & Overy, CMS — all with dedicated securitisation + DLT practices
- **ERC-3643 platform providers:** Tokeny (Luxembourg-headquartered, creator of the T-REX protocol), Fireblocks, InvestaX
- **Auditors:** All Big-4 have Luxembourg securitisation practices (PwC, Deloitte, EY, KPMG)
- **Custodians:** State Street, BNP Paribas Securities Services, Northern Trust

The DTCC joined the ERC-3643 Association in 2025, signalling mainstream institutional adoption of the standard P7 uses.

### 2.2 Entity Stack

```
BRIDGEPOINT INTELLIGENCE INC. (Canada — BC ULC)
Role:    Portfolio Manager, Data/Oracle Provider, IP Licensor
Revenue: Management fee (1.5-2.0% AUM) + performance fee (15-20% above hurdle)
         + technology licensing fee (bps on monitored volume)
         |
         | Portfolio Management Agreement
         | Oracle Services Agreement
         | IP Licensing Agreement
         v
BPI RECEIVABLES S.A. (Luxembourg — Securitisation Vehicle)
Governed by:   Luxembourg Securitisation Law (as amended 2022)
Structure:     Umbrella SV with statutory compartments
Board:         2 Luxembourg-resident directors + 1 BPI nominee
Administrator: Third-party Luxembourg fund administrator
                (CACEIS, Alter Domus, or Apex Group — RFP at W2)
Auditor:       Big-4 Luxembourg office
Custodian:     Qualified custodian for fiat reserves + token custody
               (Fireblocks or Copper.co for digital asset custody)
         |
         |-- COMPARTMENT A: EU <-> APAC corridor
         |       Senior Notes / Mezzanine Notes / Equity Reserve
         |       Segregated pool of bridge loan receivables
         |       Independent coverage tests, waterfall, NAV
         |
         |-- COMPARTMENT B: EU <-> North America corridor
         |       Senior Notes / Mezzanine Notes / Equity Reserve
         |       Segregated pool of bridge loan receivables
         |       Independent coverage tests, waterfall, NAV
         |
         | Receivable Purchase Agreement (true sale) OR
         | Sub-participation Agreement (Phase 1)
         v
BANK / ELO PARTNER
Role:      Lender of record, originator of bridge loans
Mechanism: Sells sub-participation interests in bridge loans to SV
Retains:   Regulatory relationship, borrower KYC, AML
Revenue:   Origination fee + retained spread on sub-participation
```

### 2.3 True Sale vs Sub-Participation

The choice between true sale and sub-participation determines the legal insulation of the SV's assets from the originating bank's insolvency. P7 v0 launches with sub-participation and migrates to true sale in Phase 2.

**Phase 1: Sub-participation (launch)**

| Aspect | Sub-participation |
|--------|-------------------|
| Legal title | Bank retains legal title to loan |
| SV interest | Economic interest in cash flows |
| Borrower notification | Not required |
| Regulatory treatment | On-balance-sheet for bank (no SSFA benefit) |
| Insolvency remoteness | Moderate (SV has contractual claim, not proprietary right) |
| Setup time | 4-6 weeks (standard bilateral agreement) |
| Risk | Bank insolvency exposes SV to senior creditor claims |

**Phase 2: True sale (migration)**

| Aspect | True sale |
|--------|-----------|
| Legal title | Transferred to SV (or security trustee) |
| SV interest | Proprietary ownership |
| Borrower notification | Required (Luxembourg Civil Code Art. 1690) |
| Regulatory treatment | Off-balance-sheet for bank (Basel SSFA treatment available) |
| Insolvency remoteness | Strong (SV has proprietary right; assets not part of bank estate) |
| Setup time | 8-12 weeks (requires Basel capital treatment memo, legal opinions) |
| Risk | Recharacterisation risk (court treats as secured loan, not true sale) |

The Basel capital treatment memo (Phase 2) must demonstrate:

1. True sale achieves effective transfer of risk per CRR Article 244 (EU) / OSFI B-20 (Canada)
2. SV meets the "significant risk transfer" test
3. Bank retains no implicit support (clean break)
4. The securitisation positions qualify as Group 1a under the Basel cryptoasset framework (July 2024)

### 2.4 Transfer Pricing Architecture

Three intra-group flows require arm's-length pricing under OECD Transfer Pricing Guidelines (2022) and Luxembourg Circular 56/1:

| Flow | Direction | Pricing Basis | Benchmark |
|------|-----------|---------------|-----------|
| Management fee | SV → BPI Inc. | 1.5-2.0% AUM | CLO/CDO manager fees (market range: 1.0-2.5% AUM) |
| Performance fee | SV → BPI Inc. | 15-20% above 8% hurdle | Private credit fund performance fees (15-25% above 6-10% hurdle) |
| Technology licensing fee | SV → BPI Inc. | bps on monitored volume | Comparable software licensing (SaaS pricing benchmarks) |

Documentation required: contemporaneous transfer pricing study, BEPS Master File and Local File (Luxembourg CbCR), annual arm's-length benchmark refresh. Luxembourg tax authorities accept advance pricing agreements (APAs) for complex intra-group structures — BPI should file for a bilateral Canada-Luxembourg APA within 6 months of SV incorporation.

---

## 4. Part 3 — Token Architecture

### 3.1 ERC-3643 (T-REX Protocol) — Standard Selection Rationale

ERC-3643, originally created by Tokeny (Luxembourg-headquartered), is the de facto standard for institutional tokenised securities. The standard has been used to tokenise over $28 billion in assets across hundreds of projects. It was validated by the DTCC joining the ERC-3643 Association in 2025, and Nasdaq's SEC filing to tokenise listed stocks by 2026 references ERC-3643-compatible infrastructure.

**Why ERC-3643 and not alternatives:**

| Standard | Capabilities | Why Not P7 |
|----------|-------------|------------|
| ERC-20 (vanilla) | Transfer, approve, balance | No KYC/AML enforcement, no transfer restrictions, no forced transfer. Regulatory non-starter. |
| ERC-1400 (Polymath) | Partitioned balances, document management | Less institutional adoption. Polymath pivoted to private chain (Polymesh). No ONCHAINID integration. |
| ERC-3525 (Semi-Fungible) | Tranche-like value splits | Novel but unproven. No institutional track record. No compliance infrastructure. |
| ERC-3643 (T-REX) | On-chain KYC via ONCHAINID, transfer rules, identity registry, freeze/force transfer | $28B tokenised. SocGen, ABN AMRO, BNP Paribas deployed. DTCC member. Luxembourg-native. |

**ERC-3643 core capabilities leveraged by P7:**

1. **ONCHAINID credential verification** — Every investor must hold a verified ONCHAINID containing KYC/AML credentials issued by a licensed identity verifier. Transfer attempts from non-verified wallets are rejected at the smart contract level. This satisfies Luxembourg AML/CFT requirements without manual transfer agent intervention.

2. **Transfer rule engine** — Configurable rules enforced on-chain:
   - Jurisdiction whitelist (only wallets from approved jurisdictions)
   - Maximum holding limits per investor (concentration risk)
   - Lock-up periods (6-month soft lock for Class B)
   - Minimum denomination (EUR 500K for Class A, EUR 250K for Class B)
   - Maximum investor count (private placement: <150 per member state)

3. **Identity Registry** — Maintained by BPI Receivables S.A. (as issuer). Maps wallet addresses to ONCHAINID contracts. Only the issuer (or delegated compliance agent) can add/remove identities. Investor off-boarding triggers Identity Registry removal → all tokens from that address are frozen.

4. **Frozen / forced transfer** — Legal disputes, regulatory orders, or court injunctions require the ability to freeze tokens or force-transfer to a recovery address. ERC-3643 provides this natively. The SV administrator triggers freeze via the compliance agent role; forced transfer requires multi-sig from SV board + administrator.

### 3.2 Token Classes

```
CLASS A — SENIOR NOTES
├── NAV allocation: 80%
├── Coupon: SOFR/EURIBOR + 150-250 bps
├── Subordination: 20% (Class B + Class E absorb losses first)
├── Liquidity: T+2 daily (subject to coverage test)
├── Minimum denomination: EUR 500,000
├── Lock-up: None
├── Target investor: Money market funds, bank treasury desks
├── Risk weight (Basel): Standard securitisation treatment (Group 1a)
└── Transfer restrictions: Qualified investors only (MiFID II professional clients)

CLASS B — MEZZANINE NOTES
├── NAV allocation: 15%
├── Coupon: SOFR/EURIBOR + 400-600 bps
├── Subordination: 5% (Class E absorbs losses first)
├── Liquidity: T+5 weekly (subject to coverage test)
├── Minimum denomination: EUR 250,000
├── Lock-up: 6-month soft lock-up (early redemption at 2% penalty)
├── Target investor: Private credit funds, yield-seeking family offices
├── Risk weight (Basel): Higher risk weight per tranche seniority
└── Transfer restrictions: Qualified investors, max 50 holders

CLASS E — EQUITY / FIRST-LOSS
├── NAV allocation: 5%
├── Return: Residual cash flows after all senior/mezzanine obligations
├── Subordination: None — absorbs ALL losses first
├── Liquidity: None (Phase 1)
├── Holder: BPI Inc. (100% — skin in the game)
├── Transferability: Non-transferable (Phase 1)
├── Purpose: Alignment of interest + coverage test buffer
└── Accounting: BPI consolidates Class E at fair value through P&L
```

**Why BPI holds 100% of Class E:** This is not a regulatory requirement (EU Securitisation Regulation Article 6 requires 5% retention, which Class E satisfies). It is a commercial necessity. Institutional investors in Class A and B need to know that BPI — the entity controlling the ML models, the oracle, and the portfolio management — has material first-loss exposure. If the ML model mispredicts, if the oracle malfunctions, if the portfolio manager makes bad allocation decisions, BPI loses money first. This alignment of interest is the single most important investor due diligence point.

### 3.3 Token Lifecycle

The lifecycle of a P7 token from bridge loan origination to investor distribution demonstrates the integration of BPI's existing C-components with the new SV infrastructure:

```
T+0ms:  C1 detects payment failure → C2 prices bridge loan (PD, fee, maturity)
        → C7 ExecutionAgent routes disbursement decision

T+0:    ELO bank disburses bridge loan to receiving bank
        → C7 notifies SV (POST /sv/participation-notify)
        → SV administrator updates pool composition
        → NAV adjusted (new receivable added to pool)
        → If pool growth exceeds existing token supply:
            Smart contract mints additional tokens to investor wallets
            (pro-rata to existing allocations, or to new subscriptions in queue)

T+days: C3 SettlementMonitor tracks UETR via process_signal()
        C4 DisputeClassifier monitors camt.056 recall signals
        Hourly NAV Feed updates pool metrics:
        {
          "compartment": "A",
          "activeLoans": 47,
          "totalExposure": "23450000.00",
          "settledLast60min": 3,
          "settledAmountLast60min": "1875000.00",
          "defaultedLast60min": 0,
          "trailingLossRate30d": "0.0012",
          "estimatedNAVPerToken": "1.00034",
          "coverageTestStatus": "PASS",
          "timestamp": "2026-11-15T14:00:00Z"
        }

T+settlement: C3 detects pacs.002 (or FedNow/RTP/SEPA/BACS equivalent)
        → SettlementMonitor.process_signal() matches UETR to ActiveLoan
        → Oracle Signing Service generates ECDSA attestation:
            {
              "uetr": "550e8400-e29b-41d4-a716-446655440000",
              "status": "SETTLED",
              "settledAmount": "2500000.00",
              "currency": "EUR",
              "settlementTimestamp": "2026-11-15T15:23:47Z",
              "bridgeLoanId": "BL-2026-0742",
              "compartment": "A",
              "svContractAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18"
            }
        → On-chain: confirmSettlement(uetr, amount, signature)
        → Smart contract verifies ECDSA signature against registered oracle key
        → Waterfall executes (see Part 4)
        → Distributions flow to Class A, then B, then E token holders

T+dispute: If C4 detects adversarial camt.056 recall:
        → Oracle Signing Service calls disputeAlert(uetr, reason, signature)
        → Smart contract freezes token redemption for affected receivable
        → NAV marked down by disputed amount
        → Dispute resolution per sub-participation agreement terms
```

### 3.4 Smart Contract Architecture

```
ERC3643Compliance.sol          — T-REX compliance module (identity registry, transfer rules)
BPIReceiverablePool.sol        — Pool state: active loans, NAV, coverage tests
BPIOracleVerifier.sol          — ECDSA signature verification for settlement attestations
BPIWaterfall.sol               — Priority-ordered distribution logic (8 levels)
BPIRedemptionManager.sol       — Investor redemption queue, coverage test gates
BPIGovernance.sol              — Multi-sig for admin functions (freeze, force transfer, param changes)
```

All contracts to be audited by two independent firms (Certik + Trail of Bits or OpenZeppelin) before mainnet deployment. Formal verification of the waterfall contract using Certora or equivalent tool.

---

## 5. Part 4 — Cash Waterfall

### 4.1 Inflows

| Source | Description | Frequency |
|--------|-------------|-----------|
| Bridge loan fee income | Fee = principal x bps x (days_funded / 365) per `compute_loan_fee()` | Per-settlement (continuous) |
| Principal repayment | Full principal returned on settlement confirmation | Per-settlement (continuous) |
| Default recovery | Partial recovery on defaulted loans (per sub-participation agreement) | Ad hoc |
| Reserve earnings | Interest on uninvested cash reserves (overnight deposits) | Daily |

### 4.2 Outflow Waterfall (8 Priorities)

The waterfall executes on-chain via `BPIWaterfall.sol` upon each settlement confirmation. Off-chain, the SV administrator reconciles daily.

```
Priority 1 — EXPENSES & FEES
├── SV operating expenses (administrator, audit, legal, regulatory filings)
├── Management fee to BPI Inc. (1.5-2.0% AUM, daily accrual)
├── Technology licensing fee to BPI Inc. (bps on monitored volume)
└── Gas costs for on-chain operations (ETH/L2 transaction fees)

Priority 2 — CLASS A INTEREST
├── SOFR/EURIBOR + contracted spread (150-250 bps)
├── Accrued daily, distributed on settlement events
└── If insufficient: coverage test triggered (see below)

Priority 3 — CLASS A PRINCIPAL REPAYMENT
├── Pro-rata as underlying loans settle
├── Investor may reinvest (rolling) or withdraw (T+2 redemption queue)
└── Withdrawal gated by coverage test compliance

Priority 4 — COVERAGE TEST CURE
├── Triggered if pool loss > 1.5% trailing 30-day OR
│   overcollateralisation ratio < 120%
├── ALL cash blocked from Priority 5-8
├── Redirected to Class A reserve until tests pass
└── Circuit breaker: if coverage test fails for 15 consecutive days,
    automatic Class A early redemption offer at par

Priority 5 — CLASS B INTEREST
├── SOFR/EURIBOR + contracted spread (400-600 bps)
├── Only paid after Class A fully current AND coverage tests pass
└── Accrued during coverage test breach (paid when cure achieved)

Priority 6 — CLASS B PRINCIPAL REPAYMENT
├── Pro-rata as loans settle, only after Class A fully repaid per settlement
├── T+5 weekly liquidity window
└── 6-month soft lock-up: early redemption incurs 2% penalty

Priority 7 — PERFORMANCE FEE TO BPI INC.
├── 15-20% of net returns above 8% annualised hurdle
├── Quarterly crystallisation (to prevent gaming via short-term volatility)
├── High-water mark: no performance fee until previous losses recovered
└── Clawback provision: 2-year lookback for loss reversal

Priority 8 — CLASS E RESIDUAL DISTRIBUTION
├── All remaining cash flows after 1-7 satisfied
├── Distributed to BPI Inc. (100% Class E holder)
├── Represents BPI's primary equity upside from P7
└── Frequency: Monthly (or on-demand for amounts > EUR 100K)
```

### 4.3 Coverage Tests

Four tests must be satisfied continuously. Breach of any test triggers Priority 4 (block B + E distributions):

| Test | Threshold | Measurement | Action on Breach |
|------|-----------|-------------|------------------|
| **Overcollateralisation** | SV assets / Class A outstanding >= 120% | Daily NAV calculation | Block all Class B + E distributions; redirect to Class A reserve |
| **Loss Coverage** | Trailing 30-day net losses < 1.5% of pool | Rolling 30-day window from C3 settlement data | Block B + E; accelerate Class A repayment if sustained > 15 days |
| **Concentration** | Single corridor exposure < 40% of pool | Per-compartment, measured at each new loan addition | Cap new originations in over-concentrated corridor |
| **Duration** | Weighted-average pool duration < 14 days | Weighted by principal outstanding | If exceeded: offer Class A early redemption at par; pause new Class B issuance |

The loss rate calculation uses actual settlement data from C3, not model-predicted losses. `SettlementMonitor.get_active_loans()` provides the current pool snapshot; the `RepaymentLoop.trigger_repayment()` method records each settlement with `is_partial`, `shortfall_amount`, and `shortfall_pct` fields that feed directly into the loss computation.

### 4.4 Worked Example

```
Pool state at T=0:
  Active loans:        50
  Total principal:     EUR 25,000,000
  Class A outstanding: EUR 20,000,000 (80%)
  Class B outstanding: EUR 3,750,000  (15%)
  Class E:             EUR 1,250,000  (5%)
  Trailing 30d loss:   0.3% (well within 1.5% threshold)
  OC ratio:            125% (above 120% minimum)

Settlement event: Loan BL-2026-0742 settles
  Principal:   EUR 2,500,000
  Fee earned:  EUR 2,500,000 × 350 bps × (5/365) = EUR 1,198.63
  Total cash:  EUR 2,501,198.63

Waterfall execution:
  P1 — Expenses:           EUR 250.00 (admin fee allocation)
        Management fee:    EUR 2,500,000 × 1.75% × (5/365) = EUR 599.32
        Technology licence: EUR 2,500,000 × 10 bps × (5/365) = EUR 34.25
        Subtotal:          EUR 883.57
  P2 — Class A interest:   EUR 2,000,000 × (SOFR 4.35% + 200 bps) × (5/365)
                          = EUR 2,000,000 × 6.35% × 0.01370 = EUR 1,739.73
  P3 — Class A principal:  EUR 2,000,000 (80% of loan principal, pro-rata)
  P4 — Coverage test:      PASS (no cure needed)
  P5 — Class B interest:   EUR 375,000 × (SOFR 4.35% + 500 bps) × (5/365)
                          = EUR 375,000 × 9.35% × 0.01370 = EUR 480.47
  P6 — Class B principal:  EUR 375,000 (15% of loan principal, pro-rata)
  P7 — Performance fee:    Computed quarterly (accrued, not distributed per settlement)
  P8 — Class E residual:   EUR 2,501,198.63 - 883.57 - 1,739.73 - 2,000,000
                          - 480.47 - 375,000 = EUR 123,094.86
        (to BPI Inc. as Class E holder)
```

---

## 6. Part 5 — Revenue Architecture & Financial Projections

### 5.1 BPI Revenue Streams from P7

P7 generates four distinct revenue streams for BPI Inc., each with different risk/return characteristics and accounting treatment:

| Revenue Stream | Source | Rate | Accounting | Tax Treatment (Canada) |
|----------------|--------|------|------------|----------------------|
| **Management fee** | SV → BPI Inc. (Portfolio Management Agreement) | 1.5-2.0% AUM annually (daily accrual) | Service revenue, accrual basis | Ordinary business income; protected by Canada-Luxembourg treaty (Art. 7) |
| **Performance fee** | SV → BPI Inc. (Portfolio Management Agreement) | 15-20% above 8% hurdle (quarterly crystallisation, high-water mark) | Contingent revenue, recognised at crystallisation | Ordinary business income |
| **Technology licensing fee** | SV → BPI Inc. (IP Licensing Agreement) | bps on monitored settlement volume | Licensing revenue, accrual basis | Royalty income; protected by Canada-Luxembourg treaty (Art. 12, 10% withholding max) |
| **Class E residual returns** | Waterfall Priority 8 (residual after all senior/mezzanine obligations) | Variable — absorbs all upside after debt service | Investment income / mark-to-market | Capital gains (if structured as equity participation) or ordinary income |

### 5.2 Three-Scenario AUM Projections

AUM projections are driven by bridge loan origination volume (determined by bank partner count and corridor activity) and the percentage of receivables channelled through the SV.

**Conservative scenario:** 1 bank partner, 2 corridors, slow investor onboarding

| Metric | Year 1 | Year 2 | Year 3 | Year 5 |
|--------|--------|--------|--------|--------|
| Bridge loan volume (annual) | EUR 500M | EUR 1.5B | EUR 3B | EUR 8B |
| % channelled through SV | 5% | 7% | 8% | 10% |
| Average outstanding AUM | EUR 25M | EUR 100M | EUR 250M | EUR 800M |
| Class A outstanding | EUR 20M | EUR 80M | EUR 200M | EUR 640M |
| Class B outstanding | EUR 3.75M | EUR 15M | EUR 37.5M | EUR 120M |
| Class E (BPI) | EUR 1.25M | EUR 5M | EUR 12.5M | EUR 40M |

**Base scenario:** 3 bank partners, 5 corridors, standard institutional uptake

| Metric | Year 1 | Year 2 | Year 3 | Year 5 |
|--------|--------|--------|--------|--------|
| Bridge loan volume (annual) | EUR 1B | EUR 4B | EUR 10B | EUR 25B |
| % channelled through SV | 5% | 10% | 12% | 15% |
| Average outstanding AUM | EUR 50M | EUR 200M | EUR 500M | EUR 2B |
| Class A outstanding | EUR 40M | EUR 160M | EUR 400M | EUR 1.6B |
| Class B outstanding | EUR 7.5M | EUR 30M | EUR 75M | EUR 300M |
| Class E (BPI) | EUR 2.5M | EUR 10M | EUR 25M | EUR 100M |

**Aggressive scenario:** 5+ bank partners, 10+ corridors, strong secondary market

| Metric | Year 1 | Year 2 | Year 3 | Year 5 |
|--------|--------|--------|--------|--------|
| Bridge loan volume (annual) | EUR 2B | EUR 8B | EUR 20B | EUR 50B |
| % channelled through SV | 5% | 12% | 15% | 20% |
| Average outstanding AUM | EUR 100M | EUR 500M | EUR 1B | EUR 5B |
| Class A outstanding | EUR 80M | EUR 400M | EUR 800M | EUR 4B |
| Class B outstanding | EUR 15M | EUR 75M | EUR 150M | EUR 750M |
| Class E (BPI) | EUR 5M | EUR 25M | EUR 50M | EUR 250M |

### 5.3 Revenue Per Scenario

**Conservative:**

| Revenue Stream | Year 1 | Year 2 | Year 3 | Year 5 |
|----------------|--------|--------|--------|--------|
| Management fee (1.75% AUM) | EUR 438K | EUR 1.75M | EUR 4.38M | EUR 14.0M |
| Performance fee (17.5% above 8% hurdle) | EUR 50K | EUR 250K | EUR 750K | EUR 3.0M |
| Technology licensing (10 bps on volume) | EUR 500K | EUR 1.5M | EUR 3.0M | EUR 8.0M |
| Class E residual (estimated 15% return on E) | EUR 188K | EUR 750K | EUR 1.88M | EUR 6.0M |
| **Total BPI P7 revenue** | **EUR 1.18M** | **EUR 4.25M** | **EUR 10.0M** | **EUR 31.0M** |

**Base:**

| Revenue Stream | Year 1 | Year 2 | Year 3 | Year 5 |
|----------------|--------|--------|--------|--------|
| Management fee (1.75% AUM) | EUR 875K | EUR 3.5M | EUR 8.75M | EUR 35.0M |
| Performance fee (17.5% above 8% hurdle) | EUR 100K | EUR 500K | EUR 1.5M | EUR 8.0M |
| Technology licensing (10 bps on volume) | EUR 1.0M | EUR 4.0M | EUR 10.0M | EUR 25.0M |
| Class E residual (estimated 15% return on E) | EUR 375K | EUR 1.5M | EUR 3.75M | EUR 15.0M |
| **Total BPI P7 revenue** | **EUR 2.35M** | **EUR 9.5M** | **EUR 24.0M** | **EUR 83.0M** |

**Aggressive:**

| Revenue Stream | Year 1 | Year 2 | Year 3 | Year 5 |
|----------------|--------|--------|--------|--------|
| Management fee (1.75% AUM) | EUR 1.75M | EUR 8.75M | EUR 17.5M | EUR 87.5M |
| Performance fee (17.5% above 8% hurdle) | EUR 200K | EUR 1.25M | EUR 3.75M | EUR 20.0M |
| Technology licensing (10 bps on volume) | EUR 2.0M | EUR 8.0M | EUR 20.0M | EUR 50.0M |
| Class E residual (estimated 15% return on E) | EUR 750K | EUR 3.75M | EUR 7.5M | EUR 37.5M |
| **Total BPI P7 revenue** | **EUR 4.7M** | **EUR 21.75M** | **EUR 48.75M** | **EUR 195.0M** |

### 5.4 Comparable Tokenised Fund Economics

| Fund | AUM | Fee Structure | Annual Fee Revenue | BPI Advantage |
|------|-----|---------------|-------------------|---------------|
| BlackRock BUIDL | $1.9B | ~50 bps management | ~$9.5M | BPI charges 175 bps — justified by ML pricing, settlement oracle, and active management. Government bond wrapper requires zero intelligence; P7 requires continuous ML inference, settlement monitoring, and waterfall management. |
| Franklin Templeton BENJI | $742M | ~40 bps management | ~$3.0M | Similar justification. BENJI is a passive fund buying T-bills. P7 is an actively managed, ML-driven receivable pool. |
| Centrifuge (largest pool) | ~$200M per pool | 1-2% management + junior tranche | ~$2-4M | Comparable fee level but no performance fee, no technology licensing, no oracle premium. BPI's multi-stream revenue model generates 2-3x revenue per AUM dollar vs. Centrifuge. |

### 5.5 Unit Economics

**Per-loan economics (EUR 2.5M bridge loan, 5-day duration, 350 bps):**

| Item | Amount | % of Fee |
|------|--------|----------|
| Gross fee | EUR 1,198.63 | 100% |
| SV expenses (Priority 1) | EUR 250.00 | 20.9% |
| BPI management fee (Priority 1) | EUR 599.32 | 50.0% |
| BPI tech licensing (Priority 1) | EUR 34.25 | 2.9% |
| Class A interest (Priority 2) | EUR 1,739.73 | From principal flow |
| Class B interest (Priority 5) | EUR 480.47 | From principal flow |
| Class E residual | Variable | Remainder |

BPI captures approximately 53% of fee income directly (management + licensing) plus 100% of Class E residual. On a pool basis with normal settlement patterns, BPI's total take rate is approximately 60-70% of gross fee income — substantially higher than the 30% Phase 1 royalty rate from P2 licensing.

**This is the core strategic rationale for P7: it converts BPI from a technology licensor (30% Phase 1 royalty) to an asset manager (60-70% effective take rate).**

---

## 7. Part 6 — C-Component Engineering Map

### 6.1 C3 Extensions (5-7 weeks total)

**Extension 1: Oracle Signing Service (~3-4 weeks)**

The Oracle Signing Service bridges the on-chain/off-chain boundary by cryptographically attesting to settlement events observed by C3.

Implementation:
- HSM-backed ECDSA key pair (secp256k1) for attestation signing
- Key ceremony: 2-of-3 multi-sig for key generation; HSM stores private key; public key registered on-chain in `BPIOracleVerifier.sol`
- Gas management: L2 deployment (Polygon, Arbitrum, or Base) for sub-$0.01 per attestation; L1 Ethereum for high-value settlements (>EUR 1M)
- Circuit breaker: if chain congestion delays attestation >30 seconds, fall back to off-chain queue; retry on next block with sufficient gas
- Multi-sig requirement: any single settlement >EUR 1M requires 2-of-3 oracle attestation (multiple C3 instances or C3 + administrator)

Attestation payload (signed by Oracle Signing Service):
```json
{
  "uetr": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SETTLED",
  "settledAmount": "2500000.00",
  "currency": "EUR",
  "settlementTimestamp": "2026-11-15T15:23:47Z",
  "bridgeLoanId": "BL-2026-0742",
  "compartment": "A",
  "svContractAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  "c3InstanceId": "c3-prod-eu-west-1a",
  "attestationTimestamp": "2026-11-15T15:23:48Z",
  "nonce": 47291
}
```

Smart contract interface:
```solidity
function confirmSettlement(
    bytes32 uetr,
    uint256 amount,
    uint256 timestamp,
    bytes memory signature
) external onlyRegisteredOracle {
    require(verifySignature(uetr, amount, timestamp, signature), "Invalid oracle signature");
    require(!settlements[uetr].confirmed, "Already settled");

    settlements[uetr] = Settlement({
        amount: amount,
        timestamp: timestamp,
        confirmed: true,
        confirmedAt: block.timestamp
    });

    emit SettlementConfirmed(uetr, amount, timestamp);
    _executeWaterfall(uetr, amount);
}
```

Codebase touchpoints:
- `lip/c3_repayment_engine/repayment_loop.py` — `RepaymentLoop.trigger_repayment()` gains a new callback hook for oracle attestation. After the existing repayment record is built (line 380-407 in current code), a new `_attest_settlement()` method signs and publishes the attestation.
- `lip/common/encryption.py` — Existing `sign_hmac_sha256()` is HMAC-based. The oracle requires ECDSA (secp256k1). New function `sign_ecdsa_secp256k1(message: bytes, private_key: bytes) -> bytes` to be added alongside existing crypto functions. The `cryptography` library already imported supports this.

**Extension 2: NAV Event Feed (~1-2 weeks)**

Hourly pool-level aggregation published via Kafka topic and REST API for the SV administrator's NAV calculation.

Implementation:
- Kafka topic: `bpi.sv.nav-events` (partitioned by compartment)
- Redis cache: latest NAV snapshot per compartment (TTL: 2 hours)
- Aggregation: queries `SettlementMonitor.get_active_loans()` and `RepaymentLoop.get_active_loans()` to compute pool metrics

NAV event payload:
```json
{
  "compartment": "A",
  "activeLoans": 47,
  "totalExposure": "23450000.00",
  "weightedAveragePD": "0.034",
  "weightedAverageFeeBps": 342,
  "weightedAverageDaysToMaturity": 8.3,
  "settledLast60min": 3,
  "settledAmountLast60min": "1875000.00",
  "defaultedLast60min": 0,
  "trailingLossRate30d": "0.0012",
  "trailingLossRate7d": "0.0005",
  "estimatedNAVPerToken": "1.00034",
  "coverageTestStatus": {
    "overcollateralisation": {"value": 1.25, "threshold": 1.20, "status": "PASS"},
    "lossCoverage": {"value": 0.0012, "threshold": 0.015, "status": "PASS"},
    "concentration": {"maxCorridor": 0.32, "threshold": 0.40, "status": "PASS"},
    "duration": {"weightedAvgDays": 8.3, "threshold": 14, "status": "PASS"}
  },
  "timestamp": "2026-11-15T14:00:00Z"
}
```

Codebase touchpoints:
- New module: `lip/c3_repayment_engine/nav_feed.py`
- Consumes: `SettlementMonitor.get_active_loans()`, `PortfolioRiskEngine.compute_var()`, `PortfolioRiskEngine.compute_concentration()`
- `lip/risk/portfolio_risk.py` — `PortfolioRiskEngine.get_risk_summary()` (line 269-320) already produces VaR and concentration metrics. NAV Feed wraps this with pool-level aggregation specific to each SV compartment.

**Extension 3: Dispute Alert Hook (~1 week)**

When C4 classifies a payment as adversarial (dispute confirmed), the Oracle Signing Service publishes a dispute alert on-chain that freezes token redemption for the affected receivable.

Implementation:
- Triggered by: C4 `DisputeClassifier` output where `dispute_class == "DISPUTE_CONFIRMED"`
- Oracle signs: `disputeAlert(uetr, reason, disputeTimestamp, signature)`
- Smart contract: marks receivable as disputed; blocks redemption queue for affected amount; adjusts NAV downward

```solidity
function disputeAlert(
    bytes32 uetr,
    string memory reason,
    uint256 disputeTimestamp,
    bytes memory signature
) external onlyRegisteredOracle {
    require(verifySignature(uetr, reason, disputeTimestamp, signature), "Invalid signature");

    disputes[uetr] = Dispute({
        reason: reason,
        reportedAt: block.timestamp,
        resolved: false
    });

    // Adjust NAV and freeze affected amount
    _freezeRedemptionForDispute(uetr);
    emit DisputeAlerted(uetr, reason, disputeTimestamp);
}
```

### 6.2 C7 Extensions (8-10 weeks total)

**Extension 1: Sub-Participation Notification API (~3-4 weeks)**

New REST endpoint that notifies the SV administrator when a bridge loan is originated, allowing the administrator to update the pool composition and adjust NAV.

Endpoint: `POST /sv/participation-notify`

Request payload:
```json
{
  "loanId": "BL-2026-0742",
  "uetr": "550e8400-e29b-41d4-a716-446655440000",
  "corridor": "EUR_USD",
  "counterpartyHashedId": "a3f2b1c4d5e6f7...",
  "advanceAmount": "2500000.00",
  "currency": "EUR",
  "disbursementTimestamp": "2026-11-10T09:15:22Z",
  "estimatedDurationDays": 5,
  "c2RiskBucket": "CLASS_A",
  "c2PD": 0.032,
  "c2FeeBps": 350,
  "svCompartment": "A",
  "licenseeId": "HSBC_UK_001",
  "deploymentPhase": "HYBRID"
}
```

Codebase touchpoints:
- `lip/c7_execution_agent/agent.py` — `ExecutionAgent.process_payment()` gains a post-offer hook. After `_build_loan_offer()` returns (line 426), and after offer delivery (line 440-447), a new `_notify_sv()` method fires the sub-participation notification if the licensee is configured for SV participation.
- The `LicenseeContext` in `lip/c8_license_manager/license_token.py` gains a new field: `sv_participation_enabled: bool = False` (default off; enabled per-licensee when the sub-participation agreement is signed).

**Extension 2: ELO Settlement-and-Receipt Confirmation (~2-3 weeks)**

New REST endpoint that confirms to the SV that a loan has been repaid and the bank's core banking system has recorded the repayment.

Endpoint: `POST /sv/repayment-confirmed`

Request payload:
```json
{
  "loanId": "BL-2026-0742",
  "uetr": "550e8400-e29b-41d4-a716-446655440000",
  "repaidAmount": "2500000.00",
  "repaidCurrency": "EUR",
  "repaidTimestamp": "2026-11-15T15:23:47Z",
  "confirmedByCBS": true,
  "cbsReferenceId": "CBS-2026-1115-00742",
  "feeEarned": "1198.63",
  "isPartial": false,
  "shortfallAmount": "0.00"
}
```

Codebase touchpoints:
- `lip/c3_repayment_engine/repayment_loop.py` — `RepaymentLoop.trigger_repayment()` (line 293-419) already produces a `repayment_record` with all required fields. The new endpoint wraps this record with CBS confirmation and routes it to the SV administrator + Oracle Signing Service.
- Integration with `lip/c3_repayment_engine/settlement_handlers.py` — the `SettlementHandlerRegistry` dispatches settlement signals from 5 rails. The SV confirmation is a downstream consumer, not a new signal source.

**Extension 3: B2B2C Investor Distribution Passthrough (Phase 2 — deferred)**

Phase 2 only. When individual investors (via bank distribution channels) hold Class A or B notes, the bank's wealth management platform needs distribution data. Deferred because Phase 1 targets institutional investors with direct SV subscriptions.

### 6.3 C8 Extensions (3-4 weeks total)

**Extension 1: Management Fee Accrual**

Daily fee computation added to C8's licensing and metering module:

```
daily_management_fee = (compartment_AUM × management_fee_rate) / 365
```

Implementation: new class `SVFeeAccrual` in `lip/c8_license_manager/sv_fee_accrual.py`
- Reads compartment AUM from NAV Event Feed (C3 Extension 2)
- Accrues daily to BPI Inc.'s management fee receivable
- Settles quarterly against SV operating account
- Transfer pricing documentation: fee benchmarked against CLO/CDO manager fees (1.0-2.5% AUM, Preqin benchmark database)

**Extension 2: Performance Fee**

```
performance_fee = max(0, (net_return - 8% hurdle) × fee_rate)
```

Where:
- `net_return` = (ending NAV - beginning NAV + distributions - subscriptions) / beginning NAV, annualised
- `fee_rate` = 15-20% (per investor class offering memorandum)
- High-water mark: NAV must exceed previous crystallisation NAV before fee accrues
- Crystallisation: quarterly (31 March, 30 June, 30 September, 31 December)
- Clawback: if trailing 8-quarter average return < hurdle, prior performance fees subject to 50% clawback

**Extension 3: Technology Licensing Fee (Intra-Group)**

The IP Licensing Agreement between BPI Inc. (licensor) and BPI Receivables S.A. (licensee) charges bps on monitored settlement volume. This is intra-group revenue but must be priced at arm's length.

- Rate: 10-25 bps of settlement volume monitored by C3
- Benchmark: comparable SaaS settlement monitoring services (Volante Technologies, Bottomline Technologies, ACI Worldwide — published pricing 5-30 bps)
- Documentation: Luxembourg transfer pricing study (OECD TNMM or CUP method), BPI Master File, Luxembourg Local File
- APA: bilateral Canada-Luxembourg advance pricing agreement recommended

### 6.4 C6 Minor Extension (~1 week)

**Circular Exposure Rule**

If a bridge loan's counterparty (the entity whose payment failed) is also an investor in the SV, the investor effectively has exposure to their own creditworthiness. This creates a circular dependency that must be flagged.

Implementation:
```python
# In lip/c6_aml_velocity/cross_licensee.py or new module:
def check_circular_exposure(
    loan_counterparty_hashed_id: str,
    sv_investor_whitelist: set[str],
) -> bool:
    """Return True if the counterparty is also an SV investor."""
    return loan_counterparty_hashed_id in sv_investor_whitelist
```

The `CrossLicenseeAggregator` in `lip/c6_aml_velocity/cross_licensee.py` already uses SHA-256 hashed identifiers with salt rotation. The circular exposure check uses the same hashing infrastructure — the SV investor whitelist is stored as hashed IDs, and the loan counterparty ID is hashed with the same salt before comparison. No plaintext identifiers cross system boundaries.

Action on detection: flag for compliance review. Do not auto-block (the counterparty may be a large bank that is legitimately both a bridge loan recipient and an SV investor). The compliance officer decides whether the circular exposure is within acceptable limits.

---

## 8. Part 7 — Investor Acquisition Strategy & Secondary Market Design

### 7.1 Target Investor Types

P7's ultra-short-duration, settlement-observable profile appeals to four distinct investor segments, each requiring a different acquisition approach:

**Tier 1 — Money Market Funds (Primary Target)**

| Characteristic | Why P7 Fits |
|----------------|-------------|
| Mandate | Ultra-short duration (<1 year), daily liquidity, investment-grade credit quality |
| Current holdings | Government bonds, CP, CDs, repo (SOFR/EURIBOR flat to +50 bps) |
| P7 appeal | SOFR/EURIBOR + 150-250 bps (Class A) with 3-21 day WAL; 20% subordination |
| Allocation size | EUR 5-25M per fund (typical new asset class allocation) |
| Decision maker | CIO / Head of Fixed Income; compliance sign-off on new asset class |
| Due diligence focus | Credit quality of underlying pool (C2 ML model validation), liquidity (redemption mechanics), legal structure (compartment ring-fencing), operational risk (oracle reliability) |
| Target names | Amundi (EUR 2.1T AUM), BlackRock (money market division), HSBC Asset Management, Pictet |
| Acquisition timeline | 6-12 months from first meeting to allocation |

**Tier 2 — Bank Treasury Desks**

| Characteristic | Why P7 Fits |
|----------------|-------------|
| Mandate | Liquidity buffer management, yield enhancement on excess reserves |
| Current holdings | Government bonds, central bank deposits, repo, high-grade CP |
| P7 appeal | Higher yield than traditional liquidity assets; familiarity with payment corridor risk |
| Allocation size | EUR 10-50M per bank (LCR-eligible if structured correctly) |
| Decision maker | Group Treasurer / Head of ALM; ALCO approval required |
| Due diligence focus | Basel capital treatment (Group 1a qualification), LCR eligibility (HQLA classification), operational risk |
| Target names | BPI's existing bank partners (natural cross-sell), other banks in BPI's pipeline |
| Acquisition timeline | 3-6 months (shorter because they already understand the underlying asset) |

**Tier 3 — Private Credit Funds**

| Characteristic | Why P7 Fits |
|----------------|-------------|
| Mandate | Yield generation, diversification from traditional private credit (long duration, illiquid) |
| Current holdings | Direct lending, CLO tranches, real estate debt, infrastructure debt |
| P7 appeal | Ultra-short duration reduces liquidity risk; ML-priced credit is a differentiator in LP reporting |
| Allocation size | EUR 5-20M per fund (Class B for yield, Class A for anchoring) |
| Decision maker | Portfolio Manager / Investment Committee |
| Due diligence focus | Track record (historical loss rates), ML model performance (C2 validation), manager (BPI) capabilities |
| Target names | Ares Management, Tikehau Capital, Muzinich, PIMCO (alternatives division) |
| Acquisition timeline | 6-9 months |

**Tier 4 — Family Offices & Institutional Allocators**

| Characteristic | Why P7 Fits |
|----------------|-------------|
| Mandate | Diversified fixed income; emerging alternative asset classes |
| P7 appeal | Novel asset class with technology differentiation; skin-in-the-game alignment (BPI holds Class E) |
| Allocation size | EUR 1-5M per office (smaller tickets, more relationship-driven) |
| Decision maker | CIO / Investment Director (often single decision maker) |
| Due diligence focus | Manager reputation, concept clarity, fee transparency |
| Acquisition timeline | 3-6 months (faster decision cycle than institutional funds) |

### 7.2 Investor Onboarding Funnel

```
Pipeline (100 qualified leads)
    │
    ├── 50 receive offering memorandum (after NDA)
    │       │
    │       ├── 25 schedule due diligence meeting
    │       │       │
    │       │       ├── 15 complete full DD (legal, ML model review, operational)
    │       │       │       │
    │       │       │       ├── 10 receive allocation committee approval
    │       │       │       │       │
    │       │       │       │       ├── 7 submit subscription agreement
    │       │       │       │       │       │
    │       │       │       │       │       └── 5 complete KYC/AML and fund
    │       │       │       │       │
    │       │       │       │       └── 3 decline (timing, mandate fit, internal capacity)
    │       │       │       │
    │       │       │       └── 5 fail DD (concerns about track record, model, or structure)
    │       │       │
    │       │       └── 10 decline DD (not a fit, competing priorities)
    │       │
    │       └── 25 no response / pass
    │
    └── 50 not qualified (mandate mismatch, jurisdiction, size)

TARGET: 5 subscribed investors within 6 months of pilot launch
AVERAGE SUBSCRIPTION: EUR 5M (Class A), EUR 2M (Class B)
TARGET AUM: EUR 25-35M at 6-month mark
```

### 7.3 Investor Materials Required

| Document | Purpose | Timeline |
|----------|---------|----------|
| Offering Memorandum (Class A + B) | Comprehensive disclosure document for qualified investors | W4-W8 (legal counsel) |
| Executive Summary (5 pages) | One-pager for initial outreach; pool overview, return profile, structure | W2-W4 |
| ML Model Validation Report | C2 PD model performance (AUC, confusion matrix, out-of-time validation) | Existing (SR 11-7 pack) |
| Oracle Architecture Whitepaper | Technical description of the first-party settlement oracle for DD | W6-W10 |
| Historical Performance Backtest | Simulated pool performance using 12+ months of bridge lending data | W8-W16 |
| Legal Opinion (Luxembourg counsel) | Confirms: true sale / sub-participation validity, compartment ring-fencing, DLT token legal status | W4-W10 |
| Tax Opinion | Confirms: SV tax treatment, treaty protection for BPI fees, investor withholding | W4-W10 |
| Basel Capital Treatment Memo | Confirms: Group 1a classification, risk weight for bank treasury investors | W6-W12 |

### 7.4 Secondary Market Design

Secondary market liquidity is critical for investor confidence but must develop in phases to manage regulatory and operational complexity.

**Phase 1: Bilateral OTC with ERC-3643 Transfer Restrictions (Launch)**

- Investors may transfer tokens to other verified ERC-3643 wallets (i.e., wallets with valid ONCHAINID credentials in the Identity Registry)
- Transfer must comply with: jurisdiction whitelist, minimum denomination, holding limits, lock-up periods
- BPI Receivables S.A. (issuer) maintains the Identity Registry — only pre-approved investors can receive tokens
- Bilateral negotiation between seller and buyer; SV administrator processes transfer request
- No public order book; no automated market making
- Estimated secondary market activity: <5% of outstanding tokens per quarter

**Phase 2: RWA Marketplace Integration (Year 2)**

- Integrate with established RWA secondary marketplaces:
  - **Securitize** (SEC-registered ATS, $1B+ in tokenised securities traded)
  - **Backed Finance** (Swiss-regulated, EU passport)
  - **Centrifuge** (if interoperable with ERC-3643)
- BPI Receivables S.A. remains the identity registry administrator — marketplace integration means the marketplace accesses the ERC-3643 transfer rules, not that it bypasses them
- Potential for request-for-quote (RFQ) trading with designated market makers
- Estimated secondary market activity: 10-20% of outstanding tokens per quarter

**Phase 3: DEX Liquidity Pool with Compliance Hooks (Year 3+)**

- Uniswap v4 hooks enable custom compliance logic within AMM pools:
  - `beforeSwap` hook: verify buyer ONCHAINID credentials
  - `afterSwap` hook: update Identity Registry, enforce holding limits
  - `beforeAddLiquidity` hook: verify LP ONCHAINID credentials
- Only feasible after ERC-3643 v4 (Tokeny's upgradeable version, launched 2025) demonstrates compatibility with AMM mechanics
- Regulatory dependencies: ESMA DLT Pilot Regime extension, MiCA secondary market rules
- Estimated secondary market activity: 20-40% of outstanding tokens per quarter

### 7.5 Competitive Positioning vs. Existing Yield Products

| Product | Yield | Duration | Liquidity | Intelligence | P7 Advantage |
|---------|-------|----------|-----------|-------------|--------------|
| Money market fund (Vanguard VMFXX) | SOFR ~4.35% | Overnight to 13 weeks | T+1 | None | P7 Class A: SOFR + 200 bps = ~6.35%; ML-priced credit adds 150-250 bps yield premium |
| Commercial paper (A1/P1) | SOFR + 10-30 bps | 30-270 days | T+2 | None | P7: shorter duration (3-21 days) with higher yield; observable settlement reduces credit opacity |
| BlackRock BUIDL | ~SOFR | Overnight | T+0 (on-chain) | None | P7: +200 bps yield with comparable on-chain liquidity. BUIDL has zero alpha; P7 has ML alpha |
| Centrifuge pools | 8-15% | 30-180 days | Weekly to monthly | None | P7: comparable yield for Class B with dramatically shorter duration and real-time NAV |

---

## 9. Part 8 — Consolidated Engineering Timeline

### 8.1 Sprint Schedule (24 weeks / 9 sprints)

| Sprint | Weeks | Deliverable | Dependencies | Team |
|--------|-------|-------------|-------------|------|
| Sprint 1 | W1-W2 | **C3 Extension 2 — NAV Event Feed** | Kafka topic provisioning; NAV payload schema agreed with SV administrator | 1 senior engineer |
| Sprint 2 | W3-W6 | **C3 Extension 1 — Oracle Signing Service** | HSM procurement + key ceremony; L2 chain selection; `BPIOracleVerifier.sol` deployed to testnet | 1 senior engineer + 1 smart contract dev |
| Sprint 3 | W7-W8 | **C3 Extension 3 — Dispute Alert Hook** | C4 output routing confirmed; `disputeAlert()` in smart contract tested | 1 senior engineer |
| Sprint 4 | W9-W12 | **C7 Extensions 1+2 — Sub-participation API + Repayment Confirm** | Sub-participation agreement template from legal counsel; bank partner API integration spec | 1 senior engineer |
| Sprint 5 | W13-W15 | **C8 Extensions 1-3 — SV Fee Accrual + Performance Fee + Intra-group Licensing** | Transfer pricing study from Luxembourg counsel; fee parameters agreed with SV board | 1 senior engineer |
| Sprint 6 | W16 | **C6 Minor Extension — Circular Exposure Rule** | SV investor whitelist format agreed with administrator | 1 senior engineer |
| Sprint 7 | W17-W18 | **Integration Test — Full E2E Flow** | All extensions complete; smart contracts audited; testnet environment stable | 2 senior engineers |
| Sprint 8 | W19-W20 | **Shadow Run — Real Loans, Internal SV, No External Investors** | SV incorporated; internal-only Compartment A active; 100% Class E (BPI) | 2 senior engineers + SV administrator |
| Sprint 9 | W21-W24 | **Pilot — 1-3 External Investors, One Corridor, EUR 10-25M Cap** | At least 1 external investor KYC/AML complete; Class A subscription signed | 2 senior engineers + SV administrator + BPI compliance |

### 8.2 Parallel Legal Track

| Weeks | Workstream | Responsible | Deliverable |
|-------|-----------|-------------|-------------|
| W1 | Engage Luxembourg securitisation counsel | BPI General Counsel | Engagement letter signed; scope of work defined |
| W2-W4 | Incorporate BPI RECEIVABLES S.A. | Luxembourg counsel + notary | SV incorporation documents, articles of association, compartment deed |
| W3-W6 | Draft sub-participation agreement | Luxembourg counsel + BPI | Agreement template for bank partner review |
| W4-W8 | Draft Offering Memorandum (Class A + B) | Luxembourg counsel + BPI | OM covering: structure, risks, fees, redemption, coverage tests, tax |
| W2-W4 | Select ERC-3643 platform provider | BPI CTO + procurement | RFP to Tokeny, InvestaX, Fireblocks; selection based on compliance, cost, interoperability |
| W6-W10 | Deploy smart contracts + token classes | Platform provider + BPI | Smart contracts on testnet → security audit → mainnet deployment |
| W2-W4 | GDPR Data Processing Agreement addendum | BPI DPO + Luxembourg counsel | DPA covering UETR data flows between BPI, SV, bank |
| W2-W5 | Basel capital treatment memo | External regulatory consultant | Memo confirming Group 1a classification, risk weight, SSFA treatment |
| W8-W16 | Investor onboarding (KYC/AML) | SV administrator + BPI compliance | ONCHAINID credential issuance for each investor; Identity Registry population |
| W4-W8 | Transfer pricing study | Luxembourg tax adviser (Big-4) | Contemporaneous study covering management fee, performance fee, technology licensing |
| W20+ | First external subscription | SV administrator + investor | Class A subscription agreement signed; fiat transferred; tokens minted |
| W22+ | First live bridge loan in SV pool | Full operational team | End-to-end: C1 → C2 → C7 → SV notification → NAV update → oracle attestation → waterfall |

### 8.3 Key Milestones

| Milestone | Target Date | Gate Criteria |
|-----------|-------------|---------------|
| SV incorporation complete | W4 (end of month 1) | Articles registered with Luxembourg RCS |
| Smart contracts audited | W10 (end of month 2.5) | Two independent audits; zero critical findings |
| Sub-participation agreement executed | W12 (end of month 3) | Bank partner legal sign-off |
| Shadow run begins | W19 (end of month 4.75) | All C-component extensions integrated; E2E test passing |
| First external investor onboarded | W21 (end of month 5.25) | KYC/AML complete; ONCHAINID issued; subscription signed |
| Pilot go-live | W22 (end of month 5.5) | First live bridge loan originated, tracked, settled, and distributed through full waterfall |
| Pilot evaluation | W24 (end of month 6) | Performance report to SV board: loss rates, NAV accuracy, oracle reliability, investor feedback |

---

## 10. Part 9 — What Stays in the Long-Horizon P7 Patent

The following capabilities are architecturally sound but blocked by current infrastructure or regulatory limitations. They are documented in the P7 patent claims as future embodiments, not implemented in P7 v0.

### 9.1 Per-Loan Real-Time Dutch Auction

**Concept:** Instead of pooling receivables and issuing tranched notes, each individual bridge loan is offered to investors via a real-time Dutch auction. Price starts at par and decreases until an investor bids.

**Why deferred:** DLT block finality is incompatible with sub-100ms bridge loan trigger times. Ethereum L1 finalises in ~12 minutes. Even L2s (Arbitrum, Polygon zkEVM) have 2-10 second finality. The bridge loan must be originated in milliseconds (C7 decision → C3 registration → bank disbursement). An auction with DLT settlement would delay origination by seconds to minutes — unacceptable for the payment recipient who needs immediate liquidity.

**Patent protection:** The auction mechanism is claimed as a method of allocating individual receivables to investors using a decreasing-price auction with cryptographic bid verification. The claim is independent of the finality constraint — future L2/L3 infrastructure with sub-second finality would enable implementation.

### 9.2 Fully Decentralised Oracle

**Concept:** Replace BPI's first-party oracle with a decentralised oracle network (Chainlink, Pyth, UMA Optimistic Oracle) that aggregates settlement signals from multiple independent sources.

**Why deferred:** Adds latency (consensus rounds) and counterparty risk (oracle operators may not have access to SWIFT settlement data). BPI's first-party oracle is faster and more reliable because C3 IS the settlement monitor — it does not need to query an external data source. Decentralisation adds trust assumptions (oracle node operators) that do not exist in the centralised model.

**Patent protection:** The decentralised oracle architecture is claimed as an alternative embodiment. The claim covers the aggregation of settlement attestations from multiple independent monitoring nodes using threshold signatures.

### 9.3 On-Chain Cross-Border Security Interest Perfection

**Concept:** Record the SV's security interest in bridge loan receivables on-chain, creating a DLT-native equivalent of a UCC-1 filing (US) or registration under the Personal Property Securities Act (Canada/Australia).

**Why deferred:** No jurisdiction currently recognises an on-chain record as legally perfecting a security interest. Luxembourg's DLT laws cover dematerialised securities and payment instruments, not security interest perfection. UNCITRAL's 2023 Model Law on Electronic Transferable Records is a step toward recognition, but adoption is jurisdiction-by-jurisdiction and incomplete.

### 9.4 CBDC-Rail Token Redemption

**Concept:** Investors redeem P7 tokens directly for CBDC (digital euro, mBridge cross-border CBDC). The waterfall distributes in CBDC instead of fiat, eliminating the SV's dependence on commercial bank payment rails.

**Why deferred:** CBDC standards are too fragmented. The ECB digital euro pilot is ongoing (2024-2026) but not in production. The BIS mBridge project (cross-border wholesale CBDC) involves only 5 central banks. There is no standard CBDC payment API that P7 could target. The ECB's "waterfall functionality" concept (automatic transfer between digital euro and commercial bank money) suggests future compatibility, but the API specification does not exist yet.

### 9.5 Fully Open Institutional Order Book

**Concept:** A public, permissioned order book where institutional investors can post bids and offers for P7 tokens with real-time execution.

**Why deferred:** AML/KYC scalability constraints. Every participant in the order book must have verified ONCHAINID credentials. The ERC-3643 Identity Registry scales to hundreds of investors; scaling to thousands requires a redesign of the identity verification pipeline (batch processing, delegated verification, etc.). Additionally, the EU DLT Pilot Regime (Regulation (EU) 2022/858) caps total issuance on DLT trading venues at EUR 6 billion — a constraint that would limit P7's growth if it operated its own order book.

---

## 11. Part 10 — Risk Register

### Risk 1: Luxembourg SV Incorporation Delays

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | High |
| **Description** | Luxembourg notarial and RCS registration process can take 4-8 weeks. Regulatory uncertainty around DLT-native SV issuance may require additional CSSF clarifications. |
| **Mitigation** | Engage specialist Luxembourg securitisation counsel (Loyens & Loeff, DLA Piper) who have incorporated DLT-issuing SVs before. Use standard articles of association template with DLT addendum. Begin incorporation at W2 to provide 8-week buffer before Shadow Run (W19). |
| **Contingency** | If incorporation exceeds W8, run Shadow Run using a shelf company with compartment deed amendment. Not ideal but maintains timeline. |

### Risk 2: ELO Bank Refuses Sub-Participation

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | Critical |
| **Description** | The bank partner may refuse to enter a sub-participation agreement because: (a) legal/compliance unfamiliarity with SV structures, (b) credit committee reluctance to expose loan book to tokenisation, (c) regulatory capital concerns (sub-participation does not achieve off-balance-sheet treatment). |
| **Mitigation** | Pre-socialise the SV concept during P2/P3 bank partner negotiations. Include SV participation as a clause in the BPI License Agreement (future option, not immediate obligation). Prepare the Basel capital treatment memo (W2-W5) before the bank conversation. Offer the bank a revenue share on SV origination volume. |
| **Contingency** | If primary bank refuses, approach bank's treasury desk as an investor (Tier 2 target) — they may be willing to invest in Class A even if the lending division won't originate. Alternatively, use BPI's own balance sheet for initial pool seeding (requires BPI capitalisation). |

### Risk 3: ERC-3643 Platform KYC Onboarding Slow

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | Medium |
| **Description** | Tokeny / InvestaX / Fireblocks investor onboarding (ONCHAINID credential issuance) requires identity verification against EU AML5D and Luxembourg AML law. Institutional investors may have complex beneficial ownership structures that delay verification. |
| **Mitigation** | Begin investor KYC at W8 (8 weeks before first subscription target). Use the SV administrator's existing KYC infrastructure (CACEIS, Alter Domus all have institutional investor onboarding workflows). ONCHAINID issuance is the final step after traditional KYC is complete. |
| **Contingency** | If ONCHAINID issuance delays beyond W20, launch pilot with off-chain subscription + manual token minting (ERC-3643 allows issuer-initiated minting without buyer ONCHAINID, but transfer restrictions are then enforced at the issuer level, not the smart contract level). |

### Risk 4: Oracle Private Key Compromise

| Attribute | Detail |
|-----------|--------|
| **Probability** | Low |
| **Impact** | Critical |
| **Description** | If the ECDSA private key used by the Oracle Signing Service is compromised, an attacker could forge settlement attestations, triggering false waterfall distributions. |
| **Mitigation** | HSM-backed key storage (AWS CloudHSM or Thales Luna). Key never exported from HSM. Signing requests authenticated via mTLS from C3 instances only. Multi-sig requirement for settlements >EUR 1M. On-chain circuit breaker: if more than 10 settlements confirmed in 1 hour from a single oracle instance, freeze all attestations pending manual review. |
| **Contingency** | Key rotation procedure: deploy new oracle key to smart contract via multi-sig governance transaction. Revoke compromised key. Audit all attestations signed by compromised key. If false attestations detected, invoke `forceTransfer()` to recover misdirected funds. |

### Risk 5: Coverage Test Breach

| Attribute | Detail |
|-----------|--------|
| **Probability** | Low |
| **Impact** | High |
| **Description** | Trailing 30-day loss rate exceeds 1.5% or overcollateralisation ratio falls below 120%. This triggers Priority 4 (block B+E distributions), which damages investor confidence and BPI's residual returns. |
| **Mitigation** | 5% Class E first-loss buffer absorbs losses before coverage tests are threatened. Pool construction rules: diversification across corridors (max 40% concentration), rejection class limits (max 30% CLASS_C), ML model threshold (only loans with PD < 0.15 eligible for pool). `PortfolioRiskEngine.compute_var()` in `lip/risk/portfolio_risk.py` provides real-time VaR monitoring; coverage test breach triggers immediate pool construction adjustment. |
| **Contingency** | If coverage test breached: Class B and E distributions blocked automatically (smart contract enforced). BPI injects additional Class E capital to restore OC ratio. If breach persists >15 days, offer Class A early redemption at par. |

### Risk 6: Circular Investor/Counterparty Exposure

| Attribute | Detail |
|-----------|--------|
| **Probability** | Low |
| **Impact** | Medium |
| **Description** | An entity that is both a bridge loan counterparty (their payment failed, BPI bridged them) and an SV investor (they hold Class A or B notes). If their payment permanently fails, they suffer both the bridge loan default AND the NAV decline in their SV investment. |
| **Mitigation** | C6 circular exposure rule (Section 6.4) flags the overlap. SV administrator reviews and decides whether to: (a) exclude the counterparty's loans from the compartment where they invest, (b) limit their investment to a different compartment, or (c) accept the circular exposure with a documented risk acknowledgment. |
| **Contingency** | If circular exposure causes a correlated loss event, the compartment ring-fencing ensures the impact is contained. Other compartments' investors are unaffected. |

### Risk 7: GDPR Violation in UETR Cross-Border Data Transfer

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | High |
| **Description** | UETR data flows from bank (EEA) to BPI (Canada) to SV (Luxembourg) to on-chain (global). GDPR Chapter V restricts transfers to third countries without adequate protection. The on-chain attestation contains hashed UETR and settlement amount — potentially personal data under GDPR if the UETR can be linked to a natural person. |
| **Mitigation** | GDPR Data Processing Agreement (DPA) addendum (W2-W4) covering all data flows. On-chain attestation uses hashed UETR (SHA-256 of UETR + salt) — not plaintext UETR. Canada has an EU adequacy decision (2001, renewed 2023). Luxembourg is EEA. On-chain data: hashed identifiers only; no natural person data on-chain. `hash_identifier()` in `lip/common/encryption.py` provides the hashing function with per-deployment salt. |
| **Contingency** | If GDPR regulators challenge on-chain data: redesign attestation to use a mapping table (hashed pool-level reference on-chain; UETR-level detail off-chain, accessible only to SV administrator under DPA). |

### Risk 8: Regulatory Reclassification as Deposit-Taking

| Attribute | Detail |
|-----------|--------|
| **Probability** | Low |
| **Impact** | Critical |
| **Description** | If a regulator (CSSF, ECB, OSFI) determines that P7 tokens constitute "deposits" rather than "transferable debt securities," the SV would require a banking licence — effectively killing the product. |
| **Mitigation** | P7 tokens are structured as transferable debt securities (notes) issued by a Luxembourg SV under the Securitisation Law. They have: (a) a fixed maturity (aligned to underlying pool), (b) a stated coupon (SOFR/EURIBOR + spread), (c) subordination structure (seniority determines loss absorption), (d) no demand repayment right (redemption subject to coverage tests and liquidity windows). These characteristics definitively distinguish them from deposits (which are demand-repayable, unsecured, and carry deposit insurance). |
| **Contingency** | If reclassification risk materialises: obtain Luxembourg CSSF no-action letter before launch (W4-W8 legal track). Include external regulatory counsel opinion in offering memorandum. |

### Risk 9: Smart Contract Bug in Waterfall Logic

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | High |
| **Description** | A bug in `BPIWaterfall.sol` could misdirect distributions — paying Class B before Class A is fully satisfied, or distributing more than the available cash. Smart contract bugs in DeFi have caused billions in losses (Wormhole: $325M, Ronin: $625M). |
| **Mitigation** | Two independent security audits (Certik + Trail of Bits or OpenZeppelin). Formal verification of the waterfall contract using Certora Prover — mathematically proving that Priority N+1 never receives funds before Priority N is satisfied. Mainnet deployment with EUR 1M cap for first 4 weeks (circuit breaker). Upgrade path: use ERC-3643 v4 upgradeable proxy pattern for bug fixes without redeployment. |
| **Contingency** | If bug discovered post-deployment: invoke smart contract pause (multi-sig governance). Redeploy corrected contract. Use `forceTransfer()` to recover misdirected funds. Investor notification within 24 hours per offering memorandum terms. |

### Risk 10: Transfer Pricing Challenge by Tax Authority

| Attribute | Detail |
|-----------|--------|
| **Probability** | Medium |
| **Impact** | Medium |
| **Description** | Luxembourg tax authority (ACD) or Canada Revenue Agency (CRA) challenges the arm's-length nature of management fees, performance fees, or technology licensing fees between BPI Inc. and BPI Receivables S.A. |
| **Mitigation** | Contemporaneous transfer pricing documentation (W4-W8 legal track). Arm's-length benchmarking using Preqin (fund manager fees), BvD/TP Catalyst (technology licensing), and public CLO/CDO manager fee data. File bilateral Canada-Luxembourg APA within 6 months of SV incorporation. Maintain BEPS Master File and Luxembourg Local File per CbCR requirements. |
| **Contingency** | If challenged: defend with benchmark study. Worst case: fee adjustment with retrospective tax liability (interest + penalties). APA eliminates future risk once approved (typically 12-18 months for bilateral APAs). |

---

## Appendix A — Glossary

| Term | Definition |
|------|-----------|
| **AUM** | Assets Under Management — the total value of receivables in the SV pool |
| **Class A / B / E** | Token tranches with decreasing seniority and increasing yield/risk |
| **Compartment** | Statutory ring-fenced sub-pool within the Luxembourg SV |
| **Coverage test** | Automated test (OC ratio, loss rate, concentration, duration) that gates distributions |
| **ERC-3643** | Ethereum token standard for permissioned, compliance-enforced securities (T-REX protocol) |
| **ELO** | Execution Lending Organisation — the bank-side agent that originates bridge loans |
| **HSM** | Hardware Security Module — tamper-resistant device for cryptographic key storage |
| **LGD** | Loss Given Default — fraction of exposure lost if counterparty defaults |
| **MiCA** | Markets in Crypto-Assets Regulation (EU) |
| **NAV** | Net Asset Value — pool value minus liabilities, divided by token supply |
| **ONCHAINID** | On-chain identity credential used by ERC-3643 for KYC/AML verification |
| **Oracle** | System that bridges off-chain data (settlement events) to on-chain smart contracts |
| **PD** | Probability of Default — ML-predicted likelihood of bridge loan non-repayment |
| **SOFR** | Secured Overnight Financing Rate — USD benchmark rate |
| **EURIBOR** | Euro Interbank Offered Rate — EUR benchmark rate |
| **SV** | Securitisation Vehicle — the Luxembourg legal entity issuing tokenised notes |
| **UETR** | Unique End-to-end Transaction Reference — SWIFT payment identifier (UUID format) |
| **Waterfall** | Priority-ordered distribution of cash flows to token holders |

---

## Appendix B — Codebase Cross-Reference

| P7 Concept | Codebase Location | Function/Class |
|------------|-------------------|---------------|
| Settlement monitoring | `lip/c3_repayment_engine/repayment_loop.py` | `SettlementMonitor`, `RepaymentLoop`, `ActiveLoan` |
| Execution orchestration | `lip/c7_execution_agent/agent.py` | `ExecutionAgent`, `_build_loan_offer()` |
| License token / context | `lip/c8_license_manager/license_token.py` | `LicenseToken`, `LicenseeContext`, `sign_token()`, `verify_token()` |
| AML velocity aggregation | `lip/c6_aml_velocity/cross_licensee.py` | `CrossLicenseeAggregator`, `cross_licensee_hash()` |
| Cryptographic primitives | `lip/common/encryption.py` | `sign_hmac_sha256()`, `encrypt_aes_gcm()`, `hash_identifier()` |
| Portfolio risk / VaR | `lip/risk/portfolio_risk.py` | `PortfolioRiskEngine`, `compute_var()`, `compute_concentration()` |
| Regulatory reporting | `lip/common/regulatory_reporter.py` | `DORAAuditEvent`, `SR117ModelValidationReport`, `RegulatoryReporter` |
| Fee computation | `lip/c2_pd_model/fee.py` | `compute_loan_fee()`, `compute_platform_royalty()` |
| Deployment phase config | `lip/common/deployment_phase.py` | `DeploymentPhase`, `get_phase_config()` |

---

## Appendix C — Regulatory Reference Table

| Regulation | Jurisdiction | Relevance to P7 | Status |
|------------|-------------|-----------------|--------|
| Luxembourg Securitisation Law (2004, amended 2022) | Luxembourg | SV legal basis, compartment ring-fencing, active management | In force |
| Luxembourg Blockchain Laws I-IV (2019-2024) | Luxembourg | DLT-native dematerialised securities recognition | In force (Law IV pending) |
| EU Prospectus Regulation (2017/1129) | EU | Private placement exemption for qualified investors / EUR 100K minimum | In force |
| MiCA (2023/1114) | EU | Excludes tokenised securities regulated under existing financial law | In force (transitional to July 2026) |
| EU DLT Pilot Regime (2022/858) | EU | Framework for DLT-based trading venues | In force |
| Basel Cryptoasset Framework (July 2024) | International (Basel) | Group 1a classification for tokenised traditional assets | Implementation date: 1 January 2026 |
| GDPR (2016/679) | EU | Data protection for UETR and settlement data flows | In force |
| Canada-Luxembourg Tax Treaty | Canada / Luxembourg | Treaty protection for management fees, licensing royalties | In force |
| CRR / CRD (EU) | EU | Bank capital treatment for SV investment (securitisation framework) | In force |
| DORA (2022/2554) | EU | ICT operational resilience for financial entities | In force (17 January 2025) |

---

*End of P7 v0 Implementation Blueprint*
*Bridgepoint Intelligence Inc. — Confidential*
*Version 2.0 — March 2026*
