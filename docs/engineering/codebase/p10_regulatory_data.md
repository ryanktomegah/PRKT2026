# `lip/p10_regulatory_data/` — P10 Regulatory Data Product

> **Patent family P10.** A privacy-preserving systemic-risk analytics product designed for regulators (central banks, financial stability boards). Takes raw cross-border payment-failure data from LIP licensees, anonymises it under formal differential-privacy and k-anonymity guarantees, and emits trend, concentration, and contagion analyses with reproducible methodology appendices. **Until now, this entire patent family had no reader-facing documentation in the repo.**

**Source:** `lip/p10_regulatory_data/`
**Module count:** 17 modules + `__init__.py`
**Patent reference:** [`docs/engineering/blueprints/P10-v0-Implementation-Blueprint.md`](../blueprints/P10-v0-Implementation-Blueprint.md) (referenced via [`Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md))
**Sprint history:** Sprint 4a (anonymizer foundation) → 4b (systemic risk engine) → Sprint 5 (report generator)

---

## Purpose

LIP sits in a unique observational position: it sees real-time payment failures across multiple licensee banks' SWIFT streams. That dataset is **exactly** what financial-stability regulators need to detect emerging systemic stress — corridor concentration, circular exposure between counterparties, contagion risk between institutions — but it is **also** exactly the kind of dataset that, in raw form, would expose every licensee bank's commercial operations to its competitors and every customer to identification.

P10's contribution is to make that data shareable with regulators **without** disclosing licensee or customer identity. Every output of P10 carries a formal privacy proof (k-anonymity, differential privacy) plus a methodology appendix that lets the regulator (or an auditor working for the regulator) reproduce the analysis end-to-end without ever seeing the raw underlying records.

This is a patent because the construction is non-obvious: differential privacy is well-known in the literature, but composing it with the specific structure of cross-border payment-failure data (long-tailed corridor distributions, time-correlated cascades, sparse high-risk events) requires a privacy-budget allocator and a methodology layer that does not exist in the public DP literature.

---

## Module groups

### 1. Anonymisation foundation (Sprint 4a)

| File | Lines | Purpose |
|------|-------|---------|
| `anonymizer.py` | 252 | `RegulatoryAnonymizer` — the entry point. Takes raw payment-failure records and emits k-anonymised, differentially-private outputs. Composes the helpers in `privacy_audit.py` and budgets via `privacy_budget.py`. |
| `privacy_budget.py` | 82 | `PrivacyBudgetTracker` — the differential-privacy budget allocator. Each query against the anonymised dataset consumes ε from a fixed budget; once the budget is exhausted, further queries are refused. |
| `privacy_audit.py` | 364 | The audit suite — `KAnonymityProof`, `BudgetAuditResult`, `DPVerificationResult`, `AttackResult`, `PrivacyAuditReport`, plus the attack simulators (`frequency_attack`, `temporal_linkage_attack`, `uniqueness_attack`) and verifiers (`verify_budget_composition`, `verify_dp_distribution`, `k_anonymity_proof`, `generate_audit_report`). This is the **proof layer**: every output ships with these audits attached. |

### 2. Systemic risk engine (Sprint 4b)

| File | Lines | Purpose |
|------|-------|---------|
| `systemic_risk.py` | 269 | The top-level systemic-risk analyser. Composes concentration + contagion + circular-exposure analyses into a single regulator-facing report. |
| `concentration.py` | 107 | `ConcentrationResult`, `CorridorConcentrationAnalyzer` — Herfindahl–Hirschman Index (HHI) over corridors and counterparties; flags corridors approaching anti-competitive concentration |
| `contagion.py` | 191 | `ContagionNode`, `ContagionResult`, `ContagionSimulator` — BFS contagion simulation across the anonymised counterparty graph, modelling how a single institution's stress propagates outward |
| `circular_exposure.py` | 216 | `CircularExposure`, `detect_circular_exposures` — finds counterparty cycles (A funds B funds C funds A) that look stable bilaterally but are systemically fragile |

### 3. Report generator (Sprint 5)

| File | Lines | Purpose |
|------|-------|---------|
| `methodology.py` | 97 | `MethodologyAppendix` — the structured appendix object attached to every report; describes the exact transformations applied so the regulator can reproduce the analysis |
| `methodology_paper.py` | 190 | `MethodologyPaper`, `generate_methodology_paper` — the longer-form methodology document for the regulator's analytics team; includes formal proofs and parameter choices |
| `report_metadata.py` | 99 | Versioning and provenance metadata for every emitted report |
| `report_renderer.py` | 220 | JSON / CSV / PDF rendering with the methodology appendix embedded |
| `regulator_onboarding.py` | 240 | `ChecklistItem` — the per-regulator onboarding checklist (data-sharing agreement, key exchange, attack-model agreement, budget allocation) |

### 4. Telemetry & shadow infrastructure

| File | Lines | Purpose |
|------|-------|---------|
| `telemetry_collector.py` | 311 | Collects the per-licensee inputs that feed P10. Runs out-of-band from the main pipeline so it cannot delay any payment decision. |
| `telemetry_schema.py` | 78 | The wire format for telemetry submission |
| `shadow_data.py` | 189 | Generates synthetic shadow data for end-to-end testing of the privacy proof chain without using any real licensee data |
| `shadow_runner.py` | 163 | Drives the shadow data through the full anonymiser → analyser → report pipeline as a regression test for privacy guarantees |
| `constants.py` | 48 | P10-local constants (default ε, default k, attack threshold parameters) — separate from `lip/configs/canonical_numbers.yaml` |

---

## Privacy guarantees and what they actually mean

Every output of P10 carries:

- **k-anonymity proof** (`KAnonymityProof`): no record in the output can be re-identified as one of fewer than k underlying records, where k is configurable per regulator agreement
- **DP verification** (`DPVerificationResult`): the noise distribution applied to numeric outputs satisfies (ε, δ)-differential privacy with the parameters declared in the methodology appendix
- **Budget audit** (`BudgetAuditResult`): the cumulative ε spent across all queries against the same underlying dataset is within the agreed budget
- **Attack simulation results** (`AttackResult`): the same output, run through frequency / temporal-linkage / uniqueness attacks, fails to recover any underlying record above the agreed confidence threshold

A regulator receiving a P10 report can independently verify all four. The verifiers are exposed via `privacy_audit.py` and ship with the methodology appendix.

## Where it sits

P10 is **completely out-of-band** from the LIP base pipeline. There is no path from `lip/pipeline.py` into `lip/p10_regulatory_data/`. The data flow is:

```
licensee bank's LIP deployment
        │
        │  raw payment-failure records (audit log)
        ▼
   telemetry_collector.py (out-of-band, async)
        │
        ▼
   RegulatoryAnonymizer  ←  PrivacyBudgetTracker
        │                          ↑
        │                  privacy_audit (proofs attached)
        ▼
   systemic_risk.py (concentration + contagion + circular)
        │
        ▼
   report_renderer.py + methodology_paper.py
        │
        ▼
   regulator (out-of-band, signed delivery)
```

## Public API

Per `lip/p10_regulatory_data/__init__.py`, the exported symbols cover the full surface needed by an integrator: anonymisation, all four privacy proofs, the systemic-risk analysers, the report renderer, the methodology generators, and the regulator onboarding checklist.

## Patent context

P10 is its own patent in the BPI patent family. The patentable contribution is the **composition** — k-anonymity + (ε, δ)-DP + payment-failure-data structure + reproducible methodology appendix — not any single primitive. The same EPG-21 language scrub rules apply: no AML / SAR / OFAC / SDN / PEP terms in any published claim.

## Cross-references

- **Forward technology disclosure**: [`../../legal/patent/Future-Technology-Disclosure-v2.1.md`](../../legal/patent/Future-Technology-Disclosure-v2.1.md)
- **Patent family map**: [`../../legal/patent/Patent-Family-Architecture-v2.1.md`](../../legal/patent/Patent-Family-Architecture-v2.1.md)
- **Related forward-looking patents**: P5 (cascade engine, see [`p5_cascade_engine.md`](p5_cascade_engine.md)), P9 (CBDC, see [`../../models/cbdc-protocol-research.md`](../../models/cbdc-protocol-research.md)), P12 (federated learning, see [`../../models/federated-learning-architecture.md`](../../models/federated-learning-architecture.md))
- **Integrity layer**: P10 reports are emitted through `lip/integrity/compliance_enforcer.py` so the proof chain is gated end-to-end (see [`integrity.md`](integrity.md))
