# IP Risk Pre-Counsel Analysis — Bridgepoint Intelligence (PRKT2026)

**Date:** March 23, 2026
**Subject:** Pre-counsel structured risk identification — RBC employment IP assignment
**Prepared for:** Founder (for use in preparing for engagement with qualified IP/employment counsel)
**Status:** DRAFT — NOT LEGAL ADVICE

---

> **This document is a structured risk identification exercise. It is not legal advice and must not be relied upon as such. Its sole purpose is to prepare the founder for an informed conversation with qualified Canadian IP and employment counsel. Every conclusion herein should be tested against the opinion of a licensed lawyer before any action is taken.**

---

## ROLE FRAMING

This analysis is written from the perspective of three adversarial senior professionals:

1. **A senior IP/employment attorney** (15+ years, Bay Street, specializing in employer IP disputes and Canadian startup formation)
2. **A startup financing counsel** (experienced in NACO SAFEs, NI 45-106 exempt distributions, Canadian pre-seed diligence)
3. **A litigation strategist** (evaluating which claims a Schedule I bank would actually pursue vs. use as leverage)

The operating posture is **skeptical, adversarial, and precise**. The job is to find every crack, not to reassure.

---

## SECTION 1 — FACT RECONSTRUCTION

### 1.1 Chronological Timeline

| # | Date | Event | Status |
|---|------|-------|--------|
| 1 | Pre-2026 (unspecified) | Founder claims core BPI concepts were conceived | **UNVERIFIED** — no dated evidence assembled |
| 2 | Pre-2026 (unspecified) | Founder may have personal notes, emails, searches, or conversations about cross-border payment bridging | **UNASSESSED** — evidence inventory not conducted |
| 3 | January 12, 2026 | Founder begins employment at RBC as Credit Management Resolution Officer (retail banking) | **CONFIRMED** |
| 4 | January 12, 2026 | Founder signs RBC offer letter containing broad IP assignment clause | **CONFIRMED** — clause language obtained (see Section 3) |
| 5 | January 12, 2026 – present | All commits in PRKT2026 git repository occur during RBC employment | **CONFIRMED** — entire git history post-dates employment start |
| 6 | January 12, 2026 – present | All development performed on personal equipment (laptop, cloud accounts) on personal time (evenings, weekends, days off) | **CLAIMED** — no independent verification |
| 7 | January 12, 2026 – present | No RBC equipment, network, VPN, data, or internal tools used | **CLAIMED** — no independent verification |
| 8 | January 12, 2026 – present | No RBC proprietary data, trade secrets, customer data, or confidential information used | **CLAIMED** — no independent verification |
| 9 | January 12, 2026 – present | No discussion of BPI with any RBC employee, manager, or colleague | **CLAIMED** — no independent verification |
| 10 | January 12, 2026 – present | No outside business activity approval sought from RBC | **CONFIRMED** (by omission — founder states this was not done) |
| 11 | March 2026 (approx) | BPI prototype reaches 1,476 passing tests, 7 Docker images, full CI/CD, ML inference engine, SWIFT integration layer | **CONFIRMED** from repository |
| 12 | March 20, 2026 | Capital Partner Strategy, Founder Financial Model, Revenue Projection Model created | **CONFIRMED** from memory |
| 13 | March 23, 2026 | Founder still employed at RBC; has not resigned | **CONFIRMED** |
| 14 | Not yet occurred | IP/employment lawyer engagement | **NOT STARTED** |
| 15 | Not yet occurred | Patent filing (provisional, US + CA) | **NOT STARTED** |
| 16 | Not yet occurred | CBCA incorporation | **NOT STARTED** |
| 17 | Not yet occurred | F&F fundraising ($75K–$150K on NACO SAFEs) | **NOT STARTED** |
| 18 | Not yet occurred | Resignation from RBC | **NOT STARTED** |
| 19 | Planned | Pre-Seed round ($1.5M at $6M pre-money) | **PLANNED** |

### 1.2 Critical Inference

**The single most damaging inference an adversary can draw:** Every artifact constituting BPI — code, architecture, ML models, financial models, investor materials, business strategy — was created between January 12, 2026 and March 23, 2026, a period of approximately 10 weeks, during which the founder was employed by RBC under a broad IP assignment clause. There is zero documentary evidence in the repository of pre-employment conception.

This is not merely a timing problem. It is the **structural core** of the risk. Everything that follows in this analysis flows from this fact.

### 1.3 Missing Facts — Critical Unknowns

| # | Missing Fact | Importance | If Present (Favourable) | If Absent (Unfavourable) |
|---|-------------|-----------|------------------------|--------------------------|
| 1 | **Exact, complete text of all IP-related clauses** in the RBC offer letter, any separate IP/invention assignment agreement, and any confidentiality/non-compete agreement | **CRITICAL** | We have the offer letter clause (see Section 3). But we do not know if there are additional agreements (e.g., a separate invention assignment, NDA, or outside business activity policy signed at onboarding). Additional agreements could narrow or broaden exposure. | If the offer letter clause is the only IP provision, the analysis in Section 3 applies directly. If there are additional agreements, they could impose additional obligations (e.g., mandatory disclosure, non-compete, garden leave). |
| 2 | **Pre-employment evidence of conception** — dated notes, emails, texts, search history, bookmarks, conversations with identifiable third parties, domain registrations, prior prototypes, journal entries | **CRITICAL** | Strong pre-employment evidence is the single most powerful counter to RBC's claim. If the core inventive concept demonstrably predates January 12, 2026, the argument shifts from "created during employment" to "reduced to practice during employment using personal resources, based on pre-existing independently-conceived ideas." This distinction matters enormously under Canadian common law. | Without pre-employment evidence, the founder's position rests entirely on: (a) the argument that the work is unrelated to RBC's business, (b) the equitable defence that the clause is unconscionably broad, and (c) the factual claim of personal time/equipment. These are weaker without corroboration. |
| 3 | **Whether RBC's onboarding included a separate IP/invention assignment form** distinct from the offer letter | **CRITICAL** | If the offer letter is the sole IP document, the clause is broad but may be attacked as boilerplate not specifically negotiated. | If there is a separate, detailed invention assignment (common at banks for technology roles, less common for retail credit), it may contain additional provisions such as mandatory invention disclosure schedules, assignment of moral rights, or survival clauses. |
| 4 | **RBC's outside business activity (OBA) policy** — text, scope, whether it applies to this founder's role | **CRITICAL** | If RBC has a formal OBA policy that permits personal projects unrelated to banking (common in retail roles), this is strong evidence that RBC itself distinguishes between work product and personal activity. | If the OBA policy requires pre-approval for any outside business activity and the founder did not seek approval, this creates an independent compliance violation that strengthens RBC's position in any dispute — not because it proves IP ownership, but because it provides RBC with disciplinary leverage and undercuts the "good faith" narrative. |
| 5 | **Whether the founder's role description or job duties reference technology, innovation, software development, or payment systems** | **IMPORTANT** | If the role description is purely retail credit management (collections, workouts, forbearance), this strongly supports the "unrelated to duties" defence. | If the role description includes any language about "process improvement," "innovation," "technology adoption," or similar, RBC could argue that the founder was expected to bring technological thinking to the role, even if the specific domain differs. |
| 6 | **Whether any RBC system logs show access to cross-border payment, SWIFT, or correspondent banking systems or data** | **CRITICAL** | If RBC's access logs confirm zero access to relevant systems, this is powerful exculpatory evidence. | If there is any access — even incidental, such as viewing a training module about SWIFT or reading an internal wiki page about correspondent banking — RBC could argue exposure to confidential information. |
| 7 | **Whether RBC's Code of Conduct or internal policies define "Work Product" differently or more narrowly than the offer letter** | **IMPORTANT** | Internal policies that narrow the scope of the offer letter clause (e.g., by reference to "business-related" work) could support a narrower reading. | The RBC Code of Conduct states: IP "created by employees during their employment belongs to and remains the exclusive property of RBC." This is consistent with the broadest reading of the offer letter clause. |
| 8 | **Whether the AI tools (Claude, etc.) used in the "Ford model" development were accessed via personal accounts or employer-provisioned accounts** | **IMPORTANT** | Personal accounts on personal devices = no employer resource argument. | If any AI tool was accessed through an RBC-provisioned account, SSO, or network, it could be argued that employer resources contributed to the work product. |
| 9 | **Whether the founder discussed, brainstormed, or mentioned the concept with anyone who could testify to pre-employment conception** | **IMPORTANT** | Third-party witnesses to pre-employment ideation are powerful corroboration. | Without witnesses, the founder's claim of pre-employment conception is self-serving and uncorroborated. |
| 10 | **Whether the founder has any prior employment agreements (before RBC) that contain IP assignment clauses** | **HELPFUL** | Prior agreements may not apply (they typically terminate with employment), but they could create chain-of-title complications if any prior employer could claim the concept. | If no prior employer has an IP claim, the only claimant is RBC. |
| 11 | **Whether the personal cloud accounts (AWS, GCP, etc.) used for development have audit trails showing exclusive personal-device access** | **HELPFUL** | Cloud provider access logs showing only personal IP addresses and devices strengthen the "no employer resources" claim. | Absence of logs is not damaging per se, but gathering them now (before they rotate) is prudent. |
| 12 | **The founder's work schedule at RBC — shift work, fixed hours, or flexible** | **HELPFUL** | If the founder works fixed shifts (e.g., 9-5 M-F), git commit timestamps showing commits exclusively outside those hours are corroborating evidence. | If the founder has flexible hours, the temporal separation is harder to establish. |
| 13 | **Whether RBC has any existing or planned products in the cross-border payment bridging space** | **IMPORTANT** | If RBC has no product in this space, the "unrelated to employer's business" argument is stronger. | RBC is a Schedule I bank that processes cross-border payments. Even though the founder's role is unrelated, RBC's *corporate* business includes correspondent banking and cross-border payments. An aggressive reading of "relates to the employer's business" could capture BPI. |
| 14 | **Whether the RBC offer letter contains a severability clause** | **HELPFUL** | A severability clause means that if one part of the IP clause is struck down, the rest survives. This cuts both ways — it prevents a successful challenge from voiding the entire agreement, but it also means a court could narrow the clause rather than void it. | Without a severability clause, successfully challenging the breadth of the IP clause could void it entirely, which favours the founder. |
| 15 | **Whether the founder signed any document at RBC acknowledging the IP policy specifically** (beyond the general offer letter acceptance) | **IMPORTANT** | If the founder signed a specific IP acknowledgment, RBC can argue informed consent. | If the offer letter was a take-it-or-leave-it standard form with no specific IP discussion, the unconscionability argument is stronger. |

### 1.4 Follow-Up Questions for the Founder (Priority Order)

1. **Do you have the complete, unredacted text of your RBC offer letter?** We have the IP clause from a prior review, but I need to confirm: is there any other IP-related language elsewhere in the offer letter or in any separate document you signed at onboarding (invention assignment, NDA, non-compete, outside business activity acknowledgment)?

2. **Have you conducted a systematic search for pre-employment evidence?** Specifically: personal email (search for "payment," "bridge," "SWIFT," "cross-border," "fintech," "startup"), text messages, Signal/WhatsApp conversations, personal notes (physical or digital), browser bookmarks, Google search history, domain registration records, social media posts/DMs, journal entries, conversations with friends or family who could testify.

3. **Did you discuss the concept with anyone — friend, family member, former colleague, mentor — before January 12, 2026?** If so, can they provide a written statement with specific dates and details of what was discussed?

4. **What is your exact work schedule at RBC?** Fixed shifts or flexible hours? Do you have access to your git commit timestamps to verify that all development occurred outside work hours?

5. **Did you sign any document at RBC onboarding beyond the offer letter?** Specifically: employee handbook acknowledgment, code of conduct acknowledgment, IT acceptable use policy, confidentiality agreement, or any form that mentions IP, inventions, or intellectual property?

6. **Does RBC have an outside business activity (OBA) policy, and if so, have you read it?** Many banks require employees to disclose and obtain approval for outside employment, directorships, or business activities. Failure to comply could be a separate compliance issue.

7. **Have you ever accessed any RBC internal system, database, wiki, training module, or document that relates to cross-border payments, SWIFT, correspondent banking, or payment processing?** Even incidentally — e.g., as part of training, onboarding, or general browsing of the internal intranet.

8. **What personal devices and accounts were used for all BPI development?** List every device (laptop model, serial if available), every cloud account (AWS, GCP, Azure — registered to personal email), every AI tool account (Claude, GitHub Copilot, etc.), and every code repository hosting account (GitHub personal account). Were any of these ever connected to the RBC network or VPN?

9. **Does your personal laptop have any RBC software installed on it?** VPN client, MDM (mobile device management), monitoring software, RBC email client, etc.?

10. **Have you ever worked from home on your personal laptop while connected to RBC systems on a different device at the same time?** This matters because RBC could argue temporal/spatial overlap between employment duties and BPI development.

11. **Do you have access to your ISP logs or router logs showing device connections?** These could corroborate that your personal development device never connected to RBC infrastructure.

12. **Have you registered any domains, trademarks, or business names related to BPI?** If so, when and using what identity/address?

13. **Do you have any work product from a previous employer or educational institution that relates to cross-border payments, financial technology, or ML-driven risk pricing?** Prior work in the space that predates RBC strengthens the prior-conception narrative.

14. **Have you ever published anything (blog posts, academic papers, social media, forum posts) about cross-border payment systems or fintech?** Pre-employment publications are powerful evidence of independent conception.

15. **Is your RBC employment at-will or does it have a fixed term?** What is the notice period? Is there a garden leave clause? A non-compete clause? A non-solicitation clause?

16. **What is your annual compensation at RBC?** This matters for assessing the enforceability of the IP clause — courts weigh the consideration received against the breadth of restrictions imposed.

17. **Have you ever used your personal phone at work in a way that could show BPI-related activity?** (e.g., checking GitHub notifications, receiving CI/CD alerts, reading BPI-related emails or Slack messages while on RBC premises)

18. **Does anyone at RBC know that you have programming skills or technology expertise?** If your role is purely retail credit management and no one knows you code, this supports the "unrelated to duties" argument. If colleagues know you as "the tech guy," RBC could argue your technical skills were part of why you were hired.

---

## SECTION 2 — IP CLAIM MAP

### Preliminary Note on the RBC Clause

From the founder's offer letter (obtained in prior review):

> *"Anything you conceive, create or produce, whether alone or jointly with others, during your employment in this role or any other you might have later, as well as any improvements or contributions you make, including written documents, drawings, presentations and technologies (collectively, the Work Product), will be the property of Royal Bank of Canada (the Bank)."*

Additionally, the offer letter imposes a **disclosure obligation**: *"You must promptly and fully disclose Work Product to your Employer."*

This is the operative clause. It is **broader than Formulation C** described in the prompt — it covers "anything you conceive, create or produce … during your employment" with no limitation to employer's business, employer resources, or course of employment. It covers "written documents, drawings, presentations and technologies" — which captures code, designs, financial models, and investor materials.

### IP Claim Map

| # | Asset | Possible Owner/Claimant | Legal Theory | Best Argument for Founder | Best Argument for RBC | Key Evidence Needed | Risk Level |
|---|-------|------------------------|-------------|--------------------------|----------------------|---------------------|-----------|
| 1 | **Source code** (existing PRKT2026 repository — Python, Docker, CI/CD, ML pipeline) | RBC (contractual); Founder (factual creator) | Contractual assignment under offer letter clause; *Copyright Act* s.13(3) "course of employment" default; common-law shop right doctrine | (a) Not created in course of employment — different function, different division, different skills; (b) s.13(3) default is narrow ("course of employment"), and this code has zero connection to retail credit management; (c) Personal time, personal equipment, no employer resources — factual creation is entirely independent; (d) The contractual clause may be unconscionably broad under BC employment law | (a) The offer letter clause says "anything you … create … during your employment" — the code was indisputably created during employment; (b) The clause requires no nexus to employer's business; (c) The founder accepted the clause as consideration for employment; (d) The entire git history confirms creation during the employment period; (e) "Create" is broader than "course of employment" in s.13(3) — the contract overrides the statutory default | Offer letter (complete), git commit timestamps vs. work schedule, pre-employment conception evidence, access logs confirming no RBC resource usage | **HIGH** |
| 2 | **Architecture and design documents** (consolidation files, playbooks, briefings, EPIGNOSIS decisions) | RBC (contractual); Founder (factual creator) | Same contractual theory; clause specifically covers "written documents" | Same as #1, plus: architectural decisions reflect domain expertise accumulated over founder's career, not from RBC employment | Clause explicitly covers "written documents" — design docs are written documents created during employment. RBC does not need to prove they are related to its business under this clause. | Same as #1 | **HIGH** |
| 3 | **ML models and training methodology** (C2 model, BIC-pair detection, CVA/PD estimation) | RBC (contractual); Founder (factual creator) | Contractual assignment; clause covers "technologies" | ML models were trained on publicly available data (BIS papers, SWIFT GPI docs, academic research). No RBC proprietary data used. The methodology is based on published academic work. | "Technologies" in the clause covers ML models. Created during employment. Trained using skills the founder exercised during the employment period. | Training data provenance, model development logs, evidence that methodology derives from public sources | **HIGH** |
| 4 | **Pricing logic, rules, and fee constants** (QUANT-controlled parameters, 300bps floor) | RBC (contractual); Founder (factual creator) | Contractual assignment; trade secret if kept confidential | Fee structures and pricing logic derive from public financial mathematics (CVA, PD/LGD), BIS published data, and the founder's own business judgment. No RBC pricing data used. | Created during employment. Pricing logic for financial products is core banking IP. Even if the math is public, the specific calibration and business rules are "improvements or contributions" under the clause. | Source of calibration data, whether any RBC credit models or pricing approaches influenced the design | **HIGH** |
| 5 | **Patentable inventions** (bridging methodology, two-step classification, auto-settlement on UETR confirmation) | RBC (contractual); Founder (common law default: employee owns inventions unless contract says otherwise) | Contractual assignment overriding common-law default; *Patent Act* is silent on employee inventions — common law applies; *Comstock Canada* factors | Under *Comstock Canada v. Electec* (ONCA), the default is that the employee owns inventions. The Comstock factors favour the founder: (a) not hired to invent, (b) personal time/resources, (c) invention unrelated to duties, (d) no fiduciary obligation to invent for RBC. These factors mean the common-law default would assign ownership to the founder absent a valid contractual override. | The contractual clause IS the override. "Anything you conceive … during your employment" covers inventions conceived during the employment period. The clause does not need to use the word "invention" or "patent" — "conceive" and "create" are sufficient. Patent assignment clauses are routinely enforced in Canada. Even if the common-law default favours the founder, the contract supersedes it. | Whether the inventive concept predates employment (the CRITICAL question), enforceability of the clause as applied to inventions unrelated to duties, consideration adequacy | **HIGH** |
| 6 | **Trade secrets and know-how** (domain expertise assembled during prototype development — rejection code taxonomy, corridor risk mapping, BIC-pair failure patterns) | RBC (contractual + possible duty of confidentiality); Founder (factual developer) | Contractual assignment; implied duty of fidelity during employment; *Trade Secrets Act* (if BC enacts one); common-law confidential information doctrine | The know-how was assembled from public sources (BIS, SWIFT GPI, academic papers, regulatory filings). There is no RBC trade secret in cross-border payment failure patterns — this is not information obtained from RBC. The founder's synthesis of public information into a taxonomy is original work. | (a) The clause covers "anything … you conceive, create or produce" — a taxonomy is something created; (b) Even if the inputs are public, the synthesized know-how may be covered by the clause; (c) More dangerously: RBC could argue that the founder's understanding of how banks process payments was enhanced by employment at a bank, even if no specific confidential information was used | Public-source documentation for every element of the taxonomy; evidence that the founder had cross-border payment knowledge before RBC employment | **MEDIUM-HIGH** |
| 7 | **Brand, domain, and company name** ("Bridgepoint Intelligence," "BPI") | Founder (trademark law — first use); RBC (contractual, weakly) | Trademark first use; contractual assignment under "anything you … create" | Brand names and company names are not typically covered by employment IP clauses, which focus on inventions, works, and technologies. "Bridgepoint Intelligence" was created as a personal business identity, not as work product. No RBC association. | Under the literal clause language, a name "created during employment" could theoretically be covered. However, this is an extreme stretch — no court has extended an employment IP clause to cover a personal business name unrelated to the employer. | Domain registration records, any branding work predating employment | **LOW-MEDIUM** |
| 8 | **Clean-room reimplementation** (new code written after resignation, from same inventor) | Founder (post-employment creation); RBC (if contaminated by prior work) | Post-employment works are not covered by the clause (employment has ended); but derivative work doctrine; inevitable disclosure (US — not adopted in Canada) | Clean-room code written after resignation is NOT covered by the "during your employment" clause — the employment has ended. If the reimplementation is based on publicly available specifications and the founder's own general skill and knowledge, RBC has no claim. | (a) If the reimplemented code is substantially similar to the quarantined code, RBC could argue it is a derivative work of code they own; (b) Even post-resignation, if the inventive concepts were "conceived during employment," the patent rights may still be assigned — clean-room only addresses copyright, not patent; (c) The solo-founder problem: the same person who wrote the original code is writing the "clean" version, making it structurally difficult to establish independence | Separation protocol documentation, similarity analysis between old and new code, evidence that clean-room spec was based on public information only | **MEDIUM** |
| 9 | **Future patents derived from current work** (continuation applications, improvements, related inventions in the 15-patent portfolio) | Founder (post-employment); RBC (if priority chain traces back to employment-period conception) | Patent continuation and improvement doctrine; contractual "improvements" clause | Post-resignation patents based on independently developed ideas are outside the clause. The 15-patent portfolio covers diverse aspects of payment bridging — not all were necessarily conceived during employment. | (a) The clause covers "improvements" — any improvement to a concept conceived during employment arguably falls within scope; (b) Continuation patents that claim priority from an employment-period filing create a chain that links back to the covered period; (c) The broader the original claim, the more future patents it potentially captures | Patent claim scope, whether continuation priority dates fall within or after employment | **MEDIUM-HIGH** |
| 10 | **Investor-facing materials** (pitch deck, financial models, valuation analysis, SAFE template, risk disclosure) | Founder (personal business planning); RBC (contractual — "written documents, drawings, presentations") | Contractual assignment — the clause specifically enumerates "written documents" and "presentations" | (a) Investor materials are personal business documents, not technology work product; (b) Extending an IP assignment clause to personal financial planning documents would be unconscionable; (c) No court has held that an employee's personal business plan belongs to the employer simply because it was written during employment | (a) The clause literally covers "written documents" and "presentations" created during employment; (b) These documents describe RBC-claimed technology and its commercialization — they are inseparable from the IP; (c) The financial models embed proprietary market analysis and pricing assumptions | Whether the materials were created on personal time/equipment, whether any RBC information appears in them | **MEDIUM** |
| 11 | **Academic/research work product** (papers, analyses based on public BIS/SWIFT data) | Founder (personal scholarship); RBC (if created during employment) | Contractual assignment; academic freedom (weak — founder is not an academic employee) | Research based on publicly available data is not properly characterized as employer work product. Academic and research freedom, while not a legal defence per se, reflects the public policy concern with over-broad IP assignment. | The clause makes no exception for research. "Anything you … create" includes research papers. If the research was conducted during employment, it falls within the clause. | Dates of research, whether any RBC resources or data were used | **LOW-MEDIUM** |
| 12 | **Data compilations** (BIC-pair databases, rejection code taxonomies, corridor risk data) | Founder (sweat of the brow / original compilation); RBC (contractual) | Contractual assignment; *Copyright Act* compilation copyright; database right (limited in Canada) | Compilations of publicly available data are protectable by copyright only if the selection and arrangement are original (*CCH Canadian v. Law Society of Upper Canada*). The underlying data is public. The compilation effort is the founder's personal work. | The compilation was "created during employment" and falls within the clause. The value is in the selection, arrangement, and synthesis — which are "technologies" and "work product" under the clause. | Source data documentation, evidence of compilation methodology using only public inputs | **MEDIUM** |

### Risk Level Summary

| Risk Level | Assets |
|------------|--------|
| **HIGH** | Source code, architecture docs, ML models, pricing logic, patentable inventions |
| **MEDIUM-HIGH** | Trade secrets/know-how, future derived patents |
| **MEDIUM** | Clean-room reimplementation, investor materials, data compilations |
| **LOW-MEDIUM** | Brand/domain, academic work product |

**Key observation:** The five assets that constitute BPI's core value (code, architecture, models, pricing, inventions) are ALL rated HIGH. This is not a peripheral risk — it strikes at the heart of the venture.

---

## SECTION 3 — EMPLOYMENT AGREEMENT ANALYSIS

### 3.0 The Actual Clause (No Longer a Critical Unknown)

From a prior review of the RBC offer letter (page 3), the actual IP assignment clause reads:

> *"Anything you conceive, create or produce, whether alone or jointly with others, during your employment in this role or any other you might have later, as well as any improvements or contributions you make, including written documents, drawings, presentations and technologies (collectively, the Work Product), will be the property of Royal Bank of Canada (the Bank)."*

Additionally:

> *"You must promptly and fully disclose Work Product to your Employer."*

**This is not Formulation A, B, or C. This is broader than all three.** It is an unqualified assignment of "anything you conceive, create or produce … during your employment" with:
- No limitation to "course of employment"
- No limitation to "related to the employer's business"
- No limitation to "using employer resources"
- No exception for personal time or personal equipment
- An explicit enumeration of "written documents, drawings, presentations and technologies"
- A mandatory disclosure obligation

For completeness, the three-formulation analysis below is retained because it shows how the actual clause compares, and because counsel may argue the clause should be *read as* one of the narrower formulations despite its literal breadth.

### 3.1 Formulation A — Narrow

**"Inventions conceived or reduced to practice in the course of employment or using employer resources."**

**Strongest RBC interpretation:** "Course of employment" includes any activity that draws on skills or knowledge developed or maintained during the employment relationship. The founder's understanding of banking, payments, and risk management — even if not specific to their retail credit role — was "maintained" through bank employment.

**Strongest founder interpretation:** "Course of employment" has a well-defined meaning in Canadian employment law — it means work done as part of one's job duties, during work hours, in furtherance of the employer's objectives. A retail credit officer developing cross-border payment software on personal time has nothing to do with the "course of employment." The founder never used employer resources.

**What a cautious pre-seed investor would assume:** Under this narrow formulation, BPI is likely in the clear. An investor would want confirmation that no RBC resources were used and that the role is genuinely unrelated, but would likely proceed.

**IP rights affected:** Copyright (via s.13(3) default), patent assignment, trade secrets.

**Enforceability:** Strong — this is the default under *Copyright Act* s.13(3) and closely mirrors the common-law position. Courts routinely enforce "course of employment" + "employer resources" clauses.

**Risk to BPI: LOW.** Under this formulation, BPI would almost certainly survive a challenge. The founder was not hired to develop software, did not use RBC resources, and the work is unrelated to retail credit management.

**But this is NOT the actual clause.** The actual clause is far broader.

### 3.2 Formulation B — Medium

**"Inventions or works conceived or developed during the period of employment that relate to the employer's business or anticipated business."**

**Strongest RBC interpretation:** RBC is a Schedule I bank that processes cross-border payments through its correspondent banking network. BPI's technology directly addresses cross-border payment failures — a problem that exists within RBC's business. Even though the founder's role is in retail credit, RBC's *business* includes cross-border payments. "Anticipated business" is even broader — RBC could argue it anticipates expanding its payment technology capabilities (which is true — all major banks are investing in payment innovation).

**Strongest founder interpretation:** "Relates to the employer's business" should be read in context of the employee's role and division, not the entire corporate conglomerate. RBC has >80,000 employees across dozens of business lines. Interpreting "employer's business" as "anything done anywhere at RBC" would mean that no RBC employee could ever innovate in any financial domain on personal time. This is absurd and unenforceable as applied.

**What a cautious pre-seed investor would assume:** The connection to RBC's broader business is concerning. Cross-border payments are part of RBC's operations, even if the founder is in a different division. An investor would likely want a legal opinion before proceeding.

**IP rights affected:** Copyright, patent, trade secrets, potentially confidential information.

**Enforceability:** Moderate — the "relates to employer's business" standard has been interpreted by Canadian courts, but the application to a conglomerate bank employee working in an unrelated division is not well-settled.

**Risk to BPI: MEDIUM-HIGH.** The connection between BPI's domain (cross-border payments) and RBC's business (banking, including cross-border payments) is uncomfortably close, even though the founder's specific role is unrelated.

### 3.3 Formulation C — Broad

**"All inventions, works, improvements, and intellectual property conceived, created, or reduced to practice during the period of employment, regardless of whether created on personal time or using personal resources."**

**Strongest RBC interpretation:** The clause means exactly what it says — everything created during employment belongs to RBC, regardless of time, resources, or business connection. The founder signed the contract with full knowledge and received employment as consideration. This is not unconscionable — it is a standard term in employment at a major bank.

**Strongest founder interpretation:** (a) This clause is unconscionably broad under BC employment law — it effectively claims ownership of an employee's entire creative output, including hobbies, personal writing, and non-work inventions. No BC court has enforced a clause this broad against an employee working in an unrelated field on personal time. (b) The clause fails for lack of consideration if applied to personal-time inventions — the employment salary was consideration for work performed during work hours, not for the employee's entire creative life. (c) Public policy militates against enforcement — if this clause were enforceable as written, it would prevent all 80,000+ RBC employees from any creative or inventive activity during their employment. (d) Under *Techform Products v. Wolda* (ONCA 2001), courts look at the substance of the employment relationship, not just the contract language, when assessing the reasonableness of restrictive covenants.

**What a cautious pre-seed investor would assume:** This is a deal-blocker until resolved by counsel. No sophisticated investor would proceed without a legal opinion on enforceability.

**IP rights affected:** All — copyright, patent, trade secrets, moral rights waiver (if clause includes moral rights), database rights.

**Enforceability:** Uncertain — the clause is maximally broad, which actually makes it more vulnerable to challenge. Canadian courts have shown increasing skepticism toward over-broad restrictive covenants in employment (*Shafron v. KRG Insurance Brokers*, SCC 2009 — though that case addressed non-competes, the principle of reading restrictive covenants strictly against the drafter applies). However, there is no direct Canadian authority striking down a blanket IP assignment clause in the banking context.

**Risk to BPI: HIGH.**

### 3.4 The Actual RBC Clause — Broader Than C

The actual clause is essentially Formulation C with specific enumeration. Key features that make it even broader than the generic Formulation C:

1. **"Anything you conceive, create or produce"** — "Conceive" captures ideas that haven't been reduced to code. "Anything" is maximally inclusive.

2. **"Whether alone or jointly with others"** — Covers both solo and collaborative work. This is standard but comprehensive.

3. **"During your employment in this role or any other you might have later"** — Extends to future roles at RBC, ensuring promotion or transfer doesn't escape the clause.

4. **"As well as any improvements or contributions you make"** — "Improvements" captures derivative works and future enhancements. "Contributions" is vague and broad.

5. **"Including written documents, drawings, presentations and technologies"** — The enumeration specifically captures the exact types of artifacts BPI has produced: written documents (architecture docs, financial models, investor materials), presentations (pitch materials), and technologies (code, ML models).

6. **Mandatory disclosure obligation** — "You must promptly and fully disclose Work Product to your Employer." The founder has NOT disclosed BPI to RBC, creating an independent contractual breach.

**Strongest RBC interpretation under actual clause:**
- The clause is unambiguous. "Anything you conceive, create or produce during your employment" means what it says.
- BPI's entire technology stack — code, models, methods, documents, financial analyses — was created during the employment period.
- The founder failed to comply with the mandatory disclosure obligation, which is an independent breach.
- RBC is entitled to ownership of all Work Product and can demand its delivery.

**Strongest founder interpretation under actual clause:**
- The clause is unconscionably broad as applied to this fact pattern. No BC court has enforced a "anything you create during employment" clause against:
  - An employee in a completely unrelated role (retail credit vs. payment technology)
  - Working exclusively on personal time with personal equipment
  - On a project with zero connection to their job duties
  - In a field they had expertise in before the employment began
- The clause lacks adequate consideration for its breadth — the salary compensated job duties, not the employee's entire creative output.
- Applying the *Comstock* factors: (a) not hired to invent, (b) invention completely unrelated to job duties, (c) personal time and resources, (d) no fiduciary obligation to innovate for RBC in this domain.
- The clause may be severable — a court could read it down to "course of employment" rather than void it entirely, and BPI falls outside "course of employment."
- The *Techform* principle of examining the substance of the employment relationship supports a narrow reading.
- **Public policy argument**: If enforceable as written, this clause would prevent every RBC employee from writing a novel, composing music, inventing a kitchen gadget, or developing any personal project during their employment. This cannot be the law.

**What a cautious pre-seed investor should assume:** The literal clause language favours RBC. Until a qualified lawyer opines on enforceability, **assume the clause is enforceable as written.** This is the conservative planning assumption.

### 3.5 Planning Assumption

**Assume the clause is enforceable as written until counsel advises otherwise.**

This means:
- RBC has a **contractual claim** to all BPI work product
- The founder is in **breach of the disclosure obligation**
- The strength of the claim is untested (no case directly on point)
- The enforceability challenge is real but uncertain
- **No fundraising, patent filing, or incorporation should proceed until this is resolved**

---

## SECTION 4 — LEGAL ISSUE DEEP DIVE

### Question 1: Could RBC claim ownership of the existing codebase under copyright law?

**Short answer:** Yes, under two independent theories — and the contractual theory is the stronger one. Under the statutory default (*Copyright Act* s.13(3)), RBC would struggle because the code was not created "in the course of employment." But the offer letter clause contractually assigns "anything you … create … during your employment," which overrides the statutory default and covers the code.

**Full analysis:**

*Statutory route — Copyright Act s.13(3):*

Section 13(3) of the *Copyright Act* provides: "Where the author of a work was in the employment of some other person under a contract of service or apprenticeship and the work was made in the course of his employment by that person, the employer shall, in the absence of any agreement to the contrary, be the first owner of the copyright."

The key phrase is "in the course of his employment." Canadian courts have interpreted this narrowly — it means work done as part of the employee's job duties, during working hours, in furtherance of the employer's objectives. (*University of British Columbia v. Berg*, BCSC 1993; *Netupsky v. Dominion Bridge Co.*, ONCA 1969).

Under this standard, BPI's code was NOT created "in the course of employment." The founder's employment is retail credit management. Writing a cross-border payment bridging platform is not part of the founder's job duties, was not done during working hours, and was not in furtherance of RBC's retail credit objectives.

However, s.13(3) includes the phrase "in the absence of any agreement to the contrary." This means a contractual provision can override the default.

*Contractual route — the offer letter clause:*

The RBC clause assigns "anything you conceive, create or produce … during your employment." This IS an "agreement to the contrary" under s.13(3). If the clause is enforceable, it overrides the statutory default and assigns copyright in BPI's code to RBC regardless of whether the code was created "in the course of employment."

The critical question is therefore not whether the code falls under s.13(3), but whether the contractual override is enforceable as applied to this fact pattern. This is the question for counsel.

*AI-generated code complication:*

A significant portion of BPI's code was generated using AI tools (the "Ford model"). The copyright status of AI-generated code in Canada is unsettled. If portions of the code are not copyrightable (because they were generated by AI, not authored by a human), then there may be no copyright for RBC to claim. However, the founder's selection, arrangement, and curation of AI-generated code likely constitutes sufficient human authorship for copyright. And the contractual clause is not limited to copyrightable works — it covers "anything you … create," which is broader than copyright.

**Key fact dependencies:**
- Enforceability of the offer letter clause as applied to personal-time, unrelated work (THE critical question)
- Proportion of code that is AI-generated vs. human-authored
- Whether any code predates the employment period (currently: no evidence of this)

### Question 2: Could RBC claim ownership of the underlying inventions even if the code is entirely rewritten?

**Short answer:** Yes. This is the most dangerous aspect of the risk. Copyright protects expression; patents protect inventions. Even a complete code rewrite does not address RBC's claim to the inventive concepts conceived during the employment period. If the bridging methodology, two-step classification, or auto-settlement approach was "conceived" during employment, the contractual clause assigns the *invention* to RBC, not just the code.

**Full analysis:**

The *Patent Act* (Canada) is silent on employee inventions. The common-law default, as articulated in *Comstock Canada v. Electec Ltd.* (1991, ONCA), is that the employee owns inventions made during employment unless:
1. The employee was hired to invent, or
2. There is a contractual provision assigning inventions to the employer.

The RBC clause satisfies condition (2) — it assigns "anything you conceive … during your employment." "Conceive" is the operative word for inventions. If the core inventive concepts were conceived after January 12, 2026, RBC has a contractual claim to the inventions regardless of who writes the code.

This means:
- **Clean-room reimplementation addresses copyright but NOT patent risk.** A new codebase may be free of RBC's copyright claim, but the inventions it implements may still be claimed by RBC.
- **The patent filing creates a public record** that documents the inventive concepts — which RBC could then point to as Work Product conceived during employment.
- **The inventions must have been conceived before employment** for the founder to have a clear claim. This is why pre-employment evidence is the single most important factual issue.

*The Comstock factors:*

Even with a contractual clause, the *Comstock* factors inform the enforceability analysis:
1. **Was the employee hired to invent?** No — hired as a credit management resolution officer.
2. **Did the employee use employer resources?** No — personal equipment and time.
3. **Is the invention related to the employer's business?** This is the weak point — RBC is a bank that processes cross-border payments, even though the founder's role is unrelated.
4. **Did the employee have a fiduciary obligation to invent for the employer?** No — retail credit officers have no such obligation.

Factors 1, 2, and 4 strongly favour the founder. Factor 3 is ambiguous and is the one RBC would exploit.

**Key fact dependencies:**
- Whether the core inventive concepts were conceived before January 12, 2026 (THE critical question)
- Whether "conceived" in the RBC clause has the same meaning as "conception" in patent law (reduction to a definite and permanent idea, as opposed to a vague notion)
- The exact scope of what is claimed as "inventive" — the broader the patent claims, the more likely some element was first conceived during employment

### Question 3: Could RBC block, oppose, or complicate a patent filing — and would they have standing to do so?

**Short answer:** Yes to all three, with different mechanisms and different thresholds. Blocking is difficult without litigation; opposing is straightforward if they discover the filing; complicating is almost certain once they learn of it.

**Full analysis:**

*Blocking a filing:*

RBC cannot prevent the founder from physically filing a patent application. The Patent Office does not verify ownership at the filing stage. However, if RBC learns of the filing, they could:
1. Send a cease-and-desist letter claiming ownership
2. File a statement of claim in court seeking a declaration that they own the invention
3. Seek an interim injunction preventing prosecution or assignment of the application

An interim injunction would require RBC to demonstrate a serious issue to be tried, irreparable harm, and balance of convenience — a moderate threshold that they could potentially meet if the clause language is as broad as it is.

*Opposing a filing:*

Under Canadian patent procedure, there is no formal opposition process during prosecution (unlike trademarks). However, RBC could:
1. Submit prior art to the Patent Office
2. Initiate *inter partes* proceedings in the US (if a US patent is filed) under AIA procedures
3. Challenge the patent post-grant through Federal Court proceedings

*Complicating a filing:*

This is the most likely outcome. RBC does not need to win — they only need to create uncertainty. A letter from RBC's legal department claiming ownership of the IP would:
1. Create a title defect that must be disclosed to any investor
2. Potentially trigger the inventor's duty of candor in patent prosecution
3. Make it impossible to cleanly assign the patent to a new corporate entity
4. Provide ammunition for any investor's due diligence counsel to flag a "do not proceed"

*Standing:*

RBC has standing if they can point to the contractual clause assigning IP created during employment. They do not need to prove the clause is enforceable at the standing stage — they only need to show a colourable claim. The clause as written provides this.

**Key fact dependencies:**
- Whether RBC discovers the patent filing (provisional filings are not published for 18 months; but the patent filing creates discoverable records)
- RBC's litigation appetite (see Section 9 for analysis)
- Whether the founder has resigned before filing (filing while employed is more provocative than filing after resignation)

### Question 4: Could RBC claim the founder used confidential information, trade secrets, or internal know-how even if no code was copied and no RBC systems were accessed?

**Short answer:** This is the argument RBC would *want* to make because it is harder to disprove than code-copying. However, it is also the weakest claim on the facts — the founder works in retail credit management and has no access to cross-border payment systems. The "know-how osmosis" argument requires RBC to show that the founder learned something from RBC that was both confidential and material to BPI. On the stated facts, this is difficult.

**Full analysis:**

The confidential information claim has three elements:
1. The information must be confidential (not publicly available)
2. It must have been communicated in circumstances of confidence (e.g., during employment)
3. There must be unauthorized use or disclosure

*The "osmosis" argument:*

RBC's most sophisticated argument would be: "Even if the founder never accessed cross-border payment systems directly, working at a major bank creates exposure to institutional knowledge about payment processing, risk management frameworks, regulatory approaches, and operational practices. This exposure — absorbed through training, internal communications, cultural immersion, and proximity — informed the development of BPI."

This argument is weak on the stated facts because:
- The founder works in **retail credit management**, a completely different business line
- The founder has **no access** to cross-border payment, SWIFT, or correspondent banking systems
- The founder has **not discussed** BPI with any RBC colleague
- Cross-border payment bridging uses **publicly available** information (BIS papers, SWIFT GPI documentation, ISO 20022 standards)

However, the argument becomes dangerous if:
- The founder ever accessed any internal RBC material about payments (even incidentally)
- The founder attended any training that covered correspondent banking
- RBC can show that any element of BPI's design mirrors RBC's internal processes

*The "duty of fidelity" angle:*

During employment, employees owe a common-law duty of fidelity to their employer. This includes not competing with the employer during employment and not diverting business opportunities. RBC could argue that developing BPI while employed — even on personal time — is a breach of this duty, especially given that BPI targets banks as customers.

This is distinct from the IP ownership claim — it is a breach of duty claim that could support damages even if IP ownership is not established.

**Key fact dependencies:**
- Whether the founder ever accessed any RBC material related to payments (even training modules)
- Whether any element of BPI's design reflects non-public banking practices
- Whether the duty of fidelity extends to developing a product for a different market than the employee's role

### Question 5: Does the fact that the entire git history falls within the employment period materially worsen the position compared to having pre-employment commits?

**Short answer:** Yes, materially. This is one of the most damaging facts in the entire analysis. It creates a rebuttable presumption that the work was "created during employment" — which is exactly the trigger for the RBC clause.

**Full analysis:**

The git history is the **primary documentary evidence** of when BPI was created. In any IP dispute, timelines matter enormously. The current timeline tells a story that is devastating for the founder:

- January 12, 2026: Employment begins
- January 12, 2026 – March 23, 2026: All 1,476 tests worth of code, all architecture, all ML models, all financial models, all investor materials created
- Zero pre-employment artifacts exist in the repository

A reasonable factfinder (judge or arbitrator) would conclude: "The entire system was conceived and created during the RBC employment period."

*How pre-employment commits would change this:*

If the repository had commits from December 2025 showing the core architecture, the bridging concept, and early ML model design, the narrative shifts dramatically:
- "The core concepts predate the employment. The employee continued to develop a pre-existing personal project during employment, on personal time, using personal resources."
- The "conceived during employment" trigger in the RBC clause would not apply to concepts that demonstrably predate employment.
- The remaining question would be whether the improvements made during employment are separable.

*What can be done now:*

The git history cannot be retroactively changed (and any attempt to do so would be discoverable and devastating to credibility). However:
1. **External corroboration** of pre-employment conception (emails, notes, conversations) could rebut the presumption.
2. **The AI development methodology** may help — if the founder can show that the "Ford model" approach means 10 weeks is consistent with building this system from a pre-existing concept using AI acceleration, the timeline becomes less suspicious.
3. **The founder should NOT rewrite git history, backdate commits, or fabricate evidence.** This would be discoverable, would destroy credibility, and could constitute fraud.

**Key fact dependencies:**
- Existence and strength of pre-employment conception evidence (THE critical variable)
- Whether the commit timestamps correlate exclusively with non-work hours (supporting the personal-time claim)
- Whether the AI-assisted development model explains the rapid build timeline

### Question 6: Under Canadian law, how much does it matter that the founder built it on personal time, personal equipment, with no use of employer resources?

**Short answer:** It matters significantly but is not dispositive. Under the common-law defaults and *Copyright Act* s.13(3), personal time/equipment would likely mean the founder owns the work. But the contractual clause explicitly overrides these defaults by claiming "anything … during your employment" without limiting to employer resources. The personal time/equipment facts are relevant to the *enforceability* challenge — a court deciding whether the clause is unconscionably broad would weigh these facts heavily in the founder's favour.

**Full analysis:**

*Why it matters:*

1. **Common-law default:** The *Comstock* factors include "did the employee use employer resources?" This factor favours the founder and would be determinative absent a contractual override.

2. **Enforceability challenge:** If the founder challenges the breadth of the clause, personal time/equipment is the strongest equitable argument. A court would ask: "Is it reasonable to assign ownership of work created entirely on the employee's own time, with their own equipment, in a field unrelated to their employment?"

3. **Factual credibility:** Personal time/equipment makes the founder's narrative more sympathetic. A factfinder is more likely to find the clause unconscionable if the founder demonstrably received no benefit from the employment relationship in creating BPI.

*Why it is not dispositive:*

1. **The contract says what it says.** The clause does not limit itself to employer-resource creations. If the clause is enforceable, personal time/equipment does not defeat RBC's claim.

2. **No Canadian equivalent to California s.2870.** In California, there is a statutory provision (*Labour Code* §2870) that renders unenforceable any employer claim to inventions made on the employee's own time, with the employee's own equipment, and unrelated to the employer's business. **Canada has no equivalent statute.** This is a critical gap — the US "safe harbour" for personal-time inventions does not exist in Canadian law.

3. **The precedent gap.** There is no reported Canadian case that directly addresses the enforceability of a blanket IP assignment clause (like RBC's) as applied to an employee working in an unrelated field on personal time. The outcome is genuinely uncertain.

**Key fact dependencies:**
- Ability to prove personal time/equipment with documentary evidence (git timestamps, device logs, cloud access logs)
- Whether the clause is found enforceable as written or read down by a court
- Whether any incidental employer resource use undermines the claim (e.g., ever checking BPI-related email on a work break)

### Question 7: How much does it matter whether the startup concept overlaps with RBC's actual or reasonably contemplated business?

**Short answer:** It matters enormously — this is the swing factor. If BPI's domain is found to "relate to RBC's business," even a court that narrows the clause would likely keep BPI within scope. If BPI is found to be in a genuinely different domain, the unconscionability/read-down argument becomes much stronger. The problem is that RBC is a bank and BPI targets banks — the connection is real even if the founder's specific role is unrelated.

**Full analysis:**

*The overlapping layers:*

1. **Founder's role vs. BPI's domain:** No overlap. Retail credit management (collections, workouts, forbearance) has nothing to do with cross-border B2B payment bridging. Different customers, different products, different systems, different skills, different division.

2. **Founder's division vs. BPI's target market:** Minimal overlap. Retail banking and institutional/correspondent banking are separate business lines with separate P&Ls.

3. **RBC's corporate business vs. BPI's domain:** Significant overlap. RBC processes cross-border payments. RBC has a correspondent banking operation. RBC is, in fact, a potential BPI customer (the go-to-market strategy targets RBCx). This connection is the foundation of RBC's strongest argument.

4. **RBC's "anticipated business" vs. BPI's innovation:** Potentially high overlap. All major banks are investing in payment technology, AI/ML for risk management, and cross-border payment optimization. RBC could argue that BPI's approach is within its "anticipated business" — meaning the R&D frontier RBC is exploring.

*The "department vs. conglomerate" question:*

The legal question is whether "employer's business" means:
- (a) the business of the department/role in which the employee works, or
- (b) the entire business of the corporate employer

If (a), BPI is clearly outside scope. If (b), BPI has substantial overlap with RBC's corporate activities.

Canadian courts have not definitively resolved this for IP assignment purposes. In non-compete cases, courts have tended toward a narrower reading (*Shafron*), but non-compete analysis is not directly transferable to IP assignment analysis.

*The dual-nature problem:*

The fact that RBC is both a potential IP claimant AND a potential BPI customer is uniquely dangerous. If the founder approaches RBC as a vendor (Angle 6), RBC's internal assessment will immediately flag the IP question. "Our former employee built a product that relates to our payment operations and now wants to sell it to us" is a narrative that RBC's legal department would not overlook.

**Key fact dependencies:**
- Whether the clause contains "relates to the employer's business" language (the actual clause does NOT — it has no business-nexus requirement at all, which makes this question relevant only to the enforceability challenge)
- Whether RBC has any internal innovation initiatives in cross-border payment bridging
- Whether the founder's approach to RBC as vendor (Angle 6) triggers the IP review

### Question 8: If the founder incorporates BPI now (while still employed at RBC), does that create additional legal exposure?

**Short answer:** Yes, on multiple fronts. Incorporating while employed creates a paper trail documenting the founder's intent to commercialize work allegedly covered by RBC's IP clause. It may also violate the outside business activity policy and the common-law duty of fidelity.

**Full analysis:**

1. **Outside business activity:** If RBC has an OBA policy (virtually all Schedule I banks do), incorporating a company without disclosure may be a violation. This is not an IP issue per se, but it gives RBC disciplinary grounds and undercuts the founder's "good faith" narrative.

2. **Duty of fidelity:** Incorporating a company in a domain that overlaps with the employer's business — while employed — could be characterized as preparation to compete. The common-law duty of fidelity is generally interpreted to prohibit an employee from actively competing during employment, though preparation (such as planning) is permissible. Incorporation may cross the line from "planning" to "active preparation to compete."

3. **Assignment chain:** If the founder incorporates and then assigns IP to the corporation, this creates a chain of title that RBC could attack. RBC could argue: "The founder assigned our IP to a shell corporation without our consent."

4. **S.85 rollover implications:** The planned s.85 rollover is premised on the founder having clear title to the IP being rolled into the corporation. If the IP is encumbered by RBC's claim, the rollover is defective.

**Recommendation:** Do NOT incorporate until after IP counsel has provided an opinion. The incorporation can be completed in days once the IP question is resolved.

**Key fact dependencies:**
- Whether RBC has an OBA policy and whether incorporation triggers it
- Whether the s.85 rollover requires clean title to IP (it does)
- Timing of resignation relative to incorporation

### Question 9: If the founder raises F&F money before obtaining an IP lawyer opinion, what specific legal and ethical risks arise?

**Short answer:** This is ethically indefensible and legally risky. Taking money from friends and family while knowing that the foundational IP may not belong to you — and without having engaged a lawyer to assess this — creates potential liability under securities law, common law fraud/misrepresentation, and the founder's personal relationships.

**Full analysis:**

*Securities law risk:*

Under NI 45-106, the s.2.5 family, friends, and business associates exemption requires that investors be provided with sufficient information to make an informed investment decision. While s.2.5 does not mandate specific disclosure documents, the common-law duty of honest dealing applies. If the founder knows of a material risk (the IP clause) and does not adequately disclose it, this could constitute a misrepresentation.

The existing risk disclosure document (Section 2.2) DOES disclose the RBC IP risk — this is good. However, it describes the clause as a "broad intellectual property assignment clause" without stating the actual clause language. Now that the actual language is known, the disclosure should be updated to include it verbatim.

More critically, the disclosure states: "The Company cannot assess the probability of any of these outcomes until an IP lawyer has reviewed the specific language of the RBC employment agreement." But the founder now HAS the specific language. This creates an obligation to either (a) update the disclosure with the actual language and the founder's own assessment, or (b) engage the lawyer first.

*Ethical risk:*

Friends and family investors trust the founder personally. Taking their money while knowing the IP may be owned by RBC — and without having spent the relatively modest amount ($5K–$10K) to get a legal opinion — is ethically problematic even if legally defensible. These investors are not sophisticated — they are investing based on personal trust. Asking them to fund the legal opinion that might reveal the venture is non-viable is asking them to take a risk the founder should bear personally.

*Practical risk:*

If the IP lawyer subsequently advises that the IP is owned by RBC, the founder would need to either:
- Return the F&F money (triggering personal financial stress and relationship damage)
- Proceed with clean-room reimplementation (meaning the investors funded a legal opinion that says the existing work has to be abandoned)
- Attempt to negotiate with RBC (from a position of weakness, having already taken money)

None of these outcomes are made better by having taken F&F money prematurely.

**Conclusion: Do not raise F&F money before obtaining an IP lawyer opinion.** Self-fund the lawyer engagement ($5K–$10K). This is the most important pre-fundraising expenditure.

**Key fact dependencies:**
- The adequacy of the existing risk disclosure (it needs to be updated)
- Whether the founder can self-fund the $5K–$10K lawyer engagement
- The sophistication of the F&F investors

### Question 10: Under what conditions would clean-room reimplementation materially reduce risk, and under what conditions would it be insufficient or unnecessary?

**Short answer:** Clean-room reduces copyright risk significantly but does NOT address patent/invention ownership risk. It is most valuable when counsel advises that the clause is likely enforceable for code ownership but the inventive concepts are arguably pre-employment. It is insufficient when the inventive concepts themselves (not just the code) are claimed by RBC. It is unnecessary only if counsel provides a clear opinion that the clause is unenforceable as applied.

**Full analysis:**

*When clean-room helps:*

1. **Copyright claim mitigation:** If RBC owns the copyright in the existing code (under the clause), a clean-room reimplementation creates new code with new copyright owned by the post-resignation founder. This is the classic purpose of clean-room development (*Sega v. Accolade* (9th Cir. 1992), *Sony v. Connectix* (9th Cir. 2000)). These are US cases, but the principle of independent creation as a defence to copyright infringement is recognized in Canadian law.

2. **Practical risk reduction:** Even if not legally required, a clean-room rewrite demonstrates good faith, creates distance from the employment-period code, and shows investors that the company's technology is not encumbered.

3. **Negotiation leverage:** If RBC comes knocking, the founder can say: "We discarded the employment-period code. Our current product is independently created." This makes RBC's claim more expensive to pursue and less likely to succeed.

*When clean-room is insufficient:*

1. **Invention ownership:** If RBC's claim extends to the inventive concepts (not just the code), clean-room reimplementation of those same concepts doesn't help. You're implementing RBC's claimed invention with new code — the patent assignment survives the rewrite.

2. **Trade secret contamination:** If the founder's knowledge includes RBC confidential information (even allegedly), the same knowledge would contaminate the clean-room process. You can't "clean-room" your own brain.

3. **Solo founder structural problem:** Traditional clean-room requires separation between "dirty room" (people who analyze the original work) and "clean room" (people who build the new version). With a solo founder, the same person is in both rooms. This structurally undermines the defence. Modified approaches exist (see Section 5) but they are less robust.

*When clean-room is unnecessary:*

1. **Counsel opines clause is unenforceable** as applied to this fact pattern — no need to rewrite if the existing code is not encumbered.
2. **Strong pre-employment conception evidence** establishes that the core work predates employment — the clause's "during your employment" trigger is defeated on the facts.
3. **RBC provides a release** — negotiated or obtained through the resignation process.

**Key fact dependencies:**
- Whether RBC's claim extends to inventive concepts (patent) vs. only code (copyright)
- The enforceability of the clause
- The availability and strength of pre-employment conception evidence
- The feasibility of a modified clean-room protocol for a solo founder

### Question 11: If RBC discovers the patent filing, what is their most likely response — and what is their most dangerous response?

**Short answer:** Most likely response is a formal letter asserting ownership. Most dangerous response is a Federal Court action seeking a declaration of ownership plus an injunction against prosecution.

**Full analysis:**

*How RBC might discover it:*

1. **Patent publication:** Provisional filings are not published, but non-provisional applications are published at 18 months. RBC has sophisticated IP monitoring tools (as do all Schedule I banks).
2. **Pre-seed investor diligence:** If BPI raises a pre-seed round, the investors' lawyers may discover the RBC connection.
3. **Vendor due diligence:** If BPI approaches RBC (Angle 6), RBC's vendor onboarding process would identify the founder as a former employee.
4. **Media coverage:** Any press or publicity about BPI could reach RBC employees.
5. **LinkedIn/professional network:** The founder's professional network overlaps with banking.

*Most likely response (70% probability estimate):*

1. RBC's legal department sends a formal letter asserting IP ownership under the offer letter clause.
2. The letter demands: (a) disclosure of all Work Product as required by the clause, (b) assignment of any filed patent applications, (c) cessation of unauthorized commercialization.
3. This letter is designed to create leverage for negotiation, not necessarily litigation.
4. RBC offers: license back to the founder for a royalty, or assignment for a one-time payment.

*Most dangerous response (15% probability estimate):*

1. RBC files a statement of claim in Ontario Superior Court or Federal Court seeking: (a) declaration that BPI's IP is RBC property, (b) assignment of all patent applications, (c) injunction against further development or commercialization, (d) accounting of profits.
2. RBC simultaneously sends a litigation hold notice to the founder and any investors.
3. This response is most likely if: (a) the founder is perceived as having acted in bad faith (concealed the project, violated disclosure obligations, raised money on RBC's IP), or (b) an RBC innovation team has a competing initiative and BPI is seen as a threat.

*Least likely response (15% probability estimate):*

RBC does nothing — either because they never discover it, or because the cost of pursuing a retail credit officer's personal project exceeds the expected return. (See Question 6 in Section 9 for further analysis.)

**Key fact dependencies:**
- RBC's awareness timeline (when they discover, not if)
- Whether the founder is perceived as having acted in good faith
- Whether any RBC team has a competing initiative
- The economic value at stake (higher value = more likely to pursue)

### Question 12: Could RBC claim that the financial models, business strategy documents, and investor materials are covered by the IP clause?

**Short answer:** Yes, on the literal clause language. The clause covers "written documents" and "presentations" created during employment. Financial models and investor presentations are written documents. However, this is the weakest part of RBC's potential claim — no court has extended an employment IP clause to personal business planning documents, and doing so would be an extraordinary reach.

**Full analysis:**

The clause literally covers "written documents, drawings, presentations and technologies (collectively, the Work Product)." Financial models, pitch decks, valuation analyses, and SAFE templates are "written documents." The literal clause captures them.

However, practical considerations counsel against RBC pursuing this:
1. The financial models describe the commercialization of the technology — they have no value to RBC without the technology itself.
2. The valuation analysis and SAFE templates are standard financial instruments, not proprietary work product.
3. Pursuing this claim would make RBC look absurd in court — "we own our employee's personal investment spreadsheet because they wrote it while employed at our bank."
4. The precedent risk for RBC is high — if they win this argument, it implies that any RBC employee's personal financial planning belongs to RBC.

**Practical assessment:** While theoretically covered, this is unlikely to be pursued and even less likely to succeed. Counsel should be aware of it but should not spend significant time on it.

**Key fact dependencies:**
- Whether the business strategy documents contain any information derived from RBC (market data, competitor analysis that references internal knowledge)
- Whether RBC pursues a maximalist legal strategy or a targeted one

### Question 13: What is the statute of limitations for RBC to bring a claim, and does the clock start at creation, discovery, resignation, patent publication, or commercial launch?

**Short answer:** Under the BC *Limitation Act*, the basic limitation period is **2 years from the date of discovery** of the claim, with an **ultimate limitation period of 15 years from the act or omission giving rise to the claim**. The clock for the basic period likely starts when RBC discovers (or reasonably ought to discover) the existence of BPI and the potential IP claim. The clock for the ultimate period starts when the Work Product was created — meaning RBC has up to 15 years from creation, regardless of when they discover it.

**Full analysis:**

*BC Limitation Act, S.B.C. 2012, c. 13:*

- **Basic limitation period (s. 6(1)):** 2 years from the date on which the claim is "discovered." A claim is "discovered" when the claimant knew or reasonably ought to have known that (a) injury, loss, or damage occurred, (b) it was caused by an act or omission of the defendant, and (c) a court proceeding would be an appropriate remedy.

- **Ultimate limitation period (s. 21(1)):** 15 years from the "act or omission" on which the claim is based.

*Application to RBC's potential claim:*

| Triggering Event | Basic Period Starts | Ultimate Period Starts |
|-----------------|--------------------|-----------------------|
| Code creation (Jan–Mar 2026) | No (RBC doesn't know yet) | **Yes — 15-year clock running since first commit** |
| Founder resignation | Possibly (RBC may investigate upon resignation) | No (resignation is not the act giving rise to the claim) |
| Patent filing | Possibly (if RBC discovers the filing) | No |
| Patent publication (18 months post-filing) | Likely (RBC has IP monitoring) | No |
| Commercial launch | Very likely (public visibility) | No |
| RBC discovery (however it occurs) | **Yes — 2-year clock starts** | N/A |

*Key implications:*

1. **The 15-year ultimate period means RBC could bring a claim as late as 2041** (15 years after the first commits in early 2026). This is an extraordinarily long tail risk.
2. **The 2-year basic period is triggered by discovery.** If RBC discovers BPI in 2028 (e.g., at patent publication), they have until 2030 to sue. If they discover it in 2035, they have until 2037 — as long as it's within the 15-year ultimate period.
3. **There is no "safe" date** after which the founder can assume RBC will not bring a claim, short of the ultimate limitation expiring.
4. **This is a long-tail risk for investors.** Even if BPI raises a Series A and achieves product-market fit, the RBC claim could surface years later and threaten the company's IP foundation.

*Ontario limitation considerations:*

If RBC brings the claim in Ontario (its headquarters), the Ontario *Limitations Act, 2002* has a similar 2-year basic / 15-year ultimate structure. The forum does not materially change the analysis.

**Key fact dependencies:**
- When RBC discovers BPI (the trigger for the 2-year basic period)
- Whether RBC is deemed to have "reasonably ought to have known" at resignation
- Whether the ultimate period runs from first creation or from each subsequent act (e.g., each new commit)

### Question 14: If the founder proceeds with Angle 6 (resign → patent → approach RBC as vendor), could RBC argue that the founder is commercializing their IP back to them?

**Short answer:** Yes, and this is the most ironic and dangerous aspect of Angle 6. RBC's argument would be: "Our former employee conceived and developed this technology during his employment at our bank, in breach of his IP assignment obligations, and is now trying to sell it back to us." This narrative is reputationally devastating even if legally defensible.

**Full analysis:**

*RBC's argument:*

"The founder built BPI during his RBC employment, using knowledge and insights gained from working at a major bank. The IP clause in his offer letter assigns this work to RBC. Instead of disclosing it as required, the founder resigned, incorporated, raised money from family and friends, filed a patent on our property, and then had the audacity to try to sell it to us. This is a textbook case of employee misappropriation of corporate IP."

This argument is powerful because:
1. It is simple and intuitively compelling to a judge or arbitrator
2. The narrative of "selling our own IP back to us" is uniquely provocative — it combines IP theft with commercial exploitation
3. It triggers not just the IP clause but also the duty of fidelity and the disclosure obligation
4. It gives RBC maximum institutional motivation to pursue the claim (both to recover the IP and to send a message to other employees)

*Why Angle 6 is still the best option despite this risk:*

The alternative angles are worse:
- Angle 1–3 (raise/incorporate/file before resolving IP) create securities law exposure and investor trust problems
- Angle 4 (clean-room first without legal guidance) may be unnecessarily costly if the clause is unenforceable
- Angle 5 (lawyer first → clean-room if needed → raise → patent) is the correct order of operations and is essentially Angle 6 with the legal opinion gating everything

**The modification to Angle 6 should be:** Resign → IP lawyer opinion → clean-room if recommended → patent → incorporate → raise → approach RBC. The lawyer opinion gates everything else.

*RBC's dual incentive:*

RBC is simultaneously:
1. A potential claimant (IP rights under the clause)
2. A potential customer (the go-to-market strategy targets RBCx)

These incentives may conflict. If BPI's technology is genuinely valuable, RBC might prefer to license it cheaply (using the IP claim as leverage for a favourable license) rather than litigate. This is the optimistic negotiation scenario.

But it could also go the other way: RBC could claim the IP, build the product internally with the founder's work as a head start, and owe nothing. This is the worst case.

**Key fact dependencies:**
- Whether BPI's technology has genuine commercial value to RBC's correspondent banking division
- Whether RBC has any internal initiative in the same space
- The personality and priorities of the RBC personnel who handle the vendor relationship vs. the legal department
- Whether the founder can establish a pre-employment conception story that blunts the "stole our IP" narrative

---

## SECTION 5 — CLEAN-ROOM STRATEGY

### 5.1 Should Clean-Room Be the Default Assumption?

**Yes.** Given:
- The actual clause language is maximally broad
- The entire git history falls within the employment period
- No pre-employment evidence has been assembled
- No legal opinion has been obtained
- The inventions, not just the code, may be claimed

The founder should **assume clean-room will be recommended** until counsel advises otherwise. Planning for it costs nothing; being unprepared for it could cost weeks.

However, the clean-room should not be executed until counsel advises. If counsel's opinion is favourable ("clause likely unenforceable as applied"), the clean-room is unnecessary overhead.

### 5.2 Quarantine Protocol

The following artifacts from PRKT2026 must be quarantined:

| Artifact | Quarantine Action | Access Restriction |
|----------|------------------|--------------------|
| Git repository (PRKT2026) | Archive as read-only; create cryptographic hash of complete state | **Dirty room only** — not accessible during clean-room development |
| All source code | Included in repository quarantine | Same |
| ML model weights and training data | Archive separately | Same |
| Architecture documents (consolidation files, playbooks, EPIGNOSIS decisions) | Archive | Same |
| Financial models and investor materials | Separate archive — these may not need clean-room treatment but should be preserved for litigation hold | Accessible for business use but not for technical specification |
| Test suites and test data | Archive — tests are a form of specification that could contaminate the clean room | Same as code |
| CI/CD configuration | Archive | Same |
| Docker images and deployment configs | Archive | Same |
| All CLAUDE.md files, agent prompts, and development instructions | Archive — these contain design specifications | Same |

**Critical preservation step:** Before quarantine, create a **forensic copy** of the entire repository (including git history, commit timestamps, branch structure) with a **third-party timestamp** (e.g., notarized hash, blockchain timestamp service). This preserves evidence of the founder's work in case of dispute.

### 5.3 Dirty Room Team

**Role:** Analyze the quarantined PRKT2026 artifacts and extract the **non-infringing functional requirements** — what the system does (at a high level), without specifying how it does it.

**Who can be in the dirty room:** Someone who has full access to the quarantined code and can write functional specifications from it. In a traditional clean-room, this is a separate person from the implementer.

**Can the founder be on this team?** In a traditional clean-room, the answer is "the founder should be in only ONE room." The founder's deep knowledge of the implementation makes them the natural dirty-room analyst. However, this creates the solo-founder problem (see 5.5).

**Dirty room output:** A **functional specification document** that describes:
- What the system does (inputs, outputs, behaviours)
- External interface contracts (API schemas, message formats)
- Business rules at a functional level (e.g., "the system must price bridge loans using CVA methodology" — without specifying the implementation)
- Performance requirements
- Regulatory requirements

The functional specification must NOT include:
- Code snippets or pseudocode derived from PRKT2026
- Architecture decisions (clean-room team makes their own)
- Data structure designs
- Algorithm implementations
- Variable names, class names, or module structure

### 5.4 Clean Room Team

**Role:** Implement the system from the functional specification, using only:
- The functional specification (from the dirty room)
- Publicly available standards (ISO 20022, SWIFT specifications, BIS publications)
- Academic literature
- General programming knowledge

**Who can be in the clean room:** Someone who has NOT seen the quarantined PRKT2026 code.

**Can the founder be on this team?** This is the critical question. In a traditional clean-room, NO — the founder has seen (indeed wrote) the original code and is contaminated. However, see 5.5 for the solo-founder problem.

### 5.5 The Solo Founder Problem

**The problem:** Traditional clean-room development requires strict separation between the person who analyzes the original work and the person who reimplements it. With a solo founder who wrote the original code, the same person is in both rooms. This structurally undermines the clean-room defence because the implementer has unavoidable knowledge of the original implementation.

**The options:**

**Option A — Hire a clean-room implementer:** The founder writes the functional specification (dirty room). A contracted developer (or team) implements from the specification without access to PRKT2026. The founder cannot review the implementation code until it is complete and a similarity analysis has been conducted.

- **Pros:** This is the strongest clean-room defence. True separation between analysis and implementation.
- **Cons:** Expensive ($30K–$100K depending on scope); slower (2–6 weeks); the founder loses control over implementation quality; the "Ford model" AI-assisted approach may not be available to the contractor; the contractor becomes a potential witness.
- **Cost mitigation:** The contractor could be instructed to use AI tools, reducing time/cost. The specification would need to be detailed enough for AI-assisted development.
- **This is the recommended approach if budget permits.**

**Option B — Modified solo clean-room with temporal separation:**

1. Founder writes the functional specification (dirty room phase).
2. A **mandatory cooling-off period** (2–4 weeks) elapses, during which the founder does NOT access PRKT2026 or any notes about its implementation.
3. Founder reimplements from the functional specification only (clean-room phase), documenting every design decision and citing only the functional specification and public sources.
4. An independent third party conducts a similarity analysis comparing the new code to the quarantined code.

- **Pros:** No external hiring cost; founder retains full control; the AI-assisted methodology can be used.
- **Cons:** This is a **legally weaker** defence. Courts have recognized that you cannot truly "unsee" code. The cooling-off period is not a legal standard — it is a practical measure to create distance. An aggressive opposing counsel would argue: "The founder is the same person who wrote the original. The 'clean room' is fiction."
- **Mitigations:** (a) The AI-assisted development approach actually helps here — if the founder provides the functional specification to Claude/AI tools and lets the AI generate the implementation, there is a genuine separation between the founder's memory of the original code and the AI's independent implementation decisions. (b) The functional specification should be reviewed by counsel before the clean-room phase begins. (c) The similarity analysis should be conducted by an independent expert.

**Option C — Patent-specification-based reimplementation:**

If a patent is filed before clean-room, the patent specification becomes a public document describing the invention at a functional level. The clean-room implementer (or founder) works from the patent specification rather than a separately-created functional specification.

- **Pros:** The patent specification is a legitimate "clean" document — it is publicly available and describes the invention without implementation details.
- **Cons:** (a) Filing the patent before clean-room creates the risk discussed in Q3 and Q11. (b) The patent specification may not be detailed enough for implementation. (c) If RBC claims the patent is itself their IP (which they can under the clause), the specification is not "clean."
- **NOT recommended** as the primary approach.

**Option D — Hybrid: AI as the clean-room barrier:**

1. Founder writes the functional specification (dirty room).
2. Founder provides the specification to AI tools (Claude, etc.) with explicit instructions: "Implement this system from the functional specification only. Do not reference, copy, or derive from any existing codebase."
3. The AI generates the implementation.
4. The founder reviews and refines the AI output — but the initial implementation decisions (architecture, data structures, algorithms) are made by the AI, not from the founder's memory of PRKT2026.

- **Pros:** This is a genuinely novel approach that leverages the Ford model. The AI has no memory of PRKT2026 (unless it was provided in the conversation context). The initial implementation is independently generated. The founder's review is akin to code review, not original authorship.
- **Cons:** (a) This is a legally untested approach — no court has ruled on whether AI-generated code constitutes a valid "clean room." (b) If the founder provides too much guidance during the AI-assisted development, the separation breaks down. (c) The legal framework for clean-room is built around human actors, not AI systems.
- **This approach has potential but should be validated with counsel before execution.**

### 5.6 Repository Hygiene

| Requirement | Implementation |
|------------|----------------|
| New git repository | Yes — new repo, fresh history. No connection to PRKT2026. |
| New git identity | Advisable — new email, new GitHub account (or new personal account if incorporating). Purpose is documentation, not deception — the founder's identity is known. |
| New cloud accounts | Yes — new AWS/GCP accounts not associated with PRKT2026 development. |
| New development environment | Advisable — fresh OS install or new virtual machine. The goal is to ensure no PRKT2026 artifacts are accessible during clean-room development. |
| No code transfer | Absolutely no copying of code, configuration, tests, or documentation from PRKT2026 to the new repo. |
| Public-source documentation | Every external source used in clean-room development must be logged: URL, date accessed, what was used. |

### 5.7 Documentation Requirements

The following records MUST be created and preserved:

1. **Quarantine log:** Date/time of quarantine, list of all quarantined artifacts, cryptographic hashes, access control measures.
2. **Functional specification:** The dirty-room output. Version-controlled, dated, reviewed by counsel.
3. **Clean-room development log:** Every design decision, every external source consulted, every AI interaction (full conversation logs if using the AI hybrid approach).
4. **Similarity analysis report:** Independent comparison of old and new codebases. Conducted by qualified expert.
5. **Access control records:** Evidence that clean-room developer(s) did not access quarantined materials during development.
6. **Timeline documentation:** Calendar entries, git commit timestamps, and any other evidence establishing the temporal separation.

### 5.8 Specification Document

The functional specification should be derived from:
1. **Public standards:** ISO 20022 message specifications, SWIFT GPI documentation, BIS papers on cross-border payments
2. **The founder's domain expertise** (which is personal knowledge, not employer IP — though this boundary is exactly what RBC would challenge)
3. **The quarantined PRKT2026's functional behaviour** — described at the "what it does" level, not "how it does it"

**Can the patent specification serve as the clean specification?** Only if:
- The patent has been filed and published (or at least drafted)
- The patent specification is not itself claimed by RBC
- The specification is detailed enough for implementation

In practice, the patent specification is too high-level for direct implementation. A separate functional specification is needed.

### 5.9 Similarity Analysis

**Purpose:** Demonstrate that the clean-room implementation is independently created, not derived from PRKT2026.

**Method:**
1. Automated code comparison (e.g., MOSS, JPlag, or commercial tools) measuring structural similarity
2. Manual expert review of architecture, data structures, and algorithm choices
3. Documentation of expected functional similarity (the systems do the same thing) vs. implementation differences (different architecture, different variable names, different algorithms for the same function)

**Key standard:** Some similarity is expected and acceptable — both systems implement the same functionality from the same public standards. The test is whether the similarity is at the **expression level** (copying) or the **functional level** (independent implementation of the same requirements).

### 5.10 Contamination Risks

The following actions would invalidate the clean-room defence:

1. **Accessing PRKT2026 code during clean-room development** — even "just to check one thing"
2. **Copying any code, configuration, or documentation** from PRKT2026 to the new repo
3. **Having the same person write the specification AND implement from it** without adequate separation measures (this is the solo-founder risk — it weakens but does not necessarily invalidate the defence)
4. **Using test cases from PRKT2026** — tests are a form of specification that encodes implementation details
5. **Referencing PRKT2026 commit messages or PR descriptions** during clean-room development
6. **Discussing PRKT2026 implementation details** with the clean-room implementer
7. **Providing AI tools with PRKT2026 code** in the context window during clean-room AI-assisted development

### 5.11 30-Day Execution Plan

**Assumes:** Founder resigns on Day 0. IP counsel has been engaged and recommends clean-room. Budget allows for Option A (hired implementer) or Option D (AI hybrid).

| Day | Action | Deliverable |
|-----|--------|------------|
| 0 | Resign from RBC. Effective date per notice period. | Resignation letter (reviewed by counsel) |
| 0 | Execute forensic preservation of PRKT2026. | Notarized hash, full archive, quarantine log |
| 1–3 | Write functional specification from quarantined materials. | Functional specification v1 (dirty room output) |
| 3–5 | Counsel reviews functional specification for contamination risk. | Counsel-approved functional specification |
| 5–7 | If Option A: engage clean-room contractor. If Option D: prepare AI-assisted clean-room environment. | Contractor NDA + scope; or fresh development environment |
| 7–21 | Clean-room implementation. Daily development logs. | New codebase, fully documented |
| 21–23 | Integration testing and validation against functional specification. | Test results |
| 23–25 | Independent similarity analysis (old vs. new). | Similarity analysis report |
| 25–27 | Counsel reviews similarity analysis and clean-room documentation. | Counsel sign-off |
| 27–30 | Patent filing preparation using clean-room codebase. | Patent application draft |

**Total elapsed time:** 30 days post-resignation. This timeline is aggressive — a more realistic estimate is 45–60 days, especially if the contractor requires additional time.

### 5.12 Litigation Hold Records

**Preserve immediately (regardless of whether clean-room is ultimately needed):**

1. Complete PRKT2026 git repository (all branches, all history)
2. All communication about BPI (emails, messages, notes)
3. All pre-employment evidence of conception (when found)
4. The RBC offer letter (complete, all pages)
5. Any RBC onboarding documents signed
6. Git commit timestamps (exported)
7. Cloud access logs (AWS/GCP/Azure)
8. AI tool conversation histories (Claude, Copilot, etc.)
9. Personal device purchase receipts (proving personal ownership)
10. ISP records (if obtainable, showing device connections)

**Do NOT destroy, alter, or overwrite any of these records.** A litigation hold means preserving everything in its current state, even if it is unfavourable.

---

## SECTION 6 — FUNDRAISING IMPACT

### 6.1 SAFE Terms

The standard NACO SAFE terms (no discount, valuation cap, pro-rata rights, MFN) are appropriate for F&F. However, given the IP uncertainty:

- **Consider adding an IP resolution milestone:** The SAFE could include a provision stating that if the IP risk cannot be resolved within [X months], investors have the option to reclaim their investment (minus legal costs incurred). This is unusual in SAFEs but appropriate given the pre-counsel status.
- **Alternatively, do not modify SAFE terms** — resolve the IP question before raising, which eliminates the need for unusual terms.

**Recommendation:** Do not modify the SAFE. Instead, resolve the IP question first.

### 6.2 Valuation Cap

**Is $2M defensible given IP uncertainty?**

No. A $2M pre-money valuation for a pre-incorporation, pre-revenue, pre-patent company with a material unresolved IP claim is not defensible to a sophisticated investor. The IP uncertainty is not a "risk factor" — it is a **title defect** that could mean the company owns nothing.

However, if the IP question is resolved favourably before raising, $2M may be defensible based on the prototype's sophistication (1,476 tests, 7 Docker images, working ML pipeline) and the market opportunity.

**Recommendation:** Do not raise at any valuation until IP is resolved. After resolution:
- If clean title: $2M is defensible
- If clean-room needed: $1.5M–$2M (discounted for the rewrite risk and delay)
- If RBC negotiated release with conditions: Valuation depends on conditions (royalty, license fee, etc.)

### 6.3 Investor Trust

**How does a sophisticated F&F investor react to this disclosure?**

A sophisticated investor will:
1. Ask whether a lawyer has reviewed the clause — if not, ask why not
2. Question why the founder is raising money before resolving the most material risk
3. Wonder whether the founder is transferring the risk of a legal battle to friends and family
4. Potentially decline until the IP is resolved

A less sophisticated investor (which most F&F are) will:
1. Trust the founder's assurance that "it will be fine"
2. Not fully understand the implications of the IP clause
3. Invest based on personal relationship, not diligence

This asymmetry is exactly why raising before the IP opinion is ethically problematic. The founder would be taking advantage of the trust relationship.

### 6.4 Disclosure Obligations

**Is the current risk disclosure (Section 2.2) sufficient?**

The existing Section 2.2 is remarkably thorough and honest. It discloses:
- The RBC employment
- The broad IP clause
- The git history problem
- The fact that no IP lawyer has been engaged
- The possible outcomes (favourable, negotiated, license, clean-room, adverse)
- The pre-employment conception evidence plan

**What's missing or needs updating:**

1. **The actual clause language.** The disclosure says "broad intellectual property assignment clause" — now that the exact language is known, it should be quoted verbatim. Investors deserve to see what they're up against.

2. **The disclosure obligation breach.** The clause requires the founder to "promptly and fully disclose Work Product." The founder has not done this. This creates an independent contractual breach that should be disclosed.

3. **The 15-year limitation period.** Investors should know that even if RBC doesn't claim now, they have up to 15 years.

4. **The patent risk.** The current Section 2.5 discusses patent risk generically but does not connect it to the RBC clause — specifically, that filing a patent creates a public record that RBC could discover.

5. **The "sell it back to them" risk.** The go-to-market strategy targets RBC. Investors should know this creates a unique conflict.

6. **Probability assessment.** The current disclosure says "Likelihood: Unknown" for all outcomes. Now that the actual clause language is known, the likelihood can be partially assessed (likely HIGH for RBC having a colourable claim, UNCERTAIN for enforceability).

### 6.5 Use-of-Proceeds Language

The IP lawyer engagement should be described as:

> "IP/employment legal opinion ($5,000–$10,000): Engagement of a qualified British Columbia IP and employment lawyer to: (1) opine on the enforceability and scope of the RBC IP assignment clause as applied to BPI's technology; (2) advise on whether clean-room reimplementation is recommended; (3) if clean-room is recommended, design the protocol; (4) prepare a title opinion suitable for pre-seed investor diligence."

This language should appear in the use-of-proceeds section of the SAFE term sheet AND in the risk disclosure.

### 6.6 Timing of Incorporation

**Before or after IP opinion?**

**After.** Reasons:
1. Incorporation creates a legal entity that is premised on the founder contributing IP — if the IP is encumbered, the incorporation is defective
2. The s.85 rollover requires clean title to the IP being transferred
3. Incorporating while employed may violate OBA policies
4. No urgency — incorporation can be completed in 5–10 business days once the IP is resolved

### 6.7 Timing of Patent Filing

**Before or after IP opinion?** After. The IP opinion gates the patent strategy:
- If clean title → file patent on existing work
- If clean-room needed → file patent on clean-room work
- If RBC negotiation needed → patent filing timing depends on negotiation outcome

**Before or after resignation?** After. Filing while employed is more provocative, creates a discoverable public record while the employment relationship is active, and may violate the disclosure obligation.

### 6.8 Is It Defensible to Take F&F Money Before Obtaining a Legal Opinion?

**No.**

The reasoning is straightforward:
1. The founder knows of a material risk that could render the IP worthless
2. The founder has not taken the relatively inexpensive step ($5K–$10K) of getting a legal opinion
3. The founder would be asking friends and family to fund the legal opinion that might reveal the venture is non-viable
4. This transfers the founder's risk to people who trust him personally
5. NI 45-106 s.2.5 may not require formal disclosure, but common-law duties of honest dealing apply
6. A securities regulator reviewing this fact pattern would question the founder's good faith

**The right sequence is:**
1. Self-fund the IP lawyer engagement ($5K–$10K)
2. Obtain the legal opinion
3. If favourable: raise F&F at $2M cap with clean disclosure
4. If clean-room recommended: do the clean-room, then raise
5. If adverse: reassess the entire venture before taking anyone's money

### 6.9 Three Disclosure Versions

#### Version 1 — CANDID (Recommended)

> **Section 2.2 — Intellectual Property Assignment Risk**
>
> **This is the most material risk facing the Company. Please read carefully.**
>
> The founder is currently employed by the Royal Bank of Canada ("RBC") as a Credit Management Resolution Officer in retail banking. The founder's RBC offer letter contains the following IP assignment clause:
>
> > *"Anything you conceive, create or produce, whether alone or jointly with others, during your employment in this role or any other you might have later, as well as any improvements or contributions you make, including written documents, drawings, presentations and technologies (collectively, the Work Product), will be the property of Royal Bank of Canada (the Bank)."*
>
> > *"You must promptly and fully disclose Work Product to your Employer."*
>
> **Key facts:**
>
> 1. The founder's RBC employment began on January 12, 2026.
> 2. The entire BPI technology repository was developed after this date. There are no pre-employment dated artifacts in the repository.
> 3. All development was done on personal time, using personal equipment, with no RBC resources, data, or systems. BPI's domain (cross-border B2B payment bridging) is unrelated to the founder's retail credit management role.
> 4. The founder has not disclosed BPI to RBC as the clause requires, creating an independent contractual breach.
> 5. The founder believes core concepts predate the RBC employment, but dated evidence of this has not yet been assembled or verified.
> 6. A qualified IP/employment lawyer has reviewed the clause and provided an opinion on enforceability. [UPDATE: Insert result of opinion here once obtained.]
>
> **Possible outcomes:**
>
> | Outcome | Impact on Your Investment |
> |---------|-------------------------|
> | IP lawyer opines clause is unenforceable as applied | Proceed as planned |
> | Clean-room reimplementation recommended | 30–60 day delay; existing code discarded; new code written |
> | RBC negotiated release | Possible ongoing cost; reduced margins |
> | RBC asserts ownership | Fundamental threat to the Company; may require abandonment |
>
> **Limitation period:** Under the BC *Limitation Act*, RBC has up to 15 years from creation or 2 years from discovery to bring a claim. This is a long-tail risk.
>
> **The founder's commitment:** The IP legal opinion is being obtained before any investment is accepted. No investment will be accepted until this risk is assessed by qualified counsel.

#### Version 2 — CONSERVATIVE

> **Section 2.2 — Intellectual Property Risk**
>
> The founder's current employer may have a contractual claim to intellectual property developed during the employment period. The claim is based on a standard employment agreement clause. The founder's employment role is unrelated to BPI's technology domain, and all development was conducted on personal time and equipment.
>
> A qualified legal opinion has been obtained confirming [insert opinion]. Investors should be aware that the former employer has not been notified of BPI and may assert a claim if it becomes aware of the Company. The Company believes any such claim would be unlikely to succeed based on the facts and applicable law, but cannot guarantee this outcome.

*Note: This version omits the actual clause language, the disclosure obligation breach, and the 15-year limitation period. It is weaker than Version 1 but still defensible IF the legal opinion has been obtained first.*

#### Version 3 — TOO AGGRESSIVE (Do NOT Use)

> **Section 2.2 — Employment IP**
>
> ~~The founder's employer has a standard IP clause in its employment agreement. Our legal counsel has confirmed that this clause does not apply to BPI because the work was done on personal time, with personal equipment, and is completely unrelated to the founder's job.~~
>
> ~~The risk of any employer claim is minimal and would not succeed if pursued.~~

**Why every sentence is problematic:**

1. *"Standard IP clause"* — minimizes the clause's unusual breadth. The clause is NOT standard; it is extremely broad with no carve-outs.
2. *"Our legal counsel has confirmed"* — if no counsel has been engaged, this is a false statement. If counsel has been engaged but gave a nuanced opinion, this misrepresents their conclusion.
3. *"Does not apply to BPI"* — this is a legal conclusion the founder is not qualified to make and that no counsel would state with this certainty.
4. *"Completely unrelated"* — the founder's role is unrelated, but RBC's business includes cross-border payments. "Completely unrelated" is an overstatement.
5. *"Risk … is minimal"* — the risk is material and uncertain. "Minimal" is a misrepresentation.
6. *"Would not succeed if pursued"* — no lawyer would make this guarantee given the clause's breadth and the untested legal question.

Using Version 3 would expose the founder to potential securities fraud liability if the IP claim materializes and investors can show they relied on this disclosure.

---

## SECTION 7 — DECISION MATRIX

### Path Descriptions

| Path | Sequence |
|------|----------|
| **A** | Raise F&F now → IP lawyer later → patent → incorporate |
| **B** | IP lawyer first (self-funded, $5K–$10K) → raise F&F → patent → incorporate |
| **C** | Incorporate now → IP lawyer → raise → patent |
| **D** | Clean-room reimplementation first → IP lawyer → raise → patent |
| **E** | IP lawyer first → clean-room if recommended → raise → patent → incorporate |
| **F** | Abandon PRKT2026 entirely → resign → restart from scratch → raise → patent |

### Scoring (1–10, 10 = Best)

| Criterion (Weight) | A | B | C | D | E | F |
|--------------------|---|---|---|---|---|---|
| **Legal risk minimization (25%)** | 2 | 6 | 3 | 5 | 9 | 10 |
| **Financing credibility (20%)** | 3 | 7 | 4 | 5 | 8 | 6 |
| **Speed to fundraise (15%)** | 9 | 6 | 7 | 3 | 5 | 2 |
| **Cash efficiency (10%)** | 8 | 5 | 6 | 3 | 5 | 2 |
| **Ethical defensibility (15%)** | 2 | 7 | 3 | 6 | 9 | 8 |
| **Diligence survivability (15%)** | 2 | 7 | 3 | 6 | 9 | 7 |

### Weighted Scores

| Path | Calculation | Weighted Score |
|------|------------|---------------|
| **A** | (2×0.25)+(3×0.20)+(9×0.15)+(8×0.10)+(2×0.15)+(2×0.15) | **3.85** |
| **B** | (6×0.25)+(7×0.20)+(6×0.15)+(5×0.10)+(7×0.15)+(7×0.15) | **6.40** |
| **C** | (3×0.25)+(4×0.20)+(7×0.15)+(6×0.10)+(3×0.15)+(3×0.15) | **4.05** |
| **D** | (5×0.25)+(5×0.20)+(3×0.15)+(3×0.10)+(6×0.15)+(6×0.15) | **4.80** |
| **E** | (9×0.25)+(8×0.20)+(5×0.15)+(5×0.10)+(9×0.15)+(9×0.15) | **7.80** |
| **F** | (10×0.25)+(6×0.20)+(2×0.15)+(2×0.10)+(8×0.15)+(7×0.15) | **6.40** |

### Recommendation: Path E

**Path E — IP lawyer first → clean-room if recommended → raise → patent → incorporate — wins decisively at 7.80.**

**Why Path E is superior:**

1. **It puts the legal opinion first.** Every other decision — whether to clean-room, when to raise, how to structure the patent, whether to incorporate — depends on the legal opinion. Path E recognizes this dependency and sequences correctly.

2. **It is self-funded at the critical step.** The $5K–$10K for the IP lawyer comes from the founder's personal funds, not from investors. This means no one else's money is at risk during the most uncertain phase.

3. **It is ethically unassailable.** The founder has done diligence before taking anyone's money. If the news is bad, no investor has been harmed. If the news is good, the investor gets a better-diligenced opportunity.

4. **It preserves all optionality.** After the legal opinion, the founder can:
   - Proceed directly (if clause is unenforceable)
   - Clean-room (if recommended)
   - Negotiate with RBC (if needed)
   - Abandon (if catastrophic)

5. **It survives pre-seed diligence.** When pre-seed investors ask "what did you do about the RBC IP risk?", the answer is: "I obtained a legal opinion, followed counsel's recommendation, and resolved the issue before taking any money." This is the answer that passes diligence.

**Why not Path F (Abandon)?**

Path F scores highest on legal risk minimization (10/10) because it eliminates the existing codebase entirely. However:
- It is unnecessarily destructive if the clause is unenforceable
- It wastes 10 weeks of prototype development
- It delays fundraising by months
- It is only appropriate if counsel advises that the clause is enforceable AND no clean-room approach can salvage the work

Path F is the fallback if Path E's legal opinion is catastrophic. It should not be the default.

**Why not Path B?**

Path B (IP lawyer first → raise → patent → incorporate) ties with F at 6.40 but lacks the clean-room contingency. If the lawyer recommends clean-room, Path B has no plan for it. Path E includes this contingency.

---

## SECTION 8 — LAWYER PREP MEMO

---

**CONFIDENTIAL — ATTORNEY-CLIENT PRIVILEGED**

**MEMORANDUM**

**TO:** [BC IP/Employment Counsel — TBD]
**FROM:** [Founder Name]
**DATE:** March 23, 2026
**RE:** IP Ownership — Employee Personal Project During RBC Employment

---

### 1. Factual Background

I am a Canadian citizen, resident of British Columbia, currently employed at the Royal Bank of Canada ("RBC") as a Credit Management Resolution Officer in the retail banking division. My employment began on January 12, 2026. I have not resigned.

My role at RBC involves working with customers in financial difficulty on existing retail banking products (mortgages, lines of credit, credit cards). My role does NOT involve: technology development, cross-border payments, SWIFT messaging, institutional payments, correspondent banking, AI/ML development, or fintech product development. I have no access to RBC's cross-border payment systems, SWIFT infrastructure, or correspondent banking data.

Between approximately January 12, 2026 and March 23, 2026, I developed a software prototype called "Bridgepoint Intelligence" (codename PRKT2026), a system for detecting and bridging cross-border B2B payment failures using ML-driven risk pricing. The target market is Tier 1 banks' institutional/correspondent banking divisions — a completely different business line from retail credit management.

Key development facts:
- All development was on personal equipment (personal laptop, personal cloud accounts)
- All development was on personal time (evenings, weekends, days off)
- I used only publicly available information (BIS papers, SWIFT GPI docs, ISO 20022 standards, academic research, public regulatory filings)
- I did NOT use any RBC equipment, network, VPN, email, or cloud resources
- I did NOT use any RBC proprietary data, internal documents, trade secrets, or customer data
- I did NOT discuss the project with any RBC employee
- I did NOT seek outside business activity approval from RBC
- The development used AI-assisted methodology ("Ford model") — much of the code was generated by AI tools on personal accounts
- The git repository has 1,476 passing tests, 7 Docker images, a full CI/CD pipeline, and an ML inference engine

Critical timing issue: The **entire git history** falls within the RBC employment period. There are no commits, documents, or dated artifacts from before January 12, 2026. I believe core concepts predate my employment, but I have not yet assembled or verified evidence of this.

My RBC offer letter (attached) contains the following IP assignment clause:

> *"Anything you conceive, create or produce, whether alone or jointly with others, during your employment in this role or any other you might have later, as well as any improvements or contributions you make, including written documents, drawings, presentations and technologies (collectively, the Work Product), will be the property of Royal Bank of Canada (the Bank)."*

The offer letter also states:

> *"You must promptly and fully disclose Work Product to your Employer."*

I have not disclosed the project to RBC.

### 2. Legal Questions

In priority order:

1. **Is the IP assignment clause in my RBC offer letter enforceable under BC/Canadian law as applied to a personal project that is (a) unrelated to my job duties, (b) developed entirely on personal time and equipment, and (c) in a different business domain than my role?**

2. **If the clause is enforceable as written, would a court likely read it down (sever or narrow it) to cover only work done in the course of employment or related to RBC's business?** What is the applicable standard under BC law for interpreting overly broad employment covenants?

3. **Does RBC have a cognizable claim to the patentable inventions** (as opposed to just the copyright in the code)? Specifically, does the word "conceive" in the clause create an assignment of inventive concepts?

4. **What is the legal significance of the entire git history falling within the employment period?** Is this a rebuttable presumption of employment-period creation, and what evidence would be sufficient to rebut it?

5. **Am I in breach of the disclosure obligation**, and does this breach strengthen RBC's position on IP ownership?

6. **If I resign and rewrite the code from scratch (clean-room reimplementation), does this materially reduce RBC's claim?** What protocol would be legally defensible?

7. **Can I file a patent on the underlying methodology, and would RBC have standing to challenge the filing or claim inventorship/ownership?**

8. **Under the BC *Limitation Act*, what is the limitation period for RBC to bring a claim?** When does the clock start?

9. **Does the common-law duty of fidelity create exposure independent of the IP clause?** Specifically, is it a breach to develop a product targeting the banking industry while employed at a bank?

10. **If I raise money from friends and family before this IP question is resolved, what are my disclosure obligations under NI 45-106 s.2.5 and common law?**

### 3. Documents for Review

Please review:

1. **RBC offer letter** (complete, all pages) — attached
2. **Any additional onboarding documents** I signed at RBC (I will locate and provide these)
3. **RBC Code of Conduct** (if obtainable — the published version states IP "created by employees during their employment belongs to and remains the exclusive property of RBC")
4. **PRKT2026 git repository summary** — commit count, date range, branch structure (I can provide a git log export)
5. **Sample of pre-employment evidence** (once assembled — emails, notes, search history)
6. **Investor risk disclosure document** — current draft (to assess adequacy)
7. **SAFE template** — current draft (to assess whether IP uncertainty requires modification)
8. **Planned patent claims** — summary of the inventions I plan to patent

### 4. Decision Deadlines

| Decision | Deadline | Why |
|----------|----------|-----|
| Whether to resign | Ongoing — each day employed extends the "during employment" period | Every commit adds to the period covered by the clause |
| Whether to raise F&F | Blocked on this opinion | I will not raise money until IP risk is assessed |
| Whether to file patent | Blocked on this opinion | Filing creates public record and triggers RBC discovery risk |
| Whether to incorporate | Blocked on this opinion | S.85 rollover requires clean IP title |
| Whether to clean-room | Depends on this opinion | If recommended, 30–60 day execution timeline |

### 5. Desired Outputs

I need the following written deliverables:

1. **IP ownership opinion letter** — your opinion on whether the RBC clause is enforceable as applied to BPI's fact pattern, with probability-weighted outcomes
2. **Clean-room recommendation** — if clean-room is recommended, a brief protocol outline
3. **Patent filing guidance** — whether it is safe to file, timing, and any precautions
4. **Fundraising clearance** — whether it is defensible to raise F&F given the IP risk, and what disclosures are required
5. **Resignation strategy** — any considerations for the resignation process (e.g., should I request a release, or is silence better?)

### 6. Scope of Engagement

I am asking you to opine on:
- Enforceability of the RBC IP assignment clause under BC employment law
- Ownership of the existing PRKT2026 work product
- Ownership of the underlying inventions
- Clean-room protocol design (if recommended)
- Fundraising disclosure adequacy

I am NOT asking for:
- Patent prosecution (I will engage a separate patent agent)
- CBCA incorporation (I have a corporate lawyer for this)
- Securities law compliance (I will confirm with a securities lawyer)

### 7. Gating Note

**This opinion gates the following downstream actions:**
- $75,000–$150,000 F&F fundraising round
- Provisional patent filing (US + CA)
- CBCA incorporation
- Pre-Seed round ($1.5M at $6M pre-money)
- Go-to-market execution (including potential approach to RBC as customer)

I cannot proceed with any of these until I have your opinion. Time is of the essence — each day of employment extends the clause's coverage, and patent priority dates are not being established.

### 8. Budget Expectation

I have budgeted $5,000–$10,000 for this engagement. Is this realistic for the scope described above? If not, please advise on a phased approach:
- Phase 1 (urgent): Clause enforceability opinion and clean-room recommendation
- Phase 2 (if needed): Protocol design, resignation strategy, disclosure review

I would prefer a fixed-fee engagement if possible, with the scope defined as above.

---

*End of memo*

---

## SECTION 9 — RED TEAM

### Attack 1: Weakest Parts of the Reasoning

**The enforceability challenge is assumed to be a strong defence — but it is untested.**

The analysis throughout this document relies heavily on the argument that the RBC clause is "unconscionably broad" and that a court would read it down. This argument is theoretically sound but has NO direct precedent in Canadian law. There is no reported case where a Canadian court has struck down or narrowed a blanket IP assignment clause like RBC's in the context of a bank employee. The closest analogies (*Shafron*, *Techform*) involve non-competes and restrictive covenants, not IP assignment. The transfer of principles from non-compete law to IP assignment law is plausible but not guaranteed.

**Risk: A court may simply enforce the clause as written.** The founder signed it, received employment as consideration, and is an educated adult. The "unconscionable" threshold in Canadian contract law is high — it requires a finding that the clause is grossly unfair, oppressive, and that the weaker party had no meaningful choice. Given that the founder is a professional with the ability to negotiate or decline the offer, unconscionability may not apply.

### Attack 2: Assumptions That Might Be Wrong

1. **Assumption: RBC's institutional inertia means they won't pursue a retail credit officer's side project.** This may be wrong. RBC's legal department handles IP matters centrally — they don't distinguish by division. If the IP has patent value (projected $18B–$35B portfolio), the economics change dramatically. RBC may pursue not because of the current code but because of the patent position.

2. **Assumption: The "personal time, personal equipment" defence is strong.** This may be overweighted. The clause explicitly does not require employer resources — it covers "anything … during your employment." The personal time/equipment argument is relevant to enforceability, not to the clause's literal coverage. If the clause is enforced as written, these facts are irrelevant.

3. **Assumption: Pre-employment conception evidence exists.** The founder "believes" core concepts predate employment but has not conducted a search. It is entirely possible that no datable evidence exists. If the evidence does not exist, the founder's position is significantly weaker — "I thought of it before" is a self-serving statement that requires corroboration.

4. **Assumption: Clean-room is a reliable fallback.** The solo-founder clean-room problem is real. No court has ruled on the validity of a clean-room where the original developer is also the clean-room implementer, and no court has ruled on AI-as-clean-room-barrier. These are novel legal arguments that might not succeed.

5. **Assumption: RBC's cost-benefit calculus disfavours litigation.** This assumes RBC acts rationally on economics. In practice, large institutions sometimes litigate for reputational or policy reasons — to send a message to other employees that personal projects during employment will not be tolerated. If RBC is in a "making an example" mode, rational economics do not apply.

### Attack 3: Arguments Aggressive RBC Counsel Would Make

1. **"The founder deliberately concealed the project."** The disclosure obligation required "prompt and full" disclosure. The founder disclosed nothing. This is not just a breach — it demonstrates consciousness of guilt. "He knew it belonged to RBC, which is why he hid it."

2. **"The timing is not coincidental."** The founder started at RBC on January 12 and immediately began building a payment technology company. "He took the job at a bank to give himself insider credibility and domain exposure while building a competing product on the side."

3. **"Cross-border payments IS RBC's business."** RBC processed $X billion in cross-border payments last year through its correspondent banking network. BPI targets the same market. "Our employee built a product for our market during his employment and now wants to sell it to our competitors — or worse, back to us."

4. **"The AI tools are irrelevant."** "The founder directed the AI to write the code. The founder made the design decisions. The founder chose the architecture. The AI is a tool, like a compiler or a word processor. Using an AI to write the code does not change who conceived and created the work product."

5. **"The Ford model proves the founder is the inventor."** "The founder brags about his 'Ford model' — being the strategic vision behind the system while AI does the implementation. This proves he conceived the inventions. 'Conceive' is exactly the word in our clause."

### Attack 4: Facts That Could Collapse the Optimistic Case

1. **What if the founder once Googled something on RBC's network?** Even a single search query about SWIFT, cross-border payments, or payment failures on an RBC device or network would undermine the "no RBC resources" claim. IT forensics could reveal this.

2. **What if an RBC training module covered correspondent banking or cross-border payments?** Mandatory compliance training at banks often covers broad topics. If the founder completed a module on payments, RBC could argue exposure to confidential banking practices.

3. **What if a co-worker saw the founder's screen or heard a phone call?** Even without the founder voluntarily discussing BPI, incidental exposure could create a witness who places BPI in the workplace context.

4. **What if RBC's policy is broader than the offer letter?** The Code of Conduct language ("created by employees during their employment") is separate from the offer letter. If there is a third document (invention assignment, acceptable use policy) that is even more specific, it could close loopholes.

5. **What if the founder used a personal phone that syncs work email?** If a personal device that was used for BPI development also receives RBC email, it could be argued that it is partially an "employer resource" or at minimum that the separation between work and personal is blurred.

6. **What if RBC has an internal innovation team working on cross-border payment optimization?** If RBC has a skunkworks project in the same space, they would have both the motive and the institutional knowledge to pursue the claim aggressively.

### Attack 5: What Would a Hostile Acquirer or Down-Round Investor Do 3 Years From Now?

A hostile acquirer or down-round investor in 2029 could:

1. **Use the unresolved IP history as a negotiation weapon** to demand a lower valuation, even if the legal opinion is favourable. "Your IP lawyer says it's probably fine, but 'probably' isn't 'certainly.' We're discounting by 30% for the residual risk."

2. **Demand an IP insurance policy** (tech E&O or IP defense insurance) as a condition of investment, which could cost $50K–$200K annually.

3. **Demand a full chain-of-title opinion** from a top-tier firm, costing $50K+, and then use any hedging language as justification for a haircut.

4. **Use the threat of disclosing the RBC history to a competitor** as leverage in negotiations. "If you don't accept our terms, we walk, and the market will know about your IP problem."

5. **In a down-round scenario, use the IP risk to justify a cramdown** that wipes out F&F investors entirely. "The IP was always uncertain — the previous valuation was inflated."

This is why resolving the IP question NOW, before raising any money, is essential. The longer the ambiguity persists, the more leverage it gives future adverse parties.

### Attack 6: Could RBC Discover This and Do Nothing?

**Yes, and there are several scenarios:**

1. **Cost-benefit analysis:** The cost of litigating against a former retail credit officer exceeds the expected recovery. PRKT2026 is a prototype with zero revenue. The patent hasn't been filed. There's nothing of current value to recover. **This is the most likely "do nothing" scenario in the near term.**

2. **Reputational risk to RBC:** Suing a former employee for a personal side project could generate negative press. "Canada's largest bank claims ownership of employee's weekend hobby." RBC's PR team might counsel against it.

3. **Strategic interest:** If RBC sees BPI as potentially valuable, they may prefer to engage commercially (license, acquire, or partner) rather than litigate. Litigation creates an adversary; commercial engagement creates a supplier.

4. **Institutional blindness:** RBC has 80,000+ employees. The legal department processes hundreds of IP matters. A retail credit officer's side project may simply never reach anyone's radar.

**But the "do nothing" assumption is the most dangerous planning error in this analysis.** It requires assuming that:
- RBC never discovers BPI (unlikely if the patent is filed and BPI approaches banks as customers)
- RBC's discovery triggers no institutional response (unlikely — the legal department monitors for exactly this)
- RBC's economic calculus remains unfavourable (changes dramatically if BPI succeeds and the patent portfolio becomes valuable)

**The correct planning assumption is that RBC will discover BPI and will respond.** The only unknowns are when and how aggressively.

---

## SECTION 10 — EXECUTIVE BOTTOM LINE

### Most Likely Practical Outcome

RBC's IP clause is extremely broad but likely unenforceable as applied to this specific fact pattern — an employee in a completely unrelated role, working on personal time with personal equipment, on a project with no connection to their job duties. A qualified IP lawyer will likely advise that the risk is **manageable but not zero**, and recommend one of:

1. **Proceed with documented precautions** (evidence preservation, clean separation narrative, strong pre-employment evidence if available), or
2. **Modified clean-room reimplementation** to create additional distance, especially if pre-employment evidence is weak

The F&F round proceeds, the patent gets filed, and the company incorporates. RBC either never discovers BPI, or discovers it and concludes the cost of litigation exceeds the benefit.

**Probability estimate: 55–65%.**

### Worst Plausible Outcome

The IP clause is enforced as written. Pre-employment evidence is non-existent or insufficient. RBC sends a demand letter, then files suit. The patent filing is contested. Investors learn of the litigation. The pre-seed round collapses. The founder is forced to negotiate from a position of extreme weakness — either:

- Assign the IP to RBC and walk away, or
- Settle for a licence that gives RBC a permanent royalty and effective veto over BPI's business

The F&F investors lose most or all of their investment. The founder's relationships with friends and family are damaged. The multi-year effort is lost or captured by RBC.

**Probability estimate: 10–15%.** Low but not negligible — and the consequences are catastrophic.

### Best Plausible Outcome

The IP lawyer confirms the clause is unenforceable as applied. Strong pre-employment evidence is found (emails, notes, conversations). The founder assembles a clean title package. The patent is filed with clean chain of title. The F&F round closes at $2M. The pre-seed follows. RBC never pursues a claim, or discovers BPI after it has a strong IP position and market traction and concludes that commercial engagement is preferable to litigation.

**Probability estimate: 25–30%.**

### What to Do in the Next 72 Hours

**Hour 0–4: Evidence Preservation Sprint**

1. **Search every personal email account** (Gmail, Outlook, Yahoo, etc.) for pre-employment messages containing: "payment," "bridge," "SWIFT," "cross-border," "fintech," "startup," "bank failure," "payment failure," "correspondent banking," "PRKT," "Bridgepoint." Export and date-stamp any results.

2. **Search personal messaging apps** (iMessage, WhatsApp, Signal, Telegram, Slack) for any pre-January-12-2026 messages about payment bridging or startup concepts. Screenshot with timestamps.

3. **Check browser history and bookmarks** for pre-employment research on BIS papers, SWIFT GPI, ISO 20022, or cross-border payment systems.

4. **Check personal notes** (Apple Notes, Google Keep, Notion, physical notebooks) for any pre-employment ideation.

5. **Identify any person** you discussed the concept with before January 12, 2026. Contact them and ask if they would provide a written statement of what was discussed and when.

**Hour 4–24: Lawyer Engagement**

6. **Research BC IP/employment lawyers.** Look for: (a) experience with employee IP disputes, (b) familiarity with Schedule I bank employment practices, (c) startup formation experience, (d) fixed-fee engagement availability.

7. **Send the lawyer prep memo** (Section 8 of this document) to 2–3 candidate lawyers. Request a 30-minute initial consultation.

8. **Budget the $5K–$10K** from personal funds. Do not use any planned F&F proceeds for this.

**Hour 24–72: Repository Forensics**

9. **Export the complete git log** of PRKT2026 with timestamps: `git log --all --format="%H %ai %s" > git-history-export.txt`. Store this outside the repository.

10. **Verify that all commit timestamps are outside RBC work hours.** If any commits fall during work hours (e.g., 9 AM–5 PM weekdays), determine whether you were working at RBC at that time (shift schedules, time-off records).

11. **Create a forensic snapshot** of the repository: `tar -czf PRKT2026-forensic-$(date +%Y%m%d).tar.gz PRKT2026/`. Store in a separate location with a timestamp.

12. **Document your development environment:** List every device, account, and tool used. Photograph your personal laptop (serial number visible). Export cloud access logs from AWS/GCP if applicable.

### What You Absolutely Should NOT Do Yet

1. **Do NOT raise money from anyone.** Not friends, not family, not anyone. Not until the IP lawyer has opined.

2. **Do NOT incorporate.** The incorporation requires clean IP title for the s.85 rollover. Incorporating with encumbered IP creates a defective foundation.

3. **Do NOT file a patent.** The patent filing creates a public record that RBC can discover. Filing before the IP opinion is obtained is premature and potentially provocative.

4. **Do NOT resign from RBC.** Resignation triggers potential discovery. Resign only after the IP lawyer has advised on timing and strategy.

5. **Do NOT disclose BPI to RBC.** Even though the clause requires disclosure, voluntary disclosure before obtaining legal advice could trigger the exact claim you are trying to assess. This is a decision for counsel.

6. **Do NOT modify, delete, rewrite, or backdate any git history.** Altering evidence is discoverable, destroys credibility, and could constitute fraud or spoliation.

7. **Do NOT discuss BPI with any RBC employee or on any RBC system.** Zero contact between the two worlds.

8. **Do NOT approach RBC, RBCx, or any bank as a potential customer.** The go-to-market strategy must wait until the IP question is resolved.

9. **Do NOT publish anything about BPI** (blog posts, social media, conference talks, academic papers) that could trigger RBC discovery before you are prepared.

10. **Do NOT panic.** The clause is broad, but the facts favour you. You need a lawyer, not a miracle.

---

## CLOSING DELIVERABLES

### TOP 10 FACTS I STILL NEED FROM YOU

1. **Complete, unredacted RBC offer letter** — every page, every clause. The IP clause is known, but there may be additional provisions (non-compete, OBA policy acknowledgment, confidentiality schedule).

2. **Any additional documents signed at RBC onboarding** — invention assignment, NDA, IT acceptable use policy, employee handbook acknowledgment, code of conduct acknowledgment.

3. **Pre-employment conception evidence inventory** — what do you actually have? Emails, texts, notes, conversations, browser history, domain registrations, prior prototypes, journal entries. Be specific about dates.

4. **Your exact RBC work schedule** — shift times, days worked, flex time. I need this to cross-reference with git commit timestamps.

5. **Whether you have ever accessed any RBC system, database, wiki, or training module related to cross-border payments, SWIFT, or correspondent banking** — even incidentally.

6. **Whether anyone at RBC knows you have programming skills or technology expertise** — this affects the "unrelated to duties" argument.

7. **Complete list of all devices, accounts, and tools used for BPI development** — to confirm no employer resource contamination.

8. **Whether your personal laptop has any RBC software installed** (VPN client, MDM, monitoring) — this is a potential contamination vector.

9. **Your annual RBC compensation** — relevant to the consideration adequacy analysis for the IP clause.

10. **Names of any people you discussed the BPI concept with before January 12, 2026** — potential corroboration witnesses for pre-employment conception.

### TOP 10 DOCUMENTS TO GATHER

1. **RBC offer letter** (complete) — look for: IP clause (known), non-compete clause, non-solicitation clause, garden leave clause, notice period, OBA provisions, confidentiality clause, termination provisions, governing law clause, severability clause.

2. **Any separate RBC IP/invention assignment agreement** — some employers have a separate form in addition to the offer letter. Check onboarding packet.

3. **RBC Code of Conduct** — the published version references IP. Obtain the full text if possible. Look for: definition of "Work Product," exceptions for personal projects, OBA policy, disclosure procedures.

4. **RBC IT Acceptable Use Policy** — look for: provisions on personal devices, personal cloud accounts, BYOD policy, monitoring disclosures.

5. **Pre-employment emails/messages about BPI concept** — search all personal accounts for anything dated before January 12, 2026 that references payment bridging, cross-border payments, fintech, or startup concepts.

6. **Git log export** — `git log --all --format="%H %ai %an %s"` — the complete commit history with timestamps, authors, and messages.

7. **Cloud access logs** — AWS/GCP CloudTrail or equivalent showing access patterns, source IPs, and devices. Export before logs rotate.

8. **AI tool conversation histories** — Claude, GitHub Copilot, or any other AI tool used in development. These show the creative process and confirm personal-account usage.

9. **Personal device purchase receipts** — proving the development hardware is personally owned, not employer-provided.

10. **RBC shift schedules or time records** — to cross-reference with git commit timestamps and demonstrate non-overlapping personal time.

### TOP 10 QUESTIONS FOR REAL COUNSEL

1. **Is the RBC IP assignment clause enforceable under BC employment law as applied to work that is (a) unrelated to my job duties, (b) created on personal time with personal equipment, and (c) in a different business domain than my role?**

2. **If a court were to review this clause, would it more likely (a) enforce it as written, (b) read it down to "course of employment" or "related to employer's business," or (c) strike it as unconscionable? What is the probability distribution across these outcomes?**

3. **Does the word "conceive" in the clause create an assignment of inventive concepts (patent rights), or does it apply only to tangible works (copyright)?** If it covers inventions, does a clean-room code rewrite address the patent ownership problem?

4. **Am I in breach of the mandatory disclosure obligation, and does this breach create independent legal exposure (e.g., disciplinary termination, strengthened IP claim, duty of good faith violation)?**

5. **What is the strongest pre-employment evidence I could assemble to rebut the presumption that BPI was created during employment?** How strong does it need to be? Does it need to show the complete inventive concept, or just the general idea?

6. **If clean-room reimplementation is recommended, what protocol would you consider legally defensible for a solo founder? Is the AI-as-clean-room-barrier approach (founder writes specification, AI implements independently) a viable strategy?**

7. **Should I resign before or after obtaining your opinion? Does continued employment extend my exposure?** Is there any advantage to requesting a release of IP claims as part of the resignation process?

8. **If I file a provisional patent, what is the probability that RBC discovers it, and what is their most likely response?** Is there a way to file that minimizes the discovery risk?

9. **Can I safely raise money from friends and family after receiving your opinion, assuming the opinion is cautiously favourable? What disclosures are required under NI 45-106 s.2.5?**

10. **What is the total realistic cost and timeline for resolving this IP question — from initial opinion through clean-room (if needed) through patent filing through incorporation?** I need to budget this against the $5K–$10K I have set aside.

---

*This analysis was prepared on March 23, 2026 as structured risk identification material. It is not legal advice and must not be relied upon as such. Every conclusion should be validated by qualified Canadian IP and employment counsel before action is taken.*

*Prepared with AI assistance (Claude, Anthropic). All legal citations should be verified by counsel — AI systems can hallucinate case citations and statutory references.*
