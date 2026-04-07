# LIP Codebase Reference

> **What this is.** A reference document for every substantive subsystem in the `lip/` Python package, beyond the eight primary components (C1–C8) that already have their own READMEs at `lip/c{N}_*/README.md`.
>
> **Why it exists.** The README advertises an "8-component pipeline" but the actual codebase contains at least 14 substantive subsystems. Patent families P5 (Cascade Engine) and P10 (Regulatory Data Product) live entirely inside `lip/` with no reader-facing documentation. The shared `common/` layer underpins everything but had no entry point. This directory closes those gaps.

**Last updated:** 2026-04-07
**Parent index:** [`../INDEX.md`](../INDEX.md)

---

## How to read this directory

Each file documents one subsystem. The format is the same throughout:

1. **Purpose** — what this subsystem does and why it exists
2. **Where it sits in the pipeline** — what calls it, what it calls
3. **Key files** — annotated list of the modules a reader needs to know
4. **Public API** — the symbols intended for use by other subsystems
5. **Cross-references** — canonical spec, related EPG decisions, related modules

This is **reference documentation**, not narrative. For the end-to-end story of how a payment moves through LIP, read [`../architecture.md`](../architecture.md) and the per-component READMEs in `lip/c{N}_*/README.md`. For *why* the code looks the way it does, read [`../decisions/README.md`](../decisions/README.md). For *what's blocking pilot*, read [`../OPEN_BLOCKERS.md`](../OPEN_BLOCKERS.md).

---

## Subsystem Index

### Core orchestration

| File | Subsystem | Path | Purpose |
|------|-----------|------|---------|
| [`pipeline.md`](pipeline.md) | End-to-end orchestrator | `lip/pipeline.py` | Implements Algorithm 1 — chains C5→C1→[C4∥C6∥C2]→C7→C3 with full audit trail |
| [`common.md`](common.md) | Shared infrastructure | `lip/common/` | Schemas, constants, state machines, encryption, business calendar, registries, used by every component |
| [`configs.md`](configs.md) | Canonical configuration | `lip/configs/` | YAML configuration files (canonical numbers, corridor defaults, rejection taxonomy) — the operative parameters of the platform |

### Eight primary components (already documented in `lip/c{N}_*/README.md`)

| Component | Path | README |
|-----------|------|--------|
| C1 — Failure Classifier | `lip/c1_failure_classifier/` | [`lip/c1_failure_classifier/README.md`](../../lip/c1_failure_classifier/README.md) |
| C2 — PD Model | `lip/c2_pd_model/` | [`lip/c2_pd_model/README.md`](../../lip/c2_pd_model/README.md) |
| C3 — Repayment Engine | `lip/c3_repayment_engine/` | [`lip/c3_repayment_engine/README.md`](../../lip/c3_repayment_engine/README.md) |
| C4 — Dispute Classifier | `lip/c4_dispute_classifier/` | [`lip/c4_dispute_classifier/README.md`](../../lip/c4_dispute_classifier/README.md) |
| C5 — Streaming | `lip/c5_streaming/` | [`lip/c5_streaming/README.md`](../../lip/c5_streaming/README.md) |
| C6 — AML / Velocity | `lip/c6_aml_velocity/` | [`lip/c6_aml_velocity/README.md`](../../lip/c6_aml_velocity/README.md) |
| C7 — Execution Agent | `lip/c7_execution_agent/` | [`lip/c7_execution_agent/README.md`](../../lip/c7_execution_agent/README.md) |
| C8 — License Manager | `lip/c8_license_manager/` | [`lip/c8_license_manager/README.md`](../../lip/c8_license_manager/README.md) |

### Forward-looking patent families

| File | Subsystem | Path | Patent |
|------|-----------|------|--------|
| [`c9_settlement_predictor.md`](c9_settlement_predictor.md) | C9 settlement-time forecaster | `lip/c9_settlement_predictor/` | Survival-analysis model for ETA bands |
| [`p5_cascade_engine.md`](p5_cascade_engine.md) | P5 supply-chain cascade engine | `lip/p5_cascade_engine/` | **P5 patent family** — corporate entity resolution, cascade propagation, intervention optimisation |
| [`p10_regulatory_data.md`](p10_regulatory_data.md) | P10 regulatory data product | `lip/p10_regulatory_data/` | **P10 patent family** — privacy-preserving systemic-risk analytics for regulators |

### Cross-cutting infrastructure

| File | Subsystem | Path | Purpose |
|------|-----------|------|---------|
| [`api.md`](api.md) | FastAPI surface | `lip/api/` | HTTP routers and services — admin, MIPLO, portfolio, regulatory, cascade, health |
| [`integrity.md`](integrity.md) | Integrity Shield | `lip/integrity/` | Evidence-before-assertion enforcement — breach protocol, claims registry, vendor attestation, OSS tracker |
| [`risk.md`](risk.md) | Portfolio risk | `lip/risk/` | VaR (Monte Carlo), concentration, stress testing, portfolio-level metrics |
| [`dgen.md`](dgen.md) | Synthetic data generation | `lip/dgen/` | Domain-realism corpora for C1/C2/C3/C4/C6 training and validation |
| [`compliance.md`](compliance.md) | Compliance reporting | `lip/compliance/` | Auto-generated SR 11-7 model cards, DORA Art. 19, EU AI Act Art. 61 templates |
| [`tests.md`](tests.md) | Test organisation | `lip/tests/` | Unit / integration / live / E2E layout, markers, infrastructure assumptions |
| [`scripts.md`](scripts.md) | CLI tools | `scripts/` and `lip/scripts/` | Training, monitoring, regulatory batch jobs |

---

## Coverage map (what is documented and where)

| Layer | Where | Coverage |
|-------|-------|----------|
| Architecture overview | [`../architecture.md`](../architecture.md) | ✅ Algorithm 1, state machines, Redis/Kafka maps |
| Per-component (C1–C8) | `lip/c{N}_*/README.md` | ✅ All eight |
| Canonical specs (prosecution-grade) | `consolidation files/BPI_C{N}_Component_Spec_v1.0*.md` | ✅ All eight; C3/C5/C7 split into Part1/Part2 |
| Migration / hardening specs | [`../specs/`](../specs/) | ✅ C1, C2, C3, C5, C6, C7 |
| Model cards (SR 11-7) | [`../c1-model-card.md`](../c1-model-card.md), [`c1-training-data-card.md`](../c1-training-data-card.md), [`c2-model-card.md`](../c2-model-card.md), [`c6_sanctions_audit.md`](../c6_sanctions_audit.md) | ✅ C1, C2, C6 |
| Forward-looking patents | [`../federated-learning-architecture.md`](../federated-learning-architecture.md), [`../cbdc-protocol-research.md`](../cbdc-protocol-research.md), `consolidation files/Future-Technology-Disclosure-v2.1.md` | ✅ P9, P12; P5/P10 documented here |
| Pipeline orchestrator | [`pipeline.md`](pipeline.md) | ✅ This directory |
| Shared `common/` layer | [`common.md`](common.md) | ✅ This directory |
| FastAPI surface | [`api.md`](api.md) | ✅ This directory |
| Integrity / breach protocol | [`integrity.md`](integrity.md) | ✅ This directory |
| Portfolio risk | [`risk.md`](risk.md) | ✅ This directory |
| Synthetic data generation | [`dgen.md`](dgen.md) + [`../data-pipeline.md`](../data-pipeline.md) | ✅ |
| Tests | [`tests.md`](tests.md) + `CLAUDE.md` § Test Suite Notes | ✅ |
| Configs (YAML) | [`configs.md`](configs.md) | ✅ This directory |

---

## Maintenance rule

When a new module is added to `lip/`, the contributor must update the relevant `docs/codebase/*.md` file in the same PR. When a new subsystem is added (e.g. a P11 patent family), add a new file in this directory and a row to the index above. The codebase reference and the actual code are version-locked — do not let them drift.
