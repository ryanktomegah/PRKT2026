# LIP Current State

**Date:** 2026-04-28
**Status:** staging release candidate available; not production-final
**Primary release note:** [`operations/releases/staging-rc-2026-04-24.md`](operations/releases/staging-rc-2026-04-24.md)

This file is the canonical status bridge between active documentation and dated historical artifacts. Older model cards, research drafts, governance packs, and strategy memos may preserve March or early-April baseline numbers for auditability. When there is a conflict, use this file and the staging RC release note for current deployable truth.

---

## Product Functionality

LIP turns payment-network failure signals into auditable bridge-loan decisions for bank-operated deployments.

1. C5 normalises payment events from supported rails into the canonical event schema.
2. C1 predicts payment failure probability and applies the locked operating threshold `tau* = 0.110`.
3. C4 blocks disputed or contested payment contexts.
4. C6 blocks sanctions, AML velocity, and compliance-risk conditions.
5. C2 estimates borrower probability of default, LGD, and annualised fee pricing with rail-aware floors.
6. C7 applies execution controls, borrower enrollment, kill switch, KMS availability, durable offer logging, and human-review gates.
7. C3 monitors accepted offers against settlement telemetry and drives repayment/default state transitions.

The platform is designed for bank-side operation: the bank supplies capital, origination authority, compliance certification, and final acceptance; BPI supplies the licensed technology.

---

## Current Engineering State

| Area | Current state |
|---|---|
| C1 failure classifier | Staging RC trained and signed on 2026-04-24; 5M generated corpus, 2M training sample, 20 epochs. |
| C2 PD model | Staging RC trained and signed on 2026-04-24; 50k corpus, 50 Optuna trials, 5 LightGBM models, Tier-3 stress gate passed. |
| Runtime artifacts | Strict C1/C2 artifact loading verified on host and in the C7 container with fallback disabled. |
| Multi-rail code | SWIFT, SEPA, FedNow, RTP, CBDC retail, mBridge, and Nexus stub paths are represented in code/docs. |
| CBDC training coverage | DGEN now supports CBDC corridor generation, but the currently signed C1 RC artifact predates the post-CBDC retraining sprint. Retrain C1 before claiming CBDC-trained model coverage. |
| Sub-day rails | Rail-aware maturity, sub-day fee floor, rail-aware C3 TTL, cross-rail handoff detection, and rail-aware stress windows are implemented. |
| C7 container | Staging C7 image was built and strict artifact smoke-tested for the 2026-04-24 RC. |
| Engineering blockers | No known code blocker for staging validation. Production-final artifacts still require the full remote production-size C1 workflow after account billing/spend-limit repair. |

---

## Current Model Metrics

### C1 Staging RC

| Metric | Value |
|---|---:|
| Corpus | 5,000,000 generated payment rows |
| Training sample | 2,000,000 rows |
| Best chronological OOT AUC | 0.8839 |
| Post-training summary AUC | 0.887623 |
| LightGBM branch AUC | 0.886426 |
| PyTorch branch AUC | 0.884256 |
| Calibrated F2 threshold | 0.1100 |
| F2 score | 0.623269 |
| ECE | 0.188449 -> 0.069066 |

### C2 Staging RC

| Metric | Value |
|---|---:|
| Corpus | 50,000 records |
| Optuna trials | 50 |
| Ensemble size | 5 LightGBM models |
| Held-out AUC | 0.931482085175773 |
| Brier | 0.03374044185210159 |
| KS | 0.7380619645214892 |
| Tier-3 stress gate | Passed; 2,513 / 2,513 test-set Tier-3 PDs inside [0.05, 0.25] |

---

## Production Reality

The current state is strong enough for staging RC validation, not for uncontrolled production use.

Production-final status still requires:

1. Full remote production-size C1 retrain after billing/spend-limit repair.
2. Signed artifact promotion after reproducible training and validation.
3. Staging deployment smoke tests against the real API surface.
4. Durable offer-store and rollback drills.
5. Live pilot validation with bank-provided anonymised payment data.
6. Legal/patent/IP clearance before external disclosure or bank engagement.
7. Pilot-bank contract language for `hold_bridgeable` certification and required warranties.

Project Nexus is an active strategic threat to the SWIFT-first narrative. The counsel-session packet is [`legal/patent/project-nexus-counsel-session-2026-04-28.md`](legal/patent/project-nexus-counsel-session-2026-04-28.md).

---

## Documentation Policy

Active docs should link to this file when they include dated model metrics, pilot readiness claims, or legal/commercial status. Historical docs should not be rewritten destructively because their dated claims are part of the audit trail.

Use this rule:

- For current engineering execution, read this file first, then the release note, then active component docs.
- For model governance history, preserve the dated model cards and SR 11-7 pack, but interpret them through this file.
- For patent, IP, and RBC strategy material, preserve the historical record and follow counsel-reviewed status blocks before taking action.
