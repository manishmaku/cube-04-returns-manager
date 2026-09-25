"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient


def test_health_check_returns_200_and_healthy(client: TestClient):
    """GET /health must return 200 OK and status 'healthy'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "returns-manager"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data
