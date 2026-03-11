# LIP Developer Guide

## Quick Start

```bash
# 1. Create virtualenv and install
python -m venv .venv && source .venv/bin/activate
pip install -e "lip/[all]"

# 2. Verify installation
ruff check lip/
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q

# 3. Generate synthetic training data
PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic

# 4. Train all models
PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic
```

## Test Commands

```bash
# Full unit + integration suite (excludes live Kafka/Redis E2E)
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q

# Single component
PYTHONPATH=. python -m pytest lip/tests/test_c6_aml_velocity.py -v

# E2E pipeline (requires running Kafka + Redis)
PYTHONPATH=. python -m pytest lip/tests/test_e2e_pipeline.py -v

# Type checking
mypy lip/

# Lint (must be zero errors before any commit)
ruff check lip/
```

## Canonical Constants — QUANT Sign-Off Required

The following constants are **locked** and may only be changed with explicit QUANT team approval. Changing them without sign-off constitutes a model governance violation under SR 11-7.

| Constant | Value | File | Impact of Change |
|----------|-------|------|-----------------|
| `FAILURE_PROBABILITY_THRESHOLD` (τ*) | **0.152** | `pipeline.py`, `constants.py` | Directly changes which payments are offered bridge loans |
| `FEE_FLOOR_BPS` | **300** | `constants.py` | Changes minimum revenue per loan |
| `LATENCY_SLO_MS` | **94 ms** | `constants.py` | Changes the SLO contract with deploying banks |
| `UETR_TTL_BUFFER_DAYS` | **45** | `constants.py` | Changes UETR deduplication window |
| `PLATFORM_ROYALTY_RATE` | **0.15** | `constants.py` | Changes BPI revenue share |
| `SALT_ROTATION_DAYS` | **365** | `constants.py` | Changes AML privacy protection lifetime |
| `SALT_ROTATION_OVERLAP_DAYS` | **30** | `constants.py` | Changes transition window for re-hashing |

## Never Commit List

The following must never appear in git history:

- `artifacts/` — model artefacts and training outputs (gitignored)
- `c6_corpus_*.json` — AML training corpus (gitignored)
- `.env` files — environment variables with secrets
- Redis password / Kafka SSL private keys
- PagerDuty integration keys
- BPI license tokens (`LIP_LICENSE_TOKEN` env var)

## Mock Injection Pattern

All pipeline dependencies use **constructor injection** to enable testing with mocks:

```python
# Production
pipeline = LIPPipeline(
    c1_engine=real_inference_engine,
    c2_engine=real_pd_engine,
    c4_classifier=real_dispute_classifier,
    c6_checker=real_aml_checker,
    c7_agent=real_execution_agent,
    c3_monitor=real_settlement_monitor,
)

# Testing — inject mock callables
pipeline = LIPPipeline(
    c1_engine=lambda d: {"failure_probability": 0.9, "above_threshold": True, "shap_top20": []},
    c2_engine=lambda d, b: {"pd_score": 0.05, "fee_bps": 350, "tier": 2, "shap_values": []},
    c4_classifier=MockDisputeClassifier(),
    c6_checker=MockVelocityChecker(),
    c7_agent=MockExecutionAgent(),
)
```

Mock objects must expose the same method signatures as their real counterparts:
- `c1_engine`: `(payment_dict: dict) -> dict` with `failure_probability`, `above_threshold`, `shap_top20`
- `c2_engine`: `(payment_dict: dict, borrower: dict) -> dict` with `pd_score`, `fee_bps`, `tier`
- `c4_classifier`: `.classify(rejection_code, narrative, amount, currency, counterparty) -> dict`
- `c6_checker`: `.check(entity_id, amount, beneficiary_id) -> result with .passed attribute`
- `c7_agent`: `.process_payment(context: dict) -> dict` with `status`, `loan_offer`, `decision_entry_id`

## Agent Team

The `.claude/agents/` directory contains 17 specialist agents:

| Tier | Agents |
|------|--------|
| 1 — Domain | ML-Scientist, Quant-Engineer, Payments-Architect, NLP-Engineer, Streaming-Engineer, Security-Analyst, Execution-Engineer |
| 2 — Platform | Test-Engineer, DevOps-Engineer, Perf-Engineer, Data-Engineer |
| 3 — Business | Patent-Analyst, Compliance-Officer, Product-Lead, Release-Engineer |
| 4 — Orchestration | Tech-Lead, Sprint-Planner |

## Slash Commands (`.claude/commands/`)

| Command | Description |
|---------|-------------|
| `/c1` – `/c8` | Per-component development tasks |
| `/test` | Run full test suite |
| `/lint` | Run ruff check |
| `/pipeline` | Pipeline orchestration tasks |
| `/patent` | Patent analysis and claims mapping |
| `/security` | Security review tasks |
| `/perf` | Performance benchmarking |
| `/status` | Project status summary |

## Code Quality Rules

1. **Zero ruff errors** before every commit: `ruff check lip/`
2. **Google-style docstrings** (Args / Returns / Raises) for all public methods
3. **No raw entity identifiers** in logs, metrics, or data stores — always hash with salt
4. **No `datetime.utcnow()`** — always use `datetime.now(tz=timezone.utc)`
5. **Decimal for money** — never use `float` for monetary amounts
6. **Type annotations** on all function signatures
