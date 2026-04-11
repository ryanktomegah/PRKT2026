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
