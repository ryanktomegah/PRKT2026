from fastapi.testclient import TestClient

from lip.c3_repayment_engine.api import create_app


def test_c3_api_health():
    with TestClient(create_app()) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}
