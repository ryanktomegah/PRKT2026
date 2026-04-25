# `scripts/` and `lip/scripts/` — CLI Tools

> **Operational scripts.** Two directories: `scripts/` at the repo root for ops / CI / local infra, and `lip/scripts/` inside the package for evaluation tooling that needs to import from `lip` directly.

---

## `/scripts/` — repo-root operations

| File | Purpose |
|------|---------|
| `start_local_infra.sh` | Brings up local Redpanda (Kafka) + Redis (TLS, port 6380) for `test_e2e_live.py` and end-to-end manual testing. Run this before any test marked `@pytest.mark.live`. |
| `init_topics.sh` | Creates the canonical Kafka topics on a fresh Redpanda instance (paired with `start_local_infra.sh`) |
| `train_all.py` | Top-level training entry point. Wraps `lip/train_all.py` with environment setup. Trains C1 (GraphSAGE + TabTransformer + LightGBM ensemble) and C2 (PD model) end-to-end on the synthetic corpus. |
| `train_c1_on_parquet.py` | C1-only training against a parquet corpus, used when iterating on the C1 model independently of the rest of the pipeline |
| `eval_c1_checkpoint.py` | Evaluate a saved C1 checkpoint against the validation cohort. Reports AUC, F2, ECE, and threshold-calibration metrics. |
| `evaluate_c4_on_negation_corpus.py` | Run C4 against the 100-case negation suite (`lip/c4_dispute_classifier/negation.py`). **Use prefilter-only FP rate** (not full-pipeline accuracy) as the C4 Step 2x metric — see `CLAUDE.md` § C4 Dispute Classifier Notes. |
| `validate_c1_pilot.py` | Pilot-data validation script for C1 — runs out-of-time validation against a held-out time slice |
| `monitor_c1.py` / `monitor_c1_gh.py` | C1 drift monitoring; the `_gh` variant posts results as a GitHub Actions check |
| `benchmark_pipeline.py` | End-to-end latency benchmark — runs the full pipeline against a synthetic event stream and reports p50 / p95 / p99 against the 94 ms SLO. Used by `docs/benchmark-results.md`. |
| `run_poc_validation.py` | Reproduces the figures in [`../poc-validation-report.md`](../poc-validation-report.md) — C1/C2/C4/C6 metrics on the synthetic corpus |
| `check_k8s_manifests.py` | Static linting of `lip/infrastructure/` Helm and K8s manifests against the canonical security requirements (PSS labels, securityContext, network policies, image pull policy). Run in CI. |
| `check_redis_wiring.py` | Verifies that every code path that talks to Redis goes through `lip/common/redis_factory.py` (no direct `redis.Redis(...)` calls leaking past the factory) |
| `check_temporal_features.py` | Verifies temporal-clustering integrity in DGEN-generated corpora — labels preserved, shapes preserved, epoch bounds correct, no train/test leakage on stratified splits |
| `generate_c2_artifact.py` | Trains a C2 PD model on synthetic data and writes a **signed** pickle (`artifacts/c2_trained/c2_model.pkl` + `.pkl.sig`) plus a `c2_training_report.json`. Requires `LIP_MODEL_HMAC_KEY` (≥32 bytes) or `--hmac-key-file`. Output is gitignored — regenerate per environment, never commit the binary. Consumed by `lip/c2_pd_model/api.py` via `LIP_C2_MODEL_PATH`. |
| `deploy_staging_self_hosted.sh` | One-command staging deploy against a self-hosted `kubeconfig` (colima / kind / k3s). Profiles: `local-core` (lip-api + lip-c2-pd + lip-c4-dispute + lip-c6-aml), `local-full-non-gpu`, `gpu-full`, `analytics`. Auto-loads `.secrets/groq_api_key` → `GROQ_API_KEY` and `.secrets/c2_model_hmac_key` → `LIP_MODEL_HMAC_KEY`. Injects `LIP_API_ENABLE_REAL_PIPELINE=true` + `LIP_C1_MODEL_DIR` + `LIP_C2_MODEL_PATH` into the API/C2 pods. See [`../../operations/deployment.md`](../../operations/deployment.md) § Self-Hosted Staging Deployment. |
| `make_kubeconfig.sh` / `set_github_kubeconfig.sh` | Compose a service-account-scoped kubeconfig for the self-hosted runner and publish it to the GitHub Actions secret consumed by `.github/workflows/deploy-staging.yml`. |

## `/lip/scripts/` — package-internal tooling

| File | Purpose |
|------|---------|
| `eval_c1_auc.py` | C1 AUC evaluation against in-package corpora |
| `eval_c1_auc_torch.py` | Same as above but using the PyTorch C1 backend (`graphsage_torch.py` + `tabtransformer_torch.py`) |
| `simulate_pipeline.py` | In-package pipeline simulator — drives `lip/pipeline.py` against generated events without any HTTP layer. Useful for one-off latency profiling and reproducing audit-log scenarios. |

These live inside the package because they import freely from `lip.c{N}_*` and `lip.common`, which a script under `scripts/` would have to do via PYTHONPATH gymnastics.

---

## Common patterns

- **PYTHONPATH**: every script that imports from `lip` requires `PYTHONPATH=.` to be set when invoked from the repo root. This is documented in `CLAUDE.md` and is a recurring pitfall for new contributors.
- **Model artifacts go to `artifacts/`**, which is gitignored. Never commit model binaries (`CLAUDE.md` § Key Rules).
- **AML corpora (`c6_corpus_*.json`)** are gitignored and must never be committed (CIPHER refusal rule).
- **Live infra**: scripts that touch Redis or Kafka assume `start_local_infra.sh` has been run and infrastructure is reachable on `localhost:6380` (Redis TLS) and `localhost:9092` (Redpanda).

## Cross-references

- **Operational guide**: [`../data-pipeline.md`](../data-pipeline.md) for training command sequences
- **Deployment**: [`../../operations/deployment.md`](../../operations/deployment.md) for the production K8s context (these scripts are local-dev / CI only)
- **Test suite**: [`tests.md`](tests.md) — `test_e2e_live.py` is the consumer of `start_local_infra.sh`
- **CI**: `.github/workflows/` (run via `gh run list --repo ryanktomegah/PRKT2026`)
