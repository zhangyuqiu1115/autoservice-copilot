from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    """The health endpoint should return valid application information."""

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()

    assert body["status"] == "ok"
    assert body["application"] == "AutoService Copilot API"
    assert body["version"] == "0.1.0"
    assert body["environment"] == "development"

    timestamp = datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
    assert timestamp.tzinfo is not None