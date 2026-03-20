---
description: Validate LIP K8s manifests and Helm chart — checks template rendering, port consistency, secret refs, network policies. Run before deployment.
argument-hint: "[--env dev|staging|prod]"
allowed-tools: Bash, Read, Grep, Glob
---

Run the K8s manifest validation script to confirm manifests are deployment-ready.

```bash
PYTHONPATH=. python scripts/check_k8s_manifests.py $ARGUMENTS
```

**Checks performed:**
1. All 7 Dockerfiles (c1-c7) have corresponding K8s deployment YAMLs
2. `EXPOSE` ports in Dockerfiles match `containerPort` in deployments
3. `helm template` renders without errors for the specified environment (requires `helm` CLI)
4. No hardcoded secrets or API key patterns in manifest files
5. `values-prod.yaml` does not use `tag: latest`

**Environment overlays checked:**
- `--env dev` → `values-dev.yaml` (1 replica, no GPU, GHCR registry)
- `--env staging` → `values-staging.yaml` (reduced replicas, shared Redis)
- `--env prod` → `values-prod.yaml` (full replicas, GPU, managed Redis/Kafka)
- Default (no flag) → checks all three environments

After running, report:
1. Any missing Dockerfile ↔ deployment pairs
2. Port mismatches between Dockerfiles and deployment specs
3. Helm template errors per environment
4. Any secret hygiene violations
