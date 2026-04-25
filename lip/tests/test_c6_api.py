from fastapi.testclient import TestClient

from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.api import create_app
from lip.c6_aml_velocity.velocity import VelocityChecker


def test_c6_api_health_and_check():
    checker = AMLChecker(
        velocity_checker=VelocityChecker(salt=b"test_salt_32_bytes_for_c6_api___"),
        entity_name_resolver=None,
    )
    client = TestClient(create_app(checker))

    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}

    response = client.post(
        "/check",
        json={
            "entity_id": "BANKA123",
            "amount": "100.00",
            "beneficiary_id": "BENE456",
            "entity_name": "Acme Trading Ltd",
            "beneficiary_name": "Globex Imports",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is True
    assert payload["reason"] is None
    assert payload["velocity_result"]["passed"] is True
