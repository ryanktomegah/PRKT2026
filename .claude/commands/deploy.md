# LIP Deployment Operations

Build, package, and deploy LIP components.

## Docker Build
Each component has its own Dockerfile in `lip/infrastructure/docker/`:

```bash
# Build individual component
docker build -f lip/infrastructure/docker/Dockerfile.c1 -t lip-c1:latest .
docker build -f lip/infrastructure/docker/Dockerfile.c2 -t lip-c2:latest .
# ... through Dockerfile.c7
```

## Kubernetes Deployment
Manifests in `lip/infrastructure/kubernetes/`:
- `c1-deployment.yaml` through `c7-deployment.yaml`
- `hpa.yaml` — Horizontal Pod Autoscaler (queue depth + CPU)
- `network-policies.yaml` — Inter-component traffic rules
- `secrets.yaml` — Secret templates (DO NOT commit actual values)

## Helm Chart
```bash
# Install/upgrade
helm upgrade --install lip lip/infrastructure/helm/lip/ \
  --namespace lip-production \
  --values lip/infrastructure/helm/lip/values.yaml
```

## HPA Configuration
| Component | Min | Max | Scale-out trigger |
|-----------|-----|-----|-------------------|
| C1 | 2 | 20 | Queue depth > 100 |
| C5 | 3 | 30 | Consumer lag > 1000 |
| C7 | 2 | 10 | CPU > 70% |

## Pre-deployment Checklist
1. CI green on target branch
2. All tests pass locally (`/test`)
3. Lint clean (`/lint`)
4. Model artifacts exist and validated
5. License tokens configured (C8)
6. Secrets populated in K8s (never in manifests)
7. Network policies reviewed

## Rules
- NEVER deploy with failing tests
- NEVER commit actual secrets to K8s manifests
- Docker images must use non-root users
- All components must pass health checks before receiving traffic
- Blue-green deployment for zero-downtime updates
