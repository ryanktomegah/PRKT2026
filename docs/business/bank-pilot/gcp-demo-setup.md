# GCP Demo Environment Setup Checklist

> Steps to deploy LIP on GCP Free Tier for pilot bank demonstrations.
> **Status:** Documentation only — actual deployment deferred to next session.

---

## Prerequisites

- [ ] Google account with billing enabled (Free Tier eligible)
- [ ] `gcloud` CLI installed locally
- [ ] Docker images built and pushed (via `docker-build.yml` or manual build)

---

## Step 1 — Create GCP Project

```bash
gcloud projects create lip-demo-2026 --name="LIP Demo Environment"
gcloud config set project lip-demo-2026
```

Enable billing:
```bash
gcloud billing accounts list
gcloud billing projects link lip-demo-2026 --billing-account=<ACCOUNT_ID>
```

---

## Step 2 — Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com
```

**Alternative (GKE Autopilot):**
```bash
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com
```

---

## Step 3 — Authenticate

```bash
gcloud auth login
gcloud auth configure-docker us-central1-docker.pkg.dev
gcloud config set project lip-demo-2026
gcloud config set compute/region us-central1
```

---

## Step 4 — Create Artifact Registry Repository

```bash
gcloud artifacts repositories create lip-images \
  --repository-format=docker \
  --location=us-central1 \
  --description="LIP container images"
```

### Push Images

**Option A — Build and push from local:**
```bash
# Tag and push C7 image
docker build -f lip/infrastructure/docker/Dockerfile.c7 -t us-central1-docker.pkg.dev/lip-demo-2026/lip-images/lip-c7:latest .
docker push us-central1-docker.pkg.dev/lip-demo-2026/lip-images/lip-c7:latest
```

**Option B — Use GHCR images directly:**

If using GitHub Container Registry (from `docker-build.yml`), configure Cloud Run to pull from GHCR:
```bash
# Images are at: ghcr.io/ryanktomegah/lip-c7:latest
# Cloud Run can pull from GHCR if the repo is public
```

---

## Step 5 — Deploy via Cloud Run (Simplest for Demo)

Cloud Run is the simplest option — no K8s cluster management, pay-per-request, free tier includes 2M requests/month.

```bash
# Deploy C7 (API + execution agent)
gcloud run deploy lip-c7 \
  --image=us-central1-docker.pkg.dev/lip-demo-2026/lip-images/lip-c7:latest \
  --port=8080 \
  --memory=2Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=1 \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="REDIS_URL=<REDIS_URL>,LIP_API_HMAC_KEY=<KEY>"
```

### Alternative — GKE Autopilot

For a more production-like demo with Helm:

```bash
# Create Autopilot cluster
gcloud container clusters create-auto lip-demo \
  --region=us-central1 \
  --project=lip-demo-2026

# Get credentials
gcloud container clusters get-credentials lip-demo --region=us-central1

# Deploy with Helm
helm upgrade --install lip ./lip/infrastructure/helm/lip \
  --namespace lip \
  --create-namespace \
  --values lip/infrastructure/helm/lip/values-dev.yaml \
  --set image.registry=us-central1-docker.pkg.dev/lip-demo-2026/lip-images \
  --set image.tag=latest
```

---

## Step 6 — Set Up Redis (Memorystore)

**Option A — Memorystore (managed Redis):**
```bash
gcloud redis instances create lip-demo-redis \
  --size=1 \
  --region=us-central1 \
  --tier=basic \
  --redis-version=redis_7_0
```

Get the Redis IP:
```bash
gcloud redis instances describe lip-demo-redis --region=us-central1 --format="get(host)"
```

**Option B — Skip Redis (in-memory mode):**

For a lightweight demo, LIP runs without Redis. Set `REDIS_URL=""` — all state is in-memory and lost on restart. Suitable for demonstration purposes only.

---

## Step 7 — Set Secrets

```bash
# Store HMAC key in Secret Manager
echo -n "your-hmac-key-hex" | gcloud secrets create lip-hmac-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding lip-hmac-key \
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

For Cloud Run, reference the secret:
```bash
gcloud run services update lip-c7 \
  --set-secrets="LIP_API_HMAC_KEY=lip-hmac-key:latest" \
  --region=us-central1
```

---

## Step 8 — Verify Health Endpoints

```bash
# Get the Cloud Run URL
SERVICE_URL=$(gcloud run services describe lip-c7 --region=us-central1 --format="value(status.url)")

# Liveness
curl ${SERVICE_URL}/health/live

# Readiness
curl ${SERVICE_URL}/health/ready

# Platform summary (if HMAC is disabled for demo)
curl ${SERVICE_URL}/admin/platform/summary
```

---

## Cost Estimate (Free Tier)

| Service | Free Tier Allowance | Demo Usage | Cost |
|---------|-------------------|-----------|------|
| Cloud Run | 2M requests/month, 360K vCPU-seconds | Minimal | $0 |
| Artifact Registry | 500 MB storage | ~200 MB (1 image) | $0 |
| Memorystore | None (not free tier) | 1 GB Basic | ~$35/month |
| Secret Manager | 6 active secret versions | 1 secret | $0 |

**Without Memorystore (in-memory mode): $0/month**
**With Memorystore: ~$35/month**

---

## Cleanup

```bash
# Delete Cloud Run service
gcloud run services delete lip-c7 --region=us-central1

# Delete Memorystore instance (if created)
gcloud redis instances delete lip-demo-redis --region=us-central1

# Delete Artifact Registry
gcloud artifacts repositories delete lip-images --location=us-central1

# Delete project (removes everything)
gcloud projects delete lip-demo-2026
```

---

## Next Steps (Deferred)

- [ ] Authenticate `gcloud` CLI
- [ ] Create GCP project with billing
- [ ] Build and push Docker images
- [ ] Deploy Cloud Run service
- [ ] Verify health endpoints from external network
- [ ] Run demo walkthrough against live deployment
