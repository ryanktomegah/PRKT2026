# Repository Guidelines

## Project Structure & Module Organization
`lip/` is the main package. Core production code lives in component folders such as `c1_failure_classifier/`, `c2_pd_model/`, `c6_aml_velocity/`, and `c7_execution_agent/`; shared schemas and constants live in `lip/common/`; the FastAPI surface is in `lip/api/`; tests are in `lip/tests/`. Mixed-language subsystems are colocated with their Python wrappers, for example `lip/c3/rust_state_machine/`, `lip/c6_aml_velocity/rust_velocity/`, `lip/c5_streaming/go_consumer/`, and `lip/c7_execution_agent/go_offer_router/`. Operational scripts live in `scripts/`, and longer-form specs, architecture notes, and governance docs live in `docs/`.

## Build, Test, and Development Commands
Set up a local environment with `python -m venv .venv && source .venv/bin/activate` and `pip install -e "lip/[all]"`. Start local Kafka-compatible Redpanda and Redis with `./scripts/start_local_infra.sh` or `docker compose up -d`. Use `ruff check lip/` for linting, `mypy lip/` for type checks, and `PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q` for the standard suite. Run component tests directly, for example `PYTHONPATH=. python -m pytest lip/tests/test_c6_aml_velocity.py -v`.

### Runtime Artifacts & Staging
Generate the signed C2 model artifact with `PYTHONPATH=. python scripts/generate_c2_artifact.py --hmac-key-file .secrets/c2_model_hmac_key`. Deploy the local staging slice (lip-api, lip-c2-pd, lip-c4-dispute, lip-c6-aml) with `./scripts/deploy_staging_self_hosted.sh --profile local-core`; other profiles are `local-full-non-gpu`, `gpu-full`, `analytics`. The real runtime pipeline activates via `LIP_API_ENABLE_REAL_PIPELINE=true`, with `LIP_C1_MODEL_DIR`, `LIP_C2_MODEL_PATH`, and `LIP_MODEL_HMAC_KEY` selecting the artifact load path. See `docs/operations/deployment.md` and `docs/engineering/developer-guide.md` for full details.

## Coding Style & Naming Conventions
Follow Python conventions already enforced by `pyproject.toml`: 4-space indentation, type annotations on public functions, and Ruff with a 100-character line length. Test modules use `test_*.py`; classes use `Test*`; functions use `test_*`. Prefer `Decimal` for money, `datetime.now(tz=timezone.utc)` over naive UTC calls, and Google-style docstrings for public APIs. Keep naming consistent with the component prefixes (`c1_`, `c2_`, `p10_`) used across the repo.

## Testing Guidelines
Pytest is the primary framework; markers include `slow` and `live`. Keep fast coverage in `lip/tests/`, and mark infrastructure-dependent checks explicitly. Before opening a PR, run `ruff check lip/` and the relevant `pytest` target. The repo advertises high coverage, so new production logic should ship with focused tests close to the affected component.

## Commit & Pull Request Guidelines
Recent history uses short imperative prefixes such as `fix: ...`, `test: ...`, and `docs: ...`; keep commit subjects concise and scoped. PRs should explain the affected component, note any infra or model prerequisites, and link supporting docs or issues when relevant. Include screenshots only for UI or report changes; otherwise, paste the exact verification commands you ran.

## Security & Governance Notes
Do not commit secrets, `.env` files, license tokens, or AML corpus files such as `c6_corpus_*.json`. Treat constants in `lip/common/constants.py` and other QUANT-locked parameters as governed values: change them only with explicit sign-off.
