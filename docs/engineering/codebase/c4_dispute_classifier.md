# `lip/c4_dispute_classifier/` — LLM-Backed Dispute Detection

> **The last gate before a loan offer.** After C1 says "this will probably fail" (above τ\*), C4 asks "is the failure narrative a dispute or a routine processing error?" A dispute answer hard-blocks the pipeline — no C2 pricing happens, no C7 loan offer is generated.

**Source:** `lip/c4_dispute_classifier/`
**Module count:** 10 files, 2,373 LoC
**Test files:** 5 (`test_c4_{api,backends,contraction_expansion,dispute,llm_integration}.py`)
**Spec:** [`../specs/BPI_C4_Component_Spec_v1.0.md`](../specs/BPI_C4_Component_Spec_v1.0.md)
**Model card:** [`../../models/c4-model-card.md`](../../models/c4-model-card.md)

---

## Purpose

C4 is a **compliance gate**, not just a narrative classifier. Bridging a payment under active fraud/dispute investigation creates:

- FATF R.21 structuring/layering typology violations (CIPHER)
- AMLD6 Art.10 legal-person criminal liability (REX)
- Structurally broken settlement path — UETR never settles, disputed payment may be clawed back (NOVA)

C4 is defense-in-depth **Layer 1** of the dispute block. Layer 2 is the `_COMPLIANCE_HOLD_CODES` list in C7's `agent.py`. Both must independently hard-block dispute-coded payments. Never assume one catches what the other misses.

---

## Two-stage pipeline

### Stage 1 — Prefilter (`prefilter.py`, `negation.py`, `multilingual.py`)

Pure Python, deterministic, runs first on every C4 invocation. Catches ~95%+ of disputes with no LLM call.

**Keyword heads** (exact wording locked):
- fraud, unauthori[sz]ed, dispute, chargeback, investigation, SAR, frozen, legal-hold

**Negation awareness** — critical. Without it the prefilter fires on "no fraud detected" (false positive). The `negation.py` module has 500 synthetic test cases across 5 categories (20 templates × 5 languages). Post-hardening FP rate: **4%**, FN rate: **1%** on the negation suite.

**Multilingual coverage** — EN / FR / DE / ES / IT / JA keyword variants. Real pilot banks handle non-English narratives, and the prefilter cannot defer to the LLM on every foreign-language narrative for latency reasons.

### Stage 2 — LLM classifier (`model.py::DisputeClassifier`, `backends.py`)

Runs only when prefilter hits. Few-shot structured-output prompt to an OpenAI-compatible API. Default backend: **Groq `qwen/qwen3-32b`**.

Backend selection (`LIP_C4_BACKEND` env var):

| Value | Provider | When used |
|-------|----------|-----------|
| `groq` (staging default) | Groq | Live |
| `github_models` | GitHub-hosted OpenAI | Legacy CI |
| `openai_compat` | Any OpenAI-API endpoint | Self-hosted vLLM for on-prem pilots |
| `mock` (test default) | `MockLLMBackend` | Tests only — NEVER production |

Fallback to mock in production is a **P0 incident**. Monitor for `"C4 using MockLLMBackend"` at CRITICAL.

---

## The taxonomy (`taxonomy.py`)

`DisputeClass` enum:

| Class | Downstream effect |
|-------|-------------------|
| `DISPUTE_CONFIRMED` | Hard block — `PipelineResult.outcome = DISPUTE_BLOCKED` |
| `DISPUTE_POSSIBLE` | Hard block — same as above (belt-and-braces: no bridging when in doubt) |
| `NO_DISPUTE` | Pipeline proceeds to C6 AML check |

`_DISPUTE_BLOCK_CLASSES` in `lip/pipeline.py` is the frozenset of which `DisputeClass` values block — both `DISPUTE_CONFIRMED` and `DISPUTE_POSSIBLE` are in it.

---

## Circuit breaker

`_api_circuit_breaker` in `backends.py` opens after 5 consecutive timeout or 5xx responses from the LLM endpoint. While open, C4 returns `DISPUTE_POSSIBLE` with confidence 0.0 and rationale `"circuit breaker open"`.

This is a **fail-safe**: when the LLM is down, every payment is treated as potentially disputed until the endpoint recovers. Loans are blocked rather than accidentally bridged. The alternative (fail-open to `NO_DISPUTE`) would be catastrophic — an LLM outage would translate into bridging every disputed payment in the corridor.

Recovery: 30-second exponential backoff with jitter, half-open state on first success.

---

## Language scrub (EPG-21)

C4 public-facing documentation MUST NOT use these terms:

| Banned | Approved |
|--------|----------|
| "AML classifier" | "Narrative-content classifier" |
| "SAR detection" | "Dispute-indicator classifier" |
| "OFAC awareness" | "Text-content filter" |
| "compliance investigation detector" | "Bridgeability precondition" |
| "PEP screening" | (say nothing) |
| "tipping-off defense" | (say nothing) |

CIPHER and REX have joint veto over outward copy. This rule applies to:
- Patent filings
- BPI marketing website
- Licensee pilot collateral
- Regulator-facing documentation (use the approved terms there too — the regulator doesn't care about the name, they care about the control)

Internal docs (including this one) use the honest terms.

---

## Groq / Qwen3 constraints (CLAUDE.md § C4 LLM Backend Rules)

1. **Model is locked at `qwen/qwen3-32b`.** Do NOT switch without a full 100-case negation corpus run.
2. **Never add `stop=["\n"," "]`** to Qwen3 calls — breaks generation inside `<think>` blocks. Use `/no_think` in system prompt + regex strip only.
3. **Models in `models.list()` can 403.** Check project permissions at console.groq.com before assuming a model is available.
4. **Always benchmark through the full pipeline**, not raw LLM calls — the prefilter masks FN differences.
5. **Never conclude on FP/FN from < 100 cases** — small samples produce misleading zeros.
6. **`openai>=1.0.0` required** in the lip-api image (Dockerfile.c7). Without it, `create_backend` silently falls back to MockLLMBackend.

---

## Training (`training.py`)

Not training in the ML-weights sense — this file contains:

- Prompt generation utilities
- Evaluation harness for the 500-case negation corpus
- FP/FN calibration logic for tuning the keyword head cutoffs
- Groq-request retry logic

Run the evaluation:

```bash
PYTHONPATH=. python scripts/evaluate_c4_on_negation_corpus.py --n-per-category 100
```

Before any model / prompt change:
1. Full 600+ case evaluation must be re-run
2. Delta FP / FN recorded in [`../../models/c4-model-card.md`](../../models/c4-model-card.md) § 4
3. REX sign-off required before merge

---

## Consumers

| Consumer | How it uses C4 |
|----------|---------------|
| `lip/pipeline.py::LIPPipeline.process_event` | Calls `c4_classifier.classify` in parallel with C6; blocks on `DISPUTE_CONFIRMED / POSSIBLE` |
| `lip/c4_dispute_classifier/api.py` | Standalone HTTP surface for external testing |
| `lip/api/runtime_pipeline.py` | Constructs `DisputeClassifier()` with defaults (reads env for backend selection) |

---

## What C4 does NOT do

- **Does not classify the BIC's sanctions status** — that is C6's job. C4 reads the narrative only.
- **Does not verify the rejection code** — C5's event normalizer validates the envelope upstream.
- **Does not learn from operator overrides** — the LLM is stateless and the prompt is frozen. Override telemetry is preserved for future fine-tuning but does not affect the live classifier.
- **Does not price anything** — C2's job. C4 is a binary gate.

---

## Cross-references

- **Pipeline** — [`pipeline.md`](pipeline.md) § step 3a
- **Spec** — [`../specs/BPI_C4_Component_Spec_v1.0.md`](../specs/BPI_C4_Component_Spec_v1.0.md)
- **Model card** — [`../../models/c4-model-card.md`](../../models/c4-model-card.md)
- **EPG-19 / EPG-21** — [`../../legal/decisions/EPG-19_compliance_hold_bridging.md`](../../legal/decisions/EPG-19_compliance_hold_bridging.md), [`EPG-20-21_patent_briefing.md`](../../legal/decisions/EPG-20-21_patent_briefing.md)
- **Groq ToS** — [`../review/2026-04-17/week-2-code-quality/groq-qwen3-tos-review.md`](../review/2026-04-17/week-2-code-quality/groq-qwen3-tos-review.md)
- **Canonical notes** — `CLAUDE.md` § C4 Dispute Classifier Notes + C4 LLM Backend Rules
