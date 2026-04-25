from __future__ import annotations

import json
import secrets
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lip.api.auth import sign_request
from lip.c8_license_manager.license_token import ALL_COMPONENTS, LicenseToken, sign_token

_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "c1_trained"
_C1_CHECKPOINT = _ARTIFACT_DIR / "c1_model_parquet.pt"

_c1_artifacts_missing = pytest.mark.skipif(
    not _C1_CHECKPOINT.is_file(),
    reason=(
        "C1 torch checkpoint not present (artifacts/c1_trained/ is gitignored). "
        "Run `scripts/train_c1_on_parquet.py` or restore from CI artifact cache "
        "to exercise this path locally."
    ),
)


class _StubMetricsCollector:
    def generate_latest(self) -> str:
        return ""

    def increment(self, *args, **kwargs) -> None:
        return None


def _make_processor_token() -> tuple[str, str]:
    key = secrets.token_bytes(32)
    today = date.today()
    token = LicenseToken(
        licensee_id="SELF_HOSTED_STAGING",
        issue_date=today.isoformat(),
        expiry_date=(today + timedelta(days=30)).isoformat(),
        max_tps=500,
        aml_dollar_cap_usd=5_000_000,
        aml_count_cap=500,
        min_loan_amount_usd=500_000,
        deployment_phase="LICENSOR",
        licensee_type="PROCESSOR",
        sub_licensee_bics=["COBADEFF", "DEUTDEFF"],
        annual_minimum_usd=500_000,
        performance_premium_pct=0.15,
        platform_take_rate_pct=0.20,
        permitted_components=list(ALL_COMPONENTS),
    )
    signed = sign_token(token, key)
    return json.dumps(signed.to_dict(), separators=(",", ":")), key.hex()


def test_runtime_pipeline_requires_durable_offer_store(monkeypatch):
    from lip.api.runtime_pipeline import build_runtime_pipeline

    monkeypatch.setenv("LIP_REQUIRE_DURABLE_OFFER_STORE", "1")

    with pytest.raises(RuntimeError, match="LIP_REQUIRE_DURABLE_OFFER_STORE=1"):
        build_runtime_pipeline(
            kill_switch=object(),
            settlement_monitor=object(),
            borrower_registry=object(),
            known_entity_registry=object(),
            redis_client=None,
        )


@_c1_artifacts_missing
def test_real_runtime_pipeline_mounts_and_processes_miplo_request(monkeypatch):
    from lip.api import app as app_module

    token_json, key_hex = _make_processor_token()
    artifact_dir = _ARTIFACT_DIR
    monkeypatch.setenv("LIP_API_ENABLE_REAL_PIPELINE", "true")
    monkeypatch.setenv("LIP_C4_BACKEND", "mock")
    monkeypatch.setenv("LIP_C1_MODEL_DIR", str(artifact_dir))
    monkeypatch.setenv("LOKY_MAX_CPU_COUNT", "1")
    monkeypatch.setenv("LIP_API_HMAC_KEY", key_hex)
    monkeypatch.setenv("LIP_ENFORCE_LICENSE_VALIDATION", "true")
    monkeypatch.setenv("LIP_LICENSE_TOKEN_JSON", token_json)
    monkeypatch.setenv("LIP_LICENSE_KEY_HEX", key_hex)
    monkeypatch.setattr(app_module, "PrometheusMetricsCollector", _StubMetricsCollector)

    application = app_module.create_app()
    assert any(route.path == "/miplo/process" for route in application.routes)
    assert application.state.runtime_pipeline is not None
    assert application.state.processor_context is not None

    payload = {
        "uetr": "test-runtime-uetr-001",
        "individual_payment_id": "payment-001",
        "sending_bic": "COBADEFF",
        "receiving_bic": "DEUTDEFF",
        "amount": "75000.00",
        "currency": "USD",
        "rejection_code": "CURR",
        "narrative": "Invoice payment",
        "debtor_account": "DE89370400440532013000",
        "borrower": {
            "tax_id": "TAX-001",
            "has_financial_statements": True,
            "has_transaction_history": True,
            "has_credit_bureau": True,
            "months_history": 18,
            "transaction_count": 42,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    auth = sign_request("POST", "/miplo/process", body, bytes.fromhex(key_hex))

    with TestClient(application) as client:
        response = client.post(
            "/miplo/process",
            content=body,
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["uetr"] == payload["uetr"]
    assert data["tenant_id"] == "SELF_HOSTED_STAGING"
    assert isinstance(data["failure_probability"], float)
    assert isinstance(data["above_threshold"], bool)
    assert data["outcome"]


@_c1_artifacts_missing
def test_torch_artifact_c1_engine_loads_repo_checkpoint(monkeypatch):
    from lip.api.runtime_pipeline import TorchArtifactInferenceEngine

    artifact_dir = _ARTIFACT_DIR
    monkeypatch.setenv("LOKY_MAX_CPU_COUNT", "1")
    engine = TorchArtifactInferenceEngine(artifact_dir)

    result = engine.predict(
        {
            "payment_id": "artifact-check-001",
            "amount_usd": 75_000.0,
            "timestamp": "2026-04-23T12:00:00+00:00",
            "currency_pair": "USD_EUR",
            "sending_bic": "COBADEFF",
            "receiving_bic": "DEUTDEFF",
            "charge_type": "SHA",
            "message_type": "103",
            "beneficiary_name": "Acme Corp",
        }
    )

    assert 0.0 <= result["failure_probability"] <= 1.0
    assert isinstance(result["above_threshold"], bool)
    assert result["shap_top20"]
