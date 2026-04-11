# Founder Protection & Corporate Governance Strategy — Bridgepoint Intelligence Inc.

**VERSION 1.0 | March 2026**

> **Internal planning document — for the founder and corporate counsel ONLY. NOT for distribution to investors, employees, or any external party.**

This document specifies the governance architecture for Bridgepoint Intelligence Inc. ("BPI"). Every protection described here must be embedded in the articles of incorporation, shareholders' agreement, or CEO employment agreement **before** external capital enters the company. The goal: make it structurally impossible for investors, board members, co-founders, or acquirers to remove the founder from the company they created, regardless of how much economic dilution occurs.

---

## Why This Document Exists

The [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) projects dilution from 85% at inception to ~27% at IPO. Without governance protections, 27% ownership means the founder can be outvoted on everything — CEO removal, company sale, strategic direction, share issuance. Every protection in this document exists to decouple **economic ownership** (which dilutes naturally through fundraising) from **voting control** (which must not dilute).

The existing fundraising documents mention a "dual share class (common + blank-cheque preferred)" in the [F&F round budget](../fundraising/ff-round-structure.md) (line item #3: CBCA incorporation). This document converts that one-line mention into a complete governance architecture.

---

## Table of Contents

1. [Dual-Class Share Structure](#1-dual-class-share-structure)
2. [Board Composition Controls](#2-board-composition-controls)
3. [Founder Consent Rights (Veto Powers)](#3-founder-consent-rights-veto-powers)
4. [CEO Employment Agreement](#4-ceo-employment-agreement)
5. [Anti-Dilution & Preemptive Rights](#5-anti-dilution--preemptive-rights)
6. [Change of Control Protections](#6-change-of-control-protections)
7. [Sunset Provisions](#7-sunset-provisions--when-to-hold-when-to-concede)
8. [CBCA Legal Framework](#8-cbca-legal-framework)
9. [Implementation Timeline](#9-implementation-timeline)
10. [Traps to Watch For](#10-traps-to-watch-for)

---

## 1. Dual-Class Share Structure

### 1.1 Share Classes

| Class | Voting | Economic | Holders | Conversion |
|-------|--------|----------|---------|------------|
| **Class A Common** | **10 votes per share** | Equal per-share with Class B | Founder only | One-way, irreversible → Class B |
| **Class B Common** | 1 vote per share | Equal per-share with Class A | ESOP, employees, converted investors | Cannot convert to Class A |
| **Class C Preferred** | 1 vote per share (on as-converted basis) | Liquidation preference + equal per-share | Investors (series C-1, C-2, etc.) | Mandatory → Class B at IPO |

**Why three classes, not two:** Class A/B is the dual-class voting structure. Class C is the "blank-cheque preferred" referenced in the [F&F round structure](../fundraising/ff-round-structure.md) and the [Section 85 Rollover Briefing](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md) — it accommodates investor-specific terms (liquidation preference, anti-dilution) without contaminating the common share economics or voting structure.

### 1.2 Shares at Founding

| Class | Authorized | Issued | Holder |
|-------|-----------|--------|--------|
| Class A Common | 10,000,000 | 8,500,000 | Founder (Ryan Tomegah) |
| Class B Common | 100,000,000 | 0 (1,500,000 reserved for ESOP, unissued until exercised) | Option pool |
| Class C Preferred | 100,000,000 (in series) | 0 | — |

**Share math:** 8,500,000 / 10,000,000 = 85% founder ownership at inception. 1,500,000 / 10,000,000 = 15% ESOP reserve. Both figures match the [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) ("Inception: 85% (15% ESOP reserved)").

**CBCA requirement:** No par value shares — s.24(1) of the Canada Business Corporations Act prohibits par value shares. This is mandatory. The articles will specify share class rights, not par values.

**S.85 interaction:** The [Section 85 Rollover Briefing v1.1](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md) raises a PUC (paid-up capital) question about dual share classes (Question 5 for the accountant): "Does the dual share class structure create any PUC complications under s. 85(2.1) that could affect future preferred share issuances?" The s.85(2.1) PUC reduction applies only to the shares issued as consideration for the IP transfer (Class A Common). It should not contaminate Class C Preferred PUC when preferred shares are later issued for cash. **Confirm with tax counsel before filing the T2057.**

### 1.3 Automatic Conversion Triggers on Class A

Class A shares automatically and irrevocably convert to Class B upon:

1. **Transfer to non-permitted transferee.** Any transfer of Class A shares to anyone other than:
   - The founder individually
   - A holding company 100% owned and controlled by the founder
   - A trust of which the founder is the sole trustee and primary beneficiary

   ...triggers automatic conversion to Class B.

2. **Death.** Class A shares pass to the founder's estate and remain Class A for **12 months** (the grace period). If not transferred to a permitted transferee within 12 months, they automatically convert to Class B.

3. **No sunset at IPO.** Class A shares do NOT automatically convert upon an initial public offering. This is a negotiation point with underwriters and stock exchanges — see [Section 7](#7-sunset-provisions--when-to-hold-when-to-concede).

### 1.4 Voting Control Math Through Dilution

This is the core of the strategy. Because Class A shares carry 10 votes each and all other shares carry 1 vote, the founder's voting power declines far more slowly than economic ownership.

| Stage | Founder Economic | Fully-Diluted Shares | Others' Shares (1 vote ea.) | Founder Votes (10 votes ea.) | **Founder Vote %** |
|-------|-----------------|---------------------|---------------------------|-----------------------------|--------------------|
| Founding | 85% | 10,000,000 | 1,500,000 (ESOP, unissued) | 85,000,000 | **100%** |
| F&F (SAFEs, no conversion) | 85% | 10,000,000 | 1,500,000 (unissued) | 85,000,000 | **100%** |
| Pre-Seed (~68%) | 68% | 12,500,000 | 4,000,000 | 85,000,000 | **95.5%** |
| Seed (~55%) | 55% | 15,454,545 | 6,954,545 | 85,000,000 | **92.4%** |
| Series A (~45%) | 45% | 18,888,889 | 10,388,889 | 85,000,000 | **89.1%** |
| Series B (~37%) | 37% | 22,972,973 | 14,472,973 | 85,000,000 | **85.5%** |
| Growth/Pre-IPO (~32%) | 32% | 26,562,500 | 18,062,500 | 85,000,000 | **82.5%** |
| **IPO (~27%)** | **27%** | **31,481,481** | **22,981,481** | **85,000,000** | **78.7%** |

**How to read this table:** Economic ownership percentages come from the [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) dilution path (fully-diluted basis, including ESOP reserve in the denominator). At each stage, total fully-diluted shares = founder shares / founder %. Others' shares = total − founder shares. All non-founder shares carry 1 vote each (Class B Common or Class C Preferred on as-converted basis). F&F SAFEs do not convert until the Pre-Seed equity financing ($500K minimum qualifying financing per the [SAFE template](../fundraising/safe-agreement-template.md)), so the founder holds 100% of votes through the F&F stage. At founding, the ESOP reserve is authorized but unissued — no voting shares exist outside Class A.

**Conservative assumption:** This table counts ALL non-founder fully-diluted shares as voting, including ESOP shares that may not yet be exercised. In practice, unexercised options do not vote, so the founder's actual voting power at each stage is equal to or higher than shown.

### 1.5 The Breakpoint

The founder loses voting majority when total non-Class-A votes exceed 85,000,000. This requires 85,000,000 non-founder shares outstanding, meaning total shares = 85,000,000 + 8,500,000 = 93,500,000, and founder economic ownership = 8,500,000 / 93,500,000 = **~9.1%**.

**At the projected IPO (27% economic), the founder still holds ~78.7% of votes.** The headroom is enormous — the founder would need to be diluted from 27% to approximately 9% economic ownership before losing voting majority. That is an additional ~18 percentage points of dilution beyond IPO, requiring either catastrophic additional funding rounds or a major restructuring far beyond anything projected.

**Why 10:1 and not 5:1:** At a 5:1 ratio, the founder's voting power at IPO (27% economic) would be approximately 64.9% — still a majority, but with a thinner margin. More critically, the breakpoint at 5:1 occurs at ~16.1% economic ownership, which is significantly closer to a plausible dilution path. The 10:1 ratio pushes the breakpoint to ~9.1%, providing a much larger buffer against unexpected dilution events (down rounds, ESOP pool refreshes, bridge financing).

---

## 2. Board Composition Controls

### 2.1 Board Evolution by Stage

| Stage | Board Size | Founder-Appointed | Investor-Appointed | Independent (Mutual) | Chair |
|-------|-----------|-------------------|--------------------|----------------------|-------|
| Founding | 1 | 1 (Founder) | 0 | 0 | Founder |
| F&F | 1 | 1 | 0 | 0 | Founder |
| Pre-Seed | 3 | 2 | 0 | 1 | Founder |
| Seed | 3 | 2 | 0 | 1 | Founder |
| Series A | 5 | 2 | 1 | 2 | Founder |
| Series B | 5 | 2 | 2 | 1 | Founder |
| Growth/Pre-IPO | 7 | 2 | 2 | 3 | Founder |

### 2.2 What Goes in the Articles

**Maximum board size = 9.** This is specified in the articles of incorporation and prevents investors from unilaterally adding board seats to dilute founder-appointed directors. Changing the maximum requires a special resolution (2/3 of all shareholders per CBCA s.173), and because board size is tied to Class A rights, it also requires a separate Class A class vote (s.176(1)(b)).

### 2.3 What Goes in the Shareholders' Agreement

- **Chair = founder** (or the founder's nominee) for as long as the founder holds any Class A shares. The chair controls the agenda, calls meetings, and breaks ties.
- **Nomination rights:** The founder nominates the "founder-appointed" directors. Lead investors in each preferred series nominate "investor-appointed" directors. Independent directors are nominated by mutual agreement of the founder and the lead investor(s).
- **Board observer rights:** Non-board investors may attend meetings as observers only with board consent. The board may exclude observers from any session by majority vote (prevents information leakage to non-board investors on sensitive matters).

### 2.4 Belt and Suspenders

The 10:1 voting ratio already controls director elections — under CBCA s.106(3), directors are elected by ordinary resolution of voting shareholders. With ~78.7% of votes at IPO, the founder can elect or remove any director. But explicit nomination rights in the shareholders' agreement provide a second layer of protection that doesn't require calling a shareholder vote and operates even in scenarios where the founder temporarily holds fewer votes (e.g., during a SAFE conversion where timing creates a brief window).

---

## 3. Founder Consent Rights (Veto Powers)

### 3.1 Architecture: Class Rights, Not Personal Rights

These consent rights are attached to the **Class A share class** under CBCA s.24(3), NOT to a named individual or a board seat. This matters because:

- Class rights require a **separate special resolution of that class** to amend (CBCA s.176(1)(b)) — meaning the founder has an absolute veto over any attempt to weaken these protections, as long as the founder holds a majority of Class A shares.
- If the rights were personal (e.g., "Ryan Tomegah has a veto"), they would not survive a hypothetical future event where Class A shares pass to an estate or holdco. Class-level rights travel with the shares.

### 3.2 Actions Requiring Written Consent of Holders of Majority of Class A Shares

#### Existential

- Sale, merger, amalgamation, or change of control of BPI
- Sale of all or substantially all assets of BPI
- Voluntary liquidation or dissolution
- Initial public offering (including timing, exchange selection, underwriter selection)
- Change of control of BPI Capital I Ltd (the Phase 2/3 lending SPV)

#### Capital Structure

- Issuance of any new share class or series
- Issuance of any shares (except grants under an approved ESOP within the authorized pool)
- Amendment of any share class rights (voting, economic, conversion, or otherwise)
- Stock splits, consolidations, or reclassifications
- Declaration or payment of dividends or share repurchases
- Issuance of convertible debt (including SAFEs after the F&F round)
- Creation of or material amendment to any equity incentive plan

#### Governance

- Increase or decrease of board size beyond the range specified in the articles
- Removal of the CEO
- Amendment of the articles of incorporation
- Amendment of the shareholders' agreement
- Amendment of by-laws that affect Class A rights

#### Operational (Thresholds Negotiable Per Stage)

- Entry into a materially different line of business
- Single transactions or commitments exceeding $500,000 (adjust upward at each funding round)
- Assignment, licensing, encumbrance, or abandonment of the patent or any core IP (including the provisional patent application, the utility patent, and the trade secret portfolio described in the [Section 85 Rollover Briefing](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md))
- Related-party transactions (any transaction between BPI and the founder, founder's family, founder's holdco, or any entity in which the founder has an interest)

### 3.3 Why This Is Robust

These consent rights are embedded in the articles as **Class A class rights.** Amending them requires a 2/3 special resolution of Class A holders, voting as a separate class (CBCA s.176(1)(b)). Because the founder holds all Class A shares, this is the founder's **absolute veto** — it cannot be overridden by investor votes, board votes, or any combination of non-Class-A shareholders. Even at 27% economic ownership (IPO), this veto remains intact.

---

## 4. CEO Employment Agreement

This agreement is executed at or immediately after incorporation (Phase 2 of the implementation timeline). It protects the founder's operational role independently of share ownership.

| Provision | Terms |
|-----------|-------|
| **Term** | Indefinite (no fixed expiry). This prevents soft removal through non-renewal of a fixed-term contract. |
| **Termination for Cause** | Narrowly defined: (a) conviction of a criminal offence involving fraud; (b) willful and material breach of fiduciary duty (with 30-day cure period); (c) commission of material fraud against the Company. **Expressly excludes:** poor performance, strategic disagreements, missed targets, failure to meet board expectations. Requires **75% board supermajority** to invoke. |
| **Termination Without Cause** | 24 months base salary severance + prorated annual bonus + continuation of benefits for 24 months + **100% immediate acceleration of all unvested equity** |
| **"Good Reason" Resignation** | Triggers the full Without Cause severance package if any of the following occur: (a) material diminution of title, authority, or responsibilities; (b) reduction in base salary; (c) relocation of principal workplace by more than 50 km; (d) material breach of the employment agreement by the Company; (e) failure to nominate the founder for election to the board of directors |
| **Double-Trigger Acceleration** | Upon change of control + termination (actual or constructive) within 24 months of the change of control → 100% immediate acceleration of all unvested equity |
| **Board Seat Guarantee** | The Company will nominate the founder as a director at every annual or special meeting of shareholders for as long as the founder holds the CEO title |
| **D&O Insurance** | Minimum $5,000,000 coverage from incorporation (budgeted at $2,000–$5,000/yr in the [F&F Use of Proceeds](../fundraising/ff-round-structure.md)) |
| **Indemnification** | Broadest indemnification permitted under CBCA s.124 — advances for defence costs, indemnification for settlements and judgments in any proceeding arising from the founder's role as director or officer |

### 4.1 Why These Protections Matter

The employment agreement is the last line of defence. If an adversarial board somehow bypassed the dual-class voting structure (which should be impossible, but governance is about defence in depth), the employment agreement ensures that:

- **Removing the CEO is expensive.** 24 months severance + 100% equity acceleration makes a board think very carefully before terminating without cause.
- **Constructive dismissal is covered.** "Good Reason" prevents the board from stripping the CEO's authority without technically firing them.
- **Change of control is covered.** Double-trigger acceleration protects the founder in an acquisition scenario where a new owner wants to replace management.

---

## 5. Anti-Dilution & Preemptive Rights

### 5.1 Founder Preemptive Right

The founder has the right to participate pro rata in any new share issuance (except ESOP grants from the approved pool and conversions of existing preferred shares or SAFEs). This is most valuable at early stages when the founder has personal capital to invest alongside institutional investors.

**Note:** F&F investors do NOT receive pro-rata rights per the [F&F round structure](../fundraising/ff-round-structure.md) ("Pro-Rata Rights: None — Reserved for Pre-Seed and later institutional rounds"). Side letters for $25K+ F&F checks include a pre-seed pro-rata right only, not a general preemptive right.

### 5.2 Structural Protection

The 10:1 voting ratio IS the primary anti-dilution mechanism for **control.** Economic dilution is expected and natural — the [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) projects dilution from 85% to 27% across seven rounds. What dual-class prevents is **voting dilution** — the founder's economic stake shrinks, but their governance control does not.

### 5.3 Explicit Class A Protection

In the articles of incorporation: *"The voting rights attached to Class A Common Shares shall not be amended, varied, or otherwise modified without the affirmative vote of not less than two-thirds (2/3) of the holders of Class A Common Shares, voting as a separate class."*

This is already required by CBCA s.176(1)(b), but stating it explicitly in the articles removes any ambiguity and makes the protection visible to investors during due diligence.

### 5.4 Pay-to-Play

Investors who do not participate pro rata in subsequent financing rounds lose their anti-dilution protection, and their preferred shares (Class C) automatically convert to Class B Common. This prevents free-rider dilution — where an investor benefits from downside protection without contributing capital to support the company.

---

## 6. Change of Control Protections

### 6.1 Layered Approval Requirement

A sale, merger, or change of control requires **ALL** of the following:

1. **Board approval** — majority of the board of directors
2. **Founder written consent** — Class A class right per [Section 3](#3-founder-consent-rights-veto-powers) above
3. **Special resolution of shareholders** — 2/3 of all voting shareholders per CBCA s.183 (amalgamation) or s.189(3) (sale of substantially all assets)
4. **Investor consent** — Class C Preferred protective provision (negotiated at each funding round)

**No single party can force a sale. The founder has an absolute veto.**

The CBCA also provides **dissent rights** under s.190 — any shareholder who votes against an amalgamation or asset sale can demand fair value for their shares. This protects minority shareholders but also constrains the founder: a sale must be at fair value, not just majority-approved.

### 6.2 Drag-Along Negotiation

Drag-along rights force minority shareholders to sell alongside a majority. They are standard in institutional rounds. The founder's negotiating position:

| Parameter | Founder's Position |
|-----------|-------------------|
| **Threshold** | ≥75% of all outstanding shares + majority of EACH class voting separately |
| **Price floor** | ≥1.5× the most recent post-money valuation |
| **Founder terms** | No less favorable than any other common shareholder |
| **Non-compete** | Released in full upon closing of the sale |

The separate class vote requirement means the founder must consent (via Class A) AND investors must consent (via Class C) — no party can drag the other without agreement.

### 6.3 Tag-Along

If any shareholder or group sells more than 25% of their holdings, the founder has the right to sell a pro rata portion on the same terms and conditions. This prevents a scenario where investors sell their stake to an unfriendly acquirer without giving the founder an exit opportunity.

---

## 7. Sunset Provisions — When to Hold, When to Concede

Sunset provisions eliminate the dual-class structure after a specified trigger. They are the most contentious negotiation point in any dual-class governance structure. The founder's negotiating position, by stage:

| Stage | Position |
|-------|----------|
| Pre-Seed → Series A | **No sunset. Non-negotiable.** The company is pre-revenue or early-revenue. There is zero justification for constraining founder control at this stage. Any investor who demands a sunset before Series A does not trust the founder enough to invest. Walk away. |
| Series B | **Accept:** transfer-based sunset (already built into Class A conversion triggers) + death/incapacity sunset (12-month grace, already built in). **Reject:** time-based sunset. |
| Growth / Pre-IPO | **If forced:** 10-year sunset from IPO date (NOT from incorporation date). Negotiate a shareholder vote mechanism to extend the sunset at expiry. |

### 7.1 What to Never Concede

| Demand | Why to Reject |
|--------|---------------|
| Ownership-threshold sunset ("Class A converts if founder falls below X%") | Converts the inevitable dilution path into a governance cliff. The whole point of dual-class is to survive dilution. |
| Sunset < 7 years from IPO | Not enough time. Meta, Google, and Shopify have survived and thrived with long-duration or no-sunset dual-class structures. |
| Sunset triggered by role change (e.g., founder steps down as CEO but remains board chair) | Allows a forced role change to trigger loss of control. The founder may want to transition to Executive Chair — that should not destroy the governance structure. |

### 7.2 Stock Exchange Implications

| Exchange | Dual-Class Policy |
|----------|------------------|
| **TSX (Toronto)** | Permits dual-class. Requires either a **coat-tail provision** (gives minority holders the right to participate in a takeover bid proportionally) OR a sunset. The coat-tail provision is preferable — it protects minority shareholders without stripping founder control. Shopify (TSX: SHOP) used a coat-tail until 2022. |
| **NASDAQ** | Permits dual-class. No mandatory sunset. The tradeoff is S&P 500 exclusion (S&P changed its policy in 2023 to exclude new dual-class entrants). For a Canadian company, this may be less relevant than TSX listing. |

---

## 8. CBCA Legal Framework

The Canada Business Corporations Act provides the statutory foundation for every protection in this document. The following sections are the most critical:

| CBCA Section | What It Does | Why It Matters for This Strategy |
|-------------|-------------|----------------------------------|
| **s.6(1)(c)** | Articles of incorporation must specify the rights, privileges, restrictions, and conditions attached to each class of shares | **The share structure (Class A/B/C, voting ratios, conversion mechanics, founder consent rights) must be specified in the articles at incorporation.** Cannot be added later without a special resolution of each affected class. |
| **s.24(1)** | Shares of a CBCA corporation shall be without par value | Mandatory. The articles specify rights and conditions, not par values. |
| **s.24(3)** | Articles may attach special rights or restrictions to any class of shares | **This is the enabling provision for everything in this document** — 10:1 voting, automatic conversion triggers, founder consent rights, all flow from s.24(3). |
| **s.106(3)** | Directors are elected by ordinary resolution of shareholders | With 10:1 voting, the founder controls director elections even at minority economic ownership. |
| **s.124** | Corporation may indemnify directors and officers | Broadest possible indemnification should be in the by-laws and the CEO employment agreement. |
| **s.173** | Amendments to the articles require a special resolution (2/3 of votes cast) | High bar to change the articles, but not sufficient alone — see s.176 below. |
| **s.176(1)(b)** | Amendments that affect the rights of a class require a separate special resolution of that class | **The founder's nuclear veto.** Changing Class A rights requires a 2/3 vote of Class A holders — which is the founder alone. This cannot be overridden. |
| **s.183** | Amalgamation requires a special resolution + separate class vote if any class is affected | Founder veto on mergers. |
| **s.189(3)** | Sale of substantially all assets requires a special resolution | Founder veto on asset sales (through combined voting power and Class A consent right). |
| **s.190** | Dissent and appraisal rights | Shareholders who vote against certain fundamental changes can demand fair value buyout. Protects the founder against investor-forced transactions — but also protects minorities against founder actions. |
| **s.241** | **Oppression remedy** | **Cannot be contracted away.** Any stakeholder (shareholder, creditor, director, officer) can petition a court if the corporation's conduct is oppressive, unfairly prejudicial, or unfairly disregards their interests. This is dual-edged: it protects the founder against investor abuse, but it also constrains the founder. A dual-class structure does NOT give the founder carte blanche — excessive compensation, self-dealing, or disregard for minority interests can trigger s.241 even if the founder controls every vote. **The founder must act in good faith at all times.** |

---

## 9. Implementation Timeline

### Phase 1: Before Resignation (Now)

| Action | Documents | Details |
|--------|-----------|---------|
| Engage corporate/IP lawyer | Retainer agreement | Specializing in CBCA incorporations, tech company share structures. Must be separate from the IP/employment lawyer resolving the RBC clause (see [F&F Use of Proceeds](../fundraising/ff-round-structure.md), item #1). |
| Engage patent lawyer | Retainer agreement | For provisional patent filing. Must be done on own time and own equipment — NOT during RBC work hours or using RBC resources. |
| Finalize this governance strategy | This document | Review with corporate lawyer before articles are drafted. |

### Phase 2: Resign → Incorporate (1–2 Weeks Post-Resignation)

| Action | Documents | What Goes In |
|--------|-----------|--------------|
| File Articles of Incorporation | CBCA Form 1 | **Everything in Sections 1–3 of this document:** Class A/B/C share structure, voting ratios (10:1), conversion mechanics, authorized share counts, founder consent rights (as Class A class rights), maximum board size. **This is the most important filing in the company's life.** Articles are extremely hard to change after filing (special resolution of each class per s.173/s.176). |
| Adopt By-law No. 1 | Corporate by-law | Standard CBCA by-law: meetings, quorum, officer appointments, banking, indemnification (broadest per s.124). |
| Pass organizational resolutions | Board resolutions | First director = founder. Adopt by-law. Authorize share issuance. Authorize CEO to sign T2057. Adopt ESOP plan. |
| Adopt ESOP plan | Equity incentive plan | 1,500,000 Class B shares reserved. Vesting: 4-year standard, 1-year cliff. Board (i.e., founder at this stage) approves all grants. |
| Execute IP Assignment Agreement | IP transfer agreement | Transfers all IP from founder to BPI. Separate from the T2057 (tax election) — this is the legal transfer of title. Per [Section 85 Rollover Briefing v1.1](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md). |
| File T2057 (Section 85 election) | CRA Form T2057 | Joint election: elected amount = $1 (or lowest defensible amount per accountant). PUC reduction per s.85(2.1). **Do not miss the filing deadline — penalty is $100/month, max $8,000, and CRA may deny the election entirely if >3 years late.** |

### Phase 3: Incorporate → F&F Close (2–8 Weeks Post-Incorporation)

| Action | Documents | What Goes In |
|--------|-----------|--------------|
| Execute CEO Employment Agreement | Employment contract | Everything in [Section 4](#4-ceo-employment-agreement) of this document. |
| Execute SAFE agreements with F&F investors | SAFE instrument + Form 45-106F5 | Per [SAFE Agreement Template](../fundraising/safe-agreement-template.md): $2M cap, 20% discount, 24-month maturity, $500K minimum qualifying financing. No pro-rata, no board rights, no observer rights. |
| File Reports of Exempt Distribution | BCSC filing | Within 10 days of each SAFE execution. Filing fee ~$100 per report. Required under NI 45-106. |
| Incorporate BPI Capital I Ltd | Federal (CBCA) or provincial incorporation | The Phase 2/3 lending SPV. 100% owned by BPI. Incorporated now to establish the entity; operational setup deferred to Series A. |
| Draft inter-company IP license | License agreement | BPI licenses IP to BPI Capital I Ltd for lending operations. Preserves IP ownership in the parent company (important for patent prosecution and investor due diligence). |
| Obtain D&O insurance | Insurance policy | Minimum $5M coverage. Budgeted in [F&F Use of Proceeds](../fundraising/ff-round-structure.md) at $2,000–$5,000/yr. |

### Phase 4: Pre-Seed Close

| Action | Documents | What Goes In |
|--------|-----------|--------------|
| Execute Shareholders' Agreement | SHA | Board composition rules ([Section 2](#2-board-composition-controls)), nomination rights, preemptive rights, drag-along/tag-along ([Section 6](#6-change-of-control-protections)), investor protective provisions (Class C class rights). **This is renegotiated every round — put deal-specific terms here, not foundational protections (those belong in the articles).** |
| Issue Class C-1 Preferred | Subscription agreement | Pre-Seed preferred terms. 1× non-participating liquidation preference. Broad-based weighted average anti-dilution. |
| Convert F&F SAFEs | Conversion notice | SAFEs convert upon Equity Financing ≥ $500K. Per the [SAFE template](../fundraising/safe-agreement-template.md), conversion price = lesser of (a) $2M cap / fully-diluted shares, or (b) round price × 80% (20% discount). F&F investors receive shares of the most senior class issued in the financing (Class C-1 Preferred). |

### Critical Ordering Principle

**Articles of incorporation are filed ONCE and are extremely hard to change.** Every protective provision that the founder wants to be permanent must be in the articles from day one. The shareholders' agreement is renegotiated at every round — its protections are important but impermanent. The employment agreement is bilateral and can only be changed by mutual consent — but a desperate company can offer to renegotiate. Only the articles have the structural permanence of requiring a separate class vote to amend.

---

## 10. Traps to Watch For

### 10.1 Investment Term Traps

| Trap | What It Is | Defence |
|------|-----------|---------|
| **Participating preferred** | Investors get their money back (liquidation preference) AND a pro rata share of remaining proceeds — double-dipping. On a $50M exit with $12M Series A invested: non-participating = investor takes $12M OR pro rata share (whichever is higher). Participating = investor takes $12M AND pro rata share. | **Never accept participating preferred.** Insist on 1× non-participating liquidation preference at every round. |
| **Full ratchet anti-dilution** | If the company raises a down round, the investor's conversion price resets to the new lower price — as if they invested at the lower valuation. Massively dilutive to the founder. | **Insist on broad-based weighted average anti-dilution.** This is market standard and adjusts the conversion price proportionally, not fully. |
| **Cumulative dividends** | Preferred shares accrue dividends that compound over time and are paid before common shareholders in a liquidity event. After 5–7 years, cumulative dividends can add 30–50% to the liquidation preference stack. | **Reject cumulative dividends.** Accept non-cumulative dividends (declared at board discretion, if at all). |
| **Liquidation preference stack** | Each round adds another layer of liquidation preference. By Series B, the stack could be: $12M (Series A) + $35M (Series B) = $47M that gets paid before common shareholders see anything. On a $50M exit, the founder's 37% = $1.1M. | **Model the liquidation waterfall at every round.** Ensure the founder's economics are acceptable at 1×, 2×, and 3× the investment amount. Never accept more than 1× non-participating per round. |

### 10.2 Governance Traps

| Trap | What It Is | Defence |
|------|-----------|---------|
| **Protective provisions creep** | Each investor series negotiates its own veto list. By Series B, the founder needs separate approvals from Series A, Series B, and common shareholders for any significant action — four separate votes for one decision. | **Require majority of ALL outstanding preferred shares voting together** (not each series individually) for preferred protective provisions. Each series gets board representation, not its own veto. |
| **Board observer creep** | Non-board investors demand observer seats. By Series B, there are 3 observers at every meeting who hear everything but have no fiduciary duty. They report back to their funds. | **Limit observers.** Board may exclude any observer from any session by majority vote. No observer rights without board consent. |
| **Information rights escalation** | Each round adds more reporting: monthly financials, quarterly board packages, annual audits, real-time metrics dashboards. By Series B, the founder is spending 20% of their time on investor reporting. | **Agree to specific information rights at each investment** and resist scope expansion. Terminate information rights for investors who fall below a specified ownership threshold (e.g., <5%). |

### 10.3 Founder-Specific Traps

| Trap | What It Is | Defence |
|------|-----------|---------|
| **Founder vesting** | Investors demand that the founder's shares vest over 4 years, as if the founder were a new hire. If the founder is terminated at Month 12, they lose 75% of their shares. | **Negotiate aggressively:** (a) credit for prior work — 25% vested at close (1 year of pre-funding development); (b) all vested shares remain Class A; (c) 100% acceleration on termination without cause or Good Reason; (d) 100% acceleration on change of control (double-trigger). |
| **Founder salary cap** | Investors set a below-market salary for the founder "to preserve capital." Combined with no revenue, this creates personal financial pressure that weakens the founder's negotiating position at the next round. | **Set a reasonable salary** from Pre-Seed. Not excessive (s.241 oppression risk), but sufficient to remove personal financial pressure. The [F&F operating buffer](../fundraising/ff-round-structure.md) ($15K–$40K) bridges the gap between resignation and Pre-Seed. |

### 10.4 Structural Traps

| Trap | What It Is | Defence |
|------|-----------|---------|
| **Running out of cash** | The most powerful governance protections in this document are worthless if the company is desperate for capital. A company with 2 months of runway will accept any terms. | **Never go below 6 months of runway before starting a fundraise.** The [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) sizes each round for 18–24 months of runway. Start raising at Month 12, not Month 18. |
| **Oppression remedy (s.241)** | Investors can petition a court if the founder uses dual-class control for self-dealing, excessive compensation, or disregard of minority interests. The court has broad discretion to order any remedy it considers fit, including ordering the company to buy back shares or restraining the founder's actions. | **Act in good faith.** No excessive salary, no related-party sweetheart deals, no disregarding minority economic interests. The dual-class structure grants control, not impunity. Consider all stakeholders in every material decision. Document the business rationale for any decision that could be perceived as self-interested. |

---

## Key Numbers Summary

| Parameter | Value | Source |
|-----------|-------|--------|
| Class A voting ratio | 10 votes per share | This document, Section 1 |
| Founder Class A shares at founding | 8,500,000 | Founder Financial Model (85% of 10M) |
| ESOP reserve (Class B) at founding | 1,500,000 (15%) | Founder Financial Model |
| Voting breakpoint (founder loses majority) | ~9.1% economic ownership | This document, Section 1.5 |
| Founder voting % at IPO (27% economic) | **~78.7%** | This document, Section 1.4 |
| Maximum board size (in articles) | 9 | This document, Section 2 |
| CEO termination for cause | 75% board supermajority | This document, Section 4 |
| CEO severance without cause | 24 months + 100% equity acceleration | This document, Section 4 |
| Drag-along threshold | ≥75% all shares + majority of each class | This document, Section 6 |
| Sunset (if forced at Growth/Pre-IPO) | 10 years from IPO | This document, Section 7 |
| Liquidation preference (standard) | 1× non-participating | This document, Section 10 |
| Anti-dilution (standard) | Broad-based weighted average | This document, Section 10 |
| F&F SAFE cap / discount | $2M / 20% | F&F Round Structure, SAFE Template |
| Pre-Seed raise / pre-money | $1.5M / $6M | Founder Financial Model |

---

## Cross-Reference Verification

This document was cross-referenced against the following source documents on creation:

| Check | Source Document | Status |
|-------|----------------|--------|
| Founder ownership at inception = 85% (15% ESOP) | [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md), Row 1 | Consistent (8.5M / 10M = 85%) |
| Dilution path: 85% → 68% → 55% → 45% → 37% → 32% → 27% | Founder Financial Model, Section 2 equity journey table | Consistent |
| F&F SAFE terms: $2M cap, 20% discount | [F&F Round Structure](../fundraising/ff-round-structure.md), Section 1 | Consistent |
| SAFE conversion trigger: $500K minimum qualifying financing | [SAFE Agreement Template](../fundraising/safe-agreement-template.md), Section 1.5 | Consistent |
| ESOP reserve = 15% = 1,500,000 / 10,000,000 | Founder Financial Model ("15% ESOP reserved") | Consistent |
| S.85 rollover: IP transfer at elected amount $1, PUC reduction per s.85(2.1) | [Section 85 Rollover Briefing v1.1](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md), Sections 1, 4 | Consistent. PUC dual-class interaction flagged (Question 5 for accountant) — requires counsel confirmation. |
| Dual share class mentioned in existing docs | F&F Round Structure (budget item #3), Section 85 Briefing (Question 5) | Consistent. This document expands the one-line mention into full specification. |
| No par value shares (CBCA s.24(1)) | Section 85 Briefing (no par value assumed throughout) | Consistent |
| D&O insurance: $2K–$5K/yr | F&F Round Structure, budget item #6 | Consistent. This document specifies $5M minimum coverage. |

### Items Requiring Founder Financial Model Update

The [Founder Financial Model](../../consolidation%20files/Founder-Financial-Model.md) should be updated to reflect:

1. **Voting control column.** The equity journey table (Section 2) shows only economic ownership. A "Founder Voting %" column should be added showing the 10:1 impact (as calculated in Section 1.4 of this document).
2. **Liquidation waterfall modeling.** Section 7 ("Dilution May Be Higher Than Modeled") mentions liquidation preferences but does not model them. A waterfall analysis showing founder proceeds at various exit valuations (1×, 2×, 3× last post-money) should be added.
3. **BPI Capital I Ltd.** The SPV for Phase 2/3 lending operations is not mentioned in the financial model. If SPV-level economics (management fees, carried interest, intercompany licensing) affect founder economics, they should be modeled.

---

## Disclaimer

This document is an internal planning tool. It does not constitute legal advice. All governance structures described herein must be reviewed, refined, and implemented by qualified Canadian corporate counsel before being embedded in the articles of incorporation, shareholders' agreement, or any other legal instrument. The founder should not file articles of incorporation without legal counsel review of the share structure, class rights, and conversion mechanics.

The CBCA section references in this document reflect the statute as of March 2026. Confirm all statutory references against the current text of the Canada Business Corporations Act before relying on them.

---

*Cross-references: [Founder-Financial-Model.md](../../consolidation%20files/Founder-Financial-Model.md) | [ff-round-structure.md](../fundraising/ff-round-structure.md) | [safe-agreement-template.md](../fundraising/safe-agreement-template.md) | [Section-85-Rollover-Briefing-v1.1.md](../../consolidation%20files/Section-85-Rollover-Briefing-v1.1.md)*

*VERSION 1.0 | Bridgepoint Intelligence Inc. | March 2026*
