# Sprint 8: Validation & Audit Prep — Design Spec

> **P10 Blueprint Sprint 8 (W20-W22)** — Final sprint. Hardens Sprints 1-7 for production audit.

## Goal

Make the P10 regulatory data product auditable by an independent privacy firm and ready for OSFI sandbox onboarding. All validation is code — reproducible pytest runs that generate quantitative audit evidence.

## Architecture

Three new production modules + three new test modules. No new API endpoints. All evidence is programmatically generated and deterministically reproducible.

## Tech Stack

Python (pytest, asyncio, numpy), FastAPI TestClient, existing P10 modules.

---

## Deliverable 1: Privacy Audit Kit

**New file:** `lip/p10_regulatory_data/privacy_audit.py`

Toolkit for privacy auditors to verify P10's three-layer defense.

### 1a. Re-Identification Attack Simulator

Three attack vectors that a privacy auditor would run:

- **Frequency attack**: Given anonymized corridor output, attempt to identify individual banks by payment volume distribution. Attack succeeds if any bank can be uniquely identified.
- **Uniqueness attack**: Check if any corridor has a bank with unique characteristics (e.g., only bank in a specific amount bucket) that survives anonymization.
- **Temporal linkage attack**: Correlate anonymized output across time periods to track persistent patterns attributable to a single entity.

Each attack returns a structured `AttackResult(attack_type, succeeded, confidence, details)`.

### 1b. K-Anonymity Proof Generator

Formal verification that no corridor in anonymized output has fewer than k distinct bank hashes. Iterates all corridors, all time periods, asserts `bank_count >= k` universally.

Returns `KAnonymityProof(k_threshold, corridors_checked, all_satisfied, violations)`.

### 1c. Differential Privacy Verifier

Statistical test that noise distribution matches theoretical Laplace(0, b) where b = sensitivity/epsilon. Runs N trials, collects noise samples, performs Kolmogorov-Smirnov test against theoretical CDF. 

Returns `DPVerificationResult(epsilon, sensitivity, n_samples, ks_statistic, ks_p_value, passed)`.

### 1d. Privacy Budget Audit

Verify that total epsilon consumed across all corridors and queries matches expected composition. Check that budget exhaustion correctly triggers stale-serving behavior.

Returns `BudgetAuditResult(total_epsilon_consumed, expected_epsilon, corridors_audited, composition_valid, exhaustion_behavior_correct)`.

### 1e. Audit Report Generator

`generate_audit_report()` — runs all four checks, aggregates into a single `PrivacyAuditReport` with timestamp, methodology version, pass/fail per check, and overall verdict.

---

## Deliverable 2: Load Test Suite

**New file:** `lip/tests/test_p10_load_test.py`

Concurrent API query testing using FastAPI TestClient + threading.

### Tests (8):

1. `test_100_concurrent_corridor_queries` — 100 threads hit GET /corridors simultaneously. Assert: all return 200, mean latency < 500ms.
2. `test_100_concurrent_mixed_endpoints` — 100 threads across all endpoint types. Assert: all authorized requests succeed.
3. `test_rate_limiter_under_load` — Exceed rate limit with burst. Assert: excess requests get 429.
4. `test_budget_enforcement_under_concurrency` — Multiple threads consuming same regulator's budget. Assert: no over-consumption (total queries <= budget).
5. `test_response_time_corridor_under_load` — GET /corridors p95 < 500ms with 50 concurrent.
6. `test_response_time_stress_test_under_load` — POST /stress-test p95 < 30s with 10 concurrent.
7. `test_sequential_vs_concurrent_consistency` — Same queries sequential vs concurrent produce equivalent results.
8. `test_privacy_budget_isolation_under_load` — Concurrent requests from different regulators don't cross-contaminate budgets.

---

## Deliverable 3: Security Penetration Test Suite

**New file:** `lip/tests/test_p10_security_pentest.py`

Adversarial testing of auth, integrity, and access control.

### Tests (14):

**Token Auth (5):**
1. `test_missing_bearer_token_returns_401`
2. `test_malformed_token_returns_401`
3. `test_expired_token_returns_401`
4. `test_tampered_hmac_signature_returns_401`
5. `test_valid_token_wrong_signing_key_returns_401`

**Tier Escalation (3):**
6. `test_standard_tier_cannot_access_stress_test`
7. `test_query_tier_cannot_access_contagion`
8. `test_realtime_tier_accesses_all_endpoints`

**Corridor Access Control (3):**
9. `test_corridor_restricted_token_blocked_from_other_corridors`
10. `test_wildcard_corridor_permission_works`
11. `test_stress_test_with_unpermitted_corridor_blocked`

**Re-Identification Probing (3):**
12. `test_api_response_contains_no_raw_bics` — scan all endpoint responses for BIC patterns
13. `test_api_response_contains_no_individual_payment_ids` — scan for UETR/payment ID leakage
14. `test_suppressed_corridors_not_enumerable` — verify suppressed corridor names aren't leaked

---

## Deliverable 4: Methodology Paper Generator

**New file:** `lip/p10_regulatory_data/methodology_paper.py`

Auto-generates a methodology document from code constants. For regulators reviewing P10's statistical approach.

### Sections (auto-populated from constants + module metadata):

1. **Data Collection** — telemetry schema, collection frequency (hourly), amount bucketing thresholds
2. **Anonymization Layers** — entity hashing (SHA-256 + rotating salt), k-anonymity (k=5, suppression), differential privacy (Laplace, ε=0.5)
3. **Statistical Methodology** — failure rate computation, HHI concentration, contagion BFS, trend detection
4. **Privacy Guarantees** — formal ε-DP guarantee statement, composition theorem, budget lifecycle
5. **Limitations** — data volume requirements, shadow period rationale, re-identification residual risk
6. **Constants Reference** — all P10 constants with descriptions

Output: `MethodologyPaper` dataclass with `to_dict()`, `to_markdown()` methods.

---

## Deliverable 5: Regulator Onboarding Package

**New file:** `lip/p10_regulatory_data/regulator_onboarding.py`

OSFI sandbox readiness toolkit.

### Components:

1. **OnboardingChecklist** — dataclass with 12 checklist items (data_collection_active, k_anonymity_verified, dp_budget_configured, api_endpoints_tested, load_test_passed, security_audit_passed, methodology_documented, report_formats_verified, token_auth_configured, rate_limiting_active, query_metering_active, integrity_verification_passing). Each has `status: str` (PASS/FAIL/PENDING) and `evidence: str`.

2. **generate_sample_data_package()** — uses `shadow_data.generate_shadow_events()` + full pipeline to produce a sample anonymized report, demonstrating the end-to-end flow. Returns package dict with sample events, batches, anonymized results, and versioned report.

3. **generate_compliance_mapping()** — maps P10 controls to DORA CTPP requirements (Art. 31-44). Returns `list[ComplianceMapping]` with P10 control, DORA article, status, evidence.

---

## Test Summary

| File | Tests | Purpose |
|------|-------|---------|
| `test_p10_privacy_audit.py` | 16 | Privacy audit kit verification |
| `test_p10_load_test.py` | 8 | Concurrent API load testing |
| `test_p10_security_pentest.py` | 14 | Security penetration tests |
| **Total** | **38** | |

## Out of Scope

- Actual OSFI sandbox submission (requires regulatory affairs engagement)
- Privacy audit firm engagement (3-6 month lead time per blueprint)
- Luxembourg subsidiary formation (corporate legal)
- Production Kafka/Redpanda integration (deferred to bank pilot)
- PDF rendering of methodology paper (fpdf2 optional; markdown sufficient for audit)
