# LIP Prototype PoC Validation Report

**Generated**: 2026-03-15 20:12:29 UTC  
**Total generation+validation time**: 27.4s  
**Data type**: FULLY SYNTHETIC — no real transaction data  
**Regulatory tag**: EU AI Act Art.10 traceability (seed-controlled)  

---

## Summary

| Component | Records | Status | Key Metric |
|-----------|---------|--------|------------|
| C1 Payment Failure | 10,000 | ✅ pass | rate_err: 0.0 |
| C2 PD Borrowers | 10,000 | ✅ pass | Z-sep: True |
| C4 Dispute Classifier | 10,000 | ⚠️ warn | DISPUTE_CONFIRMED recall: 0.528 |
| C6 AML Anomaly | 10,000 | ✅ pass | precision: 1.0 |

---

## C1: Payment Failure Corpus

- **Records**: 10,000
- **Corpus tag**: `SYNTHETIC_CORPUS_C1`
- **All labels = 1 (RJCT)**: True
- **Corridor count**: 12
- **Temporal span**: 539.9 days (target: ~540)
- **Corridor rate max abs error**: 0.0 (target: <0.001)

**Rejection class distribution** (target: A≈35%, B≈45%, C≈15%, BLOCK≈5%):

| Class | Fraction | Target |
|-------|----------|--------|
| A | 0.351 | ~35% |
| B | 0.448 | ~45% |
| BLOCK | 0.050 | ~5% |
| C | 0.151 | ~15% |

> **Not measured**: C1 ML inference (GraphSAGE/TabTransformer). Trained AUC=0.9998 on 2K synthetic samples (commit `f38f0dc`). Estimated real-world AUC: 0.82–0.88 (requires SWIFT pilot data).

---

## C2: PD Borrower Corpus

- **Records**: 10,000
- **Corpus tag**: `SYNTHETIC_CORPUS_C2_V2`
- **Altman Z separation (healthy > default)**: True
- **Altman Z (healthy Tier-1 mean)**: 3.995
- **Altman Z (default Tier-1 mean)**: 1.33

**Tier distribution and default rates**:

| Tier | Weight | Default Rate | Target Rate | Tolerance |
|------|--------|-------------|-------------|-----------|
| 1 | 0.403 | 0.0268 | 0.03 | ±0.03 |
| 2 | 0.352 | 0.0616 | 0.06 | ±0.03 |
| 3 | 0.244 | 0.1482 | 0.12 | ±0.03 |

> **Not measured**: C2 PD model calibration (Merton/KMV/Altman ensemble). Requires real default history under QUANT sign-off.

---

## C4: Dispute Classifier

- **Records generated**: 10,000
- **Records evaluated**: 2000
- **Backend**: `MockLLMBackend`
- **Overall accuracy**: 0.599
- **DISPUTE_CONFIRMED recall**: 0.528 (threshold: ≥0.60)

**Per-class metrics**:

| Class | Precision | Recall | F1 | TP | FP | FN |
|-------|-----------|--------|----|----|----|----|
| NOT_DISPUTE | 0.531 | 0.894 | 0.667 | 802 | 707 | 95 |
| DISPUTE_CONFIRMED | 0.996 | 0.528 | 0.69 | 256 | 1 | 229 |
| DISPUTE_POSSIBLE | 1.0 | 0.056 | 0.106 | 23 | 0 | 386 |
| NEGOTIATION | 0.55 | 0.555 | 0.552 | 116 | 95 | 93 |

> **Known limitation**: `MockLLMBackend` has no negation awareness — pure keyword match. Results reflect prefilter pipeline only. For real LLM metrics, see P6 (requires Groq API key).

---

## C6: AML Anomaly Detector

- **Records**: 10,000
- **Train / Test split**: 8000 / 2000 (80/20)
- **AML flag rate**: 0.0785 (target: ~0.08)
- **Precision**: 1.0
- **Recall**: 0.244
- **F1**: 0.392
- **Accuracy**: 0.94

**AML pattern distribution** (ground truth labels from generator):

| Pattern | Count | Rate |
|---------|-------|------|
| clean | 9,215 | 0.921 |
| velocity_abuse | 247 | 0.025 |
| structuring | 233 | 0.023 |
| layering | 193 | 0.019 |
| high_risk_jurisdiction | 112 | 0.011 |

> **Note**: Isolation Forest is unsupervised — scores reflect density-based anomaly rather than supervised label alignment. Precision/recall is indicative only.

---

## What Is NOT Validated Here

| Item | Reason | Reference |
|------|--------|-----------|
| C1 ML inference AUC | Requires trained model artifacts | Commit `f38f0dc` (AUC=0.9998 synthetic) |
| C2 PD calibration | Requires real default history | QUANT sign-off pending |
| C3 repayment accuracy | Requires live UETR settlement tracking | Phase 2 |
| C4 negation handling | MockLLMBackend has no negation awareness | P6 (Groq API) |
| C7 kill switch / human override | See e2e pipeline tests | `test_e2e_pipeline.py` |
| End-to-end latency p99 | Benchmarked separately | `docs/benchmark-results.md` |

> All synthetic corpora are generated with fixed seed=42 for full reproducibility. No real transaction data, PII, or real bank identifiers are present in any corpus. EU AI Act Art.10 compliant.
