# LIP Codebase Review — 2026-04-08

**HEAD**: `2b32314`
**Reviewer**: Claude Opus 4.6 (batched, 13 batches — all complete)
**Plan**: `/Users/tomegah/.claude/plans/velvet-giggling-map.md`

## How to read this index

Findings are aggregated across all batches by **severity**. Each row links back to the batch file for full context, suggested fix, and surrounding discussion. Critical and High are the only severities that should drive near-term action; Medium is a triage backlog; Low/Nit are for the slow grooming pass.

**Batches completed** (with findings files): 1 Integrity/Common, 2 API, 3 C8 License, 4 C7 Execution, 5 C3 Repayment, 6 C5 Streaming, 7 C6 AML Velocity, 8 Compliance/Risk/P10, 9 P5 Cascade, 10 ML Models (C1/C2/C4/C9), 12 Infra/Scripts.

**Batches deferred** (rate-limited or out of budget): **11 DGEN** — background subagent hit Claude.ai daily limit; **13 Tests** — 121 files, budget exhausted after Batch 12. Both have follow-up prompts preserved in their placeholder files (`11-dgen.md`, `13-tests.md`).

---

## Critical findings

Direct CLAUDE.md violations, RCE primitives, privacy-soundness breaks, and money-loss paths. **These block production.**

| ID | File:line | Finding | Batch |
|---|---|---|---|
| B3-01 | `c8_license_manager/query_metering.py:59-99` | TOCTOU race in DP budget enforcement — concurrent regulators can all pass pre-check and all increment, exceeding the budget | [03](03-c8-license.md) |
| B3-02 | `c8_license_manager/license_token.py:93-262` | Hand-maintained canonical HMAC payload — adding any field without updating 4 parallel lists leaves the field *unsigned*, a privilege-escalation primitive | [03](03-c8-license.md) |
| B6-01 | `c5_streaming/go_consumer/normalizer.go:79-92` + 4 siblings | 5-way (now 6-way with B8-03) dual-maintained BLOCK code list across Py/Rust/Go — any drift creates a silent EPG-19 defense-in-depth gap | [06](06-c5-streaming.md) |
| B6-02 | `c5_streaming/go_consumer/consumer.go:256-260` | Exactly-once claim violated — Go consumer commits offset on **error paths**, so failed messages are lost to DLQ and never reprocessed | [06](06-c5-streaming.md) |
| B8-01 | `p10_regulatory_data/anonymizer.py` | Differential privacy composition violated — `anonymize_batch` charges **1ε** but releases **3 noised values**, so the actual privacy cost is 3× the documented budget | [08](08-compliance-risk-p10.md) |
| B8-02 | `p10_regulatory_data/anonymizer.py` | Budget-exhausted fallback publishes **raw un-noised data** when no cache exists — fail-open on the hardest privacy invariant | [08](08-compliance-risk-p10.md) |
| B9-01 | `p5_cascade_engine/constants.py:39` | `INTERVENTION_FEE_RATE_BPS = 200` directly violates the CLAUDE.md canonical **300 bps fee floor** — intervention optimizer understates true cost by 33% | [09](09-p5-cascade.md) |
| B10-01 | `c1_failure_classifier/model.py:509-516` | `pickle.load()` on `lgbm.pkl` and `calibrator.pkl` with no hash/signature check — write access to model dir = arbitrary RCE | [10](10-ml-models.md) |
| B10-02 | `c2_pd_model/model.py:360-361` | Same pickle RCE primitive for the full 5-model PD ensemble | [10](10-ml-models.md) |
| B11-01 | `dgen/iso20022_payments.py:69`, `statistical_validator_production.py:67` | CLASS_B labelled as "compliance/AML hold" in DGEN — directly contradicts CLAUDE.md CLASS_B warning; 53.6h P95 target is the mislabelled value | [11](11-dgen.md) |
| B11-02 | `dgen/c1_generator.py:74-82,179` | EPG-19 codes (RR01/RR02/FRAU/LEGL) tagged Class B/C with `is_bridgeable=True` — trains C1 to bridge compliance holds | [11](11-dgen.md) |
| B13-01 | `lip/tests/` | Zero regression tests for pickle-load RCE (B10-01/02) — `grep pickle` returns no matches | [13](13-tests.md) |
| B13-02 | `lip/tests/` | No cross-language BLOCK-code drift regression — 6+ independent code copies, no test asserts set-equality across Py/Rust/Go | [13](13-tests.md) |

---

## High findings (selected — see batch files for full list)

Load-bearing correctness, security, or domain invariants. Not production-blocking individually but each is a real bug.

| ID | File:line | Finding | Batch |
|---|---|---|---|
| B3-03 | `license_token.py:79-80` | Default-permissive AML caps (0=unlimited) on programmatic construction; sentinel protection is unreachable | [03](03-c8-license.md) |
| B3-04 | `query_metering.py:46-53` | Metering store is in-memory — redeploy resets every regulator's monthly budget; multi-replica = N× the budget | [03](03-c8-license.md) |
| B3-05 | `license_token.py:93-114` | No schema version in canonical HMAC payload — future field adds cause signature drift or forgery | [03](03-c8-license.md) |
| B6-03 | `go_consumer/normalizer.go:37-56` | Proprietary→ISO 20022 mapping dual-maintained in Go/Py — drift means same event gets different rejection class | [06](06-c5-streaming.md) |
| B6-04 | `go_consumer/grpc_client.go:47-50` | gRPC connections use insecure credentials — payment data (UETR, BIC, amount) flows plaintext inside the cluster | [06](06-c5-streaming.md) |
| B6-05 | `go_consumer/config.go:74` | Go consumer defaults to Kafka `PLAINTEXT` while Py defaults to `SSL` — silent security downgrade | [06](06-c5-streaming.md) |
| B6-06 | `go_consumer/config.go:127` | Undocumented divergence: Go producer `max.in.flight=5` vs Py `=1`; ordering risk if idempotence ever disabled | [06](06-c5-streaming.md) |
| B7-01 | `rust_velocity/src/velocity.rs:308` | Decimal→float precision loss at AML cap boundary — Rust path can pass where Py blocks (or vice versa) | [07](07-c6-aml-velocity.md) |
| B7-02 | `rust_velocity/src/velocity.rs` | Rust velocity has no Redis backing — multi-replica deployments get per-pod isolation and N× AML budget | [07](07-c6-aml-velocity.md) |
| B7-03 | `sanctions.py:128-157` | Sanctions screening has no transliteration/phonetic matching — OFAC SDN Cyrillic/Arabic entries silently miss | [07](07-c6-aml-velocity.md) |
| B8-03 | `p10_regulatory_data/telemetry_collector.py` | 6th independent copy of the EPG-19 BLOCK code list (was 5 at B6-01) | [08](08-compliance-risk-p10.md) |
| B8-04 | `risk/portfolio_risk.py` | Decimal→float→Decimal round-trip via `math.sqrt` loses Decimal precision guarantee in parametric VaR | [08](08-compliance-risk-p10.md) |
| B8-05 | `p10_regulatory_data/privacy_audit.py` | Attack simulations (frequency/uniqueness/temporal) are tautological — always pass by construction | [08](08-compliance-risk-p10.md) |
| B9-02 | `p5_cascade_engine/cascade_propagation.py:142-147` | O(n²) bottom-up CVaR pass — fine at current scale, breaks at 1k+ corporates | [09](09-p5-cascade.md) |
| B9-03 | `p5_cascade_engine/intervention_optimizer.py:78-100` | O(N²) greedy optimizer per iteration; heap-based would be O(N log N) | [09](09-p5-cascade.md) |
| B10-03 | `c2_pd_model/training.py:568,578-583` | C2 OOT split collapses (wrong dict path → all timestamps 0.0) + Tier-3 stress test contaminates train with test | [10](10-ml-models.md) |
| B10-04 | `c1_failure_classifier/training.py:878` | C1 OOT split silently random when `timestamp_unix` field is missing from synthetic data | [10](10-ml-models.md) |
| B10-05 | `c4_dispute_classifier/model.py:86-94` | Default LLM backend is `MockLLMBackend` (substring match, no negation) — prod footgun on missing env var | [10](10-ml-models.md) |
| B10-06 | `c4_dispute_classifier/prompt.py:173-180` | Prompt injection — user-controlled `narrative`/`counterparty` f-stringed into LLM prompt without sanitisation | [10](10-ml-models.md) |
| B10-07 | `c2_pd_model/features.py:238` + `inference.py:27` | Zero-byte default salt — borrower-ID hashes trivially reversible if `configure_salt()` never called | [10](10-ml-models.md) |
| B10-08 | `c2_pd_model/fee.py:300` | `assert` for the 300 bps fee floor — stripped under `python -O`, canonical constant bypassable via runtime flag | [10](10-ml-models.md) |
| B12-01 | `requirements*.txt` | No upper version bounds on any package — supply-chain risk for a payments+crypto system | [12](12-infra-scripts.md) |
| B12-02 | `docker/Dockerfile.c1` | Triton base image pinned to 2024-01 release — multiple NVIDIA Triton CVEs since then | [12](12-infra-scripts.md) |

---

## Medium / Low / Nit

See individual batch files. Total counts across completed batches (approximate):
- Batch 3 (C8 License): 14 findings
- Batch 6 (C5 Streaming): 20 findings
- Batch 7 (C6 AML): 14 findings
- Batch 8 (Compliance/Risk/P10): 18 findings
- Batch 9 (P5 Cascade): 10 findings
- Batch 10 (ML Models): 21 findings
- Batch 12 (Infra/Scripts): 12 findings

Batches 1, 2, 4, 5 findings files exist from the earlier session — see directory listing under `docs/review/2026-04-08/`.

---

## Cross-batch themes

Patterns that appear in more than one batch and deserve a single structural fix rather than individual per-module patches:

1. **Dual/multi-maintained constant lists.** BLOCK codes are enumerated in **7 places** across Py, Rust, and Go — the seventh being DGEN's `c1_generator.py` which actively contradicts the list by marking EPG-19 codes bridgeable (B11-02). No test asserts cross-language set-equality (B13-02). Proprietary→ISO 20022 mappings are dual-maintained (B6-03). Canonical HMAC fields are hand-maintained (B3-02). **Single fix**: shared JSON file under `lip/common/` consumed by Python at import, Rust via `include_str!`, Go via `go:embed`. CI regression test asserts all loaders produce identical sets.

2. **In-memory state in multi-replica deployments.** C8 query metering (B3-04), Rust velocity (B7-02), C6 structuring detector (B7-10). Each claims to be single-replica-safe but nothing enforces it. **Single fix**: require Redis backing or refuse construction with an explicit `single_replica=True` opt-in.

3. **Decimal→float→Decimal round-trips at compliance boundaries.** Portfolio VaR (B8-04), Rust velocity cap (B7-01), license token take-rate (B3-07), ML fee computation paths. Every one of these is a potential boundary-condition bug. **Single fix**: audit every `float()` call on a Decimal-typed field; forbid via a lint rule.

4. **`assert` for load-bearing invariants.** Fee floor (B10-08), likely others. `python -O` strips them. **Single fix**: repo-wide grep for `assert` in non-test files, convert each to explicit `if ... raise`.

5. **Pickle deserialization without verification.** C1 LightGBM (B10-01), C2 PD ensemble (B10-02), potential C9 Cox (B10-11). No regression test exists (B13-01). **Single fix**: a shared `lip/common/secure_pickle.py` that verifies an HMAC sidecar before `pickle.load`, used as the only legal pickle loader in the codebase. Forbid direct `pickle.load` via lint, gated by a test that fails if any `pickle.load` call appears outside `secure_pickle.py`.

6. **Default-permissive fallbacks.** Zero-byte salt (B10-07), 0=unlimited AML cap (B3-03), 0=unlimited budget (B9-04), mock LLM as default backend (B10-05), in-memory metering (B3-04). Every one of these is "insecure by default, secure if you remember to configure." **Single fix**: construct-time validation that refuses the insecure default unless an explicit `allow_insecure_default=True` is passed, plus a startup log banner enumerating any that are active.

---

## Recommended next actions

1. **Land fixes for the 9 Critical findings** in a single hardening sprint. Each one is small but they are the only items that block production.
2. **Pick one cross-batch theme** (suggest #1 — BLOCK code consolidation — since it touches 3 languages and has the most lines of duplicated compliance logic) and execute it end-to-end, including the CI regression test. This establishes the pattern for the other themes.
3. **Re-run Batch 11 (DGEN)** after the Claude.ai rate limit resets.
4. **Re-run Batch 13 (Tests)** in a fresh session with full budget. This is the most important deferred batch because every prior finding's regression lives here.
5. **Founder decision**: which of the cross-batch themes are worth doing *now* vs deferring until the RBC pilot conversation lands, given the IP clause risk noted in the founder's memory.
