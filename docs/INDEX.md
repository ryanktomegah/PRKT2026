# LIP / BPI Documentation Index

> **The front door.** This file exists because LIP's documentation is extensive but lives in three layers (root, `docs/`, `consolidation files/`). This index tells you, depending on who you are, exactly which files to read in what order.

**Last updated:** 2026-04-07
**Audience:** Banker · Developer · Investor · Compliance Officer · Patent Counsel · New Team Member

---

## The Three Documentation Layers

LIP documentation lives in three places. Knowing this is half the battle.

| Layer | Where | What it contains | Authority |
|---|---|---|---|
| **1. Root governance** | `/CLAUDE.md`, `/PROGRESS.md`, `/EPIGNOSIS_ARCHITECTURE_REVIEW.md`, `/CLIENT_PERSPECTIVE_ANALYSIS.md`, `/LIP_COMPLETE_NARRATIVE.md` | Team rules, constants lock, EPG decision register, internal audit, business archetypes, project narrative | **Operative** — code refuses to violate these |
| **2. `docs/` reader layer** | `docs/*.md` plus `docs/bank-pilot/`, `docs/fundraising/`, `docs/governance/`, `docs/specs/`, `docs/engineering/` | Architecture overview, API reference, model cards, compliance checklists, bank pilot kit, fundraising kit, founder protection, migration specs | **Reference** — for external readers and operators |
| **3. `consolidation files/` canonical specs** | `consolidation files/BPI_*.md`, `Provisional-Specification-v5.2.md`, etc. | Prosecution-grade C1–C7 component specs, architecture spec v1.2, sign-off records, gap analysis, patent provisional, financial model, GTM strategy | **Source of truth** for design and IP |

When the layers disagree, the order of authority is: **`CLAUDE.md` > `consolidation files/` canonical specs > `docs/` reader layer > everything else.** `CLAUDE.md` is the constitution. Everything else is interpretation.

---

## Read by Role

Pick your role. Read the files in the order shown. Do not skip ahead — each step assumes the previous.

### A. You are a Pilot Bank (RBC, etc.)

You want to understand what LIP does, whether you can deploy it, what it costs, and what you have to sign.

| # | File | Why |
|---|------|-----|
| 1 | [`README.md`](../README.md) | One-page overview, architecture diagram, patent moat |
| 2 | [`docs/bank-pilot/commercial-overview.md`](bank-pilot/commercial-overview.md) | What you get, what it does to your payment stream |
| 3 | [`docs/bank-pilot/integration-guide.md`](bank-pilot/integration-guide.md) | How LIP fits behind your SWIFT pacs.002 stream |
| 4 | [`docs/bank-pilot/demo-walkthrough.md`](bank-pilot/demo-walkthrough.md) | What a working demo looks like end-to-end |
| 5 | [`docs/bank-pilot/legal-prerequisites.md`](bank-pilot/legal-prerequisites.md) | Three-layer enrollment: License Agreement → MRFA → Borrower Registry |
| 6 | [`docs/bank-pilot/api-reference.md`](bank-pilot/api-reference.md) | Pydantic schemas you'll integrate against |
| 7 | [`decisions/EPG-04-05_hold_bridgeable.md`](decisions/EPG-04-05_hold_bridgeable.md) | **CRITICAL** — the `hold_bridgeable` certification flag your compliance system must emit. Without this, Class B is permanently block-all and you lose all B1 LIP revenue. |
| 8 | [`decisions/EPG-19_compliance_hold_bridging.md`](decisions/EPG-19_compliance_hold_bridging.md) | Why LIP will refuse to bridge any payment your AML system has flagged — and why arguing with this is futile |
| 9 | [`docs/bank-pilot/rbc-pilot-strategy.md`](bank-pilot/rbc-pilot-strategy.md) | (RBC-specific) tailored pilot approach |
| 10 | [`OPEN_BLOCKERS.md`](OPEN_BLOCKERS.md) | What still has to happen before LIP goes live |

**Critical context for bankers**: Three things must be true before LIP makes a single bridge offer in your environment:
1. Your bank has signed the BPI License Agreement (gives C8 a token)
2. Your bank has a signed MRFA from each corporate client (gives C7 authority to debit fees)
3. Each enrolled client's BIC is in the LIP Borrower Registry

Until step 3 is done for at least one client, every offer returns `BORROWER_NOT_ENROLLED`. This is the correct behavior, not a bug.

---

### B. You are a Developer (joining LIP, modifying a component, or integrating)

| # | File | Why |
|---|------|-----|
| 1 | [`README.md`](../README.md) | Repo layout, architecture diagram, components table |
| 2 | [`/CLAUDE.md`](../CLAUDE.md) | **Read this fully before touching any code.** Team agents, decision authority, refusal rules, canonical constants lock, never-commit list, test notes |
| 3 | [`docs/codebase/README.md`](codebase/README.md) | **Codebase reference** — every substantive subsystem in `lip/` (orchestrator, common, configs, api, integrity, risk, P5, P10, C9, dgen, compliance, tests, scripts) |
| 4 | [`docs/codebase/pipeline.md`](codebase/pipeline.md) | The end-to-end orchestrator — start here when reading code |
| 5 | [`docs/codebase/common.md`](codebase/common.md) | Shared infrastructure used by every component |
| 6 | [`docs/developer-guide.md`](developer-guide.md) | Setup, test commands, mock injection patterns |
| 7 | [`docs/architecture.md`](architecture.md) | Algorithm 1 step-by-step, state machines, Redis/Kafka maps |
| 8 | [`docs/engineering/default-execution-protocol.md`](engineering/default-execution-protocol.md) | **Mandatory** — the `codex/*` branch + plan/design + draft PR workflow every contributor must follow |
| 9 | [`lip/c{N}_*/README.md`](../lip/) | The README for whichever component you're touching (C1–C8) |
| 10 | [`consolidation files/BPI_C{N}_Component_Spec_v1.0*.md`](../consolidation%20files/) | **Source of truth** for that component's behaviour, state transitions, error codes |
| 11 | [`docs/specs/`](specs/) | Migration / hardening specs (C1 typing, C2 fee hardening, C3 state machine migration, C5 Kafka consumer, C6 velocity, C7 kill switch + offer routing) |
| 12 | [`docs/api-reference.md`](api-reference.md) | All Pydantic schemas + retention rules |
| 13 | [`docs/codebase/tests.md`](codebase/tests.md) | Test organisation, markers, infrastructure assumptions, flaky-test notes |
| 14 | [`PROGRESS.md`](../PROGRESS.md) | Most recent session log — what just changed, what's open |
| 15 | [`decisions/README.md`](decisions/README.md) | The EPG-XX decision register — *why* the code looks the way it does |

**Critical context for developers**: The constants in `lip/common/constants.py` (τ\* = 0.110, fee floor 300 bps, latency SLO 94ms, UETR TTL 45d, salt rotation 365d/30d overlap) are **locked**. Changing any of them requires QUANT sign-off. Touching fee math without QUANT sign-off will be refused at code review. Touching AML patterns and committing them to git will be refused by CIPHER. Read the **What Agents Will Push Back On** section of `CLAUDE.md` before your first PR.

---

### C. You are an Investor (FF round, due diligence, IP evaluation)

| # | File | Why |
|---|------|-----|
| 1 | [`README.md`](../README.md) | One-page positioning, patent moat, technology licensor model |
| 2 | [`LIP_COMPLETE_NARRATIVE.md`](../LIP_COMPLETE_NARRATIVE.md) | The full project story end-to-end |
| 3 | [`consolidation files/Investor-Briefing-v2.1.md`](../consolidation%20files/Investor-Briefing-v2.1.md) | The investor briefing |
| 4 | [`consolidation files/Founder-Financial-Model.md`](../consolidation%20files/Founder-Financial-Model.md) | The financial model |
| 5 | [`consolidation files/Revenue-Projection-Model.md`](../consolidation%20files/Revenue-Projection-Model.md) + [`Revenue-Acceleration-Analysis.md`](../consolidation%20files/Revenue-Acceleration-Analysis.md) + [`Unit-Economics-Exhibit.md`](../consolidation%20files/Unit-Economics-Exhibit.md) | Revenue, capital efficiency, unit economics |
| 6 | [`consolidation files/Capital-Partner-Strategy.md`](../consolidation%20files/Capital-Partner-Strategy.md) | Capital partner strategy |
| 7 | [`consolidation files/Market-Fundamentals-Fact-Sheet.md`](../consolidation%20files/Market-Fundamentals-Fact-Sheet.md) + [`Competitive-Landscape-Analysis.md`](../consolidation%20files/Competitive-Landscape-Analysis.md) | Market sizing and competitive landscape |
| 8 | [`consolidation files/GTM-Strategy-v1.0.md`](../consolidation%20files/GTM-Strategy-v1.0.md) + [`Master-Action-Plan-2026.md`](../consolidation%20files/Master-Action-Plan-2026.md) | Go-to-market and 2026 plan |
| 9 | [`docs/fundraising/ff-round-structure.md`](fundraising/ff-round-structure.md) | FF round structure |
| 10 | [`docs/fundraising/valuation-analysis.md`](fundraising/valuation-analysis.md) | Valuation analysis |
| 11 | [`docs/fundraising/safe-agreement-template.md`](fundraising/safe-agreement-template.md) | SAFE template |
| 12 | [`docs/fundraising/investor-risk-disclosure.md`](fundraising/investor-risk-disclosure.md) | Honest risk disclosure |
| 13 | [`docs/fundraising/ip-risk-pre-counsel-analysis.md`](fundraising/ip-risk-pre-counsel-analysis.md) | **140 KB pre-counsel deep-dive** on patent novelty, defensibility, and regulatory exposure |
| 14 | [`consolidation files/Patent-Family-Architecture-v2.1.md`](../consolidation%20files/Patent-Family-Architecture-v2.1.md) + [`Provisional-Specification-v5.2.md`](../consolidation%20files/Provisional-Specification-v5.2.md) | Patent family and provisional specification |
| 15 | [`consolidation files/Future-Technology-Disclosure-v2.1.md`](../consolidation%20files/Future-Technology-Disclosure-v2.1.md) | Forward-looking patent family (P9 CBDC, P12 federated learning, etc.) |
| 16 | [`docs/governance/Founder-Protection-Strategy.md`](governance/Founder-Protection-Strategy.md) | Founder protection mechanics |
| 17 | [`docs/fundraising/pre-fundraising-checklist.md`](fundraising/pre-fundraising-checklist.md) | Pre-fundraising checklist |

**Critical context for investors**: The `EPIGNOSIS_ARCHITECTURE_REVIEW.md` at the repo root is an **internal adversarial audit**, not investor disclosure. It exists to make the team disagree with itself before the market does. The 18-issue Master Issue Register inside it has been substantially closed (see GAP-01 through GAP-17 in `PROGRESS.md`). What is *not* closed are **legal/contractual blockers** — see [`OPEN_BLOCKERS.md`](OPEN_BLOCKERS.md). Engineering is done. Legal and patent filing are not.

---

### D. You are a Compliance Officer / Regulator

| # | File | Why |
|---|------|-----|
| 1 | [`docs/compliance.md`](compliance.md) | SR 11-7, EU AI Act Art. 9/13/14/17/61, DORA Art. 30, AML controls, GDPR — checklist form |
| 2 | [`decisions/EPG-19_compliance_hold_bridging.md`](decisions/EPG-19_compliance_hold_bridging.md) | **Definitive policy** — LIP NEVER bridges compliance-held payments. Three independent grounds (CIPHER/REX/NOVA). Defense in depth at two layers in code. |
| 3 | [`decisions/EPG-04-05_hold_bridgeable.md`](decisions/EPG-04-05_hold_bridgeable.md) | The `hold_bridgeable` certification API design — FATF-compliant, no tipping-off |
| 4 | [`decisions/EPG-14_borrower_identity.md`](decisions/EPG-14_borrower_identity.md) | Why the borrower is the originating bank, not the end customer |
| 5 | [`decisions/EPG-16-18_aml_caps_human_review.md`](decisions/EPG-16-18_aml_caps_human_review.md) | Per-licensee AML caps, explicit cap enforcement, EU AI Act Art. 14 human review routing |
| 6 | [`docs/c6_sanctions_audit.md`](c6_sanctions_audit.md) | C6 OFAC/EU sanctions screening audit |
| 7 | [`docs/c1-model-card.md`](c1-model-card.md) + [`c1-training-data-card.md`](c1-training-data-card.md) | C1 SR 11-7 model documentation + training data card |
| 8 | [`docs/c2-model-card.md`](c2-model-card.md) | C2 PD model card (B2B framing) |
| 9 | [`consolidation files/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](../consolidation%20files/BPI_SR11-7_Model_Governance_Pack_v1.0.md) | Full SR 11-7 governance pack |
| 10 | [`consolidation files/BPI_C6_Component_Spec_v1.0.md`](../consolidation%20files/BPI_C6_Component_Spec_v1.0.md) | C6 deep spec — sanctions, velocity, anomaly, salt rotation |

**Critical context for compliance**: LIP encodes EPG-19 (no compliance-hold bridging) at **two layers**: (1) all eight compliance-hold ISO 20022 codes (DNOR, CNOR, RR01–RR04, AG01, LEGL) are BLOCK class in `rejection_taxonomy.py`, short-circuiting the pipeline; and (2) `_COMPLIANCE_HOLD_CODES` in `agent.py` gates C7 even if Layer 1 is bypassed. There is no configuration that turns this off. The only path to bridging a held payment is for the bank's own compliance system to certify `hold_bridgeable=true` via the API in EPG-04/05, with the three warranties listed in that decision record.

---

### E. You are Patent Counsel

| # | File | Why |
|---|------|-----|
| 1 | [`docs/patent_counsel_briefing.md`](patent_counsel_briefing.md) | The briefing prepared for you |
| 2 | [`decisions/EPG-20-21_patent_briefing.md`](decisions/EPG-20-21_patent_briefing.md) | Core novel claims + language scrub rules + non-enumeration policy |
| 3 | [`consolidation files/Provisional-Specification-v5.2.md`](../consolidation%20files/Provisional-Specification-v5.2.md) | Current provisional specification |
| 4 | [`consolidation files/Patent-Family-Architecture-v2.1.md`](../consolidation%20files/Patent-Family-Architecture-v2.1.md) | Full patent family architecture |
| 5 | [`consolidation files/Future-Technology-Disclosure-v2.1.md`](../consolidation%20files/Future-Technology-Disclosure-v2.1.md) | Forward patents (P9, P12, etc.) |
| 6 | [`docs/federated-learning-architecture.md`](federated-learning-architecture.md) | P12 — FedProx + DP-SGD architecture |
| 7 | [`docs/cbdc-protocol-research.md`](cbdc-protocol-research.md) | P9 — mBridge / ECB DLT / FedNow research |
| 8 | [`docs/fundraising/ip-risk-pre-counsel-analysis.md`](fundraising/ip-risk-pre-counsel-analysis.md) | 140 KB pre-counsel novelty / defensibility analysis |
| 9 | [`consolidation files/BPI_Architecture_Specification_v1.2.md`](../consolidation%20files/BPI_Architecture_Specification_v1.2.md) | Architecture spec referenced by claims |

**Critical context for counsel**: The novel claim is **two-step classification + conditional offer logic**, not the bridge loan mechanics (JPMorgan US7089207B1 covers Tier 1 listed counterparties — LIP's contribution is Tier 2/3 private counterparties). EPG-21 forbids the words "AML", "SAR", "OFAC", "SDN", "compliance investigation", "tipping-off", "suspicious activity", and "PEP" anywhere in the published spec. Replace with: "classification gate", "hold type discriminator", "bridgeability flag", "procedural hold", "investigatory hold". The BLOCK code list must NOT appear in any claim — it is a circumvention roadmap.

---

### F. You are a New Team Member (any role)

Read in this exact order. Do not start coding until you have finished step 5.

1. [`README.md`](../README.md) — what LIP is in one page
2. [`LIP_COMPLETE_NARRATIVE.md`](../LIP_COMPLETE_NARRATIVE.md) — why it exists and how it got here
3. [`/CLAUDE.md`](../CLAUDE.md) — the team constitution; team agents (ARIA/NOVA/QUANT/CIPHER/REX/DGEN/FORGE), what each will refuse, canonical constants
4. [`EPIGNOSIS_ARCHITECTURE_REVIEW.md`](../EPIGNOSIS_ARCHITECTURE_REVIEW.md) — the internal audit that shaped current behaviour
5. [`decisions/README.md`](decisions/README.md) — the EPG-XX decision register
6. [`PROGRESS.md`](../PROGRESS.md) — what was done last session and what is open
7. [`docs/architecture.md`](architecture.md) — Algorithm 1 + state machines
8. [`docs/developer-guide.md`](developer-guide.md) + [`docs/engineering/default-execution-protocol.md`](engineering/default-execution-protocol.md) — how to work
9. [`OPEN_BLOCKERS.md`](OPEN_BLOCKERS.md) — what's blocking pilot launch (so you don't propose work that's already gated)

---

## Map of `docs/` (substantive files only)

```
docs/
├── INDEX.md                          ← YOU ARE HERE
├── OPEN_BLOCKERS.md                  ← Critical-path blockers (extracted from PROGRESS.md)
├── codebase/                         ← Reference docs for every subsystem in lip/
│   ├── README.md
│   ├── pipeline.md                   (lip/pipeline.py — Algorithm 1 orchestrator)
│   ├── common.md                     (lip/common/ — shared infrastructure)
│   ├── configs.md                    (lip/configs/ — canonical YAML)
│   ├── api.md                        (lip/api/ — FastAPI surface)
│   ├── integrity.md                  (lip/integrity/ — Integrity Shield)
│   ├── risk.md                       (lip/risk/ — portfolio risk)
│   ├── dgen.md                       (lip/dgen/ — synthetic data)
│   ├── compliance.md                 (lip/compliance/ — model card generator)
│   ├── tests.md                      (lip/tests/ — test organisation)
│   ├── scripts.md                    (scripts/ + lip/scripts/)
│   ├── c9_settlement_predictor.md    (forward-looking)
│   ├── p5_cascade_engine.md          (P5 patent family)
│   └── p10_regulatory_data.md        (P10 patent family)
├── decisions/                        ← ADR-style EPG-XX register
│   ├── README.md
│   ├── EPG-04-05_hold_bridgeable.md
│   ├── EPG-09-10_compliance_hold_audit.md
│   ├── EPG-14_borrower_identity.md
│   ├── EPG-16-18_aml_caps_human_review.md
│   ├── EPG-19_compliance_hold_bridging.md
│   └── EPG-20-21_patent_briefing.md
│
├── architecture.md                   ← Algorithm 1, state machines, constants
├── api-reference.md                  ← Pydantic schemas (C1–C8)
├── compliance.md                     ← SR 11-7, EU AI Act, DORA, AML, GDPR checklist
├── developer-guide.md                ← Setup, tests, mock injection
├── deployment.md                     ← Docker, K8s, HPA, secrets, health checks
├── data-pipeline.md                  ← dgen, training, model status
├── benchmark-results.md              ← p99 latency results
├── poc-validation-report.md          ← PoC validation metrics
├── c1-model-card.md                  ← C1 SR 11-7 model card (403 lines)
├── c1-training-data-card.md          ← C1 training data card
├── c2-model-card.md                  ← C2 PD model card
├── c6_sanctions_audit.md             ← C6 sanctions audit
├── cbdc-protocol-research.md         ← P9 CBDC/DLT research
├── federated-learning-architecture.md← P12 FedProx + DP-SGD
├── patent_counsel_briefing.md        ← Briefing for counsel
├── pedigree-rd-roadmap.md            ← R&D roadmap
├── technical-rd-memo.md              ← R&D status
├── bpi_license_agreement_clauses.md  ← License agreement clauses
│
├── bank-pilot/                       ← Bank pilot kit (7 docs, ~65 KB)
│   ├── commercial-overview.md
│   ├── rbc-pilot-strategy.md
│   ├── integration-guide.md
│   ├── legal-prerequisites.md
│   ├── demo-walkthrough.md
│   ├── gcp-demo-setup.md
│   └── api-reference.md
│
├── fundraising/                      ← Fundraising kit (9 docs, ~379 KB)
│   ├── ff-round-structure.md
│   ├── valuation-analysis.md
│   ├── safe-agreement-template.md
│   ├── nda-template.md
│   ├── investor-risk-disclosure.md
│   ├── pre-fundraising-checklist.md
│   ├── ip-risk-pre-counsel-analysis.md         (140 KB)
│   ├── ip-risk-pre-counsel-analysis-revised.md (50 KB)
│   └── ip-risk-analysis-prompt.md
│
├── governance/
│   └── Founder-Protection-Strategy.md
│
├── specs/                            ← Migration / hardening specs
│   ├── c1_inference_endpoint_typing.md
│   ├── c2_fee_formula_hardening.md
│   ├── c3_state_machine_migration.md
│   ├── c5_kafka_consumer_migration.md
│   ├── c6_velocity_sanctions_migration.md
│   ├── c7_kill_switch_migration.md
│   └── c7_offer_routing_migration.md
│
└── engineering/
    └── default-execution-protocol.md ← Mandatory contributor protocol
```

## Map of `consolidation files/` (canonical source-of-truth specs)

This directory is **not** linked from the legacy README. Use it whenever you need the prosecution-grade detail behind any component.

```
consolidation files/
├── Provisional-Specification-v5.2.md         ← Current patent provisional
├── Provisional-Specification-v5.1.md         ← Prior version
├── Patent-Family-Architecture-v2.1.md        ← Patent family map
├── Future-Technology-Disclosure-v2.1.md      ← Forward-looking patents
├── Academic-Paper-v2.1.md
│
├── BPI_Architecture_Specification_v1.2.md    ← Canonical architecture spec
├── BPI_Architecture_SignOff_Record_v1.1.md
├── BPI_Architecture_SignOff_Record_v1.2.md   ← Sign-off record (decisions trail)
├── BPI_Gap_Analysis_v2.0.md                  ← 18-issue gap analysis
├── BPI_Open_Questions_Resolution_v1.0.md
├── BPI_SR11-7_Model_Governance_Pack_v1.0.md  ← SR 11-7 pack
├── BPI_Internal_Build_Validation_Roadmap_v1.0.md
│
├── BPI_C1_Component_Spec_v1.0.md             (~34 KB)
├── BPI_C2_Component_Spec_v1.0.md             (~38 KB)
├── BPI_C3_Component_Spec_v1.0_Part1.md       ┐
├── BPI_C3_Component_Spec_v1.0_Part2.md       ┘ (~75 KB total)
├── BPI_C4_Component_Spec_v1.0.md             (~39 KB)
├── BPI_C5_Component_Spec_v1.0_Part1.md       ┐
├── BPI_C5_Component_Spec_v1.0_Part2.md       ┘ (~76 KB total)
├── BPI_C6_Component_Spec_v1.0.md             (~45 KB)
├── BPI_C7_Component_Spec_v1.0_Part1.md       ┐
├── BPI_C7_Component_Spec_v1.0_Part2.md       ┘ (~92 KB total)
├── BPI_C7_Bank_Deployment_Guide_v1.0.md
│
├── Founder-Financial-Model.md
├── Revenue-Projection-Model.md
├── Revenue-Acceleration-Analysis.md
├── Unit-Economics-Exhibit.md
├── Capital-Partner-Strategy.md
├── Investor-Briefing-v2.1.md
├── Market-Fundamentals-Fact-Sheet.md
├── Competitive-Landscape-Analysis.md
├── GTM-Strategy-v1.0.md
├── Operational-Playbook-v2.1.md
├── Master-Action-Plan-2026.md
├── Section-85-Rollover-Briefing-v1.1.md
│
├── P3-v0-Implementation-Blueprint.md         ← Forward patent blueprints
├── P4-v0-Implementation-Blueprint.md
├── P5-v0-Implementation-Blueprint.md
├── P7-v0-Implementation-Blueprint.md
├── P8-v0-Implementation-Blueprint.md
├── P10-v0-Implementation-Blueprint.md
│
└── DEVELOPMENT-START-PROMPT.md
```

---

## Quick Reference: "Where do I find...?"

| Question | File |
|---|---|
| What does LIP do? | `README.md` → `LIP_COMPLETE_NARRATIVE.md` |
| What's the patent moat? | `README.md` (one-line) → `consolidation files/Patent-Family-Architecture-v2.1.md` (full) |
| Why won't LIP bridge a compliance-held payment? | `decisions/EPG-19_compliance_hold_bridging.md` |
| Who is the borrower? | `decisions/EPG-14_borrower_identity.md` |
| What is `hold_bridgeable`? | `decisions/EPG-04-05_hold_bridgeable.md` |
| Why is Class B currently block-all? | `decisions/EPG-19_compliance_hold_bridging.md` (gating reason) + `OPEN_BLOCKERS.md` (unlock conditions) |
| What are the canonical constants and who can change them? | `CLAUDE.md` § Canonical Constants |
| Which agents own which decisions? | `CLAUDE.md` § Team Agents |
| What did the last engineering session do? | `PROGRESS.md` (top of file) |
| What's blocking pilot launch right now? | `OPEN_BLOCKERS.md` |
| What's the financial model? | `consolidation files/Founder-Financial-Model.md` |
| What's the SR 11-7 governance pack? | `consolidation files/BPI_SR11-7_Model_Governance_Pack_v1.0.md` |
| How do I run the tests? | `docs/developer-guide.md` |
| What does C{N} do in detail? | `consolidation files/BPI_C{N}_Component_Spec_v1.0*.md` |
| What's the contributor protocol? | `docs/engineering/default-execution-protocol.md` |
| What does the financial risk to investors look like? | `docs/fundraising/investor-risk-disclosure.md` + `docs/fundraising/ip-risk-pre-counsel-analysis.md` |

---

## Maintenance

When you add a substantive document, add a row to the role table(s) it serves, the docs/ map, and (if relevant) the Quick Reference. When you make a decision that constrains future work, add an EPG-XX file under `docs/decisions/` and update `docs/decisions/README.md`. When a blocker is resolved, move it to the bottom of `OPEN_BLOCKERS.md` under "Recently closed."

This index is the contract between LIP and any new reader. Keep it current.
