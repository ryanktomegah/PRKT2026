# IP Risk Pre-Counsel Analysis — Prompt

---

## ROLE AND CONSTRAINTS

You are acting as a **coalition of three adversarial senior professionals** performing a pre-counsel risk analysis for a Canadian startup founder:

1. **A senior technology/IP attorney** (15+ years, Bay Street firm, specializing in employer IP disputes and startup formation under Canadian law)
2. **A startup financing counsel** (experienced in NACO SAFEs, NI 45-106 exempt distributions, and pre-seed diligence in Canada)
3. **A litigation strategist** (experienced in evaluating which claims a large Canadian bank would actually pursue vs. use as leverage)

**You are not my lawyer. You must not present yourself as one. You must not provide legal advice. You are performing structured risk identification to help me prepare for real counsel.**

**Operating constraints — follow these exactly:**

- Be skeptical, adversarial, and precise. Your job is to find every crack, not to reassure me.
- Do not give generic startup advice unless it is directly tied to THIS fact pattern.
- Do not say "consult a lawyer" until AFTER you have fully analyzed every issue. The entire point of this exercise is to prepare for that conversation.
- Do not assume missing facts in my favour. If a fact is missing, identify it as a **critical unknown** and explain exactly how its presence or absence changes the legal outcome in each direction.
- If a question has multiple plausible answers, present the **strongest version of each side** before stating which you consider more likely and why.
- Whenever you say "it depends," immediately state what it depends on and rank the dependencies.
- If the right answer is "do not raise money yet," say so directly.
- If clean-room reimplementation should be the baseline assumption, say so directly.

---

## FACT PATTERN

Read every fact below carefully. These are the ONLY facts you may rely on. Anything not stated here is a critical unknown.

### The Founder

- I am a Canadian citizen residing in British Columbia.
- I am currently employed at the **Royal Bank of Canada (RBC)** as a **Credit Management Resolution Officer** in their retail banking division.
- My RBC employment start date is **January 12, 2026**.
- I have not yet resigned. I am still employed at RBC as of today (**March 23, 2026**).
- My role at RBC involves **retail credit management** — specifically working with customers in financial difficulty on their existing retail banking products (mortgages, LOCs, credit cards). It does NOT involve: cross-border payments, SWIFT messaging, B2B payments, ML/AI development, payment infrastructure, fintech product development, or capital markets.
- I have NO access to RBC's cross-border payment systems, SWIFT infrastructure, correspondent banking data, or institutional payment processing systems through my role.
- I have NOT used any RBC equipment (laptop, phone, network, VPN, email, cloud resources, internal tools) to develop the prototype.
- I have NOT used any RBC proprietary data, internal documents, trade secrets, customer data, or confidential information in the prototype.
- I have NOT discussed the startup idea with any RBC employee, manager, or colleague.
- I have NOT sought or received approval for outside business activity from RBC.

### The Prototype (Bridgepoint Intelligence / "BPI")

- BPI is a software system for **detecting and bridging cross-border B2B payment failures** using ML-driven risk pricing.
- The system ingests SWIFT pacs.002/pacs.008 messages, detects payment failures via BIC-pair analysis, prices short-term bridge loans using a structural ML model (CVA, PD estimation), and auto-settles on SWIFT UETR confirmation.
- The target market is **Tier 1 banks' institutional/correspondent banking divisions** — a completely different business line from retail credit management.
- The prototype consists of: ML inference engine, SWIFT integration layer, 7 Docker images, full CI/CD pipeline, **1,476 passing tests**.
- All development was done on **personal equipment** (personal laptop, personal cloud accounts), on **personal time** (evenings, weekends, days off), using **publicly available information** (BIS papers, SWIFT GPI documentation, academic research, public regulatory filings).
- The AI-assisted development approach ("Ford model") means much of the code was generated with AI tools on personal accounts.

### The Git History Problem

- The git repository (**PRKT2026**) has its **entire commit history within the RBC employment period** (all commits after January 12, 2026).
- There are **no commits, documents, or dated artifacts from before January 12, 2026** currently in the repository.
- I believe the **core concepts** were conceived before my RBC employment began, but I have not yet assembled or notarized evidence of this.
- I do not know what pre-employment evidence exists (notes, emails, searches, conversations). This is an **unassessed evidence question**.

### The RBC Employment Agreement

- The RBC offer letter contains a **broad IP assignment clause** that covers works "conceived, reduced to practice, or developed" during the period of employment.
- I have NOT yet had this clause reviewed by an IP/employment lawyer.
- I do NOT know the exact scope language — whether it is limited to "in the course of employment," "related to the employer's business," "using employer resources," or is a blanket assignment of all IP created during employment regardless of connection to RBC.
- I do NOT know whether there is a separate IP/invention assignment agreement, confidentiality agreement, or outside business activity policy beyond the offer letter.
- I do NOT know the enforceability precedents for this specific clause under BC/Canadian employment law.

### The Fundraising Plan

- I plan to raise **$75,000–$150,000** from friends and family using **NACO-adapted Canadian SAFEs** at a **$2,000,000 pre-money valuation cap**.
- The primary use of proceeds is: IP lawyer ($5K–$10K), patent lawyer ($15K–$25K), CBCA incorporation ($2K–$4K), S.85 rollover ($3K–$8K), operating buffer.
- I plan a subsequent **Pre-Seed round of $1.5M at $6M pre-money** after resolving IP, filing patent, and incorporating.
- I have prepared: valuation analysis, SAFE template, NDA template, risk disclosure document, round structure document, and pre-fundraising checklist. All are in `docs/fundraising/`.
- The risk disclosure document **does** disclose the RBC IP risk (Section 2.2), including that the entire git history falls within the employment period.

### The Patent Strategy

- I plan to file a **provisional patent** (US + CA) covering the core bridging methodology.
- No patent has been filed yet. No priority date exists.
- The patent strategy envisions a **15-patent portfolio** with projected value of $18B–$35B over the patent lifetime.
- Filing a patent would create a **public record of the invention** that RBC could discover.

### Strategic Context

- My chosen strategy is **Angle 6: resign → resolve IP → file patent → incorporate → approach banks as external vendor**.
- RBC is both a potential IP claimant AND a potential future customer (the go-to-market strategy targets RBCx as the first pilot bank).
- The relationship with RBC is therefore **dual-natured** — adversarial on IP, collaborative on commercial engagement.

---

## JURISDICTION AND FRAMING

- **Primary jurisdiction:** Canada (British Columbia for employment law; federal for CBCA incorporation, patent law, and IP ownership under the *Copyright Act* and *Patent Act*).
- **Secondary:** Ontario (RBC headquarters; potential forum for any RBC-initiated action).
- **Cross-border:** US patent law (USPTO provisional filing), US securities implications ONLY if they materially affect the fundraising or IP strategy.
- **Frame this as:** a startup fundraising and ownership diligence problem, not an abstract IP law exam. Every analysis should connect back to: Can I raise money? Can I file a patent? Can I incorporate safely? What happens if RBC notices?

---

## REQUIRED OUTPUT — FOLLOW THIS STRUCTURE EXACTLY

### SECTION 1 — FACT RECONSTRUCTION

Build a **chronological timeline** from the facts above, marking each event as CONFIRMED or INFERRED.

Then list every **missing fact** needed for a reliable legal opinion. For each:
- Describe the fact
- Rate importance: **CRITICAL** / IMPORTANT / HELPFUL
- Explain how its presence vs. absence changes the analysis (both directions)

Then provide a **numbered list of follow-up questions** to me, in strict priority order (most important first). Minimum 15 questions.

---

### SECTION 2 — IP CLAIM MAP

Create a detailed table with these columns:

| Asset | Possible Owner/Claimant | Legal Theory | Best Argument for Founder | Best Argument for RBC | Key Evidence Needed | Risk Level |
|-------|------------------------|-------------|--------------------------|----------------------|--------------------:|-----------|

**Mandatory rows** (add more if the fact pattern warrants):

1. Source code (existing PRKT2026 repository)
2. Architecture and design documents (docs/ subdirectories, playbooks, briefings)
3. ML models and training methodology (C2 model, BIC-pair detection, CVA/PD estimation)
4. Pricing logic, rules, heuristics, and fee constants (QUANT-controlled parameters)
5. Patentable inventions (bridging methodology, auto-settlement on UETR)
6. Trade secrets and know-how (domain expertise assembled during prototype development)
7. Brand, domain, and company name (created post-employment-start but pre-incorporation)
8. Clean-room reimplementation (new code written after resignation from same inventor)
9. Future patents derived from or continuing from current work
10. Investor-facing materials (pitch deck, financial models, valuation analysis)
11. Academic/research work product (papers, analyses)
12. Data compilations (BIC-pair databases, rejection code taxonomies, corridor risk data)

For each row, explain the risk rating.

---

### SECTION 3 — EMPLOYMENT AGREEMENT ANALYSIS

Since the exact clause language is a **critical unknown**, analyze the three most common formulations used by Canadian Schedule I banks and assess BPI's exposure under each:

**Formulation A — Narrow:** "Inventions conceived or reduced to practice **in the course of employment** or **using employer resources**."

**Formulation B — Medium:** "Inventions or works conceived or developed **during the period of employment** that **relate to the employer's business** or **anticipated business**."

**Formulation C — Broad:** "All inventions, works, improvements, and intellectual property conceived, created, or reduced to practice **during the period of employment**, regardless of whether created on personal time or using personal resources."

For each formulation:
- Explain the strongest RBC interpretation
- Explain the strongest founder interpretation
- State what a cautious pre-seed investor would assume
- Identify which IP rights are affected (copyright, patent assignment, trade secrets, confidential information, moral rights)
- Assess enforceability under BC employment law, noting any relevant Canadian case law or statutory provisions
- Rate the risk to BPI: LOW / MEDIUM / HIGH / EXTREME

Then state: **Which formulation should I assume for planning purposes until I obtain the actual clause?**

---

### SECTION 4 — LEGAL ISSUE DEEP DIVE

Analyze each question below with this structure:
- **Short answer** (1–2 sentences)
- **Full analysis** (detailed reasoning)
- **Key fact dependencies** (what facts would most change the answer)

**Questions:**

1. Could RBC claim **ownership of the existing codebase** under copyright law?
2. Could RBC claim **ownership of the underlying inventions** even if the code is entirely rewritten?
3. Could RBC **block, oppose, or complicate a patent filing** — and would they have standing to do so?
4. Could RBC claim I **used confidential information, trade secrets, or internal know-how** even if I never copied code or accessed RBC systems?
5. Does the fact that **the entire git history falls within my employment period** materially worsen my position compared to having pre-employment commits?
6. Under Canadian law, how much does it matter that I built it on **personal time, personal equipment, with no use of employer resources**?
7. How much does it matter whether the startup concept **overlaps with RBC's actual or reasonably contemplated business**? (Note: RBC does process cross-border payments, but through an entirely different division than my role.)
8. If I **incorporate BPI now** (while still employed at RBC), does that create additional legal exposure?
9. If I **raise F&F money before obtaining an IP lawyer opinion**, what specific legal and ethical risks arise?
10. Under what conditions would **clean-room reimplementation materially reduce risk**, and under what conditions would it be insufficient or unnecessary?
11. If RBC discovers the patent filing, **what is their most likely response** — and what is their most dangerous response?
12. Could RBC claim that **the financial models, business strategy documents, and investor materials** (not just the code) are covered by the IP clause?
13. What is the **statute of limitations** for RBC to bring a claim, and does the clock start at creation, discovery, resignation, patent publication, or commercial launch?
14. If I proceed with Angle 6 (resign → patent → approach RBC as vendor), could RBC argue that I am **commercializing their IP back to them**?

---

### SECTION 5 — CLEAN-ROOM STRATEGY

Design a **legally defensible clean-room reimplementation plan** assuming it may be needed. Research current best practices for clean-room development — a proper process typically requires strict separation between those who analyze the original work ("dirty room") and those who rebuild from non-infringing specifications ("clean room"), plus documentation, access controls, and final similarity analysis.

Address:

1. **Should clean-room be the default assumption?** (Yes/no and why, given this fact pattern)
2. **Quarantine protocol:** What artifacts from PRKT2026 must be quarantined and who can access them?
3. **Dirty room team:** What do they do? Can the founder be on this team?
4. **Clean room team:** What do they do? Can the founder be on this team? (This is the critical question for a solo founder.)
5. **The solo founder problem:** In a traditional clean-room, the inventor cannot be in both rooms. How does this work when there is only one person? What are the options?
6. **Repository hygiene:** New repo, new accounts, new git identity? What level of separation is needed?
7. **Documentation requirements:** What records must be created and preserved?
8. **Specification document:** What can the clean-room team work from? Can the patent specification serve as the "clean" specification?
9. **Similarity analysis:** How is the final product compared to the original to establish independence?
10. **Contamination risks:** What actions would invalidate the clean-room defense?
11. **30-day execution plan:** Step-by-step timeline assuming founder resigns on Day 0
12. **Litigation hold records:** What should be preserved in case of future diligence or litigation?

---

### SECTION 6 — FUNDRAISING IMPACT

Analyze how the unresolved IP uncertainty affects each of these specifically:

1. **SAFE terms** — Should the cap, discount, or other terms be adjusted?
2. **Valuation cap** — Is $2M defensible given the IP uncertainty? Should it be lower?
3. **Investor trust** — How does a sophisticated F&F investor react to this disclosure?
4. **Disclosure obligations** — Is the current risk disclosure (Section 2.2 of investor-risk-disclosure.md) sufficient? What's missing?
5. **Use-of-proceeds language** — How should the IP lawyer engagement be described?
6. **Timing of incorporation** — Before or after IP opinion?
7. **Timing of patent filing** — Before or after IP opinion? Before or after resignation?
8. **Is it defensible to take F&F money before obtaining a legal opinion?** — Be direct.

Then draft three versions of an IP status disclosure:

**Version 1 — CANDID (recommended):** What you would actually want an investor to read.

**Version 2 — CONSERVATIVE:** The most cautious defensible framing.

**Version 3 — TOO AGGRESSIVE (do NOT use):** An example of what a founder might be tempted to write that would create liability. Explain why each sentence is problematic.

---

### SECTION 7 — DECISION MATRIX

Evaluate these six paths:

| Path | Description |
|------|-------------|
| **A** | Raise F&F now → IP lawyer later → patent → incorporate |
| **B** | IP lawyer first (self-funded, $5K–$10K) → raise F&F → patent → incorporate |
| **C** | Incorporate now → IP lawyer → raise → patent |
| **D** | Clean-room reimplementation first → IP lawyer → raise → patent |
| **E** | IP lawyer first → clean-room if recommended → raise → patent → incorporate |
| **F** | Abandon PRKT2026 entirely → resign → restart from scratch → raise → patent |

Score each path **1–10** (10 = best) on:

| Criterion | Weight | Explanation |
|-----------|--------|-------------|
| Legal risk minimization | 25% | Lowest exposure to RBC claims |
| Financing credibility | 20% | How a sophisticated investor evaluates this path |
| Speed to fundraise | 15% | Calendar time to first dollar in the bank |
| Cash efficiency | 10% | Minimizes out-of-pocket before external funding |
| Ethical defensibility | 15% | Could you defend this sequence to a regulator, judge, or journalist? |
| Diligence survivability | 15% | Would this path survive Pre-Seed investor due diligence? |

Calculate weighted scores. **Recommend one path. Explain why.**

---

### SECTION 8 — LAWYER PREP MEMO

Draft a **ready-to-send memo** to a BC IP/employment lawyer. Include:

1. **Factual background** (concise, chronological, no legal conclusions)
2. **Top legal questions** (numbered, specific to this fact pattern)
3. **Documents to review** (list everything the lawyer needs to see)
4. **Decision deadlines** (what decisions are time-sensitive and why)
5. **Desired outputs** (what written deliverables I need from counsel)
6. **Scope of engagement** (what I'm asking them to opine on)
7. **Gating note** (explain that this opinion gates a fundraising round and patent filing)
8. **Budget expectation** ($5K–$10K — is this realistic for this scope?)

---

### SECTION 9 — RED TEAM

Attack your own analysis:

1. **What are the weakest parts of your reasoning?**
2. **What assumptions might be wrong?**
3. **What arguments would aggressive RBC counsel make that you may be underestimating?**
4. **What facts, if discovered later, could collapse the optimistic case?** (e.g., what if the founder once Googled something on RBC's network, what if RBC's policy is broader than assumed, what if a co-worker knew about the project)
5. **What would a hostile acquirer or down-round investor do with this IP uncertainty 3 years from now?**
6. **Is there a scenario where RBC discovers this and does nothing — and what would motivate that?**

---

### SECTION 10 — EXECUTIVE BOTTOM LINE

Provide:

- **Most likely practical outcome** (what probably happens in the real world)
- **Worst plausible outcome** (not worst theoretically possible, but worst that a reasonable person should plan for)
- **Best plausible outcome** (optimistic but realistic)
- **What I should do in the next 72 hours** (specific, actionable, ordered)
- **What I absolutely should NOT do yet** (specific prohibitions with reasons)

---

## CLOSING DELIVERABLES

After the full analysis, end with three numbered lists:

**TOP 10 FACTS I STILL NEED FROM YOU**
(Specific questions about my situation that would most change the analysis)

**TOP 10 DOCUMENTS TO GATHER**
(In priority order, with notes on what to look for in each)

**TOP 10 QUESTIONS FOR REAL COUNSEL**
(The exact questions to bring to the IP/employment lawyer, ordered by importance)

---

*This analysis will be provided to qualified legal counsel as preparation material. It is not legal advice and should not be relied upon as such.*
