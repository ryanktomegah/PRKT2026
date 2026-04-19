# Prior-Art Citation Audit

**Date:** 2026-04-18
**Sprint:** Pre-Lawyer Review — Week 1 IP Timing
**Day:** 5 of 5
**Branch:** `codex/pre-lawyer-review`
**Prepared by:** Engineering review (automated audit)
**Purpose:** Satisfy 37 CFR 1.56 duty-of-candour preparation. Surface to patent counsel: (a) every citation currently in the publishable corpus, (b) verification status of each, (c) adjacent prior art that counsel should consider adding before filing.

---

## 1. Source Corpus

The following six files constitute the publishable patent corpus audited here. "Publishable" = documents destined for patent counsel and ultimately for filing. No other files are in scope for the citation grep, though README-level context is referenced where it bears on citation provenance.

| File | Path |
|---|---|
| Provisional-Specification-v5.1.md | `docs/legal/patent/Provisional-Specification-v5.1.md` |
| Provisional-Specification-v5.2.md | `docs/legal/patent/Provisional-Specification-v5.2.md` |
| Patent-Family-Architecture-v2.1.md | `docs/legal/patent/Patent-Family-Architecture-v2.1.md` |
| Future-Technology-Disclosure-v2.1.md | `docs/legal/patent/Future-Technology-Disclosure-v2.1.md` |
| patent_claims_consolidated.md | `docs/legal/patent/patent_claims_consolidated.md` |
| patent_counsel_briefing.md | `docs/legal/patent/patent_counsel_briefing.md` |

---

## 2. Methodology

### 2.1 Grep patterns applied

The following patterns were applied to all six files using ripgrep with line-number output:

- `US[0-9]{7}[BA][0-9]` — US patent numbers
- `EP[0-9]{7}` — EP patent numbers
- `ISO 20022` — ISO standard references
- `Merton` — Merton structural PD model
- `KMV` — KMV/Moody's structural model
- `Damodaran` — Damodaran industry-beta dataset
- `Altman` — Altman Z' score model
- `Bottomline` — assignee name for US11532040B2 (confirmed: appears in docs with patent number)

Additional passes were run for: `Alice Corp`, `Festo`, `Enfish`, `McRO`, `CLS Bank`, `SWIFT gpi`, `correspondent bank`.

Results from the `Bottomline` assignee-name grep are listed in the Location columns of §3.1 and are explicitly distinguished from patent-number grep hits (e.g., `PFA-v2.1.md:83,87 (assignee-name reference only — no patent number)`) to preserve the audit trail. Case-law grep hits (Alice, Festo, Enfish, McRO) are segregated into §3.4.

### 2.2 Verification approach and limits

**US patent numbers:** This session does not have network access to USPTO.gov or Google Patents. For each patent number, the audit records: (a) the exact claim made in the specification about that patent (assignee, grant year, subject matter), and (b) whether that claim can be cross-checked against any in-corpus evidence. Patent-number existence and the accuracy of the bibliographic description are marked **Partial** — independent USPTO verification is not possible in this session.

**ISO 20022 message types:** Verified against spec text — the specific message codes (pacs.002, pacs.008, camt.056, camt.055, pacs.004, camt.029) are explicitly named and described. ISO 20022 is a published international standard; specific message-type names are verifiable against the ISO 20022 Universal Financial Industry Message Scheme. Version/release number of the standard is not cited in any publishable doc.

**Academic references (Merton, KMV, Altman, Damodaran):** Zero formal bibliographic citations found in any of the six publishable docs. The README (`README.md:42`) states: `C2 — PD Model | Tiered PD/LGD + fee pricing | Merton/KMV, Damodaran, Altman Z'` and (`README.md:204`) explicitly names Damodaran industry-beta and Altman Z' as the thin-file model gap over US7089207B1. The README is not part of the six-file publishable corpus in §1 and is referenced here and in Finding F-1 solely as evidence of the inventors' awareness of these sources, not as a publishable document. These academic references are absent from the publishable corpus; see Finding F-1 below.

**Case law citations:** Alice Corp., Festo, Enfish, McRO appear in the specifications as legal argument support. These are not prior art in the patent sense (not 35 USC § 102/103 references) but are noted for completeness.

---

## 3. Cited Prior-Art Inventory

### 3.1 US and EP Patents

| # | Citation | Location (file : line) | Quoted context (exact) | Claim relevance | Verification status | Verification notes |
|---|---|---|---|---|---|---|
| P-1 | **US11532040B2** (Bottomline Technologies SARL) | v5.1.md:38–50; v5.2.md:47–59; PFA-v2.1.md:81 (patent number); PFA-v2.1.md:83,87 (assignee-name reference only — no patent number); multiple claim amendment notes | `"US11532040B2, assigned to Bottomline Technologies SARL and granted in 2022, discloses a system and method for international cash management using machine learning."` (v5.1.md:40) | Primary §103 prior-art reference for triggering mechanism. Extensively distinguished. | **Partial** | The spec asserts: assignee = Bottomline Technologies SARL, grant year = 2022, subject matter = ML-based cash management/cash flow forecasting. Patent-number existence and accuracy of these assertions cannot be independently confirmed via USPTO in this session. Counsel must validate via USPTO before filing. |
| P-2 | **US7089207B1** (JPMorgan Chase Bank N.A.) | v5.1.md:52–64; v5.2.md:61–73 | `"US7089207B1, assigned to JPMorgan Chase Bank N.A. and granted in 2006, discloses a method and system for determining a company's probability of no default using observable market factors — specifically current equity share price, equity price volatility, and total debt levels — as inputs to a structural credit risk model."` (v5.1.md:54) | Primary §103 prior-art reference for PD pricing methodology. Extensively distinguished on: (1) private company limitation; (2) no payment-network integration. | **Partial** | The spec asserts: assignee = JPMorgan Chase Bank N.A., grant year = 2006, subject matter = structural PD model from observable equity data. Patent-number existence and accuracy of these assertions cannot be independently confirmed via USPTO in this session. Counsel must validate via USPTO before filing. Note: README.md:204 references this same patent as the gap the invention fills. Internal consistency is good. US7089207B1 is not cited by number in PFA-v2.1.md — the v5.1/v5.2 provisional specs are the only publishable docs that cite this patent by number. |

No EP patent numbers were found in any of the six publishable docs.

### 3.2 ISO 20022 Standard References

| # | Citation | Location (file : line) | Quoted context (exact) | Claim relevance | Verification status | Verification notes |
|---|---|---|---|---|---|---|
| S-1 | **ISO 20022 — pacs.002** (Payment Status Report) | v5.1.md:199; v5.2.md:203; patent_claims_consolidated.md:13,17–22; patent_counsel_briefing.md:12,17 | `"D1 | Claim 1 | Parsing specifically ISO 20022 pacs.002 XML status reason codes as the payment failure signal"` (v5.1.md:199) | Dependent Claim D1 and the core failure-detection trigger. The failure-taxonomy claim family (patent_claims_consolidated.md) is organised around pacs.002 rejection reason codes. Central to §101 interoperability argument. | **Y (standard name)** | pacs.002 is a real, published ISO 20022 message type (FI to FI Payment Status Report). The name and purpose match the spec's description. No specific version/release year of ISO 20022 is cited — counsel should consider adding release year. |
| S-2 | **ISO 20022 — pacs.008** (Credit Transfer) | v5.1.md:206; v5.2.md:210 | `"D8 | Claim 1 | Repayment collected automatically via ISO 20022 pacs.008 debit instruction upon pacs.002 settlement confirmation"` (v5.1.md:206) | Dependent Claim D8 — closed-loop auto-repayment. | **Y (standard name)** | pacs.008 is the FI to FI Customer Credit Transfer message in ISO 20022. Name and described purpose are consistent with the standard. |
| S-3 | **ISO 20022 — camt.056** (Payment Cancellation Request) | v5.1.md:211; v5.2.md:215; FTD-v2.1.md:349,355; patent_claims_consolidated.md:153 | `"D13 (new v5.0) | Claim 5 | Adversarial payment cancellation detection: monitoring ISO 20022 camt.056 cancellation requests"` (v5.1.md:211) | Dependent Claim D13 — adversarial cancellation detection. Also cited in FTD as the primary attack vector against auto-repayment collateral. | **Y (standard name)** | camt.056 is the FI to FI Payment Cancellation Request message in ISO 20022. Consistent with described use. |
| S-4 | **ISO 20022 — pacs.004** (Payment Return) | FTD-v2.1.md:355,373; patent_claims_consolidated.md (claim element aa) | `"If accepted, the receiving bank returns the funds to the sender via a pacs.004 Payment Return message."` (FTD-v2.1.md:355) | Security-interest preservation workflow in D13/Claim 5. | **Y (standard name)** | pacs.004 is the Payment Return message in ISO 20022. Consistent. |
| S-5 | **ISO 20022 — camt.029** (Resolution of Investigation) | FTD-v2.1.md:418; patent_claims_consolidated.md (claim element aa) | `"the receiving bank responds to the camt.056 with a camt.029 Resolution of Investigation message"` (FTD-v2.1.md:418) | Security-interest preservation workflow — the receiving bank's acceptance/rejection signal. | **Y (standard name)** | camt.029 is the Resolution of Investigation message in ISO 20022. Consistent. |
| S-6 | **ISO 20022 — camt.055** (Customer Credit Transfer Cancellation Request) | patent_claims_consolidated.md (claim element aa) | `"monitoring...a plurality of ISO 20022 cancellation and return message channels including camt.056...camt.055 Customer Credit Transfer Cancellation Request"` | Broadens D13 monitoring to customer-initiated cancellations, not just FI-to-FI. | **Y (standard name)** | camt.055 is the Customer Credit Transfer Cancellation Request in ISO 20022. Consistent. |
| S-7 | **ISO 20022 — general (standard name without message type)** | v5.1.md:103; v5.2.md:113; many other locations | `"including but not limited to ISO 20022 structured messaging networks"` (v5.1.md:103, Claim 1 step (a)) | Broadest claim scope — ISO 20022 networks cited as the primary but not exclusive monitoring surface. | **Y (standard name)** | ISO 20022 is the globally recognised financial messaging standard published by ISO. No version year cited anywhere in the corpus. Counsel should consider whether to add a publication year or version reference to the formal IDS. |

### 3.3 Academic / Methodological References

**Finding F-1 (significant gap — see Section 4):** The grep patterns `Merton`, `KMV`, `Damodaran`, and `Altman` return **zero hits** across all six publishable patent docs.

The README (`README.md:42`) explicitly names these as the academic sources underlying the PD model component:
> `C2 — PD Model | Tiered PD/LGD + fee pricing | Merton/KMV, Damodaran, Altman Z'`

And (`README.md:204`):
> `LIP's core patent claim covers...the novel extension to Tier 2/3 private counterparties using Damodaran industry-beta and Altman Z' thin-file models (gap in JPMorgan US7089207B1).`

The publishable specs describe the PD methodology substantively — structural models using equity price and volatility, proxy structural models using sector-median asset volatility, and reduced-form ratio scoring — but do not formally name Merton (1974), KMV, Damodaran, or Altman (1968) as their sources anywhere.

This is recorded as a gap below.

### 3.4 Case Law Citations (non-prior-art; informational)

These are legal argument anchors, not § 102/103 prior art. Listed for completeness; no IDS disclosure required.

| Citation | Location | Notes |
|---|---|---|
| *Alice Corp. v. CLS Bank Int'l*, 573 U.S. 208 (2014) | v5.1.md:219; v5.2.md:223 | §101 framework. Standard citation; verify cite form with counsel. |
| *Enfish, LLC v. Microsoft Corp.*, 822 F.3d 1327 (Fed. Cir. 2016) | v5.1.md:221; v5.2.md:225 | §101 Step 2A affirmative precedent. |
| *McRO, Inc. v. Bandai Namco Games Am. Inc.*, 837 F.3d 1299 (Fed. Cir. 2016) | v5.1.md:221; v5.2.md:225 | §101 Step 2A affirmative precedent. |
| *Festo Corp. v. Shoketsu Kinzoku Kogyo Kabushiki Co.* (Fed. Cir. 2002 en banc) | v5.1.md:86,119; v5.2.md:95 | Prosecution history estoppel rationale for v5.0 Amendment A. |
| *Recentive Analytics v. Fox* | v5.2.md:25,35,101,239 | **Removed from v5.2.** v5.1 cited it; v5.2 explicitly removes it as adverse authority. Do not re-introduce. |

---

## 4. Gap Analysis — Adjacent Prior Art Not Currently Cited

The following four areas were identified in the task plan as known-adjacent prior art that may be material under 37 CFR 1.56.

### 4.1 FX Settlement Risk Systems — CLS Bank

**Status: NOT CITED in any publishable doc.**

CLS Bank International operates the world's largest multi-currency settlement system (settling approximately USD 6.5 trillion daily across 18 currencies). CLS uses a payment-versus-payment (PvP) mechanism and netting to eliminate FX settlement risk — the risk that one leg of a currency exchange settles while the other fails.

**Why potentially material:** The present invention addresses liquidity gaps caused by cross-border payment failures. CLS Bank's architecture (real-time bilateral netting, settlement failure detection, automated funding gap coverage) is directly adjacent to the claims. An examiner familiar with financial infrastructure could plausibly argue that CLS Bank's settlement-failure-handling mechanisms teach elements of the real-time monitoring and liquidity-response architecture.

**Counsel action:** Counsel should evaluate whether any CLS Bank patents (CLS Bank Holdings, Inc. has US patent filings) or published technical specifications (CLS white papers, BIS CPMI reports on PvP settlement) are material references. If material, add to IDS. If not material, document the reasoning.

### 4.2 Real-Time Payment Failure Detection — SWIFT gpi

**Status: CITED as technology reference; NOT cited as prior art.**

SWIFT gpi is extensively referenced throughout the publishable corpus as an integration point: SWIFT gpi UETR tracking is cited in Claim D3, in Claim 5's settlement monitoring steps, in D13, and repeatedly in §101 arguments. However, SWIFT gpi is cited only as a technology the invention integrates with — not as prior art to be distinguished.

SWIFT gpi was launched in 2017 and introduced the UETR (Unique End-to-End Transaction Reference) as a standard payment tracking identifier. SWIFT has published technical documentation (gpi Observer Analytics, gpi Tracker API specifications) and may hold patents or filed applications related to real-time cross-border payment tracking.

**Why potentially material:** If SWIFT holds patents or published applications on real-time cross-border payment tracking using UETR keys — which is precisely the settlement-monitoring mechanism in Claims 5(u) and D3 — those references may be material. The current specs cite SWIFT gpi as infrastructure but do not analyse it as prior art.

**Counsel action:** Assignee search on SWIFT S.C. and Society for Worldwide Interbank Financial Telecommunication in USPTO. If any SWIFT-held patent covers UETR-based payment tracking or real-time cross-border payment status monitoring, counsel must evaluate for IDS disclosure.

### 4.3 ISO 20022 pacs.002 Handling Standards

**Status: ISO 20022 pacs.002 IS cited as the primary input message; the ISO 20022 standard itself is NOT cited as prior art.**

The claims use ISO 20022 pacs.002 rejection reason codes as the primary trigger input. The ISO 20022 standard (including the pacs.002 message specification and its reason code vocabulary) is prior art in the sense that it is a published international standard predating the invention. However, the publishable docs cite it as integrated technology, not as a prior-art reference to be formally listed on an IDS.

Additionally, the specific enumeration of pacs.002 reason codes and their classification into the invention's three-class taxonomy (permanent failure / systemic delay / hold-type) is identified in the patent_counsel_briefing.md as a key trade-secret element held outside the claims. This raises a disclosure question: if the claim taxonomy is based on a specific set of ISO 20022 codes, and those codes are defined by a published standard, the standard itself may be material to understanding and evaluating claim scope.

**Counsel action:** Consider whether the ISO 20022 pacs.002 message specification (version year to be determined — currently absent from all publishable docs) should be formally listed on the IDS as a non-patent literature reference. Specifically: ISO 20022 Universal financial industry message scheme, pacs.002.001.XX. Confirm version year with technical team.

### 4.4 Correspondent Banking Credit Limit Tools

**Status: NOT CITED in any publishable doc.**

The correspondent banking credit-limit infrastructure (Nostro account monitoring, intraday credit facilities, correspondent bank risk exposure limits) is directly relevant to the commercial context of the invention. Tools such as SWIFT's Correspondents Monitor, Finastra's Fusion Equation, and various bank-internal correspondent banking risk systems perform real-time monitoring of correspondent bank exposure and payment flows.

The Patent-Family-Architecture-v2.1.md (`line 218`) explicitly names Finastra, FIS Global, Temenos, and Bottomline Technologies as assignees requiring search coverage — but this is framed as a competitive/prior-art search task to be commissioned, not as a completed search. No specific Finastra, FIS, or Temenos patents are currently cited in the corpus.

**Why potentially material:** If a Finastra, FIS Global, or Temenos patent covers real-time payment monitoring with automated credit response in a correspondent banking context, it may be a § 102/103 reference against Claims 1 and 2.

**Counsel action:** The commissioned professional prior-art search noted in PFA-v2.1.md (line 218) should specifically include assignee searches on Finastra (and predecessor Misys), FIS Global, Temenos, and Diebold Nixdorf for correspondent banking and payment monitoring claims. Results must feed the IDS. This search has not been completed as of this audit.

---

## 5. Counsel-Action Summary

1. **USPTO validation of both cited patent numbers before filing.** US11532040B2 (Bottomline) and US7089207B1 (JPMorgan) are the only two patents cited in the corpus. Both are marked Partial — their existence, assignee accuracy, grant year, and subject-matter description have not been independently confirmed via USPTO in this audit. Counsel should pull both patents from USPTO and confirm the specification's description of each is accurate before the IDS is filed. If either description is materially inaccurate, the specification must be corrected.

2. **Add formal bibliographic citations for Merton, Altman, and Damodaran.** The README confirms these three academic sources underpin the PD model. None appear in any publishable doc. The specification describes the methodology they introduce (structural model, sector-median asset volatility proxy, ratio scoring) without crediting the source. Under 37 CFR 1.56, if the inventors were aware of these publications and they are material to patentability (which they may be, given the PD model is part of the claimed system), they should be disclosed. Counsel must evaluate. The specific references are: (a) Merton, R.C. "On the Pricing of Corporate Debt: The Risk Structure of Interest Rates." Journal of Finance 29(2), 1974; (b) Altman, E.I. "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy." Journal of Finance 23(4), 1968; (c) KMV LLC / Moody's Analytics — KMV Credit Monitor (commercial model, not a single paper — confirm with technical team which KMV publication is the operative reference); (d) Damodaran, A. — industry beta datasets published on pages.stern.nyu.edu (confirm which dataset version was used by the technical team).

3. **Cite ISO 20022 standard with version year on IDS.** The specs cite the standard by name and message type but not by version. ISO 20022 standards are published with version suffixes (e.g., pacs.002.001.10). Counsel should determine whether to list the ISO 20022 standard as non-patent literature on the IDS and, if so, confirm which version was operative during invention conception.

4. **Commission the prior-art assignee search noted in PFA-v2.1.md.** The architecture doc flags this as advisory but required before utility filing. Until that search is complete, the IDS cannot be considered comprehensive. Specifically: SWIFT S.C., Finastra (Misys), FIS Global, Temenos, Citibank technology filings, and Deutsche Bank technology filings — all in CPC codes G06Q20, G06Q40, G06N20.

5. **Evaluate CLS Bank settlement-risk patents for materiality.** CLS Bank's PvP settlement architecture and failure-handling mechanisms are directly adjacent to the invention's real-time liquidity response. No CLS Bank patents have been reviewed. Counsel should run an assignee search on CLS Bank Holdings, Inc. and CLS Services Ltd.

6. **SWIFT gpi patent review.** SWIFT gpi is cited as an integration target throughout the claims. If SWIFT holds patents on UETR-based real-time cross-border payment tracking, those may be material to Claims 5 and D3. An assignee search on Society for Worldwide Interbank Financial Telecommunication and SWIFT S.C. is needed.

7. **Confirm Recentive removal is complete in all filing materials.** v5.2 removes the *Recentive Analytics v. Fox* citation. Confirm with counsel that v5.2 is the version going to filing and that no v5.1-only materials will be submitted. The *Recentive* citation must not appear in any filed document.

---

## 6. Open Questions for Counsel

1. **Patent number accuracy (STOP-condition adjacent):** The spec describes US7089207B1 as "granted in 2006" and US11532040B2 as "granted in 2022." Are these dates correct per USPTO? A wrong grant year is a factual error in the specification — not necessarily a §1.56 candour issue, but a credibility risk if flagged by an examiner.

2. **Merton/KMV/Altman/Damodaran disclosure obligation:** Do these academic sources meet the materiality threshold under 37 CFR 1.56, given that the invention's PD model component is described at a functional level without formally naming them? The README's explicit reference to these sources suggests the inventors were aware of them. Counsel must determine whether they are material to the claims and if so add them to the IDS as non-patent literature.

3. **ISO 20022 as non-patent literature:** Should the ISO 20022 Universal Financial Industry Message Scheme (or the specific pacs.002 message specification) be formally listed? It is a published international standard, but the claims build on it rather than being anticipated by it. Is listing it protective or does it create prosecution history that narrows claim scope?

4. **KMV identity:** The README cites "KMV" alongside Merton. KMV LLC was acquired by Moody's in 2002 and became Moody's Analytics Credit Monitor. The relevant prior art may be either the original KMV academic papers (Crosbie & Bohn) or Moody's Analytics patent filings. Counsel should advise which is the correct reference form.

5. **Provisional vs. utility:** All publishable docs are provisional-specification documents. The duty of candour under 37 CFR 1.56 formally attaches to the utility application. However, if an IDS is submitted with the provisional, any omissions discovered later can still be problematic. Counsel should advise whether to file a formal IDS with the provisional or wait for the utility application, given the gap findings above.

---

*Audit completed 2026-04-18. Scope limited to six named publishable docs. Network verification of patent numbers was not possible in this session; all patent citations are marked Partial pending USPTO confirmation by counsel.*
