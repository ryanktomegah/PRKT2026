# `lip/compliance/` — Compliance Reporting Automation

> **Auto-generation of regulator-facing compliance artifacts** — SR 11-7 model cards, DORA Art. 19 incident reports, EU AI Act Art. 61 logging exports. Distinct from `docs/compliance.md` (which is the human-readable checklist) and from `lip/integrity/` (which gates emission of any external artifact).

**Source:** `lip/compliance/`
**Module count:** 1 module + `report_templates/` directory + `__init__.py`
**Self-description:** *"Compliance reporting automation — model cards, SR 11-7, DORA Art. 19, EU AI Act Art. 61."*

---

## Purpose

Three regulatory regimes require LIP to produce structured documents on a recurring or event-driven schedule:

1. **SR 11-7 (US Federal Reserve / OCC model risk management)** — every model in production must have a model card containing intended use, training data provenance, performance metrics, calibration evidence, limitations, and ongoing monitoring plan
2. **DORA Art. 19 (EU Digital Operational Resilience Act)** — incident reports at fixed thresholds (4h initial, 24h intermediate, 1 month final) for any major ICT-related incident
3. **EU AI Act Art. 61** — logging and post-market monitoring records for high-risk AI systems

Producing these documents by hand for every model and every release is unsustainable. `lip/compliance/` auto-generates them from runtime data: the model registry knows which models are in production, the audit log knows what happened, and the templates know what each regulator wants to see. The output is a draft document that the compliance team reviews and signs, but the structure, the numbers, and the evidence pointers are all generated.

---

## Modules

| File | Purpose |
|------|---------|
| `model_card_generator.py` | The auto-generator. Reads model registry entries (training data card, calibration metrics, validation cohort, drift detector state) and produces a SR 11-7 conformant model card as a structured document. Used to generate `docs/c1-model-card.md`, `docs/c2-model-card.md`, and similar artifacts. |
| `report_templates/` | Markdown / Jinja templates for each report type. SR 11-7 model card template, DORA Art. 19 incident template (4h / 24h / 1-month variants), EU AI Act Art. 61 logging export template. |

---

## Distinctions to keep clear

| Layer | Path | What it contains |
|-------|------|------------------|
| **Runbook checklist** | `docs/compliance.md` | Human-readable checklist of obligations — what we have to comply with, mapped to where the compliance is implemented |
| **Auto-generators** | `lip/compliance/` (this file) | Code that produces the artifacts the regulator actually receives |
| **Runtime reporters** | `lip/common/regulatory_reporter.py` | Runtime emission of DORA audit events with `within_threshold` calculations; `SR117ModelValidationReport` data structure; `RegulatoryReporter` class |
| **HTTP exposure** | `lip/api/regulatory_router.py`, `regulatory_service.py`, `regulatory_models.py` | The HTTP surface a regulator (or auditor) uses to fetch the generated artifacts |
| **Emission gate** | `lip/integrity/compliance_enforcer.py` | The structural check that refuses to emit any artifact whose evidence chain is broken |
| **Generated artifacts** | `docs/models/c1-model-card.md`, `docs/models/c1-training-data-card.md`, `docs/models/c2-model-card.md`, `docs/legal/c6_sanctions_audit.md`, `docs/legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md` | The actual output documents |

A compliance officer onboarding to LIP should read `docs/compliance.md` first (the checklist), then this file (the generator), then `lip/integrity/` (see [`integrity.md`](integrity.md)) to understand the gate, then the generated artifacts to see what the output looks like in practice.

## Cross-references

- **Compliance checklist (human-readable)**: [`../compliance.md`](../compliance.md)
- **Runtime reporters**: `lip/common/regulatory_reporter.py` (see [`common.md`](common.md))
- **HTTP surface**: `lip/api/regulatory_router.py` (see [`api.md`](api.md))
- **Emission gate**: `lip/integrity/compliance_enforcer.py` (see [`integrity.md`](integrity.md))
- **Operative compliance decisions**: [`../../legal/decisions/EPG-19_compliance_hold_bridging.md`](../../legal/decisions/EPG-19_compliance_hold_bridging.md), [`../../legal/decisions/EPG-16-18_aml_caps_human_review.md`](../../legal/decisions/EPG-16-18_aml_caps_human_review.md)
- **Full SR 11-7 governance pack**: [`../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md`](../../legal/governance/BPI_SR11-7_Model_Governance_Pack_v1.0.md)
