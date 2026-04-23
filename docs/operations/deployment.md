# LIP Deployment Reference

## Docker Images

LIP ships 7 Docker images, one per deployable service:

| Service | Dockerfile | Description |
|---------|-----------|-------------|
| `lip-c1` | `lip/c1_failure_classifier/Dockerfile` | C1 inference service (GPU-enabled) |
| `lip-c2` | `lip/c2_pd_model/Dockerfile` | C2 PD inference service |
| `lip-c3` | `lip/c3_repayment_engine/Dockerfile` | C3 settlement monitor |
| `lip-c4` | `lip/c4_dispute_classifier/Dockerfile` | C4 dispute classifier |
| `lip-c5` | `lip/c5_streaming/Dockerfile` | C5 Kafka worker + event normaliser |
| `lip-c7` | `lip/c7_execution_agent/Dockerfile` | C7 execution agent |
| `lip-c8` | `lip/c8_license_manager/Dockerfile` | C8 license validator |

C6 AML velocity runs inside the pipeline service (no separate image).

## Kubernetes Manifests

K8s manifests live in `lip/infrastructure/k8s/`:

```
lip/infrastructure/k8s/
├── namespace.yaml          ← lip namespace
├── c1-deployment.yaml      ← GPU-enabled Deployment
├── c1-hpa.yaml             ← HPA: min 2, max 20 replicas
├── c7-deployment.yaml      ← Execution Agent Deployment
├── redis-cluster.yaml      ← Redis Cluster StatefulSet
├── network-policies.yaml   ← Default-deny + allow rules
└── secrets/                ← Secret manifests (do not commit values)
```

## Horizontal Pod Autoscaler (HPA)

C1 (Failure Classifier) auto-scales based on Kafka queue depth:

| Metric | Scale-Out | Scale-In |
|--------|----------|---------|
| Queue depth | > **100** messages | < **20** messages |
| Min replicas | 2 | — |
| Max replicas | 20 | — |

Constants: `HPA_SCALE_OUT_QUEUE_DEPTH = 100`, `HPA_SCALE_IN_QUEUE_DEPTH = 20` in `constants.py`.

## Environment Variables

| Variable | Component | Description |
|----------|-----------|-------------|
| `LIP_LICENSE_TOKEN` | C8 | HMAC-SHA256 signed license token (required at boot) |
| `LIP_LICENSE_TOKEN_JSON` | C8 | Inline JSON license token (alternative to `LIP_LICENSE_TOKEN`) |
| `LIP_ENFORCE_LICENSE_VALIDATION` | C8 | `"true"` in staging/prod to hard-fail on missing/invalid token |
| `LIP_MODEL_HMAC_KEY` | C2 | ≥32-byte HMAC key used to sign/verify the C2 `.pkl` + `.pkl.sig` pair. Required wherever `LIP_C2_MODEL_PATH` is set. |
| `LIP_C2_MODEL_PATH` | C2 | Absolute path to the signed C2 pickle inside the container (e.g. `/app/artifacts/c2_trained/c2_model.pkl`). Unset → bootstrap model. |
| `LIP_C1_MODEL_DIR` | C1 / API | Directory containing the C1 Torch checkpoint + optional calibrator / scaler / lgbm pickles. Unset → default NumPy model. |
| `LIP_C1_THRESHOLD` | C1 | Override for τ* (defaults to the constant in `lip/common/constants.py`). |
| `LIP_API_ENABLE_REAL_PIPELINE` | API | `"true"` mounts the real runtime pipeline (C1+C2+C4+C6+C7+C3). Unset → stub pipeline for tests. |
| `LIP_C4_BACKEND` | C4 | `groq` (live) or `mock`. Groq requires `GROQ_API_KEY`. |
| `LIP_C4_MODEL` | C4 | Groq model id (staging default: `qwen/qwen3-32b`). |
| `GROQ_API_KEY` | C4 | Groq API key for live Qwen3 dispute classification. |
| `LIP_API_HMAC_KEY` | API | HMAC-SHA256 signing key for inbound MIPLO requests. |
| `REDIS_PASSWORD` | All | Redis authentication password |
| `KAFKA_SSL_KEY_PASSWORD` | C5 | Kafka mTLS private key password |
| `PAGERDUTY_INTEGRATION_KEY` | Monitoring | PagerDuty Events v2 routing key |
| `LIP_KMS_ENDPOINT` | C7 | KMS endpoint URL for key operations |
| `LIP_PUSH_GATEWAY` | Monitoring | Prometheus Pushgateway `host:port` |

## Network Policies

All pods default to **deny-all ingress/egress**. Explicitly allowed connections:

| Source | Destination | Port | Purpose |
|--------|------------|------|---------|
| C5 (Kafka worker) | Kafka cluster | 9092 | Event ingestion |
| C1, C2, C3, C7 | Redis cluster | 6379 | State and cache |
| C7 | KMS endpoint | 443 | Key management |
| C8 (boot only) | BPI license server | 443 | Token validation |
| All pods | PagerDuty Events API | 443 | Alerting |

## Secrets Management

Secrets are injected via Kubernetes Secrets (mounted as environment variables, not files):

```bash
kubectl create secret generic lip-secrets \
  --from-literal=REDIS_PASSWORD='...' \
  --from-literal=LIP_LICENSE_TOKEN='...' \
  --from-literal=KAFKA_SSL_KEY_PASSWORD='...' \
  --from-literal=PAGERDUTY_INTEGRATION_KEY='...' \
  --namespace=lip
```

**Never** hardcode secrets in:
- `Dockerfile` or `docker-compose.yaml`
- Python source files
- Git-committed YAML manifests

## Health Checks

| Service | Liveness | Readiness |
|---------|---------|-----------|
| C1 | `GET /health` → 200 | `GET /ready` — model loaded + Redis reachable |
| C7 | `GET /health` → 200 | Kill switch state + KMS reachable |
| C8 | Boot validation (non-HTTP) | Token signature valid + not expired |

## Self-Hosted Staging Deployment

`scripts/deploy_staging_self_hosted.sh` is the canonical one-command staging deploy against a self-hosted Kubernetes runner (colima / kind / k3s / any cluster the runner's `kubeconfig` can reach). It is driven by `.github/workflows/deploy-staging.yml` and is the primary surface for pre-prod validation.

### Profiles

| Profile | Services deployed | When to use |
|---------|-------------------|-------------|
| `local-core` | `lip-api`, `lip-c2-pd`, `lip-c4-dispute`, `lip-c6-aml` | Default staging — exercises the full bridging path without GPU |
| `local-full-non-gpu` | adds `lip-c1-classifier` (NumPy backend) | When validating C1 artifact loading without requiring GPUs |
| `gpu-full` | adds `lip-c1-classifier` (Torch/GPU) | GPU-enabled smoke, requires node with `nvidia.com/gpu` capacity |
| `analytics` | `lip-api` only | Lightweight analytics/regulatory export validation |

### Secrets auto-loaded from `.secrets/`

The deploy script reads the following files if present and exports them as env vars before applying Kubernetes secrets:

| File (gitignored) | Env variable exported | Used by |
|-------------------|-----------------------|---------|
| `.secrets/groq_api_key` | `GROQ_API_KEY` | C4 Groq/Qwen3 live backend |
| `.secrets/c2_model_hmac_key` | `LIP_MODEL_HMAC_KEY` | C2 signed-artifact load verification |

Both are required for `local-core`, `local-full-non-gpu`, and `gpu-full` profiles. `analytics` does not require them.

### Signed C2 Artifact Injection

The C2 service loads a **signed pickle** at boot. The deploy script wires:

```yaml
env:
  - name: LIP_MODEL_HMAC_KEY
    valueFrom:
      secretKeyRef:
        name: lip-model-artifact-secret
        key: model_hmac_key
  - name: LIP_C2_MODEL_PATH
    value: /app/artifacts/c2_trained/c2_model.pkl
```

The `Dockerfile.c2` image `COPY`s `artifacts/c2_trained/` at build time (see `.dockerignore` whitelist — the directory is **gitignored** but build-context-included). If the `.pkl.sig` signature does not verify under `LIP_MODEL_HMAC_KEY`, `_load_or_bootstrap_model()` falls back to a bootstrap model and logs `C2 service ready (bootstrap)` instead of `(artifact)`.

### Real Runtime Pipeline in Staging

The `lip-api` deployment in staging is launched with `LIP_API_ENABLE_REAL_PIPELINE=true`, which mounts the full C1→C2→C4→C6→C7→C3 pipeline into the HTTP surface. The C1 engine is loaded from `LIP_C1_MODEL_DIR=/app/artifacts/c1_trained` via `TorchArtifactInferenceEngine` (see `lip/api/runtime_pipeline.py`). C4 runs Groq/Qwen3-32B live (`LIP_C4_BACKEND=groq`, `LIP_C4_MODEL=qwen/qwen3-32b`).

### Operator Commands

```bash
# 1. Generate a fresh signed C2 artifact locally (writes to artifacts/c2_trained/)
PYTHONPATH=. python scripts/generate_c2_artifact.py \
    --hmac-key-file .secrets/c2_model_hmac_key \
    --output-dir artifacts/c2_trained

# 2. Rebuild + deploy the local-core staging slice
LIP_API_IMAGE=lip-api:local \
LIP_C2_IMAGE=lip-c2:local \
LIP_C4_IMAGE=lip-c4:local \
LIP_C6_IMAGE=lip-c6:local \
./scripts/deploy_staging_self_hosted.sh --profile local-core

# 3. Confirm the artifact files are present inside the running pod — primary check.
# This is the canonical verification: if the files are mounted with the right sizes
# and signature present, the image was built with the intended artifacts.
kubectl -n lip-staging exec deploy/lip-c2-pd -- ls -l /app/artifacts/c2_trained/
# Expected: c2_model.pkl + c2_model.pkl.sig + c2_training_report.json

kubectl -n lip-staging exec deploy/lip-api -- ls -l /app/artifacts/c1_trained/
# Expected: c1_model_parquet.pt + c1_lgbm_parquet.pkl + train_metrics_parquet.json

# 4. (Optional, requires --log-level info in the uvicorn CMD)
# App-level loggers in lip/c2_pd_model/api.py and lip/api/runtime_pipeline.py emit
# "C2 service ready (artifact|bootstrap)" and "Runtime C1 engine ready (artifact:<path>|default)"
# at INFO. With the default CMD (no --log-level info), uvicorn suppresses these.
# To enable in a debug rebuild, add --log-level info to the relevant Dockerfile CMD.
kubectl -n lip-staging logs deploy/lip-c2-pd | grep "C2 service ready"
kubectl -n lip-staging logs deploy/lip-api | grep "Runtime C1 engine ready"
```

If the C2 logs later show `(bootstrap)` after `--log-level info` is enabled while `LIP_C2_MODEL_PATH` is set, the HMAC key in `.secrets/c2_model_hmac_key` does not match the key used when generating the artifact. Regenerate with the correct key and redeploy. Until `--log-level info` is wired, a mismatched key manifests as a `/predict` endpoint returning `model_source: "bootstrap"` on the `C2Service` state — inspected from a Python shell in the pod.

## CI/CD Pipeline

See `.github/workflows/` for the full CI/CD configuration:

```
push → lint (ruff) → type check (mypy) → unit tests → integration tests → build images → deploy (staging)
                                                                                        ↓
                                                                               manual approval
                                                                                        ↓
                                                                               deploy (production)
```

All production deployments require:
1. Zero ruff errors
2. All unit + integration tests passing
3. Valid `LIP_LICENSE_TOKEN` environment variable
4. Manual approval gate for production namespace
