# `lip/integrity/` — Integrity Shield

> **Structural prevention of "Delve-class" failure modes.** Every external claim BPI makes — compliance reports, breach disclosures, OSS attribution, vendor onboarding — must carry a cryptographic proof chain back to the underlying data. Uncorroborated assertions are structurally rejected by this layer before they can leave the platform.

**Source:** `lip/integrity/`
**Module count:** 8 modules + `__init__.py`
**Self-description:** *"Integrity Shield — structural prevention of Delve-class failure modes. Every external integrity artifact must carry a cryptographic proof chain back to the underlying data; uncorroborated assertions are structurally rejected."*

---

## Purpose

The Integrity Shield encodes a single discipline at the code level: **evidence before assertion.** It is the operational expression of `CLAUDE.md`'s rule that no agent may infer field semantics from names, computed statistics, or surface patterns alone. Where the rule applies to humans and AI agents writing code, the Integrity Shield applies to the platform's *outputs*: any artifact LIP emits to a regulator, a pilot bank, an investor, or the open-source community must be backed by an evidence chain that can be re-verified independently.

This is the defensive complement to the EPG decision layer. EPG-XX decisions describe *what we will and will not do*; `lip/integrity/` enforces *that we cannot accidentally claim something we did not do*.

---

## Modules

| File | Lines | Purpose |
|------|-------|---------|
| `breach_protocol.py` | 326 | The end-to-end protocol for handling a confirmed or suspected security / compliance breach. Drives notification timing (DORA Art. 19 thresholds: 4h initial, 24h intermediate, 1 month final), evidence preservation, and the cryptographic chain that ties the disclosure to the underlying incident data. |
| `claims_registry.py` | 212 | A signed, append-only registry of every public claim BPI has made — patent claims, marketing claims, compliance certifications, performance numbers. Each entry carries the evidence hash and the date the claim was made. Used to detect drift between what we say and what we can prove. |
| `compliance_enforcer.py` | 202 | Runtime enforcement: blocks any export, report, or external API response that fails the evidence-chain check. Wired into the `regulatory_router` and the BPI admin export endpoints. |
| `evidence.py` | 195 | The cryptographic primitives that make the proof chain work: hashing, signing, Merkle-tree assembly, witness generation. Anything that wants to *be* evidence must be passed through one of these helpers. |
| `oss_tracker.py` | 244 | Tracks every open-source dependency LIP uses, its license, its required attribution, and the proof that the attribution is in place. Generates the OSS attribution document on demand and refuses to certify if any dependency lacks an attribution record. |
| `pipeline_gate.py` | 116 | The pipeline-side gate. The main `lip/pipeline.py` does not import from `lip/integrity/` directly; instead, the gate registers callbacks that fire on outputs that *would* leave the platform (audit log exports, breach notifications, claim publications). |
| `vendor_attestation.py` | 236 | The attestation chain for any vendor BPI integrates with — pilot banks, ML model providers, sanctions list providers (OFAC/EU). Each vendor must produce a signed attestation of (a) what data they handle, (b) what controls are in place, (c) when the controls were last audited. Without an unexpired attestation, the vendor cannot be wired into production. |
| `vendor_validator.py` | 287 | Validates incoming vendor attestations against the schema, checks signatures, and refuses out-of-date or malformed records. |

---

## Why this exists (the "Delve-class" reference)

The module docstring's phrase "Delve-class failure modes" refers to a category of failure where an organisation makes a claim — about model performance, about compliance, about data lineage — that cannot be reproduced from the underlying records. The failure is structural, not malicious: it happens when there is no mechanism that *forces* the claim and the evidence to be linked.

`lip/integrity/` is that mechanism. Every external artifact carries a hash; every hash points to evidence; every piece of evidence is signed; every signature can be re-verified by an independent party. If the chain is broken, `compliance_enforcer.py` blocks the artifact at emission. There is no manual override. The rule is enforced at the type level: an artifact that has not been through `evidence.py` cannot be passed to any function that emits to an external interface.

## Where it sits

```
internal data (audit logs, model metrics, breach record, OSS deps)
   │
   ▼
evidence.py        ← hash + sign + witness
   │
   ▼
claims_registry.py ← append to signed registry
   │
   ▼
compliance_enforcer.py ← gate at emission
   │
   ▼
external surface (regulatory_router export, breach_protocol notification, attribution doc)
```

## Public API

The module's `__init__.py` is intentionally minimal — only the docstring. Callers must import the specific helper they need (`from lip.integrity.evidence import sign_artifact`, etc.). This is deliberate: there is no convenience facade that would let a careless caller bypass the gate.

## Cross-references

- **DORA Art. 19 threshold helpers**: `lip/common/regulatory_reporter.py` (`DORAAuditEvent.within_threshold`), consumed by `breach_protocol.py`
- **SR 11-7 model validation reports**: `lip/compliance/model_card_generator.py` produces them; `claims_registry.py` records them; `compliance_enforcer.py` gates them
- **EPG decisions that this layer protects**: every 🟡 entry in [`../../legal/decisions/README.md`](../../legal/decisions/README.md) — the Integrity Shield is what makes "we said X" verifiable against "we actually did X"
- **Patent claims**: `claims_registry.py` carries the published patent claims so `EPG-21` (language scrub) violations can be detected against the registry rather than against ad-hoc memory
