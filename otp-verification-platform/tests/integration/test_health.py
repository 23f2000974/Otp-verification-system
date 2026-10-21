
"""Integration tests for the API health endpoint."""
from fastapi.testclient import TestClient
from otp_api.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "otp-verification-platform",
    }
