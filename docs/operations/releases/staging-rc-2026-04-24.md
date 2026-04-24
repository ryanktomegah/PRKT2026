# Staging RC - 2026-04-24

Status: staging release candidate, not production-final.
Base commit: `1f4c632a7bd70a14fc0fb0cc30d0dbc98b099d18`

## Scope

This RC replaces the toy/smoke C1 and C2 artifacts with locally trained staging artifacts:

- C1 failure classifier: 5,000,000 generated payment corpus, 2,000,000 record training sample, 20 epochs, signed supplementary pickle artifacts.
- C2 PD model: 50,000 record DGEN corpus, 50 Optuna trials, 5 LightGBM models, signed artifact, Tier-3 stress gate required.
- Runtime: strict artifact loading verified for C1 and C2 with fallback disabled.

This is not the final production artifact set because the remote full production workflow remains blocked by account billing/spend-limit failure. The next production-final candidate should rerun C1 on the full remote target corpus once billing is restored.

## Model Results

C1:

- Corpus: `artifacts/staging_rc_c1_5m/payments_synthetic.parquet`
- Generated rows: 5,000,000
- Post-BLOCK filtered rows: 4,550,658
- Training sample: 2,000,000
- Epochs: 20
- Training-loop best chronological OOT AUC: 0.8839
- Post-training summary AUC: 0.887623
- Post-training summary split: random fallback before timestamp metrics fix
- LightGBM AUC: 0.886426
- PyTorch-only AUC: 0.884256
- Calibrated F2 threshold: 0.1100
- F2 score: 0.623269
- ECE: 0.188449 -> 0.069066

C2:

- Corpus: `artifacts/staging_rc_c2/c2_corpus_n50000_seed42.json`
- Records: 50,000
- Trials: 50
- Models: 5
- Backend: LightGBM 4.6.0 with `libomp`
- Held-out AUC: 0.931482085175773
- Brier: 0.03374044185210159
- KS: 0.7380619645214892
- Tier-3 stress gate: passed, 2,513 / 2,513 test-set Tier-3 PDs inside [0.05, 0.25]

## Artifact Hashes

```text
695200831e8f075312533c5bc6adb0ba7f7162851e298f355fe12989fb156ad2  artifacts/c1_trained/c1_model_parquet.pt
85d9da8135383ce9af79353f3284fc9c6a315cd9bd8002a35ab09feedd228fc8  artifacts/c1_trained/c1_lgbm_parquet.pkl
92c97315dc3888add2631db301a6bbf9e743b2a3c4e15fc096c6c422d496f911  artifacts/c1_trained/c1_lgbm_parquet.pkl.sig
d55446e709adaa0797ea6a6d307b69335e85efb3ef44e03755f0ba911e835389  artifacts/c1_trained/c1_calibrator.pkl
cc2cfe4c914aae960866a7d77403ac6b1309d987535f33928b7483ad72b07128  artifacts/c1_trained/c1_calibrator.pkl.sig
be68040be9c588caba2c13d5e1a05226406c881644c0bc41b2c9d6474b7ee987  artifacts/c1_trained/c1_scaler.pkl
3ff4d67ba17353addba60eafa3f63fdc859890e2f2d2441f973e2d4b99f13e1e  artifacts/c1_trained/c1_scaler.pkl.sig
76849651aa83a1be101477407b9d5a3446196a55a0ca63ec4561d04a6e47671e  artifacts/c1_trained/f2_threshold.txt
79f6a46ae1b1f3178bf953c8b0017652fb2005ade9db2ffdbceacf3e092c4002  artifacts/c1_trained/train_metrics_parquet.json
b340eba10d7bd116eb138f47c4f56ed680db40a5907c7f778e9c388768bba861  artifacts/c2_trained/c2_model.pkl
57bec989ce2bd2550b780d8abfd050f5052356d6e26aa9268dddfe8fae2d32ee  artifacts/c2_trained/c2_model.pkl.sig
910a95729b13c2c1f08a494c5b8cbcc00a1fa554ed3a6a43a404e0cfb7b23667  artifacts/c2_trained/c2_training_report.json
```

## Verification

Commands passed:

```bash
ruff check scripts/generate_c2_artifact.py scripts/train_c1_on_parquet.py lip/c2_pd_model/training.py lip/api/runtime_pipeline.py
PYTHONPATH=. python -m pytest lip/tests/test_c2_comprehensive.py::TestPipelineFullRun::test_run_end_to_end lip/tests/test_c2_comprehensive.py::TestPipelineStage8::test_empty_thin_file_passes lip/tests/test_c2_api.py::test_c2_api_loads_signed_artifact lip/tests/test_c1_lgbm_ensemble.py lip/tests/test_api_runtime_pipeline.py -q --tb=short
```

Result: `14 passed`.

Strict artifact load passed with:

- `LIP_REQUIRE_MODEL_ARTIFACTS=1`
- `LIP_C1_MODEL_DIR=artifacts/c1_trained`
- `LIP_C2_MODEL_PATH=artifacts/c2_trained/c2_model.pkl`
- `LIP_MODEL_HMAC_KEY` from `.secrets/c2_model_hmac_key`

Observed result:

```text
strict_artifact_load_ok
c1 TorchArtifactInferenceEngine
c2_source artifact
```

Container verification passed:

```bash
docker build -f lip/infrastructure/docker/Dockerfile.c7 -t lip-local-c7:staging-rc .
docker run --rm -e LIP_MODEL_HMAC_KEY=... -e LIP_REQUIRE_MODEL_ARTIFACTS=1 -e LIP_C1_MODEL_DIR=/app/artifacts/c1_trained -e LIP_C2_MODEL_PATH=/app/artifacts/c2_trained/c2_model.pkl lip-local-c7:staging-rc python -c "..."
```

Image: `lip-local-c7:staging-rc` / `45e19494159e`

Observed result:

```text
container_strict_artifact_load_ok
c1 TorchArtifactInferenceEngine
c2_source artifact
```

## Release Gates

Required staging environment:

- `LIP_REQUIRE_MODEL_ARTIFACTS=1`
- `LIP_MODEL_HMAC_KEY` set from the artifact signing key
- `LIP_C1_MODEL_DIR=/app/artifacts/c1_trained`
- `LIP_C2_MODEL_PATH=/app/artifacts/c2_trained/c2_model.pkl`
- `LIP_REQUIRE_DURABLE_OFFER_STORE=1`
- `REDIS_URL` configured
- `LIP_API_ENABLE_REAL_PIPELINE=true`

Engineering notes:

- C1 post-training metrics were generated before the adapter fix that passes timestamps into the summary split. The trained checkpoint itself used chronological OOT selection and restored best OOT AUC 0.8839.
- C2 artifact generation now refuses to write a signed artifact if the Tier-3 stress gate fails.
- C2 hyperparameter search now uses the same LightGBM backend factory as final ensemble training.
- C1 runtime now caps Torch threads before loading artifacts to avoid LightGBM/PyTorch runtime deadlock after `libomp` is installed.

## Recommendation

Use this artifact set for staging RC validation. Do not label it production-final until the full remote production-size C1 workflow completes after billing/spend-limit repair, and until staging deployment passes live API smoke, durable offer-store, and rollback drills.
