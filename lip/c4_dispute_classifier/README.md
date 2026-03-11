# C4: Dispute Classifier

## Role in Pipeline

C4 distinguishes **commercial disputes** (buyer-seller conflict that would make bridge lending inappropriate) from **operational failures** (technical or network issues that are valid bridge-lending candidates). It acts as a **hard block gate** — any payment classified as `DISPUTE_CONFIRMED`, `DISPUTE_POSSIBLE`, or `NEGOTIATION` is rejected before C2 prices it.

## Algorithm 1 Position

```
C1 → [C4] ∥ C6 → hard block? → C2
```

C4 and C6 run **in parallel** (Step 2 of Algorithm 1). C4's hard block is checked first; C6's block is checked second.

## Key Classes

| Class / Function | File | Description |
|-----------------|------|-------------|
| `DisputeClassifier` | `classifier.py` | Main entry point — keyword pre-filter → LLM classifier |
| `KeywordPrefilter` | `prefilter.py` | Fast rule-based dispute signal detection |
| `NegationHandler` | `negation.py` | Identifies negated dispute language ("no dispute") |
| `DisputeClass` | `taxonomy.py` | 4-class taxonomy enum |

## Inputs / Outputs

**Input** (passed by `LIPPipeline._run_c4`):

| Field | Type | Description |
|-------|------|-------------|
| `rejection_code` | str \| None | ISO 20022 rejection reason code |
| `narrative` | str \| None | Free-text payment narrative (up to 2048 chars) |
| `amount` | str | Transaction amount (string decimal) |
| `currency` | str | ISO 4217 currency code |
| `counterparty` | str | Sending BIC |

**Output** dict:

| Key | Description |
|-----|-------------|
| `dispute_class` | `DisputeClass` enum — see taxonomy below |
| `confidence` | Softmax confidence [0, 1] for the predicted class |
| `hard_block` | `True` for `DISPUTE_CONFIRMED`, `DISPUTE_POSSIBLE`, `NEGOTIATION` |

## Four-Class Taxonomy

| Class | Hard Block | Description |
|-------|-----------|-------------|
| `NOT_DISPUTE` | No | Operational / technical failure; bridge eligible |
| `DISPUTE_CONFIRMED` | **Yes** | Explicit buyer-seller conflict in narrative |
| `DISPUTE_POSSIBLE` | **Yes** | Ambiguous language; blocked conservatively |
| `NEGOTIATION` | **Yes** | Partial payment / resolution in progress |

## Timeout Fallback

When the LLM backend is unavailable or times out, C4 defaults to `DISPUTE_POSSIBLE` (hard block). This is a **conservative safety choice** — it may block legitimate loans but never funds a disputed payment.

## Configuration Parameters

| Parameter | Default | Source |
|-----------|---------|--------|
| `timeout_seconds` | 5.0 | `classifier.py` |
| `confidence_threshold` | 0.7 | `classifier.py` |

## Known Performance Gaps

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| False-negative rate | **8%** | **2%** | Needs LLM backend + better multilingual prefilter |

(`DISPUTE_FN_CURRENT = 0.08`, `DISPUTE_FN_TARGET = 0.02` in `constants.py`)

## Spec References

- Architecture Spec v1.2 §4.4 — `DisputeRequest` / `DisputeResponse` schemas
- Architecture Spec v1.2 §S4.4 — Four-class dispute taxonomy
- EU AI Act Art.13 — Transparency requirements for high-risk AI dispute classification
