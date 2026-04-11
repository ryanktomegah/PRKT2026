# LIP Documentation Index

**This is your entry point.** Find your role below and follow the reading path. All paths are relative to this file (`docs/`).

---

## Reading Paths by Role

### A. New Team Member / Contributor

Start here to understand what you're working on:

1. [`../README.md`](../README.md) — Project overview, architecture diagram, quick start
2. [`engineering/architecture.md`](engineering/architecture.md) — Algorithm 1, component pipeline, state machines, Redis/Kafka schemas
3. [`engineering/developer-guide.md`](engineering/developer-guide.md) — Setup, test commands, agent team structure, canonical constants
4. [`engineering/data-pipeline.md`](engineering/data-pipeline.md) — Synthetic data generation, training workflow, artefact policy
5. [`engineering/codebase/README.md`](engineering/codebase/README.md) — Subsystem reference index (C1–C8, P5, P10, API, risk)
6. [`../CLAUDE.md`](../CLAUDE.md) — Agent team roles, non-negotiable rules, EPG decisions summary

---

### B. Engineer (Component Work)

7. [`engineering/specs/BPI_Architecture_Specification_v1.2.md`](engineering/specs/BPI_Architecture_Specification_v1.2.md) — Full architecture specification
8. [`engineering/specs/`](engineering/specs/) — Component specs (BPI_C1–C7) and migration specs (22 files)
9. [`engineering/blueprints/`](engineering/blueprints/) — P3–P10 implementation blueprints
10. [`legal/decisions/`](legal/decisions/) — EPG decision register (EPG-04 through EPG-21)
11. [`engineering/OPEN_BLOCKERS.md`](engineering/OPEN_BLOCKERS.md) — Current engineering blockers
12. [`engineering/review/2026-04-08/INDEX.md`](engineering/review/2026-04-08/INDEX.md) — Code review findings (13 batches, B1–B13)
13. [`engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md`](engineering/review/EPIGNOSIS_ARCHITECTURE_REVIEW.md) — Deep architecture audit (87 KB)
14. [`engineering/default-execution-protocol.md`](engineering/default-execution-protocol.md) — Mandatory execution protocol for all agents

---

### C. Compliance Officer / Regulator

1. [`legal/compliance.md`](legal/compliance.md) — SR 11-7, EU AI Act Art.9/13/14/17/61, DORA Art.30, AML, GDPR
2. [`models/c1-model-card.md`](models/c1-model-card.md) — C1 model card (AUC 0.8871, τ★=0.110, ECE 0.069)
3. [`models/c2-model-card.md`](models/c2-model-card.md) — C2 model card (B2B MRFA, Tier 1/2/3 PD, 300 bps floor)
4. [`models/c1-training-data-card.md`](models/c1-training-data-card.md) — Training data card (EU AI Act Art.10)
5. [`legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md) — SR 11-7 governance pack
6. [`legal/governance/BPI_Architecture_SignOff_Record_v1.2.md`](legal/governance/BPI_Architecture_SignOff_Record_v1.2.md) — Architecture sign-off record
7. [`legal/decisions/EPG-19_compliance_hold_bridging.md`](legal/decisions/EPG-19_compliance_hold_bridging.md) — Never-bridge rule (unanimous team decision, three legal grounds)
8. [`engineering/poc-validation-report.md`](engineering/poc-validation-report.md) — PoC validation on synthetic corpus (C1/C2/C4/C6)

---

### D. Patent Counsel

1. [`legal/patent/Provisional-Specification-v5.2.md`](legal/patent/Provisional-Specification-v5.2.md) — Latest provisional specification
2. [`legal/patent/Patent-Family-Architecture-v2.1.md`](legal/patent/Patent-Family-Architecture-v2.1.md) — Patent family architecture (P1–P12)
3. [`legal/patent/patent_claims_consolidated.md`](legal/patent/patent_claims_consolidated.md) — Consolidated claims
4. [`legal/patent/Future-Technology-Disclosure-v2.1.md`](legal/patent/Future-Technology-Disclosure-v2.1.md) — Future technology disclosure
5. [`legal/patent/patent_counsel_briefing.md`](legal/patent/patent_counsel_briefing.md) — Pre-session briefing for counsel
6. [`legal/decisions/EPG-20-21_patent_briefing.md`](legal/decisions/EPG-20-21_patent_briefing.md) — Language scrub rules (no AML/SAR/OFAC in claims)
7. [`engineering/research/Academic-Paper-v2.1.md`](engineering/research/Academic-Paper-v2.1.md) — Academic publication draft
8. [`legal/patent/Provisional-Specification-v5.1.md`](legal/patent/Provisional-Specification-v5.1.md) — Prior provisional (v5.1, for comparison)

---

### E. Pilot Bank Contact (RBC)

1. [`business/bank-pilot/rbc-pilot-strategy.md`](business/bank-pilot/rbc-pilot-strategy.md) — Pilot approach and strategy
2. [`business/bank-pilot/commercial-overview.md`](business/bank-pilot/commercial-overview.md) — Commercial overview and value proposition
3. [`business/bank-pilot/integration-guide.md`](business/bank-pilot/integration-guide.md) — Technical integration guide
4. [`business/bank-pilot/api-reference.md`](business/bank-pilot/api-reference.md) — API reference for bank integration
5. [`business/bank-pilot/demo-walkthrough.md`](business/bank-pilot/demo-walkthrough.md) — Demo walkthrough script
6. [`business/bank-pilot/gcp-demo-setup.md`](business/bank-pilot/gcp-demo-setup.md) — GCP demo environment setup
7. [`business/bank-pilot/legal-prerequisites.md`](business/bank-pilot/legal-prerequisites.md) — Legal prerequisites before pilot
8. [`legal/decisions/EPG-04-05_hold_bridgeable.md`](legal/decisions/EPG-04-05_hold_bridgeable.md) — `hold_bridgeable` certification API (FATF R.13 structure)

---

### F. DevOps / Infrastructure

1. [`operations/deployment.md`](operations/deployment.md) — Docker, Kubernetes, Helm, HPA configuration
2. [`engineering/architecture.md`](engineering/architecture.md) — Redis schemas, Kafka topics, service topology
3. [`engineering/benchmark-results.md`](engineering/benchmark-results.md) — p99 latency = 0.29ms (warm path), SLO = 94ms
4. [`engineering/benchmark-data/`](engineering/benchmark-data/) — Raw benchmark CSV and JSON
5. [`operations/Operational-Playbook-v2.1.md`](operations/Operational-Playbook-v2.1.md) — Operational runbook

---

### G. Investor / Business Strategy

1. [`business/LIP_COMPLETE_NARRATIVE.md`](business/LIP_COMPLETE_NARRATIVE.md) — Business model, patent moat, pipeline walkthrough
2. [`business/CLIENT_PERSPECTIVE_ANALYSIS.md`](business/CLIENT_PERSPECTIVE_ANALYSIS.md) — Bank COO perspective, 5 critical gaps, 7 client archetypes
3. [`business/Competitive-Landscape-Analysis.md`](business/Competitive-Landscape-Analysis.md) — Competitive landscape
4. [`business/Market-Fundamentals-Fact-Sheet.md`](business/Market-Fundamentals-Fact-Sheet.md) — Market fundamentals
5. [`business/Investor-Briefing-v2.1.md`](business/Investor-Briefing-v2.1.md) — Investor briefing
6. [`business/GTM-Strategy-v1.0.md`](business/GTM-Strategy-v1.0.md) — Go-to-market strategy
7. [`business/fundraising/`](business/fundraising/) — Fundraising materials (SAFE, NDA, valuation, IP risk analysis)

---

## Map of `docs/`

```
docs/
├── INDEX.md                              ← You are here
│
├── engineering/                          ← For developers and engineers
│   ├── architecture.md                   ← Algorithm 1, state machines, Redis/Kafka schemas, patent mapping
│   ├── developer-guide.md                ← Setup, test commands, agent roles, contribution guidelines
│   ├── api-reference.md                  ← REST API reference
│   ├── data-pipeline.md                  ← Synthetic data generation, training, artefact policy
│   ├── benchmark-results.md              ← p99 latency benchmarks (warm: 0.29ms, cold: varies)
│   ├── poc-validation-report.md          ← PoC validation results (C1/C2/C4/C6 on synthetic corpus)
│   ├── OPEN_BLOCKERS.md                  ← Current engineering and legal blockers
│   ├── DEVELOPMENT-START-PROMPT.md       ← Claude Code session initialisation prompt
│   ├── default-execution-protocol.md     ← Mandatory execution protocol for all agents
│   ├── specs/                            ← Component specs + migration/hardening specs
│   │   ├── BPI_Architecture_Specification_v1.2.md
│   │   ├── BPI_C1_Component_Spec_v1.0.md through BPI_C7 (11 files)
│   │   ├── BPI_C7_Bank_Deployment_Guide_v1.0.md
│   │   ├── BPI_Gap_Analysis_v2.0.md
│   │   ├── BPI_Internal_Build_Validation_Roadmap_v1.0.md
│   │   ├── BPI_Open_Questions_Resolution_v1.0.md
│   │   └── c1_inference_endpoint_typing.md … c7_offer_routing_migration.md (7 migration specs)
│   ├── blueprints/                       ← Patent family implementation blueprints
│   │   └── P3-v0 through P10-v0 Implementation Blueprint (6 files)
│   ├── codebase/                         ← Subsystem reference docs
│   │   ├── README.md                     ← Index of subsystem docs
│   │   └── api.md, common.md, pipeline.md, risk.md … (13 files)
│   ├── review/                           ← Code review and architecture audit
│   │   ├── EPIGNOSIS_ARCHITECTURE_REVIEW.md  ← 87 KB deep architecture audit (19 issues)
│   │   └── 2026-04-08/                   ← Code review (13 batches, B1–B13 findings)
│   │       ├── INDEX.md
│   │       └── 01-integrity-common.md … 13-tests.md
│   ├── research/                         ← Academic and R&D output
│   │   ├── Academic-Paper-v2.1.md
│   │   ├── pedigree-rd-roadmap.md
│   │   └── technical-rd-memo.md
│   └── benchmark-data/                   ← Raw benchmark data files
│       ├── c5_baseline_10ktps.csv
│       └── c5_baseline_10ktps.json
│
├── legal/                                ← For compliance officers, regulators, counsel
│   ├── compliance.md                     ← SR 11-7, EU AI Act Art.9/13/14/17/61, DORA Art.30, AML, GDPR
│   ├── bpi_license_agreement_clauses.md  ← BPI license agreement clause library
│   ├── c6_sanctions_audit.md             ← C6 sanctions screening audit trail
│   ├── patent/                           ← Patent specifications and briefings
│   │   ├── Provisional-Specification-v5.2.md  ← Latest provisional (canonical)
│   │   ├── Provisional-Specification-v5.1.md
│   │   ├── Patent-Family-Architecture-v2.1.md
│   │   ├── Future-Technology-Disclosure-v2.1.md
│   │   ├── patent_claims_consolidated.md
│   │   └── patent_counsel_briefing.md
│   ├── decisions/                        ← EPIGNOSIS decision register
│   │   ├── README.md                     ← Decision register index
│   │   ├── EPG-04-05_hold_bridgeable.md  ← hold_bridgeable certification API
│   │   ├── EPG-09-10_compliance_hold_audit.md
│   │   ├── EPG-14_borrower_identity.md   ← B2B MRFA, governing law from BIC
│   │   ├── EPG-16-18_aml_caps_human_review.md
│   │   ├── EPG-19_compliance_hold_bridging.md  ← NEVER bridge compliance holds
│   │   └── EPG-20-21_patent_briefing.md  ← Language scrub, claim scope
│   └── governance/                       ← Formal sign-off and governance records
│       ├── BPI_Architecture_SignOff_Record_v1.1.md
│       ├── BPI_Architecture_SignOff_Record_v1.2.md
│       ├── BPI_SR11-7_Model_Governance_Pack_v1.0.md
│       └── Founder-Protection-Strategy.md
│
├── business/                             ← For pilots, investors, strategy
│   ├── CLIENT_PERSPECTIVE_ANALYSIS.md   ← Bank COO perspective, 5 critical gaps, 7 archetypes
│   ├── LIP_COMPLETE_NARRATIVE.md         ← Business model (3 phases), patent moat, pipeline walkthrough
│   ├── Competitive-Landscape-Analysis.md
│   ├── Market-Fundamentals-Fact-Sheet.md
│   ├── Investor-Briefing-v2.1.md
│   ├── GTM-Strategy-v1.0.md
│   ├── Capital-Partner-Strategy.md
│   ├── Founder-Financial-Model.md
│   ├── Revenue-Projection-Model.md
│   ├── Revenue-Acceleration-Analysis.md
│   ├── Unit-Economics-Exhibit.md
│   ├── Section-85-Rollover-Briefing-v1.1.md
│   ├── fundraising/                      ← Fundraising materials
│   │   ├── safe-agreement-template.md
│   │   ├── nda-template.md
│   │   ├── valuation-analysis.md
│   │   ├── ff-round-structure.md
│   │   ├── ip-risk-pre-counsel-analysis.md
│   │   ├── investor-risk-disclosure.md
│   │   └── pre-fundraising-checklist.md
│   └── bank-pilot/                       ← RBC pilot kit
│       ├── rbc-pilot-strategy.md
│       ├── commercial-overview.md
│       ├── integration-guide.md
│       ├── api-reference.md
│       ├── demo-walkthrough.md
│       ├── gcp-demo-setup.md
│       └── legal-prerequisites.md
│
├── operations/                           ← For DevOps and deployment
│   ├── deployment.md                     ← K8s, Helm, HPA, Docker images, CI/CD pipeline
│   ├── Operational-Playbook-v2.1.md      ← Operational runbook
│   └── Master-Action-Plan-2026.md        ← 2026 operational action plan
│
├── models/                               ← For ML engineers and auditors
│   ├── c1-model-card.md                  ← M-01: AUC 0.8871, τ★=0.110, ECE 0.069, GraphSAGE+TabTransformer+LightGBM
│   ├── c2-model-card.md                  ← M-02: B2B MRFA, Merton/KMV, Damodaran, Altman Z', Tier 1/2/3 PD
│   ├── c1-training-data-card.md          ← 10M synthetic corpus, 20 corridors, 200 BICs (EU AI Act Art.10)
│   ├── federated-learning-architecture.md ← P12 patent: FedProx, DP-SGD (ε=1.0, δ=1e-5)
│   └── cbdc-protocol-research.md         ← P9 patent: mBridge, ECB DLT, FedNow analysis
│
└── superpowers/                          ← Sprint planning artefacts (preserved)
    ├── plans/                            ← Sprint implementation plans
    └── specs/                            ← Sprint design specs
```

---

## Quick Reference

| What you want | Where to look |
|---------------|---------------|
| Run the tests | `PYTHONPATH=. python -m pytest lip/tests/ -m "not slow"` |
| Lint the code | `ruff check lip/` |
| Start local infra | `docker compose up -d && bash scripts/init_topics.sh` |
| Train C1 model | `PYTHONPATH=. python lip/train_all.py --component c1` |
| Fee floor value | `lip/common/constants.py` — `FEE_FLOOR_BPS = 300` |
| C1 threshold (τ★) | `lip/common/constants.py` — `TAU_STAR = 0.110` |
| Why we never bridge compliance holds | [`legal/decisions/EPG-19_compliance_hold_bridging.md`](legal/decisions/EPG-19_compliance_hold_bridging.md) |
| Current open blockers | [`engineering/OPEN_BLOCKERS.md`](engineering/OPEN_BLOCKERS.md) |
| Latest code review | [`engineering/review/2026-04-08/INDEX.md`](engineering/review/2026-04-08/INDEX.md) |
| Patent latest draft | [`legal/patent/Provisional-Specification-v5.2.md`](legal/patent/Provisional-Specification-v5.2.md) |
| RBC pilot kit | [`business/bank-pilot/`](business/bank-pilot/) |
| C1 model card | [`models/c1-model-card.md`](models/c1-model-card.md) |
| Architecture diagram | [`engineering/architecture.md`](engineering/architecture.md) |
| EPG decision register | [`legal/decisions/`](legal/decisions/) |

---

## Maintenance

- When adding a new doc, add it to this index under the appropriate role-based path and docs/ map
- When a decision is made (EPG-XX), add it to `legal/decisions/` and update `legal/decisions/README.md`
- Model cards must be updated whenever a model is retrained (REX authority)
- `engineering/OPEN_BLOCKERS.md` is the authoritative blocker list — keep it current
- Sprint plans go in `superpowers/plans/`, design specs in `superpowers/specs/`
