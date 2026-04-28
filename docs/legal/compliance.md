# LIP Compliance Reference

**Current status:** read [`../CURRENT_STATE.md`](../CURRENT_STATE.md) before relying on dated model metrics in this compliance reference. The C1/C2 staging RC artifacts were retrained and signed on 2026-04-24, while the March model governance evidence remains part of the historical audit trail.

## SR 11-7: Model Risk Management (Fed / OCC)

**Scope**: All ML models deployed in C1 (Failure Classifier) and C2 (PD Model).

| Requirement | LIP Implementation | File |
|-------------|-------------------|------|
| Model inventory | All models versioned with artefact tags in `model_version` field | `common/schemas.py` |
| Validation independence | C1 AUC monitoring via `PrometheusMetricsCollector.set_auc()` with 0.80 warning threshold | `infrastructure/monitoring/metrics.py` |
| Human override | `HumanOverrideInterface` — any AI decision can be countermanded | `c7_execution_agent/human_override.py` |
| Kill switch | `KillSwitch.activate()` halts all new offers without code changes | `c7_execution_agent/kill_switch.py` |
| Decision audit trail | `DecisionLogEntry` with HMAC-SHA256 integrity, 7-year Kafka retention | `common/schemas.py` |
| Performance monitoring | P99 latency, AUC drift, queue depth tracked and alerted | `infrastructure/monitoring/` |
| Documentation | Model cards (`docs/c1-model-card.md`), training data cards (`docs/c1-training-data-card.md`), component READMEs, SR 11-7 Pack v1.0 | `docs/`, `lip/c*/README.md` |

**C1 model status** (2026-03-21): Retrained on 10M synthetic corpus (2M sample, 20 corridors, temporal burst clustering, per-BIC risk tiers). Val AUC = 0.8871, F2 = 0.6245, ECE = 0.0687 (post-isotonic calibration). Calibrated threshold τ* = 0.110. Full model card: `docs/c1-model-card.md`. Training data card: `docs/c1-training-data-card.md`. Real-world production target (0.850 AUC) pending pilot with anonymised SWIFT data under QUANT sign-off.

---

## EU AI Act (Regulation 2024/1689)

LIP processes payment failure predictions that inform credit decisions — classified as **high-risk AI** under Annex III, Section 5(b) (AI systems used in creditworthiness assessment).

### Article 9 — Risk Management

| Requirement | Implementation |
|-------------|---------------|
| Identify and mitigate risks | `KillSwitch` (primary risk control); `DegradedModeManager` (failure handling) |
| Testing before deployment | 92%+ test coverage; `ruff` zero-error policy |
| Monitoring in production | Prometheus metrics + PagerDuty alerting for AUC drift and latency |

### Article 13 — Transparency

| Requirement | Implementation |
|-------------|---------------|
| System documentation | This docs/ suite + component READMEs + `docs/c1-model-card.md` + `docs/c1-training-data-card.md` |
| Intended purpose | Automated bridge lending for SWIFT payment failures |
| Model limitations | Documented in `docs/c1-model-card.md` §6 (7 limitations) and component READMEs |
| SHAP explanations | `ClassifyResponse.shap_top20` — top-20 feature contributions per prediction |

### Article 14 — Human Oversight

| Requirement | Implementation |
|-------------|---------------|
| Human override capability | `HumanOverrideInterface.request_override()` and `submit_response()` |
| Override audit trail | All overrides logged with `operator_id` and `justification` |
| Timeout enforcement | Configurable `timeout_seconds` (default 300 s); expired requests rejected |
| Dual approval option | `requires_dual_approval` flag available for high-value thresholds |

### Article 17 — Quality Management System

| Requirement | Implementation |
|-------------|---------------|
| Record keeping | `DecisionLogEntry` — immutable, HMAC-signed, 7-year Kafka retention |
| Version control | All model artefacts tagged; `model_version` in every log entry |
| Change management | QUANT sign-off required for canonical constants (see `docs/developer-guide.md`) |

### Article 61 — Post-Market Monitoring

| Requirement | Implementation |
|-------------|---------------|
| Serious incident reporting | `AlertManager.alert_kill_switch()` + DORA Art.30 incident records |
| Performance monitoring | `PrometheusMetricsCollector` — AUC, latency, queue depth |

---

## DORA (Digital Operational Resilience Act, Art.30)

**Scope**: ICT operational resilience for financial entities using LIP.

| Requirement | Implementation |
|-------------|---------------|
| ICT incident logging | Kill switch activations logged at `CRITICAL` with reason string |
| Resilience testing | `degraded_mode.py` — GPU/KMS failure simulation |
| Recovery time tracking | `KillSwitch.kms_unavailable_gap_seconds()` — elapsed outage duration |
| Incident reporting | `AlertManager.alert_kms_failure(gap_seconds)` for KMS outages |
| Third-party risk | C8 License Manager validates BPI token at boot |

---

## AML / CFT (FATF Recommendations 10, 16)

| Requirement | C6 Implementation |
|-------------|------------------|
| Transaction monitoring | 24-hour rolling velocity window with $1M and 100-transaction caps |
| Sanctions screening | OFAC / EU / UN list screening at every payment event |
| Beneficiary concentration | >80% to single beneficiary triggers block |
| Record keeping | AML decision entries in `DecisionLogEntry` (7-year retention) |

### Privacy Design (GDPR Art.25 — Data Protection by Design)

Raw entity identifiers are **never stored** in any LIP data store. The privacy guarantee is enforced through:

```
stored_identifier = SHA-256(entity_id + salt)
```

- Salt is **32 bytes of OS random** (`os.urandom(32)`) — cryptographically secure
- Salts rotate **annually** (365 days) with a 30-day dual-salt overlap
- Each licensee has a **unique salt** — cross-licensee correlation is impossible
- Salt values are stored in Redis with appropriate TTLs (`lip:salt:current`, `lip:salt:previous`)

### Data Retention

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| Decision log entries | **7 years** | `lip.decision.log` Kafka topic |
| AML velocity counters | 24 hours | Redis (auto-expires) |
| Corridor embeddings | 7 days | Redis (auto-expires) |
| Active loan state | 90 days | Redis (auto-expires) |
| Previous AML salt | 30 days | Redis (auto-expires) |
