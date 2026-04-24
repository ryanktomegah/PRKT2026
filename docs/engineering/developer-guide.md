# LIP Developer Guide

## Quick Start

```bash
# 1. Create virtualenv and install
python -m venv .venv && source .venv/bin/activate
pip install -e "lip/[all]"

# 2. Verify installation
ruff check lip/
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q

# 3. Start local infrastructure (Redpanda + Redis via Docker)
./scripts/start_local_infra.sh   # requires Docker Desktop

# 4. Generate synthetic training data
PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic

# 5. Train all models
PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic
```

## Local Infrastructure (Docker)

`docker-compose.yml` at repo root starts all required services:

```bash
docker compose up -d          # start Redpanda (Kafka-compatible) + Redis 7
./scripts/start_local_infra.sh  # same, with health checks + guidance
docker compose down           # stop and remove containers
```

| Service | Port | Notes |
|---------|------|-------|
| Redpanda | 9092 | Kafka API-compatible, single-node, zero ZooKeeper |
| Redis | 6379 | Redis 7 Alpine, standalone mode |

All 10 Kafka topics are created automatically on first boot via the `redpanda-init` container.

## Test Commands

```bash
# Full unit + integration suite (excludes live Kafka/Redis E2E)
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q

# Single component
PYTHONPATH=. python -m pytest lip/tests/test_c6_aml_velocity.py -v

# E2E pipeline (requires running Kafka + Redis — start with docker compose up -d first)
PYTHONPATH=. python -m pytest lip/tests/test_e2e_pipeline.py -v

# C4 Groq wrapper (loads .env.local and file-backed secret)
./scripts/run_c4_with_groq.sh doctor
./scripts/run_c4_with_groq.sh test-live
./scripts/run_c4_with_groq.sh eval-negation --n-per-category 20

# Plain pytest also auto-loads repo-root .env.local during local test startup
# when the file exists. Existing shell env vars still win.

# Raw C4 LLM integration test (requires GROQ_API_KEY or GROQ_API_KEY_FILE)
GROQ_API_KEY_FILE=.secrets/groq_api_key PYTHONPATH=. python -m pytest lip/tests/test_c4_llm_integration.py -v
# Auto-skipped without GROQ_API_KEY/GROQ_API_KEY_FILE.

# Generate and publish the staging kubeconfig consumed by GitHub Actions deploys
KUBE_SERVER="https://<cluster-endpoint>" \
KUBE_TOKEN="<service-account-token>" \
KUBE_CA_FILE=/path/to/ca.crt \
./scripts/make_kubeconfig.sh .secrets/staging.kubeconfig
./scripts/set_github_kubeconfig.sh .secrets/staging.kubeconfig

# Type checking
mypy lip/

# Lint (must be zero errors before any commit)
ruff check lip/
```

## Runtime Artifacts and Real Pipeline Flags

The FastAPI surface can run in two modes, selected by `LIP_API_ENABLE_REAL_PIPELINE`:

| Mode | Flag | Behavior |
|------|------|----------|
| Stub (default in tests) | unset / `"false"` | `miplo_router` uses an in-memory stub pipeline |
| Real | `LIP_API_ENABLE_REAL_PIPELINE=true` | `lip/api/runtime_pipeline.py` mounts the full C1→C2→C4→C6→C7→C3 pipeline |

When the real pipeline is enabled, these env vars control where the trained artifacts come from:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIP_C1_MODEL_DIR` | unset (falls back to `create_default_model()`) | Directory containing the C1 Torch checkpoint (`c1_model_parquet.pt`), and optional `c1_lgbm_parquet.pkl` / `c1_calibrator.pkl` / `c1_scaler.pkl` |
| `LIP_C2_MODEL_PATH` | unset (bootstrap model) | Path to the signed C2 pickle |
| `LIP_MODEL_HMAC_KEY` | — | HMAC key for signed C2 pickle verification. **Required** when `LIP_C2_MODEL_PATH` is set |
| `LIP_C1_THRESHOLD` | `constants.FAILURE_PROBABILITY_THRESHOLD` | Override τ* (usually not needed; threshold is QUANT-locked) |
| `LIP_C4_BACKEND` | `mock` in tests | `groq` for live Qwen3-32B dispute classification |
| `LIP_REQUIRE_MODEL_ARTIFACTS` | `0` | When `1`, fail closed instead of falling back to bootstrap/default models |

### Generate the C2 Signed Artifact

```bash
# Writes artifacts/c2_trained/c2_model.pkl + .pkl.sig + c2_training_report.json
# artifacts/ is gitignored — regenerate per environment, never commit binaries
PYTHONPATH=. python scripts/generate_c2_artifact.py \
    --hmac-key-file .secrets/c2_model_hmac_key \
    --output-dir artifacts/c2_trained \
    --corpus artifacts/staging_rc_c2/c2_corpus_n50000_seed42.json \
    --n-trials 50 \
    --n-models 5 \
    --min-auc 0.70
```

### Deploy / Redeploy Local Staging

```bash
# local-core profile: lip-api + lip-c2-pd + lip-c4-dispute + lip-c6-aml
LIP_API_IMAGE=lip-api:local \
LIP_C2_IMAGE=lip-c2:local \
LIP_C4_IMAGE=lip-c4:local \
LIP_C6_IMAGE=lip-c6:local \
./scripts/deploy_staging_self_hosted.sh --profile local-core

# Other profiles: local-full-non-gpu, gpu-full, analytics — see docs/operations/deployment.md
```

### Verify Model Source in Running Pods

```bash
# Should print: "C2 service ready (artifact)"
kubectl -n lip-staging logs deploy/lip-c2-pd | grep "C2 service ready"

# Should print: "Runtime C1 engine ready (artifact:/app/artifacts/c1_trained)"
kubectl -n lip-staging logs deploy/lip-api | grep "Runtime C1 engine ready"

# Supplemental: artifact files present in pod
kubectl -n lip-staging exec deploy/lip-c2-pd -- ls -l /app/artifacts/c2_trained/
kubectl -n lip-staging exec deploy/lip-api  -- ls -l /app/artifacts/c1_trained/

# Strict artifact loading in staging RC
LIP_REQUIRE_MODEL_ARTIFACTS=1
LIP_TORCH_NUM_THREADS=1
LIP_TORCH_NUM_INTEROP_THREADS=1
```

`C2Service.model_source` (`artifact`, `bootstrap`, or `injected`) is the programmatic truth and is asserted in `test_c2_api_loads_signed_artifact`. It is intentionally not exposed on `/health`. See [`../operations/deployment.md`](../operations/deployment.md) § Self-Hosted Staging Deployment for the profile matrix and secret-loading rules.

App-level logging is configured by `lip/common/logging_setup.py` via `configure_app_logging()` at service import time. Level is controlled by `LIP_LOG_LEVEL` (default `INFO`).

## Canonical Constants — QUANT Sign-Off Required

The following constants are **locked** and may only be changed with explicit QUANT team approval. Changing them without sign-off constitutes a model governance violation under SR 11-7.

| Constant | Value | File | Impact of Change |
|----------|-------|------|-----------------|
| `FAILURE_PROBABILITY_THRESHOLD` (τ*) | **0.110** | `pipeline.py` | Directly changes which payments are offered bridge loans |
| `FEE_FLOOR_BPS` | **300** | `constants.py` | Changes minimum revenue per loan |
| `LATENCY_SLO_MS` | **94 ms** | `constants.py` | Changes the SLO contract with deploying banks |
| `UETR_TTL_BUFFER_DAYS` | **45** | `constants.py` | Changes UETR deduplication window |
| `PLATFORM_ROYALTY_RATE` | **0.30** | `constants.py` | Changes BPI revenue share |
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
