# Batch 10 — ML Models (C1 / C2 / C4 / C9)

**Scope**: `lip/c1_failure_classifier/` (16 files), `lip/c2_pd_model/` (11 files), `lip/c4_dispute_classifier/` (9 files), `lip/c9_settlement_predictor/` (3 files).
**HEAD**: `2b32314`
**Reviewer focus**: Pickle deserialization, label leakage, temporal splits, calibration, fee floor enforcement, prompt injection, negation handling, mock-backend footguns.

## Summary

The ML layer is the most mature part of the codebase on numerics (Decimal-throughout fee math, isotonic+Platt calibration with ECE gating, cyclical time encodings, SR 11-7 OOT splits) but the weakest on **artifact trust**: C1 and C2 both load LightGBM models and calibrators via `pickle.load()` with a `# noqa: S301` suppression and no signature/hash check. An attacker with write access to the model directory gets arbitrary code execution at load time. C4's default backend is `MockLLMBackend` which does pure substring matching with no negation awareness — any deployment that forgets to set `LIP_C4_BACKEND` silently uses a broken classifier. C4 also interpolates user-controlled `narrative`/`counterparty` fields straight into the LLM prompt (prompt injection vector). C2's stage-7 training has a Tier-3 stress test that indexes into the full dataset rather than the held-out test set (train/test contamination). The C2 training loop reads `r.get("timestamp", 0.0)` from an outer record dict where the timestamp actually lives at `r["payment"]["timestamp"]` — every record gets timestamp 0.0, collapsing the OOT split into a random permutation and silently losing the temporal validation guarantee. C1's `fee.py` uses `assert` for the 300 bps floor check which is stripped under `python -O`.

## Findings

| ID | Sev | File:line | Category | Finding | Suggested fix |
|---|---|---|---|---|---|
| B10-01 | **Critical** | `c1_failure_classifier/model.py:509-516` | Pickle RCE on model load | `pickle.load()` on `lgbm.pkl` and `calibrator.pkl` with no integrity check. `# noqa: S301` hides it. Write access to model dir = RCE. | HMAC-SHA256 sidecar verified before `pickle.load()`, or use LightGBM native `Booster(model_file=...)` text format. |
| B10-02 | **Critical** | `c2_pd_model/model.py:360-361` | Pickle RCE on PD ensemble load | Same pattern — full 5-model ensemble deserialized via pickle with no verification. Comment says "trusted only" but nothing enforces it. | Same: HMAC sidecar, or LightGBM native `.txt` format per member. |
| B10-03 | **High** | `c2_pd_model/training.py:568` + `:578-583` | OOT split collapses + Tier-3 stress contamination | `r.get("timestamp", 0.0)` reads from the outer record but the timestamp lives at `r["payment"]["timestamp"]` → every record gets 0.0, OOT `argsort` becomes random permutation, chronological guarantee lost. Separately, the Tier-3 stress test uses `tier3_idx` into the full `X` rather than the test set, so some Tier-3 stress samples were in training. Both silently invalidate SR 11-7 validation claims. | Read `r.get("payment", {}).get("timestamp", 0.0)` and assert >50% non-zero. Intersect `tier3_idx` with test indices before the stress test. |
| B10-04 | **High** | `c1_failure_classifier/training.py:878` | OOT split silently random on missing field | `timestamps` built from `r.get("timestamp_unix", 0.0)` but the synthetic generator emits `timestamp`. On a missing field all values are 0.0 and `argsort` collapses. Same failure mode as B10-03. | Fall back to `r.get("timestamp", 0.0)` and warn when >50% are zero. |
| B10-05 | **High** | `c4_dispute_classifier/model.py:86-94` + `backends.py:154-158` | Default backend is `MockLLMBackend` (substring match, no negation) | `LIP_C4_BACKEND` defaults to `"mock"`. Mock uses `"fraud" in lowered`; "no fraud detected" returns `DISPUTE_CONFIRMED`. CRITICAL log exists but is easy to miss. A prod deployment that forgets the env var silently runs a broken dispute classifier. | Refuse to construct mock unless `LIP_ALLOW_MOCK_BACKEND=1` is explicitly set. Default backend must be a real LLM or a fail-closed error. |
| B10-06 | **High** | `c4_dispute_classifier/prompt.py:173-180` | Prompt injection on narrative/counterparty | User fields are f-string interpolated into the LLM prompt with no sanitisation. Adversarial narrative can override the classification instruction. | Strip control chars/newlines; wrap in `<narrative>...</narrative>` delimiters with a system instruction to ignore instructions inside delimiters. |
| B10-07 | High | `c2_pd_model/features.py:238` + `c2_pd_model/inference.py:27` | Zero-byte default salt | `_DEFAULT_SALT = b"\x00"*32` as fallback. If `configure_salt()`/`salt=` is never called, borrower-ID hashes are rainbow-reversible. `PDInferenceEngine` direct path bypasses the convenience-function warning. | Refuse to run in prod when the configured salt still equals the default; require explicit salt at engine construction. |
| B10-08 | High | `c2_pd_model/fee.py:300` | `assert` for 300 bps floor invariant | `assert cascade_adjusted_fee_bps >= FEE_FLOOR_BPS` — stripped under `python -O`. The canonical CLAUDE.md fee floor can be bypassed by a single runtime flag. | `if ... < FEE_FLOOR_BPS: raise ValueError(...)`. Asserts are never the right primitive for financial invariants. |
| B10-09 | Medium | `c4_dispute_classifier/prefilter.py:303-306` | Negotiation keywords skip negation guard | `_CONFIRMED_KEYWORDS` runs `_is_negated()` but `_NEGOTIATION_KEYWORDS` does not. "Not a negotiation" → `NEGOTIATION`. | Apply the same negation guard to the negotiation keyword pass. |
| B10-10 | Medium | `c4_dispute_classifier/backends.py:175-176` | Wrong Groq default model | `_GROQ_DEFAULT = "mistral-saba-24b"`. CLAUDE.md canonical C4 model is `qwen/qwen3-32b`. Only correct when `LIP_C4_MODEL` overrides. | Set `_GROQ_DEFAULT = "qwen/qwen3-32b"`. |
| B10-11 | Medium | `c9_settlement_predictor/model.py:193-227` | Cox model loaded via lifelines pickle path | Current code only fits in-process, but the persist/load shape implied by the class is pickle-based. Same class of RCE as B10-01/02 if load from untrusted paths is ever added. | Document explicitly; when adding load, gate it to trusted paths and verify a hash. |
| B10-12 | Medium | `c2_pd_model/model.py:316` | `except Exception` masks SHAP bugs | Broad catch in `predict_with_shap` returns zero-SHAP silently. A shape-mismatch bug looks like "SHAP unavailable". | Narrow to `(ImportError, ValueError, TypeError)`. |
| B10-13 | Medium | `c1_failure_classifier/model.py:354` | Private attribute access `calibrator._is_fitted` | Fragile coupling; internal refactor silently breaks caller. | Add a public `IsotonicCalibrator.is_fitted` property. |
| B10-14 | Medium | `c2_pd_model/training.py:406` | `except Exception` in calibration stage | Swallows `MemoryError` etc.; failed calibration produces uncalibrated deployment with no signal. | Narrow + return a success flag to the caller. |
| B10-15 | Medium | `c1_failure_classifier/inference.py:231` | Broad `except Exception` in `predict_validated` | Converts all exceptions to generic error response. | Narrow to expected error set. |
| B10-16 | Medium | `c4_dispute_classifier/backends.py:125-128` | Fragile timeout detection via string match | `"Timeout" in exc_type` — misses other HTTP clients. | Match specific exception classes (`httpx.TimeoutException`, `requests.exceptions.Timeout`). |
| B10-17 | Medium | `c4_dispute_classifier/prefilter.py:18-24` | Only LEGL of 8 EPG-19 codes in `IMMEDIATE_BLOCK_CODES` | Prefilter enumerates {DISP,LEGL,FRAU,FRAD,DUPL}; EPG-19 is {DNOR,CNOR,RR01-04,AG01,LEGL}. Handled at C3/C7 layer but non-obvious. | Document scope; add a `COMPLIANCE_HOLD` early return or cross-reference to C3/C7. |
| B10-18 | Low | `c2_pd_model/training.py:524`, `c1_failure_classifier/synthetic_data.py:980` | `except (ImportError, Exception)` redundant tuple | `Exception` supersedes `ImportError`; swallows real bugs. | Narrow to `ImportError` only; handle SMOTE runtime errors separately. |
| B10-19 | Low | `c4`, `c9` modules | Pre-3.10 typing | `List`/`Optional`/`Tuple` imports across `c4/*.py`, `c9/*.py`. | `pyupgrade --py310-plus`. |
| B10-20 | Nit | `c1_failure_classifier/inference_types.py:33,38` | `_BIC_RE` defined twice | Duplicate regex definition; second shadows first. | Delete the duplicate. |
| B10-21 | Nit | `c4_dispute_classifier/prefilter.py:82-91` | Broad negotiation keywords | `"partial"`, `"settlement"` standalone trigger NEGOTIATION on "partial failure" / "settlement completed". | Require co-occurrence or add `"settled"` to a resolution bank. |

## Notable positives (preserve)

- **Decimal-throughout fee math** with explicit `ROUND_HALF_UP`. Tiered floor (500/400/300) converging to canonical 300 bps is well-designed unit economics.
- **No pickle for numpy weights** — GraphSAGE / TabTransformer / MLP use `np.savez`/`np.load`. Pickle is only the LightGBM/calibrator path (which is where the RCE lives, but the scope is bounded).
- **Isotonic + Platt calibration from scratch** with ECE < 0.08 deployment gate — exactly the SR 11-7 shape.
- **C1 cyclical time encodings** (sin/cos hour/day/month) avoid midnight/year-boundary discontinuities.
- **EPG-19 BLOCK codes filtered from C1 training data** and validated in `validate_dataset()`.
- **C2 inference strips raw `tax_id`** before feature extraction. SHA-256 borrower hash with configurable salt (the default-salt footgun aside).
- **Pydantic-strict typed C1 inference API** (`ClassifyRequest`/`Response`/`Error`) with BIC + currency-pair validation.
- **C9 `MAX_MATURITY_OVERRIDE_FACTOR = 1.0`** prevents the ML model from ever exceeding the QUANT-approved static maturity window.
- **C9 graceful degradation** — heuristic fallback when `lifelines`/`peft`/GPU unavailable; CI runs without ML infra.
- **C4 fail-closed on timeout/parse error** — falls back to `DISPUTE_POSSIBLE` (blocking), not `NOT_DISPUTE`.
- **C4 multilingual negation engine** (EN/DE/FR/ES) with 5-token window and 500-case test suite.
- **C4 circuit breaker on LLM API** (5-failure open threshold).
- **C9 imports maturity constants** from `lip/common/constants.py` rather than hardcoding.

## Files read

- [x] `c1_failure_classifier/` — all 16 files
- [x] `c2_pd_model/` — all 11 files
- [x] `c4_dispute_classifier/` — 9 files
- [x] `c9_settlement_predictor/` — 3 files
