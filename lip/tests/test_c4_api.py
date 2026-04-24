from fastapi.testclient import TestClient

from lip.c4_dispute_classifier.api import create_app
from lip.c4_dispute_classifier.model import DisputeClassifier, MockLLMBackend


def test_c4_api_import_and_health_do_not_require_backend(monkeypatch):
    monkeypatch.delenv("LIP_C4_BACKEND", raising=False)
    app = create_app()
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}

    response = client.post(
        "/classify",
        json={
            "rejection_code": None,
            "narrative": "Routine status update.",
            "amount": "100.00",
            "currency": "USD",
            "counterparty": "TESTBANK",
        },
    )
    assert response.status_code == 503


def test_c4_api_health_and_classify():
    app = create_app(DisputeClassifier(llm_backend=MockLLMBackend()))
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}

    response = client.post(
        "/classify",
        json={
            "rejection_code": None,
            "narrative": "Customer reports unauthorized transfer.",
            "amount": "100.00",
            "currency": "USD",
            "counterparty": "TESTBANK",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dispute_class"] == "DISPUTE_CONFIRMED"
    assert payload["prefilter_triggered"] is True
