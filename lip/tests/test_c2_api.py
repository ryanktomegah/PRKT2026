from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lip.c2_pd_model.api import create_app
from lip.c2_pd_model.synthetic_data import generate_pd_training_data
from lip.c2_pd_model.training import PDTrainingPipeline, TrainingConfig


def test_c2_api_health_and_predict():
    client = TestClient(create_app())

    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}

    response = client.post(
        "/predict",
        json={
            "payment": {
                "amount_usd": 1250000.0,
                "currency_pair": "USD_EUR",
                "sending_bic": "AAAABBCC",
                "receiving_bic": "DDDDEEFF",
                "timestamp": "2026-04-23T12:00:00Z",
                "corridor_failure_rate": 0.05,
                "sending_jurisdiction": "US",
                "receiving_jurisdiction": "EU",
            },
            "borrower": {
                "tax_id": "TAX-123",
                "has_financial_statements": True,
                "has_transaction_history": True,
                "has_credit_bureau": True,
                "months_history": 24,
                "transaction_count": 100,
                "current_assets": 2000000,
                "current_liabilities": 1000000,
                "total_assets": 5000000,
                "total_liabilities": 2500000,
                "working_capital": 1000000,
                "retained_earnings": 500000,
                "ebit": 250000,
                "market_cap": 4000000,
                "revenue": 3000000,
                "current_ratio": 2.0,
                "debt_to_equity": 0.8,
                "interest_coverage": 4.0,
                "asset_value": 7000000,
                "debt": 2500000,
                "asset_vol": 0.25,
                "risk_free": 0.04,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert 0.0 <= payload["pd_score"] <= 1.0
    assert payload["fee_bps"] >= 300
    assert payload["tier"] == 1
    assert len(payload["borrower_id_hash"]) == 64


def test_c2_api_loads_signed_artifact(monkeypatch, tmp_path: Path):
    records = generate_pd_training_data(n_samples=160, seed=7)
    model, _ = PDTrainingPipeline(
        TrainingConfig(n_trials=1, n_models=1, random_seed=7)
    ).run(records)

    model_key = "c2_test_model_hmac_key__32bytes__"
    assert len(model_key.encode("utf-8")) >= 32
    model_path = tmp_path / "c2_model.pkl"
    monkeypatch.setenv("LIP_MODEL_HMAC_KEY", model_key)
    model.save(str(model_path))

    monkeypatch.setenv("LIP_C2_MODEL_PATH", str(model_path))
    app = create_app()
    assert app.state.c2_service.model_source == "artifact"

    client = TestClient(app)
    response = client.post(
        "/predict",
        json={
            "payment": {
                "amount_usd": 250000.0,
                "currency_pair": "USD_EUR",
                "sending_bic": "AAAABBCC",
                "receiving_bic": "DDDDEEFF",
                "timestamp": "2026-04-23T12:00:00Z",
                "corridor_failure_rate": 0.04,
                "sending_jurisdiction": "US",
                "receiving_jurisdiction": "DE",
            },
            "borrower": {
                "tax_id": "TAX-456",
                "has_financial_statements": True,
                "has_transaction_history": True,
                "has_credit_bureau": True,
                "months_history": 18,
                "transaction_count": 42,
                "current_assets": 1500000,
                "current_liabilities": 900000,
                "total_assets": 4500000,
                "total_liabilities": 2100000,
                "working_capital": 600000,
                "retained_earnings": 450000,
                "ebit": 200000,
                "market_cap": 2500000,
                "revenue": 2700000,
                "current_ratio": 1.8,
                "debt_to_equity": 0.7,
                "interest_coverage": 3.5,
                "asset_value": 5500000,
                "debt": 2200000,
                "asset_vol": 0.20,
                "risk_free": 0.04,
            },
        },
    )

    assert response.status_code == 200
    assert 0.0 <= response.json()["pd_score"] <= 1.0
