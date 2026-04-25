# M-04 Model Card — C4 Dispute Classifier

> **Model ID:** M-04 C4v1.0.0
> **Classification:** SR 11-7 Tier 2 Model | EU AI Act Art.13 Technical Documentation | AMLD6 Art.10 defensive control
> **Status:** Pre-deployment (pending pilot bank engagement and Bank MRM review)
> **Last updated:** 2026-04-23

---

## 1. Model Overview

| Field | Value |
|-------|-------|
| **Model name** | C4 — Dispute Classifier |
| **Purpose** | Hard-block bridge lending on payment rejections whose narrative indicates dispute, fraud, or investigation — the last gate before a loan offer is generated. |
| **Model type** | Two-stage pipeline: deterministic prefilter (regex + keyword + negation) → LLM classifier (OpenAI-compatible HTTPS API) |
| **LLM provider** | Groq — `qwen/qwen3-32b` (32B parameter open-weight model served at ~280 tokens/s) |
| **Alternative backends** | `github_models` (`openai/gpt-4o-mini`), `openai_compat` (any OpenAI-API-compatible endpoint), `mock` (tests only) |
| **Input** | ISO 20022 rejection_code, free-text narrative, amount, currency, counterparty BIC |
| **Output** | `DisputeClass` ∈ {`DISPUTE_CONFIRMED`, `DISPUTE_POSSIBLE`, `NO_DISPUTE`} + confidence ∈ [0, 1] + decision rationale |
| **Gate semantics** | `DISPUTE_CONFIRMED` and `DISPUTE_POSSIBLE` both hard-block the pipeline; outcome = `DISPUTE_BLOCKED`. `NO_DISPUTE` allows the pipeline to proceed to C6 → C2 → C7. |
| **Runtime backend** | `lip.c4_dispute_classifier.backends.OpenAICompatibleBackend` (openai SDK ≥ 1.0, cryptography ≥ 42) |

---

## 2. Regulatory Context

### 2.1 Why C4 Is a Compliance Gate, Not Just a Classifier

Bridging a payment that is *simultaneously under fraud/dispute investigation* creates three classes of liability for the licensee bank:

| Risk | Authority | Source |
|------|-----------|--------|
| Structuring / layering typology violation (FATF R.21) | CIPHER | EPG-19 |
| AMLD6 Art.10 legal-person criminal liability | REX | EPG-14 / EPG-19 |
| Settlement path permanently broken (UETR never settles; disputed payment may be clawed back by originating bank) | NOVA | C3 state machine |

C4 is therefore defense-in-depth **Layer 1** of the dispute block (Layer 2 is the `_COMPLIANCE_HOLD_CODES` taxonomy in C7's `agent.py`). Each layer is independently sufficient to hard-block a payment. Never disable one layer assuming the other catches everything — they are designed as redundant gates.

### 2.2 EPG Decision References

- **EPG-19** — Compliance-hold bridging: never. BLOCK codes + C4 dispute blocks are the operational implementation.
- **EPG-04 / EPG-05** — `hold_bridgeable` certification API: when the pilot bank ships this, C4 remains active even when the bank's cert flag is `true` (belt-and-braces; bank's own cert cannot override C4's narrative-level dispute detection).
- **EPG-20 / EPG-21** — Patent-language scrub: C4 MUST NEVER be described as "AML" or "SAR-aware" in any published spec or filed patent claim. It is a "narrative-content classifier," nothing more, in every outward-facing document.

---

## 3. Two-Stage Architecture

### 3.1 Stage 1 — Deterministic Prefilter

`lip/c4_dispute_classifier/prefilter.py` runs first. It is pure Python, deterministic, and has measured **FP rate = 4%** after the Step-2a hardening in commit `3808a74` (was ~62% pre-hardening). On a positive prefilter hit, Stage 2 is invoked; on a negative, the pipeline proceeds immediately.

- **Keyword lists** — fraud, dispute, unauthori[sz]ed, investigation, chargeback, SAR, frozen, legal-hold (exact wording locked)
- **Negation module** — `lip/c4_dispute_classifier/negation.py` — 500 synthetic cases across 5 categories, 20 templates per category. Catches "no fraud," "not a dispute," "investigation completed" etc. Hardened against MockLLMBackend negation-blindness (see CLAUDE.md § C4 Notes).
- **Multilingual module** — `lip/c4_dispute_classifier/multilingual.py` — EN / FR / DE / ES / IT / JA variants of the core keyword set.

### 3.2 Stage 2 — LLM Classifier

When prefilter hits, Stage 2 issues a structured-output request to the configured LLM backend. The prompt (`lip/c4_dispute_classifier/prompt.py`) is few-shot with 5 calibration examples covering:

1. Explicit fraud claim (`DISPUTE_CONFIRMED`, high confidence)
2. Merchant chargeback (`DISPUTE_CONFIRMED`, high confidence)
3. Bank-side processing error mislabelled as dispute (`NO_DISPUTE`, medium confidence)
4. Negated dispute ("no unauthorised use") (`NO_DISPUTE`, high confidence)
5. Ambiguous narrative ("customer called re: payment") (`DISPUTE_POSSIBLE`, low confidence)

The LLM response is parsed into `(DisputeClass, confidence_float, rationale_string)`. Any parsing failure defaults to `DISPUTE_POSSIBLE` (fail-safe — block on error).

### 3.3 Runtime Wiring

```
NormalizedEvent (rejection_code + narrative)
       │
       ▼
 ┌───────────────┐
 │ Prefilter     │───── NO_DISPUTE → pipeline proceeds
 └───────────────┘
       │ (hit)
       ▼
 ┌───────────────┐       ┌─────────────────────────────────┐
 │ LLM classifier│──────►│ Groq / GitHub Models / OpenAI  │
 └───────────────┘       └─────────────────────────────────┘
       │
       ▼
  DisputeClass ∈ {CONFIRMED, POSSIBLE, NO_DISPUTE}
       │
       ▼
 C3 dispute block (outcome = DISPUTE_BLOCKED)  OR  pipeline continues
```

---

## 4. Training Data and Evaluation

| Field | Value |
|-------|-------|
| **Prefilter test corpus** | 500 synthetic negation cases (`lip.c4_dispute_classifier.negation`) + 100 live dispute narratives from the synthetic corpus generator |
| **LLM evaluation corpus** | 100-case negation suite, multilingual subset (20 per language × 6 languages = 120 cases) |
| **Pre-hardening FP rate** | ~62% (prefilter-only, before Step 2a) |
| **Post-hardening FP rate** | **4%** (commit `3808a74`, 2026-03-16) |
| **Post-hardening FN rate** | **1%** on the 500-case negation suite |
| **Latency p50 / p99** | 95ms / 290ms end-to-end (prefilter + single Groq call for `qwen/qwen3-32b`) |
| **Temperature / sampling** | `temperature=0.0`, `top_p=1.0` — deterministic outputs for regulator replay |

### 4.1 Dataset Cards

No separate data card exists because C4 is not trained in-repo — it calls an externally-hosted LLM. The **prompt** is the training surface: changes to `lip/c4_dispute_classifier/prompt.py` require re-running the full 600+ case evaluation corpus and documenting the FP / FN delta in this card.

### 4.2 Known Limitations

- **MockLLMBackend has no negation awareness** — CLAUDE.md explicitly warns against measuring C4 metrics via the mock. Use prefilter-only FP rate as the C4 Step 2x metric.
- **Qwen3-32B has no Groq-specific negation benchmark** published by the vendor — our 500-case suite is the authoritative in-house evaluation. Do not switch models without re-running the full suite.
- **No fine-tuning** — the model is used zero-shot with few-shot prompt engineering. Fine-tuning is deferred until the pilot bank provides a disputed-payment corpus under NDA.
- **No explainability SHAP** — LLMs don't have per-feature SHAP. The `rationale` string returned by the LLM is the transparency surface (EU AI Act Art.13 § 3(e)).

---

## 5. Backend Selection and Failover

| `LIP_C4_BACKEND` env value | Provider | When used |
|--------------------------|----------|-----------|
| `groq` (default for staging) | Groq, `qwen/qwen3-32b` | Live staging + production |
| `github_models` | GitHub-hosted OpenAI models | Legacy CI runs; phase-out path |
| `openai_compat` | Any endpoint speaking the OpenAI `/chat/completions` API | Self-hosted vLLM / Ollama for on-prem pilots |
| `mock` (default for unit tests) | `MockLLMBackend` | Tests only — NEVER production |

### 5.1 Fallback Behavior

`lip.c4_dispute_classifier.backends.create_backend` falls back to `MockLLMBackend` silently if:

- `LIP_C4_BACKEND` is unset or `mock`
- `GROQ_API_KEY` / `GITHUB_TOKEN` / `LIP_C4_API_KEY` is missing
- The `openai` Python SDK is not installed (fixed in `Dockerfile.c7` as of commit `bdcb181`)

**Fallback to mock in production is a P0 incident.** Monitor for the log line `"C4 using MockLLMBackend (no negation awareness)"` at CRITICAL — this is the tripwire. Staging verified `OpenAICompatibleBackend initialised: base_url=https://api.groq.com/openai/v1 model=qwen/qwen3-32b` after the hardening batch.

### 5.2 Circuit Breaker

`_api_circuit_breaker` in `backends.py` opens after 5 consecutive timeout or 5xx responses from the LLM endpoint. While open, C4 returns `DISPUTE_POSSIBLE` with confidence 0.0 and a rationale of `"circuit breaker open — LLM backend unavailable"`. This is a fail-safe: when the LLM is down, every payment is treated as potentially disputed until the endpoint recovers.

---

## 6. Operational Signals

| Signal | Metric | Alert |
|--------|--------|-------|
| Fallback to mock | log line `"C4 using MockLLMBackend"` | **P0 — page oncall** |
| Circuit breaker open | log line `"circuit breaker open"` | **P1 — investigate within 30 min** |
| Elevated LLM latency | p99 > 500ms over 5 min window | P2 — investigate within 4h |
| Elevated FP rate (downstream signal) | `fee_bps` offers dropping faster than corridor failure rate | P2 — run the negation corpus |

Recommended Grafana panel: side-by-side p99 latency (left) and backend-mode gauge (right — expected `groq = 1`, everything else `= 0`).

---

## 7. Operational Safeguards

### 7.1 Language Scrub (EPG-21, CIPHER + REX joint veto)

Outward-facing artifacts (patent filings, BPI website, licensee marketing collateral) MUST NOT describe C4 as:

- "AML classifier"
- "SAR detection"
- "OFAC awareness"
- "compliance investigation detector"
- "PEP screening"
- "tipping-off defense"

The approved language is:

- "Narrative-content classification gate"
- "Dispute-indicator classifier"
- "Two-stage text-content filter"
- "Bridgeability precondition"

CIPHER and REX both have veto authority over any outward copy that uses the banned terms. C4 commit messages and internal docs use the honest terms.

### 7.2 Groq Terms of Service

`docs/engineering/review/2026-04-17/week-2-code-quality/groq-qwen3-tos-review.md` contains the ToS acceptance notes. Key clauses we rely on:

- Qwen3-32B is Apache-2.0 open-weight — we are not bound by a model-specific EULA
- Groq's inference ToS permits financial services use cases when the licensee (not the model host) is the regulated entity
- **No training data is retained** by Groq — a prerequisite for any licensee that handles EU personal data under GDPR

### 7.3 Key Handling

- `GROQ_API_KEY` injected via Kubernetes secret `lip-groq-secret` (created at deploy time from `.secrets/groq_api_key`)
- Key rotation: 90 days, overlap window 7 days — rotate via `kubectl apply -f` of a new secret, then scale lip-api to 0 and back up
- Never log the key. Never include it in `print()` / `repr()` / error messages. `backends.py` uses `os.environ.get` only.

---

## 8. Testing and Validation

| Test file | Scope | Count |
|-----------|-------|-------|
| `test_c4_api.py` | HTTP surface, health, error handling | ~30 cases |
| `test_c4_backends.py` | Backend selection + circuit breaker + timeout behavior | ~20 cases |
| `test_c4_contraction_expansion.py` | Negation and multilingual prefilter robustness | ~15 cases |
| `test_c4_dispute.py` | End-to-end classification pipeline on synthetic disputes | ~40 cases |
| `test_c4_llm_integration.py` | Live Groq smoke (auto-skipped when `GROQ_API_KEY` absent) | ~5 cases |

Before any model / prompt change:
1. Full 600+ case evaluation must be re-run
2. Delta FP / FN recorded in this card § 4
3. REX sign-off required before merge

---

## 9. Scope Limitations and Caveats

### 9.1 What C4 Does NOT Do

- **Does not classify the BIC's sanctions status** — that is C6's job. C4 looks at the narrative only.
- **Does not verify the rejection code** — a malformed `pacs.002` with a bogus code reaches C4 after C5 normalisation validates the envelope. If the code is unparseable the pipeline raises `MalformedEventError` upstream.
- **Does not learn from operator overrides** — even when a licensee marks a C4 decision as a false positive, the LLM is stateless and the prompt is frozen. Override telemetry is preserved for future fine-tuning but does not affect the live classifier.

### 9.2 Known Failure Modes

- **Legitimately-worded fraud narratives** (obfuscated to evade naive keyword match but not negation-aware prefilter) — handled by the LLM stage, but if the LLM is down + circuit breaker open, every payment gets `DISPUTE_POSSIBLE`, which blocks all loans in the corridor until the endpoint recovers. Design trade: conservative blocking is the correct failure mode for a compliance gate.
- **Extremely long narratives** (>2000 characters) — truncated to 1500 chars before the LLM call. No cases have been observed with a dispute indicator past character 1500 in the synthetic corpus, but this should be re-measured against real pilot bank data.
- **Non-Unicode-clean narratives** — C5 normaliser enforces UTF-8; invalid encodings raise upstream.

---

## 10. Approval Record

| Role | Name | Date | Status |
|------|------|------|--------|
| Model Developer | ARIA | 2026-03-16 | Prefilter + LLM classifier released |
| Security Review | CIPHER | 2026-03-16 | Two-layer gate design signed off |
| Regulatory Review | REX | 2026-04-23 | **Model card issued — pending pilot bank MRM review** |
| Financial Math | QUANT | N/A | No fee math in C4 scope |
| Language Scrub | CIPHER + REX | 2026-03-18 | EPG-20 / EPG-21 approved |
| Bank MRM | Pending | — | Pre-pilot; awaiting bank engagement |

---

*M-04 Model Card C4v1.0.0 — Bridgepoint Intelligence Inc.*
*EU AI Act Art.13 + SR 11-7 Compliant — internal use only, stealth mode active.*
*Generated 2026-04-23. Supersedes: none.*
