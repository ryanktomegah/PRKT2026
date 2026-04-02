# C1 Inference Endpoint Hardening — Pydantic Strict Typing

**Status:** Implemented  
**Priority:** 7 (post-migration hardening)  
**Owner:** ARIA  
**Reviewers:** REX (EU AI Act §13), QUANT (latency SLO)

---

## 1. Rationale

The C1 inference gRPC endpoint was migrated to Python without changing its language.  
This spec hardens the API contract by:

- Defining all request/response objects using Pydantic `BaseModel` with strict field typing.
- Returning structured `ClassifyError` objects on validation failure rather than raw Python exceptions or HTTP 500 responses.
- Maintaining full backwards compatibility with the existing `predict(payment: dict) → dict` signature used by the orchestrator and Triton integration.
- Meeting EU AI Act Art.13 obligations (explainability via SHAP) and QUANT latency SLO (≤94 ms P99).

---

## 2. Input/Output Contract

### 2.1 `ClassifyRequest` (input)

| Field              | Type           | Required | Description                                  |
|--------------------|----------------|----------|----------------------------------------------|
| `payment_id`       | `str \| None`  | No       | Idempotency key; logged but not used in model |
| `sending_bic`      | `str`          | Yes      | ISO 9362 BIC (8 or 11 chars)                 |
| `receiving_bic`    | `str`          | Yes      | ISO 9362 BIC (8 or 11 chars)                 |
| `amount_usd`       | `float`        | Yes      | Notional amount ≥ 0.01 USD                   |
| `currency_pair`    | `str`          | Yes      | Format `"CCY1_CCY2"` (e.g. `"USD_EUR"`)      |
| `transaction_type` | `str \| None`  | No       | ISO 20022 message type (e.g. `"pacs.002"`)   |
| `timestamp_utc`    | `float \| None`| No       | POSIX timestamp; defaults to `time.time()`   |
| `metadata`         | `dict \| None` | No       | Pass-through; not used in model               |

**Validation rules:**
- `amount_usd` must be ≥ 0.01 (minimum meaningful payment).
- `sending_bic` and `receiving_bic` must be 8 or 11 characters.
- `currency_pair` must match `^[A-Z]{3}_[A-Z]{3}$`.

### 2.2 `SHAPEntry` (component of response)

| Field     | Type    | Description                          |
|-----------|---------|--------------------------------------|
| `feature` | `str`   | Feature name from tabular engineer    |
| `value`   | `float` | Integrated-gradient SHAP attribution |

### 2.3 `ClassifyResponse` (success output)

| Field                    | Type           | Description                                    |
|--------------------------|----------------|------------------------------------------------|
| `failure_probability`    | `float`        | Sigmoid output ∈ [0, 1]                        |
| `above_threshold`        | `bool`         | `failure_probability >= threshold_used`        |
| `inference_latency_ms`   | `float`        | Wall-clock latency in ms                       |
| `threshold_used`         | `float`        | Decision threshold applied                     |
| `corridor_embedding_used`| `bool`         | `True` if stored embedding found               |
| `shap_top20`             | `list[SHAPEntry]` | Top-20 feature attributions by \|value\|    |
| `payment_id`             | `str \| None`  | Echo of `ClassifyRequest.payment_id`           |

### 2.4 `ClassifyError` (validation/runtime failure output)

| Field        | Type          | Description                                    |
|--------------|---------------|------------------------------------------------|
| `error_type` | `str`         | `"VALIDATION_ERROR"` or `"INFERENCE_ERROR"`    |
| `message`    | `str`         | Human-readable description                     |
| `field`      | `str \| None` | Field name for field-level validation errors   |
| `payment_id` | `str \| None` | Echo of `payment_id` if available              |

---

## 3. API Methods

### 3.1 Existing (backwards-compatible, unchanged)

```python
InferenceEngine.predict(payment: dict) -> dict
```

Accepts raw dict; returns raw dict.  No schema enforcement.  Kept for orchestrator/Triton compatibility.

### 3.2 New typed method

```python
InferenceEngine.predict_validated(
    payment: dict | ClassifyRequest,
) -> ClassifyResponse | ClassifyError
```

- Validates input using `ClassifyRequest` Pydantic model.
- Returns `ClassifyResponse` (Pydantic model) on success.
- Returns `ClassifyError` with `error_type="VALIDATION_ERROR"` on schema violation.
- Returns `ClassifyError` with `error_type="INFERENCE_ERROR"` on unexpected runtime failure.

### 3.3 Convenience function (updated)

```python
run_inference_typed(
    payment: dict | ClassifyRequest,
    model: ClassifierModel | None = None,
    embedding_pipeline: CorridorEmbeddingPipeline | None = None,
    threshold: float = _DEFAULT_THRESHOLD,
) -> ClassifyResponse | ClassifyError
```

---

## 4. Test / Failure Matrix

| Scenario                         | Expected output                            |
|----------------------------------|--------------------------------------------|
| Valid minimal request            | `ClassifyResponse` with all required keys  |
| Valid request with metadata      | `ClassifyResponse` (metadata ignored)      |
| `amount_usd` = 0 or negative     | `ClassifyError(error_type="VALIDATION_ERROR", field="amount_usd")` |
| `sending_bic` = "" (empty)       | `ClassifyError(error_type="VALIDATION_ERROR", field="sending_bic")` |
| `sending_bic` = 5 chars (invalid length) | `ClassifyError(error_type="VALIDATION_ERROR", field="sending_bic")` |
| `currency_pair` = "USDEUR" (no underscore) | `ClassifyError(error_type="VALIDATION_ERROR", field="currency_pair")` |
| `amount_usd` = "not_a_number"    | `ClassifyError(error_type="VALIDATION_ERROR")`|
| Missing required field           | `ClassifyError(error_type="VALIDATION_ERROR")` |
| Model runtime exception          | `ClassifyError(error_type="INFERENCE_ERROR")` |
| Property-based: random valid dicts | `ClassifyResponse` always (no crashes)   |
| Golden vector: known payment     | Probability ∈ [0, 1], SHAP len ≤ 20      |

---

## 5. Rollback Plan

`predict_validated()` is additive — it is not called by any existing orchestrator or Triton path.  Rollback = do not call `predict_validated()` in downstream code.  `predict()` remains untouched.

---

## 6. Metrics

Validation failure counter: `c1_validation_errors_total{error_type}` (Prometheus).  
Inference error counter: `c1_inference_errors_total` (Prometheus).  
Both are no-op stubs until `prometheus-client` is initialised by the deployment harness.
